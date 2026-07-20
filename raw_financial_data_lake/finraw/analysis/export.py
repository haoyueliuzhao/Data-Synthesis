from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from finraw.db.client import DBProtocol
from finraw.qa.store import json_value

ANALYSIS_EXPORT_VERSION = "1.3.0"


def export_analysis_jsonl(
    db: DBProtocol,
    analysis_build_id: str,
    output_dir: str,
) -> dict[str, Any]:
    build = db.fetchone(
        "SELECT * FROM analysis_builds WHERE analysis_build_id = ?",
        (analysis_build_id,),
    )
    if not build:
        raise ValueError(f"Unknown analysis build: {analysis_build_id}")
    build = dict(build)
    if str(build["status"]) != "ready" or str(build["quality_status"]) != "passed":
        raise ValueError("Only ready, quality-passed analysis builds can be exported")
    root = Path(output_dir) / analysis_build_id
    benchmark_dir = root / "benchmark"
    sft_dir = root / "sft"
    trace_dir = root / "trace_seeds"
    for directory in (benchmark_dir, sft_dir, trace_dir):
        directory.mkdir(parents=True, exist_ok=True)
    candidates = {
        str(row["candidate_id"]): dict(row)
        for row in db.fetchall(
            "SELECT * FROM analysis_candidates WHERE analysis_build_id = ?",
            (analysis_build_id,),
        )
    }
    bundles = {
        str(row["evidence_bundle_id"]): dict(row)
        for row in db.fetchall(
            "SELECT * FROM analysis_evidence_bundles WHERE analysis_build_id = ?",
            (analysis_build_id,),
        )
    }
    plans = {
        str(row["claim_plan_id"]): dict(row)
        for row in db.fetchall(
            "SELECT * FROM analysis_claim_plans WHERE analysis_build_id = ?",
            (analysis_build_id,),
        )
    }
    signals = {
        str(row["signal_id"]): dict(row)
        for row in db.fetchall(
            "SELECT * FROM financial_signal_instances WHERE analysis_build_id = ?",
            (analysis_build_id,),
        )
    }
    samples = [
        dict(row)
        for row in db.fetchall(
            "SELECT * FROM analysis_samples WHERE analysis_build_id = ? "
            "AND validation_status = 'passed' ORDER BY analysis_sample_id",
            (analysis_build_id,),
        )
    ]
    by_split: dict[str, list[dict[str, Any]]] = {}
    sft_rows = []
    trace_rows = []
    for sample in samples:
        candidate = candidates[str(sample["candidate_id"])]
        bundle = bundles[str(candidate["evidence_bundle_id"])]
        plan = plans[str(candidate["claim_plan_id"])]
        signal_rows = [
            signals[str(signal_id)]
            for signal_id in json_value(candidate["signal_ids"], [])
        ]
        evidence_bundle = {
            "entity_ids": json_value(bundle["entity_ids"], []),
            "metric_ids": json_value(bundle["metric_ids"], []),
            "period_scope": json_value(bundle["period_scope"], {}),
            "scope_definition": bundle.get("scope_definition"),
            "peer_scope": {
                "peer_scope_type": bundle.get("peer_scope_type"),
                "peer_scope_id": bundle.get("peer_scope_id"),
                "expected_scope_entity_ids": json_value(
                    bundle.get("expected_scope_entity_ids"), []
                ),
                "scope_membership_hash": bundle.get("scope_membership_hash"),
                "scope_eligibility_policy_hash": bundle.get(
                    "scope_eligibility_policy_hash"
                ),
                "contract": json_value(bundle.get("peer_scope_contract"), {}),
            },
            "signals": [
                {
                    "signal_id": row["signal_id"],
                    "signal_spec_id": row["signal_spec_id"],
                    "payload": json_value(row["signal_payload"], {}),
                    "direction": row["direction"],
                    "strength": row["strength"],
                    "confidence": row["confidence"],
                    "input_fact_ids": json_value(row["input_fact_ids"], []),
                }
                for row in signal_rows
            ],
            "fact_ids": json_value(bundle["fact_ids"], []),
            "supporting_evidence": json_value(bundle["supporting_evidence"], []),
            "counter_evidence": json_value(bundle["counter_evidence"], []),
            "coverage_report": json_value(bundle["coverage_report"], {}),
        }
        benchmark = {
            "analysis_sample_id": sample["analysis_sample_id"],
            "instruction": sample["instruction"],
            "evidence_bundle": evidence_bundle,
            "expected_claim_schema": {
                "mandatory_claim_ids": json_value(plan["mandatory_claim_ids"], []),
                "optional_claim_ids": json_value(plan["optional_claim_ids"], []),
                "valid_conclusion_set": json_value(plan["valid_conclusion_set"], []),
                "forbidden_claim_types": json_value(plan["forbidden_claim_types"], []),
                "numeric_slots": json_value(sample.get("numeric_slots"), []),
            },
            "rubric": json_value(sample["rubric"], {}),
            "metadata": {
                "analysis_build_id": analysis_build_id,
                "kg_build_id": build["kg_build_id"],
                "pattern_id": candidate["analysis_pattern_id"],
                "difficulty": candidate["difficulty"],
                "split": sample["split"],
                "generation_method": sample["generation_method"],
                "instruction_surface_form_id": json_value(
                    sample.get("generation_metadata"), {}
                ).get("instruction_surface_form_id"),
                "discourse_plan_version": json_value(
                    sample.get("generation_metadata"), {}
                ).get("discourse_plan_version"),
            },
        }
        by_split.setdefault(str(sample["split"]), []).append(benchmark)
        if sample["split"] == "train":
            sft_rows.append(
                {
                    "instruction": sample["instruction"],
                    "evidence_summary": evidence_bundle,
                    "analysis_text": sample["analysis_text"],
                    "claim_alignment": json_value(sample["claim_alignment"], []),
                    "selected_conclusion_id": sample["selected_conclusion_id"],
                    "conclusion_text": sample.get("conclusion_text"),
                    "conclusion_semantic_frame": json_value(
                        sample.get("conclusion_semantic_frame"), {}
                    ),
                    "conclusion_surface_form_id": sample.get(
                        "conclusion_surface_form_id"
                    ),
                    "numeric_slots": json_value(sample.get("numeric_slots"), []),
                    "caveats": json_value(sample["caveats"], []),
                    "generation_metadata": json_value(
                        sample.get("generation_metadata"), {}
                    ),
                }
            )
        trace_rows.append(
            {
                "analysis_sample_id": sample["analysis_sample_id"],
                "pattern": candidate["analysis_pattern_id"],
                "binding": {
                    "entity_ids": json_value(candidate["entity_ids"], []),
                    "metric_ids": json_value(candidate["metric_ids"], []),
                    "period_scope": json_value(candidate["period_scope"], {}),
                    "peer_scope_contract": json_value(
                        candidate.get("peer_scope_contract"), {}
                    ),
                },
                "signal_computation": evidence_bundle["signals"],
                "evidence_selection": {
                    "bundle_id": bundle["evidence_bundle_id"],
                    "fact_ids": evidence_bundle["fact_ids"],
                    "evidence_node_ids": json_value(bundle["evidence_node_ids"], []),
                    "evidence_edges": json_value(bundle["evidence_edges"], []),
                },
                "claim_planning": json_value(plan["claim_graph"], []),
                "conclusion_selection": {
                    "conclusion_id": sample["selected_conclusion_id"],
                    "conclusion_text": sample.get("conclusion_text"),
                    "semantic_frame": json_value(
                        sample.get("conclusion_semantic_frame"), {}
                    ),
                    "surface_form_id": sample.get("conclusion_surface_form_id"),
                },
                "numeric_slots": json_value(sample.get("numeric_slots"), []),
                "generation": json_value(sample.get("generation_metadata"), {}),
                "response": sample["analysis_text"],
            }
        )
    written = []
    for split, rows in sorted(by_split.items()):
        path = benchmark_dir / f"{split}.jsonl"
        _write_jsonl(path, rows)
        written.append(path)
    sft_path = sft_dir / "train.jsonl"
    trace_path = trace_dir / "all.jsonl"
    _write_jsonl(sft_path, sft_rows)
    _write_jsonl(trace_path, trace_rows)
    written.extend([sft_path, trace_path])
    manifest = {
        "analysis_build_id": analysis_build_id,
        "kg_build_id": build["kg_build_id"],
        "export_version": ANALYSIS_EXPORT_VERSION,
        "sample_count": len(samples),
        "split_counts": {key: len(value) for key, value in sorted(by_split.items())},
        "formats": [
            "evidence_given_benchmark",
            "claim_grounded_discourse_sft",
            "trace_seeds",
        ],
        "generation_audit": json_value(build.get("notes"), {}).get(
            "llm_generation", {}
        ),
        "written_files": [str(path) for path in written],
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=str) + "\n"
    )
    manifest["written_files"].append(str(manifest_path))
    return manifest


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n"
            )
