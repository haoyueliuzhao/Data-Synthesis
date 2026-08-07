from __future__ import annotations

import math
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_target_identifiability import (
    DIRECTION_SCALE_HASH_PREFIX,
    IDENTIFIABILITY_STUDY_VERSION,
    OBSERVATION_HASH_PREFIX,
    PLAN_HASH_PREFIX,
    _coordinate_rows,
    _micro_split_manifest,
    _select_direct_coordinates,
    analyze_role,
    build_design_rows,
    combine_reports,
    odd_cubic_fit,
    verify_plan,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_target_identifiability_contract import (
    STEP_RATIO_LADDER,
    STUDY_THRESHOLDS,
    TARGET_IDENTIFIABILITY_ROLE,
)
from trusted_synthesis.hashing import canonical_hash


def _plan() -> dict[str, Any]:
    task_ids = tuple(f"task_{index}" for index in range(6))
    task_types = {
        task_id: task_type
        for task_id, task_type in zip(
            task_ids,
            (
                "comparison",
                "derived_growth_comparison",
                "registered_ratio",
                "temporal_absolute_change",
                "temporal_average",
                "temporal_growth",
            ),
            strict=True,
        )
    }
    state_counts = (3, 3, 3, 3, 4, 4)
    task_distributions = {
        task_id: {
            f"{task_id}_state_{state_index}": 1.0 / state_count
            for state_index in range(state_count)
        }
        for task_id, state_count in zip(task_ids, state_counts, strict=True)
    }
    task_marginals = {task_id: 1.0 / len(task_ids) for task_id in task_ids}
    coordinates = _coordinate_rows(task_distributions, task_marginals)
    direct = _select_direct_coordinates(coordinates, task_types)
    contract_hash = "contract:v20"
    micro_splits = {
        role: _micro_split_manifest(
            tuple(f"{role}_{index}" for index in range(16)),
            role=role,
            contract_hash=contract_hash,
        )
        for role in ("estimation", "validation")
    }
    values: dict[str, Any] = {
        "experiment_version": IDENTIFIABILITY_STUDY_VERSION,
        "contract_hash": contract_hash,
        "run_role": TARGET_IDENTIFIABILITY_ROLE,
        "allowed_objective_roles": ["estimation", "validation"],
        "authorization_objective_access": "forbidden",
        "production_authorization_eligible": False,
        "gp_c_execution_allowed": False,
        "step_ratio_ladder": list(STEP_RATIO_LADDER),
        "study_thresholds": STUDY_THRESHOLDS,
        "task_ids": task_ids,
        "task_type_by_task_id": task_types,
        "task_distributions": task_distributions,
        "task_marginals": task_marginals,
        "coordinate_rows": coordinates,
        "direct_coordinate_ids": direct,
        "design_rows": build_design_rows(direct),
        "objective_micro_splits": micro_splits,
        "sealed_authorization_partition": {
            "record_ids": tuple(f"authorization_{index}" for index in range(16)),
            "set_id": canonical_hash(
                tuple(f"authorization_{index}" for index in range(16)),
                prefix="finance_target_identifiability_sealed_authorization_partition:",
            ),
            "objective_access": "forbidden",
        },
        "numeric_contract_hash": "numeric:v20",
        "success_transition": "freeze_fresh_proxy_comparison_study",
        "failure_transition": "retain_contribution_zero_and_redesign_target_measurement",
        "claim_boundary": "identifiability only",
    }
    values["plan_hash"] = canonical_hash(values, prefix=PLAN_HASH_PREFIX)
    return values


def _direction_and_scale(plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    artifacts = []
    for row in plan["design_rows"]:
        norm = 0.0 if row["role"] == "null_replay" else math.sqrt(len(row["coordinate_ids"]))
        artifacts.append(
            {
                "design_row_id": row["design_row_id"],
                "role": row["role"],
                "file": f"/{row['design_row_id']}.safetensors",
                "sha256": f"sha:{row['design_row_id']}",
                "direction_norm": norm,
            }
        )
    direction: dict[str, Any] = {
        "finite_target_plan_hash": plan["plan_hash"],
        "direction_artifacts": artifacts,
    }
    direction["manifest_hash"] = canonical_hash(
        direction,
        prefix="finance_gp_c_finite_target_directions:",
    )
    scales: dict[str, Any] = {
        "plan_hash": plan["plan_hash"],
        "direction_manifest_hash": direction["manifest_hash"],
        "scale_rows": tuple(
            {
                "design_row_id": row["design_row_id"],
                "target_parameter_step_ratio": ratio,
                "direction_norm": next(
                    item["direction_norm"]
                    for item in artifacts
                    if item["design_row_id"] == row["design_row_id"]
                ),
                "coefficient_per_actual_global_step_norm": 0.0,
            }
            for row in plan["design_rows"]
            for ratio in STEP_RATIO_LADDER
        ),
    }
    scales["manifest_hash"] = canonical_hash(scales, prefix=DIRECTION_SCALE_HASH_PREFIX)
    return direction, scales


def _observations(plan: dict[str, Any], *, role: str) -> list[dict[str, Any]]:
    direct_slopes = {
        coordinate_id: float(index + 1)
        for index, coordinate_id in enumerate(plan["direct_coordinate_ids"])
    }
    values = []
    for design in plan["design_rows"]:
        if design["role"] == "null_replay":
            slope = 0.0
        else:
            slope = sum(
                float(weight) * direct_slopes[coordinate_id]
                for coordinate_id, weight in design["coordinate_weights"].items()
            ) / math.sqrt(len(design["coordinate_ids"]))
        for ratio in STEP_RATIO_LADDER:
            for sign in (-1, 1):
                step = 0.0 if design["role"] == "null_replay" else ratio
                micro = tuple(
                    {
                        "micro_split_id": split["micro_split_id"],
                        "record_ids": split["record_ids"],
                        "performance": sign * step * slope,
                        "negative_log_likelihood": -sign * step * slope,
                        "supervised_tokens": 4,
                    }
                    for split in plan["objective_micro_splits"][role]
                )
                baseline = tuple(
                    {
                        "micro_split_id": split["micro_split_id"],
                        "record_ids": split["record_ids"],
                        "performance": 0.0,
                        "negative_log_likelihood": 0.0,
                        "supervised_tokens": 4,
                    }
                    for split in plan["objective_micro_splits"][role]
                )
                row: dict[str, Any] = {
                    "plan_hash": plan["plan_hash"],
                    "objective_role": role,
                    "authorization_objective_access": "forbidden",
                    "design_row_id": design["design_row_id"],
                    "design_role": design["role"],
                    "design_family": design["design_family"],
                    "target_parameter_step_ratio": ratio,
                    "sign": sign,
                    "actual_global_parameter_step_norm": 1.0,
                    "actual_parameter_step_norm": step,
                    "actual_parameter_step_ratio": step,
                    "objective_value": sign * step * slope,
                    "negative_log_likelihood": -sign * step * slope,
                    "supervised_tokens": 16,
                    "micro_split_results": micro,
                    "baseline_objective_value": 0.0,
                    "baseline_negative_log_likelihood": 0.0,
                    "baseline_supervised_tokens": 16,
                    "baseline_micro_split_results": baseline,
                    "baseline_micro_split_manifest_hash": canonical_hash(
                        baseline,
                        prefix=(
                            f"finance_target_identifiability_{role}_"
                            "baseline_micro_splits:"
                        ),
                    ),
                    "baseline_post_global_adapter_hash": "adapter:post_global",
                    "perturbed_adapter_hash": (
                        "adapter:post_global"
                        if design["role"] == "null_replay"
                        else f"adapter:{design['design_row_id']}:{ratio}:{sign}"
                    ),
                    "numeric_contract_hash": plan["numeric_contract_hash"],
                    "numeric_seed": 7,
                }
                row["observation_hash"] = canonical_hash(row, prefix=OBSERVATION_HASH_PREFIX)
                values.append(row)
    return values


def test_design_registry_freezes_direct_and_three_block_families() -> None:
    rows = build_design_rows(tuple(f"coordinate_{index}" for index in range(7)))
    assert len(rows) == 31
    assert sum(row["design_family"] == "direct" for row in rows) == 7
    assert sum(row["design_family"] == "block_2" for row in rows) == 7
    assert sum(row["design_family"] == "block_4" for row in rows) == 8
    assert sum(row["design_family"] == "block_7" for row in rows) == 8
    assert sum(row["design_family"] == "null" for row in rows) == 1


def test_odd_cubic_fit_recovers_local_linear_and_nonlinear_terms() -> None:
    points = []
    for step in (-0.01, 0.01, -0.005, 0.005, -0.0025, 0.0025):
        points.append((step, 3.0 * step + 200.0 * step**3))
    fit = odd_cubic_fit(points)
    assert fit["linear_slope"] == pytest.approx(3.0)
    assert fit["cubic_coefficient"] == pytest.approx(200.0)


def test_identifiability_role_passes_exact_linear_direct_block_reconstruction() -> None:
    plan = verify_plan(_plan())
    direction, scales = _direction_and_scale(plan)
    reports = []
    for role in ("estimation", "validation"):
        report = analyze_role(
            plan,
            direction,
            scales,
            _observations(plan, role=role),
            objective_role=role,
        )
        assert report["status"] == "passed"
        assert report["observation_count"] == 186
        assert report["anchor_identifiable_rate"] == 1.0
        assert report["maximum_block_reconstruction_relative_error"] == pytest.approx(0.0)
        reports.append(report)
    combined = combine_reports(plan, reports)
    assert combined["status"] == "passed"
    assert combined["authorization_objective_observation_count"] == 0
    assert combined["gp_c_evaluated"] is False


def test_measurement_gate_rejects_rehashed_baseline_content_tampering() -> None:
    plan = verify_plan(_plan())
    direction, scales = _direction_and_scale(plan)
    observations = _observations(plan, role="estimation")
    observations[0]["baseline_micro_split_results"][0]["negative_log_likelihood"] = 1.0
    observations[0]["observation_hash"] = canonical_hash(
        {
            key: value
            for key, value in observations[0].items()
            if key != "observation_hash"
        },
        prefix=OBSERVATION_HASH_PREFIX,
    )
    report = analyze_role(
        plan,
        direction,
        scales,
        observations,
        objective_role="estimation",
    )
    assert report["status"] == "failed"
    assert report["gates"]["objective_measurement_gate"] is False


def test_authorization_access_is_fail_closed() -> None:
    plan = _plan()
    plan["authorization_objective_access"] = "evaluated"
    payload = dict(plan)
    payload.pop("plan_hash")
    plan["plan_hash"] = canonical_hash(payload, prefix=PLAN_HASH_PREFIX)
    with pytest.raises(ValueError, match="opened Authorization"):
        verify_plan(plan)


def test_combined_report_rejects_role_report_identity_tampering() -> None:
    plan = verify_plan(_plan())
    direction, scales = _direction_and_scale(plan)
    estimation = analyze_role(
        plan,
        direction,
        scales,
        _observations(plan, role="estimation"),
        objective_role="estimation",
    )
    validation = analyze_role(
        plan,
        direction,
        scales,
        _observations(plan, role="validation"),
        objective_role="validation",
    )
    validation["status"] = "failed"
    with pytest.raises(ValueError, match="identity replay"):
        combine_reports(plan, (estimation, validation))


def test_combined_report_fails_closed_on_cross_role_sign_disagreement() -> None:
    plan = verify_plan(_plan())
    direction, scales = _direction_and_scale(plan)
    estimation = analyze_role(
        plan,
        direction,
        scales,
        _observations(plan, role="estimation"),
        objective_role="estimation",
    )
    validation = analyze_role(
        plan,
        direction,
        scales,
        _observations(plan, role="validation"),
        objective_role="validation",
    )
    validation["direct_coordinate_rows"][0]["mean_linear_slope"] *= -1
    payload = dict(validation)
    payload.pop("report_hash")
    validation["report_hash"] = canonical_hash(
        payload,
        prefix="finance_target_identifiability_report:",
    )
    combined = combine_reports(plan, (estimation, validation))
    assert combined["status"] == "failed"
    assert combined["gates"]["role_identifiability_gate"] is True
    assert combined["gates"]["cross_role_direct_sign_agreement_gate"] is False


def test_plan_rejects_rehashed_design_and_partition_tampering() -> None:
    design_tamper = _plan()
    design_tamper["design_rows"][0]["coordinate_weights"] = {
        design_tamper["direct_coordinate_ids"][0]: -1
    }
    payload = dict(design_tamper)
    payload.pop("plan_hash")
    design_tamper["plan_hash"] = canonical_hash(payload, prefix=PLAN_HASH_PREFIX)
    with pytest.raises(ValueError, match="design registry differs"):
        verify_plan(design_tamper)

    overlap_tamper = _plan()
    authorization_ids = list(overlap_tamper["sealed_authorization_partition"]["record_ids"])
    authorization_ids[0] = str(
        overlap_tamper["objective_micro_splits"]["estimation"][0]["record_ids"][0]
    )
    overlap_tamper["sealed_authorization_partition"]["record_ids"] = tuple(authorization_ids)
    overlap_tamper["sealed_authorization_partition"]["set_id"] = canonical_hash(
        tuple(overlap_tamper["sealed_authorization_partition"]["record_ids"]),
        prefix="finance_target_identifiability_sealed_authorization_partition:",
    )
    payload = dict(overlap_tamper)
    payload.pop("plan_hash")
    overlap_tamper["plan_hash"] = canonical_hash(payload, prefix=PLAN_HASH_PREFIX)
    with pytest.raises(ValueError, match="partitions overlap"):
        verify_plan(overlap_tamper)
