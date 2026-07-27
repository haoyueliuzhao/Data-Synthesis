from __future__ import annotations

from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.task.schema import (
    PlanningTrack,
    RetrievalTrack,
    TaskPackage,
)
from trusted_synthesis.hashing import canonical_hash


def materialize_track_variant(
    task: TaskPackage,
    corpus: EvidenceCorpus,
    *,
    retrieval_track: RetrievalTrack,
    planning_track: PlanningTrack,
) -> TaskPackage:
    scope = _retrieval_scope(task, corpus, retrieval_track)
    identity = {
        "base_task_id": task.task_id,
        "retrieval_track": retrieval_track.value,
        "planning_track": planning_track.value,
        "retrieval_scope": scope,
        "track_materializer": "agent_validation_tracks.v1",
    }
    task_id = canonical_hash(identity, prefix="agent_validation_task:")
    public = task.public.model_copy(
        update={
            "task_id": task_id,
            "retrieval_track": retrieval_track,
            "planning_track": planning_track,
            "program_skeleton": (
                task.public.program_skeleton
                if planning_track == PlanningTrack.PLAN_GIVEN
                else None
            ),
            "retrieval_scope": scope,
            "metadata": {
                **task.public.metadata,
                "base_task_id": task.task_id,
                "track_materializer": "agent_validation_tracks.v1",
            },
        }
    )
    oracle = task.oracle.model_copy(update={"task_id": task_id})
    return TaskPackage(task_id=task_id, public=public, oracle=oracle)


def _retrieval_scope(
    task: TaskPackage,
    corpus: EvidenceCorpus,
    track: RetrievalTrack,
) -> dict[str, object]:
    gold_ids = set(task.oracle.gold_evidence_ids)
    target_evidence = tuple(
        item for item in corpus.evidence if item.evidence_id in gold_ids
    )
    if not target_evidence:
        raise ValueError("track materialization requires oracle evidence in the corpus")
    if track == RetrievalTrack.RESOLVED:
        return {
            "subject_ids": sorted({item.subject.subject_id for item in target_evidence}),
            "predicates": sorted({item.predicate for item in target_evidence}),
            "temporal_labels": sorted(
                {
                    item.temporal_context.label
                    for item in target_evidence
                    if item.temporal_context.label
                }
            ),
            "source_authorities": sorted(
                {item.source.authority.value for item in target_evidence}
            ),
            "semantic_constraints": {
                "definition_ids": sorted(
                    {
                        item.definition.definition_id
                        for item in target_evidence
                        if item.definition.definition_id is not None
                    }
                ),
                "scope_ids": sorted(
                    {
                        item.scope.scope_id
                        for item in target_evidence
                        if item.scope is not None and item.scope.scope_id is not None
                    }
                ),
            },
            "corpus_boundary": corpus.corpus_id,
        }
    if track == RetrievalTrack.SEMI_OPEN:
        predicates = sorted({item.predicate for item in target_evidence})
        definitions = sorted(
            {
                item.definition.definition_id
                for item in target_evidence
                if item.definition.definition_id is not None
            }
        )
        partial: dict[str, object] = {}
        if len(predicates) == 1:
            partial["predicate"] = predicates[0]
        if len(definitions) == 1:
            partial["definition_id"] = definitions[0]
        if not partial:
            partial["task_type"] = task.public.task_type
        return {
            "aliases": sorted({item.subject.name for item in target_evidence}),
            "partial_constraints": partial,
            "corpus_boundary": corpus.corpus_id,
        }
    return {"corpus_boundary": corpus.corpus_id}
