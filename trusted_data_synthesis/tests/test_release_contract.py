from __future__ import annotations

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.release import SplitPolicy, assign_split, semantic_cluster_id
from trusted_synthesis.core.task.generator import ProofGraphTaskSynthesizer


def test_surface_variants_share_a_semantic_split(finance_evidence: EvidenceItem) -> None:
    bundle = EvidenceBundle(
        bundle_id="bundle_split", evidence=(finance_evidence,), purpose="split contract"
    )
    graph = ProofGraphBuilder().build(bundle)
    task = ProofGraphTaskSynthesizer().fact_retrieval(graph, bundle, finance_evidence.evidence_id)
    variant = task.model_copy(
        update={
            "public": task.public.model_copy(
                update={"instruction": "State the requested historical value and its source."}
            )
        }
    )
    policy = SplitPolicy(policy_id="semantic_split.v1")

    assert semantic_cluster_id(task) == semantic_cluster_id(variant)
    assert assign_split(task, policy) == assign_split(variant, policy)
