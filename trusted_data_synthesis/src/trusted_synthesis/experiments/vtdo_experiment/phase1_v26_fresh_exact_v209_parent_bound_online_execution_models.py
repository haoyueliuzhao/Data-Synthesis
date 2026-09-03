from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Final, Literal, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_exact_v209_parent_bound_online_execution.v1"
CONSUMED_STAGE: Final = (
    "fresh_exact_v209_execution_condition_authoritative_parent_bound_"
    "exact_192_job_online_execution_only"
)
NEXT_STAGE: Final = (
    "fresh_exact_v209_execution_condition_authoritative_parent_bound_"
    "exact_192_job_online_execution_postrun_independent_audit_only"
)
V223_AUTHORIZATION_ID: Final = (
    "fresh_exact_v209_parent_bound_exact_online_execution_authorization:"
    "72627e0352682a0737407d7ceb88ea17e9d087077895c1288aa41f670ca2d33b"
)
V223_AUTHORIZATION_SHA256: Final = (
    "7470f83884920f7d5cf66f05afef0f90af13a7927744db019e8aa4e4b801920f"
)
V223_MANIFEST_ID: Final = (
    "finance_v26_223_artifact_manifest:"
    "7d08829ff3fb4c4e021b3c24b1b4186e3519e93afe04b8be34c71d2e97dab8f4"
)
V223_ARTIFACT_ROOT: Final = (
    "finance_v26_223_artifact_root:2ce7768c33de5416bccb403877ffa21d7d91a08d8cd8487582db12869a6c5c8e"
)
V223_COMPOSITION_ID: Final = (
    "fresh_exact_v209_parent_bound_online_execution_composition_contract:"
    "094e822857be7937a814dbe0465c9145a9249daeeb8e874869f06928502d357c"
)
EXACT_JOB_SET_SHA256: Final = "153ad4c7089e75954a223263a183bc969d2c7d57e2081c49bed9096b11bd60f7"

MainTerminalKind = Literal[
    "completed_invalid",
    "completed_qualified",
    "correction_action_reference_invalid",
    "correction_attempt_typed_invalid",
    "correction_response_abi_invalid",
    "final_response_abi_invalid",
    "first_action_reference_invalid",
    "first_response_abi_invalid",
]
FailureTerminalKind = Literal["instrument_failure", "privacy_rejection"]
TerminalKind = MainTerminalKind | FailureTerminalKind
TerminalSource = Literal[
    "current_state_runner_observation",
    "v26_218_source_bound_failure",
]
MAIN_TERMINAL_KINDS: Final[tuple[MainTerminalKind, ...]] = (
    "completed_invalid",
    "completed_qualified",
    "correction_action_reference_invalid",
    "correction_attempt_typed_invalid",
    "correction_response_abi_invalid",
    "final_response_abi_invalid",
    "first_action_reference_invalid",
    "first_response_abi_invalid",
)
FAILURE_TERMINAL_KINDS: Final[tuple[FailureTerminalKind, ...]] = (
    "instrument_failure",
    "privacy_rejection",
)
TERMINAL_KINDS: Final[tuple[TerminalKind, ...]] = (
    *MAIN_TERMINAL_KINDS,
    *FAILURE_TERMINAL_KINDS,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


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


def _terminal_source_matches(kind: TerminalKind, source: TerminalSource) -> bool:
    if kind in FAILURE_TERMINAL_KINDS:
        return source == "v26_218_source_bound_failure"
    return source == "current_state_runner_observation"


def _safe_relative_path(path: str) -> bool:
    parts = path.split("/")
    return not path.startswith("/") and all(part not in ("", ".", "..") for part in parts)


def provider_call_identity(
    *,
    run_start_receipt_id: str,
    job_id: str,
    call_ordinal: int,
    request_sha256: str,
    intention_sha256: str,
) -> str:
    return canonical_hash(
        {
            "run_start_receipt_id": run_start_receipt_id,
            "job_id": job_id,
            "call_ordinal": call_ordinal,
            "request_sha256": request_sha256,
            "intention_sha256": intention_sha256,
        },
        prefix="finance_v26_224_provider_call:",
    )


class ExternalExecutionAuthorization(FrozenModel):
    external_authorization_id: str = Field(min_length=1)
    review_sha256: Literal["10733a734b94693194eb85ac4ab0ee4fe475b48cf2cca5724c936308ed91cbb0"]
    review_byte_count: Literal[15248] = 15_248
    review_result: Literal["PASSED_AS_SCOPED"] = "PASSED_AS_SCOPED"
    blocking_defect: Literal["NONE_FOUND"] = "NONE_FOUND"
    operator_directive: Literal["参照审计，并行开展实验"] = "参照审计，并行开展实验"
    operator_directive_sha256: Literal[
        "2520ed8c585242e0792249256ee8306c3d8397891589cce5bd40a20b06c641de"
    ]
    operator_directive_byte_count: Literal[33] = 33
    v223_authorization_id: Literal[
        "fresh_exact_v209_parent_bound_exact_online_execution_authorization:"
        "72627e0352682a0737407d7ceb88ea17e9d087077895c1288aa41f670ca2d33b"
    ] = V223_AUTHORIZATION_ID
    authorized_stage: Literal[
        "fresh_exact_v209_execution_condition_authoritative_parent_bound_"
        "exact_192_job_online_execution_only"
    ] = CONSUMED_STAGE
    exact_manifest_execution_authorized: Literal[True] = True
    parallel_job_scheduling_authorized: Literal[True] = True
    maximum_authorization_consumptions: Literal[1] = 1
    replacement_execution_authorized: Literal[False] = False
    failed_job_rerun_authorized: Literal[False] = False
    recovery_execution_authorized: Literal[False] = False
    postrun_independent_audit_required: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalExecutionAuthorization:
        directive = self.operator_directive.encode("utf-8")
        if (
            len(directive) != self.operator_directive_byte_count
            or hashlib.sha256(directive).hexdigest() != self.operator_directive_sha256
            or self.external_authorization_id
            != identity(
                self,
                "external_authorization_id",
                "finance_v26_224_external_execution_authorization:",
            )
        ):
            raise ValueError("v26.224 external execution authorization differs")
        return self


class V223Freeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    source_commit: Literal["5eed1e0bb56757e3046391a8d25d522dea577975"]
    source_tree: Literal["119c4b0af09d958b34548933d55512bee5e5ac9b"]
    formal_file_count: Literal[17] = 17
    formal_total_byte_count: Literal[136590] = 136_590
    manifest_member_count: Literal[16] = 16
    manifest_member_byte_count: Literal[133829] = 133_829
    artifact_manifest_id: Literal[
        "finance_v26_223_artifact_manifest:"
        "7d08829ff3fb4c4e021b3c24b1b4186e3519e93afe04b8be34c71d2e97dab8f4"
    ] = V223_MANIFEST_ID
    artifact_root: Literal[
        "finance_v26_223_artifact_root:"
        "2ce7768c33de5416bccb403877ffa21d7d91a08d8cd8487582db12869a6c5c8e"
    ] = V223_ARTIFACT_ROOT
    composition_contract_id: Literal[
        "fresh_exact_v209_parent_bound_online_execution_composition_contract:"
        "094e822857be7937a814dbe0465c9145a9249daeeb8e874869f06928502d357c"
    ] = V223_COMPOSITION_ID
    authorization_id: Literal[
        "fresh_exact_v209_parent_bound_exact_online_execution_authorization:"
        "72627e0352682a0737407d7ceb88ea17e9d087077895c1288aa41f670ca2d33b"
    ] = V223_AUTHORIZATION_ID
    authorization_file_sha256: Literal[
        "7470f83884920f7d5cf66f05afef0f90af13a7927744db019e8aa4e4b801920f"
    ] = V223_AUTHORIZATION_SHA256
    authorization_file_byte_count: Literal[35090] = 35_090
    exact_job_set_sha256: Literal[
        "153ad4c7089e75954a223263a183bc969d2c7d57e2081c49bed9096b11bd60f7"
    ] = EXACT_JOB_SET_SHA256
    exact_package_count: Literal[32] = 32
    exact_job_count: Literal[192] = 192
    exact_coordinate_count: Literal[792] = 792
    authorization_issued: Literal[True] = True
    authorization_consumed_before_v224: Literal[False] = False
    provider_calls_before_v224: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V223Freeze:
        if self.freeze_id != identity(
            self, "freeze_id", "finance_v26_224_v223_authorization_freeze:"
        ):
            raise ValueError("v26.224 v26.223 Freeze differs")
        return self


class ExecutionPreparation(FrozenModel):
    preparation_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v223_freeze_id: str = Field(min_length=1)
    authorization_id: Literal[
        "fresh_exact_v209_parent_bound_exact_online_execution_authorization:"
        "72627e0352682a0737407d7ceb88ea17e9d087077895c1288aa41f670ca2d33b"
    ] = V223_AUTHORIZATION_ID
    authorization_bytes_sha256: Literal[
        "7470f83884920f7d5cf66f05afef0f90af13a7927744db019e8aa4e4b801920f"
    ] = V223_AUTHORIZATION_SHA256
    authorization_byte_count: Literal[35090] = 35_090
    composition_contract_id: Literal[
        "fresh_exact_v209_parent_bound_online_execution_composition_contract:"
        "094e822857be7937a814dbe0465c9145a9249daeeb8e874869f06928502d357c"
    ] = V223_COMPOSITION_ID
    exact_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    exact_job_set_sha256: Literal[
        "153ad4c7089e75954a223263a183bc969d2c7d57e2081c49bed9096b11bd60f7"
    ] = EXACT_JOB_SET_SHA256
    exact_package_count: Literal[32] = 32
    exact_job_count: Literal[192] = 192
    exact_registered_coordinate_count: Literal[792] = 792
    main_terminal_kinds: tuple[MainTerminalKind, ...] = MAIN_TERMINAL_KINDS
    failure_terminal_kinds: tuple[FailureTerminalKind, ...] = FAILURE_TERMINAL_KINDS
    authorization_consumed: Literal[False] = False
    consumption_receipts: Literal[0] = 0
    run_start_receipts: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    provider_calls: Literal[0] = 0
    replacement_job_count: Literal[0] = 0
    rerun_job_count: Literal[0] = 0
    recovery_job_count: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_preparation(self) -> ExecutionPreparation:
        if (
            self.exact_job_ids != tuple(sorted(set(self.exact_job_ids)))
            or canonical_sha256(self.exact_job_ids) != self.exact_job_set_sha256
            or self.main_terminal_kinds != MAIN_TERMINAL_KINDS
            or self.failure_terminal_kinds != FAILURE_TERMINAL_KINDS
            or self.preparation_id
            != identity(self, "preparation_id", "finance_v26_224_execution_preparation:")
        ):
            raise ValueError("v26.224 execution Preparation differs")
        return self


class AuthorizationConsumptionReceipt(FrozenModel):
    receipt_id: str = Field(min_length=1)
    preparation_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    authorization_id: Literal[
        "fresh_exact_v209_parent_bound_exact_online_execution_authorization:"
        "72627e0352682a0737407d7ceb88ea17e9d087077895c1288aa41f670ca2d33b"
    ] = V223_AUTHORIZATION_ID
    authorization_bytes_sha256: Literal[
        "7470f83884920f7d5cf66f05afef0f90af13a7927744db019e8aa4e4b801920f"
    ] = V223_AUTHORIZATION_SHA256
    authorization_byte_count: Literal[35090] = 35_090
    consumed_stage: Literal[
        "fresh_exact_v209_execution_condition_authoritative_parent_bound_"
        "exact_192_job_online_execution_only"
    ] = CONSUMED_STAGE
    consumed_at_utc: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
    prior_consumption_count: Literal[0] = 0
    consumption_ordinal: Literal[1] = 1
    resulting_consumption_count: Literal[1] = 1
    durable_before_credentials: Literal[True] = True
    authorization_consumed: Literal[True] = True
    authorization_reusable: Literal[False] = False
    replacement_authorization_permitted: Literal[False] = False
    credential_lookups: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_receipt(self) -> AuthorizationConsumptionReceipt:
        if self.receipt_id != identity(
            self,
            "receipt_id",
            "finance_v26_224_authorization_consumption_receipt:",
        ):
            raise ValueError("v26.224 authorization consumption Receipt differs")
        return self


class RunStartReceipt(FrozenModel):
    receipt_id: str = Field(min_length=1)
    consumption_receipt_id: str = Field(min_length=1)
    preparation_id: str = Field(min_length=1)
    authorization_id: Literal[
        "fresh_exact_v209_parent_bound_exact_online_execution_authorization:"
        "72627e0352682a0737407d7ceb88ea17e9d087077895c1288aa41f670ca2d33b"
    ] = V223_AUTHORIZATION_ID
    exact_job_set_sha256: Literal[
        "153ad4c7089e75954a223263a183bc969d2c7d57e2081c49bed9096b11bd60f7"
    ] = EXACT_JOB_SET_SHA256
    execution_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    execution_source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    tracked_tree_clean_before_receipt: Literal[True] = True
    started_at_utc: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
    authorization_consumption_ordinal: Literal[1] = 1
    manifest_execution_ordinal: Literal[1] = 1
    durable_before_credentials: Literal[True] = True
    credential_lookup_authorized_after_receipt: Literal[True] = True
    replacement_execution_forbidden: Literal[True] = True
    failed_job_rerun_forbidden: Literal[True] = True
    recovery_execution_forbidden: Literal[True] = True
    credential_lookups_at_receipt: Literal[0] = 0
    provider_calls_at_receipt: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_receipt(self) -> RunStartReceipt:
        if self.receipt_id != identity(self, "receipt_id", "finance_v26_224_run_start_receipt:"):
            raise ValueError("v26.224 Run Start Receipt differs")
        return self


class ProviderCallArtifact(FrozenModel):
    artifact_id: str = Field(min_length=1)
    provider_call_id: str = Field(min_length=1)
    artifact_kind: Literal[
        "request_metadata", "response_metadata", "usage_metadata", "error_metadata"
    ]
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)
    public_projection: dict[str, Any] | None = None
    public_projection_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    public_projection_present: bool
    redacted: Literal[True] = True
    prompt_content_present: Literal[False] = False
    raw_provider_response_present: Literal[False] = False
    private_reasoning_present: Literal[False] = False
    credential_content_present: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_artifact(self) -> ProviderCallArtifact:
        projection_present = self.public_projection is not None
        if (
            not _safe_relative_path(self.relative_path)
            or self.public_projection_present != projection_present
            or projection_present != (self.public_projection_sha256 is not None)
            or (
                self.public_projection is not None
                and canonical_sha256(self.public_projection) != self.public_projection_sha256
            )
            or self.artifact_id
            != identity(self, "artifact_id", "finance_v26_224_redacted_provider_call_artifact:")
        ):
            raise ValueError("v26.224 redacted Provider artifact differs")
        return self


class ProviderCallDescriptor(FrozenModel):
    descriptor_id: str = Field(min_length=1)
    provider_call_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    call_ordinal: int = Field(ge=0, le=22)
    intention_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["succeeded", "provider_error", "transport_error"]
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    error_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    artifacts: tuple[ProviderCallArtifact, ...] = Field(min_length=1, max_length=4)
    redacted: Literal[True] = True
    raw_request_present: Literal[False] = False
    raw_response_present: Literal[False] = False
    private_reasoning_present: Literal[False] = False
    credential_content_present: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_descriptor(self) -> ProviderCallDescriptor:
        paths = tuple(item.relative_path for item in self.artifacts)
        succeeded_shape = self.response_sha256 is not None and self.error_sha256 is None
        failure_shape = self.response_sha256 is None and self.error_sha256 is not None
        if (
            (self.status == "succeeded" and not succeeded_shape)
            or (self.status != "succeeded" and not failure_shape)
            or self.provider_call_id
            != provider_call_identity(
                run_start_receipt_id=self.run_start_receipt_id,
                job_id=self.job_id,
                call_ordinal=self.call_ordinal,
                request_sha256=self.request_sha256,
                intention_sha256=self.intention_sha256,
            )
            or paths != tuple(sorted(set(paths)))
            or any(item.provider_call_id != self.provider_call_id for item in self.artifacts)
            or self.descriptor_id
            != identity(
                self,
                "descriptor_id",
                "finance_v26_224_redacted_provider_call_descriptor:",
            )
        ):
            raise ValueError("v26.224 redacted Provider Call Descriptor differs")
        return self


class RawExecutionDescriptor(FrozenModel):
    descriptor_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    namespace_id: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    terminal_kind: TerminalKind
    terminal_source: TerminalSource
    provider_call_descriptor_ids: tuple[str, ...] = Field(max_length=23)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload_byte_count: int = Field(gt=0)
    persisted_sequence: int = Field(ge=0)
    empirical_execution: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_descriptor(self) -> RawExecutionDescriptor:
        if (
            not _safe_relative_path(self.relative_path)
            or not _terminal_source_matches(self.terminal_kind, self.terminal_source)
            or len(set(self.provider_call_descriptor_ids)) != len(self.provider_call_descriptor_ids)
            or self.descriptor_id
            != identity(self, "descriptor_id", "finance_v26_224_empirical_raw_descriptor:")
        ):
            raise ValueError("v26.224 empirical Raw descriptor differs")
        return self


class ResultDescriptor(FrozenModel):
    descriptor_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    namespace_id: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    terminal_kind: TerminalKind
    raw_descriptor_id: str = Field(min_length=1)
    raw_namespace_id: str = Field(min_length=1)
    raw_persisted_sequence: int = Field(ge=0)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload_byte_count: int = Field(gt=0)
    persisted_sequence: int = Field(gt=0)
    empirical_execution: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_descriptor(self) -> ResultDescriptor:
        if (
            not _safe_relative_path(self.relative_path)
            or self.raw_persisted_sequence >= self.persisted_sequence
            or self.descriptor_id
            != identity(self, "descriptor_id", "finance_v26_224_empirical_result_descriptor:")
        ):
            raise ValueError("v26.224 empirical Result descriptor differs")
        return self


class TraceDescriptor(FrozenModel):
    descriptor_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    namespace_id: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    terminal_kind: TerminalKind
    raw_descriptor_id: str = Field(min_length=1)
    raw_namespace_id: str = Field(min_length=1)
    result_descriptor_id: str = Field(min_length=1)
    result_namespace_id: str = Field(min_length=1)
    result_persisted_sequence: int = Field(gt=0)
    provider_call_descriptor_ids: tuple[str, ...] = Field(max_length=23)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload_byte_count: int = Field(gt=0)
    persisted_sequence: int = Field(gt=0)
    empirical_execution: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_descriptor(self) -> TraceDescriptor:
        if (
            not _safe_relative_path(self.relative_path)
            or self.result_persisted_sequence >= self.persisted_sequence
            or len(set(self.provider_call_descriptor_ids)) != len(self.provider_call_descriptor_ids)
            or self.descriptor_id
            != identity(self, "descriptor_id", "finance_v26_224_empirical_trace_descriptor:")
        ):
            raise ValueError("v26.224 empirical Trace descriptor differs")
        return self


class OutcomeDescriptor(FrozenModel):
    descriptor_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    namespace_id: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    terminal_kind: TerminalKind
    trace_descriptor_id: str = Field(min_length=1)
    trace_namespace_id: str = Field(min_length=1)
    trace_persisted_sequence: int = Field(gt=0)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload_byte_count: int = Field(gt=0)
    persisted_sequence: int = Field(gt=0)
    empirical_execution: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_descriptor(self) -> OutcomeDescriptor:
        if (
            not _safe_relative_path(self.relative_path)
            or self.trace_persisted_sequence >= self.persisted_sequence
            or self.descriptor_id
            != identity(self, "descriptor_id", "finance_v26_224_empirical_outcome_descriptor:")
        ):
            raise ValueError("v26.224 empirical Outcome descriptor differs")
        return self


class CheckpointDescriptor(FrozenModel):
    descriptor_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    job_ordinal: int = Field(ge=0, le=191)
    namespace_id: Literal["finance_v26_224_checkpoint_namespace"] = (
        "finance_v26_224_checkpoint_namespace"
    )
    relative_path: str = Field(min_length=1)
    terminal_kind: TerminalKind
    outcome_descriptor_id: str = Field(min_length=1)
    outcome_namespace_id: str = Field(min_length=1)
    outcome_persisted_sequence: int = Field(gt=0)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload_byte_count: int = Field(gt=0)
    persisted_sequence: int = Field(gt=0)
    empirical_execution: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_descriptor(self) -> CheckpointDescriptor:
        if (
            not _safe_relative_path(self.relative_path)
            or self.outcome_persisted_sequence >= self.persisted_sequence
            or self.descriptor_id
            != identity(
                self,
                "descriptor_id",
                "finance_v26_224_empirical_checkpoint_descriptor:",
            )
        ):
            raise ValueError("v26.224 empirical Checkpoint descriptor differs")
        return self


class JobExecutionRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    authorization_id: Literal[
        "fresh_exact_v209_parent_bound_exact_online_execution_authorization:"
        "72627e0352682a0737407d7ceb88ea17e9d087077895c1288aa41f670ca2d33b"
    ] = V223_AUTHORIZATION_ID
    job_id: str = Field(min_length=1)
    job_ordinal: int = Field(ge=0, le=191)
    terminal_kind: TerminalKind
    terminal_source: TerminalSource
    provider_calls: tuple[ProviderCallDescriptor, ...] = Field(max_length=23)
    raw: RawExecutionDescriptor
    result: ResultDescriptor
    trace: TraceDescriptor
    outcome: OutcomeDescriptor
    checkpoint: CheckpointDescriptor
    replacement_attempt: Literal[False] = False
    rerun_attempt: Literal[False] = False
    recovery_attempt: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_record(self) -> JobExecutionRecord:
        evidence = (self.raw, self.result, self.trace, self.outcome, self.checkpoint)
        call_descriptor_ids = tuple(item.descriptor_id for item in self.provider_calls)
        sequences = tuple(item.persisted_sequence for item in evidence)
        namespaces = tuple(
            item.namespace_id for item in (self.raw, self.result, self.trace, self.outcome)
        )
        paths = tuple(item.relative_path for item in evidence)
        if (
            not _terminal_source_matches(self.terminal_kind, self.terminal_source)
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
            or self.raw.provider_call_descriptor_ids != call_descriptor_ids
            or self.trace.provider_call_descriptor_ids != call_descriptor_ids
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
            or len(set(namespaces)) != len(namespaces)
            or len(set(paths)) != len(paths)
            or sequences != tuple(sorted(set(sequences)))
            or self.record_id
            != identity(self, "record_id", "finance_v26_224_online_job_execution_record:")
        ):
            raise ValueError("v26.224 Job execution record differs")
        return self


ExecutionFailureKind = Literal["unbound_provider_failure", "host_failure"]


class JobFailureRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    authorization_id: Literal[
        "fresh_exact_v209_parent_bound_exact_online_execution_authorization:"
        "72627e0352682a0737407d7ceb88ea17e9d087077895c1288aa41f670ca2d33b"
    ] = V223_AUTHORIZATION_ID
    job_id: str = Field(min_length=1)
    job_ordinal: int = Field(ge=0, le=191)
    failure_kind: ExecutionFailureKind
    error_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_calls: tuple[ProviderCallDescriptor, ...] = Field(max_length=23)
    terminal_evidence_admitted: Literal[False] = False
    five_layer_evidence_admitted: Literal[False] = False
    replacement_attempt: Literal[False] = False
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
            or self.record_id != identity(self, "record_id", "finance_v26_224_job_failure_record:")
        ):
            raise ValueError("v26.224 Job failure record differs")
        return self


class ExecutionSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    preparation_id: str = Field(min_length=1)
    consumption_receipt_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    authorization_id: Literal[
        "fresh_exact_v209_parent_bound_exact_online_execution_authorization:"
        "72627e0352682a0737407d7ceb88ea17e9d087077895c1288aa41f670ca2d33b"
    ] = V223_AUTHORIZATION_ID
    execution_status: Literal["completed", "incomplete"]
    records: tuple[JobExecutionRecord, ...] = Field(max_length=192)
    failure_records: tuple[JobFailureRecord, ...] = Field(max_length=192)
    exact_job_set_sha256: Literal[
        "153ad4c7089e75954a223263a183bc969d2c7d57e2081c49bed9096b11bd60f7"
    ] = EXACT_JOB_SET_SHA256
    exact_job_count: Literal[192] = 192
    attempted_job_count: Literal[192] = 192
    completed_job_record_count: int = Field(ge=0, le=192)
    failure_record_count: int = Field(ge=0, le=192)
    raw_count: int = Field(ge=0, le=192)
    result_count: int = Field(ge=0, le=192)
    trace_count: int = Field(ge=0, le=192)
    outcome_count: int = Field(ge=0, le=192)
    checkpoint_count: int = Field(ge=0, le=192)
    terminal_partition: dict[TerminalKind, int]
    failure_partition: dict[ExecutionFailureKind, int]
    provider_call_count: int = Field(ge=0, le=4416)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    authorization_consumption_count: Literal[1] = 1
    run_start_receipt_count: Literal[1] = 1
    replacement_job_count: Literal[0] = 0
    rerun_job_count: Literal[0] = 0
    recovery_job_count: Literal[0] = 0
    qa_read_count: Literal[0] = 0
    empirical_estimate_count: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_summary(self) -> ExecutionSummary:
        record_job_ids = tuple(item.job_id for item in self.records)
        failure_job_ids = tuple(item.job_id for item in self.failure_records)
        all_job_ids = record_job_ids + failure_job_ids
        record_ordinals = tuple(item.job_ordinal for item in self.records)
        failure_ordinals = tuple(item.job_ordinal for item in self.failure_records)
        terminal_partition = {kind: 0 for kind in TERMINAL_KINDS}
        failure_partition = {
            "unbound_provider_failure": 0,
            "host_failure": 0,
        }
        for record in self.records:
            terminal_partition[record.terminal_kind] += 1
        for failure in self.failure_records:
            failure_partition[failure.failure_kind] += 1
        calls = tuple(
            call for item in (*self.records, *self.failure_records) for call in item.provider_calls
        )
        expected_completed = len(self.failure_records) == 0 and len(self.records) == 192
        layer_counts = (
            self.raw_count,
            self.result_count,
            self.trace_count,
            self.outcome_count,
            self.checkpoint_count,
        )
        if (
            record_ordinals != tuple(sorted(record_ordinals))
            or failure_ordinals != tuple(sorted(failure_ordinals))
            or set(record_ordinals).intersection(failure_ordinals)
            or tuple(sorted((*record_ordinals, *failure_ordinals))) != tuple(range(192))
            or len(set(all_job_ids)) != 192
            or canonical_sha256(tuple(sorted(all_job_ids))) != self.exact_job_set_sha256
            or any(
                item.run_start_receipt_id != self.run_start_receipt_id
                for item in (*self.records, *self.failure_records)
            )
            or self.completed_job_record_count != len(self.records)
            or self.failure_record_count != len(self.failure_records)
            or any(count != len(self.records) for count in layer_counts)
            or dict(self.terminal_partition) != terminal_partition
            or dict(self.failure_partition) != failure_partition
            or self.provider_call_count != len(calls)
            or self.input_tokens != sum(call.input_tokens for call in calls)
            or self.output_tokens != sum(call.output_tokens for call in calls)
            or (self.execution_status == "completed") != expected_completed
            or self.summary_id != identity(self, "summary_id", "finance_v26_224_execution_summary:")
        ):
            raise ValueError("v26.224 execution Summary differs")
        return self


class Transition(FrozenModel):
    transition_id: str = Field(min_length=1)
    summary_id: str = Field(min_length=1)
    authorization_id: Literal[
        "fresh_exact_v209_parent_bound_exact_online_execution_authorization:"
        "72627e0352682a0737407d7ceb88ea17e9d087077895c1288aa41f670ca2d33b"
    ] = V223_AUTHORIZATION_ID
    execution_status: Literal["completed", "incomplete"]
    consumed_stage: Literal[
        "fresh_exact_v209_execution_condition_authoritative_parent_bound_"
        "exact_192_job_online_execution_only"
    ] = CONSUMED_STAGE
    status: Literal[
        "COMPLETED_AWAITING_POSTRUN_INDEPENDENT_AUDIT",
        "INCOMPLETE_AWAITING_POSTRUN_INDEPENDENT_AUDIT",
    ]
    next_stage: Literal[
        "fresh_exact_v209_execution_condition_authoritative_parent_bound_"
        "exact_192_job_online_execution_postrun_independent_audit_only"
    ] = NEXT_STAGE
    next_stage_authorized: Literal[False] = False
    postrun_independent_audit_only: Literal[True] = True
    authorization_consumed_exactly_once: Literal[True] = True
    authorization_reuse_forbidden: Literal[True] = True
    replacement_execution_forbidden: Literal[True] = True
    failed_job_rerun_forbidden: Literal[True] = True
    recovery_execution_forbidden: Literal[True] = True
    further_provider_calls_forbidden: Literal[True] = True
    qa_and_empirical_estimation_forbidden: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> Transition:
        expected_status = (
            "COMPLETED_AWAITING_POSTRUN_INDEPENDENT_AUDIT"
            if self.execution_status == "completed"
            else "INCOMPLETE_AWAITING_POSTRUN_INDEPENDENT_AUDIT"
        )
        if self.status != expected_status or self.transition_id != identity(
            self, "transition_id", "finance_v26_224_transition:"
        ):
            raise ValueError("v26.224 Transition differs")
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
        projection = tuple(item.model_dump(mode="json", warnings=False) for item in self.members)
        if (
            paths != tuple(sorted(set(paths)))
            or self.file_count != len(self.members)
            or self.total_byte_count != sum(item.byte_count for item in self.members)
            or self.artifact_root
            != canonical_hash(projection, prefix="finance_v26_224_artifact_root:")
            or self.manifest_id
            != identity(self, "manifest_id", "finance_v26_224_artifact_manifest:")
        ):
            raise ValueError("v26.224 Artifact Manifest differs")
        return self


def artifact_manifest(run_id: str, payloads: Mapping[str, bytes]) -> ArtifactManifest:
    members = tuple(
        ArtifactMember(
            relative_path=name,
            sha256=hashlib.sha256(payload).hexdigest(),
            byte_count=len(payload),
        )
        for name, payload in sorted(payloads.items())
    )
    projection = tuple(item.model_dump(mode="json", warnings=False) for item in members)
    return cast(
        ArtifactManifest,
        make_identity(
            ArtifactManifest,
            {
                "run_id": run_id,
                "members": members,
                "file_count": len(members),
                "total_byte_count": sum(item.byte_count for item in members),
                "artifact_root": canonical_hash(
                    projection, prefix="finance_v26_224_artifact_root:"
                ),
            },
            field="manifest_id",
            prefix="finance_v26_224_artifact_manifest:",
        ),
    )
