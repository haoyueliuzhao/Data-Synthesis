from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from finraw.builds import deactivate_active_rows, finish_build, start_build
from finraw.db.client import DBProtocol

UNIT_NORMALIZATION_VERSION = "1.0.0"
TIME_NORMALIZATION_VERSION = "1.0.0"

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
    input_build_id = _active_build_id(db, "atomic_facts")
    build_id = start_build(db, layer="fact_build", command="standardize-facts", prefix="fact_standardization", input_build_id=input_build_id)
    for table in ["derived_facts", "fact_quality_checks", "standardized_facts"]:
        deactivate_active_rows(db, table, build_id)
    metrics = {row["metric_id"]: dict(row) for row in db.fetchall("SELECT * FROM metrics WHERE COALESCE(is_active, 1) = 1")}
    source_definitions = _load_source_definition_context(db)
    frequency_map = _load_frequency_context(db)
    rows = [dict(row) for row in db.fetchall("SELECT * FROM atomic_facts WHERE COALESCE(is_active, 1) = 1 AND COALESCE(unit, '') <> 'document'")]

    standardized = []
    checks = []
    raw_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    semantic_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    report = {
        "build_id": build_id,
        "input_build_id": input_build_id,
        "standardized_count": 0,
        "verification_counts": Counter(),
        "check_counts": Counter(),
        "unit_counts": Counter(),
        "notes": [
            "Monetary facts are normalized to million currency units where possible; original atomic_facts remain unchanged.",
            "Time basis is inferred from metric period_type and source; document availability is indexed in source_documents, not standardized_facts.",
            "Verification runs in two layers: raw equivalence groups catch same-source/concept duplicates; semantic equivalence groups catch cross-source entity/metric/period/unit matches.",
            "cross_verified requires matching normalized values from more than one source with compatible source definitions; macro source differences are marked source_definition_mismatch when definitions/frequency/vintage differ.",
        ],
    }

    for fact in rows:
        result = _standardize_one(fact, metrics.get(fact.get("metric_id"), {}), build_id, source_definitions, frequency_map)
        raw_groups[_raw_equivalence_key(result.row)].append(result.row)
        semantic_groups[_semantic_equivalence_key(result.row)].append(result.row)
        standardized.append(result.row)
        checks.extend(_with_check_build(result.checks, build_id))
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

    conflict_updates, conflict_checks = _detect_conflicts_and_cross_verification(raw_groups, semantic_groups)
    _apply_status_updates(db, conflict_updates, batch_size)
    if conflict_checks:
        db.insert_fact_quality_checks(_with_check_build(conflict_checks, build_id))
        for check in conflict_checks:
            report["check_counts"][f"{check['check_type']}:{check['status']}"] += 1

    yoy_updates, yoy_checks = _detect_large_yoy_changes(db)
    _apply_status_updates(db, yoy_updates, batch_size, only_flags=True)
    if yoy_checks:
        db.insert_fact_quality_checks(_with_check_build(yoy_checks, build_id))
        for check in yoy_checks:
            report["check_counts"][f"{check['check_type']}:{check['status']}"] += 1

    db.sync_atomic_fact_verification_status()
    final_counts = db.fetchall("SELECT verification_status, COUNT(*) AS count FROM standardized_facts WHERE COALESCE(is_active, 1) = 1 GROUP BY verification_status")
    report["verification_counts"] = {row["verification_status"]: row["count"] for row in final_counts}
    report["check_counts"] = dict(sorted(report["check_counts"].items()))
    report["unit_counts"] = dict(report["unit_counts"].most_common(30))
    if output_dir:
        paths = write_fact_standardization_report(report, output_dir)
        report["written_files"] = [str(path) for path in paths]
    finish_build(db, build_id, "success", f"standardized_count={report['standardized_count']}")
    return report



def _with_check_build(checks: list[dict[str, Any]], build_id: str) -> list[dict[str, Any]]:
    out = []
    for check in checks:
        row = dict(check)
        row["build_id"] = build_id
        row["is_active"] = 1
        row["superseded_by"] = None
        out.append(row)
    return out


def _load_source_definition_context(db: DBProtocol) -> dict[tuple[str, str, str], dict[str, Any]]:
    try:
        rows = db.fetchall("SELECT * FROM source_metric_definitions WHERE COALESCE(is_active, 1) = 1")
    except Exception:
        return {}
    context = {}
    for row in rows:
        item = dict(row)
        source_id = str(item.get("source_id") or "")
        metric_id = str(item.get("metric_id") or "")
        raw_concept = str(item.get("raw_concept_name") or "")
        key = (source_id, metric_id, raw_concept)
        if all(key):
            context[key] = item
            normalized_key = (
                source_id,
                metric_id,
                _normalized_source_concept(raw_concept),
            )
            context.setdefault(normalized_key, item)
    return context


def _load_frequency_context(db: DBProtocol) -> dict[tuple[str, str], dict[str, Any]]:
    try:
        rows = db.fetchall("SELECT * FROM time_series_frequency_map WHERE COALESCE(is_active, 1) = 1")
    except Exception:
        return {}
    context = {}
    for row in rows:
        item = dict(row)
        key = (str(item.get("source_id") or ""), str(item.get("series_id") or ""))
        if all(key):
            context[key] = item
    return context


def _active_build_id(db: DBProtocol, table: str) -> str | None:
    try:
        row = db.fetchone(
            f"SELECT build_id, COUNT(*) AS count FROM {table} WHERE COALESCE(is_active, 1) = 1 GROUP BY build_id ORDER BY count DESC LIMIT 1"
        )
    except Exception:
        return None
    return row["build_id"] if row and row["build_id"] else None

def write_fact_standardization_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "fact_standardization_report.json"
    md_path = out / "fact_standardization_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path.write_text(_markdown_report(report), encoding="utf-8")
    return [json_path, md_path]


def _standardize_one(fact: dict[str, Any], metric: dict[str, Any], build_id: str, source_definitions: dict[tuple[str, str, str], dict[str, Any]], frequency_map: dict[tuple[str, str], dict[str, Any]]) -> StandardizedRow:
    flags = []
    checks = []
    value = _decimal_or_none(fact.get("value"))
    normalized_value, normalized_unit, normalized_currency, value_scale = _normalize_unit(value, fact, metric)
    time_basis = _time_basis(fact, metric)
    calendar_year = _year_from_date(fact.get("period_end") or fact.get("report_date") or fact.get("as_of_date"))
    metric_period_type = metric.get("period_type") or _infer_period_type(fact)
    status = "single_source"
    source_definition = _source_definition_for_fact(fact, source_definitions)
    frequency_info = _frequency_for_fact(fact, frequency_map)
    frequency = frequency_info.get("frequency") or source_definition.get("frequency")
    seasonal_adjustment = frequency_info.get("seasonal_adjustment")
    source_units = frequency_info.get("source_units")
    entity_scope_id, financial_scope_type = _financial_scope(fact)

    for check in _basic_checks(fact, metric, normalized_value, normalized_unit):
        checks.append(check)
        if check["status"] != "passed":
            flags.append({"check_type": check["check_type"], "severity": check["severity"], "message": check["message"]})
            if check["severity"] == "error":
                status = "rejected"

    row = {
        "fact_id": fact.get("fact_id"),
        "stable_fact_id": fact.get("stable_fact_id") or fact.get("fact_id"),
        "build_id": build_id,
        "raw_snapshot_id": fact.get("raw_snapshot_id"),
        "is_active": 1,
        "superseded_by": None,
        "entity_id": fact.get("entity_id"),
        "entity_scope_id": entity_scope_id,
        "financial_scope_type": financial_scope_type,
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
        "source_definition_id": source_definition.get("definition_id"),
        "frequency": frequency,
        "seasonal_adjustment": seasonal_adjustment,
        "vintage_policy": source_definition.get("vintage_policy"),
        "is_forecast": _forecast_status(fact, source_definition),
        "comparability_level": source_definition.get("comparability_level"),
        "as_of_date": fact.get("as_of_date"),
        "report_date": fact.get("report_date"),
        "source_id": fact.get("source_id"),
        "raw_object_id": fact.get("raw_object_id"),
        "verification_status": status,
        "validation_flags": flags,
        "conflict_group_id": None,
        "raw_equivalence_group_id": None,
        "semantic_equivalence_group_id": None,
        "confidence_score": fact.get("confidence_score"),
        "notes": _merge_notes(fact.get("notes"), {"raw_unit": fact.get("unit"), "raw_currency": fact.get("currency"), "source_definition_id": source_definition.get("definition_id"), "frequency": frequency, "seasonal_adjustment": seasonal_adjustment, "source_units": source_units, "vintage_policy": source_definition.get("vintage_policy"), "comparability_level": source_definition.get("comparability_level")}),
        "_source_field_name": fact.get("source_field_name"),
        "_metric_category": metric.get("metric_category"),
        "_extraction_method": fact.get("extraction_method"),
    }
    row["raw_equivalence_group_id"] = _equivalence_group_id("raw_equiv", _raw_equivalence_key(row))
    row["semantic_equivalence_group_id"] = _equivalence_group_id("semantic_equiv", _semantic_equivalence_key(row))
    return StandardizedRow(row=row, checks=checks)



def _int_bool(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y"}:
        return 1
    if text in {"0", "false", "f", "no", "n"}:
        return 0
    return None


def _forecast_status(
    fact: dict[str, Any], source_definition: dict[str, Any]
) -> int | None:
    notes = fact.get("notes")
    if isinstance(notes, str):
        try:
            notes = json.loads(notes)
        except json.JSONDecodeError:
            notes = {}
    if isinstance(notes, dict) and "is_forecast" in notes:
        explicit = _int_bool(notes.get("is_forecast"))
        if explicit is not None:
            return explicit
    return _int_bool(source_definition.get("is_forecast"))


def _source_definition_for_fact(fact: dict[str, Any], source_definitions: dict[tuple[str, str, str], dict[str, Any]]) -> dict[str, Any]:
    source_id = str(fact.get("source_id") or "")
    metric_id = str(fact.get("metric_id") or "")
    concept = str(fact.get("source_field_name") or "")
    candidates = [concept]
    if ":" in concept:
        candidates.append(concept.split(":", 1)[-1])
    candidates.extend(
        [_normalized_source_concept(value) for value in tuple(candidates)]
    )
    for candidate in dict.fromkeys(candidates):
        row = source_definitions.get((source_id, metric_id, candidate))
        if row:
            return row
    return {}


def _normalized_source_concept(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).casefold()


def _frequency_for_fact(fact: dict[str, Any], frequency_map: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    source_id = str(fact.get("source_id") or "")
    series_id = str(fact.get("source_field_name") or "")
    mapped = frequency_map.get((source_id, series_id))
    if mapped:
        return mapped
    notes = fact.get("notes")
    if isinstance(notes, str):
        try:
            notes = json.loads(notes)
        except json.JSONDecodeError:
            notes = {}
    if isinstance(notes, dict):
        return {
            "frequency": notes.get("frequency"),
            "seasonal_adjustment": notes.get("seasonal_adjustment"),
            "source_units": notes.get("source_units") or fact.get("unit"),
        }
    return {}

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


def _detect_conflicts_and_cross_verification(
    raw_groups: dict[tuple[Any, ...], list[dict[str, Any]]],
    semantic_groups: dict[tuple[Any, ...], list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    updates: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    raw_updates, raw_checks = _detect_raw_equivalence_conflicts(raw_groups)
    updates.extend(raw_updates)
    checks.extend(raw_checks)
    semantic_updates, semantic_checks = _detect_semantic_equivalence_verification(semantic_groups)
    updates.extend(semantic_updates)
    checks.extend(semantic_checks)
    return updates, checks


def _detect_raw_equivalence_conflicts(groups: dict[tuple[Any, ...], list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    updates: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for key, rows in groups.items():
        valid_rows = _valid_equivalence_rows(rows)
        if len(valid_rows) < 2:
            continue
        values = [Decimal(str(row["normalized_value"])) for row in valid_rows]
        max_v, min_v = max(values), min(values)
        tolerance = _tolerance(values)
        group_id = _equivalence_group_id("raw_equiv", key)
        if abs(max_v - min_v) <= tolerance:
            continue
        for row in valid_rows:
            flags = list(row.get("validation_flags") or [])
            message = f"raw_equivalence_conflict in group {group_id}: min={min_v}, max={max_v}"
            flags.append({"check_type": "raw_equivalence_conflict", "severity": "error", "message": message})
            _append_status_update(updates, row, "conflict", flags, group_id)
            checks.append(_check(row, "raw_equivalence_conflict", "failed", "error", message))
    return updates, checks


def _detect_semantic_equivalence_verification(groups: dict[tuple[Any, ...], list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    updates: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for key, rows in groups.items():
        valid_rows = _valid_equivalence_rows(rows)
        if len(valid_rows) < 2:
            continue
        values = [Decimal(str(row["normalized_value"])) for row in valid_rows]
        sources = {row.get("source_id") for row in valid_rows}
        max_v, min_v = max(values), min(values)
        tolerance = _tolerance(values)
        group_id = _equivalence_group_id("semantic_equiv", key)
        if abs(max_v - min_v) > tolerance:
            status, check_type, severity = _difference_status(valid_rows, values)
            for row in valid_rows:
                flags = list(row.get("validation_flags") or [])
                message = f"{check_type} in semantic group {group_id}: min={min_v}, max={max_v}"
                flags.append({"check_type": check_type, "severity": severity, "message": message})
                _append_status_update(updates, row, status, flags, group_id)
                checks.append(_check(row, check_type, "warning" if severity == "warning" else "failed", severity, message))
        elif len(sources) > 1:
            if _definition_mismatch(valid_rows):
                for row in valid_rows:
                    flags = list(row.get("validation_flags") or [])
                    message = "matching value but source definitions/frequency/vintage are not equivalent enough for cross verification"
                    flags.append({"check_type": "source_definition_mismatch", "severity": "warning", "message": message})
                    _append_status_update(updates, row, "source_definition_mismatch", flags, group_id)
                    checks.append(_check(row, "source_definition_mismatch", "warning", "warning", message))
            else:
                for row in valid_rows:
                    if row["verification_status"] == "single_source":
                        _append_status_update(updates, row, "cross_verified", row.get("validation_flags") or [], None)
                        checks.append(_check(row, "cross_source_match", "passed", "info", "matching normalized value from multiple compatible source definitions"))
    return updates, checks


def _valid_equivalence_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if row.get("verification_status") not in {"rejected", "conflict"}
        and row.get("normalized_value") is not None
    ]


def _append_status_update(updates: list[dict[str, Any]], row: dict[str, Any], status: str, flags: list[dict[str, Any]], group_id: str | None) -> None:
    row["verification_status"] = status
    row["validation_flags"] = flags
    row["conflict_group_id"] = group_id
    updates.append({
        "fact_id": row["fact_id"],
        "verification_status": status,
        "validation_flags": flags,
        "conflict_group_id": group_id,
    })

def _detect_large_yoy_changes(db: DBProtocol) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = [dict(row) for row in db.fetchall(
        """
        SELECT fact_id, entity_id, metric_id, normalized_value, normalized_unit, period_end,
               source_id, validation_flags, verification_status
        FROM standardized_facts
        WHERE period_end IS NOT NULL AND normalized_value IS NOT NULL
          AND COALESCE(is_active, 1) = 1
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


def _raw_equivalence_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("entity_id"), row.get("metric_id"), row.get("period_start"), row.get("period_end"),
        row.get("fiscal_year"), row.get("fiscal_quarter"), row.get("normalized_unit"), row.get("normalized_currency"),
        row.get("source_id"), row.get("source_definition_id"), row.get("_source_field_name"),
    )


def _semantic_equivalence_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("entity_id"), row.get("metric_id"), row.get("period_start"), row.get("period_end"),
        row.get("fiscal_year"), row.get("fiscal_quarter"), row.get("normalized_unit"), row.get("normalized_currency"),
    )


def _equivalence_group_id(prefix: str, key: tuple[Any, ...]) -> str:
    digest = hashlib.sha1("|".join(str(part) for part in key).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"

def _definition_mismatch(rows: list[dict[str, Any]]) -> bool:
    sources = {row.get("source_id") for row in rows}
    if len(sources) <= 1:
        return False
    categories = {row.get("_metric_category") for row in rows}
    if not (sources & {"imf_sdmx", "worldbank_indicators", "fred_observations"} or categories <= {"macro", "market", None}):
        return False
    definition_ids = {row.get("source_definition_id") for row in rows if row.get("source_definition_id")}
    comparability = {row.get("comparability_level") for row in rows if row.get("comparability_level")}
    frequencies = {row.get("frequency") for row in rows if row.get("frequency")}
    return len(definition_ids) > 1 or len(comparability) > 1 or len(frequencies) > 1


def _difference_status(rows: list[dict[str, Any]], values: list[Decimal]) -> tuple[str, str, str]:
    sources = {row.get("source_id") for row in rows}
    categories = {row.get("_metric_category") for row in rows}
    cross_macro_sources = len(sources) > 1 and sources & {"imf_sdmx", "worldbank_indicators", "fred_observations"} and categories <= {"macro", "market", None}
    if cross_macro_sources or _definition_mismatch(rows):
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
    # Match compound Chinese scales before their generic suffixes.
    if "hundred_million" in text:
        return Decimal("100")
    if "ten_thousand" in text:
        return Decimal("0.01")
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
    if source in {
        "nbs_official_statistics",
        "pboc_official_statistics",
        "safe_official_statistics",
        "sse_market_statistics",
        "szse_market_statistics",
        "bse_market_statistics",
        "csi_index_publications",
    }:
        return (
            "calendar_point_in_time"
            if period_type == "point_in_time"
            else "calendar_period"
        )
    if source in {"cninfo_announcements", "bse_disclosures", "hkex_disclosures"} and fact.get(
        "extraction_method"
    ) == "pdf_financial_statement_table":
        return (
            "fiscal_period"
            if period_type == "period_flow"
            else "fiscal_point_in_time"
        )
    if source in {"sec_filings", "cninfo_announcements", "bse_disclosures", "hkex_disclosures"}:
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


def _financial_scope(fact: dict[str, Any]) -> tuple[str | None, str]:
    notes: dict[str, Any] = {}
    raw_notes = fact.get("notes")
    if isinstance(raw_notes, dict):
        notes = raw_notes
    elif isinstance(raw_notes, str):
        try:
            parsed = json.loads(raw_notes)
            notes = parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            notes = {}
    entity_id = fact.get("entity_id")
    scope_id = notes.get("entity_scope_id") or notes.get("segment_entity_id") or entity_id
    scope_type = notes.get("financial_scope_type")
    if not scope_type:
        scope_type = (
            "segment"
            if notes.get("segment") or notes.get("segment_name") or scope_id != entity_id
            else "consolidated_entity"
        )
    return (str(scope_id) if scope_id else None, str(scope_type))


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
