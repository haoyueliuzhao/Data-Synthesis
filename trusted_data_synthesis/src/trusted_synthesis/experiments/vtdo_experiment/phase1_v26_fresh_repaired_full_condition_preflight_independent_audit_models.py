# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_repaired_full_condition_preflight_independent_audit.v1"
CONSUMED_STAGE: Final = (
    "fresh_repaired_action_interface_full_condition_integration_preflight_independent_audit_only"
)
BLOCKED_DECISION: Final = (
    "v26_206_independent_audit_failed_at_future_online_runner_"
    "repair_request_transport_no_bypass_closure"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


def make_identity(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: identity(provisional, field, prefix)}, **values)


class ExternalIndependentAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    audit_sha256: Literal["c305d4092220fd02344051690445f885ae3139c25134d61be1513cfeb826677f"]
    audit_byte_count: Literal[12167] = 12_167
    audited_experiment: Literal["Finance v26.206"] = "Finance v26.206"
    audit_decision: Literal["PASS_AS_SCOPED"] = "PASS_AS_SCOPED"
    mandatory_revision_required: Literal[False] = False
    independent_audit_required: Literal[True] = True
    only_authorized_successor: Literal[
        "fresh_repaired_action_interface_full_condition_integration_preflight_"
        "independent_audit_only"
    ] = CONSUMED_STAGE
    source_level_no_bypass_primary_audit_object: Literal[True] = True
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    online_execution_authorization_creation_authorized: Literal[False] = False
    full_repaired_192_job_execution_authorized: Literal[False] = False
    qa_mapper_state_frequency_contribution_vtdo_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalIndependentAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_207_external_independent_audit_authorization:",
        ):
            raise ValueError("v26.207 external independent Audit Authorization identity differs")
        return self


class V206PreflightFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    v206_report_id: str = Field(min_length=1)
    v206_transition_id: str = Field(min_length=1)
    v206_gate_audit_id: str = Field(min_length=1)
    v206_callsite_census_id: str = Field(min_length=1)
    v206_scripted_integration_audit_id: str = Field(min_length=1)
    v206_manifest_id: str = Field(min_length=1)
    v206_runner_id: str = Field(min_length=1)
    v206_execution_contract_id: str = Field(min_length=1)
    v206_estimand_contract_id: str = Field(min_length=1)
    v206_artifact_manifest_id: str = Field(min_length=1)
    v206_artifact_root: str = Field(min_length=1)
    v206_source_commit: Literal["0266bfc027ee6ef74f4d8b3a8762ebf7cdeeccb2"]
    v206_source_tree: Literal["98afacbad5b4af207dc00d851a9937d81ce0b9f5"]
    formal_file_count: Literal[17] = 17
    formal_total_byte_count: Literal[2519097] = 2_519_097
    manifest_member_count: Literal[16] = 16
    manifest_member_total_byte_count: Literal[2516326] = 2_516_326
    manifest_path_match_count: Literal[16] = 16
    manifest_sha256_match_count: Literal[16] = 16
    manifest_byte_count_match_count: Literal[16] = 16
    historical_mutation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V206PreflightFreeze:
        if self.freeze_id != identity(
            self,
            "freeze_id",
            "finance_v26_207_v206_preflight_freeze:",
        ):
            raise ValueError("v26.207 v26.206 Preflight Freeze identity differs")
        return self


class DetachedSourceRebuildAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    exact_source_commit: Literal["0266bfc027ee6ef74f4d8b3a8762ebf7cdeeccb2"]
    exact_source_tree: Literal["98afacbad5b4af207dc00d851a9937d81ce0b9f5"]
    archive_commit_match: Literal[True] = True
    archive_tree_match: Literal[True] = True
    detached_execution_exit_code: Literal[0] = 0
    rebuilt_file_count: Literal[17] = 17
    expected_file_count: Literal[17] = 17
    path_match_count: Literal[17] = 17
    sha256_match_count: Literal[17] = 17
    byte_count_match_count: Literal[17] = 17
    actual_byte_match_count: Literal[17] = 17
    rebuilt_total_byte_count: Literal[2519097] = 2_519_097
    saved_report_used_as_outcome_oracle: Literal[False] = False
    saved_census_used_as_outcome_oracle: Literal[False] = False
    saved_integration_used_as_outcome_oracle: Literal[False] = False
    saved_gate_used_as_outcome_oracle: Literal[False] = False
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DetachedSourceRebuildAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_207_detached_source_rebuild_audit:",
        ):
            raise ValueError("v26.207 detached Source Rebuild Audit identity differs")
        return self


class IndependentParentReconstructionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    reconstructed_repair_profile_id: str = Field(min_length=1)
    reconstructed_package_catalog_id: str = Field(min_length=1)
    reconstructed_manifest_id: str = Field(min_length=1)
    reconstructed_runner_id: str = Field(min_length=1)
    reconstructed_execution_contract_id: str = Field(min_length=1)
    source_package_count: Literal[32] = 32
    reconstructed_package_count: Literal[32] = 32
    source_package_canonical_match_count: Literal[32] = 32
    reconstructed_package_object_match_count: Literal[32] = 32
    source_job_count: Literal[192] = 192
    reconstructed_job_count: Literal[192] = 192
    source_job_canonical_match_count: Literal[192] = 192
    reconstructed_job_object_match_count: Literal[192] = 192
    package_catalog_object_match: Literal[True] = True
    manifest_object_match: Literal[True] = True
    runner_object_match: Literal[True] = True
    execution_contract_object_match: Literal[True] = True
    package_replica_cell_count: Literal[192] = 192
    unique_namespace_count: Literal[768] = 768
    predecessor_identity_collision_count: Literal[0] = 0
    saved_parent_objects_used_as_construction_inputs: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentParentReconstructionAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_207_independent_parent_reconstruction_audit:",
        ):
            raise ValueError("v26.207 independent Parent Reconstruction Audit identity differs")
        return self


class SourceRouteNoBypassAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    exact_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    preflight_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    repaired_message_compiler_definition_count: Literal[1] = 1
    callsite_builder_definition_count: Literal[1] = 1
    scripted_integration_definition_count: Literal[1] = 1
    repaired_message_compiler_call_count_in_callsite_builder: Literal[1] = 1
    request_builder_call_count_in_callsite_builder: Literal[1] = 1
    callsite_builder_call_count_in_scripted_integration: Literal[3] = 3
    registered_action_correction_callsite_count: Literal[600] = 600
    registered_action_correction_repair_match_count: Literal[600] = 600
    direct_provider_constructor_call_count: Literal[0] = 0
    direct_provider_request_call_count: Literal[0] = 0
    old_response_abi_route_count: Literal[0] = 0
    unrepaired_registered_action_correction_route_count: Literal[0] = 0
    executable_future_runner_definition_count: Literal[0] = 0
    injected_transport_seam_definition_count: Literal[0] = 0
    action_transport_dispatch_call_count: Literal[0] = 0
    correction_transport_dispatch_call_count: Literal[0] = 0
    future_model_selected_accepted_prefix_route_materialized: Literal[False] = False
    registered_callsite_surface_no_bypass: Literal[True] = True
    future_online_route_no_bypass_proved: Literal[False] = False
    all_model_reachable_states_enumerated_claimed: Literal[False] = False
    first_unclosed_seam: Literal[
        "executable_future_runner_repair_request_validation_transport_route_absent"
    ] = "executable_future_runner_repair_request_validation_transport_route_absent"
    gate_passed: Literal[False] = False
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> SourceRouteNoBypassAudit:
        if self.future_online_route_no_bypass_proved or self.gate_passed:
            raise ValueError("v26.207 source route Audit falsely closes the absent future Runner")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_207_source_route_no_bypass_audit:",
        ):
            raise ValueError("v26.207 Source Route No-Bypass Audit identity differs")
        return self


PromptPhase = Literal["first_action", "subsequent_action", "correction", "final"]


class IndependentCallsiteRow(FrozenModel):
    row_id: str = Field(min_length=1)
    source_coordinate_id: str = Field(min_length=1)
    source_v194_job_id: str = Field(min_length=1)
    fresh_job_id: str = Field(min_length=1)
    phase: PromptPhase
    rebuilt_v206_callsite_row_id: str = Field(min_length=1)
    rebuilt_prompt_id: str = Field(min_length=1)
    rebuilt_request_id: str = Field(min_length=1)
    canonical_message_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dynamic_state_exact: Literal[True] = True
    dynamic_candidate_set_and_order_exact: Literal[True] = True
    saved_row_object_match: Literal[True] = True
    saved_prompt_id_match: Literal[True] = True
    saved_request_id_match: Literal[True] = True
    saved_row_used_as_construction_input: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> IndependentCallsiteRow:
        if self.row_id != identity(
            self,
            "row_id",
            "finance_v26_207_independent_callsite_row:",
        ):
            raise ValueError("v26.207 independent Callsite Row identity differs")
        return self


class IndependentCallsiteReconstructionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    route_audit_id: str = Field(min_length=1)
    rows: tuple[IndependentCallsiteRow, ...] = Field(min_length=792, max_length=792)
    exact_job_count: Literal[192] = 192
    exact_callsite_count: Literal[792] = 792
    unique_independent_row_count: Literal[792] = 792
    unique_rebuilt_v206_row_count: Literal[792] = 792
    first_action_count: Literal[192] = 192
    subsequent_action_count: Literal[288] = 288
    correction_count: Literal[120] = 120
    final_count: Literal[192] = 192
    action_contract_compile_count: Literal[600] = 600
    final_grammar_binding_count: Literal[192] = 192
    saved_row_object_match_count: Literal[792] = 792
    saved_prompt_id_match_count: Literal[792] = 792
    saved_request_id_match_count: Literal[792] = 792
    independently_rebuilt_census_object_match: Literal[True] = True
    maximum_repaired_message_byte_count: Literal[34404] = 34_404
    maximum_repaired_request_body_byte_count: Literal[34565] = 34_565
    parser_relaxation_count: Literal[0] = 0
    historical_adaptation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentCallsiteReconstructionAudit:
        if len({item.row_id for item in self.rows}) != 792:
            raise ValueError("v26.207 independent Callsite Audit repeats a row")
        if len({item.rebuilt_v206_callsite_row_id for item in self.rows}) != 792:
            raise ValueError("v26.207 rebuilt v26.206 Callsite identity denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_207_independent_callsite_reconstruction_audit:",
        ):
            raise ValueError("v26.207 independent Callsite Reconstruction Audit identity differs")
        return self


class IndependentReplayRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    source_v194_job_id: str = Field(min_length=1)
    callsite_count: int = Field(ge=2, le=9)
    correction_count: int = Field(ge=0, le=4)
    rebuilt_raw_id: str = Field(min_length=1)
    rebuilt_result_id: str = Field(min_length=1)
    rebuilt_trace_id: str = Field(min_length=1)
    rebuilt_outcome_id: str = Field(min_length=1)
    terminal_state_reached: Literal[True] = True
    final_abi_valid: Literal[True] = True
    base_valid: Literal[True] = True
    mechanism_valid: Literal[True] = True
    qualified_valid: Literal[True] = True
    raw_result_trace_outcome_parent_closure: Literal[True] = True
    saved_integration_row_id: str = Field(min_length=1)
    saved_integration_row_object_match: Literal[True] = True
    saved_row_used_as_construction_input: Literal[False] = False
    empirical: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> IndependentReplayRow:
        if self.row_id != identity(
            self,
            "row_id",
            "finance_v26_207_independent_replay_row:",
        ):
            raise ValueError("v26.207 independent Replay Row identity differs")
        return self


class IndependentScriptedReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    callsite_reconstruction_audit_id: str = Field(min_length=1)
    rows: tuple[IndependentReplayRow, ...] = Field(min_length=192, max_length=192)
    exact_job_count: Literal[192] = 192
    first_action_parse_count: Literal[192] = 192
    subsequent_action_parse_count: Literal[288] = 288
    typed_rejection_branch_count: Literal[120] = 120
    correction_parse_count: Literal[120] = 120
    final_parse_count: Literal[192] = 192
    terminal_state_count: Literal[192] = 192
    independent_validity_count: Literal[192] = 192
    qualified_control_count: Literal[192] = 192
    unique_evidence_layer_identity_count: Literal[768] = 768
    saved_integration_row_object_match_count: Literal[192] = 192
    independently_rebuilt_integration_object_match: Literal[True] = True
    exception_escape_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentScriptedReplayAudit:
        if len({item.job_id for item in self.rows}) != 192:
            raise ValueError("v26.207 independent Replay Job denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_207_independent_scripted_replay_audit:",
        ):
            raise ValueError("v26.207 independent Scripted Replay Audit identity differs")
        return self


class IndependentFailureControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: Literal[
        "invalid_first_action_abi",
        "unknown_action_reference",
        "invalid_correction_abi",
        "invalid_final_abi",
        "typed_outer_terminal",
    ]
    expected_terminal: str = Field(min_length=1)
    observed_terminal: str = Field(min_length=1)
    parser_or_projection_executed: Literal[True] = True
    typed_outcome_count: Literal[1] = 1
    task_verifier_invoked: Literal[False] = False
    exception_escape_count: Literal[0] = 0
    saved_control_object_match: Literal[True] = True
    saved_control_used_as_construction_input: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> IndependentFailureControl:
        if self.expected_terminal != self.observed_terminal:
            raise ValueError("v26.207 independent Failure Control terminal differs")
        if self.control_id != identity(
            self,
            "control_id",
            "finance_v26_207_independent_failure_control:",
        ):
            raise ValueError("v26.207 independent Failure Control identity differs")
        return self


class IndependentFailureControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    controls: tuple[IndependentFailureControl, ...] = Field(min_length=5, max_length=5)
    control_count: Literal[5] = 5
    typed_outcome_count: Literal[5] = 5
    saved_control_object_match_count: Literal[5] = 5
    exception_escape_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentFailureControlAudit:
        if len({item.control_name for item in self.controls}) != 5:
            raise ValueError("v26.207 independent Failure Control denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_207_independent_failure_control_audit:",
        ):
            raise ValueError("v26.207 independent Failure Control Audit identity differs")
        return self


class EstimandResourceBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    reconstructed_estimand_contract_id: str = Field(min_length=1)
    exact_denominator: Literal[192] = 192
    pre_action_abi_terminal_counts_as_false: Literal[True] = True
    outer_terminal_remains_in_denominator: Literal[True] = True
    post_action_abi_conditional_null_when_denominator_zero: Literal[True] = True
    q_first_numerator: None = None
    q_bounded_correction_numerator: None = None
    q_first_estimate: None = None
    q_bounded_correction_estimate: None = None
    confidence_intervals: None = None
    saved_estimand_contract_object_match: Literal[True] = True
    maximum_primary_requests: Literal[21] = 21
    maximum_provider_calls: Literal[23] = 23
    maximum_transport_invocations: Literal[24] = 24
    maximum_rollout_tokens: Literal[1120000] = 1_120_000
    maximum_prompt_utf8_bytes: Literal[60000] = 60_000
    observed_maximum_repaired_message_bytes: Literal[34404] = 34_404
    observed_maximum_repaired_request_bytes: Literal[34565] = 34_565
    resource_bound_violation_count: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    qa_rows: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> EstimandResourceBoundaryAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_207_estimand_resource_boundary_audit:",
        ):
            raise ValueError("v26.207 Estimand/Resource Boundary Audit identity differs")
        return self


class IndependentAuditGateEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    detached_rebuild_audit_id: str = Field(min_length=1)
    parent_reconstruction_audit_id: str = Field(min_length=1)
    route_no_bypass_audit_id: str = Field(min_length=1)
    callsite_reconstruction_audit_id: str = Field(min_length=1)
    scripted_replay_audit_id: str = Field(min_length=1)
    failure_control_audit_id: str = Field(min_length=1)
    boundary_audit_id: str = Field(min_length=1)
    a0_authority_and_predecessor_freeze_passed: Literal[True] = True
    a1_detached_source_and_artifact_byte_rebuild_passed: Literal[True] = True
    a2_independent_fresh_parent_reconstruction_passed: Literal[True] = True
    a3_source_level_repair_request_transport_no_bypass_passed: Literal[False] = False
    a4_independent_scripted_replay_and_failure_controls_passed: Literal[True] = True
    a5_estimand_resource_boundary_and_zero_provider_passed: Literal[True] = True
    passed_gate_count: Literal[5] = 5
    failed_gate_count: Literal[1] = 1
    all_gates_passed: Literal[False] = False
    online_execution_authorization_ready: Literal[False] = False
    capability_estimate: None = None
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evaluation(self) -> IndependentAuditGateEvaluation:
        if self.evaluation_id != identity(
            self,
            "evaluation_id",
            "finance_v26_207_independent_audit_gate_evaluation:",
        ):
            raise ValueError("v26.207 independent Audit Gate Evaluation identity differs")
        return self


class IndependentAuditDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    route_no_bypass_audit_id: str = Field(min_length=1)
    decision: Literal[
        "v26_206_independent_audit_failed_at_future_online_runner_"
        "repair_request_transport_no_bypass_closure"
    ] = BLOCKED_DECISION
    v206_registered_callsite_result: Literal["independently_reconstructed_and_accepted"] = (
        "independently_reconstructed_and_accepted"
    )
    v206_scripted_runtime_result: Literal["independently_reconstructed_and_accepted"] = (
        "independently_reconstructed_and_accepted"
    )
    v206_scripted_outcome_parent_result: Literal["independently_reconstructed_and_accepted"] = (
        "independently_reconstructed_and_accepted"
    )
    future_online_runner_no_bypass_result: Literal["unclosed_absent_executable_route"] = (
        "unclosed_absent_executable_route"
    )
    v206_historical_artifact_mutation_count: Literal[0] = 0
    empirical_capability_materialized: Literal[False] = False
    online_execution_authorization_issued: Literal[False] = False
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> IndependentAuditDecision:
        if self.decision_id != identity(
            self,
            "decision_id",
            "finance_v26_207_independent_audit_decision:",
        ):
            raise ValueError("v26.207 independent Audit Decision identity differs")
        return self


class BlockedTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    current_status: Literal["BLOCKED_FAILED_INDEPENDENT_AUDIT"] = "BLOCKED_FAILED_INDEPENDENT_AUDIT"
    next_stage: None = None
    new_external_audit_decision_required: Literal[True] = True
    recommended_candidate_successor: Literal[
        "fresh_repaired_full_condition_executable_runner_route_closure_preflight_only"
    ] = "fresh_repaired_full_condition_executable_runner_route_closure_preflight_only"
    recommended_candidate_is_authorized: Literal[False] = False
    online_execution_authorization_authorized: Literal[False] = False
    full_repaired_192_job_execution_authorized: Literal[False] = False
    provider_calls_authorized: Literal[0] = 0
    qa_mapper_state_frequency_contribution_vtdo_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> BlockedTransition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_207_blocked_transition:",
        ):
            raise ValueError("v26.207 blocked Transition identity differs")
        return self


class SourceIdentity(FrozenModel):
    source_identity_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    implementation_files: tuple[str, ...] = Field(min_length=3)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_source(self) -> SourceIdentity:
        if tuple(sorted(set(self.implementation_files))) != self.implementation_files:
            raise ValueError("v26.207 source file vector differs")
        if self.source_identity_id != identity(
            self,
            "source_identity_id",
            "finance_v26_207_source_identity:",
        ):
            raise ValueError("v26.207 Source Identity differs")
        return self


class IndependentAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    detached_rebuild_audit_id: str = Field(min_length=1)
    parent_reconstruction_audit_id: str = Field(min_length=1)
    route_no_bypass_audit_id: str = Field(min_length=1)
    callsite_reconstruction_audit_id: str = Field(min_length=1)
    scripted_replay_audit_id: str = Field(min_length=1)
    failure_control_audit_id: str = Field(min_length=1)
    boundary_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    decision: Literal[
        "v26_206_independent_audit_failed_at_future_online_runner_"
        "repair_request_transport_no_bypass_closure"
    ] = BLOCKED_DECISION
    formal_scope_completed: Literal[True] = True
    independent_audit_passed: Literal[False] = False
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> IndependentAuditReport:
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_207_independent_audit_report:",
        ):
            raise ValueError("v26.207 independent Audit Report identity differs")
        return self


class ArtifactMember(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class ArtifactManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    members: tuple[ArtifactMember, ...] = Field(min_length=1)
    file_count: int = Field(gt=0)
    total_byte_count: int = Field(gt=0)
    artifact_root: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> ArtifactManifest:
        if tuple(item.relative_path for item in self.members) != tuple(
            sorted(item.relative_path for item in self.members)
        ):
            raise ValueError("v26.207 Artifact Manifest member order differs")
        if len({item.relative_path for item in self.members}) != len(self.members):
            raise ValueError("v26.207 Artifact Manifest repeats a path")
        if self.file_count != len(self.members):
            raise ValueError("v26.207 Artifact Manifest file count differs")
        if self.total_byte_count != sum(item.byte_count for item in self.members):
            raise ValueError("v26.207 Artifact Manifest byte count differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_207_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("v26.207 Artifact Root differs")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            "finance_v26_207_artifact_manifest:",
        ):
            raise ValueError("v26.207 Artifact Manifest identity differs")
        return self


def artifact_manifest(run_id: str, payloads: dict[str, bytes]) -> ArtifactManifest:
    members = tuple(
        ArtifactMember(
            relative_path=name,
            sha256=hashlib.sha256(payload).hexdigest(),
            byte_count=len(payload),
        )
        for name, payload in sorted(payloads.items())
    )
    root = canonical_hash(
        tuple(item.model_dump(mode="json") for item in members),
        prefix="finance_v26_207_artifact_root:",
    )
    return cast(
        ArtifactManifest,
        make_identity(
            ArtifactManifest,
            {
                "run_id": run_id,
                "members": members,
                "file_count": len(members),
                "total_byte_count": sum(item.byte_count for item in members),
                "artifact_root": root,
            },
            field="manifest_id",
            prefix="finance_v26_207_artifact_manifest:",
        ),
    )
