from __future__ import annotations

from trusted_synthesis.core.evidence.payloads import ExperimentalResult
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.domains.contracts import (
    ComparabilityDecision,
    DomainValidationReport,
    SemanticSignature,
)


class ScienceSemanticPolicy:
    policy_id = "science_semantics.v1"

    def validate_evidence(self, evidence: EvidenceItem) -> DomainValidationReport:
        payload = evidence.payload
        checks = {
            "science_domain": evidence.domain == "science",
            "experimental_result_payload": isinstance(payload, ExperimentalResult),
            "method_present": bool(isinstance(payload, ExperimentalResult) and payload.method),
            "dataset_present": bool(isinstance(payload, ExperimentalResult) and payload.dataset),
            "uncertainty_present": bool(
                isinstance(payload, ExperimentalResult) and payload.uncertainty
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
            domain="science",
            signature={
                "metric": payload.metric if isinstance(payload, ExperimentalResult) else None,
                "unit": payload.unit if isinstance(payload, ExperimentalResult) else None,
                "dataset": payload.dataset if isinstance(payload, ExperimentalResult) else None,
                "method": payload.method if isinstance(payload, ExperimentalResult) else None,
                "protocol": payload.protocol if isinstance(payload, ExperimentalResult) else None,
                "definition_id": evidence.definition.definition_id,
            },
        )

    def compare(self, left: EvidenceItem, right: EvidenceItem) -> ComparabilityDecision:
        left_report = self.validate_evidence(left)
        right_report = self.validate_evidence(right)
        reasons = []
        if not left_report.passed or not right_report.passed:
            reasons.append("invalid_science_evidence")
        left_signature = self.semantic_signature(left).signature
        right_signature = self.semantic_signature(right).signature
        for field in ("metric", "unit", "dataset", "method", "protocol", "definition_id"):
            if left_signature[field] != right_signature[field]:
                reasons.append(f"{field}_mismatch")
        return ComparabilityDecision(
            comparable=not reasons,
            compatibility_class=(
                f"science:{left_signature['definition_id']}:{left_signature['method']}"
                if not reasons
                else None
            ),
            reasons=tuple(reasons),
        )
