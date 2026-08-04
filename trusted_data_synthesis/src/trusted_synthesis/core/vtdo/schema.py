from __future__ import annotations

import math
from collections.abc import Mapping
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

VTDO_SCHEMA_VERSION = "vtdo.v12"
VTDO_ALGORITHM_ID = "anchored_energy_valid_trajectory_distribution_refinement"
VTDO_ALGORITHM_VERSION = "aevtdr.v7"
CONTRIBUTION_APPROXIMATION_AUTHORIZATION_VERSION = (
    "finance_contribution_authorization.v4"
)
GRADIENT_PROJECTION_ESTIMATOR_ID = "gp_c_post_global_local_adamw_v3"
GRADIENT_PROJECTION_CLAIM_BOUNDARY = (
    "Authorized only for one local state-homogeneous cold-start AdamW VTDO "
    "distribution update at the frozen beneficiary checkpoint. The authorization "
    "does not cover optimizer continuation, mixed-state batches, multi-step Student "
    "training, or a different task population."
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ValidityRegion(str, Enum):
    ACCEPTED = "accepted"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"


class ValidityThresholds(FrozenModel):
    reject_below: float = Field(ge=0, le=1)
    accept_at_or_above: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_order(self) -> ValidityThresholds:
        if self.reject_below >= self.accept_at_or_above:
            raise ValueError("validity thresholds require delta_reject < delta_accept")
        return self


class VTDORoleContract(FrozenModel):
    """Freeze Explorer, Materializer, beneficiary, and final Student identities."""

    contract_id: str = Field(min_length=1)
    explorer_provider_id: str = Field(min_length=1)
    materialization_provider_id: str = Field(min_length=1)
    materialization_policy: Literal["independent_regeneration"]
    beneficiary_model_state_id: str = Field(min_length=1)
    final_student_model_id: str = Field(min_length=1)
    separation_mode: Literal["strict_distinct", "declared_shared"] = "strict_distinct"
    shared_role_justification_hash: str | None = None
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> VTDORoleContract:
        if self.separation_mode not in {"strict_distinct", "declared_shared"}:
            raise ValueError("unknown VTDO role-separation mode")
        identities = (
            self.explorer_provider_id,
            self.beneficiary_model_state_id,
            self.final_student_model_id,
        )
        if self.separation_mode == "strict_distinct" and self.materialization_provider_id in {
            self.beneficiary_model_state_id,
            self.final_student_model_id,
        }:
            raise ValueError(
                "strict VTDO materialization cannot reuse beneficiary or Student identities"
            )
        if self.separation_mode == "strict_distinct":
            if len(set(identities)) != len(identities):
                raise ValueError("strict VTDO roles must have distinct identities")
            if self.shared_role_justification_hash is not None:
                raise ValueError("strict VTDO roles cannot carry a sharing justification")
        elif not self.shared_role_justification_hash:
            raise ValueError("declared shared VTDO roles require a justification hash")
        if self.contract_id != vtdo_role_contract_id(self):
            raise ValueError("VTDO role contract identity is invalid")
        return self


class StateValidityEstimate(FrozenModel):
    estimate_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    attempted_trajectory_count: int = Field(ge=1)
    valid_trajectory_count: int = Field(ge=0)
    estimated_validity: float = Field(ge=0, le=1)
    confidence_lower: float = Field(ge=0, le=1)
    confidence_upper: float = Field(ge=0, le=1)
    mean_component_validity: dict[str, float] = Field(min_length=1)
    thresholds: ValidityThresholds
    classification_statistic: str = "posterior_mean"
    region: ValidityRegion
    estimator_id: str = "beta_binomial_state_validity"
    estimator_version: str = "1.0.0"
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_estimate(self) -> StateValidityEstimate:
        if self.valid_trajectory_count > self.attempted_trajectory_count:
            raise ValueError("valid state trajectories cannot exceed attempts")
        if any(
            not component or not 0.0 <= value <= 1.0
            for component, value in self.mean_component_validity.items()
        ):
            raise ValueError("state component validity must be named and lie in [0, 1]")
        if self.confidence_lower > self.estimated_validity:
            raise ValueError("validity lower bound exceeds its estimate")
        if self.confidence_upper < self.estimated_validity:
            raise ValueError("validity upper bound is below its estimate")
        expected_region = validity_region(self.estimated_validity, self.thresholds)
        if self.region != expected_region:
            raise ValueError("state validity region is inconsistent")
        if self.estimate_id != state_validity_estimate_id(self):
            raise ValueError("state validity estimate identity is invalid")
        return self


class ConditionalTrajectoryDistribution(FrozenModel):
    distribution_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    round_index: int = Field(ge=0)
    probabilities: dict[str, float] = Field(min_length=1)
    source_distribution_id: str | None = None
    estimator_manifest_hash: str | None = None
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_distribution(self) -> ConditionalTrajectoryDistribution:
        _validate_probability_map(self.probabilities, "trajectory distribution")
        if self.distribution_id != conditional_distribution_id(self):
            raise ValueError("conditional trajectory distribution identity is invalid")
        return self


class TaskConditionedTrajectoryPolicy(FrozenModel):
    """d_t(x,z) = mu(x) pi_t(z|x), with mu frozen across updates."""

    policy_id: str = Field(min_length=1)
    round_index: int = Field(ge=0)
    task_marginal: dict[str, float] = Field(min_length=1)
    conditionals: dict[str, ConditionalTrajectoryDistribution] = Field(min_length=1)
    source_policy_id: str | None = None
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_policy(self) -> TaskConditionedTrajectoryPolicy:
        _validate_probability_map(self.task_marginal, "fixed task marginal")
        if set(self.conditionals) != set(self.task_marginal):
            raise ValueError("conditional distributions must cover the fixed task marginal")
        if any(
            condition_id != distribution.task_condition_id
            for condition_id, distribution in self.conditionals.items()
        ):
            raise ValueError("conditional distribution is stored under another task condition")
        if any(
            distribution.round_index != self.round_index
            for distribution in self.conditionals.values()
        ):
            raise ValueError("all conditional distributions must share the policy round")
        if self.policy_id != task_conditioned_policy_id(self):
            raise ValueError("task-conditioned trajectory policy identity is invalid")
        return self


class CoveragePrior(FrozenModel):
    prior_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    probabilities: dict[str, float] = Field(min_length=1)
    policy: str = Field(min_length=1)
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_prior(self) -> CoveragePrior:
        _validate_probability_map(self.probabilities, "coverage prior")
        if self.prior_id != coverage_prior_id(self):
            raise ValueError("coverage prior identity is invalid")
        return self


class ContributionEstimate(FrozenModel):
    estimate_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    raw_marginal_gain: float
    confidence: float = Field(ge=0, le=1)
    sample_standard_deviation: float = Field(ge=0)
    standard_error: float = Field(ge=0)
    centered_contribution: float
    uncertainty_penalty: float = Field(ge=0)
    conservative_raw_marginal_gain: float
    conservative_centered_contribution: float
    current_probability: float = Field(gt=0, le=1)
    observation_count: int = Field(ge=1)
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_estimate(self) -> ContributionEstimate:
        numeric = (
            self.raw_marginal_gain,
            self.sample_standard_deviation,
            self.standard_error,
            self.centered_contribution,
            self.uncertainty_penalty,
            self.conservative_raw_marginal_gain,
            self.conservative_centered_contribution,
            self.current_probability,
        )
        if any(not math.isfinite(value) for value in numeric):
            raise ValueError("contribution estimate values must be finite")
        if self.estimate_id != contribution_estimate_id(self):
            raise ValueError("contribution estimate identity is invalid")
        return self


class ContributionEstimationManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    distribution_id: str = Field(min_length=1)
    beneficiary_model_state_id: str = Field(min_length=1)
    beneficiary_checkpoint_hash: str = Field(min_length=1)
    target_evaluation_distribution_id: str = Field(min_length=1)
    target_metric_id: str = Field(min_length=1)
    target_metric_direction: Literal["higher_is_better"]
    estimator_kind: Literal[
        "synthetic_oracle",
        "finite_intervention",
        "local_probe",
        "gradient_projection",
    ]
    usage_scope: Literal[
        "synthetic_operator_control",
        "intervention_validation",
        "production_distribution_update",
    ]
    estimation_protocol_hash: str = Field(min_length=1)
    data_isolation_contract_id: str = Field(min_length=1)
    final_test_set_id: str = Field(min_length=1)
    estimator_id: str = Field(min_length=1)
    approximation_contract_id: str | None = None
    gradient_mode_contract_id: str | None = None
    calibration_artifact_hash: str | None = None
    state_realization_counts: tuple[tuple[str, int], ...] = ()
    uncertainty_statistic: Literal["sample_standard_deviation"]
    uncertainty_penalty_coefficient: float = Field(ge=0)
    production_contribution_field: Literal["conservative_centered_contribution"]
    estimates: tuple[ContributionEstimate, ...] = Field(min_length=1)
    weighted_centered_mean: float
    weighted_conservative_centered_mean: float
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> ContributionEstimationManifest:
        expected_scope = {
            "synthetic_oracle": "synthetic_operator_control",
            "finite_intervention": "intervention_validation",
            "local_probe": "intervention_validation",
            "gradient_projection": "production_distribution_update",
        }[self.estimator_kind]
        if self.usage_scope != expected_scope:
            raise ValueError("Contribution estimator kind and usage scope disagree")
        if self.estimator_kind == "gradient_projection":
            if not all(
                (
                    self.approximation_contract_id,
                    self.gradient_mode_contract_id,
                    self.calibration_artifact_hash,
                )
            ):
                raise ValueError("production Gradient Projection must freeze all contracts")
            if self.uncertainty_penalty_coefficient <= 0:
                raise ValueError("production Gradient Projection requires uncertainty control")
            realization_counts = dict(self.state_realization_counts)
            if len(realization_counts) != len(self.state_realization_counts):
                raise ValueError("Gradient Projection contains duplicate state realizations")
            if set(realization_counts) != {item.state_id for item in self.estimates}:
                raise ValueError("Gradient Projection realizations do not cover state support")
            if any(not 3 <= value <= 5 for value in realization_counts.values()):
                raise ValueError(
                    "Gradient Projection requires 3-5 realizations per state"
                )
            if any(
                item.observation_count != realization_counts[item.state_id]
                for item in self.estimates
            ):
                raise ValueError(
                    "Gradient Projection observation counts do not replay realizations"
                )
            if tuple(sorted(self.state_realization_counts)) != self.state_realization_counts:
                raise ValueError("Gradient Projection realization counts are not canonical")
        elif self.estimator_kind == "local_probe":
            if any(
                value is not None
                for value in (
                    self.approximation_contract_id,
                    self.gradient_mode_contract_id,
                    self.calibration_artifact_hash,
                )
            ) or self.state_realization_counts:
                raise ValueError("diagnostic local Probe cannot claim Gradient contracts")
            if self.uncertainty_penalty_coefficient <= 0:
                raise ValueError("diagnostic local Probe requires a positive uncertainty penalty")
            if any(item.observation_count < 2 for item in self.estimates):
                raise ValueError("diagnostic local Probe requires at least two seeds per state")
        else:
            if any(
                value is not None
                for value in (
                    self.approximation_contract_id,
                    self.gradient_mode_contract_id,
                    self.calibration_artifact_hash,
                )
            ) or self.state_realization_counts:
                raise ValueError("non-Gradient Contribution cannot carry Gradient contracts")
            if not math.isclose(self.uncertainty_penalty_coefficient, 0.0, abs_tol=1e-12):
                raise ValueError("non-Probe Contribution cannot apply the Probe uncertainty policy")
        state_ids = [item.state_id for item in self.estimates]
        if len(state_ids) != len(set(state_ids)):
            raise ValueError("contribution manifest contains duplicate states")
        if not math.isclose(
            sum(item.current_probability for item in self.estimates),
            1.0,
            abs_tol=1e-9,
        ):
            raise ValueError("contribution probabilities must form the current distribution")
        raw_mean = sum(item.current_probability * item.raw_marginal_gain for item in self.estimates)
        if any(
            not math.isclose(
                item.centered_contribution,
                item.raw_marginal_gain - raw_mean,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            for item in self.estimates
        ):
            raise ValueError("centered Contribution does not replay from raw gains and pi_t")
        if any(
            not math.isclose(
                item.uncertainty_penalty,
                self.uncertainty_penalty_coefficient * item.sample_standard_deviation,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            or not math.isclose(
                item.conservative_raw_marginal_gain,
                item.raw_marginal_gain - item.uncertainty_penalty,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            for item in self.estimates
        ):
            raise ValueError("conservative Contribution does not replay from uncertainty")
        conservative_mean = sum(
            item.current_probability * item.conservative_raw_marginal_gain
            for item in self.estimates
        )
        if any(
            not math.isclose(
                item.conservative_centered_contribution,
                item.conservative_raw_marginal_gain - conservative_mean,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            for item in self.estimates
        ):
            raise ValueError("conservative Contribution is not centered under pi_t")
        expected_mean = sum(
            item.current_probability * item.centered_contribution for item in self.estimates
        )
        if not math.isclose(self.weighted_centered_mean, expected_mean, abs_tol=1e-12):
            raise ValueError("contribution centered mean is inconsistent")
        if not math.isclose(self.weighted_centered_mean, 0.0, abs_tol=1e-12):
            raise ValueError("centered contributions must have zero current-distribution mean")
        expected_conservative_mean = sum(
            item.current_probability * item.conservative_centered_contribution
            for item in self.estimates
        )
        if not math.isclose(
            self.weighted_conservative_centered_mean,
            expected_conservative_mean,
            abs_tol=1e-12,
        ):
            raise ValueError("conservative centered mean is inconsistent")
        if not math.isclose(
            self.weighted_conservative_centered_mean,
            0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("conservative contributions must have zero pi_t mean")
        if self.manifest_id != contribution_manifest_id(self):
            raise ValueError("contribution manifest identity is invalid")
        return self


class ContributionRankValidationEvidence(FrozenModel):
    """One independently measured rank-preservation gate for a Probe estimand."""

    evidence_id: str = Field(min_length=1)
    evaluation_role: Literal[
        "cross_seed_stability",
        "independent_final_test",
        "heldout_final_test",
        "internal_estimation",
        "internal_validation",
        "independent_authorization",
    ]
    macro_task_spearman: float = Field(ge=-1, le=1)
    macro_task_spearman_ci95: tuple[float, float]
    macro_pairwise_concordance: float = Field(ge=0, le=1)
    macro_pairwise_concordance_ci95: tuple[float, float]
    winner_agreement_rate: float = Field(ge=0, le=1)
    macro_spearman_p_value: float = Field(ge=0, le=1)
    macro_pairwise_concordance_p_value: float = Field(ge=0, le=1)
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evidence(self) -> ContributionRankValidationEvidence:
        spearman_lower, spearman_upper = self.macro_task_spearman_ci95
        concordance_lower, concordance_upper = self.macro_pairwise_concordance_ci95
        if not -1 <= spearman_lower <= self.macro_task_spearman <= spearman_upper <= 1:
            raise ValueError("Contribution Spearman interval is invalid")
        if not (
            0 <= concordance_lower <= self.macro_pairwise_concordance <= concordance_upper <= 1
        ):
            raise ValueError("Contribution concordance interval is invalid")
        if self.evidence_id != contribution_rank_validation_evidence_id(self):
            raise ValueError("Contribution rank-validation evidence identity is invalid")
        return self

    @property
    def passes_production_gate(self) -> bool:
        return bool(
            self.macro_task_spearman_ci95[0] > 0
            and self.macro_pairwise_concordance_ci95[0] > 0.5
            and self.winner_agreement_rate >= 0.5
            and self.macro_spearman_p_value < 0.05
            and self.macro_pairwise_concordance_p_value < 0.05
        )


class ContributionOptimizerUpdateContract(FrozenModel):
    """Exact local update map approximated by a production Contribution estimator."""

    contract_id: str = Field(min_length=1)
    optimizer_name: Literal["adamw"]
    estimator_scope: Literal["local_distribution_update_only"]
    step_count: Literal[1]
    cold_start: Literal[True]
    reuse_main_optimizer_state: Literal[False]
    learning_rate: float = Field(gt=0)
    betas: tuple[float, float]
    epsilon: float = Field(gt=0)
    weight_decay: float = Field(ge=0)
    maximum_gradient_norm: float = Field(gt=0)
    gradient_accumulation_steps: Literal[1]
    mixed_state_batches_allowed: Literal[False]
    trainable_parameter_space: str = Field(min_length=1)
    state_gradient_mode: Literal["train"]
    objective_gradient_mode: Literal["eval"]
    objective_gradient_point: Literal["post_global_update"]
    dropout_realization_policy: Literal["independent_seed_per_realization"]
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ContributionOptimizerUpdateContract:
        beta_one, beta_two = self.betas
        if not 0 < beta_one < beta_two < 1:
            raise ValueError("Contribution optimizer betas are invalid")
        if not math.isclose(self.weight_decay, 0.0, abs_tol=1e-12):
            raise ValueError("local Gradient Projection forbids weight decay")
        if self.contract_id != contribution_optimizer_update_contract_id(self):
            raise ValueError("Contribution optimizer-update contract identity is invalid")
        return self


class ContributionCalibrationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    method: Literal["global_median_absolute_scale_through_zero"]
    estimation_set_id: str = Field(min_length=1)
    validation_set_id: str = Field(min_length=1)
    authorization_set_id: str = Field(min_length=1)
    calibration_artifact_hash: str = Field(min_length=1)
    frozen_before_authorization_access: Literal[True]
    authorization_may_tune: Literal[False]
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ContributionCalibrationContract:
        if len(
            {
                self.estimation_set_id,
                self.validation_set_id,
                self.authorization_set_id,
            }
        ) != 3:
            raise ValueError("Contribution calibration partitions must be disjoint")
        if self.contract_id != contribution_calibration_contract_id(self):
            raise ValueError("Contribution calibration contract identity is invalid")
        return self


class ContributionDistributionGateThresholds(FrozenModel):
    maximum_mean_total_variation: float = Field(ge=0, le=1)
    maximum_p95_total_variation: float = Field(ge=0, le=1)
    maximum_mean_jensen_shannon: float = Field(ge=0)
    maximum_p95_jensen_shannon: float = Field(ge=0)
    minimum_update_direction_agreement: float = Field(ge=0, le=1)
    maximum_mean_absolute_target_regret: float = Field(ge=0)
    maximum_p95_absolute_target_regret: float = Field(ge=0)
    maximum_mean_normalized_target_regret: float = Field(ge=0)
    maximum_p95_normalized_target_regret: float = Field(ge=0)
    minimum_mean_attainable_gain: float = Field(gt=0)
    minimum_normalizable_attainable_gain: float = Field(gt=0)
    minimum_normalizable_task_rate: float = Field(ge=0, le=1)


class ContributionDistributionValidationEvidence(FrozenModel):
    evidence_id: str = Field(min_length=1)
    evaluation_role: Literal[
        "internal_estimation",
        "internal_validation",
        "independent_authorization",
    ]
    task_count: int = Field(ge=1)
    mean_total_variation: float = Field(ge=0, le=1)
    p95_total_variation: float = Field(ge=0, le=1)
    mean_jensen_shannon: float = Field(ge=0)
    p95_jensen_shannon: float = Field(ge=0)
    mean_update_direction_agreement: float = Field(ge=0, le=1)
    mean_absolute_target_regret: float = Field(ge=0)
    p95_absolute_target_regret: float = Field(ge=0)
    mean_normalized_target_regret: float = Field(ge=0)
    p95_normalized_target_regret: float = Field(ge=0)
    mean_attainable_gain: float = Field(gt=0)
    normalizable_task_count: int = Field(ge=0)
    normalizable_task_rate: float = Field(ge=0, le=1)
    task_type_stratified_metrics_hash: str = Field(min_length=1)
    gain_quantile_metrics_hash: str = Field(min_length=1)
    thresholds: ContributionDistributionGateThresholds
    status: Literal["passed"]
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evidence(self) -> ContributionDistributionValidationEvidence:
        if self.normalizable_task_count > self.task_count or not math.isclose(
            self.normalizable_task_rate,
            self.normalizable_task_count / self.task_count,
            abs_tol=1e-12,
        ):
            raise ValueError("Contribution distribution normalizable support is inconsistent")
        passed = bool(
            self.mean_total_variation <= self.thresholds.maximum_mean_total_variation
            and self.p95_total_variation <= self.thresholds.maximum_p95_total_variation
            and self.mean_jensen_shannon <= self.thresholds.maximum_mean_jensen_shannon
            and self.p95_jensen_shannon <= self.thresholds.maximum_p95_jensen_shannon
            and self.mean_update_direction_agreement
            >= self.thresholds.minimum_update_direction_agreement
            and self.mean_absolute_target_regret
            <= self.thresholds.maximum_mean_absolute_target_regret
            and self.p95_absolute_target_regret
            <= self.thresholds.maximum_p95_absolute_target_regret
            and self.mean_normalized_target_regret
            <= self.thresholds.maximum_mean_normalized_target_regret
            and self.p95_normalized_target_regret
            <= self.thresholds.maximum_p95_normalized_target_regret
            and self.mean_attainable_gain >= self.thresholds.minimum_mean_attainable_gain
            and self.normalizable_task_rate
            >= self.thresholds.minimum_normalizable_task_rate
        )
        if not passed:
            raise ValueError("Contribution distribution evidence failed its frozen gate")
        if self.evidence_id != contribution_distribution_validation_evidence_id(self):
            raise ValueError("Contribution distribution-validation identity is invalid")
        return self


class ContributionApproximationAuthorization(FrozenModel):
    """Authorization for a local Gradient Projection to drive one VTDO update."""

    authorization_id: str = Field(min_length=1)
    authorization_version: Literal["finance_contribution_authorization.v4"]
    artifact_type: Literal["ContributionApproximationAuthorization"]
    status: Literal["authorized"]
    estimator_kind: Literal["gradient_projection"]
    estimator_id: Literal["gp_c_post_global_local_adamw_v3"]
    usage_scope: Literal["local_distribution_update_only"]
    approximation_contract_id: str = Field(min_length=1)
    analysis_report_hash: str = Field(min_length=1)
    source_plan_hash: str = Field(min_length=1)
    local_update_manifest_hash: str = Field(min_length=1)
    beneficiary_model_state_id: str = Field(min_length=1)
    beneficiary_checkpoint_hash: str = Field(min_length=1)
    target_metric_id: str = Field(min_length=1)
    optimizer_contract: ContributionOptimizerUpdateContract
    objective_gradient_point: Literal["post_global_update"]
    calibration_contract: ContributionCalibrationContract
    objective_partition_ids: tuple[tuple[str, str], ...] = Field(min_length=3, max_length=3)
    objective_partition_hashes: tuple[tuple[str, str], ...] = Field(
        min_length=3, max_length=3
    )
    objective_record_counts: tuple[tuple[str, int], ...] = Field(min_length=3, max_length=3)
    objective_partitions_disjoint: Literal[True]
    authorization_split_unopened_until_freeze: Literal[True]
    task_condition_ids: tuple[str, ...] = Field(min_length=30)
    task_population_hash: str = Field(min_length=1)
    task_distribution_hashes: tuple[tuple[str, str], ...] = Field(min_length=30)
    task_distribution_ids: tuple[tuple[str, str], ...] = Field(min_length=30)
    task_round_indices: tuple[tuple[str, int], ...] = Field(min_length=30)
    current_distribution_contract_hash: str = Field(min_length=1)
    exact_distribution_contract_hash: str = Field(min_length=1)
    task_state_supports: tuple[tuple[str, tuple[str, ...]], ...] = Field(min_length=30)
    state_realization_counts: tuple[tuple[str, str, int], ...] = Field(min_length=90)
    task_count: int = Field(ge=30)
    state_count: int = Field(ge=90)
    task_sampling_contract_hash: str = Field(min_length=1)
    state_realization_manifest_hash: str = Field(min_length=1)
    gradient_diagnostics_hash: str = Field(min_length=1)
    token_region_manifest_hash: str = Field(min_length=1)
    finite_target_method: Literal[
        "multi_radius_block_hadamard_richardson"
    ]
    finite_target_report_hashes: tuple[tuple[str, str], ...] = Field(
        min_length=3,
        max_length=3,
    )
    post_global_objective_gradient_hashes: tuple[tuple[str, str], ...] = Field(
        min_length=3,
        max_length=3,
    )
    proxy_report_hashes: tuple[tuple[str, str], ...] = Field(
        min_length=3,
        max_length=3,
    )
    uncertainty_penalty_coefficient: float = Field(gt=0)
    state_uncertainty_method: Literal[
        "leave_one_realization_out_jackknife_pseudovalues"
    ]
    objective_support_scaling_report_hash: str = Field(min_length=1)
    gradient_realization_stability_report_hash: str = Field(min_length=1)
    finite_target_reports_passed: Literal[True]
    post_global_objective_gradients_verified: Literal[True]
    strict_freshness_contract_hash: str = Field(min_length=1)
    strict_identity_validated: Literal[True]
    internal_estimation_rank: ContributionRankValidationEvidence
    internal_validation_rank: ContributionRankValidationEvidence
    independent_authorization_rank: ContributionRankValidationEvidence
    internal_estimation_distribution: ContributionDistributionValidationEvidence
    internal_validation_distribution: ContributionDistributionValidationEvidence
    independent_authorization_distribution: ContributionDistributionValidationEvidence
    claim_boundary: Literal[
        "Authorized only for one local state-homogeneous cold-start AdamW VTDO "
        "distribution update at the frozen beneficiary checkpoint. The authorization "
        "does not cover optimizer continuation, mixed-state batches, multi-step Student "
        "training, or a different task population."
    ]
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ContributionApproximationAuthorization:
        expected_roles = (
            "internal_estimation",
            "internal_validation",
            "independent_authorization",
        )
        rank_evidence = (
            self.internal_estimation_rank,
            self.internal_validation_rank,
            self.independent_authorization_rank,
        )
        distribution_evidence = (
            self.internal_estimation_distribution,
            self.internal_validation_distribution,
            self.independent_authorization_distribution,
        )
        if tuple(item.evaluation_role for item in rank_evidence) != expected_roles:
            raise ValueError("Contribution authorization has misassigned rank evidence")
        if not all(item.passes_production_gate for item in rank_evidence):
            raise ValueError("Contribution authorization contains a failed rank gate")
        if tuple(item.evaluation_role for item in distribution_evidence) != expected_roles:
            raise ValueError("Contribution authorization has misassigned distribution evidence")
        if tuple(sorted(self.task_condition_ids)) != self.task_condition_ids or len(
            set(self.task_condition_ids)
        ) != len(self.task_condition_ids):
            raise ValueError("Contribution authorization task population is not canonical")
        if len(self.task_condition_ids) != self.task_count:
            raise ValueError("Contribution authorization task count is inconsistent")
        distribution_hashes = dict(self.task_distribution_hashes)
        distribution_ids = dict(self.task_distribution_ids)
        round_indices = dict(self.task_round_indices)
        if (
            tuple(sorted(self.task_distribution_hashes)) != self.task_distribution_hashes
            or len(distribution_hashes) != len(self.task_distribution_hashes)
            or tuple(distribution_hashes) != self.task_condition_ids
        ):
            raise ValueError("Contribution authorization distribution mapping is incomplete")
        if (
            tuple(sorted(self.task_distribution_ids)) != self.task_distribution_ids
            or tuple(sorted(self.task_round_indices)) != self.task_round_indices
            or tuple(distribution_ids) != self.task_condition_ids
            or tuple(round_indices) != self.task_condition_ids
            or len(set(distribution_ids.values())) != self.task_count
            or len(set(round_indices.values())) != 1
        ):
            raise ValueError("Contribution authorization exact distribution identity is invalid")
        if self.current_distribution_contract_hash != contribution_distribution_contract_hash(
            distribution_hashes
        ):
            raise ValueError("Contribution authorization distribution contract is invalid")
        if self.exact_distribution_contract_hash != contribution_exact_distribution_contract_hash(
            distribution_ids,
            round_indices,
            distribution_hashes,
        ):
            raise ValueError("Contribution authorization exact distribution contract is invalid")
        if self.task_population_hash != contribution_task_population_hash(self.task_condition_ids):
            raise ValueError("Contribution authorization task-population hash is invalid")
        support_by_task = dict(self.task_state_supports)
        if (
            tuple(sorted(self.task_state_supports)) != self.task_state_supports
            or tuple(support_by_task) != self.task_condition_ids
            or any(tuple(sorted(states)) != states for states in support_by_task.values())
            or any(not 3 <= len(states) <= 5 for states in support_by_task.values())
        ):
            raise ValueError("Contribution authorization state support is invalid")
        if sum(len(states) for states in support_by_task.values()) != self.state_count:
            raise ValueError("Contribution authorization state count is inconsistent")
        realization_counts = {
            (task_id, state_id): count
            for task_id, state_id, count in self.state_realization_counts
        }
        expected_realizations = {
            (task_id, state_id)
            for task_id, states in support_by_task.items()
            for state_id in states
        }
        if (
            len(realization_counts) != len(self.state_realization_counts)
            or set(realization_counts) != expected_realizations
            or any(not 3 <= count <= 5 for count in realization_counts.values())
            or tuple(sorted(self.state_realization_counts)) != self.state_realization_counts
        ):
            raise ValueError("Contribution authorization state realizations are incomplete")
        expected_partition_roles = {"estimation", "validation", "authorization"}
        partition_ids = dict(self.objective_partition_ids)
        partition_hashes = dict(self.objective_partition_hashes)
        partition_counts = dict(self.objective_record_counts)
        if not all(
            set(values) == expected_partition_roles
            for values in (partition_ids, partition_hashes, partition_counts)
        ):
            raise ValueError("Contribution authorization objective partitions are incomplete")
        if len(set(partition_ids.values())) != 3 or len(set(partition_hashes.values())) != 3:
            raise ValueError("Contribution authorization objective partitions are not disjoint")
        if any(partition_counts[role] < 16 for role in expected_partition_roles):
            raise ValueError("Contribution authorization objective support is too small")
        finite_targets = dict(self.finite_target_report_hashes)
        post_global_gradients = dict(self.post_global_objective_gradient_hashes)
        proxy_reports = dict(self.proxy_report_hashes)
        if (
            tuple(sorted(self.finite_target_report_hashes))
            != self.finite_target_report_hashes
            or tuple(sorted(self.post_global_objective_gradient_hashes))
            != self.post_global_objective_gradient_hashes
            or tuple(sorted(self.proxy_report_hashes)) != self.proxy_report_hashes
            or set(finite_targets) != expected_partition_roles
            or set(post_global_gradients) != expected_partition_roles
            or set(proxy_reports) != expected_partition_roles
            or len(set(finite_targets.values())) != 3
            or len(set(post_global_gradients.values())) != 3
            or len(set(proxy_reports.values())) != 3
        ):
            raise ValueError("Contribution authorization target evidence is incomplete")
        if self.optimizer_contract.contract_id != self.approximation_contract_id:
            raise ValueError("Contribution authorization optimizer contract is detached")
        if self.authorization_id != contribution_approximation_authorization_id(self):
            raise ValueError("Contribution approximation authorization identity is invalid")
        return self


def validate_contribution_approximation_authorization(
    manifest: ContributionEstimationManifest,
    authorization: ContributionApproximationAuthorization | None,
) -> None:
    if manifest.estimator_kind == "synthetic_oracle":
        if authorization is not None:
            raise ValueError("synthetic Contribution cannot consume a production authorization")
        return
    if manifest.estimator_kind != "gradient_projection":
        raise ValueError(f"{manifest.estimator_kind} Contribution is validation-only")
    if authorization is None:
        raise ValueError("production Gradient Projection requires an independent authorization")
    if manifest.task_condition_id not in authorization.task_condition_ids:
        raise ValueError("Contribution manifest task is outside the authorized population")
    probabilities = {
        item.state_id: item.current_probability for item in manifest.estimates
    }
    manifest_distribution_hash = contribution_current_distribution_hash(
        manifest.task_condition_id,
        probabilities,
    )
    if dict(authorization.task_distribution_hashes).get(
        manifest.task_condition_id
    ) != manifest_distribution_hash:
        raise ValueError("Contribution authorization does not match the manifest current pi_t")
    if dict(authorization.task_distribution_ids).get(
        manifest.task_condition_id
    ) != manifest.distribution_id:
        raise ValueError("Contribution authorization does not match the manifest distribution ID")
    authorized_states = dict(authorization.task_state_supports)[manifest.task_condition_id]
    if tuple(sorted(probabilities)) != authorized_states:
        raise ValueError("Contribution authorization does not match manifest state support")
    realization_counts = {
        state_id: count
        for task_id, state_id, count in authorization.state_realization_counts
        if task_id == manifest.task_condition_id
    }
    if dict(manifest.state_realization_counts) != realization_counts:
        raise ValueError("Contribution manifest realizations differ from authorization")
    expected = {
        "beneficiary_model_state_id": authorization.beneficiary_model_state_id,
        "beneficiary_checkpoint_hash": authorization.beneficiary_checkpoint_hash,
        "target_metric_id": authorization.target_metric_id,
        "estimator_id": authorization.estimator_id,
        "approximation_contract_id": authorization.approximation_contract_id,
        "gradient_mode_contract_id": authorization.optimizer_contract.contract_id,
        "calibration_artifact_hash": (
            authorization.calibration_contract.calibration_artifact_hash
        ),
        "uncertainty_statistic": "sample_standard_deviation",
        "production_contribution_field": "conservative_centered_contribution",
        "uncertainty_penalty_coefficient": (
            authorization.uncertainty_penalty_coefficient
        ),
        "target_evaluation_distribution_id": dict(
            authorization.objective_partition_ids
        )["validation"],
        "final_test_set_id": dict(authorization.objective_partition_ids)["authorization"],
        "estimation_protocol_hash": contribution_materialization_protocol_hash(
            authorization
        ),
        "data_isolation_contract_id": authorization.strict_freshness_contract_hash,
    }
    observed = manifest.model_dump(mode="python", include=set(expected))
    if observed != expected:
        mismatched = tuple(key for key in expected if observed.get(key) != expected[key])
        raise ValueError(f"Contribution authorization does not match its manifest:{mismatched}")


class AnchoredEnergyConfig(FrozenModel):
    epsilon: float = Field(gt=0, lt=0.5)
    contribution_temperature: float = Field(gt=0)
    novelty_temperature: float = Field(gt=0)
    contribution_weight: float = Field(gt=0)
    novelty_weight: float = Field(gt=0)
    history_kl_weight: float = Field(gt=0)
    coverage_kl_weight: float = Field(gt=0)
    reachability_weight: float = Field(default=0.0, ge=0)
    reachability_floor: float = Field(default=0.01, gt=0, le=1)
    reachability_signal: Literal["posterior_mean", "confidence_lower"] = "posterior_mean"

    @model_validator(mode="after")
    def validate_weights(self) -> AnchoredEnergyConfig:
        if not math.isclose(
            self.contribution_weight + self.novelty_weight,
            1.0,
            abs_tol=1e-12,
        ):
            raise ValueError("contribution and novelty weights must sum to one")
        return self

    @property
    def history_exponent(self) -> float:
        return self.history_kl_weight / (self.history_kl_weight + self.coverage_kl_weight)

    @property
    def energy_exponent(self) -> float:
        return 1.0 / (self.history_kl_weight + self.coverage_kl_weight)


class StateReachabilityEstimate(FrozenModel):
    estimate_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    explorer_provider_id: str = Field(min_length=1)
    explorer_provider_version: str = Field(min_length=1)
    estimation_mode: Literal["unconditioned_pushforward", "state_conditioned"]
    protocol_status: Literal["unconditioned", "condition_applied", "protocol_blocked"]
    generation_constraints_hash: str | None = None
    attempted_trajectory_count: int = Field(ge=0)
    on_target_trajectory_count: int = Field(ge=0)
    posterior_alpha: float = Field(gt=0)
    posterior_beta: float = Field(gt=0)
    posterior_mean: float = Field(gt=0, lt=1)
    interval_coverage_probability: float = Field(default=0.95, gt=0, lt=1)
    confidence_lower: float = Field(ge=0, le=1)
    confidence_upper: float = Field(ge=0, le=1)
    status: Literal[
        "observed_reachable",
        "not_observed",
        "unmeasured",
        "protocol_blocked",
    ]
    estimator_id: str = "beta_binomial_with_wilson_interval"
    estimator_version: str = "1.0.0"
    schema_version: str = "trajectory_reachability.v2"

    @model_validator(mode="after")
    def validate_estimate(self) -> StateReachabilityEstimate:
        if self.on_target_trajectory_count > self.attempted_trajectory_count:
            raise ValueError("reachable-state hits cannot exceed attempts")
        if self.protocol_status == "protocol_blocked":
            if self.attempted_trajectory_count or self.generation_constraints_hash is not None:
                raise ValueError("a protocol-blocked state cannot claim model attempts")
            expected_status = "protocol_blocked"
        elif self.attempted_trajectory_count == 0:
            expected_status = "unmeasured"
        elif self.on_target_trajectory_count:
            expected_status = "observed_reachable"
        else:
            expected_status = "not_observed"
        if self.status != expected_status:
            raise ValueError("reachability status is inconsistent")
        if self.protocol_status == "condition_applied" and not self.generation_constraints_hash:
            raise ValueError("conditioned reachability requires a constraint hash")
        if self.protocol_status == "unconditioned" and self.generation_constraints_hash is not None:
            raise ValueError("unconditioned reachability cannot carry a constraint hash")
        expected_alpha = self.on_target_trajectory_count + 1.0
        expected_beta = self.attempted_trajectory_count - self.on_target_trajectory_count + 1.0
        if not math.isclose(self.posterior_alpha, expected_alpha, abs_tol=1e-12):
            raise ValueError("reachability posterior alpha is inconsistent")
        if not math.isclose(self.posterior_beta, expected_beta, abs_tol=1e-12):
            raise ValueError("reachability posterior beta is inconsistent")
        expected_mean = expected_alpha / (expected_alpha + expected_beta)
        if not math.isclose(self.posterior_mean, expected_mean, abs_tol=1e-12):
            raise ValueError("reachability posterior mean is inconsistent")
        expected_lower, expected_upper = _wilson_interval(
            self.on_target_trajectory_count,
            self.attempted_trajectory_count,
            self.interval_coverage_probability,
        )
        if not math.isclose(self.confidence_lower, expected_lower, abs_tol=1e-12):
            raise ValueError("reachability lower bound is inconsistent")
        if not math.isclose(self.confidence_upper, expected_upper, abs_tol=1e-12):
            raise ValueError("reachability upper bound is inconsistent")
        if self.estimate_id != state_reachability_estimate_id(self):
            raise ValueError("state reachability estimate identity is invalid")
        return self


class StateReachabilityManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    explorer_provider_id: str = Field(min_length=1)
    explorer_provider_version: str = Field(min_length=1)
    estimates: tuple[StateReachabilityEstimate, ...] = Field(min_length=1)
    source_batch_ids: tuple[str, ...] = Field(min_length=1)
    schema_version: str = "trajectory_reachability_manifest.v2"

    @model_validator(mode="after")
    def validate_manifest(self) -> StateReachabilityManifest:
        state_ids = tuple(item.state_id for item in self.estimates)
        if len(state_ids) != len(set(state_ids)):
            raise ValueError("reachability manifest contains duplicate states")
        if len(self.source_batch_ids) != len(set(self.source_batch_ids)):
            raise ValueError("reachability source batches must be unique")
        if any(
            item.task_condition_id != self.task_condition_id
            or item.explorer_provider_id != self.explorer_provider_id
            or item.explorer_provider_version != self.explorer_provider_version
            for item in self.estimates
        ):
            raise ValueError("reachability estimates disagree with their manifest")
        if self.manifest_id != state_reachability_manifest_id(self):
            raise ValueError("state reachability manifest identity is invalid")
        return self


class StateEnergyPotential(FrozenModel):
    state_id: str = Field(min_length=1)
    current_probability: float = Field(gt=0, le=1)
    coverage_probability: float = Field(gt=0, le=1)
    centered_contribution: float
    conservative_centered_contribution: float
    contribution_signal_kind: Literal["conservative_centered_contribution"]
    normalized_contribution: float = Field(gt=0, lt=1)
    coverage_relative_novelty: float = Field(ge=0)
    normalized_novelty: float = Field(gt=0, lt=1)
    reachability_estimate_id: str | None = None
    reachability_probability: float = Field(default=1.0, ge=0, le=1)
    normalized_reachability: float = Field(default=1.0, gt=0, le=1)
    potential: float = Field(gt=0, lt=1)
    energy: float = Field(gt=0)


class AnchoredDistributionUpdate(FrozenModel):
    update_id: str = Field(min_length=1)
    algorithm_id: str = VTDO_ALGORITHM_ID
    algorithm_version: str = VTDO_ALGORITHM_VERSION
    prior_distribution: ConditionalTrajectoryDistribution
    coverage_prior: CoveragePrior
    next_distribution: ConditionalTrajectoryDistribution
    validity_estimates: tuple[StateValidityEstimate, ...] = Field(min_length=1)
    contribution_manifest: ContributionEstimationManifest
    contribution_approximation_authorization: ContributionApproximationAuthorization | None = None
    role_contract: VTDORoleContract
    energy_config: AnchoredEnergyConfig
    reachability_manifest: StateReachabilityManifest | None = None
    state_potentials: tuple[StateEnergyPotential, ...] = Field(min_length=1)
    history_exponent: float = Field(gt=0, lt=1)
    energy_exponent: float = Field(gt=0)
    kl_to_history: float = Field(ge=0)
    kl_to_coverage: float = Field(ge=0)
    total_variation_from_history: float = Field(ge=0, le=1)
    prior_entropy: float = Field(ge=0)
    next_entropy: float = Field(ge=0)
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_update(self) -> AnchoredDistributionUpdate:
        if self.algorithm_id != VTDO_ALGORITHM_ID:
            raise ValueError("anchored VTDO update has another algorithm identity")
        if self.algorithm_version != VTDO_ALGORITHM_VERSION:
            raise ValueError("anchored VTDO update has another algorithm version")
        state_ids = set(self.prior_distribution.probabilities)
        if set(self.coverage_prior.probabilities) != state_ids:
            raise ValueError("coverage prior support differs from the current distribution")
        if set(self.next_distribution.probabilities) != state_ids:
            raise ValueError("VTDO update changed the accepted-state support")
        potentials = {item.state_id: item for item in self.state_potentials}
        if len(potentials) != len(self.state_potentials) or set(potentials) != state_ids:
            raise ValueError("state potentials do not cover the distribution support exactly")
        validity_by_state = {item.state_id: item for item in self.validity_estimates}
        if (
            len(validity_by_state) != len(self.validity_estimates)
            or set(validity_by_state) != state_ids
        ):
            raise ValueError("validity estimates do not cover accepted support exactly")
        if any(item.region != ValidityRegion.ACCEPTED for item in self.validity_estimates):
            raise ValueError("VTDO update contains a non-Accepted state")
        if any(
            item.task_condition_id != self.prior_distribution.task_condition_id
            for item in self.validity_estimates
        ):
            raise ValueError("VTDO validity estimate crosses task conditions")
        if self.prior_distribution.task_condition_id != self.coverage_prior.task_condition_id:
            raise ValueError("VTDO coverage prior belongs to another task condition")
        if self.next_distribution.task_condition_id != self.prior_distribution.task_condition_id:
            raise ValueError("VTDO update crosses task conditions")
        if self.next_distribution.round_index != self.prior_distribution.round_index + 1:
            raise ValueError("VTDO update must advance exactly one round")
        if self.next_distribution.source_distribution_id != self.prior_distribution.distribution_id:
            raise ValueError("VTDO next distribution does not identify its prior")
        if self.contribution_manifest.task_condition_id != (
            self.prior_distribution.task_condition_id
        ):
            raise ValueError("VTDO contribution manifest crosses task conditions")
        if self.contribution_manifest.distribution_id != self.prior_distribution.distribution_id:
            raise ValueError("VTDO contribution manifest targets another distribution")
        if self.contribution_manifest.beneficiary_model_state_id != (
            self.role_contract.beneficiary_model_state_id
        ):
            raise ValueError("VTDO contribution manifest violates the role contract")
        validate_contribution_approximation_authorization(
            self.contribution_manifest,
            self.contribution_approximation_authorization,
        )
        contribution_by_state = {
            item.state_id: item for item in self.contribution_manifest.estimates
        }
        if set(contribution_by_state) != state_ids:
            raise ValueError("VTDO contribution manifest has another state support")
        reachability_by_state: dict[str, StateReachabilityEstimate] = {}
        if self.reachability_manifest is not None:
            if self.reachability_manifest.task_condition_id != (
                self.prior_distribution.task_condition_id
            ):
                raise ValueError("VTDO reachability manifest crosses task conditions")
            if (
                self.reachability_manifest.explorer_provider_id
                != self.role_contract.explorer_provider_id
            ):
                raise ValueError("VTDO reachability manifest uses another Explorer")
            reachability_by_state = {
                item.state_id: item for item in self.reachability_manifest.estimates
            }
            if set(reachability_by_state) != state_ids:
                raise ValueError("reachability manifest has another state support")
        if self.energy_config.reachability_weight > 0 and not reachability_by_state:
            raise ValueError("reachability-aware energy requires a complete manifest")
        if self.energy_config.reachability_weight > 0 and any(
            item.attempted_trajectory_count == 0 for item in reachability_by_state.values()
        ):
            raise ValueError("reachability-aware energy requires measured state support")
        if not math.isclose(
            self.history_exponent,
            self.energy_config.history_exponent,
            abs_tol=1e-12,
        ):
            raise ValueError("VTDO history exponent is inconsistent")
        if not math.isclose(
            self.energy_exponent,
            self.energy_config.energy_exponent,
            abs_tol=1e-12,
        ):
            raise ValueError("VTDO energy exponent is inconsistent")
        log_weights: dict[str, float] = {}
        for state_id, potential in potentials.items():
            current = self.prior_distribution.probabilities[state_id]
            coverage = self.coverage_prior.probabilities[state_id]
            contribution = contribution_by_state[state_id]
            if not math.isclose(potential.current_probability, current, abs_tol=1e-12):
                raise ValueError("state potential has another current probability")
            if not math.isclose(contribution.current_probability, current, abs_tol=1e-12):
                raise ValueError("state contribution has another current probability")
            if not math.isclose(
                potential.centered_contribution,
                contribution.centered_contribution,
                abs_tol=1e-12,
            ):
                raise ValueError("state potential is detached from its contribution manifest")
            if not math.isclose(
                potential.conservative_centered_contribution,
                contribution.conservative_centered_contribution,
                abs_tol=1e-12,
            ):
                raise ValueError("state potential is detached from conservative Contribution")
            if potential.contribution_signal_kind != "conservative_centered_contribution":
                raise ValueError("state potential uses an unsupported Contribution signal")
            if not math.isclose(potential.coverage_probability, coverage, abs_tol=1e-12):
                raise ValueError("state potential has another coverage probability")
            expected_novelty = max(math.log(coverage / current), 0.0)
            if not math.isclose(
                potential.coverage_relative_novelty,
                expected_novelty,
                abs_tol=1e-12,
            ):
                raise ValueError("state potential novelty is not log(r/pi)+")
            expected_contribution = _normalized_contribution_value(
                potential.conservative_centered_contribution,
                epsilon=self.energy_config.epsilon,
                temperature=self.energy_config.contribution_temperature,
            )
            expected_normalized_novelty = _normalized_novelty_value(
                expected_novelty,
                epsilon=self.energy_config.epsilon,
                temperature=self.energy_config.novelty_temperature,
            )
            estimate = reachability_by_state.get(state_id)
            expected_reachability = (
                _reachability_signal_value(estimate, self.energy_config)
                if estimate is not None
                else 1.0
            )
            expected_normalized_reachability = max(
                self.energy_config.reachability_floor,
                expected_reachability,
            )
            if not math.isclose(
                potential.normalized_contribution,
                expected_contribution,
                abs_tol=1e-12,
            ):
                raise ValueError("state contribution normalization is inconsistent")
            if not math.isclose(
                potential.normalized_novelty,
                expected_normalized_novelty,
                abs_tol=1e-12,
            ):
                raise ValueError("state novelty normalization is inconsistent")
            if potential.reachability_estimate_id != (
                estimate.estimate_id if estimate is not None else None
            ):
                raise ValueError("state potential is detached from reachability evidence")
            if not math.isclose(
                potential.reachability_probability,
                expected_reachability,
                abs_tol=1e-12,
            ):
                raise ValueError("state reachability probability is inconsistent")
            if not math.isclose(
                potential.normalized_reachability,
                expected_normalized_reachability,
                abs_tol=1e-12,
            ):
                raise ValueError("state reachability normalization is inconsistent")
            expected_potential = (
                potential.normalized_contribution**self.energy_config.contribution_weight
                * potential.normalized_novelty**self.energy_config.novelty_weight
                * potential.normalized_reachability**self.energy_config.reachability_weight
            )
            if not math.isclose(potential.potential, expected_potential, abs_tol=1e-12):
                raise ValueError("state geometric potential is inconsistent")
            if not math.isclose(potential.energy, -math.log(potential.potential), abs_tol=1e-12):
                raise ValueError("state energy is inconsistent")
            log_weights[state_id] = (
                self.history_exponent * math.log(current)
                + (1.0 - self.history_exponent) * math.log(coverage)
                + self.energy_exponent * math.log(potential.potential)
            )
        maximum = max(log_weights.values())
        weights = {state_id: math.exp(value - maximum) for state_id, value in log_weights.items()}
        total = sum(weights.values())
        expected_next = {state_id: value / total for state_id, value in weights.items()}
        if any(
            not math.isclose(
                self.next_distribution.probabilities[state_id],
                expected_next[state_id],
                abs_tol=1e-12,
            )
            for state_id in state_ids
        ):
            raise ValueError("VTDO next distribution does not satisfy the anchored equation")
        expected_kl_history = _kl_probability(expected_next, self.prior_distribution.probabilities)
        expected_kl_coverage = _kl_probability(expected_next, self.coverage_prior.probabilities)
        expected_tv = _total_variation_probability(
            expected_next,
            self.prior_distribution.probabilities,
        )
        if not math.isclose(self.kl_to_history, expected_kl_history, abs_tol=1e-12):
            raise ValueError("VTDO KL-to-history metric is inconsistent")
        if not math.isclose(self.kl_to_coverage, expected_kl_coverage, abs_tol=1e-12):
            raise ValueError("VTDO KL-to-coverage metric is inconsistent")
        if not math.isclose(self.total_variation_from_history, expected_tv, abs_tol=1e-12):
            raise ValueError("VTDO total-variation metric is inconsistent")
        if not math.isclose(
            self.prior_entropy,
            _entropy_probability(self.prior_distribution.probabilities),
            abs_tol=1e-12,
        ):
            raise ValueError("VTDO prior entropy is inconsistent")
        if not math.isclose(
            self.next_entropy,
            _entropy_probability(expected_next),
            abs_tol=1e-12,
        ):
            raise ValueError("VTDO next entropy is inconsistent")
        if self.update_id != anchored_distribution_update_id(self):
            raise ValueError("anchored VTDO update identity is invalid")
        return self


class ExplorationDistribution(FrozenModel):
    exploration_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    training_distribution: ConditionalTrajectoryDistribution
    coverage_prior: CoveragePrior
    exploration_rate: float = Field(gt=0, lt=1)
    probabilities: dict[str, float] = Field(min_length=1)
    importance_weights: dict[str, float] = Field(min_length=1)
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_exploration(self) -> ExplorationDistribution:
        _validate_probability_map(self.probabilities, "exploration distribution")
        if set(self.importance_weights) != set(self.probabilities):
            raise ValueError("exploration importance weights have different support")
        if any(value < 0 for value in self.importance_weights.values()):
            raise ValueError("exploration importance weights cannot be negative")
        if not any(value > 0 for value in self.importance_weights.values()):
            raise ValueError("exploration must retain positive training-policy mass")
        if self.training_distribution.task_condition_id != self.task_condition_id:
            raise ValueError("exploration training distribution crosses task conditions")
        if self.coverage_prior.task_condition_id != self.task_condition_id:
            raise ValueError("exploration coverage prior crosses task conditions")
        training_support = set(self.training_distribution.probabilities)
        coverage_support = set(self.coverage_prior.probabilities)
        if not training_support <= coverage_support:
            raise ValueError("training support is absent from the exploration catalog")
        if set(self.probabilities) != coverage_support:
            raise ValueError("exploration must cover the complete coverage-prior support")
        for state_id in coverage_support:
            training_probability = self.training_distribution.probabilities.get(state_id, 0.0)
            expected_probability = (
                1.0 - self.exploration_rate
            ) * training_probability + self.exploration_rate * self.coverage_prior.probabilities[
                state_id
            ]
            if not math.isclose(self.probabilities[state_id], expected_probability, abs_tol=1e-12):
                raise ValueError("exploration probability does not satisfy q=(1-xi)pi+xi*r")
            expected_weight = training_probability / expected_probability
            if not math.isclose(self.importance_weights[state_id], expected_weight, abs_tol=1e-12):
                raise ValueError("exploration importance weight is not pi/q")
        if self.exploration_id != exploration_distribution_id(self):
            raise ValueError("exploration distribution identity is invalid")
        return self


class EmpiricalDistributionEstimate(FrozenModel):
    estimate_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    state_exposure_counts: dict[str, int] = Field(min_length=1)
    state_exposure_weights: dict[str, float] = Field(min_length=1)
    total_exposure_count: int = Field(ge=1)
    total_exposure_weight: float = Field(gt=0)
    sum_squared_importance_weights: float = Field(gt=0)
    effective_sample_size: float = Field(gt=0)
    source_observation_ids: tuple[str, ...] = Field(min_length=1)
    sampling_distribution_id: str | None = None
    estimator_kind: Literal["unweighted_pushforward", "importance_weighted_pushforward"]
    coverage_prior: CoveragePrior
    prior_strength: float = Field(ge=0)
    distribution: ConditionalTrajectoryDistribution
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_estimate(self) -> EmpiricalDistributionEstimate:
        if any(not state_id or count < 0 for state_id, count in self.state_exposure_counts.items()):
            raise ValueError("empirical state exposures require named nonnegative counts")
        if sum(self.state_exposure_counts.values()) != self.total_exposure_count:
            raise ValueError("empirical state exposures do not sum to their total")
        if len(self.source_observation_ids) != self.total_exposure_count:
            raise ValueError("empirical estimate does not identify every observation")
        if len(set(self.source_observation_ids)) != len(self.source_observation_ids):
            raise ValueError("empirical estimate contains duplicate observations")
        if set(self.state_exposure_weights) != set(self.state_exposure_counts):
            raise ValueError("weighted and raw empirical supports differ")
        if any(value < 0 for value in self.state_exposure_weights.values()):
            raise ValueError("empirical state exposure weights cannot be negative")
        if not math.isclose(
            sum(self.state_exposure_weights.values()),
            self.total_exposure_weight,
            abs_tol=1e-12,
        ):
            raise ValueError("empirical state weights do not sum to their total")
        expected_effective_size = (
            self.total_exposure_weight**2 / self.sum_squared_importance_weights
        )
        if not math.isclose(self.effective_sample_size, expected_effective_size, abs_tol=1e-12):
            raise ValueError("empirical effective sample size is inconsistent")
        if set(self.state_exposure_counts) != set(self.distribution.probabilities):
            raise ValueError("empirical exposure support differs from its distribution")
        if self.distribution.task_condition_id != self.task_condition_id:
            raise ValueError("empirical distribution crosses task conditions")
        if self.coverage_prior.task_condition_id != self.task_condition_id:
            raise ValueError("empirical coverage prior crosses task conditions")
        if set(self.coverage_prior.probabilities) != set(self.state_exposure_counts):
            raise ValueError("empirical coverage prior has another support")
        if self.estimator_kind == "unweighted_pushforward":
            if self.sampling_distribution_id is not None:
                raise ValueError("unweighted push-forward cannot name an exploration policy")
            if any(
                not math.isclose(self.state_exposure_weights[state_id], float(count), abs_tol=1e-12)
                for state_id, count in self.state_exposure_counts.items()
            ):
                raise ValueError("unweighted push-forward has non-unit observation weights")
            if not math.isclose(
                self.sum_squared_importance_weights,
                float(self.total_exposure_count),
                abs_tol=1e-12,
            ):
                raise ValueError("unweighted push-forward has invalid squared weights")
        elif self.sampling_distribution_id is None:
            raise ValueError("importance-weighted push-forward requires its sampling policy")
        denominator = self.total_exposure_weight + self.prior_strength
        expected_probabilities = {
            state_id: (
                self.state_exposure_weights[state_id]
                + self.prior_strength * self.coverage_prior.probabilities[state_id]
            )
            / denominator
            for state_id in self.state_exposure_counts
        }
        if any(
            not math.isclose(
                self.distribution.probabilities[state_id],
                expected_probabilities[state_id],
                abs_tol=1e-12,
            )
            for state_id in expected_probabilities
        ):
            raise ValueError("empirical distribution does not replay its weighted estimate")
        if self.estimate_id != empirical_distribution_estimate_id(self):
            raise ValueError("empirical distribution estimate identity is invalid")
        return self


def validity_region(value: float, thresholds: ValidityThresholds) -> ValidityRegion:
    if value >= thresholds.accept_at_or_above:
        return ValidityRegion.ACCEPTED
    if value < thresholds.reject_below:
        return ValidityRegion.REJECTED
    return ValidityRegion.QUARANTINED


def vtdo_role_contract_id(value: VTDORoleContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="vtdo_role_contract:",
    )


def state_validity_estimate_id(value: StateValidityEstimate) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"estimate_id"}),
        prefix="state_validity_estimate:",
    )


def conditional_distribution_id(value: ConditionalTrajectoryDistribution) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"distribution_id"}),
        prefix="conditional_trajectory_distribution:",
    )


def task_conditioned_policy_id(value: TaskConditionedTrajectoryPolicy) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"policy_id"}),
        prefix="task_conditioned_trajectory_policy:",
    )


def coverage_prior_id(value: CoveragePrior) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"prior_id"}),
        prefix="trajectory_coverage_prior:",
    )


def contribution_estimate_id(value: ContributionEstimate) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"estimate_id"}),
        prefix="trajectory_contribution_estimate:",
    )


def contribution_manifest_id(value: ContributionEstimationManifest) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="trajectory_contribution_manifest:",
    )


def contribution_rank_validation_evidence_id(
    value: ContributionRankValidationEvidence,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"evidence_id"}),
        prefix="contribution_rank_validation_evidence:",
    )


def contribution_task_population_hash(task_condition_ids: tuple[str, ...]) -> str:
    return canonical_hash(
        tuple(sorted(task_condition_ids)),
        prefix="contribution_task_population:",
    )


def contribution_current_distribution_hash(
    task_condition_id: str,
    state_probabilities: Mapping[str, float],
) -> str:
    probabilities = dict(state_probabilities)
    _validate_probability_map(probabilities, "Contribution current distribution")
    return canonical_hash(
        {
            "task_condition_id": task_condition_id,
            "state_probabilities": dict(sorted(probabilities.items())),
        },
        prefix="contribution_current_distribution:",
    )


def contribution_distribution_contract_hash(
    task_distribution_hashes: Mapping[str, str],
) -> str:
    values = dict(task_distribution_hashes)
    if not values or any(not task_id or not value for task_id, value in values.items()):
        raise ValueError("Contribution distribution contract requires named task distributions")
    return canonical_hash(
        dict(sorted(values.items())),
        prefix="contribution_distribution_contract:",
    )


def contribution_exact_distribution_contract_hash(
    task_distribution_ids: Mapping[str, str],
    task_round_indices: Mapping[str, int],
    task_distribution_hashes: Mapping[str, str],
) -> str:
    distribution_ids = dict(task_distribution_ids)
    round_indices = dict(task_round_indices)
    distribution_hashes = dict(task_distribution_hashes)
    if not distribution_ids or not (
        set(distribution_ids) == set(round_indices) == set(distribution_hashes)
    ):
        raise ValueError("exact Contribution distribution contract is incomplete")
    if any(not value for value in distribution_ids.values()) or any(
        value < 0 for value in round_indices.values()
    ):
        raise ValueError("exact Contribution distribution identity is invalid")
    return canonical_hash(
        {
            task_id: {
                "distribution_id": distribution_ids[task_id],
                "round_index": round_indices[task_id],
                "probability_hash": distribution_hashes[task_id],
            }
            for task_id in sorted(distribution_ids)
        },
        prefix="contribution_exact_distribution_contract:",
    )


def contribution_materialization_protocol_hash(
    authorization: ContributionApproximationAuthorization,
) -> str:
    return canonical_hash(
        {
            "authorization_id": authorization.authorization_id,
            "source_plan_hash": authorization.source_plan_hash,
            "validation_proxy_report_hash": dict(authorization.proxy_report_hashes)[
                "validation"
            ],
            "local_update_manifest_hash": authorization.local_update_manifest_hash,
            "objective_gradient_point": authorization.objective_gradient_point,
            "exact_distribution_contract_hash": (
                authorization.exact_distribution_contract_hash
            ),
            "token_region_manifest_hash": authorization.token_region_manifest_hash,
            "uncertainty_method": authorization.state_uncertainty_method,
        },
        prefix="finance_gradient_contribution_materialization_protocol:",
    )


def contribution_optimizer_update_contract_id(
    value: ContributionOptimizerUpdateContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="contribution_optimizer_update_contract:",
    )


def contribution_calibration_contract_id(
    value: ContributionCalibrationContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="contribution_calibration_contract:",
    )


def contribution_distribution_validation_evidence_id(
    value: ContributionDistributionValidationEvidence,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"evidence_id"}),
        prefix="contribution_distribution_validation_evidence:",
    )


def contribution_approximation_authorization_id(
    value: ContributionApproximationAuthorization,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"authorization_id"}),
        prefix="contribution_approximation_authorization:",
    )


def anchored_distribution_update_id(value: AnchoredDistributionUpdate) -> str:
    payload = value.model_dump(mode="json", exclude={"update_id"})
    energy_config = payload["energy_config"]
    state_potentials = payload["state_potentials"]
    if (
        payload.get("reachability_manifest") is None
        and energy_config.get("reachability_weight") == 0.0
        and energy_config.get("reachability_floor") == 0.01
        and energy_config.get("reachability_signal") == "posterior_mean"
        and all(
            item.get("reachability_estimate_id") is None
            and item.get("reachability_probability") == 1.0
            and item.get("normalized_reachability") == 1.0
            for item in state_potentials
        )
    ):
        payload.pop("reachability_manifest", None)
        for field in (
            "reachability_weight",
            "reachability_floor",
            "reachability_signal",
        ):
            energy_config.pop(field, None)
        for item in state_potentials:
            item.pop("reachability_estimate_id", None)
            item.pop("reachability_probability", None)
            item.pop("normalized_reachability", None)
    return canonical_hash(
        payload,
        prefix="anchored_vtdo_update:",
    )


def state_reachability_estimate_id(value: StateReachabilityEstimate) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"estimate_id"}),
        prefix="state_reachability_estimate:",
    )


def state_reachability_manifest_id(value: StateReachabilityManifest) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="state_reachability_manifest:",
    )


def exploration_distribution_id(value: ExplorationDistribution) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"exploration_id"}),
        prefix="trajectory_exploration_distribution:",
    )


def empirical_distribution_estimate_id(value: EmpiricalDistributionEstimate) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"estimate_id"}),
        prefix="trajectory_empirical_distribution:",
    )


def _validate_probability_map(values: dict[str, float], label: str) -> None:
    if any(not key for key in values):
        raise ValueError(f"{label} contains an empty state ID")
    if any(value <= 0 for value in values.values()):
        raise ValueError(f"{label} requires full positive support")
    if not math.isclose(sum(values.values()), 1.0, abs_tol=1e-9):
        raise ValueError(f"{label} probabilities must sum to one")


def _normalized_contribution_value(
    value: float,
    *,
    epsilon: float,
    temperature: float,
) -> float:
    scaled = value / temperature
    if scaled >= 0:
        sigmoid = 1.0 / (1.0 + math.exp(-scaled))
    else:
        exponential = math.exp(scaled)
        sigmoid = exponential / (1.0 + exponential)
    return epsilon + (1.0 - 2.0 * epsilon) * sigmoid


def _normalized_novelty_value(
    value: float,
    *,
    epsilon: float,
    temperature: float,
) -> float:
    return epsilon + (1.0 - 2.0 * epsilon) * (1.0 - math.exp(-value / temperature))


def _kl_probability(left: dict[str, float], right: dict[str, float]) -> float:
    return sum(left[key] * math.log(left[key] / right[key]) for key in left)


def _total_variation_probability(
    left: dict[str, float],
    right: dict[str, float],
) -> float:
    return 0.5 * sum(abs(left[key] - right[key]) for key in left)


def _entropy_probability(values: dict[str, float]) -> float:
    return -sum(value * math.log(value) for value in values.values())


def _reachability_signal_value(
    estimate: StateReachabilityEstimate,
    config: AnchoredEnergyConfig,
) -> float:
    if config.reachability_signal == "posterior_mean":
        return estimate.posterior_mean
    return estimate.confidence_lower


def _wilson_interval(
    successes: int,
    attempts: int,
    interval_coverage_probability: float,
) -> tuple[float, float]:
    if attempts == 0:
        return 0.0, 1.0
    # The reachability contract currently freezes a 95% interval.
    if not math.isclose(interval_coverage_probability, 0.95, abs_tol=1e-12):
        raise ValueError("reachability currently supports interval_coverage_probability=0.95 only")
    z = 1.959963984540054
    probability = successes / attempts
    denominator = 1.0 + z * z / attempts
    center = (probability + z * z / (2.0 * attempts)) / denominator
    margin = (
        z
        * math.sqrt(
            probability * (1.0 - probability) / attempts + z * z / (4.0 * attempts * attempts)
        )
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)
