from __future__ import annotations

from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.task.generator import ProofGraphTaskSynthesizer
from trusted_synthesis.experiments.finance_pilot.candidate import (
    FinanceNumericCandidateGenerator,
)
from trusted_synthesis.runtime import InMemoryEvidenceToolRuntime


def test_candidate_pipeline_is_deterministic(finance_evidence: EvidenceItem) -> None:
    bundle = EvidenceBundle(
        bundle_id="bundle_determinism",
        evidence=(finance_evidence,),
        purpose="determinism contract",
        graph_build_id="kg_test",
    )
    corpus = EvidenceCorpus.from_bundle(bundle)

    def compile_once():
        graph = ProofGraphBuilder().build(bundle)
        task = ProofGraphTaskSynthesizer().fact_retrieval(
            graph, bundle, finance_evidence.evidence_id
        )
        candidate = FinanceNumericCandidateGenerator().generate(
            task.public, InMemoryEvidenceToolRuntime(corpus)
        )
        quality = CandidateQualityEvaluator().evaluate(task, corpus, graph, candidate)
        return graph, task, candidate, quality

    first = compile_once()
    second = compile_once()

    assert [item.model_dump(mode="json") for item in first] == [
        item.model_dump(mode="json") for item in second
    ]
