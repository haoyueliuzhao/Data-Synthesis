from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from typing import Any

from finraw.qa.graph_walk.operation_macros import (
    MACROS,
    OperationMacro,
    get_operation_macro,
)
from finraw.qa.graph_walk.query_graph import QUERY_GRAPH_IR_VERSION, QueryGraphIR
from finraw.qa.graph_walk.schema_registry import (
    WALK_GRAMMAR_VERSION,
    relation_candidates,
)


@dataclass(frozen=True)
class TypedPath:
    steps: tuple[dict[str, Any], ...]
    total_cost: float


@dataclass(order=True)
class _BeamState:
    score: float
    node_type: str
    path: tuple[tuple[str, str, str], ...]
    visited_types: tuple[str, ...]


def find_typed_paths(
    from_type: str,
    to_type: str,
    *,
    maximum_depth: int,
    beam_width: int = 100,
    limit: int = 3,
) -> list[TypedPath]:
    if from_type == to_type:
        return [TypedPath((), 0.0)]
    heap: list[_BeamState] = [_BeamState(0.0, from_type, (), (from_type,))]
    complete: list[TypedPath] = []
    expanded = 0
    while heap and len(complete) < limit:
        state = heappop(heap)
        if len(state.path) >= maximum_depth:
            continue
        for spec, direction, target in relation_candidates(state.node_type):
            if target in state.visited_types:
                continue
            path = (*state.path, (spec.relation_type, direction, target))
            cost = state.score + spec.walk_cost
            if target == to_type:
                complete.append(
                    TypedPath(
                        tuple(
                            {
                                "relation": relation,
                                "direction": edge_direction,
                                "to_node_type": node_type,
                            }
                            for relation, edge_direction, node_type in path
                        ),
                        cost,
                    )
                )
                continue
            heappush(
                heap,
                _BeamState(cost, target, path, (*state.visited_types, target)),
            )
            expanded += 1
            if expanded > beam_width * max(maximum_depth, 1):
                break
        if len(heap) > beam_width:
            heap = sorted(heap)[:beam_width]
    return sorted(complete, key=lambda item: (item.total_cost, str(item.steps)))[:limit]


def _metric_id_for_role(macro: OperationMacro, role_name: str) -> str:
    role = next(item for item in macro.roles if item.role == role_name)
    for field, operator, value in role.predicates:
        if field == "properties.metric_id" and operator == "eq":
            return str(value)
    raise ValueError(
        f"Macro {macro.macro_id} role {role_name} has no fixed metric predicate"
    )


def assemble_query_graph(
    macro: OperationMacro,
    *,
    discovery_method: str = "typed_walk",
    beam_width: int = 100,
) -> QueryGraphIR:
    roles: dict[str, dict[str, Any]] = {
        item.role: {
            "node_type": item.node_type,
            "cardinality": item.cardinality,
            "required": True,
        }
        for item in macro.roles
    }
    walks: list[dict[str, Any]] = []
    role_constraints: list[dict[str, Any]] = []
    for role in macro.roles:
        if role.role == macro.anchor_role:
            continue
        if not role.parent_role or role.parent_role not in roles:
            raise ValueError(f"Macro role {role.role} has no bound parent role")
        parent_type = str(roles[role.parent_role]["node_type"])
        paths = find_typed_paths(
            parent_type,
            role.node_type,
            maximum_depth=macro.maximum_walk_depth,
            beam_width=beam_width,
            limit=1,
        )
        if not paths:
            raise ValueError(
                f"No registered typed path for macro {macro.macro_id}: "
                f"{parent_type} -> {role.node_type}"
            )
        selected = paths[0]
        steps = []
        from_role = role.parent_role
        for index, edge in enumerate(selected.steps):
            final = index == len(selected.steps) - 1
            to_role = role.role if final else f"__{role.role}_hop_{index + 1}"
            if not final:
                roles[to_role] = {
                    "node_type": edge["to_node_type"],
                    "cardinality": "many",
                    "required": True,
                    "generated": True,
                }
            step = {
                "from_role": from_role,
                "relation": edge["relation"],
                "direction": edge["direction"],
                "to_role": to_role,
                "to_node_type": edge["to_node_type"],
                "mode": role.cardinality
                if role.cardinality in {"one", "collect"}
                else ("collect" if role.cardinality == "many" else "one"),
                "required": True,
            }
            if final and role.predicates:
                step["predicates"] = role.predicate_rows()
            steps.append(step)
            from_role = to_role
        walks.append({"walk_id": f"bind_{role.role}", "steps": steps})
        if role.predicates:
            role_constraints.append(
                {
                    "constraint": "role_predicates",
                    "role": role.role,
                    "predicates": role.predicate_rows(),
                }
            )

    if macro.anchor.predicates:
        role_constraints.append(
            {
                "constraint": "role_predicates",
                "role": macro.anchor_role,
                "predicates": macro.anchor.predicate_rows(),
            }
        )
    fact_roles = [
        name
        for name, spec in roles.items()
        if spec["node_type"] == "Fact" and not spec.get("generated")
    ]
    if macro.pattern_family == "walk_temporal_followup":
        role_constraints.append(
            {
                "constraint": "require_roles_contiguous",
                "roles": ["primary_series", "secondary_series"],
                "group_keys": ["properties.entity_id"],
                "period_key": "properties.fiscal_year",
                "minimum_observations": 3,
            }
        )
    role_constraints.extend(
        {
            "constraint": "deduplicate_role_by_key",
            "role": role,
            "keys": ["properties.entity_id", "properties.fiscal_year"],
            "selection": "min_source_pk",
        }
        for role in fact_roles
    )
    entity_roles = [
        name
        for name, spec in roles.items()
        if spec["node_type"] == "Entity" and not spec.get("generated")
    ]
    derived_roles = [
        name
        for name, spec in roles.items()
        if spec["node_type"] == "DerivedFact" and not spec.get("generated")
    ]
    raw_roles = [
        name
        for name, spec in roles.items()
        if spec["node_type"] == "RawObject" and not spec.get("generated")
    ]
    projection: dict[str, Any] = {
        "role_bindings": {role: role for role in fact_roles},
        "fact_roles": fact_roles,
        "entity_roles": entity_roles,
        "derived_roles": derived_roles,
        "raw_object_roles": raw_roles,
        "scope_role": macro.anchor_role
        if macro.anchor.node_type == "EntitySet"
        else None,
        "scope_type": macro.pattern_family,
        "answer": {
            "binding": "graph_answer",
            "role": fact_roles[0],
            "shape": "records",
            "output_key": "records",
            "fields": {"fact_id": "source_pk"},
        },
    }
    if macro.pattern_family == "walk_temporal_followup":
        projection["context"] = {
            "primary_metric_id": _metric_id_for_role(macro, "primary_series"),
            "secondary_metric_id": _metric_id_for_role(
                macro, "secondary_series"
            ),
        }
        projection["provenance_binding"] = {
            "binding": "provenance_map",
            "fact_role": "secondary_series",
            "raw_object_role": "raw_objects",
            "relation": "TRACED_TO",
        }
    if macro.macro_id == "scope_filter_rank_followup":
        projection["context"] = {
            "primary_metric_id": "net_margin",
            "secondary_metric_id": "debt_ratio",
            "growth_threshold_pct": "10",
            "top_k": 3,
            "followup_rank": 1,
            "current_period": {
                "role": "current_revenue",
                "source": "properties.fiscal_year",
            },
        }
    if macro.macro_id == "derived_fact_time_source_trace":
        projection["context"] = {
            "derived_id": {"role": "derived_fact", "source": "source_pk"},
            "derived_type": {
                "role": "derived_fact",
                "source": "properties.derived_type",
                "default": "derived calculation",
            },
        }
        projection["answer"] = {
            "binding": "graph_answer",
            "shape": "fact_trace_records",
            "output_key": "inputs",
            "fact_role": "input_facts",
            "period_role": "periods",
            "hierarchy_role": "fiscal_years",
            "raw_object_role": "raw_objects",
        }

    graph = QueryGraphIR(
        query_graph_version=QUERY_GRAPH_IR_VERSION,
        discovery_method=discovery_method,
        operation_macro_id=macro.macro_id,
        answer_target=dict(macro.answer_target),
        anchors=(
            {
                "role": macro.anchor_role,
                "node_type": macro.anchor.node_type,
                "predicates": macro.anchor.predicate_rows(),
            },
        ),
        roles=roles,
        walks=tuple(walks),
        joins=tuple(dict(item) for item in macro.joins),
        role_constraints=tuple(
            [*role_constraints, *[dict(item) for item in macro.coverage_constraints]]
        ),
        semantic_constraints=tuple(dict(item) for item in macro.semantic_constraints),
        binding_projection=projection,
        operation_template=dict(macro.operator_template),
        answer_schema=dict(macro.answer_schema),
        evidence_policy={
            "required_roles": fact_roles,
            "context_roles": [macro.anchor_role, *entity_roles],
            "discard_unselected_walk_edges": True,
        },
        sampling={"stratum_fields": ["scope_type", "period", "entity_hash_bucket"]},
        walk_grammar_version=WALK_GRAMMAR_VERSION,
    )
    graph.validate()
    return graph


def discover_query_graphs(
    macro_ids: list[str] | tuple[str, ...] | None = None,
    *,
    discovery_method: str = "typed_walk",
    beam_width: int = 100,
) -> list[QueryGraphIR]:
    selected = list(macro_ids or [item.macro_id for item in MACROS])
    graphs = [
        assemble_query_graph(
            get_operation_macro(macro_id),
            discovery_method=discovery_method,
            beam_width=beam_width,
        )
        for macro_id in selected
    ]
    return sorted(graphs, key=lambda item: item.query_graph_hash)
