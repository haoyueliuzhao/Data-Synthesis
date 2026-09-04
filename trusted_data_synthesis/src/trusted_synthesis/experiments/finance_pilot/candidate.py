from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from trusted_synthesis.core.evaluation.answer import CandidateAnswerNormalizer
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.program import ProgramExecution, TaskProgramExecutor
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.task.program import InputRefKind, TaskProgram
from trusted_synthesis.core.task.schema import TaskPublicSpec
from trusted_synthesis.core.trajectory.public_plan_executor import (
    _project_public_result,
    _reconstruct_program,
    _resolve_public_roles,
)
from trusted_synthesis.core.trajectory.schema import (
    ActionType,
    StepStatus,
    Trajectory,
    TrajectoryStep,
    WorkflowKind,
)
from trusted_synthesis.domains.finance.operations import finance_vnext_operation_registry
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import EvidenceToolRuntime

CANDIDATE_GENERATOR_VERSION = "finance_numeric_candidate.v7"
FINANCE_NUMERIC_GENERATOR_CONTRACT_ID = canonical_hash(
    {
        "implementation": "FinanceNumericCandidateGenerator",
        "generator_version": CANDIDATE_GENERATOR_VERSION,
        "input_schema": "TaskPublicSpec+EvidenceCorpus",
        "output_schema": "Trajectory",
        "program_authority": "public_program_skeleton",
        "program_execution": "registry_topological_complete",
        "answer_projection": "executed_node_outputs_and_public_answer_schema",
        "registered_task_catalog_totality": (
            "comparison",
            "derived_growth_comparison",
            "fact_retrieval",
            "registered_cross_metric_comparison",
            "registered_ratio",
            "temporal_absolute_change",
            "temporal_average",
            "temporal_growth",
        ),
        "schema_version": "deterministic_generator_contract.v1",
    },
    prefix="deterministic_generator_contract:",
)


class FinanceNumericCandidateGenerator:
    """Execute a resolved Finance public Program without consulting the hidden Oracle."""

    def generate(self, task: TaskPublicSpec, runtime: EvidenceToolRuntime) -> Trajectory:
        evidence = runtime.search(task.retrieval_scope)
        selected = self._select(task, evidence)
        registry = finance_vnext_operation_registry()
        program, execution, public_roles = _execute_public_program(
            task,
            selected,
            registry,
        )
        result = self._answer(task, selected, execution, public_roles)
        citations = [
            {
                "evidence_id": item.evidence_id,
                "source_id": item.source.source_id,
                "source_locator": item.source_locator.model_dump(mode="json", exclude_none=True),
            }
            for item in selected
        ]
        evidence_ids = tuple(item.evidence_id for item in selected)
        steps: list[TrajectoryStep] = [
            TrajectoryStep(
                step_index=1,
                action=ActionType.PLAN,
                observation={
                    "task_type": task.task_type,
                    "planning_track": task.planning_track.value,
                    "program_node_count": len(program.nodes),
                },
                rationale_summary="Read the public Program skeleton and retrieval constraints.",
                status=StepStatus.SUCCEEDED,
            ),
            TrajectoryStep(
                step_index=2,
                action=ActionType.SEARCH,
                tool_name="evidence.search",
                tool_input=task.retrieval_scope,
                observation={"matched_count": len(evidence)},
                evidence_ids=tuple(item.evidence_id for item in evidence),
                rationale_summary="Search with public subject, predicate, and time constraints.",
                status=StepStatus.SUCCEEDED,
            ),
        ]
        steps.extend(
            _operation_steps(
                selected,
                program,
                execution,
                registry,
                start_index=3,
            )
        )
        next_index = len(steps) + 1
        if any(item.value == "verify_result" for item in task.requirements):
            steps.append(
                TrajectoryStep(
                    step_index=next_index,
                    action=ActionType.VERIFY,
                    observation={
                        "schema_checked": True,
                        "source_checked": True,
                        "verified_output_ref": f"operation:{program.output_node_id}",
                        "verified_result": execution.final_output,
                    },
                    evidence_ids=evidence_ids,
                    program_node_id=program.output_node_id,
                    input_refs=(f"operation:{program.output_node_id}",),
                    rationale_summary=(
                        "Check answer fields and bind citations to selected evidence."
                    ),
                    status=StepStatus.SUCCEEDED,
                )
            )
            next_index += 1
        steps.append(
            TrajectoryStep(
                step_index=next_index,
                action=ActionType.ANSWER,
                observation={"result": result, "citations": citations},
                evidence_ids=evidence_ids,
                rationale_summary="Return the answer derived from publicly retrieved evidence.",
                status=StepStatus.SUCCEEDED,
            )
        )
        return Trajectory(
            trajectory_id=canonical_hash(
                {
                    "task_id": task.task_id,
                    "retrieved_evidence_ids": tuple(item.evidence_id for item in evidence),
                    "evidence_ids": evidence_ids,
                    "program_id": program.program_id,
                    "node_outputs": execution.node_outputs,
                    "result": result,
                    "version": CANDIDATE_GENERATOR_VERSION,
                },
                prefix="candidate_workflow:",
            ),
            task_id=task.task_id,
            workflow_kind=WorkflowKind.CANDIDATE,
            steps=tuple(steps),
            program_execution=execution.model_dump(mode="json"),
            final_answer={"result": result, "citations": citations},
            generator_version=CANDIDATE_GENERATOR_VERSION,
        )

    @staticmethod
    def _select(task: TaskPublicSpec, evidence):
        contract = task.retrieval_scope.get("semantic_constraints")
        if not isinstance(contract, dict):
            return evidence
        return tuple(item for item in evidence if _matches_semantic_constraints(item, contract))

    @staticmethod
    def _answer(
        task: TaskPublicSpec,
        evidence: tuple[EvidenceItem, ...],
        execution: ProgramExecution,
        public_roles: Mapping[str, str],
    ) -> dict[str, Any]:
        answer_role_bindings: dict[str, tuple[str, ...]] = {}
        projection = task.answer_schema.get("result_projection")
        if isinstance(projection, Mapping):
            fields = projection.get("fields")
            if isinstance(fields, Mapping):
                for spec in fields.values():
                    if not isinstance(spec, Mapping) or spec.get("kind") != "evidence_role":
                        continue
                    role_id = str(spec["role_id"])
                    position = int(spec.get("role_position", 0))
                    if len(evidence) != 1 or position != 0:
                        raise ValueError(
                            "public answer Evidence-role projection is not uniquely resolvable"
                        )
                    answer_role_bindings[role_id] = (evidence[0].evidence_id,)
        projected = _project_public_result(
            task.answer_schema,
            execution,
            {item.evidence_id: item for item in evidence},
            answer_role_bindings,
        )
        if task.answer_schema.get("type") == "payload_with_source":
            if len(evidence) != 1:
                raise ValueError("fact answer source projection is not uniquely resolvable")
            projected = {**projected, "source_id": evidence[0].source.source_id}
        result = CandidateAnswerNormalizer().normalize_result(task, projected)

        _validate_catalog_answer(task, result, public_roles)
        return result


def _execute_public_program(
    task: TaskPublicSpec,
    evidence: tuple[EvidenceItem, ...],
    registry: OperationRegistry,
) -> tuple[TaskProgram, ProgramExecution, dict[str, str]]:
    skeleton = task.program_skeleton
    if skeleton is None:
        raise ValueError("finance numeric candidate requires a public Program skeleton")
    evidence_by_id = {item.evidence_id: item for item in evidence}
    public_roles = _resolve_public_roles(skeleton.nodes, evidence_by_id)
    program = _reconstruct_program(
        skeleton.nodes,
        skeleton.output_node_id,
        public_roles,
        registry,
    )
    execution = TaskProgramExecutor(registry).execute(program, evidence_by_id)
    return program, execution, public_roles


def _validate_catalog_answer(
    task: TaskPublicSpec,
    result: dict[str, Any],
    public_roles: Mapping[str, str],
) -> None:
    registered = {
        "comparison",
        "derived_growth_comparison",
        "fact_retrieval",
        "registered_cross_metric_comparison",
        "registered_ratio",
        "temporal_absolute_change",
        "temporal_average",
        "temporal_growth",
    }
    if task.task_type not in registered:
        raise ValueError(f"unsupported finance task type: {task.task_type}")
    if result.get("status") == "insufficient_capability":
        raise ValueError(f"registered finance task did not produce an answer: {task.task_type}")
    required = set(task.answer_schema.get("required_fields") or ())
    missing = required - set(result)
    if missing:
        raise ValueError(f"registered finance answer is missing fields: {sorted(missing)}")
    if not public_roles:
        raise ValueError("registered finance answer has no public Evidence-role binding")


def _operation_steps(
    evidence: tuple[EvidenceItem, ...],
    program: TaskProgram,
    execution: ProgramExecution,
    registry: OperationRegistry,
    *,
    start_index: int,
) -> tuple[TrajectoryStep, ...]:
    evidence_ids = tuple(item.evidence_id for item in evidence)
    steps: list[TrajectoryStep] = [
        TrajectoryStep(
            step_index=start_index,
            action=ActionType.SELECT_EVIDENCE,
            observation={"selected_count": len(evidence)},
            evidence_ids=evidence_ids,
            rationale_summary="Bind every public Program Evidence role to one retrieved row.",
            status=StepStatus.SUCCEEDED,
        )
    ]
    for node in program.nodes:
        definition = registry.require(node.operator_id)
        input_refs = tuple(
            f"{ref.kind.value}:{ref.ref_id}" + (f"#{ref.selector}" if ref.selector else "")
            for ref in node.input_refs
        )
        direct_evidence_ids = tuple(
            ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.EVIDENCE
        )
        steps.append(
            TrajectoryStep(
                step_index=start_index + len(steps),
                action=ActionType(definition.action_type),
                tool_name=definition.tool_capability,
                tool_input={"parameters": node.parameters},
                observation={"result": execution.node_outputs[node.node_id]},
                evidence_ids=direct_evidence_ids,
                program_node_id=node.node_id,
                operator_id=node.operator_id,
                input_refs=input_refs,
                output_ref=f"operation:{node.node_id}",
                rationale_summary=(
                    "Execute this registered public Program node in dependency order."
                ),
                status=StepStatus.SUCCEEDED,
            )
        )
    return tuple(steps)


def _matches_semantic_constraints(item, contract: dict[str, object]) -> bool:
    payload = item.payload.model_dump(mode="json", exclude_none=True)
    payload_context = {
        key: value for key, value in payload.items() if key not in {"kind", "value", "precision"}
    }
    payload_contexts = contract.get("payload_contexts")
    payload_context_match = True
    if isinstance(payload_contexts, list) and payload_contexts:
        payload_context_match = payload_context in payload_contexts
    checks = (
        _allowed(item.definition.definition_id, contract.get("definition_ids")),
        _allowed(item.source.authority.value, contract.get("source_authorities")),
        payload_context_match,
        _allowed(item.epistemic_status.value, contract.get("epistemic_statuses")),
        _allowed(item.temporal_context.basis, contract.get("time_bases")),
        _allowed(item.temporal_context.frequency, contract.get("frequencies")),
        _allowed(item.scope.scope_type if item.scope else None, contract.get("scope_types")),
        _allowed(item.scope.scope_id if item.scope else None, contract.get("scope_ids")),
    )
    if not all(checks):
        return False
    return not (contract.get("historical_only") is True and item.domain_context.get("is_forecast"))


def _allowed(value: object, allowed: object) -> bool:
    if not isinstance(allowed, (list, tuple, set)) or not allowed:
        return True
    return value in set(allowed)
