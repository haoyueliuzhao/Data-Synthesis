"""Synthetic CPU comparisons against actual torch.optim.AdamW and finite differences."""

import copy

import pytest
import torch

from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.optimizer_pullback import (
    aggregate_gradient,
    bind_adamw,
    centered_contributions,
    pullback,
    virtual_step,
    virtual_step_and_vjp,
)


def fixture(dtype, *, maximize=False, warmed=True, clip=0.4, foreach=False):
    named = {
        "left": torch.nn.Parameter(torch.tensor([0.7, -0.9], dtype=dtype)),
        "right": torch.nn.Parameter(torch.tensor([[0.2, 1.4]], dtype=dtype)),
    }
    optimizer = torch.optim.AdamW(
        [
            {
                "params": [named["left"]],
                "lr": 0.031,
                "betas": (0.8, 0.93),
                "eps": 0.07,
                "weight_decay": 0.13,
                "maximize": maximize,
            },
            {
                "params": [named["right"]],
                "lr": 0.019,
                "betas": (0.7, 0.88),
                "eps": 0.04,
                "weight_decay": 0.09,
                "maximize": maximize,
            },
        ],
        foreach=foreach,
    )
    if warmed:
        for index in range(3):
            named["left"].grad = torch.tensor([0.12 + index * 0.03, -0.24], dtype=dtype)
            named["right"].grad = torch.tensor([[0.31, -0.09 - index * 0.02]], dtype=dtype)
            optimizer.step()
        optimizer.zero_grad(set_to_none=True)
    binding = bind_adamw(named, optimizer, clip_max_norm=clip)
    return named, optimizer, binding


def torch_step(binding, gradient):
    clones = {p.name: torch.nn.Parameter(p.theta.clone()) for p in binding.parameters}
    groups = []
    for config in binding.groups:
        groups.append(
            {
                "params": [clones[name] for name in config["parameter_names"]],
                "lr": config["lr"],
                "betas": (config["beta1"], config["beta2"]),
                "eps": config["eps"],
                "weight_decay": config["weight_decay"],
                "maximize": config["maximize"],
                "foreach": config["foreach"],
            }
        )
    optimizer = torch.optim.AdamW(groups)
    for parameter in binding.parameters:
        optimizer.state[clones[parameter.name]] = {
            "step": torch.tensor(float(parameter.step)),
            "exp_avg": parameter.first.clone(),
            "exp_avg_sq": parameter.second.clone(),
        }
        clones[parameter.name].grad = gradient[parameter.name].clone()
    if binding.clip_max_norm is not None:
        torch.nn.utils.clip_grad_norm_(list(clones.values()), binding.clip_max_norm)
    optimizer.step()
    return {name: value.detach() for name, value in clones.items()}


def vector(dtype):
    return {
        "left": torch.tensor([0.7, -0.4], dtype=dtype),
        "right": torch.tensor([[0.3, 0.5]], dtype=dtype),
    }


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
@pytest.mark.parametrize("clip", [0.4, 2.0, None])
@pytest.mark.parametrize("maximize", [False, True])
@pytest.mark.parametrize("foreach", [False, True])
def test_virtual_step_matches_actual_torch_AdamW_without_mutating_real_state(
    dtype, clip, maximize, foreach
):
    named, optimizer, binding = fixture(dtype, maximize=maximize, clip=clip, foreach=foreach)
    before = {name: value.detach().clone() for name, value in named.items()}
    optimizer_before = copy.deepcopy(optimizer.state_dict())
    gradient = vector(dtype)
    original_gradient = {name: value.clone() for name, value in gradient.items()}
    virtual = virtual_step(binding, gradient)
    expected = torch_step(binding, gradient)
    for name in named:
        torch.testing.assert_close(
            virtual["theta_bar"][name],
            expected[name],
            rtol=2e-6 if dtype == torch.float32 else 1e-13,
            atol=2e-7 if dtype == torch.float32 else 1e-14,
        )
        assert torch.equal(named[name], before[name]) and named[name].grad is None
        assert torch.equal(gradient[name], original_gradient[name])
        assert virtual["theta_bar"][name].requires_grad and virtual["theta_bar"][name].is_leaf
    actual_state = optimizer.state_dict()
    assert actual_state["param_groups"] == optimizer_before["param_groups"]
    for index, fields in actual_state["state"].items():
        for key, value in fields.items():
            assert torch.equal(value, optimizer_before["state"][index][key])
    assert virtual["diagnostics"]["clipping_active"] == (clip == 0.4)


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
@pytest.mark.parametrize("clip", [0.4, 2.0])
@pytest.mark.parametrize("maximize", [False, True])
def test_population_pullback_matches_directional_finite_differences(dtype, clip, maximize):
    _, _, binding = fixture(dtype, maximize=maximize, clip=clip)
    gradient = vector(dtype)
    covector = {
        "left": torch.tensor([-0.3, 0.6], dtype=dtype),
        "right": torch.tensor([[0.8, -0.2]], dtype=dtype),
    }
    direction = {
        "left": torch.tensor([0.4, 0.3], dtype=dtype),
        "right": torch.tensor([[-0.2, 0.6]], dtype=dtype),
    }
    a = pullback(binding, gradient, covector)["a"]
    observed = sum((a[name] * direction[name]).double().sum().item() for name in a)
    delta = 0.003 if dtype == torch.float32 else 1e-6

    def objective(sign):
        G = {name: value + sign * delta * direction[name] for name, value in gradient.items()}
        update = virtual_step(binding, G)["update"]
        return sum(
            (covector[name].double() * value.double()).sum().item()
            for name, value in update.items()
        )

    numeric = (objective(1) - objective(-1)) / (2 * delta)
    assert observed == pytest.approx(
        numeric,
        abs=1e-5 if dtype == torch.float32 else 3e-10,
        rel=0.008 if dtype == torch.float32 else 2e-6,
    )


def test_utility_gradient_is_formed_at_virtual_theta_before_negative_pullback():
    _, _, binding = fixture(torch.float64)
    gradient = vector(torch.float64)
    virtual = virtual_step(binding, gradient)
    utility = sum((value.square()).sum() for value in virtual["theta_bar"].values())
    values = torch.autograd.grad(utility, tuple(virtual["theta_bar"].values()))
    gJ = dict(zip(virtual["theta_bar"], values, strict=True))
    actual = pullback(binding, gradient, {name: -value for name, value in gJ.items()})
    convenient = virtual_step_and_vjp(binding, gradient, gJ)
    for name in gJ:
        torch.testing.assert_close(actual["a"][name], convenient["a"][name])


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
def test_lazy_zero_moments_and_zero_gradient_have_correct_differentiable_limit(dtype):
    parameter = torch.nn.Parameter(torch.tensor([0.4], dtype=dtype))
    optimizer = torch.optim.AdamW([parameter], lr=0.1, eps=0.2, weight_decay=0.1)
    binding = bind_adamw({"p": parameter}, optimizer, clip_max_norm=1.0)
    zero = {"p": torch.zeros_like(parameter)}
    assert not optimizer.state
    virtual = virtual_step(binding, zero)
    a = pullback(binding, zero, {"p": torch.ones_like(parameter)})["a"]["p"]
    torch.testing.assert_close(a, torch.tensor([0.5], dtype=dtype))
    torch.testing.assert_close(virtual["theta_bar"]["p"], torch_step(binding, zero)["p"])
    assert not optimizer.state
    assert virtual["diagnostics"]["zero_second_moment_differentiable_limit_coordinates"] == 1


def test_zero_second_moment_with_nonzero_first_moment_is_rejected():
    named, optimizer, _ = fixture(torch.float64)
    optimizer.state[named["left"]]["exp_avg_sq"].zero_()
    binding = bind_adamw(named, optimizer, clip_max_norm=1.0)
    gradient = {name: torch.zeros_like(parameter) for name, parameter in named.items()}
    with pytest.raises(ValueError, match="zero_second_moment_nondifferentiable"):
        virtual_step(binding, gradient)


def test_float32_population_norm_underflow_is_explicitly_rejected():
    named, optimizer, _ = fixture(torch.float32, warmed=False)
    binding = bind_adamw(named, optimizer, clip_max_norm=1.0)
    with pytest.raises(ValueError, match="population_norm_underflow_STOP"):
        virtual_step(
            binding, {name: torch.full_like(parameter, 1e-30) for name, parameter in named.items()}
        )


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
def test_exact_PyTorch_clip_kink_is_rejected(dtype):
    parameter = torch.nn.Parameter(torch.tensor([1.0], dtype=dtype))
    optimizer = torch.optim.AdamW([parameter], eps=0.1)
    binding = bind_adamw({"p": parameter}, optimizer, clip_max_norm=1.0)
    with pytest.raises(ValueError, match="clip_boundary_nondifferentiable"):
        virtual_step(binding, {"p": torch.tensor([1 - 1e-6], dtype=dtype)})


@pytest.mark.parametrize("change", ["theta", "moments", "step", "config"])
def test_stale_actual_optimizer_binding_is_rejected(change):
    named, optimizer, binding = fixture(torch.float64)
    if change == "theta":
        with torch.no_grad():
            named["left"].add_(0.1)
    elif change == "moments":
        optimizer.state[named["left"]]["exp_avg"].add_(0.1)
    elif change == "step":
        optimizer.state[named["left"]]["step"].add_(1)
    else:
        optimizer.param_groups[0]["lr"] *= 2
    with pytest.raises(ValueError, match="stale_real_parameter_or_optimizer"):
        virtual_step(binding, vector(torch.float64))


def test_population_G_includes_controls_and_is_not_average_of_state_updates():
    parameter = torch.nn.Parameter(torch.tensor([0.2], dtype=torch.float64))
    optimizer = torch.optim.AdamW([parameter], lr=0.1, eps=0.01, weight_decay=0)
    binding = bind_adamw({"p": parameter}, optimizer, clip_max_norm=None)
    gradients = {
        "task": {
            "low": {"p": torch.tensor([-2.0], dtype=torch.float64)},
            "high": {"p": torch.tensor([1.0], dtype=torch.float64)},
        },
        "control": {"fixed": {"p": torch.tensor([2.0], dtype=torch.float64)}},
    }
    pi = {"task": {"low": 0.5, "high": 0.5}, "control": {"fixed": 1.0}}
    mu = {"task": 0.8, "control": 0.2}
    G = aggregate_gradient(gradients, pi, mu)
    torch.testing.assert_close(G["p"], torch.zeros(1, dtype=torch.float64), atol=1e-15, rtol=0)
    correct = virtual_step(binding, G)["update"]["p"]
    wrong = sum(
        mu[task] * pi[task][state] * virtual_step(binding, gradient)["update"]["p"]
        for task, states in gradients.items()
        for state, gradient in states.items()
    )
    assert (correct - wrong).abs().item() > 0.01
    C = centered_contributions(gradients, pi, mu, {"p": torch.ones_like(parameter)})
    assert C["C"]["task"] == pytest.approx({"low": -1.2, "high": 1.2})
    assert C["C"]["control"]["fixed"] == 0
    assert all(abs(value) < 1e-14 for value in C["center_residuals"].values())


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
def test_zero_gradient_inside_active_tiny_clip_has_correct_derivative_limit(dtype):
    parameter = torch.nn.Parameter(torch.tensor([0.4], dtype=dtype))
    optimizer = torch.optim.AdamW([parameter], lr=0.1, eps=0.2, weight_decay=0)
    binding = bind_adamw({"p": parameter}, optimizer, clip_max_norm=5e-7)
    G = {"p": torch.zeros_like(parameter)}
    actual = virtual_step(binding, G)
    assert actual["diagnostics"]["clipping_active"]
    assert actual["diagnostics"]["clip_coefficient"] == pytest.approx(0.5)
    a = pullback(binding, G, {"p": torch.ones_like(parameter)})["a"]["p"]
    torch.testing.assert_close(a, torch.tensor([0.25], dtype=dtype))
    torch.testing.assert_close(actual["theta_bar"]["p"], torch_step(binding, G)["p"])


def test_underflowed_second_moment_coordinate_even_with_nonzero_global_norm_is_rejected():
    named, optimizer, _ = fixture(torch.float32, warmed=False)
    binding = bind_adamw(named, optimizer, clip_max_norm=1)
    G = vector(torch.float32)
    G["left"][0] = 1e-30
    with pytest.raises(ValueError, match="zero_second_moment_nondifferentiable_or_underflow"):
        virtual_step(binding, G)


def test_float32_step_counter_that_cannot_advance_is_rejected():
    named, optimizer, _ = fixture(torch.float64)
    optimizer.state[named["left"]]["step"] = torch.tensor(float(2**24), dtype=torch.float32)
    with pytest.raises(ValueError, match="step_increment_rounding_STOP"):
        bind_adamw(named, optimizer, clip_max_norm=1)


@pytest.mark.parametrize("change", ["tensor", "metadata"])
def test_internal_binding_snapshot_tampering_is_rejected(change):
    _, _, binding = fixture(torch.float64)
    if change == "tensor":
        binding.parameters[0].first.add_(0.1)
    else:
        binding.snapshot["torch_version"] = "forged"
    with pytest.raises(ValueError, match="snapshot_tensors_modified|content_identity"):
        virtual_step(binding, vector(torch.float64))


def test_population_accepts_exact_Fraction_strings_without_changing_inputs():
    gradients = {
        "x": {
            "a": {"p": torch.tensor([1.0], dtype=torch.float64)},
            "b": {"p": torch.tensor([3.0], dtype=torch.float64)},
        }
    }
    pi, mu = {"x": {"a": "1/4", "b": "3/4"}}, {"x": "1/1"}
    actual = aggregate_gradient(gradients, pi, mu)
    assert actual["p"].item() == 2.5
    C = centered_contributions(gradients, pi, mu, {"p": torch.ones_like(actual["p"])})
    assert C["C"] == {"x": {"a": -1.5, "b": 0.5}}
    assert pi == {"x": {"a": "1/4", "b": "3/4"}}


def test_preexisting_real_grad_buffers_remain_bitwise_unchanged():
    named, _, binding = fixture(torch.float64)
    for value in named.values():
        value.grad = torch.full_like(value, 0.8125)
    before = {name: value.grad.clone() for name, value in named.items()}
    G = vector(torch.float64)
    virtual_step(binding, G)
    pullback(binding, G, G)
    assert all(torch.equal(value.grad, before[name]) for name, value in named.items())
