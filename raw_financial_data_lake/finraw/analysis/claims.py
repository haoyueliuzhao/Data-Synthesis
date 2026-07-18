from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from finraw.analysis.registry import AnalysisPattern, stable_hash

CLAIM_PLANNER_VERSION = "1.0.0"


@dataclass(frozen=True)
class ClaimPlanResult:
    claims: list[dict[str, Any]]
    valid_conclusions: list[dict[str, Any]]
    invalid_conclusions: list[str]
    selected_conclusion_id: str
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
        claims = _operating_claims(by_spec, subject)
        selected = _operating_conclusion(claims)
    elif pattern.analysis_pattern_id == "growth_quality_diagnosis_v1":
        claims = _growth_quality_claims(by_spec, subject)
        selected = _growth_quality_conclusion(claims)
    elif pattern.analysis_pattern_id == "peer_positioning_v1":
        claims = _peer_claims(by_spec, subject)
        selected = _peer_conclusion(claims)
    else:
        raise ValueError(f"Unsupported analysis pattern: {pattern.analysis_pattern_id}")
    valid = _valid_conclusions(pattern, selected, claims)
    caveats = [
        {
            "caveat_id": "bounded_structured_evidence",
            "sentence": (
                "This assessment is limited to the covered structured financial evidence and does not establish causality or a forecast."
            ),
        }
    ]
    conclusion_text = next(
        item["text"] for item in valid if item["conclusion_id"] == selected
    )
    analysis_text = " ".join(
        [claim["sentence"] for claim in claims]
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
    counter = [claim["claim_id"] for claim in claims if claim.get("claim_role") == "risk"]
    numeric_slots = [
        slot
        for claim in claims
        for slot in claim.get("required_numeric_slots") or []
    ]
    return {
        "rubric_type": "claim_grounded_analysis",
        "mandatory_claims": mandatory,
        "optional_claims": optional,
        "acceptable_conclusions": valid_conclusions,
        "forbidden_claim_types": list(pattern.forbidden_claim_types),
        "required_counterevidence": counter,
        "numeric_slots": numeric_slots,
        "evidence_requirements": {
            "signal_grounding_required": True,
            "fact_trace_required": True,
            "complete_scope_required": pattern.analysis_family == "peer_positioning",
        },
        "hard_failures": [
            "wrong_entity_or_period",
            "unsupported_numeric_claim",
            "unsupported_causal_claim",
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
        _growth_claim("revenue_trend", "revenue", signals["revenue_growth_v1"], entity_name),
        _growth_claim("profit_trend", "net income", signals["profit_growth_v1"], entity_name),
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
    claims = [
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
            "risk" if divergence["direction"] == "negative" or cash["direction"] == "negative" else "support",
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
    return claims


def _peer_claims(
    signals: dict[str, dict[str, Any]], entity_name: str
) -> list[dict[str, Any]]:
    growth = signals["peer_growth_percentile_v1"]
    margin = signals["peer_margin_percentile_v1"]
    leverage = signals["peer_leverage_percentile_v1"]
    return [
        _claim(
            "relative_growth",
            "support" if growth["direction"] == "positive" else "risk" if growth["direction"] == "negative" else "context",
            growth["direction"],
            [growth],
            f"{entity_name}'s revenue-growth position is {_peer_phrase(growth['direction'])} within the complete covered peer set.",
        ),
        _claim(
            "relative_profitability",
            "support" if margin["direction"] == "positive" else "risk" if margin["direction"] == "negative" else "context",
            margin["direction"],
            [margin],
            f"Its net-margin position is {_peer_phrase(margin['direction'])} relative to those peers.",
        ),
        _claim(
            "relative_leverage",
            "risk" if leverage["direction"] == "negative" else "support" if leverage["direction"] == "positive" else "context",
            leverage["direction"],
            [leverage],
            f"Its leverage position is {_leverage_phrase(leverage['direction'])}, which must be considered alongside growth and profitability.",
        ),
    ]


def _growth_claim(
    claim_role: str,
    metric_label: str,
    signal: dict[str, Any],
    entity_name: str,
) -> dict[str, Any]:
    direction = str(signal["direction"])
    return _claim(
        claim_role,
        "support" if direction == "positive" else "risk" if direction == "negative" else "context",
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
) -> dict[str, Any]:
    signal_ids = sorted(str(signal["signal_id"]) for signal in signals)
    confidence = min(float(signal.get("confidence") or 0) for signal in signals)
    claim_id = f"claim_{stable_hash([claim_type, signal_ids])[:20]}"
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
        "required_numeric_slots": [],
        "required_entity_slots": [],
        "required_period_slots": [],
        "qualifiers": ["indicates", "suggests", "should be considered"],
        "confidence_band": "high" if confidence >= 0.9 else "moderate",
        "is_required": True,
        "is_optional": False,
        "is_forbidden": False,
        "depends_on_claim_ids": [],
        "contradicts_claim_ids": [],
        "sentence": sentence,
    }


def _operating_conclusion(claims: list[dict[str, Any]]) -> str:
    positive = sum(claim["claim_polarity"] == "positive" for claim in claims)
    negative = sum(claim["claim_polarity"] == "negative" for claim in claims)
    if positive == len(claims):
        return "broadly_positive"
    if positive >= 2 and negative:
        return "positive_with_caveat"
    if negative >= 2:
        return "broadly_negative"
    return "mixed_operating_trend"


def _growth_quality_conclusion(claims: list[dict[str, Any]]) -> str:
    positive = sum(claim["claim_polarity"] == "positive" for claim in claims)
    risk = sum(claim["claim_role"] == "risk" for claim in claims)
    cash_risk = any(claim["claim_type"] == "cash_quality" and claim["claim_role"] == "risk" for claim in claims)
    if positive >= 3 and not risk:
        return "high_quality_growth"
    if positive >= 2 and cash_risk:
        return "growth_with_cash_caveat"
    if risk >= 3:
        return "weak_growth_quality"
    return "mixed_growth_quality"


def _peer_conclusion(claims: list[dict[str, Any]]) -> str:
    positive = sum(claim["claim_polarity"] == "positive" for claim in claims)
    negative = sum(claim["claim_polarity"] == "negative" for claim in claims)
    leverage_risk = any(claim["claim_type"] == "relative_leverage" and claim["claim_role"] == "risk" for claim in claims)
    if positive >= 2 and not leverage_risk:
        return "peer_leader"
    if positive >= 2 and leverage_risk:
        return "peer_strength_with_leverage_caveat"
    if negative >= 2:
        return "peer_laggard"
    return "balanced_peer_position"


def _valid_conclusions(
    pattern: AnalysisPattern,
    selected: str,
    claims: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    allowed = list(pattern.conclusion_policy["allowed"])
    required = [claim["claim_id"] for claim in claims]
    text = {
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
    alternatives = [selected]
    if "mixed_growth_quality" in allowed and selected != "mixed_growth_quality":
        alternatives.append("mixed_growth_quality")
    if "mixed_operating_trend" in allowed and selected != "mixed_operating_trend":
        alternatives.append("mixed_operating_trend")
    if "balanced_peer_position" in allowed and selected != "balanced_peer_position":
        alternatives.append("balanced_peer_position")
    return [
        {
            "conclusion_id": conclusion_id,
            "required_claim_ids": required,
            "text": text[conclusion_id],
        }
        for conclusion_id in alternatives
        if conclusion_id in allowed
    ]


def _combined_direction(signals: list[dict[str, Any]]) -> str:
    score = sum(1 if signal["direction"] == "positive" else -1 if signal["direction"] == "negative" else 0 for signal in signals)
    return "positive" if score > 0 else "negative" if score < 0 else "neutral"


def _cash_quality_sentence(
    entity_name: str,
    cash: dict[str, Any],
    divergence: dict[str, Any],
) -> str:
    if divergence["direction"] == "negative":
        return f"{entity_name}'s profit and operating-cash-flow signals diverge, so the apparent growth should be interpreted with a cash-quality caveat."
    if cash["direction"] == "positive":
        return f"Operating cash flow broadly supports the observed profit trend for {entity_name}."
    return f"Operating cash flow does not provide clear confirmation of the observed profit trend for {entity_name}."


def _direction_phrase(direction: str) -> str:
    return {"positive": "positive", "negative": "negative", "neutral": "broadly stable or mixed"}[direction]


def _peer_phrase(direction: str) -> str:
    return {"positive": "relatively strong", "negative": "relatively weak", "neutral": "near the middle"}[direction]


def _leverage_phrase(direction: str) -> str:
    return {"positive": "relatively conservative", "negative": "relatively elevated", "neutral": "near the peer middle"}[direction]
