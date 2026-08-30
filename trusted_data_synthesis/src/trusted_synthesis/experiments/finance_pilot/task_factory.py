from __future__ import annotations

from dataclasses import dataclass, field

from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.epistemic import EpistemicStatus
from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.evidence.schema import (
    EvidenceBundle,
    EvidenceItem,
    SourceAuthority,
)
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.domains.finance.realization import FinanceRealizationCompilation
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.experiments.finance_pilot.sampler import (
    TaskBinding,
    select_distractors,
    select_real_distractors,
)
from trusted_synthesis.hashing import canonical_hash


@dataclass(frozen=True)
class PilotTaskCase:
    binding: TaskBinding
    bundle: EvidenceBundle
    corpus: EvidenceCorpus
    proof_graph: ProofGraph
    task: TaskPackage
    realization_compilation: FinanceRealizationCompilation
    distractor_ids: tuple[str, ...]
    hard_distractor_ids: tuple[str, ...] = ()
    distractor_kinds: dict[str, str] = field(default_factory=dict)


def build_task_cases(
    bindings: tuple[TaskBinding, ...],
    evidence: tuple[EvidenceItem, ...],
    *,
    distractors_per_task: int,
    hard_distractors_per_task: int | None = None,
    hard_distractor_types: tuple[str, ...] = (),
    use_real_distractors: bool = False,
    task_synthesizer: FinanceTaskPlugin,
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
        instantiation = task_synthesizer.compile_evidence_ids(
            binding.task_type,
            graph,
            bundle,
            binding.evidence_ids,
        )
        realization_compilation = task_synthesizer.realize_instantiation(
            instantiation,
            graph,
            bundle,
        )
        task = instantiation.task
        hard_count = (
            distractors_per_task if hard_distractors_per_task is None else hard_distractors_per_task
        )
        if use_real_distractors:
            real_selection = select_real_distractors(
                evidence,
                gold,
                hard_count=hard_count,
                broad_count=distractors_per_task,
                preferred_hard_kinds=hard_distractor_types,
            )
            hard_distractors = real_selection.hard
            soft_distractors = real_selection.broad
            distractor_kinds = {
                item.evidence_id: real_selection.kinds[item.evidence_id]
                for item in hard_distractors
            }
        else:
            hard_distractors, distractor_kinds = _hard_distractors(
                gold,
                hard_distractor_types,
                hard_count,
            )
            soft_distractors = select_distractors(evidence, gold, distractors_per_task)
        distractors = (*hard_distractors, *soft_distractors)
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
                realization_compilation=realization_compilation,
                distractor_ids=tuple(item.evidence_id for item in distractors),
                hard_distractor_ids=tuple(item.evidence_id for item in hard_distractors),
                distractor_kinds=distractor_kinds,
            )
        )
    return tuple(cases)


def _hard_distractors(
    gold: tuple[EvidenceItem, ...],
    kinds: tuple[str, ...],
    count: int,
) -> tuple[tuple[EvidenceItem, ...], dict[str, str]]:
    if not kinds or count <= 0:
        return (), {}
    output = []
    observed_kinds = {}
    for index in range(count):
        base = gold[index % len(gold)]
        kind = kinds[index % len(kinds)]
        identity = canonical_hash(
            {
                "gold_evidence_id": base.evidence_id,
                "kind": kind,
                "ordinal": index,
                "version": "finance_hard_distractor.v1",
            },
            prefix="finance_hard_distractor:",
        )
        item = _mutate_semantic_contract(base, kind, identity)
        output.append(item)
        observed_kinds[item.evidence_id] = kind
    return tuple(output), observed_kinds


def _mutate_semantic_contract(base: EvidenceItem, kind: str, identity: str) -> EvidenceItem:
    updates = {
        "evidence_id": f"evidence:distractor:{identity.split(':')[-1]}",
        "assertion_id": f"assertion:distractor:{identity.split(':')[-1]}",
        "evidence_version_id": f"version:distractor:{identity.split(':')[-1]}",
        "provenance": base.provenance.model_copy(
            update={"source_record_id": f"distractor:{identity.split(':')[-1]}"}
        ),
        "domain_context": {
            **base.domain_context,
            "synthetic_distractor_kind": kind,
        },
    }
    if kind == "wrong_definition":
        updates["definition"] = base.definition.model_copy(
            update={"definition_id": f"{base.definition.definition_id}:incompatible"}
        )
    elif kind == "stale_version":
        updates["evidence_version_id"] = f"version:stale:{identity.split(':')[-1]}"
        updates["epistemic_status"] = EpistemicStatus.SUPERSEDED
        updates["provenance"] = base.provenance.model_copy(
            update={
                "source_record_id": f"stale:{identity.split(':')[-1]}",
                "build_ids": {**base.provenance.build_ids, "kg": "kg_stale"},
            }
        )
    elif kind == "forecast":
        updates["domain_context"] = {
            **base.domain_context,
            "is_forecast": True,
            "synthetic_distractor_kind": kind,
        }
    elif kind == "lower_authority":
        updates["source"] = base.source.model_copy(
            update={
                "source_id": f"{base.source.source_id}:secondary",
                "name": f"Secondary mirror of {base.source.name}",
                "authority": SourceAuthority.SECONDARY,
            }
        )
    elif kind in {"unit_mismatch", "currency_mismatch"}:
        if isinstance(base.payload, ScalarObservation):
            if kind == "unit_mismatch":
                updates["payload"] = base.payload.model_copy(
                    update={"unit": f"incompatible {base.payload.unit or 'unit'}"}
                )
            else:
                updates["payload"] = base.payload.model_copy(
                    update={
                        "currency": "ZZZ",
                        "unit": (
                            base.payload.unit
                            if base.payload.currency
                            else f"incompatible {base.payload.unit or 'unit'}"
                        ),
                    }
                )
    elif kind == "wrong_scope":
        if base.scope is not None:
            updates["scope"] = base.scope.model_copy(
                update={
                    "scope_type": f"{base.scope.scope_type}:segment",
                    "scope_id": f"{base.scope.scope_id}:segment",
                }
            )
    else:
        raise ValueError(f"unsupported hard distractor kind: {kind}")
    return base.model_copy(update=updates)
