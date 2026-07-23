from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from finraw.db.client import DBProtocol


BUILD_COLUMNS: dict[str, dict[str, str]] = {
    "canonical_entities": {"build_id": "TEXT", "is_active": "INTEGER DEFAULT 1", "superseded_by": "TEXT"},
    "entity_alias_map": {"build_id": "TEXT", "is_active": "INTEGER DEFAULT 1", "superseded_by": "TEXT"},
    "canonical_securities": {"build_id": "TEXT", "is_active": "INTEGER DEFAULT 1", "superseded_by": "TEXT"},
    "entity_relationships": {"build_id": "TEXT", "is_active": "INTEGER DEFAULT 1", "superseded_by": "TEXT"},
    "source_series_entity_map": {"build_id": "TEXT", "is_active": "INTEGER DEFAULT 1", "superseded_by": "TEXT"},
    "metrics": {"build_id": "TEXT", "is_active": "INTEGER DEFAULT 1", "superseded_by": "TEXT"},
    "metric_alias_map": {"build_id": "TEXT", "is_active": "INTEGER DEFAULT 1", "superseded_by": "TEXT"},
    "source_metric_definitions": {"build_id": "TEXT", "is_active": "INTEGER DEFAULT 1", "superseded_by": "TEXT"},
    "time_series_frequency_map": {"build_id": "TEXT", "is_active": "INTEGER DEFAULT 1", "superseded_by": "TEXT"},
    "atomic_facts": {
        "stable_fact_id": "TEXT",
        "build_id": "TEXT",
        "raw_snapshot_id": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "superseded_by": "TEXT",
    },
    "standardized_facts": {
        "stable_fact_id": "TEXT",
        "build_id": "TEXT",
        "raw_snapshot_id": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "superseded_by": "TEXT",
        "graph_ready": "INTEGER DEFAULT 0",
        "graph_ready_reason": "TEXT",
        "raw_equivalence_group_id": "TEXT",
        "semantic_equivalence_group_id": "TEXT",
        "source_definition_id": "TEXT",
        "frequency": "TEXT",
        "seasonal_adjustment": "TEXT",
        "vintage_policy": "TEXT",
        "is_forecast": "INTEGER",
        "comparability_level": "TEXT",
    },
    "fact_quality_checks": {"build_id": "TEXT", "is_active": "INTEGER DEFAULT 1", "superseded_by": "TEXT"},
    "derived_facts": {
        "stable_derived_id": "TEXT",
        "build_id": "TEXT",
        "input_build_id": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "superseded_by": "TEXT",
        "scope_type": "TEXT",
        "scope_id": "TEXT",
        "scope_definition": "TEXT",
        "scope_entity_ids": "TEXT",
        "scope_source": "TEXT",
    },
    "document_text_chunks": {
        "stable_chunk_id": "TEXT",
        "build_id": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "superseded_by": "TEXT",
    },
    "raw_extracted_tables": {
        "stable_table_id": "TEXT",
        "build_id": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "superseded_by": "TEXT",
    },
    "candidate_facts": {
        "stable_candidate_id": "TEXT",
        "build_id": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "superseded_by": "TEXT",
        "candidate_state": "TEXT",
        "state_reason": "TEXT",
        "matched_metric_id": "TEXT",
        "evidence_status": "TEXT",
        "cross_check_status": "TEXT",
        "promotion_status": "TEXT",
        "promoted_fact_id": "TEXT",
        "qa_eligible": "INTEGER DEFAULT 0",
        "kg_eligible": "INTEGER DEFAULT 0",
        "period_start": "TEXT",
        "period_end": "TEXT",
        "fiscal_year": "INTEGER",
        "fiscal_quarter": "TEXT",
        "currency": "TEXT",
        "value_scale": "TEXT",
        "source_field_name": "TEXT",
        "statement_type": "TEXT",
        "financial_scope_type": "TEXT",
        "page_number": "INTEGER",
        "row_index": "INTEGER",
        "column_index": "INTEGER",
        "extraction_metadata": "TEXT",
        "evidence_sha256": "TEXT",
    },
    "candidate_fact_evidence": {
        "unit_source_page": "INTEGER",
        "unit_evidence_text": "TEXT",
        "statement_source_page": "INTEGER",
        "period_source_page": "INTEGER",
    },
    "source_documents": {
        "stable_document_id": "TEXT",
        "build_id": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "superseded_by": "TEXT",
    },
}


MDM_SQL = """
CREATE TABLE IF NOT EXISTS canonical_securities (
    security_id         TEXT PRIMARY KEY,
    company_entity_id  TEXT REFERENCES canonical_entities(entity_id),
    canonical_name     TEXT NOT NULL,
    security_type      TEXT,
    market             TEXT,
    country            TEXT,
    exchange           TEXT,
    ticker             TEXT,
    composite_ticker   TEXT,
    figi               TEXT,
    isin               TEXT,
    cusip              TEXT,
    currency           TEXT,
    is_primary_listing INTEGER DEFAULT 1,
    listing_status     TEXT,
    valid_from         TEXT,
    valid_to           TEXT,
    build_id           TEXT,
    is_active          INTEGER DEFAULT 1,
    superseded_by      TEXT,
    created_at         TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at         TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_canonical_securities_company ON canonical_securities(company_entity_id);
CREATE INDEX IF NOT EXISTS idx_canonical_securities_ticker_exchange ON canonical_securities(ticker, exchange);
CREATE TABLE IF NOT EXISTS entity_relationships (
    relationship_id    TEXT PRIMARY KEY,
    subject_entity_id  TEXT REFERENCES canonical_entities(entity_id),
    relationship_type  TEXT NOT NULL,
    object_id          TEXT,
    object_type        TEXT,
    object_entity_id   TEXT REFERENCES canonical_entities(entity_id),
    source_id          TEXT REFERENCES source_registry(source_id),
    source_code        TEXT,
    confidence_score   REAL,
    valid_from         TEXT,
    valid_to           TEXT,
    notes              TEXT,
    build_id           TEXT,
    is_active          INTEGER DEFAULT 1,
    superseded_by      TEXT,
    created_at         TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_entity_relationships_subject ON entity_relationships(subject_entity_id, relationship_type);
CREATE INDEX IF NOT EXISTS idx_entity_relationships_object ON entity_relationships(object_id, object_type);
CREATE INDEX IF NOT EXISTS idx_entity_relationships_object_entity ON entity_relationships(object_entity_id);
CREATE TABLE IF NOT EXISTS source_series_entity_map (
    series_map_id      TEXT PRIMARY KEY,
    source_id          TEXT REFERENCES source_registry(source_id),
    series_id          TEXT,
    series_entity_id   TEXT REFERENCES canonical_entities(entity_id),
    metric_id          TEXT REFERENCES metrics(metric_id),
    applies_to_entity_id TEXT REFERENCES canonical_entities(entity_id),
    instrument_entity_id TEXT REFERENCES canonical_entities(entity_id),
    frequency          TEXT,
    source_units       TEXT,
    seasonal_adjustment TEXT,
    notes              TEXT,
    build_id           TEXT,
    is_active          INTEGER DEFAULT 1,
    superseded_by      TEXT,
    created_at         TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_source_series_entity_map_source_series ON source_series_entity_map(source_id, series_id);
CREATE INDEX IF NOT EXISTS idx_source_series_entity_map_metric ON source_series_entity_map(metric_id);
CREATE INDEX IF NOT EXISTS idx_source_series_entity_map_target ON source_series_entity_map(applies_to_entity_id, instrument_entity_id);
"""

SOURCE_DOCUMENTS_SQL = """
CREATE TABLE IF NOT EXISTS source_documents (
    document_id         TEXT PRIMARY KEY,
    stable_document_id  TEXT,
    build_id            TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    entity_id           TEXT REFERENCES canonical_entities(entity_id),
    source_id           TEXT REFERENCES source_registry(source_id),
    form_type           TEXT,
    report_type         TEXT,
    period_end          TEXT,
    filing_date         TEXT,
    storage_uri         TEXT,
    original_url        TEXT,
    raw_object_id       TEXT REFERENCES raw_objects(raw_object_id),
    document_status     TEXT,
    notes               TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_source_documents_entity ON source_documents(entity_id);
CREATE INDEX IF NOT EXISTS idx_source_documents_source ON source_documents(source_id, form_type, report_type);
CREATE INDEX IF NOT EXISTS idx_source_documents_period ON source_documents(period_end, filing_date);
CREATE INDEX IF NOT EXISTS idx_source_documents_raw_object ON source_documents(raw_object_id);
"""

DOCUMENT_CANDIDATE_EVIDENCE_SQL = """
CREATE TABLE IF NOT EXISTS candidate_fact_evidence (
    evidence_id         TEXT PRIMARY KEY,
    candidate_id        TEXT REFERENCES candidate_facts(candidate_id),
    build_id            TEXT,
    raw_object_id       TEXT REFERENCES raw_objects(raw_object_id),
    table_id            TEXT REFERENCES raw_extracted_tables(table_id),
    page_number         INTEGER,
    unit_source_page    INTEGER,
    unit_evidence_text  TEXT,
    statement_source_page INTEGER,
    period_source_page  INTEGER,
    statement_type      TEXT,
    financial_scope_type TEXT,
    row_index           INTEGER,
    column_index        INTEGER,
    source_field_name   TEXT,
    raw_value_text      TEXT,
    period_label        TEXT,
    evidence_text       TEXT,
    evidence_sha256     TEXT,
    verification_method TEXT,
    validation_status   TEXT,
    validation_errors   TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_candidate_fact_evidence_candidate
ON candidate_fact_evidence(candidate_id);
CREATE INDEX IF NOT EXISTS idx_candidate_fact_evidence_object_page
ON candidate_fact_evidence(raw_object_id, page_number);
"""


def make_build_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}"


def ensure_build_schema(db: DBProtocol) -> None:
    for sql_block in [MDM_SQL, SOURCE_DOCUMENTS_SQL, DOCUMENT_CANDIDATE_EVIDENCE_SQL]:
        for statement in sql_block.split(";"):
            statement = statement.strip()
            if statement:
                db.execute(statement)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_builds (
            build_id            TEXT PRIMARY KEY,
            layer               TEXT,
            command             TEXT,
            raw_snapshot_id     TEXT,
            input_build_id      TEXT,
            status              TEXT,
            started_at          TEXT,
            completed_at        TEXT,
            notes               TEXT
        )
        """
    )
    for table, columns in BUILD_COLUMNS.items():
        for column, column_type in columns.items():
            try:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
            except Exception:
                pass


def start_build(
    db: DBProtocol,
    *,
    layer: str,
    command: str,
    prefix: str | None = None,
    raw_snapshot_id: str | None = None,
    input_build_id: str | None = None,
    notes: str | None = None,
) -> str:
    ensure_build_schema(db)
    db.execute(
        """
        UPDATE pipeline_builds
        SET status = ?, completed_at = ?, notes = COALESCE(notes, '') || ?
        WHERE command = ? AND status = ?
        """,
        ["failed", _now(), "; superseded by a newer build start", command, "running"],
    )
    build_id = make_build_id(prefix or command.replace("-", "_"))
    db.execute(
        """
        INSERT INTO pipeline_builds (
            build_id, layer, command, raw_snapshot_id, input_build_id, status, started_at, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [build_id, layer, command, raw_snapshot_id, input_build_id, "running", _now(), notes],
    )
    return build_id


def finish_build(db: DBProtocol, build_id: str, status: str = "success", notes: str | None = None) -> None:
    db.execute(
        "UPDATE pipeline_builds SET status = ?, completed_at = ?, notes = COALESCE(?, notes) WHERE build_id = ?",
        [status, _now(), notes, build_id],
    )



def mark_running_builds_failed(db: DBProtocol, notes: str | None = None) -> None:
    ensure_build_schema(db)
    db.execute(
        """
        UPDATE pipeline_builds
        SET status = ?, completed_at = ?, notes = COALESCE(?, notes)
        WHERE status = ?
        """,
        ["failed", _now(), notes, "running"],
    )

    # KG builds are populated while inactive. Quarantine partial rows on error
    # and preserve the previously active graph.
    try:
        running_kg_builds = db.fetchall(
            "SELECT kg_build_id FROM kg_builds WHERE status = ?",
            ["running"],
        )
        for row in running_kg_builds:
            kg_build_id = row["kg_build_id"]
            db.execute(
                "UPDATE kg_nodes SET is_active = 0 WHERE kg_build_id = ?",
                [kg_build_id],
            )
            db.execute(
                "UPDATE kg_edges SET is_active = 0 WHERE kg_build_id = ?",
                [kg_build_id],
            )
        db.execute(
            "UPDATE kg_builds SET status = ?, quality_status = ?, completed_at = ?, "
            "notes = COALESCE(?, notes), is_active = 0 WHERE status = ?",
            ["failed", "failed", _now(), notes, "running"],
        )
    except Exception:
        pass


def latest_active_build(db: DBProtocol, table: str) -> str | None:
    ensure_build_schema(db)
    try:
        row = db.fetchone(
            f"""
            SELECT build_id
            FROM {table}
            WHERE is_active = 1 AND build_id IS NOT NULL
            GROUP BY build_id
            ORDER BY MAX(created_at) DESC
            LIMIT 1
            """
        )
    except Exception:
        row = None
    return row["build_id"] if row and row["build_id"] else None


def deactivate_active_rows(db: DBProtocol, table: str, superseded_by: str) -> None:
    ensure_build_schema(db)
    try:
        db.execute(
            f"UPDATE {table} SET is_active = 0, superseded_by = ? WHERE COALESCE(is_active, 1) = 1",
            [superseded_by],
        )
    except Exception:
        pass


def scoped_active_clause(alias: str | None = None) -> str:
    prefix = f"{alias}." if alias else ""
    return f"COALESCE({prefix}is_active, 1) = 1"


def attach_build(row: dict[str, Any], build_id: str, *, stable_key: str | None = None, stable_value: str | None = None) -> dict[str, Any]:
    out = dict(row)
    out["build_id"] = build_id
    out["is_active"] = 1
    out["superseded_by"] = None
    if stable_key and stable_value:
        out[stable_key] = stable_value
    return out


def versioned_id(stable_id: str, build_id: str) -> str:
    return f"{stable_id}__{build_id}"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
