from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.epistemic import EpistemicStatus
from trusted_synthesis.core.evidence.locator import SourceLocator
from trusted_synthesis.core.evidence.payloads import EvidenceKind, EvidencePayload
from trusted_synthesis.core.evidence.scope import EvidenceScope
from trusted_synthesis.core.evidence.temporal import TemporalContext
from trusted_synthesis.hashing import canonical_hash


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceAuthority(str, Enum):
    PRIMARY = "primary"
    OFFICIAL = "official"
    PEER_REVIEWED = "peer_reviewed"
    CURATED_DATABASE = "curated_database"
    SECONDARY = "secondary"
    UNKNOWN = "unknown"


class SubjectRef(FrozenModel):
    subject_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    subject_type: str = Field(min_length=1)
    attributes: dict[str, Any] = Field(default_factory=dict)


class SourceRef(FrozenModel):
    source_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    authority: SourceAuthority
    provider: str | None = None
    license_note: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class SemanticDefinitionRef(FrozenModel):
    definition_id: str | None = None
    text: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class ProvenanceRef(FrozenModel):
    adapter_id: str = Field(min_length=1)
    archive_id: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    build_ids: dict[str, str] = Field(default_factory=dict)
    content_hash: str | None = None
    extraction_method: str | None = None
    parent_evidence_ids: tuple[str, ...] = ()


class EvidenceItem(FrozenModel):
    evidence_id: str = Field(min_length=1)
    assertion_id: str = Field(min_length=1)
    evidence_version_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    subject: SubjectRef
    predicate: str = Field(min_length=1)
    payload: EvidencePayload
    temporal_context: TemporalContext = Field(default_factory=TemporalContext)
    scope: EvidenceScope | None = None
    source: SourceRef
    source_locator: SourceLocator
    definition: SemanticDefinitionRef = Field(default_factory=SemanticDefinitionRef)
    provenance: ProvenanceRef
    epistemic_status: EpistemicStatus
    extraction_confidence: float = Field(ge=0, le=1)
    domain_context: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_kind(self) -> EvidenceItem:
        if self.payload.kind != self.evidence_kind:
            raise ValueError("evidence_kind must match payload kind")
        return self

    @property
    def semantic_key(self) -> str:
        return canonical_hash(
            {
                "domain": self.domain,
                "subject_id": self.subject.subject_id,
                "predicate": self.predicate,
                "evidence_kind": self.evidence_kind,
                "temporal_context": self.temporal_context.model_dump(
                    mode="json", exclude_none=True
                ),
                "scope": (
                    self.scope.model_dump(mode="json", exclude_none=True) if self.scope else None
                ),
                "definition_id": self.definition.definition_id,
            },
            prefix="evidence_semantic:",
        )


class EvidenceBundle(FrozenModel):
    bundle_id: str = Field(min_length=1)
    evidence: tuple[EvidenceItem, ...] = Field(min_length=1)
    purpose: str = Field(min_length=1)
    graph_build_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> EvidenceBundle:
        identifiers = [item.evidence_id for item in self.evidence]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("evidence bundle contains duplicate evidence IDs")
        return self

    @property
    def bundle_hash(self) -> str:
        return canonical_hash(self, prefix="bundle:")
