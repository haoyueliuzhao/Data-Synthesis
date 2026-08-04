from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from trusted_synthesis.core.vtdo import (
    ConditionalTrajectoryDistribution,
    ContributionApproximationAuthorization,
    ContributionDistributionGateThresholds,
    ContributionEstimationManifest,
    contribution_materialization_protocol_hash,
    make_conditional_distribution,
    make_contribution_approximation_authorization,
    make_contribution_calibration_contract,
    make_contribution_distribution_validation_evidence,
    make_contribution_optimizer_update_contract,
    make_contribution_rank_validation_evidence,
    make_gradient_projection_contribution_manifest,
)


@dataclass(frozen=True)
class GradientProjectionTestBundle:
    manifest: ContributionEstimationManifest
    authorization: ContributionApproximationAuthorization


def make_test_gradient_projection_bundle(
    distribution: ConditionalTrajectoryDistribution,
    state_values: Mapping[str, float],
    *,
    beneficiary_model_state_id: str,
    beneficiary_checkpoint_hash: str = "checkpoint:test-beneficiary",
    target_metric_id: str = "negative_supervised_token_nll",
) -> GradientProjectionTestBundle:
    state_ids = tuple(sorted(distribution.probabilities))
    if not 3 <= len(state_ids) <= 5:
        raise ValueError("production Gradient Projection tests require 3-5 states")
    if set(state_values) != set(state_ids):
        raise ValueError("test Gradient values must cover the current support")

    optimizer = make_contribution_optimizer_update_contract(
        learning_rate=2e-4,
        betas=(0.9, 0.999),
        epsilon=1e-8,
        maximum_gradient_norm=1.0,
        trainable_parameter_space="lora_adapter_parameters",
    )
    calibration = make_contribution_calibration_contract(
        estimation_set_id="objective:estimation",
        validation_set_id="objective:validation",
        authorization_set_id="objective:authorization",
        calibration_artifact_hash="calibration:test-frozen",
    )
    realizations = {
        state_id: (
            float(state_values[state_id]) - 0.001,
            float(state_values[state_id]),
            float(state_values[state_id]) + 0.001,
        )
        for state_id in state_ids
    }
    task_ids = tuple(
        sorted(
            (
                distribution.task_condition_id,
                *(f"task:authorization:{index:02d}" for index in range(29)),
            )
        )
    )
    task_distributions: dict[str, ConditionalTrajectoryDistribution] = {}
    realization_counts: dict[tuple[str, str], int] = {}
    for task_id in task_ids:
        if task_id == distribution.task_condition_id:
            probabilities = dict(distribution.probabilities)
        else:
            dummy_states = tuple(f"{task_id}:state:{index}" for index in range(3))
            probabilities = {
                dummy_states[0]: 0.5,
                dummy_states[1]: 0.3,
                dummy_states[2]: 0.2,
            }
        task_distributions[task_id] = (
            distribution
            if task_id == distribution.task_condition_id
            else make_conditional_distribution(
                task_id,
                probabilities,
                round_index=distribution.round_index,
            )
        )
        realization_counts.update(
            {(task_id, state_id): 3 for state_id in probabilities}
        )

    def rank_evidence(role):
        return make_contribution_rank_validation_evidence(
            evaluation_role=role,
            macro_task_spearman=0.85,
            macro_task_spearman_ci95=(0.70, 0.95),
            macro_pairwise_concordance=0.85,
            macro_pairwise_concordance_ci95=(0.70, 0.95),
            winner_agreement_rate=0.90,
            macro_spearman_p_value=0.001,
            macro_pairwise_concordance_p_value=0.001,
        )

    thresholds = ContributionDistributionGateThresholds(
        maximum_mean_total_variation=0.10,
        maximum_p95_total_variation=0.15,
        maximum_mean_jensen_shannon=0.05,
        maximum_p95_jensen_shannon=0.08,
        minimum_update_direction_agreement=0.90,
        maximum_mean_absolute_target_regret=0.05,
        maximum_p95_absolute_target_regret=0.08,
        maximum_mean_normalized_target_regret=0.20,
        maximum_p95_normalized_target_regret=0.30,
        minimum_mean_attainable_gain=0.01,
        minimum_normalizable_attainable_gain=0.01,
        minimum_normalizable_task_rate=0.80,
    )

    def distribution_evidence(role):
        return make_contribution_distribution_validation_evidence(
            evaluation_role=role,
            task_count=30,
            mean_total_variation=0.02,
            p95_total_variation=0.04,
            mean_jensen_shannon=0.01,
            p95_jensen_shannon=0.02,
            mean_update_direction_agreement=0.95,
            mean_absolute_target_regret=0.01,
            p95_absolute_target_regret=0.02,
            mean_normalized_target_regret=0.05,
            p95_normalized_target_regret=0.10,
            mean_attainable_gain=0.10,
            normalizable_task_count=30,
            normalizable_task_rate=1.0,
            task_type_stratified_metrics_hash=f"task-strata:{role}",
            gain_quantile_metrics_hash=f"gain-quantiles:{role}",
            thresholds=thresholds,
        )

    authorization = make_contribution_approximation_authorization(
        analysis_report_hash="analysis:test-passed",
        source_plan_hash="plan:test-frozen",
        local_update_manifest_hash="local-update:test-frozen",
        beneficiary_model_state_id=beneficiary_model_state_id,
        beneficiary_checkpoint_hash=beneficiary_checkpoint_hash,
        target_metric_id=target_metric_id,
        optimizer_contract=optimizer,
        calibration_contract=calibration,
        objective_partition_ids={
            "estimation": "objective:estimation",
            "validation": "objective:validation",
            "authorization": "objective:authorization",
        },
        objective_partition_hashes={
            "estimation": "objective-hash:estimation",
            "validation": "objective-hash:validation",
            "authorization": "objective-hash:authorization",
        },
        objective_record_counts={
            "estimation": 16,
            "validation": 16,
            "authorization": 16,
        },
        task_distributions=task_distributions,
        state_realization_counts=realization_counts,
        task_sampling_contract_hash="sampling:test-stratified-salted",
        state_realization_manifest_hash="realizations:test-independent",
        gradient_diagnostics_hash="gradient-diagnostics:test-passed",
        token_region_manifest_hash="token-regions:test-passed",
        finite_target_report_hashes={
            "estimation": "finite-target:estimation",
            "validation": "finite-target:validation",
            "authorization": "finite-target:authorization",
        },
        post_global_objective_gradient_hashes={
            "estimation": "post-global-gradient:estimation",
            "validation": "post-global-gradient:validation",
            "authorization": "post-global-gradient:authorization",
        },
        proxy_report_hashes={
            "estimation": "proxy-report:estimation",
            "validation": "proxy-report:validation",
            "authorization": "proxy-report:authorization",
        },
        uncertainty_penalty_coefficient=1.0,
        state_uncertainty_method=(
            "leave_one_realization_out_jackknife_pseudovalues"
        ),
        objective_support_scaling_report_hash="support-scaling:test-passed",
        gradient_realization_stability_report_hash="realization-stability:test-passed",
        strict_freshness_contract_hash="freshness:test-strict",
        internal_estimation_rank=rank_evidence("internal_estimation"),
        internal_validation_rank=rank_evidence("internal_validation"),
        independent_authorization_rank=rank_evidence("independent_authorization"),
        internal_estimation_distribution=distribution_evidence("internal_estimation"),
        internal_validation_distribution=distribution_evidence("internal_validation"),
        independent_authorization_distribution=distribution_evidence(
            "independent_authorization"
        ),
    )
    manifest = make_gradient_projection_contribution_manifest(
        distribution,
        realizations,
        beneficiary_model_state_id=beneficiary_model_state_id,
        beneficiary_checkpoint_hash=beneficiary_checkpoint_hash,
        target_validation_set_id="objective:validation",
        authorization_set_id="objective:authorization",
        target_metric_id=target_metric_id,
        estimation_protocol_hash=contribution_materialization_protocol_hash(
            authorization
        ),
        data_isolation_contract_id=authorization.strict_freshness_contract_hash,
        estimator_id=authorization.estimator_id,
        optimizer_contract=optimizer,
        calibration_contract=calibration,
        uncertainty_penalty_coefficient=1.0,
    )
    return GradientProjectionTestBundle(
        manifest=manifest,
        authorization=authorization,
    )
