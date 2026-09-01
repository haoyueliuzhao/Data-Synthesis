from __future__ import annotations

from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.fresh_artifact_backed_terminal_to_outcome_integration import (
    ReachableTerminalKind,
)
from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_terminal_to_outcome_postrun_independent_audit.v1"
CONSUMED_STAGE: Final = (
    "fresh_artifact_backed_terminal_to_outcome_integration_repair_exact_192_job_"
    "online_execution_postrun_independent_audit_only"
)
NEXT_DECISION: Final = "no_further_experiment_authorized_without_new_audit_decision"


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


class V200ExecutionFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    execution_summary_id: str = Field(min_length=1)
    execution_artifact_manifest_id: str = Field(min_length=1)
    execution_artifact_root: str = Field(min_length=1)
    online_authorization_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    execution_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    execution_source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    execution_status: Literal["completed"] = "completed"
    manifest_execution_ordinal: Literal[1] = 1
    exact_job_count: Literal[192] = 192
    formal_file_count: Literal[1154] = 1154
    formal_total_byte_count: Literal[4304518] = 4_304_518
    authorization_consumed: Literal[True] = True
    replacement_rerun_count: Literal[0] = 0
    recovery_execution_count: Literal[0] = 0
    provider_calls_during_audit: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V200ExecutionFreeze:
        if self.freeze_id != identity(self, "freeze_id", "finance_v26_201_v200_execution_freeze:"):
            raise ValueError("v26.201 v26.200 execution Freeze identity differs")
        return self


class IndependentJobAuditRow(FrozenModel):
    audit_row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    terminal_kind: ReachableTerminalKind
    independently_reconstructed_terminal_kind: ReachableTerminalKind
    raw_execution_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    outcome_row_id: str = Field(min_length=1)
    raw_actual_byte_match: Literal[True] = True
    result_actual_byte_match: Literal[True] = True
    raw_before_result: Literal[True] = True
    raw_result_parent_match: Literal[True] = True
    trace_parent_match: Literal[True] = True
    outcome_parent_match: Literal[True] = True
    failure_locus_match: Literal[True] = True
    terminal_projection_count: Literal[1] = 1
    provider_call_count: Literal[1] = 1
    model_identity_complete: Literal[True] = True
    thinking_complete: Literal[True] = True
    usage_complete: Literal[True] = True
    exact_action_abi_crossed: bool
    public_payload_key_shape: tuple[str, ...] | None
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> IndependentJobAuditRow:
        if self.terminal_kind != self.independently_reconstructed_terminal_kind:
            raise ValueError("v26.201 independent terminal reconstruction differs")
        if self.audit_row_id != identity(
            self, "audit_row_id", "finance_v26_201_independent_job_audit_row:"
        ):
            raise ValueError("v26.201 independent Job audit-row identity differs")
        return self


class ByteReconstructionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    v200_freeze_id: str = Field(min_length=1)
    rows: tuple[IndependentJobAuditRow, ...] = Field(min_length=192, max_length=192)
    exact_job_count: Literal[192] = 192
    manifest_member_count: Literal[1153] = 1153
    manifest_path_match_count: Literal[1153] = 1153
    manifest_sha256_match_count: Literal[1153] = 1153
    manifest_byte_match_count: Literal[1153] = 1153
    raw_count: Literal[192] = 192
    result_count: Literal[192] = 192
    trace_count: Literal[192] = 192
    outcome_count: Literal[192] = 192
    raw_actual_byte_match_count: Literal[192] = 192
    result_actual_byte_match_count: Literal[192] = 192
    raw_before_result_count: Literal[192] = 192
    terminal_reconstruction_match_count: Literal[192] = 192
    failure_locus_reconstruction_match_count: Literal[192] = 192
    exception_escape_count: Literal[0] = 0
    fixture_complete_terminal_count: Literal[0] = 0
    provider_calls_during_audit: Literal[0] = 0
    gate_passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ByteReconstructionAudit:
        if (
            len({item.job_id for item in self.rows}) != 192
            or len({item.raw_execution_id for item in self.rows}) != 192
            or len({item.result_id for item in self.rows}) != 192
            or len({item.trace_id for item in self.rows}) != 192
            or len({item.outcome_row_id for item in self.rows}) != 192
        ):
            raise ValueError("v26.201 evidence-layer denominator differs")
        if self.audit_id != identity(
            self, "audit_id", "finance_v26_201_byte_reconstruction_audit:"
        ):
            raise ValueError("v26.201 byte-reconstruction Audit identity differs")
        return self


class ResponseInterfaceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    byte_reconstruction_audit_id: str = Field(min_length=1)
    provider_call_count: Literal[192] = 192
    http_200_count: Literal[192] = 192
    exact_model_identity_count: Literal[192] = 192
    thinking_present_count: Literal[192] = 192
    thinking_token_telemetry_count: Literal[192] = 192
    usage_complete_count: Literal[192] = 192
    public_projection_count: Literal[188] = 188
    privacy_rejection_count: Literal[0] = 0
    exact_action_abi_count: Literal[0] = 0
    first_response_abi_invalid_count: Literal[188] = 188
    reasoning_budget_exhausted_count: Literal[4] = 4
    thinking_integrity_failure_count: Literal[4] = 4
    terminal_partition: dict[str, int]
    public_payload_key_shape_counts: dict[str, int]
    total_usage_tokens: Literal[1824320] = 1_824_320
    private_reasoning_content_persisted: Literal[False] = False
    provider_calls_during_audit: Literal[0] = 0
    gate_passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ResponseInterfaceAudit:
        if self.terminal_partition != {
            "first_response_abi_invalid": 188,
            "thinking_integrity_failure": 4,
        }:
            raise ValueError("v26.201 terminal partition differs")
        if sum(self.public_payload_key_shape_counts.values()) != 188:
            raise ValueError("v26.201 public payload-shape denominator differs")
        if self.audit_id != identity(self, "audit_id", "finance_v26_201_response_interface_audit:"):
            raise ValueError("v26.201 response-interface Audit identity differs")
        return self


class PostrunIndependentAuditDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    v200_freeze_id: str = Field(min_length=1)
    byte_reconstruction_audit_id: str = Field(min_length=1)
    response_interface_audit_id: str = Field(min_length=1)
    decision: Literal["v26_200_exact_online_execution_accepted_as_complete"]
    exact_job_run_complete: Literal[True] = True
    execution_integrity_passed: Literal[True] = True
    model_crossed_action_interface: Literal[False] = False
    capability_estimate_materialized: Literal[False] = False
    no_rerun_or_recovery_permitted: Literal[True] = True
    provider_calls_during_audit: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> PostrunIndependentAuditDecision:
        if self.decision_id != identity(
            self, "decision_id", "finance_v26_201_postrun_independent_audit_decision:"
        ):
            raise ValueError("v26.201 postrun Decision identity differs")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    next_decision: Literal["no_further_experiment_authorized_without_new_audit_decision"] = (
        NEXT_DECISION
    )
    provider_execution_authorized: Literal[False] = False
    replacement_rerun_authorized: Literal[False] = False
    recovery_execution_authorized: Literal[False] = False
    empirical_estimation_authorized: Literal[False] = False
    qa_integration_authorized: Literal[False] = False
    mapper_state_frequency_contribution_vtdo_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.transition_id != identity(self, "transition_id", "finance_v26_201_transition:"):
            raise ValueError("v26.201 transition identity differs")
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
        paths = tuple(item.relative_path for item in self.members)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.201 artifact member set differs")
        if self.file_count != len(self.members) or self.total_byte_count != sum(
            item.byte_count for item in self.members
        ):
            raise ValueError("v26.201 artifact aggregate differs")
        root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_201_artifact_root:",
        )
        if self.artifact_root != root:
            raise ValueError("v26.201 artifact Root differs")
        if self.manifest_id != identity(self, "manifest_id", "finance_v26_201_artifact_manifest:"):
            raise ValueError("v26.201 artifact Manifest identity differs")
        return self


def artifact_manifest(*, run_id: str, members: tuple[ArtifactMember, ...]) -> ArtifactManifest:
    root = canonical_hash(
        tuple(item.model_dump(mode="json") for item in members),
        prefix="finance_v26_201_artifact_root:",
    )
    return cast(
        ArtifactManifest,
        make_identity(
            ArtifactManifest,
            {
                "run_id": run_id,
                "members": members,
                "file_count": len(members),
                "total_byte_count": sum(item.byte_count for item in members),
                "artifact_root": root,
            },
            field="manifest_id",
            prefix="finance_v26_201_artifact_manifest:",
        ),
    )
