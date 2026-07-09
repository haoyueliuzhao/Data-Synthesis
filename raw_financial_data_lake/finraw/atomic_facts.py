from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from finraw.db.client import DBProtocol

FACT_COLUMNS = [
    "fact_id", "entity_id", "metric_id", "value", "value_type", "unit", "currency",
    "period_start", "period_end", "fiscal_year", "fiscal_quarter", "as_of_date", "report_date",
    "source_id", "raw_object_id", "source_field_name", "source_page_or_table",
    "extraction_method", "confidence_score", "verification_status", "tolerance", "notes",
]

FX_ENTITY_BY_FRED_SERIES = {
    "DEXUSEU": "EUR_USD",
    "DEXJPUS": "USD_JPY",
    "DEXCHUS": "USD_CNY",
    "DTWEXBGS": "USD_BROAD_INDEX",
}


def refresh_atomic_facts(db: DBProtocol, config: dict[str, Any], output_dir: str | None = None, batch_size: int = 5000) -> dict[str, Any]:
    context = _load_context(db)
    report = {
        "inserted_count": 0,
        "source_counts": Counter(),
        "metric_counts": Counter(),
        "skipped_counts": Counter(),
        "notes": [
            "Atomic facts are extracted only from structured raw records: SEC companyfacts XBRL JSON, FRED observations, and World Bank observations.",
            "PDF/HTML filing facts are intentionally excluded until a parse-and-verify layer exists.",
        ],
    }
    db.execute("DELETE FROM atomic_facts")
    batch: list[dict[str, Any]] = []
    for fact in _iter_atomic_facts(db, context, report):
        batch.append(fact)
        if len(batch) >= batch_size:
            db.insert_atomic_facts(batch)
            report["inserted_count"] += len(batch)
            batch.clear()
    if batch:
        db.insert_atomic_facts(batch)
        report["inserted_count"] += len(batch)

    final_report = {
        "inserted_count": report["inserted_count"],
        "source_counts": dict(sorted(report["source_counts"].items())),
        "top_metric_counts": dict(report["metric_counts"].most_common(30)),
        "skipped_counts": dict(sorted(report["skipped_counts"].items())),
        "notes": report["notes"],
    }
    if output_dir:
        paths = write_atomic_facts_report(final_report, output_dir)
        final_report["written_files"] = [str(path) for path in paths]
    return final_report


def write_atomic_facts_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "atomic_facts_report.json"
    md_path = out / "atomic_facts_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path.write_text(_markdown_report(report), encoding="utf-8")
    return [json_path, md_path]


def _load_context(db: DBProtocol) -> dict[str, Any]:
    metric_rows = [dict(row) for row in db.fetchall("SELECT * FROM metrics")]
    metric_alias_rows = [dict(row) for row in db.fetchall("SELECT * FROM metric_alias_map")]
    entity_alias_rows = [dict(row) for row in db.fetchall("SELECT * FROM entity_alias_map")]
    source_entity_rows = [dict(row) for row in db.fetchall("SELECT source_id, source_code, raw_metadata FROM source_entities")]
    metrics = {row["metric_id"]: row for row in metric_rows}
    metric_aliases = _metric_alias_context(metric_alias_rows)
    entity_aliases = _entity_alias_context(entity_alias_rows)
    return {"metrics": metrics, "metric_aliases": metric_aliases, "entity_aliases": entity_aliases, "source_metadata": _source_metadata_context(source_entity_rows)}



def _source_metadata_context(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = defaultdict(dict)
    for row in rows:
        source_id = row.get("source_id")
        source_code = row.get("source_code")
        if not source_id or not source_code:
            continue
        metadata[source_id][source_code] = _json_value(row.get("raw_metadata"))
    return metadata

def _metric_alias_context(rows: list[dict[str, Any]]) -> dict[str, dict[str, tuple[str, float]]]:
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


def _iter_atomic_facts(db: DBProtocol, context: dict[str, Any], report: dict[str, Any]) -> Iterable[dict[str, Any]]:
    rows = db.fetchall(
        """
        SELECT raw_record_id, raw_object_id, source_id, record_type, record_key,
               record_json, entity_hint, metric_hint, period_hint
        FROM raw_records
        WHERE record_type IN (?, ?, ?)
        """,
        ("sec_companyfacts_json", "fred_observation", "wb_observation"),
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


def _extract_sec_companyfacts(record: dict[str, Any], context: dict[str, Any], report: dict[str, Any]) -> Iterable[dict[str, Any]]:
    payload = _json_value(record.get("record_json"))
    if not isinstance(payload, dict):
        report["skipped_counts"]["sec_invalid_json"] += 1
        return
    cik = _cik10(payload.get("cik") or record.get("record_key"))
    entity_id = _lookup_entity(context, "sec_companyfacts", cik, record.get("entity_hint"))
    if not entity_id:
        report["skipped_counts"]["sec_missing_entity"] += 1
        return
    facts = payload.get("facts", {})
    if not isinstance(facts, dict):
        report["skipped_counts"]["sec_missing_facts"] += 1
        return
    metric_map = context["metric_aliases"].get("sec_companyfacts", {})
    for namespace, namespace_facts in facts.items():
        if not isinstance(namespace_facts, dict):
            continue
        for concept, concept_payload in namespace_facts.items():
            full_concept = f"{namespace}:{concept}"
            mapped = metric_map.get(full_concept)
            if not mapped:
                continue
            metric_id, confidence = mapped
            units = concept_payload.get("units", {}) if isinstance(concept_payload, dict) else {}
            label = concept_payload.get("label") if isinstance(concept_payload, dict) else concept
            if not isinstance(units, dict):
                continue
            for unit_name, items in units.items():
                if not isinstance(items, list):
                    continue
                for idx, item in enumerate(items):
                    if not isinstance(item, dict):
                        continue
                    value = _decimal_or_none(item.get("val"))
                    if value is None:
                        report["skipped_counts"]["sec_non_numeric_value"] += 1
                        continue
                    fact = _fact(
                        entity_id=entity_id,
                        metric_id=metric_id,
                        value=value,
                        unit=unit_name,
                        currency=_currency_from_unit(unit_name),
                        period_start=_date_or_none(item.get("start")),
                        period_end=_date_or_none(item.get("end")),
                        fiscal_year=_int_or_none(item.get("fy")),
                        fiscal_quarter=item.get("fp"),
                        as_of_date=_date_or_none(item.get("filed")),
                        report_date=_date_or_none(item.get("end")),
                        source_id="sec_companyfacts",
                        raw_object_id=record.get("raw_object_id"),
                        source_field_name=full_concept,
                        source_page_or_table=None,
                        extraction_method="xbrl",
                        confidence_score=confidence,
                        verification_status="single_source",
                        tolerance=None,
                        notes=_compact_notes({"label": label, "form": item.get("form"), "accn": item.get("accn"), "frame": item.get("frame")}),
                        stable_parts=[record.get("raw_record_id"), full_concept, unit_name, idx, item.get("accn"), item.get("fy"), item.get("fp"), item.get("end"), item.get("val")],
                    )
                    _count_fact(report, fact)
                    yield fact


def _extract_fred_observation(record: dict[str, Any], context: dict[str, Any], report: dict[str, Any]) -> dict[str, Any] | None:
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
    entity_id = FX_ENTITY_BY_FRED_SERIES.get(series_id) or "USA_COUNTRY"
    metric = context["metrics"].get(metric_id, {})
    series_metadata = context.get("source_metadata", {}).get("fred_observations", {}).get(series_id, {})
    source_unit = series_metadata.get("units") if isinstance(series_metadata, dict) else None
    obs_date = _date_or_none(payload.get("date") or record.get("period_hint"))
    fact = _fact(
        entity_id=entity_id,
        metric_id=metric_id,
        value=value,
        unit=source_unit or metric.get("default_unit"),
        currency=_currency_from_fred_metadata(series_metadata) or metric.get("default_currency"),
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
        notes=_compact_notes({"realtime_start": payload.get("realtime_start"), "realtime_end": payload.get("realtime_end"), "frequency": series_metadata.get("frequency") if isinstance(series_metadata, dict) else None, "units_short": series_metadata.get("units_short") if isinstance(series_metadata, dict) else None}),
        stable_parts=[record.get("raw_record_id"), series_id, payload.get("date"), payload.get("value"), payload.get("realtime_start"), payload.get("realtime_end")],
    )
    _count_fact(report, fact)
    return fact


def _extract_worldbank_observation(record: dict[str, Any], context: dict[str, Any], report: dict[str, Any]) -> dict[str, Any] | None:
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
        stable_parts=[record.get("raw_record_id"), country, indicator, year, payload.get("value")],
    )
    _count_fact(report, fact)
    return fact


def _lookup_entity(context: dict[str, Any], source_id: str, source_code: Any, alias: Any) -> str | None:
    source_map = context["entity_aliases"].get(source_id, {})
    for key in [source_code, alias]:
        if key is None:
            continue
        value = source_map.get(str(key))
        if value:
            return value
    return None


def _fact(**kwargs: Any) -> dict[str, Any]:
    stable_parts = kwargs.pop("stable_parts")
    fact_id = "fact_" + hashlib.sha1("|".join(str(part) for part in stable_parts).encode("utf-8")).hexdigest()[:24]
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
    text = json.dumps({"units": metadata.get("units"), "units_short": metadata.get("units_short")}, default=str).lower()
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
    clean = {key: value for key, value in values.items() if value not in {None, ""}}
    return json.dumps(clean, ensure_ascii=False, sort_keys=True) if clean else None


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

