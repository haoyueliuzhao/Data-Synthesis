from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.vtdo.contribution import (
    ContributionInterventionObservation,
    ContributionProbeObservation,
)
from trusted_synthesis.hashing import canonical_hash

from .multistate import FinanceMultiStateConfig

VTDO_EXPERIMENT_VERSION = "vtdo_experiment.v6"

MovingPotentialMethod = Literal["no_feedback", "static_optimization", "full_vtdo"]
MovingPotentialTrack = Literal[
    "exogenous_shared",
    "vtdo_induced_shared",
    "method_specific_closed_loop",
]

VTDOTrainingArm = Literal[
    "B1_raw",
    "B2_validity",
    "B2_contribution_only",
    "B2_novelty_only",
    "B3_ccgr",
    "B4_random_state",
    "B5_vtdo",
]
VTDO_TRAINING_ARMS: tuple[VTDOTrainingArm, ...] = (
    "B1_raw",
    "B2_validity",
    "B2_contribution_only",
    "B2_novelty_only",
    "B3_ccgr",
    "B4_random_state",
    "B5_vtdo",
)

SyntheticMethod = Literal[
    "random",
    "novelty_only",
    "contribution_only",
    "no_global_coverage_anchor",
    "no_coverage_prior",
    "ccgr",
    "full_vtdo",
    "no_iteration",
    "no_quotient_exact",
    "no_quotient_noisy",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SyntheticExperimentConfig(FrozenModel):
    state_count: int = Field(default=200, ge=20)
    rounds: int = Field(default=20, ge=2)
    seeds: tuple[int, ...] = (11, 23, 37, 53, 71)
    reject_below: float = Field(default=0.3, ge=0, le=1)
    accept_at_or_above: float = Field(default=0.8, ge=0, le=1)
    coverage_epsilon: float = Field(default=1e-4, gt=0, lt=1)
    contribution_temperature: float = Field(default=1.0, gt=0)
    novelty_temperature: float = Field(default=1.0, gt=0)
    contribution_weight: float = Field(default=0.5, gt=0, lt=1)
    novelty_weight: float = Field(default=0.5, gt=0, lt=1)
    history_kl_weight: float = Field(default=1.0, gt=0)
    coverage_kl_weight: float = Field(default=1.0, gt=0)
    eta_sensitivity: tuple[float, ...] = (0.1, 0.25, 0.5, 1.0)
    raw_variants_per_state: int = Field(default=3, ge=2, le=10)

    @model_validator(mode="after")
    def validate_contract(self) -> SyntheticExperimentConfig:
        if self.reject_below >= self.accept_at_or_above:
            raise ValueError("synthetic validity thresholds are unordered")
        if not self.seeds or len(self.seeds) != len(set(self.seeds)):
            raise ValueError("synthetic seeds must be non-empty and unique")
        if not self.eta_sensitivity or any(value <= 0 for value in self.eta_sensitivity):
            raise ValueError("eta sensitivity values must be positive")
        if abs(self.contribution_weight + self.novelty_weight - 1.0) > 1e-12:
            raise ValueError("synthetic contribution and novelty weights must sum to one")
        return self


class MovingPotentialBenchmarkConfig(FrozenModel):
    """Frozen tracks for method-neutral and endogenous moving-optimum analysis."""

    enabled: Literal[True] = True
    rounds: int = Field(default=5, ge=2, le=50)
    tracks: tuple[MovingPotentialTrack, ...] = (
        "exogenous_shared",
        "vtdo_induced_shared",
        "method_specific_closed_loop",
    )
    primary_track: Literal["exogenous_shared"] = "exogenous_shared"
    drift_period: int = Field(default=5, ge=2)
    contribution_drift_scale: float = Field(default=0.75, gt=0)
    capability_decay: float = Field(default=0.15, ge=0)
    objective_tolerance: float = Field(default=1e-10, gt=0)
    require_regret_advantage: bool = True
    require_regret_ci_lower_bound_nonnegative: bool = True

    @model_validator(mode="after")
    def validate_tracks(self) -> MovingPotentialBenchmarkConfig:
        if len(self.tracks) != len(set(self.tracks)):
            raise ValueError("moving-potential tracks must be unique")
        if self.primary_track not in self.tracks:
            raise ValueError("primary moving-potential track is not enabled")
        return self


class RefinementDynamicsConfig(FrozenModel):
    """Frozen contract for fixed-potential and moving-potential round analysis."""

    enabled: Literal[True] = True
    method: Literal["full_vtdo"] = "full_vtdo"
    analysis_rounds: int = Field(default=5, ge=2)
    checkpoint_rounds: tuple[int, ...] = (1, 3, 5)
    primary_training_round: int = Field(default=3, ge=1)
    stabilization_score_threshold: float = Field(default=0.01, gt=0)
    utility_delta_weight: float = Field(default=1.0, ge=0)
    potential_drift_weight: float = Field(default=1.0, ge=0)
    coverage_epsilon: float = Field(default=1e-4, gt=0, lt=1)
    consecutive_stable_rounds: int = Field(default=2, ge=2)
    fixed_potential_rounds: int = Field(default=10, ge=2)
    contraction_tolerance: float = Field(default=1e-9, gt=0)
    moving_potential_benchmark: MovingPotentialBenchmarkConfig = MovingPotentialBenchmarkConfig()
    real_round_input_path: Path | None = None
    real_round_artifact_paths: tuple[Path, ...] = ()
    expected_real_task_condition_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_dynamics(self) -> RefinementDynamicsConfig:
        if not self.checkpoint_rounds:
            raise ValueError("refinement dynamics requires at least one checkpoint round")
        if len(self.checkpoint_rounds) != len(set(self.checkpoint_rounds)):
            raise ValueError("refinement checkpoint rounds must be unique")
        if tuple(sorted(self.checkpoint_rounds)) != self.checkpoint_rounds:
            raise ValueError("refinement checkpoint rounds must be ordered")
        if any(value < 1 or value > self.analysis_rounds for value in self.checkpoint_rounds):
            raise ValueError("refinement checkpoint round lies outside the analysis window")
        if self.primary_training_round not in self.checkpoint_rounds:
            raise ValueError("primary training round must be a declared checkpoint")
        if self.consecutive_stable_rounds > self.analysis_rounds:
            raise ValueError("stability window exceeds the refinement analysis window")
        if self.moving_potential_benchmark.rounds > self.analysis_rounds:
            raise ValueError("moving-potential benchmark exceeds the analysis window")
        if len(self.real_round_artifact_paths) != len(set(self.real_round_artifact_paths)):
            raise ValueError("real VTDO round artifact paths must be unique")
        if self.real_round_input_path is not None and self.real_round_artifact_paths:
            raise ValueError("configure real Round inputs or prebuilt artifacts, not both")
        expected_ids = self.expected_real_task_condition_ids
        if tuple(sorted(set(expected_ids))) != expected_ids:
            raise ValueError("expected real task-condition IDs must be ordered and unique")
        real_rounds_configured = self.real_round_input_path is not None or bool(
            self.real_round_artifact_paths
        )
        if real_rounds_configured != bool(expected_ids):
            raise ValueError(
                "real-round inputs and expected task-condition IDs must be configured together"
            )
        return self


class ExternalBenchmarkSnapshot(FrozenModel):
    benchmark_id: Literal["finqa", "tat_qa", "financebench"]
    path: Path
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_repository: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    split: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    metric_version: str = Field(min_length=1)
    usage: Literal["evaluation_only"] = "evaluation_only"


class ContributionValidationConfig(FrozenModel):
    enabled: bool = True
    observation_path: Path | None = None
    minimum_observation_count: int = Field(default=270, ge=6)
    minimum_unique_task_count: int = Field(default=30, ge=2)
    minimum_states_per_task: int = Field(default=3, ge=3)
    minimum_seeds_per_state: int = Field(default=3, ge=2)
    minimum_macro_spearman_ci_lower_bound: float = Field(default=0.2, ge=-1, le=1)
    minimum_pairwise_concordance_ci_lower_bound: float = Field(default=0.55, ge=0, le=1)
    cluster_bootstrap_samples: int = Field(default=2_000, ge=100)
    bootstrap_seed: int = 20260731


class BeneficiaryStateShiftConfig(FrozenModel):
    """One controlled M0 -> M1 check for model-state-dependent contribution."""

    enabled: bool = False
    baseline_observation_path: Path | None = None
    updated_observation_path: Path | None = None
    minimum_unique_task_count: int = Field(default=10, ge=2)
    minimum_states_per_task: int = Field(default=3, ge=3)
    minimum_seeds_per_state: int = Field(default=3, ge=2)
    baseline_round_index: int = Field(default=0, ge=0)
    updated_round_index: int = Field(default=1, ge=0)
    dependence_tolerance: float = Field(default=1e-6, ge=0)

    @model_validator(mode="after")
    def validate_rounds(self) -> BeneficiaryStateShiftConfig:
        if self.updated_round_index <= self.baseline_round_index:
            raise ValueError("updated beneficiary round must follow baseline round")
        return self


class TrainingExperimentConfig(FrozenModel):
    enabled: bool = False
    training_config_path: Path
    ccgr_task_distribution_path: Path | None = None
    external_benchmarks: tuple[ExternalBenchmarkSnapshot, ...] = ()
    target_supervised_tokens: int = Field(default=500_000, ge=1_000)
    minimum_unique_tasks_per_arm: int = Field(default=100, ge=1)
    minimum_unique_states_per_arm: int = Field(default=50, ge=1)
    gpu_ids: tuple[int, ...] = (3, 4, 5, 6, 7)
    seeds: tuple[int, ...] = (20260731, 20260801, 20260802)
    minimum_primary_seed_count: int = Field(default=3, ge=2)

    @model_validator(mode="after")
    def validate_training(self) -> TrainingExperimentConfig:
        if not self.gpu_ids or len(self.gpu_ids) != len(set(self.gpu_ids)):
            raise ValueError("training GPU IDs must be non-empty and unique")
        if not self.seeds or len(self.seeds) != len(set(self.seeds)):
            raise ValueError("training seeds must be non-empty and unique")
        if len(self.seeds) < self.minimum_primary_seed_count:
            raise ValueError("primary causal training requires multiple frozen seeds")
        benchmark_ids = [item.benchmark_id for item in self.external_benchmarks]
        if len(benchmark_ids) != len(set(benchmark_ids)):
            raise ValueError("external benchmark IDs must be unique")
        return self


class VTDOStudentTrainingConfig(FrozenModel):
    """Trainer-only contract, independent of historical D1-D5 cohort assumptions."""

    base_model: str = Field(min_length=1)
    model_revision: str | None = None
    max_seq_length: int = Field(default=24_576, ge=512, le=131_072)
    max_new_tokens: int = Field(default=1_536, ge=64, le=4_096)
    max_steps: int = Field(default=1_000, ge=1, le=10_000)
    supervised_token_budget: int = Field(default=500_000, ge=1_000)
    maximum_token_budget_deviation_rate: float = Field(default=0.04, ge=0, le=0.05)
    per_device_train_batch_size: int = Field(default=1, ge=1, le=16)
    gradient_accumulation_steps: int = Field(default=4, ge=1, le=128)
    learning_rate: float = Field(default=2e-4, gt=0)
    warmup_ratio: float = Field(default=0.1, ge=0, le=1)
    weight_decay: float = Field(default=0.01, ge=0)
    lora_rank: int = Field(default=8, ge=1, le=256)
    lora_alpha: int = Field(default=16, ge=1, le=512)
    lora_dropout: float = Field(default=0.05, ge=0, lt=1)
    lora_target_modules: tuple[str, ...] = (
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    )
    seed: int = 20260731
    prompt_version: Literal["vtdo_student_prompt.v2"] = "vtdo_student_prompt.v2"
    student_interaction_protocol: Literal["host_instrumented_decisions_v1"] = (
        "host_instrumented_decisions_v1"
    )
    budget_contract: Literal["equal_supervised_tokens"] = "equal_supervised_tokens"

    @classmethod
    def from_json(cls, path: str | Path) -> VTDOStudentTrainingConfig:
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))

    @property
    def config_hash(self) -> str:
        return canonical_hash(self, prefix="vtdo_student_training_config:")


class VTDOExperimentConfig(FrozenModel):
    experiment_id: str = "vtdo_experiment.finance.v6"
    synthetic: SyntheticExperimentConfig = SyntheticExperimentConfig()
    multi_state: FinanceMultiStateConfig
    training: TrainingExperimentConfig
    contribution_validation: ContributionValidationConfig = ContributionValidationConfig()
    beneficiary_state_shift: BeneficiaryStateShiftConfig = BeneficiaryStateShiftConfig()
    refinement_dynamics: RefinementDynamicsConfig = RefinementDynamicsConfig()
    output_dir: Path
    schema_version: str = VTDO_EXPERIMENT_VERSION

    @model_validator(mode="after")
    def validate_cross_section_contract(self) -> VTDOExperimentConfig:
        if self.refinement_dynamics.analysis_rounds > self.synthetic.rounds:
            raise ValueError("refinement analysis rounds exceed the synthetic experiment horizon")
        return self

    @classmethod
    def from_json(cls, path: str | Path) -> VTDOExperimentConfig:
        source = Path(path).resolve()
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["multi_state"]["finance_archive_config_path"] = _resolve_relative_path(
            source, payload["multi_state"]["finance_archive_config_path"]
        )
        payload["training"]["training_config_path"] = _resolve_relative_path(
            source, payload["training"]["training_config_path"]
        )
        ccgr_path = payload["training"].get("ccgr_task_distribution_path")
        if ccgr_path is not None:
            payload["training"]["ccgr_task_distribution_path"] = _resolve_relative_path(
                source, ccgr_path
            )
        for benchmark in payload["training"].get("external_benchmarks", ()):
            benchmark["path"] = _resolve_relative_path(source, benchmark["path"])
        contribution = payload.setdefault("contribution_validation", {})
        observation_path = contribution.get("observation_path")
        if observation_path is not None:
            contribution["observation_path"] = _resolve_relative_path(source, observation_path)
        beneficiary_shift = payload.setdefault("beneficiary_state_shift", {})
        for field in ("baseline_observation_path", "updated_observation_path"):
            raw_path = beneficiary_shift.get(field)
            if raw_path is not None:
                beneficiary_shift[field] = _resolve_relative_path(source, raw_path)
        dynamics = payload.setdefault("refinement_dynamics", {})
        real_round_input_path = dynamics.get("real_round_input_path")
        if real_round_input_path is not None:
            dynamics["real_round_input_path"] = _resolve_relative_path(
                source,
                real_round_input_path,
            )
        dynamics["real_round_artifact_paths"] = [
            _resolve_relative_path(source, raw_value)
            for raw_value in dynamics.get("real_round_artifact_paths", ())
        ]
        payload["output_dir"] = _resolve_relative_path(source, payload["output_dir"])
        return cls.model_validate(payload)

    @property
    def config_hash(self) -> str:
        return canonical_hash(self, prefix="vtdo_experiment_config:")


def _resolve_relative_path(config_path: Path, raw_value: object) -> Path:
    value = Path(str(raw_value))
    if not value.is_absolute():
        value = config_path.parent / value
    return value.resolve()


class SyntheticState(FrozenModel):
    state_id: str
    validity: float = Field(ge=0, le=1)
    validity_region: Literal["accepted", "quarantined", "rejected"]
    true_contribution: float
    coverage_prior: float = Field(gt=0, le=1)
    initial_probability: float = Field(gt=0, le=1)


class SyntheticMetricPoint(FrozenModel):
    seed: int
    method: SyntheticMethod
    round_index: int = Field(ge=0)
    kl_to_initial_fixed_target_diagnostic: float = Field(ge=0)
    expected_log_potential: float
    anchored_variational_objective: float
    expected_contribution_novelty_diagnostic: float
    expected_contribution: float
    coverage_kl: float = Field(ge=0)
    coverage_alignment: float = Field(gt=0, le=1)
    coverage_count: int = Field(ge=0)
    entropy: float = Field(ge=0)
    kl_to_previous: float = Field(ge=0)
    top_right_mass: float = Field(ge=0, le=1)
    support_size: int = Field(ge=1)
    raw_support_size: int | None = Field(default=None, ge=1)


class AggregateMetric(FrozenModel):
    mean: float
    standard_deviation: float = Field(ge=0)
    ci95_half_width: float = Field(ge=0)
    sample_count: int = Field(default=1, ge=1)
    interval_method: Literal["student_t_95"] = "student_t_95"


class RefinementRoundAggregate(FrozenModel):
    round_index: int = Field(ge=0)
    transition_from_round: int | None = Field(default=None, ge=0)
    kl_shift: AggregateMetric | None = None
    expected_log_potential: AggregateMetric
    absolute_utility_delta: AggregateMetric | None = None
    potential_drift: AggregateMetric | None = None
    stabilization_score: AggregateMetric | None = None
    entropy: AggregateMetric
    coverage_count: AggregateMetric
    stable_seed_count: int = Field(ge=0)


class RefinementCheckpointSummary(FrozenModel):
    round_index: int = Field(ge=1)
    role: Literal["one_shot", "primary_iterative", "analysis_only"]
    expected_log_potential: AggregateMetric
    log_potential_difference_from_round_one: float
    kl_shift: AggregateMetric
    entropy: AggregateMetric
    coverage_count: AggregateMetric
    downstream_training_evaluated: bool = False


class RefinementCheckpointTrainingPreflight(FrozenModel):
    training_config_hash: str
    supervised_token_budget: int = Field(ge=1_000)
    analysis_checkpoint_rounds: tuple[int, ...] = Field(min_length=2)
    training_checkpoint_rounds: tuple[int, ...] = Field(min_length=2)
    materialized_training_rounds: tuple[int, ...]
    records_per_checkpoint: dict[str, int]
    unique_tasks_per_checkpoint: dict[str, int]
    unique_states_per_checkpoint: dict[str, int]
    external_benchmark_status: Literal["ready", "not_available", "not_configured"]
    ready: bool
    blockers: tuple[str, ...]
    report_hash: str
    schema_version: str = VTDO_EXPERIMENT_VERSION

    @model_validator(mode="after")
    def validate_checkpoint_preflight(self) -> RefinementCheckpointTrainingPreflight:
        if tuple(sorted(set(self.analysis_checkpoint_rounds))) != self.analysis_checkpoint_rounds:
            raise ValueError("analysis checkpoint rounds must be ordered and unique")
        if tuple(sorted(set(self.training_checkpoint_rounds))) != self.training_checkpoint_rounds:
            raise ValueError("training checkpoint rounds must be ordered and unique")
        if not set(self.training_checkpoint_rounds).issubset(self.analysis_checkpoint_rounds):
            raise ValueError("training checkpoint lies outside the analysis contract")
        if not set(self.materialized_training_rounds).issubset(self.training_checkpoint_rounds):
            raise ValueError("materialized training round lies outside the frozen contract")
        expected_ready = (
            self.materialized_training_rounds == self.training_checkpoint_rounds
            and self.external_benchmark_status == "ready"
            and not self.blockers
        )
        if self.ready != expected_ready:
            raise ValueError("checkpoint training readiness is inconsistent")
        expected_keys = {str(value) for value in self.materialized_training_rounds}
        if any(
            set(values) != expected_keys
            for values in (
                self.records_per_checkpoint,
                self.unique_tasks_per_checkpoint,
                self.unique_states_per_checkpoint,
            )
        ):
            raise ValueError("checkpoint training counts have incomplete round coverage")
        if self.report_hash != refinement_checkpoint_training_preflight_hash(self):
            raise ValueError("checkpoint training preflight identity is invalid")
        return self


def refinement_checkpoint_training_preflight_hash(
    value: RefinementCheckpointTrainingPreflight,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_hash"}),
        prefix="vtdo_refinement_checkpoint_training_preflight:",
    )


class PracticalStabilizationSummary(FrozenModel):
    criterion_id: Literal["distribution_stabilization_consecutive_rounds"] = (
        "distribution_stabilization_consecutive_rounds"
    )
    stabilization_score_threshold: float = Field(gt=0)
    utility_delta_weight: float = Field(ge=0)
    potential_drift_weight: float = Field(ge=0)
    consecutive_rounds: int = Field(ge=2)
    evaluated_seed_count: int = Field(ge=1)
    stabilized_seed_count: int = Field(ge=0)
    first_stable_round_by_seed: dict[str, int | None]
    first_stable_round_counts: dict[str, int]
    practical_stabilization_observed: bool

    @model_validator(mode="after")
    def validate_stabilization(self) -> PracticalStabilizationSummary:
        observed = sum(value is not None for value in self.first_stable_round_by_seed.values())
        if len(self.first_stable_round_by_seed) != self.evaluated_seed_count:
            raise ValueError("stabilization summary has incomplete seed coverage")
        if observed != self.stabilized_seed_count:
            raise ValueError("stabilized seed count is inconsistent")
        if sum(self.first_stable_round_counts.values()) != self.evaluated_seed_count:
            raise ValueError("stabilization round counts are incomplete")
        if self.practical_stabilization_observed != (observed == self.evaluated_seed_count):
            raise ValueError("practical stabilization flag is inconsistent")
        return self


class FixedPotentialContractionSummary(FrozenModel):
    verification_role: Literal["update_operator_verification"] = "update_operator_verification"
    run_count: int = Field(ge=1)
    round_count: int = Field(ge=2)
    history_exponent: float = Field(gt=0, lt=1)
    energy_exponent: float = Field(gt=0)
    analytic_fixed_point_formula: str
    initial_projective_distance: AggregateMetric
    final_projective_distance: AggregateMetric
    observed_projective_contraction_factor: AggregateMetric
    maximum_absolute_factor_error: float = Field(ge=0)
    final_kl_to_fixed_point: AggregateMetric
    projective_contraction_verified: bool


class VariationalObjectiveVerificationSummary(FrozenModel):
    transition_count: int = Field(ge=1)
    monotonic_transition_count: int = Field(ge=0)
    minimum_objective_gain: float
    maximum_proximal_optimizer_kl: float = Field(ge=0)
    tolerance: float = Field(gt=0)
    all_transitions_verified: bool

    @model_validator(mode="after")
    def validate_objective(self) -> VariationalObjectiveVerificationSummary:
        if self.monotonic_transition_count > self.transition_count:
            raise ValueError("monotonic transition count exceeds its denominator")
        expected = (
            self.monotonic_transition_count == self.transition_count
            and self.minimum_objective_gain >= -self.tolerance
            and self.maximum_proximal_optimizer_kl <= self.tolerance
        )
        if self.all_transitions_verified != expected:
            raise ValueError("variational objective verification flag is inconsistent")
        return self


class MovingPotentialMethodSummary(FrozenModel):
    method: MovingPotentialMethod
    run_count: int = Field(ge=1)
    mean_tracking_error: AggregateMetric
    final_tracking_error: AggregateMetric
    cumulative_regret: AggregateMetric
    final_anchor_objective: AggregateMetric


class MovingPotentialTrackingSummary(FrozenModel):
    track: MovingPotentialTrack
    is_primary_track: bool
    status: Literal["passed", "failed"]
    state_count: int = Field(ge=2)
    round_count: int = Field(ge=2)
    seed_count: int = Field(ge=1)
    potential_sequence_definition: str
    instantaneous_optimum_formula: str
    method_summaries: tuple[MovingPotentialMethodSummary, ...]
    target_movement_kl: AggregateMetric
    variational_objective: VariationalObjectiveVerificationSummary
    vtdo_regret_advantage_over_no_feedback: AggregateMetric
    vtdo_regret_advantage_over_static: AggregateMetric
    regret_advantage_required: bool
    regret_advantage_ci_lower_bound_required: bool
    optimization_direction_supported: bool
    report_hash: str

    @model_validator(mode="after")
    def validate_tracking(self) -> MovingPotentialTrackingSummary:
        methods = {item.method for item in self.method_summaries}
        if methods != {"no_feedback", "static_optimization", "full_vtdo"}:
            raise ValueError("moving-potential benchmark has an incomplete method set")
        if any(item.run_count != self.seed_count for item in self.method_summaries):
            raise ValueError("moving-potential method summaries have incomplete seed coverage")
        if self.variational_objective.transition_count != self.seed_count * self.round_count:
            raise ValueError("moving-potential objective replay has incomplete transitions")
        expected_status = (
            "passed"
            if self.variational_objective.all_transitions_verified
            and (self.optimization_direction_supported or not self.regret_advantage_required)
            else "failed"
        )
        if self.status != expected_status:
            raise ValueError("moving-potential status is inconsistent with its checks")
        if self.is_primary_track != (self.track == "exogenous_shared"):
            raise ValueError("moving-potential primary-track flag is inconsistent")
        if self.report_hash != moving_potential_tracking_hash(self):
            raise ValueError("moving-potential tracking identity is invalid")
        return self


class RealRefinementDynamicsSummary(FrozenModel):
    status: Literal["not_configured", "passed", "partial", "blocked"]
    configured_artifact_count: int = Field(ge=0)
    validated_artifact_count: int = Field(ge=0)
    task_condition_count: int = Field(ge=0)
    expected_task_condition_count: int = Field(default=0, ge=0)
    missing_task_condition_count: int = Field(default=0, ge=0)
    unexpected_task_condition_count: int = Field(default=0, ge=0)
    turnover_probability_threshold: float | None = Field(default=None, gt=0, lt=1)
    complete_sequence_count: int = Field(ge=0)
    sequential_link_failure_count: int = Field(ge=0)
    stabilization_eligible_sequence_count: int = Field(ge=0)
    stabilized_sequence_count: int = Field(ge=0)
    mean_final_kl_shift: float | None = Field(default=None, ge=0)
    variational_transition_count: int = Field(default=0, ge=0)
    variational_monotonic_transition_count: int = Field(default=0, ge=0)
    minimum_variational_objective_gain: float | None = None
    maximum_proximal_optimizer_kl: float | None = Field(default=None, ge=0)
    variational_objective_verified: bool | None = None
    mean_final_tracking_error: float | None = Field(default=None, ge=0)
    mean_cumulative_regret: float | None = Field(default=None, ge=0)
    mean_target_movement_kl: float | None = Field(default=None, ge=0)
    mean_state_entries_per_transition: float | None = Field(default=None, ge=0)
    mean_state_exits_per_transition: float | None = Field(default=None, ge=0)
    blockers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_real_dynamics(self) -> RealRefinementDynamicsSummary:
        if self.stabilized_sequence_count > self.stabilization_eligible_sequence_count:
            raise ValueError("stabilized sequence count exceeds its denominator")
        if self.variational_monotonic_transition_count > self.variational_transition_count:
            raise ValueError("real variational transition count is inconsistent")
        if self.status == "not_configured" and (
            self.configured_artifact_count or self.validated_artifact_count
        ):
            raise ValueError("not-configured real dynamics contains artifacts")
        if self.status == "passed" and self.variational_objective_verified is not True:
            raise ValueError("passed real dynamics lacks exact objective verification")
        return self


class RefinementDynamicsReport(FrozenModel):
    experiment_id: str
    config_hash: str
    controlled_method: Literal["full_vtdo"] = "full_vtdo"
    analysis_rounds: int = Field(ge=2)
    round_aggregates: tuple[RefinementRoundAggregate, ...]
    checkpoint_summaries: tuple[RefinementCheckpointSummary, ...]
    practical_stabilization: PracticalStabilizationSummary
    fixed_potential_contraction: FixedPotentialContractionSummary
    primary_moving_potential_track: Literal["exogenous_shared"] = "exogenous_shared"
    moving_potential_tracks: tuple[MovingPotentialTrackingSummary, ...]
    real_refinement: RealRefinementDynamicsSummary
    strict_convergence_claim_supported: bool = False
    interpretation: str
    report_hash: str
    schema_version: str = VTDO_EXPERIMENT_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> RefinementDynamicsReport:
        if self.strict_convergence_claim_supported:
            raise ValueError("moving-potential refinement cannot claim strict convergence")
        tracks = {item.track for item in self.moving_potential_tracks}
        if len(tracks) != len(self.moving_potential_tracks):
            raise ValueError("moving-potential report contains duplicate tracks")
        if self.primary_moving_potential_track not in tracks:
            raise ValueError("moving-potential report lacks its primary track")
        if sum(item.is_primary_track for item in self.moving_potential_tracks) != 1:
            raise ValueError("moving-potential report must identify exactly one primary track")
        if self.report_hash != refinement_dynamics_report_hash(self):
            raise ValueError("refinement dynamics report identity is invalid")
        return self


def refinement_dynamics_report_hash(value: RefinementDynamicsReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_hash"}),
        prefix="vtdo_refinement_dynamics_report:",
    )


def moving_potential_tracking_hash(value: MovingPotentialTrackingSummary) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_hash"}),
        prefix="moving_potential_tracking:",
    )


class SyntheticMethodSummary(FrozenModel):
    method: SyntheticMethod
    run_count: int = Field(ge=1)
    final_expected_log_potential: AggregateMetric
    final_anchored_variational_objective: AggregateMetric
    final_expected_contribution_novelty_diagnostic: AggregateMetric
    final_coverage_kl: AggregateMetric
    final_coverage_alignment: AggregateMetric
    final_coverage_count: AggregateMetric
    final_entropy: AggregateMetric
    final_top_right_mass: AggregateMetric


class EtaSensitivityResult(FrozenModel):
    energy_exponent: float = Field(gt=0)
    final_expected_log_potential: AggregateMetric
    final_anchored_variational_objective: AggregateMetric
    final_expected_contribution_novelty_diagnostic: AggregateMetric
    final_coverage_kl: AggregateMetric
    final_coverage_alignment: AggregateMetric
    final_entropy: AggregateMetric


class SyntheticExperimentReport(FrozenModel):
    experiment_id: str
    config_hash: str
    reference_definitions: dict[str, str]
    production_algorithm_id: str
    production_algorithm_version: str
    state_count: int
    accepted_state_counts: dict[str, int]
    metric_points: tuple[SyntheticMetricPoint, ...]
    main_method_summaries: tuple[SyntheticMethodSummary, ...]
    ablation_summaries: tuple[SyntheticMethodSummary, ...]
    eta_sensitivity: tuple[EtaSensitivityResult, ...]
    artifact_hash: str
    schema_version: str = VTDO_EXPERIMENT_VERSION


class VTDOTrainingRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    arm_id: VTDOTrainingArm
    task_id: str = Field(min_length=1)
    trajectory_state_id: str | None = None
    accepted_target: bool
    system_prompt: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)
    assistant_target: str = Field(min_length=1)
    target_contract: Literal["host_instrumented_decisions.v1"] = "host_instrumented_decisions.v1"
    sampling_weight: float = Field(gt=0)
    source_artifact_id: str = Field(min_length=1)
    source_distribution_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: Literal["vtdo_training_record.v2"] = "vtdo_training_record.v2"

    @model_validator(mode="after")
    def validate_identity(self) -> VTDOTrainingRecord:
        if self.record_id != vtdo_training_record_id(self):
            raise ValueError("VTDO training record identity is invalid")
        return self


class CCGRTaskDistribution(FrozenModel):
    distribution_id: str = Field(min_length=1)
    task_probabilities: dict[str, float] = Field(min_length=1)
    feedback_manifest_hash: str = Field(min_length=1)
    method: Literal["ccgr"] = "ccgr"
    schema_version: Literal["ccgr_task_distribution.v1"] = "ccgr_task_distribution.v1"

    @model_validator(mode="after")
    def validate_distribution(self) -> CCGRTaskDistribution:
        if any(value <= 0 for value in self.task_probabilities.values()):
            raise ValueError("CCGR task probabilities must be positive")
        if abs(sum(self.task_probabilities.values()) - 1.0) > 1e-9:
            raise ValueError("CCGR task probabilities must sum to one")
        if self.distribution_id != ccgr_task_distribution_id(self):
            raise ValueError("CCGR task distribution identity is invalid")
        return self


class ContributionValidationObservation(FrozenModel):
    """Pair independent Probe and Intervention estimates on one (x, t, z, seed)."""

    observation_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    round_index: int = Field(ge=0)
    state_id: str = Field(min_length=1)
    seed: int
    baseline_distribution_id: str = Field(min_length=1)
    probe_observation: ContributionProbeObservation
    intervention_observation: ContributionInterventionObservation
    schema_version: Literal["contribution_validation_observation.v6"] = (
        "contribution_validation_observation.v6"
    )

    @model_validator(mode="after")
    def validate_identity(self) -> ContributionValidationObservation:
        probe = self.probe_observation
        intervention = self.intervention_observation
        if (
            probe.task_condition_id != self.task_condition_id
            or intervention.task_condition_id != self.task_condition_id
            or probe.round_index != self.round_index
            or intervention.round_index != self.round_index
            or probe.state_id != self.state_id
            or intervention.state_id != self.state_id
            or probe.seed != self.seed
            or intervention.seed != self.seed
        ):
            raise ValueError("Contribution validation pair has mismatched support")
        probe_contract = probe.probe_contract
        intervention_contract = intervention.intervention_contract
        if (
            probe_contract.beneficiary_model_state_id
            != intervention_contract.beneficiary_model_state_id
            or probe_contract.beneficiary_checkpoint_hash
            != intervention_contract.beneficiary_checkpoint_hash
            or probe_contract.metric_contract != intervention_contract.metric_contract
            or probe_contract.data_isolation != intervention_contract.data_isolation
        ):
            raise ValueError("Contribution validation pair has mismatched frozen identity")
        if (
            probe.adaptation_result.adapted_model_state_id
            == intervention.training_result.intervention_model_state_id
            or probe.adaptation_result.adapted_checkpoint_hash
            == intervention.training_result.intervention_checkpoint_hash
        ):
            raise ValueError("Contribution validation estimators reuse one trained artifact")
        if not math.isclose(
            probe.baseline_performance,
            intervention.baseline_performance,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("Contribution validation pair has mismatched baseline performance")
        if self.observation_id != contribution_validation_observation_id(self):
            raise ValueError("contribution-validation observation identity is invalid")
        return self


class ContributionValidationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    observation_count: int = Field(ge=0)
    unique_task_count: int = Field(ge=0)
    unique_round_count: int = Field(ge=0)
    unique_task_round_count: int = Field(ge=0)
    unique_state_count: int = Field(ge=0)
    paired_seed_count: int = Field(ge=0)
    aggregated_state_count: int = Field(ge=0)
    mean_within_state_intervention_variance: float | None = Field(default=None, ge=0)
    eligible_task_round_count: int = Field(ge=0)
    task_rank_correlation: AggregateMetric | None = None
    task_rank_bootstrap_ci95: tuple[float, float] | None = None
    centered_global_spearman: float | None = Field(default=None, ge=-1, le=1)
    pairwise_concordance_rate: float | None = Field(default=None, ge=0, le=1)
    pairwise_concordance_bootstrap_ci95: tuple[float, float] | None = None
    pair_count: int = Field(ge=0)
    sign_agreement_rate: float | None = Field(default=None, ge=0, le=1)
    frozen_identity: dict[str, str] = Field(default_factory=dict)
    status: Literal["passed", "blocked"]
    blockers: tuple[str, ...]
    schema_version: Literal["contribution_validation_report.v6"] = (
        "contribution_validation_report.v6"
    )

    @model_validator(mode="after")
    def validate_identity(self) -> ContributionValidationReport:
        if self.status == "passed" and self.blockers:
            raise ValueError("passed Contribution validation report has blockers")
        if self.status == "blocked" and not self.blockers:
            raise ValueError("blocked Contribution validation report lacks blockers")
        if self.report_id != contribution_validation_report_id(self):
            raise ValueError("contribution-validation report identity is invalid")
        return self


class BeneficiaryStateShiftReport(FrozenModel):
    report_id: str = Field(min_length=1)
    baseline_model_state_id: str | None = None
    updated_model_state_id: str | None = None
    baseline_round_index: int = Field(ge=0)
    updated_round_index: int = Field(ge=0)
    atomic_pair_count: int = Field(ge=0)
    unique_task_count: int = Field(ge=0)
    aggregated_state_count: int = Field(ge=0)
    probe_seed_count: int = Field(ge=0)
    mean_absolute_contribution_shift: AggregateMetric | None = None
    mean_absolute_shift_ci95_lower_bound: float | None = Field(default=None, ge=0)
    task_rank_correlation: AggregateMetric | None = None
    contribution_direction_change_rate: float | None = Field(default=None, ge=0, le=1)
    model_state_dependence_observed: bool | None = None
    dependence_tolerance: float = Field(ge=0)
    frozen_comparison_identity: dict[str, str] = Field(default_factory=dict)
    status: Literal["passed", "blocked"]
    blockers: tuple[str, ...]
    schema_version: Literal["beneficiary_state_shift_report.v4"] = (
        "beneficiary_state_shift_report.v4"
    )

    @model_validator(mode="after")
    def validate_identity(self) -> BeneficiaryStateShiftReport:
        if self.updated_round_index <= self.baseline_round_index:
            raise ValueError("beneficiary-state shift round order is invalid")
        if self.model_state_dependence_observed is not None:
            expected = bool(
                self.mean_absolute_shift_ci95_lower_bound is not None
                and self.mean_absolute_shift_ci95_lower_bound > self.dependence_tolerance
            )
            if self.model_state_dependence_observed != expected:
                raise ValueError("beneficiary-state dependence decision is inconsistent")
        if self.status == "passed" and self.blockers:
            raise ValueError("passed beneficiary-state shift report has blockers")
        if self.status == "blocked" and not self.blockers:
            raise ValueError("blocked beneficiary-state shift report lacks blockers")
        if self.report_id != beneficiary_state_shift_report_id(self):
            raise ValueError("beneficiary-state shift report identity is invalid")
        return self


def beneficiary_state_shift_report_id(value: BeneficiaryStateShiftReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="beneficiary_state_shift_report:",
    )


class TrainingArmCapacity(FrozenModel):
    arm_id: VTDOTrainingArm
    source_record_count: int = Field(ge=0)
    unique_task_count: int = Field(ge=0)
    unique_state_count: int = Field(ge=0)
    multi_state_task_count: int = Field(ge=0)
    maximum_states_per_task: int = Field(ge=0)
    accepted_only: bool
    comparison_role: Literal[
        "primary_fixed_task_marginal",
        "secondary_task_marginal_baseline",
        "controlled_quality_lower_bound",
    ]
    task_marginal_policy: Literal["uniform_fixed", "ccgr_nonuniform"]
    minimum_task_weight: float = Field(ge=0)
    maximum_task_weight: float = Field(ge=0)
    maximum_task_weight_deviation: float = Field(ge=0)
    task_marginal_verified: bool
    budget_contract: Literal["equal_supervised_tokens"] = "equal_supervised_tokens"
    requested_supervised_tokens: int = Field(ge=1)
    capacity_status: Literal["ready", "pilot_only", "blocked"]
    blockers: tuple[str, ...] = ()


class TrainingExperimentPreflight(FrozenModel):
    training_config_hash: str
    base_model: str
    model_revision: str | None = None
    supervised_token_budget: int = Field(ge=1_000)
    training_seeds: tuple[int, ...] = Field(min_length=3)
    arms: tuple[TrainingArmCapacity, ...]
    primary_causal_arms: tuple[VTDOTrainingArm, ...]
    secondary_comparison_arms: tuple[VTDOTrainingArm, ...]
    primary_task_marginal_contract_verified: bool
    primary_causal_training_ready: bool
    full_comparison_matrix_ready: bool
    permitted_arm_ids: tuple[VTDOTrainingArm, ...]
    external_benchmark_status: Literal["ready", "not_available", "not_configured"]
    benchmark_leakage_status: Literal["passed", "failed", "not_configured"]
    benchmark_leakage_count: int = Field(ge=0)
    benchmark_leakage_report_hash: str | None = None
    shared_training_blockers: tuple[str, ...]
    primary_causal_blockers: tuple[str, ...]
    secondary_comparison_blockers: tuple[str, ...]
    blockers: tuple[str, ...]
    report_hash: str
    schema_version: str = VTDO_EXPERIMENT_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> TrainingExperimentPreflight:
        if self.primary_causal_training_ready != (
            not self.shared_training_blockers and not self.primary_causal_blockers
        ):
            raise ValueError("primary-causal readiness is inconsistent with its blockers")
        if self.full_comparison_matrix_ready != (
            self.primary_causal_training_ready and not self.secondary_comparison_blockers
        ):
            raise ValueError("full-matrix readiness is inconsistent with its blockers")
        expected_permitted = (
            tuple(item.arm_id for item in self.arms if item.capacity_status == "ready")
            if not self.shared_training_blockers
            else ()
        )
        if self.permitted_arm_ids != expected_permitted:
            raise ValueError("permitted training arms are inconsistent with frozen capacities")
        if len(self.permitted_arm_ids) != len(set(self.permitted_arm_ids)):
            raise ValueError("permitted training arms must be unique")
        if self.report_hash != training_experiment_preflight_hash(self):
            raise ValueError("VTDO training preflight identity is invalid")
        return self


def training_experiment_preflight_hash(value: TrainingExperimentPreflight) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_hash"}),
        prefix="vtdo_training_preflight:",
    )


class VTDOTrainingRunResult(FrozenModel):
    result_id: str = Field(min_length=1)
    arm_id: VTDOTrainingArm
    config_hash: str = Field(min_length=1)
    dataset_hash: str = Field(min_length=1)
    training_input_sha256: dict[str, str]
    training_input_manifest_hash: str = Field(min_length=1)
    base_model: str = Field(min_length=1)
    base_model_manifest_hash: str = Field(min_length=1)
    adapter_manifest_hash: str = Field(min_length=1)
    model_revision: str | None = None
    training_seed: int
    adapter_dir: str = Field(min_length=1)
    completed_steps: int = Field(ge=0)
    final_train_loss: float | None = None
    supervised_token_count: int = Field(ge=1)
    supervised_token_budget: int = Field(ge=1_000)
    prompt_token_count: int = Field(ge=1)
    processed_token_count: int = Field(ge=1)
    scheduled_example_count: int = Field(ge=1)
    unique_scheduled_record_count: int = Field(ge=1)
    repeated_example_rate: float = Field(ge=0, le=1)
    budget_contract: Literal["equal_supervised_tokens"] = "equal_supervised_tokens"
    token_budget_deviation_rate: float = Field(ge=0)
    train_runtime_seconds: float = Field(ge=0)
    peak_gpu_memory_bytes: int = Field(ge=0)
    dependency_versions: dict[str, str]
    status: Literal["completed"] = "completed"
    schema_version: Literal["vtdo_training_run.v4"] = "vtdo_training_run.v4"

    @model_validator(mode="after")
    def validate_identity(self) -> VTDOTrainingRunResult:
        required_inputs = {"student_config", "preflight", "arm_manifest", "dataset"}
        if set(self.training_input_sha256) != required_inputs:
            raise ValueError("training input SHA256 manifest is incomplete")
        if any(
            len(value) != 64 or any(char not in "0123456789abcdef" for char in value)
            for value in self.training_input_sha256.values()
        ):
            raise ValueError("training input SHA256 manifest contains an invalid digest")
        expected_input_hash = canonical_hash(
            self.training_input_sha256,
            prefix="vtdo_training_input_manifest:",
        )
        if self.training_input_manifest_hash != expected_input_hash:
            raise ValueError("training input manifest identity is invalid")
        if self.result_id != vtdo_training_run_result_id(self):
            raise ValueError("VTDO training run identity is invalid")
        return self


def vtdo_training_record_id(value: VTDOTrainingRecord) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"record_id"}),
        prefix="vtdo_training_record:",
    )


def ccgr_task_distribution_id(value: CCGRTaskDistribution) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"distribution_id"}),
        prefix="ccgr_task_distribution:",
    )


def contribution_validation_observation_id(
    value: ContributionValidationObservation,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"observation_id"}),
        prefix="contribution_validation_observation:",
    )


def contribution_validation_report_id(value: ContributionValidationReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="contribution_validation_report:",
    )


def vtdo_training_run_result_id(value: VTDOTrainingRunResult) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"result_id"}),
        prefix="vtdo_training_run:",
    )


class VTDOExperimentManifest(FrozenModel):
    experiment_id: str
    config_hash: str
    synthetic_report_hash: str
    refinement_dynamics_report_hash: str | None = None
    multi_state_report_id: str | None = None
    contribution_validation_report_id: str | None = None
    beneficiary_state_shift_report_id: str | None = None
    training_preflight_hash: str | None = None
    refinement_checkpoint_training_preflight_hash: str | None = None
    input_manifest_hash: str
    completed_components: tuple[str, ...]
    blocked_components: tuple[str, ...]
    artifact_paths: dict[str, str]
    git_commit: str
    git_worktree_dirty: bool
    status: Literal["passed", "partial", "blocked"]
    limitations: tuple[str, ...] = ()
    manifest_hash: str
    schema_version: str = VTDO_EXPERIMENT_VERSION
