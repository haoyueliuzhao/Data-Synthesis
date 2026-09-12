"""One five-task update over 64 complete original response packages.

The coefficient already contains the task, method-package and whole-package
token means. Selecting predecessor logits never selects or truncates history.
This module loads neither model assets nor a tokenizer.
"""

import math
from collections import Counter
from contextlib import nullcontext
from fractions import Fraction

import torch
from torch.nn.attention import SDPBackend, sdpa_kernel

from ..finance_qa_vnext_basis_scale_preparation import design
from ..finance_qa_vnext_pq_student.loss import selected_target_loss
from .protocol import encode, record, require, sha


def validate_row(row):
    """Check, without rewriting, the stored unpadded causal representation."""
    representation = row["representation"]
    ids, mask, labels = (
        representation["input_ids"],
        representation["target_mask"],
        representation["labels"],
    )
    require(
        isinstance(ids, list)
        and isinstance(mask, list)
        and isinstance(labels, list)
        and len(ids) == len(mask) == len(labels)
        and 1 < len(ids) <= 24576
        and all(type(token) is int and token >= 0 for token in ids)
        and all(type(active) is int and active in (0, 1) for active in mask)
        and mask[0] == 0
        and all(
            type(label) is int and label == (token if active else -100)
            for token, active, label in zip(ids, mask, labels, strict=True)
        )
        and type(representation["sequence_length"]) is int
        and representation["sequence_length"] == len(ids)
        and type(representation["target_token_count"]) is int
        and representation["target_token_count"] == sum(mask) > 0,
        "kernel.original_full_history_mask_and_single_causal_shift",
    )
    require(
        representation.get("attention_mask", [1] * len(ids)) == [1] * len(ids),
        "kernel.original_unpadded_attention",
    )
    require(
        representation.get("consumable_token_representation", True) is True
        and representation.get("truncation", False) is False,
        "kernel.no_nonconsumable_or_truncated_row",
    )
    return representation


def validate_update(examples, batch, *, pool, arm, expected_package_ids=None):
    require(pool in design.POOLS and arm in design.ARMS, "kernel.registered_pool_arm")
    tasks = batch["tasks"]
    require(
        len(tasks) == 5
        and len({task["task_id"] for task in tasks}) == 5
        and Counter(task["group"] for task in tasks)
        == Counter({**dict.fromkeys(design.DUAL_GROUPS, 1), "control": 2}),
        "kernel.five_tasks_three_dual_two_controls",
    )
    groups = {task["task_id"]: task["group"] for task in tasks}
    require(
        len(examples) == 64 and len({item["package_id"] for item in examples}) == 64,
        "kernel.exact_64_unique_complete_packages",
    )
    if expected_package_ids is not None:
        require(
            [item["package_id"] for item in examples] == list(expected_package_ids),
            "kernel.original_frozen_training_package_order",
        )
    counts, metadata = Counter(), []
    for package in examples:
        require(
            package["pool"] == pool
            and package["task_id"] in groups
            and package.get("role", "train") == "train",
            "kernel.no_mixed_pool_holdout_or_foreign_task",
        )
        method, group = package["actual_method"], groups[package["task_id"]]
        require(
            method in (("control",) if group == "control" else design.METHODS),
            "kernel.actual_method_stratum",
        )
        require(isinstance(package["rows"], list) and package["rows"], "kernel.complete_rows")
        rows = [validate_row(row) for row in package["rows"]]
        length = sum(row["target_token_count"] for row in rows)
        require(
            type(package["whole_package_target_tokens"]) is int
            and package["whole_package_target_tokens"] == length,
            "kernel.true_whole_package_token_denominator",
        )
        require(
            isinstance(package["target_token_coefficient"], (str, Fraction))
            and Fraction(package["target_token_coefficient"])
            == design.update_token_coefficient(arm, group, method, length),
            "kernel.exact_alpha_over_40L_no_extra_normalization",
        )
        counts[package["task_id"], method] += 1
        metadata.append(
            {
                "package_id": package["package_id"],
                "task_id": package["task_id"],
                "actual_method": method,
                "whole_package_target_tokens": length,
                "target_token_coefficient": str(Fraction(package["target_token_coefficient"])),
                "rows": len(rows),
                "sequence_tokens": sum(row["sequence_length"] for row in rows),
                "original_rows_sha256": sha(encode(package["rows"])),
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
        "kernel.eight_training_packages_per_actual_method",
    )
    return metadata


def execute_update(
    model,
    optimizer,
    examples,
    batch,
    *,
    pool,
    arm,
    device,
    loss_fn=selected_target_loss,
    event_sink=None,
    expected_package_ids=None,
):
    """Accumulate original-row sums; clip and step only after all 64 packages.

    ``event_sink`` is called before a potentially irreversible optimizer step.
    A failed sink or forward/backward aborts immediately, with no retry or step.
    CPU injection is a synthetic test seam, not a reduced production protocol.
    """
    metadata = validate_update(
        examples, batch, pool=pool, arm=arm, expected_package_ids=expected_package_ids
    )
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    require(bool(parameters), "kernel.trainable_parameters_present")
    require(
        all(torch.isfinite(parameter.detach()).all().item() for parameter in parameters),
        "kernel.finite_initial_parameters",
    )
    emit = event_sink if event_sink is not None else lambda event: None
    state = {
        "rows_completed": 0,
        "packages_completed": 0,
        "zero_grad_calls": 0,
        "clip_calls": 0,
        "optimizer_step_calls": 0,
    }
    total_loss, target_tokens, sequence_tokens, package_losses = 0.0, 0, 0, []
    try:
        emit({"event": "update_validated", "packages": metadata, "tasks": batch["tasks"]})
        optimizer.zero_grad(set_to_none=True)
        state["zero_grad_calls"] += 1
        emit({"event": "zero_grad_completed", **state})
        for package in examples:
            nll_sum = 0.0
            coefficient = str(Fraction(package["target_token_coefficient"]))
            for row_index, row in enumerate(package["rows"]):
                representation = row["representation"]
                ids = torch.tensor([representation["input_ids"]], dtype=torch.long, device=device)
                attention = torch.ones_like(ids)
                target_positions = [
                    index for index, active in enumerate(representation["target_mask"]) if active
                ]
                positions = torch.tensor(
                    [index - 1 for index in target_positions], dtype=torch.long, device=device
                )
                targets = [representation["labels"][index] for index in target_positions]
                emit(
                    {
                        "event": "row_started",
                        "package_id": package["package_id"],
                        "row_index": row_index,
                        **state,
                    }
                )
                context = (
                    sdpa_kernel(SDPBackend.FLASH_ATTENTION)
                    if torch.device(device).type == "cuda"
                    else nullcontext()
                )
                with context:
                    logits = model(
                        input_ids=ids,
                        attention_mask=attention,
                        use_cache=False,
                        logits_to_keep=positions,
                    ).logits
                    loss = loss_fn(logits, targets, coefficient)
                    require(
                        isinstance(loss, torch.Tensor)
                        and loss.ndim == 0
                        and bool(torch.isfinite(loss.detach())),
                        "kernel.finite_scalar_loss",
                    )
                    loss.backward()
                value = float(loss.detach())
                require(math.isfinite(total_loss + value), "kernel.finite_accumulated_loss")
                total_loss += value
                nll_sum += value / float(Fraction(coefficient))
                target_tokens += len(targets)
                sequence_tokens += len(representation["input_ids"])
                state["rows_completed"] += 1
                emit(
                    {
                        "event": "row_backward_completed",
                        "package_id": package["package_id"],
                        "row_index": row_index,
                        "weighted_loss": value,
                        "target_tokens": len(targets),
                        "sequence_tokens": ids.shape[1],
                        **state,
                    }
                )
                del loss, logits, ids, attention, positions
            package_losses.append(
                {
                    "package_id": package["package_id"],
                    "target_nll_sum": nll_sum,
                    "target_tokens": package["whole_package_target_tokens"],
                }
            )
            state["packages_completed"] += 1
        require(
            all(
                parameter.grad is not None and bool(torch.isfinite(parameter.grad).all())
                for parameter in parameters
            ),
            "kernel.complete_finite_gradients_before_step",
        )
        require(
            all(
                bool(torch.isfinite(value).all())
                for state_values in optimizer.state.values()
                for value in state_values.values()
                if isinstance(value, torch.Tensor)
            ),
            "kernel.finite_optimizer_state_before_step",
        )
        norm = torch.nn.utils.clip_grad_norm_(parameters, max_norm=1.0, error_if_nonfinite=True)
        state["clip_calls"] += 1
        require(bool(torch.isfinite(norm)), "kernel.finite_gradient_norm")
        emit(
            {
                "event": "optimizer_step_intent",
                "gradient_norm_before_clip": float(norm),
                "maximum_gradient_norm": 1.0,
                "target_tokens": target_tokens,
                "sequence_tokens": sequence_tokens,
                "weighted_loss": total_loss,
                **state,
            }
        )
        state["optimizer_step_calls"] += 1
        optimizer.step()
        emit({"event": "optimizer_step_returned", **state})
        require(
            all(bool(torch.isfinite(parameter.detach()).all()) for parameter in parameters),
            "kernel.finite_post_step_parameters",
        )
        result = record(
            "optimizer_update",
            status="COMPLETE",
            batch=batch,
            pool=pool,
            arm=arm,
            packages=metadata,
            package_losses=package_losses,
            weighted_loss=total_loss,
            target_tokens=target_tokens,
            sequence_tokens=sequence_tokens,
            gradient_norm_before_clip=float(norm),
            maximum_gradient_norm=1.0,
            full_original_histories=True,
            causal_shift=1,
            extra_normalization=False,
            **state,
        )
        emit({"event": "update_complete", "update_id": result["id"], **state})
        return result
    except BaseException as error:
        emit(
            {
                "event": "update_failed",
                "error_type": type(error).__name__,
                "error": str(error),
                "automatic_retry": False,
                **state,
            }
        )
        raise
