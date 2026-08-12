from __future__ import annotations

from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    CAPABILITY_SENSITIVE_FAMILIES,
    FAMILY_PRIMARY_CAPABILITY,
    STRICT_MONOTONIC_DIMENSIONS,
    TIER_TASKS_PER_FAMILY,
    CapabilityDemandVector,
    capability_demand_vector_hash,
    make_capability_information_audit,
    make_capability_sensitive_frontier_audit,
)


def _demand(values: dict[str, float]) -> CapabilityDemandVector:
    provisional = CapabilityDemandVector.model_construct(
        values=values,
        vector_hash="pending",
    )
    return CapabilityDemandVector(
        values=values,
        vector_hash=capability_demand_vector_hash(provisional),
    )


def _axis_demand(axis: str) -> CapabilityDemandVector:
    values = {name: 0.1 for name in CAPABILITY_AXES}
    values[axis] = 5.0
    return _demand(values)


def _information_tasks(*, swap_labels: bool = False) -> tuple[SimpleNamespace, ...]:
    families = list(CAPABILITY_SENSITIVE_FAMILIES)
    labels = families[1:] + families[:1] if swap_labels else families
    return tuple(
        SimpleNamespace(
            family=label,
            capability_demand=_axis_demand(FAMILY_PRIMARY_CAPABILITY[family]),
        )
        for family, label in zip(families, labels, strict=True)
        for _ in range(3)
    )


def test_capability_information_accepts_seven_structurally_distinct_directions() -> None:
    audit = make_capability_information_audit(_information_tasks())

    assert audit.numerical_rank == len(CAPABILITY_AXES) - 1
    assert audit.identifiable_subspace_effective_rank >= 5.9
    assert audit.identifiable_subspace_condition_number <= 1.01
    assert audit.primary_axis_alignment_ready is True
    assert audit.capability_direction_ready is True


def test_capability_information_rejects_surface_balanced_low_rank_pseudo_distribution() -> None:
    shared = _demand({axis: 1.0 for axis in CAPABILITY_AXES})
    tasks = tuple(
        SimpleNamespace(family=family, capability_demand=shared)
        for family in CAPABILITY_SENSITIVE_FAMILIES
        for _ in range(3)
    )

    audit = make_capability_information_audit(tasks)

    assert audit.numerical_rank == 0
    assert audit.identifiable_subspace_effective_rank == 0
    assert audit.full_condition_number == 1e12
    assert audit.primary_axis_alignment_ready is False
    assert audit.capability_direction_ready is False


def test_family_labels_cannot_manufacture_capability_direction_coverage() -> None:
    aligned = make_capability_information_audit(_information_tasks())
    relabeled = make_capability_information_audit(_information_tasks(swap_labels=True))

    assert relabeled.information_eigenvalues == aligned.information_eigenvalues
    assert relabeled.primary_axis_alignment_ready is False
    assert relabeled.capability_direction_ready is False


def test_capability_information_requires_complete_frozen_family_support() -> None:
    incomplete = tuple(
        task for task in _information_tasks() if task.family != CAPABILITY_SENSITIVE_FAMILIES[-1]
    )

    with pytest.raises(ValueError, match="complete frozen family set"):
        make_capability_information_audit(incomplete)


def _frontier_tasks(
    *,
    flatten_dimension: str | None = None,
    flatten_family: str | None = None,
) -> tuple[SimpleNamespace, ...]:
    tasks = []
    tier_value = {
        DifficultyTier.EASY_CONTROL: 1,
        DifficultyTier.FRONTIER: 3,
        DifficultyTier.HARD_CONTROL: 5,
    }
    semantic_score = {
        DifficultyTier.EASY_CONTROL: 2.0,
        DifficultyTier.FRONTIER: 4.0,
        DifficultyTier.HARD_CONTROL: 6.0,
    }
    for family in CAPABILITY_SENSITIVE_FAMILIES:
        for tier in DifficultyTier:
            for index in range(TIER_TASKS_PER_FAMILY[tier]):
                dimensions = {
                    name: (
                        1
                        if name == flatten_dimension
                        and (flatten_family is None or family == flatten_family)
                        else tier_value[tier]
                    )
                    for name in STRICT_MONOTONIC_DIMENSIONS
                }
                structure = SimpleNamespace(
                    **dimensions,
                    single_retrieval_solvable=tier == DifficultyTier.EASY_CONTROL,
                    semantic_score=semantic_score[tier],
                )
                tasks.append(
                    SimpleNamespace(
                        family=family,
                        tier=tier,
                        structure=structure,
                        capability_demand=_axis_demand(FAMILY_PRIMARY_CAPABILITY[family]),
                        verification=SimpleNamespace(passed=True),
                        public_corpus=SimpleNamespace(
                            evidence=(
                                SimpleNamespace(evidence_id=f"{family}:{tier.value}:{index}"),
                            )
                        ),
                    )
                )
    return tuple(tasks)


def test_frontier_audit_requires_every_registered_structural_dimension() -> None:
    ready = make_capability_sensitive_frontier_audit(_frontier_tasks())
    flattened_family = CAPABILITY_SENSITIVE_FAMILIES[0]
    collapsed = make_capability_sensitive_frontier_audit(
        _frontier_tasks(
            flatten_dimension="query_decomposition_rounds",
            flatten_family=flattened_family,
        )
    )

    assert ready.structural_frontier_ready is True
    assert ready.next_permitted_stage == "paired_model_capability_boundary_calibration"
    assert collapsed.strict_dimension_passes["query_decomposition_rounds"] is True
    assert (
        collapsed.family_strict_dimension_passes[flattened_family]["query_decomposition_rounds"]
        is False
    )
    assert collapsed.structural_frontier_ready is False
    assert collapsed.next_permitted_stage == "frontier_task_construction_only"
