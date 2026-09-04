# mypy: disable-error-code="valid-type"
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Final, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = (
    "fresh_exact_v209_unbound_provider_failure_recovery_online_execution_"
    "postrun_independent_audit.v1"
)
RUN_ID: Final = (
    "finance_v26_234_fresh_exact_v209_unbound_provider_failure_recovery_population_"
    "bound_online_execution_postrun_independent_audit_v1_20260904"
)
OUTPUT_DIR: Final = f"trusted_data_synthesis/artifacts/vtdo_experiment/{RUN_ID}"
CONSUMED_STAGE: Final = (
    "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_"
    "execution_postrun_independent_audit_only"
)
NEXT_DECISION: Final = "no_further_experiment_authorized_without_new_audit_decision"

EXTERNAL_REVIEW_SHA256: Final = "f9331fb9310c5b29f5af5df488c10d682b8f6725c29b035eb01d744c0e08c9c0"
EXTERNAL_REVIEW_BYTE_COUNT: Final = 17_401
OPERATOR_DIRECTIVE: Final = "参照审计报告开展后续实验修订"
OPERATOR_DIRECTIVE_SHA256: Final = (
    "e3adc8d65f07c54893d36828d8c12bdca9e83ab8a07fb94e40a259a2a18bcf73"
)
OPERATOR_DIRECTIVE_BYTE_COUNT: Final = 42

V233_SOURCE_COMMIT: Final = "0c10e93a10ba85f89725be565137d8cc890d1ce4"
V233_SOURCE_TREE: Final = "379083e1c04f1617a91b71828083a14ad346594e"
V233_FILE_COUNT: Final = 381
V233_TOTAL_BYTES: Final = 12_265_007
V233_MANIFEST_MEMBER_COUNT: Final = 380
V233_MANIFEST_MEMBER_BYTES: Final = 12_184_524
V233_MANIFEST_BYTE_COUNT: Final = 80_483
V233_MANIFEST_SHA256: Final = "1044931f77953b584c4efd857629c9030d35e390b60219d0f382a9b65f5fde5d"
V233_MANIFEST_ID: Final = (
    "finance_v26_224_artifact_manifest:"
    "06d5c3d26a99e6b614c71a5791249f1ede5852244e0d66df71117609bdc9f626"
)
V233_ARTIFACT_ROOT: Final = (
    "finance_v26_224_artifact_root:652730c3c535232fa99c310ca5fac3322a65778dd376751eac49107e5d5cb60b"
)
V233_SUMMARY_ID: Final = (
    "finance_v26_233_execution_summary:"
    "af4e4ceaa286a2cd93b1dcb5433104b70509918205ffb2cf457fe8745ad6b233"
)
V233_TRANSITION_ID: Final = (
    "finance_v26_233_transition:475f270536c7448f8d687ce982cb55534a4862e783f63d543a2bd9a5ae04640f"
)

TERMINAL_ORDINALS: Final = (
    16,
    21,
    62,
    78,
    103,
    106,
    116,
    121,
    127,
    130,
    131,
    132,
    136,
    139,
    147,
    155,
)
FAILURE_ORDINALS: Final = (
    9,
    10,
    32,
    58,
    63,
    72,
    79,
    92,
    102,
    110,
    112,
    114,
    129,
    135,
    144,
    171,
    180,
)
ALL_ORDINALS: Final = tuple(sorted((*TERMINAL_ORDINALS, *FAILURE_ORDINALS)))

ModelT = TypeVar("ModelT", bound=BaseModel)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False), prefix=prefix
    )


def make_identity(
    model_type: type[ModelT], values: Mapping[str, Any], *, field: str, prefix: str
) -> ModelT:
    payload = dict(values)
    provisional = model_type.model_construct(**{field: "pending"}, **payload)
    payload[field] = identity(provisional, field, prefix)
    return model_type.model_validate(payload)


class Identified(FrozenModel):
    @classmethod
    def prefix(cls) -> str:
        raise NotImplementedError

    def check_id(self, field: str) -> None:
        if getattr(self, field) != identity(self, field, self.prefix()):
            raise ValueError(f"{type(self).__name__} identity differs")


class ExternalAuthorization(Identified):
    authorization_id: str
    external_review_sha256: Literal[EXTERNAL_REVIEW_SHA256] = EXTERNAL_REVIEW_SHA256
    external_review_byte_count: Literal[17401] = EXTERNAL_REVIEW_BYTE_COUNT
    audit_decision: Literal["PASS_AS_SCOPED"] = "PASS_AS_SCOPED"
    blocking_defect: Literal["NONE_FOUND"] = "NONE_FOUND"
    mandatory_revision: Literal["NONE"] = "NONE"
    current_gate: Literal["PASS_FOR_POSTRUN_AUDIT_ADMISSION"] = "PASS_FOR_POSTRUN_AUDIT_ADMISSION"
    scientific_denominator_status: Literal["INCOMPLETE"] = "INCOMPLETE"
    next_unclosed_gate: Literal["POSTRUN_INDEPENDENT_AUDIT"] = "POSTRUN_INDEPENDENT_AUDIT"
    operator_directive: Literal[OPERATOR_DIRECTIVE] = OPERATOR_DIRECTIVE
    operator_directive_sha256: Literal[OPERATOR_DIRECTIVE_SHA256] = OPERATOR_DIRECTIVE_SHA256
    operator_directive_byte_count: Literal[42] = OPERATOR_DIRECTIVE_BYTE_COUNT
    authorized_stage: Literal[CONSUMED_STAGE] = CONSUMED_STAGE
    provider_calls_authorized: Literal[False] = False
    retries_or_backfills_authorized: Literal[False] = False
    empirical_estimation_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_external_independent_audit_authorization:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        directive = self.operator_directive.encode()
        if (
            len(directive) != self.operator_directive_byte_count
            or hashlib.sha256(directive).hexdigest() != self.operator_directive_sha256
        ):
            raise ValueError("operator directive bytes differ")
        self.check_id("authorization_id")
        return self


class SourceMember(FrozenModel):
    relative_path: str
    git_blob_oid: str = Field(pattern=r"^[0-9a-f]{40}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)
    committed_current_bytes_match: Literal[True] = True


class SourceAuthorityAudit(Identified):
    audit_id: str
    authorization_id: str
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    implementation_members: tuple[SourceMember, SourceMember]
    implementation_member_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    v233_source_commit: Literal[V233_SOURCE_COMMIT] = V233_SOURCE_COMMIT
    v233_source_tree: Literal[V233_SOURCE_TREE] = V233_SOURCE_TREE
    v233_source_members: tuple[SourceMember, SourceMember]
    v233_saved_source_identity_match: Literal[True] = True
    commit_tree_relations_verified: Literal[2] = 2
    committed_current_member_matches: Literal[4] = 4
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_source_authority_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        for members in (self.implementation_members, self.v233_source_members):
            paths = tuple(row.relative_path for row in members)
            if paths != tuple(sorted(set(paths))):
                raise ValueError("source member path set differs")
        if (
            canonical_sha256(
                tuple(row.model_dump(mode="json") for row in self.implementation_members)
            )
            != self.implementation_member_set_sha256
        ):
            raise ValueError("implementation source member set differs")
        self.check_id("audit_id")
        return self


class V233ExecutionFreezeAudit(Identified):
    audit_id: str
    source_authority_audit_id: str
    manifest_id: Literal[V233_MANIFEST_ID] = V233_MANIFEST_ID
    artifact_root: Literal[V233_ARTIFACT_ROOT] = V233_ARTIFACT_ROOT
    manifest_file_sha256: Literal[V233_MANIFEST_SHA256] = V233_MANIFEST_SHA256
    manifest_file_byte_count: Literal[80483] = V233_MANIFEST_BYTE_COUNT
    file_count: Literal[381] = V233_FILE_COUNT
    total_byte_count: Literal[12265007] = V233_TOTAL_BYTES
    manifest_member_count: Literal[380] = V233_MANIFEST_MEMBER_COUNT
    manifest_member_byte_count: Literal[12184524] = V233_MANIFEST_MEMBER_BYTES
    manifest_path_matches: Literal[380] = 380
    manifest_sha256_matches: Literal[380] = 380
    manifest_byte_count_matches: Literal[380] = 380
    manifest_actual_byte_matches: Literal[380] = 380
    summary_id: Literal[V233_SUMMARY_ID] = V233_SUMMARY_ID
    transition_id: Literal[V233_TRANSITION_ID] = V233_TRANSITION_ID
    authorization_consumption_count: Literal[1] = 1
    run_start_receipt_count: Literal[1] = 1
    summary_used_as_outcome_oracle: Literal[False] = False
    transition_used_as_outcome_oracle: Literal[False] = False
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_v233_execution_freeze_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("audit_id")
        return self


class RecoveryAuthorityRow(Identified):
    row_id: str
    job_ordinal: int = Field(ge=0, le=191)
    historical_job_id: str
    recovery_candidate_id: str
    recovery_job_id: str
    source_row_id: str
    failed_request_phase: Literal["first_action", "subsequent_action", "final"]
    successful_prefix_projection_count: int = Field(ge=0, le=22)
    historical_prefix_descriptor_count: int = Field(ge=0, le=22)
    captured_failed_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    captured_failed_request_byte_count: int = Field(gt=0)
    first_fresh_provider_call_id: str
    first_fresh_request_match: Literal[True] = True
    first_fresh_certificate_match: Literal[True] = True
    first_fresh_receipt_match: Literal[True] = True
    historical_prefix_actual_byte_matches: int = Field(ge=0, le=22)
    source_row_actual_byte_match: Literal[True] = True
    recovery_candidate_actual_byte_match: Literal[True] = True
    recovery_job_actual_byte_match: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_recovery_authority_row:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            self.successful_prefix_projection_count != self.historical_prefix_descriptor_count
            or self.successful_prefix_projection_count != self.historical_prefix_actual_byte_matches
        ):
            raise ValueError("historical prefix geometry differs")
        self.check_id("row_id")
        return self


class RecoveryAuthorityAudit(Identified):
    audit_id: str
    v233_freeze_audit_id: str
    rows: tuple[RecoveryAuthorityRow, ...] = Field(min_length=33, max_length=33)
    exact_source_row_count: Literal[33] = 33
    exact_recovery_job_count: Literal[33] = 33
    local_prefix_projection_count: Literal[55] = 55
    historical_prefix_provider_reissue_count: Literal[0] = 0
    captured_failed_request_handoff_count: Literal[33] = 33
    exact_first_fresh_request_matches: Literal[33] = 33
    exact_source_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_calls: Literal[0] = 0
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_recovery_authority_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        ordinals = tuple(row.job_ordinal for row in self.rows)
        if (
            ordinals != ALL_ORDINALS
            or sum(row.successful_prefix_projection_count for row in self.rows) != 55
            or canonical_sha256(tuple(row.source_row_id for row in self.rows))
            != self.exact_source_set_sha256
        ):
            raise ValueError("Recovery authority population differs")
        self.check_id("audit_id")
        return self


class ProviderCallAuditRow(Identified):
    row_id: str
    job_ordinal: int = Field(ge=0, le=191)
    recovery_job_id: str
    provider_call_id: str
    descriptor_id: str
    call_ordinal: int = Field(ge=0, le=22)
    status: Literal["succeeded", "provider_error", "transport_error"]
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    error_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    error_type: str | None
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    artifact_count: Literal[3] = 3
    descriptor_actual_byte_match: Literal[True] = True
    artifact_actual_byte_matches: Literal[3] = 3
    request_metadata_match: Literal[True] = True
    response_or_error_metadata_match: Literal[True] = True
    usage_metadata_match: Literal[True] = True
    first_fresh_captured_request_handoff: bool
    retry_authorized: Literal[False] = False
    raw_request_present: Literal[False] = False
    raw_response_present: Literal[False] = False
    private_reasoning_present: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_provider_call_audit_row:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (self.status == "succeeded") != (
            self.response_sha256 is not None
            and self.error_sha256 is None
            and self.error_type is None
        ):
            raise ValueError("Provider call status shape differs")
        if (self.status != "succeeded") != (
            self.response_sha256 is None
            and self.error_sha256 is not None
            and self.error_type is not None
        ):
            raise ValueError("Provider failure status shape differs")
        self.check_id("row_id")
        return self


class ProviderJournalAudit(Identified):
    audit_id: str
    recovery_authority_audit_id: str
    rows: tuple[ProviderCallAuditRow, ...] = Field(min_length=64, max_length=64)
    provider_descriptor_count: Literal[64] = 64
    provider_artifact_count: Literal[192] = 192
    succeeded_count: Literal[47] = 47
    provider_error_count: Literal[17] = 17
    transport_error_count: Literal[0] = 0
    reasoning_budget_error_count: Literal[16] = 16
    json_decode_error_count: Literal[1] = 1
    first_fresh_handoff_count: Literal[33] = 33
    input_tokens: Literal[464481] = 464_481
    output_tokens: Literal[637076] = 637_076
    per_job_call_count_distribution: dict[int, int]
    orphan_descriptor_count: Literal[0] = 0
    orphan_artifact_count: Literal[0] = 0
    provider_calls_during_audit: Literal[0] = 0
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_independent_provider_journal_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            len({row.provider_call_id for row in self.rows}) != 64
            or sum(row.status == "succeeded" for row in self.rows) != 47
            or sum(row.status == "provider_error" for row in self.rows) != 17
            or sum(row.first_fresh_captured_request_handoff for row in self.rows) != 33
            or sum(row.input_tokens for row in self.rows) != self.input_tokens
            or sum(row.output_tokens for row in self.rows) != self.output_tokens
            or self.per_job_call_count_distribution != {1: 14, 2: 10, 3: 6, 4: 3}
        ):
            raise ValueError("Provider journal partition differs")
        self.check_id("audit_id")
        return self


class TerminalReconstructionRow(Identified):
    row_id: str
    job_ordinal: int = Field(ge=0, le=191)
    recovery_job_id: str
    historical_job_id: str
    evidence_kind: Literal["completed_runner", "final_parser_rejection"]
    evidence_id: str
    decision_id: str
    terminal_kind: Literal["completed_qualified", "completed_invalid", "final_response_abi_invalid"]
    terminal_policy_id: str
    derivation_rule: Literal[
        "final_base_and_mechanism_conjunction", "final_parser_validation_rejection"
    ]
    invocation_record_count: int = Field(ge=2, le=23)
    successful_prefix_projection_count: int = Field(ge=0, le=22)
    fresh_provider_call_count: int = Field(ge=1, le=23)
    invocation_public_projection_matches: int = Field(ge=2, le=23)
    evidence_actual_byte_match: Literal[True] = True
    decision_actual_byte_match: Literal[True] = True
    record_actual_byte_match: Literal[True] = True
    layer_descriptor_ids: tuple[str, str, str, str, str]
    layer_actual_byte_matches: Literal[5] = 5
    layer_parent_matches: Literal[5] = 5
    layer_namespace_matches: Literal[5] = 5
    raw_before_result: Literal[True] = True
    formal_empirical_row: Literal[False] = False
    historical_job_reclassified: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_terminal_reconstruction_row:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            self.invocation_record_count
            != self.successful_prefix_projection_count + self.fresh_provider_call_count
            or self.invocation_public_projection_matches != self.invocation_record_count
            or len(set(self.layer_descriptor_ids)) != 5
        ):
            raise ValueError("terminal reconstruction geometry differs")
        self.check_id("row_id")
        return self


class TerminalReconstructionAudit(Identified):
    audit_id: str
    provider_journal_audit_id: str
    rows: tuple[TerminalReconstructionRow, ...] = Field(min_length=16, max_length=16)
    terminal_record_count: Literal[16] = 16
    completed_qualified_count: Literal[8] = 8
    completed_invalid_count: Literal[1] = 1
    final_response_abi_invalid_count: Literal[7] = 7
    independently_derived_terminal_matches: Literal[16] = 16
    independently_derived_decision_byte_matches: Literal[16] = 16
    five_layer_file_count: Literal[80] = 80
    layer_actual_byte_matches: Literal[80] = 80
    layer_parent_matches: Literal[80] = 80
    layer_namespace_matches: Literal[80] = 80
    empirical_rows_created: Literal[0] = 0
    provider_calls: Literal[0] = 0
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_independent_terminal_reconstruction_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            tuple(row.job_ordinal for row in self.rows) != TERMINAL_ORDINALS
            or sum(row.terminal_kind == "completed_qualified" for row in self.rows) != 8
            or sum(row.terminal_kind == "completed_invalid" for row in self.rows) != 1
            or sum(row.terminal_kind == "final_response_abi_invalid" for row in self.rows) != 7
        ):
            raise ValueError("terminal reconstruction partition differs")
        self.check_id("audit_id")
        return self


class FailureReconstructionRow(Identified):
    row_id: str
    job_ordinal: int = Field(ge=0, le=191)
    recovery_job_id: str
    historical_job_id: str
    failed_request_phase: Literal["first_action", "subsequent_action", "final"]
    fresh_provider_call_count: int = Field(ge=1, le=23)
    final_call_ordinal: int = Field(ge=0, le=22)
    final_provider_call_id: str
    final_error_type: Literal["ReasoningBudgetExhaustedError", "JSONDecodeError"]
    final_error_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    completion_tokens: int = Field(ge=0)
    reasoning_tokens: int = Field(ge=0)
    response_model: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    prior_fresh_calls_succeeded: Literal[True] = True
    final_fresh_call_failed: Literal[True] = True
    no_later_provider_call: Literal[True] = True
    record_actual_byte_match: Literal[True] = True
    terminal_evidence_admitted: Literal[False] = False
    five_layer_evidence_admitted: Literal[False] = False
    historical_job_reclassified: Literal[False] = False
    empirical_estimate_admitted: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_failure_reconstruction_row:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if self.final_call_ordinal != self.fresh_provider_call_count - 1:
            raise ValueError("failure terminal call ordinal differs")
        self.check_id("row_id")
        return self


class FailureReconstructionAudit(Identified):
    audit_id: str
    provider_journal_audit_id: str
    rows: tuple[FailureReconstructionRow, ...] = Field(min_length=17, max_length=17)
    failure_record_count: Literal[17] = 17
    unbound_provider_failure_count: Literal[17] = 17
    host_failure_count: Literal[0] = 0
    reasoning_budget_error_count: Literal[16] = 16
    json_decode_error_count: Literal[1] = 1
    final_call_failure_matches: Literal[17] = 17
    no_later_call_matches: Literal[17] = 17
    terminal_evidence_admitted_count: Literal[0] = 0
    five_layer_evidence_admitted_count: Literal[0] = 0
    empirical_estimate_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_independent_failure_reconstruction_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            tuple(row.job_ordinal for row in self.rows) != FAILURE_ORDINALS
            or sum(row.final_error_type == "ReasoningBudgetExhaustedError" for row in self.rows)
            != 16
            or sum(row.final_error_type == "JSONDecodeError" for row in self.rows) != 1
        ):
            raise ValueError("failure reconstruction partition differs")
        self.check_id("audit_id")
        return self


class ExactPartitionAudit(Identified):
    audit_id: str
    recovery_authority_audit_id: str
    terminal_audit_id: str
    failure_audit_id: str
    exact_job_ordinals: tuple[int, ...]
    terminal_ordinals: tuple[int, ...]
    failure_ordinals: tuple[int, ...]
    exact_job_count: Literal[33] = 33
    attempted_job_count: Literal[33] = 33
    terminal_record_count: Literal[16] = 16
    failure_record_count: Literal[17] = 17
    terminal_partition: dict[str, int]
    failure_partition: dict[str, int]
    failed_request_phase_partition: dict[str, int]
    provider_call_count: Literal[64] = 64
    input_tokens: Literal[464481] = 464_481
    output_tokens: Literal[637076] = 637_076
    execution_status: Literal["incomplete"] = "incomplete"
    scientific_denominator_complete: Literal[False] = False
    execution_summary_actual_byte_match: Literal[True] = True
    transition_actual_byte_match: Literal[True] = True
    execution_summary_used_as_outcome_oracle: Literal[False] = False
    empirical_estimate_count: Literal[0] = 0
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_exact_recovery_partition_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            self.exact_job_ordinals != ALL_ORDINALS
            or self.terminal_ordinals != TERMINAL_ORDINALS
            or self.failure_ordinals != FAILURE_ORDINALS
            or self.terminal_partition
            != {
                "completed_invalid": 1,
                "completed_qualified": 8,
                "correction_action_reference_invalid": 0,
                "correction_attempt_typed_invalid": 0,
                "correction_response_abi_invalid": 0,
                "final_response_abi_invalid": 7,
                "first_action_reference_invalid": 0,
                "first_response_abi_invalid": 0,
                "instrument_failure": 0,
                "privacy_rejection": 0,
            }
            or self.failure_partition != {"host_failure": 0, "unbound_provider_failure": 17}
            or self.failed_request_phase_partition
            != {"final": 5, "first_action": 3, "subsequent_action": 25}
        ):
            raise ValueError("exact Recovery partition differs")
        self.check_id("audit_id")
        return self


class ScopeBoundaryAudit(Identified):
    audit_id: str
    exact_partition_audit_id: str
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    client_constructions: Literal[0] = 0
    recovery_job_retries: Literal[0] = 0
    historical_prefix_provider_reissues: Literal[0] = 0
    historical_v26_226_writes: Literal[0] = 0
    historical_terminal_backfills: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    new_online_authorizations: Literal[0] = 0
    qa_mapper_state_frequency_contribution_vtdo_rows: Literal[0] = 0
    execution_summary_oracle_calls: Literal[0] = 0
    v233_execution_helper_calls: Literal[0] = 0
    network_or_credential_symbols: Literal[0] = 0
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_scope_boundary_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("audit_id")
        return self


class GateRow(FrozenModel):
    gate: Literal["A0", "A1", "A2", "A3", "A4", "A5", "A6"]
    description: str
    passed: Literal[True] = True


class GateEvaluation(Identified):
    gate_id: str
    rows: tuple[GateRow, GateRow, GateRow, GateRow, GateRow, GateRow, GateRow]
    passed_count: Literal[7] = 7
    failed_count: Literal[0] = 0
    noncompensatory: Literal[True] = True
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_gate_evaluation:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if tuple(row.gate for row in self.rows) != (
            "A0",
            "A1",
            "A2",
            "A3",
            "A4",
            "A5",
            "A6",
        ):
            raise ValueError("audit Gate partition differs")
        self.check_id("gate_id")
        return self


class IndependentAuditDecision(Identified):
    decision_id: str
    gate_id: str
    decision: Literal[
        "v26_233_exact_33_job_recovery_attempt_execution_independently_confirmed_"
        "terminal_evidence_set_incomplete"
    ]
    attempted_recovery_population_closed: Literal[True] = True
    terminal_evidence_set_complete: Literal[False] = False
    terminal_record_count: Literal[16] = 16
    failure_record_count: Literal[17] = 17
    scientific_denominator_complete: Literal[False] = False
    empirical_estimate_materialized: Literal[False] = False
    provider_failure_terminalized: Literal[False] = False
    retry_backfill_or_historical_mutation_performed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_postrun_independent_audit_decision:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("decision_id")
        return self


class Transition(Identified):
    transition_id: str
    decision_id: str
    next_decision: Literal[NEXT_DECISION] = NEXT_DECISION
    next_stage_authorized: Literal[False] = False
    provider_execution_authorized: Literal[False] = False
    recovery_retry_authorized: Literal[False] = False
    historical_backfill_authorized: Literal[False] = False
    empirical_estimation_authorized: Literal[False] = False
    qa_mapper_state_frequency_contribution_vtdo_authorized: Literal[False] = False
    training_release_production_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_transition:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("transition_id")
        return self


class Report(Identified):
    report_id: str
    authorization_id: str
    source_authority_audit_id: str
    v233_freeze_audit_id: str
    recovery_authority_audit_id: str
    provider_journal_audit_id: str
    terminal_reconstruction_audit_id: str
    failure_reconstruction_audit_id: str
    exact_partition_audit_id: str
    scope_audit_id: str
    gate_id: str
    decision_id: str
    transition_id: str
    audit_result: Literal["PASSED_AS_SCOPED"] = "PASSED_AS_SCOPED"
    attempted_jobs: Literal[33] = 33
    local_prefix_projections: Literal[55] = 55
    captured_failed_request_handoffs: Literal[33] = 33
    fresh_provider_descriptors: Literal[64] = 64
    terminal_records: Literal[16] = 16
    five_layer_files: Literal[80] = 80
    failure_records: Literal[17] = 17
    scientific_denominator_status: Literal["INCOMPLETE"] = "INCOMPLETE"
    empirical_estimate: Literal["NOT_MATERIALIZED"] = "NOT_MATERIALIZED"
    provider_calls_during_audit: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_postrun_independent_audit_report:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("report_id")
        return self


class ArtifactMember(FrozenModel):
    relative_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class ArtifactManifest(Identified):
    manifest_id: str
    run_id: Literal[RUN_ID] = RUN_ID
    members: tuple[ArtifactMember, ...] = Field(min_length=1)
    file_count: int = Field(gt=0)
    total_byte_count: int = Field(gt=0)
    artifact_root: str
    self_excluding: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_234_artifact_manifest:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        paths = tuple(row.relative_path for row in self.members)
        projection = tuple(row.model_dump(mode="json") for row in self.members)
        if (
            paths != tuple(sorted(set(paths)))
            or self.file_count != len(self.members)
            or self.total_byte_count != sum(row.byte_count for row in self.members)
            or self.artifact_root
            != canonical_hash(projection, prefix="finance_v26_234_artifact_root:")
        ):
            raise ValueError("v26.234 Artifact Manifest differs")
        self.check_id("manifest_id")
        return self


def artifact_manifest(payloads: Mapping[str, bytes]) -> ArtifactManifest:
    members = tuple(
        ArtifactMember(
            relative_path=name,
            sha256=hashlib.sha256(payload).hexdigest(),
            byte_count=len(payload),
        )
        for name, payload in sorted(payloads.items())
    )
    projection = tuple(row.model_dump(mode="json") for row in members)
    return make_identity(
        ArtifactManifest,
        {
            "members": members,
            "file_count": len(members),
            "total_byte_count": sum(row.byte_count for row in members),
            "artifact_root": canonical_hash(projection, prefix="finance_v26_234_artifact_root:"),
        },
        field="manifest_id",
        prefix=ArtifactManifest.prefix(),
    )
