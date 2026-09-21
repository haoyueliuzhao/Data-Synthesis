"""CPU-only crash-boundary tests. No new model generation, scoring or process signals."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
a = importlib.import_module("fixed_kernel_delayed_C_autorun_state_20260921")
c = importlib.import_module("run_fixed_kernel_delayed_C_autorun_20260921")


def test_aggressive_phase_floors_increase_only_after_oom():
    assert a.FLOORS == dict(sft=32768, feedback=51200, final=57344, score=0)
    assert a.threshold("sft", 1) == 36864
    assert a.threshold("final", 99) == 77824
    assert [a.cooldown(n) for n in range(1, 7)] == [60, 120, 240, 480, 900, 900]


def test_atomic_immutable_equal_reuse_and_conflict(tmp_path):
    path = tmp_path / "state.json"
    a.write(path, dict(completed=23), immutable=True)
    a.write(path, dict(completed=23), immutable=True)
    with pytest.raises(ValueError, match="immutable_conflict"):
        a.write(path, dict(completed=24), immutable=True)
    assert a.p.read_json(path) == dict(completed=23)
    assert not list(tmp_path.glob("*.partial.*"))


def test_metadata_is_durable_and_restorable_before_local_commit(tmp_path, monkeypatch):
    root = tmp_path / "work"
    monkeypatch.setattr(a, "CONTROL", tmp_path / "disk")
    monkeypatch.setattr(a.p, "write_once", a.p.write_once)
    a.install_durable_writer(root)
    path = root / a.r.OUTPUT / "runs/test/report.json"
    assert a.p.write_once(path, dict(done=7)) == dict(done=7)
    path.unlink()
    a.restore_metadata(root)
    assert a.p.read_json(path) == dict(done=7)
    with pytest.raises(ValueError, match="immutable_conflict"):
        a.p.write_once(path, dict(done=8))


def test_final_storage_import_preserves_old_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(a.r, "RAW", tmp_path / "disk")
    root, key = tmp_path / "work", "A_delayed_c_47"
    directory = root / a.r.OUTPUT / "runs" / key / "final_greedy"
    a.write(directory / "completed/0000.json", dict(sealed=True))
    a.final_links(root, key)
    assert directory.is_symlink()
    assert a.p.read_json(directory / "completed/0000.json") == dict(sealed=True)
    assert (
        directory.with_name("final_greedy.preserved_before_data1_link") / "completed/0000.json"
    ).exists()
    a.final_links(root, key)


def test_capacity_wait_yields_only_after_bounded_boundary_wait(monkeypatch):
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: None)
    monkeypatch.setattr(torch.cuda, "mem_get_info", lambda: (2**30, 80 * 2**30))
    monkeypatch.setattr(torch.cuda, "memory_reserved", lambda: 20 * 2**30)
    sleeps, events = [], []
    monkeypatch.setattr(a.time, "sleep", sleeps.append)
    with pytest.raises(a.BoundaryYield, match="capacity_wait"):
        a.wait_capacity(32768, events.append)
    assert sleeps == [20, 20, 20] and len(events) == 4


def test_failure_classification_never_retries_numerical_error():
    assert (
        c.classify_exit(
            dict(resource_retry_allowed=False, error="ValueError('numeric_guard')"),
            "feedback",
            "feedback",
        )[0]
        == "fatal"
    )
    assert c.classify_exit(dict(resource_retry_allowed=True), "feedback", "feedback")[0] == "oom"
    assert c.classify_exit(None, "sft", "sft")[0] == "lost"
    assert c.classify_exit(dict(returncode=43), "final", "sft")[0] == "progress"


def test_busy_adopted_worker_is_never_signaled(tmp_path, monkeypatch):
    monkeypatch.setattr(
        c.m, "last_event", lambda path: dict(event="feedback_response_checkpointed")
    )
    monkeypatch.setattr(c.m, "signal_owned", lambda *args: pytest.fail("busy worker signaled"))
    assert not c.safe_adopted_yield(
        tmp_path, "A_delayed_c_29", dict(adopted=True, identity={"pid": 123}, attempt=1)
    )


def test_generation_oom_reuses_committed_cases_and_accounts_extra_call(tmp_path, monkeypatch):
    directory = tmp_path / "final"
    monkeypatch.setattr(a, "CONTROL", tmp_path / "control")
    monkeypatch.setattr(a, "wait_capacity", lambda *args: None)
    monkeypatch.setattr(a.f, "validate_receipts", lambda *args: None)
    jobs = [dict(index=i, task={"task_id": str(i)}, repeat=0, seed=i) for i in range(180)]
    point = {"id": "point"}
    parent = dict(assets={}, tasks=[job["task"] for job in jobs], source_manifest_id="source")
    counts, current, once = [], [None], [True]

    def generate():
        counts.append(current[0])
        if current[0] == 3 and once[0]:
            once[0] = False
            raise torch.OutOfMemoryError("injected shared GPU pressure")
        return "answer"

    model = SimpleNamespace(generate=generate, named_parameters=lambda: [])

    def job_runner(root, output, subset, bound_point, assets, actual_model, tokenizer, **kwargs):
        job = subset[0]
        current[0] = job["index"]
        actual_model.generate()
        path = output / "sessions" / f"{job['index']:04d}.json.gz"
        reference = a.f.write_session(path, {"id": f"session{job['index']}"})
        row = a.p.record(
            "anchored_generated_trajectory",
            job=job,
            point_id=bound_point["id"],
            path=str(path.relative_to(root)),
            **reference,
            actual_generate_calls=1,
            generated_tokens=1,
        )
        a.write(output / "completed" / f"{job['index']:04d}.json", row, immutable=True)
        return [row]

    monkeypatch.setattr(a.f, "generate_jobs", job_runner)
    with pytest.raises(torch.OutOfMemoryError):
        a.generate_remaining(tmp_path, directory, jobs, point, parent, model, None, 1, 57344)
    assert not (directory / "generation_manifest.json").exists()
    report = a.generate_remaining(tmp_path, directory, jobs, point, parent, model, None, 2, 57344)
    assert len(report["trajectories"]) == report["total_generate_calls"] == 180
    assert report["interrupted_attempt_generate_call_upper_bound"] == 1
    assert len(counts) == 181 and counts.count(0) == counts.count(1) == counts.count(2) == 1
    assert counts.count(3) == 2


def test_partial_final_cannot_open_private_scoring(tmp_path):
    a.write(
        tmp_path / "generation_manifest.json",
        a.p.record(
            "anchored_generation_manifest", complete=False, stochastic=False, trajectories=[]
        ),
    )
    with pytest.raises(ValueError, match="seal_all_180_before_scoring"):
        a.score_remaining(tmp_path, tmp_path, tmp_path)


def test_scoring_reuses_all_completed_assessments_without_rescoring(tmp_path, monkeypatch):
    directory = tmp_path / "final"
    trajectories = []
    for i in range(180):
        trajectories.append(
            dict(job=dict(index=i, task=dict(task_id=str(i), group="test")), session_id=f"s{i}")
        )
        a.write(
            directory / "assessments" / f"{i:04d}.json",
            dict(session_id=f"s{i}", financial_valid=i % 2 == 0),
        )
    manifest = a.p.record(
        "anchored_generation_manifest",
        complete=True,
        stochastic=False,
        point_id="point",
        tasks=[],
        source_manifest_id="source",
        trajectories=trajectories,
    )
    a.write(directory / "generation_manifest.json", manifest)
    monkeypatch.setattr(
        a, "ProcessPoolExecutor", lambda **kwargs: pytest.fail("completed cases rescored")
    )
    result = a.score_remaining(tmp_path, directory, tmp_path)
    assert result["qualified"] == 90 and result["denominator"] == 180
    assert a.score_remaining(tmp_path, directory, tmp_path) == result


def test_completed_final_inventory_rejects_other_point(tmp_path, monkeypatch):
    job = dict(index=0)
    row = a.p.record("anchored_generated_trajectory", job=job, point_id="wrong")
    a.write(tmp_path / "completed/0000.json", row)
    with pytest.raises(ValueError, match="fixed_final_job_and_point"):
        a.inventory(tmp_path, tmp_path, [job], {"id": "correct"})


def test_controller_isolates_fatal_run_and_keeps_other_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(a, "CONTROL", tmp_path / "control")
    monkeypatch.setattr(c, "policy", lambda root: {})
    monkeypatch.setattr(c.r, "plans", lambda root: ({"id": "plan"}, {}))
    monkeypatch.setattr(a, "restore_metadata", lambda root: None)
    monkeypatch.setattr(a, "archive_metadata", lambda root, known: None)
    monkeypatch.setattr(a, "cursor", lambda key: 250)
    monkeypatch.setattr(c, "safe_adopted_yield", lambda *args: False)
    monkeypatch.setattr(c.time, "sleep", lambda _: None)
    monkeypatch.setattr(c.m, "signal_owned", lambda *args: pytest.fail("healthy worker signaled"))
    retained_checks = []

    def alive(identity):
        if identity["pid"] == 1:
            return False
        retained_checks.append(True)
        return len(retained_checks) == 1

    monkeypatch.setattr(c.m, "same_process", alive)
    monkeypatch.setattr(
        a,
        "phase",
        lambda root, key: "done" if key.endswith("_29") and len(retained_checks) >= 2 else "sft",
    )
    monkeypatch.setattr(
        c,
        "failure_record",
        lambda root, key, active: dict(
            error="ValueError('numeric_guard')", resource_retry_allowed=False
        ),
    )
    state = {}
    for i, key in enumerate(c.KEYS, 1):
        state[key] = dict(
            active=dict(identity={"pid": i}, phase="sft", attempt=1),
            attempt=1,
            failures={name: 0 for name in a.FLOORS},
            not_before=0,
            stopped=None,
        )
    a.write(a.CONTROL / "state.json", state)
    assert c.coordinate(tmp_path) == 1
    saved = a.p.read_json(a.CONTROL / "state.json")
    assert saved[c.KEYS[0]]["stopped"] is not None
    assert saved[c.KEYS[1]]["stopped"] is None
    assert len(retained_checks) == 2


def test_watchdog_restarts_preemption_but_not_protocol_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(a, "CONTROL", tmp_path / "control")
    monkeypatch.setattr(c, "policy", lambda root: {})
    codes = iter([-9, 42, 1])
    monkeypatch.setattr(
        c, "spawn", lambda *args, **kwargs: SimpleNamespace(wait=lambda: next(codes))
    )
    sleeps = []
    monkeypatch.setattr(c.time, "sleep", sleeps.append)
    assert c.watch(tmp_path) == 1
    assert sleeps == [30, 30]
