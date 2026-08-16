from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_heterogeneous_mainline import (  # noqa: E501
    FINANCE_V26_MAINLINE_VERSION,
    CapabilityHeterogeneousMainlineProtocol,
    ContributionRecoveryContract,
    ImmutableArtifactReference,
    JointCompilationAdmissionContract,
    MainlineStateMaterializationContract,
    MainlineSupportContract,
    MainlineSupportObservation,
    StudentEvaluationContract,
    _no_c_contract,
    _population_contract,
    capability_heterogeneous_mainline_protocol_id,
    make_mainline_support_observation,
    partition_mainline_support,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_bridge import (
    default_compiler_assisted_bridge_contract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_state_support import (
    make_state_support_discovery_plan,
)


def _observation(**updates: Any) -> MainlineSupportObservation:
    values: dict[str, Any] = {
        "task_id": "task:1",
        "rollout_id": "rollout:1",
        "capability_axis": "recovery",
        "split_id": "synthesis_training",
        "phase": "discovery",
        "terminal_status": "model_failed",
        "construct_valid": True,
        "runtime_eligible_for_capability_denominator": True,
        "observable": True,
        "interference_free": True,
    }
    values.update(updates)
    return make_mainline_support_observation(**values)


def _protocol() -> CapabilityHeterogeneousMainlineProtocol:
    bridge = default_compiler_assisted_bridge_contract()
    values = {
        "run_id": "finance_v26_protocol_test",
        "prior_evidence": (
            ImmutableArtifactReference(
                role="historical_measurement_hypothesis_only",
                artifact_id="decision:v25.47",
                schema_version="decision.v1",
                path="/frozen/v25.47.json",
                sha256="a" * 64,
            ),
        ),
        "population": _population_contract(),
        "joint_compilation": JointCompilationAdmissionContract(),
        "capability_bridge": bridge,
        "state_support_discovery": make_state_support_discovery_plan(bridge),
        "materialization": MainlineStateMaterializationContract(),
        "support": MainlineSupportContract(),
        "no_c": _no_c_contract(),
        "contribution": ContributionRecoveryContract(),
        "student_evaluation": StudentEvaluationContract(),
        "explorer_config_sha256": "b" * 64,
        "student_config_sha256": "c" * 64,
        "archive_config_sha256": "d" * 64,
        "schema_version": FINANCE_V26_MAINLINE_VERSION,
    }
    provisional = CapabilityHeterogeneousMainlineProtocol.model_construct(
        protocol_id="pending", **values
    )
    return CapabilityHeterogeneousMainlineProtocol(
        protocol_id=capability_heterogeneous_mainline_protocol_id(provisional),
        **values,
    )


def test_failed_model_outcome_is_measurement_support_only() -> None:
    failed = _observation()
    partition = partition_mainline_support((failed,))

    assert partition.measurement_observation_ids == (failed.observation_id,)
    assert partition.training_observation_ids == ()
    assert partition.contribution_observation_ids == ()
    assert partition.failed_outcome_measurement_count == 1
    assert partition.failed_outcome_training_count == 0
    assert not partition.inverse_success_weighting_used


def test_discovery_success_cannot_be_promoted_to_positive_sft() -> None:
    discovery = _observation(
        terminal_status="completed",
        independent_validity_passed=True,
        quotient_state_id="state:recovery",
        state_mapping_on_target=True,
        replayable=True,
        decision_trace_hash="1" * 64,
    )
    partition = partition_mainline_support((discovery,))

    assert discovery.observation_id in partition.measurement_observation_ids
    assert discovery.observation_id not in partition.training_observation_ids
    assert partition.excluded_from_training[discovery.observation_id] == (
        "discovery_not_positive_materialization",
    )


def test_valid_materialization_enters_training_but_not_contribution() -> None:
    materialized = _observation(
        phase="materialization",
        terminal_status="completed",
        independent_validity_passed=True,
        quotient_state_id="state:recovery",
        state_mapping_on_target=True,
        replayable=True,
        decision_trace_hash="2" * 64,
    )
    partition = partition_mainline_support((materialized,))

    assert partition.training_observation_ids == (materialized.observation_id,)
    assert partition.contribution_observation_ids == ()
    assert (
        "exact_target_not_meaningful"
        in partition.excluded_from_contribution[materialized.observation_id]
    )


def test_contribution_support_requires_the_complete_independent_chain() -> None:
    exact_target_only = _observation(exact_target_exceeds_mpe=True)
    intermediate = partition_mainline_support((exact_target_only,))
    assert intermediate.contribution_observation_ids == ()

    with pytest.raises(ValidationError, match="complete sealed chain"):
        _observation(
            contribution_authorization_id="authorization:premature",
            exact_target_exceeds_mpe=True,
        )

    authorized = _observation(
        phase="materialization",
        terminal_status="completed",
        independent_validity_passed=True,
        quotient_state_id="state:recovery",
        state_mapping_on_target=True,
        replayable=True,
        decision_trace_hash="3" * 64,
        beneficiary_boundary_id="beneficiary:qwen:round0",
        contribution_authorization_id="authorization:sealed",
        exact_target_exceeds_mpe=True,
        gp_c_independently_validated=True,
        distribution_update_contract_passed=True,
    )
    partition = partition_mainline_support((authorized,))

    assert partition.contribution_observation_ids == (authorized.observation_id,)


def test_duplicate_positive_decision_traces_are_rejected() -> None:
    first = _observation(
        phase="materialization",
        terminal_status="completed",
        independent_validity_passed=True,
        quotient_state_id="state:first",
        state_mapping_on_target=True,
        replayable=True,
        decision_trace_hash="4" * 64,
    )
    second = _observation(
        task_id="task:2",
        rollout_id="rollout:2",
        phase="materialization",
        terminal_status="completed",
        independent_validity_passed=True,
        quotient_state_id="state:second",
        state_mapping_on_target=True,
        replayable=True,
        decision_trace_hash="4" * 64,
    )

    with pytest.raises(ValueError, match="duplicate decision traces"):
        partition_mainline_support((first, second))


def test_v26_protocol_keeps_old_results_and_contribution_closed() -> None:
    protocol = _protocol()

    assert protocol.schema_version == FINANCE_V26_MAINLINE_VERSION
    assert protocol.population.task_marginal_probability == 0.01
    assert protocol.population.explorer_replicas_per_training_task == 8
    assert protocol.historical_task_promotion_count == 0
    assert not protocol.prior_evidence[0].authorizes_current_population
    assert protocol.no_c.method_label == "AEVTDR-NoC"
    assert protocol.no_c.materialized_training_rounds == (1, 3)
    assert protocol.no_c.dynamics_only_rounds == (5,)
    assert protocol.contribution.production_contribution == 0.0
    assert not protocol.flash_api_calls_authorized
    assert protocol.current_permitted_stage == "v26_1_joint_compilation_admission"
    assert protocol.joint_compilation.pre_model_admission_required
    assert protocol.joint_compilation.failure_transition == "joint_compilation_repair_only"
    assert protocol.capability_bridge.planned_development_rollout_count == 576
    assert protocol.capability_bridge.support_selected_per_mechanism_not_task
    assert not protocol.capability_bridge.api_authorized_before_static_construct_audit
    assert protocol.capability_bridge.development_three_state_gate_forbidden
    assert protocol.capability_bridge.estimand_compression_forbidden
    assert protocol.state_support_discovery.total_unconditional_rollouts_per_task == 18
    assert protocol.state_support_discovery.support_freeze_required_before_no_c


def test_v26_protocol_rejects_historical_task_promotion() -> None:
    protocol = _protocol()
    payload = protocol.model_dump(mode="json")
    payload["prior_evidence"][0]["historical_task_promotion_count"] = 1

    with pytest.raises(ValidationError):
        CapabilityHeterogeneousMainlineProtocol.model_validate(payload)
