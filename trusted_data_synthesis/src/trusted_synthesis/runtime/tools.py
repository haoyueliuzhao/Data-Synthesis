from __future__ import annotations

from typing import Protocol

from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem


class EvidenceToolRuntime(Protocol):
    def search(self, retrieval_scope: dict[str, object]) -> tuple[EvidenceItem, ...]: ...


class InMemoryEvidenceToolRuntime:
    """Test runtime that implements public-scope retrieval without oracle IDs."""

    def __init__(self, corpus: EvidenceCorpus | EvidenceBundle) -> None:
        self._corpus = (
            corpus if isinstance(corpus, EvidenceCorpus) else EvidenceCorpus.from_bundle(corpus)
        )
        self.last_query: dict[str, object] | None = None

    def search(self, retrieval_scope: dict[str, object]) -> tuple[EvidenceItem, ...]:
        self.last_query = retrieval_scope
        subjects = _string_set(retrieval_scope.get("subject_ids"))
        predicates = _string_set(retrieval_scope.get("predicates"))
        temporal_labels = _string_set(retrieval_scope.get("temporal_labels"))
        return tuple(
            item
            for item in self._corpus.evidence
            if (not subjects or item.subject.subject_id in subjects)
            and (not predicates or item.predicate in predicates)
            and (not temporal_labels or _time_label(item) in temporal_labels)
        )


def _time_label(item: EvidenceItem) -> str:
    context = item.temporal_context
    if context.label:
        return context.label
    if context.valid_to:
        return context.valid_to.isoformat()
    if context.observed_at:
        return context.observed_at.isoformat()
    return "the stated period"


def _string_set(value: object | None) -> set[str]:
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(item) for item in value}
