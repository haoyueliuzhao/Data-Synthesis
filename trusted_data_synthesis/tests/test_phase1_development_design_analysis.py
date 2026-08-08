from __future__ import annotations

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_development_design_analysis import (
    classify_effect_interval,
    measurement_design_power,
)


def test_effect_interval_keeps_significance_and_equivalence_as_separate_axes() -> None:
    result = classify_effect_interval(
        mean=0.2,
        ci_lower=0.1,
        ci_upper=0.3,
        minimum_practical_effect=1.0,
    )
    assert result == {
        "statistically_nonzero": True,
        "statistical_direction": "positive",
        "practically_equivalent": True,
        "meaningful_beyond_mpe": False,
        "meaningful_direction": "unresolved",
        "joint_resolution": "sub_mpe_nonzero_and_equivalent",
    }


@pytest.mark.parametrize(
    ("ci_lower", "ci_upper", "expected"),
    [
        (-0.2, 0.2, "equivalent_including_zero"),
        (1.1, 1.5, "meaningful_positive"),
        (-1.5, -1.1, "meaningful_negative"),
        (-0.2, 1.2, "inconclusive_across_mpe_boundary"),
    ],
)
def test_effect_interval_joint_resolutions(ci_lower: float, ci_upper: float, expected: str) -> None:
    result = classify_effect_interval(
        mean=(ci_lower + ci_upper) / 2.0,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        minimum_practical_effect=1.0,
    )
    assert result["joint_resolution"] == expected


def test_measurement_power_separates_objective_and_realization_support() -> None:
    rows = [
        {
            "minimum_practical_effect": 1.0,
            "objective_variance": 0.16,
            "realization_variance": 0.0001,
            "interaction_variance": 0.0001,
        }
    ]
    power = measurement_design_power(
        rows,
        objective_split_grid=(8, 16),
        realization_grid=(5, 8),
        effect_ratio_grid=(0.0, 0.25),
    )
    lookup = {
        (
            row["objective_micro_split_count"],
            row["realization_count_per_state"],
            row["true_effect_ratio_to_mpe"],
        ): row
        for row in power
    }
    assert (
        lookup[(16, 5, 0.25)]["mean_nonzero_detection_probability"]
        > lookup[(8, 5, 0.25)]["mean_nonzero_detection_probability"]
    )
    objective_gain = lookup[(16, 5, 0.25)]["median_normalized_standard_error"]
    realization_gain = lookup[(8, 8, 0.25)]["median_normalized_standard_error"]
    assert objective_gain < realization_gain
    assert (
        lookup[(16, 5, 0.0)]["mean_equivalence_declaration_probability"]
        >= lookup[(8, 5, 0.0)]["mean_equivalence_declaration_probability"]
    )
