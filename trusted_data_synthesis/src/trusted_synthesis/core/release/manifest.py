from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from trusted_synthesis.core.evaluation.evaluator import REQUIRED_CHECK_MANIFEST
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.release.schema import ReleaseManifest, SplitPolicy
from trusted_synthesis.core.release.split import assign_split
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.domains.base import DomainAdapter
from trusted_synthesis.hashing import canonical_hash


def build_release_manifest(
    *,
    release_id: str,
    tasks: Iterable[TaskPackage],
    adapters: Iterable[DomainAdapter],
    registry: OperationRegistry,
    split_policy: SplitPolicy,
    source_build_ids: dict[str, str],
) -> ReleaseManifest:
    task_items = tuple(tasks)
    adapter_items = tuple(adapters)
    split_counts = Counter(assign_split(task, split_policy).value for task in task_items)
    return ReleaseManifest(
        release_id=release_id,
        framework_version="0.2.0",
        evidence_schema_version="evidence_ir.v2",
        proof_graph_schema_version="proof_graph.v2",
        task_program_version="task_program.v1",
        operation_manifest_hash=canonical_hash(registry.manifest(), prefix="operation_manifest:"),
        required_check_manifest_hash=canonical_hash(
            REQUIRED_CHECK_MANIFEST, prefix="check_manifest:"
        ),
        split_policy_hash=split_policy.policy_hash,
        adapter_capabilities={
            adapter.adapter_id: tuple(item.value for item in adapter.capability_manifest())
            for adapter in adapter_items
        },
        source_build_ids=source_build_ids,
        sample_counts={"total": len(task_items), **dict(split_counts)},
    )
