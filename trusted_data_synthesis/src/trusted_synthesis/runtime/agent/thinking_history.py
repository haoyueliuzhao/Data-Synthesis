from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry

THINKING_CONTINUITY_CONTRACT_VERSION = "thinking_continuity_contract.v1"
THINKING_TURN_ATTESTATION_VERSION = "thinking_turn_attestation.v1"
THINKING_HISTORY_AUDIT_VERSION = "thinking_history_audit.v1"
COMPLETION_USABILITY_CLASSIFICATION_VERSION = "completion_usability_classification.v1"

PROVIDER_THINKING_GUIDE_URL = "https://api-docs.deepseek.com/guides/thinking_mode"

ContinuityAction = Literal[
    "omit_reasoning_for_host_instrumented_json_turn",
    "pass_reasoning_for_provider_native_tool_call",
]
CompletionOutcome = Literal[
    "typed_no_call",
    "provider_transport_failure",
    "thinking_telemetry_missing_or_empty",
    "reasoning_only_length_truncation",
    "length_truncated_content",
    "empty_final_content",
    "invalid_json_after_repair",
    "invalid_decision_contract_after_repair",
    "usable_after_contract_repair",
    "usable_structured_completion",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ThinkingContinuityContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    provider: Literal["deepseek"] = "deepseek"
    provider_guide_url: Literal["https://api-docs.deepseek.com/guides/thinking_mode"] = (
        "https://api-docs.deepseek.com/guides/thinking_mode"
    )
    provider_guide_checked_at: Literal["2026-08-21"] = "2026-08-21"
    interaction_protocol: Literal["host_instrumented_json_decision"] = (
        "host_instrumented_json_decision"
    )
    provider_native_tool_calls_allowed: Literal[False] = False
    provider_native_tool_call_reasoning_passback_required: Literal[True] = True
    current_turn_reasoning_passback_required: Literal[False] = False
    current_turn_continuity_action: Literal["omit_reasoning_for_host_instrumented_json_turn"] = (
        "omit_reasoning_for_host_instrumented_json_turn"
    )
    compact_public_state_reconstructed_per_request: Literal[True] = True
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    final_content_hash_excludes_reasoning_content: Literal[True] = True
    retained_reasoning_fields: tuple[str, ...] = (
        "reasoning_content_present",
        "reasoning_content_length",
        "reasoning_tokens",
    )
    turn_order_attestation_required: Literal[True] = True
    parent_attestation_binding_required: Literal[True] = True
    missing_or_out_of_order_attestation_fails_closed: Literal[True] = True
    provider_native_tool_call_fails_closed: Literal[True] = True
    verifier_reasoning_content_dependency_forbidden: Literal[True] = True
    state_mapper_reasoning_content_dependency_forbidden: Literal[True] = True
    schema_version: str = THINKING_CONTINUITY_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ThinkingContinuityContract:
        expected_fields = (
            "reasoning_content_present",
            "reasoning_content_length",
            "reasoning_tokens",
        )
        if self.retained_reasoning_fields != expected_fields:
            raise ValueError("thinking continuity retained private reasoning fields")
        if self.contract_id != thinking_continuity_contract_id(self):
            raise ValueError("thinking continuity Contract identity is invalid")
        return self


class ThinkingTurnAttestation(FrozenModel):
    attestation_id: str = Field(min_length=1)
    continuity_contract_id: str = Field(min_length=1)
    call_index: int = Field(ge=0)
    request_hash: str = Field(min_length=64, max_length=64)
    final_content_sha256: str = Field(min_length=64, max_length=64)
    parent_attestation_id: str | None = None
    provider_native_tool_call_observed: Literal[False] = False
    continuity_action: Literal["omit_reasoning_for_host_instrumented_json_turn"] = (
        "omit_reasoning_for_host_instrumented_json_turn"
    )
    reasoning_content_present: bool
    reasoning_content_length: int = Field(ge=0)
    reasoning_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    finish_reason: str | None = None
    json_contract_success: bool
    private_reasoning_content_persisted: Literal[False] = False
    private_reasoning_content_hashed: Literal[False] = False
    schema_version: str = THINKING_TURN_ATTESTATION_VERSION

    @model_validator(mode="after")
    def validate_attestation(self) -> ThinkingTurnAttestation:
        if self.call_index == 0 and self.parent_attestation_id is not None:
            raise ValueError("first thinking turn has a parent")
        if self.call_index > 0 and self.parent_attestation_id is None:
            raise ValueError("later thinking turn lacks a parent")
        if self.reasoning_content_present != (self.reasoning_content_length > 0):
            raise ValueError("thinking reasoning presence and length disagree")
        if not self.reasoning_content_present or self.reasoning_tokens == 0:
            raise ValueError("successful thinking turn lacks positive reasoning telemetry")
        if self.reasoning_tokens > self.completion_tokens:
            raise ValueError("reasoning tokens exceed completion Usage")
        if self.attestation_id != thinking_turn_attestation_id(self):
            raise ValueError("thinking turn attestation identity is invalid")
        return self


class ThinkingHistoryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    continuity_contract_id: str = Field(min_length=1)
    turns: tuple[ThinkingTurnAttestation, ...] = Field(min_length=1)
    turn_count: int = Field(ge=1)
    contiguous_order_passed: Literal[True] = True
    parent_binding_passed: Literal[True] = True
    private_reasoning_content_absent: Literal[True] = True
    provider_native_tool_call_absent: Literal[True] = True
    verifier_reasoning_independence_passed: Literal[True] = True
    state_mapper_reasoning_independence_passed: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: str = THINKING_HISTORY_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ThinkingHistoryAudit:
        if self.turn_count != len(self.turns):
            raise ValueError("thinking history denominator changed")
        if tuple(item.call_index for item in self.turns) != tuple(range(len(self.turns))):
            raise ValueError("thinking history order is not contiguous")
        for index, item in enumerate(self.turns):
            expected_parent = None if index == 0 else self.turns[index - 1].attestation_id
            if item.parent_attestation_id != expected_parent:
                raise ValueError("thinking history parent binding changed")
            if item.continuity_contract_id != self.continuity_contract_id:
                raise ValueError("thinking history crosses continuity Contracts")
        if self.audit_id != thinking_history_audit_id(self):
            raise ValueError("thinking history audit identity is invalid")
        return self


class CompletionUsabilityClassification(FrozenModel):
    classification_id: str = Field(min_length=1)
    request_index: int = Field(ge=0)
    provider_call_made: bool
    typed_no_call: bool
    completion_outcome: CompletionOutcome
    completion_unusable: bool
    resource_no_call: bool
    completion_limit_hit: bool
    reasoning_content_present: bool
    reasoning_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    reasoning_token_fraction: float | None = Field(default=None, ge=0, le=1)
    contract_repair_attempted: bool
    contract_repair_succeeded: bool
    model_validity_evaluated: Literal[False] = False
    schema_version: str = COMPLETION_USABILITY_CLASSIFICATION_VERSION

    @model_validator(mode="after")
    def validate_classification(self) -> CompletionUsabilityClassification:
        if self.resource_no_call != (self.completion_outcome == "typed_no_call"):
            raise ValueError("resource no-call and completion outcome were conflated")
        if self.typed_no_call != self.resource_no_call:
            raise ValueError("typed no-call classification changed")
        if self.resource_no_call and (self.provider_call_made or self.completion_unusable):
            raise ValueError("typed no-call entered the completion denominator")
        completion_failures = {
            "thinking_telemetry_missing_or_empty",
            "reasoning_only_length_truncation",
            "length_truncated_content",
            "empty_final_content",
            "invalid_json_after_repair",
            "invalid_decision_contract_after_repair",
        }
        if self.completion_unusable != (self.completion_outcome in completion_failures):
            raise ValueError("completion usability taxonomy changed")
        if self.reasoning_token_fraction is not None:
            if self.reasoning_tokens is None or self.completion_tokens in (None, 0):
                raise ValueError("reasoning fraction lacks Usage fields")
        if self.classification_id != completion_usability_classification_id(self):
            raise ValueError("completion usability identity is invalid")
        return self


def thinking_continuity_contract_id(value: ThinkingContinuityContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="thinking_continuity_contract:",
    )


def thinking_turn_attestation_id(value: ThinkingTurnAttestation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"attestation_id"}),
        prefix="thinking_turn_attestation:",
    )


def thinking_history_audit_id(value: ThinkingHistoryAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="thinking_history_audit:",
    )


def completion_usability_classification_id(
    value: CompletionUsabilityClassification,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"classification_id"}),
        prefix="completion_usability_classification:",
    )


def make_thinking_continuity_contract() -> ThinkingContinuityContract:
    provisional = ThinkingContinuityContract.model_construct(contract_id="pending")
    return ThinkingContinuityContract(contract_id=thinking_continuity_contract_id(provisional))


def attest_thinking_turn(
    *,
    contract: ThinkingContinuityContract,
    call_index: int,
    telemetry: ModelCallTelemetry,
    parent_attestation_id: str | None,
    provider_native_tool_call_observed: bool = False,
) -> ThinkingTurnAttestation:
    if provider_native_tool_call_observed:
        raise ValueError(
            "provider-native tool calls require private reasoning passback and are forbidden"
        )
    if not telemetry.http_success:
        raise ValueError("thinking attestation requires an HTTP-success response")
    if telemetry.response_hash is None:
        raise ValueError("thinking turn lacks a final-content hash")
    if telemetry.reasoning_content_length is None or telemetry.reasoning_tokens is None:
        raise ValueError("thinking turn lacks redacted reasoning telemetry")
    if (
        not telemetry.reasoning_content_present
        or telemetry.reasoning_content_length == 0
        or telemetry.reasoning_tokens == 0
    ):
        raise ValueError("thinking turn lacks positive reasoning telemetry")
    if telemetry.completion_tokens is None:
        raise ValueError("thinking turn lacks completion Usage")
    values = {
        "continuity_contract_id": contract.contract_id,
        "call_index": call_index,
        "request_hash": telemetry.request_hash,
        "final_content_sha256": telemetry.response_hash,
        "parent_attestation_id": parent_attestation_id,
        "reasoning_content_present": telemetry.reasoning_content_present,
        "reasoning_content_length": telemetry.reasoning_content_length,
        "reasoning_tokens": telemetry.reasoning_tokens,
        "completion_tokens": telemetry.completion_tokens,
        "finish_reason": telemetry.finish_reason,
        "json_contract_success": telemetry.json_contract_success,
    }
    provisional = ThinkingTurnAttestation.model_construct(
        attestation_id="pending",
        **values,
    )
    return ThinkingTurnAttestation(
        attestation_id=thinking_turn_attestation_id(provisional),
        **values,
    )


def audit_thinking_history(
    contract: ThinkingContinuityContract,
    turns: tuple[ThinkingTurnAttestation, ...],
) -> ThinkingHistoryAudit:
    values = {
        "continuity_contract_id": contract.contract_id,
        "turns": turns,
        "turn_count": len(turns),
    }
    provisional = ThinkingHistoryAudit.model_construct(audit_id="pending", **values)
    return ThinkingHistoryAudit(
        audit_id=thinking_history_audit_id(provisional),
        **values,
    )


def classify_completion_usability(
    *,
    request_index: int,
    telemetry: ModelCallTelemetry | None,
    typed_no_call: bool = False,
    final_content_present: bool = True,
    decision_contract_valid: bool = True,
    contract_repair_attempted: bool = False,
    contract_repair_succeeded: bool = False,
) -> CompletionUsabilityClassification:
    if typed_no_call:
        if telemetry is not None:
            raise ValueError("typed no-call unexpectedly has Provider telemetry")
        outcome: CompletionOutcome = "typed_no_call"
        provider_call_made = False
        limit_hit = False
    else:
        if telemetry is None:
            raise ValueError("completion classification lacks Provider telemetry")
        provider_call_made = True
        limit_hit = telemetry.finish_reason == "length"
        if not telemetry.http_success:
            outcome = "provider_transport_failure"
        elif (
            not telemetry.reasoning_content_present
            or telemetry.reasoning_content_length in (None, 0)
            or telemetry.reasoning_tokens in (None, 0)
        ):
            outcome = "thinking_telemetry_missing_or_empty"
        elif limit_hit and not final_content_present and telemetry.reasoning_content_present:
            outcome = "reasoning_only_length_truncation"
        elif limit_hit:
            outcome = "length_truncated_content"
        elif not final_content_present:
            outcome = "empty_final_content"
        elif not telemetry.json_contract_success and not contract_repair_succeeded:
            outcome = "invalid_json_after_repair"
        elif not decision_contract_valid and not contract_repair_succeeded:
            outcome = "invalid_decision_contract_after_repair"
        elif contract_repair_succeeded:
            outcome = "usable_after_contract_repair"
        else:
            outcome = "usable_structured_completion"
    completion_failures = {
        "thinking_telemetry_missing_or_empty",
        "reasoning_only_length_truncation",
        "length_truncated_content",
        "empty_final_content",
        "invalid_json_after_repair",
        "invalid_decision_contract_after_repair",
    }
    reasoning_tokens = telemetry.reasoning_tokens if telemetry is not None else None
    completion_tokens = telemetry.completion_tokens if telemetry is not None else None
    fraction = (
        reasoning_tokens / completion_tokens
        if reasoning_tokens is not None and completion_tokens not in (None, 0)
        else None
    )
    values = {
        "request_index": request_index,
        "provider_call_made": provider_call_made,
        "typed_no_call": typed_no_call,
        "completion_outcome": outcome,
        "completion_unusable": outcome in completion_failures,
        "resource_no_call": typed_no_call,
        "completion_limit_hit": limit_hit,
        "reasoning_content_present": (
            telemetry.reasoning_content_present if telemetry is not None else False
        ),
        "reasoning_tokens": reasoning_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_token_fraction": fraction,
        "contract_repair_attempted": contract_repair_attempted,
        "contract_repair_succeeded": contract_repair_succeeded,
    }
    provisional = CompletionUsabilityClassification.model_construct(
        classification_id="pending",
        **values,
    )
    return CompletionUsabilityClassification(
        classification_id=completion_usability_classification_id(provisional),
        **values,
    )
