from __future__ import annotations

import pytest

from finraw.regional_share_audit import (
    GREATER_CHINA,
    INTERNATIONAL,
    MIXED_GLOBAL,
    classify_entity,
    classify_entity_scope,
    classify_raw_content,
    classify_source,
    distribution,
)


@pytest.mark.parametrize(
    ("source_id", "expected"),
    [
        ("cninfo_announcements", GREATER_CHINA),
        ("hkex_disclosures", GREATER_CHINA),
        ("nbs_official_statistics", GREATER_CHINA),
        ("sec_companyfacts", INTERNATIONAL),
        ("fred_observations", INTERNATIONAL),
        ("worldbank_indicators", MIXED_GLOBAL),
        ("imf_sdmx", MIXED_GLOBAL),
    ],
)
def test_classify_source_uses_explicit_regional_policy(
    source_id: str, expected: str
) -> None:
    assert classify_source(source_id) == expected


@pytest.mark.parametrize(
    ("entity", "expected"),
    [
        ({"entity_id": "600000_SSE", "country": "CN"}, GREATER_CHINA),
        ({"entity_id": "00005_HKEX", "country": "HK"}, GREATER_CHINA),
        ({"entity_id": "CHN_COUNTRY", "entity_type": "country"}, GREATER_CHINA),
        ({"entity_id": "AAPL_US", "country": "US"}, INTERNATIONAL),
        (
            {
                "entity_id": "USA_COUNTRY",
                "entity_type": "country",
                "market": "Global",
            },
            INTERNATIONAL,
        ),
        ({"entity_id": "TWN_COUNTRY", "country": "TWN"}, INTERNATIONAL),
        (
            {
                "entity_id": "USD_CNY",
                "entity_type": "currency_pair",
                "market": "Global",
            },
            MIXED_GLOBAL,
        ),
    ],
)
def test_classify_entity_obeys_current_greater_china_boundary(
    entity: dict[str, str], expected: str
) -> None:
    assert classify_entity(entity) == expected


def test_classify_entity_uses_authoritative_alias_when_geography_is_missing() -> None:
    assert (
        classify_entity(
            {"entity_id": "MAINLAND_COMPANY", "entity_type": "company"},
            ["cninfo_announcements"],
        )
        == GREATER_CHINA
    )


@pytest.mark.parametrize(
    ("hints", "expected"),
    [
        (["CHN"], GREATER_CHINA),
        (["CHN_COUNTRY"], GREATER_CHINA),
        (["HKG"], GREATER_CHINA),
        (["USA"], INTERNATIONAL),
        (["CHN", "USA"], MIXED_GLOBAL),
        ([], MIXED_GLOBAL),
    ],
)
def test_world_bank_raw_objects_are_classified_by_content_entity(
    hints: list[str], expected: str
) -> None:
    assert classify_raw_content("worldbank_indicators", hints) == expected


def test_scope_classification_requires_all_members_to_be_known() -> None:
    regions = {
        "CN_A": GREATER_CHINA,
        "HK_B": GREATER_CHINA,
        "US_A": INTERNATIONAL,
    }
    assert classify_entity_scope(["CN_A", "HK_B"], regions) == GREATER_CHINA
    assert classify_entity_scope(["US_A"], regions) == INTERNATIONAL
    assert classify_entity_scope(["CN_A", "US_A"], regions) == MIXED_GLOBAL
    assert classify_entity_scope(["CN_A", "MISSING"], regions) == "unclassified"


def test_distribution_reports_narrow_and_broad_regional_shares() -> None:
    result = distribution(
        {
            GREATER_CHINA: 25,
            INTERNATIONAL: 50,
            MIXED_GLOBAL: 20,
            "unclassified": 5,
        }
    )

    assert result["total"] == 100
    assert result["greater_china_share"] == pytest.approx(0.25)
    assert result["international_broad_count"] == 70
    assert result["international_broad_share"] == pytest.approx(0.70)
    assert result["unclassified_share"] == pytest.approx(0.05)
