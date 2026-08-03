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
    _fidelity_summary,
    _linear_gradient_combination,
    _recover_centered_state_values,
    _sylvester_hadamard,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    GRADIENT_ALIGNMENT_VERSION,
    _append_jsonl,
    _gradient_dot,
    _gradient_norm,
    _gradient_parameter_manifest,
    _load_jsonl,
    _load_verified_gradient,
    _normalized_gradient_alignment,
    _record_gradient,
    _sha256,
    _valid_hashed_row,
    _weighted_gradient,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_distribution_intervention import (
    _rank_evidence,
    _restore_adapter,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_gp_abc_validation import (
    ADAMW_BETAS,
    ADAMW_EPSILON,
    ADAMW_WEIGHT_DECAY,
    MAXIMUM_GRADIENT_NORM,
    _adamw_descent_direction,
    _apply_descent_vector,
    _center,
    _cpu_contiguous,
    _parameter_step_fidelity,
    _to_device,
    _vector_fidelity,
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

AUTHORIZATION_VERSION = "finance_contribution_gradient_authorization.v1"
AUTHORIZATION_NUMERIC_SEED = 20261010
PRIMARY_ESTIMATOR = "gp_c_adamw_update"
SECONDARY_ESTIMATOR = "gp_b_centered_dot"
DIAGNOSTIC_ESTIMATOR = "gp_a_cosine"
ESTIMATOR_IDS = (PRIMARY_ESTIMATOR, SECONDARY_ESTIMATOR, DIAGNOSTIC_ESTIMATOR)
INTERVENTION_EPSILON = 0.4
MAXIMUM_RECONSTRUCTION_RELATIVE_ERROR = 0.5
CALIBRATION_FLOOR = 1e-12

# These gates are frozen before the authorization objective is opened.
DISTRIBUTION_GATES: dict[str, float] = {
    "maximum_mean_total_variation": 0.10,
    "maximum_p95_total_variation": 0.20,
    "maximum_mean_jensen_shannon": 0.02,
    "maximum_p95_jensen_shannon": 0.05,
    "minimum_update_direction_agreement": 0.75,
    "maximum_mean_normalized_target_regret": 0.25,
    "maximum_p95_normalized_target_regret": 0.60,
}


def _assert_canonical_artifact(
    payload: dict[str, Any],
    *,
    hash_field: str,
    prefix: str,
    artifact_name: str,
) -> None:
    expected = payload.get(hash_field)
    if not isinstance(expected, str) or not expected:
        raise ValueError(f"{artifact_name} is missing {hash_field}")
    unhashed = dict(payload)
    unhashed.pop(hash_field)
    observed = canonical_hash(unhashed, prefix=prefix)
    if observed != expected:
        raise ValueError(f"{artifact_name} canonical identity changed")

ENERGY_CONTRACT: dict[str, float] = {
    "epsilon": 0.0001,
    "contribution_weight": 0.5,
    "novelty_weight": 0.5,
    "history_kl_weight": 1.0,
    "coverage_kl_weight": 1.0,
    "history_exponent": 0.5,
    "energy_exponent": 0.5,
}


def _sharded_baseline_lora_model(
    model_dir: Path,
    adapter_dir: Path,
    *,
    visible_gpu_count: int,
) -> Any:
    """Load the identical beneficiary with memory-bounded placement only."""
    if visible_gpu_count < 2:
        raise ValueError("sharded diagnostic placement requires at least two GPUs")
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM

    base = AutoModelForCausalLM.from_pretrained(
        model_dir,
        local_files_only=True,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
        low_cpu_mem_usage=True,
        device_map="balanced",
        max_memory={index: "45GiB" for index in range(visible_gpu_count)},
    )
    base.config.use_cache = False
    base.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    base.enable_input_require_grads()
    model = PeftModel.from_pretrained(base, adapter_dir, is_trainable=True)
    model.config.use_cache = False
    return model


def _percentile(values: list[float], probability: float) -> float:
    if not values or not 0 <= probability <= 1:
        raise ValueError("authorization percentile input is invalid")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _robust_positive_scale(proxy: list[float], target: list[float]) -> float:
    if len(proxy) != len(target) or not proxy:
        raise ValueError("authorization calibration support is incomplete")
    proxy_scale = statistics.median(abs(value) for value in proxy)
    target_scale = statistics.median(abs(value) for value in target)
    if proxy_scale <= CALIBRATION_FLOOR or target_scale <= CALIBRATION_FLOOR:
        raise ValueError("authorization calibration has a degenerate robust scale")
    scale = target_scale / proxy_scale
    if not scale > 0 or not math.isfinite(scale):
        raise ValueError("authorization calibration produced an invalid scale")
    return scale


def _normalize_contribution(value: float, *, temperature: float) -> float:
    if not temperature > 0:
        raise ValueError("authorization contribution temperature must be positive")
    scaled = value / temperature
    if scaled >= 0:
        sigmoid = 1.0 / (1.0 + math.exp(-scaled))
    else:
        exponential = math.exp(scaled)
        sigmoid = exponential / (1.0 + exponential)
    epsilon = ENERGY_CONTRACT["epsilon"]
    return epsilon + (1.0 - 2.0 * epsilon) * sigmoid


def _next_distribution(
    probabilities: list[float],
    values: list[float],
    *,
    temperature: float,
) -> tuple[list[float], list[float]]:
    if len(probabilities) != len(values) or not probabilities:
        raise ValueError("authorization distribution support is incomplete")
    if any(value <= 0 for value in probabilities) or not math.isclose(
        sum(probabilities), 1.0, abs_tol=1e-12
    ):
        raise ValueError("authorization current distribution is invalid")
    normalized = [_normalize_contribution(value, temperature=temperature) for value in values]
    rho = ENERGY_CONTRACT["history_exponent"]
    eta = ENERGY_CONTRACT["energy_exponent"]
    contribution_weight = ENERGY_CONTRACT["contribution_weight"]
    log_weights = [
        rho * math.log(probability)
        + (1.0 - rho) * math.log(probability)
        + eta * contribution_weight * math.log(contribution)
        for probability, contribution in zip(probabilities, normalized, strict=True)
    ]
    maximum = max(log_weights)
    unnormalized = [math.exp(value - maximum) for value in log_weights]
    total = sum(unnormalized)
    return [value / total for value in unnormalized], normalized


def _kl(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or any(value <= 0 for value in (*left, *right)):
        raise ValueError("authorization KL support is invalid")
    return sum(a * math.log(a / b) for a, b in zip(left, right, strict=True))


def _jensen_shannon(left: list[float], right: list[float]) -> float:
    midpoint = [(a + b) / 2.0 for a, b in zip(left, right, strict=True)]
    return 0.5 * _kl(left, midpoint) + 0.5 * _kl(right, midpoint)


def _variational_objective(
    candidate: list[float],
    current: list[float],
    target_normalized: list[float],
) -> float:
    log_potential = [
        ENERGY_CONTRACT["contribution_weight"] * math.log(value) for value in target_normalized
    ]
    expected_log_potential = sum(
        probability * value for probability, value in zip(candidate, log_potential, strict=True)
    )
    return (
        expected_log_potential
        - ENERGY_CONTRACT["history_kl_weight"] * _kl(candidate, current)
        - ENERGY_CONTRACT["coverage_kl_weight"] * _kl(candidate, current)
    )


def _direction_agreement(current: list[float], left: list[float], right: list[float]) -> float:
    matches = 0
    for base, first, second in zip(current, left, right, strict=True):
        left_delta = first - base
        right_delta = second - base
        left_sign = 0 if abs(left_delta) <= 1e-12 else (1 if left_delta > 0 else -1)
        right_sign = 0 if abs(right_delta) <= 1e-12 else (1 if right_delta > 0 else -1)
        matches += int(left_sign == right_sign)
    return matches / len(current)


def _distribution_evidence(
    grouped: dict[str, list[dict[str, Any]]],
    *,
    proxy_field: str,
    target_field: str,
    proxy_scale: float,
    temperature: float,
) -> dict[str, Any]:
    task_rows: list[dict[str, Any]] = []
    for task_id, values in sorted(grouped.items()):
        ordered = sorted(values, key=lambda row: str(row["state_id"]))
        current = [float(row["current_probability"]) for row in ordered]
        proxy = _center(
            [proxy_scale * float(row[proxy_field]) for row in ordered],
            current,
        )
        target = _center([float(row[target_field]) for row in ordered], current)
        proxy_next, _ = _next_distribution(current, proxy, temperature=temperature)
        target_next, target_normalized = _next_distribution(
            current, target, temperature=temperature
        )
        tv = 0.5 * sum(abs(a - b) for a, b in zip(proxy_next, target_next, strict=True))
        target_objective = _variational_objective(target_next, current, target_normalized)
        proxy_objective = _variational_objective(proxy_next, current, target_normalized)
        current_objective = _variational_objective(current, current, target_normalized)
        regret = max(0.0, target_objective - proxy_objective)
        attainable_gain = max(target_objective - current_objective, CALIBRATION_FLOOR)
        task_rows.append(
            {
                "task_id": task_id,
                "total_variation": tv,
                "jensen_shannon": _jensen_shannon(proxy_next, target_next),
                "update_direction_agreement": _direction_agreement(
                    current, proxy_next, target_next
                ),
                "target_variational_objective": target_objective,
                "proxy_variational_objective": proxy_objective,
                "target_utility_regret": regret,
                "normalized_target_regret": regret / attainable_gain,
                "proxy_next_probabilities": proxy_next,
                "target_next_probabilities": target_next,
            }
        )
    if not task_rows:
        raise ValueError("authorization distribution evidence is empty")
    total_variation = [float(row["total_variation"]) for row in task_rows]
    jensen_shannon = [float(row["jensen_shannon"]) for row in task_rows]
    direction = [float(row["update_direction_agreement"]) for row in task_rows]
    normalized_regret = [float(row["normalized_target_regret"]) for row in task_rows]
    summary: dict[str, Any] = {
        "task_count": len(task_rows),
        "mean_total_variation": statistics.fmean(total_variation),
        "p95_total_variation": _percentile(total_variation, 0.95),
        "mean_jensen_shannon": statistics.fmean(jensen_shannon),
        "p95_jensen_shannon": _percentile(jensen_shannon, 0.95),
        "mean_update_direction_agreement": statistics.fmean(direction),
        "mean_normalized_target_regret": statistics.fmean(normalized_regret),
        "p95_normalized_target_regret": _percentile(normalized_regret, 0.95),
        "task_rows": task_rows,
    }
    summary["passes_distribution_gate"] = bool(
        summary["mean_total_variation"] <= DISTRIBUTION_GATES["maximum_mean_total_variation"]
        and summary["p95_total_variation"] <= DISTRIBUTION_GATES["maximum_p95_total_variation"]
        and summary["mean_jensen_shannon"] <= DISTRIBUTION_GATES["maximum_mean_jensen_shannon"]
        and summary["p95_jensen_shannon"] <= DISTRIBUTION_GATES["maximum_p95_jensen_shannon"]
        and summary["mean_update_direction_agreement"]
        >= DISTRIBUTION_GATES["minimum_update_direction_agreement"]
        and summary["mean_normalized_target_regret"]
        <= DISTRIBUTION_GATES["maximum_mean_normalized_target_regret"]
        and summary["p95_normalized_target_regret"]
        <= DISTRIBUTION_GATES["maximum_p95_normalized_target_regret"]
    )
    return summary


def _design_rows(coordinate_count: int) -> list[dict[str, Any]]:
    if coordinate_count != 60:
        raise ValueError("authorization requires exactly 60 task contrast coordinates")
    rows: list[dict[str, Any]] = []
    for index, hadamard_row in enumerate(_sylvester_hadamard(HADAMARD_ORDER)):
        payload = {
            "design_row_index": index,
            "role": "orthogonal_design",
            "signs": list(hadamard_row[:coordinate_count]),
        }
        payload["row_id"] = canonical_hash(payload, prefix="finance_authorization_design_row:")
        rows.append(payload)
    for replay_index, design_index in enumerate(NUMERIC_REPLAY_ROW_INDICES):
        source = rows[design_index]
        payload = {
            "design_row_index": design_index,
            "role": "numeric_replay",
            "replay_index": replay_index,
            "signs": source["signs"],
        }
        payload["row_id"] = canonical_hash(payload, prefix="finance_authorization_design_row:")
        rows.append(payload)
    return rows


def _split_rows_by_task(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["task_id"])].append(row)
    return dict(grouped)


def _prepare(args: argparse.Namespace) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_id)
    import torch
    from safetensors.torch import save_file

    gradient_dir = Path(args.gradient_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    gradient_plan = _read_json(gradient_dir / "plan.json")
    gradient_report = _read_json(gradient_dir / "report.json")
    gradient_manifest = _read_json(gradient_dir / "evaluation_gradient_manifest.json")
    support_plan = _read_json(Path(gradient_plan["source_support_plan_path"]))
    support_report = _read_json(Path(gradient_plan["source_support_report_path"]))
    if gradient_plan.get("experiment_version") != GRADIENT_ALIGNMENT_VERSION:
        raise ValueError("authorization requires the current Gradient Projection plan")
    if gradient_report.get("plan_hash") != gradient_plan.get("plan_hash"):
        raise ValueError("authorization Gradient report failed plan replay")
    if gradient_manifest.get("manifest_hash") != gradient_report.get(
        "evaluation_gradient_manifest_hash"
    ):
        raise ValueError("authorization evaluation-gradient manifest changed")
    if support_plan.get("plan_hash") != gradient_plan.get("source_support_plan_hash"):
        raise ValueError("authorization support plan identity changed")
    if support_report.get("report_hash") != gradient_plan.get("source_support_report_hash"):
        raise ValueError("authorization support report identity changed")
    if support_plan.get("strict_freshness_contract") != {
        "task_identity_overlap_allowed": False,
        "task_semantic_signature_overlap_allowed": False,
        "evidence_version_overlap_allowed": False,
    }:
        raise ValueError("authorization requires the strict three-layer freshness contract")
    if int(support_plan["freshness_funnel"]["strictly_fresh_task_count"]) < 30:
        raise ValueError("authorization has too few strictly fresh tasks")
    if gradient_report.get("task_count") != 30 or gradient_report.get("state_count") != 90:
        raise ValueError("authorization requires the frozen 30x3 target population")

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
        raise ValueError("authorization optimizer protocol is incompatible")
    learning_rate = float(optimizer["learning_rate"])
    if not math.isclose(learning_rate, 2e-4, rel_tol=0, abs_tol=1e-15):
        raise ValueError("authorization requires the preregistered 2e-4 learning rate")

    aggregate_by_split = {
        str(row["split"]): row for row in gradient_manifest["aggregate_gradients"]
    }
    if set(aggregate_by_split) != {"estimation", "validation"}:
        raise ValueError("authorization internal objective splits are incomplete")
    estimation_ids = tuple(str(value) for value in gradient_plan["gradient_estimation_record_ids"])
    validation_ids = tuple(str(value) for value in gradient_plan["gradient_validation_record_ids"])
    authorization_ids = tuple(str(value) for value in gradient_plan["final_test_record_ids"])
    if (
        len(estimation_ids) != 4
        or len(validation_ids) != 4
        or len(authorization_ids) != 8
        or set(estimation_ids) & set(validation_ids)
        or set(estimation_ids) & set(authorization_ids)
        or set(validation_ids) & set(authorization_ids)
    ):
        raise ValueError("authorization objective partitions are not strictly disjoint")

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
    grouped_sources = _split_rows_by_task(list(gradient_report["state_rows"]))
    output_dir.mkdir(parents=True, exist_ok=True)
    coordinate_dir = output_dir / "optimizer_coordinates"
    coordinate_dir.mkdir(parents=True, exist_ok=True)
    global_update: dict[str, Any] | None = None
    task_rows: list[dict[str, Any]] = []
    coordinate_artifacts: list[dict[str, Any]] = []
    for task_index, task_id in enumerate(sorted(grouped_sources)):
        sources = sorted(grouped_sources[task_id], key=lambda row: str(row["state_id"]))
        probabilities = [float(row["current_probability"]) for row in sources]
        if len(sources) != 3 or any(
            not math.isclose(value, 1.0 / 3.0, abs_tol=1e-12) for value in probabilities
        ):
            raise ValueError("authorization requires uniform three-state task support")
        task_marginal = float(gradient_report["task_marginals"][task_id])
        updates: list[dict[str, Any]] = []
        states: list[dict[str, Any]] = []
        for source in sources:
            gradient = _to_device(
                _load_verified_gradient(
                    Path(source["state_gradient_file"]),
                    str(source["state_gradient_sha256"]),
                ),
                device,
            )
            gradient_norm = _gradient_norm(gradient)
            update = _adamw_descent_direction(
                gradient,
                learning_rate=learning_rate,
                epsilon=ADAMW_EPSILON,
                maximum_gradient_norm=MAXIMUM_GRADIENT_NORM,
            )
            row: dict[str, Any] = {
                "task_id": task_id,
                "task_type": source["task_type"],
                "state_id": source["state_id"],
                "strategy": source["strategy"],
                "current_probability": source["current_probability"],
                "state_gradient_norm": gradient_norm,
            }
            for split in ("estimation", "validation"):
                dot, cosine = _normalized_gradient_alignment(
                    gradient,
                    objective_gradients[split],
                    left_norm=gradient_norm,
                    right_norm=objective_norms[split],
                )
                row[f"{split}_gp_a_raw"] = cosine
                row[f"{split}_gp_b_raw"] = dot
                row[f"{split}_gp_c_raw"] = _gradient_dot(update, objective_gradients[split])
            states.append(row)
            updates.append(update)
            del gradient
        for split in ("estimation", "validation"):
            for estimator_id, raw_name in (
                (DIAGNOSTIC_ESTIMATOR, "gp_a_raw"),
                (SECONDARY_ESTIMATOR, "gp_b_raw"),
                (PRIMARY_ESTIMATOR, "gp_c_raw"),
            ):
                centered = _center(
                    [float(row[f"{split}_{raw_name}"]) for row in states],
                    probabilities,
                )
                for row, value in zip(states, centered, strict=True):
                    row[f"{split}_{estimator_id}"] = value
        mean_update = _linear_gradient_combination(
            tuple(updates),
            tuple(task_marginal * value for value in probabilities),
        )
        if global_update is None:
            global_update = {name: value.clone() for name, value in mean_update.items()}
        else:
            for name in global_update:
                global_update[name].add_(mean_update[name])
        coordinate_indices = []
        for basis_index, basis in enumerate(CONTRAST_BASIS):
            coordinate_index = len(coordinate_artifacts)
            coordinate_indices.append(coordinate_index)
            coordinate = _linear_gradient_combination(
                tuple(updates), tuple(task_marginal * value for value in basis)
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
                "task_index": task_index,
                "task_id": task_id,
                "task_type": sources[0]["task_type"],
                "task_marginal": task_marginal,
                "probabilities": probabilities,
                "coordinate_indices": coordinate_indices,
                "states": states,
            }
        )
        del updates, mean_update
    if global_update is None or len(task_rows) != 30 or len(coordinate_artifacts) != 60:
        raise ValueError("authorization failed to construct the complete update space")
    global_path = output_dir / "optimizer_global_update.safetensors"
    save_file(_cpu_contiguous(global_update), global_path)
    plan: dict[str, Any] = {
        "experiment_version": AUTHORIZATION_VERSION,
        "role": "independent_contribution_approximation_authorization",
        "gradient_plan_path": str(gradient_dir / "plan.json"),
        "gradient_plan_hash": gradient_plan["plan_hash"],
        "gradient_report_path": str(gradient_dir / "report.json"),
        "gradient_report_hash": gradient_report["report_hash"],
        "evaluation_gradient_manifest_hash": gradient_manifest["manifest_hash"],
        "support_plan_path": gradient_plan["source_support_plan_path"],
        "support_plan_hash": support_plan["plan_hash"],
        "support_report_hash": support_report["report_hash"],
        "strict_freshness_contract": support_plan["strict_freshness_contract"],
        "freshness_funnel": support_plan["freshness_funnel"],
        "optimizer_protocol_path": str(protocol_path),
        "optimizer_protocol_sha256": _sha256(protocol_path),
        "optimizer_contract": {
            "optimizer_name": "adamw",
            "step_count": 1,
            "cold_start": True,
            "learning_rate": learning_rate,
            "betas": list(ADAMW_BETAS),
            "epsilon": ADAMW_EPSILON,
            "weight_decay": ADAMW_WEIGHT_DECAY,
            "maximum_gradient_norm": MAXIMUM_GRADIENT_NORM,
            "optimizer_state_policy": "reinitialize_per_state_intervention",
        },
        "batch_semantics": {
            "estimand": "expected_per_state_optimizer_update",
            "formula": "E_pi[U_AdamW(g_z)]",
            "mixed_state_batch_formula": "U_AdamW(E_pi[g_z])",
            "mixed_state_batch_allowed": False,
            "state_sampling_granularity": "one_state_record_per_optimizer_step",
            "gradient_accumulation_steps": 1,
            "required_student_training_contract": "state_homogeneous_cold_start_adamw",
        },
        "estimator_preregistration": {
            "primary": PRIMARY_ESTIMATOR,
            "secondary": SECONDARY_ESTIMATOR,
            "diagnostic_only": DIAGNOSTIC_ESTIMATOR,
            "selection_frozen_before_authorization_objective_access": True,
        },
        "estimator_contracts": {
            DIAGNOSTIC_ESTIMATOR: "pi_centered_gradient_cosine",
            SECONDARY_ESTIMATOR: "pi_centered_objective_dot_state_gradient",
            PRIMARY_ESTIMATOR: "pi_centered_objective_dot_cold_start_adamw_descent",
        },
        "calibration_contract": {
            "method": "global_median_absolute_scale_through_zero",
            "fit_split": "estimation",
            "freeze_split": "validation",
            "authorization_split_may_tune": False,
            "temperature_method": "estimation_target_global_median_absolute_value",
            "minimum_scale": CALIBRATION_FLOOR,
        },
        "rank_gate_contract": "existing_cluster_bootstrap_and_permutation_rank_gate_v1",
        "distribution_gate_contract": DISTRIBUTION_GATES,
        "energy_contract": ENERGY_CONTRACT,
        "model_dir": gradient_plan["model_dir"],
        "base_model_manifest_hash": gradient_plan["base_model_manifest_hash"],
        "beneficiary_adapter_dir": gradient_plan["beneficiary_adapter_dir"],
        "beneficiary_adapter_tensor_sha256": gradient_plan["beneficiary_adapter_tensor_sha256"],
        "beneficiary_model_state_id": gradient_plan["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": gradient_plan["beneficiary_checkpoint_hash"],
        "source_records_path": gradient_plan["source_records_path"],
        "source_records_sha256": gradient_plan["source_records_sha256"],
        "objective_partitions": {
            "estimation": {
                "record_ids": list(estimation_ids),
                "set_id": gradient_plan["gradient_estimation_set_id"],
                "objective_gradient_accessed_at_prepare": True,
            },
            "validation": {
                "record_ids": list(validation_ids),
                "set_id": gradient_plan["gradient_validation_set_id"],
                "objective_gradient_accessed_at_prepare": True,
            },
            "authorization": {
                "record_ids": list(authorization_ids),
                "set_id": gradient_plan["final_test_set_id"],
                "objective_gradient_accessed_at_prepare": False,
            },
        },
        "objective_partition_disjoint": True,
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
        "design_rows": _design_rows(len(coordinate_artifacts)),
        "orthogonal_design_row_count": HADAMARD_ORDER,
        "numeric_replay_row_indices": list(NUMERIC_REPLAY_ROW_INDICES),
        "intervention_epsilon": INTERVENTION_EPSILON,
        "maximum_reconstruction_relative_error": MAXIMUM_RECONSTRUCTION_RELATIVE_ERROR,
        "authorization_objective_accessed": False,
        "production_authorized": False,
        "claim_boundary": (
            "This plan can authorize only the preregistered GP-C estimator under one-step, "
            "cold-start AdamW and expected-per-state update semantics. It cannot authorize "
            "optimizer continuation, mixed-state batches, multi-step training, or estimator "
            "selection based on the untouched authorization objective."
        ),
    }
    plan["plan_hash"] = canonical_hash(plan, prefix="finance_contribution_authorization_plan:")
    _write_json(output_dir / "plan.json", plan)
    print(
        json.dumps(
            {
                "plan_hash": plan["plan_hash"],
                "task_count": plan["task_count"],
                "state_count": plan["state_count"],
                "strictly_fresh_task_count": plan["freshness_funnel"]["strictly_fresh_task_count"],
                "authorization_objective_accessed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    del objective_gradients, global_update
    gc.collect()
    torch.cuda.empty_cache()


def _preflight(args: argparse.Namespace) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_id)
    import torch
    from safetensors.torch import save_file

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    _assert_canonical_artifact(
        plan,
        hash_field="plan_hash",
        prefix="finance_contribution_authorization_plan:",
        artifact_name="authorization plan",
    )
    if plan.get("experiment_version") != AUTHORIZATION_VERSION:
        raise ValueError("authorization preflight requires a current plan")
    _seed_everything(AUTHORIZATION_NUMERIC_SEED)
    torch.cuda.reset_peak_memory_stats()
    model = _baseline_lora_model(Path(plan["model_dir"]), Path(plan["beneficiary_adapter_dir"]))
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("authorization preflight loaded another Adapter")
    parameters = {
        name: parameter
        for name, parameter in sorted(model.named_parameters())
        if parameter.requires_grad
    }
    initial = {name: value.detach().clone() for name, value in parameters.items()}
    gradient_report = _read_json(Path(plan["gradient_report_path"]))
    first = plan["task_rows"][0]["states"][0]
    source = next(
        row
        for row in gradient_report["state_rows"]
        if row["task_id"] == first["task_id"] and row["state_id"] == first["state_id"]
    )
    gradient = _to_device(
        _load_verified_gradient(
            Path(source["state_gradient_file"]), str(source["state_gradient_sha256"])
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
        parameter.grad = gradient[name].to(parameter.device, parameter.dtype).clone()
    torch.nn.utils.clip_grad_norm_(
        tuple(parameters.values()), float(contract["maximum_gradient_norm"])
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
        raise ValueError("authorization AdamW did not start from empty state")
    optimizer.step()
    actual = {name: initial[name] - parameter.detach() for name, parameter in parameters.items()}
    formula_fidelity = _vector_fidelity(expected, actual)
    with torch.no_grad():
        for name, parameter in parameters.items():
            parameter.copy_(initial[name])
            parameter.grad = None
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("authorization preflight failed Adapter restoration")
    global_update = _to_device(
        _load_verified_gradient(
            Path(plan["global_update_artifact"]["file"]),
            str(plan["global_update_artifact"]["sha256"]),
        ),
        torch.device("cuda"),
    )
    baseline = {
        name: initial[name] - global_update[name].to(dtype=initial[name].dtype) for name in initial
    }
    coordinates = tuple(
        _to_device(
            _load_verified_gradient(Path(row["file"]), str(row["sha256"])),
            torch.device("cuda"),
        )
        for row in plan["coordinate_artifacts"]
    )
    direction_dir = output_dir / "optimizer_directions"
    direction_dir.mkdir(parents=True, exist_ok=True)
    direction_artifacts = []
    fidelity_rows = []
    for design in plan["design_rows"][:HADAMARD_ORDER]:
        direction = _combine_coordinate_directions(
            coordinates, tuple(int(value) for value in design["signs"])
        )
        path = direction_dir / f"direction_{design['design_row_index']:02d}.safetensors"
        save_file(_cpu_contiguous(direction), path)
        direction_artifacts.append(
            {
                "design_row_index": design["design_row_index"],
                "row_id": design["row_id"],
                "file": str(path),
                "sha256": _sha256(path),
                "update_norm": _gradient_norm(direction),
            }
        )
        for label, sign in (("plus", 1.0), ("minus", -1.0)):
            value = {name: sign * tensor for name, tensor in direction.items()}
            row: dict[str, Any] = dict(
                _parameter_step_fidelity(
                    initial,
                    baseline,
                    global_update,
                    value,
                    learning_rate=1.0,
                    directional_scale=float(plan["intervention_epsilon"]),
                )
            )
            row.update(
                {
                    "design_row_index": design["design_row_index"],
                    "intervention_sign": label,
                }
            )
            fidelity_rows.append(row)
        del direction
    storage_fidelity = _fidelity_summary(fidelity_rows)
    formula_passed = bool(
        formula_fidelity["cosine"] >= 0.999 and formula_fidelity["relative_error"] <= 0.01
    )
    status = "passed" if formula_passed and storage_fidelity["passes"] else "failed"
    report: dict[str, Any] = {
        "experiment_version": AUTHORIZATION_VERSION,
        "plan_hash": plan["plan_hash"],
        "status": status,
        "optimizer_formula_fidelity": formula_fidelity,
        "optimizer_formula_passed": formula_passed,
        "parameter_storage_fidelity": storage_fidelity,
        "direction_artifacts": direction_artifacts,
        "direction_manifest_hash": canonical_hash(
            direction_artifacts, prefix="finance_authorization_direction_manifest:"
        ),
        "authorization_objective_accessed": False,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
    }
    report["preflight_hash"] = canonical_hash(
        report, prefix="finance_contribution_authorization_preflight:"
    )
    _write_json(output_dir / "preflight.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    del model, gradient, expected, actual, global_update, coordinates
    gc.collect()
    torch.cuda.empty_cache()


def _target_prefix(split: str) -> str:
    return f"finance_authorization_{split}_target_result:"


def _worker(args: argparse.Namespace) -> None:
    split = str(args.split)
    if split not in {"estimation", "validation", "authorization"}:
        raise ValueError("authorization worker received an unknown objective split")
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_id)
    import torch
    from peft import get_peft_model_state_dict

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    preflight = _read_json(output_dir / "preflight.json")
    _assert_canonical_artifact(
        plan,
        hash_field="plan_hash",
        prefix="finance_contribution_authorization_plan:",
        artifact_name="authorization plan",
    )
    _assert_canonical_artifact(
        preflight,
        hash_field="preflight_hash",
        prefix="finance_contribution_authorization_preflight:",
        artifact_name="authorization preflight",
    )
    if preflight.get("plan_hash") != plan.get("plan_hash") or preflight.get("status") != "passed":
        raise ValueError("authorization worker requires a passing preflight")
    if split == "authorization":
        calibration = _read_json(output_dir / "calibration.json")
        proxy = _read_json(output_dir / "authorization_proxy.json")
        _assert_canonical_artifact(
            calibration,
            hash_field="calibration_hash",
            prefix="finance_contribution_authorization_calibration:",
            artifact_name="authorization calibration",
        )
        _assert_canonical_artifact(
            proxy,
            hash_field="proxy_hash",
            prefix="finance_contribution_authorization_proxy:",
            artifact_name="authorization proxy",
        )
        if (
            calibration.get("plan_hash") != plan["plan_hash"]
            or calibration.get("status") != "passed"
            or proxy.get("calibration_hash") != calibration.get("calibration_hash")
            or proxy.get("status") != "passed"
        ):
            raise ValueError("authorization target remains sealed before frozen calibration")
    if _sha256(Path(plan["source_records_path"])) != plan["source_records_sha256"]:
        raise ValueError("authorization source records changed")
    rows = [
        row
        for index, row in enumerate(plan["design_rows"])
        if index % args.partition_count == args.partition_index
    ]
    worker_dir = output_dir / "workers" / split
    worker_dir.mkdir(parents=True, exist_ok=True)
    worker_path = worker_dir / f"partition_{args.partition_index}.jsonl"
    completed = {
        str(row["row_id"])
        for row in _load_jsonl(worker_path)
        if row.get("status") == "passed" and _valid_hashed_row(row, prefix=_target_prefix(split))
    }
    directions = {int(row["design_row_index"]): row for row in preflight["direction_artifacts"]}
    records = _load_records(Path(plan["source_records_path"]))
    objective_records = tuple(
        records[value] for value in plan["objective_partitions"][split]["record_ids"]
    )
    _seed_everything(AUTHORIZATION_NUMERIC_SEED)
    torch.cuda.reset_peak_memory_stats()
    tokenizer = _load_tokenizer(Path(plan["model_dir"]))
    model = _baseline_lora_model(Path(plan["model_dir"]), Path(plan["beneficiary_adapter_dir"]))
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("authorization worker loaded another Adapter")
    baseline_state = {
        name: tensor.detach().cpu().clone()
        for name, tensor in get_peft_model_state_dict(model).items()
    }
    global_update = _load_verified_gradient(
        Path(plan["global_update_artifact"]["file"]),
        str(plan["global_update_artifact"]["sha256"]),
    )
    _restore_adapter(model, baseline_state)
    _apply_descent_vector(model, global_update)
    baseline_performance, baseline_loss, baseline_tokens = _evaluate(
        model, tokenizer, objective_records
    )
    baseline_hash = _adapter_tensor_sha256(model)
    started = time.monotonic()
    completed_now = 0
    for row in rows:
        if str(row["row_id"]) in completed:
            continue
        artifact = directions[int(row["design_row_index"])]
        direction = _load_verified_gradient(Path(artifact["file"]), str(artifact["sha256"]))
        plus = {
            name: value.clone().add_(direction[name], alpha=float(plan["intervention_epsilon"]))
            for name, value in global_update.items()
        }
        minus = {
            name: value.clone().add_(direction[name], alpha=-float(plan["intervention_epsilon"]))
            for name, value in global_update.items()
        }
        _seed_everything(AUTHORIZATION_NUMERIC_SEED)
        _restore_adapter(model, baseline_state)
        _apply_descent_vector(model, plus)
        plus_performance, plus_loss, plus_tokens = _evaluate(model, tokenizer, objective_records)
        plus_hash = _adapter_tensor_sha256(model)
        _seed_everything(AUTHORIZATION_NUMERIC_SEED)
        _restore_adapter(model, baseline_state)
        _apply_descent_vector(model, minus)
        minus_performance, minus_loss, minus_tokens = _evaluate(model, tokenizer, objective_records)
        minus_hash = _adapter_tensor_sha256(model)
        if plus_tokens != baseline_tokens or minus_tokens != baseline_tokens:
            raise ValueError("authorization target changed objective token support")
        result: dict[str, Any] = {
            "experiment_version": AUTHORIZATION_VERSION,
            "plan_hash": plan["plan_hash"],
            "preflight_hash": preflight["preflight_hash"],
            "objective_split": split,
            "objective_set_id": plan["objective_partitions"][split]["set_id"],
            "row_id": row["row_id"],
            "design_row_index": row["design_row_index"],
            "role": row["role"],
            "replay_index": row.get("replay_index"),
            "partition_index": args.partition_index,
            "partition_count": args.partition_count,
            "gpu_id": args.gpu_id,
            "status": "passed",
            "baseline_performance": baseline_performance,
            "baseline_loss": baseline_loss,
            "plus_performance": plus_performance,
            "plus_loss": plus_loss,
            "minus_performance": minus_performance,
            "minus_loss": minus_loss,
            "central_directional_derivative": (
                (plus_performance - minus_performance) / (2.0 * float(plan["intervention_epsilon"]))
            ),
            "objective_supervised_tokens": baseline_tokens,
            "baseline_adapter_tensor_sha256": baseline_hash,
            "plus_adapter_tensor_sha256": plus_hash,
            "minus_adapter_tensor_sha256": minus_hash,
            "direction_sha256": artifact["sha256"],
            "numeric_seed": AUTHORIZATION_NUMERIC_SEED,
        }
        result["result_hash"] = canonical_hash(result, prefix=_target_prefix(split))
        _append_jsonl(worker_path, result)
        completed_now += 1
        del direction, plus, minus
    report = {
        "plan_hash": plan["plan_hash"],
        "objective_split": split,
        "partition_index": args.partition_index,
        "partition_count": args.partition_count,
        "gpu_id": args.gpu_id,
        "assigned_count": len(rows),
        "completed_now": completed_now,
        "runtime_seconds": time.monotonic() - started,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
    }
    _write_json(worker_dir / f"partition_{args.partition_index}_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    del model, global_update, baseline_state
    gc.collect()
    torch.cuda.empty_cache()


def _run(args: argparse.Namespace) -> None:
    if not args.gpu_ids or len(args.gpu_ids) != len(set(args.gpu_ids)):
        raise ValueError("authorization run requires unique GPU ids")
    context = get_context("spawn")
    reports = []
    with ProcessPoolExecutor(max_workers=len(args.gpu_ids), mp_context=context) as executor:
        futures = {
            executor.submit(
                _worker,
                argparse.Namespace(
                    output_dir=args.output_dir,
                    split=args.split,
                    gpu_id=gpu_id,
                    partition_index=index,
                    partition_count=len(args.gpu_ids),
                ),
            ): index
            for index, gpu_id in enumerate(args.gpu_ids)
        }
        for future in as_completed(futures):
            future.result()
            reports.append(futures[future])
    print(json.dumps({"completed_partitions": sorted(reports)}, indent=2))


def _aggregate_target(args: argparse.Namespace) -> None:
    split = str(args.split)
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    preflight = _read_json(output_dir / "preflight.json")
    _assert_canonical_artifact(
        plan,
        hash_field="plan_hash",
        prefix="finance_contribution_authorization_plan:",
        artifact_name="authorization plan",
    )
    _assert_canonical_artifact(
        preflight,
        hash_field="preflight_hash",
        prefix="finance_contribution_authorization_preflight:",
        artifact_name="authorization preflight",
    )
    if preflight.get("plan_hash") != plan.get("plan_hash") or preflight.get("status") != "passed":
        raise ValueError("authorization target aggregate requires a passing preflight")
    rows = [
        row
        for path in sorted((output_dir / "workers" / split).glob("partition_*.jsonl"))
        for row in _load_jsonl(path)
    ]
    if len(rows) != len(plan["design_rows"]):
        raise ValueError(f"authorization {split} target matrix is incomplete")
    if any(not _valid_hashed_row(row, prefix=_target_prefix(split)) for row in rows):
        raise ValueError(f"authorization {split} target identity failed replay")
    if any(
        row.get("plan_hash") != plan["plan_hash"]
        or row.get("objective_split") != split
        or row.get("objective_set_id") != plan["objective_partitions"][split]["set_id"]
        or row.get("preflight_hash") != preflight["preflight_hash"]
        for row in rows
    ):
        raise ValueError(f"authorization {split} worker contract changed")
    by_id = {str(row["row_id"]): row for row in rows}
    if len(by_id) != len(rows) or set(by_id) != {str(row["row_id"]) for row in plan["design_rows"]}:
        raise ValueError(f"authorization {split} design support changed")
    ordered = [
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
        raise ValueError(f"authorization {split} target replay is nondeterministic")
    hadamard = _sylvester_hadamard(HADAMARD_ORDER)
    observed = [float(row["central_directional_derivative"]) for row in ordered]
    coordinate_values = [
        sum(hadamard[row][column] * observed[row] for row in range(HADAMARD_ORDER)) / HADAMARD_ORDER
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
    relative_error = residual_norm / observed_norm if observed_norm else math.inf
    state_rows = []
    for task in plan["task_rows"]:
        first, second = task["coordinate_indices"]
        recovered = _recover_centered_state_values(
            coordinate_values[first],
            coordinate_values[second],
            task_marginal=float(task["task_marginal"]),
        )
        for state, value in zip(task["states"], recovered, strict=True):
            state_rows.append(
                {
                    "task_id": task["task_id"],
                    "task_type": task["task_type"],
                    "state_id": state["state_id"],
                    "strategy": state["strategy"],
                    "current_probability": state["current_probability"],
                    "optimizer_target": value,
                }
            )
    status = (
        "passed"
        if relative_error <= float(plan["maximum_reconstruction_relative_error"])
        else "failed"
    )
    report: dict[str, Any] = {
        "experiment_version": AUTHORIZATION_VERSION,
        "plan_hash": plan["plan_hash"],
        "preflight_hash": preflight["preflight_hash"],
        "objective_split": split,
        "objective_set_id": plan["objective_partitions"][split]["set_id"],
        "status": status,
        "result_count": len(rows),
        "maximum_numeric_replay_range": maximum_replay_range,
        "reconstruction_relative_error": relative_error,
        "coordinate_values": coordinate_values,
        "state_rows": state_rows,
        "authorization_objective_accessed": split == "authorization",
    }
    report["target_hash"] = canonical_hash(report, prefix=f"finance_{split}_authorization_target:")
    target_dir = output_dir / "targets"
    target_dir.mkdir(parents=True, exist_ok=True)
    _write_json(target_dir / f"{split}.json", report)
    print(
        json.dumps(
            {
                "objective_split": split,
                "status": status,
                "target_hash": report["target_hash"],
                "reconstruction_relative_error": relative_error,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _rows_with_target(
    plan: dict[str, Any], target: dict[str, Any], *, split: str
) -> list[dict[str, Any]]:
    target_by_key = {
        (str(row["task_id"]), str(row["state_id"])): row for row in target["state_rows"]
    }
    rows = []
    for task in plan["task_rows"]:
        for state in task["states"]:
            key = (str(task["task_id"]), str(state["state_id"]))
            if key not in target_by_key:
                raise ValueError(f"authorization {split} target support changed")
            rows.append(
                {
                    **state,
                    "task_id": task["task_id"],
                    "task_type": task["task_type"],
                    "optimizer_target": target_by_key[key]["optimizer_target"],
                }
            )
    return rows


def _calibrate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    estimation_target = _read_json(output_dir / "targets" / "estimation.json")
    validation_target = _read_json(output_dir / "targets" / "validation.json")
    _assert_canonical_artifact(
        plan,
        hash_field="plan_hash",
        prefix="finance_contribution_authorization_plan:",
        artifact_name="authorization plan",
    )
    for split, target in (
        ("estimation", estimation_target),
        ("validation", validation_target),
    ):
        _assert_canonical_artifact(
            target,
            hash_field="target_hash",
            prefix=f"finance_{split}_authorization_target:",
            artifact_name=f"authorization {split} target",
        )
    if (output_dir / "targets" / "authorization.json").exists() or (
        output_dir / "authorization_proxy.json"
    ).exists():
        raise ValueError("authorization objective was opened before calibration froze")
    if any(
        target.get("plan_hash") != plan["plan_hash"] or target.get("status") != "passed"
        for target in (estimation_target, validation_target)
    ):
        raise ValueError("authorization calibration requires passing internal targets")
    estimation_rows = _rows_with_target(plan, estimation_target, split="estimation")
    validation_rows = _rows_with_target(plan, validation_target, split="validation")
    estimation_grouped = _split_rows_by_task(estimation_rows)
    validation_grouped = _split_rows_by_task(validation_rows)
    target_values = [float(row["optimizer_target"]) for row in estimation_rows]
    temperature = statistics.median(abs(value) for value in target_values)
    if temperature <= CALIBRATION_FLOOR:
        raise ValueError("authorization target temperature is degenerate")
    estimator_rows: dict[str, Any] = {}
    for index, estimator_id in enumerate(ESTIMATOR_IDS):
        estimation_field = f"estimation_{estimator_id}"
        validation_field = f"validation_{estimator_id}"
        scale = _robust_positive_scale(
            [float(row[estimation_field]) for row in estimation_rows], target_values
        )
        estimation_rank = _rank_evidence(
            estimation_grouped,
            estimator_field=estimation_field,
            target_field="optimizer_target",
            seed=AUTHORIZATION_NUMERIC_SEED + 100 * index,
        )
        validation_rank = _rank_evidence(
            validation_grouped,
            estimator_field=validation_field,
            target_field="optimizer_target",
            seed=AUTHORIZATION_NUMERIC_SEED + 100 * index + 10,
        )
        estimation_distribution = _distribution_evidence(
            estimation_grouped,
            proxy_field=estimation_field,
            target_field="optimizer_target",
            proxy_scale=scale,
            temperature=temperature,
        )
        validation_distribution = _distribution_evidence(
            validation_grouped,
            proxy_field=validation_field,
            target_field="optimizer_target",
            proxy_scale=scale,
            temperature=temperature,
        )
        estimator_rows[estimator_id] = {
            "robust_scale": scale,
            "contribution_temperature": temperature,
            "estimation_rank": estimation_rank,
            "validation_rank": validation_rank,
            "estimation_distribution": estimation_distribution,
            "validation_distribution": validation_distribution,
            "internal_gate_passed": bool(
                estimation_rank["passes_rank_gate"]
                and validation_rank["passes_rank_gate"]
                and validation_distribution["passes_distribution_gate"]
            ),
        }
    primary = estimator_rows[PRIMARY_ESTIMATOR]
    status = "passed" if primary["internal_gate_passed"] else "failed"
    calibration: dict[str, Any] = {
        "experiment_version": AUTHORIZATION_VERSION,
        "plan_hash": plan["plan_hash"],
        "status": status,
        "fit_split": "estimation",
        "freeze_split": "validation",
        "authorization_split_accessed": False,
        "estimator_selection": plan["estimator_preregistration"],
        "calibration_contract": plan["calibration_contract"],
        "distribution_gate_contract": plan["distribution_gate_contract"],
        "energy_contract": plan["energy_contract"],
        "estimation_target_hash": estimation_target["target_hash"],
        "validation_target_hash": validation_target["target_hash"],
        "estimator_rows": estimator_rows,
        "blockers": [] if status == "passed" else ["primary_internal_gate_failed"],
    }
    calibration["calibration_hash"] = canonical_hash(
        calibration, prefix="finance_contribution_authorization_calibration:"
    )
    _write_json(output_dir / "calibration.json", calibration)
    print(
        json.dumps(
            {
                "status": status,
                "calibration_hash": calibration["calibration_hash"],
                "primary_internal_gate_passed": primary["internal_gate_passed"],
                "authorization_split_accessed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _build_authorization_gradient(args: argparse.Namespace) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_id)
    import torch
    from safetensors.torch import save_file

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    calibration = _read_json(output_dir / "calibration.json")
    _assert_canonical_artifact(
        plan,
        hash_field="plan_hash",
        prefix="finance_contribution_authorization_plan:",
        artifact_name="authorization plan",
    )
    _assert_canonical_artifact(
        calibration,
        hash_field="calibration_hash",
        prefix="finance_contribution_authorization_calibration:",
        artifact_name="authorization calibration",
    )
    if (
        calibration.get("plan_hash") != plan.get("plan_hash")
        or calibration.get("status") != "passed"
    ):
        raise ValueError("authorization objective remains sealed before calibration passes")
    if (output_dir / "targets" / "authorization.json").exists():
        raise ValueError("authorization proxy must freeze before target access")
    if _sha256(Path(plan["source_records_path"])) != plan["source_records_sha256"]:
        raise ValueError("authorization records changed before objective-gradient access")
    _seed_everything(AUTHORIZATION_NUMERIC_SEED + 1)
    torch.cuda.reset_peak_memory_stats()
    tokenizer = _load_tokenizer(Path(plan["model_dir"]))
    model = _baseline_lora_model(Path(plan["model_dir"]), Path(plan["beneficiary_adapter_dir"]))
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("authorization objective loaded another Adapter")
    parameter_manifest, parameter_manifest_hash = _gradient_parameter_manifest(model)
    internal_manifest = _read_json(
        Path(plan["gradient_plan_path"]).parent / "evaluation_gradient_manifest.json"
    )
    if (
        parameter_manifest_hash != internal_manifest["parameter_manifest_hash"]
        or parameter_manifest != internal_manifest["parameter_manifest"]
    ):
        raise ValueError("authorization objective parameter space changed")
    records = _load_records(Path(plan["source_records_path"]))
    record_ids = tuple(plan["objective_partitions"]["authorization"]["record_ids"])
    gradient_dir = output_dir / "authorization_gradients"
    gradient_dir.mkdir(parents=True, exist_ok=True)
    gradients_by_id = {}
    record_rows = []
    for index, record_id in enumerate(record_ids):
        gradient, loss, supervised_tokens = _record_gradient(model, tokenizer, records[record_id])
        path = gradient_dir / f"record_{index:02d}.safetensors"
        save_file(gradient, path)
        gradients_by_id[record_id] = gradient
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
    aggregate = _weighted_gradient(
        [gradients_by_id[record_id] for record_id in record_ids],
        [float(row["supervised_tokens"]) for row in record_rows],
    )
    aggregate_path = gradient_dir / "authorization_aggregate.safetensors"
    save_file(aggregate, aggregate_path)
    aggregate_artifact = {
        "split": "authorization",
        "record_ids": list(record_ids),
        "weights": [float(row["supervised_tokens"]) for row in record_rows],
        "file": str(aggregate_path),
        "sha256": _sha256(aggregate_path),
        "gradient_norm": _gradient_norm(aggregate),
    }
    device = torch.device("cuda")
    objective = _to_device(aggregate, device)
    objective_norm = _gradient_norm(objective)
    gradient_report = _read_json(Path(plan["gradient_report_path"]))
    source_by_key = {
        (str(row["task_id"]), str(row["state_id"])): row for row in gradient_report["state_rows"]
    }
    state_rows = []
    for task in plan["task_rows"]:
        raw_rows = []
        probabilities = [float(value) for value in task["probabilities"]]
        for state in task["states"]:
            key = (str(task["task_id"]), str(state["state_id"]))
            source = source_by_key.get(key)
            if source is None:
                raise ValueError("authorization proxy state support changed")
            state_gradient = _to_device(
                _load_verified_gradient(
                    Path(source["state_gradient_file"]),
                    str(source["state_gradient_sha256"]),
                ),
                device,
            )
            state_norm = _gradient_norm(state_gradient)
            dot, cosine = _normalized_gradient_alignment(
                state_gradient,
                objective,
                left_norm=state_norm,
                right_norm=objective_norm,
            )
            update = _adamw_descent_direction(
                state_gradient,
                learning_rate=float(plan["optimizer_contract"]["learning_rate"]),
                epsilon=float(plan["optimizer_contract"]["epsilon"]),
                maximum_gradient_norm=float(plan["optimizer_contract"]["maximum_gradient_norm"]),
            )
            raw_rows.append(
                {
                    "task_id": task["task_id"],
                    "task_type": task["task_type"],
                    "state_id": state["state_id"],
                    "strategy": state["strategy"],
                    "current_probability": state["current_probability"],
                    "authorization_gp_a_raw": cosine,
                    "authorization_gp_b_raw": dot,
                    "authorization_gp_c_raw": _gradient_dot(update, objective),
                }
            )
            del state_gradient, update
        for estimator_id, raw_field in (
            (DIAGNOSTIC_ESTIMATOR, "authorization_gp_a_raw"),
            (SECONDARY_ESTIMATOR, "authorization_gp_b_raw"),
            (PRIMARY_ESTIMATOR, "authorization_gp_c_raw"),
        ):
            centered = _center([float(row[raw_field]) for row in raw_rows], probabilities)
            for row, value in zip(raw_rows, centered, strict=True):
                row[f"authorization_{estimator_id}"] = value
        state_rows.extend(raw_rows)
    proxy: dict[str, Any] = {
        "experiment_version": AUTHORIZATION_VERSION,
        "plan_hash": plan["plan_hash"],
        "calibration_hash": calibration["calibration_hash"],
        "status": "passed",
        "authorization_objective_accessed": True,
        "authorization_target_accessed": False,
        "objective_set_id": plan["objective_partitions"]["authorization"]["set_id"],
        "parameter_manifest_hash": parameter_manifest_hash,
        "record_gradients": record_rows,
        "aggregate_gradient": aggregate_artifact,
        "state_rows": state_rows,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
    }
    proxy["proxy_hash"] = canonical_hash(proxy, prefix="finance_contribution_authorization_proxy:")
    _write_json(output_dir / "authorization_proxy.json", proxy)
    print(
        json.dumps(
            {
                "status": proxy["status"],
                "proxy_hash": proxy["proxy_hash"],
                "record_count": len(record_rows),
                "state_count": len(state_rows),
                "authorization_target_accessed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    del model, aggregate, objective, gradients_by_id
    gc.collect()
    torch.cuda.empty_cache()


def _diagnose_post_update_objective(args: argparse.Namespace) -> None:
    """Test the correct finite-intervention linearization point on internal splits only."""
    gpu_ids = tuple(int(value) for value in args.gpu_ids)
    if not gpu_ids or len(gpu_ids) != len(set(gpu_ids)):
        raise ValueError("post-update diagnostic requires unique GPU ids")
    os.environ["CUDA_VISIBLE_DEVICES"] = ",".join(str(value) for value in gpu_ids)
    import torch

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    estimation_target = _read_json(output_dir / "targets" / "estimation.json")
    validation_target = _read_json(output_dir / "targets" / "validation.json")
    _assert_canonical_artifact(
        plan,
        hash_field="plan_hash",
        prefix="finance_contribution_authorization_plan:",
        artifact_name="authorization plan",
    )
    for split, target in (
        ("estimation", estimation_target),
        ("validation", validation_target),
    ):
        _assert_canonical_artifact(
            target,
            hash_field="target_hash",
            prefix=f"finance_{split}_authorization_target:",
            artifact_name=f"authorization {split} target",
        )
    if (output_dir / "targets" / "authorization.json").exists() or (
        output_dir / "authorization_proxy.json"
    ).exists():
        raise ValueError("post-update diagnostic cannot run after authorization access")
    if any(
        target.get("plan_hash") != plan["plan_hash"] or target.get("status") != "passed"
        for target in (estimation_target, validation_target)
    ):
        raise ValueError("post-update diagnostic requires passing internal targets")
    _seed_everything(AUTHORIZATION_NUMERIC_SEED + 2)
    torch.cuda.reset_peak_memory_stats()
    tokenizer = _load_tokenizer(Path(plan["model_dir"]))
    model = (
        _baseline_lora_model(Path(plan["model_dir"]), Path(plan["beneficiary_adapter_dir"]))
        if len(gpu_ids) == 1
        else _sharded_baseline_lora_model(
            Path(plan["model_dir"]),
            Path(plan["beneficiary_adapter_dir"]),
            visible_gpu_count=len(gpu_ids),
        )
    )
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("post-update diagnostic loaded another Adapter")
    global_update = _load_verified_gradient(
        Path(plan["global_update_artifact"]["file"]),
        str(plan["global_update_artifact"]["sha256"]),
    )
    _apply_descent_vector(model, global_update)
    post_update_adapter_hash = _adapter_tensor_sha256(model)
    records = _load_records(Path(plan["source_records_path"]))
    objective_gradients: dict[str, dict[str, Any]] = {}
    objective_rows: dict[str, list[dict[str, Any]]] = {}
    for split in ("estimation", "validation"):
        rows = []
        gradients = []
        for record_id in plan["objective_partitions"][split]["record_ids"]:
            gradient, loss, supervised_tokens = _record_gradient(
                model, tokenizer, records[record_id]
            )
            gradients.append(gradient)
            rows.append(
                {
                    "record_id": record_id,
                    "loss": loss,
                    "supervised_tokens": supervised_tokens,
                    "gradient_norm": _gradient_norm(gradient),
                }
            )
        objective_gradients[split] = _weighted_gradient(
            gradients,
            [float(row["supervised_tokens"]) for row in rows],
        )
        objective_rows[split] = rows
    gradient_report = _read_json(Path(plan["gradient_report_path"]))
    source_by_key = {
        (str(row["task_id"]), str(row["state_id"])): row for row in gradient_report["state_rows"]
    }
    device = torch.device("cuda")
    objective_device = {
        split: _to_device(values, device) for split, values in objective_gradients.items()
    }
    objective_norms = {split: _gradient_norm(values) for split, values in objective_device.items()}
    rows_by_split: dict[str, list[dict[str, Any]]] = {
        "estimation": [],
        "validation": [],
    }
    targets = {
        "estimation": {
            (str(row["task_id"]), str(row["state_id"])): float(row["optimizer_target"])
            for row in estimation_target["state_rows"]
        },
        "validation": {
            (str(row["task_id"]), str(row["state_id"])): float(row["optimizer_target"])
            for row in validation_target["state_rows"]
        },
    }
    for task in plan["task_rows"]:
        task_values: dict[str, list[dict[str, Any]]] = {
            "estimation": [],
            "validation": [],
        }
        probabilities = [float(value) for value in task["probabilities"]]
        for state in task["states"]:
            key = (str(task["task_id"]), str(state["state_id"]))
            source = source_by_key[key]
            state_gradient = _to_device(
                _load_verified_gradient(
                    Path(source["state_gradient_file"]),
                    str(source["state_gradient_sha256"]),
                ),
                device,
            )
            state_norm = _gradient_norm(state_gradient)
            update = _adamw_descent_direction(
                state_gradient,
                learning_rate=float(plan["optimizer_contract"]["learning_rate"]),
                epsilon=float(plan["optimizer_contract"]["epsilon"]),
                maximum_gradient_norm=float(plan["optimizer_contract"]["maximum_gradient_norm"]),
            )
            for split in ("estimation", "validation"):
                dot, cosine = _normalized_gradient_alignment(
                    state_gradient,
                    objective_device[split],
                    left_norm=state_norm,
                    right_norm=objective_norms[split],
                )
                task_values[split].append(
                    {
                        "task_id": task["task_id"],
                        "task_type": task["task_type"],
                        "state_id": state["state_id"],
                        "strategy": state["strategy"],
                        "current_probability": state["current_probability"],
                        "gp_a_raw": cosine,
                        "gp_b_raw": dot,
                        "gp_c_raw": _gradient_dot(update, objective_device[split]),
                        "optimizer_target": targets[split][key],
                    }
                )
            del state_gradient, update
        for split in ("estimation", "validation"):
            for estimator_id, raw_field in (
                (DIAGNOSTIC_ESTIMATOR, "gp_a_raw"),
                (SECONDARY_ESTIMATOR, "gp_b_raw"),
                (PRIMARY_ESTIMATOR, "gp_c_raw"),
            ):
                centered = _center(
                    [float(row[raw_field]) for row in task_values[split]],
                    probabilities,
                )
                for row, value in zip(task_values[split], centered, strict=True):
                    row[estimator_id] = value
            rows_by_split[split].extend(task_values[split])
    target_values = [float(row["optimizer_target"]) for row in rows_by_split["estimation"]]
    temperature = statistics.median(abs(value) for value in target_values)
    estimator_rows: dict[str, dict[str, Any]] = {}
    for index, estimator_id in enumerate(ESTIMATOR_IDS):
        scale = _robust_positive_scale(
            [float(row[estimator_id]) for row in rows_by_split["estimation"]],
            target_values,
        )
        split_evidence: dict[str, dict[str, Any]] = {}
        for offset, split in enumerate(("estimation", "validation")):
            grouped = _split_rows_by_task(rows_by_split[split])
            split_evidence[split] = {
                "rank": _rank_evidence(
                    grouped,
                    estimator_field=estimator_id,
                    target_field="optimizer_target",
                    seed=AUTHORIZATION_NUMERIC_SEED + 3000 + 100 * index + offset,
                ),
                "distribution": _distribution_evidence(
                    grouped,
                    proxy_field=estimator_id,
                    target_field="optimizer_target",
                    proxy_scale=scale,
                    temperature=temperature,
                ),
            }
        estimator_rows[estimator_id] = {
            "robust_scale": scale,
            "contribution_temperature": temperature,
            "split_evidence": split_evidence,
        }
    report: dict[str, Any] = {
        "experiment_version": AUTHORIZATION_VERSION,
        "diagnostic_version": "post_global_update_objective_gradient.v1",
        "role": "internal_linearization_point_diagnostic_only",
        "plan_hash": plan["plan_hash"],
        "authorization_objective_accessed": False,
        "objective_gradient_evaluation_point": "beneficiary_after_global_pi_update",
        "post_update_adapter_tensor_sha256": post_update_adapter_hash,
        "objective_rows": objective_rows,
        "estimator_rows": estimator_rows,
        "gpu_ids": list(gpu_ids),
        "model_placement": "single_gpu" if len(gpu_ids) == 1 else "balanced_sharded",
        "peak_gpu_memory_bytes": {
            str(gpu_ids[index]): int(torch.cuda.max_memory_allocated(index))
            for index in range(len(gpu_ids))
        },
        "claim_boundary": (
            "This internal diagnostic may motivate a new preregistered estimator contract, "
            "but it cannot alter or rescue the failed v1 authorization plan."
        ),
    }
    report["diagnostic_hash"] = canonical_hash(
        report, prefix="finance_post_update_objective_diagnostic:"
    )
    _write_json(output_dir / "post_update_objective_diagnostic.json", report)
    print(
        json.dumps(
            {
                "diagnostic_hash": report["diagnostic_hash"],
                "authorization_objective_accessed": False,
                "primary_estimation_spearman": estimator_rows[PRIMARY_ESTIMATOR]["split_evidence"][
                    "estimation"
                ]["rank"]["macro_task_spearman"],
                "primary_validation_spearman": estimator_rows[PRIMARY_ESTIMATOR]["split_evidence"][
                    "validation"
                ]["rank"]["macro_task_spearman"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    del model, global_update, objective_gradients, objective_device
    gc.collect()
    torch.cuda.empty_cache()


def _authorize(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    preflight = _read_json(output_dir / "preflight.json")
    calibration = _read_json(output_dir / "calibration.json")
    proxy = _read_json(output_dir / "authorization_proxy.json")
    target = _read_json(output_dir / "targets" / "authorization.json")
    for artifact, hash_field, prefix, name in (
        (
            plan,
            "plan_hash",
            "finance_contribution_authorization_plan:",
            "authorization plan",
        ),
        (
            preflight,
            "preflight_hash",
            "finance_contribution_authorization_preflight:",
            "authorization preflight",
        ),
        (
            calibration,
            "calibration_hash",
            "finance_contribution_authorization_calibration:",
            "authorization calibration",
        ),
        (
            proxy,
            "proxy_hash",
            "finance_contribution_authorization_proxy:",
            "authorization proxy",
        ),
        (
            target,
            "target_hash",
            "finance_authorization_authorization_target:",
            "authorization target",
        ),
    ):
        _assert_canonical_artifact(
            artifact,
            hash_field=hash_field,
            prefix=prefix,
            artifact_name=name,
        )
    if (
        preflight.get("plan_hash") != plan.get("plan_hash")
        or preflight.get("status") != "passed"
        or calibration.get("plan_hash") != plan.get("plan_hash")
        or calibration.get("status") != "passed"
        or proxy.get("calibration_hash") != calibration.get("calibration_hash")
        or proxy.get("status") != "passed"
        or target.get("plan_hash") != plan.get("plan_hash")
        or target.get("status") != "passed"
    ):
        raise ValueError("authorization evidence failed immutable replay")
    proxy_by_key = {(str(row["task_id"]), str(row["state_id"])): row for row in proxy["state_rows"]}
    target_by_key = {
        (str(row["task_id"]), str(row["state_id"])): row for row in target["state_rows"]
    }
    if proxy_by_key.keys() != target_by_key.keys() or len(proxy_by_key) != 90:
        raise ValueError("authorization proxy and target supports differ")
    rows = [
        {**proxy_by_key[key], "optimizer_target": target_by_key[key]["optimizer_target"]}
        for key in sorted(proxy_by_key)
    ]
    grouped = _split_rows_by_task(rows)
    estimator_evidence: dict[str, dict[str, Any]] = {}
    for index, estimator_id in enumerate(ESTIMATOR_IDS):
        field = f"authorization_{estimator_id}"
        calibrated = calibration["estimator_rows"][estimator_id]
        rank = _rank_evidence(
            grouped,
            estimator_field=field,
            target_field="optimizer_target",
            seed=AUTHORIZATION_NUMERIC_SEED + 1000 + 100 * index,
        )
        distribution = _distribution_evidence(
            grouped,
            proxy_field=field,
            target_field="optimizer_target",
            proxy_scale=float(calibrated["robust_scale"]),
            temperature=float(calibrated["contribution_temperature"]),
        )
        estimator_evidence[estimator_id] = {
            "rank": rank,
            "distribution": distribution,
            "authorization_gate_passed": bool(
                rank["passes_rank_gate"] and distribution["passes_distribution_gate"]
            ),
        }
    primary_passed = bool(estimator_evidence[PRIMARY_ESTIMATOR]["authorization_gate_passed"])
    production_authorized = bool(
        primary_passed
        and preflight["status"] == "passed"
        and target["reconstruction_relative_error"] <= plan["maximum_reconstruction_relative_error"]
        and target["maximum_numeric_replay_range"] == 0.0
    )
    blockers = []
    if not primary_passed:
        blockers.append("preregistered_primary_authorization_gate_failed")
    if target["reconstruction_relative_error"] > plan["maximum_reconstruction_relative_error"]:
        blockers.append("authorization_target_reconstruction_failed")
    report: dict[str, Any] = {
        "experiment_version": AUTHORIZATION_VERSION,
        "artifact_type": "ContributionApproximationAuthorization",
        "plan_hash": plan["plan_hash"],
        "preflight_hash": preflight["preflight_hash"],
        "calibration_hash": calibration["calibration_hash"],
        "proxy_hash": proxy["proxy_hash"],
        "authorization_target_hash": target["target_hash"],
        "status": "authorized" if production_authorized else "denied",
        "production_authorized": production_authorized,
        "authorized_estimator_id": PRIMARY_ESTIMATOR if production_authorized else None,
        "secondary_estimator_role": "reported_not_substituted_post_hoc",
        "optimizer_contract": plan["optimizer_contract"],
        "batch_semantics": plan["batch_semantics"],
        "beneficiary_model_state_id": plan["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": plan["beneficiary_checkpoint_hash"],
        "objective_partition_ids": {
            split: values["set_id"] for split, values in plan["objective_partitions"].items()
        },
        "strict_freshness_contract": plan["strict_freshness_contract"],
        "estimator_preregistration": plan["estimator_preregistration"],
        "calibration_contract": plan["calibration_contract"],
        "rank_gate_contract": plan["rank_gate_contract"],
        "distribution_gate_contract": plan["distribution_gate_contract"],
        "energy_contract": plan["energy_contract"],
        "task_count": plan["task_count"],
        "state_count": plan["state_count"],
        "estimator_evidence": estimator_evidence,
        "blockers": blockers,
        "claim_boundary": (
            "Authorization, when issued, is limited to GP-C driving a VTDO contribution "
            "update under the frozen one-step cold-start AdamW, state-homogeneous sampling, "
            "beneficiary checkpoint, calibration, and energy contracts. It is not evidence "
            "for optimizer continuation, mixed-state batches, multi-step Student gains, or "
            "optimizer-independent Contribution estimation."
        ),
    }
    report["authorization_id"] = canonical_hash(
        report, prefix="contribution_approximation_authorization:"
    )
    _write_json(output_dir / "authorization.json", report)
    if production_authorized:
        credential = {
            "authorization_id": report["authorization_id"],
            "plan_hash": plan["plan_hash"],
            "estimator_id": PRIMARY_ESTIMATOR,
            "beneficiary_checkpoint_hash": plan["beneficiary_checkpoint_hash"],
            "optimizer_contract": plan["optimizer_contract"],
            "batch_semantics": plan["batch_semantics"],
            "calibration_hash": calibration["calibration_hash"],
            "energy_contract": plan["energy_contract"],
        }
        credential["credential_hash"] = canonical_hash(
            credential, prefix="contribution_approximation_credential:"
        )
        _write_json(output_dir / "authorization_credential.json", credential)
    print(
        json.dumps(
            {
                "status": report["status"],
                "production_authorized": production_authorized,
                "authorization_id": report["authorization_id"],
                "primary_rank_gate": estimator_evidence[PRIMARY_ESTIMATOR]["rank"][
                    "passes_rank_gate"
                ],
                "primary_distribution_gate": estimator_evidence[PRIMARY_ESTIMATOR]["distribution"][
                    "passes_distribution_gate"
                ],
                "blockers": blockers,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Authorize Gradient Projection on a fresh Finance objective"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--gradient-dir", required=True)
    prepare.add_argument("--optimizer-protocol", required=True)
    prepare.add_argument("--output-dir", required=True)
    prepare.add_argument("--gpu-id", type=int, default=0)
    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--output-dir", required=True)
    preflight.add_argument("--gpu-id", type=int, default=0)
    worker = subparsers.add_parser("worker")
    worker.add_argument("--output-dir", required=True)
    worker.add_argument(
        "--split", choices=("estimation", "validation", "authorization"), required=True
    )
    worker.add_argument("--gpu-id", type=int, required=True)
    worker.add_argument("--partition-index", type=int, required=True)
    worker.add_argument("--partition-count", type=int, required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--output-dir", required=True)
    run.add_argument(
        "--split", choices=("estimation", "validation", "authorization"), required=True
    )
    run.add_argument("--gpu-ids", type=int, nargs="+", required=True)
    aggregate = subparsers.add_parser("aggregate-target")
    aggregate.add_argument("--output-dir", required=True)
    aggregate.add_argument(
        "--split", choices=("estimation", "validation", "authorization"), required=True
    )
    calibrate = subparsers.add_parser("calibrate")
    calibrate.add_argument("--output-dir", required=True)
    objective = subparsers.add_parser("build-authorization-gradient")
    objective.add_argument("--output-dir", required=True)
    objective.add_argument("--gpu-id", type=int, default=0)
    diagnostic = subparsers.add_parser("diagnose-post-update-objective")
    diagnostic.add_argument("--output-dir", required=True)
    diagnostic.add_argument("--gpu-ids", type=int, nargs="+", required=True)
    authorize = subparsers.add_parser("authorize")
    authorize.add_argument("--output-dir", required=True)
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
        _run(args)
    elif args.command == "aggregate-target":
        _aggregate_target(args)
    elif args.command == "calibrate":
        _calibrate(args)
    elif args.command == "build-authorization-gradient":
        _build_authorization_gradient(args)
    elif args.command == "diagnose-post-update-objective":
        _diagnose_post_update_objective(args)
    else:
        _authorize(args)


if __name__ == "__main__":
    main()
