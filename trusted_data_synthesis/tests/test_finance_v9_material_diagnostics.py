from fractions import Fraction

from test_finance_v9_conditional_training import material

from trusted_synthesis.finance_research.v9_material_diagnostics import (
    diagnose_pool,
    manual_dose,
    schedule_exposure,
)


def test_tail_exposure_is_exact_but_not_equal_across_fixed_tasks():
    report = schedule_exposure([f"q{i}" for i in range(7)], 11)
    assert report["sum_c_x"] == "20"
    assert report["expected_c_x_under_uniform_permutation"] == "20/7"
    assert report["exact_equal_finite_exposure"] is False
    assert sum(row["tail_batch_visits"] for row in report["per_task"].values()) == 20
    for row in report["per_task"].values():
        tail = row["tail_batch_visits"]
        assert row["visits"] == 10
        assert Fraction(row["c_x"]) == Fraction(10 - tail, 5) + Fraction(tail, 2)
    full = schedule_exposure([f"q{i}" for i in range(10)], 11)
    assert full["exact_equal_finite_exposure"] is True
    assert full["min_c_x"] == full["max_c_x"] == "2"


def test_manual_true_binary_mass_and_unequal_global_dose():
    report = manual_dose(
        {"a": {"z0": "2/3", "z1": "1/3"}, "b": {"z": "1"}},
        {"a": {"z0": 0, "z1": 1}, "b": {"z": 1}},
        {"a": "1/2", "b": "1/2"},
    )
    a, b = report["per_task"]["a"], report["per_task"]["b"]
    assert (a["p"], a["p_plus"], a["p_minus"]) == ("1/3", "1/2", "1/5")
    assert (a["TV_plus"], a["TV_minus"]) == ("1/6", "2/15")
    assert b["TV_plus"] == b["TV_minus"] == "0"
    assert report["mu_weighted_TV_plus"] == "1/12"
    assert report["mu_weighted_TV_minus"] == "1/15"


def test_material_lengths_include_zero_target_original_history():
    pool = material(7)
    for rows in pool._rows.values():
        rows[0]["layer_target_positions"] = {"reason": [1], "tool": [2], "final": []}
    first = pool.packages[0]["package_id"]
    pool._rows[first].append(
        dict(
            input_ids=list(range(19)),
            target_ids=[],
            layer_target_positions={"reason": [], "tool": [], "final": []},
        )
    )
    lineages = {
        t: dict(source_group="group" + str(i % 2), source_group_level="report")
        for i, t in enumerate(pool.task_ids)
    }
    report = diagnose_pool(pool, lineages)
    assert report["complete_response_row_sequence_tokens"]["maximum"] == 19
    assert report["complete_response_row_sequence_tokens"]["count"] == 22
    assert report["source_groups"] == {"group0": 4, "group1": 3}
    assert report["supervised_token_layers"] == {"reason": 21, "tool": 21, "final": 0}
    assert report["reason_layer"] == "R+U" and report["model_calls"] == 0
