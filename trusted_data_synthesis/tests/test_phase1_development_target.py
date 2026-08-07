from __future__ import annotations

import math

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_development_target import (
    cold_start_adamw_vjp,
    crossed_effect_summary,
    empirical_power_grid,
)


@pytest.mark.parametrize("maximum_gradient_norm", [10.0, 0.25])
def test_cold_start_adamw_vjp_matches_autograd(maximum_gradient_norm: float) -> None:
    torch = pytest.importorskip("torch")
    learning_rate = 2e-4
    epsilon = 1e-8
    flattened = torch.tensor(
        [0.4, -0.2, 0.1, -0.7, 0.3],
        dtype=torch.float64,
        requires_grad=True,
    )
    objective = torch.tensor([0.3, 0.5, -0.4, 0.2, -0.1], dtype=torch.float64)
    norm = torch.linalg.vector_norm(flattened)
    scale = torch.clamp(maximum_gradient_norm / norm, max=1.0)
    clipped = flattened * scale
    update = learning_rate * clipped / (clipped.abs() + epsilon)
    torch.sum(objective * update).backward()
    expected = flattened.grad.detach().clone()

    observed = cold_start_adamw_vjp(
        {"left": flattened.detach()[:3], "right": flattened.detach()[3:]},
        {"left": objective[:3], "right": objective[3:]},
        learning_rate=learning_rate,
        epsilon=epsilon,
        maximum_gradient_norm=maximum_gradient_norm,
        dtype=torch.float64,
    )
    combined = torch.cat((observed["left"], observed["right"]))
    assert torch.allclose(combined, expected, rtol=1e-9, atol=1e-12)


def test_crossed_effect_summary_separates_two_main_effects() -> None:
    objective_effects = {"m0": -1.0, "m1": 0.0, "m2": 1.0}
    realization_effects = {"r0": -0.5, "r1": 0.5}
    values = {
        (micro_split, realization): 2.0 + objective + realization_effects[realization]
        for micro_split, objective in objective_effects.items()
        for realization in realization_effects
    }
    summary = crossed_effect_summary(values)
    assert summary["mean"] == pytest.approx(2.0)
    assert summary["objective_variance"] == pytest.approx(1.0)
    assert summary["realization_variance"] == pytest.approx(0.5)
    assert summary["interaction_variance"] == pytest.approx(0.0, abs=1e-15)
    assert summary["standard_error"] == pytest.approx(math.sqrt(1.0 / 3.0 + 0.5 / 2.0))


def test_empirical_power_grid_is_deterministic_and_increases_with_support() -> None:
    first = empirical_power_grid(task_between_variance=1.0, measurement_variance=0.5)
    second = empirical_power_grid(task_between_variance=1.0, measurement_variance=0.5)
    assert first == second
    assert [row["task_count"] for row in first] == [30, 45, 50, 60, 80, 100]
    assert first[-1]["power"] > first[0]["power"]

