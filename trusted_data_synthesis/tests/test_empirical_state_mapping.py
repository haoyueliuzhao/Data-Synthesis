from __future__ import annotations

from typing import Any

import pytest

from trusted_synthesis.core.evaluation.trajectory_validity import (
    QualifiedTrajectoryValidityReport,
)
from trusted_synthesis.core.evaluation.valid_only_state_mapping import (
    make_valid_only_state_mapper_contract,
)
from trusted_synthesis.core.trajectory.empirical_state_mapping import (
    PublicTrajectoryAction,
    make_empirical_route_projection,
    make_public_trajectory_projection,
    map_independently_valid_public_trajectory_to_state,
)
from trusted_synthesis.hashing import canonical_hash


def _qualified_report(*, valid: bool | None = True) -> QualifiedTrajectoryValidityReport:
    values: dict[str, Any] = {
        "verifier_contract_id": "verifier-contract",
        "trajectory_id": "trajectory-1",
        "eligibility_id": "eligibility-1",
        "base_report_id": "base-report-1",
        "mechanism_report_id": "mechanism-report-1",
        "valid": valid,
        "state_mapping_eligible": valid is True,
    }
    provisional = QualifiedTrajectoryValidityReport.model_construct(
        report_id="pending",
        **values,
    )
    return QualifiedTrajectoryValidityReport(
        report_id=canonical_hash(
            provisional.model_dump(mode="json", exclude={"report_id"}),
            prefix="prospective_qualified_trajectory_validity_report:",
        ),
        **values,
    )


def _contract():
    return make_valid_only_state_mapper_contract(
        qualified_verifier_contract_id="verifier-contract",
        mapper_implementation_id="empirical-mapper",
        mapper_version="empirical.v1",
    )


def _actions(runtime_ref: str, *, reverse_acquisition: bool = False):
    acquisitions = [
        PublicTrajectoryAction(
            action_index=0,
            decision_kind="acquire_public_input",
            action_kind="call_tool",
            tool_id="query_structured_fact",
            arguments={"subject": "A"},
            observation_status="succeeded",
            observation_result={"evidence_ids": ["evidence:a"]},
            evidence_ids=("evidence:a",),
        ),
        PublicTrajectoryAction(
            action_index=1,
            decision_kind="acquire_public_input",
            action_kind="call_tool",
            tool_id="query_structured_fact",
            arguments={"subject": "B"},
            observation_status="succeeded",
            observation_result={"evidence_ids": ["evidence:b"]},
            evidence_ids=("evidence:b",),
        ),
    ]
    if reverse_acquisition:
        acquisitions.reverse()
        acquisitions = [
            item.model_copy(update={"action_index": index})
            for index, item in enumerate(acquisitions)
        ]
    return (
        *acquisitions,
        PublicTrajectoryAction(
            action_index=2,
            decision_kind="execute_public_operation",
            action_kind="call_tool",
            tool_id="calculator",
            arguments={
                "operands": [{"operation_ref": runtime_ref}],
                "evidence_ids": ["evidence:a", "evidence:b"],
            },
            observation_status="succeeded",
            observation_result={
                "result": {
                    "operation_ref": runtime_ref,
                    "output": {"value": "1.0"},
                }
            },
            evidence_ids=("evidence:a", "evidence:b"),
        ),
        PublicTrajectoryAction(
            action_index=3,
            decision_kind="emit_final_answer",
            action_kind="emit_final",
        ),
    )


def _map(*, runtime_ref: str, reverse_acquisition: bool = False):
    trajectory = make_public_trajectory_projection(
        trajectory_id="trajectory-1",
        terminal_disposition="completed_model_endpoint",
        actions=_actions(runtime_ref, reverse_acquisition=reverse_acquisition),
        final_result={"operation_ref": runtime_ref, "value": "1.0"},
        final_citations=("evidence:a", "evidence:b"),
    )
    route = make_empirical_route_projection(
        sampling_mode="reachability_unconditional",
        public_condition_id="unconditional",
        requested_path_id=None,
        requested_path_strategy=None,
        static_path_catalog_id="path-catalog",
        trajectory=trajectory,
    )
    return (
        trajectory,
        map_independently_valid_public_trajectory_to_state(
            trajectory=trajectory,
            qualified_validity_report=_qualified_report(),
            mapper_contract=_contract(),
            omega_task_context_id="omega-context",
            route_projection=route,
            runtime_operation_aliases={runtime_ref: "program-node:operation-1"},
        ),
    )


def test_empirical_mapper_binds_all_required_assignment_parents() -> None:
    trajectory, assignment = _map(runtime_ref="runtime-operation:a")

    assert assignment.trajectory_content_hash == trajectory.trajectory_content_hash
    assert assignment.qualified_validity_report_id == _qualified_report().report_id
    assert assignment.omega_task_context_id == "omega-context"
    assert assignment.structural_state_id == assignment.structural_state.state_id
    assert assignment.route_condition_id == assignment.route_projection.projection_id
    assert assignment.static_path_catalog_id == "path-catalog"
    assert assignment.raw_observation_prefix_hash == trajectory.raw_observation_prefix_hash
    assert assignment.static_path_used_as_empirical_state is False


def test_runtime_alias_and_independent_action_order_do_not_split_state() -> None:
    left_trajectory, left = _map(runtime_ref="runtime-operation:a")
    alias_trajectory, alias = _map(runtime_ref="runtime-operation:b")
    order_trajectory, order = _map(
        runtime_ref="runtime-operation:a",
        reverse_acquisition=True,
    )

    assert (
        len(
            {
                left_trajectory.trajectory_content_hash,
                alias_trajectory.trajectory_content_hash,
                order_trajectory.trajectory_content_hash,
            }
        )
        == 3
    )
    assert left.structural_state_id == alias.structural_state_id
    assert left.structural_state_id == order.structural_state_id
    assert left.route_condition_id == order.route_condition_id
    assert left.assignment_id != order.assignment_id


@pytest.mark.parametrize("valid", [False, None])
def test_empirical_mapper_rejects_nonqualified_trajectory(valid: bool | None) -> None:
    trajectory = make_public_trajectory_projection(
        trajectory_id="trajectory-1",
        terminal_disposition="completed_model_endpoint",
        actions=_actions("runtime-operation:a"),
        final_result={"value": "1.0"},
    )
    route = make_empirical_route_projection(
        sampling_mode="reachability_unconditional",
        public_condition_id="unconditional",
        requested_path_id=None,
        requested_path_strategy=None,
        static_path_catalog_id="path-catalog",
        trajectory=trajectory,
    )

    with pytest.raises(ValueError, match="non-Qualified trajectory"):
        map_independently_valid_public_trajectory_to_state(
            trajectory=trajectory,
            qualified_validity_report=_qualified_report(valid=valid),
            mapper_contract=_contract(),
            omega_task_context_id="omega-context",
            route_projection=route,
            runtime_operation_aliases={"runtime-operation:a": "program-node:operation-1"},
        )


def test_static_path_condition_is_separate_from_structural_state() -> None:
    trajectory, first = _map(runtime_ref="runtime-operation:a")
    alternate_route = make_empirical_route_projection(
        sampling_mode="reachability_conditioned",
        public_condition_id="condition-2",
        requested_path_id="path-2",
        requested_path_strategy="search_then_open",
        static_path_catalog_id="path-catalog",
        trajectory=trajectory,
    )
    second = map_independently_valid_public_trajectory_to_state(
        trajectory=trajectory,
        qualified_validity_report=_qualified_report(),
        mapper_contract=_contract(),
        omega_task_context_id="omega-context",
        route_projection=alternate_route,
        runtime_operation_aliases={"runtime-operation:a": "program-node:operation-1"},
    )

    assert first.route_condition_id != second.route_condition_id
    assert first.structural_state_id == second.structural_state_id


def test_rejection_content_addresses_do_not_split_structural_state() -> None:
    common = {
        "error_category": "unknown_or_unselectable_action",
        "failed_decision_kind": "acquire_public_input",
        "violated_public_constraint": "action_id_must_be_in_visible_candidate_set",
        "semantic_recovery_available": True,
        "job_terminal": False,
        "unresolved_public_symbols": ["symbol-b", "symbol-a"],
    }
    trajectories = tuple(
        make_public_trajectory_projection(
            trajectory_id="trajectory-1",
            terminal_disposition="completed_model_endpoint",
            actions=_actions("runtime-operation:a"),
            semantic_rejections=(
                {
                    **common,
                    "proposal_id": f"proposal:{suffix}",
                    "rejection_id": f"rejection:{suffix}",
                    "state_id": f"state:{suffix}",
                    "selected_action_id": f"action:{suffix}",
                },
            ),
            final_result={"value": "1.0"},
        )
        for suffix in ("left", "right")
    )
    assignments = []
    for trajectory in trajectories:
        route = make_empirical_route_projection(
            sampling_mode="reachability_unconditional",
            public_condition_id="unconditional",
            requested_path_id=None,
            requested_path_strategy=None,
            static_path_catalog_id="path-catalog",
            trajectory=trajectory,
        )
        assignments.append(
            map_independently_valid_public_trajectory_to_state(
                trajectory=trajectory,
                qualified_validity_report=_qualified_report(),
                mapper_contract=_contract(),
                omega_task_context_id="omega-context",
                route_projection=route,
                runtime_operation_aliases={"runtime-operation:a": "program-node:operation-1"},
            )
        )

    assert trajectories[0].trajectory_content_hash != trajectories[1].trajectory_content_hash
    assert assignments[0].structural_state_id == assignments[1].structural_state_id
