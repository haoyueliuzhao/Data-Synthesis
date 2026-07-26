from __future__ import annotations

from decimal import Decimal

from trusted_synthesis.core.evaluation.evaluator import QualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.evidence.validation import EvidenceValidator
from trusted_synthesis.core.graph.builder import EvidenceGraphBuilder
from trusted_synthesis.core.task.generator import EvidenceTaskSynthesizer
from trusted_synthesis.core.trajectory.generator import DeterministicTrajectoryGenerator
from trusted_synthesis.core.trajectory.verifier import TrajectoryVerifier


def test_retrieval_pipeline_is_recomputable(finance_evidence: EvidenceItem) -> None:
    bundle = EvidenceBundle(
        bundle_id="bundle_finance_retrieval",
        evidence=(finance_evidence,),
        purpose="test retrieval",
        graph_build_id="kg_test",
    )
    task = EvidenceTaskSynthesizer().fact_retrieval(bundle, finance_evidence.evidence_id)
    trajectory = DeterministicTrajectoryGenerator().generate(task, bundle)
    assessment = QualityEvaluator().evaluate(task, bundle, trajectory)

    assert EvidenceValidator().validate(finance_evidence).passed
    assert TrajectoryVerifier().verify(task, bundle, trajectory).passed
    assert trajectory.final_answer["value"] == "383285"
    assert assessment.total_score == 100
    assert assessment.decision == ReleaseDecision.ACCEPTED


def test_evidence_graph_preserves_identity_and_lineage(finance_evidence: EvidenceItem) -> None:
    bundle = EvidenceBundle(
        bundle_id="bundle_graph",
        evidence=(finance_evidence,),
        purpose="test graph",
        graph_build_id="kg_test",
    )
    graph = EvidenceGraphBuilder().build(bundle)

    assert graph.source_build_id == "kg_test"
    assert {edge.relation for edge in graph.edges} == {
        "HAS_EVIDENCE",
        "MEASURES",
        "FROM_SOURCE",
        "IN_TIME",
    }
    assert len(graph.nodes) == 5
    assert graph.graph_hash == graph.graph_hash


def test_comparison_requires_compatible_evidence(finance_evidence: EvidenceItem) -> None:
    peer = finance_evidence.model_copy(
        update={
            "evidence_id": "evidence:finance:fact_peer_revenue_2023",
            "entity": finance_evidence.entity.model_copy(
                update={"entity_id": "MSFT_US", "name": "Microsoft Corporation"}
            ),
            "value": Decimal("211915"),
            "provenance": finance_evidence.provenance.model_copy(
                update={"source_record_id": "fact_peer_revenue_2023"}
            ),
        }
    )
    bundle = EvidenceBundle(
        bundle_id="bundle_comparison",
        evidence=(finance_evidence, peer),
        purpose="test comparison",
    )
    task = EvidenceTaskSynthesizer().comparison(
        bundle,
        finance_evidence.evidence_id,
        peer.evidence_id,
    )
    trajectory = DeterministicTrajectoryGenerator().generate(task, bundle)

    assert trajectory.final_answer["higher_evidence_id"] == finance_evidence.evidence_id
    assert trajectory.final_answer["difference"] == "171370"
    assert (
        QualityEvaluator().evaluate(task, bundle, trajectory).decision == ReleaseDecision.ACCEPTED
    )


def test_mutated_answer_is_rejected(finance_evidence: EvidenceItem) -> None:
    bundle = EvidenceBundle(
        bundle_id="bundle_mutation",
        evidence=(finance_evidence,),
        purpose="test mutation",
    )
    task = EvidenceTaskSynthesizer().fact_retrieval(bundle, finance_evidence.evidence_id)
    trajectory = DeterministicTrajectoryGenerator().generate(task, bundle)
    mutated = trajectory.model_copy(update={"final_answer": {"value": "1"}})

    report = TrajectoryVerifier().verify(task, bundle, mutated)
    assessment = QualityEvaluator().evaluate(task, bundle, mutated)

    assert not report.passed
    assert assessment.decision == ReleaseDecision.REJECTED
    assert "independent_recompute" in assessment.fatal_failures
