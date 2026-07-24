from __future__ import annotations

from finraw.greater_china_quality import (
    _detect_statement_schema_profile,
    _document_metric_extraction_complete,
    _evaluate_metric_coverage_profile,
    _expected_companies,
    _industry_ontology_ids,
    _load_entity_aliases,
    _load_raw_annual_coverage,
    _quality_failures,
    _select_metric_coverage_profile,
)

from finraw.db.client import MetadataDB


def test_expected_companies_preserves_authoritative_scope_and_years() -> None:
    config = {
        "cninfo": {
            "stock_pool": [
                {
                    "stock_code": "1",
                    "company_name": "A",
                    "market": "SZSE",
                    "industry": "Technology",
                }
            ],
            "announcements": [
                {"stock_code": "1", "year": "2021"},
                {"stock_code": "1", "year": "2022"},
            ],
        },
        "bse": {
            "stock_pool": [
                {"stock_code": "920001", "company_name": "B"}
            ],
            "announcements": [{"stock_code": "920001", "year": "2022"}],
        },
        "hkex": {
            "announcements": [
                {
                    "stock_code": "1",
                    "company_name": "HK",
                    "year": "2020",
                },
                {
                    "stock_code": "1",
                    "company_name": "HK",
                    "year": "2021",
                },
            ]
        },
    }

    companies = _expected_companies(config)

    assert set(companies) == {
        "cninfo_announcements:000001",
        "bse_disclosures:920001",
        "hkex_disclosures:00001",
    }
    assert companies["cninfo_announcements:000001"]["expected_years"] == {
        2021,
        2022,
    }
    assert companies["hkex_disclosures:00001"]["exchange"] == "HKEX"


def test_entity_alias_resolution_ignores_superseded_generic_cn_entity(
    tmp_path,
) -> None:
    db = MetadataDB(str(tmp_path / "metadata.db"))
    db.init_schema()
    db.seed_sources()
    entity_columns = (
        "entity_id, canonical_name, entity_type, market, country, exchange, "
        "build_id, is_active"
    )
    db.execute(
        f"INSERT INTO canonical_entities ({entity_columns}) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "000009_CN",
            "Legacy Company",
            "company",
            "CN",
            "CN",
            "CN",
            "entity_old",
            0,
        ),
    )
    db.execute(
        f"INSERT INTO canonical_entities ({entity_columns}) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "000009_SZSE",
            "Active Company",
            "company",
            "CN",
            "CN",
            "SZSE",
            "entity_active",
            1,
        ),
    )
    alias_columns = (
        "alias_id, entity_id, source_id, source_code, alias, confidence_score, "
        "build_id, is_active"
    )
    db.execute(
        f"INSERT INTO entity_alias_map ({alias_columns}) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "alias_old",
            "000009_CN",
            "cninfo_announcements",
            "000009",
            "000009",
            1.0,
            "entity_old",
            0,
        ),
    )
    db.execute(
        f"INSERT INTO entity_alias_map ({alias_columns}) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "alias_active",
            "000009_SZSE",
            "cninfo_announcements",
            "000009",
            "000009",
            1.0,
            "entity_active",
            1,
        ),
    )

    aliases = _load_entity_aliases(db)

    assert aliases["cninfo_announcements:000009"] == "000009_SZSE"
    db.close()


def test_raw_annual_coverage_selects_latest_version_per_authoritative_url(
    tmp_path,
) -> None:
    db = MetadataDB(str(tmp_path / "metadata.db"))
    db.init_schema()
    db.seed_sources()
    for raw_object_id, retrieval_time, suffix in (
        ("raw_old", "2026-01-01T00:00:00+00:00", "old"),
        ("raw_new", "2026-02-01T00:00:00+00:00", "new"),
    ):
        db.insert_raw_object(
            {
                "raw_object_id": raw_object_id,
                "source_id": "cninfo_announcements",
                "object_type": "pdf",
                "original_url": f"https://example.test/report.pdf?version={suffix}",
                "content_sha256": suffix,
                "retrieval_time": retrieval_time,
                "validation_status": "passed",
            }
        )
        db.insert_raw_records(
            [
                {
                    "raw_record_id": f"record_{suffix}",
                    "raw_object_id": raw_object_id,
                    "source_id": "cninfo_announcements",
                    "record_key": f"000001_2023_{suffix}",
                    "record_type": "cninfo_pdf_announcement",
                    "record_json": {},
                    "entity_hint": "000001",
                    "metric_hint": "annual",
                    "period_hint": "2023",
                }
            ]
        )

    coverage = _load_raw_annual_coverage(
        db,
        {
            "cninfo_announcements:000001": {
                "expected_urls": {"https://example.test/report.pdf"}
            }
        },
    )

    assert coverage["cninfo_announcements:000001"]["years"] == {2023}
    assert coverage["cninfo_announcements:000001"]["raw_object_ids"] == {
        "raw_new"
    }
    db.close()


def test_quality_failures_are_scoped_and_fail_closed() -> None:
    report = {
        "contract": {
            "minimum_a_share_companies": 2,
            "minimum_hkex_companies": 1,
            "required_a_share_exchanges": ["SSE", "SZSE", "BSE"],
            "minimum_document_with_verified_fact_ratio": 0.9,
            "minimum_required_metric_extraction_complete_ratio": 0.9,
            "minimum_graph_ready_ratio": 0.9,
        },
        "raw_annual_covered_a_share_company_count": 1,
        "raw_annual_covered_hkex_company_count": 1,
        "document_with_verified_fact_ratio": 0.5,
        "required_metric_extraction_complete_ratio": 0.4,
        "scoped_graph_ready_ratio": 0.0,
        "company_coverage": [
            {
                "company_key": "cninfo_announcements:600001",
                "exchange": "SSE",
                "raw_annual_coverage_passed": True,
                "core_metric_coverage_passed": False,
            },
            {
                "company_key": "bse_disclosures:920001",
                "exchange": "BSE",
                "raw_annual_coverage_passed": False,
                "core_metric_coverage_passed": False,
            },
        ],
        "official_publication_coverage": {
            "nbs_official_statistics": {
                "expected_target_count": 2,
                "passed_target_count": 1,
            }
        },
    }

    failures = _quality_failures(report)

    assert any("raw_annual_covered_a_share_company_count" in item for item in failures)
    assert any("incomplete_required_a_share_exchanges" in item for item in failures)
    assert any("document_with_verified_fact_ratio" in item for item in failures)
    assert any(
        "required_metric_extraction_complete_ratio" in item
        for item in failures
    )
    assert any("company_core_metric_coverage_failures" in item for item in failures)
    assert any("official_publication_coverage" in item for item in failures)


def test_metric_profile_is_selected_and_evaluated_with_not_applicable_metrics() -> None:
    profiles = [
        {
            "profile_id": "general",
            "is_default": True,
            "applicable_metric_ids": ["revenue", "net_income"],
        },
        {
            "profile_id": "regulated_financial",
            "match": {"industry_contains_any": ["金融"]},
            "applicable_metric_ids": [
                "net_income",
                "total_assets",
                "total_liabilities",
            ],
            "required_metric_groups": [
                {
                    "group_id": "earnings",
                    "metric_ids": ["net_income"],
                    "minimum_metric_count": 1,
                },
                {
                    "group_id": "position",
                    "metric_ids": ["total_assets", "total_liabilities"],
                    "minimum_metric_count": 2,
                },
            ],
            "minimum_covered_metric_count": 3,
        },
    ]
    profile, reason = _select_metric_coverage_profile(
        "cninfo_announcements:600000",
        {"industry": "金融业", "source_id": "cninfo_announcements"},
        profiles,
    )
    result = _evaluate_metric_coverage_profile(
        profile,
        {
            "metric_years": {
                "net_income": {2020, 2021, 2022, 2023, 2024},
                "total_assets": {2020, 2021, 2022, 2023, 2024},
                "total_liabilities": {2020, 2021, 2022, 2023, 2024},
            }
        },
        default_minimum_years=5,
        all_profile_metric_ids={
            "revenue",
            "net_income",
            "total_assets",
            "total_liabilities",
        },
    )

    assert reason == "industry_ontology_profile"
    assert result["core_metric_coverage_passed"] is True
    assert result["not_applicable_core_metric_ids"] == ["revenue"]


def test_explicit_company_profile_does_not_match_other_companies() -> None:
    profiles = [
        {
            "profile_id": "special",
            "match": {"company_keys": ["hkex_disclosures:00001"]},
            "applicable_metric_ids": ["revenue"],
        },
        {
            "profile_id": "general",
            "is_default": True,
            "applicable_metric_ids": ["revenue", "net_income"],
        },
    ]

    profile, reason = _select_metric_coverage_profile(
        "hkex_disclosures:00002",
        {"source_id": "hkex_disclosures", "source_code": "00002"},
        profiles,
    )

    assert profile["profile_id"] == "general"
    assert reason == "default_profile"


def test_manual_profile_override_has_highest_priority() -> None:
    profiles = [
        {
            "profile_id": "manual",
            "match": {"company_keys": ["hkex_disclosures:00001"]},
            "applicable_metric_ids": ["revenue"],
        },
        {
            "profile_id": "schema",
            "applicable_metric_ids": ["shareholders_equity"],
        },
        {
            "profile_id": "industry",
            "match": {"industry_ontology_ids": ["financial_institution"]},
            "applicable_metric_ids": ["net_income"],
        },
    ]

    profile, reason = _select_metric_coverage_profile(
        "hkex_disclosures:00001",
        {
            "statement_schema_detected_profile_id": "schema",
            "industry_ontology_ids": ["financial_institution"],
        },
        profiles,
    )

    assert profile["profile_id"] == "manual"
    assert reason == "manual_override_profile"


def test_statement_schema_detection_precedes_industry_profile() -> None:
    profiles = [
        {
            "profile_id": "schema",
            "statement_schema_detection": {
                "source_ids": ["hkex_disclosures"],
                "exchanges": ["HKEX"],
                "required_any_metric_ids": ["shareholders_equity"],
                "absent_metric_ids": ["total_assets", "total_liabilities"],
                "required_statement_types": [
                    "income_statement",
                    "balance_sheet",
                ],
            },
            "applicable_metric_ids": ["shareholders_equity"],
        },
        {
            "profile_id": "industry",
            "match": {"industry_ontology_ids": ["financial_institution"]},
            "applicable_metric_ids": ["net_income"],
        },
    ]
    company = {
        "source_id": "hkex_disclosures",
        "exchange": "HKEX",
        "industry_ontology_ids": ["financial_institution"],
    }
    detected = _detect_statement_schema_profile(
        company,
        profiles,
        {
            "verified_metric_ids_by_raw_object": {
                "raw_1": {"shareholders_equity", "net_income"}
            },
            "verified_statement_raw_object_ids": {
                "income_statement": {"raw_1"},
                "balance_sheet": {"raw_1"},
            },
        },
        {"metric_years": {}},
    )
    company["statement_schema_detected_profile_id"] = detected

    profile, reason = _select_metric_coverage_profile(
        "hkex_disclosures:00999", company, profiles
    )

    assert detected == "schema"
    assert profile["profile_id"] == "schema"
    assert reason == "statement_schema_detected_profile"


def test_industry_ontology_normalizes_financial_institutions() -> None:
    assert _industry_ontology_ids({"industry": "Banking Services"}) == {
        "financial_institution"
    }
    assert _industry_ontology_ids({"industry": "保险业"}) == {
        "financial_institution"
    }


def test_document_metric_completeness_requires_all_profile_groups() -> None:
    profile = {
        "profile_id": "general",
        "applicable_metric_ids": [
            "revenue",
            "net_income",
            "total_assets",
            "total_liabilities",
        ],
        "required_metric_groups": [
            {
                "group_id": "performance",
                "metric_ids": ["revenue", "net_income"],
                "minimum_metric_count": 1,
            },
            {
                "group_id": "position",
                "metric_ids": ["total_assets", "total_liabilities"],
                "minimum_metric_count": 1,
            },
        ],
        "minimum_covered_metric_count": 3,
    }

    assert not _document_metric_extraction_complete(profile, {"revenue"})
    assert not _document_metric_extraction_complete(
        profile, {"revenue", "total_assets"}
    )
    assert _document_metric_extraction_complete(
        profile, {"revenue", "net_income", "total_assets"}
    )
