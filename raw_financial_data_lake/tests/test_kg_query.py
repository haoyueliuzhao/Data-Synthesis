from __future__ import annotations

import pytest

from finraw.db.client import MetadataDB
from finraw.kg_builder import ensure_kg_schema
from finraw.kg_query import query_neighbors, resolve_kg_build_id


def test_neighbor_query_uses_active_build_and_stable_ids(tmp_path) -> None:
    db = MetadataDB(str(tmp_path / "metadata.sqlite3"))
    db.init_schema()
    ensure_kg_schema(db)
    try:
        db.execute(
            """
            INSERT INTO kg_builds (
                kg_build_id, graph_schema_version, status, quality_status,
                is_active, started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ["kg_query", "3.0", "success", "passed", 1, "2026-01-01", "2026-01-01"],
        )
        for node_id, stable_id, node_type in [
            ("entity:A@@kg_query", "entity:A", "Entity"),
            ("fact:F@@kg_query", "fact:F", "Fact"),
        ]:
            db.execute(
                """
                INSERT INTO kg_nodes (
                    node_id, stable_node_id, kg_build_id, node_type,
                    properties_json, is_active
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [node_id, stable_id, "kg_query", node_type, "{}", 1],
            )
        db.execute(
            """
            INSERT INTO kg_edges (
                edge_id, stable_edge_id, kg_build_id, src_node_id, dst_node_id,
                relation_type, properties_json, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "edge:E@@kg_query",
                "edge:E",
                "kg_query",
                "entity:A@@kg_query",
                "fact:F@@kg_query",
                "HAS_FACT",
                "{}",
                1,
            ],
        )

        assert resolve_kg_build_id(db) == "kg_query"
        result = query_neighbors(db, "entity:A", direction="out")
        assert result["count"] == 1
        assert result["edges"][0]["dst_stable_node_id"] == "fact:F"
    finally:
        db.close()


def test_neighbor_query_validates_limit(tmp_path) -> None:
    db = MetadataDB(str(tmp_path / "metadata.sqlite3"))
    db.init_schema()
    ensure_kg_schema(db)
    try:
        with pytest.raises(ValueError, match="between 1 and 1000"):
            query_neighbors(db, "entity:A", kg_build_id="missing", limit=1001)
    finally:
        db.close()
