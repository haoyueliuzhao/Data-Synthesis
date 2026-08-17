from __future__ import annotations

from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_failure_audit import (
    build_empirical_failure_audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
SOURCE_RECOVERY = ARTIFACT_ROOT / "finance_v26_58_transport_recovery_20260818"
V26_56_SOURCE = ARTIFACT_ROOT / "finance_v26_56_executable_task_rematerialization_20260818"


def test_failure_audit_localizes_public_program_contract_gap(tmp_path: Path) -> None:
    report = build_empirical_failure_audit(
        run_id="finance_v26_59_failure_audit_test",
        source_recovery_dir=SOURCE_RECOVERY,
        v26_56_source_dir=V26_56_SOURCE,
        output_dir=tmp_path,
        package_root=PACKAGE_ROOT,
    )

    assert report.rollout_count == 456
    assert report.raw_replay_pass_count == 456
    assert report.complete_trajectory_count == 416
    assert report.model_contract_failure_count == 40
    assert report.earliest_failure_stage_counts == {
        "evidence_selection": 86,
        "model_contract": 40,
        "operation_execution": 330,
    }
    assert report.completed_operation_lineage_failure_count == 416
    assert report.public_operation_execution_contract_task_count == 0
    assert report.missing_public_operation_execution_contract_task_count == 24
    assert report.compiler_witness_count == 0
    assert report.status == "public_operation_contract_gap_observed"
    assert report.next_permitted_stage == ("fresh_public_operation_contract_rematerialization_only")
    assert report.model_api_call_count == report.gpu_job_count == 0
    assert not report.fresh_confirmation_authorized
    assert not report.no_c_vtdo_authorized
    assert report.production_contribution == 0


def test_condition_channel_changes_invalid_behavior_without_authorizing_state(
    tmp_path: Path,
) -> None:
    report = build_empirical_failure_audit(
        run_id="finance_v26_59_condition_audit_test",
        source_recovery_dir=SOURCE_RECOVERY,
        v26_56_source_dir=V26_56_SOURCE,
        output_dir=tmp_path,
        package_root=PACKAGE_ROOT,
    )
    conditions = {item.requested_strategy: item for item in report.condition_behavior_summaries}

    assert conditions["search_then_structured"].matching_behavior_count == 71
    assert conditions["search_then_open"].matching_behavior_count == 36
    assert conditions["structured_direct"].matching_behavior_count == 38
    assert all(item.independently_valid_count == 0 for item in conditions.values())
    assert report.natural_precalculation_strategy_counts == {
        "search_then_open": 4,
        "search_then_structured": 128,
        "structured_direct": 12,
    }


def test_failure_audit_replays_byte_identically(tmp_path: Path) -> None:
    outputs = (tmp_path / "first", tmp_path / "second")
    reports = []
    for output in outputs:
        reports.append(
            build_empirical_failure_audit(
                run_id="finance_v26_59_determinism_test",
                source_recovery_dir=SOURCE_RECOVERY,
                v26_56_source_dir=V26_56_SOURCE,
                output_dir=output,
                package_root=PACKAGE_ROOT,
            )
        )
    assert reports[0] == reports[1]
    for name in ("rollout_failure_diagnostics.json", "report.json"):
        assert (outputs[0] / name).read_bytes() == (outputs[1] / name).read_bytes()
