from __future__ import annotations

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION = "fresh_artifact_backed_terminal_to_outcome_integration_repair_independent_audit.v1"
AUTHORIZED_STAGE: Final[
    Literal[
        "fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_"
        "independent_audit_only"
    ]
] = "fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_independent_audit_only"
NEXT_STAGE: Final[
    Literal[
        "fresh_artifact_backed_terminal_to_outcome_integration_repair_"
        "online_execution_authorization_only"
    ]
] = (
    "fresh_artifact_backed_terminal_to_outcome_integration_repair_"
    "online_execution_authorization_only"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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


class IndependentAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    audit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    audit_byte_count: int = Field(gt=0)
    audit_decision: Literal["v26_197_accepted_independent_audit_only"]
    consumed_stage: Literal[
        "fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_"
        "independent_audit_only"
    ] = AUTHORIZED_STAGE
    source_transition_id: str = Field(min_length=1)
    audited_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    provider_calls_authorized: Literal[False] = False
    online_execution_authorized: Literal[False] = False
    source_or_manifest_change_authorized: Literal[False] = False
    authority_contract_change_authorized: Literal[False] = False
    qa_change_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> IndependentAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_198_external_independent_audit_authorization:",
        ):
            raise ValueError("v26.198 external authorization identity differs")
        return self


class V197FreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    v197_report_id: str = Field(min_length=1)
    v197_transition_id: str = Field(min_length=1)
    v197_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    v197_source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    v197_sealed_artifact_root: str = Field(min_length=1)
    v197_distribution_artifact_root: str = Field(min_length=1)
    formal_file_count: Literal[48] = 48
    formal_file_match_count: Literal[48] = 48
    formal_total_byte_count: Literal[285781] = 285_781
    distribution_member_count: Literal[47] = 47
    sealed_member_count: Literal[45] = 45
    six_authority_identity_match_count: Literal[6] = 6
    historical_mutation_count: Literal[0] = 0
    qa_change_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V197FreezeAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_198_v197_source_artifact_freeze_audit:",
        ):
            raise ValueError("v26.198 v26.197 Freeze identity differs")
        return self


class FormalRebuildAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    freeze_audit_id: str = Field(min_length=1)
    detached_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    detached_source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    frozen_file_count: Literal[48] = 48
    rebuilt_file_count: Literal[48] = 48
    path_match_count: Literal[48] = 48
    sha256_match_count: Literal[48] = 48
    byte_count_match_count: Literal[48] = 48
    actual_byte_match_count: Literal[48] = 48
    rebuilt_total_byte_count: Literal[285781] = 285_781
    candidate_report_used_as_outcome_oracle: Literal[False] = False
    credential_environment_variable_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FormalRebuildAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_198_v197_formal_rebuild_audit:",
        ):
            raise ValueError("v26.198 formal rebuild identity differs")
        return self


class IndependentReplayControl(FrozenModel):
    control_id: str = Field(min_length=1)
    exact_job_id: str = Field(min_length=1)
    expected_terminal_kind: str = Field(min_length=1)
    observed_terminal_kind: str = Field(min_length=1)
    terminal_decision_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    outcome_row_id: str = Field(min_length=1)
    failure_locus_count: int = Field(ge=0, le=1)
    v194_actual_invoke_count: Literal[1] = 1
    raw_actual_byte_match: Literal[True] = True
    result_actual_byte_match: Literal[True] = True
    candidate_raw_byte_match: Literal[True] = True
    candidate_result_byte_match: Literal[True] = True
    independent_terminal_reconstructed: Literal[True] = True
    independent_failure_locus_reconstructed: Literal[True] = True
    independent_trace_reconstructed: Literal[True] = True
    independent_outcome_reconstructed: Literal[True] = True
    terminal_value_entered_harness_input: Literal[False] = False
    exception_escape_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> IndependentReplayControl:
        if self.expected_terminal_kind != self.observed_terminal_kind:
            raise ValueError("independent replay terminal differs")
        if self.control_id != identity(
            self,
            "control_id",
            "finance_v26_198_independent_terminal_replay_control:",
        ):
            raise ValueError("independent replay control identity differs")
        return self


class IndependentRuntimeReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    controls: tuple[IndependentReplayControl, ...] = Field(min_length=16, max_length=16)
    reachable_terminal_count: Literal[16] = 16
    distinct_job_count: Literal[16] = 16
    actual_invoke_count: Literal[16] = 16
    dispatcher_decision_count: Literal[16] = 16
    fresh_raw_count: Literal[16] = 16
    fresh_result_count: Literal[16] = 16
    independent_terminal_reconstruction_count: Literal[16] = 16
    independent_failure_locus_reconstruction_count: Literal[16] = 16
    independent_trace_reconstruction_count: Literal[16] = 16
    independent_outcome_reconstruction_count: Literal[16] = 16
    actual_raw_result_byte_match_count: Literal[32] = 32
    candidate_raw_result_byte_match_count: Literal[32] = 32
    old_fixture_complete_count: Literal[0] = 0
    old_complete_job_call_count: Literal[0] = 0
    exception_escape_count: Literal[0] = 0
    candidate_report_used_as_outcome_oracle: Literal[False] = False
    provider_calls: Literal[0] = 0
    development_outcomes: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentRuntimeReplayAudit:
        if (
            len({item.exact_job_id for item in self.controls}) != 16
            or len({item.observed_terminal_kind for item in self.controls}) != 16
        ):
            raise ValueError("independent replay denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_198_independent_runtime_replay_audit:",
        ):
            raise ValueError("independent runtime replay identity differs")
        return self


class DispatcherCodomainAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    dispatcher_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    registry_reachable_terminals: tuple[str, ...] = Field(min_length=16, max_length=16)
    dispatcher_literal_outputs: tuple[str, ...] = Field(min_length=16, max_length=16)
    actual_replay_outputs: tuple[str, ...] = Field(min_length=16, max_length=16)
    excluded_terminals: tuple[
        Literal["measurement_support_exit", "policy_horizon_exhausted"], ...
    ] = Field(min_length=2, max_length=2)
    registry_dispatcher_set_match: Literal[True] = True
    registry_actual_set_match: Literal[True] = True
    excluded_dispatcher_output_count: Literal[0] = 0
    excluded_actual_output_count: Literal[0] = 0
    output_codomains_independently_reconstructed: Literal[True] = True
    string_token_only_witness: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DispatcherCodomainAudit:
        reachable = set(self.registry_reachable_terminals)
        if (
            len(reachable) != 16
            or set(self.dispatcher_literal_outputs) != reachable
            or set(self.actual_replay_outputs) != reachable
            or set(self.excluded_terminals) & reachable
        ):
            raise ValueError("dispatcher codomain differs from reachable Registry")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_198_dispatcher_codomain_audit:",
        ):
            raise ValueError("dispatcher codomain audit identity differs")
        return self


class TerminalInjectionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    invoke_terminal_parameter_count: Literal[0] = 0
    complete_job_terminal_parameter_count: Literal[0] = 0
    client_plan_terminal_field_count: Literal[0] = 0
    caller_supplied_terminal_attempt_count: Literal[1] = 1
    caller_supplied_terminal_rejection_count: Literal[1] = 1
    expected_terminal_postcomparison_only: Literal[True] = True
    harness_terminal_injection_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> TerminalInjectionAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_198_terminal_injection_audit:",
        ):
            raise ValueError("terminal injection audit identity differs")
        return self


class AuthorizationOrderingControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    admitted: bool
    rejected: bool
    client_factory_count: int = Field(ge=0, le=1)
    kernel_writer_factory_count: int = Field(ge=0, le=1)
    outcome_writer_factory_count: int = Field(ge=0, le=1)
    credential_lookup_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> AuthorizationOrderingControl:
        if self.admitted == self.rejected:
            raise ValueError("authorization ordering control must admit xor reject")
        if self.control_id != identity(
            self,
            "control_id",
            "finance_v26_198_authorization_ordering_control:",
        ):
            raise ValueError("authorization ordering control identity differs")
        return self


class AuthorizationOrderingAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    controls: tuple[AuthorizationOrderingControl, ...] = Field(min_length=6, max_length=6)
    constructor_source_order_validated: Literal[True] = True
    guard_before_client_factory: Literal[True] = True
    guard_before_kernel_writer_factory: Literal[True] = True
    guard_before_outcome_writer_factory: Literal[True] = True
    guard_before_credential_lookup: Literal[True] = True
    invalid_control_factory_call_count: Literal[0] = 0
    invalid_control_credential_lookup_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> AuthorizationOrderingAudit:
        if len({item.control_name for item in self.controls}) != 6:
            raise ValueError("authorization ordering control set differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_198_authorization_ordering_audit:",
        ):
            raise ValueError("authorization ordering audit identity differs")
        return self


class LegacyCompletionBypassAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    v194_complete_job_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    successor_complete_job_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    old_fixture_complete_source_present: Literal[True] = True
    successor_calls_old_complete_job_count: Literal[0] = 0
    old_complete_job_runtime_call_count: Literal[0] = 0
    successor_fresh_writer_runtime_call_count: Literal[32] = 32
    future_online_entry_materialized: Literal[False] = False
    future_online_entry_requires_successor_kernel: Literal[True] = True
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> LegacyCompletionBypassAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_198_legacy_completion_bypass_audit:",
        ):
            raise ValueError("legacy completion bypass audit identity differs")
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
        if self.gate_count != len(self.gates) or self.passed_count != len(self.gates):
            raise ValueError("v26.198 static Gate denominator differs")
        if len({item.name for item in self.gates}) != len(self.gates):
            raise ValueError("v26.198 static Gate names differ")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_198_static_audit:",
        ):
            raise ValueError("v26.198 static audit identity differs")
        return self


class IndependentAuditDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    freeze_audit_id: str = Field(min_length=1)
    formal_rebuild_audit_id: str = Field(min_length=1)
    runtime_replay_audit_id: str = Field(min_length=1)
    dispatcher_codomain_audit_id: str = Field(min_length=1)
    terminal_injection_audit_id: str = Field(min_length=1)
    authorization_ordering_audit_id: str = Field(min_length=1)
    legacy_completion_bypass_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_artifact_backed_terminal_to_outcome_integration_repair_independent_"
        "audit_passed_online_execution_still_blocked"
    ]
    first_failed_gate: None = None
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> IndependentAuditDecision:
        if self.decision_id != identity(
            self,
            "decision_id",
            "finance_v26_198_independent_audit_decision:",
        ):
            raise ValueError("v26.198 decision identity differs")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    next_stage: Literal[
        "fresh_artifact_backed_terminal_to_outcome_integration_repair_"
        "online_execution_authorization_only"
    ] = NEXT_STAGE
    online_execution_authorized: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    job_192_execution_authorized: Literal[False] = False
    source_or_manifest_change_authorized: Literal[False] = False
    authority_contract_change_authorized: Literal[False] = False
    qa_change_authorized: Literal[False] = False
    mapper_state_vtdo_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_198_transition:",
        ):
            raise ValueError("v26.198 transition identity differs")
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
            raise ValueError("v26.198 artifact member set differs")
        if self.file_count != len(self.members) or self.total_byte_count != sum(
            item.byte_count for item in self.members
        ):
            raise ValueError("v26.198 artifact aggregate differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix=f"finance_v26_198_{self.scope}_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("v26.198 artifact Root differs")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            f"finance_v26_198_{self.scope}_artifact_manifest:",
        ):
            raise ValueError("v26.198 artifact Manifest identity differs")
        return self


class IndependentAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    freeze_audit_id: str = Field(min_length=1)
    formal_rebuild_audit_id: str = Field(min_length=1)
    runtime_replay_audit_id: str = Field(min_length=1)
    dispatcher_codomain_audit_id: str = Field(min_length=1)
    terminal_injection_audit_id: str = Field(min_length=1)
    authorization_ordering_audit_id: str = Field(min_length=1)
    legacy_completion_bypass_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    sealed_manifest_id: str = Field(min_length=1)
    sealed_artifact_root: str = Field(min_length=1)
    decision: Literal[
        "fresh_artifact_backed_terminal_to_outcome_integration_repair_independent_"
        "audit_passed_online_execution_still_blocked"
    ]
    v197_formal_file_match_count: Literal[48] = 48
    v197_formal_rebuild_byte_match_count: Literal[48] = 48
    independent_terminal_replay_count: Literal[16] = 16
    independent_raw_result_byte_match_count: Literal[32] = 32
    dispatcher_codomains_match: Literal[True] = True
    terminal_injection_count: Literal[0] = 0
    invalid_authorization_factory_call_count: Literal[0] = 0
    old_complete_job_runtime_call_count: Literal[0] = 0
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
    online_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> IndependentAuditReport:
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_198_terminal_outcome_repair_independent_audit_report:",
        ):
            raise ValueError("v26.198 Report identity differs")
        return self
