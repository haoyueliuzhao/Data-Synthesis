from __future__ import annotations

from trusted_synthesis.core.evidence import DerivedResult, EpistemicStatus, EvidenceKind
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.graph.extractor import ProofSubgraphExtractor
from trusted_synthesis.core.graph.schema import NodeKind
from trusted_synthesis.core.graph.validation import ProofGraphValidator
from trusted_synthesis.core.task.generator import ProofGraphTaskSynthesizer, TaskSynthesisError
from trusted_synthesis.core.trajectory.generator import ReferenceWorkflowCompiler
from trusted_synthesis.core.trajectory.verifier import ReferenceWorkflowVerifier


def _bundle(*evidence: EvidenceItem) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="bundle_proof_contract",
        evidence=evidence,
        purpose="proof graph contract",
        graph_build_id="kg_test",
    )


def test_locator_payload_mutation_fails_task_synthesis(finance_evidence: EvidenceItem) -> None:
    bundle = _bundle(finance_evidence)
    graph = ProofGraphBuilder().build(bundle)
    nodes = tuple(
        node.model_copy(update={"properties": {"uri": "https://wrong.example/"}})
        if node.kind == NodeKind.LOCATOR
        else node
        for node in graph.nodes
    )
    mutated = graph.model_copy(update={"nodes": nodes})

    try:
        ProofGraphTaskSynthesizer().fact_retrieval(mutated, bundle, finance_evidence.evidence_id)
    except TaskSynthesisError as exc:
        assert "proof graph is missing or invalid" in str(exc)
    else:
        raise AssertionError("mutated source locator must fail closed")


def test_oracle_binds_graph_content_hash(finance_evidence: EvidenceItem) -> None:
    bundle = _bundle(finance_evidence)
    graph = ProofGraphBuilder().build(bundle)
    task = ProofGraphTaskSynthesizer().fact_retrieval(graph, bundle, finance_evidence.evidence_id)
    workflow = ReferenceWorkflowCompiler().compile(task, bundle)
    mutated = graph.model_copy(
        update={
            "nodes": tuple(
                node.model_copy(update={"properties": {**node.properties, "tampered": True}})
                if node.kind == NodeKind.SOURCE
                else node
                for node in graph.nodes
            )
        }
    )

    report = ReferenceWorkflowVerifier().verify(task, bundle, mutated, workflow)

    checks = {check.check_id: check.passed for check in report.checks}
    assert checks["proof_graph_identity"] is False


def test_recursive_proof_closure_includes_parent_lineage(
    finance_evidence: EvidenceItem,
) -> None:
    derived = finance_evidence.model_copy(
        update={
            "evidence_id": "evidence:finance:derived_average@kg_test",
            "assertion_id": "assertion:finance:derived_average",
            "evidence_version_id": "version:finance:derived_average@kg_test",
            "evidence_kind": EvidenceKind.DERIVED_RESULT,
            "predicate": "average_revenue",
            "payload": DerivedResult(
                operation_id="aggregate.mean.v1",
                input_evidence_ids=(finance_evidence.evidence_id,),
                output={"value": "383285", "unit": "million USD"},
            ),
            "provenance": finance_evidence.provenance.model_copy(
                update={
                    "source_record_id": "derived_average",
                    "parent_evidence_ids": (finance_evidence.evidence_id,),
                }
            ),
            "epistemic_status": EpistemicStatus.DERIVED,
        }
    )
    bundle = _bundle(finance_evidence, derived)
    graph = ProofGraphBuilder().build(bundle)

    subgraph = ProofSubgraphExtractor().extract(graph, (derived.evidence_id,))
    report = ProofGraphValidator().validate(
        subgraph, bundle, (derived.evidence_id, finance_evidence.evidence_id)
    )

    assert report.passed
    assert subgraph.contains_evidence(finance_evidence.evidence_id)
    parent_edges = {
        edge.relation
        for edge in subgraph.edges
        if edge.source_id == finance_evidence.evidence_id
        or edge.target_id == finance_evidence.evidence_id
    }
    assert {"FROM_SOURCE", "LOCATED_AT", "IN_TIME", "HAS_DEFINITION"}.issubset(parent_edges)
