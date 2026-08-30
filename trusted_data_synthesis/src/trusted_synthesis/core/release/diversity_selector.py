from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from difflib import SequenceMatcher
from fractions import Fraction

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.realization_binding import (
    RealizationExecutionBinding,
    bind_realization_execution,
)
from trusted_synthesis.core.evaluation.schema import QualityAssessment, ReleaseDecision
from trusted_synthesis.core.release.schema import SplitPolicy
from trusted_synthesis.core.release.split import assign_realization_split
from trusted_synthesis.core.task.realization import RealizedTaskPackage
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.hashing import canonical_hash

ReleaseRecord = tuple[
    RealizedTaskPackage,
    Trajectory,
    QualityAssessment,
    RealizationExecutionBinding,
]


class DiversityReleasePolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = Field(min_length=1)
    max_total: int = Field(default=10_000, ge=1)
    max_per_semantic_instance: int = Field(default=3, ge=1)
    max_per_semantic_schema: int = Field(default=10_000, ge=1)
    coverage_gain_weight: float = Field(default=1.0, ge=0)
    similarity_penalty_weight: float = Field(default=0.25, ge=0)
    schema_version: str = "diversity_release_policy.v2"

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self, prefix="diversity_release_policy:")


class PersistedReleaseRecord(BaseModel):
    """One exact package/trajectory/assessment/binding row used by selection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str = Field(min_length=1)
    realized: RealizedTaskPackage
    trajectory: Trajectory
    assessment: QualityAssessment
    execution_binding: RealizationExecutionBinding
    schema_version: str = "persisted_release_record.v1"

    @model_validator(mode="after")
    def validate_record(self) -> PersistedReleaseRecord:
        expected_binding = bind_realization_execution(
            self.realized,
            self.execution_binding.realization_portfolio,
            self.trajectory,
            self.assessment,
            self.execution_binding.execution_descriptor,
        )
        if self.execution_binding != expected_binding:
            raise ValueError("persisted release record binding is not derived")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"record_id"}),
            prefix="persisted_release_record:",
        )
        if self.record_id != expected:
            raise ValueError("persisted release record identity is invalid")
        return self

    def as_tuple(self) -> ReleaseRecord:
        return (
            self.realized,
            self.trajectory,
            self.assessment,
            self.execution_binding,
        )


class ReleaseWeightAssignment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    assignment_id: str = Field(min_length=1)
    release_plan_id: str = Field(min_length=1)
    semantic_schema_id: str = Field(min_length=1)
    semantic_instance_id: str = Field(min_length=1)
    binding_snapshot_id: str = Field(min_length=1)
    realized_package_id: str = Field(min_length=1)
    realization_id: str = Field(min_length=1)
    execution_binding_id: str = Field(min_length=1)
    numerator: int = Field(ge=1)
    denominator: int = Field(ge=1)
    exact_fraction: str = Field(pattern=r"^[1-9][0-9]*/[1-9][0-9]*$")
    schema_version: str = "release_weight_assignment.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> ReleaseWeightAssignment:
        reduced = Fraction(self.numerator, self.denominator)
        expected_fraction = f"{reduced.numerator}/{reduced.denominator}"
        if self.exact_fraction != expected_fraction:
            raise ValueError("release weight is not the exact reduced Fraction")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"assignment_id"}),
            prefix="release_weight_assignment:",
        )
        if self.assignment_id != expected:
            raise ValueError("release weight assignment identity is invalid")
        return self


class DiversityAwareReleaseSelection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    selection_id: str = Field(min_length=1)
    release_plan_id: str = Field(min_length=1)
    release_policy: DiversityReleasePolicy
    split_policy: SplitPolicy
    release_records: tuple[PersistedReleaseRecord, ...]
    selected_realized_package_ids: tuple[str, ...]
    selected_realization_ids: tuple[str, ...]
    selected_trajectory_ids: tuple[str, ...]
    selected_quality_assessment_ids: tuple[str, ...]
    selected_execution_binding_ids: tuple[str, ...]
    valid_but_not_selected_realized_package_ids: tuple[str, ...]
    valid_but_not_selected_realization_ids: tuple[str, ...]
    failure_distribution: dict[str, int]
    split_counts: dict[str, int]
    semantic_instance_child_counts: dict[str, int]
    semantic_schema_child_counts: dict[str, int]
    weight_assignments: tuple[ReleaseWeightAssignment, ...]
    skeleton_distribution: dict[str, int]
    largest_skeleton_share: float = Field(ge=0, le=1)
    policy_hash: str = Field(min_length=1)
    split_policy_hash: str = Field(min_length=1)
    hard_gates: dict[str, bool]
    schema_version: str = "diversity_aware_release_selection.v3"

    @model_validator(mode="after")
    def validate_selection(self) -> DiversityAwareReleaseSelection:
        if self.policy_hash != self.release_policy.policy_hash:
            raise ValueError("persisted release policy hash is not derived")
        if self.split_policy_hash != self.split_policy.policy_hash:
            raise ValueError("persisted split policy hash is not derived")
        for record in self.release_records:
            PersistedReleaseRecord.model_validate(record.model_dump(mode="python", warnings=False))
        record_ids = tuple(record.record_id for record in self.release_records)
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("persisted release records contain duplicate identities")
        expected = select_diversity_aware_release(
            (record.as_tuple() for record in self.release_records),
            policy=self.release_policy,
            split_policy=self.split_policy,
            _validate=False,
        )
        observed_payload = self.model_dump(mode="json", exclude={"selection_id"})
        expected_payload = expected.model_dump(mode="json", exclude={"selection_id"})
        if observed_payload != expected_payload:
            raise ValueError("persisted release selection is not source-derived")
        if any(not passed for passed in self.hard_gates.values()):
            raise ValueError("diversity-aware release failed a hard gate")
        selected_sets = (
            self.selected_realized_package_ids,
            self.selected_realization_ids,
            self.selected_trajectory_ids,
            self.selected_quality_assessment_ids,
            self.selected_execution_binding_ids,
        )
        if len({len(values) for values in selected_sets}) != 1:
            raise ValueError("diversity-aware release selected-parent cardinality differs")
        if any(len(values) != len(set(values)) for values in selected_sets):
            raise ValueError("diversity-aware release contains duplicate selected identities")
        for assignment in self.weight_assignments:
            ReleaseWeightAssignment.model_validate(
                assignment.model_dump(mode="python", warnings=False)
            )
        if len(self.weight_assignments) != len(self.selected_realization_ids):
            raise ValueError("release weight assignment coverage is incomplete")
        if {row.realized_package_id for row in self.weight_assignments} != set(
            self.selected_realized_package_ids
        ):
            raise ValueError("release weights do not cover selected packages exactly")
        if {row.realization_id for row in self.weight_assignments} != set(
            self.selected_realization_ids
        ):
            raise ValueError("release weights do not cover selected realizations exactly")
        if {row.execution_binding_id for row in self.weight_assignments} != set(
            self.selected_execution_binding_ids
        ):
            raise ValueError("release weights do not cover execution bindings exactly")
        if any(row.release_plan_id != self.release_plan_id for row in self.weight_assignments):
            raise ValueError("release weight crosses its release plan")
        observed_counts = Counter(row.semantic_instance_id for row in self.weight_assignments)
        if dict(sorted(observed_counts.items())) != self.semantic_instance_child_counts:
            raise ValueError("release instance child counts disagree with assignments")
        for instance_id in observed_counts:
            total = sum(
                (
                    Fraction(row.numerator, row.denominator)
                    for row in self.weight_assignments
                    if row.semantic_instance_id == instance_id
                ),
                start=Fraction(0, 1),
            )
            if total != Fraction(1, 1):
                raise ValueError("release weights do not exactly conserve instance mass")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"selection_id"}),
            prefix="diversity_aware_release_selection:",
        )
        if self.selection_id != expected:
            raise ValueError("diversity-aware release identity is invalid")
        return self


def select_diversity_aware_release(
    records: Iterable[ReleaseRecord],
    *,
    policy: DiversityReleasePolicy,
    split_policy: SplitPolicy,
    _validate: bool = True,
) -> DiversityAwareReleaseSelection:
    records_tuple = tuple(records)
    persisted_records = tuple(
        sorted(
            (_persist_release_record(row) for row in records_tuple), key=lambda row: row.record_id
        )
    )
    valid: list[ReleaseRecord] = []
    failures: Counter[str] = Counter()
    for realized, trajectory, assessment, execution_binding in records_tuple:
        expected_binding = bind_realization_execution(
            realized,
            execution_binding.realization_portfolio,
            trajectory,
            assessment,
            execution_binding.execution_descriptor,
        )
        if execution_binding != expected_binding:
            raise ValueError("realization execution binding does not match record contents")
        if not realized.realization.validation.passed:
            raise ValueError("release cannot compensate for an invalid realization")
        if assessment.decision == ReleaseDecision.ACCEPTED:
            valid.append((realized, trajectory, assessment, execution_binding))
        else:
            failures.update(assessment.fatal_failures or (assessment.decision.value,))
    valid.sort(
        key=lambda item: (
            item[0].semantic_instance_id,
            item[0].realization.realization_id,
            item[1].trajectory_id,
        )
    )
    for offset, label in ((1, "trajectory"), (0, "realized package"), (3, "execution binding")):
        values = [
            item[offset].trajectory_id
            if offset == 1
            else item[offset].realized_package_id
            if offset == 0
            else item[offset].execution_binding_id
            for item in valid
        ]
        if len(values) != len(set(values)):
            raise ValueError(f"valid release pool contains duplicate {label} IDs")

    selected: list[ReleaseRecord] = []
    remaining = list(valid)
    instance_counts: Counter[str] = Counter()
    schema_counts: Counter[str] = Counter()
    selected_features: set[str] = set()
    selected_skeletons: list[str] = []
    while remaining and len(selected) < policy.max_total:
        eligible = [
            item
            for item in remaining
            if instance_counts[item[0].semantic_instance_id] < policy.max_per_semantic_instance
            and schema_counts[item[0].semantic_plan.semantic_task_id]
            < policy.max_per_semantic_schema
        ]
        if not eligible:
            break

        def rank(item: ReleaseRecord) -> tuple[float, str]:
            realized = item[0]
            realization = realized.realization
            features = {
                f"schema:{realized.semantic_plan.semantic_task_id}",
                f"instance:{realized.semantic_instance_id}",
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
                    "execution_binding_id": item[3].execution_binding_id,
                }
            )
            return gain, tie_break

        chosen = max(eligible, key=rank)
        remaining.remove(chosen)
        selected.append(chosen)
        realized = chosen[0]
        realization = realized.realization
        instance_counts[realized.semantic_instance_id] += 1
        schema_counts[realized.semantic_plan.semantic_task_id] += 1
        selected_skeletons.append(realization.normalized_skeleton)
        selected_features.update(
            {
                f"schema:{realized.semantic_plan.semantic_task_id}",
                f"instance:{realized.semantic_instance_id}",
                f"program:{realized.task.oracle.task_program.semantic_hash}",
                f"family_skeleton:{realized.task.public.task_type}|"
                f"{realization.normalized_skeleton}",
                f"skeleton:{realization.normalized_skeleton}",
                f"style:{realization.style}",
                f"language:{realization.language}",
            }
        )

    selected_package_ids = tuple(item[0].realized_package_id for item in selected)
    selected_realization_ids = tuple(item[0].realization.realization_id for item in selected)
    selected_execution_ids = tuple(item[3].execution_binding_id for item in selected)
    selected_package_set = set(selected_package_ids)
    not_selected_packages = tuple(
        sorted(
            item[0].realized_package_id
            for item in valid
            if item[0].realized_package_id not in selected_package_set
        )
    )
    not_selected_package_set = set(not_selected_packages)
    not_selected_realizations = tuple(
        sorted(
            item[0].realization.realization_id
            for item in valid
            if item[0].realized_package_id in not_selected_package_set
        )
    )
    release_plan_payload = {
        "selected_execution_binding_ids": selected_execution_ids,
        "policy_hash": policy.policy_hash,
        "split_policy_hash": split_policy.policy_hash,
        "schema_version": "release_plan.v1",
    }
    release_plan_id = canonical_hash(release_plan_payload, prefix="release_plan:")
    child_counts = dict(sorted(instance_counts.items()))
    assignments = tuple(
        _make_weight_assignment(
            release_plan_id=release_plan_id,
            record=item,
            denominator=child_counts[item[0].semantic_instance_id],
        )
        for item in selected
    )
    split_counts = Counter(
        assign_realization_split(item[0], split_policy).value for item in selected
    )
    skeletons = Counter(item[0].realization.normalized_skeleton for item in selected)
    total = len(selected)
    schema_child_counts = dict(sorted(schema_counts.items()))
    hard_gates = {
        "quality_accepted_only": all(
            item[2].decision == ReleaseDecision.ACCEPTED for item in selected
        ),
        "realization_contract_pass_only": all(
            item[0].realization.validation.passed for item in selected
        ),
        "execution_binding_exact": all(
            item[3]
            == bind_realization_execution(
                item[0],
                item[3].realization_portfolio,
                item[1],
                item[2],
                item[3].execution_descriptor,
            )
            for item in selected
        ),
        "semantic_instance_quota_respected": all(
            count <= policy.max_per_semantic_instance for count in instance_counts.values()
        ),
        "semantic_schema_quota_respected": all(
            count <= policy.max_per_semantic_schema for count in schema_counts.values()
        ),
        "instance_weight_exactly_conserved": all(
            sum(
                (
                    Fraction(row.numerator, row.denominator)
                    for row in assignments
                    if row.semantic_instance_id == instance_id
                ),
                start=Fraction(0, 1),
            )
            == Fraction(1, 1)
            for instance_id in instance_counts
        ),
        "selected_identity_collision_zero": all(
            len(values) == len(set(values))
            for values in (
                selected_package_ids,
                selected_realization_ids,
                tuple(item[1].trajectory_id for item in selected),
                selected_execution_ids,
            )
        ),
    }
    payload = {
        "release_plan_id": release_plan_id,
        "release_policy": policy,
        "split_policy": split_policy,
        "release_records": persisted_records,
        "selected_realized_package_ids": selected_package_ids,
        "selected_realization_ids": selected_realization_ids,
        "selected_trajectory_ids": tuple(item[1].trajectory_id for item in selected),
        "selected_quality_assessment_ids": tuple(item[2].assessment_id for item in selected),
        "selected_execution_binding_ids": selected_execution_ids,
        "valid_but_not_selected_realized_package_ids": not_selected_packages,
        "valid_but_not_selected_realization_ids": not_selected_realizations,
        "failure_distribution": dict(sorted(failures.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "semantic_instance_child_counts": child_counts,
        "semantic_schema_child_counts": schema_child_counts,
        "weight_assignments": assignments,
        "skeleton_distribution": dict(sorted(skeletons.items())),
        "largest_skeleton_share": (max(skeletons.values(), default=0) / total if total else 0.0),
        "policy_hash": policy.policy_hash,
        "split_policy_hash": split_policy.policy_hash,
        "hard_gates": hard_gates,
        "schema_version": "diversity_aware_release_selection.v3",
    }
    provisional = DiversityAwareReleaseSelection.model_construct(
        selection_id="pending",
        **payload,
    )
    selection_id = canonical_hash(
        provisional.model_dump(mode="json", exclude={"selection_id"}),
        prefix="diversity_aware_release_selection:",
    )
    if not _validate:
        return DiversityAwareReleaseSelection.model_construct(
            selection_id=selection_id,
            **payload,
        )
    return DiversityAwareReleaseSelection(selection_id=selection_id, **payload)


def _persist_release_record(record: ReleaseRecord) -> PersistedReleaseRecord:
    realized, trajectory, assessment, execution_binding = record
    payload = {
        "realized": realized,
        "trajectory": trajectory,
        "assessment": assessment,
        "execution_binding": execution_binding,
        "schema_version": "persisted_release_record.v1",
    }
    provisional = PersistedReleaseRecord.model_construct(
        record_id="pending",
        **payload,
    )
    record_id = canonical_hash(
        provisional.model_dump(mode="json", exclude={"record_id"}),
        prefix="persisted_release_record:",
    )
    return PersistedReleaseRecord(record_id=record_id, **payload)


def _make_weight_assignment(
    *,
    release_plan_id: str,
    record: ReleaseRecord,
    denominator: int,
) -> ReleaseWeightAssignment:
    realized, _, _, execution_binding = record
    reduced = Fraction(1, denominator)
    payload = {
        "release_plan_id": release_plan_id,
        "semantic_schema_id": realized.semantic_plan.semantic_task_id,
        "semantic_instance_id": realized.semantic_instance_id,
        "binding_snapshot_id": realized.binding_snapshot_id,
        "realized_package_id": realized.realized_package_id,
        "realization_id": realized.realization.realization_id,
        "execution_binding_id": execution_binding.execution_binding_id,
        "numerator": reduced.numerator,
        "denominator": reduced.denominator,
        "exact_fraction": f"{reduced.numerator}/{reduced.denominator}",
        "schema_version": "release_weight_assignment.v1",
    }
    assignment_id = canonical_hash(payload, prefix="release_weight_assignment:")
    return ReleaseWeightAssignment(assignment_id=assignment_id, **payload)
