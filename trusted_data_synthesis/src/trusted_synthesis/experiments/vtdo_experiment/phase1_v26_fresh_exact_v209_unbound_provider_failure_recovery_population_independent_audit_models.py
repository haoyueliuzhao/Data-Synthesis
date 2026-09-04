from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any, Final, Literal, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = (
    "finance_v26_230_fresh_exact_v209_unbound_provider_failure_source_authority_"
    "and_recovery_population_preflight_independent_audit_v1_20260904"
)
OUTPUT_DIR: Final = f"trusted_data_synthesis/artifacts/vtdo_experiment/{RUN_ID}"
SCHEMA_VERSION: Final = (
    "fresh_exact_v209_unbound_provider_failure_recovery_population_independent_audit.v1"
)
CONSUMED_STAGE: Final = (
    "fresh_exact_v209_unbound_provider_failure_source_authority_and_"
    "recovery_population_preflight_independent_audit_only"
)
NEXT_STAGE: Final = (
    "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_"
    "online_execution_authorization_only"
)
DECISION_VALUE: Final = (
    "v26_229_exact_33_unbound_provider_failure_recovery_population_independently_confirmed"
)

EXTERNAL_REVIEW_SHA256: Final = "357326334bbd3af473e0f473503797ccd797fd0c8b92b8d91f7b478f340b002b"
EXTERNAL_REVIEW_BYTE_COUNT: Final = 13_653
OPERATOR_DIRECTIVE: Final = "参照审计继续实验"
OPERATOR_DIRECTIVE_SHA256: Final = (
    "b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb"
)
OPERATOR_DIRECTIVE_BYTE_COUNT: Final = 24

V229_RUN_ID: Final = (
    "finance_v26_229_fresh_exact_v209_unbound_provider_failure_source_authority_"
    "and_recovery_population_preflight_v1_20260904"
)
V229_DIR: Final = f"trusted_data_synthesis/artifacts/vtdo_experiment/{V229_RUN_ID}"
V229_SOURCE_COMMIT: Final = "60b17abebae106477089df365d3ddafb2dac3174"
V229_SOURCE_TREE: Final = "040f3831fcf6bd08a9f7b9385321cfb78808acf2"
V229_FILE_COUNT: Final = 117
V229_TOTAL_BYTES: Final = 1_105_367
V229_MEMBER_COUNT: Final = 116
V229_MEMBER_BYTES: Final = 1_088_415
V229_MANIFEST_BYTE_COUNT: Final = 16_952
V229_MANIFEST_SHA256: Final = "3c74bf72426c33400338e9f234a82bc342f368910a40c84d360ac3bd61b8fa72"
V229_MANIFEST_ID: Final = (
    "finance_v26_229_artifact_manifest:"
    "968a9b5adee2a0c5011c753ec777de8bc91a768745f09943ea676cd2e9e2f863"
)
V229_ARTIFACT_ROOT: Final = (
    "finance_v26_229_artifact_root:0e99bbf37aff7faeb3f5adef51eeccd086d3cc760c09de6ecf236de914b6abe1"
)
V229_REPORT_ID: Final = (
    "finance_v26_229_preflight_report:"
    "bec3dbbf526d38dd566c57cb10c14235d21c21636b4c81fd8f1dd2a088d83ecc"
)
V229_GATE_ID: Final = (
    "finance_v26_229_gate_evaluation:"
    "107717707d461d1d4be979ba7b7f3739d1fde755d854eb51370462fc3cefeb96"
)
V229_DECISION_ID: Final = (
    "finance_v26_229_decision:a81ff8a964d8c58bd7b444c71fc4c910c02938d0f0ce7d07f7c85bc297650e23"
)
V229_TRANSITION_ID: Final = (
    "finance_v26_229_transition:2e2160e5568d140141aad37da5133d8904395de5c4ff284666500cba289eae80"
)
V229_SOURCE_AUTHORITY_ID: Final = (
    "finance_v26_229_v226_source_authority_audit:"
    "66acdec328cb7bab260601eba8f8360707a5b518d442f551cd8afeac813a92d3"
)
V229_JOURNAL_ID: Final = (
    "finance_v26_229_provider_journal_authority:"
    "afd0bc6cb9e1ebdb283ef4e69a92fda307b3806aebe5e8a26f0900c33e086334"
)
V229_REPLAY_ID: Final = (
    "finance_v26_229_request_replay_audit:"
    "5373177519eb09f98fdf5de74e452511dfc6fd8bfaf072ea1afcd09e84029ecf"
)
V229_IDENTIFIABILITY_ID: Final = (
    "finance_v26_229_identifiability_audit:"
    "43fd7b63182487b200fcd7345cd325c14c7f25a75e85cf739c9e9a0dd458a65a"
)
V229_RECOVERY_CONTRACT_ID: Final = (
    "finance_v26_229_recovery_contract:"
    "5313f77c0284420e5ee8a23d34f418a52b517ffb8fcf24d1efb49608dda81202"
)
V229_RECOVERY_POPULATION_ID: Final = (
    "finance_v26_229_recovery_population:"
    "f7b9e21a46abd8efbace595d10ef4d479973eb5631542ee80f5a191e48979821"
)

V226_RUN_ID: Final = (
    "finance_v26_226_fresh_exact_v209_parent_bound_postresponse_serializer_"
    "repair_exact_192_job_replacement_online_execution_v1_20260904"
)
V226_DIR: Final = f"trusted_data_synthesis/artifacts/vtdo_experiment/{V226_RUN_ID}"
V226_MANIFEST_ID: Final = (
    "finance_v26_226_artifact_manifest:"
    "19cef807ae34c71c13d526c09c385163d1b30b2ced05322e3ec7e6f0e803d217"
)
V226_ARTIFACT_ROOT: Final = (
    "finance_v26_226_artifact_root:7ac11713bf70dbd57297b6d87db0e6982ce5ad8222849e3a4826020904f95280"
)
V226_SUMMARY_ID: Final = (
    "finance_v26_226_execution_summary:"
    "459c05325e7d8b1201b4ee9c5cca903876c8bd70f331b97db5d3245b59d82bbd"
)
V226_TRANSITION_ID: Final = (
    "finance_v26_226_transition:e5b3a3b173cf91c5bf6150c3279fa053608c09d2f3d4679084d54cc4f32207b7"
)
V226_PROVIDER_CENSUS_ID: Final = (
    "finance_v26_226_provider_intent_census:"
    "bc758841db428bcd89d8b3f0a91adf83c5716b13d2529c2bafcd1ebfe5e45024"
)
V226_PROVIDER_SOURCE_SET_SHA256: Final = (
    "d9243f618f547da83cae5e6698d3155030b3065058cf5372b8171bf013d3d3f0"
)

HOST_ORDINALS: Final = (6, 22, 149)
PROVIDER_ORDINALS: Final = (
    9,
    10,
    16,
    21,
    32,
    58,
    62,
    63,
    72,
    78,
    79,
    92,
    102,
    103,
    106,
    110,
    112,
    114,
    116,
    121,
    127,
    129,
    130,
    131,
    132,
    135,
    136,
    139,
    144,
    147,
    155,
    171,
    180,
)
NEGATIVE_CONTROL_NAMES: Final = (
    "authorize_online_execution",
    "authorize_provider_call",
    "cross_job_provider_descriptor",
    "duplicate_recovery_job",
    "failed_request_hash_replaced",
    "historical_job_identity_reused",
    "host_failure_substituted",
    "invent_json_response_bytes",
    "provider_call_prefix_truncated",
    "reclassify_json_syntax_as_identifiable",
    "remove_recovery_job",
    "swap_error_or_usage_artifact",
)
GATE_NAMES: Final = (
    "A0_exact_v26_229_freeze",
    "A1_detached_exact_directory_rebuild_and_dependency_closure",
    "A2_independent_v26_226_source_partition",
    "A3_independent_provider_journal_relation_closure",
    "A4_independent_prefix_and_failed_request_reconstruction",
    "A5_independent_identifiability_and_recovery_population_reconstruction",
    "A6_independent_direct_negative_controls",
    "A7_zero_external_execution_scope",
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False), prefix=prefix
    )


def make_identity(
    model_type: type[ModelT], values: Mapping[str, Any], *, field: str, prefix: str
) -> ModelT:
    payload = dict(values)
    payload[field] = "pending"
    provisional = model_type.model_construct(**payload)
    payload[field] = identity(provisional, field, prefix)
    return model_type.model_validate(payload)


def _safe_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(path.parts) and not path.is_absolute() and ".." not in path.parts


class Identified(FrozenModel):
    @classmethod
    def prefix(cls) -> str:
        raise NotImplementedError

    def check_id(self, field: str) -> None:
        if getattr(self, field) != identity(self, field, self.prefix()):
            raise ValueError(f"{field} differs")


class ExternalAuthorization(Identified):
    authorization_id: str
    external_review_sha256: Literal[
        "357326334bbd3af473e0f473503797ccd797fd0c8b92b8d91f7b478f340b002b"
    ] = EXTERNAL_REVIEW_SHA256
    external_review_byte_count: Literal[13653] = EXTERNAL_REVIEW_BYTE_COUNT
    review_result: Literal["PASS_AS_SCOPED"] = "PASS_AS_SCOPED"
    blocking_defect: Literal["NONE_FOUND"] = "NONE_FOUND"
    mandatory_revision: Literal["NONE"] = "NONE"
    operator_directive: Literal["参照审计继续实验"] = OPERATOR_DIRECTIVE
    operator_directive_sha256: Literal[
        "b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb"
    ] = OPERATOR_DIRECTIVE_SHA256
    operator_directive_byte_count: Literal[24] = OPERATOR_DIRECTIVE_BYTE_COUNT
    consumed_stage: Literal[
        "fresh_exact_v209_unbound_provider_failure_source_authority_and_recovery_population_preflight_independent_audit_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized: Literal[False] = False
    credential_lookups_authorized: Literal[False] = False
    recovery_execution_authorized: Literal[False] = False
    online_authorization_created: Literal[False] = False
    schema_version: Literal[
        "fresh_exact_v209_unbound_provider_failure_recovery_population_independent_audit.v1"
    ] = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_230_external_independent_audit_authorization:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if sha(self.operator_directive.encode()) != self.operator_directive_sha256:
            raise ValueError("directive differs")
        self.check_id("authorization_id")
        return self


class SourceMember(FrozenModel):
    relative_path: str
    git_blob_oid: str = Field(pattern=r"^[0-9a-f]{40}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)
    committed_current_bytes_match: Literal[True] = True

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if not _safe_path(self.relative_path):
            raise ValueError("unsafe source member")
        return self


class SourceIdentity(Identified):
    source_identity_id: str
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    implementation_members: tuple[SourceMember, SourceMember]
    member_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    commit_tree_relation: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_230_source_identity:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        paths = tuple(row.relative_path for row in self.implementation_members)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("source members differ")
        self.check_id("source_identity_id")
        return self


class ImplementationBinding(Identified):
    binding_id: str
    source_identity_id: str
    required_independent_symbols: tuple[str, ...]
    candidate_helper_calls: Literal[0] = 0
    candidate_oracle_calls: Literal[0] = 0
    candidate_formal_writes: Literal[0] = 0
    helper_boundary_passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "fresh_v26_230_independent_audit_implementation_binding:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("binding_id")
        return self


class V229FreezeAudit(Identified):
    audit_id: str
    authorization_id: str
    run_id: Literal[
        "finance_v26_229_fresh_exact_v209_unbound_provider_failure_source_authority_and_recovery_population_preflight_v1_20260904"
    ] = V229_RUN_ID
    source_commit: Literal["60b17abebae106477089df365d3ddafb2dac3174"] = V229_SOURCE_COMMIT
    source_tree: Literal["040f3831fcf6bd08a9f7b9385321cfb78808acf2"] = V229_SOURCE_TREE
    file_count: Literal[117] = V229_FILE_COUNT
    total_bytes: Literal[1105367] = V229_TOTAL_BYTES
    manifest_member_count: Literal[116] = V229_MEMBER_COUNT
    manifest_member_bytes: Literal[1088415] = V229_MEMBER_BYTES
    manifest_byte_count: Literal[16952] = V229_MANIFEST_BYTE_COUNT
    manifest_sha256: Literal["3c74bf72426c33400338e9f234a82bc342f368910a40c84d360ac3bd61b8fa72"] = (
        V229_MANIFEST_SHA256
    )
    manifest_id: Literal[
        "finance_v26_229_artifact_manifest:968a9b5adee2a0c5011c753ec777de8bc91a768745f09943ea676cd2e9e2f863"
    ] = V229_MANIFEST_ID
    artifact_root: Literal[
        "finance_v26_229_artifact_root:0e99bbf37aff7faeb3f5adef51eeccd086d3cc760c09de6ecf236de914b6abe1"
    ] = V229_ARTIFACT_ROOT
    report_id: Literal[
        "finance_v26_229_preflight_report:bec3dbbf526d38dd566c57cb10c14235d21c21636b4c81fd8f1dd2a088d83ecc"
    ] = V229_REPORT_ID
    gate_id: Literal[
        "finance_v26_229_gate_evaluation:107717707d461d1d4be979ba7b7f3739d1fde755d854eb51370462fc3cefeb96"
    ] = V229_GATE_ID
    decision_id: Literal[
        "finance_v26_229_decision:a81ff8a964d8c58bd7b444c71fc4c910c02938d0f0ce7d07f7c85bc297650e23"
    ] = V229_DECISION_ID
    transition_id: Literal[
        "finance_v26_229_transition:2e2160e5568d140141aad37da5133d8904395de5c4ff284666500cba289eae80"
    ] = V229_TRANSITION_ID
    path_matches: Literal[117] = 117
    sha256_matches: Literal[116] = 116
    byte_count_matches: Literal[116] = 116
    actual_byte_matches: Literal[117] = 117
    candidate_report_used_as_oracle: Literal[False] = False
    candidate_gate_used_as_oracle: Literal[False] = False
    candidate_source_rows_used_as_selector: Literal[False] = False
    candidate_recovery_population_used_as_selector: Literal[False] = False
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_230_v229_freeze_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("audit_id")
        return self


class DetachedRebuildAudit(Identified):
    audit_id: str
    freeze_audit_id: str
    archived_source_file_count: int = Field(gt=0)
    saved_file_count: Literal[117] = 117
    rebuilt_file_count: Literal[117] = 117
    saved_byte_count: Literal[1105367] = V229_TOTAL_BYTES
    rebuilt_byte_count: Literal[1105367] = V229_TOTAL_BYTES
    path_matches: Literal[117] = 117
    sha256_matches: Literal[117] = 117
    actual_byte_matches: Literal[117] = 117
    manifest_members_revalidated: Literal[116] = 116
    credential_like_environment_keys: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    provider_calls: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_230_detached_rebuild_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("audit_id")
        return self


class DependencyMember(FrozenModel):
    relative_path: str
    v229_blob_oid: str = Field(pattern=r"^[0-9a-f]{40}$")
    current_blob_oid: str = Field(pattern=r"^[0-9a-f]{40}$")
    frozen_parent_commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    frozen_parent_blob_oid: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)
    v229_current_match: Literal[True] = True
    frozen_parent_match: bool


class DependencyClosureAudit(Identified):
    audit_id: str
    source_identity_id: str
    members: tuple[DependencyMember, ...] = Field(min_length=6)
    member_count: int = Field(ge=6)
    v229_current_matches: int = Field(ge=6)
    frozen_parent_matches: int = Field(ge=2)
    v209_replay_blob_matches_frozen_source: Literal[True] = True
    v226_loader_blob_matches_frozen_source: Literal[True] = True
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_230_replay_dependency_closure_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if self.member_count != len(self.members):
            raise ValueError("dependency member count differs")
        self.check_id("audit_id")
        return self


class SourceRow(FrozenModel):
    job_ordinal: int = Field(ge=0, le=191)
    historical_job_id: str
    failure_record_id: str
    failure_kind: Literal["unbound_provider_failure"]
    failure_relative_path: str
    failure_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    failure_file_byte_count: int = Field(gt=0)
    provider_call_count: int = Field(gt=0)
    successful_prefix_call_count: int = Field(ge=0)
    failed_call_ordinal: int = Field(ge=0)
    failed_provider_call_id: str
    failed_descriptor_id: str
    failed_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    failure_class: Literal[
        "reasoning_budget_exhausted_normalized_public_content_empty",
        "json_decode_failure_exact_syntax_unavailable",
    ]
    candidate_source_row_id: str
    candidate_source_row_actual_byte_match: Literal[True] = True


class SourcePartitionAudit(Identified):
    audit_id: str
    freeze_audit_id: str
    v226_manifest_id: Literal[
        "finance_v26_226_artifact_manifest:19cef807ae34c71c13d526c09c385163d1b30b2ced05322e3ec7e6f0e803d217"
    ] = V226_MANIFEST_ID
    v226_artifact_root: Literal[
        "finance_v26_226_artifact_root:7ac11713bf70dbd57297b6d87db0e6982ce5ad8222849e3a4826020904f95280"
    ] = V226_ARTIFACT_ROOT
    v226_summary_id: Literal[
        "finance_v26_226_execution_summary:459c05325e7d8b1201b4ee9c5cca903876c8bd70f331b97db5d3245b59d82bbd"
    ] = V226_SUMMARY_ID
    v226_transition_id: Literal[
        "finance_v26_226_transition:e5b3a3b173cf91c5bf6150c3279fa053608c09d2f3d4679084d54cc4f32207b7"
    ] = V226_TRANSITION_ID
    exact_failure_count: Literal[36] = 36
    host_ordinals: tuple[int, int, int]
    provider_ordinals: tuple[int, ...] = Field(min_length=33, max_length=33)
    rows: tuple[SourceRow, ...] = Field(min_length=33, max_length=33)
    provider_source_projection_sha256: Literal[
        "d9243f618f547da83cae5e6698d3155030b3065058cf5372b8171bf013d3d3f0"
    ] = V226_PROVIDER_SOURCE_SET_SHA256
    candidate_source_row_byte_matches: Literal[33] = 33
    candidate_source_authority_actual_byte_match: Literal[True] = True
    candidate_selector_calls: Literal[0] = 0
    historical_v26_226_writes: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_230_independent_source_partition_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if self.host_ordinals != HOST_ORDINALS or self.provider_ordinals != PROVIDER_ORDINALS:
            raise ValueError("source partition differs")
        if tuple(row.job_ordinal for row in self.rows) != PROVIDER_ORDINALS:
            raise ValueError("source rows differ")
        self.check_id("audit_id")
        return self


class JournalCall(FrozenModel):
    job_ordinal: int = Field(ge=0, le=191)
    call_ordinal: int = Field(ge=0, le=22)
    provider_call_id: str
    descriptor_id: str
    status: Literal["succeeded", "provider_error"]
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_byte_count: int = Field(gt=0)
    certificate_id: str
    pre_transport_receipt_id: str
    response_sha256: str | None = None
    error_sha256: str | None = None
    error_type: str | None = None
    artifact_paths: tuple[str, str, str]
    artifact_sha256s: tuple[str, str, str]
    relation_closed: Literal[True] = True


class JournalAudit(Identified):
    audit_id: str
    source_partition_audit_id: str
    calls: tuple[JournalCall, ...] = Field(min_length=88, max_length=88)
    provider_descriptor_count: Literal[88] = 88
    successful_prefix_call_count: Literal[55] = 55
    failed_call_count: Literal[33] = 33
    request_metadata_count: Literal[88] = 88
    response_metadata_count: Literal[55] = 55
    error_metadata_count: Literal[33] = 33
    usage_metadata_count: Literal[88] = 88
    reasoning_budget_error_count: Literal[31] = 31
    json_decode_error_count: Literal[2] = 2
    relation_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_journal_actual_byte_match: Literal[True] = True
    orphan_descriptors: Literal[0] = 0
    invalid_relations: Literal[0] = 0
    raw_requests: Literal[0] = 0
    raw_provider_responses: Literal[0] = 0
    private_reasoning_bodies: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_230_independent_provider_journal_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if len(self.calls) != 88:
            raise ValueError("Journal call count differs")
        self.check_id("audit_id")
        return self


class ReplayRow(FrozenModel):
    job_ordinal: int = Field(ge=0, le=191)
    source_row_id: str
    invocation_count: int = Field(gt=0)
    successful_prefix_call_count: int = Field(ge=0)
    phases: tuple[str, ...]
    request_sha256s: tuple[str, ...]
    response_sha256s: tuple[str, ...]
    successful_invocation_ids: tuple[str, ...]
    failed_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    failed_request_byte_count: int = Field(gt=0)
    failed_request_certificate_id: str
    failed_pre_transport_receipt_id: str
    request_matches: int = Field(gt=0)
    response_matches: int = Field(ge=0)
    candidate_replay_row_actual_byte_match: Literal[True] = True


class ReplayAudit(Identified):
    audit_id: str
    journal_audit_id: str
    rows: tuple[ReplayRow, ...] = Field(min_length=33, max_length=33)
    exact_job_count: Literal[33] = 33
    reconstructed_call_count: Literal[88] = 88
    successful_prefix_invocation_count: Literal[55] = 55
    captured_failed_request_count: Literal[33] = 33
    exact_request_matches: Literal[88] = 88
    exact_response_matches: Literal[55] = 55
    first_action_failures: Literal[3] = 3
    subsequent_action_failures: Literal[25] = 25
    final_failures: Literal[5] = 5
    correction_failures: Literal[0] = 0
    failed_call_response_supplied: Literal[0] = 0
    failed_call_invocation_records_created: Literal[0] = 0
    historical_terminals_created: Literal[0] = 0
    candidate_replay_audit_actual_byte_match: Literal[True] = True
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_230_independent_request_replay_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if tuple(row.job_ordinal for row in self.rows) != PROVIDER_ORDINALS:
            raise ValueError("replay rows differ")
        self.check_id("audit_id")
        return self


class IdentifiabilityRow(FrozenModel):
    job_ordinal: int = Field(ge=0, le=191)
    source_row_id: str
    candidate_row_id: str
    error_type: Literal["ReasoningBudgetExhaustedError", "JSONDecodeError"]
    failure_class: str
    public_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    public_content_length: int = Field(ge=0)
    finish_reason: Literal["length", "stop"]
    failure_semantics_identifiable: bool
    exact_json_syntax_identifiable: Literal[False] = False
    exact_response_bytes_persisted: Literal[False] = False
    exact_response_bytes_guessed: Literal[False] = False
    candidate_row_actual_byte_match: Literal[True] = True


class IdentifiabilityAudit(Identified):
    audit_id: str
    source_partition_audit_id: str
    rows: tuple[IdentifiabilityRow, ...] = Field(min_length=33, max_length=33)
    exact_source_count: Literal[33] = 33
    reasoning_budget_count: Literal[31] = 31
    json_decode_count: Literal[2] = 2
    failed_requests_reconstructible: Literal[33] = 33
    raw_response_bytes_persisted: Literal[0] = 0
    raw_response_bytes_guessed: Literal[0] = 0
    historical_terminals_created: Literal[0] = 0
    candidate_identifiability_audit_actual_byte_match: Literal[True] = True
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_230_independent_identifiability_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if sum(row.error_type == "ReasoningBudgetExhaustedError" for row in self.rows) != 31:
            raise ValueError("identifiability partition differs")
        self.check_id("audit_id")
        return self


class RecoveryMatchRow(FrozenModel):
    job_ordinal: int = Field(ge=0, le=191)
    source_row_id: str
    candidate_id: str
    recovery_job_id: str
    historical_job_id: str
    failure_record_id: str
    exact_failed_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    successful_prefix_call_count: int = Field(ge=0)
    candidate_actual_byte_match: Literal[True] = True
    recovery_job_actual_byte_match: Literal[True] = True
    historical_identity_overlap: Literal[False] = False


class RecoveryPopulationAudit(Identified):
    audit_id: str
    source_partition_audit_id: str
    replay_audit_id: str
    identifiability_audit_id: str
    rows: tuple[RecoveryMatchRow, ...] = Field(min_length=33, max_length=33)
    reconstructed_candidate_count: Literal[33] = 33
    reconstructed_recovery_job_count: Literal[33] = 33
    candidate_actual_byte_matches: Literal[33] = 33
    recovery_job_actual_byte_matches: Literal[33] = 33
    candidate_contract_actual_byte_match: Literal[True] = True
    candidate_population_actual_byte_match: Literal[True] = True
    candidate_recovery_contract_id: Literal[
        "finance_v26_229_recovery_contract:5313f77c0284420e5ee8a23d34f418a52b517ffb8fcf24d1efb49608dda81202"
    ] = V229_RECOVERY_CONTRACT_ID
    candidate_recovery_population_id: Literal[
        "finance_v26_229_recovery_population:f7b9e21a46abd8efbace595d10ef4d479973eb5631542ee80f5a191e48979821"
    ] = V229_RECOVERY_POPULATION_ID
    reasoning_budget_count: Literal[31] = 31
    json_decode_count: Literal[2] = 2
    historical_identity_overlap_count: Literal[0] = 0
    provider_calls_authorized: Literal[False] = False
    recovery_execution_authorized: Literal[False] = False
    online_authorization_created: Literal[False] = False
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_230_independent_recovery_population_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if tuple(row.job_ordinal for row in self.rows) != PROVIDER_ORDINALS:
            raise ValueError("Recovery rows differ")
        self.check_id("audit_id")
        return self


class AttackResult(FrozenModel):
    attack_name: str
    rejection_stage: str
    reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_identity_recomputed: Literal[True] = True
    rejected: Literal[True] = True
    writes_before_rejection: Literal[0] = 0
    provider_calls_before_rejection: Literal[0] = 0


class NegativeControlAudit(Identified):
    audit_id: str
    source_partition_audit_id: str
    recovery_population_audit_id: str
    results: tuple[AttackResult, ...] = Field(min_length=12, max_length=12)
    attack_count: Literal[12] = 12
    rejection_count: Literal[12] = 12
    accepted_count: Literal[0] = 0
    candidate_negative_audit_used_as_oracle: Literal[False] = False
    candidate_attack_helper_calls: Literal[0] = 0
    attack_output_writes: Literal[0] = 0
    provider_calls: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_230_independent_negative_control_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if tuple(row.attack_name for row in self.results) != NEGATIVE_CONTROL_NAMES:
            raise ValueError("negative control set differs")
        self.check_id("audit_id")
        return self


class ScopeBoundaryAudit(Identified):
    audit_id: str
    credential_lookups: Literal[0] = 0
    model_client_constructions: Literal[0] = 0
    provider_calls: Literal[0] = 0
    recovery_executions: Literal[0] = 0
    failed_job_reruns: Literal[0] = 0
    historical_v26_226_writes: Literal[0] = 0
    historical_outcome_backfills: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    online_authorizations: Literal[0] = 0
    qa_reads: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    training_runs: Literal[0] = 0
    releases: Literal[0] = 0
    production_writes: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_230_scope_boundary_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("audit_id")
        return self


class Gate(FrozenModel):
    name: str
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    passed: Literal[True] = True


class GateEvaluation(Identified):
    evaluation_id: str
    gates: tuple[Gate, ...] = Field(min_length=8, max_length=8)
    passed_count: Literal[8] = 8
    failed_count: Literal[0] = 0
    noncompensatory: Literal[True] = True
    decision: Literal["PASS"] = "PASS"

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_230_gate_evaluation:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if tuple(row.name for row in self.gates) != GATE_NAMES:
            raise ValueError("Gate partition differs")
        self.check_id("evaluation_id")
        return self


class Decision(Identified):
    decision_id: str
    gate_evaluation_id: str
    decision: Literal[
        "v26_229_exact_33_unbound_provider_failure_recovery_population_independently_confirmed"
    ] = DECISION_VALUE
    exact_source_count: Literal[33] = 33
    fresh_recovery_job_count: Literal[33] = 33
    provider_calls: Literal[0] = 0
    recovery_executions: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    online_authorization_issued: Literal[False] = False

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_230_independent_audit_decision:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("decision_id")
        return self


class Transition(Identified):
    transition_id: str
    decision_id: str
    consumed_stage: Literal[
        "fresh_exact_v209_unbound_provider_failure_source_authority_and_recovery_population_preflight_independent_audit_only"
    ] = CONSUMED_STAGE
    prospective_next_stage: Literal[
        "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_authorization_only"
    ] = NEXT_STAGE
    next_stage_authorized: Literal[False] = False
    separate_external_audit_decision_required: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    credential_lookups_authorized: Literal[False] = False
    recovery_execution_authorized: Literal[False] = False
    failed_job_reruns_authorized: Literal[False] = False
    online_authorization_created: Literal[False] = False
    historical_v26_226_mutation_authorized: Literal[False] = False
    empirical_estimation_authorized: Literal[False] = False

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_230_transition:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("transition_id")
        return self


class Report(Identified):
    report_id: str
    run_id: Literal[
        "finance_v26_230_fresh_exact_v209_unbound_provider_failure_source_authority_and_recovery_population_preflight_independent_audit_v1_20260904"
    ] = RUN_ID
    authorization_id: str
    source_identity_id: str
    implementation_binding_id: str
    v229_freeze_audit_id: str
    detached_rebuild_audit_id: str
    dependency_closure_audit_id: str
    source_partition_audit_id: str
    journal_audit_id: str
    replay_audit_id: str
    identifiability_audit_id: str
    recovery_population_audit_id: str
    negative_control_audit_id: str
    scope_boundary_audit_id: str
    gate_evaluation_id: str
    decision_id: str
    transition_id: str
    decision: Literal[
        "v26_229_exact_33_unbound_provider_failure_recovery_population_independently_confirmed"
    ] = DECISION_VALUE
    exact_source_count: Literal[33] = 33
    reconstructed_provider_calls: Literal[88] = 88
    successful_prefix_calls: Literal[55] = 55
    captured_failed_requests: Literal[33] = 33
    reasoning_budget_count: Literal[31] = 31
    json_decode_count: Literal[2] = 2
    fresh_recovery_job_count: Literal[33] = 33
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    recovery_executions: Literal[0] = 0
    historical_mutations: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    online_authorizations: Literal[0] = 0

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_230_independent_audit_report:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("report_id")
        return self


class ArtifactMember(FrozenModel):
    relative_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if not _safe_path(self.relative_path):
            raise ValueError("unsafe artifact path")
        return self


class ArtifactManifest(Identified):
    manifest_id: str
    run_id: Literal[
        "finance_v26_230_fresh_exact_v209_unbound_provider_failure_source_authority_and_recovery_population_preflight_independent_audit_v1_20260904"
    ] = RUN_ID
    members: tuple[ArtifactMember, ...]
    file_count: int = Field(ge=1)
    total_member_bytes: int = Field(gt=0)
    self_excluding: Literal[True] = True
    manifest_relative_path: Literal["artifact_manifest.json"] = "artifact_manifest.json"
    artifact_root: str
    provider_calls: Literal[0] = 0

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_230_artifact_manifest:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        paths = tuple(row.relative_path for row in self.members)
        expected_root = canonical_hash(
            tuple(row.model_dump(mode="json") for row in self.members),
            prefix="finance_v26_230_artifact_root:",
        )
        if (
            paths != tuple(sorted(set(paths)))
            or self.file_count != len(self.members)
            or self.total_member_bytes != sum(row.byte_count for row in self.members)
            or self.artifact_root != expected_root
        ):
            raise ValueError("artifact Manifest differs")
        self.check_id("manifest_id")
        return self


def artifact_manifest(payloads: Mapping[str, bytes]) -> ArtifactManifest:
    members = tuple(
        ArtifactMember(relative_path=path, sha256=sha(payload), byte_count=len(payload))
        for path, payload in sorted(payloads.items())
    )
    root = canonical_hash(
        tuple(row.model_dump(mode="json") for row in members),
        prefix="finance_v26_230_artifact_root:",
    )
    return make_identity(
        ArtifactManifest,
        {
            "members": members,
            "file_count": len(members),
            "total_member_bytes": sum(row.byte_count for row in members),
            "artifact_root": root,
        },
        field="manifest_id",
        prefix=ArtifactManifest.prefix(),
    )
