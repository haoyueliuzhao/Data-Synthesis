from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from finraw.artifact_retention import enforce_artifact_retention
from finraw.db.client import MetadataDB
from finraw.qa.schema import ensure_qa_schema
from finraw.qa_retention import ensure_qa_retention_schema


def _db(tmp_path: Path) -> MetadataDB:
    db = MetadataDB(str(tmp_path / "metadata.sqlite3"))
    db.init_schema()
    ensure_qa_schema(db)
    ensure_qa_retention_schema(db)
    return db


def _insert_build(db: MetadataDB, build_id: str, *, active: bool) -> None:
    db.execute(
        """
        INSERT INTO qa_builds (
            qa_build_id, kg_build_id, graph_schema_version, status,
            quality_status, is_active, started_at, completed_at,
            candidate_count, sample_count, passed_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            build_id,
            "kg_test",
            "3.0",
            "ready" if active else "archived",
            "passed",
            active,
            "2026-01-01",
            "2026-01-01",
            1,
            1,
            1,
        ],
    )


def _insert_purged_archive(db: MetadataDB, build_id: str, archive_dir: Path) -> None:
    db.execute(
        """
        INSERT INTO qa_archives (
            archive_id, qa_build_id, archive_uri, archive_format,
            compression, candidate_count, sample_count, evidence_count,
            quality_check_count, manifest_sha256, status, created_at,
            verified_at, purged_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            f"archive_{build_id}",
            build_id,
            str(archive_dir),
            "parquet",
            "zstd",
            1,
            1,
            1,
            1,
            "archive_sha",
            "purged",
            "2026-01-01",
            "2026-01-01",
            "2026-01-01",
        ],
    )


def test_artifact_retention_deletes_only_verified_cold_artifacts(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    try:
        _insert_build(db, "qa_build_active", active=True)
        _insert_build(db, "qa_build_old", active=False)
        _insert_purged_archive(db, "qa_build_old", tmp_path / "archive")

        qa_root = tmp_path / "qa_exports"
        active_export = qa_root / "qa_build_active"
        old_export = qa_root / "qa_build_old"
        active_export.mkdir(parents=True)
        old_export.mkdir(parents=True)
        (active_export / "manifest.json").write_text("active\n", encoding="utf-8")
        nested = old_export / "benchmark"
        nested.mkdir()
        (nested / "train.jsonl").write_text('{"qa_id":"old"}\n', encoding="utf-8")

        jsonl_dir = tmp_path / "jsonl"
        parquet_dir = tmp_path / "parquet"
        jsonl_dir.mkdir()
        parquet_dir.mkdir()
        rows = [{"source_id": "sec"}, {"source_id": "fred"}]
        jsonl_path = jsonl_dir / "source_registry.jsonl"
        jsonl_path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )
        parquet_path = parquet_dir / "source_registry.parquet"
        pq.write_table(pa.Table.from_pylist(rows), parquet_path)

        dry_run = enforce_artifact_retention(
            db,
            qa_export_roots=[str(qa_root)],
            metadata_jsonl_dir=str(jsonl_dir),
            metadata_parquet_dir=str(parquet_dir),
            output_dir=str(tmp_path / "audit"),
        )
        assert [row["qa_build_id"] for row in dry_run["qa_export_candidates"]] == [
            "qa_build_old"
        ]
        assert [row["qa_build_id"] for row in dry_run["qa_export_protected"]] == [
            "qa_build_active"
        ]
        assert len(dry_run["redundant_jsonl_candidates"]) == 1
        assert old_export.exists()
        assert jsonl_path.exists()

        result = enforce_artifact_retention(
            db,
            qa_export_roots=[str(qa_root)],
            metadata_jsonl_dir=str(jsonl_dir),
            metadata_parquet_dir=str(parquet_dir),
            output_dir=str(tmp_path / "audit"),
            execute=True,
        )
        assert result["released_bytes"] > 0
        assert not old_export.exists()
        assert not jsonl_path.exists()
        assert active_export.exists()
        assert parquet_path.exists()
    finally:
        db.close()


def test_artifact_retention_blocks_unarchived_and_mismatched_artifacts(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    try:
        _insert_build(db, "qa_build_unarchived", active=False)
        qa_root = tmp_path / "qa_exports"
        export = qa_root / "qa_build_unarchived"
        export.mkdir(parents=True)
        (export / "manifest.json").write_text("{}\n", encoding="utf-8")

        jsonl_dir = tmp_path / "jsonl"
        parquet_dir = tmp_path / "parquet"
        jsonl_dir.mkdir()
        parquet_dir.mkdir()
        jsonl_path = jsonl_dir / "raw_objects.jsonl"
        jsonl_path.write_text('{"id":1}\n{"id":2}\n', encoding="utf-8")
        parquet_path = parquet_dir / "raw_objects.parquet"
        pq.write_table(pa.Table.from_pylist([{"id": 1}, {"id": 3}]), parquet_path)

        report = enforce_artifact_retention(
            db,
            qa_export_roots=[str(qa_root)],
            metadata_jsonl_dir=str(jsonl_dir),
            metadata_parquet_dir=str(parquet_dir),
            output_dir=str(tmp_path / "audit"),
            execute=True,
        )
        assert report["qa_export_candidates"] == []
        assert report["redundant_jsonl_candidates"] == []
        assert report["qa_export_blocked"][0]["reason"] == "qa_build_not_cold_archived"
        assert (
            report["redundant_jsonl_blocked"][0]["verification_status"]
            == "content_mismatch"
        )
        assert export.exists()
        assert jsonl_path.exists()
        assert parquet_path.exists()
    finally:
        db.close()
