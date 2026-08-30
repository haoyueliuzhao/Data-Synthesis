from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any, Final, Literal, cast, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.job_bound_multistep_outcome import (
    CapabilityDevelopmentJob,
    CapabilityDevelopmentJobManifest,
)
from trusted_synthesis.hashing import canonical_hash

AUTHORITATIVE_JOB_BOUND_OUTCOME_VERSION: Final = "authoritative_job_bound_outcome.v2"
EXPECTED_JOB_COUNT: Final = 192

EvidenceKind = Literal["scripted_preflight_control", "empirical_execution"]
TerminalRegistrationStatus = Literal[
    "reachable",
    "registered_but_unreachable_under_frozen_runner",
    "not_applicable_with_independent_exclusion_witness",
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
FailureEvaluability = Literal["unevaluable", "evaluated_false", "not_applicable"]


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


class FailureLocus(FrozenModel):
    locus_id: str = Field(min_length=1)
    stage: FailureStage
    component_key: str | None = None
    attempt_index: int | None = Field(default=None, ge=0, le=3)
    reason_code: str = Field(min_length=1)
    evaluability: FailureEvaluability
    source_descriptor_id: str = Field(min_length=1)
    schema_version: str = AUTHORITATIVE_JOB_BOUND_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_locus(self) -> FailureLocus:
        component_stages = {
            "action_abi",
            "action_reference",
            "state_precondition",
            "operation_support",
            "mechanism",
        }
        outer_stages = {
            "provider",
            "transport",
            "privacy",
            "resource",
            "instrument",
            "model_identity",
            "thinking",
            "usage",
            "final_abi",
            "base_answer",
            "base_citation",
            "policy",
        }
        if self.stage in component_stages and (
            self.component_key is None or self.attempt_index is None
        ):
            raise ValueError("Component-local FailureLocus lacks Component or attempt")
        if self.stage in outer_stages and (
            self.component_key is not None or self.attempt_index is not None
        ):
            raise ValueError("non-Component FailureLocus carries Component coordinates")
        if self.locus_id != identity(
            self,
            "locus_id",
            "capability_authoritative_failure_locus:",
        ):
            raise ValueError("FailureLocus identity is invalid")
        return self


class ComponentAttemptEvidence(FrozenModel):
    attempt_id: str = Field(min_length=1)
    component_index: int = Field(ge=0, le=3)
    component_key: str = Field(min_length=1)
    reached_state_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    first_response_abi_valid: bool
    first_action_reference_valid: bool | None = None
    first_action_state_precondition_valid: bool | None = None
    first_action_accepted: bool | None = None
    correction_invoked: bool
    correction_response_abi_valid: bool | None = None
    corrected_action_reference_valid: bool | None = None
    corrected_action_state_precondition_valid: bool | None = None
    corrected_action_accepted: bool | None = None
    committed: bool
    terminal: bool
    terminal_kind: TerminalKind | None = None
    schema_version: str = AUTHORITATIVE_JOB_BOUND_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_attempt(self) -> ComponentAttemptEvidence:
        if not self.first_response_abi_valid:
            if (
                any(
                    item is not None
                    for item in (
                        self.first_action_reference_valid,
                        self.first_action_state_precondition_valid,
                        self.first_action_accepted,
                    )
                )
                or self.correction_invoked
            ):
                raise ValueError("ABI-invalid first response carries Action disposition")
        elif self.first_action_reference_valid is None:
            raise ValueError("ABI-valid first response lacks Action-reference disposition")
        if self.correction_invoked and self.correction_response_abi_valid is None:
            raise ValueError("correction attempt lacks ABI disposition")
        if not self.correction_invoked and any(
            item is not None
            for item in (
                self.correction_response_abi_valid,
                self.corrected_action_reference_valid,
                self.corrected_action_state_precondition_valid,
                self.corrected_action_accepted,
            )
        ):
            raise ValueError("non-correction attempt carries correction disposition")
        if self.committed and self.terminal:
            raise ValueError("committed Component attempt is also terminal")
        if self.terminal != (self.terminal_kind is not None):
            raise ValueError("Component terminal flag and terminal kind differ")
        if self.attempt_id != identity(
            self,
            "attempt_id",
            "capability_authoritative_component_attempt:",
        ):
            raise ValueError("ComponentAttemptEvidence identity is invalid")
        return self


class TerminalExclusionWitness(FrozenModel):
    witness_id: str = Field(min_length=1)
    terminal_kind: TerminalKind
    frozen_runner_id: str = Field(min_length=1)
    frozen_runner_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_parent_ids: tuple[str, ...] = Field(min_length=1)
    exclusion_reason_code: str = Field(min_length=1)
    excluded_branch_token_counts: dict[str, int] = Field(min_length=1)
    applicable_branch_count: Literal[0] = 0
    independent_contract_check: Literal[True] = True
    not_applicable: Literal[True] = True
    schema_version: str = AUTHORITATIVE_JOB_BOUND_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_witness(self) -> TerminalExclusionWitness:
        if any(self.excluded_branch_token_counts.values()):
            raise ValueError("terminal exclusion witness found a frozen Runner branch")
        if self.witness_id != identity(
            self,
            "witness_id",
            "capability_authoritative_terminal_exclusion_witness:",
        ):
            raise ValueError("terminal exclusion witness identity is invalid")
        return self


class AuthoritativeTerminalPolicy(FrozenModel):
    policy_id: str = Field(min_length=1)
    terminal_kind: TerminalKind
    registration_status: TerminalRegistrationStatus
    source_labels: tuple[str, ...] = Field(min_length=1)
    source_parent_ids: tuple[str, ...] = Field(min_length=1)
    exclusion_witness_id: str | None = None
    expected_task_completion: bool | None
    expected_base_validity: bool | None
    expected_mechanism_qualification: bool | None
    expected_qualified_validity: bool | None
    expected_task_verifier_invoked: bool
    expected_mapping_eligible: bool
    exactly_one_outcome_required: Literal[True] = True
    schema_version: str = AUTHORITATIVE_JOB_BOUND_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_policy(self) -> AuthoritativeTerminalPolicy:
        excluded = self.registration_status == ("not_applicable_with_independent_exclusion_witness")
        if excluded != (self.exclusion_witness_id is not None):
            raise ValueError("terminal applicability status and exclusion witness differ")
        if self.expected_qualified_validity is True and not (
            self.expected_base_validity is True
            and self.expected_mechanism_qualification is True
            and self.expected_task_verifier_invoked
        ):
            raise ValueError("Qualified terminal policy lacks exact validity parents")
        if self.policy_id != identity(
            self,
            "policy_id",
            "capability_authoritative_terminal_policy:",
        ):
            raise ValueError("authoritative terminal policy identity is invalid")
        return self


class AuthoritativeTerminalRegistry(FrozenModel):
    registry_id: str = Field(min_length=1)
    v166_terminal_matrix_id: str = Field(min_length=1)
    v179_runner_id: str = Field(min_length=1)
    v179_generation_profile_id: str = Field(min_length=1)
    v180_outer_terminal_audit_id: str = Field(min_length=1)
    derivation_source_labels: tuple[str, ...] = Field(min_length=1)
    consumed_derivation_source_labels: tuple[str, ...] = Field(min_length=1)
    policies: tuple[AuthoritativeTerminalPolicy, ...] = Field(min_length=18, max_length=18)
    exclusion_witnesses: tuple[TerminalExclusionWitness, ...] = ()
    terminal_kind_count: Literal[18] = 18
    unmapped_source_label_count: Literal[0] = 0
    silent_omission_count: Literal[0] = 0
    schema_version: str = AUTHORITATIVE_JOB_BOUND_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_registry(self) -> AuthoritativeTerminalRegistry:
        expected = set(get_args(TerminalKind))
        observed = {item.terminal_kind for item in self.policies}
        if observed != expected or len(self.policies) != len(expected):
            raise ValueError("authoritative terminal registry is not the exact TerminalKind set")
        if self.derivation_source_labels != tuple(sorted(set(self.derivation_source_labels))):
            raise ValueError("terminal derivation labels are not canonical and unique")
        if self.consumed_derivation_source_labels != self.derivation_source_labels:
            raise ValueError("terminal registry leaves an authoritative source label unmapped")
        expected_witness_ids = {
            item.exclusion_witness_id
            for item in self.policies
            if item.exclusion_witness_id is not None
        }
        observed_witness_ids = {item.witness_id for item in self.exclusion_witnesses}
        if expected_witness_ids != observed_witness_ids:
            raise ValueError("terminal registry exclusion witnesses are incomplete")
        if any(
            item.terminal_kind
            != next(
                policy.terminal_kind
                for policy in self.policies
                if policy.exclusion_witness_id == item.witness_id
            )
            for item in self.exclusion_witnesses
        ):
            raise ValueError("terminal exclusion witness crosses its policy")
        if self.registry_id != identity(
            self,
            "registry_id",
            "capability_authoritative_terminal_registry:",
        ):
            raise ValueError("authoritative terminal registry identity is invalid")
        return self


class RawExecutionEvidencePayload(FrozenModel):
    payload_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    terminal_kind: TerminalKind
    component_attempts: tuple[ComponentAttemptEvidence, ...] = Field(max_length=4)
    provider_artifact_ids: tuple[str, ...] = ()
    transport_artifact_ids: tuple[str, ...] = ()
    terminal_evidence_id: str = Field(min_length=1)
    final_parser_input_hash: str | None = None
    final_parser_rejected: bool | None = None
    terminal_projection_count: Literal[1] = 1
    schema_version: str = AUTHORITATIVE_JOB_BOUND_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_payload(self) -> RawExecutionEvidencePayload:
        attempts = self.component_attempts
        if tuple(item.component_index for item in attempts) != tuple(range(len(attempts))):
            raise ValueError("Raw attempt evidence is not contiguous")
        if len({item.component_key for item in attempts}) != len(attempts):
            raise ValueError("Raw attempt evidence repeats a Component")
        if len(set(self.provider_artifact_ids)) != len(self.provider_artifact_ids):
            raise ValueError("Raw evidence repeats a Provider artifact")
        if len(set(self.transport_artifact_ids)) != len(self.transport_artifact_ids):
            raise ValueError("Raw evidence repeats a Transport artifact")
        if self.final_parser_rejected is not None and self.final_parser_input_hash is None:
            raise ValueError("Final parser disposition lacks its exact input hash")
        if self.terminal_kind == "final_response_abi_invalid" and (
            self.final_parser_rejected is not True or self.final_parser_input_hash is None
        ):
            raise ValueError("Final-ABI-invalid Raw evidence lacks parser rejection")
        if self.payload_id != identity(
            self,
            "payload_id",
            "capability_authoritative_raw_execution_payload:",
        ):
            raise ValueError("RawExecutionEvidencePayload identity is invalid")
        return self


class RawExecutionDescriptor(FrozenModel):
    raw_execution_id: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    job_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_package_id: str = Field(min_length=1)
    source_package_artifact_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    raw_namespace: str = Field(min_length=1)
    raw_artifact_path: str = Field(min_length=1)
    payload: RawExecutionEvidencePayload
    schema_version: str = AUTHORITATIVE_JOB_BOUND_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_descriptor(self) -> RawExecutionDescriptor:
        if self.payload.job_id != self.job_id:
            raise ValueError("Raw descriptor crosses its payload Job")
        if self.raw_execution_id != identity(
            self,
            "raw_execution_id",
            "capability_authoritative_raw_execution_descriptor:",
        ):
            raise ValueError("RawExecutionDescriptor identity is invalid")
        return self


class JobResultEvidencePayload(FrozenModel):
    payload_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    terminal_kind: TerminalKind
    task_completion: bool | None
    task_verifier_invoked: bool
    final_result_id: str | None = None
    final_base_valid: bool | None = None
    final_mechanism_qualified: bool | None = None
    final_qualified_valid: bool | None = None
    failure_locus_ids: tuple[str, ...] = ()
    terminal_projection_count: Literal[1] = 1
    schema_version: str = AUTHORITATIVE_JOB_BOUND_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_payload(self) -> JobResultEvidencePayload:
        if len(set(self.failure_locus_ids)) != len(self.failure_locus_ids):
            raise ValueError("Result payload repeats a FailureLocus")
        if self.final_qualified_valid is True and not (
            self.final_base_valid is True and self.final_mechanism_qualified is True
        ):
            raise ValueError("Result Qualified validity lacks its exact conjunction")
        if self.payload_id != identity(
            self,
            "payload_id",
            "capability_authoritative_job_result_payload:",
        ):
            raise ValueError("JobResultEvidencePayload identity is invalid")
        return self


class JobResultDescriptor(FrozenModel):
    result_id: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    result_namespace: str = Field(min_length=1)
    result_artifact_path: str = Field(min_length=1)
    payload: JobResultEvidencePayload
    schema_version: str = AUTHORITATIVE_JOB_BOUND_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_descriptor(self) -> JobResultDescriptor:
        if (
            self.payload.job_id != self.job_id
            or self.payload.raw_execution_id != self.raw_execution_id
        ):
            raise ValueError("Result descriptor crosses its payload parents")
        if self.result_id != identity(
            self,
            "result_id",
            "capability_authoritative_job_result_descriptor:",
        ):
            raise ValueError("JobResultDescriptor identity is invalid")
        return self


class JobBoundAttemptTrace(FrozenModel):
    trace_id: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    job_id: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    terminal_kind: TerminalKind
    component_attempts: tuple[ComponentAttemptEvidence, ...] = Field(max_length=4)
    failure_loci: tuple[FailureLocus, ...] = ()
    correction_count: int = Field(ge=0, le=4)
    terminal_projection_count: Literal[1] = 1
    schema_version: str = AUTHORITATIVE_JOB_BOUND_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_trace(self) -> JobBoundAttemptTrace:
        attempts = self.component_attempts
        if tuple(item.component_index for item in attempts) != tuple(range(len(attempts))):
            raise ValueError("Job-bound AttemptTrace is not contiguous")
        if len({item.component_key for item in attempts}) != len(attempts):
            raise ValueError("Job-bound AttemptTrace repeats a Component")
        terminal_indices = tuple(index for index, item in enumerate(attempts) if item.terminal)
        if terminal_indices and terminal_indices != (len(attempts) - 1,):
            raise ValueError("Job-bound AttemptTrace continues after a terminal")
        if self.correction_count != sum(item.correction_invoked for item in attempts):
            raise ValueError("Job-bound AttemptTrace correction count changed")
        if len({item.locus_id for item in self.failure_loci}) != len(self.failure_loci):
            raise ValueError("Job-bound AttemptTrace repeats a FailureLocus")
        if self.trace_id != identity(
            self,
            "trace_id",
            "capability_authoritative_job_bound_attempt_trace:",
        ):
            raise ValueError("JobBoundAttemptTrace identity is invalid")
        return self


class AuthoritativeCapabilityOutcomeRow(FrozenModel):
    row_id: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    job_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_package_id: str = Field(min_length=1)
    source_package_artifact_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    raw_namespace: str = Field(min_length=1)
    result_namespace: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    terminal_kind: TerminalKind
    correction_count: int = Field(ge=0, le=4)
    first_policy_qualified_valid: bool
    bounded_policy_qualified_valid: bool
    task_completion: bool | None
    task_verifier_invoked: bool
    final_result_id: str | None = None
    final_base_valid: bool | None = None
    final_mechanism_qualified: bool | None = None
    final_qualified_valid: bool | None = None
    first_runtime_uncommitted_locus_id: str | None = None
    first_base_invalid_locus_id: str | None = None
    first_mechanism_failed_locus_id: str | None = None
    terminal_locus_id: str | None = None
    terminal_projection_count: Literal[1] = 1
    schema_version: str = AUTHORITATIVE_JOB_BOUND_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> AuthoritativeCapabilityOutcomeRow:
        expected_first = bool(self.final_qualified_valid is True and self.correction_count == 0)
        expected_bounded = self.final_qualified_valid is True
        if self.first_policy_qualified_valid != expected_first:
            raise ValueError("authoritative q_first row value is not derived")
        if self.bounded_policy_qualified_valid != expected_bounded:
            raise ValueError("authoritative bounded row value is not derived")
        if self.first_policy_qualified_valid and not self.bounded_policy_qualified_valid:
            raise ValueError("authoritative first-policy success is absent under bounded policy")
        if self.row_id != identity(
            self,
            "row_id",
            "capability_authoritative_outcome_row:",
        ):
            raise ValueError("AuthoritativeCapabilityOutcomeRow identity is invalid")
        return self


class JobComponentSequence(FrozenModel):
    job_id: str = Field(min_length=1)
    ordered_component_keys: tuple[str, ...] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def validate_sequence(self) -> JobComponentSequence:
        if len(set(self.ordered_component_keys)) != len(self.ordered_component_keys):
            raise ValueError("authoritative Job Component sequence repeats a Component")
        return self


class AuthoritativeJobBoundOutcomeContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_manifest_id: str = Field(min_length=1)
    predecessor_runner_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    job_component_sequences: tuple[JobComponentSequence, ...] = Field(
        min_length=192,
        max_length=192,
    )
    exact_job_count: Literal[192] = 192
    raw_result_trace_row_bijection_required: Literal[True] = True
    estimator_revalidates_canonical_bytes: Literal[True] = True
    estimator_rebuilds_rows_from_descriptors: Literal[True] = True
    arbitrary_caller_ids_authoritative: Literal[False] = False
    first_action_reference_invalid_policy: Literal[
        "immediate_typed_terminal_without_correction"
    ] = "immediate_typed_terminal_without_correction"
    malformed_final_policy: Literal[
        "validation_error_at_exact_parser_then_typed_final_abi_invalid"
    ] = "validation_error_at_exact_parser_then_typed_final_abi_invalid"
    exactly_one_terminal_projection_per_job: Literal[True] = True
    python_exception_escape_allowed: Literal[False] = False
    formal_empirical_rows_materialized: Literal[False] = False
    schema_version: str = AUTHORITATIVE_JOB_BOUND_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> AuthoritativeJobBoundOutcomeContract:
        job_ids = tuple(item.job_id for item in self.job_component_sequences)
        if job_ids != tuple(sorted(set(job_ids))):
            raise ValueError("authoritative Outcome Contract Job sequences are not exact")
        if self.contract_id != identity(
            self,
            "contract_id",
            "capability_authoritative_job_bound_outcome_contract:",
        ):
            raise ValueError("Authoritative Job-bound Outcome Contract identity is invalid")
        return self


class ExactEvidenceSetEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    registry_id: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    raw_descriptor_count: Literal[192] = 192
    result_descriptor_count: Literal[192] = 192
    trace_count: Literal[192] = 192
    outcome_row_count: Literal[192] = 192
    unique_raw_descriptor_count: Literal[192] = 192
    unique_result_descriptor_count: Literal[192] = 192
    unique_trace_count: Literal[192] = 192
    unique_outcome_row_count: Literal[192] = 192
    exact_job_set_match: Literal[True] = True
    missing_job_count: Literal[0] = 0
    duplicate_job_count: Literal[0] = 0
    extra_job_count: Literal[0] = 0
    crossed_parent_count: Literal[0] = 0
    duplicate_canonical_object_count: Literal[0] = 0
    terminal_projection_count: Literal[192] = 192
    terminal_kind_counts: dict[str, int]
    q_first_numerator: int = Field(ge=0, le=192)
    q_bounded_correction_numerator: int = Field(ge=0, le=192)
    q_first_fraction: str = Field(pattern=r"^[0-9]+/192$")
    q_bounded_correction_fraction: str = Field(pattern=r"^[0-9]+/192$")
    empirical: bool
    schema_version: str = AUTHORITATIVE_JOB_BOUND_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_evaluation(self) -> ExactEvidenceSetEvaluation:
        if self.empirical != (self.evidence_kind == "empirical_execution"):
            raise ValueError("exact evidence-set evaluation empirical label changed")
        if self.q_first_numerator > self.q_bounded_correction_numerator:
            raise ValueError("q_first exceeds bounded-correction success")
        if self.q_first_fraction != f"{self.q_first_numerator}/192":
            raise ValueError("q_first fraction is inconsistent")
        if self.q_bounded_correction_fraction != (f"{self.q_bounded_correction_numerator}/192"):
            raise ValueError("q_bounded fraction is inconsistent")
        if sum(self.terminal_kind_counts.values()) != self.terminal_projection_count:
            raise ValueError("terminal-kind counts do not partition the exact evidence set")
        if self.evaluation_id != identity(
            self,
            "evaluation_id",
            "capability_authoritative_exact_evidence_set_evaluation:",
        ):
            raise ValueError("ExactEvidenceSetEvaluation identity is invalid")
        return self


def expected_raw_artifact_path(job: CapabilityDevelopmentJob) -> str:
    suffix = job.job_id.split(":", 1)[-1]
    return f"{job.raw_namespace}/{suffix}.json"


def expected_result_artifact_path(job: CapabilityDevelopmentJob) -> str:
    suffix = job.job_id.split(":", 1)[-1]
    return f"{job.result_namespace}/{suffix}.json"


def expected_provider_artifact_ids(
    job: CapabilityDevelopmentJob,
    terminal_kind: TerminalKind,
) -> tuple[str, ...]:
    if terminal_kind not in {
        "provider_failure_no_payload",
        "privacy_rejection",
        "provider_identity_failure",
        "thinking_integrity_failure",
        "usage_integrity_failure",
    }:
        return ()
    return (
        canonical_hash(
            {"job_id": job.job_id, "terminal_kind": terminal_kind},
            prefix="capability_authoritative_provider_artifact_fixture:",
        ),
    )


def expected_transport_artifact_ids(
    job: CapabilityDevelopmentJob,
    terminal_kind: TerminalKind,
) -> tuple[str, ...]:
    if terminal_kind != "provider_transport_failure":
        return ()
    return (
        canonical_hash(
            {"job_id": job.job_id, "terminal_kind": terminal_kind},
            prefix="capability_authoritative_transport_artifact_fixture:",
        ),
    )


def _revalidate(model_type: type[BaseModel], value: BaseModel) -> Any:
    return model_type.model_validate(value.model_dump(mode="python", warnings=False))


def _derived_locus_fields(
    loci: Sequence[FailureLocus],
) -> tuple[str | None, str | None, str | None, str | None]:
    runtime_stages = {
        "action_abi",
        "action_reference",
        "state_precondition",
        "operation_support",
    }
    first_runtime = next(
        (item.locus_id for item in loci if item.stage in runtime_stages),
        None,
    )
    first_base = next(
        (item.locus_id for item in loci if item.stage in {"base_answer", "base_citation"}),
        None,
    )
    first_mechanism = next(
        (item.locus_id for item in loci if item.stage == "mechanism"),
        None,
    )
    terminal = loci[-1].locus_id if loci else None
    return first_runtime, first_base, first_mechanism, terminal


def validate_authoritative_bundle(
    *,
    job: CapabilityDevelopmentJob,
    manifest: CapabilityDevelopmentJobManifest,
    runner_id: str,
    registry: AuthoritativeTerminalRegistry,
    contract: AuthoritativeJobBoundOutcomeContract,
    raw: RawExecutionDescriptor,
    result: JobResultDescriptor,
    trace: JobBoundAttemptTrace,
    row: AuthoritativeCapabilityOutcomeRow,
    expected_evidence_kind: EvidenceKind,
) -> None:
    raw = cast(RawExecutionDescriptor, _revalidate(RawExecutionDescriptor, raw))
    result = cast(JobResultDescriptor, _revalidate(JobResultDescriptor, result))
    trace = cast(JobBoundAttemptTrace, _revalidate(JobBoundAttemptTrace, trace))
    row = cast(
        AuthoritativeCapabilityOutcomeRow,
        _revalidate(AuthoritativeCapabilityOutcomeRow, row),
    )
    policies = {item.terminal_kind: item for item in registry.policies}
    policy = policies[row.terminal_kind]
    component_sequences = {
        item.job_id: item.ordered_component_keys for item in contract.job_component_sequences
    }
    if set(component_sequences) != set(manifest.expected_job_ids):
        raise ValueError("Outcome Contract Component sequences cross the Manifest Job set")
    expected_job_values = (
        manifest.manifest_id,
        runner_id,
        job.execution_package_id,
        job.source_package_artifact_id,
        job.replica_index,
        job.raw_namespace,
    )
    observed_raw_values = (
        raw.manifest_id,
        raw.runner_id,
        raw.execution_package_id,
        raw.source_package_artifact_id,
        raw.replica_index,
        raw.raw_namespace,
    )
    if raw.job_id != job.job_id or observed_raw_values != expected_job_values:
        raise ValueError("Raw descriptor crosses the exact Manifest Job")
    if raw.evidence_kind != expected_evidence_kind:
        raise ValueError("Raw descriptor evidence kind differs from the evaluation")
    if raw.raw_artifact_path != expected_raw_artifact_path(job):
        raise ValueError("Raw descriptor path is not owned by the exact Job")
    if raw.payload.job_id != job.job_id or raw.payload.terminal_kind != row.terminal_kind:
        raise ValueError("Raw payload crosses its Job or terminal")
    if raw.payload.provider_artifact_ids != expected_provider_artifact_ids(
        job,
        row.terminal_kind,
    ) or raw.payload.transport_artifact_ids != expected_transport_artifact_ids(
        job,
        row.terminal_kind,
    ):
        raise ValueError("Raw payload artifact parents are not owned by the exact Job")
    expected_component_keys = component_sequences[job.job_id]
    observed_component_keys = tuple(item.component_key for item in raw.payload.component_attempts)
    if observed_component_keys != expected_component_keys[: len(observed_component_keys)]:
        raise ValueError("Raw Component attempt sequence crosses its frozen Package")
    completed_terminals = {
        "completed_qualified",
        "completed_invalid",
        "final_response_abi_invalid",
    }
    component_terminals = {
        "first_response_abi_invalid",
        "correction_response_abi_invalid",
        "first_action_reference_invalid",
        "correction_action_reference_invalid",
        "correction_attempt_typed_invalid",
        "measurement_support_exit",
    }
    if row.terminal_kind in completed_terminals:
        if (
            observed_component_keys != expected_component_keys
            or not all(item.committed for item in raw.payload.component_attempts)
            or any(item.terminal for item in raw.payload.component_attempts)
        ):
            raise ValueError("completed terminal lacks the exact committed Component sequence")
    elif row.terminal_kind in component_terminals:
        attempts = raw.payload.component_attempts
        if (
            not attempts
            or not attempts[-1].terminal
            or attempts[-1].terminal_kind != row.terminal_kind
            or any(not item.committed for item in attempts[:-1])
        ):
            raise ValueError("Component terminal lacks one exact terminal attempt")
    elif raw.payload.component_attempts:
        raise ValueError("outer terminal carries a Component attempt sequence")
    if (
        result.evidence_kind != expected_evidence_kind
        or result.job_id != job.job_id
        or result.raw_execution_id != raw.raw_execution_id
        or result.result_namespace != job.result_namespace
        or result.result_artifact_path != expected_result_artifact_path(job)
    ):
        raise ValueError("Result descriptor crosses the exact Raw or Job parent")
    if (
        result.payload.job_id != job.job_id
        or result.payload.raw_execution_id != raw.raw_execution_id
        or result.payload.terminal_kind != row.terminal_kind
    ):
        raise ValueError("Result payload crosses its authoritative parent")
    if (
        trace.evidence_kind != expected_evidence_kind
        or trace.job_id != job.job_id
        or trace.raw_execution_id != raw.raw_execution_id
        or trace.result_id != result.result_id
        or trace.terminal_kind != row.terminal_kind
        or trace.component_attempts != raw.payload.component_attempts
    ):
        raise ValueError("Job-bound AttemptTrace crosses Raw, Result, or attempt bytes")
    locus_ids = tuple(item.locus_id for item in trace.failure_loci)
    if result.payload.failure_locus_ids != locus_ids:
        raise ValueError("Result and AttemptTrace FailureLocus sets differ")
    allowed_locus_parents = {raw.raw_execution_id, result.result_id}
    if any(item.source_descriptor_id not in allowed_locus_parents for item in trace.failure_loci):
        raise ValueError("FailureLocus lacks an authoritative descriptor parent")
    row_job_values = (
        row.manifest_id,
        row.runner_id,
        row.execution_package_id,
        row.source_package_artifact_id,
        row.replica_index,
        row.raw_namespace,
    )
    if (
        row.evidence_kind != expected_evidence_kind
        or row.job_id != job.job_id
        or row_job_values != expected_job_values
        or row.result_namespace != job.result_namespace
        or row.raw_execution_id != raw.raw_execution_id
        or row.result_id != result.result_id
        or row.trace_id != trace.trace_id
        or row.correction_count != trace.correction_count
    ):
        raise ValueError("Outcome row crosses its exact descriptor DAG")
    result_values = (
        result.payload.task_completion,
        result.payload.task_verifier_invoked,
        result.payload.final_result_id,
        result.payload.final_base_valid,
        result.payload.final_mechanism_qualified,
        result.payload.final_qualified_valid,
    )
    row_values = (
        row.task_completion,
        row.task_verifier_invoked,
        row.final_result_id,
        row.final_base_valid,
        row.final_mechanism_qualified,
        row.final_qualified_valid,
    )
    if row_values != result_values:
        raise ValueError("Outcome row values are not reconstructed from JobResult")
    completed = row.terminal_kind in {"completed_qualified", "completed_invalid"}
    if completed != (row.final_result_id is not None):
        raise ValueError("terminal and Final Result identity policy differ")
    expected_policy_values = (
        policy.expected_task_completion,
        policy.expected_task_verifier_invoked,
        policy.expected_base_validity,
        policy.expected_mechanism_qualification,
        policy.expected_qualified_validity,
    )
    observed_policy_values = (
        row.task_completion,
        row.task_verifier_invoked,
        row.final_base_valid,
        row.final_mechanism_qualified,
        row.final_qualified_valid,
    )
    if observed_policy_values != expected_policy_values:
        raise ValueError("Outcome row differs from its exact terminal policy")
    if (
        row.first_runtime_uncommitted_locus_id,
        row.first_base_invalid_locus_id,
        row.first_mechanism_failed_locus_id,
        row.terminal_locus_id,
    ) != _derived_locus_fields(trace.failure_loci):
        raise ValueError("Outcome FailureLocus projections are not strictly derived")


def evaluate_exact_evidence_set(
    *,
    raws: Sequence[RawExecutionDescriptor],
    results: Sequence[JobResultDescriptor],
    traces: Sequence[JobBoundAttemptTrace],
    rows: Sequence[AuthoritativeCapabilityOutcomeRow],
    manifest: CapabilityDevelopmentJobManifest,
    registry: AuthoritativeTerminalRegistry,
    contract: AuthoritativeJobBoundOutcomeContract,
    runner_id: str,
    expected_evidence_kind: EvidenceKind,
) -> ExactEvidenceSetEvaluation:
    catalogs: tuple[tuple[str, Sequence[BaseModel]], ...] = (
        ("Raw", raws),
        ("Result", results),
        ("Trace", traces),
        ("Outcome", rows),
    )
    if any(len(items) != EXPECTED_JOB_COUNT for _, items in catalogs):
        raise ValueError("authoritative evidence catalog differs from the exact Manifest")
    if (
        contract.predecessor_manifest_id != manifest.manifest_id
        or contract.predecessor_runner_id != runner_id
        or contract.terminal_registry_id != registry.registry_id
    ):
        raise ValueError("authoritative Outcome Contract crosses its frozen parents")
    jobs = {item.job_id: item for item in manifest.jobs}
    expected_job_ids = set(manifest.expected_job_ids)
    for name, items in catalogs:
        observed = [cast(Any, item).job_id for item in items]
        if len(set(observed)) != EXPECTED_JOB_COUNT or set(observed) != expected_job_ids:
            raise ValueError(f"{name} catalog is not exactly one object per Manifest Job")
    raw_by_job = {item.job_id: item for item in raws}
    result_by_job = {item.job_id: item for item in results}
    trace_by_job = {item.job_id: item for item in traces}
    row_by_job = {item.job_id: item for item in rows}
    id_sets = (
        {item.raw_execution_id for item in raws},
        {item.result_id for item in results},
        {item.trace_id for item in traces},
        {item.row_id for item in rows},
    )
    if any(len(items) != EXPECTED_JOB_COUNT for items in id_sets):
        raise ValueError("authoritative evidence catalog repeats a content identity")
    for job_id in manifest.expected_job_ids:
        validate_authoritative_bundle(
            job=jobs[job_id],
            manifest=manifest,
            runner_id=runner_id,
            registry=registry,
            contract=contract,
            raw=raw_by_job[job_id],
            result=result_by_job[job_id],
            trace=trace_by_job[job_id],
            row=row_by_job[job_id],
            expected_evidence_kind=expected_evidence_kind,
        )
    q_first = sum(item.first_policy_qualified_valid for item in rows)
    q_bounded = sum(item.bounded_policy_qualified_valid for item in rows)
    terminal_counts = dict(sorted(Counter(item.terminal_kind for item in rows).items()))
    return cast(
        ExactEvidenceSetEvaluation,
        make_identity_model(
            ExactEvidenceSetEvaluation,
            {
                "contract_id": contract.contract_id,
                "manifest_id": manifest.manifest_id,
                "registry_id": registry.registry_id,
                "evidence_kind": expected_evidence_kind,
                "terminal_kind_counts": terminal_counts,
                "q_first_numerator": q_first,
                "q_bounded_correction_numerator": q_bounded,
                "q_first_fraction": f"{q_first}/192",
                "q_bounded_correction_fraction": f"{q_bounded}/192",
                "empirical": expected_evidence_kind == "empirical_execution",
            },
            field="evaluation_id",
            prefix="capability_authoritative_exact_evidence_set_evaluation:",
        ),
    )


__all__ = [
    "AUTHORITATIVE_JOB_BOUND_OUTCOME_VERSION",
    "AuthoritativeCapabilityOutcomeRow",
    "AuthoritativeJobBoundOutcomeContract",
    "AuthoritativeTerminalPolicy",
    "AuthoritativeTerminalRegistry",
    "ComponentAttemptEvidence",
    "EvidenceKind",
    "ExactEvidenceSetEvaluation",
    "FailureEvaluability",
    "FailureLocus",
    "FailureStage",
    "JobBoundAttemptTrace",
    "JobComponentSequence",
    "JobResultDescriptor",
    "JobResultEvidencePayload",
    "RawExecutionDescriptor",
    "RawExecutionEvidencePayload",
    "TerminalKind",
    "TerminalExclusionWitness",
    "TerminalRegistrationStatus",
    "evaluate_exact_evidence_set",
    "expected_provider_artifact_ids",
    "expected_raw_artifact_path",
    "expected_result_artifact_path",
    "expected_transport_artifact_ids",
    "identity",
    "make_identity_model",
    "validate_authoritative_bundle",
]
