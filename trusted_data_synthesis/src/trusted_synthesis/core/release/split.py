from __future__ import annotations

from enum import Enum

from trusted_synthesis.core.release.schema import SplitPolicy
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.hashing import canonical_hash


class DatasetSplit(str, Enum):
    TRAIN = "train"
    DEV = "dev"
    TEST = "test"


def semantic_cluster_id(task: TaskPackage) -> str:
    scope = task.public.retrieval_scope
    return canonical_hash(
        {
            "domain": task.public.domain,
            "task_type": task.public.task_type,
            "subject_ids": sorted(scope.get("subject_ids") or []),
            "predicates": sorted(scope.get("predicates") or []),
            "program_hash": task.oracle.task_program.program_hash,
        },
        prefix="semantic_cluster:",
    )


def assign_split(task: TaskPackage, policy: SplitPolicy) -> DatasetSplit:
    bucket = int(canonical_hash(semantic_cluster_id(task))[-8:], 16) % 100
    if bucket < policy.train_share:
        return DatasetSplit.TRAIN
    if bucket < policy.train_share + policy.dev_share:
        return DatasetSplit.DEV
    return DatasetSplit.TEST
