from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from finraw.analysis.claims import ClaimPlanResult
from finraw.analysis.registry import AnalysisPattern, stable_hash
from finraw.analysis.semantic_frames import (
    SEMANTIC_FRAME_VERSION,
    allowed_surface_form_ids,
    default_surface_form_id,
    render_semantic_frame,
    validate_semantic_frame,
)
from finraw.llm_client import LLMClientError, OpenAICompatibleJsonClient

ANALYSIS_GENERATOR_VERSION = "2.1.0"
ANALYSIS_RESPONSE_SCHEMA_VERSION = "analysis_response.v2"


class AnalysisProvider(Protocol):
    last_telemetry: dict[str, Any]

    def generate(self, request: dict[str, Any]) -> dict[str, Any]: ...


class OpenAICompatibleAnalysisProvider:
    def __init__(self, config: dict[str, Any]):
        self.client = OpenAICompatibleJsonClient(config)
        self.last_telemetry: dict[str, Any] = {}

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "You are selecting surface forms for a bounded financial analysis. "
            "Copy every semantic_frame exactly; never create or edit its subject, predicate, "
            "object, or qualifier. Select only supplied surface_form_ids. The program, not you, "
            "will render the final financial language. Use every mandatory claim exactly once, "
            "copy exact evidence IDs, select one allowed conclusion, and include every required "
            "caveat ID. Return exactly one JSON object with no extra fields and this shape: "
            '{"schema_version":"analysis_response.v2",'
            '"selected_conclusion_id":"COPY_ONE_ALLOWED_ID",'
            '"claims":[{"claim_id":"COPY_MANDATORY_ID",'
            '"semantic_frame":{"subject":"COPY","predicate":"COPY",'
            '"object":"COPY","qualifier":"COPY"},'
            '"surface_form_id":"COPY_ALLOWED_SURFACE_ID",'
            '"evidence_ids":["COPY_EXACT_EVIDENCE_ID"]}],'
            '"conclusion_semantic_frame":{"subject":"COPY","predicate":"COPY",'
            '"object":"COPY","qualifier":"COPY"},'
            '"conclusion_surface_form_id":"COPY_ALLOWED_SURFACE_ID",'
            '"caveats":[{"caveat_id":"COPY_REQUIRED_CAVEAT_ID"}]}. '
            "Do not return sentence, surface_text, conclusion_sentence, text, or analysis fields.\n"
            + json.dumps(request, ensure_ascii=False, sort_keys=True)
        )
        try:
            completion = self.client.complete_json(prompt, temperature=0.2)
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
    conclusion_semantic_frame: dict[str, Any]
    conclusion_surface_form_id: str
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
            claim_result, numeric_slots, mode="deterministic_semantic_frame_v1"
        )
    mandatory = [claim for claim in claim_result.claims if claim.get("is_required")]
    request = {
        "schema_version": ANALYSIS_RESPONSE_SCHEMA_VERSION,
        "semantic_frame_version": SEMANTIC_FRAME_VERSION,
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
                "evidence_ids": claim["support_signal_ids"],
                "semantic_frame": claim["semantic_frame"],
                "allowed_surface_form_ids": allowed_surface_form_ids(
                    claim["semantic_frame"], kind="claim"
                ),
                "allowed_context": {
                    "entity_ids": claim["allowed_entity_ids"],
                    "metric_ids": claim["allowed_metric_ids"],
                    "periods": claim["allowed_periods"],
                    "predicates": claim["allowed_predicates"],
                    "numeric_slot_ids": claim["allowed_numeric_slot_ids"],
                },
                "forbidden_claim_extensions": claim["forbidden_claim_extensions"],
            }
            for claim in mandatory
        ],
        "valid_conclusions": claim_result.valid_conclusions,
        "required_caveat_ids": [caveat["caveat_id"] for caveat in claim_result.caveats],
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
                        "Regenerate the full object. Copy every semantic frame and evidence "
                        "binding exactly, and select only registered surface form IDs."
                    ),
                }
                continue
            claims = validation["claims"]
            caveats = validation["caveats"]
            conclusion_text = validation["conclusion_text"]
            text = " ".join(
                [item["sentence"] for item in claims]
                + [conclusion_text]
                + [item["sentence"] for item in caveats]
            )
            return AnalysisGenerationResult(
                text,
                validation["selected_conclusion_id"],
                conclusion_text,
                validation["conclusion_semantic_frame"],
                validation["conclusion_surface_form_id"],
                claims,
                caveats,
                numeric_slots,
                "controlled_llm_semantic_frame",
                {
                    "generator_version": ANALYSIS_GENERATOR_VERSION,
                    "response_schema_version": ANALYSIS_RESPONSE_SCHEMA_VERSION,
                    "semantic_frame_version": SEMANTIC_FRAME_VERSION,
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
        claim_result, numeric_slots, mode="deterministic_semantic_frame_fallback"
    )
    return AnalysisGenerationResult(
        fallback.analysis_text,
        fallback.selected_conclusion_id,
        fallback.conclusion_text,
        fallback.conclusion_semantic_frame,
        fallback.conclusion_surface_form_id,
        fallback.claim_alignment,
        fallback.caveats,
        numeric_slots,
        fallback.generation_method,
        {
            "generator_version": ANALYSIS_GENERATOR_VERSION,
            "response_schema_version": ANALYSIS_RESPONSE_SCHEMA_VERSION,
            "semantic_frame_version": SEMANTIC_FRAME_VERSION,
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
        "conclusion_semantic_frame",
        "conclusion_surface_form_id",
        "caveats",
    }
    if set(payload) != allowed:
        errors.append("response_fields_mismatch")
    if payload.get("schema_version") != ANALYSIS_RESPONSE_SCHEMA_VERSION:
        errors.append("schema_version_mismatch")
    conclusion_by_id = {
        item["conclusion_id"]: item for item in claim_result.valid_conclusions
    }
    selected = str(payload.get("selected_conclusion_id") or "")
    selected_conclusion = conclusion_by_id.get(selected)
    if selected_conclusion is None:
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
        if set(item) != {
            "claim_id",
            "semantic_frame",
            "surface_form_id",
            "evidence_ids",
        }:
            errors.append("claim_fields_mismatch")
        claim_id = str(item.get("claim_id") or "")
        expected = expected_claims.get(claim_id)
        evidence = sorted(str(value) for value in item.get("evidence_ids") or [])
        if expected and evidence != sorted(expected["support_signal_ids"]):
            errors.append(f"claim_evidence_mismatch:{claim_id}")
        frame = item.get("semantic_frame")
        surface_form_id = str(item.get("surface_form_id") or "")
        sentence = ""
        if expected:
            frame_errors = validate_semantic_frame(
                frame, expected["semantic_frame"], kind="claim"
            )
            errors.extend(f"claim_{error}:{claim_id}" for error in frame_errors)
            if surface_form_id not in allowed_surface_form_ids(
                expected["semantic_frame"], kind="claim"
            ):
                errors.append(f"claim_surface_form_invalid:{claim_id}")
            elif not frame_errors:
                sentence = render_semantic_frame(
                    expected["semantic_frame"], surface_form_id, kind="claim"
                )
        normalized_claims.append(
            {
                "claim_id": claim_id,
                "semantic_frame": frame,
                "surface_form_id": surface_form_id,
                "sentence": sentence,
                "evidence_ids": evidence,
                "context_bindings": {
                    "entity_ids": list(expected.get("allowed_entity_ids") or []),
                    "metric_ids": list(expected.get("allowed_metric_ids") or []),
                    "periods": list(expected.get("allowed_periods") or []),
                    "predicates": list(expected.get("allowed_predicates") or []),
                    "numeric_slot_ids": list(
                        expected.get("allowed_numeric_slot_ids") or []
                    ),
                }
                if expected
                else {},
                "claim_extensions": [],
            }
        )
    conclusion_frame = payload.get("conclusion_semantic_frame")
    conclusion_surface = str(payload.get("conclusion_surface_form_id") or "")
    conclusion_text = ""
    if selected_conclusion:
        frame_errors = validate_semantic_frame(
            conclusion_frame,
            selected_conclusion["semantic_frame"],
            kind="conclusion",
        )
        errors.extend(f"conclusion_{error}" for error in frame_errors)
        if conclusion_surface not in selected_conclusion["allowed_surface_form_ids"]:
            errors.append("conclusion_surface_form_invalid")
        elif not frame_errors:
            conclusion_text = render_semantic_frame(
                selected_conclusion["semantic_frame"],
                conclusion_surface,
                kind="conclusion",
            )
    required_caveats = {item["caveat_id"]: item for item in claim_result.caveats}
    caveats = payload.get("caveats") if isinstance(payload.get("caveats"), list) else []
    observed_caveats = []
    normalized_caveats = []
    for item in caveats:
        if not isinstance(item, dict) or set(item) != {"caveat_id"}:
            errors.append("caveat_fields_mismatch")
            continue
        caveat_id = str(item.get("caveat_id") or "")
        observed_caveats.append(caveat_id)
        expected = required_caveats.get(caveat_id)
        if expected:
            normalized_caveats.append(dict(expected))
    if sorted(observed_caveats) != sorted(required_caveats) or len(
        observed_caveats
    ) != len(set(observed_caveats)):
        errors.append("required_caveat_set_mismatch")
    return {
        "passed": not errors,
        "errors": errors,
        "selected_conclusion_id": selected,
        "claims": normalized_claims,
        "conclusion_text": conclusion_text,
        "conclusion_semantic_frame": conclusion_frame,
        "conclusion_surface_form_id": conclusion_surface,
        "caveats": normalized_caveats,
    }


def _deterministic_result(
    claim_result: ClaimPlanResult, numeric_slots: list[dict[str, Any]], *, mode: str
) -> AnalysisGenerationResult:
    alignment = []
    for claim in claim_result.claims:
        if not claim.get("is_required"):
            continue
        frame = dict(claim["semantic_frame"])
        surface_form_id = default_surface_form_id(frame, kind="claim")
        alignment.append(
            {
                "claim_id": claim["claim_id"],
                "semantic_frame": frame,
                "surface_form_id": surface_form_id,
                "sentence": render_semantic_frame(frame, surface_form_id, kind="claim"),
                "evidence_ids": claim["support_signal_ids"],
                "context_bindings": {
                    "entity_ids": list(claim["allowed_entity_ids"]),
                    "metric_ids": list(claim["allowed_metric_ids"]),
                    "periods": list(claim["allowed_periods"]),
                    "predicates": list(claim["allowed_predicates"]),
                    "numeric_slot_ids": list(claim["allowed_numeric_slot_ids"]),
                },
                "claim_extensions": [],
            }
        )
    conclusion = next(
        item
        for item in claim_result.valid_conclusions
        if item["conclusion_id"] == claim_result.selected_conclusion_id
    )
    conclusion_frame = dict(conclusion["semantic_frame"])
    conclusion_surface = default_surface_form_id(conclusion_frame, kind="conclusion")
    conclusion_text = render_semantic_frame(
        conclusion_frame, conclusion_surface, kind="conclusion"
    )
    text = " ".join(
        [item["sentence"] for item in alignment]
        + [conclusion_text]
        + [item["sentence"] for item in claim_result.caveats]
    )
    return AnalysisGenerationResult(
        text,
        claim_result.selected_conclusion_id,
        conclusion_text,
        conclusion_frame,
        conclusion_surface,
        alignment,
        claim_result.caveats,
        numeric_slots,
        mode,
        {
            "generator_version": ANALYSIS_GENERATOR_VERSION,
            "response_schema_version": ANALYSIS_RESPONSE_SCHEMA_VERSION,
            "semantic_frame_version": SEMANTIC_FRAME_VERSION,
            "schema_valid": True,
            "schema_errors": [],
            "fallback_reason": None,
            "llm_attempts": [],
            "llm_telemetry": {},
            "request_contract_hash": None,
        },
    )
