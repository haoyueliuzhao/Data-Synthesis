"""Full-supervision original-package consumer for an unequal finite material kernel.

Five tasks contribute exactly 1/5 each. All of their original training packages
are consumed once, without token/row/package truncation or a second loss mean.
This module does not construct models, initialize CUDA, or load tokenizers.
"""

import math
from collections import Counter, defaultdict
from contextlib import nullcontext
from fractions import Fraction

import torch
from torch.nn.attention import SDPBackend, sdpa_kernel

from ..finance_qa_vnext_basis_student.kernel import validate_row
from ..finance_qa_vnext_pq_student.loss import selected_target_loss
from .distribution import canonical_state_id
from .protocol import ARMS, FAMILIES, checked_record, encode, record, require, sha

GROUPS = FAMILIES


def fraction(value):
    """Accept only exact representations, never a binary floating point weight."""
    if isinstance(value, dict):
        require(set(value) == {"numerator", "denominator"}, "consumer.exact_fraction_fields")
        require(all(type(v) is int for v in value.values()), "consumer.integer_fraction")
        value = Fraction(value["numerator"], value["denominator"])
    require(
        isinstance(value, (str, int, Fraction)) and not isinstance(value, bool),
        "consumer.exact_fraction",
    )
    return Fraction(value)


def validate_update(
    examples, batch, *, pool, arm, expected_package_ids=None, engineering_only=False
):
    """Validate the complete original package set and all exact mass identities."""
    require(pool in ("A", "B") and arm in ARMS, "consumer.registered_pool_arm")
    require(type(engineering_only) is bool, "consumer.explicit_engineering_mode")
    tasks = batch["tasks"]
    require(
        len(tasks) == 5 and len({t["task_id"] for t in tasks}) == 5, "consumer.five_unique_tasks"
    )
    require(
        Counter(t["group"] for t in tasks)
        == Counter({GROUPS[0]: 1, GROUPS[1]: 1, GROUPS[2]: 1, GROUPS[3]: 2}),
        "consumer.one_each_target_two_controls",
    )
    require(
        isinstance(examples, list)
        and examples
        and len({p["package_id"] for p in examples}) == len(examples),
        "consumer.nonempty_unique_original_packages",
    )
    # A caller must supply the independently frozen inventory. Otherwise a
    # maliciously dropped package could hide behind a recomputed n_state.
    require(
        expected_package_ids is not None
        and [p["package_id"] for p in examples] == list(expected_package_ids),
        "consumer.exact_frozen_package_inventory_order",
    )
    groups = {t["task_id"]: t["group"] for t in tasks}
    state_counts = Counter((p["task_id"], p["state_id"]) for p in examples)
    states, task_mass, metadata = {}, defaultdict(Fraction), []
    for package in examples:
        task, state = package["task_id"], package["state_id"]
        require(
            task in groups and package["pool"] == pool and package["role"] == "train",
            "consumer.no_holdout_other_pool_or_foreign_task",
        )
        require(isinstance(state, str) and state, "consumer.actual_complete_state_identity")
        method = package["method"]
        require(
            method in (("control",) if groups[task] == "control" else ("endpoint", "movement")),
            "consumer.actual_method",
        )
        pi, coefficient = fraction(package["pi"]), fraction(package["target_token_coefficient"])
        require(0 < pi <= 1, "consumer.positive_state_probability")
        n = package["n_state"]
        require(
            type(n) is int and n == state_counts[task, state], "consumer.actual_unequal_state_count"
        )
        require(isinstance(package["rows"], list) and package["rows"], "consumer.all_original_rows")
        rows = [validate_row(row) for row in package["rows"]]
        length = sum(row["target_token_count"] for row in rows)
        require(
            type(package["whole_package_target_tokens"]) is int
            and package["whole_package_target_tokens"] == length,
            "consumer.true_whole_package_target_denominator",
        )
        require(
            coefficient == pi / (5 * n * length),
            "consumer.exact_pi_over_5_n_state_L_no_extra_scale",
        )
        if not engineering_only or "original_package" in package:
            original = package.get("original_package")
            require(isinstance(original, dict), "consumer.production_original_identity_required")
            checked_record(original, "encoded_original_package")
            require(
                original["id"] == package["package_id"]
                and original["task_id"] == task
                and original["pool"] == pool
                and original["actual_method"] == method
                and original["whole_package_target_tokens"] == length
                and original["rows"] == package["rows"]
                and original["consumable"] is True
                and sha(encode(original)) == package["original_package_sha256"]
                and state == canonical_state_id(method, original["full_class"]),
                "consumer.actual_canonical_state_and_immutable_full_original",
            )
        key = task, state
        if key in states:
            require(states[key] == (pi, method), "consumer.same_state_probability_and_method")
        else:
            states[key] = pi, method
            task_mass[task] += pi
        metadata.append(
            {
                "package_id": package["package_id"],
                "task_id": task,
                "state_id": state,
                "method": method,
                "n_state": n,
                "pi": str(pi),
                "whole_package_target_tokens": length,
                "target_token_coefficient": str(coefficient),
                "rows": len(rows),
                "sequence_tokens": sum(row["sequence_length"] for row in rows),
                "original_rows_sha256": sha(encode(package["rows"])),
            }
        )
    require(
        set(task_mass) == set(groups) and all(v == 1 for v in task_mass.values()),
        "consumer.all_five_tasks_normalized_no_task_deletion",
    )
    require(
        sum(
            (
                fraction(p["target_token_coefficient"]) * p["whole_package_target_tokens"]
                for p in examples
            ),
            Fraction(),
        )
        == 1,
        "consumer.unit_update_mass",
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
    engineering_only=False,
):
    """One zero_grad, every original row backward, then one clip and one step.

    Failures abort without retries or partial optimizer steps. Synthetic injected
    CPU models exercise the identical consumer but are not scientific training.
    """
    metadata = validate_update(
        examples,
        batch,
        pool=pool,
        arm=arm,
        expected_package_ids=expected_package_ids,
        engineering_only=engineering_only,
    )
    parameters = [p for p in model.parameters() if p.requires_grad]
    require(
        parameters and all(torch.isfinite(p.detach()).all().item() for p in parameters),
        "consumer.finite_trainable_parameters",
    )
    emit = event_sink or (lambda event: None)
    state = dict(
        rows_completed=0,
        packages_completed=0,
        zero_grad_calls=0,
        clip_calls=0,
        optimizer_step_calls=0,
    )
    total_loss, target_tokens, sequence_tokens, package_losses = 0.0, 0, 0, []
    try:
        emit({"event": "update_validated", "packages": metadata, "tasks": batch["tasks"]})
        optimizer.zero_grad(set_to_none=True)
        state["zero_grad_calls"] += 1
        for package in examples:
            coefficient = fraction(package["target_token_coefficient"])
            nll_sum = 0.0
            for row_index, row in enumerate(package["rows"]):
                representation = row["representation"]
                ids = torch.tensor([representation["input_ids"]], dtype=torch.long, device=device)
                attention = torch.ones_like(ids)
                target_positions = [
                    i for i, active in enumerate(representation["target_mask"]) if active
                ]
                positions = torch.tensor(
                    [i - 1 for i in target_positions], dtype=torch.long, device=device
                )
                targets = [representation["labels"][i] for i in target_positions]
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
                    loss = loss_fn(logits, targets, str(coefficient))
                    require(
                        isinstance(loss, torch.Tensor)
                        and loss.ndim == 0
                        and bool(torch.isfinite(loss.detach())),
                        "consumer.finite_scalar_loss",
                    )
                    loss.backward()
                value = float(loss.detach())
                total_loss += value
                require(math.isfinite(total_loss), "consumer.finite_accumulated_loss")
                nll_sum += value / float(coefficient)
                target_tokens += len(targets)
                sequence_tokens += ids.shape[1]
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
            all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in parameters),
            "consumer.complete_finite_gradients_before_step",
        )
        require(
            all(
                bool(torch.isfinite(v).all())
                for values in optimizer.state.values()
                for v in values.values()
                if isinstance(v, torch.Tensor)
            ),
            "consumer.finite_optimizer_state_before_step",
        )
        norm = torch.nn.utils.clip_grad_norm_(parameters, 1.0, error_if_nonfinite=True)
        state["clip_calls"] += 1
        emit({"event": "before_optimizer_step", "preclip_gradient_norm": float(norm), **state})
        optimizer.step()
        state["optimizer_step_calls"] += 1
        require(
            all(bool(torch.isfinite(p.detach()).all()) for p in parameters),
            "consumer.finite_parameters_after_step",
        )
        require(
            all(
                bool(torch.isfinite(v).all())
                for values in optimizer.state.values()
                for v in values.values()
                if isinstance(v, torch.Tensor)
            ),
            "consumer.finite_optimizer_state_after_step",
        )
        result = record(
            "optimizer_update",
            pool=pool,
            arm=arm,
            tasks=batch["tasks"],
            packages=metadata,
            package_losses=package_losses,
            weighted_loss=total_loss,
            target_tokens=target_tokens,
            sequence_tokens=sequence_tokens,
            preclip_gradient_norm=float(norm),
            loss_rule="pi(state|task)/(5*n_state*whole_package_target_tokens)",
            loss_domain="Full_original_target_mask",
            additional_loss_scaling=False,
            engineering_only=engineering_only,
            physical_package_count=len(examples),
            **state,
        )
        emit({"event": "update_complete", "report_id": result["id"], **state})
        return result
    except BaseException as error:
        emit(
            {
                "event": "update_failed",
                "error_type": type(error).__name__,
                "error": str(error),
                **state,
            }
        )
        raise
