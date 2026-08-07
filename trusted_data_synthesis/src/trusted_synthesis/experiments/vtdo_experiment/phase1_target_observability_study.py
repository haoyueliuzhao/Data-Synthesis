from __future__ import annotations

import argparse
import gc
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
    TARGET_OBSERVABILITY_ROLE,
    _adapter_tensor_sha256,
    _configure_numeric_policy,
    _evaluate_records_numeric_detailed,
    _load_execution_model,
    _load_records,
    _load_tokenizer,
    _load_verified_gradient,
    _seed_everything,
    _sha256,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_gp_c_proxy import (
    _apply_descent_vector,
    _linear_combination,
    _restore_adapter,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_target_local_updates import (
    _verify_plan as verify_gradient_plan,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_target_observability import (
    DIRECT_COORDINATE_COUNT,
    MINIMUM_PRACTICAL_EFFECT,
    OBJECTIVE_MICRO_SPLIT_COUNT,
    OBJECTIVE_RECORDS_PER_MICRO_SPLIT,
    OBJECTIVE_RECORDS_PER_ROLE,
    OBJECTIVE_ROLES,
    PRIMARY_STEP_RATIO,
    STEP_RATIO_LADDER,
    classify_effect,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_target_observability_contract import (
    REQUIRED_TASK_TYPES,
    verify_observability_contract,
)
from trusted_synthesis.hashing import canonical_hash

TARGET_OBSERVABILITY_STUDY_VERSION = "finance_target_observability_study.v21"
PLAN_HASH_PREFIX = "finance_target_observability_study_plan:"
DESIGN_ROW_HASH_PREFIX = "finance_target_observability_design_row:"
MICRO_SPLIT_HASH_PREFIX = "finance_target_observability_micro_split:"
DIRECTION_MANIFEST_HASH_PREFIX = "finance_target_observability_direction_manifest:"
SCALE_MANIFEST_HASH_PREFIX = "finance_target_observability_scale_manifest:"
OBSERVATION_HASH_PREFIX = "finance_target_observability_observation:"
BASELINE_CHECKPOINT_HASH_PREFIX = "finance_target_observability_baseline_checkpoint:"
ROLE_REPORT_HASH_PREFIX = "finance_target_observability_role_report:"
COMBINED_REPORT_HASH_PREFIX = "finance_target_observability_combined_report:"
EXPECTED_TASK_COUNT = 6
EXPECTED_STATE_COUNT = 20
EXPECTED_REALIZATION_COUNT = 60
MAXIMUM_PARAMETER_STEP_RATIO_RELATIVE_ERROR = 5e-5
MAXIMUM_NULL_OBJECTIVE_DELTA = 1e-10
NUMERIC_SEED = 20262101


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"v21 study artifact is not an object:{path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_jsonl(path: Path, values: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(dict(value), ensure_ascii=False, sort_keys=True) + "\n" for value in values
        ),
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as sink:
        sink.write(json.dumps(dict(value), ensure_ascii=False, sort_keys=True) + "\n")
        sink.flush()
        os.fsync(sink.fileno())


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


def _validate_probabilities(values: Mapping[str, Any]) -> dict[str, float]:
    probabilities = {str(key): float(value) for key, value in sorted(values.items())}
    if not 3 <= len(probabilities) <= 5:
        raise ValueError("v21 study requires complete 3-5-state support")
    if any(value <= 0 or not math.isfinite(value) for value in probabilities.values()):
        raise ValueError("v21 state probabilities must be positive and finite")
    if not math.isclose(
        sum(probabilities.values()),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("v21 state probabilities must sum to one")
    return probabilities


def _coordinate_rows(
    task_distributions: Mapping[str, Mapping[str, float]],
    task_marginals: Mapping[str, float],
) -> tuple[dict[str, Any], ...]:
    if set(task_distributions) != set(task_marginals):
        raise ValueError("v21 task marginals do not cover every task distribution")
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
                prefix="finance_target_observability_coordinate:",
            )
            rows.append(row)
    return tuple(rows)


def _materialize_objective_role_files(
    gradient_plan: Mapping[str, Any],
    *,
    output_dir: Path,
) -> dict[str, dict[str, Any]]:
    source_path = Path(str(gradient_plan["source_records_path"])).resolve()
    if not source_path.is_file() or _sha256(source_path) != gradient_plan.get(
        "source_records_sha256"
    ):
        raise ValueError("v21 Objective source changed before role isolation")
    source_rows = _load_jsonl(source_path)
    by_id = {str(row["record_id"]): row for row in source_rows}
    if len(by_id) != len(source_rows):
        raise ValueError("v21 Objective source contains duplicate records")
    role_fields = {
        "estimation": "gradient_estimation_record_ids",
        "validation": "gradient_validation_record_ids",
    }
    authorization_ids = {str(value) for value in gradient_plan["final_test_record_ids"]}
    manifests: dict[str, dict[str, Any]] = {}
    role_dir = output_dir / "objective_roles"
    for role, field in role_fields.items():
        ids = tuple(str(value) for value in gradient_plan[field])
        if (
            len(ids) != OBJECTIVE_RECORDS_PER_ROLE
            or len(set(ids)) != len(ids)
            or set(ids) & authorization_ids
            or any(record_id not in by_id for record_id in ids)
        ):
            raise ValueError(f"v21 {role} Objective role cannot be isolated")
        path = role_dir / f"{role}.jsonl"
        if path.exists():
            raise ValueError("v21 Objective role file is immutable")
        _write_jsonl(path, tuple(by_id[record_id] for record_id in ids))
        manifests[role] = {
            "path": str(path.resolve()),
            "sha256": _sha256(path),
            "record_count": len(ids),
            "record_ids": ids,
            "authorization_record_count": 0,
        }
    if set(manifests["estimation"]["record_ids"]) & set(manifests["validation"]["record_ids"]):
        raise ValueError("v21 isolated Objective role files overlap")
    return manifests


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
            raise ValueError("v21 target contains a duplicate required task type")
        type_to_task[task_type] = task_id
    if set(type_to_task) != set(REQUIRED_TASK_TYPES):
        raise ValueError("v21 target task-type support differs from the contract")
    selected = [sorted(by_task[type_to_task[task_type]])[0] for task_type in REQUIRED_TASK_TYPES]
    largest_task = max(by_task, key=lambda task_id: (len(by_task[task_id]), task_id))
    extra = next(
        (value for value in sorted(by_task[largest_task]) if value not in selected),
        None,
    )
    if extra is None:
        raise ValueError("v21 target lacks the preregistered seventh coordinate")
    selected.append(extra)
    if len(selected) != DIRECT_COORDINATE_COUNT or len(set(selected)) != len(selected):
        raise ValueError("v21 Direct Coordinate support must contain seven identities")
    return tuple(selected)


def _design_rows(coordinate_ids: Sequence[str]) -> tuple[dict[str, Any], ...]:
    direct = tuple(sorted(str(value) for value in coordinate_ids))
    if len(direct) != DIRECT_COORDINATE_COUNT or len(set(direct)) != len(direct):
        raise ValueError("v21 study requires seven unique Direct Coordinates")
    rows = []
    for index, coordinate_id in enumerate(direct):
        row: dict[str, Any] = {
            "role": "direct_coordinate",
            "row_index": index,
            "coordinate_ids": (coordinate_id,),
            "coordinate_weights": {coordinate_id: 1.0},
        }
        row["design_row_id"] = canonical_hash(row, prefix=DESIGN_ROW_HASH_PREFIX)
        rows.append(row)
    null: dict[str, Any] = {
        "role": "null_replay",
        "row_index": len(rows),
        "coordinate_ids": (),
        "coordinate_weights": {},
    }
    null["design_row_id"] = canonical_hash(null, prefix=DESIGN_ROW_HASH_PREFIX)
    rows.append(null)
    return tuple(rows)


def _micro_splits(
    record_ids: Sequence[str],
    *,
    role: str,
    contract_hash: str,
) -> tuple[dict[str, Any], ...]:
    values = tuple(str(value) for value in record_ids)
    if len(values) != OBJECTIVE_RECORDS_PER_ROLE or len(set(values)) != len(values):
        raise ValueError("v21 Objective role must contain 128 unique records")
    ordered = sorted(
        values,
        key=lambda record_id: canonical_hash(
            {
                "contract_hash": contract_hash,
                "objective_role": role,
                "record_id": record_id,
            },
            prefix="finance_target_observability_micro_split_order:",
        ),
    )
    buckets = [
        ordered[index::OBJECTIVE_MICRO_SPLIT_COUNT] for index in range(OBJECTIVE_MICRO_SPLIT_COUNT)
    ]
    rows = []
    for index, bucket in enumerate(buckets):
        if len(bucket) != OBJECTIVE_RECORDS_PER_MICRO_SPLIT:
            raise ValueError("v21 Objective micro-split size differs")
        row: dict[str, Any] = {
            "micro_split_index": index,
            "record_ids": tuple(bucket),
        }
        row["micro_split_id"] = canonical_hash(
            {"objective_role": role, **row},
            prefix=MICRO_SPLIT_HASH_PREFIX,
        )
        rows.append(row)
    if set().union(*(set(row["record_ids"]) for row in rows)) != set(values):
        raise ValueError("v21 Objective micro-splits do not exactly partition the role")
    return tuple(rows)


def _verify_local_artifacts(
    report: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    gradient_plan: Mapping[str, Any],
) -> None:
    _replay_hash(
        report,
        field="report_hash",
        prefix="finance_target_local_update_report:",
        label="v21 local update report",
    )
    _replay_hash(
        manifest,
        field="manifest_hash",
        prefix="finance_target_local_update_manifest:",
        label="v21 local update manifest",
    )
    if (
        report.get("status") != "passed"
        or report.get("plan_hash") != gradient_plan["plan_hash"]
        or report.get("local_update_manifest_hash") != manifest.get("manifest_hash")
        or manifest.get("source_gradient_plan_hash") != gradient_plan["plan_hash"]
        or int(report.get("task_count", 0)) != EXPECTED_TASK_COUNT
        or int(report.get("state_count", 0)) != EXPECTED_STATE_COUNT
        or int(report.get("realization_count", 0)) != EXPECTED_REALIZATION_COUNT
    ):
        raise ValueError("v21 local update support differs from the sealed study")
    for artifact in (report, manifest):
        if (
            artifact.get("authorization_objective_access") != "forbidden"
            or artifact.get("objective_record_access") != "none"
            or artifact.get("gp_c_evaluated") is not False
            or artifact.get("contribution_approximation_authorized") is not False
        ):
            raise ValueError("v21 local update artifact opened a forbidden path")


def build_plan(
    *,
    contract: Mapping[str, Any],
    gradient_plan: Mapping[str, Any],
    local_update_report: Mapping[str, Any],
    local_update_manifest: Mapping[str, Any],
    objective_role_files: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    frozen_contract = verify_observability_contract(contract)
    frozen_gradient, _ = verify_gradient_plan(dict(gradient_plan))
    if frozen_gradient.get("numeric_contract_hash") != frozen_contract["contract_hash"]:
        raise ValueError("v21 Gradient plan uses another observability contract")
    _verify_local_artifacts(
        local_update_report,
        local_update_manifest,
        gradient_plan=frozen_gradient,
    )
    task_ids = tuple(sorted(str(value) for value in frozen_contract["task_ids"]))
    if set(task_ids) != set(str(value) for value in frozen_gradient["selected_task_ids"]):
        raise ValueError("v21 Gradient plan targets another task population")
    task_type_by_task_id = {
        str(row["task_id"]): str(row["task_type"]) for row in frozen_gradient["jobs"]
    }
    if set(task_type_by_task_id.values()) != set(REQUIRED_TASK_TYPES):
        raise ValueError("v21 Gradient task-type support differs")
    task_distributions = {
        str(task_id): _validate_probabilities(value["probabilities"])
        for task_id, value in frozen_gradient["task_distributions"].items()
    }
    task_marginals = {
        str(key): float(value) for key, value in local_update_manifest["task_marginals"].items()
    }
    if set(task_distributions) != set(task_ids) or set(task_marginals) != set(task_ids):
        raise ValueError("v21 task distribution identity differs")
    coordinates = _coordinate_rows(task_distributions, task_marginals)
    direct_ids = _select_direct_coordinates(coordinates, task_type_by_task_id)
    designs = _design_rows(direct_ids)
    role_ids = {
        "estimation": tuple(
            str(value) for value in frozen_gradient["gradient_estimation_record_ids"]
        ),
        "validation": tuple(
            str(value) for value in frozen_gradient["gradient_validation_record_ids"]
        ),
        "authorization": tuple(str(value) for value in frozen_gradient["final_test_record_ids"]),
    }
    source_partitions = frozen_contract["source_support"]["objective_partition_ids"]
    if any(role_ids[key] != tuple(source_partitions[key]) for key in role_ids):
        raise ValueError("v21 Objective partitions differ from the sealed contract")
    if any(
        set(role_ids[left]) & set(role_ids[right])
        for left, right in (
            ("estimation", "validation"),
            ("estimation", "authorization"),
            ("validation", "authorization"),
        )
    ):
        raise ValueError("v21 Objective partitions overlap")
    if set(objective_role_files) != set(OBJECTIVE_ROLES):
        raise ValueError("v21 Objective role files are incomplete")
    for role in OBJECTIVE_ROLES:
        manifest = objective_role_files[role]
        if (
            tuple(str(value) for value in manifest.get("record_ids", ())) != role_ids[role]
            or int(manifest.get("record_count", 0)) != OBJECTIVE_RECORDS_PER_ROLE
            or int(manifest.get("authorization_record_count", -1)) != 0
        ):
            raise ValueError(f"v21 {role} Objective role file differs")
    splits = {
        role: _micro_splits(
            role_ids[role],
            role=role,
            contract_hash=str(frozen_contract["contract_hash"]),
        )
        for role in OBJECTIVE_ROLES
    }
    values: dict[str, Any] = {
        "experiment_version": TARGET_OBSERVABILITY_STUDY_VERSION,
        "artifact_type": "DirectTargetObservabilityPlan",
        "run_role": TARGET_OBSERVABILITY_ROLE,
        "contract_hash": frozen_contract["contract_hash"],
        "source_gradient_plan_hash": frozen_gradient["plan_hash"],
        "source_local_update_report_hash": local_update_report["report_hash"],
        "source_local_update_manifest_hash": local_update_manifest["manifest_hash"],
        "beneficiary_model_state_id": frozen_gradient["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": frozen_gradient["beneficiary_checkpoint_hash"],
        "model_dir": frozen_gradient["model_dir"],
        "base_model_manifest_hash": frozen_gradient["base_model_manifest_hash"],
        "beneficiary_adapter_dir": frozen_gradient["beneficiary_adapter_dir"],
        "beneficiary_adapter_tensor_sha256": frozen_gradient["beneficiary_adapter_tensor_sha256"],
        "source_records_path": frozen_gradient["source_records_path"],
        "source_records_sha256": frozen_gradient["source_records_sha256"],
        "objective_role_files": {
            role: dict(objective_role_files[role]) for role in OBJECTIVE_ROLES
        },
        "numeric_profile": frozen_contract["selected_profile"],
        "profile_algorithm_contract": frozen_contract["profile_algorithm_contract"],
        "task_ids": task_ids,
        "task_type_by_task_id": dict(sorted(task_type_by_task_id.items())),
        "task_distributions": task_distributions,
        "task_marginals": task_marginals,
        "coordinate_rows": coordinates,
        "direct_coordinate_ids": direct_ids,
        "design_rows": designs,
        "step_ratio_ladder": list(STEP_RATIO_LADDER),
        "primary_step_ratio": PRIMARY_STEP_RATIO,
        "objective_micro_splits": splits,
        "sealed_authorization_partition": {
            "record_ids": role_ids["authorization"],
            "set_id": canonical_hash(
                role_ids["authorization"],
                prefix="finance_target_observability_sealed_authorization:",
            ),
            "objective_access": "forbidden",
        },
        "minimum_practical_effect": MINIMUM_PRACTICAL_EFFECT,
        "maximum_parameter_step_ratio_relative_error": MAXIMUM_PARAMETER_STEP_RATIO_RELATIVE_ERROR,
        "maximum_null_objective_delta": MAXIMUM_NULL_OBJECTIVE_DELTA,
        "radius_agreement_policy": frozen_contract["radius_agreement_policy"],
        "effect_resolution_policy": frozen_contract["effect_resolution_policy"],
        "design_policy": "direct_coordinates_only",
        "allowed_objective_roles": list(OBJECTIVE_ROLES),
        "authorization_objective_access": "forbidden",
        "objective_gradient_access": "none",
        "gp_c_evaluated": False,
        "gp_c_execution_allowed": False,
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
        "success_transition": "freeze_independent_gp_c_comparison_protocol",
        "failure_transition": "retain_contribution_zero_and_report_target_unobservability",
        "claim_boundary": (
            "This Direct-only plan tests target observability. It reads no Objective gradient, "
            "does not evaluate GP-C, cannot open Authorization, and cannot authorize Contribution."
        ),
    }
    values["plan_hash"] = canonical_hash(values, prefix=PLAN_HASH_PREFIX)
    return verify_plan(values)


def verify_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    frozen = dict(plan)
    _replay_hash(frozen, field="plan_hash", prefix=PLAN_HASH_PREFIX, label="v21 study plan")
    if frozen.get("experiment_version") != TARGET_OBSERVABILITY_STUDY_VERSION:
        raise ValueError("v21 study version differs")
    if frozen.get("run_role") != TARGET_OBSERVABILITY_ROLE:
        raise ValueError("v21 study role differs")
    if frozen.get("design_policy") != "direct_coordinates_only":
        raise ValueError("v21 study contains an unregistered design")
    if frozen.get("step_ratio_ladder") != list(STEP_RATIO_LADDER):
        raise ValueError("v21 step-ratio ladder differs")
    if float(frozen.get("primary_step_ratio", 0)) != PRIMARY_STEP_RATIO:
        raise ValueError("v21 primary step ratio differs")
    task_ids = {str(value) for value in frozen.get("task_ids", ())}
    raw_distributions = frozen.get("task_distributions")
    raw_marginals = frozen.get("task_marginals")
    task_types = frozen.get("task_type_by_task_id")
    if (
        len(task_ids) != EXPECTED_TASK_COUNT
        or not isinstance(raw_distributions, dict)
        or not isinstance(raw_marginals, dict)
        or not isinstance(task_types, dict)
        or task_ids != set(str(value) for value in raw_distributions)
        or task_ids != set(str(value) for value in raw_marginals)
        or task_ids != set(str(value) for value in task_types)
        or set(str(value) for value in task_types.values()) != set(REQUIRED_TASK_TYPES)
    ):
        raise ValueError("v21 task distribution identity differs")
    task_distributions = {
        str(task_id): _validate_probabilities(values)
        for task_id, values in raw_distributions.items()
    }
    task_marginals = {str(task_id): float(value) for task_id, value in raw_marginals.items()}
    if any(
        value <= 0 or not math.isfinite(value) for value in task_marginals.values()
    ) or not math.isclose(
        sum(task_marginals.values()),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("v21 task marginals are invalid")
    expected_coordinates = _coordinate_rows(task_distributions, task_marginals)
    if len(frozen.get("coordinate_rows", ())) != 14 or canonical_hash(
        frozen["coordinate_rows"]
    ) != canonical_hash(expected_coordinates):
        raise ValueError("v21 quotient coordinate support differs")
    direct_ids = tuple(str(value) for value in frozen.get("direct_coordinate_ids", ()))
    expected_direct_ids = _select_direct_coordinates(expected_coordinates, task_types)
    if (
        direct_ids != expected_direct_ids
        or len(direct_ids) != DIRECT_COORDINATE_COUNT
        or len(set(direct_ids)) != len(direct_ids)
    ):
        raise ValueError("v21 Direct Coordinate support differs")
    if canonical_hash(frozen.get("design_rows")) != canonical_hash(_design_rows(direct_ids)):
        raise ValueError("v21 design rows differ")
    splits = frozen.get("objective_micro_splits")
    if not isinstance(splits, dict) or set(splits) != set(OBJECTIVE_ROLES):
        raise ValueError("v21 Objective micro-split roles differ")
    for role in OBJECTIVE_ROLES:
        rows = splits[role]
        if len(rows) != OBJECTIVE_MICRO_SPLIT_COUNT:
            raise ValueError("v21 Objective micro-split count differs")
        ids = [str(record_id) for row in rows for record_id in row["record_ids"]]
        if len(ids) != OBJECTIVE_RECORDS_PER_ROLE or len(set(ids)) != len(ids):
            raise ValueError("v21 Objective micro-split support is invalid")
        if canonical_hash(rows) != canonical_hash(
            _micro_splits(ids, role=role, contract_hash=str(frozen["contract_hash"]))
        ):
            raise ValueError("v21 Objective micro-split registry differs")
    role_files = frozen.get("objective_role_files")
    if not isinstance(role_files, dict) or set(role_files) != set(OBJECTIVE_ROLES):
        raise ValueError("v21 Objective role files differ")
    for role in OBJECTIVE_ROLES:
        manifest = role_files[role]
        path = Path(str(manifest.get("path", ""))).resolve()
        if (
            not path.is_file()
            or _sha256(path) != manifest.get("sha256")
            or int(manifest.get("record_count", 0)) != OBJECTIVE_RECORDS_PER_ROLE
            or int(manifest.get("authorization_record_count", -1)) != 0
        ):
            raise ValueError(f"v21 {role} Objective role file changed")
        rows = _load_jsonl(path)
        role_file_ids = tuple(str(row["record_id"]) for row in rows)
        expected_ids = tuple(str(value) for value in manifest.get("record_ids", ()))
        split_ids = tuple(
            str(record_id) for split in splits[role] for record_id in split["record_ids"]
        )
        if (
            role_file_ids != expected_ids
            or set(role_file_ids) != set(split_ids)
            or len(role_file_ids) != OBJECTIVE_RECORDS_PER_ROLE
        ):
            raise ValueError(f"v21 {role} Objective role file content differs")
    sealed = frozen.get("sealed_authorization_partition")
    if (
        not isinstance(sealed, dict)
        or len(set(sealed.get("record_ids", ()))) != OBJECTIVE_RECORDS_PER_ROLE
    ):
        raise ValueError("v21 sealed Authorization support differs")
    expected_sealed_id = canonical_hash(
        tuple(str(value) for value in sealed["record_ids"]),
        prefix="finance_target_observability_sealed_authorization:",
    )
    if sealed.get("objective_access") != "forbidden" or sealed.get("set_id") != expected_sealed_id:
        raise ValueError("v21 sealed Authorization identity differs")
    objective_ids = {
        role: {str(record_id) for row in splits[role] for record_id in row["record_ids"]}
        for role in OBJECTIVE_ROLES
    }
    authorization_ids = {str(value) for value in sealed["record_ids"]}
    if objective_ids["estimation"] & objective_ids["validation"] or any(
        values & authorization_ids for values in objective_ids.values()
    ):
        raise ValueError("v21 Objective partitions overlap")
    for field, expected in {
        "authorization_objective_access": "forbidden",
        "objective_gradient_access": "none",
        "gp_c_evaluated": False,
        "gp_c_execution_allowed": False,
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
    }.items():
        if frozen.get(field) != expected:
            raise ValueError(f"v21 study opened a forbidden path:{field}")
    if float(frozen.get("minimum_practical_effect", 0)) != MINIMUM_PRACTICAL_EFFECT or frozen.get(
        "allowed_objective_roles"
    ) != list(OBJECTIVE_ROLES):
        raise ValueError("v21 statistical contract differs")
    if (
        float(frozen.get("maximum_parameter_step_ratio_relative_error", math.nan))
        != MAXIMUM_PARAMETER_STEP_RATIO_RELATIVE_ERROR
        or float(frozen.get("maximum_null_objective_delta", math.nan))
        != MAXIMUM_NULL_OBJECTIVE_DELTA
        or frozen.get("radius_agreement_policy")
        != {
            "maximum_absolute_slope_difference": MINIMUM_PRACTICAL_EFFECT,
            "require_resolution_agreement": True,
        }
        or frozen.get("effect_resolution_policy")
        != {
            "meaningful": "ci_excludes_zero_and_absolute_mean_at_least_mpe",
            "equivalent": "ci_fully_contained_within_plus_or_minus_mpe",
            "inconclusive": "neither_meaningful_nor_equivalent",
            "required_role_resolved_rate": 1.0,
            "required_cross_role_resolution_agreement": 1.0,
        }
        or frozen.get("success_transition")
        != "freeze_independent_gp_c_comparison_protocol"
        or frozen.get("failure_transition")
        != "retain_contribution_zero_and_report_target_unobservability"
    ):
        raise ValueError("v21 target-observability gate contract differs")
    return frozen


def freeze_directions(
    plan: Mapping[str, Any],
    local_update_manifest: Mapping[str, Any],
    *,
    output_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from safetensors.torch import save_file

    frozen = verify_plan(plan)
    if (
        local_update_manifest.get("manifest_hash") != frozen["source_local_update_manifest_hash"]
        or local_update_manifest.get("source_gradient_plan_hash")
        != frozen["source_gradient_plan_hash"]
        or local_update_manifest.get("objective_record_access") != "none"
        or local_update_manifest.get("authorization_objective_access") != "forbidden"
        or local_update_manifest.get("gp_c_evaluated") is not False
    ):
        raise ValueError("v21 direction source opened a forbidden path or changed identity")
    state_updates = {
        (str(row["task_id"]), str(row["state_id"])): _load_verified_gradient(
            Path(str(row["file"])),
            str(row["sha256"]),
        )
        for row in local_update_manifest["state_artifacts"]
    }
    if len(state_updates) != EXPECTED_STATE_COUNT:
        raise ValueError("v21 direction source lacks a state update")
    coordinates = {}
    for row in frozen["coordinate_rows"]:
        task_id = str(row["task_id"])
        state_id = str(row["state_id"])
        reference_id = str(row["reference_state_id"])
        marginal = float(row["task_marginal"])
        coordinates[str(row["coordinate_id"])] = _linear_combination(
            [state_updates[(task_id, state_id)], state_updates[(task_id, reference_id)]],
            [0.5 * marginal, -0.5 * marginal],
        )
    global_artifact = local_update_manifest["global_update_artifact"]
    global_update = _load_verified_gradient(
        Path(str(global_artifact["file"])),
        str(global_artifact["sha256"]),
    )
    zero = {name: value.new_zeros(value.shape) for name, value in global_update.items()}
    direction_dir = output_dir / "direct_directions"
    direction_dir.mkdir(parents=True, exist_ok=True)
    artifacts = []
    for index, design in enumerate(frozen["design_rows"]):
        if design["role"] == "null_replay":
            direction = zero
        else:
            coordinate_id = str(design["coordinate_ids"][0])
            direction = coordinates[coordinate_id]
        path = direction_dir / f"direction_{index:02d}.safetensors"
        save_file(direction, path)
        norm = math.sqrt(sum(float((value.double() ** 2).sum()) for value in direction.values()))
        if design["role"] != "null_replay" and norm <= 0:
            raise ValueError("v21 non-null Direct Coordinate has zero norm")
        artifacts.append(
            {
                "design_row_id": design["design_row_id"],
                "role": design["role"],
                "file": str(path),
                "sha256": _sha256(path),
                "direction_norm": norm,
            }
        )
    direction_manifest: dict[str, Any] = {
        "experiment_version": TARGET_OBSERVABILITY_STUDY_VERSION,
        "artifact_type": "DirectTargetDirectionManifest",
        "plan_hash": frozen["plan_hash"],
        "source_gradient_plan_hash": frozen["source_gradient_plan_hash"],
        "local_update_manifest_hash": local_update_manifest["manifest_hash"],
        "global_update_artifact": global_artifact,
        "direction_artifacts": tuple(artifacts),
        "coordinate_direction_count": len(coordinates),
        "authorization_objective_access": "forbidden",
        "objective_record_access": "none",
        "gp_c_evaluated": False,
    }
    direction_manifest["manifest_hash"] = canonical_hash(
        direction_manifest,
        prefix=DIRECTION_MANIFEST_HASH_PREFIX,
    )
    scale_rows = []
    by_id = {str(row["design_row_id"]): row for row in artifacts}
    for design in frozen["design_rows"]:
        row_id = str(design["design_row_id"])
        norm = float(by_id[row_id]["direction_norm"])
        for ratio in STEP_RATIO_LADDER:
            scale_rows.append(
                {
                    "design_row_id": row_id,
                    "target_parameter_step_ratio": ratio,
                    "direction_norm": norm,
                    "coefficient_per_actual_global_step_norm": (
                        0.0 if design["role"] == "null_replay" else ratio / norm
                    ),
                }
            )
    scale_manifest: dict[str, Any] = {
        "experiment_version": TARGET_OBSERVABILITY_STUDY_VERSION,
        "artifact_type": "DirectTargetDirectionScaleManifest",
        "plan_hash": frozen["plan_hash"],
        "direction_manifest_hash": direction_manifest["manifest_hash"],
        "local_update_manifest_hash": local_update_manifest["manifest_hash"],
        "global_update_artifact": global_artifact,
        "normalization": "coefficient_times_measured_actual_global_parameter_step_norm",
        "scale_rows": tuple(scale_rows),
        "authorization_objective_access": "forbidden",
        "objective_record_access": "none",
        "gp_c_evaluated": False,
    }
    scale_manifest["manifest_hash"] = canonical_hash(
        scale_manifest,
        prefix=SCALE_MANIFEST_HASH_PREFIX,
    )
    _write_json(output_dir / "direction_manifest.json", direction_manifest)
    _write_json(output_dir / "direction_scale_manifest.json", scale_manifest)
    return direction_manifest, scale_manifest


def _verify_direction_manifests(
    plan: Mapping[str, Any],
    direction_manifest: Mapping[str, Any],
    scale_manifest: Mapping[str, Any],
) -> None:
    _replay_hash(
        direction_manifest,
        field="manifest_hash",
        prefix=DIRECTION_MANIFEST_HASH_PREFIX,
        label="v21 direction manifest",
    )
    _replay_hash(
        scale_manifest,
        field="manifest_hash",
        prefix=SCALE_MANIFEST_HASH_PREFIX,
        label="v21 direction scale manifest",
    )
    if (
        direction_manifest.get("plan_hash") != plan["plan_hash"]
        or scale_manifest.get("plan_hash") != plan["plan_hash"]
        or scale_manifest.get("direction_manifest_hash") != direction_manifest.get("manifest_hash")
    ):
        raise ValueError("v21 direction artifacts belong to another plan")
    expected_ids = {str(row["design_row_id"]) for row in plan["design_rows"]}
    designs = {str(row["design_row_id"]): row for row in plan["design_rows"]}
    direction_rows = tuple(direction_manifest.get("direction_artifacts", ()))
    observed = [str(row["design_row_id"]) for row in direction_rows]
    if set(observed) != expected_ids or len(observed) != len(expected_ids):
        raise ValueError("v21 direction support is incomplete")
    direction_by_id = {str(row["design_row_id"]): row for row in direction_rows}
    for row_id, row in direction_by_id.items():
        path = Path(str(row.get("file", "")))
        norm = float(row.get("direction_norm", math.nan))
        role = str(designs[row_id]["role"])
        if (
            row.get("role") != role
            or not path.is_file()
            or _sha256(path) != row.get("sha256")
            or not math.isfinite(norm)
            or (role == "null_replay" and norm != 0.0)
            or (role != "null_replay" and norm <= 0.0)
        ):
            raise ValueError("v21 direction artifact content differs")
    scale_rows = tuple(scale_manifest.get("scale_rows", ()))
    expected_scale_keys = {
        (row_id, float(ratio)) for row_id in expected_ids for ratio in STEP_RATIO_LADDER
    }
    observed_scale_keys = [
        (str(row.get("design_row_id", "")), float(row.get("target_parameter_step_ratio", 0)))
        for row in scale_rows
    ]
    if (
        set(observed_scale_keys) != expected_scale_keys
        or len(observed_scale_keys) != len(expected_scale_keys)
    ):
        raise ValueError("v21 direction scale support is incomplete")
    for row in scale_rows:
        row_id = str(row["design_row_id"])
        ratio = float(row["target_parameter_step_ratio"])
        norm = float(row["direction_norm"])
        coefficient = float(row["coefficient_per_actual_global_step_norm"])
        expected_norm = float(direction_by_id[row_id]["direction_norm"])
        expected_coefficient = 0.0 if designs[row_id]["role"] == "null_replay" else ratio / norm
        if (
            not math.isclose(norm, expected_norm, rel_tol=0.0, abs_tol=1e-15)
            or not math.isclose(
                coefficient,
                expected_coefficient,
                rel_tol=0.0,
                abs_tol=1e-15,
            )
        ):
            raise ValueError("v21 direction scale content differs")
    if scale_manifest.get("global_update_artifact") != direction_manifest.get(
        "global_update_artifact"
    ):
        raise ValueError("v21 direction manifests disagree on the global update")
    for artifact in (direction_manifest, scale_manifest):
        if (
            artifact.get("authorization_objective_access") != "forbidden"
            or artifact.get("objective_record_access") != "none"
            or artifact.get("gp_c_evaluated") is not False
        ):
            raise ValueError("v21 direction artifact opened a forbidden path")


def _snapshot_trainable(model: Any) -> dict[str, Any]:
    values = {
        name: parameter.detach().float().clone()
        for name, parameter in sorted(model.named_parameters())
        if parameter.requires_grad
    }
    if not values:
        raise ValueError("v21 study found no trainable parameters")
    return values


def _parameter_distance(model: Any, reference: Mapping[str, Any]) -> float:
    total = 0.0
    parameters = {
        name: parameter
        for name, parameter in sorted(model.named_parameters())
        if parameter.requires_grad
    }
    if tuple(parameters) != tuple(reference):
        raise ValueError("v21 trainable parameter support changed")
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
        tokens = sum(int(row["supervised_tokens"]) for row in rows)
        if tokens <= 0:
            raise ValueError("v21 Objective micro-split has no supervised tokens")
        loss = (
            sum(
                float(row["negative_log_likelihood"]) * int(row["supervised_tokens"])
                for row in rows
            )
            / tokens
        )
        values.append(
            {
                "micro_split_id": split["micro_split_id"],
                "record_ids": split["record_ids"],
                "performance": -loss,
                "negative_log_likelihood": loss,
                "supervised_tokens": tokens,
            }
        )
    return tuple(values)


def _observation_hash(value: Mapping[str, Any]) -> str:
    payload = dict(value)
    payload.pop("observation_hash", None)
    return canonical_hash(payload, prefix=OBSERVATION_HASH_PREFIX)


def _baseline_checkpoint_hash(value: Mapping[str, Any]) -> str:
    payload = dict(value)
    payload.pop("checkpoint_hash", None)
    return canonical_hash(payload, prefix=BASELINE_CHECKPOINT_HASH_PREFIX)


def _verify_baseline_checkpoint(
    value: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
    direction_manifest: Mapping[str, Any],
    scale_manifest: Mapping[str, Any],
    objective_role: str,
    objective_role_file_sha256: str,
    micro_splits: Sequence[Mapping[str, Any]],
    post_global_adapter_hash: str,
    actual_global_step_norm: float,
    numeric_seed: int,
) -> dict[str, Any]:
    checkpoint = dict(value)
    if checkpoint.get("checkpoint_hash") != _baseline_checkpoint_hash(checkpoint):
        raise ValueError("v21 baseline checkpoint identity changed")
    expected = {
        "experiment_version": TARGET_OBSERVABILITY_STUDY_VERSION,
        "plan_hash": plan["plan_hash"],
        "direction_manifest_hash": direction_manifest["manifest_hash"],
        "direction_scale_manifest_hash": scale_manifest["manifest_hash"],
        "objective_role": objective_role,
        "objective_role_file_sha256": objective_role_file_sha256,
        "authorization_objective_access": "forbidden",
        "objective_gradient_access": "none",
        "gp_c_evaluated": False,
        "baseline_post_global_adapter_hash": post_global_adapter_hash,
        "numeric_seed": numeric_seed,
    }
    for field, expected_value in expected.items():
        if checkpoint.get(field) != expected_value:
            raise ValueError(f"v21 baseline checkpoint contract changed:{field}")
    expected_split_ids = tuple(str(row["micro_split_id"]) for row in micro_splits)
    baseline_micro = tuple(checkpoint.get("baseline_micro_split_results", ()))
    if tuple(str(row["micro_split_id"]) for row in baseline_micro) != expected_split_ids:
        raise ValueError("v21 baseline checkpoint micro-split support changed")
    prefix = f"finance_target_observability_{objective_role}_baseline_micro_splits:"
    if canonical_hash(baseline_micro, prefix=prefix) != checkpoint.get(
        "baseline_micro_split_manifest_hash"
    ):
        raise ValueError("v21 baseline checkpoint micro-split identity changed")
    tokens = sum(int(row["supervised_tokens"]) for row in baseline_micro)
    if tokens <= 0 or tokens != int(checkpoint.get("baseline_supervised_tokens", -1)):
        raise ValueError("v21 baseline checkpoint token support changed")
    loss = (
        sum(
            float(row["negative_log_likelihood"]) * int(row["supervised_tokens"])
            for row in baseline_micro
        )
        / tokens
    )
    if not math.isclose(
        loss,
        float(checkpoint.get("baseline_negative_log_likelihood", math.nan)),
        rel_tol=0.0,
        abs_tol=1e-10,
    ) or not math.isclose(
        -loss,
        float(checkpoint.get("baseline_objective_value", math.nan)),
        rel_tol=0.0,
        abs_tol=1e-10,
    ):
        raise ValueError("v21 baseline checkpoint Objective replay failed")
    if not math.isclose(
        float(checkpoint.get("actual_global_parameter_step_norm", math.nan)),
        actual_global_step_norm,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("v21 baseline checkpoint global step changed")
    return checkpoint


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

    if objective_role not in OBJECTIVE_ROLES:
        raise ValueError("v21 execution cannot open this Objective role")
    if len(gpu_ids) != 3 or len(set(gpu_ids)) != 3:
        raise ValueError("v21 execution requires one frozen three-GPU group")
    if any(value < 0 or value >= torch.cuda.device_count() for value in gpu_ids):
        raise ValueError("v21 execution GPU group is unavailable")
    if not 0 <= partition_index < partition_count:
        raise ValueError("v21 execution partition is invalid")
    if numeric_seed != NUMERIC_SEED:
        raise ValueError("v21 execution numeric seed differs from the frozen protocol")
    torch.cuda.set_device(gpu_ids[0])
    plan = verify_plan(_read_json(output_dir / "plan.json"))
    direction_manifest = _read_json(direction_dir / "direction_manifest.json")
    scale_manifest = _read_json(direction_dir / "direction_scale_manifest.json")
    _verify_direction_manifests(plan, direction_manifest, scale_manifest)
    role_file = plan["objective_role_files"][objective_role]
    records_path = Path(str(role_file["path"]))
    if not records_path.is_file() or _sha256(records_path) != role_file["sha256"]:
        raise ValueError("v21 isolated Objective role file changed after planning")
    records = _load_records(records_path)
    micro_splits = tuple(plan["objective_micro_splits"][objective_role])
    objective_ids = tuple(
        str(record_id) for split in micro_splits for record_id in split["record_ids"]
    )
    if len(objective_ids) != OBJECTIVE_RECORDS_PER_ROLE or any(
        record_id not in records for record_id in objective_ids
    ):
        raise ValueError("v21 Objective support is incomplete")
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
        for ratio in STEP_RATIO_LADDER
        for sign in (-1, 1)
    ]
    assigned = [job for index, job in enumerate(jobs) if index % partition_count == partition_index]
    worker_dir = output_dir / "workers" / objective_role
    worker_path = worker_dir / f"partition_{partition_index}.jsonl"
    existing = _load_jsonl(worker_path)
    completed = set()
    for row in existing:
        if (
            row.get("observation_hash") != _observation_hash(row)
            or row.get("plan_hash") != plan["plan_hash"]
            or row.get("objective_role") != objective_role
            or row.get("authorization_objective_access") != "forbidden"
            or row.get("objective_gradient_access") != "none"
            or row.get("gp_c_evaluated") is not False
        ):
            raise ValueError("v21 resume observation failed replay")
        completed.add(
            (
                str(row["design_row_id"]),
                float(row["target_parameter_step_ratio"]),
                int(row["sign"]),
            )
        )
    _seed_everything(numeric_seed)
    _configure_numeric_policy(plan["numeric_profile"])
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
        raise ValueError("v21 execution loaded another beneficiary Adapter")
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
        raise ValueError("v21 actual global parameter step is invalid")
    post_global_trainable = _snapshot_trainable(model)
    post_global_adapter_hash = _adapter_tensor_sha256(model)
    baseline_checkpoint_path = worker_dir / f"partition_{partition_index}_baseline.json"
    if baseline_checkpoint_path.is_file():
        baseline_checkpoint = _verify_baseline_checkpoint(
            _read_json(baseline_checkpoint_path),
            plan=plan,
            direction_manifest=direction_manifest,
            scale_manifest=scale_manifest,
            objective_role=objective_role,
            objective_role_file_sha256=str(role_file["sha256"]),
            micro_splits=micro_splits,
            post_global_adapter_hash=post_global_adapter_hash,
            actual_global_step_norm=actual_global_step_norm,
            numeric_seed=numeric_seed,
        )
    elif existing:
        first = existing[0]
        baseline_checkpoint = {
            "experiment_version": TARGET_OBSERVABILITY_STUDY_VERSION,
            "plan_hash": plan["plan_hash"],
            "direction_manifest_hash": direction_manifest["manifest_hash"],
            "direction_scale_manifest_hash": scale_manifest["manifest_hash"],
            "objective_role": objective_role,
            "objective_role_file_sha256": role_file["sha256"],
            "authorization_objective_access": "forbidden",
            "objective_gradient_access": "none",
            "gp_c_evaluated": False,
            "baseline_objective_value": first["baseline_objective_value"],
            "baseline_negative_log_likelihood": first["baseline_negative_log_likelihood"],
            "baseline_supervised_tokens": first["baseline_supervised_tokens"],
            "baseline_micro_split_results": first["baseline_micro_split_results"],
            "baseline_micro_split_manifest_hash": first[
                "baseline_micro_split_manifest_hash"
            ],
            "baseline_post_global_adapter_hash": first["baseline_post_global_adapter_hash"],
            "actual_global_parameter_step_norm": first[
                "actual_global_parameter_step_norm"
            ],
            "numeric_seed": first["numeric_seed"],
        }
        baseline_checkpoint["checkpoint_hash"] = _baseline_checkpoint_hash(
            baseline_checkpoint
        )
        baseline_checkpoint = _verify_baseline_checkpoint(
            baseline_checkpoint,
            plan=plan,
            direction_manifest=direction_manifest,
            scale_manifest=scale_manifest,
            objective_role=objective_role,
            objective_role_file_sha256=str(role_file["sha256"]),
            micro_splits=micro_splits,
            post_global_adapter_hash=post_global_adapter_hash,
            actual_global_step_norm=actual_global_step_norm,
            numeric_seed=numeric_seed,
        )
        for existing_observation in existing:
            if any(
                existing_observation.get(field) != baseline_checkpoint[field]
                for field in (
                    "baseline_objective_value",
                    "baseline_negative_log_likelihood",
                    "baseline_supervised_tokens",
                    "baseline_micro_split_results",
                    "baseline_micro_split_manifest_hash",
                    "baseline_post_global_adapter_hash",
                    "actual_global_parameter_step_norm",
                    "numeric_seed",
                )
            ):
                raise ValueError("v21 resumed observations disagree on baseline identity")
        _write_json(baseline_checkpoint_path, baseline_checkpoint)
    else:
        baseline_performance, baseline_loss, baseline_tokens, baseline_rows = (
            _evaluate_records_numeric_detailed(model, tokenizer, objective_records)
        )
        baseline_micro = _summarize_micro_splits(baseline_rows, micro_splits)
        baseline_manifest_hash = canonical_hash(
            baseline_micro,
            prefix=f"finance_target_observability_{objective_role}_baseline_micro_splits:",
        )
        baseline_checkpoint = {
            "experiment_version": TARGET_OBSERVABILITY_STUDY_VERSION,
            "plan_hash": plan["plan_hash"],
            "direction_manifest_hash": direction_manifest["manifest_hash"],
            "direction_scale_manifest_hash": scale_manifest["manifest_hash"],
            "objective_role": objective_role,
            "objective_role_file_sha256": role_file["sha256"],
            "authorization_objective_access": "forbidden",
            "objective_gradient_access": "none",
            "gp_c_evaluated": False,
            "baseline_objective_value": baseline_performance,
            "baseline_negative_log_likelihood": baseline_loss,
            "baseline_supervised_tokens": baseline_tokens,
            "baseline_micro_split_results": baseline_micro,
            "baseline_micro_split_manifest_hash": baseline_manifest_hash,
            "baseline_post_global_adapter_hash": post_global_adapter_hash,
            "actual_global_parameter_step_norm": actual_global_step_norm,
            "numeric_seed": numeric_seed,
        }
        baseline_checkpoint["checkpoint_hash"] = _baseline_checkpoint_hash(
            baseline_checkpoint
        )
        _write_json(baseline_checkpoint_path, baseline_checkpoint)
        del baseline_rows
    baseline_performance = float(baseline_checkpoint["baseline_objective_value"])
    baseline_loss = float(baseline_checkpoint["baseline_negative_log_likelihood"])
    baseline_tokens = int(baseline_checkpoint["baseline_supervised_tokens"])
    baseline_micro = tuple(baseline_checkpoint["baseline_micro_split_results"])
    baseline_manifest_hash = str(
        baseline_checkpoint["baseline_micro_split_manifest_hash"]
    )
    design_by_id = {str(row["design_row_id"]): row for row in plan["design_rows"]}
    started = time.monotonic()
    completed_now = 0
    cached_direction_id: str | None = None
    cached_direction: dict[str, Any] | None = None
    for job in assigned:
        row_id = str(job["design_row_id"])
        ratio = float(job["target_parameter_step_ratio"])
        sign = int(job["sign"])
        key = (row_id, ratio, sign)
        if key in completed:
            continue
        if cached_direction_id != row_id:
            cached_direction = _load_verified_gradient(
                Path(str(direction_by_id[row_id]["file"])),
                str(direction_by_id[row_id]["sha256"]),
            )
            cached_direction_id = row_id
        if cached_direction is None:
            raise ValueError("v21 direction cache is empty")
        scale = scale_by_key[(row_id, ratio)]
        coefficient = (
            float(scale["coefficient_per_actual_global_step_norm"]) * actual_global_step_norm
        )
        update = _linear_combination(
            [global_update, cached_direction],
            [1.0, sign * coefficient],
        )
        _seed_everything(numeric_seed)
        _configure_numeric_policy(plan["numeric_profile"])
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
            raise ValueError("v21 perturbation changed Objective token support")
        observation: dict[str, Any] = {
            "experiment_version": TARGET_OBSERVABILITY_STUDY_VERSION,
            "plan_hash": plan["plan_hash"],
            "direction_manifest_hash": direction_manifest["manifest_hash"],
            "direction_scale_manifest_hash": scale_manifest["manifest_hash"],
            "objective_role": objective_role,
            "authorization_objective_access": "forbidden",
            "objective_gradient_access": "none",
            "gp_c_evaluated": False,
            "design_row_id": row_id,
            "design_role": design_by_id[row_id]["role"],
            "coordinate_ids": design_by_id[row_id]["coordinate_ids"],
            "target_parameter_step_ratio": ratio,
            "sign": sign,
            "coefficient": coefficient,
            "actual_global_parameter_step_norm": actual_global_step_norm,
            "actual_parameter_step_norm": actual_step_norm,
            "actual_parameter_step_ratio": actual_ratio,
            "objective_value": performance,
            "negative_log_likelihood": loss,
            "supervised_tokens": tokens,
            "micro_split_results": _summarize_micro_splits(record_rows, micro_splits),
            "baseline_objective_value": baseline_performance,
            "baseline_negative_log_likelihood": baseline_loss,
            "baseline_supervised_tokens": baseline_tokens,
            "baseline_micro_split_results": baseline_micro,
            "baseline_micro_split_manifest_hash": baseline_manifest_hash,
            "baseline_post_global_adapter_hash": post_global_adapter_hash,
            "perturbed_adapter_hash": _adapter_tensor_sha256(model),
            "numeric_seed": numeric_seed,
            "partition_index": partition_index,
            "partition_count": partition_count,
        }
        observation["observation_hash"] = _observation_hash(observation)
        _append_jsonl(worker_path, observation)
        completed_now += 1
        del update, record_rows
    worker_report: dict[str, Any] = {
        "experiment_version": TARGET_OBSERVABILITY_STUDY_VERSION,
        "plan_hash": plan["plan_hash"],
        "objective_role": objective_role,
        "authorization_objective_access": "forbidden",
        "objective_gradient_access": "none",
        "gp_c_evaluated": False,
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
        prefix=f"finance_target_observability_{objective_role}_worker_report:",
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


def _measurement_integrity(
    plan: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
    *,
    objective_role: str,
) -> bool:
    splits = {
        str(row["micro_split_id"]): tuple(str(value) for value in row["record_ids"])
        for row in plan["objective_micro_splits"][objective_role]
    }
    prefix = f"finance_target_observability_{objective_role}_baseline_micro_splits:"
    baseline_hashes = set()
    baseline_adapter_hashes = set()
    global_norms = set()
    numeric_seeds = set()
    valid = True
    for observation in observations:
        current = {str(row["micro_split_id"]): row for row in observation["micro_split_results"]}
        baseline = {
            str(row["micro_split_id"]): row for row in observation["baseline_micro_split_results"]
        }
        if set(current) != set(splits) or set(baseline) != set(splits):
            valid = False
            continue
        for split_id, record_ids in splits.items():
            if (
                tuple(str(value) for value in current[split_id]["record_ids"]) != record_ids
                or tuple(str(value) for value in baseline[split_id]["record_ids"]) != record_ids
                or int(current[split_id]["supervised_tokens"])
                != int(baseline[split_id]["supervised_tokens"])
                or int(current[split_id]["supervised_tokens"]) <= 0
            ):
                valid = False
        current_tokens = sum(int(row["supervised_tokens"]) for row in current.values())
        baseline_tokens = sum(int(row["supervised_tokens"]) for row in baseline.values())
        current_loss = (
            sum(
                float(row["negative_log_likelihood"]) * int(row["supervised_tokens"])
                for row in current.values()
            )
            / current_tokens
        )
        baseline_loss = (
            sum(
                float(row["negative_log_likelihood"]) * int(row["supervised_tokens"])
                for row in baseline.values()
            )
            / baseline_tokens
        )
        valid = valid and bool(
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
            and canonical_hash(observation["baseline_micro_split_results"], prefix=prefix)
            == observation["baseline_micro_split_manifest_hash"]
        )
        baseline_hashes.add(str(observation["baseline_micro_split_manifest_hash"]))
        baseline_adapter_hashes.add(str(observation["baseline_post_global_adapter_hash"]))
        global_norms.add(float(observation["actual_global_parameter_step_norm"]))
        numeric_seeds.add(int(observation["numeric_seed"]))
    return valid and all(
        len(values) == 1
        for values in (baseline_hashes, baseline_adapter_hashes, global_norms, numeric_seeds)
    )


def _split_result(observation: Mapping[str, Any], split_id: str) -> Mapping[str, Any]:
    return next(
        row for row in observation["micro_split_results"] if str(row["micro_split_id"]) == split_id
    )


def analyze_role(
    plan: Mapping[str, Any],
    direction_manifest: Mapping[str, Any],
    scale_manifest: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
    *,
    objective_role: Literal["estimation", "validation"],
) -> dict[str, Any]:
    frozen = verify_plan(plan)
    _verify_direction_manifests(frozen, direction_manifest, scale_manifest)
    expected = {
        (str(row["design_row_id"]), float(ratio), sign)
        for row in frozen["design_rows"]
        for ratio in STEP_RATIO_LADDER
        for sign in (-1, 1)
    }
    designs = {str(row["design_row_id"]): row for row in frozen["design_rows"]}
    observed = {}
    for row in observations:
        row_id = str(row.get("design_row_id", ""))
        design = designs.get(row_id)
        if (
            row.get("observation_hash") != _observation_hash(row)
            or row.get("experiment_version") != TARGET_OBSERVABILITY_STUDY_VERSION
            or row.get("plan_hash") != frozen["plan_hash"]
            or row.get("direction_manifest_hash") != direction_manifest["manifest_hash"]
            or row.get("direction_scale_manifest_hash") != scale_manifest["manifest_hash"]
            or row.get("objective_role") != objective_role
            or row.get("authorization_objective_access") != "forbidden"
            or row.get("objective_gradient_access") != "none"
            or row.get("gp_c_evaluated") is not False
            or int(row.get("numeric_seed", -1)) != NUMERIC_SEED
            or design is None
            or row.get("design_role") != design["role"]
            or tuple(str(value) for value in row.get("coordinate_ids", ()))
            != tuple(str(value) for value in design["coordinate_ids"])
        ):
            raise ValueError("v21 observation failed replay")
        key = (
            row_id,
            float(row["target_parameter_step_ratio"]),
            int(row["sign"]),
        )
        if key in observed:
            raise ValueError("v21 observation matrix contains duplicates")
        observed[key] = row
    if set(observed) != expected:
        raise ValueError(f"v21 observation matrix is incomplete:{len(observed)}/{len(expected)}")
    split_ids = [
        str(row["micro_split_id"]) for row in frozen["objective_micro_splits"][objective_role]
    ]
    measurement_passed = _measurement_integrity(
        frozen,
        tuple(observed.values()),
        objective_role=objective_role,
    )
    nonnull = [row for row in observed.values() if row["design_role"] != "null_replay"]
    ratio_errors = [
        abs(float(row["actual_parameter_step_ratio"]) - float(row["target_parameter_step_ratio"]))
        / float(row["target_parameter_step_ratio"])
        for row in nonnull
    ]
    maximum_ratio_error = max(ratio_errors)
    parameter_scale_passed = maximum_ratio_error <= float(
        frozen["maximum_parameter_step_ratio_relative_error"]
    )
    null_rows = [row for row in observed.values() if row["design_role"] == "null_replay"]
    maximum_null_delta = max(
        abs(float(row["objective_value"]) - float(row["baseline_objective_value"]))
        for row in null_rows
    )
    null_replay_passed = maximum_null_delta <= float(frozen["maximum_null_objective_delta"])
    coordinate_rows: list[dict[str, Any]] = []
    for row_id, design in sorted(designs.items()):
        if design["role"] != "direct_coordinate":
            continue
        ratio_results: dict[str, dict[str, Any]] = {}
        for ratio in STEP_RATIO_LADDER:
            plus = observed[(row_id, ratio, 1)]
            minus = observed[(row_id, ratio, -1)]
            denominator = float(plus["actual_parameter_step_norm"]) + float(
                minus["actual_parameter_step_norm"]
            )
            if denominator <= 0:
                raise ValueError("v21 Direct Coordinate has a zero finite-difference radius")
            slopes = [
                (
                    float(_split_result(plus, split_id)["performance"])
                    - float(_split_result(minus, split_id)["performance"])
                )
                / denominator
                for split_id in split_ids
            ]
            mean = statistics.fmean(slopes)
            deviation = statistics.stdev(slopes)
            ratio_results[str(ratio)] = {
                "target_parameter_step_ratio": ratio,
                "micro_split_slopes": tuple(slopes),
                "effect_resolution": classify_effect(
                    mean=mean,
                    standard_deviation=deviation,
                    sample_count=len(slopes),
                ),
            }
        primary = ratio_results[str(PRIMARY_STEP_RATIO)]["effect_resolution"]
        secondary_ratio = next(value for value in STEP_RATIO_LADDER if value != PRIMARY_STEP_RATIO)
        secondary = ratio_results[str(secondary_ratio)]["effect_resolution"]
        mean_difference = abs(float(primary["mean"]) - float(secondary["mean"]))
        radius_agreement = bool(
            primary["resolution"] == secondary["resolution"]
            and mean_difference
            <= float(frozen["radius_agreement_policy"]["maximum_absolute_slope_difference"])
        )
        coordinate_rows.append(
            {
                "design_row_id": row_id,
                "coordinate_id": str(design["coordinate_ids"][0]),
                "ratio_results": ratio_results,
                "primary_effect_resolution": primary,
                "secondary_effect_resolution": secondary,
                "radius_mean_absolute_difference": mean_difference,
                "radius_agreement": radius_agreement,
                "resolved": bool(primary["resolved"] and radius_agreement),
            }
        )
    resolved_count = sum(bool(row["resolved"]) for row in coordinate_rows)
    status = (
        "passed"
        if measurement_passed
        and parameter_scale_passed
        and null_replay_passed
        and resolved_count == DIRECT_COORDINATE_COUNT
        else "failed"
    )
    resolution_counts: dict[str, int] = {}
    for row in coordinate_rows:
        resolution_key = str(row["primary_effect_resolution"]["resolution"])
        resolution_counts[resolution_key] = resolution_counts.get(resolution_key, 0) + 1
    report: dict[str, Any] = {
        "experiment_version": TARGET_OBSERVABILITY_STUDY_VERSION,
        "artifact_type": "DirectTargetObservabilityRoleReport",
        "plan_hash": frozen["plan_hash"],
        "direction_manifest_hash": direction_manifest["manifest_hash"],
        "direction_scale_manifest_hash": scale_manifest["manifest_hash"],
        "objective_role": objective_role,
        "objective_record_count": OBJECTIVE_RECORDS_PER_ROLE,
        "objective_micro_split_count": OBJECTIVE_MICRO_SPLIT_COUNT,
        "objective_measurement_integrity_passed": measurement_passed,
        "parameter_scale_passed": parameter_scale_passed,
        "maximum_parameter_step_ratio_relative_error": maximum_ratio_error,
        "null_replay_passed": null_replay_passed,
        "maximum_null_objective_delta": maximum_null_delta,
        "direct_coordinate_count": len(coordinate_rows),
        "resolved_coordinate_count": resolved_count,
        "resolution_counts": dict(sorted(resolution_counts.items())),
        "direct_coordinate_rows": tuple(coordinate_rows),
        "authorization_objective_access": "forbidden",
        "objective_gradient_access": "none",
        "gp_c_evaluated": False,
        "contribution_approximation_authorized": False,
        "status": status,
    }
    report["report_hash"] = canonical_hash(report, prefix=ROLE_REPORT_HASH_PREFIX)
    return report


def combine_reports(
    plan: Mapping[str, Any],
    role_reports: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    frozen = verify_plan(plan)
    by_role = {}
    for report in role_reports:
        _replay_hash(
            report,
            field="report_hash",
            prefix=ROLE_REPORT_HASH_PREFIX,
            label="v21 role report",
        )
        role = str(report["objective_role"])
        if (
            role not in OBJECTIVE_ROLES
            or role in by_role
            or report.get("plan_hash") != frozen["plan_hash"]
            or report.get("authorization_objective_access") != "forbidden"
            or report.get("objective_gradient_access") != "none"
            or report.get("gp_c_evaluated") is not False
        ):
            raise ValueError("v21 role report failed replay")
        by_role[role] = report
    if set(by_role) != set(OBJECTIVE_ROLES):
        raise ValueError("v21 combined report lacks an Objective role")
    validation = {
        str(row["coordinate_id"]): row for row in by_role["validation"]["direct_coordinate_rows"]
    }
    agreement_rows = []
    for row in by_role["estimation"]["direct_coordinate_rows"]:
        coordinate_id = str(row["coordinate_id"])
        other = validation[coordinate_id]
        left = str(row["primary_effect_resolution"]["resolution"])
        right = str(other["primary_effect_resolution"]["resolution"])
        agreement_rows.append(
            {
                "coordinate_id": coordinate_id,
                "estimation_resolution": left,
                "validation_resolution": right,
                "resolution_agreement": left == right,
            }
        )
    agreement_rate = sum(bool(row["resolution_agreement"]) for row in agreement_rows) / len(
        agreement_rows
    )
    target_observable = bool(
        all(by_role[role]["status"] == "passed" for role in OBJECTIVE_ROLES)
        and agreement_rate == 1.0
    )
    combined: dict[str, Any] = {
        "experiment_version": TARGET_OBSERVABILITY_STUDY_VERSION,
        "artifact_type": "DirectTargetObservabilityCombinedReport",
        "plan_hash": frozen["plan_hash"],
        "role_report_hashes": {role: by_role[role]["report_hash"] for role in OBJECTIVE_ROLES},
        "role_status": {role: by_role[role]["status"] for role in OBJECTIVE_ROLES},
        "cross_role_resolution_rows": tuple(agreement_rows),
        "cross_role_resolution_agreement_rate": agreement_rate,
        "target_observability_passed": target_observable,
        "next_transition": (
            frozen["success_transition"] if target_observable else frozen["failure_transition"]
        ),
        "authorization_objective_access": "forbidden",
        "authorization_record_count_consumed": 0,
        "objective_gradient_access": "none",
        "gp_c_evaluated": False,
        "contribution_approximation_authorized": False,
        "vtdo_contribution_value": 0.0,
        "status": "passed" if target_observable else "failed",
        "claim_boundary": (
            "A pass only permits preregistration of an independent GP-C comparison. It does "
            "not authorize Contribution, open Authorization, or update VTDO."
        ),
    }
    combined["report_hash"] = canonical_hash(
        combined,
        prefix=COMBINED_REPORT_HASH_PREFIX,
    )
    return combined


def _prepare(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan_path = output_dir / "plan.json"
    if plan_path.exists():
        raise ValueError("v21 target-observability plan is immutable")
    gradient_plan = _read_json(Path(args.gradient_plan).resolve())
    objective_role_files = _materialize_objective_role_files(
        gradient_plan,
        output_dir=output_dir,
    )
    plan = build_plan(
        contract=_read_json(Path(args.contract).resolve()),
        gradient_plan=gradient_plan,
        local_update_report=_read_json(Path(args.local_update_report).resolve()),
        local_update_manifest=_read_json(Path(args.local_update_manifest).resolve()),
        objective_role_files=objective_role_files,
    )
    _write_json(plan_path, plan)
    print(json.dumps({"plan_hash": plan["plan_hash"], "status": "prepared"}, indent=2))


def _freeze(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    direction_dir = Path(args.direction_dir).resolve()
    direction, scales = freeze_directions(
        _read_json(output_dir / "plan.json"),
        _read_json(Path(args.local_update_manifest).resolve()),
        output_dir=direction_dir,
    )
    print(
        json.dumps(
            {
                "direction_manifest_hash": direction["manifest_hash"],
                "direction_scale_manifest_hash": scales["manifest_hash"],
                "status": "frozen",
            },
            indent=2,
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
    direction_dir = Path(args.direction_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    observations = []
    for path in sorted((output_dir / "workers" / args.objective_role).glob("partition_*.jsonl")):
        observations.extend(_load_jsonl(path))
    report = analyze_role(
        plan,
        _read_json(direction_dir / "direction_manifest.json"),
        _read_json(direction_dir / "direction_scale_manifest.json"),
        observations,
        objective_role=args.objective_role,
    )
    path = output_dir / f"{args.objective_role}_report.json"
    _write_json(path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _combine(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    report = combine_reports(
        _read_json(output_dir / "plan.json"),
        [
            _read_json(output_dir / "estimation_report.json"),
            _read_json(output_dir / "validation_report.json"),
        ],
    )
    _write_json(output_dir / "combined_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the v21 Direct-only target study")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--contract", required=True)
    prepare.add_argument("--gradient-plan", required=True)
    prepare.add_argument("--local-update-report", required=True)
    prepare.add_argument("--local-update-manifest", required=True)
    prepare.add_argument("--output-dir", required=True)
    prepare.set_defaults(handler=_prepare)
    freeze = subparsers.add_parser("freeze")
    freeze.add_argument("--output-dir", required=True)
    freeze.add_argument("--direction-dir", required=True)
    freeze.add_argument("--local-update-manifest", required=True)
    freeze.set_defaults(handler=_freeze)
    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("--output-dir", required=True)
    execute_parser.add_argument("--direction-dir", required=True)
    execute_parser.add_argument("--objective-role", choices=OBJECTIVE_ROLES, required=True)
    execute_parser.add_argument("--gpu-ids", type=int, nargs="+", required=True)
    execute_parser.add_argument("--partition-index", type=int, default=0)
    execute_parser.add_argument("--partition-count", type=int, default=1)
    execute_parser.add_argument("--numeric-seed", type=int, default=20262101)
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
