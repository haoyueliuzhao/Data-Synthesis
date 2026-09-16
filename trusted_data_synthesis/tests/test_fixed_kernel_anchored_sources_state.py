"""Only unequal-count integration and the new all-zero feedback branch."""

import importlib
import sys
from fractions import Fraction
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
m = importlib.import_module("fixed_kernel_anchored_sources_state_20260916")


def test_variable_original_counts_recover_each_alpha0_package_mass():
    rows = [
        {"task_id": "x", "state_id": state, "method": method}
        for state, method in [
            ("e1", "endpoint"),
            ("e1", "endpoint"),
            ("e2", "endpoint"),
            ("m", "movement"),
            ("m", "movement"),
        ]
    ]
    rows += [{"task_id": "c", "state_id": "c1", "method": "control"} for _ in range(3)]
    prior, n, methods = m.prior_from_headers(rows)
    assert prior["x"] == {"e1": "1/3", "e2": "1/6", "m": "1/2"}
    for row in rows:
        task, state, method = row["task_id"], row["state_id"], row["method"]
        expected = (Fraction(1) if method == "control" else Fraction(1, 2)) / (
            5 * methods[task, method] * 137
        )
        assert m.target_coefficient(prior[task][state], n[task, state], 137) == expected


def test_zero_feedback_holds_current_not_prior_and_refuses_incomplete_registry():
    pi = {"x": {"a": "7/10", "b": "3/10"}, "c": {"c": "1"}}
    prior = {"x": {"a": "1/2", "b": "1/2"}, "c": {"c": "1"}}
    for condition in ("c_only_anchored", "full_anchored_vtdo"):
        r = m.update_distribution(
            pi,
            prior,
            None,
            {"x": "1/2", "c": "1/2"},
            [0] * 360,
            condition=condition,
            registered_complete=True,
            control_tasks={"c"},
        )
        assert r["status"] == "UNINFORMATIVE_FEEDBACK" and r["pi_next"] == pi
        assert r["novelty_active"] and r["additional_feedback_calls"] == 0
    with pytest.raises(ValueError, match="complete_fixed360"):
        m.update_distribution(
            pi,
            prior,
            None,
            {"x": "1/2", "c": "1/2"},
            [0] * 359,
            condition="full_anchored_vtdo",
            registered_complete=True,
            control_tasks={"c"},
        )
