from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.audit_artifacts import AtomicAuditCaseResult
from trusted_synthesis.core.synthesis.schema import CompiledProofCarryingArtifacts
from trusted_synthesis.core.trajectory.admission import (
    JointCompilationAdmissionArtifact,
    RuntimePublicProjection,
)
from trusted_synthesis.hashing import canonical_hash

CAPABILITY_PREREQUISITE_GRAPH_VERSION = "capability_prerequisite_graph.v1"
PUBLIC_STATE_SUMMARY_SPEC_VERSION = "minimal_public_state_summary_spec.v1"
PUBLIC_STATE_OBSERVATION_VERSION = "public_state_observation.v1"
COMPILED_PUBLIC_STATE_SUMMARY_VERSION = "compiled_public_state_summary.v1"
COMPILED_TASK_CONDITION_LINEAGE_VERSION = "compiled_task_condition_lineage.v1"
CAPABILITY_SCAFFOLD_PROJECTION_VERSION = "capability_scaffold_public_projection.v3"
CAPABILITY_SCAFFOLD_LADDER_VERSION = "capability_scaffold_ladder_compilation.v3"
CAPABILITY_SCAFFOLD_GATE_EVIDENCE_VERSION = "capability_scaffold_gate_evidence.v3"
CAPABILITY_SCAFFOLD_ADMISSION_VERSION = "capability_scaffold_admission.v3"
SCAFFOLD_INVARIANT_STATE_MAPPING_VERSION = "scaffold_invariant_state_mapping.v1"
SCAFFOLD_SEPARATED_TRAJECTORY_VIEW_VERSION = "scaffold_separated_trajectory_view.v1"

ScaffoldLevel = Literal["gamma_0", "gamma_1", "gamma_2", "gamma_3"]
ScaffoldAid = Literal[
    "typed_public_state_summary",
    "capability_prerequisite_contract",
    "action_effect_contract",
    "public_subgoal_dag",
]
PublicSummaryField = Literal[
    "selected_evidence_roles",
    "completed_operation_types",
    "unmet_public_preconditions",
    "resolved_relation_types",
    "unresolved_relation_types",
    "available_operation_references",
    "remaining_tool_budget",
    "public_completion_conditions",
    "typed_failure_category",
]
PublicSummarySource = Literal[
    "task_public",
    "public_tool_schema",
    "public_tool_observation",
    "public_runtime_counter",
]
ObservableInputKind = Literal[
    "public_relation_state",
    "public_evidence_role",
    "public_tool_result",
    "public_failure_category",
    "public_completion_condition",
    "public_budget_state",
]
ModelDecisionKind = Literal[
    "relation_classification",
    "tool_category_selection",
    "argument_instantiation",
    "candidate_verification",
    "failure_recovery",
    "continue_or_stop",
]
PublicEffectKind = Literal[
    "acquire_public_evidence",
    "transform_public_value",
    "validate_public_candidate",
    "repair_public_failure",
    "update_public_completion_state",
    "terminate_if_publicly_complete",
]
ScaffoldGate = Literal[
    "oracle_consistency",
    "public_sufficiency",
    "target_authority_preservation",
    "recursive_noninterference",
    "incremental_necessity",
    "withdrawal_readiness",
    "state_mapping_invariance",
]
BehaviorIdentityField = Literal[
    "tool_choice",
    "tool_arguments",
    "evidence_selection",
    "recovery_action",
    "verification_action",
    "stop_decision",
]
ScaffoldTraceField = Literal[
    "scaffold_level",
    "scaffold_policy_version",
    "public_state_summary",
    "capability_contract",
    "action_effect_contract",
    "public_subgoal_dag",
]

SCAFFOLD_LEVELS: tuple[ScaffoldLevel, ...] = (
    "gamma_0",
    "gamma_1",
    "gamma_2",
    "gamma_3",
)
SCAFFOLD_GATES: tuple[ScaffoldGate, ...] = (
    "oracle_consistency",
    "public_sufficiency",
    "target_authority_preservation",
    "recursive_noninterference",
    "incremental_necessity",
    "withdrawal_readiness",
    "state_mapping_invariance",
)
SCAFFOLD_AIDS_BY_LEVEL: dict[ScaffoldLevel, tuple[ScaffoldAid, ...]] = {
    "gamma_0": (),
    "gamma_1": ("typed_public_state_summary",),
    "gamma_2": (
        "typed_public_state_summary",
        "capability_prerequisite_contract",
        "action_effect_contract",
    ),
    "gamma_3": (
        "typed_public_state_summary",
        "capability_prerequisite_contract",
        "action_effect_contract",
        "public_subgoal_dag",
    ),
}
BEHAVIOR_IDENTITY_FIELDS: tuple[BehaviorIdentityField, ...] = (
    "tool_choice",
    "tool_arguments",
    "evidence_selection",
    "recovery_action",
    "verification_action",
    "stop_decision",
)
SCAFFOLD_TRACE_FIELDS: tuple[ScaffoldTraceField, ...] = (
    "scaffold_level",
    "scaffold_policy_version",
    "public_state_summary",
    "capability_contract",
    "action_effect_contract",
    "public_subgoal_dag",
)
_COMMON_SCAFFOLD_GATE_CHECKS: dict[ScaffoldGate, tuple[str, ...]] = {
    "oracle_consistency": (
        "answer_contract_unchanged",
        "evidence_manifest_unchanged",
        "program_manifest_unchanged",
        "proof_graph_manifest_unchanged",
        "quality_contract_unchanged",
    ),
    "public_sufficiency": (
        "decision_information_present",
        "critical_information_ablation_registered",
        "runtime_projection_replayable",
    ),
    "target_authority_preservation": (
        "model_selects_target_decision",
        "correct_action_absent",
        "correct_arguments_absent",
        "hidden_program_path_absent",
    ),
    "recursive_noninterference": (
        "gold_fields_absent",
        "host_events_absent",
        "mechanism_labels_absent",
        "internal_completion_state_absent",
    ),
    "incremental_necessity": (),
    "withdrawal_readiness": (
        "gamma_zero_projection_exists",
        "semantic_root_unchanged_on_removal",
        "scaffold_absent_from_answer_and_gold",
        "gamma_zero_evaluation_independently_executable",
        "task_definition_unchanged_on_removal",
    ),
    "state_mapping_invariance": (
        "state_mapper_root_unchanged",
        "scaffold_fields_stripped_before_mapping",
        "behavioral_decisions_preserved",
        "scaffold_trace_side_channel_registered",
        "cross_level_behavior_equivalence_registered",
    ),
}

_INCREMENTAL_NECESSITY_CHECKS_BY_LEVEL: dict[ScaffoldLevel, tuple[str, ...]] = {
    "gamma_0": (
        "zero_aid_baseline_exact",
        "unassisted_control_registered",
        "scaffold_rank_order_preserved",
    ),
    "gamma_1": (
        "incremental_aid_set_exact",
        "predecessor_projection_registered",
        "required_increment_ablation_registered",
        "irrelevant_aid_control_registered",
        "scaffold_rank_order_preserved",
    ),
    "gamma_2": (
        "incremental_aid_set_exact",
        "predecessor_projection_registered",
        "required_increment_ablation_registered",
        "irrelevant_aid_control_registered",
        "scaffold_rank_order_preserved",
    ),
    "gamma_3": (
        "incremental_aid_set_exact",
        "predecessor_projection_registered",
        "required_increment_ablation_registered",
        "irrelevant_aid_control_registered",
        "scaffold_rank_order_preserved",
    ),
}

_FORBIDDEN_PUBLIC_MARKERS = (
    "correct_action",
    "correct_argument",
    "gold_answer",
    "gold_evidence",
    "hidden_program",
    "host_event",
    "mechanism_activation",
    "internal_completion",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def scaffold_gate_checks(level: ScaffoldLevel, gate: ScaffoldGate) -> tuple[str, ...]:
    if gate == "incremental_necessity":
        return _INCREMENTAL_NECESSITY_CHECKS_BY_LEVEL[level]
    return _COMMON_SCAFFOLD_GATE_CHECKS[gate]


class ScaffoldInvariantStateMappingContract(FrozenModel):
    mapping_contract_id: str = Field(min_length=1)
    state_space_compilation_id: str = Field(min_length=1)
    base_state_mapper_version: str = Field(min_length=1)
    behavior_identity_fields: tuple[BehaviorIdentityField, ...] = BEHAVIOR_IDENTITY_FIELDS
    stripped_scaffold_fields: tuple[ScaffoldTraceField, ...] = SCAFFOLD_TRACE_FIELDS
    scaffold_trace_side_channel_fields: tuple[ScaffoldTraceField, ...] = SCAFFOLD_TRACE_FIELDS
    strip_before_state_mapping: Literal[True] = True
    scaffold_trace_excluded_from_state_identity: Literal[True] = True
    scaffold_trace_preserved_for_audit: Literal[True] = True
    quotient_state_semantics_unchanged_across_levels: Literal[True] = True
    cross_level_behavior_equivalence_required: Literal[True] = True
    schema_version: str = SCAFFOLD_INVARIANT_STATE_MAPPING_VERSION

    @model_validator(mode="after")
    def validate_mapping(self) -> ScaffoldInvariantStateMappingContract:
        if self.behavior_identity_fields != BEHAVIOR_IDENTITY_FIELDS:
            raise ValueError("scaffold mapping must preserve the complete behavioral identity")
        if self.stripped_scaffold_fields != SCAFFOLD_TRACE_FIELDS:
            raise ValueError("scaffold mapping strip policy is incomplete")
        if self.scaffold_trace_side_channel_fields != SCAFFOLD_TRACE_FIELDS:
            raise ValueError("scaffold audit side channel is incomplete")
        if self.mapping_contract_id != scaffold_invariant_state_mapping_contract_id(self):
            raise ValueError("scaffold-invariant state mapping identity is invalid")
        return self


class ScaffoldSeparatedTrajectoryView(FrozenModel):
    view_id: str = Field(min_length=1)
    mapping_contract_id: str = Field(min_length=1)
    behavior_payload: dict[str, Any]
    scaffold_trace: dict[str, Any]
    behavior_state_identity: str = Field(min_length=1)
    scaffold_trace_hash: str = Field(min_length=1)
    schema_version: str = SCAFFOLD_SEPARATED_TRAJECTORY_VIEW_VERSION

    @model_validator(mode="after")
    def validate_view(self) -> ScaffoldSeparatedTrajectoryView:
        if not self.behavior_payload:
            raise ValueError("scaffold-separated trajectory view needs model behavior")
        if not set(self.behavior_payload) <= set(BEHAVIOR_IDENTITY_FIELDS):
            raise ValueError("behavior payload contains a non-behavioral field")
        if not set(self.scaffold_trace) <= set(SCAFFOLD_TRACE_FIELDS):
            raise ValueError("scaffold trace contains an unregistered field")
        expected_behavior = canonical_hash(
            {
                "mapping_contract_id": self.mapping_contract_id,
                "behavior_payload": self.behavior_payload,
            },
            prefix="scaffold_invariant_behavior_state:",
        )
        if self.behavior_state_identity != expected_behavior:
            raise ValueError("scaffold-invariant behavior identity is invalid")
        expected_trace = canonical_hash(
            self.scaffold_trace,
            prefix="scaffold_trace:",
        )
        if self.scaffold_trace_hash != expected_trace:
            raise ValueError("scaffold trace hash is invalid")
        if self.view_id != scaffold_separated_trajectory_view_id(self):
            raise ValueError("scaffold-separated trajectory view identity is invalid")
        return self


class CapabilityPrerequisiteNode(FrozenModel):
    node_id: str = Field(min_length=1)
    node_key: str = Field(min_length=1)
    capability_id: str = Field(min_length=1)
    public_requirement_id: str = Field(min_length=1)
    prerequisite_node_keys: tuple[str, ...] = ()
    observable_input_kinds: tuple[ObservableInputKind, ...] = Field(min_length=1)
    model_decision_kind: ModelDecisionKind
    allowed_public_effects: tuple[PublicEffectKind, ...] = Field(min_length=1)
    completion_evaluator_id: str = Field(min_length=1)
    completion_evaluator_version: str = Field(min_length=1)
    target_authority: Literal["model"] = "model"
    hidden_resolution_required: Literal[True] = True
    schema_version: str = CAPABILITY_PREREQUISITE_GRAPH_VERSION

    @model_validator(mode="after")
    def validate_node(self) -> CapabilityPrerequisiteNode:
        if self.node_key in self.prerequisite_node_keys:
            raise ValueError("a capability node cannot depend on itself")
        if len(self.prerequisite_node_keys) != len(set(self.prerequisite_node_keys)):
            raise ValueError("capability prerequisites must be unique")
        if len(self.observable_input_kinds) != len(set(self.observable_input_kinds)):
            raise ValueError("capability observable inputs must be unique")
        if len(self.allowed_public_effects) != len(set(self.allowed_public_effects)):
            raise ValueError("capability public effects must be unique")
        if self.node_id != capability_prerequisite_node_id(self):
            raise ValueError("capability prerequisite node identity is invalid")
        return self


class CapabilityPrerequisiteGraph(FrozenModel):
    graph_id: str = Field(min_length=1)
    target_capability_id: str = Field(min_length=1)
    nodes: tuple[CapabilityPrerequisiteNode, ...] = Field(min_length=1)
    target_node_keys: tuple[str, ...] = Field(min_length=1)
    schema_version: str = CAPABILITY_PREREQUISITE_GRAPH_VERSION

    @model_validator(mode="after")
    def validate_graph(self) -> CapabilityPrerequisiteGraph:
        by_key = {item.node_key: item for item in self.nodes}
        if len(by_key) != len(self.nodes):
            raise ValueError("capability graph node keys must be unique")
        if not set(self.target_node_keys) <= set(by_key):
            raise ValueError("capability graph targets unknown nodes")
        if len(self.target_node_keys) != len(set(self.target_node_keys)):
            raise ValueError("capability graph target nodes must be unique")
        if any(
            by_key[key].capability_id != self.target_capability_id for key in self.target_node_keys
        ):
            raise ValueError("capability graph target nodes do not implement the target capability")
        for item in self.nodes:
            unknown = set(item.prerequisite_node_keys) - set(by_key)
            if unknown:
                raise ValueError(f"capability graph has unknown prerequisites: {sorted(unknown)}")
        _assert_acyclic(by_key)
        if self.graph_id != capability_prerequisite_graph_id(self):
            raise ValueError("capability prerequisite graph identity is invalid")
        return self


class MinimalPublicStateSummarySpec(FrozenModel):
    summary_spec_id: str = Field(min_length=1)
    compiler_id: str = Field(min_length=1)
    compiler_version: str = Field(min_length=1)
    source_kinds: tuple[PublicSummarySource, ...] = Field(min_length=1)
    included_fields: tuple[PublicSummaryField, ...] = Field(min_length=1)
    deterministic: Literal[True] = True
    action_neutral: Literal[True] = True
    parameter_neutral: Literal[True] = True
    schema_version: str = PUBLIC_STATE_SUMMARY_SPEC_VERSION

    @model_validator(mode="after")
    def validate_summary(self) -> MinimalPublicStateSummarySpec:
        if len(self.source_kinds) != len(set(self.source_kinds)):
            raise ValueError("public summary sources must be unique")
        if len(self.included_fields) != len(set(self.included_fields)):
            raise ValueError("public summary fields must be unique")
        if self.summary_spec_id != minimal_public_state_summary_spec_id(self):
            raise ValueError("minimal public state summary identity is invalid")
        return self


class PublicStateObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    sequence_index: int = Field(ge=0)
    source_kind: PublicSummarySource
    values: dict[PublicSummaryField, Any] = Field(min_length=1)
    schema_version: str = PUBLIC_STATE_OBSERVATION_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> PublicStateObservation:
        serialized = json.dumps(self.values, ensure_ascii=False, sort_keys=True).lower()
        if any(marker in serialized for marker in _FORBIDDEN_PUBLIC_MARKERS):
            raise ValueError("public state observation contains a forbidden marker")
        if self.observation_id != public_state_observation_id(self):
            raise ValueError("public state observation identity is invalid")
        return self


class CompiledPublicStateSummary(FrozenModel):
    summary_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    summary_spec: MinimalPublicStateSummarySpec
    source_observations: tuple[PublicStateObservation, ...] = Field(min_length=1)
    source_observation_hash: str = Field(min_length=1)
    values: dict[PublicSummaryField, Any]
    correct_action_exposed: Literal[False] = False
    correct_arguments_exposed: Literal[False] = False
    hidden_program_path_exposed: Literal[False] = False
    schema_version: str = COMPILED_PUBLIC_STATE_SUMMARY_VERSION

    @model_validator(mode="after")
    def validate_summary(self) -> CompiledPublicStateSummary:
        observation_ids = tuple(item.observation_id for item in self.source_observations)
        if len(observation_ids) != len(set(observation_ids)):
            raise ValueError("public state summary contains duplicate observations")
        if tuple(item.sequence_index for item in self.source_observations) != tuple(
            range(len(self.source_observations))
        ):
            raise ValueError("public state summary observations are incomplete or unordered")
        if any(item.task_id != self.task_id for item in self.source_observations):
            raise ValueError("public state summary crosses task identities")
        if any(
            item.source_kind not in self.summary_spec.source_kinds
            for item in self.source_observations
        ):
            raise ValueError("public state summary uses an unregistered source kind")
        expected_source_hash = canonical_hash(
            [item.model_dump(mode="json") for item in self.source_observations],
            prefix="public_state_summary_observations:",
        )
        if self.source_observation_hash != expected_source_hash:
            raise ValueError("public state summary source hash is invalid")
        expected_values = _compile_public_summary_values(
            self.summary_spec,
            self.source_observations,
        )
        if self.values != expected_values:
            raise ValueError("public state summary does not deterministically replay")
        if self.summary_id != compiled_public_state_summary_id(self):
            raise ValueError("compiled public state summary identity is invalid")
        return self


class PublicCapabilityNode(FrozenModel):
    node_key: str = Field(min_length=1)
    capability_id: str = Field(min_length=1)
    public_requirement_id: str = Field(min_length=1)
    prerequisite_node_keys: tuple[str, ...] = ()
    observable_input_kinds: tuple[ObservableInputKind, ...] = Field(min_length=1)
    model_decision_kind: ModelDecisionKind
    allowed_public_effects: tuple[PublicEffectKind, ...] = Field(min_length=1)
    target_authority: Literal["model"] = "model"


class CapabilityAwarePublicProjection(FrozenModel):
    projection_id: str = Field(min_length=1)
    compiled_task_condition_id: str = Field(min_length=1)
    joint_admission_id: str = Field(min_length=1)
    joint_compilation_id: str = Field(min_length=1)
    omega_component_manifest_id: str = Field(min_length=1)
    dependency_graph_id: str = Field(min_length=1)
    runtime_id: str = Field(min_length=1)
    base_runtime_projection: RuntimePublicProjection
    state_mapping_contract_id: str = Field(min_length=1)
    target_capability_id: str = Field(min_length=1)
    scaffold_level: ScaffoldLevel
    scaffold_rank: Literal[0, 1, 2, 3]
    scaffold_policy_version: str = Field(min_length=1)
    scaffold_payload_hash: str = Field(min_length=1)
    aid_kinds: tuple[ScaffoldAid, ...]
    public_summary_spec: MinimalPublicStateSummarySpec | None = None
    public_capability_nodes: tuple[PublicCapabilityNode, ...] = ()
    public_dependency_edges: tuple[tuple[str, str], ...] = ()
    correct_action_exposed: Literal[False] = False
    correct_arguments_exposed: Literal[False] = False
    hidden_program_path_exposed: Literal[False] = False
    host_completion_label_exposed: Literal[False] = False
    schema_version: str = CAPABILITY_SCAFFOLD_PROJECTION_VERSION

    @model_validator(mode="after")
    def validate_projection(self) -> CapabilityAwarePublicProjection:
        expected_rank = SCAFFOLD_LEVELS.index(self.scaffold_level)
        if self.scaffold_rank != expected_rank:
            raise ValueError("capability scaffold rank differs from its level")
        if self.aid_kinds != SCAFFOLD_AIDS_BY_LEVEL[self.scaffold_level]:
            raise ValueError("capability scaffold aids differ from the frozen ladder")
        if self.base_runtime_projection.runtime_id != self.runtime_id:
            raise ValueError("capability scaffold crosses runtime identities")
        if self.base_runtime_projection.joint_compilation_id != self.joint_compilation_id:
            raise ValueError("capability scaffold crosses Joint Compilation identities")
        node_keys = {item.node_key for item in self.public_capability_nodes}
        if any(
            not set(item.prerequisite_node_keys) <= node_keys
            for item in self.public_capability_nodes
        ):
            raise ValueError("capability scaffold contains an unknown public prerequisite")
        if self.scaffold_rank == 0:
            if (
                self.public_summary_spec
                or self.public_capability_nodes
                or self.public_dependency_edges
            ):
                raise ValueError("gamma_0 cannot contain compiler assistance")
        elif self.scaffold_rank == 1:
            if not self.public_summary_spec:
                raise ValueError("gamma_1 requires a public state summary")
            if self.public_capability_nodes or self.public_dependency_edges:
                raise ValueError("gamma_1 cannot expose capability contracts or a DAG")
        elif self.scaffold_rank == 2:
            if not self.public_summary_spec or not self.public_capability_nodes:
                raise ValueError("gamma_2 requires summaries and capability contracts")
            if self.public_dependency_edges:
                raise ValueError("gamma_2 cannot expose the public subgoal DAG")
        elif not (self.public_summary_spec and self.public_capability_nodes):
            raise ValueError("gamma_3 requires the complete public scaffold")
        if any(item.target_authority != "model" for item in self.public_capability_nodes):
            raise ValueError("capability scaffold cannot move target authority to the compiler")
        if self.scaffold_payload_hash != capability_scaffold_payload_hash(self):
            raise ValueError("capability scaffold payload hash is invalid")
        if self.compiled_task_condition_id != compiled_task_condition_id(self):
            raise ValueError("compiled task condition identity is invalid")
        if self.projection_id != capability_aware_public_projection_id(self):
            raise ValueError("capability-aware public projection identity is invalid")
        return self


class CapabilityScaffoldLadderCompilation(FrozenModel):
    ladder_id: str = Field(min_length=1)
    joint_admission: JointCompilationAdmissionArtifact
    joint_compilation_id: str = Field(min_length=1)
    omega_component_manifest_id: str = Field(min_length=1)
    runtime_id: str = Field(min_length=1)
    target_capability_id: str = Field(min_length=1)
    scaffold_policy_version: str = Field(min_length=1)
    dependency_graph: CapabilityPrerequisiteGraph
    summary_spec: MinimalPublicStateSummarySpec
    state_mapping_contract: ScaffoldInvariantStateMappingContract
    projections: tuple[CapabilityAwarePublicProjection, ...] = Field(min_length=4, max_length=4)
    valid_state_space_invariant_across_levels: Literal[True] = True
    scaffold_changes_reachability_only: Literal[True] = True
    schema_version: str = CAPABILITY_SCAFFOLD_LADDER_VERSION

    @model_validator(mode="after")
    def validate_ladder(self) -> CapabilityScaffoldLadderCompilation:
        if self.joint_admission.status != "admitted":
            raise ValueError("capability scaffolds require an admitted Joint Compilation")
        if self.joint_admission.joint_compilation_id != self.joint_compilation_id:
            raise ValueError("capability ladder crosses Joint Compilation identities")
        if self.joint_admission.omega_component_manifest_id != self.omega_component_manifest_id:
            raise ValueError("capability ladder crosses Omega manifests")
        if self.dependency_graph.target_capability_id != self.target_capability_id:
            raise ValueError("capability ladder targets a different dependency graph")
        if (
            self.state_mapping_contract.state_space_compilation_id
            != self.joint_admission.state_space_compilation_id
            or self.state_mapping_contract.base_state_mapper_version
            != self.joint_admission.state_mapper_version
        ):
            raise ValueError("capability ladder changes the admitted quotient state semantics")
        if tuple(item.scaffold_level for item in self.projections) != SCAFFOLD_LEVELS:
            raise ValueError("capability ladder levels are incomplete or unordered")
        admitted_by_runtime = {
            item.runtime_id: item for item in self.joint_admission.runtime_projections
        }
        if self.runtime_id not in admitted_by_runtime:
            raise ValueError("capability ladder runtime was not jointly admitted")
        base = admitted_by_runtime[self.runtime_id]
        if any(
            item.joint_admission_id != self.joint_admission.admission_id
            or item.joint_compilation_id != self.joint_compilation_id
            or item.omega_component_manifest_id != self.omega_component_manifest_id
            or item.dependency_graph_id != self.dependency_graph.graph_id
            or item.runtime_id != self.runtime_id
            or item.base_runtime_projection != base
            or item.target_capability_id != self.target_capability_id
            or item.scaffold_policy_version != self.scaffold_policy_version
            or item.state_mapping_contract_id != self.state_mapping_contract.mapping_contract_id
            for item in self.projections
        ):
            raise ValueError("capability ladder projections do not share one condition root")
        public_nodes = _public_capability_nodes(self.dependency_graph)
        public_edges = _public_dependency_edges(self.dependency_graph)
        expected_projections = tuple(
            _make_capability_projection(
                joint_admission=self.joint_admission,
                base=base,
                target_capability_id=self.target_capability_id,
                scaffold_level=level,
                scaffold_policy_version=self.scaffold_policy_version,
                state_mapping_contract_id=self.state_mapping_contract.mapping_contract_id,
                dependency_graph_id=self.dependency_graph.graph_id,
                summary_spec=self.summary_spec,
                public_nodes=public_nodes,
                public_edges=public_edges,
            )
            for level in SCAFFOLD_LEVELS
        )
        if self.projections != expected_projections:
            raise ValueError("capability ladder projections do not deterministically replay")
        if self.ladder_id != capability_scaffold_ladder_id(self):
            raise ValueError("capability scaffold ladder identity is invalid")
        return self


class CapabilityScaffoldGateEvidence(FrozenModel):
    evidence_id: str = Field(min_length=1)
    ladder_id: str = Field(min_length=1)
    projection_id: str = Field(min_length=1)
    joint_compilation_id: str = Field(min_length=1)
    scaffold_level: ScaffoldLevel
    gate: ScaffoldGate
    case_results: tuple[AtomicAuditCaseResult, ...] = Field(min_length=1)
    evaluator_id: str = Field(min_length=1)
    evaluator_version: str = Field(min_length=1)
    evaluator_manifest_hash: str = Field(min_length=1)
    schema_version: str = CAPABILITY_SCAFFOLD_GATE_EVIDENCE_VERSION

    @model_validator(mode="after")
    def validate_evidence(self) -> CapabilityScaffoldGateEvidence:
        expected_checks = scaffold_gate_checks(self.scaffold_level, self.gate)
        observed_checks = tuple(sorted(item.check_id for item in self.case_results))
        if (
            observed_checks != tuple(sorted(expected_checks))
            or len(observed_checks) != len(set(observed_checks))
        ):
            raise ValueError("capability scaffold gate checks are incomplete")
        if any(
            item.subject_id != self.projection_id
            or self.ladder_id not in item.input_artifact_ids
            or self.projection_id not in item.input_artifact_ids
            for item in self.case_results
        ):
            raise ValueError("capability scaffold audit case crosses compilation identities")
        if any(
            item.implementation_manifest
            != {
                "evaluator_id": self.evaluator_id,
                "evaluator_version": self.evaluator_version,
                "check_id": item.check_id,
            }
            or item.replay_implementation_manifest
            != {
                "evaluator_id": f"{self.evaluator_id}.independent",
                "evaluator_version": self.evaluator_version,
                "check_id": item.check_id,
            }
            for item in self.case_results
        ):
            raise ValueError("capability scaffold audit case uses an unknown implementation")
        expected_manifest = canonical_hash(
            {
                "evaluator_id": self.evaluator_id,
                "evaluator_version": self.evaluator_version,
            },
            prefix="capability_scaffold_evaluator_manifest:",
        )
        if self.evaluator_manifest_hash != expected_manifest:
            raise ValueError("capability scaffold evaluator manifest identity is invalid")
        if self.evidence_id != capability_scaffold_gate_evidence_id(self):
            raise ValueError("capability scaffold gate Evidence identity is invalid")
        return self

    @property
    def checks(self) -> dict[str, bool]:
        return {item.check_id: item.check_passed for item in self.case_results}

    @property
    def audit_case_ids(self) -> tuple[str, ...]:
        return tuple(item.case_id for item in self.case_results)

    @property
    def passed(self) -> bool:
        return all(item.check_passed for item in self.case_results)


class CapabilityScaffoldAdmissionArtifact(FrozenModel):
    admission_id: str = Field(min_length=1)
    ladder_id: str = Field(min_length=1)
    joint_admission_id: str = Field(min_length=1)
    joint_compilation_id: str = Field(min_length=1)
    ladder: CapabilityScaffoldLadderCompilation
    gate_evidence: tuple[CapabilityScaffoldGateEvidence, ...] = Field(min_length=28, max_length=28)
    gates_by_level: dict[str, dict[str, bool]]
    status: Literal["admitted", "blocked"]
    blockers: tuple[str, ...]
    next_transition: Literal[
        "bridge_rollout_development",
        "capability_scaffold_repair_only",
    ]
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = CAPABILITY_SCAFFOLD_ADMISSION_VERSION

    @model_validator(mode="after")
    def validate_admission(self) -> CapabilityScaffoldAdmissionArtifact:
        expected_keys = {(level, gate) for level in SCAFFOLD_LEVELS for gate in SCAFFOLD_GATES}
        observed_keys = {(item.scaffold_level, item.gate) for item in self.gate_evidence}
        if observed_keys != expected_keys or len(observed_keys) != len(self.gate_evidence):
            raise ValueError("capability scaffold admission Evidence is incomplete or duplicated")
        if (
            self.ladder.ladder_id != self.ladder_id
            or self.ladder.joint_admission.admission_id != self.joint_admission_id
            or self.ladder.joint_compilation_id != self.joint_compilation_id
        ):
            raise ValueError("capability scaffold admission root identities are inconsistent")
        expected_gates = _derive_scaffold_gates(self.ladder, self.gate_evidence)
        if self.gates_by_level != expected_gates:
            raise ValueError("capability scaffold gates were not derived from Evidence")
        projections = {item.scaffold_level: item for item in self.ladder.projections}
        if any(
            item.ladder_id != self.ladder_id
            or item.joint_compilation_id != self.joint_compilation_id
            or item.projection_id != projections[item.scaffold_level].projection_id
            for item in self.gate_evidence
        ):
            raise ValueError("capability scaffold gate Evidence crosses compilation identities")
        expected_blockers = tuple(
            sorted(
                f"{level}:{gate}"
                for level in SCAFFOLD_LEVELS
                for gate in SCAFFOLD_GATES
                if not self.gates_by_level.get(level, {}).get(gate, False)
            )
        )
        if self.blockers != expected_blockers:
            raise ValueError("capability scaffold blockers are inconsistent")
        expected_status = "blocked" if expected_blockers else "admitted"
        if self.status != expected_status:
            raise ValueError("capability scaffold admission status is inconsistent")
        expected_transition = (
            "capability_scaffold_repair_only" if expected_blockers else "bridge_rollout_development"
        )
        if self.next_transition != expected_transition:
            raise ValueError("capability scaffold admission transition is inconsistent")
        if self.admission_id != capability_scaffold_admission_id(self):
            raise ValueError("capability scaffold admission identity is invalid")
        return self


class CompiledTaskConditionLineage(FrozenModel):
    lineage_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    compiled_task_condition_id: str = Field(min_length=1)
    projection_id: str = Field(min_length=1)
    ladder_id: str = Field(min_length=1)
    scaffold_admission_id: str = Field(min_length=1)
    joint_admission_id: str = Field(min_length=1)
    joint_compilation_id: str = Field(min_length=1)
    omega_context_id: str = Field(min_length=1)
    omega_component_manifest_id: str = Field(min_length=1)
    runtime_projection_id: str = Field(min_length=1)
    runtime_authority_policy_id: str = Field(min_length=1)
    dependency_graph_id: str = Field(min_length=1)
    public_summary_spec_id: str | None = Field(default=None, min_length=1)
    state_mapping_contract_id: str = Field(min_length=1)
    scaffold_payload_hash: str = Field(min_length=1)
    scaffold_level: ScaffoldLevel
    schema_version: str = COMPILED_TASK_CONDITION_LINEAGE_VERSION

    @model_validator(mode="after")
    def validate_lineage(self) -> CompiledTaskConditionLineage:
        if self.lineage_id != compiled_task_condition_lineage_id(self):
            raise ValueError("compiled task condition lineage identity is invalid")
        return self


def make_capability_prerequisite_node(
    *,
    node_key: str,
    capability_id: str,
    public_requirement_id: str,
    prerequisite_node_keys: tuple[str, ...] = (),
    observable_input_kinds: tuple[ObservableInputKind, ...],
    model_decision_kind: ModelDecisionKind,
    allowed_public_effects: tuple[PublicEffectKind, ...],
    completion_evaluator_id: str,
    completion_evaluator_version: str,
) -> CapabilityPrerequisiteNode:
    values = {
        "node_key": node_key,
        "capability_id": capability_id,
        "public_requirement_id": public_requirement_id,
        "prerequisite_node_keys": tuple(sorted(prerequisite_node_keys)),
        "observable_input_kinds": tuple(sorted(observable_input_kinds)),
        "model_decision_kind": model_decision_kind,
        "allowed_public_effects": tuple(sorted(allowed_public_effects)),
        "completion_evaluator_id": completion_evaluator_id,
        "completion_evaluator_version": completion_evaluator_version,
        "schema_version": CAPABILITY_PREREQUISITE_GRAPH_VERSION,
    }
    provisional = CapabilityPrerequisiteNode.model_construct(node_id="pending", **values)
    return CapabilityPrerequisiteNode(
        node_id=capability_prerequisite_node_id(provisional),
        **values,
    )


def make_capability_prerequisite_graph(
    *,
    target_capability_id: str,
    nodes: Sequence[CapabilityPrerequisiteNode],
    target_node_keys: tuple[str, ...],
) -> CapabilityPrerequisiteGraph:
    values = {
        "target_capability_id": target_capability_id,
        "nodes": tuple(sorted(nodes, key=lambda item: item.node_key)),
        "target_node_keys": tuple(sorted(target_node_keys)),
        "schema_version": CAPABILITY_PREREQUISITE_GRAPH_VERSION,
    }
    provisional = CapabilityPrerequisiteGraph.model_construct(graph_id="pending", **values)
    return CapabilityPrerequisiteGraph(
        graph_id=capability_prerequisite_graph_id(provisional),
        **values,
    )


def make_minimal_public_state_summary_spec(
    *,
    compiler_id: str,
    compiler_version: str,
    source_kinds: tuple[PublicSummarySource, ...],
    included_fields: tuple[PublicSummaryField, ...],
) -> MinimalPublicStateSummarySpec:
    values = {
        "compiler_id": compiler_id,
        "compiler_version": compiler_version,
        "source_kinds": tuple(sorted(source_kinds)),
        "included_fields": tuple(sorted(included_fields)),
        "schema_version": PUBLIC_STATE_SUMMARY_SPEC_VERSION,
    }
    provisional = MinimalPublicStateSummarySpec.model_construct(summary_spec_id="pending", **values)
    return MinimalPublicStateSummarySpec(
        summary_spec_id=minimal_public_state_summary_spec_id(provisional),
        **values,
    )


def make_public_state_observation(
    *,
    task_id: str,
    sequence_index: int,
    source_kind: PublicSummarySource,
    values: Mapping[PublicSummaryField, Any],
) -> PublicStateObservation:
    payload = {
        "task_id": task_id,
        "sequence_index": sequence_index,
        "source_kind": source_kind,
        "values": dict(sorted(values.items())),
        "schema_version": PUBLIC_STATE_OBSERVATION_VERSION,
    }
    provisional = PublicStateObservation.model_construct(observation_id="pending", **payload)
    return PublicStateObservation(
        observation_id=public_state_observation_id(provisional),
        **payload,
    )


def compile_public_state_summary(
    summary_spec: MinimalPublicStateSummarySpec,
    observations: Sequence[PublicStateObservation],
) -> CompiledPublicStateSummary:
    rows = tuple(sorted(observations, key=lambda item: item.sequence_index))
    if not rows:
        raise ValueError("public state summary compilation requires observations")
    values = {
        "task_id": rows[0].task_id,
        "summary_spec": summary_spec,
        "source_observations": rows,
        "source_observation_hash": canonical_hash(
            [item.model_dump(mode="json") for item in rows],
            prefix="public_state_summary_observations:",
        ),
        "values": _compile_public_summary_values(summary_spec, rows),
        "schema_version": COMPILED_PUBLIC_STATE_SUMMARY_VERSION,
    }
    provisional = CompiledPublicStateSummary.model_construct(summary_id="pending", **values)
    return CompiledPublicStateSummary(
        summary_id=compiled_public_state_summary_id(provisional),
        **values,
    )


def make_scaffold_invariant_state_mapping_contract(
    joint_admission: JointCompilationAdmissionArtifact,
) -> ScaffoldInvariantStateMappingContract:
    values = {
        "state_space_compilation_id": joint_admission.state_space_compilation_id,
        "base_state_mapper_version": joint_admission.state_mapper_version,
        "behavior_identity_fields": BEHAVIOR_IDENTITY_FIELDS,
        "stripped_scaffold_fields": SCAFFOLD_TRACE_FIELDS,
        "scaffold_trace_side_channel_fields": SCAFFOLD_TRACE_FIELDS,
        "schema_version": SCAFFOLD_INVARIANT_STATE_MAPPING_VERSION,
    }
    provisional = ScaffoldInvariantStateMappingContract.model_construct(
        mapping_contract_id="pending",
        **values,
    )
    return ScaffoldInvariantStateMappingContract(
        mapping_contract_id=scaffold_invariant_state_mapping_contract_id(provisional),
        **values,
    )


def separate_scaffold_trace_for_state_mapping(
    mapping_contract: ScaffoldInvariantStateMappingContract,
    *,
    behavior_payload: Mapping[str, Any],
    scaffold_trace: Mapping[str, Any],
) -> ScaffoldSeparatedTrajectoryView:
    values = {
        "mapping_contract_id": mapping_contract.mapping_contract_id,
        "behavior_payload": dict(sorted(behavior_payload.items())),
        "scaffold_trace": dict(sorted(scaffold_trace.items())),
        "behavior_state_identity": canonical_hash(
            {
                "mapping_contract_id": mapping_contract.mapping_contract_id,
                "behavior_payload": dict(sorted(behavior_payload.items())),
            },
            prefix="scaffold_invariant_behavior_state:",
        ),
        "scaffold_trace_hash": canonical_hash(
            dict(sorted(scaffold_trace.items())),
            prefix="scaffold_trace:",
        ),
        "schema_version": SCAFFOLD_SEPARATED_TRAJECTORY_VIEW_VERSION,
    }
    provisional = ScaffoldSeparatedTrajectoryView.model_construct(view_id="pending", **values)
    return ScaffoldSeparatedTrajectoryView(
        view_id=scaffold_separated_trajectory_view_id(provisional),
        **values,
    )


def compile_capability_scaffold_ladder(
    artifacts: CompiledProofCarryingArtifacts,
    joint_admission: JointCompilationAdmissionArtifact,
    *,
    runtime_id: str,
    target_capability_id: str,
    scaffold_policy_version: str,
    dependency_graph: CapabilityPrerequisiteGraph,
    summary_spec: MinimalPublicStateSummarySpec,
    state_mapping_contract: ScaffoldInvariantStateMappingContract,
) -> CapabilityScaffoldLadderCompilation:
    joint = artifacts.joint_compilation
    if joint_admission.status != "admitted":
        raise ValueError("capability scaffold compilation requires Joint Compilation admission")
    if joint_admission.joint_compilation_id != joint.artifact_id:
        raise ValueError("capability scaffold admission belongs to another Joint Compilation")
    if dependency_graph.target_capability_id != target_capability_id:
        raise ValueError("capability dependency graph targets another capability")
    if (
        state_mapping_contract.state_space_compilation_id
        != joint_admission.state_space_compilation_id
        or state_mapping_contract.base_state_mapper_version != joint_admission.state_mapper_version
    ):
        raise ValueError("scaffold state mapping differs from Joint Compilation admission")
    by_runtime = {item.runtime_id: item for item in joint_admission.runtime_projections}
    if runtime_id not in by_runtime:
        raise ValueError("capability scaffold runtime was not admitted")
    base = by_runtime[runtime_id]
    public_nodes = _public_capability_nodes(dependency_graph)
    public_edges = _public_dependency_edges(dependency_graph)
    projections = tuple(
        _make_capability_projection(
            joint_admission=joint_admission,
            base=base,
            target_capability_id=target_capability_id,
            scaffold_level=level,
            scaffold_policy_version=scaffold_policy_version,
            state_mapping_contract_id=state_mapping_contract.mapping_contract_id,
            dependency_graph_id=dependency_graph.graph_id,
            summary_spec=summary_spec,
            public_nodes=public_nodes,
            public_edges=public_edges,
        )
        for level in SCAFFOLD_LEVELS
    )
    for projection in projections:
        if _projection_leaks_oracle(projection, artifacts):
            raise ValueError("capability scaffold public projection leaks Oracle-only content")
    values = {
        "joint_admission": joint_admission,
        "joint_compilation_id": joint.artifact_id,
        "omega_component_manifest_id": joint.component_manifest.manifest_id,
        "runtime_id": runtime_id,
        "target_capability_id": target_capability_id,
        "scaffold_policy_version": scaffold_policy_version,
        "dependency_graph": dependency_graph,
        "summary_spec": summary_spec,
        "state_mapping_contract": state_mapping_contract,
        "projections": projections,
        "schema_version": CAPABILITY_SCAFFOLD_LADDER_VERSION,
    }
    provisional = CapabilityScaffoldLadderCompilation.model_construct(ladder_id="pending", **values)
    return CapabilityScaffoldLadderCompilation(
        ladder_id=capability_scaffold_ladder_id(provisional),
        **values,
    )


def make_capability_scaffold_gate_evidence(
    *,
    ladder_id: str,
    projection_id: str,
    joint_compilation_id: str,
    scaffold_level: ScaffoldLevel,
    gate: ScaffoldGate,
    case_results: Sequence[AtomicAuditCaseResult],
    evaluator_id: str,
    evaluator_version: str,
) -> CapabilityScaffoldGateEvidence:
    evaluator_manifest_hash = canonical_hash(
        {
            "evaluator_id": evaluator_id,
            "evaluator_version": evaluator_version,
        },
        prefix="capability_scaffold_evaluator_manifest:",
    )
    values = {
        "ladder_id": ladder_id,
        "projection_id": projection_id,
        "joint_compilation_id": joint_compilation_id,
        "scaffold_level": scaffold_level,
        "gate": gate,
        "case_results": tuple(sorted(case_results, key=lambda item: item.check_id)),
        "evaluator_id": evaluator_id,
        "evaluator_version": evaluator_version,
        "evaluator_manifest_hash": evaluator_manifest_hash,
        "schema_version": CAPABILITY_SCAFFOLD_GATE_EVIDENCE_VERSION,
    }
    provisional = CapabilityScaffoldGateEvidence.model_construct(evidence_id="pending", **values)
    return CapabilityScaffoldGateEvidence(
        evidence_id=capability_scaffold_gate_evidence_id(provisional),
        **values,
    )


def admit_capability_scaffold_ladder(
    ladder: CapabilityScaffoldLadderCompilation,
    gate_evidence: Sequence[CapabilityScaffoldGateEvidence],
) -> CapabilityScaffoldAdmissionArtifact:
    evidence = tuple(sorted(gate_evidence, key=lambda item: (item.scaffold_level, item.gate)))
    projections = {item.scaffold_level: item for item in ladder.projections}
    for item in evidence:
        projection = projections.get(item.scaffold_level)
        if (
            item.ladder_id != ladder.ladder_id
            or item.joint_compilation_id != ladder.joint_compilation_id
            or projection is None
            or item.projection_id != projection.projection_id
        ):
            raise ValueError("capability scaffold gate Evidence crosses compilation identities")
    gates_by_level = _derive_scaffold_gates(ladder, evidence)
    blockers = tuple(
        sorted(
            f"{level}:{gate}"
            for level in SCAFFOLD_LEVELS
            for gate in SCAFFOLD_GATES
            if not gates_by_level[level][gate]
        )
    )
    values: dict[str, Any] = {
        "ladder_id": ladder.ladder_id,
        "joint_admission_id": ladder.joint_admission.admission_id,
        "joint_compilation_id": ladder.joint_compilation_id,
        "ladder": ladder,
        "gate_evidence": evidence,
        "gates_by_level": gates_by_level,
        "status": "blocked" if blockers else "admitted",
        "blockers": blockers,
        "next_transition": (
            "capability_scaffold_repair_only" if blockers else "bridge_rollout_development"
        ),
        "schema_version": CAPABILITY_SCAFFOLD_ADMISSION_VERSION,
    }
    provisional = CapabilityScaffoldAdmissionArtifact.model_construct(
        admission_id="pending", **values
    )
    return CapabilityScaffoldAdmissionArtifact(
        admission_id=capability_scaffold_admission_id(provisional),
        **values,
    )


def make_compiled_task_condition_lineage(
    ladder: CapabilityScaffoldLadderCompilation,
    admission: CapabilityScaffoldAdmissionArtifact,
    *,
    scaffold_level: ScaffoldLevel,
) -> CompiledTaskConditionLineage:
    if admission.status != "admitted" or admission.ladder != ladder:
        raise ValueError("compiled task condition lineage requires the admitted ladder")
    projection = next(
        item for item in ladder.projections if item.scaffold_level == scaffold_level
    )
    values = {
        "task_id": projection.base_runtime_projection.task_id,
        "compiled_task_condition_id": projection.compiled_task_condition_id,
        "projection_id": projection.projection_id,
        "ladder_id": ladder.ladder_id,
        "scaffold_admission_id": admission.admission_id,
        "joint_admission_id": ladder.joint_admission.admission_id,
        "joint_compilation_id": ladder.joint_compilation_id,
        "omega_context_id": projection.base_runtime_projection.omega_context_id,
        "omega_component_manifest_id": ladder.omega_component_manifest_id,
        "runtime_projection_id": projection.base_runtime_projection.projection_id,
        "runtime_authority_policy_id": (
            projection.base_runtime_projection.authority_policy.policy_id
        ),
        "dependency_graph_id": ladder.dependency_graph.graph_id,
        "public_summary_spec_id": (
            projection.public_summary_spec.summary_spec_id
            if projection.public_summary_spec
            else None
        ),
        "state_mapping_contract_id": ladder.state_mapping_contract.mapping_contract_id,
        "scaffold_payload_hash": projection.scaffold_payload_hash,
        "scaffold_level": scaffold_level,
        "schema_version": COMPILED_TASK_CONDITION_LINEAGE_VERSION,
    }
    provisional = CompiledTaskConditionLineage.model_construct(lineage_id="pending", **values)
    return CompiledTaskConditionLineage(
        lineage_id=compiled_task_condition_lineage_id(provisional),
        **values,
    )


def capability_prerequisite_node_id(value: CapabilityPrerequisiteNode) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"node_id"}),
        prefix="capability_prerequisite_node:",
    )


def capability_prerequisite_graph_id(value: CapabilityPrerequisiteGraph) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"graph_id"}),
        prefix="capability_prerequisite_graph:",
    )


def minimal_public_state_summary_spec_id(value: MinimalPublicStateSummarySpec) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"summary_spec_id"}),
        prefix="minimal_public_state_summary_spec:",
    )


def public_state_observation_id(value: PublicStateObservation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"observation_id"}),
        prefix="public_state_observation:",
    )


def compiled_public_state_summary_id(value: CompiledPublicStateSummary) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"summary_id"}),
        prefix="compiled_public_state_summary:",
    )


def scaffold_invariant_state_mapping_contract_id(
    value: ScaffoldInvariantStateMappingContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"mapping_contract_id"}),
        prefix="scaffold_invariant_state_mapping:",
    )


def scaffold_separated_trajectory_view_id(value: ScaffoldSeparatedTrajectoryView) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"view_id"}),
        prefix="scaffold_separated_trajectory_view:",
    )


def compiled_task_condition_id(value: CapabilityAwarePublicProjection) -> str:
    identity = {
        "task_id": value.base_runtime_projection.task_id,
        "runtime_id": value.runtime_id,
        "runtime_authority_policy_id": value.base_runtime_projection.authority_policy.policy_id,
        "joint_admission_id": value.joint_admission_id,
        "joint_compilation_id": value.joint_compilation_id,
        "omega_context_id": value.base_runtime_projection.omega_context_id,
        "omega_component_manifest_id": value.omega_component_manifest_id,
        "target_capability_id": value.target_capability_id,
        "scaffold_level": value.scaffold_level,
        "scaffold_policy_version": value.scaffold_policy_version,
        "state_mapping_contract_id": value.state_mapping_contract_id,
        "base_projection_id": value.base_runtime_projection.projection_id,
        "dependency_graph_id": value.dependency_graph_id,
        "scaffold_payload_hash": value.scaffold_payload_hash,
        "schema_version": value.schema_version,
    }
    return canonical_hash(identity, prefix="compiled_task_condition:")


def capability_scaffold_payload_hash(value: CapabilityAwarePublicProjection) -> str:
    return canonical_hash(
        {
            "scaffold_level": value.scaffold_level,
            "scaffold_rank": value.scaffold_rank,
            "aid_kinds": value.aid_kinds,
            "public_summary_spec": (
                value.public_summary_spec.model_dump(mode="json")
                if value.public_summary_spec
                else None
            ),
            "public_capability_nodes": [
                item.model_dump(mode="json") for item in value.public_capability_nodes
            ],
            "public_dependency_edges": value.public_dependency_edges,
            "correct_action_exposed": value.correct_action_exposed,
            "correct_arguments_exposed": value.correct_arguments_exposed,
            "hidden_program_path_exposed": value.hidden_program_path_exposed,
            "host_completion_label_exposed": value.host_completion_label_exposed,
        },
        prefix="capability_scaffold_payload:",
    )


def capability_aware_public_projection_id(value: CapabilityAwarePublicProjection) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"projection_id"}),
        prefix="capability_aware_public_projection:",
    )


def capability_scaffold_ladder_id(value: CapabilityScaffoldLadderCompilation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"ladder_id"}),
        prefix="capability_scaffold_ladder:",
    )


def capability_scaffold_gate_evidence_id(value: CapabilityScaffoldGateEvidence) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"evidence_id"}),
        prefix="capability_scaffold_gate_evidence:",
    )


def capability_scaffold_admission_id(value: CapabilityScaffoldAdmissionArtifact) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"admission_id"}),
        prefix="capability_scaffold_admission:",
    )


def compiled_task_condition_lineage_id(value: CompiledTaskConditionLineage) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"lineage_id"}),
        prefix="compiled_task_condition_lineage:",
    )


def _make_capability_projection(
    *,
    joint_admission: JointCompilationAdmissionArtifact,
    base: RuntimePublicProjection,
    target_capability_id: str,
    scaffold_level: ScaffoldLevel,
    scaffold_policy_version: str,
    state_mapping_contract_id: str,
    dependency_graph_id: str,
    summary_spec: MinimalPublicStateSummarySpec,
    public_nodes: tuple[PublicCapabilityNode, ...],
    public_edges: tuple[tuple[str, str], ...],
) -> CapabilityAwarePublicProjection:
    rank = SCAFFOLD_LEVELS.index(scaffold_level)
    values: dict[str, Any] = {
        "compiled_task_condition_id": "pending",
        "joint_admission_id": joint_admission.admission_id,
        "joint_compilation_id": joint_admission.joint_compilation_id,
        "omega_component_manifest_id": joint_admission.omega_component_manifest_id,
        "dependency_graph_id": dependency_graph_id,
        "runtime_id": base.runtime_id,
        "base_runtime_projection": base,
        "state_mapping_contract_id": state_mapping_contract_id,
        "target_capability_id": target_capability_id,
        "scaffold_level": scaffold_level,
        "scaffold_rank": rank,
        "scaffold_policy_version": scaffold_policy_version,
        "scaffold_payload_hash": "pending",
        "aid_kinds": SCAFFOLD_AIDS_BY_LEVEL[scaffold_level],
        "public_summary_spec": summary_spec if rank >= 1 else None,
        "public_capability_nodes": public_nodes if rank >= 2 else (),
        "public_dependency_edges": public_edges if rank >= 3 else (),
        "schema_version": CAPABILITY_SCAFFOLD_PROJECTION_VERSION,
    }
    payload_provisional = CapabilityAwarePublicProjection.model_construct(
        projection_id="pending", **values
    )
    values["scaffold_payload_hash"] = capability_scaffold_payload_hash(payload_provisional)
    condition_provisional = CapabilityAwarePublicProjection.model_construct(
        projection_id="pending", **values
    )
    values["compiled_task_condition_id"] = compiled_task_condition_id(condition_provisional)
    provisional = CapabilityAwarePublicProjection.model_construct(projection_id="pending", **values)
    return CapabilityAwarePublicProjection(
        projection_id=capability_aware_public_projection_id(provisional),
        **values,
    )


def _public_capability_nodes(
    graph: CapabilityPrerequisiteGraph,
) -> tuple[PublicCapabilityNode, ...]:
    return tuple(
        PublicCapabilityNode(
            node_key=item.node_key,
            capability_id=item.capability_id,
            public_requirement_id=item.public_requirement_id,
            prerequisite_node_keys=item.prerequisite_node_keys,
            observable_input_kinds=item.observable_input_kinds,
            model_decision_kind=item.model_decision_kind,
            allowed_public_effects=item.allowed_public_effects,
        )
        for item in graph.nodes
    )


def _public_dependency_edges(
    graph: CapabilityPrerequisiteGraph,
) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (prerequisite, item.node_key)
            for item in graph.nodes
            for prerequisite in item.prerequisite_node_keys
        )
    )


def _derive_scaffold_gates(
    ladder: CapabilityScaffoldLadderCompilation,
    evidence: Sequence[CapabilityScaffoldGateEvidence],
) -> dict[str, dict[str, bool]]:
    by_key = {(item.scaffold_level, item.gate): item for item in evidence}
    return {
        level: {
            gate: bool(
                (row := by_key.get((level, gate)))
                and row.ladder_id == ladder.ladder_id
                and row.joint_compilation_id == ladder.joint_compilation_id
                and row.projection_id
                == next(
                    item.projection_id
                    for item in ladder.projections
                    if item.scaffold_level == level
                )
                and row.passed
            )
            for gate in SCAFFOLD_GATES
        }
        for level in SCAFFOLD_LEVELS
    }


def _compile_public_summary_values(
    summary_spec: MinimalPublicStateSummarySpec,
    observations: Sequence[PublicStateObservation],
) -> dict[PublicSummaryField, Any]:
    compiled: dict[PublicSummaryField, Any] = {}
    included = set(summary_spec.included_fields)
    for observation in observations:
        for field, value in observation.values.items():
            if field in included:
                compiled[field] = value
    return dict(sorted(compiled.items()))


def _projection_leaks_oracle(
    projection: CapabilityAwarePublicProjection,
    artifacts: CompiledProofCarryingArtifacts,
) -> bool:
    serialized = json.dumps(
        projection.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    )
    public_serialized = json.dumps(
        artifacts.public_artifact.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    )
    joint = artifacts.joint_compilation
    task = joint.omega.task
    secrets = (
        joint.omega.oracle_specification.specification_id,
        joint.omega.evidence_bundle.bundle_id,
        joint.omega.proof_graph.graph_id,
        joint.omega.proof_graph.graph_hash,
        task.oracle.task_program.program_id,
        task.oracle.task_program.program_hash,
        joint.omega.quality_contract.contract_id,
        joint.omega.quality_contract.contract_hash,
        *task.oracle.gold_evidence_ids,
    )
    if any(value and value in serialized and value not in public_serialized for value in secrets):
        return True
    public_values = set(_iter_string_values(artifacts.public_artifact.model_dump(mode="json")))
    return any(
        marker in value.lower() and value not in public_values
        for value in _iter_string_values(projection.model_dump(mode="json"))
        for marker in _FORBIDDEN_PUBLIC_MARKERS
    )


def _iter_string_values(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(item for nested in value.values() for item in _iter_string_values(nested))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(item for nested in value for item in _iter_string_values(nested))
    return ()


def _assert_acyclic(by_key: Mapping[str, CapabilityPrerequisiteNode]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_key: str) -> None:
        if node_key in visiting:
            raise ValueError("capability prerequisite graph contains a cycle")
        if node_key in visited:
            return
        visiting.add(node_key)
        for prerequisite in by_key[node_key].prerequisite_node_keys:
            visit(prerequisite)
        visiting.remove(node_key)
        visited.add(node_key)

    for key in sorted(by_key):
        visit(key)
