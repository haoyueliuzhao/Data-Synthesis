from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION = "capability_artifact_backed_outcome_independent_audit.v1"
PASSED_DECISION = "PASSED_INDEPENDENT_AUDIT"
FAILED_DECISION = "FAILED_INDEPENDENT_AUDIT"
NO_FURTHER_EXPERIMENT = "no_further_experiment_authorized_without_new_audit_decision"
REPAIR_ONLY = "artifact_backed_empirical_outcome_authority_repair_preflight_only"


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
    byte_count: int = Field(gt=0)
    source_kind: str = Field(min_length=1)


class IndependentAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    consumed_stage: Literal["artifact_backed_empirical_outcome_authority_independent_audit_only"]
    external_audit_input: FileBinding
    audited_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    audited_source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    audited_artifact_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    audited_artifact_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    audited_report_id: str = Field(min_length=1)
    audited_artifact_root: str = Field(min_length=1)
    provider_calls_authorized: Literal[False] = False
    online_development_authorized: Literal[False] = False
    formal_empirical_rows_authorized: Literal[False] = False
    mapper_state_frequency_authorized: Literal[False] = False
    contribution_vtdo_student_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> IndependentAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_artifact_backed_independent_audit_authorization:",
        ):
            raise ValueError("independent audit authorization identity is invalid")
        return self


class SourceRebuildAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_archive: FileBinding
    embedded_commit_match: Literal[True] = True
    reconstructed_tree_match: Literal[True] = True
    exact_change_surface_count: Literal[7] = 7
    exact_change_surface_match_count: Literal[7] = 7
    rebuilt_file_count: Literal[398] = 398
    rebuilt_file_match_count: Literal[398] = 398
    rebuilt_byte_match_count: Literal[398] = 398
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> SourceRebuildAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_artifact_backed_source_rebuild_audit:",
        ):
            raise ValueError("Source rebuild audit identity is invalid")
        return self


class FormalArtifactReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    artifact_manifest_id: str = Field(min_length=1)
    artifact_root: str = Field(min_length=1)
    directory_file_count: Literal[398] = 398
    manifest_member_count: Literal[397] = 397
    manifest_member_match_count: Literal[397] = 397
    manifest_member_byte_count: int = Field(gt=0)
    directory_byte_count: int = Field(gt=0)
    canonical_formal_json_count: int = Field(ge=13)
    exact_report_detail_binding_count: int = Field(ge=10)
    exact_report_detail_binding_match_count: int = Field(ge=10)
    historical_artifact_mutation_count: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FormalArtifactReplayAudit:
        if self.exact_report_detail_binding_count != self.exact_report_detail_binding_match_count:
            raise ValueError("formal report detail bindings do not all match")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_artifact_backed_formal_replay_audit:",
        ):
            raise ValueError("Formal artifact replay identity is invalid")
        return self


class SemanticReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    registry_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    manifest_job_count: Literal[192] = 192
    bundle_count: Literal[192] = 192
    exact_job_match_count: Literal[192] = 192
    raw_payload_count: Literal[192] = 192
    result_payload_count: Literal[192] = 192
    actual_artifact_byte_match_count: Literal[384] = 384
    canonical_artifact_match_count: Literal[384] = 384
    payload_identity_match_count: Literal[384] = 384
    descriptor_identity_match_count: Literal[384] = 384
    attempt_identity_match_count: int = Field(gt=0)
    trace_identity_match_count: Literal[192] = 192
    row_identity_match_count: Literal[192] = 192
    exact_component_sequence_match_count: Literal[192] = 192
    terminal_validity_match_count: Literal[192] = 192
    failure_locus_match_count: Literal[192] = 192
    parent_chain_match_count: Literal[192] = 192
    production_evaluation_match: Literal[True] = True
    formal_empirical_rows: Literal[0] = 0
    formal_empirical_estimates: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> SemanticReplayAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_artifact_backed_semantic_replay_audit:",
        ):
            raise ValueError("Semantic replay audit identity is invalid")
        return self


class ValidityState(FrozenModel):
    final_base_valid: bool
    final_mechanism_qualified: bool
    final_qualified_valid: Literal[False] = False
    derived_locus_stages: tuple[str, ...]
    production_entry_accepted: Literal[True] = True
    independent_projection_match: Literal[True] = True


class ValidityFactorizationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    states: tuple[ValidityState, ValidityState]
    distinct_state_count: Literal[2] = 2
    semantic_state_preservation_count: Literal[2] = 2
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ValidityFactorizationAudit:
        pairs = {(item.final_base_valid, item.final_mechanism_qualified) for item in self.states}
        if pairs != {(True, False), (False, True)}:
            raise ValueError("mixed validity states are not the exact independent pair")
        if any(item.final_qualified_valid for item in self.states):
            raise ValueError("mixed validity state changed Qualified conjunction")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_independent_validity_factorization_audit:",
        ):
            raise ValueError("Validity factorization audit identity is invalid")
        return self


class NegativeControl(FrozenModel):
    control_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    target: str = Field(min_length=1)
    fully_rehashed: bool
    rejected: Literal[True] = True
    actual_exception_type: Literal["ValueError"] = "ValueError"
    rejection_reason: str = Field(min_length=1)
    exact_expected_reason: str | None = None
    exact_reason_match: bool

    @model_validator(mode="after")
    def validate_control(self) -> NegativeControl:
        if self.exact_expected_reason is not None and not self.exact_reason_match:
            raise ValueError("negative control rejected at the wrong Gate")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"control_id"}, warnings=False),
            prefix="finance_v26_artifact_backed_independent_control:",
        )
        if self.control_id != expected:
            raise ValueError("negative control identity is invalid")
        return self


class NegativeControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    controls: tuple[NegativeControl, ...] = Field(min_length=13, max_length=13)
    control_count: Literal[13] = 13
    rejected_control_count: Literal[13] = 13
    fully_rehashed_control_count: int = Field(ge=6)
    exact_reason_control_count: Literal[2] = 2
    exact_reason_match_count: Literal[2] = 2
    accepted_attack_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> NegativeControlAudit:
        if len(self.controls) != self.control_count:
            raise ValueError("negative control denominator changed")
        if sum(item.fully_rehashed for item in self.controls) != self.fully_rehashed_control_count:
            raise ValueError("fully rehashed control count changed")
        exact = tuple(item for item in self.controls if item.exact_expected_reason is not None)
        if (
            len(exact) != self.exact_reason_control_count
            or sum(item.exact_reason_match for item in exact) != self.exact_reason_match_count
        ):
            raise ValueError("exact rejection reason controls differ")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_artifact_backed_production_destructive_audit:",
        ):
            raise ValueError("Negative control audit identity is invalid")
        return self


class StaticGate(FrozenModel):
    name: str = Field(min_length=1)
    passed: Literal[True] = True
    evidence_ids: tuple[str, ...] = Field(min_length=1)


class StaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGate, ...] = Field(min_length=12)
    gate_count: int = Field(ge=12)
    passed_gate_count: int = Field(ge=12)
    failed_gate_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StaticAudit:
        if len(self.gates) != self.gate_count or self.gate_count != self.passed_gate_count:
            raise ValueError("independent static Gate partition differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_artifact_backed_independent_static_audit:",
        ):
            raise ValueError("Static audit identity is invalid")
        return self


class IndependentAuditDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_rebuild_audit_id: str = Field(min_length=1)
    formal_replay_audit_id: str = Field(min_length=1)
    semantic_replay_audit_id: str = Field(min_length=1)
    factorization_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    decision: Literal["PASSED_INDEPENDENT_AUDIT", "FAILED_INDEPENDENT_AUDIT"]
    online_execution_authorized: Literal[False] = False
    formal_empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    provider_calls: Literal[0] = 0
    next_stage: Literal[
        "no_further_experiment_authorized_without_new_audit_decision",
        "artifact_backed_empirical_outcome_authority_repair_preflight_only",
    ]
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> IndependentAuditDecision:
        expected_stage = NO_FURTHER_EXPERIMENT if self.decision == PASSED_DECISION else REPAIR_ONLY
        if self.next_stage != expected_stage:
            raise ValueError("independent audit decision and transition differ")
        if self.decision_id != identity(
            self,
            "decision_id",
            "finance_v26_artifact_backed_independent_audit_decision:",
        ):
            raise ValueError("Independent audit decision identity is invalid")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    next_stage: Literal[
        "no_further_experiment_authorized_without_new_audit_decision",
        "artifact_backed_empirical_outcome_authority_repair_preflight_only",
    ]
    provider_execution_authorized: Literal[False] = False
    online_development_authorized: Literal[False] = False
    empirical_rows_authorized: Literal[False] = False
    empirical_estimates_authorized: Literal[False] = False
    confirmation_authorized: Literal[False] = False
    mapper_state_frequency_authorized: Literal[False] = False
    contribution_vtdo_student_authorized: Literal[False] = False
    historical_rewrite_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_artifact_backed_independent_audit_transition:",
        ):
            raise ValueError("Prospective transition identity is invalid")
        return self


class ArtifactManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    artifact_root: str = Field(min_length=1)
    files: tuple[FileBinding, ...] = Field(min_length=10)
    file_count: int = Field(ge=10)
    total_byte_count: int = Field(gt=0)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> ArtifactManifest:
        if tuple(item.relative_path for item in self.files) != tuple(
            sorted({item.relative_path for item in self.files})
        ):
            raise ValueError("artifact manifest paths are not exact and sorted")
        if self.file_count != len(self.files) or self.total_byte_count != sum(
            item.byte_count for item in self.files
        ):
            raise ValueError("artifact manifest aggregate differs")
        expected_root = canonical_hash(
            [item.model_dump(mode="json") for item in self.files],
            prefix="finance_v26_artifact_backed_independent_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("artifact manifest content Root is invalid")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            "finance_v26_artifact_backed_independent_artifact_manifest:",
        ):
            raise ValueError("artifact manifest identity is invalid")
        return self


class IndependentAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_rebuild_audit_id: str = Field(min_length=1)
    formal_replay_audit_id: str = Field(min_length=1)
    semantic_replay_audit_id: str = Field(min_length=1)
    factorization_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    artifact_manifest_id: str | None = None
    audited_report_id: str = Field(min_length=1)
    audited_artifact_root: str = Field(min_length=1)
    exact_artifact_count: Literal[398] = 398
    replayed_job_count: Literal[192] = 192
    replayed_artifact_count: Literal[384] = 384
    negative_control_count: Literal[13] = 13
    rejected_negative_control_count: Literal[13] = 13
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    formal_empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    online_execution_authorized: Literal[False] = False
    decision: Literal["PASSED_INDEPENDENT_AUDIT", "FAILED_INDEPENDENT_AUDIT"]
    next_stage: Literal[
        "no_further_experiment_authorized_without_new_audit_decision",
        "artifact_backed_empirical_outcome_authority_repair_preflight_only",
    ]
    detail_files: tuple[FileBinding, ...] = ()
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> IndependentAuditReport:
        if self.decision == PASSED_DECISION and self.next_stage != NO_FURTHER_EXPERIMENT:
            raise ValueError("passed audit expands authorization without a new decision")
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_artifact_backed_independent_audit_report:",
        ):
            raise ValueError("Independent audit report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    authorization: IndependentAuditAuthorization
    source_rebuild: SourceRebuildAudit
    formal_replay: FormalArtifactReplayAudit
    semantic_replay: SemanticReplayAudit
    factorization: ValidityFactorizationAudit
    destructive: NegativeControlAudit
    static: StaticAudit
    decision: IndependentAuditDecision
    transition: ProspectiveTransition
    report: IndependentAuditReport


__all__ = [
    "ArtifactManifest",
    "BuildProducts",
    "FAILED_DECISION",
    "FileBinding",
    "FormalArtifactReplayAudit",
    "IndependentAuditAuthorization",
    "IndependentAuditDecision",
    "IndependentAuditReport",
    "NO_FURTHER_EXPERIMENT",
    "NegativeControl",
    "NegativeControlAudit",
    "PASSED_DECISION",
    "ProspectiveTransition",
    "REPAIR_ONLY",
    "SCHEMA_VERSION",
    "SemanticReplayAudit",
    "SourceRebuildAudit",
    "StaticAudit",
    "StaticGate",
    "ValidityFactorizationAudit",
    "ValidityState",
    "identity",
    "make_identity_model",
]
