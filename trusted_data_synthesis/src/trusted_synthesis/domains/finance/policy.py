from __future__ import annotations

from decimal import Decimal

from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.domains.contracts import (
    ComparabilityDecision,
    DomainValidationReport,
    SemanticSignature,
)


class FinanceSemanticPolicy:
    """Executable finance semantics used by synthesis and quality gates."""

    policy_id = "finance_semantics.v2"

    def validate_evidence(self, evidence: EvidenceItem) -> DomainValidationReport:
        payload = evidence.payload
        payload_is_scalar = isinstance(payload, ScalarObservation)
        unit = (
            payload.unit.casefold()
            if isinstance(payload, ScalarObservation) and payload.unit
            else ""
        )
        monetary_unit = any(
            marker in unit for marker in ("usd", "cny", "rmb", "hkd", "eur", "jpy", "gbp")
        )
        checks = {
            "finance_domain": evidence.domain == "finance",
            "scalar_payload": payload_is_scalar,
            "unit_present": bool(isinstance(payload, ScalarObservation) and payload.unit),
            "currency_consistent": bool(
                isinstance(payload, ScalarObservation) and (not monetary_unit or payload.currency)
            ),
            "time_basis_present": bool(evidence.temporal_context.basis),
            "frequency_present": bool(evidence.temporal_context.frequency),
            "scope_present": evidence.scope is not None,
            "definition_present": bool(evidence.definition.definition_id),
            "historical_not_forecast": not bool(evidence.domain_context.get("is_forecast")),
            "metric_unit_compatible": _metric_unit_compatible(evidence),
        }
        issues = tuple(check_id for check_id, passed in checks.items() if not passed)
        return DomainValidationReport(
            evidence_id=evidence.evidence_id,
            passed=not issues,
            checks=checks,
            issues=issues,
        )

    def semantic_signature(self, evidence: EvidenceItem) -> SemanticSignature:
        payload = evidence.payload
        return SemanticSignature(
            domain="finance",
            signature={
                "predicate": evidence.predicate,
                "unit": payload.unit if isinstance(payload, ScalarObservation) else None,
                "currency": payload.currency if isinstance(payload, ScalarObservation) else None,
                "definition_id": evidence.definition.definition_id,
                "time_basis": evidence.temporal_context.basis,
                "frequency": evidence.temporal_context.frequency,
                "scope_type": evidence.scope.scope_type if evidence.scope else None,
                "period_type": evidence.definition.attributes.get("period_type"),
            },
        )

    def compare(self, left: EvidenceItem, right: EvidenceItem) -> ComparabilityDecision:
        left_report = self.validate_evidence(left)
        right_report = self.validate_evidence(right)
        if not left_report.passed or not right_report.passed:
            return ComparabilityDecision(
                comparable=False,
                reasons=("invalid_finance_evidence",),
            )
        left_signature = self.semantic_signature(left).signature
        right_signature = self.semantic_signature(right).signature
        fields = (
            "predicate",
            "unit",
            "currency",
            "definition_id",
            "time_basis",
            "frequency",
            "scope_type",
            "period_type",
        )
        mismatches = tuple(
            field for field in fields if left_signature[field] != right_signature[field]
        )
        return ComparabilityDecision(
            comparable=not mismatches,
            compatibility_class=(
                f"finance:{left_signature['definition_id']}:{left_signature['frequency']}"
                if not mismatches
                else None
            ),
            reasons=mismatches,
        )

    def validate_growth_pair(
        self, earlier: EvidenceItem, later: EvidenceItem
    ) -> ComparabilityDecision:
        comparison = self.compare(earlier, later)
        reasons = list(comparison.reasons)
        if not isinstance(earlier.payload, ScalarObservation):
            reasons.append("non_scalar_growth_base")
        else:
            if Decimal(str(earlier.payload.value)) <= 0:
                reasons.append("non_positive_growth_base")
            unit = str(earlier.payload.unit or "").casefold()
            default_unit = str(earlier.definition.attributes.get("default_unit") or "").casefold()
            if any(
                marker in unit or marker in default_unit
                for marker in ("percent", "%", "basis point", "percentage point")
            ):
                reasons.append("rate_requires_signed_change")
        return ComparabilityDecision(
            comparable=not reasons,
            compatibility_class=comparison.compatibility_class if not reasons else None,
            reasons=tuple(dict.fromkeys(reasons)),
        )

    def validate_registered_comparison_pair(
        self,
        left: EvidenceItem,
        right: EvidenceItem,
        registered_pairs: tuple[tuple[str, str], ...],
    ) -> ComparabilityDecision:
        reasons: list[str] = []
        if not self.validate_evidence(left).passed or not self.validate_evidence(right).passed:
            reasons.append("invalid_finance_evidence")
        pair = (left.predicate, right.predicate)
        if pair not in registered_pairs:
            reasons.append("unregistered_financial_comparison_pair")
        if left.predicate == right.predicate:
            reasons.append("cross_metric_pair_not_distinct")
        if left.subject.subject_id != right.subject.subject_id:
            reasons.append("cross_metric_subject_mismatch")
        if left.temporal_context != right.temporal_context:
            reasons.append("cross_metric_period_mismatch")
        if left.scope != right.scope:
            reasons.append("cross_metric_scope_mismatch")
        if left.source.source_id != right.source.source_id:
            reasons.append("cross_metric_source_mismatch")
        if not left.definition.definition_id or not right.definition.definition_id:
            reasons.append("cross_metric_definition_missing")
        definition_fields = {
            "statement_type": (
                _definition_context(left, "statement_type"),
                _definition_context(right, "statement_type"),
            ),
            "metric_period_type": (
                _definition_context(left, "period_type", "metric_period_type"),
                _definition_context(right, "period_type", "metric_period_type"),
            ),
            "source_definition": (
                _definition_context(left, "comparability_level"),
                _definition_context(right, "comparability_level"),
            ),
        }
        for field, (left_value, right_value) in definition_fields.items():
            if not left_value or not right_value:
                reasons.append(f"cross_metric_{field}_missing")
            elif left_value != right_value:
                reasons.append(f"cross_metric_{field}_mismatch")
        left_context = left.payload.model_dump(
            mode="json", exclude={"value", "precision"}, exclude_none=False
        )
        right_context = right.payload.model_dump(
            mode="json", exclude={"value", "precision"}, exclude_none=False
        )
        if left_context != right_context:
            reasons.append("cross_metric_payload_context_mismatch")
        unique_reasons = tuple(dict.fromkeys(reasons))
        return ComparabilityDecision(
            comparable=not unique_reasons,
            compatibility_class=(
                f"finance_registered_comparison:{left.predicate}/{right.predicate}"
                if not unique_reasons
                else None
            ),
            reasons=unique_reasons,
        )


def _definition_context(evidence: EvidenceItem, *keys: str) -> str:
    for key in keys:
        value = evidence.definition.attributes.get(key)
        if value in (None, ""):
            value = evidence.domain_context.get(key)
        normalized = str(value or "").strip().casefold()
        if normalized:
            return normalized
    return ""


def _metric_unit_compatible(evidence: EvidenceItem) -> bool:
    if not isinstance(evidence.payload, ScalarObservation):
        return True
    expected = str(evidence.definition.attributes.get("default_unit") or "").strip()
    observed = str(evidence.payload.unit or "").strip()
    if not expected or not observed:
        return True
    expected_key = _unit_key(expected)
    observed_key = _unit_key(observed)
    if expected_key == "monetary":
        return any(
            marker in observed_key for marker in ("usd", "cny", "rmb", "hkd", "eur", "jpy", "gbp")
        )
    if expected_key == "per share":
        return "per share" in observed_key
    if "/" in expected:
        return "/" in observed and all(
            token in observed_key for token in expected_key.split("/") if token
        )
    if expected_key in {"%", "percent", "percentage"}:
        return any(marker in observed_key for marker in ("%", "percent"))
    if expected_key in {"million", "thousand", "billion"}:
        return expected_key in observed_key
    if expected_key == "persons":
        return any(marker in observed_key for marker in ("person", "people", "level"))
    if expected_key in {"claims", "count", "number"}:
        return any(marker in observed_key for marker in ("claim", "count", "number"))
    return (
        expected_key == observed_key or expected_key in observed_key or observed_key in expected_key
    )


def _unit_key(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").split())
