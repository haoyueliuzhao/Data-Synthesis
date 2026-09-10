"""New-cohort controls only: no replay, old rescoring or old tokenization."""

import ast
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_bidirectional_utility.panel import Panel
from trusted_synthesis.experiments.finance_qa_vnext_bidirectional_utility.plan import (
    CONDITIONS,
    LABELS,
    SEEDS,
    TASKS,
    TRAIN_TASKS,
    condition,
    downstream_plan,
    encode,
    policy,
    registrations,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_bidirectional_utility.study import (
    classify,
    fixed_selection,
    package_weights,
    select_candidate,
    target_prototypes,
    utility,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import evaluate
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.stage import public_document

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def panel():
    return Panel(ROOT)


@pytest.fixture(scope="module")
def prototypes(panel):
    return target_prototypes(panel, {k: public_document(v) for k, v in panel.tasks.items()})


def test_all_real_sources_bound_before_teacher(panel):
    assert len(panel.tasks) == 39
    assert list(map(len, panel.panels.values())) == [3, 12, 24]
    assert panel.companies == {
        "train": ["ETR", "GRMN", "GS", "INTC", "K", "PPG"],
        "dev": ["ADBE", "AWK", "LMT", "NCLH", "RSG"],
        "confirm": ["AAPL", "ABMD", "AMT", "BKR", "ECL", "KHC", "MRK", "UNP"],
    }


@pytest.mark.parametrize("key,expected", [("X1", "46.4"), ("X2", "6"), ("X3", "87.8")])
def test_two_real_training_relations_not_gold_formula_copy(panel, key, expected):
    task = panel.tasks[key]
    for route in ("D", "R"):
        assert evaluate(task["sufficient_routes"][route], task["facts"]) == Fraction(expected)
    assert task["sufficient_routes"]["D"] != task["sufficient_routes"]["R"]


def test_full_unmodified_model_input_no_private_routes(panel):
    for task in panel.tasks.values():
        public = public_document(task)
        assert public["question"] == task["entry"]["qa"]["question"]
        assert public["source"] == {k: task["entry"][k] for k in ("table", "pre_text", "post_text")}
        assert len(public["numeric_catalog"]) == len(task["facts"])
        assert not {"target", "sufficient_routes", "goal_scope", "original_private_spec"} & set(
            public
        )


def test_bound_budget_not_adaptive(panel):
    rows = registrations({k: public_document(panel.tasks[k]) for k in TASKS})
    assert [r["label"] for r in rows] == list(LABELS)
    assert len(rows) == len(set(LABELS)) == 72
    for key in TASKS:
        assert [r["replicate"] for r in rows if r["task_key"] == key] == list(range(1, 25))
    c = condition()
    assert c["maximum_model_requests"] == 72 * 32
    assert c["concurrent_workers"] == 24
    assert not c["force_reconstruction"] and not c["hide_disclosure"]
    assert c["first_Final_terminal_even_if_incorrect_or_no_calculation"]


def _projection(prototype):
    return dict(
        status="MAPPED",
        behavior_signature=deepcopy(prototype["signature"]),
        behavior_key=prototype["behavior_key"],
    )


@pytest.mark.parametrize("key", TASKS)
def test_private_full_signature_prototypes_are_distinct(prototypes, key):
    p = prototypes["tasks"][key]
    assert classify(_projection(p["D"]), p) == "D"
    assert classify(_projection(p["R"]), p) == "R"
    assert p["D"]["signature"] != p["R"]["signature"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("substantive_revision_path", [{"changed": "financial_source_pairing"}]),
        ("evidenced_independent_cross_checks", [{"second_executed_relation": "R"}]),
        ("active_support", ["different_original_source_fact"]),
    ],
)
def test_same_last_formula_does_not_absorb_other_valid_classes(prototypes, field, value):
    p = prototypes["tasks"]["X1"]
    projection = _projection(p["D"])
    projection["behavior_signature"][field] = value
    projection["behavior_key"] = sha(encode(projection["behavior_signature"]))
    assert classify(projection, p) == "OTHER_VALID_CLASS"
    assert classify(dict(status="UNDETERMINED"), p) == "UNDETERMINED"


def test_four_independent_indices_not_text_uniqueness():
    selected = fixed_selection(["T_X1_24", "T_X1_09", "T_X1_03", "T_X1_01", "T_X1_07"])
    assert selected["train"] == ["T_X1_01", "T_X1_03", "T_X1_07"]
    assert selected["diagnostic"] == ["T_X1_09"]
    assert selected["unselected"] == ["T_X1_24"]
    insufficient = fixed_selection(["T_X1_01", "T_X1_02", "T_X1_03"])
    assert not insufficient["sufficient"]
    assert insufficient["train"] == insufficient["diagnostic"] == []
    with pytest.raises(ValueError):
        fixed_selection(["T_X1_01", "T_X1_01", "T_X1_01", "T_X1_01"])


@pytest.mark.parametrize("name", CONDITIONS)
def test_exact_mass_and_single_task_direction(name):
    weights, base = package_weights(name), package_weights("P_new")
    assert len(weights) == 27 and sum(weights.values()) == 1
    for task in TRAIN_TASKS:
        assert sum(w for (key, _, _), w in weights.items() if key == task) == Fraction(1, 6)
    changed = {key for (key, route, i), w in weights.items() if w != base[(key, route, i)]}
    assert changed == (set() if name == "P_new" else {name[:2]})
    assert sum(max(Fraction(0), weights[k] - base[k]) for k in weights) == (
        0 if name == "P_new" else Fraction(1, 36)
    )


@pytest.mark.parametrize("key", TASKS)
def test_same_parameter_loss_identity_on_new_weights(key):
    base = package_weights("P_new")
    losses = {label: Fraction(i * i + 11, i + 3) for i, label in enumerate(base)}
    contrast = sum(losses[(key, "R", i)] - losses[(key, "D", i)] for i in range(3)) / 3
    for sign, direction in ((1, "+"), (-1, "-")):
        weights = package_weights(key + direction)
        delta = sum((weights[label] - base[label]) * losses[label] for label in base)
        assert delta == sign * contrast / 36


def test_no_old_token_budget_or_B0_reintroduced():
    downstream = downstream_plan()
    t, e = downstream["training"], downstream["evaluation"]
    assert t["train_runs"] == 21 and t["packages_per_epoch"] == 27
    assert t["epochs"] == t["optimizer_updates"] == 10
    assert t["supervised_tokens_per_run"] is None
    assert t["sequence_tokens_per_run"] is None
    assert e["development_sessions"] == 252
    assert e["maximum_confirmation_sessions"] == 144
    assert e["total_sessions"] == 396 and e["no_B0"]
    assert "fewer than four" in policy()["stopping"]


def test_unknowns_are_in_main_utility_denominator():
    counts = {"dual_sufficient": (2, 4), "detail_related": (1, 4), "other_finance": (0, 4)}
    assert utility(counts) == Fraction(1, 4)


def _utilities(default=Fraction(1, 2)):
    return {name: {seed: default for seed in SEEDS} for name in CONDITIONS}


def test_baseline_wins_zero_tie_and_both_directions_can_lose():
    u = _utilities()
    assert select_candidate(u)["selected_condition"] == "P_new"
    u["X1+"] = {s: Fraction(5, 12) for s in SEEDS}
    u["X1-"] = {s: Fraction(1, 3) for s in SEEDS}
    result = select_candidate(u)
    assert Fraction(result["finite_delta_directional_utility"]["X1"]) > 0
    assert result["selected_condition"] == "P_new" and not result["confirmation_required"]


def test_negative_direction_can_win_and_positive_tie_is_fixed():
    u = _utilities()
    u["X2-"] = {s: Fraction(2, 3) for s in SEEDS}
    assert select_candidate(u)["selected_condition"] == "X2-"
    u["X1+"] = {s: Fraction(2, 3) for s in SEEDS}
    assert select_candidate(u)["selected_condition"] == "X1+"


def test_source_unit_and_included_excluded_component_checks(panel):
    c10 = panel.tasks["C10"]
    assert evaluate(c10["target"], c10["facts"]) == Fraction("33.458")
    assert c10["entry"]["qa"]["exe_ans"] == 33458
    c14 = panel.tasks["C14"]
    assert "excludes 450000" in c14["segments"]["q62"]["text"]
    assert evaluate(c14["target"], c14["facts"]) == 599768


@pytest.mark.parametrize("name", ["source.py", "projection.py", "tokens.py", "materialize.py"])
def test_inherited_offline_algorithms_not_semantically_changed(name):
    base = ROOT / "trusted_data_synthesis/src/trusted_synthesis/experiments"
    parent = ast.parse((base / "finance_qa_vnext_open_support_exploration" / name).read_text())
    current = ast.parse((base / "finance_qa_vnext_bidirectional_utility" / name).read_text())
    assert ast.dump(parent) == ast.dump(current)
