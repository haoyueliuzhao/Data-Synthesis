from __future__ import annotations

from typing import Any

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.domains.contracts import ClaimVerification


class FinanceClaimVerifier:
    """Verify bounded structured claims without inferring causal or forecast content."""

    plugin_id = "finance_claim_verifier.v1"
    _forbidden_types = {
        "causal_claim",
        "future_forecast",
        "investment_recommendation",
    }

    def verify_claim(
        self, claim: dict[str, Any], evidence: tuple[EvidenceItem, ...]
    ) -> ClaimVerification:
        claim_id = str(claim.get("claim_id") or "")
        evidence_by_id = {item.evidence_id: item for item in evidence}
        supporting_ids = tuple(str(item) for item in claim.get("evidence_ids") or ())
        issues = []
        if not claim_id:
            issues.append("claim_id_missing")
        if claim.get("claim_type") in self._forbidden_types:
            issues.append("forbidden_claim_type")
        known_supporting_ids = tuple(
            evidence_id for evidence_id in supporting_ids if evidence_id in evidence_by_id
        )
        if not supporting_ids or len(known_supporting_ids) != len(supporting_ids):
            issues.append("supporting_evidence_invalid")
        predicate = claim.get("predicate")
        if predicate and any(
            evidence_by_id[item].predicate != predicate for item in known_supporting_ids
        ):
            issues.append("claim_predicate_mismatch")
        if any(evidence_by_id[item].domain != "finance" for item in known_supporting_ids):
            issues.append("non_finance_support")
        return ClaimVerification(
            claim_id=claim_id or "invalid_claim",
            passed=not issues,
            supporting_evidence_ids=supporting_ids,
            issues=tuple(issues),
        )
