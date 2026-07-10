from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from finraw.db.client import DBProtocol
from finraw.quality import QualityGateError

GRAPH_READY_STATUSES = {"single_source", "cross_verified"}
DEFAULT_CRITICAL_METRICS = ["revenue", "total_assets", "net_income"]


def enforce_fact_quality_gates(db: DBProtocol, config: dict[str, Any], output_dir: str | None = None) -> dict[str, Any]:
    _ensure_graph_ready_columns(db)
    _ensure_candidate_boundary_columns(db)
    gates = config.get("fact_quality_gates", {})
    rows = [dict(row) for row in db.fetchall("SELECT * FROM standardized_facts WHERE COALESCE(is_active, 1) = 1")]
    ready_updates = _graph_ready_updates(rows)
    _apply_graph_ready_updates(db, ready_updates)

    report = _build_fact_quality_report(db, rows, ready_updates, gates)
    failures = _fact_quality_failures(report, gates)
    report["fact_quality_gate_failures"] = failures
    report["fact_quality_gate_status"] = "failed" if failures else "passed"
    if output_dir:
        paths = write_fact_quality_report(report, output_dir)
        report["written_files"] = [str(path) for path in paths]
    if failures and gates.get("raise_on_failure", True):
        raise QualityGateError("; ".join(failures))
    return report


def _ensure_graph_ready_columns(db: DBProtocol) -> None:
    for column, column_type in [("graph_ready", "INTEGER DEFAULT 0"), ("graph_ready_reason", "TEXT")]:
        try:
            db.execute(f"ALTER TABLE standardized_facts ADD COLUMN {column} {column_type}")
        except Exception:
            pass
    try:
        db.execute("CREATE INDEX IF NOT EXISTS idx_standardized_facts_graph_ready ON standardized_facts(graph_ready)")
    except Exception:
        pass


def _ensure_candidate_boundary_columns(db: DBProtocol) -> None:
    columns = [
        ("candidate_state", "TEXT"),
        ("state_reason", "TEXT"),
        ("matched_metric_id", "TEXT"),
        ("evidence_status", "TEXT"),
        ("cross_check_status", "TEXT"),
        ("promotion_status", "TEXT"),
        ("promoted_fact_id", "TEXT"),
        ("qa_eligible", "INTEGER DEFAULT 0"),
        ("kg_eligible", "INTEGER DEFAULT 0"),
    ]
    for column, column_type in columns:
        try:
            db.execute(f"ALTER TABLE candidate_facts ADD COLUMN {column} {column_type}")
        except Exception:
            pass
    for sql in [
        "CREATE INDEX IF NOT EXISTS idx_candidate_facts_state ON candidate_facts(candidate_state, promotion_status)",
        "CREATE INDEX IF NOT EXISTS idx_candidate_facts_eligibility ON candidate_facts(qa_eligible, kg_eligible)",
    ]:
        try:
            db.execute(sql)
        except Exception:
            pass


def _graph_ready_updates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    updates = []
    for row in rows:
        reasons = []
        if not row.get("entity_id"):
            reasons.append("missing_entity")
        if not row.get("metric_id"):
            reasons.append("missing_metric")
        if row.get("normalized_value") is None:
            reasons.append("null_value")
        if not row.get("period_end"):
            reasons.append("missing_period_end")
        if not row.get("source_id"):
            reasons.append("missing_source")
        if not row.get("source_definition_id"):
            reasons.append("missing_source_definition")
        if str(row.get("normalized_unit") or row.get("unit") or "").lower() == "document":
            reasons.append("document_fact")
        if row.get("verification_status") not in GRAPH_READY_STATUSES:
            reasons.append(f"status_{row.get('verification_status') or 'missing'}")
        graph_ready = 0 if reasons else 1
        updates.append({"fact_id": row.get("fact_id"), "graph_ready": graph_ready, "graph_ready_reason": ",".join(reasons) if reasons else "ready"})
    return updates


def _apply_graph_ready_updates(db: DBProtocol, updates: list[dict[str, Any]], batch_size: int = 10000) -> None:
    if not updates:
        return
    for start in range(0, len(updates), batch_size):
        batch = updates[start:start + batch_size]
        db.update_standardized_graph_ready(batch)


def _build_fact_quality_report(db: DBProtocol, rows: list[dict[str, Any]], updates: list[dict[str, Any]], gates: dict[str, Any]) -> dict[str, Any]:
    total = len(rows)
    status_counts = Counter(str(row.get("verification_status") or "missing") for row in rows)
    graph_ready_count = sum(1 for row in updates if row["graph_ready"])
    not_ready_reasons = Counter()
    for row in updates:
        if row["graph_ready"]:
            continue
        for reason in str(row.get("graph_ready_reason") or "").split(","):
            if reason:
                not_ready_reasons[reason] += 1

    missing_entity_count = sum(1 for row in rows if not row.get("entity_id"))
    missing_metric_count = sum(1 for row in rows if not row.get("metric_id"))
    missing_period_end_count = sum(1 for row in rows if not row.get("period_end"))
    missing_source_count = sum(1 for row in rows if not row.get("source_id"))
    missing_source_definition_count = sum(1 for row in rows if not row.get("source_definition_id"))
    null_value_count = sum(1 for row in rows if row.get("normalized_value") is None)
    document_fact_count = sum(1 for row in rows if str(row.get("normalized_unit") or "").lower() == "document")
    rejected_fact_count = status_counts.get("rejected", 0)
    conflict_fact_count = status_counts.get("conflict", 0)
    cross_verified_count = status_counts.get("cross_verified", 0)
    single_source_count = status_counts.get("single_source", 0)

    graph_ready_by_fact_id = {str(row["fact_id"]): bool(row["graph_ready"]) for row in updates if row.get("fact_id")}
    entity_types = _load_entity_types(db)
    metric_coverage_by_entity = _metric_coverage_by_entity(rows, gates, graph_ready_by_fact_id, entity_types)
    year_coverage_by_metric = _year_coverage_by_metric(rows, gates, graph_ready_by_fact_id)

    candidate_boundary = _candidate_boundary_report(db)

    return {
        "active_standardized_fact_count": total,
        "missing_entity_count": missing_entity_count,
        "missing_metric_count": missing_metric_count,
        "missing_period_end_count": missing_period_end_count,
        "missing_source_count": missing_source_count,
        "missing_source_definition_count": missing_source_definition_count,
        "null_value_count": null_value_count,
        "document_fact_count": document_fact_count,
        "rejected_fact_count": rejected_fact_count,
        "conflict_fact_count": conflict_fact_count,
        "cross_verified_count": cross_verified_count,
        "single_source_count": single_source_count,
        "cross_verified_ratio": _ratio(cross_verified_count, total),
        "single_source_ratio": _ratio(single_source_count, total),
        "graph_ready_count": graph_ready_count,
        "graph_ready_ratio": _ratio(graph_ready_count, total),
        "verification_status_counts": dict(sorted(status_counts.items())),
        "not_graph_ready_reason_counts": dict(sorted(not_ready_reasons.items())),
        "metric_coverage_by_entity": metric_coverage_by_entity,
        "year_coverage_by_metric": year_coverage_by_metric,
        "source_document_active_count": _scalar(db, "SELECT COUNT(*) AS c FROM source_documents WHERE COALESCE(is_active, 1) = 1"),
        "derived_facts_active_count": _scalar(db, "SELECT COUNT(*) AS c FROM derived_facts WHERE COALESCE(is_active, 1) = 1"),
        **candidate_boundary,
    }


def _candidate_boundary_report(db: DBProtocol) -> dict[str, Any]:
    active_count = _scalar(db, "SELECT COUNT(*) AS c FROM candidate_facts WHERE COALESCE(is_active, 1) = 1")
    qa_eligible_count = _scalar(db, "SELECT COUNT(*) AS c FROM candidate_facts WHERE COALESCE(is_active, 1) = 1 AND COALESCE(qa_eligible, 0) <> 0")
    kg_eligible_count = _scalar(db, "SELECT COUNT(*) AS c FROM candidate_facts WHERE COALESCE(is_active, 1) = 1 AND COALESCE(kg_eligible, 0) <> 0")
    promoted_count = _scalar(db, "SELECT COUNT(*) AS c FROM candidate_facts WHERE COALESCE(is_active, 1) = 1 AND candidate_state = 'promoted_to_atomic_fact'")
    state_counts = _group_counts(db, "SELECT COALESCE(candidate_state, 'missing') AS key, COUNT(*) AS c FROM candidate_facts WHERE COALESCE(is_active, 1) = 1 GROUP BY COALESCE(candidate_state, 'missing')")
    promotion_counts = _group_counts(db, "SELECT COALESCE(promotion_status, 'missing') AS key, COUNT(*) AS c FROM candidate_facts WHERE COALESCE(is_active, 1) = 1 GROUP BY COALESCE(promotion_status, 'missing')")
    return {
        "candidate_facts_active_count": active_count,
        "candidate_state_counts": state_counts,
        "candidate_promotion_status_counts": promotion_counts,
        "candidate_qa_eligible_count": qa_eligible_count,
        "candidate_kg_eligible_count": kg_eligible_count,
        "candidate_promoted_to_atomic_count": promoted_count,
    }


def _metric_coverage_by_entity(rows: list[dict[str, Any]], gates: dict[str, Any], graph_ready_by_fact_id: dict[str, bool], entity_types: dict[str, str]) -> dict[str, Any]:
    metrics = gates.get("critical_metrics", DEFAULT_CRITICAL_METRICS)
    years_by_entity_metric: dict[tuple[str, str], set[int]] = defaultdict(set)
    for row in rows:
        if not graph_ready_by_fact_id.get(str(row.get("fact_id"))):
            continue
        entity_id = row.get("entity_id")
        metric_id = row.get("metric_id")
        year = row.get("fiscal_year") or row.get("calendar_year")
        if entity_id and metric_id in metrics and year:
            try:
                years_by_entity_metric[(str(entity_id), str(metric_id))].add(int(year))
            except (TypeError, ValueError):
                continue
    entity_ids = sorted({str(row.get("entity_id")) for row in rows if row.get("entity_id")})
    company_entity_ids = [entity_id for entity_id in entity_ids if entity_types.get(entity_id) == "company"]
    min_years = int(gates.get("min_years_per_company_critical_metric", 0) or 0)
    failing = []
    for entity_id in company_entity_ids:
        for metric_id in metrics:
            year_count = len(years_by_entity_metric.get((entity_id, metric_id), set()))
            if min_years and year_count < min_years:
                failing.append({"entity_id": entity_id, "metric_id": metric_id, "year_count": year_count, "required_years": min_years})
    sample = []
    for (entity_id, metric_id), years in sorted(years_by_entity_metric.items())[:200]:
        sample.append({"entity_id": entity_id, "metric_id": metric_id, "year_count": len(years), "min_year": min(years), "max_year": max(years)})
    return {"critical_metrics": metrics, "company_entity_count": len(company_entity_ids), "sample": sample, "failing_count": len(failing), "failing_sample": failing[:200]}


def _year_coverage_by_metric(rows: list[dict[str, Any]], gates: dict[str, Any], graph_ready_by_fact_id: dict[str, bool]) -> dict[str, Any]:
    metrics = gates.get("coverage_metrics", gates.get("critical_metrics", DEFAULT_CRITICAL_METRICS))
    years_by_metric: dict[str, set[int]] = defaultdict(set)
    entities_by_metric: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if not graph_ready_by_fact_id.get(str(row.get("fact_id"))):
            continue
        metric_id = row.get("metric_id")
        if metric_id not in metrics:
            continue
        year = row.get("fiscal_year") or row.get("calendar_year")
        if year:
            try:
                years_by_metric[str(metric_id)].add(int(year))
            except (TypeError, ValueError):
                pass
        if row.get("entity_id"):
            entities_by_metric[str(metric_id)].add(str(row["entity_id"]))
    out = {}
    for metric_id in metrics:
        years = years_by_metric.get(metric_id, set())
        out[metric_id] = {"year_count": len(years), "min_year": min(years) if years else None, "max_year": max(years) if years else None, "entity_count": len(entities_by_metric.get(metric_id, set()))}
    return out


def _load_entity_types(db: DBProtocol) -> dict[str, str]:
    try:
        rows = db.fetchall("SELECT entity_id, entity_type FROM canonical_entities WHERE COALESCE(is_active, 1) = 1")
    except Exception:
        return {}
    out = {}
    for row in rows:
        item = dict(row)
        if item.get("entity_id") and item.get("entity_type"):
            out[str(item["entity_id"])] = str(item["entity_type"])
    return out


def _fact_quality_failures(report: dict[str, Any], gates: dict[str, Any]) -> list[str]:
    failures = []
    checks = [
        ("missing_entity_count", "max_missing_entity_count", 0),
        ("missing_metric_count", "max_missing_metric_count", 0),
        ("missing_period_end_count", "max_missing_period_end_count", 0),
        ("missing_source_count", "max_missing_source_count", 0),
        ("missing_source_definition_count", "max_missing_source_definition_count", 0),
        ("null_value_count", "max_null_value_count", 0),
        ("document_fact_count", "max_document_fact_count", 0),
        ("rejected_fact_count", "max_rejected_fact_count", None),
        ("conflict_fact_count", "max_conflict_fact_count", None),
    ]
    for metric_key, gate_key, default in checks:
        if default is None and gate_key not in gates:
            continue
        maximum = int(gates.get(gate_key, default))
        actual = int(report.get(metric_key, 0))
        if actual > maximum:
            failures.append(f"{metric_key}={actual} > {maximum}")

    ratio_checks = [
        ("rejected_fact_count", "max_rejected_ratio", None),
        ("conflict_fact_count", "max_conflict_ratio", None),
        ("cross_verified_ratio", "min_cross_verified_ratio", None),
        ("single_source_ratio", "max_single_source_ratio", None),
        ("graph_ready_ratio", "min_graph_ready_ratio", None),
    ]
    total = int(report.get("active_standardized_fact_count") or 0)
    for metric_key, gate_key, default in ratio_checks:
        if default is None and gate_key not in gates:
            continue
        threshold = float(gates.get(gate_key, default))
        if metric_key.endswith("_count"):
            value = _ratio(report.get(metric_key, 0), total)
            comparator = "max"
        else:
            value = float(report.get(metric_key, 0) or 0)
            comparator = "min" if gate_key.startswith("min_") else "max"
        if comparator == "max" and value > threshold:
            failures.append(f"{metric_key}_ratio={value:.6f} > {threshold:.6f}")
        if comparator == "min" and value < threshold:
            failures.append(f"{metric_key}={value:.6f} < {threshold:.6f}")

    candidate_qa_eligible_count = int(report.get("candidate_qa_eligible_count", 0) or 0)
    if candidate_qa_eligible_count > int(gates.get("max_candidate_qa_eligible_count", 0) or 0):
        failures.append(f"candidate_qa_eligible_count={candidate_qa_eligible_count} > {int(gates.get('max_candidate_qa_eligible_count', 0) or 0)}")
    candidate_kg_eligible_count = int(report.get("candidate_kg_eligible_count", 0) or 0)
    if candidate_kg_eligible_count > int(gates.get("max_candidate_kg_eligible_count", 0) or 0):
        failures.append(f"candidate_kg_eligible_count={candidate_kg_eligible_count} > {int(gates.get('max_candidate_kg_eligible_count', 0) or 0)}")

    min_graph_ready_count = int(gates.get("min_graph_ready_count", 1) or 0)
    if int(report.get("graph_ready_count", 0)) < min_graph_ready_count:
        failures.append(f"graph_ready_count={report.get('graph_ready_count', 0)} < {min_graph_ready_count}")

    min_years = int(gates.get("min_years_per_company_critical_metric", 0) or 0)
    failing_coverage = int(report.get("metric_coverage_by_entity", {}).get("failing_count", 0))
    if min_years and failing_coverage:
        failures.append(f"metric_coverage_by_entity_failing_count={failing_coverage} > 0")
    return failures


def write_fact_quality_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "fact_quality_report.json"
    md_path = out / "fact_quality_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path.write_text(_markdown_report(report), encoding="utf-8")
    return [json_path, md_path]


def _markdown_report(report: dict[str, Any]) -> str:
    lines = ["# Fact Quality Report", ""]
    for key in ["fact_quality_gate_status", "active_standardized_fact_count", "graph_ready_count", "graph_ready_ratio", "missing_entity_count", "missing_metric_count", "missing_source_definition_count", "null_value_count", "rejected_fact_count", "conflict_fact_count", "cross_verified_ratio", "single_source_ratio", "document_fact_count", "candidate_facts_active_count", "candidate_qa_eligible_count", "candidate_kg_eligible_count", "candidate_promoted_to_atomic_count"]:
        if key in report:
            lines.append(f"- {key}: {report[key]}")
    lines.extend(["", "## Failures", ""])
    for failure in report.get("fact_quality_gate_failures", []):
        lines.append(f"- {failure}")
    if not report.get("fact_quality_gate_failures"):
        lines.append("- none")
    lines.extend(["", "## Candidate Fact States", ""])
    for key, value in report.get("candidate_state_counts", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Candidate Promotion Status", ""])
    for key, value in report.get("candidate_promotion_status_counts", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Not Graph Ready Reasons", ""])
    for key, value in report.get("not_graph_ready_reason_counts", {}).items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    return "\n".join(lines)


def _ratio(numerator: Any, denominator: Any) -> float:
    denominator = int(denominator or 0)
    return float(numerator or 0) / denominator if denominator else 0.0


def _group_counts(db: DBProtocol, sql: str) -> dict[str, int]:
    try:
        rows = db.fetchall(sql)
    except Exception:
        return {}
    return {str(row["key"]): int(row["c"] or 0) for row in rows}


def _scalar(db: DBProtocol, sql: str) -> int:
    try:
        row = db.fetchone(sql)
    except Exception:
        return 0
    return int(row["c"] if row and row["c"] is not None else 0)
