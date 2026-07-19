from __future__ import annotations

from typing import Any

SEMANTIC_FRAME_VERSION = "1.1.0"
FORBIDDEN_CLAIM_EXTENSIONS = (
    "causal_explanation",
    "management_quality_judgment",
    "future_forecast",
    "investment_recommendation",
    "unregistered_entity",
    "unregistered_metric",
    "unregistered_period",
    "unregistered_numeric_claim",
)

_FRAME_KEYS = {"subject", "predicate", "object", "qualifier"}
_PREDICATES = {"supports", "constrains", "weakens", "is_mixed"}

_SUBJECT_LABELS = {
    "revenue_trend": "Revenue trend evidence",
    "profit_trend": "Profit trend evidence",
    "cash_flow_trend": "Operating-cash-flow trend evidence",
    "growth": "Revenue and profit growth evidence",
    "profitability": "Profit-margin evidence",
    "cash_quality": "Operating-cash-flow and earnings evidence",
    "efficiency": "Asset-efficiency evidence",
    "relative_growth": "Relative growth evidence",
    "relative_profitability": "Relative profitability evidence",
    "relative_leverage": "Relative leverage evidence",
    "overall_assessment": "The combined evidence",
}

_OBJECT_LABELS = {
    "operating_trend": "operating-trend",
    "growth_quality": "growth-quality",
    "peer_position": "peer-positioning",
}

_CONCLUSION_OBJECT_LABELS = {
    "broadly_positive": "operating-trend",
    "positive_with_caveat": "operating-trend",
    "mixed_operating_trend": "operating-trend",
    "broadly_negative": "operating-trend",
    "high_quality_growth": "growth-quality",
    "growth_with_cash_caveat": "growth-quality",
    "mixed_growth_quality": "growth-quality",
    "weak_growth_quality": "growth-quality",
    "peer_leader": "peer-positioning",
    "peer_strength_with_leverage_caveat": "peer-positioning",
    "balanced_peer_position": "peer-positioning",
    "peer_laggard": "peer-positioning",
}

_CLAIM_SURFACES = {
    "supports": {
        "supports_direct": "{subject} supports the {object} assessment.",
        "supports_evidence": "{subject} provides positive support for the {object} assessment.",
    },
    "constrains": {
        "constrains_risk": "{subject} constrains the {object} assessment and should be treated as a risk caveat.",
        "does_not_support_unqualified": "{subject} does not support an unqualified {object} assessment.",
    },
    "weakens": {
        "weakens_direct": "{subject} weakens the {object} assessment.",
        "negative_evidence": "{subject} provides negative evidence for the {object} assessment.",
    },
    "is_mixed": {
        "mixed_evidence": "{subject} provides mixed evidence for the {object} assessment.",
        "does_not_confirm": "{subject} does not clearly confirm either a positive or negative {object} assessment.",
    },
}

_CONCLUSION_SURFACES = {
    "supports": {
        "conclusion_positive": "Overall, the combined evidence supports a positive {object} conclusion.",
        "conclusion_favorable": "Taken together, the evidence supports a favorable {object} assessment.",
    },
    "constrains": {
        "conclusion_risk_caveat": "Overall, the combined evidence requires a risk-qualified {object} conclusion.",
    },
    "weakens": {
        "conclusion_negative": "Overall, the combined evidence supports a negative {object} conclusion.",
        "conclusion_weak": "Taken together, the evidence points to a weak {object} assessment.",
    },
    "is_mixed": {
        "conclusion_mixed": "Overall, the combined evidence supports a mixed {object} conclusion.",
        "conclusion_balanced": "Taken together, positive and constraining evidence produce a balanced {object} assessment.",
    },
}


def build_claim_semantic_frame(
    claim_type: str, claim_role: str, polarity: str
) -> dict[str, str]:
    predicate = (
        "constrains"
        if claim_role == "risk"
        else "supports"
        if polarity == "positive"
        else "weakens"
        if polarity == "negative"
        else "is_mixed"
    )
    qualifier = {
        "supports": "positive_support",
        "constrains": "risk_caveat",
        "weakens": "negative_evidence",
        "is_mixed": "mixed_context",
    }[predicate]
    return {
        "subject": claim_type,
        "predicate": predicate,
        "object": _claim_object(claim_type),
        "qualifier": qualifier,
    }


def build_conclusion_semantic_frame(
    conclusion_id: str, expected_stance: str
) -> dict[str, str]:
    predicate = (
        "supports"
        if expected_stance == "positive"
        else "weakens"
        if expected_stance == "negative"
        else "is_mixed"
    )
    return {
        "subject": "overall_assessment",
        "predicate": predicate,
        "object": conclusion_id,
        "qualifier": "bounded_conclusion",
    }


def allowed_surface_form_ids(frame: dict[str, Any], *, kind: str) -> list[str]:
    predicate = str(frame.get("predicate") or "")
    registry = _CLAIM_SURFACES if kind == "claim" else _CONCLUSION_SURFACES
    return sorted(registry.get(predicate, {}))


def default_surface_form_id(frame: dict[str, Any], *, kind: str) -> str:
    values = allowed_surface_form_ids(frame, kind=kind)
    if not values:
        raise ValueError(
            f"No surface forms for {kind} predicate: {frame.get('predicate')}"
        )
    return values[0]


def render_semantic_frame(
    frame: dict[str, Any], surface_form_id: str, *, kind: str
) -> str:
    errors = validate_semantic_frame(frame, frame, kind=kind)
    if errors:
        raise ValueError("Invalid semantic frame: " + ",".join(errors))
    predicate = str(frame["predicate"])
    registry = _CLAIM_SURFACES if kind == "claim" else _CONCLUSION_SURFACES
    template = registry.get(predicate, {}).get(surface_form_id)
    if template is None:
        raise ValueError(f"Unknown {kind} surface form: {surface_form_id}")
    subject = _SUBJECT_LABELS.get(
        str(frame["subject"]), str(frame["subject"]).replace("_", " ").title()
    )
    object_label = _object_label(str(frame["object"]), kind=kind)
    return template.format(subject=subject, object=object_label)


def validate_semantic_frame(
    observed: Any, expected: dict[str, Any], *, kind: str
) -> list[str]:
    errors: list[str] = []
    if not isinstance(observed, dict):
        return ["semantic_frame_not_object"]
    if set(observed) != _FRAME_KEYS:
        errors.append("semantic_frame_keys_mismatch")
    normalized = {key: str(observed.get(key) or "") for key in _FRAME_KEYS}
    expected_normalized = {key: str(expected.get(key) or "") for key in _FRAME_KEYS}
    if normalized != expected_normalized:
        errors.append("semantic_frame_value_mismatch")
    if normalized["predicate"] not in _PREDICATES:
        errors.append("semantic_frame_predicate_unknown")
    if not allowed_surface_form_ids(normalized, kind=kind):
        errors.append("semantic_frame_surface_registry_missing")
    return errors


def semantic_frame_manifest() -> dict[str, Any]:
    return {
        "version": SEMANTIC_FRAME_VERSION,
        "claim_surfaces": _CLAIM_SURFACES,
        "conclusion_surfaces": _CONCLUSION_SURFACES,
        "subject_labels": _SUBJECT_LABELS,
        "object_labels": _OBJECT_LABELS,
        "conclusion_object_labels": _CONCLUSION_OBJECT_LABELS,
        "forbidden_claim_extensions": FORBIDDEN_CLAIM_EXTENSIONS,
    }


def _claim_object(claim_type: str) -> str:
    if claim_type in {"revenue_trend", "profit_trend", "cash_flow_trend"}:
        return "operating_trend"
    if claim_type in {"growth", "profitability", "cash_quality", "efficiency"}:
        return "growth_quality"
    if claim_type in {
        "relative_growth",
        "relative_profitability",
        "relative_leverage",
    }:
        return "peer_position"
    if claim_type.startswith("overall_"):
        return claim_type.removeprefix("overall_")
    raise ValueError(f"Unknown claim type for semantic frame: {claim_type}")


def _object_label(value: str, *, kind: str) -> str:
    if kind == "claim":
        return _OBJECT_LABELS.get(value, value.replace("_", "-"))
    return _CONCLUSION_OBJECT_LABELS.get(value, value.replace("_", "-"))
