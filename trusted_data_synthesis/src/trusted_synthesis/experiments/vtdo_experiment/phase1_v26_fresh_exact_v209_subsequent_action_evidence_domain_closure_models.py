# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Annotated, Any, Final, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_repair_models as v226_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    SemanticActionResponseRejection,
    parse_exact_canonical_action_payload,
)

SCHEMA_VERSION: Final = "fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"
CONSUMED_STAGE: Final = (
    "fresh_exact_v209_subsequent_action_parser_reference_evidence_domain_closure_preflight_only"
)
NEXT_STAGE: Final = (
    "fresh_exact_v209_subsequent_action_parser_reference_"
    "evidence_domain_closure_independent_audit_only"
)
DECISION_VALUE: Final = (
    "subsequent_action_parser_reference_evidence_domain_closed_for_three_"
    "v26_226_host_failures_independent_audit_required_online_execution_blocked"
)

EXTERNAL_REVIEW_SHA256: Final = "5e9c72e7f0a9c25517e4eb9f63f0f9a3088940167f4e3c7b39c7b09517b18d1a"
EXTERNAL_REVIEW_BYTE_COUNT: Final = 13_590
OPERATOR_DIRECTIVE: Final = "参照审计结果逐一修订"
OPERATOR_DIRECTIVE_SHA256: Final = (
    "a8bdf30ec84061dd289280f38fb257330db9ced1d1e559d094291d25363ca2cf"
)

V226_RUN_ID: Final = (
    "finance_v26_226_fresh_exact_v209_parent_bound_postresponse_serializer_repair_"
    "exact_192_job_replacement_online_execution_v1_20260904"
)
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
V226_MANIFEST_SHA256: Final = "d6cc9799114ad0015fe8e781317e1b0eae498a09fc109f8ead199c1b11e38ee1"
V226_SUMMARY_SHA256: Final = "337b5156fc86f5159a1c7081c9978105351dfc5217b12e7254669c37d6728122"
V226_TRANSITION_SHA256: Final = "105f2c1ed44b43ca0e0d3179278ce308c68199c3033344b0fd1e634562dd5b8c"
V226_SOURCE_COMMIT: Final = "a52df3e215f681a855bfdc94aafe9d699f08a59c"
V226_SOURCE_TREE: Final = "6600c26140eafe5581f3ca727281638df07b5d14"

HOST_FAILURE_ORDINALS: Final = (6, 22, 149)
HOST_FAILURE_JOB_IDS: Final = (
    "fresh_repaired_final_continuity_executable_full_condition_development_job:0cfecdc4a6041e079c9c9ea079c72500f8428da75a239973cd8e798630cd23f3",
    "fresh_repaired_final_continuity_executable_full_condition_development_job:27837f6bb9ec956d11ab80875959672475b303b11599edf8daf3b2ffa837921b",
    "fresh_repaired_final_continuity_executable_full_condition_development_job:c8300ed7689afaa07c68964924a1e5e58bf336cec22992840b77b91133c0d3c5",
)
HOST_FAILURE_RECORD_IDS: Final = (
    "finance_v26_226_replacement_job_failure:59eed175bd01502ae8a4915e4e932ed8661f0b48201ba801ef4b9dbe062c47f0",
    "finance_v26_226_replacement_job_failure:deab35c580b66d25b8e8260a63646285b1eaa692a6303316dccc46a0378d7650",
    "finance_v26_226_replacement_job_failure:bc0d40d583bd108fe3e3fb86285f3328cfb8f5c334f812c3c791c6e529011a53",
)
HOST_FAILURE_ERROR_SHA256S: Final = (
    "cb7d691ac6f6cae0152642ce267c69106719c43b812d6860ecd57955785e4ee2",
    "cb7d691ac6f6cae0152642ce267c69106719c43b812d6860ecd57955785e4ee2",
    "62b6b9b098a85e0666673231c87d0f60f4197e44279869843dc01151e077726c",
)
HOST_FAILURE_PROVIDER_CALL_COUNTS: Final = (3, 3, 2)
HOST_FAILURE_FILE_SHA256S: Final = (
    "a879387705ddb81a14e3fd7ea740e1f2deb245522e44d5815b513215fd8e8d6d",
    "5b98a8aa21e9d80d855afd75969bd1e9ef55e248e7c5c4fd2d993fd462d2835f",
    "e105397e02ebaa47f119f032366c81f497f6827774badbeab96e07c1bf1ab116",
)
HOST_FAILURE_FILE_BYTE_COUNTS: Final = (12_333, 12_334, 8_570)

PARSER_TERMINAL: Final = "first_response_abi_invalid"
REFERENCE_TERMINAL: Final = "first_action_reference_invalid"
PARSER_POLICY_ID: Final = (
    "fresh_kernel_terminal_policy:b5fb980fc0c80b2c72a964d538cf487e9a27403aff0ebe4e88ffb3b29847c04f"
)
REFERENCE_POLICY_ID: Final = (
    "fresh_kernel_terminal_policy:443b4c076ea4d694590fbafcd66d1c23681679bd24368ad43a354299c480fe3b"
)
EVIDENCE_KINDS: Final = (
    "subsequent_action_parser_rejection",
    "subsequent_action_reference_failure",
)
LAYER_KINDS: Final = ("raw", "result", "trace", "outcome", "checkpoint")
NEGATIVE_CONTROL_NAMES: Final = (
    "subsequent_action_phase_replaced",
    "parser_reference_evidence_type_replaced",
    "cross_job_invocation_record_substituted",
    "invocation_prefix_truncated",
    "stale_current_state_parent_substituted",
    "stale_candidate_parent_substituted",
    "fully_rehashed_evidence_and_five_layers_forged",
    "excluded_provider_failure_substituted",
)
GATE_NAMES: Final = (
    "G0_EXTERNAL_SCOPE_AND_V26_226_FREEZE",
    "G1_EXACT_THREE_HOST_FAILURE_SOURCE_ROWS",
    "G2_COMPLETE_INVOCATION_PREFIX_BINDING",
    "G3_SUBSEQUENT_ACTION_PARSER_EVIDENCE",
    "G4_SUBSEQUENT_ACTION_REFERENCE_EVIDENCE",
    "G5_DERIVED_TERMINAL_AND_FIVE_LAYER_CLOSURE",
    "G6_NEGATIVE_CONTROLS",
    "G7_ZERO_PROVIDER_SCOPE_BOUNDARY",
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


def sha(payload: bytes | bytearray | memoryview) -> str:
    return hashlib.sha256(bytes(payload)).hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha(canonical_bytes(value))


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
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


def _safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


class ExternalAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    external_review_sha256: Literal[
        "5e9c72e7f0a9c25517e4eb9f63f0f9a3088940167f4e3c7b39c7b09517b18d1a"
    ] = EXTERNAL_REVIEW_SHA256
    external_review_byte_count: Literal[13590] = EXTERNAL_REVIEW_BYTE_COUNT
    audit_result: Literal["PASSED_AS_SCOPED_ARTIFACT_COMPLETENESS"] = (
        "PASSED_AS_SCOPED_ARTIFACT_COMPLETENESS"
    )
    exact_192_job_execution_result: Literal["FAILED_INCOMPLETE"] = "FAILED_INCOMPLETE"
    first_fundamental_blocker: Literal[
        "SUBSEQUENT_ACTION_PARSER_REFERENCE_EVIDENCE_DOMAIN_NOT_CLOSED"
    ] = "SUBSEQUENT_ACTION_PARSER_REFERENCE_EVIDENCE_DOMAIN_NOT_CLOSED"
    operator_directive: Literal["参照审计结果逐一修订"] = OPERATOR_DIRECTIVE
    operator_directive_sha256: Literal[
        "a8bdf30ec84061dd289280f38fb257330db9ced1d1e559d094291d25363ca2cf"
    ] = OPERATOR_DIRECTIVE_SHA256
    operator_directive_byte_count: Literal[30] = 30
    consumed_stage: Literal[
        "fresh_exact_v209_subsequent_action_parser_reference_evidence_domain_closure_preflight_only"
    ] = CONSUMED_STAGE
    exact_host_failure_replay_ordinals: tuple[Literal[6, 22, 149], ...] = (
        6,
        22,
        149,
    )
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    historical_artifact_modification_authorized: Literal[False] = False
    empirical_estimation_authorized: Literal[False] = False
    online_execution_authorized: Literal[False] = False
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuthorization:
        directive = self.operator_directive.encode("utf-8")
        if (
            sha(directive) != self.operator_directive_sha256
            or len(directive) != self.operator_directive_byte_count
            or self.exact_host_failure_replay_ordinals != HOST_FAILURE_ORDINALS
            or self.authorization_id
            != identity(
                self,
                "authorization_id",
                "finance_v26_227_external_authorization:",
            )
        ):
            raise ValueError("v26.227 external Authorization differs")
        return self


class V226Freeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v226_run_id: Literal[
        "finance_v26_226_fresh_exact_v209_parent_bound_postresponse_serializer_repair_exact_192_job_replacement_online_execution_v1_20260904"
    ] = V226_RUN_ID
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
    v226_manifest_sha256: Literal[
        "d6cc9799114ad0015fe8e781317e1b0eae498a09fc109f8ead199c1b11e38ee1"
    ] = V226_MANIFEST_SHA256
    v226_summary_sha256: Literal[
        "337b5156fc86f5159a1c7081c9978105351dfc5217b12e7254669c37d6728122"
    ] = V226_SUMMARY_SHA256
    v226_transition_sha256: Literal[
        "105f2c1ed44b43ca0e0d3179278ce308c68199c3033344b0fd1e634562dd5b8c"
    ] = V226_TRANSITION_SHA256
    v226_source_commit: Literal["a52df3e215f681a855bfdc94aafe9d699f08a59c"] = V226_SOURCE_COMMIT
    v226_source_tree: Literal["6600c26140eafe5581f3ca727281638df07b5d14"] = V226_SOURCE_TREE
    formal_file_count: Literal[3428] = 3_428
    formal_total_byte_count: Literal[99765014] = 99_765_014
    manifest_member_count: Literal[3427] = 3_427
    manifest_member_byte_count: Literal[99047004] = 99_047_004
    exact_job_count: Literal[192] = 192
    complete_job_count: Literal[156] = 156
    failure_record_count: Literal[36] = 36
    host_failure_count: Literal[3] = 3
    unbound_provider_failure_count: Literal[33] = 33
    host_failure_ordinals: tuple[Literal[6, 22, 149], ...] = HOST_FAILURE_ORDINALS
    host_failure_job_ids: tuple[str, ...] = HOST_FAILURE_JOB_IDS
    host_failure_record_ids: tuple[str, ...] = HOST_FAILURE_RECORD_IDS
    host_failure_error_sha256s: tuple[str, ...] = HOST_FAILURE_ERROR_SHA256S
    host_failure_source_set_sha256: Literal[
        "dbecba00270f755044c2293ba103ed647b977cf2530af508e0515042cab8d33c"
    ] = "dbecba00270f755044c2293ba103ed647b977cf2530af508e0515042cab8d33c"
    unbound_provider_failure_exclusion_set_sha256: Literal[
        "d9243f618f547da83cae5e6698d3155030b3065058cf5372b8171bf013d3d3f0"
    ] = "d9243f618f547da83cae5e6698d3155030b3065058cf5372b8171bf013d3d3f0"
    v225_v3_authorization_consumed: Literal[True] = True
    v225_v3_authorization_reusable: Literal[False] = False
    historical_terminal_assignment_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_freeze(self) -> V226Freeze:
        if (
            self.host_failure_ordinals != HOST_FAILURE_ORDINALS
            or self.host_failure_job_ids != HOST_FAILURE_JOB_IDS
            or self.host_failure_record_ids != HOST_FAILURE_RECORD_IDS
            or self.host_failure_error_sha256s != HOST_FAILURE_ERROR_SHA256S
            or self.freeze_id != identity(self, "freeze_id", "finance_v26_227_v226_freeze:")
        ):
            raise ValueError("v26.227 v26.226 Freeze differs")
        return self


class SourceMember(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_member(self) -> SourceMember:
        if not _safe_relative_path(self.relative_path):
            raise ValueError("v26.227 source member path is unsafe")
        return self


class SourceIdentity(FrozenModel):
    source_identity_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    implementation_members: tuple[SourceMember, ...] = Field(min_length=2)
    implementation_member_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    v213_source_modified: Literal[False] = False
    exact_v209_runner_modified: Literal[False] = False
    provider_network_symbols: Literal[0] = 0
    credential_environment_symbols: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_source(self) -> SourceIdentity:
        paths = tuple(item.relative_path for item in self.implementation_members)
        members = tuple(
            item.model_dump(mode="json", warnings=False) for item in self.implementation_members
        )
        if (
            paths != tuple(sorted(set(paths)))
            or canonical_sha256(members) != self.implementation_member_set_sha256
            or self.source_identity_id
            != identity(
                self,
                "source_identity_id",
                "finance_v26_227_source_identity:",
            )
        ):
            raise ValueError("v26.227 Source Identity differs")
        return self


class HostFailureRow(FrozenModel):
    row_id: str = Field(min_length=1)
    v226_freeze_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    job_ordinal: Literal[6, 22, 149]
    failure_record_id: str = Field(min_length=1)
    failure_relative_path: str = Field(min_length=1)
    failure_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    failure_file_byte_count: int = Field(gt=0)
    failure_record: dict[str, Any]
    failure_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    public_payloads: tuple[dict[str, Any], ...] = Field(min_length=2, max_length=3)
    public_payload_sha256s: tuple[str, ...] = Field(min_length=2, max_length=3)
    expected_evidence_kind: Literal[
        "subsequent_action_parser_rejection",
        "subsequent_action_reference_failure",
    ]
    terminal_evidence_admitted_in_v226: Literal[False] = False
    historical_terminal_added: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_row(self) -> HostFailureRow:
        record = v226_models.JobFailureRecord.model_validate(self.failure_record)
        try:
            position = HOST_FAILURE_ORDINALS.index(self.job_ordinal)
        except ValueError as error:  # pragma: no cover - Literal rejects first
            raise ValueError("v26.227 Host failure ordinal differs") from error
        projected: list[dict[str, Any]] = []
        projected_hashes: list[str] = []
        for call in record.provider_calls:
            if call.status != "succeeded":
                raise ValueError("v26.227 Host failure source call was not successful")
            artifacts = tuple(
                item for item in call.artifacts if item.artifact_kind == "response_metadata"
            )
            if len(artifacts) != 1:
                raise ValueError("v26.227 Host failure lacks one response projection")
            artifact = artifacts[0]
            if (
                not artifact.public_projection_present
                or not isinstance(artifact.public_projection, dict)
                or artifact.public_projection_sha256 is None
            ):
                raise ValueError("v26.227 Host failure public projection is absent")
            projected.append(artifact.public_projection)
            projected_hashes.append(artifact.public_projection_sha256)
        expected_kind = (
            "subsequent_action_parser_rejection"
            if self.job_ordinal in {6, 22}
            else "subsequent_action_reference_failure"
        )
        if (
            record.failure_kind != "host_failure"
            or record.job_id != self.job_id
            or record.job_ordinal != self.job_ordinal
            or record.record_id != self.failure_record_id
            or record.record_id != HOST_FAILURE_RECORD_IDS[position]
            or record.job_id != HOST_FAILURE_JOB_IDS[position]
            or record.error_sha256 != HOST_FAILURE_ERROR_SHA256S[position]
            or len(record.provider_calls) != HOST_FAILURE_PROVIDER_CALL_COUNTS[position]
            or self.failure_relative_path != f"job_failures/job_{self.job_ordinal:03d}.json"
            or not _safe_relative_path(self.failure_relative_path)
            or self.failure_file_sha256 != HOST_FAILURE_FILE_SHA256S[position]
            or self.failure_file_byte_count != HOST_FAILURE_FILE_BYTE_COUNTS[position]
            or self.failure_record_sha256 != canonical_sha256(self.failure_record)
            or self.public_payloads != tuple(projected)
            or self.public_payload_sha256s != tuple(projected_hashes)
            or self.public_payload_sha256s
            != tuple(canonical_sha256(item) for item in self.public_payloads)
            or self.expected_evidence_kind != expected_kind
            or self.row_id != identity(self, "row_id", "finance_v26_227_host_failure_row:")
        ):
            raise ValueError("v26.227 Host failure Row differs")
        return self


def _strict_invocation_prefix(
    raw_records: tuple[dict[str, Any], ...], *, job_id: str
) -> tuple[v209_models.ExecutableInvocationRecord, ...]:
    records = tuple(
        v209_models.ExecutableInvocationRecord.model_validate(item) for item in raw_records
    )
    if (
        len(records) < 2
        or len(records) > 10
        or any(item.job_id != job_id for item in records)
        or tuple(item.invocation_index for item in records) != tuple(range(len(records)))
        or len({item.invocation_id for item in records}) != len(records)
        or records[0].phase != "first_action"
        or any(item.phase == "final" for item in records[:-1])
        or records[-1].phase != "subsequent_action"
    ):
        raise ValueError("v26.227 complete same-Job invocation prefix differs")
    for record in records[:-1]:
        if (
            record.typed_terminal is not None
            or not record.exact_response_parsed
            or not record.current_state_and_candidate_or_final_envelope_valid
            or not record.runtime_step_or_finalize_completed
            or record.public_response_sha256 is None
        ):
            raise ValueError("v26.227 invocation prefix contains an earlier terminal")
    return records


class ParserSubsequentActionEvidence(FrozenModel):
    evidence_id: str = Field(min_length=1)
    evidence_kind: Literal["subsequent_action_parser_rejection"] = (
        "subsequent_action_parser_rejection"
    )
    external_authorization_id: str = Field(min_length=1)
    v226_freeze_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    host_failure_row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    job_ordinal: Literal[6, 22]
    phase: Literal["subsequent_action"] = "subsequent_action"
    invocation_records: tuple[dict[str, Any], ...] = Field(min_length=2, max_length=10)
    public_payload: dict[str, Any]
    public_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_state_id: str = Field(min_length=1)
    current_candidate_action_ids: tuple[str, ...] = Field(min_length=1)
    observed_state_id: str = Field(min_length=1)
    observed_action_id: str = Field(min_length=1)
    parser_exception_type: Literal["SemanticActionResponseRejection"] = (
        "SemanticActionResponseRejection"
    )
    parser_exception_family: Literal["response_serialization_failure"] = (
        "response_serialization_failure"
    )
    parser_exception_subtype: Literal["canonical_action_not_exact_four_field_grammar"] = (
        "canonical_action_not_exact_four_field_grammar"
    )
    parser_rejected: Literal[True] = True
    caller_terminal_input: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_evidence(self) -> ParserSubsequentActionEvidence:
        records = _strict_invocation_prefix(self.invocation_records, job_id=self.job_id)
        record = records[-1]
        try:
            parse_exact_canonical_action_payload(self.public_payload)
        except SemanticActionResponseRejection as error:
            if (
                error.family != self.parser_exception_family
                or error.subtype != self.parser_exception_subtype
            ):
                raise ValueError("v26.227 parser rejection class differs") from error
        else:
            raise ValueError("v26.227 parser evidence carries a parseable Action")
        if (
            record.typed_terminal != PARSER_TERMINAL
            or record.exact_response_parsed
            or record.current_state_and_candidate_or_final_envelope_valid
            or record.runtime_step_or_finalize_completed
            or record.action_accepted is not None
            or record.selected_action_id is not None
            or record.current_state_id != self.current_state_id
            or record.candidate_action_ids != self.current_candidate_action_ids
            or self.observed_state_id != self.current_state_id
            or self.observed_action_id not in self.current_candidate_action_ids
            or record.event_sequence[-2:] != ("parse_exact_response", "terminal_dispatch")
            or record.public_response_sha256 != self.public_payload_sha256
            or self.public_payload_sha256 != canonical_sha256(self.public_payload)
            or self.public_payload.get("state_id") != self.observed_state_id
            or self.public_payload.get("action_id") != self.observed_action_id
            or self.evidence_id
            != identity(
                self,
                "evidence_id",
                "finance_v26_227_parser_subsequent_action_evidence:",
            )
        ):
            raise ValueError("v26.227 parser subsequent-Action Evidence differs")
        return self


class ReferenceSubsequentActionEvidence(FrozenModel):
    evidence_id: str = Field(min_length=1)
    evidence_kind: Literal["subsequent_action_reference_failure"] = (
        "subsequent_action_reference_failure"
    )
    external_authorization_id: str = Field(min_length=1)
    v226_freeze_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    host_failure_row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    job_ordinal: Literal[149] = 149
    phase: Literal["subsequent_action"] = "subsequent_action"
    invocation_records: tuple[dict[str, Any], ...] = Field(min_length=2, max_length=10)
    public_payload: dict[str, Any]
    public_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_state_id: str = Field(min_length=1)
    current_candidate_action_ids: tuple[str, ...] = Field(min_length=1)
    observed_state_id: str = Field(min_length=1)
    observed_action_id: str = Field(min_length=1)
    parser_accepted: Literal[True] = True
    current_reference_valid: Literal[False] = False
    caller_terminal_input: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_evidence(self) -> ReferenceSubsequentActionEvidence:
        records = _strict_invocation_prefix(self.invocation_records, job_id=self.job_id)
        record = records[-1]
        try:
            proposal = parse_exact_canonical_action_payload(self.public_payload)
        except SemanticActionResponseRejection as error:
            raise ValueError("v26.227 reference evidence carries parser rejection") from error
        if (
            record.typed_terminal != REFERENCE_TERMINAL
            or not record.exact_response_parsed
            or record.current_state_and_candidate_or_final_envelope_valid
            or record.runtime_step_or_finalize_completed
            or record.action_accepted is not None
            or record.current_state_id != self.current_state_id
            or record.candidate_action_ids != self.current_candidate_action_ids
            or record.selected_action_id != self.observed_action_id
            or proposal.state_id != self.observed_state_id
            or proposal.action_id != self.observed_action_id
            or self.observed_state_id != self.current_state_id
            or self.observed_action_id in self.current_candidate_action_ids
            or record.event_sequence[-3:]
            != (
                "parse_exact_response",
                "validate_current_state_and_candidate_or_final_envelope",
                "terminal_dispatch",
            )
            or record.public_response_sha256 != self.public_payload_sha256
            or self.public_payload_sha256 != canonical_sha256(self.public_payload)
            or self.evidence_id
            != identity(
                self,
                "evidence_id",
                "finance_v26_227_reference_subsequent_action_evidence:",
            )
        ):
            raise ValueError("v26.227 reference subsequent-Action Evidence differs")
        return self


Evidence = Annotated[
    ParserSubsequentActionEvidence | ReferenceSubsequentActionEvidence,
    Field(discriminator="evidence_kind"),
]
EVIDENCE_ADAPTER: Final[TypeAdapter[Evidence]] = TypeAdapter(Evidence)
ObservedEvidence = Evidence
OBSERVED_EVIDENCE_ADAPTER: Final[TypeAdapter[ObservedEvidence]] = EVIDENCE_ADAPTER


class DispatcherBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v226_freeze_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    frozen_v213_dispatcher_binding_id: Literal[
        "fresh_repaired_observation_derived_terminal_dispatcher_binding:10a51ef2cc7f7ce20ad63918507c201f12112e34729e1088ab272da3820b209f"
    ] = "fresh_repaired_observation_derived_terminal_dispatcher_binding:10a51ef2cc7f7ce20ad63918507c201f12112e34729e1088ab272da3820b209f"
    frozen_v195_terminal_registry_id: Literal[
        "fresh_kernel_terminal_registry:a9d3089011f34b114b4b8264c09eb6b4c5875dd6978de0a2c3fe316577203152"
    ] = "fresh_kernel_terminal_registry:a9d3089011f34b114b4b8264c09eb6b4c5875dd6978de0a2c3fe316577203152"
    evidence_kinds: tuple[str, str] = EVIDENCE_KINDS
    parser_terminal_kind: Literal["first_response_abi_invalid"] = PARSER_TERMINAL
    parser_terminal_policy_id: Literal[
        "fresh_kernel_terminal_policy:b5fb980fc0c80b2c72a964d538cf487e9a27403aff0ebe4e88ffb3b29847c04f"
    ] = PARSER_POLICY_ID
    reference_terminal_kind: Literal["first_action_reference_invalid"] = REFERENCE_TERMINAL
    reference_terminal_policy_id: Literal[
        "fresh_kernel_terminal_policy:443b4c076ea4d694590fbafcd66d1c23681679bd24368ad43a354299c480fe3b"
    ] = REFERENCE_POLICY_ID
    dispatcher_input: Literal["Evidence"] = "Evidence"
    phase_input_allowed: Literal[False] = False
    terminal_kind_input_allowed: Literal[False] = False
    terminal_policy_input_allowed: Literal[False] = False
    caller_terminal_input_allowed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_binding(self) -> DispatcherBinding:
        if self.evidence_kinds != EVIDENCE_KINDS or self.binding_id != identity(
            self,
            "binding_id",
            "finance_v26_227_subsequent_action_dispatcher_binding:",
        ):
            raise ValueError("v26.227 Dispatcher Binding differs")
        return self


TerminalKind = Literal["first_response_abi_invalid", "first_action_reference_invalid"]


class DispatcherDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    evidence: Evidence
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    job_id: str = Field(min_length=1)
    job_ordinal: Literal[6, 22, 149]
    phase: Literal["subsequent_action"] = "subsequent_action"
    terminal_kind: TerminalKind
    terminal_policy_id: Literal[
        "fresh_kernel_terminal_policy:b5fb980fc0c80b2c72a964d538cf487e9a27403aff0ebe4e88ffb3b29847c04f",
        "fresh_kernel_terminal_policy:443b4c076ea4d694590fbafcd66d1c23681679bd24368ad43a354299c480fe3b",
    ]
    derivation_rule: Literal[
        "subsequent_action_exact_parser_rejection",
        "subsequent_action_parsed_reference_not_current",
    ]
    phase_was_input: Literal[False] = False
    terminal_kind_was_input: Literal[False] = False
    terminal_policy_was_input: Literal[False] = False
    caller_terminal_was_input: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_decision(self) -> DispatcherDecision:
        evidence = EVIDENCE_ADAPTER.validate_python(
            self.evidence.model_dump(mode="python", warnings=False)
        )
        if isinstance(evidence, ParserSubsequentActionEvidence):
            expected = (
                PARSER_TERMINAL,
                PARSER_POLICY_ID,
                "subsequent_action_exact_parser_rejection",
            )
        else:
            expected = (
                REFERENCE_TERMINAL,
                REFERENCE_POLICY_ID,
                "subsequent_action_parsed_reference_not_current",
            )
        if (
            self.evidence_sha256 != canonical_sha256(evidence)
            or self.job_id != evidence.job_id
            or self.job_ordinal != evidence.job_ordinal
            or (self.terminal_kind, self.terminal_policy_id, self.derivation_rule) != expected
            or self.decision_id
            != identity(
                self,
                "decision_id",
                "finance_v26_227_subsequent_action_dispatcher_decision:",
            )
        ):
            raise ValueError("v26.227 Dispatcher Decision differs")
        return self


LayerKind = Literal["raw", "result", "trace", "outcome", "checkpoint"]


class LayerArtifact(FrozenModel):
    artifact_id: str = Field(min_length=1)
    layer_kind: LayerKind
    external_authorization_id: str = Field(min_length=1)
    v226_freeze_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    host_failure_row_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    dispatcher_decision_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    job_ordinal: Literal[6, 22, 149]
    terminal_kind: TerminalKind
    parent_artifact_id: str | None = None
    payload: dict[str, Any]
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    relative_path: str = Field(min_length=1)
    persisted_sequence: int = Field(ge=0, le=4)
    historical_v226_artifact: Literal[False] = False
    formal_empirical_row: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_artifact(self) -> LayerArtifact:
        sequence = LAYER_KINDS.index(self.layer_kind)
        safe_job = sha(self.job_id.encode("utf-8"))
        expected_path = (
            f"replay_checkpoints/job_{self.job_ordinal:03d}.json"
            if self.layer_kind == "checkpoint"
            else f"replay_evidence/{self.layer_kind}/{safe_job}.json"
        )
        expected_payload_parent = self.payload.get("parent_artifact_id")
        if (
            self.persisted_sequence != sequence
            or self.relative_path != expected_path
            or not _safe_relative_path(self.relative_path)
            or (self.layer_kind == "raw") != (self.parent_artifact_id is None)
            or expected_payload_parent != self.parent_artifact_id
            or self.payload.get("job_id") != self.job_id
            or self.payload.get("job_ordinal") != self.job_ordinal
            or self.payload.get("terminal_kind") != self.terminal_kind
            or self.payload.get("evidence_id") != self.evidence_id
            or self.payload.get("dispatcher_decision_id") != self.dispatcher_decision_id
            or self.payload_sha256 != canonical_sha256(self.payload)
            or self.artifact_id
            != identity(
                self,
                "artifact_id",
                "finance_v26_227_replay_layer_artifact:",
            )
        ):
            raise ValueError("v26.227 fresh replay Layer Artifact differs")
        return self


class FiveLayerArtifacts(FrozenModel):
    chain_id: str = Field(min_length=1)
    raw: LayerArtifact
    result: LayerArtifact
    trace: LayerArtifact
    outcome: LayerArtifact
    checkpoint: LayerArtifact
    exact_layer_count: Literal[5] = 5
    actual_byte_match_count: Literal[5] = 5
    historical_v226_write_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_chain(self) -> FiveLayerArtifacts:
        layers = (self.raw, self.result, self.trace, self.outcome, self.checkpoint)
        common = tuple(
            (
                item.external_authorization_id,
                item.v226_freeze_id,
                item.source_identity_id,
                item.host_failure_row_id,
                item.evidence_id,
                item.dispatcher_decision_id,
                item.job_id,
                item.job_ordinal,
                item.terminal_kind,
            )
            for item in layers
        )
        if (
            tuple(item.layer_kind for item in layers) != LAYER_KINDS
            or tuple(item.persisted_sequence for item in layers) != tuple(range(5))
            or tuple(item.parent_artifact_id for item in layers)
            != (None,) + tuple(item.artifact_id for item in layers[:-1])
            or len({item.artifact_id for item in layers}) != 5
            or len(set(common)) != 1
            or self.chain_id
            != identity(
                self,
                "chain_id",
                "finance_v26_227_replay_five_layer_chain:",
            )
        ):
            raise ValueError("v26.227 Raw -> Result -> Trace -> Outcome -> checkpoint differs")
        return self


class ControlRow(FrozenModel):
    control_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v226_freeze_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    host_failure: HostFailureRow
    evidence: Evidence
    dispatcher_decision: DispatcherDecision
    five_layers: FiveLayerArtifacts
    replay_observed_record_count: int = Field(ge=2, le=3)
    expected_terminal_used_only_after_dispatch: Literal[True] = True
    caller_terminal_argument_count: Literal[0] = 0
    historical_v226_write_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_control(self) -> ControlRow:
        evidence = EVIDENCE_ADAPTER.validate_python(
            self.evidence.model_dump(mode="python", warnings=False)
        )
        record_payloads = tuple(self.host_failure.public_payloads)
        record_hashes = tuple(self.host_failure.public_payload_sha256s)
        invocation_hashes = tuple(
            v209_models.ExecutableInvocationRecord.model_validate(item).public_response_sha256
            for item in evidence.invocation_records
        )
        expected_kind = self.host_failure.expected_evidence_kind
        expected_terminal = (
            PARSER_TERMINAL
            if isinstance(evidence, ParserSubsequentActionEvidence)
            else REFERENCE_TERMINAL
        )
        layers = self.five_layers.raw
        if (
            evidence.evidence_kind != expected_kind
            or evidence.external_authorization_id != self.external_authorization_id
            or evidence.v226_freeze_id != self.v226_freeze_id
            or evidence.source_identity_id != self.source_identity_id
            or evidence.host_failure_row_id != self.host_failure.row_id
            or evidence.job_id != self.host_failure.job_id
            or evidence.job_ordinal != self.host_failure.job_ordinal
            or len(evidence.invocation_records) != len(record_payloads)
            or invocation_hashes != record_hashes
            or evidence.public_payload != record_payloads[-1]
            or evidence.public_payload_sha256 != record_hashes[-1]
            or self.host_failure.v226_freeze_id != self.v226_freeze_id
            or self.dispatcher_decision.dispatcher_binding_id != self.dispatcher_binding_id
            or self.dispatcher_decision.evidence.evidence_id != evidence.evidence_id
            or self.dispatcher_decision.evidence_sha256 != canonical_sha256(evidence)
            or self.dispatcher_decision.terminal_kind != expected_terminal
            or self.replay_observed_record_count != len(evidence.invocation_records)
            or layers.external_authorization_id != self.external_authorization_id
            or layers.v226_freeze_id != self.v226_freeze_id
            or layers.source_identity_id != self.source_identity_id
            or layers.host_failure_row_id != self.host_failure.row_id
            or layers.evidence_id != evidence.evidence_id
            or layers.dispatcher_decision_id != self.dispatcher_decision.decision_id
            or layers.job_id != evidence.job_id
            or layers.job_ordinal != evidence.job_ordinal
            or layers.terminal_kind != expected_terminal
            or self.control_id
            != identity(
                self,
                "control_id",
                "finance_v26_227_positive_control_row:",
            )
        ):
            raise ValueError("v26.227 positive Control Row differs")
        return self


class ControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v226_freeze_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    controls: tuple[ControlRow, ...] = Field(min_length=3, max_length=3)
    exact_host_failure_count: Literal[3] = 3
    parser_control_count: Literal[2] = 2
    reference_control_count: Literal[1] = 1
    derived_terminal_count: Literal[3] = 3
    five_layer_artifact_count: Literal[15] = 15
    exception_escape_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ControlAudit:
        if (
            tuple(item.host_failure.job_ordinal for item in self.controls) != HOST_FAILURE_ORDINALS
            or len({item.host_failure.job_id for item in self.controls}) != 3
            or sum(
                isinstance(item.evidence, ParserSubsequentActionEvidence) for item in self.controls
            )
            != 2
            or sum(
                isinstance(item.evidence, ReferenceSubsequentActionEvidence)
                for item in self.controls
            )
            != 1
            or any(
                item.external_authorization_id != self.external_authorization_id
                or item.v226_freeze_id != self.v226_freeze_id
                or item.source_identity_id != self.source_identity_id
                or item.dispatcher_binding_id != self.dispatcher_binding_id
                for item in self.controls
            )
            or self.audit_id != identity(self, "audit_id", "finance_v26_227_control_audit:")
        ):
            raise ValueError("v26.227 positive Control Audit differs")
        return self


class NegativeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v226_freeze_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    control_names: tuple[str, ...] = NEGATIVE_CONTROL_NAMES
    attempted_count: Literal[8] = 8
    rejected_count: Literal[8] = 8
    accepted_count: Literal[0] = 0
    rejected_before_raw_write_count: Literal[8] = 8
    fully_rehashed_attack_count: Literal[1] = 1
    fully_rehashed_five_layer_identity_count: Literal[5] = 5
    historical_v226_write_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_audit(self) -> NegativeAudit:
        if self.control_names != NEGATIVE_CONTROL_NAMES or self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_227_negative_audit:",
        ):
            raise ValueError("v26.227 Negative Audit differs")
        return self


class ScopeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v226_freeze_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    control_audit_id: str = Field(min_length=1)
    negative_audit_id: str = Field(min_length=1)
    exact_replayed_host_failure_count: Literal[3] = 3
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    provider_client_constructions: Literal[0] = 0
    historical_v226_artifact_writes: Literal[0] = 0
    historical_outcome_backfills: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    online_authorizations_created: Literal[0] = 0
    qa_reads: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ScopeAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_227_scope_audit:",
        ):
            raise ValueError("v26.227 Scope Audit differs")
        return self


GateName = Literal[
    "G0_EXTERNAL_SCOPE_AND_V26_226_FREEZE",
    "G1_EXACT_THREE_HOST_FAILURE_SOURCE_ROWS",
    "G2_COMPLETE_INVOCATION_PREFIX_BINDING",
    "G3_SUBSEQUENT_ACTION_PARSER_EVIDENCE",
    "G4_SUBSEQUENT_ACTION_REFERENCE_EVIDENCE",
    "G5_DERIVED_TERMINAL_AND_FIVE_LAYER_CLOSURE",
    "G6_NEGATIVE_CONTROLS",
    "G7_ZERO_PROVIDER_SCOPE_BOUNDARY",
]


class Gate(FrozenModel):
    gate_id: str = Field(min_length=1)
    gate_name: GateName
    evidence_id: str = Field(min_length=1)
    passed: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_gate(self) -> Gate:
        if self.gate_id != identity(
            self,
            "gate_id",
            "finance_v26_227_evidence_domain_gate:",
        ):
            raise ValueError("v26.227 Gate differs")
        return self


class GateEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    gates: tuple[Gate, ...] = Field(min_length=8, max_length=8)
    passed_count: Literal[8] = 8
    failed_count: Literal[0] = 0
    all_gates_passed: Literal[True] = True
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_evaluation(self) -> GateEvaluation:
        if tuple(
            item.gate_name for item in self.gates
        ) != GATE_NAMES or self.evaluation_id != identity(
            self,
            "evaluation_id",
            "finance_v26_227_gate_evaluation:",
        ):
            raise ValueError("v26.227 Gate Evaluation differs")
        return self


class Decision(FrozenModel):
    decision_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v226_freeze_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    control_audit_id: str = Field(min_length=1)
    negative_audit_id: str = Field(min_length=1)
    scope_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    decision: Literal[
        "subsequent_action_parser_reference_evidence_domain_closed_for_three_v26_226_host_failures_independent_audit_required_online_execution_blocked"
    ] = DECISION_VALUE
    v26_226_historical_completion_changed: Literal[False] = False
    provider_failure_terminalization_completed: Literal[False] = False
    independent_audit_required: Literal[True] = True
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_decision(self) -> Decision:
        if self.decision_id != identity(
            self,
            "decision_id",
            "finance_v26_227_decision:",
        ):
            raise ValueError("v26.227 Decision differs")
        return self


class Transition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    status: Literal["PASSED_PREFLIGHT_INDEPENDENT_AUDIT_REQUIRED"] = (
        "PASSED_PREFLIGHT_INDEPENDENT_AUDIT_REQUIRED"
    )
    next_stage: Literal[
        "fresh_exact_v209_subsequent_action_parser_reference_evidence_domain_closure_independent_audit_only"
    ] = NEXT_STAGE
    provider_failure_authority_remains_separate: Literal[True] = True
    fresh_online_authorization_required_after_independent_audit: Literal[True] = True
    provider_execution_authorized: Literal[False] = False
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_transition(self) -> Transition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_227_transition:",
        ):
            raise ValueError("v26.227 Transition differs")
        return self


class Report(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v226_freeze_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    control_audit_id: str = Field(min_length=1)
    negative_audit_id: str = Field(min_length=1)
    scope_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    decision: Literal[
        "subsequent_action_parser_reference_evidence_domain_closed_for_three_v26_226_host_failures_independent_audit_required_online_execution_blocked"
    ] = DECISION_VALUE
    exact_source_host_failure_count: Literal[3] = 3
    parser_evidence_count: Literal[2] = 2
    reference_evidence_count: Literal[1] = 1
    derived_terminal_count: Literal[3] = 3
    fresh_five_layer_artifact_count: Literal[15] = 15
    historical_v26_226_terminal_added_count: Literal[0] = 0
    unbound_provider_failure_count_remaining: Literal[33] = 33
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_report(self) -> Report:
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_227_report:",
        ):
            raise ValueError("v26.227 Report differs")
        return self


class ArtifactMember(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_member(self) -> ArtifactMember:
        if not _safe_relative_path(self.relative_path):
            raise ValueError("v26.227 artifact member path is unsafe")
        return self


class ArtifactManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    manifest_relative_path: Literal["artifact_manifest.json"] = "artifact_manifest.json"
    members: tuple[ArtifactMember, ...] = Field(min_length=1)
    file_count: int = Field(gt=0)
    total_member_bytes: int = Field(gt=0)
    artifact_root: str = Field(min_length=1)
    self_excluding: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: Literal["fresh_exact_v209_subsequent_action_evidence_domain_closure.v1"] = (
        SCHEMA_VERSION
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> ArtifactManifest:
        paths = tuple(item.relative_path for item in self.members)
        member_payloads = tuple(
            item.model_dump(mode="json", warnings=False) for item in self.members
        )
        if (
            paths != tuple(sorted(set(paths)))
            or self.manifest_relative_path in paths
            or self.file_count != len(self.members)
            or self.total_member_bytes != sum(item.byte_count for item in self.members)
            or self.artifact_root
            != canonical_hash(
                member_payloads,
                prefix="finance_v26_227_artifact_root:",
            )
            or self.manifest_id
            != identity(
                self,
                "manifest_id",
                "finance_v26_227_artifact_manifest:",
            )
        ):
            raise ValueError("v26.227 self-excluding Artifact Manifest differs")
        return self


def artifact_manifest(run_id: str, payloads: Mapping[str, bytes]) -> ArtifactManifest:
    if "artifact_manifest.json" in payloads:
        raise ValueError("artifact_manifest.json must be self-excluded")
    members = tuple(
        ArtifactMember(
            relative_path=path,
            sha256=sha(payload),
            byte_count=len(payload),
        )
        for path, payload in sorted(payloads.items())
    )
    member_payloads = tuple(item.model_dump(mode="json", warnings=False) for item in members)
    return make_identity(
        ArtifactManifest,
        {
            "run_id": run_id,
            "members": members,
            "file_count": len(members),
            "total_member_bytes": sum(item.byte_count for item in members),
            "artifact_root": canonical_hash(
                member_payloads,
                prefix="finance_v26_227_artifact_root:",
            ),
        },
        field="manifest_id",
        prefix="finance_v26_227_artifact_manifest:",
    )


__all__ = [
    "ArtifactManifest",
    "ArtifactMember",
    "ControlAudit",
    "ControlRow",
    "DECISION_VALUE",
    "Decision",
    "DispatcherBinding",
    "DispatcherDecision",
    "EVIDENCE_ADAPTER",
    "EVIDENCE_KINDS",
    "Evidence",
    "ExternalAuthorization",
    "FiveLayerArtifacts",
    "FrozenModel",
    "GATE_NAMES",
    "Gate",
    "GateEvaluation",
    "HOST_FAILURE_ORDINALS",
    "HostFailureRow",
    "LAYER_KINDS",
    "LayerArtifact",
    "NEGATIVE_CONTROL_NAMES",
    "NEXT_STAGE",
    "NegativeAudit",
    "OBSERVED_EVIDENCE_ADAPTER",
    "ObservedEvidence",
    "ParserSubsequentActionEvidence",
    "ReferenceSubsequentActionEvidence",
    "Report",
    "SCHEMA_VERSION",
    "ScopeAudit",
    "SourceIdentity",
    "SourceMember",
    "Transition",
    "V226Freeze",
    "artifact_manifest",
    "canonical_bytes",
    "canonical_sha256",
    "identity",
    "make_identity",
    "sha",
]
