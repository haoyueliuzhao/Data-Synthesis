from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.utility import UtilityCohort
from trusted_synthesis.hashing import canonical_hash

TRAINING_UTILITY_MVP_VERSION = "training_utility_mvp.v2"


class TrainingUtilityMVPConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    base_model: str = "Qwen/Qwen2.5-7B-Instruct"
    model_revision: str | None = None
    candidate_tasks_per_domain: int = Field(default=10, ge=2, le=2000)
    evaluation_tasks_per_domain: int = Field(default=6, ge=1, le=500)
    cohort_size: int = Field(default=24, ge=6, le=5000)
    d1_counterfactual_fraction: float = Field(default=0.5, ge=0, le=1)
    d4_repair_fraction: float = Field(default=0.5, ge=0, le=1)
    max_seq_length: int = Field(default=8192, ge=512, le=16384)
    max_new_tokens: int = Field(default=1024, ge=64, le=4096)
    max_steps: int = Field(default=32, ge=1, le=10000)
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
    prompt_version: str = "training_utility_agent_prompt.v2"

    @classmethod
    def from_json(cls, path: str | Path) -> TrainingUtilityMVPConfig:
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))

    @model_validator(mode="after")
    def validate_balanced_cohort(self) -> TrainingUtilityMVPConfig:
        if self.cohort_size % 3:
            raise ValueError("cohort_size must be divisible by the three validation domains")
        if self.cohort_size > self.candidate_tasks_per_domain * 3:
            raise ValueError("cohort_size exceeds the real candidate task pool")
        d1_negative_count = round(self.cohort_size * self.d1_counterfactual_fraction)
        d4_repair_count = round(self.cohort_size * self.d4_repair_fraction)
        for label, count in (
            ("D1 counterfactual", d1_negative_count),
            ("D1 direct", self.cohort_size - d1_negative_count),
            ("D4 repair", d4_repair_count),
            ("D4 direct", self.cohort_size - d4_repair_count),
        ):
            if count % 3:
                raise ValueError(f"{label} count must be divisible by three")
        return self

    @property
    def config_hash(self) -> str:
        return canonical_hash(self, prefix="training_utility_mvp_config:")


class SFTRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str
    cohort: UtilityCohort | Literal["evaluation"]
    task_id: str
    domain: str
    system_prompt: str
    user_prompt: str
    assistant_target: str
    source_kind: str
    contract_label: str | None = None
    counterfactual_repair: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = "training_utility_sft_record.v2"

    @property
    def record_hash(self) -> str:
        return canonical_hash(self, prefix="training_utility_sft_record:")


class CohortDatasetManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cohort: UtilityCohort
    record_count: int = Field(ge=1)
    domain_counts: dict[str, int]
    source_kind_counts: dict[str, int]
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
    evaluation_record_ids: tuple[str, ...]
    evaluation_dataset_hash: str
    training_task_ids: tuple[str, ...]
    evaluation_task_ids: tuple[str, ...]
    train_evaluation_overlap_count: int = Field(ge=0)
    version: str = TRAINING_UTILITY_MVP_VERSION

    @model_validator(mode="after")
    def validate_complete_design(self) -> TrainingUtilityDataManifest:
        if {item.cohort for item in self.cohorts} != set(UtilityCohort):
            raise ValueError("MVP manifest must contain D1 through D5")
        if self.train_evaluation_overlap_count:
            raise ValueError("training and evaluation task IDs must be disjoint")
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
    required_per_domain: dict[str, int]
    observed_per_domain: dict[str, dict[str, int]]
    blockers: tuple[str, ...]
    status: Literal["ready", "blocked"]
    readiness_hash: str
    version: str = TRAINING_UTILITY_MVP_VERSION


class CohortTrainingResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cohort: UtilityCohort
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
    dependency_versions: dict[str, str]
    status: Literal["completed", "failed"]
    result_hash: str


class CohortEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cohort: str
    adapter_dir: str | None = None
    evaluation_track: str = "evidence_given_plan_given"
    evaluation_dataset_hash: str
    sample_count: int = Field(ge=1)
    valid_json_rate: float = Field(ge=0, le=1)
    response_contract_rate: float = Field(ge=0, le=1)
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
