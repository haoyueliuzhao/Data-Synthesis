"""One-time-verified trajectory inputs; exactly one weighted sum/update.

Prefix sharing changes the dropout RNG correlation between response targets.
This is a new execution design, not a bitwise replay of response-row training.
The causal target set, whole-package denominator and exact state weights remain
unchanged. Token/cache validation belongs to trajectory_materials, once only.
"""

import math
from contextlib import nullcontext

import torch
import torch.nn.functional as functional
from torch.nn.attention import SDPBackend, sdpa_kernel

from . import protocol as p


def selected_target_loss(logits, target_ids, coefficient):
    """Same FP32 summed CE as the parent, without rescanning verified targets."""
    return functional.cross_entropy(
        logits.reshape(-1, logits.shape[-1]).float(), target_ids, reduction="sum"
    ) * coefficient


def execute_update(
    model,
    optimizer,
    examples,
    batch,
    *,
    pool,
    arm,
    device,
    trajectory_cache,
    loss_fn=selected_target_loss,
    event_sink=None,
):
    """Consume the prepared inventory, then check finite loss/gradient and step.

    No canonical hashes, original rows, state counts or target masks are checked
    in this hot path. Their preparation is a single startup operation. A prefix
    package has one forward/backward; a nonprefix package uses original segments.
    """
    parameters = [value for value in model.parameters() if value.requires_grad]
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
        emit({"event": "update_started", "tasks": batch["tasks"], "packages": len(examples)})
        optimizer.zero_grad(set_to_none=True)
        state["zero_grad_calls"] = 1
        for package in examples:
            coefficient = package["coefficient_float"]
            package_loss = torch.zeros((), dtype=torch.float32, device=device)
            package_targets, package_sequence, package_rows = 0, 0, 0
            emit({"event": "package_started", "package_id": package["package_id"], **state})
            for row in trajectory_cache.row_arrays(package["package_id"]):
                # torch.tensor copies read-only mmap views into owned tensors.
                ids = torch.tensor(row["input_ids"], dtype=torch.long, device=device).unsqueeze(0)
                positions = torch.tensor(
                    row["target_positions"], dtype=torch.long, device=device
                ) - 1
                targets = torch.tensor(row["target_ids"], dtype=torch.long, device=device)
                attention = torch.ones_like(ids)
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
                    loss.backward()
                package_loss += loss.detach()
                package_targets += targets.numel()
                package_sequence += ids.shape[1]
                package_rows += 1
                del loss, logits, ids, attention, positions, targets
            value = float(package_loss)
            total_loss += value
            target_tokens += package_targets
            sequence_tokens += package_sequence
            state["rows_completed"] += package_rows
            state["packages_completed"] += 1
            package_losses.append(
                {
                    "package_id": package["package_id"],
                    "target_nll_sum": value / coefficient,
                    "target_tokens": package_targets,
                }
            )
            emit(
                {
                    "event": "package_backward_completed",
                    "package_id": package["package_id"],
                    "weighted_loss": value,
                    "target_tokens": package_targets,
                    "sequence_tokens": package_sequence,
                    "forward_segments": package_rows,
                    **state,
                }
            )
        p.require(math.isfinite(total_loss), "trajectory_consumer.finite_update_loss")
        p.require(
            all(parameter.grad is not None for parameter in parameters),
            "trajectory_consumer.complete_trainable_gradients",
        )
        # The clipping operation already scans every gradient and rejects NaN/Inf.
        # Do not perform another per-parameter finite scan before this operation.
        norm = torch.nn.utils.clip_grad_norm_(parameters, 1.0, error_if_nonfinite=True)
        state["clip_calls"] = 1
        emit({"event": "before_optimizer_step", "preclip_gradient_norm": float(norm), **state})
        optimizer.step()
        state["optimizer_step_calls"] = 1
        result = p.record(
            "optimizer_update",
            pool=pool,
            arm=arm,
            tasks=batch["tasks"],
            packages=examples,
            package_losses=package_losses,
            weighted_loss=total_loss,
            target_tokens=target_tokens,
            sequence_tokens=sequence_tokens,
            preclip_gradient_norm=float(norm),
            loss_rule="pi(state|task)/(5*n_state*whole_package_target_tokens)",
            loss_domain="unchanged original public-response targets; exact-prefix union",
            additional_loss_scaling=False,
            engineering_only=False,
            physical_package_count=len(examples),
            cache_id=trajectory_cache.cache_id,
            execution_design="trajectory_prefix_union_v1",
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
