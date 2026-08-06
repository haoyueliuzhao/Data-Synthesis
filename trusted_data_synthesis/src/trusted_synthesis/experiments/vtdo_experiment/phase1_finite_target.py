from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import statistics
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    OBJECTIVE_GRADIENT_EXECUTION_MODE,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    _adapter_tensor_sha256,
    _load_records,
    _load_tokenizer,
    _read_json,
    _seed_everything,
    _write_json,
)
from trusted_synthesis.hashing import canonical_hash

FINITE_TARGET_VERSION = "finance_gradient_finite_target.v4"
DEFAULT_BASE_RADIUS = 0.1
DEFAULT_BLOCK_SIZE = 8
DEFAULT_DESIGN_COUNT = 3
MAXIMUM_RECONSTRUCTION_RELATIVE_ERROR = 0.10
MAXIMUM_P95_RADIUS_INSTABILITY = 0.25
MINIMUM_SIGNAL_TO_NULL_RATIO = 3.0
NUMERIC_FLOOR = 1e-12
DIRECTION_MANIFEST_HASH_PREFIX = "finance_gp_c_finite_target_directions:"


def _observation_hash(observation: Mapping[str, Any]) -> str:
    values = dict(observation)
    values.pop("observation_hash", None)
    return canonical_hash(values, prefix="finance_finite_target_observation:")


def _percentile(values: Sequence[float], probability: float) -> float:
    if not values or not 0 <= probability <= 1:
        raise ValueError("finite-target percentile input is invalid")
    ordered = sorted(float(value) for value in values)
    position = probability * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _validate_probabilities(probabilities: Mapping[str, float]) -> dict[str, float]:
    frozen = {str(key): float(value) for key, value in sorted(probabilities.items())}
    if not 3 <= len(frozen) <= 5:
        raise ValueError("finite target requires complete 3-5-state support")
    if any(not math.isfinite(value) or value <= 0 for value in frozen.values()):
        raise ValueError("finite target probabilities must be positive and finite")
    if not math.isclose(sum(frozen.values()), 1.0, abs_tol=1e-12):
        raise ValueError("finite target probabilities must sum to one")
    return frozen


def _next_power_of_two(value: int) -> int:
    if value < 1:
        raise ValueError("Hadamard support must be positive")
    return 1 << (value - 1).bit_length()


def _sylvester_hadamard(order: int) -> tuple[tuple[int, ...], ...]:
    if order < 1 or order & (order - 1):
        raise ValueError("Sylvester Hadamard order must be a power of two")
    matrix: tuple[tuple[int, ...], ...] = ((1,),)
    while len(matrix) < order:
        matrix = tuple(tuple((*row, *row)) for row in matrix) + tuple(
            tuple((*row, *(-value for value in row))) for row in matrix
        )
    return matrix


def _salted_rank(value: str, *, salt: str) -> str:
    return hashlib.sha256(f"{salt}\x1f{value}".encode()).hexdigest()


def _coordinate_rows(
    task_distributions: Mapping[str, Mapping[str, float]],
    task_marginals: Mapping[str, float],
) -> list[dict[str, Any]]:
    if set(task_distributions) != set(task_marginals):
        raise ValueError("finite target task marginals do not cover its distributions")
    marginals = {str(key): float(value) for key, value in task_marginals.items()}
    invalid_marginal = any(value <= 0 or not math.isfinite(value) for value in marginals.values())
    if invalid_marginal or not math.isclose(
        sum(marginals.values()),
        1.0,
        abs_tol=1e-12,
    ):
        raise ValueError("finite target task marginals are invalid")
    rows: list[dict[str, Any]] = []
    for task_id, raw_probabilities in sorted(task_distributions.items()):
        probabilities = _validate_probabilities(raw_probabilities)
        states = tuple(probabilities)
        reference_state_id = states[-1]
        for state_id in states[:-1]:
            payload = {
                "task_id": task_id,
                "state_id": state_id,
                "reference_state_id": reference_state_id,
                "task_marginal": marginals[task_id],
                "current_probabilities": probabilities,
                "tangent_weights": {
                    state_id: 0.5,
                    reference_state_id: -0.5,
                },
            }
            payload["coordinate_id"] = canonical_hash(
                payload,
                prefix="finance_finite_target_coordinate:",
            )
            rows.append(payload)
    return rows


def _block_design_rows(
    coordinates: Sequence[Mapping[str, Any]],
    *,
    block_size: int,
    design_count: int,
    salt: str,
) -> list[dict[str, Any]]:
    if not coordinates:
        raise ValueError("finite-target design requires coordinates")
    if not 5 <= block_size <= 10:
        raise ValueError("finite-target block size must lie in [5, 10]")
    if design_count < 2:
        raise ValueError("finite target requires multiple independent designs")
    coordinate_ids = tuple(str(row["coordinate_id"]) for row in coordinates)
    if len(set(coordinate_ids)) != len(coordinate_ids):
        raise ValueError("finite-target coordinates are not unique")
    rows: list[dict[str, Any]] = []
    for design_index in range(design_count):
        design_salt = f"{salt}:design:{design_index}"
        ordered = sorted(
            coordinate_ids,
            key=lambda value: _salted_rank(value, salt=design_salt),
        )
        flips = {
            coordinate_id: (
                1
                if int(_salted_rank(coordinate_id, salt=f"{design_salt}:flip")[-1], 16) % 2
                else -1
            )
            for coordinate_id in ordered
        }
        for block_index, start in enumerate(range(0, len(ordered), block_size)):
            block = tuple(ordered[start : start + block_size])
            order = _next_power_of_two(len(block))
            matrix = _sylvester_hadamard(order)
            block_id = canonical_hash(
                {
                    "design_index": design_index,
                    "block_index": block_index,
                    "coordinate_ids": block,
                    "salt_hash": canonical_hash(salt, prefix="finite_target_salt:"),
                },
                prefix="finance_finite_target_block:",
            )
            for row_index, signs in enumerate(matrix):
                weights = {
                    coordinate_id: signs[column] * flips[coordinate_id]
                    for column, coordinate_id in enumerate(block)
                }
                payload = {
                    "role": "orthogonal_design",
                    "design_index": design_index,
                    "block_index": block_index,
                    "block_id": block_id,
                    "row_index": row_index,
                    "hadamard_order": order,
                    "coordinate_ids": block,
                    "coordinate_weights": weights,
                }
                payload["design_row_id"] = canonical_hash(
                    payload,
                    prefix="finance_finite_target_design_row:",
                )
                rows.append(payload)
        null_payload = {
            "role": "null_replay",
            "design_index": design_index,
            "block_index": -1,
            "block_id": f"null:{design_index}",
            "row_index": 0,
            "hadamard_order": 1,
            "coordinate_ids": (),
            "coordinate_weights": {},
        }
        null_payload["design_row_id"] = canonical_hash(
            null_payload,
            prefix="finance_finite_target_design_row:",
        )
        rows.append(null_payload)
    return rows


def build_finite_target_plan(
    *,
    gradient_plan: Mapping[str, Any],
    gradient_report: Mapping[str, Any],
    objective_role: Literal["estimation", "validation", "authorization"],
    objective_record_ids: Sequence[str],
    objective_records_hash: str,
    base_radius: float = DEFAULT_BASE_RADIUS,
    block_size: int = DEFAULT_BLOCK_SIZE,
    design_count: int = DEFAULT_DESIGN_COUNT,
    design_salt: str,
    authorization_prerequisite_report_hashes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if gradient_report.get("plan_hash") != gradient_plan.get("plan_hash"):
        raise ValueError("finite target requires a replayed Gradient Projection report")
    if gradient_report.get("state_count") != len(gradient_report.get("state_rows", ())):
        raise ValueError("finite target requires complete aggregated state rows")
    run_role = str(gradient_plan.get("run_role", ""))
    if run_role == "sealed_causal_pilot":
        minimum_tasks = 6
        minimum_records = 4
        if objective_role == "authorization":
            raise ValueError("sealed causal pilot cannot open the authorization objective")
        execution_contract = gradient_plan.get("numeric_contract", {})
        protocol = execution_contract.get("finite_target_protocol")
        expected = {
            "base_radius": base_radius,
            "radii": [base_radius, base_radius / 2.0, base_radius / 4.0],
            "block_size": block_size,
            "design_count": design_count,
            "finite_difference": "symmetric_central",
            "extrapolation": "two_level_richardson_O_h4",
        }
        if protocol != expected:
            raise ValueError("sealed causal pilot finite-target protocol differs")
    elif run_role == "production_candidate":
        minimum_tasks = 30
        minimum_records = 16
    else:
        raise ValueError("finite target requires a registered Gradient Projection run role")
    if gradient_report.get("task_count", 0) < minimum_tasks:
        raise ValueError(f"{run_role} finite target has insufficient tasks")
    if len(objective_record_ids) < minimum_records:
        raise ValueError(f"{run_role} finite target has insufficient objective records")
    if len(set(objective_record_ids)) != len(objective_record_ids):
        raise ValueError("finite target objective records must be unique")
    prerequisite_hashes = dict(authorization_prerequisite_report_hashes or {})
    if objective_role == "authorization":
        if set(prerequisite_hashes) != {"estimation", "validation"} or any(
            not value for value in prerequisite_hashes.values()
        ):
            raise ValueError("authorization target requires frozen estimation and validation gates")
    elif prerequisite_hashes:
        raise ValueError("development finite targets cannot carry authorization prerequisites")
    if not 0 < base_radius < 0.5:
        raise ValueError("finite-target base radius must lie in (0, 0.5)")
    optimizer_contract = gradient_plan["local_optimizer_contract"]
    if (
        optimizer_contract.get("objective_gradient_mode")
        != OBJECTIVE_GRADIENT_EXECUTION_MODE
    ):
        raise ValueError("finite-target objective execution mode changed")
    task_distributions = {
        str(task_id): _validate_probabilities(values["probabilities"])
        for task_id, values in gradient_plan["task_distributions"].items()
    }
    task_marginals = {
        str(task_id): float(value) for task_id, value in gradient_report["task_marginals"].items()
    }
    state_rows_by_task: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for state in gradient_report["state_rows"]:
        state_rows_by_task[str(state["task_id"])].append(state)
    if set(state_rows_by_task) != set(task_distributions):
        raise ValueError("finite target state rows do not cover frozen task distributions")
    for task_id, states in state_rows_by_task.items():
        if {str(row["state_id"]) for row in states} != set(task_distributions[task_id]):
            raise ValueError("finite target state artifact support differs from pi_t")
    coordinates = _coordinate_rows(task_distributions, task_marginals)
    design_rows = _block_design_rows(
        coordinates,
        block_size=block_size,
        design_count=design_count,
        salt=design_salt,
    )
    values: dict[str, Any] = {
        "experiment_version": FINITE_TARGET_VERSION,
        "artifact_type": "GradientProjectionFiniteTargetPlan",
        "run_role": run_role,
        "numeric_contract_hash": gradient_plan["numeric_contract_hash"],
        "numeric_profile": gradient_plan["numeric_contract"]["selected_profile"],
        "production_authorization_eligible": bool(
            run_role == "production_candidate"
            and gradient_plan.get("production_authorization_eligible", True)
        ),
        "source_gradient_plan_hash": gradient_plan["plan_hash"],
        "source_gradient_report_hash": gradient_report["report_hash"],
        "beneficiary_model_state_id": gradient_plan["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": gradient_plan["beneficiary_checkpoint_hash"],
        "model_dir": gradient_plan["model_dir"],
        "base_model_manifest_hash": gradient_plan["base_model_manifest_hash"],
        "beneficiary_adapter_dir": gradient_plan["beneficiary_adapter_dir"],
        "beneficiary_adapter_tensor_sha256": gradient_plan["beneficiary_adapter_tensor_sha256"],
        "source_records_path": gradient_plan["source_records_path"],
        "source_records_sha256": gradient_plan["source_records_sha256"],
        "optimizer_contract": optimizer_contract,
        "objective_role": objective_role,
        "objective_record_ids": tuple(objective_record_ids),
        "objective_records_hash": objective_records_hash,
        "objective_record_count": len(objective_record_ids),
        "objective_gradient_mode": OBJECTIVE_GRADIENT_EXECUTION_MODE,
        "objective_gradient_point": "post_global_update",
        "state_gradient_mode": "train",
        "task_distributions": task_distributions,
        "task_marginals": task_marginals,
        "state_artifacts": tuple(
            {
                "task_id": row["task_id"],
                "state_id": row["state_id"],
                "state_artifact_id": row["state_artifact_id"],
                "state_gradient_file": row["state_gradient_file"],
                "state_gradient_sha256": row["state_gradient_sha256"],
            }
            for row in gradient_report["state_rows"]
        ),
        "global_gradient_artifact": gradient_report["global_gradient_artifact"],
        "coordinate_rows": tuple(coordinates),
        "coordinate_count": len(coordinates),
        "design_rows": tuple(design_rows),
        "design_count": design_count,
        "block_size": block_size,
        "radii": (base_radius, base_radius / 2.0, base_radius / 4.0),
        "finite_difference": "symmetric_central",
        "extrapolation": "two_level_richardson_O_h4",
        "null_replay_per_design": 1,
        "maximum_reconstruction_relative_error": (MAXIMUM_RECONSTRUCTION_RELATIVE_ERROR),
        "maximum_p95_radius_instability": MAXIMUM_P95_RADIUS_INSTABILITY,
        "minimum_signal_to_null_ratio": MINIMUM_SIGNAL_TO_NULL_RATIO,
        "authorization_access_policy": (
            "authorization_requires_passed_estimation_and_validation_reports"
        ),
        "authorization_prerequisite_report_hashes": dict(sorted(prerequisite_hashes.items())),
        "claim_boundary": (
            "This protocol estimates a local, one-step cold-start AdamW distribution-update "
            "target around the post-global-update beneficiary. It does not approximate the "
            "full Student optimizer trajectory or multi-step downstream utility."
        ),
    }
    values["plan_hash"] = canonical_hash(values, prefix="finance_finite_target_plan:")
    return values


def _richardson_triplet(
    derivative_h: float,
    derivative_h2: float,
    derivative_h4: float,
) -> tuple[float, float, float]:
    first = (4.0 * derivative_h2 - derivative_h) / 3.0
    second = (4.0 * derivative_h4 - derivative_h2) / 3.0
    denominator = max(abs(first), abs(second), NUMERIC_FLOOR)
    return first, second, abs(second - first) / denominator


def _observation_derivatives(
    plan: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
) -> tuple[dict[tuple[str, float], float], dict[str, float], list[float]]:
    radii = tuple(float(value) for value in plan["radii"])
    expected_rows = {str(row["design_row_id"]): row for row in plan["design_rows"]}
    direction_manifest_hashes: set[str] = set()
    baseline_adapter_hashes: set[str] = set()
    baseline_objectives: set[float] = set()
    baseline_token_counts: set[int] = set()
    numeric_seeds: set[int] = set()
    grouped: defaultdict[tuple[str, float], dict[int, Mapping[str, Any]]] = defaultdict(dict)
    for observation in observations:
        if observation.get("observation_hash") != _observation_hash(observation):
            raise ValueError("finite-target observation identity changed")
        if observation.get("plan_hash") != plan["plan_hash"]:
            raise ValueError("finite-target observation belongs to another plan")
        if observation.get("objective_gradient_point") != "post_global_update":
            raise ValueError("finite target was not measured at the post-global point")
        if observation.get("objective_role") != plan["objective_role"]:
            raise ValueError("finite-target observation uses another objective partition")
        if observation.get("numeric_contract_hash") != plan["numeric_contract_hash"]:
            raise ValueError("finite-target observation uses another numeric contract")
        direction_manifest_hash = str(observation.get("direction_manifest_hash", ""))
        baseline_adapter_hash = str(observation.get("baseline_post_global_adapter_hash", ""))
        if not direction_manifest_hash or not baseline_adapter_hash:
            raise ValueError("finite-target observation lacks frozen execution identity")
        supervised_tokens = int(observation.get("supervised_tokens", 0))
        baseline_tokens = int(observation.get("baseline_supervised_tokens", 0))
        if supervised_tokens <= 0 or supervised_tokens != baseline_tokens:
            raise ValueError("finite-target observation changed objective token support")
        direction_manifest_hashes.add(direction_manifest_hash)
        baseline_adapter_hashes.add(baseline_adapter_hash)
        baseline_objectives.add(float(observation["baseline_objective_value"]))
        baseline_token_counts.add(baseline_tokens)
        numeric_seeds.add(int(observation["numeric_seed"]))
        row_id = str(observation["design_row_id"])
        radius = float(observation["radius"])
        sign = int(observation["sign"])
        if row_id not in expected_rows or radius not in radii or sign not in {-1, 1}:
            raise ValueError("finite-target observation lies outside the frozen design")
        key = (row_id, radius)
        if sign in grouped[key]:
            raise ValueError("finite-target observation duplicates one perturbation sign")
        grouped[key][sign] = observation
    required = {(row_id, radius) for row_id in expected_rows for radius in radii}
    if set(grouped) != required or any(set(pair) != {-1, 1} for pair in grouped.values()):
        raise ValueError("finite-target observation matrix is incomplete")
    if any(
        len(values) != 1
        for values in (
            direction_manifest_hashes,
            baseline_adapter_hashes,
            baseline_objectives,
            baseline_token_counts,
            numeric_seeds,
        )
    ):
        raise ValueError("finite-target observations do not share one frozen baseline")
    derivatives: dict[tuple[str, float], float] = {}
    extrapolated: dict[str, float] = {}
    instability: list[float] = []
    for row_id in expected_rows:
        by_radius = {}
        for radius in radii:
            pair = grouped[(row_id, radius)]
            plus = float(pair[1]["objective_value"])
            minus = float(pair[-1]["objective_value"])
            if not math.isfinite(plus) or not math.isfinite(minus):
                raise ValueError("finite-target objective is non-finite")
            derivative = (plus - minus) / (2.0 * radius)
            derivatives[(row_id, radius)] = derivative
            by_radius[radius] = derivative
        first, second, relative_change = _richardson_triplet(
            by_radius[radii[0]],
            by_radius[radii[1]],
            by_radius[radii[2]],
        )
        extrapolated[row_id] = second
        instability.append(relative_change)
        del first
    return derivatives, extrapolated, instability


def _recover_design_coordinates(
    plan: Mapping[str, Any],
    extrapolated: Mapping[str, float],
) -> dict[int, dict[str, float]]:
    by_design_block: defaultdict[tuple[int, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in plan["design_rows"]:
        if row["role"] == "orthogonal_design":
            by_design_block[(int(row["design_index"]), str(row["block_id"]))].append(row)
    recovered: defaultdict[int, dict[str, float]] = defaultdict(dict)
    for (design_index, _), rows in sorted(by_design_block.items()):
        rows.sort(key=lambda row: int(row["row_index"]))
        order = int(rows[0]["hadamard_order"])
        if len(rows) != order:
            raise ValueError("finite-target Hadamard block is incomplete")
        coordinate_ids = tuple(str(value) for value in rows[0]["coordinate_ids"])
        for coordinate_id in coordinate_ids:
            value = (
                sum(
                    float(row["coordinate_weights"][coordinate_id])
                    * float(extrapolated[str(row["design_row_id"])])
                    for row in rows
                )
                / order
            )
            if coordinate_id in recovered[design_index]:
                raise ValueError("finite-target coordinate appears twice in one design")
            recovered[design_index][coordinate_id] = value
    expected = {str(row["coordinate_id"]) for row in plan["coordinate_rows"]}
    if len(recovered) != int(plan["design_count"]) or any(
        set(values) != expected for values in recovered.values()
    ):
        raise ValueError("finite-target designs do not recover every coordinate")
    return dict(recovered)


def recover_pi_centered_state_values(
    *,
    probabilities: Mapping[str, float],
    task_marginal: float,
    reference_state_id: str,
    coordinate_values: Mapping[str, tuple[str, float]],
) -> dict[str, float]:
    frozen = _validate_probabilities(probabilities)
    if reference_state_id not in frozen or not 0 < task_marginal <= 1:
        raise ValueError("finite-target state recovery contract is invalid")
    nonreference = set(frozen) - {reference_state_id}
    if {state_id for state_id, _ in coordinate_values.values()} != nonreference:
        raise ValueError("finite-target state recovery lacks tangent coordinates")
    differences = {
        state_id: 2.0 * float(value) / task_marginal
        for state_id, value in coordinate_values.values()
    }
    reference = -sum(frozen[state_id] * value for state_id, value in differences.items())
    values = {reference_state_id: reference}
    values.update(
        {state_id: reference + difference for state_id, difference in differences.items()}
    )
    if not math.isclose(
        sum(frozen[state_id] * values[state_id] for state_id in frozen),
        0.0,
        abs_tol=1e-10,
    ):
        raise ValueError("finite-target recovered state values are not pi-centered")
    return dict(sorted(values.items()))


def analyze_finite_target(
    plan: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    unhashed = dict(plan)
    observed_plan_hash = unhashed.pop("plan_hash", None)
    if observed_plan_hash != canonical_hash(unhashed, prefix="finance_finite_target_plan:"):
        raise ValueError("finite-target plan identity changed")
    derivatives, extrapolated, radius_instability = _observation_derivatives(plan, observations)
    by_design = _recover_design_coordinates(plan, extrapolated)
    coordinate_ids = tuple(str(row["coordinate_id"]) for row in plan["coordinate_rows"])
    coordinate_values = {
        coordinate_id: statistics.fmean(values[coordinate_id] for values in by_design.values())
        for coordinate_id in coordinate_ids
    }
    design_variances = {
        coordinate_id: statistics.variance([values[coordinate_id] for values in by_design.values()])
        for coordinate_id in coordinate_ids
    }
    residuals = []
    observed_values = []
    null_values = []
    for row in plan["design_rows"]:
        row_id = str(row["design_row_id"])
        if row["role"] == "null_replay":
            null_values.append(float(extrapolated[row_id]))
            continue
        predicted = sum(
            float(weight) * coordinate_values[str(coordinate_id)]
            for coordinate_id, weight in row["coordinate_weights"].items()
        )
        observed = float(extrapolated[row_id])
        residuals.append(predicted - observed)
        observed_values.append(observed)
    residual_norm = math.sqrt(statistics.fmean(value * value for value in residuals))
    observed_norm = math.sqrt(statistics.fmean(value * value for value in observed_values))
    reconstruction_error = residual_norm / max(observed_norm, NUMERIC_FLOOR)
    signal_rms = math.sqrt(statistics.fmean(value * value for value in coordinate_values.values()))
    null_rms = math.sqrt(statistics.fmean(value * value for value in null_values))
    signal_to_null = signal_rms / max(null_rms, NUMERIC_FLOOR)
    coordinate_metadata = {str(row["coordinate_id"]): row for row in plan["coordinate_rows"]}
    task_coordinates: defaultdict[str, dict[str, tuple[str, float]]] = defaultdict(dict)
    for coordinate_id, value in coordinate_values.items():
        metadata = coordinate_metadata[coordinate_id]
        task_coordinates[str(metadata["task_id"])][coordinate_id] = (
            str(metadata["state_id"]),
            value,
        )
    state_targets = []
    for task_id, values in sorted(task_coordinates.items()):
        metadata = coordinate_metadata[next(iter(values))]
        recovered = recover_pi_centered_state_values(
            probabilities=metadata["current_probabilities"],
            task_marginal=float(metadata["task_marginal"]),
            reference_state_id=str(metadata["reference_state_id"]),
            coordinate_values=values,
        )
        state_targets.append(
            {
                "task_id": task_id,
                "current_probabilities": metadata["current_probabilities"],
                "target_state_values": recovered,
                "weighted_target_mean": sum(
                    float(metadata["current_probabilities"][state_id]) * value
                    for state_id, value in recovered.items()
                ),
            }
        )
    p95_instability = _percentile(radius_instability, 0.95)
    passed = bool(
        reconstruction_error <= float(plan["maximum_reconstruction_relative_error"])
        and p95_instability <= float(plan["maximum_p95_radius_instability"])
        and signal_to_null >= float(plan["minimum_signal_to_null_ratio"])
    )
    direction_manifest_hashes = {
        str(observation["direction_manifest_hash"]) for observation in observations
    }
    baseline_adapter_hashes = {
        str(observation["baseline_post_global_adapter_hash"]) for observation in observations
    }
    authorization_role = plan["objective_role"] == "authorization"
    report: dict[str, Any] = {
        "experiment_version": FINITE_TARGET_VERSION,
        "artifact_type": "GradientProjectionFiniteTargetReport",
        "run_role": plan["run_role"],
        "numeric_contract_hash": plan["numeric_contract_hash"],
        "numeric_profile": plan["numeric_profile"],
        "production_authorization_eligible": bool(
            passed and plan["production_authorization_eligible"]
        ),
        "plan_hash": plan["plan_hash"],
        "source_gradient_plan_hash": plan["source_gradient_plan_hash"],
        "source_gradient_report_hash": plan["source_gradient_report_hash"],
        "beneficiary_model_state_id": plan["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": plan["beneficiary_checkpoint_hash"],
        "objective_role": plan["objective_role"],
        "objective_record_ids": plan["objective_record_ids"],
        "objective_records_hash": plan["objective_records_hash"],
        "objective_record_count": plan["objective_record_count"],
        "objective_gradient_point": "post_global_update",
        "direction_manifest_hash": next(iter(direction_manifest_hashes)),
        "baseline_post_global_adapter_hash": next(iter(baseline_adapter_hashes)),
        "observation_manifest_hash": canonical_hash(
            tuple(sorted(str(row["observation_hash"]) for row in observations)),
            prefix="finance_finite_target_observation_manifest:",
        ),
        "observation_count": len(observations),
        "coordinate_count": len(coordinate_values),
        "design_count": len(by_design),
        "radii": plan["radii"],
        "reconstruction_relative_error": reconstruction_error,
        "maximum_reconstruction_relative_error": plan["maximum_reconstruction_relative_error"],
        "mean_radius_instability": statistics.fmean(radius_instability),
        "p95_radius_instability": p95_instability,
        "maximum_p95_radius_instability": plan["maximum_p95_radius_instability"],
        "signal_rms": signal_rms,
        "null_replay_rms": null_rms,
        "signal_to_null_ratio": signal_to_null,
        "minimum_signal_to_null_ratio": plan["minimum_signal_to_null_ratio"],
        "mean_cross_design_coordinate_variance": statistics.fmean(design_variances.values()),
        "coordinate_values": coordinate_values,
        "coordinate_cross_design_variances": design_variances,
        "state_targets": state_targets,
        "status": "passed" if passed else "failed",
        "authorization_prerequisite_report_hashes": plan[
            "authorization_prerequisite_report_hashes"
        ],
        "development_gate_eligible": bool(
            passed and plan["objective_role"] in {"estimation", "validation"}
        ),
        "authorization_access_granted": bool(
            passed
            and authorization_role
            and set(plan["authorization_prerequisite_report_hashes"])
            == {"estimation", "validation"}
        ),
        "claim_boundary": plan["claim_boundary"],
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_finite_target_report:",
    )
    del derivatives
    return report


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    values = []
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            if line.strip():
                values.append(json.loads(line))
    return values


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as sink:
        sink.write(json.dumps(dict(value), ensure_ascii=False, sort_keys=True) + "\n")
        sink.flush()
        os.fsync(sink.fileno())


def _verify_direction_manifest(
    plan: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> str:
    payload = dict(manifest)
    observed = payload.pop("manifest_hash", None)
    expected = canonical_hash(payload, prefix=DIRECTION_MANIFEST_HASH_PREFIX)
    if observed != expected:
        raise ValueError("finite-target direction manifest identity changed")
    if manifest.get("finite_target_plan_hash") != plan.get("plan_hash"):
        raise ValueError("finite-target direction manifest belongs to another plan")
    artifacts = manifest.get("direction_artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("finite-target direction manifest has no artifacts")
    expected_ids = {str(row["design_row_id"]) for row in plan["design_rows"]}
    observed_ids = [str(row.get("design_row_id", "")) for row in artifacts]
    if set(observed_ids) != expected_ids or len(observed_ids) != len(expected_ids):
        raise ValueError("finite-target direction support is incomplete")
    if any(not row.get("file") or not row.get("sha256") for row in artifacts):
        raise ValueError("finite-target direction artifact identity is incomplete")
    return str(observed)


def _execute(args: argparse.Namespace) -> None:
    import torch
    from peft import get_peft_model_state_dict

    from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
        _evaluate_records_numeric,
        _load_execution_model,
        _load_verified_gradient,
        _sha256,
    )
    from trusted_synthesis.experiments.vtdo_experiment.phase1_gp_c_proxy import (
        _apply_descent_vector,
        _linear_combination,
        _restore_adapter,
    )

    gpu_ids = tuple(int(value) for value in args.gpu_ids)
    if len(gpu_ids) != 3 or len(set(gpu_ids)) != 3:
        raise ValueError("finite target requires one frozen three-GPU group")
    if any(value < 0 or value >= torch.cuda.device_count() for value in gpu_ids):
        raise ValueError("finite-target GPU group is unavailable")
    torch.cuda.set_device(gpu_ids[0])
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    direction_manifest = _read_json(Path(args.direction_manifest).resolve())
    _verify_direction_manifest(plan, direction_manifest)
    if not 0 <= args.partition_index < args.partition_count:
        raise ValueError("finite-target partition index is invalid")
    records_path = Path(str(plan["source_records_path"]))
    if _sha256(records_path) != plan["source_records_sha256"]:
        raise ValueError("finite-target objective records changed")
    records = _load_records(records_path)
    objective_records = tuple(records[record_id] for record_id in plan["objective_record_ids"])
    direction_by_id = {
        str(row["design_row_id"]): row for row in direction_manifest["direction_artifacts"]
    }
    expected_direction_ids = {str(row["design_row_id"]) for row in plan["design_rows"]}
    if set(direction_by_id) != expected_direction_ids:
        raise ValueError("finite-target direction support is incomplete")
    jobs = [
        {
            "design_row_id": str(row["design_row_id"]),
            "radius": float(radius),
            "sign": sign,
        }
        for row in plan["design_rows"]
        for radius in plan["radii"]
        for sign in (-1, 1)
    ]
    assigned = [
        job
        for index, job in enumerate(jobs)
        if index % args.partition_count == args.partition_index
    ]
    worker_path = output_dir / "workers" / f"partition_{args.partition_index}.jsonl"
    completed = (
        {
            (str(row["design_row_id"]), float(row["radius"]), int(row["sign"]))
            for row in _load_jsonl(worker_path)
            if row.get("observation_hash") == _observation_hash(row)
        }
        if worker_path.is_file()
        else set()
    )
    _seed_everything(args.numeric_seed)
    for gpu_id in gpu_ids:
        torch.cuda.reset_peak_memory_stats(gpu_id)
    tokenizer = _load_tokenizer(Path(str(plan["model_dir"])))
    model, resolved_device_map = _load_execution_model(
        Path(str(plan["model_dir"])),
        Path(str(plan["beneficiary_adapter_dir"])),
        gpu_ids=gpu_ids,
        profile=plan["numeric_profile"],
    )
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("finite target loaded another beneficiary Adapter")
    baseline_state = {
        name: value.detach().cpu().clone()
        for name, value in get_peft_model_state_dict(model).items()
    }
    global_artifact = direction_manifest["global_update_artifact"]
    global_update = _load_verified_gradient(
        Path(str(global_artifact["file"])),
        str(global_artifact["sha256"]),
    )
    _restore_adapter(model, baseline_state)
    _apply_descent_vector(model, global_update)
    baseline_objective, baseline_loss, baseline_tokens = _evaluate_records_numeric(
        model,
        tokenizer,
        objective_records,
    )
    post_global_adapter_hash = _adapter_tensor_sha256(model)
    started = time.monotonic()
    completed_now = 0
    for job in assigned:
        design_row_id = str(job["design_row_id"])
        radius = float(job["radius"])
        sign = int(job["sign"])
        key = (design_row_id, radius, sign)
        if key in completed:
            continue
        artifact = direction_by_id[design_row_id]
        direction = _load_verified_gradient(
            Path(str(artifact["file"])),
            str(artifact["sha256"]),
        )
        update = _linear_combination(
            [global_update, direction],
            [1.0, sign * radius],
        )
        _seed_everything(args.numeric_seed)
        _restore_adapter(model, baseline_state)
        _apply_descent_vector(model, update)
        objective_value, loss, supervised_tokens = _evaluate_records_numeric(
            model,
            tokenizer,
            objective_records,
        )
        if supervised_tokens != baseline_tokens:
            raise ValueError("finite target changed objective token support")
        observation: dict[str, Any] = {
            "experiment_version": FINITE_TARGET_VERSION,
            "plan_hash": plan["plan_hash"],
            "direction_manifest_hash": direction_manifest["manifest_hash"],
            "objective_role": plan["objective_role"],
            "numeric_contract_hash": plan["numeric_contract_hash"],
            "objective_gradient_point": "post_global_update",
            "design_row_id": design_row_id,
            "radius": radius,
            "sign": sign,
            "objective_value": objective_value,
            "loss": loss,
            "supervised_tokens": supervised_tokens,
            "baseline_objective_value": baseline_objective,
            "baseline_loss": baseline_loss,
            "baseline_supervised_tokens": baseline_tokens,
            "baseline_post_global_adapter_hash": post_global_adapter_hash,
            "perturbed_adapter_hash": _adapter_tensor_sha256(model),
            "numeric_seed": args.numeric_seed,
            "partition_index": args.partition_index,
            "partition_count": args.partition_count,
        }
        observation["observation_hash"] = _observation_hash(observation)
        _append_jsonl(worker_path, observation)
        completed_now += 1
        del direction, update
    worker_report = {
        "plan_hash": plan["plan_hash"],
        "partition_index": args.partition_index,
        "partition_count": args.partition_count,
        "assigned_count": len(assigned),
        "completed_before_resume": len(completed),
        "completed_now": completed_now,
        "runtime_seconds": time.monotonic() - started,
        "requested_cuda_device_ids": gpu_ids,
        "resolved_hf_device_map": resolved_device_map,
        "resolved_hf_device_map_hash": canonical_hash(
            resolved_device_map,
            prefix="finance_finite_target_hf_device_map:",
        ),
        "peak_gpu_memory_bytes": max(
            int(torch.cuda.max_memory_allocated(gpu_id)) for gpu_id in gpu_ids
        ),
        "peak_gpu_memory_bytes_by_requested_device": {
            str(gpu_id): int(torch.cuda.max_memory_allocated(gpu_id)) for gpu_id in gpu_ids
        },
    }
    worker_report_path = output_dir / "workers" / f"partition_{args.partition_index}_report.json"
    _write_json(worker_report_path, worker_report)
    print(json.dumps(worker_report, ensure_ascii=False, indent=2, sort_keys=True))
    del model, global_update, baseline_state
    gc.collect()
    torch.cuda.empty_cache()


def _aggregate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    direction_manifest = _read_json(Path(args.direction_manifest).resolve())
    direction_manifest_hash = _verify_direction_manifest(plan, direction_manifest)
    observations = [
        row
        for path in sorted((output_dir / "workers").glob("partition_*.jsonl"))
        for row in _load_jsonl(path)
    ]
    report = analyze_finite_target(plan, observations)
    if report.get("direction_manifest_hash") != direction_manifest_hash:
        raise ValueError("finite-target observations use another direction manifest")
    _write_json(output_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _prepare(args: argparse.Namespace) -> None:
    gradient_dir = Path(args.gradient_dir).resolve()
    gradient_plan = _read_json(gradient_dir / "plan.json")
    gradient_report = _read_json(gradient_dir / "report.json")
    role_to_ids = {
        "estimation": gradient_plan["gradient_estimation_record_ids"],
        "validation": gradient_plan["gradient_validation_record_ids"],
        "authorization": gradient_plan["final_test_record_ids"],
    }
    prerequisite_hashes: dict[str, str] = {}
    if args.objective_role == "authorization":
        for role, required_path in (
            ("estimation", args.estimation_report),
            ("validation", args.validation_report),
        ):
            if not required_path:
                raise ValueError(
                    "authorization target requires passed estimation and validation reports"
                )
            report = _read_json(Path(required_path).resolve())
            unhashed = dict(report)
            report_hash = unhashed.pop("report_hash", None)
            if report_hash != canonical_hash(
                unhashed,
                prefix="finance_finite_target_report:",
            ):
                raise ValueError("authorization prerequisite report identity changed")
            if (
                report.get("status") != "passed"
                or report.get("objective_role") != role
                or report.get("source_gradient_plan_hash") != gradient_plan["plan_hash"]
                or report.get("source_gradient_report_hash") != gradient_report["report_hash"]
                or not report.get("development_gate_eligible")
            ):
                raise ValueError("authorization target remains sealed after a failed dev gate")
            prerequisite_hashes[role] = str(report_hash)
    objective_ids = tuple(str(value) for value in role_to_ids[args.objective_role])
    plan = build_finite_target_plan(
        gradient_plan=gradient_plan,
        gradient_report=gradient_report,
        objective_role=args.objective_role,
        objective_record_ids=objective_ids,
        objective_records_hash=canonical_hash(
            {
                "record_ids": objective_ids,
                "records_file_sha256": gradient_plan["source_records_sha256"],
            },
            prefix=f"finance_finite_target_{args.objective_role}_records:",
        ),
        base_radius=args.base_radius,
        block_size=args.block_size,
        design_count=args.design_count,
        design_salt=args.design_salt,
        authorization_prerequisite_report_hashes=prerequisite_hashes,
    )
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "plan.json", plan)
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))


def _analyze(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    observations = _load_jsonl(Path(args.observations_path).resolve())
    report = analyze_finite_target(plan, observations)
    _write_json(output_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and analyze the multi-radius post-update GP-C finite target"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--gradient-dir", required=True)
    prepare.add_argument("--output-dir", required=True)
    prepare.add_argument(
        "--objective-role",
        choices=("estimation", "validation", "authorization"),
        required=True,
    )
    prepare.add_argument("--design-salt", required=True)
    prepare.add_argument("--base-radius", type=float, default=DEFAULT_BASE_RADIUS)
    prepare.add_argument("--block-size", type=int, default=DEFAULT_BLOCK_SIZE)
    prepare.add_argument("--design-count", type=int, default=DEFAULT_DESIGN_COUNT)
    prepare.add_argument("--estimation-report")
    prepare.add_argument("--validation-report")
    prepare.set_defaults(handler=_prepare)
    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("--output-dir", required=True)
    analyze.add_argument("--observations-path", required=True)
    analyze.set_defaults(handler=_analyze)
    execute = subparsers.add_parser("execute")
    execute.add_argument("--output-dir", required=True)
    execute.add_argument("--direction-manifest", required=True)
    execute.add_argument("--gpu-ids", type=int, nargs="+", required=True)
    execute.add_argument("--partition-index", type=int, default=0)
    execute.add_argument("--partition-count", type=int, default=1)
    execute.add_argument("--numeric-seed", type=int, default=20261131)
    execute.set_defaults(handler=_execute)
    aggregate = subparsers.add_parser("aggregate")
    aggregate.add_argument("--output-dir", required=True)
    aggregate.add_argument("--direction-manifest", required=True)
    aggregate.set_defaults(handler=_aggregate)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
