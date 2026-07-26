from __future__ import annotations

from enum import Enum

from trusted_synthesis.core.release.schema import SplitPolicy
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.hashing import canonical_hash


class DatasetSplit(str, Enum):
    TRAIN = "train"
    DEV = "dev"
    TEST = "test"


def semantic_cluster_id(task: TaskPackage, policy: SplitPolicy | None = None) -> str:
    scope = task.public.retrieval_scope
    features = {
        "domain": task.public.domain,
        "task_type": task.public.task_type,
        "subject_ids": sorted(scope.get("subject_ids") or []),
        "predicates": sorted(scope.get("predicates") or []),
        "temporal_labels": sorted(scope.get("temporal_labels") or []),
        "source_authorities": sorted(scope.get("source_authorities") or []),
        "program_semantic_hash": task.oracle.task_program.semantic_hash,
        # Backward-compatible alias with corrected evidence-independent semantics.
        "program_hash": task.oracle.task_program.semantic_hash,
    }
    fields = (
        policy.cluster_fields
        if policy
        else (
            "domain",
            "task_type",
            "subject_ids",
            "predicates",
            "program_semantic_hash",
        )
    )
    unknown = tuple(field for field in fields if field not in features)
    if unknown:
        raise ValueError(f"split policy contains unknown cluster fields: {unknown}")
    return canonical_hash(
        {field: features[field] for field in fields},
        prefix="semantic_cluster:",
    )


def assign_split(task: TaskPackage, policy: SplitPolicy) -> DatasetSplit:
    bucket = int(canonical_hash(semantic_cluster_id(task, policy))[-8:], 16) % 100
    if bucket < policy.train_share:
        return DatasetSplit.TRAIN
    if bucket < policy.train_share + policy.dev_share:
        return DatasetSplit.DEV
    return DatasetSplit.TEST
