from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_postrun_audit import (  # noqa: E501
    AuthorityPreservingPostrunAuditReport,
    authority_preserving_postrun_report_id,
    build_authority_preserving_postrun_audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
TASK_SOURCE = ARTIFACT_ROOT / "finance_v26_65_authority_preserving_operation_hardening_20260819"
INTERRUPTED_SOURCE = (
    ARTIFACT_ROOT / "finance_v26_66_authority_preserving_instrument_requalification_20260819"
)
RECOVERY_RUN_ID = (
    "finance_v26_66_authority_preserving_instrument_requalification_finalization_recovery_20260819"
)
RECOVERY_SOURCE = ARTIFACT_ROOT / RECOVERY_RUN_ID
AUDIT_SOURCE = ARTIFACT_ROOT / "finance_v26_67_authority_preserving_postrun_audit_20260819"
RUN_ID = "finance_v26_67_authority_preserving_postrun_audit_20260819"
EXPECTED_HASHES = {
    "finalization_recovery_audit.json": (
        "df44535e2262ee16a94616f62c48707a91c25f877ce71d0b07a14a673d5622f0"
    ),
    "rollout_authority_audits.json": (
        "a43bda267edb0d15450226bfc91052f7268468acc54e7c6b53ebb47476b361e4"
    ),
    "mechanism_authority_summaries.json": (
        "11706bf74c85337c785f9a097c87840d991e2a16799896407f7a4d3de451f486"
    ),
    "report.json": "47b51917aa95aa5c605c5851773c59e5c23200318facb5eeb35569e3497fc1de",
}


def _build(output_dir: Path):
    del output_dir
    return AuthorityPreservingPostrunAuditReport.model_validate_json(
        (AUDIT_SOURCE / "report.json").read_text(encoding="utf-8")
    )


def test_audit_retains_immutable_bytes_and_identity(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report.report_id == authority_preserving_postrun_report_id(report)
    assert len(report.source_files) == 53
    assert (
        report.implementation_source.sha256
        == hashlib.sha256(
            (PACKAGE_ROOT / report.implementation_source.relative_path).read_bytes()
        ).hexdigest()
    )
    for name, expected in EXPECTED_HASHES.items():
        assert hashlib.sha256((AUDIT_SOURCE / name).read_bytes()).hexdigest() == expected


def test_audit_rejects_rebuild_under_successor_source(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="implementation source changed"):
        build_authority_preserving_postrun_audit(
            run_id=RUN_ID,
            interrupted_dir=INTERRUPTED_SOURCE,
            recovery_dir=RECOVERY_SOURCE,
            task_source_dir=TASK_SOURCE,
            output_dir=tmp_path,
            package_root=PACKAGE_ROOT,
        )


def test_finalization_recovery_reuses_the_exact_checkpoint(tmp_path: Path) -> None:
    recovery = _build(tmp_path / "audit").finalization_recovery

    assert recovery.status == "passed"
    assert recovery.preflight_report_preserved
    assert recovery.checkpoint_rollout_count_before == 32
    assert recovery.checkpoint_rollout_count_after == 32
    assert recovery.missing_job_count_before_recovery == 0
    assert recovery.duplicate_job_count_before_recovery == 0
    assert not recovery.raw_model_jobs_repeated
    assert recovery.recovery_model_job_count == 0
    assert recovery.recovery_api_call_count == recovery.recovery_gpu_job_count == 0
    assert all(item.byte_identical for item in recovery.file_comparisons)


def test_instrument_and_authority_gates_are_retained(tmp_path: Path) -> None:
    report = _build(tmp_path / "audit")

    assert report.completed_rollout_count == report.model_outcome_count == 32
    assert report.runtime_failure_count == report.instrument_failure_count == 0
    assert report.exact_model_rollout_count == 32
    assert report.fallback_rollout_count == 0
    assert report.public_contract_prompt_count == 32
    assert report.public_progress_prompt_count == 32
    assert report.private_identity_free_count == 32
    assert report.authority_contract_prompt_count == 32
    assert report.terminal_target_prompt_count == 32
    assert report.repair_prompt_count == 81
    assert report.action_bearing_repair_prompt_count == 0
    assert report.failed_observation_count == 92
    assert report.action_bearing_failed_observation_count == 0


def test_terminal_target_and_validity_smoke_are_scoped(tmp_path: Path) -> None:
    report = _build(tmp_path / "audit")

    assert report.full_program_lineage_count == 5
    assert report.terminal_node_completion_count == 5
    assert report.postterminal_verification_count == 5
    assert report.exact_terminal_target_acceptance_count == 5
    assert report.independently_valid_count == 4
    assert report.valid_task_count == 3
    assert report.valid_mechanism_counts == {
        "context_conditioned_action": 1,
        "state_dependent_stopping": 3,
    }
    assert report.model_validity_smoke_observed
    assert not report.all_mechanisms_empirically_supported
    assert not report.capability_support_admitted
    assert not report.state_reachability_evaluable
    assert not report.state_support_established


def test_audit_authorizes_protocol_design_only(tmp_path: Path) -> None:
    report = _build(tmp_path / "audit")

    assert report.authority_preserving_instrument_established
    assert report.capability_protocol_design_ready
    assert report.state_reachability_protocol_design_ready
    assert report.status == "authority_preserving_operation_instrument_passed"
    assert (
        report.next_permitted_stage == "capability_development_and_state_reachability_protocol_only"
    )
    assert not report.capability_development_authorized
    assert not report.state_reachability_pilot_authorized
    assert not report.fresh_confirmation_authorized
    assert not report.no_c_vtdo_authorized
    assert not report.student_training_authorized
    assert not report.exact_target_authorized
    assert not report.gp_c_authorized
    assert report.production_contribution == 0
    assert report.api_call_count == report.gpu_job_count == 0


def test_detail_outputs_have_complete_denominators(tmp_path: Path) -> None:
    report = _build(tmp_path)
    rows = json.loads((AUDIT_SOURCE / "rollout_authority_audits.json").read_text())
    summaries = json.loads((AUDIT_SOURCE / "mechanism_authority_summaries.json").read_text())

    assert len(rows) == len(report.rollout_audits) == 32
    assert len(summaries) == len(report.mechanism_summaries) == 4
    assert all(item["rollout_count"] == 8 for item in summaries)
    assert sum(item["independently_valid_count"] for item in summaries) == 4
