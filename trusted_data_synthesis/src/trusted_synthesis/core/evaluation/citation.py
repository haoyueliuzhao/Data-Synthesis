from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.hashing import canonical_hash


class CitationVerification(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool
    cited_evidence_ids: tuple[str, ...]
    failures: tuple[str, ...]


class CitationVerifier:
    def verify(
        self,
        citations: Any,
        evidence_by_id: dict[str, EvidenceItem],
        required_evidence_ids: tuple[str, ...],
    ) -> CitationVerification:
        if not isinstance(citations, list):
            return CitationVerification(
                passed=False,
                cited_evidence_ids=(),
                failures=("citations_not_array",),
            )
        failures: list[str] = []
        cited: list[str] = []
        for index, citation in enumerate(citations):
            if not isinstance(citation, dict):
                failures.append(f"citation_{index}_not_object")
                continue
            evidence_id = str(citation.get("evidence_id") or "")
            cited.append(evidence_id)
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                failures.append(f"citation_{index}_unknown_evidence")
                continue
            if citation.get("source_id") != evidence.source.source_id:
                failures.append(f"citation_{index}_source_mismatch")
            observed_locator = citation.get("source_locator")
            expected_locator = evidence.source_locator.model_dump(mode="json", exclude_none=True)
            if canonical_hash(observed_locator) != canonical_hash(expected_locator):
                failures.append(f"citation_{index}_locator_mismatch")
        if set(cited) != set(required_evidence_ids):
            failures.append("citation_evidence_set_mismatch")
        return CitationVerification(
            passed=not failures,
            cited_evidence_ids=tuple(cited),
            failures=tuple(failures),
        )
