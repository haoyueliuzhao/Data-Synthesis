from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.program import ProgramExecutionError
from trusted_synthesis.domains.finance.capability_submechanism_runtime import (
    FINANCE_SUBMECHANISM_RUNTIME_VERSION,
    FinanceStoppingDependencyOption,
    FinanceStoppingMeasurementContext,
    FinanceStoppingObservedEvidenceState,
    FinanceStoppingObservedRecord,
    FinanceStoppingResolutionAction,
    FinanceStoppingShapeDecisionContract,
    FinanceStoppingTemporalIdentity,
    SubmechanismKind,
    make_finance_submechanism_scenario,
    make_submechanism_manifest,
    submechanism_policy_manifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    MAXIMUM_FAILED_TOOL_CALLS,
    MAXIMUM_OBSERVATION_BYTES,
    MAXIMUM_TOOL_CALLS,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_development import (
    _candidate_iterator,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    RecoveryBranch,
    _CapabilityTaskBuilder,
    _load_evidence_pool,
    _minimum_mismatch_fields,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_direction_design import (  # noqa: E501
    CapabilitySubmechanismSpec,
    _graph,
    _linear_graph,
    _node,
    _spec,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_population import (  # noqa: E501
    _RECOVERY_BRANCH_KINDS,
    PUBLIC_SUBMECHANISM_METADATA_KEY,
    _answer_contract_ready,
    _freeze_scenario,
    _make_scenario,
    _select_distractor,
    replay_submechanism_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_stability_protocol import (
    SHAPE_COUNT,
    STRUCTURAL_STRATA,
    FrozenArtifactReference,
    StoppingShapeTask,
    _collect_excluded_identities,
    _difficulty_vector,
    _public_task_isolated,
    _rate,
    stopping_shape_task_id,
)
from trusted_synthesis.hashing import canonical_hash

STOPPING_SHAPE_POLICY_PROTOCOL_VERSION = "finance_stopping_shape_policy_protocol.v8"
STOPPING_SHAPE_POLICY_POPULATION_VERSION = "finance_stopping_shape_policy_population.v8"
STOPPING_SHAPE_POLICY_AUDIT_VERSION = "finance_stopping_shape_policy_static_audit.v8"
STOPPING_SHAPE_POLICY_EXPERIMENT_LABEL = "finance_v25_44_stopping_shape_policy_development"

TASKS_PER_STRATUM = 2
TASKS_PER_SHAPE = len(STRUCTURAL_STRATA) * TASKS_PER_STRATUM
EXPECTED_TASK_COUNT = SHAPE_COUNT * TASKS_PER_SHAPE
REPLICAS = 8
EXPECTED_ROLLOUT_COUNT = EXPECTED_TASK_COUNT * REPLICAS

BOUNDARY_CANDIDATE_SHAPES = frozenset(
    {
        "authority_coverage_gap",
        "contextual_resolution_choice",
        "partial_required_evidence",
        "single_dimension_conflict",
    }
)
RUNTIME_CONTROL_SHAPES = frozenset(
    {
        "verified_extra_call_cost",
        "verified_extra_call_error_risk",
    }
)
UNCHANGED_REGRESSION_SHAPES = frozenset(
    {
        "authority_coverage_gap",
        "partial_required_evidence",
        "verified_extra_call_cost",
        "verified_extra_call_error_risk",
    }
)
STRUCTURAL_REDESIGN_SHAPES = frozenset(
    {
        "contextual_resolution_choice",
        "single_dimension_conflict",
    }
)
ALL_SHAPES = BOUNDARY_CANDIDATE_SHAPES | RUNTIME_CONTROL_SHAPES

TARGET_ROLE_INDEX_BY_SHAPE: dict[str, int] = {
    "contextual_resolution_choice": 1,
    "single_dimension_conflict": 2,
}
TARGET_ROLE_ID_BY_SHAPE: dict[str, str] = {
    shape_id: f"required_{index + 1}" for shape_id, index in TARGET_ROLE_INDEX_BY_SHAPE.items()
}

CONFLICT_MISMATCH_BY_CELL: dict[tuple[str, int], str] = {
    ("retrieval_join_frontier", 0): "period",
    ("retrieval_join_frontier", 1): "definition",
    ("calculation_chain_frontier", 0): "definition",
    ("calculation_chain_frontier", 1): "period",
    ("definition_reconciliation_frontier", 0): "period",
    ("definition_reconciliation_frontier", 1): "period",
    ("verification_selection_frontier", 0): "period",
    ("verification_selection_frontier", 1): "period",
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StoppingShapePolicyThresholds(FrozenModel):
    boundary_probability_lower: float = Field(default=0.125, ge=0, le=1)
    boundary_probability_upper: float = Field(default=0.875, ge=0, le=1)
    minimum_boundary_tasks_per_candidate_shape: int = Field(default=4, ge=1, le=8)
    minimum_nonzero_tasks_per_candidate_shape: int = Field(default=6, ge=1, le=8)
    minimum_effective_task_count: float = Field(default=4.0, ge=1, le=8)
    maximum_single_task_information_share: float = Field(default=0.35, gt=0, le=1)
    maximum_between_task_probability_range: float = Field(default=0.75, ge=0, le=1)
    minimum_control_shape_success_rate: float = Field(default=0.75, ge=0, le=1)
    minimum_runtime_execution_integrity: float = Field(default=1.0, ge=1, le=1)
    minimum_terminal_resolution_rate: float = Field(default=1.0, ge=1, le=1)
    minimum_observation_replay_rate: float = Field(default=1.0, ge=1, le=1)
    minimum_authority_integrity_rate: float = Field(default=1.0, ge=1, le=1)
    maximum_runtime_pathology_rate: float = Field(default=0.0, ge=0, le=0)
    maximum_l0_l2_failure_count: int = Field(default=0, ge=0, le=0)
    minimum_conflict_tasks_per_resolution_tool: int = Field(default=2, ge=2, le=4)
    maximum_conflict_resolution_tool_share: float = Field(default=0.75, ge=0.5, le=0.75)
    bootstrap_replicates: int = Field(default=4_000, ge=1_000)
    bootstrap_seed: int = 20260818

    @model_validator(mode="after")
    def validate_thresholds(self) -> StoppingShapePolicyThresholds:
        if self.boundary_probability_lower >= self.boundary_probability_upper:
            raise ValueError("Stopping Shape policy boundary interval is empty")
        return self


class StoppingShapePolicyDefinition(FrozenModel):
    stopping_behavior_response: Literal["stopping_behavior_success"] = "stopping_behavior_success"
    stopping_behavior_expression: Literal[
        "runtime_eligible AND host_event_ordered AND NOT post_completion_violation"
    ] = "runtime_eligible AND host_event_ordered AND NOT post_completion_violation"
    full_valid_trajectory_response: Literal["full_valid_trajectory_success"] = (
        "full_valid_trajectory_success"
    )
    full_valid_trajectory_expression: Literal[
        "stopping_behavior_success AND terminal.valid_success"
    ] = "stopping_behavior_success AND terminal.valid_success"
    answer_semantic_response: Literal["answer_semantic_success"] = "answer_semantic_success"
    answer_semantic_expression: Literal["terminal.semantic_answer_correct"] = (
        "terminal.semantic_answer_correct"
    )
    mechanism_observable_support_response: Literal["stopping_behavior_success"] = (
        "stopping_behavior_success"
    )
    valid_training_support_response: Literal["full_valid_trajectory_success"] = (
        "full_valid_trajectory_success"
    )
    contribution_authorized_support_response: Literal["not_evaluated_in_v25_44"] = (
        "not_evaluated_in_v25_44"
    )
    cross_estimand_rescue_forbidden: Literal[True] = True
    invalid_trajectory_training_use_forbidden: Literal[True] = True
    estimand_semantics_frozen: Literal[True] = True
    shape_support_policy_frozen: Literal[False] = False
    historical_v25_38_reclassification_authorized: Literal[False] = False


class StoppingPredecessorMeasurementAudit(FrozenModel):
    affected_shape_ids: tuple[
        Literal["contextual_resolution_choice", "single_dimension_conflict"], ...
    ] = ("contextual_resolution_choice", "single_dimension_conflict")
    rollout_counts: dict[str, int]
    runtime_eligible_counts: dict[str, int]
    trigger_observed_counts: dict[str, int]
    resolution_observed_counts: dict[str, int]
    host_event_ordered_counts: dict[str, int]
    measurement_valid: Literal[False] = False
    invalid_reason: Literal["activation_event_not_emitted_to_tool_observation"] = (
        "activation_event_not_emitted_to_tool_observation"
    )
    historical_result_reinterpretation_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_audit(self) -> StoppingPredecessorMeasurementAudit:
        expected_shapes = {
            "contextual_resolution_choice",
            "single_dimension_conflict",
        }
        mappings = (
            self.rollout_counts,
            self.runtime_eligible_counts,
            self.trigger_observed_counts,
            self.resolution_observed_counts,
            self.host_event_ordered_counts,
        )
        if any(set(item) != expected_shapes for item in mappings):
            raise ValueError("v25.41 measurement audit Shape coverage is incomplete")
        if self.rollout_counts != {shape: 64 for shape in expected_shapes}:
            raise ValueError("v25.41 measurement audit rollout denominator changed")
        if self.runtime_eligible_counts != {shape: 64 for shape in expected_shapes}:
            raise ValueError("v25.41 affected Shape Runtime was not fully eligible")
        if self.trigger_observed_counts != {shape: 0 for shape in expected_shapes}:
            raise ValueError("v25.41 activation visibility diagnosis changed")
        if self.host_event_ordered_counts != {shape: 0 for shape in expected_shapes}:
            raise ValueError("v25.41 ordered-event diagnosis changed")
        if self.resolution_observed_counts != {
            "contextual_resolution_choice": 18,
            "single_dimension_conflict": 12,
        }:
            raise ValueError("v25.41 resolution diagnostic counts changed")
        return self


class StoppingToolPayloadMeasurementAudit(FrozenModel):
    affected_shape_ids: tuple[
        Literal["contextual_resolution_choice", "single_dimension_conflict"], ...
    ] = ("contextual_resolution_choice", "single_dimension_conflict")
    rollout_counts: dict[str, int]
    completed_counts: dict[str, int]
    trigger_observed_counts: dict[str, int]
    resolution_observed_counts: dict[str, int]
    host_event_ordered_counts: dict[str, int]
    tool_payload_schema_failure_counts: dict[str, int]
    reported_runtime_pathology_counts: dict[str, int]
    measurement_valid: Literal[False] = False
    invalid_reason: Literal["host_event_metadata_injected_into_strict_tool_result_payload"] = (
        "host_event_metadata_injected_into_strict_tool_result_payload"
    )
    historical_result_reinterpretation_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_audit(self) -> StoppingToolPayloadMeasurementAudit:
        expected_shapes = {
            "contextual_resolution_choice",
            "single_dimension_conflict",
        }
        mappings = (
            self.rollout_counts,
            self.completed_counts,
            self.trigger_observed_counts,
            self.resolution_observed_counts,
            self.host_event_ordered_counts,
            self.tool_payload_schema_failure_counts,
            self.reported_runtime_pathology_counts,
        )
        if any(set(item) != expected_shapes for item in mappings):
            raise ValueError("v25.42 tool-payload audit Shape coverage is incomplete")
        if self.rollout_counts != {shape: 64 for shape in expected_shapes}:
            raise ValueError("v25.42 tool-payload audit rollout denominator changed")
        if self.completed_counts != {
            "contextual_resolution_choice": 22,
            "single_dimension_conflict": 8,
        }:
            raise ValueError("v25.42 completed-record diagnosis changed")
        if self.trigger_observed_counts != {
            "contextual_resolution_choice": 54,
            "single_dimension_conflict": 37,
        }:
            raise ValueError("v25.42 trigger visibility counts changed")
        if self.resolution_observed_counts != {
            "contextual_resolution_choice": 29,
            "single_dimension_conflict": 13,
        }:
            raise ValueError("v25.42 resolution counts changed")
        if self.host_event_ordered_counts != self.resolution_observed_counts:
            raise ValueError("v25.42 ordered-event diagnosis changed")
        if self.tool_payload_schema_failure_counts != {
            "contextual_resolution_choice": 10,
            "single_dimension_conflict": 27,
        }:
            raise ValueError("v25.42 strict tool-payload failure counts changed")
        if self.reported_runtime_pathology_counts != {shape: 0 for shape in expected_shapes}:
            raise ValueError("v25.42 Runtime-pathology misclassification diagnosis changed")
        return self


class StoppingRolePositionPredecessorAudit(FrozenModel):
    affected_shape_ids: tuple[
        Literal["contextual_resolution_choice", "single_dimension_conflict"], ...
    ] = ("contextual_resolution_choice", "single_dimension_conflict")
    role_task_counts: dict[str, dict[str, int]]
    role_stopping_probability_vectors: dict[str, dict[str, tuple[float, ...]]]
    selected_target_role_ids: dict[str, str] = Field(
        default_factory=lambda: dict(TARGET_ROLE_ID_BY_SHAPE)
    )
    measurement_valid: Literal[True] = True
    redesign_basis: Literal["required_role_position_is_a_measured_nuisance_factor"] = (
        "required_role_position_is_a_measured_nuisance_factor"
    )
    historical_result_transfer_authorized: Literal[False] = False

    @model_validator(mode="after")
    def validate_audit(self) -> StoppingRolePositionPredecessorAudit:
        expected_counts = {
            "contextual_resolution_choice": {"required_1": 4, "required_2": 4},
            "single_dimension_conflict": {"required_1": 4, "required_3": 4},
        }
        expected_vectors = {
            "contextual_resolution_choice": {
                "required_1": (0.875, 1.0, 1.0, 1.0),
                "required_2": (0.0, 0.25, 0.25, 0.375),
            },
            "single_dimension_conflict": {
                "required_1": (0.625, 0.75, 1.0, 1.0),
                "required_3": (0.125, 0.625, 0.625, 0.75),
            },
        }
        if self.role_task_counts != expected_counts:
            raise ValueError("v25.43 required-role task counts changed")
        if self.role_stopping_probability_vectors != expected_vectors:
            raise ValueError("v25.43 required-role response vectors changed")
        if self.selected_target_role_ids != TARGET_ROLE_ID_BY_SHAPE:
            raise ValueError("v25.44 target-role policy changed")
        return self


class StoppingConflictCellAllocation(FrozenModel):
    stratum_id: str = Field(min_length=1)
    instance_index: Literal[0, 1]
    mismatch_field: Literal["period", "definition"]
    expected_resolution_tool: Literal["query_structured_fact", "normalize_metric_unit_period"]

    @model_validator(mode="after")
    def validate_allocation(self) -> StoppingConflictCellAllocation:
        expected_tool = (
            "query_structured_fact"
            if self.mismatch_field == "period"
            else "normalize_metric_unit_period"
        )
        if self.expected_resolution_tool != expected_tool:
            raise ValueError("Stopping conflict allocation uses the wrong resolution tool")
        return self


def _default_conflict_cell_allocations() -> tuple[StoppingConflictCellAllocation, ...]:
    return tuple(
        StoppingConflictCellAllocation(
            stratum_id=stratum_id,
            instance_index=cast(Any, instance_index),
            mismatch_field=cast(Any, mismatch_field),
            expected_resolution_tool=(
                "query_structured_fact"
                if mismatch_field == "period"
                else "normalize_metric_unit_period"
            ),
        )
        for (stratum_id, instance_index), mismatch_field in sorted(
            CONFLICT_MISMATCH_BY_CELL.items()
        )
    )


class StoppingShapePolicyDesign(FrozenModel):
    shape_id: str = Field(min_length=1)
    shape_role: Literal["boundary_candidate", "runtime_control"]
    early_stop_consequence: str = Field(min_length=1)
    source_spec_id: str = Field(min_length=1)
    source_spec_hash: str = Field(min_length=1)
    source_result_admitted: bool
    historical_result_transfer_authorized: Literal[False] = False
    design_status: Literal["boundary_regression", "instrument_regression", "structural_redesign"]
    spec: CapabilitySubmechanismSpec
    intervention_kind: SubmechanismKind
    decision_contract_kind: (
        Literal[
            "conditional_dependency_observation_required",
            "matched_contextual_evidence_state_choice_two_step",
            "single_conflict_evidence_state_choice_one_step",
            "sealed_terminal_extra_call_cost",
        ]
        | None
    ) = None
    expected_task_instances: Literal[8] = 8

    @model_validator(mode="after")
    def validate_design(self) -> StoppingShapePolicyDesign:
        if self.shape_id not in ALL_SHAPES:
            raise ValueError("Stopping Shape policy contains an unknown Shape")
        expected_role = (
            "boundary_candidate"
            if self.shape_id in BOUNDARY_CANDIDATE_SHAPES
            else "runtime_control"
        )
        if self.shape_role != expected_role:
            raise ValueError("Stopping Shape policy assigns the wrong Shape role")
        if self.spec.runtime_contract.intervention_kind != self.intervention_kind:
            raise ValueError("Stopping Shape policy Runtime kind differs from its spec")
        if self.spec.runtime_contract.implementation_status != (
            "host_and_materializer_implemented"
        ):
            raise ValueError("Stopping Shape policy lacks an implemented Runtime")
        expected = {
            "authority_coverage_gap": ("boundary_regression", None),
            "contextual_resolution_choice": (
                "structural_redesign",
                "matched_contextual_evidence_state_choice_two_step",
            ),
            "partial_required_evidence": (
                "boundary_regression",
                "conditional_dependency_observation_required",
            ),
            "single_dimension_conflict": (
                "structural_redesign",
                "single_conflict_evidence_state_choice_one_step",
            ),
            "verified_extra_call_cost": (
                "instrument_regression",
                "sealed_terminal_extra_call_cost",
            ),
            "verified_extra_call_error_risk": ("instrument_regression", None),
        }[self.shape_id]
        if (self.design_status, self.decision_contract_kind) != expected:
            raise ValueError("Stopping Shape policy design status is inconsistent")
        return self


class FinanceStoppingShapePolicyProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_label: Literal["finance_v25_44_stopping_shape_policy_development"] = (
        "finance_v25_44_stopping_shape_policy_development"
    )
    source_v25_43_protocol: FrozenArtifactReference
    source_v25_43_population: FrozenArtifactReference
    source_v25_43_contract: FrozenArtifactReference
    source_v25_43_report: FrozenArtifactReference
    source_v25_43_manifest: FrozenArtifactReference
    source_v25_43_records: FrozenArtifactReference
    source_v25_43_terminal_outcomes: FrozenArtifactReference
    source_v25_43_behavior_diagnostics: FrozenArtifactReference
    predecessor_role_position_audit: StoppingRolePositionPredecessorAudit
    source_finance_artifacts: FrozenArtifactReference
    source_calibration_contract: FrozenArtifactReference
    historical_population_references: tuple[FrozenArtifactReference, ...] = Field(min_length=40)
    estimand_definition: StoppingShapePolicyDefinition = Field(
        default_factory=StoppingShapePolicyDefinition
    )
    shape_designs: tuple[StoppingShapePolicyDesign, ...] = Field(
        min_length=SHAPE_COUNT, max_length=SHAPE_COUNT
    )
    conflict_cell_allocations: tuple[StoppingConflictCellAllocation, ...] = Field(
        default_factory=_default_conflict_cell_allocations,
        min_length=8,
        max_length=8,
    )
    target_role_ids: dict[str, str] = Field(default_factory=lambda: dict(TARGET_ROLE_ID_BY_SHAPE))
    conflict_allocation_basis: Literal[
        "exact_one_difference_capacity_preflight_on_frozen_snapshot"
    ] = "exact_one_difference_capacity_preflight_on_frozen_snapshot"
    unsupported_conflict_dimensions: tuple[Literal["payload_context"], ...] = ("payload_context",)
    structural_strata: tuple[tuple[str, str, DifficultyTier], ...] = STRUCTURAL_STRATA
    thresholds: StoppingShapePolicyThresholds = Field(default_factory=StoppingShapePolicyThresholds)
    tasks_per_stratum: Literal[2] = 2
    tasks_per_shape: Literal[8] = 8
    task_count: Literal[48] = 48
    replicas: Literal[8] = 8
    rollout_count: Literal[384] = 384
    task_instance_is_primary_sampling_unit: Literal[True] = True
    same_task_replica_increase_forbidden: Literal[True] = True
    pooled_result_may_rescue_shape_failure: Literal[False] = False
    cross_estimand_rescue_forbidden: Literal[True] = True
    posthoc_task_selection_authorized: Literal[False] = False
    posthoc_task_deletion_authorized: Literal[False] = False
    historical_results_reclassified: Literal[False] = False
    historical_results_transfer_authorized: Literal[False] = False
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["stopping_shape_policy_population_build"] = (
        "stopping_shape_policy_population_build"
    )
    schema_version: str = STOPPING_SHAPE_POLICY_PROTOCOL_VERSION

    @model_validator(mode="after")
    def validate_protocol(self) -> FinanceStoppingShapePolicyProtocol:
        if self.structural_strata != STRUCTURAL_STRATA:
            raise ValueError("Stopping Shape policy structural strata changed")
        if {item.shape_id for item in self.shape_designs} != ALL_SHAPES:
            raise ValueError("Stopping Shape policy coverage is incomplete")
        if len({item.intervention_kind for item in self.shape_designs}) != SHAPE_COUNT:
            raise ValueError("Stopping Shape policy Runtime kinds are duplicated")
        if self.conflict_cell_allocations != _default_conflict_cell_allocations():
            raise ValueError("Stopping Shape policy conflict allocation changed")
        expected_cells = {
            (stratum_id, instance_index)
            for stratum_id, _, _ in STRUCTURAL_STRATA
            for instance_index in range(TASKS_PER_STRATUM)
        }
        observed_cells = {
            (item.stratum_id, item.instance_index) for item in self.conflict_cell_allocations
        }
        if observed_cells != expected_cells:
            raise ValueError("Stopping Shape policy conflict Cell coverage is incomplete")
        if len({item.artifact_id for item in self.historical_population_references}) != len(
            self.historical_population_references
        ):
            raise ValueError("Stopping Shape policy historical populations are duplicated")
        historical_ids = {item.artifact_id for item in self.historical_population_references}
        if self.source_v25_43_population.artifact_id not in historical_ids:
            raise ValueError("v25.43 Population is absent from the freshness exclusion set")
        if not self.predecessor_role_position_audit.measurement_valid:
            raise ValueError("v25.44 requires a measurement-valid v25.43 predecessor")
        if self.target_role_ids != TARGET_ROLE_ID_BY_SHAPE:
            raise ValueError("v25.44 target-role position policy changed")
        if self.estimand_definition != StoppingShapePolicyDefinition():
            raise ValueError("Stopping Shape policy definition changed")
        if self.protocol_id != stopping_shape_policy_protocol_id(self):
            raise ValueError("Stopping Shape policy protocol identity is invalid")
        return self


class StoppingShapePolicyStaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_count: int = Field(ge=1)
    shape_task_counts: dict[str, int]
    shape_role_task_counts: dict[str, int]
    stratum_task_counts: dict[str, int]
    shape_stratum_task_counts: dict[str, int]
    design_status_task_counts: dict[str, int]
    boundary_candidate_task_count: int = Field(ge=0)
    runtime_control_task_count: int = Field(ge=0)
    unchanged_regression_task_count: int = Field(ge=0)
    structural_redesign_task_count: int = Field(ge=0)
    operation_replay_rate: float = Field(ge=0, le=1)
    host_replay_rate: float = Field(ge=0, le=1)
    public_oracle_isolation_rate: float = Field(ge=0, le=1)
    answer_contract_rate: float = Field(ge=0, le=1)
    public_decision_contract_rate: float = Field(ge=0, le=1)
    causal_state_action_graph_rate: float = Field(ge=0, le=1)
    conditional_dependency_contract_rate: float = Field(ge=0, le=1)
    conditional_dependency_output_contract_rate: float = Field(ge=0, le=1)
    matched_contextual_contract_rate: float = Field(ge=0, le=1)
    grounded_conflict_contract_rate: float = Field(ge=0, le=1)
    conflict_mismatch_dimension_counts: dict[str, int]
    conflict_resolution_tool_counts: dict[str, int]
    conflict_mismatch_balance_frozen: bool
    conflict_resolution_tool_diversity_frozen: bool
    sealed_cost_contract_rate: float = Field(ge=0, le=1)
    dependency_decoy_one_dimensional_rate: float = Field(ge=0, le=1)
    contextual_conflict_decoy_one_dimensional_rate: float = Field(ge=0, le=1)
    lexical_conflict_leakage_count: int = Field(ge=0, le=0)
    contextual_task_construction_matched: bool
    target_role_ids: dict[str, str]
    target_role_control_rate: float = Field(ge=0, le=1)
    target_role_position_control_frozen: bool
    within_population_evidence_disjoint: bool
    historical_task_disjoint: bool
    historical_evidence_disjoint: bool
    historical_evidence_version_disjoint: bool
    historical_semantic_signature_disjoint: bool
    historical_materializer_disjoint: bool
    estimand_semantics_frozen_pre_api: bool
    shape_support_policy_unfrozen_pre_api: bool
    historical_result_transfer_forbidden: bool
    structural_redesign_scoped: bool
    unchanged_regressions_scoped: bool
    exact_shape_stratum_redundancy: bool
    task_expected_host_events_frozen_pre_api: bool
    rejection_reasons: tuple[str, ...]
    ready: bool
    next_permitted_stage: Literal[
        "flash_stopping_shape_policy_development",
        "stopping_shape_policy_population_repair_only",
    ]
    schema_version: str = STOPPING_SHAPE_POLICY_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StoppingShapePolicyStaticAudit:
        expected = not self.rejection_reasons
        if self.ready != expected:
            raise ValueError("Stopping Shape policy static decision is inconsistent")
        if self.boundary_candidate_task_count != 32:
            raise ValueError("Stopping Shape policy boundary denominator changed")
        if self.runtime_control_task_count != 16:
            raise ValueError("Stopping Shape policy control denominator changed")
        if self.unchanged_regression_task_count != 32:
            raise ValueError("Stopping Shape policy regression denominator changed")
        if self.structural_redesign_task_count != 16:
            raise ValueError("Stopping Shape policy redesign denominator changed")
        if self.target_role_ids != TARGET_ROLE_ID_BY_SHAPE:
            raise ValueError("Stopping Shape policy target-role map changed")
        if self.target_role_control_rate != 1.0 or not self.target_role_position_control_frozen:
            raise ValueError("Stopping Shape policy target-role control is incomplete")
        expected_stage = (
            "flash_stopping_shape_policy_development"
            if expected
            else "stopping_shape_policy_population_repair_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("Stopping Shape policy transition is not fail-closed")
        if self.audit_id != stopping_shape_policy_static_audit_id(self):
            raise ValueError("Stopping Shape policy audit identity is invalid")
        return self


class FinanceStoppingShapePolicyPopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    protocol_path: str = Field(min_length=1)
    protocol_sha256: str = Field(min_length=64, max_length=64)
    protocol_id: str = Field(min_length=1)
    tasks: tuple[StoppingShapeTask, ...] = Field(
        min_length=EXPECTED_TASK_COUNT, max_length=EXPECTED_TASK_COUNT
    )
    task_stratum_instance_indices: dict[str, int]
    task_design_statuses: dict[
        str, Literal["boundary_regression", "instrument_regression", "structural_redesign"]
    ]
    task_expected_host_events: dict[str, tuple[str, str]]
    static_audit: StoppingShapePolicyStaticAudit
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    model_api_calls: Literal[0] = 0
    model_tokens: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    pro_api_calls_authorized: Literal[False] = False
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "flash_stopping_shape_policy_development",
        "stopping_shape_policy_population_repair_only",
    ]
    schema_version: str = STOPPING_SHAPE_POLICY_POPULATION_VERSION

    @model_validator(mode="after")
    def validate_population(self) -> FinanceStoppingShapePolicyPopulation:
        task_ids = {item.artifact.artifact_id for item in self.tasks}
        if any(
            set(mapping) != task_ids
            for mapping in (
                self.task_stratum_instance_indices,
                self.task_design_statuses,
                self.task_expected_host_events,
            )
        ):
            raise ValueError("Stopping Shape policy task maps are incomplete")
        if set(self.task_stratum_instance_indices.values()) != {0, 1}:
            raise ValueError("Stopping Shape policy lacks both stratum instances")
        if self.next_permitted_stage != self.static_audit.next_permitted_stage:
            raise ValueError("Stopping Shape policy population differs from its audit")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest,
            prefix="finance_stopping_shape_policy_population_implementation:",
        ):
            raise ValueError("Stopping Shape policy implementation identity is invalid")
        if self.population_id != stopping_shape_policy_population_id(self):
            raise ValueError("Stopping Shape policy population identity is invalid")
        return self


def stopping_shape_policy_protocol_id(
    value: FinanceStoppingShapePolicyProtocol,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"protocol_id"}),
        prefix="finance_stopping_shape_policy_protocol:",
    )


def stopping_shape_policy_static_audit_id(
    value: StoppingShapePolicyStaticAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_stopping_shape_policy_static_audit:",
    )


def stopping_shape_policy_population_id(
    value: FinanceStoppingShapePolicyPopulation,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"population_id"}),
        prefix="finance_stopping_shape_policy_population:",
    )


def _artifact_identity_matches(
    payload: Mapping[str, Any], *, identity_field: str, prefix: str
) -> bool:
    identity = str(payload.get(identity_field, ""))
    return bool(
        identity
        and identity
        == canonical_hash(
            {key: value for key, value in payload.items() if key != identity_field},
            prefix=prefix,
        )
    )


def prepare_stopping_shape_policy_protocol(
    *,
    source_v25_43_protocol_path: Path,
    source_v25_43_population_path: Path,
    source_v25_43_contract_path: Path,
    source_v25_43_report_path: Path,
    source_v25_43_manifest_path: Path,
    source_v25_43_records_path: Path,
    source_v25_43_terminal_outcomes_path: Path,
    source_v25_43_behavior_diagnostics_path: Path,
    output_path: Path,
    run_id: str,
    source_finance_artifacts_path: Path | None = None,
    source_finance_artifacts_id: str | None = None,
    additional_historical_population_paths: tuple[Path, ...] = (),
) -> FinanceStoppingShapePolicyProtocol:
    if output_path.exists():
        raise ValueError("Stopping Shape policy protocol is immutable")
    source_paths = tuple(
        path.resolve()
        for path in (
            source_v25_43_protocol_path,
            source_v25_43_population_path,
            source_v25_43_contract_path,
            source_v25_43_report_path,
        )
    )
    manifest_path = source_v25_43_manifest_path.resolve()
    records_path = source_v25_43_records_path.resolve()
    terminal_path = source_v25_43_terminal_outcomes_path.resolve()
    behavior_path = source_v25_43_behavior_diagnostics_path.resolve()
    payloads = tuple(json.loads(path.read_text(encoding="utf-8")) for path in source_paths)
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if any(not isinstance(item, Mapping) for item in (*payloads, manifest_payload)):
        raise ValueError("v25.43 frozen predecessor artifacts are not JSON objects")
    protocol_payload, population_payload, contract_payload, report_payload = payloads
    protocol_id = str(protocol_payload.get("protocol_id", ""))
    population_id = str(population_payload.get("population_id", ""))
    contract_id = str(contract_payload.get("contract_id", ""))
    report_id = str(report_payload.get("report_id", ""))
    contract_protocol = contract_payload.get("source_protocol")
    contract_population = contract_payload.get("source_population")
    history_payload = protocol_payload.get("historical_population_references")
    task_shape_ids = contract_payload.get("task_shape_ids")
    task_payloads = population_payload.get("tasks")
    shape_results = report_payload.get("shape_results")
    if not (
        isinstance(contract_protocol, Mapping)
        and isinstance(contract_population, Mapping)
        and isinstance(history_payload, list)
        and isinstance(task_shape_ids, Mapping)
        and isinstance(task_payloads, list)
        and isinstance(shape_results, list)
    ):
        raise ValueError("v25.43 frozen predecessor lacks typed lineage or task results")
    history = tuple(FrozenArtifactReference.model_validate(item) for item in history_payload)
    admitted = {
        str(item.get("shape_id"))
        for item in shape_results
        if isinstance(item, Mapping) and bool(item.get("admitted"))
    }
    expected_admitted = {
        "authority_coverage_gap",
        "partial_required_evidence",
        "verified_extra_call_cost",
        "verified_extra_call_error_risk",
    }
    if not (
        protocol_id
        and population_id
        and contract_id
        and report_id
        and _artifact_identity_matches(
            protocol_payload,
            identity_field="protocol_id",
            prefix="finance_stopping_shape_policy_protocol:",
        )
        and _artifact_identity_matches(
            population_payload,
            identity_field="population_id",
            prefix="finance_stopping_shape_policy_population:",
        )
        and _artifact_identity_matches(
            contract_payload,
            identity_field="contract_id",
            prefix="finance_stopping_shape_policy_contract:",
        )
        and _artifact_identity_matches(
            report_payload,
            identity_field="report_id",
            prefix="finance_stopping_shape_policy_report:",
        )
        and str(contract_protocol.get("sha256")) == _sha256(source_paths[0])
        and str(contract_population.get("sha256")) == _sha256(source_paths[1])
        and str(protocol_payload.get("schema_version"))
        == "finance_stopping_shape_policy_protocol.v7"
        and str(population_payload.get("schema_version"))
        == "finance_stopping_shape_policy_population.v7"
        and str(contract_payload.get("schema_version"))
        == "finance_stopping_shape_policy_contract.v7"
        and str(report_payload.get("schema_version")) == "finance_stopping_shape_policy_report.v7"
        and str(manifest_payload.get("schema_version"))
        == "finance_stopping_shape_policy_manifest.v7"
        and str(population_payload.get("protocol_id")) == protocol_id
        and str(contract_protocol.get("artifact_id")) == protocol_id
        and str(contract_population.get("artifact_id")) == population_id
        and str(report_payload.get("contract_id")) == contract_id
        and str(manifest_payload.get("contract_id")) == contract_id
        and str(manifest_payload.get("report_id")) == report_id
        and str(manifest_payload.get("records_sha256")) == _sha256(records_path)
        and str(manifest_payload.get("terminal_outcomes_sha256")) == _sha256(terminal_path)
        and str(manifest_payload.get("legacy_behavior_diagnostics_sha256"))
        == _sha256(behavior_path)
        and str(manifest_payload.get("report_sha256")) == _sha256(source_paths[3])
        and int(report_payload.get("recorded_rollout_count", -1)) == EXPECTED_ROLLOUT_COUNT
        and bool(report_payload.get("runtime_measurement_ready"))
        and bool(report_payload.get("valid_training_support_ready"))
        and int(report_payload.get("l0_l2_failure_count", -1)) == 0
        and float(report_payload.get("runtime_pathology_rate", -1.0)) == 0.0
        and int(report_payload.get("boundary_candidate_admitted_count", -1)) == 2
        and int(report_payload.get("runtime_control_pass_count", -1)) == 2
        and not bool(report_payload.get("all_boundary_candidates_admitted"))
        and bool(report_payload.get("all_runtime_controls_passed"))
        and not bool(report_payload.get("all_shapes_contract_passing"))
        and admitted == expected_admitted
        and str(report_payload.get("next_permitted_stage")) == "stopping_shape_redesign_only"
        and not bool(report_payload.get("fresh_three_population_preparation_authorized"))
        and int(report_payload.get("pro_api_call_count", -1)) == 0
        and not bool(report_payload.get("beneficiary_screening_authorized"))
        and not bool(report_payload.get("exact_target_evaluated"))
        and not bool(report_payload.get("gp_c_evaluated"))
        and float(report_payload.get("production_contribution", -1.0)) == 0.0
    ):
        raise ValueError("v25.43 predecessor identity or frozen result state changed")

    records = tuple(
        json.loads(line)
        for line in records_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    terminals = tuple(
        json.loads(line)
        for line in terminal_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    behaviors = tuple(
        json.loads(line)
        for line in behavior_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if not (
        len(records) == len(terminals) == len(behaviors) == EXPECTED_ROLLOUT_COUNT
        and all(isinstance(item, Mapping) for item in (*records, *terminals, *behaviors))
    ):
        raise ValueError("v25.43 diagnostic artifacts have an invalid denominator")
    forbidden_result_keys = {
        "host_event_sequence",
        "submechanism_activation",
        "host_events",
    }
    observation_count = 0
    for record in records:
        observations = list(record.get("observations") or ())
        failure = record.get("failure_artifact")
        if isinstance(failure, Mapping):
            observations.extend(failure.get("observations") or ())
        for observation in observations:
            if not isinstance(observation, Mapping):
                raise ValueError("v25.43 observation is not a JSON object")
            observation_count += 1
            if str(observation.get("schema_version")) != "agent_tool_observation.v2":
                raise ValueError("v25.43 observation does not use the Host side channel")
            result = observation.get("result")
            if not isinstance(result, Mapping):
                raise ValueError("v25.43 observation result is not a JSON object")
            if forbidden_result_keys.intersection(result):
                raise ValueError("v25.43 Host metadata contaminated a strict tool result")
            if "unknown fields" in str(observation.get("error_message") or "").lower():
                raise ValueError("v25.43 predecessor contains a strict tool-payload failure")
    if observation_count == 0:
        raise ValueError("v25.43 predecessor contains no replayable observations")
    if any(
        "Agent tool result contains unknown fields" in str(record.get("error_message") or "")
        for record in records
    ):
        raise ValueError("v25.43 predecessor contains a strict tool-payload failure")

    task_by_id = {
        str(item.get("artifact", {}).get("artifact_id", "")): item
        for item in task_payloads
        if isinstance(item, Mapping) and isinstance(item.get("artifact"), Mapping)
    }
    response_by_task: dict[str, float] = {}
    for shape_result in shape_results:
        if not isinstance(shape_result, Mapping):
            continue
        for task_result in shape_result.get("task_responses") or ():
            if isinstance(task_result, Mapping):
                response_by_task[str(task_result.get("task_artifact_id", ""))] = float(
                    task_result.get("stopping_probability", -1.0)
                )
    role_vectors: dict[str, dict[str, list[float]]] = {
        shape_id: {} for shape_id in TARGET_ROLE_ID_BY_SHAPE
    }
    for task_id, task in task_by_id.items():
        shape_id = str(task.get("shape_id", ""))
        if shape_id not in role_vectors:
            continue
        scenario = task.get("scenario")
        if not isinstance(scenario, Mapping):
            raise ValueError("v25.43 role-position task lacks a scenario")
        decision = scenario.get("stopping_shape_decision_contract")
        roles = scenario.get("evidence_roles")
        if not isinstance(decision, Mapping) or not isinstance(roles, list):
            raise ValueError("v25.43 role-position task lacks a decision or roles")
        state = decision.get("observed_evidence_state")
        if not isinstance(state, Mapping) or not isinstance(state.get("required_record"), Mapping):
            raise ValueError("v25.43 role-position task lacks a required record")
        required = state["required_record"]
        temporal = required.get("temporal_identity")
        if not isinstance(temporal, Mapping):
            raise ValueError("v25.43 required record lacks temporal identity")
        matches = [
            role
            for role in roles
            if isinstance(role, Mapping)
            and (
                str(role.get("subject_alias")),
                str(role.get("metric_alias")),
                str(role.get("period_label")),
            )
            == (
                str(required.get("subject_alias")),
                str(required.get("metric_alias")),
                str(temporal.get("label")),
            )
        ]
        if len(matches) != 1 or task_id not in response_by_task:
            raise ValueError("v25.43 target role cannot be reconstructed uniquely")
        role_id = str(matches[0].get("role_id", ""))
        role_vectors[shape_id].setdefault(role_id, []).append(response_by_task[task_id])
    frozen_role_vectors = {
        shape_id: {role_id: tuple(sorted(values)) for role_id, values in sorted(by_role.items())}
        for shape_id, by_role in sorted(role_vectors.items())
    }
    role_counts = {
        shape_id: {role_id: len(values) for role_id, values in sorted(by_role.items())}
        for shape_id, by_role in sorted(role_vectors.items())
    }
    predecessor_audit = StoppingRolePositionPredecessorAudit(
        role_task_counts=role_counts,
        role_stopping_probability_vectors=frozen_role_vectors,
    )

    manifest_id = canonical_hash(
        manifest_payload,
        prefix="finance_stopping_shape_policy_manifest_artifact:",
    )
    records_id = canonical_hash(
        {"contract_id": contract_id, "sha256": _sha256(records_path)},
        prefix="finance_stopping_shape_policy_records:",
    )
    terminal_id = canonical_hash(
        {"contract_id": contract_id, "sha256": _sha256(terminal_path)},
        prefix="finance_stopping_shape_policy_terminal_outcomes:",
    )
    behavior_id = canonical_hash(
        {
            "contract_id": contract_id,
            "sha256": _sha256(behavior_path),
            "role_position_audit": predecessor_audit,
        },
        prefix="finance_stopping_shape_policy_behavior_diagnostics:",
    )
    additional_historical = tuple(
        _reference(
            path.resolve(),
            str(json.loads(path.resolve().read_text(encoding="utf-8"))["population_id"]),
        )
        for path in additional_historical_population_paths
    )
    historical = tuple(
        sorted(
            (*history, _reference(source_paths[1], population_id), *additional_historical),
            key=lambda item: item.artifact_id,
        )
    )
    if len({item.artifact_id for item in historical}) != len(historical):
        raise ValueError("v25.44 historical exclusion set contains a duplicate")
    if (source_finance_artifacts_path is None) != (source_finance_artifacts_id is None):
        raise ValueError(
            "Stopping Shape policy Finance artifact path and identity must be supplied together"
        )
    finance_reference = FrozenArtifactReference.model_validate(
        protocol_payload.get("source_finance_artifacts")
    )
    if source_finance_artifacts_path is not None and source_finance_artifacts_id is not None:
        finance_reference = _reference(
            source_finance_artifacts_path.resolve(), source_finance_artifacts_id
        )
    calibration_reference = FrozenArtifactReference.model_validate(
        protocol_payload.get("source_calibration_contract")
    )
    result_by_shape = {
        str(item.get("shape_id")): item for item in shape_results if isinstance(item, Mapping)
    }
    design_payloads = protocol_payload.get("shape_designs")
    if not isinstance(design_payloads, list):
        raise ValueError("v25.43 protocol lacks Shape designs")
    designs = tuple(
        StoppingShapePolicyDesign.model_validate(
            {
                **item,
                "source_result_admitted": bool(
                    result_by_shape.get(str(item.get("shape_id")), {}).get("admitted")
                ),
                "design_status": (
                    "structural_redesign"
                    if str(item.get("shape_id")) in STRUCTURAL_REDESIGN_SHAPES
                    else (
                        "instrument_regression"
                        if str(item.get("shape_id")) in RUNTIME_CONTROL_SHAPES
                        else "boundary_regression"
                    )
                ),
            }
        )
        for item in design_payloads
        if isinstance(item, Mapping)
    )
    values = {
        "run_id": run_id,
        "source_v25_43_protocol": _reference(source_paths[0], protocol_id),
        "source_v25_43_population": _reference(source_paths[1], population_id),
        "source_v25_43_contract": _reference(source_paths[2], contract_id),
        "source_v25_43_report": _reference(source_paths[3], report_id),
        "source_v25_43_manifest": _reference(manifest_path, manifest_id),
        "source_v25_43_records": _reference(records_path, records_id),
        "source_v25_43_terminal_outcomes": _reference(terminal_path, terminal_id),
        "source_v25_43_behavior_diagnostics": _reference(behavior_path, behavior_id),
        "predecessor_role_position_audit": predecessor_audit,
        "source_finance_artifacts": finance_reference,
        "source_calibration_contract": calibration_reference,
        "historical_population_references": historical,
        "estimand_definition": StoppingShapePolicyDefinition(),
        "shape_designs": designs,
        "target_role_ids": dict(TARGET_ROLE_ID_BY_SHAPE),
    }
    provisional = FinanceStoppingShapePolicyProtocol.model_construct(
        protocol_id="pending", **values
    )
    protocol = FinanceStoppingShapePolicyProtocol(
        protocol_id=stopping_shape_policy_protocol_id(provisional), **values
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, protocol.model_dump(mode="json"))
    return protocol


def build_stopping_shape_policy_population(
    *,
    protocol_path: Path,
    output_dir: Path,
    run_id: str,
) -> FinanceStoppingShapePolicyPopulation:
    output_path = output_dir / "finance_stopping_shape_policy_population.json"
    if output_path.exists():
        raise ValueError("Stopping Shape policy population is immutable")
    protocol_path = protocol_path.resolve()
    protocol = FinanceStoppingShapePolicyProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    _verify_protocol_inputs(protocol)
    excluded = _collect_excluded_identities(protocol.historical_population_references)
    pool = _load_evidence_pool(Path(protocol.source_finance_artifacts.path))
    evidence_pool = tuple(pool.public.values())
    one_difference_index = _build_one_difference_index(
        evidence_pool,
        fields=("subject", "period", "definition", "payload_context"),
    )
    builder = _CapabilityTaskBuilder(pool, sampling_salt=f"{run_id}:stopping-shape-policy")
    candidate_cache = {
        (family, tier): tuple(_candidate_iterator(builder, family, tier))
        for _, family, tier in protocol.structural_strata
    }
    conflict_mismatch_by_cell = {
        (item.stratum_id, item.instance_index): item.mismatch_field
        for item in protocol.conflict_cell_allocations
    }
    used_ids = set(excluded["evidence_id"])
    used_versions = set(excluded["evidence_version_id"])
    tasks: list[StoppingShapeTask] = []
    instance_indices: dict[str, int] = {}
    statuses: dict[
        str, Literal["boundary_regression", "instrument_regression", "structural_redesign"]
    ] = {}
    # Allocate the low-capacity exact-definition conflict pairs before shapes that can
    # use arbitrary remaining evidence. Global identity reservation still applies.
    design_order = {
        "single_dimension_conflict": 0,
        "authority_coverage_gap": 1,
        "verified_extra_call_error_risk": 2,
        "verified_extra_call_cost": 3,
        "contextual_resolution_choice": 4,
        "partial_required_evidence": 5,
    }
    for design in sorted(protocol.shape_designs, key=lambda item: design_order[item.shape_id]):
        for stratum_id, family, tier in protocol.structural_strata:
            for instance_index in range(TASKS_PER_STRATUM):
                task = _materialize_shape_policy_task(
                    builder=builder,
                    candidate_rows=candidate_cache[(family, tier)],
                    design=design,
                    stratum_id=stratum_id,
                    family=family,
                    tier=tier,
                    instance_index=instance_index,
                    evidence_pool=evidence_pool,
                    one_difference_index=one_difference_index,
                    conflict_mismatch_field=(
                        conflict_mismatch_by_cell[(stratum_id, instance_index)]
                        if design.shape_id == "single_dimension_conflict"
                        else None
                    ),
                    target_role_index=TARGET_ROLE_INDEX_BY_SHAPE.get(design.shape_id),
                    used_ids=used_ids,
                    used_versions=used_versions,
                    sampling_salt=(f"{run_id}:{design.shape_id}:{stratum_id}:{instance_index}"),
                )
                if task.artifact.artifact_id in excluded["artifact_id"]:
                    raise ValueError("Stopping Shape policy reused a historical task")
                if task.source_semantic_signature in excluded["source_semantic_signature"]:
                    raise ValueError("Stopping Shape policy reused historical semantics")
                if task.materializer_hash in excluded["materializer_hash"]:
                    raise ValueError("Stopping Shape policy reused a historical materializer")
                tasks.append(task)
                task_id = task.artifact.artifact_id
                instance_indices[task_id] = instance_index
                statuses[task_id] = design.design_status
                used_ids.update(item.evidence_id for item in task.artifact.public_corpus.evidence)
                used_versions.update(
                    item.evidence_version_id for item in task.artifact.public_corpus.evidence
                )
    frozen_tasks = tuple(tasks)
    host_events = {
        item.artifact.artifact_id: item.scenario.expected_host_events for item in frozen_tasks
    }
    audit = make_stopping_shape_policy_static_audit(
        frozen_tasks,
        protocol,
        excluded=excluded,
        task_stratum_instance_indices=instance_indices,
        task_design_statuses=statuses,
        task_expected_host_events=host_events,
    )
    implementation = _implementation_manifest()
    values = {
        "run_id": run_id,
        "protocol_path": str(protocol_path),
        "protocol_sha256": _sha256(protocol_path),
        "protocol_id": protocol.protocol_id,
        "tasks": frozen_tasks,
        "task_stratum_instance_indices": instance_indices,
        "task_design_statuses": statuses,
        "task_expected_host_events": host_events,
        "static_audit": audit,
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_stopping_shape_policy_population_implementation:",
        ),
        "next_permitted_stage": audit.next_permitted_stage,
    }
    provisional = FinanceStoppingShapePolicyPopulation.model_construct(
        population_id="pending", **values
    )
    population = FinanceStoppingShapePolicyPopulation(
        population_id=stopping_shape_policy_population_id(provisional), **values
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, population.model_dump(mode="json"))
    _write_json(
        output_dir / "finance_stopping_shape_policy_static_audit.json",
        audit.model_dump(mode="json"),
    )
    (output_dir / "finance_stopping_shape_policy_population_report.md").write_text(
        _render_population_report(population), encoding="utf-8"
    )
    return population


def make_stopping_shape_policy_static_audit(
    tasks: Sequence[StoppingShapeTask],
    protocol: FinanceStoppingShapePolicyProtocol,
    *,
    excluded: Mapping[str, set[str]],
    task_stratum_instance_indices: Mapping[str, int],
    task_design_statuses: Mapping[
        str, Literal["boundary_regression", "instrument_regression", "structural_redesign"]
    ],
    task_expected_host_events: Mapping[str, tuple[str, str]],
) -> StoppingShapePolicyStaticAudit:
    design_by_shape = {item.shape_id: item for item in protocol.shape_designs}
    causal_graph_checks = tuple(
        _causal_state_action_graph_ready(design_by_shape[shape_id])
        for shape_id in (
            "contextual_resolution_choice",
            "single_dimension_conflict",
        )
    )
    shape_counts = Counter(item.shape_id for item in tasks)
    role_counts = Counter(item.shape_role for item in tasks)
    stratum_counts = Counter(item.stratum_id for item in tasks)
    shape_stratum_counts = Counter(f"{item.shape_id}|{item.stratum_id}" for item in tasks)
    status_counts = Counter(task_design_statuses.values())
    evidence = [item for task in tasks for item in task.artifact.public_corpus.evidence]
    task_ids = {item.artifact.artifact_id for item in tasks}
    semantic = {item.source_semantic_signature for item in tasks}
    materializers = {item.materializer_hash for item in tasks}
    expected_shape_strata = {
        f"{shape_id}|{stratum[0]}" for shape_id in ALL_SHAPES for stratum in STRUCTURAL_STRATA
    }
    contextual_tasks = tuple(
        item for item in tasks if item.shape_id == "contextual_resolution_choice"
    )
    partial_tasks = tuple(item for item in tasks if item.shape_id == "partial_required_evidence")
    conflict_tasks = tuple(item for item in tasks if item.shape_id == "single_dimension_conflict")
    cost_tasks = tuple(item for item in tasks if item.shape_id == "verified_extra_call_cost")
    contextual_checks = tuple(_matched_contextual_contract_ready(item) for item in contextual_tasks)
    dependency_checks = tuple(
        _conditional_dependency_contract_ready(item) for item in partial_tasks
    )
    dependency_output_checks = tuple(
        _dependency_branch_output_contract_ready(item) for item in partial_tasks
    )
    grounded_checks = tuple(_grounded_conflict_contract_ready(item) for item in conflict_tasks)
    conflict_mismatch_counts = Counter(
        mismatch
        for item in conflict_tasks
        if (mismatch := _single_public_distractor_mismatch(item)) is not None
    )
    conflict_resolution_tool_counts = Counter(
        tool
        for item in conflict_tasks
        if (tool := _expected_state_resolution_tool(item)) is not None
    )
    expected_conflict_mismatches = Counter(
        item.mismatch_field for item in protocol.conflict_cell_allocations
    )
    expected_conflict_tools = Counter(
        item.expected_resolution_tool for item in protocol.conflict_cell_allocations
    )
    cost_checks = tuple(_sealed_cost_contract_ready(item) for item in cost_tasks)
    near_decoy_checks = tuple(_dependency_decoy_is_one_dimensional(item) for item in partial_tasks)
    contextual_conflict_decoy_checks = tuple(
        _contextual_conflict_decoy_is_one_dimensional(item)
        for item in (*contextual_tasks, *conflict_tasks)
    )
    contextual_signatures = {_contextual_construction_signature(item) for item in contextual_tasks}
    role_position_tasks = (*contextual_tasks, *conflict_tasks)
    target_role_checks = tuple(
        _required_decision_role_id(item) == protocol.target_role_ids[item.shape_id]
        for item in role_position_tasks
    )
    lexical_leaks = sum(
        not _conflict_public_text_isolated(item) for item in (*contextual_tasks, *conflict_tasks)
    )
    public_contract = {
        item.artifact.artifact_id: _public_decision_contract_matches(item) for item in tasks
    }
    boundary_task_count = sum(item.shape_id in BOUNDARY_CANDIDATE_SHAPES for item in tasks)
    control_task_count = sum(item.shape_id in RUNTIME_CONTROL_SHAPES for item in tasks)
    unchanged_task_count = sum(item.shape_id in UNCHANGED_REGRESSION_SHAPES for item in tasks)
    redesign_task_count = sum(item.shape_id in STRUCTURAL_REDESIGN_SHAPES for item in tasks)
    structural_scoped = all(
        (
            design_by_shape[item.shape_id].design_status == "structural_redesign"
            and item.scenario.stopping_shape_decision_contract is not None
        )
        == (item.shape_id in STRUCTURAL_REDESIGN_SHAPES)
        for item in tasks
    )
    unchanged_scoped = all(
        (
            design_by_shape[item.shape_id].design_status
            in {"boundary_regression", "instrument_regression"}
        )
        == (item.shape_id in UNCHANGED_REGRESSION_SHAPES)
        for item in tasks
    )
    checks = {
        "complete_task_count": len(tasks) == EXPECTED_TASK_COUNT,
        "shape_redundancy": set(shape_counts) == ALL_SHAPES
        and set(shape_counts.values()) == {TASKS_PER_SHAPE},
        "shape_role_denominators": boundary_task_count == 32 and control_task_count == 16,
        "design_denominators": unchanged_task_count == 32 and redesign_task_count == 16,
        "stratum_balance": set(stratum_counts) == {item[0] for item in STRUCTURAL_STRATA}
        and set(stratum_counts.values()) == {SHAPE_COUNT * TASKS_PER_STRATUM},
        "shape_stratum_redundancy": set(shape_stratum_counts) == expected_shape_strata
        and set(shape_stratum_counts.values()) == {TASKS_PER_STRATUM},
        "operation_replay": all(item.artifact.verification.passed for item in tasks),
        "host_replay": all(item.runtime_replay.passed for item in tasks),
        "public_oracle_isolation": all(_public_task_isolated(item) for item in tasks),
        "answer_contract": all(_answer_contract_ready(item.artifact) for item in tasks),
        "public_decision_contract": all(public_contract.values()),
        "causal_state_action_graph": all(causal_graph_checks),
        "matched_contextual_contract": len(contextual_checks) == TASKS_PER_SHAPE
        and all(contextual_checks),
        "conditional_dependency_contract": len(dependency_checks) == TASKS_PER_SHAPE
        and all(dependency_checks),
        "conditional_dependency_output_contract": (
            len(dependency_output_checks) == TASKS_PER_SHAPE and all(dependency_output_checks)
        ),
        "grounded_conflict_contract": len(grounded_checks) == TASKS_PER_SHAPE
        and all(grounded_checks),
        "conflict_mismatch_balance": conflict_mismatch_counts == expected_conflict_mismatches,
        "conflict_resolution_tool_balance": conflict_resolution_tool_counts
        == expected_conflict_tools,
        "conflict_resolution_tool_diversity": (
            len(conflict_resolution_tool_counts) == 2
            and min(conflict_resolution_tool_counts.values(), default=0)
            >= protocol.thresholds.minimum_conflict_tasks_per_resolution_tool
            and max(conflict_resolution_tool_counts.values(), default=0)
            / max(sum(conflict_resolution_tool_counts.values()), 1)
            <= protocol.thresholds.maximum_conflict_resolution_tool_share
        ),
        "sealed_cost_contract": len(cost_checks) == TASKS_PER_SHAPE and all(cost_checks),
        "dependency_decoy_one_dimensional": len(near_decoy_checks) == TASKS_PER_SHAPE
        and all(near_decoy_checks),
        "contextual_conflict_decoy_one_dimensional": (
            len(contextual_conflict_decoy_checks) == 2 * TASKS_PER_SHAPE
            and all(contextual_conflict_decoy_checks)
        ),
        "contextual_task_construction_matched": len(contextual_signatures) == 1,
        "target_role_position_control": (
            len(target_role_checks) == 2 * TASKS_PER_SHAPE and all(target_role_checks)
        ),
        "zero_lexical_conflict_leakage": lexical_leaks == 0,
        "within_evidence_disjoint": len(evidence) == len({item.evidence_id for item in evidence}),
        "historical_task_disjoint": not task_ids & excluded["artifact_id"],
        "historical_evidence_disjoint": not {item.evidence_id for item in evidence}
        & excluded["evidence_id"],
        "historical_version_disjoint": not {item.evidence_version_id for item in evidence}
        & excluded["evidence_version_id"],
        "historical_semantic_disjoint": not semantic & excluded["source_semantic_signature"],
        "historical_materializer_disjoint": not materializers & excluded["materializer_hash"],
        "distinct_task_instances": len(task_ids) == EXPECTED_TASK_COUNT,
        "instance_pairing": set(task_stratum_instance_indices) == task_ids
        and all(
            {
                task_stratum_instance_indices[item.artifact.artifact_id]
                for item in tasks
                if item.shape_id == shape_id and item.stratum_id == stratum_id
            }
            == {0, 1}
            for shape_id in ALL_SHAPES
            for stratum_id, _, _ in STRUCTURAL_STRATA
        ),
        "structural_redesign_scoped": structural_scoped,
        "unchanged_regressions_scoped": unchanged_scoped,
        "design_statuses": set(task_design_statuses) == task_ids
        and all(
            task_design_statuses[item.artifact.artifact_id]
            == design_by_shape[item.shape_id].design_status
            for item in tasks
        ),
        "estimand_semantics_frozen_pre_api": (
            protocol.estimand_definition.estimand_semantics_frozen
            and protocol.estimand_definition == StoppingShapePolicyDefinition()
            and protocol.cross_estimand_rescue_forbidden
        ),
        "shape_support_policy_unfrozen_pre_api": (
            not protocol.estimand_definition.shape_support_policy_frozen
        ),
        "historical_result_transfer_forbidden": (
            not protocol.historical_results_transfer_authorized
            and all(
                not item.historical_result_transfer_authorized for item in protocol.shape_designs
            )
        ),
        "host_events_frozen_pre_api": set(task_expected_host_events) == task_ids,
        "frontier_only": all(item.artifact.tier == DifficultyTier.FRONTIER for item in tasks),
    }
    rejections = tuple(sorted(key for key, passed in checks.items() if not passed))
    values = {
        "task_count": len(tasks),
        "shape_task_counts": dict(sorted(shape_counts.items())),
        "shape_role_task_counts": dict(sorted(role_counts.items())),
        "stratum_task_counts": dict(sorted(stratum_counts.items())),
        "shape_stratum_task_counts": dict(sorted(shape_stratum_counts.items())),
        "design_status_task_counts": dict(sorted(status_counts.items())),
        "boundary_candidate_task_count": boundary_task_count,
        "runtime_control_task_count": control_task_count,
        "unchanged_regression_task_count": unchanged_task_count,
        "structural_redesign_task_count": redesign_task_count,
        "operation_replay_rate": _rate(item.artifact.verification.passed for item in tasks),
        "host_replay_rate": _rate(item.runtime_replay.passed for item in tasks),
        "public_oracle_isolation_rate": _rate(_public_task_isolated(item) for item in tasks),
        "answer_contract_rate": _rate(_answer_contract_ready(item.artifact) for item in tasks),
        "public_decision_contract_rate": _rate(public_contract.values()),
        "causal_state_action_graph_rate": _rate(causal_graph_checks),
        "conditional_dependency_contract_rate": _rate(dependency_checks),
        "conditional_dependency_output_contract_rate": _rate(dependency_output_checks),
        "matched_contextual_contract_rate": _rate(contextual_checks),
        "grounded_conflict_contract_rate": _rate(grounded_checks),
        "conflict_mismatch_dimension_counts": dict(sorted(conflict_mismatch_counts.items())),
        "conflict_resolution_tool_counts": dict(sorted(conflict_resolution_tool_counts.items())),
        "conflict_mismatch_balance_frozen": checks["conflict_mismatch_balance"]
        and checks["conflict_resolution_tool_balance"],
        "conflict_resolution_tool_diversity_frozen": checks["conflict_resolution_tool_diversity"],
        "sealed_cost_contract_rate": _rate(cost_checks),
        "dependency_decoy_one_dimensional_rate": _rate(near_decoy_checks),
        "contextual_conflict_decoy_one_dimensional_rate": _rate(contextual_conflict_decoy_checks),
        "lexical_conflict_leakage_count": lexical_leaks,
        "contextual_task_construction_matched": len(contextual_signatures) == 1,
        "target_role_ids": dict(sorted(protocol.target_role_ids.items())),
        "target_role_control_rate": _rate(target_role_checks),
        "target_role_position_control_frozen": checks["target_role_position_control"],
        "within_population_evidence_disjoint": checks["within_evidence_disjoint"],
        "historical_task_disjoint": checks["historical_task_disjoint"],
        "historical_evidence_disjoint": checks["historical_evidence_disjoint"],
        "historical_evidence_version_disjoint": checks["historical_version_disjoint"],
        "historical_semantic_signature_disjoint": checks["historical_semantic_disjoint"],
        "historical_materializer_disjoint": checks["historical_materializer_disjoint"],
        "estimand_semantics_frozen_pre_api": checks["estimand_semantics_frozen_pre_api"],
        "shape_support_policy_unfrozen_pre_api": checks["shape_support_policy_unfrozen_pre_api"],
        "historical_result_transfer_forbidden": checks["historical_result_transfer_forbidden"],
        "structural_redesign_scoped": checks["structural_redesign_scoped"],
        "unchanged_regressions_scoped": checks["unchanged_regressions_scoped"],
        "exact_shape_stratum_redundancy": checks["shape_stratum_redundancy"],
        "task_expected_host_events_frozen_pre_api": checks["host_events_frozen_pre_api"],
        "rejection_reasons": rejections,
        "ready": not rejections,
        "next_permitted_stage": (
            "flash_stopping_shape_policy_development"
            if not rejections
            else "stopping_shape_policy_population_repair_only"
        ),
    }
    provisional = StoppingShapePolicyStaticAudit.model_construct(audit_id="pending", **values)
    return StoppingShapePolicyStaticAudit(
        audit_id=stopping_shape_policy_static_audit_id(provisional), **values
    )


def _make_shape_policy_design(
    source: Any,
    source_result_admitted: bool,
) -> StoppingShapePolicyDesign:
    shape_id = str(source.shape_id)
    graph = source.spec.action_graph
    runtime = source.spec.runtime_contract.model_copy(
        update={
            "implementation_status": "host_and_materializer_implemented",
            "implementation_id": (
                f"{FINANCE_SUBMECHANISM_RUNTIME_VERSION}:"
                f"{source.spec.runtime_contract.intervention_kind}"
            ),
        }
    )
    if shape_id == "contextual_resolution_choice":
        graph = _linear_graph(
            (
                (
                    "resolve_initial_state",
                    "resolve_conflict",
                    "query_structured_fact",
                ),
                ("retrieve_remaining", "retrieve", "query_structured_fact"),
                ("calculate_result", "calculate", "calculator"),
                ("verify_resolution", "verify_evidence", "cross_check_evidence"),
            )
        )
        runtime = runtime.model_copy(
            update={
                "trigger_node_id": "read_task",
                "resolution_node_id": "verify_resolution",
            }
        )
    elif shape_id == "partial_required_evidence":
        graph = _linear_graph(
            (
                ("retrieve_partial", "retrieve", "query_structured_fact"),
                ("check_incomplete", "assess_completeness", "cross_check_evidence"),
                ("observe_dependency", "continue_work", "search_archive"),
                ("retrieve_missing", "retrieve_missing", "query_structured_fact"),
                ("check_complete", "assess_completeness", "cross_check_evidence"),
            )
        )
    elif shape_id == "single_dimension_conflict":
        graph = _graph(
            (
                _node("read_task", "read_task"),
                _node(
                    "retrieve_required",
                    "retrieve",
                    ("read_task",),
                    tool_id="query_structured_fact",
                ),
                _node(
                    "resolve_active_state",
                    "resolve_conflict",
                    ("read_task",),
                    observations=("active public Evidence state",),
                ),
                _node(
                    "calculate_result",
                    "calculate",
                    ("retrieve_required", "resolve_active_state"),
                    tool_id="calculator",
                ),
                _node(
                    "verify_result",
                    "verify_evidence",
                    ("calculate_result",),
                    tool_id="cross_check_evidence",
                ),
                _node("stop", "stop", ("verify_result",)),
            )
        )
        runtime = runtime.model_copy(
            update={
                "trigger_node_id": "read_task",
                "resolution_node_id": "resolve_active_state",
            }
        )
    spec = _spec(
        source.spec.parent_mechanism_id,
        shape_id,
        source.spec.title,
        graph,
        source.spec.evidence_dependencies,
        runtime,
        source.spec.diagnostic_outcomes,
    )
    decision_kind = {
        "contextual_resolution_choice": ("matched_contextual_evidence_state_choice_two_step"),
        "partial_required_evidence": "conditional_dependency_observation_required",
        "single_dimension_conflict": "single_conflict_evidence_state_choice_one_step",
        "verified_extra_call_cost": "sealed_terminal_extra_call_cost",
    }.get(shape_id)
    status = {
        "authority_coverage_gap": "boundary_regression",
        "contextual_resolution_choice": "structural_redesign",
        "partial_required_evidence": "boundary_regression",
        "single_dimension_conflict": "structural_redesign",
        "verified_extra_call_cost": "instrument_regression",
        "verified_extra_call_error_risk": "instrument_regression",
    }[shape_id]
    return StoppingShapePolicyDesign(
        shape_id=shape_id,
        shape_role=source.shape_role,
        early_stop_consequence=source.early_stop_consequence,
        source_spec_id=source.source_spec_id,
        source_spec_hash=source.spec.spec_hash,
        source_result_admitted=source_result_admitted,
        design_status=cast(Any, status),
        spec=spec,
        intervention_kind=cast(SubmechanismKind, spec.runtime_contract.intervention_kind),
        decision_contract_kind=cast(Any, decision_kind),
    )


def _causal_state_action_graph_ready(
    design: StoppingShapePolicyDesign,
) -> bool:
    nodes = {item.node_id: item for item in design.spec.action_graph.nodes}
    runtime = design.spec.runtime_contract
    if design.shape_id == "contextual_resolution_choice":
        return bool(
            runtime.trigger_node_id == "read_task"
            and runtime.resolution_node_id == "verify_resolution"
            and nodes.get("resolve_initial_state") is not None
            and nodes["resolve_initial_state"].tool_id == "query_structured_fact"
            and nodes["resolve_initial_state"].depends_on == ("read_task",)
            and nodes.get("retrieve_remaining") is not None
            and nodes["retrieve_remaining"].depends_on == ("resolve_initial_state",)
            and nodes.get("calculate_result") is not None
            and nodes["calculate_result"].depends_on == ("retrieve_remaining",)
            and nodes.get("verify_resolution") is not None
            and nodes["verify_resolution"].depends_on == ("calculate_result",)
        )
    if design.shape_id == "single_dimension_conflict":
        return bool(
            runtime.trigger_node_id == "read_task"
            and runtime.resolution_node_id == "resolve_active_state"
            and nodes.get("retrieve_required") is not None
            and nodes["retrieve_required"].depends_on == ("read_task",)
            and nodes.get("resolve_active_state") is not None
            and nodes["resolve_active_state"].depends_on == ("read_task",)
            and nodes.get("calculate_result") is not None
            and set(nodes["calculate_result"].depends_on)
            == {"retrieve_required", "resolve_active_state"}
            and nodes.get("verify_result") is not None
            and nodes["verify_result"].depends_on == ("calculate_result",)
        )
    return False


def _observed_record(item: EvidenceItem) -> FinanceStoppingObservedRecord:
    temporal = item.temporal_context
    return FinanceStoppingObservedRecord(
        subject_alias=item.subject.subject_id,
        metric_alias=item.predicate,
        temporal_identity=FinanceStoppingTemporalIdentity(
            label=str(temporal.label),
            valid_from=temporal.valid_from.isoformat() if temporal.valid_from else None,
            valid_to=temporal.valid_to.isoformat() if temporal.valid_to else None,
            observed_at=temporal.observed_at.isoformat() if temporal.observed_at else None,
        ),
        source_id=item.source.source_id,
        definition_id=item.definition.definition_id,
        measurement_context=FinanceStoppingMeasurementContext(
            unit=getattr(item.payload, "unit", None),
            currency=getattr(item.payload, "currency", None),
        ),
    )


def _observed_evidence_state(
    *,
    gold: tuple[EvidenceItem, ...],
    distractor: EvidenceItem,
    mismatch_field: str,
    target_role_index: int,
) -> FinanceStoppingObservedEvidenceState:
    if not 0 <= target_role_index < len(gold):
        raise ValueError("Stopping Shape target role is outside the Gold binding")
    required = gold[target_role_index]
    if _minimum_mismatch_fields(distractor, (required,)) != (mismatch_field,):
        raise ValueError("Stopping Shape target role lacks an exact one-dimensional pair")
    return FinanceStoppingObservedEvidenceState(
        observed_record=_observed_record(distractor),
        required_record=_observed_record(required),
    )


def _required_decision_role_id(task: StoppingShapeTask) -> str | None:
    decision = task.scenario.stopping_shape_decision_contract
    if decision is None or decision.observed_evidence_state is None:
        return None
    required = decision.observed_evidence_state.required_record
    matches = tuple(
        role.role_id
        for role in task.scenario.evidence_roles
        if (role.subject_alias, role.metric_alias, role.period_label)
        == (required.subject_alias, required.metric_alias, required.period_label)
    )
    return matches[0] if len(matches) == 1 else None


def _state_resolution_actions() -> tuple[FinanceStoppingResolutionAction, ...]:
    return (
        FinanceStoppingResolutionAction(
            tool_id="normalize_metric_unit_period",
            applicable_when=("establish a shared reporting or measurement basis before evaluation"),
        ),
        FinanceStoppingResolutionAction(
            tool_id="open_document",
            applicable_when="inspect document authority when provenance remains uncertain",
        ),
        FinanceStoppingResolutionAction(
            tool_id="query_structured_fact",
            applicable_when=(
                "retrieve the requested observation when subject or period coverage is absent"
            ),
        ),
    )


def _task_decision_contract(
    *,
    shape_id: str,
    gold: tuple[EvidenceItem, ...],
    distractor: EvidenceItem,
    mismatch_field: str,
    sampling_salt: str,
    target_role_index: int | None,
) -> FinanceStoppingShapeDecisionContract | None:
    if shape_id in {"authority_coverage_gap", "verified_extra_call_error_risk"}:
        return None
    if shape_id == "contextual_resolution_choice":
        if target_role_index is None:
            raise ValueError("Contextual Stopping Shape lacks a frozen target role")
        return FinanceStoppingShapeDecisionContract(
            contract_kind="matched_contextual_evidence_state_choice_two_step",
            observed_conflict_signal=(
                "Two public records are shown below. Exactly one registered identity "
                "component differs."
            ),
            observed_evidence_state=_observed_evidence_state(
                gold=gold,
                distractor=distractor,
                mismatch_field=mismatch_field,
                target_role_index=target_role_index,
            ),
            oracle_conflict_dimension={"subject": "entity_scope_alignment"}[mismatch_field],
            state_activation_phase="before_required_evidence_selection",
            available_resolution_actions=_state_resolution_actions(),
            resolution_step_count=2,
        )
    if shape_id == "partial_required_evidence":
        decoy = FinanceStoppingDependencyOption(
            option_id=canonical_hash(
                {
                    "sampling_salt": sampling_salt,
                    "evidence_version_id": distractor.evidence_version_id,
                },
                prefix="finance_stopping_dependency_decoy_option:",
            ),
            subject_alias=distractor.subject.subject_id,
            metric_alias=distractor.predicate,
            period_label=str(distractor.temporal_context.label),
        )
        return FinanceStoppingShapeDecisionContract(
            contract_kind="conditional_dependency_observation_required",
            dependency_rule=(
                "Probe the Archive for the unresolved subject-metric branch. Use the returned "
                "observation to identify which candidate closes the active operation "
                "dependency before retrieving that candidate."
            ),
            dependency_decoy_option=decoy,
            resolution_step_count=2,
        )
    if shape_id == "single_dimension_conflict":
        if target_role_index is None:
            raise ValueError("Conflict Stopping Shape lacks a frozen target role")
        return FinanceStoppingShapeDecisionContract(
            contract_kind="single_conflict_evidence_state_choice_one_step",
            observed_conflict_signal=(
                "Two public records are shown below. Exactly one registered identity "
                "component differs."
            ),
            observed_evidence_state=_observed_evidence_state(
                gold=gold,
                distractor=distractor,
                mismatch_field=mismatch_field,
                target_role_index=target_role_index,
            ),
            oracle_conflict_dimension={
                "definition": "source_definition_compatibility",
                "period": "temporal_alignment",
                "payload_context": "measurement_context_alignment",
            }[mismatch_field],
            state_activation_phase=(
                "before_required_evidence_selection"
                if mismatch_field == "period"
                else "after_required_evidence_selection_before_calculation"
            ),
            available_resolution_actions=_state_resolution_actions(),
            resolution_step_count=1,
        )
    if shape_id == "verified_extra_call_cost":
        return FinanceStoppingShapeDecisionContract(
            contract_kind="sealed_terminal_extra_call_cost",
            terminal_utility_loss=1.0,
            archive_snapshot_sealed=True,
            maximum_additional_information_gain=0.0,
            realized_call_budget_debit_fraction=0.25,
            realized_token_budget_debit_fraction=0.20,
            additional_action_rejected=True,
        )
    raise ValueError(f"Stopping Shape has no v25.44 decision contract: {shape_id}")


def _evidence_query_identity(item: EvidenceItem) -> tuple[str, str, str]:
    return (
        item.subject.subject_id,
        item.predicate,
        str(item.temporal_context.label),
    )


def _ordered_shape_candidates(
    *,
    candidate_rows: Sequence[Any],
    used_ids: set[str],
    used_versions: set[str],
    sampling_salt: str,
) -> tuple[Any, ...]:
    candidates = tuple(candidate_rows)
    available = tuple(
        row
        for row in candidates
        if not {item.evidence_id for item in row[0]} & used_ids
        and not {item.evidence_version_id for item in row[0]} & used_versions
    )
    frequency = Counter(item.evidence_id for row in available for item in row[0])

    def order_key(row: Any) -> tuple[int, int, str]:
        gold = row[0]
        collides = bool(
            {item.evidence_id for item in gold} & used_ids
            or {item.evidence_version_id for item in gold} & used_versions
        )
        rarity_cost = sum(frequency[item.evidence_id] for item in gold)
        tie_break = canonical_hash(
            {
                "sampling_salt": sampling_salt,
                "gold_versions": tuple(item.evidence_version_id for item in gold),
            },
            prefix="finance_stopping_capacity_aware_candidate_order:",
        )
        return int(collides), rarity_cost, tie_break

    return tuple(sorted(candidates, key=order_key))


def _select_distinct_query_distractor(
    *,
    spec: CapabilitySubmechanismSpec,
    gold: tuple[EvidenceItem, ...],
    evidence_pool: tuple[EvidenceItem, ...],
    used_ids: set[str],
    used_versions: set[str],
    sampling_salt: str,
) -> EvidenceItem | None:
    blocked_ids = set(used_ids)
    blocked_versions = set(used_versions)
    gold_queries = {_evidence_query_identity(item) for item in gold}
    for attempt in range(32):
        candidate = _select_distractor(
            spec,
            gold,
            evidence_pool,
            blocked_ids,
            blocked_versions,
            f"{sampling_salt}:candidate:{attempt}",
        )
        if candidate is None:
            return None
        if _evidence_query_identity(candidate) not in gold_queries:
            return candidate
        blocked_ids.add(candidate.evidence_id)
        blocked_versions.add(candidate.evidence_version_id)
    return None


OneDifferenceKey = tuple[tuple[str, Any], ...]
OneDifferenceIndex = dict[str, dict[OneDifferenceKey, tuple[EvidenceItem, ...]]]


def _semantic_components(item: EvidenceItem) -> tuple[tuple[str, Any], ...]:
    temporal = item.temporal_context
    return (
        ("subject", item.subject.subject_id),
        ("predicate", item.predicate),
        (
            "period",
            (
                temporal.label,
                temporal.valid_from.isoformat() if temporal.valid_from else None,
                temporal.valid_to.isoformat() if temporal.valid_to else None,
                temporal.observed_at.isoformat() if temporal.observed_at else None,
            ),
        ),
        ("source", item.source.source_id),
        ("definition", item.definition.definition_id),
        (
            "payload_context",
            (getattr(item.payload, "unit", None), getattr(item.payload, "currency", None)),
        ),
    )


def _one_difference_key(item: EvidenceItem, omitted_field: str) -> OneDifferenceKey:
    return tuple(
        (field, value) for field, value in _semantic_components(item) if field != omitted_field
    )


def _build_one_difference_index(
    evidence_pool: tuple[EvidenceItem, ...],
    *,
    fields: tuple[str, ...],
) -> OneDifferenceIndex:
    mutable: dict[str, dict[OneDifferenceKey, list[EvidenceItem]]] = {field: {} for field in fields}
    for item in evidence_pool:
        for field in fields:
            key = _one_difference_key(item, field)
            mutable[field].setdefault(key, []).append(item)
    return {
        field: {
            key: tuple(sorted(items, key=lambda item: item.evidence_version_id))
            for key, items in buckets.items()
        }
        for field, buckets in mutable.items()
    }


def _indexed_one_difference_candidates(
    *,
    one_difference_index: OneDifferenceIndex,
    gold: tuple[EvidenceItem, ...],
    mismatch_field: str,
) -> tuple[EvidenceItem, ...]:
    field_index = one_difference_index.get(mismatch_field)
    if field_index is None:
        raise ValueError(f"unindexed Stopping Shape mismatch field: {mismatch_field}")
    candidates = {
        item.evidence_version_id: item
        for target in gold
        for item in field_index.get(_one_difference_key(target, mismatch_field), ())
    }
    return tuple(candidates[key] for key in sorted(candidates))


def _select_contextual_distractor(
    *,
    gold: tuple[EvidenceItem, ...],
    target_role_index: int,
    one_difference_index: OneDifferenceIndex,
    used_ids: set[str],
    used_versions: set[str],
    sampling_salt: str,
) -> EvidenceItem | None:
    target = gold[target_role_index]
    candidates: list[tuple[str, EvidenceItem]] = []
    for item in _indexed_one_difference_candidates(
        one_difference_index=one_difference_index,
        gold=(target,),
        mismatch_field="subject",
    ):
        if item.evidence_id in used_ids or item.evidence_version_id in used_versions:
            continue
        if _minimum_mismatch_fields(item, (target,)) != ("subject",):
            continue
        rank = canonical_hash(
            {
                "sampling_salt": sampling_salt,
                "evidence_version_id": item.evidence_version_id,
            },
            prefix="finance_stopping_contextual_distractor_order:",
        )
        candidates.append((rank, item))
    return min(candidates, key=lambda row: row[0])[1] if candidates else None


def _select_normalization_distractor(
    *,
    gold: tuple[EvidenceItem, ...],
    target_role_index: int,
    one_difference_index: OneDifferenceIndex,
    used_ids: set[str],
    used_versions: set[str],
    sampling_salt: str,
    required_mismatch_field: str,
) -> EvidenceItem | None:
    target = gold[target_role_index]
    candidates: list[tuple[str, EvidenceItem]] = []
    for item in _indexed_one_difference_candidates(
        one_difference_index=one_difference_index,
        gold=(target,),
        mismatch_field=required_mismatch_field,
    ):
        if item.evidence_id in used_ids or item.evidence_version_id in used_versions:
            continue
        mismatches = _minimum_mismatch_fields(item, (target,))
        if mismatches != (required_mismatch_field,):
            continue
        rank = canonical_hash(
            {
                "sampling_salt": sampling_salt,
                "evidence_version_id": item.evidence_version_id,
                "mismatch_field": required_mismatch_field,
            },
            prefix="finance_stopping_normalization_distractor_order:",
        )
        candidates.append((rank, item))
    return min(candidates, key=lambda row: row[0])[1] if candidates else None


def _select_near_query_distractor(
    *,
    gold: tuple[EvidenceItem, ...],
    evidence_pool: tuple[EvidenceItem, ...],
    used_ids: set[str],
    used_versions: set[str],
    sampling_salt: str,
) -> EvidenceItem | None:
    if len(gold) < 2:
        return None
    unresolved = gold[1]
    gold_queries = {_evidence_query_identity(item) for item in gold}
    candidates = [
        item
        for item in evidence_pool
        if item.evidence_id not in used_ids
        and item.evidence_version_id not in used_versions
        and item.subject.subject_id == unresolved.subject.subject_id
        and item.predicate == unresolved.predicate
        and _evidence_query_identity(item) not in gold_queries
        and str(item.temporal_context.label) != str(unresolved.temporal_context.label)
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda item: canonical_hash(
            {
                "sampling_salt": sampling_salt,
                "evidence_version_id": item.evidence_version_id,
            },
            prefix="finance_stopping_near_query_distractor_order:",
        ),
    )


def _materialize_shape_policy_task(
    *,
    builder: _CapabilityTaskBuilder,
    candidate_rows: Sequence[Any],
    design: StoppingShapePolicyDesign,
    stratum_id: str,
    family: str,
    tier: DifficultyTier,
    instance_index: int,
    evidence_pool: tuple[EvidenceItem, ...],
    one_difference_index: OneDifferenceIndex,
    conflict_mismatch_field: str | None,
    target_role_index: int | None,
    used_ids: set[str],
    used_versions: set[str],
    sampling_salt: str,
) -> StoppingShapeTask:
    spec = design.spec
    rejection_counts: Counter[str] = Counter()
    ordered_candidates = _ordered_shape_candidates(
        candidate_rows=candidate_rows,
        used_ids=used_ids,
        used_versions=used_versions,
        sampling_salt=sampling_salt,
    )
    # Future candidate identities are not reserved globally. A near-match may be used
    # as the current task distractor; once selected, the population-level used sets
    # prevent it from appearing in any later Gold or Corpus.
    for gold, program, source_instruction, projection in ordered_candidates:
        rejection_counts["candidate_attempted"] += 1
        if design.shape_id == "partial_required_evidence" and len(gold) < 2:
            rejection_counts["partial_role_count"] += 1
            continue
        gold_ids = {item.evidence_id for item in gold}
        gold_versions = {item.evidence_version_id for item in gold}
        if gold_ids & used_ids or gold_versions & used_versions:
            rejection_counts["gold_identity_reserved"] += 1
            continue
        if design.shape_id == "partial_required_evidence":
            distractor = _select_near_query_distractor(
                gold=gold,
                evidence_pool=evidence_pool,
                used_ids=used_ids | gold_ids,
                used_versions=used_versions | gold_versions,
                sampling_salt=sampling_salt,
            )
        elif design.shape_id == "contextual_resolution_choice":
            if target_role_index is None:
                raise ValueError("Contextual task lacks a frozen target role")
            distractor = _select_contextual_distractor(
                gold=gold,
                target_role_index=target_role_index,
                one_difference_index=one_difference_index,
                used_ids=used_ids | gold_ids,
                used_versions=used_versions | gold_versions,
                sampling_salt=sampling_salt,
            )
        elif design.shape_id == "single_dimension_conflict":
            if conflict_mismatch_field is None:
                raise ValueError("Stopping conflict task lacks a frozen mismatch allocation")
            if target_role_index is None:
                raise ValueError("Conflict task lacks a frozen target role")
            distractor = _select_normalization_distractor(
                gold=gold,
                target_role_index=target_role_index,
                one_difference_index=one_difference_index,
                used_ids=used_ids | gold_ids,
                used_versions=used_versions | gold_versions,
                sampling_salt=sampling_salt,
                required_mismatch_field=conflict_mismatch_field,
            )
        else:
            distractor = _select_distinct_query_distractor(
                spec=spec,
                gold=gold,
                evidence_pool=evidence_pool,
                used_ids=used_ids | gold_ids,
                used_versions=used_versions | gold_versions,
                sampling_salt=sampling_salt,
            )
        if distractor is None:
            rejection_counts["distractor_unavailable"] += 1
            continue
        recovery = (
            (
                RecoveryBranch(
                    distractor_evidence_id=distractor.evidence_id,
                    mismatch_fields=_minimum_mismatch_fields(distractor, gold),
                ),
            )
            if spec.runtime_contract.intervention_kind in _RECOVERY_BRANCH_KINDS
            else ()
        )
        try:
            artifact = builder._materialize(
                family=family,
                tier=tier,
                gold=gold,
                distractors=(distractor,),
                recovery_branches=recovery,
                program=program,
                instruction=source_instruction,
                answer_projection=projection,
            )
        except ProgramExecutionError:
            rejection_counts["program_execution_failed"] += 1
            continue
        base_scenario = _make_scenario(
            spec,
            gold,
            distractor,
            artifact.projected_expected_output,
        )
        decision = _task_decision_contract(
            shape_id=design.shape_id,
            gold=gold,
            distractor=distractor,
            mismatch_field=_minimum_mismatch_fields(distractor, gold)[0],
            sampling_salt=sampling_salt,
            target_role_index=target_role_index,
        )
        scenario = base_scenario
        if decision is not None:
            scenario = make_finance_submechanism_scenario(
                submechanism_id=base_scenario.submechanism_id,
                parent_mechanism_id=base_scenario.parent_mechanism_id,
                intervention_kind=base_scenario.intervention_kind,
                expected_host_events=base_scenario.expected_host_events,
                evidence_roles=base_scenario.evidence_roles,
                public_resolution_hint=_shape_policy_resolution_hint(design.shape_id),
                untrusted_candidate=base_scenario.untrusted_candidate,
                canonical_candidate=base_scenario.canonical_candidate,
                repair_target_field=base_scenario.repair_target_field,
                stopping_shape_decision_contract=decision,
            )
        artifact = _freeze_scenario(
            artifact,
            scenario,
            source_instruction=source_instruction,
            projection=projection,
        )
        replay = replay_submechanism_runtime(artifact, scenario)
        if not replay.passed:
            rejection_counts["runtime_replay_failed"] += 1
            continue
        signature = canonical_hash(
            {
                "shape_id": design.shape_id,
                "family": family,
                "tier": tier,
                "stratum_instance_index": instance_index,
                "gold_versions": tuple(item.evidence_version_id for item in gold),
                "program": program,
                "projection": projection,
                "spec_hash": spec.spec_hash,
                "decision_contract": decision,
                "estimand_definition": StoppingShapePolicyDefinition(),
            },
            prefix="finance_stopping_shape_policy_semantics:",
        )
        difficulty = _difficulty_vector(
            cast(Any, design),
            artifact,
            spec,
            family=family,
            tier=tier,
        )
        materializer_hash = canonical_hash(
            {
                "shape_id": design.shape_id,
                "stratum_id": stratum_id,
                "stratum_instance_index": instance_index,
                "design_status": design.design_status,
                "spec_hash": spec.spec_hash,
                "artifact_id": artifact.artifact_id,
                "scenario": scenario,
                "difficulty": difficulty,
                "policy": submechanism_policy_manifest()[scenario.intervention_kind],
            },
            prefix="finance_stopping_shape_policy_materializer:",
        )
        values = {
            "shape_id": design.shape_id,
            "shape_role": design.shape_role,
            "stratum_id": stratum_id,
            "spec_hash": spec.spec_hash,
            "artifact": artifact,
            "scenario": scenario,
            "runtime_replay": replay,
            "difficulty": difficulty,
            "source_semantic_signature": signature,
            "materializer_hash": materializer_hash,
        }
        provisional = StoppingShapeTask.model_construct(task_record_id="pending", **values)
        return StoppingShapeTask(task_record_id=stopping_shape_task_id(provisional), **values)
    raise ValueError(
        "real Finance Evidence cannot support Stopping Shape policy "
        f"{design.shape_id}/{stratum_id}/{instance_index}; "
        f"rejections={dict(sorted(rejection_counts.items()))}"
    )


def _shape_policy_resolution_hint(shape_id: str) -> str:
    hints = {
        "contextual_resolution_choice": (
            "The initial public evidence state requires one resolution action before the "
            "requested record is selected, followed by ordinary calculation and an independent "
            "cross-check. Choose from the public state, not an internal conflict label."
        ),
        "partial_required_evidence": (
            "The unresolved dependency is conditional on an Archive observation. Run the "
            "public probe, then retrieve only the candidate identified by that observation."
        ),
        "single_dimension_conflict": (
            "Use the public activation phase: resolve a missing subject or period before "
            "selection, or normalize a definition after selection and before calculation. "
            "No internal conflict label is public."
        ),
        "verified_extra_call_cost": (
            "The verified Archive snapshot is sealed. Another call cannot add information, "
            "is rejected, and incurs the frozen realized call, token, and utility debit."
        ),
    }
    return hints[shape_id]


def _public_decision_contract_matches(task: StoppingShapeTask) -> bool:
    metadata = task.artifact.task.public.metadata
    parent = metadata.get(PUBLIC_SUBMECHANISM_METADATA_KEY)
    if not isinstance(parent, Mapping):
        return False
    observed = parent.get("stopping_shape_decision_contract")
    decision = task.scenario.stopping_shape_decision_contract
    if decision is None:
        return observed is None
    expected = decision.model_dump(
        mode="json",
        exclude={
            "contract_kind",
            "dependency_decoy_option",
            "oracle_conflict_dimension",
        },
    )
    expected["internal_shape_identity_disclosed"] = False
    public_dump = task.artifact.task.public.model_dump(mode="json")
    text = json.dumps(public_dump, ensure_ascii=False, sort_keys=True)
    return (
        observed == expected
        and "contract_kind" not in _mapping_keys(public_dump)
        and "dependency_decoy_option" not in _mapping_keys(public_dump)
        and "oracle_conflict_dimension" not in _mapping_keys(public_dump)
        and decision.contract_kind not in text
        and task.shape_id not in text
    )


def _conditional_dependency_contract_ready(task: StoppingShapeTask) -> bool:
    decision = task.scenario.stopping_shape_decision_contract
    return bool(
        decision is not None
        and decision.contract_kind == "conditional_dependency_observation_required"
        and decision.dependency_decoy_option is not None
        and decision.resolution_step_count == 2
        and len(task.scenario.evidence_roles) >= 2
        and _dependency_decoy_is_one_dimensional(task)
        and _public_decision_contract_matches(task)
    )


def _dependency_branch_output_contract_ready(task: StoppingShapeTask) -> bool:
    manifest = make_submechanism_manifest(
        corpus=task.artifact.public_corpus,
        scenario=task.scenario,
        environment_id=f"finance_v25_44:manifest-audit:{task.artifact.artifact_id}",
        maximum_tool_calls=MAXIMUM_TOOL_CALLS,
        maximum_failed_tool_calls=MAXIMUM_FAILED_TOOL_CALLS,
        maximum_total_observation_bytes=MAXIMUM_OBSERVATION_BYTES,
    )
    search = next(item for item in manifest.tools if item.tool_id == "search_archive")
    return "dependency_branch_observation" in search.output_contract


def _dependency_decoy_is_one_dimensional(task: StoppingShapeTask) -> bool:
    decision = task.scenario.stopping_shape_decision_contract
    if (
        decision is None
        or decision.dependency_decoy_option is None
        or len(task.scenario.evidence_roles) < 2
    ):
        return False
    unresolved = task.scenario.evidence_roles[1]
    decoy = decision.dependency_decoy_option
    required_queries = {
        (item.subject_alias, item.metric_alias, item.period_label)
        for item in task.scenario.evidence_roles
    }
    decoy_query = (decoy.subject_alias, decoy.metric_alias, decoy.period_label)
    return (
        decoy.subject_alias == unresolved.subject_alias
        and decoy.metric_alias == unresolved.metric_alias
        and decoy.period_label != unresolved.period_label
        and decoy_query not in required_queries
    )


def _single_public_distractor_mismatch(task: StoppingShapeTask) -> str | None:
    corpus_by_id = {item.evidence_id: item for item in task.artifact.public_corpus.evidence}
    required_ids = tuple(item.evidence_id for item in task.scenario.evidence_roles)
    if len(set(required_ids)) != len(required_ids):
        return None
    try:
        gold = tuple(corpus_by_id[item] for item in required_ids)
    except KeyError:
        return None
    required_id_set = set(required_ids)
    distractors = tuple(
        item
        for item in task.artifact.public_corpus.evidence
        if item.evidence_id not in required_id_set
    )
    if len(distractors) != 1:
        return None
    mismatches = _minimum_mismatch_fields(distractors[0], gold)
    return mismatches[0] if len(mismatches) == 1 else None


def _contextual_conflict_decoy_is_one_dimensional(
    task: StoppingShapeTask,
) -> bool:
    mismatch = _single_public_distractor_mismatch(task)
    if task.shape_id == "contextual_resolution_choice":
        return mismatch == "subject"
    if task.shape_id == "single_dimension_conflict":
        return mismatch in {"definition", "period", "payload_context"}
    return False


def _observed_state_difference(
    state: FinanceStoppingObservedEvidenceState | None,
) -> str | None:
    if state is None:
        return None
    observed = state.observed_record
    required = state.required_record
    differences = tuple(
        field
        for field, differs in (
            ("subject", observed.subject_alias != required.subject_alias),
            ("predicate", observed.metric_alias != required.metric_alias),
            ("period", observed.temporal_identity != required.temporal_identity),
            ("source", observed.source_id != required.source_id),
            ("definition", observed.definition_id != required.definition_id),
            (
                "payload_context",
                observed.measurement_context != required.measurement_context,
            ),
        )
        if differs
    )
    return differences[0] if len(differences) == 1 else None


def _matched_contextual_contract_ready(task: StoppingShapeTask) -> bool:
    decision = task.scenario.stopping_shape_decision_contract
    return bool(
        decision is not None
        and decision.contract_kind == "matched_contextual_evidence_state_choice_two_step"
        and decision.oracle_conflict_dimension == "entity_scope_alignment"
        and decision.state_activation_phase == "before_required_evidence_selection"
        and _observed_state_difference(decision.observed_evidence_state) == "subject"
        and decision.observed_conflict_signal
        and tuple(item.tool_id for item in decision.available_resolution_actions)
        == ("normalize_metric_unit_period", "open_document", "query_structured_fact")
        and decision.resolution_step_count == 2
        and _conflict_public_text_isolated(task)
        and _public_decision_contract_matches(task)
    )


def _grounded_conflict_contract_ready(task: StoppingShapeTask) -> bool:
    decision = task.scenario.stopping_shape_decision_contract
    mismatch = _single_public_distractor_mismatch(task)
    expected_dimension = (
        {
            "definition": "source_definition_compatibility",
            "period": "temporal_alignment",
            "payload_context": "measurement_context_alignment",
        }.get(mismatch)
        if mismatch is not None
        else None
    )
    return bool(
        decision is not None
        and decision.contract_kind == "single_conflict_evidence_state_choice_one_step"
        and expected_dimension is not None
        and decision.oracle_conflict_dimension == expected_dimension
        and decision.state_activation_phase
        == (
            "before_required_evidence_selection"
            if mismatch == "period"
            else "after_required_evidence_selection_before_calculation"
        )
        and _observed_state_difference(decision.observed_evidence_state) == mismatch
        and decision.observed_conflict_signal
        and tuple(item.tool_id for item in decision.available_resolution_actions)
        == ("normalize_metric_unit_period", "open_document", "query_structured_fact")
        and decision.resolution_step_count == 1
        and _conflict_public_text_isolated(task)
        and _public_decision_contract_matches(task)
    )


def _expected_state_resolution_tool(task: StoppingShapeTask) -> str | None:
    decision = task.scenario.stopping_shape_decision_contract
    if (
        decision is None
        or decision.contract_kind != "single_conflict_evidence_state_choice_one_step"
    ):
        return None
    if decision.oracle_conflict_dimension == "temporal_alignment":
        return "query_structured_fact"
    if decision.oracle_conflict_dimension in {
        "source_definition_compatibility",
        "measurement_context_alignment",
    }:
        return "normalize_metric_unit_period"
    return None


def _contextual_construction_signature(task: StoppingShapeTask) -> str:
    decision = task.scenario.stopping_shape_decision_contract
    if decision is None:
        return "missing"
    return canonical_hash(
        {
            "contract_kind": decision.contract_kind,
            "observed_conflict_signal": decision.observed_conflict_signal,
            "available_resolution_actions": decision.available_resolution_actions,
            "resolution_step_count": decision.resolution_step_count,
            "state_activation_phase": decision.state_activation_phase,
            "intervention_kind": task.scenario.intervention_kind,
            "expected_host_events": task.scenario.expected_host_events,
        },
        prefix="finance_stopping_contextual_matched_construction:",
    )


def _conflict_public_text_isolated(task: StoppingShapeTask) -> bool:
    decision = task.scenario.stopping_shape_decision_contract
    if decision is None or decision.observed_conflict_signal is None:
        return False
    text = json.dumps(
        task.artifact.task.public.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    ).lower()
    signal_tokens = _semantic_content_tokens(decision.observed_conflict_signal)
    action_tokens = tuple(
        _semantic_content_tokens(item.applicable_when)
        for item in decision.available_resolution_actions
    )
    return (
        "source_definition_compatibility" not in text
        and "source-definition compatibility" not in text
        and bool(signal_tokens)
        and all(not signal_tokens & tokens for tokens in action_tokens)
    )


def _semantic_content_tokens(value: str) -> set[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "at",
        "be",
        "is",
        "of",
        "or",
        "the",
        "to",
        "under",
        "when",
    }
    return {
        token
        for token in re.findall(r"[a-z]+", value.lower())
        if len(token) > 2 and token not in stopwords
    }


def _sealed_cost_contract_ready(task: StoppingShapeTask) -> bool:
    decision = task.scenario.stopping_shape_decision_contract
    return bool(
        decision is not None
        and decision.contract_kind == "sealed_terminal_extra_call_cost"
        and decision.archive_snapshot_sealed is True
        and decision.maximum_additional_information_gain == 0.0
        and decision.realized_call_budget_debit_fraction == 0.25
        and decision.realized_token_budget_debit_fraction == 0.20
        and decision.terminal_utility_loss == 1.0
        and decision.additional_action_rejected is True
        and _public_decision_contract_matches(task)
    )


def _mapping_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        return {
            *(str(key) for key in value),
            *(key for item in value.values() for key in _mapping_keys(item)),
        }
    if isinstance(value, (list, tuple)):
        return {key for item in value for key in _mapping_keys(item)}
    return set()


def _verify_protocol_inputs(
    protocol: FinanceStoppingShapePolicyProtocol,
) -> None:
    references = (
        protocol.source_v25_43_protocol,
        protocol.source_v25_43_population,
        protocol.source_v25_43_contract,
        protocol.source_v25_43_report,
        protocol.source_v25_43_manifest,
        protocol.source_v25_43_records,
        protocol.source_v25_43_terminal_outcomes,
        protocol.source_v25_43_behavior_diagnostics,
        protocol.source_finance_artifacts,
        protocol.source_calibration_contract,
        *protocol.historical_population_references,
    )
    for reference in references:
        if _sha256(Path(reference.path)) != reference.sha256:
            raise ValueError(f"frozen Stopping Shape policy input changed: {reference.path}")


def _reference(path: Path, artifact_id: str) -> FrozenArtifactReference:
    return FrozenArtifactReference(path=str(path), sha256=_sha256(path), artifact_id=artifact_id)


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        "src/trusted_synthesis/runtime/tools.py",
        "src/trusted_synthesis/domains/finance/capability_submechanism_runtime.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_submechanism_population.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_submechanism_flash_development.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_multitier_runtime_resolution.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_shape_stability_protocol.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_shape_policy_protocol.py",
    )
    return {item: _sha256(root / item) for item in paths}


def _render_population_report(
    population: FinanceStoppingShapePolicyPopulation,
) -> str:
    lines = [
        "# Finance v25.44 Stopping Shape Policy Population",
        "",
        f"- Population: {population.population_id}",
        f"- Tasks: {len(population.tasks)}",
        f"- Static ready: {str(population.static_audit.ready).lower()}",
        f"- Next stage: {population.next_permitted_stage}",
        "",
        "| Shape | Stratum | Instance | Status | Program depth | Actions |",
        "| --- | --- | ---: | --- | ---: | ---: |",
    ]
    for item in population.tasks:
        task_id = item.artifact.artifact_id
        lines.append(
            f"| {item.shape_id} | {item.stratum_id} | "
            f"{population.task_stratum_instance_indices[task_id]} | "
            f"{population.task_design_statuses[task_id]} | "
            f"{item.difficulty.program_depth} | "
            f"{item.difficulty.resolution_action_count} |"
        )
    return "\n".join(lines) + "\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare or build v25.44 Stopping Shape Policy")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--source-v25-43-protocol", required=True, type=Path)
    prepare.add_argument("--source-v25-43-population", required=True, type=Path)
    prepare.add_argument("--source-v25-43-contract", required=True, type=Path)
    prepare.add_argument("--source-v25-43-report", required=True, type=Path)
    prepare.add_argument("--source-v25-43-manifest", required=True, type=Path)
    prepare.add_argument("--source-v25-43-records", required=True, type=Path)
    prepare.add_argument("--source-v25-43-terminal-outcomes", required=True, type=Path)
    prepare.add_argument("--source-v25-43-behavior-diagnostics", required=True, type=Path)
    prepare.add_argument("--output", required=True, type=Path)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--source-finance-artifacts", type=Path)
    prepare.add_argument("--source-finance-artifacts-id")
    prepare.add_argument(
        "--additional-historical-population",
        action="append",
        default=[],
        type=Path,
    )
    build = subparsers.add_parser("build")
    build.add_argument("--protocol", required=True, type=Path)
    build.add_argument("--output-dir", required=True, type=Path)
    build.add_argument("--run-id", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "prepare":
        protocol = prepare_stopping_shape_policy_protocol(
            source_v25_43_protocol_path=args.source_v25_43_protocol,
            source_v25_43_population_path=args.source_v25_43_population,
            source_v25_43_contract_path=args.source_v25_43_contract,
            source_v25_43_report_path=args.source_v25_43_report,
            source_v25_43_manifest_path=args.source_v25_43_manifest,
            source_v25_43_records_path=args.source_v25_43_records,
            source_v25_43_terminal_outcomes_path=args.source_v25_43_terminal_outcomes,
            source_v25_43_behavior_diagnostics_path=args.source_v25_43_behavior_diagnostics,
            output_path=args.output,
            run_id=args.run_id,
            source_finance_artifacts_path=args.source_finance_artifacts,
            source_finance_artifacts_id=args.source_finance_artifacts_id,
            additional_historical_population_paths=tuple(args.additional_historical_population),
        )
        print(protocol.model_dump_json(indent=2))
    else:
        population = build_stopping_shape_policy_population(
            protocol_path=args.protocol,
            output_dir=args.output_dir,
            run_id=args.run_id,
        )
        print(population.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
