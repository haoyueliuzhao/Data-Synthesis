from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.schema import TaskPublicSpec
from trusted_synthesis.core.trajectory.public_operation import (
    PublicOperationContractView,
    PublicOperationVariable,
    PublicTerminalVerificationTargetView,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.public_operation import public_operation_progress
from trusted_synthesis.runtime.tools import (
    AgentToolCall,
    AgentToolEnvironmentManifest,
    AgentToolObservation,
    AgentToolResult,
    AgentToolSpec,
)

ACTION_CONSTRUCTIBILITY_PROTOCOL_VERSION: Final[
    Literal["prospective_public_action_constructibility.v1"]
] = "prospective_public_action_constructibility.v1"
PUBLIC_ACTION_STATE_VERSION: Final[Literal["prospective_public_action_state.v1"]] = (
    "prospective_public_action_state.v1"
)
SEMANTIC_PROPOSAL_VERSION: Final[Literal["prospective_semantic_decision_proposal.v1"]] = (
    "prospective_semantic_decision_proposal.v1"
)
DECISION_COMMIT_VERSION: Final[Literal["prospective_decision_commit_compilation.v1"]] = (
    "prospective_decision_commit_compilation.v1"
)
FAILURE_TAXONOMY_VERSION: Final[Literal["prospective_two_stage_failure_taxonomy.v1"]] = (
    "prospective_two_stage_failure_taxonomy.v1"
)

UNKNOWN_TOOL_ERROR_CODE: Final[Literal["unknown_or_unselectable_tool"]] = (
    "unknown_or_unselectable_tool"
)
UNKNOWN_TOOL_ERROR_MESSAGE: Final[str] = (
    "The selected tool is not available in the public environment."
)

DecisionKind = Literal[
    "acquire_public_input",
    "execute_public_operation",
    "verify_terminal_operation",
    "emit_final_answer",
]
ReferenceKind = Literal["public_evidence", "public_operation"]
ProspectiveFailureFamily = Literal[
    "channel_parse_failure",
    "response_serialization_failure",
    "decision_phase_control_failure",
    "prompt_echo_instruction_failure",
    "semantic_tool_argument_failure",
    "runtime_failure",
    "instrument_failure",
]

_PRIVATE_KEYS = frozenset(
    {
        "correct_answer",
        "expected_arguments",
        "gold_evidence_ids",
        "mechanism_private_state",
        "oracle",
        "oracle_program",
        "private_reasoning",
        "private_reasoning_content",
        "source_program_node_id",
        "target_evidence_ids",
    }
)
_OMITTED_RESULT_KEYS = frozenset(
    {
        "content_hash",
        "observation_id",
        "observation_time_hash",
        "provenance_hash",
        "provenance_hashes",
        "query_hash",
        "snapshot_hash",
        "source_locator_hash",
    }
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PublicToolGrammar(FrozenModel):
    tool_id: str = Field(min_length=1)
    semantic_role: str = Field(min_length=1)
    input_contract: dict[str, Any] = Field(min_length=1)
    required_input_fields: tuple[str, ...] = Field(min_length=1)
    allow_additional_input_fields: bool
    model_selectable: Literal[True] = True

    @model_validator(mode="after")
    def validate_grammar(self) -> PublicToolGrammar:
        if self.required_input_fields != tuple(sorted(set(self.required_input_fields))):
            raise ValueError("public tool grammar fields are not canonical")
        if not set(self.required_input_fields) <= set(self.input_contract):
            raise ValueError("public tool grammar omits a required field")
        _reject_private_keys(self.model_dump(mode="json"))
        return self


class PublicVariableAffordance(FrozenModel):
    symbol: str = Field(min_length=1)
    semantic_role: str = Field(min_length=1)
    public_record: dict[str, Any] = Field(min_length=1)
    acquisition_tool_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_affordance(self) -> PublicVariableAffordance:
        if self.acquisition_tool_ids != tuple(sorted(set(self.acquisition_tool_ids))):
            raise ValueError("public acquisition tools are not canonical")
        _reject_private_keys(self.model_dump(mode="json"))
        return self


class PublicResolvedBinding(FrozenModel):
    source_symbol: str = Field(min_length=1)
    reference_kind: ReferenceKind
    evidence_id: str | None = None
    operation_ref: str | None = None

    @model_validator(mode="after")
    def validate_binding(self) -> PublicResolvedBinding:
        if self.reference_kind == "public_evidence":
            if not self.evidence_id or self.operation_ref is not None:
                raise ValueError("public Evidence binding is malformed")
        elif not self.operation_ref or self.evidence_id is not None:
            raise ValueError("public Operation binding is malformed")
        return self


class PublicOperandSlot(FrozenModel):
    position: int = Field(ge=0)
    source_symbol: str = Field(min_length=1)
    reference_kind: ReferenceKind
    selector: str | None = None
    serialized_reference_fields: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_slot(self) -> PublicOperandSlot:
        expected = (
            ("evidence_id",)
            if self.reference_kind == "public_evidence"
            else (
                ("operation_ref", "selector") if self.selector is not None else ("operation_ref",)
            )
        )
        if self.serialized_reference_fields != expected:
            raise ValueError("public operand wire grammar changed")
        return self


class PublicReadyOperation(FrozenModel):
    node_id: str = Field(min_length=1)
    node_kind: Literal["normalization", "calculation"]
    semantic_role: str = Field(min_length=1)
    tool_id: str = Field(min_length=1)
    dependency_node_ids: tuple[str, ...]
    operand_slots: tuple[PublicOperandSlot, ...] = Field(min_length=1)
    allowed_operator_ids: tuple[str, ...]
    operator_choice_mode: str = Field(min_length=1)
    fixed_parameters: dict[str, Any]
    normalization_target: dict[str, Any] | None = None
    unresolved_symbols: tuple[str, ...]

    @model_validator(mode="after")
    def validate_operation(self) -> PublicReadyOperation:
        if tuple(item.position for item in self.operand_slots) != tuple(
            range(len(self.operand_slots))
        ):
            raise ValueError("public operand slots are not ordered")
        if self.allowed_operator_ids != tuple(sorted(set(self.allowed_operator_ids))):
            raise ValueError("public operator choices are not canonical")
        if self.node_kind == "normalization":
            if self.allowed_operator_ids or self.normalization_target is None:
                raise ValueError("public normalization grammar is malformed")
        elif not self.allowed_operator_ids or self.normalization_target is not None:
            raise ValueError("public calculation grammar is malformed")
        _reject_private_keys(self.model_dump(mode="json"))
        return self


class BoundedFailureSummary(FrozenModel):
    failed_tool_id: str = Field(min_length=1)
    error_category: str = Field(min_length=1)
    latest_call_index: int = Field(ge=1)
    blocked_call_signature_hash: str = Field(min_length=1)
    argument_shape: dict[str, Any]
    exact_argument_values_retained: Literal[False] = False


class FinalAnswerSourceProjection(FrozenModel):
    terminal_operation_ref: str = Field(min_length=1)
    terminal_result_projection: dict[str, Any] = Field(min_length=1)
    answer_source_fields: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_projection(self) -> FinalAnswerSourceProjection:
        _reject_private_keys(self.terminal_result_projection)
        return self


class PublicActionState(FrozenModel):
    state_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    tool_grammars: tuple[PublicToolGrammar, ...] = Field(min_length=1)
    variable_affordances: tuple[PublicVariableAffordance, ...]
    resolved_bindings: tuple[PublicResolvedBinding, ...]
    ready_operations: tuple[PublicReadyOperation, ...]
    unresolved_symbols: tuple[str, ...]
    selected_evidence_ids: tuple[str, ...]
    bounded_failure_history: tuple[BoundedFailureSummary, ...]
    terminal_operation_ref: str | None
    terminal_verification_completed: bool
    final_answer_allowed: bool
    final_answer_source: FinalAnswerSourceProjection | None
    action_binding_fields_exposed: Literal[True] = True
    semantic_choice_still_model_owned: Literal[True] = True
    deterministic_serialization_only: Literal[True] = True
    private_or_oracle_fields_exposed: Literal[False] = False
    schema_version: Literal["prospective_public_action_state.v1"] = PUBLIC_ACTION_STATE_VERSION

    @model_validator(mode="after")
    def validate_state(self) -> PublicActionState:
        tool_ids = tuple(item.tool_id for item in self.tool_grammars)
        if tool_ids != tuple(sorted(set(tool_ids))):
            raise ValueError("public action-state tools are not canonical")
        binding_symbols = tuple(item.source_symbol for item in self.resolved_bindings)
        if binding_symbols != tuple(sorted(set(binding_symbols))):
            raise ValueError("public action-state bindings are not canonical")
        available = set(tool_ids)
        if any(
            not set(item.acquisition_tool_ids) <= available for item in self.variable_affordances
        ):
            raise ValueError("variable acquisition tools exceed the public tool affordance")
        if self.final_answer_allowed != bool(
            self.terminal_verification_completed and self.final_answer_source is not None
        ):
            raise ValueError("public final-answer source and readiness differ")
        _reject_private_keys(self.model_dump(mode="json", exclude={"state_id"}))
        if self.state_id != public_action_state_id(self):
            raise ValueError("public action-state identity changed")
        return self


class SemanticDecisionProposal(FrozenModel):
    proposal_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    decision_kind: DecisionKind
    tool_id: str | None = None
    node_id: str | None = None
    operator_id: str | None = None
    operand_sources: tuple[str, ...] = ()
    direct_arguments: dict[str, Any] | None = None
    evidence_ids: tuple[str, ...] = ()
    model_selected_every_semantic_field: Literal[True] = True
    schema_version: Literal["prospective_semantic_decision_proposal.v1"] = SEMANTIC_PROPOSAL_VERSION

    @model_validator(mode="after")
    def validate_proposal(self) -> SemanticDecisionProposal:
        if self.decision_kind == "acquire_public_input":
            if (
                not self.tool_id
                or self.direct_arguments is None
                or self.node_id is not None
                or self.operator_id is not None
                or self.operand_sources
                or self.evidence_ids
            ):
                raise ValueError("public acquisition proposal is malformed")
        elif self.decision_kind == "execute_public_operation":
            if (
                not self.tool_id
                or not self.node_id
                or self.direct_arguments is not None
                or not self.operand_sources
                or self.evidence_ids
            ):
                raise ValueError("public Operation proposal is malformed")
        elif self.decision_kind == "verify_terminal_operation":
            if (
                not self.tool_id
                or self.node_id is not None
                or self.operator_id is not None
                or self.operand_sources
                or self.direct_arguments is not None
                or not self.evidence_ids
            ):
                raise ValueError("public terminal-verification proposal is malformed")
        elif any(
            (
                self.tool_id,
                self.node_id,
                self.operator_id,
                self.operand_sources,
                self.direct_arguments,
                self.evidence_ids,
            )
        ):
            raise ValueError("public final-answer proposal carries a tool action")
        _reject_private_keys(self.model_dump(mode="json", exclude={"proposal_id"}))
        if self.proposal_id != semantic_decision_proposal_id(self):
            raise ValueError("semantic proposal identity changed")
        return self


class DecisionCommitCompilation(FrozenModel):
    commit_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    decision_kind: DecisionKind
    action: Literal["call_tool", "emit_final"]
    call: AgentToolCall | None
    semantic_field_projection_hash: str = Field(min_length=1)
    proposal_semantics_preserved: Literal[True] = True
    compiler_selected_tool_node_operator_or_operand: Literal[False] = False
    deterministic_wire_serialization_only: Literal[True] = True
    reversible_mapping_passed: Literal[True] = True
    schema_version: Literal["prospective_decision_commit_compilation.v1"] = DECISION_COMMIT_VERSION

    @model_validator(mode="after")
    def validate_commit(self) -> DecisionCommitCompilation:
        if (self.action == "call_tool") != (self.call is not None):
            raise ValueError("decision Commit action and tool call differ")
        if self.commit_id != decision_commit_compilation_id(self):
            raise ValueError("decision Commit identity changed")
        return self


class ProspectiveFailureClassification(FrozenModel):
    family: ProspectiveFailureFamily
    subtype: str = Field(min_length=1)
    historical_terminal_reclassified: Literal[False] = False
    prospective_only: Literal[True] = True
    schema_version: Literal["prospective_two_stage_failure_taxonomy.v1"] = FAILURE_TAXONOMY_VERSION


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(field, None)
    return canonical_hash(payload, prefix=prefix)


def public_action_state_id(value: PublicActionState) -> str:
    return _identity(value, "state_id", "prospective_public_action_state:")


def semantic_decision_proposal_id(value: SemanticDecisionProposal) -> str:
    return _identity(value, "proposal_id", "prospective_semantic_decision_proposal:")


def decision_commit_compilation_id(value: DecisionCommitCompilation) -> str:
    return _identity(value, "commit_id", "prospective_decision_commit_compilation:")


def _reject_private_keys(value: Any, *, path: str = "public") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in _PRIVATE_KEYS:
                raise ValueError(f"private or Oracle field exposed at {path}.{key}")
            _reject_private_keys(item, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_private_keys(item, path=f"{path}[{index}]")


def resolve_model_selectable_tool_or_typed_failure(
    environment: AgentToolEnvironmentManifest,
    call: AgentToolCall,
) -> tuple[AgentToolSpec | None, AgentToolResult | None]:
    """One exact availability gate shared by every prospective Runtime and Verifier."""

    spec = environment.tools_by_id.get(call.tool_id)
    if spec is not None and spec.model_selectable:
        return spec, None
    return None, AgentToolResult(
        status="failed",
        result={},
        error_code=UNKNOWN_TOOL_ERROR_CODE,
        error_message=UNKNOWN_TOOL_ERROR_MESSAGE,
    )


def effective_acquisition_tool_ids(
    variable: PublicOperationVariable,
    environment: AgentToolEnvironmentManifest,
    *,
    stage_tool_ids: frozenset[str] | None = None,
) -> tuple[str, ...]:
    selectable = {item.tool_id for item in environment.tools if item.model_selectable}
    if stage_tool_ids is not None:
        selectable &= set(stage_tool_ids)
    resolution_tools = {item.source_tool_id for item in variable.resolution_rules}
    effective = tuple(sorted(resolution_tools & selectable))
    if not effective:
        raise ValueError(f"public variable {variable.symbol} has no effective acquisition tool")
    return effective


def _load_contracts(
    task: TaskPublicSpec,
) -> tuple[PublicOperationContractView, PublicTerminalVerificationTargetView]:
    guidance = task.metadata.get("agent_contract_guidance")
    if not isinstance(guidance, Mapping):
        raise ValueError("action constructibility requires public Agent guidance")
    raw_operation = guidance.get("public_operation_execution_contract")
    raw_target = guidance.get("public_terminal_verification_target")
    if not isinstance(raw_operation, Mapping) or not isinstance(raw_target, Mapping):
        raise ValueError("action constructibility requires Operation and terminal contracts")
    return (
        PublicOperationContractView.model_validate(raw_operation),
        PublicTerminalVerificationTargetView.model_validate(raw_target),
    )


def _try_select(value: Any, selector: Sequence[str]) -> Any:
    current = value
    for part in selector:
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return None
    return current


def _resolved_variables(
    variables: tuple[PublicOperationVariable, ...],
    observations: tuple[AgentToolObservation, ...],
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for variable in variables:
        matches: set[str] = set()
        for rule in variable.resolution_rules:
            for observation in observations:
                if (
                    observation.status != "succeeded"
                    or observation.call.tool_id != rule.source_tool_id
                ):
                    continue
                collection = _try_select(observation.result, rule.collection_selector)
                if not isinstance(collection, (list, tuple)):
                    continue
                for candidate in collection:
                    if not all(
                        _try_select(candidate, predicate.selector) == predicate.value
                        for predicate in rule.equals
                    ):
                        continue
                    evidence_id = _try_select(candidate, rule.evidence_id_selector)
                    if isinstance(evidence_id, str) and evidence_id.startswith("evidence:"):
                        matches.add(evidence_id)
        if len(matches) == 1:
            resolved[variable.symbol] = next(iter(matches))
        elif len(matches) > 1:
            raise ValueError(f"public variable {variable.symbol} resolves ambiguously")
    return resolved


def _public_record(variable: PublicOperationVariable) -> dict[str, Any]:
    predicate_sets: list[tuple[tuple[str, Any], ...]] = []
    for rule in variable.resolution_rules:
        predicate_sets.append(
            tuple(sorted((".".join(item.selector), item.value) for item in rule.equals))
        )
    if len(set(predicate_sets)) != 1:
        raise ValueError("public variable acquisition rules disagree semantically")
    values = dict(predicate_sets[0])
    record = {
        "subject_id": values.get("subject.subject_id"),
        "subject_name": values.get("subject.name"),
        "subject_type": values.get("subject.type"),
        "metric": values.get("metric.predicate"),
        "definition_id": values.get("metric.definition_id"),
        "period": values.get("period"),
        "source_id": values.get("source.source_id"),
        "source_authority": values.get("source.authority"),
        "unit": values.get("payload.unit"),
        "currency": values.get("payload.currency"),
        "frequency": values.get("frequency"),
        "time_basis": values.get("time_basis"),
    }
    return record


def _without_telemetry(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _without_telemetry(item)
            for key, item in value.items()
            if str(key) not in _OMITTED_RESULT_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_without_telemetry(item) for item in value]
    return value


def _argument_shape(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _argument_shape(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return {
            "container": "array",
            "length": len(value),
            "item_shapes": tuple(_argument_shape(item) for item in value),
        }
    if isinstance(value, str):
        if value.startswith("evidence:"):
            return "public_evidence_id"
        if value.startswith("operation:"):
            return "public_operation_ref"
        return "string"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__


def bounded_failure_history(
    observations: tuple[AgentToolObservation, ...],
) -> tuple[BoundedFailureSummary, ...]:
    latest: dict[tuple[str, str], AgentToolObservation] = {}
    for observation in observations:
        if observation.status == "failed" and observation.error_code:
            latest[(observation.call.tool_id, observation.error_code)] = observation
    rows = []
    for key in sorted(latest):
        observation = latest[key]
        rows.append(
            BoundedFailureSummary(
                failed_tool_id=observation.call.tool_id,
                error_category=str(observation.error_code),
                latest_call_index=observation.call.call_index,
                blocked_call_signature_hash=canonical_hash(
                    {
                        "tool_id": observation.call.tool_id,
                        "arguments": observation.call.arguments,
                    },
                    prefix="prospective_blocked_public_call:",
                ),
                argument_shape=_argument_shape(observation.call.arguments),
            )
        )
    return tuple(rows)


def _terminal_result_projection(
    observations: tuple[AgentToolObservation, ...],
    terminal_operation_ref: str | None,
) -> FinalAnswerSourceProjection | None:
    if terminal_operation_ref is None:
        return None
    for observation in observations:
        if observation.status != "succeeded":
            continue
        public_result = _without_telemetry(observation.result)
        serialized = json.dumps(public_result, sort_keys=True, ensure_ascii=False)
        if terminal_operation_ref not in serialized:
            continue
        fields = tuple(
            sorted(
                str(key)
                for key in _leaf_paths(public_result)
                if not str(key).endswith("operation_ref")
            )
        )
        return FinalAnswerSourceProjection(
            terminal_operation_ref=terminal_operation_ref,
            terminal_result_projection=public_result,
            answer_source_fields=fields or ("terminal_result_projection",),
        )
    raise ValueError("terminal public Operation reference lacks a public result")


def _leaf_paths(value: Any, *, path: str = "terminal_result") -> tuple[str, ...]:
    if isinstance(value, Mapping):
        output: list[str] = []
        for key, item in sorted(value.items()):
            output.extend(_leaf_paths(item, path=f"{path}.{key}"))
        return tuple(output)
    if isinstance(value, (list, tuple)):
        output = []
        for index, item in enumerate(value):
            output.extend(_leaf_paths(item, path=f"{path}[{index}]"))
        return tuple(output)
    return (path,)


def build_public_action_state(
    task: TaskPublicSpec,
    environment: AgentToolEnvironmentManifest,
    observations: tuple[AgentToolObservation, ...],
    *,
    stage_tool_ids: frozenset[str] | None = None,
) -> PublicActionState:
    operation, target = _load_contracts(task)
    progress = public_operation_progress(task, observations)
    if progress is None:
        raise ValueError("public Operation progress is unavailable")
    stage_tools = (
        stage_tool_ids
        if stage_tool_ids is not None
        else frozenset(item.tool_id for item in environment.tools if item.model_selectable)
    )
    variable_affordances = tuple(
        PublicVariableAffordance(
            symbol=variable.symbol,
            semantic_role=variable.semantic_role,
            public_record=_public_record(variable),
            acquisition_tool_ids=effective_acquisition_tool_ids(
                variable,
                environment,
                stage_tool_ids=stage_tools,
            ),
        )
        for variable in operation.variables
    )
    resolved = _resolved_variables(operation.variables, observations)
    completed_refs = {
        str(key): str(value) for key, value in progress["completed_node_operation_refs"].items()
    }
    nodes = {item.node_id: item for item in operation.nodes}
    variable_symbols = {item.symbol for item in operation.variables}
    bindings = [
        PublicResolvedBinding(
            source_symbol=symbol,
            reference_kind="public_evidence",
            evidence_id=evidence_id,
        )
        for symbol, evidence_id in resolved.items()
    ]
    for node_id, operation_ref in completed_refs.items():
        bindings.append(
            PublicResolvedBinding(
                source_symbol=nodes[node_id].output_symbol,
                reference_kind="public_operation",
                operation_ref=operation_ref,
            )
        )
    ready = []
    for payload in progress["ready_nodes"]:
        node = nodes[str(payload["node_id"])]
        slots = tuple(
            PublicOperandSlot(
                position=index,
                source_symbol=item.source_symbol,
                reference_kind=(
                    "public_evidence"
                    if item.source_symbol in variable_symbols
                    else "public_operation"
                ),
                selector=item.selector,
                serialized_reference_fields=(
                    ("evidence_id",)
                    if item.source_symbol in variable_symbols
                    else (
                        ("operation_ref", "selector")
                        if item.selector is not None
                        else ("operation_ref",)
                    )
                ),
            )
            for index, item in enumerate(node.inputs)
        )
        ready.append(
            PublicReadyOperation(
                node_id=node.node_id,
                node_kind=node.node_kind,
                semantic_role=node.semantic_role,
                tool_id=node.tool_id,
                dependency_node_ids=node.dependency_node_ids,
                operand_slots=slots,
                allowed_operator_ids=node.allowed_operator_ids,
                operator_choice_mode=node.operator_choice_mode,
                fixed_parameters=dict(node.parameters),
                normalization_target=(
                    dict(node.normalization_target)
                    if node.normalization_target is not None
                    else None
                ),
                unresolved_symbols=tuple(str(item) for item in payload["unresolved_symbols"]),
            )
        )
    relevant_tool_ids = {
        tool_id for item in variable_affordances for tool_id in item.acquisition_tool_ids
    }
    if progress["unresolved_symbols"]:
        relevant_tool_ids.update(
            item.tool_id
            for item in environment.tools
            if item.model_selectable and item.semantic_role in {"acquire", "inspect", "query"}
        )
    relevant_tool_ids.update(item.tool_id for item in ready)
    if progress["terminal_node_completed"]:
        relevant_tool_ids.add(target.verification_tool_id)
    grammars = tuple(
        PublicToolGrammar(
            tool_id=spec.tool_id,
            semantic_role=spec.semantic_role,
            input_contract=dict(spec.input_contract),
            required_input_fields=tuple(sorted(spec.required_input_fields)),
            allow_additional_input_fields=spec.allow_additional_input_fields,
        )
        for spec in sorted(environment.tools, key=lambda item: item.tool_id)
        if spec.model_selectable
        and spec.tool_id in relevant_tool_ids
        and spec.tool_id in stage_tools
    )
    terminal_ref = (
        str(progress["terminal_operation_ref"])
        if progress["terminal_operation_ref"] is not None
        else None
    )
    final_source = _terminal_result_projection(observations, terminal_ref)
    values = {
        "task_id": task.task_id,
        "environment_manifest_id": environment.manifest_id,
        "tool_grammars": grammars,
        "variable_affordances": variable_affordances,
        "resolved_bindings": tuple(sorted(bindings, key=lambda item: item.source_symbol)),
        "ready_operations": tuple(sorted(ready, key=lambda item: item.node_id)),
        "unresolved_symbols": tuple(str(item) for item in progress["unresolved_symbols"]),
        "selected_evidence_ids": tuple(
            sorted(
                {
                    evidence_id
                    for observation in observations
                    if observation.status == "succeeded"
                    for evidence_id in observation.evidence_ids
                }
            )
        ),
        "bounded_failure_history": bounded_failure_history(observations),
        "terminal_operation_ref": terminal_ref,
        "terminal_verification_completed": bool(progress["verification_after_terminal_completed"]),
        "final_answer_allowed": bool(progress["final_answer_allowed"]),
        "final_answer_source": (
            final_source if progress["verification_after_terminal_completed"] else None
        ),
    }
    provisional = PublicActionState.model_construct(state_id="pending", **values)
    return PublicActionState(state_id=public_action_state_id(provisional), **values)


def make_semantic_decision_proposal(
    *,
    state_id: str,
    decision_kind: DecisionKind,
    tool_id: str | None = None,
    node_id: str | None = None,
    operator_id: str | None = None,
    operand_sources: tuple[str, ...] = (),
    direct_arguments: dict[str, Any] | None = None,
    evidence_ids: tuple[str, ...] = (),
) -> SemanticDecisionProposal:
    values = {
        "state_id": state_id,
        "decision_kind": decision_kind,
        "tool_id": tool_id,
        "node_id": node_id,
        "operator_id": operator_id,
        "operand_sources": operand_sources,
        "direct_arguments": direct_arguments,
        "evidence_ids": evidence_ids,
    }
    provisional = SemanticDecisionProposal.model_construct(proposal_id="pending", **values)
    return SemanticDecisionProposal(
        proposal_id=semantic_decision_proposal_id(provisional),
        **values,
    )


def _semantic_projection(value: SemanticDecisionProposal) -> dict[str, Any]:
    return value.model_dump(
        mode="json",
        exclude={"proposal_id", "model_selected_every_semantic_field", "schema_version"},
    )


def _compile_public_call(
    state: PublicActionState,
    proposal: SemanticDecisionProposal,
    *,
    call_index: int,
) -> AgentToolCall | None:
    grammars = {item.tool_id: item for item in state.tool_grammars}
    if proposal.decision_kind == "emit_final_answer":
        if not state.final_answer_allowed:
            raise ValueError("final answer proposed before exact public readiness")
        return None
    if proposal.tool_id not in grammars:
        raise ValueError("semantic proposal selects a tool outside the public state")
    if proposal.decision_kind == "acquire_public_input":
        acquisition_tools = {
            tool_id
            for item in state.variable_affordances
            if item.symbol in set(state.unresolved_symbols)
            for tool_id in item.acquisition_tool_ids
        }
        acquisition_tools.update(
            item.tool_id
            for item in state.tool_grammars
            if item.semantic_role in {"acquire", "inspect", "query"}
        )
        if proposal.tool_id not in acquisition_tools:
            raise ValueError("semantic acquisition selects a non-effective tool")
        arguments = dict(proposal.direct_arguments or {})
    elif proposal.decision_kind == "verify_terminal_operation":
        if not state.terminal_operation_ref or state.terminal_verification_completed:
            raise ValueError("terminal verification proposed in the wrong public state")
        if not set(proposal.evidence_ids) <= set(state.selected_evidence_ids):
            raise ValueError("terminal verification selects unavailable public Evidence")
        arguments = {
            "evidence_ids": list(proposal.evidence_ids),
            "claim_or_result": {"operation_ref": state.terminal_operation_ref},
        }
    else:
        ready = {item.node_id: item for item in state.ready_operations}
        operation = ready.get(str(proposal.node_id))
        if operation is None or operation.tool_id != proposal.tool_id:
            raise ValueError("semantic proposal does not select a ready public Operation")
        if operation.unresolved_symbols:
            raise ValueError("semantic proposal selects an unresolved public Operation")
        expected_sources = tuple(item.source_symbol for item in operation.operand_slots)
        if proposal.operand_sources != expected_sources:
            raise ValueError("semantic proposal changes registered public operand sources")
        bindings = {item.source_symbol: item for item in state.resolved_bindings}
        operands = []
        for slot in operation.operand_slots:
            binding = bindings.get(slot.source_symbol)
            if binding is None or binding.reference_kind != slot.reference_kind:
                raise ValueError("semantic proposal references an unresolved public binding")
            if binding.reference_kind == "public_evidence":
                operands.append({"evidence_id": binding.evidence_id})
            else:
                item: dict[str, Any] = {"operation_ref": binding.operation_ref}
                if slot.selector is not None:
                    item["selector"] = slot.selector
                operands.append(item)
        if operation.node_kind == "normalization":
            if proposal.operator_id is not None:
                raise ValueError("normalization proposal unexpectedly selects an operator")
            arguments = {
                "evidence_ids": [item["evidence_id"] for item in operands],
                "target_definition": dict(operation.normalization_target or {}),
            }
        else:
            if proposal.operator_id not in set(operation.allowed_operator_ids):
                raise ValueError("semantic proposal selects an unavailable operator")
            arguments = {
                "operator": proposal.operator_id,
                "operands": operands,
                "parameters": dict(operation.fixed_parameters),
            }
    grammar = grammars[str(proposal.tool_id)]
    missing = set(grammar.required_input_fields) - set(arguments)
    extra = set(arguments) - set(grammar.input_contract)
    if missing or (extra and not grammar.allow_additional_input_fields):
        raise ValueError("compiled public call violates the exposed tool grammar")
    return AgentToolCall(
        call_index=call_index,
        tool_id=str(proposal.tool_id),
        arguments=arguments,
    )


def decompile_public_call(
    state: PublicActionState,
    call: AgentToolCall,
) -> SemanticDecisionProposal:
    ready = tuple(item for item in state.ready_operations if item.tool_id == call.tool_id)
    for operation in ready:
        operator = call.arguments.get("operator") if operation.node_kind == "calculation" else None
        candidate = make_semantic_decision_proposal(
            state_id=state.state_id,
            decision_kind="execute_public_operation",
            tool_id=call.tool_id,
            node_id=operation.node_id,
            operator_id=str(operator) if operator is not None else None,
            operand_sources=tuple(item.source_symbol for item in operation.operand_slots),
        )
        try:
            compiled = _compile_public_call(state, candidate, call_index=call.call_index)
        except ValueError:
            continue
        if compiled == call:
            return candidate
    if state.terminal_operation_ref and call.arguments.get("claim_or_result") == {
        "operation_ref": state.terminal_operation_ref
    }:
        raw_evidence = call.arguments.get("evidence_ids")
        if isinstance(raw_evidence, list) and all(isinstance(item, str) for item in raw_evidence):
            candidate = make_semantic_decision_proposal(
                state_id=state.state_id,
                decision_kind="verify_terminal_operation",
                tool_id=call.tool_id,
                evidence_ids=tuple(raw_evidence),
            )
            if _compile_public_call(state, candidate, call_index=call.call_index) == call:
                return candidate
    candidate = make_semantic_decision_proposal(
        state_id=state.state_id,
        decision_kind="acquire_public_input",
        tool_id=call.tool_id,
        direct_arguments=dict(call.arguments),
    )
    if _compile_public_call(state, candidate, call_index=call.call_index) != call:
        raise ValueError("public tool call cannot be reversibly mapped to a semantic proposal")
    return candidate


def compile_semantic_decision(
    state: PublicActionState,
    proposal: SemanticDecisionProposal,
    *,
    call_index: int,
) -> DecisionCommitCompilation:
    if proposal.state_id != state.state_id:
        raise ValueError("semantic proposal binds another public action state")
    call = _compile_public_call(state, proposal, call_index=call_index)
    if call is not None:
        recovered = decompile_public_call(state, call)
        if _semantic_projection(recovered) != _semantic_projection(proposal):
            raise ValueError("deterministic public call does not reverse to its proposal")
    projection_hash = canonical_hash(
        _semantic_projection(proposal),
        prefix="prospective_semantic_field_projection:",
    )
    values = {
        "state_id": state.state_id,
        "proposal_id": proposal.proposal_id,
        "decision_kind": proposal.decision_kind,
        "action": "emit_final" if call is None else "call_tool",
        "call": call,
        "semantic_field_projection_hash": projection_hash,
    }
    provisional = DecisionCommitCompilation.model_construct(commit_id="pending", **values)
    return DecisionCommitCompilation(
        commit_id=decision_commit_compilation_id(provisional),
        **values,
    )


def public_reference_policy_proposal(state: PublicActionState) -> SemanticDecisionProposal:
    """A fixture policy that consumes only the serialized model-visible action state."""

    if state.unresolved_symbols:
        variable = next(
            item
            for item in state.variable_affordances
            if item.symbol == state.unresolved_symbols[0]
        )
        if "query_structured_fact" not in variable.acquisition_tool_ids:
            raise ValueError("fixture policy requires one effective structured public query")
        record = variable.public_record
        refinement_requested = any(
            item.failed_tool_id == "query_structured_fact"
            and item.error_category == "typed_selector_requires_refinement"
            for item in state.bounded_failure_history
        )
        filter_fields = (
            (
                "source_id",
                "source_authority",
                "unit",
                "currency",
                "definition_id",
                "time_basis",
                "frequency",
                "subject_type",
            )
            if refinement_requested
            else ("source_id",)
        )
        filters = {key: record[key] for key in filter_fields if key in record}
        return make_semantic_decision_proposal(
            state_id=state.state_id,
            decision_kind="acquire_public_input",
            tool_id="query_structured_fact",
            direct_arguments={
                "subject_alias": record.get("subject_name") or record.get("subject_id"),
                "metric_alias": record["metric"],
                "period_label": record["period"],
                "public_filters": filters,
            },
        )
    executable = tuple(item for item in state.ready_operations if not item.unresolved_symbols)
    if executable:
        operation = executable[0]
        return make_semantic_decision_proposal(
            state_id=state.state_id,
            decision_kind="execute_public_operation",
            tool_id=operation.tool_id,
            node_id=operation.node_id,
            operator_id=(
                operation.allowed_operator_ids[0] if operation.allowed_operator_ids else None
            ),
            operand_sources=tuple(item.source_symbol for item in operation.operand_slots),
        )
    if state.terminal_operation_ref and not state.terminal_verification_completed:
        verification_tools = tuple(
            item.tool_id for item in state.tool_grammars if item.semantic_role == "verify"
        )
        if len(verification_tools) != 1:
            raise ValueError("fixture policy requires one public terminal verification tool")
        return make_semantic_decision_proposal(
            state_id=state.state_id,
            decision_kind="verify_terminal_operation",
            tool_id=verification_tools[0],
            evidence_ids=state.selected_evidence_ids,
        )
    if state.final_answer_allowed:
        return make_semantic_decision_proposal(
            state_id=state.state_id,
            decision_kind="emit_final_answer",
        )
    raise ValueError("public action state has no constructible next decision")


def render_action_constructible_decision_prompt(
    *,
    instruction: str,
    state: PublicActionState,
    public_path_condition: str | None,
) -> str:
    payload = {
        "protocol": ACTION_CONSTRUCTIBILITY_PROTOCOL_VERSION,
        "instruction": instruction,
        "public_path_condition": public_path_condition,
        "public_action_state": state.model_dump(mode="json"),
        "response_contract": {
            "stage": "semantic_decision_proposal",
            "decision_kinds": (
                "acquire_public_input",
                "execute_public_operation",
                "verify_terminal_operation",
                "emit_final_answer",
            ),
            "low_level_wire_call_must_not_be_guessed": True,
            "private_reasoning_content_must_not_be_returned": True,
        },
    }
    _reject_private_keys(payload)
    return "Return one public semantic decision proposal as JSON.\n" + json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def public_action_state_from_rendered_prompt(prompt: str) -> PublicActionState:
    prefix, separator, raw_payload = prompt.partition("\n")
    if prefix != "Return one public semantic decision proposal as JSON." or not separator:
        raise ValueError("action-constructible Prompt envelope changed")
    payload = json.loads(raw_payload)
    if not isinstance(payload, Mapping):
        raise ValueError("action-constructible Prompt payload must be an object")
    if payload.get("protocol") != ACTION_CONSTRUCTIBILITY_PROTOCOL_VERSION:
        raise ValueError("action-constructible Prompt protocol changed")
    raw_state = payload.get("public_action_state")
    if not isinstance(raw_state, Mapping):
        raise ValueError("action-constructible Prompt omits its public action state")
    _reject_private_keys(payload)
    return PublicActionState.model_validate(raw_state)


def public_reference_policy_proposal_from_prompt(prompt: str) -> SemanticDecisionProposal:
    """Exercise the reference policy through the exact serialized model interface."""

    return public_reference_policy_proposal(public_action_state_from_rendered_prompt(prompt))


def render_semantically_sufficient_final_rescue_prompt(
    source_prompt: str,
    *,
    failure_type: str,
) -> str:
    _, separator, raw_payload = source_prompt.partition("\n")
    if not separator:
        raise ValueError("final Rescue source Prompt lacks a public JSON payload")
    payload = json.loads(raw_payload)
    if not isinstance(payload, Mapping):
        raise ValueError("final Rescue source Prompt payload must be an object")
    final_context = payload.get("final_context")
    progress = payload.get("progress")
    history = payload.get("history")
    if not isinstance(final_context, Mapping) or not isinstance(progress, Mapping):
        raise ValueError("final Rescue source Prompt lacks final context or progress")
    if not isinstance(history, Mapping):
        raise ValueError("final Rescue source Prompt lacks public history")
    terminal_ref = progress.get("terminal_operation_ref")
    if terminal_ref is None:
        completed = progress.get("completed_node_operation_refs")
        if isinstance(completed, Mapping) and completed:
            terminal_ref = completed[sorted(str(key) for key in completed)[-1]]
    if not isinstance(terminal_ref, str) or not terminal_ref:
        raise ValueError("final Rescue source Prompt lacks a terminal Operation reference")
    terminal_projection = None
    operations = history.get("operations")
    if isinstance(operations, Sequence) and not isinstance(operations, (str, bytes)):
        for operation in operations:
            if not isinstance(operation, Mapping):
                continue
            public_result = operation.get("result")
            if terminal_ref in json.dumps(public_result, ensure_ascii=False, sort_keys=True):
                terminal_projection = public_result
                break
    if not isinstance(terminal_projection, Mapping):
        raise ValueError("final Rescue source Prompt omits the terminal public result")
    capsule = {
        "final_context": dict(final_context),
        "terminal_operation_ref": terminal_ref,
        "terminal_result_projection": _without_telemetry(terminal_projection),
        "answer_source_fields": tuple(
            sorted(
                path
                for path in _leaf_paths(terminal_projection)
                if not path.endswith("operation_ref")
            )
        ),
        "selected_evidence_ids": tuple(history.get("selected_evidence_ids") or ()),
        "response_contract": {
            "fields": ("answer",),
            "answer_must_be_object": True,
            "answer_must_derive_only_from_terminal_result_projection": True,
        },
        "rescue": {
            "failure_type": failure_type,
            "previous_final_content_reused": False,
            "private_reasoning_reused": False,
            "semantic_answer_source_retained": True,
        },
    }
    _reject_private_keys(capsule)
    return "Return the final public answer object immediately.\n" + json.dumps(
        capsule,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def classify_prospective_response_failure(
    *,
    request_kind: Literal["decision", "final_answer"],
    payload: Mapping[str, Any] | None,
    json_parse_succeeded: bool,
) -> ProspectiveFailureClassification:
    if not json_parse_succeeded or payload is None:
        return ProspectiveFailureClassification(
            family="channel_parse_failure",
            subtype="invalid_or_missing_public_json",
        )
    keys = set(payload)
    if request_kind == "decision":
        if {"public_context", "progress", "history"} <= keys:
            return ProspectiveFailureClassification(
                family="prompt_echo_instruction_failure",
                subtype="public_prompt_payload_echoed",
            )
        if not {"action", "tool_id", "arguments"} <= keys:
            return ProspectiveFailureClassification(
                family="decision_phase_control_failure",
                subtype="answer_or_non_action_emitted_during_decision",
            )
        if payload.get("action") != "call_tool":
            return ProspectiveFailureClassification(
                family="response_serialization_failure",
                subtype="unregistered_decision_action_enum",
            )
        if not isinstance(payload.get("arguments"), Mapping):
            return ProspectiveFailureClassification(
                family="response_serialization_failure",
                subtype="decision_arguments_not_object",
            )
        return ProspectiveFailureClassification(
            family="semantic_tool_argument_failure",
            subtype="schema_valid_decision_rejected_by_public_semantics",
        )
    if set(payload) != {"answer"} or not isinstance(payload.get("answer"), Mapping):
        return ProspectiveFailureClassification(
            family="response_serialization_failure",
            subtype="final_answer_not_exact_object_contract",
        )
    return ProspectiveFailureClassification(
        family="runtime_failure",
        subtype="schema_valid_final_failure_requires_runtime_attribution",
    )
