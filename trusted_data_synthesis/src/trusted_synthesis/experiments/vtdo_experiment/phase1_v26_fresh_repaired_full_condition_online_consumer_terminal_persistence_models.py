# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_repaired_online_consumer_terminal_persistence_preflight.v1"
CONSUMED_STAGE: Final = (
    "fresh_repaired_full_condition_exact_online_execution_"
    "consumer_and_terminal_persistence_integration_preflight_only"
)
NEXT_STAGE: Final = (
    "fresh_repaired_full_condition_exact_online_execution_consumer_and_"
    "terminal_persistence_integration_preflight_independent_audit_only"
)
DECISION: Final = (
    "fresh_repaired_exact_online_consumer_terminal_persistence_preflight_passed_"
    "independent_audit_required_online_execution_blocked"
)
TERMINAL_KINDS: Final = (
    "completed_qualified",
    "completed_invalid",
    "first_response_abi_invalid",
    "correction_response_abi_invalid",
    "first_action_reference_invalid",
    "correction_action_reference_invalid",
    "correction_attempt_typed_invalid",
    "final_response_abi_invalid",
    "provider_failure_no_payload",
    "provider_transport_failure",
    "privacy_rejection",
    "resource_budget_exhausted",
    "instrument_failure",
    "provider_identity_failure",
    "thinking_integrity_failure",
    "usage_integrity_failure",
)
EXECUTION_SEQUENCE: Final = (
    "validate_exact_v211_authorization_bytes",
    "validate_source_bound_consumer_and_composition",
    "durably_consume_preflight_lease_no_replace",
    "durably_persist_run_start_receipt",
    "cross_credential_boundary_without_lookup",
    "construct_transport_and_writer_factories",
    "execute_exact_v209_current_state_runner",
    "dispatch_complete_authoritative_terminal",
    "persist_raw_before_result",
    "reconstruct_and_persist_trace_outcome_checkpoint",
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


class ExternalRepairAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: Literal["400e1b6960df1d69ed71a9265bf084551abb465ad92b9718045132be4b7fd462"]
    review_byte_count: Literal[14475] = 14_475
    audit_result: Literal["VALID_SCOPED_ONLINE_AUTHORIZATION_OBJECT_PREFLIGHT"] = (
        "VALID_SCOPED_ONLINE_AUTHORIZATION_OBJECT_PREFLIGHT"
    )
    direct_online_consumption: Literal["BLOCKED"] = "BLOCKED"
    mandatory_revision: Literal["ONE_NARROW_EXECUTION_INGRESS_REPAIR"] = (
        "ONE_NARROW_EXECUTION_INGRESS_REPAIR"
    )
    operator_directive: Literal["参照审计报告修订"] = "参照审计报告修订"
    operator_directive_sha256: Literal[
        "114f98b0f559b26885ce8c278d84bd0a5915947c285752bd1b04483458954c10"
    ]
    operator_directive_byte_count: Literal[24] = 24
    consumed_stage: Literal[
        "fresh_repaired_full_condition_exact_online_execution_consumer_and_terminal_persistence_integration_preflight_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    online_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalRepairAuthorization:
        directive = self.operator_directive.encode("utf-8")
        if (
            len(directive) != self.operator_directive_byte_count
            or hashlib.sha256(directive).hexdigest() != self.operator_directive_sha256
        ):
            raise ValueError("v26.212 operator directive bytes differ")
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_212_external_repair_authorization:",
        ):
            raise ValueError("v26.212 external authorization identity differs")
        return self


class V211Freeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v211_report_id: str = Field(min_length=1)
    v211_decision_id: str = Field(min_length=1)
    v211_transition_id: str = Field(min_length=1)
    v211_authorization_id: str = Field(min_length=1)
    v211_composition_contract_id: str = Field(min_length=1)
    v211_artifact_manifest_id: str = Field(min_length=1)
    v211_artifact_root: str = Field(min_length=1)
    v211_source_commit: Literal["ed62189a162601e97a48b2ab91840c680abe7794"]
    v211_source_tree: Literal["d35134034991a7b330b2214cc67036a60f4fa289"]
    exact_authorization_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    formal_file_count: Literal[17] = 17
    formal_total_byte_count: Literal[137306] = 137_306
    manifest_member_count: Literal[16] = 16
    manifest_member_byte_count: Literal[134503] = 134_503
    authorization_object_preflight_retained: Literal[True] = True
    direct_online_consumption_blocked: Literal[True] = True
    v211_authorization_consumed: Literal[False] = False
    historical_artifact_mutation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V211Freeze:
        if self.freeze_id != identity(self, "freeze_id", "finance_v26_212_v211_freeze:"):
            raise ValueError("v26.212 v26.211 Freeze identity differs")
        return self


class SourceSymbolBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class ImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v211_freeze_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    files: tuple[SourceSymbolBinding, ...] = Field(min_length=3)
    symbols: tuple[SourceSymbolBinding, ...] = Field(min_length=8)
    provider_network_symbols: Literal[0] = 0
    credential_environment_symbols: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ImplementationBinding:
        if tuple(item.relative_path for item in self.files) != tuple(
            sorted({item.relative_path for item in self.files})
        ) or len({item.symbol for item in self.symbols}) != len(self.symbols):
            raise ValueError("v26.212 implementation source set differs")
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_repaired_online_consumer_terminal_persistence_implementation_binding:",
        ):
            raise ValueError("v26.212 implementation identity differs")
        return self


class AuthorizationConsumptionReceiptContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    exact_v211_authorization_id: str = Field(min_length=1)
    exact_authorization_bytes_required: Literal[True] = True
    durable_no_replace_required: Literal[True] = True
    file_and_directory_fsync_required: Literal[True] = True
    second_consumption_rejects_before_factories: Literal[True] = True
    preflight_lease_does_not_consume_online_authorization: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> AuthorizationConsumptionReceiptContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_repaired_authorization_consumption_receipt_contract:",
        ):
            raise ValueError("v26.212 consumption Contract identity differs")
        return self


class RunStartReceiptContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    consumption_contract_id: str = Field(min_length=1)
    durable_no_replace_required: Literal[True] = True
    consumption_receipt_parent_required: Literal[True] = True
    credential_boundary_after_receipt_only: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> RunStartReceiptContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_repaired_run_start_receipt_contract:",
        ):
            raise ValueError("v26.212 Run Start Contract identity differs")
        return self


class ProviderTransportImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    exact_v209_runner_id: str = Field(min_length=1)
    transport_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    injected_transport_protocol_compatible: Literal[True] = True
    credential_bound_factory_required: Literal[True] = True
    preflight_zero_provider_mode: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ProviderTransportImplementationBinding:
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_repaired_provider_transport_implementation_binding:",
        ):
            raise ValueError("v26.212 Provider transport binding differs")
        return self


class TerminalRegistryDispatcherBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    source_v195_terminal_registry_id: str = Field(min_length=1)
    exact_v209_runner_id: str = Field(min_length=1)
    terminal_kinds: tuple[str, ...] = Field(min_length=16, max_length=16)
    terminal_policy_ids: tuple[str, ...] = Field(min_length=16, max_length=16)
    dispatcher_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reachable_terminal_count: Literal[16] = 16
    complete_reachable_registry: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> TerminalRegistryDispatcherBinding:
        if self.terminal_kinds != TERMINAL_KINDS or len(set(self.terminal_policy_ids)) != 16:
            raise ValueError("v26.212 reachable terminal Registry differs")
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_repaired_terminal_registry_dispatcher_binding:",
        ):
            raise ValueError("v26.212 terminal dispatcher binding differs")
        return self


class RawResultWriterBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    writer_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_before_result_required: Literal[True] = True
    canonical_json_required: Literal[True] = True
    durable_no_replace_required: Literal[True] = True
    actual_sha256_and_byte_count_required: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> RawResultWriterBinding:
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_repaired_raw_result_writer_binding:",
        ):
            raise ValueError("v26.212 Raw/Result writer binding differs")
        return self


class TraceOutcomeCheckpointBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    reconstructor_symbol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_result_actual_bytes_required: Literal[True] = True
    exact_parent_dag_required: Literal[True] = True
    checkpoint_last_required: Literal[True] = True
    durable_no_replace_required: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> TraceOutcomeCheckpointBinding:
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_repaired_trace_outcome_checkpoint_binding:",
        ):
            raise ValueError("v26.212 Trace/Outcome/checkpoint binding differs")
        return self


class OnlineExecutionConsumerImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    implementation_binding_id: str = Field(min_length=1)
    exact_v211_authorization_id: str = Field(min_length=1)
    exact_v209_implementation_id: str = Field(min_length=1)
    exact_v209_manifest_id: str = Field(min_length=1)
    exact_v209_runner_id: str = Field(min_length=1)
    exact_v209_execution_contract_id: str = Field(min_length=1)
    consumption_contract_id: str = Field(min_length=1)
    run_start_contract_id: str = Field(min_length=1)
    provider_transport_binding_id: str = Field(min_length=1)
    terminal_registry_dispatcher_binding_id: str = Field(min_length=1)
    raw_result_writer_binding_id: str = Field(min_length=1)
    trace_outcome_checkpoint_binding_id: str = Field(min_length=1)
    exact_192_job_runner_required: Literal[True] = True
    online_authorization_created: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> OnlineExecutionConsumerImplementationBinding:
        parents = (
            self.consumption_contract_id,
            self.run_start_contract_id,
            self.provider_transport_binding_id,
            self.terminal_registry_dispatcher_binding_id,
            self.raw_result_writer_binding_id,
            self.trace_outcome_checkpoint_binding_id,
        )
        if len(set(parents)) != 6:
            raise ValueError("v26.212 consumer implementation parent set differs")
        if self.binding_id != identity(
            self,
            "binding_id",
            "fresh_repaired_online_execution_consumer_implementation_binding:",
        ):
            raise ValueError("v26.212 consumer binding identity differs")
        return self


class RepairedCompositionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    v211_freeze_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    event_sequence: tuple[str, ...] = EXECUTION_SEQUENCE
    exact_v211_authorization_bytes_required: Literal[True] = True
    durable_consumption_and_receipt_executable: Literal[True] = True
    complete_terminal_to_persistence_executable: Literal[True] = True
    raw_before_result_required: Literal[True] = True
    one_current_state_prompt_at_a_time: Literal[True] = True
    current_v211_authorization_consumed: Literal[False] = False
    new_online_authorization_created: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> RepairedCompositionContract:
        if self.event_sequence != EXECUTION_SEQUENCE:
            raise ValueError("v26.212 composition sequence differs")
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_repaired_online_consumer_terminal_persistence_composition_contract:",
        ):
            raise ValueError("v26.212 composition identity differs")
        return self


class PreflightConsumptionReceipt(FrozenModel):
    receipt_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    authorization_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    consumption_scope: Literal["isolated_credential_free_preflight_lease"] = (
        "isolated_credential_free_preflight_lease"
    )
    durable_no_replace: Literal[True] = True
    file_fsync_completed: Literal[True] = True
    directory_fsync_completed: Literal[True] = True
    authoritative_online_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_receipt(self) -> PreflightConsumptionReceipt:
        if self.receipt_id != identity(
            self,
            "receipt_id",
            "fresh_repaired_preflight_authorization_consumption_receipt:",
        ):
            raise ValueError("v26.212 consumption Receipt identity differs")
        return self


class PreflightRunStartReceipt(FrozenModel):
    receipt_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    consumption_receipt_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    exact_job_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_mode: Literal["credential_free_scripted_preflight"] = (
        "credential_free_scripted_preflight"
    )
    durable_no_replace: Literal[True] = True
    file_fsync_completed: Literal[True] = True
    directory_fsync_completed: Literal[True] = True
    provider_execution_started: Literal[False] = False
    credential_lookups: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_receipt(self) -> PreflightRunStartReceipt:
        if self.receipt_id != identity(
            self,
            "receipt_id",
            "fresh_repaired_preflight_run_start_receipt:",
        ):
            raise ValueError("v26.212 Run Start Receipt identity differs")
        return self


class IngressOrderControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    admitted: bool
    rejected: bool
    rejection_reason_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    consumption_write_count: int = Field(ge=0, le=1)
    run_start_receipt_write_count: int = Field(ge=0, le=1)
    credential_boundary_probe_count: int = Field(ge=0, le=1)
    transport_factory_count: int = Field(ge=0, le=1)
    writer_factory_count: int = Field(ge=0, le=1)
    credential_lookups: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> IngressOrderControl:
        if self.admitted == self.rejected:
            raise ValueError("v26.212 ingress disposition differs")
        if self.admitted:
            if self.rejection_reason_sha256 is not None or (
                self.consumption_write_count,
                self.run_start_receipt_write_count,
                self.credential_boundary_probe_count,
                self.transport_factory_count,
                self.writer_factory_count,
            ) != (1, 1, 1, 1, 1):
                raise ValueError("v26.212 legal ingress order differs")
        elif self.rejection_reason_sha256 is None:
            raise ValueError("v26.212 rejected ingress lacks reason")
        if self.control_id != identity(
            self,
            "control_id",
            "finance_v26_212_ingress_order_control:",
        ):
            raise ValueError("v26.212 ingress control identity differs")
        return self


class IngressOrderAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    controls: tuple[IngressOrderControl, ...] = Field(min_length=4, max_length=4)
    exact_control_count: Literal[4] = 4
    legal_control_count: Literal[1] = 1
    rejected_attack_count: Literal[3] = 3
    second_consumption_rejected_before_factories: Literal[True] = True
    factory_before_consumption_rejected: Literal[True] = True
    factory_before_run_start_receipt_rejected: Literal[True] = True
    current_v211_authorization_consumed: Literal[False] = False
    credential_lookups: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> IngressOrderAudit:
        if (
            sum(item.admitted for item in self.controls) != 1
            or sum(item.rejected for item in self.controls) != 3
            or len({item.control_name for item in self.controls}) != 4
        ):
            raise ValueError("v26.212 ingress control denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_212_ingress_order_audit:",
        ):
            raise ValueError("v26.212 ingress Audit identity differs")
        return self


class ScriptedEvidenceRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    v209_control_row_id: str = Field(min_length=1)
    invocation_ids: tuple[str, ...] = Field(min_length=2, max_length=10)
    terminal_kind: Literal["completed_qualified"] = "completed_qualified"
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
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    trace_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    persistence_sequence: tuple[str, ...]
    formal_empirical_row: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_record(self) -> ScriptedEvidenceRecord:
        if self.persistence_sequence != ("raw", "result", "trace", "outcome", "checkpoint"):
            raise ValueError("v26.212 evidence persistence order differs")
        if (
            len(
                set(
                    (
                        self.raw_id,
                        self.result_id,
                        self.trace_id,
                        self.outcome_id,
                        self.checkpoint_id,
                    )
                )
            )
            != 5
        ):
            raise ValueError("v26.212 evidence layer identity aliases")
        if self.record_id != identity(
            self,
            "record_id",
            "finance_v26_212_scripted_evidence_record:",
        ):
            raise ValueError("v26.212 evidence record identity differs")
        return self


class ScriptedPersistenceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    run_start_receipt_id: str = Field(min_length=1)
    v209_invocation_census_id: str = Field(min_length=1)
    v209_execution_control_audit_id: str = Field(min_length=1)
    records: tuple[ScriptedEvidenceRecord, ...] = Field(min_length=192, max_length=192)
    exact_job_count: Literal[192] = 192
    v209_invocation_count: Literal[792] = 792
    transport_dispatch_count: Literal[792] = 792
    raw_count: Literal[192] = 192
    result_count: Literal[192] = 192
    trace_count: Literal[192] = 192
    outcome_count: Literal[192] = 192
    checkpoint_count: Literal[192] = 192
    raw_before_result_count: Literal[192] = 192
    actual_byte_match_count: Literal[960] = 960
    exception_escape_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ScriptedPersistenceAudit:
        if len({item.job_id for item in self.records}) != 192:
            raise ValueError("v26.212 scripted Job set differs")
        layer_ids = {
            value
            for item in self.records
            for value in (
                item.raw_id,
                item.result_id,
                item.trace_id,
                item.outcome_id,
                item.checkpoint_id,
            )
        }
        if len(layer_ids) != 960:
            raise ValueError("v26.212 evidence identity set differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_212_scripted_persistence_audit:",
        ):
            raise ValueError("v26.212 persistence Audit identity differs")
        return self


class TerminalPersistenceControl(FrozenModel):
    control_id: str = Field(min_length=1)
    terminal_kind: str = Field(min_length=1)
    terminal_policy_id: str = Field(min_length=1)
    terminal_signal_id: str = Field(min_length=1)
    terminal_decision_id: str = Field(min_length=1)
    raw_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    outcome_id: str = Field(min_length=1)
    checkpoint_id: str = Field(min_length=1)
    source_bound: Literal[True] = True
    exact_persistence_order: Literal[True] = True
    formal_empirical_row: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> TerminalPersistenceControl:
        if self.terminal_kind not in TERMINAL_KINDS:
            raise ValueError("v26.212 terminal control kind differs")
        if (
            len(
                set(
                    (
                        self.raw_id,
                        self.result_id,
                        self.trace_id,
                        self.outcome_id,
                        self.checkpoint_id,
                    )
                )
            )
            != 5
        ):
            raise ValueError("v26.212 terminal persistence identity aliases")
        if self.control_id != identity(
            self,
            "control_id",
            "finance_v26_212_terminal_persistence_control:",
        ):
            raise ValueError("v26.212 terminal control identity differs")
        return self


class TerminalPersistenceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    terminal_registry_dispatcher_binding_id: str = Field(min_length=1)
    trace_outcome_checkpoint_binding_id: str = Field(min_length=1)
    controls: tuple[TerminalPersistenceControl, ...] = Field(min_length=16, max_length=16)
    reachable_terminal_count: Literal[16] = 16
    executed_control_count: Literal[16] = 16
    terminal_projection_count: Literal[16] = 16
    raw_result_trace_outcome_checkpoint_count: Literal[80] = 80
    exception_escape_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> TerminalPersistenceAudit:
        if tuple(item.terminal_kind for item in self.controls) != TERMINAL_KINDS:
            raise ValueError("v26.212 terminal control coverage differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_212_terminal_persistence_audit:",
        ):
            raise ValueError("v26.212 terminal persistence Audit identity differs")
        return self


class SourceMutationControl(FrozenModel):
    control_id: str = Field(min_length=1)
    attack_name: str = Field(min_length=1)
    mutated_parent_id: str = Field(min_length=1)
    fully_rehashed: Literal[True] = True
    rejected_before_consumption: Literal[True] = True
    credential_boundary_probe_count: Literal[0] = 0
    factory_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> SourceMutationControl:
        if self.control_id != identity(
            self,
            "control_id",
            "finance_v26_212_source_mutation_control:",
        ):
            raise ValueError("v26.212 source mutation identity differs")
        return self


class SourceMutationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    controls: tuple[SourceMutationControl, ...] = Field(min_length=7, max_length=7)
    attack_count: Literal[7] = 7
    rejected_count: Literal[7] = 7
    accepted_count: Literal[0] = 0
    post_guard_probe_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> SourceMutationAudit:
        if len({item.attack_name for item in self.controls}) != 7:
            raise ValueError("v26.212 source mutation denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_212_source_mutation_audit:",
        ):
            raise ValueError("v26.212 source mutation Audit identity differs")
        return self


class ScopeBoundaryAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v211_freeze_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    current_v211_authorization_consumed: Literal[False] = False
    isolated_preflight_lease_count: Literal[1] = 1
    preflight_run_start_receipt_count: Literal[1] = 1
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    provider_client_constructions: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    new_online_authorizations: Literal[0] = 0
    qa_reads: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ScopeBoundaryAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_212_scope_boundary_audit:",
        ):
            raise ValueError("v26.212 scope boundary identity differs")
        return self


class GateResult(FrozenModel):
    gate_id: str = Field(min_length=1)
    gate_name: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    passed: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> GateResult:
        if self.gate_id != identity(
            self,
            "gate_id",
            "finance_v26_212_consumer_terminal_persistence_gate:",
        ):
            raise ValueError("v26.212 Gate identity differs")
        return self


class GateEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    gates: tuple[GateResult, ...] = Field(min_length=7, max_length=7)
    passed_count: Literal[7] = 7
    failed_count: Literal[0] = 0
    all_gates_passed: Literal[True] = True
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evaluation(self) -> GateEvaluation:
        if len({item.gate_name for item in self.gates}) != 7:
            raise ValueError("v26.212 Gate denominator differs")
        if self.evaluation_id != identity(
            self,
            "evaluation_id",
            "finance_v26_212_consumer_terminal_persistence_gate_evaluation:",
        ):
            raise ValueError("v26.212 Gate Evaluation identity differs")
        return self


class RepairDecision(FrozenModel):
    decision_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v211_freeze_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    ingress_order_audit_id: str = Field(min_length=1)
    scripted_persistence_audit_id: str = Field(min_length=1)
    terminal_persistence_audit_id: str = Field(min_length=1)
    source_mutation_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_exact_online_consumer_terminal_persistence_preflight_passed_independent_audit_required_online_execution_blocked"
    ] = DECISION
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> RepairDecision:
        if self.decision_id != identity(
            self,
            "decision_id",
            "finance_v26_212_repair_decision:",
        ):
            raise ValueError("v26.212 Decision identity differs")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    status: Literal["PASSED_PREFLIGHT_ONLINE_EXECUTION_BLOCKED"] = (
        "PASSED_PREFLIGHT_ONLINE_EXECUTION_BLOCKED"
    )
    next_stage: Literal[
        "fresh_repaired_full_condition_exact_online_execution_consumer_and_terminal_persistence_integration_preflight_independent_audit_only"
    ] = NEXT_STAGE
    new_online_authorization_required_after_independent_audit: Literal[True] = True
    provider_execution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_212_transition:",
        ):
            raise ValueError("v26.212 Transition identity differs")
        return self


class SourceIdentity(FrozenModel):
    source_identity_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    implementation_files: tuple[str, ...] = Field(min_length=4)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_source(self) -> SourceIdentity:
        if self.implementation_files != tuple(sorted(set(self.implementation_files))):
            raise ValueError("v26.212 implementation file set differs")
        if self.source_identity_id != identity(
            self,
            "source_identity_id",
            "finance_v26_212_source_identity:",
        ):
            raise ValueError("v26.212 source identity differs")
        return self


class RepairReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    external_authorization_id: str = Field(min_length=1)
    v211_freeze_id: str = Field(min_length=1)
    consumer_binding_id: str = Field(min_length=1)
    composition_contract_id: str = Field(min_length=1)
    ingress_order_audit_id: str = Field(min_length=1)
    scripted_persistence_audit_id: str = Field(min_length=1)
    terminal_persistence_audit_id: str = Field(min_length=1)
    source_mutation_audit_id: str = Field(min_length=1)
    scope_boundary_audit_id: str = Field(min_length=1)
    gate_evaluation_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_exact_online_consumer_terminal_persistence_preflight_passed_independent_audit_required_online_execution_blocked"
    ] = DECISION
    scripted_job_count: Literal[192] = 192
    scripted_invocation_count: Literal[792] = 792
    terminal_control_count: Literal[16] = 16
    current_v211_authorization_consumed: Literal[False] = False
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> RepairReport:
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_212_consumer_terminal_persistence_report:",
        ):
            raise ValueError("v26.212 report identity differs")
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
            raise ValueError("v26.212 Artifact Manifest geometry differs")
        expected = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_212_artifact_root:",
        )
        if self.artifact_root != expected:
            raise ValueError("v26.212 Artifact Root differs")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            "finance_v26_212_artifact_manifest:",
        ):
            raise ValueError("v26.212 Artifact Manifest identity differs")
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
        prefix="finance_v26_212_artifact_root:",
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
            prefix="finance_v26_212_artifact_manifest:",
        ),
    )
