from __future__ import annotations

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_gradient_numeric_validation import (
    derive_pairwise_uncertainty_envelope,
    evaluate_margin_aware_ordering,
    ordering_sensitivity,
)


def _row(
    *,
    task_id: str,
    state_id: str,
    full: float,
    recomposed: float,
    task_type: str = "comparison",
) -> dict[str, object]:
    return {
        "task_id": task_id,
        "task_type": task_type,
        "state_id": state_id,
        "numeric_full_gp_score": full,
        "numeric_recomposed_gp_score": recomposed,
        "full_gp_score": full,
        "recomposed_gp_score": recomposed,
    }


def test_pairwise_uncertainty_envelope_uses_conservative_state_error_bound() -> None:
    rows = [
        _row(task_id="task-a", state_id="state-a", full=0.4, recomposed=0.39988),
        _row(task_id="task-a", state_id="state-b", full=0.2, recomposed=0.20031),
    ]

    result = derive_pairwise_uncertainty_envelope(rows)

    assert result["status"] == "passed"
    assert result["maximum_absolute_state_mean_score_error"] == pytest.approx(0.00031)
    assert result["raw_pairwise_uncertainty_envelope"] == pytest.approx(0.00062)
    assert result["pairwise_uncertainty_envelope"] == pytest.approx(0.0007)


def test_margin_aware_ordering_ignores_only_numerically_unresolved_pair() -> None:
    rows = [
        _row(task_id="task-a", state_id="state-a", full=1.0, recomposed=1.0),
        _row(task_id="task-a", state_id="state-b", full=0.5000, recomposed=0.4990),
        _row(task_id="task-a", state_id="state-c", full=0.4995, recomposed=0.5000),
    ]

    result = evaluate_margin_aware_ordering(rows, uncertainty_envelope=0.001)

    assert result["status"] == "passed"
    assert result["metrics"]["resolvable_pair_count"] == 2
    assert result["metrics"]["resolvable_pair_violation_count"] == 0
    assert result["metrics"]["strict_permutation_agreement_count"] == 0
    assert result["metrics"]["all_winner_agreement_rate"] == 1.0


def test_margin_aware_ordering_rejects_resolvable_direction_flip() -> None:
    rows = [
        _row(task_id="task-a", state_id="state-a", full=1.0, recomposed=1.0),
        _row(task_id="task-a", state_id="state-b", full=0.5000, recomposed=0.4990),
        _row(task_id="task-a", state_id="state-c", full=0.4995, recomposed=0.5000),
    ]

    result = evaluate_margin_aware_ordering(rows, uncertainty_envelope=0.0001)

    assert result["status"] == "failed"
    assert result["metrics"]["resolvable_pair_violation_count"] == 1
    assert "resolvable_pair_direction_violation" in result["failure_reasons"]


def test_margin_aware_ordering_rejects_an_envelope_that_hides_support() -> None:
    rows = [
        _row(task_id="task-a", state_id="state-a", full=0.004, recomposed=0.004),
        _row(task_id="task-a", state_id="state-b", full=0.003, recomposed=0.003),
        _row(task_id="task-a", state_id="state-c", full=0.002, recomposed=0.002),
    ]

    result = evaluate_margin_aware_ordering(rows, uncertainty_envelope=0.005)

    assert result["status"] == "failed"
    assert result["metrics"]["resolvable_pair_count"] == 0
    assert "resolvable_pair_coverage_below_minimum" in result["failure_reasons"]
    assert "resolvable_task_coverage_below_minimum" in result["failure_reasons"]


def test_ordering_sensitivity_is_monotone_in_resolved_pair_count() -> None:
    rows = [
        _row(task_id="task-a", state_id="state-a", full=1.0, recomposed=1.0),
        _row(task_id="task-a", state_id="state-b", full=0.5, recomposed=0.499),
        _row(task_id="task-a", state_id="state-c", full=0.4995, recomposed=0.5),
    ]

    results = ordering_sensitivity(rows, envelopes=(0.0, 0.0005, 0.001))

    counts = [row["metrics"]["resolvable_pair_count"] for row in results]
    assert counts == sorted(counts, reverse=True)
    assert results[-1]["metrics"]["resolvable_pair_violation_count"] == 0


def test_margin_aware_ordering_fails_closed_on_non_finite_scores() -> None:
    rows = [
        _row(task_id="task-a", state_id="state-a", full=1.0, recomposed=1.0),
        _row(task_id="task-a", state_id="state-b", full=float("nan"), recomposed=0.0),
    ]

    with pytest.raises(ValueError, match="non-finite"):
        evaluate_margin_aware_ordering(rows, uncertainty_envelope=0.001)
