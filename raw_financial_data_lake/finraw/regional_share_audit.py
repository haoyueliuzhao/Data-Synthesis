from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from finraw.db.client import DBProtocol


AUDIT_VERSION = "1.0.0"
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
GREATER_CHINA_MARKETS = {"CN", "CHINA", "PRC", "MAINLAND CHINA", "HK", "HONG KONG", "MO", "MACAU"}

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
FINSEARCHCOMP_GREATER_CHINA_REFERENCE_SHARE = 298 / 635


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
        classify_source(source_id)
        for source_id in alias_source_ids
        if source_id
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
    broad_international = (
        bucket_counts[INTERNATIONAL] + bucket_counts[MIXED_GLOBAL]
    )
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


def audit_regional_shares(
    db: DBProtocol,
    config: dict[str, Any],
    output_dir: str | None = None,
) -> dict[str, Any]:
    del config  # The audit is pinned to the active KG contract and DB metadata.
    source_rows = [_as_dict(row) for row in db.fetchall(
        "SELECT source_id, source_name, market, provider, authority_level "
        "FROM source_registry"
    )]
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
    raw_report, raw_regions = _raw_object_audit(
        db, raw_hints, source_markets
    )
    raw_record_report = _raw_record_audit(db, source_markets)
    candidate_report = _candidate_audit(
        db, entity_regions, source_policy
    )
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
    derived_report, scope_regions = _derived_fact_audit(
        db,
        builds["derived_build_id"],
        builds["fact_build_id"],
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
    )

    structured_gc_sources_without_facts = sorted(
        source_id
        for source_id in GREATER_CHINA_SOURCE_IDS
        if raw_report["by_source"].get(source_id, {}).get("usable_object_count", 0)
        and standardized_report["by_source"].get(source_id, {}).get("fact_count", 0) == 0
    )
    document_index_gaps = []
    for source_id in sorted(DISCLOSURE_DOCUMENT_SOURCE_IDS):
        usable_objects = int(
            raw_report["by_source"].get(source_id, {}).get(
                "usable_object_count", 0
            )
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
        if item["total"] > 0
        and item["bucket_counts"][GREATER_CHINA] == 0
    )
    source_wide_forecast_exclusions = sorted(
        source_id
        for source_id, item in standardized_report["by_source"].items()
        if item["graph_ready_count"] > 0
        and item["historical_graph_ready_count"] == 0
    )
    report = {
        "audit_version": AUDIT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope_policy": {
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
        "derived_facts": derived_report,
        "source_documents": document_report,
        "knowledge_graph": kg_report,
        "finsearchcomp_reference": {
            "total_count": 635,
            "greater_china_count": 298,
            "global_count": 337,
            "greater_china_share": FINSEARCHCOMP_GREATER_CHINA_REFERENCE_SHARE,
            "usage": "distribution_reference_only",
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
    report["balance_assessment"] = _balance_assessment(report)
    if output_dir:
        paths = write_regional_share_report(report, output_dir)
        report["written_files"] = [str(path) for path in paths]
    return report


def write_regional_share_report(
    report: dict[str, Any], output_dir: str
) -> list[Path]:
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
        raise RuntimeError("No active successful KG build is available for regional audit")
    return _as_dict(row)


def _pinned_builds(
    db: DBProtocol, active_kg: Mapping[str, Any]
) -> dict[str, str]:
    fact_build_id = str(active_kg.get("input_fact_build_id") or "")
    derived_build_id = str(active_kg.get("input_qa_build_id") or "")
    entity_build_id = str(active_kg.get("input_entity_build_id") or "")
    metric_build_id = str(active_kg.get("input_metric_build_id") or "")
    document_build_id = str(active_kg.get("input_document_build_id") or "")
    if not all([fact_build_id, derived_build_id, entity_build_id, metric_build_id]):
        raise RuntimeError("Active KG does not contain a complete pinned build contract")
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
        "derived_build_id": derived_build_id,
    }


def _entity_alias_sources(
    db: DBProtocol, build_id: str
) -> dict[str, set[str]]:
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
    rows = [_as_dict(row) for row in db.fetchall(
        "SELECT entity_id, canonical_name, entity_type, market, country, "
        "exchange, ticker FROM canonical_entities WHERE build_id = ?",
        [build_id],
    )]
    regions = {
        str(row.get("entity_id")): classify_entity(row) for row in rows
    }
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
                **{key: value for key, value in item.items() if not isinstance(value, Counter)},
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
        report["historical_graph_ready_details_by_region"] = (
            _finalize_region_details(historical_ready_details)
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
        str(row["metric_id"]): str(row["metric_category"] or "unknown")
        for row in rows
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
        "scope_region_count": dict(
            sorted(Counter(scope_regions.values()).items())
        ),
    }, scope_regions


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
    region_counts.update(
        entity_report["distribution"]["bucket_counts"]
    )
    region_counts.update(
        standardized_report["graph_ready_distribution"]["bucket_counts"]
    )
    region_counts.update(derived_report["distribution"]["bucket_counts"])
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
        raw_regions.get(str(row["source_pk"]), UNCLASSIFIED)
        for row in raw_node_rows
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
            "Fact": standardized_report["graph_ready_distribution"],
            "DerivedFact": derived_report["distribution"],
            "SourceDocument": document_report["distribution"],
            "Security": distribution(security_counts),
            "RawObject": distribution(raw_node_counts),
            "EntitySet": distribution(entity_set_counts),
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
        ("derived_facts", report["derived_facts"]["distribution"]),
        (
            "kg_region_addressable_nodes",
            report["knowledge_graph"]["region_addressable_node_distribution"],
        ),
    ]
    return [{"layer": layer, **dist} for layer, dist in rows]


def _balance_assessment(report: Mapping[str, Any]) -> dict[str, Any]:
    matrix = {row["layer"]: row for row in report["summary_matrix"]}
    graph_share_all = float(matrix["graph_ready_facts"]["greater_china_share"])
    graph_share = float(
        matrix["historical_graph_ready_facts"]["greater_china_share"]
    )
    entity_share = float(matrix["canonical_entities"]["greater_china_share"])
    document_share = float(matrix["source_documents"]["greater_china_share"])
    derived_share = float(matrix["derived_facts"]["greater_china_share"])
    reference = FINSEARCHCOMP_GREATER_CHINA_REFERENCE_SHARE
    findings = []
    if graph_share < 0.10:
        findings.append("大中华区在历史 graph-ready 结构化事实中严重不足。")
    if derived_share < graph_share:
        findings.append(
            "大中华区从 graph-ready 事实到派生事实时占比进一步下降。"
        )
    if entity_share > graph_share * 3:
        findings.append(
            "实体覆盖明显宽于结构化事实密度，仅看公司数会高估区域平衡度。"
        )
    if document_share > graph_share * 3:
        findings.append("文档覆盖明显强于可用于图推理的数值事实覆盖。")
    if report["structured_greater_china_sources_without_active_facts"]:
        findings.append(
            "多个大中华区权威宏观与市场来源仍停留在 Raw 层，尚未贡献 active facts。"
        )
    if report["document_index_gaps"]:
        findings.append("部分已校验披露文件尚未进入 source_documents 索引。")
    return {
        "status": "international_heavy" if graph_share < 0.35 else "closer_to_reference",
        "graph_ready_greater_china_share": graph_share,
        "all_period_graph_ready_greater_china_share": graph_share_all,
        "derived_greater_china_share": derived_share,
        "entity_greater_china_share": entity_share,
        "document_greater_china_share": document_share,
        "finsearchcomp_reference_greater_china_share": reference,
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
        "- Greater China scope: 中国大陆、香港、澳门；台湾尚未纳入当前权威源合同",
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

    lines.extend([
        "",
        "## 可用 Raw 对象按来源",
        "",
        "| source_id | objects | size | 大中华区 | 国际 | 混合/全球 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
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

    lines.extend([
        "",
        "## Active 标准事实按来源",
        "",
        "| source_id | facts | graph-ready | 历史 graph-ready | 大中华区 | 国际 | 混合/全球 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
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

    lines.extend([
        "",
        "## 历史 Graph-ready 区域多样性",
        "",
        "| 区域 | facts | entities | metrics | sources | min_date | max_date | facts/entity |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- | ---: |",
    ])
    for region in REGION_BUCKETS:
        item = report["standardized_facts"][
            "historical_graph_ready_details_by_region"
        ][region]
        lines.append(
            f"| {region} | {_number(item['fact_count'])} | "
            f"{_number(item['entity_count'])} | {_number(item['metric_count'])} | "
            f"{_number(item['source_count'])} | {item['min_date'] or ''} | "
            f"{item['max_date'] or ''} | {item['facts_per_entity']:.2f} |"
        )

    kg = report["knowledge_graph"]
    lines.extend([
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
    ])
    for finding in report["balance_assessment"]["findings"]:
        lines.append(f"- {finding}")
    reference = report["finsearchcomp_reference"]["greater_china_share"]
    historical_share = report["balance_assessment"][
        "graph_ready_greater_china_share"
    ]
    lines.append(
        "- 历史 graph-ready 大中华区占比为 "
        f"{_percent(historical_share)}，相对 FinSearchComp 地域参考 "
        f"{_percent(reference)} 相差 {(historical_share - reference) * 100:.2f} 个百分点。"
    )
    lines.extend([
        "",
        "## 文档索引缺口",
        "",
        "| source_id | usable raw objects | indexed documents | gap |",
        "| --- | ---: | ---: | ---: |",
    ])
    for item in report["document_index_gaps"]:
        lines.append(
            f"| {item['source_id']} | {_number(item['usable_object_count'])} | "
            f"{_number(item['indexed_document_count'])} | "
            f"{_number(item['gap_count'])} |"
        )
    if not report["document_index_gaps"]:
        lines.append("| - | 0 | 0 | 0 |")

    lines.extend([
        "",
        "## 大中华区尚无输出的派生类型",
        "",
        *(
            f"- `{derived_type}`"
            for derived_type in report[
                "greater_china_derived_types_without_outputs"
            ]
        ),
    ])
    raw_only = report["structured_greater_china_sources_without_active_facts"]
    lines.extend([
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
        "- 635 道 FinSearchComp 的 298/337 地域分布只作为未来 QA 配额参考，不作为 Raw 或 Fact 层硬门槛。",
    ])
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
    details: Mapping[str, Mapping[str, Any]]
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
