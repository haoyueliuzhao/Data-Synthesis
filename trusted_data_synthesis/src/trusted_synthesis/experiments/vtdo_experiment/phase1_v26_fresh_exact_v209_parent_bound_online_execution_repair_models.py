from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, Final, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    provisional = model_type.model_construct(**{field: "pending"}, **payload)
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


class ConditionalReplacementAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    postrun_repair_audit_id: str = Field(min_length=1)
    repair_directive: str = REPAIR_DIRECTIVE
    repair_directive_sha256: str = REPAIR_DIRECTIVE_SHA256
    conditional_run_directive: str = CONDITIONAL_RUN_DIRECTIVE
    conditional_run_directive_sha256: str = CONDITIONAL_RUN_DIRECTIVE_SHA256
    repaired_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    repaired_source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    v224_artifact_root: str = V224_ARTIFACT_ROOT
    v224_consumption_receipt_id: str = V224_CONSUMPTION_ID
    superseded_v223_authorization_id: str = prior.V223_AUTHORIZATION_ID
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
            and self.v224_consumption_receipt_id == V224_CONSUMPTION_ID
            and self.superseded_v223_authorization_id == prior.V223_AUTHORIZATION_ID
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


class JobExecutionRecord(prior.JobExecutionRecord):
    authorization_id: str = Field(min_length=1)
    replacement_attempt: Literal[True] = True


class JobFailureRecord(prior.JobFailureRecord):
    authorization_id: str = Field(min_length=1)
    replacement_attempt: Literal[True] = True


class ExecutionSummary(prior.ExecutionSummary):
    authorization_id: str = Field(min_length=1)
    records: tuple[JobExecutionRecord, ...] = Field(max_length=192)
    failure_records: tuple[JobFailureRecord, ...] = Field(max_length=192)
    replacement_job_count: Literal[192] = 192

    @model_validator(mode="after")
    def validate_replacement_summary(self) -> ExecutionSummary:
        if (
            any(item.authorization_id != self.authorization_id for item in self.records)
            or any(item.authorization_id != self.authorization_id for item in self.failure_records)
            or self.replacement_job_count != 192
        ):
            raise ValueError("v26.226 replacement Summary lineage differs")
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
    completed_execution_requires_intent_descriptor_equality: bool = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_census(self) -> ProviderIntentCensus:
        if (
            not self.completed_execution_requires_intent_descriptor_equality
            or self.census_id
            != identity(self, "census_id", "finance_v26_226_provider_intent_census:")
        ):
            raise ValueError("v26.226 Provider-intent Census differs")
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
