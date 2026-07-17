from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any

from finraw.qa.comparability import fact_frequency, period_label
from finraw.qa.store import chunks, json_value


LITERAL_BINDING_KEY = "__literal__"


def scan_pinned_graph_nodes(state: Any, operation: dict[str, Any]) -> None:
    _expect(state, "uninitialized", operation)
    role = _required_text(operation, "role")
    node_type = _required_text(operation, "node_type")
    predicates = [
        "kg_build_id = ?",
        "node_type = ?",
        "COALESCE(is_active, TRUE) = TRUE",
    ]
    parameters: list[Any] = [state.kg["kg_build_id"], node_type]
    source_table = operation.get("source_table")
    if source_table:
        predicates.append("source_table = ?")
        parameters.append(str(source_table))
    limit = int(
        operation.get("limit")
        or state.plan.get("sampling", {}).get("graph_scan_rows")
        or state.policy.get("compiled_graph_scan_rows", 5000)
    )
    rows = state.db.fetchall(
        "SELECT node_id, stable_node_id, node_type, source_table, source_pk, "
        "properties_json FROM kg_nodes WHERE "
        + " AND ".join(predicates)
        + " ORDER BY stable_node_id, node_id LIMIT ?",
        (*parameters, limit),
    )
    state.relation = [
        {
            "roles": {role: _node(dict(row))},
            "graph_node_ids": [str(row["node_id"])],
            "graph_edges": [],
        }
        for row in rows
    ]
    state.candidate_limit = max(
        len(state.relation),
        int(state.policy["max_candidates_per_proposal"])
        * int(state.policy["compiled_scan_multiplier"]),
    )
    state.relation_kind = "graph_rows"


def expand_graph_edges(state: Any, operation: dict[str, Any]) -> None:
    _expect(state, "graph_rows", operation)
    from_role = _required_text(operation, "from_role")
    to_role = _required_text(operation, "to_role")
    relations = operation.get("relations") or [operation.get("relation")]
    relation_types = [str(value) for value in relations if value]
    if not relation_types:
        raise ValueError("expand_graph_edges requires relation or relations")
    direction = str(operation.get("direction") or "out")
    if direction not in {"out", "in"}:
        raise ValueError("expand_graph_edges direction must be out or in")
    mode = str(operation.get("mode") or "one")
    if mode not in {"one", "collect"}:
        raise ValueError("expand_graph_edges mode must be one or collect")
    required = bool(operation.get("required", True))
    expected_types = {
        str(value)
        for value in operation.get("to_node_types")
        or ([operation["to_node_type"]] if operation.get("to_node_type") else [])
    }

    source_ids = sorted(
        {
            str(node["node_id"])
            for row in state.relation
            for node in _role_nodes(row, from_role)
        }
    )
    matches: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(
        list
    )
    source_column = "src_node_id" if direction == "out" else "dst_node_id"
    target_column = "dst_node_id" if direction == "out" else "src_node_id"
    for batch in chunks(source_ids, 500):
        source_placeholders = ",".join("?" for _ in batch)
        relation_placeholders = ",".join("?" for _ in relation_types)
        rows = state.db.fetchall(
            f"SELECT e.edge_id, e.stable_edge_id, e.src_node_id, e.dst_node_id, "
            f"e.relation_type, n.node_id, n.stable_node_id, n.node_type, "
            f"n.source_table, n.source_pk, n.properties_json "
            f"FROM kg_edges e JOIN kg_nodes n ON n.kg_build_id = e.kg_build_id "
            f"AND n.node_id = e.{target_column} "
            f"WHERE e.kg_build_id = ? AND e.{source_column} IN ({source_placeholders}) "
            f"AND e.relation_type IN ({relation_placeholders}) "
            "AND COALESCE(e.is_active, TRUE) = TRUE "
            "AND COALESCE(n.is_active, TRUE) = TRUE "
            f"ORDER BY e.{source_column}, e.relation_type, e.edge_id",
            [state.kg["kg_build_id"], *batch, *relation_types],
        )
        for raw in rows:
            item = dict(raw)
            node = _node(item)
            if expected_types and str(node["node_type"]) not in expected_types:
                continue
            edge = {
                "edge_id": str(item["edge_id"]),
                "src_node_id": str(item["src_node_id"]),
                "dst_node_id": str(item["dst_node_id"]),
                "relation_type": str(item["relation_type"]),
            }
            matches[str(item[source_column])].append((edge, node))

    expanded: list[dict[str, Any]] = []
    for row in state.relation:
        selected = [
            match
            for source in _role_nodes(row, from_role)
            for match in matches.get(str(source["node_id"]), [])
        ]
        minimum_related = int(operation.get("minimum_related") or 1)
        maximum_related = int(operation.get("maximum_related") or 0)
        if selected and (
            len(selected) < minimum_related
            or (maximum_related and len(selected) > maximum_related)
        ):
            continue
        if not selected:
            if not required:
                copied = _copy_graph_row(row)
                copied["roles"][to_role] = [] if mode == "collect" else None
                expanded.append(copied)
            continue
        if mode == "collect":
            copied = _copy_graph_row(row)
            copied["roles"][to_role] = _unique_nodes(
                node for _, node in selected
            )
            _extend_evidence(copied, selected)
            expanded.append(copied)
        else:
            for edge, node in selected:
                copied = _copy_graph_row(row)
                copied["roles"][to_role] = node
                _extend_evidence(copied, [(edge, node)])
                expanded.append(copied)
    state.relation = expanded[: state.candidate_limit]
    state.relation_kind = "graph_rows"


def project_graph_binding(state: Any, operation: dict[str, Any]) -> None:
    _expect(state, "graph_rows", operation)
    fact_roles = [str(value) for value in operation.get("fact_roles") or []]
    if not fact_roles:
        raise ValueError("project_graph_binding requires fact_roles")
    all_fact_ids = sorted(
        {
            str(node.get("source_pk"))
            for row in state.relation
            for role in fact_roles
            for node in _role_nodes(row, role)
            if node.get("source_pk")
        }
    )
    fact_map, metrics = _load_facts(state, all_fact_ids)
    state.facts = list(fact_map.values())
    state.metrics = metrics

    answer_spec = dict(operation.get("answer") or {})
    answer_binding = str(answer_spec.get("binding") or "graph_answer")
    candidates: list[dict[str, Any]] = []
    for row in state.relation:
        fact_ids = sorted(
            {
                str(node.get("source_pk"))
                for role in fact_roles
                for node in _role_nodes(row, role)
                if node.get("source_pk")
            }
        )
        if not fact_ids or any(fact_id not in fact_map for fact_id in fact_ids):
            continue
        facts = [fact_map[fact_id] for fact_id in fact_ids]
        answer = _project_answer(row, answer_spec)
        if not answer:
            continue
        entity_ids = sorted(
            {str(fact["entity_id"]) for fact in facts if fact.get("entity_id")}
            | _source_pks(row, operation.get("entity_roles") or [])
        )
        metric_ids = sorted(
            {str(fact["metric_id"]) for fact in facts if fact.get("metric_id")}
            | _source_pks(row, operation.get("metric_roles") or [])
        )
        input_bindings = {
            "facts": fact_ids,
            answer_binding: {LITERAL_BINDING_KEY: answer},
        }
        first = facts[0]
        binding = {
            "input_bindings": input_bindings,
            "fact_ids": fact_ids,
            "entity_ids": entity_ids,
            "metric_ids": metric_ids,
            "period": period_label(first),
            "frequency": fact_frequency(first),
            "scope_type": str(operation.get("scope_type") or "graph_topology"),
            "scope_definition": _role_property(
                row, operation.get("scope_role"), "scope_definition"
            ),
            "source_derived_ids": sorted(
                _source_pks(row, operation.get("derived_roles") or [])
            ),
            "source_document_ids": sorted(
                _source_pks(row, operation.get("document_roles") or [])
            ),
            "raw_object_ids": sorted(
                _source_pks(row, operation.get("raw_object_roles") or [])
            ),
            "graph_node_ids": sorted(set(row["graph_node_ids"])),
            "graph_edge_ids": sorted(
                {str(edge["edge_id"]) for edge in row["graph_edges"]}
            ),
            "graph_edges": sorted(
                row["graph_edges"],
                key=lambda edge: (
                    str(edge["relation_type"]),
                    str(edge["edge_id"]),
                ),
            ),
        }
        for field_name, projection in dict(
            operation.get("context") or {}
        ).items():
            binding[str(field_name)] = _project_value(row, projection)
        candidates.append(binding)
    state.discovered_count += len(candidates)
    state.relation = candidates[: state.candidate_limit]
    state.relation_kind = "binding_candidates"


def _project_answer(
    row: dict[str, Any],
    answer_spec: dict[str, Any],
) -> dict[str, Any]:
    role = str(answer_spec.get("role") or "")
    shape = str(answer_spec.get("shape") or "record")
    output_key = str(
        answer_spec.get("output_key")
        or ("records" if shape == "records" else "trace")
    )
    fields = dict(answer_spec.get("fields") or {})
    if shape == "composite":
        record = {
            str(name): _project_value(row, projection)
            for name, projection in fields.items()
        }
        return {output_key: record, "count": 1}
    nodes = _role_nodes(row, role)
    if not nodes:
        return {}
    records = [
        {
            str(name): _node_value(node, str(source))
            for name, source in fields.items()
        }
        for node in nodes
    ]
    records = sorted(records, key=_digest)
    value: Any = records if shape == "records" else records[0]
    return {output_key: value, "count": len(records)}


def _project_value(row: dict[str, Any], projection: Any) -> Any:
    if not isinstance(projection, dict):
        return projection
    role = str(projection.get("role") or "")
    source = str(projection.get("source") or "source_pk")
    values = [_node_value(node, source) for node in _role_nodes(row, role)]
    values = [value for value in values if value is not None]
    if projection.get("many"):
        return sorted(values, key=str)
    return values[0] if values else projection.get("default")


def _load_facts(
    state: Any,
    fact_ids: list[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    facts: dict[str, dict[str, Any]] = {}
    for batch in chunks(fact_ids, 500):
        placeholders = ",".join("?" for _ in batch)
        rows = state.db.fetchall(
            f"SELECT sf.*, ce.entity_type, ce.market, ce.country, ce.industry, "
            f"m.canonical_name AS metric_name, m.metric_category, "
            f"m.statement_type, m.period_type AS ontology_period_type, "
            f"m.aggregation_rule, m.revision_risk "
            f"FROM standardized_facts sf "
            f"JOIN canonical_entities ce ON ce.build_id = ? "
            f"AND ce.entity_id = sf.entity_id "
            f"JOIN metrics m ON m.build_id = ? AND m.metric_id = sf.metric_id "
            f"WHERE sf.build_id = ? AND sf.fact_id IN ({placeholders}) "
            "AND COALESCE(sf.graph_ready, FALSE) = TRUE "
            "AND COALESCE(sf.is_forecast, FALSE) = FALSE",
            [
                state.kg["input_entity_build_id"],
                state.kg["input_metric_build_id"],
                state.kg["input_fact_build_id"],
                *batch,
            ],
        )
        for raw in rows:
            fact = dict(raw)
            fact["graph_ready"] = bool(fact.get("graph_ready"))
            facts[str(fact["fact_id"])] = fact
    metric_ids = sorted(
        {str(fact["metric_id"]) for fact in facts.values() if fact.get("metric_id")}
    )
    metrics: dict[str, dict[str, Any]] = {}
    for batch in chunks(metric_ids, 500):
        placeholders = ",".join("?" for _ in batch)
        rows = state.db.fetchall(
            f"SELECT * FROM metrics WHERE build_id = ? "
            f"AND metric_id IN ({placeholders})",
            [state.kg["input_metric_build_id"], *batch],
        )
        metrics.update({str(row["metric_id"]): dict(row) for row in rows})
    return facts, metrics


def _node(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": str(row["node_id"]),
        "stable_node_id": str(row.get("stable_node_id") or ""),
        "node_type": str(row["node_type"]),
        "source_table": str(row.get("source_table") or ""),
        "source_pk": (
            str(row["source_pk"]) if row.get("source_pk") is not None else None
        ),
        "properties": json_value(row.get("properties_json"), {}),
    }


def _node_value(node: dict[str, Any], source: str) -> Any:
    if source.startswith("properties."):
        value: Any = node.get("properties") or {}
        for part in source.split(".")[1:]:
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value
    return node.get(source)


def _role_nodes(row: dict[str, Any], role: str) -> list[dict[str, Any]]:
    value = row.get("roles", {}).get(role)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return [value] if isinstance(value, dict) else []


def _role_property(
    row: dict[str, Any], role: Any, property_name: str
) -> Any:
    if not role:
        return None
    nodes = _role_nodes(row, str(role))
    return (
        (nodes[0].get("properties") or {}).get(property_name) if nodes else None
    )


def _source_pks(row: dict[str, Any], roles: Any) -> set[str]:
    return {
        str(node["source_pk"])
        for role in roles
        for node in _role_nodes(row, str(role))
        if node.get("source_pk")
    }


def _copy_graph_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "roles": dict(row["roles"]),
        "graph_node_ids": list(row["graph_node_ids"]),
        "graph_edges": list(row["graph_edges"]),
    }


def _extend_evidence(
    row: dict[str, Any],
    selected: list[tuple[dict[str, Any], dict[str, Any]]],
) -> None:
    row["graph_edges"].extend(edge for edge, _ in selected)
    row["graph_node_ids"].extend(str(node["node_id"]) for _, node in selected)


def _unique_nodes(nodes: Any) -> list[dict[str, Any]]:
    by_id = {str(node["node_id"]): node for node in nodes}
    return [by_id[node_id] for node_id in sorted(by_id)]


def _required_text(operation: dict[str, Any], field: str) -> str:
    value = str(operation.get(field) or "")
    if not value:
        raise ValueError(f"{operation.get('op')} requires {field}")
    return value


def _expect(state: Any, expected: str, operation: dict[str, Any]) -> None:
    if state.relation_kind != expected:
        raise ValueError(
            f"{operation['op']} expected {expected}, found {state.relation_kind}"
        )


def _digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
