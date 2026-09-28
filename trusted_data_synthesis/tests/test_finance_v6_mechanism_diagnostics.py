"""Pure fixed arithmetic controls; no real FinQA or Student result is asserted."""

import pytest

from trusted_synthesis.finance_research.v6_mechanism_diagnostics import (
    cross_repeat_diagnostics,
    direction_utility_report,
    distribution_change,
    same_point_n_diagnostics,
)


def inputs():
    pi = {"a": {"x": 0.5, "y": 0.5}, "singleton": {"only": 1.0}}
    C = {"a": {"x": 2.0, "y": -2.0}, "singleton": {"only": 0.0}}
    return pi, C, {"a": 0.25, "singleton": 0.75}


def test_cross_repeat_uses_other_C_without_second_mu_factor():
    pi, C, mu = inputs()
    r = cross_repeat_diagnostics(pi, pi, [C, C], mu, denominators=(350, 350))
    d = r["proposed_pi"][0]["a"]["x"] - 0.5
    assert r["S_0_to_1"] == pytest.approx(4 * d)
    assert r["S_1_to_0"] == pytest.approx(4 * d)
    assert r["C_full_from_equal_halves"] == C
    assert r["proposed_pi"][0]["singleton"] == {"only": 1.0}
    assert r["selected_repeat"] is None
    assert not r["actual_feedback_provenance_verified"]
    assert not r["training_benefit_established"]


def test_repeat_disagreement_keeps_both_negative_cross_scores():
    pi, C, mu = inputs()
    reverse = {t: {z: -v for z, v in row.items()} for t, row in C.items()}
    r = cross_repeat_diagnostics(pi, pi, [C, reverse], mu, denominators=(350, 350))
    assert r["S_0_to_1"] < 0 and r["S_1_to_0"] < 0
    assert all(v > 0 for v in r["self_scores"])
    assert all(v == 0 for row in r["C_full_from_equal_halves"].values() for v in row.values())
    assert r["actual_update_requires_complete_700"]


@pytest.mark.parametrize("denominators", [(349, 350), (100, 100), (700, 0)])
def test_no_success_only_or_incomplete_repeat_denominator(denominators):
    pi, C, mu = inputs()
    with pytest.raises(ValueError, match="350"):
        cross_repeat_diagnostics(pi, pi, [C, C], mu, denominators=denominators)


def test_first_point_n_has_no_distribution_effect_and_zero_feedback_holds():
    pi, C, mu = inputs()
    r = same_point_n_diagnostics(pi, pi, C, mu)
    assert not r["N_distribution_effect_nonzero"]
    assert r["local_training_effect"] is None and r["closed_loop_effect"] is None
    r = same_point_n_diagnostics(pi, pi, C, mu, feedback_all_zero=True)
    assert r["C_only"] == r["Full"] == pi


def test_n_changes_distribution_away_from_prior_but_does_not_claim_training_gain():
    pi = {"task": {"a": 0.8, "b": 0.2}}
    prior = {"task": {"a": 0.5, "b": 0.5}}
    C = {"task": {"a": 1.0, "b": -4.0}}
    r = same_point_n_diagnostics(pi, prior, C, {"task": 1.0})
    assert r["N_distribution_effect_nonzero"]
    assert r["Full"]["task"]["b"] > r["C_only"]["task"]["b"]
    assert not r["genuine_theta_Adam_RNG_G_feedback_identity_verified"]


def test_less_harmed_than_reverse_is_not_positive_vs_static():
    keys = [f"task{t}:rep{r}" for t in range(120) for r in range(3)]
    rows = {
        arm: {k: float(i < successes) for i, k in enumerate(keys)}
        for arm, successes in (("Static", 200), ("positive", 150), ("reverse", 100))
    }
    r = direction_utility_report(rows, registered_keys=keys)
    assert r["only_less_harmed_than_reverse"]
    assert not r["observed_numeric_positive_vs_Static"]
    assert not r["checkpoint_selection_allowed"]
    rows["reverse"].pop(keys[0])
    with pytest.raises(ValueError, match="denominator"):
        direction_utility_report(rows, registered_keys=keys)


def test_distribution_diagnostics_keep_singletons_and_unnormalized_input_rejected():
    pi, _, mu = inputs()
    r = distribution_change(pi, pi, mu)
    assert r["mu_weighted"]["TV"] == r["mu_weighted"]["KL_new_to_old"] == 0
    assert "singleton" in r["per_task"]
    with pytest.raises(ValueError, match="marginals"):
        distribution_change(pi, pi, {"a": 0.25, "singleton": 0.25})
