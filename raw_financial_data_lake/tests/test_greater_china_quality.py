from __future__ import annotations

from finraw.greater_china_quality import (
    _evaluate_metric_coverage_profile,
    _expected_companies,
    _quality_failures,
    _select_metric_coverage_profile,
)


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


def test_quality_failures_are_scoped_and_fail_closed() -> None:
    report = {
        "contract": {
            "minimum_a_share_companies": 2,
            "minimum_hkex_companies": 1,
            "required_a_share_exchanges": ["SSE", "SZSE", "BSE"],
            "minimum_verified_document_ratio": 0.9,
            "minimum_graph_ready_ratio": 0.9,
        },
        "raw_annual_covered_a_share_company_count": 1,
        "raw_annual_covered_hkex_company_count": 1,
        "verified_document_ratio": 0.5,
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
    assert any("verified_document_ratio" in item for item in failures)
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

    assert reason == "profile_match"
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
