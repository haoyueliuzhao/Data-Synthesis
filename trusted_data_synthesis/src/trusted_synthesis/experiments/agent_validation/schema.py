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

AGENT_VALIDATION_VERSION = "agent_validation.v1"


class AgentValidationConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model: AgentModelConfig
    tasks_per_domain: int = Field(default=1, ge=1, le=20)
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
    model_critic_max_examples: int = Field(default=24, ge=1, le=500)
    generate_counterfactuals: bool = True
    selection_target: int = Field(default=10, ge=1)
    training_base_model: str = "Qwen2.5-7B"
    random_seed: int = 20260726

    @model_validator(mode="after")
    def validate_tracks(self) -> AgentValidationConfig:
        if not self.retrieval_tracks or not self.planning_tracks:
            raise ValueError("agent validation requires retrieval and planning tracks")
        if len(set(self.retrieval_tracks)) != len(self.retrieval_tracks):
            raise ValueError("retrieval tracks must be unique")
        if len(set(self.planning_tracks)) != len(self.planning_tracks):
            raise ValueError("planning tracks must be unique")
        return self

    @classmethod
    def from_json(cls, path: str | Path) -> AgentValidationConfig:
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))

    @property
    def config_hash(self) -> str:
        return canonical_hash(self, prefix="agent_validation_config:")


class AgentValidationSample(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_id: str
    task_id: str
    domain: str
    retrieval_track: RetrievalTrack
    planning_track: PlanningTrack
    generation_status: str
    generation_audit: AgentGenerationAudit | None = None
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
    attempted_count: int = Field(ge=0)
    api_success_count: int = Field(ge=0)
    normalized_trajectory_count: int = Field(ge=0)
    contract_evaluated_count: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    quarantined_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    counterfactual_count: int = Field(ge=0)
    counterfactual_rejection_rate: float | None = Field(default=None, ge=0, le=1)
    domain_counts: dict[str, int]
    retrieval_planning_counts: dict[str, int]
    retrieval_planning_acceptance_rates: dict[str, float]
    agent_selected_model_counts: dict[str, int]
    critic_selected_model_counts: dict[str, int]
    critic_attempted_count: int = Field(ge=0)
    critic_success_count: int = Field(ge=0)
    critic_failure_count: int = Field(ge=0)
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
