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
    CohortTrainingResult,
    TrainingUtilityMVPConfig,
    aggregate_evaluation_outcomes,
    audit_training_utility_readiness,
    build_qa_review_record,
    build_training_utility_datasets,
    export_traditional_qa,
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
from trusted_synthesis.experiments.training_utility_mvp.model_security import (
    validate_adapter_artifact,
    validate_model_loading_contract,
)
from trusted_synthesis.experiments.training_utility_mvp.training import (
    _completed_training_budget_matches,
    _encode_records,
    _schedule_supervised_token_budget,
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


class _CharacterChatTokenizer:
    def apply_chat_template(
        self,
        messages: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
    ) -> str:
        assert tokenize is False
        text = "".join(f"<{item['role']}>{item['content']}</{item['role']}>" for item in messages)
        if add_generation_prompt:
            text += "<assistant>"
        return text

    def __call__(self, text: str, *, add_special_tokens: bool) -> dict[str, list[int]]:
        assert add_special_tokens is False
        return {"input_ids": [ord(item) for item in text]}


def test_remote_model_loading_requires_immutable_revision(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="immutable"):
        validate_model_loading_contract("vendor/model", None)
    with pytest.raises(ValueError, match="immutable"):
        validate_model_loading_contract("vendor/model", "main")

    validate_model_loading_contract("vendor/model", "a" * 40)
    local_model = tmp_path / "local_model"
    local_model.mkdir()
    validate_model_loading_contract(str(local_model), None)


def test_adapter_loading_requires_safetensors(tmp_path: Path) -> None:
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir()
    with pytest.raises(ValueError, match="adapter_model.safetensors"):
        validate_adapter_artifact(adapter_dir)

    (adapter_dir / "adapter_model.safetensors").write_bytes(b"safe-test-placeholder")
    validate_adapter_artifact(adapter_dir)


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
    assert manifest.train_evaluation_subject_overlap_count == 0
    assert manifest.train_evaluation_evidence_overlap_count == 0
    assert manifest.train_evaluation_evidence_version_overlap_count == 0
    assert manifest.train_evaluation_source_record_overlap_count == 0
    assert manifest.train_evaluation_binding_overlap_count == 0
    assert manifest.train_evaluation_program_signature_overlap_count > 0
    assert manifest.internal_evaluation_isolation_status == "passed"
    assert manifest.evaluation_track == "internal_iid_contract"
    assert manifest.external_benchmark_status == "not_executed"
    assert manifest.accepted_real_candidate_count == 6
    assert manifest.critic_reviewed_accepted_count == 6
    assert manifest.critic_model_ids == ("deepseek-v4-pro",)
    assert manifest.d5_selection_status == "complete"
    assert manifest.d5_selection_id
    assert all(item.source_kind == "real_agent" for item in cohorts[UtilityCohort.RANDOM_SYNTHETIC])
    assert all(
        not item.counterfactual_repair
        and item.metadata["training_mode"] == "solve"
        and item.metadata["feedback_counterfactual_example_ids"]
        for item in cohorts[UtilityCohort.CONTRACT_COUNTERFACTUAL]
    )
    assert all(
        item.metadata["critic_role"] == "advisory_ranking_only"
        and item.metadata["quality_selection_id"] == manifest.d5_selection_id
        for item in cohorts[UtilityCohort.CRITIC_SELECTED]
    )
    assert all(
        item.training_format == "host_instrumented_joint"
        and tuple(message.role for message in item.messages)
        == ("system", "user", "assistant", "tool", "assistant")
        for records in cohorts.values()
        for item in records
    )
    for records in cohorts.values():
        for item in records:
            supervised = "".join(message.content for message in item.messages if message.supervise)
            assert "execution_trace" not in supervised
            assert "execution_id" not in supervised
            assert "source_locator" not in supervised
            host_feedback = json.loads(item.messages[3].content)
            assert host_feedback["schema_version"] == "host_execution_feedback.v2"
            assert "raw_output_result" in host_feedback
            assert "execution:host_agent_execution:" not in json.dumps(
                host_feedback["output_result"],
                sort_keys=True,
            )


def test_training_prompt_v5_disambiguates_public_program_and_action_ir() -> None:
    config = TrainingUtilityMVPConfig(
        candidate_tasks_per_domain=2,
        evaluation_tasks_per_domain=1,
        cohort_size=6,
        max_steps=1,
    )
    records, _ = _reference_and_evaluation_records(config)
    record = records[0]
    user_payload = json.loads(record.user_prompt)
    action_payload = json.loads(record.messages[2].content)
    output_contract = user_payload["output_contract"]

    assert record.prompt_version == config.prompt_version
    assert record.metadata["prompt_version"] == config.prompt_version
    assert output_contract["prompt_version"] == config.prompt_version
    assert "result_contract" in output_contract["second_response_after_tool"]
    assert output_contract["first_response"]["forbidden_input_fields"] == [
        "kind",
        "role_id",
        "semantic_constraints",
        "source_id",
    ]
    assert "Do not copy kind, role_id, semantic_constraints, source_id" in record.system_prompt
    assert all(
        set(action_input) <= {"source", "evidence_id", "step_index", "selector"}
        for execution in action_payload["executions"]
        for action_input in execution["inputs"]
    )


def test_training_prompt_v5_remains_replayable() -> None:
    config = TrainingUtilityMVPConfig(
        candidate_tasks_per_domain=2,
        evaluation_tasks_per_domain=1,
        cohort_size=6,
        max_steps=1,
        prompt_version="training_utility_agent_prompt.v5",
    )
    records, _ = _reference_and_evaluation_records(config)
    record = records[0]
    output_contract = json.loads(record.user_prompt)["output_contract"]

    assert record.prompt_version == "training_utility_agent_prompt.v5"
    assert "result_contract" not in output_contract["second_response_after_tool"]
    assert "result must exactly match public_task.answer_schema" not in record.system_prompt


def test_training_prompt_version_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported training utility prompt"):
        TrainingUtilityMVPConfig(prompt_version="training_utility_agent_prompt.unknown")


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
    mutated["answer_decision"]["result"] = {"unsupported": "answer"}
    outcome = score_generated_response(
        evaluation[0],
        json.dumps(mutated),
    )
    assert outcome["valid_json"] is True
    assert outcome["response_contract"] is True
    assert outcome["answer_exact"] is False
    assert outcome["end_to_end"] is False


def test_training_utility_scorer_normalizes_numeric_answer_representation() -> None:
    _, evaluation = _reference_and_evaluation_records(
        TrainingUtilityMVPConfig(
            candidate_tasks_per_domain=3,
            evaluation_tasks_per_domain=3,
            cohort_size=6,
            max_steps=1,
        )
    )
    record = next(item for item in evaluation if "total_sample_size" in item.assistant_target)
    predicted = json.loads(record.assistant_target)
    result = predicted["answer_decision"]["result"]
    result["total_sample_size"] = int(result["total_sample_size"])

    outcome = score_generated_response(record, json.dumps(predicted))

    assert outcome["response_contract"] is True
    assert outcome["answer_exact"] is True
    assert outcome["end_to_end"] is True


def test_host_transcript_masks_tool_messages_from_sft_loss() -> None:
    records, _ = _reference_and_evaluation_records(
        TrainingUtilityMVPConfig(
            candidate_tasks_per_domain=2,
            evaluation_tasks_per_domain=1,
            cohort_size=6,
            max_steps=1,
        )
    )
    record = records[0]
    tokenizer = _CharacterChatTokenizer()

    encoded, audit = _encode_records(
        tokenizer,
        (record,),
        max_seq_length=100000,
    )

    full_text = tokenizer.apply_chat_template(
        [{"role": item.role, "content": item.content} for item in record.messages],
        tokenize=False,
        add_generation_prompt=False,
    )
    labels = encoded[0]["labels"]
    tool_fragment = f"<tool>{record.messages[3].content}</tool>"
    tool_start = full_text.index(tool_fragment)
    tool_end = tool_start + len(tool_fragment)
    action_start = full_text.index(record.messages[2].content)
    answer_start = full_text.index(record.messages[4].content)

    assert all(item == -100 for item in labels[tool_start:tool_end])
    assert any(item != -100 for item in labels[action_start : action_start + 10])
    assert any(item != -100 for item in labels[answer_start : answer_start + 10])
    assert audit["training_format_counts"] == {"host_instrumented_joint": 1}


def test_training_utility_rejects_unbalanced_fraction_contract() -> None:
    with pytest.raises(ValueError, match="divisible by three"):
        TrainingUtilityMVPConfig(
            candidate_tasks_per_domain=3,
            cohort_size=9,
            d1_construction_mode="legacy_counterfactual_mix",
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
    assert all("assistant_target_answer" in row for row in rows)
    assert all(row["assistant_target_answer_text"] for row in rows)
    assert {row["target_interpretation"] for row in rows} == {"gold_reference"}
    assert all(row["is_gold_reference"] for row in rows)
    assert all(row["is_quality_approved"] for row in rows)
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
    broken_messages = list(records[0].messages)
    broken_messages[1] = broken_messages[1].model_copy(update={"content": "{"})
    broken = records[0].model_copy(update={"user_prompt": "{", "messages": tuple(broken_messages)})
    (input_dir / "D2_reference_workflow.jsonl").write_text(
        broken.model_dump_json() + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid JSON in user_prompt"):
        export_training_utility_review(input_dir, tmp_path / "review")


def test_traditional_qa_export_contains_only_question_and_answer(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "data"
    config = TrainingUtilityMVPConfig(
        candidate_tasks_per_domain=2,
        evaluation_tasks_per_domain=1,
        cohort_size=6,
        max_steps=1,
    )
    write_reference_training_preflight(config, input_dir)
    (input_dir / "D2_reference_workflow.jsonl").rename(input_dir / "C3_verified_static.jsonl")
    output_file = tmp_path / "traditional_qa.jsonl"

    result = export_traditional_qa(
        input_dir,
        output_file,
        cohorts=("C3_verified_static",),
        limit=2,
    )

    rows = [json.loads(line) for line in output_file.read_text().splitlines() if line]
    assert result.record_count == 2
    assert result.cohort_counts == {"C3_verified_static": 2}
    assert all(set(row) == {"question", "answer"} for row in rows)
    assert all(isinstance(row["question"], str) and row["question"] for row in rows)
    assert all(row["answer"] is not None for row in rows)


def test_traditional_qa_markdown_has_no_experiment_metadata(tmp_path: Path) -> None:
    input_dir = tmp_path / "data"
    write_reference_training_preflight(
        TrainingUtilityMVPConfig(
            candidate_tasks_per_domain=2,
            evaluation_tasks_per_domain=1,
            cohort_size=6,
            max_steps=1,
        ),
        input_dir,
    )
    output_file = tmp_path / "traditional_qa.md"

    result = export_traditional_qa(
        input_dir,
        output_file,
        cohorts=("D2_reference_workflow",),
        limit=1,
    )

    rendered = output_file.read_text()
    assert result.output_format == "markdown"
    assert "**Question**" in rendered
    assert "**Answer**" in rendered
    assert "Evidence" not in rendered
    assert "record_id" not in rendered
    assert "cohort" not in rendered.lower()


def test_traditional_qa_default_discovery_ignores_its_own_output(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "data"
    write_reference_training_preflight(
        TrainingUtilityMVPConfig(
            candidate_tasks_per_domain=2,
            evaluation_tasks_per_domain=1,
            cohort_size=6,
            max_steps=1,
        ),
        input_dir,
    )
    output_file = input_dir / "traditional_qa.jsonl"

    first = export_traditional_qa(input_dir, output_file, limit=2)
    second = export_traditional_qa(input_dir, output_file, limit=2)

    assert first.record_count == second.record_count == 2
    assert first.dataset_hash == second.dataset_hash


def test_training_utility_review_labels_target_semantics() -> None:
    records, _ = _reference_and_evaluation_records(
        TrainingUtilityMVPConfig(
            candidate_tasks_per_domain=2,
            evaluation_tasks_per_domain=1,
            cohort_size=6,
            max_steps=1,
        )
    )
    base = records[0]
    variants = (
        (base, "gold_reference"),
        (
            base.model_copy(update={"source_kind": "real_agent", "contract_label": "accept"}),
            "quality_accepted_candidate",
        ),
        (
            base.model_copy(update={"source_kind": "real_agent", "contract_label": "reject"}),
            "quality_rejected_candidate",
        ),
        (
            base.model_copy(
                update={"source_kind": "typed_counterfactual", "contract_label": "reject"}
            ),
            "intentionally_faulty_counterfactual",
        ),
        (
            base.model_copy(
                update={
                    "source_kind": "real_agent",
                    "contract_label": "accept",
                    "counterfactual_repair": True,
                }
            ),
            "counterfactual_repair_target",
        ),
    )

    assert tuple(
        build_qa_review_record(record, source_dataset_file="test.jsonl").target_interpretation
        for record, _ in variants
    ) == tuple(expected for _, expected in variants)


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


def test_supervised_token_schedule_is_deterministic_and_step_aligned() -> None:
    config = TrainingUtilityMVPConfig(
        candidate_tasks_per_domain=2,
        evaluation_tasks_per_domain=1,
        cohort_size=6,
        max_steps=10,
    )
    records, _ = _reference_and_evaluation_records(config)
    records = records[:4]
    encoded = [
        {"input_ids": [1] * count, "attention_mask": [1] * count, "labels": [1] * count}
        for count in (2, 3, 4, 5)
    ]

    first, first_tokens = _schedule_supervised_token_budget(
        encoded,
        records,
        token_budget=18,
        examples_per_step=2,
        seed=7,
    )
    second, second_tokens = _schedule_supervised_token_budget(
        encoded,
        records,
        token_budget=18,
        examples_per_step=2,
        seed=7,
    )

    assert first == second
    assert first_tokens == second_tokens
    assert len(first) % 2 == 0
    assert first_tokens == sum(label != -100 for item in first for label in item["labels"])


def test_completed_token_budget_uses_microbatches_not_examples() -> None:
    config = TrainingUtilityMVPConfig(
        candidate_tasks_per_domain=2,
        evaluation_tasks_per_domain=1,
        cohort_size=6,
        max_steps=10,
        supervised_token_budget=1000,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
    )
    result = CohortTrainingResult(
        cohort="cohort",
        config_hash=config.config_hash,
        dataset_hash="dataset",
        base_model="model",
        adapter_dir="adapter",
        trainable_parameter_count=1,
        total_parameter_count=2,
        train_runtime_seconds=1,
        peak_gpu_memory_bytes=1,
        completed_steps=3,
        supervised_token_count=1000,
        supervised_token_budget=1000,
        token_budget_deviation_rate=0,
        micro_batch_count=12,
        dependency_versions={},
        status="completed",
        result_hash="result",
    )

    assert _completed_training_budget_matches(config, result)


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
