# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_repaired_full_condition_executable_runner_final_request_contract_continuity_repair_preflight.v1"
CONSUMED_STAGE: Final = "fresh_repaired_full_condition_executable_runner_final_request_contract_continuity_repair_preflight_only"
NEXT_STAGE: Final = "fresh_repaired_full_condition_executable_runner_final_request_contract_continuity_repair_preflight_independent_audit_only"
DECISION: Final = (
    "fresh_repaired_full_condition_executable_runner_final_request_contract_continuity_"
    "repair_preflight_passed_independent_audit_required_online_execution_blocked"
)
EVENT_SEQUENCE: Final = (
    "read_current_runtime_state",
    "compile_authoritative_messages",
    "build_canonical_request",
    "validate_request_and_certificate",
    "emit_pre_transport_receipt",
    "injected_transport_dispatch",
    "project_public_payload",
    "parse_exact_response",
    "validate_current_state_and_candidate_or_final_envelope",
    "runtime_step_or_finalize",
    "terminal_dispatch",
)


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
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


def make_identity(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: identity(provisional, field, prefix)}, **values)


class ExternalFinalRequestContinuityAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: Literal["aca402146bae4afd780bf0ba06e5736744aefb787f9c2064071311b53ba13902"]
    review_byte_count: Literal[14180] = 14_180
    review_audit_result: Literal[
        "REPRODUCIBLE_PARTIAL_MECHANISM_PREFLIGHT_BUT_FAILED_AT_FROZEN_FINAL_REQUEST_CONTINUITY"
    ] = "REPRODUCIBLE_PARTIAL_MECHANISM_PREFLIGHT_BUT_FAILED_AT_FROZEN_FINAL_REQUEST_CONTINUITY"
    review_mandatory_revision: Literal["YES_NARROW"] = "YES_NARROW"
    review_candidate_stage: Literal[
        "fresh_repaired_full_condition_executable_runner_final_request_contract_continuity_repair_preflight_only"
    ] = CONSUMED_STAGE
    operator_directive: Literal["参照审计修订"] = "参照审计修订"
    operator_directive_sha256: Literal[
        "8a13fc4ca97304bb08362b5fbc22809e35375df599fa8866c93fb5eae69798e4"
    ]
    operator_directive_byte_count: Literal[18] = 18
    explicit_operator_authorization_after_review: Literal[True] = True
    only_authorized_stage: Literal[
        "fresh_repaired_full_condition_executable_runner_final_request_contract_continuity_repair_preflight_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    online_execution_authorization_creation_authorized: Literal[False] = False
    full_repaired_192_job_provider_execution_authorized: Literal[False] = False
    semantic_condition_change_authorized: Literal[False] = False
    qa_mapper_state_frequency_contribution_vtdo_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalFinalRequestContinuityAuthorization:
        encoded = self.operator_directive.encode("utf-8")
        if (
            len(encoded) != self.operator_directive_byte_count
            or hashlib.sha256(encoded).hexdigest() != self.operator_directive_sha256
        ):
            raise ValueError("v26.209 operator directive bytes differ")
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_209_external_final_request_continuity_authorization:",
        ):
            raise ValueError("v26.209 external route-closure Authorization identity differs")
        return self


class V208PredecessorFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    v208_report_id: str = Field(min_length=1)
    v208_gate_audit_id: str = Field(min_length=1)
    v208_transition_id: str = Field(min_length=1)
    v208_artifact_manifest_id: str = Field(min_length=1)
    v208_artifact_root: str = Field(min_length=1)
    v208_source_commit: Literal["f9f532ea449f786dd0058b60345f04091a6f77f5"]
    v208_source_tree: Literal["3a9b1ef4e6d8c6903d903086e280e0a36ad16e52"]
    v208_formal_file_count: Literal[20] = 20
    v208_formal_total_byte_count: Literal[2596518] = 2_596_518
    v208_manifest_member_count: Literal[19] = 19
    v208_manifest_member_total_byte_count: Literal[2593272] = 2_593_272
    v208_stored_all_gates_passed: Literal[True] = True
    postreview_scope: Literal[
        "REPRODUCIBLE_PARTIAL_MECHANISM_PREFLIGHT_BUT_FAILED_AT_FROZEN_FINAL_REQUEST_CONTINUITY"
    ] = "REPRODUCIBLE_PARTIAL_MECHANISM_PREFLIGHT_BUT_FAILED_AT_FROZEN_FINAL_REQUEST_CONTINUITY"
    first_blocker: Literal["frozen_final_provider_request_envelope_not_preserved"] = (
        "frozen_final_provider_request_envelope_not_preserved"
    )
    v208_shared_executable_route_retained: Literal[True] = True
    v207_report_id: str = Field(min_length=1)
    v207_decision_id: str = Field(min_length=1)
    v207_transition_id: str = Field(min_length=1)
    v207_gate_evaluation_id: str = Field(min_length=1)
    v207_source_route_audit_id: str = Field(min_length=1)
    v207_artifact_manifest_id: str = Field(min_length=1)
    v207_artifact_root: str = Field(min_length=1)
    v207_source_commit: Literal["304d4a6f42b22524a34e76eda55c23235937acdb"]
    v207_source_tree: Literal["40e503fc402d337b48038d65bf22ffd90b00ed21"]
    v207_formal_file_count: Literal[16] = 16
    v207_formal_total_byte_count: Literal[1408911] = 1_408_911
    v207_manifest_member_count: Literal[15] = 15
    v207_manifest_member_total_byte_count: Literal[1406276] = 1_406_276
    v207_stage_integrity: Literal["VALID_NEGATIVE_INDEPENDENT_AUDIT"] = (
        "VALID_NEGATIVE_INDEPENDENT_AUDIT"
    )
    v207_online_readiness: Literal["FAILED"] = "FAILED"
    v207_first_blocker: Literal[
        "executable_future_runner_repair_request_validation_transport_route_absent"
    ] = "executable_future_runner_repair_request_validation_transport_route_absent"
    v206_report_id: str = Field(min_length=1)
    v206_repair_profile_id: str = Field(min_length=1)
    v206_package_catalog_id: str = Field(min_length=1)
    v206_manifest_id: str = Field(min_length=1)
    v206_runner_id: str = Field(min_length=1)
    v206_execution_contract_id: str = Field(min_length=1)
    v206_estimand_contract_id: str = Field(min_length=1)
    v193_prompt_evidence_set_id: str = Field(min_length=1)
    v203_action_contract_id: str = Field(min_length=1)
    v194_resource_contract_id: str = Field(min_length=1)
    historical_artifact_mutation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V208PredecessorFreeze:
        if self.freeze_id != identity(
            self,
            "freeze_id",
            "finance_v26_209_v208_predecessor_freeze:",
        ):
            raise ValueError("v26.209 v26.208 predecessor Freeze identity differs")
        return self


class SourceFileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class ImplementationBinding(FrozenModel):
    implementation_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    predecessor_freeze_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    files: tuple[SourceFileBinding, ...] = Field(min_length=3)
    executable_runner_definition_count: Literal[1] = 1
    injected_transport_seam_definition_count: Literal[1] = 1
    shared_invocation_entry_count: Literal[1] = 1
    direct_provider_or_network_call_count: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ImplementationBinding:
        paths = tuple(item.relative_path for item in self.files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.209 implementation file vector differs")
        if self.implementation_id != identity(
            self,
            "implementation_id",
            "fresh_repaired_final_continuity_executable_route_implementation_binding:",
        ):
            raise ValueError("v26.209 Implementation Binding identity differs")
        return self


class ExecutableRunnerPackage(FrozenModel):
    package_id: str = Field(min_length=1)
    source_v206_package_id: str = Field(min_length=1)
    source_v206_package_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    implementation_id: str = Field(min_length=1)
    repair_profile_id: str = Field(min_length=1)
    runtime_semantic_contract_id: str = Field(min_length=1)
    runtime_implementation_binding_id: str = Field(min_length=1)
    final_grammar_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    capability_family: str = Field(min_length=1)
    depth: str = Field(min_length=1)
    schedule_ids: tuple[str, ...] = Field(min_length=1, max_length=4)
    component_keys: tuple[str, ...] = Field(min_length=1, max_length=4)
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> ExecutableRunnerPackage:
        if len(self.schedule_ids) != len(self.component_keys):
            raise ValueError("v26.209 Package Schedule/Component denominator differs")
        if self.package_id != identity(
            self,
            "package_id",
            "fresh_repaired_final_continuity_executable_full_condition_runner_package:",
        ):
            raise ValueError("v26.209 executable Runner Package identity differs")
        return self


class ExecutableRunnerPackageCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    implementation_id: str = Field(min_length=1)
    repair_profile_id: str = Field(min_length=1)
    packages: tuple[ExecutableRunnerPackage, ...] = Field(min_length=32, max_length=32)
    source_v206_package_ids: tuple[str, ...] = Field(min_length=32, max_length=32)
    package_count: Literal[32] = 32
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> ExecutableRunnerPackageCatalog:
        if len({item.package_id for item in self.packages}) != 32:
            raise ValueError("v26.209 executable Package denominator differs")
        if self.source_v206_package_ids != tuple(
            sorted(item.source_v206_package_id for item in self.packages)
        ):
            raise ValueError("v26.209 source Package set differs")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "fresh_repaired_final_continuity_executable_full_condition_package_catalog:",
        ):
            raise ValueError("v26.209 Package Catalog identity differs")
        return self


class ExecutableDevelopmentJob(FrozenModel):
    job_id: str = Field(min_length=1)
    source_v206_job_id: str = Field(min_length=1)
    source_v206_job_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_v194_job_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    source_v206_package_id: str = Field(min_length=1)
    implementation_id: str = Field(min_length=1)
    repair_profile_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    raw_namespace: str = Field(min_length=1)
    result_namespace: str = Field(min_length=1)
    trace_namespace: str = Field(min_length=1)
    outcome_namespace: str = Field(min_length=1)
    deterministic_seed_id: str = Field(min_length=1)
    provider_calls: Literal[0] = 0
    empirical_outcome: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_job(self) -> ExecutableDevelopmentJob:
        parent = {
            "source_v206_job_id": self.source_v206_job_id,
            "package_id": self.package_id,
            "implementation_id": self.implementation_id,
            "repair_profile_id": self.repair_profile_id,
            "replica_index": self.replica_index,
        }
        expected = (
            canonical_hash(
                parent, prefix="fresh_repaired_final_continuity_executable_raw_namespace:"
            ),
            canonical_hash(
                parent, prefix="fresh_repaired_final_continuity_executable_result_namespace:"
            ),
            canonical_hash(
                parent, prefix="fresh_repaired_final_continuity_executable_trace_namespace:"
            ),
            canonical_hash(
                parent, prefix="fresh_repaired_final_continuity_executable_outcome_namespace:"
            ),
            canonical_hash(
                parent, prefix="fresh_repaired_final_continuity_executable_deterministic_seed:"
            ),
        )
        actual = (
            self.raw_namespace,
            self.result_namespace,
            self.trace_namespace,
            self.outcome_namespace,
            self.deterministic_seed_id,
        )
        if actual != expected:
            raise ValueError("v26.209 Job namespace parent differs")
        if self.job_id != identity(
            self,
            "job_id",
            "fresh_repaired_final_continuity_executable_full_condition_development_job:",
        ):
            raise ValueError("v26.209 Development Job identity differs")
        return self


class ExecutableDevelopmentManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    implementation_id: str = Field(min_length=1)
    repair_profile_id: str = Field(min_length=1)
    jobs: tuple[ExecutableDevelopmentJob, ...] = Field(min_length=192, max_length=192)
    expected_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    source_v206_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    package_count: Literal[32] = 32
    replica_count: Literal[6] = 6
    job_count: Literal[192] = 192
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> ExecutableDevelopmentManifest:
        ids = tuple(item.job_id for item in self.jobs)
        if len(set(ids)) != 192 or self.expected_job_ids != tuple(sorted(ids)):
            raise ValueError("v26.209 Manifest Job set differs")
        if self.source_v206_job_ids != tuple(sorted(item.source_v206_job_id for item in self.jobs)):
            raise ValueError("v26.209 source Job set differs")
        if len({(item.package_id, item.replica_index) for item in self.jobs}) != 192:
            raise ValueError("v26.209 Package x Replica denominator differs")
        namespaces = tuple(
            {getattr(item, field) for item in self.jobs}
            for field in (
                "raw_namespace",
                "result_namespace",
                "trace_namespace",
                "outcome_namespace",
            )
        )
        if any(len(values) != 192 for values in namespaces):
            raise ValueError("v26.209 evidence namespaces are not unique")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            "fresh_repaired_final_continuity_executable_full_condition_manifest:",
        ):
            raise ValueError("v26.209 Manifest identity differs")
        return self


class ExecutableRunnerContract(FrozenModel):
    runner_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    implementation_id: str = Field(min_length=1)
    repair_profile_id: str = Field(min_length=1)
    source_v206_runner_id: str = Field(min_length=1)
    shared_invocation_entry: Literal[
        "FinalContinuityRepairedFullConditionRunner._invoke_current_state"
    ] = "FinalContinuityRepairedFullConditionRunner._invoke_current_state"
    injected_transport_seam: Literal["InjectedTransportSeam.send"] = "InjectedTransportSeam.send"
    action_route_through_shared_entry: Literal[True] = True
    correction_route_through_shared_entry: Literal[True] = True
    final_route_through_shared_entry: Literal[True] = True
    one_current_prompt_at_a_time: Literal[True] = True
    dynamic_contract_recompiled_per_state: Literal[True] = True
    pre_transport_receipt_required: Literal[True] = True
    exact_job_count: Literal[192] = 192
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_runner(self) -> ExecutableRunnerContract:
        if self.runner_id != identity(
            self,
            "runner_id",
            "fresh_repaired_final_continuity_executable_full_condition_runner:",
        ):
            raise ValueError("v26.209 executable Runner identity differs")
        return self


class ExecutableExecutionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    implementation_id: str = Field(min_length=1)
    repair_profile_id: str = Field(min_length=1)
    source_v206_execution_contract_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    exact_job_count: Literal[192] = 192
    exact_dynamic_invocation_count: Literal[792] = 792
    action_and_correction_invocation_count: Literal[600] = 600
    final_invocation_count: Literal[192] = 192
    maximum_primary_requests: Literal[21] = 21
    maximum_provider_calls: Literal[23] = 23
    maximum_transport_invocations: Literal[24] = 24
    maximum_rollout_tokens: Literal[1120000] = 1_120_000
    maximum_prompt_utf8_bytes: Literal[60000] = 60_000
    raw_result_trace_outcome_required: Literal[True] = True
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_execution(self) -> ExecutableExecutionContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_repaired_final_continuity_executable_full_condition_execution_contract:",
        ):
            raise ValueError("v26.209 Execution Contract identity differs")
        return self


PromptPhase = Literal["first_action", "subsequent_action", "correction", "final"]


class ValidatedRequestCertificate(FrozenModel):
    certificate_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    invocation_index: int = Field(ge=0, le=9)
    phase: PromptPhase
    prompt_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    current_state_id: str = Field(min_length=1)
    candidate_action_ids: tuple[str, ...]
    canonical_messages_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    repair_profile_id: str = Field(min_length=1)
    grammar_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    thinking_enabled: Literal[True] = True
    exact_builder_reconstruction_match: Literal[True] = True
    dynamic_state_and_candidate_match: Literal[True] = True
    old_response_abi_key_count: Literal[0] = 0
    model_visible_grammar_id_key_count: int = Field(ge=0)
    validation_passed: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_certificate(self) -> ValidatedRequestCertificate:
        if self.phase == "final":
            if self.candidate_action_ids:
                raise ValueError("v26.209 Final certificate carries Action candidates")
        elif not self.candidate_action_ids or self.model_visible_grammar_id_key_count != 0:
            raise ValueError("v26.209 Action certificate lacks Candidates or exposes grammar_id")
        if self.certificate_id != identity(
            self,
            "certificate_id",
            "fresh_repaired_final_continuity_executable_request_validation_certificate:",
        ):
            raise ValueError("v26.209 Request Certificate identity differs")
        return self


class PreTransportReceipt(FrozenModel):
    receipt_id: str = Field(min_length=1)
    certificate_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    invocation_index: int = Field(ge=0, le=9)
    phase: PromptPhase
    request_id: str = Field(min_length=1)
    injected_transport_seam_id: str = Field(min_length=1)
    emitted_before_transport: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_receipt(self) -> PreTransportReceipt:
        if self.receipt_id != identity(
            self,
            "receipt_id",
            "fresh_repaired_final_continuity_executable_pre_transport_receipt:",
        ):
            raise ValueError("v26.209 pre-transport Receipt identity differs")
        return self


class ExecutableInvocationRecord(FrozenModel):
    invocation_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    invocation_index: int = Field(ge=0, le=9)
    phase: PromptPhase
    component_key: str | None = None
    current_state_id: str = Field(min_length=1)
    candidate_action_ids: tuple[str, ...]
    selected_action_id: str | None = None
    prompt_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    certificate_id: str = Field(min_length=1)
    pre_transport_receipt_id: str = Field(min_length=1)
    injected_transport_seam_id: str = Field(min_length=1)
    canonical_messages_json: str = Field(min_length=1)
    canonical_messages_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_messages_byte_count: int = Field(gt=0)
    canonical_request_body_json: str = Field(min_length=1)
    canonical_request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_request_body_byte_count: int = Field(gt=0)
    public_response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    exact_response_parsed: bool
    current_state_and_candidate_or_final_envelope_valid: bool
    runtime_step_or_finalize_completed: bool
    action_accepted: bool | None = None
    typed_terminal: str | None = None
    event_sequence: tuple[str, ...]
    transport_dispatch_count: Literal[1] = 1
    direct_provider_calls: Literal[0] = 0
    empirical: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_record(self) -> ExecutableInvocationRecord:
        message_bytes = self.canonical_messages_json.encode("utf-8")
        request_bytes = self.canonical_request_body_json.encode("utf-8")
        if (
            canonical_bytes(json.loads(self.canonical_messages_json)) != message_bytes
            or canonical_bytes(json.loads(self.canonical_request_body_json)) != request_bytes
            or hashlib.sha256(message_bytes).hexdigest() != self.canonical_messages_sha256
            or hashlib.sha256(request_bytes).hexdigest() != self.canonical_request_body_sha256
            or len(message_bytes) != self.canonical_messages_byte_count
            or len(request_bytes) != self.canonical_request_body_byte_count
        ):
            raise ValueError("v26.209 canonical invocation bytes differ")
        if self.typed_terminal is None and self.event_sequence != EVENT_SEQUENCE:
            raise ValueError("v26.209 successful invocation order differs")
        if self.phase == "final":
            if self.candidate_action_ids or self.selected_action_id is not None:
                raise ValueError("v26.209 Final invocation carries Action fields")
            if self.action_accepted is not None:
                raise ValueError("v26.209 Final invocation carries Action acceptance")
        elif not self.candidate_action_ids:
            raise ValueError("v26.209 Action invocation lacks Candidate set")
        if self.invocation_id != identity(
            self,
            "invocation_id",
            "fresh_repaired_final_continuity_executable_invocation_record:",
        ):
            raise ValueError("v26.209 Invocation identity differs")
        return self


class ExecutableInvocationCensus(FrozenModel):
    census_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    implementation_id: str = Field(min_length=1)
    rows: tuple[ExecutableInvocationRecord, ...] = Field(min_length=792, max_length=792)
    exact_job_count: Literal[192] = 192
    dynamic_invocation_count: Literal[792] = 792
    unique_invocation_count: Literal[792] = 792
    unique_prompt_count: Literal[792] = 792
    unique_request_count: Literal[792] = 792
    unique_certificate_count: Literal[792] = 792
    unique_pre_transport_receipt_count: Literal[792] = 792
    first_action_count: Literal[192] = 192
    subsequent_action_count: Literal[288] = 288
    correction_count: Literal[120] = 120
    final_count: Literal[192] = 192
    action_and_correction_count: Literal[600] = 600
    transport_dispatch_count: Literal[792] = 792
    successful_order_count: Literal[792] = 792
    maximum_message_byte_count: int = Field(gt=0, le=60000)
    maximum_request_body_byte_count: int = Field(gt=0)
    old_abi_route_count: Literal[0] = 0
    unrepaired_route_count: Literal[0] = 0
    direct_provider_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_census(self) -> ExecutableInvocationCensus:
        fields = (
            "invocation_id",
            "prompt_id",
            "request_id",
            "certificate_id",
            "pre_transport_receipt_id",
        )
        if any(len({getattr(item, field) for item in self.rows}) != 792 for field in fields):
            raise ValueError("v26.209 executable invocation identity set differs")
        counts = {
            phase: sum(item.phase == phase for item in self.rows)
            for phase in ("first_action", "subsequent_action", "correction", "final")
        }
        if counts != {
            "first_action": 192,
            "subsequent_action": 288,
            "correction": 120,
            "final": 192,
        }:
            raise ValueError("v26.209 invocation phase denominator differs")
        if any(
            item.event_sequence != EVENT_SEQUENCE or item.typed_terminal is not None
            for item in self.rows
        ):
            raise ValueError("v26.209 denominator contains a failed or bypassed invocation")
        if self.census_id != identity(
            self,
            "census_id",
            "finance_v26_209_executable_invocation_census:",
        ):
            raise ValueError("v26.209 Invocation Census identity differs")
        return self


class RegisteredRequestContinuityRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    source_v206_job_id: str = Field(min_length=1)
    invocation_index: int = Field(ge=0, le=9)
    phase: PromptPhase
    source_v206_callsite_row_id: str = Field(min_length=1)
    source_v193_evidence_row_id: str = Field(min_length=1)
    actual_messages_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_messages_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    actual_messages_byte_count: int = Field(gt=0)
    expected_messages_byte_count: int = Field(gt=0)
    actual_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    actual_request_byte_count: int = Field(gt=0)
    expected_request_byte_count: int = Field(gt=0)
    message_hash_match: Literal[True] = True
    message_byte_count_match: Literal[True] = True
    request_hash_match: Literal[True] = True
    request_byte_count_match: Literal[True] = True
    final_actual_message_bytes_equal_v193: bool | None = None
    final_actual_request_bytes_equal_v193: bool | None = None
    coordinate_match: Literal[True] = True
    provider_calls: Literal[0] = 0
    empirical: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> RegisteredRequestContinuityRow:
        if (
            self.actual_messages_sha256 != self.expected_messages_sha256
            or self.actual_messages_byte_count != self.expected_messages_byte_count
            or self.actual_request_sha256 != self.expected_request_sha256
            or self.actual_request_byte_count != self.expected_request_byte_count
        ):
            raise ValueError("v26.209 registered request continuity differs")
        final_values = (
            self.final_actual_message_bytes_equal_v193,
            self.final_actual_request_bytes_equal_v193,
        )
        if self.phase == "final":
            if final_values != (True, True):
                raise ValueError("v26.209 Final actual-byte continuity differs")
        elif final_values != (None, None):
            raise ValueError("v26.209 non-Final row carries Final byte evidence")
        if self.row_id != identity(
            self,
            "row_id",
            "finance_v26_209_registered_request_continuity_row:",
        ):
            raise ValueError("v26.209 request-continuity Row identity differs")
        return self


class FrozenRequestContinuityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_freeze_id: str = Field(min_length=1)
    invocation_census_id: str = Field(min_length=1)
    source_v206_callsite_census_id: str = Field(min_length=1)
    source_v193_evidence_set_id: str = Field(min_length=1)
    prompt_contract_id: str = Field(min_length=1)
    prompt_schema_id: str = Field(min_length=1)
    rows: tuple[RegisteredRequestContinuityRow, ...] = Field(min_length=792, max_length=792)
    action_correction_message_match_count: Literal[600] = 600
    action_correction_request_match_count: Literal[600] = 600
    final_message_match_count: Literal[192] = 192
    final_request_match_count: Literal[192] = 192
    final_actual_message_byte_equality_count: Literal[192] = 192
    final_actual_request_byte_equality_count: Literal[192] = 192
    total_registered_message_match_count: Literal[792] = 792
    total_registered_request_match_count: Literal[792] = 792
    missing_coordinate_count: Literal[0] = 0
    duplicate_coordinate_count: Literal[0] = 0
    extra_coordinate_count: Literal[0] = 0
    maximum_message_byte_count: Literal[34404] = 34_404
    maximum_request_body_byte_count: Literal[34565] = 34_565
    v208_drifted_maximum_message_byte_count: Literal[29053] = 29_053
    v208_drifted_maximum_request_body_byte_count: Literal[29214] = 29_214
    v208_final_message_mismatch_count: Literal[192] = 192
    v208_final_request_mismatch_count: Literal[192] = 192
    provider_calls: Literal[0] = 0
    gate_passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FrozenRequestContinuityAudit:
        keys = tuple((item.job_id, item.invocation_index) for item in self.rows)
        if len(set(keys)) != 792:
            raise ValueError("v26.209 continuity coordinate set differs")
        counts = {
            phase: sum(item.phase == phase for item in self.rows)
            for phase in ("first_action", "subsequent_action", "correction", "final")
        }
        if counts != {
            "first_action": 192,
            "subsequent_action": 288,
            "correction": 120,
            "final": 192,
        }:
            raise ValueError("v26.209 continuity phase denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_209_frozen_request_continuity_audit:",
        ):
            raise ValueError("v26.209 frozen request Continuity Audit identity differs")
        return self


class ExecutableJobControlRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    source_v206_job_id: str = Field(min_length=1)
    invocation_ids: tuple[str, ...] = Field(min_length=2, max_length=10)
    first_action_count: Literal[1] = 1
    subsequent_action_count: int = Field(ge=0, le=3)
    correction_count: int = Field(ge=0, le=4)
    correction_calls_are_registered_side_branch_controls: Literal[True] = True
    single_linear_provider_trajectory_claimed: Literal[False] = False
    final_count: Literal[1] = 1
    action_and_correction_count: int = Field(ge=1, le=8)
    terminal_reference_path: Literal[True] = True
    base_valid: Literal[True] = True
    mechanism_valid: Literal[True] = True
    qualified_valid: Literal[True] = True
    raw_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    outcome_id: str = Field(min_length=1)
    empirical: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> ExecutableJobControlRow:
        if self.action_and_correction_count != (
            self.first_action_count + self.subsequent_action_count + self.correction_count
        ):
            raise ValueError("v26.209 per-Job invocation geometry differs")
        expected_raw = canonical_hash(
            {"job_id": self.job_id, "invocation_ids": self.invocation_ids},
            prefix="fresh_repaired_final_continuity_executable_control_raw:",
        )
        expected_result = canonical_hash(
            {"job_id": self.job_id, "raw_id": expected_raw, "qualified_valid": True},
            prefix="fresh_repaired_final_continuity_executable_control_result:",
        )
        expected_trace = canonical_hash(
            {"job_id": self.job_id, "raw_id": expected_raw, "result_id": expected_result},
            prefix="fresh_repaired_final_continuity_executable_control_trace:",
        )
        expected_outcome = canonical_hash(
            {"job_id": self.job_id, "trace_id": expected_trace, "qualified_valid": True},
            prefix="fresh_repaired_final_continuity_executable_control_outcome:",
        )
        if (self.raw_id, self.result_id, self.trace_id, self.outcome_id) != (
            expected_raw,
            expected_result,
            expected_trace,
            expected_outcome,
        ):
            raise ValueError("v26.209 Raw -> Result -> Trace -> Outcome chain differs")
        if self.row_id != identity(
            self,
            "row_id",
            "finance_v26_209_executable_job_control_row:",
        ):
            raise ValueError("v26.209 Job Control Row identity differs")
        return self


class FullConditionExecutionControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    invocation_census_id: str = Field(min_length=1)
    rows: tuple[ExecutableJobControlRow, ...] = Field(min_length=192, max_length=192)
    completed_scripted_job_count: Literal[192] = 192
    terminal_reference_path_count: Literal[192] = 192
    first_action_count: Literal[192] = 192
    subsequent_action_count: Literal[288] = 288
    correction_count: Literal[120] = 120
    registered_callsite_control: Literal[True] = True
    correction_side_branch_control_count: Literal[120] = 120
    single_linear_provider_trajectory_claimed: Literal[False] = False
    final_count: Literal[192] = 192
    action_and_correction_count: Literal[600] = 600
    transport_dispatch_count: Literal[792] = 792
    scripted_raw_count: Literal[192] = 192
    scripted_result_count: Literal[192] = 192
    scripted_trace_count: Literal[192] = 192
    scripted_outcome_count: Literal[192] = 192
    unique_layer_identity_count: Literal[768] = 768
    exception_escape_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FullConditionExecutionControlAudit:
        if len({item.job_id for item in self.rows}) != 192:
            raise ValueError("v26.209 execution Job denominator differs")
        layer_ids = {
            value
            for item in self.rows
            for value in (item.raw_id, item.result_id, item.trace_id, item.outcome_id)
        }
        if len(layer_ids) != 768:
            raise ValueError("v26.209 evidence-layer identity denominator differs")
        if sum(item.correction_count for item in self.rows) != 120:
            raise ValueError("v26.209 Correction denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_209_full_condition_execution_control_audit:",
        ):
            raise ValueError("v26.209 Execution Control Audit identity differs")
        return self


class SourceAndDynamicNoBypassAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    implementation_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    invocation_census_id: str = Field(min_length=1)
    executable_runner_definition_count: Literal[1] = 1
    injected_transport_seam_definition_count: Literal[1] = 1
    shared_invocation_entry_definition_count: Literal[1] = 1
    transport_dispatch_call_in_shared_entry_count: Literal[1] = 1
    action_wrapper_shared_entry_call_count: Literal[1] = 1
    correction_wrapper_shared_entry_call_count: Literal[1] = 1
    final_wrapper_shared_entry_call_count: Literal[1] = 1
    compiler_call_in_shared_entry_count: Literal[1] = 1
    request_builder_call_in_shared_entry_count: Literal[1] = 1
    validator_call_in_shared_entry_count: Literal[1] = 1
    pre_transport_receipt_call_in_shared_entry_count: Literal[1] = 1
    source_order_exact: Literal[True] = True
    dynamic_order_exact_count: Literal[792] = 792
    action_transport_route_count: Literal[480] = 480
    correction_transport_route_count: Literal[120] = 120
    final_transport_route_count: Literal[192] = 192
    old_abi_route_count: Literal[0] = 0
    unrepaired_route_count: Literal[0] = 0
    renderer_request_validator_bypass_count: Literal[0] = 0
    direct_provider_or_network_call_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    gate_passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> SourceAndDynamicNoBypassAudit:
        if (
            self.action_transport_route_count
            + self.correction_transport_route_count
            + self.final_transport_route_count
            != self.dynamic_order_exact_count
        ):
            raise ValueError("v26.209 dynamic route partition differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_209_source_dynamic_no_bypass_audit:",
        ):
            raise ValueError("v26.209 source/dynamic no-bypass Audit identity differs")
        return self


class TypedFailureControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: Literal[
        "invalid_first_action_abi",
        "unknown_current_action",
        "invalid_correction_abi",
        "invalid_final_abi",
        "typed_outer_failure",
    ]
    expected_terminal: str = Field(min_length=1)
    observed_terminal: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    transport_dispatch_count: Literal[1] = 1
    typed_outcome_count: Literal[1] = 1
    exception_escape_count: Literal[0] = 0
    empirical: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> TypedFailureControl:
        if self.expected_terminal != self.observed_terminal:
            raise ValueError("v26.209 Failure Control terminal differs")
        if self.control_id != identity(
            self,
            "control_id",
            "finance_v26_209_typed_failure_control:",
        ):
            raise ValueError("v26.209 Failure Control identity differs")
        return self


class TypedFailureControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    controls: tuple[TypedFailureControl, ...] = Field(min_length=5, max_length=5)
    control_count: Literal[5] = 5
    typed_outcome_count: Literal[5] = 5
    exception_escape_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> TypedFailureControlAudit:
        if len({item.control_name for item in self.controls}) != 5:
            raise ValueError("v26.209 Failure Control denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_209_typed_failure_control_audit:",
        ):
            raise ValueError("v26.209 Failure Control Audit identity differs")
        return self


class DynamicNonReferenceBranchAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    component_key: str = Field(min_length=1)
    initial_state_id: str = Field(min_length=1)
    reference_action_id: str = Field(min_length=1)
    nonreference_action_id: str = Field(min_length=1)
    candidate_count: int = Field(ge=2)
    nonreference_action_current_and_accepted: Literal[True] = True
    reference_next_state_id: str = Field(min_length=1)
    nonreference_next_state_id: str = Field(min_length=1)
    next_states_differ: Literal[True] = True
    second_invocation_current_state_id: str = Field(min_length=1)
    second_invocation_matches_nonreference_prefix: Literal[True] = True
    dynamic_final_message_json: str = Field(min_length=1)
    prompt_contract_id: str = Field(min_length=1)
    dynamic_final_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reference_final_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dynamic_final_request_differs_from_reference: Literal[True] = True
    dynamic_final_contract_envelope_valid: Literal[True] = True
    diagnostic_action_dispatch_count: int = Field(ge=2, le=4)
    diagnostic_final_dispatch_count: Literal[1] = 1
    diagnostic_transport_dispatch_count: int = Field(ge=3, le=5)
    enters_manifest_denominator: Literal[False] = False
    empirical: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DynamicNonReferenceBranchAudit:
        envelope = json.loads(self.dynamic_final_message_json)
        protocol = envelope.get("provider_output_protocol", {})
        if (
            self.reference_action_id == self.nonreference_action_id
            or self.initial_state_id
            in (self.reference_next_state_id, self.nonreference_next_state_id)
            or self.reference_next_state_id == self.nonreference_next_state_id
            or self.second_invocation_current_state_id != self.nonreference_next_state_id
            or tuple(sorted(envelope)) != ("prompt_core", "prompt_kind", "provider_output_protocol")
            or envelope.get("prompt_kind") != "final"
            or protocol.get("contract_id") != self.prompt_contract_id
            or protocol.get("response_format") != {"type": "json_object"}
            or self.dynamic_final_request_sha256 == self.reference_final_request_sha256
            or self.diagnostic_transport_dispatch_count
            != self.diagnostic_action_dispatch_count + self.diagnostic_final_dispatch_count
        ):
            raise ValueError("v26.209 dynamic nonreference branch witness differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_209_dynamic_nonreference_branch_audit:",
        ):
            raise ValueError("v26.209 Dynamic Branch Audit identity differs")
        return self


class EstimandResourceBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    source_v206_estimand_contract_id: str = Field(min_length=1)
    exact_denominator: Literal[192] = 192
    q_first_numerator: None = None
    q_bounded_correction_numerator: None = None
    q_first_estimate: None = None
    q_bounded_correction_estimate: None = None
    confidence_intervals: None = None
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    online_authorization_count: Literal[0] = 0
    qa_rows: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> EstimandResourceBoundaryAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_209_estimand_resource_boundary_audit:",
        ):
            raise ValueError("v26.209 Estimand/Resource Boundary Audit identity differs")
        return self


class FinalRequestContinuityGateAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_freeze_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    invocation_census_id: str = Field(min_length=1)
    execution_control_audit_id: str = Field(min_length=1)
    request_continuity_audit_id: str = Field(min_length=1)
    no_bypass_audit_id: str = Field(min_length=1)
    failure_control_audit_id: str = Field(min_length=1)
    dynamic_branch_audit_id: str = Field(min_length=1)
    boundary_audit_id: str = Field(min_length=1)
    r0_exact_v208_freeze_and_provider_facing_condition_passed: Literal[True] = True
    r1_fresh_executable_identity_closure_passed: Literal[True] = True
    r2_shared_entry_no_bypass_and_frozen_request_continuity_passed: Literal[True] = True
    r3_zero_provider_full_condition_execution_control_passed: Literal[True] = True
    r4_typed_failure_controls_and_boundary_passed: Literal[True] = True
    all_gates_passed: Literal[True] = True
    passed_gate_count: Literal[5] = 5
    failed_gate_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FinalRequestContinuityGateAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_209_final_request_continuity_gate_audit:",
        ):
            raise ValueError("v26.209 Final Request Continuity Gate Audit identity differs")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    gate_audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    boundary_audit_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_full_condition_executable_runner_final_request_contract_continuity_"
        "repair_preflight_passed_independent_audit_required_online_execution_blocked"
    ] = DECISION
    next_stage: Literal[
        "fresh_repaired_full_condition_executable_runner_final_request_contract_continuity_repair_preflight_"
        "independent_audit_only"
    ] = NEXT_STAGE
    independent_audit_required: Literal[True] = True
    online_execution_authorization_issued: Literal[False] = False
    full_repaired_192_job_provider_execution_authorized: Literal[False] = False
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    qa_mapper_state_frequency_contribution_vtdo_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_209_transition:",
        ):
            raise ValueError("v26.209 Transition identity differs")
        return self


class SourceIdentity(FrozenModel):
    source_identity_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    implementation_files: tuple[str, ...] = Field(min_length=3)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_source(self) -> SourceIdentity:
        if self.implementation_files != tuple(sorted(set(self.implementation_files))):
            raise ValueError("v26.209 source file vector differs")
        if self.source_identity_id != identity(
            self,
            "source_identity_id",
            "finance_v26_209_source_identity:",
        ):
            raise ValueError("v26.209 Source Identity differs")
        return self


class FinalRequestContinuityPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    predecessor_freeze_id: str = Field(min_length=1)
    implementation_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    invocation_census_id: str = Field(min_length=1)
    execution_control_audit_id: str = Field(min_length=1)
    request_continuity_audit_id: str = Field(min_length=1)
    no_bypass_audit_id: str = Field(min_length=1)
    failure_control_audit_id: str = Field(min_length=1)
    dynamic_branch_audit_id: str = Field(min_length=1)
    boundary_audit_id: str = Field(min_length=1)
    gate_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_full_condition_executable_runner_final_request_contract_continuity_"
        "repair_preflight_passed_independent_audit_required_online_execution_blocked"
    ] = DECISION
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    online_execution_authorization_issued: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinalRequestContinuityPreflightReport:
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_209_final_request_contract_continuity_repair_preflight_report:",
        ):
            raise ValueError("v26.209 Report identity differs")
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
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.209 Artifact Manifest path set differs")
        if self.file_count != len(self.members):
            raise ValueError("v26.209 Artifact Manifest file count differs")
        if self.total_byte_count != sum(item.byte_count for item in self.members):
            raise ValueError("v26.209 Artifact Manifest byte count differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_209_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("v26.209 Artifact Root differs")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            "finance_v26_209_artifact_manifest:",
        ):
            raise ValueError("v26.209 Artifact Manifest identity differs")
        return self


def artifact_manifest(run_id: str, payloads: dict[str, bytes]) -> ArtifactManifest:
    members = tuple(
        ArtifactMember(
            relative_path=name,
            sha256=hashlib.sha256(payload).hexdigest(),
            byte_count=len(payload),
        )
        for name, payload in sorted(payloads.items())
    )
    root = canonical_hash(
        tuple(item.model_dump(mode="json") for item in members),
        prefix="finance_v26_209_artifact_root:",
    )
    return cast(
        ArtifactManifest,
        make_identity(
            ArtifactManifest,
            {
                "run_id": run_id,
                "members": members,
                "file_count": len(members),
                "total_byte_count": sum(item.byte_count for item in members),
                "artifact_root": root,
            },
            field="manifest_id",
            prefix="finance_v26_209_artifact_manifest:",
        ),
    )
