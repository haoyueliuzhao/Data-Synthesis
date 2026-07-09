from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from finraw.db.client import DBProtocol

NON_NEGATIVE_STRICT = {"total_assets", "total_liabilities"}
NON_NEGATIVE_USUALLY = {
    "revenue", "gross_profit", "cost_of_revenue", "cash_and_cash_equivalents", "inventory",
    "accounts_receivable_net", "shareholders_equity", "population_total", "money_supply_m2",
}
PERCENT_REASONABLE = {
    "unemployment_rate": (-10, 100),
    "labor_force_participation_rate": (0, 100),
    "employment_population_ratio": (0, 100),
    "inflation_rate_cpi": (-100, 1000),
    "real_gdp_growth_pct": (-100, 1000),
    "current_account_balance_pct_gdp": (-300, 300),
    "government_expense_pct_gdp": (0, 300),
    "tax_revenue_pct_gdp": (0, 200),
    "government_consumption_pct_gdp": (0, 200),
    "gross_capital_formation_pct_gdp": (-100, 300),
    "government_gross_debt_pct_gdp": (0, 1000),
    "government_net_lending_pct_gdp": (-300, 300),
    "share_of_world_gdp_ppp": (0, 100),
    "broad_money_pct_gdp": (0, 1000),
    "domestic_credit_private_sector_pct_gdp": (0, 1000),
}


@dataclass
class StandardizedRow:
    row: dict[str, Any]
    checks: list[dict[str, Any]]


def refresh_fact_standardization(db: DBProtocol, config: dict[str, Any], output_dir: str | None = None, batch_size: int = 10000) -> dict[str, Any]:
    db.execute("DELETE FROM fact_quality_checks")
    db.execute("DELETE FROM standardized_facts")
    metrics = {row["metric_id"]: dict(row) for row in db.fetchall("SELECT * FROM metrics")}
    rows = [dict(row) for row in db.fetchall("SELECT * FROM atomic_facts")]

    standardized = []
    checks = []
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    report = {
        "standardized_count": 0,
        "verification_counts": Counter(),
        "check_counts": Counter(),
        "unit_counts": Counter(),
        "notes": [
            "Monetary facts are normalized to million currency units where possible; original atomic_facts remain unchanged.",
            "Time basis is inferred from metric period_type and source; document facts are preserved as document_presence facts, not numeric financial extractions.",
            "cross_verified requires matching normalized values from more than one source; macro source differences beyond tolerance are marked source_definition_mismatch when source definitions likely differ.",
        ],
    }

    for fact in rows:
        result = _standardize_one(fact, metrics.get(fact.get("metric_id"), {}))
        grouped[_conflict_key(result.row)].append(result.row)
        standardized.append(result.row)
        checks.extend(result.checks)
        if len(standardized) >= batch_size:
            db.insert_standardized_facts(standardized)
            report["standardized_count"] += len(standardized)
            for row in standardized:
                report["verification_counts"][row["verification_status"]] += 1
                report["unit_counts"][row.get("normalized_unit") or "unknown"] += 1
            standardized.clear()
        if len(checks) >= batch_size:
            db.insert_fact_quality_checks(checks)
            for check in checks:
                report["check_counts"][f"{check['check_type']}:{check['status']}"] += 1
            checks.clear()

    if standardized:
        db.insert_standardized_facts(standardized)
        report["standardized_count"] += len(standardized)
        for row in standardized:
            report["verification_counts"][row["verification_status"]] += 1
            report["unit_counts"][row.get("normalized_unit") or "unknown"] += 1
    if checks:
        db.insert_fact_quality_checks(checks)
        for check in checks:
            report["check_counts"][f"{check['check_type']}:{check['status']}"] += 1

    conflict_updates, conflict_checks = _detect_conflicts_and_cross_verification(grouped)
    _apply_status_updates(db, conflict_updates, batch_size)
    if conflict_checks:
        db.insert_fact_quality_checks(conflict_checks)
        for check in conflict_checks:
            report["check_counts"][f"{check['check_type']}:{check['status']}"] += 1

    yoy_updates, yoy_checks = _detect_large_yoy_changes(db)
    _apply_status_updates(db, yoy_updates, batch_size, only_flags=True)
    if yoy_checks:
        db.insert_fact_quality_checks(yoy_checks)
        for check in yoy_checks:
            report["check_counts"][f"{check['check_type']}:{check['status']}"] += 1

    db.sync_atomic_fact_verification_status()
    final_counts = db.fetchall("SELECT verification_status, COUNT(*) AS count FROM standardized_facts GROUP BY verification_status")
    report["verification_counts"] = {row["verification_status"]: row["count"] for row in final_counts}
    report["check_counts"] = dict(sorted(report["check_counts"].items()))
    report["unit_counts"] = dict(report["unit_counts"].most_common(30))
    if output_dir:
        paths = write_fact_standardization_report(report, output_dir)
        report["written_files"] = [str(path) for path in paths]
    return report


def write_fact_standardization_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "fact_standardization_report.json"
    md_path = out / "fact_standardization_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path.write_text(_markdown_report(report), encoding="utf-8")
    return [json_path, md_path]


def _standardize_one(fact: dict[str, Any], metric: dict[str, Any]) -> StandardizedRow:
    flags = []
    checks = []
    value = _decimal_or_none(fact.get("value"))
    normalized_value, normalized_unit, normalized_currency, value_scale = _normalize_unit(value, fact, metric)
    time_basis = _time_basis(fact, metric)
    calendar_year = _year_from_date(fact.get("period_end") or fact.get("report_date") or fact.get("as_of_date"))
    metric_period_type = metric.get("period_type") or _infer_period_type(fact)
    status = "single_source"

    for check in _basic_checks(fact, metric, normalized_value, normalized_unit):
        checks.append(check)
        if check["status"] != "passed":
            flags.append({"check_type": check["check_type"], "severity": check["severity"], "message": check["message"]})
            if check["severity"] == "error":
                status = "rejected"

    row = {
        "fact_id": fact.get("fact_id"),
        "entity_id": fact.get("entity_id"),
        "metric_id": fact.get("metric_id"),
        "normalized_value": normalized_value,
        "normalized_unit": normalized_unit,
        "normalized_currency": normalized_currency,
        "value_scale": value_scale,
        "period_start": fact.get("period_start"),
        "period_end": fact.get("period_end"),
        "calendar_year": calendar_year,
        "fiscal_year": fact.get("fiscal_year"),
        "fiscal_quarter": fact.get("fiscal_quarter"),
        "time_basis": time_basis,
        "metric_period_type": metric_period_type,
        "as_of_date": fact.get("as_of_date"),
        "report_date": fact.get("report_date"),
        "source_id": fact.get("source_id"),
        "raw_object_id": fact.get("raw_object_id"),
        "verification_status": status,
        "validation_flags": flags,
        "conflict_group_id": None,
        "confidence_score": fact.get("confidence_score"),
        "notes": _merge_notes(fact.get("notes"), {"raw_unit": fact.get("unit"), "raw_currency": fact.get("currency")}),
        "_source_field_name": fact.get("source_field_name"),
        "_metric_category": metric.get("metric_category"),
        "_extraction_method": fact.get("extraction_method"),
    }
    return StandardizedRow(row=row, checks=checks)


def _normalize_unit(value: Decimal | None, fact: dict[str, Any], metric: dict[str, Any]) -> tuple[Decimal | None, str | None, str | None, str | None]:
    unit = str(fact.get("unit") or metric.get("default_unit") or "").strip()
    currency = fact.get("currency") or metric.get("default_currency")
    unit_l = unit.lower()
    if value is None:
        return None, unit or None, currency, None

    if _is_percent_unit(unit, metric):
        if unit_l in {"ratio", "decimal"} or (abs(value) <= Decimal("1") and str(metric.get("default_unit") or "").lower() in {"percent", "%"}):
            return value * Decimal("100"), "percent", None, "ratio_to_percent"
        return value, "percent", None, "percent"

    if unit_l == "document":
        return value, "document", None, "document_presence"

    if _is_per_share_unit(unit, metric):
        return value, _per_share_unit(unit, currency), currency, "reported"

    if _is_per_person_unit(unit, metric):
        return value, _per_person_unit(unit, currency), currency, "reported"

    monetary_currency = _currency_from_unit(unit) or currency
    if monetary_currency:
        scale = _monetary_scale(unit)
        if scale:
            return value * scale, f"million {monetary_currency}", monetary_currency, "million"
        return value / Decimal("1000000"), f"million {monetary_currency}", monetary_currency, "million"

    if "billions of dollars" in unit_l:
        return value * Decimal("1000"), "million USD", "USD", "million"
    if "millions of dollars" in unit_l:
        return value, "million USD", "USD", "million"
    if "thousands of dollars" in unit_l:
        return value / Decimal("1000"), "million USD", "USD", "million"

    if "index" in unit_l:
        return value, unit, currency, "index_level"
    return value, unit or metric.get("default_unit"), currency, "reported"


def _basic_checks(fact: dict[str, Any], metric: dict[str, Any], value: Decimal | None, unit: str | None) -> list[dict[str, Any]]:
    checks = []
    metric_id = fact.get("metric_id")
    if value is None:
        checks.append(_check(fact, "numeric_value", "failed", "error", "normalized value is null"))
        return checks
    checks.append(_check(fact, "numeric_value", "passed", "info", "normalized value is numeric"))

    if metric_id in NON_NEGATIVE_STRICT:
        if value < 0:
            checks.append(_check(fact, "non_negative", "failed", "error", f"{metric_id} is negative"))
        else:
            checks.append(_check(fact, "non_negative", "passed", "info", f"{metric_id} is non-negative"))
    elif metric_id in NON_NEGATIVE_USUALLY and value < 0:
        checks.append(_check(fact, "usually_non_negative", "warning", "warning", f"{metric_id} is usually non-negative but value is negative"))

    if unit == "percent" or str(metric.get("default_unit") or "").lower() in {"percent", "%"}:
        lo, hi = PERCENT_REASONABLE.get(metric_id, (-1000, 1000))
        if value < Decimal(str(lo)) or value > Decimal(str(hi)):
            checks.append(_check(fact, "percentage_range", "warning", "warning", f"percent value {value} outside expected range [{lo}, {hi}]"))
        else:
            checks.append(_check(fact, "percentage_range", "passed", "info", "percent value in expected range"))

    if metric.get("period_type") == "point_in_time" and not fact.get("period_end"):
        checks.append(_check(fact, "time_completeness", "failed", "error", "point-in-time metric missing period_end"))
    elif metric.get("period_type") == "period_flow" and not fact.get("period_end"):
        checks.append(_check(fact, "time_completeness", "failed", "error", "period-flow metric missing period_end"))
    else:
        checks.append(_check(fact, "time_completeness", "passed", "info", "time fields present"))
    return checks


def _detect_conflicts_and_cross_verification(groups: dict[tuple[Any, ...], list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    updates = []
    checks = []
    for key, rows in groups.items():
        if len(rows) < 2:
            continue
        valid_rows = [row for row in rows if row["verification_status"] != "rejected" and row.get("normalized_value") is not None]
        if len(valid_rows) < 2:
            continue
        values = [Decimal(str(row["normalized_value"])) for row in valid_rows]
        sources = {row.get("source_id") for row in valid_rows}
        max_v, min_v = max(values), min(values)
        tolerance = _tolerance(values)
        conflict_group_id = "conflict_" + hashlib.sha1("|".join(str(part) for part in key).encode("utf-8")).hexdigest()[:16]
        if abs(max_v - min_v) > tolerance:
            status, check_type, severity = _difference_status(valid_rows, values)
            for row in valid_rows:
                flags = list(row.get("validation_flags") or [])
                message = f"{check_type} in group {conflict_group_id}: min={min_v}, max={max_v}"
                flags.append({"check_type": check_type, "severity": severity, "message": message})
                updates.append({"fact_id": row["fact_id"], "verification_status": status, "validation_flags": flags, "conflict_group_id": conflict_group_id})
                checks.append(_check(row, check_type, "warning" if severity == "warning" else "failed", severity, message))
        elif len(sources) > 1:
            for row in valid_rows:
                if row["verification_status"] == "single_source":
                    updates.append({"fact_id": row["fact_id"], "verification_status": "cross_verified", "validation_flags": row.get("validation_flags") or [], "conflict_group_id": None})
                    checks.append(_check(row, "cross_source_match", "passed", "info", "matching normalized value from multiple sources"))
    return updates, checks


def _detect_large_yoy_changes(db: DBProtocol) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = [dict(row) for row in db.fetchall(
        """
        SELECT fact_id, entity_id, metric_id, normalized_value, normalized_unit, period_end,
               source_id, validation_flags, verification_status
        FROM standardized_facts
        WHERE period_end IS NOT NULL AND normalized_value IS NOT NULL
          AND verification_status NOT IN ('rejected', 'conflict')
        """
    )]
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("metric_id") in {"federal_funds_rate", "treasury_yield_10y", "treasury_yield_2y", "fx_cny_per_usd", "fx_jpy_per_usd", "fx_usd_per_eur"}:
            continue
        grouped[(row.get("entity_id"), row.get("metric_id"), row.get("normalized_unit"), row.get("source_id"))].append(row)
    updates = []
    checks = []
    for group_rows in grouped.values():
        group_rows.sort(key=lambda row: row.get("period_end") or "")
        prev = None
        for row in group_rows:
            value = Decimal(str(row["normalized_value"]))
            if prev is not None:
                prev_value = Decimal(str(prev["normalized_value"]))
                if prev_value != 0:
                    ratio = abs((value - prev_value) / prev_value)
                    if ratio > Decimal("5"):
                        flags = _json_flags(row.get("validation_flags"))
                        message = f"large sequential change versus previous observation: {ratio:.2f}"
                        flags.append({"check_type": "large_change", "severity": "warning", "message": message})
                        updates.append({"fact_id": row["fact_id"], "verification_status": row.get("verification_status"), "validation_flags": flags, "conflict_group_id": None})
                        checks.append(_check(row, "large_change", "warning", "warning", message))
            prev = row
    return updates, checks


def _apply_status_updates(db: DBProtocol, updates: list[dict[str, Any]], batch_size: int, only_flags: bool = False) -> None:
    if not updates:
        return
    for start in range(0, len(updates), batch_size):
        db.update_standardized_fact_statuses(updates[start:start + batch_size], only_flags=only_flags)


def _conflict_key(row: dict[str, Any]) -> tuple[Any, ...]:
    source_concept_scope = None
    if row.get("source_id") == "sec_companyfacts" and row.get("_metric_category") == "financial_statement":
        source_concept_scope = row.get("_source_field_name")
    return (
        row.get("entity_id"), row.get("metric_id"), row.get("period_start"), row.get("period_end"),
        row.get("fiscal_year"), row.get("fiscal_quarter"), row.get("normalized_unit"), row.get("normalized_currency"),
        source_concept_scope,
    )


def _difference_status(rows: list[dict[str, Any]], values: list[Decimal]) -> tuple[str, str, str]:
    sources = {row.get("source_id") for row in rows}
    categories = {row.get("_metric_category") for row in rows}
    cross_macro_sources = len(sources) > 1 and sources & {"imf_sdmx", "worldbank_indicators", "fred_observations"} and categories <= {"macro", "market", None}
    if cross_macro_sources:
        return "source_definition_mismatch", "source_definition_mismatch", "warning"
    return "conflict", "conflict", "error"


def _check(fact: dict[str, Any], check_type: str, status: str, severity: str, message: str) -> dict[str, Any]:
    fact_id = fact.get("fact_id")
    digest = hashlib.sha1(f"{fact_id}|{check_type}|{status}|{message}".encode("utf-8")).hexdigest()[:16]
    return {"check_id": f"check_{digest}", "fact_id": fact_id, "check_type": check_type, "status": status, "severity": severity, "message": message}


def _is_percent_unit(unit: str, metric: dict[str, Any]) -> bool:
    text = f"{unit} {metric.get('default_unit') or ''}".lower()
    return text.strip() in {"percent", "%"} or "percent" in text or text.strip() in {"ratio", "decimal"}


def _is_per_share_unit(unit: str, metric: dict[str, Any]) -> bool:
    text = f"{unit} {metric.get('default_unit') or ''}".lower()
    return "share" in text or metric.get("default_unit") == "per_share"


def _is_per_person_unit(unit: str, metric: dict[str, Any]) -> bool:
    text = f"{unit} {metric.get('default_unit') or ''}".lower()
    return "per_person" in text or "per person" in text or "per capita" in text


def _per_share_unit(unit: str, currency: Any) -> str:
    cur = currency or _currency_from_unit(unit) or "currency"
    return f"{cur}_per_share"


def _per_person_unit(unit: str, currency: Any) -> str:
    cur = currency or _currency_from_unit(unit) or "currency"
    return f"{cur}_per_person"


def _currency_from_unit(unit: Any) -> str | None:
    text = str(unit or "").upper()
    for cur in ["USD", "CNY", "RMB", "EUR", "JPY", "GBP", "CAD", "AUD"]:
        if cur in text:
            return "CNY" if cur == "RMB" else cur
    return None


def _monetary_scale(unit: str) -> Decimal | None:
    text = unit.lower()
    if "thousand" in text:
        return Decimal("0.001")
    if "million" in text:
        return Decimal("1")
    if "billion" in text:
        return Decimal("1000")
    return None


def _time_basis(fact: dict[str, Any], metric: dict[str, Any]) -> str:
    source = fact.get("source_id")
    period_type = metric.get("period_type") or _infer_period_type(fact)
    if source == "sec_companyfacts":
        return "fiscal_period" if period_type == "period_flow" else "fiscal_point_in_time"
    if source == "fred_observations":
        return "observation_date"
    if source in {"worldbank_indicators", "imf_sdmx"}:
        return "calendar_year"
    if source in {"sec_filings", "cninfo_announcements"}:
        return "document_period"
    return "source_period"


def _infer_period_type(fact: dict[str, Any]) -> str | None:
    return "period_flow" if fact.get("period_start") else "point_in_time"


def _year_from_date(value: Any) -> int | None:
    if not value:
        return None
    text = str(value)
    return int(text[:4]) if len(text) >= 4 and text[:4].isdigit() else None


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _tolerance(values: list[Decimal]) -> Decimal:
    max_abs = max(abs(value) for value in values) if values else Decimal("0")
    return max(Decimal("0.000001"), max_abs * Decimal("0.000001"))


def _json_flags(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _merge_notes(existing: Any, extra: dict[str, Any]) -> str | None:
    payload = {}
    if existing:
        try:
            parsed = json.loads(existing) if isinstance(existing, str) else existing
            if isinstance(parsed, dict):
                payload.update(parsed)
        except json.JSONDecodeError:
            payload["source_notes"] = existing
    payload.update({key: value for key, value in extra.items() if value not in {None, ""}})
    return json.dumps(payload, ensure_ascii=False, sort_keys=True) if payload else None


def _markdown_report(report: dict[str, Any]) -> str:
    lines = ["# Fact Standardization Report", ""]
    lines.append(f"Standardized facts: {report['standardized_count']}")
    lines.append("")
    lines.append("## Verification Status")
    lines.append("")
    for status, count in sorted(report.get("verification_counts", {}).items()):
        lines.append(f"- {status}: {count}")
    lines.append("")
    lines.append("## Checks")
    lines.append("")
    for key, count in sorted(report.get("check_counts", {}).items()):
        lines.append(f"- {key}: {count}")
    lines.append("")
    lines.append("## Top Normalized Units")
    lines.append("")
    for unit, count in list(report.get("unit_counts", {}).items())[:20]:
        lines.append(f"- {unit}: {count}")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for note in report.get("notes", []):
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)

