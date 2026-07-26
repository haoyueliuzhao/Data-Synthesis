from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from trusted_synthesis.core.evaluation.evaluator import QualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence import ScalarObservation, TemporalContext
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem, SubjectRef
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.graph.extractor import ProofSubgraphExtractor
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.task.generator import ProofGraphTaskSynthesizer, TaskSynthesisError
from trusted_synthesis.core.trajectory.generator import ReferenceWorkflowCompiler
from trusted_synthesis.core.trajectory.verifier import ReferenceWorkflowVerifier


def _bundle(*items: EvidenceItem) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="bundle_test",
        evidence=items,
        purpose="test trusted synthesis v2",
        graph_build_id="kg_test",
    )


def test_retrieval_pipeline_is_recomputable(finance_evidence: EvidenceItem) -> None:
    bundle = _bundle(finance_evidence)
    graph = ProofGraphBuilder().build(bundle)
    task = ProofGraphTaskSynthesizer().fact_retrieval(graph, bundle, finance_evidence.evidence_id)
    workflow = ReferenceWorkflowCompiler().compile(task, bundle)
    assessment = QualityEvaluator().evaluate(task, bundle, graph, workflow)

    assert ReferenceWorkflowVerifier().verify(task, bundle, graph, workflow).passed
    assert workflow.final_answer["result"]["payload"]["value"] == "383285"
    assert assessment.total_score == 100
    assert assessment.decision == ReleaseDecision.ACCEPTED
    assert all(gate.passed for gate in assessment.hard_gates)


def test_proof_graph_preserves_identity_and_lineage(finance_evidence: EvidenceItem) -> None:
    graph = ProofGraphBuilder().build(_bundle(finance_evidence))

    assert graph.source_build_id == "kg_test"
    assert {edge.relation for edge in graph.edges} == {
        "HAS_EVIDENCE",
        "ASSERTS",
        "FROM_SOURCE",
        "IN_TIME",
        "APPLIES_TO",
        "HAS_DEFINITION",
        "LOCATED_AT",
    }
    assert graph.contains_evidence(finance_evidence.evidence_id)
    assert graph.graph_hash == graph.graph_hash

    subgraph = ProofSubgraphExtractor().extract(graph, (finance_evidence.evidence_id,))
    assert subgraph.contains_evidence(finance_evidence.evidence_id)
    assert {edge.relation for edge in subgraph.edges} == {
        "HAS_EVIDENCE",
        "ASSERTS",
        "FROM_SOURCE",
        "IN_TIME",
        "APPLIES_TO",
        "HAS_DEFINITION",
        "LOCATED_AT",
    }


def test_comparison_requires_compatible_evidence(finance_evidence: EvidenceItem) -> None:
    peer = finance_evidence.model_copy(
        update={
            "evidence_id": "evidence:finance:fact_peer_revenue_2023@kg_test",
            "assertion_id": "assertion:finance:fact_peer_revenue_2023",
            "evidence_version_id": "version:finance:fact_peer_revenue_2023@kg_test",
            "subject": SubjectRef(subject_id="MSFT_US", name="Microsoft", subject_type="company"),
            "payload": ScalarObservation(
                value=Decimal("211915"), unit="million USD", currency="USD"
            ),
            "provenance": finance_evidence.provenance.model_copy(
                update={"source_record_id": "fact_peer_revenue_2023"}
            ),
        }
    )
    bundle = _bundle(finance_evidence, peer)
    graph = ProofGraphBuilder().build(bundle)
    task = ProofGraphTaskSynthesizer().comparison(
        graph, bundle, finance_evidence.evidence_id, peer.evidence_id
    )
    workflow = ReferenceWorkflowCompiler().compile(task, bundle)

    result = workflow.final_answer["result"]
    assert result["higher_ref"] == finance_evidence.evidence_id
    assert result["difference"] == "171370"
    assert QualityEvaluator().evaluate(task, bundle, graph, workflow).decision == (
        ReleaseDecision.ACCEPTED
    )


def test_temporal_growth_is_a_three_node_program(finance_evidence: EvidenceItem) -> None:
    later = finance_evidence.model_copy(
        update={
            "evidence_id": "evidence:finance:fact_revenue_2024@kg_test",
            "assertion_id": "assertion:finance:fact_revenue_2024",
            "evidence_version_id": "version:finance:fact_revenue_2024@kg_test",
            "payload": ScalarObservation(
                value=Decimal("421613.5"), unit="million USD", currency="USD"
            ),
            "temporal_context": TemporalContext(
                label="FY2024",
                valid_from=date(2023, 10, 1),
                valid_to=date(2024, 9, 30),
                basis="fiscal_period",
                frequency="annual",
            ),
            "provenance": finance_evidence.provenance.model_copy(
                update={"source_record_id": "fact_revenue_2024"}
            ),
        }
    )
    bundle = _bundle(finance_evidence, later)
    graph = ProofGraphBuilder().build(bundle)
    task = ProofGraphTaskSynthesizer().temporal_growth(
        graph, bundle, finance_evidence.evidence_id, later.evidence_id
    )
    workflow = ReferenceWorkflowCompiler().compile(task, bundle)

    assert [node.operator_id for node in task.oracle.task_program.nodes] == [
        "lookup",
        "lookup",
        "growth",
    ]
    assert [ref.selector for ref in task.oracle.task_program.nodes[-1].input_refs] == [
        "payload.value",
        "payload.value",
    ]
    assert workflow.final_answer["result"]["value"] == "10.0"


def test_missing_proof_graph_evidence_fails_closed(finance_evidence: EvidenceItem) -> None:
    bundle = _bundle(finance_evidence)
    empty_graph = ProofGraph(graph_id="proof:empty", nodes=(), edges=())

    with pytest.raises(TaskSynthesisError, match="proof graph is missing"):
        ProofGraphTaskSynthesizer().fact_retrieval(
            empty_graph, bundle, finance_evidence.evidence_id
        )


def test_mutated_program_and_answer_are_rejected(finance_evidence: EvidenceItem) -> None:
    bundle = _bundle(finance_evidence)
    graph = ProofGraphBuilder().build(bundle)
    task = ProofGraphTaskSynthesizer().fact_retrieval(graph, bundle, finance_evidence.evidence_id)
    workflow = ReferenceWorkflowCompiler().compile(task, bundle)
    execution = dict(workflow.program_execution or {})
    execution["node_outputs"] = {"result": {"payload": {"value": "1"}}}
    mutated = workflow.model_copy(
        update={
            "program_execution": execution,
            "final_answer": {"result": {"payload": {"value": "1"}}, "citations": []},
        }
    )

    report = ReferenceWorkflowVerifier().verify(task, bundle, graph, mutated)
    assessment = QualityEvaluator().evaluate(task, bundle, graph, mutated)

    assert not report.passed
    assert assessment.decision == ReleaseDecision.REJECTED
    assert "independent_recompute" in assessment.fatal_failures
