from __future__ import annotations

from finraw.coverage import build_data_coverage_report
from finraw.db.client import MetadataDB


def test_coverage_uses_active_fact_output_for_parse_readiness(tmp_path) -> None:
    db = MetadataDB(str(tmp_path / "metadata.sqlite3"))
    db.init_schema()
    try:
        _seed_source(db, "cninfo_announcements", "CN")
        _seed_raw_object(db, "cninfo_announcements")
        db.execute(
            "INSERT INTO standardized_facts ("
            "fact_id, build_id, entity_id, metric_id, normalized_value, "
            "period_end, source_id, verification_status, graph_ready, is_active"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "fact_cninfo_1",
                "fact_build_1",
                "000001_CN",
                "revenue",
                100.0,
                "2023-12-31",
                "cninfo_announcements",
                "single_source",
                1,
                1,
            ),
        )

        report = build_data_coverage_report(
            db,
            {"cninfo": {"announcements": []}},
        )
        source = _source_report(report, "cninfo_announcements")

        assert source["parse_ready"] is True
        assert source["quality_level"] == "ready_high"
        assert source["active_standardized_fact_count"] == 1
        assert source["active_graph_ready_fact_count"] == 1
        assert source["active_fact_entity_count"] == 1
        assert source["active_fact_metric_count"] == 1
        assert any(
            "active standardized facts" in note
            for note in source["coverage_notes"]
        )
    finally:
        db.close()


def test_coverage_classifies_new_raw_only_sources_instead_of_unclassified(
    tmp_path,
) -> None:
    db = MetadataDB(str(tmp_path / "metadata.sqlite3"))
    db.init_schema()
    try:
        _seed_source(db, "nbs_official_statistics", "CN")
        _seed_raw_object(db, "nbs_official_statistics")

        report = build_data_coverage_report(db, {})
        source = _source_report(report, "nbs_official_statistics")

        assert source["parse_ready"] is False
        assert source["active_standardized_fact_count"] == 0
        assert source["quality_level"] == "raw_only_high"
        assert "cn_macro_statistics" in source["data_types"]
        assert "macro_series" in source["entity_types"]
    finally:
        db.close()


def _source_report(report: dict, source_id: str) -> dict:
    return next(
        row for row in report["source_reports"] if row["source_id"] == source_id
    )


def _seed_source(db: MetadataDB, source_id: str, market: str) -> None:
    db.execute(
        "INSERT INTO source_registry ("
        "source_id, source_name, source_type, authority_level, market, is_active"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        (source_id, source_id, "api", "S1_official", market, 1),
    )


def _seed_raw_object(db: MetadataDB, source_id: str) -> None:
    db.execute(
        "INSERT INTO raw_objects ("
        "raw_object_id, source_id, object_type, storage_uri, original_url, "
        "response_status, content_sha256, content_size_bytes, "
        "validation_status"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            f"raw_{source_id}",
            source_id,
            "json",
            "/tmp/example.json",
            f"https://example.test/{source_id}",
            200,
            "sha256",
            100,
            "passed",
        ),
    )
