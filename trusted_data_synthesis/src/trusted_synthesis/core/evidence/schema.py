from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceAuthority(str, Enum):
    OFFICIAL = "official"
    CURATED_DATABASE = "curated_database"
    SECONDARY_WEB = "secondary_web"


class EvidenceStatus(str, Enum):
    ACCEPTED = "accepted"
    CONFLICT = "conflict"
    CANDIDATE = "candidate"
    REJECTED = "rejected"


class EntityRef(FrozenModel):
    entity_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    market: str | None = None
    country: str | None = None


class PropertyRef(FrozenModel):
    property_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str | None = None
    period_type: str | None = None


class TimeRef(FrozenModel):
    label: str = Field(min_length=1)
    start: date | None = None
    end: date | None = None
    basis: str | None = None
    frequency: str | None = None

    @model_validator(mode="after")
    def validate_range(self) -> TimeRef:
        if self.start and self.end and self.start > self.end:
            raise ValueError("time start must not be after end")
        return self


class SourceRef(FrozenModel):
    source_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    authority: SourceAuthority
    provider: str | None = None
    uri: str | None = None
    license_note: str | None = None


class DefinitionRef(FrozenModel):
    definition_id: str | None = None
    text: str | None = None
    comparability_level: str | None = None
    vintage_policy: str | None = None


class ProvenanceRef(FrozenModel):
    adapter_id: str = Field(min_length=1)
    archive_id: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    raw_object_id: str | None = None
    source_document_id: str | None = None
    build_ids: dict[str, str] = Field(default_factory=dict)
    content_hash: str | None = None
    extraction_method: str | None = None


class EvidenceItem(FrozenModel):
    evidence_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    entity: EntityRef
    property: PropertyRef
    value: Decimal | int | float | str | bool
    unit: str | None = None
    currency: str | None = None
    time: TimeRef
    source: SourceRef
    definition: DefinitionRef = Field(default_factory=DefinitionRef)
    provenance: ProvenanceRef
    status: EvidenceStatus
    confidence: float = Field(ge=0, le=1)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @property
    def semantic_key(self) -> str:
        return canonical_hash(
            {
                "domain": self.domain,
                "entity_id": self.entity.entity_id,
                "property_id": self.property.property_id,
                "time": self.time.model_dump(mode="json"),
                "unit": self.unit,
                "currency": self.currency,
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
