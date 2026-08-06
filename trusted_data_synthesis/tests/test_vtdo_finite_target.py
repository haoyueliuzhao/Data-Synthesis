from __future__ import annotations

import copy

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_finite_target import (
    DIRECTION_MANIFEST_HASH_PREFIX,
    _observation_hash,
    _verify_direction_manifest,
    analyze_finite_target,
    build_finite_target_plan,
    recover_pi_centered_state_values,
)
from trusted_synthesis.hashing import canonical_hash


def _gradient_inputs() -> tuple[dict[str, object], dict[str, object]]:
    task_distributions = {}
    state_rows = []
    for task_index in range(30):
        state_count = 3 + task_index % 3
        weights = [float(index + 1) for index in range(state_count)]
        total = sum(weights)
        probabilities = {
            f"state-{task_index}-{index}": weight / total for index, weight in enumerate(weights)
        }
        task_id = f"task-{task_index}"
        task_distributions[task_id] = {
            "probabilities": probabilities,
        }
        for state_id in probabilities:
            state_rows.append(
                {
                    "task_id": task_id,
                    "state_id": state_id,
                    "state_artifact_id": f"artifact:{task_id}:{state_id}",
                    "state_gradient_file": f"/{task_id}/{state_id}.safetensors",
                    "state_gradient_sha256": f"sha:{task_id}:{state_id}",
                }
            )
    plan: dict[str, object] = {
        "plan_hash": "gradient-plan",
        "run_role": "production_candidate",
        "numeric_contract_hash": "numeric-contract",
        "numeric_contract": {"selected_profile": {"profile_id": "test"}},
        "production_authorization_eligible": True,
        "beneficiary_model_state_id": "beneficiary-state",
        "beneficiary_checkpoint_hash": "beneficiary-checkpoint",
        "model_dir": "/model",
        "base_model_manifest_hash": "base-model-manifest",
        "beneficiary_adapter_dir": "/adapter",
        "beneficiary_adapter_tensor_sha256": "adapter-sha",
        "source_records_path": "/records.jsonl",
        "source_records_sha256": "records-sha",
        "local_optimizer_contract": {
            "contract_id": "optimizer-contract",
            "objective_gradient_mode": "deterministic_eval_with_checkpoint_wrappers",
        },
        "task_distributions": task_distributions,
        "gradient_estimation_record_ids": tuple(f"est-{index}" for index in range(16)),
        "gradient_validation_record_ids": tuple(f"val-{index}" for index in range(16)),
        "final_test_record_ids": tuple(f"auth-{index}" for index in range(16)),
    }
    task_marginal = 1.0 / 30
    report: dict[str, object] = {
        "plan_hash": "gradient-plan",
        "report_hash": "gradient-report",
        "task_count": 30,
        "state_count": len(state_rows),
        "state_rows": state_rows,
        "task_marginals": {f"task-{index}": task_marginal for index in range(30)},
        "global_gradient_artifact": {
            "file": "/global.safetensors",
            "sha256": "global-sha",
        },
    }
    return plan, report


def _plan() -> dict[str, object]:
    gradient_plan, gradient_report = _gradient_inputs()
    return build_finite_target_plan(
        gradient_plan=gradient_plan,
        gradient_report=gradient_report,
        objective_role="estimation",
        objective_record_ids=tuple(f"est-{index}" for index in range(16)),
        objective_records_hash="objective-records-hash",
        base_radius=0.08,
        block_size=8,
        design_count=3,
        design_salt="preregistered-test-salt",
    )


def _observations(plan: dict[str, object]) -> tuple[list[dict[str, object]], dict[str, float]]:
    coordinate_rows = plan["coordinate_rows"]
    assert isinstance(coordinate_rows, (list, tuple))
    true_coordinates = {
        str(row["coordinate_id"]): ((index % 11) - 5) / 1000.0
        for index, row in enumerate(coordinate_rows)
    }
    observations = []
    design_rows = plan["design_rows"]
    radii = plan["radii"]
    assert isinstance(design_rows, (list, tuple))
    assert isinstance(radii, (list, tuple))
    for row in design_rows:
        linear = sum(
            float(weight) * true_coordinates[str(coordinate_id)]
            for coordinate_id, weight in row["coordinate_weights"].items()
        )
        for radius in radii:
            radius = float(radius)
            for sign in (-1, 1):
                signed_radius = sign * radius
                objective = 0.75 + signed_radius * linear + 0.2 * signed_radius**3 * linear
                observation = {
                    "plan_hash": plan["plan_hash"],
                    "numeric_contract_hash": plan["numeric_contract_hash"],
                    "direction_manifest_hash": "direction-manifest:test",
                    "objective_role": plan["objective_role"],
                    "design_row_id": row["design_row_id"],
                    "radius": radius,
                    "sign": sign,
                    "objective_value": objective,
                    "objective_gradient_point": "post_global_update",
                    "supervised_tokens": 128,
                    "baseline_objective_value": 0.75,
                    "baseline_supervised_tokens": 128,
                    "baseline_post_global_adapter_hash": "adapter:post-global",
                    "numeric_seed": 20261131,
                }
                observation["observation_hash"] = _observation_hash(observation)
                observations.append(observation)
    return observations, true_coordinates


def test_sealed_causal_pilot_uses_frozen_protocol_and_forbids_authorization() -> None:
    gradient_plan, gradient_report = _gradient_inputs()
    task_ids = tuple(f"task-{index}" for index in range(6))
    gradient_plan["run_role"] = "sealed_causal_pilot"
    gradient_plan["production_authorization_eligible"] = False
    gradient_plan["task_distributions"] = {
        task_id: gradient_plan["task_distributions"][task_id] for task_id in task_ids
    }
    gradient_plan["numeric_contract"] = {
        "selected_profile": {"profile_id": "test"},
        "finite_target_protocol": {
            "base_radius": 0.1,
            "radii": [0.1, 0.05, 0.025],
            "block_size": 7,
            "design_count": 2,
            "finite_difference": "symmetric_central",
            "extrapolation": "two_level_richardson_O_h4",
        },
    }
    gradient_report["task_count"] = 6
    gradient_report["state_rows"] = [
        row for row in gradient_report["state_rows"] if row["task_id"] in task_ids
    ]
    gradient_report["state_count"] = len(gradient_report["state_rows"])
    gradient_report["task_marginals"] = {task_id: 1.0 / 6 for task_id in task_ids}

    plan = build_finite_target_plan(
        gradient_plan=gradient_plan,
        gradient_report=gradient_report,
        objective_role="estimation",
        objective_record_ids=tuple(f"est-{index}" for index in range(4)),
        objective_records_hash="pilot-estimation-records",
        base_radius=0.1,
        block_size=7,
        design_count=2,
        design_salt="sealed-causal-pilot",
    )

    assert plan["run_role"] == "sealed_causal_pilot"
    assert plan["production_authorization_eligible"] is False
    with pytest.raises(ValueError, match="cannot open the authorization objective"):
        build_finite_target_plan(
            gradient_plan=gradient_plan,
            gradient_report=gradient_report,
            objective_role="authorization",
            objective_record_ids=tuple(f"auth-{index}" for index in range(4)),
            objective_records_hash="pilot-authorization-records",
            base_radius=0.1,
            block_size=7,
            design_count=2,
            design_salt="sealed-causal-pilot",
        )


def test_multiradius_hadamard_target_recovers_nonuniform_support() -> None:
    plan = _plan()
    observations, expected = _observations(plan)

    report = analyze_finite_target(plan, observations)

    assert report["status"] == "passed"
    assert report["objective_gradient_point"] == "post_global_update"
    assert report["design_count"] == 3
    assert report["reconstruction_relative_error"] < 1e-8
    assert report["p95_radius_instability"] < 1e-8
    assert report["signal_to_null_ratio"] > 1e6
    assert report["coordinate_values"] == pytest.approx(expected, abs=1e-10)
    assert all(abs(float(row["weighted_target_mean"])) < 1e-10 for row in report["state_targets"])


def test_finite_target_rejects_an_incomplete_design() -> None:
    plan = _plan()
    observations, _ = _observations(plan)

    with pytest.raises(ValueError, match="matrix is incomplete"):
        analyze_finite_target(plan, observations[:-1])


def test_finite_target_rejects_state_support_outside_three_to_five() -> None:
    gradient_plan, gradient_report = _gradient_inputs()
    task_id = "task-0"
    probabilities = gradient_plan["task_distributions"][task_id]["probabilities"]
    removed = tuple(probabilities)[-1]
    del probabilities[removed]
    gradient_report["state_rows"] = [
        row
        for row in gradient_report["state_rows"]
        if not (row["task_id"] == task_id and row["state_id"] == removed)
    ]
    gradient_report["state_count"] = len(gradient_report["state_rows"])

    with pytest.raises(ValueError, match="complete 3-5-state support"):
        build_finite_target_plan(
            gradient_plan=gradient_plan,
            gradient_report=gradient_report,
            objective_role="estimation",
            objective_record_ids=tuple(f"est-{index}" for index in range(16)),
            objective_records_hash="objective-records-hash",
            design_salt="test-salt",
        )


def test_pi_centered_recovery_handles_nonuniform_probabilities() -> None:
    probabilities = {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.4}
    recovered = recover_pi_centered_state_values(
        probabilities=probabilities,
        task_marginal=0.25,
        reference_state_id="d",
        coordinate_values={
            "coordinate-a": ("a", 0.025),
            "coordinate-b": ("b", -0.0125),
            "coordinate-c": ("c", 0.05),
        },
    )

    assert sum(probabilities[key] * recovered[key] for key in probabilities) == pytest.approx(0)


def test_finite_target_plan_hash_is_fail_closed() -> None:
    plan = _plan()
    observations, _ = _observations(plan)
    tampered = copy.deepcopy(plan)
    tampered["radii"] = (0.1, 0.05, 0.025)

    with pytest.raises(ValueError, match="plan identity changed"):
        analyze_finite_target(tampered, observations)


def test_authorization_target_requires_frozen_development_gates() -> None:
    gradient_plan, gradient_report = _gradient_inputs()

    with pytest.raises(ValueError, match="frozen estimation and validation gates"):
        build_finite_target_plan(
            gradient_plan=gradient_plan,
            gradient_report=gradient_report,
            objective_role="authorization",
            objective_record_ids=tuple(f"auth-{index}" for index in range(16)),
            objective_records_hash="objective-records-hash",
            design_salt="test-salt",
        )


def test_direction_manifest_replay_is_fail_closed() -> None:
    plan = {
        "plan_hash": "finite-plan",
        "design_rows": [{"design_row_id": "design-1"}],
    }
    manifest = {
        "finite_target_plan_hash": "finite-plan",
        "direction_artifacts": [
            {
                "design_row_id": "design-1",
                "file": "/direction.safetensors",
                "sha256": "direction-sha",
            }
        ],
    }
    manifest["manifest_hash"] = canonical_hash(
        manifest,
        prefix=DIRECTION_MANIFEST_HASH_PREFIX,
    )

    assert _verify_direction_manifest(plan, manifest) == manifest["manifest_hash"]

    tampered = copy.deepcopy(manifest)
    tampered["direction_artifacts"][0]["sha256"] = "tampered"
    with pytest.raises(ValueError, match="identity changed"):
        _verify_direction_manifest(plan, tampered)
