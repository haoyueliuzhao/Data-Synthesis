from __future__ import annotations

import copy

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_finite_radius_diagnostic import (
    _sign_consistent,
    _signed_derivatives,
    _triplet_instability,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_finite_target import (
    _observation_hash,
)


def _observations() -> list[dict[str, object]]:
    rows = []
    for radius, derivative in ((0.1, 2.0), (0.05, 2.0), (0.025, 2.0)):
        for sign in (-1, 1):
            row: dict[str, object] = {
                "plan_hash": "plan",
                "objective_role": "estimation",
                "numeric_contract_hash": "numeric",
                "design_row_id": "direction",
                "radius": radius,
                "sign": sign,
                "objective_value": sign * radius * derivative,
                "baseline_post_global_adapter_hash": "adapter",
                "baseline_objective_value": 0.0,
            }
            row["observation_hash"] = _observation_hash(row)
            rows.append(row)
    return rows


def test_radius_diagnostic_recovers_stable_derivatives() -> None:
    derivatives = _signed_derivatives(
        _observations(),
        direction_ids=("direction",),
        radii=(0.1, 0.05, 0.025),
        expected_plan_hash="plan",
        expected_role="estimation",
        expected_numeric_contract_hash="numeric",
    )

    values = derivatives["direction"]
    assert values == {0.1: 2.0, 0.05: 2.0, 0.025: 2.0}
    assert _triplet_instability(values, (0.1, 0.05, 0.025)) == pytest.approx(0.0)
    assert _sign_consistent(values) is True


def test_radius_diagnostic_rejects_rehashed_payload_tampering() -> None:
    rows = _observations()
    tampered = copy.deepcopy(rows)
    tampered[0]["objective_value"] = 999.0

    with pytest.raises(ValueError, match="observation identity changed"):
        _signed_derivatives(
            tampered,
            direction_ids=("direction",),
            radii=(0.1, 0.05, 0.025),
            expected_plan_hash="plan",
            expected_role="estimation",
            expected_numeric_contract_hash="numeric",
        )
