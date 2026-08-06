from __future__ import annotations

import copy

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_causal_pilot import (
    PILOT_REPORT_PREFIX,
    PREREQUISITE_REPORT_PREFIX,
    analyze_causal_pilot,
    analyze_prerequisite_failure,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_numeric_execution import (
    EXECUTION_CONTRACT_HASH_PREFIX,
    EXECUTION_CONTRACT_VERSION,
    EXPECTED_PROFILE,
    EXPECTED_PROFILE_ALGORITHM_CONTRACT,
    EXPECTED_TASK_SET_ID,
    FINITE_TARGET_PROTOCOL,
    NUMERIC_THRESHOLDS,
    SEALED_CAUSAL_PILOT_ROLE,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_finite_target import (
    FINITE_TARGET_VERSION,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_gp_c_proxy import (
    GP_C_PROXY_VERSION,
)
from trusted_synthesis.hashing import canonical_hash


def _contract() -> dict[str, object]:
    value: dict[str, object] = {
        "contract_version": EXECUTION_CONTRACT_VERSION,
        "run_role": SEALED_CAUSAL_PILOT_ROLE,
        "source_v18": {"report_hash": "v18-report"},
        "source_gradient_plan": {"plan_hash": "source-gradient-plan"},
        "source_support": {
            "plan_hash": "source-support-plan",
            "objective_partition_ids": {
                role: [f"{role}-{index}" for index in range(4)]
                for role in ("estimation", "validation", "authorization")
            },
        },
        "frozen_inputs": {"target_records": {"sha256": "records"}},
        "selected_profile": EXPECTED_PROFILE,
        "profile_algorithm_contract": EXPECTED_PROFILE_ALGORITHM_CONTRACT,
        "numeric_thresholds": NUMERIC_THRESHOLDS,
        "finite_target_protocol": FINITE_TARGET_PROTOCOL,
        "task_set_id": EXPECTED_TASK_SET_ID,
        "task_ids": [f"task-{index}" for index in range(6)],
        "task_count": 6,
        "state_count": 20,
        "state_realization_count": 60,
        "allowed_objective_roles": ["estimation", "validation"],
        "authorization_objective_access": "forbidden",
        "production_authorization_eligible": False,
        "success_transition": "launch_fresh_30_task_independent_authorization_study",
        "failure_transition": "retain_contribution_zero_and_investigate_estimator_bias",
        "claim_boundary": "pilot only",
    }
    value["contract_hash"] = canonical_hash(
        value,
        prefix=EXECUTION_CONTRACT_HASH_PREFIX,
    )
    return value


def _proxy_report(
    role: str,
    contract: dict[str, object],
    *,
    reverse_proxy: bool = False,
) -> dict[str, object]:
    state_rows = []
    for task_index, state_count in enumerate((3, 3, 3, 3, 4, 4)):
        target = [float(index - (state_count - 1) / 2) for index in range(state_count)]
        proxy = list(reversed(target)) if reverse_proxy else target
        for state_index in range(state_count):
            state_rows.append(
                {
                    "task_id": f"task-{task_index}",
                    "task_type": f"type-{task_index}",
                    "state_id": f"state-{state_index}",
                    "current_probability": 1.0 / state_count,
                    "scaled_gp_c_proxy": proxy[state_index],
                    "finite_target": target[state_index],
                }
            )
    report: dict[str, object] = {
        "experiment_version": GP_C_PROXY_VERSION,
        "artifact_type": "PostGlobalGPCProxyReport",
        "run_role": SEALED_CAUSAL_PILOT_ROLE,
        "numeric_contract_hash": contract["contract_hash"],
        "numeric_profile": EXPECTED_PROFILE,
        "production_authorization_eligible": False,
        "finite_target_plan_hash": f"finite-plan:{role}",
        "finite_target_report_hash": f"finite-report:{role}",
        "source_gradient_plan_hash": "gradient-plan",
        "beneficiary_model_state_id": "beneficiary-state",
        "beneficiary_checkpoint_hash": "beneficiary-checkpoint",
        "local_update_manifest_hash": "local-updates",
        "objective_gradient_manifest_hash": f"objective-gradient:{role}",
        "objective_role": role,
        "objective_record_ids": [f"{role}-{index}" for index in range(4)],
        "objective_records_hash": f"objective-records:{role}",
        "objective_record_count": 4,
        "objective_gradient_point": "post_global_update",
        "calibration_source": (
            "fitted_on_estimation_only" if role == "estimation" else "frozen_estimation_scale"
        ),
        "calibration_report_hash": (
            _proxy_report("estimation", contract)["report_hash"] if role == "validation" else None
        ),
        "fitted_estimation_scale": 1.0 if role == "estimation" else None,
        "applied_calibration_scale": 1.0,
        "orientation_before_calibration": "aligned",
        "macro_task_spearman": -1.0 if reverse_proxy else 1.0,
        "winner_agreement_rate": 0.0 if reverse_proxy else 1.0,
        "mean_normalized_residual_rms": 2.0 if reverse_proxy else 0.0,
        "task_type_fidelity": {},
        "task_rows": [],
        "state_rows": state_rows,
        "state_uncertainty_method": "test",
        "status": "passed",
        "claim_boundary": "pilot only",
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_post_global_gp_c_proxy_report:",
    )
    return report


def _finite_report(role: str, contract: dict[str, object]) -> dict[str, object]:
    report: dict[str, object] = {
        "experiment_version": FINITE_TARGET_VERSION,
        "artifact_type": "GradientProjectionFiniteTargetReport",
        "run_role": SEALED_CAUSAL_PILOT_ROLE,
        "numeric_contract_hash": contract["contract_hash"],
        "numeric_profile": EXPECTED_PROFILE,
        "production_authorization_eligible": False,
        "plan_hash": f"finite-plan:{role}",
        "source_gradient_plan_hash": "gradient-plan",
        "source_gradient_report_hash": "gradient-report",
        "beneficiary_model_state_id": "beneficiary-state",
        "beneficiary_checkpoint_hash": "beneficiary-checkpoint",
        "objective_role": role,
        "objective_record_ids": [f"{role}-{index}" for index in range(4)],
        "objective_records_hash": f"objective-records:{role}",
        "objective_record_count": 4,
        "objective_gradient_point": "post_global_update",
        "direction_manifest_hash": f"direction-manifest:{role}",
        "baseline_post_global_adapter_hash": "baseline-adapter",
        "observation_manifest_hash": f"observations:{role}",
        "observation_count": 204,
        "coordinate_count": 14,
        "design_count": 2,
        "radii": [0.1, 0.05, 0.025],
        "reconstruction_relative_error": 0.5,
        "maximum_reconstruction_relative_error": 0.1,
        "mean_radius_instability": 0.7,
        "p95_radius_instability": 1.5,
        "maximum_p95_radius_instability": 0.25,
        "signal_rms": 0.001,
        "null_replay_rms": 0.0,
        "signal_to_null_ratio": 1e9,
        "minimum_signal_to_null_ratio": 3.0,
        "mean_cross_design_coordinate_variance": 0.0,
        "coordinate_values": {},
        "coordinate_cross_design_variances": {},
        "state_targets": [],
        "status": "failed",
        "authorization_prerequisite_report_hashes": {},
        "development_gate_eligible": False,
        "authorization_access_granted": False,
        "claim_boundary": "pilot only",
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_finite_target_report:",
    )
    return report


def test_prerequisite_failure_closes_gp_c_without_authorization() -> None:
    contract = _contract()
    report = analyze_prerequisite_failure(
        execution_contract=contract,
        estimation_finite_report=_finite_report("estimation", contract),
        validation_finite_report=_finite_report("validation", contract),
    )

    assert report["status"] == "blocked_prerequisite"
    assert report["pilot_gate_passed"] is False
    assert report["gp_c_executed"] is False
    assert report["contribution_approximation_authorized"] is False
    assert report["authorization_objective_access"] == "forbidden"
    assert report["allowed_next_stage"] == contract["failure_transition"]
    assert report["diagnostics"]["estimation"]["failure_reasons"] == (
        "reconstruction_relative_error_exceeded",
        "p95_radius_instability_exceeded",
    )
    payload = dict(report)
    observed = payload.pop("report_hash")
    assert observed == canonical_hash(payload, prefix=PREREQUISITE_REPORT_PREFIX)


def test_prerequisite_failure_rejects_incomplete_finite_target() -> None:
    contract = _contract()
    validation = _finite_report("validation", contract)
    validation["observation_count"] = 203
    validation["report_hash"] = canonical_hash(
        {key: value for key, value in validation.items() if key != "report_hash"},
        prefix="finance_finite_target_report:",
    )

    with pytest.raises(ValueError, match="finite target is incomplete"):
        analyze_prerequisite_failure(
            execution_contract=contract,
            estimation_finite_report=_finite_report("estimation", contract),
            validation_finite_report=validation,
        )


def test_causal_pilot_passes_without_authorizing_production() -> None:
    contract = _contract()
    report = analyze_causal_pilot(
        execution_contract=contract,
        estimation_proxy_report=_proxy_report("estimation", contract),
        validation_proxy_report=_proxy_report("validation", contract),
    )

    assert report["status"] == "passed"
    assert report["pilot_gate_passed"] is True
    assert report["contribution_approximation_authorized"] is False
    assert report["production_authorization_eligible"] is False
    assert report["authorization_objective_access"] == "forbidden"
    assert report["allowed_next_stage"] == contract["success_transition"]
    payload = dict(report)
    observed = payload.pop("report_hash")
    assert observed == canonical_hash(payload, prefix=PILOT_REPORT_PREFIX)


def test_causal_pilot_failure_retains_zero_contribution() -> None:
    contract = _contract()
    report = analyze_causal_pilot(
        execution_contract=contract,
        estimation_proxy_report=_proxy_report("estimation", contract),
        validation_proxy_report=_proxy_report(
            "validation",
            contract,
            reverse_proxy=True,
        ),
    )

    assert report["status"] == "failed"
    assert report["pilot_gate_passed"] is False
    assert report["contribution_approximation_authorized"] is False
    assert report["allowed_next_stage"] == contract["failure_transition"]


def test_causal_pilot_rejects_tampered_proxy_identity() -> None:
    contract = _contract()
    validation = _proxy_report("validation", contract)
    tampered = copy.deepcopy(validation)
    tampered["applied_calibration_scale"] = 2.0

    with pytest.raises(ValueError, match="identity changed"):
        analyze_causal_pilot(
            execution_contract=contract,
            estimation_proxy_report=_proxy_report("estimation", contract),
            validation_proxy_report=tampered,
        )


def test_causal_pilot_rejects_unfrozen_objective_partition() -> None:
    contract = _contract()
    estimation = _proxy_report("estimation", contract)
    estimation["objective_record_ids"] = [
        "unknown",
        "estimation-1",
        "estimation-2",
        "estimation-3",
    ]
    estimation["report_hash"] = canonical_hash(
        {key: value for key, value in estimation.items() if key != "report_hash"},
        prefix="finance_post_global_gp_c_proxy_report:",
    )

    with pytest.raises(ValueError, match="partition differs from contract"):
        analyze_causal_pilot(
            execution_contract=contract,
            estimation_proxy_report=estimation,
            validation_proxy_report=_proxy_report("validation", contract),
        )
