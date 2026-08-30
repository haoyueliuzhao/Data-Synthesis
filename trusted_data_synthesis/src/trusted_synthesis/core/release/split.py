from __future__ import annotations

from enum import Enum

from trusted_synthesis.core.release.schema import SplitPolicy
from trusted_synthesis.core.task.realization import RealizedTaskPackage
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


def semantic_parent_cluster_id(semantic_task_id: str) -> str:
    if not semantic_task_id:
        raise ValueError("semantic parent split requires a semantic task identity")
    return canonical_hash(
        {
            "semantic_task_id": semantic_task_id,
            "schema_version": "semantic_parent_cluster.v1",
        },
        prefix="semantic_parent_cluster:",
    )


def assign_semantic_parent_split(
    semantic_task_id: str,
    policy: SplitPolicy,
) -> DatasetSplit:
    bucket = int(canonical_hash(semantic_parent_cluster_id(semantic_task_id))[-8:], 16) % 100
    if bucket < policy.train_share:
        return DatasetSplit.TRAIN
    if bucket < policy.train_share + policy.dev_share:
        return DatasetSplit.DEV
    return DatasetSplit.TEST


def semantic_instance_cluster_id(semantic_instance_id: str) -> str:
    if not semantic_instance_id:
        raise ValueError("semantic instance split requires a semantic instance identity")
    return canonical_hash(
        {
            "semantic_instance_id": semantic_instance_id,
            "schema_version": "semantic_instance_cluster.v1",
        },
        prefix="semantic_instance_cluster:",
    )


def assign_semantic_instance_split(
    semantic_instance_id: str,
    policy: SplitPolicy,
) -> DatasetSplit:
    bucket = int(canonical_hash(semantic_instance_cluster_id(semantic_instance_id))[-8:], 16) % 100
    if bucket < policy.train_share:
        return DatasetSplit.TRAIN
    if bucket < policy.train_share + policy.dev_share:
        return DatasetSplit.DEV
    return DatasetSplit.TEST


def assign_realization_split(
    realized: RealizedTaskPackage,
    policy: SplitPolicy,
) -> DatasetSplit:
    return assign_semantic_instance_split(realized.semantic_instance_id, policy)
