from __future__ import annotations

from trusted_synthesis.core.evaluation.schema import (
    DiagnosticQualityVector,
    DimensionScore,
    HardGateResult,
    QualityAssessment,
    ReleaseDecision,
)
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.evidence.validation import EvidenceValidator
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory.schema import ActionType, Trajectory
from trusted_synthesis.core.trajectory.verifier import ReferenceWorkflowVerifier
from trusted_synthesis.hashing import canonical_hash

EVALUATOR_VERSION = "deterministic_quality.v2"
REQUIRED_CHECK_MANIFEST = (
    "task_identity",
    "reference_workflow_kind",
    "proof_graph_identity",
    "proof_graph_evidence_coverage",
    "operation_inputs_complete",
    "required_actions_present",
    "step_statuses_succeeded",
    "evidence_coverage",
    "independent_program_replay",
    "final_answer_matches_oracle",
    "citation_coverage",
)


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
        self._workflow_verifier = ReferenceWorkflowVerifier()

    def evaluate(
        self,
        task: TaskPackage,
        bundle: EvidenceBundle,
        proof_graph: ProofGraph,
        trajectory: Trajectory,
    ) -> QualityAssessment:
        gold_ids = set(task.oracle.gold_evidence_ids)
        evidence_reports = [
            self._evidence_validator.validate(item)
            for item in bundle.evidence
            if item.evidence_id in gold_ids
        ]
        workflow_report = self._workflow_verifier.verify(task, bundle, proof_graph, trajectory)
        checks = {check.check_id: check for check in workflow_report.checks}
        missing_checks = tuple(
            check_id for check_id in REQUIRED_CHECK_MANIFEST if check_id not in checks
        )
        failed_checks = tuple(
            check_id
            for check_id in REQUIRED_CHECK_MANIFEST
            if check_id in checks and not checks[check_id].passed
        )
        invalid_evidence = tuple(
            report.evidence_id for report in evidence_reports if not report.passed
        )
        hard_gates = (
            HardGateResult(
                gate_id="required_check_manifest",
                passed=not missing_checks,
                details=missing_checks,
            ),
            HardGateResult(
                gate_id="evidence_validity",
                passed=not invalid_evidence and len(evidence_reports) == len(gold_ids),
                details=invalid_evidence,
            ),
            HardGateResult(
                gate_id="proof_and_lineage",
                passed=not any(
                    item in failed_checks
                    for item in (
                        "proof_graph_identity",
                        "proof_graph_evidence_coverage",
                        "evidence_coverage",
                        "citation_coverage",
                    )
                ),
                details=failed_checks,
            ),
            HardGateResult(
                gate_id="independent_recompute",
                passed=not any(
                    item in failed_checks
                    for item in (
                        "independent_program_replay",
                        "final_answer_matches_oracle",
                    )
                ),
                details=failed_checks,
            ),
        )
        evidence_score = _ratio_score(report.passed for report in evidence_reports)
        actions = {step.action for step in trajectory.steps}
        reasoning_score = _boolean_score(
            checks["required_actions_present"].passed and checks["step_statuses_succeeded"].passed
        )
        tool_score = _boolean_score(
            ActionType.SEARCH in actions
            and all(step.tool_name for step in trajectory.steps if step.action == ActionType.SEARCH)
        )
        verification_score = _boolean_score(checks["independent_program_replay"].passed)
        answer_score = _boolean_score(
            checks["final_answer_matches_oracle"].passed and checks["citation_coverage"].passed
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
        total = round(sum(item.score * item.weight for item in dimensions), 4)
        fatal_failures = tuple(gate.gate_id for gate in hard_gates if not gate.passed)
        decision = (
            ReleaseDecision.REJECTED
            if fatal_failures
            else ReleaseDecision.ACCEPTED
            if total >= 90
            else ReleaseDecision.QUARANTINED
        )
        diagnostic = DiagnosticQualityVector(
            evidence_validity=evidence_score / 100,
            proof_graph_coverage=float(checks["proof_graph_evidence_coverage"].passed),
            operation_replay=float(checks["independent_program_replay"].passed),
            citation_coverage=float(checks["citation_coverage"].passed),
            workflow_completeness=reasoning_score / 100,
            program_depth=len(task.oracle.task_program.nodes),
        )
        manifest_hash = canonical_hash(REQUIRED_CHECK_MANIFEST, prefix="check_manifest:")
        identity = {
            "task_id": task.task_id,
            "trajectory_id": trajectory.trajectory_id,
            "manifest_hash": manifest_hash,
            "evaluator_version": EVALUATOR_VERSION,
        }
        return QualityAssessment(
            assessment_id=canonical_hash(identity, prefix="assessment:"),
            task_id=task.task_id,
            trajectory_id=trajectory.trajectory_id,
            hard_gates=hard_gates,
            required_check_manifest_hash=manifest_hash,
            diagnostic_vector=diagnostic,
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
        "evidence": ("evidence_validity", "proof_graph_evidence_coverage"),
        "reasoning": ("required_actions_present", "step_statuses_succeeded"),
        "tool_use": ("search_action_present", "tool_identity_present"),
        "verification": ("independent_program_replay",),
        "answer": ("final_answer_matches_oracle", "citation_coverage"),
    }[dimension]
