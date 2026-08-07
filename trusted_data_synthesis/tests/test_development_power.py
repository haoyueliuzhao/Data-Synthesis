from __future__ import annotations

from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.vtdo_experiment import phase1_development_power as v22


def test_mpe_is_centered_contrast_for_frozen_probability_shift() -> None:
    probabilities = {"state:a": 0.55, "state:b": 0.30, "state:c": 0.15}
    reachability = {"state:a": 0.80, "state:b": 0.65, "state:c": 0.50}

    contrast = v22.contribution_mpe_for_state(
        probabilities,
        selected_state_id="state:a",
        reachability=reachability,
    )
    selected_effect = contrast * (1.0 - probabilities["state:a"])
    other_effect = -contrast * probabilities["state:a"]
    contributions = {
        state_id: selected_effect if state_id == "state:a" else other_effect
        for state_id in probabilities
    }
    baseline = v22._next_probabilities(
        probabilities,
        {state_id: 0.0 for state_id in probabilities},
        reachability=reachability,
    )
    updated = v22._next_probabilities(
        probabilities,
        contributions,
        reachability=reachability,
    )

    assert sum(
        probabilities[state_id] * contributions[state_id]
        for state_id in probabilities
    ) == pytest.approx(0.0, abs=1e-12)
    assert contrast == pytest.approx(selected_effect - other_effect, abs=1e-12)
    assert abs(updated["state:a"] - baseline["state:a"]) == pytest.approx(
        v22.TARGET_PROBABILITY_SHIFT,
        abs=1e-12,
    )


def test_mpe_requires_complete_reachability_support() -> None:
    with pytest.raises(ValueError, match="reachability support differs"):
        v22.contribution_mpe_for_state(
            {"state:a": 0.5, "state:b": 0.5},
            selected_state_id="state:a",
            reachability={"state:a": 0.8},
        )


def test_standardized_power_grid_is_deterministic_and_sensitive() -> None:
    first = v22.standardized_power_grid(
        task_counts=(30, 100),
        effect_sizes=(0.3, 0.5),
        replicates=2_000,
        seed=17,
    )
    second = v22.standardized_power_grid(
        task_counts=(30, 100),
        effect_sizes=(0.3, 0.5),
        replicates=2_000,
        seed=17,
    )
    power = {
        (row["standardized_effect"], row["task_count"]): row["power"]
        for row in first
    }

    assert first == second
    assert power[(0.3, 100)] > power[(0.3, 30)]
    assert power[(0.5, 100)] > power[(0.3, 100)]


def test_micro_splits_are_exhaustive_disjoint_and_balanced(monkeypatch) -> None:
    task_types = tuple(
        v22.REQUIRED_TASK_TYPES[index % len(v22.REQUIRED_TASK_TYPES)]
        for index in range(v22.DEVELOPMENT_OBJECTIVE_RECORD_COUNT)
    )
    artifacts = tuple(
        SimpleNamespace(task_id=f"task:{index}", task_type=task_type)
        for index, task_type in enumerate(task_types)
    )
    records = tuple(
        SimpleNamespace(record_id=f"record:{index}")
        for index in range(v22.DEVELOPMENT_OBJECTIVE_RECORD_COUNT)
    )
    monkeypatch.setattr(v22, "_artifact_task_id", lambda value: value.task_id)
    monkeypatch.setattr(v22, "_artifact_task_type", lambda value: value.task_type)

    manifests = v22._micro_split_manifest(artifacts, records)
    observed_record_ids = {
        record_id for manifest in manifests for record_id in manifest["record_ids"]
    }

    assert len(manifests) == v22.OBJECTIVE_MICRO_SPLIT_COUNT
    assert all(
        len(manifest["record_ids"]) == v22.OBJECTIVE_RECORDS_PER_MICRO_SPLIT
        for manifest in manifests
    )
    assert observed_record_ids == {record.record_id for record in records}
    assert sum(len(manifest["record_ids"]) for manifest in manifests) == len(
        observed_record_ids
    )


def test_objective_selector_rejects_shared_evidence_and_signatures(monkeypatch) -> None:
    artifacts = tuple(SimpleNamespace(name=name) for name in ("a", "b", "c", "d"))
    signatures = {"a": "sig:a", "b": "sig:b", "c": "sig:c", "d": "sig:a"}
    evidence = {
        "a": frozenset({"evidence:1"}),
        "b": frozenset({"evidence:1", "evidence:2"}),
        "c": frozenset({"evidence:3"}),
        "d": frozenset({"evidence:4"}),
    }
    monkeypatch.setattr(
        v22,
        "_select_stratified_artifacts",
        lambda values, count, salt: values,
    )
    monkeypatch.setattr(v22, "_task_semantic_signature", lambda value: signatures[value.name])
    monkeypatch.setattr(v22, "_artifact_evidence_version_ids", lambda value: evidence[value.name])

    selected = v22._select_disjoint_objective_artifacts(
        artifacts,
        count=2,
        salt="test",
    )

    assert tuple(value.name for value in selected) == ("a", "c")
