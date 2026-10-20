"""CPU-only V63 budget, provenance, global barriers and exact research gate."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

import finqa_v63_binding as binding
import finqa_v63_evaluation as evaluation
import finqa_v63_statistics as stats


def native(task, state, source="group"):
    status, executable, value = {
        "R": ("scored", True, 1.0), "W": ("scored", True, 0.0),
        "I": ("invalid_prediction", False, 0.0), "UNKNOWN": ("unknown", None, None),
    }[state]
    return dict(task_key=task, source_group=dict(group=source, level="report"),
                native=dict(status=status, program_executable=executable,
                            native=dict(execution_accuracy=value, program_accuracy=value)))


def report(seed, arm, states, batch):
    rows = [native(f"q{i}", state) for i, state in enumerate(states)]
    value = dict(seed=seed, arm=arm, feedback_batch=batch, results=rows,
                 denominator=len(rows), metrics=stats.native_metrics(rows, len(rows)))
    if arm == "Hold":
        value.update(reused_old_hold=True, old_model_report=dict(path=f"/old/{seed}/Hold", sha256="a" * 64),
                     old_summary_id="old-summary", old_registration_id="old-registration")
    return value


def paired_fixture(monkeypatch, *, hold=("W", "I"), c1=("R", "I"), c05=("R", "R")):
    monkeypatch.setattr(stats.original, "source_cluster_sensitivity",
                        lambda vectors, groups: dict(status="COMPLETE", comparisons={}))
    new = {stats.coordinate(s, a): report(s, a, c1 if a == "C1" else c05, 1)
           for s in stats.SEEDS for a in stats.ARMS}
    holds = {stats.original.coordinate(s, "Hold"): report(s, "Hold", hold, None) for s in stats.SEEDS}
    tasks = [f"q{i}" for i in range(len(c05))]
    return tasks, {task: dict(group="group", level="report") for task in tasks}, new, holds


def decision_summary(temperature_total, hold_total=1):
    comparisons = {}
    totals = {"C05-C1": temperature_total, "C05-Hold": hold_total,
              "C1-Hold": hold_total - temperature_total}
    for name, total in totals.items():
        counts = [total, 0, 0]
        per_seed = {
            str(seed): dict(status="COMPLETE", denominator=883, unknown_pair_count=0,
                            numerator=count, difference=count / 883)
            for seed, count in zip(stats.SEEDS, counts, strict=True)}
        comparisons[name] = dict(status="COMPLETE", denominator=883, per_seed=per_seed,
            seed_summary=stats.seed_effect_summary([n / 883 for n in counts],
                                                   count_differences=counts, denominator=883))
    conditions = {stats.coordinate(s, a): dict(feedback_batch=1, source="new_sealed_result")
                  for s in stats.SEEDS for a in stats.ARMS}
    conditions.update({stats.original.coordinate(s, "Hold"): dict(
        feedback_batch=None, source="read_only_old_hold", old_model_report=dict(path="/old", sha256="a" * 64),
        old_summary_id="old-summary", old_registration_id="old-registration") for s in stats.SEEDS})
    return dict(feedback_batch=1, primary_uses_only_new_batch=True, old_new_batch_pooling=False,
                best_of_old_new_selection=False, denominator=883, independent_parent_count=3,
                conditions=conditions, comparisons=comparisons)


def test_exact_new_budget_and_fixed_evaluation_seeds():
    jobs, contract = evaluation.planned_jobs(), evaluation.evaluation_contract()
    assert len(jobs) == contract["generation_jobs"] == 24
    assert sum(job["denominator"] for job in jobs.values()) == contract["total_sessions"] == 7458
    assert contract["new_feedback_sessions"] == 4200
    assert contract["total_new_sessions_including_feedback"] == 11658
    assert contract["logical_endpoint_conditions"] == 15
    assert contract["independent_parent_count"] == 3
    assert {panel: row["sessions"] for panel, row in contract["panels"].items()} == {
        "step894_calibration120_greedy": 720,
        "step894_calibration120_random_T1": 1440,
        "step894_dev883_greedy": 5298,
    }
    for key, job in jobs.items():
        assert job["step"] == 894 and job["arm"] in ("C1", "C05")
        assert job["feedback_batch"] == 1 and "_b1_draw" in key
        config = job["config"]
        assert (config["max_new_tokens"], config["max_steps"], config["context_limit"]) == (2048, 32, 24576)
        assert (config["temperature"], config["seed"]) in ((0, 20260928), (1, 11), (1, 29))
        assert config["top_p"] == 1 and config["top_k"] == 0
    with pytest.raises(ValueError, match="no step745"):
        evaluation.panel_config("step745_calibration120_greedy", 20260928)
    with pytest.raises(ValueError, match="unregistered"):
        evaluation.panel_config("step894_calibration120_random_T1", 101)


def test_original_native_and_uncertainty_math_is_reused():
    assert stats.native_metrics is stats.original.native_metrics
    assert stats.paired_transitions is stats.original.paired_transitions
    assert stats.seed_effect_summary is stats.original.seed_effect_summary
    assert stats.source_cluster_sensitivity is stats.original.source_cluster_sensitivity
    contract = stats.statistics_contract()
    assert contract["source_cluster"]["replicates"] == 10000
    assert contract["source_cluster"]["seed"] == 20261018
    assert not contract["all_seeds_positive_required"]
    assert not contract["all_auxiliary_panels_positive_required"]
    assert not contract["significance_or_stability_confirmation"]


@pytest.mark.parametrize(("net", "passes"), [(26, False), (27, True), (1, False), (0, False)])
def test_exact_integer_research_gate_26_vs_27(net, passes):
    value = stats.advancement(decision_summary(net), contracts_complete=True)
    assert value["advance"] is passes
    assert value["temperature_net_correct"] == net
    assert value["delta_temperature"] == net / 2649
    assert value["automatic_followup_authorized"] is False
    if passes:
        # The registered rule does not add an all-seeds-positive requirement.
        assert decision_summary(net)["comparisons"]["C05-C1"]["seed_summary"]["positive"] == 1


@pytest.mark.parametrize(("contracts", "hold"), [(False, 1), (True, 0), (True, -1)])
def test_contract_or_strict_hold_gate_cannot_be_bypassed(contracts, hold):
    assert stats.advancement(decision_summary(27, hold), contracts_complete=contracts)["advance"] is False


def test_threshold_is_not_a_float_mean_or_old_batch_selection():
    value = decision_summary(26)
    value["comparisons"]["C05-C1"]["seed_summary"]["mean"] = 0.01
    with pytest.raises(ValueError, match="exact counts"):
        stats.advancement(value, contracts_complete=True)
    value = decision_summary(27)
    value["conditions"]["seed137/C1"]["feedback_batch"] = 0
    with pytest.raises(ValueError, match="mix or select"):
        stats.advancement(value, contracts_complete=True)
    value = decision_summary(27)
    value["old_new_batch_pooling"] = True
    with pytest.raises(ValueError, match="old, pooled or selected"):
        stats.advancement(value, contracts_complete=True)


def test_unknown_keeps_denominator_and_blocks_only_affected_pair(monkeypatch):
    tasks, groups, new, holds = paired_fixture(monkeypatch)
    hold = holds["seed137/Hold"]
    hold["results"][0] = native(tasks[0], "UNKNOWN")
    hold["metrics"] = stats.native_metrics(hold["results"], 2)
    result = stats.paired_summary(new, tasks, groups, denominator=2, old_hold_reports=holds)
    assert result["comparisons"]["C05-C1"]["status"] == "COMPLETE"
    assert result["comparisons"]["C05-Hold"]["status"] == "INCOMPLETE"
    row = result["comparisons"]["C05-Hold"]["per_seed"]["137"]
    assert row["denominator"] == 2 and row["unknown_pair_count"] == 1 and row["difference"] is None
    decision = decision_summary(27)
    decision["comparisons"]["C05-Hold"]["status"] = "INCOMPLETE"
    assert stats.advancement(decision, contracts_complete=True)["status"] == "EVALUATION_INCOMPLETE"


def test_summary_rejects_mixed_new_batches_and_unbound_hold(monkeypatch):
    tasks, groups, new, holds = paired_fixture(monkeypatch)
    new["seed251/C1"]["feedback_batch"] = 0
    with pytest.raises(ValueError, match="mixed feedback batches"):
        stats.paired_summary(new, tasks, groups, denominator=2, old_hold_reports=holds)
    new["seed251/C1"]["feedback_batch"] = 1
    holds["seed137/Hold"].pop("old_model_report")
    with pytest.raises(ValueError, match="bound model"):
        stats.paired_summary(new, tasks, groups, denominator=2, old_hold_reports=holds)


def training_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    protocol = evaluation.publish(tmp_path / "protocol/record.json",
                                  dict(evaluation=evaluation.evaluation_contract()))
    results, references = {}, {}
    for seed in stats.SEEDS:
        for arm in stats.ARMS:
            key = stats.coordinate(seed, arm)
            path = tmp_path / f"branches/seed{seed}/{arm}/completed/record.json"
            results[key] = evaluation.publish(path, dict(
                schema="v63_fixed_q_branch_complete.v1", status="COMPLETE", seed=seed, arm=arm,
                feedback_batch=1, optimizer_updates=298, new_optimizer_updates=298,
                snapshots={str(step): dict(path=f"/mock/{key}/{step}", state_sha256="s",
                                           record_sha256="r", actual_state_digest="d") for step in (745, 894)}))
            references[key] = evaluation.file_binding(path)
    seal = dict(protocol_id=protocol["id"], all_six_new_branches_complete=True,
                all_six_894_snapshots_sealed=True, all_dispatched_training_workers_exited=True,
                active_children=[], branch_records=references)
    return results, seal


def test_all_six_new_training_branches_and_real_exit_barrier(tmp_path, monkeypatch):
    results, seal = training_fixture(tmp_path, monkeypatch)
    evaluation.publish(tmp_path / "training_barrier/record.json", seal)
    barrier = evaluation.generation_barrier(
        tmp_path, branch_reader=lambda root, seed, arm: results[stats.coordinate(seed, arm)])
    assert barrier["new_branches"] == barrier["snapshot_count"] == 6
    assert all(key.endswith("/step894") for key in barrier["snapshots"])
    bad = deepcopy(results)
    bad["seed137/C1"]["new_optimizer_updates"] = 0
    with pytest.raises(ValueError, match="six complete new b1"):
        evaluation.generation_barrier(
            tmp_path, branch_reader=lambda root, seed, arm: bad[stats.coordinate(seed, arm)])


def test_training_not_exited_cannot_generate(tmp_path, monkeypatch):
    results, seal = training_fixture(tmp_path, monkeypatch)
    seal["all_dispatched_training_workers_exited"] = False
    evaluation.publish(tmp_path / "training_barrier/record.json", seal)
    with pytest.raises(ValueError, match="actual successful training exits"):
        evaluation.generation_barrier(
            tmp_path, branch_reader=lambda root, seed, arm: results[stats.coordinate(seed, arm)])


def test_both_new_arms_keep_pre596_outer_history(monkeypatch):
    monkeypatch.setattr(evaluation.original, "_snapshot_state",
                        lambda *args: dict(outer_done=[298, 596]))
    with pytest.raises(ValueError, match="old C1 outer"):
        evaluation._snapshot_state({}, 137, 894, None)
    monkeypatch.setattr(evaluation.original, "_snapshot_state", lambda *args: dict(outer_done=[298]))
    assert evaluation._snapshot_state({}, 137, 894, None)["outer_done"] == [298]


def test_scoring_cannot_read_private_references_before_global_24_exit_barrier(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, "checked_plan", lambda root: dict(
        contract=evaluation.evaluation_contract(), jobs=evaluation.planned_jobs()))
    private_reads = []
    monkeypatch.setattr(evaluation, "_runtime", lambda: SimpleNamespace())
    monkeypatch.setattr(evaluation, "_panel_private_bundles", lambda *args: private_reads.append(args))
    def blocked(*args):
        raise ValueError("all 24 generation jobs not exited")
    monkeypatch.setattr(evaluation, "generation_exit_barrier", blocked)
    with pytest.raises(ValueError, match="all 24"):
        evaluation.score(tmp_path, evaluation.PRIMARY_PANEL)
    assert private_reads == []


def generation_exit_fixture(tmp_path, monkeypatch, bad_exit=None):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    protocol = evaluation.publish(tmp_path / "protocol/record.json",
                                  dict(evaluation=evaluation.evaluation_contract()))
    plan = dict(id="plan", jobs=evaluation.planned_jobs())
    references = {}
    for key, job in plan["jobs"].items():
        directory = evaluation.job_root(tmp_path, job)
        attempt = directory / "attempts/attempt0001"
        evaluation.publish(attempt / "launch/record.json", dict(pid=12, birth="34"))
        evaluation.publish(attempt / "actual_exit/record.json", dict(
            protocol_id=protocol["id"], job_id=key, pid=12, birth="34",
            returncode=-9 if key == bad_exit else 0, actual_waitpid_observed=True))
        result = evaluation.publish(directory / "result/record.json", dict(
            registration_id=plan["id"], job_id=key, status="COMPLETE", feedback_batch=1,
            sessions=job["denominator"]))
        references[key] = evaluation.file_binding(directory / "result/record.json")
        evaluation.publish(directory / "accepted/record.json", dict(
            protocol_id=protocol["id"], job_id=key, result=references[key], result_id=result["id"],
            actual_exit=evaluation.file_binding(attempt / "actual_exit/record.json"),
            actual_exit_zero=True, resources_passed=True))
    evaluation.publish(tmp_path / "evaluation_barrier/record.json", dict(
        protocol_id=protocol["id"], all_24_generation_jobs_complete=True,
        all_dispatched_evaluation_workers_exited=True, active_children=[], job_results=references))
    return plan


def test_all_24_actual_exits_are_checked_not_just_the_controller_boolean(tmp_path, monkeypatch):
    key = next(iter(evaluation.planned_jobs()))
    plan = generation_exit_fixture(tmp_path, monkeypatch, bad_exit=key)
    with pytest.raises(ValueError, match="actually exit successfully"):
        evaluation.generation_exit_barrier(tmp_path, plan)


def test_complete_24_exit_barrier_exact_budget(tmp_path, monkeypatch):
    plan = generation_exit_fixture(tmp_path, monkeypatch)
    seal = evaluation.generation_exit_barrier(tmp_path, plan)
    assert seal["generation_jobs"] == len(seal["accepted_jobs"]) == 24
    assert seal["new_sessions"] == 7458 and seal["private_references_read"] is False


def test_old_hold_source_is_bound_to_original_path(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "OLD_ROOT", tmp_path / "old")
    with pytest.raises(ValueError, match="registered original path"):
        evaluation._old_registration(dict(old_evaluation_registration=dict(
            path=str(tmp_path / "new/evaluations/registration/record.json"), sha256="a" * 64)))


def test_reuse_reads_bound_old_nine_reports_without_rescoring_or_mutation(tmp_path, monkeypatch):
    new_root, old_root = tmp_path / "new", tmp_path / "old"
    monkeypatch.setattr(binding, "ROOT", new_root)
    monkeypatch.setattr(binding, "OLD_ROOT", old_root)
    panel = evaluation.PRIMARY_PANEL
    tasks = ["draw20260928/q0"]
    groups = {tasks[0]: dict(group="group", level="report")}
    cohorts = dict(development=dict(tasks=["q0"], denominator=1,
                                   source_groups={"q0": groups[tasks[0]]}))
    old_plan_path = old_root / "evaluations/registration/record.json"
    old_plan = evaluation.original.publish(old_plan_path, dict(
        contract=evaluation.original.evaluation_contract(), snapshot_id="public-snapshot", cohorts=cohorts))
    refs = {}
    for seed in stats.SEEDS:
        for arm in stats.original.ARMS:
            key = stats.original.coordinate(seed, arm)
            path = old_root / "evaluations/panels" / panel / "models" / f"seed{seed}" / arm / "record.json"
            rows = [native(tasks[0], "R")]
            evaluation.original.publish(path, dict(
                registration_id=old_plan["id"], panel=panel, seed=seed, arm=arm,
                denominator=1, all_generation_seal_id="old-seal", results=rows,
                metrics=stats.native_metrics(rows, 1)))
            refs[key] = evaluation.file_binding(path)
    old_summary_path = old_root / "evaluations/panels" / panel / "summary/record.json"
    old_summary = evaluation.original.publish(old_summary_path, dict(
        panel=panel, registration_id=old_plan["id"], independent_parent_count=3,
        denominator=1, all_generation_seal_id="old-seal", model_reports=refs))
    evaluation.publish(new_root / "protocol/record.json", dict(
        evaluation=evaluation.evaluation_contract(),
        old_evaluation_registration=evaluation.file_binding(old_plan_path),
        old_evaluation_summaries={panel: evaluation.file_binding(old_summary_path)}))
    plan = dict(snapshot_id="public-snapshot", cohorts=cohorts, contract=evaluation.evaluation_contract())
    summary, reused = evaluation.reused_old_reports(new_root, panel, plan, tasks, groups)
    assert summary["id"] == old_summary["id"]
    assert len(reused) == 9
    for seed in stats.SEEDS:
        hold = reused[f"seed{seed}/Hold"]
        assert hold["feedback_batch"] is None and hold["reused_old_hold"] is True
        assert hold["old_registration_id"] == old_plan["id"]
        assert hold["old_summary_id"] == old_summary["id"]
        for arm in ("C1", "C05"):
            assert reused[f"seed{seed}/{arm}"]["feedback_batch"] == 0
    for key, reference in refs.items():
        assert evaluation.file_binding(reference["path"]) == reference
        assert "feedback_batch" not in evaluation.checked(reference["path"])


def test_same_temperature_diagnostics_do_not_pool_or_rescore_old_batches(monkeypatch):
    tasks, groups, new, holds = paired_fixture(monkeypatch)
    old = dict(holds)
    for seed in stats.SEEDS:
        for arm in stats.ARMS:
            row = report(seed, arm, ("W", "W"), 0)
            row.update(old_model_report=dict(path=f"/old/{seed}/{arm}", sha256="a" * 64),
                       old_summary_id="old-summary", old_registration_id="old-registration")
            old[stats.coordinate(seed, arm)] = row
    result = stats.batch_replication_diagnostics(new, old, tasks, denominator=2)
    assert result["used_in_advancement"] is False and result["old_results_rescored"] is False
    assert result["old_bootstrap_rerun"] is False and result["independent_parent_count"] == 3
    assert result["comparisons"]["C05_b1-C05_b0"]["seed_summary"]["mean"] == 1.0
    old["seed137/C05"]["feedback_batch"] = 1
    with pytest.raises(ValueError, match="bound b0 and b1"):
        stats.batch_replication_diagnostics(new, old, tasks, denominator=2)
