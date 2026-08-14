from __future__ import annotations

from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_boundary_calibration import (  # noqa: E501
    STOPPING_SUBMECHANISM_IDS,
    BernoulliInterval,
    FinanceStoppingBoundaryCalibrationReport,
    StoppingCalibrationGate,
    StoppingTaskCalibrationRow,
    stopping_boundary_calibration_report_id,
)


def _row(submechanism_id: str) -> StoppingTaskCalibrationRow:
    return StoppingTaskCalibrationRow(
        task_artifact_id=f"task:{submechanism_id}",
        submechanism_id=submechanism_id,
        runtime_eligible_count=12,
        trigger_rate=1.0,
        resolution_rate=0.5,
        ordered_behavior_rate=0.5,
        semantic_answer_rate=0.5,
        capability_contract_success_rate=0.5,
        capability_contract_interval_95=BernoulliInterval(lower=0.25, upper=0.75),
        boundary_task=True,
    )


def _gates(*, boundary_passed: bool) -> tuple[StoppingCalibrationGate, ...]:
    runtime = tuple(
        StoppingCalibrationGate(
            gate_id=f"runtime_{index}",
            category="runtime",
            observed=1.0,
            requirement=">=0.98",
            passed=True,
        )
        for index in range(5)
    )
    instrument = tuple(
        StoppingCalibrationGate(
            gate_id=f"instrument_{index}",
            category="instrument",
            observed=1.0,
            requirement=">=0.1",
            passed=True,
        )
        for index in range(5)
    )
    boundary = StoppingCalibrationGate(
        gate_id="repair_target_boundary_count",
        category="boundary",
        observed=float(boundary_passed),
        requirement=">=1",
        passed=boundary_passed,
    )
    return (*runtime, *instrument, boundary)


def _report(*, boundary_passed: bool) -> FinanceStoppingBoundaryCalibrationReport:
    gates = _gates(boundary_passed=boundary_passed)
    values = {
        "contract_id": "contract:test",
        "recorded_rollout_count": 60,
        "runtime_eligible_rollout_count": 60,
        "api_transport_resolution_rate": 1.0,
        "bounded_json_resolution_rate": 1.0,
        "observation_replay_rate": 1.0,
        "authority_integrity_rate": 1.0,
        "runtime_pathology_rate": 0.0,
        "semantic_accuracy_given_runtime_eligible": 0.5,
        "end_to_end_valid_success_rate": 0.5,
        "locator_precondition_failure_count": 0,
        "task_rows": tuple(_row(item) for item in STOPPING_SUBMECHANISM_IDS),
        "repair_target_boundary_count": 1 if boundary_passed else 0,
        "gates": gates,
        "runtime_measurement_ready": True,
        "stopping_instrument_repair_validated": True,
        "boundary_signal_observed": boundary_passed,
        "fresh_stable_support_development_permitted": boundary_passed,
        "failure_codes": () if boundary_passed else ("repair_target_boundary_count",),
        "outcome_set_hash": "outcomes:test",
        "behavior_set_hash": "behaviors:test",
        "api_call_count": 60,
        "total_model_tokens": 6000,
        "estimated_cost_usd": 0.1,
        "discovered_models": ("DeepSeek-V4-Flash",),
        "next_permitted_stage": (
            "fresh_stable_support_development_population_build"
            if boundary_passed
            else "stopping_instrument_redesign_only"
        ),
    }
    provisional = FinanceStoppingBoundaryCalibrationReport.model_construct(
        report_id="pending", **values
    )
    return FinanceStoppingBoundaryCalibrationReport(
        report_id=stopping_boundary_calibration_report_id(provisional), **values
    )


def test_stopping_calibration_permits_fresh_support_only_after_boundary_signal() -> None:
    report = _report(boundary_passed=True)

    assert report.runtime_measurement_ready
    assert report.stopping_instrument_repair_validated
    assert report.boundary_signal_observed
    assert report.fresh_stable_support_development_permitted
    assert (
        report.next_permitted_stage
        == "fresh_stable_support_development_population_build"
    )


def test_stopping_calibration_fails_closed_without_boundary_signal() -> None:
    report = _report(boundary_passed=False)

    assert report.runtime_measurement_ready
    assert report.stopping_instrument_repair_validated
    assert not report.boundary_signal_observed
    assert not report.fresh_stable_support_development_permitted
    assert report.next_permitted_stage == "stopping_instrument_redesign_only"

