from __future__ import annotations

from typing import Any

from trusted_synthesis.core.evaluation.grounding import (
    evaluate_source_grounding,
    grounding_requirement,
)
from trusted_synthesis.core.evaluation.schema import (
    DiagnosticQualityVector,
    DimensionScore,
    GateScope,
    HardGateResult,
    QualityAssessment,
    ReleaseDecision,
)
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.evidence.validation import EvidenceValidator
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.plugins import (
    ClaimVerifierProtocol,
    SemanticPolicyProtocol,
    SourceGroundingVerifierProtocol,
)
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory.candidate_verifier import (
    CandidateWorkflowVerifier,
)
from trusted_synthesis.core.trajectory.schema import ActionType, Trajectory
from trusted_synthesis.core.trajectory.verifier import (
    ReferenceWorkflowVerifier,
)
from trusted_synthesis.hashing import canonical_hash

REFERENCE_EVALUATOR_VERSION = "reference_quality.v5"
CANDIDATE_EVALUATOR_VERSION = "candidate_quality.v6"
REQUIRED_CHECK_MANIFEST = (
    "task_identity",
    "reference_workflow_kind",
    "proof_graph_identity",
    "proof_graph_content_integrity",
    "proof_graph_evidence_coverage",
    "operation_inputs_complete",
    "required_actions_present",
    "step_statuses_succeeded",
    "evidence_coverage",
    "independent_program_replay",
    "final_answer_matches_oracle",
    "citation_coverage",
    "citation_binding",
)
CANDIDATE_REQUIRED_CHECK_MANIFEST = (
    "task_identity",
    "candidate_workflow_kind",
    "public_only_generation",
    "allowed_tool_compliance",
    "required_actions_present",
    "step_statuses_succeeded",
    "action_sequence_valid",
    "retrieved_evidence_known",
    "retrieved_evidence_validity",
    "selected_evidence_was_retrieved",
    "selected_evidence_validity",
    "source_grounding",
    "evidence_recall",
    "evidence_precision",
    "proof_graph_binding",
    "execution_coverage",
    "operation_grounding",
    "tool_necessity",
    "program_node_alignment",
    "all_calculations_correct",
    "verification_step_binding",
    "operation_correctness",
    "answer_schema_validity",
    "answer_correctness",
    "citation_binding",
    "unsupported_claim_detection",
    "domain_claim_verification",
)


class ReferenceQualityEvaluator:
    """Certify deterministic reference compilation, not model behavior."""

    _weights = {
        "evidence": 0.30,
        "reasoning": 0.20,
        "tool_use": 0.15,
        "verification": 0.20,
        "answer": 0.15,
    }

    def __init__(
        self,
        *,
        semantic_policy: SemanticPolicyProtocol | None = None,
        source_grounding_verifier: SourceGroundingVerifierProtocol | None = None,
        workflow_verifier: ReferenceWorkflowVerifier | None = None,
    ) -> None:
        self._structural_evidence_validator = EvidenceValidator()
        self._domain_evidence_validator = EvidenceValidator(semantic_policy)
        self._source_grounding_verifier = source_grounding_verifier
        self._workflow_verifier = workflow_verifier or ReferenceWorkflowVerifier()

    def evaluate(
        self,
        task: TaskPackage,
        bundle: EvidenceBundle,
        proof_graph: ProofGraph,
        trajectory: Trajectory,
    ) -> QualityAssessment:
        gold_ids = set(task.oracle.gold_evidence_ids)
        structural_reports = [
            self._structural_evidence_validator.validate_structural(item)
            for item in bundle.evidence
            if item.evidence_id in gold_ids
        ]
        domain_reports = [
            self._domain_evidence_validator.validate_domain(item)
            for item in bundle.evidence
            if item.evidence_id in gold_ids
        ]
        workflow_report = self._workflow_verifier.verify(task, bundle, proof_graph, trajectory)
        checks = {check.check_id: check for check in workflow_report.checks}
        missing, failed = _check_failures(checks, REQUIRED_CHECK_MANIFEST)
        invalid_structural_evidence = tuple(
            report.evidence_id for report in structural_reports if not report.passed
        )
        invalid_domain_evidence = tuple(
            report.evidence_id for report in domain_reports if not report.passed
        )
        grounding = evaluate_source_grounding(
            tuple(item for item in bundle.evidence if item.evidence_id in gold_ids),
            grounding_requirement(task.public.metadata),
            self._source_grounding_verifier,
        )
        hard_gates = (
            HardGateResult(
                gate_id="required_check_manifest",
                scope=GateScope.UNIVERSAL,
                passed=not missing,
                details=missing,
            ),
            HardGateResult(
                gate_id="structural_evidence_validity",
                scope=GateScope.UNIVERSAL,
                passed=(
                    not invalid_structural_evidence and len(structural_reports) == len(gold_ids)
                ),
                details=invalid_structural_evidence,
            ),
            HardGateResult(
                gate_id="domain_evidence_semantics",
                scope=GateScope.DOMAIN,
                passed=not invalid_domain_evidence and len(domain_reports) == len(gold_ids),
                details=invalid_domain_evidence,
            ),
            HardGateResult(
                gate_id="domain_source_grounding",
                scope=GateScope.DOMAIN,
                passed=grounding.passed,
                details=(f"status={grounding.status.value}", *grounding.failures),
            ),
            HardGateResult(
                gate_id="proof_and_lineage",
                scope=GateScope.UNIVERSAL,
                passed=all(
                    _check_passed(checks, item)
                    for item in (
                        "proof_graph_identity",
                        "proof_graph_content_integrity",
                        "proof_graph_evidence_coverage",
                        "evidence_coverage",
                        "citation_coverage",
                        "citation_binding",
                    )
                ),
                details=failed,
            ),
            HardGateResult(
                gate_id="independent_recompute",
                scope=GateScope.UNIVERSAL,
                passed=all(
                    _check_passed(checks, item)
                    for item in (
                        "independent_program_replay",
                        "final_answer_matches_oracle",
                    )
                ),
                details=failed,
            ),
        )
        actions = {step.action for step in trajectory.steps}
        raw_scores = {
            "evidence": _ratio_score(report.passed for report in structural_reports),
            "reasoning": _boolean_score(
                _check_passed(checks, "required_actions_present")
                and _check_passed(checks, "step_statuses_succeeded")
            ),
            "tool_use": _boolean_score(
                ActionType.SEARCH in actions
                and all(
                    step.tool_name for step in trajectory.steps if step.action == ActionType.SEARCH
                )
            ),
            "verification": _boolean_score(_check_passed(checks, "independent_program_replay")),
            "answer": _boolean_score(
                _check_passed(checks, "final_answer_matches_oracle")
                and _check_passed(checks, "citation_binding")
            ),
        }
        return _assessment(
            task=task,
            trajectory=trajectory,
            hard_gates=hard_gates,
            manifest=REQUIRED_CHECK_MANIFEST,
            raw_scores=raw_scores,
            weights=self._weights,
            diagnostic=DiagnosticQualityVector(
                evidence_validity=raw_scores["evidence"] / 100,
                proof_graph_coverage=float(_check_passed(checks, "proof_graph_content_integrity")),
                operation_replay=float(_check_passed(checks, "independent_program_replay")),
                citation_coverage=float(_check_passed(checks, "citation_binding")),
                workflow_completeness=raw_scores["reasoning"] / 100,
                program_depth=len(task.oracle.task_program.nodes),
            ),
            failed_check_ids=failed,
            check_failure_details=_failure_detail_map(checks, failed),
            evaluator_version=REFERENCE_EVALUATOR_VERSION,
        )


class CandidateQualityEvaluator:
    """Evaluate a model/agent trajectory against a hidden, independently replayed oracle."""

    _weights = {
        "evidence": 0.30,
        "reasoning": 0.20,
        "tool_use": 0.15,
        "verification": 0.20,
        "answer": 0.15,
    }

    def __init__(
        self,
        *,
        semantic_policy: SemanticPolicyProtocol | None = None,
        claim_verifier: ClaimVerifierProtocol | None = None,
        source_grounding_verifier: SourceGroundingVerifierProtocol | None = None,
        workflow_verifier: CandidateWorkflowVerifier | None = None,
    ) -> None:
        self._structural_evidence_validator = EvidenceValidator()
        self._domain_evidence_validator = EvidenceValidator(semantic_policy)
        self._workflow_verifier = workflow_verifier or CandidateWorkflowVerifier(
            semantic_policy=semantic_policy,
            claim_verifier=claim_verifier,
            source_grounding_verifier=source_grounding_verifier,
        )

    def evaluate(
        self,
        task: TaskPackage,
        corpus: EvidenceCorpus,
        proof_graph: ProofGraph,
        trajectory: Trajectory,
    ) -> QualityAssessment:
        report = self._workflow_verifier.verify(task, corpus, proof_graph, trajectory)
        checks = {check.check_id: check for check in report.checks}
        missing, failed = _check_failures(checks, CANDIDATE_REQUIRED_CHECK_MANIFEST)
        gold_structural_reports = [
            self._structural_evidence_validator.validate_structural(corpus.by_id()[evidence_id])
            for evidence_id in task.oracle.gold_evidence_ids
            if evidence_id in corpus.by_id()
        ]
        gold_domain_reports = [
            self._domain_evidence_validator.validate_domain(corpus.by_id()[evidence_id])
            for evidence_id in task.oracle.gold_evidence_ids
            if evidence_id in corpus.by_id()
        ]
        invalid_structural_evidence = tuple(
            item.evidence_id for item in gold_structural_reports if not item.passed
        )
        invalid_domain_evidence = tuple(
            item.evidence_id for item in gold_domain_reports if not item.passed
        )
        hard_gates = (
            HardGateResult(
                gate_id="required_check_manifest",
                scope=GateScope.UNIVERSAL,
                passed=not missing,
                details=missing,
            ),
            HardGateResult(
                gate_id="workflow_contract",
                scope=GateScope.UNIVERSAL,
                passed=all(
                    _check_passed(checks, item)
                    for item in (
                        "task_identity",
                        "candidate_workflow_kind",
                        "required_actions_present",
                        "step_statuses_succeeded",
                        "action_sequence_valid",
                    )
                ),
                details=failed,
            ),
            HardGateResult(
                gate_id="public_boundary_and_tools",
                scope=GateScope.UNIVERSAL,
                passed=all(
                    _check_passed(checks, item)
                    for item in ("public_only_generation", "allowed_tool_compliance")
                ),
                details=failed,
            ),
            HardGateResult(
                gate_id="evidence_retrieval_and_selection",
                scope=GateScope.UNIVERSAL,
                passed=not invalid_structural_evidence
                and all(
                    _check_passed(checks, item)
                    for item in (
                        "retrieved_evidence_known",
                        "retrieved_evidence_validity",
                        "selected_evidence_was_retrieved",
                        "evidence_recall",
                        "evidence_precision",
                    )
                ),
                details=invalid_structural_evidence + failed,
            ),
            HardGateResult(
                gate_id="domain_evidence_semantics",
                scope=GateScope.DOMAIN,
                passed=not invalid_domain_evidence
                and _check_passed(checks, "selected_evidence_validity")
                and _check_passed(checks, "source_grounding"),
                details=invalid_domain_evidence + failed,
            ),
            HardGateResult(
                gate_id="proof_and_operation",
                scope=GateScope.UNIVERSAL,
                passed=_check_passed(checks, "proof_graph_binding")
                and all(
                    _check_passed(checks, item)
                    for item in (
                        "execution_coverage",
                        "operation_grounding",
                        "tool_necessity",
                        "program_node_alignment",
                        "all_calculations_correct",
                        "verification_step_binding",
                        "operation_correctness",
                    )
                ),
                details=failed,
            ),
            HardGateResult(
                gate_id="answer_and_citation",
                scope=GateScope.UNIVERSAL,
                passed=all(
                    _check_passed(checks, item)
                    for item in (
                        "answer_schema_validity",
                        "answer_correctness",
                        "citation_binding",
                        "unsupported_claim_detection",
                    )
                ),
                details=failed,
            ),
            HardGateResult(
                gate_id="domain_claims",
                scope=GateScope.DOMAIN,
                passed=_check_passed(checks, "domain_claim_verification"),
                details=failed,
            ),
        )
        raw_scores = {
            "evidence": round(50 * report.evidence_recall + 50 * report.evidence_precision, 4),
            "reasoning": round(
                50 * (report.execution_coverage + report.operation_grounding_score),
                4,
            )
            if _check_passed(checks, "operation_correctness")
            else 0.0,
            "tool_use": round(100 * report.tool_necessity_score, 4)
            if _check_passed(checks, "allowed_tool_compliance")
            else 0.0,
            "verification": _boolean_score(
                _check_passed(checks, "proof_graph_binding")
                and _check_passed(checks, "public_only_generation")
                and all(item.verified for item in report.program_node_statuses)
            ),
            "answer": _boolean_score(
                _check_passed(checks, "answer_schema_validity")
                and _check_passed(checks, "answer_correctness")
                and _check_passed(checks, "citation_binding")
            ),
        }
        return _assessment(
            task=task,
            trajectory=trajectory,
            hard_gates=hard_gates,
            manifest=CANDIDATE_REQUIRED_CHECK_MANIFEST,
            raw_scores=raw_scores,
            weights=self._weights,
            diagnostic=DiagnosticQualityVector(
                evidence_validity=(report.evidence_recall + report.evidence_precision) / 2,
                proof_graph_coverage=float(_check_passed(checks, "proof_graph_binding")),
                operation_replay=float(_check_passed(checks, "operation_correctness")),
                citation_coverage=float(_check_passed(checks, "citation_binding")),
                workflow_completeness=float(_check_passed(checks, "required_actions_present")),
                execution_coverage=report.execution_coverage,
                operation_grounding=report.operation_grounding_score,
                tool_necessity=report.tool_necessity_score,
                program_depth=len(task.oracle.task_program.nodes),
            ),
            failed_check_ids=failed,
            check_failure_details=_failure_detail_map(checks, failed),
            evaluator_version=CANDIDATE_EVALUATOR_VERSION,
        )


class QualityEvaluator(ReferenceQualityEvaluator):
    """Backward-compatible name for the reference-only evaluator."""


def _assessment(
    *,
    task: TaskPackage,
    trajectory: Trajectory,
    hard_gates: tuple[HardGateResult, ...],
    manifest: tuple[str, ...],
    raw_scores: dict[str, float],
    weights: dict[str, float],
    diagnostic: DiagnosticQualityVector,
    evaluator_version: str,
    failed_check_ids: tuple[str, ...] = (),
    check_failure_details: dict[str, tuple[str, ...]] | None = None,
) -> QualityAssessment:
    dimensions = tuple(
        DimensionScore(
            dimension=name,
            score=score,
            weight=weights[name],
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
    manifest_hash = canonical_hash(manifest, prefix="check_manifest:")
    identity = {
        "task_id": task.task_id,
        "trajectory_id": trajectory.trajectory_id,
        "manifest_hash": manifest_hash,
        "evaluator_version": evaluator_version,
    }
    return QualityAssessment(
        assessment_id=canonical_hash(identity, prefix="assessment:"),
        task_id=task.task_id,
        trajectory_id=trajectory.trajectory_id,
        hard_gates=hard_gates,
        universal_gates=tuple(gate for gate in hard_gates if gate.scope == GateScope.UNIVERSAL),
        domain_gates=tuple(gate for gate in hard_gates if gate.scope == GateScope.DOMAIN),
        required_check_manifest_hash=manifest_hash,
        diagnostic_vector=diagnostic,
        dimensions=dimensions,
        total_score=total,
        decision=decision,
        fatal_failures=fatal_failures,
        failed_check_ids=failed_check_ids,
        check_failure_details=check_failure_details or {},
        evaluator_version=evaluator_version,
    )


def _failure_detail_map(
    checks: dict[str, Any], failed: tuple[str, ...]
) -> dict[str, tuple[str, ...]]:
    return {
        check_id: tuple(getattr(checks[check_id], "details", ()) or ())
        for check_id in failed
        if check_id in checks
    }


def _check_failures(
    checks: dict[str, Any], manifest: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    missing = tuple(check_id for check_id in manifest if check_id not in checks)
    failed = tuple(check_id for check_id in manifest if not _check_passed(checks, check_id))
    return missing, failed


def _check_passed(checks: dict[str, Any], check_id: str) -> bool:
    check = checks.get(check_id)
    return bool(check is not None and check.passed)


def _ratio_score(values) -> float:
    observed = list(values)
    if not observed:
        return 0.0
    return 100.0 * sum(bool(value) for value in observed) / len(observed)


def _boolean_score(value: bool) -> float:
    return 100.0 if value else 0.0


def _dimension_checks(dimension: str) -> tuple[str, ...]:
    return {
        "evidence": ("evidence_validity", "evidence_recall", "evidence_precision"),
        "reasoning": (
            "required_actions_present",
            "execution_coverage",
            "operation_grounding",
            "operation_correctness",
        ),
        "tool_use": ("allowed_tool_compliance", "tool_necessity", "search_action_present"),
        "verification": ("proof_graph_binding", "independent_program_replay"),
        "answer": ("answer_correctness", "citation_binding"),
    }[dimension]
