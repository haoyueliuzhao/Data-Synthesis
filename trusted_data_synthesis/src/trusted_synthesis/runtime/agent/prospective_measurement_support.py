from __future__ import annotations

from typing import Any, cast

from trusted_synthesis.core.measurement.support import (
    BaselineActionSetResolution,
    MeasurementSupportDecision,
    SupportEventKind,
    classify_measurement_support,
    make_baseline_resolution,
    make_measurement_support_event,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    CanonicalPublicAction,
    SemanticActionState,
)


def public_progress_vector(state: SemanticActionState) -> tuple[Any, ...]:
    return (
        state.unresolved_symbols,
        tuple((item.node_id, item.frontier_status) for item in state.operation_frontier),
        state.terminal_operation_ref,
        state.terminal_verification_completed,
        state.final_answer_allowed,
    )


def public_progress_vector_id(state: SemanticActionState) -> str:
    return canonical_hash(
        public_progress_vector(state),
        prefix="prospective_public_progress_vector:",
    )


def _acquisition_baseline(state: SemanticActionState) -> tuple[CanonicalPublicAction, ...]:
    symbol = state.unresolved_symbols[0]
    candidates = tuple(
        item
        for item in state.action_candidates
        if item.decision_kind == "acquire_public_input" and item.target_source_symbols == (symbol,)
    )
    successful_modes = {
        item.acquisition_mode
        for item in state.acquisition_history
        if item.status == "succeeded" and item.target_source_symbols == (symbol,)
    }
    return tuple(item for item in candidates if item.acquisition_mode not in successful_modes)


def _operation_baseline(state: SemanticActionState) -> tuple[CanonicalPublicAction, ...]:
    candidates = tuple(
        item for item in state.action_candidates if item.decision_kind == "execute_public_operation"
    )
    if not candidates:
        return ()
    first_node_id = min(str(item.node_id) for item in candidates)
    same_node = tuple(item for item in candidates if item.node_id == first_node_id)
    frontier = next(
        (
            item
            for item in state.operation_frontier
            if item.node_id == first_node_id and item.frontier_status == "executable"
        ),
        None,
    )
    if frontier is None or frontier.required_output_schema is None:
        return same_node
    schema_matched = tuple(
        item
        for item in same_node
        if frontier.operator_output_schemas.get(str(item.operator_id))
        == frontier.required_output_schema
    )
    return schema_matched or same_node


def _verification_baseline(state: SemanticActionState) -> tuple[CanonicalPublicAction, ...]:
    candidates = tuple(
        item
        for item in state.action_candidates
        if item.decision_kind == "verify_terminal_operation"
    )
    if not candidates:
        return ()
    maximum_support = max(len(item.evidence_reference_ids) for item in candidates)
    return tuple(item for item in candidates if len(item.evidence_reference_ids) == maximum_support)


def _public_baseline_actions(state: SemanticActionState) -> tuple[CanonicalPublicAction, ...]:
    if state.unresolved_symbols:
        return _acquisition_baseline(state)
    operation = _operation_baseline(state)
    if operation:
        return operation
    verification = _verification_baseline(state)
    if verification:
        return verification
    return tuple(
        item for item in state.action_candidates if item.decision_kind == "emit_final_answer"
    )


def resolve_public_baseline_action_set(
    state: SemanticActionState,
) -> BaselineActionSetResolution:
    """Return a total, public-state-only baseline resolution without choosing an action."""

    actions = _public_baseline_actions(state)
    progress_id = public_progress_vector_id(state)
    if actions:
        return make_baseline_resolution(
            status="available",
            public_state_id=state.state_id,
            progress_vector_id=progress_id,
            baseline_action_ids=tuple(item.action_id for item in actions),
        )
    reason = (
        "no_untried_public_acquisition_for_first_unresolved_symbol"
        if state.unresolved_symbols
        else "no_progress_directed_public_baseline_action"
    )
    return make_baseline_resolution(
        status="unavailable",
        public_state_id=state.state_id,
        progress_vector_id=progress_id,
        reason_code=reason,
    )


def classify_public_observation_support(
    *,
    state_before: SemanticActionState,
    state_after: SemanticActionState,
    selected_action_id: str,
    observation_status: str,
) -> MeasurementSupportDecision:
    if observation_status not in {"succeeded", "failed"}:
        raise ValueError("public Observation status is outside the frozen support ABI")
    event = make_measurement_support_event(
        event_kind="public_observation",
        public_state_id_before=state_before.state_id,
        public_state_id_after=state_after.state_id,
        progress_vector_id_before=public_progress_vector_id(state_before),
        progress_vector_id_after=public_progress_vector_id(state_after),
        selected_action_id=selected_action_id,
        observation_status=cast(Any, observation_status),
    )
    return classify_measurement_support(
        event,
        baseline_resolver=lambda: resolve_public_baseline_action_set(state_before),
    )


def classify_non_observation_support(
    *,
    event_kind: str,
    state: SemanticActionState,
    state_after: SemanticActionState | None = None,
    selected_action_id: str | None,
) -> MeasurementSupportDecision:
    if event_kind not in {"terminal_verification", "final_commit", "non_public_commit"}:
        raise ValueError("non-Observation support event kind changed")
    after = state_after or state
    progress_id = public_progress_vector_id(state)
    event = make_measurement_support_event(
        event_kind=cast(SupportEventKind, event_kind),
        public_state_id_before=state.state_id,
        public_state_id_after=after.state_id,
        progress_vector_id_before=progress_id,
        progress_vector_id_after=public_progress_vector_id(after),
        selected_action_id=selected_action_id,
        observation_status=None,
    )
    return classify_measurement_support(
        event,
        baseline_resolver=lambda: resolve_public_baseline_action_set(state),
    )
