from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.task.schema import TaskSpec
from trusted_synthesis.core.trajectory.generator import execute_operation
from trusted_synthesis.core.trajectory.schema import ActionType, StepStatus, Trajectory


class TrajectoryCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    passed: bool
    message: str


class TrajectoryVerificationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trajectory_id: str
    checks: tuple[TrajectoryCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


class TrajectoryVerifier:
    def verify(
        self,
        task: TaskSpec,
        bundle: EvidenceBundle,
        trajectory: Trajectory,
    ) -> TrajectoryVerificationReport:
        evidence_by_id = {item.evidence_id: item for item in bundle.evidence}
        input_ids = task.operation.input_evidence_ids
        complete = all(item in evidence_by_id for item in input_ids)
        expected = (
            execute_operation(
                task.operation.operator_id,
                tuple(evidence_by_id[item] for item in input_ids),
            )
            if complete
            else None
        )
        action_types = [step.action for step in trajectory.steps]
        referenced = {item for step in trajectory.steps for item in step.evidence_ids}
        checks = (
            TrajectoryCheck(
                check_id="task_identity",
                passed=trajectory.task_id == task.task_id,
                message="Trajectory is bound to the task",
            ),
            TrajectoryCheck(
                check_id="operation_inputs_complete",
                passed=complete,
                message="All operation inputs are present in the evidence bundle",
            ),
            TrajectoryCheck(
                check_id="required_actions_present",
                passed={
                    ActionType.PLAN,
                    ActionType.SEARCH,
                    ActionType.SELECT_EVIDENCE,
                    ActionType.VERIFY,
                    ActionType.ANSWER,
                }.issubset(action_types),
                message="Required agent workflow actions are present",
            ),
            TrajectoryCheck(
                check_id="step_statuses_succeeded",
                passed=all(step.status == StepStatus.SUCCEEDED for step in trajectory.steps),
                message="All trajectory steps succeeded",
            ),
            TrajectoryCheck(
                check_id="evidence_coverage",
                passed=set(input_ids).issubset(referenced),
                message="Every operation input is referenced by the trajectory",
            ),
            TrajectoryCheck(
                check_id="independent_recompute",
                passed=complete and expected == trajectory.final_answer,
                message="Final answer matches independent operation replay",
            ),
        )
        return TrajectoryVerificationReport(
            trajectory_id=trajectory.trajectory_id,
            checks=checks,
        )
