from __future__ import annotations

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.audit_artifacts import make_atomic_audit_case_result
from trusted_synthesis.core.trajectory.scaffolding import (
    SCAFFOLD_LEVELS,
    CompiledTaskConditionLineage,
    compile_public_state_summary,
    compiled_task_condition_lineage_id,
    make_minimal_public_state_summary_spec,
    make_public_state_observation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_bridge import (
    BRIDGE_MECHANISMS,
    MECHANISM_ESTIMANDS,
    STATIC_CONSTRUCT_CHECKS,
    BridgeEstimandOutcome,
    BridgeMechanism,
    aggregate_bridge_cell_observation,
    authorize_bridge_confirmation,
    authorize_bridge_development,
    confirm_compiler_assisted_bridge,
    default_compiler_assisted_bridge_contract,
    freeze_compiler_assisted_bridge_support,
    make_bridge_execution_manifest,
    make_bridge_rollout_observation,
    make_bridge_static_construct_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_state_support import (
    freeze_state_support_discovery,
    make_state_acceptance_estimate,
    make_state_support_discovery_contract,
    make_task_state_support_observation,
)


def _static_audit(contract_id: str, mechanism: BridgeMechanism, phase: str):
    mechanism_index = BRIDGE_MECHANISMS.index(mechanism)
    task_ids = tuple(f"{phase}:{mechanism_index}:{index}" for index in range(8))
    task_admission_ids = {task_id: f"admission:{task_id}" for task_id in task_ids}
    auditor_id = f"state_support_test.{phase}.{mechanism}"
    auditor_version = "1.0.0"
    return make_bridge_static_construct_audit(
        contract_id=contract_id,
        mechanism_id=mechanism,
        task_admission_ids=task_admission_ids,
        case_results=tuple(
            make_atomic_audit_case_result(
                check_id=check_id,
                subject_id=task_admission_ids[task_id],
                input_artifact_ids=(contract_id, task_admission_ids[task_id]),
                output_artifact_ids=(f"bridge-audit:{task_id}:{check_id}",),
                implementation_manifest={
                    "auditor_id": auditor_id,
                    "auditor_version": auditor_version,
                    "check_id": check_id,
                },
                replay_implementation_manifest={
                    "auditor_id": f"{auditor_id}.independent",
                    "auditor_version": auditor_version,
                    "check_id": check_id,
                },
                check_passed=True,
            )
            for task_id in task_ids
            for check_id in STATIC_CONSTRUCT_CHECKS
        ),
        auditor_id=auditor_id,
        auditor_version=auditor_version,
    )


def _summary(task_id: str):
    spec = make_minimal_public_state_summary_spec(
        compiler_id="state_support_test.summary",
        compiler_version="1.0.0",
        source_kinds=("task_public",),
        included_fields=("remaining_tool_budget",),
    )
    return compile_public_state_summary(
        spec,
        (
            make_public_state_observation(
                task_id=task_id,
                sequence_index=0,
                source_kind="task_public",
                values={"remaining_tool_budget": 4},
            ),
        ),
    )


def _lineage(task_id: str, level: str, summary):
    values = {
        "task_id": task_id,
        "compiled_task_condition_id": f"condition:{task_id}:{level}",
        "projection_id": f"projection:{task_id}:{level}",
        "ladder_id": f"ladder:{task_id}",
        "scaffold_admission_id": f"scaffold-admission:{task_id}",
        "joint_admission_id": f"joint-admission:{task_id}",
        "joint_compilation_id": f"joint:{task_id}",
        "omega_context_id": f"omega:{task_id}",
        "omega_component_manifest_id": f"omega-manifest:{task_id}",
        "runtime_projection_id": f"runtime-projection:{task_id}",
        "runtime_authority_policy_id": "runtime-policy:autonomous",
        "dependency_graph_id": f"dependency-graph:{task_id}",
        "public_summary_spec_id": summary.summary_spec.summary_spec_id if summary else None,
        "state_mapping_contract_id": f"mapping:{task_id}",
        "scaffold_payload_hash": f"scaffold-payload:{task_id}:{level}",
        "scaffold_level": level,
        "schema_version": "compiled_task_condition_lineage.v1",
    }
    provisional = CompiledTaskConditionLineage.model_construct(
        lineage_id="pending",
        **values,
    )
    return CompiledTaskConditionLineage(
        lineage_id=compiled_task_condition_lineage_id(provisional),
        **values,
    )


def _execution_manifest(contract_id: str, lineage: CompiledTaskConditionLineage):
    return make_bridge_execution_manifest(
        contract_id=contract_id,
        condition_lineage=lineage,
        model_id="deepseek-v4-flash",
        model_config={"temperature": 0.2, "top_p": 0.95},
        provider_route={"provider": "test", "route_id": "openai-compatible"},
        prompt_manifest={"template_id": "state-support-test.v1"},
        runtime_id="autonomous",
        tool_manifest={"allowed_tools": ["evidence_lookup"]},
    )


def _bridge_cell(contract, authorization, mechanism, level, phase):
    rank = SCAFFOLD_LEVELS.index(level)
    mechanism_index = BRIDGE_MECHANISMS.index(mechanism)
    task_ids = tuple(f"{phase}:{mechanism_index}:{index}" for index in range(8))
    summaries = {task_id: (_summary(task_id) if rank >= 1 else None) for task_id in task_ids}
    lineages = {task_id: _lineage(task_id, level, summaries[task_id]) for task_id in task_ids}
    success_replicates = (1, 3, 4, 5)[rank]
    fixed_policy_success_replicates = 1
    rollouts = []
    for task_index, task_id in enumerate(task_ids):
        for replicate_index in range(6):
            global_index = task_index * 6 + replicate_index
            outcomes = []
            for estimand_id in MECHANISM_ESTIMANDS[mechanism]:
                outcomes.append(
                    BridgeEstimandOutcome(
                        estimand_id=estimand_id,
                        evaluated=True,
                        success=replicate_index < success_replicates,
                        fixed_policy_success=(replicate_index < fixed_policy_success_replicates),
                    )
                )
            terminal = (
                "model_valid_trajectory"
                if replicate_index < success_replicates
                else "model_invalid_trajectory"
            )
            rollouts.append(
                make_bridge_rollout_observation(
                    contract_id=contract.contract_id,
                    phase_authorization_id=authorization.authorization_id,
                    phase=phase,
                    mechanism_id=mechanism,
                    scaffold_level=level,
                    replicate_index=replicate_index,
                    condition_lineage=lineages[task_id],
                    execution_manifest=_execution_manifest(contract.contract_id, lineages[task_id]),
                    provider_call_ids=(
                        f"call:{phase}:{mechanism}:{level}:{task_id}:{replicate_index}",
                    ),
                    public_state_summary=summaries[task_id],
                    terminal_category=terminal,
                    independent_validity_passed=terminal == "model_valid_trajectory",
                    quotient_state_id=f"state:{replicate_index % 2}",
                    decision_trace_hash=f"trajectory_decision_trace:{global_index + 1:064x}",
                    estimand_outcomes=tuple(outcomes),
                    raw_payload={
                        "task_id": task_id,
                        "replicate_index": replicate_index,
                        "terminal_category": terminal,
                        "failure_attribution": (
                            None
                            if terminal == "model_valid_trajectory"
                            else "model_invalid_trajectory"
                        ),
                    },
                    raw_artifact_uri=f"embedded://state-support/{task_id}/{replicate_index}",
                )
            )
    return aggregate_bridge_cell_observation(
        contract_id=contract.contract_id,
        phase_authorization_id=authorization.authorization_id,
        phase=phase,
        mechanism_id=mechanism,
        scaffold_level=level,
        rollout_observations=rollouts,
    )


def _confirmation():
    contract = default_compiler_assisted_bridge_contract()
    audits = [
        _static_audit(contract.contract_id, mechanism, "development")
        for mechanism in BRIDGE_MECHANISMS
    ]
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
    confirmation_audits = [
        _static_audit(contract.contract_id, mechanism, "fresh_confirmation")
        for mechanism in BRIDGE_MECHANISMS
    ]
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
