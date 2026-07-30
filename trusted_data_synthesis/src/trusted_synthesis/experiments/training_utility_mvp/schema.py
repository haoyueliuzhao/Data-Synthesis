from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.utility import UtilityCohort
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import (
    AgentActionPlanContract,
    AgentAnswerDecisionContract,
    HostExecutionFeedbackContract,
)

TRAINING_UTILITY_MVP_VERSION = "training_utility_mvp.v5"
TRAINING_UTILITY_AGENT_PROMPT_VERSION = "training_utility_agent_prompt.v6"
SUPPORTED_TRAINING_UTILITY_AGENT_PROMPT_VERSIONS = frozenset(
    {
        "training_utility_agent_prompt.v3",
        "training_utility_agent_prompt.v4",
        "training_utility_agent_prompt.v5",
        TRAINING_UTILITY_AGENT_PROMPT_VERSION,
    }
)
VALIDATION_DOMAINS = ("finance", "legal", "science")


class TrainingUtilityMVPConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    base_model: str = "Qwen/Qwen2.5-7B-Instruct"
    model_revision: str | None = None
    candidate_tasks_per_domain: int = Field(default=10, ge=2, le=2000)
    evaluation_tasks_per_domain: int = Field(default=6, ge=1, le=500)
    candidate_task_targets: dict[str, int] = Field(default_factory=dict)
    evaluation_task_targets: dict[str, int] = Field(default_factory=dict)
    cohort_size: int = Field(default=24, ge=6, le=5000)
    minimum_real_candidate_completion_rate: float = Field(default=0.8, gt=0, le=1)
    d1_construction_mode: Literal[
        "unfiltered_real_agent",
        "legacy_counterfactual_mix",
    ] = "unfiltered_real_agent"
    d1_counterfactual_fraction: float = Field(default=0.5, ge=0, le=1)
    d4_training_format: Literal[
        "clean_solve_feedback",
        "legacy_mixed_repair",
    ] = "clean_solve_feedback"
    d4_repair_fraction: float = Field(default=0.5, ge=0, le=1)
    d5_minimum_overall_score: float = Field(default=0, ge=0, le=1)
    d5_minimum_dimension_score: float = Field(default=0, ge=0, le=1)
    d5_minimum_critic_accept_probability: float = Field(default=0, ge=0, le=1)
    max_seq_length: int = Field(default=8192, ge=512, le=16384)
    max_new_tokens: int = Field(default=1024, ge=64, le=4096)
    max_steps: int = Field(default=32, ge=1, le=10000)
    supervised_token_budget: int | None = Field(default=None, ge=1000)
    maximum_token_budget_deviation_rate: float = Field(default=0.005, ge=0, le=0.05)
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
    seed: int = 20260726
    prompt_version: str = TRAINING_UTILITY_AGENT_PROMPT_VERSION
    student_interaction_protocol: Literal["host_instrumented_joint"] = "host_instrumented_joint"

    @classmethod
    def from_json(cls, path: str | Path) -> TrainingUtilityMVPConfig:
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))

    @model_validator(mode="after")
    def validate_balanced_cohort(self) -> TrainingUtilityMVPConfig:
        if self.prompt_version not in SUPPORTED_TRAINING_UTILITY_AGENT_PROMPT_VERSIONS:
            raise ValueError(f"unsupported training utility prompt: {self.prompt_version}")
        expected_domains = set(VALIDATION_DOMAINS)
        for field_name, targets, upper_bound in (
            ("candidate_task_targets", self.candidate_task_targets, 5000),
            ("evaluation_task_targets", self.evaluation_task_targets, 2000),
        ):
            if targets and set(targets) != expected_domains:
                raise ValueError(f"{field_name} must define finance, legal, and science")
            if any(
                not isinstance(value, int) or value < 1 or value > upper_bound
                for value in targets.values()
            ):
                raise ValueError(f"{field_name} values must be integers from 1 to {upper_bound}")
        if self.cohort_size % 3:
            raise ValueError("cohort_size must be divisible by the three validation domains")
        required_per_domain = self.cohort_size // len(VALIDATION_DOMAINS)
        shortfalls = {
            domain: target
            for domain, target in self.resolved_candidate_task_targets.items()
            if target < required_per_domain
        }
        if shortfalls:
            raise ValueError(
                f"cohort_size exceeds at least one real candidate task pool: {shortfalls}"
            )
        legacy_counts: list[tuple[str, int]] = []
        if self.d1_construction_mode == "legacy_counterfactual_mix":
            d1_negative_count = round(self.cohort_size * self.d1_counterfactual_fraction)
            legacy_counts.extend(
                (
                    ("D1 counterfactual", d1_negative_count),
                    ("D1 direct", self.cohort_size - d1_negative_count),
                )
            )
        if self.d4_training_format == "legacy_mixed_repair":
            d4_repair_count = round(self.cohort_size * self.d4_repair_fraction)
            legacy_counts.extend(
                (
                    ("D4 repair", d4_repair_count),
                    ("D4 direct", self.cohort_size - d4_repair_count),
                )
            )
        for label, count in legacy_counts:
            if count % 3:
                raise ValueError(f"{label} count must be divisible by three")
        return self

    def candidate_task_target(self, domain: str) -> int:
        return self.candidate_task_targets.get(domain, self.candidate_tasks_per_domain)

    def evaluation_task_target(self, domain: str) -> int:
        return self.evaluation_task_targets.get(domain, self.evaluation_tasks_per_domain)

    @property
    def resolved_candidate_task_targets(self) -> dict[str, int]:
        return {domain: self.candidate_task_target(domain) for domain in VALIDATION_DOMAINS}

    @property
    def resolved_evaluation_task_targets(self) -> dict[str, int]:
        return {domain: self.evaluation_task_target(domain) for domain in VALIDATION_DOMAINS}

    @property
    def config_hash(self) -> str:
        return canonical_hash(self, prefix="training_utility_mvp_config:")


class SFTMessage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1)
    supervise: bool = False
    phase: Literal[
        "context",
        "action_plan",
        "host_execution",
        "answer_decision",
    ]


class SFTRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str
    cohort: str = Field(min_length=1)
    task_id: str
    domain: str
    system_prompt: str
    user_prompt: str
    assistant_target: str
    training_format: Literal[
        "legacy_full_response",
        "host_instrumented_joint",
    ] = "legacy_full_response"
    messages: tuple[SFTMessage, ...] = ()
    source_kind: str
    contract_label: str | None = None
    counterfactual_repair: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    prompt_version: str = "training_utility_agent_prompt.legacy_unspecified"
    schema_version: str = "training_utility_sft_record.v4"

    @model_validator(mode="after")
    def validate_training_transcript(self) -> SFTRecord:
        if self.training_format == "legacy_full_response":
            if self.messages:
                raise ValueError("legacy SFT records cannot contain a tool transcript")
            return self
        expected = (
            ("system", "context", False),
            ("user", "context", False),
            ("assistant", "action_plan", True),
            ("tool", "host_execution", False),
            ("assistant", "answer_decision", True),
        )
        observed = tuple((item.role, item.phase, item.supervise) for item in self.messages)
        if observed != expected:
            raise ValueError("host-instrumented SFT records require the fixed five-message loop")
        if self.system_prompt != self.messages[0].content:
            raise ValueError("system_prompt must mirror the transcript system message")
        if self.user_prompt != self.messages[1].content:
            raise ValueError("user_prompt must mirror the transcript user message")
        try:
            combined = json.loads(self.assistant_target)
            action = json.loads(self.messages[2].content)
            host_execution = json.loads(self.messages[3].content)
            answer = json.loads(self.messages[4].content)
        except json.JSONDecodeError as exc:
            raise ValueError("host-instrumented SFT contracts must be valid JSON") from exc
        if combined != {
            "schema_version": "host_instrumented_student_target.v1",
            "action_plan": action,
            "answer_decision": answer,
        }:
            raise ValueError("assistant_target must mirror model-owned transcript turns")
        AgentActionPlanContract.model_validate(action)
        HostExecutionFeedbackContract.model_validate(host_execution)
        AgentAnswerDecisionContract.model_validate(answer)
        return self

    @property
    def record_hash(self) -> str:
        return canonical_hash(self, prefix="training_utility_sft_record:")


class CohortDatasetManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cohort: UtilityCohort
    record_count: int = Field(ge=1)
    domain_counts: dict[str, int]
    source_kind_counts: dict[str, int]
    pattern_counts: dict[str, int] = Field(default_factory=dict)
    program_signature_counts: dict[str, int] = Field(default_factory=dict)
    structural_group_count: int = Field(default=0, ge=0)
    counterfactual_repair_count: int = Field(ge=0)
    record_ids: tuple[str, ...]
    dataset_hash: str


class TrainingUtilityDataManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_id: str
    config_hash: str
    source_agent_run_id: str
    source_agent_model: str
    source_critic_dataset_id: str
    accepted_real_candidate_count: int = Field(ge=0)
    critic_reviewed_accepted_count: int = Field(ge=0)
    critic_model_ids: tuple[str, ...]
    cohorts: tuple[CohortDatasetManifest, ...]
    evaluation_record_count: int = Field(ge=1)
    evaluation_domain_counts: dict[str, int]
    evaluation_pattern_counts: dict[str, int] = Field(default_factory=dict)
    evaluation_program_signature_counts: dict[str, int] = Field(default_factory=dict)
    evaluation_worst_case_95ci_half_width: dict[str, float] = Field(default_factory=dict)
    evaluation_record_ids: tuple[str, ...]
    evaluation_dataset_hash: str
    training_task_ids: tuple[str, ...]
    evaluation_task_ids: tuple[str, ...]
    train_evaluation_overlap_count: int = Field(ge=0)
    train_evaluation_subject_overlap_count: int = Field(default=0, ge=0)
    train_evaluation_evidence_overlap_count: int = Field(default=0, ge=0)
    train_evaluation_evidence_version_overlap_count: int = Field(default=0, ge=0)
    train_evaluation_source_record_overlap_count: int = Field(default=0, ge=0)
    train_evaluation_binding_overlap_count: int = Field(default=0, ge=0)
    train_evaluation_program_signature_overlap_count: int = Field(default=0, ge=0)
    internal_evaluation_isolation_status: str = "passed"
    d5_selection_id: str | None = None
    d5_selection_policy_hash: str | None = None
    d5_selection_status: str | None = None
    evaluation_track: str = "internal_iid_contract"
    external_benchmark_status: str = "not_executed"
    version: str = TRAINING_UTILITY_MVP_VERSION

    @model_validator(mode="after")
    def validate_complete_design(self) -> TrainingUtilityDataManifest:
        if {item.cohort for item in self.cohorts} != set(UtilityCohort):
            raise ValueError("MVP manifest must contain D1 through D5")
        hard_overlaps = {
            "task": self.train_evaluation_overlap_count,
            "subject": self.train_evaluation_subject_overlap_count,
            "evidence": self.train_evaluation_evidence_overlap_count,
            "evidence_version": self.train_evaluation_evidence_version_overlap_count,
            "source_record": self.train_evaluation_source_record_overlap_count,
            "binding": self.train_evaluation_binding_overlap_count,
        }
        observed = {key: value for key, value in hard_overlaps.items() if value}
        if observed:
            raise ValueError(
                f"training and internal evaluation identities must be disjoint: {observed}"
            )
        if self.internal_evaluation_isolation_status != "passed":
            raise ValueError("completed MVP manifests require passed evaluation isolation")
        return self


class TrainingUtilityReadinessReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    config_hash: str
    source_agent_run_id: str
    source_critic_dataset_id: str
    expected_real_candidate_count: int = Field(ge=0)
    observed_real_candidate_count: int = Field(ge=0)
    accepted_real_candidate_count: int = Field(ge=0)
    critic_reviewed_accepted_count: int = Field(ge=0)
    required_per_domain: dict[str, dict[str, int]]
    observed_per_domain: dict[str, dict[str, int]]
    blockers: tuple[str, ...]
    status: Literal["ready", "blocked"]
    readiness_hash: str
    version: str = TRAINING_UTILITY_MVP_VERSION


class CohortTrainingResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cohort: str = Field(min_length=1)
    config_hash: str
    dataset_hash: str
    base_model: str
    model_revision: str | None = None
    adapter_dir: str
    trainable_parameter_count: int = Field(ge=0)
    total_parameter_count: int = Field(ge=0)
    final_train_loss: float | None = None
    train_runtime_seconds: float = Field(ge=0)
    peak_gpu_memory_bytes: int = Field(ge=0)
    completed_steps: int = Field(ge=0)
    supervised_token_count: int | None = Field(default=None, ge=0)
    supervised_token_budget: int | None = Field(default=None, ge=1000)
    token_budget_deviation_rate: float | None = Field(default=None, ge=0)
    micro_batch_count: int | None = Field(default=None, ge=1)
    dependency_versions: dict[str, str]
    status: Literal["completed", "failed"]
    result_hash: str


class CohortTokenBudgetAudit(BaseModel):
    """CPU-only audit of the exact supervised-token schedule used by training."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cohort: str = Field(min_length=1)
    config_hash: str = Field(min_length=1)
    dataset_hash: str = Field(min_length=1)
    record_count: int = Field(ge=1)
    raw_input_token_count: int = Field(ge=1)
    raw_supervised_token_count: int = Field(ge=1)
    minimum_record_tokens: int = Field(ge=1)
    maximum_record_tokens: int = Field(ge=1)
    maximum_target_tokens: int = Field(ge=1)
    truncated_record_count: int = Field(ge=0)
    scheduled_record_count: int = Field(ge=1)
    scheduled_supervised_token_count: int = Field(ge=1)
    supervised_token_budget: int | None = Field(default=None, ge=1000)
    token_budget_deviation_rate: float | None = Field(default=None, ge=0)
    examples_per_optimizer_step: int = Field(ge=1)
    effective_optimizer_steps: int = Field(ge=1)
    maximum_optimizer_steps: int = Field(ge=1)
    training_format_counts: dict[str, int]
    blockers: tuple[str, ...]
    status: Literal["ready", "blocked"]
    audit_hash: str = Field(min_length=1)


class CohortEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cohort: str
    evaluator_version: str = "training_utility_evaluator.legacy_unversioned"
    adapter_dir: str | None = None
    evaluation_track: str = "evidence_given_plan_given"
    evaluation_dataset_hash: str
    sample_count: int = Field(ge=1)
    valid_json_rate: float = Field(ge=0, le=1)
    response_contract_rate: float = Field(ge=0, le=1)
    action_plan_contract_rate: float = Field(default=0, ge=0, le=1)
    answer_decision_contract_rate: float = Field(default=0, ge=0, le=1)
    host_execution_success_rate: float = Field(default=0, ge=0, le=1)
    host_replay_available_rate: float = Field(default=0, ge=0, le=1)
    execution_replay_valid_rate: float = Field(default=0, ge=0, le=1)
    evidence_recall: float = Field(ge=0, le=1)
    evidence_precision: float = Field(ge=0, le=1)
    execution_coverage: float = Field(ge=0, le=1)
    operation_grounding_score: float = Field(ge=0, le=1)
    tool_necessity_score: float = Field(ge=0, le=1)
    operation_exact_rate: float = Field(ge=0, le=1)
    answer_exact_rate: float = Field(ge=0, le=1)
    citation_exact_rate: float = Field(ge=0, le=1)
    verification_exact_rate: float = Field(ge=0, le=1)
    tool_success_rate: float | None = Field(default=None, ge=0, le=1)
    multi_hop_exact_rate: float | None = Field(default=None, ge=0, le=1)
    distractor_robustness_rate: float | None = Field(default=None, ge=0, le=1)
    end_to_end_rate: float = Field(ge=0, le=1)
    mean_latency_ms: float = Field(ge=0)
    generated_token_count: int = Field(ge=0)
    failure_counts: dict[str, int]
    domain_metrics: dict[str, dict[str, float | int | None]]
    prediction_artifact: str
    status: Literal["completed", "failed"]
    result_hash: str


class TrainingUtilityMVPReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    report_id: str
    config_hash: str
    data_manifest_id: str
    base_evaluation: CohortEvaluationResult
    cohort_training: tuple[CohortTrainingResult, ...]
    cohort_evaluations: tuple[CohortEvaluationResult, ...]
    best_cohort_by_end_to_end: str | None = None
    best_end_to_end_rate: float | None = Field(default=None, ge=0, le=1)
    cohort_deltas_vs_base: dict[str, dict[str, float]]
    cohort_ranking: tuple[str, ...]
    completed_cohort_count: int = Field(ge=0)
    status: Literal["completed", "partial", "failed"]
    limitations: tuple[str, ...]
    version: str = TRAINING_UTILITY_MVP_VERSION

    @property
    def report_hash(self) -> str:
        return canonical_hash(self, prefix="training_utility_mvp_report:")
