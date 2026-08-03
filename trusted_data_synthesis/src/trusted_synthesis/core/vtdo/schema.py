from __future__ import annotations

import math
from collections.abc import Mapping
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

VTDO_SCHEMA_VERSION = "vtdo.v8"
VTDO_ALGORITHM_ID = "anchored_energy_valid_trajectory_distribution_refinement"
VTDO_ALGORITHM_VERSION = "aevtdr.v4"


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
    estimator_kind: Literal["synthetic_oracle", "finite_intervention", "local_probe"]
    usage_scope: Literal[
        "synthetic_operator_control",
        "intervention_validation",
        "production_distribution_update",
    ]
    estimation_protocol_hash: str = Field(min_length=1)
    data_isolation_contract_id: str = Field(min_length=1)
    final_test_set_id: str = Field(min_length=1)
    estimator_id: str = Field(min_length=1)
    probe_optimizer_contract_id: str | None = None
    probe_adaptation_horizon: int | None = Field(default=None, ge=1, le=3)
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
            "local_probe": "production_distribution_update",
        }[self.estimator_kind]
        if self.usage_scope != expected_scope:
            raise ValueError("Contribution estimator kind and usage scope disagree")
        if self.estimator_kind == "local_probe":
            if not self.probe_optimizer_contract_id or self.probe_adaptation_horizon is None:
                raise ValueError(
                    "production local Probe must freeze its optimizer and adaptation horizon"
                )
            if self.uncertainty_penalty_coefficient <= 0:
                raise ValueError("production local Probe requires a positive uncertainty penalty")
            if any(item.observation_count < 2 for item in self.estimates):
                raise ValueError("production local Probe requires at least two seeds per state")
        else:
            if self.probe_optimizer_contract_id is not None or (
                self.probe_adaptation_horizon is not None
            ):
                raise ValueError("non-Probe Contribution cannot carry a Probe optimizer")
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


class ContributionProductionAuthorization(FrozenModel):
    """Proof that a frozen local-Probe estimand may influence a VTDO update."""

    authorization_id: str = Field(min_length=1)
    analysis_version: str = Field(min_length=1)
    analysis_report_hash: str = Field(min_length=1)
    current_distribution_contract_hash: str = Field(min_length=1)
    task_distribution_hashes: tuple[tuple[str, str], ...] = Field(min_length=1)
    beneficiary_model_state_id: str = Field(min_length=1)
    beneficiary_checkpoint_hash: str = Field(min_length=1)
    target_metric_id: str = Field(min_length=1)
    probe_optimizer_contract_id: str = Field(min_length=1)
    selected_adaptation_horizon: int = Field(ge=1, le=3)
    uncertainty_statistic: Literal["sample_standard_deviation"]
    uncertainty_penalty_coefficient: float = Field(gt=0)
    production_contribution_field: Literal["conservative_centered_contribution"]
    internal_validation_set_id: str = Field(min_length=1)
    final_test_set_id: str = Field(min_length=1)
    task_condition_ids: tuple[str, ...] = Field(min_length=1)
    task_population_hash: str = Field(min_length=1)
    task_count: int = Field(ge=1)
    state_count: int = Field(ge=1)
    internal_validation_record_count: int = Field(ge=1)
    final_test_record_count: int = Field(ge=1)
    estimation_seed_count: int = Field(ge=1)
    validation_seed_count: int = Field(ge=1)
    intervention_seed_count: int = Field(ge=1)
    seed_sets_disjoint: Literal[True]
    strict_identity_validated: Literal[True]
    cross_seed_stability: ContributionRankValidationEvidence
    independent_final_test: ContributionRankValidationEvidence
    heldout_final_test: ContributionRankValidationEvidence
    status: Literal["passed"]
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ContributionProductionAuthorization:
        evidence = (
            self.cross_seed_stability,
            self.independent_final_test,
            self.heldout_final_test,
        )
        expected_roles = (
            "cross_seed_stability",
            "independent_final_test",
            "heldout_final_test",
        )
        if tuple(item.evaluation_role for item in evidence) != expected_roles:
            raise ValueError("Contribution authorization has misassigned validation evidence")
        if not all(item.passes_production_gate for item in evidence):
            raise ValueError("Contribution authorization contains a failed rank gate")
        if tuple(sorted(self.task_condition_ids)) != self.task_condition_ids:
            raise ValueError("Contribution authorization task population is not canonical")
        if len(self.task_condition_ids) != len(set(self.task_condition_ids)):
            raise ValueError("Contribution authorization contains duplicate task identities")
        if len(self.task_condition_ids) != self.task_count:
            raise ValueError("Contribution authorization task count is not its frozen population")
        if tuple(sorted(self.task_distribution_hashes)) != self.task_distribution_hashes:
            raise ValueError("Contribution authorization distribution mapping is not canonical")
        task_distribution_hashes = dict(self.task_distribution_hashes)
        if len(task_distribution_hashes) != len(self.task_distribution_hashes):
            raise ValueError("Contribution authorization contains duplicate distribution tasks")
        if tuple(task_distribution_hashes) != self.task_condition_ids:
            raise ValueError("Contribution authorization distributions do not cover its tasks")
        if self.current_distribution_contract_hash != contribution_distribution_contract_hash(
            task_distribution_hashes
        ):
            raise ValueError("Contribution authorization distribution contract is invalid")
        if self.task_population_hash != contribution_task_population_hash(self.task_condition_ids):
            raise ValueError("Contribution authorization task-population hash is invalid")
        if self.task_count < 30 or self.state_count < self.task_count:
            raise ValueError("Contribution production authorization needs at least 30 tasks")
        if self.internal_validation_record_count < 5 or self.final_test_record_count < 5:
            raise ValueError("Contribution production authorization lacks evaluation support")
        if (
            min(
                self.estimation_seed_count,
                self.validation_seed_count,
                self.intervention_seed_count,
            )
            < 2
        ):
            raise ValueError("Contribution production authorization needs multiple seeds per role")
        if self.authorization_id != contribution_production_authorization_id(self):
            raise ValueError("Contribution production authorization identity is invalid")
        return self


def validate_contribution_production_authorization(
    manifest: ContributionEstimationManifest,
    authorization: ContributionProductionAuthorization | None,
) -> None:
    if manifest.estimator_kind == "synthetic_oracle":
        if authorization is not None:
            raise ValueError("synthetic Contribution cannot consume a Probe authorization")
        return
    if manifest.estimator_kind != "local_probe":
        raise ValueError("finite Intervention Contribution is validation-only")
    if authorization is None:
        raise ValueError("production local Probe requires an independent authorization")
    if manifest.task_condition_id not in authorization.task_condition_ids:
        raise ValueError("Contribution manifest task is outside the validated population")
    manifest_distribution_hash = contribution_current_distribution_hash(
        manifest.task_condition_id,
        {item.state_id: item.current_probability for item in manifest.estimates},
    )
    authorized_distribution_hash = dict(authorization.task_distribution_hashes).get(
        manifest.task_condition_id
    )
    if authorized_distribution_hash != manifest_distribution_hash:
        raise ValueError("Contribution authorization does not match the manifest current pi_t")
    if any(
        item.observation_count < authorization.estimation_seed_count for item in manifest.estimates
    ):
        raise ValueError("Contribution manifest has fewer seeds than its authorization")
    expected = {
        "beneficiary_model_state_id": manifest.beneficiary_model_state_id,
        "beneficiary_checkpoint_hash": manifest.beneficiary_checkpoint_hash,
        "target_metric_id": manifest.target_metric_id,
        "probe_optimizer_contract_id": manifest.probe_optimizer_contract_id,
        "selected_adaptation_horizon": manifest.probe_adaptation_horizon,
        "uncertainty_statistic": manifest.uncertainty_statistic,
        "uncertainty_penalty_coefficient": manifest.uncertainty_penalty_coefficient,
        "production_contribution_field": manifest.production_contribution_field,
        "internal_validation_set_id": manifest.target_evaluation_distribution_id,
        "final_test_set_id": manifest.final_test_set_id,
    }
    observed = authorization.model_dump(mode="python", include=set(expected))
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
    contribution_production_authorization: ContributionProductionAuthorization | None = None
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
        validate_contribution_production_authorization(
            self.contribution_manifest,
            self.contribution_production_authorization,
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


def contribution_production_authorization_id(
    value: ContributionProductionAuthorization,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"authorization_id"}),
        prefix="contribution_production_authorization:",
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
