from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from finraw.llm_client import LLMClientError, OpenAICompatibleJsonClient


SENTENCE_PLAN_VERSION = "sentence_plan.v1"
QUESTION_REWRITE_VERSION = "question_rewrite.v2"
SURFACE_VARIATION_VERSION = "surface_variation.v1"
QUESTION_PARSER_VERSION = "1.3.0"
QUESTION_PARSER_SUPPORTED_LANGUAGES = ("en", "zh")

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
_PROTECTED_REWRITE_STYLES = {
    "direct": "Use a direct analytical question.",
    "analyst": "Use an analyst-review formulation.",
    "concise": "Use a compact request with minimal filler.",
    "comparative": "Emphasize the filtering and ranking sequence.",
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
_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9_.])-?\d+(?:\.\d+)?(?![A-Za-z0-9_.])")
_OBSERVABLE_OPERATOR_PATTERNS = {
    "filter": re.compile(
        r"\b(?:filter(?:s|ed|ing)?|screen(?:s|ed|ing)?|qualifying|condition(?:s)?)\b|筛选|过滤|条件",
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
_EXTREME_MAX_PATTERN = re.compile(
    r"\b(?:peak|highest|maximum|max)\b|最高|最大|峰值",
    re.IGNORECASE,
)
_EXTREME_MIN_PATTERN = re.compile(
    r"\b(?:trough|lowest|minimum|min)\b|最低|最小|谷值",
    re.IGNORECASE,
)
_PROTECTED_SLOT_PATTERN = re.compile(r"<slot_[a-z0-9_]+>")
_FORBIDDEN_QUESTION_EXTENSION = re.compile(
    r"\b(?:because|caused? by|management quality|forecast|predict|guarantee|"
    r"buy|sell|target price|investment recommendation)\b|"
    r"因为|导致|管理层能力|预测|保证|买入|卖出|目标价|投资建议",
    re.IGNORECASE,
)
_METRIC_SURFACE_ALIASES = {
    "revenue": ("revenue", "sales"),
    "net income": ("net income", "net profit"),
    "operating income": ("operating income", "operating profit"),
    "gross profit": ("gross profit",),
    "total assets": ("total assets", "assets"),
    "total liabilities": ("total liabilities", "liabilities"),
    "net cash provided by used in operating activities": (
        "operating cash flow",
        "cash flow from operations",
    ),
    "operating cash flow": ("operating cash flow", "cash flow from operations"),
    "net margin": ("net margin", "net profit margin"),
    "debt ratio": ("debt ratio", "liabilities-to-assets ratio"),
}


_TOP_K_PATTERNS = (
    re.compile(r"\b(?:top|bottom|first|last)\s+(\d+)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:list|identify|rank|report)\s+(?:the\s+)?(\d+)\s+(?:qualifying\s+)?(?:companies|entities)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:前|后)\s*(\d+)"),
)


def question_parser_manifest(templates: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the immutable parser/template compatibility contract."""
    supported_languages = list(QUESTION_PARSER_SUPPORTED_LANGUAGES)
    template_contracts = sorted(
        (
            {
                "template_id": str(template["template_id"]),
                "language": str(template.get("language") or ""),
                "task_family": str(template.get("task_family") or ""),
                "required_slots": sorted(
                    str(slot) for slot in template.get("required_slots") or []
                ),
            }
            for template in templates
            if str(template.get("language") or "") in supported_languages
        ),
        key=lambda item: item["template_id"],
    )
    supported_template_ids = [item["template_id"] for item in template_contracts]
    all_template_ids = sorted(str(item["template_id"]) for item in templates)
    return {
        "manifest_version": 1,
        "question_parser_version": QUESTION_PARSER_VERSION,
        "supported_languages": supported_languages,
        "supported_template_ids": supported_template_ids,
        "unsupported_template_ids": sorted(
            set(all_template_ids) - set(supported_template_ids)
        ),
        "template_contracts": template_contracts,
        "semantic_capabilities": [
            "comparison_near_threshold",
            "extreme_direction",
            "operator_order",
            "rank_direction",
            "slot_presence",
            "top_k",
        ],
        "comparison_lexemes": dict(sorted(_COMPARISON_LEXEMES.items())),
        "regex_contract": {
            "comparison": _COMPARISON_PATTERN.pattern,
            "number": _NUMBER_PATTERN.pattern,
            "observable_operators": {
                key: pattern.pattern
                for key, pattern in sorted(_OBSERVABLE_OPERATOR_PATTERNS.items())
            },
            "rank_ascending": _RANK_ASC_PATTERN.pattern,
            "rank_descending": _RANK_DESC_PATTERN.pattern,
            "extreme_maximum": _EXTREME_MAX_PATTERN.pattern,
            "extreme_minimum": _EXTREME_MIN_PATTERN.pattern,
            "top_k": [pattern.pattern for pattern in _TOP_K_PATTERNS],
        },
    }


def question_parser_manifest_hash(templates: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        question_parser_manifest(templates),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_question_parser_support(
    template: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    language = str(template.get("language") or "")
    template_id = str(template.get("template_id") or "")
    errors = []
    if language not in set(manifest.get("supported_languages") or []):
        errors.append("unsupported_language")
    if template_id not in set(manifest.get("supported_template_ids") or []):
        errors.append("unsupported_template_id")
    return {
        "passed": not errors,
        "template_id": template_id,
        "language": language,
        "errors": errors,
    }


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
        self.client = OpenAICompatibleJsonClient(config)
        self.last_telemetry: dict[str, Any] = {}

    def generate(self, request: dict[str, Any]) -> list[Any]:
        strategy = str(request.get("generation_strategy") or "sentence_plan")
        if strategy == "protected_rewrite":
            prompt = (
                "Rewrite the protected financial question naturally while preserving its "
                "exact meaning. Every <slot_name> token is immutable: include every "
                "required placeholder exactly once and add no other placeholders, numbers, "
                "entities, metrics, periods, conditions, conclusions, causes, forecasts, "
                "or recommendations. Preserve comparison direction, extrema direction, "
                "top-k, and operation order. Return JSON only as "
                f'{{"rewrites":[{{"rewrite_version":"{QUESTION_REWRITE_VERSION}",'
                '"question_template":"..."}]}. Return distinct concise interrogative '
                "rewrites ending with a question mark.\n"
                + json.dumps(request, ensure_ascii=False, sort_keys=True)
            )
            response_key = "rewrites"
            temperature = 0.7
        else:
            prompt = (
                "Do not write or rewrite the financial question. Select sentence-plan IDs "
                "only from the supplied enum schema. The application will render all "
                "semantic language, slots, comparisons, thresholds, ordering, and top-k "
                "values deterministically. Return JSON only as "
                '{"sentence_plans":[{"plan_version":"sentence_plan.v1",'
                '"tone":...,"sentence_form":...,"connector":...}]}. '
                "Return exactly variant_count distinct plans when possible. Do not return "
                "a question, semantic contract, slots, operators, constraints, numbers, "
                "metric names, entity names, or time expressions.\n"
                + json.dumps(request, ensure_ascii=False, sort_keys=True)
            )
            response_key = "sentence_plans"
            temperature = 0.4
        try:
            completion = self.client.complete_json(prompt, temperature=temperature)
        except LLMClientError as exc:
            self.last_telemetry = dict(exc.telemetry)
            raise
        parsed = completion.payload
        items = [
            item for item in parsed.get(response_key, []) if isinstance(item, dict)
        ]
        self.last_telemetry = {
            **completion.telemetry,
            "generation_strategy": strategy,
            "structured_item_count": len(items),
        }
        return items


def realize_question(
    canonical_question: str,
    *,
    semantics: dict[str, Any],
    immutable_slots: dict[str, str],
    required_slots: list[str],
    config: dict[str, Any] | None,
    provider: QuestionProvider | None = None,
    surface_slots: dict[str, str] | None = None,
    protected_question: str | None = None,
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
    semantic_contract = build_question_contract(
        semantics, immutable_slots, required_slots
    )
    if mode != "controlled_llm":
        slot_check = validate_question_roundtrip(
            canonical_question, semantic_contract, trusted_contract=True
        )
        return VerbalizationResult(
            canonical_question,
            "deterministic_template",
            {**base_validation, **slot_check, "fallback_reason": None},
        )
    strategy = str(policy.get("strategy") or "sentence_plan")
    if strategy == "protected_rewrite":
        return _realize_protected_rewrite(
            canonical_question,
            semantics=semantics,
            canonical_slots=immutable_slots,
            surface_slots=surface_slots or immutable_slots,
            required_slots=required_slots,
            protected_question=protected_question,
            policy=policy,
            provider=provider,
            base_validation=base_validation,
        )
    sentence_plan_errors: list[str] = []
    llm_telemetry: dict[str, Any] = {}
    effective_provider: QuestionProvider | None = None
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
        llm_telemetry = dict(getattr(effective_provider, "last_telemetry", {}) or {})
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
                        "llm_telemetry": {
                            **llm_telemetry,
                            "sentence_plan_valid": True,
                            "controlled_generation": True,
                        },
                    },
                )
            sentence_plan_errors.extend(slot_check["contract_errors"])
        fallback_reason = "no_llm_sentence_plan_passed_validation"
    except Exception as exc:
        if isinstance(exc, LLMClientError):
            llm_telemetry = dict(exc.telemetry)
        elif effective_provider is not None:
            llm_telemetry = dict(
                getattr(effective_provider, "last_telemetry", {}) or {}
            )
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
            "llm_telemetry": {
                **llm_telemetry,
                "sentence_plan_valid": False,
                "controlled_generation": False,
            },
        },
    )


def protected_rewrite_style_ids() -> list[str]:
    return sorted(_PROTECTED_REWRITE_STYLES)


def _realize_protected_rewrite(
    canonical_question: str,
    *,
    semantics: dict[str, Any],
    canonical_slots: dict[str, str],
    surface_slots: dict[str, str],
    required_slots: list[str],
    protected_question: str | None,
    policy: dict[str, Any],
    provider: QuestionProvider | None,
    base_validation: dict[str, Any],
) -> VerbalizationResult:
    effective_provider: QuestionProvider | None = None
    telemetry: dict[str, Any] = {}
    errors: list[str] = []
    protected = protected_question or _protect_question_text(
        canonical_question, canonical_slots, required_slots
    )
    protected_names = sorted(
        {
            token.removeprefix("<slot_").removesuffix(">")
            for token in _PROTECTED_SLOT_PATTERN.findall(protected)
        }
    )
    placeholders = [slot_placeholder(name) for name in protected_names]
    resolved_slots = {
        name: str(surface_slots.get(name) or canonical_slots.get(name) or "")
        for name in protected_names
    }
    style_variant_id = str(policy.get("style_variant_id") or "direct")
    if style_variant_id not in _PROTECTED_REWRITE_STYLES:
        style_variant_id = "direct"
    surface_contract = build_question_contract(
        semantics, resolved_slots, protected_names
    )
    deterministic_surface = render_protected_question(protected, resolved_slots)
    try:
        effective_provider = provider or OpenAICompatibleQuestionProvider(
            policy.get("llm", {})
        )
        request = {
            "generation_strategy": "protected_rewrite",
            "protected_question": protected,
            "required_placeholders": placeholders,
            "rewrite_schema": {
                "rewrite_version": QUESTION_REWRITE_VERSION,
                "allowed_fields": ["rewrite_version", "question_template"],
            },
            "variant_count": max(int(policy.get("variants", 3)), 1),
            "language": str(policy.get("language") or "en"),
            "style_variant_id": style_variant_id,
            "style_instruction": _PROTECTED_REWRITE_STYLES[style_variant_id],
        }
        rewrites = effective_provider.generate(request)
        telemetry = dict(getattr(effective_provider, "last_telemetry", {}) or {})
        indexed_rewrites = list(enumerate(rewrites))
        if indexed_rewrites:
            style_offset = (
                protected_rewrite_style_ids().index(style_variant_id)
                % len(indexed_rewrites)
            )
            indexed_rewrites = (
                indexed_rewrites[style_offset:] + indexed_rewrites[:style_offset]
            )
        for rewrite_variant_index, candidate in indexed_rewrites:
            rewrite_check = validate_protected_rewrite(candidate, placeholders)
            if not rewrite_check["passed"]:
                errors.extend(rewrite_check["rewrite_errors"])
                continue
            question = render_protected_question(
                rewrite_check["question_template"], resolved_slots
            )
            slot_check = validate_question_roundtrip(
                question, surface_contract, trusted_contract=True
            )
            numeric_check = validate_rewrite_numeric_grounding(question, resolved_slots)
            if slot_check["passed"] and numeric_check["passed"]:
                return VerbalizationResult(
                    question,
                    "controlled_llm_protected_rewrite",
                    {
                        **base_validation,
                        **slot_check,
                        "semantic_rendering": "llm_protected_template",
                        "rewrite_version": QUESTION_REWRITE_VERSION,
                        "style_variant_id": style_variant_id,
                        "rewrite_variant_index": rewrite_variant_index,
                        "rewrite_valid": True,
                        "rewrite_errors": [],
                        "protected_question": protected,
                        "surface_slots": resolved_slots,
                        "surface_variation_version": SURFACE_VARIATION_VERSION,
                        "numeric_grounding": numeric_check,
                        "fallback_reason": None,
                        "llm_telemetry": {
                            **telemetry,
                            "sentence_plan_valid": True,
                            "rewrite_valid": True,
                            "controlled_generation": True,
                        },
                    },
                )
            errors.extend(slot_check["contract_errors"])
            errors.extend(numeric_check["errors"])
        fallback_reason = "no_llm_protected_rewrite_passed_validation"
    except Exception as exc:
        if isinstance(exc, LLMClientError):
            telemetry = dict(exc.telemetry)
        elif effective_provider is not None:
            telemetry = dict(getattr(effective_provider, "last_telemetry", {}) or {})
        fallback_reason = f"llm_unavailable:{type(exc).__name__}"

    fallback_check = validate_question_roundtrip(
        deterministic_surface, surface_contract, trusted_contract=True
    )
    return VerbalizationResult(
        deterministic_surface,
        "deterministic_surface_fallback",
        {
            **base_validation,
            **fallback_check,
            "semantic_rendering": "deterministic_surface_template",
            "rewrite_version": QUESTION_REWRITE_VERSION,
            "style_variant_id": style_variant_id,
            "rewrite_valid": False,
            "rewrite_errors": sorted(set(errors)),
            "protected_question": protected,
            "surface_slots": resolved_slots,
            "surface_variation_version": SURFACE_VARIATION_VERSION,
            "numeric_grounding": validate_rewrite_numeric_grounding(
                deterministic_surface, resolved_slots
            ),
            "fallback_reason": fallback_reason,
            "llm_telemetry": {
                **telemetry,
                "sentence_plan_valid": False,
                "rewrite_valid": False,
                "controlled_generation": False,
            },
        },
    )


def slot_placeholder(slot_name: str) -> str:
    normalized = re.sub(r"[^a-z0-9_]+", "_", slot_name.casefold()).strip("_")
    return f"<slot_{normalized}>"


def build_protected_question(template_text: str, slot_names: list[str]) -> str:
    placeholders = {name: slot_placeholder(name) for name in slot_names}
    return template_text.format(**placeholders)


def _protect_question_text(
    question: str,
    slots: dict[str, str],
    required_slots: list[str],
) -> str:
    protected = question
    for slot in sorted(
        required_slots,
        key=lambda name: len(str(slots.get(name) or "")),
        reverse=True,
    ):
        value = str(slots.get(slot) or "").strip()
        if not value:
            continue
        protected, _ = re.subn(
            re.escape(value),
            slot_placeholder(slot),
            protected,
            count=1,
            flags=re.IGNORECASE,
        )
    return protected


def validate_protected_rewrite(
    candidate: Any, required_placeholders: list[str]
) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(candidate, dict):
        return {
            "passed": False,
            "question_template": "",
            "rewrite_errors": ["rewrite_not_object"],
        }
    if set(candidate) - {"rewrite_version", "question_template"}:
        errors.append("rewrite_unknown_fields")
    if str(candidate.get("rewrite_version") or "") != QUESTION_REWRITE_VERSION:
        errors.append("rewrite_version_invalid")
    question_template = str(candidate.get("question_template") or "").strip()
    observed = _PROTECTED_SLOT_PATTERN.findall(question_template)
    if sorted(observed) != sorted(required_placeholders):
        errors.append("rewrite_placeholder_mismatch")
    if len(observed) != len(set(observed)):
        errors.append("rewrite_placeholder_duplicate")
    if _NUMBER_PATTERN.search(question_template):
        errors.append("rewrite_unprotected_number")
    if not question_template.endswith("?") or question_template.count("?") != 1:
        errors.append("rewrite_not_single_question")
    if _FORBIDDEN_QUESTION_EXTENSION.search(question_template):
        errors.append("rewrite_forbidden_extension")
    return {
        "passed": not errors,
        "question_template": question_template,
        "rewrite_errors": errors,
    }


def render_protected_question(
    question_template: str, surface_slots: dict[str, str]
) -> str:
    output = question_template
    for slot, value in sorted(surface_slots.items()):
        output = output.replace(slot_placeholder(slot), str(value))
    return output


def validate_rewrite_numeric_grounding(
    question: str, surface_slots: dict[str, str]
) -> dict[str, Any]:
    allowed = {
        value
        for slot_value in surface_slots.values()
        for value in _NUMBER_PATTERN.findall(str(slot_value))
    }
    observed = set(_NUMBER_PATTERN.findall(question))
    extra = sorted(observed - allowed)
    return {
        "passed": not extra,
        "extra_numbers": extra,
        "errors": ["rewrite_unsupported_number" for _ in extra],
    }


def diversify_surface_slots(
    canonical_slots: dict[str, str],
    semantics: dict[str, Any],
    stable_seed: str,
    config: dict[str, Any] | None,
) -> dict[str, str]:
    policy = dict((config or {}).get("surface_variation") or {})
    if not policy.get("enabled", False):
        return dict(canonical_slots)
    output: dict[str, str] = {}
    for slot, value in canonical_slots.items():
        options = _surface_options(slot, str(value), semantics, policy)
        digest = hashlib.sha256(
            f"{SURFACE_VARIATION_VERSION}|{stable_seed}|{slot}".encode("utf-8")
        ).hexdigest()
        output[slot] = options[int(digest[:8], 16) % len(options)]
    return output


def surface_variation_manifest(config: dict[str, Any] | None) -> dict[str, Any]:
    policy = dict((config or {}).get("surface_variation") or {})
    manifest = {
        "surface_variation_version": SURFACE_VARIATION_VERSION,
        "enabled": bool(policy.get("enabled", False)),
        "entity_suffix_shortening": bool(policy.get("entity_suffix_shortening", True)),
        "metric_aliases": {
            key: list(values) for key, values in sorted(_METRIC_SURFACE_ALIASES.items())
        },
        "period_styles": ["canonical", "fiscal_or_calendar"],
    }
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return {
        **manifest,
        "surface_variation_manifest_hash": hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest(),
    }


def _surface_options(
    slot: str,
    value: str,
    semantics: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:
    options = [value]
    normalized = _normalize(value)
    if slot.startswith("metric") or slot in {
        "ratio",
        "primary_metric",
        "secondary_metric",
        "growth_metric",
        "ranking_metric",
        "debt_metric",
    }:
        options.extend(_METRIC_SURFACE_ALIASES.get(normalized, ()))
    if slot.startswith("entity") and policy.get("entity_suffix_shortening", True):
        shortened = re.sub(
            r",?\\s+(?:inc\\.?|corp\\.?|corporation|company|co\\.?|ltd\\.?|plc)$",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()
        if shortened:
            options.append(shortened)
    if slot in {"period", "previous_period", "start_period", "end_period"}:
        match = re.fullmatch(r"(?:fiscal year\\s+|FY\\s*)?(\\d{4})", value, re.I)
        if match:
            year = match.group(1)
            basis = str(
                (semantics.get("time_scope") or {}).get("basis")
                or semantics.get("time_basis")
                or ""
            )
            options.append(
                f"FY{year}" if "fiscal" in basis else f"calendar year {year}"
            )
    if slot == "frequency" and normalized == "annual":
        options.append("yearly")
    if slot == "extreme":
        if normalized == "highest":
            options.extend(["maximum", "peak"])
        elif normalized == "lowest":
            options.extend(["minimum", "trough"])
    if slot == "scope":
        options.append(
            re.sub(
                r"the explicitly configured data scope",
                "the covered data universe",
                value,
                flags=re.IGNORECASE,
            )
        )
    return list(dict.fromkeys(item for item in options if item))


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
    if "filter" in expected_order and observed_positions.get("filter") is None:
        implicit_filter_positions = [
            _comparison_position_near_number(question, item.get("value"))
            for item in requirements["comparisons"]
            if item.get("value") is not None
        ]
        if implicit_filter_positions and all(
            position is not None for position in implicit_filter_positions
        ):
            observed_positions["filter"] = min(
                int(position)
                for position in implicit_filter_positions
                if position is not None
            )
    if expected_order == ["filter", "rank"] and re.search(
        r"\b(?:after|following)\s+(?:filter(?:ing|ed)?|screen(?:ing|ed)?)\b",
        question,
        re.IGNORECASE,
    ):
        rank_position = observed_positions.get("rank")
        if rank_position is not None:
            observed_positions["filter"] = rank_position - 1
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


def _comparison_position_near_number(
    question: str, expected_value: Any
) -> int | None:
    expected = _decimal_key(expected_value)
    if expected is None:
        return None
    candidates: list[tuple[int, int]] = []
    for number_match in _NUMBER_PATTERN.finditer(question):
        if _decimal_key(number_match.group(0)) != expected:
            continue
        for comparison_match in _COMPARISON_PATTERN.finditer(question):
            if comparison_match.end() <= number_match.start():
                distance = number_match.start() - comparison_match.end()
            elif comparison_match.start() >= number_match.end():
                distance = comparison_match.start() - number_match.end()
            else:
                distance = 0
            if distance <= 48:
                candidates.append((distance, comparison_match.start()))
    return min(candidates)[1] if candidates else None


def _rank_direction(question: str) -> str | None:
    descending_sequence = re.search(
        r"\b(?:highest|largest|greatest)\b.{0,32}\b(?:to|toward)\s+"
        r"(?:the\s+)?(?:lowest|smallest|least)\b",
        question,
        re.IGNORECASE,
    )
    ascending_sequence = re.search(
        r"\b(?:lowest|smallest|least)\b.{0,32}\b(?:to|toward)\s+"
        r"(?:the\s+)?(?:highest|largest|greatest)\b",
        question,
        re.IGNORECASE,
    )
    if bool(descending_sequence) != bool(ascending_sequence):
        return "desc" if descending_sequence else "asc"
    descending = bool(_RANK_DESC_PATTERN.search(question))
    ascending = bool(_RANK_ASC_PATTERN.search(question))
    if descending == ascending:
        return None
    return "desc" if descending else "asc"


def _extreme_direction(question: str) -> str | None:
    maximum = bool(_EXTREME_MAX_PATTERN.search(question))
    minimum = bool(_EXTREME_MIN_PATTERN.search(question))
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
    matches = list(_OBSERVABLE_OPERATOR_PATTERNS[operator].finditer(question))
    if not matches:
        return None
    match = matches[-1] if operator == "rank" else matches[0]
    return match.start()


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


def build_question_contract(
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
