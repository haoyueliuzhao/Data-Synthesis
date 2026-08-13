from __future__ import annotations

from types import SimpleNamespace

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_confirmation import (
    CONFIRMATION_GROUPS_PER_MECHANISM,
    CONFIRMATION_REPLICAS,
    CONFIRMATION_TIER_SCHEDULE,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_flash_development import (  # noqa: E501
    _selection_decisions,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_ir import (
    MECHANISM_IDS,
)


def test_confirmation_schedule_is_five_fresh_groups_with_bridge_support() -> None:
    assert CONFIRMATION_GROUPS_PER_MECHANISM == 5
    assert CONFIRMATION_REPLICAS == 5
    assert CONFIRMATION_TIER_SCHEDULE == (
        "bridge",
        "bridge",
        "frontier",
        "frontier",
        "frontier",
    )


def test_selection_fails_closed_without_mechanism_specific_behavior() -> None:
    mechanism_id = MECHANISM_IDS[2]
    behaviors = []
    task_group_ids: dict[str, str] = {}
    task_mechanism_ids: dict[str, str] = {}
    task_mechanism_tiers: dict[str, str] = {}
    for group_index in range(4):
        group_id = f"group-{group_index}"
        for role in ("resolved_control", "mechanism_required"):
            task_id = f"task-{group_index}-{role}"
            task_group_ids[task_id] = group_id
            task_mechanism_ids[task_id] = mechanism_id
            task_mechanism_tiers[task_id] = "bridge"
            for replicate in range(3):
                mechanism_valid = group_index >= 2 or replicate < 2
                behaviors.append(
                    SimpleNamespace(
                        mechanism_id=mechanism_id,
                        mechanism_tier="bridge",
                        variant_role=role,
                        group_id=group_id,
                        runtime_eligible=True,
                        valid_success=(
                            True if role == "resolved_control" else mechanism_valid
                        ),
                        mechanism_evaluable=True,
                        mechanism_success=(role == "resolved_control"),
                    )
                )
    contract = SimpleNamespace(
        task_group_ids=task_group_ids,
        task_mechanism_ids=task_mechanism_ids,
        task_mechanism_tiers=task_mechanism_tiers,
    )

    decisions = _selection_decisions(contract, behaviors, runtime_passed=True)
    decision = next(item for item in decisions if item.mechanism_id == mechanism_id)

    assert decision.bridge_or_frontier_matched_difference_group_count == 2
    assert decision.bridge_or_frontier_boundary_group_count == 2
    assert decision.bridge_or_frontier_mechanism_behavior_success_count == 0
    assert not decision.matched_behavior_detected
    assert not decision.selected_for_confirmation
    assert "mechanism_specific_behavior_not_observed" in decision.reasons
