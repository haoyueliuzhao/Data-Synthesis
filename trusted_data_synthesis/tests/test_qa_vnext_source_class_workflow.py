"""Finite source-class weights and selection; no Teacher or Student execution."""

from fractions import Fraction

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.derive import (
    fixed_selection,
)
from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.plan import (
    CONDITIONS,
    GROUPS,
    SEEDS,
    TASKS,
    X3_KEYS,
    package_mass,
    select_candidate,
    utility,
)


@pytest.mark.parametrize("arm", CONDITIONS)
def test_exact_mass_table_and_six_task_marginals(arm):
    weights = {}
    for task in TASKS:
        routes = ("D", "A") if task == "X3C" else ("control",)
        weights[task] = [package_mass(arm, task, route) for route in routes for _ in range(3)]
        assert sum(weights[task]) == Fraction(1, 6)
    assert sum(map(sum, weights.values())) == 1
    assert sum(map(len, weights.values())) == 21


def test_local_loss_wiring_same_parameter_state():
    losses = {
        "D": [Fraction(2), Fraction(3), Fraction(7)],
        "A": [Fraction(9), Fraction(4), Fraction(8)],
    }
    values = {
        arm: sum(
            package_mass(arm, "X3C", r) * loss for r, group in losses.items() for loss in group
        )
        for arm in CONDITIONS
    }
    delta = (sum(losses["A"]) - sum(losses["D"])) / 3 / 36
    assert values["plus_A"] - values["pi0"] == delta
    assert values["minus_D"] - values["pi0"] == -delta


def matrix(zero, plus, minus):
    return {
        arm: {s: value for s in SEEDS}
        for arm, value in zip(CONDITIONS, (zero, plus, minus), strict=True)
    }


@pytest.mark.parametrize(
    ("values", "chosen"),
    [
        (("1/2", "1/2", "1/2"), "pi0"),
        (("1/2", "1/3", "1/4"), "pi0"),
        (("1/2", "2/3", "2/3"), "plus_A"),
        (("1/2", "2/3", "3/4"), "minus_D"),
        (("1/2", "7/12", "1/2"), "plus_A"),
    ],
)
def test_strict_positive_and_predeclared_ties(values, chosen):
    result = select_candidate(matrix(*values))
    assert result["selected_condition"] == chosen
    assert result["confirmation_required"] == (chosen != "pi0")
    assert result["no_runner_up_after_confirmation"]


def test_unknowns_stay_in_registered_denominator():
    assert utility({g: (1, 4) for g in GROUPS}) == Fraction(1, 4)


def support_rows():
    result = []
    for key in ("X1", "X2", "X3C"):
        for rep in range(1, 9):
            route = "D" if rep in (1, 2, 7, 8) or key != "X3C" else "A"
            result.append(
                {
                    "label": f"N_{key}_{rep:02d}",
                    "task_key": key,
                    "arm": "N",
                    "formula_driven_trace_verified": True,
                    "projection": {"status": "MAPPED", "behavior_key": X3_KEYS[route]},
                    "historical_behavior_label": "PURE_D" if route == "D" else "OTHER_VALID_CLASS",
                }
            )
    return result


def test_fixed_order_not_prose_quality_or_holdout_replacement():
    selection = fixed_selection(list(reversed(support_rows())))
    assert [r["label"] for r in selection["train"]] == [
        "N_X1_01",
        "N_X1_02",
        "N_X1_03",
        "N_X2_01",
        "N_X2_02",
        "N_X2_03",
        "N_X3C_01",
        "N_X3C_02",
        "N_X3C_07",
        "N_X3C_03",
        "N_X3C_04",
        "N_X3C_05",
    ]
    assert [r["label"] for r in selection["heldout"]] == ["N_X3C_08", "N_X3C_06"]
    rows = support_rows()
    rows[-1]["formula_driven_trace_verified"] = False
    assert fixed_selection(rows)["status"] == "INPUT_INADEQUATE"


def test_E_support_never_substitutes_N_support():
    rows = support_rows()
    for row in rows:
        if row["task_key"] == "X3C" and row["label"].endswith("_08"):
            row["arm"] = "E"
    assert fixed_selection(rows)["status"] == "INPUT_INADEQUATE"
