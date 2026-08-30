from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash

V26_181_INDEPENDENT_AUDIT_VERSION = "capability_authoritative_outcome_terminal_independent_audit.v1"

ControlCategory = Literal[
    "completed_invalid_factorization",
    "diagnostic_empirical_admission",
    "failure_locus_authenticity",
    "artifact_byte_authenticity",
    "authoritative_parent_revalidation",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return strict_canonical_hash(
        value.model_dump(mode="python", exclude={field}, warnings=False),
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
    source_kind: str = Field(min_length=1)


class ExactPredecessorFreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    audited_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    audited_tree_id: str = Field(pattern=r"^[0-9a-f]{40}$")
    v181_report_id: str = Field(min_length=1)
    v181_source_root_id: str = Field(min_length=1)
    source_file_manifest_hash: str = Field(min_length=1)
    source_file_count: Literal[347] = 347
    source_file_match_count: Literal[347] = 347
    entry_source_file_count: Literal[4] = 4
    entry_source_file_match_count: Literal[4] = 4
    formal_artifact_count: Literal[15] = 15
    formal_artifact_match_count: Literal[15] = 15
    current_worktree_artifact_match_count: Literal[15] = 15
    report_detail_binding_count: Literal[14] = 14
    report_detail_binding_match_count: Literal[14] = 14
    exact_commit_artifacts: tuple[FileBinding, ...] = Field(min_length=15, max_length=15)
    auditor_source_root_hash: str = Field(min_length=1)
    auditor_source_files: tuple[FileBinding, ...] = Field(min_length=3)
    schema_version: str = V26_181_INDEPENDENT_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ExactPredecessorFreezeAudit:
        if tuple(item.relative_path for item in self.exact_commit_artifacts) != tuple(
            sorted(item.relative_path for item in self.exact_commit_artifacts)
        ):
            raise ValueError("v26.181 exact artifact bindings are not canonical")
        if tuple(item.relative_path for item in self.auditor_source_files) != tuple(
            sorted(item.relative_path for item in self.auditor_source_files)
        ):
            raise ValueError("independent auditor source bindings are not canonical")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_181_exact_predecessor_freeze_audit:",
        ):
            raise ValueError("v26.181 exact predecessor freeze identity is invalid")
        return self


class NegativeControlObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    category: ControlCategory
    control: str = Field(min_length=1)
    exact_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    attack: bool
    input_valid: bool
    fully_rehashed: bool
    production_entry_admitted: bool
    required_property_preserved: bool
    expected_behavior: str = Field(min_length=1)
    observed_behavior: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = V26_181_INDEPENDENT_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> NegativeControlObservation:
        if self.observation_id != identity(
            self,
            "observation_id",
            "finance_v26_181_independent_negative_control:",
        ):
            raise ValueError("v26.181 independent control identity is invalid")
        return self


class ControlGroupAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    category: ControlCategory
    observations: tuple[NegativeControlObservation, ...] = Field(min_length=1)
    expected_rejection_count: int = Field(ge=0)
    observed_rejection_count: int = Field(ge=0)
    admitted_attack_count: int = Field(ge=0)
    property_failure_count: int = Field(ge=0)
    gate_passed: bool
    schema_version: str = V26_181_INDEPENDENT_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_group(self) -> ControlGroupAudit:
        if any(item.category != self.category for item in self.observations):
            raise ValueError("independent control group crosses categories")
        expected_rejections = sum(item.attack and item.input_valid for item in self.observations)
        observed_rejections = sum(
            item.attack and item.input_valid and not item.production_entry_admitted
            for item in self.observations
        )
        admitted = sum(item.attack and item.production_entry_admitted for item in self.observations)
        property_failures = sum(not item.required_property_preserved for item in self.observations)
        if self.expected_rejection_count != expected_rejections:
            raise ValueError("independent group expected-rejection count changed")
        if self.observed_rejection_count != observed_rejections:
            raise ValueError("independent group observed-rejection count changed")
        if self.admitted_attack_count != admitted:
            raise ValueError("independent group admitted-attack count changed")
        if self.property_failure_count != property_failures:
            raise ValueError("independent group property-failure count changed")
        expected_gate = all(
            (not item.attack or not item.input_valid or not item.production_entry_admitted)
            and item.required_property_preserved
            for item in self.observations
        )
        if self.gate_passed != expected_gate:
            raise ValueError("independent control group gate summary changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            f"finance_v26_181_{self.category}_audit:",
        ):
            raise ValueError("v26.181 independent group identity is invalid")
        return self


class IndependentAuditGateDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    predecessor_freeze_audit_id: str = Field(min_length=1)
    control_group_audit_ids: tuple[str, ...] = Field(min_length=5, max_length=5)
    gates: dict[str, bool]
    passed_gate_count: int = Field(ge=0)
    failed_gate_count: int = Field(ge=0)
    exact_source_and_artifact_freeze: Literal[True] = True
    scripted_object_dag_parent_binding: Literal[True] = True
    enumerated_terminal_shape_construction: Literal[True] = True
    empirical_terminal_semantic_totality: Literal[False] = False
    diagnostic_terminal_empirical_isolation: Literal[False] = False
    failure_locus_semantic_authenticity: Literal[False] = False
    persisted_artifact_byte_authenticity: Literal[False] = False
    authoritative_parent_revalidation: Literal[False] = False
    online_execution_authorized: Literal[False] = False
    online_execution_admission: Literal["BLOCKED_FAILED_INDEPENDENT_AUDIT"] = (
        "BLOCKED_FAILED_INDEPENDENT_AUDIT"
    )
    next_stage: Literal[
        "artifact_backed_terminal_validity_factorization_and_failure_locus_reconstruction_preflight_only"
    ] = (
        "artifact_backed_terminal_validity_factorization_and_"
        "failure_locus_reconstruction_preflight_only"
    )
    provider_calls: Literal[0] = 0
    empirical_outcome_count: Literal[0] = 0
    schema_version: str = V26_181_INDEPENDENT_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> IndependentAuditGateDecision:
        if self.passed_gate_count != sum(self.gates.values()):
            raise ValueError("independent audit passed-gate count changed")
        if self.failed_gate_count != sum(not item for item in self.gates.values()):
            raise ValueError("independent audit failed-gate count changed")
        if self.failed_gate_count == 0 or self.online_execution_authorized:
            raise ValueError("failed independent audit authorized online execution")
        if self.decision_id != identity(
            self,
            "decision_id",
            "finance_v26_181_independent_audit_gate_decision:",
        ):
            raise ValueError("v26.181 independent gate decision identity is invalid")
        return self


class IndependentAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    audited_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    predecessor_freeze_audit_id: str = Field(min_length=1)
    completed_invalid_factorization_audit_id: str = Field(min_length=1)
    diagnostic_empirical_admission_audit_id: str = Field(min_length=1)
    failure_locus_authenticity_audit_id: str = Field(min_length=1)
    artifact_byte_authenticity_audit_id: str = Field(min_length=1)
    authoritative_parent_revalidation_audit_id: str = Field(min_length=1)
    gate_decision_id: str = Field(min_length=1)
    detail_files: tuple[FileBinding, ...] = Field(min_length=7, max_length=7)
    detail_file_count: Literal[7] = 7
    independent_control_count: Literal[10] = 10
    admitted_attack_count: Literal[8] = 8
    semantic_state_loss_control_count: Literal[2] = 2
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    formal_empirical_rows_materialized: Literal[0] = 0
    online_execution_authorized: Literal[False] = False
    online_execution_admission: Literal["BLOCKED_FAILED_INDEPENDENT_AUDIT"] = (
        "BLOCKED_FAILED_INDEPENDENT_AUDIT"
    )
    next_stage: Literal[
        "artifact_backed_terminal_validity_factorization_and_failure_locus_reconstruction_preflight_only"
    ] = (
        "artifact_backed_terminal_validity_factorization_and_"
        "failure_locus_reconstruction_preflight_only"
    )
    schema_version: str = V26_181_INDEPENDENT_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> IndependentAuditReport:
        if tuple(item.relative_path for item in self.detail_files) != tuple(
            sorted(item.relative_path for item in self.detail_files)
        ):
            raise ValueError("v26.181 independent report details are not canonical")
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_181_independent_audit_report:",
        ):
            raise ValueError("v26.181 independent audit report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    freeze: ExactPredecessorFreezeAudit
    completed_invalid: ControlGroupAudit
    diagnostic_empirical: ControlGroupAudit
    failure_locus: ControlGroupAudit
    artifact_bytes: ControlGroupAudit
    parent_revalidation: ControlGroupAudit
    decision: IndependentAuditGateDecision
    report: IndependentAuditReport


__all__ = [
    "BuildProducts",
    "ControlGroupAudit",
    "ExactPredecessorFreezeAudit",
    "FileBinding",
    "IndependentAuditGateDecision",
    "IndependentAuditReport",
    "NegativeControlObservation",
    "V26_181_INDEPENDENT_AUDIT_VERSION",
    "identity",
    "make_identity_model",
]
