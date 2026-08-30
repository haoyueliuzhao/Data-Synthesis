from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.capability_observation import (
    CapabilityFamily,
    ObservationDepth,
)
from trusted_synthesis.hashing import canonical_hash

JOB_BOUND_MULTISTEP_OUTCOME_VERSION: Final = "job_bound_multistep_outcome_contract.v1"
EXPECTED_DEVELOPMENT_PACKAGE_COUNT: Final = 32
EXPECTED_REPLICA_COUNT: Final = 6
EXPECTED_DEVELOPMENT_JOB_COUNT: Final = 192

CorrectionActionRelation = Literal[
    "reference",
    "valid_nonreference",
    "same_current_invalid",
    "different_current_invalid",
    "stale_action",
    "foreign_or_unbound_action",
]
CorrectionTerminalReason = Literal[
    "correction_response_abi_invalid",
    "correction_attempt_typed_invalid",
    "correction_action_reference_invalid",
]
EndpointKind = Literal[
    "completed_qualified",
    "completed_invalid",
    "first_response_abi_invalid",
    "correction_response_abi_invalid",
    "correction_attempt_typed_invalid",
    "correction_action_reference_invalid",
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


class FrozenGenerationProfile(FrozenModel):
    profile_id: str = Field(min_length=1)
    source_development_catalog_id: str = Field(min_length=1)
    source_nuisance_signature_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    prompt_contract_id: str = Field(min_length=1)
    action_grammar_id: str = Field(min_length=1)
    final_grammar_id: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    thinking_policy_id: str = Field(min_length=1)
    bounded_generation_policy_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    action_response_decision_kind: Literal["execute_public_operation"] = "execute_public_operation"
    profile_changed_from_frozen_source: Literal[False] = False
    schema_version: str = JOB_BOUND_MULTISTEP_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_profile(self) -> FrozenGenerationProfile:
        if len(set(self.source_nuisance_signature_ids)) != 8:
            raise ValueError("generation profile does not bind eight unique nuisance signatures")
        if self.profile_id != identity(
            self,
            "profile_id",
            "capability_job_bound_generation_profile:",
        ):
            raise ValueError("job-bound generation profile identity is invalid")
        return self


class JobBoundMultistepOutcomeContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    package_count: Literal[32] = EXPECTED_DEVELOPMENT_PACKAGE_COUNT
    replica_count: Literal[6] = EXPECTED_REPLICA_COUNT
    job_count: Literal[192] = EXPECTED_DEVELOPMENT_JOB_COUNT
    correction_attempt_bound_per_component: Literal[1] = 1
    multiple_components_may_each_invoke_correction: Literal[True] = True
    ordered_component_attempts_required: Literal[True] = True
    first_policy_definition: Literal["complete_job_qualified_with_zero_component_corrections"] = (
        "complete_job_qualified_with_zero_component_corrections"
    )
    bounded_policy_definition: Literal[
        "complete_job_qualified_under_one_correction_per_reached_component"
    ] = "complete_job_qualified_under_one_correction_per_reached_component"
    first_action_is_not_job_first_policy_estimand: Literal[True] = True
    abi_invalid_action_acceptance_evaluable: Literal[False] = False
    abi_invalid_action_accepted: Literal[False] = False
    abi_invalid_verifier_fields_are_null: Literal[True] = True
    empirical_row_requires_job_and_manifest: Literal[True] = True
    empirical_row_requires_raw_and_result_identity: Literal[True] = True
    fixture_row_promotable_to_empirical: Literal[False] = False
    exact_manifest_job_set_required: Literal[True] = True
    missing_duplicate_extra_jobs_allowed: Literal[False] = False
    q_first_formula: Literal["sum(first_policy_qualified_valid)/exact_manifest_job_count"] = (
        "sum(first_policy_qualified_valid)/exact_manifest_job_count"
    )
    q_bounded_correction_formula: Literal[
        "sum(bounded_policy_qualified_valid)/exact_manifest_job_count"
    ] = "sum(bounded_policy_qualified_valid)/exact_manifest_job_count"
    schema_version: str = JOB_BOUND_MULTISTEP_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> JobBoundMultistepOutcomeContract:
        if self.package_count * self.replica_count != self.job_count:
            raise ValueError("job-bound Outcome Contract denominator geometry changed")
        if self.contract_id != identity(
            self,
            "contract_id",
            "capability_job_bound_multistep_outcome_contract:",
        ):
            raise ValueError("job-bound multistep Outcome Contract identity is invalid")
        return self


class CapabilityDevelopmentJob(FrozenModel):
    job_id: str = Field(min_length=1)
    runner_package_id: str = Field(min_length=1)
    execution_package_id: str = Field(min_length=1)
    authoritative_package_artifact_id: str = Field(min_length=1)
    source_package_artifact_id: str = Field(min_length=1)
    source_package_id: str = Field(min_length=1)
    source_group_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    fixed_generation_condition_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    schedule_ids: tuple[str, ...] = Field(min_length=1, max_length=4)
    generation_profile_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    public_feedback_contract_id: str = Field(min_length=1)
    typed_rejection_surface_contract_id: str = Field(min_length=1)
    raw_namespace: str = Field(min_length=1)
    result_namespace: str = Field(min_length=1)
    deterministic_seed_id: str = Field(min_length=1)
    schema_version: str = JOB_BOUND_MULTISTEP_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_job(self) -> CapabilityDevelopmentJob:
        if len(self.schedule_ids) != len(set(self.schedule_ids)):
            raise ValueError("Development Job repeats a State-local Schedule")
        if self.job_id != identity(
            self,
            "job_id",
            "capability_job_bound_development_job:",
        ):
            raise ValueError("Development Job identity is invalid")
        return self


class CapabilityDevelopmentJobManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    source_runner_catalog_id: str = Field(min_length=1)
    source_development_catalog_id: str = Field(min_length=1)
    generation_profile_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    jobs: tuple[CapabilityDevelopmentJob, ...] = Field(min_length=192, max_length=192)
    expected_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    package_count: Literal[32] = EXPECTED_DEVELOPMENT_PACKAGE_COUNT
    replica_count: Literal[6] = EXPECTED_REPLICA_COUNT
    job_count: Literal[192] = EXPECTED_DEVELOPMENT_JOB_COUNT
    missing_job_count: Literal[0] = 0
    duplicate_job_count: Literal[0] = 0
    extra_job_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_model_outcome_count: Literal[0] = 0
    schema_version: str = JOB_BOUND_MULTISTEP_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> CapabilityDevelopmentJobManifest:
        if len(self.jobs) != self.job_count:
            raise ValueError("Development Manifest Job denominator changed")
        job_ids = tuple(item.job_id for item in self.jobs)
        if len(set(job_ids)) != self.job_count:
            raise ValueError("Development Manifest repeats a Job identity")
        if self.expected_job_ids != tuple(sorted(job_ids)):
            raise ValueError("Development Manifest expected Job set changed")
        if len({item.raw_namespace for item in self.jobs}) != self.job_count:
            raise ValueError("Development Manifest repeats a Raw namespace")
        if len({item.result_namespace for item in self.jobs}) != self.job_count:
            raise ValueError("Development Manifest repeats a Result namespace")
        if any(
            item.generation_profile_id != self.generation_profile_id
            or item.outcome_contract_id != self.outcome_contract_id
            for item in self.jobs
        ):
            raise ValueError("Development Manifest Job crosses a frozen Contract")
        package_replicas = Counter(
            (item.runner_package_id, item.replica_index) for item in self.jobs
        )
        if len(package_replicas) != self.job_count or any(
            count != 1 for count in package_replicas.values()
        ):
            raise ValueError("Development Manifest package x Replica cells are not unique")
        package_ids = {item.runner_package_id for item in self.jobs}
        if len(package_ids) != self.package_count:
            raise ValueError("Development Manifest Package denominator changed")
        if any(
            {item.replica_index for item in self.jobs if item.runner_package_id == package_id}
            != set(range(self.replica_count))
            for package_id in package_ids
        ):
            raise ValueError("Development Manifest Package lacks an exact six-Replica set")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            "capability_job_bound_development_manifest:",
        ):
            raise ValueError("Development Manifest identity is invalid")
        return self


class ComponentAttemptOutcome(FrozenModel):
    attempt_id: str = Field(min_length=1)
    component_index: int = Field(ge=0, le=3)
    component_key: str = Field(min_length=1)
    reached_state_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    first_response_abi_valid: bool
    first_action_acceptance_evaluable: bool
    first_action_id: str | None = None
    first_action_state_precondition_valid: bool | None = None
    first_action_accepted: bool
    first_rejection_code: str | None = None
    first_observation_receipt_id: str | None = None
    correction_invoked: bool
    correction_feedback_id: str | None = None
    correction_response_abi_valid: bool | None = None
    corrected_action_id: str | None = None
    corrected_action_relation: CorrectionActionRelation | None = None
    corrected_action_acceptance_evaluable: bool | None = None
    corrected_action_accepted: bool | None = None
    correction_observation_receipt_id: str | None = None
    correction_terminal_reason: CorrectionTerminalReason | None = None
    committed: bool
    terminal: bool
    schema_version: str = JOB_BOUND_MULTISTEP_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_attempt(self) -> ComponentAttemptOutcome:
        if not self.first_response_abi_valid:
            if (
                self.first_action_acceptance_evaluable
                or self.first_action_id is not None
                or self.first_action_state_precondition_valid is not None
                or self.first_action_accepted
                or self.first_rejection_code is not None
                or self.first_observation_receipt_id is not None
                or self.correction_invoked
                or self.committed
                or not self.terminal
            ):
                raise ValueError("ABI-invalid first response contains Action acceptance")
        else:
            if (
                not self.first_action_acceptance_evaluable
                or self.first_action_id is None
                or self.first_action_state_precondition_valid is None
            ):
                raise ValueError("ABI-valid first response lacks Action acceptance")
            if self.first_action_accepted:
                if (
                    not self.first_action_state_precondition_valid
                    or self.first_rejection_code is not None
                    or self.first_observation_receipt_id is None
                    or self.correction_invoked
                    or not self.committed
                    or self.terminal
                ):
                    raise ValueError("accepted first Action has inconsistent attempt lineage")
            elif (
                self.first_action_state_precondition_valid
                or self.first_rejection_code is None
                or self.first_observation_receipt_id is None
                or not self.correction_invoked
            ):
                raise ValueError("typed-rejected first Action lacks bounded correction")
        correction_fields = (
            self.correction_feedback_id,
            self.correction_response_abi_valid,
            self.corrected_action_id,
            self.corrected_action_relation,
            self.corrected_action_acceptance_evaluable,
            self.corrected_action_accepted,
            self.correction_observation_receipt_id,
            self.correction_terminal_reason,
        )
        if not self.correction_invoked:
            if any(item is not None for item in correction_fields):
                raise ValueError("non-correction Component carries correction fields")
        else:
            if self.correction_feedback_id is None or self.correction_response_abi_valid is None:
                raise ValueError("bounded correction lacks public Feedback or ABI disposition")
            if not self.correction_response_abi_valid:
                if (
                    self.corrected_action_id is not None
                    or self.corrected_action_relation is not None
                    or self.corrected_action_acceptance_evaluable
                    or self.corrected_action_accepted
                    or self.correction_observation_receipt_id is not None
                    or self.correction_terminal_reason != "correction_response_abi_invalid"
                    or self.committed
                    or not self.terminal
                ):
                    raise ValueError("ABI-invalid correction contains Action acceptance")
            else:
                if (
                    self.corrected_action_id is None
                    or self.corrected_action_relation is None
                    or self.corrected_action_accepted is None
                ):
                    raise ValueError("ABI-valid correction lacks Action acceptance")
                reference_invalid = self.corrected_action_relation in {
                    "stale_action",
                    "foreign_or_unbound_action",
                }
                if reference_invalid != (self.corrected_action_acceptance_evaluable is False):
                    raise ValueError(
                        "correction Action-reference class and acceptance evaluability differ"
                    )
                if self.corrected_action_accepted:
                    if (
                        self.corrected_action_relation not in {"reference", "valid_nonreference"}
                        or self.corrected_action_acceptance_evaluable is not True
                        or self.correction_observation_receipt_id is None
                        or self.correction_terminal_reason is not None
                        or not self.committed
                        or self.terminal
                    ):
                        raise ValueError("accepted correction has inconsistent commit lineage")
                else:
                    if (
                        self.corrected_action_relation in {"reference", "valid_nonreference"}
                        or self.correction_terminal_reason is None
                        or self.committed
                        or not self.terminal
                    ):
                        raise ValueError("failed correction lacks an exact terminal lineage")
                    typed = self.corrected_action_relation in {
                        "same_current_invalid",
                        "different_current_invalid",
                    }
                    if typed and self.corrected_action_acceptance_evaluable is not True:
                        raise ValueError("typed-invalid correction was not acceptance-evaluable")
                    if typed != (
                        self.correction_terminal_reason == "correction_attempt_typed_invalid"
                    ):
                        raise ValueError("correction terminal class and reason differ")
                    if typed != (self.correction_observation_receipt_id is not None):
                        raise ValueError("typed correction terminal lacks its Observation")
        if self.attempt_id != identity(
            self,
            "attempt_id",
            "capability_component_attempt_outcome:",
        ):
            raise ValueError("Component attempt Outcome identity is invalid")
        return self


class JobBoundOutcomePayload(FrozenModel):
    attempt_trace_id: str = Field(min_length=1)
    component_attempts: tuple[ComponentAttemptOutcome, ...] = Field(
        min_length=1,
        max_length=4,
    )
    reached_component_count: int = Field(ge=1, le=4)
    committed_component_count: int = Field(ge=0, le=4)
    correction_count: int = Field(ge=0, le=4)
    correction_feedback_ids: tuple[str, ...]
    first_failed_component_key: str | None = None
    first_policy_qualified_valid: bool
    bounded_policy_endpoint_complete: bool
    task_verifier_invoked: bool
    final_response_abi_valid: bool | None = None
    final_result_id: str | None = None
    final_base_valid: bool | None = None
    final_mechanism_qualified: bool | None = None
    final_qualified_valid: bool | None = None
    bounded_policy_qualified_valid: bool
    endpoint_kind: EndpointKind
    schema_version: str = JOB_BOUND_MULTISTEP_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_payload(self) -> JobBoundOutcomePayload:
        attempts = self.component_attempts
        if tuple(item.component_index for item in attempts) != tuple(range(len(attempts))):
            raise ValueError("Component attempt trace is not contiguous")
        if len({item.component_key for item in attempts}) != len(attempts):
            raise ValueError("Component attempt trace repeats a Component")
        terminals = tuple(index for index, item in enumerate(attempts) if item.terminal)
        if terminals and terminals != (len(attempts) - 1,):
            raise ValueError("Component attempt trace continues after a terminal")
        feedback_ids = tuple(
            item.correction_feedback_id
            for item in attempts
            if item.correction_feedback_id is not None
        )
        if self.reached_component_count != len(attempts):
            raise ValueError("reached Component count differs from the attempt trace")
        if self.committed_component_count != sum(item.committed for item in attempts):
            raise ValueError("committed Component count differs from the attempt trace")
        if self.correction_count != sum(item.correction_invoked for item in attempts):
            raise ValueError("correction count differs from the attempt trace")
        if self.correction_feedback_ids != feedback_ids:
            raise ValueError("ordered correction Feedback lineage differs from attempts")
        expected_failed = next(
            (item.component_key for item in attempts if not item.committed),
            None,
        )
        if expected_failed is not None and self.first_failed_component_key != expected_failed:
            raise ValueError("first failed Component differs from the terminal attempt")
        final_fields = (
            self.final_response_abi_valid,
            self.final_result_id,
            self.final_base_valid,
            self.final_mechanism_qualified,
            self.final_qualified_valid,
        )
        if self.task_verifier_invoked:
            if any(item is None for item in final_fields):
                raise ValueError("completed Outcome lacks Final or Verifier fields")
            expected_qualified = bool(self.final_base_valid and self.final_mechanism_qualified)
            if self.final_qualified_valid != expected_qualified:
                raise ValueError("final Qualified validity is not its exact conjunction")
            if self.bounded_policy_qualified_valid != bool(self.final_qualified_valid):
                raise ValueError("bounded-policy Qualified value differs from final validity")
            if not self.bounded_policy_endpoint_complete:
                raise ValueError("Verifier-invoked Outcome is not a complete endpoint")
            expected_endpoint = "completed_qualified" if expected_qualified else "completed_invalid"
            if self.endpoint_kind != expected_endpoint:
                raise ValueError("completed endpoint kind differs from final validity")
            if not all(item.committed for item in attempts):
                raise ValueError("completed Outcome contains an uncommitted Component")
        else:
            if any(item is not None for item in final_fields):
                raise ValueError("unevaluable terminal contains Final or Verifier values")
            if self.bounded_policy_qualified_valid:
                raise ValueError("unevaluable terminal is bounded-policy Qualified")
            if not self.bounded_policy_endpoint_complete:
                raise ValueError("typed policy terminal is not a complete policy endpoint")
            terminal = attempts[-1]
            expected_terminal_endpoint: EndpointKind
            if not terminal.first_response_abi_valid:
                expected_terminal_endpoint = "first_response_abi_invalid"
            elif terminal.correction_terminal_reason is None:
                raise ValueError("unevaluable terminal lacks a terminal reason")
            else:
                expected_terminal_endpoint = terminal.correction_terminal_reason
            if self.endpoint_kind != expected_terminal_endpoint:
                raise ValueError("typed endpoint kind differs from terminal lineage")
        expected_first = bool(self.final_qualified_valid is True and self.correction_count == 0)
        if self.first_policy_qualified_valid != expected_first:
            raise ValueError("first-policy Qualified value is not zero-correction Job success")
        if self.first_policy_qualified_valid and not self.bounded_policy_qualified_valid:
            raise ValueError("first-policy success is absent under the bounded policy")
        if self.attempt_trace_id != identity(
            self,
            "attempt_trace_id",
            "capability_job_attempt_trace:",
        ):
            raise ValueError("Job attempt trace identity is invalid")
        return self


class ScriptedPreflightOutcomeRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    execution_package_id: str = Field(min_length=1)
    source_package_artifact_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    attempt_trace_id: str = Field(min_length=1)
    raw_namespace: str = Field(min_length=1)
    result_namespace: str = Field(min_length=1)
    raw_execution_id: Literal[None] = None
    result_id: Literal[None] = None
    scenario: str = Field(min_length=1)
    exact_manifest_denominator_member: bool
    outcome: JobBoundOutcomePayload
    empirical: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = JOB_BOUND_MULTISTEP_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> ScriptedPreflightOutcomeRow:
        if self.attempt_trace_id != self.outcome.attempt_trace_id:
            raise ValueError("scripted Outcome row crosses its attempt trace")
        if self.exact_manifest_denominator_member != (
            self.scenario == "exact_manifest_reference_preflight"
        ):
            raise ValueError("scripted Outcome denominator membership is mislabeled")
        if self.row_id != identity(
            self,
            "row_id",
            "capability_scripted_preflight_outcome_row:",
        ):
            raise ValueError("scripted preflight Outcome row identity is invalid")
        return self


class EmpiricalCapabilityOutcomeRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    execution_package_id: str = Field(min_length=1)
    source_package_artifact_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    attempt_trace_id: str = Field(min_length=1)
    raw_namespace: str = Field(min_length=1)
    result_namespace: str = Field(min_length=1)
    raw_execution_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    outcome: JobBoundOutcomePayload
    empirical: Literal[True] = True
    job_eligible: Literal[True] = True
    eligibility_exclusion_reason: Literal[None] = None
    schema_version: str = JOB_BOUND_MULTISTEP_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> EmpiricalCapabilityOutcomeRow:
        if self.attempt_trace_id != self.outcome.attempt_trace_id:
            raise ValueError("empirical Outcome row crosses its attempt trace")
        if self.row_id != identity(
            self,
            "row_id",
            "capability_empirical_job_bound_outcome_row:",
        ):
            raise ValueError("empirical Job-bound Outcome row identity is invalid")
        return self


class CapabilityEstimandEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    eligible_job_count: Literal[192] = EXPECTED_DEVELOPMENT_JOB_COUNT
    q_first_numerator: int = Field(ge=0, le=192)
    q_bounded_correction_numerator: int = Field(ge=0, le=192)
    q_first_fraction: str = Field(pattern=r"^[0-9]+/192$")
    q_bounded_correction_fraction: str = Field(pattern=r"^[0-9]+/192$")
    exact_job_set_match: Literal[True] = True
    missing_job_count: Literal[0] = 0
    duplicate_job_count: Literal[0] = 0
    extra_job_count: Literal[0] = 0
    first_and_bounded_outcomes_pooled: Literal[False] = False
    empirical: Literal[True] = True
    schema_version: str = JOB_BOUND_MULTISTEP_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_evaluation(self) -> CapabilityEstimandEvaluation:
        if self.q_first_numerator > self.q_bounded_correction_numerator:
            raise ValueError("first-policy success exceeds bounded-correction success")
        if self.q_first_fraction != f"{self.q_first_numerator}/192":
            raise ValueError("q_first fraction is inconsistent")
        if self.q_bounded_correction_fraction != (f"{self.q_bounded_correction_numerator}/192"):
            raise ValueError("q_bounded fraction is inconsistent")
        if self.evaluation_id != identity(
            self,
            "evaluation_id",
            "capability_job_bound_estimand_evaluation:",
        ):
            raise ValueError("Job-bound estimand evaluation identity is invalid")
        return self


class JobBoundRunnerContract(FrozenModel):
    runner_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    source_runner_catalog_id: str = Field(min_length=1)
    generation_profile_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    public_feedback_contract_id: str = Field(min_length=1)
    one_current_prompt_at_a_time: Literal[True] = True
    reference_trace_input_allowed: Literal[False] = False
    precommitted_choice_vector_allowed: Literal[False] = False
    future_prompt_materialization_allowed: Literal[False] = False
    complete_baseline_loading_allowed: Literal[False] = False
    outcome_projection_must_use_actual_trace: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    sealed_confirmation_access_authorized: Literal[False] = False
    schema_version: str = JOB_BOUND_MULTISTEP_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_runner(self) -> JobBoundRunnerContract:
        if self.runner_id != identity(
            self,
            "runner_id",
            "capability_job_bound_multistep_runner_contract:",
        ):
            raise ValueError("Job-bound Runner Contract identity is invalid")
        return self


def evaluate_empirical_capability_estimands(
    rows: Sequence[EmpiricalCapabilityOutcomeRow],
    *,
    manifest: CapabilityDevelopmentJobManifest,
) -> CapabilityEstimandEvaluation:
    if any(not isinstance(item, EmpiricalCapabilityOutcomeRow) for item in rows):
        raise ValueError("fixture or scripted row cannot enter the empirical estimator")
    if len(rows) != manifest.job_count:
        raise ValueError("empirical Outcome denominator differs from the exact Manifest")
    row_ids = tuple(item.row_id for item in rows)
    if len(set(row_ids)) != len(row_ids):
        raise ValueError("empirical Outcome denominator repeats an Outcome row")
    observed_job_ids = tuple(item.job_id for item in rows)
    if len(set(observed_job_ids)) != len(observed_job_ids):
        raise ValueError("empirical Outcome denominator repeats a Job")
    if tuple(sorted(observed_job_ids)) != manifest.expected_job_ids:
        raise ValueError("empirical Outcome denominator is not the exact Manifest Job set")
    jobs = {item.job_id: item for item in manifest.jobs}
    for row in rows:
        job = jobs[row.job_id]
        if (
            row.manifest_id != manifest.manifest_id
            or row.execution_package_id != job.execution_package_id
            or row.source_package_artifact_id != job.source_package_artifact_id
            or row.replica_index != job.replica_index
            or row.raw_namespace != job.raw_namespace
            or row.result_namespace != job.result_namespace
        ):
            raise ValueError("empirical Outcome row crosses an exact Job parent")
    q_first = sum(item.outcome.first_policy_qualified_valid for item in rows)
    q_bounded = sum(item.outcome.bounded_policy_qualified_valid for item in rows)
    values = {
        "manifest_id": manifest.manifest_id,
        "q_first_numerator": q_first,
        "q_bounded_correction_numerator": q_bounded,
        "q_first_fraction": f"{q_first}/192",
        "q_bounded_correction_fraction": f"{q_bounded}/192",
    }
    return make_identity_model(
        CapabilityEstimandEvaluation,
        values,
        field="evaluation_id",
        prefix="capability_job_bound_estimand_evaluation:",
    )


__all__ = [
    "CapabilityDevelopmentJob",
    "CapabilityDevelopmentJobManifest",
    "CapabilityEstimandEvaluation",
    "ComponentAttemptOutcome",
    "CorrectionActionRelation",
    "CorrectionTerminalReason",
    "EmpiricalCapabilityOutcomeRow",
    "EndpointKind",
    "EXPECTED_DEVELOPMENT_JOB_COUNT",
    "EXPECTED_DEVELOPMENT_PACKAGE_COUNT",
    "EXPECTED_REPLICA_COUNT",
    "FrozenGenerationProfile",
    "JOB_BOUND_MULTISTEP_OUTCOME_VERSION",
    "JobBoundMultistepOutcomeContract",
    "JobBoundOutcomePayload",
    "JobBoundRunnerContract",
    "ScriptedPreflightOutcomeRow",
    "evaluate_empirical_capability_estimands",
    "identity",
    "make_identity_model",
]
