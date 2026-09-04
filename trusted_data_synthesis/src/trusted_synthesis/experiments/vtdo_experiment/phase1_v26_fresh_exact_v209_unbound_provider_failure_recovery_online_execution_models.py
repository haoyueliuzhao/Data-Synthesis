# mypy: disable-error-code="valid-type"
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Final, Literal, TypeVar

from typing_extensions import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_models as v224_models,
)
from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_exact_v209_unbound_provider_failure_recovery_online_execution.v1"
RUN_ID: Final = (
    "finance_v26_233_fresh_exact_v209_unbound_provider_failure_recovery_population_"
    "bound_online_execution_v1_20260904"
)
CONSUMED_STAGE: Final = (
    "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_only"
)
NEXT_STAGE: Final = (
    "fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_"
    "postrun_independent_audit_only"
)
AUTHORIZATION_ID: Final = (
    "fresh_v26_232_exact_manifest_byte_bound_recovery_online_execution_authorization:"
    "c332e42c45bbd718a16ba65258099c9193cb84348b83f94960d3bf4bd015e371"
)
AUTHORIZATION_SHA256: Final = "576f0ca2799e447158419e4ef7a59822e76b08c2203ac5d67d9b4a4038a1737f"
AUTHORIZATION_BYTE_COUNT: Final = 5_883
RECOVERY_JOB_SET_SHA256: Final = "e1a0ad2cddbb48e857cef232b11396161aa64636f44fd91bcd15915de37fb50d"
EXTERNAL_REVIEW_SHA256: Final = "dc214719a86aaaac4526de1b247ac86438d73ae5db683514841c00eb329aec08"
EXTERNAL_REVIEW_BYTE_COUNT: Final = 12_052
OPERATOR_DIRECTIVE: Final = "参照审计继续实验修订"
OPERATOR_DIRECTIVE_SHA256: Final = (
    "d7f0a7b9c625edb3ec4d53a21418dd0b11ec7291a0ae934b98364ea651f9d3ca"
)
OPERATOR_DIRECTIVE_BYTE_COUNT: Final = 30

ModelT = TypeVar("ModelT", bound=BaseModel)
RecoveryStatus = Literal["terminal", "failure"]
RecoveryFailureKind = Literal["unbound_provider_failure", "host_failure"]
LayerKind = Literal["raw", "result", "trace", "outcome", "checkpoint"]
SubsequentEvidenceKind = Literal[
    "subsequent_action_parser_rejection", "subsequent_action_reference_failure"
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False), prefix=prefix
    )


def make_identity(
    model_type: type[ModelT], values: Mapping[str, Any], *, field: str, prefix: str
) -> ModelT:
    payload = dict(values)
    provisional = model_type.model_construct(**{field: "pending"}, **payload)
    payload[field] = identity(provisional, field, prefix)
    return model_type.model_validate(payload)


class Identified(FrozenModel):
    @classmethod
    def prefix(cls) -> str:
        raise NotImplementedError

    def check_id(self, field: str) -> None:
        if getattr(self, field) != identity(self, field, self.prefix()):
            raise ValueError(f"{type(self).__name__} identity differs")


class ExternalExecutionDecision(Identified):
    decision_id: str
    review_sha256: Literal[EXTERNAL_REVIEW_SHA256] = EXTERNAL_REVIEW_SHA256
    review_byte_count: Literal[12052] = EXTERNAL_REVIEW_BYTE_COUNT
    audit_decision: Literal["PASS_AS_SCOPED"] = "PASS_AS_SCOPED"
    blocking_defect: Literal["NONE_FOUND"] = "NONE_FOUND"
    mandatory_revision: Literal["NONE"] = "NONE"
    v26_232_authorization_state: Literal["ACCEPTED_UNCONSUMED"] = "ACCEPTED_UNCONSUMED"
    recovery_population_authority: Literal["RETAINED"] = "RETAINED"
    next_unclosed_gate: Literal["RECOVERY_ONLINE_EXECUTION"] = "RECOVERY_ONLINE_EXECUTION"
    operator_directive: Literal[OPERATOR_DIRECTIVE] = OPERATOR_DIRECTIVE
    operator_directive_sha256: Literal[OPERATOR_DIRECTIVE_SHA256] = OPERATOR_DIRECTIVE_SHA256
    operator_directive_byte_count: Literal[30] = OPERATOR_DIRECTIVE_BYTE_COUNT
    authorized_stage: Literal[CONSUMED_STAGE] = CONSUMED_STAGE
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_233_external_execution_decision:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        directive = self.operator_directive.encode("utf-8")
        if (
            len(directive) != self.operator_directive_byte_count
            or hashlib.sha256(directive).hexdigest() != self.operator_directive_sha256
        ):
            raise ValueError("operator directive bytes differ")
        self.check_id("decision_id")
        return self


class SourceMember(FrozenModel):
    relative_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class ExecutionSourceIdentity(Identified):
    source_id: str
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    members: tuple[SourceMember, ...] = Field(min_length=2, max_length=2)
    member_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tracked_tree_clean: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_233_execution_source_identity:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        paths = tuple(item.relative_path for item in self.members)
        if (
            paths != tuple(sorted(set(paths)))
            or canonical_sha256(tuple(item.model_dump(mode="json") for item in self.members))
            != self.member_set_sha256
        ):
            raise ValueError("execution source member set differs")
        self.check_id("source_id")
        return self


class ExecutionPreparation(Identified):
    preparation_id: str
    external_decision_id: str
    authorization_id: Literal[AUTHORIZATION_ID] = AUTHORIZATION_ID
    authorization_sha256: Literal[AUTHORIZATION_SHA256] = AUTHORIZATION_SHA256
    authorization_byte_count: Literal[5883] = AUTHORIZATION_BYTE_COUNT
    v26_232_manifest_id: str
    v26_232_artifact_root: str
    v26_229_manifest_id: str
    v26_229_artifact_root: str
    v26_229_source_authority_audit_id: str
    v26_229_request_replay_audit_id: str
    recovery_population_id: str
    recovery_job_ids: tuple[str, ...] = Field(min_length=33, max_length=33)
    recovery_job_set_sha256: Literal[RECOVERY_JOB_SET_SHA256] = RECOVERY_JOB_SET_SHA256
    successful_prefix_projection_count: Literal[55] = 55
    failed_request_count: Literal[33] = 33
    request_max_tokens: Literal[16384] = 16_384
    authorization_consumed: Literal[False] = False
    credential_lookups: Literal[0] = 0
    provider_calls: Literal[0] = 0
    output_writes: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_233_execution_preparation:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if (
            self.recovery_job_ids != tuple(sorted(set(self.recovery_job_ids)))
            or canonical_sha256(self.recovery_job_ids) != self.recovery_job_set_sha256
        ):
            raise ValueError("Recovery Job set differs")
        self.check_id("preparation_id")
        return self


class AuthorizationConsumptionReceipt(Identified):
    receipt_id: str
    preparation_id: str
    authorization_id: Literal[AUTHORIZATION_ID] = AUTHORIZATION_ID
    authorization_sha256: Literal[AUTHORIZATION_SHA256] = AUTHORIZATION_SHA256
    authorization_byte_count: Literal[5883] = AUTHORIZATION_BYTE_COUNT
    consumed_stage: Literal[CONSUMED_STAGE] = CONSUMED_STAGE
    consumed_at_utc: str
    prior_consumption_count: Literal[0] = 0
    consumption_ordinal: Literal[1] = 1
    resulting_consumption_count: Literal[1] = 1
    durable_before_credentials: Literal[True] = True
    authorization_reusable: Literal[False] = False
    credential_lookups: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_233_authorization_consumption_receipt:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("receipt_id")
        return self


class RecoveryRunStartReceipt(Identified):
    receipt_id: str
    consumption_receipt_id: str
    preparation_id: str
    authorization_id: Literal[AUTHORIZATION_ID] = AUTHORIZATION_ID
    recovery_job_set_sha256: Literal[RECOVERY_JOB_SET_SHA256] = RECOVERY_JOB_SET_SHA256
    execution_source_id: str
    execution_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    execution_source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    started_at_utc: str
    exact_job_count: Literal[33] = 33
    successful_prefix_projection_count: Literal[55] = 55
    durable_before_credentials: Literal[True] = True
    credential_lookups_at_receipt: Literal[0] = 0
    provider_calls_at_receipt: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_233_recovery_run_start_receipt:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        self.check_id("receipt_id")
        return self


class SubsequentActionEvidence(Identified):
    evidence_id: str
    evidence_kind: SubsequentEvidenceKind
    run_start_receipt_id: str
    recovery_job_id: str
    recovery_candidate_id: str
    historical_job_id: str
    job_ordinal: int = Field(ge=0, le=191)
    phase: Literal["subsequent_action"] = "subsequent_action"
    invocation_records: tuple[dict[str, Any], ...] = Field(min_length=2, max_length=23)
    public_payload: dict[str, Any]
    public_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_state_id: str
    current_candidate_action_ids: tuple[str, ...] = Field(min_length=1)
    terminal_derived_from_record: Literal[True] = True
    caller_terminal_input: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_233_subsequent_action_evidence:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        records = self.invocation_records
        last = records[-1]
        expected_terminal = (
            "first_response_abi_invalid"
            if self.evidence_kind == "subsequent_action_parser_rejection"
            else "first_action_reference_invalid"
        )
        parser_shape = (
            last.get("exact_response_parsed") is False
            if self.evidence_kind == "subsequent_action_parser_rejection"
            else last.get("exact_response_parsed") is True
        )
        if (
            tuple(item.get("invocation_index") for item in records) != tuple(range(len(records)))
            or any(item.get("job_id") != self.historical_job_id for item in records)
            or any(item.get("typed_terminal") is not None for item in records[:-1])
            or last.get("phase") != self.phase
            or last.get("typed_terminal") != expected_terminal
            or not parser_shape
            or last.get("current_state_and_candidate_or_final_envelope_valid") is not False
            or last.get("runtime_step_or_finalize_completed") is not False
            or last.get("current_state_id") != self.current_state_id
            or tuple(last.get("candidate_action_ids", ())) != self.current_candidate_action_ids
            or last.get("public_response_sha256") != self.public_payload_sha256
            or canonical_sha256(self.public_payload) != self.public_payload_sha256
        ):
            raise ValueError("subsequent-Action Recovery Evidence differs")
        self.check_id("evidence_id")
        return self


class SubsequentActionDecision(Identified):
    decision_id: str
    evidence: SubsequentActionEvidence
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_kind: Literal["first_response_abi_invalid", "first_action_reference_invalid"]
    terminal_policy_id: str
    derivation_rule: Literal[
        "subsequent_action_exact_parser_rejection",
        "subsequent_action_parsed_reference_not_current",
    ]
    caller_terminal_input: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_233_subsequent_action_decision:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        parser = self.evidence.evidence_kind == "subsequent_action_parser_rejection"
        expected = (
            "first_response_abi_invalid" if parser else "first_action_reference_invalid",
            "fresh_kernel_terminal_policy:"
            + (
                "b5fb980fc0c80b2c72a964d538cf487e9a27403aff0ebe4e88ffb3b29847c04f"
                if parser
                else "443b4c076ea4d694590fbafcd66d1c23681679bd24368ad43a354299c480fe3b"
            ),
            (
                "subsequent_action_exact_parser_rejection"
                if parser
                else "subsequent_action_parsed_reference_not_current"
            ),
        )
        if (
            self.terminal_kind,
            self.terminal_policy_id,
            self.derivation_rule,
        ) != expected or self.evidence_sha256 != canonical_sha256(self.evidence):
            raise ValueError("subsequent-Action Recovery Decision differs")
        self.check_id("decision_id")
        return self


class RecoveryLayerDescriptor(Identified):
    descriptor_id: str
    run_start_receipt_id: str
    recovery_job_id: str
    historical_job_id: str
    job_ordinal: int = Field(ge=0, le=191)
    layer_kind: LayerKind
    namespace_id: str
    relative_path: str
    terminal_kind: v224_models.TerminalKind
    terminal_source: v224_models.TerminalSource
    parent_descriptor_ids: tuple[str, ...] = Field(max_length=2)
    provider_call_descriptor_ids: tuple[str, ...] = Field(max_length=23)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload_byte_count: int = Field(gt=0)
    persisted_sequence: int = Field(ge=0, le=4)
    recovery_execution: Literal[True] = True
    historical_v26_226_mutation: Literal[False] = False
    downstream_empirical_admission: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_233_recovery_layer_descriptor:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        expected = ("raw", "result", "trace", "outcome", "checkpoint")[self.persisted_sequence]
        if (
            self.layer_kind != expected
            or self.relative_path.startswith("/")
            or ".." in self.relative_path.split("/")
        ):
            raise ValueError("Recovery layer relation differs")
        self.check_id("descriptor_id")
        return self


class RecoveryJobRecord(Identified):
    record_id: str
    run_start_receipt_id: str
    authorization_id: Literal[AUTHORIZATION_ID] = AUTHORIZATION_ID
    recovery_job_id: str
    recovery_candidate_id: str
    historical_job_id: str
    job_ordinal: int = Field(ge=0, le=191)
    failed_request_phase: Literal["first_action", "subsequent_action", "final"]
    successful_prefix_projection_count: int = Field(ge=0, le=22)
    successful_prefix_provider_reissue_count: Literal[0] = 0
    exact_failed_request_reissue_count: Literal[1] = 1
    invocation_record_count: int = Field(ge=1, le=23)
    provider_calls: tuple[v224_models.ProviderCallDescriptor, ...] = Field(
        min_length=1, max_length=23
    )
    terminal_kind: v224_models.TerminalKind
    terminal_source: v224_models.TerminalSource
    layers: tuple[
        RecoveryLayerDescriptor,
        RecoveryLayerDescriptor,
        RecoveryLayerDescriptor,
        RecoveryLayerDescriptor,
        RecoveryLayerDescriptor,
    ]
    status: Literal["terminal"] = "terminal"
    historical_job_reclassified: Literal[False] = False
    empirical_estimate_admitted: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_233_recovery_job_record:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        calls = self.provider_calls
        if (
            tuple(item.call_ordinal for item in calls) != tuple(range(len(calls)))
            or any(item.job_id != self.recovery_job_id for item in calls)
            or self.invocation_record_count != self.successful_prefix_projection_count + len(calls)
            or tuple(item.persisted_sequence for item in self.layers) != tuple(range(5))
            or any(item.recovery_job_id != self.recovery_job_id for item in self.layers)
        ):
            raise ValueError("Recovery terminal record geometry differs")
        self.check_id("record_id")
        return self


class RecoveryFailureRecord(Identified):
    record_id: str
    run_start_receipt_id: str
    authorization_id: Literal[AUTHORIZATION_ID] = AUTHORIZATION_ID
    recovery_job_id: str
    recovery_candidate_id: str
    historical_job_id: str
    job_ordinal: int = Field(ge=0, le=191)
    failed_request_phase: Literal["first_action", "subsequent_action", "final"]
    successful_prefix_projection_count: int = Field(ge=0, le=22)
    successful_prefix_provider_reissue_count: Literal[0] = 0
    exact_failed_request_reissue_count: Literal[1] = 1
    provider_calls: tuple[v224_models.ProviderCallDescriptor, ...] = Field(
        min_length=1, max_length=23
    )
    failure_kind: RecoveryFailureKind
    error_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_evidence_admitted: Literal[False] = False
    five_layer_evidence_admitted: Literal[False] = False
    status: Literal["failure"] = "failure"
    historical_job_reclassified: Literal[False] = False
    empirical_estimate_admitted: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_233_recovery_failure_record:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        if tuple(item.call_ordinal for item in self.provider_calls) != tuple(
            range(len(self.provider_calls))
        ) or any(item.job_id != self.recovery_job_id for item in self.provider_calls):
            raise ValueError("Recovery failure record geometry differs")
        self.check_id("record_id")
        return self


class ExecutionSummary(Identified):
    summary_id: str
    preparation_id: str
    consumption_receipt_id: str
    run_start_receipt_id: str
    authorization_id: Literal[AUTHORIZATION_ID] = AUTHORIZATION_ID
    execution_status: Literal["completed", "incomplete"]
    records: tuple[RecoveryJobRecord, ...] = Field(max_length=33)
    failures: tuple[RecoveryFailureRecord, ...] = Field(max_length=33)
    exact_job_count: Literal[33] = 33
    attempted_job_count: Literal[33] = 33
    terminal_record_count: int = Field(ge=0, le=33)
    failure_record_count: int = Field(ge=0, le=33)
    successful_prefix_projection_count: Literal[55] = 55
    successful_prefix_provider_reissue_count: Literal[0] = 0
    exact_failed_request_reissue_count: Literal[33] = 33
    provider_call_count: int = Field(ge=33, le=704)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    terminal_partition: dict[str, int]
    failure_partition: dict[str, int]
    failed_request_phase_partition: dict[str, int]
    five_layer_file_count: int = Field(ge=0, le=165)
    historical_v26_226_mutation_count: Literal[0] = 0
    historical_terminal_backfill_count: Literal[0] = 0
    empirical_estimate_count: Literal[0] = 0
    authorization_consumption_count: Literal[1] = 1
    run_start_receipt_count: Literal[1] = 1
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_233_execution_summary:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        items = (*self.records, *self.failures)
        calls = tuple(call for item in items for call in item.provider_calls)
        ordinals = tuple(sorted(item.job_ordinal for item in items))
        terminals = {kind: 0 for kind in v224_models.TERMINAL_KINDS}
        for item in self.records:
            terminals[item.terminal_kind] += 1
        failures = {"unbound_provider_failure": 0, "host_failure": 0}
        for item in self.failures:
            failures[item.failure_kind] += 1
        phases = {"first_action": 0, "subsequent_action": 0, "final": 0}
        for item in items:
            phases[item.failed_request_phase] += 1
        if (
            ordinals != tuple(sorted({item.job_ordinal for item in items}))
            or len(items) != 33
            or self.terminal_record_count != len(self.records)
            or self.failure_record_count != len(self.failures)
            or self.provider_call_count != len(calls)
            or self.input_tokens != sum(call.input_tokens for call in calls)
            or self.output_tokens != sum(call.output_tokens for call in calls)
            or self.five_layer_file_count != len(self.records) * 5
            or self.terminal_partition != terminals
            or self.failure_partition != failures
            or self.failed_request_phase_partition != phases
            or phases != {"first_action": 3, "subsequent_action": 25, "final": 5}
            or (self.execution_status == "completed") != (not self.failures)
        ):
            raise ValueError("Recovery execution Summary differs")
        self.check_id("summary_id")
        return self


class Transition(Identified):
    transition_id: str
    summary_id: str
    authorization_id: Literal[AUTHORIZATION_ID] = AUTHORIZATION_ID
    execution_status: Literal["completed", "incomplete"]
    status: Literal[
        "COMPLETED_AWAITING_POSTRUN_INDEPENDENT_AUDIT",
        "INCOMPLETE_AWAITING_POSTRUN_INDEPENDENT_AUDIT",
    ]
    next_stage: Literal[NEXT_STAGE] = NEXT_STAGE
    next_stage_authorized: Literal[False] = False
    authorization_consumed_exactly_once: Literal[True] = True
    further_provider_calls_forbidden: Literal[True] = True
    failed_job_retry_forbidden: Literal[True] = True
    historical_mutation_or_backfill_forbidden: Literal[True] = True
    empirical_estimation_forbidden: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def prefix(cls) -> str:
        return "finance_v26_233_transition:"

    @model_validator(mode="after")
    def validate_all(self) -> Self:
        expected = (
            "COMPLETED_AWAITING_POSTRUN_INDEPENDENT_AUDIT"
            if self.execution_status == "completed"
            else "INCOMPLETE_AWAITING_POSTRUN_INDEPENDENT_AUDIT"
        )
        if self.status != expected:
            raise ValueError("Recovery transition status differs")
        self.check_id("transition_id")
        return self
