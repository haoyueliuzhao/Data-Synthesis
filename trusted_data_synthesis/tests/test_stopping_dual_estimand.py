from __future__ import annotations

import pytest
from pydantic import ValidationError

from trusted_synthesis.domains.finance.capability_submechanism_runtime import (
    FINANCE_STOPPING_SHAPE_DECISION_V1_VERSION,
    FinanceStoppingDependencyOption,
    FinanceStoppingResolutionAction,
    FinanceStoppingShapeDecisionContract,
    FinanceSubmechanismEvidenceRole,
    make_finance_submechanism_scenario,
    public_submechanism_contract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_dual_estimand import (
    FinanceStoppingDualEstimandReport,
    FrozenStoppingDualEstimandPolicy,
    StoppingDualEstimandObservation,
    StoppingDualEstimandResult,
    StoppingDualEstimandTaskResponse,
    _stopping_information_bootstrap,
    stopping_dual_estimand_observation_id,
    stopping_dual_estimand_policy_id,
    stopping_dual_estimand_report_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_dual_estimand_protocol import (
    ALL_SHAPES,
    PROSPECTIVE_RECHECK_SHAPES,
    STRUCTURAL_REDESIGN_SHAPES,
    STRUCTURAL_STRATA,
    StoppingDualEstimandThresholds,
    _semantic_content_tokens,
)

SHAPE_ROLES = {
    "partial_required_evidence": "boundary_candidate",
    "authority_coverage_gap": "boundary_candidate",
    "single_dimension_conflict": "boundary_candidate",
    "contextual_resolution_choice": "boundary_candidate",
    "verified_extra_call_error_risk": "runtime_control",
    "verified_extra_call_cost": "runtime_control",
}


def _roles() -> tuple[FinanceSubmechanismEvidenceRole, ...]:
    return tuple(
        FinanceSubmechanismEvidenceRole(
            role_id=f"required_{index}",
            evidence_id=f"evidence:{index}",
            subject_alias=f"entity:{index}",
            metric_alias=f"metric:{index}",
            period_label=f"FY20{20 + index}",
        )
        for index in (1, 2)
    )


def _decoy() -> FinanceStoppingDependencyOption:
    return FinanceStoppingDependencyOption(
        option_id="option:decoy",
        subject_alias="entity:decoy",
        metric_alias="metric:decoy",
        period_label="FY2024",
    )


def _dependency_decision() -> FinanceStoppingShapeDecisionContract:
    return FinanceStoppingShapeDecisionContract(
        contract_kind="dependency_disambiguation_required",
        dependency_rule="Choose the query that closes the unresolved operation dependency.",
        dependency_decoy_option=_decoy(),
        resolution_step_count=1,
    )


def _conflict_decision() -> FinanceStoppingShapeDecisionContract:
    return FinanceStoppingShapeDecisionContract(
        contract_kind="single_conflict_semantic_choice_one_step",
        observed_conflict_signal=(
            "A direct comparison would change the economic meaning of at least one selected figure."
        ),
        oracle_conflict_dimension="source_definition_compatibility",
        available_resolution_actions=(
            FinanceStoppingResolutionAction(
                tool_id="normalize_metric_unit_period",
                applicable_when=("re-express the measurements under a shared reporting convention"),
            ),
            FinanceStoppingResolutionAction(
                tool_id="open_document",
                applicable_when=(
                    "inspect provenance when document authority or location is unresolved"
                ),
            ),
        ),
        resolution_step_count=1,
    )


def _cost_decision() -> FinanceStoppingShapeDecisionContract:
    return FinanceStoppingShapeDecisionContract(
        contract_kind="sealed_terminal_extra_call_cost",
        terminal_utility_loss=1.0,
        archive_snapshot_sealed=True,
        maximum_additional_information_gain=0.0,
        realized_call_budget_debit_fraction=0.25,
        realized_token_budget_debit_fraction=0.20,
        additional_action_rejected=True,
    )


@pytest.mark.parametrize(
    ("decision", "runtime_kind"),
    (
        (_dependency_decision(), "incomplete_continue"),
        (_conflict_decision(), "evidence_conflict"),
        (_cost_decision(), "post_complete_cost"),
    ),
)
def test_v25_38_public_projection_omits_oracle_decision_fields(
    decision: FinanceStoppingShapeDecisionContract,
    runtime_kind: str,
) -> None:
    scenario = make_finance_submechanism_scenario(
        submechanism_id="finance.test.dual_estimand",
        parent_mechanism_id="finance.test.parent",
        intervention_kind=runtime_kind,
        expected_host_events=("observe:decision", "resolve:decision"),
        evidence_roles=_roles(),
        public_resolution_hint="Use the public decision state.",
        stopping_shape_decision_contract=decision,
    )

    public = public_submechanism_contract(scenario)
    projected = public["stopping_shape_decision_contract"]

    assert "contract_kind" not in projected
    assert "dependency_decoy_option" not in projected
    assert "oracle_conflict_dimension" not in projected
    assert projected["internal_shape_identity_disclosed"] is False


@pytest.mark.parametrize(
    "payload",
    (
        {
            "contract_kind": "dependency_disambiguation_required",
            "dependency_rule": "Choose an unresolved operand.",
            "resolution_step_count": 1,
        },
        {
            "contract_kind": "single_conflict_semantic_choice_one_step",
            "observed_conflict_signal": "The figures conflict.",
            "oracle_conflict_dimension": "source_definition_compatibility",
            "available_resolution_actions": (),
            "resolution_step_count": 1,
        },
        {
            "contract_kind": "sealed_terminal_extra_call_cost",
            "archive_snapshot_sealed": True,
            "maximum_additional_information_gain": 0.0,
            "realized_call_budget_debit_fraction": 0.25,
            "realized_token_budget_debit_fraction": 0.20,
            "terminal_utility_loss": 1.0,
            "additional_action_rejected": False,
        },
    ),
)
def test_v25_38_decision_contracts_fail_closed(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="decision contract is inconsistent"):
        FinanceStoppingShapeDecisionContract.model_validate(payload)


def test_v1_decision_serialization_preserves_frozen_canonical_field_set() -> None:
    decision = FinanceStoppingShapeDecisionContract(
        contract_kind="partial_evidence_count_only",
        missing_role_disclosure="count_only",
        schema_version=FINANCE_STOPPING_SHAPE_DECISION_V1_VERSION,
    )

    payload = decision.model_dump(mode="json")

    assert payload["schema_version"] == FINANCE_STOPPING_SHAPE_DECISION_V1_VERSION
    assert "dependency_rule" not in payload
    assert "dependency_decoy_option" not in payload
    assert "oracle_conflict_dimension" not in payload


def test_semantic_conflict_requires_semantics_not_content_word_copying() -> None:
    decision = _conflict_decision()
    signal = _semantic_content_tokens(str(decision.observed_conflict_signal))

    assert signal
    assert all(
        not signal & _semantic_content_tokens(item.applicable_when)
        for item in decision.available_resolution_actions
    )


def _observation(
    *,
    runtime_eligible: bool = True,
    host_event_ordered: bool = True,
    post_completion_violation_observed: bool = False,
    terminal_valid_success: bool = False,
    answer_semantic_success: bool = False,
) -> StoppingDualEstimandObservation:
    stopping = runtime_eligible and host_event_ordered and not post_completion_violation_observed
    full_valid = stopping and terminal_valid_success
    values = {
        "contract_id": "contract:test",
        "source_behavior_observation_id": "behavior:test",
        "record_id": "record:test",
        "binding_id": "binding:test",
        "task_artifact_id": "task:test",
        "shape_id": "shape:test",
        "stratum_id": "stratum:test",
        "replicate": 0,
        "runtime_eligible": runtime_eligible,
        "host_event_ordered": host_event_ordered,
        "post_completion_violation_observed": post_completion_violation_observed,
        "stopping_behavior_success": stopping,
        "terminal_valid_success": terminal_valid_success,
        "full_valid_trajectory_success": full_valid,
        "answer_semantic_success": answer_semantic_success,
        "final_answer_emitted": True,
        "stop_quality_success": True,
        "terminalization_success": True,
        "training_eligible": full_valid,
    }
    provisional = StoppingDualEstimandObservation.model_construct(
        observation_id="pending", **values
    )
    return StoppingDualEstimandObservation(
        observation_id=stopping_dual_estimand_observation_id(provisional), **values
    )


def test_correct_stopping_can_be_observed_without_admitting_invalid_training_data() -> None:
    observation = _observation(
        terminal_valid_success=False,
        answer_semantic_success=False,
    )

    assert observation.stopping_behavior_success
    assert not observation.full_valid_trajectory_success
    assert not observation.training_eligible


def test_full_valid_response_cannot_exceed_stopping_response() -> None:
    with pytest.raises(ValidationError, match="Full-valid support exceeds"):
        StoppingDualEstimandTaskResponse(
            task_artifact_id="task:test",
            stratum_id="retrieval_planning_frontier",
            stratum_instance_index=0,
            stopping_realizations=(0, 0, 0, 0, 0, 0, 0, 0),
            full_valid_realizations=(1, 0, 0, 0, 0, 0, 0, 0),
            semantic_realizations=(1, 0, 0, 0, 0, 0, 0, 0),
            stopping_probability=0.0,
            full_valid_probability=0.125,
            semantic_probability=0.125,
            stopping_fisher_information=0.0,
            full_valid_fisher_information=0.109375,
        )


def _task_responses(*, valid: bool) -> tuple[StoppingDualEstimandTaskResponse, ...]:
    stopping = (1, 0, 1, 0, 1, 0, 1, 0)
    full_valid = stopping if valid else (0, 0, 0, 0, 0, 0, 0, 0)
    return tuple(
        StoppingDualEstimandTaskResponse(
            task_artifact_id=f"task:{index}:{instance}",
            stratum_id=stratum[0],
            stratum_instance_index=instance,
            stopping_realizations=stopping,
            full_valid_realizations=full_valid,
            semantic_realizations=stopping,
            stopping_probability=0.5,
            full_valid_probability=0.5 if valid else 0.0,
            semantic_probability=0.5,
            stopping_fisher_information=0.25,
            full_valid_fisher_information=0.25 if valid else 0.0,
        )
        for index, stratum in enumerate(STRUCTURAL_STRATA)
        for instance in (0, 1)
    )


def _shape_result(
    shape_id: str,
    *,
    admitted: bool,
    valid: bool,
) -> StoppingDualEstimandResult:
    responses = _task_responses(valid=valid)
    valid_count = sum(sum(item.full_valid_realizations) for item in responses)
    gates = {"scientific_gate": admitted}
    return StoppingDualEstimandResult(
        shape_id=shape_id,
        shape_role=SHAPE_ROLES[shape_id],
        design_status=(
            "prospective_estimand_recheck"
            if shape_id in PROSPECTIVE_RECHECK_SHAPES
            else "structural_redesign"
        ),
        task_responses=responses,
        mean_stopping_success_rate=0.5,
        mean_full_valid_success_rate=0.5 if valid else 0.0,
        mean_semantic_success_rate=0.5,
        minimum_stopping_task_probability=0.5,
        maximum_stopping_task_probability=0.5,
        between_task_stopping_probability_range=0.0,
        stopping_boundary_task_count=8,
        stopping_nonzero_information_task_count=8,
        total_stopping_fisher_information=2.0,
        total_full_valid_fisher_information=2.0 if valid else 0.0,
        stopping_effective_task_count=8.0,
        stopping_maximum_single_task_information_share=0.125,
        stopping_bootstrap_information_interval95=(1.0, 2.0),
        stopping_bootstrap_information_lcb=1.0,
        valid_training_trajectory_count=valid_count,
        valid_training_support_rate=valid_count / 64,
        gate_results=gates,
        admitted=admitted,
        failure_codes=() if admitted else ("scientific_gate",),
    )


def _policy() -> FrozenStoppingDualEstimandPolicy:
    values = {
        "source_contract_id": "contract:test",
        "shape_task_quotas": {shape_id: 8 for shape_id in ALL_SHAPES},
        "structural_strata": STRUCTURAL_STRATA,
        "thresholds": StoppingDualEstimandThresholds(),
    }
    provisional = FrozenStoppingDualEstimandPolicy.model_construct(policy_id="pending", **values)
    return FrozenStoppingDualEstimandPolicy(
        policy_id=stopping_dual_estimand_policy_id(provisional), **values
    )


def _report(
    shape_results: tuple[StoppingDualEstimandResult, ...],
) -> FinanceStoppingDualEstimandReport:
    all_shapes = all(item.admitted for item in shape_results)
    valid_ready = all(item.valid_training_trajectory_count > 0 for item in shape_results)
    valid_count = sum(item.valid_training_trajectory_count for item in shape_results)
    policy = _policy() if all_shapes else None
    values = {
        "contract_id": "contract:test",
        "recorded_rollout_count": 384,
        "execution_integrity_rate": 1.0,
        "terminal_resolution_rate": 1.0,
        "api_transport_resolution_rate": 1.0,
        "bounded_json_resolution_rate": 1.0,
        "observation_replay_rate": 1.0,
        "authority_integrity_rate": 1.0,
        "runtime_pathology_rate": 0.0,
        "l0_l2_failure_count": 0,
        "stopping_behavior_success_rate": 0.5,
        "full_valid_trajectory_success_rate": valid_count / 384,
        "answer_semantic_success_rate": 0.5,
        "terminalization_success_rate": 1.0,
        "valid_training_trajectory_count": valid_count,
        "valid_training_support_ready": valid_ready,
        "runtime_measurement_ready": True,
        "shape_results": shape_results,
        "prospective_recheck_failure_count": sum(
            not item.admitted
            for item in shape_results
            if item.shape_id in PROSPECTIVE_RECHECK_SHAPES
        ),
        "structural_redesign_admission_count": sum(
            item.admitted for item in shape_results if item.shape_id in STRUCTURAL_REDESIGN_SHAPES
        ),
        "mechanism_observable_shape_count": sum(item.admitted for item in shape_results),
        "all_shapes_admitted": all_shapes,
        "policy": policy,
        "policy_frozen": all_shapes,
        "api_call_count": 384,
        "total_model_tokens": 10_000,
        "estimated_cost_usd": 1.0,
        "discovered_models": ("DeepSeek-V4-Flash",),
        "failure_codes": (),
        "fresh_three_population_preparation_authorized": all_shapes and valid_ready,
        "next_permitted_stage": (
            "stopping_shape_redesign_only"
            if not all_shapes
            else (
                "fresh_three_population_dual_estimand_preparation"
                if valid_ready
                else "valid_training_support_repair_only"
            )
        ),
    }
    provisional = FinanceStoppingDualEstimandReport.model_construct(report_id="pending", **values)
    return FinanceStoppingDualEstimandReport(
        report_id=stopping_dual_estimand_report_id(provisional), **values
    )


def test_full_valid_success_cannot_rescue_a_failed_stopping_shape() -> None:
    failed = sorted(ALL_SHAPES)[0]
    results = tuple(
        _shape_result(shape_id, admitted=shape_id != failed, valid=True)
        for shape_id in sorted(ALL_SHAPES)
    )

    report = _report(results)

    assert report.valid_training_support_ready
    assert not report.all_shapes_admitted
    assert not report.policy_frozen
    assert report.next_permitted_stage == "stopping_shape_redesign_only"


def test_mechanism_policy_does_not_admit_invalid_training_support() -> None:
    no_valid = sorted(ALL_SHAPES)[0]
    results = tuple(
        _shape_result(shape_id, admitted=True, valid=shape_id != no_valid)
        for shape_id in sorted(ALL_SHAPES)
    )

    report = _report(results)

    assert report.all_shapes_admitted
    assert report.policy_frozen
    assert not report.valid_training_support_ready
    assert not report.fresh_three_population_preparation_authorized
    assert report.next_permitted_stage == "valid_training_support_repair_only"


def test_dual_estimand_bootstrap_is_deterministic() -> None:
    thresholds = StoppingDualEstimandThresholds(bootstrap_replicates=1_000)
    responses = _task_responses(valid=True)

    first = _stopping_information_bootstrap(responses, thresholds, shape_id="shape:test")
    second = _stopping_information_bootstrap(responses, thresholds, shape_id="shape:test")

    assert first == second
    assert first[0] > 0.0
