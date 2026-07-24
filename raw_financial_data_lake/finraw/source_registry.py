from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

from finraw.db.schema import SOURCE_REGISTRY_SEED


SOURCE_REGISTRY_CONTRACT_VERSION = "1.0.0"
SOURCE_REGISTRY_BY_ID = {
    str(row["source_id"]): dict(row) for row in SOURCE_REGISTRY_SEED
}
CANONICAL_SOURCE_IDS = frozenset(SOURCE_REGISTRY_BY_ID)

# Migration-only aliases. New profiles and persisted rows must use canonical IDs.
DEPRECATED_SOURCE_ID_ALIASES = {
    "hkex_announcements": "hkex_disclosures",
    "nbs_publications": "nbs_official_statistics",
    "pboc_publications": "pboc_official_statistics",
    "safe_publications": "safe_official_statistics",
}

GREATER_CHINA_SOURCE_IDS = frozenset(
    {
        "bse_disclosures",
        "bse_market_statistics",
        "cninfo_announcements",
        "csi_index_publications",
        "hkex_disclosures",
        "nbs_official_statistics",
        "pboc_official_statistics",
        "safe_official_statistics",
        "sse_market_statistics",
        "szse_market_statistics",
    }
)
INTERNATIONAL_SOURCE_IDS = frozenset(
    {
        "fred_observations",
        "sec_companyfacts",
        "sec_filings",
        "sec_submissions",
    }
)
MULTI_REGION_SOURCE_IDS = frozenset({"imf_sdmx", "worldbank_indicators"})
DISCLOSURE_DOCUMENT_SOURCE_IDS = frozenset(
    {
        "bse_disclosures",
        "cninfo_announcements",
        "hkex_disclosures",
        "sec_filings",
    }
)
GREATER_CHINA_QA_SOURCE_IDS = tuple(sorted(GREATER_CHINA_SOURCE_IDS))

SOURCE_ID_SCALAR_CONFIG_KEYS = frozenset({"source_id"})
SOURCE_ID_LIST_CONFIG_KEYS = frozenset(
    {
        "source_ids",
        "greater_china_source_ids",
        "allowed_corporate_sources",
        "allowed_market_and_macro_sources",
        "annual_filing_sources",
        "required_official_publication_sources",
    }
)
SOURCE_ID_MAP_CONFIG_KEYS = frozenset({"min_raw_objects_by_source"})
SOURCE_RECORD_MAP_CONFIG_KEYS = frozenset({"min_raw_records_by_type"})


def canonical_source_id(
    source_id: str,
    *,
    allow_deprecated_alias: bool = True,
) -> str:
    value = str(source_id).strip()
    if value in CANONICAL_SOURCE_IDS:
        return value
    if allow_deprecated_alias and value in DEPRECATED_SOURCE_ID_ALIASES:
        return DEPRECATED_SOURCE_ID_ALIASES[value]
    raise ValueError(
        f"Unknown source_id {value!r}; expected one of "
        f"{sorted(CANONICAL_SOURCE_IDS)}"
    )


def canonical_source_ids(
    source_ids: Iterable[str],
    *,
    allow_deprecated_alias: bool = True,
) -> list[str]:
    output = []
    seen = set()
    for source_id in source_ids:
        canonical = canonical_source_id(
            source_id, allow_deprecated_alias=allow_deprecated_alias
        )
        if canonical not in seen:
            seen.add(canonical)
            output.append(canonical)
    return output


def normalize_config_source_ids(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copied config with source IDs canonicalized and unknown IDs rejected."""

    def visit(value: Any, key: str | None = None) -> Any:
        if key in SOURCE_ID_SCALAR_CONFIG_KEYS and isinstance(value, str):
            return canonical_source_id(value)
        if key in SOURCE_ID_LIST_CONFIG_KEYS and isinstance(value, list):
            return canonical_source_ids(str(item) for item in value)
        if key in SOURCE_ID_MAP_CONFIG_KEYS and isinstance(value, dict):
            return {
                canonical_source_id(str(source_id)): visit(item)
                for source_id, item in value.items()
            }
        if key in SOURCE_RECORD_MAP_CONFIG_KEYS and isinstance(value, dict):
            output = {}
            for compound_key, item in value.items():
                source_id, separator, record_type = str(compound_key).partition(":")
                canonical = canonical_source_id(source_id)
                normalized_key = (
                    f"{canonical}:{record_type}" if separator else canonical
                )
                output[normalized_key] = visit(item)
            return output
        if isinstance(value, dict):
            return {str(child_key): visit(item, str(child_key)) for child_key, item in value.items()}
        if isinstance(value, list):
            return [visit(item) for item in value]
        return value

    return visit(dict(config))


def audit_source_ids(
    source_ids: Iterable[str],
    *,
    live_source_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    observed = [str(value).strip() for value in source_ids]
    aliases = Counter(value for value in observed if value in DEPRECATED_SOURCE_ID_ALIASES)
    unknown = Counter(
        value
        for value in observed
        if value not in CANONICAL_SOURCE_IDS
        and value not in DEPRECATED_SOURCE_ID_ALIASES
    )
    live = set(str(value) for value in live_source_ids or [])
    return {
        "contract_version": SOURCE_REGISTRY_CONTRACT_VERSION,
        "canonical_source_count": len(CANONICAL_SOURCE_IDS),
        "observed_source_count": len(observed),
        "canonical_observed_count": sum(value in CANONICAL_SOURCE_IDS for value in observed),
        "deprecated_alias_counts": dict(sorted(aliases.items())),
        "unknown_source_counts": dict(sorted(unknown.items())),
        "live_missing_from_seed": sorted(live - CANONICAL_SOURCE_IDS),
        "seed_missing_from_live": sorted(CANONICAL_SOURCE_IDS - live) if live else [],
        "status": "passed"
        if not aliases and not unknown and not (live - CANONICAL_SOURCE_IDS)
        else "failed",
    }


def assert_source_registry_integrity() -> None:
    seed_ids = [str(row["source_id"]) for row in SOURCE_REGISTRY_SEED]
    duplicates = sorted(
        source_id for source_id, count in Counter(seed_ids).items() if count > 1
    )
    if duplicates:
        raise RuntimeError(f"Duplicate canonical source IDs: {duplicates}")
    invalid_alias_targets = sorted(
        set(DEPRECATED_SOURCE_ID_ALIASES.values()) - CANONICAL_SOURCE_IDS
    )
    if invalid_alias_targets:
        raise RuntimeError(
            f"Deprecated source aliases target unknown IDs: {invalid_alias_targets}"
        )
    regional_overlap = (
        GREATER_CHINA_SOURCE_IDS & INTERNATIONAL_SOURCE_IDS
        | GREATER_CHINA_SOURCE_IDS & MULTI_REGION_SOURCE_IDS
        | INTERNATIONAL_SOURCE_IDS & MULTI_REGION_SOURCE_IDS
    )
    if regional_overlap:
        raise RuntimeError(f"Source region sets overlap: {sorted(regional_overlap)}")


assert_source_registry_integrity()
