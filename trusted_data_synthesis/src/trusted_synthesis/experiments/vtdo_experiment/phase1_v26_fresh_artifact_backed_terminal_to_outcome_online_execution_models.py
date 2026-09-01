from __future__ import annotations

import json
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task import fresh_artifact_backed_outcome_authority as authority
from trusted_synthesis.core.task import (
    fresh_artifact_backed_terminal_to_outcome_integration as integration,
)
from trusted_synthesis.core.task.job_bound_multistep_outcome import (
    ComponentAttemptOutcome,
    JobBoundOutcomePayload,
)
from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_terminal_to_outcome_exact_online_execution.v1"
CONSUMED_STAGE: Final = (
    "fresh_artifact_backed_terminal_to_outcome_integration_repair_"
    "exact_192_job_online_execution_only"
)
NEXT_STAGE: Final = (
    "fresh_artifact_backed_terminal_to_outcome_integration_repair_"
    "exact_192_job_online_execution_postrun_independent_audit_only"
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


def canonical_bytes(value: BaseModel) -> bytes:
    return (
        json.dumps(
            value.model_dump(mode="json", warnings=False),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


class FileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class ExternalOnlineExecutionDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    audit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    audit_byte_count: Literal[9063] = 9063
    audit_decision: Literal["v26_199_accepted_exact_online_execution_only"]
    consumed_stage: Literal[
        "fresh_artifact_backed_terminal_to_outcome_integration_repair_"
        "exact_192_job_online_execution_only"
    ] = CONSUMED_STAGE
    v199_report_id: str = Field(min_length=1)
    v199_decision_id: str = Field(min_length=1)
    v199_transition_id: str = Field(min_length=1)
    exact_manifest_execution_authorized: Literal[True] = True
    maximum_manifest_executions: Literal[1] = 1
    replacement_rerun_authorized: Literal[False] = False
    recovery_execution_authorized: Literal[False] = False
    empirical_estimation_authorized: Literal[False] = False
    qa_integration_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> ExternalOnlineExecutionDecision:
        if self.decision_id != identity(
            self,
            "decision_id",
            "finance_v26_200_external_online_execution_decision:",
        ):
            raise ValueError("v26.200 external execution decision identity differs")
        return self


class V199AuthorizationFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    external_decision_id: str = Field(min_length=1)
    v199_report_id: str = Field(min_length=1)
    v199_decision_id: str = Field(min_length=1)
    v199_transition_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    sealed_artifact_root: str = Field(min_length=1)
    distribution_artifact_root: str = Field(min_length=1)
    exact_job_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    formal_file_count: Literal[16] = 16
    formal_file_match_count: Literal[16] = 16
    formal_total_byte_count: Literal[102783] = 102_783
    authorization_issued: Literal[True] = True
    authorization_consumed_before_v200: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V199AuthorizationFreeze:
        if self.freeze_id != identity(
            self,
            "freeze_id",
            "finance_v26_200_v199_authorization_freeze:",
        ):
            raise ValueError("v26.200 v26.199 freeze identity differs")
        return self


class ExactExecutionPreparation(FrozenModel):
    preparation_id: str = Field(min_length=1)
    external_decision_id: str = Field(min_length=1)
    v199_freeze_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    raw_contract_id: str = Field(min_length=1)
    result_contract_id: str = Field(min_length=1)
    trace_contract_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    evaluator_contract_id: str = Field(min_length=1)
    prompt_contract_id: str = Field(min_length=1)
    prompt_schema_id: str = Field(min_length=1)
    generation_profile_id: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    thinking_policy_id: str = Field(min_length=1)
    exact_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    exact_job_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_package_count: Literal[32] = 32
    exact_job_count: Literal[192] = 192
    exact_registered_invocation_count: Literal[792] = 792
    mapped_runtime_job_count: Literal[192] = 192
    old_complete_job_call_count: Literal[0] = 0
    credentials_read: Literal[False] = False
    provider_calls: Literal[0] = 0
    qa_reads: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_preparation(self) -> ExactExecutionPreparation:
        if self.exact_job_ids != tuple(sorted(set(self.exact_job_ids))):
            raise ValueError("v26.200 preparation Job denominator differs")
        if self.preparation_id != identity(
            self,
            "preparation_id",
            "finance_v26_200_exact_execution_preparation:",
        ):
            raise ValueError("v26.200 preparation identity differs")
        return self


class RunStartReceipt(FrozenModel):
    receipt_id: str = Field(min_length=1)
    external_decision_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    admission_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    exact_job_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    execution_source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    started_at_utc: str = Field(min_length=20)
    manifest_execution_ordinal: Literal[1] = 1
    authorization_consumed: Literal[True] = True
    replacement_rerun_forbidden: Literal[True] = True
    recovery_execution_forbidden: Literal[True] = True
    credential_lookup_after_receipt_only: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_receipt(self) -> RunStartReceipt:
        if self.receipt_id != identity(
            self,
            "receipt_id",
            "finance_v26_200_online_run_start_receipt:",
        ):
            raise ValueError("v26.200 run-start receipt identity differs")
        return self


class EmpiricalTerminalExecutionEvidence(FrozenModel):
    evidence_id: str = Field(min_length=1)
    dispatcher_evidence_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    online_admission_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    component_index: int = Field(ge=0, le=3)
    component_key: str = Field(min_length=1)
    invocation_receipt_ids: tuple[str, ...] = Field(max_length=23)
    public_terminal_projection: integration.DispatchControlPayload | None = None
    exception_type: integration.ObservedExceptionType | None = None
    exception_reason_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    provider_call_count: int = Field(ge=0, le=23)
    cumulative_tokens: int = Field(ge=0, le=1_120_000)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evidence(self) -> EmpiricalTerminalExecutionEvidence:
        if (self.public_terminal_projection is None) == (self.exception_type is None):
            raise ValueError("empirical terminal evidence must have one source kind")
        if self.exception_type is None and self.exception_reason_sha256 is not None:
            raise ValueError("public terminal evidence carries an exception reason")
        if self.exception_type is not None and self.exception_reason_sha256 is None:
            raise ValueError("exception terminal evidence lacks a reason hash")
        if self.evidence_id != identity(
            self,
            "evidence_id",
            "empirical_terminal_execution_evidence:",
        ):
            raise ValueError("empirical terminal evidence identity differs")
        return self


class EmpiricalIntegratedRawPayload(FrozenModel):
    payload_id: str = Field(min_length=1)
    evidence_kind: Literal["empirical_execution"] = "empirical_execution"
    job_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    online_authorization_id: str = Field(min_length=1)
    online_admission_id: str = Field(min_length=1)
    terminal_kind: integration.ReachableTerminalKind
    component_attempts: tuple[ComponentAttemptOutcome, ...] = Field(max_length=4)
    source_outcome: JobBoundOutcomePayload | None = None
    terminal_evidence: EmpiricalTerminalExecutionEvidence
    terminal_decision: integration.TerminalDecision
    provider_artifact_ids: tuple[str, ...] = Field(max_length=23)
    model_response_present: bool
    token_usage: int = Field(ge=0, le=1_120_000)
    provider_calls: int = Field(ge=0, le=23)
    execution_error: str | None = None
    provider_telemetry: tuple[dict[str, Any], ...] = Field(max_length=24)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_payload(self) -> EmpiricalIntegratedRawPayload:
        if tuple(item.component_index for item in self.component_attempts) != tuple(
            range(len(self.component_attempts))
        ):
            raise ValueError("empirical component attempts are not contiguous")
        if (
            self.terminal_evidence.job_id != self.job_id
            or self.terminal_decision.job_id != self.job_id
            or self.terminal_decision.terminal_kind != self.terminal_kind
            or self.terminal_decision.execution_evidence_id
            != self.terminal_evidence.dispatcher_evidence_id
            or self.provider_calls != self.terminal_evidence.provider_call_count
            or self.token_usage != self.terminal_evidence.cumulative_tokens
        ):
            raise ValueError("empirical Raw crosses terminal or Provider evidence")
        if self.payload_id != identity(
            self,
            "payload_id",
            "fresh_kernel_raw_execution_payload:",
        ):
            raise ValueError("empirical Raw payload identity differs")
        return self


class EmpiricalIntegratedAttemptTrace(FrozenModel):
    trace_id: str = Field(min_length=1)
    trace_contract_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    online_admission_id: str = Field(min_length=1)
    evidence_kind: Literal["empirical_execution"] = "empirical_execution"
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    terminal_kind: integration.ReachableTerminalKind
    terminal_evidence_id: str = Field(min_length=1)
    terminal_decision_id: str = Field(min_length=1)
    component_attempts: tuple[ComponentAttemptOutcome, ...] = Field(max_length=4)
    failure_loci: tuple[authority.FreshFailureLocus, ...] = ()
    correction_count: int = Field(ge=0, le=4)
    terminal_projection_count: Literal[1] = 1
    provider_call_count: int = Field(ge=0, le=23)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_trace(self) -> EmpiricalIntegratedAttemptTrace:
        if self.correction_count != sum(
            int(item.correction_invoked) for item in self.component_attempts
        ):
            raise ValueError("empirical Trace correction count differs")
        if self.trace_id != identity(
            self,
            "trace_id",
            "fresh_kernel_job_bound_attempt_trace:",
        ):
            raise ValueError("empirical Trace identity differs")
        return self


class EmpiricalIntegratedEvidenceBundle(FrozenModel):
    raw: authority.FreshRawExecutionDescriptor
    result: authority.FreshJobResultDescriptor
    trace: EmpiricalIntegratedAttemptTrace
    row: authority.FreshOutcomeRow


class OnlineJobExecutionRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    source_json_job_id: str = Field(min_length=1)
    source_runtime_job_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    capability_family: str = Field(min_length=1)
    observation_depth: str = Field(min_length=1)
    terminal_kind: integration.ReachableTerminalKind
    bundle: EmpiricalIntegratedEvidenceBundle
    kernel_invocation_receipt_ids: tuple[str, ...] = Field(max_length=23)
    provider_call_count: int = Field(ge=0, le=23)
    cumulative_tokens: int = Field(ge=0, le=1_120_000)
    execution_error: str | None = None
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_record(self) -> OnlineJobExecutionRecord:
        if (
            self.bundle.row.job_id != self.job_id
            or self.bundle.row.terminal_kind != self.terminal_kind
            or self.bundle.raw.job_id != self.job_id
            or self.bundle.result.job_id != self.job_id
        ):
            raise ValueError("online Job record crosses its evidence bundle")
        if self.record_id != identity(
            self,
            "record_id",
            "finance_v26_200_online_job_execution_record:",
        ):
            raise ValueError("online Job execution record identity differs")
        return self


class ExecutionCheckpoint(FrozenModel):
    checkpoint_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    ordinal: int = Field(ge=0, le=191)
    job_id: str = Field(min_length=1)
    record_id: str = Field(min_length=1)
    terminal_kind: integration.ReachableTerminalKind
    raw_execution_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_checkpoint(self) -> ExecutionCheckpoint:
        if self.checkpoint_id != identity(
            self,
            "checkpoint_id",
            "finance_v26_200_online_execution_checkpoint:",
        ):
            raise ValueError("v26.200 checkpoint identity differs")
        return self


class OnlineExecutionSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    integration_contract_id: str = Field(min_length=1)
    execution_status: Literal["completed", "failed", "interrupted"]
    exact_job_count: Literal[192] = 192
    attempted_job_count: int = Field(ge=0, le=192)
    completed_job_record_count: int = Field(ge=0, le=192)
    raw_count: int = Field(ge=0, le=192)
    result_count: int = Field(ge=0, le=192)
    outcome_count: int = Field(ge=0, le=192)
    terminal_partition: dict[str, int]
    provider_calls: int = Field(ge=0)
    total_usage_tokens: int = Field(ge=0)
    old_complete_job_call_count: Literal[0] = 0
    fixture_complete_count: Literal[0] = 0
    replacement_job_count: Literal[0] = 0
    rerun_job_count: Literal[0] = 0
    recovery_job_count: Literal[0] = 0
    qa_read_count: Literal[0] = 0
    empirical_estimate_count: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    next_stage: str | None
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_summary(self) -> OnlineExecutionSummary:
        counts = (self.raw_count, self.result_count, self.outcome_count)
        if any(item != self.completed_job_record_count for item in counts):
            raise ValueError("v26.200 evidence layer counts differ")
        if sum(self.terminal_partition.values()) != self.completed_job_record_count:
            raise ValueError("v26.200 terminal partition differs")
        if self.execution_status == "completed" and self.completed_job_record_count != 192:
            raise ValueError("completed v26.200 execution lacks exact Job set")
        if self.summary_id != identity(
            self,
            "summary_id",
            "finance_v26_200_online_execution_summary:",
        ):
            raise ValueError("v26.200 execution summary identity differs")
        return self


class ExecutionArtifactMember(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class ExecutionArtifactManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    members: tuple[ExecutionArtifactMember, ...] = Field(min_length=1)
    file_count: int = Field(gt=0)
    total_byte_count: int = Field(gt=0)
    artifact_root: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> ExecutionArtifactManifest:
        paths = tuple(item.relative_path for item in self.members)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.200 artifact member set differs")
        if self.file_count != len(self.members) or self.total_byte_count != sum(
            item.byte_count for item in self.members
        ):
            raise ValueError("v26.200 artifact aggregate differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_200_execution_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("v26.200 artifact Root differs")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            "finance_v26_200_execution_artifact_manifest:",
        ):
            raise ValueError("v26.200 artifact Manifest identity differs")
        return self


def empirical_bundle(
    *,
    raw: authority.FreshRawExecutionDescriptor,
    result: authority.FreshJobResultDescriptor,
    trace: EmpiricalIntegratedAttemptTrace,
    row: authority.FreshOutcomeRow,
) -> EmpiricalIntegratedEvidenceBundle:
    return cast(
        EmpiricalIntegratedEvidenceBundle,
        EmpiricalIntegratedEvidenceBundle(raw=raw, result=result, trace=trace, row=row),
    )
