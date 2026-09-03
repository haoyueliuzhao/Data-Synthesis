# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)
from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_repaired_upstream_typed_failure_event_authority.v1"
CONSUMED_STAGE: Final = (
    "fresh_repaired_upstream_typed_failure_event_authority_and_artifact_backing_preflight_only"
)
NEXT_STAGE: Final = (
    "fresh_repaired_upstream_typed_failure_event_authority_and_artifact_backing_"
    "preflight_independent_audit_only"
)
DECISION: Final = (
    "fresh_repaired_upstream_typed_failure_event_authority_and_artifact_backing_"
    "preflight_passed_independent_audit_required_online_execution_blocked"
)
EXACT_V209_RUNNER_ID: Final = (
    "fresh_repaired_final_continuity_executable_full_condition_runner:"
    "e58b8318667568b9becbb1fa946f1ac079937c9c744b6a2c4877661abebf0266"
)
EXACT_V209_EXCEPTION_TYPE_ID: Final = (
    "trusted_synthesis.experiments.vtdo_experiment."
    "phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight:"
    "TypedTransportFailure"
)
UPSTREAM_EVENT_KIND: Final = "transport_instrument_failure"
UPSTREAM_FAILURE_CODE: Final = "local_injected_transport_instrument_failure"
UPSTREAM_FAILURE_REASON: Final = "authenticated source-derived upstream instrument failure"
FORBIDDEN_UPSTREAM_TERMINALS: Final = (
    "completed_qualified",
    "completed_invalid",
    "first_response_abi_invalid",
    "correction_response_abi_invalid",
    "first_action_reference_invalid",
    "correction_action_reference_invalid",
    "correction_attempt_typed_invalid",
    "final_response_abi_invalid",
    "provider_no_payload_failure",
    "provider_transport_failure",
    "privacy_rejection",
    "resource_failure",
    "provider_identity_failure",
    "thinking_integrity_failure",
    "usage_integrity_failure",
)
EXIT_CONTROL_ITEMS: Final = (
    ("transport_invalid_dispatch_chain", "E0_invalid_dispatch_chain", "instrument_failure"),
    ("transport_empty_queue", "E1_empty_queue", "instrument_failure"),
    ("transport_authenticated_rethrow", "E2_authenticated_rethrow", "instrument_failure"),
    ("projection_reasoning_key", "E3_reasoning_key", "privacy_rejection"),
    ("projection_non_object", "E4_non_object", "instrument_failure"),
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
        value.model_dump(mode="json", exclude={field}, warnings=False), prefix=prefix
    )


def make_identity(
    model: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> BaseModel:
    provisional = model.model_construct(**{field: "pending"}, **values)
    return model.model_validate({field: identity(provisional, field, prefix), **values})


class ExternalRevisionAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: Literal["b63396f5321a6c99cf6fade8fd501a8387a7e172470250b2e931413afc4ba871"]
    review_byte_count: Literal[14940] = 14_940
    operator_directive: Literal["参照审计报告继续实验修订"] = "参照审计报告继续实验修订"
    operator_directive_sha256: Literal[
        "dc2b598ec3667bd0e26354d1dac1ca447fa87acea50bd30a5fc245a9c35374e9"
    ]
    operator_directive_byte_count: Literal[36] = 36
    audit_result: Literal["VALID_SCOPED_FIVE_EXIT_AST_ENUMERATION_AND_FIXED_CONTROL_EXECUTION"] = (
        "VALID_SCOPED_FIVE_EXIT_AST_ENUMERATION_AND_FIXED_CONTROL_EXECUTION"
    )
    failed_at: Literal["UPSTREAM_FAILURE_OBSERVATION_SOURCE_AUTHORITY_AND_ARTIFACT_BACKING"] = (
        "UPSTREAM_FAILURE_OBSERVATION_SOURCE_AUTHORITY_AND_ARTIFACT_BACKING"
    )
    consumed_stage: Literal[
        "fresh_repaired_upstream_typed_failure_event_authority_and_artifact_backing_preflight_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    online_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalRevisionAuthorization:
        if self.authorization_id != identity(
            self, "authorization_id", "finance_v26_217_external_revision_authorization:"
        ):
            raise ValueError("v26.217 external authorization identity differs")
        return self


class V216Freeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v216_report_id: str = Field(min_length=1)
    v216_decision_id: str = Field(min_length=1)
    v216_transition_id: str = Field(min_length=1)
    v216_artifact_manifest_id: str = Field(min_length=1)
    v216_artifact_root: str = Field(min_length=1)
    v216_source_commit: Literal["a3e6589a71cbf40b0c93488343e406641f0d017a"] = (
        "a3e6589a71cbf40b0c93488343e406641f0d017a"
    )
    v216_source_tree: Literal["ed56a5dfaa45510535647343b534db557fb3aefd"] = (
        "ed56a5dfaa45510535647343b534db557fb3aefd"
    )
    formal_file_count: Literal[50] = 50
    formal_total_byte_count: Literal[1038367] = 1_038_367
    manifest_member_count: Literal[49] = 49
    manifest_member_byte_count: Literal[1029127] = 1_029_127
    five_exit_ast_controls_retained: Literal[True] = True
    unauthenticated_rethrow_attack_retained: Literal[True] = True
    upstream_event_authority_failed: Literal[True] = True
    first_blocker: Literal[
        "upstream_producer_converts_caller_labels_without_artifact_backed_source_event"
    ] = "upstream_producer_converts_caller_labels_without_artifact_backed_source_event"
    v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V216Freeze:
        if self.freeze_id != identity(self, "freeze_id", "finance_v26_217_v216_freeze:"):
            raise ValueError("v26.217 v26.216 Freeze identity differs")
        return self


class SourceBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class SourceIdentity(FrozenModel):
    source_identity_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    implementation_files: tuple[str, ...] = Field(min_length=4, max_length=4)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_source(self) -> SourceIdentity:
        if self.source_identity_id != identity(
            self, "source_identity_id", "finance_v26_217_source_identity:"
        ):
            raise ValueError("v26.217 source identity differs")
        return self


class ImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v216_freeze_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    files: tuple[SourceBinding, ...] = Field(min_length=4, max_length=4)
    symbols: tuple[SourceBinding, ...] = Field(min_length=9)
    direct_network_routes: Literal[0] = 0
    credential_environment_routes: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ImplementationBinding:
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_repaired_upstream_typed_failure_event_authority_implementation_binding:",
        ):
            raise ValueError("v26.217 implementation Binding differs")
        return self


class SourceExitDeclaration(FrozenModel):
    source_exit_id: str = Field(min_length=1)
    exit_code: Literal[
        "E0_invalid_dispatch_chain",
        "E1_empty_queue",
        "E2_authenticated_rethrow",
        "E3_reasoning_key",
        "E4_non_object",
    ]
    source_relative_path: str = Field(min_length=1)
    source_symbol: Literal["ScriptedTransport.send", "_project_public_payload"]
    source_symbol_id: str = Field(min_length=1)
    source_line: int = Field(gt=0)
    source_col_offset: int = Field(ge=0)
    source_exit_kind: Literal["direct_constructor", "authenticated_rethrow"]
    failure_origin: Literal["transport_send", "public_projection"]
    direct_terminal_kind: str | None
    direct_reason_sha256: str | None
    upstream_authority_required: bool
    ast_node_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_declaration(self) -> SourceExitDeclaration:
        if self.source_exit_kind == "direct_constructor":
            valid = (
                self.direct_terminal_kind is not None
                and self.direct_reason_sha256 is not None
                and not self.upstream_authority_required
            )
        else:
            valid = (
                self.exit_code == "E2_authenticated_rethrow"
                and self.direct_terminal_kind is None
                and self.direct_reason_sha256 is None
                and self.upstream_authority_required
            )
        if not valid or self.source_exit_id != identity(
            self, "source_exit_id", "fresh_repaired_v209_typed_failure_source_exit:"
        ):
            raise ValueError("v26.217 Source Exit declaration differs")
        return self


class TypedFailureExitSurfaceContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    exact_v209_source_commit: Literal["5809e9782515e55ee797b43730584d5d860aaa5c"] = (
        "5809e9782515e55ee797b43730584d5d860aaa5c"
    )
    exact_v209_source_tree: Literal["b2272bc1766a2d9b8c6562cb0b9f2f47151ad7cf"] = (
        "b2272bc1766a2d9b8c6562cb0b9f2f47151ad7cf"
    )
    exact_v209_source_sha256: Literal[
        "4529523fc737f26801118cc5cf78b682f2e510c5f887ed0d14a60a5bd26d9b35"
    ] = "4529523fc737f26801118cc5cf78b682f2e510c5f887ed0d14a60a5bd26d9b35"
    ast_module_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exits: tuple[SourceExitDeclaration, ...] = Field(min_length=5, max_length=5)
    typed_failure_exit_count: Literal[5] = 5
    direct_constructor_exit_count: Literal[4] = 4
    authenticated_rethrow_exit_count: Literal[1] = 1
    constructor_string_count_is_authority: Literal[False] = False
    complete_ast_raise_enumeration_required: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> TypedFailureExitSurfaceContract:
        expected = (
            "E0_invalid_dispatch_chain",
            "E1_empty_queue",
            "E2_authenticated_rethrow",
            "E3_reasoning_key",
            "E4_non_object",
        )
        if (
            tuple(item.exit_code for item in self.exits) != expected
            or len({item.source_exit_id for item in self.exits}) != 5
            or sum(item.source_exit_kind == "direct_constructor" for item in self.exits) != 4
            or sum(item.source_exit_kind == "authenticated_rethrow" for item in self.exits) != 1
            or self.contract_id
            != identity(
                self,
                "contract_id",
                "fresh_repaired_actual_v209_typed_failure_exit_surface_contract:",
            )
        ):
            raise ValueError("v26.217 typed-failure Exit Surface Contract differs")
        return self


class UpstreamEventSourceBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    source_v195_terminal_registry_id: str = Field(min_length=1)
    admitted_event_terminal_policy_items: tuple[tuple[str, str, str], ...] = Field(
        min_length=1, max_length=1
    )
    forbidden_terminal_kinds: tuple[str, ...] = Field(min_length=15, max_length=15)
    event_source_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_argument_allowed: Literal[False] = False
    reason_argument_allowed: Literal[False] = False
    source_event_id_argument_allowed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> UpstreamEventSourceBinding:
        admitted = self.admitted_event_terminal_policy_items
        if (
            len(admitted) != 1
            or admitted[0][0] != UPSTREAM_EVENT_KIND
            or admitted[0][1] != "instrument_failure"
            or set(self.forbidden_terminal_kinds) != set(FORBIDDEN_UPSTREAM_TERMINALS)
            or self.binding_id
            != identity(
                self,
                "binding_id",
                "fresh_repaired_upstream_failure_event_source_binding:",
            )
        ):
            raise ValueError("v26.217 upstream Event Source Binding differs")
        return self


class UpstreamObservationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    event_source_binding_id: str = Field(min_length=1)
    observe_failure_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation_terminal_derived_from_event_kind: Literal[True] = True
    event_and_observation_artifacts_required: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> UpstreamObservationBinding:
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_repaired_upstream_failure_observation_binding:",
        ):
            raise ValueError("v26.217 upstream Observation Binding differs")
        return self


class AuthenticatedUpstreamFailureEvent(FrozenModel):
    event_id: str = Field(min_length=1)
    event_source_binding_id: str = Field(min_length=1)
    event_kind: Literal["transport_instrument_failure"] = UPSTREAM_EVENT_KIND
    source_job_id: str = Field(min_length=1)
    source_invocation_request_parent_id: str = Field(min_length=1)
    failure_code: Literal["local_injected_transport_instrument_failure"] = UPSTREAM_FAILURE_CODE
    reason: Literal["authenticated source-derived upstream instrument failure"] = (
        UPSTREAM_FAILURE_REASON
    )
    event_sequence: tuple[str, ...] = (
        "bound_upstream_event_source_entered",
        "instrument_failure_observed",
    )
    terminal_field_present: Literal[False] = False
    caller_selected_event_id: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_event(self) -> AuthenticatedUpstreamFailureEvent:
        if self.event_sequence != (
            "bound_upstream_event_source_entered",
            "instrument_failure_observed",
        ) or self.event_id != identity(
            self,
            "event_id",
            "fresh_repaired_authenticated_upstream_failure_event:",
        ):
            raise ValueError("v26.217 authenticated upstream Event differs")
        return self


class UpstreamArtifactDescriptor(FrozenModel):
    descriptor_id: str = Field(min_length=1)
    artifact_kind: Literal["upstream_failure_event", "upstream_failure_observation"]
    object_id: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)
    parent_descriptor_id: str | None = None
    durable_no_replace: Literal[True] = True
    actual_byte_match: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_descriptor(self) -> UpstreamArtifactDescriptor:
        expected_prefix = (
            "upstream_events/"
            if self.artifact_kind == "upstream_failure_event"
            else "upstream_observations/"
        )
        expected_parent = (
            None if self.artifact_kind == "upstream_failure_event" else self.parent_descriptor_id
        )
        if (
            not self.relative_path.startswith(expected_prefix)
            or (self.artifact_kind == "upstream_failure_observation" and expected_parent is None)
            or (
                self.artifact_kind == "upstream_failure_event"
                and self.parent_descriptor_id is not None
            )
            or self.descriptor_id
            != identity(
                self,
                "descriptor_id",
                "fresh_repaired_upstream_artifact_descriptor:",
            )
        ):
            raise ValueError("v26.217 upstream artifact Descriptor differs")
        return self


class ArtifactBackedUpstreamFailureObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    observation_binding_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    event_descriptor_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    exception_type_id: Literal[
        "trusted_synthesis.experiments.vtdo_experiment."
        "phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight:"
        "TypedTransportFailure"
    ] = EXACT_V209_EXCEPTION_TYPE_ID
    terminal_kind: Literal["instrument_failure"] = "instrument_failure"
    exception_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_policy_id: str = Field(min_length=1)
    derivation_rule: Literal["strict_event_kind_to_terminal_and_literal_event_reason"] = (
        "strict_event_kind_to_terminal_and_literal_event_reason"
    )
    caller_terminal_input: Literal[False] = False
    caller_reason_input: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> ArtifactBackedUpstreamFailureObservation:
        expected_reason = hashlib.sha256(UPSTREAM_FAILURE_REASON.encode("utf-8")).hexdigest()
        if self.exception_reason_sha256 != expected_reason or self.observation_id != identity(
            self,
            "observation_id",
            "fresh_repaired_artifact_backed_upstream_failure_observation:",
        ):
            raise ValueError("v26.217 artifact-backed upstream Observation differs")
        return self


class UpstreamArtifactChain(FrozenModel):
    chain_id: str = Field(min_length=1)
    event: AuthenticatedUpstreamFailureEvent
    event_descriptor: UpstreamArtifactDescriptor
    observation: ArtifactBackedUpstreamFailureObservation
    observation_descriptor: UpstreamArtifactDescriptor
    persistence_sequence: tuple[str, ...] = (
        "event",
        "event_descriptor",
        "observation",
        "observation_descriptor",
    )
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_chain(self) -> UpstreamArtifactChain:
        event_bytes = canonical_bytes(self.event) + b"\n"
        observation_bytes = canonical_bytes(self.observation) + b"\n"
        if (
            self.event_descriptor.artifact_kind != "upstream_failure_event"
            or self.event_descriptor.object_id != self.event.event_id
            or self.event_descriptor.sha256 != hashlib.sha256(event_bytes).hexdigest()
            or self.event_descriptor.byte_count != len(event_bytes)
            or self.observation.event_id != self.event.event_id
            or self.observation.event_descriptor_id != self.event_descriptor.descriptor_id
            or self.observation.source_job_id != self.event.source_job_id
            or self.observation_descriptor.artifact_kind != "upstream_failure_observation"
            or self.observation_descriptor.object_id != self.observation.observation_id
            or self.observation_descriptor.parent_descriptor_id
            != self.event_descriptor.descriptor_id
            or self.observation_descriptor.sha256 != hashlib.sha256(observation_bytes).hexdigest()
            or self.observation_descriptor.byte_count != len(observation_bytes)
            or self.persistence_sequence
            != ("event", "event_descriptor", "observation", "observation_descriptor")
            or self.chain_id
            != identity(
                self,
                "chain_id",
                "fresh_repaired_upstream_failure_artifact_chain:",
            )
        ):
            raise ValueError("v26.217 upstream artifact Chain differs")
        return self


class SourceExitProof(FrozenModel):
    proof_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    source_symbol_id: str = Field(min_length=1)
    source_exit_id: str = Field(min_length=1)
    exit_code: str = Field(min_length=1)
    source_exit_kind: Literal["direct_constructor", "authenticated_rethrow"]
    failure_origin: Literal["transport_send", "public_projection"]
    exception_type_id: str = Field(min_length=1)
    terminal_kind: str = Field(min_length=1)
    exception_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dispatch_or_response_parent_id: str = Field(min_length=1)
    upstream_failure_observation_id: str | None
    upstream_artifact_chain: UpstreamArtifactChain | None
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_proof(self) -> SourceExitProof:
        if self.source_exit_kind == "authenticated_rethrow":
            valid = (
                self.upstream_failure_observation_id is not None
                and self.upstream_artifact_chain is not None
                and self.upstream_artifact_chain.observation.observation_id
                == self.upstream_failure_observation_id
                and self.upstream_artifact_chain.observation.exception_type_id
                == self.exception_type_id
                and self.upstream_artifact_chain.observation.terminal_kind == self.terminal_kind
                and self.upstream_artifact_chain.observation.exception_reason_sha256
                == self.exception_reason_sha256
                and self.upstream_artifact_chain.event.source_invocation_request_parent_id
                == self.dispatch_or_response_parent_id
            )
        else:
            valid = (
                self.upstream_failure_observation_id is None
                and self.upstream_artifact_chain is None
            )
        if not valid or self.proof_id != identity(
            self, "proof_id", "fresh_repaired_v209_typed_failure_source_exit_proof:"
        ):
            raise ValueError("v26.217 Source Exit proof differs")
        return self


class RunnerObservationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    upstream_event_source_binding_id: str = Field(min_length=1)
    upstream_observation_binding_id: str = Field(min_length=1)
    exact_v209_runner_id: Literal[
        "fresh_repaired_final_continuity_executable_full_condition_runner:"
        "e58b8318667568b9becbb1fa946f1ac079937c9c744b6a2c4877661abebf0266"
    ] = EXACT_V209_RUNNER_ID
    inherited_v216_runner_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminalizer_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_exit_authority_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_exit_proof_required_before_runner_authority: Literal[True] = True
    unauthenticated_rethrow_rejected_before_runner_authority: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> RunnerObservationBinding:
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_repaired_upstream_event_authority_runner_observation_binding:",
        ):
            raise ValueError("v26.217 Runner observation Binding differs")
        return self


class TypedFailureObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    runner_binding_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    source_runner_id: Literal[
        "fresh_repaired_final_continuity_executable_full_condition_runner:"
        "e58b8318667568b9becbb1fa946f1ac079937c9c744b6a2c4877661abebf0266"
    ] = EXACT_V209_RUNNER_ID
    job_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    certificate_id: str = Field(min_length=1)
    pre_transport_receipt_id: str = Field(min_length=1)
    injected_transport_seam_id: str = Field(min_length=1)
    source_exit_proof: SourceExitProof
    exception_type_id: str = Field(min_length=1)
    caught_terminal_kind: str = Field(min_length=1)
    exception_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    invocation_record: dict[str, Any]
    runner_owned: Literal[True] = True
    source_exit_admitted: Literal[True] = True
    terminal_label_input: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> TypedFailureObservation:
        proof = self.source_exit_proof
        record = v209_models.ExecutableInvocationRecord.model_validate(self.invocation_record)
        if (
            proof.source_contract_id != self.source_contract_id
            or proof.exception_type_id != self.exception_type_id
            or proof.terminal_kind != self.caught_terminal_kind
            or proof.exception_reason_sha256 != self.exception_reason_sha256
            or (
                proof.source_exit_kind == "authenticated_rethrow"
                and (
                    proof.upstream_artifact_chain is None
                    or proof.upstream_artifact_chain.event.source_job_id != self.job_id
                    or proof.upstream_artifact_chain.event.source_invocation_request_parent_id
                    != proof.dispatch_or_response_parent_id
                )
            )
            or record.typed_terminal != self.caught_terminal_kind
            or record.job_id != self.job_id
            or record.invocation_id != self.invocation_id
            or record.request_id != self.request_id
            or record.certificate_id != self.certificate_id
            or record.pre_transport_receipt_id != self.pre_transport_receipt_id
            or record.injected_transport_seam_id != self.injected_transport_seam_id
            or record.public_response_sha256 is not None
            or record.exact_response_parsed
            or record.runtime_step_or_finalize_completed
            or not record.event_sequence
            or record.event_sequence[-1] != "terminal_dispatch"
            or self.observation_id
            != identity(
                self,
                "observation_id",
                "fresh_repaired_upstream_event_authority_typed_failure_observation:",
            )
        ):
            raise ValueError("v26.217 typed failure observation differs")
        return self


class AuthenticatedTypedFailureEvidence(FrozenModel):
    evidence_id: str = Field(min_length=1)
    evidence_kind: Literal["runner_owned_source_exit_typed_failure"] = (
        "runner_owned_source_exit_typed_failure"
    )
    job_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    failure_observation: TypedFailureObservation
    expected_terminal_input: Literal[False] = False
    caller_selected_source_exit: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evidence(self) -> AuthenticatedTypedFailureEvidence:
        if (
            self.job_id != self.failure_observation.job_id
            or self.invocation_id != self.failure_observation.invocation_id
            or self.evidence_id
            != identity(
                self,
                "evidence_id",
                "fresh_repaired_upstream_event_authority_authenticated_typed_failure_evidence:",
            )
        ):
            raise ValueError("v26.217 authenticated evidence differs")
        return self


class DispatcherBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    runner_observation_binding_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    source_v195_terminal_registry_id: str = Field(min_length=1)
    dispatcher_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_policy_items: tuple[tuple[str, str], ...] = Field(min_length=16)
    authority_ledger_match_required: Literal[True] = True
    source_exit_proof_revalidation_required: Literal[True] = True
    terminal_kind_input_allowed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> DispatcherBinding:
        kinds = tuple(item[0] for item in self.terminal_policy_items)
        policies = tuple(item[1] for item in self.terminal_policy_items)
        if (
            len(set(kinds)) != len(kinds)
            or len(set(policies)) != len(policies)
            or self.binding_id
            != identity(
                self,
                "binding_id",
                "fresh_repaired_upstream_event_authority_dispatcher_binding:",
            )
        ):
            raise ValueError("v26.217 Dispatcher Binding differs")
        return self


class PersistenceBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    source_v216_persistence_binding_id: str = Field(min_length=1)
    persistence_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_dispatch_rederivation_required: Literal[True] = True
    source_exit_proof_revalidation_required: Literal[True] = True
    raw_before_result_required: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> PersistenceBinding:
        if self.binding_id != identity(
            self, "binding_id", "fresh_repaired_upstream_event_authority_persistence_binding:"
        ):
            raise ValueError("v26.217 persistence Binding differs")
        return self


class ConsumerBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    exact_v211_authorization_id: str = Field(min_length=1)
    exact_v209_manifest_id: str = Field(min_length=1)
    source_v212_consumption_contract_id: str = Field(min_length=1)
    source_v212_run_start_contract_id: str = Field(min_length=1)
    upstream_event_source_binding_id: str = Field(min_length=1)
    upstream_observation_binding_id: str = Field(min_length=1)
    runner_observation_binding_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    persistence_binding_id: str = Field(min_length=1)
    execute_preflight_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    one_entry_function: Literal["ArtifactBackedFailureConsumer.execute_preflight"] = (
        "ArtifactBackedFailureConsumer.execute_preflight"
    )
    current_v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ConsumerBinding:
        if self.binding_id != identity(
            self, "binding_id", "fresh_repaired_upstream_event_authority_failure_consumer_binding:"
        ):
            raise ValueError("v26.217 consumer Binding differs")
        return self


class CompositionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    v216_freeze_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    upstream_event_source_binding_id: str = Field(min_length=1)
    upstream_observation_binding_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    runner_observation_binding_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    persistence_binding_id: str = Field(min_length=1)
    exact_sequence: tuple[str, ...] = (
        "authorization_guard",
        "durable_preflight_consumption_receipt",
        "durable_run_start_receipt",
        "credential_and_factory_gate",
        "ast_enumerated_v209_source_exit",
        "source_derived_upstream_event",
        "durable_event_and_descriptor",
        "derived_upstream_observation",
        "durable_observation_and_descriptor",
        "artifact_backed_source_exit_proof",
        "runner_owned_observation",
        "consumer_terminal_branch",
        "source_exit_registry_dispatch",
        "raw_result_trace_outcome_checkpoint",
    )
    current_v211_authorization_consumed: Literal[False] = False
    new_online_authorization_created: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> CompositionContract:
        if self.contract_id != identity(
            self, "contract_id", "fresh_repaired_upstream_event_authority_composition_contract:"
        ):
            raise ValueError("v26.217 Composition Contract differs")
        return self


class DerivedTerminalDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    source_exit_id: str = Field(min_length=1)
    source_exit_kind: Literal["direct_constructor", "authenticated_rethrow"]
    upstream_failure_observation_id: str | None
    invocation_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    terminal_kind: str = Field(min_length=1)
    terminal_policy_id: str = Field(min_length=1)
    exception_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivation_rule: Literal[
        "source_exit_proof_artifact_backed_event_observation_and_registry_agreement"
    ] = "source_exit_proof_artifact_backed_event_observation_and_registry_agreement"
    terminal_label_was_input: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> DerivedTerminalDecision:
        if (self.source_exit_kind == "authenticated_rethrow") != (
            self.upstream_failure_observation_id is not None
        ) or self.decision_id != identity(
            self,
            "decision_id",
            "fresh_repaired_upstream_event_authority_terminal_decision:",
        ):
            raise ValueError("v26.217 derived terminal Decision differs")
        return self


class PersistedEvidenceDescriptor(FrozenModel):
    descriptor_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    source_exit_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    terminal_kind: str = Field(min_length=1)
    raw_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    outcome_id: str = Field(min_length=1)
    checkpoint_id: str = Field(min_length=1)
    raw_relative_path: str = Field(min_length=1)
    result_relative_path: str = Field(min_length=1)
    trace_relative_path: str = Field(min_length=1)
    outcome_relative_path: str = Field(min_length=1)
    checkpoint_relative_path: str = Field(min_length=1)
    persistence_sequence: tuple[str, ...]
    actual_byte_match_count: Literal[5] = 5
    formal_empirical_row: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_descriptor(self) -> PersistedEvidenceDescriptor:
        if (
            self.persistence_sequence != ("raw", "result", "trace", "outcome", "checkpoint")
            or len(
                {self.raw_id, self.result_id, self.trace_id, self.outcome_id, self.checkpoint_id}
            )
            != 5
            or self.descriptor_id
            != identity(
                self,
                "descriptor_id",
                "finance_v26_217_upstream_event_authority_persisted_descriptor:",
            )
        ):
            raise ValueError("v26.217 persisted descriptor differs")
        return self


class ExitSurfaceControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    expected_exit_code: str = Field(min_length=1)
    expected_terminal: str = Field(min_length=1)
    source_exit_proof: SourceExitProof
    failure_observation: TypedFailureObservation
    evidence: AuthenticatedTypedFailureEvidence
    decision: DerivedTerminalDecision
    persistence: PersistedEvidenceDescriptor
    expected_values_used_only_after_dispatch: Literal[True] = True
    exception_escape: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> ExitSurfaceControl:
        if (
            (self.control_name, self.expected_exit_code, self.expected_terminal)
            not in EXIT_CONTROL_ITEMS
            or self.source_exit_proof.exit_code != self.expected_exit_code
            or self.failure_observation.source_exit_proof.proof_id
            != self.source_exit_proof.proof_id
            or self.decision.source_exit_id != self.source_exit_proof.source_exit_id
            or self.decision.terminal_kind != self.expected_terminal
            or self.persistence.terminal_kind != self.expected_terminal
            or self.control_id
            != identity(self, "control_id", "finance_v26_217_typed_failure_exit_control:")
        ):
            raise ValueError("v26.217 Exit Surface control differs")
        return self


class ExitSurfaceExecutionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    consumption_receipt_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    controls: tuple[ExitSurfaceControl, ...] = Field(min_length=5, max_length=5)
    typed_failure_exit_count: Literal[5] = 5
    direct_constructor_control_count: Literal[4] = 4
    authenticated_rethrow_control_count: Literal[1] = 1
    positive_source_derived_upstream_event_count: Literal[1] = 1
    positive_upstream_event_descriptor_count: Literal[1] = 1
    positive_derived_upstream_observation_count: Literal[1] = 1
    positive_upstream_observation_descriptor_count: Literal[1] = 1
    positive_e2_embedded_artifact_chain_count: Literal[1] = 1
    runner_owned_observation_count: Literal[5] = 5
    consumer_terminal_branch_count: Literal[5] = 5
    exact_exit_terminal_match_count: Literal[5] = 5
    persisted_layer_count: Literal[25] = 25
    exception_escape_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ExitSurfaceExecutionAudit:
        observed = tuple(
            (item.control_name, item.expected_exit_code, item.expected_terminal)
            for item in self.controls
        )
        if observed != EXIT_CONTROL_ITEMS or self.audit_id != identity(
            self, "audit_id", "finance_v26_217_exit_surface_execution_audit:"
        ):
            raise ValueError("v26.217 Exit Surface execution Audit differs")
        return self


class NegativeControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    rejection_stage: Literal[
        "event_schema_admission",
        "upstream_artifact_admission",
        "persistence_pre_raw",
    ]
    rejected: Literal[True] = True
    rejected_before_runner_authority_append: Literal[True] = True
    rejected_before_raw_write: Literal[True] = True
    fully_rehashed: bool
    fully_rehashed_downstream_layer_ids: tuple[str, ...] = Field(max_length=5)
    rejection_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> NegativeControl:
        if self.fully_rehashed != bool(
            self.fully_rehashed_downstream_layer_ids
        ) or self.control_id != identity(
            self,
            "control_id",
            "finance_v26_217_upstream_event_authority_negative_control:",
        ):
            raise ValueError("v26.217 negative control differs")
        return self


class NegativeControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    controls: tuple[NegativeControl, ...] = Field(min_length=5, max_length=5)
    rejected_count: Literal[5] = 5
    accepted_count: Literal[0] = 0
    completed_qualified_mint_rejection_count: Literal[1] = 1
    incompatible_outer_terminal_rejection_count: Literal[1] = 1
    forged_source_event_rejection_count: Literal[1] = 1
    missing_event_artifact_rejection_count: Literal[1] = 1
    cross_event_job_substitution_rejection_count: Literal[1] = 1
    fully_rehashed_attack_count: Literal[2] = 2
    fully_rehashed_downstream_layer_identity_count: Literal[10] = 10
    runner_authority_append_count: Literal[0] = 0
    raw_write_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> NegativeControlAudit:
        expected = {
            "completed_qualified_producer_mint_attempt",
            "registered_event_incompatible_outer_terminal",
            "caller_forged_source_event_id_full_rehash",
            "missing_upstream_event_artifact",
            "cross_event_cross_job_observation_substitution",
        }
        if {item.control_name for item in self.controls} != expected or self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_217_upstream_event_authority_negative_control_audit:",
        ):
            raise ValueError("v26.217 negative-control Audit differs")
        return self


class ScopeBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v216_freeze_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    isolated_preflight_lease_count: Literal[1] = 1
    preflight_run_start_receipt_count: Literal[1] = 1
    current_v211_authorization_consumed: Literal[False] = False
    new_online_authorizations: Literal[0] = 0
    provider_calls: Literal[0] = 0
    provider_client_constructions: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    qa_reads: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ScopeBoundaryAudit:
        if self.audit_id != identity(self, "audit_id", "finance_v26_217_scope_boundary_audit:"):
            raise ValueError("v26.217 scope boundary Audit differs")
        return self


class GateResult(FrozenModel):
    gate_id: str = Field(min_length=1)
    gate_name: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> GateResult:
        if self.gate_id != identity(self, "gate_id", "finance_v26_217_gate:"):
            raise ValueError("v26.217 Gate identity differs")
        return self


class GateEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    gates: tuple[GateResult, ...] = Field(min_length=8, max_length=8)
    passed_count: Literal[8] = 8
    failed_count: Literal[0] = 0
    all_gates_passed: Literal[True] = True
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evaluation(self) -> GateEvaluation:
        if len({item.gate_name for item in self.gates}) != 8 or self.evaluation_id != identity(
            self, "evaluation_id", "finance_v26_217_gate_evaluation:"
        ):
            raise ValueError("v26.217 Gate Evaluation differs")
        return self


class Decision(FrozenModel):
    decision_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_upstream_typed_failure_event_authority_and_artifact_backing_"
        "preflight_passed_independent_audit_required_online_execution_blocked"
    ] = DECISION
    external_authorization_id: str = Field(min_length=1)
    v216_freeze_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    execution_audit_id: str = Field(min_length=1)
    negative_control_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> Decision:
        if self.decision_id != identity(
            self, "decision_id", "finance_v26_217_upstream_event_authority_decision:"
        ):
            raise ValueError("v26.217 Decision differs")
        return self


class Transition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    status: Literal["PASSED_PREFLIGHT_ONLINE_EXECUTION_BLOCKED"] = (
        "PASSED_PREFLIGHT_ONLINE_EXECUTION_BLOCKED"
    )
    next_stage: Literal[
        "fresh_repaired_upstream_typed_failure_event_authority_and_artifact_backing_"
        "preflight_independent_audit_only"
    ] = NEXT_STAGE
    provider_execution_authorized: Literal[False] = False
    new_online_authorization_required_after_independent_audit: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> Transition:
        if self.transition_id != identity(self, "transition_id", "finance_v26_217_transition:"):
            raise ValueError("v26.217 Transition differs")
        return self


class Report(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v216_freeze_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    upstream_event_source_binding_id: str = Field(min_length=1)
    upstream_observation_binding_id: str = Field(min_length=1)
    runner_observation_binding_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    execution_audit_id: str = Field(min_length=1)
    negative_control_audit_id: str = Field(min_length=1)
    scope_boundary_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_upstream_typed_failure_event_authority_and_artifact_backing_"
        "preflight_passed_independent_audit_required_online_execution_blocked"
    ] = DECISION
    current_v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> Report:
        if self.report_id != identity(
            self, "report_id", "finance_v26_217_upstream_event_authority_report:"
        ):
            raise ValueError("v26.217 Report differs")
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
        if (
            self.file_count != len(self.members)
            or self.total_byte_count != sum(item.byte_count for item in self.members)
            or tuple(item.relative_path for item in self.members)
            != tuple(sorted({item.relative_path for item in self.members}))
        ):
            raise ValueError("v26.217 Artifact Manifest geometry differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_217_artifact_root:",
        )
        if self.artifact_root != expected_root or self.manifest_id != identity(
            self, "manifest_id", "finance_v26_217_artifact_manifest:"
        ):
            raise ValueError("v26.217 Artifact Root or Manifest differs")
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
        prefix="finance_v26_217_artifact_root:",
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
            prefix="finance_v26_217_artifact_manifest:",
        ),
    )
