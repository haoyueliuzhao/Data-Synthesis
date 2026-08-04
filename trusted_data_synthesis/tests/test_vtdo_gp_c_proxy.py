from __future__ import annotations

from pathlib import Path

import pytest
import torch
from safetensors.torch import save_file

from trusted_synthesis.experiments.vtdo_experiment.phase1_gp_c_proxy import (
    _cold_start_adamw_update,
    _linear_combination,
    analyze_gp_c_proxy,
    freeze_finite_target_directions,
)


def _save(path: Path, value: float) -> dict[str, object]:
    save_file({"weight": torch.tensor([value])}, path)
    import hashlib

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"file": str(path), "sha256": digest}


def _proxy_inputs(tmp_path: Path, *, role: str = "estimation"):
    objective = _save(tmp_path / "objective.safetensors", 1.0)
    state_values = {
        ("task-a", "a"): -1.0,
        ("task-a", "b"): 0.2,
        ("task-a", "c"): 0.8,
        ("task-b", "a"): -0.6,
        ("task-b", "b"): 0.1,
        ("task-b", "c"): 0.5,
    }
    state_artifacts = []
    jackknife_artifacts = []
    for index, ((task_id, state_id), value) in enumerate(state_values.items()):
        artifact = _save(tmp_path / f"state-{index}.safetensors", value)
        state_artifacts.append(
            {
                "task_id": task_id,
                "task_type": "comparison" if task_id == "task-a" else "temporal",
                "state_id": state_id,
                **artifact,
            }
        )
        for jackknife_index, adjustment in enumerate((-0.05, 0.0, 0.05)):
            jackknife = _save(
                tmp_path / f"state-{index}-jackknife-{jackknife_index}.safetensors",
                value + adjustment,
            )
            jackknife_artifacts.append(
                {
                    "task_id": task_id,
                    "state_id": state_id,
                    "jackknife_id": f"jackknife:{task_id}:{state_id}:{jackknife_index}",
                    "excluded_realization_id": (
                        f"realization:{task_id}:{state_id}:{jackknife_index}"
                    ),
                    **jackknife,
                }
            )
    finite_plan = {
        "plan_hash": f"plan:{role}",
        "source_gradient_plan_hash": "gradient-plan",
        "beneficiary_model_state_id": "beneficiary-state",
        "beneficiary_checkpoint_hash": "beneficiary-checkpoint",
        "objective_role": role,
        "objective_record_ids": tuple(f"{role}-{index}" for index in range(16)),
        "objective_records_hash": f"objective-records:{role}",
        "task_distributions": {
            "task-a": {"a": 0.2, "b": 0.3, "c": 0.5},
            "task-b": {"a": 0.5, "b": 0.3, "c": 0.2},
        },
        "claim_boundary": "local only",
    }
    target_rows = []
    for task_id, probabilities in finite_plan["task_distributions"].items():
        raw = {state_id: state_values[(task_id, state_id)] for state_id in probabilities}
        mean = sum(probabilities[state_id] * raw[state_id] for state_id in probabilities)
        target_rows.append(
            {
                "task_id": task_id,
                "target_state_values": {
                    state_id: raw[state_id] - mean for state_id in probabilities
                },
            }
        )
    finite_report = {
        "plan_hash": f"plan:{role}",
        "report_hash": f"target:{role}",
        "source_gradient_plan_hash": "gradient-plan",
        "objective_role": role,
        "status": "passed",
        "state_targets": target_rows,
    }
    update_manifest = {
        "manifest_hash": "updates",
        "source_gradient_plan_hash": "gradient-plan",
        "state_artifacts": state_artifacts,
        "state_jackknife_artifacts": jackknife_artifacts,
        "state_uncertainty_method": (
            "leave_one_realization_out_jackknife_pseudovalues"
        ),
    }
    objective_manifest = {
        "manifest_hash": f"objective:{role}",
        "finite_target_plan_hash": f"plan:{role}",
        "local_update_manifest_hash": "updates",
        "beneficiary_checkpoint_hash": "beneficiary-checkpoint",
        "objective_role": role,
        "objective_record_ids": tuple(f"{role}-{index}" for index in range(16)),
        "objective_records_hash": f"objective-records:{role}",
        "objective_gradient_point": "post_global_update",
        "aggregate_gradient_artifact": objective,
    }
    return finite_plan, finite_report, update_manifest, objective_manifest


def test_cold_start_adamw_is_applied_before_distribution_expectation() -> None:
    left = _cold_start_adamw_update(
        {"weight": torch.tensor([1.0, 0.01])},
        learning_rate=2e-4,
        epsilon=1e-8,
        maximum_gradient_norm=1.0,
    )
    right = _cold_start_adamw_update(
        {"weight": torch.tensor([-0.2, 0.4])},
        learning_rate=2e-4,
        epsilon=1e-8,
        maximum_gradient_norm=1.0,
    )

    expected = _linear_combination([left, right], [0.25, 0.75])
    update_of_mean_gradient = _cold_start_adamw_update(
        {"weight": torch.tensor([0.1, 0.3025])},
        learning_rate=2e-4,
        epsilon=1e-8,
        maximum_gradient_norm=1.0,
    )

    assert not torch.allclose(expected["weight"], update_of_mean_gradient["weight"])


def test_gp_c_proxy_is_pi_centered_and_uses_post_global_objective(tmp_path: Path) -> None:
    inputs = _proxy_inputs(tmp_path)

    report = analyze_gp_c_proxy(
        finite_plan=inputs[0],
        finite_report=inputs[1],
        update_manifest=inputs[2],
        objective_gradient_manifest=inputs[3],
    )

    assert report["status"] == "passed"
    assert report["objective_gradient_point"] == "post_global_update"
    assert report["macro_task_spearman"] == pytest.approx(1.0)
    assert report["winner_agreement_rate"] == pytest.approx(1.0)
    for task_id, probabilities in inputs[0]["task_distributions"].items():
        rows = [row for row in report["state_rows"] if row["task_id"] == task_id]
        assert sum(
            probabilities[row["state_id"]] * row["scaled_gp_c_proxy"] for row in rows
        ) == pytest.approx(0.0)
        assert all(row["jackknife_realization_count"] == 3 for row in rows)
        assert all(row["jackknife_proxy_sample_standard_deviation"] > 0 for row in rows)


def test_validation_proxy_requires_frozen_estimation_calibration(tmp_path: Path) -> None:
    inputs = _proxy_inputs(tmp_path, role="validation")

    with pytest.raises(ValueError, match="frozen calibration"):
        analyze_gp_c_proxy(
            finite_plan=inputs[0],
            finite_report=inputs[1],
            update_manifest=inputs[2],
            objective_gradient_manifest=inputs[3],
        )


def test_finite_target_direction_uses_task_marginal_and_tangent(tmp_path: Path) -> None:
    state_a = _save(tmp_path / "a.safetensors", 2.0)
    state_b = _save(tmp_path / "b.safetensors", -2.0)
    global_update = _save(tmp_path / "global.safetensors", 0.5)
    jackknife_artifacts = []
    for state_id, value in (("a", 2.0), ("b", -2.0)):
        for index, adjustment in enumerate((-0.1, 0.0, 0.1)):
            artifact = _save(
                tmp_path / f"{state_id}-jackknife-{index}.safetensors",
                value + adjustment,
            )
            jackknife_artifacts.append(
                {
                    "task_id": "task-a",
                    "state_id": state_id,
                    "jackknife_id": f"jackknife:task-a:{state_id}:{index}",
                    "excluded_realization_id": f"realization:task-a:{state_id}:{index}",
                    **artifact,
                }
            )
    plan = {
        "plan_hash": "finite-plan",
        "source_gradient_plan_hash": "gradient-plan",
        "beneficiary_model_state_id": "beneficiary-state",
        "beneficiary_checkpoint_hash": "beneficiary-checkpoint",
        "coordinate_rows": (
            {
                "coordinate_id": "coordinate-a",
                "task_id": "task-a",
                "state_id": "a",
                "reference_state_id": "b",
                "task_marginal": 0.25,
            },
        ),
        "design_rows": (
            {
                "design_row_id": "row-a",
                "role": "orthogonal_design",
                "coordinate_weights": {"coordinate-a": 1.0},
            },
            {
                "design_row_id": "row-null",
                "role": "null_replay",
                "coordinate_weights": {},
            },
        ),
    }
    manifest = freeze_finite_target_directions(
        plan,
        {
            "manifest_hash": "updates",
            "source_gradient_plan_hash": "gradient-plan",
            "state_artifacts": (
                {"task_id": "task-a", "state_id": "a", **state_a},
                {"task_id": "task-a", "state_id": "b", **state_b},
            ),
            "state_jackknife_artifacts": tuple(jackknife_artifacts),
            "global_update_artifact": global_update,
        },
        output_dir=tmp_path,
    )

    from safetensors.torch import load_file

    direction = load_file(manifest["direction_artifacts"][0]["file"])["weight"]
    null = load_file(manifest["direction_artifacts"][1]["file"])["weight"]
    assert direction.item() == pytest.approx(0.5)
    assert null.item() == pytest.approx(0.0)
    assert manifest["jackknife_state_count"] == 2
