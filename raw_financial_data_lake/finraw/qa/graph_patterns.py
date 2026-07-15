from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class GraphPattern:
    pattern_id: str
    pattern_version: int
    pattern_family: str
    task_subtype: str
    matcher: str | None
    node_constraints: list[dict[str, Any]]
    edge_constraints: list[dict[str, str]]
    semantic_constraints: list[dict[str, Any]]
    operator_template: dict[str, Any]
    answer_schema: dict[str, Any]
    difficulty_base: str
    question_intents: tuple[str, ...]
    is_active: bool = True

    def as_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["question_intents"] = list(self.question_intents)
        return row


PATTERNS: tuple[GraphPattern, ...] = (
    GraphPattern(
        pattern_id="entity_metric_time_lookup",
        pattern_version=2,
        pattern_family="lookup",
        task_subtype="single_fact",
        matcher=None,
        node_constraints=[
            {"variable": "entity", "type": "Entity"},
            {"variable": "fact", "type": "Fact"},
            {"variable": "metric", "type": "Metric"},
            {"variable": "period", "type": "TimePeriod"},
        ],
        edge_constraints=[
            {"src": "entity", "relation": "HAS_FACT", "dst": "fact"},
            {"src": "fact", "relation": "MEASURES", "dst": "metric"},
            {"src": "fact", "relation": "IN_PERIOD", "dst": "period"},
        ],
        semantic_constraints=[
            {"field": "fact.graph_ready", "operator": "eq", "value": True}
        ],
        operator_template={
            "operators": [
                {
                    "step_id": "answer",
                    "operator": "lookup",
                    "inputs": [{"binding": "fact"}],
                }
            ],
            "output_step": "answer",
        },
        answer_schema={"type": "numeric"},
        difficulty_base="easy",
        question_intents=("direct_lookup",),
    ),
    GraphPattern(
        pattern_id="pairwise_entity_metric_comparison",
        pattern_version=3,
        pattern_family="comparison",
        task_subtype="pairwise_entity_comparison",
        matcher="pairwise_entity_metric_comparison",
        node_constraints=[
            {"variable": "left_entity", "type": "Entity"},
            {"variable": "left_fact", "type": "Fact"},
            {"variable": "right_entity", "type": "Entity"},
            {"variable": "right_fact", "type": "Fact"},
            {"variable": "metric", "type": "Metric"},
            {"variable": "period", "type": "TimePeriod"},
        ],
        edge_constraints=[
            {"src": "left_entity", "relation": "HAS_FACT", "dst": "left_fact"},
            {"src": "right_entity", "relation": "HAS_FACT", "dst": "right_fact"},
            {"src": "left_fact", "relation": "MEASURES", "dst": "metric"},
            {"src": "right_fact", "relation": "MEASURES", "dst": "metric"},
            {"src": "left_fact", "relation": "IN_PERIOD", "dst": "period"},
            {"src": "right_fact", "relation": "IN_PERIOD", "dst": "period"},
        ],
        semantic_constraints=[
            {"field": "left_entity", "operator": "ne", "value_from": "right_entity"},
            {"field": "entity_type", "operator": "same"},
            {"field": "scope", "operator": "same"},
            {"field": "source_definition", "operator": "compatible"},
            {"field": "time_basis", "operator": "same"},
            {"field": "frequency", "operator": "same"},
            {"field": "is_forecast", "operator": "eq", "value": False},
            {"field": "unit", "operator": "compatible"},
            {"field": "currency", "operator": "compatible"},
        ],
        operator_template={
            "operators": [
                {
                    "step_id": "answer",
                    "operator": "compare",
                    "inputs": [{"binding": "left"}, {"binding": "right"}],
                }
            ],
            "output_step": "answer",
        },
        answer_schema={
            "type": "comparison",
            "fields": ["winner_id", "relation", "difference", "rows"],
        },
        difficulty_base="medium",
        question_intents=("which_is_higher", "direct_comparison"),
    ),
    GraphPattern(
        pattern_id="entity_cross_metric_comparison",
        pattern_version=3,
        pattern_family="comparison",
        task_subtype="cross_metric_comparison",
        matcher="entity_cross_metric_comparison",
        node_constraints=[
            {"variable": "entity", "type": "Entity"},
            {"variable": "left_fact", "type": "Fact"},
            {"variable": "right_fact", "type": "Fact"},
            {"variable": "left_metric", "type": "Metric"},
            {"variable": "right_metric", "type": "Metric"},
            {"variable": "period", "type": "TimePeriod"},
        ],
        edge_constraints=[
            {"src": "entity", "relation": "HAS_FACT", "dst": "left_fact"},
            {"src": "entity", "relation": "HAS_FACT", "dst": "right_fact"},
            {"src": "left_fact", "relation": "MEASURES", "dst": "left_metric"},
            {"src": "right_fact", "relation": "MEASURES", "dst": "right_metric"},
            {"src": "left_fact", "relation": "IN_PERIOD", "dst": "period"},
            {"src": "right_fact", "relation": "IN_PERIOD", "dst": "period"},
        ],
        semantic_constraints=[
            {"field": "metric_pair", "operator": "registered_comparable_pair"},
            {"field": "statement_type", "operator": "same"},
            {"field": "metric_period_type", "operator": "same"},
            {"field": "source_definition", "operator": "compatible"},
            {"field": "frequency", "operator": "same"},
            {"field": "is_forecast", "operator": "eq", "value": False},
            {"field": "unit", "operator": "compatible"},
            {"field": "currency", "operator": "compatible"},
        ],
        operator_template={
            "operators": [
                {
                    "step_id": "answer",
                    "operator": "compare",
                    "inputs": [{"binding": "left"}, {"binding": "right"}],
                }
            ],
            "output_step": "answer",
        },
        answer_schema={
            "type": "comparison",
            "fields": ["winner_id", "relation", "difference", "rows"],
        },
        difficulty_base="medium",
        question_intents=("which_metric_is_higher", "metric_difference"),
    ),
    GraphPattern(
        pattern_id="entity_metric_temporal_average",
        pattern_version=4,
        pattern_family="temporal_aggregation",
        task_subtype="multi_period_average",
        matcher="entity_metric_temporal_average",
        node_constraints=[
            {"variable": "entity", "type": "Entity"},
            {"variable": "facts", "type": "Fact", "cardinality": "many"},
            {"variable": "metric", "type": "Metric"},
            {"variable": "periods", "type": "TimePeriod", "cardinality": "many"},
        ],
        edge_constraints=[
            {"src": "entity", "relation": "HAS_FACT", "dst": "facts"},
            {"src": "facts", "relation": "MEASURES", "dst": "metric"},
            {"src": "facts", "relation": "IN_PERIOD", "dst": "periods"},
        ],
        semantic_constraints=[
            {"field": "facts.count", "operator": "gte", "value": 3},
            {"field": "periods", "operator": "contiguous"},
            {"field": "annual_flow_duration", "operator": "between_days", "value": [300, 430]},
            {"field": "source_definition", "operator": "same"},
            {"field": "frequency", "operator": "same"},
            {"field": "time_basis", "operator": "same"},
            {"field": "is_forecast", "operator": "eq", "value": False},
            {"field": "unit", "operator": "same"},
            {"field": "currency", "operator": "same"},
        ],
        operator_template={
            "operators": [
                {
                    "step_id": "answer",
                    "operator": "mean",
                    "inputs": [{"binding": "series"}],
                }
            ],
            "output_step": "answer",
        },
        answer_schema={"type": "numeric", "aggregation": "arithmetic_mean"},
        difficulty_base="hard",
        question_intents=("period_average", "analyst_average"),
    ),
    GraphPattern(
        pattern_id="temporal_argmax_then_metric_lookup",
        pattern_version=3,
        pattern_family="multi_stage_temporal_join",
        task_subtype="temporal_peak_followup",
        matcher="temporal_argmax_then_metric_lookup",
        node_constraints=[
            {"variable": "entity", "type": "Entity"},
            {"variable": "primary_facts", "type": "Fact", "cardinality": "many"},
            {"variable": "secondary_facts", "type": "Fact", "cardinality": "many"},
            {"variable": "primary_metric", "type": "Metric"},
            {"variable": "secondary_metric", "type": "Metric"},
            {"variable": "periods", "type": "TimePeriod", "cardinality": "many"},
        ],
        edge_constraints=[
            {"src": "entity", "relation": "HAS_FACT", "dst": "primary_facts"},
            {"src": "entity", "relation": "HAS_FACT", "dst": "secondary_facts"},
            {"src": "primary_facts", "relation": "MEASURES", "dst": "primary_metric"},
            {"src": "secondary_facts", "relation": "MEASURES", "dst": "secondary_metric"},
            {"src": "primary_facts", "relation": "IN_PERIOD", "dst": "periods"},
            {"src": "secondary_facts", "relation": "IN_PERIOD", "dst": "periods"},
        ],
        semantic_constraints=[
            {"field": "primary_facts.count", "operator": "gte", "value": 3},
            {"field": "periods", "operator": "contiguous"},
            {"field": "annual_flow_duration", "operator": "between_days", "value": [300, 430]},
            {"field": "secondary_period_coverage", "operator": "eq", "value": 1.0},
            {"field": "financial_scope", "operator": "same"},
            {"field": "source_definition", "operator": "compatible_by_series"},
            {"field": "frequency", "operator": "same"},
            {"field": "time_basis", "operator": "same"},
            {"field": "is_forecast", "operator": "eq", "value": False},
        ],
        operator_template={
            "operators": [
                {
                    "step_id": "find_peak",
                    "operator": "argmax",
                    "inputs": [{"binding": "primary_series"}],
                    "params": {"selection_key": "period"},
                },
                {
                    "step_id": "answer",
                    "operator": "select_by_period",
                    "inputs": [
                        {"step": "find_peak"},
                        {"binding": "secondary_series"},
                    ],
                },
            ],
            "output_step": "answer",
        },
        answer_schema={
            "type": "period_metric_lookup",
            "fields": [
                "period",
                "primary_value",
                "secondary_value",
                "unit",
                "currency",
            ],
        },
        difficulty_base="expert",
        question_intents=("peak_then_lookup", "temporal_followup"),
    ),
    GraphPattern(
        pattern_id="industry_growth_filter_then_margin_rank",
        pattern_version=2,
        pattern_family="multi_stage_scope_analysis",
        task_subtype="filter_then_rank",
        matcher="industry_growth_filter_then_margin_rank",
        node_constraints=[
            {"variable": "entities", "type": "Entity", "cardinality": "many"},
            {"variable": "current_revenue", "type": "Fact", "cardinality": "many"},
            {"variable": "previous_revenue", "type": "Fact", "cardinality": "many"},
            {"variable": "net_income", "type": "Fact", "cardinality": "many"},
        ],
        edge_constraints=[
            {"src": "entities", "relation": "HAS_FACT", "dst": "current_revenue"},
            {"src": "entities", "relation": "HAS_FACT", "dst": "previous_revenue"},
            {"src": "entities", "relation": "HAS_FACT", "dst": "net_income"},
        ],
        semantic_constraints=[
            {"field": "entity.industry", "operator": "same"},
            {"field": "financial_scope", "operator": "consolidated_entity"},
            {"field": "revenue_growth_pct", "operator": "gt", "value_from": "policy"},
            {"field": "scope_input_coverage", "operator": "eq", "value": 1.0},
            {"field": "annual_flow_duration", "operator": "between_days", "value": [300, 430]},
        ],
        operator_template={
            "operators": [
                {
                    "step_id": "growth",
                    "operator": "growth_by_entity",
                    "inputs": [
                        {"binding": "current_revenue"},
                        {"binding": "previous_revenue"},
                    ],
                    "params": {"output_metric_id": "revenue_yoy_growth"},
                },
                {
                    "step_id": "growth_filter",
                    "operator": "filter",
                    "inputs": [{"step": "growth"}],
                    "params": {"comparison": "gt", "field": "normalized_value", "value": "10"},
                },
                {
                    "step_id": "margin",
                    "operator": "ratio_by_entity",
                    "inputs": [
                        {"binding": "net_income"},
                        {"binding": "current_revenue"},
                    ],
                    "params": {"output_metric_id": "net_margin"},
                },
                {
                    "step_id": "eligible_margins",
                    "operator": "intersect_on_entity",
                    "inputs": [{"step": "growth_filter"}, {"step": "margin"}],
                },
                {
                    "step_id": "answer",
                    "operator": "rank",
                    "inputs": [{"step": "eligible_margins"}],
                    "params": {"direction": "desc", "top_k": 3},
                },
            ],
            "output_step": "answer",
        },
        answer_schema={"type": "ranked_table", "value_metric": "net_margin"},
        difficulty_base="research",
        question_intents=("growth_screen_then_margin_rank", "analyst_filter_rank"),
    ),
    GraphPattern(
        pattern_id="industry_revenue_rank_then_assets_lookup",
        pattern_version=2,
        pattern_family="multi_stage_scope_analysis",
        task_subtype="rank_then_secondary_lookup",
        matcher="industry_revenue_rank_then_assets_lookup",
        node_constraints=[
            {"variable": "entities", "type": "Entity", "cardinality": "many"},
            {"variable": "revenue", "type": "Fact", "cardinality": "many"},
            {"variable": "total_assets", "type": "Fact", "cardinality": "many"},
        ],
        edge_constraints=[
            {"src": "entities", "relation": "HAS_FACT", "dst": "revenue"},
            {"src": "entities", "relation": "HAS_FACT", "dst": "total_assets"},
        ],
        semantic_constraints=[
            {"field": "entity.industry", "operator": "same"},
            {"field": "period", "operator": "same"},
            {"field": "financial_scope", "operator": "consolidated_entity"},
            {"field": "secondary_entity_coverage", "operator": "eq", "value": 1.0},
            {"field": "annual_flow_duration", "operator": "between_days", "value": [300, 430]},
        ],
        operator_template={
            "operators": [
                {
                    "step_id": "rank_revenue",
                    "operator": "rank",
                    "inputs": [{"binding": "revenue"}],
                    "params": {"direction": "desc", "top_k": 3},
                },
                {
                    "step_id": "answer",
                    "operator": "lookup_ranked_entities",
                    "inputs": [{"step": "rank_revenue"}, {"binding": "total_assets"}],
                },
            ],
            "output_step": "answer",
        },
        answer_schema={
            "type": "multi_metric_ranked_table",
            "primary_metric": "revenue",
            "secondary_metric": "total_assets",
        },
        difficulty_base="expert",
        question_intents=("ranking_followup", "top_entities_secondary_metric"),
    ),
    GraphPattern(
        pattern_id="industry_multi_factor_screening",
        pattern_version=2,
        pattern_family="multi_stage_scope_analysis",
        task_subtype="multi_factor_screening",
        matcher="industry_multi_factor_screening",
        node_constraints=[
            {"variable": "entities", "type": "Entity", "cardinality": "many"},
            {"variable": "financial_facts", "type": "Fact", "cardinality": "many"},
        ],
        edge_constraints=[
            {"src": "entities", "relation": "HAS_FACT", "dst": "financial_facts"},
            {"src": "financial_facts", "relation": "MEASURES", "dst": "metrics"},
            {"src": "financial_facts", "relation": "IN_PERIOD", "dst": "periods"},
        ],
        semantic_constraints=[
            {"field": "entity.industry", "operator": "same"},
            {"field": "financial_scope", "operator": "consolidated_entity"},
            {"field": "revenue_growth_pct", "operator": "gt", "value_from": "policy"},
            {"field": "net_margin", "operator": "gt_industry_average"},
            {"field": "debt_ratio_pct", "operator": "lt", "value_from": "policy"},
            {"field": "annual_flow_duration", "operator": "between_days", "value": [300, 430]},
        ],
        operator_template={
            "operators": [
                {
                    "step_id": "growth",
                    "operator": "growth_by_entity",
                    "inputs": [
                        {"binding": "current_revenue"},
                        {"binding": "previous_revenue"},
                    ],
                    "params": {"output_metric_id": "revenue_yoy_growth"},
                },
                {
                    "step_id": "margin",
                    "operator": "ratio_by_entity",
                    "inputs": [{"binding": "net_income"}, {"binding": "current_revenue"}],
                    "params": {"output_metric_id": "net_margin"},
                },
                {
                    "step_id": "debt_ratio",
                    "operator": "ratio_by_entity",
                    "inputs": [{"binding": "total_liabilities"}, {"binding": "total_assets"}],
                    "params": {"output_metric_id": "debt_ratio"},
                },
                {
                    "step_id": "answer",
                    "operator": "multi_factor_screen",
                    "inputs": [{"step": "growth"}, {"step": "margin"}, {"step": "debt_ratio"}],
                    "params": {"growth_min_pct": "10", "debt_max_pct": "70"},
                },
            ],
            "output_step": "answer",
        },
        answer_schema={"type": "screening_table", "order": "net_margin_desc"},
        difficulty_base="research",
        question_intents=("multi_factor_screen", "analyst_screen"),
    ),
    GraphPattern(
        pattern_id="fact_provenance_trace",
        pattern_version=2,
        pattern_family="provenance",
        task_subtype="provenance_trace",
        matcher=None,
        node_constraints=[
            {"variable": "fact", "type": "Fact"},
            {"variable": "source", "type": "DataSource"},
            {"variable": "raw_object", "type": "RawObject"},
            {"variable": "definition", "type": "SourceDefinition"},
        ],
        edge_constraints=[
            {"src": "fact", "relation": "FROM_SOURCE", "dst": "source"},
            {"src": "fact", "relation": "TRACED_TO", "dst": "raw_object"},
            {"src": "fact", "relation": "USES_SOURCE_DEFINITION", "dst": "definition"},
        ],
        semantic_constraints=[],
        operator_template={
            "operators": [
                {
                    "step_id": "answer",
                    "operator": "provenance",
                    "inputs": [{"binding": "fact"}],
                }
            ],
            "output_step": "answer",
        },
        answer_schema={"type": "evidence_trace"},
        difficulty_base="easy",
        question_intents=("source_trace", "definition_trace"),
        is_active=False,
    ),
)


def pattern_registry() -> dict[str, GraphPattern]:
    return {pattern.pattern_id: pattern for pattern in PATTERNS}


def get_pattern(pattern_id: str) -> GraphPattern:
    try:
        return pattern_registry()[pattern_id]
    except KeyError as exc:
        raise ValueError(f"Unknown QA graph pattern: {pattern_id}") from exc


def pattern_manifest() -> list[dict[str, Any]]:
    return [pattern.as_row() for pattern in PATTERNS]
