from __future__ import annotations

import argparse
import gc
import json
import math
import os
import statistics
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import get_context
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.phase1_batch_distribution_intervention import (
    CONTRAST_BASIS,
    HADAMARD_ORDER,
    NUMERIC_REPLAY_ROW_INDICES,
    _combine_coordinate_directions,
    _contrast_weights,
    _fidelity_summary,
    _linear_gradient_combination,
    _recover_centered_state_values,
    _sylvester_hadamard,
    _symmetric_probabilities,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    GRADIENT_ALIGNMENT_VERSION,
    _append_jsonl,
    _cluster_bootstrap_interval,
    _gradient_dot,
    _gradient_norm,
    _load_jsonl,
    _load_verified_gradient,
    _normalized_gradient_alignment,
    _sha256,
    _valid_hashed_row,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_distribution_intervention import (
    _rank_evidence,
    _restore_adapter,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_gradient_linearization_diagnostic import (
    _parameter_step_fidelity,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    _adapter_tensor_sha256,
    _baseline_lora_model,
    _evaluate,
    _load_records,
    _load_tokenizer,
    _read_json,
    _seed_everything,
    _write_json,
)
from trusted_synthesis.hashing import canonical_hash

GP_ABC_VERSION = "finance_gradient_projection_abc.v1"
GP_ABC_NUMERIC_SEED = 20260920
ESTIMATOR_IDS = ("gp_a_cosine", "gp_b_centered_dot", "gp_c_adamw_update")
ADAMW_BETAS = (0.9, 0.999)
ADAMW_EPSILON = 1e-8
ADAMW_WEIGHT_DECAY = 0.0
MAXIMUM_GRADIENT_NORM = 1.0
DEFAULT_EPSILON = 0.4
MAXIMUM_RECONSTRUCTION_RELATIVE_ERROR = 0.5


def _to_device(values: dict[str, Any], device: Any) -> dict[str, Any]:
    return {
        name: value.to(device=device, dtype=value.dtype)
        for name, value in values.items()
    }


def _cpu_contiguous(values: dict[str, Any]) -> dict[str, Any]:
    return {
        name: value.detach().cpu().contiguous()
        for name, value in values.items()
    }


def _adamw_descent_direction(
    gradient: dict[str, Any],
    *,
    learning_rate: float,
    epsilon: float,
    maximum_gradient_norm: float,
) -> dict[str, Any]:
    import torch

    if learning_rate <= 0 or epsilon <= 0 or maximum_gradient_norm <= 0:
        raise ValueError("GP-C optimizer constants must be positive")
    norm = _gradient_norm(gradient)
    if not norm > 0:
        raise ValueError("GP-C requires a nonzero state gradient")
    clip_scale = min(1.0, maximum_gradient_norm / norm)
    result = {}
    for name, value in gradient.items():
        scaled = value * clip_scale
        descent = learning_rate * scaled / (scaled.abs() + epsilon)
        if not torch.isfinite(descent).all():
            raise ValueError(f"GP-C produced a non-finite update:{name}")
        result[name] = descent.contiguous()
    return result


def _apply_descent_vector(model: Any, descent: dict[str, Any]) -> None:
    import torch

    parameters = {
        name: parameter
        for name, parameter in sorted(model.named_parameters())
        if parameter.requires_grad
    }
    if tuple(parameters) != tuple(descent):
        raise ValueError("GP-C update parameter manifest changed")
    with torch.no_grad():
        for name, parameter in parameters.items():
            value = descent[name]
            if value.shape != parameter.shape or not torch.isfinite(value).all():
                raise ValueError(f"GP-C invalid update tensor:{name}")
            parameter.add_(value.to(device=parameter.device, dtype=parameter.dtype), alpha=-1.0)


def _vector_fidelity(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, float]:
    if tuple(expected) != tuple(actual) or not expected:
        raise ValueError("GP-C fidelity parameter manifests differ")
    dot = 0.0
    expected_squared = 0.0
    actual_squared = 0.0
    error_squared = 0.0
    for name in expected:
        left = expected[name].double().reshape(-1)
        right = actual[name].double().reshape(-1)
        if left.shape != right.shape:
            raise ValueError(f"GP-C fidelity tensor shape changed:{name}")
        error = right - left
        dot += float((left * right).sum())
        expected_squared += float((left * left).sum())
        actual_squared += float((right * right).sum())
        error_squared += float((error * error).sum())
    expected_norm = math.sqrt(expected_squared)
    actual_norm = math.sqrt(actual_squared)
    if not expected_norm > 0 or not actual_norm > 0:
        raise ValueError("GP-C fidelity has a zero update")
    return {
        "cosine": dot / (expected_norm * actual_norm),
        "relative_error": math.sqrt(error_squared) / expected_norm,
        "norm_ratio": actual_norm / expected_norm,
    }


def _center(values: list[float], probabilities: list[float]) -> list[float]:
    if len(values) != len(probabilities) or not values:
        raise ValueError("GP estimator centering support is incomplete")
    mean = sum(
        value * probability
        for value, probability in zip(values, probabilities, strict=True)
    )
    centered = [value - mean for value in values]
    if not math.isclose(
        sum(
            value * probability
            for value, probability in zip(centered, probabilities, strict=True)
        ),
        0.0,
        abs_tol=1e-10,
    ):
        raise ValueError("GP estimator failed pi-centered replay")
    return centered


def _sign_agreement(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("GP sign agreement support is incomplete")
    matches = sum(
        (a == 0 and b == 0) or (a > 0 and b > 0) or (a < 0 and b < 0)
        for a, b in zip(left, right, strict=True)
    )
    return matches / len(left)


def _rank_with_sign(
    grouped: dict[str, list[dict[str, Any]]],
    *,
    estimator_field: str,
    target_field: str,
    seed: int,
) -> dict[str, Any]:
    evidence = _rank_evidence(
        grouped,
        estimator_field=estimator_field,
        target_field=target_field,
        seed=seed,
    )
    task_sign = []
    for values in grouped.values():
        ordered = sorted(values, key=lambda row: str(row["state_id"]))
        task_sign.append(
            _sign_agreement(
                [float(row[estimator_field]) for row in ordered],
                [float(row[target_field]) for row in ordered],
            )
        )
    evidence["macro_sign_agreement"] = statistics.fmean(task_sign)
    return evidence


def _prepare(args: argparse.Namespace) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_id)
    import torch
    from safetensors.torch import save_file

    gradient_dir = Path(args.gradient_dir).resolve()
    legacy_dir = Path(args.legacy_target_dir).resolve()
    gradient_plan = _read_json(gradient_dir / "plan.json")
    gradient_report = _read_json(gradient_dir / "report.json")
    evaluation_manifest = _read_json(gradient_dir / "evaluation_gradient_manifest.json")
    legacy_plan = _read_json(legacy_dir / "plan.json")
    legacy_report = _read_json(legacy_dir / "report.json")
    if gradient_plan.get("experiment_version") != GRADIENT_ALIGNMENT_VERSION:
        raise ValueError("GP A/B/C requires the current Gradient Projection plan")
    if gradient_report.get("plan_hash") != gradient_plan.get("plan_hash"):
        raise ValueError("GP A/B/C Gradient report failed plan replay")
    if evaluation_manifest.get("manifest_hash") != gradient_report.get(
        "evaluation_gradient_manifest_hash"
    ):
        raise ValueError("GP A/B/C evaluation-gradient manifest changed")
    if legacy_report.get("plan_hash") != legacy_plan.get("plan_hash"):
        raise ValueError("GP A/B/C legacy target failed plan replay")
    if gradient_report.get("task_count") != 30 or gradient_report.get("state_count") != 90:
        raise ValueError("GP A/B/C requires the frozen 30x3 population")

    protocol_path = Path(args.optimizer_protocol).resolve()
    protocol = _read_json(protocol_path)
    optimizer = protocol.get("optimizer", {})
    if (
        optimizer.get("optimizer_name") != "adamw"
        or optimizer.get("cold_start") is not True
        or optimizer.get("reuse_main_optimizer_state") is not False
        or float(optimizer.get("weight_decay", -1)) != ADAMW_WEIGHT_DECAY
        or protocol.get("beneficiary_model_state_id")
        != gradient_plan.get("beneficiary_model_state_id")
        or protocol.get("beneficiary_checkpoint_hash")
        != gradient_plan.get("beneficiary_checkpoint_hash")
    ):
        raise ValueError("GP-C source optimizer protocol is incompatible")
    learning_rate = float(optimizer["learning_rate"])
    if learning_rate <= 0:
        raise ValueError("GP-C source learning rate must be positive")

    aggregate_by_split = {
        str(row["split"]): row for row in evaluation_manifest["aggregate_gradients"]
    }
    if set(aggregate_by_split) != {"estimation", "validation"}:
        raise ValueError("GP A/B/C objective-gradient splits are incomplete")
    device = torch.device("cuda")
    objective_gradients = {
        split: _to_device(
            _load_verified_gradient(Path(row["file"]), str(row["sha256"])),
            device,
        )
        for split, row in aggregate_by_split.items()
    }
    objective_norms = {
        split: _gradient_norm(values) for split, values in objective_gradients.items()
    }
    source_rows = {
        (str(row["task_id"]), str(row["state_id"])): row
        for row in gradient_report["state_rows"]
    }
    legacy_targets = {
        (str(row["task_id"]), str(row["state_id"])): float(
            row["recovered_centered_contribution"]
        )
        for row in legacy_report["state_rows"]
    }
    output_dir = Path(args.output_dir).resolve()
    coordinate_dir = output_dir / "optimizer_coordinates"
    coordinate_dir.mkdir(parents=True, exist_ok=True)
    global_update: dict[str, Any] | None = None
    task_rows: list[dict[str, Any]] = []
    coordinate_artifacts: list[dict[str, Any]] = []

    for task in legacy_plan["task_rows"]:
        task_id = str(task["task_id"])
        probability_values = [float(value) for value in task["probabilities"]]
        if len(probability_values) != 3 or any(
            not math.isclose(value, 1.0 / 3.0, abs_tol=1e-12)
            for value in probability_values
        ):
            raise ValueError("GP A/B/C v1 requires uniform three-state support")
        task_marginal = float(task["task_marginal"])
        state_updates = []
        states = []
        for state in task["states"]:
            key = (task_id, str(state["state_id"]))
            source = source_rows.get(key)
            if source is None or key not in legacy_targets:
                raise ValueError("GP A/B/C state support changed")
            gradient = _to_device(
                _load_verified_gradient(
                    Path(source["state_gradient_file"]),
                    str(source["state_gradient_sha256"]),
                ),
                device,
            )
            update = _adamw_descent_direction(
                gradient,
                learning_rate=learning_rate,
                epsilon=ADAMW_EPSILON,
                maximum_gradient_norm=MAXIMUM_GRADIENT_NORM,
            )
            raw = {
                "task_id": task_id,
                "task_type": task["task_type"],
                "state_id": key[1],
                "strategy": source["strategy"],
                "state_gradient_norm": _gradient_norm(gradient),
                "legacy_sgd_target": legacy_targets[key],
            }
            for split in ("estimation", "validation"):
                dot, cosine = _normalized_gradient_alignment(
                    gradient,
                    objective_gradients[split],
                    left_norm=raw["state_gradient_norm"],
                    right_norm=objective_norms[split],
                )
                raw[f"{split}_gp_a_raw"] = cosine
                raw[f"{split}_gp_b_raw"] = dot
                raw[f"{split}_gp_c_raw"] = _gradient_dot(
                    update,
                    objective_gradients[split],
                )
            states.append(raw)
            state_updates.append(update)
            del gradient

        for estimator in ESTIMATOR_IDS:
            source_name = {
                "gp_a_cosine": "gp_a_raw",
                "gp_b_centered_dot": "gp_b_raw",
                "gp_c_adamw_update": "gp_c_raw",
            }[estimator]
            for split in ("estimation", "validation"):
                centered = _center(
                    [float(row[f"{split}_{source_name}"]) for row in states],
                    probability_values,
                )
                for row, value in zip(states, centered, strict=True):
                    row[f"{split}_{estimator}"] = value
        for row in states:
            for split in ("estimation", "validation"):
                row[f"{split}_gp_c_sgd_equivalent"] = (
                    float(legacy_plan["source_learning_rate"])
                    * float(row[f"{split}_gp_b_centered_dot"])
                )

        weighted_mean_update = _linear_gradient_combination(
            tuple(state_updates),
            tuple(task_marginal * value for value in probability_values),
        )
        if global_update is None:
            global_update = {
                name: value.clone() for name, value in weighted_mean_update.items()
            }
        else:
            for name in global_update:
                global_update[name].add_(weighted_mean_update[name])
        coordinate_indices = []
        for basis_index, basis in enumerate(CONTRAST_BASIS):
            coordinate_index = len(coordinate_artifacts)
            coordinate_indices.append(coordinate_index)
            coordinate = _linear_gradient_combination(
                tuple(state_updates),
                tuple(task_marginal * value for value in basis),
            )
            path = coordinate_dir / f"coordinate_{coordinate_index:02d}.safetensors"
            save_file(_cpu_contiguous(coordinate), path)
            coordinate_artifacts.append(
                {
                    "coordinate_index": coordinate_index,
                    "task_id": task_id,
                    "basis_index": basis_index,
                    "basis": list(basis),
                    "file": str(path),
                    "sha256": _sha256(path),
                    "update_norm": _gradient_norm(coordinate),
                }
            )
            del coordinate
        task_rows.append(
            {
                "task_id": task_id,
                "task_type": task["task_type"],
                "task_marginal": task_marginal,
                "probabilities": probability_values,
                "coordinate_indices": coordinate_indices,
                "states": states,
            }
        )
        del state_updates, weighted_mean_update
    if global_update is None or len(task_rows) != 30 or len(coordinate_artifacts) != 60:
        raise ValueError("GP A/B/C failed to construct the complete optimizer update space")
    global_path = output_dir / "optimizer_global_update.safetensors"
    save_file(_cpu_contiguous(global_update), global_path)

    design_rows = legacy_plan["design_rows"]
    if len(design_rows) != HADAMARD_ORDER + len(NUMERIC_REPLAY_ROW_INDICES):
        raise ValueError("GP A/B/C legacy orthogonal design changed")
    plan: dict[str, Any] = {
        "experiment_version": GP_ABC_VERSION,
        "role": "preregistered_estimator_family_validation",
        "gradient_plan_path": str(gradient_dir / "plan.json"),
        "gradient_plan_hash": gradient_plan["plan_hash"],
        "gradient_report_path": str(gradient_dir / "report.json"),
        "gradient_report_hash": gradient_report["report_hash"],
        "evaluation_gradient_manifest_hash": evaluation_manifest["manifest_hash"],
        "legacy_target_plan_hash": legacy_plan["plan_hash"],
        "legacy_target_report_hash": legacy_report["report_hash"],
        "optimizer_protocol_path": str(protocol_path),
        "optimizer_protocol_sha256": _sha256(protocol_path),
        "optimizer_source_contract_id": optimizer["contract_id"],
        "optimizer_contract": {
            "optimizer_name": "adamw",
            "projection_step_count": 1,
            "source_protocol_step_count": int(optimizer["step_count"]),
            "state_policy": "cold_start_independent_state_update",
            "learning_rate": learning_rate,
            "betas": list(ADAMW_BETAS),
            "epsilon": ADAMW_EPSILON,
            "weight_decay": ADAMW_WEIGHT_DECAY,
            "maximum_gradient_norm": MAXIMUM_GRADIENT_NORM,
            "main_optimizer_continuation_state_available": False,
        },
        "estimator_contracts": {
            "gp_a_cosine": "pi_centered_cosine_of_state_and_objective_loss_gradients",
            "gp_b_centered_dot": "objective_dot_state_gradient_minus_pi_mean_gradient",
            "gp_c_adamw_update": "objective_dot_cold_start_adamw_descent_minus_pi_mean_descent",
            "gp_c_sgd_equivalent": "source_sgd_learning_rate_times_gp_b",
        },
        "model_dir": gradient_plan["model_dir"],
        "base_model_manifest_hash": gradient_plan["base_model_manifest_hash"],
        "beneficiary_adapter_dir": gradient_plan["beneficiary_adapter_dir"],
        "beneficiary_adapter_tensor_sha256": gradient_plan[
            "beneficiary_adapter_tensor_sha256"
        ],
        "beneficiary_model_state_id": gradient_plan["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": gradient_plan["beneficiary_checkpoint_hash"],
        "source_records_path": gradient_plan["source_records_path"],
        "source_records_sha256": gradient_plan["source_records_sha256"],
        "final_test_record_ids": gradient_plan["final_test_record_ids"],
        "final_test_set_id": gradient_plan["final_test_set_id"],
        "objective_gradient_splits": {
            split: {
                "file": row["file"],
                "sha256": row["sha256"],
                "record_ids": row["record_ids"],
                "gradient_norm": row["gradient_norm"],
            }
            for split, row in aggregate_by_split.items()
        },
        "task_rows": task_rows,
        "task_count": len(task_rows),
        "state_count": sum(len(row["states"]) for row in task_rows),
        "coordinate_artifacts": coordinate_artifacts,
        "coordinate_count": len(coordinate_artifacts),
        "global_update_artifact": {
            "file": str(global_path),
            "sha256": _sha256(global_path),
            "update_norm": _gradient_norm(global_update),
        },
        "design_rows": design_rows,
        "orthogonal_design_row_count": HADAMARD_ORDER,
        "numeric_replay_row_indices": list(NUMERIC_REPLAY_ROW_INDICES),
        "distribution_epsilon": args.epsilon,
        "maximum_reconstruction_relative_error": MAXIMUM_RECONSTRUCTION_RELATIVE_ERROR,
        "final_test_objective_accessed": False,
        "claim_boundary": (
            "GP-A/B/C are candidate first-order approximations. GP-C uses a new one-step "
            "cold-start AdamW projection contract because the main optimizer continuation "
            "state was not retained. No estimator may be promoted without the matching "
            "independent target, numeric fidelity, and frozen rank gates."
        ),
    }
    plan["plan_hash"] = canonical_hash(plan, prefix="finance_gp_abc_plan:")
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "plan.json", plan)
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
    del objective_gradients, global_update
    gc.collect()
    torch.cuda.empty_cache()


def _preflight(args: argparse.Namespace) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_id)
    import torch
    from safetensors.torch import save_file

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    if plan.get("experiment_version") != GP_ABC_VERSION:
        raise ValueError("GP A/B/C preflight requires a current plan")
    started = time.monotonic()
    _seed_everything(GP_ABC_NUMERIC_SEED)
    torch.cuda.reset_peak_memory_stats()
    model = _baseline_lora_model(
        Path(plan["model_dir"]),
        Path(plan["beneficiary_adapter_dir"]),
    )
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("GP A/B/C preflight loaded another Adapter")
    parameters = {
        name: parameter
        for name, parameter in sorted(model.named_parameters())
        if parameter.requires_grad
    }
    initial = {name: value.detach().clone() for name, value in parameters.items()}
    first_state = plan["task_rows"][0]["states"][0]
    source_report = _read_json(Path(plan["gradient_report_path"]))
    source = next(
        row
        for row in source_report["state_rows"]
        if row["task_id"] == first_state["task_id"]
        and row["state_id"] == first_state["state_id"]
    )
    gradient = _to_device(
        _load_verified_gradient(
            Path(source["state_gradient_file"]),
            str(source["state_gradient_sha256"]),
        ),
        torch.device("cuda"),
    )
    contract = plan["optimizer_contract"]
    expected = _adamw_descent_direction(
        gradient,
        learning_rate=float(contract["learning_rate"]),
        epsilon=float(contract["epsilon"]),
        maximum_gradient_norm=float(contract["maximum_gradient_norm"]),
    )
    for name, parameter in parameters.items():
        parameter.grad = gradient[name].to(device=parameter.device, dtype=parameter.dtype).clone()
    torch.nn.utils.clip_grad_norm_(
        tuple(parameters.values()),
        float(contract["maximum_gradient_norm"]),
    )
    optimizer = torch.optim.AdamW(
        tuple(parameters.values()),
        lr=float(contract["learning_rate"]),
        betas=tuple(float(value) for value in contract["betas"]),
        eps=float(contract["epsilon"]),
        weight_decay=float(contract["weight_decay"]),
        foreach=False,
    )
    if optimizer.state:
        raise ValueError("GP-C AdamW preflight did not start from empty state")
    optimizer.step()
    actual = {name: initial[name] - parameter.detach() for name, parameter in parameters.items()}
    optimizer_formula_fidelity = _vector_fidelity(expected, actual)
    with torch.no_grad():
        for name, parameter in parameters.items():
            parameter.copy_(initial[name])
            parameter.grad = None
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("GP-C formula preflight failed Adapter restoration")

    global_update = _to_device(
        _load_verified_gradient(
            Path(plan["global_update_artifact"]["file"]),
            str(plan["global_update_artifact"]["sha256"]),
        ),
        torch.device("cuda"),
    )
    baseline = {
        name: initial[name] - global_update[name].to(dtype=initial[name].dtype)
        for name in initial
    }
    coordinate_updates = tuple(
        _to_device(
            _load_verified_gradient(Path(row["file"]), str(row["sha256"])),
            torch.device("cuda"),
        )
        for row in plan["coordinate_artifacts"]
    )
    direction_dir = output_dir / "optimizer_batch_directions"
    direction_dir.mkdir(parents=True, exist_ok=True)
    direction_artifacts = []
    fidelity_rows = []
    for design_row in plan["design_rows"][:HADAMARD_ORDER]:
        signs = tuple(int(value) for value in design_row["signs"])
        direction = _combine_coordinate_directions(coordinate_updates, signs)
        path = direction_dir / f"direction_{design_row['design_row_index']:02d}.safetensors"
        save_file(_cpu_contiguous(direction), path)
        direction_artifacts.append(
            {
                "design_row_index": design_row["design_row_index"],
                "row_id": design_row["row_id"],
                "file": str(path),
                "sha256": _sha256(path),
                "update_norm": _gradient_norm(direction),
            }
        )
        negative = {name: -value for name, value in direction.items()}
        for label, value in (("plus", direction), ("minus", negative)):
            row: dict[str, Any] = dict(
                _parameter_step_fidelity(
                    initial,
                    baseline,
                    global_update,
                    value,
                    learning_rate=1.0,
                    directional_scale=float(plan["distribution_epsilon"]),
                )
            )
            row.update(
                {
                    "design_row_index": design_row["design_row_index"],
                    "intervention_sign": label,
                }
            )
            fidelity_rows.append(row)
        del direction, negative
    fidelity_summary = _fidelity_summary(fidelity_rows)
    formula_passed = bool(
        optimizer_formula_fidelity["cosine"] >= 0.999
        and optimizer_formula_fidelity["relative_error"] <= 0.01
    )
    status = "passed" if formula_passed and fidelity_summary["passes"] else "failed"
    report: dict[str, Any] = {
        "experiment_version": GP_ABC_VERSION,
        "plan_hash": plan["plan_hash"],
        "status": status,
        "optimizer_formula_fidelity": optimizer_formula_fidelity,
        "optimizer_formula_passed": formula_passed,
        "parameter_storage_fidelity": fidelity_summary,
        "direction_artifacts": direction_artifacts,
        "direction_manifest_hash": canonical_hash(
            direction_artifacts,
            prefix="finance_gp_c_direction_manifest:",
        ),
        "numeric_seed": GP_ABC_NUMERIC_SEED,
        "final_test_objective_accessed": False,
        "runtime_seconds": time.monotonic() - started,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
        "blockers": [] if status == "passed" else ["optimizer_update_numeric_fidelity_failed"],
    }
    report["preflight_hash"] = canonical_hash(report, prefix="finance_gp_abc_preflight:")
    _write_json(output_dir / "preflight.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    del model, gradient, expected, actual, global_update, coordinate_updates
    gc.collect()
    torch.cuda.empty_cache()


def _worker(args: argparse.Namespace) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_id)
    import torch
    from peft import get_peft_model_state_dict

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    preflight = _read_json(output_dir / "preflight.json")
    if preflight.get("plan_hash") != plan.get("plan_hash") or preflight.get("status") != "passed":
        raise ValueError("GP A/B/C worker requires a passing preflight")
    if _sha256(Path(plan["source_records_path"])) != plan["source_records_sha256"]:
        raise ValueError("GP A/B/C source records changed")
    rows = [
        row
        for index, row in enumerate(plan["design_rows"])
        if index % args.partition_count == args.partition_index
    ]
    worker_path = output_dir / "workers" / f"partition_{args.partition_index}.jsonl"
    completed = {
        str(row["row_id"])
        for row in _load_jsonl(worker_path)
        if row.get("status") == "passed"
        and _valid_hashed_row(row, prefix="finance_gp_c_target_result:")
    }
    directions = {
        int(row["design_row_index"]): row for row in preflight["direction_artifacts"]
    }
    source_records = _load_records(Path(plan["source_records_path"]))
    final_records = tuple(source_records[value] for value in plan["final_test_record_ids"])
    _seed_everything(GP_ABC_NUMERIC_SEED)
    torch.cuda.reset_peak_memory_stats()
    tokenizer = _load_tokenizer(Path(plan["model_dir"]))
    model = _baseline_lora_model(
        Path(plan["model_dir"]),
        Path(plan["beneficiary_adapter_dir"]),
    )
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("GP A/B/C worker loaded another Adapter")
    baseline_adapter_state = {
        name: tensor.detach().cpu().clone()
        for name, tensor in get_peft_model_state_dict(model).items()
    }
    global_update = _load_verified_gradient(
        Path(plan["global_update_artifact"]["file"]),
        str(plan["global_update_artifact"]["sha256"]),
    )
    _restore_adapter(model, baseline_adapter_state)
    _apply_descent_vector(model, global_update)
    baseline_performance, baseline_loss, baseline_tokens = _evaluate(
        model,
        tokenizer,
        final_records,
    )
    baseline_adapter_hash = _adapter_tensor_sha256(model)
    started = time.monotonic()
    completed_now = 0
    for row in rows:
        if str(row["row_id"]) in completed:
            continue
        artifact = directions[int(row["design_row_index"])]
        direction = _load_verified_gradient(Path(artifact["file"]), str(artifact["sha256"]))
        plus = {
            name: value.clone().add_(direction[name], alpha=float(plan["distribution_epsilon"]))
            for name, value in global_update.items()
        }
        minus = {
            name: value.clone().add_(direction[name], alpha=-float(plan["distribution_epsilon"]))
            for name, value in global_update.items()
        }
        _seed_everything(GP_ABC_NUMERIC_SEED)
        _restore_adapter(model, baseline_adapter_state)
        _apply_descent_vector(model, plus)
        plus_performance, plus_loss, plus_tokens = _evaluate(model, tokenizer, final_records)
        plus_hash = _adapter_tensor_sha256(model)
        _seed_everything(GP_ABC_NUMERIC_SEED)
        _restore_adapter(model, baseline_adapter_state)
        _apply_descent_vector(model, minus)
        minus_performance, minus_loss, minus_tokens = _evaluate(model, tokenizer, final_records)
        minus_hash = _adapter_tensor_sha256(model)
        if plus_tokens != baseline_tokens or minus_tokens != baseline_tokens:
            raise ValueError("GP-C target changed final-test token support")
        result: dict[str, Any] = {
            "experiment_version": GP_ABC_VERSION,
            "plan_hash": plan["plan_hash"],
            "preflight_hash": preflight["preflight_hash"],
            "row_id": row["row_id"],
            "design_row_index": row["design_row_index"],
            "role": row["role"],
            "replay_index": row.get("replay_index"),
            "partition_index": args.partition_index,
            "partition_count": args.partition_count,
            "gpu_id": args.gpu_id,
            "status": "passed",
            "distribution_epsilon": plan["distribution_epsilon"],
            "baseline_performance": baseline_performance,
            "baseline_loss": baseline_loss,
            "plus_performance": plus_performance,
            "plus_loss": plus_loss,
            "minus_performance": minus_performance,
            "minus_loss": minus_loss,
            "central_directional_derivative": (
                (plus_performance - minus_performance)
                / (2.0 * float(plan["distribution_epsilon"]))
            ),
            "final_test_supervised_tokens": baseline_tokens,
            "baseline_adapter_tensor_sha256": baseline_adapter_hash,
            "plus_adapter_tensor_sha256": plus_hash,
            "minus_adapter_tensor_sha256": minus_hash,
            "direction_sha256": artifact["sha256"],
            "numeric_seed": GP_ABC_NUMERIC_SEED,
        }
        result["result_hash"] = canonical_hash(
            result,
            prefix="finance_gp_c_target_result:",
        )
        _append_jsonl(worker_path, result)
        completed_now += 1
        del direction, plus, minus
    report = {
        "plan_hash": plan["plan_hash"],
        "preflight_hash": preflight["preflight_hash"],
        "partition_index": args.partition_index,
        "partition_count": args.partition_count,
        "gpu_id": args.gpu_id,
        "assigned_count": len(rows),
        "completed_now": completed_now,
        "runtime_seconds": time.monotonic() - started,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
    }
    _write_json(
        output_dir / "workers" / f"partition_{args.partition_index}_report.json",
        report,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    del model, global_update, baseline_adapter_state
    gc.collect()
    torch.cuda.empty_cache()


def _estimator_evidence(
    grouped: dict[str, list[dict[str, Any]]],
    *,
    estimator_id: str,
    target_field: str,
    seed: int,
) -> dict[str, Any]:
    estimation_field = f"estimation_{estimator_id}"
    validation_field = f"validation_{estimator_id}"
    return {
        "cross_split": _rank_with_sign(
            grouped,
            estimator_field=estimation_field,
            target_field=validation_field,
            seed=seed,
        ),
        "estimation_vs_target": _rank_with_sign(
            grouped,
            estimator_field=estimation_field,
            target_field=target_field,
            seed=seed + 10,
        ),
        "validation_vs_target": _rank_with_sign(
            grouped,
            estimator_field=validation_field,
            target_field=target_field,
            seed=seed + 20,
        ),
    }


def _sgd_equivalence_audit(
    task_rows: list[dict[str, Any]],
    *,
    learning_rate: float,
) -> dict[str, Any]:
    if learning_rate <= 0:
        raise ValueError("GP-C SGD equivalence requires a positive learning rate")
    errors: list[float] = []
    ranking_matches: list[bool] = []
    for task in task_rows:
        states = list(task["states"])
        for split in ("estimation", "validation"):
            gp_b = [float(row[f"{split}_gp_b_centered_dot"]) for row in states]
            gp_c = [float(row[f"{split}_gp_c_sgd_equivalent"]) for row in states]
            expected = [learning_rate * value for value in gp_b]
            errors.extend(
                abs(left - right)
                for left, right in zip(gp_c, expected, strict=True)
            )
            state_ids = [str(row["state_id"]) for row in states]
            left_order = sorted(
                range(len(states)),
                key=lambda index: (gp_c[index], state_ids[index]),
            )
            right_order = sorted(
                range(len(states)),
                key=lambda index: (expected[index], state_ids[index]),
            )
            ranking_matches.append(left_order == right_order)
    return {
        "learning_rate": learning_rate,
        "comparison_count": len(errors),
        "maximum_absolute_scaling_error": max(errors, default=math.inf),
        "all_task_split_rankings_identical": all(ranking_matches),
        "claim_boundary": (
            "Under plain SGD with a positive scalar learning rate, GP-C is a positive "
            "rescaling of GP-B and therefore provides no independent ranking evidence."
        ),
    }


def _distribution_contract_replay(plan: dict[str, Any]) -> dict[str, Any]:
    minimum_probability = math.inf
    maximum_mass_error = 0.0
    evaluation_count = 0
    for task in plan["task_rows"]:
        first, second = (int(value) for value in task["coordinate_indices"])
        probabilities = tuple(float(value) for value in task["probabilities"])
        for design in plan["design_rows"][:HADAMARD_ORDER]:
            signs = tuple(int(value) for value in design["signs"])
            weights = _contrast_weights(signs[first], signs[second])
            plus, minus = _symmetric_probabilities(
                probabilities,
                weights,
                epsilon=float(plan["distribution_epsilon"]),
            )
            minimum_probability = min(minimum_probability, *plus, *minus)
            maximum_mass_error = max(
                maximum_mass_error,
                abs(sum(plus) - 1.0),
                abs(sum(minus) - 1.0),
            )
            evaluation_count += 1
    return {
        "task_design_evaluation_count": evaluation_count,
        "minimum_perturbed_probability": minimum_probability,
        "maximum_probability_mass_error": maximum_mass_error,
        "support_preserved": bool(minimum_probability > 0),
        "task_marginal_policy": "fixed_uniform_over_30_tasks",
    }


def _paired_estimator_deltas(
    evidence: dict[str, dict[str, Any]],
    *,
    baseline_estimator: str,
    candidate_estimator: str,
    seed: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for comparison in ("estimation_vs_target", "validation_vs_target"):
        baseline_rows = {
            str(row["task_id"]): row
            for row in evidence[baseline_estimator][comparison]["task_rows"]
        }
        candidate_rows = {
            str(row["task_id"]): row
            for row in evidence[candidate_estimator][comparison]["task_rows"]
        }
        if baseline_rows.keys() != candidate_rows.keys():
            raise ValueError("GP estimator comparison task support changed")
        metric_rows: dict[str, Any] = {}
        for offset, metric in enumerate(
            ("spearman", "pairwise_concordance", "winner_agreement")
        ):
            deltas = [
                float(candidate_rows[task_id][metric])
                - float(baseline_rows[task_id][metric])
                for task_id in sorted(baseline_rows)
            ]
            metric_rows[metric] = {
                "candidate_minus_baseline_mean": statistics.fmean(deltas),
                "candidate_minus_baseline_ci95": _cluster_bootstrap_interval(
                    deltas,
                    samples=5000,
                    seed=seed + 10 * offset,
                ),
            }
        result[comparison] = metric_rows
    return {
        "baseline_estimator": baseline_estimator,
        "candidate_estimator": candidate_estimator,
        "task_count": len(
            evidence[baseline_estimator]["estimation_vs_target"]["task_rows"]
        ),
        "paired_deltas": result,
    }


def _aggregate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    preflight = _read_json(output_dir / "preflight.json")
    if preflight.get("plan_hash") != plan.get("plan_hash") or preflight.get("status") != "passed":
        raise ValueError("GP A/B/C aggregate requires a passing preflight")
    legacy_dir = Path(args.legacy_target_dir).resolve()
    legacy_plan = _read_json(legacy_dir / "plan.json")
    legacy_preflight = _read_json(legacy_dir / "preflight.json")
    legacy_report = _read_json(legacy_dir / "report.json")
    gradient_report = _read_json(Path(plan["gradient_report_path"]))
    if (
        legacy_plan.get("plan_hash") != plan.get("legacy_target_plan_hash")
        or legacy_preflight.get("plan_hash") != legacy_plan.get("plan_hash")
        or legacy_report.get("plan_hash") != legacy_plan.get("plan_hash")
        or legacy_report.get("report_hash") != plan.get("legacy_target_report_hash")
        or gradient_report.get("report_hash") != plan.get("gradient_report_hash")
    ):
        raise ValueError("GP A/B/C frozen source identity changed")
    rows = [
        row
        for path in sorted((output_dir / "workers").glob("partition_*.jsonl"))
        for row in _load_jsonl(path)
    ]
    if len(rows) != len(plan["design_rows"]):
        raise ValueError("GP-C optimizer target matrix is incomplete")
    if any(
        not _valid_hashed_row(row, prefix="finance_gp_c_target_result:") for row in rows
    ):
        raise ValueError("GP-C optimizer target identity failed replay")
    expected_direction_hashes = {
        int(row["design_row_index"]): str(row["sha256"])
        for row in preflight["direction_artifacts"]
    }
    if any(
        row.get("status") != "passed"
        or row.get("plan_hash") != plan["plan_hash"]
        or row.get("preflight_hash") != preflight["preflight_hash"]
        or str(row.get("direction_sha256"))
        != expected_direction_hashes.get(int(row["design_row_index"]))
        for row in rows
    ):
        raise ValueError("GP-C worker contract identity changed")
    baseline_hashes = {
        str(row["baseline_adapter_tensor_sha256"]) for row in rows
    }
    baseline_losses = {float(row["baseline_loss"]) for row in rows}
    baseline_performances = {float(row["baseline_performance"]) for row in rows}
    baseline_tokens = {int(row["final_test_supervised_tokens"]) for row in rows}
    if (
        len(baseline_hashes) != 1
        or len(baseline_losses) != 1
        or len(baseline_performances) != 1
        or len(baseline_tokens) != 1
        or any(
            row["plus_adapter_tensor_sha256"] == row["minus_adapter_tensor_sha256"]
            for row in rows
        )
    ):
        raise ValueError("GP-C multi-worker baseline or intervention replay changed")
    worker_identity_replay = {
        "result_count": len(rows),
        "plan_hash_count": 1,
        "preflight_hash_count": 1,
        "baseline_adapter_hash": next(iter(baseline_hashes)),
        "baseline_loss": next(iter(baseline_losses)),
        "baseline_performance": next(iter(baseline_performances)),
        "final_test_supervised_tokens": next(iter(baseline_tokens)),
        "all_direction_hashes_match": True,
        "all_plus_minus_adapter_hashes_distinct": True,
    }
    by_id = {str(row["row_id"]): row for row in rows}
    if len(by_id) != len(rows) or set(by_id) != {
        str(row["row_id"]) for row in plan["design_rows"]
    }:
        raise ValueError("GP-C optimizer target support changed")
    ordered_design = [
        by_id[str(row["row_id"])]
        for row in plan["design_rows"]
        if row["role"] == "orthogonal_design"
    ]
    replay_ranges = []
    for design_index in plan["numeric_replay_row_indices"]:
        values = [
            float(row["central_directional_derivative"])
            for row in rows
            if int(row["design_row_index"]) == int(design_index)
        ]
        replay_ranges.append(max(values) - min(values))
    maximum_replay_range = max(replay_ranges)
    if maximum_replay_range != 0.0:
        raise ValueError("GP-C optimizer target replay is not deterministic")
    hadamard = _sylvester_hadamard(HADAMARD_ORDER)
    observed = [float(row["central_directional_derivative"]) for row in ordered_design]
    coordinate_values = [
        sum(hadamard[row][column] * observed[row] for row in range(HADAMARD_ORDER))
        / HADAMARD_ORDER
        for column in range(plan["coordinate_count"])
    ]
    reconstructed = [
        sum(
            hadamard[row][column] * coordinate_values[column]
            for column in range(plan["coordinate_count"])
        )
        for row in range(HADAMARD_ORDER)
    ]
    residual_norm = math.sqrt(
        sum((a - b) ** 2 for a, b in zip(observed, reconstructed, strict=True))
    )
    observed_norm = math.sqrt(sum(value * value for value in observed))
    reconstruction_relative_error = residual_norm / observed_norm if observed_norm else math.inf

    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    state_rows = []
    conservative_gp_a = {
        (str(row["task_id"]), str(row["state_id"])): row
        for row in gradient_report["state_rows"]
    }
    for task in plan["task_rows"]:
        first, second = task["coordinate_indices"]
        recovered = _recover_centered_state_values(
            coordinate_values[first],
            coordinate_values[second],
            task_marginal=float(task["task_marginal"]),
        )
        for source, target in zip(task["states"], recovered, strict=True):
            key = (str(task["task_id"]), str(source["state_id"]))
            frozen_source = conservative_gp_a.get(key)
            if frozen_source is None:
                raise ValueError("GP A/B/C conservative GP-A support changed")
            row = {
                **source,
                "optimizer_target": target,
                "estimation_gp_a_conservative": frozen_source[
                    "estimation_conservative_centered_contribution"
                ],
                "validation_gp_a_conservative": frozen_source[
                    "validation_conservative_centered_contribution"
                ],
            }
            state_rows.append(row)
            grouped[str(task["task_id"])].append(row)

    estimator_evidence = {
        estimator_id: _estimator_evidence(
            grouped,
            estimator_id=estimator_id,
            target_field="optimizer_target",
            seed=GP_ABC_NUMERIC_SEED + 100 * index,
        )
        for index, estimator_id in enumerate(ESTIMATOR_IDS, start=1)
    }
    legacy_evidence = {
        estimator_id: _estimator_evidence(
            grouped,
            estimator_id=estimator_id,
            target_field="legacy_sgd_target",
            seed=GP_ABC_NUMERIC_SEED + 1000 + 100 * index,
        )
        for index, estimator_id in enumerate(ESTIMATOR_IDS, start=1)
    }
    legacy_evidence["gp_c_sgd_equivalent"] = _estimator_evidence(
        grouped,
        estimator_id="gp_c_sgd_equivalent",
        target_field="legacy_sgd_target",
        seed=GP_ABC_NUMERIC_SEED + 1500,
    )
    conservative_gp_a_evidence = _estimator_evidence(
        grouped,
        estimator_id="gp_a_conservative",
        target_field="optimizer_target",
        seed=GP_ABC_NUMERIC_SEED + 1800,
    )
    if not math.isclose(
        float(conservative_gp_a_evidence["cross_split"]["macro_task_spearman"]),
        float(gradient_report["macro_task_spearman"]),
        abs_tol=1e-12,
    ):
        raise ValueError("GP A/B/C failed to replay the historical conservative GP-A")
    norm_evidence = {
        "optimizer_target": _rank_with_sign(
            grouped,
            estimator_field="state_gradient_norm",
            target_field="optimizer_target",
            seed=GP_ABC_NUMERIC_SEED + 2000,
        ),
        "legacy_sgd_target": _rank_with_sign(
            grouped,
            estimator_field="state_gradient_norm",
            target_field="legacy_sgd_target",
            seed=GP_ABC_NUMERIC_SEED + 2100,
        ),
    }
    source_learning_rate = float(legacy_plan["source_learning_rate"])
    selected_learning_rate = float(legacy_preflight["selected_learning_rate"])
    fidelity_by_learning_rate = {
        float(row["learning_rate"]): row
        for row in legacy_preflight["candidate_summaries"]
    }
    if (
        source_learning_rate not in fidelity_by_learning_rate
        or selected_learning_rate not in fidelity_by_learning_rate
    ):
        raise ValueError("GP A/B/C legacy learning-rate fidelity is incomplete")
    legacy_sgd_contract = {
        "source_learning_rate": source_learning_rate,
        "selected_learning_rate": selected_learning_rate,
        "production_scale_matched": bool(legacy_preflight["production_scale_matched"]),
        "source_learning_rate_fidelity": fidelity_by_learning_rate[
            source_learning_rate
        ],
        "selected_learning_rate_fidelity": fidelity_by_learning_rate[
            selected_learning_rate
        ],
        "source_learning_rate_target_status": (
            "not_evaluated_due_numeric_fidelity_failure"
            if not fidelity_by_learning_rate[source_learning_rate]["passes"]
            else "evaluated"
        ),
        "selected_target_used_for_legacy_evidence": True,
    }
    sgd_equivalence = _sgd_equivalence_audit(
        plan["task_rows"],
        learning_rate=source_learning_rate,
    )
    estimator_authorization = {}
    for estimator_id, evidence in estimator_evidence.items():
        estimator_authorization[estimator_id] = bool(
            evidence["cross_split"]["passes_rank_gate"]
            and evidence["estimation_vs_target"]["passes_rank_gate"]
            and evidence["validation_vs_target"]["passes_rank_gate"]
            and reconstruction_relative_error <= plan["maximum_reconstruction_relative_error"]
            and maximum_replay_range == 0.0
        )
    estimator_comparisons = {
        "gp_b_minus_gp_a": _paired_estimator_deltas(
            estimator_evidence,
            baseline_estimator="gp_a_cosine",
            candidate_estimator="gp_b_centered_dot",
            seed=GP_ABC_NUMERIC_SEED + 3000,
        ),
        "gp_c_minus_gp_a": _paired_estimator_deltas(
            estimator_evidence,
            baseline_estimator="gp_a_cosine",
            candidate_estimator="gp_c_adamw_update",
            seed=GP_ABC_NUMERIC_SEED + 4000,
        ),
        "gp_c_minus_gp_b": _paired_estimator_deltas(
            estimator_evidence,
            baseline_estimator="gp_b_centered_dot",
            candidate_estimator="gp_c_adamw_update",
            seed=GP_ABC_NUMERIC_SEED + 5000,
        ),
    }
    distribution_replay = _distribution_contract_replay(plan)
    if (
        not distribution_replay["support_preserved"]
        or distribution_replay["maximum_probability_mass_error"] > 1e-12
    ):
        raise ValueError("GP-C optimizer target violates the conditional distribution contract")
    optimizer_state_blocker = not bool(
        plan["optimizer_contract"]["main_optimizer_continuation_state_available"]
    )
    report: dict[str, Any] = {
        "experiment_version": GP_ABC_VERSION,
        "plan_hash": plan["plan_hash"],
        "preflight_hash": preflight["preflight_hash"],
        "task_count": plan["task_count"],
        "state_count": plan["state_count"],
        "coordinate_count": plan["coordinate_count"],
        "maximum_numeric_replay_range": maximum_replay_range,
        "reconstruction_relative_error": reconstruction_relative_error,
        "estimator_evidence": estimator_evidence,
        "legacy_sgd_target_evidence": legacy_evidence,
        "current_conservative_gp_a_diagnostic": conservative_gp_a_evidence,
        "gradient_norm_target_evidence": norm_evidence,
        "legacy_sgd_contract": legacy_sgd_contract,
        "gp_c_sgd_equivalence": sgd_equivalence,
        "estimator_rank_gate_passed": estimator_authorization,
        "estimator_paired_comparisons": estimator_comparisons,
        "distribution_contract_replay": distribution_replay,
        "worker_identity_replay": worker_identity_replay,
        "production_authorized": False,
        "production_blockers": [
            "main_optimizer_continuation_state_unavailable"
            if optimizer_state_blocker
            else "production_authorization_not_issued",
            *[
                f"{estimator_id}_rank_gate_failed"
                for estimator_id, passed in estimator_authorization.items()
                if not passed
            ],
        ],
        "optimizer_contract": plan["optimizer_contract"],
        "baseline_loss": statistics.fmean(float(row["baseline_loss"]) for row in rows),
        "baseline_performance": statistics.fmean(
            float(row["baseline_performance"]) for row in rows
        ),
        "final_test_supervised_tokens": int(rows[0]["final_test_supervised_tokens"]),
        "final_test_objective_accessed": True,
        "state_rows": state_rows,
        "coordinate_values": coordinate_values,
        "status": "passed" if any(estimator_authorization.values()) else "failed",
        "claim_boundary": (
            "This comparison validates GP-A/B/C on a common frozen support. The optimizer-aware "
            "target matches a one-step cold-start AdamW projection contract, not unavailable "
            "continuation state from the beneficiary's original optimizer. Rank evidence may "
            "validate an approximation family but cannot by itself issue production credentials."
        ),
    }
    report["report_hash"] = canonical_hash(report, prefix="finance_gp_abc_report:")
    _write_json(output_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate GP-A/B/C on a shared finance target")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--gradient-dir", required=True)
    prepare.add_argument("--legacy-target-dir", required=True)
    prepare.add_argument("--optimizer-protocol", required=True)
    prepare.add_argument("--output-dir", required=True)
    prepare.add_argument("--epsilon", type=float, default=DEFAULT_EPSILON)
    prepare.add_argument("--gpu-id", type=int, default=0)
    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--output-dir", required=True)
    preflight.add_argument("--gpu-id", type=int, default=0)
    worker = subparsers.add_parser("worker")
    worker.add_argument("--output-dir", required=True)
    worker.add_argument("--gpu-id", type=int, required=True)
    worker.add_argument("--partition-index", type=int, required=True)
    worker.add_argument("--partition-count", type=int, required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--output-dir", required=True)
    run.add_argument("--gpu-ids", type=int, nargs="+", required=True)
    aggregate = subparsers.add_parser("aggregate")
    aggregate.add_argument("--output-dir", required=True)
    aggregate.add_argument("--legacy-target-dir", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "prepare":
        _prepare(args)
    elif args.command == "preflight":
        _preflight(args)
    elif args.command == "worker":
        _worker(args)
    elif args.command == "run":
        partition_count = len(args.gpu_ids)
        context = get_context("spawn")
        reports = []
        with ProcessPoolExecutor(max_workers=partition_count, mp_context=context) as executor:
            futures = {
                executor.submit(
                    _worker,
                    argparse.Namespace(
                        output_dir=args.output_dir,
                        gpu_id=gpu_id,
                        partition_index=index,
                        partition_count=partition_count,
                    ),
                ): index
                for index, gpu_id in enumerate(args.gpu_ids)
            }
            for future in as_completed(futures):
                future.result()
                reports.append(futures[future])
        print(json.dumps({"completed_partitions": sorted(reports)}, indent=2))
    else:
        _aggregate(args)


if __name__ == "__main__":
    main()
