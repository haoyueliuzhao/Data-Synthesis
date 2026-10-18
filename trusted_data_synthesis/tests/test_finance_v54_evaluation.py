from __future__ import annotations

from copy import deepcopy
import hashlib
from types import SimpleNamespace

import pytest

import finqa_v54_evaluation as evaluation
import finqa_v54_statistics as stats


def native(task, state):
    values = {"R": ("scored", True, 1.0), "W": ("scored", True, 0.0),
              "I": ("invalid_prediction", False, 0.0), "UNKNOWN": ("unknown", None, None)}
    status, executable, value = values[state]
    return dict(task_key=task, native=dict(status=status, program_executable=executable,
        native=dict(execution_accuracy=value, program_accuracy=value)))


def reports(arms):
    tasks = [f"q{i}" for i in range(len(arms["Hold"]))]
    result = {}
    for seed in stats.SEEDS:
        for arm in stats.ARMS:
            rows = [native(task, state) for task, state in zip(tasks, arms[arm], strict=True)]
            result[stats.coordinate(seed, arm)] = dict(seed=seed, arm=arm, results=rows,
                denominator=len(tasks), metrics=stats.native_metrics(rows, len(tasks)))
    return tasks, result


def test_panel_configs_and_exact_session_budget():
    contract, jobs = evaluation.evaluation_contract(), evaluation.planned_jobs()
    assert contract["total_sessions"] == sum(j["denominator"] for j in jobs.values()) == 12267
    assert contract["total_new_sessions_including_feedback"] == 14367
    assert len(jobs) == 45
    assert [p["sessions"] for p in contract["panels"].values()] == [1080, 1080, 2160, 7947]
    assert contract["old_test1147_new_generation"] == 0
    for job in jobs.values():
        config = job["config"]
        assert (config["max_new_tokens"], config["max_steps"], config["context_limit"]) == (2048, 32, 24576)
        assert (config["top_p"], config["top_k"], config["tier"]) == (1, 0, "EVAL_NATIVE")
        assert (config["temperature"], config["seed"]) in ((0, 20260928), (1, 11), (1, 29))
        assert job["step"] != 745 or config["temperature"] == 0
    with pytest.raises(ValueError, match="unregistered"):
        evaluation.panel_config("step745_calibration120_random_T1", 11)


def test_transition_orientation_and_exact_decomposition():
    old = [native(str(i), s) for i, s in enumerate("IWRRWI")]
    new = [native(str(i), s) for i, s in enumerate("RRWIWW")]
    value = stats.paired_transitions(new, old, 6)
    assert value["difference"] == 0
    assert value["transitions"]["I->R"] == 1
    assert value["transitions"]["W->R"] == 1
    assert value["transitions"]["R->W"] == 1
    assert value["transitions"]["R->I"] == 1
    assert value["transitions"]["I->W"] == 1
    assert value["decomposition"]["numerator"] == 0
    assert value["both_executable"]["denominator"] == 3


def test_unknown_keeps_full_denominator_and_only_blocks_affected_comparison():
    tasks, values = reports(dict(Hold=["W", "I"], C1=["R", "I"], C05=["R", "R"]))
    row = values[stats.coordinate(137, "Hold")]
    row["results"][0] = native(tasks[0], "UNKNOWN")
    row["metrics"] = stats.native_metrics(row["results"], 2)
    result = stats.paired_summary(values, tasks, dict(zip(tasks, ("a", "b"))), denominator=2)
    assert result["comparisons"]["C05-C1"]["status"] == "COMPLETE"
    assert result["comparisons"]["C05-Hold"]["seed_summary"] is None
    assert result["comparisons"]["C1-Hold"]["status"] == "INCOMPLETE"
    seed = result["comparisons"]["C05-Hold"]["per_seed"]["137"]
    assert seed["denominator"] == 2 and seed["unknown_pair_count"] == 1
    assert seed["difference"] is None
    assert row["metrics"]["execution_accuracy"]["complete_dataset_mean"] is None
    assert stats.advancement(result, contracts_complete=True)["status"] == "EVALUATION_INCOMPLETE"


def test_three_parents_directional_rule_and_zero_baseline():
    tasks, values = reports(dict(Hold=["I", "W", "R"], C1=["W", "R", "R"], C05=["R", "R", "R"]))
    result = stats.paired_summary(values, tasks, {t: "source" for t in tasks}, denominator=3)
    assert result["independent_parent_count"] == 3
    seed = result["comparisons"]["C05-C1"]["seed_summary"]
    assert seed["n"] == 3 and seed["sample_SD"] == 0 and seed["positive"] == 3
    assert seed["seed_t_approximate_interval"]["df"] == 2
    assert stats.advancement(result, contracts_complete=True)["advance"] is True
    assert stats.advancement(result, contracts_complete=False)["advance"] is False
    result["comparisons"]["C05-C1"]["seed_summary"]["mean"] = 0
    assert stats.advancement(result, contracts_complete=True)["status"] == "RETAIN_BASELINE"


def test_source_clusters_share_weights_and_are_task_weighted():
    vectors = {"C05-C1": [1, 1, -1], "C05-Hold": [1, 1, 0], "C1-Hold": [0, 0, 1]}
    value = stats.source_cluster_sensitivity(vectors, ["a", "a", "b"])
    reversed_keys = stats.source_cluster_sensitivity(dict(reversed(list(vectors.items()))), ["a", "a", "b"])
    assert value == reversed_keys
    assert value["replicates"] == 10000 and value["seed"] == 20261018
    assert value["cluster_task_counts"] == {"a": 2, "b": 1}
    assert value["comparisons"]["C05-C1"]["mean_difference"] == pytest.approx(1 / 3)
    assert value["same_weights_all_seeds_and_arms"] is True


def test_native_unknown_and_score_contradictions_are_not_repaired():
    row = native("q", "I")
    row["native"]["native"]["execution_accuracy"] = 1
    with pytest.raises(ValueError, match="contradiction"):
        stats.native_state(row)


def test_exact_zero_count_mean_cannot_promote_float_cancellation_residue():
    summary = stats.seed_effect_summary([0.1, 0.2, -0.3], count_differences=[1, 2, -3], denominator=10)
    assert summary["mean"] == 0.0


def training_fixture(tmp_path):
    protocol = evaluation.publish(tmp_path / "protocol/record.json", dict(evaluation=evaluation.evaluation_contract()))
    results, bindings = {}, {}
    for seed in stats.SEEDS:
        for arm in stats.ARMS:
            key = stats.coordinate(seed, arm)
            path = tmp_path / "branches" / f"seed{seed}" / arm / "completed/record.json"
            results[key] = evaluation.publish(path, dict(status="COMPLETE", seed=seed, arm=arm,
                optimizer_updates=298, snapshots={str(step): dict(path=f"mock/{key}/{step}",
                    state_sha256="s", record_sha256="r", actual_state_digest="a") for step in (745, 894)}))
            bindings[key] = evaluation.file_binding(path)
    seal = dict(protocol_id=protocol["id"], all_nine_logical_branches_complete=True,
        all_18_snapshots_sealed=True, all_dispatched_training_workers_exited=True,
        active_children=[], branch_records=bindings, worker_exits=[])
    return results, seal


def test_generation_waits_for_all_branches_and_real_worker_exit(tmp_path):
    results, seal = training_fixture(tmp_path)
    seal["all_dispatched_training_workers_exited"] = False
    evaluation.publish(tmp_path / "training_barrier/record.json", seal)
    with pytest.raises(ValueError, match="successful training exits"):
        evaluation.generation_barrier(tmp_path, branch_reader=lambda r, s, a: results[stats.coordinate(s, a)])


def test_full_training_barrier_is_immutable(tmp_path):
    results, seal = training_fixture(tmp_path)
    evaluation.publish(tmp_path / "training_barrier/record.json", seal)
    barrier = evaluation.generation_barrier(tmp_path, branch_reader=lambda r, s, a: results[stats.coordinate(s, a)])
    assert len(barrier["branches"]) == 9 and len(barrier["snapshots"]) == 18
    bad = deepcopy(results)
    bad[stats.coordinate(389, "C05")]["snapshots"].pop("894")
    with pytest.raises(ValueError, match="all nine"):
        evaluation.generation_barrier(tmp_path, branch_reader=lambda r, s, a: bad[stats.coordinate(s, a)])


def test_score_cannot_open_references_before_complete_panel(monkeypatch, tmp_path):
    private_reads = []
    monkeypatch.setattr(evaluation, "checked_plan", lambda _: {})
    monkeypatch.setattr(evaluation, "_runtime", lambda: SimpleNamespace())
    monkeypatch.setattr(evaluation, "_panel_private_bundles", lambda *args: private_reads.append(args))
    def blocked(*args, **kwargs):
        raise ValueError("panel incomplete")
    monkeypatch.setattr(evaluation, "seal_panel", blocked)
    with pytest.raises(ValueError, match="panel incomplete"):
        evaluation.score(tmp_path, evaluation.PRIMARY_PANEL)
    assert private_reads == []


def test_private_reference_selection_never_parses_unselected_test_row(tmp_path):
    raw = b'not-even-valid-json-for-unselected-test\n{"answer": 7}\n'
    (tmp_path / "private.references.jsonl").write_bytes(raw)
    parsed = []
    final = SimpleNamespace(task_key=lambda x: x,
        PrivateReference=SimpleNamespace(model_validate_json=lambda value: parsed.append(value) or "reference"),
        TaskBundle=lambda **kwargs: kwargs)
    bundles = evaluation._panel_private_bundles(final, dict(snapshot=str(tmp_path)),
        dict(files={"private.references.jsonl": dict(sha256=hashlib.sha256(raw).hexdigest())}),
        ["test", "dev"], ["test_lineage", "dev_lineage"], {"dev"})
    assert parsed == [b'{"answer": 7}']
    assert bundles == {"dev": dict(public="dev", reference="reference", lineage="dev_lineage")}
