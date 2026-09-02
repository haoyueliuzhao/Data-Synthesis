# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_calibration_preflight_models as v203_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_paired_online_calibration as experiment,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_paired_online_calibration_models as models,
)
from trusted_synthesis.runtime.agent.client import LLMClientError
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parent
V203_ROOT = PACKAGE_ROOT / experiment.V203_DIR
FORMAL_ROOT = PACKAGE_ROOT / experiment.OUTPUT_DIR
AUDIT_PATH = FORMAL_ROOT / "external_audit.txt"


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


@pytest.fixture(scope="module")
def prepared(tmp_path_factory: pytest.TempPathFactory) -> experiment.PreparedOnlineCalibration:
    return experiment.prepare_execution(
        repository_root=REPOSITORY_ROOT,
        output_dir=tmp_path_factory.mktemp("v26-204") / "online",
        external_audit_path=AUDIT_PATH,
    )


def _telemetry(
    request: v203_models.FirstRequestDescriptor, *, failure: bool = False
) -> ModelCallTelemetry:
    return ModelCallTelemetry(
        provider="deepseek",
        endpoint_host="api.deepseek.com",
        model_requested="deepseek-v4-flash",
        model_selected="deepseek-v4-flash",
        response_model="deepseek-v4-flash",
        request_hash=request.canonical_request_body_sha256,
        response_hash=(None if failure else "1" * 64),
        http_status=200,
        http_success=True,
        json_contract_success=not failure,
        finish_reason="length" if failure else "stop",
        response_content_length=0 if failure else 128,
        reasoning_content_present=True,
        reasoning_content_length=100,
        reasoning_tokens=50,
        prompt_tokens=100,
        prompt_cache_hit_tokens=0,
        prompt_cache_miss_tokens=100,
        completion_tokens=75,
        total_tokens=175,
        estimated_cost=0.001,
        cost_estimation_method="provider_cache_breakdown",
        latency_ms=1,
        error_type="ReasoningBudgetExhaustedError" if failure else None,
        error_message="fixture" if failure else None,
    )


class PassingClient:
    calls: list[str] = []

    def __init__(self, _: AgentModelConfig) -> None:
        type(self).calls = []

    def complete_messages(
        self,
        request: v203_models.FirstRequestDescriptor,
    ) -> tuple[dict[str, Any], ModelCallTelemetry]:
        type(self).calls.append(request.job_id)
        if request.arm == "C":
            payload = {"value": "0"}
        else:
            contract = json.loads(request.messages[0].content)["authoritative_response_contract"]
            values = contract["field_values"]
            payload = {
                "state_id": values["state_id"],
                "action_id": values["action_id"]["one_of"][0],
                "decision_kind": values["decision_kind"],
                "protocol": values["protocol"],
            }
        return payload, _telemetry(request)


class TwoOuterTerminalClient(PassingClient):
    ordinal = 0

    def __init__(self, config: AgentModelConfig) -> None:
        super().__init__(config)
        type(self).ordinal = 0

    def complete_messages(
        self,
        request: v203_models.FirstRequestDescriptor,
    ) -> tuple[dict[str, Any], ModelCallTelemetry]:
        current = type(self).ordinal
        type(self).ordinal += 1
        if current in {0, 7}:
            telemetry = _telemetry(request, failure=True)
            type(self).calls.append(request.job_id)
            raise LLMClientError("fixture reasoning exhaustion", (telemetry,))
        return super().complete_messages(request)


def test_external_authorization_freeze_and_exact_sequential_order(
    prepared: experiment.PreparedOnlineCalibration,
) -> None:
    assert prepared.authorization.audit_sha256 == experiment.EXTERNAL_AUDIT_SHA256
    assert prepared.authorization.audit_byte_count == experiment.EXTERNAL_AUDIT_BYTES
    assert prepared.authorization.exact_provider_call_limit == 24
    assert prepared.authorization.stage_two_call_limit == 0
    assert prepared.authorization.retry_limit == prepared.authorization.recovery_call_limit == 0
    assert prepared.freeze.artifact_manifest_id == experiment.EXPECTED_V203_ARTIFACT_MANIFEST_ID
    assert prepared.freeze.artifact_root == experiment.EXPECTED_V203_ARTIFACT_ROOT
    order = prepared.preparation.execution_order
    assert tuple(item.ordinal for item in order) == tuple(range(24))
    assert sum(item.arm == "C" for item in order[::2]) == 6
    assert sum(item.arm == "R" for item in order[::2]) == 6
    assert all(
        order[index].source_cell_id == order[index + 1].source_cell_id for index in range(0, 24, 2)
    )


def test_precredential_guard_consumes_once_and_rejects_changed_request(
    prepared: experiment.PreparedOnlineCalibration,
) -> None:
    guard = experiment.PrecredentialAuthorizationGuard(prepared.authorization)
    raw = models.canonical_bytes(prepared.authorization)
    admission = guard.admit(
        candidate=prepared.authorization,
        candidate_bytes=raw,
        preparation_id=prepared.preparation.preparation_id,
        requested_stage=models.CONSUMED_STAGE,
        requested_provider_calls=24,
    )
    assert admission.authorization_consumed is True
    assert admission.admitted_before_credential_lookup is True
    with pytest.raises(experiment.V204Error, match="already consumed"):
        guard.admit(
            candidate=prepared.authorization,
            candidate_bytes=raw,
            preparation_id=prepared.preparation.preparation_id,
            requested_stage=models.CONSUMED_STAGE,
            requested_provider_calls=24,
        )
    fresh = experiment.PrecredentialAuthorizationGuard(prepared.authorization)
    with pytest.raises(experiment.V204Error, match="request differs"):
        fresh.admit(
            candidate=prepared.authorization,
            candidate_bytes=raw,
            preparation_id=prepared.preparation.preparation_id,
            requested_stage=models.CONSUMED_STAGE,
            requested_provider_calls=23,
        )


def test_exact_24_call_fixture_closes_all_evidence_and_online_gates(
    tmp_path: Path,
) -> None:
    prepared = experiment.prepare_execution(
        repository_root=REPOSITORY_ROOT,
        output_dir=tmp_path / "passing",
        external_audit_path=AUDIT_PATH,
    )
    summary = experiment.execute(
        prepared=prepared,
        client_factory=PassingClient,
        credential_loader=lambda _root, _key: None,
        source_identity=("1" * 40, "2" * 40),
    )
    assert summary.execution_status == "completed"
    assert summary.provider_calls == summary.raw_count == summary.result_count == 24
    assert summary.observation_count == 24
    assert summary.stage_two_calls == summary.retry_count == summary.recovery_call_count == 0
    assert PassingClient.calls == [item.job_id for item in prepared.preparation.execution_order]
    paired = v203_models.ExactPairedCalibrationEvaluation.model_validate(
        _load(prepared.output_dir / "exact_paired_calibration_evaluation.json")
    )
    gates = models.OnlineGateEvaluation.model_validate(
        _load(prepared.output_dir / "online_gate_evaluation.json")
    )
    assert paired.repair_abi_success_count == 12
    assert paired.repair_reference_state_valid_count == 12
    assert paired.paired_repair_only_abi_success_count == 12
    assert paired.paired_control_only_abi_success_count == 0
    assert paired.capability_estimate is None
    assert gates.all_gates_passed is True
    assert len(tuple((prepared.output_dir / "raw").glob("*.json"))) == 24
    assert len(tuple((prepared.output_dir / "results").glob("*.json"))) == 24
    assert len(tuple((prepared.output_dir / "observations").glob("*.json"))) == 24
    assert len(tuple((prepared.output_dir / "checkpoints").glob("*.json"))) == 24


def test_outer_terminals_remain_in_fixed_denominator(tmp_path: Path) -> None:
    prepared = experiment.prepare_execution(
        repository_root=REPOSITORY_ROOT,
        output_dir=tmp_path / "outer",
        external_audit_path=AUDIT_PATH,
    )
    summary = experiment.execute(
        prepared=prepared,
        client_factory=TwoOuterTerminalClient,
        credential_loader=lambda _root, _key: None,
        source_identity=("3" * 40, "4" * 40),
    )
    assert summary.execution_status == "completed"
    assert summary.provider_calls == summary.raw_count == summary.result_count == 24
    assert summary.observation_count == 24
    assert summary.typed_outer_terminal_partition["thinking_integrity_failure"] == 2
    raw = models.PublicProviderCallRaw.model_validate(
        _load(prepared.output_dir / "raw/job_000.json")
    )
    observation = models.ObservationRecord.model_validate(
        _load(prepared.output_dir / "observations/job_000.json")
    )
    assert raw.private_reasoning_content_persisted is False
    assert raw.typed_outer_terminal == "thinking_integrity_failure"
    assert observation.observation.exact_four_field_abi_valid is False
    assert observation.observation.action_reference_valid is None
    assert observation.observation.state_binding_valid is None


def test_manifest_requests_and_public_evidence_are_exact(
    prepared: experiment.PreparedOnlineCalibration,
) -> None:
    for request in prepared.manifest.requests:
        body = experiment._request_body(prepared.config, request.messages)
        assert models.canonical_sha256(body) == request.canonical_request_body_sha256
        roles = tuple(item.role for item in request.messages)
        assert roles == (("user",) if request.arm == "C" else ("system", "user"))
    assert all(job.planned_stage_one_calls == 1 for job in prepared.manifest.jobs)
    assert all(job.planned_stage_two_calls == 0 for job in prepared.manifest.jobs)
    assert all(job.automatic_retries == job.recovery_calls == 0 for job in prepared.manifest.jobs)


def test_immutable_output_prevents_authorization_reuse(tmp_path: Path) -> None:
    target = tmp_path / "existing"
    target.mkdir()
    prepared = experiment.prepare_execution(
        repository_root=REPOSITORY_ROOT,
        output_dir=target,
        external_audit_path=AUDIT_PATH,
    )
    called = False

    def credential_loader(_root: Path, _key: str) -> None:
        nonlocal called
        called = True

    with pytest.raises(experiment.V204Error, match="already exists"):
        experiment.execute(
            prepared=prepared,
            client_factory=PassingClient,
            credential_loader=credential_loader,
            source_identity=("5" * 40, "6" * 40),
        )
    assert called is False


def test_authoritative_execution_artifact_bytes_and_parent_chain_close() -> None:
    artifact = models.ExecutionArtifactManifest.model_validate(
        _load(FORMAL_ROOT / "execution_artifact_manifest.json")
    )
    assert artifact.file_count == 107
    assert artifact.total_byte_count == 261_434
    assert artifact.artifact_root == (
        "finance_v26_204_execution_artifact_root:"
        "10d7d5d17b518d2758c3e746a39a29f0a381cb5d3a267fb79e67e860093e8a3f"
    )
    for member in artifact.members:
        path = FORMAL_ROOT / member.relative_path
        assert path.is_file()
        assert path.stat().st_size == member.byte_count
        assert hashlib.sha256(path.read_bytes()).hexdigest() == member.sha256
    assert len(tuple(path for path in FORMAL_ROOT.rglob("*") if path.is_file())) == 108
    for ordinal in range(24):
        raw = models.PublicProviderCallRaw.model_validate(
            _load(FORMAL_ROOT / "raw" / f"job_{ordinal:03d}.json")
        )
        result = models.CalibrationJobResult.model_validate(
            _load(FORMAL_ROOT / "results" / f"job_{ordinal:03d}.json")
        )
        observation = models.ObservationRecord.model_validate(
            _load(FORMAL_ROOT / "observations" / f"job_{ordinal:03d}.json")
        )
        checkpoint = models.ExecutionCheckpoint.model_validate(
            _load(FORMAL_ROOT / "checkpoints" / f"job_{ordinal:03d}.json")
        )
        assert raw.ordinal == result.ordinal == observation.ordinal == checkpoint.ordinal == ordinal
        assert raw.job_id == result.job_id == observation.job_id == checkpoint.job_id
        assert result.raw_id == observation.raw_id == checkpoint.raw_id == raw.raw_id
        assert observation.result_id == checkpoint.result_id == result.result_id
        assert checkpoint.observation_record_id == observation.record_id
        assert result.response.response_id == observation.observation.response_id
        assert raw.provider_call_count == 1
        assert raw.telemetry.http_success is True
        assert raw.telemetry.model_requested == "deepseek-v4-flash"
        assert raw.telemetry.model_selected == "deepseek-v4-flash"
        assert raw.telemetry.response_model == "deepseek-v4-flash"
        assert raw.telemetry.reasoning_content_present is True
        assert raw.telemetry.total_tokens is not None
        assert raw.telemetry.reasoning_tokens is not None
        assert raw.private_reasoning_content_persisted is False


def test_authoritative_online_result_and_gate_counts_are_exact() -> None:
    paired = v203_models.ExactPairedCalibrationEvaluation.model_validate(
        _load(FORMAL_ROOT / "exact_paired_calibration_evaluation.json")
    )
    gates = models.OnlineGateEvaluation.model_validate(
        _load(FORMAL_ROOT / "online_gate_evaluation.json")
    )
    summary = models.OnlineExecutionSummary.model_validate(
        _load(FORMAL_ROOT / "execution_summary.json")
    )
    run_start = models.RunStartReceipt.model_validate(_load(FORMAL_ROOT / "run_start_receipt.json"))
    assert run_start.execution_source_commit == "01924d88f9e57502cd981c9d3be16b298b2ad45c"
    assert run_start.execution_source_tree == "70db179b44eb8834c5fc09d77a7ca89b56ce3d44"
    assert paired.repair_abi_success_count == 11
    assert paired.repair_reference_state_valid_count == 11
    assert paired.paired_repair_only_abi_success_count == 11
    assert paired.paired_control_only_abi_success_count == 0
    assert paired.delta_abi_numerator == 11
    assert paired.capability_estimate is None
    assert gates.all_gates_passed is True
    assert gates.exact_mcnemar_supplementary_two_sided_p == "0.0009765625"
    assert summary.execution_status == "completed"
    assert summary.provider_calls == summary.raw_count == summary.result_count == 24
    assert summary.observation_count == 24
    assert summary.total_usage_tokens == 224_104
    assert summary.stage_two_calls == summary.retry_count == summary.recovery_call_count == 0
    assert summary.full_192_job_execution_authorized is False
