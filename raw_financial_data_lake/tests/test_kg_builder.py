from __future__ import annotations

import json

import pytest

from finraw.db.client import MetadataDB
from finraw.kg_builder import (
    KG_SCHEMA_VERSION,
    _apply_kg_activation_policy,
    _activate_kg_build,
    _add_time_hierarchy,
    _dangling_edge_count,
    _derived_time_node,
    _eligible_derived_rows,
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


def test_fact_universe_keeps_only_closed_derived_fact_inputs(tmp_path) -> None:
    db = _db(tmp_path)
    try:
        for derived_id, input_fact_ids in [
            ("derived_closed", ["fact_a", "fact_b"]),
            ("derived_open", ["fact_a", "fact_c"]),
            ("derived_empty", []),
        ]:
            db.execute(
                "INSERT INTO derived_facts ("
                "derived_id, build_id, input_build_id, derived_type, "
                "input_fact_ids, verification_status, is_active"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    derived_id,
                    "derived_build",
                    "fact_build",
                    "difference",
                    json.dumps(input_fact_ids),
                    "single_source",
                    1,
                ],
            )

        rows = _eligible_derived_rows(
            db,
            "derived_build",
            "fact_build",
            selected_fact_ids={"fact_a", "fact_b"},
        )

        assert [row["derived_id"] for row in rows] == ["derived_closed"]
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


def test_nonactivating_validation_build_preserves_active_pointer(tmp_path) -> None:
    db = _db(tmp_path)
    try:
        for build_id, is_active in [("kg_active", 1), ("kg_validation", 0)]:
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

        _apply_kg_activation_policy(
            db,
            "kg_validation",
            quality_status="passed",
            activate=False,
        )

        active = db.fetchall(
            "SELECT kg_build_id FROM kg_builds WHERE is_active = 1"
        )
        validation = db.fetchone(
            "SELECT is_active, superseded_by FROM kg_builds "
            "WHERE kg_build_id = ?",
            ("kg_validation",),
        )
        assert [row["kg_build_id"] for row in active] == ["kg_active"]
        assert validation["is_active"] == 0
        assert validation["superseded_by"] is None
    finally:
        db.close()


def test_time_hierarchy_links_calendar_and_fiscal_dimensions() -> None:
    nodes = {}
    edges = []

    def add_node(stable_id, node_type, source_table, source_pk, properties):
        nodes[stable_id] = (node_type, properties)

    def add_edge(src, relation, dst, source_table, source_pk, properties=None):
        edges.append((src, relation, dst))

    _add_time_hierarchy(
        add_node,
        add_edge,
        "time:test",
        {
            "time_basis": "observation_date",
            "frequency": "monthly",
            "period_end": "2024-05-31",
            "calendar_year": 2024,
            "fiscal_year": 2024,
            "fiscal_quarter": "Q2",
        },
        "AAPL_US",
    )

    assert nodes["calendar_year:2024"][0] == "CalendarYear"
    assert nodes["calendar_month:2024-05"][0] == "CalendarMonth"
    assert nodes["calendar_quarter:2024:Q2"][0] == "CalendarQuarter"
    assert nodes["fiscal_year:AAPL_US:2024"][0] == "FiscalYear"
    assert ("time:test", "BELONGS_TO_YEAR", "calendar_year:2024") in edges
    assert ("time:test", "BELONGS_TO_MONTH", "calendar_month:2024-05") in edges
    assert ("time:test", "BELONGS_TO_QUARTER", "calendar_quarter:2024:Q2") in edges
    assert ("time:test", "IN_FISCAL_YEAR", "fiscal_year:AAPL_US:2024") in edges
    assert ("fiscal_year:AAPL_US:2024", "FISCAL_YEAR_OF", "entity:AAPL_US") in edges
