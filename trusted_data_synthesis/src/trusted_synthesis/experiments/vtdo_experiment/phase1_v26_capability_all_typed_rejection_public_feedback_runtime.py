from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from trusted_synthesis.core.task.all_typed_rejection_public_feedback import (
    PUBLIC_ACTION_ID_PATTERN,
    HostTypedRejectionBinding,
    PublicCorrectionBoundTerminal,
    PublicTypedRejectionFeedback,
    PublicTypedRejectionObservation,
    make_host_typed_rejection_binding,
    make_public_correction_bound_terminal,
    make_public_typed_rejection_feedback,
    make_public_typed_rejection_observation,
    prompt_with_public_typed_rejection_history,
)
from trusted_synthesis.core.task.state_local_presentation_hardening import (
    HardenedPublicObservation,
    HardenedPublicPrompt,
    StateLocalRankSchedule,
    StepRuntimeResult,
    classify_action_acceptance,
    make_state_local_prompt,
    resolve_runtime_operation,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_joint_presentation_receipt_hardening_runtime as v174_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_state_local_presentation_runtime as v175_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_runtime as v171_runtime,
)


class CorrectionBoundTerminalReached(ValueError):
    pass


class InitialActionReferenceRejected(ValueError):
    pass


@dataclass
class StepRuntimeState(v175_runtime.StepRuntimeState):
    public_feedback_by_component: dict[str, list[PublicTypedRejectionFeedback]] = field(
        default_factory=dict
    )
    public_rejection_observations_by_component: dict[
        str,
        list[PublicTypedRejectionObservation],
    ] = field(default_factory=dict)
    host_rejection_bindings_by_component: dict[
        str,
        list[HostTypedRejectionBinding],
    ] = field(default_factory=dict)
    seen_public_action_ids: set[str] = field(default_factory=set)
    current_public_action_ids: set[str] = field(default_factory=set)
    correction_terminal: PublicCorrectionBoundTerminal | None = None


def initialize(
    runtime_input: v171_runtime.RuntimeInput,
    *,
    package_id: str,
    replica_index: int,
    schedules_by_component: Mapping[str, StateLocalRankSchedule],
) -> StepRuntimeState:
    base = v175_runtime.initialize(
        runtime_input,
        package_id=package_id,
        replica_index=replica_index,
        schedules_by_component=schedules_by_component,
    )
    return StepRuntimeState(**base.__dict__)


def render_next_prompt(state: StepRuntimeState) -> HardenedPublicPrompt:
    if state.correction_terminal is not None:
        raise CorrectionBoundTerminalReached("bounded-correction terminal forbids a later Prompt")
    if state.current_index >= len(state.ordered_components):
        raise ValueError("all-typed-rejection Runtime has no later Prompt")
    if state.pending_prompt is not None:
        return state.pending_prompt
    v174_runtime._prepare_current_recovery_failure(state)
    component = state.ordered_components[state.current_index]
    predecessor = tuple(state.observations[key] for key in component.dependency_component_keys)
    prompt, mapping = make_state_local_prompt(
        package_id=state.package_id,
        task=state.runtime_input.public_task,
        component=component,
        replica_index=state.replica_index,
        predecessor_observations=predecessor,
        failure_receipt=state.failure_receipts.get(component.component_key),
        schedule=state.schedules_by_component[component.component_key],
    )
    feedback = tuple(state.public_feedback_by_component.get(component.component_key, ()))
    prompt = prompt_with_public_typed_rejection_history(prompt, feedback)
    state.pending_prompt = prompt
    state.pending_source_by_display = mapping
    state.current_public_action_ids = {item.action_id for item in prompt.candidates}
    state.seen_public_action_ids.update(state.current_public_action_ids)
    return prompt


def _absent_action_class(
    state: StepRuntimeState,
    selected_action_id: str,
) -> Literal[
    "stale_action_id",
    "foreign_or_unbound_action_id",
    "malformed_action_reference",
]:
    prior_action_ids = state.seen_public_action_ids - state.current_public_action_ids
    if selected_action_id in prior_action_ids:
        return "stale_action_id"
    if re.fullmatch(PUBLIC_ACTION_ID_PATTERN, selected_action_id) is not None:
        return "foreign_or_unbound_action_id"
    return "malformed_action_reference"


def _terminal_for_absent_second_response(
    *,
    state: StepRuntimeState,
    prompt: HardenedPublicPrompt,
    selected_action_id: str,
    first_feedback: PublicTypedRejectionFeedback,
) -> PublicCorrectionBoundTerminal:
    terminal = make_public_correction_bound_terminal(
        public_state_token=prompt.state.state_token,
        first_public_feedback_id=first_feedback.feedback_id,
        second_public_feedback_id=None,
        second_public_action_reference=selected_action_id,
        second_response_class=_absent_action_class(state, selected_action_id),
    )
    state.correction_terminal = terminal
    state.pending_prompt = None
    state.pending_source_by_display = None
    return terminal


def step(
    state: StepRuntimeState,
    selected_action_id: str,
) -> HardenedPublicObservation | PublicTypedRejectionObservation | PublicCorrectionBoundTerminal:
    prompt = render_next_prompt(state)
    component = state.ordered_components[state.current_index]
    existing_feedback = state.public_feedback_by_component.get(component.component_key, [])
    selected = tuple(item for item in prompt.candidates if item.action_id == selected_action_id)
    if len(selected) != 1:
        if existing_feedback:
            return _terminal_for_absent_second_response(
                state=state,
                prompt=prompt,
                selected_action_id=selected_action_id,
                first_feedback=existing_feedback[0],
            )
        raise InitialActionReferenceRejected(
            "initial Action reference is absent from the current public Prompt"
        )

    mapping = state.pending_source_by_display
    if mapping is None:
        raise ValueError("all-typed-rejection Runtime lost its display/source binding")
    displayed = selected[0].choice_handle
    source_handle = mapping[displayed]
    operation = resolve_runtime_operation(prompt.state, displayed)
    source_operation = v171_runtime.choice_operation(component.public_state, source_handle)
    if operation.model_dump(mode="json") != source_operation.model_dump(mode="json"):
        raise ValueError("all-typed-rejection Runtime crosses its exact source Operation")
    acceptance = classify_action_acceptance(
        package_id=state.package_id,
        task=state.runtime_input.public_task,
        component=component,
        source_choice_handle=source_handle,
        visible_failure_receipt=prompt.state.failure_receipt,
        expected_failure_receipt=state.failure_receipts.get(component.component_key),
    )
    if acceptance.accepted:
        return v175_runtime.step(state, selected_action_id)

    correction_attempt_index = len(existing_feedback) + 1
    event_start = len(state.events)
    v174_runtime._append_event(
        state,
        component_key=component.component_key,
        event_type="action_state_precondition_rejected",
        tool_id=operation.tool_id,
        status="typed",
        error_code=None,
        inputs=operation.model_dump(mode="json"),
        outputs={"action_committed": False},
        public_effects={
            "public_rejection_code": acceptance.rejection_code,
            "public_correction_attempt_index": correction_attempt_index,
        },
    )
    runtime_event_ids = tuple(item.event_id for item in state.events[event_start:])
    if not runtime_event_ids:
        raise ValueError("typed rejection did not persist its Host Runtime event")
    if acceptance.rejection_code is None:
        raise ValueError("typed rejection is missing its production rejection code")
    public_observation = make_public_typed_rejection_observation(
        prompt=prompt,
        public_rejected_action_id=selected_action_id,
        public_displayed_choice_handle=displayed,
        public_rejection_code=acceptance.rejection_code,
        correction_attempt_index=correction_attempt_index,
    )
    public_feedback = make_public_typed_rejection_feedback(
        observation=public_observation,
        predecessor_public_feedback_id=(
            existing_feedback[-1].feedback_id if existing_feedback else None
        ),
    )
    host_binding = make_host_typed_rejection_binding(
        package_id=state.package_id,
        component_key=component.component_key,
        source_choice_handle=source_handle,
        acceptance=acceptance,
        runtime_event_ids=runtime_event_ids,
        observation=public_observation,
        feedback=public_feedback,
    )
    state.public_feedback_by_component.setdefault(component.component_key, []).append(
        public_feedback
    )
    state.public_rejection_observations_by_component.setdefault(
        component.component_key,
        [],
    ).append(public_observation)
    state.host_rejection_bindings_by_component.setdefault(component.component_key, []).append(
        host_binding
    )
    state.pending_prompt = None
    state.pending_source_by_display = None

    if correction_attempt_index > 1:
        response_class: Literal["same_current_invalid", "different_current_invalid"] = (
            "same_current_invalid"
            if selected_action_id == existing_feedback[0].public_rejected_action_id
            else "different_current_invalid"
        )
        terminal = make_public_correction_bound_terminal(
            public_state_token=prompt.state.state_token,
            first_public_feedback_id=existing_feedback[0].feedback_id,
            second_public_feedback_id=public_feedback.feedback_id,
            second_public_action_reference=selected_action_id,
            second_response_class=response_class,
        )
        state.correction_terminal = terminal
        return terminal
    return public_observation


def finalize(state: StepRuntimeState) -> StepRuntimeResult:
    if state.correction_terminal is not None:
        raise CorrectionBoundTerminalReached(
            "bounded-correction terminal cannot finalize as a completed Package"
        )
    return v175_runtime.finalize(state)


__all__ = [
    "CorrectionBoundTerminalReached",
    "InitialActionReferenceRejected",
    "StepRuntimeState",
    "finalize",
    "initialize",
    "render_next_prompt",
    "step",
]
