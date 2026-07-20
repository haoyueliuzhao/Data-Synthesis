from __future__ import annotations

from typing import Any

from finraw.qa.graph_walk.explorer import discover_query_graphs
from finraw.qa.graph_walk.grammar import compile_query_graph
from finraw.qa.graph_walk.operation_macros import (
    get_operation_macro,
    operation_macro_manifest,
)
from finraw.qa.graph_walk.schema_registry import relation_schema_manifest


def query_graph_pattern_spec(graph: Any) -> dict[str, Any]:
    macro = get_operation_macro(graph.operation_macro_id)
    edges = []
    for walk in graph.walks:
        for step in walk.get("steps") or []:
            edges.append(
                {
                    "src": step["from_role"],
                    "relation": step["relation"],
                    "dst": step["to_role"],
                    "direction": step.get("direction", "out"),
                }
            )
    required_metric_ids = sorted(
        {
            str(predicate["value"])
            for constraint in graph.role_constraints
            if constraint.get("constraint") == "role_predicates"
            for predicate in constraint.get("predicates") or []
            if predicate.get("field") == "properties.metric_id"
            and predicate.get("operator") == "eq"
        }
    )
    return {
        "pattern_version": 1,
        "pattern_family": macro.pattern_family,
        "task_subtype": macro.task_subtype,
        "semantic_profile": "graph_trace"
        if macro.macro_id == "derived_fact_time_source_trace"
        else "typed_walk",
        "node_constraints": [
            {
                "variable": role,
                "type": spec["node_type"],
                "cardinality": spec.get("cardinality", "one"),
            }
            for role, spec in sorted(graph.roles.items())
            if not spec.get("generated")
        ],
        "edge_constraints": edges,
        "semantic_constraints": [dict(item) for item in graph.semantic_constraints],
        "operator_template": dict(graph.operation_template),
        "answer_schema": dict(graph.answer_schema),
        "difficulty_base": macro.difficulty_base,
        "question_intents": list(macro.question_intents),
        "binding_query": compile_query_graph(graph),
        "discovery_method": graph.discovery_method,
        "query_graph_ir": graph.as_dict(),
        "query_graph_hash": graph.query_graph_hash,
        "walk_grammar_version": graph.walk_grammar_version,
        "operation_macro_id": graph.operation_macro_id,
        "required_metric_ids": required_metric_ids,
        "walk_schema_manifest_hash": relation_schema_manifest()["manifest_hash"],
        "operation_macro_manifest_hash": operation_macro_manifest()["manifest_hash"],
        "financial_value_score": macro.financial_value_score,
    }


def build_walk_pattern_specs(
    policy: dict[str, Any] | None = None,
    *,
    discovery_method: str = "typed_walk",
) -> list[tuple[str, dict[str, Any]]]:
    settings = dict(policy or {})
    macro_ids = settings.get("operation_macros")
    graphs = discover_query_graphs(
        macro_ids,
        discovery_method=discovery_method,
        beam_width=max(int(settings.get("beam_width", 100)), 1),
    )
    return [
        (
            get_operation_macro(graph.operation_macro_id).pattern_family,
            query_graph_pattern_spec(graph),
        )
        for graph in graphs
    ]
