from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, cast

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_online_authorization as v199,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_online_authorization_models as v199_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_online_execution as execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_online_execution_models as models,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    require_stage_one_model_config,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parent
EXTERNAL_AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/90d48127-c499-4d68-87be-9b74fdad1573/pasted-text.txt"
)


class AbiInvalidClient:
    def __init__(self, config: AgentModelConfig) -> None:
        self.config = config

    def complete_json_certified(self, prompt: str, certificate: Any) -> Any:
        return {}, ModelCallTelemetry(
            provider="deepseek",
            endpoint_host="api.deepseek.com",
            model_requested="deepseek-v4-flash",
            model_selected="deepseek-v4-flash",
            response_model="deepseek-v4-flash",
            request_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            response_hash=hashlib.sha256(b"{}").hexdigest(),
            http_status=200,
            http_success=True,
            json_contract_success=True,
            finish_reason="stop",
            response_content_length=2,
            reasoning_content_present=True,
            reasoning_content_length=1,
            reasoning_tokens=1,
            prompt_tokens=10,
            completion_tokens=2,
            total_tokens=12,
        )


@pytest.fixture(scope="module")
def prepared(tmp_path_factory: pytest.TempPathFactory) -> execution.PreparedOnlineExecution:
    output = tmp_path_factory.mktemp("v26-200") / "one-shot"
    return execution.prepare_execution(
        repository_root=REPOSITORY_ROOT,
        output_dir=output,
        external_audit_path=EXTERNAL_AUDIT,
    )


def _admission(
    prepared: execution.PreparedOnlineExecution,
) -> v199_models.OnlineAuthorizationAdmission:
    guard = v199_models.PrecredentialOnlineAuthorizationGuard(
        expected_authorization=prepared.authorization,
        expected_authorization_bytes=v199_models.canonical_bytes(prepared.authorization),
    )
    return guard.admit(**v199._request_arguments(prepared.authorization))  # noqa: SLF001


def _run_start(
    prepared: execution.PreparedOnlineExecution,
    admission: v199_models.OnlineAuthorizationAdmission,
) -> models.RunStartReceipt:
    return cast(
        models.RunStartReceipt,
        models.make_identity(
            models.RunStartReceipt,
            {
                "external_decision_id": prepared.external_decision.decision_id,
                "authorization_id": prepared.authorization.authorization_id,
                "admission_id": admission.admission_id,
                "manifest_id": prepared.manifest.manifest_id,
                "exact_job_set_sha256": prepared.authorization.exact_job_set_sha256,
                "execution_source_commit": "0" * 40,
                "execution_source_tree": "1" * 40,
                "started_at_utc": "2026-09-01T00:00:00+00:00",
            },
            field="receipt_id",
            prefix="finance_v26_200_online_run_start_receipt:",
        ),
    )


def _config() -> AgentModelConfig:
    payload = json.loads((PACKAGE_ROOT / execution.MODEL_PROFILE_PATH).read_bytes())
    return require_stage_one_model_config(
        AgentModelConfig.model_validate(payload.get("model", payload))
    )


def test_exact_external_audit_v199_freeze_and_192_job_mapping(
    prepared: execution.PreparedOnlineExecution,
) -> None:
    assert prepared.external_decision.audit_sha256 == execution.EXTERNAL_AUDIT_SHA256
    assert prepared.v199_freeze.formal_file_match_count == 16
    assert prepared.v199_freeze.formal_total_byte_count == 102_783
    assert prepared.authorization.authorization_id == execution.V199_AUTHORIZATION_ID
    assert prepared.preparation.exact_job_count == 192
    assert prepared.preparation.mapped_runtime_job_count == 192
    assert tuple(sorted(prepared.job_parents)) == prepared.authorization.exact_job_ids
    assert prepared.preparation.provider_calls == 0
    assert prepared.preparation.credentials_read is False


def test_precredential_guard_admits_only_the_exact_provider_request(
    prepared: execution.PreparedOnlineExecution,
) -> None:
    admission = _admission(prepared)
    assert admission.authorization_id == prepared.authorization.authorization_id
    assert admission.provider_execution_requested is True
    changed = v199._request_arguments(prepared.authorization)  # noqa: SLF001
    changed["requested_job_ids"] = changed["requested_job_ids"][:-1]
    guard = v199_models.PrecredentialOnlineAuthorizationGuard(
        expected_authorization=prepared.authorization,
        expected_authorization_bytes=v199_models.canonical_bytes(prepared.authorization),
    )
    with pytest.raises(ValueError, match="requested online Job set differs"):
        guard.admit(**changed)


def test_invalid_external_audit_rejects_before_output_creation(tmp_path: Path) -> None:
    audit = tmp_path / "changed.txt"
    audit.write_bytes(EXTERNAL_AUDIT.read_bytes() + b"changed")
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="audit bytes differ"):
        execution.prepare_execution(
            repository_root=REPOSITORY_ROOT,
            output_dir=output,
            external_audit_path=audit,
        )
    assert not output.exists()


def test_one_actual_kernel_invoke_dispatches_and_writes_raw_before_result(
    prepared: execution.PreparedOnlineExecution,
) -> None:
    admission = _admission(prepared)
    run_start = _run_start(prepared, admission)
    job_id = prepared.authorization.exact_job_ids[0]
    record = execution.execute_job(
        prepared=prepared,
        parents=prepared.job_parents[job_id],
        run_start=run_start,
        admission=admission,
        config=_config(),
        client_factory=AbiInvalidClient,
    )
    assert record.terminal_kind == "first_response_abi_invalid"
    assert record.provider_call_count == 1
    assert record.cumulative_tokens == 12
    assert len(record.kernel_invocation_receipt_ids) == 1
    assert record.bundle.row.formal_empirical_row is True
    assert record.bundle.row.task_verifier_invoked is False
    assert record.bundle.raw.evidence_kind == "empirical_execution"
    assert record.bundle.result.evidence_kind == "empirical_execution"
    raw = prepared.output_dir / "fresh_outcome_artifacts" / record.bundle.raw.artifact_relative_path
    result = (
        prepared.output_dir
        / "fresh_outcome_artifacts"
        / record.bundle.result.artifact_relative_path
    )
    assert raw.is_file() and result.is_file()
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == record.bundle.raw.artifact_sha256
    assert hashlib.sha256(result.read_bytes()).hexdigest() == record.bundle.result.artifact_sha256
    assert b"fixture_complete" not in raw.read_bytes() + result.read_bytes()


def test_public_terminal_shapes_cover_final_and_correction_dispatch() -> None:
    first = execution._public_observation(  # noqa: SLF001
        terminal_kind="first_action_reference_invalid",
        component_index=0,
        component_key="component",
        source_outcome=None,
    )
    correction = execution._public_observation(  # noqa: SLF001
        terminal_kind="correction_attempt_typed_invalid",
        component_index=0,
        component_key="component",
        source_outcome=None,
    )
    final = execution._public_observation(  # noqa: SLF001
        terminal_kind="final_response_abi_invalid",
        component_index=0,
        component_key="component",
        source_outcome=None,
    )
    assert first.public_payload is not None
    assert first.public_payload.action_reference_valid is False
    assert correction.public_payload is not None
    assert correction.public_payload.correction_state_precondition_valid is False
    assert final.public_payload is not None
    assert final.public_payload.final_response_abi_valid is False


def test_execution_source_has_no_old_complete_job_or_estimator_call() -> None:
    source = inspect.getsource(execution)
    assert ".complete_job(" not in source
    assert "evaluate_fresh_evidence_set(" not in source
    assert "empirical_estimate_count" not in source
    assert models.NEXT_STAGE.endswith("postrun_independent_audit_only")
