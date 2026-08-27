from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.evaluation.bounded_policy_endpoint import (
    BoundedPolicyEndpointGenerationPolicy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_frequency_preflight_models import (  # noqa: E501
    FrequencyManifest,
    FreshFrequencySourcePopulation,
    FreshnessChannelRow,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return strict_canonical_hash(value.model_dump(mode="python", exclude={field}), prefix=prefix)


class FileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    source_kind: str = Field(min_length=1)


class PredecessorReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    predecessor_report_sha256: str = Field(min_length=64, max_length=64)
    predecessor_route_b_decision_id: str = Field(min_length=1)
    predecessor_next_permitted_stage: Literal[
        "fresh_bounded_policy_endpoint_frequency_preflight_only"
    ] = "fresh_bounded_policy_endpoint_frequency_preflight_only"
    predecessor_direct_output_count: Literal[9] = 9
    predecessor_rebuilt_output_count: Literal[9] = 9
    predecessor_byte_match_count: Literal[9] = 9
    file_bindings: tuple[FileBinding, ...] = Field(min_length=1)
    current_stage_input_file_count: int = Field(ge=1)
    v26_158_full_transitive_rebuild_claimed: Literal[False] = False
    historical_snapshot_limitation_preserved: Literal[True] = True
    migrated_checkout_snapshot_available: Literal[False] = False
    external_recovered_snapshot_available: Literal[True] = True
    external_recovered_snapshot_path: str = Field(min_length=1)
    external_recovered_snapshot_sha256: str = Field(min_length=64, max_length=64)
    external_recovered_snapshot_byte_count: Literal[604998387] = 604_998_387
    credential_lookup_attempted: Literal[False] = False
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorReplayAudit:
        paths = tuple(item.relative_path for item in self.file_bindings)
        if (
            paths != tuple(sorted(set(paths)))
            or self.current_stage_input_file_count != len(self.file_bindings)
            or self.audit_id
            != identity(
                self,
                "audit_id",
                "finance_v26_bounded_policy_predecessor_replay:",
            )
        ):
            raise ValueError("v26.163 predecessor replay changed")
        return self


class RouteBSourceSelectionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_replay_audit_id: str = Field(min_length=1)
    source_frame_population_id: str = Field(min_length=1)
    source_population_id: str = Field(min_length=1)
    source_selection_salt: str = Field(min_length=1)
    prior_population_count: Literal[4] = 4
    exclusion_registry_task_count: Literal[48] = 48
    exclusion_overlap_with_frame: int = Field(ge=0)
    frame_candidate_count_before_exclusion: int = Field(ge=70)
    frame_candidate_count_after_exclusion: int = Field(ge=12)
    selected_task_count: Literal[12] = 12
    prior_historical_excluded_evidence_count: Literal[27173] = 27_173
    prior_population_evidence_count: int = Field(ge=1)
    effective_excluded_evidence_count: int = Field(gt=27173)
    external_recovered_snapshot_used_for_source_construction: Literal[True] = True
    freshness_channels: tuple[FreshnessChannelRow, ...] = Field(min_length=8, max_length=8)
    source_selection_before_policy_mapper_path_resource_or_outcome_load: Literal[True] = True
    compatibility_results_used_for_selection: Literal[False] = False
    model_outcomes_used_for_selection: Literal[False] = False
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> RouteBSourceSelectionAudit:
        channels = tuple(item.channel for item in self.freshness_channels)
        if (
            channels != tuple(sorted(set(channels)))
            or any(item.overlap_count for item in self.freshness_channels)
            or self.exclusion_overlap_with_frame > self.frame_candidate_count_before_exclusion
            or self.frame_candidate_count_after_exclusion
            > self.frame_candidate_count_before_exclusion
            or self.effective_excluded_evidence_count
            != self.prior_historical_excluded_evidence_count + self.prior_population_evidence_count
            or self.audit_id
            != identity(
                self,
                "audit_id",
                "finance_v26_bounded_policy_source_selection:",
            )
        ):
            raise ValueError("v26.163 Route B source selection changed")
        return self


class BoundedPolicyEstimandContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    task_condition_cell_catalog_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    frequency_assignment_contract_id: str = Field(min_length=1)
    q_estimand: Literal["q_c=P_gbounded(V_qualified=1|x,c)"] = "q_c=P_gbounded(V_qualified=1|x,c)"
    pi_estimand: Literal["pi_c(z)=P_gbounded(z|x,c,V_qualified=1)"] = (
        "pi_c(z)=P_gbounded(z|x,c,V_qualified=1)"
    )
    q_estimator: Literal["q_hat_c=N_qualified_c/N_total_c"] = "q_hat_c=N_qualified_c/N_total_c"
    pi_estimator: Literal["pi_hat_c(z)=N_c_z/N_qualified_c_when_N_qualified_c_gt_0"] = (
        "pi_hat_c(z)=N_c_z/N_qualified_c_when_N_qualified_c_gt_0"
    )
    global_gate_scope: Literal[
        "raw_instrument_resource_privacy_model_identity_thinking_usage_transport_integrity"
    ] = "raw_instrument_resource_privacy_model_identity_thinking_usage_transport_integrity"
    cell_gate_scope: Literal["fixed_complete_bounded_policy_endpoint_denominator"] = (
        "fixed_complete_bounded_policy_endpoint_denominator"
    )
    cell_is_independent_estimand: Literal[True] = True
    outcome_dependent_cell_selection_allowed: Literal[False] = False
    unconditional_and_conditioned_denominators_separate: Literal[True] = True
    conditioned_paths_have_independent_denominators: Literal[True] = True
    paths_can_be_pooled: Literal[False] = False
    task_is_primary_statistical_unit: Literal[True] = True
    rollouts_are_secondary_repeated_measures: Literal[True] = True
    q_uncertainty_method: Literal["wilson_score_95_percent"] = "wilson_score_95_percent"
    pi_uncertainty_method: Literal["marginal_wilson_score_95_percent"] = (
        "marginal_wilson_score_95_percent"
    )
    simultaneous_multinomial_coverage_claimed: Literal[False] = False
    minimum_qualified_rows_for_pi: Literal[1] = 1
    minimum_qualified_rows_for_empirical_non_degeneracy: Literal[2] = 2
    minimum_distinct_states_for_empirical_non_degeneracy: Literal[2] = 2
    zero_qualified_cell_q_is_zero_with_interval: Literal[True] = True
    zero_qualified_cell_pi_is_null: Literal[True] = True
    zero_vector_or_state_imputation_allowed: Literal[False] = False
    stable_population_probability_claimed: Literal[False] = False
    unrestricted_natural_agent_distribution_claimed: Literal[False] = False
    empirical_route_signature_conditioning_allowed: Literal[False] = False
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> BoundedPolicyEstimandContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "finance_v26_bounded_policy_estimand_contract:",
        ):
            raise ValueError("v26.163 bounded-policy Estimand Contract changed")
        return self


class BoundedPolicyOutcomeContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    estimand_contract_id: str = Field(min_length=1)
    assignment_contract_id: str = Field(min_length=1)
    exact_denominator: Literal[360] = 360
    global_integrity_gate: tuple[str, ...] = (
        "bounded_policy_endpoint_360_of_360",
        "complete_raw_360_of_360",
        "privacy_failure_zero",
        "provider_identity_thinking_usage_failure_zero",
        "raw_instrument_failure_zero",
        "resource_accounting_failure_zero",
        "unresolved_transport_failure_zero",
        "unsupported_measurement_exit_zero",
    )
    cell_endpoint_gate: tuple[str, ...] = (
        "conditioned_cell_endpoint_6_of_6",
        "unconditional_cell_endpoint_12_of_12",
    )
    ordinary_detour_limit_is_policy_horizon: Literal[True] = True
    policy_horizon_is_complete_failure_endpoint: Literal[True] = True
    policy_horizon_is_measurement_support_exit: Literal[False] = False
    policy_horizon_is_model_semantic_error: Literal[False] = False
    valid_only_mapping_requires_qualified_true: Literal[True] = True
    q_reported_for_complete_zero_qualified_cell: Literal[True] = True
    pi_null_for_zero_qualified_cell: Literal[True] = True
    independent_postrun_audit_required: Literal[True] = True
    preflight_formal_assignment_count: Literal[0] = 0
    preflight_frequency_report_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> BoundedPolicyOutcomeContract:
        if (
            self.global_integrity_gate != tuple(sorted(set(self.global_integrity_gate)))
            or self.cell_endpoint_gate != tuple(sorted(set(self.cell_endpoint_gate)))
            or self.contract_id
            != identity(
                self,
                "contract_id",
                "finance_v26_bounded_policy_outcome_contract:",
            )
        ):
            raise ValueError("v26.163 bounded-policy Outcome Contract changed")
        return self


class BoundedPolicyRunnerContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    estimand_contract_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    endpoint_adapter_implementation_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    mapper_protocol_id: str = Field(min_length=1)
    mapper_contract_id: str = Field(min_length=1)
    frequency_assignment_contract_id: str = Field(min_length=1)
    task_condition_cell_catalog_id: str = Field(min_length=1)
    tool_schema_closure_audit_id: str = Field(min_length=1)
    independent_reference_mapper_implementation_id: str = Field(min_length=1)
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    exact_final_response_grammar_id: str = Field(min_length=1)
    joint_support_validity_contract_id: str = Field(min_length=1)
    qualified_final_grammar_id: str = Field(min_length=1)
    runner_run_id: str = Field(min_length=1)
    execution_run_id: str = Field(min_length=1)
    exact_job_denominator: Literal[360] = 360
    maximum_primary_stage_one_requests: Literal[21] = 21
    maximum_stage_one_provider_calls: Literal[23] = 23
    maximum_transport_inclusive_invocations: Literal[24] = 24
    maximum_ordinary_detours: Literal[1] = 1
    policy_horizon_after_observation_before_next_provider: Literal[True] = True
    policy_horizon_preserves_raw_instrument_and_resource_integrity: Literal[True] = True
    measurement_support_after_observation_before_next_provider: Literal[True] = True
    failed_and_progress_observation_skip_baseline: Literal[True] = True
    successful_no_progress_only_baseline: Literal[True] = True
    qualified_final_parser_before_usable_classification: Literal[True] = True
    privacy_envelope_before_projection: Literal[True] = True
    raw_only_recovery: Literal[True] = True
    orphan_artifact_fails_closed: Literal[True] = True
    exact_model_thinking_profile_required: Literal[True] = True
    condition_bound_before_provider_invocation: Literal[True] = True
    mapper_runs_only_after_qualified_verifier: Literal[True] = True
    reference_mapper_exact_match_required: Literal[True] = True
    stage_two_provider_call_upper_bound: Literal[0] = 0
    empirical_execution_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_contract(self) -> BoundedPolicyRunnerContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "finance_v26_bounded_policy_runner_contract:",
        ):
            raise ValueError("v26.163 bounded-policy Runner Contract changed")
        return self


class BoundedPolicyEndpointFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    one_detour_legacy_terminal: Literal["completed_model_endpoint"] = "completed_model_endpoint"
    one_detour_policy_endpoint_observed: Literal[True] = True
    one_detour_qualified_validity: Literal[True] = True
    second_detour_legacy_terminal: Literal["measurement_support_exit"] = "measurement_support_exit"
    second_detour_legacy_failure_type: Literal["ordinary_detour_allowance_exhausted"] = (
        "ordinary_detour_allowance_exhausted"
    )
    second_detour_policy_terminal: Literal["policy_horizon_exhausted"] = "policy_horizon_exhausted"
    second_detour_policy_reason: Literal["ordinary_detour_limit"] = "ordinary_detour_limit"
    second_detour_raw_instrument_integrity: Literal[True] = True
    second_detour_measurement_support_available: Literal[True] = True
    second_detour_resource_accounting_integrity: Literal[True] = True
    second_detour_policy_endpoint_observed: Literal[True] = True
    second_detour_task_completion: Literal[False] = False
    second_detour_base_validity: Literal[False] = False
    second_detour_qualified_validity: Literal[False] = False
    second_detour_state_mapping_eligible: Literal[False] = False
    second_detour_task_verifier_invocation_count: Literal[0] = 0
    second_detour_later_provider_calls: Literal[0] = 0
    global_integrity_gate_passed: Literal[True] = True
    historical_raw_reclassification_count: Literal[0] = 0
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> BoundedPolicyEndpointFixtureAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_bounded_policy_endpoint_fixture:",
        ):
            raise ValueError("v26.163 bounded-policy endpoint fixture changed")
        return self


class BoundedPolicyFrequencyApiFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    passing_global_gate_count: Literal[1] = 1
    failed_global_gate_null_cell_count: Literal[1] = 1
    incomplete_cell_null_count: Literal[1] = 1
    complete_zero_qualified_q_zero_count: Literal[1] = 1
    complete_zero_qualified_pi_null_count: Literal[1] = 1
    single_qualified_pi_instantiated_count: Literal[1] = 1
    single_qualified_stable_probability_claim_count: Literal[0] = 0
    multi_state_empirical_non_degenerate_count: Literal[1] = 1
    q_wilson_interval_count: Literal[3] = 3
    marginal_pi_wilson_interval_count: Literal[3] = 3
    simultaneous_multinomial_coverage_claim_count: Literal[0] = 0
    imputed_state_vector_count: Literal[0] = 0
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> BoundedPolicyFrequencyApiFixtureAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_bounded_policy_frequency_api_fixture:",
        ):
            raise ValueError("v26.163 bounded-policy Frequency API fixture changed")
        return self


class RunnerPreflightAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    generation_fixture_audit_id: str = Field(min_length=1)
    independent_mapper_preflight_audit_id: str = Field(min_length=1)
    bounded_policy_endpoint_fixture_audit_id: str = Field(min_length=1)
    bounded_policy_frequency_api_fixture_audit_id: str = Field(min_length=1)
    temporal_gold_fixture_audit_id: str = Field(min_length=1)
    within_cell_contrast_audit_id: str = Field(min_length=1)
    scripted_job_count: Literal[360] = 360
    raw_recovery_count: Literal[360] = 360
    formal_assignment_count: Literal[0] = 0
    formal_frequency_report_count: Literal[0] = 0
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerPreflightAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_bounded_policy_runner_preflight:",
        ):
            raise ValueError("v26.163 bounded-policy Runner preflight changed")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    failure_type: str = Field(min_length=1)


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[MutationResult, ...] = Field(min_length=20)
    mutation_count: int = Field(ge=20)
    rejected_count: int = Field(ge=20)
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.mutation_name for item in self.mutations)
        if (
            names != tuple(sorted(set(names)))
            or self.mutation_count != len(self.mutations)
            or self.rejected_count != self.mutation_count
            or self.audit_id
            != identity(
                self,
                "audit_id",
                "finance_v26_bounded_policy_destructive:",
            )
        ):
            raise ValueError("v26.163 bounded-policy destructive audit changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    next_permitted_stage: Literal["fresh_bounded_policy_endpoint_frequency_execution_only"] = (
        "fresh_bounded_policy_endpoint_frequency_execution_only"
    )
    exact_fresh_360_job_manifest_execution_authorized: Literal[True] = True
    bounded_policy_endpoint_semantics_required: Literal[True] = True
    historical_rerun_pooling_or_reclassification_authorized: Literal[False] = False
    source_reselection_authorized: Literal[False] = False
    policy_mapper_condition_model_resource_or_verifier_change_authorized: Literal[False] = False
    current_denominator_frequency_authorized: Literal[False] = False
    state_probability_vtdo_training_release_or_production_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "finance_v26_bounded_policy_transition:",
        ):
            raise ValueError("v26.163 bounded-policy transition changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class BoundedPolicyPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    predecessor_replay_audit_id: str = Field(min_length=1)
    source_population_id: str = Field(min_length=1)
    source_selection_audit_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    support_closure_audit_id: str = Field(min_length=1)
    detour_qualification_audit_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    semantic_policy_id: str = Field(min_length=1)
    mapper_contract_id: str = Field(min_length=1)
    omega_task_context_catalog_id: str = Field(min_length=1)
    task_condition_cell_catalog_id: str = Field(min_length=1)
    frequency_assignment_contract_id: str = Field(min_length=1)
    mapper_protocol_id: str = Field(min_length=1)
    estimand_contract_id: str = Field(min_length=1)
    tool_schema_closure_audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    endpoint_fixture_audit_id: str = Field(min_length=1)
    frequency_api_fixture_audit_id: str = Field(min_length=1)
    independent_mapper_preflight_audit_id: str = Field(min_length=1)
    runner_preflight_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    prospective_execution_id: str = Field(min_length=1)
    prospective_report_id: str = Field(min_length=1)
    fresh_source_task_count: Literal[12] = 12
    task_package_count: Literal[12] = 12
    conditioned_path_count: Literal[36] = 36
    strong_cell_count: Literal[48] = 48
    fresh_job_count: Literal[360] = 360
    unconditional_job_count: Literal[144] = 144
    conditioned_job_count: Literal[216] = 216
    formal_assignment_count: Literal[0] = 0
    formal_frequency_report_count: Literal[0] = 0
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    historical_reclassification_count: Literal[0] = 0
    detail_files: tuple[DetailFile, ...] = Field(min_length=20)
    next_permitted_stage: Literal["fresh_bounded_policy_endpoint_frequency_execution_only"] = (
        "fresh_bounded_policy_endpoint_frequency_execution_only"
    )
    status: Literal["fresh_bounded_policy_endpoint_frequency_preflight_passed"] = (
        "fresh_bounded_policy_endpoint_frequency_preflight_passed"
    )

    @model_validator(mode="after")
    def validate_report(self) -> BoundedPolicyPreflightReport:
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_bounded_policy_preflight_report:",
        ):
            raise ValueError("v26.163 bounded-policy preflight report changed")
        return self


class BuildProducts(FrozenModel):
    predecessor_replay: PredecessorReplayAudit
    source_population: FreshFrequencySourcePopulation
    source_selection: RouteBSourceSelectionAudit
    generation_policy: BoundedPolicyEndpointGenerationPolicy
    manifest: FrequencyManifest
    estimand_contract: BoundedPolicyEstimandContract
    outcome_contract: BoundedPolicyOutcomeContract
    runner_contract: BoundedPolicyRunnerContract
    endpoint_fixture: BoundedPolicyEndpointFixtureAudit
    frequency_api_fixture: BoundedPolicyFrequencyApiFixtureAudit
    runner_preflight: RunnerPreflightAudit
    destructive: DestructiveAudit
    transition: ProspectiveTransitionContract
    report: BoundedPolicyPreflightReport
    internal: dict[str, Any] = Field(default_factory=dict, exclude=True)
