from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from finraw.analysis.claims import ClaimPlanResult
from finraw.analysis.discourse import (
    DISCOURSE_PLAN_VERSION,
    default_discourse_plan,
    discourse_manifest,
    instruction_surface_ids,
    render_analysis_text,
    render_instruction,
    render_numeric_slot,
    selectable_numeric_slot_ids,
    validate_discourse_plan,
)
from finraw.analysis.registry import AnalysisPattern, stable_hash
from finraw.analysis.semantic_frames import (
    SEMANTIC_FRAME_VERSION,
    allowed_surface_form_ids,
    default_surface_form_id,
    render_semantic_frame,
    validate_semantic_frame,
)
from finraw.llm_client import LLMClientError, OpenAICompatibleJsonClient

ANALYSIS_GENERATOR_VERSION = "2.5.0"
ANALYSIS_RESPONSE_SCHEMA_VERSION = "analysis_response.v3"


class AnalysisProvider(Protocol):
    last_telemetry: dict[str, Any]

    def generate(self, request: dict[str, Any]) -> dict[str, Any]: ...


class OpenAICompatibleAnalysisProvider:
    def __init__(self, config: dict[str, Any]):
        self.client = OpenAICompatibleJsonClient(config)
        self.last_telemetry: dict[str, Any] = {}

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "You are selecting a bounded discourse plan for financial analysis. "
            "Never write prose and never create or edit facts, numbers, claims, semantic "
            "frames, predicates, evidence IDs, entities, metrics, periods, or conclusions. "
            "Choose only supplied IDs. Start from valid_response_template and preserve "
            "its exact object shape. You may change only registered surface-form IDs, "
            "instruction_surface_form_id, selected_conclusion_id, Claim order, registered "
            "transition IDs, and allowed numeric-slot selections. Use every mandatory claim "
            "exactly once, preserve each semantic_frame and evidence list exactly, choose at "
            "most the configured numeric slots, and include every required caveat. Return one "
            "JSON object with "
            "exactly the requested analysis_response.v3 fields. Claim order may vary, but "
            "it must equal discourse_plan.claim_order. Do not return sentence, surface_text, "
            "conclusion_sentence, analysis_text, or any free text.\n"
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
    instruction_text: str
    instruction_surface_form_id: str
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
    maximum_numeric_mentions = max(
        0, min(int(policy.get("maximum_numeric_mentions", 2)), 5)
    )
    if mode != "controlled_llm":
        return _deterministic_result(
            pattern,
            claim_result,
            numeric_slots,
            maximum_numeric_mentions=maximum_numeric_mentions,
            mode="deterministic_semantic_frame_v2",
        )
    mandatory = [claim for claim in claim_result.claims if claim.get("is_required")]
    discourse = discourse_manifest()
    default_plan = default_discourse_plan(
        mandatory, maximum_numeric_mentions=maximum_numeric_mentions
    )
    mandatory_by_id = {str(claim["claim_id"]): claim for claim in mandatory}
    selected_conclusion = next(
        item
        for item in claim_result.valid_conclusions
        if item["conclusion_id"] == claim_result.selected_conclusion_id
    )
    valid_response_template = {
        "schema_version": ANALYSIS_RESPONSE_SCHEMA_VERSION,
        "instruction_surface_form_id": instruction_surface_ids(
            pattern.analysis_pattern_id
        )[0],
        "selected_conclusion_id": claim_result.selected_conclusion_id,
        "discourse_plan": default_plan,
        "claims": [
            {
                "claim_id": claim_id,
                "semantic_frame": mandatory_by_id[claim_id]["semantic_frame"],
                "surface_form_id": default_surface_form_id(
                    mandatory_by_id[claim_id]["semantic_frame"], kind="claim"
                ),
                "evidence_ids": mandatory_by_id[claim_id]["support_signal_ids"],
                "numeric_slot_ids": default_plan["selected_numeric_slot_ids"][
                    claim_id
                ],
            }
            for claim_id in default_plan["claim_order"]
        ],
        "conclusion_semantic_frame": selected_conclusion["semantic_frame"],
        "conclusion_surface_form_id": selected_conclusion[
            "allowed_surface_form_ids"
        ][0],
        "caveats": [
            {"caveat_id": caveat["caveat_id"]}
            for caveat in claim_result.caveats
        ],
    }
    selectable_slot_ids = {
        slot_id
        for claim in mandatory
        for slot_id in selectable_numeric_slot_ids(claim)
    }
    request = {
        "schema_version": ANALYSIS_RESPONSE_SCHEMA_VERSION,
        "valid_response_template": valid_response_template,
        "response_contract": {
            "exact_top_level_fields": [
                "schema_version",
                "instruction_surface_form_id",
                "selected_conclusion_id",
                "discourse_plan",
                "claims",
                "conclusion_semantic_frame",
                "conclusion_surface_form_id",
                "caveats",
            ],
            "exact_claim_fields": [
                "claim_id",
                "semantic_frame",
                "surface_form_id",
                "evidence_ids",
                "numeric_slot_ids",
            ],
            "exact_caveat_fields": ["caveat_id"],
            "free_text_fields_allowed": [],
        },
        "semantic_frame_version": SEMANTIC_FRAME_VERSION,
        "discourse_plan_version": DISCOURSE_PLAN_VERSION,
        "instruction_surface_form_ids": instruction_surface_ids(
            pattern.analysis_pattern_id
        ),
        "discourse_schema": {
            "style_ids": sorted(discourse["styles"]),
            "first_transition_ids": sorted(discourse["first_transitions"]),
            "next_transition_ids": sorted(discourse["next_transitions"]),
            "conclusion_transition_ids": sorted(
                discourse["conclusion_transitions"]
            ),
            "caveat_transition_ids": sorted(discourse["caveat_transitions"]),
            "maximum_numeric_mentions": maximum_numeric_mentions,
        },
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
                "allowed_numeric_slot_ids": [
                    str(slot["slot_id"])
                    for slot in claim.get("required_numeric_slots") or []
                    if str(slot.get("field") or "")
                    in discourse["selectable_numeric_fields"]
                ],
                "allowed_context": {
                    "entity_ids": claim["allowed_entity_ids"],
                    "metric_ids": claim["allowed_metric_ids"],
                    "periods": claim["allowed_periods"],
                    "predicates": claim["allowed_predicates"],
                    "numeric_slot_ids": claim["allowed_numeric_slot_ids"],
                },
                "forbidden_claim_extensions": claim[
                    "forbidden_claim_extensions"
                ],
            }
            for claim in mandatory
        ],
        "valid_conclusions": claim_result.valid_conclusions,
        "required_caveat_ids": [
            caveat["caveat_id"] for caveat in claim_result.caveats
        ],
        "numeric_slots": [
            slot
            for slot in numeric_slots
            if str(slot.get("slot_id") or "") in selectable_slot_ids
        ]
        if policy.get("allow_numeric_slots", True)
        else [],
        "forbidden_claim_types": list(pattern.forbidden_claim_types),
    }
    request_contract_hash = stable_hash(request)
    effective_provider: AnalysisProvider | None = None
    attempts: list[dict[str, Any]] = []
    max_attempts = max(1, int(policy.get("max_attempts", 2)))
    validation: dict[str, Any] = {"errors": ["no_attempt"]}
    try:
        effective_provider = provider or OpenAICompatibleAnalysisProvider(
            policy.get("llm", {})
        )
        for attempt_index in range(1, max_attempts + 1):
            payload = effective_provider.generate(request)
            telemetry = dict(getattr(effective_provider, "last_telemetry", {}) or {})
            validation = validate_analysis_response(
                payload,
                claim_result,
                pattern=pattern,
                maximum_numeric_mentions=maximum_numeric_mentions,
            )
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
                        "Regenerate the full object using only allowed IDs and exact "
                        "semantic/evidence bindings. Return no prose."
                    ),
                }
                continue
            claims = validation["claims"]
            caveats = validation["caveats"]
            conclusion_text = validation["conclusion_text"]
            text = render_analysis_text(
                claims,
                conclusion_text,
                caveats,
                validation["discourse_plan"],
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
                validation["instruction_text"],
                validation["instruction_surface_form_id"],
                "controlled_llm_discourse_plan",
                {
                    "generator_version": ANALYSIS_GENERATOR_VERSION,
                    "response_schema_version": ANALYSIS_RESPONSE_SCHEMA_VERSION,
                    "semantic_frame_version": SEMANTIC_FRAME_VERSION,
                    "discourse_plan_version": DISCOURSE_PLAN_VERSION,
                    "discourse_manifest_hash": discourse["manifest_hash"],
                    "discourse_plan": validation["discourse_plan"],
                    "instruction_surface_form_id": validation[
                        "instruction_surface_form_id"
                    ],
                    "maximum_numeric_mentions": maximum_numeric_mentions,
                    "schema_valid": True,
                    "schema_errors": [],
                    "fallback_reason": None,
                    "llm_attempts": attempts,
                    "llm_telemetry": attempts[-1],
                    "request_contract_hash": request_contract_hash,
                },
            )
        fallback_reason = "invalid_analysis_response:" + ",".join(
            validation["errors"]
        )
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
        pattern,
        claim_result,
        numeric_slots,
        maximum_numeric_mentions=maximum_numeric_mentions,
        mode="deterministic_semantic_frame_fallback_v2",
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
        fallback.instruction_text,
        fallback.instruction_surface_form_id,
        fallback.generation_method,
        {
            **fallback.generation_metadata,
            "schema_valid": False,
            "schema_errors": [fallback_reason],
            "fallback_reason": fallback_reason,
            "llm_attempts": attempts,
            "llm_telemetry": attempts[-1] if attempts else {},
            "request_contract_hash": request_contract_hash,
        },
    )

def validate_analysis_response(
    payload: Any,
    claim_result: ClaimPlanResult,
    *,
    pattern: AnalysisPattern,
    maximum_numeric_mentions: int = 2,
) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"passed": False, "errors": ["response_not_object"]}
    allowed = {
        "schema_version",
        "instruction_surface_form_id",
        "selected_conclusion_id",
        "discourse_plan",
        "claims",
        "conclusion_semantic_frame",
        "conclusion_surface_form_id",
        "caveats",
    }
    if set(payload) != allowed:
        errors.append("response_fields_mismatch")
    if payload.get("schema_version") != ANALYSIS_RESPONSE_SCHEMA_VERSION:
        errors.append("schema_version_mismatch")
    instruction_surface = str(payload.get("instruction_surface_form_id") or "")
    if instruction_surface not in instruction_surface_ids(
        pattern.analysis_pattern_id
    ):
        errors.append("instruction_surface_form_invalid")
        instruction_text = ""
    else:
        instruction_text = render_instruction(
            pattern.analysis_pattern_id, instruction_surface
        )
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
    discourse_check = validate_discourse_plan(
        payload.get("discourse_plan"),
        list(expected_claims.values()),
        maximum_numeric_mentions=maximum_numeric_mentions,
    )
    errors.extend(discourse_check["errors"])
    discourse_plan = discourse_check.get("plan") or {}
    claims = payload.get("claims") if isinstance(payload.get("claims"), list) else []
    observed_ids = [
        str(item.get("claim_id") or "") for item in claims if isinstance(item, dict)
    ]
    if sorted(observed_ids) != sorted(expected_claims) or len(observed_ids) != len(
        set(observed_ids)
    ):
        errors.append("mandatory_claim_set_mismatch")
    if discourse_plan and observed_ids != discourse_plan.get("claim_order"):
        errors.append("claim_order_discourse_mismatch")
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
            "numeric_slot_ids",
        }:
            errors.append("claim_fields_mismatch")
        claim_id = str(item.get("claim_id") or "")
        expected = expected_claims.get(claim_id)
        evidence = sorted(str(value) for value in item.get("evidence_ids") or [])
        if expected and evidence != sorted(expected["support_signal_ids"]):
            errors.append(f"claim_evidence_mismatch:{claim_id}")
        selected_numeric = [
            str(value) for value in item.get("numeric_slot_ids") or []
        ]
        discourse_numeric = list(
            (discourse_plan.get("selected_numeric_slot_ids") or {}).get(
                claim_id, []
            )
        )
        if selected_numeric != discourse_numeric:
            errors.append(f"claim_numeric_discourse_mismatch:{claim_id}")
        slots_by_id = {
            str(slot["slot_id"]): slot
            for slot in (expected or {}).get("required_numeric_slots") or []
        }
        if not set(selected_numeric).issubset(slots_by_id):
            errors.append(f"claim_numeric_slot_invalid:{claim_id}")
        numeric_sentences = [
            render_numeric_slot(slots_by_id[slot_id])
            for slot_id in selected_numeric
            if slot_id in slots_by_id
        ]
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
                "selected_numeric_slot_ids": selected_numeric,
                "numeric_sentences": numeric_sentences,
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
        "instruction_text": instruction_text,
        "instruction_surface_form_id": instruction_surface,
        "selected_conclusion_id": selected,
        "discourse_plan": discourse_plan,
        "claims": normalized_claims,
        "conclusion_text": conclusion_text,
        "conclusion_semantic_frame": conclusion_frame,
        "conclusion_surface_form_id": conclusion_surface,
        "caveats": normalized_caveats,
    }

def _deterministic_result(
    pattern: AnalysisPattern,
    claim_result: ClaimPlanResult,
    numeric_slots: list[dict[str, Any]],
    *,
    maximum_numeric_mentions: int,
    mode: str,
) -> AnalysisGenerationResult:
    mandatory = [claim for claim in claim_result.claims if claim.get("is_required")]
    discourse_plan = default_discourse_plan(
        mandatory, maximum_numeric_mentions=maximum_numeric_mentions
    )
    alignment = []
    claim_by_id = {str(claim["claim_id"]): claim for claim in mandatory}
    for claim_id in discourse_plan["claim_order"]:
        claim = claim_by_id[claim_id]
        frame = dict(claim["semantic_frame"])
        surfaces = allowed_surface_form_ids(frame, kind="claim")
        surface_form_id = surfaces[
            int(stable_hash([claim_id, mode])[:8], 16) % len(surfaces)
        ]
        slots_by_id = {
            str(slot["slot_id"]): slot
            for slot in claim.get("required_numeric_slots") or []
        }
        selected_numeric = list(
            discourse_plan["selected_numeric_slot_ids"].get(claim_id) or []
        )
        alignment.append(
            {
                "claim_id": claim_id,
                "semantic_frame": frame,
                "surface_form_id": surface_form_id,
                "sentence": render_semantic_frame(
                    frame, surface_form_id, kind="claim"
                ),
                "evidence_ids": claim["support_signal_ids"],
                "selected_numeric_slot_ids": selected_numeric,
                "numeric_sentences": [
                    render_numeric_slot(slots_by_id[slot_id])
                    for slot_id in selected_numeric
                ],
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
    conclusion_surfaces = list(conclusion["allowed_surface_form_ids"])
    conclusion_surface = conclusion_surfaces[
        int(stable_hash([claim_result.selected_conclusion_id, mode])[:8], 16)
        % len(conclusion_surfaces)
    ]
    conclusion_text = render_semantic_frame(
        conclusion_frame, conclusion_surface, kind="conclusion"
    )
    instruction_ids = instruction_surface_ids(pattern.analysis_pattern_id)
    instruction_surface = instruction_ids[
        int(stable_hash([claim_result.selected_conclusion_id, mode])[:8], 16)
        % len(instruction_ids)
    ]
    instruction_text = render_instruction(
        pattern.analysis_pattern_id, instruction_surface
    )
    text = render_analysis_text(
        alignment, conclusion_text, claim_result.caveats, discourse_plan
    )
    discourse = discourse_manifest()
    return AnalysisGenerationResult(
        text,
        claim_result.selected_conclusion_id,
        conclusion_text,
        conclusion_frame,
        conclusion_surface,
        alignment,
        claim_result.caveats,
        numeric_slots,
        instruction_text,
        instruction_surface,
        mode,
        {
            "generator_version": ANALYSIS_GENERATOR_VERSION,
            "response_schema_version": ANALYSIS_RESPONSE_SCHEMA_VERSION,
            "semantic_frame_version": SEMANTIC_FRAME_VERSION,
            "discourse_plan_version": DISCOURSE_PLAN_VERSION,
            "discourse_manifest_hash": discourse["manifest_hash"],
            "discourse_plan": discourse_plan,
            "instruction_surface_form_id": instruction_surface,
            "maximum_numeric_mentions": maximum_numeric_mentions,
            "schema_valid": True,
            "schema_errors": [],
            "fallback_reason": None,
            "llm_attempts": [],
            "llm_telemetry": {},
            "request_contract_hash": None,
        },
    )
