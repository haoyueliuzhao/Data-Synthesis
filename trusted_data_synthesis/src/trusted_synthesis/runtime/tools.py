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
        aliases = _string_set(retrieval_scope.get("aliases"))
        authorities = _string_set(retrieval_scope.get("source_authorities"))
        semantic = _mapping(retrieval_scope.get("semantic_constraints"))
        partial = _mapping(retrieval_scope.get("partial_constraints"))
        definitions = _string_set(semantic.get("definition_ids"))
        scopes = _string_set(semantic.get("scope_ids"))
        semantic_times = _string_set(semantic.get("temporal_labels"))
        semantic_authorities = _string_set(semantic.get("source_authorities"))
        semantic_subject_types = _string_set(semantic.get("subject_types"))
        semantic_time_bases = _string_set(semantic.get("time_bases"))
        semantic_frequencies = _string_set(semantic.get("frequencies"))
        semantic_epistemic_statuses = _string_set(semantic.get("epistemic_statuses"))
        apply_semantic_filters = retrieval_scope.get("apply_semantic_filters") is True
        partial_predicate = _optional_string(partial.get("predicate"))
        partial_definition = _optional_string(partial.get("definition_id"))
        return tuple(
            item
            for item in self._corpus.evidence
            if (not subjects or item.subject.subject_id in subjects)
            and (not predicates or item.predicate in predicates)
            and (not temporal_labels or bool(_time_labels(item) & temporal_labels))
            and (not aliases or item.subject.subject_id in aliases or item.subject.name in aliases)
            and (not authorities or item.source.authority.value in authorities)
            and (
                not apply_semantic_filters
                or not definitions
                or item.definition.definition_id in definitions
            )
            and (
                not apply_semantic_filters
                or not scopes
                or item.scope is not None
                and item.scope.scope_id in scopes
            )
            and (
                not apply_semantic_filters
                or not semantic_times
                or bool(_time_labels(item) & semantic_times)
            )
            and (
                not apply_semantic_filters
                or not semantic_authorities
                or item.source.authority.value in semantic_authorities
            )
            and (
                not apply_semantic_filters
                or not semantic_subject_types
                or item.subject.subject_type in semantic_subject_types
            )
            and (
                not apply_semantic_filters
                or not semantic_time_bases
                or item.temporal_context.basis in semantic_time_bases
            )
            and (
                not apply_semantic_filters
                or not semantic_frequencies
                or item.temporal_context.frequency in semantic_frequencies
            )
            and (
                not apply_semantic_filters
                or not semantic_epistemic_statuses
                or item.epistemic_status.value in semantic_epistemic_statuses
            )
            and (partial_predicate is None or item.predicate == partial_predicate)
            and (partial_definition is None or item.definition.definition_id == partial_definition)
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


def _time_labels(item: EvidenceItem) -> set[str]:
    context = item.temporal_context
    labels = {context.label} if context.label else set()
    labels.update(
        value.isoformat()
        for value in (
            context.valid_from,
            context.valid_to,
            context.observed_at,
        )
        if value is not None
    )
    if not labels:
        labels.add("the stated period")
    return labels


def _string_set(value: object | None) -> set[str]:
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(item) for item in value}


def _mapping(value: object | None) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _optional_string(value: object | None) -> str | None:
    return None if value in (None, "") else str(value)
