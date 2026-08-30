from __future__ import annotations

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

V26_OUTCOME_PARENT_TERMINAL_AUDIT_VERSION: Final = (
    "job_bound_outcome_parent_authenticity_terminal_totality_audit.v1"
)
CONSUMED_STAGE: Final = (
    "capability_observation_job_bound_multistep_outcome_192_job_"
    "runner_preflight_independent_audit_only"
)
NEXT_STAGE: Final = (
    "capability_observation_empirical_outcome_authoritative_parent_binding_"
    "and_terminal_totality_preflight_only"
)
FAILED_DECISION: Final = "job_bound_outcome_parent_authenticity_and_terminal_totality_failed"

ParentAttackName = Literal[
    "cross_job_outcome_payload_reassignment",
    "duplicate_raw_execution_id_across_jobs",
    "duplicate_result_id_across_jobs",
    "swapped_raw_and_result_parents",
    "result_parent_outcome_final_mismatch",
    "duplicate_attempt_trace_across_jobs",
]
OuterEndpointKind = Literal[
    "provider_failure_no_payload",
    "provider_transport_failure",
    "privacy_rejection",
    "resource_budget_exhausted",
    "instrument_failure",
    "provider_identity_thinking_usage_failure",
]


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
        "predecessor_artifact",
        "implementation_source",
        "formal_detail",
    ]


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: Literal["f2da2aef728d78964a6c6b0060382f55a91937dc86c029c5cd7b8fdd9f7cdd78"]
    review_byte_count: Literal[22294] = 22_294
    audited_commit: Literal["27ac98d03d078d522cecf7a0cb290230cac63036"]
    consumed_stage: str = CONSUMED_STAGE
    provider_execution_authorized: Literal[False] = False
    development_outcomes_authorized: Literal[False] = False
    independent_negative_audit_required: Literal[True] = True
    schema_version: str = V26_OUTCOME_PARENT_TERMINAL_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.consumed_stage != CONSUMED_STAGE:
            raise ValueError("v26.180 consumed stage changed")
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_job_bound_parent_terminal_external_authorization:",
        ):
            raise ValueError("v26.180 external Authorization identity is invalid")
        return self


class TransitiveSourceRoot(FrozenModel):
    root_id: str = Field(min_length=1)
    entry_modules: tuple[str, ...] = Field(min_length=2)
    files: tuple[FileBinding, ...] = Field(min_length=1)
    file_count: int = Field(ge=1)
    unresolved_imports: tuple[str, ...] = ()
    unresolved_import_count: Literal[0] = 0
    schema_version: str = V26_OUTCOME_PARENT_TERMINAL_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_root(self) -> TransitiveSourceRoot:
        if self.file_count != len(self.files):
            raise ValueError("v26.180 transitive source file count changed")
        if len({item.relative_path for item in self.files}) != self.file_count:
            raise ValueError("v26.180 transitive source Root repeats a file")
        if self.unresolved_imports:
            raise ValueError("v26.180 transitive source Root has unresolved imports")
        if self.root_id != identity(
            self,
            "root_id",
            "finance_v26_job_bound_parent_terminal_transitive_source_root:",
        ):
            raise ValueError("v26.180 transitive source Root identity is invalid")
        return self


class V179PredecessorFreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    predecessor_next_stage: str = CONSUMED_STAGE
    predecessor_files: tuple[FileBinding, ...] = Field(min_length=18, max_length=18)
    predecessor_file_count: Literal[18] = 18
    independent_rebuild_match_count: Literal[18] = 18
    predecessor_mutation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    historical_reclassification_count: Literal[0] = 0
    schema_version: str = V26_OUTCOME_PARENT_TERMINAL_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V179PredecessorFreezeAudit:
        if self.predecessor_next_stage != CONSUMED_STAGE:
            raise ValueError("v26.179 predecessor transition is not the audited stage")
        if len(self.predecessor_files) != self.predecessor_file_count:
            raise ValueError("v26.179 predecessor file denominator changed")
        if len({item.relative_path for item in self.predecessor_files}) != 18:
            raise ValueError("v26.179 predecessor file bindings are not unique")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v179_predecessor_freeze_audit:",
        ):
            raise ValueError("v26.179 predecessor Freeze identity is invalid")
        return self


class V179ClaimScopeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    local_scripted_runner_preflight_retained: Literal[True] = True
    exact_prospective_job_index_set_retained: Literal[True] = True
    multicomponent_correction_representation_retained: Literal[True] = True
    job_level_estimand_definition_retained: Literal[True] = True
    accepted_prefix_coverage_retained: Literal[True] = True
    strongest_estimator_claim: Literal["exact_job_key_set_and_wrapper_parent_estimator_gate"] = (
        "exact_job_key_set_and_wrapper_parent_estimator_gate"
    )
    exact_job_outcome_evidence_set_closed: Literal[False] = False
    empirical_outcome_parent_authenticity_closed: Literal[False] = False
    online_terminal_totality_closed: Literal[False] = False
    online_development_execution_authorized: Literal[False] = False
    historical_artifact_rewrite_count: Literal[0] = 0
    historical_reclassification_count: Literal[0] = 0
    empirical_outcome_row_count: Literal[0] = 0
    empirical_estimate_count: Literal[0] = 0
    schema_version: str = V26_OUTCOME_PARENT_TERMINAL_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V179ClaimScopeAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v179_outcome_claim_scope_audit:",
        ):
            raise ValueError("v26.179 claim-scope Audit identity is invalid")
        return self


class ParentAuthenticityAttackResult(FrozenModel):
    attack_id: str = Field(min_length=1)
    control_index: int = Field(ge=1, le=6)
    attack_name: ParentAttackName
    row_count: Literal[192] = 192
    fully_rehashed_row_count: Literal[192] = 192
    unique_row_id_count: int = Field(ge=1, le=192)
    unique_job_id_count: Literal[192] = 192
    unique_raw_execution_id_count: int = Field(ge=1, le=192)
    unique_result_id_count: int = Field(ge=1, le=192)
    unique_attempt_trace_id_count: int = Field(ge=1, le=192)
    exact_manifest_job_set_match: Literal[True] = True
    current_estimator_accepted: Literal[True] = True
    q_first_fraction: str = Field(pattern=r"^[0-9]+/192$")
    q_bounded_correction_fraction: str = Field(pattern=r"^[0-9]+/192$")
    defect_reproduced: Literal[True] = True
    empirical_evidence: Literal[False] = False
    schema_version: str = V26_OUTCOME_PARENT_TERMINAL_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> ParentAuthenticityAttackResult:
        if self.unique_row_id_count != self.row_count:
            raise ValueError("fully rehashed parent attack repeats a row identity")
        if self.attack_id != identity(
            self,
            "attack_id",
            "finance_v26_job_bound_parent_authenticity_attack:",
        ):
            raise ValueError("parent-authenticity attack identity is invalid")
        return self


class ParentAuthenticityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    predecessor_empirical_schema_audit_id: str = Field(min_length=1)
    attacks: tuple[ParentAuthenticityAttackResult, ...] = Field(
        min_length=6,
        max_length=6,
    )
    attack_count: Literal[6] = 6
    current_estimator_acceptance_count: Literal[6] = 6
    defect_reproduction_count: Literal[6] = 6
    raw_execution_descriptor_count: Literal[0] = 0
    job_result_descriptor_count: Literal[0] = 0
    authoritative_job_bound_trace_count: Literal[0] = 0
    formal_empirical_outcome_row_count: Literal[0] = 0
    formal_empirical_estimate_count: Literal[0] = 0
    exact_job_index_set_closed: Literal[True] = True
    exact_job_outcome_evidence_set_closed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = V26_OUTCOME_PARENT_TERMINAL_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ParentAuthenticityAudit:
        expected = {
            "cross_job_outcome_payload_reassignment",
            "duplicate_raw_execution_id_across_jobs",
            "duplicate_result_id_across_jobs",
            "swapped_raw_and_result_parents",
            "result_parent_outcome_final_mismatch",
            "duplicate_attempt_trace_across_jobs",
        }
        if {item.attack_name for item in self.attacks} != expected:
            raise ValueError("parent-authenticity attack registry changed")
        if tuple(item.control_index for item in self.attacks) != tuple(range(1, 7)):
            raise ValueError("parent-authenticity control indices changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_empirical_outcome_parent_authenticity_audit:",
        ):
            raise ValueError("parent-authenticity Audit identity is invalid")
        return self


class FinalAbiTotalityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    promoted_payload_id: str = Field(min_length=1)
    control_indices: tuple[Literal[7], Literal[8]] = (7, 8)
    final_abi_false_qualified_payload_accepted: Literal[True] = True
    final_response_abi_invalid_endpoint_registered: Literal[False] = False
    invalid_final_parser_rejected: Literal[True] = True
    production_runner_final_parser_invocation_count: Literal[1] = 1
    production_runner_returned_trace: Literal[False] = False
    production_runner_exception_type: str = Field(min_length=1)
    production_runner_exception_message: str = Field(min_length=1)
    typed_final_abi_invalid_outcome_count: Literal[0] = 0
    exact_outcome_row_count: Literal[0] = 0
    verifier_null_policy_proven: Literal[False] = False
    qualified_false_policy_proven: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = V26_OUTCOME_PARENT_TERMINAL_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FinalAbiTotalityAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_final_abi_terminal_totality_audit:",
        ):
            raise ValueError("Final ABI totality Audit identity is invalid")
        return self


class FirstActionReferenceTotalityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    control_index: Literal[9] = 9
    unknown_action_id: str = Field(pattern=r"^[0-9a-f]{24}$")
    action_abi_valid: Literal[True] = True
    response_state_matches_current_state: Literal[True] = True
    action_absent_from_current_candidates: Literal[True] = True
    first_action_reference_invalid_endpoint_registered: Literal[False] = False
    production_runner_raised: Literal[True] = True
    production_runner_exception_type: str = Field(min_length=1)
    production_runner_exception_message: str = Field(min_length=1)
    typed_outcome_count: Literal[0] = 0
    exact_outcome_row_count: Literal[0] = 0
    correction_policy_frozen: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = V26_OUTCOME_PARENT_TERMINAL_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FirstActionReferenceTotalityAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_first_action_reference_terminal_totality_audit:",
        ):
            raise ValueError("first-Action reference totality Audit identity is invalid")
        return self


class FailureFieldSemanticsAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    control_index: Literal[10] = 10
    promoted_payload_id: str = Field(min_length=1)
    all_components_committed: Literal[True] = True
    expected_first_uncommitted_component_key: Literal[None] = None
    injected_first_failed_component_key: str = Field(min_length=1)
    fully_rehashed_payload_accepted: Literal[True] = True
    first_uncommitted_component_key_field_present: Literal[False] = False
    first_mechanism_failed_component_key_field_present: Literal[False] = False
    old_field_has_runtime_mechanism_fallback: Literal[True] = True
    strict_failure_field_semantics_closed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = V26_OUTCOME_PARENT_TERMINAL_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FailureFieldSemanticsAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_first_failure_field_semantics_audit:",
        ):
            raise ValueError("failure-field semantics Audit identity is invalid")
        return self


class OuterEndpointTotalityRow(FrozenModel):
    row_id: str = Field(min_length=1)
    endpoint_kind: OuterEndpointKind
    endpoint_registered_in_v179: Literal[False] = False
    job_bound_payload_constructible: Literal[False] = False
    exact_outcome_row_constructible: Literal[False] = False
    task_verifier_value_available: Literal[False] = False
    qualified_value_available: Literal[False] = False
    provider_call_executed: Literal[False] = False
    schema_version: str = V26_OUTCOME_PARENT_TERMINAL_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> OuterEndpointTotalityRow:
        if self.row_id != identity(
            self,
            "row_id",
            "finance_v26_outer_endpoint_totality_row:",
        ):
            raise ValueError("outer-endpoint totality row identity is invalid")
        return self


class OuterTerminalTotalityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    control_index: Literal[11] = 11
    rows: tuple[OuterEndpointTotalityRow, ...] = Field(min_length=6, max_length=6)
    endpoint_class_count: Literal[6] = 6
    registered_endpoint_count: Literal[0] = 0
    exact_outcome_row_count: Literal[0] = 0
    missing_exact_outcome_row_count: Literal[6] = 6
    terminal_totality_closed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = V26_OUTCOME_PARENT_TERMINAL_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> OuterTerminalTotalityAudit:
        expected = {
            "provider_failure_no_payload",
            "provider_transport_failure",
            "privacy_rejection",
            "resource_budget_exhausted",
            "instrument_failure",
            "provider_identity_thinking_usage_failure",
        }
        if {item.endpoint_kind for item in self.rows} != expected:
            raise ValueError("outer-endpoint totality registry changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_outer_terminal_totality_audit:",
        ):
            raise ValueError("outer terminal-totality Audit identity is invalid")
        return self


class StaticGate(FrozenModel):
    gate_name: str = Field(min_length=1)
    passed: Literal[True] = True
    evidence: str = Field(min_length=1)


class StaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGate, ...] = Field(min_length=1)
    gate_count: int = Field(ge=1)
    passed_gate_count: int = Field(ge=1)
    failed_gate_count: Literal[0] = 0
    registered_defect_control_count: Literal[11] = 11
    reproduced_defect_control_count: Literal[11] = 11
    provider_calls: Literal[0] = 0
    stage2_provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    empirical_outcome_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    mapper_calls: Literal[0] = 0
    state_assignments: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    schema_version: str = V26_OUTCOME_PARENT_TERMINAL_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StaticAudit:
        if self.gate_count != len(self.gates) or self.passed_gate_count != self.gate_count:
            raise ValueError("v26.180 static Gate denominator changed")
        if len({item.gate_name for item in self.gates}) != self.gate_count:
            raise ValueError("v26.180 static Gate names are not unique")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_job_bound_parent_terminal_static_audit:",
        ):
            raise ValueError("v26.180 Static Audit identity is invalid")
        return self


class OnlineExecutionGate(FrozenModel):
    gate_id: str = Field(min_length=1)
    parent_authenticity_audit_id: str = Field(min_length=1)
    final_abi_totality_audit_id: str = Field(min_length=1)
    first_action_totality_audit_id: str = Field(min_length=1)
    failure_field_audit_id: str = Field(min_length=1)
    outer_terminal_totality_audit_id: str = Field(min_length=1)
    decision: str = FAILED_DECISION
    exact_job_index_set_closed: Literal[True] = True
    exact_job_outcome_evidence_set_closed: Literal[False] = False
    empirical_outcome_parent_authenticity_closed: Literal[False] = False
    online_terminal_totality_closed: Literal[False] = False
    online_development_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    empirical_outcome_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    schema_version: str = V26_OUTCOME_PARENT_TERMINAL_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> OnlineExecutionGate:
        if self.decision != FAILED_DECISION:
            raise ValueError("v26.180 online execution Gate must fail closed")
        if self.gate_id != identity(
            self,
            "gate_id",
            "finance_v26_job_bound_online_execution_gate:",
        ):
            raise ValueError("v26.180 online execution Gate identity is invalid")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_root_id: str = Field(min_length=1)
    predecessor_freeze_audit_id: str = Field(min_length=1)
    claim_scope_audit_id: str = Field(min_length=1)
    parent_authenticity_audit_id: str = Field(min_length=1)
    final_abi_totality_audit_id: str = Field(min_length=1)
    first_action_totality_audit_id: str = Field(min_length=1)
    failure_field_audit_id: str = Field(min_length=1)
    outer_terminal_totality_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    online_execution_gate_id: str = Field(min_length=1)
    consumed_stage: str = CONSUMED_STAGE
    decision: str = FAILED_DECISION
    next_stage: str = NEXT_STAGE
    permitted_change_surface: tuple[str, ...] = Field(min_length=9, max_length=9)
    provider_execution_authorized: Literal[False] = False
    development_outcomes_authorized: Literal[False] = False
    source_task_component_candidate_change_authorized: Literal[False] = False
    schedule_presentation_change_authorized: Literal[False] = False
    model_thinking_grammar_policy_resource_change_authorized: Literal[False] = False
    confirmation_access_authorized: Literal[False] = False
    mapper_state_frequency_contribution_vtdo_authorized: Literal[False] = False
    historical_rewrite_authorized: Literal[False] = False
    schema_version: str = V26_OUTCOME_PARENT_TERMINAL_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if (
            self.consumed_stage != CONSUMED_STAGE
            or self.decision != FAILED_DECISION
            or self.next_stage != NEXT_STAGE
        ):
            raise ValueError("v26.180 prospective transition boundary changed")
        expected = {
            "raw_execution_descriptor",
            "job_result_descriptor",
            "job_bound_attempt_trace_parent",
            "empirical_outcome_row_constructor",
            "exact_evidence_set_estimator",
            "first_action_reference_invalid_endpoint",
            "final_response_abi_invalid_endpoint",
            "strict_failure_localization_fields",
            "outer_terminal_exact_row_totality",
        }
        if set(self.permitted_change_surface) != expected:
            raise ValueError("v26.180 permitted repair surface changed")
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_job_bound_parent_terminal_audit_transition:",
        ):
            raise ValueError("v26.180 prospective Transition identity is invalid")
        return self


class AuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_root_id: str = Field(min_length=1)
    predecessor_freeze_audit_id: str = Field(min_length=1)
    claim_scope_audit_id: str = Field(min_length=1)
    parent_authenticity_audit_id: str = Field(min_length=1)
    final_abi_totality_audit_id: str = Field(min_length=1)
    first_action_totality_audit_id: str = Field(min_length=1)
    failure_field_audit_id: str = Field(min_length=1)
    outer_terminal_totality_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    online_execution_gate_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    detail_files: tuple[FileBinding, ...] = Field(min_length=1)
    detail_file_count: int = Field(ge=1)
    registered_defect_control_count: Literal[11] = 11
    reproduced_defect_control_count: Literal[11] = 11
    predecessor_file_count: Literal[18] = 18
    predecessor_rebuild_match_count: Literal[18] = 18
    exact_job_index_count: Literal[192] = 192
    empirical_outcome_row_count: Literal[0] = 0
    empirical_estimate_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage2_provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    online_execution_authorized: Literal[False] = False
    decision: str = FAILED_DECISION
    next_stage: str = NEXT_STAGE
    schema_version: str = V26_OUTCOME_PARENT_TERMINAL_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> AuditReport:
        if self.detail_file_count != len(self.detail_files):
            raise ValueError("v26.180 report detail-file count changed")
        if self.decision != FAILED_DECISION or self.next_stage != NEXT_STAGE:
            raise ValueError("v26.180 report decision boundary changed")
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_job_bound_parent_terminal_audit_report:",
        ):
            raise ValueError("v26.180 Audit Report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    authorization: ExternalAuditAuthorization
    source_root: TransitiveSourceRoot
    predecessor: V179PredecessorFreezeAudit
    claim_scope: V179ClaimScopeAudit
    parent_authenticity: ParentAuthenticityAudit
    final_abi_totality: FinalAbiTotalityAudit
    first_action_totality: FirstActionReferenceTotalityAudit
    failure_field_semantics: FailureFieldSemanticsAudit
    outer_terminal_totality: OuterTerminalTotalityAudit
    static: StaticAudit
    online_gate: OnlineExecutionGate
    transition: ProspectiveTransition
    report: AuditReport


__all__ = [
    "AuditReport",
    "BuildProducts",
    "CONSUMED_STAGE",
    "ExternalAuditAuthorization",
    "FAILED_DECISION",
    "FailureFieldSemanticsAudit",
    "FileBinding",
    "FinalAbiTotalityAudit",
    "FirstActionReferenceTotalityAudit",
    "NEXT_STAGE",
    "OnlineExecutionGate",
    "OuterEndpointKind",
    "OuterEndpointTotalityRow",
    "OuterTerminalTotalityAudit",
    "ParentAttackName",
    "ParentAuthenticityAttackResult",
    "ParentAuthenticityAudit",
    "ProspectiveTransition",
    "StaticAudit",
    "StaticGate",
    "TransitiveSourceRoot",
    "V179ClaimScopeAudit",
    "V179PredecessorFreezeAudit",
    "V26_OUTCOME_PARENT_TERMINAL_AUDIT_VERSION",
    "identity",
    "make_identity_model",
]
