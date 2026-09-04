from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any, Final, Literal, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = (
    "finance_v26_229_fresh_exact_v209_unbound_provider_failure_source_authority_"
    "and_recovery_population_preflight_v1_20260904"
)
OUTPUT_DIR: Final = f"trusted_data_synthesis/artifacts/vtdo_experiment/{RUN_ID}"
CONSUMED_STAGE: Final = (
    "fresh_exact_v209_unbound_provider_failure_source_authority_and_"
    "recovery_population_preflight_only"
)
NEXT_STAGE: Final = (
    "fresh_exact_v209_unbound_provider_failure_source_authority_and_"
    "recovery_population_preflight_independent_audit_only"
)

EXTERNAL_REVIEW_SHA256: Final = "0b63d855ddd8e8707f3c0bdc2ddd4231b6a16fdaa986f7acb8e092f1491b58c2"
EXTERNAL_REVIEW_BYTE_COUNT: Final = 10_739
EXTERNAL_REVIEW_RESULT: Final = "PASS_AS_SCOPED"
OPERATOR_DIRECTIVE: Final = "参照审计继续实验"
OPERATOR_DIRECTIVE_SHA256: Final = (
    "b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb"
)
OPERATOR_DIRECTIVE_BYTE_COUNT: Final = 24

V228_RUN_ID: Final = (
    "finance_v26_228_fresh_exact_v209_subsequent_action_evidence_domain_"
    "closure_independent_audit_v1_20260904"
)
V228_DIR: Final = f"trusted_data_synthesis/artifacts/vtdo_experiment/{V228_RUN_ID}"
V228_SOURCE_COMMIT: Final = "e73ced617283eb69ea0c2a768368554959a5abc3"
V228_SOURCE_TREE: Final = "a0bba2a647f60cb0bfbcbcc4c28a25150a80863b"
V228_REPORT_ID: Final = (
    "finance_v26_228_independent_audit_report:"
    "73726cf06630fe0686d6bda8425bc354500c96fff464407fc06786798e541e59"
)
V228_DECISION_ID: Final = (
    "finance_v26_228_independent_audit_decision:"
    "f6062949296f88a31e0de1af3ab59e5cfc933576750b7bcce709e5eb8594e540"
)
V228_TRANSITION_ID: Final = (
    "finance_v26_228_transition:d84987584d8d07fd67554bf053e807305a987ac75285017722c207a66bd9d802"
)
V228_MANIFEST_ID: Final = (
    "finance_v26_228_artifact_manifest:"
    "7514b10d627fb19d3d42f1ad8f5e74e12bf0a152265d42742ab2b1b4e1391eaa"
)
V228_ARTIFACT_ROOT: Final = (
    "finance_v26_228_artifact_root:92ed34f45846d1ba8e93cf5dd2e9d972f3f97bdbc69eb110135d8976e1d68aaf"
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
V226_JOB_FAILURE_SHA256: Final = "bf06dd05d7431b80d5a218229dd0c1b6251b7e801ba4ade9e745d4a61ae3ca2f"
V228_PROVIDER_EXCLUSION_SET_SHA256: Final = (
    "d9243f618f547da83cae5e6698d3155030b3065058cf5372b8171bf013d3d3f0"
)

EXACT_SOURCE_COUNT: Final = 33
IDENTIFIABLE_REASONING_BUDGET_COUNT: Final = 31
UNIDENTIFIABLE_JSON_SYNTAX_COUNT: Final = 2
HOST_EXCLUSION_COUNT: Final = 3

FailureClass = Literal[
    "reasoning_budget_exhausted_normalized_public_content_empty",
    "json_decode_failure_exact_syntax_unavailable",
]
ProviderCallStatus = Literal["succeeded", "provider_error", "transport_error"]
ArtifactKind = Literal["request_metadata", "response_metadata", "usage_metadata", "error_metadata"]

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
    "A0_exact_v26_228_freeze",
    "A1_exact_v26_226_source_authority",
    "A2_provider_journal_relation_closure",
    "A3_exact_prefix_and_failed_request_reconstruction",
    "A4_identifiability_and_fresh_recovery_population",
    "A5_direct_negative_controls_and_zero_scope",
)
DECISION_VALUE: Final = (
    "v26_226_exact_33_unbound_provider_failure_source_authority_and_fresh_"
    "recovery_population_preflight_passed"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Identified(FrozenModel):
    @classmethod
    def prefix(cls) -> str:
        raise NotImplementedError

    def check_id(self, field: str) -> None:
        if getattr(self, field) != identity(self, field, self.prefix()):
            raise ValueError(f"{field} differs")


ModelT = TypeVar("ModelT", bound=BaseModel)


def canonical_bytes(value: Any) -> bytes:
    payload = (
        value.model_dump(mode="json", warnings=False) if isinstance(value, BaseModel) else value
    )
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha(canonical_bytes(value))


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


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


def _safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(path.parts) and not path.is_absolute() and ".." not in path.parts


class ExternalAuthorization(Identified):
    authorization_id: str
    review_sha256: Literal["0b63d855ddd8e8707f3c0bdc2ddd4231b6a16fdaa986f7acb8e092f1491b58c2"] = (
        EXTERNAL_REVIEW_SHA256
    )
    review_byte_count: Literal[10739] = EXTERNAL_REVIEW_BYTE_COUNT
    review_result: Literal["PASS_AS_SCOPED"] = EXTERNAL_REVIEW_RESULT
    blocking_defect: Literal["NONE_FOUND"] = "NONE_FOUND"
    mandatory_revision: Literal["NONE"] = "NONE"
    operator_directive: Literal["参照审计继续实验"] = OPERATOR_DIRECTIVE
    operator_directive_sha256: Literal[
        "b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb"
    ] = OPERATOR_DIRECTIVE_SHA256
    operator_directive_byte_count: Literal[24] = OPERATOR_DIRECTIVE_BYTE_COUNT
    consumed_stage: Literal[
        "fresh_exact_v209_unbound_provider_failure_source_authority_and_recovery_population_preflight_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized: Literal[False] = False
    credential_lookups_authorized: Literal[False] = False
    recovery_execution_authorized: Literal[False] = False
    failed_job_reruns_authorized: Literal[False] = False
    online_authorization_created: Literal[False] = False
    schema_version: Literal["finance_v26_229_external_authorization.v1"] = (
        "finance_v26_229_external_authorization.v1"
    )

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_external_authorization:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("authorization_id")
        return self


class SourceIdentity(Identified):
    source_identity_id: str
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    model_relative_path: str
    model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_byte_count: int = Field(gt=0)
    preflight_relative_path: str
    preflight_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_byte_count: int = Field(gt=0)
    ordered_member_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    working_tree_bytes_match_source: Literal[True] = True
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_source_identity:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if not _safe_relative_path(self.model_relative_path) or not _safe_relative_path(
            self.preflight_relative_path
        ):
            raise ValueError("source path differs")
        self.check_id("source_identity_id")
        return self


class V228Freeze(Identified):
    freeze_id: str
    authorization_id: str
    v228_run_id: Literal[
        "finance_v26_228_fresh_exact_v209_subsequent_action_evidence_domain_closure_independent_audit_v1_20260904"
    ] = V228_RUN_ID
    v228_source_commit: Literal["e73ced617283eb69ea0c2a768368554959a5abc3"] = V228_SOURCE_COMMIT
    v228_source_tree: Literal["a0bba2a647f60cb0bfbcbcc4c28a25150a80863b"] = V228_SOURCE_TREE
    v228_report_id: Literal[
        "finance_v26_228_independent_audit_report:73726cf06630fe0686d6bda8425bc354500c96fff464407fc06786798e541e59"
    ] = V228_REPORT_ID
    v228_decision_id: Literal[
        "finance_v26_228_independent_audit_decision:f6062949296f88a31e0de1af3ab59e5cfc933576750b7bcce709e5eb8594e540"
    ] = V228_DECISION_ID
    v228_transition_id: Literal[
        "finance_v26_228_transition:d84987584d8d07fd67554bf053e807305a987ac75285017722c207a66bd9d802"
    ] = V228_TRANSITION_ID
    v228_manifest_id: Literal[
        "finance_v26_228_artifact_manifest:7514b10d627fb19d3d42f1ad8f5e74e12bf0a152265d42742ab2b1b4e1391eaa"
    ] = V228_MANIFEST_ID
    v228_artifact_root: Literal[
        "finance_v26_228_artifact_root:92ed34f45846d1ba8e93cf5dd2e9d972f3f97bdbc69eb110135d8976e1d68aaf"
    ] = V228_ARTIFACT_ROOT
    saved_file_count: Literal[17] = 17
    saved_byte_count: Literal[45679] = 45_679
    manifest_member_count: Literal[16] = 16
    manifest_member_bytes: Literal[42978] = 42_978
    path_hash_byte_match_count: Literal[17] = 17
    transition_names_consumed_stage: Literal[
        "fresh_exact_v209_unbound_provider_failure_source_authority_and_recovery_population_preflight_only"
    ] = CONSUMED_STAGE
    transition_next_stage_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_v228_freeze:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("freeze_id")
        return self


class ArtifactBinding(FrozenModel):
    artifact_id: str
    provider_call_id: str
    artifact_kind: ArtifactKind
    relative_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)
    public_projection_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    canonical_bytes_match: Literal[True] = True
    descriptor_bytes_match: Literal[True] = True

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if not _safe_relative_path(self.relative_path):
            raise ValueError("unsafe Provider artifact path")
        if (self.artifact_kind == "response_metadata") != (
            self.public_projection_sha256 is not None
        ):
            raise ValueError("Provider response projection shape differs")
        return self


class ProviderCallAuthority(FrozenModel):
    provider_call_id: str
    descriptor_id: str
    run_start_receipt_id: str
    historical_job_id: str
    call_ordinal: int = Field(ge=0, le=22)
    status: ProviderCallStatus
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_byte_count: int = Field(gt=0)
    intention_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    certificate_id: str
    pre_transport_receipt_id: str
    response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    error_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    error_type: str | None = None
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    artifact_bindings: tuple[ArtifactBinding, ArtifactBinding, ArtifactBinding]
    relation_closed: Literal[True] = True

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        kinds = tuple(sorted(item.artifact_kind for item in self.artifact_bindings))
        expected = (
            ("request_metadata", "response_metadata", "usage_metadata")
            if self.status == "succeeded"
            else ("error_metadata", "request_metadata", "usage_metadata")
        )
        if (
            kinds != expected
            or len({item.relative_path for item in self.artifact_bindings}) != 3
            or any(
                item.provider_call_id != self.provider_call_id for item in self.artifact_bindings
            )
            or (self.status == "succeeded")
            != (self.response_sha256 is not None and self.error_sha256 is None)
            or (self.status != "succeeded")
            != (self.response_sha256 is None and self.error_sha256 is not None)
            or (self.status == "succeeded") != (self.error_type is None)
        ):
            raise ValueError("Provider call authority relation differs")
        return self


class V226SourceRow(Identified):
    row_id: str
    v228_freeze_id: str
    historical_job_id: str
    job_ordinal: int = Field(ge=0, le=191)
    failure_record_id: str
    failure_relative_path: str
    failure_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    failure_file_byte_count: int = Field(gt=0)
    failure_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_start_receipt_id: str
    authorization_id: str
    failure_kind: Literal["unbound_provider_failure"] = "unbound_provider_failure"
    job_error_sha256: Literal[
        "bf06dd05d7431b80d5a218229dd0c1b6251b7e801ba4ade9e745d4a61ae3ca2f"
    ] = V226_JOB_FAILURE_SHA256
    provider_calls: tuple[ProviderCallAuthority, ...] = Field(min_length=1, max_length=23)
    successful_prefix_call_count: int = Field(ge=0, le=22)
    failed_call_ordinal: int = Field(ge=0, le=22)
    failed_provider_call_id: str
    failed_descriptor_id: str
    failed_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    failure_class: FailureClass
    historical_terminal_evidence_admitted: Literal[False] = False
    historical_five_layer_evidence_admitted: Literal[False] = False
    recovery_attempted: Literal[False] = False

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_v226_source_row:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        calls = self.provider_calls
        failed = calls[-1]
        if (
            not _safe_relative_path(self.failure_relative_path)
            or tuple(item.call_ordinal for item in calls) != tuple(range(len(calls)))
            or any(item.historical_job_id != self.historical_job_id for item in calls)
            or any(item.run_start_receipt_id != self.run_start_receipt_id for item in calls)
            or any(item.status != "succeeded" for item in calls[:-1])
            or failed.status == "succeeded"
            or self.successful_prefix_call_count != len(calls) - 1
            or self.failed_call_ordinal != len(calls) - 1
            or self.failed_provider_call_id != failed.provider_call_id
            or self.failed_descriptor_id != failed.descriptor_id
            or self.failed_request_sha256 != failed.request_sha256
            or (
                self.failure_class == "reasoning_budget_exhausted_normalized_public_content_empty"
                and failed.error_type != "ReasoningBudgetExhaustedError"
            )
            or (
                self.failure_class == "json_decode_failure_exact_syntax_unavailable"
                and failed.error_type != "JSONDecodeError"
            )
        ):
            raise ValueError("v26.226 source row differs")
        self.check_id("row_id")
        return self


class V226SourceAuthorityAudit(Identified):
    audit_id: str
    source_identity_id: str
    v228_freeze_id: str
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
    source_rows: tuple[V226SourceRow, ...] = Field(
        min_length=EXACT_SOURCE_COUNT, max_length=EXACT_SOURCE_COUNT
    )
    exact_source_count: Literal[33] = EXACT_SOURCE_COUNT
    excluded_host_failure_count: Literal[3] = HOST_EXCLUSION_COUNT
    source_row_id_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    v226_actual_source_projection_sha256: Literal[
        "d9243f618f547da83cae5e6698d3155030b3065058cf5372b8171bf013d3d3f0"
    ] = V228_PROVIDER_EXCLUSION_SET_SHA256
    v228_exclusion_set_sha256: Literal[
        "d9243f618f547da83cae5e6698d3155030b3065058cf5372b8171bf013d3d3f0"
    ] = V228_PROVIDER_EXCLUSION_SET_SHA256
    v228_exclusion_set_match: Literal[True] = True
    excluded_host_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_and_exclusion_exact_set_equality: Literal[True] = True
    historical_v26_226_mutation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_v226_source_authority_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        ordinals = tuple(item.job_ordinal for item in self.source_rows)
        jobs = tuple(item.historical_job_id for item in self.source_rows)
        if (
            ordinals != tuple(sorted(set(ordinals)))
            or len(set(jobs)) != EXACT_SOURCE_COUNT
            or canonical_sha256(tuple(item.row_id for item in self.source_rows))
            != self.source_row_id_set_sha256
        ):
            raise ValueError("source authority population differs")
        self.check_id("audit_id")
        return self


class ProviderJournalAuthority(Identified):
    audit_id: str
    source_authority_audit_id: str
    predecessor_provider_census_id: Literal[
        "finance_v26_226_provider_intent_census:bc758841db428bcd89d8b3f0a91adf83c5716b13d2529c2bafcd1ebfe5e45024"
    ] = V226_PROVIDER_CENSUS_ID
    source_row_ids: tuple[str, ...] = Field(
        min_length=EXACT_SOURCE_COUNT, max_length=EXACT_SOURCE_COUNT
    )
    provider_descriptor_count: int = Field(ge=EXACT_SOURCE_COUNT)
    request_metadata_count: int = Field(ge=EXACT_SOURCE_COUNT)
    response_metadata_count: int = Field(ge=0)
    error_metadata_count: Literal[33] = EXACT_SOURCE_COUNT
    usage_metadata_count: int = Field(ge=EXACT_SOURCE_COUNT)
    reasoning_budget_error_count: Literal[31] = IDENTIFIABLE_REASONING_BUDGET_COUNT
    json_decode_error_count: Literal[2] = UNIDENTIFIABLE_JSON_SYNTAX_COUNT
    relation_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    orphan_request_intent_count: Literal[0] = 0
    orphan_descriptor_count: Literal[0] = 0
    invalid_relation_count: Literal[0] = 0
    raw_request_count: Literal[0] = 0
    raw_provider_response_count: Literal[0] = 0
    private_reasoning_content_count: Literal[0] = 0
    relation_closed: Literal[True] = True
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_provider_journal_authority:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            self.source_row_ids != tuple(sorted(set(self.source_row_ids)))
            or self.request_metadata_count != self.provider_descriptor_count
            or self.response_metadata_count + self.error_metadata_count
            != self.provider_descriptor_count
            or self.usage_metadata_count != self.provider_descriptor_count
        ):
            raise ValueError("Provider journal authority geometry differs")
        self.check_id("audit_id")
        return self


class RequestReplayRow(FrozenModel):
    source_row_id: str
    historical_job_id: str
    job_ordinal: int = Field(ge=0, le=191)
    invocation_count: int = Field(ge=1, le=23)
    successful_invocation_ids: tuple[str, ...] = Field(max_length=22)
    phases: tuple[str, ...] = Field(min_length=1, max_length=23)
    request_sha256s: tuple[str, ...] = Field(min_length=1, max_length=23)
    response_sha256s: tuple[str, ...] = Field(max_length=22)
    successful_prefix_call_count: int = Field(ge=0, le=22)
    failed_call_ordinal: int = Field(ge=0, le=22)
    exact_request_match_count: int = Field(ge=1, le=23)
    exact_response_match_count: int = Field(ge=0, le=22)
    failed_request_certificate_id: str
    failed_pre_transport_receipt_id: str
    failed_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    failed_request_byte_count: int = Field(gt=0)
    persisted_public_prefix_only: Literal[True] = True
    failed_call_response_supplied_to_replay: Literal[False] = False
    failed_request_capture_stopped_before_response_projection: Literal[True] = True
    historical_terminal_record_created_for_failed_call: Literal[False] = False
    historical_provider_calls_reissued: Literal[0] = 0
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            len(self.successful_invocation_ids) != self.successful_prefix_call_count
            or self.invocation_count != len(self.phases)
            or self.invocation_count != len(self.request_sha256s)
            or self.successful_prefix_call_count != len(self.response_sha256s)
            or self.failed_call_ordinal != self.successful_prefix_call_count
            or self.invocation_count != self.successful_prefix_call_count + 1
            or self.exact_request_match_count != self.invocation_count
            or self.exact_response_match_count != self.successful_prefix_call_count
        ):
            raise ValueError("request replay geometry differs")
        return self


class RequestReplayAudit(Identified):
    audit_id: str
    source_authority_audit_id: str
    provider_journal_authority_id: str
    rows: tuple[RequestReplayRow, ...] = Field(
        min_length=EXACT_SOURCE_COUNT, max_length=EXACT_SOURCE_COUNT
    )
    exact_job_count: Literal[33] = EXACT_SOURCE_COUNT
    exact_failed_request_match_count: Literal[33] = EXACT_SOURCE_COUNT
    historical_provider_calls_reissued: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_request_replay_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        ordinals = tuple(item.job_ordinal for item in self.rows)
        if ordinals != tuple(sorted(set(ordinals))):
            raise ValueError("request replay rows differ")
        self.check_id("audit_id")
        return self


class IdentifiabilityRow(Identified):
    row_id: str
    source_row_id: str
    historical_job_id: str
    job_ordinal: int = Field(ge=0, le=191)
    failure_class: FailureClass
    error_type: Literal["ReasoningBudgetExhaustedError", "JSONDecodeError"]
    public_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    public_content_length: int = Field(ge=0)
    finish_reason: Literal["length", "stop"]
    failure_semantics_identifiable: bool
    exact_json_syntax_identifiable: bool
    exact_json_response_bytes_persisted: Literal[False] = False
    exact_json_response_bytes_guessed: Literal[False] = False
    fresh_request_recovery_eligibility_identifiable: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_identifiability_row:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        reasoning = (
            self.failure_class == "reasoning_budget_exhausted_normalized_public_content_empty"
        )
        if reasoning != (
            self.error_type == "ReasoningBudgetExhaustedError"
            and self.failure_semantics_identifiable
            and not self.exact_json_syntax_identifiable
            and self.public_content_length == 0
            and self.public_content_sha256 == hashlib.sha256(b"").hexdigest()
        ) or (not reasoning) != (
            self.error_type == "JSONDecodeError"
            and not self.failure_semantics_identifiable
            and not self.exact_json_syntax_identifiable
            and self.public_content_length > 0
        ):
            raise ValueError("failure identifiability classification differs")
        self.check_id("row_id")
        return self


class IdentifiabilityAudit(Identified):
    audit_id: str
    source_authority_audit_id: str
    rows: tuple[IdentifiabilityRow, ...] = Field(
        min_length=EXACT_SOURCE_COUNT, max_length=EXACT_SOURCE_COUNT
    )
    exact_source_count: Literal[33] = EXACT_SOURCE_COUNT
    identifiable_reasoning_budget_count: Literal[31] = IDENTIFIABLE_REASONING_BUDGET_COUNT
    unidentifiable_json_syntax_count: Literal[2] = UNIDENTIFIABLE_JSON_SYNTAX_COUNT
    exact_json_response_bytes_persisted_count: Literal[0] = 0
    exact_json_response_bytes_guessed_count: Literal[0] = 0
    recovery_request_authority_identifiable_count: Literal[33] = EXACT_SOURCE_COUNT
    provider_calls: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_identifiability_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        ids = tuple(item.row_id for item in self.rows)
        reasoning = sum(item.failure_semantics_identifiable for item in self.rows)
        unknown_json = sum(item.error_type == "JSONDecodeError" for item in self.rows)
        if (
            ids != tuple(sorted(set(ids)))
            or reasoning != self.identifiable_reasoning_budget_count
            or unknown_json != self.unidentifiable_json_syntax_count
        ):
            raise ValueError("identifiability partition differs")
        self.check_id("audit_id")
        return self


class RecoveryCandidate(Identified):
    candidate_id: str
    source_authority_audit_id: str
    provider_journal_authority_id: str
    request_replay_audit_id: str
    identifiability_audit_id: str
    source_row_id: str
    identifiability_row_id: str
    historical_job_id: str
    job_ordinal: int = Field(ge=0, le=191)
    failure_record_id: str
    successful_prefix_call_count: int = Field(ge=0, le=22)
    successful_prefix_provider_call_ids: tuple[str, ...] = Field(max_length=22)
    failed_provider_call_id: str
    failed_descriptor_id: str
    exact_failed_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_failed_request_byte_count: int = Field(gt=0)
    exact_failed_request_certificate_id: str
    exact_failed_pre_transport_receipt_id: str
    failure_class: FailureClass
    historical_json_syntax_detail_available: bool
    historical_response_content_guessed: Literal[False] = False
    historical_job_identity_retained_only_as_parent: Literal[True] = True
    historical_job_reclassified: Literal[False] = False
    replacement_or_recovery_attempted: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    online_execution_authorized: Literal[False] = False

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_recovery_candidate:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            self.successful_prefix_call_count != len(self.successful_prefix_provider_call_ids)
            or self.historical_json_syntax_detail_available
        ):
            raise ValueError("Recovery Candidate boundary differs")
        self.check_id("candidate_id")
        return self


class RecoveryContract(Identified):
    contract_id: str
    source_authority_audit_id: str
    provider_journal_authority_id: str
    request_replay_audit_id: str
    identifiability_audit_id: str
    candidate_ids: tuple[str, ...] = Field(
        min_length=EXACT_SOURCE_COUNT, max_length=EXACT_SOURCE_COUNT
    )
    exact_candidate_count: Literal[33] = EXACT_SOURCE_COUNT
    fresh_recovery_job_identity_required: Literal[True] = True
    historical_job_identity_parent_only: Literal[True] = True
    exact_successful_prefix_and_failed_request_binding_required: Literal[True] = True
    historical_response_reconstruction_required: Literal[False] = False
    unknown_json_response_invention_allowed: Literal[False] = False
    historical_job_rerun_or_reclassification_allowed: Literal[False] = False
    historical_v26_226_mutation_allowed: Literal[False] = False
    empirical_row_creation_allowed: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    credential_lookups_authorized: Literal[False] = False
    recovery_execution_authorized: Literal[False] = False
    online_authorization_created: Literal[False] = False

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_recovery_contract:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if self.candidate_ids != tuple(sorted(set(self.candidate_ids))):
            raise ValueError("Recovery Contract Candidate set differs")
        self.check_id("contract_id")
        return self


class RecoveryPopulationJob(Identified):
    recovery_job_id: str
    recovery_contract_id: str
    candidate: RecoveryCandidate
    historical_job_identity_retained_only_as_parent: Literal[True] = True
    historical_job_reclassified: Literal[False] = False
    successful_prefix_provider_calls_authorized: Literal[0] = 0
    failed_request_reissue_authorized: Literal[0] = 0
    replacement_response_authorization_count: Literal[0] = 0
    recovery_execution_authorized: Literal[False] = False
    provider_calls_authorized: Literal[False] = False

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_recovery_job:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if self.recovery_job_id == self.candidate.historical_job_id:
            raise ValueError("Recovery Job reused historical Job identity")
        self.check_id("recovery_job_id")
        return self


class RecoveryPopulation(Identified):
    population_id: str
    recovery_contract_id: str
    jobs: tuple[RecoveryPopulationJob, ...] = Field(
        min_length=EXACT_SOURCE_COUNT, max_length=EXACT_SOURCE_COUNT
    )
    exact_job_count: Literal[33] = EXACT_SOURCE_COUNT
    fresh_recovery_job_identity_count: Literal[33] = EXACT_SOURCE_COUNT
    historical_job_identity_overlap_count: Literal[0] = 0
    identifiable_reasoning_budget_count: Literal[31] = IDENTIFIABLE_REASONING_BUDGET_COUNT
    unidentifiable_json_syntax_count: Literal[2] = UNIDENTIFIABLE_JSON_SYNTAX_COUNT
    provider_calls_authorized: Literal[False] = False
    recovery_execution_authorized: Literal[False] = False
    online_authorization_created: Literal[False] = False

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_recovery_population:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        recovery_ids = tuple(item.recovery_job_id for item in self.jobs)
        historical_ids = tuple(item.candidate.historical_job_id for item in self.jobs)
        reasoning = sum(
            item.candidate.failure_class
            == "reasoning_budget_exhausted_normalized_public_content_empty"
            for item in self.jobs
        )
        unknown_json = sum(
            item.candidate.failure_class == "json_decode_failure_exact_syntax_unavailable"
            for item in self.jobs
        )
        if (
            recovery_ids != tuple(sorted(set(recovery_ids)))
            or len(set(historical_ids)) != EXACT_SOURCE_COUNT
            or set(recovery_ids) & set(historical_ids)
            or any(item.recovery_contract_id != self.recovery_contract_id for item in self.jobs)
            or reasoning != self.identifiable_reasoning_budget_count
            or unknown_json != self.unidentifiable_json_syntax_count
        ):
            raise ValueError("Recovery Population differs")
        self.check_id("population_id")
        return self


class NegativeControlResult(FrozenModel):
    attack_name: str
    rejection_stage: str
    reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rejected: Literal[True] = True
    candidate_writes_before_rejection: Literal[0] = 0
    recovery_job_writes_before_rejection: Literal[0] = 0
    provider_calls_before_rejection: Literal[0] = 0


class NegativeControlAudit(Identified):
    audit_id: str
    source_authority_audit_id: str
    recovery_population_id: str
    results: tuple[NegativeControlResult, ...] = Field(
        min_length=len(NEGATIVE_CONTROL_NAMES), max_length=len(NEGATIVE_CONTROL_NAMES)
    )
    attack_count: Literal[12] = 12
    rejection_count: Literal[12] = 12
    accepted_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_negative_control_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        names = tuple(item.attack_name for item in self.results)
        if names != NEGATIVE_CONTROL_NAMES:
            raise ValueError("negative-control set differs")
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
        return "finance_v26_229_scope_boundary_audit:"

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
    gates: tuple[Gate, ...] = Field(min_length=len(GATE_NAMES), max_length=len(GATE_NAMES))
    passed_count: Literal[6] = 6
    failed_count: Literal[0] = 0
    noncompensatory: Literal[True] = True
    decision: Literal["PASS"] = "PASS"

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_gate_evaluation:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if tuple(item.name for item in self.gates) != GATE_NAMES:
            raise ValueError("Gate partition differs")
        self.check_id("evaluation_id")
        return self


class Decision(Identified):
    decision_id: str
    gate_evaluation_id: str
    decision: Literal[
        "v26_226_exact_33_unbound_provider_failure_source_authority_and_fresh_recovery_population_preflight_passed"
    ] = DECISION_VALUE
    exact_source_count: Literal[33] = EXACT_SOURCE_COUNT
    fresh_recovery_job_count: Literal[33] = EXACT_SOURCE_COUNT
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    recovery_execution_authorized: Literal[False] = False
    online_execution_authorized: Literal[False] = False

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_decision:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("decision_id")
        return self


class Transition(Identified):
    transition_id: str
    decision_id: str
    consumed_stage: Literal[
        "fresh_exact_v209_unbound_provider_failure_source_authority_and_recovery_population_preflight_only"
    ] = CONSUMED_STAGE
    next_stage: Literal[
        "fresh_exact_v209_unbound_provider_failure_source_authority_and_recovery_population_preflight_independent_audit_only"
    ] = NEXT_STAGE
    next_stage_authorized: Literal[False] = False
    independent_audit_required: Literal[True] = True
    recovery_population_preflight_only: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    credential_lookups_authorized: Literal[False] = False
    recovery_execution_authorized: Literal[False] = False
    failed_job_reruns_authorized: Literal[False] = False
    online_authorization_created: Literal[False] = False
    historical_v26_226_mutation_authorized: Literal[False] = False
    empirical_estimation_authorized: Literal[False] = False

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_transition:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("transition_id")
        return self


class Report(Identified):
    report_id: str
    run_id: Literal[
        "finance_v26_229_fresh_exact_v209_unbound_provider_failure_source_authority_and_recovery_population_preflight_v1_20260904"
    ] = RUN_ID
    authorization_id: str
    source_identity_id: str
    v228_freeze_id: str
    source_authority_audit_id: str
    provider_journal_authority_id: str
    request_replay_audit_id: str
    identifiability_audit_id: str
    recovery_contract_id: str
    recovery_population_id: str
    negative_control_audit_id: str
    scope_boundary_audit_id: str
    gate_evaluation_id: str
    decision_id: str
    transition_id: str
    decision: Literal[
        "v26_226_exact_33_unbound_provider_failure_source_authority_and_fresh_recovery_population_preflight_passed"
    ] = DECISION_VALUE
    exact_source_count: Literal[33] = EXACT_SOURCE_COUNT
    identifiable_reasoning_budget_count: Literal[31] = IDENTIFIABLE_REASONING_BUDGET_COUNT
    unidentifiable_json_syntax_count: Literal[2] = UNIDENTIFIABLE_JSON_SYNTAX_COUNT
    fresh_recovery_job_count: Literal[33] = EXACT_SOURCE_COUNT
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    recovery_executions: Literal[0] = 0
    failed_job_reruns: Literal[0] = 0
    historical_v26_226_mutations: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    online_authorizations: Literal[0] = 0

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_229_preflight_report:"

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
        if not _safe_relative_path(self.relative_path):
            raise ValueError("unsafe artifact path")
        return self


class ArtifactManifest(Identified):
    manifest_id: str
    run_id: Literal[
        "finance_v26_229_fresh_exact_v209_unbound_provider_failure_source_authority_and_recovery_population_preflight_v1_20260904"
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
        return "finance_v26_229_artifact_manifest:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        paths = tuple(item.relative_path for item in self.members)
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_229_artifact_root:",
        )
        if (
            paths != tuple(sorted(set(paths)))
            or self.file_count != len(self.members)
            or self.total_member_bytes != sum(item.byte_count for item in self.members)
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
        tuple(item.model_dump(mode="json") for item in members),
        prefix="finance_v26_229_artifact_root:",
    )
    return make_identity(
        ArtifactManifest,
        {
            "members": members,
            "file_count": len(members),
            "total_member_bytes": sum(item.byte_count for item in members),
            "artifact_root": root,
        },
        field="manifest_id",
        prefix=ArtifactManifest.prefix(),
    )
