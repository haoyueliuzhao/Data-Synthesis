from __future__ import annotations

from test_empirical_state_mapping_v2 import _base_actions, _map, _policy

from trusted_synthesis.core.trajectory.empirical_state_mapping_v2 import (
    TypedActionReferencesV2,
    make_public_trajectory_projection_v2,
)
from trusted_synthesis.core.trajectory.reference_empirical_state_mapping_v2 import (
    reference_map_public_trajectory_v2,
)


def test_independent_reference_mapper_matches_production_without_calling_it() -> None:
    policy = _policy()
    trajectory, assignment = _map(
        actions=_base_actions(policy, reverse_acquisitions=True),
        raw_final_result={"difference": 0.224},
        canonical_result={"difference": "0.224"},
        trajectory_id="trajectory-reference-control",
    )

    reference = reference_map_public_trajectory_v2(
        trajectory=trajectory,
        omega_task_context_id="omega-context",
        runtime_operation_aliases={"runtime:result": "operation:result"},
        semantic_policy=policy,
    )

    assert reference.production_mapper_called is False
    assert reference.structural_state == assignment.structural_state
    assert reference.structural_state.state_id == assignment.structural_state_id


def test_reference_mapper_reextracts_typed_references_from_raw_tool_fields() -> None:
    policy = _policy()
    trajectory, _ = _map(
        actions=_base_actions(policy),
        raw_final_result={"difference": 0.224},
        canonical_result={"difference": "0.224"},
        trajectory_id="trajectory-reference-reextract",
    )
    first_action = trajectory.actions[0].model_copy(
        update={"typed_references": TypedActionReferencesV2()}
    )
    altered = make_public_trajectory_projection_v2(
        trajectory_id="trajectory-reference-reextract-altered",
        terminal_disposition=trajectory.terminal_disposition,
        actions=(first_action, *trajectory.actions[1:]),
        semantic_rejections=trajectory.semantic_rejections,
        raw_final_result=trajectory.raw_final_result,
        canonical_result=trajectory.canonical_result,
        answer_semantic_schema_id=trajectory.answer_semantic_schema_id,
        reference_projection_policy_id=trajectory.reference_projection_policy_id,
        final_citations=trajectory.final_citations,
    )

    reference = reference_map_public_trajectory_v2(
        trajectory=altered,
        omega_task_context_id="omega-context",
        runtime_operation_aliases={"runtime:result": "operation:result"},
        semantic_policy=policy,
    )

    evidence_references = {
        item.normalized_reference
        for item in reference.structural_state.reference_classes
        if item.reference_kind == "evidence"
    }
    assert "evidence:a" in evidence_references
