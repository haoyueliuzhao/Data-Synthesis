"""Bounded CPU-only scheduling checks; no live process, CUDA, model or API work."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/finqa_v18_four_gpu_queue_recovery.py"
SPEC = importlib.util.spec_from_file_location("v18_recovery_test", SCRIPT)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def job(tmp_path, key="arm-29-full"):
    return dict(
        key=key,
        module="v16_arm_training",
        args=["run-arm", "--seed", "29"],
        result=tmp_path / key / "result/record.json",
    )


def policy():
    return dict(
        schema="v18_four_gpu_queue_recovery.v1",
        allowed_gpu_indices=[1, 2, 3, 6],
        max_gpu_workers=4,
        minimum_free_mib=24576,
        API_calls=0,
        api_model_policy="deepseek-flash",
        restart_live_workers=False,
        partial_feedback_resampling=False,
        automatic_numerical_failure_retry=False,
    )


def test_fixed_four_gpu_policy():
    recovery.validate_policy(policy())


@pytest.mark.parametrize(
    "field,value",
    [
        ("allowed_gpu_indices", [0, 1, 2, 3]),
        ("max_gpu_workers", 8),
        ("minimum_free_mib", 1000),
        ("API_calls", 1),
        ("restart_live_workers", True),
        ("partial_feedback_resampling", True),
        ("automatic_numerical_failure_retry", True),
    ],
)
def test_no_expansion_or_retry_authority(field, value):
    with pytest.raises(ValueError):
        recovery.validate_policy({**policy(), field: value})


def test_only_unallocated_headroom_refusal_can_be_deferred(tmp_path):
    task, attempt = job(tmp_path), tmp_path / "attempt"
    attempt.mkdir()
    (attempt / "controller.log").write_text("traceback\n" + recovery.HEADROOM_ERROR + "\n")
    assert recovery.headroom_only(task, attempt, 1)
    assert not recovery.headroom_only(task, attempt, 0)
    assert not recovery.headroom_only({**task, "args": ["resume-arm"]}, attempt, 1)
    assert not recovery.headroom_only({**task, "module": "v9_final_evaluation"}, attempt, 1)
    recovery.arm_root(task).mkdir()
    assert not recovery.headroom_only(task, attempt, 1)  # Any real work refuses retry.


@pytest.mark.parametrize(
    "error",
    [
        "torch.OutOfMemoryError: CUDA out of memory",
        "ValueError: replayed probabilities differ from actual sampling receipts",
        "ValueError: infrastructure/reference unknown cannot become zero reward",
    ],
)
def test_oom_replay_and_scoring_are_never_resource_deferrals(tmp_path, error):
    (tmp_path / "controller.log").write_text(error)
    assert not recovery.headroom_only(job(tmp_path), tmp_path, 1)


def observed(tmp_path):
    child = dict(pid=11, birth="birth11", attempt=str(tmp_path), job_key="arm-11-full")
    parent = dict(pid=10, process_start_time_ticks="birth10")
    return recovery.AdoptedProcess(child, parent)


def test_live_adoption_does_not_start_or_signal_process(monkeypatch, tmp_path):
    item = observed(tmp_path)
    monkeypatch.setattr(recovery, "identity", lambda pid: "birth11")
    monkeypatch.setattr(recovery.subprocess, "Popen", lambda *a, **kw: pytest.fail("no relaunch"))
    monkeypatch.setattr(recovery.os, "kill", lambda *a: pytest.fail("no signal"))
    assert item.poll() is None


def test_adoption_waits_for_original_reaper(monkeypatch, tmp_path):
    item = observed(tmp_path)
    monkeypatch.setattr(recovery, "identity", lambda pid: "birth10" if pid == 10 else None)
    assert item.poll() is None


@pytest.mark.parametrize("code", [0, 1])
def test_adoption_consumes_real_original_exit(monkeypatch, tmp_path, code):
    item = observed(tmp_path)
    (tmp_path / "exit").mkdir()
    (tmp_path / "exit/record.json").write_text("{}")
    monkeypatch.setattr(recovery, "identity", lambda pid: None)
    monkeypatch.setattr(
        recovery, "checked", lambda p: dict(pid=11, key="arm-11-full", exit_code=code)
    )
    assert item.poll() == code


def test_missing_exit_and_dead_parent_cannot_be_inferred_success(monkeypatch, tmp_path):
    monkeypatch.setattr(recovery, "identity", lambda pid: None)
    with pytest.raises(ValueError, match="never infer success"):
        observed(tmp_path).poll()


def test_pid_reuse_cannot_be_adopted_as_the_original(monkeypatch, tmp_path):
    monkeypatch.setattr(recovery, "identity", lambda pid: "different-birth")
    with pytest.raises(ValueError):
        observed(tmp_path).poll()


def bare_controller(tmp_path):
    ctl = recovery.Supervisor.__new__(recovery.Supervisor)
    ctl.root, ctl.output, ctl.frozen = tmp_path / "recovery", tmp_path, tmp_path / "frozen"
    ctl.children, ctl.stop, ctl.max_gpu_workers = {}, False, 4
    ctl.plan, ctl.recovery = dict(id="original"), dict(id="recovery")
    ctl.guard_old_dispatch = lambda: None
    ctl.update = lambda *a, **kw: None
    return ctl


def test_new_workers_keep_original_runtime_and_four_gpu_limit(monkeypatch, tmp_path):
    ctl = bare_controller(tmp_path)
    calls = []
    monkeypatch.setattr(
        recovery.subprocess,
        "Popen",
        lambda cmd, **kw: calls.append((cmd, kw)) or SimpleNamespace(pid=22),
    )
    monkeypatch.setattr(recovery, "identity", lambda pid: "birth22")
    ctl.launch(job(tmp_path), gpu=6)
    assert len(calls) == 1
    assert calls[0][1]["cwd"] == ctl.frozen
    assert calls[0][1]["env"]["PYTHONPATH"] == str(ctl.frozen / "trusted_data_synthesis/src")
    assert calls[0][0][-2:] == ["--gpu", "6"]
    with pytest.raises(ValueError):
        ctl.launch(job(tmp_path, "not-started"), gpu=0)
    assert len(calls) == 1


def test_four_adopted_workers_count_toward_limit_and_are_not_requeued(monkeypatch, tmp_path):
    ctl = bare_controller(tmp_path)
    tasks = [job(tmp_path, f"job{i}") for i in range(15)]
    ctl.children = {
        t["key"]: dict(job=t, adopted=True, gpu=g)
        for t, g in zip(tasks[:4], recovery.GPUS, strict=True)
    }
    launched, snapshots = [], []
    ctl.reap_recovery = lambda: ([], [])
    ctl.update = lambda phase, **kw: snapshots.append(kw)
    monkeypatch.setattr(recovery, "marker_complete", lambda p: False)
    monkeypatch.setattr(
        recovery, "gpu_inventory", lambda: [dict(index=i, free=90000) for i in range(8)]
    )

    def stop_after_first_poll(seconds):
        ctl.stop = True
        ctl.children.clear()

    monkeypatch.setattr(recovery.time, "sleep", stop_after_first_poll)
    ctl.launch = lambda task, gpu: launched.append((task["key"], gpu))
    assert ctl.gpu_queue(tasks, recovery.GPUS) is False
    assert not launched
    assert snapshots[0]["queued"] == [t["key"] for t in tasks[4:]]
    assert len(snapshots[0]["adopted_live_workers"]) == 4


def test_available_slots_automatically_fill_only_authorized_gpus(monkeypatch, tmp_path):
    ctl = bare_controller(tmp_path)
    tasks = [job(tmp_path, f"job{i}") for i in range(3)]
    ctl.children = {"existing": dict(adopted=True, gpu=1)}
    ctl.reap_recovery = lambda: ([], [])
    monkeypatch.setattr(recovery, "marker_complete", lambda p: False)
    monkeypatch.setattr(
        recovery, "gpu_inventory", lambda: [dict(index=i, free=90000) for i in range(8)]
    )
    launched = []

    def launch(task, gpu):
        launched.append((task["key"], gpu))
        ctl.children[task["key"]] = dict(adopted=False, gpu=gpu)

    def stop_after_first_poll(seconds):
        ctl.stop = True
        ctl.children.clear()

    ctl.launch = launch
    monkeypatch.setattr(recovery.time, "sleep", stop_after_first_poll)
    assert ctl.gpu_queue(tasks, recovery.GPUS) is False
    assert [g for _, g in launched] == [2, 3, 6]


def test_runtime_failure_stops_new_admission(monkeypatch, tmp_path):
    ctl = bare_controller(tmp_path)
    ctl.reap_recovery = lambda: ([dict(kind="replay_mismatch")], [])
    ctl.launch = lambda *a, **kw: pytest.fail("no retry after real failure")
    monkeypatch.setattr(recovery, "marker_complete", lambda p: False)
    assert ctl.gpu_queue([job(tmp_path)], recovery.GPUS) is False


@pytest.mark.parametrize("adopted", [False, True])
def test_reaper_defers_only_own_unallocated_attempts(monkeypatch, tmp_path, adopted):
    ctl = bare_controller(tmp_path)
    task = job(tmp_path)
    ctl.children = {
        task["key"]: dict(
            process=SimpleNamespace(poll=lambda: 1),
            adopted=adopted,
            pid=23,
            job=task,
            attempt=str(tmp_path / "attempt"),
            gpu=2,
        )
    }
    monkeypatch.setattr(recovery, "headroom_only", lambda *a: True)
    failures, deferred = ctl.reap_recovery()
    assert not ctl.children
    if adopted:
        assert len(failures) == 1 and not deferred
    else:
        assert not failures and deferred == [task]


def test_downstream_mainline_remains_the_original_implementation():
    assert (
        recovery.Supervisor.run_remaining_mainline
        is recovery.OriginalSupervisor.run_remaining_mainline
    )
    ctl = recovery.Supervisor.__new__(recovery.Supervisor)
    tasks = ctl.arm_jobs(Path("synthetic-absent-launcher"))
    assert len(tasks) == 15
    remaining = [t["key"] for t in tasks if t["key"] not in recovery.LIVE_KEYS]
    assert remaining[:2] == ["arm-29-full", "arm-47-full"]
    assert len(remaining) == 11
