from __future__ import annotations

from pathlib import Path

import pytest

from finraw.analysis.schema import ensure_analysis_schema
from finraw.db.client import MetadataDB
from finraw.qa.schema import ensure_qa_schema
from finraw.qa_cleanup import (
    PURGE_CONFIRMATION,
    default_qa_artifact_paths,
    plan_qa_history_cleanup,
    purge_qa_history,
)


def _db(tmp_path: Path) -> MetadataDB:
    db = MetadataDB(str(tmp_path / "metadata.sqlite3"))
    db.init_schema()
    ensure_qa_schema(db)
    ensure_analysis_schema(db)
    db.seed_sources()
    db.execute(
        """
        INSERT INTO qa_builds (
            qa_build_id, kg_build_id, graph_schema_version, status, is_active
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ("qa_old", "kg_active", "3.0", "ready", True),
    )
    db.execute(
        """
        INSERT INTO qa_archives (
            archive_id, qa_build_id, archive_uri, archive_format, status
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ("archive_old", "qa_old", "/tmp/archive", "parquet", "verified"),
    )
    db.execute(
        """
        INSERT INTO qa_pattern_mining_runs (
            mining_run_id, kg_build_id, mining_version, config_hash, status,
            lifecycle_events, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("mining_old", "kg_active", "1", "hash", "success", "[]", "{}"),
    )
    db.execute(
        """
        INSERT INTO qa_templates (
            template_id, task_family, language, template_text,
            required_slots, answer_type, difficulty_base
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("template_old", "lookup", "en", "Question", "[]", "numeric", "easy"),
    )
    db.execute(
        """
        INSERT INTO analysis_builds (
            analysis_build_id, kg_build_id, graph_schema_version,
            fact_build_id, entity_build_id, metric_build_id,
            signal_registry_manifest_hash, analysis_pattern_manifest_hash,
            claim_schema_manifest_hash, conclusion_policy_manifest_hash,
            analysis_verifier_manifest_hash, config_hash, status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "analysis_old",
            "kg_active",
            "3.0",
            "fact_active",
            "entity_active",
            "metric_active",
            "signal_hash",
            "pattern_hash",
            "claim_hash",
            "conclusion_hash",
            "verifier_hash",
            "config_hash",
            "ready",
            "{}",
        ),
    )
    return db


def test_qa_history_cleanup_requires_confirmation_and_preserves_upstream(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    project_root = tmp_path / "project"
    export = project_root / "data" / "qa_exports" / "qa_old"
    export.mkdir(parents=True)
    (export / "sample.jsonl").write_text("{}\n", encoding="utf-8")
    try:
        plan = plan_qa_history_cleanup(db, artifact_paths=[export.parent])
        assert plan["row_count"] == 5
        assert plan["artifact_file_count"] == 1

        with pytest.raises(ValueError, match=PURGE_CONFIRMATION):
            purge_qa_history(
                db,
                project_root=project_root,
                artifact_paths=[export.parent],
                execute=True,
            )
        assert db.fetchone("SELECT COUNT(*) AS count FROM qa_builds")["count"] == 1

        report = purge_qa_history(
            db,
            project_root=project_root,
            artifact_paths=[export.parent],
            execute=True,
            confirmation=PURGE_CONFIRMATION,
            output_dir=project_root / "data" / "audit" / "cleanup",
        )
        assert report["status"] == "completed"
        assert report["after"]["row_count"] == 0
        assert not export.parent.exists()
        assert db.fetchone("SELECT COUNT(*) AS count FROM source_registry")["count"] > 0
        assert (project_root / "data" / "audit" / "cleanup" / "qa_history_cleanup_result.json").exists()
    finally:
        db.close()


def test_default_artifacts_keep_qa_ready_and_explicit_report(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    audit = project_root / "data" / "audit"
    old_qa = audit / "qa_build_old"
    qa_ready = audit / "qa_ready_v3"
    report = audit / "qa_history_cleanup"
    for path in (old_qa, qa_ready, report):
        path.mkdir(parents=True)
        (path / "report.json").write_text("{}", encoding="utf-8")

    paths = default_qa_artifact_paths(project_root, exclude_paths=[report])
    assert old_qa.resolve() in paths
    assert qa_ready.resolve() not in paths
    assert report.resolve() not in paths
