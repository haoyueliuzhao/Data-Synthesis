from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from trusted_synthesis.core.evaluation.answer import CandidateAnswerNormalizer
from trusted_synthesis.core.evaluation.citation import CitationVerifier
from trusted_synthesis.core.evaluation.grounding import (
    evaluate_source_grounding,
    grounding_requirement,
)
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
from trusted_synthesis.core.plugins import (
    ClaimVerifierProtocol,
    SemanticPolicyProtocol,
    SourceGroundingVerifierProtocol,
)
from trusted_synthesis.core.task.program import InputRefKind
from trusted_synthesis.core.task.schema import PlanningTrack, TaskPackage, TaskRequirement
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
        semantic_policy: SemanticPolicyProtocol | None = None,
        claim_verifier: ClaimVerifierProtocol | None = None,
        source_grounding_verifier: SourceGroundingVerifierProtocol | None = None,
    ) -> None:
        self._oracle = TaskProgramOracleVerifier(registry or default_registry())
        self._normalizer = CandidateAnswerNormalizer()
        self._citation_verifier = CitationVerifier()
        self._leakage_checker = OracleLeakageChecker()
        self._retrieved_evidence_validator = EvidenceValidator()
        self._selected_evidence_validator = EvidenceValidator(semantic_policy)
        self._graph_validator = ProofGraphValidator()
        self._claim_verifier = claim_verifier
        self._source_grounding_verifier = source_grounding_verifier

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
            and self._retrieved_evidence_validator.validate_retrievable(evidence_by_id[item]).passed
            for item in retrieved_set
        )
        selected_valid = all(
            item in evidence_by_id
            and self._selected_evidence_validator.validate(evidence_by_id[item]).passed
            for item in selected_set
        )
        try:
            expected = self._oracle.derive_expected(task.oracle.task_program, evidence_by_id)
            expected_output = expected.final_output
            expected_node_outputs = expected.node_outputs
            operation_error: tuple[str, ...] = ()
        except ProgramExecutionError as exc:
            expected_output = {}
            expected_node_outputs = {}
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
            expected_node_outputs,
        )
        graph_report = self._graph_validator.validate(proof_graph, corpus.as_bundle(), gold_ids)
        action_sequence_failures = _verify_action_sequence(candidate, task)
        trace_failures, node_mapping = _verify_program_trace(
            task,
            candidate,
            expected_node_outputs,
        )
        verification_failures = _verify_result_step(task, candidate, expected_output, node_mapping)
        source_grounding = evaluate_source_grounding(
            tuple(evidence_by_id[item] for item in selected_ids if item in evidence_by_id),
            grounding_requirement(task.public.metadata),
            self._source_grounding_verifier,
        )
        operation_correct = not operation_error and not trace_failures
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
                "action_sequence_valid",
                not action_sequence_failures,
                action_sequence_failures,
            ),
            _check(
                "retrieved_evidence_known",
                retrieved_set.issubset(evidence_by_id),
                tuple(sorted(retrieved_set - set(evidence_by_id))),
            ),
            _check("retrieved_evidence_validity", retrieved_valid),
            _check("selected_evidence_was_retrieved", selected_set.issubset(retrieved_set)),
            _check("selected_evidence_validity", selected_valid),
            _check(
                "source_grounding",
                source_grounding.passed,
                (
                    f"status={source_grounding.status.value}",
                    *source_grounding.failures,
                ),
            ),
            _check("evidence_recall", recall == 1.0, (f"recall={recall:.6f}",)),
            _check("evidence_precision", precision == 1.0, (f"precision={precision:.6f}",)),
            _check(
                "proof_graph_binding",
                proof_graph.graph_id == task.oracle.proof_graph_id
                and proof_graph.graph_hash == task.oracle.proof_graph_hash
                and graph_report.passed,
            ),
            _check(
                "program_node_alignment",
                not trace_failures,
                trace_failures,
            ),
            _check(
                "all_calculations_correct",
                operation_correct,
                operation_error + trace_failures,
            ),
            _check(
                "verification_step_binding",
                not verification_failures,
                verification_failures,
            ),
            _check("operation_correctness", operation_correct, operation_error + trace_failures),
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
    failures: list[str] = []
    result = final_answer.get("result")
    status = final_answer.get("status")
    if isinstance(result, dict):
        status = status or result.get("status")
    if status in {"insufficient_capability", "unsupported_payload"}:
        failures.append("candidate_reported_failure_status")
    return tuple(failures)


def _verify_claims(
    final_answer: dict[str, Any],
    evidence: tuple,
    claim_verifier: ClaimVerifierProtocol | None,
    operation_outputs: dict[str, dict[str, Any]],
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
        report = claim_verifier.verify_claim(
            claim,
            evidence,
            operation_outputs=operation_outputs,
        )
        failures.extend(f"claim_{index}:{issue}" for issue in report.issues)
    return tuple(failures)


def _verify_action_sequence(candidate: Trajectory, task: TaskPackage) -> tuple[str, ...]:
    order = {
        ActionType.PLAN: 0,
        ActionType.SEARCH: 1,
        ActionType.SELECT_EVIDENCE: 2,
        ActionType.CALCULATE: 3,
        ActionType.VERIFY: 4,
        ActionType.ANSWER: 5,
    }
    failures: list[str] = []
    ranks = [order[step.action] for step in candidate.steps]
    if ranks != sorted(ranks):
        failures.append("action_order_not_monotonic")
    counts = {action: sum(step.action == action for step in candidate.steps) for action in order}
    for action in (ActionType.PLAN, ActionType.SEARCH, ActionType.ANSWER):
        if counts[action] != 1:
            failures.append(f"{action.value}_count={counts[action]}")
    if counts[ActionType.SELECT_EVIDENCE] < 1:
        failures.append("select_evidence_missing")
    calculation_required = TaskRequirement.CALCULATE in task.public.requirements
    if calculation_required and counts[ActionType.CALCULATE] < 1:
        failures.append("calculate_missing")
    verification_required = TaskRequirement.VERIFY_RESULT in task.public.requirements
    if counts[ActionType.VERIFY] != int(verification_required):
        failures.append(f"verify_count={counts[ActionType.VERIFY]}")
    return tuple(failures)


def _verify_program_trace(
    task: TaskPackage,
    candidate: Trajectory,
    expected_outputs: dict[str, dict[str, Any]],
) -> tuple[tuple[str, ...], dict[str, str]]:
    if task.public.planning_track == PlanningTrack.PLAN_HIDDEN:
        return _verify_plan_hidden_trace(task, candidate, expected_outputs)
    failures = _verify_plan_given_trace(task, candidate, expected_outputs)
    return failures, {node.node_id: node.node_id for node in task.oracle.task_program.nodes}


def _verify_plan_given_trace(
    task: TaskPackage,
    candidate: Trajectory,
    expected_outputs: dict[str, dict[str, Any]],
) -> tuple[str, ...]:
    program = task.oracle.task_program
    nodes = {node.node_id: node for node in program.nodes}
    failures: list[str] = []
    mapped_steps: dict[str, list] = {}
    for step in candidate.steps:
        if step.action not in {ActionType.SELECT_EVIDENCE, ActionType.CALCULATE}:
            continue
        if step.program_node_id is None:
            if step.action == ActionType.CALCULATE:
                failures.append(f"step:{step.step_index}:unbound_calculation")
            continue
        mapped_steps.setdefault(step.program_node_id, []).append(step)
        if step.program_node_id not in nodes:
            failures.append(f"step:{step.step_index}:unknown_program_node:{step.program_node_id}")
    step_index_by_node: dict[str, int] = {}
    for node in program.nodes:
        steps = mapped_steps.get(node.node_id, [])
        if len(steps) != 1:
            failures.append(f"node:{node.node_id}:execution_count={len(steps)}")
            continue
        step = steps[0]
        step_index_by_node[node.node_id] = step.step_index
        expected_action = (
            ActionType.SELECT_EVIDENCE if node.operator_id == "lookup" else ActionType.CALCULATE
        )
        if step.action != expected_action:
            failures.append(
                f"node:{node.node_id}:step:{step.step_index}:action={step.action.value}"
            )
        if step.operator_id != node.operator_id:
            failures.append(
                f"node:{node.node_id}:step:{step.step_index}:operator={step.operator_id}"
            )
        expected_refs = tuple(_program_ref(ref) for ref in node.input_refs)
        if step.input_refs != expected_refs:
            failures.append(f"node:{node.node_id}:step:{step.step_index}:input_refs")
        if step.output_ref != f"operation:{node.node_id}":
            failures.append(f"node:{node.node_id}:step:{step.step_index}:output_ref")
        observed = step.observation.get("result")
        expected = expected_outputs.get(node.node_id)
        if not _values_equivalent(observed, expected):
            failures.append(f"node:{node.node_id}:step:{step.step_index}:output_mismatch")
        expected_evidence = {
            ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.EVIDENCE
        }
        if expected_evidence and set(step.evidence_ids) != expected_evidence:
            failures.append(f"node:{node.node_id}:step:{step.step_index}:evidence_binding")
    for node in program.nodes:
        current_index = step_index_by_node.get(node.node_id)
        if current_index is None:
            continue
        for dependency in node.dependencies:
            dependency_index = step_index_by_node.get(dependency)
            if dependency_index is None or dependency_index >= current_index:
                failures.append(f"node:{node.node_id}:dependency_order:{dependency}")
    return tuple(failures)


def _verify_plan_hidden_trace(
    task: TaskPackage,
    candidate: Trajectory,
    expected_outputs: dict[str, dict[str, Any]],
) -> tuple[tuple[str, ...], dict[str, str]]:
    program = task.oracle.task_program
    candidate_steps = tuple(
        step
        for step in candidate.steps
        if step.action in {ActionType.SELECT_EVIDENCE, ActionType.CALCULATE}
        and step.program_node_id is not None
    )
    failures: list[str] = []
    mapping: dict[str, str] = {}
    mapped_step_indexes: dict[str, int] = {}
    used_step_indexes: set[int] = set()
    used_program_node_ids: set[str] = set()
    for node in program.nodes:
        expected_action = (
            ActionType.SELECT_EVIDENCE if node.operator_id == "lookup" else ActionType.CALCULATE
        )
        expected_refs = _translated_program_refs(node, mapping)
        candidates = [
            step
            for step in candidate_steps
            if step.step_index not in used_step_indexes
            and step.action == expected_action
            and step.operator_id == node.operator_id
            and step.input_refs == expected_refs
        ]
        if len(candidates) != 1:
            failures.append(f"node:{node.node_id}:semantic_execution_count={len(candidates)}")
            continue
        step = candidates[0]
        assert step.program_node_id is not None
        if step.program_node_id in used_program_node_ids:
            failures.append(f"node:{node.node_id}:duplicate_candidate_node_id")
            continue
        dependency_indexes = [
            mapped_step_indexes[item] for item in node.dependencies if item in mapped_step_indexes
        ]
        if dependency_indexes and step.step_index <= max(dependency_indexes):
            failures.append(f"node:{node.node_id}:dependency_order")
            continue
        mapping[node.node_id] = step.program_node_id
        mapped_step_indexes[node.node_id] = step.step_index
        used_step_indexes.add(step.step_index)
        used_program_node_ids.add(step.program_node_id)
        if step.output_ref != f"operation:{step.program_node_id}":
            failures.append(f"node:{node.node_id}:step:{step.step_index}:output_ref")
        if not _values_equivalent(
            step.observation.get("result"), expected_outputs.get(node.node_id)
        ):
            failures.append(f"node:{node.node_id}:step:{step.step_index}:output_mismatch")
        expected_evidence = {
            ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.EVIDENCE
        }
        if expected_evidence and set(step.evidence_ids) != expected_evidence:
            failures.append(f"node:{node.node_id}:step:{step.step_index}:evidence_binding")
    unused = [
        step.step_index for step in candidate_steps if step.step_index not in used_step_indexes
    ]
    if unused:
        failures.append(f"unmapped_candidate_steps:{','.join(str(item) for item in unused)}")
    return tuple(failures), mapping


def _translated_program_refs(node, mapping: dict[str, str]) -> tuple[str, ...]:
    refs = []
    for ref in node.input_refs:
        ref_id = ref.ref_id
        if ref.kind == InputRefKind.OPERATION:
            if ref_id not in mapping:
                return ()
            ref_id = mapping[ref_id]
        value = f"{ref.kind.value}:{ref_id}"
        refs.append(f"{value}#{ref.selector}" if ref.selector else value)
    return tuple(refs)


def _program_ref(ref) -> str:
    value = f"{ref.kind.value}:{ref.ref_id}"
    return f"{value}#{ref.selector}" if ref.selector else value


def _verify_result_step(
    task: TaskPackage,
    candidate: Trajectory,
    expected_output: dict[str, Any],
    node_mapping: dict[str, str],
) -> tuple[str, ...]:
    if TaskRequirement.VERIFY_RESULT not in task.public.requirements:
        return ()
    steps = [step for step in candidate.steps if step.action == ActionType.VERIFY]
    if len(steps) != 1:
        return (f"verify_step_count={len(steps)}",)
    step = steps[0]
    oracle_output_node = task.oracle.task_program.output_node_id
    candidate_output_node = node_mapping.get(oracle_output_node)
    if candidate_output_node is None:
        return ("verify_output_node_unmapped",)
    expected_ref = f"operation:{candidate_output_node}"
    failures = []
    if step.program_node_id != candidate_output_node:
        failures.append(f"step:{step.step_index}:verify_program_node")
    if step.input_refs != (expected_ref,):
        failures.append(f"step:{step.step_index}:verify_input_ref")
    if step.observation.get("verified_output_ref") != expected_ref:
        failures.append(f"step:{step.step_index}:verified_output_ref")
    if not _values_equivalent(step.observation.get("verified_result"), expected_output):
        failures.append(f"step:{step.step_index}:verified_result")
    return tuple(failures)


def _values_equivalent(left: Any, right: Any) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(
            _values_equivalent(left[key], right[key]) for key in left
        )
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(
            _values_equivalent(a, b) for a, b in zip(left, right, strict=True)
        )
    try:
        return Decimal(str(left)).normalize() == Decimal(str(right)).normalize()
    except (InvalidOperation, TypeError, ValueError):
        return left == right


def _check(check_id: str, passed: bool, details: tuple[str, ...] = ()) -> CandidateCheck:
    return CandidateCheck(check_id=check_id, passed=passed, details=details)
