from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_population_union import (
    _assert_union_identity_disjoint,
    _deduplicate_population_records,
)


def _artifact(
    task_id: str,
    artifact_id: str,
    *evidence_version_ids: str,
) -> Any:
    evidence = tuple(SimpleNamespace(evidence_version_id=value) for value in evidence_version_ids)
    return cast(
        Any,
        SimpleNamespace(
            artifact_id=artifact_id,
            omega=SimpleNamespace(
                task=SimpleNamespace(task_id=task_id),
                public_corpus=SimpleNamespace(evidence=evidence),
            ),
        ),
    )


def test_population_union_uses_source_priority_and_reports_drop_reasons() -> None:
    primary = (
        _artifact("task-a", "artifact-a", "ev-a"),
        _artifact("task-b", "artifact-b", "ev-b"),
    )
    supplemental = (
        _artifact("task-a", "artifact-c", "ev-c"),
        _artifact("task-c", "artifact-d", "ev-b"),
        _artifact("task-d", "artifact-e", "ev-d"),
    )

    retained, retained_by_source, dropped_by_source, dropped_by_reason = (
        _deduplicate_population_records((("1" * 64, primary), ("2" * 64, supplemental)))
    )

    assert [item.omega.task.task_id for item in retained] == [
        "task-a",
        "task-b",
        "task-d",
    ]
    assert retained_by_source == {"1" * 64: 2, "2" * 64: 1}
    assert dropped_by_source == {"1" * 64: 0, "2" * 64: 2}
    assert dropped_by_reason == {
        "duplicate_task_id": 1,
        "public_evidence_version_overlap": 1,
    }


def test_population_union_rejects_duplicate_versions_within_source_record() -> None:
    malformed = _artifact("task-a", "artifact-a", "ev-a", "ev-a")

    with pytest.raises(ValueError, match="duplicated Evidence Versions"):
        _deduplicate_population_records((("1" * 64, (malformed,)),))


def test_population_union_postcondition_is_fail_closed() -> None:
    records = (
        _artifact("task-a", "artifact-a", "ev-a"),
        _artifact("task-b", "artifact-b", "ev-a"),
    )

    with pytest.raises(ValueError, match="overlapping public Evidence Versions"):
        _assert_union_identity_disjoint(records)
