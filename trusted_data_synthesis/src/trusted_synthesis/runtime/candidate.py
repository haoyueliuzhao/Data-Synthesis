from __future__ import annotations

from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.task.schema import TaskPublicSpec
from trusted_synthesis.core.trajectory.schema import (
    ActionType,
    StepStatus,
    Trajectory,
    TrajectoryStep,
    WorkflowKind,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import EvidenceToolRuntime

CANDIDATE_GENERATOR_VERSION = "candidate_workflow.v1"


class CandidateTrajectoryGenerator:
    """Generate from public task data only; the oracle type cannot be supplied."""

    def generate(self, task: TaskPublicSpec, runtime: EvidenceToolRuntime) -> Trajectory:
        evidence = runtime.search(task.retrieval_scope)
        selected = self._select(task, evidence)
        result = self._answer(task, selected)
        evidence_ids = tuple(item.evidence_id for item in selected)
        steps = (
            TrajectoryStep(
                step_index=1,
                action=ActionType.PLAN,
                observation={"task_type": task.task_type},
                rationale_summary="Infer the required evidence from the public instruction.",
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
            TrajectoryStep(
                step_index=3,
                action=ActionType.SELECT_EVIDENCE,
                observation={"selected_count": len(selected)},
                evidence_ids=evidence_ids,
                rationale_summary="Select evidence matching the requested task semantics.",
                status=StepStatus.SUCCEEDED,
            ),
            TrajectoryStep(
                step_index=4,
                action=ActionType.ANSWER,
                observation=result,
                evidence_ids=evidence_ids,
                rationale_summary="Return the answer derived from publicly retrieved evidence.",
                status=StepStatus.SUCCEEDED,
            ),
        )
        return Trajectory(
            trajectory_id=canonical_hash(
                {
                    "task_id": task.task_id,
                    "evidence_ids": evidence_ids,
                    "version": CANDIDATE_GENERATOR_VERSION,
                },
                prefix="candidate_workflow:",
            ),
            task_id=task.task_id,
            workflow_kind=WorkflowKind.CANDIDATE,
            steps=steps,
            final_answer=result,
            generator_version=CANDIDATE_GENERATOR_VERSION,
        )

    @staticmethod
    def _select(task: TaskPublicSpec, evidence):
        if task.task_type == "fact_retrieval" and len(evidence) == 1:
            return evidence
        return evidence

    @staticmethod
    def _answer(task: TaskPublicSpec, evidence) -> dict[str, object]:
        if task.task_type != "fact_retrieval" or len(evidence) != 1:
            return {"status": "insufficient_capability", "matched_count": len(evidence)}
        item = evidence[0]
        if not isinstance(item.payload, ScalarObservation):
            return {"status": "unsupported_payload"}
        return {
            "value": str(item.payload.value),
            "unit": item.payload.unit,
            "currency": item.payload.currency,
            "source_id": item.source.source_id,
        }
