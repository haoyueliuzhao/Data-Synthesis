from __future__ import annotations

from trusted_synthesis.core.evaluation.counterfactual import (
    CounterfactualOperatorRegistry,
    ReplaceSelectedEvidenceOperator,
    universal_counterfactual_registry,
)
from trusted_synthesis.core.evidence.schema import EvidenceItem

SCIENCE_COUNTERFACTUAL_PROVIDER_ID = "science_counterfactual_operators.v1"


class _ScienceSelector:
    selector_version = "1.0.0"
    selector_id: str

    @staticmethod
    def _same_outcome(target: EvidenceItem, candidate: EvidenceItem) -> bool:
        return candidate.predicate == target.predicate


class ScienceObservationVersionSelector(_ScienceSelector):
    selector_id = "science_observation_version_swap.v1"

    def __call__(self, target: EvidenceItem, candidate: EvidenceItem) -> bool:
        return self._same_outcome(target, candidate) and (
            candidate.temporal_context.label != target.temporal_context.label
        )


class SciencePopulationSelector(_ScienceSelector):
    selector_id = "science_population_swap.v1"

    def __call__(self, target: EvidenceItem, candidate: EvidenceItem) -> bool:
        target_scope = target.scope.scope_id if target.scope else None
        candidate_scope = candidate.scope.scope_id if candidate.scope else None
        return self._same_outcome(target, candidate) and candidate_scope != target_scope


class ScienceOutcomeDefinitionSelector(_ScienceSelector):
    selector_id = "science_outcome_definition_swap.v1"

    def __call__(self, target: EvidenceItem, candidate: EvidenceItem) -> bool:
        return self._same_outcome(target, candidate) and (
            candidate.definition.definition_id != target.definition.definition_id
        )


def science_counterfactual_registry() -> CounterfactualOperatorRegistry:
    selectors = (
        ("science_replace_observation_version", ScienceObservationVersionSelector()),
        ("science_replace_population", SciencePopulationSelector()),
        ("science_replace_outcome_definition", ScienceOutcomeDefinitionSelector()),
    )
    return universal_counterfactual_registry(
        *(
            ReplaceSelectedEvidenceOperator(
                operator_id=operator_id,
                provider_id=SCIENCE_COUNTERFACTUAL_PROVIDER_ID,
                selector=selector,
            )
            for operator_id, selector in selectors
        )
    )
