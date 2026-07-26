from __future__ import annotations

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.program import TaskProgramExecutor
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.task.program import (
    InputRefKind,
    OperationNode,
    ProgramInputRef,
    make_program,
)
from trusted_synthesis.core.task.schema import TaskPublicSpec, TaskRequirement
from trusted_synthesis.core.trajectory.schema import (
    ActionType,
    StepStatus,
    Trajectory,
    TrajectoryStep,
    WorkflowKind,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import EvidenceToolRuntime

CONTRACT_CANDIDATE_VERSION = "cross_domain_plan_given_candidate.v1"


class PlanGivenContractCandidate:
    """Public-only candidate used to exercise non-finance operation contracts."""

    def __init__(self, registry: OperationRegistry) -> None:
        self._registry = registry

    def generate(self, task: TaskPublicSpec, runtime: EvidenceToolRuntime) -> Trajectory:
        skeleton = task.program_skeleton
        if skeleton is None:
            raise ValueError("contract candidate requires a plan-given public skeleton")
        retrieved = runtime.search(task.retrieval_scope)
        eligible = _publicly_eligible(task, retrieved)
        role_bindings = _bind_evidence_roles(task, eligible)
        program = _bind_program(task, role_bindings, self._registry)
        evidence_by_id = {item.evidence_id: item for item in eligible}
        execution = TaskProgramExecutor(self._registry).execute(program, evidence_by_id)
        selected = tuple({item.evidence_id: item for item in role_bindings.values()}.values())
        citations = [
            {
                "evidence_id": item.evidence_id,
                "source_id": item.source.source_id,
                "source_locator": item.source_locator.model_dump(mode="json", exclude_none=True),
            }
            for item in selected
        ]
        selected_ids = tuple(item.evidence_id for item in selected)
        steps = [
            TrajectoryStep(
                step_index=1,
                action=ActionType.PLAN,
                observation={
                    "planning_track": task.planning_track.value,
                    "public_skeleton_version": skeleton.skeleton_version,
                },
                rationale_summary="Bind public evidence roles before executing the declared DAG.",
                status=StepStatus.SUCCEEDED,
            ),
            TrajectoryStep(
                step_index=2,
                action=ActionType.SEARCH,
                tool_name="evidence.search",
                tool_input=task.retrieval_scope,
                observation={"matched_count": len(retrieved)},
                evidence_ids=tuple(item.evidence_id for item in retrieved),
                rationale_summary="Search the bounded corpus using public semantic constraints.",
                status=StepStatus.SUCCEEDED,
            ),
            TrajectoryStep(
                step_index=3,
                action=ActionType.SELECT_EVIDENCE,
                observation={"selected_count": len(eligible)},
                evidence_ids=selected_ids,
                rationale_summary="Select only evidence satisfying the public role constraints.",
                status=StepStatus.SUCCEEDED,
            ),
        ]
        for node in program.nodes:
            definition = self._registry.require(node.operator_id)
            direct_evidence_ids = tuple(
                ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.EVIDENCE
            )
            steps.append(
                TrajectoryStep(
                    step_index=len(steps) + 1,
                    action=ActionType(definition.action_type),
                    tool_name=definition.tool_capability,
                    observation={"result": execution.node_outputs[node.node_id]},
                    evidence_ids=direct_evidence_ids,
                    program_node_id=node.node_id,
                    operator_id=node.operator_id,
                    input_refs=tuple(_program_ref(ref) for ref in node.input_refs),
                    output_ref=f"operation:{node.node_id}",
                    rationale_summary="Execute one public program node with its bound inputs.",
                    status=StepStatus.SUCCEEDED,
                )
            )
        if TaskRequirement.VERIFY_RESULT in task.requirements:
            output_ref = f"operation:{program.output_node_id}"
            steps.append(
                TrajectoryStep(
                    step_index=len(steps) + 1,
                    action=ActionType.VERIFY,
                    observation={
                        "verified_output_ref": output_ref,
                        "verified_result": execution.final_output,
                    },
                    evidence_ids=selected_ids,
                    program_node_id=program.output_node_id,
                    input_refs=(output_ref,),
                    rationale_summary="Verify the final structured output against its schema.",
                    status=StepStatus.SUCCEEDED,
                )
            )
        final_answer = {"result": execution.final_output, "citations": citations}
        steps.append(
            TrajectoryStep(
                step_index=len(steps) + 1,
                action=ActionType.ANSWER,
                observation=final_answer,
                evidence_ids=selected_ids,
                rationale_summary="Return the grounded structured result with source citations.",
                status=StepStatus.SUCCEEDED,
            )
        )
        return Trajectory(
            trajectory_id=canonical_hash(
                {
                    "task_id": task.task_id,
                    "selected_ids": selected_ids,
                    "execution": execution.model_dump(mode="json"),
                    "version": CONTRACT_CANDIDATE_VERSION,
                },
                prefix="cross_domain_candidate:",
            ),
            task_id=task.task_id,
            workflow_kind=WorkflowKind.CANDIDATE,
            steps=tuple(steps),
            final_answer=final_answer,
            generator_version=CONTRACT_CANDIDATE_VERSION,
        )


def _bind_program(task, role_bindings, registry: OperationRegistry):
    assert task.program_skeleton is not None
    nodes = []
    for public_node in task.program_skeleton.nodes:
        inputs = []
        for item in public_node.inputs:
            ref_id = item.role_id
            if item.kind == InputRefKind.EVIDENCE:
                ref_id = role_bindings[item.role_id].evidence_id
            inputs.append(ProgramInputRef(kind=item.kind, ref_id=ref_id, selector=item.selector))
        definition = registry.require(public_node.operator_id)
        nodes.append(
            OperationNode(
                node_id=public_node.public_node_id,
                operator_id=public_node.operator_id,
                input_refs=tuple(inputs),
                parameters=public_node.parameters,
                output_schema=public_node.output_schema,
                verifier_id=definition.verifier_id,
                dependencies=public_node.dependencies,
            )
        )
    return make_program(tuple(nodes), task.program_skeleton.output_node_id)


def _bind_evidence_roles(
    task: TaskPublicSpec,
    evidence: tuple[EvidenceItem, ...],
) -> dict[str, EvidenceItem]:
    assert task.program_skeleton is not None
    role_constraints: dict[str, dict[str, object]] = {}
    for node in task.program_skeleton.nodes:
        for item in node.inputs:
            if item.kind != InputRefKind.EVIDENCE:
                continue
            existing = role_constraints.setdefault(item.role_id, item.semantic_constraints)
            if existing != item.semantic_constraints:
                raise ValueError(f"evidence role has conflicting constraints: {item.role_id}")
    bindings: dict[str, EvidenceItem] = {}
    used_evidence_ids: set[str] = set()
    for role_id, constraints in role_constraints.items():
        matches = tuple(
            item
            for item in evidence
            if item.evidence_id not in used_evidence_ids
            and _matches_role_constraints(item, constraints)
        )
        if len(matches) != 1:
            raise ValueError(
                "public role constraints must identify exactly one unused item: "
                f"role={role_id}, matched={len(matches)}"
            )
        bindings[role_id] = matches[0]
        used_evidence_ids.add(matches[0].evidence_id)
    if len(used_evidence_ids) != len(evidence):
        raise ValueError("public role constraints left eligible evidence unbound")
    return bindings


def _publicly_eligible(
    task: TaskPublicSpec,
    evidence: tuple[EvidenceItem, ...],
) -> tuple[EvidenceItem, ...]:
    scope = task.retrieval_scope
    semantic = scope.get("semantic_constraints") or {}
    partial = scope.get("partial_constraints") or {}
    definition_ids = set(semantic.get("definition_ids") or ())
    scope_ids = set(semantic.get("scope_ids") or ())
    temporal_labels = set(semantic.get("temporal_labels") or ())
    authorities = set(scope.get("source_authorities") or semantic.get("source_authorities") or ())
    partial_predicate = partial.get("predicate")
    partial_definition = partial.get("definition_id")
    return tuple(
        item
        for item in evidence
        if (not definition_ids or item.definition.definition_id in definition_ids)
        and (not scope_ids or (item.scope and item.scope.scope_id in scope_ids))
        and (not temporal_labels or item.temporal_context.label in temporal_labels)
        and (not authorities or item.source.authority.value in authorities)
        and (not partial_predicate or item.predicate == partial_predicate)
        and (not partial_definition or item.definition.definition_id == partial_definition)
    )


def _matches_role_constraints(
    item: EvidenceItem,
    constraints: dict[str, object],
) -> bool:
    actual = {
        "subject_id": item.subject.subject_id,
        "predicate": item.predicate,
        "temporal_label": item.temporal_context.label,
        "time_basis": item.temporal_context.basis,
        "frequency": item.temporal_context.frequency,
        "definition_id": item.definition.definition_id,
        "scope_type": item.scope.scope_type if item.scope is not None else None,
        "scope_id": item.scope.scope_id if item.scope is not None else None,
        "source_name": item.source.name,
        "source_authority": item.source.authority.value,
        "epistemic_status": item.epistemic_status.value,
    }
    return all(actual.get(key) == value for key, value in constraints.items())


def _program_ref(ref: ProgramInputRef) -> str:
    value = f"{ref.kind.value}:{ref.ref_id}"
    return f"{value}#{ref.selector}" if ref.selector else value
