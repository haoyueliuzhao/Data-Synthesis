"""State-weighted consumption of every original row, package and heldout identity.

The historical alpha-only kernel is unchanged. This module validates a distinct
state coefficient and provides a CPU-verified full 64-package accumulator; it
does not claim that its production Qwen/GPU execution has been validated.
"""

import copy
import math
from collections import Counter
from fractions import Fraction

import torch

from ..finance_qa_vnext_basis_scale_preparation import design
from ..finance_qa_vnext_basis_student.kernel import validate_row
from ..finance_qa_vnext_eval_readiness import materials
from ..finance_qa_vnext_pq_student.loss import selected_target_loss
from .protocol import encode, record, require, sha
from .state_catalog import validate_catalog, validate_state_support

MASS_TOLERANCE = Fraction(1, 10**12)


def policy():
    return record(
        "state_material_policy",
        coefficient="pi(z|x)/(5*n_train(x,z)*whole_package_target_tokens)",
        original_all_train_packages_consumed=True,
        heldout_packages_preserved_not_trained=True,
        original_row_bytes_order_and_tokenizer_unchanged=True,
        re_tokenization=False,
        initial_pushforward_recovers_alpha0_exactly=True,
        updated_float_probability_mass_tolerance="1e-12",
        posthoc_probability_clipping_or_renormalization=False,
        old_alpha_kernel_assertions_modified=False,
        CPU_complete_step_controls_only=True,
        production_Qwen_GPU_validation="NOT_EXECUTED_NOT_ADMITTED",
    )


def _fraction(value):
    require(
        not isinstance(value, bool) and isinstance(value, (str, int, float, Fraction)),
        "state_weights.finite_probability_scalar",
    )
    result = Fraction(str(value))
    require(result > 0, "state_weights.strictly_positive_original_support")
    return result


def initial_distribution(catalog, *, pool):
    require(pool in {"A", "B"}, "state_weights.registered_pool")
    return {
        row["task_id"]: {state["state_id"]: state["pi0"] for state in row["states"]}
        for row in catalog["task_support"]
        if row["pool"] == pool
    }


def validate_distribution(catalog, distribution, *, pool):
    validate_state_support(catalog)
    require(
        catalog["status"] == "READY_STATE_TRAIN_SUPPORT",
        "state_weights.full_original_train_kernel_ready",
    )
    support = {row["task_id"]: row for row in catalog["task_support"] if row["pool"] == pool}
    require(
        isinstance(distribution, dict) and set(distribution) == set(support),
        "state_weights.exact_pool_task_support",
    )
    checked, residuals = {}, {}
    for task, row in support.items():
        require(
            row["train_pending"] == 0
            and isinstance(distribution[task], dict)
            and set(distribution[task]) == {state["state_id"] for state in row["states"]},
            "state_weights.no_pending_omitted_or_new_states",
        )
        values = {state: _fraction(value) for state, value in distribution[task].items()}
        residual = sum(values.values(), Fraction()) - 1
        require(
            abs(residual) <= MASS_TOLERANCE, "state_weights.task_mass_one_without_renormalizing"
        )
        if row["group"] == "control":
            require(
                all(values[state["state_id"]] == Fraction(state["pi0"]) for state in row["states"]),
                "state_weights.controls_stay_at_original_prior",
            )
        checked[task], residuals[task] = values, str(residual)
    return checked, residuals


def _ordered_ids(catalog, batch, pool):
    ids = []
    for task in batch["tasks"]:
        for method in ("control",) if task["group"] == "control" else design.METHODS:
            ids.extend(
                row["id"]
                for row in catalog["original_package_descriptors"]
                if row["pool"] == pool
                and row["task_id"] == task["task_id"]
                and row["actual_method"] == method
                and row["role"] == "train"
            )
    return ids


def update_examples(root, manifest, catalog, batch, *, pool, distribution):
    validate_catalog(catalog, manifest)
    probabilities, residuals = validate_distribution(catalog, distribution, pool=pool)
    # Reuse the byte-checked original reader under its unchanged alpha0 contract.
    originals = materials.update_examples(root, manifest, batch, pool=pool, arm="alpha0")
    mappings = {row["package_id"]: row for row in catalog["package_mappings"]}
    supports = {
        (row["task_id"], state["state_id"]): state
        for row in catalog["task_support"]
        if row["pool"] == pool
        for state in row["states"]
    }
    output = []
    for package in originals:
        item = mappings[package["package_id"]]
        task, state = package["task_id"], item["state_id"]
        n = supports[task, state]["n_train"]
        require(
            item["status"] == "MAPPED"
            and item["role"] == "train"
            and item["pool"] == pool
            and item["actual_method"] == package["actual_method"]
            and item["original_rows_sha256"] == sha(encode(package["rows"])),
            "state_weights.original_physical_rows_and_mapping",
        )
        coefficient = probabilities[task][state] / (5 * n * package["whole_package_target_tokens"])
        if probabilities[task][state] == Fraction(supports[task, state]["pi0"]):
            require(
                coefficient == Fraction(package["target_token_coefficient"]),
                "state_weights.initial_exact_original_alpha0",
            )
        output.append(
            {
                **package,
                "target_token_coefficient": str(coefficient),
                "original_alpha0_coefficient": package["target_token_coefficient"],
                "state_id": state,
                "n_train_in_state": n,
                "state_probability": str(probabilities[task][state]),
                "role": "train",
                "state_catalog_id": catalog["id"],
                "original_rows_sha256": item["original_rows_sha256"],
                "task_mass_residual": residuals[task],
            }
        )
    validate_update(output, batch, pool=pool, catalog=catalog, distribution=distribution)
    return output


def validate_update(examples, batch, *, pool, catalog, distribution):
    require(pool in {"A", "B"}, "state_update.registered_pool")
    probabilities, residuals = validate_distribution(catalog, distribution, pool=pool)
    tasks = batch["tasks"]
    require(
        len(tasks) == 5
        and len({row["task_id"] for row in tasks}) == 5
        and Counter(row["group"] for row in tasks)
        == Counter({**dict.fromkeys(design.DUAL_GROUPS, 1), "control": 2}),
        "state_update.five_tasks_three_dual_two_control",
    )
    require(
        len(examples) == 64
        and len({row["package_id"] for row in examples}) == 64
        and [row["package_id"] for row in examples] == _ordered_ids(catalog, batch, pool),
        "state_update.all_64_original_packages_in_original_order",
    )
    mappings = {row["package_id"]: row for row in catalog["package_mappings"]}
    supports = {
        (row["task_id"], state["state_id"]): state
        for row in catalog["task_support"]
        if row["pool"] == pool
        for state in row["states"]
    }
    groups = {row["task_id"]: row["group"] for row in tasks}
    metadata, counts = [], Counter()
    for package in examples:
        task, state = package["task_id"], package["state_id"]
        original = mappings[package["package_id"]]
        require(
            task in groups
            and package["pool"] == pool
            and package["role"] == "train"
            and original["status"] == "MAPPED"
            and original["state_id"] == state
            and original["task_id"] == task
            and original["pool"] == pool
            and package["actual_method"] == original["actual_method"]
            and package["state_catalog_id"] == catalog["id"],
            "state_update.no_mixed_pool_holdout_method_or_state",
        )
        require(
            sha(encode(package["rows"]))
            == original["original_rows_sha256"]
            == package["original_rows_sha256"],
            "state_update.no_recompiled_reordered_or_deleted_rows",
        )
        rows = [validate_row(row) for row in package["rows"]]
        length = sum(row["target_token_count"] for row in rows)
        n = supports[task, state]["n_train"]
        require(
            length > 0
            and length
            == package["whole_package_target_tokens"]
            == original["whole_package_target_tokens"]
            and n == package["n_train_in_state"],
            "state_update.true_original_state_count_and_whole_package_length",
        )
        require(
            Fraction(package["target_token_coefficient"])
            == probabilities[task][state] / (5 * n * length)
            and Fraction(package["state_probability"]) == probabilities[task][state],
            "state_update.exact_pi_over_5nL_without_extra_divisor",
        )
        counts[task, package["actual_method"]] += 1
        metadata.append(
            {
                "package_id": package["package_id"],
                "state_id": state,
                "target_token_coefficient": package["target_token_coefficient"],
                "whole_package_target_tokens": length,
                "row_count": len(rows),
                "original_rows_sha256": original["original_rows_sha256"],
            }
        )
    require(
        counts
        == Counter(
            {
                (task["task_id"], method): 8
                for task in tasks
                for method in (("control",) if task["group"] == "control" else design.METHODS)
            }
        ),
        "state_update.eight_per_original_actual_method",
    )
    return record(
        "validated_state_update",
        state_catalog_id=catalog["id"],
        pool=pool,
        packages=metadata,
        task_mass_residuals={row["task_id"]: residuals[row["task_id"]] for row in tasks},
        probability_values_used_without_clipping_or_renormalizing=True,
    )


def execute_update(
    model,
    optimizer,
    examples,
    batch,
    *,
    pool,
    catalog,
    distribution,
    device="cpu",
    event_sink=None,
    loss_fn=selected_target_loss,
):
    """Full CPU synthetic step; no cancelled historical assertion or live GPU claim."""
    require(
        torch.device(device).type == "cpu", "state_update.Qwen_GPU_not_yet_authorized_or_validated"
    )
    # Callbacks must not be able to change already-validated weights or rows
    # through a reference to caller-owned input objects.
    examples, batch, catalog, distribution = copy.deepcopy((examples, batch, catalog, distribution))
    validation = validate_update(
        examples, batch, pool=pool, catalog=catalog, distribution=distribution
    )
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    require(
        parameters
        and all(
            parameter.device.type == "cpu" and bool(torch.isfinite(parameter).all())
            for parameter in parameters
        ),
        "state_update.finite_CPU_parameters",
    )
    emit = event_sink if event_sink is not None else lambda event: None
    counters = {
        "zero_grad_calls": 0,
        "backward_calls": 0,
        "packages_completed": 0,
        "clip_calls": 0,
        "optimizer_step_calls": 0,
        "target_tokens": 0,
        "sequence_tokens": 0,
    }
    loss_total = 0.0
    try:
        emit({"event": "validated_state_update", "validation_id": validation["id"]})
        optimizer.zero_grad(set_to_none=True)
        counters["zero_grad_calls"] += 1
        for package in examples:
            for row in package["rows"]:
                data = validate_row(row)
                ids = torch.tensor([data["input_ids"]], dtype=torch.long, device=device)
                active = [position for position, value in enumerate(data["target_mask"]) if value]
                positions = torch.tensor(
                    [position - 1 for position in active], dtype=torch.long, device=device
                )
                targets = [data["labels"][position] for position in active]
                logits = model(
                    input_ids=ids,
                    attention_mask=torch.ones_like(ids),
                    use_cache=False,
                    logits_to_keep=positions,
                ).logits
                loss = loss_fn(logits, targets, package["target_token_coefficient"])
                require(loss.ndim == 0 and bool(torch.isfinite(loss)), "state_update.finite_loss")
                loss.backward()
                value = float(loss.detach())
                require(math.isfinite(loss_total + value), "state_update.finite_loss_sum")
                loss_total += value
                counters["backward_calls"] += 1
                counters["target_tokens"] += len(targets)
                counters["sequence_tokens"] += len(data["input_ids"])
                emit(
                    {
                        "event": "original_row_backward",
                        "package_id": package["package_id"],
                        "candidate_id": row["candidate_id"],
                        "weighted_loss": value,
                        **counters,
                    }
                )
            counters["packages_completed"] += 1
        require(
            counters["packages_completed"] == 64
            and all(
                parameter.grad is not None and bool(torch.isfinite(parameter.grad).all())
                for parameter in parameters
            ),
            "state_update.all_packages_finite_gradients_before_step",
        )
        require(
            all(
                bool(torch.isfinite(value).all())
                for state in optimizer.state.values()
                for value in state.values()
                if isinstance(value, torch.Tensor)
            ),
            "state_update.finite_actual_optimizer_state",
        )
        norm = torch.nn.utils.clip_grad_norm_(parameters, 1.0, error_if_nonfinite=True)
        counters["clip_calls"] += 1
        emit({"event": "before_single_optimizer_step", "gradient_norm": float(norm), **counters})
        optimizer.step()
        counters["optimizer_step_calls"] += 1
        require(
            all(bool(torch.isfinite(parameter).all()) for parameter in parameters),
            "state_update.finite_updated_parameters",
        )
    except Exception as error:
        emit(
            {
                "event": "state_update_failed",
                "error_type": type(error).__name__,
                "error": str(error),
                **counters,
            }
        )
        raise
    return record(
        "completed_state_CPU_update",
        validation_id=validation["id"],
        weighted_loss=loss_total,
        gradient_norm=float(norm),
        **counters,
        execution_kind="synthetic_cpu_control",
        actual_Qwen_training=False,
        GPU_operations=0,
        original_alpha_kernel_modified=False,
    )
