from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.core.task import authoritative_artifact_backed_outcome as evidence
from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
    AuthoritativeTerminalRegistry,
    RawExecutionEvidencePayload,
)
from trusted_synthesis.core.task.job_bound_multistep_outcome import (
    CapabilityDevelopmentJob,
    CapabilityDevelopmentJobManifest,
    JobBoundRunnerContract,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_189_artifact_backed_online_postrun_independent_audit_v1_20260831"
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
AUTHORIZED_STAGE: Final = (
    "capability_observation_artifact_backed_192_job_postrun_independent_audit_only"
)
RECOMMENDED_FUTURE_AUDIT: Final = "exact_route_http_400_request_contract_root_cause_audit_only"
CURRENT_DECISION: Final = "no_further_experiment_authorized_without_new_audit_decision"

EXTERNAL_AUDIT_SHA256: Final = "25b3049a42cd22f3613ce4e29df77b8eb92299f69f3dce625964914434a5a762"
EXTERNAL_AUDIT_BYTE_COUNT: Final = 11_240
V188_SOURCE_COMMIT: Final = "53d0128f22043a88efb612af835aa99bdc78ede4"
V188_SOURCE_TREE: Final = "38456681dfd2e3d18fa65b1268245affc1e34d39"
V188_ARTIFACT_COMMIT: Final = "da40cb1512d86296cbeb14b127ace4c20cfd076e"
V188_ARTIFACT_TREE: Final = "ac3371743c1ec3d010bf27dea6afb860e7297530"
V188_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_188_artifact_backed_online_development_execution_v1_20260831"
)
V186_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_186_artifact_backed_outcome_preflight_v2_20260831"
)
V181_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_181_authoritative_outcome_terminal_preflight_v1_20260830"
)
V179_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_179_job_bound_multistep_outcome_preflight_v1_20260830"
)

EXPECTED_FILE_COUNT: Final = 1_350
EXPECTED_BYTE_COUNT: Final = 3_618_348
EXPECTED_JOB_COUNT: Final = 192
EXPECTED_ARTIFACT_FILE_COUNT: Final = 384
EXPECTED_V188_RECORDED_CONTENT_ROOT: Final = (
    "finance_v26_188_online_execution_content_root:"
    "c2aac4f4cfcfad9729bcd64fd8945026d75b5fb85a067d7022a4db22f55bd3a7"
)
EXPECTED_EVALUATION_ID: Final = (
    "capability_artifact_backed_empirical_evaluation:"
    "71771453c6fe86b832e7b7924b03896c8643ceda27d572972fcf826a2672842a"
)
EXPECTED_CONTRACT_ID: Final = (
    "capability_artifact_backed_outcome_contract:"
    "00fd9874ff98b5e58bc999ee76328639580393b49652417bf9ab7cdf22bd8376"
)
EXPECTED_REGISTRY_ID: Final = (
    "capability_authoritative_terminal_registry:"
    "2fb3fa1572ac9681702ff0b3488152a1da8396c73683d4c7d67cb9a3257fb4c1"
)
EXPECTED_MANIFEST_ID: Final = (
    "capability_job_bound_development_manifest:"
    "ab33e14cb0dbf81ab38682bfa4785cc1dc8eb5031b696d738a12acc9a97b203a"
)
EXPECTED_RUNNER_ID: Final = (
    "capability_job_bound_multistep_runner_contract:"
    "11e3e81775a4c38e2c888957cb704c0a718213b25db52a376efbe6f3f4f52238"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    authorized_stage: Literal[
        "capability_observation_artifact_backed_192_job_postrun_independent_audit_only"
    ] = AUTHORIZED_STAGE
    source_sha256: Literal["25b3049a42cd22f3613ce4e29df77b8eb92299f69f3dce625964914434a5a762"] = (
        EXTERNAL_AUDIT_SHA256
    )
    source_byte_count: Literal[11240] = EXTERNAL_AUDIT_BYTE_COUNT
    provider_calls_authorized: Literal[False] = False
    provider_rerun_authorized: Literal[False] = False
    recovery_jobs_authorized: Literal[False] = False
    mapper_state_frequency_authorized: Literal[False] = False
    schema_version: Literal["artifact_backed_postrun_external_authorization.v1"] = (
        "artifact_backed_postrun_external_authorization.v1"
    )

    @model_validator(mode="after")
    def validate_identity(self) -> ExternalAuditAuthorization:
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="authorization_id",
            prefix="finance_v26_188_postrun_external_authorization:",
        )
        return self


class AuditedDirectoryManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    audited_run_id: Literal[
        "finance_v26_188_artifact_backed_online_development_execution_v1_20260831"
    ] = "finance_v26_188_artifact_backed_online_development_execution_v1_20260831"
    file_count: Literal[1350] = EXPECTED_FILE_COUNT
    total_byte_count: Literal[3618348] = EXPECTED_BYTE_COUNT
    files: tuple[FileBinding, ...] = Field(min_length=1350, max_length=1350)
    independently_defined_content_root: str = Field(min_length=1)
    predecessor_recorded_content_root: Literal[
        "finance_v26_188_online_execution_content_root:"
        "c2aac4f4cfcfad9729bcd64fd8945026d75b5fb85a067d7022a4db22f55bd3a7"
    ] = EXPECTED_V188_RECORDED_CONTENT_ROOT
    predecessor_root_preimage_persisted: Literal[False] = False
    schema_version: Literal["artifact_backed_postrun_directory_manifest.v1"] = (
        "artifact_backed_postrun_directory_manifest.v1"
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> AuditedDirectoryManifest:
        paths = tuple(item.relative_path for item in self.files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.188 directory Manifest paths are not exact")
        if sum(item.byte_count for item in self.files) != self.total_byte_count:
            raise ValueError("v26.188 directory Manifest byte count differs")
        expected_root = canonical_hash(
            [item.model_dump(mode="json", warnings=False) for item in self.files],
            prefix="finance_v26_188_independent_directory_content_root:",
        )
        if self.independently_defined_content_root != expected_root:
            raise ValueError("v26.188 independent directory content Root differs")
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="manifest_id",
            prefix="finance_v26_188_independent_directory_manifest:",
        )
        return self


class PredecessorFreezeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_commit: Literal["53d0128f22043a88efb612af835aa99bdc78ede4"] = V188_SOURCE_COMMIT
    source_tree: Literal["38456681dfd2e3d18fa65b1268245affc1e34d39"] = V188_SOURCE_TREE
    artifact_commit: Literal["da40cb1512d86296cbeb14b127ace4c20cfd076e"] = V188_ARTIFACT_COMMIT
    artifact_tree: Literal["ac3371743c1ec3d010bf27dea6afb860e7297530"] = V188_ARTIFACT_TREE
    directory_manifest_id: str = Field(min_length=1)
    exact_file_count: Literal[1350] = EXPECTED_FILE_COUNT
    exact_byte_count: Literal[3618348] = EXPECTED_BYTE_COUNT
    directory_unchanged_after_audit: Literal[True] = True
    historical_file_mutation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["artifact_backed_postrun_predecessor_freeze.v1"] = (
        "artifact_backed_postrun_predecessor_freeze.v1"
    )

    @model_validator(mode="after")
    def validate_identity(self) -> PredecessorFreezeAudit:
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="audit_id",
            prefix="finance_v26_188_online_predecessor_freeze:",
        )
        return self


class IndependentJobReplayRow(FrozenModel):
    row_id: str = Field(min_length=1)
    ordinal: int = Field(ge=0, le=191)
    job_id: str = Field(min_length=1)
    record_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    outcome_row_id: str = Field(min_length=1)
    provider_envelope_id: str = Field(min_length=1)
    public_projection_id: str = Field(min_length=1)
    transport_certificate_id: str = Field(min_length=1)
    request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_body_byte_count: int = Field(gt=0)
    http_status: Literal[400] = 400
    http_success: Literal[False] = False
    response_envelope_observed: Literal[False] = False
    model_identity_evaluable: Literal[False] = False
    observed_wrong_model_response: Literal[False] = False
    public_payload_observed: Literal[False] = False
    usage_observed: Literal[False] = False
    raw_http_body_persisted: Literal[False] = False
    terminal_kind: Literal["provider_identity_failure"] = "provider_identity_failure"
    frozen_reason_code: Literal["provider_identity_failure"] = "provider_identity_failure"
    q_first_value: Literal[False] = False
    q_bounded_value: Literal[False] = False
    exact_parent_chain_match: Literal[True] = True
    raw_result_byte_match_count: Literal[2] = 2
    descriptor_byte_match_count: Literal[3] = 3
    schema_version: Literal["artifact_backed_postrun_job_replay.v1"] = (
        "artifact_backed_postrun_job_replay.v1"
    )

    @model_validator(mode="after")
    def validate_identity(self) -> IndependentJobReplayRow:
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="row_id",
            prefix="finance_v26_188_independent_job_replay:",
        )
        return self


class IndependentJobReplayCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    manifest_id: Literal[
        "capability_job_bound_development_manifest:"
        "ab33e14cb0dbf81ab38682bfa4785cc1dc8eb5031b696d738a12acc9a97b203a"
    ] = EXPECTED_MANIFEST_ID
    rows: tuple[IndependentJobReplayRow, ...] = Field(min_length=192, max_length=192)
    schema_version: Literal["artifact_backed_postrun_job_replay_catalog.v1"] = (
        "artifact_backed_postrun_job_replay_catalog.v1"
    )

    @model_validator(mode="after")
    def validate_catalog(self) -> IndependentJobReplayCatalog:
        if tuple(item.ordinal for item in self.rows) != tuple(range(EXPECTED_JOB_COUNT)):
            raise ValueError("independent Job replay ordinals differ")
        job_ids = tuple(item.job_id for item in self.rows)
        if len(set(job_ids)) != EXPECTED_JOB_COUNT:
            raise ValueError("independent Job replay repeats a Job")
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="catalog_id",
            prefix="finance_v26_188_independent_job_replay_catalog:",
        )
        return self


class EvidenceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: Literal[
        "capability_artifact_backed_outcome_contract:"
        "00fd9874ff98b5e58bc999ee76328639580393b49652417bf9ab7cdf22bd8376"
    ] = EXPECTED_CONTRACT_ID
    registry_id: Literal[
        "capability_authoritative_terminal_registry:"
        "2fb3fa1572ac9681702ff0b3488152a1da8396c73683d4c7d67cb9a3257fb4c1"
    ] = EXPECTED_REGISTRY_ID
    manifest_id: Literal[
        "capability_job_bound_development_manifest:"
        "ab33e14cb0dbf81ab38682bfa4785cc1dc8eb5031b696d738a12acc9a97b203a"
    ] = EXPECTED_MANIFEST_ID
    runner_id: Literal[
        "capability_job_bound_multistep_runner_contract:"
        "11e3e81775a4c38e2c888957cb704c0a718213b25db52a376efbe6f3f4f52238"
    ] = EXPECTED_RUNNER_ID
    job_record_count: Literal[192] = 192
    checkpoint_count: Literal[192] = 192
    raw_count: Literal[192] = 192
    result_count: Literal[192] = 192
    raw_result_file_count: Literal[384] = 384
    raw_result_byte_match_count: Literal[384] = 384
    provider_envelope_count: Literal[192] = 192
    public_projection_count: Literal[192] = 192
    transport_certificate_count: Literal[192] = 192
    descriptor_byte_match_count: Literal[576] = 576
    exact_parent_chain_match_count: Literal[192] = 192
    typed_outcome_count: Literal[192] = 192
    terminal_projection_count: Literal[192] = 192
    recomputed_evaluation_id: Literal[
        "capability_artifact_backed_empirical_evaluation:"
        "71771453c6fe86b832e7b7924b03896c8643ceda27d572972fcf826a2672842a"
    ] = EXPECTED_EVALUATION_ID
    frozen_evaluation_exact_match: Literal[True] = True
    v188_online_helpers_used_as_outcome_oracle: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["artifact_backed_postrun_evidence_replay.v1"] = (
        "artifact_backed_postrun_evidence_replay.v1"
    )

    @model_validator(mode="after")
    def validate_identity(self) -> EvidenceReplayAudit:
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="audit_id",
            prefix="finance_v26_188_independent_evidence_replay:",
        )
        return self


class RawEventDecompositionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    stage_one_request_count: Literal[192] = 192
    stage_two_request_count: Literal[0] = 0
    http_error_count: Literal[192] = 192
    http_400_count: Literal[192] = 192
    http_success_count: Literal[0] = 0
    response_envelope_count: Literal[0] = 0
    model_identity_evaluable_count: Literal[0] = 0
    observed_wrong_model_response_count: Literal[0] = 0
    public_payload_count: Literal[0] = 0
    usage_observed_count: Literal[0] = 0
    total_usage_tokens: Literal[0] = 0
    raw_http_body_persisted_count: Literal[0] = 0
    raw_request_body_persisted_count: Literal[0] = 0
    frozen_provider_identity_failure_count: Literal[192] = 192
    actual_responding_model: Literal["unknown"] = "unknown"
    server_side_rejection_detail: Literal["unavailable_not_persisted"] = "unavailable_not_persisted"
    provider_calls_during_audit: Literal[0] = 0
    schema_version: Literal["artifact_backed_postrun_raw_event_decomposition.v1"] = (
        "artifact_backed_postrun_raw_event_decomposition.v1"
    )

    @model_validator(mode="after")
    def validate_identity(self) -> RawEventDecompositionAudit:
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="audit_id",
            prefix="finance_v26_188_independent_raw_event_decomposition:",
        )
        return self


class EstimandSeparationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    exact_job_denominator: Literal[192] = 192
    q_job_first_numerator: Literal[0] = 0
    q_job_first_fraction: Literal["0/192"] = "0/192"
    q_job_bounded_numerator: Literal[0] = 0
    q_job_bounded_fraction: Literal["0/192"] = "0/192"
    model_endpoint_denominator: Literal[0] = 0
    semantic_qualified_numerator: Literal[0] = 0
    semantic_capability_fraction: Literal["null"] = "null"
    semantic_capability_instantiated: Literal[False] = False
    semantic_null_is_not_zero: Literal[True] = True
    capability_depth_instantiated: Literal[False] = False
    schema_version: Literal["artifact_backed_postrun_estimand_separation.v1"] = (
        "artifact_backed_postrun_estimand_separation.v1"
    )

    @model_validator(mode="after")
    def validate_identity(self) -> EstimandSeparationAudit:
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="audit_id",
            prefix="finance_v26_188_independent_estimand_separation:",
        )
        return self


class LayeredGateAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    job_exact_set: Literal["PASS"] = "PASS"
    raw_result_completeness: Literal["PASS"] = "PASS"
    artifact_byte_authority: Literal["PASS"] = "PASS"
    typed_terminal_totality: Literal["PASS"] = "PASS"
    parent_chain_reconstruction: Literal["PASS"] = "PASS"
    frozen_terminal_admission: Literal["PASS"] = "PASS"
    provider_request_acceptance: Literal["FAIL"] = "FAIL"
    model_endpoint_observability: Literal["UNINSTANTIATED"] = "UNINSTANTIATED"
    semantic_capability_measurement: Literal["UNAVAILABLE"] = "UNAVAILABLE"
    mapper_state_admission: Literal["NOT_AUTHORIZED"] = "NOT_AUTHORIZED"
    all_evidence_authority_gates_passed: Literal[True] = True
    capability_measurement_gate_passed: Literal[False] = False
    schema_version: Literal["artifact_backed_postrun_layered_gate.v1"] = (
        "artifact_backed_postrun_layered_gate.v1"
    )

    @model_validator(mode="after")
    def validate_identity(self) -> LayeredGateAudit:
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="audit_id",
            prefix="finance_v26_188_independent_layered_gate:",
        )
        return self


class StaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: dict[str, bool]
    passed_gate_count: int = Field(ge=1)
    failed_gate_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    confirmation_payload_access_count: Literal[0] = 0
    historical_reclassification_count: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    schema_version: Literal["artifact_backed_postrun_static_audit.v1"] = (
        "artifact_backed_postrun_static_audit.v1"
    )

    @model_validator(mode="after")
    def validate_static(self) -> StaticAudit:
        if self.passed_gate_count != len(self.gates) or not all(self.gates.values()):
            raise ValueError("postrun static Gate count differs")
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="audit_id",
            prefix="finance_v26_188_independent_static_audit:",
        )
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    current_stage: Literal[
        "capability_observation_artifact_backed_192_job_postrun_independent_audit_only"
    ] = AUTHORIZED_STAGE
    current_audit_passed: Literal[True] = True
    decision: Literal["no_further_experiment_authorized_without_new_audit_decision"] = (
        CURRENT_DECISION
    )
    recommended_future_audit: Literal[
        "exact_route_http_400_request_contract_root_cause_audit_only"
    ] = RECOMMENDED_FUTURE_AUDIT
    recommended_future_audit_authorized_now: Literal[False] = False
    provider_rerun_authorized: Literal[False] = False
    recovery_jobs_authorized: Literal[False] = False
    request_route_repair_authorized: Literal[False] = False
    mapper_state_frequency_contribution_vtdo_authorized: Literal[False] = False
    schema_version: Literal["artifact_backed_postrun_transition.v1"] = (
        "artifact_backed_postrun_transition.v1"
    )

    @model_validator(mode="after")
    def validate_identity(self) -> ProspectiveTransition:
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="transition_id",
            prefix="finance_v26_188_postrun_transition:",
        )
        return self


class PostrunIndependentAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: Literal[
        "finance_v26_189_artifact_backed_online_postrun_independent_audit_v1_20260831"
    ] = RUN_ID
    authorization_id: str = Field(min_length=1)
    predecessor_freeze_id: str = Field(min_length=1)
    directory_manifest_id: str = Field(min_length=1)
    job_replay_catalog_id: str = Field(min_length=1)
    evidence_replay_audit_id: str = Field(min_length=1)
    raw_event_decomposition_audit_id: str = Field(min_length=1)
    estimand_separation_audit_id: str = Field(min_length=1)
    layered_gate_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    online_execution_and_evidence_chain: Literal["PASS"] = "PASS"
    model_semantic_capability_observation: Literal["UNINSTANTIATED"] = "UNINSTANTIATED"
    formal_end_to_end_q_first: Literal["0/192"] = "0/192"
    formal_end_to_end_q_bounded: Literal["0/192"] = "0/192"
    model_endpoint_conditional_semantic_q: Literal["null"] = "null"
    first_blocker: Literal["http_400_before_response_envelope_and_model_endpoint"] = (
        "http_400_before_response_envelope_and_model_endpoint"
    )
    provider_calls: Literal[0] = 0
    decision: Literal["no_further_experiment_authorized_without_new_audit_decision"] = (
        CURRENT_DECISION
    )
    schema_version: Literal["artifact_backed_postrun_independent_audit_report.v1"] = (
        "artifact_backed_postrun_independent_audit_report.v1"
    )

    @model_validator(mode="after")
    def validate_identity(self) -> PostrunIndependentAuditReport:
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="report_id",
            prefix="finance_v26_188_postrun_independent_audit_report:",
        )
        return self


class FormalArtifactManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    artifact_root: str = Field(min_length=1)
    files: tuple[FileBinding, ...]
    file_count: int = Field(ge=1)
    total_byte_count: int = Field(ge=1)
    schema_version: Literal["artifact_backed_postrun_formal_artifact_manifest.v1"] = (
        "artifact_backed_postrun_formal_artifact_manifest.v1"
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> FormalArtifactManifest:
        if self.file_count != len(self.files):
            raise ValueError("formal artifact Manifest file count differs")
        if self.total_byte_count != sum(item.byte_count for item in self.files):
            raise ValueError("formal artifact Manifest byte count differs")
        root = canonical_hash(
            [item.model_dump(mode="json", warnings=False) for item in self.files],
            prefix="finance_v26_189_postrun_artifact_root:",
        )
        if self.artifact_root != root:
            raise ValueError("formal artifact Root differs")
        _require_identity(
            self.model_dump(mode="json", warnings=False),
            field="manifest_id",
            prefix="finance_v26_189_postrun_artifact_manifest:",
        )
        return self


class BuildProducts(FrozenModel):
    authorization: ExternalAuditAuthorization
    directory_manifest: AuditedDirectoryManifest
    freeze: PredecessorFreezeAudit
    job_replay: IndependentJobReplayCatalog
    evidence_replay: EvidenceReplayAudit
    raw_events: RawEventDecompositionAudit
    estimands: EstimandSeparationAudit
    gates: LayeredGateAudit
    static: StaticAudit
    transition: ProspectiveTransition
    report: PostrunIndependentAuditReport
    artifact_manifest: FormalArtifactManifest


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.189 cannot resolve the trusted_data_synthesis package root")


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _require_identity(value: dict[str, Any], *, field: str, prefix: str) -> None:
    observed = value[field]
    expected = canonical_hash(
        {key: item for key, item in value.items() if key != field},
        prefix=prefix,
    )
    if observed != expected:
        raise ValueError(f"content identity differs:{field}")


def _identity_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    payload = provisional.model_dump(mode="json", exclude={field}, warnings=False)
    return model_type(**{field: canonical_hash(payload, prefix=prefix)}, **values)


def _safe_bound_path(root: Path, relative_path: str) -> Path:
    logical = PurePosixPath(relative_path)
    if (
        logical.is_absolute()
        or not logical.parts
        or any(part in {"", ".", ".."} for part in logical.parts)
    ):
        raise ValueError("descriptor path is not safe and relative")
    current = root
    for part in logical.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("descriptor path contains a symlink")
    if not current.resolve(strict=False).is_relative_to(root.resolve()):
        raise ValueError("descriptor path escapes the v26.188 root")
    return current


def _binding(root: Path, path: Path) -> FileBinding:
    payload = path.read_bytes()
    return FileBinding(
        relative_path=path.relative_to(root).as_posix(),
        sha256=_sha256_bytes(payload),
        byte_count=len(payload),
    )


def _directory_bindings(root: Path) -> tuple[FileBinding, ...]:
    paths = tuple(sorted(path for path in root.rglob("*") if path.is_file()))
    if any(path.is_symlink() for path in paths):
        raise ValueError("v26.188 audited directory contains a symlink")
    return tuple(_binding(root, path) for path in paths)


def _git_tree(repository_root: Path, commit: str) -> str:
    result = subprocess.run(
        ("git", "show", "-s", "--format=%T", commit),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _authorization(path: Path) -> tuple[ExternalAuditAuthorization, bytes]:
    payload = path.read_bytes()
    if len(payload) != EXTERNAL_AUDIT_BYTE_COUNT or _sha256_bytes(payload) != EXTERNAL_AUDIT_SHA256:
        raise ValueError("v26.188 postrun external audit bytes differ")
    values = {
        "authorized_stage": AUTHORIZED_STAGE,
        "source_sha256": EXTERNAL_AUDIT_SHA256,
        "source_byte_count": EXTERNAL_AUDIT_BYTE_COUNT,
        "provider_calls_authorized": False,
        "provider_rerun_authorized": False,
        "recovery_jobs_authorized": False,
        "mapper_state_frequency_authorized": False,
    }
    return (
        cast(
            ExternalAuditAuthorization,
            _identity_model(
                ExternalAuditAuthorization,
                values,
                field="authorization_id",
                prefix="finance_v26_188_postrun_external_authorization:",
            ),
        ),
        payload,
    )


def _directory_manifest(root: Path) -> AuditedDirectoryManifest:
    files = _directory_bindings(root)
    if len(files) != EXPECTED_FILE_COUNT or sum(item.byte_count for item in files) != (
        EXPECTED_BYTE_COUNT
    ):
        raise ValueError("v26.188 audited directory geometry differs")
    independent_root = canonical_hash(
        [item.model_dump(mode="json", warnings=False) for item in files],
        prefix="finance_v26_188_independent_directory_content_root:",
    )
    values = {
        "audited_run_id": root.name,
        "file_count": len(files),
        "total_byte_count": sum(item.byte_count for item in files),
        "files": files,
        "independently_defined_content_root": independent_root,
        "predecessor_recorded_content_root": EXPECTED_V188_RECORDED_CONTENT_ROOT,
        "predecessor_root_preimage_persisted": False,
    }
    return cast(
        AuditedDirectoryManifest,
        _identity_model(
            AuditedDirectoryManifest,
            values,
            field="manifest_id",
            prefix="finance_v26_188_independent_directory_manifest:",
        ),
    )


def _load_frozen_parents(
    package_root: Path,
) -> tuple[
    AuthoritativeTerminalRegistry,
    evidence.ArtifactBackedOutcomeContract,
    CapabilityDevelopmentJobManifest,
    JobBoundRunnerContract,
]:
    registry = AuthoritativeTerminalRegistry.model_validate(
        _load(package_root / V181_DIR / "authoritative_terminal_registry_audit.json")["registry"]
    )
    contract = evidence.ArtifactBackedOutcomeContract.model_validate(
        _load(package_root / V186_DIR / "artifact_backed_outcome_contract.json")["contract"]
    )
    manifest = CapabilityDevelopmentJobManifest.model_validate(
        _load(package_root / V179_DIR / "development_job_manifest.json")
    )
    runner = JobBoundRunnerContract.model_validate(
        _load(package_root / V179_DIR / "job_bound_runner_contract.json")
    )
    if (
        registry.registry_id,
        contract.contract_id,
        manifest.manifest_id,
        runner.runner_id,
    ) != (
        EXPECTED_REGISTRY_ID,
        EXPECTED_CONTRACT_ID,
        EXPECTED_MANIFEST_ID,
        EXPECTED_RUNNER_ID,
    ):
        raise ValueError("v26.188 frozen authority parent differs")
    return registry, contract, manifest, runner


def validate_http_400_telemetry(telemetry: dict[str, Any]) -> None:
    expected_null = (
        "completion_tokens",
        "finish_reason",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "prompt_tokens",
        "reasoning_content_length",
        "reasoning_tokens",
        "response_content_length",
        "response_hash",
        "response_model",
        "total_tokens",
    )
    if (
        telemetry.get("error_type") != "HTTPError"
        or telemetry.get("http_status") != 400
        or telemetry.get("http_success") is not False
        or telemetry.get("json_contract_success") is not False
        or telemetry.get("model_requested") != "deepseek-v4-flash"
        or telemetry.get("model_selected") != "deepseek-v4-flash"
        or telemetry.get("provider") != "deepseek"
        or telemetry.get("endpoint_host") != "api.deepseek.com"
        or telemetry.get("discovery_attempted") is not False
        or telemetry.get("discovered_model_count") != 0
        or telemetry.get("fallback_used") is not False
        or telemetry.get("reasoning_content_present") is not False
        or any(telemetry.get(key) is not None for key in expected_null)
    ):
        raise ValueError("v26.188 telemetry is not the exact pre-envelope HTTP-400 shape")
    shape = telemetry.get("response_shape")
    if not isinstance(shape, dict) or (
        shape.get("response_envelope_captured_before_content_parse") is not False
        or shape.get("response_envelope_schema_valid") is not False
        or shape.get("redacted_response_envelope") is not None
        or shape.get("response_envelope_schema") is not None
        or shape.get("provider_native_tool_call_observed") is not None
    ):
        raise ValueError("v26.188 telemetry unexpectedly contains a response Envelope")


def _validate_bound_file(root: Path, descriptor: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    path = _safe_bound_path(root, str(descriptor["relative_path"]))
    if not path.is_file():
        raise ValueError("v26.188 descriptor target is not a regular file")
    payload = path.read_bytes()
    if len(payload) != descriptor["byte_count"] or _sha256_bytes(payload) != descriptor["sha256"]:
        raise ValueError("v26.188 descriptor does not bind actual bytes")
    decoded = json.loads(payload)
    canonical = _canonical_bytes(decoded)
    if payload not in (canonical, canonical[:-1]):
        raise ValueError("v26.188 bound descriptor JSON is not a frozen canonical form")
    return path, cast(dict[str, Any], decoded)


def _validate_artifact_payload(
    root: Path,
    descriptor: evidence.ArtifactBackedRawExecutionDescriptor
    | evidence.ArtifactBackedJobResultDescriptor,
    model_type: type[BaseModel],
) -> BaseModel:
    path = _safe_bound_path(root, descriptor.artifact_relative_path)
    payload = path.read_bytes()
    if (
        len(payload) != descriptor.artifact_byte_count
        or _sha256_bytes(payload) != descriptor.artifact_sha256
    ):
        raise ValueError("v26.188 Raw/Result descriptor bytes differ")
    model = model_type.model_validate(json.loads(payload))
    if evidence.canonical_model_bytes(model) != payload:
        raise ValueError("v26.188 Raw/Result bytes are not canonical model bytes")
    return model


def _assert_job_parentage(
    *,
    job: CapabilityDevelopmentJob,
    record: dict[str, Any],
    bundle: evidence.ArtifactBackedEvidenceBundle,
    manifest: CapabilityDevelopmentJobManifest,
    runner: JobBoundRunnerContract,
) -> None:
    expected = (
        job.job_id,
        manifest.manifest_id,
        runner.runner_id,
        job.execution_package_id,
        job.source_package_artifact_id,
        job.replica_index,
        job.raw_namespace,
        job.result_namespace,
    )
    record_parents = (
        record["job_id"],
        record["manifest_id"],
        record["runner_id"],
        record["execution_package_id"],
        record["source_package_artifact_id"],
        record["replica_index"],
        bundle.raw.raw_namespace,
        bundle.result.result_namespace,
    )
    row = bundle.row
    row_parents = (
        row.job_id,
        row.manifest_id,
        row.runner_id,
        row.execution_package_id,
        row.source_package_artifact_id,
        row.replica_index,
        row.raw_namespace,
        row.result_namespace,
    )
    if record_parents != expected or row_parents != expected:
        raise ValueError("v26.188 Job parent chain differs from frozen Manifest")
    if (
        bundle.raw.job_id != job.job_id
        or bundle.result.job_id != job.job_id
        or bundle.trace.job_id != job.job_id
        or bundle.result.raw_execution_id != bundle.raw.raw_execution_id
        or bundle.trace.raw_execution_id != bundle.raw.raw_execution_id
        or bundle.trace.result_id != bundle.result.result_id
        or row.raw_execution_id != bundle.raw.raw_execution_id
        or row.result_id != bundle.result.result_id
        or row.trace_id != bundle.trace.trace_id
    ):
        raise ValueError("v26.188 Raw/Result/Trace/Outcome DAG parent differs")


def _audit_job(
    *,
    root: Path,
    artifact_root: Path,
    ordinal: int,
    job: CapabilityDevelopmentJob,
    manifest: CapabilityDevelopmentJobManifest,
    runner: JobBoundRunnerContract,
) -> IndependentJobReplayRow:
    suffix = job.job_id.split(":", 1)[-1]
    record_path = root / "job_records" / f"{suffix}.json"
    checkpoint_path = root / "checkpoints" / f"job_{ordinal:03d}.json"
    record = cast(dict[str, Any], _load(record_path))
    checkpoint = cast(dict[str, Any], _load(checkpoint_path))
    _require_identity(
        record,
        field="record_id",
        prefix="finance_v26_artifact_backed_online_job_execution:",
    )
    bundle = evidence.ArtifactBackedEvidenceBundle.model_validate(record["bundle"])
    _assert_job_parentage(
        job=job,
        record=record,
        bundle=bundle,
        manifest=manifest,
        runner=runner,
    )
    if checkpoint != {
        "job_id": job.job_id,
        "ordinal": ordinal,
        "raw_execution_id": bundle.raw.raw_execution_id,
        "record_id": record["record_id"],
        "result_id": bundle.result.result_id,
        "terminal_kind": "provider_identity_failure",
    }:
        raise ValueError("v26.188 checkpoint differs from its exact Job record")
    raw_payload = cast(
        RawExecutionEvidencePayload,
        _validate_artifact_payload(
            artifact_root,
            bundle.raw,
            RawExecutionEvidencePayload,
        ),
    )
    result_payload = cast(
        evidence.ArtifactBackedJobResultPayload,
        _validate_artifact_payload(
            artifact_root,
            bundle.result,
            evidence.ArtifactBackedJobResultPayload,
        ),
    )
    if (
        raw_payload.payload_id != bundle.raw.payload_id
        or result_payload.payload_id != bundle.result.payload_id
        or raw_payload.job_id != job.job_id
        or result_payload.job_id != job.job_id
        or raw_payload.terminal_kind != "provider_identity_failure"
        or result_payload.terminal_kind != "provider_identity_failure"
        or raw_payload.component_attempts
        or bundle.trace.component_attempts
        or bundle.trace.correction_count != 0
        or len(bundle.trace.failure_loci) != 1
        or bundle.trace.failure_loci[0].stage != "model_identity"
        or bundle.trace.failure_loci[0].reason_code != "provider_identity_failure"
        or bundle.trace.failure_loci[0].source_descriptor_id != bundle.raw.raw_execution_id
        or bundle.row.terminal_locus_id != bundle.trace.failure_loci[0].locus_id
        or bundle.row.final_qualified_valid is not None
        or bundle.row.task_verifier_invoked
        or bundle.row.first_policy_qualified_valid
        or bundle.row.bounded_policy_qualified_valid
    ):
        raise ValueError("v26.188 typed terminal evidence differs")
    if (
        record["terminal_kind"] != "provider_identity_failure"
        or record["execution_error"] != "exact_model_mismatch_or_missing"
        or record["provider_call_count"] != 1
        or record["transport_inclusive_invocation_count"] != 1
        or record["cumulative_provider_tokens"] != 0
        or record["stage_two_provider_calls"] != 0
        or record["privacy_rejection_count"] != 0
        or record["runtime_component_attempts"]
        or record["source_outcome"] is not None
        or len(record["provider_telemetry"]) != 1
    ):
        raise ValueError("v26.188 Job execution terminal projection differs")
    descriptors = (
        record["provider_envelope_artifacts"],
        record["public_payload_projection_artifacts"],
        record["transport_invocation_artifacts"],
    )
    if any(len(items) != 1 for items in descriptors):
        raise ValueError("v26.188 Job does not have exactly one online descriptor triple")
    _, envelope = _validate_bound_file(root, descriptors[0][0])
    _, projection = _validate_bound_file(root, descriptors[1][0])
    _, transport = _validate_bound_file(root, descriptors[2][0])
    _require_identity(
        envelope,
        field="envelope_id",
        prefix="finance_v26_privacy_first_provider_envelope:",
    )
    dynamic = cast(dict[str, Any], envelope["dynamic_certificate"])
    request = cast(dict[str, Any], envelope["request_binding_certificate"])
    _require_identity(
        dynamic,
        field="certificate_id",
        prefix="finance_v26_privacy_first_dynamic_request_certificate:",
    )
    _require_identity(
        request,
        field="certificate_id",
        prefix="two_stage_stage_one_request_certificate:",
    )
    _require_identity(
        projection,
        field="projection_id",
        prefix="finance_v26_public_payload_projection:",
    )
    _require_identity(
        transport,
        field="certificate_id",
        prefix="finance_v26_s1_transport_invocation_certificate:",
    )
    telemetry = cast(dict[str, Any], envelope["provider_telemetry"])
    validate_http_400_telemetry(telemetry)
    if telemetry != record["provider_telemetry"][0]:
        raise ValueError("v26.188 embedded Provider telemetry differs")
    if (
        envelope["job_id"] != job.job_id
        or envelope["provider_call_index"] != 0
        or envelope["logical_request_index"] != 0
        or envelope["request_kind"] != "semantic_proposal"
        or envelope["failure_artifact"] is not None
        or envelope["raw_http_body_persisted"] is not False
        or envelope["raw_request_body_persisted"] is not False
        or envelope["payload_content_persisted"] is not False
        or envelope["public_content_hash"] is not None
        or envelope["public_content_length"] is not None
        or envelope["private_reasoning_content_persisted"] is not False
        or envelope["private_reasoning_content_hashed"] is not False
        or envelope["stage_two_provider_call_count"] != 0
        or request["endpoint"] != "https://api.deepseek.com/v1/chat/completions"
        or request["request_model"] != "deepseek-v4-flash"
        or request["thinking_type"] != "enabled"
        or request["request_max_tokens"] != 16384
        or request["response_format_type"] != "json_object"
        or request["model_discovery_call_required"] is not False
        or request["fallback_forbidden"] is not True
        or request["raw_request_body_persisted"] is not False
        or request["request_body_fields"]
        != [
            "max_tokens",
            "messages",
            "model",
            "response_format",
            "temperature",
            "thinking",
            "top_p",
        ]
        or telemetry["request_hash"] != envelope["prompt_sha256"]
        or telemetry["request_hash"] != dynamic["request_prompt_sha256"]
        or telemetry["request_hash"] != request["prompt_sha256"]
    ):
        raise ValueError("v26.188 Provider request certificate or no-payload shape differs")
    if (
        projection["job_id"] != job.job_id
        or projection["provider_envelope_id"] != envelope["envelope_id"]
        or projection["provider_call_index"] != 0
        or projection["projection_status"] != "provider_failure_no_payload"
        or projection["failure_family"] != "provider_or_completion_failure"
        or projection["failure_subtype"] != "no_public_payload_returned"
        or projection["response_payload"] is not None
        or projection["invalid_payload_content_persisted"] is not False
        or projection["invalid_payload_key_persisted"] is not False
        or projection["private_reasoning_content_persisted"] is not False
    ):
        raise ValueError("v26.188 public no-payload projection differs")
    if (
        transport["job_id"] != job.job_id
        or transport["transport_invocation_index"] != 0
        or transport["persisted_before_transport_invocation"] is not True
        or transport["is_transport_replacement"] is not False
        or transport["provider_calls_before_invocation"] != 0
        or transport["stage_two_provider_calls_before_invocation"] != 0
        or transport["request_binding_certificate_id"] != request["certificate_id"]
        or transport["inner_dynamic_certificate_id"] != dynamic["certificate_id"]
        or transport["request_prompt_sha256"] != telemetry["request_hash"]
        or transport["runner_contract_id"] != runner.runner_id
    ):
        raise ValueError("v26.188 transport certificate parent differs")
    values = {
        "ordinal": ordinal,
        "job_id": job.job_id,
        "record_id": record["record_id"],
        "raw_execution_id": bundle.raw.raw_execution_id,
        "result_id": bundle.result.result_id,
        "trace_id": bundle.trace.trace_id,
        "outcome_row_id": bundle.row.row_id,
        "provider_envelope_id": envelope["envelope_id"],
        "public_projection_id": projection["projection_id"],
        "transport_certificate_id": transport["certificate_id"],
        "request_body_sha256": request["canonical_request_body_sha256"],
        "request_body_byte_count": request["canonical_request_body_bytes"],
        "http_status": 400,
        "http_success": False,
        "response_envelope_observed": False,
        "model_identity_evaluable": False,
        "observed_wrong_model_response": False,
        "public_payload_observed": False,
        "usage_observed": False,
        "raw_http_body_persisted": False,
        "terminal_kind": "provider_identity_failure",
        "frozen_reason_code": "provider_identity_failure",
        "q_first_value": False,
        "q_bounded_value": False,
        "exact_parent_chain_match": True,
        "raw_result_byte_match_count": 2,
        "descriptor_byte_match_count": 3,
    }
    return cast(
        IndependentJobReplayRow,
        _identity_model(
            IndependentJobReplayRow,
            values,
            field="row_id",
            prefix="finance_v26_188_independent_job_replay:",
        ),
    )


def _recompute_frozen_evaluation(
    *, root: Path, rows: tuple[IndependentJobReplayRow, ...]
) -> dict[str, Any]:
    frozen = cast(dict[str, Any], _load(root / "empirical_evaluation.json"))
    _require_identity(
        frozen,
        field="evaluation_id",
        prefix="capability_artifact_backed_empirical_evaluation:",
    )
    terminal_counts = dict(Counter(item.terminal_kind for item in rows))
    expected = {
        "artifact_byte_match_count": EXPECTED_ARTIFACT_FILE_COUNT,
        "artifact_file_count": EXPECTED_ARTIFACT_FILE_COUNT,
        "contract_id": EXPECTED_CONTRACT_ID,
        "empirical": True,
        "evaluation_id": EXPECTED_EVALUATION_ID,
        "evidence_kind": "empirical_execution",
        "exact_job_count": EXPECTED_JOB_COUNT,
        "manifest_id": EXPECTED_MANIFEST_ID,
        "q_bounded_correction_fraction": "0/192",
        "q_bounded_correction_numerator": 0,
        "q_first_fraction": "0/192",
        "q_first_numerator": 0,
        "registry_id": EXPECTED_REGISTRY_ID,
        "runner_id": EXPECTED_RUNNER_ID,
        "schema_version": "authoritative_artifact_backed_outcome.v3",
        "terminal_kind_counts": terminal_counts,
    }
    if frozen != expected:
        raise ValueError("v26.188 frozen empirical evaluation differs from independent replay")
    report = cast(dict[str, Any], _load(root / "report.json"))
    if (
        report["job_count"] != 192
        or report["raw_count"] != 192
        or report["result_count"] != 192
        or report["typed_outcome_count"] != 192
        or report["provider_calls"] != 192
        or report["stage_two_provider_calls"] != 0
        or report["terminal_partition"] != terminal_counts
        or report["q_first_fraction"] != "0/192"
        or report["q_bounded_correction_fraction"] != "0/192"
    ):
        raise ValueError("v26.188 Report differs from independent replay")
    return frozen


def _formal_manifest(payloads: dict[str, bytes]) -> FormalArtifactManifest:
    files = tuple(
        FileBinding(relative_path=name, sha256=_sha256_bytes(value), byte_count=len(value))
        for name, value in sorted(payloads.items())
    )
    root = canonical_hash(
        [item.model_dump(mode="json", warnings=False) for item in files],
        prefix="finance_v26_189_postrun_artifact_root:",
    )
    values = {
        "artifact_root": root,
        "files": files,
        "file_count": len(files),
        "total_byte_count": sum(item.byte_count for item in files),
    }
    return cast(
        FormalArtifactManifest,
        _identity_model(
            FormalArtifactManifest,
            values,
            field="manifest_id",
            prefix="finance_v26_189_postrun_artifact_manifest:",
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
    package_root = _resolve_package_root(package_root)
    repository_root = package_root.parent
    output_dir = output_dir.resolve()
    if os.environ.get("DEEPSEEK_API_KEY"):
        raise ValueError("v26.189 independent postrun audit requires credential removal")
    if output_dir.exists():
        raise FileExistsError(f"v26.189 output directory already exists: {output_dir}")
    if len(source_commit) != 40 or len(source_tree) != 40:
        raise ValueError("v26.189 source identity is incomplete")
    if _git_tree(repository_root, source_commit) != source_tree:
        raise ValueError("v26.189 source commit and Tree differ")
    if (
        _git_tree(repository_root, V188_SOURCE_COMMIT) != V188_SOURCE_TREE
        or _git_tree(repository_root, V188_ARTIFACT_COMMIT) != V188_ARTIFACT_TREE
    ):
        raise ValueError("v26.188 frozen Git identities differ")
    authorization, authorization_bytes = _authorization(external_audit_path)
    v188_root = package_root / V188_DIR
    before = _directory_manifest(v188_root)
    registry, contract, manifest, runner = _load_frozen_parents(package_root)
    jobs_by_id = {item.job_id: item for item in manifest.jobs}
    if len(jobs_by_id) != EXPECTED_JOB_COUNT or set(jobs_by_id) != set(manifest.expected_job_ids):
        raise ValueError("v26.188 frozen Manifest Job set differs")
    jobs = tuple(jobs_by_id[job_id] for job_id in manifest.expected_job_ids)
    artifact_root = v188_root / "artifact_backed_evidence"
    rows = tuple(
        _audit_job(
            root=v188_root,
            artifact_root=artifact_root,
            ordinal=ordinal,
            job=job,
            manifest=manifest,
            runner=runner,
        )
        for ordinal, job in enumerate(jobs)
    )
    _recompute_frozen_evaluation(root=v188_root, rows=rows)
    after = _directory_manifest(v188_root)
    if before != after:
        raise ValueError("v26.188 directory changed during independent audit")
    freeze = cast(
        PredecessorFreezeAudit,
        _identity_model(
            PredecessorFreezeAudit,
            {
                "authorization_id": authorization.authorization_id,
                "source_commit": V188_SOURCE_COMMIT,
                "source_tree": V188_SOURCE_TREE,
                "artifact_commit": V188_ARTIFACT_COMMIT,
                "artifact_tree": V188_ARTIFACT_TREE,
                "directory_manifest_id": before.manifest_id,
                "exact_file_count": EXPECTED_FILE_COUNT,
                "exact_byte_count": EXPECTED_BYTE_COUNT,
                "directory_unchanged_after_audit": True,
                "historical_file_mutation_count": 0,
                "provider_calls": 0,
            },
            field="audit_id",
            prefix="finance_v26_188_online_predecessor_freeze:",
        ),
    )
    job_replay = cast(
        IndependentJobReplayCatalog,
        _identity_model(
            IndependentJobReplayCatalog,
            {"manifest_id": manifest.manifest_id, "rows": rows},
            field="catalog_id",
            prefix="finance_v26_188_independent_job_replay_catalog:",
        ),
    )
    evidence_replay = cast(
        EvidenceReplayAudit,
        _identity_model(
            EvidenceReplayAudit,
            {
                "contract_id": contract.contract_id,
                "registry_id": registry.registry_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "job_record_count": 192,
                "checkpoint_count": 192,
                "raw_count": 192,
                "result_count": 192,
                "raw_result_file_count": 384,
                "raw_result_byte_match_count": sum(
                    item.raw_result_byte_match_count for item in rows
                ),
                "provider_envelope_count": 192,
                "public_projection_count": 192,
                "transport_certificate_count": 192,
                "descriptor_byte_match_count": sum(
                    item.descriptor_byte_match_count for item in rows
                ),
                "exact_parent_chain_match_count": sum(
                    item.exact_parent_chain_match for item in rows
                ),
                "typed_outcome_count": 192,
                "terminal_projection_count": 192,
                "recomputed_evaluation_id": EXPECTED_EVALUATION_ID,
                "frozen_evaluation_exact_match": True,
                "v188_online_helpers_used_as_outcome_oracle": False,
                "provider_calls": 0,
            },
            field="audit_id",
            prefix="finance_v26_188_independent_evidence_replay:",
        ),
    )
    raw_events = cast(
        RawEventDecompositionAudit,
        _identity_model(
            RawEventDecompositionAudit,
            {
                "stage_one_request_count": len(rows),
                "stage_two_request_count": 0,
                "http_error_count": len(rows),
                "http_400_count": sum(item.http_status == 400 for item in rows),
                "http_success_count": sum(item.http_success for item in rows),
                "response_envelope_count": sum(item.response_envelope_observed for item in rows),
                "model_identity_evaluable_count": sum(
                    item.model_identity_evaluable for item in rows
                ),
                "observed_wrong_model_response_count": sum(
                    item.observed_wrong_model_response for item in rows
                ),
                "public_payload_count": sum(item.public_payload_observed for item in rows),
                "usage_observed_count": sum(item.usage_observed for item in rows),
                "total_usage_tokens": 0,
                "raw_http_body_persisted_count": sum(item.raw_http_body_persisted for item in rows),
                "raw_request_body_persisted_count": 0,
                "frozen_provider_identity_failure_count": sum(
                    item.terminal_kind == "provider_identity_failure" for item in rows
                ),
                "actual_responding_model": "unknown",
                "server_side_rejection_detail": "unavailable_not_persisted",
                "provider_calls_during_audit": 0,
            },
            field="audit_id",
            prefix="finance_v26_188_independent_raw_event_decomposition:",
        ),
    )
    estimands = cast(
        EstimandSeparationAudit,
        _identity_model(
            EstimandSeparationAudit,
            {
                "exact_job_denominator": 192,
                "q_job_first_numerator": sum(item.q_first_value for item in rows),
                "q_job_first_fraction": "0/192",
                "q_job_bounded_numerator": sum(item.q_bounded_value for item in rows),
                "q_job_bounded_fraction": "0/192",
                "model_endpoint_denominator": sum(item.model_identity_evaluable for item in rows),
                "semantic_qualified_numerator": 0,
                "semantic_capability_fraction": "null",
                "semantic_capability_instantiated": False,
                "semantic_null_is_not_zero": True,
                "capability_depth_instantiated": False,
            },
            field="audit_id",
            prefix="finance_v26_188_independent_estimand_separation:",
        ),
    )
    gates = cast(
        LayeredGateAudit,
        _identity_model(
            LayeredGateAudit,
            {
                "job_exact_set": "PASS",
                "raw_result_completeness": "PASS",
                "artifact_byte_authority": "PASS",
                "typed_terminal_totality": "PASS",
                "parent_chain_reconstruction": "PASS",
                "frozen_terminal_admission": "PASS",
                "provider_request_acceptance": "FAIL",
                "model_endpoint_observability": "UNINSTANTIATED",
                "semantic_capability_measurement": "UNAVAILABLE",
                "mapper_state_admission": "NOT_AUTHORIZED",
                "all_evidence_authority_gates_passed": True,
                "capability_measurement_gate_passed": False,
            },
            field="audit_id",
            prefix="finance_v26_188_independent_layered_gate:",
        ),
    )
    static_gates = {
        "external_audit_byte_binding": True,
        "v188_git_source_and_artifact_freeze": True,
        "v188_directory_geometry_and_bytes": True,
        "exact_manifest_job_set": True,
        "job_record_identity_reconstruction": True,
        "checkpoint_exactness": True,
        "raw_result_canonical_byte_authority": True,
        "provider_projection_transport_byte_authority": True,
        "provider_certificate_parentage": True,
        "artifact_backed_dag_parentage": True,
        "typed_terminal_totality": True,
        "frozen_empirical_evaluation_reconstruction": True,
        "raw_http_event_decomposition": True,
        "job_and_semantic_estimand_separation": True,
        "zero_provider_calls": True,
        "zero_historical_reclassification": True,
        "zero_downstream_admission": True,
    }
    static = cast(
        StaticAudit,
        _identity_model(
            StaticAudit,
            {
                "gates": static_gates,
                "passed_gate_count": len(static_gates),
                "failed_gate_count": 0,
                "provider_calls": 0,
                "confirmation_payload_access_count": 0,
                "historical_reclassification_count": 0,
                "mapper_rows": 0,
                "state_rows": 0,
                "contribution_rows": 0,
                "vtdo_rows": 0,
            },
            field="audit_id",
            prefix="finance_v26_188_independent_static_audit:",
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
                "recommended_future_audit": RECOMMENDED_FUTURE_AUDIT,
                "recommended_future_audit_authorized_now": False,
                "provider_rerun_authorized": False,
                "recovery_jobs_authorized": False,
                "request_route_repair_authorized": False,
                "mapper_state_frequency_contribution_vtdo_authorized": False,
            },
            field="transition_id",
            prefix="finance_v26_188_postrun_transition:",
        ),
    )
    report = cast(
        PostrunIndependentAuditReport,
        _identity_model(
            PostrunIndependentAuditReport,
            {
                "run_id": RUN_ID,
                "authorization_id": authorization.authorization_id,
                "predecessor_freeze_id": freeze.audit_id,
                "directory_manifest_id": before.manifest_id,
                "job_replay_catalog_id": job_replay.catalog_id,
                "evidence_replay_audit_id": evidence_replay.audit_id,
                "raw_event_decomposition_audit_id": raw_events.audit_id,
                "estimand_separation_audit_id": estimands.audit_id,
                "layered_gate_audit_id": gates.audit_id,
                "static_audit_id": static.audit_id,
                "transition_id": transition.transition_id,
                "online_execution_and_evidence_chain": "PASS",
                "model_semantic_capability_observation": "UNINSTANTIATED",
                "formal_end_to_end_q_first": "0/192",
                "formal_end_to_end_q_bounded": "0/192",
                "model_endpoint_conditional_semantic_q": "null",
                "first_blocker": "http_400_before_response_envelope_and_model_endpoint",
                "provider_calls": 0,
                "decision": CURRENT_DECISION,
            },
            field="report_id",
            prefix="finance_v26_188_postrun_independent_audit_report:",
        ),
    )
    payloads = {
        "external_v26_188_result_audit.txt": authorization_bytes,
        "external_audit_authorization.json": _canonical_bytes(authorization),
        "v188_directory_manifest.json": _canonical_bytes(before),
        "v188_predecessor_freeze.json": _canonical_bytes(freeze),
        "independent_job_replay_catalog.json": _canonical_bytes(job_replay),
        "independent_evidence_replay_audit.json": _canonical_bytes(evidence_replay),
        "independent_raw_event_decomposition_audit.json": _canonical_bytes(raw_events),
        "independent_estimand_separation_audit.json": _canonical_bytes(estimands),
        "independent_layered_gate_audit.json": _canonical_bytes(gates),
        "static_audit.json": _canonical_bytes(static),
        "prospective_transition.json": _canonical_bytes(transition),
        "report.json": _canonical_bytes(report),
        "source_identity.json": _canonical_bytes(
            {
                "source_commit": source_commit,
                "source_tree": source_tree,
                "schema_version": "artifact_backed_postrun_source_identity.v1",
            }
        ),
    }
    artifact_manifest = _formal_manifest(payloads)
    payloads["artifact_manifest.json"] = _canonical_bytes(artifact_manifest)
    write_immutable_artifact_directory(output_dir, payloads)
    return BuildProducts(
        authorization=authorization,
        directory_manifest=before,
        freeze=freeze,
        job_replay=job_replay,
        evidence_replay=evidence_replay,
        raw_events=raw_events,
        estimands=estimands,
        gates=gates,
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
