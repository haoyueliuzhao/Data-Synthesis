from __future__ import annotations

from datetime import date

from finraw.cn_financial_statements import (
    _deactivate_out_of_scope_output,
    _deactivate_superseded_output,
    _iso_date_value,
    _load_objects,
)
from finraw.db.client import MetadataDB


def test_source_publish_date_is_json_safe_and_iso_stable() -> None:
    assert _iso_date_value(date(2024, 3, 20)) == "2024-03-20"
    assert _iso_date_value("2024-03-20") == "2024-03-20"
    assert _iso_date_value(None) is None


def test_raw_object_loading_deduplicates_before_limit(tmp_path) -> None:
    db = MetadataDB(str(tmp_path / "metadata.sqlite3"))
    db.init_schema()
    db.seed_sources()
    for index in (1, 2):
        db.insert_raw_object(
            {
                "raw_object_id": f"raw_{index}",
                "source_id": "cninfo_announcements",
                "object_type": "pdf",
                "storage_uri": f"/tmp/report_{index}.pdf",
                "original_url": f"https://static.cninfo.com.cn/report_{index}.pdf",
                "content_sha256": str(index) * 64,
                "content_size_bytes": 100,
                "source_publish_date": f"2024-03-{20 + index:02d}",
                "validation_status": "passed",
            }
        )
    db.insert_raw_records(
        [
            {
                "raw_record_id": "record_1a",
                "raw_object_id": "raw_1",
                "source_id": "cninfo_announcements",
                "record_key": "000001:2023:a",
                "record_type": "cninfo_pdf_announcement",
                "record_json": {"stock_code": "000001"},
                "entity_hint": "000001",
                "metric_hint": "annual",
                "period_hint": "2023",
            },
            {
                "raw_record_id": "record_1b",
                "raw_object_id": "raw_1",
                "source_id": "cninfo_announcements",
                "record_key": "000001:2023:b",
                "record_type": "cninfo_pdf_announcement",
                "record_json": {"stock_code": "000001"},
                "entity_hint": "000001",
                "metric_hint": "annual",
                "period_hint": "2023",
            },
            {
                "raw_record_id": "record_2",
                "raw_object_id": "raw_2",
                "source_id": "cninfo_announcements",
                "record_key": "000002:2023",
                "record_type": "cninfo_pdf_announcement",
                "record_json": {"stock_code": "000002"},
                "entity_hint": "000002",
                "metric_hint": "annual",
                "period_hint": "2023",
            },
        ]
    )

    objects = _load_objects(db, ("annual",), 2)

    assert [row["raw_object_id"] for row in objects] == ["raw_1", "raw_2"]
    db.close()


def test_activation_switch_only_supersedes_prior_build(tmp_path) -> None:
    db = MetadataDB(str(tmp_path / "metadata.sqlite3"))
    db.init_schema()
    db.seed_sources()
    for raw_object_id in ("raw_target", "raw_other"):
        db.insert_raw_object(
            {
                "raw_object_id": raw_object_id,
                "source_id": "cninfo_announcements",
                "object_type": "pdf",
                "storage_uri": f"/tmp/{raw_object_id}.pdf",
                "original_url": f"https://static.cninfo.com.cn/{raw_object_id}.pdf",
                "content_sha256": raw_object_id.ljust(64, "0"),
                "content_size_bytes": 100,
                "validation_status": "passed",
            }
        )
    db.execute(
        """
        INSERT INTO candidate_facts (
            candidate_id, raw_object_id, build_id, is_active, review_status
        ) VALUES (?, ?, ?, 1, ?), (?, ?, ?, 1, ?), (?, ?, ?, 1, ?)
        """,
        [
            "old_candidate",
            "raw_target",
            "old_build",
            "cn_pdf_programmatic_verified",
            "new_candidate",
            "raw_target",
            "new_build",
            "cn_pdf_programmatic_verified",
            "other_candidate",
            "raw_other",
            "old_build",
            "cn_pdf_programmatic_verified",
        ],
    )

    with db.transaction():
        _deactivate_superseded_output(db, "new_build", ("raw_target",))

    rows = {
        row["candidate_id"]: dict(row)
        for row in db.fetchall(
            "SELECT candidate_id, is_active, superseded_by FROM candidate_facts"
        )
    }
    assert rows["old_candidate"] == {
        "candidate_id": "old_candidate",
        "is_active": 0,
        "superseded_by": "new_build",
    }
    assert rows["new_candidate"] == {
        "candidate_id": "new_candidate",
        "is_active": 1,
        "superseded_by": None,
    }
    assert rows["other_candidate"] == {
        "candidate_id": "other_candidate",
        "is_active": 1,
        "superseded_by": None,
    }
    db.close()


def test_full_scope_activation_deactivates_only_same_source_outside_scope(
    tmp_path,
) -> None:
    db = MetadataDB(str(tmp_path / "metadata.sqlite3"))
    db.init_schema()
    db.seed_sources()
    for raw_object_id, source_id in (
        ("raw_selected", "cninfo_announcements"),
        ("raw_outside", "cninfo_announcements"),
        ("raw_hkex", "hkex_disclosures"),
    ):
        db.insert_raw_object(
            {
                "raw_object_id": raw_object_id,
                "source_id": source_id,
                "object_type": "pdf",
                "storage_uri": f"/tmp/{raw_object_id}.pdf",
                "original_url": f"https://example.test/{raw_object_id}.pdf",
                "content_sha256": raw_object_id.ljust(64, "0"),
                "content_size_bytes": 100,
                "validation_status": "passed",
            }
        )
        db.execute(
            "INSERT INTO candidate_facts "
            "(candidate_id, raw_object_id, build_id, is_active, review_status) "
            "VALUES (?, ?, 'old_build', 1, 'cn_pdf_programmatic_verified')",
            (f"candidate_{raw_object_id}", raw_object_id),
        )

    _deactivate_out_of_scope_output(
        db,
        "new_build",
        ("cninfo_announcements",),
        ("raw_selected",),
    )

    states = {
        row["raw_object_id"]: row["is_active"]
        for row in db.fetchall(
            "SELECT raw_object_id, is_active FROM candidate_facts"
        )
    }
    assert states == {
        "raw_selected": 1,
        "raw_outside": 0,
        "raw_hkex": 1,
    }
    db.close()
