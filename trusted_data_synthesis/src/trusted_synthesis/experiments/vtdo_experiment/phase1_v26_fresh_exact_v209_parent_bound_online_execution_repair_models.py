from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, Final, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_authorization_models as v223_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_models as prior,
)
from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_exact_v209_parent_bound_replacement_execution.v1"
REPAIR_DIRECTIVE: Final = "修正后执行独立审计，然后重跑"
REPAIR_DIRECTIVE_SHA256: Final = "61d7416f9e9886eb4c374f2aa7bb7993696f31a928c3559cc20f053e6c1023d8"
CONDITIONAL_RUN_DIRECTIVE: Final = "如果修订后的审计无误，重跑在线测试，我授予权限"
CONDITIONAL_RUN_DIRECTIVE_SHA256: Final = (
    "9d2d804d662735bf0b9dc539be16a89e5dc22a515f11df2e55eaa7eea5de3929"
)
REPLACEMENT_STAGE: Final = (
    "fresh_exact_v209_parent_bound_postresponse_serializer_repair_"
    "exact_192_job_replacement_online_execution_only"
)
V224_SOURCE_COMMIT: Final = "ef0c34ea2eedf305311fa27e3e9187239307e874"
V224_SOURCE_TREE: Final = "697492c60255aafef727c0bd8ba45b31bfef442a"
V224_MANIFEST_ID: Final = (
    "finance_v26_224_artifact_manifest:"
    "16f18a3fca68d190327d9d81f39e4251a817c97f2bb573e07018846424003c59"
)
V224_ARTIFACT_ROOT: Final = (
    "finance_v26_224_artifact_root:71435d07e0f486d01a4654007231ace5381465796d165f02f2e67e55ea602925"
)
V224_SUMMARY_ID: Final = (
    "finance_v26_224_execution_summary:"
    "8b88cb6cc97d9a0f57fcf3e0ab805510e960d1c80e6e7beef67fbea5f54f58b5"
)
V224_TRANSITION_ID: Final = (
    "finance_v26_224_transition:1670d9b380a87d2c178a48a5b3dc9b543611b092d7d27ce7af2cffdde1e00b73"
)
V224_CONSUMPTION_ID: Final = (
    "finance_v26_224_authorization_consumption_receipt:"
    "e784a94f87f8b275d50fdea51b9373c503753ae661a05349431a8d2cf6621aea"
)
V224_RUN_START_ID: Final = (
    "finance_v26_224_run_start_receipt:"
    "00ae0af03a4fd89a840b9ac2fa39c7b38e9c63a2c95740d7dd69570ff13e3629"
)
FAILURE_SHA256: Final = "651fb4b608ea3f399df980361cfa585307bf865e2a24eb03dbf00fbbcfa0aa6a"

ModelT = TypeVar("ModelT", bound=BaseModel)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def canonical_bytes(value: Any) -> bytes:
    return prior.canonical_bytes(value)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False), prefix=prefix
    )


def make_identity(
    model_type: type[ModelT],
    values: Mapping[str, Any],
    *,
    field: str,
    prefix: str,
) -> ModelT:
    payload = dict(values)
    payload[field] = "pending"
    provisional = model_type.model_construct(**payload)
    payload[field] = identity(provisional, field, prefix)
    return model_type.model_validate(payload)


class PostrunRepairAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    v224_manifest_id: str = V224_MANIFEST_ID
    v224_artifact_root: str = V224_ARTIFACT_ROOT
    v224_summary_id: str = V224_SUMMARY_ID
    v224_transition_id: str = V224_TRANSITION_ID
    v224_source_commit: str = V224_SOURCE_COMMIT
    v224_source_tree: str = V224_SOURCE_TREE
    formal_file_count: Literal[398] = 398
    formal_byte_count: Literal[680947] = 680_947
    manifest_member_count: Literal[397] = 397
    manifest_member_byte_count: Literal[609062] = 609_062
    exact_job_count: Literal[192] = 192
    request_intent_count: Literal[192] = 192
    failure_record_count: Literal[192] = 192
    unique_failure_sha256: str = FAILURE_SHA256
    response_metadata_count: Literal[0] = 0
    usage_metadata_count: Literal[0] = 0
    error_metadata_count: Literal[0] = 0
    provider_descriptor_count: Literal[0] = 0
    five_layer_file_count: Literal[0] = 0
    stored_summary_provider_call_count: Literal[0] = 0
    stored_summary_zero_call_interpretation_valid: Literal[False] = False
    exact_failure_locus: Literal["redacted_typed_dict_model_dump"] = (
        "redacted_typed_dict_model_dump"
    )
    root_cause_independently_reproduced: Literal[True] = True
    historical_authorization_consumed: Literal[True] = True
    historical_authorization_reusable: Literal[False] = False
    provider_calls_during_audit: Literal[0] = 0
    credential_lookups_during_audit: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PostrunRepairAudit:
        exact = (
            self.v224_manifest_id == V224_MANIFEST_ID
            and self.v224_artifact_root == V224_ARTIFACT_ROOT
            and self.v224_summary_id == V224_SUMMARY_ID
            and self.v224_transition_id == V224_TRANSITION_ID
            and self.v224_source_commit == V224_SOURCE_COMMIT
            and self.v224_source_tree == V224_SOURCE_TREE
            and self.unique_failure_sha256 == FAILURE_SHA256
        )
        if not exact or self.audit_id != identity(
            self, "audit_id", "finance_v26_225_postrun_repair_audit:"
        ):
            raise ValueError("v26.225 postrun repair Audit differs")
        return self


class RepairControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    postrun_repair_audit_id: str = Field(min_length=1)
    repaired_online_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    repaired_models_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    success_record_id: str = Field(min_length=1)
    error_record_id: str = Field(min_length=1)
    success_terminal_kind: Literal["first_response_abi_invalid"] = "first_response_abi_invalid"
    success_mock_http_calls: Literal[1] = 1
    error_mock_http_calls: Literal[1] = 1
    success_provider_descriptors: Literal[1] = 1
    error_provider_descriptors: Literal[1] = 1
    success_journal_files: Literal[4] = 4
    error_journal_files: Literal[4] = 4
    success_five_layer_files: Literal[5] = 5
    error_five_layer_files: Literal[0] = 0
    success_relation_closed: Literal[True] = True
    error_relation_closed: Literal[True] = True
    typed_dict_success_path_passed: Literal[True] = True
    typed_dict_error_path_passed: Literal[True] = True
    real_provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> RepairControlAudit:
        if self.audit_id != identity(self, "audit_id", "finance_v26_225_repair_control_audit:"):
            raise ValueError("v26.225 repair Control Audit differs")
        return self


class SourceMember(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class RepairPreflightSourceIdentity(FrozenModel):
    source_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    implementation_members: tuple[SourceMember, ...] = Field(min_length=4, max_length=4)
    implementation_member_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    detached_rebuild_required: Literal[True] = True
    real_provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_source(self) -> RepairPreflightSourceIdentity:
        paths = tuple(item.relative_path for item in self.implementation_members)
        if (
            paths != tuple(sorted(set(paths)))
            or canonical_sha256(
                tuple(
                    item.model_dump(mode="json", warnings=False)
                    for item in self.implementation_members
                )
            )
            != self.implementation_member_set_sha256
            or self.source_id
            != identity(self, "source_id", "finance_v26_225_repair_source_identity:")
        ):
            raise ValueError("v26.225 repair Source Identity differs")
        return self


class ConditionalReplacementAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    postrun_repair_audit_id: str = Field(min_length=1)
    repair_control_audit_id: str = Field(min_length=1)
    repair_source_identity_id: str = Field(min_length=1)
    repair_directive: str = REPAIR_DIRECTIVE
    repair_directive_sha256: str = REPAIR_DIRECTIVE_SHA256
    conditional_run_directive: str = CONDITIONAL_RUN_DIRECTIVE
    conditional_run_directive_sha256: str = CONDITIONAL_RUN_DIRECTIVE_SHA256
    repaired_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    repaired_source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    v224_artifact_root: str = V224_ARTIFACT_ROOT
    v224_manifest_id: str = V224_MANIFEST_ID
    v224_summary_id: str = V224_SUMMARY_ID
    v224_transition_id: str = V224_TRANSITION_ID
    v224_consumption_receipt_id: str = V224_CONSUMPTION_ID
    v224_run_start_receipt_id: str = V224_RUN_START_ID
    superseded_v223_authorization_id: str = prior.V223_AUTHORIZATION_ID
    superseded_v223_authorization_sha256: str = prior.V223_AUTHORIZATION_SHA256
    superseded_v223_composition_id: str = prior.V223_COMPOSITION_ID
    exact_v209_manifest_id: str = v223_models.V209_MANIFEST_ID
    exact_v209_artifact_root: str = v223_models.V209_ARTIFACT_ROOT
    exact_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    exact_job_set_sha256: str = prior.EXACT_JOB_SET_SHA256
    authorized_stage: str = REPLACEMENT_STAGE
    maximum_authorization_consumptions: int = 1
    exact_replacement_execution_authorized: bool = True
    failed_job_recovery_authorized: bool = False
    per_job_selective_rerun_authorized: bool = False
    condition_change_authorized: bool = False
    historical_response_reuse_authorized: bool = False
    caller_terminal_authorized: bool = False
    qa_integration_authorized: bool = False
    audit_passed_before_authorization: bool = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ConditionalReplacementAuthorization:
        exact_constants = (
            self.repair_directive == REPAIR_DIRECTIVE
            and self.repair_directive_sha256 == REPAIR_DIRECTIVE_SHA256
            and self.conditional_run_directive == CONDITIONAL_RUN_DIRECTIVE
            and self.conditional_run_directive_sha256 == CONDITIONAL_RUN_DIRECTIVE_SHA256
            and self.v224_artifact_root == V224_ARTIFACT_ROOT
            and self.v224_manifest_id == V224_MANIFEST_ID
            and self.v224_summary_id == V224_SUMMARY_ID
            and self.v224_transition_id == V224_TRANSITION_ID
            and self.v224_consumption_receipt_id == V224_CONSUMPTION_ID
            and self.v224_run_start_receipt_id == V224_RUN_START_ID
            and self.superseded_v223_authorization_id == prior.V223_AUTHORIZATION_ID
            and self.superseded_v223_authorization_sha256 == prior.V223_AUTHORIZATION_SHA256
            and self.superseded_v223_composition_id == prior.V223_COMPOSITION_ID
            and self.exact_v209_manifest_id == v223_models.V209_MANIFEST_ID
            and self.exact_v209_artifact_root == v223_models.V209_ARTIFACT_ROOT
            and self.exact_job_set_sha256 == prior.EXACT_JOB_SET_SHA256
            and self.authorized_stage == REPLACEMENT_STAGE
            and self.maximum_authorization_consumptions == 1
            and self.exact_replacement_execution_authorized
            and not self.failed_job_recovery_authorized
            and not self.per_job_selective_rerun_authorized
            and not self.condition_change_authorized
            and not self.historical_response_reuse_authorized
            and not self.caller_terminal_authorized
            and not self.qa_integration_authorized
            and self.audit_passed_before_authorization
        )
        if (
            not exact_constants
            or self.exact_job_ids != tuple(sorted(set(self.exact_job_ids)))
            or canonical_sha256(self.exact_job_ids) != self.exact_job_set_sha256
            or self.authorization_id
            != identity(
                self,
                "authorization_id",
                "finance_v26_225_repaired_replacement_execution_authorization:",
            )
        ):
            raise ValueError("v26.225 conditional replacement Authorization differs")
        return self


class ReplacementPreparation(FrozenModel):
    preparation_id: str = Field(min_length=1)
    postrun_repair_audit_id: str = Field(min_length=1)
    repair_control_audit_id: str = Field(min_length=1)
    repair_source_identity_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    authorization_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    repaired_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    repaired_source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    exact_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    exact_job_set_sha256: str = prior.EXACT_JOB_SET_SHA256
    request_success_control_passed: bool = True
    request_error_control_passed: bool = True
    intent_descriptor_reconciliation_control_passed: bool = True
    authorization_consumed: bool = False
    credential_lookups: int = 0
    provider_calls: int = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_preparation(self) -> ReplacementPreparation:
        if (
            self.exact_job_ids != tuple(sorted(set(self.exact_job_ids)))
            or canonical_sha256(self.exact_job_ids) != prior.EXACT_JOB_SET_SHA256
            or not self.repair_control_audit_id.startswith("finance_v26_225_repair_control_audit:")
            or not self.request_success_control_passed
            or not self.request_error_control_passed
            or not self.intent_descriptor_reconciliation_control_passed
            or self.authorization_consumed
            or self.credential_lookups != 0
            or self.provider_calls != 0
            or self.preparation_id
            != identity(self, "preparation_id", "finance_v26_225_repair_preparation:")
        ):
            raise ValueError("v26.225 replacement Preparation differs")
        return self


class AuthorizationConsumptionReceipt(FrozenModel):
    receipt_id: str = Field(min_length=1)
    preparation_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    authorization_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    consumed_at_utc: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
    prior_consumption_count: int = 0
    resulting_consumption_count: int = 1
    durable_before_credentials: bool = True
    historical_v223_authorization_reused: bool = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_receipt(self) -> AuthorizationConsumptionReceipt:
        if (
            self.prior_consumption_count != 0
            or self.resulting_consumption_count != 1
            or not self.durable_before_credentials
            or self.historical_v223_authorization_reused
            or self.receipt_id
            != identity(
                self,
                "receipt_id",
                "finance_v26_226_replacement_authorization_consumption_receipt:",
            )
        ):
            raise ValueError("v26.226 replacement consumption Receipt differs")
        return self


class RunStartReceipt(FrozenModel):
    receipt_id: str = Field(min_length=1)
    consumption_receipt_id: str = Field(min_length=1)
    preparation_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    exact_job_set_sha256: str = prior.EXACT_JOB_SET_SHA256
    execution_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    execution_source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    started_at_utc: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
    durable_before_credentials: bool = True
    replacement_execution: bool = True
    failed_job_recovery: bool = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_receipt(self) -> RunStartReceipt:
        if (
            self.exact_job_set_sha256 != prior.EXACT_JOB_SET_SHA256
            or not self.durable_before_credentials
            or not self.replacement_execution
            or self.failed_job_recovery
            or self.receipt_id
            != identity(self, "receipt_id", "finance_v26_226_replacement_run_start_receipt:")
        ):
            raise ValueError("v26.226 replacement Run Start Receipt differs")
        return self


class JobExecutionRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    job_ordinal: int = Field(ge=0, le=191)
    terminal_kind: prior.TerminalKind
    terminal_source: prior.TerminalSource
    provider_calls: tuple[prior.ProviderCallDescriptor, ...] = Field(max_length=23)
    raw: prior.RawExecutionDescriptor
    result: prior.ResultDescriptor
    trace: prior.TraceDescriptor
    outcome: prior.OutcomeDescriptor
    checkpoint: prior.CheckpointDescriptor
    replacement_attempt: Literal[True] = True
    rerun_attempt: Literal[False] = False
    recovery_attempt: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_record(self) -> JobExecutionRecord:
        evidence = (self.raw, self.result, self.trace, self.outcome, self.checkpoint)
        call_ids = tuple(item.descriptor_id for item in self.provider_calls)
        safe_job = hashlib.sha256(self.job_id.encode("utf-8")).hexdigest()
        expected_paths = (
            f"evidence/raw/{safe_job}.json",
            f"evidence/result/{safe_job}.json",
            f"evidence/trace/{safe_job}.json",
            f"evidence/outcome/{safe_job}.json",
            f"checkpoints/job_{self.job_ordinal:03d}.json",
        )
        sequences = tuple(item.persisted_sequence for item in evidence)
        namespaces = tuple(
            item.namespace_id for item in (self.raw, self.result, self.trace, self.outcome)
        )
        if (
            (self.terminal_kind in prior.FAILURE_TERMINAL_KINDS)
            != (self.terminal_source == "v26_218_source_bound_failure")
            or any(item.job_id != self.job_id for item in evidence)
            or any(item.run_start_receipt_id != self.run_start_receipt_id for item in evidence)
            or any(item.terminal_kind != self.terminal_kind for item in evidence)
            or tuple(item.call_ordinal for item in self.provider_calls)
            != tuple(range(len(self.provider_calls)))
            or any(item.job_id != self.job_id for item in self.provider_calls)
            or any(
                item.run_start_receipt_id != self.run_start_receipt_id
                for item in self.provider_calls
            )
            or len({item.provider_call_id for item in self.provider_calls})
            != len(self.provider_calls)
            or self.raw.provider_call_descriptor_ids != call_ids
            or self.trace.provider_call_descriptor_ids != call_ids
            or self.result.raw_descriptor_id != self.raw.descriptor_id
            or self.result.raw_namespace_id != self.raw.namespace_id
            or self.result.raw_persisted_sequence != self.raw.persisted_sequence
            or self.trace.raw_descriptor_id != self.raw.descriptor_id
            or self.trace.raw_namespace_id != self.raw.namespace_id
            or self.trace.result_descriptor_id != self.result.descriptor_id
            or self.trace.result_namespace_id != self.result.namespace_id
            or self.trace.result_persisted_sequence != self.result.persisted_sequence
            or self.outcome.trace_descriptor_id != self.trace.descriptor_id
            or self.outcome.trace_namespace_id != self.trace.namespace_id
            or self.outcome.trace_persisted_sequence != self.trace.persisted_sequence
            or self.checkpoint.outcome_descriptor_id != self.outcome.descriptor_id
            or self.checkpoint.outcome_namespace_id != self.outcome.namespace_id
            or self.checkpoint.outcome_persisted_sequence != self.outcome.persisted_sequence
            or self.checkpoint.job_ordinal != self.job_ordinal
            or len(set(namespaces)) != 4
            or tuple(item.relative_path for item in evidence) != expected_paths
            or sequences != (0, 1, 2, 3, 4)
            or self.record_id
            != identity(self, "record_id", "finance_v26_226_replacement_job_record:")
        ):
            raise ValueError("v26.226 replacement Job record differs")
        return self


class JobFailureRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    job_ordinal: int = Field(ge=0, le=191)
    failure_kind: prior.ExecutionFailureKind
    error_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_calls: tuple[prior.ProviderCallDescriptor, ...] = Field(max_length=23)
    terminal_evidence_admitted: Literal[False] = False
    five_layer_evidence_admitted: Literal[False] = False
    replacement_attempt: Literal[True] = True
    rerun_attempt: Literal[False] = False
    recovery_attempt: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_record(self) -> JobFailureRecord:
        if (
            tuple(item.call_ordinal for item in self.provider_calls)
            != tuple(range(len(self.provider_calls)))
            or any(item.job_id != self.job_id for item in self.provider_calls)
            or any(
                item.run_start_receipt_id != self.run_start_receipt_id
                for item in self.provider_calls
            )
            or len({item.provider_call_id for item in self.provider_calls})
            != len(self.provider_calls)
            or self.record_id
            != identity(self, "record_id", "finance_v26_226_replacement_job_failure:")
        ):
            raise ValueError("v26.226 replacement Job failure differs")
        return self


class ExecutionSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    preparation_id: str = Field(min_length=1)
    consumption_receipt_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    execution_status: Literal["completed", "incomplete"]
    records: tuple[JobExecutionRecord, ...] = Field(max_length=192)
    failure_records: tuple[JobFailureRecord, ...] = Field(max_length=192)
    exact_job_set_sha256: str = prior.EXACT_JOB_SET_SHA256
    exact_job_count: Literal[192] = 192
    attempted_job_count: Literal[192] = 192
    completed_job_record_count: int = Field(ge=0, le=192)
    failure_record_count: int = Field(ge=0, le=192)
    raw_count: int = Field(ge=0, le=192)
    result_count: int = Field(ge=0, le=192)
    trace_count: int = Field(ge=0, le=192)
    outcome_count: int = Field(ge=0, le=192)
    checkpoint_count: int = Field(ge=0, le=192)
    terminal_partition: dict[prior.TerminalKind, int]
    failure_partition: dict[prior.ExecutionFailureKind, int]
    request_intent_count: int = Field(ge=0, le=4416)
    provider_descriptor_count: int = Field(ge=0, le=4416)
    attempted_provider_call_lower_bound: int = Field(ge=0, le=4416)
    attempted_provider_call_upper_bound: int = Field(ge=0, le=4416)
    provider_call_count: int = Field(ge=0, le=4416)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    authorization_consumption_count: Literal[1] = 1
    run_start_receipt_count: Literal[1] = 1
    replacement_job_count: Literal[192] = 192
    rerun_job_count: Literal[0] = 0
    recovery_job_count: Literal[0] = 0
    qa_read_count: Literal[0] = 0
    empirical_estimate_count: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_summary(self) -> ExecutionSummary:
        ordinals = tuple(
            sorted(
                [item.job_ordinal for item in self.records]
                + [item.job_ordinal for item in self.failure_records]
            )
        )
        job_ids = tuple(
            sorted(
                [item.job_id for item in self.records]
                + [item.job_id for item in self.failure_records]
            )
        )
        calls = tuple(call for item in self.records for call in item.provider_calls) + tuple(
            call for item in self.failure_records for call in item.provider_calls
        )
        terminals = {kind: 0 for kind in prior.TERMINAL_KINDS}
        failures = {"unbound_provider_failure": 0, "host_failure": 0}
        for record in self.records:
            terminals[record.terminal_kind] += 1
        for failure in self.failure_records:
            failures[failure.failure_kind] += 1
        completed = len(self.records) == 192 and not self.failure_records
        layer_counts = (
            self.raw_count,
            self.result_count,
            self.trace_count,
            self.outcome_count,
            self.checkpoint_count,
        )
        if (
            ordinals != tuple(range(192))
            or len(set(job_ids)) != 192
            or canonical_sha256(job_ids) != self.exact_job_set_sha256
            or any(item.authorization_id != self.authorization_id for item in self.records)
            or any(item.authorization_id != self.authorization_id for item in self.failure_records)
            or any(item.run_start_receipt_id != self.run_start_receipt_id for item in self.records)
            or any(
                item.run_start_receipt_id != self.run_start_receipt_id
                for item in self.failure_records
            )
            or self.completed_job_record_count != len(self.records)
            or self.failure_record_count != len(self.failure_records)
            or any(value != len(self.records) for value in layer_counts)
            or dict(self.terminal_partition) != terminals
            or dict(self.failure_partition) != failures
            or self.provider_descriptor_count != len(calls)
            or self.provider_call_count != self.provider_descriptor_count
            or self.attempted_provider_call_lower_bound != self.provider_descriptor_count
            or self.attempted_provider_call_upper_bound != self.request_intent_count
            or self.input_tokens != sum(item.input_tokens for item in calls)
            or self.output_tokens != sum(item.output_tokens for item in calls)
            or (self.execution_status == "completed") != completed
            or self.summary_id != identity(self, "summary_id", "finance_v26_226_execution_summary:")
        ):
            raise ValueError("v26.226 replacement execution Summary differs")
        return self


class ProviderIntentCensus(FrozenModel):
    census_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    exact_job_count: Literal[192] = 192
    request_intent_count: int = Field(ge=0)
    provider_descriptor_count: int = Field(ge=0)
    response_metadata_count: int = Field(ge=0)
    error_metadata_count: int = Field(ge=0)
    usage_metadata_count: int = Field(ge=0)
    job_ids_with_request_intent_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_provider_relation_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    orphan_request_intent_count: int = Field(ge=0)
    orphan_descriptor_count: int = Field(ge=0)
    invalid_relation_count: int = Field(ge=0)
    relation_closed: bool
    completed_execution_requires_intent_descriptor_equality: bool = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_census(self) -> ProviderIntentCensus:
        expected_closed = (
            self.orphan_request_intent_count == 0
            and self.orphan_descriptor_count == 0
            and self.invalid_relation_count == 0
            and self.request_intent_count == self.provider_descriptor_count
            and self.response_metadata_count + self.error_metadata_count
            == self.provider_descriptor_count
            and self.usage_metadata_count == self.provider_descriptor_count
        )
        if (
            not self.completed_execution_requires_intent_descriptor_equality
            or self.relation_closed != expected_closed
            or self.census_id
            != identity(self, "census_id", "finance_v26_226_provider_intent_census:")
        ):
            raise ValueError("v26.226 Provider-intent Census differs")
        return self


class RepairPreflightGateEvaluation(FrozenModel):
    gate_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    postrun_repair_audit_id: str = Field(min_length=1)
    repair_control_audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    authorization_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    gates: tuple[
        Literal[
            "P0_EXACT_V224_FAILURE_RECONSTRUCTION_PASS",
            "P1_TYPED_DICT_SERIALIZATION_REPAIR_PASS",
            "P2_MOCK_SUCCESS_PROVIDER_JOURNAL_AND_FIVE_LAYERS_PASS",
            "P3_MOCK_ERROR_PROVIDER_JOURNAL_PASS",
            "P4_EXACT_PARENT_AND_192_JOB_BINDING_PASS",
            "P5_EXPECTED_BYTE_AND_FULL_REHASH_REJECTION_PASS",
            "P6_ZERO_REAL_PROVIDER_AND_CREDENTIAL_BOUNDARY_PASS",
        ],
        ...,
    ]
    passed: Literal[7] = 7
    failed: Literal[0] = 0
    real_provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> RepairPreflightGateEvaluation:
        if (
            len(self.gates) != 7
            or len(set(self.gates)) != 7
            or self.gate_id != identity(self, "gate_id", "finance_v26_225_repair_gate_evaluation:")
        ):
            raise ValueError("v26.225 repair Gate differs")
        return self


class AuthorizationAttackAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    authorization_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    attacks: Literal[8] = 8
    fully_rehashed_candidates: Literal[8] = 8
    rejected: Literal[8] = 8
    accepted: Literal[0] = 0
    post_guard_probes: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    real_provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> AuthorizationAttackAudit:
        if self.audit_id != identity(
            self, "audit_id", "finance_v26_225_authorization_attack_audit:"
        ):
            raise ValueError("v26.225 Authorization Attack Audit differs")
        return self


class RepairPreflightDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    gate_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    decision: Literal[
        "postresponse_serializer_repair_independent_audit_passed_"
        "replacement_online_execution_authorization_issued_not_consumed"
    ] = (
        "postresponse_serializer_repair_independent_audit_passed_"
        "replacement_online_execution_authorization_issued_not_consumed"
    )
    authorization_consumed: Literal[False] = False
    real_provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> RepairPreflightDecision:
        if self.decision_id != identity(self, "decision_id", "finance_v26_225_repair_decision:"):
            raise ValueError("v26.225 repair Decision differs")
        return self


class RepairPreflightTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    next_stage: Literal[
        "fresh_exact_v209_parent_bound_postresponse_serializer_repair_"
        "exact_192_job_replacement_online_execution_only"
    ] = REPLACEMENT_STAGE
    online_execution_authorized: Literal[True] = True
    authorization_consumed: Literal[False] = False
    replacement_or_recovery_after_next_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> RepairPreflightTransition:
        if self.transition_id != identity(
            self, "transition_id", "finance_v26_225_repair_transition:"
        ):
            raise ValueError("v26.225 repair Transition differs")
        return self


class Transition(FrozenModel):
    transition_id: str = Field(min_length=1)
    summary_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    execution_status: Literal["completed", "incomplete"]
    provider_intent_census_id: str = Field(min_length=1)
    status: Literal[
        "COMPLETED_AWAITING_POSTRUN_INDEPENDENT_AUDIT",
        "INCOMPLETE_AWAITING_POSTRUN_INDEPENDENT_AUDIT",
    ]
    next_stage: Literal[
        "fresh_exact_v209_parent_bound_replacement_execution_postrun_independent_audit_only"
    ] = "fresh_exact_v209_parent_bound_replacement_execution_postrun_independent_audit_only"
    replacement_or_recovery_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> Transition:
        expected = (
            "COMPLETED_AWAITING_POSTRUN_INDEPENDENT_AUDIT"
            if self.execution_status == "completed"
            else "INCOMPLETE_AWAITING_POSTRUN_INDEPENDENT_AUDIT"
        )
        if self.status != expected or self.transition_id != identity(
            self, "transition_id", "finance_v26_226_transition:"
        ):
            raise ValueError("v26.226 Transition differs")
        return self


class ArtifactMember(prior.ArtifactMember):
    pass


class RepairPreflightArtifactManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    members: tuple[ArtifactMember, ...]
    artifact_root: str = Field(min_length=1)
    total_member_bytes: int = Field(ge=0)
    self_excluding: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> RepairPreflightArtifactManifest:
        if (
            tuple(item.relative_path for item in self.members)
            != tuple(sorted(item.relative_path for item in self.members))
            or len({item.relative_path for item in self.members}) != len(self.members)
            or self.total_member_bytes != sum(item.byte_count for item in self.members)
            or self.artifact_root
            != canonical_hash(self.members, prefix="finance_v26_225_repair_artifact_root:")
            or self.manifest_id
            != identity(
                self,
                "manifest_id",
                "finance_v26_225_repair_artifact_manifest:",
            )
        ):
            raise ValueError("v26.225 repair Artifact Manifest differs")
        return self


def repair_preflight_artifact_manifest(
    run_id: str, payloads: Mapping[str, bytes]
) -> RepairPreflightArtifactManifest:
    members = tuple(
        ArtifactMember(
            relative_path=path,
            sha256=hashlib.sha256(payload).hexdigest(),
            byte_count=len(payload),
        )
        for path, payload in sorted(payloads.items())
    )
    artifact_root = canonical_hash(members, prefix="finance_v26_225_repair_artifact_root:")
    return make_identity(
        RepairPreflightArtifactManifest,
        {
            "run_id": run_id,
            "members": members,
            "artifact_root": artifact_root,
            "total_member_bytes": sum(item.byte_count for item in members),
        },
        field="manifest_id",
        prefix="finance_v26_225_repair_artifact_manifest:",
    )


class ArtifactManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    members: tuple[ArtifactMember, ...]
    artifact_root: str = Field(min_length=1)
    total_member_bytes: int = Field(ge=0)
    self_excluding: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> ArtifactManifest:
        if (
            tuple(item.relative_path for item in self.members)
            != tuple(sorted(item.relative_path for item in self.members))
            or len({item.relative_path for item in self.members}) != len(self.members)
            or self.total_member_bytes != sum(item.byte_count for item in self.members)
            or self.artifact_root
            != canonical_hash(self.members, prefix="finance_v26_226_artifact_root:")
            or self.manifest_id
            != identity(self, "manifest_id", "finance_v26_226_artifact_manifest:")
        ):
            raise ValueError("v26.226 Artifact Manifest differs")
        return self


def artifact_manifest(run_id: str, payloads: Mapping[str, bytes]) -> ArtifactManifest:
    members = tuple(
        ArtifactMember(
            relative_path=path,
            sha256=hashlib.sha256(payload).hexdigest(),
            byte_count=len(payload),
        )
        for path, payload in sorted(payloads.items())
    )
    return make_identity(
        ArtifactManifest,
        {
            "run_id": run_id,
            "members": members,
            "artifact_root": canonical_hash(members, prefix="finance_v26_226_artifact_root:"),
            "total_member_bytes": sum(item.byte_count for item in members),
        },
        field="manifest_id",
        prefix="finance_v26_226_artifact_manifest:",
    )
