from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from trusted_synthesis.core.task.schema import TaskPublicSpec
from trusted_synthesis.core.trajectory.public_operation import (
    PublicActionNeutralRepairView,
    PublicOperationContractView,
    PublicOperationNode,
    PublicOperationVariable,
    PublicStopReadinessView,
    PublicTerminalVerificationTargetView,
)
from trusted_synthesis.runtime.tools import (
    ARGUMENT_PATCH_REQUIRED_POLICY,
    PREREQUISITE_ACTION_REQUIRED_POLICY,
    AgentToolCall,
    AgentToolObservation,
    AgentToolResult,
)


def public_operation_progress(
    task: TaskPublicSpec,
    observations: tuple[AgentToolObservation, ...],
) -> dict[str, Any] | None:
    loaded = _load_contracts(task)
    if loaded is None:
        return None
    contract, stop_contract, _, verification_target = loaded
    variables = {item.symbol: item for item in contract.variables}
    nodes = {item.node_id: item for item in contract.nodes}
    completed: dict[str, dict[str, Any]] = {}
    matched_observation_ids: list[str] = []

    for observation_index, observation in enumerate(observations):
        if observation.status != "succeeded":
            continue
        resolved, _ = _resolved_variables(variables, observations[:observation_index])
        ready = _ready_nodes(nodes, completed)
        for node in ready:
            arguments, unresolved = _node_arguments(node, resolved, completed)
            if unresolved or arguments is None:
                continue
            if not _observation_matches_node(observation, node, arguments):
                continue
            operation_ref = _operation_ref(observation, node)
            if operation_ref is None:
                continue
            completed[node.node_id] = {
                "operation_ref": operation_ref,
                "output_symbol": node.output_symbol,
                "observation_id": observation.observation_id,
                "observation_index": observation_index,
                "operator_id": (
                    observation.call.arguments.get("operator")
                    if node.node_kind == "calculation"
                    else None
                ),
            }
            matched_observation_ids.append(observation.observation_id)
            break

    resolved, ambiguous = _resolved_variables(variables, observations)
    ready_payloads = []
    unresolved_symbols: set[str] = set(ambiguous)
    for node in _ready_nodes(nodes, completed):
        arguments, unresolved = _node_arguments(node, resolved, completed)
        unresolved_symbols.update(unresolved)
        ready_payloads.append(
            _ready_node_payload(
                node,
                arguments=arguments,
                unresolved_symbols=tuple(sorted(unresolved)),
            )
        )

    required = set(stop_contract.required_node_ids)
    required_complete = required <= set(completed)
    terminal = completed.get(stop_contract.terminal_node_id)
    terminal_complete = terminal is not None
    terminal_ref = str(terminal["operation_ref"]) if terminal else None
    terminal_index = int(terminal["observation_index"]) if terminal else None
    verification_index = _postterminal_verification_index(
        observations,
        terminal_operation_ref=terminal_ref,
        terminal_observation_index=terminal_index,
        target=verification_target,
    )
    verification_complete = verification_index is not None
    postcompletion_ids = (
        tuple(item.observation_id for item in observations[verification_index + 1 :])
        if verification_index is not None
        else ()
    )
    postcompletion_violation = bool(postcompletion_ids)
    stop_ready = bool(
        required_complete
        and terminal_complete
        and verification_complete
        and not postcompletion_violation
    )
    return {
        "contract_version": contract.schema_version,
        "contract_view_id": contract.view_id,
        "stop_readiness_contract_id": stop_contract.contract_id,
        "completion_rule": contract.completion_rule,
        "acquisition_path_policy": contract.acquisition_path_policy,
        "completed_node_ids": tuple(sorted(completed)),
        "completed_node_operation_refs": {
            key: str(value["operation_ref"]) for key, value in sorted(completed.items())
        },
        "remaining_node_ids": tuple(sorted(required - set(completed))),
        "matched_observation_ids": tuple(matched_observation_ids),
        "ready_nodes": tuple(ready_payloads),
        "unresolved_symbols": tuple(sorted(unresolved_symbols)),
        "unresolved_variable_requirements": tuple(
            variables[symbol].model_dump(mode="json")
            for symbol in sorted(unresolved_symbols)
            if symbol in variables
        ),
        "next_required_step": ready_payloads[0] if len(ready_payloads) == 1 else None,
        "all_steps_completed": required_complete,
        "terminal_node_id": stop_contract.terminal_node_id,
        "terminal_node_completed": terminal_complete,
        "terminal_operation_ref": terminal_ref,
        "terminal_verification_target": (
            verification_target.model_dump(mode="json") if verification_target is not None else None
        ),
        "verification_after_terminal_completed": verification_complete,
        "verification_observation_index": verification_index,
        "postcompletion_violation": postcompletion_violation,
        "postcompletion_observation_ids": postcompletion_ids,
        "stop_ready": stop_ready,
        "final_answer_allowed": stop_ready,
        "required_action": _required_action(
            required_complete=required_complete,
            terminal_complete=terminal_complete,
            verification_complete=verification_complete,
            postcompletion_violation=postcompletion_violation,
            ready_payloads=ready_payloads,
        ),
    }


def model_visible_public_operation_progress(
    task: TaskPublicSpec,
    observations: tuple[AgentToolObservation, ...],
) -> dict[str, Any] | None:
    """Project semantic progress without supplying the next tool invocation."""

    progress = public_operation_progress(task, observations)
    if progress is None:
        return None
    ready_nodes = tuple(_semantic_ready_node(item) for item in progress["ready_nodes"])
    return {
        **progress,
        "ready_nodes": ready_nodes,
        "next_required_step": ready_nodes[0] if len(ready_nodes) == 1 else None,
        "action_binding_fields_exposed": False,
    }


def public_operation_step_rejection(
    task: TaskPublicSpec,
    observations: tuple[AgentToolObservation, ...],
    call: AgentToolCall,
) -> AgentToolResult | None:
    loaded = _load_contracts(task)
    if loaded is None:
        return None
    contract, _, _, _ = loaded
    if call.tool_id not in {item.tool_id for item in contract.nodes}:
        return None
    progress = public_operation_progress(task, observations)
    if progress is None:
        return None
    if progress["all_steps_completed"]:
        return AgentToolResult(
            status="failed",
            result={},
            error_code="public_operation_contract_complete",
            error_message="Every required public Operation node is already complete.",
        )
    ready_by_id = {item.node_id: item for item in contract.nodes}
    for payload in progress["ready_nodes"]:
        node = ready_by_id[str(payload["node_id"])]
        if payload["unresolved_symbols"]:
            continue
        arguments = payload.get("expected_arguments") or payload.get("argument_contract")
        if isinstance(arguments, Mapping) and _call_matches_ready_payload(call, node, arguments):
            return None
    unresolved = tuple(progress["unresolved_symbols"])
    if unresolved:
        return AgentToolResult(
            status="failed",
            result={
                "retry_contract": {
                    "policy": PREREQUISITE_ACTION_REQUIRED_POLICY,
                    "maximum_identical_replays": 0,
                    "required_prerequisite_action": {
                        "action": "select_missing_public_variables",
                        "unresolved_symbols": unresolved,
                    },
                }
            },
            error_code="public_operation_input_not_selected",
            error_message=(
                "Resolve every public input role before executing a ready Operation node."
            ),
        )
    ready = tuple(progress["ready_nodes"])
    return AgentToolResult(
        status="failed",
        result={
            "retry_contract": {
                "policy": ARGUMENT_PATCH_REQUIRED_POLICY,
                "maximum_identical_replays": 0,
                "suggested_argument_patch": {
                    "rule": "match one ready semantic node without changing its public inputs",
                    "ready_nodes": ready,
                },
            }
        },
        error_code="public_operation_node_contract",
        error_message="The tool call does not satisfy any currently ready public Operation node.",
    )


def public_postcompletion_action_rejection(
    task: TaskPublicSpec,
    observations: tuple[AgentToolObservation, ...],
    call: AgentToolCall,
) -> AgentToolResult | None:
    progress = public_operation_progress(task, observations)
    if progress is None or not progress["stop_ready"]:
        return None
    return AgentToolResult(
        status="failed",
        result={
            "completion_state": {
                "stop_ready": True,
                "terminal_operation_ref": progress["terminal_operation_ref"],
            }
        },
        error_code="redundant_action_after_public_operation_completion",
        error_message=(
            "The public Program is complete and verified; stop now without another tool call."
        ),
    )


def public_terminal_verification_rejection(
    task: TaskPublicSpec,
    observations: tuple[AgentToolObservation, ...],
    call: AgentToolCall,
) -> AgentToolResult | None:
    loaded = _load_contracts(task)
    if loaded is None:
        return None
    _, _, _, target = loaded
    if target is None or call.tool_id != target.verification_tool_id:
        return None
    progress = public_operation_progress(task, observations)
    if progress is None:
        raise ValueError("terminal verification lost the public Operation contract")
    terminal_ref = progress["terminal_operation_ref"]
    if not isinstance(terminal_ref, str) or not terminal_ref:
        return _terminal_verification_failure(
            "terminal_verification_before_terminal",
            "complete_terminal_operation_before_verification",
            progress,
        )
    claim = call.arguments.get(target.claim_argument_field)
    if not isinstance(claim, Mapping) or target.terminal_reference_field not in claim:
        return _terminal_verification_failure(
            "terminal_verification_reference_missing",
            "bind_verification_to_terminal_operation_reference",
            progress,
        )
    if claim.get(target.terminal_reference_field) != terminal_ref:
        return _terminal_verification_failure(
            "terminal_verification_reference_wrong",
            "bind_verification_to_observed_terminal_operation_reference",
            progress,
        )
    if set(claim) != set(target.required_claim_fields):
        return _terminal_verification_failure(
            "terminal_verification_extra_claim_fields",
            "use_registered_terminal_verification_claim_schema",
            progress,
        )
    return None


def public_action_neutral_repair_result(
    task: TaskPublicSpec,
    observations: tuple[AgentToolObservation, ...],
    call: AgentToolCall,
    result: AgentToolResult,
) -> AgentToolResult:
    loaded = _load_contracts(task)
    if loaded is None or loaded[2] is None or result.status != "failed":
        return result
    progress = public_operation_progress(task, observations)
    unresolved_variables: tuple[str, ...] = ()
    requirements: tuple[str, ...] = ("satisfy_public_tool_contract",)
    if progress is not None:
        unresolved_variables = tuple(str(item) for item in progress["unresolved_symbols"])
        ready = tuple(
            f"{item['node_id']}:{item['semantic_role']}"
            for item in progress["ready_nodes"]
            if isinstance(item, Mapping)
        )
        if ready:
            requirements = ready
        elif (
            progress["terminal_node_completed"]
            and not progress["verification_after_terminal_completed"]
        ):
            requirements = ("verify_terminal_operation_reference",)
        elif progress["postcompletion_violation"]:
            requirements = ("trajectory_invalid_after_postcompletion_action",)
    return AgentToolResult(
        status="failed",
        result={
            "retry_contract": {
                "policy": "model_owned_semantic_repair_required",
                "maximum_identical_replays": 0,
                "unresolved_semantic_requirements": requirements,
                "unresolved_public_variables": unresolved_variables,
                "model_decision_required": True,
            }
        },
        evidence_ids=result.evidence_ids,
        provenance_hashes=result.provenance_hashes,
        host_events=result.host_events,
        error_code=result.error_code,
        error_message=(
            "The attempted public action failed. Use the typed error category, unresolved "
            "public semantics, and prior public observations to choose a different repair."
        ),
    )


def public_action_neutral_repair_context(
    task: TaskPublicSpec,
    observations: tuple[AgentToolObservation, ...],
) -> dict[str, Any] | None:
    loaded = _load_contracts(task)
    if loaded is None or loaded[2] is None:
        return None
    if not observations or observations[-1].status != "failed":
        return None
    failed = observations[-1]
    retry = failed.result.get("retry_contract")
    if not isinstance(retry, Mapping):
        retry = {}
    return {
        "error_category": failed.error_code,
        "failed_tool_id": failed.call.tool_id,
        "identical_arguments_forbidden": True,
        "unresolved_public_variables": tuple(
            str(item) for item in retry.get("unresolved_public_variables") or ()
        ),
        "unresolved_semantic_requirements": tuple(
            str(item) for item in retry.get("unresolved_semantic_requirements") or ()
        ),
    }


def public_stop_readiness_payload(
    task: TaskPublicSpec,
    observations: tuple[AgentToolObservation, ...],
) -> dict[str, Any] | None:
    loaded = _load_contracts(task)
    if loaded is None:
        return None
    _, stop_contract, _, verification_target = loaded
    progress = public_operation_progress(task, observations)
    if progress is None:
        raise ValueError("public Operation progress unexpectedly disappeared")
    return {
        "operation_contract_view_id": progress["contract_view_id"],
        "required_node_ids": stop_contract.required_node_ids,
        "completed_node_ids": progress["completed_node_ids"],
        "terminal_node_completed": progress["terminal_node_completed"],
        "verification_after_terminal_completed": progress["verification_after_terminal_completed"],
        "terminal_verification_target_view_id": (
            verification_target.view_id if verification_target is not None else None
        ),
        "postcompletion_violation": progress["postcompletion_violation"],
        "stop_ready": progress["stop_ready"],
        "final_answer_allowed": progress["final_answer_allowed"],
    }


def _load_contracts(
    task: TaskPublicSpec,
) -> (
    tuple[
        PublicOperationContractView,
        PublicStopReadinessView,
        PublicActionNeutralRepairView | None,
        PublicTerminalVerificationTargetView | None,
    ]
    | None
):
    guidance = task.metadata.get("agent_contract_guidance")
    if not isinstance(guidance, Mapping):
        return None
    raw_operation = guidance.get("public_operation_execution_contract")
    raw_stop = guidance.get("public_stop_readiness_contract")
    raw_repair = guidance.get("public_action_neutral_repair_contract")
    raw_target = guidance.get("public_terminal_verification_target")
    if raw_operation is None and raw_stop is None:
        return None
    if not isinstance(raw_operation, Mapping) or not isinstance(raw_stop, Mapping):
        raise ValueError("public Operation and stop-readiness contracts must both be objects")
    operation = PublicOperationContractView.model_validate(raw_operation)
    stop_payload = dict(raw_stop)
    stop_payload.pop("semantic_source_id", None)
    stop = PublicStopReadinessView.model_validate(stop_payload)
    if stop.required_node_ids != tuple(sorted(item.node_id for item in operation.nodes)):
        raise ValueError("public stop contract does not require every Operation node")
    if stop.terminal_node_id != operation.terminal_node_id:
        raise ValueError("public stop and Operation terminal nodes differ")
    if (raw_repair is None) != (raw_target is None):
        raise ValueError("repair and terminal verification contracts must be jointly present")
    if raw_repair is None:
        if stop.terminal_verification_target_id is not None:
            raise ValueError("legacy public task unexpectedly binds a verification target")
        return operation, stop, None, None
    if not isinstance(raw_repair, Mapping) or not isinstance(raw_target, Mapping):
        raise ValueError("repair and terminal verification contracts must be objects")
    repair = PublicActionNeutralRepairView.model_validate(raw_repair)
    target = PublicTerminalVerificationTargetView.model_validate(raw_target)
    if repair.operation_contract_id != operation.view_id and (
        repair.operation_contract_id
        != task.metadata.get("executable_support_bindings", {}).get("operation_contract_id")
    ):
        raise ValueError("repair view is detached from public Operation execution")
    if target.operation_contract_id != task.metadata.get("executable_support_bindings", {}).get(
        "operation_contract_id"
    ):
        raise ValueError("terminal verification target is detached from Operation execution")
    bindings = task.metadata.get("executable_support_bindings")
    if not isinstance(bindings, Mapping):
        raise ValueError("authority-preserving task lacks public binding identities")
    if repair.contract_id != bindings.get("action_neutral_repair_contract_id"):
        raise ValueError("repair view identity differs from TaskPackage binding")
    if stop.terminal_verification_target_id != bindings.get("terminal_verification_target_id"):
        raise ValueError("stop readiness differs from terminal verification binding")
    return operation, stop, repair, target


def _semantic_ready_node(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value[key]
        for key in (
            "node_id",
            "node_kind",
            "semantic_role",
            "dependency_node_ids",
            "unresolved_symbols",
        )
        if key in value
    }


def _resolved_variables(
    variables: dict[str, PublicOperationVariable],
    observations: tuple[AgentToolObservation, ...],
) -> tuple[dict[str, str], tuple[str, ...]]:
    resolved: dict[str, str] = {}
    ambiguous: list[str] = []
    for symbol, variable in variables.items():
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
            resolved[symbol] = next(iter(matches))
        elif len(matches) > 1:
            ambiguous.append(symbol)
    return resolved, tuple(sorted(ambiguous))


def _ready_nodes(
    nodes: dict[str, PublicOperationNode],
    completed: dict[str, dict[str, Any]],
) -> tuple[PublicOperationNode, ...]:
    return tuple(
        node
        for node in sorted(nodes.values(), key=lambda item: item.node_id)
        if node.node_id not in completed and set(node.dependency_node_ids) <= set(completed)
    )


def _node_arguments(
    node: PublicOperationNode,
    resolved_variables: dict[str, str],
    completed: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    operands: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for item in node.inputs:
        if item.source_symbol in resolved_variables:
            operands.append({"evidence_id": resolved_variables[item.source_symbol]})
        else:
            producer = next(
                (
                    value
                    for value in completed.values()
                    if value.get("output_symbol") == item.source_symbol
                ),
                None,
            )
            if producer is None:
                unresolved.append(item.source_symbol)
                continue
            operand = {"operation_ref": producer["operation_ref"]}
            if item.selector is not None:
                operand["selector"] = item.selector
            operands.append(operand)
    if unresolved:
        return None, tuple(sorted(set(unresolved)))
    if node.node_kind == "normalization":
        evidence_ids = [item["evidence_id"] for item in operands]
        return {
            "evidence_ids": evidence_ids,
            "target_definition": node.normalization_target,
        }, ()
    base = {"operands": operands, "parameters": node.parameters}
    if node.operator_choice_mode == "fixed_semantics":
        base["operator"] = node.allowed_operator_ids[0]
    return base, ()


def _ready_node_payload(
    node: PublicOperationNode,
    *,
    arguments: dict[str, Any] | None,
    unresolved_symbols: tuple[str, ...],
) -> dict[str, Any]:
    common = {
        "node_id": node.node_id,
        "node_kind": node.node_kind,
        "semantic_role": node.semantic_role,
        "tool_id": node.tool_id,
        "dependency_node_ids": node.dependency_node_ids,
        "unresolved_symbols": unresolved_symbols,
    }
    if arguments is None:
        return common
    if node.operator_choice_mode == "model_context_choice":
        return {
            **common,
            "allowed_operators": node.allowed_operator_ids,
            "operator_selection_rule": node.operator_selection_rule,
            "operator_output_schemas": node.operator_output_schemas,
            "required_output_schema": node.required_output_schema,
            "argument_contract": {
                **arguments,
                "operator": "choose_one_allowed_operator_from_public_context",
            },
        }
    return {**common, "expected_arguments": arguments}


def _observation_matches_node(
    observation: AgentToolObservation,
    node: PublicOperationNode,
    arguments: dict[str, Any],
) -> bool:
    if observation.call.tool_id != node.tool_id:
        return False
    return _call_matches_ready_payload(observation.call, node, arguments)


def _call_matches_ready_payload(
    call: AgentToolCall,
    node: PublicOperationNode,
    arguments: Mapping[str, Any],
) -> bool:
    observed = call.arguments
    if node.node_kind == "normalization":
        return observed == dict(arguments)
    if observed.get("operator") not in set(node.allowed_operator_ids):
        return False
    return observed.get("operands") == arguments.get("operands") and observed.get(
        "parameters"
    ) == arguments.get("parameters")


def _operation_ref(
    observation: AgentToolObservation,
    node: PublicOperationNode,
) -> str | None:
    value = (
        observation.result.get("normalized_operation_ref")
        if node.node_kind == "normalization"
        else _try_select(observation.result, ("result", "operation_ref"))
    )
    return value if isinstance(value, str) and value else None


def _postterminal_verification_index(
    observations: tuple[AgentToolObservation, ...],
    *,
    terminal_operation_ref: str | None,
    terminal_observation_index: int | None,
    target: PublicTerminalVerificationTargetView | None,
) -> int | None:
    if terminal_operation_ref is None or terminal_observation_index is None:
        return None
    for index, observation in enumerate(observations):
        if index <= terminal_observation_index:
            continue
        if _terminal_verification_observation_matches(
            observation,
            terminal_operation_ref=terminal_operation_ref,
            target=target,
        ):
            return index
    return None


def _terminal_verification_observation_matches(
    observation: AgentToolObservation,
    *,
    terminal_operation_ref: str,
    target: PublicTerminalVerificationTargetView | None,
) -> bool:
    if target is None:
        return bool(
            observation.status == "succeeded"
            and observation.call.tool_id == "cross_check_evidence"
            and observation.call.arguments.get("claim_or_result")
            == {"operation_ref": terminal_operation_ref}
            and observation.result.get("verified") is True
        )
    claim = observation.call.arguments.get(target.claim_argument_field)
    return bool(
        observation.status == "succeeded"
        and observation.call.tool_id == target.verification_tool_id
        and isinstance(claim, Mapping)
        and set(claim) == set(target.required_claim_fields)
        and claim.get(target.terminal_reference_field) == terminal_operation_ref
        and observation.result.get(target.verification_result_field)
        is target.verification_success_value
    )


def _terminal_verification_failure(
    error_code: str,
    semantic_requirement: str,
    progress: Mapping[str, Any],
) -> AgentToolResult:
    return AgentToolResult(
        status="failed",
        result={
            "retry_contract": {
                "policy": "model_owned_semantic_repair_required",
                "maximum_identical_replays": 0,
                "unresolved_semantic_requirements": (semantic_requirement,),
                "unresolved_public_variables": tuple(progress["unresolved_symbols"]),
                "model_decision_required": True,
            }
        },
        error_code=error_code,
        error_message=(
            "The public verification call does not satisfy the registered terminal target."
        ),
    )


def _required_action(
    *,
    required_complete: bool,
    terminal_complete: bool,
    verification_complete: bool,
    postcompletion_violation: bool,
    ready_payloads: list[dict[str, Any]],
) -> str:
    if postcompletion_violation:
        return "trajectory_invalid_due_to_postcompletion_action"
    if not required_complete or not terminal_complete:
        return (
            "resolve public inputs and complete one ready semantic node"
            if ready_payloads
            else "resolve missing public inputs before Program completion"
        )
    if not verification_complete:
        return "verify the terminal operation reference before stopping"
    return "emit the final answer now without another tool call"


def _try_select(value: object, selector: tuple[str, ...]) -> object | None:
    current = value
    for part in selector:
        if isinstance(current, Mapping):
            if part not in current:
                return None
            current = current[part]
        elif isinstance(current, (list, tuple)) and part.isdigit():
            index = int(part)
            if index >= len(current):
                return None
            current = current[index]
        else:
            return None
    return current
