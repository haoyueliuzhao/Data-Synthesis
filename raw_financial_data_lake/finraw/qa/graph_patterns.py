from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class GraphPattern:
    pattern_id: str
    pattern_version: int
    pattern_family: str
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
        pattern_version=1,
        pattern_family="lookup",
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
        semantic_constraints=[{"field": "fact.graph_ready", "operator": "eq", "value": True}],
        operator_template={"operators": [{"step_id": "answer", "operator": "lookup", "inputs": [{"binding": "fact"}]}], "output_step": "answer"},
        answer_schema={"type": "numeric"},
        difficulty_base="easy",
        question_intents=("direct_lookup",),
    ),
    GraphPattern(
        pattern_id="pairwise_entity_metric_comparison",
        pattern_version=1,
        pattern_family="comparison",
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
            {"field": "unit", "operator": "compatible"},
            {"field": "currency", "operator": "compatible"},
        ],
        operator_template={"operators": [{"step_id": "answer", "operator": "compare", "inputs": [{"binding": "left"}, {"binding": "right"}]}], "output_step": "answer"},
        answer_schema={"type": "comparison", "fields": ["winner_id", "relation", "difference", "rows"]},
        difficulty_base="medium",
        question_intents=("which_is_higher", "direct_comparison"),
    ),
    GraphPattern(
        pattern_id="entity_cross_metric_comparison",
        pattern_version=1,
        pattern_family="comparison",
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
            {"field": "left_metric", "operator": "ne", "value_from": "right_metric"},
            {"field": "unit", "operator": "compatible"},
            {"field": "currency", "operator": "compatible"},
        ],
        operator_template={"operators": [{"step_id": "answer", "operator": "compare", "inputs": [{"binding": "left"}, {"binding": "right"}]}], "output_step": "answer"},
        answer_schema={"type": "comparison", "fields": ["winner_id", "relation", "difference", "rows"]},
        difficulty_base="medium",
        question_intents=("which_metric_is_higher", "metric_difference"),
    ),
    GraphPattern(
        pattern_id="entity_metric_temporal_average",
        pattern_version=1,
        pattern_family="temporal_aggregation",
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
            {"field": "unit", "operator": "same"},
            {"field": "currency", "operator": "same"},
        ],
        operator_template={"operators": [{"step_id": "answer", "operator": "mean", "inputs": [{"binding": "series"}]}], "output_step": "answer"},
        answer_schema={"type": "numeric", "aggregation": "arithmetic_mean"},
        difficulty_base="hard",
        question_intents=("period_average", "analyst_average"),
    ),
    GraphPattern(
        pattern_id="fact_provenance_trace",
        pattern_version=1,
        pattern_family="provenance",
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
        operator_template={"operators": [{"step_id": "answer", "operator": "provenance", "inputs": [{"binding": "fact"}]}], "output_step": "answer"},
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
