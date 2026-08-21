from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_thinking_completion import (
    CompletionFailureKind,
    CompletionRequestKind,
)

COMPLETION_BOUND_PROTOCOL_VERSION: Final = "prospective_thinking_completion_bound_protocol.v1"
COMPLETION_BOUND_CANDIDATE_VERSION: Final = "prospective_completion_bound_candidate.v1"
DYNAMIC_PRECALL_CERTIFICATE_VERSION: Final = "dynamic_completion_precall_certificate.v1"

INITIAL_COMPLETION_BOUND_TOKENS: Final = 8192
INITIAL_ROLLOUT_BOUND_TOKENS: Final = 160_000
FALLBACK_COMPLETION_BOUND_TOKENS: Final = 16_384
FALLBACK_ROLLOUT_BOUND_TOKENS: Final = 240_000
PROMPT_UPPER_BOUND_BYTES: Final = 60_000
CHAT_ENVELOPE_TOKENS: Final = 256
STATIC_REQUEST_MARGIN_TOKENS: Final = 64
RESCUE_PROMPT_UPPER_BOUND_BYTES: Final = 6144

_CANDIDATE_BOUNDS = {
    1: (INITIAL_COMPLETION_BOUND_TOKENS, INITIAL_ROLLOUT_BOUND_TOKENS),
    2: (FALLBACK_COMPLETION_BOUND_TOKENS, FALLBACK_ROLLOUT_BOUND_TOKENS),
}
_ALLOWED_RESPONSE_FIELDS = {
    "decision": ("action", "arguments", "tool_id"),
    "final_answer": ("answer",),
}
_FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "correct_next_action",
        "expected_arguments",
        "expected_operator_id",
        "gold_evidence_ids",
        "mechanism_private_state",
        "oracle",
        "oracle_program",
        "private",
        "private_reasoning",
        "previous_final_content",
        "raw_http_body",
        "reasoning_content",
        "required_argument_patch",
        "required_next_tools",
        "required_prerequisite_action",
        "source_program_node_id",
        "suggested_argument_patch",
        "target_evidence_ids",
    }
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CompletionBoundCandidate(FrozenModel):
    candidate_id: str = Field(min_length=1)
    candidate_rank: Literal[1, 2]
    completion_upper_bound_tokens: Literal[8192, 16384]
    rollout_upper_bound_tokens: Literal[160000, 240000]
    prompt_upper_bound_bytes: Literal[60000] = PROMPT_UPPER_BOUND_BYTES
    chat_envelope_tokens: Literal[256] = CHAT_ENVELOPE_TOKENS
    static_request_margin_tokens: Literal[64] = STATIC_REQUEST_MARGIN_TOKENS
    initial_calibration_candidate: bool
    automatic_same_run_escalation_allowed: Literal[False] = False
    semantic_outcomes_used_for_selection: Literal[False] = False
    schema_version: Literal["prospective_completion_bound_candidate.v1"] = (
        COMPLETION_BOUND_CANDIDATE_VERSION
    )

    @model_validator(mode="after")
    def validate_candidate(self) -> CompletionBoundCandidate:
        expected = _CANDIDATE_BOUNDS[self.candidate_rank]
        if (self.completion_upper_bound_tokens, self.rollout_upper_bound_tokens) != expected:
            raise ValueError("Completion candidate rank and resource bounds differ")
        if self.initial_calibration_candidate != (self.candidate_rank == 1):
            raise ValueError("only the minimum Completion candidate may run first")
        if self.candidate_id != completion_bound_candidate_id(self):
            raise ValueError("Completion candidate identity mismatch")
        return self


class ProspectiveThinkingCompletionBoundProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    predecessor_transition_contract_id: str = Field(min_length=1)
    thinking_type: Literal["enabled"] = "enabled"
    candidates: tuple[CompletionBoundCandidate, CompletionBoundCandidate]
    initial_candidate_id: str = Field(min_length=1)
    fallback_candidate_id: str = Field(min_length=1)
    same_4096_bound_prompt_only_repair_allowed: Literal[False] = False
    bound_selection_uses_completion_usability_only: Literal[True] = True
    semantic_validity_can_select_bound: Literal[False] = False
    fallback_materialized_as_execution_job: Literal[False] = False
    fallback_automatic_execution_allowed: Literal[False] = False
    maximum_rescue_calls_per_job: Literal[1] = 1
    rescue_prompt_upper_bound_bytes: Literal[6144] = RESCUE_PROMPT_UPPER_BOUND_BYTES
    relative_rescue_reduction_gate_retained: Literal[False] = False
    actual_request_kind_pre_call_certificate_required: Literal[True] = True
    actual_primary_prompt_pre_call_certificate_required: Literal[True] = True
    actual_rescue_prompt_pre_call_certificate_required: Literal[True] = True
    actual_resource_pre_call_certificate_required: Literal[True] = True
    provider_invocation_before_all_required_certificates_allowed: Literal[False] = False
    rescue_reuses_previous_final_content: Literal[False] = False
    rescue_reuses_private_reasoning: Literal[False] = False
    rescue_includes_full_transcript: Literal[False] = False
    rescue_includes_failed_arguments: Literal[False] = False
    rescue_includes_superseded_operation_replay: Literal[False] = False
    rescue_includes_stale_search_results: Literal[False] = False
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    raw_http_body_persisted: Literal[False] = False
    schema_version: Literal["prospective_thinking_completion_bound_protocol.v1"] = (
        COMPLETION_BOUND_PROTOCOL_VERSION
    )

    @model_validator(mode="after")
    def validate_protocol(self) -> ProspectiveThinkingCompletionBoundProtocol:
        if tuple(item.candidate_rank for item in self.candidates) != (1, 2):
            raise ValueError("Completion candidates must retain their prospective order")
        if self.initial_candidate_id != self.candidates[0].candidate_id:
            raise ValueError("initial Completion candidate changed")
        if self.fallback_candidate_id != self.candidates[1].candidate_id:
            raise ValueError("fallback Completion candidate changed")
        if self.protocol_id != prospective_completion_bound_protocol_id(self):
            raise ValueError("Completion-bound protocol identity mismatch")
        return self


class DynamicCompletionPrecallCertificate(FrozenModel):
    certificate_id: str = Field(min_length=1)
    protocol_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    phase: Literal["primary", "rescue"]
    request_kind: CompletionRequestKind
    failure_type: CompletionFailureKind | None = None
    primary_prompt_sha256: str = Field(min_length=64, max_length=64)
    primary_prompt_utf8_bytes: int = Field(gt=0)
    request_prompt_sha256: str = Field(min_length=64, max_length=64)
    request_prompt_utf8_bytes: int = Field(gt=0)
    completion_upper_bound_tokens: int = Field(gt=4096)
    rollout_upper_bound_tokens: int = Field(gt=120000)
    cumulative_usage_tokens_before_request: int = Field(ge=0)
    required_future_reserve_tokens: int = Field(ge=0)
    request_token_upper_bound: int = Field(gt=0)
    post_request_and_reserve_upper_bound: int = Field(gt=0)
    actual_request_kind_certificate_passed: Literal[True] = True
    actual_primary_prompt_certificate_passed: Literal[True] = True
    actual_rescue_prompt_certificate_passed: bool | None
    actual_resource_certificate_passed: Literal[True] = True
    provider_call_count_before_certificate: Literal[0] = 0
    provider_invocation_authorized_after_certificate: Literal[True] = True
    previous_final_content_present: Literal[False] = False
    private_reasoning_content_present: Literal[False] = False
    schema_version: Literal["dynamic_completion_precall_certificate.v1"] = (
        DYNAMIC_PRECALL_CERTIFICATE_VERSION
    )

    @model_validator(mode="after")
    def validate_certificate(self) -> DynamicCompletionPrecallCertificate:
        if self.phase == "primary":
            if (
                self.failure_type is not None
                or self.actual_rescue_prompt_certificate_passed is not None
            ):
                raise ValueError("Primary certificate cannot contain Rescue state")
            if self.request_prompt_sha256 != self.primary_prompt_sha256:
                raise ValueError("Primary request and source Prompt hashes differ")
        else:
            if (
                self.failure_type is None
                or self.actual_rescue_prompt_certificate_passed is not True
            ):
                raise ValueError("Rescue certificate is incomplete")
            if self.request_prompt_utf8_bytes > RESCUE_PROMPT_UPPER_BOUND_BYTES:
                raise ValueError("Rescue Prompt exceeds its absolute byte bound")
        expected_request_bound = (
            self.request_prompt_utf8_bytes
            + CHAT_ENVELOPE_TOKENS
            + STATIC_REQUEST_MARGIN_TOKENS
            + self.completion_upper_bound_tokens
        )
        if self.request_token_upper_bound != expected_request_bound:
            raise ValueError("dynamic request token upper bound differs")
        expected_total = (
            self.cumulative_usage_tokens_before_request
            + self.request_token_upper_bound
            + self.required_future_reserve_tokens
        )
        if self.post_request_and_reserve_upper_bound != expected_total:
            raise ValueError("dynamic cumulative resource certificate differs")
        if expected_total > self.rollout_upper_bound_tokens:
            raise ValueError("dynamic request exceeds the candidate rollout bound")
        if self.request_prompt_utf8_bytes > PROMPT_UPPER_BOUND_BYTES:
            raise ValueError("dynamic request exceeds the Prompt byte bound")
        if self.certificate_id != dynamic_completion_precall_certificate_id(self):
            raise ValueError("dynamic Completion certificate identity mismatch")
        return self


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(field, None)
    return canonical_hash(payload, prefix=prefix)


def completion_bound_candidate_id(value: CompletionBoundCandidate) -> str:
    return _identity(
        value,
        "candidate_id",
        "prospective_completion_bound_candidate:",
    )


def prospective_completion_bound_protocol_id(
    value: ProspectiveThinkingCompletionBoundProtocol,
) -> str:
    return _identity(
        value,
        "protocol_id",
        "prospective_thinking_completion_bound_protocol:",
    )


def dynamic_completion_precall_certificate_id(
    value: DynamicCompletionPrecallCertificate,
) -> str:
    return _identity(
        value,
        "certificate_id",
        "dynamic_completion_precall_certificate:",
    )


def make_completion_bound_candidate(rank: Literal[1, 2]) -> CompletionBoundCandidate:
    completion, rollout = _CANDIDATE_BOUNDS[rank]
    values = {
        "candidate_rank": rank,
        "completion_upper_bound_tokens": completion,
        "rollout_upper_bound_tokens": rollout,
        "initial_calibration_candidate": rank == 1,
    }
    provisional = CompletionBoundCandidate.model_construct(candidate_id="pending", **values)
    return CompletionBoundCandidate(
        candidate_id=completion_bound_candidate_id(provisional),
        **values,
    )


def make_prospective_completion_bound_protocol(
    *,
    predecessor_transition_contract_id: str,
) -> ProspectiveThinkingCompletionBoundProtocol:
    candidates = (make_completion_bound_candidate(1), make_completion_bound_candidate(2))
    values = {
        "predecessor_transition_contract_id": predecessor_transition_contract_id,
        "candidates": candidates,
        "initial_candidate_id": candidates[0].candidate_id,
        "fallback_candidate_id": candidates[1].candidate_id,
    }
    provisional = ProspectiveThinkingCompletionBoundProtocol.model_construct(
        protocol_id="pending",
        **values,
    )
    return ProspectiveThinkingCompletionBoundProtocol(
        protocol_id=prospective_completion_bound_protocol_id(provisional),
        **values,
    )


def _assert_no_forbidden_public_keys(value: Any, *, path: str = "capsule") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).casefold()
            if normalized in _FORBIDDEN_PUBLIC_KEYS:
                raise ValueError(f"forbidden public Completion field at {path}.{key}")
            _assert_no_forbidden_public_keys(item, path=f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _assert_no_forbidden_public_keys(item, path=f"{path}[{index}]")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _primary_payload(primary_prompt: str) -> dict[str, Any]:
    _, separator, raw_payload = primary_prompt.partition("\n")
    if not separator:
        raise ValueError("Primary Prompt lacks a public JSON payload")
    payload = json.loads(raw_payload)
    if not isinstance(payload, dict):
        raise ValueError("Primary Prompt payload must be an object")
    _assert_no_forbidden_public_keys(payload, path="primary")
    return payload


def infer_actual_request_kind(primary_prompt: str) -> CompletionRequestKind:
    payload = _primary_payload(primary_prompt)
    response_contract = payload.get("response_contract")
    if not isinstance(response_contract, Mapping):
        raise ValueError("Primary Prompt lacks a response Contract")
    fields = response_contract.get("fields")
    normalized_fields = (
        tuple(sorted(str(item) for item in fields)) if isinstance(fields, list) else ()
    )
    if "public_context" in payload and "final_context" not in payload:
        request_kind: CompletionRequestKind = "decision"
    elif "final_context" in payload and "public_context" not in payload:
        request_kind = "final_answer"
    else:
        raise ValueError("Primary Prompt has an ambiguous request kind")
    if normalized_fields != tuple(sorted(_ALLOWED_RESPONSE_FIELDS[request_kind])):
        raise ValueError("Primary Prompt response fields do not match its actual request kind")
    return request_kind


def _mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a public object")
    return value


def _compact_fact(fact: Mapping[str, Any]) -> dict[str, Any]:
    output = {
        key: fact.get(key)
        for key in (
            "evidence_id",
            "frequency",
            "metric",
            "payload",
            "period",
            "subject",
            "time_basis",
        )
        if fact.get(key) is not None
    }
    _assert_no_forbidden_public_keys(output, path="selected_fact")
    return output


def _selected_facts(history: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    selected = {str(item) for item in history.get("selected_evidence_ids", ()) if str(item).strip()}
    facts_by_id: dict[str, Mapping[str, Any]] = {}
    acquisitions = history.get("acquisitions", ())
    if not isinstance(acquisitions, Sequence) or isinstance(acquisitions, (str, bytes)):
        raise ValueError("public acquisition history must be a sequence")
    for acquisition in acquisitions:
        if not isinstance(acquisition, Mapping):
            continue
        result = acquisition.get("result")
        if not isinstance(result, Mapping):
            continue
        candidates: list[Any] = []
        facts = result.get("facts")
        if isinstance(facts, Sequence) and not isinstance(facts, (str, bytes)):
            candidates.extend(facts)
        content = result.get("content")
        if isinstance(content, Mapping):
            content_facts = content.get("facts")
            if isinstance(content_facts, Sequence) and not isinstance(
                content_facts,
                (str, bytes),
            ):
                candidates.extend(content_facts)
        for fact in candidates:
            if not isinstance(fact, Mapping):
                continue
            evidence_id = str(fact.get("evidence_id") or "")
            if evidence_id and (not selected or evidence_id in selected):
                facts_by_id[evidence_id] = fact
    return tuple(_compact_fact(facts_by_id[item]) for item in sorted(facts_by_id))


def _compact_pending_search(history: Mapping[str, Any]) -> dict[str, Any] | None:
    pending = history.get("pending_search")
    if pending is None:
        return None
    pending = _mapping(pending, label="pending search")
    result = _mapping(pending.get("result"), label="pending search result")
    matches = result.get("matches", ())
    if not isinstance(matches, Sequence) or isinstance(matches, (str, bytes)):
        raise ValueError("pending search matches must be a sequence")
    compact_matches = []
    for item in matches:
        if not isinstance(item, Mapping):
            continue
        compact_matches.append(
            {
                key: item.get(key)
                for key in (
                    "evidence_id",
                    "metric",
                    "period",
                    "public_locator",
                    "subject",
                )
                if item.get(key) is not None
            }
        )
    return {
        "tool_id": pending.get("tool_id"),
        "matches": tuple(compact_matches),
    }


def _latest_failure(history: Mapping[str, Any]) -> dict[str, Any] | None:
    failures = history.get("failed_actions", ())
    if not isinstance(failures, Sequence) or isinstance(failures, (str, bytes)):
        raise ValueError("public failure history must be a sequence")
    mappings = [item for item in failures if isinstance(item, Mapping)]
    if not mappings:
        return None
    latest = mappings[-1]
    result = latest.get("result")
    retry_contract = result.get("retry_contract") if isinstance(result, Mapping) else None
    return {
        "error_code": latest.get("error_code"),
        "failed_tool_id": latest.get("tool_id"),
        "retry_contract": retry_contract,
        "failed_arguments_omitted": True,
        "earlier_failures_omitted": len(mappings) - 1,
    }


def _compact_operation(
    operation: Mapping[str, Any],
    progress: Mapping[str, Any],
) -> dict[str, Any]:
    remaining = {str(item) for item in progress.get("remaining_node_ids", ())}
    ready_nodes = progress.get("ready_nodes", ())
    ready = {
        str(item.get("node_id"))
        for item in ready_nodes
        if isinstance(item, Mapping) and item.get("node_id") is not None
    }
    current = ready or remaining
    unresolved = {str(item) for item in progress.get("unresolved_symbols", ())}
    nodes = operation.get("nodes", ())
    variables = operation.get("variables", ())
    if not isinstance(nodes, Sequence) or isinstance(nodes, (str, bytes)):
        raise ValueError("public Operation nodes must be a sequence")
    if not isinstance(variables, Sequence) or isinstance(variables, (str, bytes)):
        raise ValueError("public Operation variables must be a sequence")
    current_nodes = tuple(
        item for item in nodes if isinstance(item, Mapping) and str(item.get("node_id")) in current
    )
    current_variables = tuple(
        item
        for item in variables
        if isinstance(item, Mapping) and str(item.get("symbol")) in unresolved
    )
    return {
        "completion_rule": operation.get("completion_rule"),
        "terminal_node_id": operation.get("terminal_node_id"),
        "nodes": current_nodes,
        "variables": current_variables,
    }


def _compact_progress(progress: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: progress.get(key)
        for key in (
            "completed_node_ids",
            "completed_node_operation_refs",
            "remaining_node_ids",
            "ready_nodes",
            "unresolved_symbols",
            "terminal_node_completed",
            "verification_after_terminal_completed",
            "stop_ready",
            "final_answer_allowed",
        )
    }


def _response_contract(request_kind: CompletionRequestKind) -> dict[str, Any]:
    if request_kind == "decision":
        return {
            "action": "call_tool",
            "fields": _ALLOWED_RESPONSE_FIELDS[request_kind],
            "free_text_fields": "forbidden",
        }
    return {
        "fields": _ALLOWED_RESPONSE_FIELDS[request_kind],
        "free_text_fields": "forbidden",
    }


def _bounded_rescue_payload(
    request_kind: CompletionRequestKind,
    primary_prompt: str,
    failure_type: CompletionFailureKind,
) -> dict[str, Any]:
    payload = _primary_payload(primary_prompt)
    actual_kind = infer_actual_request_kind(primary_prompt)
    if actual_kind != request_kind:
        raise ValueError("declared request kind differs from actual Primary Prompt")
    if request_kind == "decision":
        context = _mapping(payload.get("public_context"), label="decision public context")
        task = _mapping(context.get("task"), label="decision public task")
        operation = _mapping(context.get("public_operation"), label="decision public Operation")
        progress = _mapping(payload.get("progress"), label="decision public progress")
        history = _mapping(payload.get("history"), label="decision public history")
        latest_failure = _latest_failure(history)
        capsule: dict[str, Any] = {
            "request_kind": request_kind,
            "instruction": task.get("instruction"),
            "answer_schema": task.get("answer_schema"),
            "path": payload.get("public_path_condition"),
            "current_operation": _compact_operation(operation, progress),
            "progress": _compact_progress(progress),
            "selected_evidence_ids": tuple(
                sorted(str(item) for item in history.get("selected_evidence_ids", ()))
            ),
            "selected_facts": _selected_facts(history),
            "pending_search": _compact_pending_search(history),
            "latest_failure": latest_failure,
            "allowed_tools": context.get("tools"),
            "response_contract": _response_contract(request_kind),
        }
        if latest_failure is not None:
            repair = _mapping(context.get("repair"), label="decision public repair")
            capsule["repair_contract"] = {
                "model_retains_repair_decision": repair.get("model_retains_repair_decision"),
                "identical_arguments_forbidden": True,
            }
        if progress.get("terminal_node_completed"):
            capsule["terminal_verification"] = context.get("terminal_verification")
    else:
        final_context = _mapping(payload.get("final_context"), label="final public context")
        capsule = {
            "request_kind": request_kind,
            "final_context": dict(final_context),
            "path": payload.get("public_path_condition"),
            "response_contract": _response_contract(request_kind),
        }
    capsule["rescue"] = {
        "failure_type": failure_type,
        "emit_compact_json_immediately": True,
        "previous_final_content_reused": False,
        "private_reasoning_reused": False,
        "repeat_planning_or_deliberation": False,
        "same_public_state": True,
    }
    _assert_no_forbidden_public_keys(capsule)
    return capsule


def render_bounded_rescue_completion_prompt(
    request_kind: CompletionRequestKind,
    primary_prompt: str,
    failure_type: CompletionFailureKind,
) -> str:
    capsule = _bounded_rescue_payload(request_kind, primary_prompt, failure_type)
    prompt = "Emit compact JSON now; do not deliberate or repeat prior text.\n"
    prompt += _canonical_json(capsule)
    if len(prompt.encode("utf-8")) > RESCUE_PROMPT_UPPER_BOUND_BYTES:
        raise ValueError("dynamic Rescue Prompt exceeds the absolute byte bound")
    return prompt


def _candidate_by_id(
    protocol: ProspectiveThinkingCompletionBoundProtocol,
    candidate_id: str,
) -> CompletionBoundCandidate:
    for candidate in protocol.candidates:
        if candidate.candidate_id == candidate_id:
            return candidate
    raise ValueError("Completion candidate is not registered by the protocol")


def _make_precall_certificate(
    *,
    protocol: ProspectiveThinkingCompletionBoundProtocol,
    candidate_id: str,
    phase: Literal["primary", "rescue"],
    request_kind: CompletionRequestKind,
    primary_prompt: str,
    request_prompt: str,
    failure_type: CompletionFailureKind | None,
    cumulative_usage_tokens_before_request: int,
    required_future_reserve_tokens: int,
) -> DynamicCompletionPrecallCertificate:
    candidate = _candidate_by_id(protocol, candidate_id)
    actual_kind = infer_actual_request_kind(primary_prompt)
    if actual_kind != request_kind:
        raise ValueError("actual dynamic request kind certificate failed")
    primary_bytes = len(primary_prompt.encode("utf-8"))
    request_bytes = len(request_prompt.encode("utf-8"))
    if primary_bytes > PROMPT_UPPER_BOUND_BYTES:
        raise ValueError("actual dynamic Primary Prompt exceeds the byte bound")
    if phase == "rescue" and request_bytes > RESCUE_PROMPT_UPPER_BOUND_BYTES:
        raise ValueError("actual dynamic Rescue Prompt exceeds the absolute byte bound")
    request_bound = (
        request_bytes
        + CHAT_ENVELOPE_TOKENS
        + STATIC_REQUEST_MARGIN_TOKENS
        + candidate.completion_upper_bound_tokens
    )
    cumulative_bound = (
        cumulative_usage_tokens_before_request + request_bound + required_future_reserve_tokens
    )
    if cumulative_bound > candidate.rollout_upper_bound_tokens:
        raise ValueError("actual dynamic request lacks rollout budget")
    values = {
        "protocol_id": protocol.protocol_id,
        "candidate_id": candidate.candidate_id,
        "phase": phase,
        "request_kind": request_kind,
        "failure_type": failure_type,
        "primary_prompt_sha256": _sha256_text(primary_prompt),
        "primary_prompt_utf8_bytes": primary_bytes,
        "request_prompt_sha256": _sha256_text(request_prompt),
        "request_prompt_utf8_bytes": request_bytes,
        "completion_upper_bound_tokens": candidate.completion_upper_bound_tokens,
        "rollout_upper_bound_tokens": candidate.rollout_upper_bound_tokens,
        "cumulative_usage_tokens_before_request": cumulative_usage_tokens_before_request,
        "required_future_reserve_tokens": required_future_reserve_tokens,
        "request_token_upper_bound": request_bound,
        "post_request_and_reserve_upper_bound": cumulative_bound,
        "actual_rescue_prompt_certificate_passed": True if phase == "rescue" else None,
    }
    provisional = DynamicCompletionPrecallCertificate.model_construct(
        certificate_id="pending",
        **values,
    )
    return DynamicCompletionPrecallCertificate(
        certificate_id=dynamic_completion_precall_certificate_id(provisional),
        **values,
    )


def certify_dynamic_primary_pre_call(
    *,
    protocol: ProspectiveThinkingCompletionBoundProtocol,
    candidate_id: str,
    request_kind: CompletionRequestKind,
    primary_prompt: str,
    cumulative_usage_tokens_before_request: int,
    required_future_reserve_tokens: int,
) -> DynamicCompletionPrecallCertificate:
    return _make_precall_certificate(
        protocol=protocol,
        candidate_id=candidate_id,
        phase="primary",
        request_kind=request_kind,
        primary_prompt=primary_prompt,
        request_prompt=primary_prompt,
        failure_type=None,
        cumulative_usage_tokens_before_request=cumulative_usage_tokens_before_request,
        required_future_reserve_tokens=required_future_reserve_tokens,
    )


def certify_dynamic_rescue_pre_call(
    *,
    protocol: ProspectiveThinkingCompletionBoundProtocol,
    candidate_id: str,
    request_kind: CompletionRequestKind,
    primary_prompt: str,
    failure_type: CompletionFailureKind,
    cumulative_usage_tokens_before_request: int,
    required_future_reserve_tokens: int,
) -> tuple[str, DynamicCompletionPrecallCertificate]:
    rescue_prompt = render_bounded_rescue_completion_prompt(
        request_kind,
        primary_prompt,
        failure_type,
    )
    certificate = _make_precall_certificate(
        protocol=protocol,
        candidate_id=candidate_id,
        phase="rescue",
        request_kind=request_kind,
        primary_prompt=primary_prompt,
        request_prompt=rescue_prompt,
        failure_type=failure_type,
        cumulative_usage_tokens_before_request=cumulative_usage_tokens_before_request,
        required_future_reserve_tokens=required_future_reserve_tokens,
    )
    return rescue_prompt, certificate


def candidate_for_initial_calibration(
    protocol: ProspectiveThinkingCompletionBoundProtocol,
) -> CompletionBoundCandidate:
    return cast(
        CompletionBoundCandidate,
        _candidate_by_id(protocol, protocol.initial_candidate_id),
    )
