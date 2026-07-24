from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from finraw.qa.evaluation.contracts import JUDGE_ROLES
from finraw.qa.evaluation.dataset_metrics import build_slice_metrics
from finraw.qa.evaluation.feedback import build_generation_feedback


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
    quality_config = dict((run.get("notes") or {}).get("quality_config") or {})
    minimum_slice_size = max(
        int((quality_config.get("reporting") or {}).get("minimum_slice_size", 30)),
        1,
    )
    feedback_config = (
        (quality_config.get("reporting") or {}).get("generation_feedback") or {}
    )
    issue_report = _issue_code_report(successful_calls)
    unresolved_report = _unresolved_adjudication_report(items, quality_config)
    adjudication_report = _adjudication_report(items)
    generation_feedback = build_generation_feedback(
        bundles,
        successful_calls,
        items=items,
        minimum_issue_count=int(feedback_config.get("minimum_issue_count", 1)),
        maximum_hotspots=int(feedback_config.get("maximum_hotspots", 100)),
    )
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
        # Backward-compatible alias: samples flagged by at least one judge.
        "issue_code_counts": issue_report["flagged_by_any_judge"],
        "issue_codes_by_role": issue_report["by_role"],
        "issue_code_consensus": {
            "flagged_by_any_judge": issue_report["flagged_by_any_judge"],
            "flagged_by_two_or_more": issue_report["flagged_by_two_or_more"],
            "confirmed_by_adjudicator": issue_report[
                "confirmed_by_adjudicator"
            ],
            "by_issue": issue_report["by_issue"],
        },
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
        "dataset_role_contract": {
            "contract_id": (run.get("notes") or {}).get(
                "dataset_role_contract", {}
            ).get("contract_id"),
            "contract_hash": (run.get("notes") or {}).get(
                "dataset_role_contract_hash"
            ),
            "training_release_eligible_count": sum(
                float(
                    (row.get("dataset_role_components") or {}).get(
                        "training_release_eligible", 0
                    )
                )
                == 100.0
                for row in items
            ),
            "training_release_excluded_count": sum(
                float(
                    (row.get("dataset_role_components") or {}).get(
                        "training_release_eligible", 0
                    )
                )
                != 100.0
                for row in items
            ),
        },
        "judge_disagreement": {
            "adjudication_required_count": sum(
                bool(row.get("judge_disagreement", {}).get("requires_adjudication"))
                for row in items
            ),
            "adjudication_required_rate": _rate(
                bool(row.get("judge_disagreement", {}).get("requires_adjudication"))
                for row in items
            ),
            "unresolved_sources": unresolved_report,
        },
        "adjudication": adjudication_report,
        "generation_feedback": generation_feedback,
        "risk_router": {
            "status_counts": dict(
                sorted(
                    Counter(
                        str(
                            (
                                row.get("judge_disagreement") or {}
                            ).get("risk_router_status")
                            or "legacy_or_unknown"
                        )
                        for row in items
                    ).items()
                )
            ),
            "quarantined_count": sum(
                row.get("decision") == "quarantined_judge_disagreement"
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
        "slices": build_slice_metrics(
            bundles,
            items,
            minimum_slice_size=minimum_slice_size,
        ),
        "slice_interpretation": {
            "minimum_slice_size": minimum_slice_size,
            "interval_method": "wilson_score_95",
            "warning": (
                "Slices below the minimum are descriptive only and must not be "
                "compared as if they had full-sample confidence."
            ),
        },
        "policy_note": _policy_note(run),
    }
    if output_dir:
        report["written_files"] = write_quality_artifacts(
            report, bundles, items, output_dir
        )
    return report



def _issue_code_report(calls: list[dict[str, Any]]) -> dict[str, Any]:
    role_issue_counts = {role: Counter() for role in JUDGE_ROLES}
    role_samples = {role: set() for role in JUDGE_ROLES}
    by_sample: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    adjudicator_confirmations: dict[str, set[str]] = defaultdict(set)
    for row in calls:
        role = str(row.get("judge_role") or "unknown")
        qa_id = str(row.get("qa_id") or "")
        role_issue_counts.setdefault(role, Counter())
        role_samples.setdefault(role, set()).add(qa_id)
        for issue in set(str(item) for item in row.get("issue_codes") or []):
            role_issue_counts[role][issue] += 1
            by_sample[qa_id][issue].add(role)
            if role == "adversarial_reviewer" and row.get("resolutions"):
                adjudicator_confirmations[qa_id].add(issue)

    flagged_any = Counter()
    flagged_two = Counter()
    adjudicator_confirmed = Counter()
    for qa_id, issue_roles in by_sample.items():
        for issue, roles in issue_roles.items():
            flagged_any[issue] += 1
            if len(roles) >= 2:
                flagged_two[issue] += 1
            if issue in adjudicator_confirmations.get(qa_id, set()):
                adjudicator_confirmed[issue] += 1

    all_issues = sorted(
        set(flagged_any) | set(flagged_two) | set(adjudicator_confirmed)
    )
    return {
        "by_role": {
            role: {
                "successful_call_count": sum(
                    1
                    for row in calls
                    if str(row.get("judge_role") or "unknown") == role
                ),
                "evaluated_sample_count": len(role_samples.get(role, set())),
                "flagged_sample_count": len(
                    {
                        str(row.get("qa_id") or "")
                        for row in calls
                        if str(row.get("judge_role") or "unknown") == role
                        and row.get("issue_codes")
                    }
                ),
                "issue_counts": dict(
                    sorted(role_issue_counts.get(role, Counter()).items())
                ),
            }
            for role in sorted(role_issue_counts)
        },
        "flagged_by_any_judge": dict(sorted(flagged_any.items())),
        "flagged_by_two_or_more": dict(sorted(flagged_two.items())),
        "confirmed_by_adjudicator": dict(
            sorted(adjudicator_confirmed.items())
        ),
        "by_issue": {
            issue: {
                "flagged_by_any_judge": flagged_any.get(issue, 0),
                "flagged_by_two_or_more": flagged_two.get(issue, 0),
                "confirmed_by_adjudicator": adjudicator_confirmed.get(issue, 0),
            }
            for issue in all_issues
        },
    }


def _unresolved_adjudication_report(
    items: list[dict[str, Any]],
    quality_config: dict[str, Any],
) -> dict[str, Any]:
    routing = quality_config.get("judge_routing") or {}
    total_threshold = float(
        routing.get("total_score_disagreement_threshold", 12)
    )
    dimension_threshold = float(
        routing.get("dimension_disagreement_threshold", 2)
    )
    counts = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    unresolved_count = 0
    for item in items:
        disagreement = item.get("judge_disagreement") or {}
        if not disagreement.get("requires_adjudication"):
            continue
        unresolved_count += 1
        reasons: list[str] = []
        if disagreement.get("total_score_disagreement") or float(
            disagreement.get("total_score_range") or 0
        ) >= total_threshold:
            reasons.append("total_score_disagreement")
        if disagreement.get("dimension_disagreement") or float(
            disagreement.get("maximum_dimension_range") or 0
        ) >= dimension_threshold:
            reasons.append("dimension_disagreement")
        if disagreement.get("low_confidence_roles"):
            reasons.append("low_confidence")
        if disagreement.get("fatal_disagreement"):
            reasons.append("fatal_disagreement")
        if disagreement.get("missing_dimensions"):
            reasons.append("missing_dimensions")
        if (
            disagreement.get("adversarial_review_required")
            and not disagreement.get("adversarial_review_completed")
        ):
            reasons.append("adjudicator_pending")
        if disagreement.get("adversarial_resolution_errors"):
            reasons.append("adjudicator_contract_or_resolution_error")
        if disagreement.get("escalate_to_human"):
            reasons.append("adjudicator_escalation")
        if not reasons:
            reasons.append("unclassified_unresolved")
        for reason in sorted(set(reasons)):
            counts[reason] += 1
            if len(examples[reason]) < 20:
                examples[reason].append(str(item.get("qa_id") or ""))
        if len(set(reasons)) > 1:
            counts["multiple_reasons"] += 1

    return {
        "unresolved_count": unresolved_count,
        "reason_counts": dict(sorted(counts.items())),
        "reason_example_qa_ids": {
            key: value for key, value in sorted(examples.items())
        },
        "disagreement_contract_note": (
            "V2 base judges own disjoint dimensions. Total-score and same-"
            "dimension vote disagreement are retained only for legacy runs; "
            "adversarial downgrade and routing reasons are reported separately."
        ),
    }


def _adjudication_report(items: list[dict[str, Any]]) -> dict[str, Any]:
    resolution_counts = Counter()
    transitions = Counter()
    base_scores: list[float] = []
    final_scores: list[float] = []
    score_deltas: list[float] = []
    required_count = 0
    completed_count = 0
    downgraded_item_count = 0
    for item in items:
        disagreement = item.get("judge_disagreement") or {}
        trace = disagreement.get("adjudication_trace") or {}
        if disagreement.get("adversarial_review_required"):
            required_count += 1
        if disagreement.get("adversarial_review_completed"):
            completed_count += 1
        decisions = [
            str(row.get("decision") or "")
            for row in (trace.get("adversarial_resolutions") or {}).values()
        ]
        resolution_counts.update(decision for decision in decisions if decision)
        if "downgrade" in decisions:
            downgraded_item_count += 1
        base = trace.get("base_subjective_quality_score")
        final = trace.get("final_subjective_quality_score")
        delta = trace.get("score_delta")
        if base is not None:
            base_scores.append(float(base))
        if final is not None:
            final_scores.append(float(final))
        if delta is not None:
            score_deltas.append(float(delta))
        base_decision = trace.get("base_threshold_decision")
        final_decision = trace.get("final_decision")
        if base_decision and final_decision:
            transitions[f"{base_decision}->{final_decision}"] += 1
    return {
        "required_count": required_count,
        "completed_count": completed_count,
        "pending_count": max(required_count - completed_count, 0),
        "downgraded_item_count": downgraded_item_count,
        "resolution_decision_counts": dict(sorted(resolution_counts.items())),
        "base_score": _score_summary(base_scores),
        "final_score": _score_summary(final_scores),
        "score_delta": _score_summary(score_deltas),
        "decision_transitions": dict(sorted(transitions.items())),
    }


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
    quarantine_path = out / "judge_disagreement_quarantine.jsonl"
    llm_secondary = (
        ((report.get("policy_note") or "").startswith("Human calibration is temporarily"))
    )
    review_path = out / (
        "llm_secondary_review_queue.jsonl" if llm_secondary
        else "manual_review_queue.jsonl"
    )
    feedback_path = out / "qa_generation_issue_feedback.json"
    hotspots_path = out / "qa_generation_issue_hotspots.csv"
    json_path.write_text(_pretty(report) + "\n", encoding="utf-8")
    feedback_path.write_text(
        _pretty(report["generation_feedback"]) + "\n", encoding="utf-8"
    )
    _write_feedback_csv(
        hotspots_path,
        report["generation_feedback"]["component_hotspots"],
    )
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
    _write_jsonl(
        quarantine_path,
        [
            row
            for row in items
            if row.get("decision") == "quarantined_judge_disagreement"
        ],
    )
    review_rows = []
    for bundle in bundles:
        item = item_by_qa.get(str(bundle["qa_id"]))
        if not item or item.get("decision") != "manual_review":
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
        f"- Dataset Role contract: `{report['dataset_role_contract']['contract_id']}`",
        f"- Training-release eligible: `{report['dataset_role_contract']['training_release_eligible_count']}`",
        f"- Evaluation holdouts excluded from SFT: `{report['dataset_role_contract']['training_release_excluded_count']}`",
        f"- Judge calls passed: `{report['population']['judge_call_success_count']} / {report['population']['judge_call_count']}`",
        f"- Subjective mean: `{report['subjective_quality']['mean']}`",
        f"- Adjudication required: `{report['judge_disagreement']['adjudication_required_count']}`",
        f"- Judge-disagreement quarantine: `{report['risk_router']['quarantined_count']}`",
        "",
        "## Decisions",
        "",
    ]
    lines.extend(
        f"- {key}: {value}" for key, value in report["decision_counts"].items()
    )
    lines.extend(["", "## Issue Codes By Role", ""])
    for role, role_report in report["issue_codes_by_role"].items():
        lines.append(
            f"- {role}: "
            + json.dumps(
                role_report["issue_counts"],
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    lines.extend(["", "## Issue Consensus", ""])
    for level in (
        "flagged_by_any_judge",
        "flagged_by_two_or_more",
        "confirmed_by_adjudicator",
    ):
        lines.append(
            f"- {level}: "
            + json.dumps(
                report["issue_code_consensus"][level],
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    lines.extend(["", "## Generation Feedback", ""])
    feedback = report["generation_feedback"]
    lines.append(
        f"- Samples with at least one issue: "
        f"{feedback['population']['sample_with_issue_count']} / "
        f"{feedback['population']['sample_count']}"
    )
    for row in feedback["recommended_actions"][:20]:
        lines.append(
            f"- [{row['priority']}] {row['issue_code']} -> "
            f"{row['target_component']} / {row['recommended_action']} "
            f"(any={row['flagged_by_any_judge']}, "
            f"consensus={row['flagged_by_two_or_more']}, "
            f"confirmed={row['confirmed_by_adjudicator']})"
        )
    unresolved = report["judge_disagreement"]["unresolved_sources"]
    lines.extend(
        [
            "",
            "## Risk Router",
            "",
            "- Statuses: "
            + json.dumps(
                report["risk_router"]["status_counts"],
                ensure_ascii=False,
                sort_keys=True,
            ),
            f"- Quarantined: {report['risk_router']['quarantined_count']}",
            "",
            "## Unresolved Adjudication",
            "",
            f"- Count: {unresolved['unresolved_count']}",
            "- Reasons: "
            + json.dumps(
                unresolved["reason_counts"],
                ensure_ascii=False,
                sort_keys=True,
            ),
            "",
            "## Adjudication Before And After",
            "",
            f"- Required: {report['adjudication']['required_count']}",
            f"- Completed: {report['adjudication']['completed_count']}",
            f"- Pending: {report['adjudication']['pending_count']}",
            "- Resolutions: "
            + json.dumps(
                report["adjudication"]["resolution_decision_counts"],
                ensure_ascii=False,
                sort_keys=True,
            ),
            "- Decision transitions: "
            + json.dumps(
                report["adjudication"]["decision_transitions"],
                ensure_ascii=False,
                sort_keys=True,
            ),
            "",
            "## Small Slice Warnings",
            "",
        ]
    )
    small_slices = [
        (dimension, name, row["sample_count"])
        for dimension, groups in report["slices"].items()
        for name, row in groups.items()
        if row.get("insufficient_slice_size")
    ]
    if small_slices:
        lines.extend(
            f"- {dimension}/{name}: {count} samples"
            for dimension, name, count in small_slices
        )
    else:
        lines.append("- None")
    lines.extend(["", "## Calibration Status", "", f"- {report['policy_note']}"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [
        str(json_path),
        str(md_path),
        str(items_path),
        str(disagreement_path),
        str(quarantine_path),
        str(review_path),
        str(feedback_path),
        str(hotspots_path),
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


def _write_feedback_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "issue_code",
        "target_component",
        "recommended_action",
        "action_type",
        "template_id",
        "pattern_id",
        "operation_macro",
        "metric_pair",
        "generation_pipeline",
        "language",
        "population_count",
        "flagged_by_any_judge",
        "flagged_by_two_or_more",
        "confirmed_by_adjudicator",
        "affected_rate_within_component",
        "correctness_gate",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
