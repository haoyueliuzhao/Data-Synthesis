from __future__ import annotations

import math
from collections import Counter
from itertools import islice
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.core.trajectory.specification import TrajectoryVerificationContext
from trusted_synthesis.core.trajectory.state import (
    TrajectoryState,
    TrajectoryStateAssignment,
    map_trajectory_to_state,
)
from trusted_synthesis.core.trajectory.validity import (
    TrajectoryValidityEvaluator,
    TrajectoryValidityReport,
)
from trusted_synthesis.hashing import canonical_hash

from .catalog import TrajectoryStateCatalog
from .explorer import StateConditionedTrajectoryProviderProtocol
from .schema import (
    VTDO_SCHEMA_VERSION,
    ConditionalTrajectoryDistribution,
    VTDORoleContract,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StateConditionedTrainingArtifact(FrozenModel):
    """One released training trajectory carrying its task, Omega, and target state."""

    artifact_id: str = Field(min_length=1)
    context: TrajectoryVerificationContext
    target_state: TrajectoryState
    trajectory: Trajectory
    validity_report: TrajectoryValidityReport
    assignment: TrajectoryStateAssignment
    source_distribution_id: str = Field(min_length=1)
    role_contract_id: str = Field(min_length=1)
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_artifact(self) -> StateConditionedTrainingArtifact:
        if self.target_state.verification_context_id != self.context.context_id:
            raise ValueError("training target state belongs to another Omega context")
        if self.trajectory.task_id != self.context.task.task_id:
            raise ValueError("training trajectory belongs to another task")
        if not self.validity_report.valid:
            raise ValueError("training artifact cannot carry an invalid trajectory")
        if self.validity_report.trajectory_hash != self.trajectory.trajectory_hash:
            raise ValueError("training validity report has another trajectory hash")
        if self.assignment.trajectory_hash != self.trajectory.trajectory_hash:
            raise ValueError("training assignment has another trajectory hash")
        if self.assignment.state != self.target_state:
            raise ValueError("training trajectory missed its requested quotient state")
        if self.artifact_id != state_conditioned_training_artifact_id(self):
            raise ValueError("state-conditioned training artifact identity is invalid")
        return self


class TrajectoryStateMaterializationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    context_id: str = Field(min_length=1)
    state_catalog_id: str = Field(min_length=1)
    source_distribution_id: str = Field(min_length=1)
    role_contract_id: str = Field(min_length=1)
    seed: int
    maximum_attempt_multiplier: int = Field(ge=1)
    requested_state_counts: dict[str, int] = Field(min_length=1)
    attempted_trajectory_count: int = Field(ge=0)
    released_state_counts: dict[str, int] = Field(min_length=1)
    artifacts: tuple[StateConditionedTrainingArtifact, ...] = ()
    failure_counts: dict[str, int] = Field(default_factory=dict)
    status: Literal["passed", "blocked"]
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> TrajectoryStateMaterializationReport:
        if any(count < 0 for count in self.requested_state_counts.values()):
            raise ValueError("materialization request counts cannot be negative")
        if set(self.released_state_counts) != set(self.requested_state_counts):
            raise ValueError("materialization released counts have another support")
        observed = Counter(item.target_state.state_id for item in self.artifacts)
        if dict(sorted(observed.items())) != {
            state_id: count
            for state_id, count in sorted(self.released_state_counts.items())
            if count
        }:
            raise ValueError("materialization artifacts disagree with released counts")
        if any(item.context.context_id != self.context_id for item in self.artifacts):
            raise ValueError("materialization artifacts cross verification contexts")
        if any(
            item.source_distribution_id != self.source_distribution_id
            or item.role_contract_id != self.role_contract_id
            for item in self.artifacts
        ):
            raise ValueError("materialization artifacts cross frozen contracts")
        exact = self.released_state_counts == self.requested_state_counts
        expected_status: Literal["passed", "blocked"] = "passed" if exact else "blocked"
        if self.status != expected_status:
            raise ValueError("materialization status is inconsistent")
        if self.report_id != trajectory_state_materialization_report_id(self):
            raise ValueError("trajectory-state materialization report identity is invalid")
        return self


class ValidTrajectoryStateMaterializer:
    """Materialize pi_(t+1) as independently verified on-target trajectories."""

    def __init__(
        self,
        provider: StateConditionedTrajectoryProviderProtocol,
        evaluator: TrajectoryValidityEvaluator,
    ) -> None:
        self._provider = provider
        self._evaluator = evaluator

    def materialize(
        self,
        context: TrajectoryVerificationContext,
        state_catalog: TrajectoryStateCatalog,
        distribution: ConditionalTrajectoryDistribution,
        role_contract: VTDORoleContract,
        *,
        total_budget: int,
        seed: int,
        maximum_attempt_multiplier: int = 3,
    ) -> tuple[tuple[StateConditionedTrainingArtifact, ...], TrajectoryStateMaterializationReport]:
        if total_budget < 1:
            raise ValueError("trajectory-state materialization budget must be positive")
        if maximum_attempt_multiplier < 1:
            raise ValueError("materialization attempt multiplier must be positive")
        if self._provider.provider_id != role_contract.explorer_provider_id:
            raise ValueError("materialization provider violates the VTDO role contract")
        if state_catalog.verification_context_id != context.context_id:
            raise ValueError("materialization catalog belongs to another Omega context")
        if distribution.task_condition_id != state_catalog.task_condition_id:
            raise ValueError("materialization distribution crosses task conditions")
        if not set(distribution.probabilities) <= set(state_catalog.states):
            raise ValueError("materialization distribution contains an unknown state")

        requested = _allocate_distribution(distribution, total_budget)
        released: list[StateConditionedTrainingArtifact] = []
        released_counts = {state_id: 0 for state_id in requested}
        failures: Counter[str] = Counter()
        attempted = 0
        seen_trajectory_ids: set[str] = set()
        for state_id in sorted(requested):
            target_count = requested[state_id]
            if target_count == 0:
                continue
            target_state = state_catalog.states[state_id]
            attempt_budget = target_count * maximum_attempt_multiplier
            try:
                candidates = islice(
                    self._provider.generate(
                        context,
                        target_state,
                        candidate_count=attempt_budget,
                        seed=_state_seed(seed, state_id),
                    ),
                    attempt_budget,
                )
                for trajectory in candidates:
                    if released_counts[state_id] >= target_count:
                        break
                    attempted += 1
                    if trajectory.trajectory_id in seen_trajectory_ids:
                        failures["duplicate_trajectory"] += 1
                        continue
                    seen_trajectory_ids.add(trajectory.trajectory_id)
                    try:
                        report = self._evaluator.evaluate(context, trajectory)
                    except Exception:
                        failures["verification_error"] += 1
                        continue
                    if not report.valid:
                        failures["invalid_trajectory"] += 1
                        continue
                    try:
                        assignment = map_trajectory_to_state(
                            context,
                            trajectory,
                            task_condition_id=distribution.task_condition_id,
                            program_node_aliases=report.program_node_mapping,
                        )
                    except Exception:
                        failures["state_mapping_error"] += 1
                        continue
                    if assignment.state.state_id != state_id:
                        failures["off_target_state"] += 1
                        continue
                    values = {
                        "context": context,
                        "target_state": target_state,
                        "trajectory": trajectory,
                        "validity_report": report,
                        "assignment": assignment,
                        "source_distribution_id": distribution.distribution_id,
                        "role_contract_id": role_contract.contract_id,
                        "schema_version": VTDO_SCHEMA_VERSION,
                    }
                    provisional = StateConditionedTrainingArtifact.model_construct(
                        artifact_id="pending",
                        **values,
                    )
                    released.append(
                        StateConditionedTrainingArtifact(
                            artifact_id=state_conditioned_training_artifact_id(provisional),
                            **values,
                        )
                    )
                    released_counts[state_id] += 1
            except Exception:
                failures["provider_error"] += 1
            if released_counts[state_id] < target_count:
                failures["target_quota_unfilled"] += target_count - released_counts[state_id]

        status: Literal["passed", "blocked"] = (
            "passed" if released_counts == requested else "blocked"
        )
        report_values = {
            "provider_id": self._provider.provider_id,
            "provider_version": self._provider.provider_version,
            "context_id": context.context_id,
            "state_catalog_id": state_catalog.catalog_id,
            "source_distribution_id": distribution.distribution_id,
            "role_contract_id": role_contract.contract_id,
            "seed": seed,
            "maximum_attempt_multiplier": maximum_attempt_multiplier,
            "requested_state_counts": requested,
            "attempted_trajectory_count": attempted,
            "released_state_counts": released_counts,
            "artifacts": tuple(released),
            "failure_counts": dict(sorted(failures.items())),
            "status": status,
            "schema_version": VTDO_SCHEMA_VERSION,
        }
        provisional_report = TrajectoryStateMaterializationReport.model_construct(
            report_id="pending",
            **report_values,
        )
        report = TrajectoryStateMaterializationReport(
            report_id=trajectory_state_materialization_report_id(provisional_report),
            **report_values,
        )
        return tuple(released), report


def state_conditioned_training_artifact_id(
    value: StateConditionedTrainingArtifact,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"artifact_id"}),
        prefix="state_conditioned_training_artifact:",
    )


def trajectory_state_materialization_report_id(
    value: TrajectoryStateMaterializationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="trajectory_state_materialization_report:",
    )


def _allocate_distribution(
    distribution: ConditionalTrajectoryDistribution,
    total_budget: int,
) -> dict[str, int]:
    exact = {
        state_id: probability * total_budget
        for state_id, probability in distribution.probabilities.items()
    }
    counts = {state_id: math.floor(value) for state_id, value in exact.items()}
    remainder = total_budget - sum(counts.values())
    order = sorted(
        exact,
        key=lambda state_id: (-(exact[state_id] - counts[state_id]), state_id),
    )
    for state_id in order[:remainder]:
        counts[state_id] += 1
    return dict(sorted(counts.items()))


def _state_seed(seed: int, state_id: str) -> int:
    digest = canonical_hash(
        {"seed": seed, "state_id": state_id},
        prefix="trajectory_state_materialization_seed:",
    ).rsplit(":", 1)[-1]
    return int(digest[:16], 16)
