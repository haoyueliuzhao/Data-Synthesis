"""CPU/mock controls for V56 resource deferral and actual durable restart scope."""

import errno
import fcntl
import os
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import finqa_v56_runtime as runtime
import finqa_v56_worker as worker
from test_finance_v54_runtime import FakeCuda


@pytest.fixture
def env(tmp_path, monkeypatch):
    gib = runtime.GIB
    leases = tmp_path / "leases"
    leases.mkdir()
    lease = (leases / ("gpu-" + runtime.digest(runtime.GPU_UUIDS["0"]) + ".lock")).open("a")
    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    runtime.publish(tmp_path / "protocol/record.json", dict(resource_policy=runtime.resource_policy(),
        resource_recovery_policy=runtime.resource_recovery_policy(), allowed_gpu_indices=list(range(8)),
        gpu_uuids=runtime.GPU_UUIDS, gpu_lease_root=str(leases)))
    job = dict(id="seed137.train_Hold", job_id="seed137.train_Hold", seed=137, stage="train_Hold", kind="train")
    cuda, clock = FakeCuda(), {"now": 100.0}
    cuda.empty_calls = 0
    def empty():
        cuda.empty_calls += 1
    cuda.empty_cache = empty
    host = dict(available_bytes=512 * gib)
    process = dict(rss_bytes=2*gib, peak_rss_bytes=3*gib)
    row = dict(index=0, uuid=runtime.GPU_UUIDS["0"], free_mib=70*1024)
    monkeypatch.setattr(runtime, "inventory", lambda: [dict(row)])
    monkeypatch.setattr(runtime.original, "host_memory", lambda: dict(host))
    monkeypatch.setattr(runtime.original, "process_memory", lambda pid: dict(process))
    monkeypatch.setattr(runtime.original, "birth", lambda pid: "birth")
    monkeypatch.setattr(runtime.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(runtime.time, "sleep", lambda seconds: clock.update(now=clock["now"]+seconds))
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", runtime.GPU_UUIDS["0"])
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    monkeypatch.setenv("V54_GPU_LEASE_FD", str(lease.fileno()))
    monkeypatch.setenv("V54_JOB_ID", job["id"])
    guard = runtime.ResourceGuard(tmp_path, job, 0, torch_module=SimpleNamespace(cuda=cuda))
    yield SimpleNamespace(root=tmp_path, job=job, guard=guard, cuda=cuda, clock=clock,
                          host=host, process=process, row=row, lease=lease)
    if not guard._events.closed:
        guard._finish()
    lease.close()


def test_boundary_cleanup_rechecks_actual_free_and_keeps_failed_preflight(env):
    f = env
    with f.guard:
        f.cuda.peak, f.cuda.free = 60*runtime.GIB, runtime.GIB
        def free_own_cache():
            f.cuda.empty_calls += 1
            f.cuda.free = 4*runtime.GIB
        f.cuda.empty_cache = free_own_cache
        observed = f.guard.check("before_actual_call")
        assert observed["passed"] and observed["free_bytes"] == 4*runtime.GIB
        assert f.guard.preflight_observations[0]["passed"] is False
        assert f.guard.preflight_observations[0]["accepted_scientific_boundary"] is False
        assert f.cuda.peak == 60*runtime.GIB and f.cuda.resets == 1
        assert f.cuda.empty_calls == 1
    assert f.guard.report()["all_gates_passed"]


def test_persistent_shortage_yields_after60_and_preserves_closed_evidence(env):
    f = env
    with pytest.raises(runtime.ResourceDeferred):
        with f.guard:
            f.cuda.free = runtime.GIB
            f.guard.check("before_actual_call")
    closed = runtime.checked(f.guard.directory / "closeout/record.json")
    assert closed["resources"]["resource_wait_seconds"] == 60.0
    assert closed["resources"]["deferred_observation"]["free_bytes"] == runtime.GIB
    assert not closed["resources"]["all_gates_passed"]
    assert f.cuda.resets == 1 and f.cuda.empty_calls == 1


def test_pre_cuda_shortage_yields_before_model_and_has_discoverable_closeout(env):
    f = env
    f.row["free_mib"] = 10 * 1024
    with pytest.raises(runtime.ResourceDeferred) as captured:
        with f.guard:
            pytest.fail("capacity is not sufficient")
    assert not f.cuda.initialized and f.cuda.resets == 0
    attempt = f.root / "stages/seed137/train_Hold/attempts/attempt0001"
    record = worker.record_attempt_failure(f.root, f.job, attempt, captured.value)
    assert record["resource_closeout"] and record["resources"]["resource_wait_seconds"] == 60.0


def test_host_pressure_during_preflight_wait_does_not_clear_or_create_hard_peak_violation(env):
    f = env
    with f.guard:
        f.guard._capacity_wait_active = True
        f.host["available_bytes"] = 95 * runtime.GIB
        assert f.guard._observe_host_capacity() is True and f.guard.violation is None
        assert f.guard.preflight_observations[-1]["accepted_scientific_boundary"] is False
        f.host["available_bytes"] = 100 * runtime.GIB
        f.guard._capacity_wait_active = False
        f.guard.check("before_actual_call")
    assert f.guard.report()["all_gates_passed"]


def test_lifetime_peak_failure_cannot_be_recovered_by_empty_cache(env):
    f = env
    with pytest.raises(runtime.LifetimeResourceFailure):
        with f.guard:
            f.cuda.peak, f.cuda.allocated = 77 * runtime.GIB, runtime.GIB
            f.guard.check("after_release", boundary=False)
    assert f.cuda.empty_calls == 0 and f.cuda.resets == 1
    assert f.guard.report()["observed_violation"]["peak_allocated_bytes"] == 77 * runtime.GIB


def test_R3_still_requires_physical_free_for_KV_despite_large_own_cache(env, monkeypatch):
    f = env
    monkeypatch.setitem(sys.modules, "finqa_v32_replay_variants",
                        SimpleNamespace(estimate_complete_kv_bytes=lambda *args: runtime.GIB))
    session = SimpleNamespace(full_kv_budget_bytes=8*runtime.GIB,
        bank=SimpleNamespace(resident_limit=2*runtime.GIB, activation_resident_limit=16*runtime.GIB))
    with pytest.raises(runtime.R3CapacityError):
        with f.guard:
            f.cuda.free = 4 * runtime.GIB
            f.cuda.reserved = 30 * runtime.GIB
            f.guard.prepare_replay_response(session, object(), 100, 100)
    observed = f.guard.report()["deferred_observation"]
    assert observed["required_free_bytes"] == 5*runtime.GIB
    assert observed["required_own_available_bytes"] == 21*runtime.GIB
    assert observed["own_available_bytes"] >= observed["required_own_available_bytes"]
    assert observed["free_bytes"] < observed["required_free_bytes"]


def test_original_R3_failed_after_response_snapshot_cannot_be_reclassified_by_later_free(env):
    f = env
    with pytest.raises(runtime.R3CapacityError):
        with f.guard:
            f.guard.check("replay.after_response", response_backend_observation=dict(
                phase="after_response", torch_peak_allocated_bytes=50*runtime.GIB,
                device_free_bytes_at_response_boundary=runtime.GIB))
    assert f.cuda.free == 70 * runtime.GIB
    assert f.cuda.empty_calls == 0
    assert f.guard.report()["deferred_observation"]["free_bytes"] == runtime.GIB
    assert not f.guard.report()["all_gates_passed"]


def test_overlay_reads_old_complete_task_and_never_recomputes_or_rebinds_it(monkeypatch):
    plan = dict(id="plan", task_ids=["old", "new"])
    reads, commits = [], []
    def cache(name):
        return SimpleNamespace(plan=plan, binding={"source": name}, root=Path(name), parameter_spec=[],
            directory=lambda task: Path("absent") / task, has=lambda task: True,
            read=lambda task: reads.append((name, task)) or {"z": {"w": name}},
            commit=lambda task, values, receipt=None: commits.append((name, task)),
            task=lambda task: task)
    new, old = cache("new"), cache("old")
    monkeypatch.setattr(worker.training.task_cache, "TaskCache", lambda *a: old)
    parent = dict(parent_state_digest="state", component_digests={"rng": "same"}, point_id="point", parameter_spec=[])
    inherited = dict(parent, task_plan={"id": "plan"}, original_task_cache_root="old",
                     tasks=[dict(task_id="old", binding={"source": "old"})])
    rt = SimpleNamespace(v8=SimpleNamespace(_DeviceGradients=lambda values, device: values))
    overlay = worker.TaskCacheOverlay(new, inherited, parent, rt)
    assert list(overlay.assemble()) == ["old", "new"]
    assert reads == [("old", "old"), ("new", "new")]
    with pytest.raises(ValueError, match="cannot be recomputed"):
        overlay.commit("old", {})
    overlay.commit("new", {})
    assert commits == [("new", "new")]


def _audit(monkeypatch, *, unknown=0):
    monkeypatch.setattr(worker, "audit_job_resume", lambda root, job: dict(
        unknown_calls=unknown, resume_allowed=unknown == 0, progress_units=9,
        durable_progress_digest="actual-nine-tasks", evidence=[]))


def test_classification_requires_actual_capacity_evidence_and_no_unknown(env, monkeypatch):
    f = env
    _audit(monkeypatch)
    with pytest.raises(runtime.ResourceDeferred) as error:
        with f.guard:
            f.cuda.free = runtime.GIB
            f.guard.check("before_actual_call")
    attempt = f.root / "stages/seed137/train_Hold/attempts/attempt0001"
    worker.record_attempt_failure(f.root, f.job, attempt, error.value, guard=f.guard)
    assert worker.classify_attempt(f.root, f.job, attempt, 1)["classification"] == "RETRY_SAFE_RESOURCE"
    _audit(monkeypatch, unknown=1)
    assert worker.classify_attempt(f.root, f.job, attempt, 1)["classification"] == "HARD_BLOCK"


def test_self_hard_peak_and_stop_are_not_automatic_resource_retries(env, monkeypatch):
    f = env
    _audit(monkeypatch)
    with pytest.raises(runtime.LifetimeResourceFailure) as error:
        with f.guard:
            f.cuda.peak = 77 * runtime.GIB
            f.guard.check("model_failure")
    attempt = f.root / "stages/seed137/train_Hold/attempts/attempt0001"
    worker.record_attempt_failure(f.root, f.job, attempt, error.value, guard=f.guard)
    assert worker.classify_attempt(f.root, f.job, attempt, 1)["classification"] == "HARD_BLOCK"
    assert worker.classify_attempt(f.root, f.job, attempt, -signal.SIGTERM)["classification"] == "EXPLICIT_STOP"


def test_transient_audit_IO_wait_never_authorizes_science(env, monkeypatch):
    f = env
    attempt = f.root / "stages/seed137/train_Hold/attempts/attempt0001"
    worker.record_attempt_failure(f.root, f.job, attempt, OSError(errno.EIO, "actual temporary read failure"))
    def unreadable(*args):
        raise OSError(errno.ESTALE, "actual stale evidence read")
    monkeypatch.setattr(worker, "audit_job_resume", unreadable)
    result = worker.classify_attempt(f.root, f.job, attempt, 1)
    assert result["classification"] == "AUDIT_IO_WAIT" and result["actual_errno"] == errno.ESTALE
    assert result["resume_allowed"] is False and result["evidence"]


def test_message_text_alone_cannot_claim_cuda_OOM(env, monkeypatch):
    f = env
    _audit(monkeypatch)
    attempt = f.root / "stages/seed137/train_Hold/attempts/attempt0001"
    worker.record_attempt_failure(f.root, f.job, attempt, ValueError("CUDA out of memory"))
    assert worker.classify_attempt(f.root, f.job, attempt, 1)["classification"] == "HARD_BLOCK"


def test_evaluation_audit_inspects_actual_nested_generation_journals(env, monkeypatch):
    f = env
    runtime.publish(f.root / "evaluations/registration/record.json", dict(schema="CPU_fixture"))
    seen = []
    def audit(path, inheritance=None):
        seen.append(path)
        return dict(resume_allowed=False, unknown_calls=1, progress_units=0,
                    durable_progress_digest="actual-unreturned-intent", evidence=[])
    monkeypatch.setitem(sys.modules, "finqa_v56_feedback", SimpleNamespace(audit_resume=audit))
    job = dict(job_id="eval137", id="eval137", seed=137, stage="generate", kind="generate", panel="dev")
    result = worker.audit_job_resume(f.root, job)
    assert seen == [f.root / "evaluations/jobs/eval137/shards/dev/generation"]
    assert not result["resume_allowed"] and result["unknown_calls"] == 1
