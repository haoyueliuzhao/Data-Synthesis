from __future__ import annotations

import json
from typing import Any

from finraw.db.client import DBProtocol


def resolve_kg_build_id(db: DBProtocol, kg_build_id: str | None = None) -> str:
    if kg_build_id:
        row = db.fetchone("SELECT kg_build_id FROM kg_builds WHERE kg_build_id = ?", (kg_build_id,))
    else:
        row = db.fetchone(
            "SELECT kg_build_id FROM kg_builds WHERE COALESCE(is_active, 1) = 1 "
            "ORDER BY completed_at DESC, started_at DESC LIMIT 1"
        )
    if not row:
        raise RuntimeError("No matching KG build")
    return str(dict(row)["kg_build_id"])


def query_neighbors(
    db: DBProtocol,
    node_id: str,
    *,
    kg_build_id: str | None = None,
    direction: str = "both",
    relation_type: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    limit = _validated_limit(limit)
    build_id = resolve_kg_build_id(db, kg_build_id)
    node = _resolve_node(db, build_id, node_id)
    versioned_node_id = node["node_id"]
    if direction not in {"in", "out", "both"}:
        raise ValueError("direction must be in, out, or both")

    predicates = []
    params: list[Any] = [build_id]
    if direction in {"out", "both"}:
        predicates.append("e.src_node_id = ?")
        params.append(versioned_node_id)
    if direction in {"in", "both"}:
        predicates.append("e.dst_node_id = ?")
        params.append(versioned_node_id)
    relation_clause = ""
    if relation_type:
        relation_clause = " AND e.relation_type = ?"
        params.append(relation_type)
    params.append(limit)
    rows = db.fetchall(
        f"""
        SELECT e.*,
               src.stable_node_id AS src_stable_node_id,
               src.node_type AS src_node_type,
               src.properties_json AS src_properties_json,
               dst.stable_node_id AS dst_stable_node_id,
               dst.node_type AS dst_node_type,
               dst.properties_json AS dst_properties_json
        FROM kg_edges e
        JOIN kg_nodes src ON src.node_id = e.src_node_id AND src.kg_build_id = e.kg_build_id
        JOIN kg_nodes dst ON dst.node_id = e.dst_node_id AND dst.kg_build_id = e.kg_build_id
        WHERE e.kg_build_id = ? AND ({' OR '.join(predicates)})
        {relation_clause}
        ORDER BY e.relation_type, e.edge_id
        LIMIT ?
        """,
        params,
    )
    edges = []
    for row in rows:
        item = dict(row)
        item["properties"] = _json_value(item.pop("properties_json", None))
        item["src_properties"] = _json_value(item.pop("src_properties_json", None))
        item["dst_properties"] = _json_value(item.pop("dst_properties_json", None))
        edges.append(item)
    return {
        "kg_build_id": build_id,
        "node": _decode_node(node),
        "direction": direction,
        "relation_type": relation_type,
        "count": len(edges),
        "edges": edges,
    }


def query_facts(
    db: DBProtocol,
    *,
    entity_id: str | None = None,
    metric_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    source_id: str | None = None,
    kg_build_id: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    limit = _validated_limit(limit)
    build_id = resolve_kg_build_id(db, kg_build_id)
    build = dict(db.fetchone("SELECT * FROM kg_builds WHERE kg_build_id = ?", (build_id,)))
    fact_build_id = build.get("input_fact_build_id")
    predicates = [
        "sf.build_id = ?",
        "COALESCE(sf.graph_ready, 0) = 1",
        "sf.verification_status IN ('single_source', 'cross_verified')",
    ]
    params: list[Any] = [fact_build_id]
    for column, value in [
        ("sf.entity_id", entity_id),
        ("sf.metric_id", metric_id),
        ("sf.source_id", source_id),
    ]:
        if value:
            predicates.append(f"{column} = ?")
            params.append(value)
    if date_from:
        predicates.append("sf.period_end >= ?")
        params.append(date_from)
    if date_to:
        predicates.append("sf.period_end <= ?")
        params.append(date_to)
    params.append(limit)
    rows = db.fetchall(
        f"""
        SELECT sf.*, ce.canonical_name AS entity_name, m.canonical_name AS metric_name,
               ro.original_url, ro.storage_uri, ro.content_sha256
        FROM standardized_facts sf
        LEFT JOIN canonical_entities ce ON ce.entity_id = sf.entity_id
        LEFT JOIN metrics m ON m.metric_id = sf.metric_id
        LEFT JOIN raw_objects ro ON ro.raw_object_id = sf.raw_object_id
        WHERE {' AND '.join(predicates)}
        ORDER BY sf.period_end DESC, sf.entity_id, sf.metric_id, sf.fact_id
        LIMIT ?
        """,
        params,
    )
    return {
        "kg_build_id": build_id,
        "input_fact_build_id": fact_build_id,
        "filters": {
            "entity_id": entity_id,
            "metric_id": metric_id,
            "date_from": date_from,
            "date_to": date_to,
            "source_id": source_id,
        },
        "count": len(rows),
        "facts": [_decode_json_columns(dict(row)) for row in rows],
    }


def query_derived_facts(
    db: DBProtocol,
    *,
    derived_type: str | None = None,
    entity_id: str | None = None,
    kg_build_id: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    limit = _validated_limit(limit)
    build_id = resolve_kg_build_id(db, kg_build_id)
    build = dict(db.fetchone("SELECT * FROM kg_builds WHERE kg_build_id = ?", (build_id,)))
    qa_build_id = build.get("input_qa_build_id")
    fact_build_id = build.get("input_fact_build_id")
    predicates = ["d.build_id = ?", "d.input_build_id = ?"]
    params: list[Any] = [qa_build_id, fact_build_id]
    joins = ""
    if derived_type:
        predicates.append("d.derived_type = ?")
        params.append(derived_type)
    if entity_id:
        entity_node = _resolve_node(db, build_id, f"entity:{entity_id}")
        joins = """
            JOIN kg_nodes dn ON dn.source_pk = d.derived_id
              AND dn.kg_build_id = ? AND dn.node_type = 'DerivedFact'
            JOIN kg_edges about ON about.src_node_id = dn.node_id
              AND about.kg_build_id = dn.kg_build_id
              AND about.relation_type = 'ABOUT_ENTITY'
        """
        params = [build_id, *params]
        predicates.append("about.dst_node_id = ?")
        params.append(entity_node["node_id"])
    params.append(limit)
    rows = db.fetchall(
        f"""
        SELECT d.*
        FROM derived_facts d
        {joins}
        WHERE {' AND '.join(predicates)}
        ORDER BY d.derived_type, d.derived_id
        LIMIT ?
        """,
        params,
    )
    return {
        "kg_build_id": build_id,
        "input_qa_build_id": qa_build_id,
        "filters": {"derived_type": derived_type, "entity_id": entity_id},
        "count": len(rows),
        "derived_facts": [_decode_json_columns(dict(row)) for row in rows],
    }


def _resolve_node(db: DBProtocol, kg_build_id: str, node_id: str) -> dict[str, Any]:
    if "@@" in node_id:
        row = db.fetchone(
            "SELECT * FROM kg_nodes WHERE kg_build_id = ? AND node_id = ?",
            (kg_build_id, node_id),
        )
    else:
        row = db.fetchone(
            "SELECT * FROM kg_nodes WHERE kg_build_id = ? AND stable_node_id = ?",
            (kg_build_id, node_id),
        )
    if not row:
        raise RuntimeError(f"Node not found in {kg_build_id}: {node_id}")
    return dict(row)


def _decode_node(node: dict[str, Any]) -> dict[str, Any]:
    item = dict(node)
    item["properties"] = _json_value(item.pop("properties_json", None))
    return item


def _decode_json_columns(item: dict[str, Any]) -> dict[str, Any]:
    for key in [
        "validation_flags",
        "input_fact_ids",
        "entity_scope",
        "metric_scope",
        "time_scope",
        "scope_entity_ids",
        "output_table",
    ]:
        if key in item:
            item[key] = _json_value(item[key])
    return item


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)) or value is None:
        return value
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _validated_limit(limit: int) -> int:
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")
    return limit
