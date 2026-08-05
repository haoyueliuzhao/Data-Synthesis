from __future__ import annotations

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_gradient_calibration_population import (
    balanced_partition_ids,
)


def _rows(count_per_family: int = 3) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "artifact_id": f"artifact:{family}:{index}",
            "task_id": f"task:{family}:{index}",
            "task_type": family,
        }
        for family in ("comparison", "temporal_growth")
        for index in range(count_per_family)
    )


def test_balanced_calibration_population_freezes_each_family_in_each_partition() -> None:
    first = balanced_partition_ids(_rows(), sampling_salt="calibration-v1")
    second = balanced_partition_ids(_rows(), sampling_salt="calibration-v1")

    assert first == second
    assert set(first) == {"development", "validation", "sealed_candidate"}
    assert all(len(values) == 2 for values in first.values())
    selected = [artifact_id for values in first.values() for artifact_id in values]
    assert len(selected) == len(set(selected)) == 6
    for values in first.values():
        assert {artifact_id.split(":")[1] for artifact_id in values} == {
            "comparison",
            "temporal_growth",
        }


def test_balanced_calibration_population_rejects_insufficient_family_support() -> None:
    with pytest.raises(ValueError, match="are required"):
        balanced_partition_ids(
            _rows(count_per_family=2),
            sampling_salt="calibration-v1",
        )


def test_balanced_calibration_population_rejects_duplicate_task_identity() -> None:
    rows = list(_rows())
    rows[-1] = {**rows[-1], "task_id": rows[0]["task_id"]}

    with pytest.raises(ValueError, match="duplicate identities"):
        balanced_partition_ids(
            tuple(rows),
            sampling_salt="calibration-v1",
        )
