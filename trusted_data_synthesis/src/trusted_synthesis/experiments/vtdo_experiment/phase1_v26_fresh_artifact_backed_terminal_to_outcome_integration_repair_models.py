from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION = "fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight.v1"
AUTHORIZED_STAGE = "fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_only"
NEXT_STAGE: Literal[
    "fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_independent_audit_only"
] = "fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_independent_audit_only"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


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


class FileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class SymbolBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_byte_count: int = Field(gt=0)


class PredecessorFreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    v196_report_id: str = Field(min_length=1)
    v196_transition_id: str = Field(min_length=1)
    v196_sealed_artifact_root: str = Field(min_length=1)
    v196_distribution_artifact_root: str = Field(min_length=1)
    v196_file_count: Literal[13] = 13
    v196_file_match_count: Literal[13] = 13
    v195_terminal_registry_id: str = Field(min_length=1)
    v195_raw_descriptor_contract_id: str = Field(min_length=1)
    v195_result_descriptor_contract_id: str = Field(min_length=1)
    v195_attempt_trace_contract_id: str = Field(min_length=1)
    v195_outcome_row_contract_id: str = Field(min_length=1)
    v195_evaluator_contract_id: str = Field(min_length=1)
    six_authority_identity_match_count: Literal[6] = 6
    v194_execution_contract_id: str = Field(min_length=1)
    v194_runner_id: str = Field(min_length=1)
    v194_manifest_id: str = Field(min_length=1)
    v194_package_catalog_id: str = Field(min_length=1)
    historical_mutation_count: Literal[0] = 0
    qa_change_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorFreezeAudit:
        six = (
            self.v195_terminal_registry_id,
            self.v195_raw_descriptor_contract_id,
            self.v195_result_descriptor_contract_id,
            self.v195_attempt_trace_contract_id,
            self.v195_outcome_row_contract_id,
            self.v195_evaluator_contract_id,
        )
        if len(set(six)) != 6:
            raise ValueError("v26.195 authority identity vector differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_197_predecessor_freeze_audit:",
        ):
            raise ValueError("v26.197 predecessor Freeze identity differs")
        return self


class IntegrationImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    files: tuple[FileBinding, ...] = Field(min_length=4, max_length=4)
    symbols: tuple[SymbolBinding, ...] = Field(min_length=8)
    predecessor_complete_job_source_unchanged: Literal[True] = True
    successor_identity_required: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> IntegrationImplementationBinding:
        paths = tuple(item.relative_path for item in self.files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("integration implementation file vector differs")
        if any(item.relative_path not in set(paths) for item in self.symbols):
            raise ValueError("integration symbol crosses its source files")
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_terminal_to_outcome_implementation_binding:",
        ):
            raise ValueError("integration implementation binding identity differs")
        return self


class TerminalIntegrationControl(FrozenModel):
    control_id: str = Field(min_length=1)
    target_terminal_kind: str = Field(min_length=1)
    exact_job_id: str = Field(min_length=1)
    execution_evidence_id: str = Field(min_length=1)
    terminal_decision_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    outcome_row_id: str = Field(min_length=1)
    observed_terminal_kind: str = Field(min_length=1)
    v194_invoke_count: Literal[1] = 1
    terminal_projection_count: Literal[1] = 1
    fresh_writer_raw_call_count: Literal[1] = 1
    fresh_writer_result_call_count: Literal[1] = 1
    raw_before_result: Literal[True] = True
    raw_actual_byte_match: Literal[True] = True
    result_actual_byte_match: Literal[True] = True
    failure_locus_reconstructed: Literal[True] = True
    trace_reconstructed: Literal[True] = True
    outcome_reconstructed: Literal[True] = True
    old_fixture_complete_observed: Literal[False] = False
    caller_supplied_terminal: Literal[False] = False
    exception_escape_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> TerminalIntegrationControl:
        if self.target_terminal_kind != self.observed_terminal_kind:
            raise ValueError("terminal integration control did not reach its target")
        if self.control_id != identity(
            self,
            "control_id",
            "finance_v26_197_terminal_integration_control:",
        ):
            raise ValueError("terminal integration control identity differs")
        return self


class ProductionTerminalIntegrationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    authorization_admission_id: str = Field(min_length=1)
    controls: tuple[TerminalIntegrationControl, ...] = Field(min_length=16, max_length=16)
    reachable_terminal_count: Literal[16] = 16
    distinct_job_count: Literal[16] = 16
    v194_invoke_count: Literal[16] = 16
    dispatcher_decision_count: Literal[16] = 16
    terminal_projection_count: Literal[16] = 16
    fresh_raw_count: Literal[16] = 16
    fresh_result_count: Literal[16] = 16
    reconstructed_trace_count: Literal[16] = 16
    reconstructed_outcome_count: Literal[16] = 16
    raw_result_actual_byte_match_count: Literal[32] = 32
    old_fixture_complete_count: Literal[0] = 0
    exception_escape_count: Literal[0] = 0
    gate_passed: Literal[True] = True
    provider_calls: Literal[0] = 0
    development_outcomes: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ProductionTerminalIntegrationAudit:
        if (
            len({item.target_terminal_kind for item in self.controls}) != 16
            or len({item.exact_job_id for item in self.controls}) != 16
            or any(item.provider_calls for item in self.controls)
        ):
            raise ValueError("terminal integration control denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_197_production_terminal_integration_audit:",
        ):
            raise ValueError("terminal integration audit identity differs")
        return self


class DispatcherExclusionWitness(FrozenModel):
    witness_id: str = Field(min_length=1)
    terminal_kind: Literal["measurement_support_exit", "policy_horizon_exhausted"]
    integration_contract_id: str = Field(min_length=1)
    dispatcher_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    runner_invoke_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dispatcher_branch_token_count: Literal[0] = 0
    runner_branch_token_count: Literal[0] = 0
    caller_terminal_parameter_count: Literal[0] = 0
    empirical_denominator_entry_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_witness(self) -> DispatcherExclusionWitness:
        if self.witness_id != identity(
            self,
            "witness_id",
            "finance_v26_197_dispatcher_exclusion_witness:",
        ):
            raise ValueError("dispatcher exclusion witness identity differs")
        return self


class DispatcherExclusionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    witnesses: tuple[DispatcherExclusionWitness, ...] = Field(min_length=2, max_length=2)
    exact_witness_count: Literal[2] = 2
    exclusion_pass_count: Literal[2] = 2
    empirical_denominator_entry_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DispatcherExclusionAudit:
        if {item.terminal_kind for item in self.witnesses} != {
            "measurement_support_exit",
            "policy_horizon_exhausted",
        }:
            raise ValueError("dispatcher exclusion witness set differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_197_dispatcher_exclusion_audit:",
        ):
            raise ValueError("dispatcher exclusion audit identity differs")
        return self


class AuthorizationControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    admitted: bool
    rejected: bool
    exact_reason: str = Field(min_length=1)
    credential_lookup_count: Literal[0] = 0
    client_construction_count: int = Field(ge=0, le=1)
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> AuthorizationControl:
        if self.admitted == self.rejected:
            raise ValueError("authorization control must be admitted xor rejected")
        if self.control_id != identity(
            self,
            "control_id",
            "finance_v26_197_authorization_control:",
        ):
            raise ValueError("authorization control identity differs")
        return self


class AuthorizationIngressAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    controls: tuple[AuthorizationControl, ...] = Field(min_length=6, max_length=6)
    legal_preflight_parent_admitted: Literal[True] = True
    missing_parent_rejected: Literal[True] = True
    modified_parent_rejected: Literal[True] = True
    self_declared_parent_rejected: Literal[True] = True
    cross_experiment_parent_rejected: Literal[True] = True
    legal_parent_provider_request_rejected: Literal[True] = True
    invalid_control_credential_lookup_count: Literal[0] = 0
    invalid_control_client_construction_count: Literal[0] = 0
    valid_preflight_client_construction_count: Literal[1] = 1
    provider_calls: Literal[0] = 0
    gate_passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> AuthorizationIngressAudit:
        if len({item.control_name for item in self.controls}) != 6:
            raise ValueError("authorization control denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_197_authorization_ingress_audit:",
        ):
            raise ValueError("authorization ingress audit identity differs")
        return self


class AttackResult(FrozenModel):
    attack_id: str = Field(min_length=1)
    attack_name: str = Field(min_length=1)
    target_layer: str = Field(min_length=1)
    expected_reason: str = Field(min_length=1)
    actual_reason: str = Field(min_length=1)
    fully_rehashed: bool
    rejected: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_attack(self) -> AttackResult:
        if self.expected_reason != self.actual_reason:
            raise ValueError("integration attack rejection reason differs")
        if self.attack_id != identity(
            self,
            "attack_id",
            "fresh_terminal_to_outcome_attack:",
        ):
            raise ValueError("integration attack identity differs")
        return self


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    attacks: tuple[AttackResult, ...] = Field(min_length=12)
    attack_count: int = Field(ge=12)
    rejection_count: int = Field(ge=12)
    accepted_count: Literal[0] = 0
    fully_rehashed_attack_count: int = Field(ge=4)
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        if (
            self.attack_count != len(self.attacks)
            or self.rejection_count != len(self.attacks)
            or self.fully_rehashed_attack_count
            != sum(int(item.fully_rehashed) for item in self.attacks)
            or len({item.attack_name for item in self.attacks}) != len(self.attacks)
        ):
            raise ValueError("integration destructive denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_197_destructive_audit:",
        ):
            raise ValueError("integration destructive audit identity differs")
        return self


class StaticGate(FrozenModel):
    name: str = Field(min_length=1)
    passed: Literal[True] = True
    evidence_ids: tuple[str, ...] = Field(min_length=1)


class StaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGate, ...] = Field(min_length=20)
    gate_count: int = Field(ge=20)
    passed_count: int = Field(ge=20)
    failed_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_outcomes: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    qa_change_count: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StaticAudit:
        if (
            self.gate_count != len(self.gates)
            or self.passed_count != len(self.gates)
            or len({item.name for item in self.gates}) != len(self.gates)
        ):
            raise ValueError("integration static Gate denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_197_static_audit:",
        ):
            raise ValueError("integration static audit identity differs")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    terminal_integration_audit_id: str = Field(min_length=1)
    exclusion_audit_id: str = Field(min_length=1)
    authorization_ingress_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    next_stage: Literal[
        "fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_"
        "independent_audit_only"
    ] = NEXT_STAGE
    online_execution_authorized: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    source_task_or_manifest_change_authorized: Literal[False] = False
    six_outcome_contract_semantic_change_authorized: Literal[False] = False
    qa_change_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_197_transition:",
        ):
            raise ValueError("v26.197 transition identity differs")
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
    scope: Literal["sealed_evidence", "distribution"]
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> ArtifactManifest:
        paths = tuple(item.relative_path for item in self.members)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.197 artifact member set differs")
        if self.file_count != len(self.members) or self.total_byte_count != sum(
            item.byte_count for item in self.members
        ):
            raise ValueError("v26.197 artifact aggregate differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix=f"finance_v26_197_{self.scope}_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("v26.197 artifact Root differs")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            f"finance_v26_197_{self.scope}_artifact_manifest:",
        ):
            raise ValueError("v26.197 artifact Manifest identity differs")
        return self


class RepairPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    predecessor_freeze_audit_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    authorization_admission_id: str = Field(min_length=1)
    terminal_integration_audit_id: str = Field(min_length=1)
    dispatcher_exclusion_audit_id: str = Field(min_length=1)
    authorization_ingress_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    sealed_evidence_manifest_id: str = Field(min_length=1)
    sealed_evidence_artifact_root: str = Field(min_length=1)
    decision: Literal[
        "fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_passed_"
        "independent_audit_required_online_execution_blocked"
    ]
    reachable_terminal_count: Literal[16] = 16
    production_terminal_integration_success_count: Literal[16] = 16
    excluded_terminal_witness_count: Literal[2] = 2
    external_authorization_ingress_passed: Literal[True] = True
    six_authority_identity_change_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_outcomes: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    qa_change_count: Literal[0] = 0
    online_development_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> RepairPreflightReport:
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_197_terminal_outcome_repair_preflight_report:",
        ):
            raise ValueError("v26.197 Report identity differs")
        return self
