from __future__ import annotations

from collections import Counter
from enum import Enum
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.capability_observation import (
    CAPABILITY_FAMILY_ORDER,
    OBSERVATION_DEPTH_ORDER,
    CapabilityFamily,
    EmpiricalBoundaryStatus,
    ObservationDepth,
)
from trusted_synthesis.hashing import canonical_hash

EXECUTABLE_CAPABILITY_DEPTH_VERSION = "executable_capability_depth.v1"
EXECUTABLE_DEPTH_SLOT_IDS: Final = ("slot_01", "slot_02", "slot_03")


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DepthActionKind(str, Enum):
    CONTEXT_SELECT = "context_select"
    NORMALIZE_REFERENCE = "normalize_reference"
    CONSUME_NORMALIZED_REFERENCE = "consume_normalized_reference"
    TRIGGER_TYPED_FAILURE = "trigger_typed_failure"
    REVISE_AFTER_FAILURE = "revise_after_failure"
    ADVANCE_CHECKPOINT = "advance_checkpoint"
    VERIFY_COMPLETION = "verify_completion"
    STOP_AFTER_COMPLETION = "stop_after_completion"
    INERT_ADVANCE = "inert_advance"
    TARGET_BYPASS = "target_bypass"
    TEMPTING_CONTINUATION = "tempting_continuation"


class DepthTransitionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    TYPED_FAILURE = "typed_failure"
    REJECTED = "rejected"


class MechanismCounterfactualKind(str, Enum):
    DELETE_TARGET_ACTION = "delete_target_action"
    BYPASS_TARGET_ACTION = "bypass_target_action"


TARGET_LOAD_DIMENSIONS: dict[CapabilityFamily, tuple[str, ...]] = {
    CapabilityFamily.CONTEXT_CONDITIONED_ACTION: (
        "candidate_ambiguity",
        "context_dependency_edges",
        "delayed_public_updates",
        "irreversible_choices",
        "model_owned_decision_states",
    ),
    CapabilityFamily.SEMANTIC_RECONCILIATION: (
        "downstream_consumption_edges",
        "nonidentity_axes",
        "normalization_states",
        "normalized_reference_consumptions",
        "raw_bypass_candidates",
    ),
    CapabilityFamily.FAILURE_RECOVERY: (
        "failure_type_diversity",
        "recovery_branching",
        "recovery_dependency_depth",
        "recovery_successes",
        "typed_failures",
    ),
    CapabilityFamily.STATE_DEPENDENT_STOPPING: (
        "completion_predicates",
        "delayed_readiness_states",
        "near_terminal_checkpoints",
        "tempting_continuations",
        "verification_stop_separations",
    ),
}

DEPTH_VERIFIER_CHECKS: Final = (
    "answer_ready_only_after_reference_path",
    "candidate_sets_exact",
    "event_multiplicities_exact",
    "normalization_references_consumed",
    "reference_path_complete",
    "state_transitions_exact",
    "target_decisions_model_owned",
    "typed_failures_recovered",
    "verified_stop_has_no_later_action",
)


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class ExecutableDepthCandidate(FrozenModel):
    candidate_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    slot_id: str = Field(min_length=1)
    presentation_index: int = Field(ge=0)
    action_kind: DepthActionKind
    semantic_role: str = Field(min_length=1)
    model_owned: Literal[True] = True
    target_capability_action: bool
    reference_action: bool
    visible: Literal[True] = True
    nonidentity_axes: tuple[str, ...] = ()
    failure_type: str | None = None
    schema_version: str = EXECUTABLE_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_candidate(self) -> ExecutableDepthCandidate:
        if self.slot_id not in EXECUTABLE_DEPTH_SLOT_IDS:
            raise ValueError("executable depth Candidate uses an unknown slot")
        if self.nonidentity_axes != tuple(sorted(set(self.nonidentity_axes))):
            raise ValueError("executable depth Candidate axes are not canonical")
        if self.action_kind == DepthActionKind.TRIGGER_TYPED_FAILURE:
            if not self.failure_type:
                raise ValueError("typed-failure Candidate lacks a failure type")
        elif self.failure_type is not None:
            raise ValueError("nonfailure Candidate carries a failure type")
        if self.candidate_id != _identity(
            self,
            "candidate_id",
            "executable_capability_depth_candidate:",
        ):
            raise ValueError("executable depth Candidate identity is invalid")
        return self


class ExecutableDepthState(FrozenModel):
    state_id: str = Field(min_length=1)
    slot_id: str = Field(min_length=1)
    state_index: int = Field(ge=0)
    phase: str = Field(min_length=1)
    public_state: dict[str, Any] = Field(min_length=1)
    candidate_ids: tuple[str, ...] = ()
    reference_candidate_id: str | None = None
    terminal: bool = False
    answer_ready: bool = False
    schema_version: str = EXECUTABLE_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_state(self) -> ExecutableDepthState:
        if self.slot_id not in (*EXECUTABLE_DEPTH_SLOT_IDS, "terminal"):
            raise ValueError("executable depth State uses an unknown slot")
        if self.candidate_ids != tuple(sorted(set(self.candidate_ids))):
            raise ValueError("executable depth State Candidates are not canonical")
        if self.terminal:
            if (
                self.candidate_ids
                or self.reference_candidate_id is not None
                or not self.answer_ready
            ):
                raise ValueError("terminal executable depth State is malformed")
        elif not self.candidate_ids or self.reference_candidate_id not in self.candidate_ids:
            raise ValueError("nonterminal executable depth State lacks one reference Candidate")
        identity_payload = self.model_dump(
            mode="json",
            exclude={"state_id", "candidate_ids", "reference_candidate_id"},
        )
        if self.state_id != canonical_hash(
            identity_payload,
            prefix="executable_capability_depth_state:",
        ):
            raise ValueError("executable depth State identity is invalid")
        return self


class ExecutableDepthTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    from_state_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    to_state_id: str = Field(min_length=1)
    status: DepthTransitionStatus
    failure_code: str | None = None
    emitted_event_types: tuple[str, ...] = ()
    emitted_reference_ids: tuple[str, ...] = ()
    consumed_reference_ids: tuple[str, ...] = ()
    public_update_delayed: bool = False
    schema_version: str = EXECUTABLE_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ExecutableDepthTransition:
        for values in (
            self.emitted_event_types,
            self.emitted_reference_ids,
            self.consumed_reference_ids,
        ):
            if values != tuple(sorted(set(values))):
                raise ValueError("executable depth Transition payload is not canonical")
        if self.status == DepthTransitionStatus.TYPED_FAILURE:
            if not self.failure_code:
                raise ValueError("typed-failure Transition lacks a failure code")
        elif self.failure_code is not None:
            raise ValueError("nonfailure Transition carries a failure code")
        if self.transition_id != _identity(
            self,
            "transition_id",
            "executable_capability_depth_transition:",
        ):
            raise ValueError("executable depth Transition identity is invalid")
        return self


class ExecutableCapabilityDepthGraph(FrozenModel):
    graph_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    base_operational_task_package_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    initial_state_id: str = Field(min_length=1)
    success_terminal_state_id: str = Field(min_length=1)
    maximum_slot_ids: tuple[str, ...] = EXECUTABLE_DEPTH_SLOT_IDS
    active_slot_ids: tuple[str, ...] = Field(min_length=1, max_length=3)
    states: tuple[ExecutableDepthState, ...] = Field(min_length=4)
    candidates: tuple[ExecutableDepthCandidate, ...] = Field(min_length=3)
    transitions: tuple[ExecutableDepthTransition, ...] = Field(min_length=3)
    required_event_multiplicities: dict[str, int] = Field(min_length=1)
    fixed_maximum_skeleton: Literal[True] = True
    model_selects_every_nonterminal_action: Literal[True] = True
    schema_version: str = EXECUTABLE_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_graph(self) -> ExecutableCapabilityDepthGraph:
        if self.maximum_slot_ids != EXECUTABLE_DEPTH_SLOT_IDS:
            raise ValueError("executable depth maximum skeleton changed")
        if self.active_slot_ids != tuple(sorted(set(self.active_slot_ids))):
            raise ValueError("executable depth active slots are not canonical")
        if not set(self.active_slot_ids) <= set(EXECUTABLE_DEPTH_SLOT_IDS):
            raise ValueError("executable depth graph activates an unknown slot")
        states = {item.state_id: item for item in self.states}
        candidates = {item.candidate_id: item for item in self.candidates}
        transitions = {item.candidate_id: item for item in self.transitions}
        if len(states) != len(self.states) or len(candidates) != len(self.candidates):
            raise ValueError("executable depth graph repeats State or Candidate identity")
        if len(transitions) != len(self.transitions) or set(transitions) != set(candidates):
            raise ValueError("executable depth graph does not bind one Transition per Candidate")
        if self.initial_state_id not in states or self.success_terminal_state_id not in states:
            raise ValueError("executable depth graph endpoint is absent")
        if not states[self.success_terminal_state_id].terminal:
            raise ValueError("executable depth success endpoint is not terminal")
        for state in self.states:
            if set(state.candidate_ids) != {
                item.candidate_id for item in self.candidates if item.state_id == state.state_id
            }:
                raise ValueError("executable depth State Candidate set is not exact")
        for candidate in self.candidates:
            transition = transitions[candidate.candidate_id]
            if transition.from_state_id != candidate.state_id:
                raise ValueError("executable depth Candidate Transition starts elsewhere")
            if transition.to_state_id not in states:
                raise ValueError("executable depth Transition targets an absent State")
        if any(value <= 0 for value in self.required_event_multiplicities.values()):
            raise ValueError("executable depth event multiplicity is not positive")
        visited: set[str] = set()
        state_id = self.initial_state_id
        while state_id != self.success_terminal_state_id:
            if state_id in visited:
                raise ValueError("executable depth reference path contains a cycle")
            visited.add(state_id)
            state = states[state_id]
            if state.reference_candidate_id is None:
                raise ValueError("executable depth reference path stops before terminal")
            state_id = transitions[state.reference_candidate_id].to_state_id
        if self.graph_id != _identity(
            self,
            "graph_id",
            "executable_capability_depth_graph:",
        ):
            raise ValueError("executable capability depth graph identity is invalid")
        return self


class CapabilityDepthWitnessContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    required_event_multiplicities: dict[str, int] = Field(min_length=1)
    all_emitted_normalized_references_must_be_consumed: Literal[True] = True
    every_nonterminal_state_requires_model_action: Literal[True] = True
    typed_failure_requires_later_recovery: Literal[True] = True
    verified_stop_forbids_later_action: Literal[True] = True
    schema_version: str = EXECUTABLE_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> CapabilityDepthWitnessContract:
        if any(value <= 0 for value in self.required_event_multiplicities.values()):
            raise ValueError("depth Witness Contract has invalid event multiplicity")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "capability_depth_witness_contract:",
        ):
            raise ValueError("depth Witness Contract identity is invalid")
        return self


class CapabilityDepthVerifierContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    witness_contract_id: str = Field(min_length=1)
    required_checks: tuple[str, ...] = DEPTH_VERIFIER_CHECKS
    counterfactual_kinds: tuple[MechanismCounterfactualKind, ...] = tuple(
        MechanismCounterfactualKind
    )
    target_matched_counterfactual_required: Literal[True] = True
    task_answer_and_mechanism_both_required: Literal[True] = True
    schema_version: str = EXECUTABLE_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> CapabilityDepthVerifierContract:
        if self.required_checks != DEPTH_VERIFIER_CHECKS:
            raise ValueError("depth Verifier check vector changed")
        if self.counterfactual_kinds != tuple(MechanismCounterfactualKind):
            raise ValueError("depth Verifier counterfactual language changed")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "capability_depth_verifier_contract:",
        ):
            raise ValueError("depth Verifier Contract identity is invalid")
        return self


class DepthRuntimeObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    call_index: int = Field(ge=1)
    state_id: str = Field(min_length=1)
    visible_candidate_ids: tuple[str, ...] = Field(min_length=1)
    chosen_candidate_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    next_state_id: str = Field(min_length=1)
    status: DepthTransitionStatus
    failure_code: str | None = None
    emitted_event_types: tuple[str, ...] = ()
    emitted_reference_ids: tuple[str, ...] = ()
    consumed_reference_ids: tuple[str, ...] = ()
    schema_version: str = EXECUTABLE_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> DepthRuntimeObservation:
        if self.visible_candidate_ids != tuple(sorted(set(self.visible_candidate_ids))):
            raise ValueError("Runtime Observation Candidate set is not canonical")
        if self.chosen_candidate_id not in self.visible_candidate_ids:
            raise ValueError("Runtime selected a nonvisible depth Candidate")
        if self.status == DepthTransitionStatus.TYPED_FAILURE:
            if not self.failure_code:
                raise ValueError("Runtime typed failure lacks a code")
        elif self.failure_code is not None:
            raise ValueError("Runtime nonfailure carries a failure code")
        if self.observation_id != _identity(
            self,
            "observation_id",
            "capability_depth_runtime_observation:",
        ):
            raise ValueError("depth Runtime Observation identity is invalid")
        return self


class ExecutableCapabilityDepthWitness(FrozenModel):
    witness_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    witness_contract_id: str = Field(min_length=1)
    verifier_contract_id: str = Field(min_length=1)
    observations: tuple[DepthRuntimeObservation, ...] = Field(min_length=1)
    reached_state_ids: tuple[str, ...] = Field(min_length=2)
    event_multiplicities: dict[str, int] = Field(min_length=1)
    emitted_reference_ids: tuple[str, ...] = ()
    consumed_reference_ids: tuple[str, ...] = ()
    final_state_id: str = Field(min_length=1)
    checks: dict[str, bool] = Field(min_length=len(DEPTH_VERIFIER_CHECKS))
    full_validity_passed: Literal[True] = True
    mechanism_verifier_invoked: Literal[True] = True
    model_behavior_measured: Literal[False] = False
    schema_version: str = EXECUTABLE_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_witness(self) -> ExecutableCapabilityDepthWitness:
        if tuple(item.call_index for item in self.observations) != tuple(
            range(1, len(self.observations) + 1)
        ):
            raise ValueError("depth Witness call indices are not contiguous")
        observed = Counter(
            event for observation in self.observations for event in observation.emitted_event_types
        )
        if dict(sorted(observed.items())) != self.event_multiplicities:
            raise ValueError("depth Witness event multiplicities are not computed from Runtime")
        if set(self.checks) != set(DEPTH_VERIFIER_CHECKS) or not all(self.checks.values()):
            raise ValueError("depth Witness does not pass the complete Verifier")
        if self.witness_id != _identity(
            self,
            "witness_id",
            "executable_capability_depth_witness:",
        ):
            raise ValueError("executable depth Witness identity is invalid")
        return self


class CompiledTargetLoad(FrozenModel):
    load_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    witness_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    dimensions: dict[str, int]
    total: int = Field(gt=0)
    computed_from_runtime_graph: Literal[True] = True
    declared_load_used_as_measurement: Literal[False] = False
    schema_version: str = EXECUTABLE_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_load(self) -> CompiledTargetLoad:
        if set(self.dimensions) != set(TARGET_LOAD_DIMENSIONS[self.capability_family]):
            raise ValueError("compiled target load has the wrong dimensions")
        if any(value < 0 for value in self.dimensions.values()) or self.total != sum(
            self.dimensions.values()
        ):
            raise ValueError("compiled target load is inconsistent")
        if self.load_id != _identity(
            self,
            "load_id",
            "compiled_capability_target_load:",
        ):
            raise ValueError("compiled target load identity is invalid")
        return self


class CompiledNuisanceMeasurement(FrozenModel):
    measurement_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    base_operational_task_package_id: str = Field(min_length=1)
    evidence_count: int = Field(ge=1)
    program_node_count: int = Field(ge=1)
    program_edge_count: int = Field(ge=0)
    tool_count: int = Field(ge=1)
    non_target_candidate_count: int = Field(ge=0)
    verification_obligation_count: int = Field(ge=1)
    prompt_bytes: int = Field(ge=1)
    base_reference_call_count: int = Field(ge=1)
    resource_token_ceiling: int = Field(ge=1)
    unrelated_recovery_burden: Literal[0] = 0
    unrelated_retrieval_branching: Literal[0] = 0
    computed_from_bound_objects: Literal[True] = True
    schema_version: str = EXECUTABLE_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_measurement(self) -> CompiledNuisanceMeasurement:
        if self.measurement_id != _identity(
            self,
            "measurement_id",
            "compiled_capability_nuisance_measurement:",
        ):
            raise ValueError("compiled nuisance measurement identity is invalid")
        return self


class DepthPromptBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    semantic_payload_hash: str = Field(min_length=1)
    rendered_prompt_hash: str = Field(min_length=1)
    rendered_prompt_bytes: int = Field(ge=1)
    padding_bytes: int = Field(ge=0)
    fixed_generation_condition_id: str = Field(min_length=1)
    target_capability_candidate_hash: str = Field(min_length=1)
    condition_changed_candidate_set: Literal[False] = False
    runner_consumption_preflighted: Literal[False] = False
    schema_version: str = EXECUTABLE_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> DepthPromptBinding:
        if self.binding_id != _identity(
            self,
            "binding_id",
            "capability_depth_prompt_binding:",
        ):
            raise ValueError("depth Prompt binding identity is invalid")
        return self


class ExecutableDepthSignature(FrozenModel):
    signature_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    base_operational_record_id: str = Field(min_length=1)
    variant_operational_witness_id: str = Field(min_length=1)
    variant_program_verification_hash: str = Field(min_length=1)
    depth_witness_id: str = Field(min_length=1)
    witness_contract_id: str = Field(min_length=1)
    verifier_contract_id: str = Field(min_length=1)
    target_load_id: str = Field(min_length=1)
    nuisance_measurement_id: str = Field(min_length=1)
    prompt_binding_id: str = Field(min_length=1)
    public_state_graph_hash: str = Field(min_length=1)
    candidate_set_hash: str = Field(min_length=1)
    transition_hash: str = Field(min_length=1)
    operational_witness_full_validity_passed: Literal[True] = True
    depth_witness_full_validity_passed: Literal[True] = True
    target_matched_necessity_passed: Literal[True] = True
    model_behavior_measured: Literal[False] = False
    runner_consumption_preflighted: Literal[False] = False
    schema_version: str = EXECUTABLE_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_signature(self) -> ExecutableDepthSignature:
        if self.signature_id != _identity(
            self,
            "signature_id",
            "executable_capability_depth_signature:",
        ):
            raise ValueError("executable depth Signature identity is invalid")
        return self


class ObservabilityFloorNuisanceEnvelope(FrozenModel):
    contract_id: str = Field(min_length=1)
    maximum_evidence_count: Literal[2] = 2
    maximum_program_node_count: Literal[1] = 1
    maximum_program_edge_count: Literal[0] = 0
    maximum_tool_count: int = Field(ge=1)
    maximum_non_target_candidate_count: int = Field(ge=0)
    maximum_verification_obligation_count: int = Field(ge=1)
    maximum_prompt_bytes: int = Field(ge=1)
    maximum_base_reference_call_count: int = Field(ge=1)
    resource_token_ceiling: int = Field(ge=1)
    development_source_tiers: tuple[str, ...] = ("easy_control",)
    unrelated_recovery_burden_allowed: Literal[False] = False
    unrelated_retrieval_branching_allowed: Literal[False] = False
    schema_version: str = EXECUTABLE_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ObservabilityFloorNuisanceEnvelope:
        if self.development_source_tiers != ("easy_control",):
            raise ValueError("D0 nuisance envelope admits a non-Easy Development source")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "observability_floor_nuisance_envelope:",
        ):
            raise ValueError("D0 nuisance envelope identity is invalid")
        return self


class BoundarySelectionAlgorithmContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    development_threshold: Literal[2] = 2
    development_denominator: Literal[6] = 6
    confirmation_threshold: Literal[3] = 3
    confirmation_denominator: Literal[8] = 8
    development_group_count: Literal[2] = 2
    depth_order: tuple[ObservationDepth, ...] = OBSERVATION_DEPTH_ORDER
    nonincreasing_support_required: Literal[True] = True
    disagreement_is_confounded: Literal[True] = True
    multiple_brackets_are_confounded: Literal[True] = True
    equality_meets_threshold: Literal[True] = True
    total_boolean_development_patterns: Literal[256] = 256
    schema_version: str = EXECUTABLE_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> BoundarySelectionAlgorithmContract:
        if self.depth_order != OBSERVATION_DEPTH_ORDER:
            raise ValueError("Boundary Selection depth order changed")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "capability_boundary_selection_algorithm_contract:",
        ):
            raise ValueError("Boundary Selection Algorithm identity is invalid")
        return self


class CapabilityDepthRuntime:
    def __init__(self, graph: ExecutableCapabilityDepthGraph) -> None:
        self.graph = graph
        self._states = {item.state_id: item for item in graph.states}
        self._candidates = {item.candidate_id: item for item in graph.candidates}
        self._transitions = {item.candidate_id: item for item in graph.transitions}
        self.state_id = graph.initial_state_id
        self.observations: list[DepthRuntimeObservation] = []

    @property
    def state(self) -> ExecutableDepthState:
        return self._states[self.state_id]

    @property
    def visible_candidates(self) -> tuple[ExecutableDepthCandidate, ...]:
        return tuple(self._candidates[item] for item in self.state.candidate_ids)

    def execute(self, candidate_id: str) -> DepthRuntimeObservation:
        state = self.state
        if state.terminal:
            raise ValueError("depth Runtime forbids actions after terminal completion")
        if candidate_id not in state.candidate_ids:
            raise ValueError("depth Runtime rejected a nonvisible Candidate")
        transition = self._transitions[candidate_id]
        values = {
            "call_index": len(self.observations) + 1,
            "state_id": state.state_id,
            "visible_candidate_ids": state.candidate_ids,
            "chosen_candidate_id": candidate_id,
            "transition_id": transition.transition_id,
            "next_state_id": transition.to_state_id,
            "status": transition.status,
            "failure_code": transition.failure_code,
            "emitted_event_types": transition.emitted_event_types,
            "emitted_reference_ids": transition.emitted_reference_ids,
            "consumed_reference_ids": transition.consumed_reference_ids,
        }
        provisional = DepthRuntimeObservation.model_construct(
            observation_id="pending",
            **values,
        )
        observation = DepthRuntimeObservation(
            observation_id=_identity(
                provisional,
                "observation_id",
                "capability_depth_runtime_observation:",
            ),
            **values,
        )
        self.observations.append(observation)
        self.state_id = transition.to_state_id
        return observation


def classify_capability_boundary(
    counts_by_group: tuple[tuple[int, int, int, int], tuple[int, int, int, int]],
    *,
    threshold: Literal[2, 3],
    denominator: Literal[6, 8],
) -> tuple[EmpiricalBoundaryStatus, tuple[ObservationDepth, ObservationDepth] | None]:
    if (threshold, denominator) not in ((2, 6), (3, 8)):
        raise ValueError("Capability Boundary threshold and denominator are not registered")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > denominator
        for row in counts_by_group
        for value in row
    ):
        raise ValueError("Capability Boundary count is outside its frozen denominator")
    supported = tuple(tuple(value >= threshold for value in row) for row in counts_by_group)
    if any(any(not row[index] and row[index + 1] for index in range(3)) for row in supported):
        return EmpiricalBoundaryStatus.NONMONOTONIC_OR_CONFOUNDED, None
    if all(not row[0] for row in supported):
        return EmpiricalBoundaryStatus.BELOW_OBSERVATION_FLOOR, None
    if all(row[-1] for row in supported):
        return EmpiricalBoundaryStatus.ABOVE_OBSERVATION_CEILING, None
    if any(supported[0][index] != supported[1][index] for index in range(4)):
        return EmpiricalBoundaryStatus.NONMONOTONIC_OR_CONFOUNDED, None
    brackets = tuple(
        index
        for index in range(3)
        if all(row[index] and not row[index + 1] for row in supported)
        and all(not row[later] for row in supported for later in range(index + 1, 4))
    )
    if len(brackets) != 1:
        return EmpiricalBoundaryStatus.NONMONOTONIC_OR_CONFOUNDED, None
    index = brackets[0]
    return (
        EmpiricalBoundaryStatus.BOUNDARY_BRACKETED,
        (OBSERVATION_DEPTH_ORDER[index], OBSERVATION_DEPTH_ORDER[index + 1]),
    )


def validate_capability_family_order(values: tuple[CapabilityFamily, ...]) -> None:
    if values != CAPABILITY_FAMILY_ORDER:
        raise ValueError("executable capability breadth changed")
