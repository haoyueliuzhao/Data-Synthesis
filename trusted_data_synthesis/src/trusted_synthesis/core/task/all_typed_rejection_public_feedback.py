from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.joint_presentation_receipt_hardening import (
    DISPLAY_CHOICE_PATTERN,
    ActionAcceptanceReport,
    HardenedPublicPrompt,
    HardenedPublicState,
)
from trusted_synthesis.core.task.public_semantic_capability_depth import (
    PUBLIC_ACTION_ID_LENGTH,
    canonical_bytes,
    scan_model_visible_leakage,
)
from trusted_synthesis.hashing import canonical_hash

ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION: Final = "all_typed_rejection_public_feedback.v1"
MAX_CORRECTION_ATTEMPTS: Final = 1
PUBLIC_ACTION_ID_PATTERN: Final = rf"^[0-9a-f]{{{PUBLIC_ACTION_ID_LENGTH}}}$"

PUBLIC_FEEDBACK_FIELDS: Final = (
    "feedback_id",
    "public_rejected_action_id",
    "public_displayed_choice_handle",
    "public_rejection_code",
    "public_observation_receipt_id",
    "correction_attempt_index",
    "correction_attempt_bound",
    "predecessor_public_feedback_id",
    "schema_version",
)

PROHIBITED_PUBLIC_FEEDBACK_KEYS: Final = frozenset(
    {
        "package_id",
        "component_key",
        "source_choice_handle",
        "selected_operation_hash",
        "reference_choice_handle",
        "reference_path_hash",
        "schedule_id",
        "schedule_ids",
        "seed_commitment",
        "derivation_nonce",
        "source_package_artifact_id",
        "source_development_package_artifact_id",
        "action_acceptance_report",
        "action_acceptance_report_id",
        "replica_index",
    }
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


def strict_public_feedback_findings(value: Any, path: str = "$") -> tuple[str, ...]:
    findings: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).casefold()
            if key_text in PROHIBITED_PUBLIC_FEEDBACK_KEYS:
                findings.append(f"{path}.{key}:host_only_feedback_key")
            findings.extend(strict_public_feedback_findings(item, f"{path}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            findings.extend(strict_public_feedback_findings(item, f"{path}[{index}]"))
    return tuple(sorted(set(findings)))


class PublicTypedRejectionObservation(FrozenModel):
    public_observation_receipt_id: str = Field(min_length=1)
    public_state_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    public_rejected_action_id: str = Field(pattern=PUBLIC_ACTION_ID_PATTERN)
    public_displayed_choice_handle: str = Field(pattern=DISPLAY_CHOICE_PATTERN)
    public_rejection_code: str = Field(min_length=1)
    correction_attempt_index: int = Field(ge=1, le=MAX_CORRECTION_ATTEMPTS + 1)
    correction_attempt_bound: Literal[1] = MAX_CORRECTION_ATTEMPTS
    action_committed: Literal[False] = False
    schema_version: str = ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> PublicTypedRejectionObservation:
        visible = self.model_dump(
            mode="json",
            exclude={"public_observation_receipt_id"},
        )
        if scan_model_visible_leakage(visible) or strict_public_feedback_findings(visible):
            raise ValueError("public typed-rejection Observation exposes Host-only content")
        if self.public_observation_receipt_id != _identity(
            self,
            "public_observation_receipt_id",
            "public_typed_rejection_observation:",
        ):
            raise ValueError("public typed-rejection Observation identity is invalid")
        return self


class PublicTypedRejectionFeedback(FrozenModel):
    feedback_id: str = Field(min_length=1)
    public_rejected_action_id: str = Field(pattern=PUBLIC_ACTION_ID_PATTERN)
    public_displayed_choice_handle: str = Field(pattern=DISPLAY_CHOICE_PATTERN)
    public_rejection_code: str = Field(min_length=1)
    public_observation_receipt_id: str = Field(min_length=1)
    correction_attempt_index: int = Field(ge=1, le=MAX_CORRECTION_ATTEMPTS + 1)
    correction_attempt_bound: Literal[1] = MAX_CORRECTION_ATTEMPTS
    predecessor_public_feedback_id: str | None = None
    schema_version: str = ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_feedback(self) -> PublicTypedRejectionFeedback:
        visible = self.model_dump(mode="json", exclude={"feedback_id"})
        if tuple(type(self).model_fields) != PUBLIC_FEEDBACK_FIELDS:
            raise ValueError("public typed-rejection Feedback schema changed")
        if scan_model_visible_leakage(visible) or strict_public_feedback_findings(visible):
            raise ValueError("public typed-rejection Feedback exposes Host-only content")
        if self.correction_attempt_index == 1 and self.predecessor_public_feedback_id is not None:
            raise ValueError("first public Feedback unexpectedly has a predecessor")
        if self.correction_attempt_index > 1 and self.predecessor_public_feedback_id is None:
            raise ValueError("later public Feedback is missing its public predecessor")
        if self.feedback_id != _identity(
            self,
            "feedback_id",
            "public_typed_rejection_feedback:",
        ):
            raise ValueError("public typed-rejection Feedback identity is invalid")
        return self


class HostTypedRejectionBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    component_key: str = Field(min_length=1)
    source_choice_handle: str = Field(min_length=1)
    selected_operation_hash: str = Field(min_length=1)
    action_acceptance_report_id: str = Field(min_length=1)
    runtime_event_ids: tuple[str, ...] = Field(min_length=1)
    public_observation_receipt_id: str = Field(min_length=1)
    public_feedback_id: str = Field(min_length=1)
    model_visible: Literal[False] = False
    schema_version: str = ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> HostTypedRejectionBinding:
        if len(self.runtime_event_ids) != len(set(self.runtime_event_ids)):
            raise ValueError("Host typed-rejection Binding repeats a Runtime event")
        if self.binding_id != _identity(
            self,
            "binding_id",
            "host_typed_rejection_binding:",
        ):
            raise ValueError("Host typed-rejection Binding identity is invalid")
        return self


class PublicCorrectionBoundTerminal(FrozenModel):
    terminal_id: str = Field(min_length=1)
    public_state_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    first_public_feedback_id: str = Field(min_length=1)
    second_public_feedback_id: str | None = None
    second_public_action_reference: str = Field(min_length=1)
    second_response_class: Literal[
        "same_current_invalid",
        "different_current_invalid",
        "stale_action_id",
        "foreign_or_unbound_action_id",
        "malformed_action_reference",
    ]
    terminal_reason: Literal[
        "correction_attempt_typed_invalid",
        "correction_action_reference_invalid",
    ]
    correction_attempt_bound: Literal[1] = MAX_CORRECTION_ATTEMPTS
    action_committed: Literal[False] = False
    later_prompt_allowed: Literal[False] = False
    schema_version: str = ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_terminal(self) -> PublicCorrectionBoundTerminal:
        typed_current = self.second_response_class in {
            "same_current_invalid",
            "different_current_invalid",
        }
        if typed_current != (self.second_public_feedback_id is not None):
            raise ValueError("correction terminal public Feedback binding is inconsistent")
        if typed_current != (self.terminal_reason == "correction_attempt_typed_invalid"):
            raise ValueError("correction terminal reason is inconsistent")
        visible = self.model_dump(mode="json", exclude={"terminal_id"})
        if scan_model_visible_leakage(visible) or strict_public_feedback_findings(visible):
            raise ValueError("public correction terminal exposes Host-only content")
        if self.terminal_id != _identity(
            self,
            "terminal_id",
            "public_correction_bound_terminal:",
        ):
            raise ValueError("public correction terminal identity is invalid")
        return self


def make_public_typed_rejection_observation(
    *,
    prompt: HardenedPublicPrompt,
    public_rejected_action_id: str,
    public_displayed_choice_handle: str,
    public_rejection_code: str,
    correction_attempt_index: int,
) -> PublicTypedRejectionObservation:
    matches = tuple(
        item
        for item in prompt.candidates
        if item.action_id == public_rejected_action_id
        and item.choice_handle == public_displayed_choice_handle
    )
    if len(matches) != 1:
        raise ValueError("public rejection Observation action is absent from its Prompt")
    values = {
        "public_state_token": prompt.state.state_token,
        "public_rejected_action_id": public_rejected_action_id,
        "public_displayed_choice_handle": public_displayed_choice_handle,
        "public_rejection_code": public_rejection_code,
        "correction_attempt_index": correction_attempt_index,
    }
    provisional = PublicTypedRejectionObservation.model_construct(
        public_observation_receipt_id="pending",
        **values,
    )
    return PublicTypedRejectionObservation(
        public_observation_receipt_id=_identity(
            provisional,
            "public_observation_receipt_id",
            "public_typed_rejection_observation:",
        ),
        **values,
    )


def make_public_typed_rejection_feedback(
    *,
    observation: PublicTypedRejectionObservation,
    predecessor_public_feedback_id: str | None,
) -> PublicTypedRejectionFeedback:
    values = {
        "public_rejected_action_id": observation.public_rejected_action_id,
        "public_displayed_choice_handle": observation.public_displayed_choice_handle,
        "public_rejection_code": observation.public_rejection_code,
        "public_observation_receipt_id": observation.public_observation_receipt_id,
        "correction_attempt_index": observation.correction_attempt_index,
        "predecessor_public_feedback_id": predecessor_public_feedback_id,
    }
    provisional = PublicTypedRejectionFeedback.model_construct(
        feedback_id="pending",
        **values,
    )
    return PublicTypedRejectionFeedback(
        feedback_id=_identity(
            provisional,
            "feedback_id",
            "public_typed_rejection_feedback:",
        ),
        **values,
    )


def make_host_typed_rejection_binding(
    *,
    package_id: str,
    component_key: str,
    source_choice_handle: str,
    acceptance: ActionAcceptanceReport,
    runtime_event_ids: Sequence[str],
    observation: PublicTypedRejectionObservation,
    feedback: PublicTypedRejectionFeedback,
) -> HostTypedRejectionBinding:
    if acceptance.accepted or acceptance.rejection_code is None:
        raise ValueError("Host rejection Binding requires one rejected Acceptance")
    if acceptance.rejection_code != observation.public_rejection_code:
        raise ValueError("Host rejection Binding crosses its public rejection code")
    if feedback.public_observation_receipt_id != observation.public_observation_receipt_id:
        raise ValueError("Host rejection Binding crosses public Observation/Feedback")
    values = {
        "package_id": package_id,
        "component_key": component_key,
        "source_choice_handle": source_choice_handle,
        "selected_operation_hash": acceptance.selected_operation_hash,
        "action_acceptance_report_id": acceptance.report_id,
        "runtime_event_ids": tuple(runtime_event_ids),
        "public_observation_receipt_id": observation.public_observation_receipt_id,
        "public_feedback_id": feedback.feedback_id,
    }
    provisional = HostTypedRejectionBinding.model_construct(binding_id="pending", **values)
    return HostTypedRejectionBinding(
        binding_id=_identity(
            provisional,
            "binding_id",
            "host_typed_rejection_binding:",
        ),
        **values,
    )


def prompt_with_public_typed_rejection_history(
    prompt: HardenedPublicPrompt,
    feedback: tuple[PublicTypedRejectionFeedback, ...],
) -> HardenedPublicPrompt:
    if not feedback:
        return prompt
    expected_attempts = tuple(range(1, len(feedback) + 1))
    if tuple(item.correction_attempt_index for item in feedback) != expected_attempts:
        raise ValueError("public typed-rejection Feedback attempts are not contiguous")
    for index, item in enumerate(feedback):
        expected_parent = feedback[index - 1].feedback_id if index else None
        if item.predecessor_public_feedback_id != expected_parent:
            raise ValueError("public typed-rejection Feedback chain is not contiguous")

    facts: dict[str, Any] = dict(prompt.state.facts)
    facts["public_typed_rejection_feedback"] = tuple(
        item.model_dump(mode="json") for item in feedback
    )
    facts["public_correction_attempt_index"] = len(feedback)
    facts["public_correction_attempt_bound"] = MAX_CORRECTION_ATTEMPTS
    if strict_public_feedback_findings(facts):
        raise ValueError("public typed-rejection Prompt contains a prohibited Feedback field")
    state_values = {
        "decision_kind": prompt.state.decision_kind,
        "tool_id": prompt.state.tool_id,
        "facts": facts,
        "argument_fields": prompt.state.argument_fields,
        "argument_value_catalogs": prompt.state.argument_value_catalogs,
        "choice_legend": prompt.state.choice_legend,
        "prior_observations": prompt.state.prior_observations,
        "failure_receipt": prompt.state.failure_receipt,
        "schema_version": prompt.state.schema_version,
    }
    provisional = HardenedPublicState.model_construct(state_token="0" * 24, **state_values)
    visible = provisional.model_dump(mode="json", exclude={"state_token"})
    state = HardenedPublicState(
        state_token=hashlib.sha256(canonical_bytes(visible)).hexdigest()[:24],
        **state_values,
    )
    payload = {
        "task": prompt.task.model_dump(mode="json"),
        "state": state.model_dump(mode="json"),
        "candidates": [item.model_dump(mode="json") for item in prompt.candidates],
    }
    rendered = canonical_bytes(payload)
    return HardenedPublicPrompt(
        prompt_hash=hashlib.sha256(rendered).hexdigest(),
        rendered_bytes=len(rendered),
        task=prompt.task,
        state=state,
        candidates=prompt.candidates,
    )


def make_public_correction_bound_terminal(
    *,
    public_state_token: str,
    first_public_feedback_id: str,
    second_public_feedback_id: str | None,
    second_public_action_reference: str,
    second_response_class: Literal[
        "same_current_invalid",
        "different_current_invalid",
        "stale_action_id",
        "foreign_or_unbound_action_id",
        "malformed_action_reference",
    ],
) -> PublicCorrectionBoundTerminal:
    typed_current = second_response_class in {
        "same_current_invalid",
        "different_current_invalid",
    }
    values = {
        "public_state_token": public_state_token,
        "first_public_feedback_id": first_public_feedback_id,
        "second_public_feedback_id": second_public_feedback_id,
        "second_public_action_reference": second_public_action_reference,
        "second_response_class": second_response_class,
        "terminal_reason": (
            "correction_attempt_typed_invalid"
            if typed_current
            else "correction_action_reference_invalid"
        ),
    }
    provisional = PublicCorrectionBoundTerminal.model_construct(
        terminal_id="pending",
        **values,
    )
    return PublicCorrectionBoundTerminal(
        terminal_id=_identity(
            provisional,
            "terminal_id",
            "public_correction_bound_terminal:",
        ),
        **values,
    )


def public_feedback_identity_preimage(feedback: PublicTypedRejectionFeedback) -> bytes:
    return canonical_bytes(feedback.model_dump(mode="json", exclude={"feedback_id"}))


__all__ = [
    "ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION",
    "HostTypedRejectionBinding",
    "MAX_CORRECTION_ATTEMPTS",
    "PROHIBITED_PUBLIC_FEEDBACK_KEYS",
    "PUBLIC_ACTION_ID_PATTERN",
    "PUBLIC_FEEDBACK_FIELDS",
    "PublicCorrectionBoundTerminal",
    "PublicTypedRejectionFeedback",
    "PublicTypedRejectionObservation",
    "make_host_typed_rejection_binding",
    "make_public_correction_bound_terminal",
    "make_public_typed_rejection_feedback",
    "make_public_typed_rejection_observation",
    "prompt_with_public_typed_rejection_history",
    "public_feedback_identity_preimage",
    "strict_public_feedback_findings",
]
