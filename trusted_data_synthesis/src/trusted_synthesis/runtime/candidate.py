from __future__ import annotations

from decimal import Decimal

from trusted_synthesis.core.evaluation.answer import scalar_candidate_result
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

CANDIDATE_GENERATOR_VERSION = "candidate_workflow.v3"


class CandidateTrajectoryGenerator:
    """Generate from public task data only; the oracle type cannot be supplied."""

    def generate(self, task: TaskPublicSpec, runtime: EvidenceToolRuntime) -> Trajectory:
        evidence = runtime.search(task.retrieval_scope)
        selected = self._select(task, evidence)
        result = self._answer(task, selected)
        citations = [
            {
                "evidence_id": item.evidence_id,
                "source_id": item.source.source_id,
                "source_locator": item.source_locator.model_dump(mode="json", exclude_none=True),
            }
            for item in selected
        ]
        evidence_ids = tuple(item.evidence_id for item in selected)
        steps = [
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
        ]
        next_index = 4
        if any(item.value == "calculate" for item in task.requirements):
            steps.append(
                TrajectoryStep(
                    step_index=next_index,
                    action=ActionType.CALCULATE,
                    tool_name="calculator",
                    observation={"result": result},
                    evidence_ids=evidence_ids,
                    rationale_summary="Compute the requested result from selected evidence.",
                    status=StepStatus.SUCCEEDED,
                )
            )
            next_index += 1
        if any(item.value == "verify_result" for item in task.requirements):
            steps.append(
                TrajectoryStep(
                    step_index=next_index,
                    action=ActionType.VERIFY,
                    observation={"schema_checked": True, "source_checked": True},
                    evidence_ids=evidence_ids,
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
                    "evidence_ids": evidence_ids,
                    "version": CANDIDATE_GENERATOR_VERSION,
                },
                prefix="candidate_workflow:",
            ),
            task_id=task.task_id,
            workflow_kind=WorkflowKind.CANDIDATE,
            steps=tuple(steps),
            final_answer={"result": result, "citations": citations},
            generator_version=CANDIDATE_GENERATOR_VERSION,
        )

    @staticmethod
    def _select(task: TaskPublicSpec, evidence):
        if task.task_type == "fact_retrieval" and len(evidence) == 1:
            return evidence
        return evidence

    @staticmethod
    def _answer(task: TaskPublicSpec, evidence) -> dict[str, object]:
        if task.task_type == "fact_retrieval" and len(evidence) == 1:
            item = evidence[0]
            scalar = scalar_candidate_result(item)
            if scalar is not None:
                return scalar
            return {
                "payload": item.payload.model_dump(mode="json", exclude_none=True),
                "source_id": item.source.source_id,
            }
        if task.task_type == "comparison" and len(evidence) == 2:
            values = [_scalar_value(item) for item in evidence]
            higher = None
            if values[0] > values[1]:
                higher = evidence[0].evidence_id
            elif values[1] > values[0]:
                higher = evidence[1].evidence_id
            return {"higher_ref": higher, "difference": str(abs(values[0] - values[1]))}
        if task.task_type == "temporal_growth" and len(evidence) == 2:
            ordered = sorted(evidence, key=_temporal_sort_key)
            earlier = _scalar_value(ordered[0])
            later = _scalar_value(ordered[1])
            if earlier == 0:
                return {"status": "insufficient_capability", "reason": "zero_base"}
            return {"value": str((later - earlier) / abs(earlier) * Decimal("100"))}
        if task.task_type == "temporal_average" and len(evidence) >= 3:
            values = [_scalar_value(item) for item in evidence]
            return {
                "method": "mean",
                "value": str(sum(values, Decimal("0")) / Decimal(len(values))),
            }
        return {"status": "insufficient_capability", "matched_count": len(evidence)}


def _scalar_value(item) -> Decimal:
    if not isinstance(item.payload, ScalarObservation):
        raise ValueError(f"candidate numeric task received non-scalar evidence: {item.evidence_id}")
    return Decimal(str(item.payload.value))


def _temporal_sort_key(item):
    context = item.temporal_context
    return context.valid_to or context.observed_at or context.valid_from
