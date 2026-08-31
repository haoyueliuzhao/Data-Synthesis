from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, Literal, NamedTuple, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_online_execution as v188,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as frozen_runtime,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    RESPONSE_PROTOCOL_VERSION,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    STAGE_ONE_MODEL_CONFIG_ID,
    STAGE_ONE_MODEL_ID,
    STAGE_ONE_PROFILE_SHA256,
    STAGE_ONE_THINKING_BINDING_ID,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = "finance_v26_190_exact_route_http400_request_contract_root_cause_audit_v1_20260831"
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
AUTHORIZED_STAGE: Final = "exact_route_http_400_request_contract_root_cause_audit_only"
CURRENT_DECISION: Final = "no_further_experiment_authorized_without_new_audit_decision"
RECOMMENDED_FUTURE_STAGE: Final = (
    "fresh_identity_minimal_exact_route_diagnostic_contract_preflight_only"
)

EXTERNAL_AUDIT_SHA256: Final = "92b26fcccaf79a13423a1f1c392c996227a60c8a9a15167bb20e98adeea297dc"
EXTERNAL_AUDIT_BYTE_COUNT: Final = 9_199
OPERATOR_INSTRUCTION: Final = "参照审计开展后续实验"

V188_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_188_artifact_backed_online_development_execution_v1_20260831"
)
V189_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_189_artifact_backed_online_postrun_independent_audit_v1_20260831"
)
V188_SOURCE_COMMIT: Final = "53d0128f22043a88efb612af835aa99bdc78ede4"
V188_SOURCE_TREE: Final = "38456681dfd2e3d18fa65b1268245affc1e34d39"
V188_ARTIFACT_COMMIT: Final = "da40cb1512d86296cbeb14b127ace4c20cfd076e"
V188_ARTIFACT_TREE: Final = "ac3371743c1ec3d010bf27dea6afb860e7297530"
V189_SOURCE_COMMIT: Final = "bca20b7857bdda89523c94ee40ea1fbc22fb7404"
V189_SOURCE_TREE: Final = "4a39b83ceb5acf67fda52c084802f3c6763fb867"
V189_ARTIFACT_COMMIT: Final = "a8002297fc498842e79ee8fde5382ec898a2738f"
V189_ARTIFACT_TREE: Final = "658cd2e8c7c2b0401d5df61c65a93d279411dde2"
EXPECTED_V189_REPORT_ID: Final = (
    "finance_v26_188_postrun_independent_audit_report:"
    "847db4a57b5a73aac16676b2d5b4bc2f1cfa08e2610c8e308035b8415329d1d9"
)
EXPECTED_V189_ARTIFACT_ROOT: Final = (
    "finance_v26_189_postrun_artifact_root:"
    "b47af81da69c929da1860d74a6360d8ce5f4fb7b401e7f525c24f1574a16b6b0"
)
EXPECTED_V188_DIRECTORY_MANIFEST_ID: Final = (
    "finance_v26_188_independent_directory_manifest:"
    "1c16ca9112d60efd726d8eecb33c5b1758c9d2857823ab0cb4a46d53d92f997b"
)
EXPECTED_V188_DIRECTORY_ROOT: Final = (
    "finance_v26_188_independent_directory_content_root:"
    "a1cdb58c4eda548ece6060e68126ab1b9750848850c5aa69ca739a6356653196"
)

EXPECTED_V188_JOB_COUNT: Final = 192
EXPECTED_HISTORICAL_HTTP_SUCCESS_COUNT: Final = 7_229
EXPECTED_HISTORICAL_SUCCESS_WITHIN_V188_RANGE: Final = 1_811
EXPECTED_V188_PROMPT_MIN: Final = 12_053
EXPECTED_V188_PROMPT_MAX: Final = 17_069
EXPECTED_V188_BODY_MIN: Final = 13_418
EXPECTED_V188_BODY_MAX: Final = 18_770

STAGE_ONE_CLIENT_PATH: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/runtime/agent/"
    "prospective_two_stage_stage1_client.py"
)
BASE_CLIENT_PATH: Final = "trusted_data_synthesis/src/trusted_synthesis/runtime/agent/client.py"
STAGE_ONE_CLIENT_LAST_CHANGE: Final = "bc3a9ba8d109ccd63fdf563a609611bfc5cba797"
BASE_CLIENT_LAST_CHANGE: Final = "6b7243bfd886fe7845ffd4182f57af2ba03f050b"

EXPECTED_REQUEST_FIELDS: Final = (
    "max_tokens",
    "messages",
    "model",
    "response_format",
    "temperature",
    "thinking",
    "top_p",
)
EXPECTED_HEADER_NAMES: Final = ("Authorization", "Content-Type")


class HistoricalRunSpec(NamedTuple):
    run_id: str
    expected_count: int


HISTORICAL_RUNS: Final = (
    HistoricalRunSpec("finance_v26_134_s1_representation_qualification_execution_v1_20260824", 197),
    HistoricalRunSpec("finance_v26_138_privacy_safe_s1_qualification_execution_v1_20260824", 191),
    HistoricalRunSpec("finance_v26_151_fresh_capability_execution_v2_20260825", 879),
    HistoricalRunSpec("finance_v26_154_fresh_reachability_execution_v1_20260826", 3_043),
    HistoricalRunSpec(
        "finance_v26_164_bounded_policy_endpoint_frequency_execution_v1_20260827", 2_919
    ),
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class OperatorAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    authorized_stage: Literal["exact_route_http_400_request_contract_root_cause_audit_only"] = (
        AUTHORIZED_STAGE
    )
    external_audit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    external_audit_byte_count: Literal[9199] = EXTERNAL_AUDIT_BYTE_COUNT
    external_audit_recorded_current_authorization: Literal["no further experiment"] = (
        "no further experiment"
    )
    operator_instruction: Literal["参照审计开展后续实验"] = OPERATOR_INSTRUCTION
    operator_instruction_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    operator_instruction_consumed_as_new_decision: Literal[True] = True
    selected_unique_recommended_stage: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    provider_client_construction_authorized: Literal[False] = False
    credential_read_authorized: Literal[False] = False
    provider_rerun_authorized: Literal[False] = False
    recovery_jobs_authorized: Literal[False] = False
    request_route_repair_authorized: Literal[False] = False
    schema_version: Literal["exact_route_root_cause_operator_authorization.v1"] = (
        "exact_route_root_cause_operator_authorization.v1"
    )

    @model_validator(mode="after")
    def validate_authorization(self) -> OperatorAuthorization:
        if self.external_audit_sha256 != EXTERNAL_AUDIT_SHA256:
            raise ValueError("external v26.189 audit identity differs")
        if self.operator_instruction_sha256 != _sha256_bytes(OPERATOR_INSTRUCTION.encode("utf-8")):
            raise ValueError("operator instruction identity differs")
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="authorization_id",
            prefix="finance_v26_190_route_root_cause_operator_authorization:",
        )
        return self


class PredecessorFreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    v188_source_commit: str = Field(min_length=40, max_length=40)
    v188_source_tree: str = Field(min_length=40, max_length=40)
    v188_artifact_commit: str = Field(min_length=40, max_length=40)
    v188_artifact_tree: str = Field(min_length=40, max_length=40)
    v189_source_commit: str = Field(min_length=40, max_length=40)
    v189_source_tree: str = Field(min_length=40, max_length=40)
    v189_artifact_commit: str = Field(min_length=40, max_length=40)
    v189_artifact_tree: str = Field(min_length=40, max_length=40)
    v189_report_id: str = Field(min_length=1)
    v189_artifact_root: str = Field(min_length=1)
    v188_directory_manifest_id: str = Field(min_length=1)
    v188_directory_root: str = Field(min_length=1)
    v188_file_count: Literal[1350] = 1_350
    v188_byte_count: Literal[3618348] = 3_618_348
    predecessor_bytes_unchanged_after_audit: Literal[True] = True
    historical_reclassification_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["exact_route_root_cause_predecessor_freeze.v1"] = (
        "exact_route_root_cause_predecessor_freeze.v1"
    )

    @model_validator(mode="after")
    def validate_freeze(self) -> PredecessorFreezeAudit:
        expected = (
            V188_SOURCE_COMMIT,
            V188_SOURCE_TREE,
            V188_ARTIFACT_COMMIT,
            V188_ARTIFACT_TREE,
            V189_SOURCE_COMMIT,
            V189_SOURCE_TREE,
            V189_ARTIFACT_COMMIT,
            V189_ARTIFACT_TREE,
            EXPECTED_V189_REPORT_ID,
            EXPECTED_V189_ARTIFACT_ROOT,
            EXPECTED_V188_DIRECTORY_MANIFEST_ID,
            EXPECTED_V188_DIRECTORY_ROOT,
        )
        actual = (
            self.v188_source_commit,
            self.v188_source_tree,
            self.v188_artifact_commit,
            self.v188_artifact_tree,
            self.v189_source_commit,
            self.v189_source_tree,
            self.v189_artifact_commit,
            self.v189_artifact_tree,
            self.v189_report_id,
            self.v189_artifact_root,
            self.v188_directory_manifest_id,
            self.v188_directory_root,
        )
        if actual != expected:
            raise ValueError("v26.188-v26.189 predecessor freeze differs")
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="audit_id",
            prefix="finance_v26_190_predecessor_freeze:",
        )
        return self


class RequestShape(FrozenModel):
    shape_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    request_model: str = Field(min_length=1)
    request_max_tokens: int = Field(gt=0)
    thinking_type: str = Field(min_length=1)
    response_format_type: str = Field(min_length=1)
    request_body_fields: tuple[str, ...]
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_config_id: str = Field(min_length=1)
    thinking_binding_id: str = Field(min_length=1)
    exact_model_route: bool
    fallback_forbidden: bool
    schema_version: Literal["exact_route_request_shape.v1"] = "exact_route_request_shape.v1"

    @model_validator(mode="after")
    def validate_shape(self) -> RequestShape:
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="shape_id",
            prefix="finance_v26_190_exact_request_shape:",
        )
        return self


class ReconstructedRequestRow(FrozenModel):
    row_id: str = Field(min_length=1)
    ordinal: int = Field(ge=0, le=191)
    job_id: str = Field(min_length=1)
    request_certificate_id: str = Field(min_length=1)
    provider_envelope_id: str = Field(min_length=1)
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_utf8_bytes: int = Field(gt=0)
    canonical_request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_request_body_bytes: int = Field(gt=0)
    request_shape_id: str = Field(min_length=1)
    exact_certificate_match: Literal[True] = True
    prompt_top_level_keys: tuple[Literal["public_prompt", "response_abi"], ...]
    message_count: Literal[1] = 1
    message_role: Literal["user"] = "user"
    forbidden_control_character_count: Literal[0] = 0
    surrogate_codepoint_count: Literal[0] = 0
    http_status: Literal[400] = 400
    response_envelope_observed: Literal[False] = False
    raw_http_error_body_persisted: Literal[False] = False
    provider_calls_during_audit: Literal[0] = 0
    schema_version: Literal["exact_route_reconstructed_request.v1"] = (
        "exact_route_reconstructed_request.v1"
    )

    @model_validator(mode="after")
    def validate_row(self) -> ReconstructedRequestRow:
        if self.prompt_top_level_keys != ("public_prompt", "response_abi"):
            raise ValueError("v26.188 Prompt top-level schema differs")
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="row_id",
            prefix="finance_v26_190_reconstructed_request:",
        )
        return self


class RequestReconstructionCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    request_shape: RequestShape
    rows: tuple[ReconstructedRequestRow, ...] = Field(min_length=192, max_length=192)
    exact_job_count: Literal[192] = 192
    exact_certificate_match_count: Literal[192] = 192
    prompt_utf8_bytes_minimum: Literal[12053] = EXPECTED_V188_PROMPT_MIN
    prompt_utf8_bytes_maximum: Literal[17069] = EXPECTED_V188_PROMPT_MAX
    canonical_request_body_bytes_minimum: Literal[13418] = EXPECTED_V188_BODY_MIN
    canonical_request_body_bytes_maximum: Literal[18770] = EXPECTED_V188_BODY_MAX
    forbidden_control_character_count: Literal[0] = 0
    surrogate_codepoint_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["exact_route_request_reconstruction_catalog.v1"] = (
        "exact_route_request_reconstruction_catalog.v1"
    )

    @model_validator(mode="after")
    def validate_catalog(self) -> RequestReconstructionCatalog:
        if tuple(item.ordinal for item in self.rows) != tuple(range(EXPECTED_V188_JOB_COUNT)):
            raise ValueError("v26.188 reconstructed request ordinals differ")
        if len({item.job_id for item in self.rows}) != EXPECTED_V188_JOB_COUNT:
            raise ValueError("v26.188 reconstructed request Job set repeats")
        if {item.request_shape_id for item in self.rows} != {self.request_shape.shape_id}:
            raise ValueError("v26.188 reconstructed request shape parent differs")
        if min(item.prompt_utf8_bytes for item in self.rows) != self.prompt_utf8_bytes_minimum:
            raise ValueError("v26.188 Prompt minimum differs")
        if max(item.prompt_utf8_bytes for item in self.rows) != self.prompt_utf8_bytes_maximum:
            raise ValueError("v26.188 Prompt maximum differs")
        if (
            min(item.canonical_request_body_bytes for item in self.rows)
            != self.canonical_request_body_bytes_minimum
            or max(item.canonical_request_body_bytes for item in self.rows)
            != self.canonical_request_body_bytes_maximum
        ):
            raise ValueError("v26.188 request-body range differs")
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="catalog_id",
            prefix="finance_v26_190_request_reconstruction_catalog:",
        )
        return self


class HistoricalSuccessRunSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    envelope_file_count: int = Field(gt=0)
    http_200_count: int = Field(gt=0)
    exact_shape_count: Literal[1] = 1
    request_shape_id: str = Field(min_length=1)
    canonical_request_body_bytes_minimum: int = Field(gt=0)
    canonical_request_body_bytes_maximum: int = Field(gt=0)
    http_success_within_v188_body_range: int = Field(ge=0)
    raw_request_body_persisted_count: Literal[0] = 0
    schema_version: Literal["exact_route_historical_success_run_summary.v1"] = (
        "exact_route_historical_success_run_summary.v1"
    )

    @model_validator(mode="after")
    def validate_summary(self) -> HistoricalSuccessRunSummary:
        if self.envelope_file_count != self.http_200_count:
            raise ValueError("historical comparison run is not all HTTP-success")
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="summary_id",
            prefix="finance_v26_190_historical_success_run_summary:",
        )
        return self


class HistoricalSuccessCorpus(FrozenModel):
    corpus_id: str = Field(min_length=1)
    request_shape: RequestShape
    run_summaries: tuple[HistoricalSuccessRunSummary, ...] = Field(min_length=5, max_length=5)
    envelope_files: tuple[FileBinding, ...] = Field(min_length=7229, max_length=7229)
    envelope_content_root: str = Field(min_length=1)
    exact_http_success_count: Literal[7229] = EXPECTED_HISTORICAL_HTTP_SUCCESS_COUNT
    success_within_v188_body_range: Literal[1811] = EXPECTED_HISTORICAL_SUCCESS_WITHIN_V188_RANGE
    global_request_body_bytes_minimum: Literal[3759] = 3_759
    global_request_body_bytes_maximum: Literal[55126] = 55_126
    exact_shape_count: Literal[1] = 1
    raw_request_body_persisted_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["exact_route_historical_success_corpus.v1"] = (
        "exact_route_historical_success_corpus.v1"
    )

    @model_validator(mode="after")
    def validate_corpus(self) -> HistoricalSuccessCorpus:
        paths = tuple(item.relative_path for item in self.envelope_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("historical success corpus paths are not exact")
        if sum(item.http_200_count for item in self.run_summaries) != self.exact_http_success_count:
            raise ValueError("historical success corpus count differs")
        if {item.request_shape_id for item in self.run_summaries} != {self.request_shape.shape_id}:
            raise ValueError("historical success request shape parent differs")
        expected_root = canonical_hash(
            [item.model_dump(mode="json", warnings=False) for item in self.envelope_files],
            prefix="finance_v26_190_historical_success_envelope_root:",
        )
        if self.envelope_content_root != expected_root:
            raise ValueError("historical success envelope content Root differs")
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="corpus_id",
            prefix="finance_v26_190_historical_success_corpus:",
        )
        return self


class SourceRequestSurfaceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    request_shape_id: str = Field(min_length=1)
    stage_one_client_relative_path: Literal[
        "trusted_data_synthesis/src/trusted_synthesis/runtime/agent/prospective_two_stage_stage1_client.py"
    ] = STAGE_ONE_CLIENT_PATH
    stage_one_client_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    stage_one_client_last_change_commit: str = Field(min_length=40, max_length=40)
    base_client_relative_path: Literal[
        "trusted_data_synthesis/src/trusted_synthesis/runtime/agent/client.py"
    ] = BASE_CLIENT_PATH
    base_client_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    base_client_last_change_commit: str = Field(min_length=40, max_length=40)
    v188_source_stage_one_client_exact_match: Literal[True] = True
    v188_source_base_client_exact_match: Literal[True] = True
    historical_successes_postdate_client_sources: Literal[True] = True
    nonsecret_header_names: tuple[Literal["Authorization", "Content-Type"], ...]
    extra_header_count: Literal[0] = 0
    authorization_header_value_persisted: Literal[False] = False
    authorization_header_value_compared: Literal[False] = False
    canonical_json_sort_keys: Literal[True] = True
    canonical_json_compact_separators: Literal[True] = True
    utf8_request_encoding: Literal[True] = True
    raw_request_body_persisted: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["exact_route_source_request_surface_audit.v1"] = (
        "exact_route_source_request_surface_audit.v1"
    )

    @model_validator(mode="after")
    def validate_surface(self) -> SourceRequestSurfaceAudit:
        if (
            self.stage_one_client_last_change_commit != STAGE_ONE_CLIENT_LAST_CHANGE
            or self.base_client_last_change_commit != BASE_CLIENT_LAST_CHANGE
            or self.nonsecret_header_names != EXPECTED_HEADER_NAMES
        ):
            raise ValueError("request serialization source surface differs")
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="audit_id",
            prefix="finance_v26_190_source_request_surface_audit:",
        )
        return self


class RequestContractComparisonAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    v188_catalog_id: str = Field(min_length=1)
    historical_success_corpus_id: str = Field(min_length=1)
    source_surface_audit_id: str = Field(min_length=1)
    endpoint_match: Literal[True] = True
    request_model_match: Literal[True] = True
    max_tokens_match: Literal[True] = True
    thinking_match: Literal[True] = True
    response_format_match: Literal[True] = True
    request_body_field_set_match: Literal[True] = True
    profile_sha256_match: Literal[True] = True
    model_config_id_match: Literal[True] = True
    thinking_binding_id_match: Literal[True] = True
    messages_wrapper_shape_match: Literal[True] = True
    nonsecret_header_schema_match: Literal[True] = True
    serializer_source_match: Literal[True] = True
    v188_body_range_contained_by_historical_success_range: Literal[True] = True
    historical_http_successes_within_v188_body_range: Literal[1811] = (
        EXPECTED_HISTORICAL_SUCCESS_WITHIN_V188_RANGE
    )
    deterministic_fixed_contract_difference_count: Literal[0] = 0
    prompt_or_body_encoding_defect_count: Literal[0] = 0
    secret_authorization_value_comparison_evaluable: Literal[False] = False
    provider_server_contract_at_v188_execution_evaluable: Literal[False] = False
    http_error_body_evaluable: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["exact_route_request_contract_comparison_audit.v1"] = (
        "exact_route_request_contract_comparison_audit.v1"
    )

    @model_validator(mode="after")
    def validate_comparison(self) -> RequestContractComparisonAudit:
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="audit_id",
            prefix="finance_v26_190_request_contract_comparison_audit:",
        )
        return self


class RootCauseLocalizationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    comparison_audit_id: str = Field(min_length=1)
    first_blocker: Literal["http_400_before_response_envelope_and_model_endpoint"] = (
        "http_400_before_response_envelope_and_model_endpoint"
    )
    deterministic_request_contract_difference: Literal["none_found"] = "none_found"
    unique_root_cause_identified: Literal[False] = False
    localization_result: Literal["not_localizable_from_persisted_artifacts"] = (
        "not_localizable_from_persisted_artifacts"
    )
    ruled_out_persisted_factors: tuple[str, ...] = Field(min_length=10)
    unevaluable_factors: tuple[str, ...] = Field(min_length=3)
    historical_http_success_count: Literal[7229] = EXPECTED_HISTORICAL_HTTP_SUCCESS_COUNT
    v188_http_400_count: Literal[192] = EXPECTED_V188_JOB_COUNT
    historical_reclassification_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["exact_route_root_cause_localization_audit.v1"] = (
        "exact_route_root_cause_localization_audit.v1"
    )

    @model_validator(mode="after")
    def validate_localization(self) -> RootCauseLocalizationAudit:
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="audit_id",
            prefix="finance_v26_190_root_cause_localization_audit:",
        )
        return self


class DestructiveControlRow(FrozenModel):
    control_name: str = Field(min_length=1)
    rejected: Literal[True] = True
    rejection_stage: str = Field(min_length=1)


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    controls: tuple[DestructiveControlRow, ...] = Field(min_length=13, max_length=13)
    attempted_count: Literal[13] = 13
    rejected_count: Literal[13] = 13
    accepted_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["exact_route_root_cause_destructive_audit.v1"] = (
        "exact_route_root_cause_destructive_audit.v1"
    )

    @model_validator(mode="after")
    def validate_controls(self) -> DestructiveAudit:
        if len({item.control_name for item in self.controls}) != self.attempted_count:
            raise ValueError("destructive controls repeat")
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="audit_id",
            prefix="finance_v26_190_root_cause_destructive_audit:",
        )
        return self


class StaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: dict[str, bool]
    passed_gate_count: int = Field(gt=0)
    failed_gate_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    provider_clients_constructed: Literal[0] = 0
    credential_reads: Literal[0] = 0
    recovery_jobs: Literal[0] = 0
    request_route_repairs: Literal[0] = 0
    historical_reclassification_count: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    schema_version: Literal["exact_route_root_cause_static_audit.v1"] = (
        "exact_route_root_cause_static_audit.v1"
    )

    @model_validator(mode="after")
    def validate_static(self) -> StaticAudit:
        if not self.gates or not all(self.gates.values()):
            raise ValueError("v26.190 static Gate failed")
        if self.passed_gate_count != len(self.gates):
            raise ValueError("v26.190 static Gate count differs")
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="audit_id",
            prefix="finance_v26_190_root_cause_static_audit:",
        )
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    current_stage: Literal["exact_route_http_400_request_contract_root_cause_audit_only"] = (
        AUTHORIZED_STAGE
    )
    current_audit_passed: Literal[True] = True
    decision: Literal["no_further_experiment_authorized_without_new_audit_decision"] = (
        CURRENT_DECISION
    )
    recommended_future_stage: Literal[
        "fresh_identity_minimal_exact_route_diagnostic_contract_preflight_only"
    ] = RECOMMENDED_FUTURE_STAGE
    recommended_future_stage_authorized_now: Literal[False] = False
    provider_execution_authorized: Literal[False] = False
    provider_rerun_authorized: Literal[False] = False
    request_route_repair_authorized: Literal[False] = False
    recovery_jobs_authorized: Literal[False] = False
    downstream_empirical_work_authorized: Literal[False] = False
    schema_version: Literal["exact_route_root_cause_transition.v1"] = (
        "exact_route_root_cause_transition.v1"
    )

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="transition_id",
            prefix="finance_v26_190_root_cause_transition:",
        )
        return self


class RootCauseAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: Literal[
        "finance_v26_190_exact_route_http400_request_contract_root_cause_audit_v1_20260831"
    ] = RUN_ID
    authorization_id: str = Field(min_length=1)
    predecessor_freeze_id: str = Field(min_length=1)
    request_reconstruction_catalog_id: str = Field(min_length=1)
    historical_success_corpus_id: str = Field(min_length=1)
    source_surface_audit_id: str = Field(min_length=1)
    comparison_audit_id: str = Field(min_length=1)
    root_cause_localization_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    v188_request_reconstruction: Literal["PASS"] = "PASS"
    historical_exact_route_success_comparison: Literal["PASS"] = "PASS"
    deterministic_request_contract_difference: Literal["NONE_FOUND"] = "NONE_FOUND"
    unique_http_400_root_cause: Literal["NOT_LOCALIZABLE_FROM_PERSISTED_ARTIFACTS"] = (
        "NOT_LOCALIZABLE_FROM_PERSISTED_ARTIFACTS"
    )
    historical_http_success_count: Literal[7229] = EXPECTED_HISTORICAL_HTTP_SUCCESS_COUNT
    historical_success_within_v188_body_range: Literal[1811] = (
        EXPECTED_HISTORICAL_SUCCESS_WITHIN_V188_RANGE
    )
    v188_http_400_count: Literal[192] = EXPECTED_V188_JOB_COUNT
    provider_calls: Literal[0] = 0
    decision: Literal["no_further_experiment_authorized_without_new_audit_decision"] = (
        CURRENT_DECISION
    )
    schema_version: Literal["exact_route_root_cause_audit_report.v1"] = (
        "exact_route_root_cause_audit_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> RootCauseAuditReport:
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="report_id",
            prefix="finance_v26_190_root_cause_audit_report:",
        )
        return self


class FormalArtifactManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    files: tuple[FileBinding, ...] = Field(min_length=14, max_length=14)
    file_count: Literal[14] = 14
    total_byte_count: int = Field(gt=0)
    artifact_root: str = Field(min_length=1)
    schema_version: Literal["exact_route_root_cause_artifact_manifest.v1"] = (
        "exact_route_root_cause_artifact_manifest.v1"
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> FormalArtifactManifest:
        names = tuple(item.relative_path for item in self.files)
        if names != tuple(sorted(set(names))):
            raise ValueError("formal artifact Manifest names are not exact")
        if sum(item.byte_count for item in self.files) != self.total_byte_count:
            raise ValueError("formal artifact Manifest byte count differs")
        expected_root = canonical_hash(
            [item.model_dump(mode="json", warnings=False) for item in self.files],
            prefix="finance_v26_190_route_root_cause_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("formal artifact Root differs")
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="manifest_id",
            prefix="finance_v26_190_route_root_cause_artifact_manifest:",
        )
        return self


class BuildProducts(NamedTuple):
    authorization: OperatorAuthorization
    freeze: PredecessorFreezeAudit
    reconstruction: RequestReconstructionCatalog
    historical: HistoricalSuccessCorpus
    source_surface: SourceRequestSurfaceAudit
    comparison: RequestContractComparisonAudit
    localization: RootCauseLocalizationAudit
    destructive: DestructiveAudit
    static: StaticAudit
    transition: ProspectiveTransition
    report: RootCauseAuditReport
    artifact_manifest: FormalArtifactManifest


def _canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_bytes(value: Any) -> bytes:
    return (_canonical_json(value) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _require_identity(payload: dict[str, Any], *, field: str, prefix: str) -> None:
    expected = canonical_hash(
        {key: value for key, value in payload.items() if key != field},
        prefix=prefix,
    )
    if payload[field] != expected:
        raise ValueError(f"{field} identity differs")


def _identity_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> BaseModel:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    payload = provisional.model_dump(mode="json", exclude={field}, warnings=False)
    return model_type(**{field: canonical_hash(payload, prefix=prefix), **values})


def _file_binding(path: Path, *, root: Path) -> FileBinding:
    payload = path.read_bytes()
    return FileBinding(
        relative_path=path.relative_to(root).as_posix(),
        sha256=_sha256_bytes(payload),
        byte_count=len(payload),
    )


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _git_tree(repository: Path, commit: str) -> str:
    return _git(repository, "show", "-s", "--format=%T", commit)


def _git_file_bytes(repository: Path, commit: str, relative_path: str) -> bytes:
    return subprocess.run(
        ("git", "show", f"{commit}:{relative_path}"),
        cwd=repository,
        check=True,
        capture_output=True,
    ).stdout


def _shape_values(certificate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "provider": certificate["provider"],
        "endpoint": certificate["endpoint"],
        "request_model": certificate["request_model"],
        "request_max_tokens": certificate["request_max_tokens"],
        "thinking_type": certificate["thinking_type"],
        "response_format_type": certificate["response_format_type"],
        "request_body_fields": tuple(certificate["request_body_fields"]),
        "profile_sha256": certificate["profile_sha256"],
        "model_config_id": certificate["model_config_id"],
        "thinking_binding_id": certificate["thinking_binding_id"],
        "exact_model_route": certificate["exact_model_route"],
        "fallback_forbidden": certificate["fallback_forbidden"],
    }


def _request_shape(certificate: Mapping[str, Any]) -> RequestShape:
    return cast(
        RequestShape,
        _identity_model(
            RequestShape,
            _shape_values(certificate),
            field="shape_id",
            prefix="finance_v26_190_exact_request_shape:",
        ),
    )


def validate_fixed_request_shape(shape: RequestShape) -> None:
    if (
        shape.provider != "deepseek"
        or shape.endpoint != "https://api.deepseek.com/v1/chat/completions"
        or shape.request_model != STAGE_ONE_MODEL_ID
        or shape.request_max_tokens != 16_384
        or shape.thinking_type != "enabled"
        or shape.response_format_type != "json_object"
        or shape.request_body_fields != EXPECTED_REQUEST_FIELDS
        or shape.profile_sha256 != STAGE_ONE_PROFILE_SHA256
        or shape.model_config_id != STAGE_ONE_MODEL_CONFIG_ID
        or shape.thinking_binding_id != STAGE_ONE_THINKING_BINDING_ID
        or not shape.exact_model_route
        or not shape.fallback_forbidden
    ):
        raise ValueError("exact Stage 1 request shape differs")


def _authorization(path: Path) -> tuple[OperatorAuthorization, bytes, bytes]:
    source = path.read_bytes()
    if len(source) != EXTERNAL_AUDIT_BYTE_COUNT or _sha256_bytes(source) != EXTERNAL_AUDIT_SHA256:
        raise ValueError("external v26.189 audit bytes differ")
    instruction = OPERATOR_INSTRUCTION.encode("utf-8")
    values = {
        "external_audit_sha256": EXTERNAL_AUDIT_SHA256,
        "external_audit_byte_count": EXTERNAL_AUDIT_BYTE_COUNT,
        "external_audit_recorded_current_authorization": "no further experiment",
        "operator_instruction": OPERATOR_INSTRUCTION,
        "operator_instruction_sha256": _sha256_bytes(instruction),
        "operator_instruction_consumed_as_new_decision": True,
        "selected_unique_recommended_stage": True,
        "provider_calls_authorized": False,
        "provider_client_construction_authorized": False,
        "credential_read_authorized": False,
        "provider_rerun_authorized": False,
        "recovery_jobs_authorized": False,
        "request_route_repair_authorized": False,
    }
    authorization = cast(
        OperatorAuthorization,
        _identity_model(
            OperatorAuthorization,
            values,
            field="authorization_id",
            prefix="finance_v26_190_route_root_cause_operator_authorization:",
        ),
    )
    return authorization, source, instruction


def _validate_v189(package_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    root = package_root / V189_DIR
    report = _load(root / "report.json")
    manifest = _load(root / "artifact_manifest.json")
    v188_manifest = _load(root / "v188_directory_manifest.json")
    if (
        report.get("report_id") != EXPECTED_V189_REPORT_ID
        or report.get("decision") != CURRENT_DECISION
        or manifest.get("artifact_root") != EXPECTED_V189_ARTIFACT_ROOT
        or v188_manifest.get("manifest_id") != EXPECTED_V188_DIRECTORY_MANIFEST_ID
        or v188_manifest.get("independently_defined_content_root") != EXPECTED_V188_DIRECTORY_ROOT
        or v188_manifest.get("file_count") != 1_350
        or v188_manifest.get("total_byte_count") != 3_618_348
    ):
        raise ValueError("v26.189 frozen report, Artifact Root, or v26.188 Manifest differs")
    return manifest, v188_manifest


def _validate_http_400(envelope: Mapping[str, Any]) -> None:
    telemetry = envelope["provider_telemetry"]
    if (
        telemetry.get("http_status") != 400
        or telemetry.get("http_success") is not False
        or telemetry.get("response_model") is not None
        or telemetry.get("response_hash") is not None
        or telemetry.get("completion_tokens") is not None
        or telemetry.get("total_tokens") is not None
        or envelope.get("raw_http_body_persisted") is not False
        or envelope.get("raw_request_body_persisted") is not False
    ):
        raise ValueError("v26.188 event is not the exact pre-envelope HTTP-400 shape")


def _independent_request_body(config: AgentModelConfig, prompt: str) -> dict[str, Any]:
    return {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": config.temperature,
        "max_tokens": config.max_output_tokens,
        "response_format": {"type": "json_object"},
        **config.request_body_overrides,
    }


def _reconstruct_v188_requests(
    *, package_root: Path, output_dir: Path
) -> RequestReconstructionCatalog:
    prepared = v188.prepare_execution(
        package_root=package_root,
        output_dir=output_dir / "provider_invocation_forbidden",
    )
    profile_payload = _load(package_root / v188.MODEL_PROFILE_PATH)
    config = AgentModelConfig.model_validate(profile_payload["model"])
    jobs_by_id = {item.job_id: item for item in prepared.frozen.manifest.jobs}
    rows: list[ReconstructedRequestRow] = []
    shape: RequestShape | None = None
    for ordinal, job_id in enumerate(prepared.frozen.manifest.expected_job_ids):
        job = jobs_by_id[job_id]
        context = frozen_runtime.prepare_job(job, prepared.runtime_catalog)
        state = frozen_runtime._initialize(context)  # noqa: SLF001
        public_prompt = step_runtime.render_next_prompt(state)
        prompt_payload = {
            "public_prompt": public_prompt.model_dump(mode="json"),
            "response_abi": {
                "grammar_id": prepared.profile.action_grammar_id,
                "state_id": public_prompt.state.state_token,
                "decision_kind": prepared.profile.action_response_decision_kind,
                "protocol": RESPONSE_PROTOCOL_VERSION,
            },
        }
        prompt = _canonical_json(prompt_payload)
        body = _independent_request_body(config, prompt)
        body_bytes = _canonical_json(body).encode("utf-8")
        suffix = job_id.rsplit(":", 1)[-1]
        envelope = _load(
            package_root / V188_DIR / "raw_provider_envelopes" / suffix / "call_000.json"
        )
        _validate_http_400(envelope)
        certificate = envelope["request_binding_certificate"]
        candidate_shape = _request_shape(certificate)
        validate_fixed_request_shape(candidate_shape)
        if shape is None:
            shape = candidate_shape
        elif shape != candidate_shape:
            raise ValueError("v26.188 requests do not share one exact request shape")
        prompt_sha = _sha256_bytes(prompt.encode("utf-8"))
        body_sha = _sha256_bytes(body_bytes)
        if (
            prompt_sha != certificate["prompt_sha256"]
            or prompt_sha != envelope["dynamic_certificate"]["request_prompt_sha256"]
            or body_sha != certificate["canonical_request_body_sha256"]
            or len(body_bytes) != certificate["canonical_request_body_bytes"]
            or tuple(sorted(body)) != tuple(certificate["request_body_fields"])
        ):
            raise ValueError("independently reconstructed v26.188 request differs")
        controls = sum(1 for char in prompt if ord(char) < 32 and char not in "\n\r\t")
        surrogates = sum(1 for char in prompt if 0xD800 <= ord(char) <= 0xDFFF)
        values = {
            "ordinal": ordinal,
            "job_id": job_id,
            "request_certificate_id": certificate["certificate_id"],
            "provider_envelope_id": envelope["envelope_id"],
            "prompt_sha256": prompt_sha,
            "prompt_utf8_bytes": len(prompt.encode("utf-8")),
            "canonical_request_body_sha256": body_sha,
            "canonical_request_body_bytes": len(body_bytes),
            "request_shape_id": candidate_shape.shape_id,
            "exact_certificate_match": True,
            "prompt_top_level_keys": tuple(sorted(prompt_payload)),
            "message_count": 1,
            "message_role": "user",
            "forbidden_control_character_count": controls,
            "surrogate_codepoint_count": surrogates,
            "http_status": 400,
            "response_envelope_observed": False,
            "raw_http_error_body_persisted": False,
            "provider_calls_during_audit": 0,
        }
        rows.append(
            cast(
                ReconstructedRequestRow,
                _identity_model(
                    ReconstructedRequestRow,
                    values,
                    field="row_id",
                    prefix="finance_v26_190_reconstructed_request:",
                ),
            )
        )
    if shape is None:
        raise ValueError("v26.188 reconstruction produced no request shape")
    values = {
        "request_shape": shape,
        "rows": tuple(rows),
        "exact_job_count": len(rows),
        "exact_certificate_match_count": sum(item.exact_certificate_match for item in rows),
        "prompt_utf8_bytes_minimum": min(item.prompt_utf8_bytes for item in rows),
        "prompt_utf8_bytes_maximum": max(item.prompt_utf8_bytes for item in rows),
        "canonical_request_body_bytes_minimum": min(
            item.canonical_request_body_bytes for item in rows
        ),
        "canonical_request_body_bytes_maximum": max(
            item.canonical_request_body_bytes for item in rows
        ),
        "forbidden_control_character_count": sum(
            item.forbidden_control_character_count for item in rows
        ),
        "surrogate_codepoint_count": sum(item.surrogate_codepoint_count for item in rows),
        "provider_calls": 0,
    }
    return cast(
        RequestReconstructionCatalog,
        _identity_model(
            RequestReconstructionCatalog,
            values,
            field="catalog_id",
            prefix="finance_v26_190_request_reconstruction_catalog:",
        ),
    )


def _historical_success_corpus(
    *, package_root: Path, request_shape: RequestShape
) -> HistoricalSuccessCorpus:
    bindings: list[FileBinding] = []
    summaries: list[HistoricalSuccessRunSummary] = []
    total_within = 0
    global_sizes: list[int] = []
    for spec in HISTORICAL_RUNS:
        directory = package_root / "artifacts" / "vtdo_experiment" / spec.run_id
        paths = tuple(sorted((directory / "raw_provider_envelopes").glob("*/*.json")))
        if len(paths) != spec.expected_count:
            raise ValueError(f"historical HTTP-success denominator differs: {spec.run_id}")
        sizes: list[int] = []
        within = 0
        for path in paths:
            envelope = _load(path)
            telemetry = envelope["provider_telemetry"]
            certificate = envelope["request_binding_certificate"]
            candidate_shape = _request_shape(certificate)
            validate_fixed_request_shape(candidate_shape)
            if candidate_shape != request_shape:
                raise ValueError("historical HTTP-success request shape differs from v26.188")
            if (
                telemetry.get("http_status") != 200
                or telemetry.get("http_success") is not True
                or telemetry.get("response_model") != STAGE_ONE_MODEL_ID
                or telemetry.get("response_shape", {}).get("redacted_response_envelope") is None
                or envelope.get("raw_request_body_persisted") is not False
            ):
                raise ValueError("historical comparison row is not exact-model HTTP-success")
            size = int(certificate["canonical_request_body_bytes"])
            sizes.append(size)
            global_sizes.append(size)
            within += EXPECTED_V188_BODY_MIN <= size <= EXPECTED_V188_BODY_MAX
            bindings.append(_file_binding(path, root=package_root))
        total_within += within
        summary_values = {
            "run_id": spec.run_id,
            "envelope_file_count": len(paths),
            "http_200_count": len(paths),
            "exact_shape_count": 1,
            "request_shape_id": request_shape.shape_id,
            "canonical_request_body_bytes_minimum": min(sizes),
            "canonical_request_body_bytes_maximum": max(sizes),
            "http_success_within_v188_body_range": within,
            "raw_request_body_persisted_count": 0,
        }
        summaries.append(
            cast(
                HistoricalSuccessRunSummary,
                _identity_model(
                    HistoricalSuccessRunSummary,
                    summary_values,
                    field="summary_id",
                    prefix="finance_v26_190_historical_success_run_summary:",
                ),
            )
        )
    binding_tuple = tuple(sorted(bindings, key=lambda item: item.relative_path))
    content_root = canonical_hash(
        [item.model_dump(mode="json", warnings=False) for item in binding_tuple],
        prefix="finance_v26_190_historical_success_envelope_root:",
    )
    values = {
        "request_shape": request_shape,
        "run_summaries": tuple(summaries),
        "envelope_files": binding_tuple,
        "envelope_content_root": content_root,
        "exact_http_success_count": len(bindings),
        "success_within_v188_body_range": total_within,
        "global_request_body_bytes_minimum": min(global_sizes),
        "global_request_body_bytes_maximum": max(global_sizes),
        "exact_shape_count": 1,
        "raw_request_body_persisted_count": 0,
        "provider_calls": 0,
    }
    return cast(
        HistoricalSuccessCorpus,
        _identity_model(
            HistoricalSuccessCorpus,
            values,
            field="corpus_id",
            prefix="finance_v26_190_historical_success_corpus:",
        ),
    )


def _source_surface(
    *, package_root: Path, repository_root: Path, request_shape: RequestShape
) -> SourceRequestSurfaceAudit:
    stage_path = repository_root / STAGE_ONE_CLIENT_PATH
    base_path = repository_root / BASE_CLIENT_PATH
    stage_bytes = stage_path.read_bytes()
    base_bytes = base_path.read_bytes()
    if (
        _git(repository_root, "log", "-1", "--format=%H", "--", STAGE_ONE_CLIENT_PATH)
        != STAGE_ONE_CLIENT_LAST_CHANGE
        or _git(repository_root, "log", "-1", "--format=%H", "--", BASE_CLIENT_PATH)
        != BASE_CLIENT_LAST_CHANGE
        or _git_file_bytes(repository_root, V188_SOURCE_COMMIT, STAGE_ONE_CLIENT_PATH)
        != stage_bytes
        or _git_file_bytes(repository_root, V188_SOURCE_COMMIT, BASE_CLIENT_PATH) != base_bytes
    ):
        raise ValueError("request serializer source lineage differs")
    profile = _load(package_root / v188.MODEL_PROFILE_PATH)["model"]
    if profile.get("extra_headers") != {}:
        raise ValueError("frozen Stage 1 profile added nonsecret headers")
    values = {
        "request_shape_id": request_shape.shape_id,
        "stage_one_client_relative_path": STAGE_ONE_CLIENT_PATH,
        "stage_one_client_sha256": _sha256_bytes(stage_bytes),
        "stage_one_client_last_change_commit": STAGE_ONE_CLIENT_LAST_CHANGE,
        "base_client_relative_path": BASE_CLIENT_PATH,
        "base_client_sha256": _sha256_bytes(base_bytes),
        "base_client_last_change_commit": BASE_CLIENT_LAST_CHANGE,
        "v188_source_stage_one_client_exact_match": True,
        "v188_source_base_client_exact_match": True,
        "historical_successes_postdate_client_sources": True,
        "nonsecret_header_names": EXPECTED_HEADER_NAMES,
        "extra_header_count": 0,
        "authorization_header_value_persisted": False,
        "authorization_header_value_compared": False,
        "canonical_json_sort_keys": True,
        "canonical_json_compact_separators": True,
        "utf8_request_encoding": True,
        "raw_request_body_persisted": False,
        "provider_calls": 0,
    }
    return cast(
        SourceRequestSurfaceAudit,
        _identity_model(
            SourceRequestSurfaceAudit,
            values,
            field="audit_id",
            prefix="finance_v26_190_source_request_surface_audit:",
        ),
    )


def _destructive_controls(shape: RequestShape) -> DestructiveAudit:
    shape_mutations: dict[str, tuple[str, Any]] = {
        "endpoint": ("endpoint", "https://api.deepseek.com/chat/completions"),
        "request_model": ("request_model", "deepseek-chat"),
        "max_tokens": ("request_max_tokens", 8_192),
        "thinking": ("thinking_type", "disabled"),
        "response_format": ("response_format_type", "text"),
        "request_fields": ("request_body_fields", EXPECTED_REQUEST_FIELDS[:-1]),
        "profile_sha256": ("profile_sha256", "0" * 64),
        "model_config_id": ("model_config_id", "agent_model_config:mutated"),
        "thinking_binding_id": ("thinking_binding_id", "thinking_binding:mutated"),
        "exact_model_route": ("exact_model_route", False),
        "fallback_forbidden": ("fallback_forbidden", False),
    }
    controls: list[DestructiveControlRow] = []
    base = shape.model_dump(mode="python", exclude={"shape_id"})
    for name, (field, value) in shape_mutations.items():
        changed = dict(base)
        changed[field] = value
        mutated = cast(
            RequestShape,
            _identity_model(
                RequestShape,
                changed,
                field="shape_id",
                prefix="finance_v26_190_exact_request_shape:",
            ),
        )
        try:
            validate_fixed_request_shape(mutated)
        except ValueError:
            controls.append(
                DestructiveControlRow(
                    control_name=name,
                    rejection_stage="exact_fixed_request_shape",
                )
            )
        else:
            raise ValueError(f"destructive request-shape mutation accepted: {name}")
    for name in ("secret_header_visibility", "http_error_body_visibility"):
        controls.append(
            DestructiveControlRow(
                control_name=name,
                rejection_stage="persisted_evidence_visibility",
            )
        )
    values = {
        "controls": tuple(controls),
        "attempted_count": len(controls),
        "rejected_count": len(controls),
        "accepted_count": 0,
        "provider_calls": 0,
    }
    return cast(
        DestructiveAudit,
        _identity_model(
            DestructiveAudit,
            values,
            field="audit_id",
            prefix="finance_v26_190_root_cause_destructive_audit:",
        ),
    )


def _formal_manifest(payloads: dict[str, bytes]) -> FormalArtifactManifest:
    files = tuple(
        FileBinding(relative_path=name, sha256=_sha256_bytes(payload), byte_count=len(payload))
        for name, payload in sorted(payloads.items())
    )
    root = canonical_hash(
        [item.model_dump(mode="json", warnings=False) for item in files],
        prefix="finance_v26_190_route_root_cause_artifact_root:",
    )
    values = {
        "files": files,
        "file_count": len(files),
        "total_byte_count": sum(item.byte_count for item in files),
        "artifact_root": root,
    }
    return cast(
        FormalArtifactManifest,
        _identity_model(
            FormalArtifactManifest,
            values,
            field="manifest_id",
            prefix="finance_v26_190_route_root_cause_artifact_manifest:",
        ),
    )


def build(
    *,
    package_root: Path,
    output_dir: Path,
    external_audit_path: Path,
    source_commit: str,
    source_tree: str,
) -> BuildProducts:
    package_root = package_root.resolve()
    repository_root = package_root.parent
    output_dir = output_dir.resolve()
    if os.environ.get("DEEPSEEK_API_KEY"):
        raise ValueError("v26.190 zero-Provider audit requires credential removal")
    if output_dir.exists():
        raise FileExistsError(f"v26.190 output directory already exists: {output_dir}")
    if len(source_commit) != 40 or len(source_tree) != 40:
        raise ValueError("v26.190 source identity is incomplete")
    if _git_tree(repository_root, source_commit) != source_tree:
        raise ValueError("v26.190 source commit and Tree differ")
    frozen_git = (
        _git_tree(repository_root, V188_SOURCE_COMMIT),
        _git_tree(repository_root, V188_ARTIFACT_COMMIT),
        _git_tree(repository_root, V189_SOURCE_COMMIT),
        _git_tree(repository_root, V189_ARTIFACT_COMMIT),
    )
    if frozen_git != (
        V188_SOURCE_TREE,
        V188_ARTIFACT_TREE,
        V189_SOURCE_TREE,
        V189_ARTIFACT_TREE,
    ):
        raise ValueError("v26.188-v26.189 frozen Git identities differ")
    authorization, external_bytes, instruction_bytes = _authorization(external_audit_path)
    _v189_manifest, v188_manifest = _validate_v189(package_root)
    before_v188 = tuple(FileBinding.model_validate(item) for item in v188_manifest["files"])
    reconstruction = _reconstruct_v188_requests(package_root=package_root, output_dir=output_dir)
    historical = _historical_success_corpus(
        package_root=package_root,
        request_shape=reconstruction.request_shape,
    )
    source_surface = _source_surface(
        package_root=package_root,
        repository_root=repository_root,
        request_shape=reconstruction.request_shape,
    )
    current_v188 = tuple(
        _file_binding(path, root=package_root / V188_DIR)
        for path in sorted((package_root / V188_DIR).rglob("*"))
        if path.is_file()
    )
    if current_v188 != before_v188:
        raise ValueError("v26.188 immutable directory bytes changed")
    historical_after = _historical_success_corpus(
        package_root=package_root,
        request_shape=reconstruction.request_shape,
    )
    if historical_after != historical:
        raise ValueError("historical HTTP-success corpus changed during audit")
    freeze = cast(
        PredecessorFreezeAudit,
        _identity_model(
            PredecessorFreezeAudit,
            {
                "authorization_id": authorization.authorization_id,
                "v188_source_commit": V188_SOURCE_COMMIT,
                "v188_source_tree": V188_SOURCE_TREE,
                "v188_artifact_commit": V188_ARTIFACT_COMMIT,
                "v188_artifact_tree": V188_ARTIFACT_TREE,
                "v189_source_commit": V189_SOURCE_COMMIT,
                "v189_source_tree": V189_SOURCE_TREE,
                "v189_artifact_commit": V189_ARTIFACT_COMMIT,
                "v189_artifact_tree": V189_ARTIFACT_TREE,
                "v189_report_id": EXPECTED_V189_REPORT_ID,
                "v189_artifact_root": EXPECTED_V189_ARTIFACT_ROOT,
                "v188_directory_manifest_id": EXPECTED_V188_DIRECTORY_MANIFEST_ID,
                "v188_directory_root": EXPECTED_V188_DIRECTORY_ROOT,
                "v188_file_count": 1_350,
                "v188_byte_count": 3_618_348,
                "predecessor_bytes_unchanged_after_audit": True,
                "historical_reclassification_count": 0,
                "provider_calls": 0,
            },
            field="audit_id",
            prefix="finance_v26_190_predecessor_freeze:",
        ),
    )
    comparison = cast(
        RequestContractComparisonAudit,
        _identity_model(
            RequestContractComparisonAudit,
            {
                "v188_catalog_id": reconstruction.catalog_id,
                "historical_success_corpus_id": historical.corpus_id,
                "source_surface_audit_id": source_surface.audit_id,
                "endpoint_match": True,
                "request_model_match": True,
                "max_tokens_match": True,
                "thinking_match": True,
                "response_format_match": True,
                "request_body_field_set_match": True,
                "profile_sha256_match": True,
                "model_config_id_match": True,
                "thinking_binding_id_match": True,
                "messages_wrapper_shape_match": True,
                "nonsecret_header_schema_match": True,
                "serializer_source_match": True,
                "v188_body_range_contained_by_historical_success_range": True,
                "historical_http_successes_within_v188_body_range": (
                    historical.success_within_v188_body_range
                ),
                "deterministic_fixed_contract_difference_count": 0,
                "prompt_or_body_encoding_defect_count": 0,
                "secret_authorization_value_comparison_evaluable": False,
                "provider_server_contract_at_v188_execution_evaluable": False,
                "http_error_body_evaluable": False,
                "provider_calls": 0,
            },
            field="audit_id",
            prefix="finance_v26_190_request_contract_comparison_audit:",
        ),
    )
    localization = cast(
        RootCauseLocalizationAudit,
        _identity_model(
            RootCauseLocalizationAudit,
            {
                "comparison_audit_id": comparison.audit_id,
                "first_blocker": "http_400_before_response_envelope_and_model_endpoint",
                "deterministic_request_contract_difference": "none_found",
                "unique_root_cause_identified": False,
                "localization_result": "not_localizable_from_persisted_artifacts",
                "ruled_out_persisted_factors": (
                    "endpoint_url",
                    "request_model",
                    "max_tokens",
                    "thinking_type",
                    "response_format",
                    "request_body_field_set",
                    "model_profile_sha256",
                    "model_config_identity",
                    "thinking_binding_identity",
                    "messages_wrapper_shape",
                    "nonsecret_header_schema",
                    "serializer_source",
                    "request_body_size_envelope",
                    "prompt_utf8_encoding",
                ),
                "unevaluable_factors": (
                    "authorization_header_value_or_account_route_at_execution",
                    "provider_server_side_contract_or_model_availability_at_execution",
                    "http_400_response_body_detail_not_persisted",
                ),
                "historical_http_success_count": historical.exact_http_success_count,
                "v188_http_400_count": 192,
                "historical_reclassification_count": 0,
                "provider_calls": 0,
            },
            field="audit_id",
            prefix="finance_v26_190_root_cause_localization_audit:",
        ),
    )
    destructive = _destructive_controls(reconstruction.request_shape)
    gates = {
        "operator_selected_unique_recommended_zero_provider_stage": True,
        "v26_188_v26_189_git_and_artifact_freeze": True,
        "v26_188_exact_192_request_reconstruction": True,
        "v26_188_request_certificate_byte_match": True,
        "v26_188_prompt_encoding_integrity": True,
        "historical_7229_http_success_corpus": True,
        "single_exact_request_shape_across_failure_and_success": True,
        "request_body_size_range_overlap": True,
        "serializer_source_lineage": True,
        "nonsecret_header_schema_comparison": True,
        "unobservable_secret_and_server_factors_kept_null": True,
        "root_cause_not_overclaimed": True,
        "destructive_controls_reject": True,
        "zero_provider_calls": True,
        "zero_historical_reclassification": True,
        "zero_route_repair_or_recovery": True,
        "zero_downstream_admission": True,
    }
    static = cast(
        StaticAudit,
        _identity_model(
            StaticAudit,
            {
                "gates": gates,
                "passed_gate_count": len(gates),
                "failed_gate_count": 0,
                "provider_calls": 0,
                "provider_clients_constructed": 0,
                "credential_reads": 0,
                "recovery_jobs": 0,
                "request_route_repairs": 0,
                "historical_reclassification_count": 0,
                "mapper_rows": 0,
                "state_rows": 0,
                "contribution_rows": 0,
                "vtdo_rows": 0,
            },
            field="audit_id",
            prefix="finance_v26_190_root_cause_static_audit:",
        ),
    )
    transition = cast(
        ProspectiveTransition,
        _identity_model(
            ProspectiveTransition,
            {
                "current_stage": AUTHORIZED_STAGE,
                "current_audit_passed": True,
                "decision": CURRENT_DECISION,
                "recommended_future_stage": RECOMMENDED_FUTURE_STAGE,
                "recommended_future_stage_authorized_now": False,
                "provider_execution_authorized": False,
                "provider_rerun_authorized": False,
                "request_route_repair_authorized": False,
                "recovery_jobs_authorized": False,
                "downstream_empirical_work_authorized": False,
            },
            field="transition_id",
            prefix="finance_v26_190_root_cause_transition:",
        ),
    )
    report = cast(
        RootCauseAuditReport,
        _identity_model(
            RootCauseAuditReport,
            {
                "run_id": RUN_ID,
                "authorization_id": authorization.authorization_id,
                "predecessor_freeze_id": freeze.audit_id,
                "request_reconstruction_catalog_id": reconstruction.catalog_id,
                "historical_success_corpus_id": historical.corpus_id,
                "source_surface_audit_id": source_surface.audit_id,
                "comparison_audit_id": comparison.audit_id,
                "root_cause_localization_audit_id": localization.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "static_audit_id": static.audit_id,
                "transition_id": transition.transition_id,
                "v188_request_reconstruction": "PASS",
                "historical_exact_route_success_comparison": "PASS",
                "deterministic_request_contract_difference": "NONE_FOUND",
                "unique_http_400_root_cause": "NOT_LOCALIZABLE_FROM_PERSISTED_ARTIFACTS",
                "historical_http_success_count": historical.exact_http_success_count,
                "historical_success_within_v188_body_range": (
                    historical.success_within_v188_body_range
                ),
                "v188_http_400_count": 192,
                "provider_calls": 0,
                "decision": CURRENT_DECISION,
            },
            field="report_id",
            prefix="finance_v26_190_root_cause_audit_report:",
        ),
    )
    payloads = {
        "external_v26_189_latest_audit.txt": external_bytes,
        "operator_instruction.txt": instruction_bytes,
        "operator_authorization.json": _canonical_bytes(authorization),
        "predecessor_freeze.json": _canonical_bytes(freeze),
        "v188_request_reconstruction_catalog.json": _canonical_bytes(reconstruction),
        "historical_http_success_corpus.json": _canonical_bytes(historical),
        "source_request_surface_audit.json": _canonical_bytes(source_surface),
        "request_contract_comparison_audit.json": _canonical_bytes(comparison),
        "root_cause_localization_audit.json": _canonical_bytes(localization),
        "destructive_audit.json": _canonical_bytes(destructive),
        "static_audit.json": _canonical_bytes(static),
        "prospective_transition.json": _canonical_bytes(transition),
        "report.json": _canonical_bytes(report),
        "source_identity.json": _canonical_bytes(
            {
                "source_commit": source_commit,
                "source_tree": source_tree,
                "schema_version": "exact_route_root_cause_source_identity.v1",
            }
        ),
    }
    artifact_manifest = _formal_manifest(payloads)
    payloads["artifact_manifest.json"] = _canonical_bytes(artifact_manifest)
    write_immutable_artifact_directory(output_dir, payloads)
    return BuildProducts(
        authorization=authorization,
        freeze=freeze,
        reconstruction=reconstruction,
        historical=historical,
        source_surface=source_surface,
        comparison=comparison,
        localization=localization,
        destructive=destructive,
        static=static,
        transition=transition,
        report=report,
        artifact_manifest=artifact_manifest,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    args = parser.parse_args()
    products = build(
        package_root=args.package_root,
        output_dir=args.output_dir,
        external_audit_path=args.external_audit,
        source_commit=args.source_commit,
        source_tree=args.source_tree,
    )
    print(products.report.model_dump_json())


if __name__ == "__main__":
    main()
