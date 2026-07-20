from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


OPERATION_MACRO_REGISTRY_VERSION = "1.0.0"


@dataclass(frozen=True)
class MacroRole:
    role: str
    node_type: str
    cardinality: str
    parent_role: str | None = None
    predicates: tuple[tuple[str, str, Any], ...] = ()

    def predicate_rows(self) -> list[dict[str, Any]]:
        return [
            {"field": field, "operator": operator, "value": value}
            for field, operator, value in self.predicates
        ]


@dataclass(frozen=True)
class OperationMacro:
    macro_id: str
    pattern_family: str
    task_subtype: str
    anchor_role: str
    roles: tuple[MacroRole, ...]
    joins: tuple[dict[str, Any], ...]
    coverage_constraints: tuple[dict[str, Any], ...]
    semantic_constraints: tuple[dict[str, Any], ...]
    operator_template: dict[str, Any]
    answer_schema: dict[str, Any]
    answer_target: dict[str, Any]
    difficulty_base: str
    question_intents: tuple[str, ...]
    maximum_walk_depth: int
    financial_value_score: float

    @property
    def anchor(self) -> MacroRole:
        return next(role for role in self.roles if role.role == self.anchor_role)


def _annual_metric(metric_id: str) -> tuple[tuple[str, str, Any], ...]:
    return (
        ("properties.metric_id", "eq", metric_id),
        ("properties.fiscal_quarter", "eq", "FY"),
    )


MACROS: tuple[OperationMacro, ...] = (
    OperationMacro(
        macro_id="temporal_extreme_followup_provenance",
        pattern_family="walk_temporal_followup",
        task_subtype="walk_temporal_peak_followup_provenance",
        anchor_role="entity",
        roles=(
            MacroRole("entity", "Entity", "one"),
            MacroRole(
                "primary_series",
                "Fact",
                "many",
                "entity",
                _annual_metric("revenue"),
            ),
            MacroRole(
                "secondary_series",
                "Fact",
                "many",
                "entity",
                _annual_metric("net_cash_provided_by_used_in_operating_activities"),
            ),
            MacroRole("raw_objects", "RawObject", "many", "secondary_series"),
        ),
        joins=(
            {
                "join_type": "assert_role_key_equal",
                "roles": ["primary_series", "secondary_series"],
                "keys": ["properties.entity_id", "properties.fiscal_year"],
                "intersection": True,
                "minimum_common": 3,
            },
        ),
        coverage_constraints=(),
        semantic_constraints=(
            {"field": "primary_series.count", "operator": "gte", "value": 3},
            {"field": "periods", "operator": "contiguous"},
            {"field": "is_forecast", "operator": "eq", "value": False},
        ),
        operator_template={
            "operators": [
                {
                    "step_id": "find_peak",
                    "operator": "argmax",
                    "inputs": [{"binding": "primary_series"}],
                },
                {
                    "step_id": "select_followup",
                    "operator": "select_by_period",
                    "inputs": [{"step": "find_peak"}, {"binding": "secondary_series"}],
                },
                {
                    "step_id": "answer",
                    "operator": "attach_provenance",
                    "inputs": [
                        {"step": "select_followup"},
                        {"binding": "provenance_map"},
                    ],
                },
            ],
            "output_step": "answer",
        },
        answer_schema={
            "type": "period_metric_provenance",
            "fields": ["period", "primary_value", "secondary_value", "raw_object_ids"],
        },
        answer_target={"type": "period_metric_provenance", "role": "secondary_series"},
        difficulty_base="research",
        question_intents=("peak_followup_with_source",),
        maximum_walk_depth=3,
        financial_value_score=0.96,
    ),
    OperationMacro(
        macro_id="scope_filter_rank_followup",
        pattern_family="walk_scope_analysis",
        task_subtype="walk_scope_filter_rank_followup",
        anchor_role="peer_scope",
        roles=(
            MacroRole(
                "peer_scope",
                "EntitySet",
                "one",
                predicates=(("properties.scope_type", "eq", "industry_universe"),),
            ),
            MacroRole("entities", "Entity", "many", "peer_scope"),
            MacroRole(
                "current_revenue",
                "Fact",
                "many",
                "entities",
                _annual_metric("revenue"),
            ),
            MacroRole(
                "previous_revenue",
                "Fact",
                "many",
                "entities",
                _annual_metric("revenue"),
            ),
            MacroRole(
                "net_income",
                "Fact",
                "many",
                "entities",
                _annual_metric("net_income"),
            ),
            MacroRole(
                "total_assets",
                "Fact",
                "many",
                "entities",
                _annual_metric("total_assets"),
            ),
            MacroRole(
                "total_liabilities",
                "Fact",
                "many",
                "entities",
                _annual_metric("total_liabilities"),
            ),
        ),
        joins=(
            {
                "join_type": "assert_role_key_relation",
                "left_role": "current_revenue",
                "right_role": "previous_revenue",
                "match_keys": ["properties.entity_id"],
                "key": "properties.fiscal_year",
                "relation": "previous_by",
                "value": 1,
            },
            {
                "join_type": "assert_role_key_equal",
                "roles": [
                    "current_revenue",
                    "net_income",
                    "total_assets",
                    "total_liabilities",
                ],
                "keys": ["properties.entity_id", "properties.fiscal_year"],
                "intersection": True,
                "minimum_common": 2,
            },
        ),
        coverage_constraints=(
            {
                "scope_role": "entities",
                "fact_roles": [
                    "current_revenue",
                    "previous_revenue",
                    "net_income",
                    "total_assets",
                    "total_liabilities",
                ],
                "coverage": 1.0,
            },
        ),
        semantic_constraints=(
            {"field": "financial_scope", "operator": "consolidated_entity"},
            {"field": "scope_input_coverage", "operator": "eq", "value": 1.0},
            {"field": "is_forecast", "operator": "eq", "value": False},
        ),
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
                    "params": {
                        "field": "normalized_value",
                        "comparison": "gt",
                        "value": "10",
                    },
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
                    "step_id": "ranking",
                    "operator": "rank",
                    "inputs": [{"step": "eligible_margins"}],
                    "params": {"direction": "desc", "top_k": 3},
                },
                {
                    "step_id": "debt_ratio",
                    "operator": "ratio_by_entity",
                    "inputs": [
                        {"binding": "total_liabilities"},
                        {"binding": "total_assets"},
                    ],
                    "params": {"output_metric_id": "debt_ratio"},
                },
                {
                    "step_id": "answer",
                    "operator": "lookup_ranked_entities",
                    "inputs": [{"step": "ranking"}, {"step": "debt_ratio"}],
                    "params": {"target_ranks": [1]},
                },
            ],
            "output_step": "answer",
        },
        answer_schema={
            "type": "filtered_rank_followup",
            "top_k": 3,
            "followup_rank": 1,
        },
        answer_target={
            "type": "ranked_entities_with_followup",
            "role": "total_liabilities",
        },
        difficulty_base="research",
        question_intents=("filter_rank_followup",),
        maximum_walk_depth=3,
        financial_value_score=0.98,
    ),
    OperationMacro(
        macro_id="derived_fact_time_source_trace",
        pattern_family="walk_derived_trace",
        task_subtype="walk_derived_input_time_source_trace",
        anchor_role="derived_fact",
        roles=(
            MacroRole("derived_fact", "DerivedFact", "one"),
            MacroRole("input_facts", "Fact", "many", "derived_fact"),
            MacroRole("periods", "TimePeriod", "many", "input_facts"),
            MacroRole("fiscal_years", "FiscalYear", "many", "periods"),
            MacroRole("raw_objects", "RawObject", "many", "input_facts"),
        ),
        joins=(),
        coverage_constraints=(),
        semantic_constraints=(
            {"field": "graph_ready", "operator": "eq", "value": True},
            {"field": "is_forecast", "operator": "eq", "value": False},
        ),
        operator_template={
            "operators": [
                {
                    "step_id": "answer",
                    "operator": "graph_answer",
                    "inputs": [{"binding": "graph_answer"}],
                }
            ],
            "output_step": "answer",
        },
        answer_schema={"type": "derived_fact_input_trace"},
        answer_target={"type": "derived_fact_input_trace", "role": "input_facts"},
        difficulty_base="hard",
        question_intents=("derived_inputs_with_time_and_source",),
        maximum_walk_depth=3,
        financial_value_score=0.9,
    ),
)


def get_operation_macro(macro_id: str) -> OperationMacro:
    try:
        return next(item for item in MACROS if item.macro_id == macro_id)
    except StopIteration as exc:
        raise ValueError(f"Unknown typed-walk operation macro: {macro_id}") from exc


def operation_macro_manifest() -> dict[str, Any]:
    rows = [asdict(item) for item in MACROS]
    payload = json.dumps(rows, sort_keys=True, default=str, separators=(",", ":"))
    return {
        "registry_version": OPERATION_MACRO_REGISTRY_VERSION,
        "macro_count": len(rows),
        "macros": rows,
        "manifest_hash": hashlib.sha256(payload.encode()).hexdigest(),
    }
