"""A frozen AdamW population step and its analytic clip-aware pullback.

This is a one-step proxy at the full population gradient, not the next real
mini-batch step or a multi-step utility derivative. Supported parameters and
moments are dense FP32/FP64 tensors. All real parameters, optimizer state and
configuration remain unchanged. Clipping is the global PyTorch L2 rule.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

import torch

from .protocol import checked_record, record, require, sha


def _tensor_record(value):
    raw = value.detach().cpu().contiguous()
    return {
        "shape": list(raw.shape),
        "dtype": str(raw.dtype),
        "device": str(value.device),
        "sha256": sha(raw.reshape(-1).view(torch.uint8).numpy().tobytes()),
    }


def _number(value, name):
    require(type(value) in (int, float) and math.isfinite(value), "adamw.scalar:" + name)
    return float(value)


@dataclass(frozen=True)
class _Parameter:
    name: str
    live: torch.Tensor
    theta: torch.Tensor
    first: torch.Tensor
    second: torch.Tensor
    step: int
    group: int


@dataclass(frozen=True)
class AdamWBinding:
    snapshot: dict
    parameters: tuple
    groups: tuple
    optimizer: torch.optim.AdamW
    clip_max_norm: float | None
    clip_epsilon: float


def _capture(named_parameters, optimizer, clip_max_norm, clip_epsilon):
    require(type(optimizer) is torch.optim.AdamW, "adamw.exact_torch_AdamW_required")
    named = (
        dict(named_parameters)
        if not isinstance(named_parameters, Mapping)
        else dict(named_parameters)
    )
    require(
        named and all(isinstance(name, str) and name for name in named), "adamw.named_parameters"
    )
    require(len({id(value) for value in named.values()}) == len(named), "adamw.unique_parameters")
    by_identity = {id(value): name for name, value in named.items()}
    parameters, groups, metadata = [], [], []
    encountered = set()
    for group_index, group in enumerate(optimizer.param_groups):
        require(not group.get("amsgrad", False), "adamw.amsgrad_not_in_registered_proxy")
        require(
            not group.get("differentiable", False), "adamw.differentiable_optimizer_not_supported"
        )
        require(not group.get("capturable", False), "adamw.capturable_optimizer_not_supported")
        require(not group.get("fused", False), "adamw.fused_kernel_not_CPU_validated")
        beta1, beta2 = group["betas"]
        config = {
            "lr": _number(group["lr"], "lr"),
            "beta1": _number(beta1, "beta1"),
            "beta2": _number(beta2, "beta2"),
            "eps": _number(group["eps"], "eps"),
            "weight_decay": _number(group["weight_decay"], "weight_decay"),
            "maximize": bool(group.get("maximize", False)),
            "foreach": group.get("foreach"),
            "fused": group.get("fused"),
            "capturable": bool(group.get("capturable", False)),
            "differentiable": bool(group.get("differentiable", False)),
            "amsgrad": bool(group.get("amsgrad", False)),
        }
        require(
            config["lr"] >= 0
            and config["eps"] > 0
            and config["weight_decay"] >= 0
            and 0 <= config["beta1"] < 1
            and 0 <= config["beta2"] < 1,
            "adamw.supported_group_hyperparameters",
        )
        groups.append(config)
        names = []
        for parameter in group["params"]:
            identity = id(parameter)
            require(
                identity in by_identity and identity not in encountered,
                "adamw.exact_optimizer_parameter_set",
            )
            encountered.add(identity)
            name = by_identity[identity]
            require(
                parameter.dtype in (torch.float32, torch.float64)
                and parameter.layout == torch.strided
                and parameter.numel() > 0
                and bool(torch.isfinite(parameter).all()),
                "adamw.dense_finite_FP32_or_FP64",
            )
            state = optimizer.state.get(parameter, {})
            if state:
                require(
                    set(state) == {"step", "exp_avg", "exp_avg_sq"},
                    "adamw.exact_supported_state_fields",
                )
                raw_step = state["step"]
                require(
                    isinstance(raw_step, torch.Tensor)
                    and raw_step.numel() == 1
                    and raw_step.dtype in (torch.float32, torch.float64),
                    "adamw.actual_supported_scalar_step_tensor",
                )
                step_value = raw_step.detach().item()
                require(
                    type(step_value) in (int, float)
                    and math.isfinite(step_value)
                    and step_value >= 0
                    and step_value == int(step_value),
                    "adamw.nonnegative_integer_step",
                )
                step = int(step_value)
                require(
                    (raw_step.detach() + 1).item() == step + 1,
                    "adamw.step_increment_rounding_STOP",
                )
                first, second = state["exp_avg"], state["exp_avg_sq"]
                for moment in (first, second):
                    require(
                        isinstance(moment, torch.Tensor)
                        and moment.shape == parameter.shape
                        and moment.dtype == parameter.dtype
                        and moment.device == parameter.device
                        and moment.layout == torch.strided
                        and bool(torch.isfinite(moment).all()),
                        "adamw.actual_moment_shape_dtype_device",
                    )
                require(bool((second >= 0).all()), "adamw.nonnegative_second_moment")
            else:
                step = 0
                first, second = torch.zeros_like(parameter), torch.zeros_like(parameter)
            parameters.append(
                _Parameter(
                    name,
                    parameter,
                    parameter.detach().clone(),
                    first.detach().clone(),
                    second.detach().clone(),
                    step,
                    group_index,
                )
            )
            names.append(name)
            metadata.append(
                {
                    "name": name,
                    "group": group_index,
                    "step": step,
                    "step_storage": _tensor_record(state["step"]) if state else None,
                    "state_initialized": bool(state),
                    "parameter": _tensor_record(parameter),
                    "first_moment": _tensor_record(first),
                    "second_moment": _tensor_record(second),
                }
            )
        config["parameter_names"] = names
    require(encountered == set(by_identity), "adamw.all_named_parameters_in_optimizer")
    require(
        len({(p.theta.device, p.theta.dtype) for p in parameters}) == 1,
        "adamw.single_dtype_device_for_registered_global_clip",
    )
    snapshot = record(
        "optimizer_binding",
        optimizer_type="torch.optim.AdamW",
        parameters=metadata,
        groups=groups,
        clip={
            "max_norm": clip_max_norm,
            "norm_type": 2.0,
            "epsilon": clip_epsilon,
            "authority": "caller-supplied frozen actual training clipping configuration",
        },
        torch_version=str(torch.__version__),
        all_supplied_gradients_are_dense_not_None=True,
        raw_parameters_or_optimizer_mutated=False,
    )
    return tuple(parameters), tuple(groups), snapshot


def bind_adamw(named_parameters, optimizer, *, clip_max_norm, clip_epsilon=1e-6):
    """Snapshot the actual optimizer, including lazy zero moments and per-parameter steps."""
    if clip_max_norm is not None:
        clip_max_norm = _number(clip_max_norm, "clip_max_norm")
        require(clip_max_norm > 0, "adamw.positive_clip_limit")
    require(clip_epsilon == 1e-6, "adamw.PyTorch_clip_epsilon")
    parameters, groups, snapshot = _capture(
        named_parameters, optimizer, clip_max_norm, clip_epsilon
    )
    return AdamWBinding(snapshot, parameters, groups, optimizer, clip_max_norm, clip_epsilon)


def _verify(binding):
    require(isinstance(binding, AdamWBinding), "adamw.actual_binding_required")
    checked_record(binding.snapshot, "optimizer_binding")
    _, _, current = _capture(
        {p.name: p.live for p in binding.parameters},
        binding.optimizer,
        binding.clip_max_norm,
        binding.clip_epsilon,
    )
    require(current == binding.snapshot, "adamw.stale_real_parameter_or_optimizer_binding")
    for parameter in binding.parameters:
        original = next(
            row for row in binding.snapshot["parameters"] if row["name"] == parameter.name
        )
        require(
            _tensor_record(parameter.theta) == original["parameter"]
            and _tensor_record(parameter.first) == original["first_moment"]
            and _tensor_record(parameter.second) == original["second_moment"],
            "adamw.snapshot_tensors_modified",
        )
    require(list(binding.groups) == binding.snapshot["groups"], "adamw.snapshot_groups_modified")


def _vector(binding, vector, label):
    require(
        isinstance(vector, Mapping) and set(vector) == {p.name for p in binding.parameters},
        "adamw.complete_named_vector:" + label,
    )
    for parameter in binding.parameters:
        value = vector[parameter.name]
        require(
            isinstance(value, torch.Tensor)
            and value.shape == parameter.theta.shape
            and value.dtype == parameter.theta.dtype
            and value.device == parameter.theta.device
            and value.layout == torch.strided
            and bool(torch.isfinite(value).all()),
            "adamw.bound_vector_shape_dtype_device:" + label,
        )


def _clip(binding, gradient):
    values = [gradient[p.name].detach() for p in binding.parameters]
    norm = torch.linalg.vector_norm(
        torch.stack([torch.linalg.vector_norm(value, 2.0) for value in values]), 2.0
    )
    norm_value = float(norm.item())
    require(math.isfinite(norm_value), "adamw.finite_population_gradient_norm")
    require(
        norm_value != 0 or not any(bool((value != 0).any()) for value in values),
        "adamw.population_norm_underflow_STOP",
    )
    if binding.clip_max_norm is None:
        coefficient, active = torch.ones_like(norm), False
    else:
        ratio = binding.clip_max_norm / (norm + binding.clip_epsilon)
        boundary_tolerance = (
            8
            * torch.finfo(norm.dtype).eps
            * max(binding.clip_max_norm, norm_value + binding.clip_epsilon)
        )
        require(
            abs(norm_value + binding.clip_epsilon - binding.clip_max_norm) > boundary_tolerance,
            "adamw.clip_boundary_nondifferentiable_STOP",
        )
        active = bool(ratio < 1)
        coefficient = torch.clamp(ratio, max=1.0)
    clipped = {
        parameter.name: value * coefficient
        for parameter, value in zip(binding.parameters, values, strict=True)
    }
    return clipped, norm, coefficient, active


def _evaluate(binding, gradient):
    _verify(binding)
    _vector(binding, gradient, "population_G")
    clipped, norm, coefficient, active = _clip(binding, gradient)
    theta_bar, update, derivatives = {}, {}, {}
    zero_limit_coordinates = 0
    for parameter in binding.parameters:
        config = binding.groups[parameter.group]
        sign = -1.0 if config["maximize"] else 1.0
        h = clipped[parameter.name] * sign
        first = torch.lerp(parameter.first, h, 1 - config["beta1"])
        second = torch.addcmul(parameter.second * config["beta2"], h, h, value=1 - config["beta2"])
        step = parameter.step + 1
        correction1 = 1 - config["beta1"] ** step
        correction2_sqrt = (1 - config["beta2"] ** step) ** 0.5
        step_size = config["lr"] / correction1
        square_root = second.sqrt()
        denominator = square_root / correction2_sqrt + config["eps"]
        virtual = torch.addcdiv(
            parameter.theta * (1 - config["lr"] * config["weight_decay"]),
            first,
            denominator,
            value=-step_size,
        )
        zero = square_root == 0
        require(
            not bool((zero & ((h != 0) | (first != 0))).any()),
            "adamw.zero_second_moment_nondifferentiable_or_underflow_STOP",
        )
        safe_root = torch.where(zero, torch.ones_like(square_root), square_root)
        denominator_derivative = (1 - config["beta2"]) * h / (safe_root * correction2_sqrt)
        derivative = (
            step_size
            * (
                (1 - config["beta1"]) / denominator
                - first * denominator_derivative / denominator.square()
            )
            * sign
        )
        # At h=m=v=0, h/(|h|+eps) has derivative 1/eps. The expression above
        # uses that exact limit, rather than differentiating sqrt(0) as 0/0.
        zero_limit_coordinates += int(zero.sum().item())
        require(
            bool(torch.isfinite(virtual).all()) and bool(torch.isfinite(derivative).all()),
            "adamw.finite_virtual_step_and_derivative",
        )
        theta_bar[parameter.name] = virtual.detach().clone().requires_grad_(True)
        update[parameter.name] = (parameter.theta - virtual).detach()
        derivatives[parameter.name] = derivative.detach()
    diagnostics = record(
        "virtual_population_step",
        optimizer_binding_id=binding.snapshot["id"],
        aggregate_gradient={p.name: _tensor_record(gradient[p.name]) for p in binding.parameters},
        global_gradient_norm=norm.item(),
        clip_coefficient=coefficient.item(),
        clipping_active=active,
        zero_second_moment_differentiable_limit_coordinates=zero_limit_coordinates,
        real_parameters_optimizer_unchanged=True,
        scope=(
            "full-population aggregate gradient virtual one-step, "
            "not next real minibatch or multistep utility derivative"
        ),
    )
    return theta_bar, update, derivatives, norm, coefficient, active, diagnostics


def virtual_step(binding, G):
    """Compute theta_bar first, before any stochastic utility probes exist."""
    theta, update, _, _, _, _, diagnostics = _evaluate(binding, G)
    return {"theta_bar": theta, "update": update, "diagnostics": diagnostics}


def pullback(binding, G, g_v):
    """Compute DU(G)^T g_v; the Contribution caller supplies g_v=-g_J."""
    _vector(binding, g_v, "utility_covector_g_v")
    _, _, diagonal, norm, coefficient, active, step = _evaluate(binding, G)
    scaled = {p.name: diagonal[p.name] * g_v[p.name].detach() for p in binding.parameters}
    if active and norm.item() != 0:
        dot = sum((scaled[p.name] * G[p.name].detach()).sum() for p in binding.parameters)
        radial = dot / (norm * (norm + binding.clip_epsilon))
        answer = {
            p.name: coefficient * (scaled[p.name] - radial * G[p.name].detach())
            for p in binding.parameters
        }
    else:
        answer = {p.name: coefficient * scaled[p.name] for p in binding.parameters}
    require(
        all(bool(torch.isfinite(value).all()) for value in answer.values()), "adamw.finite_pullback"
    )
    return {
        "a": answer,
        "diagnostics": record(
            "optimizer_pullback",
            virtual_step_id=step["id"],
            optimizer_binding_id=binding.snapshot["id"],
            covector={name: _tensor_record(value) for name, value in g_v.items()},
            formula="a = DU(G)^T g_v; caller g_v = -g_J",
            clipping_jacobian_at_population_G=True,
            per_state_virtual_updates_averaged=False,
            real_parameters_optimizer_unchanged=True,
        ),
    }


def virtual_step_and_vjp(binding, G, g_J):
    """Convenience helper when a same-virtual-point utility gradient is already available."""
    value = virtual_step(binding, G)
    derivative = pullback(binding, G, {name: -tensor for name, tensor in g_J.items()})
    return {**value, "a": derivative["a"], "pullback_diagnostics": derivative["diagnostics"]}


def _mass(value):
    require(not isinstance(value, bool), "contribution.mass_not_boolean")
    try:
        number = float(Fraction(value)) if isinstance(value, str) else float(value)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError) as error:
        raise ValueError("contribution.finite_mass") from error
    require(math.isfinite(number), "contribution.finite_mass")
    return number


def _population(state_gradients, pi, mu):
    require(
        state_gradients and set(state_gradients) == set(pi) == set(mu),
        "contribution.task_population",
    )
    require(
        all(math.isfinite(_mass(value)) and _mass(value) > 0 for value in mu.values())
        and math.isclose(math.fsum(map(_mass, mu.values())), 1.0, rel_tol=0, abs_tol=1e-12),
        "contribution.task_marginals",
    )
    require(all(state_gradients.values()), "contribution.nonempty_state_support")
    first = next(iter(next(iter(state_gradients.values())).values()))
    require(isinstance(first, Mapping) and first, "contribution.named_state_gradient")
    require(
        all(
            isinstance(value, torch.Tensor)
            and value.dtype in (torch.float32, torch.float64)
            and value.layout == torch.strided
            and bool(torch.isfinite(value).all())
            for value in first.values()
        ),
        "contribution.dense_finite_FP32_or_FP64_gradients",
    )
    for task, states in state_gradients.items():
        require(states and set(states) == set(pi[task]), "contribution.state_support")
        require(
            all(math.isfinite(_mass(p)) and _mass(p) > 0 for p in pi[task].values())
            and math.isclose(
                math.fsum(map(_mass, pi[task].values())), 1.0, rel_tol=0, abs_tol=1e-12
            ),
            "contribution.interior_distribution",
        )
        for gradient in states.values():
            require(set(gradient) == set(first), "contribution.complete_parameter_gradient")
            for name, value in gradient.items():
                reference = first[name]
                require(
                    isinstance(value, torch.Tensor)
                    and value.shape == reference.shape
                    and value.dtype == reference.dtype
                    and value.device == reference.device
                    and bool(torch.isfinite(value).all()),
                    "contribution.gradient_shape_dtype_device",
                )
    return first


def aggregate_gradient(state_gradients, pi, mu):
    """G=sum_x mu(x)sum_z pi(z|x)g[x,z], including every control task."""
    first = _population(state_gradients, pi, mu)
    result = {name: torch.zeros_like(value) for name, value in first.items()}
    for task in sorted(state_gradients):
        for state in sorted(state_gradients[task]):
            for name, value in state_gradients[task][state].items():
                result[name].add_(value.detach(), alpha=_mass(mu[task]) * _mass(pi[task][state]))
    return result


def centered_contributions(state_gradients, pi, mu, a):
    """Return centered mu-weighted one-step random-trajectory Contribution proxies."""
    first = _population(state_gradients, pi, mu)
    require(set(a) == set(first), "contribution.complete_pullback")
    scores, residuals = {}, {}
    for task, states in state_gradients.items():
        dots = {}
        for state, gradient in states.items():
            terms = []
            for name, value in gradient.items():
                require(
                    a[name].shape == value.shape
                    and a[name].dtype == value.dtype
                    and a[name].device == value.device
                    and bool(torch.isfinite(a[name]).all()),
                    "contribution.pullback_shape_dtype_device",
                )
                terms.append((a[name].detach().double() * value.detach().double()).sum().item())
            dots[state] = math.fsum(terms)
        mean = math.fsum(_mass(pi[task][state]) * value for state, value in dots.items())
        scores[task] = {state: _mass(mu[task]) * (value - mean) for state, value in dots.items()}
        residuals[task] = math.fsum(
            _mass(pi[task][state]) * value for state, value in scores[task].items()
        )
        require(
            abs(residuals[task]) <= 1e-10 * max(1.0, *(abs(v) for v in scores[task].values())),
            "contribution.centering_residual",
        )
    return {
        "C": scores,
        "center_residuals": residuals,
        "diagnostics": record(
            "centered_contribution_proxy",
            C=scores,
            center_residuals=residuals,
            formula="mu(x) <a, g_xz - sum_z pi(z|x) g_xz>",
            proxy_name="one-step stochastic full-trajectory-feedback Contribution proxy",
            exact_multistep_or_greedy_utility_derivative=False,
            gradients_or_real_parameters_modified=False,
        ),
    }
