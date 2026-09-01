from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Any, Final, Literal, cast, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_authoritative_execution_kernel_models as kernel_models,
)
from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_artifact_backed_outcome_authority.v1"
EXPECTED_JOB_COUNT: Final = 192

EvidenceKind = Literal["scripted_preflight_control", "empirical_execution"]
TerminalRegistrationStatus = Literal[
    "reachable",
    "not_applicable_under_v26_194_execution_kernel",
]
TerminalKind = Literal[
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
    "policy_horizon_exhausted",
    "measurement_support_exit",
]
FailureStage = Literal[
    "provider",
    "transport",
    "privacy",
    "resource",
    "instrument",
    "model_identity",
    "thinking",
    "usage",
    "action_abi",
    "action_reference",
    "state_precondition",
    "operation_support",
    "final_abi",
    "base_answer",
    "base_citation",
    "mechanism",
    "policy",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


def make_identity_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: identity(provisional, field, prefix)}, **values)


def canonical_model_bytes(value: BaseModel) -> bytes:
    return json.dumps(
        value.model_dump(mode="json", warnings=False),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class FreshTerminalPolicy(FrozenModel):
    policy_id: str = Field(min_length=1)
    terminal_kind: TerminalKind
    registration_status: TerminalRegistrationStatus
    final_validity_rule: Literal[
        "qualified_conjunction_true",
        "factorized_conjunction_false",
        "nonverifier_null",
    ]
    exact_execution_contract_id: str = Field(min_length=1)
    exact_runner_id: str = Field(min_length=1)
    mechanism_design_reused: Literal[True] = True
    predecessor_policy_identity_reused: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_policy(self) -> FreshTerminalPolicy:
        expected_rule = "nonverifier_null"
        if self.terminal_kind == "completed_qualified":
            expected_rule = "qualified_conjunction_true"
        elif self.terminal_kind == "completed_invalid":
            expected_rule = "factorized_conjunction_false"
        if self.final_validity_rule != expected_rule:
            raise ValueError("fresh terminal policy validity rule differs")
        if self.policy_id != identity(
            self,
            "policy_id",
            "fresh_kernel_terminal_policy:",
        ):
            raise ValueError("fresh terminal policy identity differs")
        return self


class FreshTerminalRegistry(FrozenModel):
    registry_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    runtime_semantic_contract_id: str = Field(min_length=1)
    runtime_implementation_binding_id: str = Field(min_length=1)
    policies: tuple[FreshTerminalPolicy, ...] = Field(min_length=18, max_length=18)
    exact_terminal_kind_count: Literal[18] = 18
    predecessor_registry_identity_reuse_count: Literal[0] = 0
    online_outcome_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_registry(self) -> FreshTerminalRegistry:
        expected = set(get_args(TerminalKind))
        observed = {item.terminal_kind for item in self.policies}
        if observed != expected or len(self.policies) != len(expected):
            raise ValueError("fresh terminal registry is not total")
        expected_not_applicable = {
            "policy_horizon_exhausted",
            "measurement_support_exit",
        }
        observed_not_applicable = {
            item.terminal_kind
            for item in self.policies
            if item.registration_status == "not_applicable_under_v26_194_execution_kernel"
        }
        if observed_not_applicable != expected_not_applicable:
            raise ValueError("fresh terminal applicability partition differs")
        if any(
            (item.exact_execution_contract_id, item.exact_runner_id)
            != (self.execution_contract_id, self.runner_id)
            for item in self.policies
        ):
            raise ValueError("fresh terminal policy crosses execution parents")
        if self.registry_id != identity(
            self,
            "registry_id",
            "fresh_kernel_terminal_registry:",
        ):
            raise ValueError("fresh terminal registry identity differs")
        return self


class JobComponentSequence(FrozenModel):
    sequence_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    ordered_component_keys: tuple[str, ...] = Field(min_length=1, max_length=4)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_sequence(self) -> JobComponentSequence:
        if len(set(self.ordered_component_keys)) != len(self.ordered_component_keys):
            raise ValueError("fresh Job sequence repeats a Component")
        if self.sequence_id != identity(
            self,
            "sequence_id",
            "fresh_kernel_job_component_sequence:",
        ):
            raise ValueError("fresh Job sequence identity differs")
        return self


class FreshRawExecutionDescriptorContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    exact_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    canonical_json_required: Literal[True] = True
    actual_sha256_required: Literal[True] = True
    actual_byte_count_required: Literal[True] = True
    deterministic_job_owned_path_required: Literal[True] = True
    regular_file_required: Literal[True] = True
    symlink_forbidden: Literal[True] = True
    scripted_payload_has_model_response: Literal[False] = False
    scripted_payload_has_provider_artifacts: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FreshRawExecutionDescriptorContract:
        if self.exact_job_ids != tuple(sorted(set(self.exact_job_ids))):
            raise ValueError("fresh Raw Contract Job set differs")
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_raw_execution_descriptor_contract:",
        ):
            raise ValueError("fresh Raw Contract identity differs")
        return self


class FreshJobResultDescriptorContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    raw_descriptor_contract_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    exact_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    raw_parent_required: Literal[True] = True
    canonical_json_required: Literal[True] = True
    actual_sha256_required: Literal[True] = True
    actual_byte_count_required: Literal[True] = True
    independent_base_mechanism_factors_required: Literal[True] = True
    qualified_conjunction_required: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FreshJobResultDescriptorContract:
        if self.exact_job_ids != tuple(sorted(set(self.exact_job_ids))):
            raise ValueError("fresh Result Contract Job set differs")
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_job_result_descriptor_contract:",
        ):
            raise ValueError("fresh Result Contract identity differs")
        return self


class FreshJobBoundAttemptTraceContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    raw_descriptor_contract_id: str = Field(min_length=1)
    result_descriptor_contract_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    job_component_sequences: tuple[JobComponentSequence, ...] = Field(
        min_length=192,
        max_length=192,
    )
    trace_reconstructed_from_artifacts: Literal[True] = True
    failure_loci_reconstructed_from_artifacts: Literal[True] = True
    caller_supplied_failure_loci_authoritative: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FreshJobBoundAttemptTraceContract:
        job_ids = tuple(item.job_id for item in self.job_component_sequences)
        if job_ids != tuple(sorted(set(job_ids))):
            raise ValueError("fresh AttemptTrace Contract Job set differs")
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_job_bound_attempt_trace_contract:",
        ):
            raise ValueError("fresh AttemptTrace Contract identity differs")
        return self


class FreshOutcomeRowContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    raw_descriptor_contract_id: str = Field(min_length=1)
    result_descriptor_contract_id: str = Field(min_length=1)
    attempt_trace_contract_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    exact_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    constructor_only_from_reconstructed_evidence: Literal[True] = True
    completed_validity_definition: Literal[
        "independent_base_and_mechanism_with_qualified_conjunction"
    ] = "independent_base_and_mechanism_with_qualified_conjunction"
    scripted_rows_are_empirical: Literal[False] = False
    formal_empirical_rows_materialized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FreshOutcomeRowContract:
        if self.exact_job_ids != tuple(sorted(set(self.exact_job_ids))):
            raise ValueError("fresh Outcome-row Contract Job set differs")
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_outcome_row_contract:",
        ):
            raise ValueError("fresh Outcome-row Contract identity differs")
        return self


class FreshExactEvidenceSetEvaluatorContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    outcome_row_contract_id: str = Field(min_length=1)
    attempt_trace_contract_id: str = Field(min_length=1)
    result_descriptor_contract_id: str = Field(min_length=1)
    raw_descriptor_contract_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    exact_job_count: Literal[192] = 192
    exact_raw_result_file_count: Literal[384] = 384
    strict_parent_revalidation_required: Literal[True] = True
    exact_job_set_required: Literal[True] = True
    unique_layer_identity_required: Literal[True] = True
    actual_artifact_bytes_required: Literal[True] = True
    empirical_evaluation_authorized: Literal[False] = False
    empirical_estimate_materialized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FreshExactEvidenceSetEvaluatorContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_exact_evidence_set_evaluator_contract:",
        ):
            raise ValueError("fresh evaluator Contract identity differs")
        return self


class FreshComponentAttemptEvidence(FrozenModel):
    attempt_id: str = Field(min_length=1)
    component_index: int = Field(ge=0, le=3)
    component_key: str = Field(min_length=1)
    reached_state_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    response_source: Literal["scripted_reference_control"] = "scripted_reference_control"
    first_response_abi_valid: Literal[True] = True
    first_action_reference_valid: Literal[True] = True
    first_action_state_precondition_valid: Literal[True] = True
    first_action_accepted: Literal[True] = True
    correction_invoked: Literal[False] = False
    committed: Literal[True] = True
    terminal: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_attempt(self) -> FreshComponentAttemptEvidence:
        if self.attempt_id != identity(
            self,
            "attempt_id",
            "fresh_kernel_component_attempt:",
        ):
            raise ValueError("fresh Component attempt identity differs")
        return self


class FreshRawExecutionPayload(FrozenModel):
    payload_id: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    job_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    terminal_kind: TerminalKind
    component_attempts: tuple[FreshComponentAttemptEvidence, ...] = Field(
        min_length=1,
        max_length=4,
    )
    terminal_evidence_id: str = Field(min_length=1)
    provider_artifact_ids: tuple[str, ...] = ()
    transport_artifact_ids: tuple[str, ...] = ()
    model_response_present: Literal[False] = False
    token_usage: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_payload(self) -> FreshRawExecutionPayload:
        if self.evidence_kind == "scripted_preflight_control" and (
            self.provider_artifact_ids or self.transport_artifact_ids
        ):
            raise ValueError("scripted Raw payload carries Provider evidence")
        if tuple(item.component_index for item in self.component_attempts) != tuple(
            range(len(self.component_attempts))
        ):
            raise ValueError("fresh Raw attempts are not contiguous")
        if self.payload_id != identity(
            self,
            "payload_id",
            "fresh_kernel_raw_execution_payload:",
        ):
            raise ValueError("fresh Raw payload identity differs")
        return self


class FreshRawExecutionDescriptor(FrozenModel):
    raw_execution_id: str = Field(min_length=1)
    descriptor_contract_id: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    job_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    raw_namespace: str = Field(min_length=1)
    artifact_relative_path: str = Field(min_length=1)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_byte_count: int = Field(gt=0)
    payload_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_descriptor(self) -> FreshRawExecutionDescriptor:
        _validate_relative_path(self.artifact_relative_path)
        if self.raw_execution_id != identity(
            self,
            "raw_execution_id",
            "fresh_kernel_raw_execution_descriptor:",
        ):
            raise ValueError("fresh Raw descriptor identity differs")
        return self


class FreshTerminalValidity(FrozenModel):
    validity_id: str = Field(min_length=1)
    terminal_kind: TerminalKind
    task_completion: bool | None
    task_verifier_invoked: bool
    final_response_abi_valid: bool | None = None
    final_result_id: str | None = None
    final_base_valid: bool | None = None
    final_mechanism_qualified: bool | None = None
    final_qualified_valid: bool | None = None
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_validity(self) -> FreshTerminalValidity:
        factors = (
            self.final_result_id,
            self.final_base_valid,
            self.final_mechanism_qualified,
            self.final_qualified_valid,
        )
        if self.task_verifier_invoked:
            if (
                self.task_completion is not True
                or self.final_response_abi_valid is not True
                or any(item is None for item in factors)
            ):
                raise ValueError("fresh completed validity lacks exact factors")
            if self.final_qualified_valid != bool(
                self.final_base_valid and self.final_mechanism_qualified
            ):
                raise ValueError("fresh Qualified validity is not its conjunction")
        elif any(item is not None for item in factors):
            raise ValueError("fresh non-Verifier validity carries Final factors")
        if self.validity_id != identity(
            self,
            "validity_id",
            "fresh_kernel_terminal_validity:",
        ):
            raise ValueError("fresh terminal validity identity differs")
        return self


class FreshJobResultPayload(FrozenModel):
    payload_id: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    terminal_kind: TerminalKind
    validity: FreshTerminalValidity
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_payload(self) -> FreshJobResultPayload:
        if self.terminal_kind != self.validity.terminal_kind:
            raise ValueError("fresh Result terminal differs from validity")
        if self.terminal_kind == "completed_qualified" and (
            self.validity.final_qualified_valid is not True
        ):
            raise ValueError("fresh qualified Result lacks Qualified validity")
        if self.payload_id != identity(
            self,
            "payload_id",
            "fresh_kernel_job_result_payload:",
        ):
            raise ValueError("fresh Result payload identity differs")
        return self


class FreshJobResultDescriptor(FrozenModel):
    result_id: str = Field(min_length=1)
    descriptor_contract_id: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    result_namespace: str = Field(min_length=1)
    artifact_relative_path: str = Field(min_length=1)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_byte_count: int = Field(gt=0)
    payload_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_descriptor(self) -> FreshJobResultDescriptor:
        _validate_relative_path(self.artifact_relative_path)
        if self.result_id != identity(
            self,
            "result_id",
            "fresh_kernel_job_result_descriptor:",
        ):
            raise ValueError("fresh Result descriptor identity differs")
        return self


class FreshFailureLocus(FrozenModel):
    locus_id: str = Field(min_length=1)
    stage: FailureStage
    component_key: str | None = None
    attempt_index: int | None = Field(default=None, ge=0, le=3)
    reason_code: str = Field(min_length=1)
    source_descriptor_id: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_locus(self) -> FreshFailureLocus:
        if self.locus_id != identity(
            self,
            "locus_id",
            "fresh_kernel_failure_locus:",
        ):
            raise ValueError("fresh FailureLocus identity differs")
        return self


class FreshJobBoundAttemptTrace(FrozenModel):
    trace_id: str = Field(min_length=1)
    trace_contract_id: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    terminal_kind: TerminalKind
    component_attempts: tuple[FreshComponentAttemptEvidence, ...] = Field(
        min_length=1,
        max_length=4,
    )
    failure_loci: tuple[FreshFailureLocus, ...] = ()
    correction_count: int = Field(ge=0, le=4)
    terminal_projection_count: Literal[1] = 1
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_trace(self) -> FreshJobBoundAttemptTrace:
        if self.correction_count != sum(
            int(item.correction_invoked) for item in self.component_attempts
        ):
            raise ValueError("fresh AttemptTrace correction count differs")
        if self.trace_id != identity(
            self,
            "trace_id",
            "fresh_kernel_job_bound_attempt_trace:",
        ):
            raise ValueError("fresh AttemptTrace identity differs")
        return self


class FreshOutcomeRow(FrozenModel):
    row_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    job_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    raw_execution_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    terminal_kind: TerminalKind
    correction_count: int = Field(ge=0, le=4)
    task_completion: bool | None
    task_verifier_invoked: bool
    final_result_id: str | None = None
    final_base_valid: bool | None = None
    final_mechanism_qualified: bool | None = None
    final_qualified_valid: bool | None = None
    failure_locus_ids: tuple[str, ...] = ()
    formal_empirical_row: bool
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> FreshOutcomeRow:
        if self.formal_empirical_row != (self.evidence_kind == "empirical_execution"):
            raise ValueError("fresh Outcome empirical status differs from evidence kind")
        if self.final_qualified_valid is not None and self.final_qualified_valid != bool(
            self.final_base_valid and self.final_mechanism_qualified
        ):
            raise ValueError("fresh Outcome Qualified validity is not its conjunction")
        if self.row_id != identity(
            self,
            "row_id",
            "fresh_kernel_outcome_row:",
        ):
            raise ValueError("fresh Outcome row identity differs")
        return self


class FreshEvidenceBundle(FrozenModel):
    raw: FreshRawExecutionDescriptor
    result: FreshJobResultDescriptor
    trace: FreshJobBoundAttemptTrace
    row: FreshOutcomeRow


class FreshExactEvidenceSetEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    evaluator_contract_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    evidence_kind: Literal["scripted_preflight_control"] = "scripted_preflight_control"
    raw_descriptor_count: Literal[192] = 192
    result_descriptor_count: Literal[192] = 192
    trace_count: Literal[192] = 192
    outcome_row_count: Literal[192] = 192
    artifact_file_count: Literal[384] = 384
    artifact_byte_match_count: Literal[384] = 384
    exact_job_set_match: Literal[True] = True
    unique_layer_identity_match: Literal[True] = True
    parent_revalidation_passed: Literal[True] = True
    trace_reconstruction_passed: Literal[True] = True
    outcome_reconstruction_passed: Literal[True] = True
    terminal_kind_counts: dict[str, int]
    empirical: Literal[False] = False
    empirical_numerator_materialized: Literal[False] = False
    empirical_estimate_materialized: Literal[False] = False
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evaluation(self) -> FreshExactEvidenceSetEvaluation:
        if sum(self.terminal_kind_counts.values()) != self.outcome_row_count:
            raise ValueError("fresh terminal counts do not partition exact Jobs")
        if self.evaluation_id != identity(
            self,
            "evaluation_id",
            "fresh_exact_evidence_set_evaluation:",
        ):
            raise ValueError("fresh evidence-set evaluation identity differs")
        return self


def _validate_relative_path(value: str) -> None:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("artifact descriptor path is not safe and relative")


def _artifact_path(root: Path, relative_path: str) -> Path:
    _validate_relative_path(relative_path)
    resolved_root = root.resolve()
    current = root
    for part in PurePosixPath(relative_path).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("artifact path contains a symlink")
    candidate = root.joinpath(*PurePosixPath(relative_path).parts)
    if not candidate.resolve(strict=False).is_relative_to(resolved_root):
        raise ValueError("artifact path escapes exact root")
    return candidate


def _load_canonical_artifact(
    *,
    root: Path,
    relative_path: str,
    expected_sha256: str,
    expected_byte_count: int,
    model_type: type[BaseModel],
) -> BaseModel:
    path = _artifact_path(root, relative_path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("artifact descriptor does not resolve to a regular file")
    payload = path.read_bytes()
    if len(payload) != expected_byte_count or sha256_bytes(payload) != expected_sha256:
        raise ValueError("artifact descriptor does not bind actual file bytes")
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("artifact is not valid JSON") from exc
    model = model_type.model_validate(decoded)
    if canonical_model_bytes(model) != payload:
        raise ValueError("artifact bytes are not exact canonical model serialization")
    return model


def expected_raw_artifact_filename_from_id(job_id: str) -> str:
    return f"raw/{hashlib.sha256(job_id.encode('utf-8')).hexdigest()}.json"


def expected_raw_artifact_filename(job: kernel_models.AuthoritativeDevelopmentJob) -> str:
    return expected_raw_artifact_filename_from_id(job.job_id)


def expected_result_artifact_filename_from_id(job_id: str) -> str:
    return f"result/{hashlib.sha256(job_id.encode('utf-8')).hexdigest()}.json"


def expected_result_artifact_filename(job: kernel_models.AuthoritativeDevelopmentJob) -> str:
    return expected_result_artifact_filename_from_id(job.job_id)


def _strict(model_type: type[BaseModel], value: BaseModel) -> Any:
    return model_type.model_validate(value.model_dump(mode="python", warnings=False))


def _scripted_raw_payload(
    *,
    job: kernel_models.AuthoritativeDevelopmentJob,
    sequence: JobComponentSequence,
    execution_contract_id: str,
    terminal_registry_id: str,
) -> FreshRawExecutionPayload:
    attempts = tuple(
        cast(
            FreshComponentAttemptEvidence,
            make_identity_model(
                FreshComponentAttemptEvidence,
                {
                    "component_index": index,
                    "component_key": component_key,
                    "reached_state_token": canonical_hash(
                        {
                            "job_id": job.job_id,
                            "component_index": index,
                            "component_key": component_key,
                        },
                        prefix="fresh_kernel_scripted_state:",
                    ).split(":", 1)[1][:24],
                },
                field="attempt_id",
                prefix="fresh_kernel_component_attempt:",
            ),
        )
        for index, component_key in enumerate(sequence.ordered_component_keys)
    )
    return cast(
        FreshRawExecutionPayload,
        make_identity_model(
            FreshRawExecutionPayload,
            {
                "evidence_kind": "scripted_preflight_control",
                "job_id": job.job_id,
                "execution_contract_id": execution_contract_id,
                "terminal_registry_id": terminal_registry_id,
                "terminal_kind": "completed_qualified",
                "component_attempts": attempts,
                "terminal_evidence_id": canonical_hash(
                    {
                        "job_id": job.job_id,
                        "execution_contract_id": execution_contract_id,
                        "terminal_kind": "completed_qualified",
                        "control": "scripted_reference_only",
                    },
                    prefix="fresh_kernel_terminal_evidence:",
                ),
            },
            field="payload_id",
            prefix="fresh_kernel_raw_execution_payload:",
        ),
    )


def _scripted_validity(
    *,
    job_id: str,
    raw_execution_id: str,
) -> FreshTerminalValidity:
    return cast(
        FreshTerminalValidity,
        make_identity_model(
            FreshTerminalValidity,
            {
                "terminal_kind": "completed_qualified",
                "task_completion": True,
                "task_verifier_invoked": True,
                "final_response_abi_valid": True,
                "final_result_id": canonical_hash(
                    {"job_id": job_id, "raw_execution_id": raw_execution_id},
                    prefix="fresh_kernel_scripted_final_result:",
                ),
                "final_base_valid": True,
                "final_mechanism_qualified": True,
                "final_qualified_valid": True,
            },
            field="validity_id",
            prefix="fresh_kernel_terminal_validity:",
        ),
    )


def _trace_and_row(
    *,
    job: kernel_models.AuthoritativeDevelopmentJob,
    manifest: kernel_models.AuthoritativeDevelopmentManifest,
    runner: kernel_models.AuthoritativeRunnerContract,
    execution: kernel_models.AuthoritativeExecutionContract,
    registry: FreshTerminalRegistry,
    trace_contract: FreshJobBoundAttemptTraceContract,
    outcome_contract: FreshOutcomeRowContract,
    raw: FreshRawExecutionDescriptor,
    raw_payload: FreshRawExecutionPayload,
    result: FreshJobResultDescriptor,
    result_payload: FreshJobResultPayload,
) -> tuple[FreshJobBoundAttemptTrace, FreshOutcomeRow]:
    trace = cast(
        FreshJobBoundAttemptTrace,
        make_identity_model(
            FreshJobBoundAttemptTrace,
            {
                "trace_contract_id": trace_contract.contract_id,
                "evidence_kind": raw.evidence_kind,
                "job_id": job.job_id,
                "raw_execution_id": raw.raw_execution_id,
                "result_id": result.result_id,
                "terminal_kind": result_payload.terminal_kind,
                "component_attempts": raw_payload.component_attempts,
                "failure_loci": (),
                "correction_count": 0,
            },
            field="trace_id",
            prefix="fresh_kernel_job_bound_attempt_trace:",
        ),
    )
    validity = result_payload.validity
    row = cast(
        FreshOutcomeRow,
        make_identity_model(
            FreshOutcomeRow,
            {
                "outcome_contract_id": outcome_contract.contract_id,
                "evidence_kind": raw.evidence_kind,
                "job_id": job.job_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "execution_contract_id": execution.contract_id,
                "package_id": job.package_id,
                "replica_index": job.replica_index,
                "raw_execution_id": raw.raw_execution_id,
                "result_id": result.result_id,
                "trace_id": trace.trace_id,
                "terminal_registry_id": registry.registry_id,
                "terminal_kind": result_payload.terminal_kind,
                "correction_count": trace.correction_count,
                "task_completion": validity.task_completion,
                "task_verifier_invoked": validity.task_verifier_invoked,
                "final_result_id": validity.final_result_id,
                "final_base_valid": validity.final_base_valid,
                "final_mechanism_qualified": validity.final_mechanism_qualified,
                "final_qualified_valid": validity.final_qualified_valid,
                "failure_locus_ids": tuple(item.locus_id for item in trace.failure_loci),
                "formal_empirical_row": raw.evidence_kind == "empirical_execution",
            },
            field="row_id",
            prefix="fresh_kernel_outcome_row:",
        ),
    )
    return trace, row


def build_scripted_bundle(
    *,
    artifact_root: Path,
    writer: Any,
    job: kernel_models.AuthoritativeDevelopmentJob,
    sequence: JobComponentSequence,
    manifest: kernel_models.AuthoritativeDevelopmentManifest,
    runner: kernel_models.AuthoritativeRunnerContract,
    execution: kernel_models.AuthoritativeExecutionContract,
    registry: FreshTerminalRegistry,
    raw_contract: FreshRawExecutionDescriptorContract,
    result_contract: FreshJobResultDescriptorContract,
    trace_contract: FreshJobBoundAttemptTraceContract,
    outcome_contract: FreshOutcomeRowContract,
) -> FreshEvidenceBundle:
    raw_payload = _scripted_raw_payload(
        job=job,
        sequence=sequence,
        execution_contract_id=execution.contract_id,
        terminal_registry_id=registry.registry_id,
    )
    raw_path = expected_raw_artifact_filename(job)
    raw_sha, raw_bytes = writer.write_raw(job_id=job.job_id, payload=raw_payload)
    raw = cast(
        FreshRawExecutionDescriptor,
        make_identity_model(
            FreshRawExecutionDescriptor,
            {
                "descriptor_contract_id": raw_contract.contract_id,
                "evidence_kind": "scripted_preflight_control",
                "job_id": job.job_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "execution_contract_id": execution.contract_id,
                "package_id": job.package_id,
                "replica_index": job.replica_index,
                "raw_namespace": job.raw_namespace,
                "artifact_relative_path": raw_path,
                "artifact_sha256": raw_sha,
                "artifact_byte_count": raw_bytes,
                "payload_id": raw_payload.payload_id,
            },
            field="raw_execution_id",
            prefix="fresh_kernel_raw_execution_descriptor:",
        ),
    )
    validity = _scripted_validity(job_id=job.job_id, raw_execution_id=raw.raw_execution_id)
    result_payload = cast(
        FreshJobResultPayload,
        make_identity_model(
            FreshJobResultPayload,
            {
                "evidence_kind": "scripted_preflight_control",
                "job_id": job.job_id,
                "raw_execution_id": raw.raw_execution_id,
                "execution_contract_id": execution.contract_id,
                "terminal_registry_id": registry.registry_id,
                "terminal_kind": "completed_qualified",
                "validity": validity,
            },
            field="payload_id",
            prefix="fresh_kernel_job_result_payload:",
        ),
    )
    result_path = expected_result_artifact_filename(job)
    result_sha, result_bytes = writer.write_result(job_id=job.job_id, payload=result_payload)
    result = cast(
        FreshJobResultDescriptor,
        make_identity_model(
            FreshJobResultDescriptor,
            {
                "descriptor_contract_id": result_contract.contract_id,
                "evidence_kind": "scripted_preflight_control",
                "job_id": job.job_id,
                "raw_execution_id": raw.raw_execution_id,
                "execution_contract_id": execution.contract_id,
                "result_namespace": job.result_namespace,
                "artifact_relative_path": result_path,
                "artifact_sha256": result_sha,
                "artifact_byte_count": result_bytes,
                "payload_id": result_payload.payload_id,
            },
            field="result_id",
            prefix="fresh_kernel_job_result_descriptor:",
        ),
    )
    trace, row = _trace_and_row(
        job=job,
        manifest=manifest,
        runner=runner,
        execution=execution,
        registry=registry,
        trace_contract=trace_contract,
        outcome_contract=outcome_contract,
        raw=raw,
        raw_payload=raw_payload,
        result=result,
        result_payload=result_payload,
    )
    return FreshEvidenceBundle(raw=raw, result=result, trace=trace, row=row)


def _validated_parents(
    *,
    catalog: kernel_models.AuthoritativeRunnerPackageCatalog,
    manifest: kernel_models.AuthoritativeDevelopmentManifest,
    runner: kernel_models.AuthoritativeRunnerContract,
    execution: kernel_models.AuthoritativeExecutionContract,
    registry: FreshTerminalRegistry,
    raw_contract: FreshRawExecutionDescriptorContract,
    result_contract: FreshJobResultDescriptorContract,
    trace_contract: FreshJobBoundAttemptTraceContract,
    outcome_contract: FreshOutcomeRowContract,
    evaluator_contract: FreshExactEvidenceSetEvaluatorContract,
) -> tuple[
    kernel_models.AuthoritativeRunnerPackageCatalog,
    kernel_models.AuthoritativeDevelopmentManifest,
    kernel_models.AuthoritativeRunnerContract,
    kernel_models.AuthoritativeExecutionContract,
    FreshTerminalRegistry,
    FreshRawExecutionDescriptorContract,
    FreshJobResultDescriptorContract,
    FreshJobBoundAttemptTraceContract,
    FreshOutcomeRowContract,
    FreshExactEvidenceSetEvaluatorContract,
]:
    catalog = cast(
        kernel_models.AuthoritativeRunnerPackageCatalog,
        _strict(kernel_models.AuthoritativeRunnerPackageCatalog, catalog),
    )
    manifest = cast(
        kernel_models.AuthoritativeDevelopmentManifest,
        _strict(kernel_models.AuthoritativeDevelopmentManifest, manifest),
    )
    runner = cast(
        kernel_models.AuthoritativeRunnerContract,
        _strict(kernel_models.AuthoritativeRunnerContract, runner),
    )
    execution = cast(
        kernel_models.AuthoritativeExecutionContract,
        _strict(kernel_models.AuthoritativeExecutionContract, execution),
    )
    registry = cast(FreshTerminalRegistry, _strict(FreshTerminalRegistry, registry))
    raw_contract = cast(
        FreshRawExecutionDescriptorContract,
        _strict(FreshRawExecutionDescriptorContract, raw_contract),
    )
    result_contract = cast(
        FreshJobResultDescriptorContract,
        _strict(FreshJobResultDescriptorContract, result_contract),
    )
    trace_contract = cast(
        FreshJobBoundAttemptTraceContract,
        _strict(FreshJobBoundAttemptTraceContract, trace_contract),
    )
    outcome_contract = cast(
        FreshOutcomeRowContract,
        _strict(FreshOutcomeRowContract, outcome_contract),
    )
    evaluator_contract = cast(
        FreshExactEvidenceSetEvaluatorContract,
        _strict(FreshExactEvidenceSetEvaluatorContract, evaluator_contract),
    )
    jobs = tuple(
        cast(
            kernel_models.AuthoritativeDevelopmentJob,
            _strict(kernel_models.AuthoritativeDevelopmentJob, item),
        )
        for item in manifest.jobs
    )
    if jobs != manifest.jobs:
        raise ValueError("v26.194 Manifest Job strict revalidation changed objects")
    if (
        runner.manifest_id != manifest.manifest_id
        or runner.package_catalog_id != catalog.catalog_id
        or execution.manifest_id != manifest.manifest_id
        or execution.runner_id != runner.runner_id
        or execution.package_catalog_id != catalog.catalog_id
    ):
        raise ValueError("v26.194 execution parents cross exact objects")
    exact = tuple(manifest.expected_job_ids)
    if any(
        item != expected
        for item, expected in (
            (raw_contract.exact_job_ids, exact),
            (result_contract.exact_job_ids, exact),
            (outcome_contract.exact_job_ids, exact),
        )
    ):
        raise ValueError("fresh authority Contract crosses exact v26.194 Jobs")
    parent_projection = (
        registry.execution_contract_id,
        registry.manifest_id,
        registry.runner_id,
        registry.package_catalog_id,
        raw_contract.execution_contract_id,
        raw_contract.manifest_id,
        raw_contract.runner_id,
        raw_contract.package_catalog_id,
        result_contract.execution_contract_id,
        result_contract.manifest_id,
        result_contract.runner_id,
        trace_contract.execution_contract_id,
        trace_contract.manifest_id,
        trace_contract.runner_id,
        outcome_contract.execution_contract_id,
        outcome_contract.manifest_id,
        outcome_contract.runner_id,
        evaluator_contract.execution_contract_id,
        evaluator_contract.manifest_id,
        evaluator_contract.runner_id,
        evaluator_contract.package_catalog_id,
    )
    expected_projection = (
        execution.contract_id,
        manifest.manifest_id,
        runner.runner_id,
        catalog.catalog_id,
        execution.contract_id,
        manifest.manifest_id,
        runner.runner_id,
        catalog.catalog_id,
        execution.contract_id,
        manifest.manifest_id,
        runner.runner_id,
        execution.contract_id,
        manifest.manifest_id,
        runner.runner_id,
        execution.contract_id,
        manifest.manifest_id,
        runner.runner_id,
        execution.contract_id,
        manifest.manifest_id,
        runner.runner_id,
        catalog.catalog_id,
    )
    if parent_projection != expected_projection:
        raise ValueError("fresh authority layer crosses v26.194 execution parents")
    if (
        result_contract.raw_descriptor_contract_id != raw_contract.contract_id
        or trace_contract.raw_descriptor_contract_id != raw_contract.contract_id
        or trace_contract.result_descriptor_contract_id != result_contract.contract_id
        or outcome_contract.raw_descriptor_contract_id != raw_contract.contract_id
        or outcome_contract.result_descriptor_contract_id != result_contract.contract_id
        or outcome_contract.attempt_trace_contract_id != trace_contract.contract_id
        or evaluator_contract.raw_descriptor_contract_id != raw_contract.contract_id
        or evaluator_contract.result_descriptor_contract_id != result_contract.contract_id
        or evaluator_contract.attempt_trace_contract_id != trace_contract.contract_id
        or evaluator_contract.outcome_row_contract_id != outcome_contract.contract_id
        or any(
            item.terminal_registry_id != registry.registry_id
            for item in (
                raw_contract,
                result_contract,
                trace_contract,
                outcome_contract,
                evaluator_contract,
            )
        )
    ):
        raise ValueError("fresh authority layer DAG is not exact")
    sequences = {item.job_id: item for item in trace_contract.job_component_sequences}
    if set(sequences) != set(exact):
        raise ValueError("fresh AttemptTrace Contract crosses exact Job set")
    package_map = {item.package_id: item for item in catalog.packages}
    for job in jobs:
        package = package_map.get(job.package_id)
        sequence = sequences[job.job_id]
        if package is None or (
            sequence.package_id,
            sequence.ordered_component_keys,
        ) != (job.package_id, package.topological_component_keys):
            raise ValueError("fresh Job sequence crosses exact Package topology")
    return (
        catalog,
        manifest,
        runner,
        execution,
        registry,
        raw_contract,
        result_contract,
        trace_contract,
        outcome_contract,
        evaluator_contract,
    )


def validate_fresh_bundle(
    *,
    artifact_root: Path,
    job: kernel_models.AuthoritativeDevelopmentJob,
    sequence: JobComponentSequence,
    manifest: kernel_models.AuthoritativeDevelopmentManifest,
    runner: kernel_models.AuthoritativeRunnerContract,
    execution: kernel_models.AuthoritativeExecutionContract,
    registry: FreshTerminalRegistry,
    raw_contract: FreshRawExecutionDescriptorContract,
    result_contract: FreshJobResultDescriptorContract,
    trace_contract: FreshJobBoundAttemptTraceContract,
    outcome_contract: FreshOutcomeRowContract,
    bundle: FreshEvidenceBundle,
    expected_evidence_kind: EvidenceKind,
) -> None:
    job = cast(
        kernel_models.AuthoritativeDevelopmentJob,
        _strict(kernel_models.AuthoritativeDevelopmentJob, job),
    )
    if next((item for item in manifest.jobs if item.job_id == job.job_id), None) != job:
        raise ValueError("fresh evidence Job is not exact Manifest object")
    bundle = cast(FreshEvidenceBundle, _strict(FreshEvidenceBundle, bundle))
    raw, result, trace, row = bundle.raw, bundle.result, bundle.trace, bundle.row
    expected_raw_parents = (
        raw_contract.contract_id,
        expected_evidence_kind,
        job.job_id,
        manifest.manifest_id,
        runner.runner_id,
        execution.contract_id,
        job.package_id,
        job.replica_index,
        job.raw_namespace,
        expected_raw_artifact_filename(job),
    )
    observed_raw_parents = (
        raw.descriptor_contract_id,
        raw.evidence_kind,
        raw.job_id,
        raw.manifest_id,
        raw.runner_id,
        raw.execution_contract_id,
        raw.package_id,
        raw.replica_index,
        raw.raw_namespace,
        raw.artifact_relative_path,
    )
    if observed_raw_parents != expected_raw_parents:
        raise ValueError("fresh Raw descriptor crosses exact v26.194 Job")
    raw_payload = cast(
        FreshRawExecutionPayload,
        _load_canonical_artifact(
            root=artifact_root,
            relative_path=raw.artifact_relative_path,
            expected_sha256=raw.artifact_sha256,
            expected_byte_count=raw.artifact_byte_count,
            model_type=FreshRawExecutionPayload,
        ),
    )
    expected_raw_payload = _scripted_raw_payload(
        job=job,
        sequence=sequence,
        execution_contract_id=execution.contract_id,
        terminal_registry_id=registry.registry_id,
    )
    if raw_payload != expected_raw_payload or raw.payload_id != raw_payload.payload_id:
        raise ValueError("fresh Raw payload is not reconstructed from exact Job")
    expected_result_parents = (
        result_contract.contract_id,
        expected_evidence_kind,
        job.job_id,
        raw.raw_execution_id,
        execution.contract_id,
        job.result_namespace,
        expected_result_artifact_filename(job),
    )
    observed_result_parents = (
        result.descriptor_contract_id,
        result.evidence_kind,
        result.job_id,
        result.raw_execution_id,
        result.execution_contract_id,
        result.result_namespace,
        result.artifact_relative_path,
    )
    if observed_result_parents != expected_result_parents:
        raise ValueError("fresh Result descriptor crosses Raw or Job")
    result_payload = cast(
        FreshJobResultPayload,
        _load_canonical_artifact(
            root=artifact_root,
            relative_path=result.artifact_relative_path,
            expected_sha256=result.artifact_sha256,
            expected_byte_count=result.artifact_byte_count,
            model_type=FreshJobResultPayload,
        ),
    )
    expected_validity = _scripted_validity(
        job_id=job.job_id,
        raw_execution_id=raw.raw_execution_id,
    )
    expected_result_payload = cast(
        FreshJobResultPayload,
        make_identity_model(
            FreshJobResultPayload,
            {
                "evidence_kind": expected_evidence_kind,
                "job_id": job.job_id,
                "raw_execution_id": raw.raw_execution_id,
                "execution_contract_id": execution.contract_id,
                "terminal_registry_id": registry.registry_id,
                "terminal_kind": "completed_qualified",
                "validity": expected_validity,
            },
            field="payload_id",
            prefix="fresh_kernel_job_result_payload:",
        ),
    )
    if result_payload != expected_result_payload or result.payload_id != result_payload.payload_id:
        raise ValueError("fresh Result payload is not reconstructed from Raw")
    policy = next(
        item for item in registry.policies if item.terminal_kind == result_payload.terminal_kind
    )
    if expected_evidence_kind == "empirical_execution" and (
        policy.registration_status != "reachable"
    ):
        raise ValueError("non-reachable terminal cannot enter empirical evidence")
    expected_trace, expected_row = _trace_and_row(
        job=job,
        manifest=manifest,
        runner=runner,
        execution=execution,
        registry=registry,
        trace_contract=trace_contract,
        outcome_contract=outcome_contract,
        raw=raw,
        raw_payload=raw_payload,
        result=result,
        result_payload=result_payload,
    )
    if trace != expected_trace:
        raise ValueError("fresh AttemptTrace or FailureLocus is not reconstructed")
    if row != expected_row:
        raise ValueError("fresh Outcome row is not reconstructed from artifacts")


def evaluate_fresh_evidence_set(
    *,
    artifact_root: Path,
    bundles: Sequence[FreshEvidenceBundle],
    catalog: kernel_models.AuthoritativeRunnerPackageCatalog,
    manifest: kernel_models.AuthoritativeDevelopmentManifest,
    runner: kernel_models.AuthoritativeRunnerContract,
    execution: kernel_models.AuthoritativeExecutionContract,
    registry: FreshTerminalRegistry,
    raw_contract: FreshRawExecutionDescriptorContract,
    result_contract: FreshJobResultDescriptorContract,
    trace_contract: FreshJobBoundAttemptTraceContract,
    outcome_contract: FreshOutcomeRowContract,
    evaluator_contract: FreshExactEvidenceSetEvaluatorContract,
    expected_evidence_kind: EvidenceKind,
) -> FreshExactEvidenceSetEvaluation:
    (
        catalog,
        manifest,
        runner,
        execution,
        registry,
        raw_contract,
        result_contract,
        trace_contract,
        outcome_contract,
        evaluator_contract,
    ) = _validated_parents(
        catalog=catalog,
        manifest=manifest,
        runner=runner,
        execution=execution,
        registry=registry,
        raw_contract=raw_contract,
        result_contract=result_contract,
        trace_contract=trace_contract,
        outcome_contract=outcome_contract,
        evaluator_contract=evaluator_contract,
    )
    if expected_evidence_kind != "scripted_preflight_control":
        raise ValueError("empirical evaluation remains unauthorized pending independent audit")
    if len(bundles) != EXPECTED_JOB_COUNT:
        raise ValueError("fresh evidence differs from exact Manifest denominator")
    by_job: dict[str, FreshEvidenceBundle] = {}
    for bundle in bundles:
        bundle = cast(FreshEvidenceBundle, _strict(FreshEvidenceBundle, bundle))
        if bundle.row.job_id in by_job:
            raise ValueError("fresh evidence repeats a Job")
        by_job[bundle.row.job_id] = bundle
    if set(by_job) != set(manifest.expected_job_ids):
        raise ValueError("fresh evidence Job set differs from Manifest")
    identity_sets = (
        {item.raw.raw_execution_id for item in bundles},
        {item.result.result_id for item in bundles},
        {item.trace.trace_id for item in bundles},
        {item.row.row_id for item in bundles},
    )
    if any(len(items) != EXPECTED_JOB_COUNT for items in identity_sets):
        raise ValueError("fresh evidence repeats a layer identity")
    jobs = {item.job_id: item for item in manifest.jobs}
    sequences = {item.job_id: item for item in trace_contract.job_component_sequences}
    for job_id in manifest.expected_job_ids:
        validate_fresh_bundle(
            artifact_root=artifact_root,
            job=jobs[job_id],
            sequence=sequences[job_id],
            manifest=manifest,
            runner=runner,
            execution=execution,
            registry=registry,
            raw_contract=raw_contract,
            result_contract=result_contract,
            trace_contract=trace_contract,
            outcome_contract=outcome_contract,
            bundle=by_job[job_id],
            expected_evidence_kind=expected_evidence_kind,
        )
    terminal_counts = dict(
        sorted(
            Counter(
                by_job[job_id].row.terminal_kind for job_id in manifest.expected_job_ids
            ).items()
        )
    )
    return cast(
        FreshExactEvidenceSetEvaluation,
        make_identity_model(
            FreshExactEvidenceSetEvaluation,
            {
                "evaluator_contract_id": evaluator_contract.contract_id,
                "terminal_registry_id": registry.registry_id,
                "execution_contract_id": execution.contract_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "terminal_kind_counts": terminal_counts,
            },
            field="evaluation_id",
            prefix="fresh_exact_evidence_set_evaluation:",
        ),
    )


__all__ = [
    "EvidenceKind",
    "FreshComponentAttemptEvidence",
    "FreshEvidenceBundle",
    "FreshExactEvidenceSetEvaluation",
    "FreshExactEvidenceSetEvaluatorContract",
    "FreshFailureLocus",
    "FreshJobBoundAttemptTrace",
    "FreshJobBoundAttemptTraceContract",
    "FreshJobResultDescriptor",
    "FreshJobResultDescriptorContract",
    "FreshJobResultPayload",
    "FreshOutcomeRow",
    "FreshOutcomeRowContract",
    "FreshRawExecutionDescriptor",
    "FreshRawExecutionDescriptorContract",
    "FreshRawExecutionPayload",
    "FreshTerminalPolicy",
    "FreshTerminalRegistry",
    "FreshTerminalValidity",
    "JobComponentSequence",
    "TerminalKind",
    "build_scripted_bundle",
    "canonical_model_bytes",
    "evaluate_fresh_evidence_set",
    "expected_raw_artifact_filename",
    "expected_raw_artifact_filename_from_id",
    "expected_result_artifact_filename",
    "expected_result_artifact_filename_from_id",
    "identity",
    "make_identity_model",
    "sha256_bytes",
    "validate_fresh_bundle",
]
