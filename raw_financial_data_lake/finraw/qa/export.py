from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from finraw.db.client import DBProtocol
from finraw.qa.schema import ensure_qa_schema
from finraw.qa.store import json_value


def export_qa_jsonl(
    db: DBProtocol, qa_build_id: str, output_dir: str
) -> dict[str, Any]:
    ensure_qa_schema(db)
    build = db.fetchone("SELECT * FROM qa_builds WHERE qa_build_id = ?", (qa_build_id,))
    if not build:
        raise RuntimeError(f"Unknown QA build: {qa_build_id}")
    build = dict(build)
    build_notes = json_value(build.get("notes"), {})
    gate_status = build_notes.get("build_gate", {}).get("status")
    if build.get("status") != "ready" or gate_status != "passed":
        raise RuntimeError(
            f"QA build {qa_build_id} is not exportable: "
            f"status={build.get('status')}, build_gate={gate_status}"
        )
    rows = db.fetchall(
        """
        SELECT s.*, e.ordered_node_ids, e.ordered_edge_ids,
               e.evidence_node_ids, e.evidence_edges, e.evidence_components,
               e.source_fact_ids, e.source_derived_ids, e.raw_object_ids,
               c.canonical_semantics
        FROM qa_samples s
        JOIN qa_evidence_paths e ON e.qa_id = s.qa_id
        JOIN qa_candidates c ON c.candidate_id = s.candidate_id
        WHERE s.qa_build_id = ? AND s.validation_status = 'passed' AND s.split IS NOT NULL
        ORDER BY s.split, s.qa_id
        """,
        (qa_build_id,),
    )
    out = Path(output_dir) / qa_build_id
    benchmark_dir = out / "benchmark"
    sft_dir = out / "sft"
    trace_dir = out / "trace_seeds"
    for directory in (benchmark_dir, sft_dir, trace_dir):
        directory.mkdir(parents=True, exist_ok=True)
    splits = sorted({str(row["split"]) for row in rows})
    benchmark_paths = {split: benchmark_dir / f"{split}.jsonl" for split in splits}
    trace_paths = {split: trace_dir / f"{split}.jsonl" for split in splits}
    sft_allowed_splits = [split for split in ["train", "train_complex"] if split in splits]
    sft_paths = {split: sft_dir / f"{split}.jsonl" for split in sft_allowed_splits}
    benchmark_files = {
        key: path.open("w", encoding="utf-8") for key, path in benchmark_paths.items()
    }
    trace_files = {
        key: path.open("w", encoding="utf-8") for key, path in trace_paths.items()
    }
    sft_files = {
        key: path.open("w", encoding="utf-8") for key, path in sft_paths.items()
    }
    split_counts: Counter[str] = Counter()
    try:
        for raw in rows:
            row = _decode(dict(raw))
            split = row["split"]
            metadata = {
                "qa_group_id": row["qa_group_id"],
                "semantic_cluster_id": row["semantic_cluster_id"],
                "qa_build_id": qa_build_id,
                "kg_build_id": build["kg_build_id"],
                "source_fact_ids": row["source_fact_ids"],
                "source_derived_ids": row["source_derived_ids"],
                "split": split,
                "template_id": row.get("template_id"),
                "template_hash": row.get("template_hash"),
            }
            benchmark_files[split].write(
                json.dumps(
                    {
                        "id": row["qa_id"],
                        "question": row["question"],
                        "answer": row["answer_value"],
                        "answer_text": row["answer_text"],
                        "rubric": row["rubric"],
                        "task_type": row["task_subtype"],
                        "difficulty": row["difficulty"],
                        "split": split,
                        "metadata": metadata,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                + "\n"
            )
            if split in sft_files:
                sft_files[split].write(
                    json.dumps(
                        {
                            "messages": [
                                {"role": "user", "content": row["question"]},
                                {"role": "assistant", "content": row["answer_text"]},
                            ],
                            "metadata": metadata,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    )
                    + "\n"
                )
            trace_files[split].write(
                json.dumps(
                    {
                        "question": row["question"],
                        "answer": row["answer_value"],
                        "task_type": row["task_subtype"],
                        "kg_path": {
                            "node_ids": row["ordered_node_ids"],
                            "edge_ids": row["ordered_edge_ids"],
                        },
                        "evidence_subgraph": {
                            "node_ids": row["evidence_node_ids"],
                            "edges": row["evidence_edges"],
                            "components": row["evidence_components"],
                        },
                        "source_fact_ids": row["source_fact_ids"],
                        "source_derived_ids": row["source_derived_ids"],
                        "raw_object_ids": row["raw_object_ids"],
                        "required_operations": _operations(row["task_subtype"]),
                        "canonical_semantics": row["canonical_semantics"],
                        "split": split,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                + "\n"
            )
            split_counts[split] += 1
    finally:
        for handle in [
            *benchmark_files.values(),
            *sft_files.values(),
            *trace_files.values(),
        ]:
            handle.close()
    files = {
        "benchmark": {
            split: _file_info(path, split_counts[split])
            for split, path in benchmark_paths.items()
        },
        "sft": {
            split: _file_info(path, split_counts.get(split, 0))
            for split, path in sft_paths.items()
        },
        "trace_seeds": {
            split: _file_info(path, split_counts[split])
            for split, path in trace_paths.items()
        },
    }
    manifest = {
        "qa_build_id": qa_build_id,
        "kg_build_id": build["kg_build_id"],
        "sample_count": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "sft_allowed_splits": sft_allowed_splits,
        "files": files,
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    manifest["manifest"] = str(manifest_path)
    return manifest


def combine_qa_export_manifests(
    manifest_paths: list[str],
    output_dir: str,
    release_id: str,
) -> dict[str, Any]:
    """Combine immutable regional QA exports into one checksummed release."""
    if len(manifest_paths) < 2:
        raise ValueError("A combined QA release requires at least two source manifests")
    if not release_id.strip():
        raise ValueError("release_id must not be empty")
    out = Path(output_dir) / release_id
    if out.exists():
        raise FileExistsError(f"Combined QA release already exists: {out}")

    sources: list[dict[str, Any]] = []
    kg_build_ids: set[str] = set()
    qa_build_ids: set[str] = set()
    artifact_rows: dict[str, dict[str, list[dict[str, Any]]]] = {}
    source_sample_count = 0
    source_split_counts: Counter[str] = Counter()

    for raw_manifest_path in manifest_paths:
        manifest_path = Path(raw_manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        qa_build_id = str(manifest.get("qa_build_id") or "")
        kg_build_id = str(manifest.get("kg_build_id") or "")
        if not qa_build_id or not kg_build_id:
            raise ValueError(f"Invalid source QA manifest: {manifest_path}")
        if qa_build_id in qa_build_ids:
            raise ValueError(f"Duplicate source QA build: {qa_build_id}")
        qa_build_ids.add(qa_build_id)
        kg_build_ids.add(kg_build_id)
        source_sample_count += int(manifest.get("sample_count") or 0)
        source_split_counts.update(
            {
                str(key): int(value)
                for key, value in manifest.get("split_counts", {}).items()
            }
        )
        sources.append(
            {
                "qa_build_id": qa_build_id,
                "kg_build_id": kg_build_id,
                "manifest_path": str(manifest_path),
                "manifest_sha256": _sha256(manifest_path),
                "sample_count": int(manifest.get("sample_count") or 0),
            }
        )
        for artifact_kind, split_files in manifest.get("files", {}).items():
            for split, file_info in split_files.items():
                path = Path(str(file_info["path"]))
                expected_sha256 = str(file_info.get("sha256") or "")
                if _sha256(path) != expected_sha256:
                    raise ValueError(f"Source artifact checksum mismatch: {path}")
                rows = _read_jsonl(path)
                expected_rows = int(file_info.get("rows") or 0)
                if len(rows) != expected_rows:
                    raise ValueError(
                        f"Source artifact row mismatch: {path}: "
                        f"expected={expected_rows}, actual={len(rows)}"
                    )
                artifact_rows.setdefault(str(artifact_kind), {}).setdefault(
                    str(split), []
                ).extend(rows)

    if len(kg_build_ids) != 1:
        raise ValueError(
            "Combined QA release sources must use one pinned KG build: "
            f"{sorted(kg_build_ids)}"
        )

    benchmark_rows = [
        row for rows in artifact_rows.get("benchmark", {}).values() for row in rows
    ]
    benchmark_ids = [str(row.get("id") or "") for row in benchmark_rows]
    if (
        len(set(benchmark_ids)) != len(benchmark_ids)
        or any(not value for value in benchmark_ids)
    ):
        raise ValueError("Combined benchmark contains missing or duplicate QA IDs")
    if len(benchmark_rows) != source_sample_count:
        raise ValueError(
            "Combined benchmark sample count does not match source manifests: "
            f"expected={source_sample_count}, actual={len(benchmark_rows)}"
        )

    sources.sort(key=lambda row: str(row["qa_build_id"]))
    files: dict[str, dict[str, dict[str, Any]]] = {}
    for artifact_kind, split_rows in sorted(artifact_rows.items()):
        for split, rows in sorted(split_rows.items()):
            path = out / artifact_kind / f"{split}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            ordered_rows = sorted(rows, key=_combined_row_sort_key)
            with path.open("w", encoding="utf-8") as handle:
                for row in ordered_rows:
                    handle.write(
                        json.dumps(
                            row,
                            ensure_ascii=False,
                            sort_keys=True,
                            default=str,
                        )
                        + "\n"
                    )
            files.setdefault(artifact_kind, {})[split] = _file_info(
                path, len(ordered_rows)
            )

    manifest = {
        "release_id": release_id,
        "release_type": "combined_immutable_qa_export",
        "kg_build_id": next(iter(kg_build_ids)),
        "qa_build_ids": sorted(qa_build_ids),
        "source_manifests": sources,
        "sample_count": source_sample_count,
        "split_counts": dict(sorted(source_split_counts.items())),
        "sft_allowed_splits": ["train", "train_complex"],
        "files": files,
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    manifest["manifest"] = str(manifest_path)
    return manifest


def _file_info(path: Path, row_count: int) -> dict[str, Any]:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path),
        "rows": row_count,
        "bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected JSON object at {path}:{line_number}")
            rows.append(value)
    return rows


def _combined_row_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    messages = row.get("messages") if isinstance(row.get("messages"), list) else []
    question = str(row.get("question") or "")
    if not question and messages and isinstance(messages[0], dict):
        question = str(messages[0].get("content") or "")
    return (
        str(row.get("id") or metadata.get("qa_build_id") or ""),
        str(metadata.get("qa_group_id") or ""),
        question,
    )


def _decode(row: dict[str, Any]) -> dict[str, Any]:
    for key in [
        "answer_value",
        "rubric",
        "source_metadata",
        "ordered_node_ids",
        "ordered_edge_ids",
        "evidence_node_ids",
        "evidence_edges",
        "evidence_components",
        "source_fact_ids",
        "source_derived_ids",
        "raw_object_ids",
        "canonical_semantics",
    ]:
        row[key] = json_value(row.get(key), [] if key.endswith("_ids") else {})
    return row


def _operations(task_type: str) -> list[str]:
    operations = ["entity_lookup", "metric_lookup", "time_filter"]
    if task_type == "single_fact":
        return operations + ["fact_lookup", "provenance_lookup"]
    if task_type in {
        "difference",
        "yoy_growth",
        "qoq_growth",
        "ratio",
        "share",
        "long_window_return",
    }:
        return operations + ["load_derived_inputs", task_type, "independent_recompute"]
    if "ranking" in task_type or task_type in {
        "argmax",
        "argmin",
        "industry_argmax",
        "industry_argmin",
    }:
        return operations + ["scope_filter", "sort", "independent_recompute"]
    if task_type == "multi_condition_screening":
        return operations + ["scope_filter", "condition_filter", "set_validation"]
    return operations + [
        "time_range_filter",
        "argmax" if task_type.endswith("max") else "argmin",
        "independent_recompute",
    ]
