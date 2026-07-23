from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable, ContextManager, Iterator, Protocol

from finraw.db.schema import SCHEMA_SQL, SOURCE_REGISTRY_SEED
from finraw.storage import utc_now


class DBProtocol(Protocol):
    def close(self) -> None: ...
    def init_schema(self) -> None: ...
    def seed_sources(self) -> None: ...
    def transaction(self) -> ContextManager[None]: ...
    def execute(self, sql: str, params: Iterable[Any] = ()) -> None: ...
    def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[Any]: ...
    def fetchone(self, sql: str, params: Iterable[Any] = ()) -> Any | None: ...
    def insert_job(self, job: dict[str, Any]) -> None: ...
    def update_job(self, job_id: str, **fields: Any) -> None: ...
    def find_raw_object(self, source_id: str, original_url: str, content_sha256: str, include_statuses: tuple[str, ...] | None = ("passed",)) -> Any | None: ...
    def find_existing_passed_object(self, source_id: str, original_url: str, content_sha256: str) -> Any | None: ...
    def find_any_existing_object(self, source_id: str, original_url: str, content_sha256: str) -> Any | None: ...
    def insert_raw_object(self, obj: dict[str, Any]) -> None: ...
    def insert_raw_records(self, records: list[dict[str, Any]]) -> None: ...
    def upsert_source_entity(self, **kwargs: Any) -> None: ...
    def insert_snapshot(self, snapshot: dict[str, Any]) -> None: ...
    def insert_atomic_facts(self, facts: list[dict[str, Any]]) -> None: ...
    def sync_atomic_fact_verification_status(self) -> None: ...
    def insert_fact_quality_checks(self, checks: list[dict[str, Any]]) -> None: ...
    def insert_standardized_facts(self, facts: list[dict[str, Any]]) -> None: ...
    def update_standardized_fact_statuses(self, updates: list[dict[str, Any]], only_flags: bool = False) -> None: ...
    def update_standardized_graph_ready(self, updates: list[dict[str, Any]]) -> None: ...
    def insert_derived_facts(self, facts: list[dict[str, Any]]) -> None: ...


class MetadataDB:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._transaction_depth = 0

    def _commit_if_needed(self) -> None:
        if self._transaction_depth == 0:
            self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA_SQL)
        self.conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_objects_url_hash "
            "ON raw_objects(source_id, original_url, content_sha256)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_source_entities_source_code "
            "ON source_entities(source_id, source_code)"
        )
        self._commit_if_needed()

    def seed_sources(self) -> None:
        columns = [
            "source_id", "source_name", "source_type", "authority_level",
            "market", "provider", "base_url", "access_method",
            "update_frequency", "license_note", "rate_limit_note"
        ]
        sql = f"""
        INSERT OR REPLACE INTO source_registry ({','.join(columns)})
        VALUES ({','.join('?' for _ in columns)})
        """
        self.conn.executemany(sql, [[row.get(col) for col in columns] for row in SOURCE_REGISTRY_SEED])
        self._commit_if_needed()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        try:
            self.conn.execute(sql, tuple(params))
            if self._transaction_depth == 0:
                self._commit_if_needed()
        except Exception:
            if self._transaction_depth == 0:
                self.conn.rollback()
            raise

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self._transaction_depth:
            self._transaction_depth += 1
            try:
                yield
            finally:
                self._transaction_depth -= 1
            return
        self.conn.execute("BEGIN IMMEDIATE")
        self._transaction_depth = 1
        try:
            yield
        except Exception:
            self.conn.rollback()
            raise
        else:
            self.conn.commit()
        finally:
            self._transaction_depth = 0

    def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return list(self.conn.execute(sql, tuple(params)).fetchall())

    def fetchone(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, tuple(params)).fetchone()

    def insert_job(self, job: dict[str, Any]) -> None:
        columns = [
            "job_id", "source_id", "job_type", "target_scope", "start_time",
            "end_time", "status", "records_found", "records_saved",
            "error_message", "config"
        ]
        values = [self._json(job.get(col)) if col in {"target_scope", "config"} else job.get(col) for col in columns]
        self.conn.execute(
            f"INSERT OR REPLACE INTO ingestion_jobs ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            values,
        )
        self._commit_if_needed()

    def update_job(self, job_id: str, **fields: Any) -> None:
        assignments = []
        values: list[Any] = []
        for key, value in fields.items():
            assignments.append(f"{key} = ?")
            values.append(self._json(value) if key in {"target_scope", "config"} else value)
        values.append(job_id)
        self.conn.execute(f"UPDATE ingestion_jobs SET {', '.join(assignments)} WHERE job_id = ?", values)
        self._commit_if_needed()

    def find_raw_object(
        self,
        source_id: str,
        original_url: str,
        content_sha256: str,
        include_statuses: tuple[str, ...] | None = ("passed",),
    ) -> sqlite3.Row | None:
        sql = "SELECT * FROM raw_objects WHERE source_id = ? AND original_url = ? AND content_sha256 = ?"
        params: list[Any] = [source_id, original_url, content_sha256]
        if include_statuses is not None:
            if not include_statuses:
                return None
            sql += f" AND validation_status IN ({','.join('?' for _ in include_statuses)})"
            params.extend(include_statuses)
        return self.fetchone(sql, params)

    def find_existing_passed_object(self, source_id: str, original_url: str, content_sha256: str) -> sqlite3.Row | None:
        return self.find_raw_object(source_id, original_url, content_sha256, include_statuses=("passed",))

    def find_any_existing_object(self, source_id: str, original_url: str, content_sha256: str) -> sqlite3.Row | None:
        return self.find_raw_object(source_id, original_url, content_sha256, include_statuses=None)

    def insert_raw_object(self, obj: dict[str, Any]) -> None:
        columns = [
            "raw_object_id", "source_id", "job_id", "object_type", "storage_uri",
            "original_url", "request_params", "response_headers", "response_status",
            "content_sha256", "content_size_bytes", "compression", "retrieval_time",
            "source_publish_date", "source_update_time", "parse_status",
            "validation_status", "notes"
        ]
        json_columns = {"request_params", "response_headers"}
        values = [self._json(obj.get(col)) if col in json_columns else obj.get(col) for col in columns]
        self.conn.execute(
            f"INSERT OR REPLACE INTO raw_objects ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            values,
        )
        self._commit_if_needed()

    def insert_raw_records(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        columns = [
            "raw_record_id", "raw_object_id", "source_id", "record_key",
            "record_type", "record_json", "entity_hint", "metric_hint", "period_hint"
        ]
        values = [[self._json(row.get(col)) if col == "record_json" else row.get(col) for col in columns] for row in records]
        self.conn.executemany(
            f"INSERT OR REPLACE INTO raw_records ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            values,
        )
        self._commit_if_needed()


    def insert_atomic_facts(self, facts: list[dict[str, Any]]) -> None:
        if not facts:
            return
        columns = ["fact_id", "stable_fact_id", "build_id", "raw_snapshot_id", "is_active", "superseded_by", "entity_id", "metric_id", "value", "value_type", "unit", "currency", "period_start", "period_end", "fiscal_year", "fiscal_quarter", "as_of_date", "report_date", "source_id", "raw_object_id", "source_field_name", "source_page_or_table", "extraction_method", "confidence_score", "verification_status", "tolerance", "notes"]
        values = [[_row_value(row, col) for col in columns] for row in facts]
        self.conn.executemany(
            f"INSERT OR REPLACE INTO atomic_facts ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            values,
        )
        self._commit_if_needed()


    def insert_standardized_facts(self, facts: list[dict[str, Any]]) -> None:
        if not facts:
            return
        columns = ["fact_id", "stable_fact_id", "build_id", "raw_snapshot_id", "is_active", "superseded_by", "entity_id", "entity_scope_id", "financial_scope_type", "metric_id", "normalized_value", "normalized_unit", "normalized_currency", "value_scale", "period_start", "period_end", "calendar_year", "fiscal_year", "fiscal_quarter", "time_basis", "metric_period_type", "source_definition_id", "frequency", "seasonal_adjustment", "vintage_policy", "is_forecast", "comparability_level", "as_of_date", "report_date", "source_id", "raw_object_id", "verification_status", "validation_flags", "conflict_group_id", "raw_equivalence_group_id", "semantic_equivalence_group_id", "confidence_score", "notes"]
        values = [[self._json(_row_value(row, col)) if col == "validation_flags" else _row_value(row, col) for col in columns] for row in facts]
        self.conn.executemany(
            f"INSERT OR REPLACE INTO standardized_facts ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            values,
        )
        self._commit_if_needed()

    def insert_fact_quality_checks(self, checks: list[dict[str, Any]]) -> None:
        if not checks:
            return
        columns = ["check_id", "fact_id", "build_id", "is_active", "superseded_by", "check_type", "status", "severity", "message"]
        values = [[_row_value(row, col) for col in columns] for row in checks]
        self.conn.executemany(
            f"INSERT OR REPLACE INTO fact_quality_checks ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            values,
        )
        self._commit_if_needed()


    def update_standardized_fact_statuses(self, updates: list[dict[str, Any]], only_flags: bool = False) -> None:
        if not updates:
            return
        if only_flags:
            values = [(self._json(row.get("validation_flags") or []), row.get("fact_id")) for row in updates]
            self.conn.executemany("UPDATE standardized_facts SET validation_flags = ? WHERE fact_id = ?", values)
        else:
            values = [
                (row.get("verification_status"), self._json(row.get("validation_flags") or []), row.get("conflict_group_id"), row.get("fact_id"))
                for row in updates
            ]
            self.conn.executemany(
                "UPDATE standardized_facts SET verification_status = ?, validation_flags = ?, conflict_group_id = ? WHERE fact_id = ?",
                values,
            )
        self._commit_if_needed()

    def sync_atomic_fact_verification_status(self) -> None:
        self.conn.execute(
            """
            UPDATE atomic_facts
            SET verification_status = (
                SELECT verification_status FROM standardized_facts
                WHERE standardized_facts.fact_id = atomic_facts.fact_id
                  AND COALESCE(standardized_facts.is_active, 1) = 1
            )
            WHERE COALESCE(is_active, 1) = 1
              AND fact_id IN (SELECT fact_id FROM standardized_facts WHERE COALESCE(is_active, 1) = 1)
            """
        )
        self._commit_if_needed()

    def insert_derived_facts(self, facts: list[dict[str, Any]]) -> None:
        if not facts:
            return
        columns = ["derived_id", "stable_derived_id", "build_id", "input_build_id", "is_active", "superseded_by", "derived_type", "input_fact_ids", "entity_scope", "metric_scope", "time_scope", "scope_type", "scope_id", "scope_definition", "scope_entity_ids", "scope_source", "calculation_code", "output_value", "output_table", "unit", "tolerance", "verification_status"]
        json_columns = {"input_fact_ids", "entity_scope", "metric_scope", "time_scope", "scope_entity_ids", "output_table"}
        values = [[self._json(_row_value(row, col)) if col in json_columns else _row_value(row, col) for col in columns] for row in facts]
        self.conn.executemany(
            f"INSERT OR REPLACE INTO derived_facts ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            values,
        )
        self._commit_if_needed()


    def upsert_source_entity(self, *, source_id: str, source_code: str, source_name: str | None = None,
                             aliases: list[str] | None = None, market: str | None = None,
                             raw_metadata: dict[str, Any] | None = None) -> None:
        entity_id = f"{source_id}:{source_code}"
        existing = self.fetchone("SELECT first_seen_at FROM source_entities WHERE source_entity_id = ?", (entity_id,))
        first_seen_at = existing["first_seen_at"] if existing else utc_now()
        self.conn.execute(
            """
            INSERT OR REPLACE INTO source_entities (
                source_entity_id, source_id, source_code, source_name, aliases,
                market, raw_metadata, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (entity_id, source_id, source_code, source_name, self._json(aliases or []), market,
             self._json(raw_metadata or {}), first_seen_at, utc_now()),
        )
        self._commit_if_needed()

    def insert_snapshot(self, snapshot: dict[str, Any]) -> None:
        columns = ["snapshot_id", "source_id", "snapshot_date", "storage_prefix", "object_count", "total_size_bytes", "manifest_uri", "checksum_uri"]
        self.conn.execute(
            f"INSERT OR REPLACE INTO raw_dataset_snapshots ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            [snapshot.get(col) for col in columns],
        )
        self._commit_if_needed()

    @staticmethod
    def _json(value: Any) -> str | None:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False, sort_keys=True)


class PostgresMetadataDB:
    def __init__(self, dsn: str, schema_path: str = "sql/postgres_schema.sql"):
        import psycopg
        from psycopg.rows import dict_row

        self.dsn = dsn
        self.schema_path = Path(schema_path)
        self.conn = psycopg.connect(dsn, row_factory=dict_row)
        self._transaction_depth = 0

    def _commit_if_needed(self) -> None:
        if self._transaction_depth == 0:
            self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def init_schema(self) -> None:
        sql = self.schema_path.read_text(encoding="utf-8")
        with self.conn.cursor() as cur:
            cur.execute(sql)
        self._commit_if_needed()

    def seed_sources(self) -> None:
        columns = [
            "source_id", "source_name", "source_type", "authority_level",
            "market", "provider", "base_url", "access_method",
            "update_frequency", "license_note", "rate_limit_note"
        ]
        placeholders = ",".join(["%s"] * len(columns))
        updates = ", ".join([f"{col}=EXCLUDED.{col}" for col in columns if col != "source_id"])
        sql = f"""
        INSERT INTO source_registry ({','.join(columns)}) VALUES ({placeholders})
        ON CONFLICT (source_id) DO UPDATE SET {updates}
        """
        with self.conn.cursor() as cur:
            cur.executemany(sql, [[row.get(col) for col in columns] for row in SOURCE_REGISTRY_SEED])
        self._commit_if_needed()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        try:
            with self.conn.cursor() as cur:
                cur.execute(self._sql(sql), tuple(params))
            if self._transaction_depth == 0:
                self._commit_if_needed()
        except Exception:
            if self._transaction_depth == 0:
                self.conn.rollback()
            raise

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self._transaction_depth:
            self._transaction_depth += 1
            try:
                yield
            finally:
                self._transaction_depth -= 1
            return
        # psycopg starts an implicit transaction even for SELECT. End that
        # read transaction so this context owns the real top-level commit.
        self.conn.commit()
        self._transaction_depth = 1
        try:
            with self.conn.transaction():
                yield
        finally:
            self._transaction_depth = 0

    def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[Any]:
        with self.conn.cursor() as cur:
            cur.execute(self._sql(sql), tuple(params))
            return list(cur.fetchall())

    def fetchone(self, sql: str, params: Iterable[Any] = ()) -> Any | None:
        with self.conn.cursor() as cur:
            cur.execute(self._sql(sql), tuple(params))
            return cur.fetchone()

    def insert_job(self, job: dict[str, Any]) -> None:
        from psycopg.types.json import Jsonb
        columns = ["job_id", "source_id", "job_type", "target_scope", "start_time", "end_time", "status", "records_found", "records_saved", "error_message", "config"]
        values = [Jsonb(job.get(col)) if col in {"target_scope", "config"} else job.get(col) for col in columns]
        updates = ", ".join([f"{col}=EXCLUDED.{col}" for col in columns if col != "job_id"])
        sql = f"INSERT INTO ingestion_jobs ({','.join(columns)}) VALUES ({','.join(['%s'] * len(columns))}) ON CONFLICT (job_id) DO UPDATE SET {updates}"
        with self.conn.cursor() as cur:
            cur.execute(sql, values)
        self._commit_if_needed()

    def update_job(self, job_id: str, **fields: Any) -> None:
        from psycopg.types.json import Jsonb
        assignments = []
        values: list[Any] = []
        for key, value in fields.items():
            assignments.append(f"{key} = %s")
            values.append(Jsonb(value) if key in {"target_scope", "config"} else value)
        values.append(job_id)
        with self.conn.cursor() as cur:
            cur.execute(f"UPDATE ingestion_jobs SET {', '.join(assignments)} WHERE job_id = %s", values)
        self._commit_if_needed()

    def find_raw_object(
        self,
        source_id: str,
        original_url: str,
        content_sha256: str,
        include_statuses: tuple[str, ...] | None = ("passed",),
    ) -> Any | None:
        sql = "SELECT * FROM raw_objects WHERE source_id = ? AND original_url = ? AND content_sha256 = ?"
        params: list[Any] = [source_id, original_url, content_sha256]
        if include_statuses is not None:
            if not include_statuses:
                return None
            sql += f" AND validation_status IN ({','.join('?' for _ in include_statuses)})"
            params.extend(include_statuses)
        return self.fetchone(sql, params)

    def find_existing_passed_object(self, source_id: str, original_url: str, content_sha256: str) -> Any | None:
        return self.find_raw_object(source_id, original_url, content_sha256, include_statuses=("passed",))

    def find_any_existing_object(self, source_id: str, original_url: str, content_sha256: str) -> Any | None:
        return self.find_raw_object(source_id, original_url, content_sha256, include_statuses=None)

    def insert_raw_object(self, obj: dict[str, Any]) -> None:
        from psycopg.types.json import Jsonb
        columns = ["raw_object_id", "source_id", "job_id", "object_type", "storage_uri", "original_url", "request_params", "response_headers", "response_status", "content_sha256", "content_size_bytes", "compression", "retrieval_time", "source_publish_date", "source_update_time", "parse_status", "validation_status", "notes"]
        values = [Jsonb(obj.get(col) or {}) if col in {"request_params", "response_headers"} else obj.get(col) for col in columns]
        updates = ", ".join([f"{col}=EXCLUDED.{col}" for col in columns if col != "raw_object_id"])
        sql = f"INSERT INTO raw_objects ({','.join(columns)}) VALUES ({','.join(['%s'] * len(columns))}) ON CONFLICT (raw_object_id) DO UPDATE SET {updates}"
        with self.conn.cursor() as cur:
            cur.execute(sql, values)
        self._commit_if_needed()

    def insert_raw_records(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        from psycopg.types.json import Jsonb
        columns = ["raw_record_id", "raw_object_id", "source_id", "record_key", "record_type", "record_json", "entity_hint", "metric_hint", "period_hint"]
        values = [[Jsonb(row.get(col)) if col == "record_json" else row.get(col) for col in columns] for row in records]
        updates = ", ".join([f"{col}=EXCLUDED.{col}" for col in columns if col != "raw_record_id"])
        sql = f"INSERT INTO raw_records ({','.join(columns)}) VALUES ({','.join(['%s'] * len(columns))}) ON CONFLICT (raw_record_id) DO UPDATE SET {updates}"
        with self.conn.cursor() as cur:
            cur.executemany(sql, values)
        self._commit_if_needed()


    def insert_atomic_facts(self, facts: list[dict[str, Any]]) -> None:
        if not facts:
            return
        columns = ["fact_id", "stable_fact_id", "build_id", "raw_snapshot_id", "is_active", "superseded_by", "entity_id", "metric_id", "value", "value_type", "unit", "currency", "period_start", "period_end", "fiscal_year", "fiscal_quarter", "as_of_date", "report_date", "source_id", "raw_object_id", "source_field_name", "source_page_or_table", "extraction_method", "confidence_score", "verification_status", "tolerance", "notes"]
        updates = ", ".join([f"{col}=EXCLUDED.{col}" for col in columns if col != "fact_id"])
        sql = f"INSERT INTO atomic_facts ({','.join(columns)}) VALUES ({','.join(['%s'] * len(columns))}) ON CONFLICT (fact_id) DO UPDATE SET {updates}"
        values = [[_row_value(row, col) for col in columns] for row in facts]
        with self.conn.cursor() as cur:
            cur.executemany(sql, values)
        self._commit_if_needed()


    def insert_standardized_facts(self, facts: list[dict[str, Any]]) -> None:
        if not facts:
            return
        from psycopg.types.json import Jsonb
        columns = ["fact_id", "stable_fact_id", "build_id", "raw_snapshot_id", "is_active", "superseded_by", "entity_id", "entity_scope_id", "financial_scope_type", "metric_id", "normalized_value", "normalized_unit", "normalized_currency", "value_scale", "period_start", "period_end", "calendar_year", "fiscal_year", "fiscal_quarter", "time_basis", "metric_period_type", "source_definition_id", "frequency", "seasonal_adjustment", "vintage_policy", "is_forecast", "comparability_level", "as_of_date", "report_date", "source_id", "raw_object_id", "verification_status", "validation_flags", "conflict_group_id", "raw_equivalence_group_id", "semantic_equivalence_group_id", "confidence_score", "notes"]
        updates = ", ".join([f"{col}=EXCLUDED.{col}" for col in columns if col != "fact_id"])
        sql = f"INSERT INTO standardized_facts ({','.join(columns)}) VALUES ({','.join(['%s'] * len(columns))}) ON CONFLICT (fact_id) DO UPDATE SET {updates}"
        values = [[Jsonb(_row_value(row, col) or []) if col == "validation_flags" else _row_value(row, col) for col in columns] for row in facts]
        with self.conn.cursor() as cur:
            cur.executemany(sql, values)
        self._commit_if_needed()

    def insert_fact_quality_checks(self, checks: list[dict[str, Any]]) -> None:
        if not checks:
            return
        columns = ["check_id", "fact_id", "build_id", "is_active", "superseded_by", "check_type", "status", "severity", "message"]
        updates = ", ".join([f"{col}=EXCLUDED.{col}" for col in columns if col != "check_id"])
        sql = f"INSERT INTO fact_quality_checks ({','.join(columns)}) VALUES ({','.join(['%s'] * len(columns))}) ON CONFLICT (check_id) DO UPDATE SET {updates}"
        values = [[_row_value(row, col) for col in columns] for row in checks]
        with self.conn.cursor() as cur:
            cur.executemany(sql, values)
        self._commit_if_needed()


    def update_standardized_fact_statuses(self, updates: list[dict[str, Any]], only_flags: bool = False) -> None:
        if not updates:
            return
        from psycopg.types.json import Jsonb
        with self.conn.cursor() as cur:
            if only_flags:
                values = [(Jsonb(row.get("validation_flags") or []), row.get("fact_id")) for row in updates]
                cur.executemany("UPDATE standardized_facts SET validation_flags = %s WHERE fact_id = %s", values)
            else:
                values = [
                    (row.get("verification_status"), Jsonb(row.get("validation_flags") or []), row.get("conflict_group_id"), row.get("fact_id"))
                    for row in updates
                ]
                cur.executemany(
                    "UPDATE standardized_facts SET verification_status = %s, validation_flags = %s, conflict_group_id = %s WHERE fact_id = %s",
                    values,
                )
        self._commit_if_needed()

    def update_standardized_graph_ready(self, updates: list[dict[str, Any]]) -> None:
        if not updates:
            return
        values = [(row.get("graph_ready"), row.get("graph_ready_reason"), row.get("fact_id")) for row in updates]
        with self.conn.cursor() as cur:
            cur.executemany("UPDATE standardized_facts SET graph_ready = %s, graph_ready_reason = %s WHERE fact_id = %s", values)
        self._commit_if_needed()

    def sync_atomic_fact_verification_status(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE atomic_facts af
                SET verification_status = sf.verification_status
                FROM standardized_facts sf
                WHERE sf.fact_id = af.fact_id
                  AND COALESCE(sf.is_active, 1) = 1
                  AND COALESCE(af.is_active, 1) = 1
                """
            )
        self._commit_if_needed()

    def insert_derived_facts(self, facts: list[dict[str, Any]]) -> None:
        if not facts:
            return
        from psycopg.types.json import Jsonb
        columns = ["derived_id", "stable_derived_id", "build_id", "input_build_id", "is_active", "superseded_by", "derived_type", "input_fact_ids", "entity_scope", "metric_scope", "time_scope", "scope_type", "scope_id", "scope_definition", "scope_entity_ids", "scope_source", "calculation_code", "output_value", "output_table", "unit", "tolerance", "verification_status"]
        json_columns = {"input_fact_ids", "entity_scope", "metric_scope", "time_scope", "scope_entity_ids", "output_table"}
        updates = ", ".join([f"{col}=EXCLUDED.{col}" for col in columns if col != "derived_id"])
        sql = f"INSERT INTO derived_facts ({','.join(columns)}) VALUES ({','.join(['%s'] * len(columns))}) ON CONFLICT (derived_id) DO UPDATE SET {updates}"
        values = [[Jsonb(_row_value(row, col) if _row_value(row, col) is not None else ([] if col in {'input_fact_ids', 'output_table', 'scope_entity_ids'} else {})) if col in json_columns else _row_value(row, col) for col in columns] for row in facts]
        with self.conn.cursor() as cur:
            cur.executemany(sql, values)
        self._commit_if_needed()


    def upsert_source_entity(self, *, source_id: str, source_code: str, source_name: str | None = None,
                             aliases: list[str] | None = None, market: str | None = None,
                             raw_metadata: dict[str, Any] | None = None) -> None:
        from psycopg.types.json import Jsonb
        entity_id = f"{source_id}:{source_code}"
        existing = self.fetchone("SELECT first_seen_at FROM source_entities WHERE source_entity_id = ?", (entity_id,))
        first_seen_at = existing["first_seen_at"] if existing else utc_now()
        sql = """
        INSERT INTO source_entities (source_entity_id, source_id, source_code, source_name, aliases, market, raw_metadata, first_seen_at, last_seen_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_entity_id) DO UPDATE SET
            source_name=EXCLUDED.source_name,
            aliases=EXCLUDED.aliases,
            market=EXCLUDED.market,
            raw_metadata=EXCLUDED.raw_metadata,
            last_seen_at=EXCLUDED.last_seen_at
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (entity_id, source_id, source_code, source_name, aliases or [], market, Jsonb(raw_metadata or {}), first_seen_at, utc_now()))
        self._commit_if_needed()

    def insert_snapshot(self, snapshot: dict[str, Any]) -> None:
        columns = ["snapshot_id", "source_id", "snapshot_date", "storage_prefix", "object_count", "total_size_bytes", "manifest_uri", "checksum_uri"]
        updates = ", ".join([f"{col}=EXCLUDED.{col}" for col in columns if col != "snapshot_id"])
        sql = f"INSERT INTO raw_dataset_snapshots ({','.join(columns)}) VALUES ({','.join(['%s'] * len(columns))}) ON CONFLICT (snapshot_id) DO UPDATE SET {updates}"
        with self.conn.cursor() as cur:
            cur.execute(sql, [snapshot.get(col) for col in columns])
        self._commit_if_needed()

    @staticmethod
    def _sql(sql: str) -> str:
        return sql.replace("?", "%s")


def create_metadata_db(config: dict[str, Any]) -> DBProtocol:
    backend = config.get("metadata_backend", {}).get("type", "sqlite")
    if backend == "postgres":
        dsn = os.environ.get("DATABASE_URL") or config.get("metadata_backend", {}).get("dsn")
        if not dsn:
            raise RuntimeError("PostgreSQL backend selected but DATABASE_URL or metadata_backend.dsn is not set")
        schema_path = config.get("metadata_backend", {}).get("postgres_schema", "sql/postgres_schema.sql")
        return PostgresMetadataDB(dsn, schema_path=schema_path)
    return MetadataDB(config["metadata_db"])


def _row_value(row: dict[str, Any], column: str) -> Any:
    value = row.get(column)
    if column == "is_active":
        return 1 if value is None else value
    if isinstance(value, Decimal):
        return str(value)
    return value
