from __future__ import annotations

import pytest
from pydantic import ValidationError

from trusted_synthesis.domains.finance.capability_submechanism_runtime import (
    FINANCE_STOPPING_SHAPE_DECISION_V1_VERSION,
    FINANCE_STOPPING_SHAPE_DECISION_V2_VERSION,
    FINANCE_STOPPING_SHAPE_DECISION_V3_VERSION,
    FINANCE_STOPPING_SHAPE_DECISION_V4_VERSION,
    FinanceStoppingDependencyOption,
    FinanceStoppingMeasurementContext,
    FinanceStoppingObservedEvidenceState,
    FinanceStoppingObservedRecord,
    FinanceStoppingResolutionAction,
    FinanceStoppingShapeDecisionContract,
    FinanceStoppingTemporalIdentity,
    FinanceSubmechanismEvidenceRole,
    make_finance_submechanism_scenario,
    public_submechanism_contract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_policy import (
    FinanceStoppingShapePolicyReport,
    FrozenStoppingShapePolicyPolicy,
    StoppingShapePolicyObservation,
    StoppingShapePolicyResult,
    StoppingShapePolicyTaskResponse,
    _stopping_information_bootstrap,
    stopping_shape_policy_observation_id,
    stopping_shape_policy_policy_id,
    stopping_shape_policy_report_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_policy_protocol import (
    ALL_SHAPES,
    BOUNDARY_CANDIDATE_SHAPES,
    CONFLICT_MISMATCH_BY_CELL,
    RUNTIME_CONTROL_SHAPES,
    STRUCTURAL_STRATA,
    TARGET_ROLE_ID_BY_SHAPE,
    StoppingConflictCellAllocation,
    StoppingPredecessorMeasurementAudit,
    StoppingRolePositionPredecessorAudit,
    StoppingShapePolicyThresholds,
    StoppingToolPayloadMeasurementAudit,
    _artifact_identity_matches,
    _semantic_content_tokens,
)
from trusted_synthesis.hashing import canonical_hash

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
        subject_alias="entity:2",
        metric_alias="metric:2",
        period_label="FY2024",
    )


def _dependency_decision() -> FinanceStoppingShapeDecisionContract:
    return FinanceStoppingShapeDecisionContract(
        contract_kind="conditional_dependency_observation_required",
        dependency_rule=(
            "Probe the Archive and use its observation to identify the active dependency."
        ),
        dependency_decoy_option=_decoy(),
        resolution_step_count=2,
    )


def _state(*, field: str) -> FinanceStoppingObservedEvidenceState:
    required = FinanceStoppingObservedRecord(
        subject_alias="entity:required",
        metric_alias="metric:required",
        temporal_identity=FinanceStoppingTemporalIdentity(label="FY2024"),
        source_id="source:official",
        definition_id="definition:required",
        measurement_context=FinanceStoppingMeasurementContext(
            unit="USD",
            currency="USD",
        ),
    )
    updates: dict[str, object]
    if field == "subject":
        updates = {"subject_alias": "entity:observed"}
    elif field == "period":
        updates = {"temporal_identity": FinanceStoppingTemporalIdentity(label="FY2023")}
    elif field == "definition":
        updates = {"definition_id": "definition:observed"}
    else:
        updates = {
            "measurement_context": FinanceStoppingMeasurementContext(
                unit="thousand USD",
                currency="USD",
            )
        }
    return FinanceStoppingObservedEvidenceState(
        observed_record=required.model_copy(update=updates),
        required_record=required,
    )


def _state_actions() -> tuple[FinanceStoppingResolutionAction, ...]:
    return (
        FinanceStoppingResolutionAction(
            tool_id="normalize_metric_unit_period",
            applicable_when="establish a shared reporting or measurement basis",
        ),
        FinanceStoppingResolutionAction(
            tool_id="open_document",
            applicable_when="inspect document authority when provenance remains uncertain",
        ),
        FinanceStoppingResolutionAction(
            tool_id="query_structured_fact",
            applicable_when="retrieve an observation when subject or period coverage is absent",
        ),
    )


def _contextual_decision() -> FinanceStoppingShapeDecisionContract:
    return FinanceStoppingShapeDecisionContract(
        contract_kind="matched_contextual_evidence_state_choice_two_step",
        observed_conflict_signal=(
            "Two public records are shown below. Exactly one registered identity component differs."
        ),
        observed_evidence_state=_state(field="subject"),
        oracle_conflict_dimension="entity_scope_alignment",
        state_activation_phase="before_required_evidence_selection",
        available_resolution_actions=_state_actions(),
        resolution_step_count=2,
    )


def _conflict_decision() -> FinanceStoppingShapeDecisionContract:
    return FinanceStoppingShapeDecisionContract(
        contract_kind="single_conflict_evidence_state_choice_one_step",
        observed_conflict_signal=(
            "Two public records are shown below. Exactly one registered identity component differs."
        ),
        observed_evidence_state=_state(field="definition"),
        oracle_conflict_dimension="source_definition_compatibility",
        state_activation_phase="after_required_evidence_selection_before_calculation",
        available_resolution_actions=_state_actions(),
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
        (_contextual_decision(), "unresolved_conflict_cannot_stop"),
        (_conflict_decision(), "evidence_conflict"),
        (_cost_decision(), "post_complete_cost"),
    ),
)
def test_v25_40_public_projection_omits_oracle_decision_fields(
    decision: FinanceStoppingShapeDecisionContract,
    runtime_kind: str,
) -> None:
    scenario = make_finance_submechanism_scenario(
        submechanism_id="finance.test.shape_policy",
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
def test_v25_40_decision_contracts_fail_closed(payload: dict[str, object]) -> None:
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


def test_v2_schema_rejects_v25_39_contract_kinds() -> None:
    payload = _dependency_decision().model_dump(mode="json")
    payload["schema_version"] = FINANCE_STOPPING_SHAPE_DECISION_V2_VERSION

    with pytest.raises(ValidationError, match="v3 decision uses a v2 schema identity"):
        FinanceStoppingShapeDecisionContract.model_validate(payload)


def test_v3_schema_rejects_v25_40_state_contracts() -> None:
    payload = _contextual_decision().model_dump(mode="json")
    payload["schema_version"] = FINANCE_STOPPING_SHAPE_DECISION_V3_VERSION

    with pytest.raises(ValidationError, match="v4 decision uses a v3 schema identity"):
        FinanceStoppingShapeDecisionContract.model_validate(payload)


def test_v4_schema_rejects_v25_41_activation_phase() -> None:
    payload = _contextual_decision().model_dump(mode="json")
    payload["schema_version"] = FINANCE_STOPPING_SHAPE_DECISION_V4_VERSION

    with pytest.raises(ValidationError, match="v5 activation uses a v4 schema identity"):
        FinanceStoppingShapeDecisionContract.model_validate(payload)


def test_public_evidence_state_rejects_more_than_one_difference() -> None:
    state = _state(field="subject")
    with pytest.raises(ValidationError, match="exactly one field"):
        FinanceStoppingObservedEvidenceState(
            observed_record=state.observed_record.model_copy(
                update={
                    "definition_id": "definition:also-different",
                }
            ),
            required_record=state.required_record,
        )


def test_conflict_cell_map_freezes_supported_dimensions_and_resolution_tools() -> None:
    counts = {
        field: tuple(CONFLICT_MISMATCH_BY_CELL.values()).count(field)
        for field in {"period", "definition", "payload_context"}
    }

    assert counts == {"period": 6, "definition": 2, "payload_context": 0}
    assert set(CONFLICT_MISMATCH_BY_CELL) == {
        (stratum, instance) for stratum, _, _ in STRUCTURAL_STRATA for instance in (0, 1)
    }
    thresholds = StoppingShapePolicyThresholds()
    assert min(counts["period"], counts["definition"]) >= (
        thresholds.minimum_conflict_tasks_per_resolution_tool
    )
    assert max(counts["period"], counts["definition"]) / 8 <= (
        thresholds.maximum_conflict_resolution_tool_share
    )


def test_conflict_cell_allocation_rejects_wrong_resolution_tool() -> None:
    with pytest.raises(ValidationError, match="wrong resolution tool"):
        StoppingConflictCellAllocation(
            stratum_id="retrieval_join_frontier",
            instance_index=0,
            mismatch_field="period",
            expected_resolution_tool="normalize_metric_unit_period",
        )


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
) -> StoppingShapePolicyObservation:
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
    provisional = StoppingShapePolicyObservation.model_construct(observation_id="pending", **values)
    return StoppingShapePolicyObservation(
        observation_id=stopping_shape_policy_observation_id(provisional), **values
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
        StoppingShapePolicyTaskResponse(
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


def _task_responses(*, valid: bool) -> tuple[StoppingShapePolicyTaskResponse, ...]:
    stopping = (1, 0, 1, 0, 1, 0, 1, 0)
    full_valid = stopping if valid else (0, 0, 0, 0, 0, 0, 0, 0)
    return tuple(
        StoppingShapePolicyTaskResponse(
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
) -> StoppingShapePolicyResult:
    responses = _task_responses(valid=valid)
    valid_count = sum(sum(item.full_valid_realizations) for item in responses)
    gates = {"scientific_gate": admitted}
    return StoppingShapePolicyResult(
        shape_id=shape_id,
        shape_role=SHAPE_ROLES[shape_id],
        design_status=(
            "boundary_regression"
            if shape_id in {"authority_coverage_gap", "partial_required_evidence"}
            else (
                "instrument_regression"
                if shape_id in RUNTIME_CONTROL_SHAPES
                else "structural_redesign"
            )
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


def _policy() -> FrozenStoppingShapePolicyPolicy:
    values = {
        "source_contract_id": "contract:test",
        "shape_task_quotas": {shape_id: 8 for shape_id in ALL_SHAPES},
        "structural_strata": STRUCTURAL_STRATA,
        "thresholds": StoppingShapePolicyThresholds(),
    }
    provisional = FrozenStoppingShapePolicyPolicy.model_construct(policy_id="pending", **values)
    return FrozenStoppingShapePolicyPolicy(
        policy_id=stopping_shape_policy_policy_id(provisional), **values
    )


def _report(
    shape_results: tuple[StoppingShapePolicyResult, ...],
) -> FinanceStoppingShapePolicyReport:
    by_shape = {item.shape_id: item for item in shape_results}
    boundary_admitted = sum(by_shape[shape_id].admitted for shape_id in BOUNDARY_CANDIDATE_SHAPES)
    controls_passed = sum(by_shape[shape_id].admitted for shape_id in RUNTIME_CONTROL_SHAPES)
    all_boundary = boundary_admitted == len(BOUNDARY_CANDIDATE_SHAPES)
    all_controls = controls_passed == len(RUNTIME_CONTROL_SHAPES)
    all_shapes = all_boundary and all_controls
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
        "estimand_semantics_frozen": True,
        "shape_results": shape_results,
        "boundary_candidate_admitted_count": boundary_admitted,
        "boundary_candidate_near_pass_count": sum(
            not by_shape[shape_id].admitted and len(by_shape[shape_id].failure_codes) == 1
            for shape_id in BOUNDARY_CANDIDATE_SHAPES
        ),
        "runtime_control_pass_count": controls_passed,
        "total_contract_passing_shape_count": sum(item.admitted for item in shape_results),
        "all_boundary_candidates_admitted": all_boundary,
        "all_runtime_controls_passed": all_controls,
        "all_shapes_contract_passing": all_shapes,
        "policy": policy,
        "shape_support_policy_frozen": all_shapes,
        "api_call_count": 384,
        "total_model_tokens": 10_000,
        "estimated_cost_usd": 1.0,
        "discovered_models": ("DeepSeek-V4-Flash",),
        "failure_codes": tuple(
            f"shape:{item.shape_id}:{code}" for item in shape_results for code in item.failure_codes
        ),
        "fresh_three_population_preparation_authorized": all_shapes and valid_ready,
        "next_permitted_stage": (
            "stopping_shape_redesign_only"
            if not all_boundary
            else (
                "runtime_control_repair_only"
                if not all_controls
                else (
                    "fresh_three_population_shape_policy_preparation"
                    if valid_ready
                    else "valid_training_support_repair_only"
                )
            )
        ),
    }
    provisional = FinanceStoppingShapePolicyReport.model_construct(report_id="pending", **values)
    return FinanceStoppingShapePolicyReport(
        report_id=stopping_shape_policy_report_id(provisional), **values
    )


def test_full_valid_success_cannot_rescue_a_failed_stopping_shape() -> None:
    failed = sorted(ALL_SHAPES)[0]
    results = tuple(
        _shape_result(shape_id, admitted=shape_id != failed, valid=True)
        for shape_id in sorted(ALL_SHAPES)
    )

    report = _report(results)

    assert report.valid_training_support_ready
    assert report.estimand_semantics_frozen
    assert report.boundary_candidate_admitted_count == 3
    assert report.boundary_candidate_near_pass_count == 1
    assert report.runtime_control_pass_count == 2
    assert not report.shape_support_policy_frozen
    assert report.next_permitted_stage == "stopping_shape_redesign_only"


def test_mechanism_policy_does_not_admit_invalid_training_support() -> None:
    no_valid = sorted(ALL_SHAPES)[0]
    results = tuple(
        _shape_result(shape_id, admitted=True, valid=shape_id != no_valid)
        for shape_id in sorted(ALL_SHAPES)
    )

    report = _report(results)

    assert report.all_boundary_candidates_admitted
    assert report.all_runtime_controls_passed
    assert report.shape_support_policy_frozen
    assert report.estimand_semantics_frozen
    assert not report.valid_training_support_ready
    assert not report.fresh_three_population_preparation_authorized
    assert report.next_permitted_stage == "valid_training_support_repair_only"


def test_runtime_control_failure_is_not_counted_as_boundary_failure() -> None:
    failed_control = "verified_extra_call_cost"
    results = tuple(
        _shape_result(
            shape_id,
            admitted=shape_id != failed_control,
            valid=True,
        )
        for shape_id in sorted(ALL_SHAPES)
    )

    report = _report(results)

    assert report.boundary_candidate_admitted_count == 4
    assert report.boundary_candidate_near_pass_count == 0
    assert report.runtime_control_pass_count == 1
    assert not report.shape_support_policy_frozen
    assert report.next_permitted_stage == "runtime_control_repair_only"


def test_shape_policy_bootstrap_is_deterministic() -> None:
    thresholds = StoppingShapePolicyThresholds(bootstrap_replicates=1_000)
    responses = _task_responses(valid=True)

    first = _stopping_information_bootstrap(responses, thresholds, shape_id="shape:test")
    second = _stopping_information_bootstrap(responses, thresholds, shape_id="shape:test")

    assert first == second
    assert first[0] > 0.0


def test_v25_41_measurement_audit_is_fail_closed() -> None:
    audit = StoppingPredecessorMeasurementAudit(
        rollout_counts={
            "contextual_resolution_choice": 64,
            "single_dimension_conflict": 64,
        },
        runtime_eligible_counts={
            "contextual_resolution_choice": 64,
            "single_dimension_conflict": 64,
        },
        trigger_observed_counts={
            "contextual_resolution_choice": 0,
            "single_dimension_conflict": 0,
        },
        resolution_observed_counts={
            "contextual_resolution_choice": 18,
            "single_dimension_conflict": 12,
        },
        host_event_ordered_counts={
            "contextual_resolution_choice": 0,
            "single_dimension_conflict": 0,
        },
    )
    payload = audit.model_dump(mode="json")
    payload["trigger_observed_counts"]["contextual_resolution_choice"] = 1

    with pytest.raises(ValidationError, match="activation visibility"):
        StoppingPredecessorMeasurementAudit.model_validate(payload)


def test_v25_42_tool_payload_audit_is_fail_closed() -> None:
    audit = StoppingToolPayloadMeasurementAudit(
        rollout_counts={
            "contextual_resolution_choice": 64,
            "single_dimension_conflict": 64,
        },
        completed_counts={
            "contextual_resolution_choice": 22,
            "single_dimension_conflict": 8,
        },
        trigger_observed_counts={
            "contextual_resolution_choice": 54,
            "single_dimension_conflict": 37,
        },
        resolution_observed_counts={
            "contextual_resolution_choice": 29,
            "single_dimension_conflict": 13,
        },
        host_event_ordered_counts={
            "contextual_resolution_choice": 29,
            "single_dimension_conflict": 13,
        },
        tool_payload_schema_failure_counts={
            "contextual_resolution_choice": 10,
            "single_dimension_conflict": 27,
        },
        reported_runtime_pathology_counts={
            "contextual_resolution_choice": 0,
            "single_dimension_conflict": 0,
        },
    )
    payload = audit.model_dump(mode="json")
    payload["tool_payload_schema_failure_counts"]["single_dimension_conflict"] = 26

    with pytest.raises(ValidationError, match="strict tool-payload"):
        StoppingToolPayloadMeasurementAudit.model_validate(payload)


def test_v25_44_predecessor_content_address_is_fail_closed() -> None:
    payload: dict[str, object] = {
        "schema_version": "fixture.v1",
        "value": 7,
    }
    payload["protocol_id"] = canonical_hash(
        payload, prefix="finance_stopping_shape_policy_protocol:"
    )

    assert _artifact_identity_matches(
        payload,
        identity_field="protocol_id",
        prefix="finance_stopping_shape_policy_protocol:",
    )
    payload["value"] = 8
    assert not _artifact_identity_matches(
        payload,
        identity_field="protocol_id",
        prefix="finance_stopping_shape_policy_protocol:",
    )


def _v25_43_role_position_audit() -> StoppingRolePositionPredecessorAudit:
    return StoppingRolePositionPredecessorAudit(
        role_task_counts={
            "contextual_resolution_choice": {"required_1": 4, "required_2": 4},
            "single_dimension_conflict": {"required_1": 4, "required_3": 4},
        },
        role_stopping_probability_vectors={
            "contextual_resolution_choice": {
                "required_1": (0.875, 1.0, 1.0, 1.0),
                "required_2": (0.0, 0.25, 0.25, 0.375),
            },
            "single_dimension_conflict": {
                "required_1": (0.625, 0.75, 1.0, 1.0),
                "required_3": (0.125, 0.625, 0.625, 0.75),
            },
        },
    )


def test_v25_44_role_position_policy_is_prospectively_frozen() -> None:
    audit = _v25_43_role_position_audit()

    assert audit.measurement_valid
    assert audit.selected_target_role_ids == TARGET_ROLE_ID_BY_SHAPE
    assert TARGET_ROLE_ID_BY_SHAPE == {
        "contextual_resolution_choice": "required_2",
        "single_dimension_conflict": "required_3",
    }


def test_v25_44_role_position_audit_is_fail_closed() -> None:
    payload = _v25_43_role_position_audit().model_dump(mode="json")
    payload["role_stopping_probability_vectors"]["single_dimension_conflict"]["required_3"][0] = (
        0.25
    )

    with pytest.raises(ValidationError, match="response vectors"):
        StoppingRolePositionPredecessorAudit.model_validate(payload)
