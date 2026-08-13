from __future__ import annotations

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    CapabilityRuntimeArm,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    CAPABILITY_SENSITIVE_FAMILIES,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_flash_information_matrix import (
    _matrix_bundle,
    _OutcomeRow,
    _positive_eigenvalues,
    _spectrum,
)


def _row(index: int, realizations: tuple[int, ...]) -> _OutcomeRow:
    demand = tuple(1.0 if axis == index % len(CAPABILITY_AXES) else 0.2 for axis in range(7))
    return _OutcomeRow(
        task_artifact_id=f"task:{index}",
        family=CAPABILITY_SENSITIVE_FAMILIES[index % len(CAPABILITY_SENSITIVE_FAMILIES)],
        probability=sum(realizations) / len(realizations),
        general_difficulty=float(index % 3),
        demand=demand,
        realizations=realizations,
    )


def test_saturated_outcomes_have_zero_empirical_information() -> None:
    rows = [_row(index, (1, 1)) for index in range(14)]

    spectrum = _spectrum(
        runtime=CapabilityRuntimeArm.AUTONOMOUS_AGENT,
        response_variable="final_valid",
        rows=rows,
        task_count=len(rows),
        boundary_lower=0.1,
        boundary_upper=0.9,
    )

    assert spectrum.residual_numerical_rank == 0
    assert spectrum.boundary_task_fraction == 0
    assert sum(spectrum.marginal_axis_information.values()) == 0


def test_mixed_task_outcomes_create_nonzero_information() -> None:
    rows = [_row(index, (0, 1) if index % 2 == 0 else (1, 1)) for index in range(21)]

    bundle = _matrix_bundle(rows)
    spectrum = _spectrum(
        runtime=CapabilityRuntimeArm.AUTONOMOUS_AGENT,
        response_variable="final_valid",
        rows=rows,
        task_count=len(rows),
        boundary_lower=0.1,
        boundary_upper=0.9,
    )

    assert spectrum.residual_numerical_rank > 0
    assert spectrum.boundary_task_fraction == 11 / 21
    assert sum(bundle.residual_matrix[index][index] for index in range(7)) > 0


def test_numerical_dust_does_not_create_a_false_information_rank() -> None:
    assert _positive_eigenvalues((4e-34, 2e-34, 1e-34)) == []
