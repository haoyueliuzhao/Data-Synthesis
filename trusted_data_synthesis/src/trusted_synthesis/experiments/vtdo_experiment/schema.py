from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

from .multistate import FinanceMultiStateConfig

VTDO_EXPERIMENT_VERSION = "vtdo_experiment.v1"

VTDOTrainingArm = Literal[
    "B1_raw",
    "B2_validity",
    "B3_ccgr",
    "B4_random_state",
    "B5_vtdo",
]
VTDO_TRAINING_ARMS: tuple[VTDOTrainingArm, ...] = (
    "B1_raw",
    "B2_validity",
    "B3_ccgr",
    "B4_random_state",
    "B5_vtdo",
)

SyntheticMethod = Literal[
    "random",
    "novelty_only",
    "contribution_only",
    "no_anchor",
    "ccgr",
    "full_vtdo",
    "no_iteration",
    "no_quotient",
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


class RefinementDynamicsConfig(FrozenModel):
    """Frozen contract for fixed-potential and moving-potential round analysis."""

    enabled: Literal[True] = True
    method: Literal["full_vtdo"] = "full_vtdo"
    analysis_rounds: int = Field(default=5, ge=2)
    checkpoint_rounds: tuple[int, ...] = (1, 3, 5)
    primary_training_round: int = Field(default=3, ge=1)
    stabilization_score_threshold: float = Field(default=0.01, gt=0)
    utility_delta_weight: float = Field(default=1.0, ge=0)
    coverage_epsilon: float = Field(default=1e-4, gt=0, lt=1)
    consecutive_stable_rounds: int = Field(default=2, ge=2)
    fixed_potential_rounds: int = Field(default=10, ge=2)
    contraction_tolerance: float = Field(default=1e-9, gt=0)
    real_round_artifact_paths: tuple[Path, ...] = ()

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
        if len(self.real_round_artifact_paths) != len(set(self.real_round_artifact_paths)):
            raise ValueError("real VTDO round artifact paths must be unique")
        return self


class ExternalBenchmarkSnapshot(FrozenModel):
    benchmark_id: Literal["finqa", "tat_qa", "financebench"]
    path: Path
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    usage: Literal["evaluation_only"] = "evaluation_only"


class ContributionValidationConfig(FrozenModel):
    enabled: bool = True
    observation_path: Path | None = None
    minimum_observation_count: int = Field(default=100, ge=1)
    minimum_unique_task_count: int = Field(default=100, ge=1)
    minimum_absolute_spearman: float = Field(default=0.2, ge=0, le=1)


class TrainingExperimentConfig(FrozenModel):
    enabled: bool = False
    training_config_path: Path
    ccgr_task_distribution_path: Path | None = None
    external_benchmarks: tuple[ExternalBenchmarkSnapshot, ...] = ()
    target_supervised_tokens: int = Field(default=500_000, ge=1_000)
    minimum_unique_tasks_per_arm: int = Field(default=100, ge=1)
    minimum_unique_states_per_arm: int = Field(default=50, ge=1)
    gpu_ids: tuple[int, ...] = (3, 4, 5, 6, 7)
    seeds: tuple[int, ...] = (20260731,)

    @model_validator(mode="after")
    def validate_training(self) -> TrainingExperimentConfig:
        if not self.gpu_ids or len(self.gpu_ids) != len(set(self.gpu_ids)):
            raise ValueError("training GPU IDs must be non-empty and unique")
        if not self.seeds or len(self.seeds) != len(set(self.seeds)):
            raise ValueError("training seeds must be non-empty and unique")
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
    prompt_version: Literal["vtdo_student_prompt.v1"] = "vtdo_student_prompt.v1"
    student_interaction_protocol: Literal["host_instrumented_joint"] = "host_instrumented_joint"

    @classmethod
    def from_json(cls, path: str | Path) -> VTDOStudentTrainingConfig:
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))

    @property
    def config_hash(self) -> str:
        return canonical_hash(self, prefix="vtdo_student_training_config:")


class VTDOExperimentConfig(FrozenModel):
    experiment_id: str = "vtdo_experiment.finance.v1"
    synthetic: SyntheticExperimentConfig = SyntheticExperimentConfig()
    multi_state: FinanceMultiStateConfig
    training: TrainingExperimentConfig
    contribution_validation: ContributionValidationConfig = ContributionValidationConfig()
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
            contribution["observation_path"] = _resolve_relative_path(
                source, observation_path
            )
        dynamics = payload.setdefault("refinement_dynamics", {})
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
    kl_to_vtdo_optimum: float = Field(ge=0)
    expected_contribution_novelty: float
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


class RefinementRoundAggregate(FrozenModel):
    round_index: int = Field(ge=0)
    transition_from_round: int | None = Field(default=None, ge=0)
    kl_shift: AggregateMetric | None = None
    expected_utility: AggregateMetric
    absolute_utility_delta: AggregateMetric | None = None
    stabilization_score: AggregateMetric | None = None
    entropy: AggregateMetric
    coverage_count: AggregateMetric
    stable_seed_count: int = Field(ge=0)


class RefinementCheckpointSummary(FrozenModel):
    round_index: int = Field(ge=1)
    role: Literal["one_shot", "primary_iterative", "analysis_only"]
    expected_utility: AggregateMetric
    utility_gain_from_one_shot: float
    kl_shift: AggregateMetric
    entropy: AggregateMetric
    coverage_count: AggregateMetric
    downstream_training_evaluated: bool = False


class PracticalConvergenceSummary(FrozenModel):
    criterion_id: Literal["combined_score_consecutive_rounds"] = (
        "combined_score_consecutive_rounds"
    )
    stabilization_score_threshold: float = Field(gt=0)
    utility_delta_weight: float = Field(ge=0)
    consecutive_rounds: int = Field(ge=2)
    evaluated_seed_count: int = Field(ge=1)
    converged_seed_count: int = Field(ge=0)
    convergence_round_by_seed: dict[str, int | None]
    convergence_round_counts: dict[str, int]
    practical_convergence_observed: bool


class FixedPotentialContractionSummary(FrozenModel):
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


class RealRefinementDynamicsSummary(FrozenModel):
    status: Literal["not_configured", "passed", "partial", "blocked"]
    configured_artifact_count: int = Field(ge=0)
    validated_artifact_count: int = Field(ge=0)
    task_condition_count: int = Field(ge=0)
    complete_sequence_count: int = Field(ge=0)
    sequential_link_failure_count: int = Field(ge=0)
    convergence_eligible_sequence_count: int = Field(ge=0)
    converged_sequence_count: int = Field(ge=0)
    mean_final_kl_shift: float | None = Field(default=None, ge=0)
    blockers: tuple[str, ...] = ()


class RefinementDynamicsReport(FrozenModel):
    experiment_id: str
    config_hash: str
    controlled_method: Literal["full_vtdo"] = "full_vtdo"
    analysis_rounds: int = Field(ge=2)
    round_aggregates: tuple[RefinementRoundAggregate, ...]
    checkpoint_summaries: tuple[RefinementCheckpointSummary, ...]
    practical_convergence: PracticalConvergenceSummary
    fixed_potential_contraction: FixedPotentialContractionSummary
    real_refinement: RealRefinementDynamicsSummary
    strict_convergence_claim_supported: bool = False
    interpretation: str
    report_hash: str
    schema_version: str = VTDO_EXPERIMENT_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> RefinementDynamicsReport:
        if self.strict_convergence_claim_supported:
            raise ValueError("moving-potential refinement cannot claim strict convergence")
        if self.report_hash != refinement_dynamics_report_hash(self):
            raise ValueError("refinement dynamics report identity is invalid")
        return self


def refinement_dynamics_report_hash(value: RefinementDynamicsReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_hash"}),
        prefix="vtdo_refinement_dynamics_report:",
    )


class SyntheticMethodSummary(FrozenModel):
    method: SyntheticMethod
    run_count: int = Field(ge=1)
    final_kl_to_vtdo_optimum: AggregateMetric
    final_expected_utility: AggregateMetric
    final_coverage_kl: AggregateMetric
    final_coverage_alignment: AggregateMetric
    final_coverage_count: AggregateMetric
    final_entropy: AggregateMetric
    final_top_right_mass: AggregateMetric


class EtaSensitivityResult(FrozenModel):
    energy_exponent: float = Field(gt=0)
    final_kl_to_vtdo_optimum: AggregateMetric
    final_expected_utility: AggregateMetric
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
    sampling_weight: float = Field(gt=0)
    source_artifact_id: str = Field(min_length=1)
    source_distribution_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: Literal["vtdo_training_record.v1"] = "vtdo_training_record.v1"

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
    observation_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    beneficiary_model_state_id: str = Field(min_length=1)
    evaluation_distribution_id: str = Field(min_length=1)
    target_metric_id: str = Field(min_length=1)
    estimated_contribution: float
    observed_delta_j: float
    sample_count: int = Field(ge=1)
    schema_version: Literal["contribution_validation_observation.v1"] = (
        "contribution_validation_observation.v1"
    )

    @model_validator(mode="after")
    def validate_identity(self) -> ContributionValidationObservation:
        if self.observation_id != contribution_validation_observation_id(self):
            raise ValueError("contribution-validation observation identity is invalid")
        return self


class ContributionValidationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    observation_count: int = Field(ge=0)
    unique_task_count: int = Field(ge=0)
    unique_state_count: int = Field(ge=0)
    spearman_correlation: float | None = Field(default=None, ge=-1, le=1)
    sign_agreement_rate: float | None = Field(default=None, ge=0, le=1)
    status: Literal["passed", "blocked"]
    blockers: tuple[str, ...]
    schema_version: Literal["contribution_validation_report.v1"] = (
        "contribution_validation_report.v1"
    )

    @model_validator(mode="after")
    def validate_identity(self) -> ContributionValidationReport:
        if self.report_id != contribution_validation_report_id(self):
            raise ValueError("contribution-validation report identity is invalid")
        return self


class TrainingArmCapacity(FrozenModel):
    arm_id: VTDOTrainingArm
    source_record_count: int = Field(ge=0)
    unique_task_count: int = Field(ge=0)
    unique_state_count: int = Field(ge=0)
    multi_state_task_count: int = Field(ge=0)
    maximum_states_per_task: int = Field(ge=0)
    accepted_only: bool
    requested_supervised_tokens: int = Field(ge=1)
    capacity_status: Literal["ready", "pilot_only", "blocked"]
    blockers: tuple[str, ...] = ()


class TrainingExperimentPreflight(FrozenModel):
    training_config_hash: str
    base_model: str
    model_revision: str | None = None
    supervised_token_budget: int = Field(ge=1_000)
    training_seed: int
    arms: tuple[TrainingArmCapacity, ...]
    formal_training_ready: bool
    pilot_training_ready: bool
    external_benchmark_status: Literal["ready", "not_available", "not_configured"]
    blockers: tuple[str, ...]
    report_hash: str
    schema_version: str = VTDO_EXPERIMENT_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> TrainingExperimentPreflight:
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
    base_model: str = Field(min_length=1)
    model_revision: str | None = None
    adapter_dir: str = Field(min_length=1)
    completed_steps: int = Field(ge=0)
    final_train_loss: float | None = None
    supervised_token_count: int = Field(ge=1)
    supervised_token_budget: int = Field(ge=1_000)
    token_budget_deviation_rate: float = Field(ge=0)
    train_runtime_seconds: float = Field(ge=0)
    peak_gpu_memory_bytes: int = Field(ge=0)
    dependency_versions: dict[str, str]
    status: Literal["completed"] = "completed"
    schema_version: Literal["vtdo_training_run.v1"] = "vtdo_training_run.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> VTDOTrainingRunResult:
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
    training_preflight_hash: str | None = None
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
