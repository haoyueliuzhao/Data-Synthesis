from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable
from itertools import islice
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.attributes import TrajectoryAttributeProfile
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.core.trajectory.specification import TrajectoryVerificationContext
from trusted_synthesis.core.trajectory.validity import (
    TrajectoryValidityEvaluator,
    TrajectoryValidityReport,
)
from trusted_synthesis.hashing import canonical_hash

VALID_TRAJECTORY_POOL_VERSION = "valid_trajectory_pool.v1"


class ValidTrajectoryPool(BaseModel):
    """Verified alternatives for one task; reference examples have no privileged rank."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pool_id: str = Field(min_length=1)
    context_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    attempted_count: int = Field(ge=1)
    verified_valid_count: int = Field(ge=0)
    retained_valid_count: int = Field(ge=0)
    minimum_valid_count: int = Field(ge=1)
    max_per_profile: int | None = Field(default=None, ge=1)
    validity_rate: float = Field(ge=0, le=1)
    retained_trajectories: tuple[Trajectory, ...] = ()
    validity_reports: tuple[TrajectoryValidityReport, ...] = Field(min_length=1)
    rejected_trajectory_ids: tuple[str, ...] = ()
    diversity_pruned_trajectory_ids: tuple[str, ...] = ()
    attribute_profile_counts: dict[str, int] = Field(default_factory=dict)
    trajectory_attribute_entropy: float = Field(ge=0)
    capability_coverage: tuple[str, ...] = ()
    status: Literal["passed", "blocked"]
    version: str = VALID_TRAJECTORY_POOL_VERSION

    @model_validator(mode="after")
    def validate_pool(self) -> ValidTrajectoryPool:
        if len(self.validity_reports) != self.attempted_count:
            raise ValueError("trajectory pool must retain every validity report")
        report_ids = [item.trajectory_id for item in self.validity_reports]
        if len(report_ids) != len(set(report_ids)):
            raise ValueError("trajectory pool reports contain duplicate trajectories")
        retained_ids = [item.trajectory_id for item in self.retained_trajectories]
        if len(retained_ids) != len(set(retained_ids)):
            raise ValueError("trajectory pool retained duplicate trajectories")
        reports = {item.trajectory_id: item for item in self.validity_reports}
        if any(not reports[item].valid for item in retained_ids):
            raise ValueError("trajectory pool can retain only independently valid trajectories")
        if self.verified_valid_count != sum(item.valid for item in self.validity_reports):
            raise ValueError("verified-valid trajectory count is inconsistent")
        if self.retained_valid_count != len(self.retained_trajectories):
            raise ValueError("retained-valid trajectory count is inconsistent")
        if not math.isclose(
            self.validity_rate,
            self.verified_valid_count / self.attempted_count,
            abs_tol=1e-12,
        ):
            raise ValueError("trajectory pool validity rate is inconsistent")
        expected_status = (
            "passed"
            if self.retained_valid_count >= self.minimum_valid_count
            else "blocked"
        )
        if self.status != expected_status:
            raise ValueError("trajectory pool status is inconsistent")
        if self.pool_id != valid_trajectory_pool_id(self):
            raise ValueError("valid trajectory pool identity is invalid")
        return self


class TrajectoryCandidateProviderProtocol(Protocol):
    """Generate alternative executions for one frozen verification context."""

    provider_id: str
    provider_version: str

    def generate(
        self,
        context: TrajectoryVerificationContext,
        target_profile: TrajectoryAttributeProfile,
        *,
        candidate_count: int,
        seed: int,
    ) -> Iterable[Trajectory]: ...


class TrajectoryPoolMaterializationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    report_id: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    context_id: str = Field(min_length=1)
    target_profile_id: str = Field(min_length=1)
    seed: int
    requested_candidate_count: int = Field(ge=1)
    generated_candidate_count: int = Field(ge=0)
    verified_candidate_count: int = Field(ge=0)
    retained_valid_count: int = Field(ge=0)
    minimum_valid_count: int = Field(ge=1)
    pool_id: str | None = None
    status: Literal["passed", "blocked"]
    failures: tuple[str, ...] = ()
    version: str = "trajectory_pool_materializer.v1"

    @model_validator(mode="after")
    def validate_report(self) -> TrajectoryPoolMaterializationReport:
        expected = (
            "passed"
            if self.generated_candidate_count == self.requested_candidate_count
            and self.verified_candidate_count == self.generated_candidate_count
            and self.retained_valid_count >= self.minimum_valid_count
            and self.pool_id is not None
            and not self.failures
            else "blocked"
        )
        if self.status != expected:
            raise ValueError("trajectory pool materialization status is inconsistent")
        if self.report_id != trajectory_pool_materialization_report_id(self):
            raise ValueError("trajectory pool materialization identity is invalid")
        return self


class ValidTrajectoryPoolBuilder:
    """Evaluate multiple candidates and retain a diverse valid trajectory pool."""

    def __init__(self, evaluator: TrajectoryValidityEvaluator) -> None:
        self._evaluator = evaluator

    def build(
        self,
        context: TrajectoryVerificationContext,
        trajectories: Iterable[Trajectory],
        *,
        minimum_valid_count: int = 1,
        max_per_profile: int | None = None,
    ) -> ValidTrajectoryPool:
        if minimum_valid_count < 1:
            raise ValueError("minimum valid trajectory count must be positive")
        if max_per_profile is not None and max_per_profile < 1:
            raise ValueError("trajectory profile cap must be positive")
        items = tuple(sorted(trajectories, key=lambda item: item.trajectory_id))
        if not items:
            raise ValueError("trajectory pool requires at least one candidate")
        if len({item.trajectory_id for item in items}) != len(items):
            raise ValueError("trajectory pool candidates must have unique identities")
        if any(item.task_id != context.task.task_id for item in items):
            raise ValueError("trajectory pool candidates belong to another task")
        reports = tuple(self._evaluator.evaluate(context, item) for item in items)
        reports_by_id = {item.trajectory_id: item for item in reports}
        valid_items = tuple(item for item in items if reports_by_id[item.trajectory_id].valid)
        retained, pruned = _apply_profile_cap(
            valid_items,
            reports_by_id,
            max_per_profile,
        )
        rejected = tuple(
            item.trajectory_id
            for item in items
            if not reports_by_id[item.trajectory_id].valid
        )
        profile_counts = Counter(
            reports_by_id[item.trajectory_id].attributes.profile.profile_id
            for item in retained
        )
        capabilities = tuple(
            sorted(
                {
                    tag
                    for item in retained
                    for tag in reports_by_id[item.trajectory_id].attributes.capability_tags
                }
            )
        )
        values = {
            "context_id": context.context_id,
            "task_id": context.task.task_id,
            "attempted_count": len(items),
            "verified_valid_count": len(valid_items),
            "retained_valid_count": len(retained),
            "minimum_valid_count": minimum_valid_count,
            "max_per_profile": max_per_profile,
            "validity_rate": len(valid_items) / len(items),
            "retained_trajectories": retained,
            "validity_reports": reports,
            "rejected_trajectory_ids": rejected,
            "diversity_pruned_trajectory_ids": pruned,
            "attribute_profile_counts": dict(sorted(profile_counts.items())),
            "trajectory_attribute_entropy": _entropy(profile_counts),
            "capability_coverage": capabilities,
            "status": "passed" if len(retained) >= minimum_valid_count else "blocked",
            "version": VALID_TRAJECTORY_POOL_VERSION,
        }
        provisional = ValidTrajectoryPool.model_construct(pool_id="pending", **values)
        return ValidTrajectoryPool(
            pool_id=valid_trajectory_pool_id(provisional),
            **values,
        )


class ValidTrajectoryMaterializer:
    """Generate several executions, verify all, and retain only the valid pool."""

    def __init__(
        self,
        provider: TrajectoryCandidateProviderProtocol,
        evaluator: TrajectoryValidityEvaluator,
    ) -> None:
        self._provider = provider
        self._builder = ValidTrajectoryPoolBuilder(evaluator)

    def materialize(
        self,
        context: TrajectoryVerificationContext,
        target_profile: TrajectoryAttributeProfile,
        *,
        candidate_count: int,
        minimum_valid_count: int,
        seed: int,
        max_per_profile: int | None = None,
    ) -> tuple[ValidTrajectoryPool | None, TrajectoryPoolMaterializationReport]:
        if candidate_count < 1:
            raise ValueError("trajectory candidate count must be positive")
        if minimum_valid_count < 1 or minimum_valid_count > candidate_count:
            raise ValueError("minimum valid count must fit the candidate budget")
        failures: list[str] = []
        candidates: tuple[Trajectory, ...] = ()
        pool: ValidTrajectoryPool | None = None
        try:
            candidates = tuple(
                islice(
                    self._provider.generate(
                        context,
                        target_profile,
                        candidate_count=candidate_count,
                        seed=seed,
                    ),
                    candidate_count,
                )
            )
        except Exception as exc:
            failures.append(f"provider:{type(exc).__name__}:{exc}")
        if len(candidates) < candidate_count:
            failures.append("candidate_provider_exhausted")
        if candidates:
            try:
                pool = self._builder.build(
                    context,
                    candidates,
                    minimum_valid_count=minimum_valid_count,
                    max_per_profile=max_per_profile,
                )
            except Exception as exc:
                failures.append(f"verification:{type(exc).__name__}:{exc}")
        if pool is not None and pool.status != "passed":
            failures.append("minimum_valid_trajectory_count_not_met")
        values = {
            "provider_id": self._provider.provider_id,
            "provider_version": self._provider.provider_version,
            "context_id": context.context_id,
            "target_profile_id": target_profile.profile_id,
            "seed": seed,
            "requested_candidate_count": candidate_count,
            "generated_candidate_count": len(candidates),
            "verified_candidate_count": (
                len(pool.validity_reports) if pool is not None else 0
            ),
            "retained_valid_count": (pool.retained_valid_count if pool is not None else 0),
            "minimum_valid_count": minimum_valid_count,
            "pool_id": pool.pool_id if pool is not None else None,
            "status": "passed" if not failures else "blocked",
            "failures": tuple(failures),
            "version": "trajectory_pool_materializer.v1",
        }
        provisional = TrajectoryPoolMaterializationReport.model_construct(
            report_id="pending",
            **values,
        )
        report = TrajectoryPoolMaterializationReport(
            report_id=trajectory_pool_materialization_report_id(provisional),
            **values,
        )
        return pool, report


def trajectory_pool_materialization_report_id(
    value: TrajectoryPoolMaterializationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="trajectory_pool_materialization_report:",
    )


def valid_trajectory_pool_id(value: ValidTrajectoryPool) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"pool_id"}),
        prefix="valid_trajectory_pool:",
    )


def _apply_profile_cap(
    trajectories: tuple[Trajectory, ...],
    reports: dict[str, TrajectoryValidityReport],
    max_per_profile: int | None,
) -> tuple[tuple[Trajectory, ...], tuple[str, ...]]:
    if max_per_profile is None:
        return trajectories, ()
    by_profile: dict[str, list[Trajectory]] = defaultdict(list)
    for item in trajectories:
        profile_id = reports[item.trajectory_id].attributes.profile.profile_id
        by_profile[profile_id].append(item)
    retained: list[Trajectory] = []
    pruned: list[str] = []
    for profile_id in sorted(by_profile):
        members = sorted(by_profile[profile_id], key=lambda item: item.trajectory_id)
        retained.extend(members[:max_per_profile])
        pruned.extend(item.trajectory_id for item in members[max_per_profile:])
    return (
        tuple(sorted(retained, key=lambda item: item.trajectory_id)),
        tuple(sorted(pruned)),
    )


def _entropy(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return -sum(
        (count / total) * math.log(count / total)
        for count in counts.values()
        if count
    )
