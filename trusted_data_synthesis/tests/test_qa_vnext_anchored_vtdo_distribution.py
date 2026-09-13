"""Exact finite-support dual-KL and documented synthetic novelty reversal controls."""

import math

import pytest
import torch

from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.distribution import (
    anchored_update,
    contribution_temperatures,
)


def centered(pi, *, mu=1.0):
    raw = {"endpoint": -1.0, "movement": 1.0}
    mean = math.fsum(pi[state] * raw[state] for state in pi)
    return {state: mu * (value - mean) for state, value in raw.items()}


def test_first_round_zero_novelty_matches_C_only_without_reweighting_C():
    pi = {"x": {"endpoint": 0.5, "movement": 0.5}}
    C = {"x": centered(pi["x"])}
    full = anchored_update(pi, pi, C, {"x": 1})
    c_only = anchored_update(pi, pi, C, {"x": 1}, contribution_only=True)
    assert full["task_diagnostics"]["x"]["N"] == {"endpoint": 0, "movement": 0}
    assert full["pi_next"]["x"] == pytest.approx(c_only["pi_next"]["x"], abs=1e-15)
    assert c_only["contribution_exponent"] == full["contribution_exponent"] == 0.8
    assert c_only["effective_novelty_exponent"] == 0
    changed_exponent = anchored_update(
        pi, pi, C, {"x": 1}, contribution_only=True, contribution_exponent=1.0
    )
    assert changed_exponent["pi_next"]["x"]["movement"] != c_only["pi_next"]["x"]["movement"]


def test_mu_scaled_RMS_uses_only_optimization_tasks_and_normalizes_their_mass():
    pi = {task: {"endpoint": "1/2", "movement": "1/2"} for task in ("small", "large", "control")}
    mu = {"small": "1/10", "large": "2/5", "control": "1/2"}
    C = {
        "small": {"endpoint": -0.1, "movement": 0.1},
        "large": {"endpoint": -0.4, "movement": 0.4},
        "control": {"endpoint": -1e9, "movement": 1e9},
    }
    result = anchored_update(pi, pi, C, mu, control_tasks=["control"])
    temperature = result["temperature"]
    assert temperature["global_weighted_RMS"] == pytest.approx(1)
    assert temperature["noncontrol_total_mu"] == 0.5
    assert temperature["T_C"] == {"large": 0.4, "small": 0.1}
    assert result["pi_next"]["small"] == pytest.approx(result["pi_next"]["large"])
    assert result["pi_next"]["control"] == {"endpoint": 0.5, "movement": 0.5}
    control = result["task_diagnostics"]["control"]
    assert not control["optimized"] and control["T_C"] is None
    assert control["KL_next_to_current"] == control["TV_next_current"] == 0
    assert control["C"] == C["control"]


def test_all_zero_empirical_proxy_has_fixed_floor_and_uninformative_diagnostic():
    pi = {"x": {"a": 0.3, "b": 0.7}, "fixed": {"single": 1.0}}
    C = {"x": {"a": 0.0, "b": 0.0}, "fixed": {"single": 0.0}}
    result = anchored_update(pi, pi, C, {"x": 0.4, "fixed": 0.6}, control_tasks=["fixed"])
    assert result["temperature"]["global_weighted_RMS"] == 0
    assert result["temperature"]["T_C"]["x"] == 0.4e-8
    assert result["temperature"]["information_status"] == "UNINFORMATIVE_ZERO_EMPIRICAL_PROXY"
    assert not result["temperature"]["zero_proxy_proves_theoretical_Contribution_zero"]
    assert result["pi_next"]["x"] == pytest.approx(pi["x"])


def test_exact_update_matches_independent_torch_softmax_and_reports_both_KLs():
    pi = {"x": {"endpoint": 0.8, "movement": 0.2}}
    prior = {"x": {"endpoint": 0.5, "movement": 0.5}}
    result = anchored_update(pi, prior, {"x": centered(pi["x"])}, {"x": 1})
    row = result["task_diagnostics"]["x"]
    assert row["N"]["endpoint"] == 0
    assert row["N"]["movement"] == pytest.approx(math.log(2.5))
    logits = torch.tensor(
        [
            (4 * math.log(pi["x"][state]) + math.log(0.5) + row["log_Phi"][state]) / 5
            for state in ("endpoint", "movement")
        ],
        dtype=torch.float64,
    )
    expected = torch.softmax(logits, dim=0).tolist()
    assert list(row["pi_next"].values()) == pytest.approx(expected, abs=1e-15)
    for name, anchor in (("KL_next_to_current", pi["x"]), ("KL_next_to_prior", prior["x"])):
        calculated = sum(p * math.log(p / anchor[state]) for state, p in row["pi_next"].items())
        assert row[name] == pytest.approx(calculated, abs=1e-15)
    assert row["optimality_residual"] < 1e-12
    assert not result["probability_clipping_or_repair"]
    assert not result["true_task_utility_monotonicity_guaranteed"]


def test_frozen_potential_solution_maximizes_dual_KL_objective():
    pi = {"x": {"endpoint": 0.7, "movement": 0.3}}
    prior = {"x": {"endpoint": 0.5, "movement": 0.5}}
    result = anchored_update(pi, prior, {"x": centered(pi["x"])}, {"x": 1})
    row = result["task_diagnostics"]["x"]

    def objective(p):
        values = {"endpoint": 1 - p, "movement": p}
        return math.fsum(
            q * row["log_Phi"][state]
            - 4 * q * math.log(q / pi["x"][state])
            - q * math.log(q / prior["x"][state])
            for state, q in values.items()
        )

    optimum = row["pi_next"]["movement"]
    assert objective(optimum) == pytest.approx(row["frozen_potential_objective"])
    assert all(objective(p / 100) <= objective(optimum) + 1e-14 for p in range(1, 100))
    delta = 1e-6
    assert (objective(optimum + delta) - objective(optimum - delta)) / (2 * delta) == pytest.approx(
        0, abs=1e-8
    )


def synthetic_rounds(**kwargs):
    prior = {"x": {"endpoint": 0.5, "movement": 0.5}}
    pi = prior
    path = [0.5]
    for _ in range(2):
        result = anchored_update(pi, prior, {"x": centered(pi["x"])}, {"x": 1}, **kwargs)
        pi = result["pi_next"]
        path.append(pi["x"]["movement"])
    return path


def test_preserved_synthetic_small_epsilon_novelty_reversal_counterexample():
    actual = synthetic_rounds(epsilon=0.001, contribution_exponent=0.5, novelty_exponent=0.5)
    assert actual == pytest.approx([0.5, 0.52492, 0.44752], abs=2e-5)
    assert actual[1] > 0.5 and actual[2] < 0.5


def test_registered_parameters_avoid_that_specific_two_round_reversal_only():
    actual = synthetic_rounds()
    assert 0.5 < actual[1] < actual[2]


def test_no_probability_clipping_to_rescue_softmax_underflow():
    tiny = math.nextafter(0.0, 1.0)
    pi = {"x": {"rare": tiny, "common": 1.0}}
    C = {"x": {"rare": -1.0, "common": tiny}}
    with pytest.raises(ValueError, match="softmax_underflow_or_nonfinite_STOP_no_clipping"):
        anchored_update(
            pi, pi, C, {"x": 1}, epsilon=0.001, contribution_exponent=1, novelty_exponent=0
        )


def test_control_distribution_cannot_drift_from_its_original_prior():
    pi = {"x": {"a": 0.5, "b": 0.5}, "fixed": {"a": 0.6, "b": 0.4}}
    prior = {"x": pi["x"], "fixed": {"a": 0.5, "b": 0.5}}
    with pytest.raises(ValueError, match="control_current_equals_original_prior"):
        anchored_update(
            pi,
            prior,
            {"x": {"a": 0, "b": 0}, "fixed": {"a": 0, "b": 0}},
            {"x": 0.5, "fixed": 0.5},
            control_tasks=["fixed"],
        )


@pytest.mark.parametrize("bad", [0, -0.1, float("nan"), float("inf")])
def test_noninterior_or_nonfinite_mass_is_not_repaired(bad):
    pi = {"x": {"a": bad, "b": 1}}
    with pytest.raises(ValueError):
        anchored_update(pi, pi, {"x": {"a": 0, "b": 0}}, {"x": 1})


def test_uncentered_contribution_is_rejected():
    pi = {"x": {"a": 0.5, "b": 0.5}}
    with pytest.raises(ValueError, match="centered_Contribution_required"):
        anchored_update(pi, pi, {"x": {"a": 1, "b": 2}}, {"x": 1})


def test_temperature_floor_is_on_C_over_mu_not_each_T_C_independently():
    pi = {"a": {"z": 1.0}, "b": {"z": 1.0}}
    C = {"a": {"z": 0.0}, "b": {"z": 0.0}}
    result = contribution_temperatures(C, pi, {"a": 0.1, "b": 0.9})
    assert result["T_C"] == pytest.approx({"a": 1e-9, "b": 9e-9})
