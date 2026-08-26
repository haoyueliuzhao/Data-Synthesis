from __future__ import annotations

from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.evaluation.valid_only_state_mapping_v2 import (
    ValidOnlyStateMapperContractV2,
)
from trusted_synthesis.core.trajectory.empirical_state_mapping_v2 import (
    EmpiricalStateSemanticPolicyV2,
    ExperimentalConditionV2,
)
from trusted_synthesis.core.trajectory.reachability_frequency_v2 import (
    TaskConditionCellCatalogV2,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveTaskArtifact,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return strict_canonical_hash(value.model_dump(mode="python", exclude={field}), prefix=prefix)


class FileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    source_kind: Literal[
        "v26_159_direct_output",
        "historical_source_population",
        "fresh_sampling_frame",
        "frozen_protocol_input",
        "implementation",
    ]


class ReproducibilityRootAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = Field(min_length=1)
    predecessor_transition_id: str = Field(min_length=1)
    predecessor_direct_output_count: int = Field(ge=1)
    predecessor_rebuilt_output_count: int = Field(ge=1)
    predecessor_byte_match_count: int = Field(ge=1)
    file_bindings: tuple[FileBinding, ...] = Field(min_length=1)
    current_stage_input_file_count: int = Field(ge=1)
    current_stage_all_bound_files_available: Literal[True] = True
    missing_historical_snapshot_path: str = Field(min_length=1)
    missing_historical_snapshot_available: Literal[False] = False
    v26_158_full_transitive_rebuild_claimed: Literal[False] = False
    limitation_preserved_without_false_pass: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["direct_predecessor_rebuilt_historical_snapshot_gap_preserved"] = (
        "direct_predecessor_rebuilt_historical_snapshot_gap_preserved"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ReproducibilityRootAudit:
        paths = tuple(item.relative_path for item in self.file_bindings)
        if (
            paths != tuple(sorted(set(paths)))
            or self.current_stage_input_file_count != len(self.file_bindings)
            or self.predecessor_direct_output_count != self.predecessor_rebuilt_output_count
            or self.predecessor_byte_match_count != self.predecessor_direct_output_count
            or self.audit_id
            != identity(self, "audit_id", "finance_v26_frequency_reproducibility_root:")
        ):
            raise ValueError("v26.160 reproducibility root changed")
        return self


class FreshFrequencySourceBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    tier: Literal["easy_control", "frontier", "hard_control"]
    source_task: CapabilitySensitiveTaskArtifact
    source_task_artifact_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    core_semantic_signature: str = Field(min_length=1)
    task_signature: str = Field(min_length=1)
    mechanism_instance_signature: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    evidence_version_ids: tuple[str, ...] = Field(min_length=1)
    source_record_ids: tuple[str, ...] = Field(min_length=1)
    source_rank: str = Field(min_length=1)
    selected_before_compatibility_or_mapper_load: Literal[True] = True
    model_outcomes_used_for_selection: Literal[False] = False
    verifier_passability_used_for_selection: Literal[False] = False
    resource_values_used_for_selection: Literal[False] = False

    @model_validator(mode="after")
    def validate_binding(self) -> FreshFrequencySourceBinding:
        if (
            self.source_task.artifact_id != self.source_task_artifact_id
            or self.source_task.task.task_id != self.task_id
            or self.evidence_ids != tuple(sorted(set(self.evidence_ids)))
            or self.evidence_version_ids != tuple(sorted(set(self.evidence_version_ids)))
            or self.source_record_ids != tuple(sorted(set(self.source_record_ids)))
            or self.binding_id
            != identity(self, "binding_id", "finance_v26_frequency_source_binding:")
        ):
            raise ValueError("v26.160 fresh source binding changed")
        return self


class FreshFrequencySourcePopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    source_frame_population_id: str = Field(min_length=1)
    source_selection_salt: str = Field(min_length=1)
    tasks: tuple[FreshFrequencySourceBinding, ...] = Field(min_length=12, max_length=12)
    task_count: Literal[12] = 12
    mechanism_tier_cell_count: Literal[12] = 12
    model_exposure_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    selected_before_compatibility_or_mapper_load: Literal[True] = True
    schema_version: str = "finance_v26_mapper_v2_frequency_source_population.v1"

    @model_validator(mode="after")
    def validate_population(self) -> FreshFrequencySourcePopulation:
        cells = {(item.mechanism_id, item.tier) for item in self.tasks}
        if (
            len(cells) != 12
            or len({item.source_task_artifact_id for item in self.tasks}) != 12
            or self.population_id
            != identity(self, "population_id", "finance_v26_frequency_source_population:")
        ):
            raise ValueError("v26.160 fresh source Population changed")
        return self


class FreshnessChannelRow(FrozenModel):
    channel: str = Field(min_length=1)
    excluded_count: int = Field(ge=1)
    selected_count: int = Field(ge=1)
    overlap_count: Literal[0] = 0


class SourceSelectionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    reproducibility_root_audit_id: str = Field(min_length=1)
    source_frame_population_id: str = Field(min_length=1)
    source_population_id: str = Field(min_length=1)
    prior_population_count: Literal[3] = 3
    prior_selected_source_task_count: Literal[36] = 36
    eligible_model_unexposed_task_count: int = Field(ge=12)
    freshness_channels: tuple[FreshnessChannelRow, ...] = Field(min_length=8, max_length=8)
    mechanism_tier_cell_count: Literal[12] = 12
    source_selection_before_mapper_policy_load: Literal[True] = True
    source_selection_before_path_or_resource_compile: Literal[True] = True
    compatibility_results_used_for_selection: Literal[False] = False
    model_outcomes_used_for_selection: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["fresh_model_unexposed_population_frozen"] = (
        "fresh_model_unexposed_population_frozen"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceSelectionAudit:
        channels = tuple(item.channel for item in self.freshness_channels)
        if (
            channels != tuple(sorted(set(channels)))
            or any(item.overlap_count for item in self.freshness_channels)
            or self.audit_id
            != identity(self, "audit_id", "finance_v26_frequency_source_selection:")
        ):
            raise ValueError("v26.160 source selection changed")
        return self


class OmegaTaskContextV2(FrozenModel):
    context_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    tier: str = Field(min_length=1)
    operational_record_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    verifier_contract_id: str = Field(min_length=1)
    joint_support_validity_contract_id: str = Field(min_length=1)
    qualified_final_grammar_id: str = Field(min_length=1)
    semantic_policy_id: str = Field(min_length=1)
    typed_reference_policy_id: str = Field(min_length=1)
    task_package_content_hash: str = Field(min_length=1)
    operational_record_content_hash: str = Field(min_length=1)
    environment_content_hash: str = Field(min_length=1)
    schema_version: str = "finance_v26_mapper_v2_frequency_omega_context.v1"

    @model_validator(mode="after")
    def validate_context(self) -> OmegaTaskContextV2:
        if self.context_id != identity(
            self,
            "context_id",
            "finance_v26_frequency_omega_task_context:",
        ):
            raise ValueError("v26.160 Omega Task Context changed")
        return self


class OmegaTaskContextCatalogV2(FrozenModel):
    catalog_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    semantic_policy_id: str = Field(min_length=1)
    contexts: tuple[OmegaTaskContextV2, ...] = Field(min_length=12, max_length=12)
    context_count: Literal[12] = 12
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> OmegaTaskContextCatalogV2:
        ids = tuple(item.context_id for item in self.contexts)
        if (
            ids != tuple(sorted(set(ids)))
            or len({item.task_package_id for item in self.contexts}) != 12
            or any(item.semantic_policy_id != self.semantic_policy_id for item in self.contexts)
            or self.catalog_id
            != identity(self, "catalog_id", "finance_v26_frequency_omega_catalog:")
        ):
            raise ValueError("v26.160 Omega Context Catalog changed")
        return self


class ToolSchemaClosureRow(FrozenModel):
    tool_id: str = Field(min_length=1)
    schema_hash: str = Field(min_length=1)
    environment_manifest_count: int = Field(ge=1)
    reachable_candidate_count: int = Field(ge=1)
    reference_commit_count: int = Field(ge=0)
    schema_registered: Literal[True] = True


class ToolSchemaClosureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    semantic_policy_id: str = Field(min_length=1)
    typed_reference_policy_id: str = Field(min_length=1)
    tool_schema_version_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    registered_tool_schema_count: Literal[6] = 6
    environment_tool_count: Literal[6] = 6
    reachable_candidate_tool_count: Literal[6] = 6
    reference_commit_tool_count: Literal[6] = 6
    unknown_tool_rejection_count: Literal[1] = 1
    closure_rows: tuple[ToolSchemaClosureRow, ...] = Field(min_length=6, max_length=6)
    all_reachable_tools_have_exact_schema: Literal[True] = True
    tool_schema_version_enters_experiment_identity: Literal[True] = True
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> ToolSchemaClosureAudit:
        ids = tuple(item.tool_id for item in self.closure_rows)
        if (
            ids != tuple(sorted(set(ids)))
            or len(ids) != 6
            or self.audit_id
            != identity(self, "audit_id", "finance_v26_frequency_tool_schema_closure:")
        ):
            raise ValueError("v26.160 Tool Schema closure changed")
        return self


class FrequencyAssignmentContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    mapper_contract_id: str = Field(min_length=1)
    semantic_policy_id: str = Field(min_length=1)
    task_condition_cell_catalog_id: str = Field(min_length=1)
    required_parent_bindings: tuple[str, ...] = (
        "empirical_route_signature_id",
        "experiment_id",
        "experimental_condition_id",
        "generation_policy_id",
        "job_id",
        "mapping_assignment_id",
        "measurement_gate_id",
        "qualified_validity_report_id",
        "structural_state_id",
        "task_condition_cell_id",
        "task_package_id",
    )
    assignment_only_after_complete_measurement_gate: Literal[True] = True
    qualified_validity_true_required: Literal[True] = True
    route_signature_excluded_from_statistics_key: Literal[True] = True
    failed_gate_creates_zero_assignments: Literal[True] = True
    preflight_formal_assignment_count: Literal[0] = 0
    schema_version: str = "finance_v26_mapper_v2_frequency_assignment_contract.v1"

    @model_validator(mode="after")
    def validate_contract(self) -> FrequencyAssignmentContract:
        if self.required_parent_bindings != tuple(
            sorted(set(self.required_parent_bindings))
        ) or self.contract_id != identity(
            self, "contract_id", "finance_v26_frequency_assignment_contract:"
        ):
            raise ValueError("v26.160 Frequency Assignment Contract changed")
        return self


class MapperV2FrequencyProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    semantic_policy: EmpiricalStateSemanticPolicyV2
    mapper_contract: ValidOnlyStateMapperContractV2
    omega_task_context_catalog_id: str = Field(min_length=1)
    task_condition_cell_catalog_id: str = Field(min_length=1)
    frequency_assignment_contract_id: str = Field(min_length=1)
    tool_schema_closure_audit_id: str = Field(min_length=1)
    tool_schema_version_id: str = Field(min_length=1)
    independent_reference_mapper_required: Literal[True] = True
    production_reference_exact_state_match_required: Literal[True] = True
    historical_mapper_v1_assignment_reuse: Literal[False] = False
    v26_159_diagnostic_assignment_promotion: Literal[False] = False
    formal_assignment_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = "finance_v26_mapper_v2_frequency_protocol.v1"

    @model_validator(mode="after")
    def validate_protocol(self) -> MapperV2FrequencyProtocol:
        if (
            self.mapper_contract.semantic_policy_id != self.semantic_policy.policy_id
            or self.tool_schema_version_id == ""
            or self.protocol_id
            != identity(self, "protocol_id", "finance_v26_mapper_v2_frequency_protocol:")
        ):
            raise ValueError("v26.160 Mapper v2 Frequency Protocol changed")
        return self


class FrequencyEstimandContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    task_condition_cell_catalog_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    frequency_assignment_contract_id: str = Field(min_length=1)
    unconditional_estimand: Literal["bounded_policy_unconditional_qualified_state_frequency"] = (
        "bounded_policy_unconditional_qualified_state_frequency"
    )
    conditioned_estimand: Literal["bounded_policy_path_conditioned_qualified_state_frequency"] = (
        "bounded_policy_path_conditioned_qualified_state_frequency"
    )
    unrestricted_natural_agent_distribution_claimed: Literal[False] = False
    unconditional_and_conditioned_denominators_separate: Literal[True] = True
    conditioned_paths_have_independent_denominators: Literal[True] = True
    conditioned_rows_can_augment_unconditional_denominator: Literal[False] = False
    paths_can_be_pooled: Literal[False] = False
    tasks_can_be_pooled_as_independent_units: Literal[False] = False
    task_primary_rollout_secondary: Literal[True] = True
    no_qualified_row_distribution_is_null: Literal[True] = True
    failed_measurement_gate_all_distributions_null: Literal[True] = True
    zero_vector_or_state_imputation_allowed: Literal[False] = False
    empirical_route_signature_conditioning_allowed: Literal[False] = False
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> FrequencyEstimandContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "finance_v26_frequency_estimand_contract:",
        ):
            raise ValueError("v26.160 Frequency Estimand Contract changed")
        return self


class FrequencyExecutionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    source_population_id: str = Field(min_length=1)
    source_selection_audit_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    mapper_protocol_id: str = Field(min_length=1)
    mapper_contract_id: str = Field(min_length=1)
    task_condition_cell_catalog_id: str = Field(min_length=1)
    frequency_estimand_contract_id: str = Field(min_length=1)
    frequency_assignment_contract_id: str = Field(min_length=1)
    joint_support_validity_contract_id: str = Field(min_length=1)
    exact_denominator: Literal[360] = 360
    task_count: Literal[12] = 12
    registered_path_count: Literal[36] = 36
    unconditional_job_count: Literal[144] = 144
    conditioned_job_count: Literal[216] = 216
    unconditional_replicas_per_task: Literal[12] = 12
    conditioned_replicas_per_path: Literal[6] = 6
    role: Literal["reachability"] = "reachability"
    formal_assignment_count: Literal[0] = 0
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> FrequencyExecutionContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "finance_v26_frequency_execution_contract:",
        ):
            raise ValueError("v26.160 Frequency Execution Contract changed")
        return self


class FrequencyJob(FrozenModel):
    job_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    mapper_protocol_id: str = Field(min_length=1)
    task_condition_cell_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    tier: Literal["easy_control", "frontier", "hard_control"]
    sampling_mode: Literal["reachability_unconditional", "reachability_conditioned"]
    replicate_index: int = Field(ge=0, le=11)
    seed: int = Field(ge=0)
    experimental_condition: ExperimentalConditionV2
    requested_path_id: str | None = None
    requested_path_strategy: str | None = None
    public_path_condition: str | None = None
    public_condition_id: str | None = None
    stage_one_profile_id: str = Field(min_length=1)
    stage_two_profile_id: str = Field(min_length=1)
    exact_final_response_grammar_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    candidate_presentation_parent_id: str = Field(min_length=1)
    historical_job_identity_reused: Literal[False] = False
    historical_seed_reused: Literal[False] = False
    execution_opened: Literal[False] = False

    @model_validator(mode="after")
    def validate_job(self) -> FrequencyJob:
        conditioned = self.sampling_mode == "reachability_conditioned"
        conditionals = (
            self.requested_path_id,
            self.requested_path_strategy,
            self.public_path_condition,
            self.public_condition_id,
        )
        if (
            conditioned != all(value is not None for value in conditionals)
            or (not conditioned and any(value is not None for value in conditionals))
            or self.experimental_condition.sampling_mode != self.sampling_mode
            or self.experimental_condition.requested_path_id != self.requested_path_id
            or self.experimental_condition.requested_path_strategy != self.requested_path_strategy
            or self.experimental_condition.public_condition_id != self.public_condition_id
            or (conditioned and self.replicate_index >= 6)
            or self.job_id != identity(self, "job_id", "finance_v26_frequency_job:")
        ):
            raise ValueError("v26.160 Frequency Job changed")
        return self


class FrequencyManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    source_population_id: str = Field(min_length=1)
    source_selection_audit_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    mapper_protocol_id: str = Field(min_length=1)
    task_condition_cell_catalog_id: str = Field(min_length=1)
    prospective_runner_run_id: str = Field(min_length=1)
    prospective_execution_run_id: str = Field(min_length=1)
    prospective_report_run_id: str = Field(min_length=1)
    jobs: tuple[FrequencyJob, ...] = Field(min_length=360, max_length=360)
    exact_denominator: Literal[360] = 360
    distinct_task_count: Literal[12] = 12
    distinct_task_condition_cell_count: Literal[48] = 48
    distinct_path_count: Literal[36] = 36
    unconditional_job_count: Literal[144] = 144
    conditioned_job_count: Literal[216] = 216
    distinct_seed_count: Literal[360] = 360
    historical_job_overlap_count: Literal[0] = 0
    historical_seed_overlap_count: Literal[0] = 0
    formal_assignment_count: Literal[0] = 0
    execution_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_manifest(self) -> FrequencyManifest:
        modes = Counter(item.sampling_mode for item in self.jobs)
        task_counts = Counter(item.task_package_id for item in self.jobs)
        cell_counts = Counter(item.task_condition_cell_id for item in self.jobs)
        path_counts = Counter(
            item.requested_path_id for item in self.jobs if item.requested_path_id is not None
        )
        if (
            len({item.job_id for item in self.jobs}) != 360
            or len({item.seed for item in self.jobs}) != 360
            or len(task_counts) != 12
            or set(task_counts.values()) != {30}
            or len(cell_counts) != 48
            or set(cell_counts.values()) != {6, 12}
            or modes
            != Counter({"reachability_unconditional": 144, "reachability_conditioned": 216})
            or len(path_counts) != 36
            or set(path_counts.values()) != {6}
            or self.manifest_id != identity(self, "manifest_id", "finance_v26_frequency_manifest:")
        ):
            raise ValueError("v26.160 Frequency Manifest changed")
        return self


class FrequencyOutcomeContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    frequency_estimand_contract_id: str = Field(min_length=1)
    frequency_assignment_contract_id: str = Field(min_length=1)
    exact_denominator: Literal[360] = 360
    measurement_gate: tuple[str, ...] = (
        "complete_raw_360_of_360",
        "model_endpoint_360_of_360",
        "validity_evaluable_360_of_360",
        "measurement_support_exit_zero",
        "instrument_failure_zero",
        "privacy_failure_zero",
        "exact_model_thinking_usage_failure_zero",
        "typed_budget_no_call_zero",
        "unresolved_transport_failure_zero",
    )
    failed_gate_keeps_every_exact_frequency_estimand_null: Literal[True] = True
    support_exit_row_deletion_forbidden: Literal[True] = True
    valid_only_assignment_requires_qualified_true: Literal[True] = True
    no_qualified_cell_distribution_null: Literal[True] = True
    task_primary_rollout_secondary: Literal[True] = True
    independent_postrun_audit_required: Literal[True] = True
    preflight_frequency_report_count: Literal[0] = 0
    preflight_formal_assignment_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_contract(self) -> FrequencyOutcomeContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "finance_v26_frequency_outcome_contract:",
        ):
            raise ValueError("v26.160 Frequency Outcome Contract changed")
        return self


class FrequencyRunnerContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
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
    def validate_contract(self) -> FrequencyRunnerContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "finance_v26_frequency_runner_contract:",
        ):
            raise ValueError("v26.160 Frequency Runner Contract changed")
        return self


class WithinCellContrastAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mapper_protocol_id: str = Field(min_length=1)
    fixture_task_package_id: str = Field(min_length=1)
    fixture_task_condition_cell_id: str = Field(min_length=1)
    fixture_state_count: int = Field(ge=4)
    within_task_state_pair_count: int = Field(ge=1)
    within_task_state_contrast_count: int = Field(ge=1)
    within_task_condition_state_pair_count: int = Field(ge=1)
    within_task_condition_state_contrast_count: int = Field(ge=1)
    action_only_pair_count: int = Field(ge=1)
    result_only_pair_count: int = Field(ge=1)
    failure_or_temporal_pair_count: int = Field(ge=1)
    every_pair_has_difference_witness: Literal[True] = True
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> WithinCellContrastAudit:
        if (
            self.within_task_state_pair_count != self.within_task_state_contrast_count
            or self.within_task_condition_state_pair_count
            != self.within_task_condition_state_contrast_count
            or self.audit_id
            != identity(self, "audit_id", "finance_v26_frequency_within_cell_contrast:")
        ):
            raise ValueError("v26.160 within-cell State Contrast changed")
        return self


class IndependentMapperPreflightAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mapper_protocol_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    fixture_task_condition_cell_count: Literal[48] = 48
    fixture_trajectory_count: Literal[48] = 48
    valid_only_authorization_count: Literal[48] = 48
    production_mapper_invocation_count: Literal[48] = 48
    reference_mapper_invocation_count: Literal[48] = 48
    exact_state_match_count: Literal[48] = 48
    reference_mapper_called_production_mapper_count: Literal[0] = 0
    intentional_mismatch_rejection_count: Literal[1] = 1
    formal_assignment_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    fixture_hash: str = Field(min_length=64, max_length=64)
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> IndependentMapperPreflightAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_frequency_independent_mapper_preflight:",
        ):
            raise ValueError("v26.160 independent Mapper preflight changed")
        return self


class FrequencyApiFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_condition_cell_catalog_id: str = Field(min_length=1)
    passing_gate_fixture_count: Literal[1] = 1
    failed_gate_fixture_count: Literal[1] = 1
    missing_qualified_cell_fixture_count: Literal[1] = 1
    strong_key_rejection_count: Literal[1] = 1
    conditioned_into_unconditional_rejection_count: Literal[1] = 1
    route_as_condition_rejection_count: Literal[1] = 1
    failed_gate_all_report_null_count: Literal[48] = 48
    missing_qualified_cell_null_count: Literal[1] = 1
    zero_vector_imputation_count: Literal[0] = 0
    formal_frequency_report_count: Literal[0] = 0
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> FrequencyApiFixtureAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_frequency_api_fixture:",
        ):
            raise ValueError("v26.160 Frequency API fixture changed")
        return self


class RunnerPreflightAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    generation_fixture_audit_id: str = Field(min_length=1)
    independent_mapper_preflight_audit_id: str = Field(min_length=1)
    frequency_api_fixture_audit_id: str = Field(min_length=1)
    temporal_gold_fixture_audit_id: str = Field(min_length=1)
    within_cell_contrast_audit_id: str = Field(min_length=1)
    scripted_job_count: Literal[360] = 360
    scripted_completed_job_count: Literal[360] = 360
    scripted_raw_recovery_count: Literal[360] = 360
    covered_task_condition_cell_count: Literal[48] = 48
    mapper_fixture_trajectory_count: Literal[48] = 48
    production_reference_match_count: Literal[48] = 48
    formal_assignment_count: Literal[0] = 0
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    credential_lookup_attempted: Literal[False] = False
    status: Literal["passed"] = "passed"

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerPreflightAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_frequency_runner_preflight:",
        ):
            raise ValueError("v26.160 Runner preflight changed")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    failure_type: str = Field(min_length=1)
    rejected: Literal[True] = True
    provider_calls_before_rejection: Literal[0] = 0


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
            or self.rejected_count != len(self.mutations)
            or self.audit_id != identity(self, "audit_id", "finance_v26_frequency_destructive:")
        ):
            raise ValueError("v26.160 destructive audit changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    next_permitted_stage: Literal["fresh_mapper_v2_reachability_frequency_execution_only"] = (
        "fresh_mapper_v2_reachability_frequency_execution_only"
    )
    exact_fresh_360_job_execution_authorized: Literal[True] = True
    provider_calls_authorized_only_for_exact_manifest: Literal[True] = True
    mapper_v2_formal_assignments_authorized_only_after_passing_gate: Literal[True] = True
    historical_rerun_pooling_or_reclassification_authorized: Literal[False] = False
    diagnostic_assignment_promotion_authorized: Literal[False] = False
    task_condition_tool_mapper_model_resource_change_authorized: Literal[False] = False
    vtdo_training_release_or_production_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "finance_v26_frequency_transition:",
        ):
            raise ValueError("v26.160 transition changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class FrequencyPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    reproducibility_root_audit_id: str = Field(min_length=1)
    source_population_id: str = Field(min_length=1)
    source_selection_audit_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    support_closure_audit_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    generation_policy_id: str = Field(min_length=1)
    semantic_policy_id: str = Field(min_length=1)
    mapper_contract_id: str = Field(min_length=1)
    omega_task_context_catalog_id: str = Field(min_length=1)
    task_condition_cell_catalog_id: str = Field(min_length=1)
    frequency_assignment_contract_id: str = Field(min_length=1)
    mapper_protocol_id: str = Field(min_length=1)
    frequency_estimand_contract_id: str = Field(min_length=1)
    tool_schema_closure_audit_id: str = Field(min_length=1)
    temporal_gold_fixture_audit_id: str = Field(min_length=1)
    within_cell_contrast_audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    independent_mapper_preflight_audit_id: str = Field(min_length=1)
    frequency_api_fixture_audit_id: str = Field(min_length=1)
    runner_preflight_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    prospective_execution_id: str = Field(min_length=1)
    prospective_report_id: str = Field(min_length=1)
    fresh_source_task_count: Literal[12] = 12
    fresh_task_package_count: Literal[12] = 12
    fresh_path_count: Literal[36] = 36
    fresh_task_condition_cell_count: Literal[48] = 48
    fresh_job_count: Literal[360] = 360
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    formal_state_assignment_count: Literal[0] = 0
    formal_frequency_report_count: Literal[0] = 0
    historical_reclassified: Literal[False] = False
    frequency_measured: Literal[False] = False
    vtdo_authorized: Literal[False] = False
    next_permitted_stage: Literal["fresh_mapper_v2_reachability_frequency_execution_only"] = (
        "fresh_mapper_v2_reachability_frequency_execution_only"
    )
    detail_files: tuple[DetailFile, ...] = Field(min_length=20)
    status: Literal["mapper_v2_reachability_frequency_preflight_passed"] = (
        "mapper_v2_reachability_frequency_preflight_passed"
    )

    @model_validator(mode="after")
    def validate_report(self) -> FrequencyPreflightReport:
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))) or self.report_id != identity(
            self, "report_id", "finance_v26_frequency_preflight_report:"
        ):
            raise ValueError("v26.160 preflight report changed")
        return self


class BuildProducts(FrozenModel):
    reproducibility_root: ReproducibilityRootAudit
    source_population: FreshFrequencySourcePopulation
    source_selection: SourceSelectionAudit
    semantic_policy: EmpiricalStateSemanticPolicyV2
    mapper_contract: ValidOnlyStateMapperContractV2
    omega_catalog: OmegaTaskContextCatalogV2
    cell_catalog: TaskConditionCellCatalogV2
    assignment_contract: FrequencyAssignmentContract
    mapper_protocol: MapperV2FrequencyProtocol
    estimand_contract: FrequencyEstimandContract
    execution_contract: FrequencyExecutionContract
    manifest: FrequencyManifest
    outcome_contract: FrequencyOutcomeContract
    runner_contract: FrequencyRunnerContract
    tool_closure: ToolSchemaClosureAudit
    within_cell_contrast: WithinCellContrastAudit
    independent_mapper: IndependentMapperPreflightAudit
    frequency_api: FrequencyApiFixtureAudit
    runner_preflight: RunnerPreflightAudit
    destructive: DestructiveAudit
    transition: ProspectiveTransitionContract
    report: FrequencyPreflightReport
    internal: dict[str, Any] = Field(default_factory=dict, exclude=True)
