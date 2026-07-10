from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from finraw.builds import deactivate_active_rows, finish_build, start_build
from finraw.db.client import DBProtocol


def refresh_source_metric_definitions(db: DBProtocol, config: dict[str, Any], output_dir: str | None = None) -> dict[str, Any]:
    build_id = start_build(db, layer="fact_validation", command="refresh-source-definitions", prefix="source_definitions")
    deactivate_active_rows(db, "source_metric_definitions", build_id)
    rows = [dict(row) for row in db.fetchall(
        """
        SELECT mam.source_id, mam.metric_id, mam.raw_field_name, mam.raw_concept_name,
               mam.confidence_score, m.canonical_name, m.default_unit, m.period_type,
               m.revision_risk, m.ambiguity_notes
        FROM metric_alias_map mam
        LEFT JOIN metrics m ON m.metric_id = mam.metric_id
        WHERE COALESCE(mam.is_active, 1) = 1
          AND COALESCE(m.is_active, 1) = 1
        """
    )]
    source_metadata = _source_metadata_context(db)
    inserted = 0
    source_counts = Counter()
    seen_definition_ids: set[str] = set()
    for row in rows:
        if not row.get("source_id"):
            continue
        concept = row.get("raw_concept_name") or row.get("raw_field_name") or row.get("metric_id")
        definition = _definition_row(row, source_metadata.get((row.get("source_id"), concept), {}))
        if definition["definition_id"] in seen_definition_ids:
            continue
        seen_definition_ids.add(definition["definition_id"])
        db.execute(
            """
            INSERT INTO source_metric_definitions (
                definition_id, source_id, metric_id, raw_concept_name, definition_text,
                unit_rule, frequency, vintage_policy, is_forecast, comparable_to_metric_id,
                comparability_level, notes, build_id, is_active, superseded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (definition_id) DO UPDATE SET
                source_id=excluded.source_id,
                metric_id=excluded.metric_id,
                raw_concept_name=excluded.raw_concept_name,
                definition_text=excluded.definition_text,
                unit_rule=excluded.unit_rule,
                frequency=excluded.frequency,
                vintage_policy=excluded.vintage_policy,
                is_forecast=excluded.is_forecast,
                comparable_to_metric_id=excluded.comparable_to_metric_id,
                comparability_level=excluded.comparability_level,
                notes=excluded.notes,
                build_id=excluded.build_id,
                is_active=1,
                superseded_by=NULL
            """,
            [
                definition.get("definition_id"), definition.get("source_id"), definition.get("metric_id"),
                definition.get("raw_concept_name"), definition.get("definition_text"), definition.get("unit_rule"),
                definition.get("frequency"), definition.get("vintage_policy"), definition.get("is_forecast"),
                definition.get("comparable_to_metric_id"), definition.get("comparability_level"), definition.get("notes"),
                build_id, 1, None,
            ],
        )
        inserted += 1
        source_counts[definition["source_id"]] += 1
    report = {
        "build_id": build_id,
        "definition_count": inserted,
        "source_counts": dict(sorted(source_counts.items(), key=lambda item: str(item[0]))),
        "notes": [
            "Definitions are source/metric/concept crosswalk metadata; they do not overwrite raw or standardized facts.",
            "IMF WEO definitions are marked actual_plus_forecast because future-year observations are forecasts.",
            "World Bank and IMF macro indicators are comparable only at definition level until vintage and release calendar alignment is added.",
        ],
    }
    if output_dir:
        paths = write_source_definition_report(report, output_dir)
        report["written_files"] = [str(path) for path in paths]
    finish_build(db, build_id, "success", f"definition_count={inserted}")
    return report


def refresh_time_series_frequency_map(db: DBProtocol, config: dict[str, Any], output_dir: str | None = None) -> dict[str, Any]:
    build_id = start_build(db, layer="fact_validation", command="refresh-frequency-map", prefix="frequency_map")
    deactivate_active_rows(db, "time_series_frequency_map", build_id)
    source_entities = [dict(row) for row in db.fetchall("SELECT source_code, source_name, raw_metadata FROM source_entities WHERE source_id = 'fred_observations'")]
    aliases = {row["raw_concept_name"]: row["metric_id"] for row in db.fetchall("SELECT raw_concept_name, metric_id FROM metric_alias_map WHERE source_id = 'fred_observations' AND COALESCE(is_active, 1) = 1")}
    inserted = 0
    frequency_counts = Counter()
    for row in source_entities:
        series_id = row.get("source_code")
        metadata = _json_value(row.get("raw_metadata"))
        if not series_id or not isinstance(metadata, dict):
            continue
        metric_id = aliases.get(series_id)
        if not metric_id:
            continue
        frequency = _normalise_frequency(metadata.get("frequency") or metadata.get("frequency_short"))
        seasonal = _seasonal_adjustment(metadata.get("seasonal_adjustment") or metadata.get("seasonal_adjustment_short"))
        source_units = metadata.get("units") or metadata.get("units_short")
        item = {
            "frequency_id": _id("freq", "fred_observations", series_id, metric_id),
            "source_id": "fred_observations",
            "metric_id": metric_id,
            "series_id": series_id,
            "frequency": frequency,
            "seasonal_adjustment": seasonal,
            "period_type": _period_type_for_frequency(frequency),
            "annualization_rule": _annualization_rule(frequency, source_units),
            "source_units": source_units,
            "notes": json.dumps({"title": row.get("source_name"), "fred_frequency": metadata.get("frequency")}, ensure_ascii=False, sort_keys=True),
        }
        db.execute(
            """
            INSERT INTO time_series_frequency_map (
                frequency_id, source_id, metric_id, series_id, frequency, seasonal_adjustment,
                period_type, annualization_rule, source_units, notes, build_id, is_active, superseded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (frequency_id) DO UPDATE SET
                source_id=excluded.source_id,
                metric_id=excluded.metric_id,
                series_id=excluded.series_id,
                frequency=excluded.frequency,
                seasonal_adjustment=excluded.seasonal_adjustment,
                period_type=excluded.period_type,
                annualization_rule=excluded.annualization_rule,
                source_units=excluded.source_units,
                notes=excluded.notes,
                build_id=excluded.build_id,
                is_active=1,
                superseded_by=NULL
            """,
            [item[k] for k in ["frequency_id", "source_id", "metric_id", "series_id", "frequency", "seasonal_adjustment", "period_type", "annualization_rule", "source_units", "notes"]] + [build_id, 1, None],
        )
        inserted += 1
        frequency_counts[frequency or "unknown"] += 1
    report = {
        "build_id": build_id,
        "frequency_count": inserted,
        "frequency_counts": dict(sorted(frequency_counts.items())),
        "notes": [
            "Frequency map is used to decide which derived calculations are valid for daily, weekly, monthly, quarterly, and annual FRED series.",
            "High-frequency derived facts remain conservative until a full trading/observation calendar layer exists.",
        ],
    }
    if output_dir:
        paths = write_frequency_report(report, output_dir)
        report["written_files"] = [str(path) for path in paths]
    finish_build(db, build_id, "success", f"frequency_count={inserted}")
    return report


def _source_metadata_context(db: DBProtocol) -> dict[tuple[str | None, str | None], dict[str, Any]]:
    try:
        rows = db.fetchall("SELECT source_id, source_code, raw_metadata FROM source_entities")
    except Exception:
        return {}
    context = {}
    for row in rows:
        item = dict(row)
        metadata = _json_value(item.get("raw_metadata"))
        if isinstance(metadata, dict):
            context[(item.get("source_id"), item.get("source_code"))] = metadata
    return context


def _definition_row(row: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    source_id = row.get("source_id")
    concept = row.get("raw_concept_name") or row.get("raw_field_name") or row.get("metric_id")
    metadata = metadata or {}
    policy = _source_policy(source_id, metadata)
    notes = {
        "canonical_name": row.get("canonical_name"),
        "revision_risk": row.get("revision_risk"),
        "ambiguity_notes": row.get("ambiguity_notes"),
        "alias_confidence": row.get("confidence_score"),
        "source_title": metadata.get("title") or metadata.get("name"),
        "source_units": metadata.get("units") or metadata.get("unit"),
        "source_frequency": metadata.get("frequency") or metadata.get("frequency_short"),
        "source_seasonal_adjustment": metadata.get("seasonal_adjustment") or metadata.get("seasonal_adjustment_short"),
    }
    return {
        "definition_id": _id("sdef", source_id, row.get("metric_id"), concept),
        "source_id": source_id,
        "metric_id": row.get("metric_id"),
        "raw_concept_name": concept,
        "definition_text": _definition_text(row, metadata),
        "unit_rule": _unit_rule(source_id, row),
        "frequency": policy["frequency"],
        "vintage_policy": policy["vintage_policy"],
        "is_forecast": policy["is_forecast"],
        "comparable_to_metric_id": row.get("metric_id"),
        "comparability_level": policy["comparability_level"],
        "notes": json.dumps(notes, ensure_ascii=False, sort_keys=True, default=str),
    }


def _source_policy(source_id: str | None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = metadata or {}
    if source_id == "imf_sdmx":
        return {"frequency": "annual", "vintage_policy": "IMF release; future years may be forecasts", "is_forecast": True, "comparability_level": "definition_level"}
    if source_id == "worldbank_indicators":
        return {"frequency": "annual", "vintage_policy": "World Bank latest available revision", "is_forecast": False, "comparability_level": "definition_level"}
    if source_id == "fred_observations":
        return {"frequency": _normalise_frequency(metadata.get("frequency") or metadata.get("frequency_short")) or "series_metadata", "vintage_policy": "FRED realtime_start/realtime_end retained when available", "is_forecast": False, "comparability_level": "series_level"}
    if source_id == "sec_companyfacts":
        return {"frequency": "filing_period", "vintage_policy": "SEC filed date and accession retained; amendments/restatements selected upstream", "is_forecast": False, "comparability_level": "xbrl_concept_level"}
    return {"frequency": None, "vintage_policy": None, "is_forecast": False, "comparability_level": "source_metadata_only"}


def _definition_text(row: dict[str, Any], metadata: dict[str, Any] | None = None) -> str:
    source_id = row.get("source_id")
    concept = row.get("raw_concept_name") or row.get("raw_field_name")
    metric = row.get("canonical_name") or row.get("metric_id")
    title = (metadata or {}).get("title") or (metadata or {}).get("name")
    suffix = f" Source title: {title}." if title else ""
    return f"{source_id}:{concept} mapped to canonical metric {metric}.{suffix}"


def _unit_rule(source_id: str | None, row: dict[str, Any]) -> str | None:
    unit = row.get("default_unit")
    if source_id in {"imf_sdmx", "worldbank_indicators", "fred_observations"}:
        return f"source reported unit normalized by fact_standardization; default_unit={unit}"
    if source_id == "sec_companyfacts":
        return "XBRL unitRef normalized by fact_standardization"
    return unit


def write_source_definition_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    return _write_report(report, output_dir, "source_metric_definitions_report", "Source Metric Definitions Report", "definition_count", "Definitions")


def write_frequency_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    return _write_report(report, output_dir, "time_series_frequency_report", "Time Series Frequency Report", "frequency_count", "Frequency mappings")


def _write_report(report: dict[str, Any], output_dir: str, stem: str, title: str, count_key: str, count_label: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / f"{stem}.json"
    md_path = out / f"{stem}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    lines = [f"# {title}", "", f"{count_label}: {report.get(count_key, 0)}", ""]
    for section in ["source_counts", "frequency_counts"]:
        if report.get(section):
            lines.extend([f"## {section}", ""])
            for key, value in report[section].items():
                lines.append(f"- {key}: {value}")
            lines.append("")
    lines.extend(["## Notes", ""])
    for note in report.get("notes", []):
        lines.append(f"- {note}")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return [json_path, md_path]


def _normalise_frequency(value: Any) -> str | None:
    text = str(value or "").lower()
    if "daily" in text or text == "d":
        return "daily"
    if "weekly" in text or text == "w":
        return "weekly"
    if "monthly" in text or text == "m":
        return "monthly"
    if "quarter" in text or text == "q":
        return "quarterly"
    if "annual" in text or "year" in text or text == "a":
        return "annual"
    return text or None


def _seasonal_adjustment(value: Any) -> str | None:
    text = str(value or "").lower()
    if "seasonally adjusted" in text or text in {"sa", "saar"}:
        return "seasonally_adjusted"
    if "not seasonally adjusted" in text or text == "nsa":
        return "not_seasonally_adjusted"
    return text or None


def _period_type_for_frequency(frequency: str | None) -> str | None:
    if frequency in {"daily", "weekly", "monthly", "quarterly", "annual"}:
        return "observation_period"
    return None


def _annualization_rule(frequency: str | None, source_units: Any) -> str:
    units = str(source_units or "").lower()
    if "annual rate" in units or "saar" in units:
        return "already_annualized"
    if frequency == "quarterly":
        return "quarterly_observation_not_annualized_unless_units_say_so"
    return "reported_observation"


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha1("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"
