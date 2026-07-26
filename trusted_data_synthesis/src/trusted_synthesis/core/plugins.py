from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceItem

if TYPE_CHECKING:
    from trusted_synthesis.core.evaluation.contracts.compiler import (
        QualityClauseCompilationContext,
    )
    from trusted_synthesis.core.evaluation.contracts.schema import QualityClause
    from trusted_synthesis.core.operations.registry import OperationRegistry


class SemanticValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    passed: bool
    checks: dict[str, bool]
    issues: tuple[str, ...] = ()


class SemanticSignature(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    domain: str
    signature: dict[str, Any]


class ComparabilityDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    comparable: bool
    compatibility_class: str | None = None
    reasons: tuple[str, ...] = ()


class ClaimVerification(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_id: str
    passed: bool
    supporting_evidence_ids: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()


class DomainPluginSet(BaseModel):
    """Serializable identity for independently deployable domain capabilities."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    domain: str
    evidence_adapter_id: str
    semantic_policy_id: str | None = None
    task_plugin_ids: tuple[str, ...] = ()
    verification_plugin_ids: tuple[str, ...] = ()
    quality_clause_provider_id: str | None = None
    quality_clause_provider_version: str | None = None
    operation_registry_manifest_hash: str | None = None
    versions: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_quality_provider_identity(self) -> DomainPluginSet:
        if (self.quality_clause_provider_id is None) != (
            self.quality_clause_provider_version is None
        ):
            raise ValueError("quality clause provider ID and version must be frozen together")
        return self

    @property
    def quality_provider_identity(self) -> tuple[str, str] | None:
        if self.quality_clause_provider_id is None:
            return None
        if self.quality_clause_provider_version is None:
            raise ValueError("quality clause provider version is not frozen")
        return self.quality_clause_provider_id, self.quality_clause_provider_version


class EvidenceAdapterProtocol(Protocol):
    adapter_id: str
    domain: str

    def inspect(self) -> dict[str, Any]: ...

    def capability_manifest(self) -> tuple[Any, ...]: ...

    def iter_evidence(self, *, limit: int | None = None) -> Iterator[EvidenceItem]: ...


class SemanticPolicyProtocol(Protocol):
    policy_id: str

    def validate_evidence(self, evidence: EvidenceItem) -> SemanticValidationReport: ...

    def semantic_signature(self, evidence: EvidenceItem) -> SemanticSignature: ...

    def compare(self, left: EvidenceItem, right: EvidenceItem) -> ComparabilityDecision: ...


class ClaimVerifierProtocol(Protocol):
    plugin_id: str

    def verify_claim(
        self,
        claim: dict[str, Any],
        evidence: tuple[EvidenceItem, ...],
        *,
        operation_outputs: dict[str, dict[str, Any]] | None = None,
    ) -> ClaimVerification: ...


class SourceGroundingReportProtocol(Protocol):
    evidence_id: str
    checks: dict[str, bool]
    failures: tuple[str, ...]


class SourceGroundingVerifierProtocol(Protocol):
    verifier_id: str
    verifier_version: str

    def verify(self, evidence: EvidenceItem) -> SourceGroundingReportProtocol: ...


class OperationRegistryProvider(Protocol):
    plugin_id: str

    def operation_registry(self) -> OperationRegistry: ...


class TaskFamilyPluginProtocol(OperationRegistryProvider, Protocol):
    task_family_ids: tuple[str, ...]


class DomainQualityClauseProviderProtocol(Protocol):
    """Compile domain clauses without exposing concrete domain logic to Core."""

    provider_id: str
    provider_version: str

    def compile_evidence_clauses(
        self, context: QualityClauseCompilationContext
    ) -> tuple[QualityClause, ...]: ...

    def compile_program_clauses(
        self, context: QualityClauseCompilationContext
    ) -> tuple[QualityClause, ...]: ...

    def compile_claim_clauses(
        self, context: QualityClauseCompilationContext
    ) -> tuple[QualityClause, ...]: ...

    def compile_selection_clauses(
        self, context: QualityClauseCompilationContext
    ) -> tuple[QualityClause, ...]: ...
