from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

CAPABILITY_OBSERVATION_CONTRACT_VERSION = "capability_observation_contract.v1"
MAXIMUM_OBSERVATION_SLOT_COUNT = 3


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CapabilityFamily(str, Enum):
    CONTEXT_CONDITIONED_ACTION = "context_conditioned_action"
    SEMANTIC_RECONCILIATION = "semantic_reconciliation"
    FAILURE_RECOVERY = "failure_recovery"
    STATE_DEPENDENT_STOPPING = "state_dependent_stopping"


class ObservationDepth(str, Enum):
    D0_OBSERVABILITY_ANCHOR = "d0_observability_anchor"
    D1_BASIC = "d1_basic"
    D2_COMPOSITIONAL = "d2_compositional"
    D3_STRESS = "d3_stress"


class EmpiricalBoundaryStatus(str, Enum):
    BELOW_OBSERVATION_FLOOR = "below_observation_floor"
    ABOVE_OBSERVATION_CEILING = "above_observation_ceiling"
    BOUNDARY_BRACKETED = "boundary_bracketed"
    NONMONOTONIC_OR_CONFOUNDED = "nonmonotonic_or_confounded"


class ObservationPartition(str, Enum):
    DEVELOPMENT = "development"
    CONFIRMATION = "confirmation"


class ProspectiveFollowupStatus(str, Enum):
    UNASSIGNED = "unassigned"
    COMPILER_CANDIDATE_AFTER_INDEPENDENT_AUDIT = "compiler_candidate_after_independent_audit"


OBSERVATION_DEPTH_ORDER: tuple[ObservationDepth, ...] = tuple(ObservationDepth)
CAPABILITY_FAMILY_ORDER: tuple[CapabilityFamily, ...] = tuple(CapabilityFamily)

PRIMARY_LOAD_DIMENSIONS: dict[CapabilityFamily, tuple[str, ...]] = {
    CapabilityFamily.CONTEXT_CONDITIONED_ACTION: (
        "ambiguity_load",
        "context_dependency_load",
        "decision_slot_load",
        "delayed_update_load",
        "irreversible_choice_load",
    ),
    CapabilityFamily.SEMANTIC_RECONCILIATION: (
        "downstream_fanout_load",
        "nonidentity_axis_load",
        "normalization_reference_consumption_load",
        "raw_bypass_constraint_load",
        "target_record_load",
    ),
    CapabilityFamily.FAILURE_RECOVERY: (
        "branching_load",
        "consequence_load",
        "dependency_depth_load",
        "failure_type_diversity_load",
        "typed_failure_load",
    ),
    CapabilityFamily.STATE_DEPENDENT_STOPPING: (
        "completion_predicate_load",
        "delayed_readiness_load",
        "near_terminal_load",
        "tempting_continuation_load",
        "verification_separation_load",
    ),
}

InactiveSlotMode = Literal[
    "explicit_nonterminal_state",
    "identity_normalization",
    "nontrigger_recovery_slot",
    "unique_legal_action",
]


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class ObservationSlot(FrozenModel):
    slot_id: str = Field(min_length=1)
    semantic_role: str = Field(min_length=1)
    active: bool
    legal_candidate_count: int = Field(ge=1)
    dependency_slot_ids: tuple[str, ...] = ()
    inactive_mode: InactiveSlotMode | None = None
    delayed_public_update: bool = False
    irreversible_choice: bool = False
    typed_failure_kind: str | None = None
    nonidentity_axes: tuple[str, ...] = ()
    public_witness: dict[str, Any] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_slot(self) -> ObservationSlot:
        if self.dependency_slot_ids != tuple(sorted(set(self.dependency_slot_ids))):
            raise ValueError("observation slot dependencies are not canonical")
        if self.nonidentity_axes != tuple(sorted(set(self.nonidentity_axes))):
            raise ValueError("observation slot axes are not canonical")
        if self.slot_id in self.dependency_slot_ids:
            raise ValueError("observation slot depends on itself")
        if self.active:
            if self.inactive_mode is not None:
                raise ValueError("active observation slot carries an inactive mode")
        elif self.inactive_mode is None or self.legal_candidate_count != 1:
            raise ValueError("inactive observation slot is not a unique inert placeholder")
        return self


class CapabilityDepthOverlay(FrozenModel):
    overlay_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    slots: tuple[ObservationSlot, ...] = Field(
        min_length=MAXIMUM_OBSERVATION_SLOT_COUNT,
        max_length=MAXIMUM_OBSERVATION_SLOT_COUNT,
    )
    primary_load: dict[str, int]
    primary_load_total: int = Field(ge=1)
    nuisance_delta: dict[str, int]
    target_capability_only: Literal[True] = True
    fixed_d3_sized_skeleton: Literal[True] = True
    d0_is_real_mechanism_observation: bool
    historical_difficulty_tier_used_as_depth: Literal[False] = False
    empirical_success_monotonicity_assumed: Literal[False] = False
    schema_version: str = CAPABILITY_OBSERVATION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_overlay(self) -> CapabilityDepthOverlay:
        expected_dimensions = set(PRIMARY_LOAD_DIMENSIONS[self.capability_family])
        if set(self.primary_load) != expected_dimensions:
            raise ValueError("capability depth overlay has the wrong primary-load dimensions")
        if any(not isinstance(value, int) or value < 0 for value in self.primary_load.values()):
            raise ValueError("capability primary loads must be nonnegative integers")
        if self.primary_load_total != sum(self.primary_load.values()):
            raise ValueError("capability primary-load total is inconsistent")
        if not self.nuisance_delta or any(value != 0 for value in self.nuisance_delta.values()):
            raise ValueError("capability depth overlay changes a nuisance dimension")
        slot_ids = tuple(item.slot_id for item in self.slots)
        if slot_ids != tuple(sorted(set(slot_ids))):
            raise ValueError("capability observation slots are not canonical")
        if not any(item.active for item in self.slots):
            raise ValueError("capability observation overlay has no active target slot")
        if (
            self.depth == ObservationDepth.D0_OBSERVABILITY_ANCHOR
            and not self.d0_is_real_mechanism_observation
        ):
            raise ValueError("D0 is not a real mechanism observation")
        if self.overlay_id != _identity(
            self,
            "overlay_id",
            "capability_depth_overlay:",
        ):
            raise ValueError("capability depth overlay identity is invalid")
        return self


class NuisanceSignature(FrozenModel):
    signature_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    source_task_id: str = Field(min_length=1)
    historical_difficulty_tier: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    evidence_version_ids: tuple[str, ...] = Field(min_length=1)
    source_record_ids: tuple[str, ...] = Field(min_length=1)
    core_question_hash: str = Field(min_length=1)
    canonical_result_hash: str = Field(min_length=1)
    answer_schema_hash: str = Field(min_length=1)
    answer_projection_hash: str = Field(min_length=1)
    oracle_program_hash: str = Field(min_length=1)
    verifier_hash: str = Field(min_length=1)
    verification_structure_hash: str = Field(min_length=1)
    tool_ids: tuple[str, ...] = Field(min_length=1)
    tool_environment_contract_id: str = Field(min_length=1)
    prompt_contract_id: str = Field(min_length=1)
    action_grammar_id: str = Field(min_length=1)
    final_grammar_id: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    thinking_policy_id: str = Field(min_length=1)
    bounded_generation_policy_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    maximum_observation_slot_count: Literal[3] = MAXIMUM_OBSERVATION_SLOT_COUNT
    candidate_cap: int = Field(ge=2)

    @model_validator(mode="after")
    def validate_signature(self) -> NuisanceSignature:
        for values in (
            self.evidence_ids,
            self.evidence_version_ids,
            self.source_record_ids,
            self.tool_ids,
        ):
            if values != tuple(sorted(set(values))):
                raise ValueError("nuisance signature set is not canonical")
        if self.signature_id != _identity(
            self,
            "signature_id",
            "capability_observation_nuisance_signature:",
        ):
            raise ValueError("capability nuisance signature identity is invalid")
        return self


class MatchedTaskSkeleton(FrozenModel):
    skeleton_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    source_task_artifact_id: str = Field(min_length=1)
    source_task_id: str = Field(min_length=1)
    historical_difficulty_tier: str = Field(min_length=1)
    core_finance_question: str = Field(min_length=1)
    nuisance_signature: NuisanceSignature
    maximum_depth: Literal[ObservationDepth.D3_STRESS] = ObservationDepth.D3_STRESS
    fixed_evidence_and_program_core: Literal[True] = True
    fixed_answer_and_verifier_core: Literal[True] = True
    fixed_tool_and_resource_core: Literal[True] = True
    inactive_slots_are_explicit_placeholders: Literal[True] = True
    historical_tier_to_observation_depth_mapping_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_skeleton(self) -> MatchedTaskSkeleton:
        if (
            self.nuisance_signature.source_task_artifact_id != self.source_task_artifact_id
            or self.nuisance_signature.source_task_id != self.source_task_id
            or self.nuisance_signature.historical_difficulty_tier != self.historical_difficulty_tier
        ):
            raise ValueError("matched skeleton differs from its nuisance signature")
        if self.skeleton_id != _identity(
            self,
            "skeleton_id",
            "matched_capability_observation_skeleton:",
        ):
            raise ValueError("matched task skeleton identity is invalid")
        return self


class RoleExecutableDepthSignature(FrozenModel):
    signature_id: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    overlay_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    source_task_artifact_id: str = Field(min_length=1)
    role_record_id: str = Field(min_length=1)
    role_task_package_id: str = Field(min_length=1)
    role_environment_manifest_id: str = Field(min_length=1)
    source_primary_load_hash: str = Field(min_length=1)
    role_primary_load_hash: str = Field(min_length=1)
    source_nuisance_signature_id: str = Field(min_length=1)
    role_nuisance_signature_id: str = Field(min_length=1)
    public_overlay_hash: str = Field(min_length=1)
    role_public_overlay_hash: str = Field(min_length=1)
    model_visible: Literal[True] = True
    compiler_intervention_applied: Literal[False] = False
    compiler_erased_depth: Literal[False] = False
    depth_preserved: Literal[True] = True

    @model_validator(mode="after")
    def validate_signature(self) -> RoleExecutableDepthSignature:
        if (
            self.source_primary_load_hash != self.role_primary_load_hash
            or self.source_nuisance_signature_id != self.role_nuisance_signature_id
            or self.public_overlay_hash != self.role_public_overlay_hash
        ):
            raise ValueError("Role compilation changed the observation-depth signature")
        if self.signature_id != _identity(
            self,
            "signature_id",
            "role_executable_depth_signature:",
        ):
            raise ValueError("Role executable depth signature identity is invalid")
        return self


class CapabilityObservationVariant(FrozenModel):
    variant_id: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    partition: ObservationPartition
    capability_family: CapabilityFamily
    depth: ObservationDepth
    skeleton_id: str = Field(min_length=1)
    overlay: CapabilityDepthOverlay
    role_signature: RoleExecutableDepthSignature
    task_identity_is_depth_specific: Literal[True] = True
    group_is_primary_statistical_unit: Literal[True] = True
    rollout_is_secondary_repeated_measure: Literal[True] = True
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_variant(self) -> CapabilityObservationVariant:
        role = self.role_signature
        if (
            self.overlay.capability_family != self.capability_family
            or self.overlay.depth != self.depth
            or role.group_id != self.group_id
            or role.overlay_id != self.overlay.overlay_id
            or role.capability_family != self.capability_family
            or role.depth != self.depth
        ):
            raise ValueError("capability observation variant bindings are inconsistent")
        if self.variant_id != _identity(
            self,
            "variant_id",
            "capability_observation_variant:",
        ):
            raise ValueError("capability observation variant identity is invalid")
        return self


class DepthDeltaRow(FrozenModel):
    from_depth: ObservationDepth
    to_depth: ObservationDepth
    changed_primary_dimensions: tuple[str, ...] = Field(min_length=1)
    primary_deltas: dict[str, int]
    total_delta: int = Field(gt=0)
    nuisance_signature_unchanged: Literal[True] = True

    @model_validator(mode="after")
    def validate_delta(self) -> DepthDeltaRow:
        if self.changed_primary_dimensions != tuple(
            sorted(key for key, value in self.primary_deltas.items() if value > 0)
        ):
            raise ValueError("DepthDelta changed-dimension set is inconsistent")
        if any(value < 0 for value in self.primary_deltas.values()):
            raise ValueError("DepthDelta decreases a primary capability load")
        if self.total_delta != sum(self.primary_deltas.values()):
            raise ValueError("DepthDelta total is inconsistent")
        return self


class DepthDeltaContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    rows: tuple[DepthDeltaRow, ...] = Field(min_length=3, max_length=3)
    constructive_monotonicity_required: Literal[True] = True
    empirical_success_monotonicity_required: Literal[False] = False
    nuisance_invariance_required: Literal[True] = True
    old_difficulty_tier_is_not_depth: Literal[True] = True

    @model_validator(mode="after")
    def validate_contract(self) -> DepthDeltaContract:
        expected_pairs = tuple(
            zip(OBSERVATION_DEPTH_ORDER, OBSERVATION_DEPTH_ORDER[1:], strict=False)
        )
        if tuple((item.from_depth, item.to_depth) for item in self.rows) != expected_pairs:
            raise ValueError("DepthDelta rows do not cover adjacent ObservationDepth values")
        allowed = set(PRIMARY_LOAD_DIMENSIONS[self.capability_family])
        if any(set(item.primary_deltas) != allowed for item in self.rows):
            raise ValueError("DepthDelta row has the wrong primary-load dimensions")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "capability_depth_delta_contract:",
        ):
            raise ValueError("DepthDelta Contract identity is invalid")
        return self


class CapabilityObservationGroup(FrozenModel):
    group_id: str = Field(min_length=1)
    group_index: int = Field(ge=1)
    partition: ObservationPartition
    capability_family: CapabilityFamily
    skeleton: MatchedTaskSkeleton
    variants: tuple[CapabilityObservationVariant, ...] = Field(min_length=4, max_length=4)
    depth_delta_contract: DepthDeltaContract
    exposure_unit_is_whole_group: Literal[True] = True
    partial_variant_regeneration_allowed: Literal[False] = False
    group_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_group(self) -> CapabilityObservationGroup:
        if self.skeleton.capability_family != self.capability_family:
            raise ValueError("matched observation group crosses capabilities")
        if self.depth_delta_contract.group_id != self.group_id:
            raise ValueError("matched observation group has another DepthDelta Contract")
        if self.depth_delta_contract.capability_family != self.capability_family:
            raise ValueError("matched observation group DepthDelta crosses capabilities")
        if tuple(item.depth for item in self.variants) != OBSERVATION_DEPTH_ORDER:
            raise ValueError("matched observation group does not contain ordered D0-D3 variants")
        if any(
            item.group_id != self.group_id
            or item.partition != self.partition
            or item.capability_family != self.capability_family
            or item.skeleton_id != self.skeleton.skeleton_id
            for item in self.variants
        ):
            raise ValueError("matched observation variants differ from their group")
        if len({item.overlay.overlay_id for item in self.variants}) != len(self.variants):
            raise ValueError("matched observation variants repeat a depth overlay")
        if len({item.role_signature.role_task_package_id for item in self.variants}) != len(
            self.variants
        ):
            raise ValueError("Role compiler erased depth-specific task identity")
        nuisance_ids = {item.role_signature.source_nuisance_signature_id for item in self.variants}
        if nuisance_ids != {self.skeleton.nuisance_signature.signature_id}:
            raise ValueError("matched observation variants change nuisance identity")
        if self.group_hash != _identity(
            self,
            "group_hash",
            "capability_observation_group_hash:",
        ):
            raise ValueError("matched observation group hash is invalid")
        return self


class CapabilityObservationProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    capability_families: tuple[CapabilityFamily, ...] = CAPABILITY_FAMILY_ORDER
    observation_depths: tuple[ObservationDepth, ...] = OBSERVATION_DEPTH_ORDER
    groups_per_capability: Literal[4] = 4
    development_groups_per_capability: Literal[2] = 2
    confirmation_groups_per_capability: Literal[2] = 2
    total_group_count: Literal[16] = 16
    total_static_task_count: Literal[64] = 64
    development_static_task_count: Literal[32] = 32
    confirmation_static_task_count: Literal[32] = 32
    development_rollouts_per_variant: Literal[6] = 6
    confirmation_rollouts_per_variant: Literal[8] = 8
    future_development_job_count: Literal[192] = 192
    maximum_future_confirmation_job_count: Literal[128] = 128
    group_is_primary_independent_unit: Literal[True] = True
    rollout_is_secondary_repeated_measure: Literal[True] = True
    all_depths_frozen_before_provider_calls: Literal[True] = True
    one_capability_neutral_condition_per_capability: Literal[True] = True
    all_path_pooling_forbidden: Literal[True] = True
    current_27_cells_used_as_selection_frame: Literal[False] = False
    old_difficulty_tier_used_as_depth: Literal[False] = False
    shallow_results_may_edit_deeper_variants: Literal[False] = False
    mapper_or_vtdo_in_development_scan: Literal[False] = False
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_protocol(self) -> CapabilityObservationProtocol:
        if self.capability_families != CAPABILITY_FAMILY_ORDER:
            raise ValueError("capability observation breadth changed")
        if self.observation_depths != OBSERVATION_DEPTH_ORDER:
            raise ValueError("capability observation depth order changed")
        if self.protocol_id != _identity(
            self,
            "protocol_id",
            "capability_observation_protocol:",
        ):
            raise ValueError("capability observation protocol identity is invalid")
        return self


class ObservabilityFloorContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    d0_requirements: dict[CapabilityFamily, tuple[str, ...]]
    d0_requires_target_mechanism: Literal[True] = True
    d0_single_candidate_context_decision_forbidden: Literal[True] = True
    d0_zero_recovery_event_forbidden: Literal[True] = True
    d0_program_size_used_as_stopping_depth: Literal[False] = False

    @model_validator(mode="after")
    def validate_contract(self) -> ObservabilityFloorContract:
        if set(self.d0_requirements) != set(CAPABILITY_FAMILY_ORDER):
            raise ValueError("observability floor omits a capability")
        if any(not values for values in self.d0_requirements.values()):
            raise ValueError("observability floor has an empty requirement set")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "observability_floor_contract:",
        ):
            raise ValueError("observability floor Contract identity is invalid")
        return self


class BoundarySelectionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    statuses: tuple[EmpiricalBoundaryStatus, ...] = tuple(EmpiricalBoundaryStatus)
    development_support_threshold_numerator: Literal[2] = 2
    development_rollout_denominator: Literal[6] = 6
    confirmation_support_threshold_numerator: Literal[3] = 3
    confirmation_rollout_denominator: Literal[8] = 8
    adjacent_depths_only: Literal[True] = True
    frozen_before_development_execution: Literal[True] = True
    threshold_tuning_after_results_allowed: Literal[False] = False
    outcome_selected_confirmation_group_allowed: Literal[False] = False
    same_confirmation_data_may_support_vtdo: Literal[False] = False

    @model_validator(mode="after")
    def validate_contract(self) -> BoundarySelectionContract:
        if self.statuses != tuple(EmpiricalBoundaryStatus):
            raise ValueError("boundary status language changed")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "capability_boundary_selection_contract:",
        ):
            raise ValueError("Boundary Selection Contract identity is invalid")
        return self


class ExposureBlockContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    development_group_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    confirmation_group_ids: tuple[str, ...] = Field(min_length=8, max_length=8)
    development_catalog_sha256: str = Field(min_length=64, max_length=64)
    sealed_confirmation_catalog_sha256: str = Field(min_length=64, max_length=64)
    group_wide_exposure_rule: Literal[True] = True
    partial_group_regeneration_forbidden: Literal[True] = True
    development_reader_may_access_confirmation_payload: Literal[False] = False
    confirmation_sealed_until_development_audit: Literal[True] = True
    any_variant_exposure_marks_group_exposed: Literal[True] = True

    @model_validator(mode="after")
    def validate_contract(self) -> ExposureBlockContract:
        if (
            self.development_group_ids != tuple(sorted(set(self.development_group_ids)))
            or self.confirmation_group_ids != tuple(sorted(set(self.confirmation_group_ids)))
            or set(self.development_group_ids) & set(self.confirmation_group_ids)
        ):
            raise ValueError("Exposure Block group partitions are invalid")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "capability_observation_exposure_block_contract:",
        ):
            raise ValueError("Exposure Block Contract identity is invalid")
        return self


def require_catalog_partition(
    *,
    catalog_partition: ObservationPartition,
    requested_partition: ObservationPartition,
) -> None:
    if catalog_partition != requested_partition:
        raise ValueError(
            "capability observation catalog access crosses the frozen exposure partition"
        )
