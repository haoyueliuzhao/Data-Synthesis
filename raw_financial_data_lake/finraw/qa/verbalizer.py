from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol


SENTENCE_PLAN_VERSION = "sentence_plan.v1"

_TONE_PREFIXES = {
    "neutral": "",
    "analyst": "For an analyst review, ",
    "investment_research": "For an investment research review, ",
}
_SENTENCE_FORMS = {"direct_question", "concise_request"}
_CONNECTORS = {
    "preserve": None,
    "then": "then",
    "next": "next",
    "subsequently": "subsequently",
}

_COMPARISON_PATTERN = re.compile(
    r"\b(?:no\s+more\s+than|not\s+above|at\s+most|less\s+than\s+or\s+equal\s+to|"
    r"no\s+less\s+than|not\s+below|at\s+least|greater\s+than\s+or\s+equal\s+to|"
    r"greater\s+than|more\s+than|higher\s+than|above|over|exceed(?:s|ed|ing)?|"
    r"less\s+than|lower\s+than|below|under|equal\s+to|exactly)\b|"
    r"不超过|不高于|至多|小于等于|不低于|不少于|至少|大于等于|高于|超过|大于|低于|少于|小于|等于",
    re.IGNORECASE,
)
_COMPARISON_LEXEMES = {
    "no more than": "lte",
    "not above": "lte",
    "at most": "lte",
    "less than or equal to": "lte",
    "no less than": "gte",
    "not below": "gte",
    "at least": "gte",
    "greater than or equal to": "gte",
    "greater than": "gt",
    "more than": "gt",
    "higher than": "gt",
    "above": "gt",
    "over": "gt",
    "exceeds": "gt",
    "exceeded": "gt",
    "exceeding": "gt",
    "less than": "lt",
    "lower than": "lt",
    "below": "lt",
    "under": "lt",
    "equal to": "eq",
    "exactly": "eq",
    "不超过": "lte",
    "不高于": "lte",
    "至多": "lte",
    "小于等于": "lte",
    "不低于": "gte",
    "不少于": "gte",
    "至少": "gte",
    "大于等于": "gte",
    "高于": "gt",
    "超过": "gt",
    "大于": "gt",
    "低于": "lt",
    "少于": "lt",
    "小于": "lt",
    "等于": "eq",
}
_NUMBER_PATTERN = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")
_OBSERVABLE_OPERATOR_PATTERNS = {
    "filter": re.compile(
        r"\b(?:filter|screen|screening|qualifying|condition(?:s)?)\b|筛选|过滤|条件",
        re.IGNORECASE,
    ),
    "rank": re.compile(
        r"\b(?:rank|ranking|top\s+\d+|bottom\s+\d+|highest|lowest)\b|排名|排行|前\s*\d+|后\s*\d+",
        re.IGNORECASE,
    ),
    "extreme": re.compile(
        r"\b(?:peak|trough|highest|lowest|maximum|minimum|max(?:imum)?|min(?:imum)?)\b|最高|最低|峰值|谷值",
        re.IGNORECASE,
    ),
    "lookup": re.compile(
        r"\b(?:report|lookup|look\s+up|add\s+each|what\s+was)\b|报告|给出|查询|列出",
        re.IGNORECASE,
    ),
}
_RANK_DESC_PATTERN = re.compile(
    r"\b(?:top|highest|largest|greatest|descending)\b|最高|最大|降序|前\s*\d+",
    re.IGNORECASE,
)
_RANK_ASC_PATTERN = re.compile(
    r"\b(?:bottom|lowest|smallest|least|ascending)\b|最低|最小|升序|后\s*\d+",
    re.IGNORECASE,
)
_TOP_K_PATTERNS = (
    re.compile(r"\b(?:top|bottom|first|last)\s+(\d+)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:list|identify|rank|report)\s+(?:the\s+)?(\d+)\s+(?:qualifying\s+)?(?:companies|entities)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:前|后)\s*(\d+)"),
)


class QuestionProvider(Protocol):
    def generate(self, request: dict[str, Any]) -> list[Any]: ...


@dataclass(frozen=True)
class VerbalizationResult:
    question: str
    generation_method: str
    validation: dict[str, Any]


class OpenAICompatibleQuestionProvider:
    """Optional adapter for a configured chat-completions compatible endpoint."""

    def __init__(self, config: dict[str, Any]):
        self.endpoint = str(config.get("endpoint") or "").strip()
        self.model = str(config.get("model") or "").strip()
        key_env = str(config.get("api_key_env") or "OPENAI_API_KEY")
        self.api_key = os.environ.get(key_env, "")
        self.timeout = float(config.get("timeout_seconds", 30))
        if not self.endpoint or not self.model or not self.api_key:
            raise ValueError(
                "LLM endpoint, model, and API key environment variable are required"
            )

    def generate(self, request: dict[str, Any]) -> list[Any]:
        prompt = (
            "Do not write or rewrite the financial question. Select sentence-plan IDs "
            "only from the supplied enum schema. The application will render all semantic "
            "language, slots, comparisons, thresholds, ordering, and top-k values "
            "deterministically. Return JSON only as "
            '{"sentence_plans":[{"plan_version":"sentence_plan.v1",'
            '"tone":...,"sentence_form":...,"connector":...}]}. '
            "Do not return a question, semantic contract, slots, operators, constraints, "
            "numbers, metric names, entity names, or time expressions.\n"
            + json.dumps(request, ensure_ascii=False, sort_keys=True)
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
        }
        http_request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return [
            item for item in parsed.get("sentence_plans", []) if isinstance(item, dict)
        ]


def realize_question(
    canonical_question: str,
    *,
    semantics: dict[str, Any],
    immutable_slots: dict[str, str],
    required_slots: list[str],
    config: dict[str, Any] | None,
    provider: QuestionProvider | None = None,
) -> VerbalizationResult:
    policy = dict(config or {})
    mode = str(policy.get("mode") or "controlled_template")
    base_validation = {
        "answer_exposed_to_generator": False,
        "contract_exposed_to_generator": False,
        "semantic_rendering": "deterministic",
        "required_slots": required_slots,
        "mode": mode,
    }
    semantic_contract = _semantic_contract(semantics, immutable_slots, required_slots)
    if mode != "controlled_llm":
        slot_check = validate_question_roundtrip(
            canonical_question, semantic_contract, trusted_contract=True
        )
        return VerbalizationResult(
            canonical_question,
            "deterministic_template",
            {**base_validation, **slot_check, "fallback_reason": None},
        )
    sentence_plan_errors: list[str] = []
    try:
        effective_provider = provider or OpenAICompatibleQuestionProvider(
            policy.get("llm", {})
        )
        request = {
            "canonical_question": canonical_question,
            "sentence_plan_schema": {
                "plan_version": SENTENCE_PLAN_VERSION,
                "tone": sorted(_TONE_PREFIXES),
                "sentence_form": sorted(_SENTENCE_FORMS),
                "connector": sorted(_CONNECTORS),
            },
            "variant_count": max(int(policy.get("variants", 3)), 1),
        }
        plans = effective_provider.generate(request)
        for candidate_plan in plans:
            plan_check = validate_sentence_plan(candidate_plan)
            if not plan_check["passed"]:
                sentence_plan_errors.extend(plan_check["sentence_plan_errors"])
                continue
            sentence_plan = plan_check["sentence_plan"]
            question = render_sentence_plan(
                canonical_question, sentence_plan, semantic_contract
            )
            slot_check = validate_question_roundtrip(
                question, semantic_contract, trusted_contract=True
            )
            if slot_check["passed"]:
                return VerbalizationResult(
                    question,
                    "controlled_llm_sentence_plan",
                    {
                        **base_validation,
                        **slot_check,
                        "sentence_plan": sentence_plan,
                        "sentence_plan_errors": [],
                        "fallback_reason": None,
                    },
                )
            sentence_plan_errors.extend(slot_check["contract_errors"])
        fallback_reason = "no_llm_sentence_plan_passed_validation"
    except Exception as exc:
        fallback_reason = f"llm_unavailable:{type(exc).__name__}"
    slot_check = validate_question_roundtrip(
        canonical_question, semantic_contract, trusted_contract=True
    )
    return VerbalizationResult(
        canonical_question,
        "deterministic_template_fallback",
        {
            **base_validation,
            **slot_check,
            "sentence_plan_errors": sentence_plan_errors,
            "fallback_reason": fallback_reason,
        },
    )


def validate_sentence_plan(candidate: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(candidate, dict):
        return {
            "passed": False,
            "sentence_plan": None,
            "sentence_plan_errors": ["sentence_plan_not_object"],
        }
    allowed_keys = {"plan_version", "tone", "sentence_form", "connector"}
    unknown_keys = sorted(set(candidate) - allowed_keys)
    if unknown_keys:
        errors.append("sentence_plan_unknown_fields")
    plan = {
        "plan_version": str(candidate.get("plan_version") or ""),
        "tone": str(candidate.get("tone") or ""),
        "sentence_form": str(candidate.get("sentence_form") or ""),
        "connector": str(candidate.get("connector") or ""),
    }
    if plan["plan_version"] != SENTENCE_PLAN_VERSION:
        errors.append("sentence_plan_version_invalid")
    if plan["tone"] not in _TONE_PREFIXES:
        errors.append("sentence_plan_tone_invalid")
    if plan["sentence_form"] not in _SENTENCE_FORMS:
        errors.append("sentence_plan_form_invalid")
    if plan["connector"] not in _CONNECTORS:
        errors.append("sentence_plan_connector_invalid")
    return {
        "passed": not errors,
        "sentence_plan": plan,
        "sentence_plan_errors": errors,
    }


def render_sentence_plan(
    canonical_question: str,
    sentence_plan: dict[str, str],
    semantic_contract: dict[str, Any],
) -> str:
    question = _render_sequence_connector(
        canonical_question.strip(),
        sentence_plan["connector"],
        semantic_contract,
    )
    tone = sentence_plan["tone"]
    sentence_form = sentence_plan["sentence_form"]
    if sentence_form == "concise_request":
        request_prefix = {
            "neutral": "Please answer this question concisely: ",
            "analyst": "Provide a concise analyst answer to this question: ",
            "investment_research": (
                "Provide a concise investment research answer to this question: "
            ),
        }[tone]
        return request_prefix + question
    prefix = _TONE_PREFIXES[tone]
    return prefix + (_lower_initial(question) if prefix else question)


def validate_question_slots(
    question: str, slots: dict[str, str], required_slots: list[str]
) -> dict[str, Any]:
    normalized_question = _normalize(question)
    missing = []
    for slot in required_slots:
        value = str(slots.get(slot) or "").strip()
        if value and _normalize(value) not in normalized_question:
            missing.append(slot)
    return {
        "passed": not missing,
        "missing_slots": missing,
        "checked_slot_count": len(required_slots),
    }


def validate_question_roundtrip(
    variant: Any,
    expected_contract: dict[str, Any],
    *,
    trusted_contract: bool = False,
) -> dict[str, Any]:
    if trusted_contract:
        question = str(variant)
        supplied_contract: dict[str, Any] | None = None
        structured = False
    elif isinstance(variant, dict):
        question = str(variant.get("question") or "")
        supplied_contract = {
            "slot_map": variant.get("slot_map"),
            "operator_id": variant.get("operator_id"),
            "constraints": variant.get("constraints"),
        }
        structured = True
    else:
        question = str(variant or "")
        supplied_contract = None
        structured = False

    required_slots = list(expected_contract.get("required_slots") or [])
    slots = dict(expected_contract.get("slot_map") or {})
    slot_check = validate_question_slots(question, slots, required_slots)
    contract_errors: list[str] = []
    if not trusted_contract:
        if not structured or supplied_contract is None:
            contract_errors.append("missing_structured_contract")
        else:
            if supplied_contract.get("slot_map") != slots:
                contract_errors.append("slot_map_mismatch")
            if supplied_contract.get("operator_id") != expected_contract.get(
                "operator_id"
            ):
                contract_errors.append("operator_id_mismatch")
            if _json_signature(supplied_contract.get("constraints")) != _json_signature(
                expected_contract.get("constraints")
            ):
                contract_errors.append("constraints_mismatch")

    semantic_check = validate_question_semantics(question, expected_contract)
    contract_errors.extend(
        f"question_semantics:{error}" for error in semantic_check["semantic_errors"]
    )
    return {
        **slot_check,
        "passed": slot_check["passed"] and not contract_errors,
        "structured_contract": structured,
        "contract_source": (
            "canonical_operation_plan" if trusted_contract else "generator_claim"
        ),
        "contract_errors": contract_errors,
        "expected_operator_id": expected_contract.get("operator_id"),
        "observed_operator_id": semantic_check.get("observed_operator_id"),
        "question_semantics": semantic_check,
    }


def validate_question_semantics(
    question: str, expected_contract: dict[str, Any]
) -> dict[str, Any]:
    requirements = _semantic_requirements(expected_contract)
    errors: list[str] = []
    observed_comparisons: list[dict[str, Any]] = []

    for requirement in requirements["comparisons"]:
        value = requirement.get("value")
        if value is None:
            continue
        observed = _comparison_near_number(question, value)
        observed_comparisons.append(
            {
                "step_id": requirement.get("step_id"),
                "value": str(value),
                "expected": requirement["comparison"],
                "observed": observed,
            }
        )
        if observed is None:
            errors.append(
                f"{requirement['error_prefix']}_comparison_or_threshold_missing"
            )
        elif observed != requirement["comparison"]:
            errors.append(f"{requirement['error_prefix']}_comparison_mismatch")

    rank_requirement = requirements.get("rank")
    observed_rank: dict[str, Any] | None = None
    if rank_requirement:
        observed_rank = {
            "direction": _rank_direction(question),
            "top_k": _extract_top_k(question),
        }
        expected_direction = rank_requirement.get("direction")
        if expected_direction and observed_rank["direction"] is None:
            errors.append("rank_direction_missing")
        elif expected_direction and observed_rank["direction"] != expected_direction:
            errors.append("rank_direction_mismatch")
        expected_top_k = rank_requirement.get("top_k")
        if expected_top_k is not None and observed_rank["top_k"] is None:
            errors.append("rank_top_k_missing")
        elif expected_top_k is not None and observed_rank["top_k"] != expected_top_k:
            errors.append("rank_top_k_mismatch")

    expected_extreme = requirements.get("extreme_direction")
    observed_extreme = _extreme_direction(question) if expected_extreme else None
    if expected_extreme and observed_extreme is None:
        errors.append("extreme_direction_missing")
    elif expected_extreme and observed_extreme != expected_extreme:
        errors.append("extreme_direction_mismatch")

    expected_order = requirements["operator_order"]
    observed_positions = {
        operator: _operator_position(question, operator)
        for operator in dict.fromkeys(expected_order)
    }
    if len(expected_order) > 1:
        missing = [
            operator
            for operator in expected_order
            if observed_positions[operator] is None
        ]
        if missing:
            errors.extend(f"operator_missing_{operator}" for operator in missing)
        elif any(
            observed_positions[left] >= observed_positions[right]
            for left, right in zip(expected_order, expected_order[1:])
        ):
            errors.append("operator_order_mismatch")

    observed_order = [
        item[0]
        for item in sorted(
            (
                (operator, position)
                for operator, position in observed_positions.items()
                if position is not None
            ),
            key=lambda item: item[1],
        )
    ]
    return {
        "passed": not errors,
        "semantic_errors": errors,
        "expected_operator_order": expected_order,
        "observed_operator_order": observed_order,
        "observed_operator_id": "_then_".join(observed_order) or None,
        "observed_comparisons": observed_comparisons,
        "observed_rank": observed_rank,
        "observed_extreme_direction": observed_extreme,
    }


def _semantic_requirements(contract: dict[str, Any]) -> dict[str, Any]:
    comparisons: list[dict[str, Any]] = []
    operator_order: list[str] = []
    rank: dict[str, Any] | None = None
    extreme_direction: str | None = None

    def add_operator(operator: str) -> None:
        if not operator_order or operator_order[-1] != operator:
            operator_order.append(operator)

    for index, item in enumerate(contract.get("constraints") or []):
        operator = str(item.get("operator") or "")
        params = dict(item.get("params") or {})
        step_id = str(item.get("step_id") or index)
        if operator == "filter":
            comparison = str(params.get("comparison") or params.get("op") or "gt")
            comparisons.append(
                {
                    "step_id": step_id,
                    "comparison": comparison,
                    "value": params.get("value"),
                    "error_prefix": "filter",
                }
            )
            add_operator("filter")
        elif operator == "multi_factor_screen":
            comparisons.extend(
                [
                    {
                        "step_id": step_id,
                        "comparison": "gt",
                        "value": params.get("growth_min_pct"),
                        "error_prefix": "growth_filter",
                    },
                    {
                        "step_id": step_id,
                        "comparison": "lt",
                        "value": params.get("debt_max_pct"),
                        "error_prefix": "debt_filter",
                    },
                ]
            )
            add_operator("filter")
        elif operator == "rank":
            rank = {
                "direction": str(params.get("direction") or "desc"),
                "top_k": _int_or_none(params.get("top_k")),
            }
            add_operator("rank")
        elif operator in {"argmax", "argmin"}:
            extreme_direction = "max" if operator == "argmax" else "min"
            add_operator("extreme")
        elif operator in {"select_by_period", "lookup_ranked_entities"}:
            add_operator("lookup")

    return {
        "comparisons": comparisons,
        "rank": rank,
        "extreme_direction": extreme_direction,
        "operator_order": operator_order,
    }


def _comparison_near_number(question: str, expected_value: Any) -> str | None:
    expected = _decimal_key(expected_value)
    if expected is None:
        return None
    number_matches = [
        match
        for match in _NUMBER_PATTERN.finditer(question)
        if _decimal_key(match.group(0)) == expected
    ]
    comparison_matches = list(_COMPARISON_PATTERN.finditer(question))
    candidates: list[tuple[int, int, str]] = []
    for number_match in number_matches:
        for comparison_match in comparison_matches:
            if comparison_match.end() <= number_match.start():
                distance = number_match.start() - comparison_match.end()
            elif comparison_match.start() >= number_match.end():
                distance = comparison_match.start() - number_match.end()
            else:
                distance = 0
            if distance <= 48:
                lexeme = _normalize(comparison_match.group(0))
                candidates.append(
                    (
                        distance,
                        -len(comparison_match.group(0)),
                        _COMPARISON_LEXEMES[lexeme],
                    )
                )
    if not candidates:
        return None
    return min(candidates)[2]


def _rank_direction(question: str) -> str | None:
    descending = bool(_RANK_DESC_PATTERN.search(question))
    ascending = bool(_RANK_ASC_PATTERN.search(question))
    if descending == ascending:
        return None
    return "desc" if descending else "asc"


def _extreme_direction(question: str) -> str | None:
    maximum = bool(
        re.search(
            r"\b(?:peak|highest|maximum|max)\b|最高|最大|峰值",
            question,
            re.IGNORECASE,
        )
    )
    minimum = bool(
        re.search(
            r"\b(?:trough|lowest|minimum|min)\b|最低|最小|谷值",
            question,
            re.IGNORECASE,
        )
    )
    if maximum == minimum:
        return None
    return "max" if maximum else "min"


def _extract_top_k(question: str) -> int | None:
    values = {
        int(match.group(1))
        for pattern in _TOP_K_PATTERNS
        for match in pattern.finditer(question)
    }
    return next(iter(values)) if len(values) == 1 else None


def _operator_position(question: str, operator: str) -> int | None:
    match = _OBSERVABLE_OPERATOR_PATTERNS[operator].search(question)
    return match.start() if match else None


def _render_sequence_connector(
    canonical_question: str,
    connector_id: str,
    semantic_contract: dict[str, Any],
) -> str:
    connector = _CONNECTORS[connector_id]
    if connector is None:
        return canonical_question
    if len(_semantic_requirements(semantic_contract)["operator_order"]) < 2:
        return canonical_question
    replacements = (
        (r",\s+then\s+", f", {connector} "),
        (
            r",\s+and\s+(?=(?:list|report|add|identify|rank)\b)",
            f", {connector} ",
        ),
        (
            r"\s+and\s+(?=(?:list|report|add)\b)",
            f", {connector} ",
        ),
    )
    for pattern, replacement in replacements:
        rendered, count = re.subn(
            pattern,
            replacement,
            canonical_question,
            count=1,
            flags=re.IGNORECASE,
        )
        if count:
            return rendered
    return canonical_question


def _decimal_key(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value)).normalize()
    except (InvalidOperation, TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _lower_initial(value: str) -> str:
    return value[:1].lower() + value[1:] if value else value


def _semantic_contract(
    semantics: dict[str, Any],
    immutable_slots: dict[str, str],
    required_slots: list[str],
) -> dict[str, Any]:
    plan = semantics.get("operation_plan") or {}
    operators = []
    for index, step in enumerate(plan.get("operators") or []):
        operators.append(
            {
                "position": index,
                "step_id": step.get("step_id"),
                "operator": step.get("operator"),
                "params": _json_ready(step.get("params") or {}),
            }
        )
    operator_id = "_then_".join(
        str(item["operator"]) for item in operators if item.get("operator")
    ) or str(semantics.get("operation") or "lookup")
    return {
        "slot_map": {
            key: immutable_slots[key]
            for key in required_slots
            if key in immutable_slots
        },
        "required_slots": list(required_slots),
        "operator_id": operator_id,
        "constraints": operators,
    }


def _json_ready(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def _json_signature(value: Any) -> str:
    return json.dumps(
        _json_ready(value), sort_keys=True, separators=(",", ":"), default=str
    )


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()
