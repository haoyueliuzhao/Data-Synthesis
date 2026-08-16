from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.trajectory.scaffolding import SCAFFOLD_LEVELS
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_bridge import (
    BRIDGE_MECHANISMS,
    MECHANISM_ESTIMANDS,
    STATIC_CONSTRUCT_CHECKS,
    BridgeMechanism,
    authorize_bridge_confirmation,
    authorize_bridge_development,
    confirm_compiler_assisted_bridge,
    default_compiler_assisted_bridge_contract,
    freeze_compiler_assisted_bridge_support,
    make_bridge_cell_observation,
    make_bridge_estimand_observation,
    make_bridge_static_construct_audit,
)


def _development_task_ids(mechanism: BridgeMechanism) -> tuple[str, ...]:
    index = BRIDGE_MECHANISMS.index(mechanism)
    return tuple(f"development:{index}:{item}" for item in range(8))


def _confirmation_task_ids(mechanism: BridgeMechanism) -> tuple[str, ...]:
    index = BRIDGE_MECHANISMS.index(mechanism)
    return tuple(f"confirmation:{index}:{item}" for item in range(8))


def _static_audit(
    contract_id: str,
    mechanism: BridgeMechanism,
    *,
    phase: str = "development",
    fail: bool = False,
):
    task_ids = (
        _development_task_ids(mechanism)
        if phase == "development"
        else _confirmation_task_ids(mechanism)
    )
    checks = {
        task_id: {
            check: not (fail and task_index == 0 and check == "construct_fidelity_exact")
            for check in STATIC_CONSTRUCT_CHECKS
        }
        for task_index, task_id in enumerate(task_ids)
    }
    return make_bridge_static_construct_audit(
        contract_id=contract_id,
        mechanism_id=mechanism,
        task_admission_ids={task_id: f"admission:{task_id}" for task_id in task_ids},
        checks_by_task=checks,
    )


def _authorization(contract, *, failed_mechanism: BridgeMechanism | None = None):
    return authorize_bridge_development(
        contract,
        tuple(
            _static_audit(
                contract.contract_id,
                mechanism,
                fail=mechanism == failed_mechanism,
            )
            for mechanism in BRIDGE_MECHANISMS
        ),
    )


def _estimands(mechanism: BridgeMechanism, rank: int):
    rows = []
    for estimand_id in MECHANISM_ESTIMANDS[mechanism]:
        evaluation_count = 24 if estimand_id == "counterfactual_branch_flip" else 48
        success_by_rank = (3, 10, 12, 14) if evaluation_count == 24 else (6, 20, 24, 28)
        baseline = 2 if evaluation_count == 24 else 4
        rows.append(
            make_bridge_estimand_observation(
                estimand_id=estimand_id,
                evaluation_count=evaluation_count,
                success_count=success_by_rank[rank],
                fixed_policy_success_count=baseline,
            )
        )
    return tuple(rows)


def _cell(
    contract_id: str,
    authorization_id: str,
    mechanism: BridgeMechanism,
    level: str,
    *,
    phase: str = "development",
    **updates: Any,
):
    rank = SCAFFOLD_LEVELS.index(level)  # type: ignore[arg-type]
    if phase == "development":
        task_ids = _development_task_ids(mechanism)
    else:
        index = BRIDGE_MECHANISMS.index(mechanism)
        task_ids = tuple(f"confirmation:{index}:{item}" for item in range(8))
    values = {
        "contract_id": contract_id,
        "phase_authorization_id": authorization_id,
        "phase": phase,
        "mechanism_id": mechanism,
        "scaffold_level": level,
        "scaffold_rank": rank,
        "task_ids": task_ids,
        "compiled_task_condition_ids": tuple(
            f"condition:{task_id}:{level}" for task_id in task_ids
        ),
        "state_mapping_contract_ids": tuple(f"mapping:{task_id}" for task_id in task_ids),
        "instrument_valid_rollout_count": 48,
        "model_outcome_count": 48,
        "valid_trajectory_count": (4, 20, 24, 28)[rank],
        "estimand_observations": _estimands(mechanism, rank),
        "preliminary_unique_state_count": 1,
        "tasks_with_multiple_observed_states_count": 1,
        "state_entropy": 0.2 + rank / 10,
        "host_interference_count": 0,
        "oracle_leakage_count": 0,
        "runtime_failure_count": 0,
    }
    values.update(updates)
    return make_bridge_cell_observation(**values)


def _development_observations(contract, authorization):
    return tuple(
        _cell(
            contract.contract_id,
            authorization.authorization_id,
            mechanism,
            level,
        )
        for mechanism in BRIDGE_MECHANISMS
        for level in SCAFFOLD_LEVELS
    )


def _passing_freeze():
    contract = default_compiler_assisted_bridge_contract()
    authorization = _authorization(contract)
    freeze = freeze_compiler_assisted_bridge_support(
        contract,
        authorization,
        _development_observations(contract, authorization),
    )
    return contract, authorization, freeze


def _confirmation_authorization(contract, freeze, *, failed_mechanism=None):
    return authorize_bridge_confirmation(
        contract,
        freeze,
        tuple(
            _static_audit(
                contract.contract_id,
                mechanism,
                phase="fresh_confirmation",
                fail=mechanism == failed_mechanism,
            )
            for mechanism in BRIDGE_MECHANISMS
        ),
    )


def test_bridge_contract_separates_boundary_support_and_transfer() -> None:
    contract = default_compiler_assisted_bridge_contract()

    assert contract.planned_development_rollout_count == 576
    assert contract.planned_confirmation_rollout_count == 144
    assert tuple(
        tuple(item.estimand_id for item in mechanism.estimands) for mechanism in contract.mechanisms
    ) == tuple(MECHANISM_ESTIMANDS[item] for item in BRIDGE_MECHANISMS)
    assert contract.estimand_compression_forbidden
    assert contract.development_state_diversity_diagnostic_only
    assert contract.development_three_state_gate_forbidden
    assert contract.support_discovery_separate_from_bridge
    assert contract.withdrawal_readiness_is_static_gate
    assert contract.withdrawal_transfer.empirical_only_after_student_training
    assert contract.experiment_separation.bridge_experiment_is_not_vtdo_distribution_comparison
    assert not contract.api_authorized_before_static_construct_audit


def test_static_construct_failure_blocks_before_model_calls() -> None:
    contract = default_compiler_assisted_bridge_contract()
    authorization = _authorization(contract, failed_mechanism="semantic_reconciliation")

    assert authorization.status == "blocked"
    assert authorization.blockers == ("semantic_reconciliation",)
    assert authorization.next_transition == "bridge_static_construct_repair_only"
    assert authorization.model_api_calls == 0
    assert authorization.gpu_jobs == 0


def test_bridge_selects_minimum_boundary_level_without_three_state_gate() -> None:
    contract, _, freeze = _passing_freeze()

    assert freeze.status == "passed"
    assert freeze.next_transition == "fresh_bridge_confirmation"
    assert tuple(item.selected_scaffold_level for item in freeze.selections) == (
        "gamma_1",
        "gamma_1",
        "gamma_1",
    )
    assert all(item.preliminary_unique_state_count == 1 for item in freeze.observations)
    assert not freeze.three_state_support_evaluated
    assert not freeze.vtdo_authorized
    assert contract.support_selected_per_mechanism_not_task


def test_bridge_cell_rejects_missing_mechanism_estimand() -> None:
    contract = default_compiler_assisted_bridge_contract()
    authorization = _authorization(contract)
    observations = _estimands("recovery_and_stopping", 1)

    with pytest.raises(ValidationError, match="Estimands are incomplete"):
        _cell(
            contract.contract_id,
            authorization.authorization_id,
            "recovery_and_stopping",
            "gamma_1",
            estimand_observations=observations[:1],
        )


def test_bridge_support_rejects_per_task_scaffold_selection() -> None:
    contract = default_compiler_assisted_bridge_contract()
    authorization = _authorization(contract)
    rows = list(_development_observations(contract, authorization))
    target = next(
        index
        for index, item in enumerate(rows)
        if item.mechanism_id == "semantic_reconciliation" and item.scaffold_level == "gamma_2"
    )
    rows[target] = _cell(
        contract.contract_id,
        authorization.authorization_id,
        "semantic_reconciliation",
        "gamma_2",
        task_ids=tuple(f"replacement:{index}" for index in range(8)),
        compiled_task_condition_ids=tuple(f"replacement-condition:{index}" for index in range(8)),
        state_mapping_contract_ids=tuple(f"replacement-mapping:{index}" for index in range(8)),
    )

    with pytest.raises(ValueError, match="same tasks within a mechanism"):
        freeze_compiler_assisted_bridge_support(contract, authorization, rows)


def test_bridge_support_rejects_cross_level_state_mapping_drift() -> None:
    contract = default_compiler_assisted_bridge_contract()
    authorization = _authorization(contract)
    rows = list(_development_observations(contract, authorization))
    target = next(
        index
        for index, item in enumerate(rows)
        if item.mechanism_id == "semantic_reconciliation" and item.scaffold_level == "gamma_2"
    )
    rows[target] = _cell(
        contract.contract_id,
        authorization.authorization_id,
        "semantic_reconciliation",
        "gamma_2",
        state_mapping_contract_ids=tuple(f"drifted-mapping:{index}" for index in range(8)),
    )

    with pytest.raises(ValueError, match="changed the state mapping contract"):
        freeze_compiler_assisted_bridge_support(contract, authorization, rows)


def test_bridge_cell_requires_complete_rollout_accounting() -> None:
    contract = default_compiler_assisted_bridge_contract()
    authorization = _authorization(contract)

    with pytest.raises(ValidationError, match="rollout accounting is incomplete"):
        _cell(
            contract.contract_id,
            authorization.authorization_id,
            "context_conditioned_action",
            "gamma_1",
            model_outcome_count=47,
            runtime_failure_count=0,
        )


def test_fresh_confirmation_authorizes_only_state_support_discovery() -> None:
    contract, _, freeze = _passing_freeze()
    authorization = _confirmation_authorization(contract, freeze)
    observations = tuple(
        _cell(
            contract.contract_id,
            authorization.authorization_id,
            mechanism,
            "gamma_1",
            phase="fresh_confirmation",
        )
        for mechanism in BRIDGE_MECHANISMS
    )
    confirmation = confirm_compiler_assisted_bridge(
        contract,
        freeze,
        authorization,
        observations,
    )

    assert confirmation.status == "passed"
    assert confirmation.next_transition == "state_support_discovery"
    assert len(confirmation.confirmed_task_conditions) == 24
    assert not confirmation.state_support_evaluated
    assert not confirmation.vtdo_authorized


def test_fresh_confirmation_rejects_development_task_reuse() -> None:
    contract, _, freeze = _passing_freeze()
    audits = tuple(
        _static_audit(
            contract.contract_id,
            mechanism,
            phase=(
                "development" if mechanism == "context_conditioned_action" else "fresh_confirmation"
            ),
        )
        for mechanism in BRIDGE_MECHANISMS
    )

    with pytest.raises(ValidationError, match="reuses Development tasks"):
        authorize_bridge_confirmation(contract, freeze, audits)


def test_failed_confirmation_static_audit_blocks_before_model_calls() -> None:
    contract, _, freeze = _passing_freeze()
    authorization = _confirmation_authorization(
        contract,
        freeze,
        failed_mechanism="recovery_and_stopping",
    )

    assert authorization.status == "blocked"
    assert authorization.blockers == ("recovery_and_stopping",)
    assert authorization.next_transition == "bridge_confirmation_static_repair_only"
    assert authorization.model_api_calls == 0
    assert authorization.gpu_jobs == 0
