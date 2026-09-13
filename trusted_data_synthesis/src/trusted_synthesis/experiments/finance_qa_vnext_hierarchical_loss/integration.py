"""Loss-consistent class gradients and complete original 64-package CPU steps.

Catalog/manifest admission remains the upstream study's responsibility for the
class-gradient seam. The update seam additionally calls the unchanged parent's
complete state/material validator. No feedback, C, novelty, or pi update occurs.
"""

import copy
import math
from collections import Counter
from collections.abc import Mapping
from fractions import Fraction

import torch

from ..finance_qa_vnext_anchored_vtdo import gradients as parent_gradients
from ..finance_qa_vnext_anchored_vtdo import state_materials as parent_materials
from ..finance_qa_vnext_basis_student.kernel import validate_row
from . import protocol as p
from .loss import HierarchicalTrajectoryLoss
from .representation import validate_package_annotation


def _cpu(model):
    p.require(isinstance(model, torch.nn.Module), "hierarchical.torch_CPU_model")
    parameters = dict(model.named_parameters())
    buffers = dict(model.named_buffers())
    trainable = {name: value for name, value in parameters.items() if value.requires_grad}
    p.require(
        trainable
        and all(
            value.device.type == "cpu"
            and value.dtype in (torch.float32, torch.float64)
            and bool(torch.isfinite(value).all())
            for value in parameters.values()
        )
        and all(value.device.type == "cpu" for value in buffers.values()),
        "hierarchical.finite_FP32_FP64_CPU_only",
    )
    return trainable


def _snapshot(model):
    return {
        "parameters": {name: value.detach().clone() for name, value in model.named_parameters()},
        "buffers": {name: value.detach().clone() for name, value in model.named_buffers()},
        "grads": {
            name: (value.grad, None if value.grad is None else value.grad.detach().clone())
            for name, value in model.named_parameters()
        },
        "modes": [(module, module.training) for module in model.modules()],
    }


def _equal(left, right):
    if isinstance(left, torch.Tensor):
        return (
            isinstance(right, torch.Tensor)
            and left.dtype == right.dtype
            and left.device == right.device
            and left.layout == right.layout
            and torch.equal(left, right)
        )
    if isinstance(left, dict):
        return (
            isinstance(right, dict)
            and set(left) == set(right)
            and all(_equal(value, right[key]) for key, value in left.items())
        )
    if isinstance(left, (list, tuple)):
        return (
            type(left) is type(right)
            and len(left) == len(right)
            and all(_equal(a, b) for a, b in zip(left, right, strict=True))
        )
    return left == right


def _unchanged(model, before, *, check_grads):
    for kind, values in (
        ("parameters", dict(model.named_parameters())),
        ("buffers", dict(model.named_buffers())),
    ):
        p.require(
            _equal(before[kind], values), "hierarchical.unexpected_model_" + kind + "_mutation"
        )
    p.require(
        all(module.training == mode for module, mode in before["modes"]),
        "hierarchical.unexpected_module_mode_mutation",
    )
    if check_grads:
        p.require(
            all(
                (old is None and value.grad is None)
                or (old is not None and value.grad is old and torch.equal(value.grad, saved))
                for name, value in model.named_parameters()
                for old, saved in [before["grads"][name]]
            ),
            "hierarchical.class_gradient_changed_real_grad_buffer",
        )


def _restore(model, before, *, parameters=False, grads=False):
    # On a rejected computation, restore the caller's original tensor contents
    # and grad-object identity. A successful training step keeps its new grads.
    with torch.no_grad():
        for name, value in model.named_buffers():
            if not _equal(value, before["buffers"][name]):
                value.copy_(before["buffers"][name])
        if parameters:
            for name, value in model.named_parameters():
                if not _equal(value, before["parameters"][name]):
                    value.copy_(before["parameters"][name])
        if grads:
            for name, value in model.named_parameters():
                original, saved = before["grads"][name]
                value.grad = original
                if original is not None and not _equal(original, saved):
                    original.copy_(saved)
    for module, mode in before["modes"]:
        module.training = mode


def _prepare(packages, annotations, loss, *, complete_classes):
    p.require(type(loss) is HierarchicalTrajectoryLoss, "hierarchical.registered_loss_class")
    p.require(isinstance(packages, list) and packages, "hierarchical.original_packages_required")
    p.require(isinstance(annotations, Mapping), "hierarchical.package_annotation_map")
    packages, loss = copy.deepcopy((packages, loss))
    identities = [row["package_id"] for row in packages]
    p.require(
        len(set(identities)) == len(identities) and set(identities) <= set(annotations),
        "hierarchical.unique_packages_with_complete_annotations",
    )
    selected = copy.deepcopy({key: annotations[key] for key in identities})
    p.require(
        len({row["pool"] for row in packages}) == 1
        and packages[0]["pool"] in {"A", "B"}
        and len({row["state_catalog_id"] for row in packages}) == 1
        and all(
            isinstance(row["state_catalog_id"], str) and row["state_catalog_id"] for row in packages
        ),
        "hierarchical.one_pool_one_original_state_catalog",
    )
    counts = Counter((row["task_id"], row["state_id"]) for row in packages)
    prepared = []
    for package in packages:
        p.require(
            package.get("role") == "train"
            and package.get("status", "MAPPED") == "MAPPED"
            and isinstance(package.get("state_id"), str)
            and package["state_id"]
            and type(package.get("n_train_in_state")) is int
            and package["n_train_in_state"] > 0,
            "hierarchical.no_heldout_pending_or_missing_state",
        )
        p.require(
            p.sha(p.encode(package["rows"])) == package["original_rows_sha256"],
            "hierarchical.original_rows_hash",
        )
        rows = [validate_row(row) for row in package["rows"]]
        p.require(
            sum(row["target_token_count"] for row in rows)
            == package["whole_package_target_tokens"]
            > 0,
            "hierarchical.original_whole_package_target_count",
        )
        if complete_classes:
            p.require(
                counts[package["task_id"], package["state_id"]] == package["n_train_in_state"],
                "hierarchical.complete_original_class_package_count",
            )
        annotation = validate_package_annotation(package, selected[package["package_id"]])
        p.require(annotation["profile"] == loss.profile, "hierarchical.common_frozen_profile")
        coefficients = loss.token_coefficients(package, annotation)
        p.require(
            len(coefficients) == len(rows)
            and all(
                len(weights) == row["target_token_count"]
                and all(isinstance(weight, Fraction) and weight >= 0 for weight in weights)
                for row, weights in zip(rows, coefficients, strict=True)
            ),
            "hierarchical.exact_original_target_coefficient_alignment",
        )
        prepared.append((package, annotation, rows, coefficients))
    return packages, loss, prepared


def _forward(model, row):
    ids = torch.tensor([row["input_ids"]], dtype=torch.long, device="cpu")
    active = [index for index, value in enumerate(row["target_mask"]) if value]
    predecessors = torch.tensor([index - 1 for index in active], dtype=torch.long)
    labels = [row["labels"][index] for index in active]
    logits = model(
        input_ids=ids,
        attention_mask=torch.ones_like(ids),
        use_cache=False,
        logits_to_keep=predecessors,
    ).logits
    return logits, labels


def _coefficient_evidence(prepared, *, class_mean=False):
    evidence = []
    for package, annotation, _, coefficients in prepared:
        n = package["n_train_in_state"]
        outer = Fraction(1, n) if class_mean else Fraction(package["state_probability"]) / (5 * n)
        evidence.append(
            {
                "package_id": package["package_id"],
                "task_id": package["task_id"],
                "state_id": package["state_id"],
                "n_train_in_state": n,
                "annotation_id": annotation["id"],
                "annotation_CPU_only": annotation["CPU_only"],
                "original_rows_sha256": package["original_rows_sha256"],
                "original_parent_token_coefficient": package["target_token_coefficient"],
                "layer_token_counts": annotation["layer_token_counts"],
                "outer_package_coefficient": str(outer),
                "effective_target_coefficients": [
                    [str(outer * value) for value in row] for row in coefficients
                ],
            }
        )
    return evidence


def class_gradients(model, packages, *, loss, annotations):
    """Mean original package objectives within each full class; pi is absent.

    The upstream controller must authenticate catalog/manifest membership. This
    seam checks the supplied original row hashes, annotation authority, state
    identities and complete per-class package counts before any forward call.
    """
    parameters = _cpu(model)
    packages, loss, prepared = _prepare(packages, annotations, loss, complete_classes=True)
    before = _snapshot(model)
    parent_artifact = None
    try:
        if loss.objective == "full_token_mean":
            original = parent_gradients.class_gradients(model, packages)
            result, parent_artifact = original["gradients"], original["artifact"]
            rows_count = parent_artifact["forward_backward_rows"]
            targets, sequences = (
                parent_artifact["target_tokens"],
                parent_artifact["sequence_tokens"],
            )
        else:
            result, rows_count, targets, sequences = {}, 0, 0, 0
            with parent_gradients.evaluation_mode(model):
                for package, _, rows, coefficients in prepared:
                    values = result.setdefault(package["task_id"], {}).setdefault(
                        package["state_id"],
                        {name: torch.zeros_like(value) for name, value in parameters.items()},
                    )
                    for row, weights in zip(rows, coefficients, strict=True):
                        logits, labels = _forward(model, row)
                        objective = loss.row_loss(
                            logits, labels, weights, scale=Fraction(1, package["n_train_in_state"])
                        )
                        p.require(
                            objective.ndim == 0
                            and objective.requires_grad
                            and bool(torch.isfinite(objective)),
                            "hierarchical.finite_connected_class_loss",
                        )
                        derivatives = torch.autograd.grad(
                            objective, tuple(parameters.values()), allow_unused=True
                        )
                        for (name, _), derivative in zip(
                            parameters.items(), derivatives, strict=True
                        ):
                            if derivative is not None:
                                p.require(
                                    bool(torch.isfinite(derivative).all()),
                                    "hierarchical.finite_class_gradient",
                                )
                                values[name].add_(derivative.detach())
                        rows_count += 1
                        targets += len(labels)
                        sequences += len(row["input_ids"])
        _unchanged(model, before, check_grads=True)
    except BaseException:
        _restore(model, before, parameters=True, grads=True)
        raise
    finally:
        _restore(model, before)
    return {
        "gradients": result,
        "artifact": p.record(
            "class_gradient_evidence",
            loss=loss.describe(),
            parent_full_delegate=parent_artifact,
            model_parameter_digest=parent_gradients.tensor_digest(dict(model.named_parameters())),
            model_buffer_digest=parent_gradients.tensor_digest(dict(model.named_buffers())),
            package_count=len(packages),
            original_package_ids=[row["package_id"] for row in packages],
            state_counts={
                task: {
                    state: next(
                        row["n_train_in_state"]
                        for row in packages
                        if row["task_id"] == task and row["state_id"] == state
                    )
                    for state in states
                }
                for task, states in result.items()
            },
            class_gradient_digests={
                task: {
                    state: parent_gradients.tensor_digest(values)
                    for state, values in states.items()
                }
                for task, states in result.items()
            },
            effective_coefficients=_coefficient_evidence(prepared, class_mean=True),
            forward_backward_rows=rows_count,
            target_tokens=targets,
            sequence_tokens=sequences,
            pi_factors_in_class_gradient=0,
            mean_of_original_package_objectives=True,
            proxy_dropout=False,
            actual_Qwen_training=False,
            GPU_operations=0,
            real_parameters_buffers_grads_or_modes_changed=False,
            feedback_or_outer_pi_updates=0,
        ),
    }


def execute_update_cpu(
    model,
    optimizer,
    examples,
    batch,
    *,
    pool,
    catalog,
    distribution,
    loss,
    annotations,
    device="cpu",
    event_sink=None,
):
    """One zero/clip/AdamW step after all 64 original packages, with pi once.

    Pre-step validation, forward/backward and sink failures do not call step.
    Original examples and target_token_coefficient remain unchanged. Full uses
    the parent's unmodified consumer; hierarchy has a separate effective weight.
    """
    p.require(torch.device(device).type == "cpu", "hierarchical.CPU_only_no_production_admission")
    parameters = _cpu(model)
    p.require(isinstance(optimizer, torch.optim.AdamW), "hierarchical.actual_AdamW_required")
    optimizer_parameters = [value for group in optimizer.param_groups for value in group["params"]]
    p.require(
        len(optimizer_parameters) == len(parameters)
        and {id(value) for value in optimizer_parameters}
        == {id(value) for value in parameters.values()},
        "hierarchical.exact_trainable_optimizer_parameter_set",
    )
    examples, batch, catalog, distribution = copy.deepcopy((examples, batch, catalog, distribution))
    validation = parent_materials.validate_update(
        examples, batch, pool=pool, catalog=catalog, distribution=distribution
    )
    examples, loss, prepared = _prepare(examples, annotations, loss, complete_classes=True)
    before = _snapshot(model)
    optimizer_before = copy.deepcopy(optimizer.state_dict())

    def emit(event):
        if event_sink is not None:
            callback_point = _snapshot(model)
            event_sink(copy.deepcopy(event))
            _unchanged(model, callback_point, check_grads=True)
        if event["event"] == "before_single_optimizer_step":
            _unchanged(model, before, check_grads=False)
            p.require(
                _equal(optimizer_before, optimizer.state_dict()),
                "hierarchical.optimizer_mutated_before_registered_step",
            )

    try:
        if loss.objective == "full_token_mean":
            result = parent_materials.execute_update(
                model,
                optimizer,
                examples,
                batch,
                pool=pool,
                catalog=catalog,
                distribution=distribution,
                device=device,
                event_sink=emit,
            )
        else:
            counters = dict(
                zero_grad_calls=0,
                backward_calls=0,
                packages_completed=0,
                clip_calls=0,
                optimizer_step_calls=0,
                target_tokens=0,
                sequence_tokens=0,
            )
            total = 0.0
            emit({"event": "validated_state_update", "validation_id": validation["id"]})
            optimizer.zero_grad(set_to_none=True)
            counters["zero_grad_calls"] += 1
            for package, _, rows, coefficients in prepared:
                outer = Fraction(package["state_probability"]) / (5 * package["n_train_in_state"])
                for original_row, row, weights in zip(
                    package["rows"], rows, coefficients, strict=True
                ):
                    logits, labels = _forward(model, row)
                    objective = loss.row_loss(logits, labels, weights, scale=outer)
                    p.require(
                        objective.ndim == 0
                        and objective.requires_grad
                        and bool(torch.isfinite(objective)),
                        "hierarchical.finite_connected_training_loss",
                    )
                    objective.backward()
                    value = float(objective.detach())
                    p.require(math.isfinite(total + value), "hierarchical.finite_accumulated_loss")
                    total += value
                    counters["backward_calls"] += 1
                    counters["target_tokens"] += len(labels)
                    counters["sequence_tokens"] += len(row["input_ids"])
                    emit(
                        {
                            "event": "original_row_backward",
                            "package_id": package["package_id"],
                            "candidate_id": original_row["candidate_id"],
                            "weighted_loss": value,
                            **counters,
                        }
                    )
                counters["packages_completed"] += 1
            p.require(
                counters["packages_completed"] == 64
                and all(
                    value.grad is not None and bool(torch.isfinite(value.grad).all())
                    for value in parameters.values()
                ),
                "hierarchical.all_64_packages_finite_gradients_before_step",
            )
            p.require(
                all(
                    bool(torch.isfinite(value).all())
                    for fields in optimizer.state.values()
                    for value in fields.values()
                    if isinstance(value, torch.Tensor)
                ),
                "hierarchical.finite_actual_AdamW_state",
            )
            norm = torch.nn.utils.clip_grad_norm_(
                list(parameters.values()), 1.0, error_if_nonfinite=True
            )
            counters["clip_calls"] += 1
            emit(
                {"event": "before_single_optimizer_step", "gradient_norm": float(norm), **counters}
            )
            optimizer.step()
            counters["optimizer_step_calls"] += 1
            p.require(
                all(bool(torch.isfinite(value).all()) for value in parameters.values()),
                "hierarchical.finite_updated_parameters",
            )
            result = p.record(
                "hierarchical_CPU_step",
                validation_id=validation["id"],
                weighted_loss=total,
                gradient_norm=float(norm),
                **counters,
            )
    except BaseException:
        _restore(model, before, parameters=True, grads=True)
        if not _equal(optimizer_before, optimizer.state_dict()):
            optimizer.load_state_dict(optimizer_before)
        raise
    finally:
        _restore(model, before)
    counters = {
        key: result[key]
        for key in (
            "zero_grad_calls",
            "backward_calls",
            "packages_completed",
            "clip_calls",
            "optimizer_step_calls",
            "target_tokens",
            "sequence_tokens",
        )
    }
    return p.record(
        "completed_loss_CPU_update",
        loss=loss.describe(),
        parent_validation_id=validation["id"],
        original_consumer_result=result,
        delegated_unchanged_parent_full_consumer=loss.objective == "full_token_mean",
        effective_coefficients=_coefficient_evidence(prepared),
        weighted_loss=result["weighted_loss"],
        gradient_norm=result["gradient_norm"],
        **counters,
        pi_applied_once=True,
        original_parent_coefficients_or_rows_rewritten=False,
        execution_kind="synthetic_cpu_control",
        actual_Qwen_training=False,
        GPU_operations=0,
        preserves_caller_dropout_mode=True,
        buffers_unchanged=True,
        successful_grad_buffers_follow_original_kernel=True,
        adaptive_pi_updates=0,
        feedback_or_C_formula_calls=0,
    )
