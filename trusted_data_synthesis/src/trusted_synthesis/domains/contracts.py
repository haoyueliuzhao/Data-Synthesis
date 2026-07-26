from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.task.schema import TaskPackage, TaskPublicSpec


class DomainValidationReport(BaseModel):
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


class DomainEvidenceAdapter(Protocol):
    adapter_id: str
    domain: str

    def inspect(self) -> dict[str, Any]: ...

    def iter_evidence(self, *, limit: int | None = None) -> Iterator[EvidenceItem]: ...


class DomainSemanticPolicy(Protocol):
    policy_id: str

    def validate_evidence(self, evidence: EvidenceItem) -> DomainValidationReport: ...

    def semantic_signature(self, evidence: EvidenceItem) -> SemanticSignature: ...

    def compare(self, left: EvidenceItem, right: EvidenceItem) -> ComparabilityDecision: ...


class DomainTaskPlugin(Protocol):
    plugin_id: str

    def operation_registry(self) -> OperationRegistry: ...

    def propose_tasks(self, evidence: tuple[EvidenceItem, ...]) -> tuple[TaskPackage, ...]: ...

    def render_instruction(self, task: TaskPublicSpec) -> str: ...


class DomainVerificationPlugin(Protocol):
    plugin_id: str

    def verify_claim(
        self, claim: dict[str, Any], evidence: tuple[EvidenceItem, ...]
    ) -> ClaimVerification: ...


class DomainPluginSet(BaseModel):
    """Serializable identity for independently deployable domain capabilities."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    domain: str
    evidence_adapter_id: str
    semantic_policy_id: str | None = None
    task_plugin_ids: tuple[str, ...] = ()
    verification_plugin_ids: tuple[str, ...] = ()
    versions: dict[str, str] = Field(default_factory=dict)
