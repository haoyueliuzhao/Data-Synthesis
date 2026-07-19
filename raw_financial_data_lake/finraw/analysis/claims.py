from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from finraw.analysis.registry import AnalysisPattern, stable_hash
from finraw.analysis.semantic_frames import (
    FORBIDDEN_CLAIM_EXTENSIONS,
    allowed_surface_form_ids,
    build_claim_semantic_frame,
    build_conclusion_semantic_frame,
)

CLAIM_PLANNER_VERSION = "1.4.0"

_CONCLUSION_TEXT = {
    "broadly_positive": "Overall operating trends are positive across the covered evidence.",
    "positive_with_caveat": "Overall growth is positive, but at least one operating signal warrants caution.",
    "mixed_operating_trend": "The operating evidence is mixed rather than uniformly positive or negative.",
    "broadly_negative": "Several operating indicators weakened across the covered period.",
    "high_quality_growth": "The covered signals support a comparatively strong and internally aligned growth profile.",
    "growth_with_cash_caveat": "Growth is evident, but cash-flow evidence limits the strength of the growth-quality conclusion.",
    "mixed_growth_quality": "Growth quality is mixed because positive and constraining signals coexist.",
    "weak_growth_quality": "The balance of covered signals points to weak growth quality.",
    "peer_leader": "The company holds a comparatively strong peer position across the covered dimensions.",
    "peer_strength_with_leverage_caveat": "The company has relative operating strengths, but leverage is an important peer-level caveat.",
    "balanced_peer_position": "The company occupies a mixed or middle peer position across the covered dimensions.",
    "peer_laggard": "The company trails the covered peer set on multiple assessed dimensions.",
}


@dataclass(frozen=True)
class ClaimPlanResult:
    claims: list[dict[str, Any]]
    valid_conclusions: list[dict[str, Any]]
    invalid_conclusions: list[str]
    selected_conclusion_id: str
    conclusion_text: str
    caveats: list[dict[str, Any]]
    analysis_text: str
    rubric: dict[str, Any]


def build_claim_plan(
    pattern: AnalysisPattern,
    signals: list[dict[str, Any]],
    *,
    entity_name: str,
    scope_definition: str | None,
) -> ClaimPlanResult:
    by_spec = {str(row["signal_spec_id"]): row for row in signals}
    subject = "The company"
    if pattern.analysis_pattern_id == "operating_trend_summary_v1":
        base_claims = _operating_claims(by_spec, subject)
        selected = _operating_conclusion(base_claims)
    elif pattern.analysis_pattern_id == "growth_quality_diagnosis_v1":
        base_claims = _growth_quality_claims(by_spec, subject)
        selected = _growth_quality_conclusion(base_claims)
    elif pattern.analysis_pattern_id == "peer_positioning_v1":
        base_claims = _peer_claims(by_spec, subject)
        selected = _peer_conclusion(base_claims)
    else:
        raise ValueError(f"Unsupported analysis pattern: {pattern.analysis_pattern_id}")
    valid = _valid_conclusions(pattern, selected, base_claims)
    conclusion_text = _CONCLUSION_TEXT[selected]
    claims = _attach_synthesis_claim(base_claims, selected, conclusion_text)
    caveats = [
        {
            "caveat_id": "bounded_structured_evidence",
            "sentence": "This assessment is limited to the covered structured financial evidence and does not establish causality or a forecast.",
        }
    ]
    analysis_text = " ".join(
        [claim["sentence"] for claim in claims if claim["claim_role"] != "synthesis"]
        + [conclusion_text, caveats[0]["sentence"]]
    )
    invalid = [
        "unqualified_comprehensive_improvement",
        "unsupported_causal_explanation",
        "future_performance_guarantee",
        "investment_recommendation",
    ]
    rubric = build_rubric(pattern, claims, valid)
    return ClaimPlanResult(
        claims,
        valid,
        invalid,
        selected,
        conclusion_text,
        caveats,
        analysis_text,
        rubric,
    )


def build_rubric(
    pattern: AnalysisPattern,
    claims: list[dict[str, Any]],
    valid_conclusions: list[dict[str, Any]],
) -> dict[str, Any]:
    mandatory = [claim for claim in claims if claim.get("is_required")]
    optional = [claim for claim in claims if claim.get("is_optional")]
    counter = [
        claim["claim_id"] for claim in claims if claim.get("claim_role") == "risk"
    ]
    numeric_slots = {
        slot["slot_id"]: slot
        for claim in claims
        for slot in claim.get("required_numeric_slots") or []
    }
    return {
        "rubric_type": "claim_grounded_analysis",
        "mandatory_claims": mandatory,
        "optional_claims": optional,
        "acceptable_conclusions": valid_conclusions,
        "forbidden_claim_types": list(pattern.forbidden_claim_types),
        "required_counterevidence": counter,
        "numeric_slots": list(numeric_slots.values()),
        "evidence_requirements": {
            "signal_grounding_required": True,
            "fact_trace_required": True,
            "complete_scope_required": pattern.analysis_family == "peer_positioning",
            "claim_graph_relations_required": True,
        },
        "hard_failures": [
            "wrong_entity_or_period",
            "unsupported_numeric_claim",
            "numeric_slot_mismatch",
            "unsupported_causal_claim",
            "claim_semantic_mismatch",
            "conclusion_semantic_mismatch",
            "invalid_conclusion",
            "missing_required_counterevidence",
            "investment_recommendation",
        ],
        "weights": {
            "factual_accuracy": 30,
            "mandatory_claim_coverage": 20,
            "conclusion_consistency": 15,
            "counterevidence_handling": 15,
            "uncertainty_calibration": 10,
            "relevance_and_clarity": 10,
        },
    }


def _operating_claims(
    signals: dict[str, dict[str, Any]], entity_name: str
) -> list[dict[str, Any]]:
    return [
        _growth_claim(
            "revenue_trend", "revenue", signals["revenue_growth_v1"], entity_name
        ),
        _growth_claim(
            "profit_trend", "net income", signals["profit_growth_v1"], entity_name
        ),
        _growth_claim(
            "cash_flow_trend",
            "operating cash flow",
            signals["operating_cash_flow_growth_v1"],
            entity_name,
        ),
    ]


def _growth_quality_claims(
    signals: dict[str, dict[str, Any]], entity_name: str
) -> list[dict[str, Any]]:
    revenue = signals["revenue_growth_v1"]
    profit = signals["profit_growth_v1"]
    cash = signals["operating_cash_flow_growth_v1"]
    divergence = signals["earnings_cash_divergence_v1"]
    margin = signals["margin_change_v1"]
    efficiency = signals["asset_efficiency_change_v1"]
    growth_direction = _combined_direction([revenue, profit])
    return [
        _claim(
            "growth",
            "growth",
            growth_direction,
            [revenue, profit],
            f"{entity_name}'s revenue and profit signals indicate {_direction_phrase(growth_direction)} operating growth over the covered window.",
        ),
        _claim(
            "profitability",
            "profitability",
            margin["direction"],
            [margin],
            f"Its profit-margin signal is {_direction_phrase(margin['direction'])}, which {'supports' if margin['direction'] == 'positive' else 'tempers'} the growth assessment.",
        ),
        _claim(
            "cash_quality",
            "risk"
            if divergence["direction"] == "negative" or cash["direction"] == "negative"
            else "support",
            _combined_direction([cash, divergence]),
            [cash, divergence],
            _cash_quality_sentence(entity_name, cash, divergence),
        ),
        _claim(
            "efficiency",
            "risk" if efficiency["direction"] == "negative" else "support",
            efficiency["direction"],
            [efficiency],
            f"Asset-efficiency evidence is {_direction_phrase(efficiency['direction'])}, adding {'support to' if efficiency['direction'] == 'positive' else 'a constraint on'} the quality of growth.",
        ),
    ]


def _peer_claims(
    signals: dict[str, dict[str, Any]], entity_name: str
) -> list[dict[str, Any]]:
    growth = signals["peer_growth_percentile_v1"]
    margin = signals["peer_margin_percentile_v1"]
    leverage = signals["peer_leverage_percentile_v1"]
    return [
        _claim(
            "relative_growth",
            "support"
            if growth["direction"] == "positive"
            else "risk"
            if growth["direction"] == "negative"
            else "context",
            growth["direction"],
            [growth],
            f"{entity_name}'s revenue-growth position is {_peer_phrase(growth['direction'])} within the complete covered peer set.",
        ),
        _claim(
            "relative_profitability",
            "support"
            if margin["direction"] == "positive"
            else "risk"
            if margin["direction"] == "negative"
            else "context",
            margin["direction"],
            [margin],
            f"Its net-margin position is {_peer_phrase(margin['direction'])} relative to those peers.",
        ),
        _claim(
            "relative_leverage",
            "risk"
            if leverage["direction"] == "negative"
            else "support"
            if leverage["direction"] == "positive"
            else "context",
            leverage["direction"],
            [leverage],
            f"Its leverage position is {_leverage_phrase(leverage['direction'])}, which must be considered alongside growth and profitability.",
        ),
    ]


def _growth_claim(
    claim_role: str, metric_label: str, signal: dict[str, Any], entity_name: str
) -> dict[str, Any]:
    direction = str(signal["direction"])
    return _claim(
        claim_role,
        "support"
        if direction == "positive"
        else "risk"
        if direction == "negative"
        else "context",
        direction,
        [signal],
        f"{entity_name}'s {metric_label} trend is {_direction_phrase(direction)} across the covered annual observations.",
    )


def _claim(
    claim_type: str,
    claim_role: str,
    polarity: str,
    signals: list[dict[str, Any]],
    sentence: str,
    *,
    is_required: bool = True,
    depends_on_claim_ids: list[str] | None = None,
    contradicts_claim_ids: list[str] | None = None,
) -> dict[str, Any]:
    signal_ids = sorted(str(signal["signal_id"]) for signal in signals)
    confidence = min(
        (float(signal.get("confidence") or 0) for signal in signals), default=1.0
    )
    claim_id = f"claim_{stable_hash([claim_type, signal_ids, depends_on_claim_ids or []])[:20]}"
    semantic_frame = build_claim_semantic_frame(claim_type, claim_role, polarity)
    numeric_slots = _numeric_slots(signals)
    allowed_entity_ids = sorted(
        {
            str(entity_id)
            for signal in signals
            for entity_id in signal.get("entity_ids") or []
        }
    )
    allowed_metric_ids = sorted(
        {
            str(metric_id)
            for signal in signals
            for metric_id in signal.get("metric_ids") or []
        }
    )
    allowed_periods = sorted(
        {
            int(year)
            for signal in signals
            for year in (signal.get("period_scope") or {}).get("years", [])
        }
    )
    return {
        "claim_id": claim_id,
        "claim_type": claim_type,
        "claim_role": claim_role,
        "claim_polarity": polarity,
        "support_signal_ids": signal_ids,
        "support_fact_ids": sorted(
            {
                str(fact_id)
                for signal in signals
                for fact_id in signal.get("input_fact_ids") or []
            }
        ),
        "counter_signal_ids": signal_ids if claim_role == "risk" else [],
        "required_numeric_slots": numeric_slots,
        "required_entity_slots": allowed_entity_ids,
        "required_period_slots": allowed_periods,
        "allowed_entity_ids": allowed_entity_ids,
        "allowed_metric_ids": allowed_metric_ids,
        "allowed_periods": allowed_periods,
        "allowed_predicates": [semantic_frame["predicate"]],
        "allowed_numeric_slot_ids": sorted(
            str(slot["slot_id"]) for slot in numeric_slots
        ),
        "forbidden_claim_extensions": list(FORBIDDEN_CLAIM_EXTENSIONS),
        "qualifiers": ["indicates", "suggests", "should be considered"],
        "semantic_contract": _claim_semantic_contract(claim_role, polarity),
        "semantic_frame": semantic_frame,
        "confidence_band": "high" if confidence >= 0.9 else "moderate",
        "is_required": is_required,
        "is_optional": False,
        "is_forbidden": False,
        "depends_on_claim_ids": list(depends_on_claim_ids or []),
        "contradicts_claim_ids": list(contradicts_claim_ids or []),
        "sentence": sentence,
    }


def _attach_synthesis_claim(
    claims: list[dict[str, Any]], conclusion_id: str, sentence: str
) -> list[dict[str, Any]]:
    base_ids = [claim["claim_id"] for claim in claims]
    risk_ids = [claim["claim_id"] for claim in claims if claim["claim_role"] == "risk"]
    synthesis = _claim(
        f"overall_{conclusion_id}",
        "synthesis",
        _conclusion_polarity(conclusion_id),
        [],
        sentence,
        is_required=False,
        depends_on_claim_ids=base_ids,
        contradicts_claim_ids=risk_ids,
    )
    for claim in claims:
        if claim["claim_role"] == "risk":
            claim["contradicts_claim_ids"] = [synthesis["claim_id"]]
    return [*claims, synthesis]


def _numeric_slots(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slots: dict[str, dict[str, Any]] = {}
    for signal in signals:
        signal_id = str(signal.get("signal_id"))
        payload = dict(signal.get("signal_payload") or {})
        for field, raw in payload.items():
            try:
                value = Decimal(str(raw))
            except (InvalidOperation, TypeError, ValueError):
                continue
            unit = _numeric_unit(field, payload)
            display_value = value * Decimal("100") if field == "percentile" else value
            slot_id = f"{signal_id}.{field}"
            slots[slot_id] = {
                "slot_id": slot_id,
                "field": field,
                "value": str(display_value),
                "unit": unit,
                "display_variants": _display_variants(display_value, unit),
                "source_signal_id": signal_id,
                "tolerance": "0.01",
                "is_required": False,
            }
    return list(slots.values())


def _numeric_unit(field: str, payload: dict[str, Any]) -> str:
    if field in {"first_period", "last_period"}:
        return "year"
    if field == "scope_size":
        return "count"
    if field.endswith("_pp"):
        return "percentage_point"
    if field.endswith("_pct") or field in {
        "percentile",
        "target_value",
        "first_ratio_pct",
        "last_ratio_pct",
    }:
        return "percent"
    return str(payload.get("unit") or "number")


def _display_variants(value: Decimal, unit: str) -> list[str]:
    compact = format(value.normalize(), "f")
    if unit == "percent":
        return [f"{compact}%", f"{compact} percent"]
    if unit == "percentage_point":
        return [f"{compact} percentage points", f"{compact} pp"]
    return [compact]


def _claim_semantic_contract(role: str, polarity: str) -> dict[str, Any]:
    expected = "risk" if role == "risk" else polarity
    return {"expected_stance": expected, "forbid_opposite_stance": True}


def _operating_conclusion(claims: list[dict[str, Any]]) -> str:
    positive = sum(c["claim_polarity"] == "positive" for c in claims)
    negative = sum(c["claim_polarity"] == "negative" for c in claims)
    if positive == len(claims):
        return "broadly_positive"
    if positive >= 2 and negative:
        return "positive_with_caveat"
    if negative >= 2:
        return "broadly_negative"
    return "mixed_operating_trend"


def _growth_quality_conclusion(claims: list[dict[str, Any]]) -> str:
    positive = sum(c["claim_polarity"] == "positive" for c in claims)
    risk = sum(c["claim_role"] == "risk" for c in claims)
    cash_risk = any(
        c["claim_type"] == "cash_quality" and c["claim_role"] == "risk" for c in claims
    )
    if positive >= 3 and not risk:
        return "high_quality_growth"
    if positive >= 2 and cash_risk:
        return "growth_with_cash_caveat"
    if risk >= 3:
        return "weak_growth_quality"
    return "mixed_growth_quality"


def _peer_conclusion(claims: list[dict[str, Any]]) -> str:
    positive = sum(c["claim_polarity"] == "positive" for c in claims)
    negative = sum(c["claim_polarity"] == "negative" for c in claims)
    leverage_risk = any(
        c["claim_type"] == "relative_leverage" and c["claim_role"] == "risk"
        for c in claims
    )
    if positive >= 2 and not leverage_risk:
        return "peer_leader"
    if positive >= 2 and leverage_risk:
        return "peer_strength_with_leverage_caveat"
    if negative >= 2:
        return "peer_laggard"
    return "balanced_peer_position"


def _valid_conclusions(
    pattern: AnalysisPattern, selected: str, claims: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    allowed = list(pattern.conclusion_policy["allowed"])
    required = [claim["claim_id"] for claim in claims if claim.get("is_required")]
    valid = []
    for conclusion_id in allowed:
        predicate = _conclusion_predicate(conclusion_id, claims)
        if predicate["passed"]:
            expected_stance = _conclusion_polarity(conclusion_id)
            semantic_frame = build_conclusion_semantic_frame(
                conclusion_id, expected_stance
            )
            valid.append(
                {
                    "conclusion_id": conclusion_id,
                    "required_claim_ids": required,
                    "text": _CONCLUSION_TEXT[conclusion_id],
                    "conditions": predicate["conditions"],
                    "semantic_contract": {"expected_stance": expected_stance},
                    "semantic_frame": semantic_frame,
                    "allowed_surface_form_ids": allowed_surface_form_ids(
                        semantic_frame, kind="conclusion"
                    ),
                }
            )
    if selected not in {row["conclusion_id"] for row in valid}:
        raise ValueError(
            f"Selected conclusion does not satisfy its predicate: {selected}"
        )
    return valid


def _conclusion_predicate(
    conclusion_id: str, claims: list[dict[str, Any]]
) -> dict[str, Any]:
    positive = sum(c["claim_polarity"] == "positive" for c in claims)
    negative = sum(c["claim_polarity"] == "negative" for c in claims)
    neutral = sum(c["claim_polarity"] == "neutral" for c in claims)
    risks = sum(c["claim_role"] == "risk" for c in claims)
    cash_risk = any(
        c["claim_type"] == "cash_quality" and c["claim_role"] == "risk" for c in claims
    )
    leverage_risk = any(
        c["claim_type"] == "relative_leverage" and c["claim_role"] == "risk"
        for c in claims
    )
    rules = {
        "broadly_positive": positive == len(claims) and risks == 0,
        "positive_with_caveat": positive >= 2 and risks >= 1,
        "mixed_operating_trend": (positive >= 1 and negative >= 1) or neutral >= 1,
        "broadly_negative": negative >= 2,
        "high_quality_growth": positive >= 3 and risks == 0,
        "growth_with_cash_caveat": positive >= 2 and cash_risk,
        "mixed_growth_quality": not (
            (positive >= 3 and risks == 0)
            or (positive >= 2 and cash_risk)
            or risks >= 3
        ),
        "weak_growth_quality": risks >= 3,
        "peer_leader": positive >= 2 and not leverage_risk,
        "peer_strength_with_leverage_caveat": positive >= 2 and leverage_risk,
        "balanced_peer_position": (positive < 2 and negative < 2) or neutral >= 1,
        "peer_laggard": negative >= 2,
    }
    return {
        "passed": bool(rules[conclusion_id]),
        "conditions": {
            "positive_claims": positive,
            "negative_claims": negative,
            "neutral_claims": neutral,
            "risk_claims": risks,
            "cash_risk": cash_risk,
            "leverage_risk": leverage_risk,
        },
    }


def _conclusion_polarity(conclusion_id: str) -> str:
    if conclusion_id in {"broadly_positive", "high_quality_growth", "peer_leader"}:
        return "positive"
    if conclusion_id in {"broadly_negative", "weak_growth_quality", "peer_laggard"}:
        return "negative"
    return "mixed"


def _combined_direction(signals: list[dict[str, Any]]) -> str:
    score = sum(
        1
        if signal["direction"] == "positive"
        else -1
        if signal["direction"] == "negative"
        else 0
        for signal in signals
    )
    return "positive" if score > 0 else "negative" if score < 0 else "neutral"


def _cash_quality_sentence(
    entity_name: str, cash: dict[str, Any], divergence: dict[str, Any]
) -> str:
    if divergence["direction"] == "negative":
        return f"{entity_name}'s profit and operating-cash-flow signals diverge, so the apparent growth should be interpreted with a cash-quality caveat."
    if cash["direction"] == "positive" or divergence["direction"] == "positive":
        return (
            "The operating-cash-flow relationship broadly supports the observed "
            f"profit trend for {entity_name}."
        )
    return (
        "Operating cash flow provides mixed evidence and does not clearly confirm "
        f"the observed profit trend for {entity_name}."
    )


def _direction_phrase(direction: str) -> str:
    return {
        "positive": "positive",
        "negative": "negative",
        "neutral": "broadly stable or mixed",
    }[direction]


def _peer_phrase(direction: str) -> str:
    return {
        "positive": "relatively strong",
        "negative": "relatively weak",
        "neutral": "near the middle",
    }[direction]


def _leverage_phrase(direction: str) -> str:
    return {
        "positive": "relatively conservative",
        "negative": "relatively elevated",
        "neutral": "near the peer middle",
    }[direction]
