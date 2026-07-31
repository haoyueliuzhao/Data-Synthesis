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
    PolicyUpdateResult,
    aggregate_cell_feedback,
    build_observed_policy,
    calibrate_clause_feedback,
    clause_reliability,
    make_synthesis_cell,
    random_same_shift_update,
    update_synthesis_policy,
)
from trusted_synthesis.core.refinement.update import _kl_divergence
from trusted_synthesis.hashing import canonical_hash


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


def test_score_only_control_accepts_domain_neutral_scalar_utilities() -> None:
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
        declared_tightening_options={
            "definition_alignment": ("require_same_definition",),
        },
    )
    task_cells = {"left": left, "right": right}
    policy = build_observed_policy(task_cells)
    statistics = aggregate_cell_feedback(policy, (), (), task_cells)

    result = update_synthesis_policy(
        policy,
        statistics,
        (),
        eta=1,
        beta=0,
        gamma=0,
        total_budget=20,
        calibration_manifest_hash="scalar_quality:test",
        enable_binding_tightening=False,
        require_calibrated_feedback=False,
        utility_overrides={left.cell_id: -0.75, right.cell_id: -0.25},
        utility_mode="score_only_control",
    )

    assert result.utility_mode == "score_only_control"
    assert result.activated_binding_constraints == {}
    assert result.next_policy.probabilities[right.cell_id] > policy.probabilities[right.cell_id]


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
        item.cell_id: item for item in aggregate_cell_feedback(policy, exposures, (), task_cells)
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


def test_kl_divergence_clamps_only_roundoff_negative_values() -> None:
    distribution = {
        "a": 0.3333333333333333,
        "b": 0.3333333333333333,
        "c": 0.3333333333333334,
    }

    assert _kl_divergence(distribution, distribution) == 0


def test_domain_conditional_ccgr_and_random_control_preserve_fixed_marginals() -> None:
    cells = {
        name: make_synthesis_cell(
            pattern_id=f"{domain}.{name}",
            binding_stratum_id=f"binding:{name}",
            difficulty_bucket="medium",
            distractor_profile_id="distractor:none",
        )
        for name, domain in (
            ("finance_left", "finance"),
            ("finance_right", "finance"),
            ("science_left", "science"),
            ("science_right", "science"),
        )
    }
    task_cells = {f"task_{name}": cell for name, cell in cells.items()}
    task_groups = {
        "task_finance_left": "finance",
        "task_finance_right": "finance",
        "task_science_left": "science",
        "task_science_right": "science",
    }
    fixed_weights = {"finance": 0.8, "science": 0.2}
    policy = build_observed_policy(
        task_cells,
        task_groups=task_groups,
        fixed_group_weights=fixed_weights,
    )
    exposures = tuple(
        FeedbackExposure(
            task_id=task_id,
            domain=task_groups[task_id],
            pattern_id=cell.pattern_id,
            failure_family="operation",
        )
        for task_id, cell in task_cells.items()
    )
    signal = _signal(
        task_id="task_finance_left",
        pattern_id=cells["finance_left"].pattern_id,
        clause_kind="operation",
        route=FeedbackRoute.AGENT_CAPABILITY_GAP,
    )
    feedback = calibrate_clause_feedback((signal,), task_cells, {"operation": 1.0})
    statistics = aggregate_cell_feedback(policy, exposures, feedback, task_cells)
    cell_groups = {cell.cell_id: task_groups[task_id] for task_id, cell in task_cells.items()}
    full = update_synthesis_policy(
        policy,
        statistics,
        feedback,
        eta=1,
        beta=1,
        gamma=0,
        total_budget=100,
        calibration_manifest_hash="calibration:conditional",
        conditioning_groups=cell_groups,
        fixed_group_weights=fixed_weights,
    )
    random_control = random_same_shift_update(
        policy,
        statistics,
        reference_update=full,
        total_budget=100,
        calibration_manifest_hash="calibration:conditional",
        random_seed=17,
    )

    assert full.conditioning_mode == "fixed_group_marginals"
    assert full.allocated_group_counts == {"finance": 80, "science": 20}
    for update in (full, random_control):
        observed = {"finance": 0.0, "science": 0.0}
        for cell_id, group in update.conditioning_groups.items():
            observed[group] += update.next_policy.probabilities[cell_id]
        assert observed == pytest.approx(fixed_weights)
    assert random_control.total_variation_distance == pytest.approx(
        full.total_variation_distance,
        abs=1e-10,
    )


def test_feedback_statistics_normalize_root_mass_shrink_and_gate_low_exposure() -> None:
    left = make_synthesis_cell(
        pattern_id="domain.shared_pattern",
        binding_stratum_id="binding:left",
        difficulty_bucket="hard",
        distractor_profile_id="distractor:none",
    )
    right = make_synthesis_cell(
        pattern_id="domain.shared_pattern",
        binding_stratum_id="binding:right",
        difficulty_bucket="hard",
        distractor_profile_id="distractor:none",
    )
    task_cells = {"left": left, "right": right}
    exposures = (
        FeedbackExposure(
            task_id="left",
            domain="domain",
            pattern_id=left.pattern_id,
            failure_family="operation",
        ),
        FeedbackExposure(
            task_id="right",
            domain="domain",
            pattern_id=right.pattern_id,
            failure_family="operation",
        ),
    )
    signals = (
        _signal(
            task_id="left",
            pattern_id=left.pattern_id,
            clause_kind="operation_a",
            route=FeedbackRoute.AGENT_CAPABILITY_GAP,
        ),
        _signal(
            task_id="left",
            pattern_id=left.pattern_id,
            clause_kind="operation_b",
            route=FeedbackRoute.AGENT_CAPABILITY_GAP,
        ),
    )
    policy = build_observed_policy(task_cells)
    feedback = calibrate_clause_feedback(
        signals,
        task_cells,
        {"operation_a": 1.0, "operation_b": 1.0},
    )
    shrunk = {
        item.cell_id: item
        for item in aggregate_cell_feedback(
            policy,
            exposures,
            feedback,
            task_cells,
            minimum_cell_exposure=1,
            shrinkage_strength=1,
        )
    }
    gated = {
        item.cell_id: item
        for item in aggregate_cell_feedback(
            policy,
            exposures,
            feedback,
            task_cells,
            minimum_cell_exposure=2,
            shrinkage_strength=1,
        )
    }

    assert shrunk[left.cell_id].raw_capability_gap_weight_sum == 2
    assert shrunk[left.cell_id].capability_gap_weight_sum == 1
    assert shrunk[left.cell_id].cell_capability_gap_rate == 1
    assert shrunk[left.cell_id].capability_gap_demand == pytest.approx(0.75)
    assert shrunk[right.cell_id].capability_gap_demand == pytest.approx(0.25)
    assert not gated[left.cell_id].minimum_exposure_met
    assert gated[left.cell_id].capability_gap_demand == 0


def test_clause_reliability_applies_finite_sample_confidence_discount() -> None:
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

    assert clause_reliability(
        metrics,
        confidence_prior_count=2,
    ) == pytest.approx(math.sqrt(0.5) * 0.5)


def test_ccgr_v1_policy_update_identity_remains_readable() -> None:
    cell = make_synthesis_cell(
        pattern_id="domain.legacy",
        binding_stratum_id="binding:legacy",
        difficulty_bucket="medium",
        distractor_profile_id="distractor:none",
    )
    task_cells = {"legacy_task": cell}
    policy = build_observed_policy(task_cells)
    update = update_synthesis_policy(
        policy,
        aggregate_cell_feedback(policy, (), (), task_cells),
        (),
        eta=0,
        beta=1,
        gamma=0,
        total_budget=1,
        calibration_manifest_hash="calibration:legacy",
        require_calibrated_feedback=False,
    )
    payload = update.model_dump(mode="json")
    payload["algorithm_version"] = "ccgr.v1"
    payload["schema_version"] = "refinement.v1"
    for field in (
        "conditioning_mode",
        "conditioning_groups",
        "fixed_group_weights",
        "allocated_group_counts",
        "cell_utility_components",
        "alpha",
        "lambda_defect",
        "prior_trajectory_metrics",
        "next_trajectory_metrics",
        "trajectory_feedback_manifest_hash",
        "trajectory_feedback_count",
    ):
        payload.pop(field)
    for statistic in payload["statistics"]:
        for field in (
            "raw_synthesis_defect_weight_sum",
            "raw_capability_gap_weight_sum",
            "pattern_exposure_count",
            "pattern_synthesis_defect_rate",
            "pattern_capability_gap_rate",
            "cell_synthesis_defect_rate",
            "cell_capability_gap_rate",
            "shrinkage_weight",
            "minimum_exposure_met",
            "trajectory_attempt_count",
            "valid_trajectory_count",
            "trajectory_validity_rate",
            "mean_trajectory_validity_score",
            "trajectory_attribute_profile_count",
            "trajectory_attribute_entropy",
            "trajectory_diversity_gain",
            "missing_attribute_rate",
        ):
            statistic.pop(field)
    for policy_key in ("prior_policy", "next_policy"):
        for policy_cell in payload[policy_key]["cells"]:
            policy_cell.pop("trajectory_attribute_profile")
    payload["update_id"] = canonical_hash(
        {key: value for key, value in payload.items() if key != "update_id"},
        prefix="ccgr_policy_update:",
    )

    loaded = PolicyUpdateResult.model_validate(payload)

    assert loaded.update_id == payload["update_id"]
    assert loaded.algorithm_version == "ccgr.v1"
    assert loaded.conditioning_mode == "global"



def test_ccgr_v2_policy_update_identity_remains_readable() -> None:
    cell = make_synthesis_cell(
        pattern_id="domain.legacy_v2",
        binding_stratum_id="binding:legacy_v2",
        difficulty_bucket="hard",
        distractor_profile_id="distractor:none",
    )
    task_cells = {"legacy_v2_task": cell}
    policy = build_observed_policy(task_cells)
    update = update_synthesis_policy(
        policy,
        aggregate_cell_feedback(policy, (), (), task_cells),
        (),
        eta=0,
        beta=1,
        gamma=0,
        total_budget=1,
        calibration_manifest_hash="calibration:legacy_v2",
        require_calibrated_feedback=False,
    )
    payload = update.model_dump(mode="json")
    payload["algorithm_version"] = "ccgr.v2"
    payload["schema_version"] = "refinement.v2"

    def downgrade_policy(
        policy_payload: dict,
        *,
        source_policy_id: str | None,
    ) -> dict[str, str]:
        identity_map: dict[str, str] = {}
        policy_payload["schema_version"] = "refinement.v2"
        policy_payload["source_policy_id"] = source_policy_id
        for policy_cell in policy_payload["cells"]:
            current_id = policy_cell["cell_id"]
            policy_cell.pop("trajectory_attribute_profile")
            policy_cell["schema_version"] = "refinement.v2"
            policy_cell["cell_id"] = canonical_hash(
                {
                    "pattern_id": policy_cell["pattern_id"],
                    "binding_stratum_id": policy_cell["binding_stratum_id"],
                    "difficulty_bucket": policy_cell["difficulty_bucket"],
                    "distractor_profile_id": policy_cell["distractor_profile_id"],
                    "active_binding_constraints": policy_cell[
                        "active_binding_constraints"
                    ],
                    "schema_version": "refinement.v2",
                },
                prefix="synthesis_cell:",
            )
            identity_map[current_id] = policy_cell["cell_id"]
        for field in ("probabilities", "target_probabilities"):
            policy_payload[field] = {
                identity_map[key]: value
                for key, value in policy_payload[field].items()
            }
        policy_payload["policy_id"] = canonical_hash(
            {
                key: value
                for key, value in policy_payload.items()
                if key != "policy_id"
            },
            prefix="synthesis_policy:",
        )
        return identity_map

    prior_map = downgrade_policy(payload["prior_policy"], source_policy_id=None)
    next_map = downgrade_policy(
        payload["next_policy"],
        source_policy_id=payload["prior_policy"]["policy_id"],
    )
    for statistic in payload["statistics"]:
        statistic["cell_id"] = prior_map[statistic["cell_id"]]
        for field in (
            "trajectory_attempt_count",
            "valid_trajectory_count",
            "trajectory_validity_rate",
            "mean_trajectory_validity_score",
            "trajectory_attribute_profile_count",
            "trajectory_attribute_entropy",
            "trajectory_diversity_gain",
            "missing_attribute_rate",
        ):
            statistic.pop(field)
    payload["cell_utilities"] = {
        prior_map[key]: value for key, value in payload["cell_utilities"].items()
    }
    payload["cell_transition_map"] = {
        prior_map[key]: next_map[value]
        for key, value in payload["cell_transition_map"].items()
    }
    payload["allocated_counts"] = {
        next_map[key]: value for key, value in payload["allocated_counts"].items()
    }
    for field in (
        "cell_utility_components",
        "alpha",
        "lambda_defect",
        "prior_trajectory_metrics",
        "next_trajectory_metrics",
        "trajectory_feedback_manifest_hash",
        "trajectory_feedback_count",
    ):
        payload.pop(field)
    payload["update_id"] = canonical_hash(
        {key: value for key, value in payload.items() if key != "update_id"},
        prefix="ccgr_policy_update:",
    )

    loaded = PolicyUpdateResult.model_validate(payload)

    assert loaded.update_id == payload["update_id"]
    assert loaded.algorithm_version == "ccgr.v2"
    assert loaded.schema_version == "refinement.v2"
