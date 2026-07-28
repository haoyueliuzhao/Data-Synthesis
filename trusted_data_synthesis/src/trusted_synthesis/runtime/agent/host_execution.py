from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.operations.schema import OperationInput
from trusted_synthesis.core.task.schema import PlanningTrack, TaskPublicSpec
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import (
    AgentActionInput,
    AgentActionPlanContract,
    AgentExecutionStep,
    AgentExecutionTrace,
)


def execute_action_plan(
    task: TaskPublicSpec,
    retrieved: tuple[EvidenceItem, ...],
    plan: AgentActionPlanContract,
    registry: OperationRegistry,
) -> AgentExecutionTrace:
    """Execute model decisions while keeping observations and immutable IDs host-owned."""

    evidence_by_id = {item.evidence_id: item for item in retrieved}
    unknown_selected = set(plan.selected_evidence_ids) - set(evidence_by_id)
    if unknown_selected:
        raise ValueError(f"selected evidence was not retrieved: {sorted(unknown_selected)}")
    _validate_public_plan_shape(task, plan)

    outputs: dict[int, dict[str, Any]] = {}
    execution_ids: dict[int, str] = {}
    lineages: dict[int, tuple[str, ...]] = {}
    steps: list[AgentExecutionStep] = []
    for step_index, decision in enumerate(plan.executions, start=1):
        definition = registry.require(decision.operator_id)
        _validate_operator_access(task, definition.tool_capability)
        inputs = tuple(
            _resolve_input(item, evidence_by_id, outputs, execution_ids)
            for item in decision.inputs
        )
        lineage = _input_lineage(decision.inputs, lineages)
        evidence_lineage = tuple(evidence_by_id[item] for item in lineage)
        registry.validate_inputs(definition, inputs)
        registry.validate_compatibility(definition, evidence_lineage, decision.parameters)
        output = definition.executor.execute(inputs, decision.parameters)
        registry.validate_output(definition, output)
        execution_id = canonical_hash(
            {
                "task_id": task.task_id,
                "step_index": step_index,
                "operator_id": decision.operator_id,
                "inputs": decision.inputs,
                "parameters": decision.parameters,
                "output": output,
            },
            prefix="host_agent_execution:",
        )
        outputs[step_index] = output
        execution_ids[step_index] = execution_id
        lineages[step_index] = lineage
        planned_node_id = (
            task.program_skeleton.nodes[step_index - 1].public_node_id
            if task.program_skeleton is not None
            else None
        )
        steps.append(
            AgentExecutionStep(
                execution_id=execution_id,
                planned_node_id=planned_node_id,
                operator_id=decision.operator_id,
                tool_name=definition.tool_capability,
                input_refs=tuple(
                    _input_ref(item, execution_ids) for item in decision.inputs
                ),
                parameters=decision.parameters,
                evidence_ids=lineage,
                observation={"result": output},
                status="succeeded",
                rationale_summary=decision.rationale_summary,
            )
        )

    used_evidence_ids = tuple(
        dict.fromkeys(item for lineage in lineages.values() for item in lineage)
    )
    if set(used_evidence_ids) != set(plan.selected_evidence_ids):
        raise ValueError(
            "selected_evidence_ids must exactly equal evidence used by host executions"
        )
    return AgentExecutionTrace(
        steps=tuple(steps),
        output_execution_id=execution_ids[plan.output_step_index],
    )


def _validate_public_plan_shape(
    task: TaskPublicSpec,
    plan: AgentActionPlanContract,
) -> None:
    if plan.output_step_index != len(plan.executions):
        raise ValueError("the output step must be the final host execution")
    if task.planning_track != PlanningTrack.PLAN_GIVEN:
        return
    skeleton = task.program_skeleton
    if skeleton is None:
        raise ValueError("plan_given task is missing its public program skeleton")
    if len(plan.executions) != len(skeleton.nodes):
        raise ValueError("action decisions must cover every public program node")
    output_index = next(
        index
        for index, node in enumerate(skeleton.nodes, start=1)
        if node.public_node_id == skeleton.output_node_id
    )
    if plan.output_step_index != output_index:
        raise ValueError("action plan output does not match the public output node")
    node_positions = {
        node.public_node_id: index for index, node in enumerate(skeleton.nodes, start=1)
    }
    for index, (decision, node) in enumerate(
        zip(plan.executions, skeleton.nodes, strict=True),
        start=1,
    ):
        if decision.operator_id != node.operator_id:
            raise ValueError("action decisions must preserve public plan operators")
        if canonical_hash(
            decision.parameters,
            prefix="agent_execution_parameters:",
        ) != canonical_hash(node.parameters, prefix="agent_execution_parameters:"):
            raise ValueError("action decisions must preserve public plan parameters")
        if len(decision.inputs) != len(node.inputs):
            raise ValueError("action inputs must preserve public plan arity")
        for observed, expected in zip(decision.inputs, node.inputs, strict=True):
            expected_source = "evidence" if expected.kind.value == "evidence" else "step"
            if observed.source != expected_source:
                raise ValueError("action input kinds must preserve the public plan")
            if observed.selector != expected.selector:
                raise ValueError("action input selectors must preserve the public plan")
            if expected_source == "step":
                expected_step = node_positions.get(expected.role_id)
                if observed.step_index != expected_step or (expected_step or 0) >= index:
                    raise ValueError("action dependencies must preserve the public plan")


def _validate_operator_access(task: TaskPublicSpec, tool_capability: str | None) -> None:
    if tool_capability is not None and tool_capability not in set(task.allowed_tools):
        raise ValueError(f"operation requires a disallowed tool: {tool_capability}")


def _resolve_input(
    item: AgentActionInput,
    evidence_by_id: dict[str, EvidenceItem],
    outputs: dict[int, dict[str, Any]],
    execution_ids: dict[int, str],
) -> OperationInput:
    if item.source == "evidence":
        evidence_id = item.evidence_id or ""
        try:
            value: Any = evidence_by_id[evidence_id].payload
        except KeyError as exc:
            raise ValueError(f"action evidence input was not retrieved: {evidence_id}") from exc
        ref_id = evidence_id
    else:
        step_index = item.step_index or 0
        try:
            value = outputs[step_index]
            ref_id = f"execution:{execution_ids[step_index]}"
        except KeyError as exc:
            raise ValueError(f"action step input is unavailable: {step_index}") from exc
    if item.selector:
        value = _select_value(value, item.selector, ref_id)
    return OperationInput(ref_id=ref_id, value=value)


def _select_value(value: Any, selector: str, ref_id: str) -> Any:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python")
    current = value
    for segment in selector.split("."):
        if isinstance(current, BaseModel):
            current = current.model_dump(mode="python")
        if not isinstance(current, dict) or segment not in current:
            raise ValueError(f"input selector {selector!r} is invalid for {ref_id}")
        current = current[segment]
    return current


def _input_lineage(
    inputs: tuple[AgentActionInput, ...],
    lineages: dict[int, tuple[str, ...]],
) -> tuple[str, ...]:
    collected: list[str] = []
    for item in inputs:
        if item.source == "evidence":
            collected.append(item.evidence_id or "")
        else:
            collected.extend(lineages.get(item.step_index or 0, ()))
    return tuple(dict.fromkeys(item for item in collected if item))


def _input_ref(item: AgentActionInput, execution_ids: dict[int, str]) -> str:
    selector = f"#{item.selector}" if item.selector else ""
    if item.source == "evidence":
        return f"evidence:{item.evidence_id}{selector}"
    return f"execution:{execution_ids[item.step_index or 0]}{selector}"
