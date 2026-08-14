from __future__ import annotations

import math

from trusted_synthesis.experiments.vtdo_experiment.phase1_stable_submechanism_geometry import (  # noqa: E501
    StableIdentifiableSubspacePolicy,
    StableTaskResponse,
    estimate_stable_subspace,
    principal_angles_degrees,
    symmetric_eigenpairs,
)


def _row(
    task_id: str,
    demand: tuple[float, ...],
    realizations: tuple[int, ...],
    parent: str,
) -> StableTaskResponse:
    return StableTaskResponse(
        task_id=task_id,
        submechanism_id=f"sub:{task_id}",
        parent_mechanism_id=parent,
        task_instance_id=f"instance:{task_id}",
        general_difficulty=0.5,
        demand=demand,
        realizations=realizations,
    )


def test_stable_subspace_does_not_let_a_weak_fifth_direction_poison_top_four() -> None:
    rows = []
    for axis in range(4):
        positive = tuple(float(index == axis) for index in range(7))
        negative = tuple(-value for value in positive)
        parent = f"parent:{axis}"
        rows.extend(
            (
                _row(f"strong:{axis}:positive", positive, (0, 1), parent),
                _row(f"strong:{axis}:negative", negative, (0, 1), parent),
            )
        )
    weak = tuple(float(index == 4) for index in range(7))
    weak_realizations = (1, *(0 for _ in range(999)))
    rows.extend(
        (
            _row("weak:positive", weak, weak_realizations, "parent:0"),
            _row("weak:negative", tuple(-value for value in weak), weak_realizations, "parent:1"),
        )
    )

    result = estimate_stable_subspace(rows, StableIdentifiableSubspacePolicy())

    assert result.numerical_rank == 5
    assert result.identifiable_rank == 4
    assert result.claimed_rank == 4
    assert result.claimed_effective_rank > 3.99
    assert result.claimed_condition_number < 1.01
    assert result.residual_eigenvalues[4] < result.identification_floor


def test_principal_angles_use_the_same_preregistered_rank() -> None:
    left = (
        (1.0, 0.0),
        (0.0, 1.0),
        (0.0, 0.0),
    )
    identical = principal_angles_degrees(left, left)
    orthogonal = principal_angles_degrees(
        left,
        (
            (1.0, 0.0),
            (0.0, 0.0),
            (0.0, 1.0),
        ),
    )

    assert identical == (0.0, 0.0)
    assert math.isclose(orthogonal[0], 0.0, abs_tol=1e-8)
    assert math.isclose(orthogonal[1], 90.0, abs_tol=1e-8)


def test_symmetric_eigenpairs_reconstruct_diagonal_spectrum() -> None:
    eigenvalues, eigenvectors = symmetric_eigenpairs(
        (
            (4.0, 0.0, 0.0),
            (0.0, 2.0, 0.0),
            (0.0, 0.0, 1.0),
        )
    )

    assert eigenvalues == (4.0, 2.0, 1.0)
    assert eigenvectors == (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )
