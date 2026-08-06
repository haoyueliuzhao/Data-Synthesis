from __future__ import annotations

import argparse
import gc
import json
import math
import statistics
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    OBJECTIVE_GRADIENT_EXECUTION_MODE,
    _gradient_dot,
    _gradient_norm,
    _gradient_parameter_manifest,
    _load_execution_model,
    _load_records,
    _load_verified_gradient,
    _record_gradient,
    _seed_everything,
    _sha256,
    _weighted_gradient,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    _adapter_tensor_sha256,
    _load_tokenizer,
    _read_json,
    _write_json,
)
from trusted_synthesis.hashing import canonical_hash

GP_C_PROXY_VERSION = "finance_gradient_projection_gp_c.v5"
CALIBRATION_FLOOR = 1e-12


def _replay_hash(
    value: Mapping[str, Any],
    *,
    field: str,
    prefix: str,
    label: str,
) -> str:
    payload = dict(value)
    observed = payload.pop(field, None)
    expected = canonical_hash(payload, prefix=prefix)
    if observed != expected:
        raise ValueError(f"{label} identity changed")
    return str(observed)


def _cold_start_adamw_update(
    gradient: Mapping[str, Any],
    *,
    learning_rate: float,
    epsilon: float,
    maximum_gradient_norm: float,
) -> dict[str, Any]:
    if learning_rate <= 0 or epsilon <= 0 or maximum_gradient_norm <= 0:
        raise ValueError("GP-C optimizer constants must be positive")
    frozen = dict(gradient)
    norm = _gradient_norm(frozen)
    clip_scale = min(1.0, maximum_gradient_norm / norm)
    updates = {
        name: (
            learning_rate * (value * clip_scale) / (value.abs() * clip_scale + epsilon)
        ).contiguous()
        for name, value in frozen.items()
    }
    if any(not value.isfinite().all() for value in updates.values()):
        raise ValueError("GP-C produced a non-finite local AdamW update")
    return updates


def _linear_combination(
    vectors: Sequence[Mapping[str, Any]],
    weights: Sequence[float],
) -> dict[str, Any]:
    if not vectors or len(vectors) != len(weights):
        raise ValueError("GP-C vector combination is incomplete")
    names = tuple(vectors[0])
    if any(tuple(vector) != names for vector in vectors):
        raise ValueError("GP-C vector parameter manifests differ")
    result = {name: vectors[0][name].new_zeros(vectors[0][name].shape) for name in names}
    for vector, weight in zip(vectors, weights, strict=True):
        if not math.isfinite(weight):
            raise ValueError("GP-C vector weight is non-finite")
        for name in names:
            result[name].add_(vector[name], alpha=float(weight))
    return {name: value.contiguous() for name, value in result.items()}


def _load_state_jackknife_updates(
    update_manifest: Mapping[str, Any],
    *,
    expected_support: set[tuple[str, str]],
) -> dict[tuple[str, str], tuple[dict[str, Any], ...]]:
    grouped: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in update_manifest["state_jackknife_artifacts"]:
        key = (str(row["task_id"]), str(row["state_id"]))
        grouped[key].append(
            {
                "jackknife_id": str(row["jackknife_id"]),
                "excluded_realization_id": str(row["excluded_realization_id"]),
                "update": _load_verified_gradient(
                    Path(str(row["file"])),
                    str(row["sha256"]),
                ),
            }
        )
    if set(grouped) != expected_support:
        raise ValueError("GP-C Jackknife support differs from state update support")
    frozen: dict[tuple[str, str], tuple[dict[str, Any], ...]] = {}
    for key, rows in grouped.items():
        if not 3 <= len(rows) <= 5:
            raise ValueError("GP-C requires 3-5 Jackknife updates per state")
        jackknife_ids = {str(row["jackknife_id"]) for row in rows}
        realization_ids = {str(row["excluded_realization_id"]) for row in rows}
        if len(jackknife_ids) != len(rows) or len(realization_ids) != len(rows):
            raise ValueError("GP-C Jackknife identities must be unique within a state")
        frozen[key] = tuple(sorted(rows, key=lambda row: str(row["excluded_realization_id"])))
    return frozen


def _apply_descent_vector(model: Any, descent: Mapping[str, Any]) -> None:
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
                raise ValueError(f"GP-C update tensor is invalid:{name}")
            parameter.add_(
                value.to(device=parameter.device, dtype=parameter.dtype),
                alpha=-1.0,
            )


def _restore_adapter(model: Any, baseline_state: Mapping[str, Any]) -> None:
    from peft import set_peft_model_state_dict

    result = set_peft_model_state_dict(model, dict(baseline_state), adapter_name="default")
    if getattr(result, "unexpected_keys", ()):
        raise ValueError("GP-C Adapter restore produced unexpected keys")


def freeze_local_update_manifest(
    gradient_plan: Mapping[str, Any],
    gradient_report: Mapping[str, Any],
    *,
    output_dir: Path,
) -> dict[str, Any]:
    from safetensors.torch import save_file

    if gradient_report.get("plan_hash") != gradient_plan.get("plan_hash"):
        raise ValueError("GP-C update freeze requires a replayed gradient report")
    if gradient_report.get("gradient_realization_stability", {}).get("status") != "passed":
        raise ValueError("GP-C update freeze requires stable state realizations")
    optimizer = gradient_plan["local_optimizer_contract"]
    expected_contract = {
        "optimizer_name": "adamw",
        "estimator_scope": "local_distribution_update_only",
        "step_count": 1,
        "cold_start": True,
        "reuse_main_optimizer_state": False,
        "weight_decay": 0.0,
        "mixed_state_batches_allowed": False,
        "state_gradient_mode": "train",
        "objective_gradient_mode": OBJECTIVE_GRADIENT_EXECUTION_MODE,
        "objective_gradient_point": "post_global_update",
    }
    if any(optimizer.get(key) != value for key, value in expected_contract.items()):
        raise ValueError("GP-C optimizer contract differs from the local estimand")
    state_dir = output_dir / "state_updates"
    state_dir.mkdir(parents=True, exist_ok=True)
    jackknife_dir = output_dir / "state_jackknife_updates"
    jackknife_dir.mkdir(parents=True, exist_ok=True)
    state_updates: dict[tuple[str, str], dict[str, Any]] = {}
    state_artifacts = []
    jackknife_artifacts = []
    for index, row in enumerate(gradient_report["state_rows"]):
        gradient = _load_verified_gradient(
            Path(str(row["state_gradient_file"])),
            str(row["state_gradient_sha256"]),
        )
        update = _cold_start_adamw_update(
            gradient,
            learning_rate=float(optimizer["learning_rate"]),
            epsilon=float(optimizer["epsilon"]),
            maximum_gradient_norm=float(optimizer["maximum_gradient_norm"]),
        )
        path = state_dir / f"state_{index:04d}.safetensors"
        save_file(update, path)
        task_id = str(row["task_id"])
        state_id = str(row["state_id"])
        state_updates[(task_id, state_id)] = update
        state_artifacts.append(
            {
                "task_id": task_id,
                "task_type": row.get("task_type", "unknown"),
                "state_id": state_id,
                "source_state_artifact_id": row["state_artifact_id"],
                "file": str(path),
                "sha256": _sha256(path),
                "update_norm": _gradient_norm(update),
            }
        )
        realization_sources = tuple(row.get("realization_gradient_artifacts", ()))
        if not 3 <= len(realization_sources) <= 5:
            raise ValueError("GP-C requires 3-5 realization gradients per state")
        if {str(value["realization_id"]) for value in realization_sources} != set(
            str(value) for value in row["realization_ids"]
        ):
            raise ValueError("GP-C realization-gradient lineage changed")
        realization_gradients = [
            _load_verified_gradient(
                Path(str(value["file"])),
                str(value["sha256"]),
            )
            for value in realization_sources
        ]
        for excluded_index, excluded in enumerate(realization_sources):
            retained = [
                gradient
                for index, gradient in enumerate(realization_gradients)
                if index != excluded_index
            ]
            jackknife_gradient = _weighted_gradient(
                retained,
                [1.0] * len(retained),
            )
            jackknife_update = _cold_start_adamw_update(
                jackknife_gradient,
                learning_rate=float(optimizer["learning_rate"]),
                epsilon=float(optimizer["epsilon"]),
                maximum_gradient_norm=float(optimizer["maximum_gradient_norm"]),
            )
            jackknife_path = (
                jackknife_dir / f"state_{index:04d}_leave_{excluded_index:02d}.safetensors"
            )
            save_file(jackknife_update, jackknife_path)
            jackknife_artifacts.append(
                {
                    "task_id": task_id,
                    "state_id": state_id,
                    "jackknife_id": canonical_hash(
                        {
                            "task_id": task_id,
                            "state_id": state_id,
                            "excluded_realization_id": excluded["realization_id"],
                            "retained_realization_ids": tuple(
                                str(value["realization_id"])
                                for position, value in enumerate(realization_sources)
                                if position != excluded_index
                            ),
                        },
                        prefix="finance_gp_c_state_jackknife:",
                    ),
                    "excluded_realization_id": str(excluded["realization_id"]),
                    "file": str(jackknife_path),
                    "sha256": _sha256(jackknife_path),
                    "update_norm": _gradient_norm(jackknife_update),
                }
            )
    task_updates = []
    task_vectors = []
    task_weights = []
    task_marginals = {
        str(key): float(value) for key, value in gradient_report["task_marginals"].items()
    }
    for task_id, distribution in sorted(gradient_plan["task_distributions"].items()):
        probabilities = {
            str(key): float(value) for key, value in distribution["probabilities"].items()
        }
        states = tuple(sorted(probabilities))
        if {(task_id, state_id) for state_id in states} - set(state_updates):
            raise ValueError("GP-C update manifest lacks a frozen state update")
        task_update = _linear_combination(
            [state_updates[(task_id, state_id)] for state_id in states],
            [probabilities[state_id] for state_id in states],
        )
        task_vectors.append(task_update)
        task_weights.append(task_marginals[task_id])
        task_updates.append(
            {
                "task_id": task_id,
                "current_probabilities": probabilities,
                "update_norm": _gradient_norm(task_update),
            }
        )
    global_update = _linear_combination(task_vectors, task_weights)
    global_path = output_dir / "global_local_adamw_update.safetensors"
    save_file(global_update, global_path)
    manifest: dict[str, Any] = {
        "experiment_version": GP_C_PROXY_VERSION,
        "artifact_type": "LocalAdamWUpdateManifest",
        "source_gradient_plan_hash": gradient_plan["plan_hash"],
        "source_gradient_report_hash": gradient_report["report_hash"],
        "run_role": gradient_plan["run_role"],
        "numeric_contract_hash": gradient_plan["numeric_contract_hash"],
        "numeric_profile": gradient_plan["numeric_contract"]["selected_profile"],
        "production_authorization_eligible": bool(
            gradient_plan.get("production_authorization_eligible", True)
        ),
        "beneficiary_model_state_id": gradient_plan["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": gradient_plan["beneficiary_checkpoint_hash"],
        "task_sampling_contract_hash": gradient_plan["task_sampling_contract_hash"],
        "state_realization_manifest_hash": gradient_plan["state_realization_manifest_hash"],
        "optimizer_contract": optimizer,
        "local_update_estimand": "expectation_of_state_homogeneous_cold_start_adamw_updates",
        "state_artifacts": tuple(state_artifacts),
        "state_jackknife_artifacts": tuple(jackknife_artifacts),
        "state_uncertainty_method": "leave_one_realization_out_jackknife_pseudovalues",
        "task_updates": tuple(task_updates),
        "task_marginals": task_marginals,
        "global_update_artifact": {
            "file": str(global_path),
            "sha256": _sha256(global_path),
            "update_norm": _gradient_norm(global_update),
        },
        "gradient_realization_stability_report_hash": gradient_report["gradient_diagnostics_hash"],
        "claim_boundary": (
            "The frozen vectors implement one local state-homogeneous cold-start AdamW "
            "distribution update. They are not full Student optimizer trajectories."
        ),
    }
    manifest["manifest_hash"] = canonical_hash(
        manifest,
        prefix="finance_gp_c_local_update_manifest:",
    )
    return manifest


def freeze_finite_target_directions(
    finite_plan: Mapping[str, Any],
    update_manifest: Mapping[str, Any],
    *,
    output_dir: Path,
) -> dict[str, Any]:
    from safetensors.torch import save_file

    if finite_plan["source_gradient_plan_hash"] != update_manifest["source_gradient_plan_hash"]:
        raise ValueError("finite-target directions cross Gradient Projection plans")
    state_updates = {
        (str(row["task_id"]), str(row["state_id"])): _load_verified_gradient(
            Path(str(row["file"])),
            str(row["sha256"]),
        )
        for row in update_manifest["state_artifacts"]
    }
    jackknife_updates = _load_state_jackknife_updates(
        update_manifest,
        expected_support=set(state_updates),
    )
    coordinates: dict[str, dict[str, Any]] = {}
    for row in finite_plan["coordinate_rows"]:
        task_id = str(row["task_id"])
        state_id = str(row["state_id"])
        reference_id = str(row["reference_state_id"])
        task_marginal = float(row["task_marginal"])
        coordinates[str(row["coordinate_id"])] = _linear_combination(
            [state_updates[(task_id, state_id)], state_updates[(task_id, reference_id)]],
            [0.5 * task_marginal, -0.5 * task_marginal],
        )
    global_artifact = update_manifest["global_update_artifact"]
    global_update = _load_verified_gradient(
        Path(str(global_artifact["file"])),
        str(global_artifact["sha256"]),
    )
    zero = {name: value.new_zeros(value.shape) for name, value in global_update.items()}
    direction_dir = output_dir / "finite_target_directions"
    direction_dir.mkdir(parents=True, exist_ok=True)
    artifacts = []
    for index, row in enumerate(finite_plan["design_rows"]):
        if row["role"] == "null_replay":
            direction = zero
        else:
            direction = _linear_combination(
                [coordinates[str(key)] for key in row["coordinate_weights"]],
                [float(value) for value in row["coordinate_weights"].values()],
            )
        path = direction_dir / f"direction_{index:04d}.safetensors"
        save_file(direction, path)
        artifacts.append(
            {
                "design_row_id": row["design_row_id"],
                "role": row["role"],
                "file": str(path),
                "sha256": _sha256(path),
                "direction_norm": math.sqrt(
                    sum(float((value.double() ** 2).sum()) for value in direction.values())
                ),
            }
        )
    manifest: dict[str, Any] = {
        "experiment_version": GP_C_PROXY_VERSION,
        "artifact_type": "FiniteTargetDirectionManifest",
        "finite_target_plan_hash": finite_plan["plan_hash"],
        "source_gradient_plan_hash": finite_plan["source_gradient_plan_hash"],
        "beneficiary_model_state_id": finite_plan["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": finite_plan["beneficiary_checkpoint_hash"],
        "local_update_manifest_hash": update_manifest["manifest_hash"],
        "global_update_artifact": global_artifact,
        "direction_artifacts": tuple(artifacts),
        "coordinate_direction_count": len(coordinates),
        "jackknife_state_count": len(jackknife_updates),
        "post_global_linearization": True,
    }
    manifest["manifest_hash"] = canonical_hash(
        manifest,
        prefix="finance_gp_c_finite_target_directions:",
    )
    return manifest


def _center(values: Mapping[str, float], probabilities: Mapping[str, float]) -> dict[str, float]:
    if set(values) != set(probabilities):
        raise ValueError("GP-C centering support differs from pi_t")
    mean = sum(probabilities[key] * values[key] for key in values)
    centered = {key: value - mean for key, value in values.items()}
    if not math.isclose(
        sum(probabilities[key] * centered[key] for key in centered),
        0.0,
        abs_tol=1e-10,
    ):
        raise ValueError("GP-C proxy failed pi-centering")
    return centered


def _spearman(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("GP-C rank support is incomplete")

    def ranks(values: Sequence[float]) -> list[float]:
        ordered = sorted(enumerate(values), key=lambda item: item[1])
        result = [0.0] * len(values)
        cursor = 0
        while cursor < len(ordered):
            end = cursor + 1
            while end < len(ordered) and ordered[end][1] == ordered[cursor][1]:
                end += 1
            rank = (cursor + end - 1) / 2.0
            for index in range(cursor, end):
                result[ordered[index][0]] = rank
            cursor = end
        return result

    left_rank = ranks(left)
    right_rank = ranks(right)
    left_mean = statistics.fmean(left_rank)
    right_mean = statistics.fmean(right_rank)
    covariance = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left_rank, right_rank, strict=True)
    )
    denominator = math.sqrt(
        sum((value - left_mean) ** 2 for value in left_rank)
        * sum((value - right_mean) ** 2 for value in right_rank)
    )
    return covariance / denominator if denominator > 0 else 0.0


def analyze_gp_c_proxy(
    *,
    finite_plan: Mapping[str, Any],
    finite_report: Mapping[str, Any],
    update_manifest: Mapping[str, Any],
    objective_gradient_manifest: Mapping[str, Any],
    calibration_scale: float | None = None,
    calibration_report_hash: str | None = None,
) -> dict[str, Any]:
    _replay_hash(
        finite_plan,
        field="plan_hash",
        prefix="finance_finite_target_plan:",
        label="GP-C finite-target plan",
    )
    _replay_hash(
        finite_report,
        field="report_hash",
        prefix="finance_finite_target_report:",
        label="GP-C finite-target report",
    )
    _replay_hash(
        update_manifest,
        field="manifest_hash",
        prefix="finance_gp_c_local_update_manifest:",
        label="GP-C local-update manifest",
    )
    _replay_hash(
        objective_gradient_manifest,
        field="manifest_hash",
        prefix="finance_post_global_objective_gradient_manifest:",
        label="GP-C objective-gradient manifest",
    )
    if finite_report.get("plan_hash") != finite_plan.get("plan_hash"):
        raise ValueError("GP-C target report does not replay its plan")
    if finite_report.get("status") != "passed":
        raise ValueError("GP-C proxy cannot consume a failed finite target")
    if finite_report.get("objective_role") != finite_plan.get("objective_role"):
        raise ValueError("GP-C finite target uses another objective partition")
    if finite_report.get("source_gradient_plan_hash") != finite_plan.get(
        "source_gradient_plan_hash"
    ):
        raise ValueError("GP-C finite target crosses Gradient Projection plans")
    if update_manifest.get("source_gradient_plan_hash") != finite_plan.get(
        "source_gradient_plan_hash"
    ):
        raise ValueError("GP-C local update belongs to another Gradient Projection plan")
    if (
        finite_report.get("numeric_contract_hash") != finite_plan.get("numeric_contract_hash")
        or update_manifest.get("numeric_contract_hash") != finite_plan.get("numeric_contract_hash")
        or objective_gradient_manifest.get("numeric_contract_hash")
        != finite_plan.get("numeric_contract_hash")
    ):
        raise ValueError("GP-C evidence crosses numeric execution contracts")
    if objective_gradient_manifest.get("finite_target_plan_hash") != finite_plan.get("plan_hash"):
        raise ValueError("GP-C objective gradient belongs to another target plan")
    if objective_gradient_manifest.get("local_update_manifest_hash") != update_manifest.get(
        "manifest_hash"
    ):
        raise ValueError("GP-C objective gradient uses another local update map")
    if objective_gradient_manifest.get("objective_role") != finite_plan.get("objective_role"):
        raise ValueError("GP-C objective gradient uses another objective partition")
    if objective_gradient_manifest.get("objective_records_hash") != finite_plan.get(
        "objective_records_hash"
    ):
        raise ValueError("GP-C objective gradient uses another objective support")
    if objective_gradient_manifest.get("beneficiary_checkpoint_hash") != finite_plan.get(
        "beneficiary_checkpoint_hash"
    ):
        raise ValueError("GP-C objective gradient uses another beneficiary checkpoint")
    if objective_gradient_manifest.get("objective_gradient_point") != "post_global_update":
        raise ValueError("GP-C requires a post-global objective gradient")
    if (
        finite_plan.get("objective_gradient_mode")
        != OBJECTIVE_GRADIENT_EXECUTION_MODE
        or finite_plan.get("optimizer_contract", {}).get("objective_gradient_mode")
        != OBJECTIVE_GRADIENT_EXECUTION_MODE
        or objective_gradient_manifest.get("objective_gradient_mode")
        != OBJECTIVE_GRADIENT_EXECUTION_MODE
    ):
        raise ValueError("GP-C objective execution mode changed")
    objective_artifact = objective_gradient_manifest["aggregate_gradient_artifact"]
    objective_gradient = _load_verified_gradient(
        Path(str(objective_artifact["file"])),
        str(objective_artifact["sha256"]),
    )
    state_updates = {
        (str(row["task_id"]), str(row["state_id"])): _load_verified_gradient(
            Path(str(row["file"])),
            str(row["sha256"]),
        )
        for row in update_manifest["state_artifacts"]
    }
    jackknife_updates = _load_state_jackknife_updates(
        update_manifest,
        expected_support=set(state_updates),
    )
    target_by_task = {
        str(row["task_id"]): {
            str(key): float(value) for key, value in row["target_state_values"].items()
        }
        for row in finite_report["state_targets"]
    }
    task_types = {
        str(row["task_id"]): str(row.get("task_type", "unknown"))
        for row in update_manifest["state_artifacts"]
    }
    unscaled_rows = []
    proxy_values_all = []
    target_values_all = []
    task_payloads = []
    for task_id, distribution in sorted(finite_plan["task_distributions"].items()):
        probabilities = {str(key): float(value) for key, value in distribution.items()}
        raw = {
            state_id: _gradient_dot(
                state_updates[(task_id, state_id)],
                objective_gradient,
            )
            for state_id in probabilities
        }
        centered = _center(raw, probabilities)
        raw_jackknife_by_state = {
            state_id: [
                {
                    **artifact,
                    "raw_proxy": _gradient_dot(artifact["update"], objective_gradient),
                }
                for artifact in jackknife_updates[(task_id, state_id)]
            ]
            for state_id in probabilities
        }
        if any(not 3 <= len(values) <= 5 for values in raw_jackknife_by_state.values()):
            raise ValueError("GP-C proxy lacks 3-5 Jackknife updates per state")
        target = target_by_task[task_id]
        proxy_vector = [centered[state_id] for state_id in sorted(probabilities)]
        target_vector = [target[state_id] for state_id in sorted(probabilities)]
        proxy_values_all.extend(proxy_vector)
        target_values_all.extend(target_vector)
        task_payloads.append(
            (
                task_id,
                probabilities,
                raw,
                centered,
                raw_jackknife_by_state,
                target,
                proxy_vector,
                target_vector,
            )
        )
    orientation = sum(
        left * right for left, right in zip(proxy_values_all, target_values_all, strict=True)
    )
    fitted_scale = statistics.median(abs(value) for value in target_values_all) / max(
        statistics.median(abs(value) for value in proxy_values_all), CALIBRATION_FLOOR
    )
    if orientation <= 0:
        fitted_scale *= -1.0
    objective_role = str(finite_plan["objective_role"])
    if objective_role == "estimation":
        if calibration_scale is not None or calibration_report_hash is not None:
            raise ValueError("estimation must fit rather than consume a calibration report")
        applied_scale = fitted_scale
        calibration_source = "fitted_on_estimation_only"
    else:
        if (
            calibration_scale is None
            or not math.isfinite(calibration_scale)
            or not calibration_report_hash
        ):
            raise ValueError("validation and authorization require a frozen calibration report")
        applied_scale = calibration_scale
        calibration_source = "frozen_estimation_scale"
    task_rows = []
    for (
        task_id,
        probabilities,
        raw,
        centered,
        raw_jackknife_by_state,
        target,
        proxy_vector,
        target_vector,
    ) in task_payloads:
        scaled = {state_id: applied_scale * value for state_id, value in centered.items()}
        scaled_vector = [scaled[state_id] for state_id in sorted(probabilities)]
        target_rms = math.sqrt(statistics.fmean(value * value for value in target_vector))
        residual_rms = math.sqrt(
            statistics.fmean(
                (left - right) ** 2
                for left, right in zip(scaled_vector, target_vector, strict=True)
            )
        )
        local_denominator = sum(value * value for value in proxy_vector)
        local_scale = (
            sum(left * right for left, right in zip(proxy_vector, target_vector, strict=True))
            / local_denominator
            if local_denominator > CALIBRATION_FLOOR
            else 0.0
        )
        task_rows.append(
            {
                "task_id": task_id,
                "task_type": task_types[task_id],
                "task_diagnostic_scale": local_scale,
                "applied_global_scale": applied_scale,
                "normalized_residual_rms": residual_rms / max(target_rms, CALIBRATION_FLOOR),
                "spearman": _spearman(scaled_vector, target_vector),
                "winner_agreement": float(
                    max(range(len(scaled_vector)), key=scaled_vector.__getitem__)
                    == max(range(len(target_vector)), key=target_vector.__getitem__)
                ),
            }
        )
        for state_id in sorted(probabilities):
            jackknife_count = len(raw_jackknife_by_state[state_id])
            jackknife_pseudovalues = tuple(
                applied_scale
                * (
                    jackknife_count * raw[state_id]
                    - (jackknife_count - 1) * float(value["raw_proxy"])
                )
                for value in raw_jackknife_by_state[state_id]
            )
            unscaled_rows.append(
                {
                    "task_id": task_id,
                    "task_type": task_types[task_id],
                    "state_id": state_id,
                    "current_probability": probabilities[state_id],
                    "unscaled_gp_c_proxy": centered[state_id],
                    "scaled_gp_c_proxy": scaled[state_id],
                    "jackknife_raw_gp_c_proxy_values": jackknife_pseudovalues,
                    "jackknife_realization_ids": tuple(
                        str(value["excluded_realization_id"])
                        for value in raw_jackknife_by_state[state_id]
                    ),
                    "jackknife_realization_count": jackknife_count,
                    "jackknife_proxy_sample_standard_deviation": statistics.stdev(
                        jackknife_pseudovalues
                    ),
                    "finite_target": target[state_id],
                }
            )
    by_type: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in task_rows:
        by_type[str(row["task_type"])].append(row)
    report: dict[str, Any] = {
        "experiment_version": GP_C_PROXY_VERSION,
        "artifact_type": "PostGlobalGPCProxyReport",
        "run_role": finite_plan["run_role"],
        "numeric_contract_hash": finite_plan["numeric_contract_hash"],
        "numeric_profile": finite_plan["numeric_profile"],
        "production_authorization_eligible": bool(finite_plan["production_authorization_eligible"]),
        "finite_target_plan_hash": finite_plan["plan_hash"],
        "finite_target_report_hash": finite_report["report_hash"],
        "source_gradient_plan_hash": finite_plan.get("source_gradient_plan_hash"),
        "beneficiary_model_state_id": finite_plan.get("beneficiary_model_state_id"),
        "beneficiary_checkpoint_hash": finite_plan.get("beneficiary_checkpoint_hash"),
        "local_update_manifest_hash": update_manifest["manifest_hash"],
        "objective_gradient_manifest_hash": objective_gradient_manifest["manifest_hash"],
        "objective_role": objective_role,
        "objective_record_ids": objective_gradient_manifest.get(
            "objective_record_ids",
            finite_plan.get("objective_record_ids", ()),
        ),
        "objective_records_hash": objective_gradient_manifest.get(
            "objective_records_hash",
            finite_plan.get("objective_records_hash"),
        ),
        "objective_record_count": len(
            objective_gradient_manifest.get(
                "objective_record_ids",
                finite_plan.get("objective_record_ids", ()),
            )
        ),
        "objective_gradient_point": "post_global_update",
        "calibration_source": calibration_source,
        "calibration_report_hash": calibration_report_hash,
        "fitted_estimation_scale": fitted_scale if objective_role == "estimation" else None,
        "applied_calibration_scale": applied_scale,
        "orientation_before_calibration": "aligned" if orientation > 0 else "reversed",
        "macro_task_spearman": statistics.fmean(row["spearman"] for row in task_rows),
        "winner_agreement_rate": statistics.fmean(row["winner_agreement"] for row in task_rows),
        "mean_normalized_residual_rms": statistics.fmean(
            row["normalized_residual_rms"] for row in task_rows
        ),
        "task_type_fidelity": {
            task_type: {
                "task_count": len(rows),
                "macro_spearman": statistics.fmean(row["spearman"] for row in rows),
                "winner_agreement": statistics.fmean(row["winner_agreement"] for row in rows),
                "mean_normalized_residual_rms": statistics.fmean(
                    row["normalized_residual_rms"] for row in rows
                ),
            }
            for task_type, rows in sorted(by_type.items())
        },
        "task_rows": task_rows,
        "state_rows": unscaled_rows,
        "state_uncertainty_method": update_manifest["state_uncertainty_method"],
        "status": "passed",
        "claim_boundary": finite_plan["claim_boundary"],
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_post_global_gp_c_proxy_report:",
    )
    return report


def _freeze_updates(args: argparse.Namespace) -> None:
    gradient_dir = Path(args.gradient_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    plan = _read_json(gradient_dir / "plan.json")
    report = _read_json(gradient_dir / "report.json")
    manifest = freeze_local_update_manifest(plan, report, output_dir=output_dir)
    _write_json(output_dir / "local_update_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


def _freeze_directions(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    plan = _read_json(Path(args.finite_target_plan).resolve())
    update_manifest = _read_json(Path(args.local_update_manifest).resolve())
    manifest = freeze_finite_target_directions(
        plan,
        update_manifest,
        output_dir=output_dir,
    )
    _write_json(output_dir / "direction_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


def _build_objective_gradient(args: argparse.Namespace) -> None:
    import torch
    from peft import get_peft_model_state_dict
    from safetensors.torch import save_file

    gpu_ids = tuple(int(value) for value in args.gpu_ids)
    if len(gpu_ids) != 3 or len(set(gpu_ids)) != 3:
        raise ValueError("post-global objective requires one frozen three-GPU group")
    if any(value < 0 or value >= torch.cuda.device_count() for value in gpu_ids):
        raise ValueError("post-global objective GPU group is unavailable")
    torch.cuda.set_device(gpu_ids[0])
    finite_plan = _read_json(Path(args.finite_target_plan).resolve())
    update_manifest = _read_json(Path(args.local_update_manifest).resolve())
    if finite_plan.get("objective_gradient_mode") != OBJECTIVE_GRADIENT_EXECUTION_MODE:
        raise ValueError("post-global objective execution mode changed")
    if (
        finite_plan.get("optimizer_contract", {}).get("objective_gradient_mode")
        != OBJECTIVE_GRADIENT_EXECUTION_MODE
    ):
        raise ValueError("post-global optimizer objective mode changed")
    if finite_plan["source_gradient_plan_hash"] != update_manifest["source_gradient_plan_hash"]:
        raise ValueError("post-global objective crosses Gradient Projection plans")
    records_path = Path(str(finite_plan["source_records_path"]))
    if _sha256(records_path) != finite_plan["source_records_sha256"]:
        raise ValueError("post-global objective records changed after planning")
    records = _load_records(records_path)
    objective_ids = tuple(str(value) for value in finite_plan["objective_record_ids"])
    if any(record_id not in records for record_id in objective_ids):
        raise ValueError("post-global objective support is incomplete")
    _seed_everything(args.numeric_seed)
    for gpu_id in gpu_ids:
        torch.cuda.reset_peak_memory_stats(gpu_id)
    tokenizer = _load_tokenizer(Path(str(finite_plan["model_dir"])))
    model, resolved_device_map = _load_execution_model(
        Path(str(finite_plan["model_dir"])),
        Path(str(finite_plan["beneficiary_adapter_dir"])),
        gpu_ids=gpu_ids,
        profile=finite_plan["numeric_profile"],
    )
    if _adapter_tensor_sha256(model) != finite_plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("post-global objective loaded another beneficiary Adapter")
    parameter_manifest, parameter_manifest_hash = _gradient_parameter_manifest(model)
    baseline_state = {
        name: value.detach().cpu().clone()
        for name, value in get_peft_model_state_dict(model).items()
    }
    global_artifact = update_manifest["global_update_artifact"]
    global_update = _load_verified_gradient(
        Path(str(global_artifact["file"])),
        str(global_artifact["sha256"]),
    )
    _restore_adapter(model, baseline_state)
    _apply_descent_vector(model, global_update)
    post_global_adapter_hash = _adapter_tensor_sha256(model)
    output_dir = Path(args.output_dir).resolve()
    gradient_dir = output_dir / "post_global_objective_gradients"
    gradient_dir.mkdir(parents=True, exist_ok=True)
    gradients = []
    weights = []
    record_rows = []
    started = time.monotonic()
    for index, record_id in enumerate(objective_ids):
        gradient, loss, supervised_tokens = _record_gradient(
            model,
            tokenizer,
            records[record_id],
            mode="objective_eval",
        )
        path = gradient_dir / f"record_{index:03d}.safetensors"
        save_file(gradient, path)
        gradients.append(gradient)
        weights.append(float(supervised_tokens))
        record_rows.append(
            {
                "record_id": record_id,
                "file": str(path),
                "sha256": _sha256(path),
                "loss": loss,
                "supervised_tokens": supervised_tokens,
                "gradient_norm": _gradient_norm(gradient),
            }
        )
    aggregate = _weighted_gradient(gradients, weights)
    aggregate_path = gradient_dir / "aggregate.safetensors"
    save_file(aggregate, aggregate_path)
    manifest: dict[str, Any] = {
        "experiment_version": GP_C_PROXY_VERSION,
        "artifact_type": "PostGlobalObjectiveGradientManifest",
        "run_role": finite_plan["run_role"],
        "numeric_contract_hash": finite_plan["numeric_contract_hash"],
        "numeric_profile": finite_plan["numeric_profile"],
        "production_authorization_eligible": bool(finite_plan["production_authorization_eligible"]),
        "finite_target_plan_hash": finite_plan["plan_hash"],
        "source_gradient_plan_hash": finite_plan["source_gradient_plan_hash"],
        "local_update_manifest_hash": update_manifest["manifest_hash"],
        "beneficiary_model_state_id": finite_plan["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": finite_plan["beneficiary_checkpoint_hash"],
        "baseline_adapter_tensor_sha256": finite_plan["beneficiary_adapter_tensor_sha256"],
        "post_global_adapter_tensor_sha256": post_global_adapter_hash,
        "objective_role": finite_plan["objective_role"],
        "objective_record_ids": objective_ids,
        "objective_records_hash": finite_plan["objective_records_hash"],
        "objective_record_count": len(objective_ids),
        "objective_gradient_mode": OBJECTIVE_GRADIENT_EXECUTION_MODE,
        "objective_gradient_point": "post_global_update",
        "parameter_manifest": parameter_manifest,
        "parameter_manifest_hash": parameter_manifest_hash,
        "record_gradients": tuple(record_rows),
        "aggregate_gradient_artifact": {
            "file": str(aggregate_path),
            "sha256": _sha256(aggregate_path),
            "gradient_norm": _gradient_norm(aggregate),
            "supervised_token_count": int(sum(weights)),
        },
        "numeric_seed": args.numeric_seed,
        "runtime_seconds": time.monotonic() - started,
        "requested_cuda_device_ids": gpu_ids,
        "resolved_hf_device_map": resolved_device_map,
        "resolved_hf_device_map_hash": canonical_hash(
            resolved_device_map,
            prefix="finance_post_global_objective_hf_device_map:",
        ),
        "peak_gpu_memory_bytes": max(
            int(torch.cuda.max_memory_allocated(gpu_id)) for gpu_id in gpu_ids
        ),
        "peak_gpu_memory_bytes_by_requested_device": {
            str(gpu_id): int(torch.cuda.max_memory_allocated(gpu_id)) for gpu_id in gpu_ids
        },
    }
    manifest["manifest_hash"] = canonical_hash(
        manifest,
        prefix="finance_post_global_objective_gradient_manifest:",
    )
    _write_json(output_dir / "post_global_objective_gradient_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    del model, gradients, aggregate, global_update
    gc.collect()
    torch.cuda.empty_cache()


def _analyze(args: argparse.Namespace) -> None:
    finite_plan = _read_json(Path(args.finite_target_plan).resolve())
    finite_report = _read_json(Path(args.finite_target_report).resolve())
    update_manifest = _read_json(Path(args.local_update_manifest).resolve())
    objective_manifest = _read_json(Path(args.objective_gradient_manifest).resolve())
    calibration_scale = None
    calibration_report_hash = None
    if args.calibration_report:
        calibration = _read_json(Path(args.calibration_report).resolve())
        calibration_report_hash = _replay_hash(
            calibration,
            field="report_hash",
            prefix="finance_post_global_gp_c_proxy_report:",
            label="GP-C calibration report",
        )
        if (
            calibration.get("status") != "passed"
            or calibration.get("objective_role") != "estimation"
            or calibration.get("calibration_source") != "fitted_on_estimation_only"
            or calibration.get("numeric_contract_hash") != finite_plan.get("numeric_contract_hash")
            or calibration.get("run_role") != finite_plan.get("run_role")
            or calibration.get("source_gradient_plan_hash")
            != finite_plan.get("source_gradient_plan_hash")
            or calibration.get("beneficiary_checkpoint_hash")
            != finite_plan.get("beneficiary_checkpoint_hash")
        ):
            raise ValueError("GP-C calibration must be the matching estimation report")
        calibration_scale = float(calibration["applied_calibration_scale"])
    report = analyze_gp_c_proxy(
        finite_plan=finite_plan,
        finite_report=finite_report,
        update_manifest=update_manifest,
        objective_gradient_manifest=objective_manifest,
        calibration_scale=calibration_scale,
        calibration_report_hash=calibration_report_hash,
    )
    output_path = Path(args.output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the post-global local AdamW GP-C Contribution proxy"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze_updates = subparsers.add_parser("freeze-local-updates")
    freeze_updates.add_argument("--gradient-dir", required=True)
    freeze_updates.add_argument("--output-dir", required=True)
    freeze_updates.set_defaults(handler=_freeze_updates)
    freeze_directions = subparsers.add_parser("freeze-target-directions")
    freeze_directions.add_argument("--finite-target-plan", required=True)
    freeze_directions.add_argument("--local-update-manifest", required=True)
    freeze_directions.add_argument("--output-dir", required=True)
    freeze_directions.set_defaults(handler=_freeze_directions)
    objective = subparsers.add_parser("build-post-global-objective-gradient")
    objective.add_argument("--finite-target-plan", required=True)
    objective.add_argument("--local-update-manifest", required=True)
    objective.add_argument("--output-dir", required=True)
    objective.add_argument("--gpu-ids", type=int, nargs="+", required=True)
    objective.add_argument("--numeric-seed", type=int, default=20261121)
    objective.set_defaults(handler=_build_objective_gradient)
    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("--finite-target-plan", required=True)
    analyze.add_argument("--finite-target-report", required=True)
    analyze.add_argument("--local-update-manifest", required=True)
    analyze.add_argument("--objective-gradient-manifest", required=True)
    analyze.add_argument("--calibration-report")
    analyze.add_argument("--output-path", required=True)
    analyze.set_defaults(handler=_analyze)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
