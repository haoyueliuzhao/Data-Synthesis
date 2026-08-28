from __future__ import annotations

from collections import Counter
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.capability_observation import (
    CAPABILITY_FAMILY_ORDER,
    OBSERVATION_DEPTH_ORDER,
    BoundarySelectionContract,
    CapabilityFamily,
    CapabilityObservationGroup,
    CapabilityObservationProtocol,
    ExposureBlockContract,
    ObservabilityFloorContract,
    ObservationPartition,
    ProspectiveFollowupStatus,
    RoleExecutableDepthSignature,
)
from trusted_synthesis.hashing import canonical_hash

RUN_VERSION = "finance_v26_capability_breadth_depth_static_audit.v1"
NEXT_STAGE: Final[Literal["capability_observation_development_runner_preflight_only"]] = (
    "capability_observation_development_runner_preflight_only"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class FileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    source_kind: Literal[
        "external_audit_input",
        "implementation",
        "v26_163_frozen_source",
        "v26_166_frozen_output",
    ]


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    review_sha256: str = Field(min_length=64, max_length=64)
    review_byte_count: int = Field(gt=0)
    authorized_stage: Literal["capability_breadth_depth_task_synthesis_and_static_audit_only"]
    provider_calls_authorized: Literal[False] = False
    historical_reclassification_authorized: Literal[False] = False
    old_confirmation_transition_consumable: Literal[False] = False
    fresh_task_synthesis_authorized: Literal[True] = True
    static_role_compilation_authorized: Literal[True] = True

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_capability_breadth_depth_external_audit_authorization:",
        ):
            raise ValueError("v26.167 external audit authorization identity is invalid")
        return self


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    bindings: tuple[FileBinding, ...] = Field(min_length=8)
    v26_166_historical_artifacts_rebuilt_or_changed: Literal[False] = False
    v26_163_v26_166_bound_before_result_use: Literal[True] = True
    source_selection_precedes_v26_166_outcome_loading: Literal[True] = True
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.167 source replay bindings are not canonical")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_capability_breadth_depth_source_replay:",
        ):
            raise ValueError("v26.167 source replay identity is invalid")
        return self


class LegacyProtocolSupersession(FrozenModel):
    decision_id: str = Field(min_length=1)
    v26_166_report_id: str = Field(min_length=1)
    v26_166_fresh_confirmation_protocol_id: str = Field(min_length=1)
    v26_166_transition_id: str = Field(min_length=1)
    historical_v26_166_artifacts_retained: Literal[True] = True
    historical_v26_166_results_retained: Literal[True] = True
    old_transition_consumed: Literal[False] = False
    old_protocol_sufficient_for_execution: Literal[False] = False
    missing_contract_dimensions: tuple[str, ...] = Field(min_length=10)
    replacement_authority: Literal["external_joint_audit"] = "external_joint_audit"
    replacement_stage: Literal["capability_breadth_depth_task_synthesis_and_static_audit_only"]

    @model_validator(mode="after")
    def validate_decision(self) -> LegacyProtocolSupersession:
        if self.missing_contract_dimensions != tuple(sorted(set(self.missing_contract_dimensions))):
            raise ValueError("legacy protocol missing dimensions are not canonical")
        if self.decision_id != identity(
            self,
            "decision_id",
            "finance_v26_legacy_confirmation_protocol_supersession:",
        ):
            raise ValueError("legacy protocol supersession identity is invalid")
        return self


class HistoricalTierBoundaryContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    historical_tier_values: tuple[str, str, str] = (
        "easy_control",
        "frontier",
        "hard_control",
    )
    historical_role: Literal["global_complexity_bundle_for_replay_only"] = (
        "global_complexity_bundle_for_replay_only"
    )
    observation_depth_values: tuple[str, str, str, str] = (
        "d0_observability_anchor",
        "d1_basic",
        "d2_compositional",
        "d3_stress",
    )
    tier_to_depth_mapping_authorized: Literal[False] = False
    survival_profile_used_as_depth_scale: Literal[False] = False
    historical_source_tier_rewritten: Literal[False] = False

    @model_validator(mode="after")
    def validate_contract(self) -> HistoricalTierBoundaryContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "finance_v26_historical_tier_observation_depth_boundary:",
        ):
            raise ValueError("historical Tier boundary identity is invalid")
        return self


class SelectedObservationSource(FrozenModel):
    binding_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    group_index: int = Field(ge=1, le=4)
    partition: ObservationPartition
    source_rank: str = Field(min_length=64, max_length=64)
    source_task_artifact_id: str = Field(min_length=1)
    source_task_id: str = Field(min_length=1)
    historical_difficulty_tier: str = Field(min_length=1)
    core_semantic_signature: str = Field(min_length=1)
    task_signature: str = Field(min_length=1)
    mechanism_instance_signature: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    evidence_version_ids: tuple[str, ...] = Field(min_length=1)
    source_record_ids: tuple[str, ...] = Field(min_length=1)
    selected_before_v26_166_outcome_loading: Literal[True] = True
    old_tier_used_for_selection: Literal[False] = False
    current_27_cells_used_for_selection: Literal[False] = False

    @model_validator(mode="after")
    def validate_binding(self) -> SelectedObservationSource:
        for values in (self.evidence_ids, self.evidence_version_ids, self.source_record_ids):
            if values != tuple(sorted(set(values))):
                raise ValueError("selected observation source channels are not canonical")
        if self.partition != (
            ObservationPartition.DEVELOPMENT
            if self.group_index <= 2
            else ObservationPartition.CONFIRMATION
        ):
            raise ValueError("selected observation source partition is inconsistent")
        if self.binding_id != identity(
            self,
            "binding_id",
            "finance_v26_capability_observation_source_binding:",
        ):
            raise ValueError("selected observation source identity is invalid")
        return self


class EvidenceCapacityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_frame_population_id: str = Field(min_length=1)
    source_frame_sha256: str = Field(min_length=64, max_length=64)
    prior_exposed_population_id: str = Field(min_length=1)
    prior_exposed_population_sha256: str = Field(min_length=64, max_length=64)
    frame_task_count: Literal[70] = 70
    prior_exposed_source_task_count: Literal[12] = 12
    eligible_source_counts: dict[CapabilityFamily, int]
    required_group_counts: dict[CapabilityFamily, int]
    selected_sources: tuple[SelectedObservationSource, ...] = Field(
        min_length=16,
        max_length=16,
    )
    selected_group_count: Literal[16] = 16
    selected_static_task_count: Literal[64] = 64
    selected_design: Literal["full_64_task_design"] = "full_64_task_design"
    fallback_48_task_design_activated: Literal[False] = False
    cross_group_evidence_overlap_count: Literal[0] = 0
    cross_group_evidence_version_overlap_count: Literal[0] = 0
    cross_group_source_record_overlap_count: Literal[0] = 0
    outcome_fields_loaded_before_selection: Literal[False] = False
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_audit(self) -> EvidenceCapacityAudit:
        expected_required = {item: 4 for item in CAPABILITY_FAMILY_ORDER}
        if self.required_group_counts != expected_required:
            raise ValueError("Evidence Capacity required-group design changed")
        if set(self.eligible_source_counts) != set(CAPABILITY_FAMILY_ORDER) or any(
            self.eligible_source_counts[item] < 4 for item in CAPABILITY_FAMILY_ORDER
        ):
            raise ValueError("Evidence Capacity cannot support the 64-task design")
        capability_counts = Counter(item.capability_family for item in self.selected_sources)
        partition_counts = Counter(item.partition for item in self.selected_sources)
        if capability_counts != Counter(expected_required) or partition_counts != Counter(
            {ObservationPartition.DEVELOPMENT: 8, ObservationPartition.CONFIRMATION: 8}
        ):
            raise ValueError("Evidence Capacity selected-source balance changed")
        if len({item.source_task_artifact_id for item in self.selected_sources}) != 16:
            raise ValueError("Evidence Capacity repeats a source task")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_capability_observation_evidence_capacity_audit:",
        ):
            raise ValueError("Evidence Capacity audit identity is invalid")
        return self


class CapabilityNeutralGenerationCondition(FrozenModel):
    condition_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    path_strategy: Literal["structured_direct"] = "structured_direct"
    capability_cue_injected_by_condition: Literal[False] = False
    same_across_depths_and_groups: Literal[True] = True
    all_path_pooling_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_condition(self) -> CapabilityNeutralGenerationCondition:
        if self.condition_id != identity(
            self,
            "condition_id",
            "capability_neutral_generation_condition:",
        ):
            raise ValueError("capability-neutral generation condition identity is invalid")
        return self


class CapabilityBreadthCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    protocol_id: str = Field(min_length=1)
    capability_families: tuple[CapabilityFamily, ...] = CAPABILITY_FAMILY_ORDER
    group_ids: tuple[str, ...] = Field(min_length=16, max_length=16)
    group_counts: dict[CapabilityFamily, int]
    depth_counts: dict[str, int]
    generation_conditions: tuple[CapabilityNeutralGenerationCondition, ...] = Field(
        min_length=4,
        max_length=4,
    )
    retrieval_as_independent_capability: Literal[False] = False
    calculation_as_independent_capability: Literal[False] = False
    verification_as_independent_capability: Literal[False] = False
    nuisance_support_dimensions_only: Literal[True] = True

    @model_validator(mode="after")
    def validate_catalog(self) -> CapabilityBreadthCatalog:
        if self.group_ids != tuple(sorted(set(self.group_ids))):
            raise ValueError("Capability Breadth group IDs are not canonical")
        if self.group_counts != {item: 4 for item in CAPABILITY_FAMILY_ORDER}:
            raise ValueError("Capability Breadth group counts changed")
        if self.depth_counts != {item.value: 16 for item in OBSERVATION_DEPTH_ORDER}:
            raise ValueError("Capability Breadth depth counts changed")
        if tuple(item.capability_family for item in self.generation_conditions) != (
            CAPABILITY_FAMILY_ORDER
        ):
            raise ValueError("Capability Breadth conditions changed")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_capability_breadth_catalog:",
        ):
            raise ValueError("Capability Breadth Catalog identity is invalid")
        return self


class CapabilityObservationGroupCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    partition: ObservationPartition
    groups: tuple[CapabilityObservationGroup, ...] = Field(min_length=8, max_length=8)
    group_count: Literal[8] = 8
    static_task_count: Literal[32] = 32
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> CapabilityObservationGroupCatalog:
        if any(item.partition != self.partition for item in self.groups):
            raise ValueError("Capability Observation Catalog crosses exposure partitions")
        if tuple(item.group_id for item in self.groups) != tuple(
            sorted(item.group_id for item in self.groups)
        ):
            raise ValueError("Capability Observation groups are not canonical")
        if Counter(item.capability_family for item in self.groups) != Counter(
            {item: 2 for item in CAPABILITY_FAMILY_ORDER}
        ):
            raise ValueError("Capability Observation partition is not capability balanced")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            f"capability_observation_{self.partition.value}_group_catalog:",
        ):
            raise ValueError("Capability Observation Catalog identity is invalid")
        return self


class FreshnessChannelRow(FrozenModel):
    channel: Literal[
        "core_semantic_signature",
        "evidence_id",
        "evidence_version_id",
        "group_semantic_identity",
        "mechanism_instance_signature",
        "source_record_id",
        "source_task_id",
        "task_id",
    ]
    historical_or_exposed_count: int = Field(ge=0)
    selected_group_count: int = Field(ge=1)
    overlap_count: Literal[0] = 0


class PairedFreshnessAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    capacity_audit_id: str = Field(min_length=1)
    channels: tuple[FreshnessChannelRow, ...] = Field(min_length=8, max_length=8)
    within_group_core_shared_count: Literal[16] = 16
    within_group_evidence_shared_count: Literal[16] = 16
    within_group_answer_verifier_shared_count: Literal[16] = 16
    within_group_variant_identity_distinct_count: Literal[16] = 16
    cross_group_channel_overlap_count: Literal[0] = 0
    development_confirmation_overlap_count: Literal[0] = 0
    fresh_group_semantic_identity_count: Literal[16] = 16
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_audit(self) -> PairedFreshnessAudit:
        if tuple(item.channel for item in self.channels) != tuple(
            sorted(item.channel for item in self.channels)
        ) or any(item.overlap_count for item in self.channels):
            raise ValueError("Paired Freshness channels changed")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_capability_observation_paired_freshness_audit:",
        ):
            raise ValueError("Paired Freshness audit identity is invalid")
        return self


class RoleDepthPreservationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    signatures: tuple[RoleExecutableDepthSignature, ...] = Field(
        min_length=64,
        max_length=64,
    )
    source_role_signature_match_count: Literal[64] = 64
    distinct_role_task_package_count: Literal[64] = 64
    model_visible_overlay_count: Literal[64] = 64
    compiler_erasure_count: Literal[0] = 0
    compiler_intervention_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_audit(self) -> RoleDepthPreservationAudit:
        if tuple(item.signature_id for item in self.signatures) != tuple(
            sorted(item.signature_id for item in self.signatures)
        ):
            raise ValueError("Role depth signatures are not canonical")
        if len({item.role_task_package_id for item in self.signatures}) != 64:
            raise ValueError("Role compiler erased one or more depth identities")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_role_depth_preservation_audit:",
        ):
            raise ValueError("Role Depth Preservation audit identity is invalid")
        return self


class TerminalEndpointCase(FrozenModel):
    terminal_kind: Literal[
        "completed_endpoint",
        "instrument_failure",
        "measurement_support_exit",
        "model_result_failure",
        "policy_horizon",
        "privacy_rejection",
        "transport_failure",
        "typed_semantic_rejection",
    ]
    endpoint_complete: bool
    task_completion: bool | None
    base_valid: bool | None
    mechanism_endpoint_qualification: bool | None
    qualified_valid: bool | None
    mapping_eligible: bool | None
    task_verifier_invoked: bool


class TerminalEndpointMatrix(FrozenModel):
    matrix_id: str = Field(min_length=1)
    cases: tuple[TerminalEndpointCase, ...] = Field(min_length=8, max_length=8)
    typed_rejection_mechanism_event_evaluable: Literal[False] = False
    typed_rejection_legacy_mechanism_success: None = None
    inherited_support_instrument_overlap_removed: Literal[True] = True

    @model_validator(mode="after")
    def validate_matrix(self) -> TerminalEndpointMatrix:
        names = tuple(item.terminal_kind for item in self.cases)
        if names != tuple(sorted(set(names))):
            raise ValueError("Terminal x Endpoint Matrix is incomplete or noncanonical")
        if self.matrix_id != identity(
            self,
            "matrix_id",
            "finance_v26_capability_observation_terminal_endpoint_matrix:",
        ):
            raise ValueError("Terminal x Endpoint Matrix identity is invalid")
        return self


class StaticGateResult(FrozenModel):
    gate_name: Literal[
        "breadth",
        "confirmation_seal",
        "d0_necessity",
        "d0_nontriviality",
        "depth_delta",
        "exposure_block",
        "group_core_match",
        "max_skeleton_closure",
        "mechanism_necessity",
        "nuisance_stability",
        "paired_freshness",
        "public_witness",
        "resource_equality",
        "role_depth_preservation",
        "runtime_replay",
        "terminal_matrix",
        "tool_closure",
    ]
    passed: Literal[True] = True
    checked_row_count: int = Field(ge=1)
    failure_count: Literal[0] = 0
    evidence_hash: str = Field(min_length=1)


class GroupStaticAuditRow(FrozenModel):
    row_id: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    partition: ObservationPartition
    core_match: Literal[True] = True
    d0_nontrivial: Literal[True] = True
    d0_necessary: Literal[True] = True
    constructive_depth_monotone: Literal[True] = True
    nuisance_stable: Literal[True] = True
    maximum_skeleton_closed: Literal[True] = True
    public_witness_passed: Literal[True] = True
    tool_closure_passed: Literal[True] = True
    runtime_replay_passed: Literal[True] = True
    mechanism_necessity_passed: Literal[True] = True
    role_depth_preserved: Literal[True] = True

    @model_validator(mode="after")
    def validate_row(self) -> GroupStaticAuditRow:
        if self.row_id != identity(
            self,
            "row_id",
            "finance_v26_capability_observation_group_static_audit:",
        ):
            raise ValueError("group static audit row identity is invalid")
        return self


class TaskLadderStaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    protocol_id: str = Field(min_length=1)
    breadth_catalog_id: str = Field(min_length=1)
    group_rows: tuple[GroupStaticAuditRow, ...] = Field(min_length=16, max_length=16)
    gates: tuple[StaticGateResult, ...] = Field(min_length=17, max_length=17)
    noncompensatory_gate_count: Literal[17] = 17
    passed_gate_count: Literal[17] = 17
    failed_gate_count: Literal[0] = 0
    static_task_count: Literal[64] = 64
    provider_calls: Literal[0] = 0
    mapper_calls: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_audit(self) -> TaskLadderStaticAudit:
        if tuple(item.group_id for item in self.group_rows) != tuple(
            sorted(item.group_id for item in self.group_rows)
        ):
            raise ValueError("Task Ladder static group rows are not canonical")
        if tuple(item.gate_name for item in self.gates) != tuple(
            sorted(item.gate_name for item in self.gates)
        ):
            raise ValueError("Task Ladder static gates are not canonical")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_capability_observation_static_audit:",
        ):
            raise ValueError("Task Ladder static audit identity is invalid")
        return self


class CoverageGapDispositionRow(FrozenModel):
    row_id: str = Field(min_length=1)
    historical_coverage_gap_row_id: str = Field(min_length=1)
    historical_compiler_candidate_flag_retained: Literal[True] = True
    prospective_followup_status: Literal[ProspectiveFollowupStatus.UNASSIGNED] = (
        ProspectiveFollowupStatus.UNASSIGNED
    )
    compiler_candidate_authorized: Literal[False] = False
    compiler_intervention_applied: Literal[False] = False
    independent_upgrade_audit_required: Literal[True] = True

    @model_validator(mode="after")
    def validate_row(self) -> CoverageGapDispositionRow:
        if self.row_id != identity(
            self,
            "row_id",
            "finance_v26_coverage_gap_prospective_disposition_row:",
        ):
            raise ValueError("Coverage Gap prospective disposition identity is invalid")
        return self


class CoverageGapDispositionCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    historical_registry_id: str = Field(min_length=1)
    rows: tuple[CoverageGapDispositionRow, ...] = Field(min_length=21, max_length=21)
    unassigned_count: Literal[21] = 21
    compiler_candidate_count: Literal[0] = 0
    historical_row_mutation_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_catalog(self) -> CoverageGapDispositionCatalog:
        if tuple(item.historical_coverage_gap_row_id for item in self.rows) != tuple(
            sorted(item.historical_coverage_gap_row_id for item in self.rows)
        ):
            raise ValueError("Coverage Gap dispositions are not canonical")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "finance_v26_coverage_gap_prospective_disposition_catalog:",
        ):
            raise ValueError("Coverage Gap prospective Catalog identity is invalid")
        return self


class MutationResult(FrozenModel):
    mutation_id: str = Field(min_length=1)
    mutation_name: str = Field(min_length=1)
    detected: Literal[True] = True
    failure_code: str = Field(min_length=1)
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_result(self) -> MutationResult:
        if self.mutation_id != identity(
            self,
            "mutation_id",
            "finance_v26_capability_observation_destructive_mutation:",
        ):
            raise ValueError("destructive mutation identity is invalid")
        return self


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[MutationResult, ...] = Field(min_length=22, max_length=22)
    mutation_count: Literal[22] = 22
    detected_count: Literal[22] = 22
    provider_calls: Literal[0] = 0
    passed: Literal[True] = True

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        if tuple(item.mutation_name for item in self.mutations) != tuple(
            sorted(item.mutation_name for item in self.mutations)
        ):
            raise ValueError("destructive mutations are not canonical")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_capability_observation_destructive_audit:",
        ):
            raise ValueError("destructive audit identity is invalid")
        return self


class TransitionContract(FrozenModel):
    transition_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    exposure_block_contract_id: str = Field(min_length=1)
    boundary_selection_contract_id: str = Field(min_length=1)
    next_stage: Literal["capability_observation_development_runner_preflight_only"] = NEXT_STAGE
    allowed_operations: tuple[str, ...] = (
        "credential_free_development_runner_preflight",
        "development_catalog_only_loading",
        "exact_192_job_development_manifest_materialization",
        "terminal_endpoint_matrix_preflight",
    )
    forbidden_operations: tuple[str, ...] = (
        "compiler_intervention",
        "confirmation_payload_loading",
        "confirmation_provider_execution",
        "current_27_cell_selection",
        "historical_reclassification",
        "mapper_or_state_assignment",
        "provider_execution",
        "threshold_tuning",
        "training_release_or_production",
        "vtdo_or_contribution_estimation",
    )

    @model_validator(mode="after")
    def validate_contract(self) -> TransitionContract:
        if self.allowed_operations != tuple(sorted(set(self.allowed_operations))):
            raise ValueError("v26.167 allowed operations are not canonical")
        if self.forbidden_operations != tuple(sorted(set(self.forbidden_operations))):
            raise ValueError("v26.167 forbidden operations are not canonical")
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_capability_observation_transition:",
        ):
            raise ValueError("v26.167 transition identity is invalid")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class CapabilityBreadthDepthStaticAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    legacy_supersession_id: str = Field(min_length=1)
    historical_tier_boundary_contract_id: str = Field(min_length=1)
    protocol_id: str = Field(min_length=1)
    evidence_capacity_audit_id: str = Field(min_length=1)
    breadth_catalog_id: str = Field(min_length=1)
    development_catalog_id: str = Field(min_length=1)
    sealed_confirmation_catalog_id: str = Field(min_length=1)
    observability_floor_contract_id: str = Field(min_length=1)
    boundary_selection_contract_id: str = Field(min_length=1)
    exposure_block_contract_id: str = Field(min_length=1)
    paired_freshness_audit_id: str = Field(min_length=1)
    role_depth_preservation_audit_id: str = Field(min_length=1)
    terminal_endpoint_matrix_id: str = Field(min_length=1)
    coverage_gap_disposition_catalog_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=18)
    capability_count: Literal[4] = 4
    observation_depth_count: Literal[4] = 4
    matched_group_count: Literal[16] = 16
    static_task_count: Literal[64] = 64
    development_group_count: Literal[8] = 8
    confirmation_group_count: Literal[8] = 8
    role_depth_signature_count: Literal[64] = 64
    noncompensatory_gate_count: Literal[17] = 17
    passed_gate_count: Literal[17] = 17
    destructive_mutation_count: Literal[22] = 22
    historical_artifact_mutation_count: Literal[0] = 0
    empirical_assignment_count: Literal[0] = 0
    development_runner_preflighted: Literal[False] = False
    confirmation_runner_preflighted: Literal[False] = False
    observation_depth_model_behavior_measured: Literal[False] = False
    state_count: Literal[0] = 0
    mapper_calls: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    next_stage: Literal["capability_observation_development_runner_preflight_only"] = NEXT_STAGE
    schema_version: str = RUN_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> CapabilityBreadthDepthStaticAuditReport:
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.167 report detail files are not canonical")
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_capability_breadth_depth_static_audit_report:",
        ):
            raise ValueError("v26.167 report identity is invalid")
        return self


class BuildProducts(FrozenModel):
    authorization: ExternalAuditAuthorization
    source_replay: SourceReplayAudit
    legacy_supersession: LegacyProtocolSupersession
    tier_boundary: HistoricalTierBoundaryContract
    protocol: CapabilityObservationProtocol
    capacity: EvidenceCapacityAudit
    breadth: CapabilityBreadthCatalog
    development: CapabilityObservationGroupCatalog
    confirmation: CapabilityObservationGroupCatalog
    observability_floor: ObservabilityFloorContract
    boundary_selection: BoundarySelectionContract
    exposure_block: ExposureBlockContract
    freshness: PairedFreshnessAudit
    role_depth: RoleDepthPreservationAudit
    terminal_matrix: TerminalEndpointMatrix
    coverage_gap_disposition: CoverageGapDispositionCatalog
    static_audit: TaskLadderStaticAudit
    destructive: DestructiveAudit
    transition: TransitionContract
    report: CapabilityBreadthDepthStaticAuditReport
