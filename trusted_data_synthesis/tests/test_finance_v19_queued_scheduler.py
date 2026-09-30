"""No-process/no-GPU queue controls for deferred validation and cold restoration."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
queue = importlib.import_module("finqa_v19_queued_scheduler")


def bare(tmp_path):
    ctl = queue.Supervisor.__new__(queue.Supervisor)
    ctl.profile_root = tmp_path
    ctl.profile = {
        "id": "profile",
        "validation": {"required_completed_outer": str(tmp_path / "outer")},
    }
    ctl.children = {}
    ctl.stop = False
    ctl.recover_active = lambda jobs: None
    ctl.guard_old_dispatch = lambda: None
    ctl.update = lambda *args, **kw: None
    return ctl


def job(tmp_path, key="plain"):
    return dict(
        key=key,
        module="v16_arm_training",
        args=["run-arm"],
        result=tmp_path / key / "result/record.json",
    )


def test_original_fifteen_jobs_only_change_two_pending_full_execution_routes(tmp_path):
    ctl = bare(tmp_path)
    jobs = ctl.arm_jobs(tmp_path / "launcher")
    assert len(jobs) == 15
    changed = [j for j in jobs if j.get("script")]
    assert [j["key"] for j in changed] == ["arm-29-full", "arm-47-full"]
    assert all(j["requires_validation"] for j in changed)
    assert all(j["key"] not in queue.previous.LIVE_KEYS for j in changed)
    assert ctl.run_remaining_mainline.__func__ is queue.previous.Supervisor.run_remaining_mainline


def test_cuda_gate_waits_for_the_original_completed_outer(tmp_path):
    ctl = bare(tmp_path)
    gate = ctl.validation_job()
    assert not ctl.eligible_job(gate)
    (tmp_path / "outer").mkdir()
    (tmp_path / "outer/record.json").write_text("{}")
    (tmp_path / "outer/outer_inputs.pt").write_bytes(b"synthetic")
    assert ctl.eligible_job(gate)


def test_optimized_work_waits_for_actual_acceptance_and_plain_work_does_not(tmp_path, monkeypatch):
    ctl = bare(tmp_path)
    optimized = {**job(tmp_path), "requires_validation": True}
    assert not ctl.eligible_job(optimized)
    assert ctl.eligible_job(job(tmp_path))
    (tmp_path / "validation/result").mkdir(parents=True)
    (tmp_path / "validation/result/record.json").write_text("{}")
    monkeypatch.setattr(
        queue, "admitted_validation", lambda *a: (_ for _ in ()).throw(ValueError("not admitted"))
    )
    with pytest.raises(ValueError):
        ctl.eligible_job(optimized)


def test_four_live_protected_workers_keep_all_new_jobs_waiting(monkeypatch, tmp_path):
    ctl = bare(tmp_path)
    tasks = [job(tmp_path, f"pending{i}") for i in range(11)]
    ctl.children = {f"original{i}": dict(gpu=g, protected=True) for i, g in enumerate(queue.GPUS)}
    ctl.reap_profiled = lambda: ([], [])
    ctl.job_complete = lambda j: False
    ctl.launch = lambda *a, **kw: pytest.fail("no spare GPU slot")
    monkeypatch.setattr(
        queue, "gpu_inventory", lambda: [dict(index=i, free=90000) for i in range(8)]
    )

    def stop(_seconds):
        ctl.children.clear()
        ctl.stop = True

    monkeypatch.setattr(queue.time, "sleep", stop)
    assert ctl.gpu_queue(tasks, queue.GPUS) is False


def test_gate_priority_but_no_optimized_worker_bypasses_it(monkeypatch, tmp_path):
    ctl = bare(tmp_path)
    ctl.children = {"old": dict(gpu=1, protected=True)}
    ctl.reap_profiled = lambda: ([], [])
    ctl.job_complete = lambda j: False
    ctl.eligible_job = lambda j: not j.get("requires_validation")
    tasks = [{**job(tmp_path, "arm-29-full"), "requires_validation": True}, job(tmp_path, "static")]
    launched = []

    def launch(task, gpu):
        launched.append((task["key"], gpu))
        ctl.children[task["key"]] = dict(gpu=gpu, protected=False)

    ctl.launch = launch
    monkeypatch.setattr(
        queue, "gpu_inventory", lambda: [dict(index=i, free=90000) for i in range(8)]
    )

    def stop(_seconds):
        ctl.children.clear()
        ctl.stop = True

    monkeypatch.setattr(queue.time, "sleep", stop)
    assert ctl.gpu_queue(tasks, queue.GPUS) is False
    assert launched == [("replay-CUDA-equivalence-gate", 2), ("static", 3)]


def test_real_failure_never_auto_retries_or_signals_other_workers(monkeypatch, tmp_path):
    ctl = bare(tmp_path)
    ctl.reap_profiled = lambda: ([{"failure": "nonfinite"}], [])
    ctl.job_complete = lambda j: False
    ctl.launch = lambda *a, **kw: pytest.fail("no retry")
    monkeypatch.setattr(queue.os, "kill", lambda *a: pytest.fail("no Student signal"))
    assert ctl.gpu_queue([job(tmp_path)], queue.GPUS) is False


def test_cold_observation_retains_live_process_and_does_not_forge_exit_code(monkeypatch, tmp_path):
    launch = dict(pid=20, process_start_time_ticks="birth")
    proc = queue.DetachedProcess(launch, tmp_path, lambda: True)
    monkeypatch.setattr(queue, "identity", lambda pid: "birth")
    assert proc.poll() is None
    monkeypatch.setattr(queue, "identity", lambda pid: None)
    assert proc.poll() == 0 and proc.actual_exit_code is None
    assert proc.exit_code_source == "durable_final_result_without_OS_wait_status"


def test_unknown_exit_without_result_is_failure_not_success(monkeypatch, tmp_path):
    proc = queue.DetachedProcess(
        dict(pid=20, process_start_time_ticks="birth"), tmp_path, lambda: False
    )
    monkeypatch.setattr(queue, "identity", lambda pid: None)
    assert proc.poll() == 1 and proc.actual_exit_code is None


@pytest.mark.parametrize("contradiction", (None, "case_boolean", "gradient_digest"))
def test_admission_checks_each_case_not_only_summary(monkeypatch, tmp_path, contradiction):
    profile_module = importlib.import_module("finqa_v19_execution_profile")
    selected = {"synthetic_case": 1}
    profile = {
        "id": "profile",
        "validation": {"cases": [selected], "maximum_optimized_time_ratio": 1.05},
    }
    result = dict(
        execution_profile_id="profile",
        admitted=True,
        all_cases_bitwise_equal=True,
        production_CUDA_measured=True,
        saved_KV_residency_exercised=True,
        actual_point_model_RNG_buffers_unchanged=True,
        case_count=1,
        new_generation_calls=0,
        optimizer_steps=0,
        API_calls=0,
        optimized_over_baseline=1.0,
    )
    case = dict(
        execution_profile_id="profile",
        case=selected,
        logp_bitwise_equal=True,
        gradient_bitwise_equal=contradiction != "case_boolean",
        same_shape_dtype_keys=True,
        baseline_gradient_digest="exact",
        optimized_gradient_digest="wrong" if contradiction == "gradient_digest" else "exact",
    )
    monkeypatch.setattr(
        profile_module, "checked", lambda path: result if path.parent.name == "result" else case
    )
    if contradiction is None:
        assert profile_module.admitted_validation(tmp_path, profile) is result
    else:
        with pytest.raises(ValueError, match="contradictory CUDA case"):
            profile_module.admitted_validation(tmp_path, profile)
