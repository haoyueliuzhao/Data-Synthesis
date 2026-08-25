from __future__ import annotations

import json
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_capability_execution as execution,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / execution.OUTPUT_DIR


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _results() -> tuple[execution.CapabilityMeasurementResult, ...]:
    return tuple(
        execution.CapabilityMeasurementResult.model_validate_json(line)
        for line in (FORMAL_DIR / "fresh_capability_results.checkpoint.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    )


def test_v26_151_formal_recovery_gate_and_estimands_are_closed() -> None:
    source = execution.ExecutionSourceReplayAudit.model_validate(
        _load(FORMAL_DIR / "execution_source_replay_audit.json")
    )
    recovery = execution.AggregationRecoveryAudit.model_validate(
        _load(FORMAL_DIR / "aggregation_recovery_audit.json")
    )
    lineage = execution.RawLineageAudit.model_validate(_load(FORMAL_DIR / "raw_lineage_audit.json"))
    gate = execution.MeasurementGateAudit.model_validate(
        _load(FORMAL_DIR / "measurement_gate_audit.json")
    )
    report = execution.CapabilityExecutionReport.model_validate(_load(FORMAL_DIR / "report.json"))

    assert source.replayed_file_count == source.replay_pass_count == 7_364
    assert source.credential_lookup_attempted is False
    assert source.model_client_constructed is False
    assert source.provider_calls == source.stage_two_provider_calls == 0
    assert recovery.compared_file_count == recovery.byte_identical_file_count == 2_734
    assert recovery.recomputed_result_count == 96
    assert recovery.model_result_rerun_count == recovery.provider_calls == 0
    assert lineage.provider_call_count == lineage.transport_invocation_count == 879
    assert lineage.provider_envelope_count == lineage.public_projection_count == 879
    assert gate.passed is gate.capability_estimand_authorized is True
    assert gate.failure_ids == ()
    assert report.terminal_counts == {
        "completed_model_endpoint": 58,
        "model_result_failure": 38,
    }
    assert (report.base_valid_count, report.mechanism_qualified_count) == (31, 74)
    assert report.qualified_valid_count == 31
    assert report.mechanisms_with_qualified_task_support == 4
    assert report.reachability_minimum_support_gate_passed is True
    assert report.reachability_preflight_authorized_pending_independent_audit is False
    assert report.next_permitted_stage == execution.POSTRUN_STAGE


def test_v26_151_raw_only_denominator_and_recursive_serialization_are_exact() -> None:
    results = _results()
    recovery = execution._aggregation_recovery_audit(  # noqa: SLF001
        package_root=PACKAGE_ROOT,
        output_dir=FORMAL_DIR,
        recomputed_result_count=len(results),
    )
    aggregate_path = FORMAL_DIR / "fresh_capability_measurement_results.json"

    assert len(results) == len({item.job_id for item in results}) == 96
    assert recovery.recovered_checkpoint_sha256 == recovery.failed_checkpoint_sha256
    assert execution._canonical_bytes(results) == aggregate_path.read_bytes()  # noqa: SLF001
    assert all(item.measurement_support_available for item in results)
    assert all(item.model_endpoint_observed for item in results)
    assert all(item.instrument_integrity for item in results)
    assert all(item.privacy_compliant for item in results)


def test_v26_151_measurement_gate_is_noncompensatory() -> None:
    results = list(_results())
    results[0] = results[0].model_copy(update={"instrument_integrity": False})
    gate = execution._measurement_gate(results, complete_raw_count=96)  # noqa: SLF001

    assert gate.passed is False
    assert gate.capability_estimand_authorized is False
    assert gate.reachability_blocked is True
    assert gate.failure_ids == ("instrument_failure_zero",)
