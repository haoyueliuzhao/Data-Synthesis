from __future__ import annotations

from typing import Any

from finraw.qa.graph_walk.query_graph import QueryGraphIR


BINDING_QUERY_IR_VERSION = 2


def compile_query_graph(graph: QueryGraphIR) -> dict[str, Any]:
    graph.validate()
    anchor = graph.anchors[0]
    operations: list[dict[str, Any]] = [
        {
            "op": "scan_pinned_graph_nodes",
            "role": anchor["role"],
            "node_type": anchor["node_type"],
        }
    ]
    if anchor.get("predicates"):
        operations.append(
            {
                "op": "filter_graph_role",
                "role": anchor["role"],
                "predicates": list(anchor["predicates"]),
            }
        )
    expanded_roles = {str(anchor["role"])}
    pending = [step for walk in graph.walks for step in walk.get("steps") or []]
    while pending:
        progressed = False
        for step in list(pending):
            if str(step["from_role"]) not in expanded_roles:
                continue
            operations.append(
                {
                    "op": "expand_graph_edges",
                    **{
                        key: value for key, value in step.items() if key != "predicates"
                    },
                }
            )
            expanded_roles.add(str(step["to_role"]))
            if step.get("predicates"):
                operations.append(
                    {
                        "op": "filter_graph_role",
                        "role": step["to_role"],
                        "predicates": list(step["predicates"]),
                    }
                )
            pending.remove(step)
            progressed = True
        if not progressed:
            raise ValueError(
                "QueryGraphIR contains walks with unresolved role dependencies"
            )

    for constraint in graph.role_constraints:
        if constraint.get("constraint") == "deduplicate_role_by_key":
            operations.append(
                {
                    "op": "deduplicate_graph_role",
                    **{
                        key: value
                        for key, value in dict(constraint).items()
                        if key != "constraint"
                    },
                }
            )
    for constraint in graph.role_constraints:
        if constraint.get("constraint") == "require_roles_contiguous":
            operations.append(
                {
                    "op": "require_graph_roles_contiguous",
                    **{
                        key: value
                        for key, value in dict(constraint).items()
                        if key != "constraint"
                    },
                }
            )
    for join in graph.joins:
        operation = dict(join)
        operation["op"] = str(operation.pop("join_type"))
        operations.append(operation)
    for constraint in graph.role_constraints:
        if constraint.get("scope_role") and constraint.get("fact_roles"):
            operations.append({"op": "require_role_coverage", **dict(constraint)})
    operations.append(
        {
            "op": "project_graph_binding_v2",
            **dict(graph.binding_projection),
            "query_graph_hash": graph.query_graph_hash,
            "answer_target": dict(graph.answer_target),
            "evidence_policy": dict(graph.evidence_policy),
        }
    )
    return {
        "ir_version": BINDING_QUERY_IR_VERSION,
        "scan_kind": "graph",
        "relational_ops": operations,
        "stratum_fields": list(graph.sampling.get("stratum_fields") or []),
    }
