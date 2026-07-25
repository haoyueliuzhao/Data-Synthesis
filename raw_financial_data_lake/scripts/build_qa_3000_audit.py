from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from finraw.config import load_config
from finraw.db.client import create_metadata_db
from finraw.qa.store import json_value


TARGET_ISSUES = (
    "overly_trivial",
    "low_standalone_value",
    "output_instruction_slightly_formulaic",
    "unnatural_output_instruction",
    "mechanical_template_language",
    "time_scope_awkward",
    "scope_definition_unclear",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--empirical-run-id", required=True)
    parser.add_argument("--global-quality-report", required=True)
    parser.add_argument("--greater-china-quality-report", required=True)
    parser.add_argument("--global-quality-items", required=True)
    parser.add_argument("--greater-china-quality-items", required=True)
    parser.add_argument("--empirical-report", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    db = create_metadata_db(load_config(args.config))
    run = db.fetchone(
        "SELECT * FROM qa_empirical_runs WHERE empirical_run_id = ?",
        (args.empirical_run_id,),
    )
    if not run:
        raise RuntimeError(f"Unknown empirical run: {args.empirical_run_id}")
    qa_ids = list(json_value(run["sample_manifest"], {}).get("qa_ids") or [])
    if len(qa_ids) != 3000 or len(set(qa_ids)) != 3000:
        raise RuntimeError("Expected exactly 3,000 unique pinned QA IDs")

    rows: list[dict[str, Any]] = []
    for start in range(0, len(qa_ids), 500):
        batch = qa_ids[start : start + 500]
        placeholders = ",".join("?" for _ in batch)
        rows.extend(
            dict(row)
            for row in db.fetchall(
                f"""
                SELECT s.*, c.entity_ids, c.metric_ids, c.time_scope,
                       c.entity_scope, c.source_fact_ids, c.source_derived_ids,
                       c.source_document_ids, c.raw_object_ids,
                       c.canonical_semantics, c.answer_payload,
                       c.answer_schema, c.graph_features, c.operation_plan_id,
                       c.pattern_id, c.pattern_version,
                       l.benchmark_task, l.market_subset, l.topic, l.subtopic,
                       l.metric_families, l.source_classes, l.frequency,
                       l.period_count, l.time_span_months,
                       l.operation_families, l.operation_depth AS label_operation_depth,
                       l.scope_size, l.rubric_type, l.generation_pipeline
                FROM qa_samples s
                JOIN qa_candidates c
                  ON c.qa_build_id = s.qa_build_id AND c.candidate_id = s.candidate_id
                JOIN qa_distribution_labels l
                  ON l.qa_build_id = s.qa_build_id AND l.qa_id = s.qa_id
                WHERE s.qa_id IN ({placeholders})
                """,
                batch,
            )
        )
    by_id = {str(row["qa_id"]): row for row in rows}
    missing = [qa_id for qa_id in qa_ids if qa_id not in by_id]
    if missing:
        raise RuntimeError(f"Pinned QA rows are missing: {missing[:5]}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    release_path = output_dir / "qa_3000.jsonl"
    digest = hashlib.sha256()
    counts: dict[str, Counter[str]] = {
        key: Counter()
        for key in (
            "market_subset",
            "benchmark_task",
            "language",
            "difficulty",
            "generation_pipeline",
            "answer_type",
            "task_subtype",
        )
    }
    with release_path.open("w", encoding="utf-8") as handle:
        for qa_id in qa_ids:
            row = by_id[qa_id]
            payload = _release_payload(row)
            line = (
                json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
                + "\n"
            )
            handle.write(line)
            digest.update(line.encode("utf-8"))
            for key, counter in counts.items():
                counter[str(payload.get(key) or "unknown")] += 1

    quality_reports = {
        "global": _load_json(args.global_quality_report),
        "greater_china": _load_json(args.greater_china_quality_report),
    }
    quality_items = _load_jsonl(args.global_quality_items) + _load_jsonl(
        args.greater_china_quality_items
    )
    quality_item_by_id = {str(item["qa_id"]): item for item in quality_items}
    missing_quality = [qa_id for qa_id in qa_ids if qa_id not in quality_item_by_id]
    if missing_quality:
        raise RuntimeError(f"Pinned QA quality rows are missing: {missing_quality[:5]}")
    release_quality_items = [quality_item_by_id[qa_id] for qa_id in qa_ids]
    release_decisions = Counter(
        str(item.get("decision") or "unknown") for item in release_quality_items
    )
    training_approved_count = sum(
        str(item.get("decision")) in {"accepted", "accepted_for_coverage"}
        and float(
            (item.get("dataset_role_components") or {}).get("training_release_eligible")
            or 0
        )
        >= 1.0
        for item in release_quality_items
    )
    empirical_reports = {
        report["evaluation_mode"]: report
        for report in (_load_json(path) for path in args.empirical_report)
    }
    if set(empirical_reports) != {
        "gold_plan_given",
        "evidence_only",
        "evidence_pool",
        "retrieval_tool",
    }:
        raise RuntimeError("All four empirical modes are required")

    manifest = {
        "release_kind": "l0_passed_diagnostic",
        "quality_filter_applied": False,
        "release_id": f"qa3000_{digest.hexdigest()[:16]}",
        "empirical_run_id": args.empirical_run_id,
        "qa_build_ids": json_value(run["qa_build_ids"], []),
        "sample_count": len(qa_ids),
        "sha256": digest.hexdigest(),
        "distribution": {
            key: dict(sorted(value.items())) for key, value in counts.items()
        },
        "deterministic_validation": {
            "passed": sum(
                str(item.get("deterministic_gate_status")) == "passed"
                for item in release_quality_items
            ),
            "population": len(release_quality_items),
        },
        "release_l2_decisions": dict(sorted(release_decisions.items())),
        "training_approved_count": training_approved_count,
        "diagnostic_only_count": len(release_quality_items) - training_approved_count,
        "quality_candidate_pool": {
            market: {
                "population": report["population"],
                "decision_counts": report["decision_counts"],
                "confirmed_target_issues": {
                    issue: int(
                        report["issue_code_consensus"]
                        .get("confirmed_by_adjudicator", {})
                        .get(issue, 0)
                    )
                    for issue in TARGET_ISSUES
                },
            }
            for market, report in quality_reports.items()
        },
        "empirical": {
            mode: {
                "empirical_run_id": report["empirical_run_id"],
                "status": report["status"],
                "overall": report["overall"],
                "model_results": {
                    role: {
                        key: value
                        for key, value in result.items()
                        if key not in {"accuracy_slices"}
                    }
                    for role, result in report["model_results"].items()
                },
            }
            for mode, report in empirical_reports.items()
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "qa_3000_full_evaluation_report.md").write_text(
        _markdown(manifest), encoding="utf-8"
    )


def _release_payload(row: dict[str, Any]) -> dict[str, Any]:
    json_fields = {
        "rubric",
        "source_metadata",
        "entity_ids",
        "metric_ids",
        "time_scope",
        "entity_scope",
        "source_fact_ids",
        "source_derived_ids",
        "source_document_ids",
        "raw_object_ids",
        "canonical_semantics",
        "answer_payload",
        "answer_schema",
        "graph_features",
        "metric_families",
        "source_classes",
        "operation_families",
    }
    payload = {
        key: json_value(
            value,
            {}
            if key
            in {
                "rubric",
                "time_scope",
                "entity_scope",
                "canonical_semantics",
                "answer_payload",
                "answer_schema",
                "graph_features",
            }
            else [],
        )
        if key in json_fields
        else value
        for key, value in row.items()
    }
    return payload


def _load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_jsonl(path: str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _markdown(manifest: dict[str, Any]) -> str:
    distribution = manifest["distribution"]
    quality = manifest["quality_candidate_pool"]
    empirical = manifest["empirical"]
    lines = [
        "# QA 3000 L0-passed Diagnostic Evaluation Report",
        "",
        "## Release",
        "",
        f"- Release ID: `{manifest['release_id']}`",
        f"- Samples: {manifest['sample_count']:,}",
        f"- Release kind: `{manifest['release_kind']}`",
        f"- L2 training-approved samples: {manifest['training_approved_count']:,}",
        f"- Diagnostic-only samples: {manifest['diagnostic_only_count']:,}",
        f"- Exact release L2 decisions: {json.dumps(manifest['release_l2_decisions'], ensure_ascii=False, sort_keys=True)}",
        f"- SHA-256: `{manifest['sha256']}`",
        f"- QA builds: {', '.join(f'`{item}`' for item in manifest['qa_build_ids'])}",
        "",
        "## Distribution",
        "",
    ]
    for key in (
        "market_subset",
        "benchmark_task",
        "language",
        "difficulty",
        "generation_pipeline",
        "answer_type",
    ):
        lines.append(
            f"- {key}: {json.dumps(distribution[key], ensure_ascii=False, sort_keys=True)}"
        )
    lines.extend(["", "## Candidate-pool L2 Context", ""])
    for market, report in quality.items():
        lines.append(f"### {market}")
        lines.append("")
        lines.append(
            f"- Decisions: {json.dumps(report['decision_counts'], ensure_ascii=False, sort_keys=True)}"
        )
        lines.append(
            f"- Confirmed target issues: {json.dumps(report['confirmed_target_issues'], ensure_ascii=False, sort_keys=True)}"
        )
        lines.append("")
    lines.extend(
        [
            "## L3 Empirical Evaluation",
            "",
            "| Mode | Contract | Semantic given valid | Evidence selection | End-to-end |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for mode in ("gold_plan_given", "evidence_only", "evidence_pool", "retrieval_tool"):
        overall = empirical[mode]["overall"]
        evidence = overall.get("evidence_selection_correct_rate")
        lines.append(
            f"| {mode} | {overall['contract_success_rate']:.2%} | "
            f"{overall['semantic_accuracy_given_valid_contract']:.2%} | "
            f"{'N/A' if evidence is None else f'{evidence:.2%}'} | "
            f"{overall['end_to_end_accuracy']:.2%} |"
        )
    lines.extend(
        [
            "",
            "## Assessment",
            "",
            "The release is deterministically correct and fully traceable, but subjective quality is not uniformly solved. Low-value and awkward-time issues improved relative to the previous generation, while formulaic output instructions and unclear scope wording remain concentrated in ranking, screening, and follow-up templates. Retrieval/tool performance is substantially below evidence-given performance, so the release is suitable for controlled QA training and evaluation but should not be treated as proof of mature autonomous financial-search capability.",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
