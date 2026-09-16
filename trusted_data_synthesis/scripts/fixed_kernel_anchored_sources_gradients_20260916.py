"""Current-original full-class gradients in host RAM, not per-class optimizer steps.

One additional dropout-free pass builds g_xz. G includes control tasks and is
formed once at current pi. All losses use complete original target masks and
whole-package denominators. This is extra proxy work, never one of ten SFT epochs.
The roughly 16 GiB A matrix stays in host RAM; no per-round giant disk artifact.
"""

import math
from collections import Counter
from contextlib import nullcontext
from dataclasses import dataclass
from fractions import Fraction

import torch
from fixed_kernel_anchored_sources_gpu_gate_20260916 import proxy_mode
from fixed_kernel_anchored_sources_state_20260916 import target_coefficient
from torch.nn.attention import SDPBackend, sdpa_kernel

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import trajectory_materials
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.trajectory_consumer import (
    selected_target_loss,
)


def mass(value):
    return float(Fraction(str(value)))


def validate_support(keys, pi, mu):
    expected = {(task, state) for task, states in pi.items() for state in states}
    p.require(set(keys) == expected and set(pi) == set(mu), "anchored_classes.exact_support")
    for states in pi.values():
        values = [mass(value) for value in states.values()]
        p.require(
            all(math.isfinite(value) and value > 0 for value in values)
            and math.isclose(math.fsum(values), 1, rel_tol=0, abs_tol=1e-12),
            "anchored_classes.interior_simplex",
        )
    values = [mass(value) for value in mu.values()]
    p.require(
        all(math.isfinite(value) and value > 0 for value in values)
        and math.isclose(math.fsum(values), 1, rel_tol=0, abs_tol=1e-12),
        "anchored_classes.task_marginals",
    )


@dataclass
class PopulationGradients:
    keys: tuple
    names: tuple
    shapes: tuple
    matrix: torch.Tensor
    G: dict
    accounting: dict

    def centered(self, pi, mu, a, *, block_rows=8):
        validate_support(self.keys, pi, mu)
        p.require(set(a) == set(self.names), "anchored_classes.complete_pullback_vector")
        flattened = torch.cat([a[name].detach().cpu().reshape(-1).double() for name in self.names])
        p.require(
            flattened.numel() == self.matrix.shape[1] and bool(torch.isfinite(flattened).all()),
            "anchored_classes.finite_pullback",
        )
        dots = {}
        # FP64 dot products; bounded temporary buffers, no second full matrix.
        for start in range(0, len(self.keys), block_rows):
            values = self.matrix[start : start + block_rows].double().mv(flattened).tolist()
            dots.update(zip(self.keys[start : start + block_rows], values, strict=True))
        result, residuals = {}, {}
        for task, states in pi.items():
            average = math.fsum(mass(value) * dots[task, state] for state, value in states.items())
            result[task] = {
                state: mass(mu[task]) * (dots[task, state] - average) for state in states
            }
            residuals[task] = math.fsum(
                mass(states[state]) * value for state, value in result[task].items()
            )
            p.require(
                abs(residuals[task]) <= 1e-10 * max(1.0, *(abs(v) for v in result[task].values()))
                and all(math.isfinite(v) for v in result[task].values()),
                "anchored_classes.finite_centered_Contribution",
            )
        return p.record(
            "anchored_sources_centered_Contribution",
            C=result,
            centering_residuals=residuals,
            formula="mu(x) <DU(G)^T(-gJ), g_xz - sum_z pi(z|x) g_xz>",
            exact_greedy_or_multistep_derivative=False,
            class_storage="CPU FP32; same full current LoRA coordinates; FP64 dot products",
        )


def _compute(model, cache, pi, mu, *, event_sink=None):
    """Numerical body; production callers must enter through population_gradients."""
    parameters = {name: value for name, value in model.named_parameters() if value.requires_grad}
    p.require(
        parameters and all(value.dtype == torch.float32 for value in parameters.values()),
        "anchored_classes.FP32_current_LoRA_coordinates",
    )
    device = next(iter(parameters.values())).device
    p.require(
        all(value.device == device for value in parameters.values()),
        "anchored_classes.one_real_device",
    )
    counts = Counter((row["task_id"], row["state_id"]) for row in cache.packages)
    keys = tuple(sorted(counts))
    validate_support(keys, pi, mu)
    indices = {key: index for index, key in enumerate(keys)}
    names, shapes = tuple(parameters), tuple(value.shape for value in parameters.values())
    sizes = [value.numel() for value in parameters.values()]
    matrix = torch.zeros((len(keys), sum(sizes)), dtype=torch.float32, device="cpu")
    package_count = segment_count = target_count = sequence_count = 0
    real_versions = [(value.data_ptr(), value._version) for value in parameters.values()]
    old_grads = [
        None if value.grad is None else (value.grad.data_ptr(), value.grad._version)
        for value in parameters.values()
    ]
    emit = event_sink or (lambda event: None)
    cuda_rng_devices = [device.index or 0] if device.type == "cuda" else []
    with torch.random.fork_rng(devices=cuda_rng_devices), proxy_mode(model, gradient=True):
        for package in cache.packages:  # exact existing physical package order
            key = package["task_id"], package["state_id"]
            coefficient = 1.0 / (counts[key] * package["whole_package_target_tokens"])
            for row in cache.row_arrays(package["package_id"]):
                ids = torch.tensor(row["input_ids"], dtype=torch.long, device=device)[None, :]
                positions = (
                    torch.tensor(row["target_positions"], dtype=torch.long, device=device) - 1
                )
                targets = torch.tensor(row["target_ids"], dtype=torch.long, device=device)
                context = (
                    sdpa_kernel(SDPBackend.FLASH_ATTENTION)
                    if device.type == "cuda"
                    else nullcontext()
                )
                with context:
                    logits = model(
                        input_ids=ids,
                        attention_mask=torch.ones_like(ids),
                        use_cache=False,
                        logits_to_keep=positions,
                    ).logits
                    loss = selected_target_loss(logits, targets, coefficient)
                    derivatives = torch.autograd.grad(
                        loss, tuple(parameters.values()), allow_unused=True
                    )
                flat = torch.cat(
                    [
                        (torch.zeros_like(parameter) if value is None else value)
                        .detach()
                        .reshape(-1)
                        for parameter, value in zip(parameters.values(), derivatives, strict=True)
                    ]
                ).cpu()
                matrix[indices[key]].add_(flat)
                segment_count += 1
                target_count += len(targets)
                sequence_count += ids.numel()
                del flat, derivatives, logits, loss, ids, positions, targets
            package_count += 1
            emit(
                dict(
                    event="class_package_gradient",
                    completed_packages=package_count,
                    package_id=package["package_id"],
                )
            )
    aggregate = torch.zeros(matrix.shape[1], dtype=torch.float32)
    for key in keys:
        aggregate.add_(matrix[indices[key]], alpha=mass(mu[key[0]]) * mass(pi[key[0]][key[1]]))
    p.require(bool(torch.isfinite(aggregate).all()), "anchored_classes.finite_full_G")
    p.require(
        real_versions == [(value.data_ptr(), value._version) for value in parameters.values()]
        and old_grads
        == [
            None if value.grad is None else (value.grad.data_ptr(), value.grad._version)
            for value in parameters.values()
        ],
        "anchored_classes.no_real_parameter_or_grad_mutation",
    )
    G = {
        name: value.reshape(shape).to(device)
        for name, shape, value in zip(names, shapes, aggregate.split(sizes), strict=True)
    }
    return PopulationGradients(
        keys,
        names,
        shapes,
        matrix,
        G,
        dict(
            packages=package_count,
            segments=segment_count,
            target_tokens=target_count,
            sequence_tokens=sequence_count,
            states=len(keys),
            trainable_coordinates=sum(sizes),
            class_matrix_host_bytes=matrix.numel() * matrix.element_size(),
            actual_inner_optimizer_updates=0,
            extra_SFT_equivalent_material_passes=1,
            control_tasks_in_G=True,
            pi_applied_in_class_loss=False,
            current_pi_applied_once_in_G=True,
        ),
    )


def admit(cache, binding):
    trajectory_materials.require_pool(cache)
    p.checked(binding, "anchored_sources_material_binding")
    p.require(
        binding["cache_id"] == cache.cache_id
        and [row["package_id"] for row in binding["package_mappings"]]
        == [row["package_id"] for row in cache.packages],
        "anchored_classes.bound_all_original_packages_in_order",
    )


def population_gradients(model, cache, binding, pi, *, event_sink=None):
    admit(cache, binding)
    return _compute(model, cache, pi, binding["mu"], event_sink=event_sink)


def training_examples(cache, binding, pi):
    """Once per pi update, not per batch; the old inner consumer stays unchanged."""
    admit(cache, binding)
    counts = Counter((row["task_id"], row["state_id"]) for row in cache.packages)
    validate_support(counts, pi, binding["mu"])
    examples = []
    for row in cache.packages:
        task, state = row["task_id"], row["state_id"]
        coefficient = target_coefficient(
            pi[task][state], counts[task, state], row["whole_package_target_tokens"]
        )
        examples.append(
            {
                **row,
                "target_token_coefficient": str(coefficient),
                "coefficient_float": float(coefficient),
            }
        )
    return examples
