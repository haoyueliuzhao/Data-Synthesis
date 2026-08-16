from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.trajectory.scaffolding import SCAFFOLD_LEVELS
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_bridge import (
    BRIDGE_MECHANISMS,
    BridgeMechanism,
    default_compiler_assisted_bridge_contract,
    freeze_compiler_assisted_bridge_support,
    make_bridge_cell_observation,
)


def _cell(
    contract_id: str,
    mechanism: BridgeMechanism,
    level: str,
    **updates: Any,
):
    mechanism_index = BRIDGE_MECHANISMS.index(mechanism)
    task_ids = tuple(f"task:{mechanism_index}:{index}" for index in range(8))
    rank = SCAFFOLD_LEVELS.index(level)  # type: ignore[arg-type]
    success_by_rank = (4, 20, 24, 28)
    values = {
        "contract_id": contract_id,
        "mechanism_id": mechanism,
        "scaffold_level": level,
        "scaffold_rank": rank,
        "task_ids": task_ids,
        "instrument_valid_rollout_count": 48,
        "model_outcome_count": 48,
        "target_success_count": success_by_rank[rank],
        "valid_trajectory_count": 20 + rank,
        "fixed_policy_success_count": 8,
        "tasks_with_three_reachable_states_count": 6,
        "reachable_state_count": 24 + rank,
        "state_entropy": 1.1 + rank / 10,
        "counterfactual_evaluation_count": 48,
        "counterfactual_faithful_count": 48,
        "host_interference_count": 0,
        "oracle_leakage_count": 0,
        "runtime_failure_count": 0,
    }
    values.update(updates)
    return make_bridge_cell_observation(**values)


def _complete_observations(contract_id: str):
    return tuple(
        _cell(contract_id, mechanism, level)
        for mechanism in BRIDGE_MECHANISMS
        for level in SCAFFOLD_LEVELS
    )


def test_bridge_contract_freezes_budget_identity_and_withdrawal_matrix() -> None:
    contract = default_compiler_assisted_bridge_contract()

    assert contract.development_task_count == 24
    assert contract.scaffold_levels == SCAFFOLD_LEVELS
    assert contract.planned_development_rollout_count == 576
    assert contract.planned_confirmation_rollout_count == 144
    assert contract.support_selected_per_mechanism_not_task
    assert not contract.api_authorized_before_scaffold_admission
    assert not contract.gpu_authorized_before_support_freeze
    assert contract.withdrawal.conditions == (
        "unassisted_train_unassisted_eval",
        "scaffold_train_scaffold_eval",
        "scaffold_train_unassisted_eval",
        "scaffold_train_weaker_scaffold_eval",
    )


def test_bridge_support_selects_the_minimum_level_per_mechanism() -> None:
    contract = default_compiler_assisted_bridge_contract()
    freeze = freeze_compiler_assisted_bridge_support(
        contract,
        _complete_observations(contract.contract_id),
    )

    assert freeze.status == "passed"
    assert freeze.next_transition == "fresh_bridge_confirmation"
    assert tuple(item.selected_scaffold_level for item in freeze.selections) == (
        "gamma_1",
        "gamma_1",
        "gamma_1",
    )
    assert not freeze.task_reallocation_used
    assert not freeze.inverse_success_weighting_used
    assert not freeze.per_task_scaffold_selection_used


def test_bridge_support_rejects_per_task_scaffold_selection() -> None:
    contract = default_compiler_assisted_bridge_contract()
    rows = list(_complete_observations(contract.contract_id))
    target = next(
        index
        for index, item in enumerate(rows)
        if item.mechanism_id == "semantic_reconciliation" and item.scaffold_level == "gamma_2"
    )
    rows[target] = _cell(
        contract.contract_id,
        "semantic_reconciliation",
        "gamma_2",
        task_ids=tuple(f"replacement:{index}" for index in range(8)),
    )

    with pytest.raises(ValueError, match="same tasks within a mechanism"):
        freeze_compiler_assisted_bridge_support(contract, rows)


def test_bridge_support_blocks_when_no_level_reaches_valid_state_support() -> None:
    contract = default_compiler_assisted_bridge_contract()
    rows = [
        (
            _cell(
                contract.contract_id,
                item.mechanism_id,
                item.scaffold_level,
                tasks_with_three_reachable_states_count=1,
            )
            if item.mechanism_id == "recovery_and_stopping"
            else item
        )
        for item in _complete_observations(contract.contract_id)
    ]
    freeze = freeze_compiler_assisted_bridge_support(contract, rows)

    assert freeze.status == "blocked"
    assert freeze.blockers == ("recovery_and_stopping",)
    assert freeze.next_transition == "capability_task_or_scaffold_redesign_only"
    failed = freeze.selections[-1]
    assert all(
        "reachable_state_support_low" in failed.failure_reasons_by_level[level]
        for level in SCAFFOLD_LEVELS
    )


def test_bridge_cell_requires_complete_rollout_accounting() -> None:
    contract = default_compiler_assisted_bridge_contract()

    with pytest.raises(ValidationError, match="rollout accounting is incomplete"):
        _cell(
            contract.contract_id,
            "context_conditioned_action",
            "gamma_1",
            model_outcome_count=47,
            runtime_failure_count=0,
        )
