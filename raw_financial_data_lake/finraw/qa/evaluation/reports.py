from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from finraw.qa.evaluation.dataset_metrics import build_slice_metrics


def build_quality_report(
    run: dict[str, Any],
    bundles: list[dict[str, Any]],
    items: list[dict[str, Any]],
    calls: list[dict[str, Any]],
    *,
    output_dir: str | None = None,
) -> dict[str, Any]:
    successful_calls = [row for row in calls if row.get("status") == "succeeded"]
    telemetry = [row.get("telemetry") or {} for row in calls]
    report = {
        "evaluation_run_id": run["evaluation_run_id"],
        "qa_build_id": run["qa_build_id"],
        "evaluation_mode": run["evaluation_mode"],
        "status": run["status"],
        "rubric_version": run["rubric_version"],
        "rubric_hash": run["rubric_hash"],
        "sample_manifest_hash": run["sample_manifest_hash"],
        "population": {
            "sample_count": len(bundles),
            "deterministic_pass_count": sum(
                row.get("deterministic_gate_status") == "passed" for row in items
            ),
            "evaluated_item_count": len(items),
            "judge_call_count": len(calls),
            "judge_call_success_count": len(successful_calls),
            "judge_call_success_rate": _rate(
                row.get("status") == "succeeded" for row in calls
            ),
        },
        "decision_counts": dict(
            sorted(Counter(str(row.get("decision")) for row in items).items())
        ),
        "fatal_flag_counts": dict(
            sorted(
                Counter(
                    flag for row in items for flag in row.get("fatal_flags") or []
                ).items()
            )
        ),
        "issue_code_counts": dict(
            sorted(
                Counter(
                    issue for row in items for issue in row.get("issue_codes") or []
                ).items()
            )
        ),
        "subjective_quality": _score_summary(
            [
                float(row["subjective_quality_score"])
                for row in items
                if row.get("subjective_quality_score") is not None
            ]
        ),
        "dataset_role_value": _score_summary(
            [float(row.get("dataset_role_value_score") or 0) for row in items]
        ),
        "judge_disagreement": {
            "adjudication_required_count": sum(
                bool(row.get("judge_disagreement", {}).get("requires_adjudication"))
                for row in items
            ),
            "adjudication_required_rate": _rate(
                bool(row.get("judge_disagreement", {}).get("requires_adjudication"))
                for row in items
            ),
        },
        "telemetry": {
            "prompt_tokens": _sum_optional(telemetry, "prompt_tokens"),
            "completion_tokens": _sum_optional(telemetry, "completion_tokens"),
            "total_tokens": _sum_optional(telemetry, "total_tokens"),
            "estimated_cost": _sum_optional(telemetry, "estimated_cost"),
            "model_fallback_count": sum(
                bool(row.get("model_fallback_used")) for row in telemetry
            ),
            "models": dict(
                sorted(
                    Counter(
                        str(row.get("response_model") or row.get("model_selected") or "unknown")
                        for row in telemetry
                    ).items()
                )
            ),
        },
        "slices": build_slice_metrics(bundles, items),
        "policy_note": _policy_note(run),
    }
    if output_dir:
        report["written_files"] = write_quality_artifacts(
            report, bundles, items, output_dir
        )
    return report


def write_quality_artifacts(
    report: dict[str, Any],
    bundles: list[dict[str, Any]],
    items: list[dict[str, Any]],
    output_dir: str,
) -> list[str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "qa_quality_evaluation_report.json"
    md_path = out / "qa_quality_evaluation_report.md"
    items_path = out / "qa_evaluation_items.jsonl"
    disagreement_path = out / "judge_disagreement.jsonl"
    llm_secondary = (
        ((report.get("policy_note") or "").startswith("Human calibration is temporarily"))
    )
    review_path = out / (
        "llm_secondary_review_queue.jsonl" if llm_secondary
        else "manual_review_queue.jsonl"
    )
    json_path.write_text(_pretty(report) + "\n", encoding="utf-8")
    item_by_qa = {str(row["qa_id"]): row for row in items}
    _write_jsonl(items_path, items)
    _write_jsonl(
        disagreement_path,
        [
            row
            for row in items
            if row.get("judge_disagreement", {}).get("requires_adjudication")
        ],
    )
    review_rows = []
    for bundle in bundles:
        item = item_by_qa.get(str(bundle["qa_id"]))
        if not item or item.get("decision") not in {"manual_review", "llm_secondary_review"}:
            continue
        review_rows.append(
            {
                "qa_id": bundle["qa_id"],
                "question": bundle["sample"].get("question"),
                "benchmark_task": bundle["distribution_label"].get("benchmark_task"),
                "language": bundle["sample"].get("language"),
                "answer_type": bundle["sample"].get("answer_type"),
                "rubric_version": report["rubric_version"],
                ("llm_secondary_review" if llm_secondary else "human_review"): {
                    "dimension_scores": {},
                    "fatal_flags": [],
                    "decision": "",
                    "reason_codes": [],
                },
            }
        )
    _write_jsonl(review_path, review_rows)
    lines = [
        "# Financial QA Quality Evaluation Report",
        "",
        f"- Evaluation run: `{report['evaluation_run_id']}`",
        f"- QA build: `{report['qa_build_id']}`",
        f"- Mode: `{report['evaluation_mode']}`",
        f"- Samples: `{report['population']['sample_count']}`",
        f"- Deterministic pass: `{report['population']['deterministic_pass_count']}`",
        f"- Judge calls passed: `{report['population']['judge_call_success_count']} / {report['population']['judge_call_count']}`",
        f"- Subjective mean: `{report['subjective_quality']['mean']}`",
        f"- Adjudication required: `{report['judge_disagreement']['adjudication_required_count']}`",
        "",
        "## Decisions",
        "",
    ]
    lines.extend(
        f"- `{key}`: `{value}`" for key, value in report["decision_counts"].items()
    )
    lines.extend(["", "## Calibration Status", "", f"- {report['policy_note']}"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [
        str(json_path),
        str(md_path),
        str(items_path),
        str(disagreement_path),
        str(review_path),
    ]


def _policy_note(run: dict[str, Any]) -> str:
    quality = dict((run.get("notes") or {}).get("quality_config") or {})
    calibration = dict(quality.get("calibration") or {})
    if calibration.get("replacement_mode") == "llm_secondary_review":
        return (
            "Human calibration is temporarily disabled. A pinned adversarial LLM "
            "performs second-stage review; this is provisional model review, not "
            "a substitute for measured human-judge agreement."
        )
    return (
        "Advisory scores are not release-blocking until human calibration freezes "
        "thresholds and judge bias has been measured."
    )


def _score_summary(values: list[float]) -> dict[str, float | None]:
    rows = sorted(values)
    return {
        "mean": round(sum(rows) / len(rows), 6) if rows else None,
        "p10": _percentile(rows, 0.10),
        "p50": _percentile(rows, 0.50),
        "p90": _percentile(rows, 0.90),
        "minimum": round(rows[0], 6) if rows else None,
        "maximum": round(rows[-1], 6) if rows else None,
    }


def _percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    return round(values[round((len(values) - 1) * ratio)], 6)


def _rate(values: Any) -> float:
    rows = list(values)
    return round(sum(bool(row) for row in rows) / len(rows), 6) if rows else 0.0


def _sum_optional(rows: list[dict[str, Any]], key: str) -> float | int | None:
    values = [row[key] for row in rows if row.get(key) is not None]
    if not values:
        return None
    total = sum(float(value) for value in values)
    return round(total, 8) if any(isinstance(value, float) for value in values) else int(total)


def _pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
