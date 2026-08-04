from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Mapping
from typing import Literal

from .estimation import estimate_centered_contributions
from .schema import (
    CONTRIBUTION_APPROXIMATION_AUTHORIZATION_VERSION,
    GRADIENT_PROJECTION_CLAIM_BOUNDARY,
    GRADIENT_PROJECTION_ESTIMATOR_ID,
    VTDO_SCHEMA_VERSION,
    ConditionalTrajectoryDistribution,
    ContributionApproximationAuthorization,
    ContributionCalibrationContract,
    ContributionDistributionGateThresholds,
    ContributionDistributionValidationEvidence,
    ContributionEstimationManifest,
    ContributionOptimizerUpdateContract,
    ContributionRankValidationEvidence,
    contribution_approximation_authorization_id,
    contribution_calibration_contract_id,
    contribution_current_distribution_hash,
    contribution_distribution_contract_hash,
    contribution_distribution_validation_evidence_id,
    contribution_exact_distribution_contract_hash,
    contribution_optimizer_update_contract_id,
    contribution_task_population_hash,
)


def make_contribution_optimizer_update_contract(
    *,
    learning_rate: float,
    betas: tuple[float, float],
    epsilon: float,
    maximum_gradient_norm: float,
    trainable_parameter_space: str,
) -> ContributionOptimizerUpdateContract:
    values = {
        "optimizer_name": "adamw",
        "estimator_scope": "local_distribution_update_only",
        "step_count": 1,
        "cold_start": True,
        "reuse_main_optimizer_state": False,
        "learning_rate": learning_rate,
        "betas": betas,
        "epsilon": epsilon,
        "weight_decay": 0.0,
        "maximum_gradient_norm": maximum_gradient_norm,
        "gradient_accumulation_steps": 1,
        "mixed_state_batches_allowed": False,
        "trainable_parameter_space": trainable_parameter_space,
        "state_gradient_mode": "train",
        "objective_gradient_mode": "eval",
        "objective_gradient_point": "post_global_update",
        "dropout_realization_policy": "independent_seed_per_realization",
        "schema_version": VTDO_SCHEMA_VERSION,
    }
    provisional = ContributionOptimizerUpdateContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ContributionOptimizerUpdateContract(
        contract_id=contribution_optimizer_update_contract_id(provisional),
        **values,
    )


def make_contribution_calibration_contract(
    *,
    estimation_set_id: str,
    validation_set_id: str,
    authorization_set_id: str,
    calibration_artifact_hash: str,
) -> ContributionCalibrationContract:
    values = {
        "method": "global_median_absolute_scale_through_zero",
        "estimation_set_id": estimation_set_id,
        "validation_set_id": validation_set_id,
        "authorization_set_id": authorization_set_id,
        "calibration_artifact_hash": calibration_artifact_hash,
        "frozen_before_authorization_access": True,
        "authorization_may_tune": False,
        "schema_version": VTDO_SCHEMA_VERSION,
    }
    provisional = ContributionCalibrationContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ContributionCalibrationContract(
        contract_id=contribution_calibration_contract_id(provisional),
        **values,
    )


def make_contribution_distribution_validation_evidence(
    *,
    evaluation_role: Literal[
        "internal_estimation",
        "internal_validation",
        "independent_authorization",
    ],
    task_count: int,
    mean_total_variation: float,
    p95_total_variation: float,
    mean_jensen_shannon: float,
    p95_jensen_shannon: float,
    mean_update_direction_agreement: float,
    mean_absolute_target_regret: float,
    p95_absolute_target_regret: float,
    mean_normalized_target_regret: float,
    p95_normalized_target_regret: float,
    mean_attainable_gain: float,
    normalizable_task_count: int,
    normalizable_task_rate: float,
    task_type_stratified_metrics_hash: str,
    gain_quantile_metrics_hash: str,
    thresholds: ContributionDistributionGateThresholds,
) -> ContributionDistributionValidationEvidence:
    values = {
        "evaluation_role": evaluation_role,
        "task_count": task_count,
        "mean_total_variation": mean_total_variation,
        "p95_total_variation": p95_total_variation,
        "mean_jensen_shannon": mean_jensen_shannon,
        "p95_jensen_shannon": p95_jensen_shannon,
        "mean_update_direction_agreement": mean_update_direction_agreement,
        "mean_absolute_target_regret": mean_absolute_target_regret,
        "p95_absolute_target_regret": p95_absolute_target_regret,
        "mean_normalized_target_regret": mean_normalized_target_regret,
        "p95_normalized_target_regret": p95_normalized_target_regret,
        "mean_attainable_gain": mean_attainable_gain,
        "normalizable_task_count": normalizable_task_count,
        "normalizable_task_rate": normalizable_task_rate,
        "task_type_stratified_metrics_hash": task_type_stratified_metrics_hash,
        "gain_quantile_metrics_hash": gain_quantile_metrics_hash,
        "thresholds": thresholds,
        "status": "passed",
        "schema_version": VTDO_SCHEMA_VERSION,
    }
    provisional = ContributionDistributionValidationEvidence.model_construct(
        evidence_id="pending",
        **values,
    )
    return ContributionDistributionValidationEvidence(
        evidence_id=contribution_distribution_validation_evidence_id(provisional),
        **values,
    )


def make_gradient_projection_contribution_manifest(
    distribution: ConditionalTrajectoryDistribution,
    state_realizations: Mapping[str, Iterable[float]],
    *,
    beneficiary_model_state_id: str,
    beneficiary_checkpoint_hash: str,
    target_validation_set_id: str,
    authorization_set_id: str,
    target_metric_id: str,
    estimation_protocol_hash: str,
    data_isolation_contract_id: str,
    estimator_id: str,
    optimizer_contract: ContributionOptimizerUpdateContract,
    calibration_contract: ContributionCalibrationContract,
    uncertainty_penalty_coefficient: float,
) -> ContributionEstimationManifest:
    frozen = {
        state_id: tuple(float(value) for value in values)
        for state_id, values in state_realizations.items()
    }
    if set(frozen) != set(distribution.probabilities):
        raise ValueError("Gradient Projection realizations must cover pi_t exactly")
    if any(len(values) < 3 for values in frozen.values()):
        raise ValueError("Gradient Projection needs at least three realizations per state")
    if any(any(not math.isfinite(value) for value in values) for values in frozen.values()):
        raise ValueError("Gradient Projection realizations must be finite")
    counts = {state_id: len(values) for state_id, values in frozen.items()}
    deviations = {
        state_id: statistics.stdev(values) for state_id, values in frozen.items()
    }
    return estimate_centered_contributions(
        distribution,
        {state_id: statistics.fmean(values) for state_id, values in frozen.items()},
        confidences={state_id: 1.0 for state_id in frozen},
        observation_counts=counts,
        sample_standard_deviations=deviations,
        standard_errors={
            state_id: deviations[state_id] / math.sqrt(counts[state_id])
            for state_id in frozen
        },
        uncertainty_penalty_coefficient=uncertainty_penalty_coefficient,
        beneficiary_model_state_id=beneficiary_model_state_id,
        beneficiary_checkpoint_hash=beneficiary_checkpoint_hash,
        target_evaluation_distribution_id=target_validation_set_id,
        target_metric_id=target_metric_id,
        target_metric_direction="higher_is_better",
        estimator_kind="gradient_projection",
        usage_scope="production_distribution_update",
        estimation_protocol_hash=estimation_protocol_hash,
        data_isolation_contract_id=data_isolation_contract_id,
        final_test_set_id=authorization_set_id,
        estimator_id=estimator_id,
        approximation_contract_id=optimizer_contract.contract_id,
        gradient_mode_contract_id=optimizer_contract.contract_id,
        calibration_artifact_hash=calibration_contract.calibration_artifact_hash,
        state_realization_counts=counts,
    )


def make_contribution_approximation_authorization(
    *,
    analysis_report_hash: str,
    source_plan_hash: str,
    local_update_manifest_hash: str,
    beneficiary_model_state_id: str,
    beneficiary_checkpoint_hash: str,
    target_metric_id: str,
    optimizer_contract: ContributionOptimizerUpdateContract,
    calibration_contract: ContributionCalibrationContract,
    objective_partition_ids: Mapping[str, str],
    objective_partition_hashes: Mapping[str, str],
    objective_record_counts: Mapping[str, int],
    task_distributions: Mapping[str, ConditionalTrajectoryDistribution],
    state_realization_counts: Mapping[tuple[str, str], int],
    task_sampling_contract_hash: str,
    state_realization_manifest_hash: str,
    gradient_diagnostics_hash: str,
    token_region_manifest_hash: str,
    finite_target_report_hashes: Mapping[str, str],
    post_global_objective_gradient_hashes: Mapping[str, str],
    proxy_report_hashes: Mapping[str, str],
    uncertainty_penalty_coefficient: float,
    state_uncertainty_method: Literal[
        "leave_one_realization_out_jackknife_pseudovalues"
    ],
    objective_support_scaling_report_hash: str,
    gradient_realization_stability_report_hash: str,
    strict_freshness_contract_hash: str,
    internal_estimation_rank: ContributionRankValidationEvidence,
    internal_validation_rank: ContributionRankValidationEvidence,
    independent_authorization_rank: ContributionRankValidationEvidence,
    internal_estimation_distribution: ContributionDistributionValidationEvidence,
    internal_validation_distribution: ContributionDistributionValidationEvidence,
    independent_authorization_distribution: ContributionDistributionValidationEvidence,
) -> ContributionApproximationAuthorization:
    frozen_distributions = dict(task_distributions)
    if any(
        task_id != distribution.task_condition_id
        for task_id, distribution in frozen_distributions.items()
    ):
        raise ValueError("Contribution authorization distributions cross task conditions")
    task_ids = tuple(sorted(frozen_distributions))
    task_state_probabilities = {
        task_id: dict(frozen_distributions[task_id].probabilities)
        for task_id in task_ids
    }
    task_distribution_hashes = tuple(
        (
            task_id,
            contribution_current_distribution_hash(
                task_id,
                task_state_probabilities[task_id],
            ),
        )
        for task_id in task_ids
    )
    task_distribution_ids = tuple(
        (task_id, frozen_distributions[task_id].distribution_id)
        for task_id in task_ids
    )
    task_round_indices = tuple(
        (task_id, frozen_distributions[task_id].round_index)
        for task_id in task_ids
    )
    supports = tuple(
        (task_id, tuple(sorted(task_state_probabilities[task_id])))
        for task_id in task_ids
    )
    frozen_realizations = tuple(
        sorted(
            (task_id, state_id, int(count))
            for (task_id, state_id), count in state_realization_counts.items()
        )
    )
    values = {
        "authorization_version": CONTRIBUTION_APPROXIMATION_AUTHORIZATION_VERSION,
        "artifact_type": "ContributionApproximationAuthorization",
        "status": "authorized",
        "estimator_kind": "gradient_projection",
        "estimator_id": GRADIENT_PROJECTION_ESTIMATOR_ID,
        "usage_scope": "local_distribution_update_only",
        "approximation_contract_id": optimizer_contract.contract_id,
        "analysis_report_hash": analysis_report_hash,
        "source_plan_hash": source_plan_hash,
        "local_update_manifest_hash": local_update_manifest_hash,
        "beneficiary_model_state_id": beneficiary_model_state_id,
        "beneficiary_checkpoint_hash": beneficiary_checkpoint_hash,
        "target_metric_id": target_metric_id,
        "optimizer_contract": optimizer_contract,
        "objective_gradient_point": "post_global_update",
        "calibration_contract": calibration_contract,
        "objective_partition_ids": tuple(sorted(objective_partition_ids.items())),
        "objective_partition_hashes": tuple(sorted(objective_partition_hashes.items())),
        "objective_record_counts": tuple(sorted(objective_record_counts.items())),
        "objective_partitions_disjoint": True,
        "authorization_split_unopened_until_freeze": True,
        "task_condition_ids": task_ids,
        "task_population_hash": contribution_task_population_hash(task_ids),
        "task_distribution_hashes": task_distribution_hashes,
        "task_distribution_ids": task_distribution_ids,
        "task_round_indices": task_round_indices,
        "current_distribution_contract_hash": contribution_distribution_contract_hash(
            dict(task_distribution_hashes)
        ),
        "exact_distribution_contract_hash": contribution_exact_distribution_contract_hash(
            dict(task_distribution_ids),
            dict(task_round_indices),
            dict(task_distribution_hashes),
        ),
        "task_state_supports": supports,
        "state_realization_counts": frozen_realizations,
        "task_count": len(task_ids),
        "state_count": sum(len(states) for _, states in supports),
        "task_sampling_contract_hash": task_sampling_contract_hash,
        "state_realization_manifest_hash": state_realization_manifest_hash,
        "gradient_diagnostics_hash": gradient_diagnostics_hash,
        "token_region_manifest_hash": token_region_manifest_hash,
        "finite_target_method": "multi_radius_block_hadamard_richardson",
        "finite_target_report_hashes": tuple(
            sorted(finite_target_report_hashes.items())
        ),
        "post_global_objective_gradient_hashes": tuple(
            sorted(post_global_objective_gradient_hashes.items())
        ),
        "proxy_report_hashes": tuple(sorted(proxy_report_hashes.items())),
        "uncertainty_penalty_coefficient": uncertainty_penalty_coefficient,
        "state_uncertainty_method": state_uncertainty_method,
        "objective_support_scaling_report_hash": objective_support_scaling_report_hash,
        "gradient_realization_stability_report_hash": (
            gradient_realization_stability_report_hash
        ),
        "finite_target_reports_passed": True,
        "post_global_objective_gradients_verified": True,
        "strict_freshness_contract_hash": strict_freshness_contract_hash,
        "strict_identity_validated": True,
        "internal_estimation_rank": internal_estimation_rank,
        "internal_validation_rank": internal_validation_rank,
        "independent_authorization_rank": independent_authorization_rank,
        "internal_estimation_distribution": internal_estimation_distribution,
        "internal_validation_distribution": internal_validation_distribution,
        "independent_authorization_distribution": independent_authorization_distribution,
        "claim_boundary": GRADIENT_PROJECTION_CLAIM_BOUNDARY,
        "schema_version": VTDO_SCHEMA_VERSION,
    }
    provisional = ContributionApproximationAuthorization.model_construct(
        authorization_id="pending",
        **values,
    )
    return ContributionApproximationAuthorization(
        authorization_id=contribution_approximation_authorization_id(provisional),
        **values,
    )
