from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from finraw.builds import (
    deactivate_active_rows,
    finish_build,
    start_build,
    versioned_id,
)
from finraw.db.client import DBProtocol

FACT_COLUMNS = [
    "fact_id",
    "entity_id",
    "metric_id",
    "value",
    "value_type",
    "unit",
    "currency",
    "period_start",
    "period_end",
    "fiscal_year",
    "fiscal_quarter",
    "as_of_date",
    "report_date",
    "source_id",
    "raw_object_id",
    "source_field_name",
    "source_page_or_table",
    "extraction_method",
    "confidence_score",
    "verification_status",
    "tolerance",
    "notes",
]

FX_ENTITY_BY_FRED_SERIES = {
    "DEXUSEU": "EUR_USD",
    "DEXJPUS": "USD_JPY",
    "DEXCHUS": "USD_CNY",
    "DTWEXBGS": "USD_BROAD_INDEX",
}

CN_DISCLOSURE_RECORD_TYPES = {
    "cninfo_announcements": "cninfo_pdf_announcement",
    "bse_disclosures": "bse_pdf_announcement",
    "hkex_disclosures": "hkex_pdf_annual_report",
}


def refresh_atomic_facts(
    db: DBProtocol,
    config: dict[str, Any],
    output_dir: str | None = None,
    batch_size: int = 5000,
) -> dict[str, Any]:
    build_id = start_build(
        db, layer="fact_build", command="refresh-atomic-facts", prefix="fact_build"
    )
    for table in [
        "derived_facts",
        "fact_quality_checks",
        "standardized_facts",
        "atomic_facts",
        "source_documents",
    ]:
        deactivate_active_rows(db, table, build_id)
    context = _load_context(db)
    report = {
        "build_id": build_id,
        "inserted_count": 0,
        "source_document_count": 0,
        "promoted_document_candidate_count": 0,
        "source_counts": Counter(),
        "metric_counts": Counter(),
        "skipped_counts": Counter(),
        "notes": [
            "Atomic facts are extracted from structured raw records plus explicitly approved, evidence-verified consolidated statement candidates.",
            "SEC filing HTML and official PRC disclosure PDFs remain indexed in source_documents; only numeric PDF candidates that passed the separate promotion policy become atomic facts.",
        ],
    }
    source_document_count = _refresh_source_documents(db, context, build_id, report)
    report["source_document_count"] = source_document_count

    batch: list[dict[str, Any]] = []
    promotion_updates: list[tuple[str, str]] = []
    for fact in _iter_atomic_facts(db, context, report):
        candidate_id = fact.pop("_candidate_id", None)
        fact = _with_build(fact, build_id)
        if candidate_id:
            promotion_updates.append((fact["fact_id"], candidate_id))
        batch.append(fact)
        if len(batch) >= batch_size:
            db.insert_atomic_facts(batch)
            report["inserted_count"] += len(batch)
            batch.clear()
    if batch:
        db.insert_atomic_facts(batch)
        report["inserted_count"] += len(batch)
    for promoted_fact_id, candidate_id in promotion_updates:
        db.execute(
            "UPDATE candidate_facts SET candidate_state = ?, promotion_status = ?, promoted_fact_id = ? WHERE candidate_id = ?",
            ["promoted_to_atomic_fact", "promoted", promoted_fact_id, candidate_id],
        )
    report["promoted_document_candidate_count"] = len(promotion_updates)

    final_report = {
        "build_id": build_id,
        "inserted_count": report["inserted_count"],
        "source_document_count": report["source_document_count"],
        "promoted_document_candidate_count": report[
            "promoted_document_candidate_count"
        ],
        "source_counts": dict(sorted(report["source_counts"].items())),
        "top_metric_counts": dict(report["metric_counts"].most_common(30)),
        "skipped_counts": dict(sorted(report["skipped_counts"].items())),
        "notes": report["notes"],
    }
    if output_dir:
        paths = write_atomic_facts_report(final_report, output_dir)
        final_report["written_files"] = [str(path) for path in paths]
    finish_build(db, build_id, "success", f"inserted_count={report['inserted_count']}")
    return final_report


def _with_build(fact: dict[str, Any], build_id: str) -> dict[str, Any]:
    stable_fact_id = fact["fact_id"]
    out = dict(fact)
    out["stable_fact_id"] = stable_fact_id
    out["fact_id"] = versioned_id(stable_fact_id, build_id)
    out["build_id"] = build_id
    out["raw_snapshot_id"] = None
    out["is_active"] = 1
    out["superseded_by"] = None
    return out


def write_atomic_facts_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "atomic_facts_report.json"
    md_path = out / "atomic_facts_report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    md_path.write_text(_markdown_report(report), encoding="utf-8")
    return [json_path, md_path]


def _load_context(db: DBProtocol) -> dict[str, Any]:
    metric_rows = [
        dict(row)
        for row in db.fetchall("SELECT * FROM metrics WHERE COALESCE(is_active, 1) = 1")
    ]
    metric_alias_rows = [
        dict(row)
        for row in db.fetchall(
            "SELECT * FROM metric_alias_map WHERE COALESCE(is_active, 1) = 1"
        )
    ]
    entity_alias_rows = [
        dict(row)
        for row in db.fetchall(
            "SELECT * FROM entity_alias_map WHERE COALESCE(is_active, 1) = 1"
        )
    ]
    active_entity_ids = {
        str(row["entity_id"])
        for row in db.fetchall(
            "SELECT entity_id FROM canonical_entities WHERE COALESCE(is_active, 1) = 1"
        )
    }
    source_entity_rows = [
        dict(row)
        for row in db.fetchall(
            "SELECT source_id, source_code, raw_metadata FROM source_entities"
        )
    ]
    try:
        series_map_rows = [
            dict(row)
            for row in db.fetchall(
                "SELECT * FROM source_series_entity_map WHERE COALESCE(is_active, 1) = 1"
            )
        ]
    except Exception:
        series_map_rows = []
    metrics = {row["metric_id"]: row for row in metric_rows}
    metric_aliases = _metric_alias_context(metric_alias_rows)
    entity_aliases = _entity_alias_context(entity_alias_rows)
    return {
        "metrics": metrics,
        "metric_aliases": metric_aliases,
        "entity_aliases": entity_aliases,
        "active_entity_ids": active_entity_ids,
        "source_metadata": _source_metadata_context(source_entity_rows),
        "series_entity_map": _series_entity_map_context(series_map_rows),
    }


def _series_entity_map_context(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    context: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        source_id = row.get("source_id")
        series_id = row.get("series_id")
        if source_id and series_id:
            context[str(source_id)][str(series_id)] = row
    return context


def _source_metadata_context(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = defaultdict(dict)
    for row in rows:
        source_id = row.get("source_id")
        source_code = row.get("source_code")
        if not source_id or not source_code:
            continue
        metadata[source_id][source_code] = _json_value(row.get("raw_metadata"))
    return metadata


def _metric_alias_context(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, tuple[str, float]]]:
    context: dict[str, dict[str, tuple[str, float]]] = defaultdict(dict)
    for row in rows:
        source_id = row.get("source_id")
        concept = row.get("raw_concept_name")
        metric_id = row.get("metric_id")
        if not source_id or not concept or not metric_id:
            continue
        current = context[source_id].get(concept)
        score = float(row.get("confidence_score") or 0)
        if not current or score > current[1]:
            context[source_id][concept] = (metric_id, score)
    return context


def _entity_alias_context(rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    context: dict[str, dict[str, str]] = defaultdict(dict)
    for row in rows:
        source_id = row.get("source_id")
        entity_id = row.get("entity_id")
        if not source_id or not entity_id:
            continue
        for key in [row.get("source_code"), row.get("alias")]:
            if key:
                context[source_id][str(key)] = entity_id
    return context


def _iter_atomic_facts(
    db: DBProtocol, context: dict[str, Any], report: dict[str, Any]
) -> Iterable[dict[str, Any]]:
    rows = db.fetchall(
        """
        SELECT rr.raw_record_id, rr.raw_object_id, rr.source_id, rr.record_type,
               rr.record_key, rr.record_json, rr.entity_hint, rr.metric_hint,
               rr.period_hint, ro.retrieval_time
        FROM raw_records rr
        LEFT JOIN raw_objects ro ON ro.raw_object_id = rr.raw_object_id
        WHERE rr.record_type IN (?, ?, ?, ?)
        """,
        (
            "sec_companyfacts_json",
            "fred_observation",
            "wb_observation",
            "imf_sdmx_response",
        ),
    )
    for row in rows:
        record = dict(row)
        record_type = record.get("record_type")
        if record_type == "sec_companyfacts_json":
            yield from _extract_sec_companyfacts(record, context, report)
        elif record_type == "fred_observation":
            fact = _extract_fred_observation(record, context, report)
            if fact:
                yield fact
        elif record_type == "wb_observation":
            fact = _extract_worldbank_observation(record, context, report)
            if fact:
                yield fact
        elif record_type == "imf_sdmx_response":
            yield from _extract_imf_datamapper(record, context, report)

    yield from _extract_official_publication_facts(db, context, report)
    yield from _extract_approved_document_candidates(db, context, report)


def _extract_official_publication_facts(
    db: DBProtocol,
    context: dict[str, Any],
    report: dict[str, Any],
) -> Iterable[dict[str, Any]]:
    from finraw.official_facts import iter_official_fact_inputs

    for item in iter_official_fact_inputs(db, report):
        entity_id = _lookup_entity(
            context,
            str(item["source_id"]),
            item.get("entity_code"),
            item.get("entity_name"),
        )
        if not entity_id:
            report["skipped_counts"]["official_publication_missing_entity"] += 1
            continue
        if item["metric_id"] not in context["metrics"]:
            report["skipped_counts"]["official_publication_missing_metric"] += 1
            continue
        fact = _fact(
            entity_id=entity_id,
            metric_id=item["metric_id"],
            value=item["value"],
            unit=item["unit"],
            currency=item.get("currency"),
            period_start=item["period_start"],
            period_end=item["period_end"],
            fiscal_year=item.get("fiscal_year"),
            fiscal_quarter=item.get("fiscal_quarter"),
            as_of_date=item.get("as_of_date"),
            report_date=item.get("report_date"),
            source_id=item["source_id"],
            raw_object_id=item.get("raw_object_id"),
            source_field_name=item["source_field_name"],
            source_page_or_table=item.get("source_page_or_table"),
            extraction_method=item["extraction_method"],
            confidence_score=item["confidence_score"],
            verification_status=item["verification_status"],
            tolerance=None,
            notes=_compact_notes(item.get("notes") or {}),
            stable_parts=item["stable_parts"],
        )
        _count_fact(report, fact)
        yield fact


def _extract_approved_document_candidates(
    db: DBProtocol,
    context: dict[str, Any],
    report: dict[str, Any],
) -> Iterable[dict[str, Any]]:
    placeholders = ",".join("?" for _ in CN_DISCLOSURE_RECORD_TYPES)
    rows = db.fetchall(
        f"""
        SELECT cf.candidate_id, cf.raw_object_id, cf.table_id, cf.entity_id,
               cf.matched_metric_id, cf.value, cf.unit, cf.currency,
               cf.period_start, cf.period_end, cf.fiscal_year,
               cf.fiscal_quarter, cf.source_field_name, cf.page_number,
               cf.row_index, cf.column_index, cf.financial_scope_type,
               cf.evidence_sha256, cf.confidence_score,
               cf.cross_check_status, cf.extraction_metadata,
               ro.source_id, ro.source_publish_date
        FROM candidate_facts cf
        JOIN raw_objects ro ON ro.raw_object_id = cf.raw_object_id
        WHERE COALESCE(cf.is_active, 1) = 1
          AND cf.evidence_status = 'verified'
          AND cf.promotion_status IN ('approved_for_atomic_fact', 'promoted')
          AND cf.matched_metric_id IS NOT NULL
          AND ro.source_id IN ({placeholders})
          AND EXISTS (
              SELECT 1
              FROM candidate_fact_evidence cfe
              WHERE cfe.candidate_id = cf.candidate_id
                AND cfe.validation_status = 'verified'
                AND cfe.evidence_sha256 = cf.evidence_sha256
          )
        ORDER BY cf.entity_id, cf.matched_metric_id, cf.period_end,
                 cf.raw_object_id, cf.page_number, cf.row_index,
                 cf.column_index
        """,
        tuple(CN_DISCLOSURE_RECORD_TYPES),
    )
    for raw_row in rows:
        row = dict(raw_row)
        value = _decimal_or_none(row.get("value"))
        metric_id = row.get("matched_metric_id")
        metric = context["metrics"].get(metric_id, {})
        if value is None:
            report["skipped_counts"]["document_candidate_non_numeric"] += 1
            continue
        if not row.get("entity_id") or not metric:
            report["skipped_counts"]["document_candidate_missing_identity"] += 1
            continue
        if row.get("financial_scope_type") != "consolidated_entity":
            report["skipped_counts"]["document_candidate_non_consolidated"] += 1
            continue
        source_id = str(row.get("source_id") or "")
        if source_id not in CN_DISCLOSURE_RECORD_TYPES:
            report["skipped_counts"]["document_candidate_unregistered_source"] += 1
            continue
        candidate_entity_id = str(row.get("entity_id") or "")
        source_code = candidate_entity_id.split("_", 1)[0]
        entity_id = _lookup_entity(
            context,
            source_id,
            source_code,
            candidate_entity_id,
        ) or (
            candidate_entity_id
            if candidate_entity_id in context.get("active_entity_ids", set())
            else None
        )
        if not entity_id:
            report["skipped_counts"]["document_candidate_missing_active_entity"] += 1
            continue
        period_end = _date_or_none(row.get("period_end"))
        period_start = _date_or_none(row.get("period_start"))
        if not period_end:
            report["skipped_counts"]["document_candidate_missing_period"] += 1
            continue
        period_type = metric.get("period_type")
        as_of_date = period_end if period_type == "point_in_time" else None
        notes = _compact_notes(
            {
                "candidate_id": row.get("candidate_id"),
                "candidate_evidence_sha256": row.get("evidence_sha256"),
                "candidate_cross_check_status": row.get("cross_check_status"),
                "parser_metadata": _json_value(row.get("extraction_metadata")),
                "entity_scope_id": entity_id,
                "candidate_entity_id": candidate_entity_id,
                "financial_scope_type": row.get("financial_scope_type"),
                "accounting_standard": "PRC_ASBE",
            }
        )
        fact = _fact(
            entity_id=entity_id,
            metric_id=metric_id,
            value=value,
            unit=row.get("unit"),
            currency=row.get("currency"),
            period_start=period_start,
            period_end=period_end,
            fiscal_year=_int_or_none(row.get("fiscal_year")),
            fiscal_quarter=row.get("fiscal_quarter"),
            as_of_date=as_of_date,
            report_date=_date_or_none(row.get("source_publish_date")),
            source_id=source_id,
            raw_object_id=row.get("raw_object_id"),
            source_field_name=row.get("source_field_name"),
            source_page_or_table=(
                f"page={row.get('page_number')};table={row.get('table_id')};"
                f"row={row.get('row_index')};column={row.get('column_index')}"
            ),
            extraction_method="pdf_financial_statement_table",
            confidence_score=row.get("confidence_score"),
            verification_status="single_source",
            tolerance=0.000001,
            notes=notes,
            stable_parts=[
                source_id,
                entity_id,
                metric_id,
                row.get("raw_object_id"),
                row.get("source_field_name"),
                row.get("page_number"),
                row.get("row_index"),
                row.get("column_index"),
                period_start,
                period_end,
                value,
                row.get("unit"),
                row.get("evidence_sha256"),
            ],
        )
        fact["_candidate_id"] = row.get("candidate_id")
        _count_fact(report, fact)
        yield fact


def _extract_sec_companyfacts(
    record: dict[str, Any], context: dict[str, Any], report: dict[str, Any]
) -> Iterable[dict[str, Any]]:
    payload = _json_value(record.get("record_json"))
    if not isinstance(payload, dict):
        report["skipped_counts"]["sec_invalid_json"] += 1
        return
    cik = _cik10(payload.get("cik") or record.get("record_key"))
    entity_id = _lookup_entity(
        context, "sec_companyfacts", cik, record.get("entity_hint")
    )
    if not entity_id:
        report["skipped_counts"]["sec_missing_entity"] += 1
        return
    facts = payload.get("facts", {})
    if not isinstance(facts, dict):
        report["skipped_counts"]["sec_missing_facts"] += 1
        return
    metric_map = context["metric_aliases"].get("sec_companyfacts", {})
    candidates: list[dict[str, Any]] = []
    for namespace, namespace_facts in facts.items():
        if not isinstance(namespace_facts, dict):
            continue
        for concept, concept_payload in namespace_facts.items():
            full_concept = f"{namespace}:{concept}"
            mapped = metric_map.get(full_concept)
            if not mapped:
                continue
            metric_id, confidence = mapped
            metric = context["metrics"].get(metric_id, {})
            units = (
                concept_payload.get("units", {})
                if isinstance(concept_payload, dict)
                else {}
            )
            label = (
                concept_payload.get("label")
                if isinstance(concept_payload, dict)
                else concept
            )
            if not isinstance(units, dict):
                continue
            for unit_name, items in units.items():
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    value = _decimal_or_none(item.get("val"))
                    if value is None:
                        report["skipped_counts"]["sec_non_numeric_value"] += 1
                        continue
                    period_start = _date_or_none(item.get("start"))
                    period_end = _date_or_none(item.get("end"))
                    fiscal_quarter, period_role = _sec_period_label(
                        metric, item, period_start, period_end
                    )
                    selection_key = _sec_selection_key(
                        entity_id,
                        metric_id,
                        unit_name,
                        item,
                        metric,
                        period_start,
                        period_end,
                        fiscal_quarter,
                        period_role,
                    )
                    fact = _fact(
                        entity_id=entity_id,
                        metric_id=metric_id,
                        value=value,
                        unit=unit_name,
                        currency=_currency_from_unit(unit_name),
                        period_start=period_start,
                        period_end=period_end,
                        fiscal_year=_int_or_none(item.get("fy")),
                        fiscal_quarter=fiscal_quarter,
                        as_of_date=_date_or_none(item.get("filed")),
                        report_date=period_end,
                        source_id="sec_companyfacts",
                        raw_object_id=record.get("raw_object_id"),
                        source_field_name=full_concept,
                        source_page_or_table=None,
                        extraction_method="xbrl",
                        confidence_score=confidence,
                        verification_status="single_source",
                        tolerance=None,
                        notes=_compact_notes(
                            {
                                "label": label,
                                "form": item.get("form"),
                                "accn": item.get("accn"),
                                "frame": item.get("frame"),
                                "period_role": period_role,
                            }
                        ),
                        stable_parts=[
                            "sec_companyfacts",
                            entity_id,
                            metric_id,
                            item.get("accn"),
                            full_concept,
                            unit_name,
                            item.get("fy"),
                            fiscal_quarter,
                            period_start,
                            period_end,
                            item.get("val"),
                            item.get("frame"),
                            item.get("form"),
                            item.get("filed"),
                        ],
                    )
                    candidates.append(
                        {
                            "fact": fact,
                            "item": item,
                            "metric": metric,
                            "selection_key": selection_key,
                            "period_role": period_role,
                        }
                    )

    for candidate in _select_sec_companyfacts(candidates, report):
        fact = candidate["fact"]
        _count_fact(report, fact)
        yield fact


def _select_sec_companyfacts(
    candidates: list[dict[str, Any]], report: dict[str, Any]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate["selection_key"]].append(candidate)
    selected = []
    for group in grouped.values():
        group.sort(key=_sec_candidate_score, reverse=True)
        winner = group[0]
        if len(group) > 1:
            report["skipped_counts"]["sec_duplicate_candidates_suppressed"] += (
                len(group) - 1
            )
            _annotate_sec_selection(winner, len(group))
        if _is_amended_form(winner["item"].get("form")):
            _annotate_sec_selection(winner, len(group), amended=True)
        selected.append(winner)
    return selected


def _annotate_sec_selection(
    candidate: dict[str, Any], candidate_count: int, amended: bool = False
) -> None:
    fact = candidate["fact"]
    current = _json_value(fact.get("notes"))
    notes = current if isinstance(current, dict) else {}
    notes.update(
        {
            "sec_selection": "canonical_companyfacts_candidate",
            "candidate_count": candidate_count,
            "selection_score": list(_sec_candidate_score(candidate)),
        }
    )
    if amended:
        notes["amended_or_restated_source"] = True
    fact["notes"] = _compact_notes(notes)


def _sec_selection_key(
    entity_id: str,
    metric_id: str,
    unit_name: str,
    item: dict[str, Any],
    metric: dict[str, Any],
    period_start: str | None,
    period_end: str | None,
    fiscal_quarter: str | None,
    period_role: str,
) -> tuple[Any, ...]:
    period_type = metric.get("period_type")
    if period_type == "point_in_time":
        return (
            "sec_instant",
            entity_id,
            metric_id,
            unit_name,
            period_end,
            item.get("fy"),
            fiscal_quarter,
        )
    return (
        "sec_duration",
        entity_id,
        metric_id,
        unit_name,
        period_start,
        period_end,
        item.get("fy"),
        fiscal_quarter,
        period_role,
    )


def _sec_period_label(
    metric: dict[str, Any],
    item: dict[str, Any],
    period_start: str | None,
    period_end: str | None,
) -> tuple[str | None, str]:
    fp = item.get("fp")
    fp_text = str(fp) if fp is not None else None
    period_type = metric.get("period_type")
    duration = _days_between(period_start, period_end)
    if period_type == "point_in_time":
        return fp_text, "instant"
    if fp_text == "FY":
        return "FY", "annual_flow"
    if fp_text in {"Q1", "Q2", "Q3", "Q4"}:
        if duration is None:
            return f"{fp_text}_UNKNOWN_DURATION", "quarter_or_ytd_unknown"
        if duration <= 120:
            return fp_text, "quarter_flow"
        return f"{fp_text}_YTD", "ytd_flow"
    return fp_text, "duration_flow"


def _sec_candidate_score(
    candidate: dict[str, Any],
) -> tuple[int, int, int, int, str, str]:
    item = candidate["item"]
    period_role = candidate.get("period_role")
    form = str(item.get("form") or "")
    return (
        _sec_form_score(form, period_role),
        -30 if _is_amended_form(form) else 0,
        _sec_frame_score(
            item.get("frame"), item.get("fy"), item.get("fp"), period_role
        ),
        _sec_duration_score(candidate["metric"], item, period_role),
        str(item.get("filed") or ""),
        str(item.get("accn") or ""),
    )


def _sec_form_score(form: str, period_role: str | None) -> int:
    form = form.upper()
    if period_role in {"annual_flow", "instant"}:
        scores = {
            "10-K": 100,
            "20-F": 95,
            "40-F": 95,
            "10-K/A": 75,
            "20-F/A": 70,
            "40-F/A": 70,
            "10-Q": 40,
            "10-Q/A": 30,
        }
    elif period_role == "quarter_flow":
        scores = {"10-Q": 100, "10-Q/A": 75, "10-K": 20, "10-K/A": 15}
    else:
        scores = {
            "10-Q": 70,
            "10-Q/A": 55,
            "10-K": 50,
            "10-K/A": 40,
            "20-F": 45,
            "40-F": 45,
        }
    return scores.get(form, 10)


def _sec_frame_score(frame: Any, fy: Any, fp: Any, period_role: str | None) -> int:
    text = str(frame or "").upper()
    if not text:
        return 5
    year = str(fy or "")
    if period_role == "annual_flow" and year and text == f"CY{year}":
        return 25
    if period_role == "quarter_flow" and year and fp and text == f"CY{year}{fp}":
        return 25
    if year and f"CY{year}" in text:
        return 15
    return 0


def _sec_duration_score(
    metric: dict[str, Any], item: dict[str, Any], period_role: str | None
) -> int:
    if metric.get("period_type") == "point_in_time":
        return 20
    duration = _days_between(
        _date_or_none(item.get("start")), _date_or_none(item.get("end"))
    )
    if duration is None:
        return 0
    if period_role == "annual_flow" and 330 <= duration <= 380:
        return 25
    if period_role == "quarter_flow" and 70 <= duration <= 110:
        return 25
    if period_role == "ytd_flow":
        return 5
    return 0


def _is_amended_form(form: Any) -> bool:
    return str(form or "").upper().endswith("/A")


def _days_between(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    except ValueError:
        return None


def _extract_fred_observation(
    record: dict[str, Any], context: dict[str, Any], report: dict[str, Any]
) -> dict[str, Any] | None:
    series_id = record.get("metric_hint") or record.get("entity_hint")
    mapped = context["metric_aliases"].get("fred_observations", {}).get(series_id)
    if not mapped:
        report["skipped_counts"]["fred_missing_metric"] += 1
        return None
    metric_id, confidence = mapped
    payload = _json_value(record.get("record_json"))
    if not isinstance(payload, dict):
        report["skipped_counts"]["fred_invalid_json"] += 1
        return None
    value = _decimal_or_none(payload.get("value"))
    if value is None:
        report["skipped_counts"]["fred_missing_value"] += 1
        return None
    series_map = (
        context.get("series_entity_map", {})
        .get("fred_observations", {})
        .get(str(series_id), {})
    )
    entity_id = (
        series_map.get("instrument_entity_id")
        or series_map.get("applies_to_entity_id")
        or FX_ENTITY_BY_FRED_SERIES.get(series_id)
        or "USA_COUNTRY"
    )
    metric = context["metrics"].get(metric_id, {})
    series_metadata = (
        context.get("source_metadata", {})
        .get("fred_observations", {})
        .get(series_id, {})
    )
    source_unit = (
        series_metadata.get("units") if isinstance(series_metadata, dict) else None
    )
    obs_date = _date_or_none(payload.get("date") or record.get("period_hint"))
    fact = _fact(
        entity_id=entity_id,
        metric_id=metric_id,
        value=value,
        unit=source_unit or metric.get("default_unit"),
        currency=_currency_from_fred_metadata(series_metadata)
        or metric.get("default_currency"),
        period_start=obs_date,
        period_end=obs_date,
        fiscal_year=_int_or_none(obs_date) if obs_date else None,
        fiscal_quarter=None,
        as_of_date=_date_or_none(payload.get("realtime_end")),
        report_date=obs_date,
        source_id="fred_observations",
        raw_object_id=record.get("raw_object_id"),
        source_field_name=series_id,
        source_page_or_table=None,
        extraction_method="api",
        confidence_score=confidence,
        verification_status="single_source",
        tolerance=None,
        notes=_compact_notes(
            {
                "realtime_start": payload.get("realtime_start"),
                "realtime_end": payload.get("realtime_end"),
                "frequency": series_metadata.get("frequency")
                if isinstance(series_metadata, dict)
                else None,
                "units_short": series_metadata.get("units_short")
                if isinstance(series_metadata, dict)
                else None,
                "series_entity_id": series_map.get("series_entity_id"),
                "applies_to_entity_id": series_map.get("applies_to_entity_id"),
                "instrument_entity_id": series_map.get("instrument_entity_id"),
            }
        ),
        stable_parts=[
            "fred_observations",
            series_id,
            entity_id,
            metric_id,
            payload.get("date"),
            payload.get("realtime_start"),
            payload.get("realtime_end"),
            payload.get("value"),
        ],
    )
    _count_fact(report, fact)
    return fact


def _extract_worldbank_observation(
    record: dict[str, Any], context: dict[str, Any], report: dict[str, Any]
) -> dict[str, Any] | None:
    country = record.get("entity_hint")
    indicator = record.get("metric_hint")
    mapped = context["metric_aliases"].get("worldbank_indicators", {}).get(indicator)
    if not mapped:
        report["skipped_counts"]["wb_missing_metric"] += 1
        return None
    metric_id, confidence = mapped
    entity_id = _lookup_entity(context, "worldbank_indicators", country, None)
    if not entity_id:
        report["skipped_counts"]["wb_missing_entity"] += 1
        return None
    payload = _json_value(record.get("record_json"))
    if not isinstance(payload, dict):
        report["skipped_counts"]["wb_invalid_json"] += 1
        return None
    value = _decimal_or_none(payload.get("value"))
    if value is None:
        report["skipped_counts"]["wb_missing_value"] += 1
        return None
    year = _int_or_none(payload.get("date") or record.get("period_hint"))
    period_start = f"{year:04d}-01-01" if year else None
    period_end = f"{year:04d}-12-31" if year else None
    metric = context["metrics"].get(metric_id, {})
    fact = _fact(
        entity_id=entity_id,
        metric_id=metric_id,
        value=value,
        unit=metric.get("default_unit"),
        currency=metric.get("default_currency"),
        period_start=period_start,
        period_end=period_end,
        fiscal_year=year,
        fiscal_quarter=None,
        as_of_date=None,
        report_date=period_end,
        source_id="worldbank_indicators",
        raw_object_id=record.get("raw_object_id"),
        source_field_name=indicator,
        source_page_or_table=None,
        extraction_method="api",
        confidence_score=confidence,
        verification_status="single_source",
        tolerance=None,
        notes=_compact_notes({"country": country, "indicator": indicator}),
        stable_parts=[
            "worldbank_indicators",
            country,
            indicator,
            entity_id,
            metric_id,
            year,
            payload.get("value"),
        ],
    )
    _count_fact(report, fact)
    return fact


IMF_UNIT_BY_CONCEPT = {
    "weo_ngdpd_current_usd_gdp": ("billion USD", "USD"),
    "weo_current_account_balance_usd": ("billion USD", "USD"),
    "weo_gdp_per_capita_current_usd": ("USD_per_person", "USD"),
    "weo_real_gdp_growth": ("percent", None),
    "weo_inflation_average_consumer_prices": ("percent", None),
    "weo_unemployment_rate": ("percent", None),
    "weo_current_account_balance_pct_gdp": ("percent", None),
    "weo_general_government_gross_debt_pct_gdp": ("percent", None),
    "weo_general_government_net_lending_pct_gdp": ("percent", None),
    "weo_share_of_world_gdp_ppp": ("percent", None),
}

SEC_DOCUMENT_METRIC_BY_FORM = {
    "10-K": "sec_filing_10k",
    "10-Q": "sec_filing_10q",
    "8-K": "sec_filing_8k",
}

CNINFO_DOCUMENT_METRIC_BY_REPORT_TYPE = {
    "annual": "cninfo_annual_report",
    "semiannual": "cninfo_semiannual_report",
    "q1": "cninfo_q1_report",
    "q3": "cninfo_q3_report",
}


def _extract_imf_datamapper(
    record: dict[str, Any], context: dict[str, Any], report: dict[str, Any]
) -> Iterable[dict[str, Any]]:
    concept = record.get("metric_hint") or record.get("record_key")
    mapped = context["metric_aliases"].get("imf_sdmx", {}).get(concept)
    if not mapped:
        report["skipped_counts"]["imf_missing_metric"] += 1
        return
    metric_id, confidence = mapped
    metadata = _json_value(record.get("record_json"))
    if not isinstance(metadata, dict):
        report["skipped_counts"]["imf_invalid_record_json"] += 1
        return
    storage_uri = metadata.get("storage_uri")
    if not storage_uri:
        report["skipped_counts"]["imf_missing_storage_uri"] += 1
        return
    try:
        payload = json.loads(Path(storage_uri).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        report["skipped_counts"]["imf_unreadable_json"] += 1
        return
    values = payload.get("values") if isinstance(payload, dict) else None
    if not isinstance(values, dict):
        report["skipped_counts"]["imf_missing_values"] += 1
        return
    indicator_values = next(
        (item for item in values.values() if isinstance(item, dict)), None
    )
    if not isinstance(indicator_values, dict):
        report["skipped_counts"]["imf_missing_indicator_values"] += 1
        return
    unit, currency = IMF_UNIT_BY_CONCEPT.get(
        concept,
        (
            context["metrics"].get(metric_id, {}).get("default_unit"),
            context["metrics"].get(metric_id, {}).get("default_currency"),
        ),
    )
    retrieval_year = _year_from_timestamp(record.get("retrieval_time"))
    for country_code, observations in indicator_values.items():
        entity_id = _lookup_entity(context, "imf_sdmx", country_code, country_code)
        if not entity_id:
            report["skipped_counts"]["imf_missing_entity"] += 1
            continue
        if not isinstance(observations, dict):
            continue
        for year_text, raw_value in observations.items():
            value = _decimal_or_none(raw_value)
            year = _int_or_none(year_text)
            if value is None or year is None:
                report["skipped_counts"]["imf_missing_value"] += 1
                continue
            period_start = f"{year:04d}-01-01"
            period_end = f"{year:04d}-12-31"
            fact = _fact(
                entity_id=entity_id,
                metric_id=metric_id,
                value=value,
                unit=unit,
                currency=currency,
                period_start=period_start,
                period_end=period_end,
                fiscal_year=year,
                fiscal_quarter=None,
                as_of_date=None,
                report_date=period_end,
                source_id="imf_sdmx",
                raw_object_id=record.get("raw_object_id"),
                source_field_name=concept,
                source_page_or_table=None,
                extraction_method="api_datamapper",
                confidence_score=confidence,
                verification_status="single_source",
                tolerance=None,
                notes=_compact_notes(
                    {
                        "country": country_code,
                        "concept": concept,
                        "dataset": metadata.get("dataset"),
                        "is_forecast": (
                            year >= retrieval_year
                            if retrieval_year is not None
                            else None
                        ),
                        "forecast_policy": "period_year_gte_retrieval_year",
                        "retrieval_year": retrieval_year,
                    }
                ),
                stable_parts=[
                    "imf_sdmx",
                    country_code,
                    concept,
                    entity_id,
                    metric_id,
                    year,
                    raw_value,
                ],
            )
            _count_fact(report, fact)
            yield fact


def _refresh_source_documents(
    db: DBProtocol, context: dict[str, Any], build_id: str, report: dict[str, Any]
) -> int:
    document_record_types = (
        "sec_filing_document",
        *CN_DISCLOSURE_RECORD_TYPES.values(),
    )
    placeholders = ",".join("?" for _ in document_record_types)
    rows = db.fetchall(
        f"""
        SELECT rr.raw_record_id, rr.raw_object_id, rr.source_id, rr.record_type, rr.record_key,
               rr.record_json, rr.entity_hint, rr.metric_hint, rr.period_hint,
               ro.storage_uri, ro.original_url, ro.validation_status
        FROM raw_records rr
        LEFT JOIN raw_objects ro ON ro.raw_object_id = rr.raw_object_id
        WHERE rr.record_type IN ({placeholders})
        """,
        document_record_types,
    )
    count = 0
    for row in rows:
        record = dict(row)
        if record.get("record_type") == "sec_filing_document":
            document = _source_document_for_sec_filing(
                record, context, build_id, report
            )
        else:
            document = _source_document_for_cn_disclosure(
                record, context, build_id, report
            )
        if not document:
            continue
        _insert_source_document(db, document)
        count += 1
    return count


def _source_document_for_sec_filing(
    record: dict[str, Any],
    context: dict[str, Any],
    build_id: str,
    report: dict[str, Any],
) -> dict[str, Any] | None:
    payload = _json_value(record.get("record_json"))
    if not isinstance(payload, dict):
        report["skipped_counts"]["sec_filing_invalid_json"] += 1
        return None
    form = payload.get("form") or record.get("metric_hint")
    if not form:
        report["skipped_counts"]["sec_filing_unmapped_form"] += 1
        return None
    cik = _cik10(payload.get("cik"))
    entity_id = _lookup_entity(context, "sec_filings", cik, payload.get("ticker"))
    if not entity_id:
        report["skipped_counts"]["sec_filing_missing_entity"] += 1
        return None
    period_end = _date_or_none(
        payload.get("reportDate")
        or payload.get("filingDate")
        or record.get("period_hint")
    )
    filing_date = _date_or_none(payload.get("filingDate"))
    stable_document_id = _stable_document_id(
        "sec_filings",
        entity_id,
        form,
        payload.get("accessionNumber"),
        payload.get("primaryDocument"),
        record.get("raw_object_id"),
    )
    return {
        "document_id": versioned_id(stable_document_id, build_id),
        "stable_document_id": stable_document_id,
        "build_id": build_id,
        "is_active": 1,
        "superseded_by": None,
        "entity_id": entity_id,
        "source_id": "sec_filings",
        "form_type": str(form),
        "report_type": None,
        "period_end": period_end,
        "filing_date": filing_date,
        "storage_uri": record.get("storage_uri"),
        "original_url": payload.get("document_url") or record.get("original_url"),
        "raw_object_id": record.get("raw_object_id"),
        "document_status": record.get("validation_status") or "indexed",
        "notes": _compact_notes(
            {
                "accessionNumber": payload.get("accessionNumber"),
                "primaryDocument": payload.get("primaryDocument"),
                "ticker": payload.get("ticker"),
            }
        ),
    }


def _source_document_for_cn_disclosure(
    record: dict[str, Any],
    context: dict[str, Any],
    build_id: str,
    report: dict[str, Any],
) -> dict[str, Any] | None:
    source_id = str(record.get("source_id") or "")
    if source_id not in CN_DISCLOSURE_RECORD_TYPES:
        report["skipped_counts"]["cn_disclosure_unregistered_source"] += 1
        return None
    skip_prefix = {
        "bse_disclosures": "bse",
        "hkex_disclosures": "hkex",
    }.get(source_id, "cninfo")
    payload = _json_value(record.get("record_json"))
    if not isinstance(payload, dict):
        report["skipped_counts"][f"{skip_prefix}_invalid_json"] += 1
        return None
    report_type = payload.get("report_type") or record.get("metric_hint")
    if not report_type:
        report["skipped_counts"][f"{skip_prefix}_unmapped_report_type"] += 1
        return None
    stock_code = payload.get("stock_code") or record.get("entity_hint")
    entity_id = _lookup_entity(
        context, source_id, stock_code, payload.get("company_name")
    )
    if not entity_id:
        report["skipped_counts"][f"{skip_prefix}_missing_entity"] += 1
        return None
    year = _int_or_none(payload.get("year") or record.get("period_hint"))
    period_end, _ = (
        (None, None)
        if source_id == "hkex_disclosures"
        else _cninfo_period(year, str(report_type))
    )
    filing_date = _date_or_none(payload.get("publish_date"))
    stable_document_id = _stable_document_id(
        source_id,
        entity_id,
        report_type,
        payload.get("announcement_id"),
        payload.get("filename"),
        record.get("raw_object_id"),
    )
    return {
        "document_id": versioned_id(stable_document_id, build_id),
        "stable_document_id": stable_document_id,
        "build_id": build_id,
        "is_active": 1,
        "superseded_by": None,
        "entity_id": entity_id,
        "source_id": source_id,
        "form_type": None,
        "report_type": str(report_type),
        "period_end": period_end,
        "filing_date": filing_date,
        "storage_uri": record.get("storage_uri") or payload.get("storage_uri"),
        "original_url": record.get("original_url") or payload.get("url"),
        "raw_object_id": record.get("raw_object_id"),
        "document_status": record.get("validation_status") or "indexed",
        "notes": _compact_notes(
            {
                "announcement_id": payload.get("announcement_id"),
                "title": payload.get("title"),
                "company_name": payload.get("company_name"),
            }
        ),
    }


def _insert_source_document(db: DBProtocol, document: dict[str, Any]) -> None:
    columns = [
        "document_id",
        "stable_document_id",
        "build_id",
        "is_active",
        "superseded_by",
        "entity_id",
        "source_id",
        "form_type",
        "report_type",
        "period_end",
        "filing_date",
        "storage_uri",
        "original_url",
        "raw_object_id",
        "document_status",
        "notes",
    ]
    db.execute(
        f"""
        INSERT INTO source_documents ({",".join(columns)})
        VALUES ({",".join(["?"] * len(columns))})
        ON CONFLICT (document_id) DO UPDATE SET
            stable_document_id=excluded.stable_document_id,
            build_id=excluded.build_id,
            is_active=excluded.is_active,
            superseded_by=excluded.superseded_by,
            entity_id=excluded.entity_id,
            source_id=excluded.source_id,
            form_type=excluded.form_type,
            report_type=excluded.report_type,
            period_end=excluded.period_end,
            filing_date=excluded.filing_date,
            storage_uri=excluded.storage_uri,
            original_url=excluded.original_url,
            raw_object_id=excluded.raw_object_id,
            document_status=excluded.document_status,
            notes=excluded.notes
        """,
        [document.get(column) for column in columns],
    )


def _stable_document_id(*parts: Any) -> str:
    digest = hashlib.sha1(
        "|".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()[:24]
    return f"srcdoc_{digest}"


def _year_from_timestamp(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.year
    text = str(value).strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _cninfo_period(year: int | None, report_type: str) -> tuple[str | None, str | None]:
    if not year:
        return None, None
    if report_type == "annual":
        return f"{year:04d}-12-31", "FY"
    if report_type == "semiannual":
        return f"{year:04d}-06-30", "Q2"
    if report_type == "q1":
        return f"{year:04d}-03-31", "Q1"
    if report_type == "q3":
        return f"{year:04d}-09-30", "Q3"
    return f"{year:04d}-12-31", None


def _lookup_entity(
    context: dict[str, Any], source_id: str, source_code: Any, alias: Any
) -> str | None:
    fallback_sources = {
        "sec_filings": ["sec_filings", "sec_submissions", "sec_companyfacts"],
        "imf_sdmx": ["imf_sdmx", "worldbank_indicators"],
    }.get(source_id, [source_id])
    for candidate_source in fallback_sources:
        source_map = context["entity_aliases"].get(candidate_source, {})
        for key in [source_code, alias]:
            if key is None:
                continue
            value = source_map.get(str(key))
            if value:
                return value
    return None


def _fact(**kwargs: Any) -> dict[str, Any]:
    stable_parts = kwargs.pop("stable_parts")
    fact_id = (
        "fact_"
        + hashlib.sha1(
            "|".join(str(part) for part in stable_parts).encode("utf-8")
        ).hexdigest()[:24]
    )
    value = kwargs.get("value")
    return {
        "fact_id": fact_id,
        "value_type": "numeric" if value is not None else None,
        **kwargs,
    }


def _count_fact(report: dict[str, Any], fact: dict[str, Any]) -> None:
    report["source_counts"][fact["source_id"]] += 1
    report["metric_counts"][fact["metric_id"]] += 1


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == ".":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _date_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    if len(text) == 4 and text.isdigit():
        return f"{text}-01-01"
    return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    if text.isdigit():
        return int(text)
    return None


def _cik10(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.upper().startswith("CIK"):
        text = text[3:]
    if not text.isdigit():
        return None
    return text.zfill(10)


def _currency_from_fred_metadata(metadata: Any) -> str | None:
    if not isinstance(metadata, dict):
        return None
    text = json.dumps(
        {"units": metadata.get("units"), "units_short": metadata.get("units_short")},
        default=str,
    ).lower()
    if "u.s. dollar" in text or "dollars" in text or "u.s. $" in text:
        return "USD"
    if "euro" in text:
        return "EUR"
    if "yen" in text:
        return "JPY"
    if "yuan" in text or "renminbi" in text:
        return "CNY"
    return None


def _currency_from_unit(unit: Any) -> str | None:
    text = str(unit or "")
    if text in {"USD", "EUR", "JPY", "CNY", "GBP", "CAD", "AUD"}:
        return text
    if "/" in text:
        head = text.split("/", 1)[0]
        if head in {"USD", "EUR", "JPY", "CNY", "GBP", "CAD", "AUD"}:
            return head
    return None


def _compact_notes(values: dict[str, Any]) -> str | None:
    clean = {}
    for key, value in values.items():
        if value is None or value == "":
            continue
        clean[key] = value
    return (
        json.dumps(clean, ensure_ascii=False, sort_keys=True, default=str)
        if clean
        else None
    )


def _markdown_report(report: dict[str, Any]) -> str:
    lines = ["# Atomic Facts Report", ""]
    lines.append(f"Inserted facts: {report['inserted_count']}")
    lines.append("")
    lines.append("## Source Counts")
    lines.append("")
    for source_id, count in report.get("source_counts", {}).items():
        lines.append(f"- {source_id}: {count}")
    lines.append("")
    lines.append("## Top Metrics")
    lines.append("")
    for metric_id, count in list(report.get("top_metric_counts", {}).items())[:20]:
        lines.append(f"- {metric_id}: {count}")
    lines.append("")
    lines.append("## Skipped")
    lines.append("")
    for reason, count in report.get("skipped_counts", {}).items():
        lines.append(f"- {reason}: {count}")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for note in report.get("notes", []):
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)
