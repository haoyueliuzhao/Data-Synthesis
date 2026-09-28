"""Zero-model V6 mathematical controls, independent of experimental outcomes."""

import math

import pytest

from trusted_synthesis.finance_research import v6_distribution as v6


def test_manual_odds_and_within_group_ratios_and_degenerate_exact_prior():
    prior = {
        "x": {"a": 0.55, "b": 0.25, "c": 0.15, "d": 0.05},
        "single_group": {"u": "1/3", "v": "2/3"},
        "single_state": {"only": 1},
    }
    chi = {
        "x": {"a": 0, "b": 1, "c": 0, "d": 1},
        "single_group": {"u": 1, "v": 1},
        "single_state": {"only": 0},
    }
    for name, factor in (("Manual+", 2), ("Manual-", 0.5)):
        result = v6.manual_distribution(prior, chi, direction=name)
        assert result["single_group"] == prior["single_group"]
        assert result["single_state"] == prior["single_state"]
        row = result["x"]
        assert min(row.values()) > 0 and math.fsum(row.values()) == pytest.approx(1)
        assert row["a"] / row["c"] == pytest.approx(0.55 / 0.15)
        assert row["b"] / row["d"] == pytest.approx(5)
        group_mass = row["b"] + row["d"]
        assert group_mass / (1 - group_mass) == pytest.approx(factor * 0.3 / 0.7)
        assert group_mass != pytest.approx(2 / 3 if factor == 2 else 1 / 3)


def test_fixed_potential_exact_contraction_and_limit():
    r = dict(a=0.6, b=0.3, c=0.1)
    p, q, phi = dict(a=0.1, b=0.3, c=0.6), dict(a=0.8, b=0.1, c=0.1), dict(a=0.2, b=0.8, c=0.5)
    limit = v6.fixed_potential_limit(r, phi)
    assert v6.fixed_potential_step(limit, r, phi) == pytest.approx(limit)
    next_p, next_q = v6.fixed_potential_step(p, r, phi), v6.fixed_potential_step(q, r, phi)
    assert v6.oscillation_distance(next_p, next_q) == pytest.approx(
        0.8 * v6.oscillation_distance(p, q)
    )
    for _ in range(150):
        p = v6.fixed_potential_step(p, r, phi)
    assert v6.oscillation_distance(p, limit) < 1e-12


def test_normalization_cross_zero_and_frozen_novelty_contraction():
    cert = v6.contraction_certificate()
    assert cert["maximum_slope_subtraction"] == pytest.approx(0.72)
    assert cert["scalar_slope_lower_bound"] == pytest.approx(0.08)
    assert cert["certified_contraction_factor"] == 0.8
    r, p, q, c = dict(a=0.8, b=0.2), dict(a=0.1, b=0.9), dict(a=0.9, b=0.1), dict(a=0.1, b=0.9)
    delta = [math.log(p[s] / q[s]) for s in p]
    assert min(delta) < 0 < max(delta)
    distance = v6.oscillation_distance(
        v6.frozen_contribution_step(p, r, c), v6.frozen_contribution_step(q, r, c)
    )
    assert distance <= 0.8 * v6.oscillation_distance(p, q) + 1e-14
    assert v6.contraction_certificate(b=1)["certified_contraction_factor"] is None


def test_outside_sufficient_condition_can_expand_not_a_universal_claim():
    r, p, q, c = (
        dict(a=0.5, b=0.5),
        dict(a=0.500001, b=0.499999),
        dict(a=0.5, b=0.5),
        dict(a=0.5, b=0.5),
    )
    ratio = v6.oscillation_distance(
        v6.frozen_contribution_step(p, r, c, b=2), v6.frozen_contribution_step(q, r, c, b=2)
    ) / v6.oscillation_distance(p, q)
    assert ratio > 1


def test_first_reverse_positive_equal_tv_but_not_general_equal_kl():
    prior = {"x": {"a": 0.7, "b": 0.2, "c": 0.1}}
    C = {"x": {"a": -0.2, "b": 0.3, "c": 0.8}}
    plus = v6.automatic_update(prior, prior, C, {"x": 1}, arm="C-only")["pi_next"]
    full = v6.automatic_update(prior, prior, C, {"x": 1}, arm="Full")["pi_next"]
    assert full["x"] == pytest.approx(plus["x"])
    minus = v6.first_direction_reverse(prior, plus)
    assert 19**0.16 < 2 and min(minus["x"].values()) > 0

    def tv(row):
        return 0.5 * sum(abs(row[s] - prior["x"][s]) for s in row)

    def kl(row):
        return sum(row[s] * math.log(row[s] / prior["x"][s]) for s in row)

    assert tv(plus["x"]) == pytest.approx(tv(minus["x"]))
    assert not math.isclose(kl(plus["x"]), kl(minus["x"]), rel_tol=1e-4)
    with pytest.raises(ValueError, match="positive"):
        v6.first_direction_reverse({"x": {"a": 0.1, "b": 0.9}}, {"x": {"a": 0.4, "b": 0.6}})


def test_automatic_update_delegates_unchanged_kernel_and_zero_feedback_is_identity(monkeypatch):
    called = []
    original = v6.kernel.anchored_update

    def spy(*args, **kwargs):
        called.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(v6.kernel, "anchored_update", spy)
    pi, r, C, mu = (
        {"x": {"a": 0.7, "b": 0.3}},
        {"x": {"a": 0.5, "b": 0.5}},
        {"x": {"a": 0.3, "b": -0.7}},
        {"x": 1},
    )
    for arm in ("C-only", "Full"):
        v6.automatic_update(pi, r, C, mu, arm=arm)
    assert called == [
        {**v6.PARAMETERS, "contribution_only": True},
        {**v6.PARAMETERS, "contribution_only": False},
    ]
    zero = v6.automatic_update(pi, r, C, mu, arm="Full", feedback_all_zero=True)
    assert zero["pi_next"] == pi and len(called) == 2
    assert zero["theoretical_Contribution_zero"] is False


def test_demo_is_synthetic_with_expected_five_arm_scope_and_no_model_calls():
    result = v6.numerical_demonstration()
    assert len(result["random_pair_checks"]) == 256
    assert result["maximum_observed_pair_ratio"] <= 0.8 + 1e-12
    assert result["iterations"][-1]["one_step_residual"] < 1e-12
    assert result["API_calls"] == result["GPU_calls"] == result["model_calls"] == 0
    assert v6.design_metadata()["main_candidate"] == "Full"
    assert v6.design_metadata()["outer_steps"] == [400, 800, 1200, 1600]
    assert v6.design_metadata()["real_closed_loop_convergence_proved"] is False


def test_support_zeros_and_mass_drift_are_rejected_not_repaired():
    with pytest.raises(ValueError, match="positive"):
        v6.oscillation_distance(dict(a=0, b=1), dict(a=0.5, b=0.5))
    with pytest.raises(ValueError, match="normalized"):
        v6.oscillation_distance(dict(a=1, b=1), dict(a=0.5, b=0.5))
