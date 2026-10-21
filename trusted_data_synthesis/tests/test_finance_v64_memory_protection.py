"""CPU/mock protection checks; never initialize CUDA or run a model."""
from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import finqa_v64_runtime as runtime
import finqa_v64_worker as worker

GIB = runtime.GIB


class MockCuda:
    def __init__(self):
        self.allocated = 28 * GIB
        self.reserved = 30 * GIB
        self.free = 49 * GIB
        self.peak = 32 * GIB
        self.peak_reserved = self.reserved
        self.empty_calls = 0
        self.allocations = []
        self.resets = 0
        self.after_allocate = lambda: None
        self.memory = SimpleNamespace(get_allocator_backend=lambda: "native")

    def synchronize(self):
        pass

    def mem_get_info(self):
        return self.free, 80 * GIB

    def memory_allocated(self):
        return self.allocated

    def memory_reserved(self):
        return self.reserved

    def max_memory_allocated(self):
        return self.peak

    def max_memory_reserved(self):
        return self.peak_reserved

    def empty_cache(self):
        self.empty_calls += 1
        self.free += self.reserved - self.allocated
        self.reserved = self.allocated

    def empty(self, amount, *, dtype, device):
        assert dtype == "uint8" and device == "cuda:0"
        self.allocations.append(amount)
        growth = max(0, amount - (self.reserved - self.allocated))
        self.reserved += growth
        self.free -= growth
        self.allocated += amount
        self.peak = max(self.peak, self.allocated)
        self.peak_reserved = max(self.peak_reserved, self.reserved)
        self.after_allocate()
        cuda = self

        class Tensor:
            def __del__(self):
                cuda.allocated -= amount

        return Tensor()


@pytest.fixture
def env(tmp_path, monkeypatch):
    guard = object.__new__(runtime.ResourceGuard)
    guard.kind = "replay"
    guard.job_id = "seed137.replay_C1"
    guard.job = dict(id=guard.job_id, job_id=guard.job_id, kind="replay", stage="replay_C1")
    guard.gpu, guard.violation = 0, None
    guard.stop = SimpleNamespace(requested=False, received_signals=[], reason=None)
    guard.protocol = {"id": "old-scientific-protocol"}
    guard.control_protocol = {"id": "new-control-protocol"}
    guard.directory = tmp_path / "science/resources" / guard.job_id / "pid123"
    guard.observations, guard.preflight_observations = [], []
    guard.deferred_observation, guard.wait_seconds = None, 0.0
    guard._reset, guard._capacity_wait_active = None, False
    guard._warm_attempted, guard._warm_allocation_bytes = False, 0
    guard._warm_status, guard._warm_receipt = "NOT_ATTEMPTED", None
    guard._cache_release_count, guard._cache_retained_wait_count = 0, 0
    guard._protection_events = []
    cuda = MockCuda()
    guard.torch = SimpleNamespace(cuda=cuda, empty=cuda.empty, uint8="uint8")
    guard._host = lambda: dict(rss_bytes=3*GIB, peak_rss_bytes=4*GIB,
        rss_limit_bytes=192*GIB, available_bytes=400*GIB,
        available_reserve_bytes=96*GIB, passed=True)
    events, receipts = [], []
    guard._record = lambda value: events.append(value)
    monkeypatch.setattr(runtime, "ROOT", tmp_path / "control")
    monkeypatch.setattr(runtime.binding, "publish", lambda path, body: receipts.append((path, body)))
    monkeypatch.setattr(runtime.binding, "entry", lambda path: dict(path=str(path), id="warm-receipt"))
    monkeypatch.setattr(runtime.reference.isolation, "probe_gpus", lambda uuids: {
        uuid: dict(gpu_uuid=uuid, allowed=True, process_count=1,
            known_processes=[dict(pid=123, birth="1", uids=[1004]*4)],
            unresolved_processes=[]) for uuid in uuids})
    clock = {"now": 0.0}
    monkeypatch.setattr(runtime._durable.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(runtime._durable.time, "sleep", lambda seconds: clock.update(now=clock["now"]+seconds))
    monkeypatch.setitem(sys.modules, "finqa_v32_replay_variants",
                        SimpleNamespace(estimate_complete_kv_bytes=lambda *args: GIB))
    session = SimpleNamespace(full_kv_budget_bytes=8*GIB,
        bank=SimpleNamespace(resident_limit=2*GIB, activation_resident_limit=16*GIB))
    return SimpleNamespace(guard=guard, cuda=cuda, events=events, receipts=receipts,
                           clock=clock, session=session)


@pytest.mark.parametrize("free,allocated,expected", [
    (50*GIB, 28*GIB, 16*GIB),
    (20*GIB, 28*GIB, 6*GIB),
    (14*GIB, 28*GIB, 0),
    (10*GIB, 28*GIB, 0),
    (14*GIB + 1024**2, 28*GIB, 0),
    (50*GIB, 75*GIB, GIB-runtime.WARM_PEAK_MARGIN_BYTES),
])
def test_plan_bounds_alignment_and_partial_zero(free, allocated, expected):
    assert runtime.planned_warm_bytes(free_bytes=free, allocated_bytes=allocated) == expected


def test_one_warm_uses_no_rng_or_model_call_and_counts_real_peak(env):
    e = env
    initial = e.cuda.allocated
    for _ in range(2):
        value = e.guard.prepare_replay_response(e.session, object(), 100, 100)
        assert value["passed"]
    assert e.cuda.allocations == [16*GIB]
    assert e.cuda.allocated == initial and e.cuda.peak == initial+16*GIB
    assert e.cuda.empty_calls == e.cuda.resets == 0
    assert len(e.receipts) == 1
    receipt = e.receipts[0][1]
    assert receipt["status"] == "FULL" and not receipt["live_warm_tensor_remaining"]
    assert receipt["model_or_rng_call"] is False
    assert receipt["extra_scientific_response"] is False
    report = e.guard.report()
    assert report["warm_allocation_bytes"] == 16*GIB
    assert report["inherited_pre_model_warm_allocation_bytes"] == 0
    assert report["peak_allocated_bytes"] == initial+16*GIB
    assert report["control_protocol_id"] == "new-control-protocol"


def test_partial_warm_is_explicit(env):
    e = env
    e.cuda.free = 20*GIB
    e.guard.prepare_replay_response(e.session, object(), 100, 100)
    assert e.cuda.allocations == [6*GIB]
    assert e.receipts[0][1]["status"] == "PARTIAL"


def test_zero_warm_does_not_raise_original_scientific_admission_threshold(env):
    e = env
    e.cuda.free, e.cuda.reserved = 13*GIB, 38*GIB
    value = e.guard.prepare_replay_response(e.session, object(), 100, 100)
    assert value["passed"] and value["free_bytes"] < runtime.WARM_RAW_FREE_BYTES
    assert not e.cuda.allocations
    assert e.receipts[0][1]["status"] == "ZERO"
    assert e.receipts[0][1]["planning_free_headroom_observed_after"] is False


def test_existing_lifetime_peak_failure_prevents_prewarm(env):
    e = env
    e.cuda.peak = 77*GIB
    with pytest.raises(runtime.LifetimeResourceFailure):
        e.guard._warm_replay_cache()
    assert not e.cuda.allocations and e.cuda.empty_calls == 0


def test_actual_warm_peak_violation_is_not_hidden_by_releasing_tensor(env):
    e = env
    e.cuda.after_allocate = lambda: setattr(e.cuda, "peak", 77*GIB)
    with pytest.raises(runtime.LifetimeResourceFailure):
        e.guard._warm_replay_cache()
    assert e.cuda.allocated == 28*GIB and e.cuda.peak == 77*GIB
    assert e.cuda.resets == e.cuda.empty_calls == 0
    assert e.guard.report()["resource_protection"]["status"] == "FAILED"
    assert not e.guard.report()["all_gates_passed"]


def test_original_raw_free_shortage_can_release_only_own_cache_and_recheck(env):
    e = env
    e.guard._warm_attempted = True
    e.cuda.free, e.cuda.reserved = 4*GIB, 58*GIB
    value = e.guard.prepare_replay_response(e.session, object(), 100, 100)
    assert value["passed"] and value["free_bytes"] >= 5*GIB
    assert e.cuda.empty_calls == 1 and e.cuda.resets == 0
    assert e.guard.preflight_observations[0]["passed"] is False
    assert e.guard.preflight_observations[0]["accepted_scientific_boundary"] is False
    assert e.guard.report()["resource_protection"]["protection_degraded"]


def test_own_capacity_shortage_keeps_cache_and_bounded_wait(env):
    e = env
    e.guard._warm_attempted = True
    e.cuda.free, e.cuda.reserved = 5*GIB, 29*GIB
    with pytest.raises(runtime.R3CapacityError):
        e.guard.prepare_replay_response(e.session, object(), 100, 100)
    assert e.cuda.empty_calls == 0 and e.clock["now"] == 60
    assert e.guard.report()["resource_protection"]["cache_retained_wait_count"] == 1
    assert e.guard.deferred_observation["required_free_bytes"] == 5*GIB
    assert e.guard.deferred_observation["required_own_available_bytes"] == 21*GIB


@pytest.mark.parametrize("during", [False, True])
def test_explicit_stop_prevents_science_before_or_after_warm(env, during):
    e = env
    if during:
        e.cuda.after_allocate = lambda: setattr(e.guard.stop, "requested", True)
    else:
        e.guard.stop.requested = True
    with pytest.raises(runtime.ExplicitStop):
        e.guard.prepare_replay_response(e.session, object(), 100, 100)
    assert e.cuda.allocations == ([16*GIB] if during else [])
    assert not any(v.get("label") == "before_actual_R3_response" for v in e.events)


def test_routine_cleanup_retains_cache_but_runs_original_gates(env):
    e = env
    result = runtime.ScientificMonitor(e.guard).clear_unused("committed_step")
    assert result["routine_allocator_cache_retained"]
    assert result["after"]["passed"] and result["after"]["boundary"]
    assert e.cuda.empty_calls == 0


def test_failed_original_after_response_cannot_be_relabelled_by_current_capacity(env):
    e = env
    with pytest.raises(runtime.R3CapacityError):
        e.guard.check("after_response", response_backend_observation=dict(
            phase="after_response", torch_peak_allocated_bytes=34*GIB,
            device_free_bytes_at_response_boundary=GIB))
    assert e.cuda.empty_calls == 0 and not e.cuda.allocations
    assert e.guard.deferred_observation["free_bytes"] == GIB


def test_private_bindings_do_not_modify_original_resource_or_worker_functions():
    assert runtime.ResourceGuard.ensure_capacity is not runtime.reference.ResourceGuard.ensure_capacity
    assert "_capacity_cleanup" in runtime.ResourceGuard.ensure_capacity.__code__.co_names
    assert "empty_cache" in runtime.reference.ResourceGuard.ensure_capacity.__code__.co_names
    assert "empty_cache" in runtime.reference_worker.ScientificMonitor.clear_unused.__code__.co_names
    assert worker._worker is not runtime.reference_worker
    assert worker._worker.ScientificMonitor is runtime.ScientificMonitor
    assert runtime.reference.MINIMUM_FREE_GIB["replay"] == 56
    assert runtime.reference.resource_policy()["max_gpu_workers"] == 6


def test_worker_entry_delegates_original_science_arguments(monkeypatch):
    calls = []
    monkeypatch.setattr(worker._worker, "run", lambda *a, **kw: calls.append((a, kw)) or "ok")
    assert worker.run(Path("science"), 137, "replay_C1", 7, attempt_root=Path("attempt")) == "ok"
    assert calls == [((Path("science"), 137, "replay_C1", 7), {"attempt_root": Path("attempt")})]
