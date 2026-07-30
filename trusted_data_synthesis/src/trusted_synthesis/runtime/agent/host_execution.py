from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.operations.schema import OperationInput
from trusted_synthesis.core.task.schema import PlanningTrack, TaskPublicSpec, TaskRequirement
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import (
    AgentActionInput,
    AgentActionPlanContract,
    AgentAnswerDecisionContract,
    AgentCitation,
    AgentExecutionStep,
    AgentExecutionTrace,
    AgentFinalAnswer,
    AgentResponseContract,
    FailedActionPlan,
    HostExecutionFeedbackContract,
)

ActionFailureCategory = Literal[
    "interface_security",
    "semantic_action",
    "upstream_data",
    "infrastructure",
]


class ActionPlanExecutionError(ValueError):
    """A classified host failure with enough context for deterministic routing."""

    def __init__(
        self,
        message: str,
        *,
        category: ActionFailureCategory,
        error_code: str,
        step_index: int | None = None,
        operator_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.error_code = error_code
        self.step_index = step_index
        self.operator_id = operator_id


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
        raise ActionPlanExecutionError(
            f"selected evidence was not retrieved: {sorted(unknown_selected)}",
            category="interface_security",
            error_code="unknown_evidence_id",
        )
    for step_index, decision in enumerate(plan.executions, start=1):
        try:
            registry.require(decision.operator_id)
        except ValueError as exc:
            raise ActionPlanExecutionError(
                str(exc),
                category="interface_security",
                error_code="unregistered_operator",
                step_index=step_index,
                operator_id=decision.operator_id,
            ) from exc
    _validate_public_plan_shape(task, plan)

    outputs: dict[int, dict[str, Any]] = {}
    execution_ids: dict[int, str] = {}
    lineages: dict[int, tuple[str, ...]] = {}
    steps: list[AgentExecutionStep] = []
    for step_index, decision in enumerate(plan.executions, start=1):
        try:
            definition = registry.require(decision.operator_id)
        except ValueError as exc:
            raise ActionPlanExecutionError(
                str(exc),
                category="interface_security",
                error_code="unregistered_operator",
                step_index=step_index,
                operator_id=decision.operator_id,
            ) from exc
        _validate_operator_access(
            task,
            definition.tool_capability,
            step_index=step_index,
            operator_id=decision.operator_id,
        )
        inputs = tuple(
            _resolve_input(
                item,
                evidence_by_id,
                outputs,
                execution_ids,
                step_index=step_index,
                operator_id=decision.operator_id,
            )
            for item in decision.inputs
        )
        lineage = _input_lineage(decision.inputs, lineages)
        evidence_lineage = tuple(evidence_by_id[item] for item in lineage)
        try:
            registry.validate_inputs(definition, inputs)
        except ValueError as exc:
            raise ActionPlanExecutionError(
                str(exc),
                category="semantic_action",
                error_code="operator_input_contract_failed",
                step_index=step_index,
                operator_id=decision.operator_id,
            ) from exc
        try:
            registry.validate_compatibility(
                definition,
                evidence_lineage,
                decision.parameters,
            )
        except ValueError as exc:
            raise ActionPlanExecutionError(
                str(exc),
                category="semantic_action",
                error_code="semantic_compatibility_failed",
                step_index=step_index,
                operator_id=decision.operator_id,
            ) from exc
        try:
            output = definition.executor.execute(inputs, decision.parameters)
        except Exception as exc:
            raise ActionPlanExecutionError(
                str(exc) or type(exc).__name__,
                category="semantic_action",
                error_code="operator_execution_failed",
                step_index=step_index,
                operator_id=decision.operator_id,
            ) from exc
        try:
            registry.validate_output(definition, output)
        except ValueError as exc:
            raise ActionPlanExecutionError(
                str(exc),
                category="semantic_action",
                error_code="operator_output_contract_failed",
                step_index=step_index,
                operator_id=decision.operator_id,
            ) from exc
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
        direct_evidence_ids = tuple(
            dict.fromkeys(
                item.evidence_id
                for item in decision.inputs
                if item.source == "evidence" and item.evidence_id is not None
            )
        )
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
                # Step grounding is intentionally direct. The complete transitive
                # answer lineage is reconstructed and frozen in program_execution.
                evidence_ids=direct_evidence_ids,
                observation={"result": output},
                status="succeeded",
                rationale_summary=decision.rationale_summary,
            )
        )

    used_evidence_ids = tuple(
        dict.fromkeys(item for lineage in lineages.values() for item in lineage)
    )
    if set(used_evidence_ids) != set(plan.selected_evidence_ids):
        raise ActionPlanExecutionError(
            "selected_evidence_ids must exactly equal evidence used by host executions",
            category="semantic_action",
            error_code="evidence_lineage_mismatch",
        )
    return AgentExecutionTrace(
        steps=tuple(steps),
        output_execution_id=execution_ids[plan.output_step_index],
    )


def make_failed_action_plan(
    task: TaskPublicSpec,
    plan: AgentActionPlanContract,
    error: ActionPlanExecutionError,
    *,
    attempt_number: int,
) -> FailedActionPlan:
    decision = (
        plan.executions[error.step_index - 1]
        if error.step_index is not None and error.step_index <= len(plan.executions)
        else None
    )
    return FailedActionPlan(
        task_id=task.task_id,
        failure_category=error.category,
        error_code=error.error_code,
        error_message=str(error),
        failed_step_index=error.step_index,
        operator_id=error.operator_id or (decision.operator_id if decision is not None else None),
        selected_evidence_ids=plan.selected_evidence_ids,
        step_evidence_ids=tuple(
            item.evidence_id or ""
            for item in (decision.inputs if decision is not None else ())
            if item.source == "evidence" and item.evidence_id
        ),
        parameters=dict(decision.parameters) if decision is not None else {},
        action_plan=plan,
        attempt_number=attempt_number,
    )


def make_host_execution_feedback(
    execution_trace: AgentExecutionTrace,
) -> HostExecutionFeedbackContract:
    output_step = next(
        item
        for item in execution_trace.steps
        if item.execution_id == execution_trace.output_execution_id
    )
    return HostExecutionFeedbackContract(
        execution_trace=execution_trace,
        raw_output_result=output_step.observation["result"],
        output_result=model_visible_execution_result(
            execution_trace,
            output_step.observation["result"],
        ),
    )


def model_visible_execution_result(
    execution_trace: AgentExecutionTrace,
    value: Any,
) -> Any:
    """Replace Host execution references with stable public step identities."""

    public_refs = {
        item.execution_id: item.planned_node_id or f"step_{index}"
        for index, item in enumerate(execution_trace.steps, start=1)
    }
    return _replace_execution_refs(value, public_refs)


def assemble_host_response(
    task: TaskPublicSpec,
    retrieved: tuple[EvidenceItem, ...],
    action_plan: AgentActionPlanContract,
    execution_trace: AgentExecutionTrace,
    answer: AgentAnswerDecisionContract,
) -> AgentResponseContract:
    """Assemble the legacy audit envelope from model decisions and host-owned state."""

    if set(answer.cited_evidence_ids) != set(action_plan.selected_evidence_ids):
        raise ValueError("answer citations must exactly cover selected evidence")
    retrieved_by_id = {item.evidence_id: item for item in retrieved}
    try:
        citations = tuple(
            AgentCitation(
                evidence_id=evidence_id,
                source_id=retrieved_by_id[evidence_id].source.source_id,
                source_locator=retrieved_by_id[evidence_id].source_locator.model_dump(
                    mode="json",
                    exclude_none=True,
                ),
            )
            for evidence_id in answer.cited_evidence_ids
        )
    except KeyError as exc:
        raise ValueError(f"answer cited evidence was not retrieved: {exc.args[0]}") from exc
    output_execution = next(
        item
        for item in execution_trace.steps
        if item.execution_id == execution_trace.output_execution_id
    )
    verification_result = (
        output_execution.observation["result"]
        if TaskRequirement.VERIFY_RESULT in task.requirements
        else None
    )
    return AgentResponseContract(
        plan_summary=action_plan.plan_summary,
        selected_evidence_ids=action_plan.selected_evidence_ids,
        execution_trace=execution_trace,
        verification_result=verification_result,
        final_answer=AgentFinalAnswer(
            result=answer.result,
            citations=citations,
            status=answer.status,
            claims=answer.claims,
        ),
    )


def _validate_public_plan_shape(
    task: TaskPublicSpec,
    plan: AgentActionPlanContract,
) -> None:
    if plan.output_step_index != len(plan.executions):
        raise ActionPlanExecutionError(
            "the output step must be the final host execution",
            category="semantic_action",
            error_code="output_step_not_final",
        )
    if task.planning_track != PlanningTrack.PLAN_GIVEN:
        return
    skeleton = task.program_skeleton
    if skeleton is None:
        raise ActionPlanExecutionError(
            "plan_given task is missing its public program skeleton",
            category="upstream_data",
            error_code="missing_public_program_skeleton",
        )
    if len(plan.executions) != len(skeleton.nodes):
        raise ActionPlanExecutionError(
            "action decisions must cover every public program node",
            category="semantic_action",
            error_code="program_node_coverage_failed",
        )
    output_index = next(
        index
        for index, node in enumerate(skeleton.nodes, start=1)
        if node.public_node_id == skeleton.output_node_id
    )
    if plan.output_step_index != output_index:
        raise ActionPlanExecutionError(
            "action plan output does not match the public output node",
            category="semantic_action",
            error_code="public_output_node_mismatch",
        )
    node_positions = {
        node.public_node_id: index for index, node in enumerate(skeleton.nodes, start=1)
    }
    for index, (decision, node) in enumerate(
        zip(plan.executions, skeleton.nodes, strict=True),
        start=1,
    ):
        if decision.operator_id != node.operator_id:
            raise ActionPlanExecutionError(
                "action decisions must preserve public plan operators",
                category="semantic_action",
                error_code="public_operator_mismatch",
                step_index=index,
                operator_id=decision.operator_id,
            )
        if canonical_hash(
            decision.parameters,
            prefix="agent_execution_parameters:",
        ) != canonical_hash(node.parameters, prefix="agent_execution_parameters:"):
            raise ActionPlanExecutionError(
                "action decisions must preserve public plan parameters",
                category="semantic_action",
                error_code="public_parameter_mismatch",
                step_index=index,
                operator_id=decision.operator_id,
            )
        if len(decision.inputs) != len(node.inputs):
            raise ActionPlanExecutionError(
                "action inputs must preserve public plan arity",
                category="semantic_action",
                error_code="public_input_arity_mismatch",
                step_index=index,
                operator_id=decision.operator_id,
            )
        for observed, expected in zip(decision.inputs, node.inputs, strict=True):
            expected_source = "evidence" if expected.kind.value == "evidence" else "step"
            if observed.source != expected_source:
                raise ActionPlanExecutionError(
                    "action input kinds must preserve the public plan",
                    category="semantic_action",
                    error_code="public_input_kind_mismatch",
                    step_index=index,
                    operator_id=decision.operator_id,
                )
            if observed.selector != expected.selector:
                raise ActionPlanExecutionError(
                    "action input selectors must preserve the public plan",
                    category="semantic_action",
                    error_code="public_selector_mismatch",
                    step_index=index,
                    operator_id=decision.operator_id,
                )
            if expected_source == "step":
                expected_step = node_positions.get(expected.role_id)
                if observed.step_index != expected_step or (expected_step or 0) >= index:
                    raise ActionPlanExecutionError(
                        "action dependencies must preserve the public plan",
                        category="semantic_action",
                        error_code="public_dependency_mismatch",
                        step_index=index,
                        operator_id=decision.operator_id,
                    )


def _replace_execution_refs(value: Any, public_refs: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {
            key: _replace_execution_refs(item, public_refs)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_replace_execution_refs(item, public_refs) for item in value]
    if isinstance(value, tuple):
        return tuple(_replace_execution_refs(item, public_refs) for item in value)
    if not isinstance(value, str) or not value.startswith("execution:"):
        return value
    execution_id, separator, selector = value.removeprefix("execution:").partition("#")
    public_ref = public_refs.get(execution_id, value)
    return f"{public_ref}#{selector}" if separator and public_ref != value else public_ref


def _validate_operator_access(
    task: TaskPublicSpec,
    tool_capability: str | None,
    *,
    step_index: int,
    operator_id: str,
) -> None:
    if tool_capability is not None and tool_capability not in set(task.allowed_tools):
        raise ActionPlanExecutionError(
            f"operation requires a disallowed tool: {tool_capability}",
            category="interface_security",
            error_code="disallowed_tool",
            step_index=step_index,
            operator_id=operator_id,
        )


def _resolve_input(
    item: AgentActionInput,
    evidence_by_id: dict[str, EvidenceItem],
    outputs: dict[int, dict[str, Any]],
    execution_ids: dict[int, str],
    *,
    step_index: int,
    operator_id: str,
) -> OperationInput:
    if item.source == "evidence":
        evidence_id = item.evidence_id or ""
        try:
            value: Any = evidence_by_id[evidence_id].payload
        except KeyError as exc:
            raise ActionPlanExecutionError(
                f"action evidence input was not retrieved: {evidence_id}",
                category="interface_security",
                error_code="unknown_evidence_input",
                step_index=step_index,
                operator_id=operator_id,
            ) from exc
        ref_id = evidence_id
    else:
        dependency_step_index = item.step_index or 0
        try:
            value = outputs[dependency_step_index]
            ref_id = f"execution:{execution_ids[dependency_step_index]}"
        except KeyError as exc:
            raise ActionPlanExecutionError(
                f"action step input is unavailable: {item.step_index}",
                category="semantic_action",
                error_code="unavailable_step_dependency",
                step_index=step_index,
                operator_id=operator_id,
            ) from exc
    if item.selector:
        try:
            value = _select_value(value, item.selector, ref_id)
        except ValueError as exc:
            raise ActionPlanExecutionError(
                str(exc),
                category="semantic_action",
                error_code="invalid_input_selector",
                step_index=step_index,
                operator_id=operator_id,
            ) from exc
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
