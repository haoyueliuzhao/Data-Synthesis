from __future__ import annotations

from trusted_synthesis.core.evaluation.schema import (
    DimensionScore,
    QualityAssessment,
    ReleaseDecision,
)
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.evidence.validation import EvidenceValidator
from trusted_synthesis.core.task.schema import TaskSpec
from trusted_synthesis.core.trajectory.schema import ActionType, Trajectory
from trusted_synthesis.core.trajectory.verifier import TrajectoryVerifier
from trusted_synthesis.hashing import canonical_hash

EVALUATOR_VERSION = "deterministic_quality.v1"


class QualityEvaluator:
    _weights = {
        "evidence": 0.30,
        "reasoning": 0.20,
        "tool_use": 0.15,
        "verification": 0.20,
        "answer": 0.15,
    }

    def __init__(self) -> None:
        self._evidence_validator = EvidenceValidator()
        self._trajectory_verifier = TrajectoryVerifier()

    def evaluate(
        self,
        task: TaskSpec,
        bundle: EvidenceBundle,
        trajectory: Trajectory,
    ) -> QualityAssessment:
        evidence_reports = [
            self._evidence_validator.validate(item)
            for item in bundle.evidence
            if item.evidence_id in task.hidden_evidence_ids
        ]
        trajectory_report = self._trajectory_verifier.verify(task, bundle, trajectory)
        evidence_score = _ratio_score(report.passed for report in evidence_reports)
        trajectory_checks = {check.check_id: check for check in trajectory_report.checks}
        reasoning_score = _boolean_score(
            trajectory_checks["required_actions_present"].passed
            and trajectory_checks["step_statuses_succeeded"].passed
        )
        actions = {step.action for step in trajectory.steps}
        tool_score = _boolean_score(
            ActionType.SEARCH in actions
            and all(step.tool_name for step in trajectory.steps if step.action == ActionType.SEARCH)
        )
        verification_score = _boolean_score(
            ActionType.VERIFY in actions and trajectory_checks["independent_recompute"].passed
        )
        answer_score = _boolean_score(
            trajectory_checks["task_identity"].passed
            and trajectory_checks["evidence_coverage"].passed
            and trajectory_checks["independent_recompute"].passed
        )
        raw_scores = {
            "evidence": evidence_score,
            "reasoning": reasoning_score,
            "tool_use": tool_score,
            "verification": verification_score,
            "answer": answer_score,
        }
        dimensions = tuple(
            DimensionScore(
                dimension=name,
                score=score,
                weight=self._weights[name],
                checks=_dimension_checks(name),
            )
            for name, score in raw_scores.items()
        )
        total = round(
            sum(item.score * item.weight for item in dimensions)
            / sum(item.weight for item in dimensions),
            4,
        )
        fatal_failures = tuple(
            check.check_id for check in trajectory_report.checks if not check.passed
        ) + tuple(
            f"evidence:{report.evidence_id}" for report in evidence_reports if not report.passed
        )
        if fatal_failures:
            decision = ReleaseDecision.REJECTED
        elif total >= 90:
            decision = ReleaseDecision.ACCEPTED
        else:
            decision = ReleaseDecision.QUARANTINED
        identity = {
            "task_id": task.task_id,
            "trajectory_id": trajectory.trajectory_id,
            "evaluator_version": EVALUATOR_VERSION,
        }
        return QualityAssessment(
            assessment_id=canonical_hash(identity, prefix="assessment:"),
            task_id=task.task_id,
            trajectory_id=trajectory.trajectory_id,
            dimensions=dimensions,
            total_score=total,
            decision=decision,
            fatal_failures=fatal_failures,
            evaluator_version=EVALUATOR_VERSION,
        )


def _ratio_score(values) -> float:
    observed = list(values)
    if not observed:
        return 0.0
    return 100.0 * sum(bool(value) for value in observed) / len(observed)


def _boolean_score(value: bool) -> float:
    return 100.0 if value else 0.0


def _dimension_checks(dimension: str) -> tuple[str, ...]:
    return {
        "evidence": ("accepted_evidence_status", "lineage_complete", "source_identity_complete"),
        "reasoning": ("required_actions_present", "step_statuses_succeeded"),
        "tool_use": ("search_action_present", "tool_identity_present"),
        "verification": ("verification_action_present", "independent_recompute"),
        "answer": ("task_identity", "evidence_coverage", "independent_recompute"),
    }[dimension]
