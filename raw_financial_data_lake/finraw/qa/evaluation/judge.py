from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from finraw.llm_client import LLMClientError, OpenAICompatibleJsonClient
from finraw.qa.evaluation.contracts import (
    JUDGE_ROLES,
    JudgeContractError,
    adversarial_response_contract,
    judge_response_contract,
    normalize_adversarial_payload,
    normalize_judge_payload,
)


JudgeFunction = Callable[
    [str, dict[str, Any], dict[str, Any]], tuple[dict[str, Any], dict[str, Any]]
]


class FinancialQualityJudge:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._clients: dict[str, OpenAICompatibleJsonClient] = {}

    def evaluate(
        self,
        role: str,
        view: dict[str, Any],
        rubric: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if role not in JUDGE_ROLES:
            raise ValueError(f"Unknown quality judge role: {role}")
        reviewed_dimensions = list(view.get("reviewed_dimensions") or [])
        prompt = build_judge_prompt(role, view, rubric)
        client = self._client(role)
        max_attempts = max(int(self.config.get("max_contract_attempts", 2)), 1)
        failures = []
        for attempt in range(1, max_attempts + 1):
            try:
                attempt_prompt = _contract_repair_prompt(prompt, failures)
                completion = client.complete_json(attempt_prompt, temperature=0.0)
                payload = (
                    normalize_adversarial_payload(
                        completion.payload, reviewed_dimensions
                    )
                    if role == "adversarial_reviewer"
                    else normalize_judge_payload(completion.payload, role)
                )
                return payload, {
                    **completion.telemetry,
                    "contract_attempt": attempt,
                    "contract_failure_count": len(failures),
                    "input_view_hash": _hash(view),
                    "base_prompt_hash": _hash(prompt),
                    "prompt_hash": _hash(attempt_prompt),
                }
            except (JudgeContractError, LLMClientError) as exc:
                telemetry = getattr(exc, "telemetry", {})
                failures.append(
                    {
                        "attempt": attempt,
                        "error_type": type(exc).__name__,
                        "message": str(exc)[:500],
                        "telemetry": telemetry,
                    }
                )
        raise QualityJudgeError(
            f"Judge {role} failed its structured contract",
            {
                "role": role,
                "failures": failures,
                "input_view_hash": _hash(view),
                "prompt_hash": _hash(prompt),
            },
        )

    def _client(self, role: str) -> OpenAICompatibleJsonClient:
        if role not in self._clients:
            shared = dict(self.config.get("llm") or {})
            shared.update(dict((self.config.get("judges") or {}).get(role) or {}))
            self._clients[role] = OpenAICompatibleJsonClient(shared)
        return self._clients[role]


class QualityJudgeError(RuntimeError):
    def __init__(self, message: str, telemetry: dict[str, Any]):
        super().__init__(message)
        self.telemetry = telemetry


def build_judge_prompt(
    role: str, view: dict[str, Any], rubric: dict[str, Any]
) -> str:
    focus = {
        "surface_financial_analyst": (
            "Assess only the user-facing question: authenticity, clarity, naturalness, "
            "standalone financial usefulness, and template artifacts. Do not guess the "
            "answer and do not reward complexity by itself."
        ),
        "grounded_qa_auditor": (
            "Assess whether the financial semantics, operation sequence, evidence scope, "
            "and answer/rubric contract fit the question. Do not recompute or score numeric "
            "correctness; deterministic validation owns that decision."
        ),
        "adversarial_reviewer": (
            "Resolve only the listed disputed dimensions. Do not rescore unrelated "
            "dimensions. Uphold the provisional score, downgrade it, confirm a fatal "
            "defect, or escalate when the supplied evidence cannot resolve the dispute."
        ),
    }[role]
    request = {
        "judge_role": role,
        "focus": focus,
        "rubric": rubric,
        "input_view": view,
        "response_contract": (
            adversarial_response_contract(list(view.get("reviewed_dimensions") or []))
            if role == "adversarial_reviewer"
            else judge_response_contract(role)
        ),
        "rules": [
            "Return one JSON object only.",
            (
                "Resolve every reviewed dimension exactly once and do not add dimensions."
                if role == "adversarial_reviewer"
                else "Score only the dimensions assigned to this role, exactly once."
            ),
            "Use only listed fatal flags and issue codes.",
            "Do not disclose chain-of-thought; provide only two brief justifications.",
            "Never infer that a generation pipeline or a longer question is higher quality.",
        ],
    }
    return "Evaluate this financial QA item.\n" + json.dumps(
        request, ensure_ascii=False, sort_keys=True
    )


def _contract_repair_prompt(prompt: str, failures: list[dict[str, Any]]) -> str:
    if not failures:
        return prompt
    failure = failures[-1]
    return (
        prompt
        + "\n\nCONTRACT REPAIR REQUIRED. The previous response was rejected: "
        + str(failure.get("message") or failure.get("error_type") or "invalid contract")
        + ". Return exactly one JSON object matching response_contract. Do not add "
        + "markdown, commentary, missing fields, or unregistered fields."
    )


def _hash(value: Any) -> str:
    payload = (
        value
        if isinstance(value, str)
        else json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
