from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_information_geometry import (  # noqa: E501
    CONFIRMED_MECHANISM_IDS,
    MechanismGeometryThresholds,
    _GeometryRow,
    _implementation_manifest,
    _make_gates,
    _make_spectrum,
    _matrices,
    _validate_path_hash_fields,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
)


def _rows(vectors: tuple[tuple[float, ...], ...]) -> tuple[_GeometryRow, ...]:
    return tuple(
        _GeometryRow(
            task_id=f"task-{index}",
            group_id=f"group-{index}",
            mechanism_id=CONFIRMED_MECHANISM_IDS[index % len(CONFIRMED_MECHANISM_IDS)],
            probability=0.5,
            general_difficulty=0.0,
            demand=vector,
            realizations=(0, 1, 0, 1, 1),
        )
        for index, vector in enumerate(vectors)
    )


def test_mechanism_geometry_recovers_independent_capability_directions() -> None:
    vectors = tuple(
        tuple(float(row == column) for column in range(len(CAPABILITY_AXES)))
        for row in range(len(CAPABILITY_AXES))
    )
    spectrum = _make_spectrum(
        _rows(vectors),
        thresholds=MechanismGeometryThresholds(bootstrap_replicates=100),
        seed=17,
    )

    assert spectrum.raw_numerical_rank == len(CAPABILITY_AXES)
    assert abs(spectrum.raw_effective_rank - len(CAPABILITY_AXES)) < 1e-9
    assert abs(spectrum.raw_condition_number - 1.0) < 1e-9


def test_mechanism_geometry_rejects_a_low_rank_pseudo_distribution() -> None:
    vector = (1.0, *(0.0 for _ in CAPABILITY_AXES[1:]))
    rows = _rows(tuple(vector for _ in range(8)))
    thresholds = MechanismGeometryThresholds(
        expected_groups_per_mechanism=2,
        bootstrap_replicates=100,
    )
    spectrum = _make_spectrum(rows, thresholds=thresholds, seed=23)
    gates = {item.gate_id: item for item in _make_gates(spectrum, thresholds)}

    assert spectrum.raw_numerical_rank == 1
    assert abs(spectrum.raw_effective_rank - 1.0) < 1e-9
    assert gates["raw_numerical_rank"].passed is False
    assert gates["raw_effective_rank"].passed is False

def test_zero_information_task_does_not_change_residual_geometry() -> None:
    size = len(CAPABILITY_AXES)
    first = (1.0, 0.0, *(0.0 for _ in range(size - 2)))
    second = (0.0, 1.0, *(0.0 for _ in range(size - 2)))
    third = (2**-0.5, 2**-0.5, *(0.0 for _ in range(size - 2)))
    rows = (
        _GeometryRow(
            task_id="task-a",
            group_id="group-a",
            mechanism_id=CONFIRMED_MECHANISM_IDS[0],
            probability=0.5,
            general_difficulty=0.0,
            demand=first,
            realizations=(0, 1, 0, 1, 1),
        ),
        _GeometryRow(
            task_id="task-b",
            group_id="group-b",
            mechanism_id=CONFIRMED_MECHANISM_IDS[1],
            probability=0.5,
            general_difficulty=1.0,
            demand=second,
            realizations=(0, 1, 0, 1, 1),
        ),
        _GeometryRow(
            task_id="task-c",
            group_id="group-c",
            mechanism_id=CONFIRMED_MECHANISM_IDS[2],
            probability=0.5,
            general_difficulty=2.0,
            demand=third,
            realizations=(0, 1, 0, 1, 1),
        ),
    )
    zero_weight_outlier = _GeometryRow(
        task_id="task-zero",
        group_id="group-zero",
        mechanism_id=CONFIRMED_MECHANISM_IDS[3],
        probability=1.0,
        general_difficulty=10_000.0,
        demand=tuple(float(index == size - 1) for index in range(size)),
        realizations=(1, 1, 1, 1, 1),
    )

    _, base_residual, base_fraction = _matrices(rows)
    _, extended_residual, extended_fraction = _matrices((*rows, zero_weight_outlier))
    base_trace = sum(base_residual[index][index] for index in range(size))
    extended_trace = sum(extended_residual[index][index] for index in range(size))

    assert base_trace > 0
    assert extended_trace > 0
    for row in range(size):
        for column in range(size):
            assert (
                abs(
                    base_residual[row][column] / base_trace
                    - extended_residual[row][column] / extended_trace
                )
                < 1e-12
            )
    assert abs(base_fraction - extended_fraction) < 1e-12


def test_geometry_implementation_manifest_covers_numeric_and_source_contracts() -> None:
    manifest = _implementation_manifest()

    assert set(manifest) >= {
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_mechanism_information_geometry.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_mechanism_confirmation.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_mechanism_repair.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_sensitive_frontier.py",
    }
    assert all(len(value) == 64 for value in manifest.values())

def test_geometry_source_reference_hash_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n", encoding="utf-8")
    frozen = {
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }

    _validate_path_hash_fields(frozen, label="fixture")
    source.write_text("{\"changed\": true}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="changed after freeze"):
        _validate_path_hash_fields(frozen, label="fixture")
