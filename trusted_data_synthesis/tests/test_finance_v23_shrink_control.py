"""CPU-only distribution matching, state restoration and sealed-scoring gates."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/finqa_v23_shrink_control.py"
SPEC = importlib.util.spec_from_file_location("shrink_control", SCRIPT)
shrink = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shrink)


def distributions():
    qc = {"a": {"x": 0.9, "y": 0.1}, "b": {"x": 0.2, "y": 0.8}, "single": {"x": 1.0}}
    prior = {"a": {"x": 0.5, "y": 0.5}, "b": {"x": 0.6, "y": 0.4}, "single": {"x": 1.0}}
    mu = {"a": "1/6", "b": "1/3", "single": "1/2"}
    return qc, prior, mu


def test_global_gamma_matches_nonuniform_original_mu_and_preserves_support():
    qc, prior, mu = distributions()
    qn = shrink.geometric_shrink(qc, prior, 0.23)
    result = shrink.solve_gamma(qc, qn, prior, mu)
    assert result["applicable"] and abs(result["gamma"] - 0.23) < 1e-12
    assert abs(result["residual"]) < 1e-12
    assert result["q_shrink"]["single"] == {"x": 1.0}
    assert set(result["q_shrink"]) == set(qc)
    for t in qc:
        assert set(result["q_shrink"][t]) == set(qc[t])
        assert sum(result["q_shrink"][t].values()) == pytest.approx(1)
    assert result["no_outcomes_NLL_or_trial_training_used"] is True


def test_boundary_and_flat_endpoints_need_no_trials():
    qc, prior, mu = distributions()
    assert shrink.solve_gamma(qc, qc, prior, mu)["gamma"] == 0
    assert shrink.solve_gamma(qc, prior, prior, mu)["gamma"] == 1
    assert shrink.solve_gamma(prior, prior, prior, mu)["gamma"] == 0


def test_outside_reachable_interval_is_not_applicable_no_extrapolation():
    qc, prior, mu = distributions()
    closer = shrink.geometric_shrink(qc, prior, 0.8)
    result = shrink.solve_gamma(closer, qc, prior, mu)
    assert result["applicable"] is False
    assert result["gamma"] is None and result["q_shrink"] is None
    with pytest.raises(ValueError, match=r"\[0,1\]"):
        shrink.geometric_shrink(qc, prior, -0.1)


def test_one_unmatched_seed_blocks_entire_B_without_dropping_seed():
    records = {str(s): {"solution": {"applicable": True}} for s in (11, 29, 47)}
    assert shrink.all_seeds_applicable(records) is True
    records["47"]["solution"]["applicable"] = False
    assert shrink.all_seeds_applicable(records) is False
    del records["47"]
    with pytest.raises(ValueError, match="no subset"):
        shrink.all_seeds_applicable(records)


@pytest.mark.parametrize("bad", [0.0, -0.1, float("nan"), True])
def test_nonpositive_or_invalid_probabilities_never_clipped(bad):
    qc, prior, mu = distributions()
    qc["a"]["x"] = bad
    with pytest.raises(ValueError):
        shrink.solve_gamma(qc, prior, prior, mu)


def test_missing_task_and_guessed_mu_rejected():
    qc, prior, mu = distributions()
    with pytest.raises(ValueError, match="support"):
        shrink.solve_gamma({"a": qc["a"]}, qc, prior, mu)
    with pytest.raises(ValueError, match="mu"):
        shrink.solve_gamma(qc, qc, prior, {t: 1.0 for t in mu})


def test_matching_global_KL_does_not_claim_TV_entropy_per_task_match():
    qc, prior, mu = distributions()
    qn = shrink.geometric_shrink(qc, prior, 0.3)
    # Redistribute KL contribution across two tasks without altering the policy.
    qn["a"] = prior["a"]
    solution = shrink.solve_gamma(qc, qn, prior, mu)
    chi = {"a": {"x": 1, "y": 0}, "b": {"x": 1, "y": 0}, "single": {"x": 1}}
    d = shrink.distribution_diagnostics(solution["q_shrink"], prior, qc, qc, mu, chi)
    n = shrink.distribution_diagnostics(qn, prior, qc, qc, mu, chi)
    assert d["mu_weighted"]["KL_to_prior"] == pytest.approx(n["mu_weighted"]["KL_to_prior"])
    assert d["per_task"]["a"]["KL_to_prior"] != n["per_task"]["a"]["KL_to_prior"]
    assert d["mu_weighted"]["TV_to_prior"] != n["mu_weighted"]["TV_to_prior"]
    assert d["mu_weighted"]["frozen_chi0_positive_replenishment_from_C"] > 0
    assert d["joint_task_state_ESS"] > 0
    assert d["chi1_renormalized_joint_ESS"] > 0


def test_unknown_singleton_chi_is_not_low_quality_or_high_quality():
    qc, prior, mu = distributions()
    chi = {"a": {"x": 1, "y": 0}, "b": {"x": 1, "y": 0}, "single": {"x": None}}
    d = shrink.distribution_diagnostics(qc, prior, qc, qc, mu, chi)
    assert d["per_task"]["single"]["frozen_chi_unknown_singleton_mass"] == 1
    assert d["per_task"]["single"]["frozen_chi0_mass"] == 0
    assert d["mu_weighted"]["frozen_chi_unknown_singleton_mass"] == 0.5


def test_undercoverage_is_probability_mass_not_chi_label():
    qc, prior, mu = distributions()
    chi = {"a": {"x": 0, "y": 1}, "b": {"x": 1, "y": 0}, "single": {"x": None}}
    current = {"a": {"x": 0.2, "y": 0.8}, "b": prior["b"], "single": prior["single"]}
    q = shrink.geometric_shrink(qc, prior, 0.3)
    d = shrink.distribution_diagnostics(q, prior, current, qc, mu, chi)
    a = d["per_task"]["a"]
    assert a["undercovered_states"] == {"current_anchor_below_prior": ["x"], "C_below_prior": ["y"]}
    assert a["current_anchor_below_prior_net_replenishment_from_C"] < 0
    assert a["C_below_prior_net_replenishment_from_C"] > 0
    assert a["current_anchor_below_prior_current_anchor_mass"] == 0.2
    assert a["C_below_prior_C_mass"] == 0.1
    assert d["global_q_over_r_minimum"] < 1 < d["global_q_over_r_maximum"]


def test_stratification_is_expectation_not_best_of_two_and_unknowns_not_zero():
    ids = [f"t{i}" for i in range(120)]
    rows = [
        dict(
            coordinate=f"draw{draw}/{t}",
            task_id=t,
            draw=draw,
            native={
                "native": {"execution_accuracy": int(draw == 0), "program_accuracy": int(draw == 2)}
            },
        )
        for draw in range(3)
        for t in ids
    ]
    result = shrink.stratify(rows, ids)
    assert result["execution_accuracy"]["stochastic_expectation"]["mean"] == 0.5
    assert result["execution_accuracy"]["greedy"]["mean"] == 0
    assert result["program_accuracy"]["greedy"]["mean"] == 1
    rows[0]["native"]["native"]["execution_accuracy"] = None
    with pytest.raises(ValueError, match="unknown"):
        shrink.stratify(rows, ids)


def test_real_cpu_restore_preserves_Adam_RNG_schedule_no_new_outer(tmp_path, monkeypatch):
    from test_finance_v9_mechanism_execution import make_driver, run_main

    from trusted_synthesis.finance_research.v8_training_driver import _tree_digest
    from trusted_synthesis.finance_research.v9_conditional_training import ConditionalTrainingDriver
    from trusted_synthesis.finance_research.v9_mechanism_execution import checked_outer, checkpoint

    _, runs = run_main(tmp_path / "source")
    outer = runs["C-only"].root / "step0008_outer"
    record, state, actual = checked_outer(outer, production=False)
    spec = dict(
        actual_outer_inputs_digest=record["outer_inputs_digest"],
        q_C=state["pi"],
        q_N=state["pi"],
        prior=state["prior"],
        current_anchor=actual["pre_state"]["pi"],
        mu=actual["mu"],
        solution=shrink.solve_gamma(state["pi"], state["pi"], state["prior"], actual["mu"]),
    )
    monkeypatch.setattr(
        ConditionalTrainingDriver,
        "outer_update",
        lambda *a, **k: pytest.fail("new feedback/C forbidden"),
    )
    result = shrink.execute_shrink(
        factory=make_driver, source_outer=outer, spec=spec, output=tmp_path / "B"
    )
    assert result["actual_extra_training_steps"] == 2
    assert result["start_step"] == 8 and result["end_step"] == 10
    assert result["API_calls"] == result["new_feedback_sessions"] == 0
    _, initial = checkpoint(tmp_path / "B/training/step0008_mechanism_branch")
    for key in ("parameters", "optimizer", "rng", "schedule", "prior"):
        assert _tree_digest(initial[key]) == _tree_digest(state[key])
    assert initial["outer_done"] == state["outer_done"]
    assert result["checkpoint"]["actual_state_digest"] != record["actual_state_digest"]
    with pytest.raises(ValueError, match="repeated"):
        shrink.execute_shrink(
            factory=make_driver, source_outer=outer, spec=spec, output=tmp_path / "B"
        )


def test_all_three_seeds_sealed_before_private_reference_read(tmp_path, monkeypatch):
    from trusted_synthesis.finance_research import storage

    monkeypatch.setattr(shrink, "registration", lambda *a, **k: {"applicable": True})
    seen = []

    def fake_seal(root, seed):
        seen.append(seed)
        if seed == 47:
            raise FileNotFoundError("third seed unsealed")
        return {"denominator": 360}

    monkeypatch.setattr(shrink, "seal", fake_seal)
    monkeypatch.setattr(
        storage,
        "_read_snapshot_rows",
        lambda *a, **k: pytest.fail("private references read before1080"),
    )
    with pytest.raises(FileNotFoundError, match="third seed"):
        shrink.score(tmp_path)
    assert seen == [11, 29, 47]


def test_api_model_guard_rejects_other_model(tmp_path, monkeypatch):
    from trusted_synthesis.finance_research import storage

    monkeypatch.setattr(
        shrink,
        "read",
        lambda *a, **k: {"model": "deepseek-v4-pro", "API_calls": 0, "new_feedback_sessions": 0},
    )
    monkeypatch.setattr(storage, "runtime_binding", lambda: {})
    with pytest.raises(ValueError, match="deepseek-flash"):
        shrink.registration(tmp_path)
