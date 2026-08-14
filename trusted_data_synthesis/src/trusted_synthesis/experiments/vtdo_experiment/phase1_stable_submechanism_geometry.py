from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from statistics import fmean
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_information_geometry import (  # noqa: E501
    _GeometryRow,
    _matrices,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (  # noqa: E501
    CAPABILITY_AXES,
)

STABLE_SUBSPACE_POLICY_VERSION = "finance_stable_identifiable_subspace_policy.v1"
STABLE_SUBSPACE_ESTIMATE_VERSION = "finance_stable_subspace_estimate.v1"
STABLE_BOOTSTRAP_VERSION = "finance_stable_subspace_bootstrap.v1"
STABLE_ALIGNMENT_VERSION = "finance_stable_subspace_alignment.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StableIdentifiableSubspacePolicy(FrozenModel):
    """Preregistered support gate defined on one common Top-r subspace."""

    required_rank: Literal[4] = 4
    absolute_eigenvalue_floor: float = Field(default=1e-4, gt=0)
    relative_trace_floor: float = Field(default=0.01, gt=0, lt=1)
    minimum_effective_rank: float = Field(default=3.0, ge=1, le=4)
    maximum_condition_number: float = Field(default=100.0, gt=1)
    bootstrap_replicates: int = Field(default=2_000, ge=100)
    bootstrap_seed: int = 20260814
    minimum_bootstrap_geometry_pass_rate: float = Field(default=0.80, ge=0, le=1)
    maximum_principal_angle_degrees: float = Field(default=45.0, gt=0, le=90)
    minimum_bootstrap_alignment_rate: float = Field(default=0.80, ge=0, le=1)
    minimum_parent_information_share: float = Field(default=0.05, ge=0, le=1)
    maximum_parent_information_share: float = Field(default=0.60, gt=0, le=1)
    minimum_parent_share_bootstrap_lcb: float = Field(default=0.01, ge=0, le=1)
    minimum_nonzero_tasks_per_parent: int = Field(default=2, ge=1)
    boundary_probability_lower: float = Field(default=0.10, ge=0, le=1)
    boundary_probability_upper: float = Field(default=0.90, ge=0, le=1)
    minimum_boundary_task_fraction: float = Field(default=0.25, ge=0, le=1)
    minimum_nonzero_weight_task_count: int = Field(default=12, ge=1)
    minimum_marginal_axis_information: float = Field(default=1e-4, gt=0)
    minimum_informative_axis_count: int = Field(default=4, ge=1)
    maximum_general_factor_fraction: float = Field(default=0.85, ge=0, le=1)
    minimum_api_transport_rate: float = Field(default=0.98, ge=0, le=1)
    minimum_bounded_json_rate: float = Field(default=0.95, ge=0, le=1)
    minimum_observation_replay_rate: float = Field(default=0.98, ge=0, le=1)
    minimum_authority_integrity_rate: float = Field(default=0.98, ge=0, le=1)
    maximum_runtime_pathology_rate: float = Field(default=0.02, ge=0, le=1)
    schema_version: str = STABLE_SUBSPACE_POLICY_VERSION

    @model_validator(mode="after")
    def validate_policy(self) -> StableIdentifiableSubspacePolicy:
        if self.boundary_probability_lower >= self.boundary_probability_upper:
            raise ValueError("stable-subspace boundary interval is empty")
        if self.minimum_parent_information_share * 4 > 1:
            raise ValueError("stable-subspace parent minimum shares are infeasible")
        if self.minimum_parent_share_bootstrap_lcb > self.minimum_parent_information_share:
            raise ValueError("parent bootstrap lower bound exceeds the point threshold")
        if self.minimum_informative_axis_count > len(CAPABILITY_AXES):
            raise ValueError("stable-subspace policy requires too many axes")
        return self


class StableTaskResponse(FrozenModel):
    task_id: str = Field(min_length=1)
    submechanism_id: str = Field(min_length=1)
    parent_mechanism_id: str = Field(min_length=1)
    task_instance_id: str = Field(min_length=1)
    general_difficulty: float
    demand: tuple[float, ...]
    realizations: tuple[int, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_response(self) -> StableTaskResponse:
        if len(self.demand) != len(CAPABILITY_AXES):
            raise ValueError("stable response demand has the wrong dimension")
        if any(value not in {0, 1} for value in self.realizations):
            raise ValueError("stable response realizations must be binary")
        return self

    @property
    def probability(self) -> float:
        return sum(self.realizations) / len(self.realizations)


class StableSubspaceEstimate(FrozenModel):
    task_count: int = Field(ge=0)
    rollout_count: int = Field(ge=0)
    response_rate: float = Field(ge=0, le=1)
    boundary_task_fraction: float = Field(ge=0, le=1)
    nonzero_weight_task_count: int = Field(ge=0)
    residual_matrix: tuple[tuple[float, ...], ...]
    residual_eigenvalues: tuple[float, ...]
    numerical_rank: int = Field(ge=0)
    identification_floor: float = Field(gt=0)
    identifiable_rank: int = Field(ge=0)
    claimed_rank: int = Field(ge=0)
    claimed_eigenvalues: tuple[float, ...]
    claimed_effective_rank: float = Field(ge=0)
    claimed_condition_number: float = Field(ge=1)
    claimed_basis: tuple[tuple[float, ...], ...]
    general_factor_fraction: float = Field(ge=0, le=1)
    marginal_axis_information: dict[str, float]
    informative_axis_count: int = Field(ge=0)
    parent_information_share: dict[str, float]
    minimum_parent_information_share: float = Field(ge=0, le=1)
    maximum_parent_information_share: float = Field(ge=0, le=1)
    nonzero_task_count_by_parent: dict[str, int]
    schema_version: str = STABLE_SUBSPACE_ESTIMATE_VERSION

    @model_validator(mode="after")
    def validate_estimate(self) -> StableSubspaceEstimate:
        size = len(CAPABILITY_AXES)
        if len(self.residual_matrix) != size or any(
            len(row) != size for row in self.residual_matrix
        ):
            raise ValueError("stable residual matrix has the wrong shape")
        if len(self.residual_eigenvalues) != size:
            raise ValueError("stable residual spectrum has the wrong shape")
        if len(self.claimed_eigenvalues) != self.claimed_rank:
            raise ValueError("stable claimed spectrum has the wrong rank")
        if len(self.claimed_basis) != size or any(
            len(row) != self.claimed_rank for row in self.claimed_basis
        ):
            raise ValueError("stable claimed basis has the wrong shape")
        if set(self.marginal_axis_information) != set(CAPABILITY_AXES):
            raise ValueError("stable marginal information is incomplete")
        observed_min = min(self.parent_information_share.values(), default=0.0)
        observed_max = max(self.parent_information_share.values(), default=0.0)
        if not math.isclose(self.minimum_parent_information_share, observed_min, abs_tol=1e-12):
            raise ValueError("stable minimum parent share is inconsistent")
        if not math.isclose(self.maximum_parent_information_share, observed_max, abs_tol=1e-12):
            raise ValueError("stable maximum parent share is inconsistent")
        return self


class StableBootstrapSummary(FrozenModel):
    replicate_count: int = Field(ge=1)
    rank_pass_rate: float = Field(ge=0, le=1)
    effective_rank_pass_rate: float = Field(ge=0, le=1)
    condition_pass_rate: float = Field(ge=0, le=1)
    joint_geometry_pass_rate: float = Field(ge=0, le=1)
    identifiable_rank_interval95: tuple[float, float]
    effective_rank_interval95: tuple[float, float]
    condition_interval95: tuple[float, float]
    parent_share_interval95: dict[str, tuple[float, float]]
    minimum_parent_share_lcb: float = Field(ge=0, le=1)
    schema_version: str = STABLE_BOOTSTRAP_VERSION


class StableSubspaceAlignment(FrozenModel):
    rank: int = Field(ge=1)
    principal_angles_degrees: tuple[float, ...]
    maximum_principal_angle_degrees: float = Field(ge=0, le=90)
    bootstrap_replicates: int = Field(ge=1)
    bootstrap_alignment_pass_rate: float = Field(ge=0, le=1)
    maximum_angle_interval95: tuple[float, float]
    schema_version: str = STABLE_ALIGNMENT_VERSION

    @model_validator(mode="after")
    def validate_alignment(self) -> StableSubspaceAlignment:
        if len(self.principal_angles_degrees) != self.rank:
            raise ValueError("stable principal-angle vector has the wrong rank")
        if not math.isclose(
            self.maximum_principal_angle_degrees,
            max(self.principal_angles_degrees),
            abs_tol=1e-10,
        ):
            raise ValueError("stable maximum principal angle is inconsistent")
        return self


def estimate_stable_subspace(
    rows: Sequence[StableTaskResponse],
    policy: StableIdentifiableSubspacePolicy,
) -> StableSubspaceEstimate:
    matrix_rows = tuple(_matrix_row(item) for item in rows)
    if matrix_rows:
        raw, residual, general_fraction = _matrices(matrix_rows)
    else:
        size = len(CAPABILITY_AXES)
        raw = residual = tuple(tuple(0.0 for _ in range(size)) for _ in range(size))
        general_fraction = 1.0
    eigenvalues, eigenvectors = symmetric_eigenpairs(residual)
    positive = tuple(value for value in eigenvalues if value > _numerical_floor(eigenvalues))
    trace = sum(max(0.0, value) for value in eigenvalues)
    identification_floor = max(
        policy.absolute_eigenvalue_floor,
        policy.relative_trace_floor * trace,
    )
    identifiable = tuple(value for value in eigenvalues if value >= identification_floor)
    claimed_rank = min(policy.required_rank, len(eigenvalues))
    claimed = tuple(eigenvalues[:claimed_rank])
    claimed_basis = tuple(
        tuple(row[index] for index in range(claimed_rank)) for row in eigenvectors
    )
    weights = tuple(item.probability * (1.0 - item.probability) for item in rows)
    total_weight = sum(weights)
    parents = tuple(sorted({item.parent_mechanism_id for item in rows}))
    parent_shares = {
        parent: (
            sum(
                weight
                for item, weight in zip(rows, weights, strict=True)
                if item.parent_mechanism_id == parent
            )
            / total_weight
            if total_weight
            else 0.0
        )
        for parent in parents
    }
    nonzero_by_parent = {
        parent: sum(
            weight > 0
            for item, weight in zip(rows, weights, strict=True)
            if item.parent_mechanism_id == parent
        )
        for parent in parents
    }
    probabilities = tuple(item.probability for item in rows)
    boundary = (
        sum(
            policy.boundary_probability_lower <= value <= policy.boundary_probability_upper
            for value in probabilities
        )
        / len(probabilities)
        if probabilities
        else 0.0
    )
    marginal = {axis: raw[index][index] for index, axis in enumerate(CAPABILITY_AXES)}
    return StableSubspaceEstimate(
        task_count=len(rows),
        rollout_count=sum(len(item.realizations) for item in rows),
        response_rate=fmean(probabilities) if probabilities else 0.0,
        boundary_task_fraction=boundary,
        nonzero_weight_task_count=sum(value > 0 for value in weights),
        residual_matrix=residual,
        residual_eigenvalues=eigenvalues,
        numerical_rank=len(positive),
        identification_floor=identification_floor,
        identifiable_rank=len(identifiable),
        claimed_rank=claimed_rank,
        claimed_eigenvalues=claimed,
        claimed_effective_rank=_effective_rank(claimed),
        claimed_condition_number=_condition_number(claimed),
        claimed_basis=claimed_basis,
        general_factor_fraction=general_fraction,
        marginal_axis_information=marginal,
        informative_axis_count=sum(
            value >= policy.minimum_marginal_axis_information for value in marginal.values()
        ),
        parent_information_share=parent_shares,
        minimum_parent_information_share=min(parent_shares.values(), default=0.0),
        maximum_parent_information_share=max(parent_shares.values(), default=0.0),
        nonzero_task_count_by_parent=nonzero_by_parent,
    )


def bootstrap_stable_subspace(
    rows: Sequence[StableTaskResponse],
    policy: StableIdentifiableSubspacePolicy,
    *,
    seed_offset: int = 0,
) -> StableBootstrapSummary:
    rng = random.Random(policy.bootstrap_seed + seed_offset)
    ranks: list[float] = []
    effective: list[float] = []
    conditions: list[float] = []
    joint: list[bool] = []
    parent_samples: dict[str, list[float]] = {
        parent: [] for parent in sorted({item.parent_mechanism_id for item in rows})
    }
    for replicate in range(policy.bootstrap_replicates):
        estimate = estimate_stable_subspace(
            hierarchical_bootstrap(rows, rng, replicate=replicate),
            policy,
        )
        rank_pass = estimate.identifiable_rank >= policy.required_rank
        effective_pass = estimate.claimed_effective_rank >= policy.minimum_effective_rank
        condition_pass = estimate.claimed_condition_number <= policy.maximum_condition_number
        ranks.append(float(estimate.identifiable_rank))
        effective.append(estimate.claimed_effective_rank)
        conditions.append(estimate.claimed_condition_number)
        joint.append(rank_pass and effective_pass and condition_pass)
        for parent in parent_samples:
            parent_samples[parent].append(estimate.parent_information_share.get(parent, 0.0))
    intervals = {parent: _interval95(values) for parent, values in parent_samples.items()}
    return StableBootstrapSummary(
        replicate_count=policy.bootstrap_replicates,
        rank_pass_rate=sum(value >= policy.required_rank for value in ranks) / len(ranks),
        effective_rank_pass_rate=(
            sum(value >= policy.minimum_effective_rank for value in effective) / len(effective)
        ),
        condition_pass_rate=(
            sum(value <= policy.maximum_condition_number for value in conditions) / len(conditions)
        ),
        joint_geometry_pass_rate=sum(joint) / len(joint),
        identifiable_rank_interval95=_interval95(ranks),
        effective_rank_interval95=_interval95(effective),
        condition_interval95=_interval95(conditions),
        parent_share_interval95=intervals,
        minimum_parent_share_lcb=min((value[0] for value in intervals.values()), default=0.0),
    )


def compare_stable_subspaces(
    development_rows: Sequence[StableTaskResponse],
    confirmation_rows: Sequence[StableTaskResponse],
    policy: StableIdentifiableSubspacePolicy,
) -> StableSubspaceAlignment:
    development = estimate_stable_subspace(development_rows, policy)
    confirmation = estimate_stable_subspace(confirmation_rows, policy)
    point_angles = principal_angles_degrees(
        development.claimed_basis,
        confirmation.claimed_basis,
    )
    rng = random.Random(policy.bootstrap_seed + 20_000)
    maximum_angles: list[float] = []
    for replicate in range(policy.bootstrap_replicates):
        left = estimate_stable_subspace(
            hierarchical_bootstrap(development_rows, rng, replicate=replicate),
            policy,
        )
        right = estimate_stable_subspace(
            hierarchical_bootstrap(
                confirmation_rows,
                rng,
                replicate=replicate + 10_000,
            ),
            policy,
        )
        maximum_angles.append(
            max(principal_angles_degrees(left.claimed_basis, right.claimed_basis))
        )
    return StableSubspaceAlignment(
        rank=policy.required_rank,
        principal_angles_degrees=point_angles,
        maximum_principal_angle_degrees=max(point_angles),
        bootstrap_replicates=policy.bootstrap_replicates,
        bootstrap_alignment_pass_rate=(
            sum(value <= policy.maximum_principal_angle_degrees for value in maximum_angles)
            / len(maximum_angles)
        ),
        maximum_angle_interval95=_interval95(maximum_angles),
    )


def hierarchical_bootstrap(
    rows: Sequence[StableTaskResponse],
    rng: random.Random,
    *,
    replicate: int,
) -> tuple[StableTaskResponse, ...]:
    """Resample task instances within submechanism, then realizations within task."""

    grouped: dict[str, list[StableTaskResponse]] = defaultdict(list)
    for item in rows:
        grouped[item.submechanism_id].append(item)
    sampled: list[StableTaskResponse] = []
    for submechanism_id, values in sorted(grouped.items()):
        for index in range(len(values)):
            source = rng.choice(values)
            realizations = tuple(
                rng.choice(source.realizations) for _ in range(len(source.realizations))
            )
            sampled.append(
                source.model_copy(
                    update={
                        "task_id": f"bootstrap:{replicate}:{submechanism_id}:{index}",
                        "task_instance_id": (
                            f"bootstrap:{replicate}:{source.task_instance_id}:{index}"
                        ),
                        "realizations": realizations,
                    }
                )
            )
    return tuple(sampled)


def principal_angles_degrees(
    left_basis: Sequence[Sequence[float]],
    right_basis: Sequence[Sequence[float]],
) -> tuple[float, ...]:
    if not left_basis or len(left_basis) != len(right_basis):
        raise ValueError("principal-angle bases have incompatible shapes")
    rank = len(left_basis[0])
    if rank < 1 or any(len(row) != rank for row in (*left_basis, *right_basis)):
        raise ValueError("principal-angle bases have incompatible ranks")
    cross = [
        [
            sum(left_basis[row][left] * right_basis[row][right] for row in range(len(left_basis)))
            for right in range(rank)
        ]
        for left in range(rank)
    ]
    gram = [
        [sum(cross[row][left] * cross[row][right] for row in range(rank)) for right in range(rank)]
        for left in range(rank)
    ]
    singular_squared, _ = symmetric_eigenpairs(gram)
    singular = [math.sqrt(min(1.0, max(0.0, value))) for value in singular_squared[:rank]]
    return tuple(sorted(math.degrees(math.acos(value)) for value in singular))


def symmetric_eigenpairs(
    matrix: Sequence[Sequence[float]],
) -> tuple[tuple[float, ...], tuple[tuple[float, ...], ...]]:
    """Deterministic Jacobi eigendecomposition for the small symmetric matrices used here."""

    size = len(matrix)
    if size < 1 or any(len(row) != size for row in matrix):
        raise ValueError("symmetric eigendecomposition requires a square matrix")
    values = [list(map(float, row)) for row in matrix]
    vectors = [[float(row == column) for column in range(size)] for row in range(size)]
    for _ in range(max(64, 64 * size * size)):
        magnitude, left, right = max(
            (
                (abs(values[row][column]), row, column)
                for row in range(size)
                for column in range(row + 1, size)
            ),
            default=(0.0, 0, 0),
        )
        if magnitude <= 1e-14:
            break
        cross = values[left][right]
        tau = (values[right][right] - values[left][left]) / (2.0 * cross)
        tangent = (
            1.0 / (tau + math.sqrt(1.0 + tau * tau))
            if tau >= 0
            else -1.0 / (-tau + math.sqrt(1.0 + tau * tau))
        )
        cosine = 1.0 / math.sqrt(1.0 + tangent * tangent)
        sine = tangent * cosine
        left_diagonal = values[left][left]
        right_diagonal = values[right][right]
        for index in range(size):
            if index in {left, right}:
                continue
            old_left = values[index][left]
            old_right = values[index][right]
            new_left = cosine * old_left - sine * old_right
            new_right = sine * old_left + cosine * old_right
            values[index][left] = values[left][index] = new_left
            values[index][right] = values[right][index] = new_right
        values[left][left] = (
            cosine * cosine * left_diagonal
            - 2.0 * sine * cosine * cross
            + sine * sine * right_diagonal
        )
        values[right][right] = (
            sine * sine * left_diagonal
            + 2.0 * sine * cosine * cross
            + cosine * cosine * right_diagonal
        )
        values[left][right] = values[right][left] = 0.0
        for index in range(size):
            old_left = vectors[index][left]
            old_right = vectors[index][right]
            vectors[index][left] = cosine * old_left - sine * old_right
            vectors[index][right] = sine * old_left + cosine * old_right
    ordered = sorted(range(size), key=lambda index: values[index][index], reverse=True)
    eigenvalues = tuple(
        0.0 if abs(values[index][index]) <= 1e-15 else max(0.0, values[index][index])
        for index in ordered
    )
    eigenvectors = tuple(tuple(vectors[row][index] for index in ordered) for row in range(size))
    return eigenvalues, eigenvectors


def _matrix_row(item: StableTaskResponse) -> _GeometryRow:
    return _GeometryRow(
        task_id=item.task_id,
        group_id=item.task_instance_id,
        mechanism_id=item.parent_mechanism_id,
        probability=item.probability,
        general_difficulty=item.general_difficulty,
        demand=item.demand,
        realizations=item.realizations,
    )


def _effective_rank(values: Sequence[float]) -> float:
    total = sum(values)
    if total <= 0:
        return 0.0
    probabilities = tuple(value / total for value in values)
    return math.exp(-sum(value * math.log(value) for value in probabilities if value > 0))


def _condition_number(values: Sequence[float]) -> float:
    if not values or values[-1] <= 0:
        return 1e12
    return values[0] / values[-1]


def _numerical_floor(values: Sequence[float]) -> float:
    return max(1e-12, max(values, default=0.0) * 1e-6)


def _interval95(values: Sequence[float]) -> tuple[float, float]:
    if not values:
        raise ValueError("confidence interval support is empty")
    ordered = sorted(values)
    return (_quantile(ordered, 0.025), _quantile(ordered, 0.975))


def _quantile(values: Sequence[float], probability: float) -> float:
    if len(values) == 1:
        return float(values[0])
    position = probability * (len(values) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    fraction = position - lower
    return float(values[lower] * (1.0 - fraction) + values[upper] * fraction)


def parent_gate_values(
    estimate: StableSubspaceEstimate,
    bootstrap: StableBootstrapSummary,
) -> Mapping[str, float]:
    """Expose parent diagnostics under stable names for reports and tests."""

    return {
        "minimum_parent_information_share": estimate.minimum_parent_information_share,
        "maximum_parent_information_share": estimate.maximum_parent_information_share,
        "minimum_parent_share_bootstrap_lcb": bootstrap.minimum_parent_share_lcb,
        "minimum_nonzero_tasks_per_parent": float(
            min(estimate.nonzero_task_count_by_parent.values(), default=0)
        ),
    }
