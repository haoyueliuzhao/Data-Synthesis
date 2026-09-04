# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any, Final, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = (
    "fresh_exact_v209_subsequent_action_evidence_domain_closure_independent_audit.v1"
)
CONSUMED_STAGE: Final = "fresh_exact_v209_subsequent_action_parser_reference_evidence_domain_closure_independent_audit_only"
NEXT_STAGE: Final = "fresh_exact_v209_unbound_provider_failure_source_authority_and_recovery_population_preflight_only"
DECISION_VALUE: Final = (
    "v26_227_exact_three_host_failure_evidence_domain_closure_independently_confirmed"
)

EXTERNAL_REVIEW_SHA256: Final = "69aaedaadd50882f5ba154ebd6d86fe87b239dfc75676d529d1dbd7f3bb02e94"
EXTERNAL_REVIEW_BYTE_COUNT: Final = 15_519
OPERATOR_DIRECTIVE: Final = "参照审计开展后续实验"
OPERATOR_DIRECTIVE_SHA256: Final = (
    "8e30b645e46c5682c61a1e4ca820e51aa5c8b07bfa052274b665ebd20afd33fa"
)
OPERATOR_DIRECTIVE_BYTE_COUNT: Final = 30

V227_RUN_ID: Final = "finance_v26_227_fresh_exact_v209_subsequent_action_parser_reference_evidence_domain_closure_preflight_v2_20260904"
V227_SOURCE_COMMIT: Final = "78bd5edf524d899a16809c793af7cfa6c333683a"
V227_SOURCE_TREE: Final = "ea4ac2e38582144c03855e6991ce9fe49d0f3a3a"
V227_MANIFEST_ID: Final = "finance_v26_227_artifact_manifest:3a4080aabfcfcc11750358961818956089c7c3ff154d168b9c00f3cb5bb25bd8"
V227_ARTIFACT_ROOT: Final = (
    "finance_v26_227_artifact_root:1e4550aaa3db50523b4a9c8ba7eefad323d2bb0d377954be71238c46e8917e94"
)
V227_DECISION_ID: Final = (
    "finance_v26_227_decision:a1ba81374ac7e0c717b3551f21d1cf116f1595a856aeb7081378788f75e1e2d9"
)
V227_TRANSITION_ID: Final = (
    "finance_v26_227_transition:e17860f5577f6e2aeb2d8251258ffb3997428b4dae3afc7fed5bdc5b0cfa763e"
)
V227_FILE_COUNT: Final = 38
V227_MEMBER_COUNT: Final = 37
V227_TOTAL_BYTES: Final = 3_715_790
V227_MEMBER_BYTES: Final = 3_708_807
V227_MANIFEST_SHA256: Final = "4d6f2b2dd58e2cc7c2e0e44be3c4522ecce539819a2f4bf256a9964348c65210"
V227_MANIFEST_BYTE_COUNT: Final = 6_983
TERMINAL_REGISTRY_ID: Final = "fresh_kernel_terminal_registry:a9d3089011f34b114b4b8264c09eb6b4c5875dd6978de0a2c3fe316577203152"
TERMINAL_REGISTRY_FILE_SHA256: Final = (
    "810edea998d24a8c3224a1d378ce2cce76dfc405e62c5b8f2908ca815035b617"
)

HOST_ORDINALS: Final = (6, 22, 149)
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
    "A0_EXACT_V227_FREEZE",
    "A1_DETACHED_EXACT_SOURCE_REBUILD",
    "A2_INDEPENDENT_V226_SOURCE_PARTITION",
    "A3_INDEPENDENT_EIGHT_CALL_REPLAY",
    "A4_INDEPENDENT_EVIDENCE_TERMINAL_DERIVATION",
    "A5_INDEPENDENT_FIVE_LAYER_RECONSTRUCTION",
    "A6_DIRECT_ATTACKS_AND_SCOPE_BOUNDARY",
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


class Identified(FrozenModel):
    @classmethod
    def prefix(cls) -> str:
        raise NotImplementedError

    def check_id(self, field: str) -> None:
        if getattr(self, field) != identity(self, field, self.prefix()):
            raise ValueError(f"{type(self).__name__} identity differs")


class ExternalAuthorization(Identified):
    authorization_id: str
    external_review_sha256: Literal[
        "69aaedaadd50882f5ba154ebd6d86fe87b239dfc75676d529d1dbd7f3bb02e94"
    ] = EXTERNAL_REVIEW_SHA256
    external_review_byte_count: Literal[15519] = EXTERNAL_REVIEW_BYTE_COUNT
    operator_directive: Literal["参照审计开展后续实验"] = OPERATOR_DIRECTIVE
    operator_directive_sha256: Literal[
        "8e30b645e46c5682c61a1e4ca820e51aa5c8b07bfa052274b665ebd20afd33fa"
    ] = OPERATOR_DIRECTIVE_SHA256
    operator_directive_byte_count: Literal[30] = OPERATOR_DIRECTIVE_BYTE_COUNT
    consumed_stage: Literal[
        "fresh_exact_v209_subsequent_action_parser_reference_evidence_domain_closure_independent_audit_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized: Literal[0] = 0
    online_execution_authorized: Literal[False] = False
    schema_version: Literal[
        "fresh_exact_v209_subsequent_action_evidence_domain_closure_independent_audit.v1"
    ] = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_228_external_independent_audit_authorization:"

    @model_validator(mode="after")
    def validate_all(self) -> ExternalAuthorization:
        if sha(self.operator_directive.encode()) != self.operator_directive_sha256:
            raise ValueError("directive differs")
        self.check_id("authorization_id")
        return self


class V227FreezeAudit(Identified):
    audit_id: str
    authorization_id: str
    run_id: Literal[
        "finance_v26_227_fresh_exact_v209_subsequent_action_parser_reference_evidence_domain_closure_preflight_v2_20260904"
    ] = V227_RUN_ID
    source_commit: Literal["78bd5edf524d899a16809c793af7cfa6c333683a"] = V227_SOURCE_COMMIT
    source_tree: Literal["ea4ac2e38582144c03855e6991ce9fe49d0f3a3a"] = V227_SOURCE_TREE
    file_count: Literal[38] = V227_FILE_COUNT
    total_bytes: Literal[3715790] = V227_TOTAL_BYTES
    manifest_member_count: Literal[37] = V227_MEMBER_COUNT
    manifest_member_bytes: Literal[3708807] = V227_MEMBER_BYTES
    manifest_id: Literal[
        "finance_v26_227_artifact_manifest:3a4080aabfcfcc11750358961818956089c7c3ff154d168b9c00f3cb5bb25bd8"
    ] = V227_MANIFEST_ID
    manifest_sha256: Literal["4d6f2b2dd58e2cc7c2e0e44be3c4522ecce539819a2f4bf256a9964348c65210"] = (
        V227_MANIFEST_SHA256
    )
    manifest_byte_count: Literal[6983] = V227_MANIFEST_BYTE_COUNT
    artifact_root: Literal[
        "finance_v26_227_artifact_root:1e4550aaa3db50523b4a9c8ba7eefad323d2bb0d377954be71238c46e8917e94"
    ] = V227_ARTIFACT_ROOT
    decision_id: Literal[
        "finance_v26_227_decision:a1ba81374ac7e0c717b3551f21d1cf116f1595a856aeb7081378788f75e1e2d9"
    ] = V227_DECISION_ID
    transition_id: Literal[
        "finance_v26_227_transition:e17860f5577f6e2aeb2d8251258ffb3997428b4dae3afc7fed5bdc5b0cfa763e"
    ] = V227_TRANSITION_ID
    path_matches: Literal[38] = 38
    sha256_matches: Literal[37] = 37
    byte_count_matches: Literal[37] = 37
    candidate_report_used_as_oracle: Literal[False] = False
    candidate_gate_used_as_oracle: Literal[False] = False
    candidate_control_audit_used_as_oracle: Literal[False] = False
    candidate_negative_audit_used_as_oracle: Literal[False] = False
    candidate_saved_evidence_used_as_replay_input: Literal[False] = False
    candidate_host_rows_used_as_source_selection: Literal[False] = False
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_228_v227_freeze_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> V227FreezeAudit:
        self.check_id("audit_id")
        return self


class SourceMember(FrozenModel):
    relative_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class SourceIdentity(Identified):
    source_identity_id: str
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    implementation_members: tuple[SourceMember, SourceMember]
    member_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    working_tree_byte_matches: Literal[2] = 2

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_228_source_identity:"

    @model_validator(mode="after")
    def validate_all(self) -> SourceIdentity:
        paths = tuple(row.relative_path for row in self.implementation_members)
        rows = tuple(row.model_dump(mode="json") for row in self.implementation_members)
        if paths != tuple(sorted(set(paths))) or self.member_set_sha256 != sha(
            canonical_bytes(rows)
        ):
            raise ValueError("source member set differs")
        self.check_id("source_identity_id")
        return self


class ImplementationBinding(Identified):
    binding_id: str
    source_identity_id: str
    implementation_files: tuple[str, str]
    required_independent_symbols: tuple[str, ...] = Field(min_length=8)
    v227_control_helper_calls: Literal[0] = 0
    v227_attack_helper_calls: Literal[0] = 0
    v227_report_oracle_calls: Literal[0] = 0
    v227_gate_oracle_calls: Literal[0] = 0
    network_symbols: Literal[0] = 0
    credential_symbols: Literal[0] = 0

    @classmethod
    def prefix(cls) -> str:
        return "fresh_v26_228_independent_audit_implementation_binding:"

    @model_validator(mode="after")
    def validate_all(self) -> ImplementationBinding:
        if self.implementation_files != tuple(sorted(set(self.implementation_files))):
            raise ValueError("implementation file set differs")
        self.check_id("binding_id")
        return self


class DetachedRebuildAudit(Identified):
    audit_id: str
    v227_freeze_audit_id: str
    archived_source_files: int = Field(gt=0)
    saved_file_count: Literal[38] = 38
    rebuilt_file_count: Literal[38] = 38
    saved_bytes: Literal[3715790] = V227_TOTAL_BYTES
    rebuilt_bytes: Literal[3715790] = V227_TOTAL_BYTES
    path_matches: Literal[38] = 38
    sha256_matches: Literal[38] = 38
    actual_byte_matches: Literal[38] = 38
    manifest_members_revalidated: Literal[37] = 37
    credential_like_environment_keys: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    provider_calls: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_228_detached_rebuild_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> DetachedRebuildAudit:
        self.check_id("audit_id")
        return self


class SourceRow(FrozenModel):
    ordinal: int
    job_id: str
    record_id: str
    failure_kind: str
    failure_file_sha256: str
    failure_file_byte_count: int
    provider_call_count: int
    provider_call_ids: tuple[str, ...]


class SourcePartitionAudit(Identified):
    audit_id: str
    v227_freeze_audit_id: str
    host_rows: tuple[SourceRow, SourceRow, SourceRow]
    host_ordinals: tuple[int, int, int] = HOST_ORDINALS
    host_source_set_sha256: str
    exclusion_count: Literal[33] = 33
    exclusion_failure_kind: Literal["unbound_provider_failure"] = "unbound_provider_failure"
    exclusion_exact_kind_count: Literal[33] = 33
    exclusion_set_sha256: str
    exact_set_equality: Literal[True] = True
    v227_control_audit_helper_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_228_independent_source_partition_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> SourcePartitionAudit:
        if tuple(row.ordinal for row in self.host_rows) != HOST_ORDINALS:
            raise ValueError("host ordinal set differs")
        self.check_id("audit_id")
        return self


class ReplayRow(FrozenModel):
    ordinal: int
    job_id: str
    invocation_count: int
    phases: tuple[str, ...]
    request_match_count: int
    response_match_count: int
    call_order_match: bool
    success_status_match: bool
    last_state_id: str
    last_candidate_action_ids: tuple[str, ...]
    evidence_kind: str
    derived_terminal: str
    terminal_policy_id: str
    derivation_rule: str
    phase: Literal["subsequent_action"] = "subsequent_action"
    evidence_id: str
    decision_id: str


class ReplayAndDerivationAudit(Identified):
    audit_id: str
    source_partition_audit_id: str
    rows: tuple[ReplayRow, ReplayRow, ReplayRow]
    invocation_count: Literal[8] = 8
    request_hash_match_count: Literal[8] = 8
    response_hash_match_count: Literal[8] = 8
    replay_descriptor_request_hash_matches: Literal[8] = 8
    replay_descriptor_response_hash_matches: Literal[8] = 8
    descriptor_metadata_request_hash_matches: Literal[8] = 8
    descriptor_metadata_response_hash_matches: Literal[8] = 8
    provider_call_id_matches: Literal[8] = 8
    call_ordinal_matches: Literal[8] = 8
    successful_status_matches: Literal[8] = 8
    saved_evidence_byte_matches: Literal[3] = 3
    detached_evidence_byte_matches: Literal[3] = 3
    saved_decision_byte_matches: Literal[3] = 3
    detached_decision_byte_matches: Literal[3] = 3
    terminal_registry_id: Literal[
        "fresh_kernel_terminal_registry:a9d3089011f34b114b4b8264c09eb6b4c5875dd6978de0a2c3fe316577203152"
    ] = TERMINAL_REGISTRY_ID
    terminal_registry_file_sha256: Literal[
        "810edea998d24a8c3224a1d378ce2cce76dfc405e62c5b8f2908ca815035b617"
    ] = TERMINAL_REGISTRY_FILE_SHA256
    reachable_policy_match_count: Literal[3] = 3
    parser_evidence_count: Literal[2] = 2
    reference_evidence_count: Literal[1] = 1
    derived_terminal_count: Literal[3] = 3
    subsequent_action_phase_count: Literal[3] = 3
    v227_replay_helper_calls: Literal[0] = 0
    v227_evidence_helper_calls: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_228_independent_replay_and_derivation_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> ReplayAndDerivationAudit:
        if sum(row.invocation_count for row in self.rows) != 8:
            raise ValueError("replay geometry differs")
        self.check_id("audit_id")
        return self


class LayerMatch(FrozenModel):
    ordinal: int
    layer_kind: str
    relative_path: str
    artifact_id: str
    sha256: str
    byte_count: int
    actual_byte_match: Literal[True] = True
    saved_actual_byte_match: Literal[True] = True
    detached_actual_byte_match: Literal[True] = True
    formal_empirical_row: Literal[False] = False


class LayerReconstructionAudit(Identified):
    audit_id: str
    replay_audit_id: str
    layers: tuple[LayerMatch, ...] = Field(min_length=15, max_length=15)
    layer_count: Literal[15] = 15
    identity_matches: Literal[15] = 15
    actual_byte_matches: Literal[15] = 15
    saved_actual_byte_matches: Literal[15] = 15
    detached_actual_byte_matches: Literal[15] = 15
    raw_before_result_checks: Literal[3] = 3
    v227_layer_helper_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    provider_calls: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_228_independent_layer_reconstruction_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> LayerReconstructionAudit:
        self.check_id("audit_id")
        return self


class AttackResult(FrozenModel):
    name: str
    rejected: Literal[True] = True
    exception_type: str
    rejection_stage: str
    reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_rehashed_layers: int = Field(ge=0, le=5)
    raw_writes: Literal[0] = 0


class NegativeControlAudit(Identified):
    audit_id: str
    results: tuple[AttackResult, ...] = Field(min_length=8, max_length=8)
    attacks: Literal[8] = 8
    rejected: Literal[8] = 8
    accepted: Literal[0] = 0
    rejected_before_raw: Literal[8] = 8
    fully_rehashed_candidate_layers: Literal[5] = 5
    fully_rehashed_terminal_invocations: Literal[1] = 1
    fully_rehashed_evidence_objects: Literal[1] = 1
    fully_rehashed_decision_objects: Literal[1] = 1
    fully_rehashed_authority_rejections: Literal[1] = 1
    v227_attack_helper_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_228_independent_negative_control_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> NegativeControlAudit:
        if tuple(row.name for row in self.results) != NEGATIVE_CONTROL_NAMES:
            raise ValueError("negative-control set differs")
        self.check_id("audit_id")
        return self


class ScopeBoundaryAudit(Identified):
    audit_id: str
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    client_constructions: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    online_authorizations: Literal[0] = 0
    qa_reads: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    historical_v226_writes: Literal[0] = 0
    passed: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_228_scope_boundary_audit:"

    @model_validator(mode="after")
    def validate_all(self) -> ScopeBoundaryAudit:
        self.check_id("audit_id")
        return self


class Gate(FrozenModel):
    name: str
    passed: Literal[True] = True
    evidence_ids: tuple[str, ...]


class GateEvaluation(Identified):
    evaluation_id: str
    gates: tuple[Gate, ...] = Field(min_length=7, max_length=7)
    passed_count: Literal[7] = 7
    failed_count: Literal[0] = 0
    noncompensatory: Literal[True] = True

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_228_gate_evaluation:"

    @model_validator(mode="after")
    def validate_all(self) -> GateEvaluation:
        if tuple(gate.name for gate in self.gates) != GATE_NAMES:
            raise ValueError("gate set differs")
        self.check_id("evaluation_id")
        return self


class Decision(Identified):
    decision_id: str
    gate_evaluation_id: str
    decision: Literal[
        "v26_227_exact_three_host_failure_evidence_domain_closure_independently_confirmed"
    ] = DECISION_VALUE
    online_execution_authorized: Literal[False] = False
    provider_failure_recovery_authorized: Literal[False] = False
    empirical_estimation_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_228_independent_audit_decision:"

    @model_validator(mode="after")
    def validate_all(self) -> Decision:
        self.check_id("decision_id")
        return self


class Transition(Identified):
    transition_id: str
    decision_id: str
    next_stage: Literal[
        "fresh_exact_v209_unbound_provider_failure_source_authority_and_recovery_population_preflight_only"
    ] = NEXT_STAGE
    next_stage_authorized: Literal[False] = False
    separate_external_audit_decision_required: Literal[True] = True
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_228_transition:"

    @model_validator(mode="after")
    def validate_all(self) -> Transition:
        self.check_id("transition_id")
        return self


class Report(Identified):
    report_id: str
    authorization_id: str
    source_identity_id: str
    implementation_binding_id: str
    freeze_audit_id: str
    detached_rebuild_audit_id: str
    source_partition_audit_id: str
    replay_and_derivation_audit_id: str
    layer_reconstruction_audit_id: str
    negative_control_audit_id: str
    scope_boundary_audit_id: str
    gate_evaluation_id: str
    decision_id: str
    transition_id: str
    decision: Literal[
        "v26_227_exact_three_host_failure_evidence_domain_closure_independently_confirmed"
    ] = DECISION_VALUE
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    online_execution_authorized: Literal[False] = False

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_228_independent_audit_report:"

    @model_validator(mode="after")
    def validate_all(self) -> Report:
        self.check_id("report_id")
        return self


class ArtifactMember(FrozenModel):
    relative_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_path(self) -> ArtifactMember:
        path = PurePosixPath(self.relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("unsafe artifact path")
        return self


class ArtifactManifest(Identified):
    manifest_id: str
    run_id: str
    members: tuple[ArtifactMember, ...]
    file_count: int
    total_member_bytes: int
    self_excluding: Literal[True] = True
    manifest_relative_path: Literal["artifact_manifest.json"] = "artifact_manifest.json"
    artifact_root: str
    provider_calls: Literal[0] = 0

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_228_artifact_manifest:"

    @model_validator(mode="after")
    def validate_all(self) -> ArtifactManifest:
        paths = tuple(member.relative_path for member in self.members)
        if (
            paths != tuple(sorted(set(paths)))
            or self.file_count != len(self.members)
            or self.total_member_bytes != sum(member.byte_count for member in self.members)
        ):
            raise ValueError("manifest geometry differs")
        expected_root = canonical_hash(
            tuple(member.model_dump(mode="json") for member in self.members),
            prefix="finance_v26_228_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("artifact root differs")
        self.check_id("manifest_id")
        return self


def artifact_manifest(run_id: str, payloads: Mapping[str, bytes]) -> ArtifactManifest:
    members = tuple(
        ArtifactMember(relative_path=path, sha256=sha(payload), byte_count=len(payload))
        for path, payload in sorted(payloads.items())
    )
    root = canonical_hash(
        tuple(member.model_dump(mode="json") for member in members),
        prefix="finance_v26_228_artifact_root:",
    )
    return make_identity(
        ArtifactManifest,
        {
            "run_id": run_id,
            "members": members,
            "file_count": len(members),
            "total_member_bytes": sum(member.byte_count for member in members),
            "artifact_root": root,
        },
        field="manifest_id",
        prefix=ArtifactManifest.prefix(),
    )
