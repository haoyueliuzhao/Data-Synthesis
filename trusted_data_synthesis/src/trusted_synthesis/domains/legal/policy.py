from __future__ import annotations

from trusted_synthesis.core.evidence.payloads import RuleStatement
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.domains.contracts import (
    ComparabilityDecision,
    DomainValidationReport,
    SemanticSignature,
)


class LegalSemanticPolicy:
    policy_id = "legal_semantics.v1"

    def validate_evidence(self, evidence: EvidenceItem) -> DomainValidationReport:
        payload = evidence.payload
        checks = {
            "legal_domain": evidence.domain == "legal",
            "rule_payload": isinstance(payload, RuleStatement),
            "authority_present": bool(isinstance(payload, RuleStatement) and payload.authority),
            "effective_time_present": bool(
                evidence.temporal_context.valid_to or evidence.temporal_context.observed_at
            ),
            "definition_present": bool(evidence.definition.definition_id),
        }
        issues = tuple(key for key, passed in checks.items() if not passed)
        return DomainValidationReport(
            evidence_id=evidence.evidence_id,
            passed=not issues,
            checks=checks,
            issues=issues,
        )

    def semantic_signature(self, evidence: EvidenceItem) -> SemanticSignature:
        payload = evidence.payload
        return SemanticSignature(
            domain="legal",
            signature={
                "predicate": evidence.predicate,
                "authority": payload.authority if isinstance(payload, RuleStatement) else None,
                "definition_id": evidence.definition.definition_id,
                "scope_type": evidence.scope.scope_type if evidence.scope else None,
                "effective_to": (
                    evidence.temporal_context.valid_to.isoformat()
                    if evidence.temporal_context.valid_to
                    else None
                ),
            },
        )

    def compare(self, left: EvidenceItem, right: EvidenceItem) -> ComparabilityDecision:
        left_report = self.validate_evidence(left)
        right_report = self.validate_evidence(right)
        reasons = []
        if not left_report.passed or not right_report.passed:
            reasons.append("invalid_legal_evidence")
        if left.predicate != right.predicate:
            reasons.append("different_legal_question")
        left_scope = left.scope.scope_id if left.scope else None
        right_scope = right.scope.scope_id if right.scope else None
        if left_scope != right_scope:
            reasons.append("jurisdiction_scope_mismatch")
        return ComparabilityDecision(
            comparable=not reasons,
            compatibility_class=(f"legal:{left_scope}:{left.predicate}" if not reasons else None),
            reasons=tuple(reasons),
        )
