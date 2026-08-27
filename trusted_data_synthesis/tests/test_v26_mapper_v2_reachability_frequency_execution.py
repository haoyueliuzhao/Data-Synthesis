from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.core.trajectory.reachability_frequency_v2 import (
    FrequencyMeasurementGateV2,
    ReachabilityFrequencySummaryV2,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_reachability_frequency_execution as execution,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / execution.OUTPUT_DIR
SUPPORT_EXIT_JOB_ID = (
    "finance_v26_frequency_job:53e29a176c06a64c701928ec7d2e958de595de83261e9abe95a45d63def57857"
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v26_161_source_replay_and_unopened_denominator_are_exact() -> None:
    source = execution.ExecutionSourceReplayAudit.model_validate(
        _load(FORMAL_DIR / "execution_source_replay_audit.json")
    )
    binding = execution.PreexecutionBindingAudit.model_validate(
        _load(FORMAL_DIR / "preexecution_binding_audit.json")
    )

    assert source.current_stage_input_binding_count == 35
    assert source.current_stage_input_byte_match_count == 35
    assert source.preflight_output_count == source.preflight_output_byte_match_count == 33
    assert source.independent_rebuild_output_count == 33
    assert source.independent_rebuild_byte_match_count == 33
    assert source.v26_158_full_transitive_rebuild_claimed is False
    assert source.missing_historical_snapshot_preserved is True
    assert source.credential_lookup_attempted is False
    assert source.provider_calls == 0
    assert len(source.implementation_files) == 2
    for item in source.implementation_files:
        path = PACKAGE_ROOT / item.relative_path
        assert path.stat().st_size == item.byte_count
        assert _sha256(path) == item.sha256

    assert binding.exact_job_count == 360
    assert binding.unconditional_job_count == 144
    assert binding.conditioned_job_count == 216
    assert binding.distinct_task_count == 12
    assert binding.distinct_cell_count == 48
    assert binding.distinct_path_count == 36
    assert binding.unopened_raw_count == 0
    assert binding.unopened_provider_artifact_count == 0
    assert binding.unopened_checkpoint_row_count == 0
    assert binding.unopened_report_count == 0
    assert binding.formal_assignment_count == 0
    assert binding.credential_lookup_attempted is False
    assert binding.provider_calls == 0
    assert binding.passed is True


def test_v26_161_complete_raw_denominator_fails_the_noncompensatory_gate() -> None:
    report = execution.FrequencyExecutionReport.model_validate(_load(FORMAL_DIR / "report.json"))
    gate = FrequencyMeasurementGateV2.model_validate(
        _load(FORMAL_DIR / "frequency_measurement_gate.json")
    )
    lineage = execution.RawLineageAudit.model_validate(_load(FORMAL_DIR / "raw_lineage_audit.json"))
    results = tuple(
        execution.FrequencyMeasurementResult.model_validate(item)
        for item in _load(FORMAL_DIR / "frequency_measurement_results.json")
    )
    checkpoint_rows = tuple(
        line
        for line in (FORMAL_DIR / "frequency_measurement_results.checkpoint.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    )

    assert len(results) == len(checkpoint_rows) == 360
    assert len({item.job_id for item in results}) == 360
    assert gate.complete_raw_count == 360
    assert gate.model_endpoint_count == 359
    assert gate.validity_evaluable_count == 359
    assert gate.measurement_support_exit_count == 1
    assert gate.instrument_failure_count == 1
    assert gate.privacy_failure_count == 0
    assert gate.exact_model_thinking_usage_failure_count == 0
    assert gate.typed_budget_no_call_count == 0
    assert gate.unresolved_transport_failure_count == 0
    assert gate.passed is False
    assert gate.exact_frequency_estimands_null is True
    assert gate.row_deletion_or_denominator_repair_allowed is False

    assert report.complete_result_count == report.complete_raw_count == 360
    assert report.terminal_counts == {
        "completed_model_endpoint": 197,
        "measurement_support_exit": 1,
        "model_result_failure": 162,
    }
    assert report.validity_evaluable_count == 359
    assert report.base_valid_count == 139
    assert report.mechanism_qualified_count == 270
    assert report.qualified_valid_count == 139
    assert report.provider_call_count == 3_134
    assert report.transport_inclusive_invocation_count == 3_134
    assert report.provider_prompt_tokens == 16_455_506
    assert report.provider_completion_tokens == 14_314_802
    assert report.provider_reasoning_tokens == 13_830_042
    assert report.provider_total_tokens == 30_770_308
    assert report.estimated_cost_usd == "5.45044867360000047422"
    assert report.measurement_gate_passed is False
    assert report.exact_frequency_estimands_null is True
    assert report.next_permitted_stage == execution.NEXT_STAGE

    assert lineage.raw_execution_count == lineage.measurement_result_count == 360
    assert lineage.provider_call_count == 3_134
    assert lineage.provider_envelope_count == 3_134
    assert lineage.public_projection_count == 3_134
    assert lineage.complete_provider_pair_count == 3_134
    assert lineage.transport_invocation_count == 3_134
    assert len(lineage.raw_descriptors) == 360
    assert len(lineage.provider_artifact_descriptors) == 9_402
    assert lineage.exact_byte_replay_pass_count == 9_762
    assert lineage.private_reasoning_payload_count == 0
    assert lineage.invalid_payload_persistence_count == 0
    assert lineage.raw_http_body_persistence_count == 0
    assert lineage.raw_request_body_persistence_count == 0
    assert lineage.stage_two_provider_call_count == 0


def test_v26_161_failed_gate_blocks_mapping_and_keeps_all_frequencies_null() -> None:
    assignment = execution.FrequencyAssignmentCatalog.model_validate(
        _load(FORMAL_DIR / "frequency_assignment_catalog.json")
    )
    mapper = execution.MapperExecutionAudit.model_validate(
        _load(FORMAL_DIR / "mapper_execution_audit.json")
    )
    cells = execution.CellDenominatorCatalog.model_validate(
        _load(FORMAL_DIR / "cell_denominator_diagnostics.json")
    )
    summary = ReachabilityFrequencySummaryV2.model_validate(
        _load(FORMAL_DIR / "task_condition_frequency_summary.json")
    )
    transition = execution.PostrunTransitionContract.model_validate(
        _load(FORMAL_DIR / "postrun_transition_contract.json")
    )

    assert assignment.complete_measurement_gate_passed is False
    assert assignment.assignment_count == 0
    assert assignment.structural_state_count == 0
    assert assignment.empirical_route_signature_count == 0
    assert assignment.assignments == ()
    assert mapper.qualified_row_count == 139
    assert mapper.production_mapper_invocation_count == 0
    assert mapper.reference_mapper_invocation_count == 0
    assert mapper.production_reference_exact_state_match_count == 0
    assert mapper.formal_assignment_count == 0
    assert mapper.mapper_invocation_before_complete_gate_count == 0
    assert cells.cell_count == 48
    assert cells.total_rollout_count == 360
    assert cells.validity_evaluable_count == 359
    assert cells.qualified_rollout_count == 139
    assert cells.formal_assignment_count == 0
    assert sum(item.qualified_rollout_count == 0 for item in cells.diagnostics) == 8
    assert {item.distribution_status for item in cells.diagnostics} == {"measurement_gate_failed"}
    assert summary.report_count == summary.null_report_count == 48
    assert {item.null_reason for item in summary.reports} == {"measurement_gate_failed"}
    assert all(item.distribution is None for item in summary.reports)
    assert all(item.observed_state_count == 0 for item in summary.reports)
    assert transition.next_permitted_stage == execution.NEXT_STAGE
    assert transition.provider_calls_authorized is False
    assert transition.row_deletion_or_denominator_repair_authorized is False
    assert transition.protocol_or_threshold_change_authorized is False


def test_v26_161_support_exit_preserves_raw_instrument_integrity() -> None:
    results = tuple(
        execution.FrequencyMeasurementResult.model_validate(item)
        for item in _load(FORMAL_DIR / "frequency_measurement_results.json")
    )
    support_exits = tuple(
        item
        for item in results
        if not item.joint_measurement_projection.measurement_support_available
    )
    assert len(support_exits) == 1
    result = support_exits[0]
    projected = result.joint_measurement_projection
    assert result.job_id == SUPPORT_EXIT_JOB_ID
    assert projected.raw_terminal_disposition == "measurement_support_exit"
    assert projected.terminal_failure_type == "ordinary_detour_allowance_exhausted"
    assert projected.model_endpoint_observed is False
    assert projected.validity_evaluable is False
    assert projected.instrument_integrity is False
    assert set(projected.measurement_gate_failure_ids) == {
        "instrument_failure",
        "measurement_support_exit",
        "model_endpoint_unobserved",
    }

    raw_path = FORMAL_DIR / projected.raw_execution_artifact.relative_path
    raw = _load(raw_path)
    assert raw["job_id"] == SUPPORT_EXIT_JOB_ID
    assert raw["terminal_disposition"] == "measurement_support_exit"
    assert raw["terminal_failure_type"] == "ordinary_detour_allowance_exhausted"
    assert raw["measurement_support_available"] is False
    assert raw["model_endpoint_observed"] is False
    assert raw["instrument_integrity"] is True
    assert raw["privacy_compliant"] is True
    assert raw["ordinary_detour_count"] == 2
    assert raw["later_provider_calls_after_support_exit"] == 0
    assert raw["stage_one_provider_call_count"] == 3
    assert raw["stage_two_provider_call_count"] == 0
    assert raw["transport_inclusive_invocation_count"] == 3
    assert raw["cumulative_provider_tokens"] == 40_041
    assert raw["task_verifier_invocation_count"] == 0
    assert raw["state_mapping_row_count"] == 0

    report_payload = _load(FORMAL_DIR / "report.json")
    report_payload["formal_assignment_count"] = 1
    with pytest.raises(ValueError, match="execution report changed"):
        execution.FrequencyExecutionReport.model_validate(report_payload)
