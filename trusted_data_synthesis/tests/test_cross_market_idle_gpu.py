"""Idle-only resource admission; CPU mocks, no real GPU or model execution."""

import pytest
import run_cross_market_idle_gpu_20260927 as m


def gpu(uuid="GPU-idle-2", **changes):
    row = dict(
        index=2,
        uuid=uuid,
        used_MiB=0,
        free_MiB=81920,
        utilization_percent=0,
        processes=[],
    )
    row.update(changes)
    return row


def changed_gpu(**changes):
    row = gpu()
    row.update(changes)
    return row


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({}, True),
        ({"free_MiB": 49152, "used_MiB": 1024, "utilization_percent": 5}, True),
        ({"free_MiB": 49151}, False),
        ({"used_MiB": 1025}, False),
        ({"utilization_percent": 6}, False),
        ({"processes": [98765]}, False),
    ],
)
def test_idle_requires_all_thresholds_and_no_existing_compute_process(changes, expected):
    assert m.is_idle(changed_gpu(**changes)) is expected


def test_worker_own_pid_can_be_ignored_but_another_process_cannot():
    assert m.is_idle(changed_gpu(processes=[12345]), own_pid=12345) is True
    assert m.is_idle(changed_gpu(processes=[12345, 98765]), own_pid=12345) is False
    assert m.is_idle(changed_gpu(processes=[12345])) is False


def test_admission_requires_two_observations_at_least_twenty_seconds_apart():
    clock, rows = [0.0], [gpu()]
    admission = m.IdleAdmission([rows[0]["uuid"]], observe=lambda: rows, clock=lambda: clock[0])
    assert admission(49152) == []
    clock[0] = 19.9
    assert admission(49152) == []
    clock[0] = 20.0
    assert admission(49152) == [rows[0]["uuid"]]
    # No unchanged scientific threshold can be silently lowered by the caller.
    clock[0] = 40.0
    assert admission(49152) == [rows[0]["uuid"]]


@pytest.mark.parametrize(
    "busy",
    [
        {"processes": [98765]},
        {"free_MiB": 49151},
        {"used_MiB": 1025},
        {"utilization_percent": 6},
    ],
)
def test_any_busy_observation_resets_the_continuous_idle_timer(busy):
    clock, rows = [0.0], [gpu()]
    admission = m.IdleAdmission([rows[0]["uuid"]], observe=lambda: rows, clock=lambda: clock[0])
    assert admission(49152) == []
    clock[0] = 19.0
    rows[:] = [changed_gpu(**busy)]
    assert admission(49152) == []
    clock[0] = 20.0
    rows[:] = [gpu()]
    assert admission(49152) == []
    clock[0] = 39.9
    assert admission(49152) == []
    clock[0] = 40.0
    assert admission(49152) == [rows[0]["uuid"]]


def test_disappeared_gpu_and_unregistered_gpu_are_not_admitted():
    clock, rows = [0.0], [gpu()]
    admission = m.IdleAdmission([rows[0]["uuid"]], observe=lambda: rows, clock=lambda: clock[0])
    assert admission(49152) == []
    clock[0] = 20.0
    rows[:] = [gpu("GPU-not-authorized")]
    assert admission(49152) == []
    clock[0] = 21.0
    rows[:] = [gpu()]
    assert admission(49152) == []
    clock[0] = 41.0
    assert admission(49152) == [rows[0]["uuid"]]


def plans():
    retry = m.retry
    parent = dict(
        target_job_id="synthetic-authorized-job-id",
        gpu_allocation=dict(
            allowed_gpu_uuids=["GPU-0", "GPU-1", "GPU-6", "GPU-7"],
            max_GPU_workers=4,
        ),
        coordinator_binding=retry.coordinate_with_extra_attempts(
            dict(vars(m.previous)), "synthetic-authorized-job-id"
        ).authorized_retry_binding,
    )
    return (
        dict(id="synthetic-idle", allowed_gpu_uuids=[f"GPU-{i}" for i in range(8)]),
        parent,
        dict(id="synthetic-performance", logprob_optimization=dict(enabled=False)),
        dict(id="synthetic-cuda", allowed_failures=[]),
    )


def test_overlay_preserves_registered_retry_barrier_and_worker_code():
    idle, parent, perf, recovered = plans()
    namespace = m.controller_namespace(idle, parent, perf, recovered)
    assert namespace["SCRIPT"] == m.SCRIPT
    assert namespace["worker"].__code__ is m.previous.worker.__code__
    assert namespace["coordinate"].authorized_retry_binding == parent["coordinator_binding"]
    assert namespace["launch"].__globals__ is namespace
    assert namespace["os"].environ["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"
    assert issubclass(namespace["evaluation"].Context, m.performance.PerformanceContext)
    assert (
        namespace["_authorized_attempt_cap"](
            dict(id=parent["target_job_id"], key=m.retry.TARGET, work_kind="generate"), 4
        )
        == 6
    )
    assert (
        namespace["_authorized_attempt_cap"](dict(id="other", key="other", work_kind="generate"), 4)
        == 4
    )
    assert (
        namespace["_authorized_attempt_cap"](dict(id="score", key="score", work_kind="score"), 2)
        == 2
    )


def test_parent_active_worker_tracking_is_retained_without_duplicate_launch(monkeypatch):
    idle, parent, perf, recovered = plans()
    original = m.retry.controller_namespace(parent, perf, recovered)
    attempts, launch, coordinate = original["attempts"], original["launch"], original["coordinate"]
    seen = []

    def inherit(*args):
        seen.append(args)
        return original

    monkeypatch.setattr(m.retry, "controller_namespace", inherit)
    namespace = m.controller_namespace(idle, parent, perf, recovered)
    assert seen == [(parent, perf, recovered)]
    assert namespace is original
    assert namespace["attempts"] is attempts
    assert namespace["launch"] is launch
    assert namespace["coordinate"] is coordinate


def test_first_boundary_rechecks_idle_then_retains_original_capacity_policy(tmp_path, monkeypatch):
    idle, parent, perf, recovered = plans()
    observations, boundaries = [], []
    rows = [gpu("GPU-2")]

    def observe():
        observations.append(True)
        return rows

    monkeypatch.setattr(m, "read_gpu_snapshot", observe)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-2")

    def boundary(self, *args):
        boundaries.append(args)
        self._capacity_checks += 1

    monkeypatch.setattr(
        m.performance.PerformanceContext,
        "capacity_boundary",
        boundary,
    )
    context = m.controller_namespace(idle, parent, perf, recovered)["evaluation"].Context(tmp_path)
    context.capacity_boundary("generation", 49152)
    rows[0]["processes"] = [98765]
    context.capacity_boundary("generation", 49152)
    assert len(observations) == 1
    assert boundaries == [("generation", 49152)] * 2


def test_start_race_is_original_resource_retry_before_model_loading(tmp_path, monkeypatch):
    idle, parent, perf, recovered = plans()
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-2")
    monkeypatch.setattr(m, "read_gpu_snapshot", lambda: [gpu("GPU-2", processes=[98765])])
    boundaries = []
    monkeypatch.setattr(
        m.performance.PerformanceContext,
        "capacity_boundary",
        lambda self, *args: boundaries.append(args),
    )
    context = m.controller_namespace(idle, parent, perf, recovered)["evaluation"].Context(tmp_path)
    with pytest.raises(m.previous.legacy.CapacityWait):
        context.capacity_boundary("generation", 49152)
    assert boundaries == []


@pytest.mark.parametrize("attempt,accepted", [(5, True), (6, True), (7, False)])
def test_worker_validation_keeps_exact_authorized_retry_cap(monkeypatch, attempt, accepted):
    idle, parent, _, _ = plans()
    job = dict(id=parent["target_job_id"], key=m.retry.TARGET, work_kind="generate")
    original = dict(scheduling=dict(generation_attempts_per_shard=4, scoring_attempts_per_cohort=2))
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-2")
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    if accepted:
        m.validate_worker(job, attempt, idle, original, parent)
    else:
        with pytest.raises(ValueError):
            m.validate_worker(job, attempt, idle, original, parent)


def test_worker_rejects_unregistered_device_and_wrong_cuda_env(monkeypatch):
    idle, parent, _, _ = plans()
    job = dict(id="other", key="other", work_kind="generate")
    original = dict(scheduling=dict(generation_attempts_per_shard=4, scoring_attempts_per_cohort=2))
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-not-in-pool")
    with pytest.raises(ValueError):
        m.validate_worker(job, 1, idle, original, parent)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-2")
    monkeypatch.delenv("CUBLAS_WORKSPACE_CONFIG", raising=False)
    with pytest.raises(ValueError):
        m.validate_worker(job, 1, idle, original, parent)


def test_cpu_scoring_still_uses_original_attempt_cap(monkeypatch):
    idle, parent, _, _ = plans()
    job = dict(id="score", key="score", work_kind="score")
    original = dict(scheduling=dict(generation_attempts_per_shard=4, scoring_attempts_per_cohort=2))
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    m.validate_worker(job, 2, idle, original, parent)
    with pytest.raises(ValueError):
        m.validate_worker(job, 3, idle, original, parent)
