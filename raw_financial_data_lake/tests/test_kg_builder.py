from __future__ import annotations

import json

import pytest

from finraw.db.client import MetadataDB
from finraw.kg_builder import (
    KG_SCHEMA_VERSION,
    _activate_kg_build,
    _dangling_edge_count,
    _derived_time_node,
    _invalid_relation_endpoint_count,
    _invalidate_kg_build,
    _optional_active_build_id,
    _required_active_build_id,
    _time_node,
    ensure_kg_schema,
    export_kg_jsonl,
)


def _db(tmp_path):
    db = MetadataDB(str(tmp_path / "metadata.sqlite3"))
    db.init_schema()
    ensure_kg_schema(db)
    return db


def _insert_historical_graph(db, kg_build_id: str = "kg_test") -> None:
    db.execute(
        """
        INSERT INTO kg_builds (
            kg_build_id, graph_schema_version, status, quality_status,
            is_active, started_at, completed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [kg_build_id, KG_SCHEMA_VERSION, "success", "passed", 0, "2026-01-01", "2026-01-01"],
    )
    for node_id, stable_id, node_type in [
        ("entity:one@@kg_test", "entity:one", "Entity"),
        ("security:one@@kg_test", "security:one", "Security"),
    ]:
        db.execute(
            """
            INSERT INTO kg_nodes (
                node_id, stable_node_id, kg_build_id, node_type,
                properties_json, is_active
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [node_id, stable_id, kg_build_id, node_type, "{}", 0],
        )
    db.execute(
        """
        INSERT INTO kg_edges (
            edge_id, stable_edge_id, kg_build_id, src_node_id, dst_node_id,
            relation_type, properties_json, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "edge:one@@kg_test",
            "edge:one",
            kg_build_id,
            "entity:one@@kg_test",
            "security:one@@kg_test",
            "HAS_SECURITY",
            "{}",
            0,
        ],
    )


def test_time_nodes_are_canonical() -> None:
    scope_a = {"year": 2024, "basis": "calendar_year", "previous_year": 2023}
    scope_b = {"previous_year": 2023, "basis": "calendar_year", "year": 2024}
    assert _derived_time_node(scope_a) == _derived_time_node(scope_b)

    row_a = {
        "time_basis": "fiscal_year",
        "metric_period_type": "period_flow",
        "period_start": "2023-01-01",
        "period_end": "2023-12-31",
        "fiscal_year": 2023,
        "report_date": "2024-01-20",
    }
    row_b = {**row_a, "report_date": "2024-02-01"}
    assert _time_node(row_a) == _time_node(row_b)


def test_active_build_selection_rejects_mixed_builds(tmp_path) -> None:
    db = _db(tmp_path)
    try:
        db.execute(
            "INSERT INTO metrics (metric_id, canonical_name, build_id, is_active) VALUES (?, ?, ?, ?)",
            ["metric_a", "Metric A", "build_a", 1],
        )
        db.execute(
            "INSERT INTO metrics (metric_id, canonical_name, build_id, is_active) VALUES (?, ?, ?, ?)",
            ["metric_b", "Metric B", "build_b", 1],
        )
        with pytest.raises(RuntimeError, match="exactly one active build"):
            _required_active_build_id(db, "metrics")
        assert _optional_active_build_id(db, "source_documents") is None
    finally:
        db.close()


def test_historical_export_includes_inactive_rows(tmp_path) -> None:
    db = _db(tmp_path)
    try:
        _insert_historical_graph(db)
        paths = export_kg_jsonl(db, str(tmp_path / "export"), kg_build_id="kg_test")
        nodes = [json.loads(line) for line in paths[0].read_text().splitlines()]
        edges = [json.loads(line) for line in paths[1].read_text().splitlines()]
        assert len(nodes) == 2
        assert len(edges) == 1
        assert {node["node_type"] for node in nodes} == {"Entity", "Security"}
    finally:
        db.close()


def test_integrity_helpers_detect_bad_edges(tmp_path) -> None:
    db = _db(tmp_path)
    try:
        _insert_historical_graph(db)
        db.execute(
            """
            INSERT INTO kg_edges (
                edge_id, stable_edge_id, kg_build_id, src_node_id, dst_node_id,
                relation_type, properties_json, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "edge:bad@@kg_test",
                "edge:bad",
                "kg_test",
                "entity:one@@kg_test",
                "missing@@kg_test",
                "HAS_SECURITY",
                "{}",
                0,
            ],
        )
        assert _dangling_edge_count(db, "kg_test", incoming=True) == 1
        db.execute(
            "UPDATE kg_edges SET dst_node_id = ? WHERE edge_id = ?",
            ["entity:one@@kg_test", "edge:bad@@kg_test"],
        )
        assert _invalid_relation_endpoint_count(db, "kg_test") == 1
    finally:
        db.close()


def test_activation_switches_build_pointer_only(tmp_path) -> None:
    db = _db(tmp_path)
    try:
        for build_id, is_active in [("kg_old", 1), ("kg_new", 0)]:
            db.execute(
                """
                INSERT INTO kg_builds (
                    kg_build_id, graph_schema_version, status, quality_status,
                    is_active, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    build_id,
                    KG_SCHEMA_VERSION,
                    "success",
                    "passed",
                    is_active,
                    "2026-01-01",
                    "2026-01-01",
                ],
            )
        db.execute(
            """
            INSERT INTO kg_nodes (
                node_id, stable_node_id, kg_build_id, node_type,
                properties_json, is_active
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ["entity:old@@kg_old", "entity:old", "kg_old", "Entity", "{}", 1],
        )

        _activate_kg_build(db, "kg_new")

        old_build = dict(db.fetchone("SELECT * FROM kg_builds WHERE kg_build_id = ?", ["kg_old"]))
        new_build = dict(db.fetchone("SELECT * FROM kg_builds WHERE kg_build_id = ?", ["kg_new"]))
        old_node = dict(db.fetchone("SELECT * FROM kg_nodes WHERE node_id = ?", ["entity:old@@kg_old"]))
        assert old_build["is_active"] == 0
        assert old_build["superseded_by"] == "kg_new"
        assert new_build["is_active"] == 1
        assert old_node["is_active"] == 1

        _invalidate_kg_build(db, "kg_old")
        invalidated_node = dict(
            db.fetchone("SELECT * FROM kg_nodes WHERE node_id = ?", ["entity:old@@kg_old"])
        )
        assert invalidated_node["is_active"] == 0
    finally:
        db.close()
