from __future__ import annotations

from datetime import datetime, timezone

from finraw.atomic_facts import _refresh_source_documents, _year_from_timestamp
from finraw.fact_standardization import _forecast_status
from finraw.source_definitions import _source_policy


def test_imf_source_policy_is_mixed_not_whole_source_forecast() -> None:
    policy = _source_policy("imf_sdmx")

    assert policy["is_forecast"] is None
    assert "per fact" in policy["vintage_policy"]


def test_imf_fact_level_forecast_note_overrides_mixed_definition() -> None:
    definition = {"is_forecast": None}

    historical = _forecast_status(
        {"source_id": "imf_sdmx", "notes": '{"is_forecast": false}'},
        definition,
    )
    forecast = _forecast_status(
        {"source_id": "imf_sdmx", "notes": {"is_forecast": True}},
        definition,
    )

    assert historical == 0
    assert forecast == 1


def test_retrieval_year_supports_database_timestamp_and_iso_text() -> None:
    assert _year_from_timestamp(datetime(2026, 7, 23, tzinfo=timezone.utc)) == 2026
    assert _year_from_timestamp("2026-07-23 03:16:11+08:00") == 2026
    assert _year_from_timestamp(None) is None


class _DocumentDB:
    def __init__(self) -> None:
        self.query_params: tuple[str, ...] = ()
        self.insert_params: list[object] = []

    def fetchall(self, _sql: str, params: tuple[str, ...]):
        self.query_params = params
        return [
            {
                "raw_record_id": "record_hkex",
                "raw_object_id": "raw_hkex",
                "source_id": "hkex_disclosures",
                "record_type": "hkex_pdf_annual_report",
                "record_key": "2025040800667",
                "record_json": {
                    "stock_code": "00700",
                    "company_name": "TENCENT",
                    "report_type": "annual",
                    "year": "2024",
                    "publish_date": "2025-04-08",
                    "announcement_id": "2025040800667",
                    "filename": "2025040800667.pdf",
                },
                "entity_hint": "00700",
                "metric_hint": "annual",
                "period_hint": "2024",
                "storage_uri": "/data/hkex/2025040800667.pdf",
                "original_url": "https://www1.hkexnews.hk/2025040800667.pdf",
                "validation_status": "passed",
            }
        ]

    def execute(self, _sql: str, params: list[object]) -> None:
        self.insert_params = params


def test_hkex_annual_report_is_included_in_source_document_refresh() -> None:
    db = _DocumentDB()
    context = {
        "entity_aliases": {
            "hkex_disclosures": {
                "00700": "HK_00700",
                "TENCENT": "HK_00700",
            }
        }
    }
    report = {"skipped_counts": {}}

    count = _refresh_source_documents(db, context, "fact_build_test", report)

    assert "hkex_pdf_annual_report" in db.query_params
    assert count == 1
    assert "HK_00700" in db.insert_params
    assert "hkex_disclosures" in db.insert_params
