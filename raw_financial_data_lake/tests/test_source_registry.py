from __future__ import annotations

import json
from pathlib import Path

import pytest

from finraw.config import load_config
from finraw.db.schema import SOURCE_REGISTRY_SEED
from finraw.source_registry import (
    CANONICAL_SOURCE_IDS,
    DEPRECATED_SOURCE_ID_ALIASES,
    GREATER_CHINA_QA_SOURCE_IDS,
    GREATER_CHINA_SOURCE_IDS,
    audit_source_ids,
    canonical_source_id,
    normalize_config_source_ids,
)


def test_canonical_source_ids_are_derived_from_registry_seed():
    assert CANONICAL_SOURCE_IDS == frozenset(
        str(row["source_id"]) for row in SOURCE_REGISTRY_SEED
    )
    assert set(GREATER_CHINA_QA_SOURCE_IDS) == GREATER_CHINA_SOURCE_IDS
    assert GREATER_CHINA_SOURCE_IDS <= CANONICAL_SOURCE_IDS


def test_deprecated_aliases_are_migration_only_and_canonicalized():
    expected = {
        "hkex_announcements": "hkex_disclosures",
        "nbs_publications": "nbs_official_statistics",
        "pboc_publications": "pboc_official_statistics",
        "safe_publications": "safe_official_statistics",
    }
    assert DEPRECATED_SOURCE_ID_ALIASES == expected
    for alias, canonical in expected.items():
        assert canonical_source_id(alias) == canonical
        with pytest.raises(ValueError, match="Unknown source_id"):
            canonical_source_id(alias, allow_deprecated_alias=False)


def test_config_source_ids_are_normalized_and_unknown_ids_fail_closed():
    config = {
        "qa": {
            "benchmark_alignment": {
                "greater_china_source_ids": [
                    "hkex_announcements",
                    "nbs_publications",
                ]
            }
        },
        "quality_gates": {
            "min_raw_objects_by_source": {"safe_publications": 2},
            "min_raw_records_by_type": {
                "pboc_publications:official_observation": 5
            },
        },
    }
    normalized = normalize_config_source_ids(config)
    assert normalized["qa"]["benchmark_alignment"]["greater_china_source_ids"] == [
        "hkex_disclosures",
        "nbs_official_statistics",
    ]
    assert normalized["quality_gates"]["min_raw_objects_by_source"] == {
        "safe_official_statistics": 2
    }
    assert normalized["quality_gates"]["min_raw_records_by_type"] == {
        "pboc_official_statistics:official_observation": 5
    }
    with pytest.raises(ValueError, match="unknown_source"):
        normalize_config_source_ids({"source_id": "unknown_source"})


def test_production_qa_profiles_inherit_canonical_greater_china_sources():
    root = Path(__file__).resolve().parents[1]
    for name in (
        "prod_qa_deepseek_v4_global_520.json",
        "prod_qa_deepseek_v4_greater_china_480.json",
    ):
        raw = json.loads((root / "config/profiles" / name).read_text())
        assert "greater_china_source_ids" not in raw["qa"]["benchmark_alignment"]
        loaded = load_config(str(root / "config/profiles" / name))
        assert "greater_china_source_ids" not in loaded["qa"]["benchmark_alignment"]


def test_source_registry_audit_reports_aliases_unknowns_and_live_drift():
    report = audit_source_ids(
        ["sec_companyfacts", "hkex_announcements", "unknown_source"],
        live_source_ids=[*CANONICAL_SOURCE_IDS, "live_only_source"],
    )
    assert report["status"] == "failed"
    assert report["deprecated_alias_counts"] == {"hkex_announcements": 1}
    assert report["unknown_source_counts"] == {"unknown_source": 1}
    assert report["live_missing_from_seed"] == ["live_only_source"]
