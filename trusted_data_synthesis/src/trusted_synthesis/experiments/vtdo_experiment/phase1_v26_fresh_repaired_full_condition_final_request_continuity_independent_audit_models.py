# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = (
    "fresh_repaired_full_condition_final_request_continuity_independent_audit.v1"
)
CONSUMED_STAGE: Final = "fresh_repaired_full_condition_executable_runner_final_request_contract_continuity_repair_preflight_independent_audit_only"
NEXT_STAGE: Final = (
    "fresh_repaired_full_condition_exact_192_job_online_execution_authorization_only"
)
DECISION: Final = "v26_209_final_request_continuity_repair_independent_audit_passed"


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
    review_sha256: Literal["c826ba2618807789f2eb427ddadb54977ad0d8dea9c472ddeef8965ec8319ee3"]
    review_byte_count: Literal[15336] = 15_336
    review_audit_result: Literal["VALID_SCOPED_ZERO_PROVIDER_REPAIR_PREFLIGHT"] = (
        "VALID_SCOPED_ZERO_PROVIDER_REPAIR_PREFLIGHT"
    )
    review_mandatory_revision: Literal["NONE"] = "NONE"
    documentation_erratum_applied: Literal[True] = True
    operator_directive: Literal["参照审计开展后续实验"] = "参照审计开展后续实验"
    operator_directive_sha256: Literal[
        "8e30b645e46c5682c61a1e4ca820e51aa5c8b07bfa052274b665ebd20afd33fa"
    ]
    operator_directive_byte_count: Literal[30] = 30
    explicit_operator_authorization_after_review: Literal[True] = True
    only_authorized_stage: Literal[
        "fresh_repaired_full_condition_executable_runner_final_request_contract_continuity_repair_preflight_independent_audit_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    online_execution_authorization_creation_authorized: Literal[False] = False
    online_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalIndependentAuditAuthorization:
        directive = self.operator_directive.encode("utf-8")
        if (
            len(directive) != self.operator_directive_byte_count
            or hashlib.sha256(directive).hexdigest() != self.operator_directive_sha256
        ):
            raise ValueError("v26.210 operator directive bytes differ")
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_210_external_independent_audit_authorization:",
        ):
            raise ValueError("v26.210 external authorization identity differs")
        return self


class V209PreflightFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    v209_report_id: str = Field(min_length=1)
    v209_gate_audit_id: str = Field(min_length=1)
    v209_transition_id: str = Field(min_length=1)
    v209_manifest_id: str = Field(min_length=1)
    v209_execution_contract_id: str = Field(min_length=1)
    v209_invocation_census_id: str = Field(min_length=1)
    v209_continuity_audit_id: str = Field(min_length=1)
    v209_dynamic_branch_audit_id: str = Field(min_length=1)
    v209_artifact_manifest_id: str = Field(min_length=1)
    v209_artifact_root: str = Field(min_length=1)
    v209_source_commit: Literal["5809e9782515e55ee797b43730584d5d860aaa5c"]
    v209_source_tree: Literal["b2272bc1766a2d9b8c6562cb0b9f2f47151ad7cf"]
    v209_formal_file_count: Literal[21] = 21
    v209_formal_total_byte_count: Literal[44916386] = 44_916_386
    v209_manifest_member_count: Literal[20] = 20
    v209_manifest_member_total_byte_count: Literal[44912918] = 44_912_918
    v209_decision: Literal[
        "fresh_repaired_full_condition_executable_runner_final_request_contract_continuity_repair_preflight_passed_independent_audit_required_online_execution_blocked"
    ]
    documentation_action_final_transport_count_correction: Literal["4/1/5"] = "4/1/5"
    historical_artifact_mutation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V209PreflightFreeze:
        if self.freeze_id != identity(self, "freeze_id", "finance_v26_210_v209_preflight_freeze:"):
            raise ValueError("v26.210 v26.209 freeze identity differs")
        return self


class DetachedRebuildAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    exact_source_commit: Literal["5809e9782515e55ee797b43730584d5d860aaa5c"]
    exact_source_tree: Literal["b2272bc1766a2d9b8c6562cb0b9f2f47151ad7cf"]
    archived_transitive_source_file_count: int = Field(gt=0)
    credential_like_environment_variable_count: Literal[0] = 0
    rebuilt_file_count: Literal[21] = 21
    saved_file_count: Literal[21] = 21
    path_match_count: Literal[21] = 21
    sha256_match_count: Literal[21] = 21
    byte_count_match_count: Literal[21] = 21
    actual_byte_equality_count: Literal[21] = 21
    rebuilt_total_byte_count: Literal[44916386] = 44_916_386
    saved_total_byte_count: Literal[44916386] = 44_916_386
    manifest_member_revalidation_count: Literal[20] = 20
    candidate_report_used_as_outcome_oracle: Literal[False] = False
    candidate_gate_used_as_outcome_oracle: Literal[False] = False
    candidate_continuity_audit_used_as_outcome_oracle: Literal[False] = False
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    gate_passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DetachedRebuildAudit:
        if self.audit_id != identity(self, "audit_id", "finance_v26_210_detached_rebuild_audit:"):
            raise ValueError("v26.210 detached rebuild identity differs")
        return self


class IndependentCallsiteGeometryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    source_v194_manifest_id: str = Field(min_length=1)
    source_v193_evidence_set_id: str = Field(min_length=1)
    source_v206_callsite_census_id: str = Field(min_length=1)
    exact_job_count: Literal[192] = 192
    exact_coordinate_count: Literal[792] = 792
    unique_coordinate_count: Literal[792] = 792
    first_action_count: Literal[192] = 192
    subsequent_action_count: Literal[288] = 288
    correction_side_branch_count: Literal[120] = 120
    final_count: Literal[192] = 192
    action_and_correction_count: Literal[600] = 600
    coordinate_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_parent_match_count: Literal[792] = 792
    single_linear_provider_trajectory_claimed: Literal[False] = False
    provider_calls: Literal[0] = 0
    gate_passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentCallsiteGeometryAudit:
        if self.audit_id != identity(
            self, "audit_id", "finance_v26_210_independent_callsite_geometry_audit:"
        ):
            raise ValueError("v26.210 callsite geometry identity differs")
        return self


class RequestContinuityRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    source_v206_job_id: str = Field(min_length=1)
    invocation_index: int = Field(ge=0, le=8)
    phase: Literal["first_action", "subsequent_action", "correction", "final"]
    source_v193_evidence_row_id: str = Field(min_length=1)
    source_v206_callsite_row_id: str = Field(min_length=1)
    observed_invocation_id: str = Field(min_length=1)
    observed_messages_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_messages_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    message_match: Literal[True] = True
    request_match: Literal[True] = True
    final_actual_message_bytes_equal: bool
    final_actual_request_bytes_equal: bool
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> RequestContinuityRow:
        if (
            self.observed_messages_sha256 != self.source_messages_sha256
            or self.observed_request_sha256 != self.source_request_sha256
            or self.final_actual_message_bytes_equal != (self.phase == "final")
            or self.final_actual_request_bytes_equal != (self.phase == "final")
        ):
            raise ValueError("v26.210 continuity row differs")
        if self.row_id != identity(
            self, "row_id", "finance_v26_210_independent_request_continuity_row:"
        ):
            raise ValueError("v26.210 continuity row identity differs")
        return self


class IndependentRequestContinuityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    callsite_geometry_audit_id: str = Field(min_length=1)
    rows: tuple[RequestContinuityRow, ...] = Field(min_length=792, max_length=792)
    action_correction_message_match_count: Literal[600] = 600
    action_correction_request_match_count: Literal[600] = 600
    final_message_match_count: Literal[192] = 192
    final_request_match_count: Literal[192] = 192
    final_actual_message_byte_equality_count: Literal[192] = 192
    final_actual_request_byte_equality_count: Literal[192] = 192
    total_message_match_count: Literal[792] = 792
    total_request_match_count: Literal[792] = 792
    missing_coordinate_count: Literal[0] = 0
    duplicate_coordinate_count: Literal[0] = 0
    extra_coordinate_count: Literal[0] = 0
    maximum_message_byte_count: Literal[34404] = 34_404
    maximum_request_body_byte_count: Literal[34565] = 34_565
    candidate_continuity_helper_call_count: Literal[0] = 0
    candidate_continuity_artifact_used_as_target_only: Literal[True] = True
    provider_calls: Literal[0] = 0
    gate_passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentRequestContinuityAudit:
        keys = tuple((row.job_id, row.invocation_index) for row in self.rows)
        if len(set(keys)) != 792:
            raise ValueError("v26.210 continuity coordinate set differs")
        if self.audit_id != identity(
            self, "audit_id", "finance_v26_210_independent_request_continuity_audit:"
        ):
            raise ValueError("v26.210 continuity audit identity differs")
        return self


class IndependentReplayJobRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    invocation_ids_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    first_action_count: Literal[1] = 1
    subsequent_action_count: int = Field(ge=0, le=3)
    correction_side_branch_count: int = Field(ge=0, le=4)
    final_count: Literal[1] = 1
    transport_dispatch_count: int = Field(ge=2, le=9)
    saved_invocation_match_count: int = Field(ge=2, le=9)
    terminal_reference_path: Literal[True] = True
    qualified_valid: Literal[True] = True
    exception_escape_count: Literal[0] = 0
    empirical: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> IndependentReplayJobRow:
        expected = (
            self.first_action_count
            + self.subsequent_action_count
            + self.correction_side_branch_count
            + self.final_count
        )
        if (
            self.transport_dispatch_count != expected
            or self.saved_invocation_match_count != expected
        ):
            raise ValueError("v26.210 replay Job geometry differs")
        if self.row_id != identity(self, "row_id", "finance_v26_210_independent_replay_job_row:"):
            raise ValueError("v26.210 replay Job row identity differs")
        return self


class IndependentExecutableReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    rows: tuple[IndependentReplayJobRow, ...] = Field(min_length=192, max_length=192)
    main_reference_path_count: Literal[192] = 192
    correction_side_branch_call_count: Literal[120] = 120
    qualified_scripted_main_path_count: Literal[192] = 192
    invocation_record_count: Literal[792] = 792
    saved_invocation_record_match_count: Literal[792] = 792
    transport_dispatch_count: Literal[792] = 792
    dynamic_nonreference_action_dispatch_count: Literal[4] = 4
    dynamic_nonreference_final_dispatch_count: Literal[1] = 1
    dynamic_nonreference_transport_dispatch_count: Literal[5] = 5
    dynamic_nonreference_saved_target_match: Literal[True] = True
    exception_escape_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    gate_passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentExecutableReplayAudit:
        if len({row.job_id for row in self.rows}) != 192:
            raise ValueError("v26.210 replay Job denominator differs")
        if self.audit_id != identity(
            self, "audit_id", "finance_v26_210_independent_executable_replay_audit:"
        ):
            raise ValueError("v26.210 replay audit identity differs")
        return self


class IndependentFailureControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: Literal[
        "invalid_first_action_abi",
        "unknown_current_action",
        "invalid_correction_abi",
        "invalid_final_abi",
        "typed_outer_failure",
    ]
    expected_terminal: str = Field(min_length=1)
    observed_terminal: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    typed_outcome_count: Literal[1] = 1
    exception_escape_count: Literal[0] = 0
    empirical: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> IndependentFailureControl:
        if self.expected_terminal != self.observed_terminal:
            raise ValueError("v26.210 failure terminal differs")
        if self.control_id != identity(
            self, "control_id", "finance_v26_210_independent_failure_control:"
        ):
            raise ValueError("v26.210 failure control identity differs")
        return self


class IndependentFailureBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    controls: tuple[IndependentFailureControl, ...] = Field(min_length=5, max_length=5)
    typed_failure_count: Literal[5] = 5
    typed_outcome_count: Literal[5] = 5
    exception_escape_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    empirical_outcome_rows: Literal[0] = 0
    estimand_evaluations: Literal[0] = 0
    qa_rows: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    gate_passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentFailureBoundaryAudit:
        if len({item.control_name for item in self.controls}) != 5:
            raise ValueError("v26.210 failure control denominator differs")
        if self.audit_id != identity(
            self, "audit_id", "finance_v26_210_independent_failure_boundary_audit:"
        ):
            raise ValueError("v26.210 failure boundary identity differs")
        return self


class IndependentAuditGateEvaluation(FrozenModel):
    gate_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    detached_rebuild_audit_id: str = Field(min_length=1)
    callsite_geometry_audit_id: str = Field(min_length=1)
    request_continuity_audit_id: str = Field(min_length=1)
    executable_replay_audit_id: str = Field(min_length=1)
    failure_boundary_audit_id: str = Field(min_length=1)
    a0_exact_freeze_and_detached_rebuild: Literal[True] = True
    a1_independent_callsite_geometry: Literal[True] = True
    a2_independent_request_continuity: Literal[True] = True
    a3_independent_executable_replay: Literal[True] = True
    a4_typed_failures_and_boundary: Literal[True] = True
    passed_gate_count: Literal[5] = 5
    failed_gate_count: Literal[0] = 0
    all_gates_passed: Literal[True] = True
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> IndependentAuditGateEvaluation:
        if self.gate_id != identity(
            self, "gate_id", "finance_v26_210_independent_audit_gate_evaluation:"
        ):
            raise ValueError("v26.210 gate identity differs")
        return self


class IndependentAuditDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    gate_id: str = Field(min_length=1)
    decision: Literal["v26_209_final_request_continuity_repair_independent_audit_passed"] = DECISION
    v209_preflight_accepted_as_scoped: Literal[True] = True
    online_execution_authorization_created: Literal[False] = False
    online_execution_authorized: Literal[False] = False
    next_stage_requires_separate_authorization_decision: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> IndependentAuditDecision:
        if self.decision_id != identity(
            self, "decision_id", "finance_v26_210_independent_audit_decision:"
        ):
            raise ValueError("v26.210 decision identity differs")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    gate_id: str = Field(min_length=1)
    status: Literal["PASSED_INDEPENDENT_AUDIT_ONLINE_AUTHORIZATION_REQUIRED"] = (
        "PASSED_INDEPENDENT_AUDIT_ONLINE_AUTHORIZATION_REQUIRED"
    )
    next_stage: Literal[
        "fresh_repaired_full_condition_exact_192_job_online_execution_authorization_only"
    ] = NEXT_STAGE
    provider_execution_in_this_stage_authorized: Literal[False] = False
    online_execution_authorization_created: Literal[False] = False
    semantic_condition_change_authorized: Literal[False] = False
    qa_mapper_state_frequency_contribution_vtdo_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.transition_id != identity(self, "transition_id", "finance_v26_210_transition:"):
            raise ValueError("v26.210 transition identity differs")
        return self


class SourceIdentity(FrozenModel):
    source_identity_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    implementation_files: tuple[str, ...] = Field(min_length=3)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_source(self) -> SourceIdentity:
        if self.implementation_files != tuple(sorted(set(self.implementation_files))):
            raise ValueError("v26.210 implementation file set differs")
        if self.source_identity_id != identity(
            self, "source_identity_id", "finance_v26_210_source_identity:"
        ):
            raise ValueError("v26.210 source identity differs")
        return self


class IndependentAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    freeze_id: str = Field(min_length=1)
    detached_rebuild_audit_id: str = Field(min_length=1)
    callsite_geometry_audit_id: str = Field(min_length=1)
    request_continuity_audit_id: str = Field(min_length=1)
    executable_replay_audit_id: str = Field(min_length=1)
    failure_boundary_audit_id: str = Field(min_length=1)
    gate_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    decision: Literal["v26_209_final_request_continuity_repair_independent_audit_passed"] = DECISION
    exact_job_count: Literal[192] = 192
    exact_invocation_count: Literal[792] = 792
    exact_request_match_count: Literal[792] = 792
    qualified_scripted_main_path_count: Literal[192] = 192
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    online_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> IndependentAuditReport:
        if self.report_id != identity(
            self, "report_id", "finance_v26_210_independent_audit_report:"
        ):
            raise ValueError("v26.210 report identity differs")
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
        if (
            self.file_count != len(self.members)
            or self.total_byte_count != sum(item.byte_count for item in self.members)
            or tuple(item.relative_path for item in self.members)
            != tuple(sorted({item.relative_path for item in self.members}))
        ):
            raise ValueError("v26.210 artifact Manifest geometry differs")
        provisional_root = canonical_hash(
            tuple(
                {
                    "relative_path": item.relative_path,
                    "sha256": item.sha256,
                    "byte_count": item.byte_count,
                }
                for item in self.members
            ),
            prefix="finance_v26_210_artifact_root:",
        )
        if self.artifact_root != provisional_root:
            raise ValueError("v26.210 artifact Root differs")
        if self.manifest_id != identity(self, "manifest_id", "finance_v26_210_artifact_manifest:"):
            raise ValueError("v26.210 artifact Manifest identity differs")
        return self


def artifact_manifest(run_id: str, payloads: dict[str, bytes]) -> ArtifactManifest:
    members = tuple(
        ArtifactMember(
            relative_path=name, sha256=hashlib.sha256(payload).hexdigest(), byte_count=len(payload)
        )
        for name, payload in sorted(payloads.items())
    )
    root = canonical_hash(
        tuple(
            {
                "relative_path": item.relative_path,
                "sha256": item.sha256,
                "byte_count": item.byte_count,
            }
            for item in members
        ),
        prefix="finance_v26_210_artifact_root:",
    )
    return make_identity(
        ArtifactManifest,
        {
            "run_id": run_id,
            "members": members,
            "file_count": len(members),
            "total_byte_count": sum(item.byte_count for item in members),
            "artifact_root": root,
        },
        field="manifest_id",
        prefix="finance_v26_210_artifact_manifest:",
    )
