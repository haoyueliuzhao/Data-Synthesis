from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    GRADIENT_ALIGNMENT_VERSION,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_support import (
    TARGET_OBSERVABILITY_ROLE,
    _required_partition_counts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_target_local_updates import (
    EXPECTED_REALIZATION_COUNT,
    EXPECTED_STATE_COUNT,
    EXPECTED_TASK_COUNT,
    _result_hash,
    _verify_plan,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_target_observability import (
    MINIMUM_PRACTICAL_EFFECT,
    PREREGISTRATION_HASH_PREFIX,
    build_preregistration,
    classify_effect,
    required_micro_split_count,
    verify_preregistration,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_target_observability_contract import (
    REQUIRED_TASK_TYPES,
    _select_target_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_target_observability_study import (
    DIRECTION_MANIFEST_HASH_PREFIX,
    NUMERIC_SEED,
    OBSERVATION_HASH_PREFIX,
    PLAN_HASH_PREFIX,
    SCALE_MANIFEST_HASH_PREFIX,
    _baseline_checkpoint_hash,
    _coordinate_rows,
    _design_rows,
    _micro_splits,
    _observation_hash,
    _select_direct_coordinates,
    _verify_baseline_checkpoint,
    _verify_direction_manifests,
    analyze_role,
    combine_reports,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_target_observability_study import (
    verify_plan as verify_study_plan,
)
from trusted_synthesis.hashing import canonical_hash


def _source_report(role: str) -> dict[str, object]:
    value: dict[str, object] = {
        "experiment_version": "finance_target_identifiability_study.v20",
        "objective_role": role,
        "authorization_objective_access": "forbidden",
        "gp_c_evaluated": False,
        "direct_coordinate_rows": [
            {
                "coordinate_ids": [f"coordinate:{index}"],
                "mean_linear_slope": (index - 3) * 0.001,
                "linear_slope_standard_deviation": 0.003 + index * 0.0001,
            }
            for index in range(7)
        ],
    }
    value["report_hash"] = canonical_hash(
        value,
        prefix="finance_target_identifiability_report:",
    )
    return value


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _target_artifact(
    task_type: str,
    suffix: str,
    evidence_version_id: str,
) -> Any:
    return SimpleNamespace(
        artifact_id=f"artifact:{suffix}",
        omega=SimpleNamespace(
            task=SimpleNamespace(
                task_id=f"task:{suffix}",
                public=SimpleNamespace(task_type=task_type),
            ),
            public_corpus=SimpleNamespace(
                evidence=(SimpleNamespace(evidence_version_id=evidence_version_id),)
            ),
        ),
    )


def test_effect_resolution_distinguishes_signal_equivalence_and_uncertainty() -> None:
    positive = classify_effect(
        mean=0.01,
        standard_deviation=0.001,
        sample_count=32,
    )
    equivalent = classify_effect(
        mean=0.0,
        standard_deviation=0.001,
        sample_count=32,
    )
    inconclusive = classify_effect(
        mean=0.003,
        standard_deviation=0.02,
        sample_count=32,
    )

    assert positive["resolution"] == "meaningful_positive"
    assert equivalent["resolution"] == "practically_equivalent"
    assert inconclusive["resolution"] == "inconclusive"


def test_power_planning_uses_frozen_engineering_effect_bound() -> None:
    assert MINIMUM_PRACTICAL_EFFECT == 0.005
    assert (
        required_micro_split_count(
            standard_deviation=0.005,
            effect_size=MINIMUM_PRACTICAL_EFFECT,
        )
        == 8
    )

    with pytest.raises(ValueError, match="frozen"):
        required_micro_split_count(
            standard_deviation=0.005,
            effect_size=MINIMUM_PRACTICAL_EFFECT,
            power=0.9,
        )


def test_target_observability_support_requires_exact_large_partitions() -> None:
    assert _required_partition_counts(TARGET_OBSERVABILITY_ROLE) == (128, 128, 128)
    assert _required_partition_counts("target_identifiability") == (16, 16, 16)


def test_preregistration_replays_source_and_freezes_authorization(
    tmp_path: Path,
) -> None:
    estimation_path = tmp_path / "estimation.json"
    validation_path = tmp_path / "validation.json"
    output_path = tmp_path / "preregistration.json"
    _write(estimation_path, _source_report("estimation"))
    _write(validation_path, _source_report("validation"))

    value = build_preregistration(
        estimation_report_path=estimation_path,
        validation_report_path=validation_path,
        output_path=output_path,
    )

    assert value["objective_records_per_role"] == 128
    assert value["objective_micro_split_count"] == 32
    assert value["design_policy"] == "direct_coordinates_only"
    assert value["authorization_objective_access"] == "forbidden"
    assert value["gp_c_execution_allowed"] is False
    assert output_path.is_file()


def test_preregistration_tamper_fails_closed(tmp_path: Path) -> None:
    estimation_path = tmp_path / "estimation.json"
    validation_path = tmp_path / "validation.json"
    output_path = tmp_path / "preregistration.json"
    _write(estimation_path, _source_report("estimation"))
    _write(validation_path, _source_report("validation"))
    value = build_preregistration(
        estimation_report_path=estimation_path,
        validation_report_path=validation_path,
        output_path=output_path,
    )
    value["minimum_practical_effect"] = 0.01

    with pytest.raises(ValueError, match="identity replay"):
        verify_preregistration(value)


def test_preregistration_hash_prefix_is_stable() -> None:
    assert PREREGISTRATION_HASH_PREFIX == "finance_target_observability_preregistration:"


def test_fresh_target_selection_is_deterministic_and_task_balanced() -> None:
    artifacts = [
        _target_artifact(task_type, f"{index}:z", f"evidence:{index}:z")
        for index, task_type in enumerate(REQUIRED_TASK_TYPES)
    ]
    artifacts.append(
        _target_artifact(
            REQUIRED_TASK_TYPES[0],
            "0:a",
            "evidence:0:a",
        )
    )

    selected = _select_target_artifacts(cast(Any, artifacts))

    assert [row.omega.task.public.task_type for row in selected] == list(REQUIRED_TASK_TYPES)
    assert selected[0].artifact_id == "artifact:0:a"


def test_fresh_target_selection_rejects_shared_public_evidence() -> None:
    artifacts = [
        _target_artifact(
            task_type,
            str(index),
            "evidence:shared" if index < 2 else f"evidence:{index}",
        )
        for index, task_type in enumerate(REQUIRED_TASK_TYPES)
    ]

    with pytest.raises(ValueError, match="share public Evidence"):
        _select_target_artifacts(cast(Any, artifacts))


def test_target_local_update_result_hash_covers_forbidden_access_fields() -> None:
    row = {
        "job_id": "job:1",
        "objective_record_access": "none",
        "authorization_objective_access": "forbidden",
        "gp_c_evaluated": False,
    }
    original = _result_hash(row)

    row["objective_record_access"] = "estimation"

    assert _result_hash(row) != original


def test_target_local_update_plan_fails_closed_on_objective_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_path = tmp_path / "target.jsonl"
    target_path.write_text("{}\n", encoding="utf-8")
    target_sha256 = hashlib.sha256(target_path.read_bytes()).hexdigest()
    jobs = [
        {"job_id": f"job:{index}", "record_id": f"record:{index}"}
        for index in range(EXPECTED_REALIZATION_COUNT)
    ]
    numeric_contract = {
        "run_role": TARGET_OBSERVABILITY_ROLE,
        "authorization_objective_access": "forbidden",
        "gp_c_execution_allowed": False,
        "contribution_approximation_authorized": False,
    }
    monkeypatch.setattr(
        "trusted_synthesis.experiments.vtdo_experiment."
        "phase1_target_local_updates._replay_numeric_contract",
        lambda _plan: numeric_contract,
    )
    plan = {
        "experiment_version": GRADIENT_ALIGNMENT_VERSION,
        "run_role": TARGET_OBSERVABILITY_ROLE,
        "numeric_contract": numeric_contract,
        "numeric_contract_hash": canonical_hash(
            numeric_contract,
            prefix="finance_contribution_numeric_contract:",
        ),
        "authorization_objective_access": "forbidden",
        "task_count": EXPECTED_TASK_COUNT,
        "state_count": EXPECTED_STATE_COUNT,
        "state_realization_count": EXPECTED_REALIZATION_COUNT,
        "target_records_path": str(target_path),
        "target_records_sha256": target_sha256,
        "jobs": jobs,
    }

    verified, _ = _verify_plan(plan)
    assert len(verified["jobs"]) == EXPECTED_REALIZATION_COUNT

    plan["authorization_objective_access"] = "estimation"
    with pytest.raises(ValueError, match="opened Authorization"):
        _verify_plan(plan)


def _study_plan(tmp_path: Path) -> dict[str, Any]:
    task_ids = [f"task:{index}" for index in range(6)]
    state_counts = [3, 3, 3, 3, 3, 5]
    distributions = {
        task_id: {
            f"state:{task_index}:{state_index}": 1.0 / state_count
            for state_index in range(state_count)
        }
        for task_index, (task_id, state_count) in enumerate(
            zip(task_ids, state_counts, strict=True)
        )
    }
    marginals = {task_id: 1.0 / 6.0 for task_id in task_ids}
    task_types = dict(zip(task_ids, REQUIRED_TASK_TYPES, strict=True))
    coordinates = _coordinate_rows(distributions, marginals)
    direct = _select_direct_coordinates(coordinates, task_types)
    contract_hash = "contract:v21"
    role_ids = {
        role: [f"record:{role}:{index}" for index in range(128)]
        for role in ("estimation", "validation", "authorization")
    }
    role_files = {}
    for role in ("estimation", "validation"):
        path = tmp_path / f"{role}.jsonl"
        path.write_text(
            "".join(json.dumps({"record_id": record_id}) + "\n" for record_id in role_ids[role]),
            encoding="utf-8",
        )
        role_files[role] = {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "record_count": 128,
            "record_ids": role_ids[role],
            "authorization_record_count": 0,
        }
    plan: dict[str, Any] = {
        "experiment_version": "finance_target_observability_study.v21",
        "run_role": TARGET_OBSERVABILITY_ROLE,
        "contract_hash": contract_hash,
        "task_ids": task_ids,
        "task_type_by_task_id": task_types,
        "task_distributions": distributions,
        "task_marginals": marginals,
        "coordinate_rows": coordinates,
        "direct_coordinate_ids": direct,
        "design_rows": _design_rows(direct),
        "step_ratio_ladder": [0.01, 0.005],
        "primary_step_ratio": 0.005,
        "objective_micro_splits": {
            role: _micro_splits(
                role_ids[role],
                role=role,
                contract_hash=contract_hash,
            )
            for role in ("estimation", "validation")
        },
        "objective_role_files": role_files,
        "sealed_authorization_partition": {
            "record_ids": role_ids["authorization"],
            "set_id": canonical_hash(
                tuple(role_ids["authorization"]),
                prefix="finance_target_observability_sealed_authorization:",
            ),
            "objective_access": "forbidden",
        },
        "minimum_practical_effect": 0.005,
        "maximum_parameter_step_ratio_relative_error": 5e-5,
        "maximum_null_objective_delta": 1e-10,
        "radius_agreement_policy": {
            "maximum_absolute_slope_difference": 0.005,
            "require_resolution_agreement": True,
        },
        "effect_resolution_policy": {
            "meaningful": "ci_excludes_zero_and_absolute_mean_at_least_mpe",
            "equivalent": "ci_fully_contained_within_plus_or_minus_mpe",
            "inconclusive": "neither_meaningful_nor_equivalent",
            "required_role_resolved_rate": 1.0,
            "required_cross_role_resolution_agreement": 1.0,
        },
        "allowed_objective_roles": ["estimation", "validation"],
        "design_policy": "direct_coordinates_only",
        "authorization_objective_access": "forbidden",
        "objective_gradient_access": "none",
        "gp_c_evaluated": False,
        "gp_c_execution_allowed": False,
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
        "success_transition": "freeze_independent_gp_c_comparison_protocol",
        "failure_transition": "retain_contribution_zero_and_report_target_unobservability",
    }
    plan["plan_hash"] = canonical_hash(plan, prefix=PLAN_HASH_PREFIX)
    return plan


def test_v21_study_has_only_direct_coordinates_and_null(tmp_path: Path) -> None:
    plan = verify_study_plan(_study_plan(tmp_path))

    roles = [row["role"] for row in plan["design_rows"]]
    assert roles.count("direct_coordinate") == 7
    assert roles.count("null_replay") == 1
    assert "block_design" not in roles


def test_v21_micro_splits_are_exact_disjoint_partitions(tmp_path: Path) -> None:
    plan = verify_study_plan(_study_plan(tmp_path))

    for role in ("estimation", "validation"):
        rows = plan["objective_micro_splits"][role]
        record_ids = [record_id for row in rows for record_id in row["record_ids"]]
        assert len(rows) == 32
        assert {len(row["record_ids"]) for row in rows} == {4}
        assert len(record_ids) == len(set(record_ids)) == 128


def test_v21_study_rejects_posthoc_gp_c_evaluation(tmp_path: Path) -> None:
    plan = _study_plan(tmp_path)
    plan["gp_c_evaluated"] = True
    plan["plan_hash"] = canonical_hash(
        {key: value for key, value in plan.items() if key != "plan_hash"},
        prefix=PLAN_HASH_PREFIX,
    )

    with pytest.raises(ValueError, match="forbidden path:gp_c_evaluated"):
        verify_study_plan(plan)


def _baseline_checkpoint(plan: dict[str, Any]) -> dict[str, Any]:
    role = "estimation"
    micro_results = [
        {
            "micro_split_id": row["micro_split_id"],
            "record_ids": row["record_ids"],
            "performance": -2.0,
            "negative_log_likelihood": 2.0,
            "supervised_tokens": 4,
        }
        for row in plan["objective_micro_splits"][role]
    ]
    value = {
        "experiment_version": "finance_target_observability_study.v21",
        "plan_hash": plan["plan_hash"],
        "direction_manifest_hash": "direction:v21",
        "direction_scale_manifest_hash": "scale:v21",
        "objective_role": role,
        "objective_role_file_sha256": plan["objective_role_files"][role]["sha256"],
        "authorization_objective_access": "forbidden",
        "objective_gradient_access": "none",
        "gp_c_evaluated": False,
        "baseline_objective_value": -2.0,
        "baseline_negative_log_likelihood": 2.0,
        "baseline_supervised_tokens": 128,
        "baseline_micro_split_results": micro_results,
        "baseline_micro_split_manifest_hash": canonical_hash(
            tuple(micro_results),
            prefix="finance_target_observability_estimation_baseline_micro_splits:",
        ),
        "baseline_post_global_adapter_hash": "adapter:v21",
        "actual_global_parameter_step_norm": 0.5,
        "numeric_seed": 7,
    }
    value["checkpoint_hash"] = _baseline_checkpoint_hash(value)
    return value


def test_v21_baseline_checkpoint_replays_and_fails_closed(tmp_path: Path) -> None:
    plan = verify_study_plan(_study_plan(tmp_path))
    checkpoint = _baseline_checkpoint(plan)
    direction_manifest = {"manifest_hash": "direction:v21"}
    scale_manifest = {"manifest_hash": "scale:v21"}
    kwargs = {
        "plan": plan,
        "direction_manifest": direction_manifest,
        "scale_manifest": scale_manifest,
        "objective_role": "estimation",
        "objective_role_file_sha256": plan["objective_role_files"]["estimation"][
            "sha256"
        ],
        "micro_splits": plan["objective_micro_splits"]["estimation"],
        "post_global_adapter_hash": "adapter:v21",
        "actual_global_step_norm": 0.5,
        "numeric_seed": 7,
    }

    assert _verify_baseline_checkpoint(checkpoint, **kwargs)["baseline_supervised_tokens"] == 128

    checkpoint["baseline_objective_value"] = -1.0
    with pytest.raises(ValueError, match="identity changed"):
        _verify_baseline_checkpoint(checkpoint, **kwargs)


def _direction_manifests(
    tmp_path: Path,
    plan: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    global_artifact = {"file": "global.safetensors", "sha256": "global:v21"}
    direction_rows = []
    scale_rows = []
    for index, design in enumerate(plan["design_rows"]):
        path = tmp_path / f"direction_{index}.bin"
        path.write_bytes(f"direction:{index}".encode())
        norm = 0.0 if design["role"] == "null_replay" else 1.0
        direction_rows.append(
            {
                "design_row_id": design["design_row_id"],
                "role": design["role"],
                "file": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "direction_norm": norm,
            }
        )
        for ratio in (0.01, 0.005):
            scale_rows.append(
                {
                    "design_row_id": design["design_row_id"],
                    "target_parameter_step_ratio": ratio,
                    "direction_norm": norm,
                    "coefficient_per_actual_global_step_norm": (
                        0.0 if design["role"] == "null_replay" else ratio / norm
                    ),
                }
            )
    direction = {
        "plan_hash": plan["plan_hash"],
        "global_update_artifact": global_artifact,
        "direction_artifacts": direction_rows,
        "authorization_objective_access": "forbidden",
        "objective_record_access": "none",
        "gp_c_evaluated": False,
    }
    direction["manifest_hash"] = canonical_hash(
        direction,
        prefix=DIRECTION_MANIFEST_HASH_PREFIX,
    )
    scales = {
        "plan_hash": plan["plan_hash"],
        "direction_manifest_hash": direction["manifest_hash"],
        "global_update_artifact": global_artifact,
        "scale_rows": scale_rows,
        "authorization_objective_access": "forbidden",
        "objective_record_access": "none",
        "gp_c_evaluated": False,
    }
    scales["manifest_hash"] = canonical_hash(scales, prefix=SCALE_MANIFEST_HASH_PREFIX)
    return direction, scales


def _equivalent_observations(
    plan: dict[str, Any],
    direction: dict[str, Any],
    scales: dict[str, Any],
    *,
    role: str,
) -> list[dict[str, Any]]:
    baseline_micro = [
        {
            "micro_split_id": split["micro_split_id"],
            "record_ids": split["record_ids"],
            "performance": -2.0,
            "negative_log_likelihood": 2.0,
            "supervised_tokens": 4,
        }
        for split in plan["objective_micro_splits"][role]
    ]
    baseline_hash = canonical_hash(
        tuple(baseline_micro),
        prefix=f"finance_target_observability_{role}_baseline_micro_splits:",
    )
    values = []
    for design in plan["design_rows"]:
        for ratio in (0.01, 0.005):
            for sign in (-1, 1):
                row = {
                    "experiment_version": "finance_target_observability_study.v21",
                    "plan_hash": plan["plan_hash"],
                    "direction_manifest_hash": direction["manifest_hash"],
                    "direction_scale_manifest_hash": scales["manifest_hash"],
                    "objective_role": role,
                    "authorization_objective_access": "forbidden",
                    "objective_gradient_access": "none",
                    "gp_c_evaluated": False,
                    "design_row_id": design["design_row_id"],
                    "design_role": design["role"],
                    "coordinate_ids": design["coordinate_ids"],
                    "target_parameter_step_ratio": ratio,
                    "sign": sign,
                    "coefficient": ratio * sign,
                    "actual_global_parameter_step_norm": 1.0,
                    "actual_parameter_step_norm": (
                        0.0 if design["role"] == "null_replay" else ratio
                    ),
                    "actual_parameter_step_ratio": (
                        0.0 if design["role"] == "null_replay" else ratio
                    ),
                    "objective_value": -2.0,
                    "negative_log_likelihood": 2.0,
                    "supervised_tokens": 128,
                    "micro_split_results": baseline_micro,
                    "baseline_objective_value": -2.0,
                    "baseline_negative_log_likelihood": 2.0,
                    "baseline_supervised_tokens": 128,
                    "baseline_micro_split_results": baseline_micro,
                    "baseline_micro_split_manifest_hash": baseline_hash,
                    "baseline_post_global_adapter_hash": "adapter:v21",
                    "perturbed_adapter_hash": f"adapter:{design['design_row_id']}:{ratio}:{sign}",
                    "numeric_seed": NUMERIC_SEED,
                    "partition_index": 0,
                    "partition_count": 1,
                }
                row["observation_hash"] = _observation_hash(row)
                values.append(row)
    return values


def test_v21_direct_target_verifier_passes_equivalent_effects_and_stays_sealed(
    tmp_path: Path,
) -> None:
    plan = verify_study_plan(_study_plan(tmp_path))
    direction, scales = _direction_manifests(tmp_path, plan)
    reports = [
        analyze_role(
            plan,
            direction,
            scales,
            _equivalent_observations(plan, direction, scales, role=role),
            objective_role=cast(Any, role),
        )
        for role in ("estimation", "validation")
    ]

    assert all(report["status"] == "passed" for report in reports)
    assert all(report["resolution_counts"] == {"practically_equivalent": 7} for report in reports)
    combined = combine_reports(plan, reports)
    assert combined["target_observability_passed"] is True
    assert combined["authorization_record_count_consumed"] == 0
    assert combined["gp_c_evaluated"] is False
    assert combined["vtdo_contribution_value"] == 0.0


def test_v21_observation_role_tamper_fails_even_with_rehashed_row(tmp_path: Path) -> None:
    plan = verify_study_plan(_study_plan(tmp_path))
    direction, scales = _direction_manifests(tmp_path, plan)
    observations = _equivalent_observations(
        plan,
        direction,
        scales,
        role="estimation",
    )
    observations[0]["design_role"] = "null_replay"
    observations[0]["observation_hash"] = canonical_hash(
        {key: value for key, value in observations[0].items() if key != "observation_hash"},
        prefix=OBSERVATION_HASH_PREFIX,
    )

    with pytest.raises(ValueError, match="observation failed replay"):
        analyze_role(
            plan,
            direction,
            scales,
            observations,
            objective_role="estimation",
        )


def test_v21_scale_manifest_requires_exact_registered_keys(tmp_path: Path) -> None:
    plan = verify_study_plan(_study_plan(tmp_path))
    direction, scales = _direction_manifests(tmp_path, plan)
    scales["scale_rows"][0] = dict(scales["scale_rows"][1])
    scales["manifest_hash"] = canonical_hash(
        {key: value for key, value in scales.items() if key != "manifest_hash"},
        prefix=SCALE_MANIFEST_HASH_PREFIX,
    )

    with pytest.raises(ValueError, match="scale support is incomplete"):
        _verify_direction_manifests(plan, direction, scales)
