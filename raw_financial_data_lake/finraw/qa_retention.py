from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from finraw.db.client import DBProtocol


QA_RETENTION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS qa_archives (
    archive_id          TEXT PRIMARY KEY,
    qa_build_id         TEXT NOT NULL REFERENCES qa_builds(qa_build_id),
    archive_uri         TEXT NOT NULL,
    archive_format      TEXT NOT NULL,
    compression         TEXT,
    candidate_count     BIGINT,
    sample_count        BIGINT,
    evidence_count      BIGINT,
    quality_check_count BIGINT,
    manifest_sha256     TEXT,
    status              TEXT NOT NULL,
    created_at          TEXT,
    verified_at         TEXT,
    purged_at           TEXT,
    notes               TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_qa_archives_build
    ON qa_archives(qa_build_id);
CREATE INDEX IF NOT EXISTS idx_qa_archives_status
    ON qa_archives(status, created_at);
"""


QA_BUILD_TABLES: tuple[tuple[str, str], ...] = (
    ("qa_builds", "qa_build_id = ?"),
    ("qa_pattern_compilations", "qa_build_id = ?"),
    ("qa_compiled_bindings", "qa_build_id = ?"),
    ("qa_candidates", "qa_build_id = ?"),
    ("qa_operation_plans", "qa_build_id = ?"),
    ("qa_samples", "qa_build_id = ?"),
    ("qa_distribution_labels", "qa_build_id = ?"),
    (
        "qa_evidence_paths",
        "qa_id IN (SELECT qa_id FROM qa_samples WHERE qa_build_id = ?)",
    ),
    ("qa_quality_checks", "qa_build_id = ?"),
)


def ensure_qa_retention_schema(db: DBProtocol) -> None:
    for statement in QA_RETENTION_SCHEMA_SQL.split(";"):
        sql = statement.strip()
        if sql:
            db.execute(sql)


def plan_qa_retention(
    db: DBProtocol,
    *,
    hot_build_count: int = 1,
    minimum_hot_sample_count: int = 100,
    preserve_build_ids: Iterable[str] = (),
) -> dict[str, Any]:
    ensure_qa_retention_schema(db)
    if hot_build_count < 0:
        raise ValueError("hot_build_count must be non-negative")
    if minimum_hot_sample_count < 0:
        raise ValueError("minimum_hot_sample_count must be non-negative")

    builds = [
        _build_summary(dict(row))
        for row in db.fetchall(
            """
            SELECT b.*,
                   (SELECT COUNT(*) FROM qa_candidates c
                    WHERE c.qa_build_id = b.qa_build_id) AS actual_candidate_count,
                   (SELECT COUNT(*) FROM qa_samples s
                    WHERE s.qa_build_id = b.qa_build_id) AS actual_sample_count,
                   (SELECT COUNT(*) FROM qa_evidence_paths e
                    JOIN qa_samples s ON s.qa_id = e.qa_id
                    WHERE s.qa_build_id = b.qa_build_id) AS actual_evidence_count,
                   (SELECT COUNT(*) FROM qa_quality_checks q
                    WHERE q.qa_build_id = b.qa_build_id) AS actual_quality_check_count,
                   (SELECT COUNT(*) FROM qa_operation_plans p
                    WHERE p.qa_build_id = b.qa_build_id) AS actual_plan_count,
                   (SELECT COUNT(*) FROM qa_pattern_compilations p
                    WHERE p.qa_build_id = b.qa_build_id) AS actual_compilation_count,
                   (SELECT COUNT(*) FROM qa_compiled_bindings p
                    WHERE p.qa_build_id = b.qa_build_id) AS actual_binding_count,
                   (SELECT status FROM qa_archives a
                    WHERE a.qa_build_id = b.qa_build_id) AS archive_status
            FROM qa_builds b
            ORDER BY COALESCE(b.completed_at, b.started_at) DESC, b.started_at DESC
            """
        )
    ]
    preserved = {str(build_id) for build_id in preserve_build_ids if build_id}
    active_ids = {
        str(row["qa_build_id"]) for row in builds if bool(row.get("is_active"))
    }
    eligible_hot = [
        row
        for row in builds
        if row.get("status") == "ready"
        and row.get("quality_status") == "passed"
        and int(row.get("actual_sample_count") or 0) >= minimum_hot_sample_count
    ]
    recent_ids = {str(row["qa_build_id"]) for row in eligible_hot[:hot_build_count]}
    hot_ids = active_ids | recent_ids | preserved
    known_ids = {str(row["qa_build_id"]) for row in builds}
    unknown_preserved_ids = sorted(preserved - known_ids)
    archive_candidates = [
        row
        for row in builds
        if str(row["qa_build_id"]) not in hot_ids
        and not (
            row.get("status") == "archived" and row.get("archive_status") == "purged"
        )
    ]
    already_cold = [
        row
        for row in builds
        if row.get("status") == "archived" and row.get("archive_status") == "purged"
    ]
    return {
        "hot_build_count": hot_build_count,
        "minimum_hot_sample_count": minimum_hot_sample_count,
        "hot_build_ids": sorted(hot_ids),
        "active_build_ids": sorted(active_ids),
        "recent_hot_build_ids": sorted(recent_ids),
        "explicitly_preserved_build_ids": sorted(preserved),
        "unknown_preserved_build_ids": unknown_preserved_ids,
        "hot_builds": [row for row in builds if str(row["qa_build_id"]) in hot_ids],
        "archive_candidates": archive_candidates,
        "already_cold_builds": already_cold,
        "archive_candidate_count": len(archive_candidates),
        "archive_candidate_candidate_count": _sum(
            archive_candidates, "actual_candidate_count"
        ),
        "archive_candidate_sample_count": _sum(
            archive_candidates, "actual_sample_count"
        ),
        "archive_candidate_evidence_count": _sum(
            archive_candidates, "actual_evidence_count"
        ),
        "archive_candidate_quality_check_count": _sum(
            archive_candidates, "actual_quality_check_count"
        ),
    }


def enforce_qa_retention(
    db: DBProtocol,
    archive_dir: str,
    *,
    hot_build_count: int = 1,
    minimum_hot_sample_count: int = 100,
    preserve_build_ids: Iterable[str] = (),
    execute: bool = False,
    purge: bool = False,
    vacuum: bool = False,
    output_dir: str | None = None,
    batch_size: int = 50_000,
) -> dict[str, Any]:
    plan = plan_qa_retention(
        db,
        hot_build_count=hot_build_count,
        minimum_hot_sample_count=minimum_hot_sample_count,
        preserve_build_ids=preserve_build_ids,
    )
    report: dict[str, Any] = {
        **plan,
        "execute": execute,
        "purge": purge,
        "vacuum": vacuum,
        "archive_dir": str(Path(archive_dir).resolve()),
        "archives": [],
        "purged_build_ids": [],
    }
    if not execute:
        if output_dir:
            report["written_files"] = [
                str(path) for path in write_qa_retention_report(report, output_dir)
            ]
        return report

    for build in plan["archive_candidates"]:
        archived = archive_qa_build(
            db,
            str(build["qa_build_id"]),
            archive_dir,
            batch_size=batch_size,
        )
        report["archives"].append(archived)
        if purge:
            _purge_archived_qa_build(
                db,
                str(build["qa_build_id"]),
                str(archived["archive_id"]),
            )
            report["purged_build_ids"].append(str(build["qa_build_id"]))

    if purge and vacuum and report["purged_build_ids"]:
        _vacuum_qa_tables(db)
    report["post_retention"] = plan_qa_retention(
        db,
        hot_build_count=hot_build_count,
        minimum_hot_sample_count=minimum_hot_sample_count,
        preserve_build_ids=preserve_build_ids,
    )
    if output_dir:
        report["written_files"] = [
            str(path) for path in write_qa_retention_report(report, output_dir)
        ]
    return report


def archive_qa_build(
    db: DBProtocol,
    qa_build_id: str,
    archive_dir: str,
    *,
    batch_size: int = 50_000,
) -> dict[str, Any]:
    ensure_qa_retention_schema(db)
    build_row = db.fetchone(
        "SELECT * FROM qa_builds WHERE qa_build_id = ?", (qa_build_id,)
    )
    if not build_row:
        raise RuntimeError(f"Unknown QA build: {qa_build_id}")
    build = dict(build_row)
    if bool(build.get("is_active")):
        raise RuntimeError(f"Refusing to archive active QA build: {qa_build_id}")

    out = Path(archive_dir).resolve() / f"qa_build_id={qa_build_id}"
    out.mkdir(parents=True, exist_ok=True)
    files: dict[str, dict[str, Any]] = {}
    for table, where_clause in QA_BUILD_TABLES:
        path = out / f"{table}.parquet"
        row_count = _archive_table_parquet(
            db,
            table,
            where_clause,
            (qa_build_id,),
            path,
            batch_size=batch_size,
        )
        files[table] = {
            "path": str(path),
            "row_count": row_count,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }

    manifest = {
        "archive_version": "1.0",
        "qa_build_id": qa_build_id,
        "created_at": _now(),
        "format": "parquet",
        "compression": "zstd",
        "column_encoding": "canonical_text_v1",
        "build": build,
        "files": files,
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    manifest_sha256 = _sha256_file(manifest_path)
    _verify_archive(manifest)

    archive_id = "qaarchive_" + hashlib.sha1(qa_build_id.encode()).hexdigest()[:24]
    row = {
        "archive_id": archive_id,
        "qa_build_id": qa_build_id,
        "archive_uri": str(out),
        "archive_format": "parquet",
        "compression": "zstd",
        "candidate_count": files["qa_candidates"]["row_count"],
        "sample_count": files["qa_samples"]["row_count"],
        "evidence_count": files["qa_evidence_paths"]["row_count"],
        "quality_check_count": files["qa_quality_checks"]["row_count"],
        "manifest_sha256": manifest_sha256,
        "status": "verified",
        "created_at": manifest["created_at"],
        "verified_at": _now(),
        "purged_at": None,
        "notes": json.dumps({"manifest": str(manifest_path)}, sort_keys=True),
    }
    _upsert_archive(db, row)
    return {**row, "manifest_path": str(manifest_path), "files": files}


def write_qa_retention_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "qa_retention_report.json"
    md_path = out / "qa_retention_report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    lines = [
        "# QA Retention Report",
        "",
        f"- Execute: {report.get('execute')}",
        f"- Purge: {report.get('purge')}",
        f"- Active builds: {', '.join(report.get('active_build_ids') or []) or 'none'}",
        f"- Hot builds: {', '.join(report.get('hot_build_ids') or []) or 'none'}",
        f"- Archive candidates: {report.get('archive_candidate_count', 0)}",
        f"- Candidate rows: {report.get('archive_candidate_candidate_count', 0)}",
        f"- Sample rows: {report.get('archive_candidate_sample_count', 0)}",
        f"- Evidence rows: {report.get('archive_candidate_evidence_count', 0)}",
        f"- Quality rows: {report.get('archive_candidate_quality_check_count', 0)}",
        f"- Purged builds: {', '.join(report.get('purged_build_ids') or []) or 'none'}",
        "",
        "## Archive Candidates",
        "",
    ]
    for row in report.get("archive_candidates") or []:
        lines.append(
            f"- {row.get('qa_build_id')}: status={row.get('status')}, "
            f"quality={row.get('quality_status')}, "
            f"candidates={row.get('actual_candidate_count')}, "
            f"samples={row.get('actual_sample_count')}"
        )
    if not report.get("archive_candidates"):
        lines.append("- none")
    lines.extend(["", "## Archives", ""])
    for row in report.get("archives") or []:
        lines.append(
            f"- {row.get('qa_build_id')}: {row.get('archive_uri')} "
            f"(samples={row.get('sample_count')}, status={row.get('status')})"
        )
    if not report.get("archives"):
        lines.append("- none")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return [json_path, md_path]


def _archive_table_parquet(
    db: DBProtocol,
    table: str,
    where_clause: str,
    params: Iterable[Any],
    path: Path,
    *,
    batch_size: int,
) -> int:
    import pyarrow as pa
    import pyarrow.parquet as pq

    temp_path = path.with_suffix(path.suffix + ".tmp")
    writer = None
    arrow_schema = None
    count = 0
    try:
        for rows in _iter_query_batches(
            db,
            f"SELECT * FROM {table} WHERE {where_clause}",
            params,
            batch_size,
        ):
            normalized = [
                {key: _archive_value(value) for key, value in dict(row).items()}
                for row in rows
            ]
            if writer is None:
                arrow_schema = pa.schema([(key, pa.string()) for key in normalized[0]])
                writer = pq.ParquetWriter(
                    temp_path,
                    arrow_schema,
                    compression="zstd",
                    use_dictionary=True,
                )
            arrow_table = pa.Table.from_pylist(normalized, schema=arrow_schema)
            writer.write_table(arrow_table)
            count += len(normalized)
        if writer is None:
            arrow_table = pa.table({"archive_empty": pa.array([], type=pa.string())})
            writer = pq.ParquetWriter(temp_path, arrow_table.schema, compression="zstd")
            writer.write_table(arrow_table)
    finally:
        if writer is not None:
            writer.close()
    temp_path.replace(path)
    return count


def _iter_query_batches(
    db: DBProtocol,
    sql: str,
    params: Iterable[Any],
    batch_size: int,
) -> Iterator[list[Any]]:
    if db.__class__.__name__ == "PostgresMetadataDB":
        identity = sql + "|" + "|".join(str(value) for value in params)
        cursor_name = "qa_archive_" + hashlib.sha1(identity.encode()).hexdigest()[:10]
        with db.conn.cursor(name=cursor_name) as cur:  # type: ignore[attr-defined]
            cur.execute(db._sql(sql), tuple(params))  # type: ignore[attr-defined]
            while True:
                rows = cur.fetchmany(batch_size)
                if not rows:
                    break
                yield list(rows)
        db.conn.commit()  # type: ignore[attr-defined]
        return
    rows = db.fetchall(sql, params)
    for offset in range(0, len(rows), batch_size):
        yield list(rows[offset : offset + batch_size])


def _archive_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (dict, list, tuple, bool, int, float)):
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
            allow_nan=False,
        )
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def _verify_archive(manifest: dict[str, Any]) -> None:
    import pyarrow.parquet as pq

    for item in manifest["files"].values():
        path = Path(item["path"])
        if not path.exists():
            raise RuntimeError(f"Archive file missing: {path}")
        if pq.read_metadata(path).num_rows != item["row_count"]:
            raise RuntimeError(f"Archive row-count mismatch: {path}")
        if _sha256_file(path) != item["sha256"]:
            raise RuntimeError(f"Archive checksum mismatch: {path}")


def _purge_archived_qa_build(db: DBProtocol, qa_build_id: str, archive_id: str) -> None:
    archive_row = db.fetchone(
        "SELECT * FROM qa_archives WHERE archive_id = ? AND qa_build_id = ?",
        (archive_id, qa_build_id),
    )
    if not archive_row or dict(archive_row).get("status") != "verified":
        raise RuntimeError(f"QA archive is not verified: {qa_build_id}")
    build_row = db.fetchone(
        "SELECT is_active FROM qa_builds WHERE qa_build_id = ?", (qa_build_id,)
    )
    if not build_row or bool(dict(build_row).get("is_active")):
        raise RuntimeError(
            f"Refusing to purge active or unknown QA build: {qa_build_id}"
        )

    with db.transaction():
        db.execute(
            "DELETE FROM qa_evidence_paths WHERE qa_id IN "
            "(SELECT qa_id FROM qa_samples WHERE qa_build_id = ?)",
            (qa_build_id,),
        )
        for table in (
            "qa_quality_checks",
            "qa_operation_plans",
            "qa_samples",
            "qa_candidates",
            "qa_compiled_bindings",
            "qa_pattern_compilations",
        ):
            db.execute(f"DELETE FROM {table} WHERE qa_build_id = ?", (qa_build_id,))
        purged_at = _now()
        db.execute(
            "UPDATE qa_archives SET status = ?, purged_at = ? WHERE archive_id = ?",
            ("purged", purged_at, archive_id),
        )
        db.execute(
            "UPDATE qa_builds SET status = ?, is_active = ? WHERE qa_build_id = ?",
            ("archived", False, qa_build_id),
        )


def _upsert_archive(db: DBProtocol, row: dict[str, Any]) -> None:
    columns = list(row)
    values = [row[column] for column in columns]
    if db.__class__.__name__ == "PostgresMetadataDB":
        placeholders = ",".join(["%s"] * len(columns))
        updates = ", ".join(
            f"{column}=EXCLUDED.{column}"
            for column in columns
            if column != "archive_id"
        )
        sql = (
            f"INSERT INTO qa_archives ({','.join(columns)}) "
            f"VALUES ({placeholders}) ON CONFLICT (archive_id) DO UPDATE SET {updates}"
        )
        with db.conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(sql, values)
        db.conn.commit()  # type: ignore[attr-defined]
        return
    placeholders = ",".join(["?"] * len(columns))
    db.conn.execute(  # type: ignore[attr-defined]
        f"INSERT OR REPLACE INTO qa_archives ({','.join(columns)}) "
        f"VALUES ({placeholders})",
        values,
    )
    db.conn.commit()  # type: ignore[attr-defined]


def _vacuum_qa_tables(db: DBProtocol) -> None:
    tables = [table for table, _ in QA_BUILD_TABLES if table != "qa_builds"]
    if db.__class__.__name__ == "PostgresMetadataDB":
        db.conn.commit()  # type: ignore[attr-defined]
        db.conn.autocommit = True  # type: ignore[attr-defined]
        try:
            with db.conn.cursor() as cur:  # type: ignore[attr-defined]
                for table in tables:
                    cur.execute(f"VACUUM (ANALYZE) {table}")
        finally:
            db.conn.autocommit = False  # type: ignore[attr-defined]
        return
    db.execute("VACUUM")


def _build_summary(row: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "qa_build_id",
        "kg_build_id",
        "mining_run_id",
        "pattern_catalog_release_id",
        "status",
        "quality_status",
        "is_active",
        "started_at",
        "completed_at",
        "candidate_count",
        "sample_count",
        "passed_count",
        "superseded_by",
        "actual_candidate_count",
        "actual_sample_count",
        "actual_evidence_count",
        "actual_quality_check_count",
        "actual_plan_count",
        "actual_compilation_count",
        "actual_binding_count",
        "archive_status",
    )
    return {field: row.get(field) for field in fields}


def _sum(rows: Iterable[dict[str, Any]], key: str) -> int:
    return sum(int(row.get(key) or 0) for row in rows)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
