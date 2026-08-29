from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from trusted_synthesis.core.task.authoritative_rejection_history_hardening import (
    MAX_CORRECTED_RESPONSE_ATTEMPTS,
    TypedRejectionFeedback,
    make_typed_rejection_feedback,
    prompt_with_typed_rejection_history,
)
from trusted_synthesis.core.task.state_local_presentation_hardening import (
    ActionAcceptanceReport,
    HardenedPublicObservation,
    HardenedPublicPrompt,
    StateLocalRankSchedule,
    StepRuntimeResult,
    classify_action_acceptance,
    make_hardened_observation,
    make_identity_model,
    make_state_local_prompt,
    resolve_runtime_operation,
)
from trusted_synthesis.core.task.validity_separated_capability_depth import (
    CausalRuntimeEvent,
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


class TypedRejectionRecoveryExhausted(ValueError):
    pass


@dataclass
class StepRuntimeState(v175_runtime.StepRuntimeState):
    rejection_feedback_by_component: dict[str, list[TypedRejectionFeedback]] = field(
        default_factory=dict
    )
    rejection_observations_by_component: dict[
        str,
        list[HardenedPublicObservation],
    ] = field(default_factory=dict)
    rejection_acceptances_by_component: dict[str, list[ActionAcceptanceReport]] = field(
        default_factory=dict
    )
    recovery_exhausted_component_key: str | None = None
    recovery_terminal_feedback_id: str | None = None


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
    if state.recovery_exhausted_component_key is not None:
        raise TypedRejectionRecoveryExhausted(
            "typed-rejection corrected-response allowance is exhausted"
        )
    if state.current_index >= len(state.ordered_components):
        raise ValueError("rejection-history Runtime has no later Prompt")
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
    feedback = tuple(state.rejection_feedback_by_component.get(component.component_key, ()))
    prompt = prompt_with_typed_rejection_history(prompt, feedback)
    state.pending_prompt = prompt
    state.pending_source_by_display = mapping
    return prompt


def _feedback_observation(
    *,
    prompt: HardenedPublicPrompt,
    selected_action_id: str,
    selected_choice_handle: str,
    predecessor_receipt_ids: tuple[str, ...],
    acceptance: ActionAcceptanceReport,
    events: tuple[CausalRuntimeEvent, ...],
    corrected_response_attempt_index: int,
    recovery_exhausted: bool,
) -> HardenedPublicObservation:
    base = make_hardened_observation(
        prompt=prompt,
        selected_choice_handle=selected_choice_handle,
        predecessor_receipt_ids=predecessor_receipt_ids,
        acceptance=acceptance,
        events=events,
    )
    values = base.model_dump(mode="python", exclude={"receipt_id"})
    public_effects = dict(values["public_effects"])
    public_effects.update(
        {
            "rejected_action_id": selected_action_id,
            "action_acceptance_report_id": acceptance.report_id,
            "corrected_response_attempt_index": corrected_response_attempt_index,
            "corrected_response_attempt_bound": MAX_CORRECTED_RESPONSE_ATTEMPTS,
            "recovery_exhausted": recovery_exhausted,
        }
    )
    values["public_effects"] = public_effects
    return cast(
        HardenedPublicObservation,
        make_identity_model(
            HardenedPublicObservation,
            values,
            field="receipt_id",
            prefix="hardened_public_observation_receipt:",
        ),
    )


def step(state: StepRuntimeState, selected_action_id: str) -> HardenedPublicObservation:
    prompt = render_next_prompt(state)
    component = state.ordered_components[state.current_index]
    selected = tuple(item for item in prompt.candidates if item.action_id == selected_action_id)
    if len(selected) != 1:
        raise ValueError("rejection-history Runtime action is absent from the current Prompt")
    mapping = state.pending_source_by_display
    if mapping is None:
        raise ValueError("rejection-history Runtime lost its display/source binding")
    displayed = selected[0].choice_handle
    source_handle = mapping[displayed]
    operation = resolve_runtime_operation(prompt.state, displayed)
    source_operation = v171_runtime.choice_operation(component.public_state, source_handle)
    if operation.model_dump(mode="json") != source_operation.model_dump(mode="json"):
        raise ValueError("rejection-history Runtime crosses its exact source Operation")
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

    existing_feedback = state.rejection_feedback_by_component.get(component.component_key, [])
    corrected_response_attempt_index = len(existing_feedback) + 1
    recovery_exhausted = len(existing_feedback) >= MAX_CORRECTED_RESPONSE_ATTEMPTS
    prepared_failure_event = state.failure_events.get(component.component_key)
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
            "rejection_code": acceptance.rejection_code,
            "selected_operation_hash": acceptance.selected_operation_hash,
            "failure_receipt_id": acceptance.failure_receipt_id,
            "corrected_response_attempt_index": corrected_response_attempt_index,
            "recovery_exhausted": recovery_exhausted,
        },
    )
    current_events = (
        (prepared_failure_event,) if prepared_failure_event is not None else ()
    ) + tuple(state.events[event_start:])
    predecessor = tuple(state.observations[key] for key in component.dependency_component_keys)
    observation = _feedback_observation(
        prompt=prompt,
        selected_action_id=selected_action_id,
        selected_choice_handle=displayed,
        predecessor_receipt_ids=tuple(item.receipt_id for item in predecessor),
        acceptance=acceptance,
        events=current_events,
        corrected_response_attempt_index=corrected_response_attempt_index,
        recovery_exhausted=recovery_exhausted,
    )
    feedback = make_typed_rejection_feedback(
        component_key=component.component_key,
        rejected_action_id=selected_action_id,
        observation=observation,
        acceptance=acceptance,
        predecessor_feedback_id=(existing_feedback[-1].feedback_id if existing_feedback else None),
        corrected_response_attempt_index=corrected_response_attempt_index,
    )
    state.rejection_feedback_by_component.setdefault(component.component_key, []).append(feedback)
    state.rejection_observations_by_component.setdefault(component.component_key, []).append(
        observation
    )
    state.rejection_acceptances_by_component.setdefault(component.component_key, []).append(
        acceptance
    )
    if recovery_exhausted:
        state.recovery_exhausted_component_key = component.component_key
        state.recovery_terminal_feedback_id = feedback.feedback_id
    state.pending_prompt = None
    state.pending_source_by_display = None
    return observation


def finalize(state: StepRuntimeState) -> StepRuntimeResult:
    if state.recovery_exhausted_component_key is not None:
        raise TypedRejectionRecoveryExhausted(
            "typed-rejection terminal cannot be finalized as a completed Package"
        )
    return v175_runtime.finalize(state)


__all__ = [
    "StepRuntimeState",
    "TypedRejectionRecoveryExhausted",
    "finalize",
    "initialize",
    "render_next_prompt",
    "step",
]
