from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from finraw.db.client import DBProtocol

KG_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS kg_builds (
    kg_build_id          TEXT PRIMARY KEY,
    input_fact_build_id  TEXT,
    input_qa_build_id    TEXT,
    status               TEXT,
    started_at           TEXT,
    completed_at         TEXT,
    node_count           INTEGER,
    edge_count           INTEGER,
    quality_status       TEXT,
    notes                TEXT,
    is_active            INTEGER DEFAULT 1,
    superseded_by        TEXT
);
CREATE TABLE IF NOT EXISTS kg_nodes (
    node_id              TEXT PRIMARY KEY,
    stable_node_id       TEXT,
    kg_build_id          TEXT REFERENCES kg_builds(kg_build_id),
    node_type            TEXT NOT NULL,
    source_table         TEXT,
    source_pk            TEXT,
    properties_json      TEXT,
    is_active            INTEGER DEFAULT 1,
    superseded_by        TEXT,
    created_at           TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_build_type ON kg_nodes(kg_build_id, node_type);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_stable ON kg_nodes(stable_node_id);
CREATE TABLE IF NOT EXISTS kg_edges (
    edge_id              TEXT PRIMARY KEY,
    stable_edge_id       TEXT,
    kg_build_id          TEXT REFERENCES kg_builds(kg_build_id),
    src_node_id          TEXT NOT NULL,
    dst_node_id          TEXT NOT NULL,
    relation_type        TEXT NOT NULL,
    source_table         TEXT,
    source_pk            TEXT,
    properties_json      TEXT,
    is_active            INTEGER DEFAULT 1,
    superseded_by        TEXT,
    created_at           TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_kg_edges_build_type ON kg_edges(kg_build_id, relation_type);
CREATE INDEX IF NOT EXISTS idx_kg_edges_src ON kg_edges(src_node_id);
CREATE INDEX IF NOT EXISTS idx_kg_edges_dst ON kg_edges(dst_node_id);
CREATE INDEX IF NOT EXISTS idx_kg_edges_stable ON kg_edges(stable_edge_id);
CREATE TABLE IF NOT EXISTS kg_quality_checks (
    check_id             TEXT PRIMARY KEY,
    kg_build_id          TEXT REFERENCES kg_builds(kg_build_id),
    check_type           TEXT,
    status               TEXT,
    severity             TEXT,
    message              TEXT,
    created_at           TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_kg_quality_checks_build ON kg_quality_checks(kg_build_id, status, severity);
"""

NODE_COLUMNS = ["node_id", "stable_node_id", "kg_build_id", "node_type", "source_table", "source_pk", "properties_json", "is_active", "superseded_by"]
EDGE_COLUMNS = ["edge_id", "stable_edge_id", "kg_build_id", "src_node_id", "dst_node_id", "relation_type", "source_table", "source_pk", "properties_json", "is_active", "superseded_by"]
CHECK_COLUMNS = ["check_id", "kg_build_id", "check_type", "status", "severity", "message"]


def build_kg(db: DBProtocol, config: dict[str, Any], output_dir: str | None = None, batch_size: int = 20000) -> dict[str, Any]:
    ensure_kg_schema(db)
    input_fact_build_id = _active_build_id(db, "standardized_facts")
    input_qa_build_id = _active_build_id(db, "derived_facts")
    kg_build_id = _new_kg_build_id()
    started_at = _now()
    _insert_kg_build(db, {
        "kg_build_id": kg_build_id,
        "input_fact_build_id": input_fact_build_id,
        "input_qa_build_id": input_qa_build_id,
        "status": "running",
        "started_at": started_at,
        "completed_at": None,
        "node_count": 0,
        "edge_count": 0,
        "quality_status": None,
        "notes": json.dumps({"source": "build-kg", "policy": "graph_ready_standardized_facts_and_active_derived_facts_only"}, sort_keys=True),
        "is_active": 0,
        "superseded_by": None,
    })

    node_writer = _BatchWriter(db, "kg_nodes", NODE_COLUMNS, batch_size)
    edge_writer = _BatchWriter(db, "kg_edges", EDGE_COLUMNS, batch_size)
    seen_nodes: set[str] = set()
    seen_edges: set[str] = set()
    node_type_counts: Counter[str] = Counter()
    edge_type_counts: Counter[str] = Counter()

    def add_node(stable_node_id: str, node_type: str, source_table: str | None, source_pk: Any, properties: dict[str, Any]) -> str:
        node_id = _versioned_graph_id(stable_node_id, kg_build_id)
        if node_id in seen_nodes:
            return node_id
        seen_nodes.add(node_id)
        node_type_counts[node_type] += 1
        node_writer.add({
            "node_id": node_id,
            "stable_node_id": stable_node_id,
            "kg_build_id": kg_build_id,
            "node_type": node_type,
            "source_table": source_table,
            "source_pk": str(source_pk) if source_pk is not None else None,
            "properties_json": _json(properties),
            "is_active": 1,
            "superseded_by": None,
        })
        return node_id

    def add_edge(src_stable: str, relation_type: str, dst_stable: str, source_table: str | None, source_pk: Any, properties: dict[str, Any] | None = None) -> str:
        stable_edge_id = _stable_edge_id(src_stable, relation_type, dst_stable, source_table, source_pk)
        edge_id = _versioned_graph_id(stable_edge_id, kg_build_id)
        if edge_id in seen_edges:
            return edge_id
        seen_edges.add(edge_id)
        edge_type_counts[relation_type] += 1
        edge_writer.add({
            "edge_id": edge_id,
            "stable_edge_id": stable_edge_id,
            "kg_build_id": kg_build_id,
            "src_node_id": _versioned_graph_id(src_stable, kg_build_id),
            "dst_node_id": _versioned_graph_id(dst_stable, kg_build_id),
            "relation_type": relation_type,
            "source_table": source_table,
            "source_pk": str(source_pk) if source_pk is not None else None,
            "properties_json": _json(properties or {}),
            "is_active": 1,
            "superseded_by": None,
        })
        return edge_id

    # Master data nodes.
    for row in _rows(db, "SELECT * FROM canonical_entities WHERE COALESCE(is_active, 1) = 1"):
        add_node(_entity_node(row.get("entity_id")), "Entity", "canonical_entities", row.get("entity_id"), _pick(row, ["entity_id", "canonical_name", "entity_type", "market", "country", "exchange", "ticker", "cik", "isin", "currency", "fiscal_year_end", "industry", "build_id"]))
    for row in _rows(db, "SELECT * FROM canonical_securities WHERE COALESCE(is_active, 1) = 1"):
        security = _security_node(row.get("security_id"))
        add_node(security, "Security", "canonical_securities", row.get("security_id"), _pick(row, ["security_id", "company_entity_id", "canonical_name", "security_type", "market", "country", "exchange", "ticker", "composite_ticker", "currency", "is_primary_listing", "listing_status", "build_id"]))
        if row.get("company_entity_id"):
            add_edge(_entity_node(row.get("company_entity_id")), "HAS_SECURITY", security, "canonical_securities", row.get("security_id"))
    for row in _rows(db, "SELECT * FROM metrics WHERE COALESCE(is_active, 1) = 1"):
        add_node(_metric_node(row.get("metric_id")), "Metric", "metrics", row.get("metric_id"), _pick(row, ["metric_id", "canonical_name", "metric_category", "statement_type", "period_type", "default_unit", "default_currency", "accounting_standard", "aggregation_rule", "revision_risk", "ambiguity_notes", "build_id"]))
    for row in _rows(db, "SELECT * FROM source_registry WHERE is_active IS DISTINCT FROM FALSE"):
        add_node(_source_node(row.get("source_id")), "DataSource", "source_registry", row.get("source_id"), _pick(row, ["source_id", "source_name", "source_type", "authority_level", "market", "provider", "base_url", "access_method", "update_frequency", "license_note", "rate_limit_note"]))
    for row in _rows(db, "SELECT * FROM source_metric_definitions WHERE COALESCE(is_active, 1) = 1"):
        source_def = _source_definition_node(row.get("definition_id"))
        add_node(source_def, "SourceDefinition", "source_metric_definitions", row.get("definition_id"), _pick(row, ["definition_id", "source_id", "metric_id", "raw_concept_name", "definition_text", "unit_rule", "frequency", "vintage_policy", "is_forecast", "comparable_to_metric_id", "comparability_level", "build_id"]))
        if row.get("metric_id"):
            add_edge(source_def, "DEFINES", _metric_node(row.get("metric_id")), "source_metric_definitions", row.get("definition_id"))

    # Facts and their source raw objects.
    fact_sql = """
        SELECT * FROM standardized_facts
        WHERE COALESCE(is_active, 1) = 1
          AND COALESCE(graph_ready, 0) = 1
          AND verification_status IN ('single_source', 'cross_verified')
    """
    for row in _rows(db, fact_sql):
        fact = _fact_node(row.get("fact_id"))
        add_node(fact, "Fact", "standardized_facts", row.get("fact_id"), _pick(row, ["fact_id", "stable_fact_id", "build_id", "entity_id", "metric_id", "normalized_value", "normalized_unit", "normalized_currency", "value_scale", "period_start", "period_end", "calendar_year", "fiscal_year", "fiscal_quarter", "time_basis", "metric_period_type", "source_definition_id", "frequency", "seasonal_adjustment", "vintage_policy", "is_forecast", "comparability_level", "source_id", "raw_object_id", "verification_status", "confidence_score"]))
        time = _time_node(row)
        add_node(time, "TimePeriod", "standardized_facts", row.get("fact_id"), _time_properties(row))
        if row.get("entity_id"):
            add_edge(_entity_node(row.get("entity_id")), "HAS_FACT", fact, "standardized_facts", row.get("fact_id"))
        if row.get("metric_id"):
            add_edge(fact, "MEASURES", _metric_node(row.get("metric_id")), "standardized_facts", row.get("fact_id"))
        add_edge(fact, "IN_PERIOD", time, "standardized_facts", row.get("fact_id"))
        if row.get("source_id"):
            add_edge(fact, "FROM_SOURCE", _source_node(row.get("source_id")), "standardized_facts", row.get("fact_id"))
        if row.get("raw_object_id"):
            raw = _raw_object_node(row.get("raw_object_id"))
            if _versioned_graph_id(raw, kg_build_id) not in seen_nodes:
                _add_raw_object_node(db, add_node, add_edge, row.get("raw_object_id"))
            add_edge(fact, "TRACED_TO", raw, "standardized_facts", row.get("fact_id"))
        if row.get("source_definition_id"):
            add_edge(fact, "USES_SOURCE_DEFINITION", _source_definition_node(row.get("source_definition_id")), "standardized_facts", row.get("fact_id"))

    # Source documents.
    for row in _rows(db, "SELECT * FROM source_documents WHERE COALESCE(is_active, 1) = 1"):
        doc = _document_node(row.get("document_id"))
        add_node(doc, "SourceDocument", "source_documents", row.get("document_id"), _pick(row, ["document_id", "stable_document_id", "build_id", "entity_id", "source_id", "form_type", "report_type", "period_end", "filing_date", "storage_uri", "original_url", "raw_object_id", "document_status"]))
        if row.get("entity_id"):
            add_edge(_entity_node(row.get("entity_id")), "FILED", doc, "source_documents", row.get("document_id"))
        if row.get("source_id"):
            add_edge(doc, "FROM_SOURCE", _source_node(row.get("source_id")), "source_documents", row.get("document_id"))
        if row.get("raw_object_id"):
            raw = _raw_object_node(row.get("raw_object_id"))
            if _versioned_graph_id(raw, kg_build_id) not in seen_nodes:
                _add_raw_object_node(db, add_node, add_edge, row.get("raw_object_id"))
            add_edge(doc, "HAS_RAW_OBJECT", raw, "source_documents", row.get("document_id"))

    # Derived facts and scopes.
    derived_sql = """
        SELECT * FROM derived_facts
        WHERE COALESCE(is_active, 1) = 1
          AND verification_status IN ('single_source', 'cross_verified')
    """
    for row in _rows(db, derived_sql):
        derived = _derived_fact_node(row.get("derived_id"))
        add_node(derived, "DerivedFact", "derived_facts", row.get("derived_id"), _pick(row, ["derived_id", "stable_derived_id", "build_id", "input_build_id", "derived_type", "entity_scope", "metric_scope", "time_scope", "scope_type", "scope_id", "scope_definition", "scope_entity_ids", "scope_source", "calculation_code", "output_value", "output_table", "unit", "tolerance", "verification_status"]))
        for fact_id in _json_list(row.get("input_fact_ids")):
            add_edge(derived, "DERIVED_FROM", _fact_node(fact_id), "derived_facts", row.get("derived_id"))
        entity_scope = _json_dict(row.get("entity_scope"))
        metric_scope = _json_dict(row.get("metric_scope"))
        time_scope = _json_dict(row.get("time_scope"))
        if entity_scope.get("entity_id"):
            add_edge(derived, "ABOUT_ENTITY", _entity_node(entity_scope.get("entity_id")), "derived_facts", row.get("derived_id"))
        metric_ids = {metric_scope.get("metric_id"), metric_scope.get("numerator"), metric_scope.get("denominator")}
        for metric_id in sorted(m for m in metric_ids if m):
            add_edge(derived, "USES_METRIC", _metric_node(metric_id), "derived_facts", row.get("derived_id"), {"metric_role": _metric_role(metric_scope, metric_id)})
        if time_scope:
            time = _derived_time_node(row.get("derived_id"), time_scope)
            add_node(time, "TimePeriod", "derived_facts", row.get("derived_id"), {"time_scope": time_scope})
            add_edge(derived, "IN_PERIOD", time, "derived_facts", row.get("derived_id"))
        if row.get("scope_id"):
            entity_set = _entity_set_node(row.get("scope_id"))
            add_node(entity_set, "EntitySet", "derived_facts", row.get("scope_id"), {"scope_id": row.get("scope_id"), "scope_type": row.get("scope_type"), "scope_definition": row.get("scope_definition"), "scope_source": row.get("scope_source")})
            add_edge(derived, "HAS_SCOPE", entity_set, "derived_facts", row.get("derived_id"))
            for entity_id in _json_list(row.get("scope_entity_ids")):
                add_edge(entity_set, "CONTAINS_ENTITY", _entity_node(entity_id), "derived_facts", row.get("scope_id"))

    node_writer.flush()
    edge_writer.flush()
    quality = kg_quality_report(db, kg_build_id, write_checks=True)
    node_count = _scalar(db, "SELECT COUNT(*) AS c FROM kg_nodes WHERE kg_build_id = ? AND COALESCE(is_active, 1) = 1", (kg_build_id,))
    edge_count = _scalar(db, "SELECT COUNT(*) AS c FROM kg_edges WHERE kg_build_id = ? AND COALESCE(is_active, 1) = 1", (kg_build_id,))
    quality_status = "passed" if not quality["kg_quality_gate_failures"] else "failed"
    completed_at = _now()
    _update_kg_build(db, kg_build_id, {
        "status": "success" if quality_status == "passed" else "quality_failed",
        "completed_at": completed_at,
        "node_count": node_count,
        "edge_count": edge_count,
        "quality_status": quality_status,
        "notes": _json({"node_type_counts": dict(sorted(node_type_counts.items())), "edge_type_counts": dict(sorted(edge_type_counts.items())), "quality": quality_status}),
    })
    if quality_status == "passed":
        _activate_kg_build(db, kg_build_id)
    report = {
        "kg_build_id": kg_build_id,
        "input_fact_build_id": input_fact_build_id,
        "input_qa_build_id": input_qa_build_id,
        "node_count": node_count,
        "edge_count": edge_count,
        "node_type_counts": dict(sorted(node_type_counts.items())),
        "edge_type_counts": dict(sorted(edge_type_counts.items())),
        "quality": quality,
    }
    if output_dir:
        report["written_files"] = [str(path) for path in write_kg_reports(report, output_dir)]
    return report


def kg_quality_report(db: DBProtocol, kg_build_id: str | None = None, output_dir: str | None = None, write_checks: bool = False) -> dict[str, Any]:
    ensure_kg_schema(db)
    kg_build_id = kg_build_id or _active_kg_build_id(db)
    if not kg_build_id:
        report = {"kg_build_id": None, "kg_quality_gate_status": "failed", "kg_quality_gate_failures": ["no_active_kg_build"]}
        if output_dir:
            report["written_files"] = [str(path) for path in write_kg_quality_report(report, output_dir)]
        return report
    checks = {
        "node_count": _scalar(db, "SELECT COUNT(*) AS c FROM kg_nodes WHERE kg_build_id = ? AND COALESCE(is_active, 1) = 1", (kg_build_id,)),
        "edge_count": _scalar(db, "SELECT COUNT(*) AS c FROM kg_edges WHERE kg_build_id = ? AND COALESCE(is_active, 1) = 1", (kg_build_id,)),
        "fact_node_count": _scalar(db, "SELECT COUNT(*) AS c FROM kg_nodes WHERE kg_build_id = ? AND node_type = 'Fact' AND COALESCE(is_active, 1) = 1", (kg_build_id,)),
        "graph_ready_fact_count": _scalar(db, "SELECT COUNT(*) AS c FROM standardized_facts WHERE COALESCE(is_active, 1) = 1 AND COALESCE(graph_ready, 0) = 1 AND verification_status IN ('single_source', 'cross_verified')"),
        "derived_fact_node_count": _scalar(db, "SELECT COUNT(*) AS c FROM kg_nodes WHERE kg_build_id = ? AND node_type = 'DerivedFact' AND COALESCE(is_active, 1) = 1", (kg_build_id,)),
        "active_derived_fact_count": _scalar(db, "SELECT COUNT(*) AS c FROM derived_facts WHERE COALESCE(is_active, 1) = 1 AND verification_status IN ('single_source', 'cross_verified')"),
        "candidate_fact_leak_count": _scalar(db, "SELECT COUNT(*) AS c FROM kg_nodes WHERE kg_build_id = ? AND (node_type = 'CandidateFact' OR source_table = 'candidate_facts')", (kg_build_id,)),
        "invalid_status_fact_count": _scalar(db, "SELECT COUNT(*) AS c FROM kg_nodes n JOIN standardized_facts sf ON n.source_pk = sf.fact_id WHERE n.kg_build_id = ? AND n.node_type = 'Fact' AND (COALESCE(sf.graph_ready, 0) <> 1 OR sf.verification_status NOT IN ('single_source', 'cross_verified'))", (kg_build_id,)),
        "candidate_kg_eligible_count": _scalar(db, "SELECT COUNT(*) AS c FROM candidate_facts WHERE COALESCE(is_active, 1) = 1 AND COALESCE(kg_eligible, 0) <> 0"),
        "missing_fact_entity_edges": _missing_fact_edge_count(db, kg_build_id, "HAS_FACT", incoming=True),
        "missing_fact_metric_edges": _missing_fact_edge_count(db, kg_build_id, "MEASURES"),
        "missing_fact_period_edges": _missing_fact_edge_count(db, kg_build_id, "IN_PERIOD"),
        "missing_fact_source_edges": _missing_fact_edge_count(db, kg_build_id, "FROM_SOURCE"),
        "missing_fact_raw_object_edges": _missing_fact_edge_count(db, kg_build_id, "TRACED_TO"),
        "missing_fact_source_definition_edges": _missing_fact_edge_count(db, kg_build_id, "USES_SOURCE_DEFINITION"),
        "derived_fact_without_inputs": _scalar(db, "SELECT COUNT(*) AS c FROM kg_nodes n WHERE n.kg_build_id = ? AND n.node_type = 'DerivedFact' AND NOT EXISTS (SELECT 1 FROM kg_edges e WHERE e.kg_build_id = n.kg_build_id AND e.src_node_id = n.node_id AND e.relation_type = 'DERIVED_FROM')", (kg_build_id,)),
        "ranking_share_missing_scope": _scalar(db, "SELECT COUNT(*) AS c FROM derived_facts WHERE COALESCE(is_active, 1) = 1 AND derived_type IN ('ranking', 'share', 'argmax', 'argmin') AND (scope_id IS NULL OR scope_definition IS NULL)"),
    }
    failures = []
    if checks["fact_node_count"] != checks["graph_ready_fact_count"]:
        failures.append(f"fact_node_count={checks['fact_node_count']} != graph_ready_fact_count={checks['graph_ready_fact_count']}")
    if checks["derived_fact_node_count"] != checks["active_derived_fact_count"]:
        failures.append(f"derived_fact_node_count={checks['derived_fact_node_count']} != active_derived_fact_count={checks['active_derived_fact_count']}")
    for key in ["candidate_fact_leak_count", "invalid_status_fact_count", "candidate_kg_eligible_count", "missing_fact_entity_edges", "missing_fact_metric_edges", "missing_fact_period_edges", "missing_fact_source_edges", "missing_fact_raw_object_edges", "missing_fact_source_definition_edges", "derived_fact_without_inputs", "ranking_share_missing_scope"]:
        if checks.get(key, 0):
            failures.append(f"{key}={checks[key]} > 0")
    report = {"kg_build_id": kg_build_id, **checks, "kg_quality_gate_failures": failures, "kg_quality_gate_status": "failed" if failures else "passed"}
    if write_checks:
        _write_quality_checks(db, kg_build_id, report)
    if output_dir:
        report["written_files"] = [str(path) for path in write_kg_quality_report(report, output_dir)]
    return report


def export_kg_jsonl(db: DBProtocol, output_dir: str, kg_build_id: str | None = None) -> list[Path]:
    ensure_kg_schema(db)
    kg_build_id = kg_build_id or _active_kg_build_id(db)
    if not kg_build_id:
        raise RuntimeError("No active KG build found. Run build-kg first.")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for table, path_name in [("kg_nodes", "kg_nodes.jsonl"), ("kg_edges", "kg_edges.jsonl")]:
        path = out / path_name
        with path.open("w", encoding="utf-8") as f:
            for row in _rows(db, f"SELECT * FROM {table} WHERE kg_build_id = ? AND COALESCE(is_active, 1) = 1", (kg_build_id,)):
                item = dict(row)
                if item.get("properties_json"):
                    item["properties"] = _json_value(item.pop("properties_json"))
                f.write(json.dumps(item, ensure_ascii=False, sort_keys=True, default=str) + "\n")
        files.append(path)
    build_report = {"kg_build_id": kg_build_id, "quality": kg_quality_report(db, kg_build_id)}
    build_path = out / "kg_build_report.json"
    build_path.write_text(json.dumps(build_report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    files.append(build_path)
    return files


def ensure_kg_schema(db: DBProtocol) -> None:
    for statement in KG_SCHEMA_SQL.split(";"):
        sql = statement.strip()
        if sql:
            db.execute(sql)


def write_kg_reports(report: dict[str, Any], output_dir: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "kg_build_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    quality_paths = write_kg_quality_report(report.get("quality", {}), output_dir)
    return [report_path, *quality_paths]


def write_kg_quality_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "kg_quality_report.json"
    md_path = out / "kg_quality_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    lines = ["# KG Quality Report", ""]
    for key, value in report.items():
        if key in {"kg_quality_gate_failures", "written_files"}:
            continue
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Failures", ""])
    failures = report.get("kg_quality_gate_failures") or []
    lines.extend([f"- {item}" for item in failures] or ["- none"])
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return [json_path, md_path]


class _BatchWriter:
    def __init__(self, db: DBProtocol, table: str, columns: list[str], batch_size: int):
        self.db = db
        self.table = table
        self.columns = columns
        self.batch_size = batch_size
        self.rows: list[dict[str, Any]] = []

    def add(self, row: dict[str, Any]) -> None:
        self.rows.append(row)
        if len(self.rows) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        if not self.rows:
            return
        _insert_many(self.db, self.table, self.columns, self.rows)
        self.rows.clear()


def _insert_many(db: DBProtocol, table: str, columns: list[str], rows: list[dict[str, Any]]) -> None:
    values = [[row.get(col) for col in columns] for row in rows]
    pk = columns[0]
    if db.__class__.__name__ == "PostgresMetadataDB":
        placeholders = ",".join(["%s"] * len(columns))
        updates = ", ".join([f"{col}=EXCLUDED.{col}" for col in columns if col != pk])
        sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders}) ON CONFLICT ({pk}) DO UPDATE SET {updates}"
        with db.conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.executemany(sql, values)
        db.conn.commit()  # type: ignore[attr-defined]
    else:
        placeholders = ",".join(["?"] * len(columns))
        db.conn.executemany(f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) VALUES ({placeholders})", values)  # type: ignore[attr-defined]
        db.conn.commit()  # type: ignore[attr-defined]


def _insert_kg_build(db: DBProtocol, row: dict[str, Any]) -> None:
    columns = ["kg_build_id", "input_fact_build_id", "input_qa_build_id", "status", "started_at", "completed_at", "node_count", "edge_count", "quality_status", "notes", "is_active", "superseded_by"]
    _insert_many(db, "kg_builds", columns, [row])


def _update_kg_build(db: DBProtocol, kg_build_id: str, fields: dict[str, Any]) -> None:
    assignments = ", ".join([f"{key} = ?" for key in fields])
    db.execute(f"UPDATE kg_builds SET {assignments} WHERE kg_build_id = ?", [*fields.values(), kg_build_id])


def _activate_kg_build(db: DBProtocol, kg_build_id: str) -> None:
    old_build_ids = [row.get("kg_build_id") for row in _rows(db, "SELECT kg_build_id FROM kg_builds WHERE COALESCE(is_active, 1) = 1 AND kg_build_id <> ?", (kg_build_id,))]
    db.execute("UPDATE kg_builds SET is_active = 0, superseded_by = ?, status = CASE WHEN status = 'running' THEN 'superseded' ELSE status END WHERE COALESCE(is_active, 1) = 1 AND kg_build_id <> ?", (kg_build_id, kg_build_id))
    for old_build_id in old_build_ids:
        db.execute("UPDATE kg_nodes SET is_active = 0, superseded_by = ? WHERE kg_build_id = ? AND COALESCE(is_active, 1) = 1", (kg_build_id, old_build_id))
        db.execute("UPDATE kg_edges SET is_active = 0, superseded_by = ? WHERE kg_build_id = ? AND COALESCE(is_active, 1) = 1", (kg_build_id, old_build_id))
    db.execute("UPDATE kg_builds SET is_active = 1, superseded_by = NULL WHERE kg_build_id = ?", (kg_build_id,))


def _write_quality_checks(db: DBProtocol, kg_build_id: str, report: dict[str, Any]) -> None:
    rows = []
    for key, value in report.items():
        if key.startswith("kg_") or key in {"written_files"}:
            continue
        status = "passed" if int(value or 0) == 0 or key in {"node_count", "edge_count", "fact_node_count", "graph_ready_fact_count", "derived_fact_node_count", "active_derived_fact_count"} else "failed"
        severity = "error" if status == "failed" else "info"
        rows.append({"check_id": _hash_id("kgcheck", kg_build_id, key), "kg_build_id": kg_build_id, "check_type": key, "status": status, "severity": severity, "message": f"{key}={value}"})
    _insert_many(db, "kg_quality_checks", CHECK_COLUMNS, rows)


def _add_raw_object_node(db: DBProtocol, add_node: Any, add_edge: Any, raw_object_id: Any) -> None:
    if not raw_object_id:
        return
    row = db.fetchone("SELECT * FROM raw_objects WHERE raw_object_id = ?", (raw_object_id,))
    if not row:
        return
    item = dict(row)
    add_node(_raw_object_node(raw_object_id), "RawObject", "raw_objects", raw_object_id, _pick(item, ["raw_object_id", "source_id", "object_type", "storage_uri", "original_url", "response_status", "content_sha256", "content_size_bytes", "retrieval_time", "source_publish_date", "source_update_time", "validation_status"]))
    if item.get("source_id"):
        add_edge(_raw_object_node(raw_object_id), "FROM_SOURCE", _source_node(item.get("source_id")), "raw_objects", raw_object_id)


def _missing_fact_edge_count(db: DBProtocol, kg_build_id: str, relation_type: str, incoming: bool = False) -> int:
    if incoming:
        sql = """
            SELECT COUNT(*) AS c FROM kg_nodes n
            WHERE n.kg_build_id = ? AND n.node_type = 'Fact' AND COALESCE(n.is_active, 1) = 1
              AND NOT EXISTS (SELECT 1 FROM kg_edges e WHERE e.kg_build_id = n.kg_build_id AND e.dst_node_id = n.node_id AND e.relation_type = ?)
        """
    else:
        sql = """
            SELECT COUNT(*) AS c FROM kg_nodes n
            WHERE n.kg_build_id = ? AND n.node_type = 'Fact' AND COALESCE(n.is_active, 1) = 1
              AND NOT EXISTS (SELECT 1 FROM kg_edges e WHERE e.kg_build_id = n.kg_build_id AND e.src_node_id = n.node_id AND e.relation_type = ?)
        """
    return _scalar(db, sql, (kg_build_id, relation_type))


def _active_build_id(db: DBProtocol, table: str) -> str | None:
    try:
        row = db.fetchone(f"SELECT build_id, COUNT(*) AS c FROM {table} WHERE COALESCE(is_active, 1) = 1 GROUP BY build_id ORDER BY c DESC LIMIT 1")
    except Exception:
        return None
    return row.get("build_id") if row and row.get("build_id") else None


def _active_kg_build_id(db: DBProtocol) -> str | None:
    try:
        row = db.fetchone("SELECT kg_build_id FROM kg_builds WHERE COALESCE(is_active, 1) = 1 ORDER BY completed_at DESC, started_at DESC LIMIT 1")
    except Exception:
        return None
    return row.get("kg_build_id") if row else None


def _rows(db: DBProtocol, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in db.fetchall(sql, params)]


def _scalar(db: DBProtocol, sql: str, params: Iterable[Any] = ()) -> int:
    try:
        row = db.fetchone(sql, params)
    except Exception:
        return 0
    return int(row.get("c") if row and row.get("c") is not None else 0)


def _pick(row: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: row.get(key) for key in keys if key in row and row.get(key) is not None}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str) or not value:
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _json_dict(value: Any) -> dict[str, Any]:
    parsed = _json_value(value)
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: Any) -> list[Any]:
    parsed = _json_value(value)
    return parsed if isinstance(parsed, list) else []


def _time_properties(row: dict[str, Any]) -> dict[str, Any]:
    return _pick(row, ["time_basis", "metric_period_type", "period_start", "period_end", "calendar_year", "fiscal_year", "fiscal_quarter", "as_of_date", "report_date"])


def _time_node(row: dict[str, Any]) -> str:
    parts = [row.get("time_basis"), row.get("metric_period_type"), row.get("period_start"), row.get("period_end"), row.get("calendar_year"), row.get("fiscal_year"), row.get("fiscal_quarter"), row.get("as_of_date"), row.get("report_date")]
    return "time:" + _digest(parts)


def _derived_time_node(derived_id: Any, time_scope: dict[str, Any]) -> str:
    return "time:derived:" + _digest([derived_id, time_scope])


def _metric_role(metric_scope: dict[str, Any], metric_id: str) -> str:
    for key in ["metric_id", "numerator", "denominator"]:
        if metric_scope.get(key) == metric_id:
            return key
    return "related"


def _entity_node(value: Any) -> str:
    return f"entity:{value}"


def _security_node(value: Any) -> str:
    return f"security:{value}"


def _metric_node(value: Any) -> str:
    return f"metric:{value}"


def _source_node(value: Any) -> str:
    return f"source:{value}"


def _source_definition_node(value: Any) -> str:
    return f"source_definition:{value}"


def _raw_object_node(value: Any) -> str:
    return f"raw_object:{value}"


def _document_node(value: Any) -> str:
    return f"document:{value}"


def _fact_node(value: Any) -> str:
    return f"fact:{value}"


def _derived_fact_node(value: Any) -> str:
    return f"derived_fact:{value}"


def _entity_set_node(value: Any) -> str:
    return f"entity_set:{value}"


def _stable_edge_id(src: str, relation: str, dst: str, source_table: str | None, source_pk: Any) -> str:
    return "edge:" + _digest([src, relation, dst, source_table, source_pk])


def _versioned_graph_id(stable_id: str, kg_build_id: str) -> str:
    return f"{stable_id}@@{kg_build_id}"


def _hash_id(prefix: str, *parts: Any) -> str:
    return prefix + "_" + _digest(parts)


def _digest(parts: Iterable[Any]) -> str:
    return hashlib.sha1(json.dumps(list(parts), ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:24]


def _new_kg_build_id() -> str:
    return "kg_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + _digest([datetime.now(timezone.utc).isoformat()])[:8]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
