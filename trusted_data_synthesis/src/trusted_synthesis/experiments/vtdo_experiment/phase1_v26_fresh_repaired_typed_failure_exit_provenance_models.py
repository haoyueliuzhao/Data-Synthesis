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

SCHEMA_VERSION: Final = "fresh_repaired_typed_failure_exit_provenance.v1"
CONSUMED_STAGE: Final = (
    "fresh_repaired_actual_v209_typed_failure_exit_surface_"
    "callsite_and_rethrow_provenance_preflight_only"
)
NEXT_STAGE: Final = (
    "fresh_repaired_actual_v209_typed_failure_exit_surface_callsite_and_rethrow_"
    "provenance_preflight_independent_audit_only"
)
DECISION: Final = (
    "fresh_repaired_actual_v209_typed_failure_exit_surface_callsite_and_rethrow_"
    "provenance_preflight_passed_independent_audit_required_online_execution_blocked"
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
    review_sha256: Literal["b80e8d540bb8c643045c71a075e7d154c52fe9a1b33d506191655cfb929fcc23"]
    review_byte_count: Literal[12959] = 12_959
    operator_directive: Literal["参照审计报告继续实验修订"] = "参照审计报告继续实验修订"
    operator_directive_sha256: Literal[
        "dc2b598ec3667bd0e26354d1dac1ca447fa87acea50bd30a5fc245a9c35374e9"
    ]
    operator_directive_byte_count: Literal[36] = 36
    audit_result: Literal["VALID_SCOPED_FOUR_DIRECT_CONSTRUCTOR_RAISE_CONTROLS"] = (
        "VALID_SCOPED_FOUR_DIRECT_CONSTRUCTOR_RAISE_CONTROLS"
    )
    failed_at: Literal["ACTUAL_V209_TYPED_FAILURE_EXIT_SURFACE_PROVENANCE_CLOSURE"] = (
        "ACTUAL_V209_TYPED_FAILURE_EXIT_SURFACE_PROVENANCE_CLOSURE"
    )
    consumed_stage: Literal[
        "fresh_repaired_actual_v209_typed_failure_exit_surface_"
        "callsite_and_rethrow_provenance_preflight_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    online_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalRevisionAuthorization:
        if self.authorization_id != identity(
            self, "authorization_id", "finance_v26_216_external_revision_authorization:"
        ):
            raise ValueError("v26.216 external authorization identity differs")
        return self


class V215Freeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v215_report_id: str = Field(min_length=1)
    v215_decision_id: str = Field(min_length=1)
    v215_transition_id: str = Field(min_length=1)
    v215_artifact_manifest_id: str = Field(min_length=1)
    v215_artifact_root: str = Field(min_length=1)
    v215_source_commit: Literal["bae3bafbedeb3c18dd04b21ebabf6c4138c14ced"] = (
        "bae3bafbedeb3c18dd04b21ebabf6c4138c14ced"
    )
    v215_source_tree: Literal["0740f9c5a56e107e5deb07fed7637b29c8a91ad9"] = (
        "0740f9c5a56e107e5deb07fed7637b29c8a91ad9"
    )
    formal_file_count: Literal[44] = 44
    formal_total_byte_count: Literal[785750] = 785_750
    manifest_member_count: Literal[43] = 43
    manifest_member_byte_count: Literal[777701] = 777_701
    four_direct_constructor_controls_retained: Literal[True] = True
    runner_authority_byte_attacks_retained: Literal[True] = True
    complete_exit_surface_failed: Literal[True] = True
    first_blocker: Literal[
        "constructor_syntax_count_omits_scripted_transport_raise_value_rethrow"
    ] = "constructor_syntax_count_omits_scripted_transport_raise_value_rethrow"
    v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V215Freeze:
        if self.freeze_id != identity(self, "freeze_id", "finance_v26_216_v215_freeze:"):
            raise ValueError("v26.216 v26.215 Freeze identity differs")
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
            self, "source_identity_id", "finance_v26_216_source_identity:"
        ):
            raise ValueError("v26.216 source identity differs")
        return self


class ImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v215_freeze_id: str = Field(min_length=1)
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
            "fresh_repaired_typed_failure_exit_provenance_implementation_binding:",
        ):
            raise ValueError("v26.216 implementation Binding differs")
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
            raise ValueError("v26.216 Source Exit declaration differs")
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
            raise ValueError("v26.216 typed-failure Exit Surface Contract differs")
        return self


class UpstreamFailureProducerBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    source_v195_terminal_registry_id: str = Field(min_length=1)
    terminal_policy_items: tuple[tuple[str, str], ...] = Field(min_length=16)
    producer_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> UpstreamFailureProducerBinding:
        kinds = tuple(item[0] for item in self.terminal_policy_items)
        policies = tuple(item[1] for item in self.terminal_policy_items)
        if (
            len(set(kinds)) != len(kinds)
            or len(set(policies)) != len(policies)
            or self.binding_id
            != identity(
                self,
                "binding_id",
                "fresh_repaired_upstream_typed_failure_producer_binding:",
            )
        ):
            raise ValueError("v26.216 upstream producer Binding differs")
        return self


class UpstreamFailureObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    producer_binding_id: str = Field(min_length=1)
    source_event_id: str = Field(min_length=1)
    exception_type_id: Literal[
        "trusted_synthesis.experiments.vtdo_experiment."
        "phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight:"
        "TypedTransportFailure"
    ] = EXACT_V209_EXCEPTION_TYPE_ID
    terminal_kind: str = Field(min_length=1)
    exception_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_policy_id: str = Field(min_length=1)
    created_by_bound_producer: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> UpstreamFailureObservation:
        if self.observation_id != identity(
            self,
            "observation_id",
            "fresh_repaired_upstream_typed_failure_observation:",
        ):
            raise ValueError("v26.216 upstream failure observation differs")
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
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_proof(self) -> SourceExitProof:
        if self.source_exit_kind == "authenticated_rethrow":
            valid = self.upstream_failure_observation_id is not None
        else:
            valid = self.upstream_failure_observation_id is None
        if not valid or self.proof_id != identity(
            self, "proof_id", "fresh_repaired_v209_typed_failure_source_exit_proof:"
        ):
            raise ValueError("v26.216 Source Exit proof differs")
        return self


class RunnerObservationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    upstream_producer_binding_id: str = Field(min_length=1)
    exact_v209_runner_id: Literal[
        "fresh_repaired_final_continuity_executable_full_condition_runner:"
        "e58b8318667568b9becbb1fa946f1ac079937c9c744b6a2c4877661abebf0266"
    ] = EXACT_V209_RUNNER_ID
    inherited_v215_runner_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
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
            "fresh_repaired_exit_provenance_runner_observation_binding:",
        ):
            raise ValueError("v26.216 Runner observation Binding differs")
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
                "fresh_repaired_exit_provenance_typed_failure_observation:",
            )
        ):
            raise ValueError("v26.216 typed failure observation differs")
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
                "fresh_repaired_exit_provenance_authenticated_typed_failure_evidence:",
            )
        ):
            raise ValueError("v26.216 authenticated evidence differs")
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
                "fresh_repaired_exit_provenance_dispatcher_binding:",
            )
        ):
            raise ValueError("v26.216 Dispatcher Binding differs")
        return self


class PersistenceBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    source_v215_persistence_binding_id: str = Field(min_length=1)
    persistence_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_dispatch_rederivation_required: Literal[True] = True
    source_exit_proof_revalidation_required: Literal[True] = True
    raw_before_result_required: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> PersistenceBinding:
        if self.binding_id != identity(
            self, "binding_id", "fresh_repaired_exit_provenance_persistence_binding:"
        ):
            raise ValueError("v26.216 persistence Binding differs")
        return self


class ConsumerBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    exact_v211_authorization_id: str = Field(min_length=1)
    exact_v209_manifest_id: str = Field(min_length=1)
    source_v212_consumption_contract_id: str = Field(min_length=1)
    source_v212_run_start_contract_id: str = Field(min_length=1)
    runner_observation_binding_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    persistence_binding_id: str = Field(min_length=1)
    execute_preflight_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    one_entry_function: Literal["ExitProvenanceFailureConsumer.execute_preflight"] = (
        "ExitProvenanceFailureConsumer.execute_preflight"
    )
    current_v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ConsumerBinding:
        if self.binding_id != identity(
            self, "binding_id", "fresh_repaired_exit_provenance_failure_consumer_binding:"
        ):
            raise ValueError("v26.216 consumer Binding differs")
        return self


class CompositionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    v215_freeze_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    upstream_producer_binding_id: str = Field(min_length=1)
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
        "upstream_authority_required_for_rethrow",
        "source_exit_proof",
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
            self, "contract_id", "fresh_repaired_exit_provenance_composition_contract:"
        ):
            raise ValueError("v26.216 Composition Contract differs")
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
        "source_exit_proof_upstream_authority_record_and_registry_agreement"
    ] = "source_exit_proof_upstream_authority_record_and_registry_agreement"
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
            "fresh_repaired_exit_provenance_terminal_decision:",
        ):
            raise ValueError("v26.216 derived terminal Decision differs")
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
                "finance_v26_216_exit_provenance_persisted_descriptor:",
            )
        ):
            raise ValueError("v26.216 persisted descriptor differs")
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
            != identity(self, "control_id", "finance_v26_216_typed_failure_exit_control:")
        ):
            raise ValueError("v26.216 Exit Surface control differs")
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
            self, "audit_id", "finance_v26_216_exit_surface_execution_audit:"
        ):
            raise ValueError("v26.216 Exit Surface execution Audit differs")
        return self


class NegativeControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    rejection_stage: Literal["source_exit_admission", "persistence_pre_raw"]
    rejected: Literal[True] = True
    rejected_before_runner_authority_append: bool
    rejected_before_raw_write: Literal[True] = True
    fully_rehashed: bool
    fully_rehashed_downstream_layer_ids: tuple[str, ...] = Field(max_length=5)
    rejection_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> NegativeControl:
        if (
            self.fully_rehashed != bool(self.fully_rehashed_downstream_layer_ids)
            or self.rejected_before_runner_authority_append
            != (self.rejection_stage == "source_exit_admission")
            or self.control_id
            != identity(self, "control_id", "finance_v26_216_exit_provenance_negative_control:")
        ):
            raise ValueError("v26.216 negative control differs")
        return self


class NegativeControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    controls: tuple[NegativeControl, ...] = Field(min_length=7, max_length=7)
    rejected_count: Literal[7] = 7
    accepted_count: Literal[0] = 0
    unauthenticated_registered_rethrow_rejection_count: Literal[1] = 1
    additional_source_admission_rejection_count: Literal[2] = 2
    retained_authority_attack_count: Literal[4] = 4
    fully_rehashed_attack_count: Literal[4] = 4
    fully_rehashed_downstream_layer_identity_count: Literal[20] = 20
    runner_authority_append_count: Literal[0] = 0
    raw_write_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> NegativeControlAudit:
        expected = {
            "registered_terminal_rethrow_without_upstream_authority",
            "unregistered_terminal_rethrow",
            "nonregistered_exact_class_spoof",
            "instrument_observation_reclassified_as_provider_identity",
            "privacy_observation_reclassified_as_transport",
            "exception_reason_hash_replaced",
            "cross_job_failure_observation_substituted",
        }
        if {item.control_name for item in self.controls} != expected or self.audit_id != identity(
            self, "audit_id", "finance_v26_216_exit_provenance_negative_control_audit:"
        ):
            raise ValueError("v26.216 negative-control Audit differs")
        return self


class ScopeBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v215_freeze_id: str = Field(min_length=1)
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
        if self.audit_id != identity(self, "audit_id", "finance_v26_216_scope_boundary_audit:"):
            raise ValueError("v26.216 scope boundary Audit differs")
        return self


class GateResult(FrozenModel):
    gate_id: str = Field(min_length=1)
    gate_name: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> GateResult:
        if self.gate_id != identity(self, "gate_id", "finance_v26_216_gate:"):
            raise ValueError("v26.216 Gate identity differs")
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
            self, "evaluation_id", "finance_v26_216_gate_evaluation:"
        ):
            raise ValueError("v26.216 Gate Evaluation differs")
        return self


class Decision(FrozenModel):
    decision_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_actual_v209_typed_failure_exit_surface_callsite_and_rethrow_"
        "provenance_preflight_passed_independent_audit_required_online_execution_blocked"
    ] = DECISION
    external_authorization_id: str = Field(min_length=1)
    v215_freeze_id: str = Field(min_length=1)
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
            self, "decision_id", "finance_v26_216_exit_provenance_decision:"
        ):
            raise ValueError("v26.216 Decision differs")
        return self


class Transition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    status: Literal["PASSED_PREFLIGHT_ONLINE_EXECUTION_BLOCKED"] = (
        "PASSED_PREFLIGHT_ONLINE_EXECUTION_BLOCKED"
    )
    next_stage: Literal[
        "fresh_repaired_actual_v209_typed_failure_exit_surface_callsite_and_rethrow_"
        "provenance_preflight_independent_audit_only"
    ] = NEXT_STAGE
    provider_execution_authorized: Literal[False] = False
    new_online_authorization_required_after_independent_audit: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> Transition:
        if self.transition_id != identity(self, "transition_id", "finance_v26_216_transition:"):
            raise ValueError("v26.216 Transition differs")
        return self


class Report(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v215_freeze_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    upstream_producer_binding_id: str = Field(min_length=1)
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
        "fresh_repaired_actual_v209_typed_failure_exit_surface_callsite_and_rethrow_"
        "provenance_preflight_passed_independent_audit_required_online_execution_blocked"
    ] = DECISION
    current_v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> Report:
        if self.report_id != identity(self, "report_id", "finance_v26_216_exit_provenance_report:"):
            raise ValueError("v26.216 Report differs")
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
            raise ValueError("v26.216 Artifact Manifest geometry differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_216_artifact_root:",
        )
        if self.artifact_root != expected_root or self.manifest_id != identity(
            self, "manifest_id", "finance_v26_216_artifact_manifest:"
        ):
            raise ValueError("v26.216 Artifact Root or Manifest differs")
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
        prefix="finance_v26_216_artifact_root:",
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
            prefix="finance_v26_216_artifact_manifest:",
        ),
    )
