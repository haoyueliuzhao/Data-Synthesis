from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.contracts.schema import ContractQualityAssessment
from trusted_synthesis.core.evaluation.critic.schema import (
    AlignmentReport,
    QualityCriticPrediction,
)
from trusted_synthesis.core.evaluation.critic.selection import QualitySelectionResult
from trusted_synthesis.core.evaluation.quality_vector import QualityVector
from trusted_synthesis.core.evaluation.utility import TrainingUtilityProtocol
from trusted_synthesis.core.task.schema import PlanningTrack, RetrievalTrack
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import (
    AgentGenerationAudit,
    AgentModelConfig,
    ModelCallTelemetry,
)

AGENT_VALIDATION_VERSION = "agent_validation.v4"
AGENT_CAPACITY_AUDIT_VERSION = "agent_capacity_audit.v2"


class AgentValidationConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model: AgentModelConfig
    tasks_per_domain: int = Field(default=1, ge=1, le=2000)
    domain_task_targets: dict[str, int] = Field(default_factory=dict)
    retrieval_tracks: tuple[RetrievalTrack, ...] = (
        RetrievalTrack.RESOLVED,
        RetrievalTrack.SEMI_OPEN,
        RetrievalTrack.OPEN,
    )
    planning_tracks: tuple[PlanningTrack, ...] = (
        PlanningTrack.PLAN_GIVEN,
        PlanningTrack.PLAN_HIDDEN,
    )
    run_model_critic: bool = False
    model_critic_max_examples: int = Field(default=24, ge=1, le=5000)
    generate_counterfactuals: bool = True
    selection_target: int = Field(default=10, ge=1)
    training_base_model: str = "Qwen2.5-7B"
    random_seed: int = 20260726
    maximum_concurrency: int = Field(default=1, ge=1, le=32)
    checkpoint_enabled: bool = True
    resume_from_checkpoints: bool = True
    retry_failed_checkpoints: bool = False

    @model_validator(mode="after")
    def validate_tracks(self) -> AgentValidationConfig:
        if self.domain_task_targets:
            expected_domains = {"finance", "legal", "science"}
            if set(self.domain_task_targets) != expected_domains:
                raise ValueError("domain_task_targets must define finance, legal, and science")
            if any(
                not isinstance(value, int) or value < 1 or value > 5000
                for value in self.domain_task_targets.values()
            ):
                raise ValueError("domain task targets must be integers from 1 to 5000")
        if not self.retrieval_tracks or not self.planning_tracks:
            raise ValueError("agent validation requires retrieval and planning tracks")
        if len(set(self.retrieval_tracks)) != len(self.retrieval_tracks):
            raise ValueError("retrieval tracks must be unique")
        if len(set(self.planning_tracks)) != len(self.planning_tracks):
            raise ValueError("planning tracks must be unique")
        return self

    def task_target(self, domain: str) -> int:
        return self.domain_task_targets.get(domain, self.tasks_per_domain)

    @property
    def resolved_domain_task_targets(self) -> dict[str, int]:
        return {domain: self.task_target(domain) for domain in ("finance", "legal", "science")}

    @classmethod
    def from_json(cls, path: str | Path) -> AgentValidationConfig:
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))

    @property
    def config_hash(self) -> str:
        return canonical_hash(self, prefix="agent_validation_config:")


class AgentValidationCapacityReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    config_hash: str
    target_task_counts: dict[str, int]
    materialized_task_counts: dict[str, int]
    unique_task_counts: dict[str, int]
    pattern_counts: dict[str, int] = Field(default_factory=dict)
    program_signature_counts: dict[str, int] = Field(default_factory=dict)
    retrieval_track_count: int = Field(ge=1)
    planning_track_count: int = Field(ge=1)
    planned_candidate_count: int = Field(ge=1)
    planned_agent_api_call_floor: int = Field(ge=1)
    planned_critic_api_call_ceiling: int = Field(ge=0)
    fixture_manifest_hash: str
    blockers: tuple[str, ...] = ()
    status: str
    version: str = AGENT_CAPACITY_AUDIT_VERSION


class AgentValidationSample(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_id: str
    task_id: str
    domain: str
    task_type: str = "unknown"
    pattern_id: str = "unknown"
    program_signature: str = "unknown"
    retrieval_track: RetrievalTrack
    planning_track: PlanningTrack
    generation_status: str
    generation_audit: AgentGenerationAudit | None = None
    agent_telemetry: tuple[ModelCallTelemetry, ...] = ()
    trajectory: Trajectory | None = None
    contract_assessment: ContractQualityAssessment | None = None
    quality_vector: QualityVector | None = None
    critic_prediction: QualityCriticPrediction | None = None
    critic_telemetry: tuple[ModelCallTelemetry, ...] = ()
    critic_prompt_manifest_hash: str | None = None
    critic_example_id: str | None = None
    counterfactual_count: int = Field(default=0, ge=0)
    error_type: str | None = None
    error_message: str | None = None


class AgentValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    version: str = AGENT_VALIDATION_VERSION
    config_hash: str
    model_config_hash: str
    requested_model: str
    requested_domain_task_counts: dict[str, int] = Field(default_factory=dict)
    requested_domain_candidate_counts: dict[str, int] = Field(default_factory=dict)
    domain_completion_rates: dict[str, float] = Field(default_factory=dict)
    attempted_count: int = Field(ge=0)
    api_success_count: int = Field(ge=0)
    normalized_trajectory_count: int = Field(ge=0)
    normalized_trajectory_rate: float = Field(default=0, ge=0, le=1)
    contract_evaluated_count: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    contract_acceptance_rate: float = Field(default=0, ge=0, le=1)
    quarantined_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    counterfactual_count: int = Field(ge=0)
    counterfactual_rejection_rate: float | None = Field(default=None, ge=0, le=1)
    domain_counts: dict[str, int]
    task_type_counts: dict[str, int] = Field(default_factory=dict)
    pattern_counts: dict[str, int] = Field(default_factory=dict)
    program_signature_counts: dict[str, int] = Field(default_factory=dict)
    retrieval_planning_counts: dict[str, int]
    retrieval_planning_acceptance_rates: dict[str, float]
    pattern_completion_rates: dict[str, float] = Field(default_factory=dict)
    pattern_acceptance_rates: dict[str, float] = Field(default_factory=dict)
    agent_selected_model_counts: dict[str, int]
    critic_selected_model_counts: dict[str, int]
    critic_attempted_count: int = Field(ge=0)
    critic_success_count: int = Field(ge=0)
    critic_failure_count: int = Field(ge=0)
    maximum_concurrency: int = Field(ge=1)
    agent_checkpoint_loaded_count: int = Field(default=0, ge=0)
    agent_checkpoint_written_count: int = Field(default=0, ge=0)
    critic_checkpoint_loaded_count: int = Field(default=0, ge=0)
    critic_checkpoint_written_count: int = Field(default=0, ge=0)
    agent_failure_type_counts: dict[str, int] = Field(default_factory=dict)
    agent_contract_error_counts: dict[str, int] = Field(default_factory=dict)
    agent_prompt_manifest_hashes: tuple[str, ...]
    critic_prompt_manifest_hashes: tuple[str, ...]
    quality_vector_policy_hashes: tuple[str, ...]
    quality_selection_policy_hash: str
    failure_family_counts: dict[str, int]
    root_location_type_counts: dict[str, int]
    quality_dimension_means: dict[str, float]
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    contract_repair_count: int = Field(ge=0)
    critic_dataset_id: str | None = None
    critic_example_count: int = Field(ge=0)
    alignment_report: AlignmentReport
    quality_selection: QualitySelectionResult | None = None
    training_utility_protocol: TrainingUtilityProtocol
    infrastructure_failures: tuple[str, ...] = ()
    critic_failures: tuple[str, ...] = ()
    status: str
    notes: tuple[str, ...] = ()
    samples: tuple[AgentValidationSample, ...] = ()

    @property
    def report_hash(self) -> str:
        return canonical_hash(self, prefix="agent_validation_report:")
