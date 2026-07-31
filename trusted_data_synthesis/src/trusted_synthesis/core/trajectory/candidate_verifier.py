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


class ProgramNodeExecutionStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    program_node_id: str
    candidate_node_id: str | None = None
    planned: bool = True
    executed: bool = False
    observed: bool = False
    grounded: bool = False
    verified: bool = False
    tool_bound: bool = False
    details: tuple[str, ...] = ()


class CandidateVerificationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trajectory_id: str
    checks: tuple[CandidateCheck, ...]
    retrieved_evidence_ids: tuple[str, ...]
    selected_evidence_ids: tuple[str, ...]
    evidence_recall: float = Field(ge=0, le=1)
    evidence_precision: float = Field(ge=0, le=1)
    required_program_node_count: int = Field(ge=0)
    executed_program_node_count: int = Field(ge=0)
    execution_coverage: float = Field(ge=0, le=1)
    grounded_operation_count: int = Field(ge=0)
    operation_grounding_score: float = Field(ge=0, le=1)
    tool_bound_operation_count: int = Field(ge=0)
    tool_necessity_score: float = Field(ge=0, le=1)
    program_node_statuses: tuple[ProgramNodeExecutionStatus, ...]
    program_node_mapping: dict[str, str]
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
        resolved_registry = registry or default_registry()
        self._registry = resolved_registry
        self._oracle = TaskProgramOracleVerifier(resolved_registry)
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
        normalized_oracle = self._normalizer.normalize_oracle(
            task,
            expected_output,
            gold_evidence,
            node_outputs=expected_node_outputs,
        )
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
        node_statuses = _program_execution_statuses(
            task,
            candidate,
            expected_node_outputs,
            node_mapping,
            selected_set,
            self._registry,
        )
        required_node_count = len(node_statuses)
        executed_node_count = sum(item.executed for item in node_statuses)
        grounded_operation_count = sum(item.grounded for item in node_statuses)
        tool_bound_operation_count = sum(
            item.executed and item.tool_bound for item in node_statuses
        )
        execution_coverage = _ratio(executed_node_count, required_node_count)
        operation_grounding_score = _ratio(
            grounded_operation_count,
            required_node_count,
        )
        search_required = TaskRequirement.RETRIEVE_EVIDENCE in task.public.requirements
        search_tool_bound = any(
            step.action == ActionType.SEARCH
            and step.status == StepStatus.SUCCEEDED
            and step.tool_name == "evidence.search"
            for step in candidate.steps
        )
        tool_necessity_score = _ratio(
            tool_bound_operation_count + int(search_required and search_tool_bound),
            required_node_count + int(search_required),
        )
        normalized_candidate_for_comparison = _translate_operation_refs(
            normalized_candidate,
            {candidate_id: oracle_id for oracle_id, candidate_id in node_mapping.items()},
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
                "execution_coverage",
                execution_coverage == 1.0,
                (
                    f"coverage={execution_coverage:.6f}",
                    *(
                        f"node:{item.program_node_id}:not_executed"
                        for item in node_statuses
                        if not item.executed
                    ),
                ),
            ),
            _check(
                "operation_grounding",
                operation_grounding_score == 1.0,
                (
                    f"score={operation_grounding_score:.6f}",
                    *(
                        f"node:{item.program_node_id}:{','.join(item.details)}"
                        for item in node_statuses
                        if not item.grounded
                    ),
                ),
            ),
            _check(
                "tool_necessity",
                tool_necessity_score == 1.0,
                (
                    f"score={tool_necessity_score:.6f}",
                    *(
                        f"node:{item.program_node_id}:tool_binding"
                        for item in node_statuses
                        if item.executed and not item.tool_bound
                    ),
                ),
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
                self._normalizer.equivalent(
                    normalized_candidate_for_comparison,
                    normalized_oracle,
                ),
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
            required_program_node_count=required_node_count,
            executed_program_node_count=executed_node_count,
            execution_coverage=execution_coverage,
            grounded_operation_count=grounded_operation_count,
            operation_grounding_score=operation_grounding_score,
            tool_bound_operation_count=tool_bound_operation_count,
            tool_necessity_score=tool_necessity_score,
            program_node_statuses=node_statuses,
            program_node_mapping={
                candidate_id: oracle_id for oracle_id, candidate_id in sorted(node_mapping.items())
            },
            normalized_candidate_answer=normalized_candidate_for_comparison,
            normalized_oracle_answer=normalized_oracle,
        )


def _program_execution_statuses(
    task: TaskPackage,
    candidate: Trajectory,
    expected_outputs: dict[str, dict[str, Any]],
    node_mapping: dict[str, str],
    selected_evidence_ids: set[str],
    registry: OperationRegistry,
) -> tuple[ProgramNodeExecutionStatus, ...]:
    operation_steps = tuple(
        step
        for step in candidate.steps
        if step.action in {ActionType.SELECT_EVIDENCE, ActionType.CALCULATE}
        and step.program_node_id is not None
    )
    step_indexes = {
        step.program_node_id: step.step_index
        for step in operation_steps
        if step.program_node_id is not None
    }
    expected_lineage_by_node: dict[str, set[str]] = {}
    for node in task.oracle.task_program.nodes:
        lineage = {ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.EVIDENCE}
        for dependency in node.dependencies:
            lineage.update(expected_lineage_by_node[dependency])
        expected_lineage_by_node[node.node_id] = lineage

    statuses = []
    for node in task.oracle.task_program.nodes:
        candidate_node_id = node_mapping.get(node.node_id)
        matches = tuple(
            step
            for step in operation_steps
            if candidate_node_id is not None and step.program_node_id == candidate_node_id
        )
        details: list[str] = []
        if len(matches) != 1:
            details.append(f"execution_count={len(matches)}")
            statuses.append(
                ProgramNodeExecutionStatus(
                    program_node_id=node.node_id,
                    candidate_node_id=candidate_node_id,
                    details=tuple(details),
                )
            )
            continue
        step = matches[0]
        executed = step.status == StepStatus.SUCCEEDED
        if not executed:
            details.append("status_failed")
        observed = isinstance(step.observation.get("result"), dict)
        if not observed:
            details.append("observation_missing")
        expected_action = (
            ActionType.SELECT_EVIDENCE if node.operator_id == "lookup" else ActionType.CALCULATE
        )
        if step.action != expected_action:
            details.append("action_mismatch")
        if step.operator_id != node.operator_id:
            details.append("operator_mismatch")
        expected_refs = (
            _translated_program_refs(node, node_mapping)
            if task.public.planning_track == PlanningTrack.PLAN_HIDDEN
            else tuple(_program_ref(ref) for ref in node.input_refs)
        )
        if step.input_refs != expected_refs:
            details.append("input_ref_mismatch")
        if not _values_equivalent(
            step.tool_input.get("parameters", {}),
            node.parameters,
        ):
            details.append("parameter_mismatch")
        if step.output_ref != f"operation:{candidate_node_id}":
            details.append("output_ref_mismatch")
        expected_evidence = {
            ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.EVIDENCE
        }
        expected_lineage = expected_lineage_by_node[node.node_id]
        observed_evidence = set(step.evidence_ids)
        if observed_evidence not in (expected_evidence, expected_lineage):
            details.append("evidence_binding_mismatch")
        if not set(step.evidence_ids).issubset(selected_evidence_ids):
            details.append("evidence_not_selected")
        for dependency in node.dependencies:
            dependency_candidate_id = node_mapping.get(dependency)
            dependency_index = (
                None
                if dependency_candidate_id is None
                else step_indexes.get(dependency_candidate_id)
            )
            if dependency_index is None or dependency_index >= step.step_index:
                details.append(f"dependency_order:{dependency}")
        definition = registry.require(node.operator_id)
        tool_bound = step.tool_name == definition.tool_capability
        if not tool_bound:
            details.append("tool_binding_mismatch")
        grounding_failures = {
            "status_failed",
            "observation_missing",
            "action_mismatch",
            "operator_mismatch",
            "input_ref_mismatch",
            "parameter_mismatch",
            "output_ref_mismatch",
            "evidence_binding_mismatch",
            "evidence_not_selected",
        }
        grounded = executed and not any(
            detail in grounding_failures or detail.startswith("dependency_order:")
            for detail in details
        )
        expected_output = expected_outputs.get(node.node_id)
        if task.public.planning_track == PlanningTrack.PLAN_HIDDEN:
            expected_output = _translate_operation_refs(expected_output, node_mapping)
        verified = observed and _values_equivalent(
            step.observation.get("result"),
            expected_output,
        )
        if not verified:
            details.append("output_mismatch")
        statuses.append(
            ProgramNodeExecutionStatus(
                program_node_id=node.node_id,
                candidate_node_id=candidate_node_id,
                executed=executed,
                observed=observed,
                grounded=grounded,
                verified=verified,
                tool_bound=tool_bound,
                details=tuple(details),
            )
        )
    return tuple(statuses)


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


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
        if not _values_equivalent(
            step.tool_input.get("parameters", {}),
            node.parameters,
        ):
            failures.append(f"node:{node.node_id}:step:{step.step_index}:parameters")
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
            step.tool_input.get("parameters", {}),
            node.parameters,
        ):
            failures.append(f"node:{node.node_id}:step:{step.step_index}:parameters")
        expected_output = _translate_operation_refs(
            expected_outputs.get(node.node_id),
            mapping,
        )
        if not _values_equivalent(step.observation.get("result"), expected_output):
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
    candidate_expected_output = _translate_operation_refs(expected_output, node_mapping)
    if not _values_equivalent(
        step.observation.get("verified_result"),
        candidate_expected_output,
    ):
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


def _translate_operation_refs(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _translate_operation_refs(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [_translate_operation_refs(item, mapping) for item in value]
    if isinstance(value, tuple):
        return tuple(_translate_operation_refs(item, mapping) for item in value)
    if isinstance(value, str) and value.startswith("operation:"):
        node_id, separator, selector = value.removeprefix("operation:").partition("#")
        translated = mapping.get(node_id, node_id)
        suffix = f"#{selector}" if separator else ""
        return f"operation:{translated}{suffix}"
    return value


def _check(check_id: str, passed: bool, details: tuple[str, ...] = ()) -> CandidateCheck:
    return CandidateCheck(check_id=check_id, passed=passed, details=details)
