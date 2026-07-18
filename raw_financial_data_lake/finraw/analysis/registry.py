from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

SIGNAL_REGISTRY_VERSION = "1.0.0"
ANALYSIS_PATTERN_REGISTRY_VERSION = "1.0.0"
CLAIM_SCHEMA_VERSION = "1.0.0"
CONCLUSION_POLICY_VERSION = "1.0.0"


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FinancialSignalSpec:
    signal_spec_id: str
    signal_type: str
    signal_version: int
    signal_category: str
    input_roles: dict[str, str]
    required_metrics: tuple[str, ...]
    required_periods: int
    required_scope: dict[str, Any]
    semantic_constraints: tuple[dict[str, Any], ...]
    operator_dag: tuple[dict[str, Any], ...]
    output_schema: dict[str, Any]
    direction_policy: dict[str, Any]
    strength_policy: dict[str, Any]
    caveat_policy: dict[str, Any]

    def row(self) -> dict[str, Any]:
        payload = asdict(self)
        return {**payload, "signal_hash": stable_hash(payload), "is_active": True}


@dataclass(frozen=True)
class AnalysisPattern:
    analysis_pattern_id: str
    pattern_version: int
    analysis_family: str
    question_intents: tuple[str, ...]
    required_signal_roles: tuple[str, ...]
    optional_signal_roles: tuple[str, ...]
    counter_signal_roles: tuple[str, ...]
    evidence_constraints: tuple[dict[str, Any], ...]
    claim_schema: dict[str, Any]
    conclusion_policy: dict[str, Any]
    forbidden_claim_types: tuple[str, ...]
    difficulty_base: str
    instruction_template: str

    def row(self) -> dict[str, Any]:
        payload = asdict(self)
        return {
            "pattern_key": f"{self.analysis_pattern_id}@{self.pattern_version}",
            **payload,
            "pattern_hash": stable_hash(payload),
            "is_active": True,
        }


_CASH_FLOW = "net_cash_provided_by_used_in_operating_activities"


def _growth_spec(spec_id: str, metric_id: str, category: str) -> FinancialSignalSpec:
    return FinancialSignalSpec(
        spec_id,
        "period_growth",
        1,
        category,
        {"series": metric_id},
        (metric_id,),
        3,
        {"scope_type": "canonical_consolidated_entity"},
        (
            {"field": "periods", "operator": "contiguous"},
            {"field": "source_definition", "operator": "same_within_series"},
            {"field": "is_forecast", "operator": "eq", "value": False},
        ),
        ({"step_id": "growth", "operator": "first_last_growth", "input": "series"},),
        {"type": "growth_signal", "fields": ["first_value", "last_value", "growth_pct"]},
        {"positive_gt": 5, "negative_lt": -5},
        {"moderate_abs": 5, "strong_abs": 15},
        {"forbidden_inference": ["causal_claim", "future_forecast"]},
    )


SIGNAL_SPECS = (
    _growth_spec("revenue_growth_v1", "revenue", "growth"),
    _growth_spec("profit_growth_v1", "net_income", "profitability"),
    _growth_spec("operating_cash_flow_growth_v1", _CASH_FLOW, "cash_flow_quality"),
    FinancialSignalSpec(
        "trend_consistency_v1", "trend_consistency", 1, "trend", {"series": "dynamic"}, (), 3,
        {"scope_type": "canonical_consolidated_entity"},
        ({"field": "periods", "operator": "contiguous"},),
        ({"step_id": "trend", "operator": "direction_consistency", "input": "series"},),
        {"type": "trend_signal", "fields": ["increase_count", "decrease_count", "consistency"]},
        {"positive_consistency": 1.0, "negative_consistency": -1.0},
        {"strong_abs": 1.0, "moderate_abs": 0.5}, {},
    ),
    FinancialSignalSpec(
        "earnings_cash_divergence_v1", "earnings_cash_divergence", 1, "earnings_quality",
        {"profit_series": "net_income", "cash_series": _CASH_FLOW},
        ("net_income", _CASH_FLOW), 3, {"scope_type": "canonical_consolidated_entity"},
        ({"field": "periods", "operator": "exact_coverage"},),
        ({"step_id": "spread", "operator": "growth_spread", "inputs": ["profit_series", "cash_series"]},),
        {"type": "divergence_signal", "fields": ["profit_growth_pct", "cash_growth_pct", "spread_pct"]},
        {"negative_spread_gt": 10, "positive_spread_lt": -10},
        {"moderate_abs": 10, "strong_abs": 25},
        {"required_qualifiers": ["suggests", "may indicate", "should be interpreted cautiously"]},
    ),
    FinancialSignalSpec(
        "margin_change_v1", "margin_change", 1, "profitability",
        {"profit_series": "net_income", "revenue_series": "revenue"},
        ("net_income", "revenue"), 3, {"scope_type": "canonical_consolidated_entity"},
        ({"field": "periods", "operator": "exact_coverage"},),
        ({"step_id": "margin", "operator": "ratio_change", "inputs": ["profit_series", "revenue_series"]},),
        {"type": "ratio_change_signal", "fields": ["first_ratio_pct", "last_ratio_pct", "change_pp"]},
        {"positive_gt": 1, "negative_lt": -1}, {"moderate_abs": 1, "strong_abs": 3}, {},
    ),
    FinancialSignalSpec(
        "asset_efficiency_change_v1", "asset_efficiency_change", 1, "growth_quality",
        {"revenue_series": "revenue", "asset_series": "total_assets"},
        ("revenue", "total_assets"), 3, {"scope_type": "canonical_consolidated_entity"},
        ({"field": "periods", "operator": "exact_coverage"},),
        ({"step_id": "efficiency", "operator": "ratio_change", "inputs": ["revenue_series", "asset_series"]},),
        {"type": "ratio_change_signal", "fields": ["first_ratio_pct", "last_ratio_pct", "change_pp"]},
        {"positive_gt": 1, "negative_lt": -1}, {"moderate_abs": 1, "strong_abs": 5}, {},
    ),
    FinancialSignalSpec(
        "peer_growth_percentile_v1", "peer_percentile", 1, "peer_growth",
        {"current": "revenue", "previous": "revenue"}, ("revenue",), 2,
        {"scope_type": "complete_industry_entity_set"},
        ({"field": "scope_input_coverage", "operator": "eq", "value": 1.0},),
        ({"step_id": "percentile", "operator": "peer_growth_percentile"},),
        {"type": "peer_position_signal", "fields": ["target_value", "percentile", "scope_size"]},
        {"positive_gte": 0.67, "negative_lte": 0.33}, {"strong_tail": 0.2, "moderate_tail": 0.33}, {},
    ),
    FinancialSignalSpec(
        "peer_margin_percentile_v1", "peer_percentile", 1, "peer_profitability",
        {"profit": "net_income", "revenue": "revenue"}, ("net_income", "revenue"), 1,
        {"scope_type": "complete_industry_entity_set"},
        ({"field": "scope_input_coverage", "operator": "eq", "value": 1.0},),
        ({"step_id": "percentile", "operator": "peer_ratio_percentile"},),
        {"type": "peer_position_signal", "fields": ["target_value", "percentile", "scope_size"]},
        {"positive_gte": 0.67, "negative_lte": 0.33}, {"strong_tail": 0.2, "moderate_tail": 0.33}, {},
    ),
    FinancialSignalSpec(
        "peer_leverage_percentile_v1", "peer_percentile", 1, "peer_leverage",
        {"liabilities": "total_liabilities", "assets": "total_assets"},
        ("total_liabilities", "total_assets"), 1,
        {"scope_type": "complete_industry_entity_set"},
        ({"field": "scope_input_coverage", "operator": "eq", "value": 1.0},),
        ({"step_id": "percentile", "operator": "peer_ratio_percentile"},),
        {"type": "peer_position_signal", "fields": ["target_value", "percentile", "scope_size"]},
        {"negative_gte": 0.67, "positive_lte": 0.33}, {"strong_tail": 0.2, "moderate_tail": 0.33}, {},
    ),
)


FORBIDDEN = ("causal_claim", "future_forecast", "investment_recommendation", "target_price")

ANALYSIS_PATTERNS = (
    AnalysisPattern(
        "operating_trend_summary_v1", 1, "operating_trend", ("trend_summary",),
        ("revenue_growth", "profit_growth", "cash_flow_growth", "trend_consistency"), (),
        ("negative_growth_signal",),
        ({"field": "period_coverage", "operator": "exact"}, {"field": "fact_graph_coverage", "operator": "eq", "value": 1.0}),
        {"required_claim_roles": ["revenue_trend", "profit_trend", "cash_flow_trend"], "minimum_caveats": 1},
        {"allowed": ["broadly_positive", "positive_with_caveat", "mixed_operating_trend", "broadly_negative"]},
        FORBIDDEN, "hard",
        "Based on the company's revenue, net income, and operating cash flow over the observed three-year period, summarize its operating trend and identify the main positive and cautionary signals.",
    ),
    AnalysisPattern(
        "growth_quality_diagnosis_v1", 1, "growth_quality", ("growth_quality_diagnosis",),
        ("revenue_growth", "profit_growth", "cash_flow_growth", "earnings_cash_divergence", "margin_change", "asset_efficiency_change"), (),
        ("earnings_cash_divergence", "negative_efficiency"),
        ({"field": "period_coverage", "operator": "exact"}, {"field": "counterevidence", "operator": "required_when_present"}),
        {"required_claim_roles": ["growth", "profitability", "cash_quality", "efficiency"], "minimum_caveats": 1},
        {"allowed": ["high_quality_growth", "growth_with_cash_caveat", "mixed_growth_quality", "weak_growth_quality"]},
        FORBIDDEN, "expert",
        "Evaluate the company's growth quality using revenue, profit, operating cash flow, margin, and asset-efficiency signals. State the strongest positive evidence, the main risk signal, and the limits of the evidence.",
    ),
    AnalysisPattern(
        "peer_positioning_v1", 1, "peer_positioning", ("peer_positioning",),
        ("peer_growth", "peer_margin", "peer_leverage"), (), ("high_peer_leverage",),
        ({"field": "scope_input_coverage", "operator": "eq", "value": 1.0}, {"field": "scope_size", "operator": "between", "value": [5, 30]}),
        {"required_claim_roles": ["relative_growth", "relative_profitability", "relative_leverage"], "minimum_caveats": 1},
        {"allowed": ["peer_leader", "peer_strength_with_leverage_caveat", "balanced_peer_position", "peer_laggard"]},
        FORBIDDEN, "expert",
        "Compare the company with the complete covered industry peer set on revenue growth, net margin, and leverage. Identify its main relative strength, weakness, and an evidence limitation.",
    ),
)


def signal_registry() -> dict[str, FinancialSignalSpec]:
    return {spec.signal_spec_id: spec for spec in SIGNAL_SPECS}


def analysis_pattern_registry() -> dict[str, AnalysisPattern]:
    return {pattern.analysis_pattern_id: pattern for pattern in ANALYSIS_PATTERNS}


def signal_registry_manifest() -> dict[str, Any]:
    return {"version": SIGNAL_REGISTRY_VERSION, "specs": [spec.row() for spec in SIGNAL_SPECS]}


def analysis_pattern_manifest() -> dict[str, Any]:
    return {"version": ANALYSIS_PATTERN_REGISTRY_VERSION, "patterns": [pattern.row() for pattern in ANALYSIS_PATTERNS]}
