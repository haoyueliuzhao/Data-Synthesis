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

from trusted_synthesis.experiments.vtdo_experiment.phase1_target_identifiability_contract import (
    BLOCK_SIZES,
    OBJECTIVE_MICRO_SPLIT_COUNT,
    OBJECTIVE_RECORDS_PER_MICRO_SPLIT,
    OBJECTIVE_RECORDS_PER_ROLE,
    REQUIRED_TASK_TYPES,
    STEP_RATIO_LADDER,
    STUDY_THRESHOLDS,
    TARGET_IDENTIFIABILITY_ROLE,
    verify_identifiability_contract,
)
from trusted_synthesis.hashing import canonical_hash

IDENTIFIABILITY_STUDY_VERSION = "finance_target_identifiability_study.v20"
PLAN_HASH_PREFIX = "finance_target_identifiability_plan:"
DIRECTION_SCALE_HASH_PREFIX = "finance_target_identifiability_direction_scale:"
OBSERVATION_HASH_PREFIX = "finance_target_identifiability_observation:"
REPORT_HASH_PREFIX = "finance_target_identifiability_report:"
COMBINED_REPORT_HASH_PREFIX = "finance_target_identifiability_combined_report:"
OBJECTIVE_ROLES = ("estimation", "validation")
NUMERIC_FLOOR = 1e-12
T_CRITICAL_DF3_95 = 3.182446305284263


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"v20 identifiability artifact is not a JSON object:{path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as sink:
        sink.write(json.dumps(dict(value), ensure_ascii=False, sort_keys=True) + "\n")
        sink.flush()
        os.fsync(sink.fileno())


def _replay_hash(value: Mapping[str, Any], *, field: str, prefix: str) -> str:
    payload = dict(value)
    observed = payload.pop(field, None)
    expected = canonical_hash(payload, prefix=prefix)
    if observed != expected:
        raise ValueError(f"v20 identifiability identity replay failed:{field}")
    return str(observed)


def _next_power_of_two(value: int) -> int:
    if value < 1:
        raise ValueError("v20 block support must be positive")
    return 1 << (value - 1).bit_length()


def _sylvester_hadamard(order: int) -> tuple[tuple[int, ...], ...]:
    if order < 1 or order & (order - 1):
        raise ValueError("v20 Hadamard order must be a power of two")
    matrix: tuple[tuple[int, ...], ...] = ((1,),)
    while len(matrix) < order:
        matrix = tuple(tuple((*row, *row)) for row in matrix) + tuple(
            tuple((*row, *(-value for value in row))) for row in matrix
        )
    return matrix


def _validate_probabilities(values: Mapping[str, Any]) -> dict[str, float]:
    probabilities = {str(key): float(value) for key, value in sorted(values.items())}
    if not 3 <= len(probabilities) <= 5:
        raise ValueError("v20 target requires complete 3-5-state support")
    if any(value <= 0 or not math.isfinite(value) for value in probabilities.values()):
        raise ValueError("v20 target probabilities must be positive and finite")
    if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-12):
        raise ValueError("v20 target probabilities must sum to one")
    return probabilities


def _coordinate_rows(
    task_distributions: Mapping[str, Mapping[str, float]],
    task_marginals: Mapping[str, float],
) -> tuple[dict[str, Any], ...]:
    if set(task_distributions) != set(task_marginals):
        raise ValueError("v20 task marginals do not cover target distributions")
    rows = []
    for task_id, raw in sorted(task_distributions.items()):
        probabilities = _validate_probabilities(raw)
        state_ids = tuple(probabilities)
        reference_state_id = state_ids[-1]
        for state_id in state_ids[:-1]:
            row: dict[str, Any] = {
                "task_id": task_id,
                "state_id": state_id,
                "reference_state_id": reference_state_id,
                "task_marginal": float(task_marginals[task_id]),
                "current_probabilities": probabilities,
                "tangent_weights": {state_id: 0.5, reference_state_id: -0.5},
            }
            row["coordinate_id"] = canonical_hash(
                row,
                prefix="finance_finite_target_coordinate:",
            )
            rows.append(row)
    return tuple(rows)


def _select_direct_coordinates(
    coordinates: Sequence[Mapping[str, Any]],
    task_type_by_task_id: Mapping[str, str],
) -> tuple[str, ...]:
    by_task: defaultdict[str, list[str]] = defaultdict(list)
    for row in coordinates:
        by_task[str(row["task_id"])].append(str(row["coordinate_id"]))
    type_to_task: dict[str, str] = {}
    for task_id, task_type in task_type_by_task_id.items():
        if task_type in type_to_task:
            raise ValueError("v20 target contains duplicate required task types")
        type_to_task[task_type] = task_id
    if set(type_to_task) != set(REQUIRED_TASK_TYPES):
        raise ValueError("v20 target task-type support differs")
    selected = [sorted(by_task[type_to_task[task_type]])[0] for task_type in REQUIRED_TASK_TYPES]
    largest_task = max(by_task, key=lambda task_id: (len(by_task[task_id]), task_id))
    extra = next(
        (value for value in sorted(by_task[largest_task]) if value not in selected),
        None,
    )
    if extra is None:
        raise ValueError("v20 target lacks the preregistered seventh direct coordinate")
    selected.append(extra)
    if len(selected) != 7 or len(set(selected)) != 7:
        raise ValueError("v20 direct-coordinate gold support must contain seven coordinates")
    return tuple(selected)


def _design_row(
    *,
    role: str,
    family: str,
    block_size: int,
    block_index: int,
    row_index: int,
    coordinate_ids: Sequence[str],
    coordinate_weights: Mapping[str, int],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "role": role,
        "design_family": family,
        "block_size": block_size,
        "block_index": block_index,
        "row_index": row_index,
        "coordinate_ids": tuple(coordinate_ids),
        "coordinate_weights": dict(sorted(coordinate_weights.items())),
    }
    row["design_row_id"] = canonical_hash(
        row,
        prefix="finance_target_identifiability_design_row:",
    )
    return row


def build_design_rows(direct_coordinate_ids: Sequence[str]) -> tuple[dict[str, Any], ...]:
    direct = tuple(sorted(str(value) for value in direct_coordinate_ids))
    if len(direct) != 7 or len(set(direct)) != 7:
        raise ValueError("v20 design requires seven direct coordinates")
    rows = [
        _design_row(
            role="direct_coordinate",
            family="direct",
            block_size=1,
            block_index=index,
            row_index=0,
            coordinate_ids=(coordinate_id,),
            coordinate_weights={coordinate_id: 1},
        )
        for index, coordinate_id in enumerate(direct)
    ]
    for block_size in BLOCK_SIZES:
        for block_index, start in enumerate(range(0, len(direct), block_size)):
            block = direct[start : start + block_size]
            matrix = _sylvester_hadamard(_next_power_of_two(len(block)))
            for row_index, signs in enumerate(matrix):
                rows.append(
                    _design_row(
                        role="block_design",
                        family=f"block_{block_size}",
                        block_size=block_size,
                        block_index=block_index,
                        row_index=row_index,
                        coordinate_ids=block,
                        coordinate_weights={
                            coordinate_id: int(signs[index])
                            for index, coordinate_id in enumerate(block)
                        },
                    )
                )
    rows.append(
        _design_row(
            role="null_replay",
            family="null",
            block_size=0,
            block_index=0,
            row_index=0,
            coordinate_ids=(),
            coordinate_weights={},
        )
    )
    if len(rows) != 31:
        raise ValueError("v20 direct/block design must contain exactly 31 structural rows")
    if len({str(row["design_row_id"]) for row in rows}) != len(rows):
        raise ValueError("v20 design rows are not unique")
    return tuple(rows)


def _micro_split_manifest(
    record_ids: Sequence[str],
    *,
    role: str,
    contract_hash: str,
) -> tuple[dict[str, Any], ...]:
    ids = tuple(str(value) for value in record_ids)
    if len(ids) != OBJECTIVE_RECORDS_PER_ROLE or len(set(ids)) != len(ids):
        raise ValueError("v20 Objective role must contain exactly 16 unique records")
    ordered = sorted(
        ids,
        key=lambda value: canonical_hash(
            {"contract_hash": contract_hash, "role": role, "record_id": value},
            prefix="finance_target_identifiability_micro_split_order:",
        ),
    )
    buckets = [ordered[index::OBJECTIVE_MICRO_SPLIT_COUNT] for index in range(4)]
    rows = []
    for index, values in enumerate(buckets):
        if len(values) != OBJECTIVE_RECORDS_PER_MICRO_SPLIT:
            raise ValueError("v20 Objective micro-split size differs")
        row: dict[str, Any] = {
            "micro_split_index": index,
            "record_ids": tuple(values),
        }
        row["micro_split_id"] = canonical_hash(
            {"role": role, **row},
            prefix="finance_target_identifiability_micro_split:",
        )
        rows.append(row)
    if set().union(*(set(row["record_ids"]) for row in rows)) != set(ids):
        raise ValueError("v20 Objective micro-splits do not exactly partition the role")
    return tuple(rows)


def verify_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    frozen = dict(plan)
    _replay_hash(frozen, field="plan_hash", prefix=PLAN_HASH_PREFIX)
    if frozen.get("experiment_version") != IDENTIFIABILITY_STUDY_VERSION:
        raise ValueError("v20 identifiability plan version differs")
    if frozen.get("run_role") != TARGET_IDENTIFIABILITY_ROLE:
        raise ValueError("v20 identifiability plan role differs")
    if frozen.get("allowed_objective_roles") != list(OBJECTIVE_ROLES):
        raise ValueError("v20 identifiability Objective access differs")
    if frozen.get("authorization_objective_access") != "forbidden":
        raise ValueError("v20 identifiability plan opened Authorization")
    if frozen.get("production_authorization_eligible") is not False:
        raise ValueError("v20 identifiability plan cannot enter production")
    if frozen.get("gp_c_execution_allowed") is not False:
        raise ValueError("v20 identifiability plan cannot execute GP-C")
    if frozen.get("step_ratio_ladder") != list(STEP_RATIO_LADDER):
        raise ValueError("v20 identifiability step-ratio ladder differs")
    if frozen.get("study_thresholds") != STUDY_THRESHOLDS:
        raise ValueError("v20 identifiability thresholds differ")
    raw_distributions = frozen.get("task_distributions")
    raw_marginals = frozen.get("task_marginals")
    task_types = frozen.get("task_type_by_task_id")
    if not isinstance(raw_distributions, dict) or not isinstance(raw_marginals, dict):
        raise ValueError("v20 task distribution support is missing")
    if not isinstance(task_types, dict):
        raise ValueError("v20 task-type support is missing")
    task_distributions = {
        str(task_id): _validate_probabilities(values)
        for task_id, values in raw_distributions.items()
    }
    task_marginals = {str(task_id): float(value) for task_id, value in raw_marginals.items()}
    task_ids = set(task_distributions)
    if (
        task_ids != set(task_marginals)
        or task_ids != set(str(value) for value in frozen.get("task_ids", ()))
        or task_ids != set(str(value) for value in task_types)
        or set(str(value) for value in task_types.values()) != set(REQUIRED_TASK_TYPES)
    ):
        raise ValueError("v20 task identity support differs")
    if (
        any(value <= 0 or not math.isfinite(value) for value in task_marginals.values())
        or not math.isclose(sum(task_marginals.values()), 1.0, abs_tol=1e-12)
    ):
        raise ValueError("v20 task marginals are invalid")
    expected_coordinates = _coordinate_rows(task_distributions, task_marginals)
    if len(frozen.get("coordinate_rows", ())) != 14:
        raise ValueError("v20 quotient coordinate support differs")
    if canonical_hash(frozen["coordinate_rows"]) != canonical_hash(expected_coordinates):
        raise ValueError("v20 quotient coordinate registry differs")
    expected_direct = _select_direct_coordinates(expected_coordinates, task_types)
    if tuple(str(value) for value in frozen.get("direct_coordinate_ids", ())) != expected_direct:
        raise ValueError("v20 direct-coordinate support differs")
    expected_design = build_design_rows(expected_direct)
    if len(frozen.get("design_rows", ())) != len(expected_design):
        raise ValueError("v20 structural design support differs")
    if canonical_hash(frozen["design_rows"]) != canonical_hash(expected_design):
        raise ValueError("v20 structural design registry differs")
    partitions = frozen.get("objective_micro_splits")
    if not isinstance(partitions, dict) or set(partitions) != set(OBJECTIVE_ROLES):
        raise ValueError("v20 Objective micro-split roles differ")
    for role in OBJECTIVE_ROLES:
        rows = partitions[role]
        if len(rows) != OBJECTIVE_MICRO_SPLIT_COUNT:
            raise ValueError("v20 Objective micro-split count differs")
        ids = [str(value) for row in rows for value in row["record_ids"]]
        if len(ids) != OBJECTIVE_RECORDS_PER_ROLE or len(set(ids)) != len(ids):
            raise ValueError("v20 Objective micro-splits overlap or are incomplete")
        expected_rows = _micro_split_manifest(
            ids,
            role=role,
            contract_hash=str(frozen["contract_hash"]),
        )
        if canonical_hash(rows) != canonical_hash(expected_rows):
            raise ValueError("v20 Objective micro-split registry differs")
    sealed = frozen.get("sealed_authorization_partition")
    if not isinstance(sealed, dict) or len(sealed.get("record_ids", ())) != 16:
        raise ValueError("v20 sealed Authorization partition differs")
    role_id_sets = {
        role: {
            str(record_id)
            for row in partitions[role]
            for record_id in row["record_ids"]
        }
        for role in OBJECTIVE_ROLES
    }
    authorization_ids = {str(value) for value in sealed["record_ids"]}
    if len(authorization_ids) != OBJECTIVE_RECORDS_PER_ROLE:
        raise ValueError("v20 sealed Authorization partition contains duplicates")
    if role_id_sets["estimation"] & role_id_sets["validation"] or any(
        values & authorization_ids for values in role_id_sets.values()
    ):
        raise ValueError("v20 Objective partitions overlap")
    expected_authorization_set_id = canonical_hash(
        tuple(str(value) for value in sealed["record_ids"]),
        prefix="finance_target_identifiability_sealed_authorization_partition:",
    )
    if (
        sealed.get("objective_access") != "forbidden"
        or sealed.get("set_id") != expected_authorization_set_id
    ):
        raise ValueError("v20 sealed Authorization identity differs")
    return frozen


def build_plan(
    *,
    contract: Mapping[str, Any],
    gradient_plan: Mapping[str, Any],
    gradient_report: Mapping[str, Any],
) -> dict[str, Any]:
    contract = verify_identifiability_contract(contract)
    if gradient_plan.get("run_role") != TARGET_IDENTIFIABILITY_ROLE:
        raise ValueError("v20 plan requires the target-identifiability Gradient role")
    if gradient_plan.get("numeric_contract_hash") != contract["contract_hash"]:
        raise ValueError("v20 Gradient plan uses another identifiability contract")
    if gradient_report.get("plan_hash") != gradient_plan.get("plan_hash"):
        raise ValueError("v20 Gradient report does not replay its plan")
    if gradient_report.get("numeric_contract_hash") != contract["contract_hash"]:
        raise ValueError("v20 Gradient report uses another identifiability contract")
    if gradient_report.get("task_count") != 6 or gradient_report.get("state_count") != 20:
        raise ValueError("v20 Gradient support differs")
    if gradient_report.get("state_realization_count") != 60:
        raise ValueError("v20 Gradient realization support differs")
    if gradient_report.get("gradient_realization_stability", {}).get("status") != "passed":
        raise ValueError("v20 requires stable state realizations before target measurement")
    if not gradient_report.get("all_state_realizations_fresh_and_verified"):
        raise ValueError("v20 requires fresh independently verified realizations")
    task_ids = {str(value) for value in gradient_plan.get("selected_task_ids", ())}
    if task_ids != set(str(value) for value in contract["task_ids"]):
        raise ValueError("v20 Gradient plan targets another task population")
    task_type_by_task_id = {
        str(row["task_id"]): str(row["task_type"]) for row in gradient_plan["jobs"]
    }
    if set(task_type_by_task_id.values()) != set(REQUIRED_TASK_TYPES):
        raise ValueError("v20 Gradient task types differ")
    task_distributions = {
        str(task_id): _validate_probabilities(values["probabilities"])
        for task_id, values in gradient_plan["task_distributions"].items()
    }
    task_marginals = {
        str(task_id): float(value) for task_id, value in gradient_report["task_marginals"].items()
    }
    coordinates = _coordinate_rows(task_distributions, task_marginals)
    direct_ids = _select_direct_coordinates(coordinates, task_type_by_task_id)
    design_rows = build_design_rows(direct_ids)
    source_partitions = contract["source_support"]["objective_partition_ids"]
    gradient_roles = {
        "estimation": tuple(
            str(value) for value in gradient_plan["gradient_estimation_record_ids"]
        ),
        "validation": tuple(
            str(value) for value in gradient_plan["gradient_validation_record_ids"]
        ),
        "authorization": tuple(str(value) for value in gradient_plan["final_test_record_ids"]),
    }
    if any(gradient_roles[role] != tuple(source_partitions[role]) for role in gradient_roles):
        raise ValueError("v20 Gradient Objective partitions differ from the sealed contract")
    micro_splits = {
        role: _micro_split_manifest(
            gradient_roles[role],
            role=role,
            contract_hash=str(contract["contract_hash"]),
        )
        for role in OBJECTIVE_ROLES
    }
    values: dict[str, Any] = {
        "experiment_version": IDENTIFIABILITY_STUDY_VERSION,
        "artifact_type": "FiniteTargetIdentifiabilityPlan",
        "run_role": TARGET_IDENTIFIABILITY_ROLE,
        "contract_hash": contract["contract_hash"],
        "numeric_contract_hash": contract["contract_hash"],
        "numeric_profile": contract["selected_profile"],
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
        "optimizer_contract": gradient_plan["local_optimizer_contract"],
        "task_ids": tuple(sorted(task_ids)),
        "task_type_by_task_id": dict(sorted(task_type_by_task_id.items())),
        "task_distributions": task_distributions,
        "task_marginals": task_marginals,
        "coordinate_rows": coordinates,
        "coordinate_count": len(coordinates),
        "direct_coordinate_ids": direct_ids,
        "design_rows": design_rows,
        "design_row_count": len(design_rows),
        "block_sizes": list(BLOCK_SIZES),
        "step_ratio_ladder": list(STEP_RATIO_LADDER),
        "parameter_step_normalization": "actual_perturbation_norm_over_actual_global_step_norm",
        "objective_micro_splits": micro_splits,
        "sealed_authorization_partition": {
            "record_ids": gradient_roles["authorization"],
            "set_id": canonical_hash(
                gradient_roles["authorization"],
                prefix="finance_target_identifiability_sealed_authorization_partition:",
            ),
            "objective_access": "forbidden",
        },
        "allowed_objective_roles": list(OBJECTIVE_ROLES),
        "authorization_objective_access": "forbidden",
        "study_thresholds": STUDY_THRESHOLDS,
        "local_slope_model": "odd_cubic_delta_J_equals_a1_s_plus_a3_s_cubed",
        "production_authorization_eligible": False,
        "gp_c_execution_allowed": False,
        "contribution_approximation_authorized": False,
        "success_transition": "freeze_fresh_proxy_comparison_study",
        "failure_transition": "retain_contribution_zero_and_redesign_target_measurement",
        "claim_boundary": (
            "This plan tests finite-target first-order identifiability only. It cannot evaluate "
            "GP-C, open Authorization, authorize Contribution, or update VTDO."
        ),
    }
    values["plan_hash"] = canonical_hash(values, prefix=PLAN_HASH_PREFIX)
    return verify_plan(values)


def freeze_directions_and_scales(
    plan: Mapping[str, Any],
    update_manifest: Mapping[str, Any],
    *,
    output_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from trusted_synthesis.experiments.vtdo_experiment.phase1_gp_c_proxy import (
        freeze_finite_target_directions,
    )

    plan = verify_plan(plan)
    if update_manifest.get("source_gradient_plan_hash") != plan["source_gradient_plan_hash"]:
        raise ValueError("v20 local updates belong to another Gradient plan")
    if update_manifest.get("run_role") != TARGET_IDENTIFIABILITY_ROLE:
        raise ValueError("v20 local updates have another run role")
    if update_manifest.get("production_authorization_eligible") is not False:
        raise ValueError("v20 local updates unexpectedly permit production")
    output_dir.mkdir(parents=True, exist_ok=True)
    direction_manifest = freeze_finite_target_directions(
        plan,
        update_manifest,
        output_dir=output_dir,
    )
    direction_by_id = {
        str(row["design_row_id"]): row for row in direction_manifest["direction_artifacts"]
    }
    scale_rows = []
    for design in plan["design_rows"]:
        row_id = str(design["design_row_id"])
        direction_norm = float(direction_by_id[row_id]["direction_norm"])
        if design["role"] != "null_replay" and direction_norm <= 0:
            raise ValueError("v20 non-null direction has zero norm")
        for ratio in plan["step_ratio_ladder"]:
            scale_rows.append(
                {
                    "design_row_id": row_id,
                    "target_parameter_step_ratio": float(ratio),
                    "direction_norm": direction_norm,
                    "coefficient_per_actual_global_step_norm": (
                        0.0 if design["role"] == "null_replay" else float(ratio) / direction_norm
                    ),
                }
            )
    scale_manifest: dict[str, Any] = {
        "experiment_version": IDENTIFIABILITY_STUDY_VERSION,
        "artifact_type": "FiniteTargetDirectionScaleManifest",
        "plan_hash": plan["plan_hash"],
        "direction_manifest_hash": direction_manifest["manifest_hash"],
        "local_update_manifest_hash": update_manifest["manifest_hash"],
        "global_update_artifact": update_manifest["global_update_artifact"],
        "normalization": "coefficient_times_measured_actual_global_parameter_step_norm",
        "scale_rows": tuple(scale_rows),
    }
    scale_manifest["manifest_hash"] = canonical_hash(
        scale_manifest,
        prefix=DIRECTION_SCALE_HASH_PREFIX,
    )
    _write_json(output_dir / "direction_manifest.json", direction_manifest)
    _write_json(output_dir / "direction_scale_manifest.json", scale_manifest)
    return direction_manifest, scale_manifest


def _verify_scale_manifest(
    plan: Mapping[str, Any],
    direction_manifest: Mapping[str, Any],
    scale_manifest: Mapping[str, Any],
) -> str:
    from trusted_synthesis.experiments.vtdo_experiment.phase1_finite_target import (
        _verify_direction_manifest,
    )

    _verify_direction_manifest(plan, direction_manifest)
    observed = _replay_hash(
        scale_manifest,
        field="manifest_hash",
        prefix=DIRECTION_SCALE_HASH_PREFIX,
    )
    if scale_manifest.get("plan_hash") != plan["plan_hash"]:
        raise ValueError("v20 direction scales belong to another plan")
    if scale_manifest.get("direction_manifest_hash") != direction_manifest["manifest_hash"]:
        raise ValueError("v20 direction scales belong to another direction manifest")
    expected = len(plan["design_rows"]) * len(plan["step_ratio_ladder"])
    if len(scale_manifest.get("scale_rows", ())) != expected:
        raise ValueError("v20 direction scale support is incomplete")
    return observed


def _snapshot_trainable(model: Any) -> dict[str, Any]:
    values = {
        name: parameter.detach().float().clone()
        for name, parameter in sorted(model.named_parameters())
        if parameter.requires_grad
    }
    if not values:
        raise ValueError("v20 execution found no trainable parameters")
    return values


def _parameter_distance(model: Any, reference: Mapping[str, Any]) -> float:
    total = 0.0
    parameters = {
        name: parameter
        for name, parameter in sorted(model.named_parameters())
        if parameter.requires_grad
    }
    if tuple(parameters) != tuple(reference):
        raise ValueError("v20 trainable parameter support changed")
    for name, parameter in parameters.items():
        difference = parameter.detach().float() - reference[name]
        total += float((difference.double() ** 2).sum().cpu())
    return math.sqrt(total)


def _summarize_micro_splits(
    record_rows: Sequence[Mapping[str, Any]],
    micro_splits: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    by_id = {str(row["record_id"]): row for row in record_rows}
    values = []
    for split in micro_splits:
        rows = [by_id[str(record_id)] for record_id in split["record_ids"]]
        token_count = sum(int(row["supervised_tokens"]) for row in rows)
        if token_count <= 0:
            raise ValueError("v20 Objective micro-split has no supervised tokens")
        weighted_loss = sum(
            float(row["negative_log_likelihood"]) * int(row["supervised_tokens"]) for row in rows
        )
        loss = weighted_loss / token_count
        values.append(
            {
                "micro_split_id": split["micro_split_id"],
                "record_ids": split["record_ids"],
                "performance": -loss,
                "negative_log_likelihood": loss,
                "supervised_tokens": token_count,
            }
        )
    return tuple(values)


def _observation_hash(value: Mapping[str, Any]) -> str:
    payload = dict(value)
    payload.pop("observation_hash", None)
    return canonical_hash(payload, prefix=OBSERVATION_HASH_PREFIX)


def execute(
    *,
    output_dir: Path,
    direction_dir: Path,
    objective_role: Literal["estimation", "validation"],
    gpu_ids: tuple[int, ...],
    partition_index: int,
    partition_count: int,
    numeric_seed: int,
) -> dict[str, Any]:
    import torch
    from peft import get_peft_model_state_dict

    from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
        _evaluate_records_numeric_detailed,
        _load_execution_model,
        _load_verified_gradient,
    )
    from trusted_synthesis.experiments.vtdo_experiment.phase1_gp_c_proxy import (
        _apply_descent_vector,
        _linear_combination,
        _restore_adapter,
    )
    from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
        _adapter_tensor_sha256,
        _load_records,
        _load_tokenizer,
        _seed_everything,
    )

    if objective_role not in OBJECTIVE_ROLES:
        raise ValueError("v20 execution cannot open this Objective role")
    if len(gpu_ids) != 3 or len(set(gpu_ids)) != 3:
        raise ValueError("v20 execution requires one frozen three-GPU group")
    if any(value < 0 or value >= torch.cuda.device_count() for value in gpu_ids):
        raise ValueError("v20 execution GPU group is unavailable")
    if not 0 <= partition_index < partition_count:
        raise ValueError("v20 execution partition is invalid")
    torch.cuda.set_device(gpu_ids[0])
    plan = verify_plan(_read_json(output_dir / "plan.json"))
    direction_manifest = _read_json(direction_dir / "direction_manifest.json")
    scale_manifest = _read_json(direction_dir / "direction_scale_manifest.json")
    _verify_scale_manifest(plan, direction_manifest, scale_manifest)
    records_path = Path(str(plan["source_records_path"]))
    if _sha256(records_path) != plan["source_records_sha256"]:
        raise ValueError("v20 Objective records changed after planning")
    records = _load_records(records_path)
    micro_splits = tuple(plan["objective_micro_splits"][objective_role])
    objective_ids = tuple(str(value) for split in micro_splits for value in split["record_ids"])
    if len(objective_ids) != 16 or any(record_id not in records for record_id in objective_ids):
        raise ValueError("v20 Objective support is incomplete")
    objective_records = tuple(records[record_id] for record_id in objective_ids)
    direction_by_id = {
        str(row["design_row_id"]): row for row in direction_manifest["direction_artifacts"]
    }
    scale_by_key = {
        (str(row["design_row_id"]), float(row["target_parameter_step_ratio"])): row
        for row in scale_manifest["scale_rows"]
    }
    jobs = [
        {
            "design_row_id": str(row["design_row_id"]),
            "target_parameter_step_ratio": float(ratio),
            "sign": sign,
        }
        for row in plan["design_rows"]
        for ratio in plan["step_ratio_ladder"]
        for sign in (-1, 1)
    ]
    assigned = [job for index, job in enumerate(jobs) if index % partition_count == partition_index]
    worker_dir = output_dir / "workers" / objective_role
    worker_path = worker_dir / f"partition_{partition_index}.jsonl"
    existing = _load_jsonl(worker_path) if worker_path.is_file() else []
    completed = {
        (
            str(row["design_row_id"]),
            float(row["target_parameter_step_ratio"]),
            int(row["sign"]),
        )
        for row in existing
        if row.get("observation_hash") == _observation_hash(row)
    }
    _seed_everything(numeric_seed)
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
        raise ValueError("v20 execution loaded another beneficiary Adapter")
    baseline_state = {
        name: value.detach().cpu().clone()
        for name, value in get_peft_model_state_dict(model).items()
    }
    baseline_trainable = _snapshot_trainable(model)
    global_artifact = scale_manifest["global_update_artifact"]
    global_update = _load_verified_gradient(
        Path(str(global_artifact["file"])),
        str(global_artifact["sha256"]),
    )
    _restore_adapter(model, baseline_state)
    _apply_descent_vector(model, global_update)
    actual_global_step_norm = _parameter_distance(model, baseline_trainable)
    if actual_global_step_norm <= 0 or not math.isfinite(actual_global_step_norm):
        raise ValueError("v20 actual global parameter step is invalid")
    post_global_trainable = _snapshot_trainable(model)
    post_global_adapter_hash = _adapter_tensor_sha256(model)
    baseline_performance, baseline_loss, baseline_tokens, baseline_rows = (
        _evaluate_records_numeric_detailed(model, tokenizer, objective_records)
    )
    baseline_micro = _summarize_micro_splits(baseline_rows, micro_splits)
    baseline_manifest_hash = canonical_hash(
        baseline_micro,
        prefix=f"finance_target_identifiability_{objective_role}_baseline_micro_splits:",
    )
    started = time.monotonic()
    completed_now = 0
    cached_direction_id = None
    cached_direction = None
    design_by_id = {str(row["design_row_id"]): row for row in plan["design_rows"]}
    for job in assigned:
        row_id = str(job["design_row_id"])
        ratio = float(job["target_parameter_step_ratio"])
        sign = int(job["sign"])
        key = (row_id, ratio, sign)
        if key in completed:
            continue
        if cached_direction_id != row_id:
            del cached_direction
            artifact = direction_by_id[row_id]
            cached_direction = _load_verified_gradient(
                Path(str(artifact["file"])),
                str(artifact["sha256"]),
            )
            cached_direction_id = row_id
        scale = scale_by_key[(row_id, ratio)]
        coefficient = (
            float(scale["coefficient_per_actual_global_step_norm"]) * actual_global_step_norm
        )
        if cached_direction is None:
            raise ValueError("v20 direction cache is empty")
        update = _linear_combination(
            [global_update, cached_direction],
            [1.0, sign * coefficient],
        )
        _seed_everything(numeric_seed)
        _restore_adapter(model, baseline_state)
        _apply_descent_vector(model, update)
        actual_step_norm = _parameter_distance(model, post_global_trainable)
        actual_ratio = actual_step_norm / actual_global_step_norm
        performance, loss, tokens, record_rows = _evaluate_records_numeric_detailed(
            model,
            tokenizer,
            objective_records,
        )
        if tokens != baseline_tokens:
            raise ValueError("v20 perturbation changed Objective token support")
        micro_results = _summarize_micro_splits(record_rows, micro_splits)
        observation: dict[str, Any] = {
            "experiment_version": IDENTIFIABILITY_STUDY_VERSION,
            "plan_hash": plan["plan_hash"],
            "direction_manifest_hash": direction_manifest["manifest_hash"],
            "direction_scale_manifest_hash": scale_manifest["manifest_hash"],
            "objective_role": objective_role,
            "authorization_objective_access": "forbidden",
            "design_row_id": row_id,
            "design_role": design_by_id[row_id]["role"],
            "design_family": design_by_id[row_id]["design_family"],
            "target_parameter_step_ratio": ratio,
            "sign": sign,
            "coefficient": coefficient,
            "actual_global_parameter_step_norm": actual_global_step_norm,
            "actual_parameter_step_norm": actual_step_norm,
            "actual_parameter_step_ratio": actual_ratio,
            "objective_value": performance,
            "negative_log_likelihood": loss,
            "supervised_tokens": tokens,
            "micro_split_results": micro_results,
            "baseline_objective_value": baseline_performance,
            "baseline_negative_log_likelihood": baseline_loss,
            "baseline_supervised_tokens": baseline_tokens,
            "baseline_micro_split_results": baseline_micro,
            "baseline_micro_split_manifest_hash": baseline_manifest_hash,
            "baseline_post_global_adapter_hash": post_global_adapter_hash,
            "perturbed_adapter_hash": _adapter_tensor_sha256(model),
            "numeric_contract_hash": plan["numeric_contract_hash"],
            "numeric_seed": numeric_seed,
            "partition_index": partition_index,
            "partition_count": partition_count,
        }
        observation["observation_hash"] = _observation_hash(observation)
        _append_jsonl(worker_path, observation)
        completed_now += 1
        del update, record_rows
    worker_report = {
        "experiment_version": IDENTIFIABILITY_STUDY_VERSION,
        "plan_hash": plan["plan_hash"],
        "objective_role": objective_role,
        "authorization_objective_access": "forbidden",
        "partition_index": partition_index,
        "partition_count": partition_count,
        "assigned_count": len(assigned),
        "completed_before_resume": len(completed),
        "completed_now": completed_now,
        "runtime_seconds": time.monotonic() - started,
        "actual_global_parameter_step_norm": actual_global_step_norm,
        "baseline_micro_split_manifest_hash": baseline_manifest_hash,
        "requested_cuda_device_ids": gpu_ids,
        "resolved_hf_device_map": resolved_device_map,
        "peak_gpu_memory_bytes": max(
            int(torch.cuda.max_memory_allocated(gpu_id)) for gpu_id in gpu_ids
        ),
    }
    worker_report["report_hash"] = canonical_hash(
        worker_report,
        prefix="finance_target_identifiability_worker_report:",
    )
    _write_json(worker_dir / f"partition_{partition_index}_report.json", worker_report)
    del (
        model,
        global_update,
        cached_direction,
        baseline_state,
        baseline_trainable,
        post_global_trainable,
    )
    gc.collect()
    torch.cuda.empty_cache()
    return worker_report


def odd_cubic_fit(points: Sequence[tuple[float, float]]) -> dict[str, float]:
    if len(points) < 4:
        raise ValueError("v20 odd-cubic fit requires multiple symmetric radii")
    scale = max(abs(float(step)) for step, _ in points)
    if scale <= 0:
        raise ValueError("v20 odd-cubic fit has zero parameter support")
    normalized = [(float(step) / scale, float(value)) for step, value in points]
    s2 = sum(step**2 for step, _ in normalized)
    s4 = sum(step**4 for step, _ in normalized)
    s6 = sum(step**6 for step, _ in normalized)
    b1 = sum(step * value for step, value in normalized)
    b3 = sum(step**3 * value for step, value in normalized)
    determinant = s2 * s6 - s4 * s4
    if abs(determinant) <= 1e-15:
        raise ValueError("v20 odd-cubic design is singular")
    normalized_linear = (b1 * s6 - b3 * s4) / determinant
    normalized_cubic = (s2 * b3 - s4 * b1) / determinant
    linear = normalized_linear / scale
    cubic = normalized_cubic / (scale**3)
    residuals = [
        value - (normalized_linear * step + normalized_cubic * step**3)
        for step, value in normalized
    ]
    return {
        "linear_slope": linear,
        "cubic_coefficient": cubic,
        "normalized_linear_effect": normalized_linear,
        "normalized_cubic_effect": normalized_cubic,
        "nonlinearity_ratio": abs(normalized_cubic) / max(abs(normalized_linear), NUMERIC_FLOOR),
        "residual_rms": math.sqrt(sum(value * value for value in residuals) / len(residuals)),
    }


def _percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("v20 percentile has no values")
    ordered = sorted(float(value) for value in values)
    position = probability * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _mean_ci95(values: Sequence[float]) -> tuple[float, tuple[float, float], float]:
    if len(values) != 4:
        raise ValueError("v20 slope inference requires four Objective micro-splits")
    mean = statistics.fmean(values)
    deviation = statistics.stdev(values)
    half_width = T_CRITICAL_DF3_95 * deviation / math.sqrt(len(values))
    return mean, (mean - half_width, mean + half_width), deviation


def analyze_role(
    plan: Mapping[str, Any],
    direction_manifest: Mapping[str, Any],
    scale_manifest: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
    *,
    objective_role: Literal["estimation", "validation"],
) -> dict[str, Any]:
    plan = verify_plan(plan)
    _verify_scale_manifest(plan, direction_manifest, scale_manifest)
    if objective_role not in OBJECTIVE_ROLES:
        raise ValueError("v20 analysis cannot open this Objective role")
    expected = {
        (str(row["design_row_id"]), float(ratio), sign)
        for row in plan["design_rows"]
        for ratio in plan["step_ratio_ladder"]
        for sign in (-1, 1)
    }
    observed: dict[tuple[str, float, int], Mapping[str, Any]] = {}
    for row in observations:
        if row.get("observation_hash") != _observation_hash(row):
            raise ValueError("v20 observation identity changed")
        if row.get("plan_hash") != plan["plan_hash"]:
            raise ValueError("v20 observation belongs to another plan")
        if row.get("objective_role") != objective_role:
            raise ValueError("v20 observations cross Objective roles")
        if row.get("authorization_objective_access") != "forbidden":
            raise ValueError("v20 observation opened Authorization")
        key = (
            str(row["design_row_id"]),
            float(row["target_parameter_step_ratio"]),
            int(row["sign"]),
        )
        if key in observed:
            raise ValueError("v20 observation matrix contains duplicates")
        observed[key] = row
    if set(observed) != expected:
        raise ValueError(f"v20 observation matrix is incomplete:{len(observed)}/{len(expected)}")
    direction_rows = {
        str(row["design_row_id"]): row for row in direction_manifest["direction_artifacts"]
    }
    design_rows = {str(row["design_row_id"]): row for row in plan["design_rows"]}
    split_ids = [
        str(row["micro_split_id"]) for row in plan["objective_micro_splits"][objective_role]
    ]
    expected_splits = {
        str(row["micro_split_id"]): tuple(str(value) for value in row["record_ids"])
        for row in plan["objective_micro_splits"][objective_role]
    }
    baseline_hash_prefix = (
        f"finance_target_identifiability_{objective_role}_baseline_micro_splits:"
    )
    baseline_hashes = {str(row["baseline_micro_split_manifest_hash"]) for row in observations}
    baseline_content_hashes = {
        canonical_hash(row["baseline_micro_split_results"], prefix=baseline_hash_prefix)
        for row in observations
    }
    baseline_adapter_hashes = {
        str(row["baseline_post_global_adapter_hash"]) for row in observations
    }
    global_norms = {float(row["actual_global_parameter_step_norm"]) for row in observations}
    numeric_seeds = {int(row["numeric_seed"]) for row in observations}
    measurement_rows_valid = True
    for observation in observations:
        current = {
            str(value["micro_split_id"]): value
            for value in observation["micro_split_results"]
        }
        baseline = {
            str(value["micro_split_id"]): value
            for value in observation["baseline_micro_split_results"]
        }
        if set(current) != set(split_ids) or set(baseline) != set(split_ids):
            measurement_rows_valid = False
            continue
        for split_id in split_ids:
            if (
                tuple(str(value) for value in current[split_id]["record_ids"])
                != expected_splits[split_id]
                or tuple(str(value) for value in baseline[split_id]["record_ids"])
                != expected_splits[split_id]
                or int(current[split_id]["supervised_tokens"]) <= 0
                or int(current[split_id]["supervised_tokens"])
                != int(baseline[split_id]["supervised_tokens"])
            ):
                measurement_rows_valid = False
        current_tokens = sum(int(value["supervised_tokens"]) for value in current.values())
        baseline_tokens = sum(int(value["supervised_tokens"]) for value in baseline.values())
        if current_tokens <= 0 or baseline_tokens <= 0:
            measurement_rows_valid = False
            continue
        current_loss = sum(
            float(value["negative_log_likelihood"]) * int(value["supervised_tokens"])
            for value in current.values()
        ) / current_tokens
        baseline_loss = sum(
            float(value["negative_log_likelihood"]) * int(value["supervised_tokens"])
            for value in baseline.values()
        ) / baseline_tokens
        measurement_rows_valid = measurement_rows_valid and bool(
            current_tokens == int(observation["supervised_tokens"])
            and baseline_tokens == int(observation["baseline_supervised_tokens"])
            and math.isclose(
                current_loss,
                float(observation["negative_log_likelihood"]),
                rel_tol=0.0,
                abs_tol=1e-10,
            )
            and math.isclose(
                -current_loss,
                float(observation["objective_value"]),
                rel_tol=0.0,
                abs_tol=1e-10,
            )
            and math.isclose(
                baseline_loss,
                float(observation["baseline_negative_log_likelihood"]),
                rel_tol=0.0,
                abs_tol=1e-10,
            )
            and math.isclose(
                -baseline_loss,
                float(observation["baseline_objective_value"]),
                rel_tol=0.0,
                abs_tol=1e-10,
            )
            and canonical_hash(
                observation["baseline_micro_split_results"],
                prefix=baseline_hash_prefix,
            )
            == observation["baseline_micro_split_manifest_hash"]
        )
    objective_measurement_passed = measurement_rows_valid and all(
        len(values) == 1
        for values in (
            baseline_hashes,
            baseline_content_hashes,
            baseline_adapter_hashes,
            global_norms,
            numeric_seeds,
        )
    )
    nonnull = [row for row in observations if row["design_role"] != "null_replay"]
    ratio_errors = [
        abs(float(row["actual_parameter_step_ratio"]) - float(row["target_parameter_step_ratio"]))
        / float(row["target_parameter_step_ratio"])
        for row in nonnull
    ]
    max_ratio_error = max(ratio_errors)
    parameter_scale_passed = max_ratio_error <= float(
        plan["study_thresholds"]["maximum_parameter_step_ratio_relative_error"]
    )
    fit_rows = []
    fit_by_design: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row_id, design in design_rows.items():
        for split_id in split_ids:
            if design["role"] == "null_replay":
                continue
            points = []
            for ratio in plan["step_ratio_ladder"]:
                for sign in (-1, 1):
                    observation = observed[(row_id, float(ratio), sign)]
                    current = next(
                        value
                        for value in observation["micro_split_results"]
                        if str(value["micro_split_id"]) == split_id
                    )
                    baseline = next(
                        value
                        for value in observation["baseline_micro_split_results"]
                        if str(value["micro_split_id"]) == split_id
                    )
                    points.append(
                        (
                            sign * float(observation["actual_parameter_step_norm"]),
                            float(current["performance"]) - float(baseline["performance"]),
                        )
                    )
            fit = odd_cubic_fit(points)
            fit_row = {
                "design_row_id": row_id,
                "design_role": design["role"],
                "design_family": design["design_family"],
                "micro_split_id": split_id,
                **fit,
            }
            fit_rows.append(fit_row)
            fit_by_design[row_id].append(fit_row)
    design_summaries = []
    for row_id, rows in sorted(fit_by_design.items()):
        slopes = [float(row["linear_slope"]) for row in rows]
        mean, ci95, deviation = _mean_ci95(slopes)
        sign_consistency = max(
            sum(value > 0 for value in slopes),
            sum(value < 0 for value in slopes),
        ) / len(slopes)
        slope_cv = deviation / max(abs(mean), NUMERIC_FLOOR)
        nonlinear_p95 = _percentile(
            [float(row["nonlinearity_ratio"]) for row in rows],
            0.95,
        )
        design_summaries.append(
            {
                "design_row_id": row_id,
                "design_role": design_rows[row_id]["role"],
                "design_family": design_rows[row_id]["design_family"],
                "coordinate_ids": design_rows[row_id]["coordinate_ids"],
                "coordinate_weights": design_rows[row_id]["coordinate_weights"],
                "mean_linear_slope": mean,
                "linear_slope_ci95": ci95,
                "linear_slope_standard_deviation": deviation,
                "linear_slope_cv": slope_cv,
                "micro_split_sign_consistency": sign_consistency,
                "p95_nonlinearity_ratio": nonlinear_p95,
            }
        )
    direct_summaries = [
        row for row in design_summaries if row["design_role"] == "direct_coordinate"
    ]
    direct_by_coordinate = {str(row["coordinate_ids"][0]): row for row in direct_summaries}
    direct_direction_norm = {
        str(design_rows[row_id]["coordinate_ids"][0]): float(
            direction_rows[row_id]["direction_norm"]
        )
        for row_id in design_rows
        if design_rows[row_id]["role"] == "direct_coordinate"
    }
    anchor_rows = []
    for row in direct_summaries:
        lower, upper = (float(value) for value in row["linear_slope_ci95"])
        identifiable = bool(
            (lower > 0 or upper < 0)
            and float(row["micro_split_sign_consistency"])
            >= float(plan["study_thresholds"]["minimum_micro_split_sign_consistency"])
            and float(row["linear_slope_cv"])
            <= float(plan["study_thresholds"]["maximum_micro_split_slope_cv"])
            and float(row["p95_nonlinearity_ratio"])
            <= float(plan["study_thresholds"]["maximum_p95_nonlinearity_ratio"])
        )
        anchor_rows.append({**row, "identifiable": identifiable})
    anchor_rate = sum(bool(row["identifiable"]) for row in anchor_rows) / len(anchor_rows)
    block_rows = []
    for row in design_summaries:
        if row["design_role"] != "block_design":
            continue
        row_id = str(row["design_row_id"])
        block_norm = float(direction_rows[row_id]["direction_norm"])
        predicted = (
            sum(
                float(row["coordinate_weights"][coordinate_id])
                * direct_direction_norm[coordinate_id]
                * float(direct_by_coordinate[coordinate_id]["mean_linear_slope"])
                for coordinate_id in row["coordinate_ids"]
            )
            / block_norm
        )
        observed_slope = float(row["mean_linear_slope"])
        magnitude = max(abs(predicted), abs(observed_slope))
        relative_error = (
            0.0 if magnitude <= NUMERIC_FLOOR else abs(predicted - observed_slope) / magnitude
        )
        direction_agreement = float(
            predicted != 0 and observed_slope != 0 and (predicted > 0) == (observed_slope > 0)
        )
        block_rows.append(
            {
                **row,
                "predicted_from_direct_coordinates": predicted,
                "reconstruction_relative_error": relative_error,
                "direction_agreement": direction_agreement,
            }
        )
    maximum_block_error = max(float(row["reconstruction_relative_error"]) for row in block_rows)
    block_direction_agreement = statistics.fmean(
        float(row["direction_agreement"]) for row in block_rows
    )
    maximum_p95_nonlinearity = max(float(row["p95_nonlinearity_ratio"]) for row in design_summaries)
    maximum_direct_slope_cv = max(float(row["linear_slope_cv"]) for row in direct_summaries)
    local_linearity_passed = bool(
        maximum_p95_nonlinearity
        <= float(plan["study_thresholds"]["maximum_p95_nonlinearity_ratio"])
        and maximum_direct_slope_cv
        <= float(plan["study_thresholds"]["maximum_micro_split_slope_cv"])
    )
    design_reconstruction_passed = bool(
        maximum_block_error
        <= float(plan["study_thresholds"]["maximum_block_reconstruction_relative_error"])
        and block_direction_agreement
        >= float(plan["study_thresholds"]["minimum_block_direction_agreement"])
    )
    anchor_identifiability_passed = anchor_rate >= float(
        plan["study_thresholds"]["minimum_anchor_identifiable_rate"]
    )
    numeric_values = [
        float(row[field])
        for row in observations
        for field in (
            "objective_value",
            "negative_log_likelihood",
            "actual_global_parameter_step_norm",
            "actual_parameter_step_norm",
            "actual_parameter_step_ratio",
        )
    ]
    null_rows = [row for row in observations if row["design_role"] == "null_replay"]
    null_deltas = [
        abs(float(row["objective_value"]) - float(row["baseline_objective_value"]))
        for row in null_rows
    ]
    null_replay_passed = bool(
        len(null_rows) == 2 * len(plan["step_ratio_ladder"])
        and max(null_deltas) <= 1e-10
        and all(
            abs(float(row["actual_parameter_step_norm"])) <= 1e-12
            and abs(float(row["actual_parameter_step_ratio"])) <= 1e-12
            and row.get("perturbed_adapter_hash") == row.get("baseline_post_global_adapter_hash")
            for row in null_rows
        )
    )
    numeric_gate_passed = bool(
        all(math.isfinite(value) for value in numeric_values)
        and all(
            row.get("numeric_contract_hash") == plan["numeric_contract_hash"]
            for row in observations
        )
    )
    gates = {
        "numeric_gate": numeric_gate_passed,
        "null_replay_gate": null_replay_passed,
        "parameter_scale_gate": parameter_scale_passed,
        "objective_measurement_gate": objective_measurement_passed,
        "local_linearity_gate": local_linearity_passed,
        "anchor_identifiability_gate": anchor_identifiability_passed,
        "design_reconstruction_gate": design_reconstruction_passed,
    }
    passed = all(gates.values())
    report: dict[str, Any] = {
        "experiment_version": IDENTIFIABILITY_STUDY_VERSION,
        "artifact_type": "FiniteTargetIdentifiabilityRoleReport",
        "plan_hash": plan["plan_hash"],
        "direction_manifest_hash": direction_manifest["manifest_hash"],
        "direction_scale_manifest_hash": scale_manifest["manifest_hash"],
        "objective_role": objective_role,
        "authorization_objective_access": "forbidden",
        "observation_count": len(observations),
        "expected_observation_count": len(expected),
        "objective_micro_split_count": len(split_ids),
        "gates": gates,
        "maximum_parameter_step_ratio_relative_error": max_ratio_error,
        "anchor_identifiable_rate": anchor_rate,
        "maximum_direct_slope_cv": maximum_direct_slope_cv,
        "maximum_p95_nonlinearity_ratio": maximum_p95_nonlinearity,
        "maximum_block_reconstruction_relative_error": maximum_block_error,
        "block_direction_agreement": block_direction_agreement,
        "maximum_null_objective_delta": max(null_deltas),
        "direct_coordinate_rows": tuple(anchor_rows),
        "block_reconstruction_rows": tuple(block_rows),
        "fit_rows": tuple(fit_rows),
        "study_thresholds": plan["study_thresholds"],
        "status": "passed" if passed else "failed",
        "gp_c_evaluated": False,
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
        "claim_boundary": plan["claim_boundary"],
    }
    report["report_hash"] = canonical_hash(report, prefix=REPORT_HASH_PREFIX)
    return report


def combine_reports(
    plan: Mapping[str, Any],
    reports: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    plan = verify_plan(plan)
    by_role = {str(report["objective_role"]): report for report in reports}
    if set(by_role) != set(OBJECTIVE_ROLES) or len(by_role) != len(reports):
        raise ValueError("v20 combined report requires exactly Estimation and Validation")
    for role, report in by_role.items():
        _replay_hash(report, field="report_hash", prefix=REPORT_HASH_PREFIX)
        if report.get("plan_hash") != plan["plan_hash"] or report.get("objective_role") != role:
            raise ValueError("v20 role report identity differs")
        if report.get("authorization_objective_access") != "forbidden":
            raise ValueError("v20 role report opened Authorization")
    direct_sign_agreements = []
    validation_direct = {
        str(row["coordinate_ids"][0]): row
        for row in by_role["validation"]["direct_coordinate_rows"]
    }
    for row in by_role["estimation"]["direct_coordinate_rows"]:
        coordinate_id = str(row["coordinate_ids"][0])
        other = validation_direct[coordinate_id]
        left = float(row["mean_linear_slope"])
        right = float(other["mean_linear_slope"])
        direct_sign_agreements.append(float(left != 0 and right != 0 and (left > 0) == (right > 0)))
    cross_role_direct_sign_agreement = statistics.fmean(direct_sign_agreements)
    cross_role_gate = cross_role_direct_sign_agreement >= float(
        plan["study_thresholds"]["minimum_anchor_identifiable_rate"]
    )
    role_gates = all(report.get("status") == "passed" for report in by_role.values())
    passed = role_gates and cross_role_gate
    combined: dict[str, Any] = {
        "experiment_version": IDENTIFIABILITY_STUDY_VERSION,
        "artifact_type": "FiniteTargetIdentifiabilityCombinedReport",
        "plan_hash": plan["plan_hash"],
        "role_report_hashes": {
            role: report["report_hash"] for role, report in sorted(by_role.items())
        },
        "role_statuses": {role: report["status"] for role, report in sorted(by_role.items())},
        "gates": {
            "role_identifiability_gate": role_gates,
            "cross_role_direct_sign_agreement_gate": cross_role_gate,
        },
        "cross_role_direct_sign_agreement": cross_role_direct_sign_agreement,
        "minimum_cross_role_direct_sign_agreement": plan["study_thresholds"][
            "minimum_anchor_identifiable_rate"
        ],
        "authorization_objective_access": "forbidden",
        "authorization_objective_observation_count": 0,
        "status": "passed" if passed else "failed",
        "gp_c_evaluated": False,
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
        "next_transition": (plan["success_transition"] if passed else plan["failure_transition"]),
        "claim_boundary": plan["claim_boundary"],
    }
    combined["report_hash"] = canonical_hash(
        combined,
        prefix=COMBINED_REPORT_HASH_PREFIX,
    )
    return combined


def _prepare(args: argparse.Namespace) -> None:
    contract = _read_json(Path(args.contract).resolve())
    gradient_dir = Path(args.gradient_dir).resolve()
    plan = build_plan(
        contract=contract,
        gradient_plan=_read_json(gradient_dir / "plan.json"),
        gradient_report=_read_json(gradient_dir / "report.json"),
    )
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if (output_dir / "plan.json").exists():
        raise ValueError("v20 identifiability plan is immutable and already exists")
    _write_json(output_dir / "plan.json", plan)
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))


def _freeze(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = verify_plan(_read_json(output_dir / "plan.json"))
    direction_manifest, scale_manifest = freeze_directions_and_scales(
        plan,
        _read_json(Path(args.local_update_manifest).resolve()),
        output_dir=Path(args.direction_dir).resolve(),
    )
    print(
        json.dumps(
            {
                "direction_manifest_hash": direction_manifest["manifest_hash"],
                "direction_scale_manifest_hash": scale_manifest["manifest_hash"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


def _execute(args: argparse.Namespace) -> None:
    report = execute(
        output_dir=Path(args.output_dir).resolve(),
        direction_dir=Path(args.direction_dir).resolve(),
        objective_role=args.objective_role,
        gpu_ids=tuple(args.gpu_ids),
        partition_index=args.partition_index,
        partition_count=args.partition_count,
        numeric_seed=args.numeric_seed,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _aggregate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = verify_plan(_read_json(output_dir / "plan.json"))
    direction_dir = Path(args.direction_dir).resolve()
    direction_manifest = _read_json(direction_dir / "direction_manifest.json")
    scale_manifest = _read_json(direction_dir / "direction_scale_manifest.json")
    observations = [
        row
        for path in sorted((output_dir / "workers" / args.objective_role).glob("partition_*.jsonl"))
        for row in _load_jsonl(path)
    ]
    report = analyze_role(
        plan,
        direction_manifest,
        scale_manifest,
        observations,
        objective_role=args.objective_role,
    )
    _write_json(output_dir / f"{args.objective_role}_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _combine(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = verify_plan(_read_json(output_dir / "plan.json"))
    reports = tuple(_read_json(output_dir / f"{role}_report.json") for role in OBJECTIVE_ROLES)
    report = combine_reports(plan, reports)
    _write_json(output_dir / "combined_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the v20 finite-target identifiability study")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--contract", required=True)
    prepare.add_argument("--gradient-dir", required=True)
    prepare.add_argument("--output-dir", required=True)
    prepare.set_defaults(handler=_prepare)
    freeze = subparsers.add_parser("freeze-directions")
    freeze.add_argument("--output-dir", required=True)
    freeze.add_argument("--local-update-manifest", required=True)
    freeze.add_argument("--direction-dir", required=True)
    freeze.set_defaults(handler=_freeze)
    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("--output-dir", required=True)
    execute_parser.add_argument("--direction-dir", required=True)
    execute_parser.add_argument("--objective-role", choices=OBJECTIVE_ROLES, required=True)
    execute_parser.add_argument("--gpu-ids", type=int, nargs="+", required=True)
    execute_parser.add_argument("--partition-index", type=int, default=0)
    execute_parser.add_argument("--partition-count", type=int, default=1)
    execute_parser.add_argument("--numeric-seed", type=int, default=20261201)
    execute_parser.set_defaults(handler=_execute)
    aggregate = subparsers.add_parser("aggregate")
    aggregate.add_argument("--output-dir", required=True)
    aggregate.add_argument("--direction-dir", required=True)
    aggregate.add_argument("--objective-role", choices=OBJECTIVE_ROLES, required=True)
    aggregate.set_defaults(handler=_aggregate)
    combine = subparsers.add_parser("combine")
    combine.add_argument("--output-dir", required=True)
    combine.set_defaults(handler=_combine)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
