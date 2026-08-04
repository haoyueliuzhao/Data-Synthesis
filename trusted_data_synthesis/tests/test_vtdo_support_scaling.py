from __future__ import annotations

import copy

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_support_scaling import (
    analyze_support_scaling,
)


def _state_rows(scale: float, *, reverse: bool = False) -> list[dict[str, object]]:
    rows = []
    for task_index in range(30):
        values = (-1.0, 0.2, 0.8)
        if reverse:
            values = tuple(reversed(values))
        for state_index, value in enumerate(values):
            rows.append(
                {
                    "task_id": f"task-{task_index}",
                    "task_type": "comparison" if task_index % 2 else "temporal",
                    "state_id": f"state-{state_index}",
                    "gp_c_proxy": scale * value,
                }
            )
    return rows


def test_support_scaling_selects_the_first_stable_production_size() -> None:
    report = analyze_support_scaling(
        gradient_vectors={
            4: (1.0, -1.0, 0.5, -0.5),
            8: (1.0, 1.0, 0.5, 0.5),
            16: (1.0, 1.9, 3.1, 4.0),
            32: (1.0, 2.0, 3.0, 4.0),
        },
        state_rows={
            4: _state_rows(1.0, reverse=True),
            8: _state_rows(1.0),
            16: _state_rows(0.98),
            32: _state_rows(1.0),
        },
        source_manifest_hashes={
            size: f"manifest:{size}" for size in (4, 8, 16, 32)
        },
    )

    assert report["status"] == "passed"
    assert report["selected_minimum_support_size"] == 16
    assert report["size_rows"][0]["passes_stability_gate"] is False
    assert report["size_rows"][2]["passes_stability_gate"] is True
    assert set(report["task_type_stratified_metrics"]) == {"comparison", "temporal"}


def test_support_scaling_rejects_population_drift() -> None:
    rows = {size: _state_rows(1.0) for size in (4, 8, 16, 32)}
    rows[16] = copy.deepcopy(rows[16][1:])

    with pytest.raises(ValueError, match="changes the task-state population"):
        analyze_support_scaling(
            gradient_vectors={size: (1.0, 2.0) for size in (4, 8, 16, 32)},
            state_rows=rows,
            source_manifest_hashes={
                size: f"manifest:{size}" for size in (4, 8, 16, 32)
            },
        )


def test_support_scaling_requires_the_frozen_size_grid() -> None:
    with pytest.raises(ValueError, match="4/8/16/32"):
        analyze_support_scaling(
            gradient_vectors={16: (1.0, 2.0), 32: (1.0, 2.0)},
            state_rows={16: _state_rows(1.0), 32: _state_rows(1.0)},
            source_manifest_hashes={16: "manifest:16", 32: "manifest:32"},
        )
