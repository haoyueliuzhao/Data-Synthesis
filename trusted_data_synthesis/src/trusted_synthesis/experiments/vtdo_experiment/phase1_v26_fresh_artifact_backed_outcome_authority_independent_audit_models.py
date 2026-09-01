from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION = "fresh_artifact_backed_outcome_authority_independent_audit.v1"
AUTHORIZED_STAGE = "fresh_artifact_backed_outcome_authority_preflight_independent_audit_only"
REPAIR_STAGE = "fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_only"


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


def validate_identity(value: BaseModel, field: str, prefix: str) -> bool:
    return getattr(value, field) == identity(value, field, prefix)


class FileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class IndependentAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    audit_sha256: Literal["19531134d019d4724a97602c14a95da57db6a05b28e32c2568bc8faeb5937ed9"]
    audit_byte_count: Literal[8957] = 8957
    consumed_stage: Literal[
        "fresh_artifact_backed_outcome_authority_preflight_independent_audit_only"
    ] = "fresh_artifact_backed_outcome_authority_preflight_independent_audit_only"
    conditional_successor: Literal[
        "frozen_v26_194_192_job_online_development_execution_only_if_all_three_audit_gates_pass"
    ]
    provider_calls_authorized: Literal[False] = False
    online_execution_authorized_before_audit: Literal[False] = False
    outcome_contract_change_authorized: Literal[False] = False
    qa_change_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> IndependentAuditAuthorization:
        if not validate_identity(
            self,
            "authorization_id",
            "finance_v26_196_external_independent_audit_authorization:",
        ):
            raise ValueError("v26.196 external authorization identity differs")
        return self


class V195FreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_commit: Literal["9c48c3bf308a93a908bfcea0dce2c3315044dd3d"]
    source_tree: Literal["ec0875ab2325502563dadb528c4a893a31c7293c"]
    artifact_commit: Literal["4ce98dbd711f3264e62ce2c6ee3d268c0144a113"]
    artifact_tree: Literal["8a16aee93c24fb07d4657e829ee086214515ed3d"]
    report_id: Literal[
        "finance_v26_195_fresh_outcome_preflight_report:"
        "ec2ae9613cd4110a41eb74de005a2ec0e4c6aa0e062dde76a7e6ff5f9eba5264"
    ]
    sealed_artifact_root: Literal[
        "finance_v26_195_sealed_evidence_artifact_root:"
        "be910ff7aa14a082cf83c218968937a140c09a212761304f247d982ad2d0762c"
    ]
    distribution_artifact_root: Literal[
        "finance_v26_195_distribution_artifact_root:"
        "ad4a020b60938855d730603033cfc62ba73d9498b69897f20410d4bcf56d1a77"
    ]
    formal_file_count: Literal[403] = 403
    formal_byte_count: Literal[2300542] = 2_300_542
    raw_file_count: Literal[192] = 192
    result_file_count: Literal[192] = 192
    root_file_count: Literal[19] = 19
    upstream_constant_match_count: int = Field(ge=16)
    upstream_constant_count: int = Field(ge=16)
    historical_mutation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> V195FreezeAudit:
        if self.upstream_constant_match_count != self.upstream_constant_count:
            raise ValueError("v26.195 upstream constants do not all match")
        if not validate_identity(self, "audit_id", "finance_v26_196_v195_freeze_audit:"):
            raise ValueError("v26.195 Freeze audit identity differs")
        return self


class FormalRebuildAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    v195_freeze_audit_id: str = Field(min_length=1)
    detached_source_commit_match: Literal[True] = True
    detached_source_tree_match: Literal[True] = True
    rebuilt_file_count: Literal[403] = 403
    frozen_file_count: Literal[403] = 403
    exact_path_match_count: Literal[403] = 403
    exact_sha256_match_count: Literal[403] = 403
    exact_byte_count_match_count: Literal[403] = 403
    exact_byte_match_count: Literal[403] = 403
    rebuilt_byte_count: Literal[2300542] = 2_300_542
    canonical_json_count: Literal[402] = 402
    symlink_count: Literal[0] = 0
    nonregular_file_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FormalRebuildAudit:
        if not validate_identity(
            self,
            "audit_id",
            "finance_v26_196_v195_formal_rebuild_audit:",
        ):
            raise ValueError("v26.195 formal rebuild audit identity differs")
        return self


class TerminalControlObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    target_terminal_kind: str = Field(min_length=1)
    exact_job_id: str = Field(min_length=1)
    actual_runner_entry: Literal[
        "AuthoritativeJsonExplicitExecutionKernel.invoke_then_complete_job"
    ]
    actual_completion_symbol: Literal[
        "json_explicit_authoritative_execution_kernel."
        "AuthoritativeJsonExplicitExecutionKernel.complete_job"
    ]
    actual_writer_symbol: Literal[
        "json_explicit_authoritative_execution_kernel.NoReplaceKernelJournalWriter"
    ]
    zero_provider_fixture_invocation_count: Literal[1] = 1
    actual_raw_written: Literal[True] = True
    actual_result_written: Literal[True] = True
    raw_before_result: Literal[True] = True
    actual_raw_canonical_json: Literal[True] = True
    actual_result_canonical_json: Literal[True] = True
    observed_terminal_value: Literal["fixture_complete"] = "fixture_complete"
    target_terminal_dispatched: Literal[False] = False
    fresh_typed_writer_reached: Literal[False] = False
    fresh_raw_payload_materialized: Literal[False] = False
    fresh_result_payload_materialized: Literal[False] = False
    fresh_trace_reconstructed: Literal[False] = False
    fresh_outcome_reconstructed: Literal[False] = False
    production_exception_escape: Literal[False] = False
    first_failed_seam: Literal[
        "v26_194_complete_job_emits_fixture_complete_without_terminal_dispatch"
    ]
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> TerminalControlObservation:
        if not validate_identity(
            self,
            "observation_id",
            "finance_v26_196_terminal_control_observation:",
        ):
            raise ValueError("terminal control observation identity differs")
        return self


class ProductionTerminalTotalityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    controls: tuple[TerminalControlObservation, ...] = Field(min_length=16, max_length=16)
    reachable_terminal_count: Literal[16] = 16
    attempted_control_count: Literal[16] = 16
    actual_old_raw_result_control_count: Literal[16] = 16
    production_terminal_to_fresh_outcome_success_count: Literal[0] = 0
    failed_control_count: Literal[16] = 16
    unique_target_terminal_count: Literal[16] = 16
    python_escape_count: Literal[0] = 0
    pydantic_escape_count: Literal[0] = 0
    value_error_escape_count: Literal[0] = 0
    gate_passed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ProductionTerminalTotalityAudit:
        if len({item.target_terminal_kind for item in self.controls}) != 16:
            raise ValueError("terminal totality target denominator differs")
        if any(item.target_terminal_dispatched for item in self.controls):
            raise ValueError("terminal integration failure was silently promoted")
        if not validate_identity(
            self,
            "audit_id",
            "finance_v26_196_production_terminal_totality_audit:",
        ):
            raise ValueError("terminal totality audit identity differs")
        return self


class NotApplicableTerminalExclusionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    terminal_kinds: tuple[
        Literal["measurement_support_exit", "policy_horizon_exhausted"],
        Literal["measurement_support_exit", "policy_horizon_exhausted"],
    ]
    exact_not_applicable_count: Literal[2] = 2
    empirical_admission_attempt_count: Literal[2] = 2
    empirical_admission_rejection_count: Literal[2] = 2
    empirical_denominator_entry_count: Literal[0] = 0
    exact_rejection_reason: Literal[
        "empirical evaluation remains unauthorized pending independent audit"
    ]
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> NotApplicableTerminalExclusionAudit:
        if set(self.terminal_kinds) != {
            "measurement_support_exit",
            "policy_horizon_exhausted",
        }:
            raise ValueError("not-applicable terminal partition differs")
        if not validate_identity(
            self,
            "audit_id",
            "finance_v26_196_not_applicable_terminal_exclusion_audit:",
        ):
            raise ValueError("not-applicable terminal exclusion identity differs")
        return self


class AuthorizationControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    rejected: bool
    rejection_reason: str = Field(min_length=1)
    credential_lookup_count: Literal[0] = 0
    client_construction_count: Literal[0] = 0
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_control(self) -> AuthorizationControl:
        if not validate_identity(
            self,
            "control_id",
            "finance_v26_196_online_authorization_control:",
        ):
            raise ValueError("online authorization control identity differs")
        return self


class OnlineAuthorizationParentAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    controls: tuple[AuthorizationControl, ...] = Field(min_length=4, max_length=4)
    missing_parent_rejected: Literal[True] = True
    forged_parent_rejected: Literal[True] = True
    self_declared_parent_rejected: Literal[True] = True
    legal_parent_valid_for_independent_audit: Literal[True] = True
    legal_parent_accepted_by_online_precredential_guard: Literal[False] = False
    online_precredential_guard_exists: Literal[False] = False
    six_contract_identity_change_count: Literal[0] = 0
    gate_passed: Literal[False] = False
    credential_lookup_count: Literal[0] = 0
    client_construction_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> OnlineAuthorizationParentAudit:
        if len({item.control_name for item in self.controls}) != 4:
            raise ValueError("online authorization control denominator differs")
        if not validate_identity(
            self,
            "audit_id",
            "finance_v26_196_online_authorization_parent_audit:",
        ):
            raise ValueError("online authorization parent audit identity differs")
        return self


class StaticGate(FrozenModel):
    name: str = Field(min_length=1)
    passed: bool
    evidence_ids: tuple[str, ...] = Field(min_length=1)


class StaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGate, ...] = Field(min_length=8)
    gate_count: int = Field(ge=8)
    passed_count: int = Field(ge=1)
    failed_count: int = Field(ge=1)
    provider_calls: Literal[0] = 0
    development_outcomes: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StaticAudit:
        if (
            self.gate_count != len(self.gates)
            or self.passed_count != sum(item.passed for item in self.gates)
            or self.failed_count != sum(not item.passed for item in self.gates)
            or len({item.name for item in self.gates}) != len(self.gates)
        ):
            raise ValueError("v26.196 static Gate aggregate differs")
        if not validate_identity(self, "audit_id", "finance_v26_196_static_audit:"):
            raise ValueError("v26.196 static audit identity differs")
        return self


class IndependentAuditDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    formal_rebuild_audit_id: str = Field(min_length=1)
    terminal_totality_audit_id: str = Field(min_length=1)
    authorization_parent_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_outcome_authority_independent_audit_failed_at_terminal_to_persistence_integration"
    ]
    first_failed_gate: Literal["production_terminal_to_fresh_outcome_totality"]
    first_failed_seam: Literal[
        "v26_194_complete_job_emits_fixture_complete_without_terminal_dispatch"
    ]
    online_execution_authorized: Literal[False] = False
    next_stage: Literal[
        "fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_only"
    ] = "fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_only"
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> IndependentAuditDecision:
        if not validate_identity(
            self,
            "decision_id",
            "finance_v26_196_independent_audit_decision:",
        ):
            raise ValueError("v26.196 independent audit decision identity differs")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    next_stage: Literal[
        "fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_only"
    ] = "fresh_artifact_backed_terminal_to_outcome_integration_repair_preflight_only"
    permitted_change: Literal[
        "first_terminal_to_fresh_outcome_and_external_authorization_ingress_seam_only"
    ]
    online_execution_authorized: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    source_task_or_manifest_change_authorized: Literal[False] = False
    six_outcome_contract_semantic_change_authorized: Literal[False] = False
    qa_change_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if not validate_identity(self, "transition_id", "finance_v26_196_transition:"):
            raise ValueError("v26.196 transition identity differs")
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
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("v26.196 artifact member set differs")
        if self.file_count != len(self.members) or self.total_byte_count != sum(
            item.byte_count for item in self.members
        ):
            raise ValueError("v26.196 artifact aggregate differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix=f"finance_v26_196_{self.scope}_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("v26.196 artifact Root differs")
        if not validate_identity(
            self,
            "manifest_id",
            f"finance_v26_196_{self.scope}_artifact_manifest:",
        ):
            raise ValueError("v26.196 artifact Manifest identity differs")
        return self


class IndependentAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    v195_freeze_audit_id: str = Field(min_length=1)
    formal_rebuild_audit_id: str = Field(min_length=1)
    terminal_totality_audit_id: str = Field(min_length=1)
    not_applicable_audit_id: str = Field(min_length=1)
    authorization_parent_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    sealed_manifest_id: str = Field(min_length=1)
    sealed_artifact_root: str = Field(min_length=1)
    decision: Literal[
        "fresh_outcome_authority_independent_audit_failed_at_terminal_to_persistence_integration"
    ]
    v195_formal_rebuild_passed: Literal[True] = True
    production_terminal_totality_passed: Literal[False] = False
    external_online_authorization_ingress_passed: Literal[False] = False
    reachable_terminal_count: Literal[16] = 16
    production_terminal_to_fresh_outcome_success_count: Literal[0] = 0
    not_applicable_empirical_entry_count: Literal[0] = 0
    online_development_execution_authorized: Literal[False] = False
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
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> IndependentAuditReport:
        if not validate_identity(
            self,
            "report_id",
            "finance_v26_196_fresh_outcome_independent_audit_report:",
        ):
            raise ValueError("v26.196 independent audit Report identity differs")
        return self
