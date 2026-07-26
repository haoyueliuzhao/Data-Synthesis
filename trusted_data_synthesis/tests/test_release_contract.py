from __future__ import annotations

import pytest

from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.release import (
    SplitPolicy,
    assign_split,
    select_candidate_release,
    semantic_cluster_id,
)
from trusted_synthesis.core.task.generator import ProofGraphTaskSynthesizer
from trusted_synthesis.core.task.program import InputRefKind
from trusted_synthesis.experiments.finance_pilot.candidate import (
    FinanceNumericCandidateGenerator,
)
from trusted_synthesis.runtime import InMemoryEvidenceToolRuntime


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


def test_program_semantic_cluster_ignores_evidence_version(
    finance_evidence: EvidenceItem,
) -> None:
    bundle = EvidenceBundle(
        bundle_id="bundle_split_version",
        evidence=(finance_evidence,),
        purpose="split version isolation",
    )
    graph = ProofGraphBuilder().build(bundle)
    task = ProofGraphTaskSynthesizer().fact_retrieval(graph, bundle, finance_evidence.evidence_id)
    versioned_id = f"{finance_evidence.evidence_id}:restated"
    node = task.oracle.task_program.nodes[0]
    refs = tuple(
        ref.model_copy(update={"ref_id": versioned_id})
        if ref.kind == InputRefKind.EVIDENCE
        else ref
        for ref in node.input_refs
    )
    program = task.oracle.task_program.model_copy(
        update={"nodes": (node.model_copy(update={"input_refs": refs}),)}
    )
    variant = task.model_copy(
        update={
            "oracle": task.oracle.model_copy(
                update={"gold_evidence_ids": (versioned_id,), "task_program": program}
            )
        }
    )

    assert task.oracle.task_program.program_hash != program.program_hash
    assert task.oracle.task_program.semantic_hash == program.semantic_hash
    assert semantic_cluster_id(task) == semantic_cluster_id(variant)


def test_split_policy_fields_are_executed_fail_closed(
    finance_evidence: EvidenceItem,
) -> None:
    bundle = EvidenceBundle(
        bundle_id="bundle_split_policy",
        evidence=(finance_evidence,),
        purpose="split policy execution",
    )
    graph = ProofGraphBuilder().build(bundle)
    task = ProofGraphTaskSynthesizer().fact_retrieval(graph, bundle, finance_evidence.evidence_id)
    minimal = SplitPolicy(policy_id="minimal", cluster_fields=("domain", "task_type"))
    assert semantic_cluster_id(task, minimal)
    invalid = SplitPolicy(policy_id="invalid", cluster_fields=("unknown_field",))
    with pytest.raises(ValueError, match="unknown cluster fields"):
        semantic_cluster_id(task, invalid)


def test_candidate_release_selects_only_quality_accepted_records(
    finance_evidence: EvidenceItem,
) -> None:
    bundle = EvidenceBundle(
        bundle_id="bundle_candidate_release",
        evidence=(finance_evidence,),
        purpose="candidate release selection",
    )
    graph = ProofGraphBuilder().build(bundle)
    task = ProofGraphTaskSynthesizer().fact_retrieval(graph, bundle, finance_evidence.evidence_id)
    corpus = EvidenceCorpus.from_bundle(bundle)
    candidate = FinanceNumericCandidateGenerator().generate(
        task.public, InMemoryEvidenceToolRuntime(corpus)
    )
    accepted = CandidateQualityEvaluator().evaluate(task, corpus, graph, candidate)
    rejected = accepted.model_copy(
        update={
            "assessment_id": "assessment:rejected",
            "trajectory_id": "trajectory:rejected",
            "decision": ReleaseDecision.REJECTED,
            "fatal_failures": ("answer_citation_and_claims",),
        }
    )
    rejected_candidate = candidate.model_copy(update={"trajectory_id": "trajectory:rejected"})
    policy = SplitPolicy(policy_id="candidate_release.v1")

    selection = select_candidate_release(
        (
            (task, candidate, accepted),
            (task, rejected_candidate, rejected),
        ),
        policy,
    )

    assert selection.accepted_trajectory_ids == (candidate.trajectory_id,)
    assert selection.failure_distribution == {"answer_citation_and_claims": 1}
    assert sum(selection.split_counts.values()) == 1
