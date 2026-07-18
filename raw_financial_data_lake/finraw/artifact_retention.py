from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from finraw.db.client import DBProtocol
from finraw.qa_retention import ensure_qa_retention_schema


def plan_artifact_retention(
    db: DBProtocol,
    *,
    qa_export_roots: Iterable[str],
    metadata_jsonl_dir: str | None = None,
    metadata_parquet_dir: str | None = None,
) -> dict[str, Any]:
    ensure_qa_retention_schema(db)
    active_qa_ids = {
        str(row["qa_build_id"])
        for row in db.fetchall(
            "SELECT qa_build_id FROM qa_builds WHERE is_active = ?", (True,)
        )
    }
    cold_qa = {
        str(row["qa_build_id"]): dict(row)
        for row in db.fetchall(
            "SELECT qa_build_id, archive_uri, manifest_sha256, status "
            "FROM qa_archives WHERE status = ?",
            ("purged",),
        )
    }
    qa_candidates: list[dict[str, Any]] = []
    qa_protected: list[dict[str, Any]] = []
    qa_blocked: list[dict[str, Any]] = []
    for root_value in qa_export_roots:
        root = Path(root_value).resolve()
        if not root.exists():
            continue
        for path in sorted(root.glob("qa_build_*")):
            if not path.is_dir():
                continue
            build_id = path.name
            inventory = _inventory_tree(path)
            row = {
                "qa_build_id": build_id,
                "path": str(path),
                "size_bytes": inventory["size_bytes"],
                "file_count": inventory["file_count"],
                "tree_sha256": inventory["tree_sha256"],
                "files": inventory["files"],
            }
            if build_id in active_qa_ids:
                qa_protected.append({**row, "reason": "active_qa_build"})
            elif build_id in cold_qa:
                archive = cold_qa[build_id]
                qa_candidates.append(
                    {
                        **row,
                        "reason": "qa_build_cold_archived",
                        "archive_uri": archive.get("archive_uri"),
                        "archive_manifest_sha256": archive.get("manifest_sha256"),
                    }
                )
            else:
                qa_blocked.append({**row, "reason": "qa_build_not_cold_archived"})

    redundant_jsonl: list[dict[str, Any]] = []
    blocked_jsonl: list[dict[str, Any]] = []
    if metadata_jsonl_dir and metadata_parquet_dir:
        jsonl_root = Path(metadata_jsonl_dir).resolve()
        parquet_root = Path(metadata_parquet_dir).resolve()
        if jsonl_root.exists() and parquet_root.exists():
            for jsonl_path in sorted(jsonl_root.glob("*.jsonl")):
                parquet_path = parquet_root / f"{jsonl_path.stem}.parquet"
                row = _jsonl_parquet_pair(jsonl_path, parquet_path)
                if row["verification_status"] == "matched":
                    redundant_jsonl.append(row)
                else:
                    blocked_jsonl.append(row)

    return {
        "active_qa_build_ids": sorted(active_qa_ids),
        "qa_export_candidates": qa_candidates,
        "qa_export_protected": qa_protected,
        "qa_export_blocked": qa_blocked,
        "redundant_jsonl_candidates": redundant_jsonl,
        "redundant_jsonl_blocked": blocked_jsonl,
        "candidate_qa_export_bytes": _sum_bytes(qa_candidates),
        "candidate_jsonl_bytes": _sum_bytes(redundant_jsonl),
        "candidate_total_bytes": _sum_bytes(qa_candidates)
        + _sum_bytes(redundant_jsonl),
    }


def enforce_artifact_retention(
    db: DBProtocol,
    *,
    qa_export_roots: Iterable[str],
    metadata_jsonl_dir: str | None = None,
    metadata_parquet_dir: str | None = None,
    output_dir: str,
    execute: bool = False,
) -> dict[str, Any]:
    report = {
        **plan_artifact_retention(
            db,
            qa_export_roots=qa_export_roots,
            metadata_jsonl_dir=metadata_jsonl_dir,
            metadata_parquet_dir=metadata_parquet_dir,
        ),
        "execute": execute,
        "created_at": _now(),
        "deleted_qa_exports": [],
        "deleted_jsonl_files": [],
        "released_bytes": 0,
    }
    written = write_artifact_retention_report(report, output_dir, suffix="plan")
    if not execute:
        report["written_files"] = [str(path) for path in written]
        return report

    for row in report["qa_export_candidates"]:
        path = Path(row["path"])
        _delete_tree(path)
        report["deleted_qa_exports"].append(str(path))
        report["released_bytes"] += int(row["size_bytes"])
    for row in report["redundant_jsonl_candidates"]:
        path = Path(row["jsonl_path"])
        path.unlink()
        report["deleted_jsonl_files"].append(str(path))
        report["released_bytes"] += int(row["size_bytes"])
    report["completed_at"] = _now()
    written = write_artifact_retention_report(report, output_dir, suffix="result")
    report["written_files"] = [str(path) for path in written]
    return report


def write_artifact_retention_report(
    report: dict[str, Any], output_dir: str, *, suffix: str
) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / f"artifact_retention_{suffix}.json"
    md_path = out / f"artifact_retention_{suffix}.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Artifact Retention Report",
        "",
        f"- Execute: {report.get('execute')}",
        f"- Candidate bytes: {report.get('candidate_total_bytes', 0)}",
        f"- Released bytes: {report.get('released_bytes', 0)}",
        f"- QA exports: {len(report.get('qa_export_candidates') or [])}",
        f"- Redundant JSONL: {len(report.get('redundant_jsonl_candidates') or [])}",
        f"- Protected QA exports: {len(report.get('qa_export_protected') or [])}",
        f"- Blocked artifacts: {len(report.get('qa_export_blocked') or []) + len(report.get('redundant_jsonl_blocked') or [])}",
        "",
        "## QA Export Candidates",
        "",
    ]
    for row in report.get("qa_export_candidates") or []:
        lines.append(
            f"- {row['qa_build_id']}: {row['size_bytes']} bytes, "
            f"archive={row.get('archive_uri')}"
        )
    if not report.get("qa_export_candidates"):
        lines.append("- none")
    lines.extend(["", "## Redundant JSONL", ""])
    for row in report.get("redundant_jsonl_candidates") or []:
        lines.append(
            f"- {row['jsonl_path']}: {row['jsonl_rows']} rows, "
            f"parquet={row['parquet_path']}"
        )
    if not report.get("redundant_jsonl_candidates"):
        lines.append("- none")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return [json_path, md_path]


def _jsonl_parquet_pair(jsonl_path: Path, parquet_path: Path) -> dict[str, Any]:
    jsonl_rows, jsonl_sha256, jsonl_content_digest = _jsonl_signature(jsonl_path)
    base = {
        "jsonl_path": str(jsonl_path),
        "parquet_path": str(parquet_path),
        "size_bytes": jsonl_path.stat().st_size,
        "jsonl_rows": jsonl_rows,
        "jsonl_sha256": jsonl_sha256,
        "jsonl_content_digest": jsonl_content_digest,
    }
    if not parquet_path.exists():
        return {**base, "verification_status": "missing_parquet"}
    parquet_rows, parquet_content_digest = _parquet_signature(parquet_path)
    if jsonl_rows != parquet_rows:
        verification_status = "row_count_mismatch"
    elif jsonl_content_digest != parquet_content_digest:
        verification_status = "content_mismatch"
    else:
        verification_status = "matched"
    return {
        **base,
        "parquet_rows": parquet_rows,
        "parquet_size_bytes": parquet_path.stat().st_size,
        "parquet_sha256": _sha256_file(parquet_path),
        "parquet_content_digest": parquet_content_digest,
        "verification_status": verification_status,
    }


def _inventory_tree(root: Path) -> dict[str, Any]:
    files = []
    digest = hashlib.sha256()
    size_bytes = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        sha256 = _sha256_file(path)
        files.append({"path": relative, "size_bytes": size, "sha256": sha256})
        digest.update(f"{relative}\0{size}\0{sha256}\n".encode())
        size_bytes += size
    return {
        "file_count": len(files),
        "size_bytes": size_bytes,
        "tree_sha256": digest.hexdigest(),
        "files": files,
    }


def _delete_tree(root: Path) -> None:
    paths = list(root.rglob("*"))
    for path in (item for item in paths if item.is_file() or item.is_symlink()):
        path.unlink()
    directories = (item for item in paths if item.is_dir())
    for path in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        path.rmdir()
    root.rmdir()


def _jsonl_signature(path: Path) -> tuple[int, str, str]:
    file_digest = hashlib.sha256()
    row_digests = []
    with path.open("rb") as handle:
        for line in handle:
            file_digest.update(line)
            row = json.loads(line)
            row_digests.append(_canonical_row_hash(row))
    return len(row_digests), file_digest.hexdigest(), _multiset_digest(row_digests)


def _parquet_signature(path: Path) -> tuple[int, str]:
    import pyarrow.parquet as pq

    row_digests = []
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(batch_size=4096):
        for row in batch.to_pylist():
            row_digests.append(_canonical_row_hash(row))
    return len(row_digests), _multiset_digest(row_digests)


def _canonical_row_hash(row: dict[str, Any]) -> int:
    normalized = {
        key: (
            json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
            if isinstance(value, (dict, list, tuple))
            else value
        )
        for key, value in row.items()
    }
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return int.from_bytes(hashlib.sha256(encoded).digest(), "big")


def _multiset_digest(row_digests: Iterable[int]) -> str:
    modulus = 1 << 256
    total = 0
    squared_total = 0
    count = 0
    for value in row_digests:
        total = (total + value) % modulus
        squared_total = (squared_total + value * value) % modulus
        count += 1
    payload = f"{count}:{total:064x}:{squared_total:064x}".encode()
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sum_bytes(rows: Iterable[dict[str, Any]]) -> int:
    return sum(int(row.get("size_bytes") or 0) for row in rows)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
