from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from finraw.db.client import DBProtocol


PURGE_CONFIRMATION = "PURGE_GENERATED_QA"

# Child rows precede their logical parents so the same plan works for SQLite.
QA_GENERATED_TABLES: tuple[str, ...] = (
    "qa_empirical_model_trials",
    "qa_empirical_runs",
    "qa_quality_release_members",
    "qa_quality_releases",
    "qa_human_reviews",
    "qa_evaluation_items",
    "qa_judge_calls",
    "qa_evaluation_runs",
    "qa_perturbation_cases",
    "qa_distribution_labels",
    "qa_quality_checks",
    "qa_evidence_paths",
    "qa_operation_plans",
    "qa_samples",
    "qa_candidates",
    "qa_compiled_bindings",
    "qa_pattern_compilations",
    "qa_archives",
    "qa_pattern_catalog_entries",
    "qa_pattern_catalog_releases",
    "qa_graph_walk_observations",
    "qa_graph_motif_observations",
    "qa_pattern_proposals",
    "qa_pattern_mining_runs",
    "qa_builds",
)

QA_REGISTRY_TABLES: tuple[str, ...] = (
    "qa_templates",
    "qa_graph_patterns",
)

ANALYSIS_GENERATED_TABLES: tuple[str, ...] = (
    "analysis_quality_checks",
    "analysis_llm_calls",
    "analysis_samples",
    "analysis_claim_plans",
    "analysis_evidence_bundles",
    "analysis_candidates",
    "financial_signal_instances",
    "analysis_pattern_catalog_entries",
    "analysis_pattern_catalog_releases",
    "analysis_pattern_proposals",
    "analysis_builds",
)

ANALYSIS_REGISTRY_TABLES: tuple[str, ...] = (
    "financial_signal_specs",
    "analysis_patterns",
)

PROTECTED_UPSTREAM_TABLES: tuple[str, ...] = (
    "raw_objects",
    "standardized_facts",
    "derived_facts",
    "kg_builds",
    "kg_nodes",
    "kg_edges",
)

_AUDIT_PREFIXES = (
    "qa_",
    "analysis_",
    "finsearchcomp_alignment_",
    "finsearchcomp_gap_alignment_",
    "moonlight_",
)
_PROTECTED_AUDIT_PREFIXES = ("qa_ready",)


def default_qa_artifact_paths(
    project_root: str | Path,
    *,
    include_analysis: bool = True,
    include_audit: bool = True,
    exclude_paths: Iterable[str | Path] = (),
) -> list[Path]:
    root = Path(project_root).resolve()
    data = root / "data"
    candidates = [
        data / "qa_exports",
        data / "qa_exports_v2_smoke",
        data / "qa_archive",
        data / "layered_exports" / "qa_build",
    ]
    if include_analysis:
        candidates.extend(
            [
                data / "analysis_exports",
                data / "analysis_archive",
                data / "layered_exports" / "analysis_build",
            ]
        )
    if include_audit:
        audit = data / "audit"
        if audit.exists():
            candidates.extend(
                path
                for path in audit.iterdir()
                if path.name.startswith(_AUDIT_PREFIXES)
                and not path.name.startswith(_PROTECTED_AUDIT_PREFIXES)
                and (include_analysis or not path.name.startswith("analysis_"))
            )

    excluded = {Path(path).resolve() for path in exclude_paths}
    return sorted(
        {
            path.resolve()
            for path in candidates
            if path.exists() and path.resolve() not in excluded
        },
        key=str,
    )


def plan_qa_history_cleanup(
    db: DBProtocol,
    *,
    include_analysis: bool = True,
    include_registries: bool = True,
    artifact_paths: Iterable[str | Path] = (),
) -> dict[str, Any]:
    requested_tables = list(QA_GENERATED_TABLES)
    if include_registries:
        requested_tables.extend(QA_REGISTRY_TABLES)
    if include_analysis:
        requested_tables.extend(ANALYSIS_GENERATED_TABLES)
        if include_registries:
            requested_tables.extend(ANALYSIS_REGISTRY_TABLES)

    existing = _existing_tables(db)
    tables = [table for table in requested_tables if table in existing]
    table_stats = [_table_stats(db, table) for table in tables]
    protected_stats = [
        _table_stats(db, table)
        for table in PROTECTED_UPSTREAM_TABLES
        if table in existing
    ]
    artifacts = [_artifact_stats(Path(path).resolve()) for path in artifact_paths]
    return {
        "include_analysis": include_analysis,
        "include_registries": include_registries,
        "tables": table_stats,
        "table_count": len(table_stats),
        "row_count": sum(int(row["row_count"]) for row in table_stats),
        "table_storage_bytes": sum(
            int(row.get("storage_bytes") or 0) for row in table_stats
        ),
        "protected_upstream_tables": protected_stats,
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
        "artifact_file_count": sum(int(row["file_count"]) for row in artifacts),
        "artifact_bytes": sum(int(row["size_bytes"]) for row in artifacts),
    }


def purge_qa_history(
    db: DBProtocol,
    *,
    project_root: str | Path,
    include_analysis: bool = True,
    include_registries: bool = True,
    artifact_paths: Iterable[str | Path] = (),
    execute: bool = False,
    confirmation: str | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    artifacts = [Path(path).resolve() for path in artifact_paths]
    before = plan_qa_history_cleanup(
        db,
        include_analysis=include_analysis,
        include_registries=include_registries,
        artifact_paths=artifacts,
    )
    report: dict[str, Any] = {
        "cleanup_version": "1.0.0",
        "created_at": _now(),
        "execute": execute,
        "confirmation_required": PURGE_CONFIRMATION,
        "scope": {
            "closed_qa": True,
            "pattern_mining_and_catalog": True,
            "semi_open_analysis": include_analysis,
            "code_rebuildable_registries": include_registries,
            "generated_artifacts": bool(artifacts),
        },
        "protected_layers": [
            "raw_lake",
            "fact_build",
            "fact_validation",
            "derived_facts",
            "knowledge_graph",
            "frozen_benchmarks",
        ],
        "before": before,
        "deleted_artifacts": [],
    }
    if not execute:
        report["status"] = "planned"
        _write_report(report, output_dir, suffix="plan")
        return report
    if confirmation != PURGE_CONFIRMATION:
        raise ValueError(
            f"Refusing destructive cleanup without --confirm {PURGE_CONFIRMATION}"
        )

    tables = [row["table"] for row in before["tables"]]
    _clear_tables(db, tables)
    safe_root = Path(project_root).resolve() / "data"
    for path in artifacts:
        _assert_safe_artifact_path(path, safe_root)
        if path.exists() or path.is_symlink():
            _remove_path(path)
            report["deleted_artifacts"].append(str(path))

    after = plan_qa_history_cleanup(
        db,
        include_analysis=include_analysis,
        include_registries=include_registries,
        artifact_paths=artifacts,
    )
    report.update(
        {
            "status": "completed",
            "completed_at": _now(),
            "after": after,
            "deleted_row_count": before["row_count"] - after["row_count"],
            "released_table_storage_bytes": before["table_storage_bytes"]
            - after["table_storage_bytes"],
            "released_artifact_bytes": before["artifact_bytes"]
            - after["artifact_bytes"],
        }
    )
    if after["row_count"] != 0:
        raise RuntimeError(
            f"QA cleanup left {after['row_count']} rows in generated tables"
        )
    if any(row["exists"] for row in after["artifacts"]):
        raise RuntimeError("QA cleanup left one or more generated artifact paths")
    _write_report(report, output_dir, suffix="result")
    return report


def _clear_tables(db: DBProtocol, tables: list[str]) -> None:
    if not tables:
        return
    if db.__class__.__name__ == "PostgresMetadataDB":
        with db.transaction():
            db.execute("TRUNCATE TABLE " + ", ".join(tables))
        return
    with db.transaction():
        for table in tables:
            db.execute(f"DELETE FROM {table}")


def _existing_tables(db: DBProtocol) -> set[str]:
    if db.__class__.__name__ == "PostgresMetadataDB":
        rows = db.fetchall(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        )
        return {str(dict(row)["table_name"]) for row in rows}
    rows = db.fetchall("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {str(dict(row)["name"]) for row in rows}


def _table_stats(db: DBProtocol, table: str) -> dict[str, Any]:
    row = db.fetchone(f"SELECT COUNT(*) AS row_count FROM {table}")
    count = int(dict(row or {}).get("row_count") or 0)
    storage_bytes = 0
    if db.__class__.__name__ == "PostgresMetadataDB":
        size = db.fetchone(
            "SELECT COALESCE(pg_total_relation_size(to_regclass(?)), 0) "
            "AS storage_bytes",
            (f"public.{table}",),
        )
        storage_bytes = int(dict(size or {}).get("storage_bytes") or 0)
    return {
        "table": table,
        "row_count": count,
        "storage_bytes": storage_bytes,
    }


def _artifact_stats(path: Path) -> dict[str, Any]:
    if not path.exists() and not path.is_symlink():
        return {
            "path": str(path),
            "exists": False,
            "file_count": 0,
            "size_bytes": 0,
        }
    if path.is_file() or path.is_symlink():
        return {
            "path": str(path),
            "exists": True,
            "file_count": 1,
            "size_bytes": path.lstat().st_size,
        }
    files = [item for item in path.rglob("*") if item.is_file()]
    return {
        "path": str(path),
        "exists": True,
        "file_count": len(files),
        "size_bytes": sum(item.stat().st_size for item in files),
    }


def _assert_safe_artifact_path(path: Path, safe_root: Path) -> None:
    try:
        relative = path.resolve().relative_to(safe_root.resolve())
    except ValueError as exc:
        raise ValueError(f"Artifact path is outside project data root: {path}") from exc
    if not relative.parts:
        raise ValueError("Refusing to delete the project data root")
    protected = {
        "fin_raw",
        "kg_archive",
        "kg_exports",
        "prod_exports",
    }
    if relative.parts[0] in protected:
        raise ValueError(f"Refusing to delete protected artifact path: {path}")
    if relative.parts[:2] == ("layered_exports", "qa_ready"):
        raise ValueError(f"Refusing to delete KG-ready layer artifact: {path}")


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)


def _write_report(
    report: dict[str, Any], output_dir: str | Path | None, *, suffix: str
) -> None:
    if output_dir is None:
        return
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / f"qa_history_cleanup_{suffix}.json"
    md_path = out / f"qa_history_cleanup_{suffix}.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    before = report["before"]
    after = report.get("after") or {}
    lines = [
        "# QA History Cleanup",
        "",
        f"- Status: {report.get('status')}",
        f"- Execute: {report.get('execute')}",
        f"- Generated rows before: {before.get('row_count', 0):,}",
        f"- Generated rows after: {after.get('row_count', 'not executed')}",
        f"- Database bytes before: {before.get('table_storage_bytes', 0):,}",
        f"- Artifact bytes before: {before.get('artifact_bytes', 0):,}",
        f"- Released database bytes: {report.get('released_table_storage_bytes', 0):,}",
        f"- Released artifact bytes: {report.get('released_artifact_bytes', 0):,}",
        "",
        "## Protected Layers",
        "",
    ]
    lines.extend(f"- {layer}" for layer in report["protected_layers"])
    lines.extend(["", "## Cleared Tables", ""])
    lines.extend(
        f"- {row['table']}: {row['row_count']:,} rows"
        for row in before["tables"]
    )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    report["written_files"] = [str(json_path), str(md_path)]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
