from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


class QuestionProvider(Protocol):
    def generate(self, request: dict[str, Any]) -> list[str]: ...


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
            raise ValueError("LLM endpoint, model, and API key environment variable are required")

    def generate(self, request: dict[str, Any]) -> list[str]:
        prompt = (
            "Rewrite the canonical financial question into diverse analyst-style English. "
            "Preserve every immutable slot exactly, preserve scope/time/operator semantics, "
            "do not add facts, and return JSON only as {\"questions\":[...]}.\n"
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
        return [str(item) for item in parsed.get("questions", []) if str(item).strip()]


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
        "required_slots": required_slots,
        "mode": mode,
    }
    if mode != "controlled_llm":
        slot_check = validate_question_slots(
            canonical_question, immutable_slots, required_slots
        )
        return VerbalizationResult(
            canonical_question,
            "deterministic_template",
            {**base_validation, **slot_check, "fallback_reason": None},
        )
    try:
        effective_provider = provider or OpenAICompatibleQuestionProvider(
            policy.get("llm", {})
        )
        request = {
            "canonical_question": canonical_question,
            "canonical_semantics": _question_safe_semantics(semantics),
            "immutable_slots": {
                key: immutable_slots[key]
                for key in required_slots
                if key in immutable_slots
            },
            "variant_count": max(int(policy.get("variants", 3)), 1),
        }
        variants = effective_provider.generate(request)
        for question in variants:
            slot_check = validate_question_slots(
                question, immutable_slots, required_slots
            )
            if slot_check["passed"]:
                return VerbalizationResult(
                    question,
                    "controlled_llm",
                    {**base_validation, **slot_check, "fallback_reason": None},
                )
        fallback_reason = "no_llm_variant_passed_slot_roundtrip"
    except Exception as exc:
        fallback_reason = f"llm_unavailable:{type(exc).__name__}"
    slot_check = validate_question_slots(
        canonical_question, immutable_slots, required_slots
    )
    return VerbalizationResult(
        canonical_question,
        "deterministic_template_fallback",
        {**base_validation, **slot_check, "fallback_reason": fallback_reason},
    )


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


def _question_safe_semantics(semantics: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "operation",
        "graph_pattern_id",
        "question_intent",
        "entity_names",
        "metric_names",
        "time_scope",
        "scope_type",
        "scope_definition",
        "primary_metric_id",
        "secondary_metric_id",
        "observation_count",
        "frequency",
    }
    return {key: value for key, value in semantics.items() if key in allowed}


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()
