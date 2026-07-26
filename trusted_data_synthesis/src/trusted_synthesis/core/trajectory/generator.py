from __future__ import annotations

from decimal import Decimal, InvalidOperation

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.task.schema import TaskSpec
from trusted_synthesis.core.trajectory.schema import (
    ActionType,
    StepStatus,
    Trajectory,
    TrajectoryStep,
)
from trusted_synthesis.hashing import canonical_hash

GENERATOR_VERSION = "deterministic_trajectory.v1"


class TrajectoryGenerationError(ValueError):
    pass


class DeterministicTrajectoryGenerator:
    def generate(self, task: TaskSpec, bundle: EvidenceBundle) -> Trajectory:
        evidence = self._bind_inputs(task, bundle)
        answer = execute_operation(task.operation.operator_id, evidence)
        evidence_ids = tuple(item.evidence_id for item in evidence)
        steps = [
            TrajectoryStep(
                step_index=1,
                action=ActionType.PLAN,
                observation={"operator_id": task.operation.operator_id},
                rationale_summary="Identify the required evidence and deterministic operation.",
                status=StepStatus.SUCCEEDED,
            ),
            TrajectoryStep(
                step_index=2,
                action=ActionType.SEARCH,
                tool_name="evidence_archive.search",
                tool_input={"evidence_ids": list(task.hidden_evidence_ids)},
                observation={"matched_evidence_ids": list(evidence_ids)},
                evidence_ids=evidence_ids,
                rationale_summary="Retrieve only evidence pinned by the task contract.",
                status=StepStatus.SUCCEEDED,
            ),
            TrajectoryStep(
                step_index=3,
                action=ActionType.SELECT_EVIDENCE,
                observation={"selected_count": len(evidence)},
                evidence_ids=evidence_ids,
                rationale_summary="Select the complete input set required by the operation.",
                status=StepStatus.SUCCEEDED,
            ),
        ]
        if task.operation.operator_id != "lookup":
            steps.append(
                TrajectoryStep(
                    step_index=len(steps) + 1,
                    action=ActionType.CALCULATE,
                    tool_name="deterministic_calculator",
                    tool_input={
                        "operator_id": task.operation.operator_id,
                        "values": [str(item.value) for item in evidence],
                    },
                    observation=answer,
                    evidence_ids=evidence_ids,
                    rationale_summary="Execute the registered operation with Decimal arithmetic.",
                    status=StepStatus.SUCCEEDED,
                )
            )
        steps.extend(
            [
                TrajectoryStep(
                    step_index=len(steps) + 1,
                    action=ActionType.VERIFY,
                    tool_name="trajectory_verifier.recompute",
                    observation={"recomputed": True, "result": answer},
                    evidence_ids=evidence_ids,
                    rationale_summary="Independently recompute the operation before answering.",
                    status=StepStatus.SUCCEEDED,
                ),
                TrajectoryStep(
                    step_index=len(steps) + 2,
                    action=ActionType.ANSWER,
                    observation=answer,
                    evidence_ids=evidence_ids,
                    rationale_summary="Return the verified result with its source lineage.",
                    status=StepStatus.SUCCEEDED,
                ),
            ]
        )
        identity = {
            "task_id": task.task_id,
            "bundle_hash": bundle.bundle_hash,
            "generator_version": GENERATOR_VERSION,
        }
        return Trajectory(
            trajectory_id=canonical_hash(identity, prefix="trajectory:"),
            task_id=task.task_id,
            steps=tuple(steps),
            final_answer=answer,
            generator_version=GENERATOR_VERSION,
        )

    @staticmethod
    def _bind_inputs(task: TaskSpec, bundle: EvidenceBundle) -> tuple[EvidenceItem, ...]:
        by_id = {item.evidence_id: item for item in bundle.evidence}
        missing = [item for item in task.operation.input_evidence_ids if item not in by_id]
        if missing:
            raise TrajectoryGenerationError(f"Missing operation inputs: {missing}")
        return tuple(by_id[item] for item in task.operation.input_evidence_ids)


def execute_operation(operator_id: str, evidence: tuple[EvidenceItem, ...]) -> dict[str, object]:
    if operator_id == "lookup" and len(evidence) == 1:
        item = evidence[0]
        return {
            "value": str(item.value),
            "unit": item.unit,
            "currency": item.currency,
            "source_id": item.source.source_id,
            "evidence_ids": [item.evidence_id],
        }
    if operator_id == "compare" and len(evidence) == 2:
        left, right = evidence
        left_value = _decimal(left)
        right_value = _decimal(right)
        if left_value == right_value:
            higher = None
        else:
            higher = left.evidence_id if left_value > right_value else right.evidence_id
        return {
            "higher_evidence_id": higher,
            "difference": str(abs(left_value - right_value)),
            "unit": left.unit,
            "currency": left.currency,
            "evidence_ids": [left.evidence_id, right.evidence_id],
        }
    raise TrajectoryGenerationError(
        f"Unsupported operation or arity: {operator_id}/{len(evidence)}"
    )


def _decimal(evidence: EvidenceItem) -> Decimal:
    try:
        return Decimal(str(evidence.value))
    except InvalidOperation as exc:
        raise TrajectoryGenerationError(
            f"Evidence value is not numeric: {evidence.evidence_id}"
        ) from exc
