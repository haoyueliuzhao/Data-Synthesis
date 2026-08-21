from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_thinking_budget_calibration_execution import (  # noqa: E501
    EXPECTED_MANIFEST_ID,
    EXPECTED_PREFLIGHT_REPORT_ID,
    HOST_PLAN_STOP_CONDITIONS,
    HOST_PLAN_SUBGOALS,
    REPAIR_MARKER,
    _CompactCalibrationClient,
    _completion_classifications,
    _contains_private_reasoning_key,
    _execute_and_persist_raw,
    _make_report,
    _raw_lineage_audit,
    _runtime,
    _score_raw_execution,
    _thinking_history,
    prepare_thinking_budget_calibration_execution,
)
from trusted_synthesis.runtime.agent.budget_closed import BudgetClosedJsonClient
from trusted_synthesis.runtime.agent.client import LLMClientError
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_DIR = (
    PACKAGE_ROOT / "artifacts/vtdo_experiment/"
    "finance_v26_91_thinking_budget_calibration_preflight_v1_20260821"
)
RUN_ID = "finance_v26_92_thinking_budget_calibration_execution_test_v1"


class _FixtureClient:
    def __init__(
        self,
        config: AgentModelConfig,
        responses: list[dict[str, Any]],
    ) -> None:
        self.config = config
        self.responses = responses
        self.prompts: list[str] = []
        self.telemetry: list[ModelCallTelemetry] = []

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        if not self.responses:
            raise RuntimeError("fixture response stream exhausted")
        payload = self.responses.pop(0)
        content = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        prompt_tokens = min(len(prompt.encode("utf-8")), 1800)
        completion_tokens = 200
        telemetry = ModelCallTelemetry(
            provider="deepseek",
            endpoint_host="fixture.invalid",
            model_requested="deepseek-v4-flash",
            model_selected="deepseek-v4-flash",
            response_model="deepseek-v4-flash",
            request_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            response_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            http_status=200,
            http_success=True,
            json_contract_success=True,
            finish_reason="stop",
            response_content_length=len(content),
            reasoning_content_present=True,
            reasoning_content_length=120,
            reasoning_tokens=100,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost=0.0001,
            cost_estimation_method="generic_input_rate",
            response_shape={"provider_native_tool_call_observed": False},
        )
        self.prompts.append(prompt)
        self.telemetry.append(telemetry)
        return payload, telemetry


@pytest.fixture(scope="module")
def prepared(tmp_path_factory: pytest.TempPathFactory) -> Any:
    output = tmp_path_factory.mktemp("v26_92_prepare")
    return prepare_thinking_budget_calibration_execution(
        execution_run_id=RUN_ID,
        preflight_dir=PREFLIGHT_DIR,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )


def _job_inputs(prepared: Any) -> tuple[Any, Any, Any, Any, Any]:
    job = prepared.manifest.jobs[0]
    record = next(item for item in prepared.records if item.record_id == job.operational_record_id)
    environment = next(
        item for item in prepared.environments if item.manifest_id == job.environment_manifest_id
    )
    prompt = next(
        item
        for item in prepared.prompt_contracts
        if item.operational_task_package_id == job.operational_task_package_id
    )
    stress = next(
        item for item in prepared.stress_paths if item.audit_id == job.stress_path_audit_id
    )
    return job, record, environment, prompt, stress


def test_prepare_replays_every_frozen_input_before_credentials(prepared: Any) -> None:
    assert prepared.preflight.report_id == EXPECTED_PREFLIGHT_REPORT_ID
    assert prepared.manifest.manifest_id == EXPECTED_MANIFEST_ID
    assert len(prepared.manifest.jobs) == 32
    assert prepared.source_audit.v26_91_output_file_count == 31
    assert prepared.source_audit.predecessor_binding_file_count == 104
    assert prepared.source_audit.replay_pass_count == prepared.source_audit.replayed_file_count
    assert prepared.execution_binding.private_reasoning_content_persisted is False


def test_compact_contract_repair_reuses_registered_padding(prepared: Any) -> None:
    job, record, environment, prompt, stress = _job_inputs(prepared)
    fixture = _FixtureClient(
        prepared.agent_model_config,
        [
            {"plan_summary": "Use the public contract.", "extra": True},
            {"plan_summary": "Use the public contract."},
        ],
    )
    budget = BudgetClosedJsonClient(fixture, prepared.provider_budget_contract)
    adapter = _CompactCalibrationClient(
        budget,
        task=record.task_package.task.public,
        environment=environment,
        runtime=_runtime(record, environment),
        prompt_contract=prompt,
        stress_path=stress,
        path_strategy=job.path_strategy_id,
    )
    with pytest.raises(LLMClientError, match="compact calibration contract"):
        adapter.complete_json("legacy plan prompt")
    payload, telemetry = adapter.complete_json(
        "legacy plan prompt" + REPAIR_MARKER + "legacy repair fields"
    )
    assert payload["subgoal_labels"] == list(HOST_PLAN_SUBGOALS)
    assert payload["stop_conditions"] == list(HOST_PLAN_STOP_CONDITIONS)
    assert (
        telemetry.request_hash
        == hashlib.sha256(
            ("legacy plan prompt" + REPAIR_MARKER + "legacy repair fields").encode("utf-8")
        ).hexdigest()
    )
    assert len(adapter.attempts) == 2
    assert adapter.attempts[0].trailing_ascii_space_padding_bytes == (
        adapter.attempts[1].trailing_ascii_space_padding_bytes
    )
    assert adapter.attempts[1].contract_repair is True
    classifications = _completion_classifications(adapter.attempts, fixture.telemetry)
    assert len(classifications) == 1
    assert classifications[0].completion_outcome == "usable_after_contract_repair"
    assert classifications[0].completion_unusable is False


def test_thinking_continuity_fails_closed_on_missing_or_native_telemetry(
    prepared: Any,
) -> None:
    fixture = _FixtureClient(
        prepared.agent_model_config,
        [{"plan_summary": "Use the public contract."}],
    )
    _, telemetry = fixture.complete_json("public prompt")
    missing = telemetry.model_copy(
        update={
            "reasoning_content_present": False,
            "reasoning_content_length": 0,
            "reasoning_tokens": 0,
        }
    )
    audit, failures = _thinking_history(prepared.continuity_contract, (missing,))
    assert audit is None
    assert len(failures) == 1
    native = telemetry.model_copy(
        update={"response_shape": {"provider_native_tool_call_observed": True}}
    )
    audit, failures = _thinking_history(prepared.continuity_contract, (native,))
    assert audit is None
    assert len(failures) == 1
    assert _contains_private_reasoning_key({"reasoning": "public rationale"}) is False
    assert _contains_private_reasoning_key({"reasoning_content": "private"}) is True


def test_all_manifest_compiler_controls_exercise_online_stack(
    prepared: Any,
    tmp_path: Path,
) -> None:
    witnesses = json.loads(
        (PREFLIGHT_DIR / "calibration_compiler_witnesses.json").read_text(encoding="utf-8")
    )
    observation_rows = json.loads(
        (PREFLIGHT_DIR / "calibration_witness_observations.json").read_text(encoding="utf-8")
    )
    observations = {item["observation_id"]: item for item in observation_rows}
    trajectories = json.loads(
        (PREFLIGHT_DIR / "calibration_compiler_trajectories.json").read_text(encoding="utf-8")
    )
    witness_by_key = {
        (item["task_package_id"], item["path_strategy_id"]): item for item in witnesses
    }
    trajectory_by_witness = {item["program_execution"]["witness_id"]: item for item in trajectories}
    record_by_id = {item.record_id: item for item in prepared.records}
    environment_by_id = {item.manifest_id: item for item in prepared.environments}
    prompt_by_task = {item.operational_task_package_id: item for item in prepared.prompt_contracts}
    stress_by_id = {item.audit_id: item for item in prepared.stress_paths}
    results = []
    raw_by_job = {}
    for job in prepared.manifest.jobs:
        record = record_by_id[job.operational_record_id]
        environment = environment_by_id[job.environment_manifest_id]
        prompt = prompt_by_task[job.operational_task_package_id]
        stress = stress_by_id[job.stress_path_audit_id]
        witness = witness_by_key[(job.operational_task_package_id, job.path_strategy_id)]
        ordered_observations = [observations[item["observation_id"]] for item in witness["steps"]]
        trajectory = trajectory_by_witness[witness["witness_id"]]
        responses = [{"plan_summary": "Execute and verify the public contract."}]
        responses.extend(
            {
                "action": "call_tool",
                "rationale_summary": f"Use {item['call']['tool_id']}.",
                "tool_id": item["call"]["tool_id"],
                "arguments": item["call"]["arguments"],
            }
            for item in ordered_observations
        )
        responses.append(
            {
                "rationale_summary": "Return the verified terminal result.",
                "answer": trajectory["final_answer"]["result"],
            }
        )
        fixture = _FixtureClient(prepared.agent_model_config, responses)
        raw = _execute_and_persist_raw(
            job=job,
            prepared=prepared,
            record=record,
            environment=environment,
            prompt_contract=prompt,
            stress_path=stress,
            client=fixture,
            output_dir=tmp_path,
        )
        assert raw.solve_result is not None
        assert raw.failure_artifact is None
        assert raw.simulation_observation_match is True
        assert raw.thinking_history_audit is not None
        assert raw.thinking_continuity_failure_ids == ()
        assert raw.provider_budget_audit.status == "passed"
        assert all(not item.completion_unusable for item in raw.completion_classifications)
        assert len(fixture.prompts) == stress.request_count
        assert all(
            item.compiler_unpadded_prefix_match and item.compiler_padded_prefix_match
            for item in raw.compact_attempts
        )
        result = _score_raw_execution(
            raw=raw,
            prepared=prepared,
            record=record,
            environment=environment,
            output_dir=tmp_path,
        )
        assert result.terminal_category == "model_valid_trajectory"
        assert result.independent_validity is True
        assert result.requested_path_adhered is True, (
            job.job_id,
            job.path_strategy_id,
            result.actual_route,
        )
        assert result.capability_denominator_eligible is False
        assert result.reachability_denominator_eligible is False
        raw_by_job[job.job_id] = raw
        results.append(result)
    raw_lineage = _raw_lineage_audit(
        prepared=prepared,
        results=results,
        raw_by_job=raw_by_job,
        output_dir=tmp_path,
    )
    report = _make_report(
        prepared=prepared,
        results=tuple(results),
        raw_by_job=raw_by_job,
        raw_lineage=raw_lineage,
        discovered_models=("deepseek-v4-flash",),
    )
    assert report.status == "passed"
    assert report.typed_no_call_job_count == 0
    assert report.completion_unusable_job_count == 0
    assert report.provider_call_count == report.http_success_call_count
    assert report.reasoning_present_http_success_call_count == report.http_success_call_count
    assert report.reasoning_content_length_total > 0
    assert report.reasoning_tokens_total > 0
    assert report.completion_tokens_total >= report.reasoning_tokens_total
    assert report.logical_request_count == sum(report.completion_outcome_counts.values())
    assert report.contract_repair_request_rate == 0.0
    assert report.failed_observation_count == 8
    assert report.next_permitted_stage == "thinking_role_protocol_freeze_only"
    assert report.role_protocol_frozen is False

    one_completion_failure = list(results)
    one_completion_failure[0] = one_completion_failure[0].model_copy(
        update={"completion_unusable": True}
    )
    completion_report = _make_report(
        prepared=prepared,
        results=tuple(one_completion_failure),
        raw_by_job=raw_by_job,
        raw_lineage=raw_lineage,
        discovered_models=("deepseek-v4-flash",),
    )
    assert completion_report.status == "blocked"
    assert completion_report.completion_unusable_job_count == 1
    assert completion_report.completion_unusable_cp95_upper_32 == pytest.approx(0.13984946027422601)
    assert completion_report.next_permitted_stage == "thinking_completion_root_cause_audit_only"

    one_no_call = list(results)
    one_no_call[0] = one_no_call[0].model_copy(update={"typed_no_call": True})
    no_call_report = _make_report(
        prepared=prepared,
        results=tuple(one_no_call),
        raw_by_job=raw_by_job,
        raw_lineage=raw_lineage,
        discovered_models=("deepseek-v4-flash",),
    )
    assert no_call_report.status == "blocked"
    assert no_call_report.typed_no_call_job_count == 1
    assert no_call_report.typed_no_call_cp95_upper_32 == pytest.approx(0.13984946027422601)
    assert no_call_report.next_permitted_stage == "thinking_budget_deviation_root_cause_audit_only"
