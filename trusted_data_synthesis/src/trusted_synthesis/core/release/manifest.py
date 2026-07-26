from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from trusted_synthesis.core.evaluation.evaluator import (
    CANDIDATE_REQUIRED_CHECK_MANIFEST,
    REQUIRED_CHECK_MANIFEST,
)
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.release.schema import (
    CandidateReleaseSelection,
    ReleaseManifest,
    SplitPolicy,
)
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
    candidate_selection: CandidateReleaseSelection | None = None,
) -> ReleaseManifest:
    task_items = tuple(tasks)
    adapter_items = tuple(adapters)
    if candidate_selection:
        unknown_tasks = set(candidate_selection.accepted_task_ids) - {
            task.task_id for task in task_items
        }
        if unknown_tasks:
            raise ValueError(
                f"candidate selection refers to unknown tasks: {sorted(unknown_tasks)}"
            )
    split_counts = (
        Counter(candidate_selection.split_counts)
        if candidate_selection
        else Counter(assign_split(task, split_policy).value for task in task_items)
    )
    released_total = (
        len(candidate_selection.accepted_trajectory_ids) if candidate_selection else len(task_items)
    )
    return ReleaseManifest(
        release_id=release_id,
        framework_version="0.3.0",
        evidence_schema_version="evidence_ir.v2",
        proof_graph_schema_version="proof_graph.v3",
        task_program_version="task_program.v2",
        operation_manifest_hash=canonical_hash(registry.manifest(), prefix="operation_manifest:"),
        required_check_manifest_hash=canonical_hash(
            REQUIRED_CHECK_MANIFEST, prefix="check_manifest:"
        ),
        candidate_required_check_manifest_hash=canonical_hash(
            CANDIDATE_REQUIRED_CHECK_MANIFEST, prefix="check_manifest:"
        ),
        split_policy_hash=split_policy.policy_hash,
        adapter_capabilities={
            adapter.adapter_id: tuple(item.value for item in adapter.capability_manifest())
            for adapter in adapter_items
        },
        source_build_ids=source_build_ids,
        sample_counts={"total": released_total, **dict(split_counts)},
        accepted_candidate_trajectory_ids=(
            candidate_selection.accepted_trajectory_ids if candidate_selection else ()
        ),
        quality_assessment_ids=(
            candidate_selection.quality_assessment_ids if candidate_selection else ()
        ),
        failure_distribution=(
            candidate_selection.failure_distribution if candidate_selection else {}
        ),
        domain_task_distribution=(
            candidate_selection.domain_task_distribution if candidate_selection else {}
        ),
    )
