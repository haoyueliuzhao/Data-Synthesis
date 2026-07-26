from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.operations.program import TaskProgramOracleVerifier
from trusted_synthesis.core.operations.registry import OperationRegistry, default_registry
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory.schema import (
    ActionType,
    StepStatus,
    Trajectory,
    WorkflowKind,
)


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


class ReferenceWorkflowVerifier:
    """Validate a reference workflow with independent operation implementations."""

    def __init__(self, registry: OperationRegistry | None = None) -> None:
        self._oracle = TaskProgramOracleVerifier(registry or default_registry())

    def verify(
        self,
        task: TaskPackage,
        bundle: EvidenceBundle,
        proof_graph: ProofGraph,
        trajectory: Trajectory,
    ) -> TrajectoryVerificationReport:
        by_id = {item.evidence_id: item for item in bundle.evidence}
        gold_ids = task.oracle.gold_evidence_ids
        complete = all(item in by_id for item in gold_ids)
        execution = trajectory.program_execution or {}
        observed_outputs = execution.get("node_outputs") or {}
        replay = (
            self._oracle.verify(task.oracle.task_program, by_id, observed_outputs)
            if complete
            else None
        )
        actions = {step.action for step in trajectory.steps}
        referenced = {item for step in trajectory.steps for item in step.evidence_ids}
        result_matches = bool(
            replay
            and replay.passed
            and trajectory.final_answer.get("result") == replay.independently_computed_output
        )
        checks = (
            _check("task_identity", trajectory.task_id == task.task_id),
            _check("reference_workflow_kind", trajectory.workflow_kind == WorkflowKind.REFERENCE),
            _check("proof_graph_identity", proof_graph.graph_id == task.oracle.proof_graph_id),
            _check(
                "proof_graph_evidence_coverage",
                all(proof_graph.contains_evidence(item) for item in gold_ids),
            ),
            _check("operation_inputs_complete", complete),
            _check(
                "required_actions_present",
                {
                    ActionType.PLAN,
                    ActionType.SEARCH,
                    ActionType.SELECT_EVIDENCE,
                    ActionType.CALCULATE,
                    ActionType.VERIFY,
                    ActionType.ANSWER,
                }.issubset(actions),
            ),
            _check(
                "step_statuses_succeeded",
                all(step.status == StepStatus.SUCCEEDED for step in trajectory.steps),
            ),
            _check("evidence_coverage", set(gold_ids).issubset(referenced)),
            _check("independent_program_replay", bool(replay and replay.passed)),
            _check("final_answer_matches_oracle", result_matches),
            _check(
                "citation_coverage",
                {item.get("evidence_id") for item in trajectory.final_answer.get("citations", [])}
                == set(gold_ids),
            ),
        )
        return TrajectoryVerificationReport(trajectory_id=trajectory.trajectory_id, checks=checks)


def _check(check_id: str, passed: bool) -> TrajectoryCheck:
    return TrajectoryCheck(check_id=check_id, passed=passed, message=check_id.replace("_", " "))
