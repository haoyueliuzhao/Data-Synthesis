from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from difflib import SequenceMatcher

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.schema import QualityAssessment, ReleaseDecision
from trusted_synthesis.core.release.schema import SplitPolicy
from trusted_synthesis.core.release.split import assign_realization_split
from trusted_synthesis.core.task.realization import RealizedTaskPackage
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.hashing import canonical_hash


class DiversityReleasePolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = Field(min_length=1)
    max_total: int = Field(default=10_000, ge=1)
    max_per_semantic_parent: int = Field(default=3, ge=1)
    coverage_gain_weight: float = Field(default=1.0, ge=0)
    similarity_penalty_weight: float = Field(default=0.25, ge=0)
    schema_version: str = "diversity_release_policy.v1"

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self, prefix="diversity_release_policy:")


class DiversityAwareReleaseSelection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    selection_id: str = Field(min_length=1)
    selected_realization_ids: tuple[str, ...]
    selected_trajectory_ids: tuple[str, ...]
    selected_quality_assessment_ids: tuple[str, ...]
    valid_but_not_selected_realization_ids: tuple[str, ...]
    failure_distribution: dict[str, int]
    split_counts: dict[str, int]
    semantic_parent_child_counts: dict[str, int]
    semantic_parent_child_weights: dict[str, str]
    skeleton_distribution: dict[str, int]
    largest_skeleton_share: float = Field(ge=0, le=1)
    policy_hash: str = Field(min_length=1)
    split_policy_hash: str = Field(min_length=1)
    hard_gates: dict[str, bool]
    schema_version: str = "diversity_aware_release_selection.v1"

    @model_validator(mode="after")
    def validate_selection(self) -> DiversityAwareReleaseSelection:
        if any(not passed for passed in self.hard_gates.values()):
            raise ValueError("diversity-aware release failed a hard gate")
        if len(self.selected_realization_ids) != len(set(self.selected_realization_ids)):
            raise ValueError("diversity-aware release contains duplicate realizations")
        if len(self.selected_trajectory_ids) != len(set(self.selected_trajectory_ids)):
            raise ValueError("diversity-aware release contains duplicate trajectories")
        if set(self.semantic_parent_child_weights) != set(self.semantic_parent_child_counts):
            raise ValueError("diversity-aware release parent-weight keys are incomplete")
        if any(
            weight != f"1/{self.semantic_parent_child_counts[parent]}"
            for parent, weight in self.semantic_parent_child_weights.items()
        ):
            raise ValueError("diversity-aware release does not conserve parent weights")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"selection_id"}),
            prefix="diversity_aware_release_selection:",
        )
        if self.selection_id != expected:
            raise ValueError("diversity-aware release identity is invalid")
        return self


def select_diversity_aware_release(
    records: Iterable[tuple[RealizedTaskPackage, Trajectory, QualityAssessment]],
    *,
    policy: DiversityReleasePolicy,
    split_policy: SplitPolicy,
) -> DiversityAwareReleaseSelection:
    valid = []
    failures: Counter[str] = Counter()
    for realized, trajectory, assessment in records:
        if trajectory.task_id != realized.task.task_id:
            raise ValueError("trajectory task identity mismatch")
        if assessment.task_id != realized.task.task_id:
            raise ValueError("quality assessment task identity mismatch")
        if assessment.trajectory_id != trajectory.trajectory_id:
            raise ValueError("quality assessment trajectory identity mismatch")
        if not realized.realization.validation.passed:
            raise ValueError("release cannot compensate for an invalid realization")
        if assessment.decision == ReleaseDecision.ACCEPTED:
            valid.append((realized, trajectory, assessment))
        else:
            failures.update(assessment.fatal_failures or (assessment.decision.value,))
    valid.sort(
        key=lambda item: (
            item[0].realization.semantic_task_id,
            item[0].realization.realization_id,
            item[1].trajectory_id,
        )
    )
    trajectory_ids = [item[1].trajectory_id for item in valid]
    if len(trajectory_ids) != len(set(trajectory_ids)):
        raise ValueError("valid release pool contains duplicate trajectory IDs")
    valid_realization_ids = [item[0].realization.realization_id for item in valid]
    if len(valid_realization_ids) != len(set(valid_realization_ids)):
        raise ValueError("valid release pool contains duplicate realization IDs")

    selected: list[tuple[RealizedTaskPackage, Trajectory, QualityAssessment]] = []
    remaining = list(valid)
    parent_counts: Counter[str] = Counter()
    selected_features: set[str] = set()
    selected_skeletons: list[str] = []
    while remaining and len(selected) < policy.max_total:
        eligible = [
            item
            for item in remaining
            if parent_counts[item[0].realization.semantic_task_id] < policy.max_per_semantic_parent
        ]
        if not eligible:
            break

        def rank(
            item: tuple[RealizedTaskPackage, Trajectory, QualityAssessment],
        ) -> tuple[float, str]:
            realized = item[0]
            realization = realized.realization
            features = {
                f"semantic:{realization.semantic_task_id}",
                f"program:{realized.task.oracle.task_program.semantic_hash}",
                f"family_skeleton:{realized.task.public.task_type}|"
                f"{realization.normalized_skeleton}",
                f"skeleton:{realization.normalized_skeleton}",
                f"style:{realization.style}",
                f"language:{realization.language}",
            }
            coverage_gain = len(features - selected_features)
            similarity = max(
                (
                    SequenceMatcher(
                        None,
                        realization.normalized_skeleton,
                        existing,
                    ).ratio()
                    for existing in selected_skeletons
                ),
                default=0.0,
            )
            gain = (
                policy.coverage_gain_weight * coverage_gain
                - policy.similarity_penalty_weight * similarity
            )
            tie_break = canonical_hash(
                {
                    "policy_hash": policy.policy_hash,
                    "realization_id": realization.realization_id,
                    "trajectory_id": item[1].trajectory_id,
                }
            )
            return gain, tie_break

        chosen = max(eligible, key=rank)
        remaining.remove(chosen)
        selected.append(chosen)
        realization = chosen[0].realization
        parent_counts[realization.semantic_task_id] += 1
        selected_skeletons.append(realization.normalized_skeleton)
        selected_features.update(
            {
                f"semantic:{realization.semantic_task_id}",
                f"program:{chosen[0].task.oracle.task_program.semantic_hash}",
                f"family_skeleton:{chosen[0].task.public.task_type}|"
                f"{realization.normalized_skeleton}",
                f"skeleton:{realization.normalized_skeleton}",
                f"style:{realization.style}",
                f"language:{realization.language}",
            }
        )

    selected_realization_ids = tuple(item[0].realization.realization_id for item in selected)
    selected_set = set(selected_realization_ids)
    not_selected = tuple(
        sorted(
            item[0].realization.realization_id
            for item in valid
            if item[0].realization.realization_id not in selected_set
        )
    )
    split_counts = Counter(
        assign_realization_split(item[0], split_policy).value for item in selected
    )
    skeletons = Counter(item[0].realization.normalized_skeleton for item in selected)
    total = len(selected)
    child_counts = dict(sorted(parent_counts.items()))
    child_weights = {parent: f"1/{count}" for parent, count in child_counts.items()}
    hard_gates = {
        "quality_accepted_only": all(
            item[2].decision == ReleaseDecision.ACCEPTED for item in selected
        ),
        "realization_contract_pass_only": all(
            item[0].realization.validation.passed for item in selected
        ),
        "semantic_parent_quota_respected": all(
            count <= policy.max_per_semantic_parent for count in parent_counts.values()
        ),
        "semantic_parent_weight_conserved": all(
            child_weights[parent] == f"1/{count}" for parent, count in child_counts.items()
        ),
        "selected_realization_collision_zero": len(selected_realization_ids)
        == len(set(selected_realization_ids)),
        "selected_trajectory_collision_zero": len(selected)
        == len({item[1].trajectory_id for item in selected}),
    }
    payload = {
        "selected_realization_ids": selected_realization_ids,
        "selected_trajectory_ids": tuple(item[1].trajectory_id for item in selected),
        "selected_quality_assessment_ids": tuple(item[2].assessment_id for item in selected),
        "valid_but_not_selected_realization_ids": not_selected,
        "failure_distribution": dict(sorted(failures.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "semantic_parent_child_counts": child_counts,
        "semantic_parent_child_weights": child_weights,
        "skeleton_distribution": dict(sorted(skeletons.items())),
        "largest_skeleton_share": (max(skeletons.values(), default=0) / total if total else 0.0),
        "policy_hash": policy.policy_hash,
        "split_policy_hash": split_policy.policy_hash,
        "hard_gates": hard_gates,
        "schema_version": "diversity_aware_release_selection.v1",
    }
    selection_id = canonical_hash(
        payload,
        prefix="diversity_aware_release_selection:",
    )
    return DiversityAwareReleaseSelection(selection_id=selection_id, **payload)
