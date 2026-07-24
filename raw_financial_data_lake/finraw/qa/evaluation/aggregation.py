from __future__ import annotations

from typing import Any

from finraw.qa.evaluation.contracts import DIMENSIONS, ROLE_DIMENSIONS
from finraw.qa.evaluation.rubrics import rubric_for_task


ADVERSARIAL_ROLE = "adversarial_reviewer"


def aggregate_judgments(
    bundle: dict[str, Any],
    judge_payloads: list[dict[str, Any]],
    dataset_role: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    if bundle.get("deterministic_gate_status") != "passed":
        return _deterministic_rejection(bundle, dataset_role)

    successful = [row for row in judge_payloads if row.get("status") == "succeeded"]
    base_rows = [
        row for row in successful if str(row.get("judge_role")) != ADVERSARIAL_ROLE
    ]
    reviewer = next(
        (
            row
            for row in successful
            if str(row.get("judge_role")) == ADVERSARIAL_ROLE
        ),
        None,
    )
    if not base_rows:
        return _missing_judges(bundle, dataset_role, "no_successful_base_judges")

    dimension_scores: dict[str, float] = {}
    dimension_owners: dict[str, str] = {}
    for row in base_rows:
        role = str(row.get("judge_role"))
        allowed = set(ROLE_DIMENSIONS.get(role) or ())
        for dimension, score in (row.get("scores") or {}).items():
            if dimension in allowed:
                dimension_scores[dimension] = float(score)
                dimension_owners[dimension] = role

    missing_dimensions = sorted(set(DIMENSIONS) - set(dimension_scores))
    base_fatal_flags = sorted(
        {
            flag
            for row in base_rows
            for flag in (row.get("fatal_flags") or [])
        }
    )
    issue_codes = sorted(
        {
            code
            for row in successful
            for code in (row.get("issue_codes") or [])
        }
    )
    routing = policy.get("judge_routing") or {}
    minimum_confidence = float(routing.get("minimum_confidence", 0.7))
    low_confidence_roles = sorted(
        str(row.get("judge_role"))
        for row in base_rows
        if float(row.get("confidence") or 0) < minimum_confidence
    )
    review_dimensions = _review_dimensions(
        dimension_scores,
        dimension_owners,
        base_rows,
        base_fatal_flags,
        routing,
    )

    base_dimension_scores = dict(dimension_scores)
    resolution_errors: list[str] = []
    confirmed_fatal: list[str] = []
    escalated = False
    resolved_dimensions: list[str] = []
    if reviewer:
        expected = set(review_dimensions)
        reviewed = set(str(item) for item in reviewer.get("reviewed_dimensions") or [])
        if reviewed != expected:
            resolution_errors.append("adversarial_review_dimension_mismatch")
        for dimension, resolution in (reviewer.get("resolutions") or {}).items():
            if dimension not in expected or dimension not in dimension_scores:
                resolution_errors.append(
                    f"unexpected_adversarial_resolution:{dimension}"
                )
                continue
            decision = str(resolution.get("decision") or "")
            resolved_score = resolution.get("resolved_score")
            provisional = float(dimension_scores[dimension])
            if decision == "uphold":
                if float(resolved_score) != provisional:
                    resolution_errors.append(
                        f"uphold_score_mismatch:{dimension}"
                    )
                    continue
                resolved_dimensions.append(dimension)
            elif decision == "downgrade":
                if float(resolved_score) > provisional:
                    resolution_errors.append(
                        f"adversarial_score_increase:{dimension}"
                    )
                    continue
                dimension_scores[dimension] = float(resolved_score)
                resolved_dimensions.append(dimension)
            elif decision == "fatal":
                resolved_dimensions.append(dimension)
            elif decision == "escalate":
                escalated = True
                resolved_dimensions.append(dimension)
            else:
                resolution_errors.append(
                    f"unknown_adversarial_resolution:{dimension}"
                )
        confirmed_fatal = sorted(set(reviewer.get("fatal_flags") or []))
        escalated = escalated or bool(reviewer.get("escalate_to_human"))
        if set(resolved_dimensions) != expected:
            resolution_errors.append("adversarial_resolution_incomplete")

    review_required = bool(
        missing_dimensions
        or low_confidence_roles
        or base_fatal_flags
        or review_dimensions
    )
    reviewer_pending = bool(review_dimensions) and reviewer is None
    unresolved = bool(
        missing_dimensions
        or resolution_errors
        or escalated
        or (review_required and not review_dimensions)
    )
    if reviewer and review_dimensions and not resolution_errors and not escalated:
        review_required = False

    task = str(bundle["distribution_label"].get("benchmark_task") or "T2")
    weights = rubric_for_task(task)["weights"]
    base_subjective = _subjective_score(
        base_dimension_scores, weights, missing_dimensions
    )
    subjective = _subjective_score(
        dimension_scores, weights, missing_dimensions
    )

    confidences = [
        float(row.get("confidence") or 0)
        for row in base_rows + ([reviewer] if reviewer else [])
    ]
    confidence = round(sum(confidences) / len(confidences), 6)
    replacement_mode = str(
        (policy.get("calibration") or {}).get("replacement_mode") or "human"
    )
    base_decision, _ = _decision(
        base_subjective,
        [],
        False,
        False,
        float(dataset_role.get("dataset_role_value_score") or 0),
        bool(dataset_role.get("training_release_eligible")),
        policy,
        replacement_mode=replacement_mode,
    )
    decision, reasons = _decision(
        subjective,
        confirmed_fatal,
        unresolved,
        reviewer_pending,
        float(dataset_role.get("dataset_role_value_score") or 0),
        bool(dataset_role.get("training_release_eligible")),
        policy,
        replacement_mode=replacement_mode,
    )
    risk_router_status = _risk_router_status(
        review_required=bool(review_dimensions),
        reviewer_pending=reviewer_pending,
        reviewer_completed=reviewer is not None,
        unresolved=unresolved,
        replacement_mode=replacement_mode,
    )
    disagreement = {
        "base_role_count": len(base_rows),
        "dimension_owners": dimension_owners,
        "missing_dimensions": missing_dimensions,
        "low_confidence_roles": low_confidence_roles,
        "base_fatal_flags": base_fatal_flags,
        "reviewed_dimensions": sorted(review_dimensions),
        "resolved_dimensions": sorted(set(resolved_dimensions)),
        "adversarial_review_required": bool(review_dimensions),
        "adversarial_review_completed": reviewer is not None,
        "adversarial_resolution_errors": sorted(set(resolution_errors)),
        "escalate_to_human": escalated,
        "requires_adjudication": reviewer_pending or unresolved,
        "risk_router_status": risk_router_status,
        "disagreement_policy": "role_specific_dimensions_v2",
        "total_score_disagreement": False,
        "dimension_disagreement": False,
        "fatal_disagreement": bool(base_fatal_flags) and not bool(
            confirmed_fatal
        ),
        "adjudication_trace": {
            "base_dimension_scores": {
                key: int(value)
                if float(value).is_integer()
                else round(value, 6)
                for key, value in sorted(base_dimension_scores.items())
            },
            "base_subjective_quality_score": (
                round(base_subjective, 6)
                if base_subjective is not None
                else None
            ),
            "base_threshold_decision": base_decision,
            "adversarial_resolutions": (
                dict(reviewer.get("resolutions") or {}) if reviewer else {}
            ),
            "final_dimension_scores": {
                key: int(value)
                if float(value).is_integer()
                else round(value, 6)
                for key, value in sorted(dimension_scores.items())
            },
            "final_subjective_quality_score": (
                round(subjective, 6) if subjective is not None else None
            ),
            "final_decision": decision,
            "score_delta": (
                round(subjective - base_subjective, 6)
                if subjective is not None and base_subjective is not None
                else None
            ),
        },
    }
    return {
        **_base(bundle, dataset_role),
        "dimension_scores": {
            key: int(value) if float(value).is_integer() else round(value, 6)
            for key, value in sorted(dimension_scores.items())
        },
        "subjective_quality_score": (
            round(subjective, 6) if subjective is not None else None
        ),
        "standalone_financial_value_score": (
            round(
                25
                * (
                    dimension_scores.get("standalone_financial_value", 1)
                    - 1
                ),
                6,
            )
            if "standalone_financial_value" in dimension_scores
            else None
        ),
        "judge_disagreement": disagreement,
        "judge_confidence": confidence,
        "fatal_flags": sorted(set(base_fatal_flags) | set(confirmed_fatal)),
        "confirmed_fatal_flags": confirmed_fatal,
        "issue_codes": issue_codes,
        "decision": decision,
        "decision_reasons": reasons,
    }


def adjudication_dimensions(item: dict[str, Any]) -> list[str]:
    disagreement = item.get("judge_disagreement") or {}
    return [
        str(item)
        for item in disagreement.get("reviewed_dimensions") or []
    ]


def needs_adjudication(item: dict[str, Any]) -> bool:
    return bool(adjudication_dimensions(item)) and not bool(
        (item.get("judge_disagreement") or {}).get(
            "adversarial_review_completed"
        )
    )


def _review_dimensions(
    scores: dict[str, float],
    owners: dict[str, str],
    rows: list[dict[str, Any]],
    fatal_flags: list[str],
    routing: dict[str, Any],
) -> list[str]:
    threshold = float(routing.get("adversarial_dimension_score_threshold", 3))
    selected = {
        dimension for dimension, score in scores.items() if score <= threshold
    }
    minimum_confidence = float(routing.get("minimum_confidence", 0.7))
    for row in rows:
        if float(row.get("confidence") or 0) < minimum_confidence:
            selected.update(ROLE_DIMENSIONS.get(str(row.get("judge_role"))) or ())
    if fatal_flags:
        selected.update(scores)
    return sorted(selected)


def _risk_router_status(
    *,
    review_required: bool,
    reviewer_pending: bool,
    reviewer_completed: bool,
    unresolved: bool,
    replacement_mode: str,
) -> str:
    if reviewer_pending:
        return "adversarial_challenge_pending"
    if unresolved:
        if replacement_mode == "llm_secondary_review":
            return "quarantined_judge_disagreement"
        return "human_review_required"
    if review_required and reviewer_completed:
        return "adversarial_challenge_resolved"
    return "no_dispute"


def _subjective_score(
    scores: dict[str, float],
    weights: dict[str, float],
    missing_dimensions: list[str],
) -> float | None:
    if missing_dimensions:
        return None
    return 100.0 * sum(
        weights[dimension] * (scores[dimension] - 1) / 4
        for dimension in DIMENSIONS
    )


def _decision(
    score: float | None,
    confirmed_fatal: list[str],
    unresolved: bool,
    reviewer_pending: bool,
    dataset_role_value: float,
    training_release_eligible: bool,
    policy: dict[str, Any],
    *,
    replacement_mode: str,
) -> tuple[str, list[str]]:
    thresholds = policy.get("decision_thresholds") or {}
    accepted = float(thresholds.get("accepted", 80))
    coverage = float(thresholds.get("coverage_acceptance", 70))
    review = float(thresholds.get("manual_review", 60))
    if confirmed_fatal:
        return "rejected_subjective_fatal", [
            "confirmed_fatal_flags=" + ",".join(confirmed_fatal)
        ]
    if reviewer_pending:
        return "manual_review", ["adversarial_challenge_pending"]
    if unresolved or score is None:
        if replacement_mode == "llm_secondary_review":
            return "quarantined_judge_disagreement", [
                "judge_disagreement_unresolved_after_adversarial_challenge"
            ]
        return "manual_review", ["judge_disagreement_requires_human_review"]
    if score >= accepted:
        return "accepted", [f"subjective_quality_score>={accepted:g}"]
    if (
        score >= coverage
        and dataset_role_value >= coverage
        and training_release_eligible
    ):
        return "accepted_for_coverage", [
            f"subjective_quality_score>={coverage:g}",
            f"dataset_role_value_score>={coverage:g}",
        ]
    if score >= review:
        return "manual_review", [
            f"subjective_quality_score_between_{review:g}_{accepted:g}"
        ]
    return "rejected_subjective_quality", [
        f"subjective_quality_score<{review:g}"
    ]


def _missing_judges(
    bundle: dict[str, Any],
    dataset_role: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        **_base(bundle, dataset_role),
        "dimension_scores": {},
        "subjective_quality_score": None,
        "standalone_financial_value_score": None,
        "judge_disagreement": {
            "requires_adjudication": True,
            "reason": reason,
            "reviewed_dimensions": [],
            "risk_router_status": "human_review_required",
        },
        "judge_confidence": 0.0,
        "fatal_flags": [],
        "confirmed_fatal_flags": [],
        "issue_codes": [],
        "decision": "manual_review",
        "decision_reasons": [reason],
    }


def _base(bundle: dict[str, Any], dataset_role: dict[str, Any]) -> dict[str, Any]:
    return {
        "qa_id": bundle["qa_id"],
        "deterministic_gate_status": bundle["deterministic_gate_status"],
        "deterministic_gate_reasons": bundle["deterministic_gate_reasons"],
        "dataset_role_value_score": dataset_role.get("dataset_role_value_score", 0),
        "coverage_contributions": dataset_role.get("coverage_contributions", []),
        "dataset_role_components": {
            **dict(dataset_role.get("components") or {}),
            "dataset_role_policy_version": dataset_role.get(
                "dataset_role_policy_version"
            ),
            "dataset_role_contract_id": dataset_role.get(
                "dataset_role_contract_id"
            ),
            "release_role": dataset_role.get("release_role"),
            "release_exclusion_reason": dataset_role.get(
                "release_exclusion_reason"
            ),
            "signatures": dataset_role.get("signatures", {}),
        },
        "dataset_role_policy_version": dataset_role.get(
            "dataset_role_policy_version"
        ),
        "dataset_role_contract_id": dataset_role.get("dataset_role_contract_id"),
        "training_release_eligible": bool(
            dataset_role.get("training_release_eligible")
        ),
        "release_role": dataset_role.get("release_role"),
        "release_exclusion_reason": dataset_role.get("release_exclusion_reason"),
        "dataset_role_signatures": dataset_role.get("signatures", {}),
    }


def _deterministic_rejection(
    bundle: dict[str, Any], dataset_role: dict[str, Any]
) -> dict[str, Any]:
    return {
        **_base(bundle, dataset_role),
        "dimension_scores": {},
        "subjective_quality_score": None,
        "standalone_financial_value_score": None,
        "judge_disagreement": {
            "requires_adjudication": False,
            "risk_router_status": "not_applicable_deterministic_failure",
        },
        "judge_confidence": None,
        "fatal_flags": [],
        "confirmed_fatal_flags": [],
        "issue_codes": [],
        "decision": "rejected_deterministic",
        "decision_reasons": list(bundle.get("deterministic_gate_reasons") or []),
    }
