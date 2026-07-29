from __future__ import annotations

import math

import pytest

from trusted_synthesis.core.evaluation.counterfactual import (
    CounterfactualSliceMetrics,
)
from trusted_synthesis.core.feedback import (
    FeedbackExposure,
    FeedbackRoute,
    make_feedback_signal,
)
from trusted_synthesis.core.refinement import (
    aggregate_cell_feedback,
    build_observed_policy,
    calibrate_clause_feedback,
    clause_reliability,
    make_synthesis_cell,
    random_same_shift_update,
    update_synthesis_policy,
)


def test_ccgr_increases_capability_demand_and_suppresses_synthesis_defects() -> None:
    capability = make_synthesis_cell(
        pattern_id="domain.capability",
        binding_stratum_id="binding:clean",
        difficulty_bucket="hard",
        distractor_profile_id="distractor:hard",
    )
    defect = make_synthesis_cell(
        pattern_id="domain.defect",
        binding_stratum_id="binding:loose",
        difficulty_bucket="medium",
        distractor_profile_id="distractor:none",
        declared_tightening_options={
            "definition_alignment": ("require_same_definition",),
        },
    )
    interface = make_synthesis_cell(
        pattern_id="domain.interface",
        binding_stratum_id="binding:clean",
        difficulty_bucket="easy",
        distractor_profile_id="distractor:none",
    )
    task_cells = {
        "task_capability": capability,
        "task_defect": defect,
        "task_interface": interface,
    }
    exposures = tuple(
        FeedbackExposure(
            task_id=task_id,
            domain="domain",
            pattern_id=cell.pattern_id,
            failure_family="test_family",
        )
        for task_id, cell in task_cells.items()
    )
    signals = (
        _signal(
            task_id="task_capability",
            pattern_id=capability.pattern_id,
            clause_kind="operation_trace",
            route=FeedbackRoute.AGENT_CAPABILITY_GAP,
        ),
        _signal(
            task_id="task_defect",
            pattern_id=defect.pattern_id,
            clause_kind="definition_alignment",
            route=FeedbackRoute.UPSTREAM_DATA_DEFECT,
        ),
        _signal(
            task_id="task_interface",
            pattern_id=interface.pattern_id,
            clause_kind="output_contract",
            route=FeedbackRoute.INTERFACE_FAILURE,
        ),
    )
    policy = build_observed_policy(task_cells)
    feedback = calibrate_clause_feedback(
        signals,
        task_cells,
        {
            "operation_trace": 0.5,
            "definition_alignment": 1.0,
            "output_contract": 1.0,
        },
    )
    statistics = aggregate_cell_feedback(
        policy,
        exposures,
        feedback,
        task_cells,
    )

    result = update_synthesis_policy(
        policy,
        statistics,
        feedback,
        eta=1.0,
        beta=1.0,
        gamma=0.0,
        total_budget=101,
        calibration_manifest_hash="calibration:test",
        binding_tightening_threshold=0.5,
    )

    next_probability = {
        old_id: result.next_policy.probabilities[new_id]
        for old_id, new_id in result.cell_transition_map.items()
    }
    assert result.status == "passed"
    assert next_probability[capability.cell_id] > policy.probabilities[capability.cell_id]
    assert next_probability[defect.cell_id] < policy.probabilities[defect.cell_id]
    assert result.activated_binding_constraints == {
        defect.cell_id: ("require_same_definition",),
    }
    assert sum(result.allocated_counts.values()) == 101
    assert result.kl_divergence > 0


def test_uncalibrated_clause_is_fail_closed_but_raw_ablation_can_measure_it() -> None:
    cell = make_synthesis_cell(
        pattern_id="domain.pattern",
        binding_stratum_id="binding:one",
        difficulty_bucket="hard",
        distractor_profile_id="distractor:none",
    )
    task_cells = {"task": cell}
    exposures = (
        FeedbackExposure(
            task_id="task",
            domain="domain",
            pattern_id=cell.pattern_id,
            failure_family="operation_trace",
        ),
    )
    signal = _signal(
        task_id="task",
        pattern_id=cell.pattern_id,
        clause_kind="not_calibrated",
        route=FeedbackRoute.AGENT_CAPABILITY_GAP,
    )
    policy = build_observed_policy(task_cells)
    calibrated = calibrate_clause_feedback((signal,), task_cells, {})
    statistics = aggregate_cell_feedback(
        policy,
        exposures,
        calibrated,
        task_cells,
    )
    result = update_synthesis_policy(
        policy,
        statistics,
        calibrated,
        eta=1,
        beta=1,
        gamma=0,
        total_budget=10,
        calibration_manifest_hash="calibration:missing",
    )
    raw = calibrate_clause_feedback(
        (signal,),
        task_cells,
        {},
        force_raw_reliability=True,
    )

    assert calibrated[0].calibrated_weight == 0
    assert calibrated[0].calibration_status == "missing"
    assert result.status == "blocked"
    assert result.failures == ("no_calibrated_directional_feedback",)
    assert raw[0].calibrated_weight == 1
    assert raw[0].calibration_status == "raw_ablation"


def test_coverage_regularization_recovers_underrepresented_cells() -> None:
    common = make_synthesis_cell(
        pattern_id="domain.common",
        binding_stratum_id="binding:common",
        difficulty_bucket="easy",
        distractor_profile_id="distractor:none",
    )
    scarce = make_synthesis_cell(
        pattern_id="domain.scarce",
        binding_stratum_id="binding:scarce",
        difficulty_bucket="expert",
        distractor_profile_id="distractor:none",
    )
    task_cells = {"task_1": common, "task_2": common, "task_3": scarce}
    exposures = tuple(
        FeedbackExposure(
            task_id=task_id,
            domain="domain",
            pattern_id=cell.pattern_id,
            failure_family="answer",
        )
        for task_id, cell in task_cells.items()
    )
    policy = build_observed_policy(
        task_cells,
        target_probabilities={common.cell_id: 0.2, scarce.cell_id: 0.8},
    )
    statistics = aggregate_cell_feedback(policy, exposures, (), task_cells)
    result = update_synthesis_policy(
        policy,
        statistics,
        (),
        eta=1,
        beta=1,
        gamma=1,
        total_budget=30,
        calibration_manifest_hash="calibration:none",
        require_calibrated_feedback=False,
    )

    assert result.next_policy.probabilities[scarce.cell_id] > policy.probabilities[scarce.cell_id]


def test_random_control_matches_full_ccgr_distribution_shift() -> None:
    left = make_synthesis_cell(
        pattern_id="domain.left",
        binding_stratum_id="binding:left",
        difficulty_bucket="medium",
        distractor_profile_id="distractor:none",
    )
    right = make_synthesis_cell(
        pattern_id="domain.right",
        binding_stratum_id="binding:right",
        difficulty_bucket="medium",
        distractor_profile_id="distractor:none",
    )
    task_cells = {"left": left, "right": right}
    exposures = tuple(
        FeedbackExposure(
            task_id=task_id,
            domain="domain",
            pattern_id=cell.pattern_id,
            failure_family="operation",
        )
        for task_id, cell in task_cells.items()
    )
    signal = _signal(
        task_id="left",
        pattern_id=left.pattern_id,
        clause_kind="operation",
        route=FeedbackRoute.AGENT_CAPABILITY_GAP,
    )
    policy = build_observed_policy(task_cells)
    feedback = calibrate_clause_feedback((signal,), task_cells, {"operation": 1.0})
    statistics = aggregate_cell_feedback(policy, exposures, feedback, task_cells)
    full = update_synthesis_policy(
        policy,
        statistics,
        feedback,
        eta=1,
        beta=1,
        gamma=0,
        total_budget=20,
        calibration_manifest_hash="calibration:test",
    )
    random_control = random_same_shift_update(
        policy,
        statistics,
        reference_update=full,
        total_budget=20,
        calibration_manifest_hash="calibration:test",
        random_seed=7,
    )

    assert math.isclose(
        random_control.total_variation_distance,
        full.total_variation_distance,
        abs_tol=1e-10,
    )
    assert random_control.utility_mode == "random_control"


def test_clause_calibration_uses_detection_localization_and_closure() -> None:
    metrics = CounterfactualSliceMetrics(
        generated_case_count=4,
        valid_case_count=2,
        detected_case_count=2,
        mutation_validity_rate=0.5,
        detection_rate=0.5,
        minimality_pass_rate=1.0,
        mean_minimality_score=1.0,
        root_cause_f1=1.0,
        failure_closure_f1=1.0,
    )

    assert math.isclose(clause_reliability(metrics), math.sqrt(0.5))


def test_cell_feedback_counts_only_explicitly_evaluated_tasks() -> None:
    evaluated = make_synthesis_cell(
        pattern_id="domain.evaluated",
        binding_stratum_id="binding:evaluated",
        difficulty_bucket="medium",
        distractor_profile_id="distractor:none",
    )
    unevaluated = make_synthesis_cell(
        pattern_id="domain.unevaluated",
        binding_stratum_id="binding:unevaluated",
        difficulty_bucket="medium",
        distractor_profile_id="distractor:none",
    )
    task_cells = {
        "task_evaluated": evaluated,
        "task_unevaluated": unevaluated,
    }
    exposures = (
        FeedbackExposure(
            task_id="task_evaluated",
            domain="domain",
            pattern_id=evaluated.pattern_id,
            failure_family="answer",
        ),
    )
    policy = build_observed_policy(
        task_cells,
        target_probabilities={evaluated.cell_id: 0.5, unevaluated.cell_id: 0.5},
    )

    statistics = {
        item.cell_id: item
        for item in aggregate_cell_feedback(policy, exposures, (), task_cells)
    }

    assert statistics[evaluated.cell_id].exposure_count == 1
    assert statistics[evaluated.cell_id].observed_share == 1
    assert statistics[unevaluated.cell_id].exposure_count == 0
    assert statistics[unevaluated.cell_id].observed_share == 0
    assert statistics[unevaluated.cell_id].coverage_gap == 0.5


def test_cell_feedback_rejects_stale_cell_identity() -> None:
    expected = make_synthesis_cell(
        pattern_id="domain.expected",
        binding_stratum_id="binding:expected",
        difficulty_bucket="hard",
        distractor_profile_id="distractor:none",
    )
    stale = make_synthesis_cell(
        pattern_id="domain.stale",
        binding_stratum_id="binding:stale",
        difficulty_bucket="hard",
        distractor_profile_id="distractor:none",
    )
    task_cells = {"task": expected}
    exposure = FeedbackExposure(
        task_id="task",
        domain="domain",
        pattern_id=expected.pattern_id,
        failure_family="operation",
    )
    signal = _signal(
        task_id="task",
        pattern_id=expected.pattern_id,
        clause_kind="operation",
        route=FeedbackRoute.AGENT_CAPABILITY_GAP,
    )
    feedback = calibrate_clause_feedback((signal,), {"task": stale}, {"operation": 1.0})
    policy = build_observed_policy(task_cells)

    with pytest.raises(ValueError, match="does not match its task binding"):
        aggregate_cell_feedback(policy, (exposure,), feedback, task_cells)


def _signal(
    *,
    task_id: str,
    pattern_id: str,
    clause_kind: str,
    route: FeedbackRoute,
):
    return make_feedback_signal(
        task_id=task_id,
        domain="domain",
        pattern_id=pattern_id,
        clause_id=f"clause:{task_id}:{clause_kind}",
        clause_kind=clause_kind,
        failure_family="test_family",
        severity="fatal",
        route=route,
        source_kind="quality_contract",
        failure_code="test_failure",
        weight=1.0,
    )
