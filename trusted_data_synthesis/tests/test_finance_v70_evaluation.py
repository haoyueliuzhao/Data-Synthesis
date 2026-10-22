"""Focused synthetic evaluation contracts; no model, API or old score runs."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import finqa_v70_evaluation as evaluation


@pytest.fixture
def stats(monkeypatch):
    path = Path(evaluation.__file__).with_name("finqa_v54_statistics.py")
    spec = importlib.util.spec_from_file_location("_v70_test_original_native_metrics", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(evaluation, "_original", lambda: SimpleNamespace(stats=module))
    return module


def native(state, task="finqa/a"):
    return dict(task_key=f"draw20260928/{task}", native=dict(
        status="unknown" if state == "UNKNOWN" else "invalid_prediction" if state == "I" else "scored",
        program_executable=None if state == "UNKNOWN" else state != "I",
        native=dict(execution_accuracy=None if state == "UNKNOWN" else int(state == "R"),
                    program_accuracy=None if state == "UNKNOWN" else int(state == "R"))))


def test_exact_three_job_dose_and_no_score_dependent_selection():
    jobs = evaluation.planned_jobs()
    assert set(jobs) == {"step1192.cal_greedy", "step1490.cal_greedy", "step1490.dev_greedy"}
    assert sum(job["denominator"] for job in jobs.values()) == 1123
    assert {(row["step"], row["denominator"]) for row in jobs.values()} == {(1192, 120), (1490, 120), (1490, 883)}
    for row in jobs.values():
        assert row["arm"] == "Full" and row["seed"] == 137
        assert row["config"]["temperature"] == 0 and row["config"]["seed"] == 20260928
        assert (row["config"]["max_steps"], row["config"]["max_new_tokens"], row["config"]["context_limit"]) == (32, 2048, 24576)
    contract = evaluation.evaluation_contract()
    assert not contract["source_cluster_bootstrap"] and not contract["cross_seed_confidence_interval"]
    assert not contract["baseline_rescoring"] and not contract["intermediate_score_selection"]
    assert contract["final_endpoint"] == 1490 and not contract["automatic_extension"]


def test_job_rejects_extra_endpoints_or_changed_decoding():
    job = copy.deepcopy(next(iter(evaluation.planned_jobs().values())))
    job["config"]["temperature"] = 1.0
    with pytest.raises(ValueError, match="unregistered endpoint"):
        evaluation._job(job)


def test_native_episode_is_hashed_from_JSON_payload_not_pydantic_object():
    class Episode:
        def model_dump(self, *, mode):
            assert mode == "json"
            return {"field": [1, 2], "tuple_native_now_list": ["a"]}
    assert evaluation.canonical_episode_hash(Episode()) == evaluation.canonical_episode_hash(Episode().model_dump(mode="json"))
    assert evaluation.canonical_episode_payload(Episode())["field"] == [1, 2]


def test_pairing_reports_new_lost_net_and_preserves_unknown(stats):
    baseline = [native("I", "a"), native("R", "b"), native("W", "c")]
    candidate = [native("R", "a"), native("W", "b"), native("R", "c")]
    result = evaluation.paired_result(candidate, baseline, 3)
    assert (result["new_correct"], result["lost_correct"], result["net_correct"]) == (2, 1, 1)
    candidate[2] = native("UNKNOWN", "c")
    result = evaluation.paired_result(candidate, baseline, 3)
    assert result["status"] == "INCOMPLETE" and result["net_correct"] is None
    metrics = stats.native_metrics(candidate, 3)
    assert metrics["states"]["UNKNOWN"] == 1
    assert metrics["execution_accuracy"]["denominator"] == 3
    assert metrics["execution_accuracy"]["complete_dataset_mean"] is None


def test_pairing_rejects_task_order_change(stats):
    with pytest.raises(ValueError, match="task/draw order"):
        evaluation.paired_result([native("R", "b"), native("R", "a")],
                                 [native("R", "a"), native("R", "b")], 2)


def test_new_Full_snapshot_loader_never_calls_fixed894_original_loader(monkeypatch):
    calls = []
    state = {"arm": "Full", "step": 1490, "outer_done": [298, 894, 1192]}
    fake = SimpleNamespace(runtime=lambda: (None, "runtime"),
        read_checkpoint=lambda ref, rt: calls.append((ref, rt)) or state,
        validate_point_state=lambda value, step, rt: value if value["step"] == step else pytest.fail("wrong point"))
    monkeypatch.setitem(sys.modules, "finqa_v70_training", fake)
    assert evaluation._snapshot_state({"path": "new"}, 1490) is state
    assert calls == [({"path": "new"}, "runtime")]


def test_unstarted_future_generation_audit_is_safe_and_no_runtime_import(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, "_runtime", lambda: pytest.fail("future empty point needs no model runtime"))
    job = evaluation.planned_jobs()["step1490.dev_greedy"]
    result = evaluation.audit_job_resume(tmp_path, job)
    assert result["resume_allowed"] and result["unknown_calls"] == result["progress_units"] == 0
    assert not result["complete_stage"]


def test_unknown_generation_audit_is_forwarded_without_retry(tmp_path, monkeypatch):
    job = evaluation.planned_jobs()["step1192.cal_greedy"]
    directory = evaluation.generation_root(tmp_path, job)
    directory.mkdir(parents=True)
    (directory / "run.json").write_text("{}")
    monkeypatch.setattr(evaluation, "_protocol", lambda root: {"id": "protocol"})
    monkeypatch.setattr(evaluation, "checked", lambda path: {"protocol_id": "protocol", "job": job})
    monkeypatch.setattr(evaluation, "_runtime", lambda: None)
    monkeypatch.setattr(evaluation, "_inspect", lambda *args: None)
    unknown = dict(resume_allowed=False, unknown_calls=1, progress_units=2, evidence=[],
                   durable_progress_digest="digest", complete_stage=False)
    monkeypatch.setattr(evaluation.binding, "old_module", lambda name: SimpleNamespace(audit_resume=lambda root: unknown))
    assert evaluation.audit_job_resume(tmp_path, job) == unknown


def test_durable_native_rows_and_complete_report_are_reused_without_rescoring(tmp_path, monkeypatch, stats):
    job = dict(job_id="toy", role="calibration", denominator=2, step=1192)
    baseline = dict(coordinate="seed137/C1", feedback_batch=1, denominator=2,
                    results=[native("I", "a"), native("R", "b")])
    plan = dict(protocol_id="P", job=job, cohort=dict(tasks=["a", "b"], source_groups={"a": "A", "b": "B"}),
                snapshot="snapshot", snapshot_id="S")
    seal = {"id": "seal"}
    class Episode:
        stop_reason, actual_model_calls, tool_events, turns = "submit", 1, [], []
        def __init__(self, task): self.task = task
        def model_dump(self, *, mode): return {"task": self.task}
    episodes = [Episode("a"), Episode("b")]
    table = {str(evaluation.job_root(tmp_path, job) / "registration/record.json"): plan}
    def publish(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        result = dict(value, id=evaluation.binding.digest(value))
        path.write_text(json.dumps(result))
        table[str(path)] = result
        return result
    monkeypatch.setattr(evaluation, "publish", publish)
    monkeypatch.setattr(evaluation, "checked", lambda path: table[str(path)])
    monkeypatch.setattr(evaluation, "_job", lambda value: value)
    monkeypatch.setattr(evaluation, "_seal", lambda *args: (seal, episodes))
    monkeypatch.setattr(evaluation.binding, "read_ref", lambda ref: baseline)
    monkeypatch.setattr(evaluation, "_original", lambda: SimpleNamespace(stats=stats,
        _panel_private_bundles=lambda *args: {"a": "a", "b": "b"}))
    score_calls = []
    final = SimpleNamespace(load_public_snapshot=lambda path: ({"id": "S"}, [], []),
        score_public_reasoning_program=lambda task, episode: score_calls.append(task) or native("R", task)["native"])
    first_row = dict(task_key="draw20260928/a", original_task_key="a", native=native("R", "a")["native"])
    publish(evaluation.job_root(tmp_path, job) / "native_rows/row0000/record.json",
        dict(protocol_id="P", job_id="toy", ordinal=0, episode_sha256=evaluation.canonical_episode_hash(episodes[0]),
             generation_seal_id="seal", row=first_row))
    protocol = dict(id="P", baseline_evaluation={"model_reports": {"calibration": {"path": "baseline"}}})
    first = evaluation._score_job(tmp_path, job, protocol, {"id": "barrier"}, final)
    assert score_calls == ["b"]
    second = evaluation._score_job(tmp_path, job, protocol, {"id": "barrier"}, final)
    assert first == second and score_calls == ["b"]
    assert first["paired_to_894"]["net_correct"] == 1


def test_explicit_STOP_blocks_finish_before_any_runtime_or_private_read(tmp_path, monkeypatch):
    (tmp_path / "STOP").write_text("stop")
    monkeypatch.setattr(evaluation, "_protocol", lambda root: pytest.fail("must stop first"))
    with pytest.raises(ValueError, match="STOP"):
        evaluation.finish(tmp_path)


def test_all_exit_barrier_precedes_runtime_and_scoring(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, "_protocol", lambda root: {"id": "P"})
    def blocked(*args): raise ValueError("not all 26 exited")
    monkeypatch.setattr(evaluation, "generation_exit_barrier", blocked)
    monkeypatch.setattr(evaluation, "_runtime", lambda: pytest.fail("private scorer/runtime started before barrier"))
    with pytest.raises(ValueError, match="26 exited"):
        evaluation.finish(tmp_path)


def test_native_UNKNOWN_stops_completion_without_rescore_or_further_panel_choice(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, "_protocol", lambda root: {"id": "P"})
    monkeypatch.setattr(evaluation, "generation_exit_barrier", lambda *args: {"id": "B"})
    monkeypatch.setattr(evaluation, "_runtime", lambda: None)
    calls = []
    monkeypatch.setattr(evaluation, "_score_job", lambda root, job, *args: calls.append(job["job_id"])
                        or {"status": "INCOMPLETE_UNKNOWN"})
    with pytest.raises(ValueError, match="UNKNOWN blocks"):
        evaluation.finish(tmp_path)
    assert calls == ["step1192.cal_greedy"]
