from __future__ import annotations

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.trajectory.scaffolding import SCAFFOLD_LEVELS
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_bridge import (
    BRIDGE_MECHANISMS,
    MECHANISM_ESTIMANDS,
    STATIC_CONSTRUCT_CHECKS,
    authorize_bridge_confirmation,
    authorize_bridge_development,
    confirm_compiler_assisted_bridge,
    default_compiler_assisted_bridge_contract,
    freeze_compiler_assisted_bridge_support,
    make_bridge_cell_observation,
    make_bridge_estimand_observation,
    make_bridge_static_construct_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_state_support import (
    freeze_state_support_discovery,
    make_state_acceptance_estimate,
    make_state_support_discovery_contract,
    make_task_state_support_observation,
)


def _estimands(mechanism, rank: int):
    return tuple(
        make_bridge_estimand_observation(
            estimand_id=estimand_id,
            evaluation_count=(24 if estimand_id == "counterfactual_branch_flip" else 48),
            success_count=(
                (3, 10, 12, 14) if estimand_id == "counterfactual_branch_flip" else (6, 20, 24, 28)
            )[rank],
            fixed_policy_success_count=(2 if estimand_id == "counterfactual_branch_flip" else 4),
        )
        for estimand_id in MECHANISM_ESTIMANDS[mechanism]
    )


def _bridge_cell(contract, authorization, mechanism, level, phase):
    rank = SCAFFOLD_LEVELS.index(level)
    mechanism_index = BRIDGE_MECHANISMS.index(mechanism)
    task_ids = tuple(f"{phase}:{mechanism_index}:{index}" for index in range(8))
    return make_bridge_cell_observation(
        contract_id=contract.contract_id,
        phase_authorization_id=authorization.authorization_id,
        phase=phase,
        mechanism_id=mechanism,
        scaffold_level=level,
        scaffold_rank=rank,
        task_ids=task_ids,
        compiled_task_condition_ids=tuple(f"condition:{task_id}:{level}" for task_id in task_ids),
        state_mapping_contract_ids=tuple(f"mapping:{task_id}" for task_id in task_ids),
        instrument_valid_rollout_count=48,
        model_outcome_count=48,
        valid_trajectory_count=(4, 20, 24, 28)[rank],
        estimand_observations=_estimands(mechanism, rank),
        preliminary_unique_state_count=2,
        tasks_with_multiple_observed_states_count=2,
        state_entropy=0.4,
        host_interference_count=0,
        oracle_leakage_count=0,
        runtime_failure_count=0,
    )


def _confirmation():
    contract = default_compiler_assisted_bridge_contract()
    audits = []
    for mechanism_index, mechanism in enumerate(BRIDGE_MECHANISMS):
        task_ids = tuple(f"development:{mechanism_index}:{index}" for index in range(8))
        checks = {
            task_id: {check: True for check in STATIC_CONSTRUCT_CHECKS} for task_id in task_ids
        }
        audits.append(
            make_bridge_static_construct_audit(
                contract_id=contract.contract_id,
                mechanism_id=mechanism,
                task_admission_ids={task_id: f"admission:{task_id}" for task_id in task_ids},
                checks_by_task=checks,
            )
        )
    authorization = authorize_bridge_development(contract, audits)
    development = tuple(
        _bridge_cell(contract, authorization, mechanism, level, "development")
        for mechanism in BRIDGE_MECHANISMS
        for level in SCAFFOLD_LEVELS
    )
    freeze = freeze_compiler_assisted_bridge_support(
        contract,
        authorization,
        development,
    )
    confirmation_audits = []
    for mechanism_index, mechanism in enumerate(BRIDGE_MECHANISMS):
        task_ids = tuple(f"fresh_confirmation:{mechanism_index}:{index}" for index in range(8))
        checks = {
            task_id: {check: True for check in STATIC_CONSTRUCT_CHECKS} for task_id in task_ids
        }
        confirmation_audits.append(
            make_bridge_static_construct_audit(
                contract_id=contract.contract_id,
                mechanism_id=mechanism,
                task_admission_ids={task_id: f"admission:{task_id}" for task_id in task_ids},
                checks_by_task=checks,
            )
        )
    confirmation_authorization = authorize_bridge_confirmation(
        contract,
        freeze,
        confirmation_audits,
    )
    confirmation_rows = tuple(
        _bridge_cell(
            contract,
            confirmation_authorization,
            mechanism,
            "gamma_1",
            "fresh_confirmation",
        )
        for mechanism in BRIDGE_MECHANISMS
    )
    return contract, confirm_compiler_assisted_bridge(
        contract,
        freeze,
        confirmation_authorization,
        confirmation_rows,
    )


def _state_estimates(task_id: str, count: int = 3):
    return tuple(
        make_state_acceptance_estimate(
            quotient_state_id=f"state:{task_id}:{index}",
            unconditional_rollout_count=18,
            unconditional_hit_count=5,
            conditioned_attempt_count=12,
            conditioned_accepted_count=10,
            independently_verified=True,
        )
        for index in range(count)
    )


def _observation(contract, condition, *, state_count: int = 3):
    return make_task_state_support_observation(
        contract,
        condition,
        unconditional_valid_trajectory_count=15,
        state_estimates=_state_estimates(condition.task_id, state_count),
        scaffold_invariant_mapping_replayed=True,
        scaffold_trace_side_channel_archived=True,
    )


def test_state_support_contract_is_separate_and_freezes_18_rollouts() -> None:
    bridge_contract, confirmation = _confirmation()
    contract = make_state_support_discovery_contract(bridge_contract, confirmation)

    assert contract.task_count == 24
    assert contract.confirmation_rollouts_per_task == 6
    assert contract.additional_unconditional_rollouts_per_task == 12
    assert contract.total_unconditional_rollouts_per_task == 18
    assert contract.planned_additional_unconditional_rollout_count == 288
    assert contract.minimum_accepted_state_count == 3
    assert contract.maximum_accepted_state_count == 5
    assert contract.state_quota_transfer_forbidden
    assert contract.bridge_boundary_result_not_state_support_proof


def test_state_support_freeze_requires_state_level_acceptance_and_budget() -> None:
    bridge_contract, confirmation = _confirmation()
    contract = make_state_support_discovery_contract(bridge_contract, confirmation)
    observations = tuple(
        _observation(contract, condition) for condition in contract.confirmed_task_conditions
    )
    freeze = freeze_state_support_discovery(contract, observations)

    assert freeze.status == "passed"
    assert freeze.next_transition == "frozen_condition_no_c_population_compilation"
    assert freeze.no_c_vtdo_support_compilation_authorized
    assert not freeze.contribution_authorized
    assert not freeze.scaffold_condition_changed_across_vtdo_arms
    assert all(
        estimate.unconditional_hit_rate_lcb95 > 0
        and estimate.conditioned_acceptance_rate_lcb95 > 0
        and estimate.estimated_attempts_for_quota <= 60
        for observation in freeze.observations
        for estimate in observation.state_estimates
    )


def test_two_observed_states_block_support_but_not_bridge_confirmation() -> None:
    bridge_contract, confirmation = _confirmation()
    assert confirmation.status == "passed"
    contract = make_state_support_discovery_contract(bridge_contract, confirmation)
    target = contract.confirmed_task_conditions[0]
    observations = tuple(
        _observation(
            contract,
            condition,
            state_count=(2 if condition.task_id == target.task_id else 3),
        )
        for condition in contract.confirmed_task_conditions
    )
    freeze = freeze_state_support_discovery(contract, observations)

    assert freeze.status == "blocked"
    assert freeze.blocker_task_ids == (target.task_id,)
    assert not freeze.no_c_vtdo_support_compilation_authorized


def test_zero_state_acceptance_blocks_materialization_feasibility() -> None:
    bridge_contract, confirmation = _confirmation()
    contract = make_state_support_discovery_contract(bridge_contract, confirmation)
    condition = contract.confirmed_task_conditions[0]
    failed = make_state_acceptance_estimate(
        quotient_state_id=f"state:{condition.task_id}:failed",
        unconditional_rollout_count=18,
        unconditional_hit_count=1,
        conditioned_attempt_count=6,
        conditioned_accepted_count=0,
        independently_verified=True,
    )
    estimates = (failed, *_state_estimates(condition.task_id, 2))
    observation = make_task_state_support_observation(
        contract,
        condition,
        unconditional_valid_trajectory_count=11,
        state_estimates=estimates,
        scaffold_invariant_mapping_replayed=True,
        scaffold_trace_side_channel_archived=True,
    )

    assert observation.status == "blocked"
    assert "state_level_acceptance_or_budget_failed" in observation.blockers
    assert failed.conditioned_acceptance_rate_lcb95 == 0
    assert failed.estimated_attempts_for_quota > 60


def test_state_support_rejects_quota_transfer() -> None:
    bridge_contract, confirmation = _confirmation()
    contract = make_state_support_discovery_contract(bridge_contract, confirmation)
    condition = contract.confirmed_task_conditions[0]
    observation = _observation(contract, condition)

    with pytest.raises(ValidationError):
        observation.model_copy(update={"quota_transfer_used": True}, deep=True).__class__(
            **{
                **observation.model_dump(),
                "quota_transfer_used": True,
            }
        )


def test_state_support_rejects_changed_frozen_condition() -> None:
    bridge_contract, confirmation = _confirmation()
    contract = make_state_support_discovery_contract(bridge_contract, confirmation)
    observations = [
        _observation(contract, condition) for condition in contract.confirmed_task_conditions
    ]
    observations[0] = observations[0].model_copy(
        update={"compiled_task_condition_id": "changed-condition"}
    )

    with pytest.raises(ValueError, match="changes the frozen task condition"):
        freeze_state_support_discovery(contract, observations)
