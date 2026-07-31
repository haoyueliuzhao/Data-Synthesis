from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.feedback import FeedbackRoute
from trusted_synthesis.core.trajectory.attributes import TrajectoryAttributeProfile
from trusted_synthesis.hashing import canonical_hash

CCGR_ALGORITHM_ID = "calibrated_clause_guided_refinement"
CCGR_ALGORITHM_VERSION = "ccgr.v3"
VALID_TRAJECTORY_ALGORITHM_ID = "valid_trajectory_distribution_optimization"
VALID_TRAJECTORY_ALGORITHM_VERSION = "vtdo.v1"
REFINEMENT_SCHEMA_VERSION = "refinement.v3"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SynthesisCell(FrozenModel):
    """One auditable point in the finite synthesis policy space."""

    cell_id: str = Field(min_length=1)
    pattern_id: str = Field(min_length=1)
    binding_stratum_id: str = Field(min_length=1)
    difficulty_bucket: str = Field(min_length=1)
    distractor_profile_id: str = Field(min_length=1)
    trajectory_attribute_profile: TrajectoryAttributeProfile | None = None
    declared_tightening_options: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    active_binding_constraints: tuple[str, ...] = ()
    schema_version: str = REFINEMENT_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_identity_and_constraints(self) -> SynthesisCell:
        declared = {
            constraint
            for constraints in self.declared_tightening_options.values()
            for constraint in constraints
        }
        if len(self.active_binding_constraints) != len(set(self.active_binding_constraints)):
            raise ValueError("active binding constraints must be unique")
        if not set(self.active_binding_constraints).issubset(declared):
            raise ValueError("active binding constraints must come from predeclared options")
        if any(not key or not values for key, values in self.declared_tightening_options.items()):
            raise ValueError("tightening options require non-empty keys and values")
        if any(
            len(values) != len(set(values)) for values in self.declared_tightening_options.values()
        ):
            raise ValueError("tightening options must be unique per clause key")
        if self.cell_id != synthesis_cell_id(self):
            raise ValueError("synthesis cell identity is invalid")
        return self


# Public method name; SynthesisCell remains as a compatibility alias in artifacts.
TrajectoryConfiguration = SynthesisCell


class ClauseFeedback(FrozenModel):
    """A root failure weighted by counterfactual calibration reliability."""

    feedback_id: str = Field(min_length=1)
    source_signal_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    clause_id: str = Field(min_length=1)
    clause_kind: str = Field(min_length=1)
    failure_family: str = Field(min_length=1)
    route: FeedbackRoute
    severity: Literal["fatal", "quarantine", "diagnostic"]
    severity_weight: float = Field(gt=0)
    calibration_reliability: float = Field(ge=0, le=1)
    calibrated_weight: float = Field(ge=0)
    calibration_status: Literal["calibrated", "missing", "raw_ablation"]
    failure_code: str | None = None
    schema_version: str = REFINEMENT_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_weight_and_identity(self) -> ClauseFeedback:
        expected = self.severity_weight * self.calibration_reliability
        if not math.isclose(self.calibrated_weight, expected, abs_tol=1e-12):
            raise ValueError("calibrated weight must equal severity times reliability")
        if self.feedback_id != clause_feedback_id(self):
            raise ValueError("clause feedback identity is invalid")
        return self


class TrajectoryUtilityWeights(FrozenModel):
    """Frozen coefficients for the valid-trajectory utility."""

    alpha_validity: float = Field(ge=0)
    beta_coverage: float = Field(ge=0)
    gamma_diversity: float = Field(ge=0)
    lambda_defect: float = Field(ge=0)


class TrajectoryUtilityComponents(FrozenModel):
    """Auditable decomposition of R(configuration)."""

    validity_reward: float = Field(ge=0, le=1)
    coverage_gain: float = Field(ge=0, le=1)
    diversity_gain: float = Field(ge=0, le=1)
    synthesis_defect_risk: float = Field(ge=0)
    weights: TrajectoryUtilityWeights
    utility: float

    @model_validator(mode="after")
    def validate_utility(self) -> TrajectoryUtilityComponents:
        expected = (
            self.weights.alpha_validity * self.validity_reward
            + self.weights.beta_coverage * self.coverage_gain
            + self.weights.gamma_diversity * self.diversity_gain
            - self.weights.lambda_defect * self.synthesis_defect_risk
        )
        if not math.isclose(self.utility, expected, abs_tol=1e-12):
            raise ValueError("trajectory utility does not match its four components")
        return self


class TrajectoryDistributionMetrics(FrozenModel):
    """Distribution-level behavior coverage for one synthesis policy."""

    profile_probabilities: dict[str, float] = Field(default_factory=dict)
    profile_entropy: float = Field(ge=0)
    effective_profile_count: float = Field(ge=0)
    capability_coverage: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_distribution(self) -> TrajectoryDistributionMetrics:
        if self.profile_probabilities and not math.isclose(
            sum(self.profile_probabilities.values()), 1.0, abs_tol=1e-9
        ):
            raise ValueError("trajectory profile probabilities must sum to one")
        expected = math.exp(self.profile_entropy) if self.profile_probabilities else 0.0
        if not math.isclose(self.effective_profile_count, expected, abs_tol=1e-12):
            raise ValueError("effective trajectory profile count is inconsistent")
        return self


class CellFeedbackStatistics(FrozenModel):
    """Calibrated D, G, and U statistics for one synthesis cell."""

    cell_id: str = Field(min_length=1)
    exposure_count: int = Field(ge=0)
    root_feedback_count: int = Field(ge=0)
    interface_failure_count: int = Field(ge=0)
    synthesis_defect_count: int = Field(ge=0)
    capability_gap_count: int = Field(ge=0)
    uncalibrated_feedback_count: int = Field(ge=0)
    interface_weight_sum: float = Field(ge=0)
    synthesis_defect_weight_sum: float = Field(ge=0)
    capability_gap_weight_sum: float = Field(ge=0)
    raw_synthesis_defect_weight_sum: float = Field(default=0.0, ge=0)
    raw_capability_gap_weight_sum: float = Field(default=0.0, ge=0)
    pattern_exposure_count: int = Field(default=0, ge=0)
    pattern_synthesis_defect_rate: float = Field(default=0.0, ge=0)
    pattern_capability_gap_rate: float = Field(default=0.0, ge=0)
    cell_synthesis_defect_rate: float = Field(default=0.0, ge=0)
    cell_capability_gap_rate: float = Field(default=0.0, ge=0)
    shrinkage_weight: float = Field(default=1.0, ge=0, le=1)
    minimum_exposure_met: bool = True
    synthesis_defect_risk: float = Field(ge=0)
    capability_gap_demand: float = Field(ge=0)
    target_share: float = Field(ge=0, le=1)
    observed_share: float = Field(ge=0, le=1)
    coverage_gap: float = Field(ge=0, le=1)
    trajectory_attempt_count: int = Field(default=0, ge=0)
    valid_trajectory_count: int = Field(default=0, ge=0)
    trajectory_validity_rate: float = Field(default=0.0, ge=0, le=1)
    mean_trajectory_validity_score: float = Field(default=0.0, ge=0, le=1)
    trajectory_attribute_profile_count: int = Field(default=0, ge=0)
    trajectory_attribute_entropy: float = Field(default=0.0, ge=0)
    trajectory_diversity_gain: float = Field(default=0.0, ge=0, le=1)
    missing_attribute_rate: float = Field(default=0.0, ge=0, le=1)

    @model_validator(mode="after")
    def validate_rates(self) -> CellFeedbackStatistics:
        if self.exposure_count == 0 and (
            self.synthesis_defect_risk > 0 or self.capability_gap_demand > 0
        ):
            raise ValueError("an unexposed cell cannot have directional feedback")
        expected_gap = max(0.0, self.target_share - self.observed_share)
        if not math.isclose(self.coverage_gap, expected_gap, abs_tol=1e-12):
            raise ValueError("coverage gap must equal max(0, target-observed)")
        if self.valid_trajectory_count > self.trajectory_attempt_count:
            raise ValueError("valid trajectory count cannot exceed attempts")
        expected_validity = (
            self.valid_trajectory_count / self.trajectory_attempt_count
            if self.trajectory_attempt_count
            else 0.0
        )
        if not math.isclose(
            self.trajectory_validity_rate, expected_validity, abs_tol=1e-12
        ):
            raise ValueError("trajectory validity rate is inconsistent")
        if self.trajectory_attribute_profile_count > self.trajectory_attempt_count:
            raise ValueError("trajectory profile count cannot exceed attempts")
        if self.trajectory_attribute_profile_count > self.valid_trajectory_count:
            raise ValueError("trajectory profile count cannot exceed valid trajectories")
        return self


class SynthesisPolicy(FrozenModel):
    """A versioned probability distribution over synthesis cells."""

    policy_id: str = Field(min_length=1)
    round_index: int = Field(ge=0)
    label: str = Field(min_length=1)
    cells: tuple[SynthesisCell, ...] = Field(min_length=1)
    probabilities: dict[str, float] = Field(min_length=1)
    target_probabilities: dict[str, float] = Field(min_length=1)
    source_policy_id: str | None = None
    schema_version: str = REFINEMENT_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_distribution_and_identity(self) -> SynthesisPolicy:
        cell_ids = [cell.cell_id for cell in self.cells]
        if len(cell_ids) != len(set(cell_ids)):
            raise ValueError("synthesis policy contains duplicate cells")
        expected = set(cell_ids)
        if set(self.probabilities) != expected:
            raise ValueError("policy probabilities must cover exactly the policy cells")
        if set(self.target_probabilities) != expected:
            raise ValueError("target probabilities must cover exactly the policy cells")
        if any(value <= 0 for value in self.probabilities.values()):
            raise ValueError("policy probabilities must be strictly positive")
        if any(value < 0 for value in self.target_probabilities.values()):
            raise ValueError("target probabilities cannot be negative")
        if not math.isclose(sum(self.probabilities.values()), 1.0, abs_tol=1e-9):
            raise ValueError("policy probabilities must sum to one")
        if not math.isclose(sum(self.target_probabilities.values()), 1.0, abs_tol=1e-9):
            raise ValueError("target probabilities must sum to one")
        if self.policy_id not in {synthesis_policy_id(self), legacy_synthesis_policy_id(self)}:
            raise ValueError("synthesis policy identity is invalid")
        return self


class PolicyUpdateResult(FrozenModel):
    """Proof-carrying output of one CCGR update or frozen ablation."""

    update_id: str = Field(min_length=1)
    algorithm_id: str = CCGR_ALGORITHM_ID
    algorithm_version: str = CCGR_ALGORITHM_VERSION
    ablation_id: str = Field(min_length=1)
    prior_policy: SynthesisPolicy
    next_policy: SynthesisPolicy
    statistics: tuple[CellFeedbackStatistics, ...] = Field(min_length=1)
    cell_utilities: dict[str, float] = Field(min_length=1)
    cell_utility_components: dict[str, TrajectoryUtilityComponents] = Field(
        default_factory=dict
    )
    cell_transition_map: dict[str, str] = Field(min_length=1)
    allocated_counts: dict[str, int] = Field(min_length=1)
    conditioning_mode: Literal["global", "fixed_group_marginals"] = "global"
    conditioning_groups: dict[str, str] = Field(default_factory=dict)
    fixed_group_weights: dict[str, float] = Field(default_factory=dict)
    allocated_group_counts: dict[str, int] = Field(default_factory=dict)
    activated_binding_constraints: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    tightening_without_declared_option: tuple[str, ...] = ()
    eta: float = Field(ge=0)
    alpha: float = Field(default=0.0, ge=0)
    beta: float = Field(ge=0)
    gamma: float = Field(ge=0)
    lambda_defect: float = Field(default=0.0, ge=0)
    total_budget: int = Field(ge=1)
    calibration_manifest_hash: str = Field(min_length=1)
    feedback_manifest_hash: str = Field(min_length=1)
    trajectory_feedback_manifest_hash: str | None = None
    trajectory_feedback_count: int = Field(default=0, ge=0)
    utility_mode: Literal[
        "feedback_objective",
        "score_only_control",
        "random_control",
        "valid_trajectory_objective",
    ]
    prior_trajectory_metrics: TrajectoryDistributionMetrics | None = None
    next_trajectory_metrics: TrajectoryDistributionMetrics | None = None
    kl_divergence: float = Field(ge=0)
    total_variation_distance: float = Field(ge=0, le=1)
    prior_entropy: float = Field(ge=0)
    next_entropy: float = Field(ge=0)
    prior_effective_cell_count: float = Field(ge=1)
    next_effective_cell_count: float = Field(ge=1)
    expected_utility_before: float
    expected_utility_after: float
    status: Literal["passed", "blocked"]
    failures: tuple[str, ...] = ()
    schema_version: str = REFINEMENT_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_update(self) -> PolicyUpdateResult:
        prior_ids = {cell.cell_id for cell in self.prior_policy.cells}
        next_ids = {cell.cell_id for cell in self.next_policy.cells}
        if self.statistics and {item.cell_id for item in self.statistics} != prior_ids:
            raise ValueError("feedback statistics must cover every prior policy cell")
        if set(self.cell_utilities) != prior_ids:
            raise ValueError("cell utilities must cover every prior policy cell")
        if self.cell_utility_components:
            if set(self.cell_utility_components) != prior_ids:
                raise ValueError(
                    "trajectory utility components must cover every prior policy cell"
                )
            if any(
                not math.isclose(
                    self.cell_utilities[cell_id],
                    component.utility,
                    abs_tol=1e-12,
                )
                for cell_id, component in self.cell_utility_components.items()
            ):
                raise ValueError("cell utility disagrees with its trajectory components")
        if self.utility_mode == "valid_trajectory_objective" and (
            not self.cell_utility_components
            or self.prior_trajectory_metrics is None
            or self.next_trajectory_metrics is None
            or self.trajectory_feedback_manifest_hash is None
            or self.trajectory_feedback_count < 1
        ):
            raise ValueError(
                "valid-trajectory updates require feedback, utility, and distribution components"
            )
        if set(self.cell_transition_map) != prior_ids:
            raise ValueError("cell transitions must cover every prior policy cell")
        if set(self.cell_transition_map.values()) != next_ids:
            raise ValueError("cell transitions must resolve every next policy cell")
        if set(self.allocated_counts) != next_ids:
            raise ValueError("allocations must cover every next policy cell")
        if sum(self.allocated_counts.values()) != self.total_budget:
            raise ValueError("CCGR allocations must preserve the total budget")
        if self.conditioning_mode == "fixed_group_marginals":
            if set(self.conditioning_groups) != next_ids:
                raise ValueError("conditioning groups must cover every next-policy Cell")
            observed_groups = set(self.conditioning_groups.values())
            if set(self.fixed_group_weights) != observed_groups:
                raise ValueError("fixed group weights must cover every conditioning group")
            if not math.isclose(sum(self.fixed_group_weights.values()), 1.0, abs_tol=1e-9):
                raise ValueError("fixed group weights must sum to one")
            if set(self.allocated_group_counts) != observed_groups:
                raise ValueError("allocated group counts must cover every conditioning group")
            observed_counts = {group: 0 for group in observed_groups}
            observed_probability = {group: 0.0 for group in observed_groups}
            for cell_id, group in self.conditioning_groups.items():
                observed_counts[group] += self.allocated_counts[cell_id]
                observed_probability[group] += self.next_policy.probabilities[cell_id]
            if observed_counts != self.allocated_group_counts:
                raise ValueError("Cell allocations disagree with fixed group allocations")
            if any(
                not math.isclose(
                    observed_probability[group],
                    self.fixed_group_weights[group],
                    abs_tol=1e-9,
                )
                for group in observed_groups
            ):
                raise ValueError("next policy does not preserve fixed group marginals")
        elif self.conditioning_groups or self.fixed_group_weights or self.allocated_group_counts:
            raise ValueError("global policy updates cannot carry conditioning metadata")
        if self.status == "passed" and self.failures:
            raise ValueError("a passed policy update cannot contain failures")
        if self.status == "blocked" and not self.failures:
            raise ValueError("a blocked policy update requires a failure reason")
        if self.update_id not in {
            policy_update_id(self),
            legacy_v2_policy_update_id(self),
            legacy_policy_update_id(self),
        }:
            raise ValueError("policy update identity is invalid")
        return self


def synthesis_cell_id(value: SynthesisCell) -> str:
    identity = {
        "pattern_id": value.pattern_id,
        "binding_stratum_id": value.binding_stratum_id,
        "difficulty_bucket": value.difficulty_bucket,
        "distractor_profile_id": value.distractor_profile_id,
        "active_binding_constraints": value.active_binding_constraints,
        "schema_version": value.schema_version,
    }
    if value.schema_version not in {"refinement.v1", "refinement.v2"}:
        identity["trajectory_attribute_profile_id"] = (
            value.trajectory_attribute_profile.profile_id
            if value.trajectory_attribute_profile is not None
            else "trajectory_profile:unspecified"
        )
    return canonical_hash(identity, prefix="synthesis_cell:")


def clause_feedback_id(value: ClauseFeedback) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"feedback_id"}),
        prefix="clause_feedback:",
    )


def synthesis_policy_id(value: SynthesisPolicy) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"policy_id"}),
        prefix="synthesis_policy:",
    )


def legacy_synthesis_policy_id(value: SynthesisPolicy) -> str:
    if value.schema_version not in {"refinement.v1", "refinement.v2"}:
        return "legacy_synthesis_policy:inapplicable"
    payload = value.model_dump(mode="json", exclude={"policy_id"})
    for cell in payload["cells"]:
        cell.pop("trajectory_attribute_profile", None)
    return canonical_hash(payload, prefix="synthesis_policy:")


def policy_update_id(value: PolicyUpdateResult) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"update_id"}),
        prefix="ccgr_policy_update:",
    )


def legacy_v2_policy_update_id(value: PolicyUpdateResult) -> str:
    """Accept persisted ccgr.v2 artifacts after additive v3 evolution."""

    if value.schema_version != "refinement.v2":
        return "legacy_ccgr_v2:inapplicable"
    payload = value.model_dump(mode="json", exclude={"update_id"})
    _strip_v3_update_fields(payload)
    return canonical_hash(payload, prefix="ccgr_policy_update:")


def legacy_policy_update_id(value: PolicyUpdateResult) -> str:
    """Accept persisted ccgr.v1 artifacts after additive schema evolution."""

    if value.schema_version != "refinement.v1":
        return "legacy_ccgr_v1:inapplicable"
    payload = value.model_dump(
        mode="json",
        exclude={
            "update_id",
            "conditioning_mode",
            "conditioning_groups",
            "fixed_group_weights",
            "allocated_group_counts",
        },
    )
    _strip_v3_update_fields(payload)
    added_statistic_fields = {
        "raw_synthesis_defect_weight_sum",
        "raw_capability_gap_weight_sum",
        "pattern_exposure_count",
        "pattern_synthesis_defect_rate",
        "pattern_capability_gap_rate",
        "cell_synthesis_defect_rate",
        "cell_capability_gap_rate",
        "shrinkage_weight",
        "minimum_exposure_met",
    }
    for statistic in payload["statistics"]:
        for field in added_statistic_fields:
            statistic.pop(field, None)
    return canonical_hash(payload, prefix="ccgr_policy_update:")


def _strip_v3_update_fields(payload: dict[str, Any]) -> None:
    for field in (
        "cell_utility_components",
        "alpha",
        "lambda_defect",
        "prior_trajectory_metrics",
        "next_trajectory_metrics",
        "trajectory_feedback_manifest_hash",
        "trajectory_feedback_count",
    ):
        payload.pop(field, None)
    added_statistic_fields = {
        "trajectory_attempt_count",
        "valid_trajectory_count",
        "trajectory_validity_rate",
        "mean_trajectory_validity_score",
        "trajectory_attribute_profile_count",
        "trajectory_attribute_entropy",
        "trajectory_diversity_gain",
        "missing_attribute_rate",
    }
    for statistic in payload["statistics"]:
        for field in added_statistic_fields:
            statistic.pop(field, None)
    for policy_key in ("prior_policy", "next_policy"):
        for cell in payload[policy_key]["cells"]:
            cell.pop("trajectory_attribute_profile", None)
