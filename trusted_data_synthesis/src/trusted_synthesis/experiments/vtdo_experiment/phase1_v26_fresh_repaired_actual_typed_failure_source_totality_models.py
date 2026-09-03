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

SCHEMA_VERSION: Final = "fresh_repaired_actual_typed_failure_source_totality.v1"
CONSUMED_STAGE: Final = (
    "fresh_repaired_actual_v209_typed_failure_source_surface_"
    "totality_and_runner_owned_observation_preflight_only"
)
NEXT_STAGE: Final = (
    "fresh_repaired_actual_v209_typed_failure_source_surface_totality_"
    "and_runner_owned_observation_preflight_independent_audit_only"
)
DECISION: Final = (
    "fresh_repaired_actual_v209_typed_failure_source_surface_totality_and_runner_owned_"
    "observation_preflight_passed_independent_audit_required_online_execution_blocked"
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
ACTUAL_TERMINAL_KINDS: Final = ("instrument_failure", "privacy_rejection")
FAILURE_ORIGIN_ITEMS: Final = (
    ("transport_send", ("instrument_failure",)),
    ("public_projection", ("instrument_failure", "privacy_rejection")),
)
FAILURE_ORIGIN_TERMINALS: Final = dict(FAILURE_ORIGIN_ITEMS)
SOURCE_CONTROL_ITEMS: Final = (
    ("transport_invalid_dispatch_chain", "transport_send", "instrument_failure"),
    ("transport_empty_queue", "transport_send", "instrument_failure"),
    ("projection_reasoning_key", "public_projection", "privacy_rejection"),
    ("projection_non_object", "public_projection", "instrument_failure"),
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
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_byte_count: Literal[13092] = 13092
    operator_directive: Literal["参照审计报告开展后续实验修订"] = "参照审计报告开展后续实验修订"
    operator_directive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    operator_directive_byte_count: Literal[42] = 42
    audit_result: Literal["VALID_SCOPED_DEDICATED_EXCEPTION_SUBCLASS_CONTROLS"] = (
        "VALID_SCOPED_DEDICATED_EXCEPTION_SUBCLASS_CONTROLS"
    )
    failed_at: Literal["ACTUAL_V209_TYPED_FAILURE_SOURCE_SURFACE_TOTALITY"] = (
        "ACTUAL_V209_TYPED_FAILURE_SOURCE_SURFACE_TOTALITY"
    )
    consumed_stage: Literal[
        "fresh_repaired_actual_v209_typed_failure_source_surface_"
        "totality_and_runner_owned_observation_preflight_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    online_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalRevisionAuthorization:
        if self.authorization_id != identity(
            self, "authorization_id", "finance_v26_215_external_revision_authorization:"
        ):
            raise ValueError("v26.215 external authorization identity differs")
        return self


class V214Freeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v214_report_id: str = Field(min_length=1)
    v214_decision_id: str = Field(min_length=1)
    v214_transition_id: str = Field(min_length=1)
    v214_artifact_manifest_id: str = Field(min_length=1)
    v214_artifact_root: str = Field(min_length=1)
    v214_source_commit: Literal["9bf04108c0b3d7d8f979246c786089927eedb16f"] = (
        "9bf04108c0b3d7d8f979246c786089927eedb16f"
    )
    v214_source_tree: Literal["7dfacd9eabbf8efb6f2269b362c6e2c739fcfca9"] = (
        "7dfacd9eabbf8efb6f2269b362c6e2c739fcfca9"
    )
    formal_file_count: Literal[63] = 63
    formal_total_byte_count: Literal[1535767] = 1535767
    manifest_member_count: Literal[62] = 62
    manifest_member_byte_count: Literal[1523563] = 1523563
    generic_evidence_surface_retained: Literal[True] = True
    authority_byte_attacks_retained: Literal[True] = True
    dedicated_exception_controls_retained: Literal[True] = True
    actual_v209_source_totality_failed: Literal[True] = True
    first_blocker: Literal[
        "class_name_registry_excludes_actual_base_typed_transport_failure_sources"
    ] = "class_name_registry_excludes_actual_base_typed_transport_failure_sources"
    v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V214Freeze:
        if self.freeze_id != identity(self, "freeze_id", "finance_v26_215_v214_freeze:"):
            raise ValueError("v26.215 v26.214 Freeze identity differs")
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
            self, "source_identity_id", "finance_v26_215_source_identity:"
        ):
            raise ValueError("v26.215 source identity differs")
        return self


class ImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v214_freeze_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    files: tuple[SourceBinding, ...] = Field(min_length=4, max_length=4)
    symbols: tuple[SourceBinding, ...] = Field(min_length=7)
    direct_network_routes: Literal[0] = 0
    credential_environment_routes: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ImplementationBinding:
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_repaired_actual_typed_failure_source_totality_implementation_binding:",
        ):
            raise ValueError("v26.215 implementation Binding differs")
        return self


class TypedFailureSourceContract(FrozenModel):
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
    admitted_exception_type_ids: tuple[str, ...] = (EXACT_V209_EXCEPTION_TYPE_ID,)
    failure_origin_terminals: tuple[tuple[str, tuple[str, ...]], ...] = FAILURE_ORIGIN_ITEMS
    scripted_transport_raise_callsite_count: Literal[2] = 2
    public_projection_raise_callsite_count: Literal[2] = 2
    total_raise_callsite_count: Literal[4] = 4
    scripted_transport_send_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    public_projection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bare_class_name_authority: Literal[False] = False
    class_to_unique_terminal_required: Literal[False] = False
    instance_terminal_required: Literal[True] = True
    exact_failure_origin_required: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> TypedFailureSourceContract:
        if (
            self.admitted_exception_type_ids != (EXACT_V209_EXCEPTION_TYPE_ID,)
            or self.failure_origin_terminals != FAILURE_ORIGIN_ITEMS
            or self.contract_id
            != identity(
                self,
                "contract_id",
                "fresh_repaired_actual_v209_typed_failure_source_contract:",
            )
        ):
            raise ValueError("v26.215 typed failure Source Contract differs")
        return self


class RunnerObservationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    exact_v209_runner_id: Literal[
        "fresh_repaired_final_continuity_executable_full_condition_runner:"
        "e58b8318667568b9becbb1fa946f1ac079937c9c744b6a2c4877661abebf0266"
    ] = EXACT_V209_RUNNER_ID
    runner_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminalizer_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation_authority_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation_constructed_from_actual_caught_instance: Literal[True] = True
    separate_transport_and_projection_catches: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> RunnerObservationBinding:
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_repaired_actual_source_runner_observation_binding:",
        ):
            raise ValueError("v26.215 Runner observation Binding differs")
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
    exception_type_id: Literal[
        "trusted_synthesis.experiments.vtdo_experiment."
        "phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight:"
        "TypedTransportFailure"
    ] = EXACT_V209_EXCEPTION_TYPE_ID
    exception_module: str = Field(min_length=1)
    exception_qualname: str = Field(min_length=1)
    failure_origin: Literal["transport_send", "public_projection"]
    caught_terminal_kind: Literal["instrument_failure", "privacy_rejection"]
    exception_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    invocation_record: dict[str, Any]
    runner_owned: Literal[True] = True
    actual_source_admitted: Literal[True] = True
    terminal_label_input: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> TypedFailureObservation:
        record = v209_models.ExecutableInvocationRecord.model_validate(self.invocation_record)
        allowed = FAILURE_ORIGIN_TERMINALS.get(self.failure_origin, ())
        expected_type_id = f"{self.exception_module}:{self.exception_qualname}"
        if (
            self.exception_type_id != EXACT_V209_EXCEPTION_TYPE_ID
            or expected_type_id != self.exception_type_id
            or self.caught_terminal_kind not in allowed
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
                "fresh_repaired_actual_source_typed_failure_observation:",
            )
        ):
            raise ValueError("actual-source typed failure observation differs")
        return self


class AuthenticatedTypedFailureEvidence(FrozenModel):
    evidence_id: str = Field(min_length=1)
    evidence_kind: Literal["runner_owned_actual_source_typed_failure"] = (
        "runner_owned_actual_source_typed_failure"
    )
    job_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    failure_observation: TypedFailureObservation
    expected_terminal_input: Literal[False] = False
    caller_selected_exception_type: Literal[False] = False
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
                "fresh_repaired_actual_source_authenticated_typed_failure_evidence:",
            )
        ):
            raise ValueError("actual-source authenticated evidence differs")
        return self


class DispatcherBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    runner_observation_binding_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    source_v195_terminal_registry_id: str = Field(min_length=1)
    dispatcher_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_kinds: tuple[str, ...] = ACTUAL_TERMINAL_KINDS
    terminal_policy_ids: tuple[str, ...] = Field(min_length=2, max_length=2)
    authority_ledger_match_required: Literal[True] = True
    terminal_from_instance_field_and_origin: Literal[True] = True
    terminal_kind_input_allowed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> DispatcherBinding:
        if (
            self.terminal_kinds != ACTUAL_TERMINAL_KINDS
            or len(set(self.terminal_policy_ids)) != 2
            or self.binding_id
            != identity(
                self,
                "binding_id",
                "fresh_repaired_actual_source_typed_failure_dispatcher_binding:",
            )
        ):
            raise ValueError("v26.215 Dispatcher Binding differs")
        return self


class PersistenceBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    source_v214_persistence_binding_id: str = Field(min_length=1)
    persistence_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_dispatch_rederivation_required: Literal[True] = True
    authority_revalidation_required: Literal[True] = True
    raw_before_result_required: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> PersistenceBinding:
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_repaired_actual_source_typed_failure_persistence_binding:",
        ):
            raise ValueError("v26.215 persistence Binding differs")
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
    one_entry_function: Literal["ActualSourceFailureConsumer.execute_preflight"] = (
        "ActualSourceFailureConsumer.execute_preflight"
    )
    current_v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ConsumerBinding:
        if self.binding_id != identity(
            self, "binding_id", "fresh_repaired_actual_source_failure_consumer_binding:"
        ):
            raise ValueError("v26.215 consumer Binding differs")
        return self


class CompositionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    v214_freeze_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    runner_observation_binding_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    persistence_binding_id: str = Field(min_length=1)
    exact_sequence: tuple[str, ...] = (
        "authorization_guard",
        "durable_preflight_consumption_receipt",
        "durable_run_start_receipt",
        "credential_and_factory_gate",
        "actual_v209_failure_source",
        "origin_specific_runner_catch",
        "runner_owned_observation",
        "consumer_terminal_branch",
        "source_contract_and_registry_dispatch",
        "raw_result_trace_outcome_checkpoint",
    )
    current_v211_authorization_consumed: Literal[False] = False
    new_online_authorization_created: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> CompositionContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_repaired_actual_source_failure_composition_contract:",
        ):
            raise ValueError("v26.215 Composition Contract differs")
        return self


class DerivedTerminalDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    dispatcher_binding_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    exception_type_id: str = Field(min_length=1)
    failure_origin: Literal["transport_send", "public_projection"]
    terminal_kind: Literal["instrument_failure", "privacy_rejection"]
    terminal_policy_id: str = Field(min_length=1)
    exception_reason_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivation_rule: Literal[
        "exact_type_instance_terminal_origin_record_and_registry_agreement"
    ] = "exact_type_instance_terminal_origin_record_and_registry_agreement"
    terminal_label_was_input: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> DerivedTerminalDecision:
        if self.decision_id != identity(
            self,
            "decision_id",
            "fresh_repaired_actual_source_typed_failure_terminal_decision:",
        ):
            raise ValueError("v26.215 terminal Decision differs")
        return self


class PersistedEvidenceDescriptor(FrozenModel):
    descriptor_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    terminal_kind: Literal["instrument_failure", "privacy_rejection"]
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
                "finance_v26_215_actual_source_persisted_descriptor:",
            )
        ):
            raise ValueError("v26.215 persisted Descriptor differs")
        return self


class SourceSurfaceControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    expected_origin: Literal["transport_send", "public_projection"]
    expected_terminal: Literal["instrument_failure", "privacy_rejection"]
    failure_observation: TypedFailureObservation
    evidence: AuthenticatedTypedFailureEvidence
    decision: DerivedTerminalDecision
    persistence: PersistedEvidenceDescriptor
    actual_v209_base_exception: Literal[True] = True
    expected_values_used_only_after_dispatch: Literal[True] = True
    exception_escape: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> SourceSurfaceControl:
        if (
            (self.control_name, self.expected_origin, self.expected_terminal)
            not in SOURCE_CONTROL_ITEMS
            or self.failure_observation.failure_origin != self.expected_origin
            or self.failure_observation.caught_terminal_kind != self.expected_terminal
            or self.failure_observation.exception_type_id != EXACT_V209_EXCEPTION_TYPE_ID
            or self.evidence.evidence_id != self.decision.evidence_id
            or self.persistence.decision_id != self.decision.decision_id
            or self.control_id
            != identity(self, "control_id", "finance_v26_215_actual_source_failure_control:")
        ):
            raise ValueError("v26.215 source-surface Control differs")
        return self


class SourceSurfaceExecutionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    consumption_receipt_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    controls: tuple[SourceSurfaceControl, ...] = Field(min_length=4, max_length=4)
    actual_v209_raise_callsite_count: Literal[4] = 4
    exercised_source_callsite_count: Literal[4] = 4
    actual_base_exception_count: Literal[4] = 4
    runner_owned_observation_count: Literal[4] = 4
    consumer_terminal_branch_count: Literal[4] = 4
    exact_origin_terminal_match_count: Literal[4] = 4
    persisted_layer_count: Literal[20] = 20
    exception_escape_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> SourceSurfaceExecutionAudit:
        observed = tuple(
            (item.control_name, item.expected_origin, item.expected_terminal)
            for item in self.controls
        )
        if observed != SOURCE_CONTROL_ITEMS or self.audit_id != identity(
            self, "audit_id", "finance_v26_215_actual_source_surface_execution_audit:"
        ):
            raise ValueError("v26.215 source-surface execution Audit differs")
        return self


class NegativeControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    rejection_stage: Literal["observation_validation", "persistence_pre_raw"]
    rejected: Literal[True] = True
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
            or len(self.fully_rehashed_downstream_layer_ids) not in (0, 5)
            or self.control_id
            != identity(self, "control_id", "finance_v26_215_source_totality_negative_control:")
        ):
            raise ValueError("v26.215 negative Control differs")
        return self


class NegativeControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    controls: tuple[NegativeControl, ...] = Field(min_length=6, max_length=6)
    rejected_count: Literal[6] = 6
    accepted_count: Literal[0] = 0
    source_admission_rejection_count: Literal[2] = 2
    retained_authority_attack_count: Literal[4] = 4
    fully_rehashed_attack_count: Literal[4] = 4
    fully_rehashed_downstream_layer_identity_count: Literal[20] = 20
    raw_write_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> NegativeControlAudit:
        expected = {
            "base_exception_unregistered_terminal",
            "nonregistered_exact_class_spoof",
            "instrument_observation_reclassified_as_provider_identity",
            "privacy_observation_reclassified_as_transport",
            "exception_reason_hash_replaced",
            "cross_job_failure_observation_substituted",
        }
        if {item.control_name for item in self.controls} != expected or self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_215_source_totality_negative_control_audit:",
        ):
            raise ValueError("v26.215 negative-control Audit differs")
        return self


class ScopeBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v214_freeze_id: str = Field(min_length=1)
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
        if self.audit_id != identity(self, "audit_id", "finance_v26_215_scope_boundary_audit:"):
            raise ValueError("v26.215 scope boundary Audit differs")
        return self


class GateResult(FrozenModel):
    gate_id: str = Field(min_length=1)
    gate_name: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> GateResult:
        if self.gate_id != identity(self, "gate_id", "finance_v26_215_gate:"):
            raise ValueError("v26.215 Gate identity differs")
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
            self, "evaluation_id", "finance_v26_215_gate_evaluation:"
        ):
            raise ValueError("v26.215 Gate Evaluation differs")
        return self


class Decision(FrozenModel):
    decision_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_actual_v209_typed_failure_source_surface_totality_and_runner_owned_"
        "observation_preflight_passed_independent_audit_required_online_execution_blocked"
    ] = DECISION
    external_authorization_id: str = Field(min_length=1)
    v214_freeze_id: str = Field(min_length=1)
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
            self, "decision_id", "finance_v26_215_source_totality_decision:"
        ):
            raise ValueError("v26.215 Decision differs")
        return self


class Transition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    status: Literal["PASSED_PREFLIGHT_ONLINE_EXECUTION_BLOCKED"] = (
        "PASSED_PREFLIGHT_ONLINE_EXECUTION_BLOCKED"
    )
    next_stage: Literal[
        "fresh_repaired_actual_v209_typed_failure_source_surface_totality_"
        "and_runner_owned_observation_preflight_independent_audit_only"
    ] = NEXT_STAGE
    provider_execution_authorized: Literal[False] = False
    new_online_authorization_required_after_independent_audit: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> Transition:
        if self.transition_id != identity(self, "transition_id", "finance_v26_215_transition:"):
            raise ValueError("v26.215 Transition differs")
        return self


class Report(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v214_freeze_id: str = Field(min_length=1)
    source_contract_id: str = Field(min_length=1)
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
        "fresh_repaired_actual_v209_typed_failure_source_surface_totality_and_runner_owned_"
        "observation_preflight_passed_independent_audit_required_online_execution_blocked"
    ] = DECISION
    current_v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> Report:
        if self.report_id != identity(self, "report_id", "finance_v26_215_source_totality_report:"):
            raise ValueError("v26.215 Report differs")
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
            raise ValueError("v26.215 Artifact Manifest geometry differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_215_artifact_root:",
        )
        if self.artifact_root != expected_root or self.manifest_id != identity(
            self, "manifest_id", "finance_v26_215_artifact_manifest:"
        ):
            raise ValueError("v26.215 Artifact Root or Manifest differs")
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
        prefix="finance_v26_215_artifact_root:",
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
            prefix="finance_v26_215_artifact_manifest:",
        ),
    )
