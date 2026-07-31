from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from itertools import islice
from typing import Literal, Protocol

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
from trusted_synthesis.core.vtdo.estimation import estimate_state_validity
from trusted_synthesis.core.vtdo.exploration import allocate_exploration_budget
from trusted_synthesis.core.vtdo.feasibility import (
    StateValidityPartition,
    make_state_validity_partition,
)
from trusted_synthesis.core.vtdo.schema import (
    VTDO_SCHEMA_VERSION,
    ExplorationDistribution,
    StateValidityEstimate,
    ValidityThresholds,
    VTDORoleContract,
)
from trusted_synthesis.hashing import canonical_hash


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StateConditionedTrajectoryProviderProtocol(Protocol):
    """Generate attempts for one requested quotient state under a frozen context."""

    provider_id: str
    provider_version: str

    def generate(
        self,
        context: TrajectoryVerificationContext,
        target_state: TrajectoryState,
        *,
        candidate_count: int,
        seed: int,
    ) -> Iterable[Trajectory]: ...


class TrajectoryExplorationObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    requested_state_id: str = Field(min_length=1)
    trajectory: Trajectory
    validity_report: TrajectoryValidityReport
    assignment: TrajectoryStateAssignment | None = None
    on_target: bool
    requested_state_importance_weight: float = Field(gt=0)
    mapping_error: str | None = None
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> TrajectoryExplorationObservation:
        if self.validity_report.trajectory_id != self.trajectory.trajectory_id:
            raise ValueError("exploration validity report belongs to another trajectory")
        if self.validity_report.trajectory_hash != self.trajectory.trajectory_hash:
            raise ValueError("exploration validity report has another trajectory hash")
        if self.assignment is None:
            if not self.mapping_error:
                raise ValueError("an unmapped exploration trajectory requires an error")
            if self.on_target:
                raise ValueError("an unmapped trajectory cannot be on target")
        else:
            if self.mapping_error is not None:
                raise ValueError("a mapped trajectory cannot retain a mapping error")
            if self.assignment.trajectory_id != self.trajectory.trajectory_id:
                raise ValueError("exploration assignment belongs to another trajectory")
            if self.on_target != (self.assignment.state.state_id == self.requested_state_id):
                raise ValueError("exploration target status is inconsistent")
        if self.observation_id != trajectory_exploration_observation_id(self):
            raise ValueError("trajectory exploration observation identity is invalid")
        return self


class StateConditionedExplorationBatch(FrozenModel):
    batch_id: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    context_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    exploration_distribution_id: str = Field(min_length=1)
    role_contract_id: str = Field(min_length=1)
    seed: int
    total_budget: int = Field(ge=1)
    requested_state_counts: dict[str, int] = Field(min_length=1)
    generated_candidate_count: int = Field(ge=0)
    evaluated_candidate_count: int = Field(ge=0)
    mapped_candidate_count: int = Field(ge=0)
    on_target_candidate_count: int = Field(ge=0)
    observed_state_counts: dict[str, int] = Field(default_factory=dict)
    observations: tuple[TrajectoryExplorationObservation, ...] = ()
    failures: tuple[str, ...] = ()
    status: Literal["passed", "partial", "blocked"]
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_batch(self) -> StateConditionedExplorationBatch:
        if sum(self.requested_state_counts.values()) != self.total_budget:
            raise ValueError("exploration requests do not preserve the total budget")
        if not (
            0
            <= self.mapped_candidate_count
            <= self.evaluated_candidate_count
            <= self.generated_candidate_count
            <= self.total_budget
        ):
            raise ValueError("exploration stage counts are not monotonic")
        if self.evaluated_candidate_count != len(self.observations):
            raise ValueError("exploration observation count is inconsistent")
        if any(item.validity_report.context_id != self.context_id for item in self.observations):
            raise ValueError("exploration observations were verified in another context")
        if any(
            item.assignment is not None
            and item.assignment.task_condition_id != self.task_condition_id
            for item in self.observations
        ):
            raise ValueError("exploration assignments cross task conditions")
        mapped = tuple(item for item in self.observations if item.assignment is not None)
        if self.mapped_candidate_count != len(mapped):
            raise ValueError("exploration mapped count is inconsistent")
        if self.on_target_candidate_count != sum(item.on_target for item in mapped):
            raise ValueError("exploration on-target count is inconsistent")
        observed = Counter(
            item.assignment.state.state_id for item in mapped if item.assignment is not None
        )
        if dict(sorted(observed.items())) != self.observed_state_counts:
            raise ValueError("exploration observed state counts are inconsistent")
        expected_status: Literal["passed", "partial", "blocked"]
        if (
            self.generated_candidate_count == self.total_budget
            and self.evaluated_candidate_count == self.generated_candidate_count
            and self.mapped_candidate_count == self.evaluated_candidate_count
            and not self.failures
        ):
            expected_status = "passed"
        elif self.mapped_candidate_count:
            expected_status = "partial"
        else:
            expected_status = "blocked"
        if self.status != expected_status:
            raise ValueError("exploration batch status is inconsistent")
        if self.batch_id != state_conditioned_exploration_batch_id(self):
            raise ValueError("state-conditioned exploration batch identity is invalid")
        return self


class StateConditionedTrajectoryExplorer:
    """Explore q_t and observe actual quotient states after independent verification."""

    def __init__(
        self,
        provider: StateConditionedTrajectoryProviderProtocol,
        evaluator: TrajectoryValidityEvaluator,
    ) -> None:
        self._provider = provider
        self._evaluator = evaluator

    def explore(
        self,
        context: TrajectoryVerificationContext,
        states: Mapping[str, TrajectoryState],
        exploration: ExplorationDistribution,
        role_contract: VTDORoleContract,
        *,
        total_budget: int,
        seed: int,
    ) -> StateConditionedExplorationBatch:
        if self._provider.provider_id != role_contract.explorer_provider_id:
            raise ValueError("Explorer provider disagrees with the VTDO role contract")
        if set(states) != set(exploration.probabilities):
            raise ValueError("Explorer state catalog differs from q_t support")
        if any(key != state.state_id for key, state in states.items()):
            raise ValueError("Explorer state catalog is stored under an invalid identity")
        if any(
            state.task_condition_id != exploration.task_condition_id for state in states.values()
        ):
            raise ValueError("Explorer state catalog crosses task conditions")
        if any(state.verification_context_id != context.context_id for state in states.values()):
            raise ValueError("Explorer state catalog belongs to another Omega context")

        requested = allocate_exploration_budget(exploration, total_budget)
        failures: list[str] = []
        observations: list[TrajectoryExplorationObservation] = []
        generated_count = 0
        seen_trajectory_ids: set[str] = set()
        for state_id in sorted(requested):
            count = requested[state_id]
            if count == 0:
                continue
            target = states[state_id]
            state_seed = _state_seed(seed, state_id)
            try:
                candidates = tuple(
                    islice(
                        self._provider.generate(
                            context,
                            target,
                            candidate_count=count,
                            seed=state_seed,
                        ),
                        count,
                    )
                )
            except Exception as exc:
                failures.append(f"provider:{state_id}:{type(exc).__name__}:{exc}")
                continue
            generated_count += len(candidates)
            if len(candidates) != count:
                failures.append(
                    f"provider_exhausted:{state_id}:requested={count}:generated={len(candidates)}"
                )
            for trajectory in candidates:
                if trajectory.trajectory_id in seen_trajectory_ids:
                    failures.append(f"duplicate_trajectory:{trajectory.trajectory_id}")
                    continue
                seen_trajectory_ids.add(trajectory.trajectory_id)
                try:
                    report = self._evaluator.evaluate(context, trajectory)
                except Exception as exc:
                    failures.append(
                        f"evaluation:{trajectory.trajectory_id}:{type(exc).__name__}:{exc}"
                    )
                    continue
                assignment = None
                mapping_error = None
                try:
                    assignment = map_trajectory_to_state(
                        context,
                        trajectory,
                        task_condition_id=exploration.task_condition_id,
                        program_node_aliases=report.program_node_mapping,
                    )
                except Exception as exc:
                    mapping_error = f"{type(exc).__name__}:{exc}"
                    failures.append(f"state_mapping:{trajectory.trajectory_id}:{mapping_error}")
                observation_values = {
                    "requested_state_id": state_id,
                    "trajectory": trajectory,
                    "validity_report": report,
                    "assignment": assignment,
                    "on_target": bool(
                        assignment is not None and assignment.state.state_id == state_id
                    ),
                    "requested_state_importance_weight": (exploration.importance_weights[state_id]),
                    "mapping_error": mapping_error,
                    "schema_version": VTDO_SCHEMA_VERSION,
                }
                provisional = TrajectoryExplorationObservation.model_construct(
                    observation_id="pending",
                    **observation_values,
                )
                observations.append(
                    TrajectoryExplorationObservation(
                        observation_id=trajectory_exploration_observation_id(provisional),
                        **observation_values,
                    )
                )

        mapped = tuple(item for item in observations if item.assignment is not None)
        observed = Counter(
            item.assignment.state.state_id for item in mapped if item.assignment is not None
        )
        if (
            generated_count == total_budget
            and len(observations) == generated_count
            and len(mapped) == len(observations)
            and not failures
        ):
            status: Literal["passed", "partial", "blocked"] = "passed"
        elif mapped:
            status = "partial"
        else:
            status = "blocked"
        batch_values = {
            "provider_id": self._provider.provider_id,
            "provider_version": self._provider.provider_version,
            "context_id": context.context_id,
            "task_condition_id": exploration.task_condition_id,
            "exploration_distribution_id": exploration.exploration_id,
            "role_contract_id": role_contract.contract_id,
            "seed": seed,
            "total_budget": total_budget,
            "requested_state_counts": dict(sorted(requested.items())),
            "generated_candidate_count": generated_count,
            "evaluated_candidate_count": len(observations),
            "mapped_candidate_count": len(mapped),
            "on_target_candidate_count": sum(item.on_target for item in mapped),
            "observed_state_counts": dict(sorted(observed.items())),
            "observations": tuple(observations),
            "failures": tuple(failures),
            "status": status,
            "schema_version": VTDO_SCHEMA_VERSION,
        }
        provisional = StateConditionedExplorationBatch.model_construct(
            batch_id="pending",
            **batch_values,
        )
        return StateConditionedExplorationBatch(
            batch_id=state_conditioned_exploration_batch_id(provisional),
            **batch_values,
        )


def estimate_exploration_state_validity(
    batch: StateConditionedExplorationBatch,
    *,
    thresholds: ValidityThresholds,
    prior_success: float = 0.0,
    prior_failure: float = 0.0,
) -> tuple[tuple[StateValidityEstimate, ...], StateValidityPartition]:
    """Aggregate validity by realized phi_x state, never by requested target."""

    grouped: dict[str, list[TrajectoryExplorationObservation]] = defaultdict(list)
    for observation in batch.observations:
        if observation.assignment is not None:
            grouped[observation.assignment.state.state_id].append(observation)
    if not grouped:
        raise ValueError("exploration batch has no mapped state for validity estimation")
    estimates = tuple(
        estimate_state_validity(
            tuple(item.assignment for item in observations if item.assignment is not None),
            tuple(item.validity_report for item in observations),
            thresholds=thresholds,
            prior_success=prior_success,
            prior_failure=prior_failure,
        )
        for _, observations in sorted(grouped.items())
    )
    return estimates, make_state_validity_partition(estimates)


def trajectory_exploration_observation_id(
    value: TrajectoryExplorationObservation,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"observation_id"}),
        prefix="trajectory_exploration_observation:",
    )


def state_conditioned_exploration_batch_id(
    value: StateConditionedExplorationBatch,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"batch_id"}),
        prefix="state_conditioned_exploration_batch:",
    )


def _state_seed(seed: int, state_id: str) -> int:
    digest = canonical_hash(
        {"seed": seed, "state_id": state_id},
        prefix="trajectory_state_exploration_seed:",
    ).rsplit(":", 1)[-1]
    return int(digest[:16], 16)
