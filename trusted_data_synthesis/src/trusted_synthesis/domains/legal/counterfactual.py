from __future__ import annotations

from trusted_synthesis.core.evaluation.counterfactual import (
    CounterfactualOperatorRegistry,
    ReplaceSelectedEvidenceOperator,
    universal_counterfactual_registry,
)
from trusted_synthesis.core.evidence.schema import EvidenceItem

LEGAL_COUNTERFACTUAL_PROVIDER_ID = "legal_counterfactual_operators.v1"


class _LegalSelector:
    selector_version = "1.0.0"
    selector_id: str

    @staticmethod
    def _same_rule(target: EvidenceItem, candidate: EvidenceItem) -> bool:
        return (
            candidate.subject.subject_id == target.subject.subject_id
            and candidate.predicate == target.predicate
        )


class LegalEffectiveDateSelector(_LegalSelector):
    selector_id = "legal_effective_date_swap.v1"

    def __call__(self, target: EvidenceItem, candidate: EvidenceItem) -> bool:
        return self._same_rule(target, candidate) and (
            candidate.temporal_context.label != target.temporal_context.label
        )


class LegalJurisdictionSelector(_LegalSelector):
    selector_id = "legal_jurisdiction_swap.v1"

    def __call__(self, target: EvidenceItem, candidate: EvidenceItem) -> bool:
        target_scope = target.scope.scope_id if target.scope else None
        candidate_scope = candidate.scope.scope_id if candidate.scope else None
        return self._same_rule(target, candidate) and candidate_scope != target_scope


class LegalDefinitionSelector(_LegalSelector):
    selector_id = "legal_definition_swap.v1"

    def __call__(self, target: EvidenceItem, candidate: EvidenceItem) -> bool:
        return self._same_rule(target, candidate) and (
            candidate.definition.definition_id != target.definition.definition_id
        )


def legal_counterfactual_registry() -> CounterfactualOperatorRegistry:
    selectors = (
        ("legal_replace_effective_date", LegalEffectiveDateSelector()),
        ("legal_replace_jurisdiction", LegalJurisdictionSelector()),
        ("legal_replace_definition", LegalDefinitionSelector()),
    )
    return universal_counterfactual_registry(
        *(
            ReplaceSelectedEvidenceOperator(
                operator_id=operator_id,
                provider_id=LEGAL_COUNTERFACTUAL_PROVIDER_ID,
                selector=selector,
            )
            for operator_id, selector in selectors
        )
    )
