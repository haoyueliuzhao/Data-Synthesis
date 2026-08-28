from __future__ import annotations

import json
import re
from collections import Counter
from enum import Enum
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.capability_observation import CapabilityFamily, ObservationDepth
from trusted_synthesis.hashing import canonical_hash

CAUSAL_CAPABILITY_DEPTH_VERSION = "causal_capability_depth.v2"
PUBLIC_ACTION_ID_LENGTH: Final = 24
PUBLIC_STATE_TOKEN_LENGTH: Final = 24
PUBLIC_CANDIDATE_DESCRIPTION: Final = "Apply the displayed operation payload."

HOST_ONLY_PUBLIC_KEYS: Final = (
    "capability_family",
    "depth",
    "expected_transition_status",
    "future_state_graph",
    "reference_action",
    "reference_candidate_id",
    "required_event_multiplicities",
    "success_reference_path",
    "success_terminal_state_id",
    "target_capability_action",
)
FORBIDDEN_PUBLIC_SCALAR_FRAGMENTS: Final = (
    "alternate_operation",
    "avoid_failure",
    "bypass",
    "correct_action",
    "d0_observability_anchor",
    "d1_basic",
    "d2_compositional",
    "d3_stress",
    "failure_recovery",
    "invalid_retry",
    "normalization_route_",
    "operand_route_",
    "postverification_operation_",
    "public_operand_",
    "public_projection_",
    "query_input_",
    "readiness_probe_",
    "recheck_partial",
    "reference_action",
    "semantic_reconciliation",
    "selector_route_",
    "skip_normalized",
    "state_dependent_stopping",
    "target_capability",
    "tempting_continuation",
    "verify_partial",
    "verify_unbound",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CausalActionKind(str, Enum):
    SELECT_OPERATOR = "select_operator"
    SELECT_INPUT_BINDING = "select_input_binding"
    SELECT_OUTPUT_PROJECTION = "select_output_projection"
    NORMALIZE_OPERAND = "normalize_operand"
    CONSUME_OPERAND = "consume_operand"
    ISSUE_SELECTOR = "issue_selector"
    REVISE_SELECTOR = "revise_selector"
    EXECUTE_PROGRAM = "execute_program"
    CHECK_READINESS = "check_readiness"
    VERIFY_TERMINAL = "verify_terminal"
    STOP = "stop"
    CONTINUE = "continue"
    TERMINATE_INVALID = "terminate_invalid"


class CausalTransitionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    TYPED_FAILURE = "typed_failure"
    REJECTED = "rejected"
    TASK_INVALID = "task_invalid"


class CausalTerminalKind(str, Enum):
    NONE = "none"
    SUCCESS = "success"
    TASK_FAILURE = "task_failure"
    POSTCOMPLETION_VIOLATION = "postcompletion_violation"


class FinanceEffectKind(str, Enum):
    SELECT_OPERATOR = "select_operator"
    SELECT_INPUT_BINDING = "select_input_binding"
    SELECT_PROJECTION = "select_projection"
    PRODUCE_REFERENCE = "produce_reference"
    CONSUME_REFERENCE = "consume_reference"
    RECORD_FAILURE = "record_failure"
    REVISE_SELECTOR = "revise_selector"
    RECORD_READINESS_CHECK = "record_readiness_check"
    COMPLETE_NODE = "complete_node"
    SET_EXPECTED_RESULT = "set_expected_result"
    SET_ALTERNATE_RESULT = "set_alternate_result"
    CLOSE_PROGRAM = "close_program"
    VERIFY_TERMINAL = "verify_terminal"
    STOP = "stop"
    RECORD_POSTCOMPLETION_CALL = "record_postcompletion_call"
    INCREMENT_INVOCATION = "increment_invocation"


class CausalCounterfactualKind(str, Enum):
    REMOVE_TARGET_MECHANISM = "remove_target_mechanism"
    BYPASS_TARGET_MECHANISM = "bypass_target_mechanism"


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def public_argument_shape(value: str) -> tuple[str, ...]:
    namespace, separator, suffix = value.rpartition(":")
    if (
        separator
        and re.fullmatch(r"[a-z][a-z0-9_]*", namespace)
        and re.fullmatch(r"[0-9a-f]{16,64}", suffix)
    ):
        return ("qualified_hex", namespace, str(len(suffix)))
    indexed = re.fullmatch(r"(?P<stem>[a-z][a-z0-9_]*_)(?P<index>[0-9]+)", value)
    if indexed is not None:
        return (
            "indexed_token",
            indexed.group("stem")[:-1],
            str(len(indexed.group("index"))),
        )
    if re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*", value):
        return ("word_sequence", str(len(value.split("_"))))
    raise ValueError("public Candidate argument has no registered lexical shape")


def scan_public_leakage(value: Any, path: str = "$") -> tuple[str, ...]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).casefold()
            if key_text in HOST_ONLY_PUBLIC_KEYS:
                findings.append(f"{path}.{key}:host_only_key")
            findings.extend(scan_public_leakage(item, f"{path}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            findings.extend(scan_public_leakage(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        scalar = value.casefold()
        for fragment in FORBIDDEN_PUBLIC_SCALAR_FRAGMENTS:
            if fragment in scalar:
                findings.append(f"{path}:forbidden_scalar:{fragment}")
    return tuple(sorted(set(findings)))


class PublicArgument(FrozenModel):
    name: str = Field(pattern=r"^arg_[0-9]{2}$")
    value: str = Field(min_length=1)


class PublicExecutableDepthCandidate(FrozenModel):
    action_id: str = Field(
        min_length=PUBLIC_ACTION_ID_LENGTH,
        max_length=PUBLIC_ACTION_ID_LENGTH,
        pattern=rf"^[0-9a-f]{{{PUBLIC_ACTION_ID_LENGTH}}}$",
    )
    presentation_index: int = Field(ge=0)
    tool: str = Field(min_length=1)
    arguments: tuple[PublicArgument, ...] = Field(min_length=1)
    description: Literal["Apply the displayed operation payload."] = PUBLIC_CANDIDATE_DESCRIPTION
    padding: str = ""
    schema_version: str = CAUSAL_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_candidate(self) -> PublicExecutableDepthCandidate:
        if tuple(item.name for item in self.arguments) != tuple(
            f"arg_{index:02d}" for index in range(1, len(self.arguments) + 1)
        ):
            raise ValueError("public Candidate argument positions are not canonical")
        for argument in self.arguments:
            public_argument_shape(argument.value)
        if scan_public_leakage(self.model_dump(mode="json")):
            raise ValueError("public Candidate contains a Host or answer cue")
        return self


class PublicFact(FrozenModel):
    name: str = Field(pattern=r"^fact_[0-9]{2}$")
    value: str = Field(min_length=1)


class PublicExecutableDepthState(FrozenModel):
    state_token: str = Field(
        min_length=PUBLIC_STATE_TOKEN_LENGTH,
        max_length=PUBLIC_STATE_TOKEN_LENGTH,
        pattern=rf"^[0-9a-f]{{{PUBLIC_STATE_TOKEN_LENGTH}}}$",
    )
    step_index: int = Field(ge=0)
    facts: tuple[PublicFact, ...]
    history: tuple[str, ...]
    options: tuple[PublicExecutableDepthCandidate, ...] = ()
    terminal: bool = False
    schema_version: str = CAUSAL_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_state(self) -> PublicExecutableDepthState:
        if tuple(item.name for item in self.facts) != tuple(
            f"fact_{index:02d}" for index in range(1, len(self.facts) + 1)
        ):
            raise ValueError("public State facts are not position-canonical")
        if self.terminal:
            if self.options:
                raise ValueError("terminal public State exposes an action")
        elif len(self.options) < 2:
            raise ValueError("nonterminal public State lacks a real choice")
        if tuple(item.presentation_index for item in self.options) != tuple(
            range(len(self.options))
        ):
            raise ValueError("public Candidate presentation order is not contiguous")
        if len({item.action_id for item in self.options}) != len(self.options):
            raise ValueError("public State repeats an opaque action ID")
        schemas = {
            (item.tool, tuple(argument.name for argument in item.arguments))
            for item in self.options
        }
        if len(schemas) > 1:
            raise ValueError("public Candidate schemas are not isomorphic")
        argument_shapes = {
            tuple(public_argument_shape(argument.value) for argument in item.arguments)
            for item in self.options
        }
        if len(argument_shapes) > 1:
            raise ValueError("public Candidate argument lexical shapes are not isomorphic")
        lengths = {len(canonical_bytes(item.model_dump(mode="json"))) for item in self.options}
        if len(lengths) > 1:
            raise ValueError("public Candidate encodings are not equal length")
        if scan_public_leakage(self.model_dump(mode="json")):
            raise ValueError("public State contains a Host or answer cue")
        return self


class CausalFinanceBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    base_operational_task_package_id: str = Field(min_length=1)
    operational_record_id: str = Field(min_length=1)
    task_program_id: str = Field(min_length=1)
    task_verifier_binding_id: str = Field(min_length=1)
    task_public_hash: str = Field(min_length=1)
    program_hash: str = Field(min_length=1)
    verifier_hash: str = Field(min_length=1)
    evidence_ids: tuple[str, str]
    operation_node_ids: tuple[str, ...] = Field(min_length=1)
    terminal_operation_node_id: str = Field(min_length=1)
    normalization_reference_ids: tuple[str, ...] = ()
    selector_ids: tuple[str, ...] = Field(min_length=1)
    selector_failure_codes: dict[str, str] = Field(min_length=1)
    input_binding_ids: tuple[str, ...] = Field(min_length=1)
    projection_ids: tuple[str, ...] = Field(min_length=1)
    readiness_check_ids: tuple[str, ...] = Field(min_length=1)
    expected_operator_id: str | None = None
    expected_result_hash: str = Field(min_length=1)
    schema_version: str = CAUSAL_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> CausalFinanceBinding:
        if self.operation_node_ids != tuple(dict.fromkeys(self.operation_node_ids)):
            raise ValueError("Finance binding repeats an operation node")
        if self.terminal_operation_node_id not in self.operation_node_ids:
            raise ValueError("Finance binding terminal node is absent")
        if self.normalization_reference_ids != tuple(
            dict.fromkeys(self.normalization_reference_ids)
        ):
            raise ValueError("Finance binding repeats a normalization reference")
        if set(self.selector_failure_codes) != set(self.selector_ids):
            raise ValueError("Finance binding does not type every selector failure")
        if len(set(self.selector_failure_codes.values())) != len(self.selector_ids):
            raise ValueError("Finance binding repeats a selector failure code")
        if self.binding_id != _identity(
            self,
            "binding_id",
            "causal_finance_program_binding:",
        ):
            raise ValueError("causal Finance binding identity is invalid")
        return self


class CausalFinanceSnapshot(FrozenModel):
    snapshot_id: str = Field(min_length=1)
    selected_operator_id: str | None = None
    selected_input_binding_ids: tuple[str, ...] = ()
    selected_projection_ids: tuple[str, ...] = ()
    produced_reference_ids: tuple[str, ...] = ()
    consumed_reference_ids: tuple[str, ...] = ()
    observed_failure_codes: tuple[str, ...] = ()
    revised_selector_ids: tuple[str, ...] = ()
    readiness_check_ids: tuple[str, ...] = ()
    completed_operation_node_ids: tuple[str, ...] = ()
    program_closed: bool = False
    terminal_verified: bool = False
    stopped: bool = False
    postcompletion_violation: bool = False
    result_hash: str | None = None
    invocation_count: int = Field(default=0, ge=0)
    schema_version: str = CAUSAL_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_snapshot(self) -> CausalFinanceSnapshot:
        for values in (
            self.selected_input_binding_ids,
            self.selected_projection_ids,
            self.produced_reference_ids,
            self.consumed_reference_ids,
            self.observed_failure_codes,
            self.revised_selector_ids,
            self.readiness_check_ids,
            self.completed_operation_node_ids,
        ):
            if values != tuple(sorted(set(values))):
                raise ValueError("causal Finance snapshot set is not canonical")
        if not set(self.consumed_reference_ids) <= set(self.produced_reference_ids):
            raise ValueError("Finance snapshot consumes a reference that was never produced")
        if self.terminal_verified and (not self.program_closed or self.result_hash is None):
            raise ValueError("Finance snapshot verifies an open or resultless Program")
        if self.stopped and not self.terminal_verified:
            raise ValueError("Finance snapshot stops before terminal verification")
        if self.postcompletion_violation and not self.terminal_verified:
            raise ValueError("Finance snapshot records a precompletion postcompletion violation")
        if self.snapshot_id != _identity(
            self,
            "snapshot_id",
            "causal_finance_snapshot:",
        ):
            raise ValueError("causal Finance snapshot identity is invalid")
        return self


class FinanceEffect(FrozenModel):
    kind: FinanceEffectKind
    value: str | None = None

    @model_validator(mode="after")
    def validate_effect(self) -> FinanceEffect:
        valueless = {FinanceEffectKind.STOP, FinanceEffectKind.RECORD_POSTCOMPLETION_CALL}
        if (self.kind in valueless) != (self.value is None):
            raise ValueError("Finance effect value shape is invalid")
        return self


class HostExecutableDepthCandidate(FrozenModel):
    candidate_id: str = Field(min_length=1)
    host_state_id: str = Field(min_length=1)
    public_action_id: str = Field(
        min_length=PUBLIC_ACTION_ID_LENGTH,
        max_length=PUBLIC_ACTION_ID_LENGTH,
        pattern=rf"^[0-9a-f]{{{PUBLIC_ACTION_ID_LENGTH}}}$",
    )
    action_kind: CausalActionKind
    reference_action: bool
    target_capability_action: bool
    semantic_choice_hash: str = Field(min_length=1)
    schema_version: str = CAUSAL_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_candidate(self) -> HostExecutableDepthCandidate:
        if self.candidate_id != _identity(
            self,
            "candidate_id",
            "host_causal_depth_candidate:",
        ):
            raise ValueError("Host Candidate identity is invalid")
        return self


class HostExecutableDepthState(FrozenModel):
    state_id: str = Field(min_length=1)
    state_index: int = Field(ge=0)
    host_phase: str = Field(min_length=1)
    public_state: PublicExecutableDepthState
    finance_snapshot: CausalFinanceSnapshot
    candidate_ids: tuple[str, ...] = ()
    reference_candidate_id: str | None = None
    terminal_kind: CausalTerminalKind = CausalTerminalKind.NONE
    schema_version: str = CAUSAL_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_state(self) -> HostExecutableDepthState:
        if self.terminal_kind == CausalTerminalKind.NONE:
            if len(self.candidate_ids) < 2 or self.reference_candidate_id not in self.candidate_ids:
                raise ValueError("Host State lacks a reference-bearing real choice")
            if self.public_state.terminal:
                raise ValueError("nonterminal Host State has a terminal public projection")
        elif self.candidate_ids or self.reference_candidate_id is not None:
            raise ValueError("terminal Host State exposes a Candidate")
        identity_payload = self.model_dump(
            mode="json",
            exclude={"state_id", "candidate_ids", "reference_candidate_id"},
        )
        if self.state_id != canonical_hash(
            identity_payload,
            prefix="host_causal_depth_state:",
        ):
            raise ValueError("Host State identity is invalid")
        return self


class HostExecutableDepthTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    from_state_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    to_state_id: str = Field(min_length=1)
    status: CausalTransitionStatus
    public_observation: str = Field(min_length=1)
    failure_code: str | None = None
    effects: tuple[FinanceEffect, ...] = Field(min_length=1)
    emitted_event_types: tuple[str, ...] = ()
    emitted_reference_ids: tuple[str, ...] = ()
    consumed_reference_ids: tuple[str, ...] = ()
    schema_version: str = CAUSAL_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> HostExecutableDepthTransition:
        for values in (
            self.emitted_event_types,
            self.emitted_reference_ids,
            self.consumed_reference_ids,
        ):
            if values != tuple(sorted(set(values))):
                raise ValueError("Host Transition set payload is not canonical")
        if self.status == CausalTransitionStatus.TYPED_FAILURE:
            if not self.failure_code:
                raise ValueError("typed failure Transition lacks a code")
        elif self.failure_code is not None:
            raise ValueError("nonfailure Transition carries a failure code")
        if self.transition_id != _identity(
            self,
            "transition_id",
            "host_causal_depth_transition:",
        ):
            raise ValueError("Host Transition identity is invalid")
        return self


class HostExecutableDepthGraph(FrozenModel):
    graph_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    predecessor_package_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    base_operational_task_package_id: str = Field(min_length=1)
    finance_binding_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    initial_state_id: str = Field(min_length=1)
    success_terminal_state_id: str = Field(min_length=1)
    states: tuple[HostExecutableDepthState, ...] = Field(min_length=4)
    candidates: tuple[HostExecutableDepthCandidate, ...] = Field(min_length=2)
    transitions: tuple[HostExecutableDepthTransition, ...] = Field(min_length=2)
    required_event_multiplicities: dict[str, int] = Field(min_length=1)
    reference_path_candidate_ids: tuple[str, ...] = Field(min_length=1)
    host_graph_model_visible: Literal[False] = False
    every_nonterminal_state_branches: Literal[True] = True
    schema_version: str = CAUSAL_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_graph(self) -> HostExecutableDepthGraph:
        states = {item.state_id: item for item in self.states}
        candidates = {item.candidate_id: item for item in self.candidates}
        transitions = {item.candidate_id: item for item in self.transitions}
        if len(states) != len(self.states) or len(candidates) != len(self.candidates):
            raise ValueError("Host Graph repeats State or Candidate identity")
        if len(transitions) != len(self.transitions) or set(transitions) != set(candidates):
            raise ValueError("Host Graph lacks one Transition per Candidate")
        if self.initial_state_id not in states or self.success_terminal_state_id not in states:
            raise ValueError("Host Graph endpoint is absent")
        if states[self.success_terminal_state_id].terminal_kind != CausalTerminalKind.SUCCESS:
            raise ValueError("Host Graph success endpoint is not a success terminal")
        for state in self.states:
            expected = {
                item.candidate_id
                for item in self.candidates
                if item.host_state_id == state.state_id
            }
            if set(state.candidate_ids) != expected:
                raise ValueError("Host State Candidate set is not exact")
            public_ids = {
                item.public_action_id
                for item in self.candidates
                if item.host_state_id == state.state_id
            }
            if public_ids != {item.action_id for item in state.public_state.options}:
                raise ValueError("Host/Public Candidate projection is inconsistent")
            if state.terminal_kind == CausalTerminalKind.NONE:
                destinations = {transitions[item].to_state_id for item in state.candidate_ids}
                if len(destinations) < 2:
                    raise ValueError("Host State Candidates do not produce distinct consequences")
        for candidate in self.candidates:
            transition = transitions[candidate.candidate_id]
            if transition.from_state_id != candidate.host_state_id:
                raise ValueError("Host Candidate Transition starts in another State")
            if transition.to_state_id not in states:
                raise ValueError("Host Transition targets an absent State")
        if any(value <= 0 for value in self.required_event_multiplicities.values()):
            raise ValueError("Host Graph event multiplicity is invalid")
        visited: set[str] = set()
        state_id = self.initial_state_id
        path: list[str] = []
        while state_id != self.success_terminal_state_id:
            if state_id in visited:
                raise ValueError("Host Graph reference path contains a cycle")
            visited.add(state_id)
            candidate_id = states[state_id].reference_candidate_id
            if candidate_id is None:
                raise ValueError("Host Graph reference path ends early")
            path.append(candidate_id)
            state_id = transitions[candidate_id].to_state_id
        if tuple(path) != self.reference_path_candidate_ids:
            raise ValueError("Host Graph reference path binding is inconsistent")
        if any(
            scan_public_leakage(item.public_state.model_dump(mode="json")) for item in self.states
        ):
            raise ValueError("Host Graph contains a leaking Public projection")
        if self.graph_id != _identity(self, "graph_id", "host_causal_depth_graph:"):
            raise ValueError("Host causal Graph identity is invalid")
        return self


class CausalDepthWitnessContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    finance_binding_id: str = Field(min_length=1)
    capability_family: CapabilityFamily
    depth: ObservationDepth
    required_event_multiplicities: dict[str, int] = Field(min_length=1)
    task_program_and_mechanism_jointly_verified: Literal[True] = True
    schema_version: str = CAUSAL_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> CausalDepthWitnessContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "causal_depth_witness_contract:",
        ):
            raise ValueError("causal Witness Contract identity is invalid")
        return self


class CausalDepthVerifierContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    witness_contract_id: str = Field(min_length=1)
    finance_binding_id: str = Field(min_length=1)
    task_program_id: str = Field(min_length=1)
    task_verifier_binding_id: str = Field(min_length=1)
    task_verifier_required: Literal[True] = True
    mechanism_verifier_required: Literal[True] = True
    counterfactual_kinds: tuple[CausalCounterfactualKind, ...] = tuple(CausalCounterfactualKind)
    schema_version: str = CAUSAL_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> CausalDepthVerifierContract:
        if self.counterfactual_kinds != tuple(CausalCounterfactualKind):
            raise ValueError("causal Counterfactual language changed")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "causal_depth_verifier_contract:",
        ):
            raise ValueError("causal Verifier Contract identity is invalid")
        return self


class CausalRuntimeObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    call_index: int = Field(ge=1)
    from_state_id: str = Field(min_length=1)
    public_state_token: str = Field(min_length=PUBLIC_STATE_TOKEN_LENGTH)
    visible_action_ids: tuple[str, ...] = Field(min_length=2)
    chosen_public_action_id: str = Field(min_length=PUBLIC_ACTION_ID_LENGTH)
    host_candidate_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    to_state_id: str = Field(min_length=1)
    status: CausalTransitionStatus
    public_observation: str = Field(min_length=1)
    failure_code: str | None = None
    before_snapshot_id: str = Field(min_length=1)
    after_snapshot_id: str = Field(min_length=1)
    emitted_event_types: tuple[str, ...] = ()
    emitted_reference_ids: tuple[str, ...] = ()
    consumed_reference_ids: tuple[str, ...] = ()
    schema_version: str = CAUSAL_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> CausalRuntimeObservation:
        if self.chosen_public_action_id not in self.visible_action_ids:
            raise ValueError("causal Runtime selected a nonvisible action")
        if self.status == CausalTransitionStatus.TYPED_FAILURE:
            if not self.failure_code:
                raise ValueError("typed failure Observation lacks a code")
        elif self.failure_code is not None:
            raise ValueError("nonfailure Observation carries a failure code")
        if self.observation_id != _identity(
            self,
            "observation_id",
            "causal_depth_runtime_observation:",
        ):
            raise ValueError("causal Runtime Observation identity is invalid")
        return self


class CausalTaskValidityReport(FrozenModel):
    report_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    finance_binding_id: str = Field(min_length=1)
    trace_hash: str = Field(min_length=1)
    task_program_id: str = Field(min_length=1)
    task_verifier_binding_id: str = Field(min_length=1)
    task_verifier_invoked: Literal[True] = True
    independent_program_replay_passed: bool
    operation_lineage_complete: bool
    finance_operand_binding_passed: bool
    expected_result_match: bool
    program_closed: bool
    terminal_verified: bool
    postcompletion_control_passed: bool
    base_valid: bool
    schema_version: str = CAUSAL_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> CausalTaskValidityReport:
        expected = all(
            (
                self.independent_program_replay_passed,
                self.operation_lineage_complete,
                self.finance_operand_binding_passed,
                self.expected_result_match,
                self.program_closed,
                self.terminal_verified,
                self.postcompletion_control_passed,
            )
        )
        if self.base_valid != expected:
            raise ValueError("causal Base validity is not computed from task checks")
        if self.report_id != _identity(
            self,
            "report_id",
            "causal_task_validity_report:",
        ):
            raise ValueError("causal task validity identity is invalid")
        return self


class CausalMechanismValidityReport(FrozenModel):
    report_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    trace_hash: str = Field(min_length=1)
    mechanism_verifier_invoked: Literal[True] = True
    expected_event_multiplicities: dict[str, int] = Field(min_length=1)
    observed_event_multiplicities: dict[str, int]
    reference_preconditions_respected: bool
    produced_before_consumed: bool
    recovery_after_matching_failure: bool
    stop_after_verification: bool
    mechanism_qualified: bool
    schema_version: str = CAUSAL_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> CausalMechanismValidityReport:
        expected = all(
            (
                self.expected_event_multiplicities == self.observed_event_multiplicities,
                self.reference_preconditions_respected,
                self.produced_before_consumed,
                self.recovery_after_matching_failure,
                self.stop_after_verification,
            )
        )
        if self.mechanism_qualified != expected:
            raise ValueError("causal mechanism validity is not computed from trace checks")
        if self.report_id != _identity(
            self,
            "report_id",
            "causal_mechanism_validity_report:",
        ):
            raise ValueError("causal mechanism validity identity is invalid")
        return self


class CausalQualifiedValidityReport(FrozenModel):
    report_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    task_report_id: str = Field(min_length=1)
    mechanism_report_id: str = Field(min_length=1)
    base_valid: bool
    mechanism_qualified: bool
    qualified_valid: bool
    schema_version: str = CAUSAL_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> CausalQualifiedValidityReport:
        if self.qualified_valid != (self.base_valid and self.mechanism_qualified):
            raise ValueError("causal Qualified validity conjunction is invalid")
        if self.report_id != _identity(
            self,
            "report_id",
            "causal_qualified_validity_report:",
        ):
            raise ValueError("causal Qualified validity identity is invalid")
        return self


class CausalDepthWitness(FrozenModel):
    witness_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    witness_contract_id: str = Field(min_length=1)
    verifier_contract_id: str = Field(min_length=1)
    observations: tuple[CausalRuntimeObservation, ...] = Field(min_length=1)
    final_state_id: str = Field(min_length=1)
    final_snapshot_id: str = Field(min_length=1)
    task_validity: CausalTaskValidityReport
    mechanism_validity: CausalMechanismValidityReport
    qualified_validity: CausalQualifiedValidityReport
    model_behavior_measured: Literal[False] = False
    schema_version: str = CAUSAL_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_witness(self) -> CausalDepthWitness:
        if tuple(item.call_index for item in self.observations) != tuple(
            range(1, len(self.observations) + 1)
        ):
            raise ValueError("causal Witness call indices are not contiguous")
        trace_hash = canonical_hash(
            tuple(item.observation_id for item in self.observations),
            prefix="causal_depth_trace:",
        )
        if (
            self.task_validity.trace_hash != trace_hash
            or self.mechanism_validity.trace_hash != trace_hash
            or self.qualified_validity.task_report_id != self.task_validity.report_id
            or self.qualified_validity.mechanism_report_id != self.mechanism_validity.report_id
            or not self.qualified_validity.qualified_valid
        ):
            raise ValueError("causal Witness validity parents are inconsistent")
        if self.witness_id != _identity(
            self,
            "witness_id",
            "causal_depth_witness:",
        ):
            raise ValueError("causal Witness identity is invalid")
        return self


class DepthPromptProjectionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    model_visible_top_level_keys: tuple[str, str] = ("state", "task")
    host_only_field_names: tuple[str, ...] = HOST_ONLY_PUBLIC_KEYS
    forbidden_scalar_fragments: tuple[str, ...] = FORBIDDEN_PUBLIC_SCALAR_FRAGMENTS
    current_state_only: Literal[True] = True
    future_graph_model_visible: Literal[False] = False
    reference_path_model_visible: Literal[False] = False
    required_events_model_visible: Literal[False] = False
    candidate_ids_opaque_and_equal_length: Literal[True] = True
    candidate_encodings_equal_length_per_state: Literal[True] = True
    id_free_semantic_selection_audited: Literal[True] = True
    schema_version: str = CAUSAL_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> DepthPromptProjectionContract:
        if self.host_only_field_names != HOST_ONLY_PUBLIC_KEYS:
            raise ValueError("Prompt Projection Host-only field vector changed")
        if self.forbidden_scalar_fragments != FORBIDDEN_PUBLIC_SCALAR_FRAGMENTS:
            raise ValueError("Prompt Projection forbidden scalar vector changed")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "depth_prompt_projection_contract:",
        ):
            raise ValueError("Prompt Projection Contract identity is invalid")
        return self


class PublicPromptProjection(FrozenModel):
    projection_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    graph_id: str = Field(min_length=1)
    host_state_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    fixed_generation_condition_id: str = Field(min_length=1)
    semantic_payload: dict[str, Any] = Field(min_length=2, max_length=2)
    semantic_payload_hash: str = Field(min_length=1)
    rendered_prompt_hash: str = Field(min_length=64, max_length=64)
    rendered_prompt_bytes: int = Field(ge=1)
    recursive_leakage_findings: tuple[str, ...] = ()
    current_state_count: Literal[1] = 1
    future_state_count: Literal[0] = 0
    schema_version: str = CAUSAL_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_projection(self) -> PublicPromptProjection:
        if tuple(sorted(self.semantic_payload)) != ("state", "task"):
            raise ValueError("Public Prompt payload shape changed")
        if self.recursive_leakage_findings or scan_public_leakage(self.semantic_payload):
            raise ValueError("Public Prompt projection contains recursive leakage")
        if self.semantic_payload_hash != canonical_hash(
            self.semantic_payload,
            prefix="causal_depth_public_prompt_payload:",
        ):
            raise ValueError("Public Prompt semantic hash is invalid")
        rendered = canonical_bytes(self.semantic_payload)
        if self.rendered_prompt_hash != __import__("hashlib").sha256(rendered).hexdigest():
            raise ValueError("Public Prompt rendered hash is invalid")
        if self.rendered_prompt_bytes != len(rendered):
            raise ValueError("Public Prompt byte count is invalid")
        if self.projection_id != _identity(
            self,
            "projection_id",
            "causal_depth_public_prompt_projection:",
        ):
            raise ValueError("Public Prompt Projection identity is invalid")
        return self


def make_snapshot(**values: Any) -> CausalFinanceSnapshot:
    provisional = CausalFinanceSnapshot.model_construct(snapshot_id="pending", **values)
    return CausalFinanceSnapshot(
        snapshot_id=_identity(provisional, "snapshot_id", "causal_finance_snapshot:"),
        **values,
    )


def initial_snapshot() -> CausalFinanceSnapshot:
    return make_snapshot()


def apply_effects(
    snapshot: CausalFinanceSnapshot,
    effects: tuple[FinanceEffect, ...],
    binding: CausalFinanceBinding,
) -> CausalFinanceSnapshot:
    values = snapshot.model_dump(mode="python", exclude={"snapshot_id", "schema_version"})
    input_bindings = set(snapshot.selected_input_binding_ids)
    projections = set(snapshot.selected_projection_ids)
    produced = set(snapshot.produced_reference_ids)
    consumed = set(snapshot.consumed_reference_ids)
    failures = set(snapshot.observed_failure_codes)
    revisions = set(snapshot.revised_selector_ids)
    readiness = set(snapshot.readiness_check_ids)
    completed = set(snapshot.completed_operation_node_ids)
    for effect in effects:
        kind = effect.kind
        value = effect.value
        if kind == FinanceEffectKind.SELECT_OPERATOR:
            values["selected_operator_id"] = value
        elif kind == FinanceEffectKind.SELECT_INPUT_BINDING:
            if value not in binding.input_binding_ids:
                raise ValueError("Runtime selected an input binding outside the Finance Program")
            input_bindings.add(str(value))
        elif kind == FinanceEffectKind.SELECT_PROJECTION:
            if value not in binding.projection_ids:
                raise ValueError(
                    "Runtime selected an output projection outside the Finance Program"
                )
            projections.add(str(value))
        elif kind == FinanceEffectKind.PRODUCE_REFERENCE:
            if value not in binding.normalization_reference_ids:
                raise ValueError("Runtime produced a reference outside the Finance Program")
            produced.add(str(value))
        elif kind == FinanceEffectKind.CONSUME_REFERENCE:
            if value not in produced:
                raise ValueError("Runtime attempted to consume an unproduced reference")
            consumed.add(str(value))
        elif kind == FinanceEffectKind.RECORD_FAILURE:
            if value not in set(binding.selector_failure_codes.values()):
                raise ValueError("Runtime observed a failure outside the Finance binding")
            failures.add(str(value))
        elif kind == FinanceEffectKind.REVISE_SELECTOR:
            if value not in binding.selector_ids:
                raise ValueError("Runtime revised a selector outside the Finance binding")
            expected_failure = binding.selector_failure_codes[str(value)]
            if expected_failure not in failures:
                raise ValueError(
                    "Runtime attempted selector recovery before its matching typed failure"
                )
            revisions.add(str(value))
        elif kind == FinanceEffectKind.COMPLETE_NODE:
            if value not in binding.operation_node_ids:
                raise ValueError("Runtime completed a node outside the Finance Program")
            completed.add(str(value))
        elif kind == FinanceEffectKind.RECORD_READINESS_CHECK:
            if value not in binding.readiness_check_ids:
                raise ValueError("Runtime recorded a readiness check outside the Finance binding")
            readiness.add(str(value))
        elif kind == FinanceEffectKind.SET_EXPECTED_RESULT:
            values["result_hash"] = binding.expected_result_hash
        elif kind == FinanceEffectKind.SET_ALTERNATE_RESULT:
            values["result_hash"] = canonical_hash(
                {"binding_id": binding.binding_id, "alternate": value},
                prefix="causal_alternate_finance_result:",
            )
        elif kind == FinanceEffectKind.CLOSE_PROGRAM:
            if not set(binding.operation_node_ids) <= completed:
                raise ValueError("Runtime closed the Finance Program before all nodes completed")
            values["program_closed"] = True
        elif kind == FinanceEffectKind.VERIFY_TERMINAL:
            if not values["program_closed"] or values["result_hash"] is None:
                raise ValueError("Runtime verified the Finance Program before closure")
            values["terminal_verified"] = values["result_hash"] == binding.expected_result_hash
        elif kind == FinanceEffectKind.STOP:
            if not values["terminal_verified"]:
                raise ValueError("Runtime stopped before successful terminal verification")
            values["stopped"] = True
        elif kind == FinanceEffectKind.RECORD_POSTCOMPLETION_CALL:
            if not values["terminal_verified"]:
                raise ValueError("Runtime recorded a postcompletion call before verification")
            values["postcompletion_violation"] = True
        elif kind == FinanceEffectKind.INCREMENT_INVOCATION:
            values["invocation_count"] += 1
        else:  # pragma: no cover - exhaustive Enum guard
            raise ValueError(f"unknown Finance effect:{kind}")
    values["selected_input_binding_ids"] = tuple(sorted(input_bindings))
    values["selected_projection_ids"] = tuple(sorted(projections))
    values["produced_reference_ids"] = tuple(sorted(produced))
    values["consumed_reference_ids"] = tuple(sorted(consumed))
    values["observed_failure_codes"] = tuple(sorted(failures))
    values["revised_selector_ids"] = tuple(sorted(revisions))
    values["readiness_check_ids"] = tuple(sorted(readiness))
    values["completed_operation_node_ids"] = tuple(sorted(completed))
    return make_snapshot(**values)


class CausalCapabilityDepthRuntime:
    def __init__(
        self,
        graph: HostExecutableDepthGraph,
        binding: CausalFinanceBinding,
    ) -> None:
        if (
            graph.finance_binding_id != binding.binding_id
            or graph.finance_core_id != binding.finance_core_id
            or graph.base_operational_task_package_id != binding.base_operational_task_package_id
        ):
            raise ValueError("causal Runtime received a crossed Finance binding")
        self.graph = graph
        self.binding = binding
        self._states = {item.state_id: item for item in graph.states}
        self._candidates = {item.candidate_id: item for item in graph.candidates}
        self._transitions = {item.candidate_id: item for item in graph.transitions}
        self.state_id = graph.initial_state_id
        self.snapshot = self.state.finance_snapshot
        self.observations: list[CausalRuntimeObservation] = []

    @property
    def state(self) -> HostExecutableDepthState:
        return self._states[self.state_id]

    @property
    def public_state(self) -> PublicExecutableDepthState:
        return self.state.public_state

    def execute(self, public_action_id: str) -> CausalRuntimeObservation:
        state = self.state
        if state.terminal_kind != CausalTerminalKind.NONE:
            raise ValueError("causal Runtime forbids actions after a terminal")
        candidates = tuple(self._candidates[item] for item in state.candidate_ids)
        matches = tuple(item for item in candidates if item.public_action_id == public_action_id)
        if len(matches) != 1:
            raise ValueError("causal Runtime rejected a nonvisible or ambiguous public action")
        candidate = matches[0]
        transition = self._transitions[candidate.candidate_id]
        next_snapshot = apply_effects(self.snapshot, transition.effects, self.binding)
        next_state = self._states[transition.to_state_id]
        if next_snapshot.snapshot_id != next_state.finance_snapshot.snapshot_id:
            raise ValueError("causal Runtime effect does not reconstruct the target State")
        values = {
            "call_index": len(self.observations) + 1,
            "from_state_id": state.state_id,
            "public_state_token": state.public_state.state_token,
            "visible_action_ids": tuple(item.action_id for item in state.public_state.options),
            "chosen_public_action_id": public_action_id,
            "host_candidate_id": candidate.candidate_id,
            "transition_id": transition.transition_id,
            "to_state_id": next_state.state_id,
            "status": transition.status,
            "public_observation": transition.public_observation,
            "failure_code": transition.failure_code,
            "before_snapshot_id": self.snapshot.snapshot_id,
            "after_snapshot_id": next_snapshot.snapshot_id,
            "emitted_event_types": transition.emitted_event_types,
            "emitted_reference_ids": transition.emitted_reference_ids,
            "consumed_reference_ids": transition.consumed_reference_ids,
        }
        provisional = CausalRuntimeObservation.model_construct(
            observation_id="pending",
            **values,
        )
        observation = CausalRuntimeObservation(
            observation_id=_identity(
                provisional,
                "observation_id",
                "causal_depth_runtime_observation:",
            ),
            **values,
        )
        self.observations.append(observation)
        self.snapshot = next_snapshot
        self.state_id = next_state.state_id
        return observation


def event_multiplicities(
    observations: tuple[CausalRuntimeObservation, ...],
) -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                event for observation in observations for event in observation.emitted_event_types
            ).items()
        )
    )
