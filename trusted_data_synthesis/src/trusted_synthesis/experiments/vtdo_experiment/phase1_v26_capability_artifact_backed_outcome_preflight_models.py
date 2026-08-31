from __future__ import annotations

from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.authoritative_artifact_backed_outcome import (
    ArtifactBackedOutcomeContract,
    ArtifactBackedPreflightEvaluation,
)
from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "capability_artifact_backed_outcome_preflight.v1"
AUTHORIZED_STAGE: Final = (
    "artifact_backed_terminal_validity_factorization_and_"
    "failure_locus_reconstruction_preflight_only"
)
NEXT_STAGE: Final = "artifact_backed_empirical_outcome_authority_independent_audit_only"


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
    byte_count: int = Field(ge=0)
    source_kind: Literal[
        "v26_181_formal_artifact",
        "v26_182_formal_artifact",
        "v26_186_source",
        "v26_186_formal_artifact",
        "scripted_raw_artifact",
        "scripted_result_artifact",
    ]


class PreflightAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    v26_182_report_id: str = Field(min_length=1)
    v26_182_gate_decision_id: str = Field(min_length=1)
    consumed_stage: Literal[
        "artifact_backed_terminal_validity_factorization_and_"
        "failure_locus_reconstruction_preflight_only"
    ] = AUTHORIZED_STAGE
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_archive_byte_count: int = Field(gt=0)
    provider_calls_authorized: Literal[False] = False
    online_development_authorized: Literal[False] = False
    empirical_outcome_authorized: Literal[False] = False
    mapper_state_frequency_authorized: Literal[False] = False
    contribution_vtdo_student_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> PreflightAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_artifact_backed_outcome_authorization:",
        ):
            raise ValueError("artifact-backed authorization identity is invalid")
        return self


class PredecessorFreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    v26_181_report_id: str = Field(min_length=1)
    v26_182_report_id: str = Field(min_length=1)
    v26_182_gate_decision_id: str = Field(min_length=1)
    v26_181_files: tuple[FileBinding, ...] = Field(min_length=15, max_length=15)
    v26_182_files: tuple[FileBinding, ...] = Field(min_length=8, max_length=8)
    v26_181_file_match_count: Literal[15] = 15
    v26_182_file_match_count: Literal[8] = 8
    failed_gate_count: Literal[5] = 5
    historical_artifact_mutation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorFreezeAudit:
        if tuple(item.relative_path for item in self.v26_181_files) != tuple(
            sorted(item.relative_path for item in self.v26_181_files)
        ):
            raise ValueError("v26.181 predecessor files are not canonical")
        if tuple(item.relative_path for item in self.v26_182_files) != tuple(
            sorted(item.relative_path for item in self.v26_182_files)
        ):
            raise ValueError("v26.182 predecessor files are not canonical")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_artifact_backed_predecessor_freeze:",
        ):
            raise ValueError("artifact-backed predecessor freeze identity is invalid")
        return self


class OutcomeContractAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    predecessor_freeze_id: str = Field(min_length=1)
    contract: ArtifactBackedOutcomeContract
    registry_id: str = Field(min_length=1)
    predecessor_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    exact_job_count: Literal[192] = 192
    exact_parent_match_count: Literal[5] = 5
    formal_empirical_rows_materialized: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> OutcomeContractAudit:
        if (
            self.contract.predecessor_registry_id != self.registry_id
            or self.contract.predecessor_contract_id != self.predecessor_contract_id
            or self.contract.manifest_id != self.manifest_id
            or self.contract.runner_id != self.runner_id
        ):
            raise ValueError("Contract audit parent projection differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_artifact_backed_outcome_contract_audit:",
        ):
            raise ValueError("artifact-backed Contract audit identity is invalid")
        return self


class FactorizationControl(FrozenModel):
    control_id: str = Field(min_length=1)
    final_base_valid: bool
    final_mechanism_qualified: bool
    final_qualified_valid: Literal[False] = False
    reconstructed_base_valid: bool
    reconstructed_mechanism_qualified: bool
    reconstructed_qualified_valid: Literal[False] = False
    derived_locus_stages: tuple[str, ...] = Field(min_length=1, max_length=2)
    semantic_state_preserved: Literal[True] = True

    @model_validator(mode="after")
    def validate_control(self) -> FactorizationControl:
        if (
            self.final_base_valid != self.reconstructed_base_valid
            or self.final_mechanism_qualified != self.reconstructed_mechanism_qualified
            or self.final_qualified_valid != self.reconstructed_qualified_valid
        ):
            raise ValueError("completed-invalid factorization lost semantic state")
        if self.final_qualified_valid != bool(
            self.final_base_valid and self.final_mechanism_qualified
        ):
            raise ValueError("factorization control Qualified value is not a conjunction")
        return self


class TerminalValidityFactorizationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    controls: tuple[FactorizationControl, FactorizationControl]
    mixed_state_count: Literal[2] = 2
    semantic_state_preservation_count: Literal[2] = 2
    old_collapsed_state_count: Literal[2] = 2
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> TerminalValidityFactorizationAudit:
        observed = {
            (item.final_base_valid, item.final_mechanism_qualified) for item in self.controls
        }
        if observed != {(True, False), (False, True)}:
            raise ValueError("factorization audit lacks both mixed invalid states")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_terminal_validity_factorization_audit:",
        ):
            raise ValueError("terminal factorization audit identity is invalid")
        return self


class RejectionControl(FrozenModel):
    control_id: str = Field(min_length=1)
    family: Literal[
        "diagnostic_empirical_admission",
        "failure_locus_reconstruction",
        "artifact_byte_authenticity",
        "authoritative_parent_revalidation",
    ]
    target: str = Field(min_length=1)
    fully_rehashed: bool
    expected_exception_type: Literal["ValueError"] = "ValueError"
    actual_exception_type: Literal["ValueError"] = "ValueError"
    rejection_reason: str = Field(min_length=1)
    rejected: Literal[True] = True
    counted: Literal[True] = True


class EmpiricalAdmissionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    controls: tuple[RejectionControl, RejectionControl]
    exact_attack_catalog_size: Literal[192] = 192
    diagnostic_terminal_count: Literal[2] = 2
    rejection_count: Literal[2] = 2
    empirical_evaluation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> EmpiricalAdmissionAudit:
        if {item.target for item in self.controls} != {
            "measurement_support_exit",
            "policy_horizon_exhausted",
        }:
            raise ValueError("empirical admission audit lacks exact diagnostic policies")
        if any(item.family != "diagnostic_empirical_admission" for item in self.controls):
            raise ValueError("empirical admission control family differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_artifact_backed_empirical_admission_audit:",
        ):
            raise ValueError("empirical admission audit identity is invalid")
        return self


class FailureLocusReconstructionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    scripted_row_count: Literal[192] = 192
    independently_reconstructed_row_count: Literal[192] = 192
    controls: tuple[RejectionControl, RejectionControl]
    invented_locus_rejection_count: Literal[2] = 2
    caller_supplied_locus_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FailureLocusReconstructionAudit:
        if any(item.family != "failure_locus_reconstruction" for item in self.controls):
            raise ValueError("FailureLocus control family differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_failure_locus_reconstruction_audit:",
        ):
            raise ValueError("FailureLocus reconstruction audit identity is invalid")
        return self


class ArtifactByteAuthenticityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    raw_artifact_count: Literal[192] = 192
    result_artifact_count: Literal[192] = 192
    byte_match_count: Literal[384] = 384
    sha256_match_count: Literal[384] = 384
    byte_count_match_count: Literal[384] = 384
    canonical_json_match_count: Literal[384] = 384
    controls: tuple[RejectionControl, RejectionControl]
    changed_byte_rejection_count: Literal[2] = 2
    path_only_descriptor_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ArtifactByteAuthenticityAudit:
        if {item.target for item in self.controls} != {"Raw", "Result"}:
            raise ValueError("artifact-byte audit lacks Raw and Result controls")
        if any(item.family != "artifact_byte_authenticity" for item in self.controls):
            raise ValueError("artifact-byte control family differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_artifact_byte_authenticity_repair_audit:",
        ):
            raise ValueError("artifact-byte authenticity audit identity is invalid")
        return self


class ParentRevalidationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    controls: tuple[
        RejectionControl,
        RejectionControl,
        RejectionControl,
        RejectionControl,
        RejectionControl,
    ]
    parent_types: tuple[str, ...] = Field(min_length=5, max_length=5)
    invalid_parent_rejection_count: Literal[5] = 5
    stale_parent_acceptance_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ParentRevalidationAudit:
        expected = ("Contract", "Job", "Manifest", "Registry", "Runner")
        if self.parent_types != expected:
            raise ValueError("parent revalidation denominator is not exact")
        if any(item.family != "authoritative_parent_revalidation" for item in self.controls):
            raise ValueError("parent revalidation control family differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_authoritative_parent_revalidation_repair_audit:",
        ):
            raise ValueError("parent revalidation repair audit identity is invalid")
        return self


class ScriptedEvidenceDagAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    evaluation: ArtifactBackedPreflightEvaluation
    raw_descriptor_count: Literal[192] = 192
    result_descriptor_count: Literal[192] = 192
    trace_count: Literal[192] = 192
    outcome_row_count: Literal[192] = 192
    artifact_file_count: Literal[384] = 384
    empirical_row_count: Literal[0] = 0
    empirical_evaluation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ScriptedEvidenceDagAudit:
        if self.evaluation.contract_id != self.contract_id:
            raise ValueError("scripted evidence audit crosses its Contract")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_artifact_backed_scripted_evidence_dag_audit:",
        ):
            raise ValueError("scripted evidence DAG audit identity is invalid")
        return self


class StaticGate(FrozenModel):
    gate_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    passed: Literal[True] = True
    evidence_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_gate(self) -> StaticGate:
        if self.gate_id != identity(
            self,
            "gate_id",
            "finance_v26_artifact_backed_static_gate:",
        ):
            raise ValueError("artifact-backed static Gate identity is invalid")
        return self


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
        if self.gate_count != len(self.gates) or self.passed_gate_count != len(self.gates):
            raise ValueError("static Gate totals differ")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_artifact_backed_static_audit:",
        ):
            raise ValueError("artifact-backed static audit identity is invalid")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    predecessor_freeze_id: str = Field(min_length=1)
    contract_audit_id: str = Field(min_length=1)
    factorization_audit_id: str = Field(min_length=1)
    admission_audit_id: str = Field(min_length=1)
    locus_audit_id: str = Field(min_length=1)
    artifact_audit_id: str = Field(min_length=1)
    parent_audit_id: str = Field(min_length=1)
    evidence_dag_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    next_stage: Literal["artifact_backed_empirical_outcome_authority_independent_audit_only"] = (
        NEXT_STAGE
    )
    online_development_authorized: Literal[False] = False
    empirical_outcome_authorized: Literal[False] = False
    mapper_state_frequency_authorized: Literal[False] = False
    contribution_vtdo_student_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_artifact_backed_outcome_transition:",
        ):
            raise ValueError("artifact-backed transition identity is invalid")
        return self


class ArtifactManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    artifact_root: str = Field(min_length=1)
    files: tuple[FileBinding, ...] = Field(min_length=1)
    file_count: int = Field(gt=0)
    total_byte_count: int = Field(gt=0)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> ArtifactManifest:
        if self.file_count != len(self.files):
            raise ValueError("formal artifact Manifest count differs")
        if self.total_byte_count != sum(item.byte_count for item in self.files):
            raise ValueError("formal artifact Manifest byte count differs")
        if tuple(item.relative_path for item in self.files) != tuple(
            sorted(item.relative_path for item in self.files)
        ):
            raise ValueError("formal artifact Manifest is not canonical")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            "finance_v26_artifact_backed_artifact_manifest:",
        ):
            raise ValueError("formal artifact Manifest identity is invalid")
        return self


class PreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    predecessor_freeze_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    factorization_audit_id: str = Field(min_length=1)
    admission_audit_id: str = Field(min_length=1)
    locus_audit_id: str = Field(min_length=1)
    artifact_audit_id: str = Field(min_length=1)
    parent_audit_id: str = Field(min_length=1)
    evidence_dag_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    artifact_manifest_id: str | None = None
    failed_v26_182_gate_count: Literal[5] = 5
    repaired_gate_count: Literal[5] = 5
    scripted_job_count: Literal[192] = 192
    scripted_artifact_count: Literal[384] = 384
    fully_rehashed_negative_control_count: int = Field(ge=4)
    negative_control_rejection_count: int = Field(ge=9)
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    formal_empirical_rows_materialized: Literal[0] = 0
    empirical_estimates_materialized: Literal[0] = 0
    online_execution_authorized: Literal[False] = False
    mapper_state_frequency_authorized: Literal[False] = False
    contribution_vtdo_student_authorized: Literal[False] = False
    next_stage: Literal["artifact_backed_empirical_outcome_authority_independent_audit_only"] = (
        NEXT_STAGE
    )
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> PreflightReport:
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_artifact_backed_outcome_preflight_report:",
        ):
            raise ValueError("artifact-backed preflight Report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    authorization: PreflightAuthorization
    freeze: PredecessorFreezeAudit
    contract_audit: OutcomeContractAudit
    factorization: TerminalValidityFactorizationAudit
    admission: EmpiricalAdmissionAudit
    locus: FailureLocusReconstructionAudit
    artifacts: ArtifactByteAuthenticityAudit
    parents: ParentRevalidationAudit
    evidence_dag: ScriptedEvidenceDagAudit
    static: StaticAudit
    transition: ProspectiveTransition
    report: PreflightReport


def new_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    return cast(
        Any,
        make_identity_model(
            model_type,
            values,
            field=field,
            prefix=prefix,
        ),
    )


__all__ = [
    "AUTHORIZED_STAGE",
    "NEXT_STAGE",
    "SCHEMA_VERSION",
    "ArtifactByteAuthenticityAudit",
    "ArtifactManifest",
    "BuildProducts",
    "EmpiricalAdmissionAudit",
    "FactorizationControl",
    "FailureLocusReconstructionAudit",
    "FileBinding",
    "OutcomeContractAudit",
    "ParentRevalidationAudit",
    "PredecessorFreezeAudit",
    "PreflightAuthorization",
    "PreflightReport",
    "ProspectiveTransition",
    "RejectionControl",
    "ScriptedEvidenceDagAudit",
    "StaticAudit",
    "StaticGate",
    "TerminalValidityFactorizationAudit",
    "identity",
    "make_identity_model",
    "new_model",
]
