from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.plugins import DomainPluginSet
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


class CrossDomainContractSuiteResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    suite_id: str
    suite_version: str
    fixture_manifest_hash: str
    domains: tuple[str, ...]
    task_count: int = Field(ge=0)
    clean_candidate_count: int = Field(ge=0)
    mutation_count: int = Field(ge=0)
    reference_pass_rate: float = Field(ge=0, le=1)
    clean_candidate_pass_rate: float = Field(ge=0, le=1)
    mutation_rejection_rate: float = Field(ge=0, le=1)
    quality_contract_count: int = Field(default=0, ge=0)
    proof_certificate_count: int = Field(default=0, ge=0)
    contract_evaluation_count: int = Field(default=0, ge=0)
    contract_decision_parity_rate: float = Field(default=0, ge=0, le=1)
    quality_contract_hashes: tuple[str, ...] = ()
    proof_certificate_hashes: tuple[str, ...] = ()
    quality_contract_compiler_versions: tuple[str, ...] = ()
    proof_compiler_versions: tuple[str, ...] = ()
    clause_verifier_manifest_hashes: tuple[str, ...] = ()
    status: str
    failure_details: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return (
            self.status == "passed"
            and not self.failure_details
            and self.task_count > 0
            and self.clean_candidate_count > 0
            and self.mutation_count > 0
            and self.quality_contract_count == self.task_count
            and self.proof_certificate_count == self.task_count
            and self.contract_evaluation_count
            == self.clean_candidate_count + self.mutation_count
            and self.reference_pass_rate == 1
            and self.clean_candidate_pass_rate == 1
            and self.mutation_rejection_rate == 1
            and self.contract_decision_parity_rate == 1
            and len(self.quality_contract_hashes) == self.quality_contract_count
            and len(self.proof_certificate_hashes) == self.proof_certificate_count
            and bool(self.quality_contract_compiler_versions)
            and bool(self.proof_compiler_versions)
            and bool(self.clause_verifier_manifest_hashes)
        )

    @property
    def result_hash(self) -> str:
        return canonical_hash(self, prefix="cross_domain_contract_suite:")


class ReleaseManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    release_id: str
    framework_version: str
    evidence_schema_version: str
    proof_graph_schema_version: str
    task_program_version: str
    task_pattern_schema_versions: tuple[str, ...]
    task_pattern_compiler_versions: tuple[str, ...]
    task_pattern_runtimes: dict[str, str]
    task_pattern_quality_profile_ids: tuple[str, ...]
    task_pattern_hashes: tuple[str, ...]
    evidence_binding_schema_versions: tuple[str, ...]
    evidence_binding_hashes: tuple[str, ...]
    task_difficulty_policy_versions: tuple[str, ...]
    operation_manifest_hash: str
    required_check_manifest_hash: str
    candidate_required_check_manifest_hash: str
    quality_contract_compiler_versions: tuple[str, ...]
    quality_contract_runtime_version: str
    clause_verifier_manifest_hashes: tuple[str, ...]
    quality_contract_hashes: tuple[str, ...]
    proof_compiler_versions: tuple[str, ...]
    proof_certificate_hashes: tuple[str, ...]
    mutation_taxonomy_manifest_hash: str
    split_policy_hash: str
    domain_plugin_sets: tuple[DomainPluginSet, ...]
    source_grounding_verifiers: dict[str, str]
    cross_domain_contract_suite: CrossDomainContractSuiteResult
    cross_domain_contract_suite_hash: str
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
