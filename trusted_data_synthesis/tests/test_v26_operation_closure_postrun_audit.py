from __future__ import annotations

import hashlib
import json
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_operation_closure_postrun_audit import (  # noqa: E501
    build_operation_closure_postrun_audit,
    operation_closure_postrun_report_id,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
TASK_SOURCE = ARTIFACT_ROOT / "finance_v26_62_public_operation_instrument_hardening_20260818"
REGRESSION_SOURCE = ARTIFACT_ROOT / "finance_v26_63_operation_closure_requalification_20260818"
RUN_ID = "finance_v26_64_operation_closure_postrun_audit_20260818"


def _build(output_dir: Path):
    return build_operation_closure_postrun_audit(
        run_id=RUN_ID,
        regression_dir=REGRESSION_SOURCE,
        task_source_dir=TASK_SOURCE,
        output_dir=output_dir,
        package_root=PACKAGE_ROOT,
    )


def test_postrun_audit_replays_every_source_and_is_byte_deterministic(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first = _build(first_dir)
    second = _build(second_dir)

    assert first == second
    assert first.report_id == operation_closure_postrun_report_id(first)
    assert len(first.source_files) == 51
    assert (
        first.implementation_source.sha256
        == hashlib.sha256(
            (PACKAGE_ROOT / first.implementation_source.relative_path).read_bytes()
        ).hexdigest()
    )
    for name in (
        "rollout_postrun_diagnostics.json",
        "mechanism_postrun_summaries.json",
        "report.json",
    ):
        assert (first_dir / name).read_bytes() == (second_dir / name).read_bytes()


def test_postrun_audit_retains_the_passing_instrument_result(tmp_path: Path) -> None:
    report = _build(tmp_path / "audit")

    assert report.source_instrument_ready
    assert report.source_instrument_status == "passed"
    assert report.source_instrument_result_retained
    assert not report.source_outcomes_rescored
    assert report.completed_rollout_count == report.model_outcome_count == 32
    assert report.runtime_failure_count == report.instrument_failure_count == 0
    assert report.progress_action_binding_prompt_count == 0
    assert report.public_progress_action_neutral


def test_postrun_audit_localizes_the_verification_binding_gap(tmp_path: Path) -> None:
    report = _build(tmp_path / "audit")

    assert report.full_program_lineage_count == 24
    assert report.terminal_node_completion_count == 24
    assert report.frozen_postterminal_verification_count == 0
    assert report.independently_valid_count == 0
    assert report.postterminal_local_verification_rollout_count == 23
    assert report.postterminal_local_verification_count == 73
    assert report.exact_terminal_reference_verification_count == 0
    assert report.terminal_reference_plus_extra_verification_count == 7
    assert report.answer_payload_verification_count == 66
    assert report.other_postterminal_verification_count == 0
    assert not report.postterminal_verification_binding_ready


def test_postrun_audit_detects_action_bearing_repair_feedback(tmp_path: Path) -> None:
    report = _build(tmp_path / "audit")

    assert report.action_bearing_repair_prompt_count == 27
    assert report.action_bearing_repair_rollout_count == 21
    assert report.action_bearing_repair_observation_count == 27
    assert report.action_bearing_repair_observation_rollout_count == 22
    assert not report.repair_feedback_action_neutral
    assert all(item.progress_action_binding_prompt_count == 0 for item in report.diagnostics)
    assert any(item.action_bearing_repair_observation_count > 0 for item in report.diagnostics)


def test_postrun_audit_reports_trace_and_mechanism_diagnostics_without_state_claims(
    tmp_path: Path,
) -> None:
    report = _build(tmp_path / "audit")

    assert report.acquisition_path_counts == {"structured_direct": 32}
    assert report.unique_successful_trace_count == 15
    assert report.effective_successful_trace_count > 12
    assert report.maximum_successful_trace_share == 0.21875
    assert not report.natural_multiroute_support_evaluable
    assert tuple(item.mechanism_id for item in report.mechanism_summaries) == (
        "context_conditioned_action",
        "semantic_reconciliation",
        "failure_recovery",
        "state_dependent_stopping",
    )
    assert all(item.rollout_count == 8 for item in report.mechanism_summaries)
    assert sum(item.terminal_node_completion_count for item in report.mechanism_summaries) == 24
    assert (
        sum(item.postterminal_local_verification_count for item in report.mechanism_summaries) == 73
    )


def test_postrun_audit_keeps_all_downstream_authority_closed(tmp_path: Path) -> None:
    report = _build(tmp_path / "audit")

    assert not report.capability_protocol_ready
    assert not report.state_reachability_protocol_ready
    assert report.status == ("public_repair_and_postterminal_verification_contract_gaps_observed")
    assert report.next_permitted_stage == (
        "public_repair_and_postterminal_verification_contract_hardening_only"
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
    assert not report.historical_artifacts_mutated
    assert not report.task_selection_performed
    assert not report.model_comparison_performed
    assert not report.state_mapping_performed
    assert not report.causal_validity_comparison_performed


def test_postrun_detail_outputs_have_complete_denominators(tmp_path: Path) -> None:
    output_dir = tmp_path / "audit"
    report = _build(output_dir)
    diagnostics = json.loads((output_dir / "rollout_postrun_diagnostics.json").read_text())
    summaries = json.loads((output_dir / "mechanism_postrun_summaries.json").read_text())

    assert len(diagnostics) == len(report.diagnostics) == 32
    assert len(summaries) == len(report.mechanism_summaries) == 4
    assert {item["diagnostic_id"] for item in diagnostics} == {
        item.diagnostic_id for item in report.diagnostics
    }
