from __future__ import annotations

import statistics
from collections import Counter
from typing import Any

from finraw.qa.evaluation.contracts import DIMENSIONS
from finraw.qa.evaluation.rubrics import rubric_for_task


def aggregate_judgments(
    bundle: dict[str, Any],
    judge_payloads: list[dict[str, Any]],
    dataset_role: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    if bundle.get("deterministic_gate_status") != "passed":
        return _deterministic_rejection(bundle, dataset_role)
    successful = [row for row in judge_payloads if row.get("status") == "succeeded"]
    if not successful:
        return {
            **_base(bundle, dataset_role),
            "dimension_scores": {},
            "subjective_quality_score": None,
            "standalone_financial_value_score": None,
            "judge_disagreement": {
                "requires_adjudication": True,
                "reason": "no_successful_judges",
            },
            "judge_confidence": 0.0,
            "fatal_flags": [],
            "issue_codes": [],
            "decision": "manual_review",
            "decision_reasons": ["no_successful_judges"],
        }

    task = str(bundle["distribution_label"].get("benchmark_task") or "T2")
    weights = rubric_for_task(task)["weights"]
    dimension_scores = {
        dimension: round(
            float(statistics.median(row["scores"][dimension] for row in successful)),
            6,
        )
        for dimension in DIMENSIONS
    }
    subjective = 100.0 * sum(
        weights[dimension] * (dimension_scores[dimension] - 1) / 4
        for dimension in DIMENSIONS
    )
    judge_totals = [
        100.0
        * sum(
            weights[dimension] * (row["scores"][dimension] - 1) / 4
            for dimension in DIMENSIONS
        )
        for row in successful
    ]
    maximum_dimension_disagreement = max(
        (
            max(row["scores"][dimension] for row in successful)
            - min(row["scores"][dimension] for row in successful)
            for dimension in DIMENSIONS
        ),
        default=0,
    )
    total_disagreement = max(judge_totals, default=0) - min(
        judge_totals, default=0
    )
    fatal_counts = Counter(
        flag for row in successful for flag in row.get("fatal_flags") or []
    )
    confirmed_fatal = sorted(flag for flag, count in fatal_counts.items() if count >= 2)
    all_fatal = sorted(fatal_counts)
    fatal_disagreement = bool(all_fatal) and not confirmed_fatal
    confidence = round(
        sum(float(row.get("confidence") or 0) for row in successful)
        / len(successful),
        6,
    )
    routing = policy.get("judge_routing") or {}
    requires_adjudication = (
        total_disagreement
        >= float(routing.get("total_score_disagreement_threshold", 12))
        or maximum_dimension_disagreement
        >= int(routing.get("dimension_disagreement_threshold", 2))
        or confidence < float(routing.get("minimum_confidence", 0.7))
        or fatal_disagreement
    )
    disagreement = {
        "judge_count": len(successful),
        "total_score_range": round(total_disagreement, 6),
        "maximum_dimension_range": maximum_dimension_disagreement,
        "fatal_flag_disagreement": fatal_disagreement,
        "requires_adjudication": requires_adjudication,
    }
    successful_roles = {str(row.get("judge_role")) for row in successful}
    replacement_mode = str(
        (policy.get("calibration") or {}).get("replacement_mode") or "human"
    )
    secondary_role = str(
        (policy.get("judge_routing") or {}).get("adjudicator")
        or "adversarial_reviewer"
    )
    secondary_pending = (
        replacement_mode == "llm_secondary_review"
        and secondary_role not in successful_roles
    )
    decision, reasons = _decision(
        subjective,
        confirmed_fatal,
        all_fatal,
        requires_adjudication,
        float(dataset_role.get("dataset_role_value_score") or 0),
        policy,
        secondary_pending=secondary_pending,
        secondary_completed=secondary_role in successful_roles,
    )
    return {
        **_base(bundle, dataset_role),
        "dimension_scores": dimension_scores,
        "subjective_quality_score": round(subjective, 6),
        "standalone_financial_value_score": round(
            25 * (dimension_scores["standalone_financial_value"] - 1), 6
        ),
        "judge_disagreement": disagreement,
        "judge_confidence": confidence,
        "fatal_flags": all_fatal,
        "confirmed_fatal_flags": confirmed_fatal,
        "issue_codes": sorted(
            {code for row in successful for code in row.get("issue_codes") or []}
        ),
        "decision": decision,
        "decision_reasons": reasons,
    }


def needs_adjudication(item: dict[str, Any]) -> bool:
    return bool(item.get("judge_disagreement", {}).get("requires_adjudication")) or item.get(
        "decision"
    ) in {"manual_review", "llm_secondary_review"}


def _decision(
    score: float,
    confirmed_fatal: list[str],
    all_fatal: list[str],
    disagreement: bool,
    dataset_role_value: float,
    policy: dict[str, Any],
    *,
    secondary_pending: bool = False,
    secondary_completed: bool = False,
) -> tuple[str, list[str]]:
    thresholds = policy.get("decision_thresholds") or {}
    accepted = float(thresholds.get("accepted", 80))
    coverage = float(thresholds.get("coverage_acceptance", 70))
    review = float(thresholds.get("manual_review", 60))
    if confirmed_fatal:
        return "rejected_subjective_fatal", [
            "confirmed_fatal_flags=" + ",".join(confirmed_fatal)
        ]
    if secondary_pending:
        return "llm_secondary_review", ["llm_secondary_review_required"]
    if secondary_completed and (all_fatal or disagreement):
        reasons = ["llm_secondary_review_unresolved"]
        if all_fatal:
            reasons.append("unresolved_fatal_flags=" + ",".join(all_fatal))
        if disagreement:
            reasons.append("judge_disagreement_after_secondary_review")
        return "rejected_llm_review_unresolved", reasons
    if all_fatal or disagreement:
        reasons = []
        if all_fatal:
            reasons.append("unconfirmed_or_disputed_fatal_flags=" + ",".join(all_fatal))
        if disagreement:
            reasons.append("judge_disagreement_requires_adjudication")
        return "manual_review", reasons
    if score >= accepted:
        return "accepted", [f"subjective_quality_score>={accepted:g}"]
    if score >= coverage and dataset_role_value >= coverage:
        return "accepted_for_coverage", [
            f"subjective_quality_score>={coverage:g}",
            f"dataset_role_value_score>={coverage:g}",
        ]
    if score >= review:
        return "manual_review", [f"subjective_quality_score_between_{review:g}_{accepted:g}"]
    return "rejected_subjective_quality", [f"subjective_quality_score<{review:g}"]


def _base(bundle: dict[str, Any], dataset_role: dict[str, Any]) -> dict[str, Any]:
    return {
        "qa_id": bundle["qa_id"],
        "deterministic_gate_status": bundle["deterministic_gate_status"],
        "deterministic_gate_reasons": bundle["deterministic_gate_reasons"],
        "dataset_role_value_score": dataset_role.get("dataset_role_value_score", 0),
        "coverage_contributions": dataset_role.get("coverage_contributions", []),
        "dataset_role_components": dataset_role.get("components", {}),
    }


def _deterministic_rejection(
    bundle: dict[str, Any], dataset_role: dict[str, Any]
) -> dict[str, Any]:
    return {
        **_base(bundle, dataset_role),
        "dimension_scores": {},
        "subjective_quality_score": None,
        "standalone_financial_value_score": None,
        "judge_disagreement": {"requires_adjudication": False},
        "judge_confidence": None,
        "fatal_flags": [],
        "issue_codes": [],
        "decision": "rejected_deterministic",
        "decision_reasons": list(bundle.get("deterministic_gate_reasons") or []),
    }
