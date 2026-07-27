from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.core.evaluation.critic import (
    AcceptabilityLabel,
    QualityCriticPrediction,
)
from trusted_synthesis.core.evaluation.utility import UtilityCohort
from trusted_synthesis.core.task.schema import PlanningTrack, RetrievalTrack
from trusted_synthesis.experiments.agent_validation import (
    AgentValidationConfig,
    run_agent_validation,
)
from trusted_synthesis.experiments.agent_validation.tracks import (
    materialize_track_variant,
)
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_cases,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    build_pattern_validation_cases,
)
from trusted_synthesis.experiments.training_utility_mvp import (
    TrainingUtilityMVPConfig,
    aggregate_evaluation_outcomes,
    audit_training_utility_readiness,
    build_training_utility_datasets,
    score_generated_response,
    write_reference_training_preflight,
)
from trusted_synthesis.experiments.training_utility_mvp.data import (
    _reference_and_evaluation_records,
    _reference_response,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import AgentModelConfig, ModelCallTelemetry


class ScriptedCandidateClient:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = payloads
        self._config = AgentModelConfig(
            provider="scripted",
            endpoint="https://models.example.test/v1/chat/completions",
            model="deepseek-v4-pro",
            api_key_env="TEST_ONLY_KEY",
            auto_discover_models=False,
            maximum_model_attempts=1,
        )

    @property
    def config(self) -> AgentModelConfig:
        return self._config

    def complete_json(self, prompt: str):
        assert '"oracle_contract":' not in prompt
        payload = self._payloads.pop(0)
        return payload, ModelCallTelemetry(
            provider="scripted",
            endpoint_host="models.example.test",
            model_requested="deepseek-v4-pro",
            model_selected="deepseek-v4-pro",
            response_model="deepseek-v4-pro",
            request_hash=canonical_hash(prompt, prefix="test_request:"),
            response_hash=canonical_hash(payload, prefix="test_response:"),
            http_status=200,
            http_success=True,
            json_contract_success=True,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )


def test_training_utility_data_contract_builds_balanced_d1_through_d5() -> None:
    utility_config = TrainingUtilityMVPConfig(
        candidate_tasks_per_domain=2,
        evaluation_tasks_per_domain=1,
        cohort_size=6,
        max_steps=1,
    )
    cases = (
        *build_finance_counterfactual_cases(count=2),
        *build_pattern_validation_cases(per_domain=2),
    )
    payloads = []
    for case in cases:
        task = materialize_track_variant(
            case.task,
            case.corpus,
            retrieval_track=RetrievalTrack.RESOLVED,
            planning_track=PlanningTrack.PLAN_GIVEN,
        )
        payloads.append(_reference_response(task, case.bundle, case.registry))
    artifacts = run_agent_validation(
        AgentValidationConfig(
            model=ScriptedCandidateClient([]).config,
            tasks_per_domain=2,
            retrieval_tracks=(RetrievalTrack.RESOLVED,),
            planning_tracks=(PlanningTrack.PLAN_GIVEN,),
            run_model_critic=False,
            generate_counterfactuals=True,
            selection_target=6,
        ),
        ScriptedCandidateClient(payloads),
    )
    updated_samples = []
    for sample in artifacts.report.samples:
        assert sample.critic_example_id is not None
        prediction = QualityCriticPrediction(
            prediction_id=canonical_hash(
                sample.critic_example_id,
                prefix="test_critic_prediction:",
            ),
            example_id=sample.critic_example_id,
            model_id="deepseek-v4-pro",
            model_manifest_hash="test-manifest",
            accept_probability=0.99,
            predicted_acceptability=AcceptabilityLabel.ACCEPT,
        )
        updated_samples.append(sample.model_copy(update={"critic_prediction": prediction}))
    report = artifacts.report.model_copy(
        update={
            "samples": tuple(updated_samples),
            "critic_attempted_count": 6,
            "critic_success_count": 6,
            "critic_selected_model_counts": {"deepseek-v4-pro": 6},
        }
    )
    readiness = audit_training_utility_readiness(
        utility_config,
        report,
        artifacts.critic_dataset,
    )

    cohorts, evaluation, manifest = build_training_utility_datasets(
        utility_config,
        report,
        artifacts.critic_dataset,
    )

    assert readiness.status == "ready"
    assert readiness.blockers == ()
    assert all(
        counts["accepted"] == 2
        for counts in readiness.observed_per_domain.values()
    )
    assert set(cohorts) == set(UtilityCohort)
    assert all(len(records) == 6 for records in cohorts.values())
    assert all(
        {item.domain for item in records} == {"finance", "legal", "science"}
        for records in cohorts.values()
    )
    assert len(evaluation) == 3
    assert manifest.train_evaluation_overlap_count == 0
    assert manifest.accepted_real_candidate_count == 6
    assert manifest.critic_reviewed_accepted_count == 6
    assert manifest.critic_model_ids == ("deepseek-v4-pro",)
    assert sum(
        item.counterfactual_repair
        for item in cohorts[UtilityCohort.CONTRACT_COUNTERFACTUAL]
    ) == 3


def test_training_utility_scorer_separates_contract_and_answer_accuracy(
    tmp_path: Path,
) -> None:
    _, evaluation = _reference_and_evaluation_records(
        TrainingUtilityMVPConfig(
            candidate_tasks_per_domain=2,
            evaluation_tasks_per_domain=1,
            cohort_size=6,
            max_steps=1,
        )
    )
    gold_outcomes = tuple(
        score_generated_response(item, item.assistant_target) for item in evaluation
    )
    result = aggregate_evaluation_outcomes(
        cohort="gold",
        adapter_dir=None,
        records=evaluation,
        outcomes=gold_outcomes,
        prediction_path=tmp_path / "predictions.jsonl",
    )
    assert result.response_contract_rate == 1
    assert result.end_to_end_rate == 1
    assert result.evidence_recall == 1
    assert result.operation_exact_rate == 1

    mutated = json.loads(evaluation[0].assistant_target)
    mutated["final_answer"]["result"] = {"unsupported": "answer"}
    outcome = score_generated_response(
        evaluation[0],
        json.dumps(mutated),
    )
    assert outcome["valid_json"] is True
    assert outcome["response_contract"] is True
    assert outcome["answer_exact"] is False
    assert outcome["end_to_end"] is False


def test_training_utility_rejects_unbalanced_fraction_contract() -> None:
    with pytest.raises(ValueError, match="divisible by three"):
        TrainingUtilityMVPConfig(
            candidate_tasks_per_domain=3,
            cohort_size=9,
            d1_counterfactual_fraction=0.5,
        )


def test_reference_training_preflight_is_balanced_and_disjoint(tmp_path: Path) -> None:
    config = TrainingUtilityMVPConfig(
        candidate_tasks_per_domain=2,
        evaluation_tasks_per_domain=1,
        cohort_size=6,
        max_steps=1,
    )

    manifest = write_reference_training_preflight(config, tmp_path)

    assert manifest["cohort_domain_counts"] == {
        "finance": 2,
        "legal": 2,
        "science": 2,
    }
    assert manifest["evaluation_domain_counts"] == {
        "finance": 1,
        "legal": 1,
        "science": 1,
    }
    assert manifest["training_evaluation_overlap_count"] == 0
    assert (tmp_path / "D2_reference_workflow.jsonl").is_file()
    assert (tmp_path / "evaluation.jsonl").is_file()
