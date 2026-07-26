from __future__ import annotations

from typing import Any

from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.hashing import canonical_hash


def time_label(evidence: EvidenceItem) -> str:
    context = evidence.temporal_context
    if context.label:
        return context.label
    if context.valid_to:
        return context.valid_to.isoformat()
    if context.observed_at:
        return context.observed_at.isoformat()
    return "the stated period"


def time_phrase(evidence: EvidenceItem) -> str:
    label = time_label(evidence)
    return "" if label == "the stated period" else f" for {label}"


def temporal_sort_key(evidence: EvidenceItem):
    context = evidence.temporal_context
    return context.valid_to or context.observed_at or context.valid_from


def payload_context(evidence: EvidenceItem) -> dict[str, Any]:
    payload = evidence.payload.model_dump(mode="json", exclude_none=True)
    return {
        key: value for key, value in payload.items() if key not in {"kind", "value", "precision"}
    }


def scalar_answer_schema(evidence: EvidenceItem, answer_type: str) -> dict[str, Any]:
    if not isinstance(evidence.payload, ScalarObservation):
        raise ValueError(f"task requires scalar evidence: {evidence.evidence_id}")
    return {"type": answer_type, "result_context": payload_context(evidence)}


def resolved_retrieval_scope(evidence: tuple[EvidenceItem, ...]) -> dict[str, Any]:
    return {
        "subject_ids": sorted({item.subject.subject_id for item in evidence}),
        "predicates": sorted({item.predicate for item in evidence}),
        "temporal_labels": sorted({time_label(item) for item in evidence}),
        "semantic_constraints": public_semantic_constraints(evidence),
    }


def public_semantic_constraints(evidence: tuple[EvidenceItem, ...]) -> dict[str, Any]:
    contexts = {
        canonical_hash(payload_context(item), prefix="public_payload_context:"): payload_context(
            item
        )
        for item in evidence
    }
    return {
        "definition_ids": sorted(
            {item.definition.definition_id for item in evidence if item.definition.definition_id}
        ),
        "source_authorities": sorted({item.source.authority.value for item in evidence}),
        "payload_contexts": [contexts[key] for key in sorted(contexts)],
        "epistemic_statuses": sorted({item.epistemic_status.value for item in evidence}),
        "historical_only": all(not item.domain_context.get("is_forecast") for item in evidence),
        "time_bases": sorted(
            {item.temporal_context.basis for item in evidence if item.temporal_context.basis}
        ),
        "frequencies": sorted(
            {
                item.temporal_context.frequency
                for item in evidence
                if item.temporal_context.frequency
            }
        ),
        "scope_types": sorted(
            {item.scope.scope_type for item in evidence if item.scope is not None}
        ),
        "scope_ids": sorted(
            {
                item.scope.scope_id
                for item in evidence
                if item.scope is not None and item.scope.scope_id
            }
        ),
    }


def oracle_selection_contract(evidence: tuple[EvidenceItem, ...]) -> dict[str, Any]:
    return {
        "evidence_version_ids": sorted({item.evidence_version_id for item in evidence}),
        "source_ids": sorted({item.source.source_id for item in evidence}),
        "payload_context_hashes": sorted(
            {canonical_hash(payload_context(item), prefix="payload_context:") for item in evidence}
        ),
        "domain_context_hashes": sorted(
            {canonical_hash(item.domain_context, prefix="domain_context:") for item in evidence}
        ),
        "required_build_ids": {
            key: sorted(
                {
                    value
                    for item in evidence
                    if (value := item.provenance.build_ids.get(key)) is not None
                }
            )
            for key in sorted({key for item in evidence for key in item.provenance.build_ids})
        },
    }

