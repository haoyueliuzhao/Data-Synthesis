from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

from finraw.db.client import DBProtocol

VALID_INPUT_STATUSES = {"single_source", "cross_verified"}
FINANCIAL_RATIOS = [
    ("gross_margin", "gross_profit", "revenue", "percent"),
    ("operating_margin", "operating_income", "revenue", "percent"),
    ("net_margin", "net_income", "revenue", "percent"),
    ("liabilities_to_assets", "total_liabilities", "total_assets", "percent"),
    ("cash_to_assets", "cash_and_cash_equivalents", "total_assets", "percent"),
    ("rd_to_revenue", "research_and_development_expense", "revenue", "percent"),
]
RANKING_METRICS = {
    "revenue", "net_income", "operating_income", "gross_profit", "total_assets", "total_liabilities",
    "cash_and_cash_equivalents", "gdp_current_usd", "population_total", "real_gdp_growth_pct",
}
SHARE_METRICS = {"revenue", "total_assets", "gdp_current_usd", "population_total"}


def refresh_derived_facts(db: DBProtocol, config: dict[str, Any], output_dir: str | None = None, batch_size: int = 5000) -> dict[str, Any]:
    db.execute("DELETE FROM derived_facts")
    rows = _load_standardized_rows(db)
    report = {
        "input_fact_count": len(rows),
        "derived_count": 0,
        "derived_type_counts": Counter(),
        "status_counts": Counter(),
        "skipped_counts": Counter(),
        "notes": [
            "Derived facts are generated only from standardized_facts with non-conflict, non-rejected inputs.",
            "YoY/difference use annual SEC FY facts and World Bank calendar-year facts; high-frequency FRED daily/monthly series are intentionally excluded for now.",
            "QoQ uses SEC quarterly facts only; macro quarterly/daily derivations need a frequency-aware calendar layer.",
            "Ranking and share facts are scoped by source, metric, year, unit, and currency to avoid mixing incomparable data.",
            "long_window_return is not generated yet because no standardized market price return facts are available in the current raw lake.",
        ],
    }
    batch: list[dict[str, Any]] = []

    def emit(fact: dict[str, Any]) -> None:
        batch.append(fact)
        report["derived_count"] += 1
        report["derived_type_counts"][fact["derived_type"]] += 1
        report["status_counts"][fact["verification_status"]] += 1
        if len(batch) >= batch_size:
            db.insert_derived_facts(batch)
            batch.clear()

    annual_rows = _annual_rows(rows, report)
    quarterly_rows = _quarterly_rows(rows, report)

    for fact in _iter_yoy_and_difference(annual_rows, report):
        emit(fact)
    for fact in _iter_qoq_growth(quarterly_rows, report):
        emit(fact)
    for fact in _iter_ratios(annual_rows, report):
        emit(fact)
    for fact in _iter_rankings_and_extrema(annual_rows, report):
        emit(fact)
    for fact in _iter_shares(annual_rows, report):
        emit(fact)

    if batch:
        db.insert_derived_facts(batch)

    final_report = {
        "input_fact_count": report["input_fact_count"],
        "derived_count": report["derived_count"],
        "derived_type_counts": dict(sorted(report["derived_type_counts"].items())),
        "status_counts": dict(sorted(report["status_counts"].items())),
        "skipped_counts": dict(sorted(report["skipped_counts"].items())),
        "notes": report["notes"],
    }
    if output_dir:
        paths = write_derived_facts_report(final_report, output_dir)
        final_report["written_files"] = [str(path) for path in paths]
    return final_report


def write_derived_facts_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "derived_facts_report.json"
    md_path = out / "derived_facts_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path.write_text(_markdown_report(report), encoding="utf-8")
    return [json_path, md_path]


def _load_standardized_rows(db: DBProtocol) -> list[dict[str, Any]]:
    rows = [dict(row) for row in db.fetchall(
        """
        SELECT sf.fact_id, sf.entity_id, sf.metric_id, sf.normalized_value, sf.normalized_unit,
               sf.normalized_currency, sf.period_start, sf.period_end, sf.calendar_year,
               sf.fiscal_year, sf.fiscal_quarter, sf.time_basis, sf.metric_period_type,
               sf.source_id, sf.raw_object_id, sf.verification_status, sf.confidence_score,
               m.metric_category, m.statement_type
        FROM standardized_facts sf
        LEFT JOIN metrics m ON m.metric_id = sf.metric_id
        WHERE sf.normalized_value IS NOT NULL
          AND sf.verification_status IN ('single_source', 'cross_verified')
        """
    )]
    normalized = []
    for row in rows:
        value = _decimal_or_none(row.get("normalized_value"))
        if value is None:
            continue
        row["value_decimal"] = value
        normalized.append(row)
    return _dedupe_rows(normalized)


def _dedupe_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = (
            row.get("entity_id"), row.get("metric_id"), row.get("source_id"), row.get("period_start"),
            row.get("period_end"), row.get("calendar_year"), row.get("fiscal_year"), row.get("fiscal_quarter"),
            row.get("normalized_unit"), row.get("normalized_currency"), row.get("value_decimal"),
        )
        current = best.get(key)
        if current is None or _row_score(row) > _row_score(current):
            best[key] = row
    return list(best.values())


def _row_score(row: dict[str, Any]) -> tuple[int, float, str]:
    status_score = 2 if row.get("verification_status") == "cross_verified" else 1
    confidence = float(row.get("confidence_score") or 0)
    return status_score, confidence, str(row.get("fact_id") or "")


def _annual_rows(rows: list[dict[str, Any]], report: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        year = None
        time_basis = None
        if row.get("source_id") == "sec_companyfacts" and row.get("fiscal_year") and row.get("fiscal_quarter") == "FY":
            year = int(row["fiscal_year"])
            time_basis = "fiscal_year"
        elif row.get("source_id") == "worldbank_indicators" and row.get("calendar_year"):
            year = int(row["calendar_year"])
            time_basis = "calendar_year"
        elif row.get("time_basis") == "calendar_year" and row.get("calendar_year"):
            year = int(row["calendar_year"])
            time_basis = "calendar_year"
        else:
            report["skipped_counts"]["non_annual_input"] += 1
            continue
        row = dict(row)
        row["derived_year"] = year
        row["derived_time_basis"] = time_basis
        out.append(row)
    return out


def _quarterly_rows(rows: list[dict[str, Any]], report: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    valid_quarters = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
    for row in rows:
        quarter = row.get("fiscal_quarter")
        if row.get("source_id") == "sec_companyfacts" and quarter in valid_quarters and row.get("fiscal_year"):
            row = dict(row)
            row["derived_quarter_index"] = int(row["fiscal_year"]) * 4 + valid_quarters[quarter]
            row["derived_quarter"] = quarter
            out.append(row)
        else:
            report["skipped_counts"]["non_quarterly_input"] += 1
    return out


def _iter_yoy_and_difference(rows: list[dict[str, Any]], report: dict[str, Any]) -> Iterable[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("normalized_unit") in {None, "document"}:
            continue
        key = (row.get("entity_id"), row.get("metric_id"), row.get("source_id"), row.get("normalized_unit"), row.get("normalized_currency"), row.get("derived_time_basis"))
        grouped[key].append(row)
    for key, group_rows in grouped.items():
        group_rows.sort(key=lambda r: (r["derived_year"], str(r.get("period_end") or "")))
        by_year: dict[int, dict[str, Any]] = {}
        for row in group_rows:
            by_year[row["derived_year"]] = row
        for year in sorted(by_year):
            prev = by_year.get(year - 1)
            curr = by_year[year]
            if not prev:
                continue
            diff = curr["value_decimal"] - prev["value_decimal"]
            yield _derived_scalar(
                "difference", [prev, curr], {"entity_id": curr["entity_id"]}, {"metric_id": curr["metric_id"]},
                {"year": year, "basis": curr["derived_time_basis"], "previous_year": year - 1},
                "current_value - prior_year_value", diff, curr.get("normalized_unit"), _status_from_inputs([prev, curr]),
            )
            if prev["value_decimal"] == 0:
                report["skipped_counts"]["yoy_zero_prior_value"] += 1
                continue
            yoy = diff / abs(prev["value_decimal"]) * Decimal("100")
            yield _derived_scalar(
                "yoy_growth", [prev, curr], {"entity_id": curr["entity_id"]}, {"metric_id": curr["metric_id"]},
                {"year": year, "basis": curr["derived_time_basis"], "previous_year": year - 1},
                "(current_value - prior_year_value) / abs(prior_year_value) * 100", yoy, "percent", _status_from_inputs([prev, curr]),
            )


def _iter_qoq_growth(rows: list[dict[str, Any]], report: dict[str, Any]) -> Iterable[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (row.get("entity_id"), row.get("metric_id"), row.get("source_id"), row.get("normalized_unit"), row.get("normalized_currency"))
        grouped[key].append(row)
    for group_rows in grouped.values():
        group_rows.sort(key=lambda r: r["derived_quarter_index"])
        prev = None
        for curr in group_rows:
            if prev and curr["derived_quarter_index"] == prev["derived_quarter_index"] + 1:
                if prev["value_decimal"] == 0:
                    report["skipped_counts"]["qoq_zero_prior_value"] += 1
                else:
                    qoq = (curr["value_decimal"] - prev["value_decimal"]) / abs(prev["value_decimal"]) * Decimal("100")
                    yield _derived_scalar(
                        "qoq_growth", [prev, curr], {"entity_id": curr["entity_id"]}, {"metric_id": curr["metric_id"]},
                        {"fiscal_year": curr.get("fiscal_year"), "fiscal_quarter": curr.get("fiscal_quarter"), "previous_quarter": prev.get("fiscal_quarter")},
                        "(current_quarter_value - prior_quarter_value) / abs(prior_quarter_value) * 100", qoq, "percent", _status_from_inputs([prev, curr]),
                    )
            prev = curr


def _iter_ratios(rows: list[dict[str, Any]], report: dict[str, Any]) -> Iterable[dict[str, Any]]:
    by_period: dict[tuple[Any, ...], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        key = (row.get("entity_id"), row.get("source_id"), row.get("derived_year"), row.get("derived_time_basis"), row.get("normalized_currency"))
        by_period[key][row.get("metric_id")] = row
    for (entity_id, source_id, year, basis, currency), metrics in by_period.items():
        for ratio_name, numerator_metric, denominator_metric, unit in FINANCIAL_RATIOS:
            numerator = metrics.get(numerator_metric)
            denominator = metrics.get(denominator_metric)
            if not numerator or not denominator:
                continue
            if denominator["value_decimal"] == 0:
                report["skipped_counts"][f"{ratio_name}_zero_denominator"] += 1
                continue
            value = numerator["value_decimal"] / denominator["value_decimal"] * Decimal("100")
            yield _derived_scalar(
                "ratio", [numerator, denominator], {"entity_id": entity_id}, {"ratio_id": ratio_name, "numerator": numerator_metric, "denominator": denominator_metric},
                {"year": year, "basis": basis}, "numerator_value / denominator_value * 100", value, unit,
                _status_from_inputs([numerator, denominator]),
            )


def _iter_rankings_and_extrema(rows: list[dict[str, Any]], report: dict[str, Any]) -> Iterable[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("metric_id") not in RANKING_METRICS:
            continue
        key = (row.get("source_id"), row.get("metric_id"), row.get("derived_year"), row.get("derived_time_basis"), row.get("normalized_unit"), row.get("normalized_currency"))
        grouped[key].append(row)
    for (source_id, metric_id, year, basis, unit, currency), group_rows in grouped.items():
        by_entity: dict[str, dict[str, Any]] = {}
        for row in group_rows:
            entity_id = row.get("entity_id")
            if entity_id and (entity_id not in by_entity or row["value_decimal"] > by_entity[entity_id]["value_decimal"]):
                by_entity[entity_id] = row
        comparable = list(by_entity.values())
        if len(comparable) < 2:
            report["skipped_counts"]["ranking_less_than_two_entities"] += 1
            continue
        comparable.sort(key=lambda r: r["value_decimal"], reverse=True)
        top = comparable[:10]
        bottom = list(reversed(comparable[-10:]))
        scope = {"source_id": source_id, "entity_count": len(comparable)}
        metric_scope = {"metric_id": metric_id}
        time_scope = {"year": year, "basis": basis}
        yield _derived_table("ranking", top, scope, metric_scope, time_scope, "rank entities by normalized_value desc", _ranking_table(top), unit, _status_from_inputs(top))
        yield _derived_scalar("argmax", [top[0]], {**scope, "entity_id": top[0].get("entity_id")}, metric_scope, time_scope, "max(normalized_value) over entity scope", top[0]["value_decimal"], unit, _status_from_inputs([top[0]]))
        yield _derived_scalar("argmin", [bottom[0]], {**scope, "entity_id": bottom[0].get("entity_id")}, metric_scope, time_scope, "min(normalized_value) over entity scope", bottom[0]["value_decimal"], unit, _status_from_inputs([bottom[0]]))


def _iter_shares(rows: list[dict[str, Any]], report: dict[str, Any]) -> Iterable[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("metric_id") not in SHARE_METRICS:
            continue
        key = (row.get("source_id"), row.get("metric_id"), row.get("derived_year"), row.get("derived_time_basis"), row.get("normalized_unit"), row.get("normalized_currency"))
        grouped[key].append(row)
    for (source_id, metric_id, year, basis, unit, currency), group_rows in grouped.items():
        by_entity: dict[str, dict[str, Any]] = {}
        for row in group_rows:
            entity_id = row.get("entity_id")
            if entity_id and (entity_id not in by_entity or row["value_decimal"] > by_entity[entity_id]["value_decimal"]):
                by_entity[entity_id] = row
        comparable = [row for row in by_entity.values() if row["value_decimal"] > 0]
        if len(comparable) < 2:
            report["skipped_counts"]["share_less_than_two_positive_entities"] += 1
            continue
        total = sum(row["value_decimal"] for row in comparable)
        if total == 0:
            report["skipped_counts"]["share_zero_total"] += 1
            continue
        for row in comparable:
            value = row["value_decimal"] / total * Decimal("100")
            yield _derived_scalar(
                "share", [row], {"source_id": source_id, "entity_id": row.get("entity_id"), "entity_count": len(comparable)},
                {"metric_id": metric_id}, {"year": year, "basis": basis},
                "entity_value / scope_total_value * 100", value, "percent", _status_from_inputs([row]),
            )


def _derived_scalar(derived_type: str, inputs: list[dict[str, Any]], entity_scope: dict[str, Any], metric_scope: dict[str, Any], time_scope: dict[str, Any], calculation_code: str, value: Decimal, unit: str | None, status: str) -> dict[str, Any]:
    input_ids = [row["fact_id"] for row in inputs if row.get("fact_id")]
    payload = {"type": derived_type, "inputs": input_ids, "entity_scope": entity_scope, "metric_scope": metric_scope, "time_scope": time_scope, "calculation_code": calculation_code}
    return {
        "derived_id": _derived_id(payload),
        "derived_type": derived_type,
        "input_fact_ids": input_ids,
        "entity_scope": entity_scope,
        "metric_scope": metric_scope,
        "time_scope": time_scope,
        "calculation_code": calculation_code,
        "output_value": _to_float(value),
        "output_table": None,
        "unit": unit,
        "tolerance": _tolerance(value),
        "verification_status": status,
    }


def _derived_table(derived_type: str, inputs: list[dict[str, Any]], entity_scope: dict[str, Any], metric_scope: dict[str, Any], time_scope: dict[str, Any], calculation_code: str, output_table: list[dict[str, Any]], unit: str | None, status: str) -> dict[str, Any]:
    input_ids = [row["fact_id"] for row in inputs if row.get("fact_id")]
    payload = {"type": derived_type, "inputs": input_ids, "entity_scope": entity_scope, "metric_scope": metric_scope, "time_scope": time_scope, "calculation_code": calculation_code}
    return {
        "derived_id": _derived_id(payload),
        "derived_type": derived_type,
        "input_fact_ids": input_ids,
        "entity_scope": entity_scope,
        "metric_scope": metric_scope,
        "time_scope": time_scope,
        "calculation_code": calculation_code,
        "output_value": None,
        "output_table": output_table,
        "unit": unit,
        "tolerance": None,
        "verification_status": status,
    }


def _ranking_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"rank": idx + 1, "entity_id": row.get("entity_id"), "fact_id": row.get("fact_id"), "value": _to_float(row["value_decimal"])}
        for idx, row in enumerate(rows)
    ]


def _status_from_inputs(rows: list[dict[str, Any]]) -> str:
    statuses = {row.get("verification_status") for row in rows}
    if statuses == {"cross_verified"}:
        return "cross_verified"
    if statuses <= VALID_INPUT_STATUSES:
        return "single_source"
    return "pending"


def _derived_id(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return "derived_" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:24]


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _to_float(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _tolerance(value: Decimal) -> float:
    return float(max(Decimal("0.000001"), abs(value) * Decimal("0.000001")))


def _markdown_report(report: dict[str, Any]) -> str:
    lines = ["# Derived Facts Report", ""]
    lines.append(f"Input standardized facts: {report['input_fact_count']}")
    lines.append(f"Derived facts: {report['derived_count']}")
    lines.append("")
    lines.append("## Derived Types")
    lines.append("")
    for key, count in sorted(report.get("derived_type_counts", {}).items()):
        lines.append(f"- {key}: {count}")
    lines.append("")
    lines.append("## Verification Status")
    lines.append("")
    for key, count in sorted(report.get("status_counts", {}).items()):
        lines.append(f"- {key}: {count}")
    lines.append("")
    lines.append("## Skipped")
    lines.append("")
    for key, count in sorted(report.get("skipped_counts", {}).items()):
        lines.append(f"- {key}: {count}")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for note in report.get("notes", []):
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)
