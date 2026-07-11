from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from finraw.db.client import MetadataDB
from finraw.kg_builder import ensure_kg_schema
from finraw.kg_retention import enforce_kg_retention, ensure_kg_retention_schema, plan_kg_retention


def _db(tmp_path: Path) -> MetadataDB:
    db = MetadataDB(str(tmp_path / "metadata.sqlite3"))
    db.init_schema()
    ensure_kg_schema(db)
    ensure_kg_retention_schema(db)
    return db


def _insert_build(db: MetadataDB, build_id: str, active: int, completed_at: str) -> None:
    db.execute(
        """
        INSERT INTO kg_builds (
            kg_build_id, graph_schema_version, status, quality_status,
            is_active, started_at, completed_at, node_count, edge_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [build_id, "3.0", "success", "passed", active, completed_at, completed_at, 2, 1],
    )
    for suffix, node_type in [("entity", "Entity"), ("metric", "Metric")]:
        db.execute(
            """
            INSERT INTO kg_nodes (
                node_id, stable_node_id, kg_build_id, node_type,
                source_table, source_pk, properties_json, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                f"{suffix}:{build_id}@@{build_id}",
                f"{suffix}:{build_id}",
                build_id,
                node_type,
                "test",
                suffix,
                "{}",
                1,
            ],
        )
    db.execute(
        """
        INSERT INTO kg_edges (
            edge_id, stable_edge_id, kg_build_id, src_node_id, dst_node_id,
            relation_type, source_table, source_pk, properties_json, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            f"edge:{build_id}",
            f"edge:{build_id}",
            build_id,
            f"entity:{build_id}@@{build_id}",
            f"metric:{build_id}@@{build_id}",
            "TEST_RELATION",
            "test",
            "edge",
            "{}",
            1,
        ],
    )


def test_retention_archives_before_purge(tmp_path: Path) -> None:
    db = _db(tmp_path)
    try:
        _insert_build(db, "kg_old", 0, "2026-01-01")
        _insert_build(db, "kg_active", 1, "2026-01-02")

        plan = plan_kg_retention(db, hot_build_count=1)
        assert plan["hot_build_ids"] == ["kg_active"]
        assert [row["kg_build_id"] for row in plan["archive_candidates"]] == ["kg_old"]

        report = enforce_kg_retention(
            db,
            str(tmp_path / "archive"),
            hot_build_count=1,
            execute=True,
            purge=True,
            output_dir=str(tmp_path / "audit"),
            batch_size=1,
        )
        assert report["purged_build_ids"] == ["kg_old"]
        archive = report["archives"][0]
        assert pq.read_metadata(archive["files"]["kg_nodes"]["path"]).num_rows == 2
        assert pq.read_metadata(archive["files"]["kg_edges"]["path"]).num_rows == 1
        assert db.fetchone(
            "SELECT COUNT(*) AS count FROM kg_nodes WHERE kg_build_id = ?",
            ["kg_old"],
        )["count"] == 0
        assert db.fetchone(
            "SELECT COUNT(*) AS count FROM kg_nodes WHERE kg_build_id = ?",
            ["kg_active"],
        )["count"] == 2
        archive_row = dict(db.fetchone("SELECT * FROM kg_archives WHERE kg_build_id = ?", ["kg_old"]))
        assert archive_row["status"] == "purged"
        assert Path(archive_row["archive_uri"], "manifest.json").exists()
    finally:
        db.close()


def test_retention_is_dry_run_by_default(tmp_path: Path) -> None:
    db = _db(tmp_path)
    try:
        _insert_build(db, "kg_old", 0, "2026-01-01")
        _insert_build(db, "kg_active", 1, "2026-01-02")
        report = enforce_kg_retention(
            db,
            str(tmp_path / "archive"),
            hot_build_count=1,
        )
        assert report["execute"] is False
        assert db.fetchone(
            "SELECT COUNT(*) AS count FROM kg_nodes WHERE kg_build_id = ?",
            ["kg_old"],
        )["count"] == 2
        assert not (tmp_path / "archive").exists()
    finally:
        db.close()
