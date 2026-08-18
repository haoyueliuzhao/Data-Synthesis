from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_role_postrun_audit import (  # noqa: E501
    AuthorityPreservingRolePostrunAuditReport,
    ConditionAdherenceSummary,
    CrossRoleIsolationAudit,
    RoleReplaySummary,
    RoleRolloutReplayAudit,
    _load_task_inputs,
    _validate_report_aggregates,
    build_authority_preserving_role_postrun_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_authority_preserving_role_runner import (  # noqa: E501
    AuthorityPreservingPreflightAudit,
    AuthorityPreservingRawIntegrityAudit,
    AuthorityPreservingRoleContract,
    AuthorityPreservingRoleJobManifest,
    AuthorityPreservingRoleReport,
    AuthorityPreservingRolloutDiagnostic,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (  # noqa: E501
    EmpiricalPilotRollout,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
CAPABILITY_RUN = ARTIFACT_ROOT / "finance_v26_71_capability_development_20260819"
CAPABILITY_PREFLIGHT = ARTIFACT_ROOT / "finance_v26_70_capability_development_preflight_20260819"
CAPABILITY_TASKS = ARTIFACT_ROOT / "finance_v26_69_fresh_capability_population_20260819"
REACHABILITY_RUN = ARTIFACT_ROOT / "finance_v26_72_state_reachability_20260819"
REACHABILITY_PREFLIGHT = ARTIFACT_ROOT / "finance_v26_70_state_reachability_preflight_20260819"
REACHABILITY_TASKS = (
    ARTIFACT_ROOT / "finance_v26_65_authority_preserving_operation_hardening_20260819"
)
V26_73 = ARTIFACT_ROOT / "finance_v26_73_authority_role_postrun_audit_v3_20260819"
RUN_ID = "finance_v26_73_authority_role_postrun_audit_v3_20260819"
DETAIL_FILES = (
    "condition_adherence_summaries.json",
    "cross_role_isolation_audit.json",
    "role_replay_summaries.json",
    "rollout_replay_audits.json",
    "report.json",
)


def _build(
    output: Path,
    *,
    capability_preflight: Path = CAPABILITY_PREFLIGHT,
) -> AuthorityPreservingRolePostrunAuditReport:
    return build_authority_preserving_role_postrun_audit(
        run_id=RUN_ID,
        capability_run_dir=CAPABILITY_RUN,
        capability_preflight_dir=capability_preflight,
        capability_task_source_dir=CAPABILITY_TASKS,
        reachability_run_dir=REACHABILITY_RUN,
        reachability_preflight_dir=REACHABILITY_PREFLIGHT,
        reachability_task_source_dir=REACHABILITY_TASKS,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )


@pytest.fixture(scope="module")
def rebuilt_audit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("v26_73_rebuild")
    _build(output)
    return output


def test_postrun_audit_is_deterministic(
    rebuilt_audit: Path,
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate"
    _build(duplicate)
    for relative in DETAIL_FILES:
        assert (rebuilt_audit / relative).read_bytes() == (duplicate / relative).read_bytes()


def test_formal_postrun_audit_is_byte_identical(rebuilt_audit: Path) -> None:
    for relative in DETAIL_FILES:
        assert (rebuilt_audit / relative).read_bytes() == (V26_73 / relative).read_bytes()


def test_postrun_audit_replays_complete_separate_denominators(rebuilt_audit: Path) -> None:
    report = AuthorityPreservingRolePostrunAuditReport.model_validate_json(
        (rebuilt_audit / "report.json").read_text(encoding="utf-8")
    )
    summaries = tuple(
        RoleReplaySummary.model_validate(item)
        for item in json.loads(
            (rebuilt_audit / "role_replay_summaries.json").read_text(encoding="utf-8")
        )
    )
    replays = tuple(
        RoleRolloutReplayAudit.model_validate(item)
        for item in json.loads(
            (rebuilt_audit / "rollout_replay_audits.json").read_text(encoding="utf-8")
        )
    )

    assert [item.observed_rollout_count for item in summaries] == [96, 360]
    assert len(replays) == 456
    assert all(item.raw_byte_replay_passed for item in replays)
    assert report.capability_independently_valid_count == 4
    assert report.capability_mechanisms_with_valid_trajectory_count == 1
    assert report.reachability_independently_valid_count == 21
    assert report.reachability_mapped_valid_count == 21
    assert report.admitted_state_count == report.admitted_task_count == 0
    assert report.state_support_freeze_status == "blocked"
    assert report.next_permitted_stage == (
        "capability_task_or_reachability_condition_redesign_only"
    )
    assert report.production_contribution == report.api_call_count == report.gpu_job_count == 0


def test_condition_diagnostics_and_cross_role_isolation(rebuilt_audit: Path) -> None:
    adherence = tuple(
        ConditionAdherenceSummary.model_validate(item)
        for item in json.loads(
            (rebuilt_audit / "condition_adherence_summaries.json").read_text(encoding="utf-8")
        )
    )
    isolation = CrossRoleIsolationAudit.model_validate_json(
        (rebuilt_audit / "cross_role_isolation_audit.json").read_text(encoding="utf-8")
    )

    assert [item.adherence_count for item in adherence] == [52, 6, 7]
    assert [item.on_target_valid_count for item in adherence] == [2, 0, 0]
    assert all(item.diagnostic_only and not item.creates_state_support for item in adherence)
    assert all(value == 0 for value in isolation.channel_overlap_counts.values())
    assert isolation.provider_call_identity_overlap_count == 0
    assert isolation.trajectory_identity_overlap_count == 0
    assert not isolation.role_denominators_combined


def test_independent_aggregation_rejects_a_report_count_mutation() -> None:
    contract = AuthorityPreservingRoleContract.model_validate_json(
        (CAPABILITY_RUN / "execution_contract.json").read_text(encoding="utf-8")
    )
    manifest = AuthorityPreservingRoleJobManifest.model_validate_json(
        (CAPABILITY_RUN / "job_manifest.json").read_text(encoding="utf-8")
    )
    preflight = AuthorityPreservingPreflightAudit.model_validate_json(
        (CAPABILITY_RUN / "static_preflight_audit.json").read_text(encoding="utf-8")
    )
    report = AuthorityPreservingRoleReport.model_validate_json(
        (CAPABILITY_RUN / "report.json").read_text(encoding="utf-8")
    )
    raw_audit = AuthorityPreservingRawIntegrityAudit.model_validate_json(
        (CAPABILITY_RUN / "raw_integrity_audit.json").read_text(encoding="utf-8")
    )
    rollouts = tuple(
        EmpiricalPilotRollout.model_validate(item)
        for item in json.loads(
            (CAPABILITY_RUN / "empirical_rollouts.json").read_text(encoding="utf-8")
        )
    )
    diagnostics = tuple(
        AuthorityPreservingRolloutDiagnostic.model_validate(item)
        for item in json.loads(
            (CAPABILITY_RUN / "rollout_diagnostics.json").read_text(encoding="utf-8")
        )
    )
    records, catalogs = _load_task_inputs("capability_development", CAPABILITY_TASKS)
    mutated = report.model_copy(update={"provider_call_count": report.provider_call_count + 1})

    with pytest.raises(ValueError, match="report aggregate mismatch: provider_call_count"):
        _validate_report_aggregates(
            contract=contract,
            manifest=manifest,
            preflight=preflight,
            report=mutated,
            raw_audit=raw_audit,
            diagnostics=diagnostics,
            rollouts=rollouts,
            records=records,
            catalogs=catalogs,
        )


def test_preflight_byte_tamper_fails_closed(tmp_path: Path) -> None:
    preflight = tmp_path / "tampered_preflight"
    shutil.copytree(CAPABILITY_PREFLIGHT, preflight)
    contract = preflight / "execution_contract.json"
    contract.write_text(contract.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="execution differs from frozen preflight"):
        _build(tmp_path / "output", capability_preflight=preflight)
