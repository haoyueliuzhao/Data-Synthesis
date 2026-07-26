from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.domains.contracts import ClaimVerification


class FinanceClaimVerifier:
    """Verify bounded structured claims without inferring causal or forecast content."""

    plugin_id = "finance_claim_verifier.v2"
    _forbidden_types = {
        "causal_claim",
        "future_forecast",
        "investment_recommendation",
    }
    _allowed_types = {"observed_metric", "derived_result", "comparison_result"}
    _allowed_fields = {
        "claim_id",
        "claim_type",
        "predicate",
        "evidence_ids",
        "operation_node_id",
        "subject_ids",
        "period_labels",
        "value",
        "unit",
        "currency",
        "output",
    }

    def verify_claim(
        self,
        claim: dict[str, Any],
        evidence: tuple[EvidenceItem, ...],
        *,
        operation_outputs: dict[str, dict[str, Any]] | None = None,
    ) -> ClaimVerification:
        claim_id = str(claim.get("claim_id") or "")
        evidence_by_id = {item.evidence_id: item for item in evidence}
        supporting_ids = tuple(str(item) for item in claim.get("evidence_ids") or ())
        issues = []
        unexpected = set(claim) - self._allowed_fields
        if unexpected:
            issues.append(f"unexpected_claim_fields:{','.join(sorted(unexpected))}")
        if not claim_id:
            issues.append("claim_id_missing")
        claim_type = str(claim.get("claim_type") or "")
        if claim_type in self._forbidden_types:
            issues.append("forbidden_claim_type")
        elif claim_type not in self._allowed_types:
            issues.append("unknown_claim_type")
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
        supporting = tuple(evidence_by_id[item] for item in known_supporting_ids)
        if claim_type == "observed_metric":
            issues.extend(_verify_observed_claim(claim, supporting))
        elif claim_type in {"derived_result", "comparison_result"}:
            issues.extend(_verify_operation_claim(claim, operation_outputs or {}))
        return ClaimVerification(
            claim_id=claim_id or "invalid_claim",
            passed=not issues,
            supporting_evidence_ids=supporting_ids,
            issues=tuple(issues),
        )


def _verify_observed_claim(
    claim: dict[str, Any], evidence: tuple[EvidenceItem, ...]
) -> tuple[str, ...]:
    if len(evidence) != 1:
        return ("observed_claim_requires_one_evidence",)
    item = evidence[0]
    issues = []
    expected_subjects = [item.subject.subject_id]
    if claim.get("subject_ids") != expected_subjects:
        issues.append("claim_subject_mismatch")
    expected_periods = [_time_label(item)]
    if claim.get("period_labels") != expected_periods:
        issues.append("claim_period_mismatch")
    if claim.get("predicate") != item.predicate:
        issues.append("claim_predicate_mismatch")
    if not isinstance(item.payload, ScalarObservation):
        issues.append("observed_claim_requires_scalar")
        return tuple(issues)
    if not _equivalent(claim.get("value"), item.payload.value):
        issues.append("claim_value_mismatch")
    if claim.get("unit") != item.payload.unit:
        issues.append("claim_unit_mismatch")
    if claim.get("currency") != item.payload.currency:
        issues.append("claim_currency_mismatch")
    return tuple(issues)


def _verify_operation_claim(
    claim: dict[str, Any], operation_outputs: dict[str, dict[str, Any]]
) -> tuple[str, ...]:
    node_id = str(claim.get("operation_node_id") or "")
    if not node_id:
        return ("claim_operation_node_missing",)
    expected = operation_outputs.get(node_id)
    if expected is None:
        return ("claim_operation_node_unknown",)
    observed = claim.get("output")
    if not isinstance(observed, dict):
        return ("claim_output_missing",)
    return () if _equivalent(observed, expected) else ("claim_output_mismatch",)


def _time_label(item: EvidenceItem) -> str:
    context = item.temporal_context
    point = context.valid_to or context.observed_at or context.valid_from
    return context.label or (point.isoformat() if point else "unspecified")


def _equivalent(left: Any, right: Any) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(_equivalent(left[key], right[key]) for key in left)
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(
            _equivalent(a, b) for a, b in zip(left, right, strict=True)
        )
    try:
        return Decimal(str(left)).normalize() == Decimal(str(right)).normalize()
    except (InvalidOperation, TypeError, ValueError):
        return left == right
