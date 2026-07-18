from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from finraw.db.client import MetadataDB
from finraw.qa.schema import ensure_qa_schema
from finraw.qa_retention import (
    enforce_qa_retention,
    ensure_qa_retention_schema,
    plan_qa_retention,
)


def _db(tmp_path: Path) -> MetadataDB:
    db = MetadataDB(str(tmp_path / "metadata.sqlite3"))
    db.init_schema()
    ensure_qa_schema(db)
    ensure_qa_retention_schema(db)
    return db


def _insert_build(
    db: MetadataDB,
    build_id: str,
    *,
    active: int,
    completed_at: str,
    sample_count: int = 1,
) -> None:
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
            "ready",
            "passed",
            active,
            completed_at,
            completed_at,
            sample_count,
            sample_count,
            sample_count,
        ],
    )
    for index in range(sample_count):
        candidate_id = f"candidate_{build_id}_{index}"
        qa_id = f"qa_{build_id}_{index}"
        db.execute(
            """
            INSERT INTO qa_candidates (
                candidate_id, stable_candidate_id, qa_build_id,
                task_family, task_subtype, difficulty,
                entity_ids, metric_ids, time_scope, entity_scope,
                source_fact_ids, source_derived_ids, source_document_ids,
                raw_object_ids, canonical_semantics, derived_payload,
                recomputed_payload, answer_payload, kg_path,
                eligibility_status, rejection_reasons
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                candidate_id,
                f"stable_{index}",
                build_id,
                "test",
                "single_fact",
                "easy",
                "[]",
                "[]",
                "{}",
                "{}",
                "[]",
                "[]",
                "[]",
                "[]",
                "{}",
                "{}",
                "{}",
                "{}",
                "{}",
                "eligible",
                "[]",
            ],
        )
        db.execute(
            """
            INSERT INTO qa_samples (
                qa_id, stable_qa_id, qa_group_id, semantic_cluster_id,
                qa_build_id, candidate_id, task_family, task_subtype,
                difficulty, language, question, canonical_question,
                answer_type, answer_value, answer_text, rubric,
                source_metadata, generation_method, validation_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                qa_id,
                f"stable_qa_{index}",
                f"group_{index}",
                f"cluster_{index}",
                build_id,
                candidate_id,
                "test",
                "single_fact",
                "easy",
                "en",
                "Question?",
                "Question?",
                "numeric",
                "{}",
                "1",
                "{}",
                "{}",
                "controlled_template",
                "passed",
            ],
        )
        db.execute(
            """
            INSERT INTO qa_evidence_paths (
                path_id, qa_id, path_type, ordered_node_ids,
                ordered_edge_ids, evidence_node_ids, evidence_edges,
                evidence_components, source_fact_ids, source_derived_ids,
                raw_object_ids, source_document_ids
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                f"path_{build_id}_{index}",
                qa_id,
                "subgraph",
                "[]",
                "[]",
                "[]",
                "[]",
                "[]",
                "[]",
                "[]",
                "[]",
                "[]",
            ],
        )
        db.execute(
            """
            INSERT INTO qa_quality_checks (
                check_id, qa_id, qa_build_id, check_name, check_status
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [f"check_{build_id}_{index}", qa_id, build_id, "test", "passed"],
        )


def test_qa_retention_archives_before_purge(tmp_path: Path) -> None:
    db = _db(tmp_path)
    try:
        _insert_build(db, "qa_old", active=0, completed_at="2026-01-01", sample_count=1)
        _insert_build(
            db, "qa_active", active=1, completed_at="2026-01-02", sample_count=2
        )

        plan = plan_qa_retention(db, hot_build_count=0, minimum_hot_sample_count=1)
        assert plan["hot_build_ids"] == ["qa_active"]
        assert [row["qa_build_id"] for row in plan["archive_candidates"]] == ["qa_old"]

        report = enforce_qa_retention(
            db,
            str(tmp_path / "archive"),
            hot_build_count=0,
            minimum_hot_sample_count=1,
            execute=True,
            purge=True,
            output_dir=str(tmp_path / "audit"),
            batch_size=1,
        )
        assert report["purged_build_ids"] == ["qa_old"]
        archive = report["archives"][0]
        assert pq.read_metadata(archive["files"]["qa_candidates"]["path"]).num_rows == 1
        assert (
            pq.read_metadata(archive["files"]["qa_evidence_paths"]["path"]).num_rows
            == 1
        )
        assert (
            db.fetchone(
                "SELECT COUNT(*) AS count FROM qa_candidates WHERE qa_build_id = ?",
                ["qa_old"],
            )["count"]
            == 0
        )
        assert (
            db.fetchone(
                "SELECT COUNT(*) AS count FROM qa_candidates WHERE qa_build_id = ?",
                ["qa_active"],
            )["count"]
            == 2
        )
        archived_build = db.fetchone(
            "SELECT status, is_active FROM qa_builds WHERE qa_build_id = ?",
            ["qa_old"],
        )
        assert archived_build["status"] == "archived"
        assert not archived_build["is_active"]
    finally:
        db.close()


def test_qa_retention_dry_run_and_minimum_sample_policy(tmp_path: Path) -> None:
    db = _db(tmp_path)
    try:
        _insert_build(
            db, "qa_large", active=0, completed_at="2026-01-01", sample_count=2
        )
        _insert_build(
            db, "qa_smoke", active=0, completed_at="2026-01-02", sample_count=1
        )
        plan = plan_qa_retention(db, hot_build_count=1, minimum_hot_sample_count=2)
        assert plan["hot_build_ids"] == ["qa_large"]
        assert [row["qa_build_id"] for row in plan["archive_candidates"]] == [
            "qa_smoke"
        ]

        report = enforce_qa_retention(
            db,
            str(tmp_path / "archive"),
            hot_build_count=1,
            minimum_hot_sample_count=2,
        )
        assert report["execute"] is False
        assert db.fetchone("SELECT COUNT(*) AS count FROM qa_candidates")["count"] == 3
        assert not (tmp_path / "archive").exists()
    finally:
        db.close()
