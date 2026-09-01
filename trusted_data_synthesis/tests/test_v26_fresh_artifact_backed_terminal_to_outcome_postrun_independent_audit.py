from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_postrun_independent_audit as audit,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_postrun_independent_audit_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parent


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, dict[str, Any]]:
    output = tmp_path_factory.mktemp("v26-201") / "formal"
    report = audit.build(repository_root=REPOSITORY_ROOT, output_dir=output)
    return output, report


def test_exact_v200_execution_freeze(built: tuple[Path, dict[str, Any]]) -> None:
    output, report = built
    freeze = models.V200ExecutionFreeze.model_validate(
        _load(output / "v26_200_execution_freeze.json")
    )
    assert freeze.run_start_receipt_id == audit.V200_RUN_START_ID
    assert freeze.execution_summary_id == audit.V200_SUMMARY_ID
    assert freeze.execution_artifact_manifest_id == audit.V200_ARTIFACT_MANIFEST_ID
    assert freeze.execution_artifact_root == audit.V200_ARTIFACT_ROOT
    assert freeze.formal_file_count == 1154
    assert freeze.formal_total_byte_count == 4_304_518
    assert freeze.manifest_execution_ordinal == 1
    assert freeze.authorization_consumed is True
    assert report["provider_calls_during_audit"] == 0


def test_all_192_job_layers_reconstruct_from_actual_bytes(
    built: tuple[Path, dict[str, Any]],
) -> None:
    output, _ = built
    reconstructed = models.ByteReconstructionAudit.model_validate(
        _load(output / "byte_reconstruction_audit.json")
    )
    assert reconstructed.exact_job_count == 192
    assert reconstructed.manifest_sha256_match_count == 1153
    assert reconstructed.manifest_byte_match_count == 1153
    assert reconstructed.raw_count == reconstructed.result_count == 192
    assert reconstructed.trace_count == reconstructed.outcome_count == 192
    assert reconstructed.raw_actual_byte_match_count == 192
    assert reconstructed.result_actual_byte_match_count == 192
    assert reconstructed.raw_before_result_count == 192
    assert reconstructed.terminal_reconstruction_match_count == 192
    assert reconstructed.failure_locus_reconstruction_match_count == 192
    assert len({item.job_id for item in reconstructed.rows}) == 192


def test_response_interface_and_terminal_partition_are_independent(
    built: tuple[Path, dict[str, Any]],
) -> None:
    output, report = built
    response = models.ResponseInterfaceAudit.model_validate(
        _load(output / "response_interface_audit.json")
    )
    assert response.provider_call_count == response.http_200_count == 192
    assert response.exact_model_identity_count == 192
    assert response.thinking_present_count == 192
    assert response.thinking_token_telemetry_count == 192
    assert response.usage_complete_count == 192
    assert response.public_projection_count == 188
    assert response.exact_action_abi_count == 0
    assert response.reasoning_budget_exhausted_count == 4
    assert response.terminal_partition == {
        "first_response_abi_invalid": 188,
        "thinking_integrity_failure": 4,
    }
    assert response.total_usage_tokens == report["total_usage_tokens"] == 1_824_320


def test_decision_accepts_execution_integrity_not_capability(
    built: tuple[Path, dict[str, Any]],
) -> None:
    output, _ = built
    decision = models.PostrunIndependentAuditDecision.model_validate(
        _load(output / "independent_audit_decision.json")
    )
    transition = models.ProspectiveTransition.model_validate(
        _load(output / "prospective_transition.json")
    )
    assert decision.decision == "v26_200_exact_online_execution_accepted_as_complete"
    assert decision.exact_job_run_complete is True
    assert decision.execution_integrity_passed is True
    assert decision.model_crossed_action_interface is False
    assert decision.capability_estimate_materialized is False
    assert transition.next_decision == models.NEXT_DECISION
    assert transition.provider_execution_authorized is False
    assert transition.replacement_rerun_authorized is False
    assert transition.recovery_execution_authorized is False
    assert transition.empirical_estimation_authorized is False


def test_empty_directory_rebuild_is_byte_identical(
    built: tuple[Path, dict[str, Any]],
    tmp_path: Path,
) -> None:
    first, _ = built
    second = tmp_path / "rebuild"
    audit.build(repository_root=REPOSITORY_ROOT, output_dir=second)
    first_files = {
        path.relative_to(first).as_posix(): path.read_bytes()
        for path in first.rglob("*")
        if path.is_file()
    }
    second_files = {
        path.relative_to(second).as_posix(): path.read_bytes()
        for path in second.rglob("*")
        if path.is_file()
    }
    assert first_files == second_files


def test_audit_source_has_no_provider_or_estimator_execution() -> None:
    source = inspect.getsource(audit)
    assert "StageOneProspectiveThinkingJsonClient" not in source
    assert ".complete_json" not in source
    assert "evaluate_fresh_evidence_set(" not in source
    assert "provider_calls_during_audit" in source
