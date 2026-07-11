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
    out.mkdir(parents=True, exist_ok=True)
    benchmark = out / "benchmark.jsonl"
    sft = out / "sft.jsonl"
    traces = out / "trace_seeds.jsonl"
    split_counts: Counter[str] = Counter()
    with (
        benchmark.open("w", encoding="utf-8") as benchmark_file,
        sft.open("w", encoding="utf-8") as sft_file,
        traces.open("w", encoding="utf-8") as trace_file,
    ):
        for raw in rows:
            row = _decode(dict(raw))
            metadata = {
                "qa_group_id": row["qa_group_id"],
                "semantic_cluster_id": row["semantic_cluster_id"],
                "qa_build_id": qa_build_id,
                "kg_build_id": build["kg_build_id"],
                "source_fact_ids": row["source_fact_ids"],
                "source_derived_ids": row["source_derived_ids"],
                "split": row["split"],
            }
            benchmark_file.write(
                json.dumps(
                    {
                        "id": row["qa_id"],
                        "question": row["question"],
                        "answer": row["answer_value"],
                        "answer_text": row["answer_text"],
                        "rubric": row["rubric"],
                        "task_type": row["task_subtype"],
                        "difficulty": row["difficulty"],
                        "split": row["split"],
                        "metadata": metadata,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                + "\n"
            )
            sft_file.write(
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
            trace_file.write(
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
                        "split": row["split"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                + "\n"
            )
            split_counts[row["split"]] += 1
    manifest = {
        "qa_build_id": qa_build_id,
        "kg_build_id": build["kg_build_id"],
        "sample_count": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "files": [str(benchmark), str(sft), str(traces)],
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    manifest["manifest"] = str(manifest_path)
    return manifest


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
