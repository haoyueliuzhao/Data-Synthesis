from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash


class CandidateReleaseSelection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    selection_id: str
    accepted_task_ids: tuple[str, ...]
    accepted_trajectory_ids: tuple[str, ...]
    quality_assessment_ids: tuple[str, ...]
    failure_distribution: dict[str, int]
    domain_task_distribution: dict[str, int]
    split_counts: dict[str, int]


class SplitPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str
    train_share: int = Field(default=80, ge=1, le=98)
    dev_share: int = Field(default=10, ge=1, le=49)
    test_share: int = Field(default=10, ge=1, le=49)
    cluster_fields: tuple[str, ...] = (
        "domain",
        "task_type",
        "subject_ids",
        "predicates",
        "program_semantic_hash",
    )

    @model_validator(mode="after")
    def validate_shares(self) -> SplitPolicy:
        if self.train_share + self.dev_share + self.test_share != 100:
            raise ValueError("split shares must sum to 100")
        return self

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self, prefix="split_policy:")


class ReleaseManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    release_id: str
    framework_version: str
    evidence_schema_version: str
    proof_graph_schema_version: str
    task_program_version: str
    operation_manifest_hash: str
    required_check_manifest_hash: str
    candidate_required_check_manifest_hash: str
    split_policy_hash: str
    adapter_capabilities: dict[str, tuple[str, ...]]
    source_build_ids: dict[str, str]
    sample_counts: dict[str, int]
    accepted_candidate_trajectory_ids: tuple[str, ...] = ()
    quality_assessment_ids: tuple[str, ...] = ()
    failure_distribution: dict[str, int] = Field(default_factory=dict)
    domain_task_distribution: dict[str, int] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def manifest_hash(self) -> str:
        return canonical_hash(self, prefix="release_manifest:")
