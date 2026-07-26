from __future__ import annotations

from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.operations.program import TaskProgramExecutor
from trusted_synthesis.core.operations.registry import OperationRegistry, default_registry
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory.schema import (
    ActionType,
    StepStatus,
    Trajectory,
    TrajectoryStep,
    WorkflowKind,
)
from trusted_synthesis.hashing import canonical_hash

REFERENCE_COMPILER_VERSION = "reference_workflow.v3"


class ReferenceWorkflowError(ValueError):
    pass


class ReferenceWorkflowCompiler:
    """Compile the hidden oracle into a deterministic reference workflow."""

    def __init__(self, registry: OperationRegistry | None = None) -> None:
        self._executor = TaskProgramExecutor(registry or default_registry())

    def compile(self, task: TaskPackage, bundle: EvidenceBundle) -> Trajectory:
        by_id = {item.evidence_id: item for item in bundle.evidence}
        missing = [item for item in task.oracle.gold_evidence_ids if item not in by_id]
        if missing:
            raise ReferenceWorkflowError(f"missing oracle evidence: {missing}")
        execution = self._executor.execute(task.oracle.task_program, by_id)
        evidence_ids = task.oracle.gold_evidence_ids
        citations = [
            {
                "evidence_id": item,
                "source_id": by_id[item].source.source_id,
                "source_locator": by_id[item].source_locator.model_dump(
                    mode="json", exclude_none=True
                ),
            }
            for item in evidence_ids
        ]
        steps = (
            TrajectoryStep(
                step_index=1,
                action=ActionType.PLAN,
                observation={"program_id": task.oracle.task_program.program_id},
                rationale_summary="Compile the pinned oracle program and its dependencies.",
                status=StepStatus.SUCCEEDED,
            ),
            TrajectoryStep(
                step_index=2,
                action=ActionType.SEARCH,
                tool_name="oracle_evidence.read",
                tool_input={"oracle_contract": task.oracle.task_id},
                observation={"matched_count": len(evidence_ids)},
                evidence_ids=evidence_ids,
                rationale_summary="Read the exact evidence pinned by the oracle contract.",
                status=StepStatus.SUCCEEDED,
            ),
            TrajectoryStep(
                step_index=3,
                action=ActionType.SELECT_EVIDENCE,
                observation={"selected_count": len(evidence_ids)},
                evidence_ids=evidence_ids,
                rationale_summary="Bind every program input to its versioned evidence item.",
                status=StepStatus.SUCCEEDED,
            ),
            TrajectoryStep(
                step_index=4,
                action=ActionType.CALCULATE,
                tool_name="operation_program.execute",
                tool_input={"program_id": execution.program_id},
                observation=execution.model_dump(mode="json"),
                evidence_ids=evidence_ids,
                rationale_summary="Execute the registered operation DAG in topological order.",
                status=StepStatus.SUCCEEDED,
            ),
            TrajectoryStep(
                step_index=5,
                action=ActionType.VERIFY,
                tool_name="operation_oracle.verify",
                observation={"verification_requested": True},
                evidence_ids=evidence_ids,
                rationale_summary="Request independent replay through oracle implementations.",
                status=StepStatus.SUCCEEDED,
            ),
            TrajectoryStep(
                step_index=6,
                action=ActionType.ANSWER,
                observation={"result": execution.final_output, "citations": citations},
                evidence_ids=evidence_ids,
                rationale_summary="Return the computed result with complete source lineage.",
                status=StepStatus.SUCCEEDED,
            ),
        )
        identity = {
            "task_id": task.task_id,
            "bundle_hash": bundle.bundle_hash,
            "program_hash": task.oracle.task_program.program_hash,
            "version": REFERENCE_COMPILER_VERSION,
        }
        return Trajectory(
            trajectory_id=canonical_hash(identity, prefix="reference_workflow:"),
            task_id=task.task_id,
            workflow_kind=WorkflowKind.REFERENCE,
            steps=steps,
            program_execution=execution.model_dump(mode="json"),
            final_answer={"result": execution.final_output, "citations": citations},
            generator_version=REFERENCE_COMPILER_VERSION,
        )
