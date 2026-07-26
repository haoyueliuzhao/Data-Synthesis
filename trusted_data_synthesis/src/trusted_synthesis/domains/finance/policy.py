from __future__ import annotations

from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.domains.contracts import (
    ComparabilityDecision,
    DomainValidationReport,
    SemanticSignature,
)


class FinanceSemanticPolicy:
    """Executable finance semantics used by synthesis and quality gates."""

    policy_id = "finance_semantics.v1"

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
