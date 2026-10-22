"""Small synthetic CPU tests; no real feedback, model or GPU accessed."""
import copy
import json

import pytest

import finqa_v70_diagnostics as diagnostics
from trusted_synthesis.finance_research import v6_distribution as original


def inputs(current=None, sign=1.0):
    prior = {"adjustable": {"a": 0.6, "b": 0.4}, "single": {"only": 1.0}}
    current = current or {"adjustable": {"a": 0.3, "b": 0.7}, "single": {"only": 1.0}}
    mu = {"adjustable": 0.25, "single": 0.75}
    p = current["adjustable"]
    C = {"adjustable": {"a": sign * p["b"], "b": -sign * p["a"]}, "single": {"only": 0.0}}
    return current, prior, mu, C


def update(current, prior, mu, C, zero=False):
    if zero:
        return original.automatic_update(current, prior, C, mu, arm="Full", feedback_all_zero=True)
    return original.kernel.anchored_update(current, prior, C, mu,
        control_tasks=[t for t in current if len(current[t]) == 1], **original.PARAMETERS)


def analyzed(current=None, sign=1.0):
    p, r, mu, C = inputs(current, sign)
    formal = update(p, r, mu, C)
    return diagnostics.analyze_frozen_point(current=p, prior=r, mu=mu, formal_update=formal,
        draw_updates={"draw0": formal, "draw1": update(p, r, mu, inputs(p, -sign)[3])},
        feedback_all_zero=False, draw_feedback_all_zero={"draw0": False, "draw1": False},
        binding={"context_id": "synthetic", "step": 894 if current is None else 1192})


def test_policy_is_finite_cpu_only_and_not_a_training_replacement():
    rule = diagnostics.policy()
    assert rule["max_iterations"] == 100
    assert rule["max_adjustable_Hilbert_tolerance"] == 1e-8
    assert rule["novelty_recomputed_from_each_internal_p"]
    assert rule["formal_q_not_replaced_by_reference"]
    assert not rule["draw_sensitivity_is_variance_estimate"]
    assert not rule["draw_sensitivity_is_confidence_interval"]
    assert not rule["formal_q_is_average_of_draw_q"]
    assert not rule["all_zero_feedback_is_convergence"]
    assert rule["model_calls"] == rule["GPU_work"] == rule["backward_passes"] == 0


def test_formal_first_step_matches_original_full_and_converges_without_mutation():
    p, r, mu, C = inputs()
    formal = update(p, r, mu, C)
    before = copy.deepcopy((p, r, mu, formal))
    result = diagnostics.frozen_reference(current=p, prior=r, mu=mu, update=formal, feedback_all_zero=False)
    assert result["status"] == "NUMERICALLY_CONVERGED_FROZEN_REFERENCE"
    assert 1 <= result["iterations"] <= 100
    assert result["first_step_match"]["passed"]
    assert result["trace"][-1]["max_adjustable_Hilbert_update"] <= 1e-8
    assert result["certificate"]["certified_contraction_factor"] == 0.8
    assert result["formal_q"] == formal["pi_next"]
    assert result["formal_q"] != result["fixed_point"]
    assert result["frozen_inputs"]["temperature"] == formal["temperature"]
    assert (p, r, mu, formal) == before
    json.dumps(result, allow_nan=False)


def test_adjustable_mass_is_renormalized_and_both_KL_directions_retained():
    result = analyzed()["formal"]
    metrics = result["R"]
    assert metrics["adjustable_mu"] == 0.25
    assert metrics["adjustable"]["TV"] == pytest.approx(4 * metrics["all_tasks"]["TV"])
    assert set(metrics["per_task"]["adjustable"]) == {"TV", "KL_left_to_right", "KL_right_to_left", "Hilbert"}
    assert metrics["per_task"]["single"] == dict(TV=0.0, KL_left_to_right=0.0, KL_right_to_left=0.0, Hilbert=0.0)


def test_novelty_tracks_internal_p_but_contribution_and_scales_never_recomputed(monkeypatch):
    p, r, mu, C = inputs()
    formal = update(p, r, mu, C)
    def forbidden(*args, **kwargs):
        pytest.fail("dynamic RMS or anchored update must not run inside frozen iteration")
    monkeypatch.setattr(original.kernel, "contribution_temperatures", forbidden)
    monkeypatch.setattr(original.kernel, "anchored_update", forbidden)
    observed, step = [], original.frozen_contribution_step
    def record(p, r, smooth):
        observed.append((dict(p), dict(smooth)))
        return step(p, r, smooth)
    monkeypatch.setattr(original, "frozen_contribution_step", record)
    result = diagnostics.frozen_reference(current=p, prior=r, mu=mu, update=formal, feedback_all_zero=False)
    adjustable = [row for row in observed if "a" in row[0]]
    assert len(adjustable) == result["iterations"]
    assert adjustable[0][0] != adjustable[1][0]
    assert all(row[1] == formal["task_diagnostics"]["adjustable"]["C_tilde"] for row in adjustable)


def test_two_draw_sensitivity_keeps_formal_q_and_is_not_uncertainty_inference():
    result = analyzed()
    sens = result["draw_sensitivity"]
    assert sens["status"] == "COMPLETE"
    assert sens["one_step"]["adjustable"]["TV"] > 0
    assert sens["reference"]["adjustable"]["TV"] > 0
    assert not sens["confidence_interval"] and not sens["variance_estimate"]
    assert not sens["formal_q_averaged"]
    p, r, mu, C = inputs()
    assert result["formal"]["formal_q"] == update(p, r, mu, C)["pi_next"]


def test_tracking_reports_D_and_hilbert_bound_only_after_real_q_continuity():
    previous = analyzed()
    current = analyzed(previous["formal"]["formal_q"], sign=-1)
    result = diagnostics.compare_frozen_points(previous, current)
    assert result["status"] == "COMPLETE"
    assert result["D"]["adjustable"]["TV"] > 0
    assert result["tracking"]["maximum_adjustable"]["finite_reference_relation_passed"]
    assert not result["TV_contraction_claim"]
    row = result["tracking"]["per_task"]["adjustable"]
    assert row["exact_reference_rhs"] == 0.8 * row["E_previous"] + row["D_H_next"]
    assert row["finite_reference_allowance"] >= 0
    with pytest.raises(ValueError, match="actually applied formal q"):
        diagnostics.compare_frozen_points(previous, analyzed())


def test_actual_allzero_is_uninformative_not_frozen_convergence():
    p, r, mu, C = inputs()
    zero = update(p, r, mu, C, zero=True)
    result = diagnostics.analyze_frozen_point(current=p, prior=r, mu=mu, formal_update=zero,
        draw_updates={"draw0": zero, "draw1": zero}, feedback_all_zero=True,
        draw_feedback_all_zero={"draw0": True, "draw1": True}, binding={"actual_rewards_all_zero": True})
    assert result["formal"]["status"] == "UNINFORMATIVE_FEEDBACK"
    assert result["formal"]["fixed_point"] is None
    assert not result["formal"]["numeric_convergence"]
    assert result["formal"]["certificate"] is None
    assert result["draw_sensitivity"]["reference"] is None


def test_zero_C_without_allzero_rewards_does_not_invent_an_uninformative_branch():
    p, r, mu, _ = inputs()
    C = {t: {s: 0.0 for s in row} for t, row in p.items()}
    formal = update(p, r, mu, C)
    result = diagnostics.frozen_reference(current=p, prior=r, mu=mu, update=formal, feedback_all_zero=False)
    assert result["numeric_convergence"]
    assert not result["feedback_all_zero"]
    assert result["formal_q"] != p
    assert result["frozen_inputs"]["temperature"]["global_scale_after_floor"] == 1e-8


@pytest.mark.parametrize("damage,match", [
    ("q", "first frozen step"), ("scale", "saved RMS scale"),
    ("arm", "registered Full"), ("nonfinite", "finite_scalar"),
])
def test_bad_first_step_scales_parameters_or_C_are_rejected(damage, match):
    p, r, mu, C = inputs()
    formal = update(p, r, mu, C)
    if damage == "q":
        formal["pi_next"]["adjustable"] = dict(p["adjustable"])
        formal["task_diagnostics"]["adjustable"]["pi_next"] = dict(p["adjustable"])
    elif damage == "scale":
        formal["temperature"]["global_scale_after_floor"] *= 2
    elif damage == "arm":
        formal["contribution_only"] = True
    else:
        formal["task_diagnostics"]["adjustable"]["C"]["a"] = float("nan")
    with pytest.raises(ValueError, match=match):
        diagnostics.frozen_reference(current=p, prior=r, mu=mu, update=formal, feedback_all_zero=False)


def test_no_adjustable_tasks_is_not_claimed_as_evidence_of_convergence():
    # Production's original RMS kernel refuses a population of only controls.
    p = {"only": {"state": 1.0}}
    mu, C = {"only": 1.0}, {"only": {"state": 0.0}}
    with pytest.raises(ValueError, match="noncontrol_optimization_population"):
        update(p, p, mu, C)


def test_singleton_controls_keep_None_smoothing_and_do_not_enter_RMS_or_iteration():
    result = analyzed()["formal"]
    frozen = result["frozen_inputs"]
    assert frozen["control_tasks"] == ["single"]
    assert frozen["C_tilde"]["single"] == {"only": None}
    assert frozen["T_C"]["single"] is None
    assert "single" not in frozen["temperature"]["T_C"]
    assert frozen["temperature"]["noncontrol_total_mu"] == 0.25
    assert result["fixed_point"]["single"] == {"only": 1.0}


def test_iteration_budget_exhaustion_is_not_reported_as_convergence(monkeypatch):
    monkeypatch.setattr(diagnostics, "MAX_ITERATIONS", 1)
    p, r, mu, C = inputs()
    result = diagnostics.frozen_reference(current=p, prior=r, mu=mu,
                                         update=update(p, r, mu, C), feedback_all_zero=False)
    assert result["iterations"] == 1
    assert result["status"] == "MAX_ITERATIONS_REACHED"
    assert not result["numeric_convergence"]


def test_full_and_draw_actual_reward_zero_flags_must_agree():
    p, r, mu, C = inputs()
    formal = update(p, r, mu, C)
    with pytest.raises(ValueError, match="allzero flags contradict"):
        diagnostics.analyze_frozen_point(current=p, prior=r, mu=mu, formal_update=formal,
            draw_updates={"draw0": formal, "draw1": formal}, feedback_all_zero=True,
            draw_feedback_all_zero={"draw0": False, "draw1": False}, binding={"context": "test"})
