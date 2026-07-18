from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from finraw.analysis.claims import ClaimPlanResult
from finraw.analysis.registry import AnalysisPattern, stable_hash
from finraw.analysis.text_semantics import validate_stance
from finraw.llm_client import LLMClientError, OpenAICompatibleJsonClient

ANALYSIS_GENERATOR_VERSION = "1.2.0"
ANALYSIS_RESPONSE_SCHEMA_VERSION = "analysis_response.v1"


class AnalysisProvider(Protocol):
    last_telemetry: dict[str, Any]

    def generate(self, request: dict[str, Any]) -> dict[str, Any]: ...


class OpenAICompatibleAnalysisProvider:
    def __init__(self, config: dict[str, Any]):
        self.client = OpenAICompatibleJsonClient(config)
        self.last_telemetry: dict[str, Any] = {}

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "You are realizing a bounded financial analysis from a verified claim plan. "
            "Use only the supplied claim IDs, evidence IDs, conclusion IDs, caveats, and "
            "numeric slots. Do not add entities, metrics, periods, causes, forecasts, "
            "recommendations, target prices, or unsupported numbers. Claim sentences must "
            "preserve each claim's stance and acknowledge risk claims as risks. "
            "Return exactly one JSON object with no extra fields and this exact nested shape: "
            '{"schema_version":"analysis_response.v1",'
            '"selected_conclusion_id":"COPY_ONE_ALLOWED_ID",'
            '"claims":[{"claim_id":"COPY_MANDATORY_ID",'
            '"sentence":"NATURAL_LANGUAGE_SENTENCE",'
            '"evidence_ids":["COPY_EXACT_EVIDENCE_ID"]}],'
            '"conclusion_sentence":"NATURAL_LANGUAGE_SENTENCE",'
            '"caveats":[{"caveat_id":"COPY_REQUIRED_CAVEAT_ID",'
            '"sentence":"NATURAL_LANGUAGE_SENTENCE"}]}. '
            "Inside claims, only claim_id, sentence, and evidence_ids are allowed. "
            "Inside caveats, only caveat_id and sentence are allowed. "
            "Do not rename sentence to text, claim_text, content, or analysis. "
            "Every mandatory claim must appear exactly once and every required caveat "
            "must appear as an object.\n"
            + json.dumps(request, ensure_ascii=False, sort_keys=True)
        )
        try:
            completion = self.client.complete_json(prompt, temperature=0.35)
        except LLMClientError as exc:
            self.last_telemetry = dict(exc.telemetry)
            raise
        self.last_telemetry = dict(completion.telemetry)
        return completion.payload


@dataclass(frozen=True)
class AnalysisGenerationResult:
    analysis_text: str
    selected_conclusion_id: str
    conclusion_text: str
    claim_alignment: list[dict[str, Any]]
    caveats: list[dict[str, Any]]
    numeric_slots: list[dict[str, Any]]
    generation_method: str
    generation_metadata: dict[str, Any]


def generate_analysis(
    pattern: AnalysisPattern,
    claim_result: ClaimPlanResult,
    signals: list[dict[str, Any]],
    *,
    config: dict[str, Any] | None,
    provider: AnalysisProvider | None = None,
) -> AnalysisGenerationResult:
    policy = dict(config or {})
    mode = str(policy.get("mode") or "deterministic_claim_plan")
    numeric_slots = list(claim_result.rubric.get("numeric_slots") or [])
    if mode != "controlled_llm":
        return _deterministic_result(
            claim_result, numeric_slots, mode="deterministic_claim_plan_v2"
        )
    mandatory = [claim for claim in claim_result.claims if claim.get("is_required")]
    request = {
        "schema_version": ANALYSIS_RESPONSE_SCHEMA_VERSION,
        "instruction": pattern.instruction_template,
        "signals": [
            {
                "signal_id": row["signal_id"],
                "signal_spec_id": row["signal_spec_id"],
                "direction": row["direction"],
                "strength": row["strength"],
                "payload": {
                    key: value
                    for key, value in dict(row.get("signal_payload") or {}).items()
                    if key != "scope_values"
                },
            }
            for row in signals
        ],
        "mandatory_claims": [
            {
                "claim_id": claim["claim_id"],
                "claim_type": claim["claim_type"],
                "claim_role": claim["claim_role"],
                "claim_polarity": claim["claim_polarity"],
                "evidence_ids": claim["support_signal_ids"],
                "semantic_contract": claim["semantic_contract"],
                "canonical_sentence": claim["sentence"],
            }
            for claim in mandatory
        ],
        "valid_conclusions": claim_result.valid_conclusions,
        "required_caveats": claim_result.caveats,
        "numeric_slots": numeric_slots
        if policy.get("allow_numeric_slots", True)
        else [],
        "forbidden_claim_types": list(pattern.forbidden_claim_types),
    }
    effective_provider: AnalysisProvider | None = None
    attempts: list[dict[str, Any]] = []
    max_attempts = max(1, int(policy.get("max_attempts", 2)))
    try:
        effective_provider = provider or OpenAICompatibleAnalysisProvider(
            policy.get("llm", {})
        )
        for attempt_index in range(1, max_attempts + 1):
            payload = effective_provider.generate(request)
            telemetry = dict(getattr(effective_provider, "last_telemetry", {}) or {})
            validation = validate_analysis_response(payload, claim_result)
            attempts.append(
                {
                    **telemetry,
                    "attempt_index": attempt_index,
                    "structured_response_valid": validation["passed"],
                    "validation_errors": list(validation["errors"]),
                }
            )
            if not validation["passed"]:
                request["repair_context"] = {
                    "previous_validation_errors": list(validation["errors"]),
                    "instruction": (
                        "Regenerate the full object. Preserve every expected claim stance; "
                        "risk and negative claims must explicitly describe a risk, constraint, "
                        "weakness, decline, divergence, or caveat, never support or improvement."
                    ),
                }
                continue
            claims = validation["claims"]
            caveats = validation["caveats"]
            conclusion_text = validation["conclusion_sentence"]
            text = " ".join(
                [item["sentence"] for item in claims]
                + [conclusion_text]
                + [item["sentence"] for item in caveats]
            )
            return AnalysisGenerationResult(
                text,
                validation["selected_conclusion_id"],
                conclusion_text,
                claims,
                caveats,
                numeric_slots,
                "controlled_llm_claim_generation",
                {
                    "generator_version": ANALYSIS_GENERATOR_VERSION,
                    "response_schema_version": ANALYSIS_RESPONSE_SCHEMA_VERSION,
                    "schema_valid": True,
                    "schema_errors": [],
                    "fallback_reason": None,
                    "llm_attempts": attempts,
                    "llm_telemetry": attempts[-1],
                    "request_contract_hash": stable_hash(request),
                },
            )
        fallback_reason = "invalid_analysis_response:" + ",".join(validation["errors"])
    except Exception as exc:
        telemetry: dict[str, Any] = {}
        if isinstance(exc, LLMClientError):
            telemetry = dict(exc.telemetry)
        elif effective_provider is not None:
            telemetry = dict(getattr(effective_provider, "last_telemetry", {}) or {})
        attempts.append(
            {
                **telemetry,
                "attempt_index": len(attempts) + 1,
                "structured_response_valid": False,
                "validation_errors": [f"llm_unavailable:{type(exc).__name__}"],
            }
        )
        fallback_reason = f"llm_unavailable:{type(exc).__name__}"
    fallback = _deterministic_result(
        claim_result, numeric_slots, mode="deterministic_claim_plan_fallback"
    )
    return AnalysisGenerationResult(
        fallback.analysis_text,
        fallback.selected_conclusion_id,
        fallback.conclusion_text,
        fallback.claim_alignment,
        fallback.caveats,
        numeric_slots,
        fallback.generation_method,
        {
            "generator_version": ANALYSIS_GENERATOR_VERSION,
            "response_schema_version": ANALYSIS_RESPONSE_SCHEMA_VERSION,
            "schema_valid": False,
            "schema_errors": [fallback_reason],
            "fallback_reason": fallback_reason,
            "llm_attempts": attempts,
            "llm_telemetry": attempts[-1] if attempts else {},
            "request_contract_hash": stable_hash(request),
        },
    )


def validate_analysis_response(
    payload: Any, claim_result: ClaimPlanResult
) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"passed": False, "errors": ["response_not_object"]}
    allowed = {
        "schema_version",
        "selected_conclusion_id",
        "claims",
        "conclusion_sentence",
        "caveats",
    }
    if set(payload) - allowed:
        errors.append("unknown_response_fields")
    if payload.get("schema_version") != ANALYSIS_RESPONSE_SCHEMA_VERSION:
        errors.append("schema_version_mismatch")
    valid_conclusions = {
        item["conclusion_id"] for item in claim_result.valid_conclusions
    }
    selected = str(payload.get("selected_conclusion_id") or "")
    if selected not in valid_conclusions:
        errors.append("invalid_conclusion_id")
    expected_claims = {
        claim["claim_id"]: claim
        for claim in claim_result.claims
        if claim.get("is_required")
    }
    claims = payload.get("claims") if isinstance(payload.get("claims"), list) else []
    observed_ids = [
        str(item.get("claim_id") or "") for item in claims if isinstance(item, dict)
    ]
    if sorted(observed_ids) != sorted(expected_claims) or len(observed_ids) != len(
        set(observed_ids)
    ):
        errors.append("mandatory_claim_set_mismatch")
    normalized_claims = []
    for item in claims:
        if not isinstance(item, dict):
            errors.append("claim_not_object")
            continue
        if set(item) - {"claim_id", "sentence", "evidence_ids"}:
            errors.append("unknown_claim_fields")
        claim_id = str(item.get("claim_id") or "")
        expected = expected_claims.get(claim_id)
        evidence = sorted(str(value) for value in item.get("evidence_ids") or [])
        if expected and evidence != sorted(expected["support_signal_ids"]):
            errors.append(f"claim_evidence_mismatch:{claim_id}")
        sentence = str(item.get("sentence") or "").strip()
        if not sentence:
            errors.append(f"claim_sentence_empty:{claim_id}")
        if expected:
            expected_stance = str(
                (expected.get("semantic_contract") or {}).get("expected_stance") or ""
            )
            if not validate_stance(sentence, expected_stance)["passed"]:
                errors.append(f"claim_stance_mismatch:{claim_id}")
        normalized_claims.append(
            {"claim_id": claim_id, "sentence": sentence, "evidence_ids": evidence}
        )
    conclusion_sentence = str(payload.get("conclusion_sentence") or "").strip()
    if not conclusion_sentence:
        errors.append("conclusion_sentence_empty")
    selected_conclusion = next(
        (
            item
            for item in claim_result.valid_conclusions
            if item["conclusion_id"] == selected
        ),
        {},
    )
    expected_conclusion_stance = str(
        (selected_conclusion.get("semantic_contract") or {}).get("expected_stance")
        or ""
    )
    if (
        conclusion_sentence
        and not validate_stance(conclusion_sentence, expected_conclusion_stance)[
            "passed"
        ]
    ):
        errors.append("conclusion_stance_mismatch")
    required_caveats = {item["caveat_id"] for item in claim_result.caveats}
    caveats = payload.get("caveats") if isinstance(payload.get("caveats"), list) else []
    normalized_caveats = []
    observed_caveats = set()
    for item in caveats:
        if not isinstance(item, dict):
            errors.append("caveat_not_object")
            continue
        if set(item) - {"caveat_id", "sentence"}:
            errors.append("unknown_caveat_fields")
        caveat_id = str(item.get("caveat_id") or "")
        sentence = str(item.get("sentence") or "").strip()
        observed_caveats.add(caveat_id)
        if not sentence:
            errors.append(f"caveat_sentence_empty:{caveat_id}")
        normalized_caveats.append({"caveat_id": caveat_id, "sentence": sentence})
    if not required_caveats.issubset(observed_caveats):
        errors.append("required_caveat_missing")
    return {
        "passed": not errors,
        "errors": errors,
        "selected_conclusion_id": selected,
        "claims": normalized_claims,
        "conclusion_sentence": conclusion_sentence,
        "caveats": normalized_caveats,
    }


def _deterministic_result(
    claim_result: ClaimPlanResult, numeric_slots: list[dict[str, Any]], *, mode: str
) -> AnalysisGenerationResult:
    alignment = [
        {
            "claim_id": claim["claim_id"],
            "sentence": claim["sentence"],
            "evidence_ids": claim["support_signal_ids"],
        }
        for claim in claim_result.claims
        if claim.get("is_required")
    ]
    return AnalysisGenerationResult(
        claim_result.analysis_text,
        claim_result.selected_conclusion_id,
        claim_result.conclusion_text,
        alignment,
        claim_result.caveats,
        numeric_slots,
        mode,
        {
            "generator_version": ANALYSIS_GENERATOR_VERSION,
            "response_schema_version": ANALYSIS_RESPONSE_SCHEMA_VERSION,
            "schema_valid": True,
            "schema_errors": [],
            "fallback_reason": None,
            "llm_telemetry": {},
            "request_contract_hash": None,
        },
    )
