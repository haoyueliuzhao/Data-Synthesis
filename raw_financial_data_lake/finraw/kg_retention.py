from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from finraw.db.client import DBProtocol

KG_RETENTION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS kg_archives (
    archive_id          TEXT PRIMARY KEY,
    kg_build_id         TEXT NOT NULL REFERENCES kg_builds(kg_build_id),
    archive_uri         TEXT NOT NULL,
    archive_format      TEXT NOT NULL,
    compression         TEXT,
    node_count          INTEGER,
    edge_count          INTEGER,
    quality_check_count INTEGER,
    node_sha256         TEXT,
    edge_sha256         TEXT,
    quality_sha256      TEXT,
    manifest_sha256     TEXT,
    status              TEXT NOT NULL,
    created_at          TEXT,
    verified_at         TEXT,
    purged_at           TEXT,
    notes               TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_kg_archives_build
    ON kg_archives(kg_build_id);
CREATE INDEX IF NOT EXISTS idx_kg_archives_status
    ON kg_archives(status, created_at);
"""


def ensure_kg_retention_schema(db: DBProtocol) -> None:
    for statement in KG_RETENTION_SCHEMA_SQL.split(";"):
        sql = statement.strip()
        if sql:
            db.execute(sql)


def plan_kg_retention(
    db: DBProtocol,
    hot_build_count: int = 2,
    preserve_build_ids: Iterable[str] = (),
) -> dict[str, Any]:
    ensure_kg_retention_schema(db)
    if hot_build_count < 1:
        raise ValueError("hot_build_count must be at least 1")
    builds = [
        dict(row)
        for row in db.fetchall(
            """
            SELECT b.*,
                   (SELECT COUNT(*) FROM kg_nodes n WHERE n.kg_build_id = b.kg_build_id) AS actual_node_count,
                   (SELECT COUNT(*) FROM kg_edges e WHERE e.kg_build_id = b.kg_build_id) AS actual_edge_count
            FROM kg_builds b
            ORDER BY COALESCE(b.completed_at, b.started_at) DESC, b.started_at DESC
            """
        )
    ]
    valid = [
        row
        for row in builds
        if row.get("status") == "success"
        and row.get("quality_status") == "passed"
        and int(row.get("actual_node_count") or 0) > 0
    ]
    preserved = {str(build_id) for build_id in preserve_build_ids if build_id}
    hot_ids = {row["kg_build_id"] for row in valid[:hot_build_count]}
    hot_ids.update(row["kg_build_id"] for row in builds if int(row.get("is_active") or 0) == 1)
    hot_ids.update(preserved)
    known_ids = {str(row["kg_build_id"]) for row in builds}
    archive_candidates = [
        row
        for row in builds
        if row["kg_build_id"] not in hot_ids
        and (int(row.get("actual_node_count") or 0) > 0 or int(row.get("actual_edge_count") or 0) > 0)
    ]
    empty_builds = [
        row
        for row in builds
        if row["kg_build_id"] not in hot_ids
        and row.get("status") not in {"archived", "archived_partial"}
        and int(row.get("actual_node_count") or 0) == 0
        and int(row.get("actual_edge_count") or 0) == 0
    ]
    return {
        "hot_build_count": hot_build_count,
        "hot_build_ids": sorted(hot_ids),
        "explicitly_preserved_build_ids": sorted(preserved),
        "unknown_preserved_build_ids": sorted(preserved - known_ids),
        "hot_builds": [row for row in builds if row["kg_build_id"] in hot_ids],
        "archive_candidates": archive_candidates,
        "empty_non_hot_builds": empty_builds,
        "archive_candidate_node_count": sum(int(row.get("actual_node_count") or 0) for row in archive_candidates),
        "archive_candidate_edge_count": sum(int(row.get("actual_edge_count") or 0) for row in archive_candidates),
    }


def enforce_kg_retention(
    db: DBProtocol,
    archive_dir: str,
    *,
    hot_build_count: int = 2,
    preserve_build_ids: Iterable[str] = (),
    execute: bool = False,
    purge: bool = False,
    vacuum: bool = False,
    output_dir: str | None = None,
    batch_size: int = 100_000,
) -> dict[str, Any]:
    plan = plan_kg_retention(
        db,
        hot_build_count=hot_build_count,
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
        "empty_build_ids": [row["kg_build_id"] for row in plan["empty_non_hot_builds"]],
    }
    if not execute:
        if output_dir:
            report["written_files"] = [str(path) for path in write_retention_report(report, output_dir)]
        return report

    for build in plan["archive_candidates"]:
        archived = archive_kg_build(
            db,
            build["kg_build_id"],
            archive_dir,
            batch_size=batch_size,
        )
        report["archives"].append(archived)
        if purge:
            _purge_archived_build(db, build["kg_build_id"], archived["archive_id"])
            report["purged_build_ids"].append(build["kg_build_id"])

    for build in plan["empty_non_hot_builds"]:
        if build.get("status") in {"running", "superseded"} and not build.get("completed_at"):
            db.execute(
                "UPDATE kg_builds SET status = ?, quality_status = ?, completed_at = ?, is_active = 0 WHERE kg_build_id = ?",
                ("failed_incomplete", "failed", _now(), build["kg_build_id"]),
            )

    if purge and vacuum and report["purged_build_ids"]:
        _vacuum_graph_tables(db)

    final_plan = plan_kg_retention(
        db,
        hot_build_count=hot_build_count,
        preserve_build_ids=preserve_build_ids,
    )
    report["post_retention"] = final_plan
    if output_dir:
        report["written_files"] = [str(path) for path in write_retention_report(report, output_dir)]
    return report


def archive_kg_build(
    db: DBProtocol,
    kg_build_id: str,
    archive_dir: str,
    *,
    batch_size: int = 100_000,
) -> dict[str, Any]:
    ensure_kg_retention_schema(db)
    build_row = db.fetchone("SELECT * FROM kg_builds WHERE kg_build_id = ?", (kg_build_id,))
    if not build_row:
        raise RuntimeError(f"Unknown KG build: {kg_build_id}")
    build = dict(build_row)
    if int(build.get("is_active") or 0) == 1:
        raise RuntimeError(f"Refusing to archive active KG build: {kg_build_id}")

    out = Path(archive_dir).resolve() / f"kg_build_id={kg_build_id}"
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for table in ("kg_nodes", "kg_edges", "kg_quality_checks"):
        path = out / f"{table}.parquet"
        count = _archive_table_parquet(
            db,
            table,
            "kg_build_id = ?",
            (kg_build_id,),
            path,
            batch_size=batch_size,
        )
        files[table] = {
            "path": str(path),
            "row_count": count,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }

    manifest = {
        "archive_version": "1.0",
        "kg_build_id": kg_build_id,
        "created_at": _now(),
        "format": "parquet",
        "compression": "zstd",
        "build": build,
        "files": files,
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    manifest_sha256 = _sha256_file(manifest_path)
    _verify_archive(manifest)

    archive_id = "kgarchive_" + hashlib.sha1(
        f"{kg_build_id}|{manifest_sha256}".encode("utf-8")
    ).hexdigest()[:24]
    row = {
        "archive_id": archive_id,
        "kg_build_id": kg_build_id,
        "archive_uri": str(out),
        "archive_format": "parquet",
        "compression": "zstd",
        "node_count": files["kg_nodes"]["row_count"],
        "edge_count": files["kg_edges"]["row_count"],
        "quality_check_count": files["kg_quality_checks"]["row_count"],
        "node_sha256": files["kg_nodes"]["sha256"],
        "edge_sha256": files["kg_edges"]["sha256"],
        "quality_sha256": files["kg_quality_checks"]["sha256"],
        "manifest_sha256": manifest_sha256,
        "status": "verified",
        "created_at": manifest["created_at"],
        "verified_at": _now(),
        "purged_at": None,
        "notes": json.dumps({"manifest": str(manifest_path)}, sort_keys=True),
    }
    _upsert_archive(db, row)
    return {**row, "manifest_path": str(manifest_path), "files": files}


def write_retention_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "kg_retention_report.json"
    md_path = out / "kg_retention_report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# KG Retention Report",
        "",
        f"- Execute: {report.get('execute')}",
        f"- Purge: {report.get('purge')}",
        f"- Hot build count: {report.get('hot_build_count')}",
        f"- Hot builds: {', '.join(report.get('hot_build_ids') or [])}",
        f"- Candidate nodes: {report.get('archive_candidate_node_count', 0)}",
        f"- Candidate edges: {report.get('archive_candidate_edge_count', 0)}",
        f"- Purged builds: {', '.join(report.get('purged_build_ids') or []) or 'none'}",
        "",
        "## Archive Candidates",
        "",
    ]
    candidates = report.get("archive_candidates") or []
    if candidates:
        for row in candidates:
            lines.append(
                f"- {row.get('kg_build_id')}: status={row.get('status')}, "
                f"nodes={row.get('actual_node_count')}, edges={row.get('actual_edge_count')}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Archives", ""])
    archives = report.get("archives") or []
    if archives:
        for row in archives:
            lines.append(
                f"- {row.get('kg_build_id')}: {row.get('archive_uri')} "
                f"(nodes={row.get('node_count')}, edges={row.get('edge_count')}, status={row.get('status')})"
            )
    else:
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
            arrow_table = pa.Table.from_pylist(normalized, schema=arrow_schema)
            if writer is None:
                arrow_schema = arrow_table.schema
                writer = pq.ParquetWriter(
                    temp_path,
                    arrow_schema,
                    compression="zstd",
                    use_dictionary=True,
                )
            writer.write_table(arrow_table)
            count += len(normalized)
        if writer is None:
            arrow_table = pa.table({"kg_build_id": pa.array([], type=pa.string())})
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
        cursor_name = "kg_archive_" + hashlib.sha1(sql.encode("utf-8")).hexdigest()[:10]
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


def _archive_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return value


def _verify_archive(manifest: dict[str, Any]) -> None:
    import pyarrow.parquet as pq

    for item in manifest["files"].values():
        path = Path(item["path"])
        if not path.exists():
            raise RuntimeError(f"Archive file missing: {path}")
        metadata = pq.read_metadata(path)
        if metadata.num_rows != item["row_count"]:
            raise RuntimeError(
                f"Archive row-count mismatch for {path}: "
                f"{metadata.num_rows} != {item['row_count']}"
            )
        if _sha256_file(path) != item["sha256"]:
            raise RuntimeError(f"Archive checksum mismatch: {path}")


def _purge_archived_build(db: DBProtocol, kg_build_id: str, archive_id: str) -> None:
    archive = db.fetchone(
        "SELECT * FROM kg_archives WHERE archive_id = ? AND kg_build_id = ?",
        (archive_id, kg_build_id),
    )
    if not archive or dict(archive).get("status") != "verified":
        raise RuntimeError(f"KG archive is not verified: {kg_build_id}")
    build = db.fetchone("SELECT is_active FROM kg_builds WHERE kg_build_id = ?", (kg_build_id,))
    if not build or int(dict(build).get("is_active") or 0) == 1:
        raise RuntimeError(f"Refusing to purge active or unknown KG build: {kg_build_id}")
    db.execute("DELETE FROM kg_edges WHERE kg_build_id = ?", (kg_build_id,))
    db.execute("DELETE FROM kg_nodes WHERE kg_build_id = ?", (kg_build_id,))
    purged_at = _now()
    db.execute(
        "UPDATE kg_archives SET status = ?, purged_at = ? WHERE archive_id = ?",
        ("purged", purged_at, archive_id),
    )
    db.execute(
        "UPDATE kg_builds SET status = ?, notes = COALESCE(notes, '') || ? WHERE kg_build_id = ?",
        ("archived", f"; cold archive={dict(archive).get('archive_uri')}", kg_build_id),
    )


def _upsert_archive(db: DBProtocol, row: dict[str, Any]) -> None:
    columns = list(row)
    values = [row[column] for column in columns]
    if db.__class__.__name__ == "PostgresMetadataDB":
        placeholders = ",".join(["%s"] * len(columns))
        updates = ", ".join(
            f"{column}=EXCLUDED.{column}" for column in columns if column != "archive_id"
        )
        sql = (
            f"INSERT INTO kg_archives ({','.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT (archive_id) DO UPDATE SET {updates}"
        )
        with db.conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(sql, values)
        db.conn.commit()  # type: ignore[attr-defined]
    else:
        placeholders = ",".join(["?"] * len(columns))
        db.conn.execute(  # type: ignore[attr-defined]
            f"INSERT OR REPLACE INTO kg_archives ({','.join(columns)}) VALUES ({placeholders})",
            values,
        )
        db.conn.commit()  # type: ignore[attr-defined]


def _vacuum_graph_tables(db: DBProtocol) -> None:
    if db.__class__.__name__ == "PostgresMetadataDB":
        db.conn.commit()  # type: ignore[attr-defined]
        db.conn.autocommit = True  # type: ignore[attr-defined]
        try:
            with db.conn.cursor() as cur:  # type: ignore[attr-defined]
                cur.execute("VACUUM (ANALYZE) kg_nodes")
                cur.execute("VACUUM (ANALYZE) kg_edges")
        finally:
            db.conn.autocommit = False  # type: ignore[attr-defined]
    else:
        db.execute("VACUUM")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
