"""Control-plane safety only: no real process signals, GPU work, or new evaluations."""

import importlib
import os
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
m = importlib.import_module("run_fixed_kernel_delayed_C_migration_20260921")


def test_signal_rejects_reused_PID_before_sending(monkeypatch):
    expected = dict(pid=1234, uid=os.getuid(), start_ticks=7, command=["our_worker"], state="S")
    monkeypatch.setattr(m, "identity", lambda pid: {**expected, "start_ticks": 8})
    sent = []
    monkeypatch.setattr(m.os, "kill", lambda pid, sig: sent.append((pid, sig)))
    with pytest.raises(ValueError, match="exact_owned_process"):
        m.signal_owned(expected, signal.SIGTERM)
    assert sent == []


def test_only_explicit_resource_sleep_is_a_migration_boundary():
    waiting = {"event": "waiting_for_GPU_headroom"}
    assert m.paused_boundary(waiting, "hrtimer_nanosleep")
    assert not m.paused_boundary(waiting, "futex_wait_queue")
    assert not m.paused_boundary(
        {"event": "real_optimizer_update_checkpointed"}, "hrtimer_nanosleep"
    )
    assert not m.paused_boundary(None, "hrtimer_nanosleep")


def test_target_reservation_enforces_capacity_and_shared_lease(monkeypatch, tmp_path):
    monkeypatch.setattr(
        m, "target_gpu", lambda index: dict(index=index, uuid="GPU-test", free_MiB=72000)
    )
    _, lease = m.reserve_target(tmp_path, 0)
    try:
        with pytest.raises(BlockingIOError):
            m.reserve_target(tmp_path, 0)
    finally:
        lease.close()
    monkeypatch.setattr(
        m, "target_gpu", lambda index: dict(index=index, uuid="GPU-test", free_MiB=61000)
    )
    with pytest.raises(ValueError, match="required_free_capacity"):
        m.reserve_target(tmp_path, 0)


def test_SFT_amendment_does_not_apply_to_feedback_worker(monkeypatch):
    monkeypatch.setattr(m.r.s, "MIN_OWN_CAPACITY_MIB", 61440)
    with pytest.raises(ValueError, match="only_seed47_SFT"):
        m.set_sft_policy(m.RETAINED)
    assert m.r.s.MIN_OWN_CAPACITY_MIB == 61440
    m.set_sft_policy(m.MOVING)
    assert m.r.s.MIN_OWN_CAPACITY_MIB == 40960


def test_adopted_nonchild_completes_even_if_migrated_worker_fails(monkeypatch, tmp_path):
    plan = {"id": "plan", "budget": {"maximum_resource_failures_per_run": 3}}
    active = {
        m.MOVING: dict(
            process=SimpleNamespace(poll=lambda: 1), identity={}, lease=None, stream=None, attempt=2
        ),
        m.RETAINED: dict(process=None, identity={"pid": 2}, lease=None, stream=None, attempt=1),
    }
    checks = []

    def living(expected):
        checks.append(expected)
        if len(checks) == 1:
            return True
        m.p.write_once(
            tmp_path / m.r.OUTPUT / "runs" / m.RETAINED / "report.json",
            dict(status="COMPLETE_RECOVERED_FIXED_FINAL", plan_id="plan"),
        )
        return False

    monkeypatch.setattr(m, "same_process", living)
    monkeypatch.setattr(m.time, "sleep", lambda _: None)
    monkeypatch.setattr(m.r.d.audit, "publish", lambda *args: None)
    monkeypatch.setattr(
        m, "signal_owned", lambda *args: pytest.fail("supervisor signaled the healthy worker")
    )
    monkeypatch.setattr(
        m.r, "publish_final", lambda *args: pytest.fail("incomplete experiment published")
    )
    m.supervise(tmp_path, plan, {"id": "migration"}, active)
    report = m.p.read_json(tmp_path / m.r.OUTPUT / m.DIRECTORY / "coordinator_failure.json")
    assert set(report["failed"]) == {m.MOVING}
    assert report["healthy_workers_not_killed"]
