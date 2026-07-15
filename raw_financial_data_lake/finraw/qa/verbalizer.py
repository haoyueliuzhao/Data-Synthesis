from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


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
            raise ValueError("LLM endpoint, model, and API key environment variable are required")

    def generate(self, request: dict[str, Any]) -> list[Any]:
        prompt = (
            "Rewrite the canonical financial question into diverse analyst-style English. "
            "Preserve every immutable slot and the exact operator order, parameters, "
            "threshold directions, scope, and time semantics. Do not add facts. Return "
            "JSON only as {\"questions\":[{\"question\":...,\"slot_map\":...,"
            "\"operator_id\":...,\"constraints\":[...]}]}; copy the supplied semantic "
            "contract fields exactly.\n"
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
            item
            for item in parsed.get("questions", [])
            if isinstance(item, dict) and str(item.get("question") or "").strip()
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
        "required_slots": required_slots,
        "mode": mode,
    }
    semantic_contract = _semantic_contract(
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
            "semantic_contract": semantic_contract,
            "variant_count": max(int(policy.get("variants", 3)), 1),
        }
        variants = effective_provider.generate(request)
        for variant in variants:
            slot_check = validate_question_roundtrip(variant, semantic_contract)
            if slot_check["passed"]:
                return VerbalizationResult(
                    str(variant["question"]),
                    "controlled_llm",
                    {**base_validation, **slot_check, "fallback_reason": None},
                )
        fallback_reason = "no_llm_variant_passed_slot_roundtrip"
    except Exception as exc:
        fallback_reason = f"llm_unavailable:{type(exc).__name__}"
    slot_check = validate_question_roundtrip(
        canonical_question, semantic_contract, trusted_contract=True
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


def validate_question_roundtrip(
    variant: Any,
    expected_contract: dict[str, Any],
    *,
    trusted_contract: bool = False,
) -> dict[str, Any]:
    if trusted_contract:
        question = str(variant)
        supplied_contract = expected_contract
        structured = True
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
        supplied_contract = {}
        structured = False

    required_slots = list(expected_contract.get("required_slots") or [])
    slots = dict(expected_contract.get("slot_map") or {})
    slot_check = validate_question_slots(question, slots, required_slots)
    contract_errors: list[str] = []
    if not structured:
        contract_errors.append("missing_structured_contract")
    if supplied_contract.get("slot_map") != slots:
        contract_errors.append("slot_map_mismatch")
    if supplied_contract.get("operator_id") != expected_contract.get("operator_id"):
        contract_errors.append("operator_id_mismatch")
    if _json_signature(supplied_contract.get("constraints")) != _json_signature(
        expected_contract.get("constraints")
    ):
        contract_errors.append("constraints_mismatch")
    return {
        **slot_check,
        "passed": slot_check["passed"] and not contract_errors,
        "structured_contract": structured,
        "contract_errors": contract_errors,
        "expected_operator_id": expected_contract.get("operator_id"),
        "observed_operator_id": supplied_contract.get("operator_id"),
    }


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
