from __future__ import annotations

import json

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
    bridge_cell_observation_id,
    bridge_static_construct_audit_id,
    confirm_compiler_assisted_bridge,
    default_compiler_assisted_bridge_contract,
    freeze_compiler_assisted_bridge_support,
    make_bridge_execution_manifest,
    make_bridge_rollout_observation,
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
    task_admission_ids = {task_id: f"admission:{task_id}" for task_id in task_ids}
    auditor_id = f"bridge_test.{mechanism}"
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
                check_passed=passed,
            )
            for task_id, task_checks in checks.items()
            for check_id, passed in task_checks.items()
        ),
        auditor_id=auditor_id,
        auditor_version=auditor_version,
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


def _summary(task_id: str):
    spec = make_minimal_public_state_summary_spec(
        compiler_id="bridge_test.summary",
        compiler_version="1.0.0",
        source_kinds=("task_public",),
        included_fields=("remaining_tool_budget",),
    )
    observation = make_public_state_observation(
        task_id=task_id,
        sequence_index=0,
        source_kind="task_public",
        values={"remaining_tool_budget": 4},
    )
    return compile_public_state_summary(spec, (observation,))


def _lineage(
    task_id: str,
    level: str,
    *,
    compiled_id: str,
    mapping_id: str,
) -> CompiledTaskConditionLineage:
    summary = _summary(task_id) if level != "gamma_0" else None
    values = {
        "task_id": task_id,
        "compiled_task_condition_id": compiled_id,
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
        "state_mapping_contract_id": mapping_id,
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
        prompt_manifest={"template_id": "bridge-test.v1"},
        runtime_id="autonomous",
        tool_manifest={"allowed_tools": ["evidence_lookup"]},
    )


def _cell(
    contract_id: str,
    authorization_id: str,
    mechanism: BridgeMechanism,
    level: str,
    *,
    phase: str = "development",
    task_ids: tuple[str, ...] | None = None,
    compiled_task_condition_ids: tuple[str, ...] | None = None,
    state_mapping_contract_ids: tuple[str, ...] | None = None,
    omit_last_rollout: bool = False,
):
    rank = SCAFFOLD_LEVELS.index(level)  # type: ignore[arg-type]
    if task_ids is not None:
        selected_task_ids = task_ids
    elif phase == "development":
        selected_task_ids = _development_task_ids(mechanism)
    else:
        index = BRIDGE_MECHANISMS.index(mechanism)
        selected_task_ids = tuple(f"confirmation:{index}:{item}" for item in range(8))
    compiled_ids = compiled_task_condition_ids or tuple(
        f"condition:{task_id}:{level}" for task_id in selected_task_ids
    )
    mapping_ids = state_mapping_contract_ids or tuple(
        f"mapping:{task_id}" for task_id in selected_task_ids
    )
    lineages = {
        task_id: _lineage(
            task_id,
            level,
            compiled_id=compiled_id,
            mapping_id=mapping_id,
        )
        for task_id, compiled_id, mapping_id in zip(
            selected_task_ids,
            compiled_ids,
            mapping_ids,
            strict=True,
        )
    }
    summaries = {
        task_id: (_summary(task_id) if rank >= 1 else None) for task_id in selected_task_ids
    }
    successes_per_task = (1, 3, 4, 5)[rank]
    fixed_policy_successes_per_task = 1
    rollouts = []
    for task_index, task_id in enumerate(selected_task_ids):
        for replicate_index in range(6):
            global_index = task_index * 6 + replicate_index
            outcomes = []
            for estimand_id in MECHANISM_ESTIMANDS[mechanism]:
                evaluated = True
                outcomes.append(
                    BridgeEstimandOutcome(
                        estimand_id=estimand_id,
                        evaluated=evaluated,
                        success=replicate_index < successes_per_task,
                        fixed_policy_success=(replicate_index < fixed_policy_successes_per_task),
                    )
                )
            terminal = (
                "model_valid_trajectory"
                if replicate_index < successes_per_task
                else "model_invalid_trajectory"
            )
            raw_payload = {
                "task_id": task_id,
                "replicate_index": replicate_index,
                "terminal_category": terminal,
                "failure_attribution": (
                    None if terminal == "model_valid_trajectory" else "model_contract_invalid"
                ),
            }
            rollouts.append(
                make_bridge_rollout_observation(
                    contract_id=contract_id,
                    phase_authorization_id=authorization_id,
                    phase=phase,  # type: ignore[arg-type]
                    mechanism_id=mechanism,
                    scaffold_level=level,  # type: ignore[arg-type]
                    replicate_index=replicate_index,
                    condition_lineage=lineages[task_id],
                    execution_manifest=_execution_manifest(contract_id, lineages[task_id]),
                    provider_call_ids=(
                        f"call:{phase}:{mechanism}:{level}:{task_id}:{replicate_index}",
                    ),
                    public_state_summary=summaries[task_id],
                    terminal_category=terminal,
                    independent_validity_passed=terminal == "model_valid_trajectory",
                    quotient_state_id="state:shared",
                    decision_trace_hash=f"trajectory_decision_trace:{global_index + 1:064x}",
                    estimand_outcomes=tuple(outcomes),
                    raw_payload=raw_payload,
                    raw_artifact_uri=f"embedded://bridge/{task_id}/{replicate_index}",
                )
            )
    if omit_last_rollout:
        rollouts.pop()
    return aggregate_bridge_cell_observation(
        contract_id=contract_id,
        phase_authorization_id=authorization_id,
        phase=phase,  # type: ignore[arg-type]
        mechanism_id=mechanism,
        scaffold_level=level,  # type: ignore[arg-type]
        rollout_observations=rollouts,
    )


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


def test_bridge_execution_manifest_rejects_credential_material() -> None:
    lineage = _lineage(
        "task:credential",
        "gamma_1",
        compiled_id="condition:credential",
        mapping_id="mapping:credential",
    )

    with pytest.raises(ValidationError, match="contains credential material"):
        make_bridge_execution_manifest(
            contract_id="contract:credential",
            condition_lineage=lineage,
            model_id="deepseek-v4-flash",
            model_config={"temperature": 0.2},
            provider_route={"provider": "test", "api_key": "not-serializable"},
            prompt_manifest={"template_id": "credential-test.v1"},
            runtime_id="autonomous",
            tool_manifest={"allowed_tools": ["evidence_lookup"]},
        )


def test_static_construct_failure_blocks_before_model_calls() -> None:
    contract = default_compiler_assisted_bridge_contract()
    authorization = _authorization(contract, failed_mechanism="semantic_reconciliation")

    assert authorization.status == "blocked"
    assert authorization.blockers == ("semantic_reconciliation",)
    assert authorization.next_transition == "bridge_static_construct_repair_only"
    assert authorization.model_api_calls == 0
    assert authorization.gpu_jobs == 0


def test_static_construct_audit_rejects_forged_aggregate_after_outer_rehash() -> None:
    contract = default_compiler_assisted_bridge_contract()
    audit = _static_audit(
        contract.contract_id,
        "semantic_reconciliation",
        fail=True,
    )
    provisional = audit.model_copy(
        update={
            "passed_task_count": 8,
            "construct_fidelity_rate": 1.0,
            "status": "passed",
            "audit_id": "pending",
        }
    )
    forged = provisional.model_copy(
        update={"audit_id": bridge_static_construct_audit_id(provisional)}
    )

    with pytest.raises(ValidationError, match="pass count is inconsistent"):
        type(audit).model_validate(forged.model_dump(mode="json"))


def test_bridge_selects_minimum_boundary_level_without_three_state_gate() -> None:
    contract, _, freeze = _passing_freeze()
    canonical_payload = json.loads(
        json.dumps(freeze.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    )

    assert freeze.status == "passed"
    assert type(freeze).model_validate(canonical_payload) == freeze
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
    cell = _cell(
        contract.contract_id,
        authorization.authorization_id,
        "recovery_and_stopping",
        "gamma_1",
    )
    payload = cell.rollout_observations[0].model_dump(mode="json")
    payload["estimand_outcomes"] = payload["estimand_outcomes"][:1]

    with pytest.raises(ValidationError, match="Estimands are incomplete"):
        type(cell.rollout_observations[0]).model_validate(payload)


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

    with pytest.raises(ValueError, match="exactly 48 atomic rollouts"):
        _cell(
            contract.contract_id,
            authorization.authorization_id,
            "context_conditioned_action",
            "gamma_1",
            omit_last_rollout=True,
        )


def test_bridge_cell_rejects_forged_denominator_after_outer_rehash() -> None:
    contract = default_compiler_assisted_bridge_contract()
    authorization = _authorization(contract)
    cell = _cell(
        contract.contract_id,
        authorization.authorization_id,
        "context_conditioned_action",
        "gamma_1",
    )
    provisional = cell.model_copy(
        update={
            "instrument_valid_rollout_count": cell.instrument_valid_rollout_count - 1,
            "observation_id": "pending",
        }
    )
    forged = provisional.model_copy(
        update={"observation_id": bridge_cell_observation_id(provisional)}
    )

    with pytest.raises(ValidationError, match="not derived from atomic rollouts"):
        type(cell).model_validate(forged.model_dump(mode="json"))


def test_bridge_rollout_rejects_rehashed_raw_payload_tampering() -> None:
    contract = default_compiler_assisted_bridge_contract()
    authorization = _authorization(contract)
    cell = _cell(
        contract.contract_id,
        authorization.authorization_id,
        "context_conditioned_action",
        "gamma_1",
    )
    rollout = cell.rollout_observations[0]
    payload = rollout.model_dump(mode="json")
    payload["raw_payload"]["terminal_category"] = "model_invalid_trajectory"
    payload["rollout_id"] = "finance_bridge_rollout:outer_rehashed"

    with pytest.raises(ValidationError, match="raw payload identity is inconsistent"):
        type(rollout).model_validate(payload)


def test_bridge_rollout_separates_attempt_and_provider_call_denominators() -> None:
    contract = default_compiler_assisted_bridge_contract()
    authorization = _authorization(contract)
    task_id = _development_task_ids("context_conditioned_action")[0]
    lineage = _lineage(
        task_id,
        "gamma_0",
        compiled_id=f"condition:{task_id}:gamma_0",
        mapping_id=f"mapping:{task_id}",
    )
    execution = _execution_manifest(contract.contract_id, lineage)
    outcomes = tuple(
        BridgeEstimandOutcome(estimand_id=item, evaluated=False)
        for item in MECHANISM_ESTIMANDS["context_conditioned_action"]
    )

    failed = make_bridge_rollout_observation(
        contract_id=contract.contract_id,
        phase_authorization_id=authorization.authorization_id,
        phase="development",
        mechanism_id="context_conditioned_action",
        scaffold_level="gamma_0",
        replicate_index=0,
        condition_lineage=lineage,
        execution_manifest=execution,
        provider_call_ids=(),
        public_state_summary=None,
        terminal_category="instrument_failure",
        independent_validity_passed=False,
        quotient_state_id=None,
        decision_trace_hash=None,
        estimand_outcomes=outcomes,
        raw_payload={
            "task_id": task_id,
            "terminal_category": "instrument_failure",
        },
        raw_artifact_uri="raw://instrument-failure",
        failure_reason="pre_request_manifest_failure",
    )
    assert failed.provider_call_ids == ()

    with pytest.raises(ValidationError, match="require Provider-call lineage"):
        make_bridge_rollout_observation(
            contract_id=contract.contract_id,
            phase_authorization_id=authorization.authorization_id,
            phase="development",
            mechanism_id="context_conditioned_action",
            scaffold_level="gamma_0",
            replicate_index=0,
            condition_lineage=lineage,
            execution_manifest=execution,
            provider_call_ids=(),
            public_state_summary=None,
            terminal_category="model_invalid_trajectory",
            independent_validity_passed=False,
            quotient_state_id=None,
            decision_trace_hash="trajectory_decision_trace:" + "a" * 64,
            estimand_outcomes=outcomes,
            raw_payload={
                "task_id": task_id,
                "terminal_category": "model_invalid_trajectory",
            },
            raw_artifact_uri="raw://invalid-model-outcome",
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
