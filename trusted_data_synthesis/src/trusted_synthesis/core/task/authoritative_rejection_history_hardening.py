from __future__ import annotations

import hashlib
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.joint_presentation_receipt_hardening import (
    HardenedPublicState,
)
from trusted_synthesis.core.task.public_semantic_capability_depth import canonical_bytes
from trusted_synthesis.core.task.state_local_presentation_hardening import (
    ActionAcceptanceReport,
    HardenedPublicObservation,
    HardenedPublicPrompt,
    make_identity_model,
)
from trusted_synthesis.hashing import canonical_hash

AUTHORITATIVE_REJECTION_HISTORY_VERSION: Final = (
    "authoritative_parent_rejection_history_hardening.v1"
)
MAX_CORRECTED_RESPONSE_ATTEMPTS: Final = 1


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


class TypedRejectionFeedback(FrozenModel):
    feedback_id: str = Field(min_length=1)
    component_key: str = Field(min_length=1)
    rejected_action_id: str = Field(min_length=1)
    rejected_choice_handle: str = Field(min_length=1)
    selected_operation_hash: str = Field(min_length=1)
    rejection_code: str = Field(min_length=1)
    observation_receipt_id: str = Field(min_length=1)
    action_acceptance_report_id: str = Field(min_length=1)
    predecessor_feedback_id: str | None = None
    corrected_response_attempt_index: int = Field(ge=1)
    corrected_response_attempt_bound: Literal[1] = MAX_CORRECTED_RESPONSE_ATTEMPTS
    action_committed: Literal[False] = False
    model_visible: Literal[True] = True
    schema_version: str = AUTHORITATIVE_REJECTION_HISTORY_VERSION

    @model_validator(mode="after")
    def validate_feedback(self) -> TypedRejectionFeedback:
        if self.corrected_response_attempt_index > self.corrected_response_attempt_bound + 1:
            raise ValueError("typed-rejection feedback exceeds its registered attempt surface")
        if self.feedback_id != _identity(
            self,
            "feedback_id",
            "typed_rejection_feedback:",
        ):
            raise ValueError("typed-rejection feedback identity is invalid")
        return self


def make_typed_rejection_feedback(
    *,
    component_key: str,
    rejected_action_id: str,
    observation: HardenedPublicObservation,
    acceptance: ActionAcceptanceReport,
    predecessor_feedback_id: str | None,
    corrected_response_attempt_index: int,
) -> TypedRejectionFeedback:
    if observation.action_accepted or acceptance.accepted:
        raise ValueError("typed-rejection feedback cannot parent an accepted Action")
    if observation.rejection_code is None or acceptance.rejection_code is None:
        raise ValueError("typed-rejection feedback is missing its rejection code")
    if (
        observation.rejection_code != acceptance.rejection_code
        or observation.selected_operation_hash != acceptance.selected_operation_hash
    ):
        raise ValueError("typed-rejection feedback crosses Observation/Acceptance semantics")
    values = {
        "component_key": component_key,
        "rejected_action_id": rejected_action_id,
        "rejected_choice_handle": observation.selected_choice_handle,
        "selected_operation_hash": observation.selected_operation_hash,
        "rejection_code": observation.rejection_code,
        "observation_receipt_id": observation.receipt_id,
        "action_acceptance_report_id": acceptance.report_id,
        "predecessor_feedback_id": predecessor_feedback_id,
        "corrected_response_attempt_index": corrected_response_attempt_index,
    }
    return cast(
        TypedRejectionFeedback,
        make_identity_model(
            TypedRejectionFeedback,
            values,
            field="feedback_id",
            prefix="typed_rejection_feedback:",
        ),
    )


def prompt_with_typed_rejection_history(
    prompt: HardenedPublicPrompt,
    feedback: tuple[TypedRejectionFeedback, ...],
) -> HardenedPublicPrompt:
    if not feedback:
        return prompt
    component_keys = {item.component_key for item in feedback}
    if len(component_keys) != 1:
        raise ValueError("one recovery Prompt cannot cross target Components")
    if tuple(item.corrected_response_attempt_index for item in feedback) != tuple(
        range(1, len(feedback) + 1)
    ):
        raise ValueError("typed-rejection feedback attempts are not contiguous")
    for index, item in enumerate(feedback):
        expected_parent = feedback[index - 1].feedback_id if index else None
        if item.predecessor_feedback_id != expected_parent:
            raise ValueError("typed-rejection feedback chain is not parent-contiguous")

    facts: dict[str, Any] = dict(prompt.state.facts)
    facts["current_action_feedback"] = tuple(item.model_dump(mode="json") for item in feedback)
    facts["corrected_response_attempt_index"] = len(feedback)
    facts["corrected_response_attempt_bound"] = MAX_CORRECTED_RESPONSE_ATTEMPTS
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


__all__ = [
    "AUTHORITATIVE_REJECTION_HISTORY_VERSION",
    "MAX_CORRECTED_RESPONSE_ATTEMPTS",
    "TypedRejectionFeedback",
    "make_typed_rejection_feedback",
    "prompt_with_typed_rejection_history",
]
