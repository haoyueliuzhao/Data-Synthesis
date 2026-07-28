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
    export_training_utility_review,
    score_generated_response,
    write_reference_training_preflight,
)
from trusted_synthesis.experiments.training_utility_mvp.data import (
    _cohort_manifest,
    _reference_and_evaluation_records,
    _reference_response,
)
from trusted_synthesis.experiments.training_utility_mvp.evaluation import (
    _ensure_evaluation_contract,
    _evaluation_shard_from_environment,
    _load_evaluation_checkpoints,
    _write_evaluation_checkpoint,
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
        candidate_tasks_per_domain=3,
        evaluation_tasks_per_domain=1,
        cohort_size=6,
        minimum_real_candidate_completion_rate=2 / 3,
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
    assert all(counts["accepted"] == 2 for counts in readiness.observed_per_domain.values())
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
    assert (
        sum(item.counterfactual_repair for item in cohorts[UtilityCohort.CONTRACT_COUNTERFACTUAL])
        == 3
    )


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
    assert result.execution_coverage == 1
    assert result.operation_grounding_score == 1
    assert result.tool_necessity_score == 1

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


def test_training_utility_review_export_flattens_question_answer_and_evidence(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "data"
    output_dir = tmp_path / "review"
    config = TrainingUtilityMVPConfig(
        candidate_tasks_per_domain=2,
        evaluation_tasks_per_domain=1,
        cohort_size=6,
        max_steps=1,
    )
    write_reference_training_preflight(config, input_dir)

    manifest = export_training_utility_review(input_dir, output_dir)

    rows = [
        json.loads(line)
        for line in (output_dir / "qa_review.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert manifest.record_count == 9
    assert manifest.cohort_counts == {"D2_reference_workflow": 6, "evaluation": 3}
    assert manifest.domain_counts == {"finance": 3, "legal": 3, "science": 3}
    assert len(rows) == 9
    assert all(row["question"] for row in rows)
    assert all("reference_answer" in row for row in rows)
    assert all(row["reference_answer_text"] for row in rows)
    assert all(row["selected_evidence_ids"] for row in rows)
    assert all(
        set(row["selected_evidence_ids"]).issubset(row["available_evidence_ids"]) for row in rows
    )
    assert all(any(item["selected"] for item in row["evidence"]) for row in rows)
    assert (output_dir / "qa_review.md").is_file()
    assert (output_dir / "markdown" / "D2_reference_workflow.md").is_file()
    assert (output_dir / "markdown" / "evaluation.md").is_file()
    assert "### Question" in (output_dir / "markdown" / "D2_reference_workflow.md").read_text(
        encoding="utf-8"
    )


def test_training_utility_review_export_fails_on_invalid_embedded_json(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "data"
    input_dir.mkdir()
    records, _ = _reference_and_evaluation_records(
        TrainingUtilityMVPConfig(
            candidate_tasks_per_domain=2,
            evaluation_tasks_per_domain=1,
            cohort_size=6,
            max_steps=1,
        )
    )
    broken = records[0].model_copy(update={"user_prompt": "{"})
    (input_dir / "D2_reference_workflow.jsonl").write_text(
        broken.model_dump_json() + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid JSON in user_prompt"):
        export_training_utility_review(input_dir, tmp_path / "review")


def test_training_utility_supports_oversupplied_per_domain_pools() -> None:
    config = TrainingUtilityMVPConfig(
        candidate_tasks_per_domain=2,
        evaluation_tasks_per_domain=1,
        candidate_task_targets={"finance": 8, "legal": 6, "science": 9},
        evaluation_task_targets={"finance": 2, "legal": 3, "science": 4},
        cohort_size=6,
        max_steps=1,
    )

    training, evaluation = _reference_and_evaluation_records(config)

    assert config.resolved_candidate_task_targets == {
        "finance": 8,
        "legal": 6,
        "science": 9,
    }
    assert config.resolved_evaluation_task_targets == {
        "finance": 2,
        "legal": 3,
        "science": 4,
    }
    assert {
        domain: sum(item.domain == domain for item in training)
        for domain in config.resolved_candidate_task_targets
    } == config.resolved_candidate_task_targets
    assert {
        domain: sum(item.domain == domain for item in evaluation)
        for domain in config.resolved_evaluation_task_targets
    } == config.resolved_evaluation_task_targets
    assert all(item.metadata["pattern_id"] for item in (*training, *evaluation))
    assert all(item.metadata["program_signature"] for item in (*training, *evaluation))
    assert all(item.metadata["structural_group_id"] for item in (*training, *evaluation))


def test_cohort_manifest_rejects_duplicate_content_addressed_records() -> None:
    config = TrainingUtilityMVPConfig(
        candidate_tasks_per_domain=2,
        evaluation_tasks_per_domain=1,
        cohort_size=6,
        max_steps=1,
    )
    reference, _ = _reference_and_evaluation_records(config)
    record = reference[0]

    with pytest.raises(ValueError, match="duplicate record IDs"):
        _cohort_manifest(record.cohort, (record, record))


def test_evaluation_checkpoints_are_atomic_and_contract_bound(tmp_path: Path) -> None:
    _, evaluation = _reference_and_evaluation_records(
        TrainingUtilityMVPConfig(
            candidate_tasks_per_domain=2,
            evaluation_tasks_per_domain=1,
            cohort_size=6,
            max_steps=1,
        )
    )
    checkpoint_dir = tmp_path / "prediction_checkpoints"
    checkpoint_dir.mkdir()
    outcome = score_generated_response(
        evaluation[0],
        evaluation[0].assistant_target,
    )

    _write_evaluation_checkpoint(checkpoint_dir / "000000.json", outcome)
    loaded = _load_evaluation_checkpoints(evaluation, checkpoint_dir)

    assert loaded == {evaluation[0].record_id: outcome}
    assert not tuple(checkpoint_dir.glob("*.tmp"))

    contract_path = tmp_path / "evaluation_contract.json"
    contract = {
        "cohort": "base",
        "config_hash": "config:test",
        "evaluation_dataset_hash": "dataset:test",
        "adapter_dir": None,
    }
    _ensure_evaluation_contract(contract_path, contract)
    _ensure_evaluation_contract(contract_path, contract)
    with pytest.raises(ValueError, match="different evaluation contract"):
        _ensure_evaluation_contract(
            contract_path,
            {**contract, "cohort": "other"},
        )


def test_evaluation_shard_environment_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _evaluation_shard_from_environment() == (0, 1)
    monkeypatch.setenv("TRAINING_UTILITY_EVAL_SHARD_COUNT", "2")
    monkeypatch.setenv("TRAINING_UTILITY_EVAL_SHARD_INDEX", "1")
    assert _evaluation_shard_from_environment() == (1, 2)
    monkeypatch.setenv("TRAINING_UTILITY_EVAL_SHARD_INDEX", "2")
    with pytest.raises(ValueError, match="within the shard count"):
        _evaluation_shard_from_environment()
