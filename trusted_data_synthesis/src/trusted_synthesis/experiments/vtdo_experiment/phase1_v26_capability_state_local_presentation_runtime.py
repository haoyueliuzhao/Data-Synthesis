from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from trusted_synthesis.core.task.state_local_presentation_hardening import (
    HardenedPublicObservation,
    HardenedPublicPrompt,
    StateLocalRankSchedule,
    StepRuntimeResult,
    classify_action_acceptance,
    make_hardened_observation,
    make_state_local_prompt,
    resolve_runtime_operation,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_joint_presentation_receipt_hardening_runtime as v174_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_runtime as v171_runtime,
)


@dataclass
class StepRuntimeState(v174_runtime.StepRuntimeState):
    schedules_by_component: dict[str, StateLocalRankSchedule] = field(default_factory=dict)


def initialize(
    runtime_input: v171_runtime.RuntimeInput,
    *,
    package_id: str,
    replica_index: int,
    schedules_by_component: Mapping[str, StateLocalRankSchedule],
) -> StepRuntimeState:
    base = v174_runtime.initialize(
        runtime_input,
        package_id=package_id,
        replica_index=replica_index,
    )
    schedules = dict(schedules_by_component)
    expected = {item.component_key for item in base.ordered_components}
    if set(schedules) != expected:
        raise ValueError("state-local Runtime Schedule denominator differs from Components")
    if any(schedule.component_key != key for key, schedule in schedules.items()):
        raise ValueError("state-local Runtime crosses a Component Schedule")
    return StepRuntimeState(**base.__dict__, schedules_by_component=schedules)


def render_next_prompt(state: StepRuntimeState) -> HardenedPublicPrompt:
    if state.current_index >= len(state.ordered_components):
        raise ValueError("state-local step Runtime has no later Prompt")
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
    state.pending_prompt = prompt
    state.pending_source_by_display = mapping
    return prompt


def step(state: StepRuntimeState, selected_action_id: str) -> HardenedPublicObservation:
    prompt = render_next_prompt(state)
    component = state.ordered_components[state.current_index]
    selected = tuple(item for item in prompt.candidates if item.action_id == selected_action_id)
    if len(selected) != 1:
        raise ValueError("state-local step Runtime action is absent from the current Prompt")
    mapping = state.pending_source_by_display
    if mapping is None:
        raise ValueError("state-local step Runtime lost its display/source binding")
    displayed = selected[0].choice_handle
    source_handle = mapping[displayed]
    operation = resolve_runtime_operation(prompt.state, displayed)
    source_operation = v171_runtime.choice_operation(component.public_state, source_handle)
    if operation.model_dump(mode="json") != source_operation.model_dump(mode="json"):
        raise ValueError("state-local step Runtime crosses its exact source Operation")
    acceptance = classify_action_acceptance(
        package_id=state.package_id,
        task=state.runtime_input.public_task,
        component=component,
        source_choice_handle=source_handle,
        visible_failure_receipt=prompt.state.failure_receipt,
        expected_failure_receipt=state.failure_receipts.get(component.component_key),
    )
    if acceptance.accepted:
        return v174_runtime.step(state, selected_action_id)

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
        },
    )
    current_events = (
        (prepared_failure_event,) if prepared_failure_event is not None else ()
    ) + tuple(state.events[event_start:])
    predecessor = tuple(state.observations[key] for key in component.dependency_component_keys)
    observation = make_hardened_observation(
        prompt=prompt,
        selected_choice_handle=displayed,
        predecessor_receipt_ids=tuple(item.receipt_id for item in predecessor),
        acceptance=acceptance,
        events=current_events,
    )
    # A typed precondition rejection is a non-committing recovery-channel outcome.
    # The same target Component remains current and no Retry operation is invoked.
    state.pending_prompt = None
    state.pending_source_by_display = None
    return observation


def finalize(state: StepRuntimeState) -> StepRuntimeResult:
    return v174_runtime.finalize(state)


__all__ = [
    "StepRuntimeState",
    "finalize",
    "initialize",
    "render_next_prompt",
    "step",
]
