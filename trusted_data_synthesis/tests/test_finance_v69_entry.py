"""No-GPU checks for a single exact source signal and GPU6 conditional handoff."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import finqa_v69_entry as e


def source(tmp_path=None):
    return dict(id="source", gpu_uuids={"6": "uuid6"}, gpu_lease_root=str(tmp_path or "/unused"),
        resource_policy=dict(minimum_free_gib_by_kind=dict(generate=24)))


def idle_row():
    return dict(index=6, uuid="uuid6", free_mib=24 * 1024, processes=[],
        gpu_isolation=dict(gpu_uuid="uuid6", allowed=True, known_processes=[], unresolved_processes=[], process_count=0))


def migration(tmp_path):
    value = e.Migration.__new__(e.Migration)
    value.root, value.protocol, value.source = tmp_path, dict(id="new"), source(tmp_path / "secondary")
    value.target = dict(job_id=e.b.TARGET_JOB_ID, pid=e.b.TARGET_PID, birth=e.b.TARGET_BIRTH, gpu_index=0, attempt=1)
    value.destination = dict(gpu_index=6)
    value.controller = dict(pid=e.b.CONTROLLER_PID, birth=e.b.CONTROLLER_BIRTH, controller_attempt=1)
    value.signals, value.lease, value.child, value.baseline = [], None, None, None
    value.source_signal_sent = value.child_signal_sent = False
    value.status = lambda *args, **kwargs: None
    return value


def test_physical_gpu6_must_be_completely_idle_with_original_capacity():
    assert e.physical_destination_gate(idle_row(), source()) is True


@pytest.mark.parametrize("change", ["process", "known", "unresolved", "count", "not_allowed", "free", "infinite"])
def test_resource_or_any_compute_process_prevents_stop(change):
    row = idle_row()
    if change == "process": row["processes"] = [dict(pid=999)]
    elif change == "known": row["gpu_isolation"]["known_processes"] = [dict(pid=999)]
    elif change == "unresolved": row["gpu_isolation"]["unresolved_processes"] = [999]
    elif change == "count": row["gpu_isolation"]["process_count"] = 1
    elif change == "not_allowed": row["gpu_isolation"]["allowed"] = False
    elif change == "free": row["free_mib"] = 23 * 1024
    else: row["free_mib"] = float("inf")
    assert e.physical_destination_gate(row, source()) is False


@pytest.mark.parametrize("change", ["gpu", "uuid", "isolation_uuid", "threshold"])
def test_destination_identity_and_original_gate_cannot_change(change):
    row, protocol = idle_row(), source()
    if change == "gpu": row["index"] = 7
    elif change == "uuid": row["uuid"] = "different"
    elif change == "isolation_uuid": row["gpu_isolation"]["gpu_uuid"] = "different"
    else: protocol["resource_policy"]["minimum_free_gib_by_kind"]["generate"] = 12
    with pytest.raises(ValueError):
        e.physical_destination_gate(row, protocol)


def test_host_admission_retains_512_gib_budget(tmp_path):
    value = migration(tmp_path)
    value.runtime = SimpleNamespace(inventory=lambda: [idle_row()], host_memory=lambda: dict(available_bytes=511 * e.GIB))
    assert value.destination_admission() is None
    value.runtime.host_memory = lambda: dict(available_bytes=512 * e.GIB)
    assert value.destination_admission()["required_host_available_gib"] == 512


def test_destination_secondary_exclusive_lock_is_acquired_and_rechecked_before_signal(tmp_path):
    value = migration(tmp_path)
    value.destination_admission = lambda: dict(gpu=idle_row())
    admitted = value.acquire_destination()
    assert admitted["secondary_EX_lease_acquired_before_source_signal"] is True
    other = migration(tmp_path)
    other.destination_admission = value.destination_admission
    assert other.acquire_destination() is None
    value.lease.close()
    value.lease = None


def test_destination_race_releases_lease_without_stop(tmp_path):
    value = migration(tmp_path)
    states = iter([dict(gpu=idle_row()), None])
    value.destination_admission = lambda: next(states)
    assert value.acquire_destination() is None and value.lease is None
    assert value.source_signal_sent is False


def test_source_completes_first_without_waiting_or_acquiring_gpu6(tmp_path, monkeypatch):
    value = migration(tmp_path)
    value.target_completed = lambda: dict(path="accepted")
    assert value.readiness() == dict(status=e.NO_MIGRATION_STATUS, accepted=dict(path="accepted"))
    value.readiness = lambda: dict(status=e.NO_MIGRATION_STATUS, accepted=dict(path="accepted"))
    value.acquire_destination = lambda: pytest.fail("finished source does not reserve GPU6")
    value.closeout = lambda result: result
    science = tmp_path / "science"
    science.mkdir()
    monkeypatch.setattr(e.b, "SCIENTIFIC_ROOT", science)
    monkeypatch.setattr(e.b, "publish", lambda path, body: body)
    monkeypatch.setattr(e, "identity", lambda pid: "123")
    assert value.run()["status"] == e.NO_MIGRATION_STATUS


def source_journal(value):
    target, dest = e.b.TARGET_JOB_ID, e.b.DESTINATION_JOB_ID
    value.plan = dict(jobs={target: dict(panel="dev"), dest: {}, "a": {}, "b": {}})
    states = {target: dict(status="RUNNING", attempts=1), dest: dict(status="RUNNING", attempts=1),
              "a": dict(status="COMPLETE", attempts=1), "b": dict(status="COMPLETE", attempts=1)}
    return dict(protocol_id="source", controller_attempt=1, updated_epoch=e.time.time(), job_states=states,
        active_jobs=[dict(job_id=target, pid=e.b.TARGET_PID, birth=e.b.TARGET_BIRTH, gpu_index=0, attempt=1),
                     dict(job_id=dest, pid=e.b.DESTINATION_PID, birth=e.b.DESTINATION_BIRTH, gpu_index=6, attempt=1)])


def test_destination_running_means_wait_without_target_signal(tmp_path, monkeypatch):
    value = migration(tmp_path)
    journal = source_journal(value)
    value.target_completed = lambda: None
    monkeypatch.setattr(e.b, "checked", lambda path: journal)
    monkeypatch.setattr(e.b, "target_directory", lambda: tmp_path / "target")
    monkeypatch.setattr(e, "alive", lambda *args: True)
    assert value.readiness()["status"] == "WAIT"
    assert not value.source_signal_sent


def test_native_complete_but_not_yet_accepted_waits_for_real_exit(tmp_path, monkeypatch):
    value = migration(tmp_path)
    journal = source_journal(value)
    value.target_completed = lambda: None
    native = tmp_path / "target/shards/dev/generation/generation_seal/seal.json"
    native.parent.mkdir(parents=True)
    native.write_text("placeholder")
    monkeypatch.setattr(e.b, "checked", lambda path: journal)
    monkeypatch.setattr(e.b, "target_directory", lambda: tmp_path / "target")
    monkeypatch.setattr(e, "alive", lambda *args: True)
    result = value.readiness()
    assert result["status"] == "WAIT" and "actual successful exit" in result["reason"]


def test_signal_requires_destination_lease(tmp_path):
    value = migration(tmp_path)
    with pytest.raises(ValueError, match="single-use"):
        value.signal_source_once({})


def test_source_sigterm_is_pidfd_identity_bound_and_single_use(tmp_path, monkeypatch):
    value = migration(tmp_path)
    value.lease = SimpleNamespace()
    value.readiness = lambda: dict(status="READY")
    value.destination_admission = lambda: dict(gpu=idle_row())
    monkeypatch.setattr(e, "alive", lambda *args: True)
    monkeypatch.setattr(e, "identity", lambda pid: "777")
    monkeypatch.setattr(e.os, "getuid", lambda: e.b.OWNER_UID)
    monkeypatch.setattr(e.os, "geteuid", lambda: e.b.OWNER_UID)
    sent, published, closed = [], [], []
    monkeypatch.setattr(e.os, "pidfd_open", lambda pid: 91, raising=False)
    monkeypatch.setattr(e.signal, "pidfd_send_signal", lambda fd, sig: sent.append((fd, sig)), raising=False)
    monkeypatch.setattr(e.os, "kill", lambda *args: pytest.fail("pidfd branch must not call broad kill"))
    monkeypatch.setattr(e.os, "close", closed.append)
    monkeypatch.setattr(e.b, "publish", lambda path, body: published.append((path, body)) or dict(body, id="intent"))
    assert value.signal_source_once({})["status"] == "SOURCE_STOP_REQUESTED"
    assert sent == [(91, e.signal.SIGTERM)] and closed == [91]
    assert published[-1][1]["target_pid"] == e.b.TARGET_PID
    assert published[-1][1]["source_SIGKILL_sent"] is False
    with pytest.raises(ValueError, match="single-use"):
        value.signal_source_once({})


def test_changed_target_identity_never_gets_a_signal(tmp_path, monkeypatch):
    value = migration(tmp_path)
    value.lease = SimpleNamespace()
    value.readiness = lambda: dict(status="READY")
    value.destination_admission = lambda: {}
    monkeypatch.setattr(e, "alive", lambda *args: False)
    monkeypatch.setattr(e.os, "pidfd_open", lambda pid: 91, raising=False)
    monkeypatch.setattr(e.os, "close", lambda fd: None)
    monkeypatch.setattr(e.signal, "pidfd_send_signal", lambda *args: pytest.fail("identity changed"), raising=False)
    with pytest.raises(ValueError, match="identity changed"):
        value.signal_source_once({})


def test_source_wait_timeout_is_no_retry_and_never_sigkill(tmp_path, monkeypatch):
    value = migration(tmp_path)
    times = iter([0, e.b.STOP_SETTLE_SECONDS + 1])
    monkeypatch.setattr(e.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(e, "alive", lambda *args: True)
    monkeypatch.setattr(e.os, "kill", lambda *args: pytest.fail("timeout cannot hard kill"))
    result = value.wait_source_settled()
    assert result["status"] == "STOPPED_SOURCE_NOT_SETTLED_NO_RETRY"
    assert result["actual_exit_not_inferred"] is True and result["SIGKILL_sent"] is False


def test_explicit_cancel_does_not_signal_other_source_processes(tmp_path, monkeypatch):
    value = migration(tmp_path)
    value.signals = [e.signal.SIGTERM]
    monkeypatch.setattr(e.os, "kill", lambda *args: pytest.fail("cancel cannot signal the old target again"))
    assert value.wait_source_settled()["status"] == "STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME"


def test_child_nonzero_waitpid_is_passed_to_bridge_without_retry(tmp_path, monkeypatch):
    value = migration(tmp_path)
    value.baseline = dict(id="base")
    value.child = SimpleNamespace(process=SimpleNamespace(pid=111, poll=lambda: 1, returncode=1),
        birth="222", directory=tmp_path / "worker")
    records = []
    monkeypatch.setattr(e.b, "publish", lambda path, body: records.append((path, body)) or body)
    monkeypatch.setattr(e.b, "entry", lambda path: dict(path=str(path)))
    def reject(root, baseline, ref):
        assert records[0][1]["returncode"] == 1
        raise ValueError("actual failure")
    value.bridge = SimpleNamespace(accept_resumed_target=reject)
    result = value.wait_child()
    assert result["status"] == "STOPPED_FAILURE_NO_RETRY"
    assert records[0][1]["actual_waitpid_observed"] is True


def test_closeout_releases_reserved_gpu6_lease_after_actual_child_exit(tmp_path, monkeypatch):
    value = migration(tmp_path)
    closed = []
    value.lease = SimpleNamespace(close=lambda: closed.append(True))
    monkeypatch.setattr(e, "alive", lambda *args: False)
    monkeypatch.setattr(e.b, "publish", lambda path, body: body)
    result = value.closeout(dict(status=e.NO_MIGRATION_STATUS))
    assert closed == [True] and value.lease is None and result["destination_secondary_lease_released"] is True


def test_early_exited_child_with_failed_launch_publication_still_gets_actual_exit(tmp_path, monkeypatch):
    import json
    value = migration(tmp_path)
    science = tmp_path / "science"
    science.mkdir()
    monkeypatch.setattr(e.b, "SCIENTIFIC_ROOT", science)
    monkeypatch.setattr(e, "identity", lambda pid: "123")
    monkeypatch.setattr(e, "alive", lambda *args: False)
    monkeypatch.setattr(e.os, "kill", lambda *args: pytest.fail("already exited child must not be signaled"))
    written = []
    def publish(path, body):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body))
        written.append((path, body))
        return body
    monkeypatch.setattr(e.b, "publish", publish)
    monkeypatch.setattr(e.b, "entry", lambda path: dict(path=str(path)))
    value.readiness = lambda: dict(status="READY")
    value.acquire_destination = lambda: {}
    value.signal_source_once = lambda admission: dict(status="SOURCE_STOP_REQUESTED")
    value.wait_source_settled = lambda: dict(status="SOURCE_DURABLE_BOUNDARY_VERIFIED")
    value.destination_admission = lambda: {}
    def launch(admission):
        value.child = SimpleNamespace(process=SimpleNamespace(pid=999, poll=lambda: 1, returncode=1),
            birth=None, directory=tmp_path / "worker")
        raise ValueError("child exited before birth/launch publication")
    value.launch_child = launch
    def reject(*args):
        raise ValueError("no bound destination launch")
    value.bridge = SimpleNamespace(accept_resumed_target=reject)
    result = value.run()
    actuals = [body for path, body in written if path == tmp_path / "worker/actual_exit/record.json"]
    assert len(actuals) == 1 and actuals[0]["returncode"] == 1
    assert actuals[0]["birth"] is None and actuals[0]["actual_waitpid_observed"] is True
    assert result["status"] == "STOPPED_FAILURE_NO_RETRY"


def test_early_signal_order_and_frozen_origin(tmp_path, monkeypatch):
    with pytest.raises(RuntimeError, match="precede"):
        e.require_early_install({"torch": SimpleNamespace(__file__="/torch/__init__.py")})
    monkeypatch.setattr(e.b, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="workspace"):
        e.verify_imported_modules(tmp_path, dict(sha256={}),
            modules={"finqa_v69_entry": SimpleNamespace(__file__="/workspace/finqa_v69_entry.py")})


@pytest.mark.parametrize("status,mode,expected", [("PASS", "check-imports", 0),
    (e.COMPLETE_STATUS, "run", 0), (e.NO_MIGRATION_STATUS, "run", 0),
    ("STOPPED_FAILURE_NO_RETRY", "run", 2), ("STOPPED_SOURCE_NOT_SETTLED_NO_RETRY", "run", 2)])
def test_only_actual_completion_or_no_migration_are_success(status, mode, expected):
    assert e.exit_status(dict(status=status), mode) == expected
