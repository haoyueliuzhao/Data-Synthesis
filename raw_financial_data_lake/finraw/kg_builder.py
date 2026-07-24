from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from finraw.db.client import DBProtocol
from finraw.fact_universe import active_fact_universe_build_id

KG_SCHEMA_VERSION = "3.1"

KG_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS kg_builds (
    kg_build_id          TEXT PRIMARY KEY,
    graph_schema_version TEXT,
    input_fact_build_id  TEXT,
    input_fact_universe_build_id TEXT,
    input_qa_build_id    TEXT,
    input_entity_build_id TEXT,
    input_metric_build_id TEXT,
    input_source_definition_build_id TEXT,
    input_document_build_id TEXT,
    input_fact_count     INTEGER,
    input_derived_count  INTEGER,
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

NODE_COLUMNS = [
    "node_id",
    "stable_node_id",
    "kg_build_id",
    "node_type",
    "source_table",
    "source_pk",
    "properties_json",
    "is_active",
    "superseded_by",
]
EDGE_COLUMNS = [
    "edge_id",
    "stable_edge_id",
    "kg_build_id",
    "src_node_id",
    "dst_node_id",
    "relation_type",
    "source_table",
    "source_pk",
    "properties_json",
    "is_active",
    "superseded_by",
]
CHECK_COLUMNS = [
    "check_id",
    "kg_build_id",
    "check_type",
    "status",
    "severity",
    "message",
]


def build_kg(
    db: DBProtocol,
    config: dict[str, Any],
    output_dir: str | None = None,
    batch_size: int = 20000,
    *,
    activate: bool = True,
) -> dict[str, Any]:
    ensure_kg_schema(db)
    input_fact_build_id = _required_active_build_id(db, "standardized_facts")
    input_qa_build_id = _required_active_build_id(db, "derived_facts")
    input_entity_build_id = _required_active_build_id(db, "canonical_entities")
    input_metric_build_id = _required_active_build_id(db, "metrics")
    input_source_definition_build_id = _required_active_build_id(
        db, "source_metric_definitions"
    )
    input_document_build_id = _optional_active_build_id(db, "source_documents")
    _validate_derived_build_chain(db, input_qa_build_id, input_fact_build_id)
    use_fact_universe = bool(
        config.get("kg", {}).get("use_active_fact_universe", False)
    )
    input_fact_universe_build_id = None
    if use_fact_universe:
        input_fact_universe_build_id = active_fact_universe_build_id(
            db,
            input_fact_build_id=input_fact_build_id,
        )
        if not input_fact_universe_build_id:
            raise RuntimeError(
                "kg.use_active_fact_universe is true, but no passing active fact "
                f"universe consumes fact build {input_fact_build_id}"
            )
    selected_fact_ids = _selected_fact_ids(
        db,
        input_fact_universe_build_id,
    )
    selected_derived_ids = _selected_derived_ids(
        db,
        input_fact_universe_build_id,
    )
    derived_rows = _eligible_derived_rows(
        db,
        input_qa_build_id,
        input_fact_build_id,
        selected_fact_ids=selected_fact_ids,
        selected_derived_ids=selected_derived_ids,
    )
    input_fact_count = _expected_fact_count(
        db,
        input_fact_build_id,
        input_fact_universe_build_id,
    )
    input_derived_count = len(derived_rows)
    kg_build_id = _new_kg_build_id()
    started_at = _now()
    _insert_kg_build(
        db,
        {
            "kg_build_id": kg_build_id,
            "graph_schema_version": KG_SCHEMA_VERSION,
            "input_fact_build_id": input_fact_build_id,
            "input_fact_universe_build_id": input_fact_universe_build_id,
            "input_qa_build_id": input_qa_build_id,
            "input_entity_build_id": input_entity_build_id,
            "input_metric_build_id": input_metric_build_id,
            "input_source_definition_build_id": input_source_definition_build_id,
            "input_document_build_id": input_document_build_id,
            "input_fact_count": input_fact_count,
            "input_derived_count": input_derived_count,
            "status": "running",
            "started_at": started_at,
            "completed_at": None,
            "node_count": 0,
            "edge_count": 0,
            "quality_status": None,
            "notes": json.dumps(
                {
                    "source": "build-kg",
                    "graph_schema_version": KG_SCHEMA_VERSION,
                    "policy": (
                        "build_pinned_fact_and_derived_universe"
                        if input_fact_universe_build_id
                        else "build_pinned_graph_ready_facts_and_validated_derived_facts_only"
                    ),
                    "input_fact_universe_build_id": input_fact_universe_build_id,
                },
                sort_keys=True,
            ),
            "is_active": 0,
            "superseded_by": None,
        },
    )

    node_writer = _BatchWriter(db, "kg_nodes", NODE_COLUMNS, batch_size)
    edge_writer = _BatchWriter(db, "kg_edges", EDGE_COLUMNS, batch_size)
    seen_nodes: set[str] = set()
    seen_edges: set[str] = set()
    node_type_counts: Counter[str] = Counter()
    edge_type_counts: Counter[str] = Counter()

    def add_node(
        stable_node_id: str,
        node_type: str,
        source_table: str | None,
        source_pk: Any,
        properties: dict[str, Any],
    ) -> str:
        node_id = _versioned_graph_id(stable_node_id, kg_build_id)
        if node_id in seen_nodes:
            return node_id
        seen_nodes.add(node_id)
        node_type_counts[node_type] += 1
        node_writer.add(
            {
                "node_id": node_id,
                "stable_node_id": stable_node_id,
                "kg_build_id": kg_build_id,
                "node_type": node_type,
                "source_table": source_table,
                "source_pk": str(source_pk) if source_pk is not None else None,
                "properties_json": _json(properties),
                "is_active": 1,
                "superseded_by": None,
            }
        )
        return node_id

    def add_edge(
        src_stable: str,
        relation_type: str,
        dst_stable: str,
        source_table: str | None,
        source_pk: Any,
        properties: dict[str, Any] | None = None,
    ) -> str:
        stable_edge_id = _stable_edge_id(
            src_stable, relation_type, dst_stable, source_table, source_pk
        )
        edge_id = _versioned_graph_id(stable_edge_id, kg_build_id)
        if edge_id in seen_edges:
            return edge_id
        seen_edges.add(edge_id)
        edge_type_counts[relation_type] += 1
        edge_writer.add(
            {
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
            }
        )
        return edge_id

    # Master data nodes.
    for row in _rows(
        db,
        "SELECT * FROM canonical_entities WHERE build_id = ?",
        (input_entity_build_id,),
    ):
        add_node(
            _entity_node(row.get("entity_id")),
            "Entity",
            "canonical_entities",
            row.get("entity_id"),
            _pick(
                row,
                [
                    "entity_id",
                    "canonical_name",
                    "entity_type",
                    "market",
                    "country",
                    "exchange",
                    "ticker",
                    "cik",
                    "isin",
                    "currency",
                    "fiscal_year_end",
                    "industry",
                    "build_id",
                ],
            ),
        )
    for row in _rows(
        db,
        "SELECT * FROM canonical_securities WHERE build_id = ?",
        (input_entity_build_id,),
    ):
        security = _security_node(row.get("security_id"))
        add_node(
            security,
            "Security",
            "canonical_securities",
            row.get("security_id"),
            _pick(
                row,
                [
                    "security_id",
                    "company_entity_id",
                    "canonical_name",
                    "security_type",
                    "market",
                    "country",
                    "exchange",
                    "ticker",
                    "composite_ticker",
                    "currency",
                    "is_primary_listing",
                    "listing_status",
                    "build_id",
                ],
            ),
        )
        if row.get("company_entity_id"):
            add_edge(
                _entity_node(row.get("company_entity_id")),
                "HAS_SECURITY",
                security,
                "canonical_securities",
                row.get("security_id"),
            )
    for row in _rows(
        db, "SELECT * FROM metrics WHERE build_id = ?", (input_metric_build_id,)
    ):
        add_node(
            _metric_node(row.get("metric_id")),
            "Metric",
            "metrics",
            row.get("metric_id"),
            _pick(
                row,
                [
                    "metric_id",
                    "canonical_name",
                    "metric_category",
                    "statement_type",
                    "period_type",
                    "default_unit",
                    "default_currency",
                    "accounting_standard",
                    "aggregation_rule",
                    "revision_risk",
                    "ambiguity_notes",
                    "build_id",
                ],
            ),
        )
    for row in _rows(
        db, "SELECT * FROM source_registry WHERE is_active IS DISTINCT FROM FALSE"
    ):
        add_node(
            _source_node(row.get("source_id")),
            "DataSource",
            "source_registry",
            row.get("source_id"),
            _pick(
                row,
                [
                    "source_id",
                    "source_name",
                    "source_type",
                    "authority_level",
                    "market",
                    "provider",
                    "base_url",
                    "access_method",
                    "update_frequency",
                    "license_note",
                    "rate_limit_note",
                ],
            ),
        )
    for row in _rows(
        db,
        "SELECT * FROM source_metric_definitions WHERE build_id = ?",
        (input_source_definition_build_id,),
    ):
        source_def = _source_definition_node(row.get("definition_id"))
        add_node(
            source_def,
            "SourceDefinition",
            "source_metric_definitions",
            row.get("definition_id"),
            _pick(
                row,
                [
                    "definition_id",
                    "source_id",
                    "metric_id",
                    "raw_concept_name",
                    "definition_text",
                    "unit_rule",
                    "frequency",
                    "vintage_policy",
                    "is_forecast",
                    "comparable_to_metric_id",
                    "comparability_level",
                    "build_id",
                ],
            ),
        )
        if row.get("metric_id"):
            add_edge(
                source_def,
                "DEFINES",
                _metric_node(row.get("metric_id")),
                "source_metric_definitions",
                row.get("definition_id"),
            )
        if row.get("source_id"):
            add_edge(
                source_def,
                "PROVIDED_BY",
                _source_node(row.get("source_id")),
                "source_metric_definitions",
                row.get("definition_id"),
            )

    # Facts and their source raw objects.
    fact_sql, fact_params = _kg_fact_query(
        input_fact_build_id,
        input_fact_universe_build_id,
    )
    for row in _rows(db, fact_sql, fact_params):
        fact = _fact_node(row.get("fact_id"))
        add_node(
            fact,
            "Fact",
            "standardized_facts",
            row.get("fact_id"),
            _pick(
                row,
                [
                    "fact_id",
                    "stable_fact_id",
                    "build_id",
                    "entity_id",
                    "entity_scope_id",
                    "financial_scope_type",
                    "metric_id",
                    "normalized_value",
                    "normalized_unit",
                    "normalized_currency",
                    "value_scale",
                    "period_start",
                    "period_end",
                    "calendar_year",
                    "fiscal_year",
                    "fiscal_quarter",
                    "time_basis",
                    "metric_period_type",
                    "source_definition_id",
                    "frequency",
                    "seasonal_adjustment",
                    "vintage_policy",
                    "is_forecast",
                    "comparability_level",
                    "source_id",
                    "raw_object_id",
                    "verification_status",
                    "graph_ready_reason",
                    "validation_flags",
                    "raw_equivalence_group_id",
                    "semantic_equivalence_group_id",
                    "confidence_score",
                ],
            ),
        )
        time = _time_node(row)
        add_node(
            time,
            "TimePeriod",
            "standardized_facts",
            row.get("fact_id"),
            _time_properties(row),
        )
        _add_time_hierarchy(add_node, add_edge, time, row, row.get("entity_id"))
        if row.get("entity_id"):
            add_edge(
                _entity_node(row.get("entity_id")),
                "HAS_FACT",
                fact,
                "standardized_facts",
                row.get("fact_id"),
            )
        if row.get("metric_id"):
            add_edge(
                fact,
                "MEASURES",
                _metric_node(row.get("metric_id")),
                "standardized_facts",
                row.get("fact_id"),
            )
        add_edge(fact, "IN_PERIOD", time, "standardized_facts", row.get("fact_id"))
        if row.get("source_id"):
            add_edge(
                fact,
                "FROM_SOURCE",
                _source_node(row.get("source_id")),
                "standardized_facts",
                row.get("fact_id"),
            )
        if row.get("raw_object_id"):
            raw = _raw_object_node(row.get("raw_object_id"))
            if _versioned_graph_id(raw, kg_build_id) not in seen_nodes:
                _add_raw_object_node(db, add_node, add_edge, row.get("raw_object_id"))
            add_edge(fact, "TRACED_TO", raw, "standardized_facts", row.get("fact_id"))
        if row.get("source_definition_id"):
            add_edge(
                fact,
                "USES_SOURCE_DEFINITION",
                _source_definition_node(row.get("source_definition_id")),
                "standardized_facts",
                row.get("fact_id"),
            )

    # Source documents.
    for row in _rows(
        db,
        "SELECT * FROM source_documents WHERE build_id = ? AND document_status = 'passed'",
        (input_document_build_id,),
    ):
        doc = _document_node(row.get("document_id"))
        add_node(
            doc,
            "SourceDocument",
            "source_documents",
            row.get("document_id"),
            _pick(
                row,
                [
                    "document_id",
                    "stable_document_id",
                    "build_id",
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
                ],
            ),
        )
        if row.get("entity_id"):
            add_edge(
                _entity_node(row.get("entity_id")),
                "FILED",
                doc,
                "source_documents",
                row.get("document_id"),
            )
        if row.get("source_id"):
            add_edge(
                doc,
                "FROM_SOURCE",
                _source_node(row.get("source_id")),
                "source_documents",
                row.get("document_id"),
            )
        if row.get("raw_object_id"):
            raw = _raw_object_node(row.get("raw_object_id"))
            if _versioned_graph_id(raw, kg_build_id) not in seen_nodes:
                _add_raw_object_node(db, add_node, add_edge, row.get("raw_object_id"))
            add_edge(
                doc, "HAS_RAW_OBJECT", raw, "source_documents", row.get("document_id")
            )

    # Derived facts and scopes.
    for row in derived_rows:
        derived = _derived_fact_node(row.get("derived_id"))
        add_node(
            derived,
            "DerivedFact",
            "derived_facts",
            row.get("derived_id"),
            _pick(
                row,
                [
                    "derived_id",
                    "stable_derived_id",
                    "build_id",
                    "input_build_id",
                    "derived_type",
                    "entity_scope",
                    "metric_scope",
                    "time_scope",
                    "scope_type",
                    "scope_id",
                    "scope_definition",
                    "scope_entity_ids",
                    "scope_source",
                    "calculation_code",
                    "output_value",
                    "output_table",
                    "unit",
                    "tolerance",
                    "verification_status",
                ],
            ),
        )
        for fact_id in _json_list(row.get("input_fact_ids")):
            add_edge(
                derived,
                "DERIVED_FROM",
                _fact_node(fact_id),
                "derived_facts",
                row.get("derived_id"),
            )
        entity_scope = _json_dict(row.get("entity_scope"))
        metric_scope = _json_dict(row.get("metric_scope"))
        time_scope = _json_dict(row.get("time_scope"))
        if entity_scope.get("entity_id"):
            add_edge(
                derived,
                "ABOUT_ENTITY",
                _entity_node(entity_scope.get("entity_id")),
                "derived_facts",
                row.get("derived_id"),
            )
        metric_ids = {
            metric_scope.get("metric_id"),
            metric_scope.get("numerator"),
            metric_scope.get("denominator"),
        }
        for metric_id in sorted(m for m in metric_ids if m):
            add_edge(
                derived,
                "USES_METRIC",
                _metric_node(metric_id),
                "derived_facts",
                row.get("derived_id"),
                {"metric_role": _metric_role(metric_scope, metric_id)},
            )
        if time_scope:
            time = _derived_time_node(time_scope)
            time_scope_id = _digest([time_scope])
            add_node(
                time,
                "TimePeriod",
                "derived_time_scope",
                time_scope_id,
                {"time_scope": time_scope},
            )
            _add_time_hierarchy(
                add_node,
                add_edge,
                time,
                time_scope,
                entity_scope.get("entity_id"),
            )
            add_edge(derived, "IN_PERIOD", time, "derived_facts", row.get("derived_id"))
        if row.get("scope_id"):
            entity_set = _entity_set_node(row.get("scope_id"))
            add_node(
                entity_set,
                "EntitySet",
                "derived_facts",
                row.get("scope_id"),
                {
                    "scope_id": row.get("scope_id"),
                    "scope_type": row.get("scope_type"),
                    "scope_definition": row.get("scope_definition"),
                    "scope_source": row.get("scope_source"),
                },
            )
            add_edge(
                derived, "HAS_SCOPE", entity_set, "derived_facts", row.get("derived_id")
            )
            for entity_id in _json_list(row.get("scope_entity_ids")):
                add_edge(
                    entity_set,
                    "CONTAINS_ENTITY",
                    _entity_node(entity_id),
                    "derived_facts",
                    row.get("scope_id"),
                )

    node_writer.flush()
    edge_writer.flush()
    quality = kg_quality_report(db, kg_build_id, write_checks=True)
    node_count = _scalar(
        db,
        "SELECT COUNT(*) AS c FROM kg_nodes WHERE kg_build_id = ? AND COALESCE(is_active, 1) = 1",
        (kg_build_id,),
    )
    edge_count = _scalar(
        db,
        "SELECT COUNT(*) AS c FROM kg_edges WHERE kg_build_id = ? AND COALESCE(is_active, 1) = 1",
        (kg_build_id,),
    )
    quality_status = "passed" if not quality["kg_quality_gate_failures"] else "failed"
    completed_at = _now()
    _update_kg_build(
        db,
        kg_build_id,
        {
            "status": "success" if quality_status == "passed" else "quality_failed",
            "completed_at": completed_at,
            "node_count": node_count,
            "edge_count": edge_count,
            "quality_status": quality_status,
            "notes": _json(
                {
                    "node_type_counts": dict(sorted(node_type_counts.items())),
                    "edge_type_counts": dict(sorted(edge_type_counts.items())),
                    "quality": quality_status,
                }
            ),
        },
    )
    _apply_kg_activation_policy(
        db,
        kg_build_id,
        quality_status=quality_status,
        activate=activate,
    )
    report = {
        "kg_build_id": kg_build_id,
        "graph_schema_version": KG_SCHEMA_VERSION,
        "input_fact_build_id": input_fact_build_id,
        "input_fact_universe_build_id": input_fact_universe_build_id,
        "input_qa_build_id": input_qa_build_id,
        "input_entity_build_id": input_entity_build_id,
        "input_metric_build_id": input_metric_build_id,
        "input_source_definition_build_id": input_source_definition_build_id,
        "input_document_build_id": input_document_build_id,
        "input_fact_count": input_fact_count,
        "input_derived_count": input_derived_count,
        "node_count": node_count,
        "edge_count": edge_count,
        "node_type_counts": dict(sorted(node_type_counts.items())),
        "edge_type_counts": dict(sorted(edge_type_counts.items())),
        "activation_requested": activate,
        "is_active": quality_status == "passed" and activate,
        "quality": quality,
    }
    if output_dir:
        report["written_files"] = [
            str(path) for path in write_kg_reports(report, output_dir)
        ]
    return report


def kg_quality_report(
    db: DBProtocol,
    kg_build_id: str | None = None,
    output_dir: str | None = None,
    write_checks: bool = False,
) -> dict[str, Any]:
    ensure_kg_schema(db)
    kg_build_id = kg_build_id or _active_kg_build_id(db)
    if not kg_build_id:
        report = {
            "kg_build_id": None,
            "kg_quality_gate_status": "failed",
            "kg_quality_gate_failures": ["no_active_kg_build"],
        }
        if output_dir:
            report["written_files"] = [
                str(path) for path in write_kg_quality_report(report, output_dir)
            ]
        return report

    build_row = db.fetchone(
        "SELECT * FROM kg_builds WHERE kg_build_id = ?", (kg_build_id,)
    )
    if not build_row:
        report = {
            "kg_build_id": kg_build_id,
            "kg_quality_gate_status": "failed",
            "kg_quality_gate_failures": ["unknown_kg_build"],
        }
        if output_dir:
            report["written_files"] = [
                str(path) for path in write_kg_quality_report(report, output_dir)
            ]
        return report
    build = dict(build_row)
    fact_build_id = build.get("input_fact_build_id")
    fact_universe_build_id = build.get("input_fact_universe_build_id")
    qa_build_id = build.get("input_qa_build_id")
    entity_build_id = build.get("input_entity_build_id")
    metric_build_id = build.get("input_metric_build_id")
    definition_build_id = build.get("input_source_definition_build_id")
    document_build_id = build.get("input_document_build_id")

    checks = {
        "node_count": _scalar(
            db,
            "SELECT COUNT(*) AS c FROM kg_nodes WHERE kg_build_id = ?",
            (kg_build_id,),
        ),
        "edge_count": _scalar(
            db,
            "SELECT COUNT(*) AS c FROM kg_edges WHERE kg_build_id = ?",
            (kg_build_id,),
        ),
        "schema_version_mismatch_count": 0
        if build.get("graph_schema_version") == KG_SCHEMA_VERSION
        else 1,
        "recorded_input_fact_count": int(build.get("input_fact_count") or 0),
        "recorded_input_derived_count": int(build.get("input_derived_count") or 0),
        "fact_node_count": _node_type_count(db, kg_build_id, "Fact"),
        "graph_ready_fact_count": _expected_fact_count(
            db,
            fact_build_id,
            fact_universe_build_id,
        ),
        "derived_fact_node_count": _node_type_count(db, kg_build_id, "DerivedFact"),
        "expected_derived_fact_count": _expected_derived_count(
            db,
            qa_build_id,
            fact_build_id,
            fact_universe_build_id,
        ),
        "entity_node_count": _node_type_count(db, kg_build_id, "Entity"),
        "expected_entity_node_count": _build_row_count(
            db, "canonical_entities", entity_build_id
        ),
        "metric_node_count": _node_type_count(db, kg_build_id, "Metric"),
        "expected_metric_node_count": _build_row_count(db, "metrics", metric_build_id),
        "source_definition_node_count": _node_type_count(
            db, kg_build_id, "SourceDefinition"
        ),
        "expected_source_definition_node_count": _build_row_count(
            db, "source_metric_definitions", definition_build_id
        ),
        "source_document_node_count": _node_type_count(
            db, kg_build_id, "SourceDocument"
        ),
        "expected_source_document_node_count": _build_row_count(
            db, "source_documents", document_build_id, "document_status = 'passed'"
        ),
        "candidate_fact_leak_count": _scalar(
            db,
            "SELECT COUNT(*) AS c FROM kg_nodes WHERE kg_build_id = ? AND (node_type = 'CandidateFact' OR source_table = 'candidate_facts')",
            (kg_build_id,),
        ),
        "invalid_status_fact_count": _scalar(
            db,
            """
            SELECT COUNT(*) AS c
            FROM kg_nodes n
            LEFT JOIN standardized_facts sf ON n.source_pk = sf.fact_id AND sf.build_id = ?
            WHERE n.kg_build_id = ? AND n.node_type = 'Fact'
              AND (sf.fact_id IS NULL OR COALESCE(sf.graph_ready, 0) <> 1
                   OR sf.verification_status NOT IN ('single_source', 'cross_verified'))
        """,
            (fact_build_id, kg_build_id),
        ),
        "fact_universe_build_mismatch_count": _fact_universe_build_mismatch_count(
            db,
            fact_universe_build_id,
            fact_build_id,
        ),
        "fact_outside_universe_count": _fact_outside_universe_count(
            db,
            kg_build_id,
            fact_universe_build_id,
        ),
        "derived_fact_outside_universe_count": (
            _derived_fact_outside_universe_count(
                db,
                kg_build_id,
                fact_universe_build_id,
            )
        ),
        "invalid_status_derived_fact_count": _scalar(
            db,
            """
            SELECT COUNT(*) AS c
            FROM kg_nodes n
            LEFT JOIN derived_facts d ON n.source_pk = d.derived_id
              AND d.build_id = ? AND d.input_build_id = ?
            WHERE n.kg_build_id = ? AND n.node_type = 'DerivedFact'
              AND (d.derived_id IS NULL OR d.verification_status NOT IN ('single_source', 'cross_verified'))
        """,
            (qa_build_id, fact_build_id, kg_build_id),
        ),
        "fact_build_mismatch_count": _source_build_mismatch_count(
            db, kg_build_id, "Fact", "standardized_facts", "fact_id", fact_build_id
        ),
        "derived_build_mismatch_count": _source_build_mismatch_count(
            db, kg_build_id, "DerivedFact", "derived_facts", "derived_id", qa_build_id
        ),
        "derived_input_build_mismatch_count": _scalar(
            db,
            "SELECT COUNT(*) AS c FROM derived_facts WHERE build_id = ? AND input_build_id <> ?",
            (qa_build_id, fact_build_id),
        ),
        "missing_fact_entity_edges": _missing_fact_edge_count(
            db, kg_build_id, "HAS_FACT", incoming=True
        ),
        "missing_fact_metric_edges": _missing_fact_edge_count(
            db, kg_build_id, "MEASURES"
        ),
        "missing_fact_period_edges": _missing_fact_edge_count(
            db, kg_build_id, "IN_PERIOD"
        ),
        "missing_fact_source_edges": _missing_fact_edge_count(
            db, kg_build_id, "FROM_SOURCE"
        ),
        "missing_fact_raw_object_edges": _missing_fact_edge_count(
            db, kg_build_id, "TRACED_TO"
        ),
        "missing_fact_source_definition_edges": _missing_fact_edge_count(
            db, kg_build_id, "USES_SOURCE_DEFINITION"
        ),
        "source_definition_missing_source_edges": _missing_node_edge_count(
            db, kg_build_id, "SourceDefinition", "PROVIDED_BY"
        ),
        "derived_fact_without_inputs": _missing_node_edge_count(
            db, kg_build_id, "DerivedFact", "DERIVED_FROM"
        ),
        "derived_input_edge_count": _edge_type_count(db, kg_build_id, "DERIVED_FROM"),
        "expected_derived_input_edge_count": _expected_derived_input_count(
            db,
            qa_build_id,
            fact_build_id,
            fact_universe_build_id,
        ),
        "derived_input_missing_fact_nodes": _missing_edge_target_count(
            db, kg_build_id, "DERIVED_FROM", "Fact"
        ),
        "dangling_source_edge_count": _dangling_edge_count(
            db, kg_build_id, incoming=False
        ),
        "dangling_target_edge_count": _dangling_edge_count(
            db, kg_build_id, incoming=True
        ),
        "invalid_relation_endpoint_count": _invalid_relation_endpoint_count(
            db, kg_build_id
        ),
        "duplicate_stable_node_count": _duplicate_stable_id_count(
            db, "kg_nodes", "stable_node_id", kg_build_id
        ),
        "duplicate_stable_edge_count": _duplicate_stable_id_count(
            db, "kg_edges", "stable_edge_id", kg_build_id
        ),
        "invalid_raw_object_status_count": _scalar(
            db,
            """
            SELECT COUNT(*) AS c FROM kg_nodes n
            LEFT JOIN raw_objects ro ON ro.raw_object_id = n.source_pk
            WHERE n.kg_build_id = ? AND n.node_type = 'RawObject'
              AND (ro.raw_object_id IS NULL OR ro.validation_status <> 'passed')
        """,
            (kg_build_id,),
        ),
        "invalid_source_document_status_count": _scalar(
            db,
            """
            SELECT COUNT(*) AS c FROM kg_nodes n
            LEFT JOIN source_documents d ON d.document_id = n.source_pk AND d.build_id = ?
            WHERE n.kg_build_id = ? AND n.node_type = 'SourceDocument'
              AND (d.document_id IS NULL OR d.document_status <> 'passed')
        """,
            (document_build_id, kg_build_id),
        ),
        "derived_time_node_count": _scalar(
            db,
            "SELECT COUNT(*) AS c FROM kg_nodes WHERE kg_build_id = ? AND node_type = 'TimePeriod' AND source_table = 'derived_time_scope'",
            (kg_build_id,),
        ),
        "time_hierarchy_edge_count": _scalar(
            db,
            "SELECT COUNT(*) AS c FROM kg_edges WHERE kg_build_id = ? AND relation_type IN ('BELONGS_TO_YEAR', 'BELONGS_TO_MONTH', 'BELONGS_TO_QUARTER', 'IN_FISCAL_YEAR', 'IN_FISCAL_YEAR_LABEL', 'FISCAL_YEAR_OF')",
            (kg_build_id,),
        ),
        "time_period_missing_hierarchy_count": _scalar(
            db,
            """
            SELECT COUNT(*) AS c
            FROM (
                SELECT node_id
                FROM kg_nodes
                WHERE kg_build_id = ? AND node_type = 'TimePeriod'
                EXCEPT
                SELECT src_node_id
                FROM kg_edges
                WHERE kg_build_id = ?
                  AND relation_type IN (
                      'BELONGS_TO_YEAR',
                      'IN_FISCAL_YEAR',
                      'IN_FISCAL_YEAR_LABEL'
                  )
            ) missing
        """,
            (kg_build_id, kg_build_id),
        ),
        "expected_derived_time_node_count": _expected_derived_time_count(
            db,
            qa_build_id,
            fact_build_id,
            fact_universe_build_id,
        ),
        "ranking_share_missing_scope": _scalar(
            db,
            "SELECT COUNT(*) AS c FROM derived_facts WHERE build_id = ? AND input_build_id = ? AND derived_type IN ('ranking', 'share', 'argmax', 'argmin', 'industry_ranking', 'industry_argmax', 'industry_argmin', 'multi_condition_screening') AND (scope_id IS NULL OR scope_definition IS NULL)",
            (qa_build_id, fact_build_id),
        ),
    }

    failures: list[str] = []
    failed_checks: set[str] = set()

    def require_zero(key: str) -> None:
        if checks.get(key, 0):
            failed_checks.add(key)
            failures.append(f"{key}={checks[key]} > 0")

    def require_equal(actual: str, expected: str) -> None:
        if checks.get(actual) != checks.get(expected):
            failed_checks.update({actual, expected})
            failures.append(
                f"{actual}={checks.get(actual)} != {expected}={checks.get(expected)}"
            )

    if checks["node_count"] <= 0:
        failed_checks.add("node_count")
        failures.append("node_count must be > 0")
    if checks["edge_count"] <= 0:
        failed_checks.add("edge_count")
        failures.append("edge_count must be > 0")
    if checks["fact_node_count"] <= 0:
        failed_checks.add("fact_node_count")
        failures.append("fact_node_count must be > 0")

    for actual, expected in [
        ("fact_node_count", "graph_ready_fact_count"),
        ("recorded_input_fact_count", "graph_ready_fact_count"),
        ("derived_fact_node_count", "expected_derived_fact_count"),
        ("recorded_input_derived_count", "expected_derived_fact_count"),
        ("derived_input_edge_count", "expected_derived_input_edge_count"),
        ("derived_time_node_count", "expected_derived_time_node_count"),
    ]:
        require_equal(actual, expected)
    for actual, expected, build_id in [
        ("entity_node_count", "expected_entity_node_count", entity_build_id),
        ("metric_node_count", "expected_metric_node_count", metric_build_id),
        (
            "source_definition_node_count",
            "expected_source_definition_node_count",
            definition_build_id,
        ),
        (
            "source_document_node_count",
            "expected_source_document_node_count",
            document_build_id,
        ),
    ]:
        if build_id:
            require_equal(actual, expected)

    for key in [
        "schema_version_mismatch_count",
        "candidate_fact_leak_count",
        "invalid_status_fact_count",
        "fact_universe_build_mismatch_count",
        "fact_outside_universe_count",
        "derived_fact_outside_universe_count",
        "invalid_status_derived_fact_count",
        "fact_build_mismatch_count",
        "derived_build_mismatch_count",
        "derived_input_build_mismatch_count",
        "missing_fact_entity_edges",
        "missing_fact_metric_edges",
        "missing_fact_period_edges",
        "missing_fact_source_edges",
        "missing_fact_raw_object_edges",
        "missing_fact_source_definition_edges",
        "source_definition_missing_source_edges",
        "derived_fact_without_inputs",
        "derived_input_missing_fact_nodes",
        "dangling_source_edge_count",
        "dangling_target_edge_count",
        "invalid_relation_endpoint_count",
        "duplicate_stable_node_count",
        "duplicate_stable_edge_count",
        "invalid_raw_object_status_count",
        "invalid_source_document_status_count",
        "time_period_missing_hierarchy_count",
        "ranking_share_missing_scope",
    ]:
        require_zero(key)

    check_statuses = {
        key: ("failed" if key in failed_checks else "passed") for key in checks
    }
    report = {
        "kg_build_id": kg_build_id,
        "graph_schema_version": build.get("graph_schema_version") or "1.0",
        "input_fact_build_id": fact_build_id,
        "input_fact_universe_build_id": fact_universe_build_id,
        "input_qa_build_id": qa_build_id,
        **checks,
        "check_statuses": check_statuses,
        "kg_quality_gate_failures": failures,
        "kg_quality_gate_status": "failed" if failures else "passed",
    }
    if write_checks:
        _write_quality_checks(db, kg_build_id, report)
    if output_dir:
        report["written_files"] = [
            str(path) for path in write_kg_quality_report(report, output_dir)
        ]
    return report


def export_kg_jsonl(
    db: DBProtocol, output_dir: str, kg_build_id: str | None = None
) -> list[Path]:
    ensure_kg_schema(db)
    kg_build_id = kg_build_id or _active_kg_build_id(db)
    if not kg_build_id:
        raise RuntimeError("No active KG build found. Run build-kg first.")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for table, path_name in [
        ("kg_nodes", "kg_nodes.jsonl"),
        ("kg_edges", "kg_edges.jsonl"),
    ]:
        path = out / path_name
        with path.open("w", encoding="utf-8") as f:
            for row in _rows(
                db, f"SELECT * FROM {table} WHERE kg_build_id = ?", (kg_build_id,)
            ):
                item = dict(row)
                if item.get("properties_json"):
                    item["properties"] = _json_value(item.pop("properties_json"))
                f.write(
                    json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
                    + "\n"
                )
        files.append(path)
    build_report = {
        "kg_build_id": kg_build_id,
        "quality": kg_quality_report(db, kg_build_id),
    }
    build_path = out / "kg_build_report.json"
    build_path.write_text(
        json.dumps(
            build_report, ensure_ascii=False, indent=2, sort_keys=True, default=str
        )
        + "\n",
        encoding="utf-8",
    )
    files.append(build_path)
    return files


def ensure_kg_schema(db: DBProtocol) -> None:
    for statement in KG_SCHEMA_SQL.split(";"):
        sql = statement.strip()
        if sql:
            db.execute(sql)
    migrations = {
        "graph_schema_version": "TEXT",
        "input_fact_universe_build_id": "TEXT",
        "input_entity_build_id": "TEXT",
        "input_metric_build_id": "TEXT",
        "input_source_definition_build_id": "TEXT",
        "input_document_build_id": "TEXT",
        "input_fact_count": "INTEGER",
        "input_derived_count": "INTEGER",
    }
    for column, column_type in migrations.items():
        try:
            db.execute(f"ALTER TABLE kg_builds ADD COLUMN {column} {column_type}")
        except Exception:
            pass


def write_kg_reports(report: dict[str, Any], output_dir: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "kg_build_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    quality_paths = write_kg_quality_report(report.get("quality", {}), output_dir)
    return [report_path, *quality_paths]


def write_kg_quality_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "kg_quality_report.json"
    md_path = out / "kg_quality_report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
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


def _insert_many(
    db: DBProtocol, table: str, columns: list[str], rows: list[dict[str, Any]]
) -> None:
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
        db.conn.executemany(
            f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) VALUES ({placeholders})",
            values,
        )  # type: ignore[attr-defined]
        db.conn.commit()  # type: ignore[attr-defined]


def _insert_kg_build(db: DBProtocol, row: dict[str, Any]) -> None:
    columns = [
        "kg_build_id",
        "graph_schema_version",
        "input_fact_build_id",
        "input_qa_build_id",
        "input_fact_universe_build_id",
        "input_entity_build_id",
        "input_metric_build_id",
        "input_source_definition_build_id",
        "input_document_build_id",
        "input_fact_count",
        "input_derived_count",
        "status",
        "started_at",
        "completed_at",
        "node_count",
        "edge_count",
        "quality_status",
        "notes",
        "is_active",
        "superseded_by",
    ]
    _insert_many(db, "kg_builds", columns, [row])


def _update_kg_build(db: DBProtocol, kg_build_id: str, fields: dict[str, Any]) -> None:
    assignments = ", ".join([f"{key} = ?" for key in fields])
    db.execute(
        f"UPDATE kg_builds SET {assignments} WHERE kg_build_id = ?",
        [*fields.values(), kg_build_id],
    )


def _apply_kg_activation_policy(
    db: DBProtocol,
    kg_build_id: str,
    *,
    quality_status: str,
    activate: bool,
) -> None:
    if quality_status == "passed" and activate:
        _activate_kg_build(db, kg_build_id)
    elif quality_status != "passed":
        _invalidate_kg_build(db, kg_build_id)


def _activate_kg_build(db: DBProtocol, kg_build_id: str) -> None:
    # Current-version selection belongs to kg_builds. Node and edge activity
    # denotes a valid materialization, so switching versions must not rewrite
    # millions of historical rows.
    db.execute(
        "UPDATE kg_builds SET is_active = 0, superseded_by = ?, "
        "status = CASE WHEN status = 'running' THEN 'superseded' ELSE status END "
        "WHERE COALESCE(is_active, 1) = 1 AND kg_build_id <> ?",
        (kg_build_id, kg_build_id),
    )
    db.execute(
        "UPDATE kg_builds SET is_active = 1, superseded_by = NULL WHERE kg_build_id = ?",
        (kg_build_id,),
    )


def _invalidate_kg_build(db: DBProtocol, kg_build_id: str) -> None:
    db.execute(
        "UPDATE kg_nodes SET is_active = 0 WHERE kg_build_id = ?",
        (kg_build_id,),
    )
    db.execute(
        "UPDATE kg_edges SET is_active = 0 WHERE kg_build_id = ?",
        (kg_build_id,),
    )


def _write_quality_checks(
    db: DBProtocol, kg_build_id: str, report: dict[str, Any]
) -> None:
    rows = []
    for key, status in (report.get("check_statuses") or {}).items():
        value = report.get(key)
        rows.append(
            {
                "check_id": _hash_id("kgcheck", kg_build_id, key),
                "kg_build_id": kg_build_id,
                "check_type": key,
                "status": status,
                "severity": "error" if status == "failed" else "info",
                "message": f"{key}={value}",
            }
        )
    _insert_many(db, "kg_quality_checks", CHECK_COLUMNS, rows)


def _add_raw_object_node(
    db: DBProtocol, add_node: Any, add_edge: Any, raw_object_id: Any
) -> None:
    if not raw_object_id:
        return
    row = db.fetchone(
        "SELECT * FROM raw_objects WHERE raw_object_id = ?", (raw_object_id,)
    )
    if not row:
        return
    item = dict(row)
    add_node(
        _raw_object_node(raw_object_id),
        "RawObject",
        "raw_objects",
        raw_object_id,
        _pick(
            item,
            [
                "raw_object_id",
                "source_id",
                "object_type",
                "storage_uri",
                "original_url",
                "response_status",
                "content_sha256",
                "content_size_bytes",
                "retrieval_time",
                "source_publish_date",
                "source_update_time",
                "validation_status",
            ],
        ),
    )
    if item.get("source_id"):
        add_edge(
            _raw_object_node(raw_object_id),
            "FROM_SOURCE",
            _source_node(item.get("source_id")),
            "raw_objects",
            raw_object_id,
        )


def _missing_fact_edge_count(
    db: DBProtocol, kg_build_id: str, relation_type: str, incoming: bool = False
) -> int:
    endpoint = "dst_node_id" if incoming else "src_node_id"
    return _scalar(
        db,
        f"""
        SELECT COUNT(*) AS c
        FROM (
            SELECT node_id
            FROM kg_nodes
            WHERE kg_build_id = ? AND node_type = 'Fact'
            EXCEPT
            SELECT {endpoint}
            FROM kg_edges
            WHERE kg_build_id = ? AND relation_type = ?
        ) missing
        """,
        (kg_build_id, kg_build_id, relation_type),
    )


def _required_active_build_id(db: DBProtocol, table: str) -> str:
    rows = _rows(
        db,
        f"SELECT build_id, COUNT(*) AS c FROM {table} "
        "WHERE COALESCE(is_active, 1) = 1 AND build_id IS NOT NULL "
        "GROUP BY build_id ORDER BY build_id",
    )
    if len(rows) != 1:
        found = [row.get("build_id") for row in rows]
        raise RuntimeError(f"{table} must have exactly one active build; found {found}")
    return str(rows[0]["build_id"])


def _optional_active_build_id(db: DBProtocol, table: str) -> str | None:
    rows = _rows(
        db,
        f"SELECT build_id, COUNT(*) AS c FROM {table} "
        "WHERE COALESCE(is_active, 1) = 1 AND build_id IS NOT NULL "
        "GROUP BY build_id ORDER BY build_id",
    )
    if not rows:
        return None
    if len(rows) != 1:
        found = [row.get("build_id") for row in rows]
        raise RuntimeError(f"{table} must have at most one active build; found {found}")
    return str(rows[0]["build_id"])


def _validate_derived_build_chain(
    db: DBProtocol, qa_build_id: str, fact_build_id: str
) -> None:
    rows = _rows(
        db,
        "SELECT input_build_id, COUNT(*) AS c FROM derived_facts "
        "WHERE build_id = ? GROUP BY input_build_id",
        (qa_build_id,),
    )
    input_build_ids = {row.get("input_build_id") for row in rows}
    if input_build_ids != {fact_build_id}:
        raise RuntimeError(
            f"derived build {qa_build_id} must consume only fact build {fact_build_id}; "
            f"found {sorted(str(value) for value in input_build_ids)}"
        )


def _kg_fact_query(
    fact_build_id: str,
    fact_universe_build_id: str | None,
) -> tuple[str, tuple[Any, ...]]:
    if fact_universe_build_id:
        return (
            "SELECT sf.* FROM standardized_facts sf "
            "JOIN fact_universe_members m ON m.fact_id = sf.fact_id "
            "WHERE m.universe_build_id = ? "
            "AND sf.build_id = ? AND COALESCE(sf.is_active, 1) = 1 "
            "AND COALESCE(sf.graph_ready, 0) = 1 "
            "AND sf.verification_status IN ('single_source', 'cross_verified') "
            "ORDER BY sf.fact_id",
            (fact_universe_build_id, fact_build_id),
        )
    return (
        "SELECT * FROM standardized_facts "
        "WHERE build_id = ? AND COALESCE(is_active, 1) = 1 "
        "AND COALESCE(graph_ready, 0) = 1 "
        "AND verification_status IN ('single_source', 'cross_verified') "
        "ORDER BY fact_id",
        (fact_build_id,),
    )


def _selected_fact_ids(
    db: DBProtocol,
    fact_universe_build_id: str | None,
) -> set[str] | None:
    if not fact_universe_build_id:
        return None
    return {
        str(row["fact_id"])
        for row in _rows(
            db,
            "SELECT fact_id FROM fact_universe_members "
            "WHERE universe_build_id = ? ORDER BY fact_id",
            (fact_universe_build_id,),
        )
    }


def _selected_derived_ids(
    db: DBProtocol,
    fact_universe_build_id: str | None,
) -> set[str] | None:
    if not fact_universe_build_id:
        return None
    return {
        str(row["derived_id"])
        for row in _rows(
            db,
            "SELECT derived_id FROM fact_universe_derived_members "
            "WHERE universe_build_id = ? ORDER BY derived_id",
            (fact_universe_build_id,),
        )
    }


def _eligible_derived_rows(
    db: DBProtocol,
    qa_build_id: str,
    fact_build_id: str,
    *,
    selected_fact_ids: set[str] | None,
    selected_derived_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    rows = _rows(
        db,
        "SELECT * FROM derived_facts "
        "WHERE build_id = ? AND input_build_id = ? "
        "AND COALESCE(is_active, 1) = 1 "
        "AND verification_status IN ('single_source', 'cross_verified') "
        "ORDER BY derived_id",
        (qa_build_id, fact_build_id),
    )
    if selected_fact_ids is None:
        return rows
    eligible = []
    for row in rows:
        if (
            selected_derived_ids is not None
            and str(row.get("derived_id")) not in selected_derived_ids
        ):
            continue
        input_ids = {str(value) for value in _json_list(row.get("input_fact_ids"))}
        if input_ids and input_ids.issubset(selected_fact_ids):
            eligible.append(row)
    return eligible


def _fact_universe_build_mismatch_count(
    db: DBProtocol,
    fact_universe_build_id: str | None,
    fact_build_id: str | None,
) -> int:
    if not fact_universe_build_id:
        return 0
    return _scalar(
        db,
        "SELECT COUNT(*) AS c FROM fact_universe_builds "
        "WHERE universe_build_id = ? AND "
        "(input_fact_build_id <> ? OR status <> 'success' "
        "OR quality_status <> 'passed')",
        (fact_universe_build_id, fact_build_id),
    ) + _scalar(
        db,
        "SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS c "
        "FROM fact_universe_builds WHERE universe_build_id = ?",
        (fact_universe_build_id,),
    )


def _fact_outside_universe_count(
    db: DBProtocol,
    kg_build_id: str,
    fact_universe_build_id: str | None,
) -> int:
    if not fact_universe_build_id:
        return 0
    return _scalar(
        db,
        "SELECT COUNT(*) AS c FROM kg_nodes n "
        "LEFT JOIN fact_universe_members m "
        "ON m.universe_build_id = ? AND m.fact_id = n.source_pk "
        "WHERE n.kg_build_id = ? AND n.node_type = 'Fact' "
        "AND m.fact_id IS NULL",
        (fact_universe_build_id, kg_build_id),
    )


def _derived_fact_outside_universe_count(
    db: DBProtocol,
    kg_build_id: str,
    fact_universe_build_id: str | None,
) -> int:
    if not fact_universe_build_id:
        return 0
    return _scalar(
        db,
        "SELECT COUNT(*) AS c FROM kg_nodes n "
        "LEFT JOIN fact_universe_derived_members m "
        "ON m.universe_build_id = ? AND m.derived_id = n.source_pk "
        "WHERE n.kg_build_id = ? AND n.node_type = 'DerivedFact' "
        "AND m.derived_id IS NULL",
        (fact_universe_build_id, kg_build_id),
    )


def _expected_derived_time_count(
    db: DBProtocol,
    qa_build_id: str | None,
    fact_build_id: str | None,
    fact_universe_build_id: str | None,
) -> int:
    if not qa_build_id or not fact_build_id:
        return 0
    rows = _eligible_derived_rows(
        db,
        qa_build_id,
        fact_build_id,
        selected_fact_ids=_selected_fact_ids(db, fact_universe_build_id),
        selected_derived_ids=_selected_derived_ids(db, fact_universe_build_id),
    )
    return len(
        {
            _json(_json_dict(row.get("time_scope")))
            for row in rows
            if _json_dict(row.get("time_scope"))
        }
    )


def _expected_fact_count(
    db: DBProtocol,
    build_id: str | None,
    fact_universe_build_id: str | None = None,
) -> int:
    if not build_id:
        return 0
    if fact_universe_build_id:
        return _scalar(
            db,
            "SELECT COUNT(*) AS c FROM fact_universe_members "
            "WHERE universe_build_id = ?",
            (fact_universe_build_id,),
        )
    return _scalar(
        db,
        "SELECT COUNT(*) AS c FROM standardized_facts "
        "WHERE build_id = ? AND COALESCE(graph_ready, 0) = 1 "
        "AND verification_status IN ('single_source', 'cross_verified')",
        (build_id,),
    )


def _expected_derived_count(
    db: DBProtocol,
    qa_build_id: str | None,
    fact_build_id: str | None,
    fact_universe_build_id: str | None = None,
) -> int:
    if not qa_build_id or not fact_build_id:
        return 0
    if fact_universe_build_id:
        return _scalar(
            db,
            "SELECT COUNT(*) AS c FROM fact_universe_derived_members "
            "WHERE universe_build_id = ?",
            (fact_universe_build_id,),
        )
    return len(
        _eligible_derived_rows(
            db,
            qa_build_id,
            fact_build_id,
            selected_fact_ids=_selected_fact_ids(db, fact_universe_build_id),
            selected_derived_ids=_selected_derived_ids(db, fact_universe_build_id),
        )
    )


def _expected_derived_input_count(
    db: DBProtocol,
    qa_build_id: str | None,
    fact_build_id: str | None,
    fact_universe_build_id: str | None = None,
) -> int:
    if not qa_build_id or not fact_build_id:
        return 0
    return sum(
        len(_json_list(row.get("input_fact_ids")))
        for row in _eligible_derived_rows(
            db,
            qa_build_id,
            fact_build_id,
            selected_fact_ids=_selected_fact_ids(db, fact_universe_build_id),
            selected_derived_ids=_selected_derived_ids(db, fact_universe_build_id),
        )
    )


def _build_row_count(
    db: DBProtocol,
    table: str,
    build_id: str | None,
    extra_predicate: str | None = None,
) -> int:
    if not build_id:
        return 0
    sql = f"SELECT COUNT(*) AS c FROM {table} WHERE build_id = ?"
    if extra_predicate:
        sql += f" AND {extra_predicate}"
    return _scalar(db, sql, (build_id,))


def _node_type_count(db: DBProtocol, kg_build_id: str, node_type: str) -> int:
    return _scalar(
        db,
        "SELECT COUNT(*) AS c FROM kg_nodes WHERE kg_build_id = ? AND node_type = ?",
        (kg_build_id, node_type),
    )


def _edge_type_count(db: DBProtocol, kg_build_id: str, relation_type: str) -> int:
    return _scalar(
        db,
        "SELECT COUNT(*) AS c FROM kg_edges WHERE kg_build_id = ? AND relation_type = ?",
        (kg_build_id, relation_type),
    )


def _missing_node_edge_count(
    db: DBProtocol,
    kg_build_id: str,
    node_type: str,
    relation_type: str,
) -> int:
    return _scalar(
        db,
        """
        SELECT COUNT(*) AS c
        FROM (
            SELECT node_id
            FROM kg_nodes
            WHERE kg_build_id = ? AND node_type = ?
            EXCEPT
            SELECT src_node_id
            FROM kg_edges
            WHERE kg_build_id = ? AND relation_type = ?
        ) missing
        """,
        (kg_build_id, node_type, kg_build_id, relation_type),
    )


def _missing_edge_target_count(
    db: DBProtocol,
    kg_build_id: str,
    relation_type: str,
    target_node_type: str,
) -> int:
    return _scalar(
        db,
        """
        SELECT COUNT(*) AS c
        FROM (
            SELECT dst_node_id
            FROM kg_edges
            WHERE kg_build_id = ? AND relation_type = ?
            EXCEPT
            SELECT node_id
            FROM kg_nodes
            WHERE kg_build_id = ? AND node_type = ?
        ) invalid_targets
        """,
        (kg_build_id, relation_type, kg_build_id, target_node_type),
    )


def _dangling_edge_count(db: DBProtocol, kg_build_id: str, incoming: bool) -> int:
    endpoint = "dst_node_id" if incoming else "src_node_id"
    return _scalar(
        db,
        f"""
        SELECT COUNT(*) AS c
        FROM (
            SELECT {endpoint}
            FROM kg_edges
            WHERE kg_build_id = ?
            EXCEPT
            SELECT node_id
            FROM kg_nodes
            WHERE kg_build_id = ?
        ) dangling_nodes
        """,
        (kg_build_id, kg_build_id),
    )


def _invalid_relation_endpoint_count(db: DBProtocol, kg_build_id: str) -> int:
    contracts: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
        "HAS_SECURITY": (("Entity",), ("Security",)),
        "HAS_FACT": (("Entity",), ("Fact",)),
        "MEASURES": (("Fact",), ("Metric",)),
        "IN_PERIOD": (("Fact", "DerivedFact"), ("TimePeriod",)),
        "FROM_SOURCE": (("Fact", "SourceDocument", "RawObject"), ("DataSource",)),
        "TRACED_TO": (("Fact",), ("RawObject",)),
        "USES_SOURCE_DEFINITION": (("Fact",), ("SourceDefinition",)),
        "DEFINES": (("SourceDefinition",), ("Metric",)),
        "PROVIDED_BY": (("SourceDefinition",), ("DataSource",)),
        "FILED": (("Entity",), ("SourceDocument",)),
        "HAS_RAW_OBJECT": (("SourceDocument",), ("RawObject",)),
        "DERIVED_FROM": (("DerivedFact",), ("Fact",)),
        "ABOUT_ENTITY": (("DerivedFact",), ("Entity",)),
        "USES_METRIC": (("DerivedFact",), ("Metric",)),
        "HAS_SCOPE": (("DerivedFact",), ("EntitySet",)),
        "CONTAINS_ENTITY": (("EntitySet",), ("Entity",)),
        "BELONGS_TO_YEAR": (
            ("TimePeriod", "CalendarMonth", "CalendarQuarter"),
            ("CalendarYear",),
        ),
        "BELONGS_TO_MONTH": (("TimePeriod",), ("CalendarMonth",)),
        "BELONGS_TO_QUARTER": (("TimePeriod",), ("CalendarQuarter",)),
        "IN_FISCAL_YEAR": (("TimePeriod",), ("FiscalYear",)),
        "IN_FISCAL_YEAR_LABEL": (("TimePeriod",), ("FiscalYearLabel",)),
        "FISCAL_YEAR_OF": (("FiscalYear",), ("Entity",)),
    }
    relation_placeholders = ",".join("?" for _ in contracts)
    invalid_count = _scalar(
        db,
        f"""
        SELECT COUNT(*) AS c
        FROM kg_edges
        WHERE kg_build_id = ?
          AND relation_type NOT IN ({relation_placeholders})
        """,
        (kg_build_id, *contracts),
    )
    for relation_type, (source_types, target_types) in contracts.items():
        for endpoint, allowed_types in (
            ("src_node_id", source_types),
            ("dst_node_id", target_types),
        ):
            type_placeholders = ",".join("?" for _ in allowed_types)
            invalid_count += _scalar(
                db,
                f"""
                SELECT COUNT(*) AS c
                FROM (
                    SELECT {endpoint}
                    FROM kg_edges
                    WHERE kg_build_id = ? AND relation_type = ?
                    EXCEPT
                    SELECT node_id
                    FROM kg_nodes
                    WHERE kg_build_id = ?
                      AND node_type IN ({type_placeholders})
                ) invalid_endpoints
                """,
                (kg_build_id, relation_type, kg_build_id, *allowed_types),
            )
    return invalid_count


def _duplicate_stable_id_count(
    db: DBProtocol,
    table: str,
    stable_column: str,
    kg_build_id: str,
) -> int:
    return _scalar(
        db,
        f"""
        SELECT COALESCE(SUM(group_count - 1), 0) AS c
        FROM (
            SELECT COUNT(*) AS group_count
            FROM {table}
            WHERE kg_build_id = ?
            GROUP BY {stable_column}
            HAVING COUNT(*) > 1
        ) duplicates
        """,
        (kg_build_id,),
    )


def _source_build_mismatch_count(
    db: DBProtocol,
    kg_build_id: str,
    node_type: str,
    source_table: str,
    source_pk: str,
    expected_build_id: str | None,
) -> int:
    if not expected_build_id:
        return 0
    return _scalar(
        db,
        f"""
        SELECT COUNT(*) AS c FROM kg_nodes n
        LEFT JOIN {source_table} source_row
          ON source_row.{source_pk} = n.source_pk
        WHERE n.kg_build_id = ? AND n.node_type = ?
          AND (source_row.{source_pk} IS NULL OR source_row.build_id <> ?)
        """,
        (kg_build_id, node_type, expected_build_id),
    )


def _distinct_json_count(
    db: DBProtocol,
    table: str,
    column: str,
    where_clause: str,
    params: Iterable[Any],
) -> int:
    rows = db.fetchall(
        f"SELECT DISTINCT {column} FROM {table} "
        f"WHERE {where_clause} AND {column} IS NOT NULL",
        params,
    )
    return len(rows)


def _active_kg_build_id(db: DBProtocol) -> str | None:
    try:
        row = db.fetchone(
            "SELECT kg_build_id FROM kg_builds WHERE COALESCE(is_active, 1) = 1 ORDER BY completed_at DESC, started_at DESC LIMIT 1"
        )
    except Exception:
        return None
    return dict(row).get("kg_build_id") if row else None


def _rows(db: DBProtocol, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in db.fetchall(sql, params)]


def _scalar(db: DBProtocol, sql: str, params: Iterable[Any] = ()) -> int:
    row = db.fetchone(sql, params)
    item = dict(row) if row else {}
    return int(item.get("c") if item.get("c") is not None else 0)


def _pick(row: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {
        key: row.get(key) for key in keys if key in row and row.get(key) is not None
    }


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
    return _pick(
        row,
        [
            "time_basis",
            "metric_period_type",
            "frequency",
            "period_start",
            "period_end",
            "calendar_year",
            "fiscal_year",
            "fiscal_quarter",
            "as_of_date",
        ],
    )


def _time_node(row: dict[str, Any]) -> str:
    parts = [
        row.get("time_basis"),
        row.get("metric_period_type"),
        row.get("period_start"),
        row.get("period_end"),
        row.get("calendar_year"),
        row.get("fiscal_year"),
        row.get("fiscal_quarter"),
        row.get("as_of_date"),
    ]
    return "time:" + _digest(parts)


def _derived_time_node(time_scope: dict[str, Any]) -> str:
    return "time:derived:" + _digest([time_scope])


def _add_time_hierarchy(
    add_node: Any,
    add_edge: Any,
    time_node: str,
    values: dict[str, Any],
    entity_id: str | None,
) -> None:
    date_value = _coerce_date(
        values.get("as_of_date")
        or values.get("period_end")
        or values.get("date")
        or values.get("end_date")
    )
    basis = str(values.get("basis") or values.get("time_basis") or "").lower()
    year = _valid_year(values.get("calendar_year"))
    if year is None and basis != "fiscal_year":
        year = _valid_year(
            values.get("year") or values.get("result_year") or values.get("end_year")
        )
    if year is None and date_value:
        year = date_value.year

    year_node = None
    if year is not None:
        year_node = f"calendar_year:{year}"
        add_node(year_node, "CalendarYear", "time_hierarchy", year, {"year": year})
        add_edge(time_node, "BELONGS_TO_YEAR", year_node, "time_hierarchy", time_node)

    frequency = str(values.get("frequency") or "").lower()
    include_month = bool(date_value) and (
        frequency in {"daily", "weekly", "monthly"} or basis == "observation_date"
    )
    if include_month and date_value:
        month_node = f"calendar_month:{date_value.year:04d}-{date_value.month:02d}"
        add_node(
            month_node,
            "CalendarMonth",
            "time_hierarchy",
            f"{date_value.year:04d}-{date_value.month:02d}",
            {"year": date_value.year, "month": date_value.month},
        )
        add_edge(time_node, "BELONGS_TO_MONTH", month_node, "time_hierarchy", time_node)
        month_year = f"calendar_year:{date_value.year}"
        add_node(
            month_year,
            "CalendarYear",
            "time_hierarchy",
            date_value.year,
            {"year": date_value.year},
        )
        add_edge(
            month_node, "BELONGS_TO_YEAR", month_year, "time_hierarchy", month_node
        )

    quarter = None
    fiscal_quarter = values.get("fiscal_quarter")
    if isinstance(fiscal_quarter, str) and fiscal_quarter in {"Q1", "Q2", "Q3", "Q4"}:
        quarter = int(fiscal_quarter[1])
    elif date_value and (include_month or frequency == "quarterly"):
        quarter = (date_value.month - 1) // 3 + 1
    if quarter is not None and date_value:
        quarter_node = f"calendar_quarter:{date_value.year}:Q{quarter}"
        add_node(
            quarter_node,
            "CalendarQuarter",
            "time_hierarchy",
            f"{date_value.year}:Q{quarter}",
            {"year": date_value.year, "quarter": quarter},
        )
        add_edge(
            time_node, "BELONGS_TO_QUARTER", quarter_node, "time_hierarchy", time_node
        )
        quarter_year = f"calendar_year:{date_value.year}"
        add_node(
            quarter_year,
            "CalendarYear",
            "time_hierarchy",
            date_value.year,
            {"year": date_value.year},
        )
        add_edge(
            quarter_node,
            "BELONGS_TO_YEAR",
            quarter_year,
            "time_hierarchy",
            quarter_node,
        )

    fiscal_year = _valid_year(values.get("fiscal_year"))
    if fiscal_year is None and str(values.get("basis") or "") == "fiscal_year":
        fiscal_year = _valid_year(
            values.get("year") or values.get("result_year") or values.get("end_year")
        )
    if fiscal_year is not None and entity_id:
        fiscal_node = f"fiscal_year:{entity_id}:{fiscal_year}"
        add_node(
            fiscal_node,
            "FiscalYear",
            "time_hierarchy",
            f"{entity_id}:{fiscal_year}",
            {"entity_id": entity_id, "fiscal_year": fiscal_year},
        )
        add_edge(time_node, "IN_FISCAL_YEAR", fiscal_node, "time_hierarchy", time_node)
        add_edge(
            fiscal_node,
            "FISCAL_YEAR_OF",
            _entity_node(entity_id),
            "time_hierarchy",
            fiscal_node,
        )
    elif fiscal_year is not None:
        fiscal_label = f"fiscal_year_label:{fiscal_year}"
        add_node(
            fiscal_label,
            "FiscalYearLabel",
            "time_hierarchy",
            fiscal_year,
            {"fiscal_year": fiscal_year, "semantics": "cross_entity_fiscal_year_label"},
        )
        add_edge(
            time_node,
            "IN_FISCAL_YEAR_LABEL",
            fiscal_label,
            "time_hierarchy",
            time_node,
        )


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _valid_year(value: Any) -> int | None:
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    return year if 1000 <= year <= 3000 else None


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


def _stable_edge_id(
    src: str, relation: str, dst: str, source_table: str | None, source_pk: Any
) -> str:
    return "edge:" + _digest([src, relation, dst, source_table, source_pk])


def _versioned_graph_id(stable_id: str, kg_build_id: str) -> str:
    return f"{stable_id}@@{kg_build_id}"


def _hash_id(prefix: str, *parts: Any) -> str:
    return prefix + "_" + _digest(parts)


def _digest(parts: Iterable[Any]) -> str:
    return hashlib.sha1(
        json.dumps(list(parts), ensure_ascii=False, sort_keys=True, default=str).encode(
            "utf-8"
        )
    ).hexdigest()[:24]


def _new_kg_build_id() -> str:
    return (
        "kg_"
        + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        + "_"
        + _digest([datetime.now(timezone.utc).isoformat()])[:8]
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
