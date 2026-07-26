from __future__ import annotations

from trusted_synthesis.core.evaluation.counterfactual import (
    CounterfactualOperatorRegistry,
    ReplaceSelectedEvidenceOperator,
    universal_counterfactual_registry,
)
from trusted_synthesis.core.evidence.schema import EvidenceItem

FINANCE_COUNTERFACTUAL_PROVIDER_ID = "finance_counterfactual_operators.v1"


class _FinanceDistractorSelector:
    selector_version = "1.0.0"
    distractor_kind: str

    def __call__(self, target: EvidenceItem, candidate: EvidenceItem) -> bool:
        return (
            candidate.domain_context.get("synthetic_distractor_kind")
            == self.distractor_kind
            and candidate.subject.subject_id == target.subject.subject_id
            and candidate.predicate == target.predicate
        )


class FinanceDefinitionSelector(_FinanceDistractorSelector):
    selector_id = "finance_definition_swap.v1"
    distractor_kind = "wrong_definition"


class FinanceVersionSelector(_FinanceDistractorSelector):
    selector_id = "finance_version_swap.v1"
    distractor_kind = "stale_version"


class FinanceForecastSelector(_FinanceDistractorSelector):
    selector_id = "finance_forecast_swap.v1"
    distractor_kind = "forecast"


class FinanceUnitSelector(_FinanceDistractorSelector):
    selector_id = "finance_unit_swap.v1"
    distractor_kind = "unit_mismatch"


class FinanceCurrencySelector(_FinanceDistractorSelector):
    selector_id = "finance_currency_swap.v1"
    distractor_kind = "currency_mismatch"


class FinanceScopeSelector(_FinanceDistractorSelector):
    selector_id = "finance_scope_swap.v1"
    distractor_kind = "wrong_scope"


def finance_counterfactual_registry() -> CounterfactualOperatorRegistry:
    selectors = (
        ("finance_replace_metric_definition", FinanceDefinitionSelector()),
        ("finance_replace_version", FinanceVersionSelector()),
        ("finance_replace_with_forecast", FinanceForecastSelector()),
        ("finance_replace_unit", FinanceUnitSelector()),
        ("finance_replace_currency", FinanceCurrencySelector()),
        ("finance_replace_scope", FinanceScopeSelector()),
    )
    return universal_counterfactual_registry(
        *(
            ReplaceSelectedEvidenceOperator(
                operator_id=operator_id,
                provider_id=FINANCE_COUNTERFACTUAL_PROVIDER_ID,
                selector=selector,
            )
            for operator_id, selector in selectors
        )
    )
