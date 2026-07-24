from __future__ import annotations

from typing import Any


RUBRIC_VERSION = "financial_qa_quality.v2"
EVALUATION_SYSTEM_VERSION = "financial_qa_evaluation.v2.2"

DIMENSIONS = (
    "task_authenticity",
    "standalone_financial_value",
    "financial_semantic_validity",
    "clarity_unambiguity",
    "reasoning_necessity",
    "evidence_scope_fit",
    "answer_rubric_fit",
    "language_quality",
)

JUDGE_ROLES = (
    "surface_financial_analyst",
    "grounded_qa_auditor",
    "adversarial_reviewer",
)

ROLE_DIMENSIONS = {
    "surface_financial_analyst": (
        "task_authenticity",
        "standalone_financial_value",
        "clarity_unambiguity",
        "language_quality",
    ),
    "grounded_qa_auditor": (
        "financial_semantic_validity",
        "reasoning_necessity",
        "evidence_scope_fit",
        "answer_rubric_fit",
    ),
    "adversarial_reviewer": (),
}

ADVERSARIAL_DECISIONS = frozenset({"uphold", "downgrade", "fatal", "escalate"})

FATAL_FLAGS = frozenset(
    {
        "fatal_ambiguity",
        "financial_semantic_invalid",
        "unsupported_evidence_or_scope",
        "ungradable_answer_contract",
        "unsupported_causal_claim",
        "unsupported_forecast_or_recommendation",
    }
)

ISSUE_CODES = frozenset(
    {
        "mechanical_template_language",
        "gratuitous_complexity",
        "low_standalone_value",
        "unnatural_output_instruction",
        "redundant_constraints",
        "weak_followup_logic",
        "overly_trivial",
        "overly_verbose",
        "insufficient_context",
        "metric_pair_weakly_meaningful",
        "time_scope_awkward",
        "scope_definition_unclear",
        "output_instruction_slightly_formulaic",
    }
)

DECISIONS = frozenset(
    {
        "accepted",
        "accepted_for_coverage",
        "manual_review",
        "quarantined_judge_disagreement",
        "rejected_deterministic",
        "rejected_subjective_fatal",
        "rejected_subjective_quality",
    }
)


class JudgeContractError(ValueError):
    """Raised when a judge response does not satisfy the frozen JSON contract."""


def dimensions_for_role(role: str) -> tuple[str, ...]:
    if role not in ROLE_DIMENSIONS:
        raise JudgeContractError(f"Unknown judge role: {role}")
    return ROLE_DIMENSIONS[role]


def normalize_judge_payload(
    payload: dict[str, Any], role: str | None = None
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise JudgeContractError("Judge response must be a JSON object")
    if role == "adversarial_reviewer":
        raise JudgeContractError("Adversarial reviewer must use its resolution contract")
    raw_scores = payload.get("scores")
    if not isinstance(raw_scores, dict):
        raise JudgeContractError("scores must be an object")
    expected_dimensions = DIMENSIONS if role is None else dimensions_for_role(role)
    missing = sorted(set(expected_dimensions) - set(raw_scores))
    unknown = sorted(set(raw_scores) - set(expected_dimensions))
    if missing or unknown:
        raise JudgeContractError(
            f"Score dimensions mismatch; missing={missing}, unknown={unknown}"
        )
    scores: dict[str, int] = {}
    for dimension in expected_dimensions:
        value = raw_scores[dimension]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise JudgeContractError(f"{dimension} must be an integer from 1 to 5")
        if int(value) != value or not 1 <= int(value) <= 5:
            raise JudgeContractError(f"{dimension} must be an integer from 1 to 5")
        scores[dimension] = int(value)

    fatal_flags = _bounded_string_list(payload.get("fatal_flags"), "fatal_flags")
    invalid_fatal = sorted(set(fatal_flags) - FATAL_FLAGS)
    if invalid_fatal:
        raise JudgeContractError(f"Unknown fatal flags: {invalid_fatal}")

    issue_codes = [
        item.casefold().strip().replace(" ", "_")
        for item in _bounded_string_list(payload.get("issue_codes"), "issue_codes")
    ]
    invalid_issues = sorted(set(issue_codes) - ISSUE_CODES)
    if invalid_issues:
        raise JudgeContractError(f"Unknown issue codes: {invalid_issues}")

    confidence = payload.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise JudgeContractError("confidence must be a number from 0 to 1")
    confidence = float(confidence)
    if not 0 <= confidence <= 1:
        raise JudgeContractError("confidence must be a number from 0 to 1")

    justification = payload.get("brief_justification") or {}
    if not isinstance(justification, dict):
        raise JudgeContractError("brief_justification must be an object")
    return {
        "rubric_version": str(payload.get("rubric_version") or RUBRIC_VERSION),
        "scores": scores,
        "fatal_flags": sorted(set(fatal_flags)),
        "issue_codes": sorted(set(issue_codes)),
        "confidence": round(confidence, 6),
        "brief_justification": {
            "financial_value": _short_text(justification.get("financial_value")),
            "main_weakness": _short_text(justification.get("main_weakness")),
        },
    }


def normalize_adversarial_payload(
    payload: dict[str, Any], expected_dimensions: list[str] | tuple[str, ...]
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise JudgeContractError("Adversarial response must be a JSON object")
    expected = tuple(dict.fromkeys(str(item) for item in expected_dimensions))
    if not expected or any(item not in DIMENSIONS for item in expected):
        raise JudgeContractError("Adversarial review requires registered dimensions")
    reviewed = tuple(
        _bounded_string_list(payload.get("reviewed_dimensions"), "reviewed_dimensions")
    )
    if set(reviewed) != set(expected):
        raise JudgeContractError(
            "Reviewed dimensions mismatch; "
            f"expected={sorted(expected)}, observed={sorted(reviewed)}"
        )
    raw_resolutions = payload.get("resolutions")
    if not isinstance(raw_resolutions, dict) or set(raw_resolutions) != set(expected):
        raise JudgeContractError(
            "resolutions must cover every reviewed dimension exactly once"
        )
    resolutions: dict[str, dict[str, Any]] = {}
    for dimension in expected:
        raw = raw_resolutions[dimension]
        if not isinstance(raw, dict):
            raise JudgeContractError(f"Resolution for {dimension} must be an object")
        decision = str(raw.get("decision") or "")
        if decision not in ADVERSARIAL_DECISIONS:
            raise JudgeContractError(
                f"Unknown adversarial decision for {dimension}: {decision}"
            )
        score = raw.get("resolved_score")
        if decision in {"uphold", "downgrade"}:
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                raise JudgeContractError(
                    f"{dimension}.resolved_score must be an integer from 1 to 5"
                )
            if int(score) != score or not 1 <= int(score) <= 5:
                raise JudgeContractError(
                    f"{dimension}.resolved_score must be an integer from 1 to 5"
                )
            score = int(score)
        elif score is not None:
            raise JudgeContractError(
                f"{dimension}.resolved_score must be null for {decision}"
            )
        resolutions[dimension] = {
            "decision": decision,
            "resolved_score": score,
            "reason": _short_text(raw.get("reason")),
        }

    issue_codes = [
        item.casefold().strip().replace(" ", "_")
        for item in _bounded_string_list(payload.get("issue_codes"), "issue_codes")
    ]
    invalid_issues = sorted(set(issue_codes) - ISSUE_CODES)
    if invalid_issues:
        raise JudgeContractError(f"Unknown issue codes: {invalid_issues}")

    fatal_flags = _bounded_string_list(
        payload.get("confirmed_fatal_flags"), "confirmed_fatal_flags"
    )
    invalid_fatal = sorted(set(fatal_flags) - FATAL_FLAGS)
    if invalid_fatal:
        raise JudgeContractError(f"Unknown fatal flags: {invalid_fatal}")
    has_fatal_resolution = any(
        item["decision"] == "fatal" for item in resolutions.values()
    )
    if has_fatal_resolution and not fatal_flags:
        raise JudgeContractError(
            "A fatal resolution requires at least one confirmed_fatal_flag"
        )
    if fatal_flags and not has_fatal_resolution:
        raise JudgeContractError(
            "confirmed_fatal_flags require at least one fatal resolution"
        )
    confidence = payload.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise JudgeContractError("confidence must be a number from 0 to 1")
    confidence = float(confidence)
    if not 0 <= confidence <= 1:
        raise JudgeContractError("confidence must be a number from 0 to 1")
    justification = payload.get("brief_justification") or {}
    if not isinstance(justification, dict):
        raise JudgeContractError("brief_justification must be an object")
    escalate = bool(payload.get("escalate_to_human"))
    if any(item["decision"] == "escalate" for item in resolutions.values()):
        escalate = True
    return {
        "rubric_version": str(payload.get("rubric_version") or RUBRIC_VERSION),
        "reviewed_dimensions": list(expected),
        "resolutions": resolutions,
        "scores": {},
        "fatal_flags": sorted(set(fatal_flags)),
        "issue_codes": sorted(set(issue_codes)),
        "confidence": round(confidence, 6),
        "escalate_to_human": escalate,
        "brief_justification": {
            "financial_value": _short_text(justification.get("financial_value")),
            "main_weakness": _short_text(justification.get("main_weakness")),
        },
    }


def judge_response_contract(role: str) -> dict[str, Any]:
    if role == "adversarial_reviewer":
        raise JudgeContractError(
            "Use adversarial_response_contract for adversarial review"
        )
    return {
        "rubric_version": RUBRIC_VERSION,
        "scores": {
            dimension: "integer 1-5" for dimension in dimensions_for_role(role)
        },
        "fatal_flags": sorted(FATAL_FLAGS),
        "issue_codes": sorted(ISSUE_CODES),
        "confidence": "number 0-1",
        "brief_justification": {
            "financial_value": "one short sentence",
            "main_weakness": "one short sentence",
        },
    }


def adversarial_response_contract(reviewed_dimensions: list[str]) -> dict[str, Any]:
    return {
        "rubric_version": RUBRIC_VERSION,
        "reviewed_dimensions": reviewed_dimensions,
        "resolutions": {
            dimension: {
                "decision": "uphold, downgrade, fatal, or escalate",
                "resolved_score": (
                    "integer 1-5 for uphold/downgrade; null otherwise"
                ),
                "reason": "one short sentence",
            }
            for dimension in reviewed_dimensions
        },
        "confirmed_fatal_flags": sorted(FATAL_FLAGS),
        "issue_codes": sorted(ISSUE_CODES),
        "confidence": "number 0-1",
        "escalate_to_human": "boolean",
        "brief_justification": {
            "financial_value": "one short sentence",
            "main_weakness": "one short sentence",
        },
    }


def _bounded_string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise JudgeContractError(f"{field} must be a list of strings")
    if len(value) > 20:
        raise JudgeContractError(f"{field} contains too many entries")
    return [item.strip() for item in value if item.strip()]


def _short_text(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) > 600:
        raise JudgeContractError("brief justification entries must be <= 600 chars")
    return text
