from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from finraw.db.client import DBProtocol


AUDIT_VERSION = "1.2.0"
GREATER_CHINA = "greater_china"
INTERNATIONAL = "international"
MIXED_GLOBAL = "mixed_global"
UNCLASSIFIED = "unclassified"
REGION_BUCKETS = (GREATER_CHINA, INTERNATIONAL, MIXED_GLOBAL, UNCLASSIFIED)

# This is the operational scope covered by the current authoritative contracts.
# Taiwan is deliberately not inferred into Greater China until an authoritative
# Taiwan source and entity contract is added.
GREATER_CHINA_COUNTRY_CODES = {"CN", "CHN", "HK", "HKG", "MO", "MAC"}
GREATER_CHINA_ENTITY_IDS = {"CHN_COUNTRY", "HKG_COUNTRY", "MAC_COUNTRY"}
GREATER_CHINA_EXCHANGES = {"SSE", "SZSE", "BSE", "HK", "HKEX", "MO", "MACAU"}
GREATER_CHINA_MARKETS = {
    "CN",
    "CHINA",
    "PRC",
    "MAINLAND CHINA",
    "HK",
    "HONG KONG",
    "MO",
    "MACAU",
}

GREATER_CHINA_SOURCE_IDS = {
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
INTERNATIONAL_SOURCE_IDS = {
    "fred_observations",
    "sec_companyfacts",
    "sec_filings",
    "sec_submissions",
}
MULTI_REGION_SOURCE_IDS = {"imf_sdmx", "worldbank_indicators"}
DISCLOSURE_DOCUMENT_SOURCE_IDS = {
    "bse_disclosures",
    "cninfo_announcements",
    "hkex_disclosures",
    "sec_filings",
}

PROMOTED_CANDIDATE_STATUSES = {"approved_for_atomic_fact", "promoted"}
FINSEARCHCOMP_REGIONAL_REFERENCE = {
    "t2": {
        "global_count": 119,
        "greater_china_count": 100,
        "total_count": 219,
        "greater_china_share": 100 / 219,
    },
    "t3": {
        "global_count": 84,
        "greater_china_count": 88,
        "total_count": 172,
        "greater_china_share": 88 / 172,
    },
    "combined_t2_t3": {
        "global_count": 203,
        "greater_china_count": 188,
        "total_count": 391,
        "greater_china_share": 188 / 391,
    },
}
INTERNAL_GREATER_CHINA_MINIMUM_SHARE = 0.40
BENCHMARK_ALIGNMENT_TOLERANCE = 0.05

T2_DERIVED_TYPES = {"difference", "yoy_growth", "qoq_growth", "ratio"}
T3_DERIVED_TYPES = {
    "share",
    "multi_year_argmax",
    "multi_year_argmin",
    "rolling_max",
    "rolling_min",
    "macro_time_series_argmax",
    "macro_time_series_argmin",
    "time_series_argmax",
    "time_series_argmin",
    "long_window_return",
    "ranking",
    "argmax",
    "argmin",
    "industry_ranking",
    "industry_argmax",
    "industry_argmin",
    "multi_condition_screening",
}

COMPANY_PROFILE_METRICS = {
    "revenue",
    "operating_income",
    "net_income",
    "total_assets",
    "total_liabilities",
    "shareholders_equity",
    "net_cash_provided_by_used_in_operating_activities",
}
COMPANY_PROFILE_INCOME_METRICS = {"revenue", "operating_income", "net_income"}
COMPANY_PROFILE_POSITION_METRICS = {
    "total_assets",
    "total_liabilities",
    "shareholders_equity",
}


def classify_source(source_id: Any, market: Any = None) -> str:
    source = str(source_id or "").strip().casefold()
    if source in GREATER_CHINA_SOURCE_IDS:
        return GREATER_CHINA
    if source in INTERNATIONAL_SOURCE_IDS:
        return INTERNATIONAL
    if source in MULTI_REGION_SOURCE_IDS:
        return MIXED_GLOBAL
    market_token = _token(market)
    if market_token in GREATER_CHINA_MARKETS or market_token in GREATER_CHINA_EXCHANGES:
        return GREATER_CHINA
    if "GLOBAL" in market_token:
        return MIXED_GLOBAL
    if market_token:
        return INTERNATIONAL
    return UNCLASSIFIED


def classify_entity(
    entity: Mapping[str, Any],
    alias_source_ids: Iterable[str] = (),
) -> str:
    entity_id = str(entity.get("entity_id") or "").strip().upper()
    country = _token(entity.get("country"))
    market = _token(entity.get("market"))
    exchange = _token(entity.get("exchange"))
    entity_type = str(entity.get("entity_type") or "").strip().casefold()

    if _is_greater_china_country(country):
        return GREATER_CHINA
    if entity_id in GREATER_CHINA_ENTITY_IDS or entity_id.endswith(
        ("_SSE", "_SZSE", "_BSE", "_HKEX", "_CN", "_HK", "_MO")
    ):
        return GREATER_CHINA
    if market in GREATER_CHINA_MARKETS or exchange in GREATER_CHINA_EXCHANGES:
        return GREATER_CHINA
    # Country observations from multilateral providers are still attributable to
    # one country. "Global" on those master-data rows describes source coverage,
    # not a cross-region value.
    if entity_type == "country":
        return INTERNATIONAL
    source_regions = {
        classify_source(source_id) for source_id in alias_source_ids if source_id
    }
    if source_regions == {GREATER_CHINA}:
        return GREATER_CHINA

    if entity_type in {"currency_pair"} or market == "GLOBAL":
        return MIXED_GLOBAL
    if source_regions == {MIXED_GLOBAL}:
        return MIXED_GLOBAL
    if len(source_regions - {UNCLASSIFIED}) > 1:
        return MIXED_GLOBAL

    if country or market or exchange:
        return INTERNATIONAL
    if INTERNATIONAL in source_regions:
        return INTERNATIONAL
    if MIXED_GLOBAL in source_regions:
        return MIXED_GLOBAL
    return UNCLASSIFIED


def classify_entity_scope(
    entity_ids: Iterable[Any],
    entity_regions: Mapping[str, str],
) -> str:
    identifiers = {str(value) for value in entity_ids if value}
    if not identifiers:
        return UNCLASSIFIED
    regions = {entity_regions.get(entity_id, UNCLASSIFIED) for entity_id in identifiers}
    if UNCLASSIFIED in regions:
        return UNCLASSIFIED
    if regions == {GREATER_CHINA}:
        return GREATER_CHINA
    if regions == {INTERNATIONAL}:
        return INTERNATIONAL
    if regions == {MIXED_GLOBAL}:
        return MIXED_GLOBAL
    return MIXED_GLOBAL


def classify_raw_content(
    source_id: Any,
    entity_hints: Iterable[Any] = (),
    source_market: Any = None,
) -> str:
    source = str(source_id or "").strip()
    source_region = classify_source(source, source_market)
    if source != "worldbank_indicators":
        return source_region
    hint_regions = {
        GREATER_CHINA
        if _is_greater_china_country(_country_token(hint))
        else INTERNATIONAL
        for hint in entity_hints
        if str(hint or "").strip()
    }
    if hint_regions == {GREATER_CHINA}:
        return GREATER_CHINA
    if hint_regions == {INTERNATIONAL}:
        return INTERNATIONAL
    return MIXED_GLOBAL


def distribution(counts: Mapping[str, int | float]) -> dict[str, Any]:
    bucket_counts = {
        bucket: int(counts.get(bucket, 0) or 0) for bucket in REGION_BUCKETS
    }
    total = sum(bucket_counts.values())
    broad_international = bucket_counts[INTERNATIONAL] + bucket_counts[MIXED_GLOBAL]
    return {
        "total": total,
        "bucket_counts": bucket_counts,
        "bucket_shares": {
            bucket: _ratio(value, total) for bucket, value in bucket_counts.items()
        },
        "greater_china_share": _ratio(bucket_counts[GREATER_CHINA], total),
        "international_broad_count": broad_international,
        "international_broad_share": _ratio(broad_international, total),
        "unclassified_share": _ratio(bucket_counts[UNCLASSIFIED], total),
    }


def regional_alignment_status(
    greater_china_share: float,
    *,
    internal_minimum: float = INTERNAL_GREATER_CHINA_MINIMUM_SHARE,
    benchmark_reference: float = FINSEARCHCOMP_REGIONAL_REFERENCE["combined_t2_t3"][
        "greater_china_share"
    ],
    tolerance: float = BENCHMARK_ALIGNMENT_TOLERANCE,
) -> str:
    if greater_china_share < 0.25:
        return "severely_underrepresented"
    if greater_china_share < internal_minimum:
        return "below_internal_contract"
    if greater_china_share < benchmark_reference - tolerance:
        return "contract_met_but_benchmark_underrepresented"
    if greater_china_share <= benchmark_reference + tolerance:
        return "within_benchmark_alignment_band"
    return "greater_china_overweighted"


def audit_regional_shares(
    db: DBProtocol,
    config: dict[str, Any],
    output_dir: str | None = None,
) -> dict[str, Any]:
    source_rows = [
        _as_dict(row)
        for row in db.fetchall(
            "SELECT source_id, source_name, market, provider, authority_level "
            "FROM source_registry"
        )
    ]
    source_markets = {
        str(row.get("source_id") or ""): row.get("market") for row in source_rows
    }
    source_policy = {
        str(row.get("source_id") or ""): classify_source(
            row.get("source_id"), row.get("market")
        )
        for row in source_rows
    }

    active_kg = _active_kg_build(db)
    builds = _pinned_builds(db, active_kg)
    entity_rows, entity_regions, entity_report = _entity_audit(
        db, builds["entity_build_id"]
    )
    alias_sources = _entity_alias_sources(db, builds["entity_build_id"])
    # Reclassify once with the complete alias source map.
    entity_regions = {
        str(row.get("entity_id")): classify_entity(
            row, alias_sources.get(str(row.get("entity_id")), set())
        )
        for row in entity_rows
    }
    entity_report = _summarize_entities(entity_rows, entity_regions)

    raw_hints = _raw_object_hints(db)
    raw_report, raw_regions = _raw_object_audit(db, raw_hints, source_markets)
    raw_record_report = _raw_record_audit(db, source_markets)
    candidate_report = _candidate_audit(db, entity_regions, source_policy)
    atomic_report = _atomic_fact_audit(
        db,
        builds["atomic_build_id"],
        entity_regions,
        source_policy,
    )
    metric_categories = _metric_categories(db, builds["metric_build_id"])
    standardized_report = _standardized_fact_audit(
        db,
        builds["fact_build_id"],
        entity_regions,
        source_policy,
        metric_categories,
    )
    fact_universe_report = _fact_universe_audit(
        db,
        builds["fact_universe_build_id"],
    )
    derived_report, scope_regions = _derived_fact_audit(
        db,
        builds["derived_build_id"],
        builds["fact_build_id"],
        entity_regions,
    )
    company_profile_report = _company_profile_audit(
        db,
        builds["fact_build_id"],
        builds["entity_build_id"],
        entity_rows,
        entity_regions,
    )
    document_report = _source_document_audit(
        db,
        builds["document_build_id"],
        entity_regions,
        source_policy,
    )
    kg_report = _kg_region_audit(
        db,
        active_kg,
        entity_report,
        standardized_report,
        derived_report,
        document_report,
        entity_regions,
        raw_regions,
        scope_regions,
        builds["entity_build_id"],
        source_policy,
    )
    qa_constructible_report = _qa_constructible_audit(
        db,
        standardized_report,
        derived_report,
        kg_report=kg_report,
    )

    structured_gc_sources_without_facts = sorted(
        source_id
        for source_id in GREATER_CHINA_SOURCE_IDS
        if raw_report["by_source"].get(source_id, {}).get("usable_object_count", 0)
        and standardized_report["by_source"].get(source_id, {}).get("fact_count", 0)
        == 0
    )
    document_index_gaps = []
    for source_id in sorted(DISCLOSURE_DOCUMENT_SOURCE_IDS):
        usable_objects = int(
            raw_report["by_source"].get(source_id, {}).get("usable_object_count", 0)
        )
        indexed_documents = int(
            document_report["by_source"].get(source_id, {}).get("total", 0)
        )
        if usable_objects > indexed_documents:
            document_index_gaps.append(
                {
                    "source_id": source_id,
                    "usable_object_count": usable_objects,
                    "indexed_document_count": indexed_documents,
                    "gap_count": usable_objects - indexed_documents,
                }
            )
    greater_china_derived_type_gaps = sorted(
        derived_type
        for derived_type, item in derived_report["by_derived_type"].items()
        if item["total"] > 0 and item["bucket_counts"][GREATER_CHINA] == 0
    )
    source_wide_forecast_exclusions = sorted(
        source_id
        for source_id, item in standardized_report["by_source"].items()
        if item["graph_ready_count"] > 0 and item["historical_graph_ready_count"] == 0
    )
    report = {
        "audit_version": AUDIT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope_policy": {
            "benchmark_market": "greater_china",
            "internal_region_scope": "mainland_hong_kong_macau",
            "greater_china_definition": "mainland_china_hong_kong_macau",
            "greater_china_country_codes": sorted(GREATER_CHINA_COUNTRY_CODES),
            "taiwan_policy": (
                "Outside the current Greater China bucket until an authoritative "
                "Taiwan source and entity contract is added."
            ),
            "international_broad_definition": (
                "international plus mixed_global; multilateral providers are "
                "classified by content entity where possible"
            ),
            "region_buckets": list(REGION_BUCKETS),
        },
        "pinned_builds": builds,
        "source_policy": source_policy,
        "raw_objects": raw_report,
        "raw_records": raw_record_report,
        "canonical_entities": entity_report,
        "candidate_facts": candidate_report,
        "atomic_facts": atomic_report,
        "standardized_facts": standardized_report,
        "fact_universe": fact_universe_report,
        "derived_facts": derived_report,
        "company_profile_capability": company_profile_report,
        "qa_constructible_capability": qa_constructible_report,
        "source_documents": document_report,
        "knowledge_graph": kg_report,
        "finsearchcomp_reference": {
            **FINSEARCHCOMP_REGIONAL_REFERENCE,
            "usage": "T2/T3 distribution reference only",
            "internal_minimum_greater_china_share": (
                INTERNAL_GREATER_CHINA_MINIMUM_SHARE
            ),
            "alignment_tolerance": BENCHMARK_ALIGNMENT_TOLERANCE,
            "internal_contract_source": (
                "config/scopes/greater_china_qa_constraints.json"
            ),
        },
        "structured_greater_china_sources_without_active_facts": (
            structured_gc_sources_without_facts
        ),
        "document_index_gaps": document_index_gaps,
        "greater_china_derived_types_without_outputs": (
            greater_china_derived_type_gaps
        ),
        "source_wide_forecast_exclusions": source_wide_forecast_exclusions,
    }
    report["summary_matrix"] = _summary_matrix(report)
    report["capability_dimensions"] = _capability_dimensions(report)
    report["balance_assessment"] = _balance_assessment(report)
    if output_dir:
        paths = write_regional_share_report(report, output_dir)
        report["written_files"] = [str(path) for path in paths]
    return report


def write_regional_share_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "regional_share_audit.json"
    md_path = output / "regional_share_audit.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    md_path.write_text(_regional_markdown(report), encoding="utf-8")
    return [json_path, md_path]


def _active_kg_build(db: DBProtocol) -> dict[str, Any]:
    row = db.fetchone(
        "SELECT * FROM kg_builds WHERE is_active = 1 AND status = 'success' "
        "ORDER BY completed_at DESC LIMIT 1"
    )
    if not row:
        raise RuntimeError(
            "No active successful KG build is available for regional audit"
        )
    return _as_dict(row)


def _pinned_builds(db: DBProtocol, active_kg: Mapping[str, Any]) -> dict[str, str]:
    fact_build_id = str(active_kg.get("input_fact_build_id") or "")
    fact_universe_build_id = str(active_kg.get("input_fact_universe_build_id") or "")
    derived_build_id = str(active_kg.get("input_qa_build_id") or "")
    entity_build_id = str(active_kg.get("input_entity_build_id") or "")
    metric_build_id = str(active_kg.get("input_metric_build_id") or "")
    document_build_id = str(active_kg.get("input_document_build_id") or "")
    if not all([fact_build_id, derived_build_id, entity_build_id, metric_build_id]):
        raise RuntimeError(
            "Active KG does not contain a complete pinned build contract"
        )
    fact_build = db.fetchone(
        "SELECT input_build_id FROM pipeline_builds WHERE build_id = ?",
        [fact_build_id],
    )
    atomic_build_id = str(
        (_as_dict(fact_build).get("input_build_id") if fact_build else None)
        or document_build_id
    )
    if not atomic_build_id:
        raise RuntimeError(
            "The active standardized fact build does not identify its atomic input build"
        )
    return {
        "kg_build_id": str(active_kg["kg_build_id"]),
        "entity_build_id": entity_build_id,
        "metric_build_id": metric_build_id,
        "source_definition_build_id": str(
            active_kg.get("input_source_definition_build_id") or ""
        ),
        "atomic_build_id": atomic_build_id,
        "document_build_id": document_build_id,
        "fact_build_id": fact_build_id,
        "fact_universe_build_id": fact_universe_build_id,
        "derived_build_id": derived_build_id,
    }


def _entity_alias_sources(db: DBProtocol, build_id: str) -> dict[str, set[str]]:
    rows = db.fetchall(
        "SELECT entity_id, source_id FROM entity_alias_map WHERE build_id = ?",
        [build_id],
    )
    output: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        item = _as_dict(row)
        if item.get("entity_id") and item.get("source_id"):
            output[str(item["entity_id"])].add(str(item["source_id"]))
    return output


def _entity_audit(
    db: DBProtocol, build_id: str
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, Any]]:
    rows = [
        _as_dict(row)
        for row in db.fetchall(
            "SELECT entity_id, canonical_name, entity_type, market, country, "
            "exchange, ticker FROM canonical_entities WHERE build_id = ?",
            [build_id],
        )
    ]
    regions = {str(row.get("entity_id")): classify_entity(row) for row in rows}
    return rows, regions, _summarize_entities(rows, regions)


def _summarize_entities(
    rows: list[dict[str, Any]], regions: Mapping[str, str]
) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    by_type: dict[str, Counter[str]] = defaultdict(Counter)
    unknown_samples = []
    for row in rows:
        entity_id = str(row.get("entity_id") or "")
        region = regions.get(entity_id, UNCLASSIFIED)
        counts[region] += 1
        by_type[str(row.get("entity_type") or "unknown")][region] += 1
        if region == UNCLASSIFIED and len(unknown_samples) < 25:
            unknown_samples.append(row)
    return {
        "distribution": distribution(counts),
        "by_entity_type": {
            entity_type: distribution(values)
            for entity_type, values in sorted(by_type.items())
        },
        "unclassified_samples": unknown_samples,
    }


def _raw_object_hints(db: DBProtocol) -> dict[str, set[str]]:
    rows = db.fetchall(
        "SELECT raw_object_id, entity_hint FROM raw_records "
        "WHERE source_id = ? GROUP BY raw_object_id, entity_hint",
        ["worldbank_indicators"],
    )
    output: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        item = _as_dict(row)
        if item.get("raw_object_id") and item.get("entity_hint"):
            output[str(item["raw_object_id"])].add(str(item["entity_hint"]))
    return output


def _raw_object_audit(
    db: DBProtocol,
    raw_hints: Mapping[str, set[str]],
    source_markets: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    rows = db.fetchall(
        "SELECT raw_object_id, source_id, object_type, validation_status, "
        "content_size_bytes FROM raw_objects"
    )
    all_counts: Counter[str] = Counter()
    all_bytes: Counter[str] = Counter()
    usable_counts: Counter[str] = Counter()
    usable_bytes: Counter[str] = Counter()
    by_source: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "all_object_count": 0,
            "usable_object_count": 0,
            "all_size_bytes": 0,
            "usable_size_bytes": 0,
            "status_counts": Counter(),
            "region_counts": Counter(),
            "usable_region_counts": Counter(),
        }
    )
    raw_regions: dict[str, str] = {}
    for raw_row in rows:
        row = _as_dict(raw_row)
        raw_object_id = str(row.get("raw_object_id") or "")
        source_id = str(row.get("source_id") or "")
        region = classify_raw_content(
            source_id,
            raw_hints.get(raw_object_id, set()),
            source_markets.get(source_id),
        )
        raw_regions[raw_object_id] = region
        size = int(row.get("content_size_bytes") or 0)
        status = str(row.get("validation_status") or "unknown")
        all_counts[region] += 1
        all_bytes[region] += size
        item = by_source[source_id]
        item["all_object_count"] += 1
        item["all_size_bytes"] += size
        item["status_counts"][status] += 1
        item["region_counts"][region] += 1
        if status == "passed":
            usable_counts[region] += 1
            usable_bytes[region] += size
            item["usable_object_count"] += 1
            item["usable_size_bytes"] += size
            item["usable_region_counts"][region] += 1
    return {
        "retained_object_distribution": distribution(all_counts),
        "retained_size_distribution": distribution(all_bytes),
        "usable_object_distribution": distribution(usable_counts),
        "usable_size_distribution": distribution(usable_bytes),
        "by_source": {
            source_id: {
                **{
                    key: value
                    for key, value in item.items()
                    if not isinstance(value, Counter)
                },
                "status_counts": dict(sorted(item["status_counts"].items())),
                "region_distribution": distribution(item["region_counts"]),
                "usable_region_distribution": distribution(
                    item["usable_region_counts"]
                ),
            }
            for source_id, item in sorted(by_source.items())
        },
    }, raw_regions


def _raw_record_audit(
    db: DBProtocol, source_markets: Mapping[str, Any]
) -> dict[str, Any]:
    rows = db.fetchall(
        "SELECT source_id, entity_hint, record_type, COUNT(*) AS row_count "
        "FROM raw_records GROUP BY source_id, entity_hint, record_type"
    )
    counts: Counter[str] = Counter()
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    for raw_row in rows:
        row = _as_dict(raw_row)
        source_id = str(row.get("source_id") or "")
        count = int(row.get("row_count") or 0)
        region = classify_raw_content(
            source_id,
            [row.get("entity_hint")],
            source_markets.get(source_id),
        )
        counts[region] += count
        by_source[source_id][region] += count
    return {
        "distribution": distribution(counts),
        "by_source": {
            source_id: distribution(values)
            for source_id, values in sorted(by_source.items())
        },
    }


def _candidate_audit(
    db: DBProtocol,
    entity_regions: Mapping[str, str],
    source_policy: Mapping[str, str],
) -> dict[str, Any]:
    rows = db.fetchall(
        "SELECT cf.entity_id, ro.source_id, cf.promotion_status, "
        "cf.evidence_status, cf.qa_eligible, cf.kg_eligible, "
        "COUNT(*) AS row_count FROM candidate_facts cf "
        "JOIN raw_objects ro ON ro.raw_object_id = cf.raw_object_id "
        "WHERE COALESCE(cf.is_active, 1) = 1 "
        "GROUP BY cf.entity_id, ro.source_id, cf.promotion_status, "
        "cf.evidence_status, cf.qa_eligible, cf.kg_eligible"
    )
    counts: Counter[str] = Counter()
    approved: Counter[str] = Counter()
    verified: Counter[str] = Counter()
    qa_eligible: Counter[str] = Counter()
    kg_eligible: Counter[str] = Counter()
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    for raw_row in rows:
        row = _as_dict(raw_row)
        source_id = str(row.get("source_id") or "")
        region = _entity_or_source_region(
            row.get("entity_id"), source_id, entity_regions, source_policy
        )
        count = int(row.get("row_count") or 0)
        counts[region] += count
        by_source[source_id][region] += count
        if str(row.get("promotion_status") or "") in PROMOTED_CANDIDATE_STATUSES:
            approved[region] += count
        if str(row.get("evidence_status") or "") == "verified":
            verified[region] += count
        if bool(row.get("qa_eligible")):
            qa_eligible[region] += count
        if bool(row.get("kg_eligible")):
            kg_eligible[region] += count
    return {
        "distribution": distribution(counts),
        "evidence_verified_distribution": distribution(verified),
        "approved_or_promoted_distribution": distribution(approved),
        "qa_eligible_distribution": distribution(qa_eligible),
        "kg_eligible_distribution": distribution(kg_eligible),
        "by_source": {
            source_id: distribution(values)
            for source_id, values in sorted(by_source.items())
        },
    }


def _atomic_fact_audit(
    db: DBProtocol,
    build_id: str,
    entity_regions: Mapping[str, str],
    source_policy: Mapping[str, str],
) -> dict[str, Any]:
    rows = db.fetchall(
        "SELECT entity_id, source_id, metric_id, COUNT(*) AS fact_count, "
        "MIN(COALESCE(period_start, period_end, as_of_date, report_date)) AS min_date, "
        "MAX(COALESCE(period_end, period_start, as_of_date, report_date)) AS max_date "
        "FROM atomic_facts WHERE build_id = ? AND COALESCE(is_active, 1) = 1 "
        "GROUP BY entity_id, source_id, metric_id",
        [build_id],
    )
    return _summarize_fact_groups(
        rows, entity_regions, source_policy, count_field="fact_count"
    )


def _standardized_fact_audit(
    db: DBProtocol,
    build_id: str,
    entity_regions: Mapping[str, str],
    source_policy: Mapping[str, str],
    metric_categories: Mapping[str, str],
) -> dict[str, Any]:
    rows = db.fetchall(
        "SELECT entity_id, source_id, metric_id, verification_status, frequency, "
        "graph_ready, is_forecast, "
        "COUNT(*) AS fact_count, "
        "SUM(CASE WHEN COALESCE(graph_ready, 0) = 1 THEN 1 ELSE 0 END) "
        "AS graph_ready_count, "
        "MIN(COALESCE(period_start, period_end, as_of_date, report_date)) AS min_date, "
        "MAX(COALESCE(period_end, period_start, as_of_date, report_date)) AS max_date "
        "FROM standardized_facts WHERE build_id = ? "
        "AND COALESCE(is_active, 1) = 1 "
        "GROUP BY entity_id, source_id, metric_id, verification_status, frequency, "
        "graph_ready, is_forecast",
        [build_id],
    )
    report = _summarize_fact_groups(
        rows,
        entity_regions,
        source_policy,
        count_field="fact_count",
        graph_ready_field="graph_ready_count",
        metric_categories=metric_categories,
    )
    return report


def _summarize_fact_groups(
    rows: Iterable[Any],
    entity_regions: Mapping[str, str],
    source_policy: Mapping[str, str],
    *,
    count_field: str,
    graph_ready_field: str | None = None,
    metric_categories: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    rows = list(rows)
    counts: Counter[str] = Counter()
    ready_counts: Counter[str] = Counter()
    historical_ready_counts: Counter[str] = Counter()
    forecast_ready_counts: Counter[str] = Counter()
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    ready_by_source: Counter[str] = Counter()
    historical_ready_by_source: Counter[str] = Counter()
    by_frequency: dict[str, Counter[str]] = defaultdict(Counter)
    by_category: dict[str, Counter[str]] = defaultdict(Counter)
    historical_metric_ids_by_category: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    details = _empty_region_details()
    ready_details = _empty_region_details()
    historical_ready_details = _empty_region_details()
    for raw_row in rows:
        row = _as_dict(raw_row)
        source_id = str(row.get("source_id") or "")
        entity_id = str(row.get("entity_id") or "")
        metric_id = str(row.get("metric_id") or "")
        region = _entity_or_source_region(
            entity_id, source_id, entity_regions, source_policy
        )
        count = int(row.get(count_field) or 0)
        ready = int(row.get(graph_ready_field) or 0) if graph_ready_field else 0
        is_forecast = bool(row.get("is_forecast"))
        historical_ready = ready if not is_forecast else 0
        forecast_ready = ready if is_forecast else 0
        counts[region] += count
        ready_counts[region] += ready
        historical_ready_counts[region] += historical_ready
        forecast_ready_counts[region] += forecast_ready
        by_source[source_id][region] += count
        ready_by_source[source_id] += ready
        historical_ready_by_source[source_id] += historical_ready
        frequency = str(row.get("frequency") or "unknown")
        by_frequency[frequency][region] += count
        category = (
            metric_categories.get(metric_id, "unknown")
            if metric_categories is not None
            else "not_applicable"
        )
        by_category[category][region] += count
        _update_region_details(details[region], row, count)
        if ready:
            _update_region_details(ready_details[region], row, ready)
        if historical_ready:
            _update_region_details(
                historical_ready_details[region], row, historical_ready
            )
            if metric_id:
                historical_metric_ids_by_category[category][region].add(metric_id)
    report = {
        "distribution": distribution(counts),
        "details_by_region": _finalize_region_details(details),
        "by_source": {
            source_id: {
                "fact_count": sum(values.values()),
                "region_distribution": distribution(values),
            }
            for source_id, values in sorted(by_source.items())
        },
        "by_frequency": {
            frequency: distribution(values)
            for frequency, values in sorted(by_frequency.items())
        },
        "by_metric_category": {
            category: distribution(values)
            for category, values in sorted(by_category.items())
        },
    }
    if graph_ready_field:
        report["graph_ready_distribution"] = distribution(ready_counts)
        report["historical_graph_ready_distribution"] = distribution(
            historical_ready_counts
        )
        report["forecast_graph_ready_distribution"] = distribution(
            forecast_ready_counts
        )
        report["graph_ready_details_by_region"] = _finalize_region_details(
            ready_details
        )
        report["historical_graph_ready_details_by_region"] = _finalize_region_details(
            historical_ready_details
        )
        report["historical_metric_family_coverage"] = _metric_family_coverage(
            historical_metric_ids_by_category
        )
        for source_id in by_source:
            report["by_source"][source_id]["graph_ready_count"] = int(
                ready_by_source[source_id]
            )
            report["by_source"][source_id]["historical_graph_ready_count"] = int(
                historical_ready_by_source[source_id]
            )
    return report


def _metric_categories(db: DBProtocol, build_id: str) -> dict[str, str]:
    rows = db.fetchall(
        "SELECT metric_id, metric_category FROM metrics WHERE build_id = ?",
        [build_id],
    )
    return {
        str(row["metric_id"]): str(row["metric_category"] or "unknown") for row in rows
    }


def _derived_fact_audit(
    db: DBProtocol,
    build_id: str,
    input_build_id: str,
    entity_regions: Mapping[str, str],
) -> tuple[dict[str, Any], dict[str, str]]:
    rows = db.fetchall(
        "SELECT derived_type, entity_scope, scope_id, scope_entity_ids, "
        "scope_source, COUNT(*) AS row_count FROM derived_facts "
        "WHERE build_id = ? AND input_build_id = ? "
        "AND COALESCE(is_active, 1) = 1 "
        "AND verification_status IN ('single_source', 'cross_verified') "
        "GROUP BY derived_type, entity_scope, scope_id, scope_entity_ids, scope_source",
        [build_id, input_build_id],
    )
    counts: Counter[str] = Counter()
    by_type: dict[str, Counter[str]] = defaultdict(Counter)
    scope_votes: dict[str, set[str]] = defaultdict(set)
    for raw_row in rows:
        row = _as_dict(raw_row)
        entity_scope = _json_dict(row.get("entity_scope"))
        entity_ids = set(_json_list(row.get("scope_entity_ids")))
        if entity_scope.get("entity_id"):
            entity_ids.add(str(entity_scope["entity_id"]))
        entity_ids.update(
            str(value) for value in entity_scope.get("entity_ids", []) if value
        )
        scope_id = str(row.get("scope_id") or "")
        if not entity_ids and scope_id in entity_regions:
            entity_ids.add(scope_id)
        region = classify_entity_scope(entity_ids, entity_regions)
        count = int(row.get("row_count") or 0)
        counts[region] += count
        by_type[str(row.get("derived_type") or "unknown")][region] += count
        if scope_id:
            scope_votes[scope_id].add(region)
    scope_regions = {
        scope_id: next(iter(regions)) if len(regions) == 1 else MIXED_GLOBAL
        for scope_id, regions in scope_votes.items()
    }
    return {
        "distribution": distribution(counts),
        "by_derived_type": {
            derived_type: distribution(values)
            for derived_type, values in sorted(by_type.items())
        },
        "scope_region_count": dict(sorted(Counter(scope_regions.values()).items())),
    }, scope_regions


def _company_profile_audit(
    db: DBProtocol,
    fact_build_id: str,
    entity_build_id: str,
    entity_rows: Iterable[Mapping[str, Any]],
    entity_regions: Mapping[str, str],
) -> dict[str, Any]:
    companies = {
        str(row.get("entity_id")): row
        for row in entity_rows
        if str(row.get("entity_type") or "") == "company"
    }
    rows = db.fetchall(
        "SELECT sf.entity_id, sf.metric_id, sf.fiscal_year "
        "FROM standardized_facts sf JOIN canonical_entities ce "
        "ON ce.entity_id = sf.entity_id AND ce.build_id = ? "
        "WHERE sf.build_id = ? AND ce.entity_type = 'company' "
        "AND COALESCE(sf.is_active, 1) = 1 "
        "AND COALESCE(sf.graph_ready, 0) = 1 "
        "AND COALESCE(sf.is_forecast, 0) = 0 "
        "AND sf.fiscal_quarter = 'FY' AND sf.fiscal_year IS NOT NULL "
        "AND sf.metric_id IN ("
        + ",".join("?" for _ in COMPANY_PROFILE_METRICS)
        + ") GROUP BY sf.entity_id, sf.metric_id, sf.fiscal_year",
        [entity_build_id, fact_build_id, *sorted(COMPANY_PROFILE_METRICS)],
    )
    metric_years: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    for raw_row in rows:
        row = _as_dict(raw_row)
        metric_years[str(row["entity_id"])][str(row["metric_id"])].add(
            int(row["fiscal_year"])
        )

    company_counts: Counter[str] = Counter()
    passing_counts: Counter[str] = Counter()
    by_region: dict[str, dict[str, Any]] = {
        region: {"company_count": 0, "passing_company_count": 0}
        for region in REGION_BUCKETS
    }
    failed_samples: dict[str, list[dict[str, Any]]] = {
        region: [] for region in REGION_BUCKETS
    }
    for entity_id, company in companies.items():
        region = entity_regions.get(entity_id, UNCLASSIFIED)
        company_counts[region] += 1
        by_region[region]["company_count"] += 1
        covered_metrics = {
            metric_id
            for metric_id, years in metric_years.get(entity_id, {}).items()
            if len(years) >= 5
        }
        passed = (
            len(covered_metrics) >= 3
            and bool(covered_metrics & COMPANY_PROFILE_INCOME_METRICS)
            and bool(covered_metrics & COMPANY_PROFILE_POSITION_METRICS)
        )
        if passed:
            passing_counts[region] += 1
            by_region[region]["passing_company_count"] += 1
        elif len(failed_samples[region]) < 20:
            failed_samples[region].append(
                {
                    "entity_id": entity_id,
                    "canonical_name": company.get("canonical_name"),
                    "covered_metric_ids": sorted(covered_metrics),
                }
            )
    for region, item in by_region.items():
        item["profile_pass_ratio"] = _ratio(
            item["passing_company_count"], item["company_count"]
        )
    return {
        "policy_id": "cross_region_company_profile_v1",
        "minimum_years_per_metric": 5,
        "minimum_covered_metric_count": 3,
        "required_income_metric_group": sorted(COMPANY_PROFILE_INCOME_METRICS),
        "required_position_metric_group": sorted(COMPANY_PROFILE_POSITION_METRICS),
        "company_distribution": distribution(company_counts),
        "passing_company_distribution": distribution(passing_counts),
        "by_region": by_region,
        "failed_company_samples": failed_samples,
    }


def _qa_constructible_audit(
    db: DBProtocol,
    standardized_report: Mapping[str, Any],
    derived_report: Mapping[str, Any],
    *,
    kg_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    kg_distributions = (
        kg_report.get("classified_node_type_distributions", {}) if kg_report else {}
    )
    fact_distribution = (
        kg_distributions.get("Fact")
        or standardized_report["historical_graph_ready_distribution"]
    )
    t2_counts = Counter(fact_distribution["bucket_counts"])
    t3_counts: Counter[str] = Counter()
    unmapped_types = []
    derived_by_type = (
        kg_report.get("derived_by_type", {})
        if kg_report
        else derived_report["by_derived_type"]
    )
    for derived_type, item in derived_by_type.items():
        counts = item["bucket_counts"]
        if derived_type in T2_DERIVED_TYPES:
            t2_counts.update(counts)
        elif derived_type in T3_DERIVED_TYPES:
            t3_counts.update(counts)
        else:
            unmapped_types.append(derived_type)
    t2 = distribution(t2_counts)
    t3 = distribution(t3_counts)
    combined_total = FINSEARCHCOMP_REGIONAL_REFERENCE["combined_t2_t3"]["total_count"]
    t2_weight = FINSEARCHCOMP_REGIONAL_REFERENCE["t2"]["total_count"] / combined_total
    t3_weight = FINSEARCHCOMP_REGIONAL_REFERENCE["t3"]["total_count"] / combined_total
    weighted_share = (
        t2["greater_china_share"] * t2_weight + t3["greater_china_share"] * t3_weight
    )
    sample_row = db.fetchone("SELECT COUNT(*) AS row_count FROM qa_samples")
    materialized_count = int(
        _as_dict(sample_row).get("row_count", 0) if sample_row else 0
    )
    return {
        "measure_type": (
            "pinned_kg_constructibility_proxy"
            if kg_report
            else "pre_build_constructibility_proxy"
        ),
        "materialized_qa_sample_count": materialized_count,
        "t2_proxy_distribution": t2,
        "t3_proxy_distribution": t3,
        "benchmark_task_weights": {"T2": t2_weight, "T3": t3_weight},
        "benchmark_weighted_greater_china_share": weighted_share,
        "unmapped_derived_types": sorted(unmapped_types),
        "limitations": [
            "T2 proxy counts pinned KG Fact nodes plus simple DerivedFact nodes.",
            "T3 proxy counts pinned KG temporal, scope, ranking and screening DerivedFact nodes.",
            "The proxy is not a substitute for a regenerated, quality-gated QA build.",
        ],
    }


def _fact_universe_audit(
    db: DBProtocol,
    universe_build_id: str,
) -> dict[str, Any]:
    if not universe_build_id:
        return {
            "universe_build_id": None,
            "status": "not_pinned",
            "distribution": distribution({}),
            "by_source": {},
        }
    build_row = db.fetchone(
        "SELECT * FROM fact_universe_builds WHERE universe_build_id = ?",
        [universe_build_id],
    )
    if not build_row:
        return {
            "universe_build_id": universe_build_id,
            "status": "missing",
            "distribution": distribution({}),
            "by_source": {},
        }
    count_rows = db.fetchall(
        "SELECT region_bucket, COUNT(*) AS row_count "
        "FROM fact_universe_members WHERE universe_build_id = ? "
        "GROUP BY region_bucket",
        [universe_build_id],
    )
    counts = Counter(
        {str(row["region_bucket"]): int(row["row_count"]) for row in count_rows}
    )
    source_rows = db.fetchall(
        "SELECT sf.source_id, m.region_bucket, COUNT(*) AS row_count "
        "FROM fact_universe_members m "
        "JOIN standardized_facts sf ON sf.fact_id = m.fact_id "
        "WHERE m.universe_build_id = ? "
        "GROUP BY sf.source_id, m.region_bucket",
        [universe_build_id],
    )
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    for raw_row in source_rows:
        row = _as_dict(raw_row)
        by_source[str(row.get("source_id") or "unknown")][
            str(row.get("region_bucket") or UNCLASSIFIED)
        ] += int(row.get("row_count") or 0)
    derived_count_rows = db.fetchall(
        "SELECT region_bucket, COUNT(*) AS row_count "
        "FROM fact_universe_derived_members WHERE universe_build_id = ? "
        "GROUP BY region_bucket",
        [universe_build_id],
    )
    derived_counts = Counter(
        {str(row["region_bucket"]): int(row["row_count"]) for row in derived_count_rows}
    )
    derived_type_rows = db.fetchall(
        "SELECT d.derived_type, m.region_bucket, COUNT(*) AS row_count "
        "FROM fact_universe_derived_members m "
        "JOIN derived_facts d ON d.derived_id = m.derived_id "
        "WHERE m.universe_build_id = ? "
        "GROUP BY d.derived_type, m.region_bucket",
        [universe_build_id],
    )
    derived_by_type: dict[str, Counter[str]] = defaultdict(Counter)
    for raw_row in derived_type_rows:
        row = _as_dict(raw_row)
        derived_by_type[str(row.get("derived_type") or "unknown")][
            str(row.get("region_bucket") or UNCLASSIFIED)
        ] += int(row.get("row_count") or 0)
    build = _as_dict(build_row)
    return {
        "universe_build_id": universe_build_id,
        "input_fact_build_id": build.get("input_fact_build_id"),
        "policy_id": build.get("policy_id"),
        "policy_version": build.get("policy_version"),
        "target_greater_china_share": float(
            build.get("target_greater_china_share") or 0
        ),
        "recorded_actual_greater_china_share": float(
            build.get("actual_greater_china_share") or 0
        ),
        "status": build.get("status"),
        "quality_status": build.get("quality_status"),
        "membership_manifest_hash": build.get("membership_manifest_hash"),
        "distribution": distribution(counts),
        "derived_distribution": distribution(derived_counts),
        "derived_by_type": {
            derived_type: distribution(type_counts)
            for derived_type, type_counts in sorted(derived_by_type.items())
        },
        "by_source": {
            source_id: distribution(values)
            for source_id, values in sorted(by_source.items())
        },
    }


def _source_document_audit(
    db: DBProtocol,
    build_id: str,
    entity_regions: Mapping[str, str],
    source_policy: Mapping[str, str],
) -> dict[str, Any]:
    if not build_id:
        return {"distribution": distribution({}), "by_source": {}}
    rows = db.fetchall(
        "SELECT entity_id, source_id, report_type, form_type, COUNT(*) AS row_count "
        "FROM source_documents WHERE build_id = ? AND document_status = 'passed' "
        "AND COALESCE(is_active, 1) = 1 "
        "GROUP BY entity_id, source_id, report_type, form_type",
        [build_id],
    )
    counts: Counter[str] = Counter()
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    for raw_row in rows:
        row = _as_dict(raw_row)
        source_id = str(row.get("source_id") or "")
        region = _entity_or_source_region(
            row.get("entity_id"), source_id, entity_regions, source_policy
        )
        count = int(row.get("row_count") or 0)
        counts[region] += count
        by_source[source_id][region] += count
    return {
        "distribution": distribution(counts),
        "by_source": {
            source_id: distribution(values)
            for source_id, values in sorted(by_source.items())
        },
    }


def _kg_region_audit(
    db: DBProtocol,
    active_kg: Mapping[str, Any],
    entity_report: Mapping[str, Any],
    standardized_report: Mapping[str, Any],
    derived_report: Mapping[str, Any],
    document_report: Mapping[str, Any],
    entity_regions: Mapping[str, str],
    raw_regions: Mapping[str, str],
    scope_regions: Mapping[str, str],
    entity_build_id: str,
    source_policy: Mapping[str, str],
) -> dict[str, Any]:
    kg_build_id = str(active_kg["kg_build_id"])
    node_rows = db.fetchall(
        "SELECT node_type, COUNT(*) AS node_count FROM kg_nodes "
        "WHERE kg_build_id = ? GROUP BY node_type",
        [kg_build_id],
    )
    node_type_counts = {
        str(row["node_type"]): int(row["node_count"]) for row in node_rows
    }
    region_counts: Counter[str] = Counter()
    region_counts.update(entity_report["distribution"]["bucket_counts"])
    fact_rows = db.fetchall(
        "SELECT sf.entity_id, sf.source_id, COUNT(*) AS row_count "
        "FROM kg_nodes n JOIN standardized_facts sf ON sf.fact_id = n.source_pk "
        "WHERE n.kg_build_id = ? AND n.node_type = 'Fact' "
        "GROUP BY sf.entity_id, sf.source_id",
        [kg_build_id],
    )
    kg_fact_counts: Counter[str] = Counter()
    for raw_row in fact_rows:
        row = _as_dict(raw_row)
        region = _entity_or_source_region(
            row.get("entity_id"),
            str(row.get("source_id") or ""),
            entity_regions,
            source_policy,
        )
        kg_fact_counts[region] += int(row.get("row_count") or 0)
    kg_fact_distribution = distribution(kg_fact_counts)
    region_counts.update(kg_fact_counts)

    derived_rows = db.fetchall(
        "SELECT d.derived_type, d.entity_scope, d.scope_id, "
        "d.scope_entity_ids, COUNT(*) AS row_count "
        "FROM kg_nodes n JOIN derived_facts d ON d.derived_id = n.source_pk "
        "WHERE n.kg_build_id = ? AND n.node_type = 'DerivedFact' "
        "GROUP BY d.derived_type, d.entity_scope, d.scope_id, d.scope_entity_ids",
        [kg_build_id],
    )
    kg_derived_counts: Counter[str] = Counter()
    kg_derived_by_type: dict[str, Counter[str]] = defaultdict(Counter)
    for raw_row in derived_rows:
        row = _as_dict(raw_row)
        entity_scope = _json_dict(row.get("entity_scope"))
        entity_ids = {str(value) for value in _json_list(row.get("scope_entity_ids"))}
        if entity_scope.get("entity_id"):
            entity_ids.add(str(entity_scope["entity_id"]))
        entity_ids.update(
            str(value) for value in entity_scope.get("entity_ids", []) if value
        )
        scope_id = str(row.get("scope_id") or "")
        if not entity_ids and scope_id in entity_regions:
            entity_ids.add(scope_id)
        region = classify_entity_scope(entity_ids, entity_regions)
        count = int(row.get("row_count") or 0)
        derived_type = str(row.get("derived_type") or "unknown")
        kg_derived_counts[region] += count
        kg_derived_by_type[derived_type][region] += count
    kg_derived_distribution = distribution(kg_derived_counts)
    region_counts.update(kg_derived_counts)
    region_counts.update(document_report["distribution"]["bucket_counts"])

    security_rows = db.fetchall(
        "SELECT security_id, company_entity_id, security_type, market, country, "
        "exchange FROM canonical_securities WHERE build_id = ? "
        "AND COALESCE(is_active, 1) = 1",
        [entity_build_id],
    )
    security_counts: Counter[str] = Counter()
    for raw_row in security_rows:
        row = _as_dict(raw_row)
        company_id = str(row.get("company_entity_id") or "")
        region = entity_regions.get(company_id)
        if not region:
            region = classify_entity(
                {
                    "entity_id": row.get("security_id"),
                    "entity_type": "security",
                    "market": row.get("market"),
                    "country": row.get("country"),
                    "exchange": row.get("exchange"),
                }
            )
        security_counts[region] += 1
    region_counts.update(security_counts)

    raw_node_rows = db.fetchall(
        "SELECT source_pk FROM kg_nodes WHERE kg_build_id = ? "
        "AND node_type = 'RawObject'",
        [kg_build_id],
    )
    raw_node_counts: Counter[str] = Counter(
        raw_regions.get(str(row["source_pk"]), UNCLASSIFIED) for row in raw_node_rows
    )
    region_counts.update(raw_node_counts)

    entity_set_rows = db.fetchall(
        "SELECT source_pk FROM kg_nodes WHERE kg_build_id = ? "
        "AND node_type = 'EntitySet'",
        [kg_build_id],
    )
    entity_set_counts: Counter[str] = Counter(
        scope_regions.get(str(row["source_pk"]), UNCLASSIFIED)
        for row in entity_set_rows
    )
    region_counts.update(entity_set_counts)

    regional_type_total = sum(region_counts.values())
    total_nodes = int(active_kg.get("node_count") or sum(node_type_counts.values()))
    shared_infrastructure = max(total_nodes - regional_type_total, 0)
    return {
        "kg_build_id": kg_build_id,
        "node_count": total_nodes,
        "edge_count": int(active_kg.get("edge_count") or 0),
        "node_type_counts": dict(sorted(node_type_counts.items())),
        "region_addressable_node_distribution": distribution(region_counts),
        "shared_infrastructure_node_count": shared_infrastructure,
        "shared_infrastructure_share": _ratio(shared_infrastructure, total_nodes),
        "classified_node_type_distributions": {
            "Entity": entity_report["distribution"],
            "Fact": kg_fact_distribution,
            "DerivedFact": kg_derived_distribution,
            "SourceDocument": document_report["distribution"],
            "Security": distribution(security_counts),
            "RawObject": distribution(raw_node_counts),
            "EntitySet": distribution(entity_set_counts),
        },
        "derived_by_type": {
            derived_type: distribution(values)
            for derived_type, values in sorted(kg_derived_by_type.items())
        },
    }


def _summary_matrix(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [
        ("raw_usable_objects", report["raw_objects"]["usable_object_distribution"]),
        ("raw_usable_bytes", report["raw_objects"]["usable_size_distribution"]),
        ("raw_records", report["raw_records"]["distribution"]),
        ("canonical_entities", report["canonical_entities"]["distribution"]),
        ("source_documents", report["source_documents"]["distribution"]),
        ("candidate_facts", report["candidate_facts"]["distribution"]),
        ("atomic_facts", report["atomic_facts"]["distribution"]),
        ("standardized_facts", report["standardized_facts"]["distribution"]),
        (
            "graph_ready_facts",
            report["standardized_facts"]["graph_ready_distribution"],
        ),
        (
            "historical_graph_ready_facts",
            report["standardized_facts"]["historical_graph_ready_distribution"],
        ),
        ("fact_universe_members", report["fact_universe"]["distribution"]),
        (
            "kg_fact_nodes",
            report["knowledge_graph"]["classified_node_type_distributions"]["Fact"],
        ),
        (
            "kg_derived_fact_nodes",
            report["knowledge_graph"]["classified_node_type_distributions"][
                "DerivedFact"
            ],
        ),
        ("derived_facts", report["derived_facts"]["distribution"]),
        (
            "kg_region_addressable_nodes",
            report["knowledge_graph"]["region_addressable_node_distribution"],
        ),
    ]
    return [{"layer": layer, **dist} for layer, dist in rows]


def _capability_dimensions(report: Mapping[str, Any]) -> dict[str, Any]:
    graph_ready = report["standardized_facts"]["historical_graph_ready_distribution"]
    entities = report["canonical_entities"]["distribution"]
    metrics = report["standardized_facts"]["historical_metric_family_coverage"]
    companies = report["company_profile_capability"]
    qa_capability = report["qa_constructible_capability"]
    company_pass_distribution = companies["passing_company_distribution"]
    serving_facts = report["fact_universe"]["distribution"]
    kg_facts = report["knowledge_graph"]["classified_node_type_distributions"]["Fact"]
    return {
        "graph_ready_fact_share": {
            "greater_china_share": graph_ready["greater_china_share"],
            "greater_china_count": graph_ready["bucket_counts"][GREATER_CHINA],
            "international_broad_count": graph_ready["international_broad_count"],
        },
        "serving_fact_universe_share": {
            "greater_china_share": serving_facts["greater_china_share"],
            "greater_china_count": serving_facts["bucket_counts"][GREATER_CHINA],
            "international_broad_count": serving_facts["international_broad_count"],
            "universe_build_id": report["fact_universe"].get("universe_build_id"),
        },
        "kg_fact_share": {
            "greater_china_share": kg_facts["greater_china_share"],
            "greater_china_count": kg_facts["bucket_counts"][GREATER_CHINA],
            "international_broad_count": kg_facts["international_broad_count"],
        },
        "entity_share": {
            "greater_china_share": entities["greater_china_share"],
            "greater_china_count": entities["bucket_counts"][GREATER_CHINA],
            "international_broad_count": entities["international_broad_count"],
        },
        "metric_family_coverage": {
            "greater_china_union_coverage_ratio": metrics[
                "greater_china_union_coverage_ratio"
            ],
            "greater_china_metric_count": metrics["greater_china_metric_count"],
            "union_metric_count": metrics["union_metric_count"],
            "by_metric_family": metrics["by_metric_family"],
        },
        "company_profile_pass_share": {
            "greater_china_share_of_passing_companies": (
                company_pass_distribution["greater_china_share"]
            ),
            "greater_china_passing_company_count": (
                company_pass_distribution["bucket_counts"][GREATER_CHINA]
            ),
            "greater_china_within_region_pass_ratio": companies["by_region"][
                GREATER_CHINA
            ]["profile_pass_ratio"],
            "international_broad_passing_company_count": (
                company_pass_distribution["international_broad_count"]
            ),
        },
        "qa_constructible_candidate_share": {
            "measure_type": qa_capability["measure_type"],
            "benchmark_weighted_greater_china_share": qa_capability[
                "benchmark_weighted_greater_china_share"
            ],
            "t2_greater_china_share": qa_capability["t2_proxy_distribution"][
                "greater_china_share"
            ],
            "t3_greater_china_share": qa_capability["t3_proxy_distribution"][
                "greater_china_share"
            ],
            "materialized_qa_sample_count": qa_capability[
                "materialized_qa_sample_count"
            ],
        },
    }


def _balance_assessment(report: Mapping[str, Any]) -> dict[str, Any]:
    matrix = {row["layer"]: row for row in report["summary_matrix"]}
    graph_share_all = float(matrix["graph_ready_facts"]["greater_china_share"])
    graph_share = float(matrix["historical_graph_ready_facts"]["greater_china_share"])
    serving_share = float(matrix["fact_universe_members"]["greater_china_share"])
    kg_fact_share = float(matrix["kg_fact_nodes"]["greater_china_share"])
    entity_share = float(matrix["canonical_entities"]["greater_china_share"])
    document_share = float(matrix["source_documents"]["greater_china_share"])
    derived_share = float(matrix["derived_facts"]["greater_china_share"])
    capability = report["capability_dimensions"]
    qa_share = float(
        capability["qa_constructible_candidate_share"][
            "benchmark_weighted_greater_china_share"
        ]
    )
    metric_coverage = float(
        capability["metric_family_coverage"]["greater_china_union_coverage_ratio"]
    )
    company_pass_share = float(
        capability["company_profile_pass_share"][
            "greater_china_share_of_passing_companies"
        ]
    )
    reference = FINSEARCHCOMP_REGIONAL_REFERENCE["combined_t2_t3"][
        "greater_china_share"
    ]
    status = regional_alignment_status(qa_share)
    findings = []
    if graph_share < 0.10:
        findings.append(
            "大中华区在完整历史 graph-ready 归档事实中仍严重不足；"
            "服务层平衡不能替代继续扩充权威来源。"
        )
    if serving_share < INTERNAL_GREATER_CHINA_MINIMUM_SHARE:
        findings.append("Fact Universe 未达到大中华区最低 40% 的内部合同。")
    if abs(serving_share - kg_fact_share) > 1e-12:
        findings.append("KG Fact 节点分布与其固定的 Fact Universe 不一致。")
    if derived_share < graph_share:
        findings.append("大中华区从 graph-ready 事实到派生事实时占比进一步下降。")
    if entity_share > graph_share * 3:
        findings.append("实体覆盖明显宽于结构化事实密度，仅看公司数会高估区域平衡度。")
    if document_share > graph_share * 3:
        findings.append("文档覆盖明显强于可用于图推理的数值事实覆盖。")
    if report["structured_greater_china_sources_without_active_facts"]:
        findings.append(
            "多个大中华区权威宏观与市场来源仍停留在 Raw 层，尚未贡献 active facts。"
        )
    if report["document_index_gaps"]:
        findings.append("部分已校验披露文件尚未进入 source_documents 索引。")
    if qa_share < INTERNAL_GREATER_CHINA_MINIMUM_SHARE:
        findings.append("T2/T3 可构造性代理未达到大中华区最低 40% 的内部 QA 合同。")
    if metric_coverage < INTERNAL_GREATER_CHINA_MINIMUM_SHARE:
        findings.append("大中华区历史指标族覆盖仍明显窄于全库指标集合。")
    return {
        "status": status,
        "primary_alignment_measure": "qa_constructible_candidate_share",
        "qa_constructible_greater_china_share": qa_share,
        "graph_ready_greater_china_share": graph_share,
        "serving_fact_universe_greater_china_share": serving_share,
        "kg_fact_greater_china_share": kg_fact_share,
        "all_period_graph_ready_greater_china_share": graph_share_all,
        "derived_greater_china_share": derived_share,
        "entity_greater_china_share": entity_share,
        "document_greater_china_share": document_share,
        "metric_family_coverage_ratio": metric_coverage,
        "company_profile_pass_greater_china_share": company_pass_share,
        "finsearchcomp_combined_t2_t3_reference_share": reference,
        "internal_minimum_greater_china_share": (INTERNAL_GREATER_CHINA_MINIMUM_SHARE),
        "alignment_band": {
            "lower": reference - BENCHMARK_ALIGNMENT_TOLERANCE,
            "upper": reference + BENCHMARK_ALIGNMENT_TOLERANCE,
        },
        "qa_constructible_share_gap_vs_reference": qa_share - reference,
        "graph_ready_share_gap_vs_reference": graph_share - reference,
        "findings": findings,
    }


def _regional_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# 国际与大中华区数据占比审计",
        "",
        f"- audit_version: {report['audit_version']}",
        f"- generated_at: {report['generated_at']}",
        f"- active_kg: `{report['pinned_builds']['kg_build_id']}`",
        f"- status: {report['balance_assessment']['status']}",
        "- benchmark_market: `greater_china`",
        "- internal_region_scope: `mainland_hong_kong_macau`",
        "- 当前内部范围：中国大陆、香港、澳门；台湾尚未纳入当前权威源合同",
        "- International broad: international + mixed_global",
        "",
        "## 核心占比",
        "",
        "| 层级 | 大中华区 | 国际 | 混合/全球 | 未分类 | 大中华区占比 | 广义国际占比 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    byte_layers = {"raw_usable_bytes"}
    for row in report["summary_matrix"]:
        counts = row["bucket_counts"]
        formatter = _human_bytes if row["layer"] in byte_layers else _number
        lines.append(
            "| {layer} | {gc} | {intl} | {mixed} | {unknown} | {gc_share} | {intl_share} |".format(
                layer=row["layer"],
                gc=formatter(counts[GREATER_CHINA]),
                intl=formatter(counts[INTERNATIONAL]),
                mixed=formatter(counts[MIXED_GLOBAL]),
                unknown=formatter(counts[UNCLASSIFIED]),
                gc_share=_percent(row["greater_china_share"]),
                intl_share=_percent(row["international_broad_share"]),
            )
        )

    reference = report["finsearchcomp_reference"]
    lines.extend(
        [
            "",
            "## FinSearchComp T2/T3 地域参考",
            "",
            "| task | Global | Greater China | Greater China share |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for task_key, task_label in (
        ("t2", "T2"),
        ("t3", "T3"),
        ("combined_t2_t3", "T2+T3"),
    ):
        item = reference[task_key]
        lines.append(
            f"| {task_label} | {_number(item['global_count'])} | "
            f"{_number(item['greater_china_count'])} | "
            f"{_percent(item['greater_china_share'])} |"
        )

    capability = report["capability_dimensions"]
    fact_capability = capability["graph_ready_fact_share"]
    serving_capability = capability["serving_fact_universe_share"]
    kg_fact_capability = capability["kg_fact_share"]
    entity_capability = capability["entity_share"]
    metric_capability = capability["metric_family_coverage"]
    company_capability = capability["company_profile_pass_share"]
    qa_capability = capability["qa_constructible_candidate_share"]
    lines.extend(
        [
            "",
            "## 七维能力评估",
            "",
            "| 维度 | 大中华区指标 | 补充信息 |",
            "| --- | ---: | --- |",
            "| Historical graph-ready Fact Share | "
            f"{_percent(fact_capability['greater_china_share'])} | "
            f"{_number(fact_capability['greater_china_count'])} facts |",
            "| Serving Fact Universe Share | "
            f"{_percent(serving_capability['greater_china_share'])} | "
            f"{_number(serving_capability['greater_china_count'])} facts; "
            f"`{serving_capability['universe_build_id'] or 'not_pinned'}` |",
            "| KG Fact Share | "
            f"{_percent(kg_fact_capability['greater_china_share'])} | "
            f"{_number(kg_fact_capability['greater_china_count'])} Fact nodes |",
            "| Entity Share | "
            f"{_percent(entity_capability['greater_china_share'])} | "
            f"{_number(entity_capability['greater_china_count'])} entities |",
            "| Metric-family Coverage | "
            f"{_percent(metric_capability['greater_china_union_coverage_ratio'])} | "
            f"{_number(metric_capability['greater_china_metric_count'])}/"
            f"{_number(metric_capability['union_metric_count'])} unique metrics |",
            "| Company-profile Pass Share | "
            f"{_percent(company_capability['greater_china_share_of_passing_companies'])} | "
            "within-region pass rate "
            f"{_percent(company_capability['greater_china_within_region_pass_ratio'])} |",
            "| QA-constructible Candidate Share | "
            f"{_percent(qa_capability['benchmark_weighted_greater_china_share'])} | "
            f"T2 {_percent(qa_capability['t2_greater_china_share'])}; "
            f"T3 {_percent(qa_capability['t3_greater_china_share'])}; proxy |",
        ]
    )

    lines.extend(
        [
            "",
            "## 可用 Raw 对象按来源",
            "",
            "| source_id | objects | size | 大中华区 | 国际 | 混合/全球 |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for source_id, item in sorted(
        report["raw_objects"]["by_source"].items(),
        key=lambda pair: (-int(pair[1]["usable_object_count"]), pair[0]),
    ):
        counts = item["usable_region_distribution"]["bucket_counts"]
        lines.append(
            f"| {source_id} | {_number(item['usable_object_count'])} | "
            f"{_human_bytes(item['usable_size_bytes'])} | "
            f"{_number(counts[GREATER_CHINA])} | "
            f"{_number(counts[INTERNATIONAL])} | "
            f"{_number(counts[MIXED_GLOBAL])} |"
        )

    lines.extend(
        [
            "",
            "## Active 标准事实按来源",
            "",
            "| source_id | facts | graph-ready | 历史 graph-ready | 大中华区 | 国际 | 混合/全球 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for source_id, item in sorted(
        report["standardized_facts"]["by_source"].items(),
        key=lambda pair: (-int(pair[1]["fact_count"]), pair[0]),
    ):
        counts = item["region_distribution"]["bucket_counts"]
        lines.append(
            f"| {source_id} | {_number(item['fact_count'])} | "
            f"{_number(item['graph_ready_count'])} | "
            f"{_number(item['historical_graph_ready_count'])} | "
            f"{_number(counts[GREATER_CHINA])} | "
            f"{_number(counts[INTERNATIONAL])} | "
            f"{_number(counts[MIXED_GLOBAL])} |"
        )

    lines.extend(
        [
            "",
            "## 历史 Graph-ready 区域多样性",
            "",
            "| 区域 | facts | entities | metrics | sources | min_date | max_date | facts/entity |",
            "| --- | ---: | ---: | ---: | ---: | --- | --- | ---: |",
        ]
    )
    for region in REGION_BUCKETS:
        item = report["standardized_facts"]["historical_graph_ready_details_by_region"][
            region
        ]
        lines.append(
            f"| {region} | {_number(item['fact_count'])} | "
            f"{_number(item['entity_count'])} | {_number(item['metric_count'])} | "
            f"{_number(item['source_count'])} | {item['min_date'] or ''} | "
            f"{item['max_date'] or ''} | {item['facts_per_entity']:.2f} |"
        )

    kg = report["knowledge_graph"]
    lines.extend(
        [
            "",
            "## KG",
            "",
            f"- nodes: {_number(kg['node_count'])}",
            f"- edges: {_number(kg['edge_count'])}",
            f"- region-addressable nodes: {_number(kg['region_addressable_node_distribution']['total'])}",
            f"- shared infrastructure nodes: {_number(kg['shared_infrastructure_node_count'])} ({_percent(kg['shared_infrastructure_share'])})",
            "",
            "时间、指标、来源定义等共享基础节点不强行归入任何地域；KG 地域占比仅对可归属节点计算。",
            "",
            "## 结论",
            "",
        ]
    )
    for finding in report["balance_assessment"]["findings"]:
        lines.append(f"- {finding}")
    combined_reference = report["finsearchcomp_reference"]["combined_t2_t3"][
        "greater_china_share"
    ]
    historical_share = report["balance_assessment"]["graph_ready_greater_china_share"]
    serving_share = report["balance_assessment"][
        "serving_fact_universe_greater_china_share"
    ]
    kg_fact_share = report["balance_assessment"]["kg_fact_greater_china_share"]
    qa_share = report["balance_assessment"]["qa_constructible_greater_china_share"]
    lines.append(
        "- 历史 graph-ready 大中华区占比为 "
        f"{_percent(historical_share)}；Fact Universe 为 "
        f"{_percent(serving_share)}；KG Fact 节点为 "
        f"{_percent(kg_fact_share)}；T2/T3 可构造性代理为 "
        f"{_percent(qa_share)}，相对 FinSearchComp T2+T3 参考 "
        f"{_percent(combined_reference)} 相差 "
        f"{(qa_share - combined_reference) * 100:.2f} 个百分点。"
    )
    lines.extend(
        [
            "",
            "## 文档索引缺口",
            "",
            "| source_id | usable raw objects | indexed documents | gap |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for item in report["document_index_gaps"]:
        lines.append(
            f"| {item['source_id']} | {_number(item['usable_object_count'])} | "
            f"{_number(item['indexed_document_count'])} | "
            f"{_number(item['gap_count'])} |"
        )
    if not report["document_index_gaps"]:
        lines.append("| - | 0 | 0 | 0 |")

    lines.extend(
        [
            "",
            "## 大中华区尚无输出的派生类型",
            "",
            *(
                f"- `{derived_type}`"
                for derived_type in report[
                    "greater_china_derived_types_without_outputs"
                ]
            ),
        ]
    )
    raw_only = report["structured_greater_china_sources_without_active_facts"]
    lines.extend(
        [
            "",
            "## 大中华区仍停留在 Raw 层的权威来源",
            "",
            *(f"- `{source_id}`" for source_id in raw_only),
            "",
            "这些来源已保存原始材料和元数据，但尚未形成 active standardized facts，不能计入事实库或 KG 推理覆盖。",
            "",
            "## 解释边界",
            "",
            "- 原始对象按内容归属审计；World Bank 中国对象计入大中华区，IMF 多国包计入 mixed_global。",
            "- Fact、DerivedFact 和 Entity 按 canonical entity/scope 归属，而不是按 API 提供方所在地归属。",
            "- historical_graph_ready 遵循当前 is_forecast 元数据；整批来源级 forecast 标记会保守排除其中的历史年份。",
            "- 当前整批被排除的来源："
            + ", ".join(
                f"`{source_id}`"
                for source_id in report["source_wide_forecast_exclusions"]
            )
            + "。",
            "- FinSearchComp T2/T3 的 203/188 地域分布只作为未来 QA 配额参考，不作为 Raw 或 Fact 层硬门槛。",
        ]
    )
    return "\n".join(lines) + "\n"


def _empty_region_details() -> dict[str, dict[str, Any]]:
    return {
        bucket: {
            "fact_count": 0,
            "entities": set(),
            "metrics": set(),
            "sources": set(),
            "min_date": None,
            "max_date": None,
        }
        for bucket in REGION_BUCKETS
    }


def _update_region_details(
    detail: dict[str, Any], row: Mapping[str, Any], count: int
) -> None:
    detail["fact_count"] += count
    if row.get("entity_id"):
        detail["entities"].add(str(row["entity_id"]))
    if row.get("metric_id"):
        detail["metrics"].add(str(row["metric_id"]))
    if row.get("source_id"):
        detail["sources"].add(str(row["source_id"]))
    min_date = _date_text(row.get("min_date"))
    max_date = _date_text(row.get("max_date"))
    if min_date and (detail["min_date"] is None or min_date < detail["min_date"]):
        detail["min_date"] = min_date
    if max_date and (detail["max_date"] is None or max_date > detail["max_date"]):
        detail["max_date"] = max_date


def _finalize_region_details(
    details: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    output = {}
    for region in REGION_BUCKETS:
        item = details[region]
        entity_count = len(item["entities"])
        output[region] = {
            "fact_count": int(item["fact_count"]),
            "entity_count": entity_count,
            "metric_count": len(item["metrics"]),
            "source_count": len(item["sources"]),
            "min_date": item["min_date"],
            "max_date": item["max_date"],
            "facts_per_entity": (
                float(item["fact_count"]) / entity_count if entity_count else 0.0
            ),
        }
    return output


def _metric_family_coverage(
    metric_ids_by_category: Mapping[str, Mapping[str, set[str]]],
) -> dict[str, Any]:
    by_family: dict[str, dict[str, Any]] = {}
    all_greater_china: set[str] = set()
    all_broad_international: set[str] = set()
    for family, regions in sorted(metric_ids_by_category.items()):
        greater_china = set(regions.get(GREATER_CHINA, set()))
        broad_international = set(regions.get(INTERNATIONAL, set())) | set(
            regions.get(MIXED_GLOBAL, set())
        )
        union = greater_china | broad_international
        all_greater_china.update(greater_china)
        all_broad_international.update(broad_international)
        by_family[family] = {
            "greater_china_metric_count": len(greater_china),
            "international_broad_metric_count": len(broad_international),
            "union_metric_count": len(union),
            "shared_metric_count": len(greater_china & broad_international),
            "greater_china_union_coverage_ratio": _ratio(
                len(greater_china), len(union)
            ),
            "greater_china_metric_ids": sorted(greater_china),
            "international_broad_metric_ids": sorted(broad_international),
        }
    union = all_greater_china | all_broad_international
    return {
        "greater_china_metric_count": len(all_greater_china),
        "international_broad_metric_count": len(all_broad_international),
        "union_metric_count": len(union),
        "shared_metric_count": len(all_greater_china & all_broad_international),
        "greater_china_union_coverage_ratio": _ratio(
            len(all_greater_china), len(union)
        ),
        "by_metric_family": by_family,
    }


def _entity_or_source_region(
    entity_id: Any,
    source_id: Any,
    entity_regions: Mapping[str, str],
    source_policy: Mapping[str, str],
) -> str:
    entity_region = entity_regions.get(str(entity_id or ""), UNCLASSIFIED)
    if entity_region != UNCLASSIFIED:
        return entity_region
    return source_policy.get(str(source_id or ""), UNCLASSIFIED)


def _is_greater_china_country(value: str) -> bool:
    if value in GREATER_CHINA_COUNTRY_CODES:
        return True
    return value in {
        "CHINA",
        "PEOPLE'S REPUBLIC OF CHINA",
        "HONG KONG",
        "HONG KONG SAR, CHINA",
        "MACAU",
        "MACAO",
        "MACAO SAR, CHINA",
        "中国",
        "中国大陆",
        "香港",
        "澳门",
    }


def _country_token(value: Any) -> str:
    token = _token(value)
    if token.endswith("_COUNTRY"):
        return token.removesuffix("_COUNTRY")
    return token


def _token(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).upper()


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value is None or value == "":
        return None
    try:
        return json.loads(str(value))
    except (TypeError, ValueError):
        return None


def _json_list(value: Any) -> list[Any]:
    parsed = _json_value(value)
    return parsed if isinstance(parsed, list) else []


def _json_dict(value: Any) -> dict[str, Any]:
    parsed = _json_value(value)
    return parsed if isinstance(parsed, dict) else {}


def _as_dict(row: Any) -> dict[str, Any]:
    return dict(row)


def _date_text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)[:10]


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def _percent(value: Any) -> str:
    return f"{float(value or 0) * 100:.2f}%"


def _number(value: Any) -> str:
    return f"{int(value or 0):,}"


def _human_bytes(value: Any) -> str:
    amount = float(value or 0)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{amount:.2f} {unit}"
        amount /= 1024
    return f"{amount:.2f} TiB"
