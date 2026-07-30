from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.hashing import canonical_hash


class EvidenceCorpus(BaseModel):
    """Versioned evidence search space; it may contain task distractors."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    corpus_id: str = Field(min_length=1)
    evidence: tuple[EvidenceItem, ...] = Field(min_length=1)
    build_id: str | None = None

    @model_validator(mode="after")
    def validate_unique_ids(self) -> EvidenceCorpus:
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence corpus contains duplicate evidence IDs")
        return self

    @classmethod
    def from_bundle(cls, bundle: EvidenceBundle) -> EvidenceCorpus:
        return cls(
            corpus_id=canonical_hash(
                {"bundle_hash": bundle.bundle_hash}, prefix="evidence_corpus:"
            ),
            evidence=bundle.evidence,
            build_id=bundle.graph_build_id,
        )

    def by_id(self) -> dict[str, EvidenceItem]:
        return {item.evidence_id: item for item in self.evidence}

    @property
    def corpus_hash(self) -> str:
        return canonical_hash(self, prefix="evidence_corpus_content:")

    def as_bundle(self, *, purpose: str = "candidate verification") -> EvidenceBundle:
        return EvidenceBundle(
            bundle_id=f"corpus_bundle:{self.corpus_id}",
            evidence=self.evidence,
            purpose=purpose,
            graph_build_id=self.build_id,
        )
