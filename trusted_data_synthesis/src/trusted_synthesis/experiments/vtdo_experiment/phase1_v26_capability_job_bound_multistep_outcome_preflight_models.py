from __future__ import annotations

from typing import Any, Final, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.job_bound_multistep_outcome import (
    CapabilityDevelopmentJobManifest,
    FrozenGenerationProfile,
    JobBoundMultistepOutcomeContract,
    JobBoundRunnerContract,
    ScriptedPreflightOutcomeRow,
)
from trusted_synthesis.hashing import canonical_hash

V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION: Final = (
    "capability_job_bound_multistep_outcome_runner_preflight.v1"
)
AUTHORIZED_STAGE: Final = (
    "capability_observation_job_bound_multistep_outcome_contract_and_192_job_runner_preflight_only"
)
BLOCKED_PREDECESSOR_STAGE: Final = "no_further_experiment_authorized_without_new_audit_decision"
NEXT_STAGE: Final = (
    "capability_observation_job_bound_multistep_outcome_192_job_"
    "runner_preflight_independent_audit_only"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


def make_identity_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: identity(provisional, field, prefix)}, **values)


class FileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(ge=1)
    source_kind: Literal[
        "external_audit_input",
        "implementation_source",
        "predecessor_artifact",
        "formal_output",
        "frozen_generation_parent",
    ]


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_byte_count: int = Field(ge=1)
    audited_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    authorized_stage: str = AUTHORIZED_STAGE
    provider_calls_authorized: Literal[False] = False
    development_model_outcomes_authorized: Literal[False] = False
    sealed_confirmation_access_authorized: Literal[False] = False
    mapper_state_frequency_authorized: Literal[False] = False
    schema_version: str = V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.authorized_stage != AUTHORIZED_STAGE:
            raise ValueError("v26.179 Authorization stage changed")
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_job_bound_outcome_external_authorization:",
        ):
            raise ValueError("v26.179 external Authorization identity is invalid")
        return self


class V178PredecessorFreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    predecessor_outcome_contract_id: str = Field(min_length=1)
    predecessor_files: tuple[FileBinding, ...] = Field(min_length=14, max_length=14)
    predecessor_file_count: Literal[14] = 14
    independent_rebuild_match_count: Literal[14] = 14
    predecessor_mutation_count: Literal[0] = 0
    predecessor_decision: str = BLOCKED_PREDECESSOR_STAGE
    new_audit_decision_required_and_bound: Literal[True] = True
    schema_version: str = V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V178PredecessorFreezeAudit:
        if len(self.predecessor_files) != self.predecessor_file_count:
            raise ValueError("v26.178 predecessor Freeze denominator changed")
        if self.predecessor_decision != BLOCKED_PREDECESSOR_STAGE:
            raise ValueError("v26.178 predecessor decision changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v178_predecessor_freeze_audit:",
        ):
            raise ValueError("v26.178 predecessor Freeze identity is invalid")
        return self


class V178ScopeNarrowingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    old_report_id: str = Field(min_length=1)
    old_title: Literal["Executed Counterfactual, Valid Control, And Outcome Row Closure"] = (
        "Executed Counterfactual, Valid Control, And Outcome Row Closure"
    )
    strongest_outcome_interpretation: Literal[
        "outcome_payload_fixture_and_denominator_geometry_closure"
    ] = "outcome_payload_fixture_and_denominator_geometry_closure"
    exact_scan_interpretation: Literal[
        "complete_reference_prefix_component_candidate_acceptance_scan"
    ] = "complete_reference_prefix_component_candidate_acceptance_scan"
    reference_prefix_state_count: Literal[480] = 480
    displayed_candidate_count: Literal[1356] = 1_356
    local_outcome_fixture_count: Literal[5] = 5
    exact_future_job_identity_count: Literal[0] = 0
    empirical_outcome_row_count: Literal[0] = 0
    multi_component_correction_row_count: Literal[0] = 0
    historical_artifact_rewrite_count: Literal[0] = 0
    historical_reclassification_count: Literal[0] = 0
    schema_version: str = V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V178ScopeNarrowingAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v178_outcome_scope_narrowing_audit:",
        ):
            raise ValueError("v26.178 scope-narrowing Audit identity is invalid")
        return self


class GenerationProfileBindingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    profile: FrozenGenerationProfile
    source_catalog_binding: FileBinding
    source_nuisance_signature_count: Literal[8] = 8
    unique_generation_configuration_count: Literal[1] = 1
    action_grammar_compile_match: Literal[True] = True
    final_grammar_compile_match: Literal[True] = True
    fixed_generation_condition_count: Literal[1] = 1
    model_or_thinking_change_count: Literal[0] = 0
    grammar_change_count: Literal[0] = 0
    policy_or_resource_change_count: Literal[0] = 0
    schema_version: str = V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> GenerationProfileBindingAudit:
        if len(self.profile.source_nuisance_signature_ids) != self.source_nuisance_signature_count:
            raise ValueError("generation profile source denominator changed")
        if self.source_catalog_binding.source_kind != "frozen_generation_parent":
            raise ValueError("generation profile lacks its exact frozen source artifact")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_job_bound_generation_profile_binding_audit:",
        ):
            raise ValueError("generation profile Binding Audit identity is invalid")
        return self


class ExactJobSetAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    package_count: Literal[32] = 32
    replica_count: Literal[6] = 6
    job_count: Literal[192] = 192
    unique_job_id_count: Literal[192] = 192
    unique_raw_namespace_count: Literal[192] = 192
    unique_result_namespace_count: Literal[192] = 192
    package_replica_cell_count: Literal[192] = 192
    packages_with_exact_six_replicas: Literal[32] = 32
    missing_job_count: Literal[0] = 0
    duplicate_job_count: Literal[0] = 0
    extra_job_count: Literal[0] = 0
    source_runner_parent_match_count: Literal[192] = 192
    source_package_parent_match_count: Literal[192] = 192
    generation_profile_parent_match_count: Literal[192] = 192
    outcome_contract_parent_match_count: Literal[192] = 192
    schema_version: str = V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ExactJobSetAudit:
        if self.package_count * self.replica_count != self.job_count:
            raise ValueError("exact Job-set denominator geometry changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_exact_192_job_set_audit:",
        ):
            raise ValueError("exact Job-set Audit identity is invalid")
        return self


class AcceptedPrefixSurfaceRow(FrozenModel):
    row_id: str = Field(min_length=1)
    runner_package_id: str = Field(min_length=1)
    component_key: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    accepted_prefix_count: int = Field(ge=1)
    reached_state_token_count: int = Field(ge=1)
    acceptance_signature_count: int = Field(ge=1)
    candidate_evaluation_count: int = Field(ge=1)
    typed_rejection_count: int = Field(ge=0)
    schema_version: str = V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> AcceptedPrefixSurfaceRow:
        if self.row_id != identity(
            self,
            "row_id",
            "capability_accepted_prefix_surface_row:",
        ):
            raise ValueError("accepted-prefix Surface row identity is invalid")
        return self


class AcceptedPrefixSurfaceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    package_count: Literal[32] = 32
    source_choice_combination_count: Literal[772] = 772
    replica_execution_count: Literal[4632] = 4_632
    rows: tuple[AcceptedPrefixSurfaceRow, ...] = Field(min_length=480, max_length=480)
    package_component_replica_row_count: Literal[480] = 480
    reached_prefix_state_count: int = Field(ge=480)
    candidate_evaluation_count: int = Field(ge=1_356)
    accepted_action_count: int = Field(ge=1)
    typed_rejection_count: int = Field(ge=120)
    acceptance_signature_invariant_row_count: Literal[480] = 480
    history_dependent_acceptance_row_count: Literal[0] = 0
    runtime_exception_count: Literal[0] = 0
    reference_trace_input_count: Literal[0] = 0
    precommitted_choice_vector_runner_input_count: Literal[0] = 0
    complete_baseline_load_count: Literal[0] = 0
    scan_interpretation: Literal[
        "all_declared_choice_vectors_under_every_accepted_predecessor_prefix"
    ] = "all_declared_choice_vectors_under_every_accepted_predecessor_prefix"
    schema_version: str = V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> AcceptedPrefixSurfaceAudit:
        if len(self.rows) != self.package_component_replica_row_count:
            raise ValueError("accepted-prefix Surface row denominator changed")
        if len(
            {(item.runner_package_id, item.component_key, item.replica_index) for item in self.rows}
        ) != len(self.rows):
            raise ValueError("accepted-prefix Surface repeats a Package Component Replica row")
        invariant = sum(item.acceptance_signature_count == 1 for item in self.rows)
        if invariant != self.acceptance_signature_invariant_row_count:
            raise ValueError("accepted-prefix acceptance depends on predecessor history")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_accepted_prefix_action_surface_audit:",
        ):
            raise ValueError("accepted-prefix Surface Audit identity is invalid")
        return self


class ScriptedDenominatorPreflightAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    rows: tuple[ScriptedPreflightOutcomeRow, ...] = Field(min_length=192, max_length=192)
    row_count: Literal[192] = 192
    unique_row_id_count: Literal[192] = 192
    unique_job_id_count: Literal[192] = 192
    exact_job_set_match_count: Literal[192] = 192
    current_prompt_render_count: Literal[480] = 480
    action_abi_parse_count: Literal[480] = 480
    accepted_action_count: Literal[480] = 480
    final_abi_parse_count: Literal[192] = 192
    finalized_runtime_result_count: Literal[192] = 192
    first_policy_qualified_control_count: Literal[192] = 192
    bounded_policy_qualified_control_count: Literal[192] = 192
    component_correction_count: Literal[0] = 0
    empirical_outcome_row_count: Literal[0] = 0
    empirical_estimand_evaluation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    reference_trace_input_count: Literal[0] = 0
    precommitted_choice_vector_input_count: Literal[0] = 0
    future_prompt_materialization_count: Literal[0] = 0
    complete_baseline_load_count: Literal[0] = 0
    saved_replica_result_oracle_read_count: Literal[0] = 0
    schema_version: str = V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ScriptedDenominatorPreflightAudit:
        if len(self.rows) != self.row_count:
            raise ValueError("scripted denominator Outcome row count changed")
        if len({item.row_id for item in self.rows}) != self.unique_row_id_count:
            raise ValueError("scripted denominator repeats an Outcome row")
        if len({item.job_id for item in self.rows}) != self.unique_job_id_count:
            raise ValueError("scripted denominator repeats a Job")
        if any(
            not item.exact_manifest_denominator_member
            or item.empirical
            or item.outcome.correction_count != 0
            for item in self.rows
        ):
            raise ValueError("scripted denominator contains a mislabeled Outcome")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_scripted_192_job_denominator_preflight_audit:",
        ):
            raise ValueError("scripted denominator Preflight Audit identity is invalid")
        return self


BranchScenario = Literal[
    "direct_first_attempt_qualified",
    "abi_invalid_first_response",
    "accepted_first_action_downstream_task_invalid",
    "one_component_correction",
    "two_component_corrections",
    "valid_nonreference_correction",
    "same_current_invalid_second_response",
    "different_current_invalid_second_response",
    "stale_action_second_response",
    "foreign_action_second_response",
    "correction_terminal_forbids_third_prompt",
]


class RunnerBranchControlRow(FrozenModel):
    control_id: str = Field(min_length=1)
    scenario: BranchScenario
    source_scope: Literal["exact_manifest", "canonical_diagnostic"]
    source_job_id: str = Field(min_length=1)
    outcome: ScriptedPreflightOutcomeRow
    actual_runtime_initialized: Literal[True] = True
    actual_prompt_render_count: int = Field(ge=1)
    actual_step_call_count: int = Field(ge=0)
    actual_finalize_call_count: int = Field(ge=0, le=1)
    projected_from_actual_trace: Literal[True] = True
    later_prompt_after_terminal_count: Literal[0] = 0
    passed: Literal[True] = True
    schema_version: str = V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> RunnerBranchControlRow:
        if self.scenario == "different_current_invalid_second_response":
            if self.source_scope != "canonical_diagnostic":
                raise ValueError("different-current-invalid control overstates exact reachability")
        elif self.source_scope != "exact_manifest":
            raise ValueError("exact Runner branch is mislabeled diagnostic")
        if self.outcome.exact_manifest_denominator_member or self.outcome.empirical:
            raise ValueError("Runner branch control entered the empirical denominator")
        if self.control_id != identity(
            self,
            "control_id",
            "capability_job_bound_runner_branch_control:",
        ):
            raise ValueError("Runner branch Control identity is invalid")
        return self


class RunnerBranchControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    rows: tuple[RunnerBranchControlRow, ...] = Field(min_length=11, max_length=11)
    scenario_count: Literal[11] = 11
    exact_manifest_scenario_count: Literal[10] = 10
    canonical_diagnostic_scenario_count: Literal[1] = 1
    direct_success_count: Literal[1] = 1
    abi_invalid_first_response_count: Literal[1] = 1
    accepted_downstream_invalid_count: Literal[1] = 1
    one_component_correction_count: Literal[1] = 1
    two_component_correction_count: Literal[1] = 1
    valid_nonreference_correction_count: Literal[1] = 1
    invalid_second_response_terminal_count: Literal[4] = 4
    terminal_third_prompt_rejection_count: Literal[1] = 1
    empirical_outcome_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerBranchControlAudit:
        if len(self.rows) != self.scenario_count:
            raise ValueError("Runner branch Control denominator changed")
        if {item.scenario for item in self.rows} != set(get_args(BranchScenario)):
            raise ValueError("Runner branch Control scenario surface is incomplete")
        if sum(item.source_scope == "exact_manifest" for item in self.rows) != (
            self.exact_manifest_scenario_count
        ):
            raise ValueError("Runner branch exact/diagnostic partition changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_job_bound_runner_branch_control_audit:",
        ):
            raise ValueError("Runner branch Control Audit identity is invalid")
        return self


class EmpiricalOutcomeSchemaAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    empirical_row_type: Literal["EmpiricalCapabilityOutcomeRow"] = "EmpiricalCapabilityOutcomeRow"
    required_parent_fields: tuple[str, ...] = Field(min_length=9)
    component_attempt_field_count: int = Field(ge=20)
    exact_job_set_estimator_required: Literal[True] = True
    raw_and_result_identity_required: Literal[True] = True
    fixture_row_accepted_by_empirical_estimator: Literal[False] = False
    duplicate_job_denominator_accepted: Literal[False] = False
    abi_invalid_accepted_action_constructible: Literal[False] = False
    multicomponent_correction_constructible: Literal[True] = True
    empirical_row_count: Literal[0] = 0
    empirical_estimate_count: Literal[0] = 0
    schema_version: str = V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> EmpiricalOutcomeSchemaAudit:
        if len(set(self.required_parent_fields)) != len(self.required_parent_fields):
            raise ValueError("Empirical Outcome schema repeats a required parent")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_empirical_job_bound_outcome_schema_audit:",
        ):
            raise ValueError("Empirical Outcome Schema Audit identity is invalid")
        return self


class DestructiveMutation(FrozenModel):
    mutation: str = Field(min_length=1)
    surface: Literal[
        "manifest",
        "component_attempt",
        "outcome_payload",
        "scripted_row",
        "empirical_row",
        "estimand",
        "runner",
        "transition_parent",
    ]
    fully_rehashed: Literal[True] = True
    rejected: Literal[True] = True
    error_code: str = Field(min_length=1)


class ProductionDestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[DestructiveMutation, ...] = Field(min_length=18)
    mutation_count: int = Field(ge=18)
    rejection_count: int = Field(ge=18)
    acceptance_count: Literal[0] = 0
    schema_version: str = V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ProductionDestructiveAudit:
        if self.mutation_count != len(self.mutations):
            raise ValueError("destructive mutation denominator changed")
        if self.rejection_count != self.mutation_count:
            raise ValueError("Job-bound destructive Audit accepted a mutation")
        if len({item.mutation for item in self.mutations}) != len(self.mutations):
            raise ValueError("Job-bound destructive Audit repeats a mutation")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_job_bound_outcome_production_destructive_audit:",
        ):
            raise ValueError("Job-bound destructive Audit identity is invalid")
        return self


class StaticGate(FrozenModel):
    gate: str = Field(min_length=1)
    observed: int = Field(ge=0)
    required: int = Field(ge=0)
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_gate(self) -> StaticGate:
        if self.observed != self.required:
            raise ValueError(f"noncompensatory Gate failed:{self.gate}")
        return self


class StaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGate, ...] = Field(min_length=30)
    gate_count: int = Field(ge=30)
    passed_gate_count: int = Field(ge=30)
    failed_gate_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_2_provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    sealed_confirmation_access_count: Literal[0] = 0
    mapper_calls: Literal[0] = 0
    state_assignment_count: Literal[0] = 0
    frequency_row_count: Literal[0] = 0
    schema_version: str = V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StaticAudit:
        if self.gate_count != len(self.gates) or self.passed_gate_count != self.gate_count:
            raise ValueError("Static Gate denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_job_bound_outcome_static_audit:",
        ):
            raise ValueError("Job-bound Static Audit identity is invalid")
        return self


class TransitiveSourceRoot(FrozenModel):
    root_id: str = Field(min_length=1)
    entry_modules: tuple[str, ...] = Field(min_length=4)
    files: tuple[FileBinding, ...] = Field(min_length=1)
    file_count: int = Field(ge=1)
    unresolved_imports: tuple[str, ...] = ()
    unresolved_import_count: Literal[0] = 0
    schema_version: str = V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_root(self) -> TransitiveSourceRoot:
        if self.file_count != len(self.files):
            raise ValueError("transitive source Root file count changed")
        if len({item.relative_path for item in self.files}) != self.file_count:
            raise ValueError("transitive source Root repeats a file")
        if self.unresolved_imports:
            raise ValueError("transitive source Root contains unresolved imports")
        if self.root_id != identity(
            self,
            "root_id",
            "finance_v26_job_bound_outcome_transitive_source_root:",
        ):
            raise ValueError("transitive source Root identity is invalid")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_root_id: str = Field(min_length=1)
    predecessor_freeze_audit_id: str = Field(min_length=1)
    scope_narrowing_audit_id: str = Field(min_length=1)
    generation_profile_audit_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    exact_job_set_audit_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    accepted_prefix_surface_audit_id: str = Field(min_length=1)
    scripted_denominator_audit_id: str = Field(min_length=1)
    branch_control_audit_id: str = Field(min_length=1)
    empirical_schema_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    consumed_stage: str = AUTHORIZED_STAGE
    blocked_predecessor_stage: str = BLOCKED_PREDECESSOR_STAGE
    next_stage: str = NEXT_STAGE
    provider_execution_authorized: Literal[False] = False
    independent_audit_required_before_execution_decision: Literal[True] = True
    empirical_outcome_row_count: Literal[0] = 0
    schema_version: str = V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if (
            self.consumed_stage != AUTHORIZED_STAGE
            or self.blocked_predecessor_stage != BLOCKED_PREDECESSOR_STAGE
            or self.next_stage != NEXT_STAGE
        ):
            raise ValueError("v26.179 prospective transition boundary changed")
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_job_bound_outcome_preflight_transition:",
        ):
            raise ValueError("v26.179 prospective Transition identity is invalid")
        return self


class PreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_root_id: str = Field(min_length=1)
    predecessor_freeze_audit_id: str = Field(min_length=1)
    scope_narrowing_audit_id: str = Field(min_length=1)
    generation_profile_audit_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    exact_job_set_audit_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    accepted_prefix_surface_audit_id: str = Field(min_length=1)
    scripted_denominator_audit_id: str = Field(min_length=1)
    branch_control_audit_id: str = Field(min_length=1)
    empirical_schema_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    detail_files: tuple[FileBinding, ...] = Field(min_length=1)
    detail_file_count: int = Field(ge=1)
    manifest_count: Literal[1] = 1
    runner_count: Literal[1] = 1
    prospective_job_count: Literal[192] = 192
    scripted_outcome_row_count: Literal[192] = 192
    empirical_outcome_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    next_stage: str = NEXT_STAGE
    schema_version: str = V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> PreflightReport:
        if self.detail_file_count != len(self.detail_files):
            raise ValueError("v26.179 report detail-file count changed")
        if self.next_stage != NEXT_STAGE:
            raise ValueError("v26.179 report next stage changed")
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_job_bound_multistep_outcome_preflight_report:",
        ):
            raise ValueError("v26.179 Preflight Report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    authorization: ExternalAuditAuthorization
    source_root: TransitiveSourceRoot
    predecessor: V178PredecessorFreezeAudit
    scope_narrowing: V178ScopeNarrowingAudit
    generation_profile: GenerationProfileBindingAudit
    outcome_contract: JobBoundMultistepOutcomeContract
    manifest: CapabilityDevelopmentJobManifest
    exact_job_set: ExactJobSetAudit
    runner: JobBoundRunnerContract
    accepted_prefix_surface: AcceptedPrefixSurfaceAudit
    scripted_denominator: ScriptedDenominatorPreflightAudit
    branch_controls: RunnerBranchControlAudit
    empirical_schema: EmpiricalOutcomeSchemaAudit
    destructive: ProductionDestructiveAudit
    static: StaticAudit
    transition: ProspectiveTransition
    report: PreflightReport


__all__ = [
    "AUTHORIZED_STAGE",
    "AcceptedPrefixSurfaceAudit",
    "AcceptedPrefixSurfaceRow",
    "BLOCKED_PREDECESSOR_STAGE",
    "BranchScenario",
    "BuildProducts",
    "DestructiveMutation",
    "EmpiricalOutcomeSchemaAudit",
    "ExactJobSetAudit",
    "ExternalAuditAuthorization",
    "FileBinding",
    "GenerationProfileBindingAudit",
    "NEXT_STAGE",
    "PreflightReport",
    "ProductionDestructiveAudit",
    "ProspectiveTransition",
    "RunnerBranchControlAudit",
    "RunnerBranchControlRow",
    "ScriptedDenominatorPreflightAudit",
    "StaticAudit",
    "StaticGate",
    "TransitiveSourceRoot",
    "V178PredecessorFreezeAudit",
    "V178ScopeNarrowingAudit",
    "V26_JOB_BOUND_OUTCOME_PREFLIGHT_VERSION",
    "identity",
    "make_identity_model",
]
