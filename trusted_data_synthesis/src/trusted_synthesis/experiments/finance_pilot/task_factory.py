from __future__ import annotations

from dataclasses import dataclass

from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.task.generator import ProofGraphTaskSynthesizer
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.experiments.finance_pilot.sampler import (
    TaskBinding,
    select_distractors,
)
from trusted_synthesis.hashing import canonical_hash


@dataclass(frozen=True)
class PilotTaskCase:
    binding: TaskBinding
    bundle: EvidenceBundle
    corpus: EvidenceCorpus
    proof_graph: ProofGraph
    task: TaskPackage
    distractor_ids: tuple[str, ...]


def build_task_cases(
    bindings: tuple[TaskBinding, ...],
    evidence: tuple[EvidenceItem, ...],
    *,
    distractors_per_task: int,
    task_synthesizer: ProofGraphTaskSynthesizer,
) -> tuple[PilotTaskCase, ...]:
    by_id = {item.evidence_id: item for item in evidence}
    graph_builder = ProofGraphBuilder()
    cases = []
    for binding in bindings:
        gold = tuple(by_id[evidence_id] for evidence_id in binding.evidence_ids)
        bundle = EvidenceBundle(
            bundle_id=canonical_hash(
                {
                    "binding_hash": binding.binding_hash,
                    "purpose": "finance_synthesis_pilot",
                },
                prefix="bundle:",
            ),
            evidence=gold,
            purpose="finance synthesis pilot gold evidence",
            graph_build_id=gold[0].provenance.build_ids.get("kg"),
        )
        graph = graph_builder.build(bundle)
        if binding.task_type == "fact_retrieval":
            task = task_synthesizer.fact_retrieval(graph, bundle, binding.evidence_ids[0])
        elif binding.task_type == "comparison":
            task = task_synthesizer.comparison(graph, bundle, *binding.evidence_ids)
        elif binding.task_type == "temporal_growth":
            task = task_synthesizer.temporal_growth(graph, bundle, *binding.evidence_ids)
        elif binding.task_type == "temporal_average":
            task = task_synthesizer.temporal_average(graph, bundle, binding.evidence_ids)
        else:
            raise ValueError(f"unsupported pilot task type: {binding.task_type}")
        distractors = select_distractors(evidence, gold, distractors_per_task)
        corpus_evidence = tuple(sorted((*gold, *distractors), key=lambda item: item.evidence_id))
        corpus = EvidenceCorpus(
            corpus_id=canonical_hash(
                {
                    "task_id": task.task_id,
                    "evidence_ids": [item.evidence_id for item in corpus_evidence],
                },
                prefix="evidence_corpus:",
            ),
            evidence=corpus_evidence,
            build_id=bundle.graph_build_id,
        )
        cases.append(
            PilotTaskCase(
                binding=binding,
                bundle=bundle,
                corpus=corpus,
                proof_graph=graph,
                task=task,
                distractor_ids=tuple(item.evidence_id for item in distractors),
            )
        )
    return tuple(cases)
