from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from trusted_synthesis.core.evaluation.answer import CandidateAnswerNormalizer
from trusted_synthesis.core.evaluation.citation import CitationVerifier
from trusted_synthesis.core.evaluation.leakage import OracleLeakageChecker
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.validation import EvidenceValidator
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.graph.validation import ProofGraphValidator
from trusted_synthesis.core.operations.program import (
    ProgramExecutionError,
    TaskProgramOracleVerifier,
)
from trusted_synthesis.core.operations.registry import OperationRegistry, default_registry
from trusted_synthesis.core.task.schema import TaskPackage, TaskRequirement
from trusted_synthesis.core.trajectory.schema import (
    ActionType,
    StepStatus,
    Trajectory,
    WorkflowKind,
)


class CandidateCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    passed: bool
    details: tuple[str, ...] = ()


class CandidateVerificationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trajectory_id: str
    checks: tuple[CandidateCheck, ...]
    retrieved_evidence_ids: tuple[str, ...]
    selected_evidence_ids: tuple[str, ...]
    evidence_recall: float = Field(ge=0, le=1)
    evidence_precision: float = Field(ge=0, le=1)
    normalized_candidate_answer: dict[str, Any]
    normalized_oracle_answer: dict[str, Any]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


class CandidateWorkflowVerifier:
    """Reconstruct candidate behavior and compare it with the isolated oracle."""

    def __init__(
        self,
        registry: OperationRegistry | None = None,
        semantic_policy: Any | None = None,
        claim_verifier: Any | None = None,
    ) -> None:
        self._oracle = TaskProgramOracleVerifier(registry or default_registry())
        self._normalizer = CandidateAnswerNormalizer()
        self._citation_verifier = CitationVerifier()
        self._leakage_checker = OracleLeakageChecker()
        self._evidence_validator = EvidenceValidator(semantic_policy)
        self._graph_validator = ProofGraphValidator()
        self._claim_verifier = claim_verifier

    def verify(
        self,
        task: TaskPackage,
        corpus: EvidenceCorpus,
        proof_graph: ProofGraph,
        candidate: Trajectory,
    ) -> CandidateVerificationReport:
        evidence_by_id = corpus.by_id()
        gold_ids = task.oracle.gold_evidence_ids
        retrieved_ids = _action_evidence(candidate, ActionType.SEARCH)
        selected_ids = _action_evidence(candidate, ActionType.SELECT_EVIDENCE)
        retrieved_set = set(retrieved_ids)
        selected_set = set(selected_ids)
        gold_set = set(gold_ids)
        recall = len(selected_set & gold_set) / len(gold_set) if gold_set else 1.0
        precision = len(selected_set & gold_set) / len(selected_set) if selected_set else 0.0
        retrieved_valid = all(
            item in evidence_by_id
            and self._evidence_validator.validate(evidence_by_id[item]).passed
            for item in retrieved_set
        )
        selected_valid = all(
            item in evidence_by_id
            and self._evidence_validator.validate(evidence_by_id[item]).passed
            for item in selected_set
        )
        try:
            expected = self._oracle.derive_expected(task.oracle.task_program, evidence_by_id)
            expected_output = expected.final_output
            operation_error: tuple[str, ...] = ()
        except ProgramExecutionError as exc:
            expected_output = {}
            operation_error = (str(exc),)
        gold_evidence = tuple(evidence_by_id[item] for item in gold_ids if item in evidence_by_id)
        normalized_candidate = self._normalizer.normalize_candidate(
            task.public, candidate.final_answer
        )
        normalized_oracle = self._normalizer.normalize_oracle(task, expected_output, gold_evidence)
        schema_passed, schema_failures = self._normalizer.validate_schema(
            task.public, candidate.final_answer
        )
        citations = self._citation_verifier.verify(
            candidate.final_answer.get("citations"), evidence_by_id, gold_ids
        )
        leakage = self._leakage_checker.verify(task.oracle, candidate)
        actions = {step.action for step in candidate.steps}
        required_actions = _required_actions(task)
        used_tools = {step.tool_name for step in candidate.steps if step.tool_name}
        unsupported_claims = _unsupported_claims(candidate.final_answer)
        claim_failures = _verify_claims(
            candidate.final_answer,
            tuple(evidence_by_id[item] for item in selected_ids if item in evidence_by_id),
            self._claim_verifier,
        )
        graph_report = self._graph_validator.validate(proof_graph, corpus.as_bundle(), gold_ids)
        calculation_outputs = [
            step.observation.get("result")
            for step in candidate.steps
            if step.action == ActionType.CALCULATE
        ]
        calculation_required = TaskRequirement.CALCULATE in task.public.requirements
        operation_correct = not operation_error and (
            not calculation_required
            or any(
                self._normalizer.equivalent(
                    self._normalizer.normalize_result(task.public, output),
                    normalized_oracle,
                )
                for output in calculation_outputs
            )
        )
        checks = (
            _check("task_identity", candidate.task_id == task.task_id),
            _check("candidate_workflow_kind", candidate.workflow_kind == WorkflowKind.CANDIDATE),
            _check("public_only_generation", leakage.passed, leakage.failures),
            _check(
                "allowed_tool_compliance",
                used_tools.issubset(set(task.public.allowed_tools)),
                tuple(sorted(used_tools - set(task.public.allowed_tools))),
            ),
            _check(
                "required_actions_present",
                required_actions.issubset(actions),
                tuple(sorted(item.value for item in required_actions - actions)),
            ),
            _check(
                "step_statuses_succeeded",
                all(step.status == StepStatus.SUCCEEDED for step in candidate.steps),
            ),
            _check(
                "retrieved_evidence_known",
                retrieved_set.issubset(evidence_by_id),
                tuple(sorted(retrieved_set - set(evidence_by_id))),
            ),
            _check("retrieved_evidence_validity", retrieved_valid),
            _check("selected_evidence_was_retrieved", selected_set.issubset(retrieved_set)),
            _check("selected_evidence_validity", selected_valid),
            _check("evidence_recall", recall == 1.0, (f"recall={recall:.6f}",)),
            _check("evidence_precision", precision == 1.0, (f"precision={precision:.6f}",)),
            _check(
                "proof_graph_binding",
                proof_graph.graph_id == task.oracle.proof_graph_id
                and proof_graph.graph_hash == task.oracle.proof_graph_hash
                and graph_report.passed,
            ),
            _check("operation_correctness", operation_correct, operation_error),
            _check("answer_schema_validity", schema_passed, schema_failures),
            _check(
                "answer_correctness",
                self._normalizer.equivalent(normalized_candidate, normalized_oracle),
            ),
            _check("citation_binding", citations.passed, citations.failures),
            _check(
                "unsupported_claim_detection",
                not unsupported_claims,
                unsupported_claims,
            ),
            _check("domain_claim_verification", not claim_failures, claim_failures),
        )
        return CandidateVerificationReport(
            trajectory_id=candidate.trajectory_id,
            checks=checks,
            retrieved_evidence_ids=retrieved_ids,
            selected_evidence_ids=selected_ids,
            evidence_recall=recall,
            evidence_precision=precision,
            normalized_candidate_answer=normalized_candidate,
            normalized_oracle_answer=normalized_oracle,
        )


def _action_evidence(candidate: Trajectory, action: ActionType) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            item for step in candidate.steps if step.action == action for item in step.evidence_ids
        )
    )


def _required_actions(task: TaskPackage) -> set[ActionType]:
    mapping = {
        TaskRequirement.RETRIEVE_EVIDENCE: ActionType.SEARCH,
        TaskRequirement.SELECT_EVIDENCE: ActionType.SELECT_EVIDENCE,
        TaskRequirement.CALCULATE: ActionType.CALCULATE,
        TaskRequirement.VERIFY_RESULT: ActionType.VERIFY,
    }
    return {mapping[item] for item in task.public.requirements if item in mapping} | {
        ActionType.PLAN,
        ActionType.ANSWER,
    }


def _unsupported_claims(final_answer: dict[str, Any]) -> tuple[str, ...]:
    failures = []
    result = final_answer.get("result")
    status = final_answer.get("status")
    if isinstance(result, dict):
        status = status or result.get("status")
    if status in {"insufficient_capability", "unsupported_payload"}:
        failures.append("candidate_reported_failure_status")
    return tuple(failures)


def _verify_claims(
    final_answer: dict[str, Any], evidence: tuple, claim_verifier: Any | None
) -> tuple[str, ...]:
    claims = final_answer.get("claims") or ()
    if not claims:
        return ()
    if not isinstance(claims, list):
        return ("claims_not_array",)
    if claim_verifier is None:
        return ("claim_verifier_not_registered",)
    failures = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            failures.append(f"claim_{index}_not_object")
            continue
        report = claim_verifier.verify_claim(claim, evidence)
        failures.extend(f"claim_{index}:{issue}" for issue in report.issues)
    return tuple(failures)


def _check(check_id: str, passed: bool, details: tuple[str, ...] = ()) -> CandidateCheck:
    return CandidateCheck(check_id=check_id, passed=passed, details=details)
