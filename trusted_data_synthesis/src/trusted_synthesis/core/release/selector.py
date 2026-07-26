from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from trusted_synthesis.core.evaluation.schema import QualityAssessment, ReleaseDecision
from trusted_synthesis.core.release.schema import CandidateReleaseSelection, SplitPolicy
from trusted_synthesis.core.release.split import assign_split
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.hashing import canonical_hash


def select_candidate_release(
    records: Iterable[tuple[TaskPackage, Trajectory, QualityAssessment]],
    split_policy: SplitPolicy,
) -> CandidateReleaseSelection:
    """Select only accepted candidates and preserve rejected failure diagnostics."""

    accepted = []
    failures: Counter[str] = Counter()
    for task, trajectory, assessment in records:
        if assessment.task_id != task.task_id:
            raise ValueError("quality assessment task identity mismatch")
        if assessment.trajectory_id != trajectory.trajectory_id:
            raise ValueError("quality assessment trajectory identity mismatch")
        if assessment.decision == ReleaseDecision.ACCEPTED:
            accepted.append((task, trajectory, assessment))
        else:
            failures.update(assessment.fatal_failures or (assessment.decision.value,))
    accepted.sort(key=lambda item: (item[0].task_id, item[1].trajectory_id))
    trajectory_ids = [item[1].trajectory_id for item in accepted]
    if len(trajectory_ids) != len(set(trajectory_ids)):
        raise ValueError("candidate release contains duplicate trajectory IDs")
    split_counts = Counter(assign_split(item[0], split_policy).value for item in accepted)
    distributions = Counter(
        f"{item[0].public.domain}|{item[0].public.task_type}" for item in accepted
    )
    identity = {
        "accepted": [
            {
                "task_id": task.task_id,
                "trajectory_id": trajectory.trajectory_id,
                "assessment_id": assessment.assessment_id,
            }
            for task, trajectory, assessment in accepted
        ],
        "split_policy_hash": split_policy.policy_hash,
    }
    return CandidateReleaseSelection(
        selection_id=canonical_hash(identity, prefix="candidate_release_selection:"),
        accepted_task_ids=tuple(item[0].task_id for item in accepted),
        accepted_trajectory_ids=tuple(trajectory_ids),
        quality_assessment_ids=tuple(item[2].assessment_id for item in accepted),
        failure_distribution=dict(sorted(failures.items())),
        domain_task_distribution=dict(sorted(distributions.items())),
        split_counts=dict(sorted(split_counts.items())),
    )
