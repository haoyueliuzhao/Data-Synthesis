from __future__ import annotations

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
    AuthoritativeJobBoundOutcomeContract,
    AuthoritativeTerminalRegistry,
    ExactEvidenceSetEvaluation,
    TerminalKind,
)
from trusted_synthesis.hashing import canonical_hash

V26_AUTHORITATIVE_OUTCOME_PREFLIGHT_VERSION: Final = (
    "capability_authoritative_outcome_terminal_preflight.v1"
)
AUTHORIZED_STAGE: Final = (
    "capability_observation_empirical_outcome_authoritative_parent_binding_"
    "and_terminal_totality_preflight_only"
)
NEXT_STAGE: Final = (
    "capability_observation_authoritative_parent_bound_terminal_total_192_job_"
    "preflight_independent_audit_only"
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
        "predecessor_artifact",
        "implementation_source",
        "formal_detail",
    ]


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: Literal["3c6038e4c303f393339daf346452d6f9824704cd498629b7eb89aaf6217f679d"]
    review_byte_count: Literal[25586] = 25_586
    audited_v179_commit: Literal["27ac98d03d078d522cecf7a0cb290230cac63036"]
    audited_v180_implementation_commit: Literal["a9f8435f375a1e2a4da21b29e1f9d1917f3e964c"]
    consumed_stage: str = AUTHORIZED_STAGE
    semantic_parser_gate_required: Literal[True] = True
    authoritative_terminal_registry_required: Literal[True] = True
    exact_evidence_bijection_required: Literal[True] = True
    typed_failure_locus_required: Literal[True] = True
    exactly_one_terminal_row_required: Literal[True] = True
    provider_execution_authorized: Literal[False] = False
    schema_version: str = V26_AUTHORITATIVE_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.consumed_stage != AUTHORIZED_STAGE:
            raise ValueError("v26.181 consumed stage changed")
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_authoritative_outcome_external_authorization:",
        ):
            raise ValueError("v26.181 external Authorization identity is invalid")
        return self


class TransitiveSourceRoot(FrozenModel):
    root_id: str = Field(min_length=1)
    entry_modules: tuple[str, ...] = Field(min_length=4)
    files: tuple[FileBinding, ...] = Field(min_length=1)
    file_count: int = Field(ge=1)
    unresolved_imports: tuple[str, ...] = ()
    unresolved_import_count: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_root(self) -> TransitiveSourceRoot:
        if self.file_count != len(self.files):
            raise ValueError("v26.181 transitive source file count changed")
        if len({item.relative_path for item in self.files}) != self.file_count:
            raise ValueError("v26.181 transitive source Root repeats a file")
        if self.unresolved_imports:
            raise ValueError("v26.181 transitive source Root has unresolved imports")
        if self.root_id != identity(
            self,
            "root_id",
            "finance_v26_authoritative_outcome_transitive_source_root:",
        ):
            raise ValueError("v26.181 transitive source Root identity is invalid")
        return self


class V180PredecessorFreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    predecessor_next_stage: str = AUTHORIZED_STAGE
    predecessor_files: tuple[FileBinding, ...] = Field(min_length=14, max_length=14)
    predecessor_file_count: Literal[14] = 14
    independent_rebuild_match_count: Literal[14] = 14
    predecessor_mutation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    historical_reclassification_count: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V180PredecessorFreezeAudit:
        if self.predecessor_next_stage != AUTHORIZED_STAGE:
            raise ValueError("v26.180 predecessor transition changed")
        if len(self.predecessor_files) != self.predecessor_file_count:
            raise ValueError("v26.180 predecessor file denominator changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v180_predecessor_freeze_audit:",
        ):
            raise ValueError("v26.180 predecessor Freeze identity is invalid")
        return self


class V180MeasurementScopeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    negative_parent_authenticity_facts_retained: Literal[True] = True
    runtime_non_totality_facts_retained: Literal[True] = True
    registered_control_matrix_size: Literal[11] = 11
    enumerated_outer_class_count: Literal[6] = 6
    historical_malformed_final_exception_type: Literal["ValidationError"] = "ValidationError"
    historical_malformed_final_observation_retained: Literal[True] = True
    old_formal_parser_rejection_gate_closed: Literal[False] = False
    old_complete_terminal_registry_claim: Literal["unknown"] = "unknown"
    old_static_gate_interpretation: Literal[
        "audit_integrity_and_defect_reproduction_meta_gates"
    ] = "audit_integrity_and_defect_reproduction_meta_gates"
    old_complete_negative_audit_claim_narrowed: Literal[True] = True
    old_synthetic_denominator_term_replaced: Literal[True] = True
    online_execution_authorized: Literal[False] = False
    historical_rewrite_count: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V180MeasurementScopeAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_v180_measurement_scope_audit:",
        ):
            raise ValueError("v26.180 measurement-scope Audit identity is invalid")
        return self


class TerminalRegistryDerivationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    v166_terminal_matrix_id: str = Field(min_length=1)
    v179_runner_id: str = Field(min_length=1)
    v179_generation_profile_id: str = Field(min_length=1)
    v180_outer_terminal_audit_id: str = Field(min_length=1)
    v166_case_count: Literal[8] = 8
    v179_endpoint_kind_count: Literal[6] = 6
    v180_outer_class_count: Literal[6] = 6
    frozen_profile_parent_count: Literal[6] = 6
    derivation_source_label_count: int = Field(ge=1)
    consumed_derivation_source_label_count: int = Field(ge=1)
    unmapped_source_label_count: Literal[0] = 0
    registry: AuthoritativeTerminalRegistry
    terminal_kind_count: Literal[18] = 18
    reachable_count: int = Field(ge=1, le=18)
    registered_but_unreachable_count: int = Field(ge=0, le=18)
    not_applicable_with_witness_count: int = Field(ge=0, le=18)
    complete_registry_closed: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> TerminalRegistryDerivationAudit:
        if (
            self.derivation_source_label_count != self.consumed_derivation_source_label_count
            or self.derivation_source_label_count != len(self.registry.derivation_source_labels)
        ):
            raise ValueError("terminal registry source-label exact set changed")
        if (
            self.reachable_count
            + self.registered_but_unreachable_count
            + self.not_applicable_with_witness_count
            != self.terminal_kind_count
        ):
            raise ValueError("terminal registry statuses do not partition the exact set")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_authoritative_terminal_registry_derivation_audit:",
        ):
            raise ValueError("terminal registry derivation Audit identity is invalid")
        return self


class FinalParserSemanticGateAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    grammar_id: str = Field(min_length=1)
    parser_input_hash: str = Field(min_length=1)
    parser_invocation_count: Literal[1] = 1
    parser_rejected: Literal[True] = True
    parser_exception_type: Literal["ValidationError"] = "ValidationError"
    parser_exception_message: str = Field(min_length=1)
    escaped_exception_phase: Literal["final_parser"] = "final_parser"
    typed_final_abi_invalid_bundle_count: Literal[1] = 1
    task_verifier_invocation_count: Literal[0] = 0
    base_validity: Literal[False] = False
    mechanism_qualification: Literal[False] = False
    qualified_validity: Literal[False] = False
    exact_outcome_row_count: Literal[1] = 1
    exception_escape_count: Literal[0] = 0
    semantic_attack_count: Literal[4] = 4
    semantic_attack_rejection_count: Literal[4] = 4
    provider_calls: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FinalParserSemanticGateAudit:
        if "Final response requires exactly answer and rationale_summary" not in (
            self.parser_exception_message
        ):
            raise ValueError("Final parser semantic Gate lacks the exact rejection reason")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_final_parser_semantic_gate_audit:",
        ):
            raise ValueError("Final parser semantic Gate Audit identity is invalid")
        return self


class AuthoritativeEvidenceDagAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract: AuthoritativeJobBoundOutcomeContract
    scripted_evaluation: ExactEvidenceSetEvaluation
    exact_manifest_job_count: Literal[192] = 192
    raw_descriptor_count: Literal[192] = 192
    result_descriptor_count: Literal[192] = 192
    job_bound_trace_count: Literal[192] = 192
    scripted_outcome_row_count: Literal[192] = 192
    unique_raw_descriptor_count: Literal[192] = 192
    unique_result_descriptor_count: Literal[192] = 192
    unique_trace_count: Literal[192] = 192
    unique_row_count: Literal[192] = 192
    exact_job_set_match_count: Literal[192] = 192
    raw_path_parent_match_count: Literal[192] = 192
    result_path_parent_match_count: Literal[192] = 192
    raw_result_parent_match_count: Literal[192] = 192
    result_trace_parent_match_count: Literal[192] = 192
    trace_row_parent_match_count: Literal[192] = 192
    terminal_projection_count: Literal[192] = 192
    python_exception_escape_count: Literal[0] = 0
    formal_empirical_row_count: Literal[0] = 0
    formal_empirical_estimate_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> AuthoritativeEvidenceDagAudit:
        if self.scripted_evaluation.evidence_kind != "scripted_preflight_control":
            raise ValueError("authoritative DAG Audit persists a non-scripted evaluation")
        if self.scripted_evaluation.empirical:
            raise ValueError("scripted authoritative DAG Audit is mislabeled empirical")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_authoritative_evidence_dag_audit:",
        ):
            raise ValueError("Authoritative Evidence DAG Audit identity is invalid")
        return self


class TerminalTotalityControlRow(FrozenModel):
    row_id: str = Field(min_length=1)
    terminal_kind: TerminalKind
    policy_id: str = Field(min_length=1)
    registration_status: str = Field(min_length=1)
    control_bundle_root_hash: str = Field(min_length=1)
    terminal_projection_count: Literal[1] = 1
    exact_outcome_row_count: Literal[1] = 1
    exception_escape_count: Literal[0] = 0
    task_completion: bool | None
    task_verifier_invoked: bool
    base_validity: bool | None
    mechanism_qualification: bool | None
    qualified_validity: bool | None
    terminal_locus_count: int = Field(ge=0, le=1)
    diagnostic_only: bool
    provider_calls: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> TerminalTotalityControlRow:
        if self.row_id != identity(
            self,
            "row_id",
            "finance_v26_terminal_totality_control_row:",
        ):
            raise ValueError("terminal totality control row identity is invalid")
        return self


class TerminalTotalityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    registry_id: str = Field(min_length=1)
    rows: tuple[TerminalTotalityControlRow, ...] = Field(min_length=18, max_length=18)
    terminal_kind_count: Literal[18] = 18
    exactly_one_projection_count: Literal[18] = 18
    exact_outcome_row_count: Literal[18] = 18
    exception_escape_count: Literal[0] = 0
    missing_terminal_kind_count: Literal[0] = 0
    duplicate_terminal_kind_count: Literal[0] = 0
    policy_match_count: Literal[18] = 18
    complete_terminal_totality_preflight_closed: Literal[True] = True
    empirical_outcome_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> TerminalTotalityAudit:
        if len({item.terminal_kind for item in self.rows}) != self.terminal_kind_count:
            raise ValueError("terminal totality controls are not one row per terminal kind")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_terminal_totality_preflight_audit:",
        ):
            raise ValueError("Terminal Totality Audit identity is invalid")
        return self


class UnknownFirstActionPolicyAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    state_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    unknown_action_id: str = Field(pattern=r"^[0-9a-f]{24}$")
    action_abi_valid: Literal[True] = True
    action_reference_valid: Literal[False] = False
    frozen_policy: Literal["immediate_typed_terminal_without_correction"] = (
        "immediate_typed_terminal_without_correction"
    )
    correction_invoked: Literal[False] = False
    terminal_kind: Literal["first_action_reference_invalid"] = "first_action_reference_invalid"
    terminal_projection_count: Literal[1] = 1
    exact_outcome_row_count: Literal[1] = 1
    exception_escape_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> UnknownFirstActionPolicyAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_unknown_first_action_policy_audit:",
        ):
            raise ValueError("unknown first-Action policy Audit identity is invalid")
        return self


class DestructiveMutation(FrozenModel):
    mutation_id: str = Field(min_length=1)
    mutation_transition_id: str = Field(min_length=1)
    mutation_report_id: str = Field(min_length=1)
    mutation_name: str = Field(min_length=1)
    mutation_family: Literal[
        "predecessor_parent_attack",
        "content_identity_attack",
        "attempt_trace_attack",
        "job_parent_attack",
        "terminal_totality_attack",
        "artifact_parent_attack",
        "final_parser_semantic_attack",
    ]
    fully_rehashed_object_count: int = Field(ge=1)
    downstream_parent_rehash_count: int = Field(ge=1)
    transition_and_report_rehashed: Literal[True] = True
    rejected: Literal[True] = True
    rejection_phase: str = Field(min_length=1)
    stale_hash_only: Literal[False] = False
    schema_version: str = V26_AUTHORITATIVE_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_mutation(self) -> DestructiveMutation:
        if self.mutation_id != identity(
            self,
            "mutation_id",
            "finance_v26_authoritative_outcome_destructive_mutation:",
        ):
            raise ValueError("authoritative Outcome mutation identity is invalid")
        return self


class ProductionDestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    registry_id: str = Field(min_length=1)
    mutations: tuple[DestructiveMutation, ...] = Field(min_length=25, max_length=25)
    mutation_count: Literal[25] = 25
    fully_rehashed_mutation_count: Literal[25] = 25
    transition_report_rehash_count: Literal[25] = 25
    rejection_count: Literal[25] = 25
    acceptance_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ProductionDestructiveAudit:
        if len({item.mutation_name for item in self.mutations}) != self.mutation_count:
            raise ValueError("authoritative Outcome destructive denominator repeats an attack")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_authoritative_outcome_production_destructive_audit:",
        ):
            raise ValueError("authoritative Outcome destructive Audit identity is invalid")
        return self


class MetaGate(FrozenModel):
    gate_name: str = Field(min_length=1)
    passed: Literal[True] = True
    layer: Literal[
        "audit_construction_integrity",
        "preflight_contract_integrity",
        "scientific_admission_boundary",
    ]
    evidence: str = Field(min_length=1)


class AuditIntegrityMetaGateAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[MetaGate, ...] = Field(min_length=1)
    gate_count: int = Field(ge=1)
    passed_gate_count: int = Field(ge=1)
    failed_gate_count: Literal[0] = 0
    audit_construction_integrity: Literal["PASS"] = "PASS"
    v179_local_scripted_preflight: Literal["RETAINED"] = "RETAINED"
    empirical_parent_authenticity: Literal["PREFLIGHT_CLOSED"] = "PREFLIGHT_CLOSED"
    terminal_totality: Literal["PREFLIGHT_CLOSED"] = "PREFLIGHT_CLOSED"
    online_execution_admission: Literal["BLOCKED_PENDING_INDEPENDENT_AUDIT"] = (
        "BLOCKED_PENDING_INDEPENDENT_AUDIT"
    )
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    formal_empirical_rows: Literal[0] = 0
    formal_empirical_estimates: Literal[0] = 0
    mapper_state_frequency_contribution_vtdo_count: Literal[0] = 0
    schema_version: str = V26_AUTHORITATIVE_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> AuditIntegrityMetaGateAudit:
        if self.gate_count != len(self.gates) or self.passed_gate_count != self.gate_count:
            raise ValueError("v26.181 meta-Gate denominator changed")
        if len({item.gate_name for item in self.gates}) != self.gate_count:
            raise ValueError("v26.181 meta-Gate names are not unique")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_authoritative_outcome_meta_gate_audit:",
        ):
            raise ValueError("v26.181 meta-Gate Audit identity is invalid")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_root_id: str = Field(min_length=1)
    predecessor_freeze_audit_id: str = Field(min_length=1)
    measurement_scope_audit_id: str = Field(min_length=1)
    terminal_registry_audit_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    final_parser_gate_audit_id: str = Field(min_length=1)
    evidence_dag_audit_id: str = Field(min_length=1)
    terminal_totality_audit_id: str = Field(min_length=1)
    unknown_action_policy_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    meta_gate_audit_id: str = Field(min_length=1)
    consumed_stage: str = AUTHORIZED_STAGE
    next_stage: str = NEXT_STAGE
    provider_execution_authorized: Literal[False] = False
    development_outcomes_authorized: Literal[False] = False
    independent_audit_required: Literal[True] = True
    empirical_rows_materialized: Literal[False] = False
    source_task_component_candidate_change_authorized: Literal[False] = False
    schedule_presentation_change_authorized: Literal[False] = False
    model_thinking_grammar_policy_resource_change_authorized: Literal[False] = False
    manifest_job_set_change_authorized: Literal[False] = False
    confirmation_access_authorized: Literal[False] = False
    mapper_state_frequency_contribution_vtdo_authorized: Literal[False] = False
    historical_rewrite_authorized: Literal[False] = False
    schema_version: str = V26_AUTHORITATIVE_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.consumed_stage != AUTHORIZED_STAGE or self.next_stage != NEXT_STAGE:
            raise ValueError("v26.181 transition stage boundary changed")
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_authoritative_outcome_preflight_transition:",
        ):
            raise ValueError("v26.181 prospective Transition identity is invalid")
        return self


class PreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    audited_v179_commit: str = Field(min_length=40, max_length=40)
    audited_v180_implementation_commit: str = Field(min_length=40, max_length=40)
    audit_implementation_source_root_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    predecessor_freeze_audit_id: str = Field(min_length=1)
    measurement_scope_audit_id: str = Field(min_length=1)
    terminal_registry_audit_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    final_parser_gate_audit_id: str = Field(min_length=1)
    evidence_dag_audit_id: str = Field(min_length=1)
    terminal_totality_audit_id: str = Field(min_length=1)
    unknown_action_policy_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    meta_gate_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    detail_files: tuple[FileBinding, ...] = Field(min_length=1)
    detail_file_count: int = Field(ge=1)
    v180_predecessor_file_count: Literal[14] = 14
    v180_rebuild_match_count: Literal[14] = 14
    terminal_kind_count: Literal[18] = 18
    exact_manifest_job_count: Literal[192] = 192
    scripted_descriptor_bundle_count: Literal[192] = 192
    terminal_control_row_count: Literal[18] = 18
    destructive_mutation_count: Literal[25] = 25
    final_parser_semantic_attack_rejection_count: Literal[4] = 4
    formal_empirical_row_count: Literal[0] = 0
    formal_empirical_estimate_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage2_provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    confirmation_access_count: Literal[0] = 0
    online_execution_authorized: Literal[False] = False
    audit_construction_integrity: Literal["PASS"] = "PASS"
    parent_authenticity_preflight: Literal["CLOSED"] = "CLOSED"
    terminal_totality_preflight: Literal["CLOSED"] = "CLOSED"
    online_execution_admission: Literal["BLOCKED_PENDING_INDEPENDENT_AUDIT"] = (
        "BLOCKED_PENDING_INDEPENDENT_AUDIT"
    )
    next_stage: str = NEXT_STAGE
    schema_version: str = V26_AUTHORITATIVE_OUTCOME_PREFLIGHT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> PreflightReport:
        if self.detail_file_count != len(self.detail_files):
            raise ValueError("v26.181 report detail-file count changed")
        if self.next_stage != NEXT_STAGE:
            raise ValueError("v26.181 report next stage changed")
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_authoritative_outcome_preflight_report:",
        ):
            raise ValueError("v26.181 Preflight Report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    authorization: ExternalAuditAuthorization
    source_root: TransitiveSourceRoot
    predecessor: V180PredecessorFreezeAudit
    measurement_scope: V180MeasurementScopeAudit
    terminal_registry: TerminalRegistryDerivationAudit
    outcome_contract: AuthoritativeJobBoundOutcomeContract
    final_parser_gate: FinalParserSemanticGateAudit
    evidence_dag: AuthoritativeEvidenceDagAudit
    terminal_totality: TerminalTotalityAudit
    unknown_action_policy: UnknownFirstActionPolicyAudit
    destructive: ProductionDestructiveAudit
    meta_gates: AuditIntegrityMetaGateAudit
    transition: ProspectiveTransition
    report: PreflightReport


__all__ = [
    "AUTHORIZED_STAGE",
    "AuditIntegrityMetaGateAudit",
    "AuthoritativeEvidenceDagAudit",
    "BuildProducts",
    "DestructiveMutation",
    "ExternalAuditAuthorization",
    "FileBinding",
    "FinalParserSemanticGateAudit",
    "MetaGate",
    "NEXT_STAGE",
    "PreflightReport",
    "ProductionDestructiveAudit",
    "ProspectiveTransition",
    "TerminalRegistryDerivationAudit",
    "TerminalTotalityAudit",
    "TerminalTotalityControlRow",
    "TransitiveSourceRoot",
    "UnknownFirstActionPolicyAudit",
    "V180MeasurementScopeAudit",
    "V180PredecessorFreezeAudit",
    "V26_AUTHORITATIVE_OUTCOME_PREFLIGHT_VERSION",
    "identity",
    "make_identity_model",
]
