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
        SELECT s.*, e.ordered_node_ids, e.ordered_edge_ids, e.source_fact_ids,
               e.source_derived_ids, e.raw_object_ids, c.canonical_semantics
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
    sft_paths = {"train": sft_dir / "train.jsonl"}
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
            if split == "train":
                sft_files["train"].write(
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
        "sft": {"train": _file_info(sft_paths["train"], split_counts.get("train", 0))},
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
        "sft_allowed_splits": ["train"],
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


def _decode(row: dict[str, Any]) -> dict[str, Any]:
    for key in [
        "answer_value",
        "rubric",
        "source_metadata",
        "ordered_node_ids",
        "ordered_edge_ids",
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
