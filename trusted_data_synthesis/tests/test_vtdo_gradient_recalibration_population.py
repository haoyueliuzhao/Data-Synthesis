from __future__ import annotations

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_gradient_recalibration_population import (
    successor_partition_ids,
)


def _rows() -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "artifact_id": f"artifact:{family}:{index}",
            "task_id": f"task:{family}:{index}",
            "task_type": family,
        }
        for family in ("comparison", "temporal_growth")
        for index in range(5)
    )


def _predecessor(*, observed: bool = False) -> dict[str, object]:
    families = ("comparison", "temporal_growth")
    return {
        "status": "passed",
        "sealed_candidate_outcomes_observed": observed,
        "partitions": {
            "development": {
                "artifact_ids": tuple(f"artifact:{family}:0" for family in families)
            },
            "validation": {
                "artifact_ids": tuple(f"artifact:{family}:1" for family in families)
            },
            "sealed_candidate": {
                "artifact_ids": tuple(f"artifact:{family}:2" for family in families)
            },
        },
        "unused_artifact_ids": tuple(
            f"artifact:{family}:{index}"
            for family in families
            for index in (3, 4)
        ),
    }


def test_successor_uses_only_reserve_and_inherits_unopened_sealed() -> None:
    result = successor_partition_ids(
        _rows(),
        predecessor_report=_predecessor(),
        sampling_salt="fresh-v5",
    )

    assert result["sealed_candidate"] == (
        "artifact:comparison:2",
        "artifact:temporal_growth:2",
    )
    assert set(result["development"]) | set(result["validation"]) == {
        "artifact:comparison:3",
        "artifact:comparison:4",
        "artifact:temporal_growth:3",
        "artifact:temporal_growth:4",
    }
    assert set(result["development"]).isdisjoint(result["validation"] )
    assert set(result["development"]).isdisjoint(result["sealed_candidate"] )


def test_successor_rejects_observed_sealed_candidate() -> None:
    with pytest.raises(ValueError, match="already observed"):
        successor_partition_ids(
            _rows(),
            predecessor_report=_predecessor(observed=True),
            sampling_salt="fresh-v5",
        )
