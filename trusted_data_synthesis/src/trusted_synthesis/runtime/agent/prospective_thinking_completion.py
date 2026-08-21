from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Final, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

THINKING_COMPLETION_PROTOCOL_VERSION: Final = "prospective_thinking_completion_protocol.v1"
REDACTED_RESPONSE_ENVELOPE_VERSION: Final = "prospective_redacted_response_envelope.v1"
THINKING_FAILURE_ARTIFACT_VERSION: Final = "prospective_thinking_failure_artifact.v1"

CompletionRequestKind = Literal["decision", "final_answer"]
CompletionFailureKind = Literal[
    "empty_final_content",
    "invalid_json",
    "invalid_response_contract",
    "length_truncated_content",
    "reasoning_only_length_truncation",
]

_ALLOWED_DROPPED_FIELDS = frozenset(
    {
        "analysis_summary",
        "plan_summary",
        "rationale_summary",
    }
)
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


class HostPlanAttestation(FrozenModel):
    provider_call_made: Literal[False] = False
    host_plan_materialized: Literal[False] = False
    action_bearing_field_count: Literal[0] = 0
    model_tool_choice_preserved: Literal[True] = True
    model_argument_choice_preserved: Literal[True] = True
    model_answer_choice_preserved: Literal[True] = True
    private_reasoning_content_used: Literal[False] = False
    schema_version: Literal["prospective_host_plan_attestation.v1"] = (
        "prospective_host_plan_attestation.v1"
    )


class CompletionProjection(FrozenModel):
    request_kind: CompletionRequestKind
    action: Literal["call_tool"] | None = None
    tool_id: str | None = None
    arguments: dict[str, Any] | None = None
    answer: dict[str, Any] | None = None
    dropped_non_authority_fields: tuple[str, ...] = ()
    model_action_fields_preserved: Literal[True] = True
    host_action_field_insertions: Literal[0] = 0
    schema_version: Literal["prospective_completion_projection.v1"] = (
        "prospective_completion_projection.v1"
    )

    @model_validator(mode="after")
    def validate_projection(self) -> CompletionProjection:
        if self.request_kind == "decision":
            if self.action != "call_tool" or not self.tool_id or self.arguments is None:
                raise ValueError("decision projection requires a complete model tool call")
            if self.answer is not None:
                raise ValueError("decision projection cannot contain an answer")
        else:
            if self.answer is None:
                raise ValueError("final projection requires a model answer")
            if self.action is not None or self.tool_id is not None or self.arguments is not None:
                raise ValueError("final projection cannot contain a tool call")
        if not set(self.dropped_non_authority_fields) <= _ALLOWED_DROPPED_FIELDS:
            raise ValueError("projection attempted to drop an unregistered response field")
        return self


class ProspectiveThinkingCompletionProtocol(FrozenModel):
    contract_id: str = Field(min_length=1)
    thinking_type: Literal["enabled"] = "enabled"
    completion_upper_bound_tokens: Literal[4096] = 4096
    rollout_upper_bound_tokens: Literal[120000] = 120000
    prompt_upper_bound_bytes: Literal[60000] = 60000
    chat_envelope_tokens: Literal[256] = 256
    model_plan_request_count: Literal[0] = 0
    host_plan_action_bearing_field_count: Literal[0] = 0
    maximum_rescue_calls_per_job: Literal[1] = 1
    rescue_reuses_previous_final_content: Literal[False] = False
    rescue_reuses_private_reasoning: Literal[False] = False
    rescue_uses_public_state_and_typed_failure_only: Literal[True] = True
    rescue_is_independent_public_decision_terminal_phase: Literal[True] = True
    rescue_requests_repeated_planning_or_deliberation: Literal[False] = False
    rescue_requires_immediate_json: Literal[True] = True
    every_rescue_prompt_strictly_shorter_than_primary: Literal[True] = True
    minimum_rescue_prompt_reduction_basis_points: Literal[1000] = 1000
    decision_response_fields: tuple[str, ...] = ("action", "arguments", "tool_id")
    final_response_fields: tuple[str, ...] = ("answer",)
    free_text_rationale_required: Literal[False] = False
    model_tool_choice_preserved: Literal[True] = True
    model_argument_choice_preserved: Literal[True] = True
    model_answer_choice_preserved: Literal[True] = True
    allowed_dropped_non_authority_fields: tuple[str, ...] = tuple(sorted(_ALLOWED_DROPPED_FIELDS))
    rescue_failure_types: tuple[CompletionFailureKind, ...] = (
        "empty_final_content",
        "invalid_json",
        "invalid_response_contract",
        "length_truncated_content",
        "reasoning_only_length_truncation",
    )
    completion_failure_gate_threshold: float = 0.1
    completion_failure_gate_requires_zero_of_32: Literal[True] = True
    completion_threshold_relaxation_forbidden: Literal[True] = True
    empirical_usability_unresolved: Literal[True] = True
    schema_version: Literal["prospective_thinking_completion_protocol.v1"] = (
        THINKING_COMPLETION_PROTOCOL_VERSION
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveThinkingCompletionProtocol:
        if set(self.allowed_dropped_non_authority_fields) != _ALLOWED_DROPPED_FIELDS:
            raise ValueError("allowed non-authority projection fields changed")
        if len(set(self.rescue_failure_types)) != len(self.rescue_failure_types):
            raise ValueError("rescue failure types must be unique")
        if self.completion_failure_gate_threshold != 0.1:
            raise ValueError("Completion failure Gate threshold changed")
        if self.contract_id != prospective_thinking_completion_protocol_id(self):
            raise ValueError("prospective Thinking Completion protocol identity mismatch")
        return self


class RedactedProviderResponseEnvelope(FrozenModel):
    response_model: str = Field(min_length=1)
    finish_reason: str | None = None
    public_content_sha256: str = Field(min_length=64, max_length=64)
    public_content_length: int = Field(ge=0)
    provider_native_tool_call_observed: bool
    reasoning_content_present: bool
    reasoning_content_length: int = Field(ge=0)
    reasoning_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    raw_http_body_persisted: Literal[False] = False
    schema_version: Literal["prospective_redacted_response_envelope.v1"] = (
        REDACTED_RESPONSE_ENVELOPE_VERSION
    )

    @model_validator(mode="after")
    def validate_reasoning_presence(self) -> RedactedProviderResponseEnvelope:
        if self.reasoning_content_present != (self.reasoning_content_length > 0):
            raise ValueError("reasoning presence and length differ")
        return self


class RedactedProviderResponseFields(TypedDict):
    response_model: str | None
    finish_reason: str | None
    public_content_sha256: str | None
    public_content_length: int | None
    provider_native_tool_call_observed: bool | None
    reasoning_content_present: bool | None
    reasoning_content_length: int | None
    reasoning_tokens: int | None
    completion_tokens: int | None


class ProspectiveThinkingFailureArtifact(FrozenModel):
    failure_artifact_id: str = Field(min_length=1)
    failure_type: (
        CompletionFailureKind
        | Literal[
            "provider_native_tool_call",
            "response_envelope_invalid",
        ]
    )
    request_hash: str = Field(min_length=64, max_length=64)
    response_envelope: RedactedProviderResponseEnvelope | None = None
    previous_final_content_persisted: Literal[False] = False
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    raw_http_body_persisted: Literal[False] = False
    validated_before_serialization: Literal[True] = True
    schema_version: Literal["prospective_thinking_failure_artifact.v1"] = (
        THINKING_FAILURE_ARTIFACT_VERSION
    )

    @model_validator(mode="after")
    def validate_identity(self) -> ProspectiveThinkingFailureArtifact:
        if self.failure_artifact_id != prospective_thinking_failure_artifact_id(self):
            raise ValueError("prospective Thinking failure artifact identity mismatch")
        if self.failure_type != "response_envelope_invalid" and self.response_envelope is None:
            raise ValueError("HTTP-success parse failure requires a redacted response envelope")
        return self


def prospective_thinking_completion_protocol_id(
    value: ProspectiveThinkingCompletionProtocol,
) -> str:
    payload = value.model_dump(mode="json")
    payload.pop("contract_id", None)
    return canonical_hash(payload, prefix="prospective_thinking_completion_protocol:")


def prospective_thinking_failure_artifact_id(
    value: ProspectiveThinkingFailureArtifact,
) -> str:
    payload = value.model_dump(mode="json")
    payload.pop("failure_artifact_id", None)
    return canonical_hash(payload, prefix="prospective_thinking_failure_artifact:")


def make_prospective_thinking_completion_protocol() -> ProspectiveThinkingCompletionProtocol:
    provisional = ProspectiveThinkingCompletionProtocol.model_construct(contract_id="pending")
    return ProspectiveThinkingCompletionProtocol(
        contract_id=prospective_thinking_completion_protocol_id(provisional)
    )


def host_plan_attestation() -> HostPlanAttestation:
    return HostPlanAttestation()


def _assert_no_forbidden_public_keys(value: Any, *, path: str = "capsule") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).casefold()
            if normalized in _FORBIDDEN_PUBLIC_KEYS:
                raise ValueError(f"forbidden public Completion field at {path}.{key}")
            _assert_no_forbidden_public_keys(item, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_no_forbidden_public_keys(item, path=f"{path}[{index}]")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _public_prompt_payload(source_prompt: str) -> dict[str, Any]:
    _, separator, raw_payload = source_prompt.partition("\n")
    if not separator:
        raise ValueError("compact source Prompt lacks a public JSON payload")
    payload = json.loads(raw_payload)
    if not isinstance(payload, dict):
        raise ValueError("compact source Prompt payload must be an object")
    _assert_no_forbidden_public_keys(payload)
    return payload


def _response_contract(request_kind: CompletionRequestKind) -> dict[str, Any]:
    if request_kind == "decision":
        return {
            "action": "call_tool",
            "fields": ("action", "arguments", "tool_id"),
            "free_text_fields": "forbidden",
        }
    return {
        "fields": ("answer",),
        "free_text_fields": "forbidden",
    }


def _primary_completion_payload(
    request_kind: CompletionRequestKind,
    source_prompt: str,
) -> dict[str, Any]:
    payload = _public_prompt_payload(source_prompt)
    payload["response_contract"] = _response_contract(request_kind)
    _assert_no_forbidden_public_keys(payload)
    return payload


def _rescue_completion_payload(
    request_kind: CompletionRequestKind,
    source_prompt: str,
    failure_type: CompletionFailureKind,
) -> dict[str, Any]:
    payload = _public_prompt_payload(source_prompt)
    if request_kind == "decision":
        context = payload.get("public_context")
        if not isinstance(context, Mapping):
            raise ValueError("decision Prompt lacks public context")
        task = context.get("task")
        if not isinstance(task, Mapping):
            raise ValueError("decision Prompt lacks public task")
        progress = payload.get("progress")
        if not isinstance(progress, Mapping):
            raise ValueError("decision Prompt lacks public progress")
        history = payload.get("history")
        if not isinstance(history, Mapping):
            raise ValueError("decision Prompt lacks public history")
        rescue_history = {
            key: history.get(key)
            for key in (
                "acquisitions",
                "failed_actions",
                "pending_search",
                "selected_evidence_ids",
            )
        }
        capsule = {
            "instruction": task.get("instruction"),
            "path": payload.get("public_path_condition"),
            "operation": context.get("public_operation"),
            "progress": progress,
            "history": rescue_history,
            "tools": context.get("tools"),
            "response_contract": _response_contract(request_kind),
        }
        if rescue_history["failed_actions"]:
            capsule["repair"] = context.get("repair")
        if progress.get("terminal_node_completed"):
            capsule["terminal_verification"] = context.get("terminal_verification")
    else:
        capsule = {
            "final_context": payload.get("final_context"),
            "response_contract": _response_contract(request_kind),
        }
    capsule["rescue"] = {
        "failure_type": failure_type,
        "previous_final_content_reused": False,
        "private_reasoning_reused": False,
        "repeat_planning_or_deliberation": False,
        "same_public_state": True,
    }
    _assert_no_forbidden_public_keys(capsule)
    return capsule


def render_primary_completion_prompt(
    request_kind: CompletionRequestKind,
    source_prompt: str,
) -> str:
    capsule = _primary_completion_payload(request_kind, source_prompt)
    header = "Return required compact JSON only. No rationale."
    return f"{header}\n{_canonical_json(capsule)}"


def render_rescue_completion_prompt(
    request_kind: CompletionRequestKind,
    source_prompt: str,
    failure_type: CompletionFailureKind,
) -> str:
    capsule = _rescue_completion_payload(request_kind, source_prompt, failure_type)
    header = (
        "Single public decision terminal phase: emit the required compact JSON immediately. "
        "Do not repeat planning, deliberation, or the previous response."
    )
    _assert_no_forbidden_public_keys(capsule)
    return f"{header}\n{_canonical_json(capsule)}"


def project_model_completion(
    request_kind: CompletionRequestKind,
    payload: Mapping[str, Any],
) -> CompletionProjection:
    _assert_no_forbidden_public_keys(payload, path="response")
    required = (
        frozenset({"action", "arguments", "tool_id"})
        if request_kind == "decision"
        else frozenset({"answer"})
    )
    keys = frozenset(str(key) for key in payload)
    missing = required - keys
    if missing:
        raise ValueError(f"model Completion lacks required fields: {tuple(sorted(missing))}")
    dropped = tuple(sorted(keys - required))
    if not set(dropped) <= _ALLOWED_DROPPED_FIELDS:
        raise ValueError("model Completion contains unregistered extra fields")
    if request_kind == "decision":
        if payload.get("action") != "call_tool":
            raise ValueError("decision Completion must choose call_tool")
        tool_id = str(payload.get("tool_id") or "").strip()
        arguments = payload.get("arguments")
        if not tool_id or not isinstance(arguments, Mapping):
            raise ValueError("decision Completion lacks tool_id or arguments")
        return CompletionProjection(
            request_kind=request_kind,
            action="call_tool",
            tool_id=tool_id,
            arguments={str(key): item for key, item in arguments.items()},
            dropped_non_authority_fields=dropped,
        )
    answer = payload.get("answer")
    if not isinstance(answer, Mapping):
        raise ValueError("final Completion answer must be an object")
    return CompletionProjection(
        request_kind=request_kind,
        answer={str(key): item for key, item in answer.items()},
        dropped_non_authority_fields=dropped,
    )


def capture_redacted_provider_response_fields(
    response_body: Mapping[str, Any],
) -> RedactedProviderResponseFields:
    response_model = str(response_body.get("model") or "").strip() or None
    choices = response_body.get("choices")
    choice = (
        choices[0]
        if isinstance(choices, Sequence)
        and not isinstance(choices, (str, bytes))
        and choices
        and isinstance(choices[0], Mapping)
        else None
    )
    raw_message = choice.get("message") if isinstance(choice, Mapping) else None
    message = raw_message if isinstance(raw_message, Mapping) else None
    raw_content = message.get("content") if message is not None else None
    content = "" if raw_content is None else str(raw_content)
    raw_reasoning = message.get("reasoning_content") if message is not None else None
    reasoning_length = (
        len(str(raw_reasoning)) if message is not None and raw_reasoning is not None else 0
    )
    usage = response_body.get("usage")
    details = usage.get("completion_tokens_details") if isinstance(usage, Mapping) else None

    def optional_int(value: Any) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    return {
        "response_model": response_model,
        "finish_reason": (
            str(choice["finish_reason"])
            if isinstance(choice, Mapping) and choice.get("finish_reason") is not None
            else None
        ),
        "public_content_sha256": (
            hashlib.sha256(content.encode("utf-8")).hexdigest() if message is not None else None
        ),
        "public_content_length": len(content) if message is not None else None,
        "provider_native_tool_call_observed": (
            bool(message.get("tool_calls") or message.get("function_call"))
            if message is not None
            else None
        ),
        "reasoning_content_present": reasoning_length > 0 if message is not None else None,
        "reasoning_content_length": reasoning_length if message is not None else None,
        "reasoning_tokens": (
            optional_int(details.get("reasoning_tokens")) if isinstance(details, Mapping) else None
        ),
        "completion_tokens": (
            optional_int(usage.get("completion_tokens", usage.get("output_tokens")))
            if isinstance(usage, Mapping)
            else None
        ),
    }


def capture_redacted_provider_response_envelope(
    response_body: Mapping[str, Any],
) -> RedactedProviderResponseEnvelope:
    fields = capture_redacted_provider_response_fields(response_body)
    return RedactedProviderResponseEnvelope.model_validate(fields)


def require_admitted_response_envelope(
    envelope: RedactedProviderResponseEnvelope,
    *,
    expected_model: str,
) -> None:
    if envelope.response_model != expected_model:
        raise ValueError("response envelope model does not match the exact requested model")
    if envelope.provider_native_tool_call_observed:
        raise ValueError("response envelope contains a forbidden Provider-native tool call")
    if (
        not envelope.reasoning_content_present
        or envelope.reasoning_content_length == 0
        or envelope.reasoning_tokens == 0
    ):
        raise ValueError("response envelope lacks positive Thinking telemetry")


def make_prospective_thinking_failure_artifact(
    *,
    failure_type: CompletionFailureKind
    | Literal["provider_native_tool_call", "response_envelope_invalid"],
    request_hash: str,
    response_envelope: RedactedProviderResponseEnvelope | None,
) -> ProspectiveThinkingFailureArtifact:
    values = {
        "failure_type": failure_type,
        "request_hash": request_hash,
        "response_envelope": response_envelope,
    }
    provisional = ProspectiveThinkingFailureArtifact.model_construct(
        failure_artifact_id="pending",
        **values,
    )
    return ProspectiveThinkingFailureArtifact(
        failure_artifact_id=prospective_thinking_failure_artifact_id(provisional),
        **values,
    )


def serialize_validated_failure_artifact(
    artifact: ProspectiveThinkingFailureArtifact,
) -> bytes:
    validated = ProspectiveThinkingFailureArtifact.model_validate(artifact.model_dump(mode="json"))
    return json.dumps(
        validated.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
