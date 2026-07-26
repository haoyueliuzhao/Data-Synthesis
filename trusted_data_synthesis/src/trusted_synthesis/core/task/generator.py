from __future__ import annotations

from typing import Any

from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.graph.validation import ProofGraphValidator
from trusted_synthesis.core.task.program import (
    InputRefKind,
    OperationNode,
    ProgramInputRef,
    TaskProgram,
    make_program,
)
from trusted_synthesis.core.task.schema import (
    RetrievalTrack,
    TaskLevel,
    TaskOracleContract,
    TaskPackage,
    TaskPublicSpec,
    TaskRequirement,
)
from trusted_synthesis.hashing import canonical_hash


class TaskSynthesisError(ValueError):
    pass


class ProofGraphTaskSynthesizer:
    """Create a public task and a separately addressable oracle contract."""

    def __init__(self, semantic_policy: Any | None = None) -> None:
        self._semantic_policy = semantic_policy
        self._proof_validator = ProofGraphValidator()

    def fact_retrieval(
        self, proof_graph: ProofGraph, bundle: EvidenceBundle, evidence_id: str
    ) -> TaskPackage:
        item = self._find(bundle, evidence_id)
        self._validate_domain_evidence(item)
        self._require_graph_evidence(proof_graph, bundle, (evidence_id,))
        node = _operation_node("result", "lookup", (evidence_id,), "payload")
        return self._package(
            task_type="fact_retrieval",
            level=TaskLevel.FACT_RETRIEVAL,
            instruction=(
                f"What is {item.subject.name}'s {item.predicate}{_time_phrase(item)}? "
                "Report the result and identify the source."
            ),
            evidence=(item,),
            bundle=bundle,
            proof_graph=proof_graph,
            program=make_program((node,), node.node_id),
            answer_schema={
                "type": "payload_with_source",
                "payload_kind": item.evidence_kind.value,
            },
        )

    def comparison(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        left_evidence_id: str,
        right_evidence_id: str,
    ) -> TaskPackage:
        left = self._find(bundle, left_evidence_id)
        right = self._find(bundle, right_evidence_id)
        self._validate_comparable(left, right)
        evidence_ids = (left_evidence_id, right_evidence_id)
        self._require_graph_evidence(proof_graph, bundle, evidence_ids)
        node = _operation_node("result", "compare", evidence_ids, "comparison")
        return self._package(
            task_type="comparison",
            level=TaskLevel.EVIDENCE_INTEGRATION,
            instruction=(
                f"Compare {left.predicate} for {left.subject.name}{_time_phrase(left)} "
                f"with {right.subject.name}{_time_phrase(right)}. Which is higher, and by how much?"
            ),
            evidence=(left, right),
            bundle=bundle,
            proof_graph=proof_graph,
            program=make_program((node,), node.node_id),
            answer_schema={
                **_scalar_answer_schema(left, "comparison"),
                "required_fields": ["higher_ref", "difference"],
            },
        )

    def temporal_growth(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        earlier_evidence_id: str,
        later_evidence_id: str,
    ) -> TaskPackage:
        earlier = self._find(bundle, earlier_evidence_id)
        later = self._find(bundle, later_evidence_id)
        self._validate_same_series(earlier, later)
        evidence_ids = (earlier_evidence_id, later_evidence_id)
        self._require_graph_evidence(proof_graph, bundle, evidence_ids)
        earlier_node = _operation_node("earlier_value", "lookup", (earlier_evidence_id,), "payload")
        later_node = _operation_node("later_value", "lookup", (later_evidence_id,), "payload")
        growth_node = OperationNode(
            node_id="result",
            operator_id="growth",
            input_refs=(
                ProgramInputRef(
                    kind=InputRefKind.OPERATION,
                    ref_id=earlier_node.node_id,
                    selector="payload.value",
                ),
                ProgramInputRef(
                    kind=InputRefKind.OPERATION,
                    ref_id=later_node.node_id,
                    selector="payload.value",
                ),
            ),
            output_schema="percentage",
            verifier_id="growth.oracle.v1",
            dependencies=(earlier_node.node_id, later_node.node_id),
        )
        return self._package(
            task_type="temporal_growth",
            level=TaskLevel.RESEARCH_WORKFLOW,
            instruction=(
                f"How much did {earlier.subject.name}'s {earlier.predicate} change from "
                f"{_time_label(earlier)} to {_time_label(later)}? Report the percentage change."
            ),
            evidence=(earlier, later),
            bundle=bundle,
            proof_graph=proof_graph,
            program=make_program((earlier_node, later_node, growth_node), "result"),
            answer_schema={"type": "percentage", "unit": "percent"},
        )

    def temporal_average(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        evidence_ids: tuple[str, ...],
    ) -> TaskPackage:
        if len(evidence_ids) < 3:
            raise TaskSynthesisError("temporal average requires at least three observations")
        evidence = tuple(self._find(bundle, evidence_id) for evidence_id in evidence_ids)
        ordered = tuple(sorted(evidence, key=_temporal_sort_key))
        self._validate_temporal_series(ordered)
        ordered_ids = tuple(item.evidence_id for item in ordered)
        self._require_graph_evidence(proof_graph, bundle, ordered_ids)
        lookup_nodes = tuple(
            _operation_node(f"value_{index}", "lookup", (item.evidence_id,), "payload")
            for index, item in enumerate(ordered, start=1)
        )
        result = OperationNode(
            node_id="result",
            operator_id="aggregate",
            input_refs=tuple(
                ProgramInputRef(
                    kind=InputRefKind.OPERATION,
                    ref_id=node.node_id,
                    selector="payload.value",
                )
                for node in lookup_nodes
            ),
            parameters={"method": "mean"},
            output_schema="scalar",
            verifier_id="aggregate.oracle.v1",
            dependencies=tuple(node.node_id for node in lookup_nodes),
        )
        first = ordered[0]
        return self._package(
            task_type="temporal_average",
            level=TaskLevel.RESEARCH_WORKFLOW,
            instruction=(
                f"What was the mean {first.predicate} for {first.subject.name} across "
                f"{_time_label(ordered[0])} through {_time_label(ordered[-1])}? "
                "Use every listed observation and identify the sources."
            ),
            evidence=ordered,
            bundle=bundle,
            proof_graph=proof_graph,
            program=make_program((*lookup_nodes, result), "result"),
            answer_schema={
                **_scalar_answer_schema(first, "aggregate"),
                "method": "mean",
                "required_fields": ["method", "value"],
            },
        )

    def _package(
        self,
        *,
        task_type: str,
        level: TaskLevel,
        instruction: str,
        evidence: tuple[EvidenceItem, ...],
        bundle: EvidenceBundle,
        proof_graph: ProofGraph,
        program: TaskProgram,
        answer_schema: dict[str, Any],
    ) -> TaskPackage:
        evidence_ids = tuple(item.evidence_id for item in evidence)
        task_id = canonical_hash(
            {
                "task_type": task_type,
                "bundle_id": bundle.bundle_id,
                "evidence_ids": evidence_ids,
                "program_hash": program.program_hash,
                "schema": "task_package.v3",
            },
            prefix="task:",
        )
        public = TaskPublicSpec(
            task_id=task_id,
            domain=evidence[0].domain,
            task_type=task_type,
            level=level,
            instruction=instruction,
            requirements=_requirements_for_program(program),
            allowed_tools=_allowed_tools_for_program(program),
            retrieval_track=RetrievalTrack.RESOLVED,
            retrieval_scope={
                "subject_ids": sorted({item.subject.subject_id for item in evidence}),
                "predicates": sorted({item.predicate for item in evidence}),
                "temporal_labels": sorted({_time_label(item) for item in evidence}),
                "source_authorities": sorted({item.source.authority.value for item in evidence}),
            },
            answer_schema=answer_schema,
            metadata={
                "bundle_id": bundle.bundle_id,
                "proof_required": True,
            },
        )
        oracle = TaskOracleContract(
            task_id=task_id,
            gold_evidence_ids=evidence_ids,
            task_program=program,
            proof_graph_id=proof_graph.graph_id,
            proof_graph_hash=proof_graph.graph_hash,
            quality_rubric={
                "evidence_coverage": 1.0,
                "operation_replay": True,
                "source_citation": True,
            },
        )
        return TaskPackage(task_id=task_id, public=public, oracle=oracle)

    @staticmethod
    def _find(bundle: EvidenceBundle, evidence_id: str) -> EvidenceItem:
        for item in bundle.evidence:
            if item.evidence_id == evidence_id:
                return item
        raise TaskSynthesisError(f"evidence not found in bundle: {evidence_id}")

    def _require_graph_evidence(
        self,
        proof_graph: ProofGraph,
        bundle: EvidenceBundle,
        evidence_ids: tuple[str, ...],
    ) -> None:
        report = self._proof_validator.validate(proof_graph, bundle, evidence_ids)
        if not report.passed:
            failures = [check.check_id for check in report.checks if not check.passed]
            raise TaskSynthesisError(f"proof graph is missing or invalid: {failures}")

    def _validate_comparable(self, left: EvidenceItem, right: EvidenceItem) -> None:
        self._validate_domain_evidence(left)
        self._validate_domain_evidence(right)
        if self._semantic_policy is not None:
            decision = self._semantic_policy.compare(left, right)
            if not decision.comparable:
                raise TaskSynthesisError(
                    f"evidence is not comparable: {', '.join(decision.reasons)}"
                )
            return
        left_payload = _require_scalar(left)
        right_payload = _require_scalar(right)
        mismatches = []
        for field, left_value, right_value in (
            ("domain", left.domain, right.domain),
            ("predicate", left.predicate, right.predicate),
            ("unit", left_payload.unit, right_payload.unit),
            ("currency", left_payload.currency, right_payload.currency),
            ("definition", left.definition.definition_id, right.definition.definition_id),
        ):
            if left_value != right_value:
                mismatches.append(field)
        if mismatches:
            raise TaskSynthesisError(f"evidence is not comparable: {', '.join(mismatches)}")

    def _validate_same_series(self, earlier: EvidenceItem, later: EvidenceItem) -> None:
        self._validate_comparable(earlier, later)
        if earlier.subject.subject_id != later.subject.subject_id:
            raise TaskSynthesisError("temporal series must refer to the same subject")
        earlier_end = earlier.temporal_context.valid_to or earlier.temporal_context.observed_at
        later_end = later.temporal_context.valid_to or later.temporal_context.observed_at
        if not earlier_end or not later_end or earlier_end >= later_end:
            raise TaskSynthesisError("temporal growth requires ordered, dated evidence")

    def _validate_temporal_series(self, evidence: tuple[EvidenceItem, ...]) -> None:
        first = evidence[0]
        observed_times = []
        for item in evidence:
            self._validate_domain_evidence(item)
            if item is not first:
                self._validate_comparable(first, item)
            if item.subject.subject_id != first.subject.subject_id:
                raise TaskSynthesisError("temporal series must refer to the same subject")
            observed_times.append(_temporal_sort_key(item))
        if any(value is None for value in observed_times):
            raise TaskSynthesisError("temporal average requires dated evidence")
        if len(set(observed_times)) != len(observed_times):
            raise TaskSynthesisError("temporal average contains duplicate periods")

    def _validate_domain_evidence(self, evidence: EvidenceItem) -> None:
        if self._semantic_policy is None:
            return
        report = self._semantic_policy.validate_evidence(evidence)
        if not report.passed:
            raise TaskSynthesisError(
                f"domain semantic validation failed: {', '.join(report.issues)}"
            )


def _operation_node(
    node_id: str, operator_id: str, evidence_ids: tuple[str, ...], output_schema: str
) -> OperationNode:
    return OperationNode(
        node_id=node_id,
        operator_id=operator_id,
        input_refs=tuple(
            ProgramInputRef(kind=InputRefKind.EVIDENCE, ref_id=item) for item in evidence_ids
        ),
        output_schema=output_schema,
        verifier_id=f"{operator_id}.oracle.v1",
    )


def _require_scalar(evidence: EvidenceItem) -> ScalarObservation:
    if not isinstance(evidence.payload, ScalarObservation):
        raise TaskSynthesisError(f"task requires scalar evidence: {evidence.evidence_id}")
    return evidence.payload


def _scalar_answer_schema(evidence: EvidenceItem, answer_type: str) -> dict[str, Any]:
    payload = _require_scalar(evidence)
    return {"type": answer_type, "unit": payload.unit, "currency": payload.currency}


def _time_label(evidence: EvidenceItem) -> str:
    context = evidence.temporal_context
    if context.label:
        return context.label
    if context.valid_to:
        return context.valid_to.isoformat()
    if context.observed_at:
        return context.observed_at.isoformat()
    return "the stated period"


def _time_phrase(evidence: EvidenceItem) -> str:
    label = _time_label(evidence)
    return "" if label == "the stated period" else f" for {label}"


def _temporal_sort_key(evidence: EvidenceItem):
    context = evidence.temporal_context
    return context.valid_to or context.observed_at or context.valid_from


def _requirements_for_program(program: TaskProgram) -> tuple[TaskRequirement, ...]:
    requirements = [
        TaskRequirement.RETRIEVE_EVIDENCE,
        TaskRequirement.SELECT_EVIDENCE,
        TaskRequirement.CITE_SOURCE,
    ]
    if any(node.operator_id != "lookup" for node in program.nodes):
        requirements.extend((TaskRequirement.CALCULATE, TaskRequirement.VERIFY_RESULT))
    return tuple(requirements)


def _allowed_tools_for_program(program: TaskProgram) -> tuple[str, ...]:
    tools = ["evidence.search"]
    if any(node.operator_id != "lookup" for node in program.nodes):
        tools.append("calculator")
    return tuple(tools)
