from __future__ import annotations

from typing import Any


RUBRIC_VERSION = "financial_qa_quality.v1"
EVALUATION_SYSTEM_VERSION = "financial_qa_evaluation.v1.0"

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
        "llm_secondary_review",
        "rejected_llm_review_unresolved",
        "rejected_deterministic",
        "rejected_subjective_fatal",
        "rejected_subjective_quality",
    }
)


class JudgeContractError(ValueError):
    """Raised when a judge response does not satisfy the frozen JSON contract."""


def normalize_judge_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise JudgeContractError("Judge response must be a JSON object")
    raw_scores = payload.get("scores")
    if not isinstance(raw_scores, dict):
        raise JudgeContractError("scores must be an object")
    missing = sorted(set(DIMENSIONS) - set(raw_scores))
    unknown = sorted(set(raw_scores) - set(DIMENSIONS))
    if missing or unknown:
        raise JudgeContractError(
            f"Score dimensions mismatch; missing={missing}, unknown={unknown}"
        )
    scores: dict[str, int] = {}
    for dimension in DIMENSIONS:
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
    normalized_justification = {
        "financial_value": _short_text(justification.get("financial_value")),
        "main_weakness": _short_text(justification.get("main_weakness")),
    }
    return {
        "rubric_version": str(payload.get("rubric_version") or RUBRIC_VERSION),
        "scores": scores,
        "fatal_flags": sorted(set(fatal_flags)),
        "issue_codes": sorted(set(issue_codes)),
        "confidence": round(confidence, 6),
        "brief_justification": normalized_justification,
    }


def judge_response_contract() -> dict[str, Any]:
    return {
        "rubric_version": RUBRIC_VERSION,
        "scores": {dimension: "integer 1-5" for dimension in DIMENSIONS},
        "fatal_flags": sorted(FATAL_FLAGS),
        "issue_codes": sorted(ISSUE_CODES),
        "confidence": "number 0-1",
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
