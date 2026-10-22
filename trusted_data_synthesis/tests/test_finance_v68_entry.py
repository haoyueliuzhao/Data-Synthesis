"""CPU/mock checks for complete-group auto-continuation without failed retries."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import finqa_v68_entry as e


@pytest.mark.parametrize("coordinate", [f"seed{seed}/{arm}" for seed in (137, 251, 389) for arm in ("C1", "C05")])
def test_exact_six_coordinates(coordinate):
    assert e.checked_coordinate(coordinate) == coordinate


@pytest.mark.parametrize("coordinate", ["seed137/Hold", "seed137/C1/b0", "seed999/C1", "../seed137/C1", None])
def test_no_scope_expansion_or_path_escape(coordinate):
    with pytest.raises(ValueError):
        e.checked_coordinate(coordinate)


def queue_fixture(tmp_path):
    queue = e.ScoringQueue.__new__(e.ScoringQueue)
    queue.root, queue.protocol = tmp_path, dict(id="p")
    queue.states = {key: dict(status="WAITING_COMPLETE_GROUP") for key in e.coordinates()}
    queue.active, queue.accepted, queue.eligibility = {}, {}, {}
    queue.explicit_stop, queue.signals = False, []
    queue.journal = lambda status: None
    return queue


def test_two_cpu_admission_reserves_512_gib_not_actual_low_rss(tmp_path):
    queue = queue_fixture(tmp_path)
    queue.runtime = SimpleNamespace(host_memory=lambda: dict(available_bytes=511 * e.GIB))
    assert queue.admission() is None
    queue.runtime.host_memory = lambda: dict(available_bytes=512 * e.GIB)
    assert queue.admission()["required_bytes"] == 512 * e.GIB
    queue.active = {"first": SimpleNamespace(lifecycle="INITIALIZING"), "second": SimpleNamespace(lifecycle="DRAINING")}
    assert queue.admission() is None


def test_ready_groups_are_discovered_once_and_future_groups_automatically_added(tmp_path, monkeypatch):
    queue = queue_fixture(tmp_path)
    first, second = "seed137/C1", "seed251/C1"
    calls = []
    def read(root, *, skip_coordinates):
        calls.append(skip_coordinates)
        return dict(ready_groups={first if not skip_coordinates else second: dict(sessions=1243)})
    adoption = SimpleNamespace(read_ready_groups=read)
    monkeypatch.setattr(e.importlib, "import_module", lambda name: adoption)
    monkeypatch.setattr(e.b, "eligibility_path", lambda key: tmp_path / "eligibility" / key / "record.json")
    published = []
    monkeypatch.setattr(e.b, "publish", lambda path, body: published.append((path, body)))
    monkeypatch.setattr(e.b, "entry", lambda path: dict(path=str(path)))
    queue.discover()
    queue.discover()
    assert calls == [(), (first,)]
    assert set(queue.eligibility) == {first, second}
    assert queue.states["seed389/C1"]["status"] == "WAITING_COMPLETE_GROUP"
    assert len(published) == 2


def test_partial_group_or_extra_group_is_not_dispatched(tmp_path, monkeypatch):
    queue = queue_fixture(tmp_path)
    monkeypatch.setattr(e.importlib, "import_module", lambda name: SimpleNamespace(
        read_ready_groups=lambda *args, **kwargs: dict(ready_groups={"seed137/C1": dict(sessions=1242)})))
    with pytest.raises(ValueError, match="partial denominator"):
        queue.discover()
    assert not queue.active


def test_source_unknown_is_not_converted_to_wait_or_permission(tmp_path, monkeypatch):
    queue = queue_fixture(tmp_path)
    def failed(*args, **kwargs):
        raise ValueError("changed original accepted identity")
    monkeypatch.setattr(e.importlib, "import_module", lambda name: SimpleNamespace(read_ready_groups=failed))
    with pytest.raises(ValueError, match="changed original"):
        queue.discover()


def test_failed_cpu_actual_exit_is_recorded_not_retried(tmp_path, monkeypatch):
    queue = queue_fixture(tmp_path)
    coordinate = "seed137/C1"
    child = SimpleNamespace(process=SimpleNamespace(pid=123, poll=lambda: 1), birth="456",
        directory=e.attempt_directory(tmp_path, coordinate), resource_failure=None)
    queue.active[coordinate] = child
    queue.accept = lambda *args: pytest.fail("nonzero worker cannot be accepted")
    records = []
    monkeypatch.setattr(e.b, "publish", lambda path, body: records.append((path, body)))
    queue.reap()
    assert not queue.active and queue.states[coordinate]["status"] == "HARD_BLOCKED"
    assert records[0][1]["returncode"] == 1 and records[0][1]["actual_waitpid_observed"] is True
    assert records[1][1]["automatic_retry"] is False


def test_attempt_directory_cannot_be_reused_even_after_failure(tmp_path):
    queue = queue_fixture(tmp_path)
    coordinate = "seed137/C1"
    queue.states[coordinate] = dict(status="READY")
    e.attempt_directory(tmp_path, coordinate).mkdir(parents=True)
    with pytest.raises(ValueError, match="immutable"):
        queue.launch(coordinate, {})


def test_cpu_launch_eof_cannot_read_private_references_or_score(tmp_path, monkeypatch):
    coordinate = "seed137/C1"
    attempt = e.attempt_directory(tmp_path, coordinate)
    attempt.mkdir(parents=True)
    reader, writer = os.pipe()
    os.close(writer)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    monkeypatch.delenv("V54_GPU_LEASE_FD", raising=False)
    monkeypatch.setenv("V68_LAUNCH_READY_FD", str(reader))
    monkeypatch.setattr(e, "runtime_api", lambda: SimpleNamespace())
    monkeypatch.setattr(e.b, "publish", lambda path, body: body)
    monkeypatch.setattr(e.importlib, "import_module", lambda name: pytest.fail("EOF cannot authorize scoring"))
    with pytest.raises(ValueError, match="did not commit"):
        e.score_worker(tmp_path, coordinate, attempt, dict(id="p"))


def completed_evidence(tmp_path, coordinate):
    attempt = e.attempt_directory(tmp_path, coordinate)
    group_path = tmp_path / "groups" / coordinate / "result/record.json"
    resource_path = attempt / "resource_closeout/record.json"
    result = dict(id="group", protocol_id="p", coordinate=coordinate, sessions=1243,
        native_scores_present=1243, scoring_execution_complete=True,
        eligibility=dict(id="eligible"),
        metrics=dict(execution_accuracy=dict(unknown=1, complete_dataset_mean=None)))
    resources = dict(status="COMPLETE", protocol_id="p", coordinate=coordinate, pid=123,
        all_gates_passed=True, CUDA_initialized=False, peak_rss_bytes=2 * e.GIB,
        minimum_host_available_bytes=600 * e.GIB)
    completed = dict(status="COMPLETE", protocol_id="p", coordinate=coordinate, group_result_id="group",
        group_result=dict(path=str(group_path)), resource_closeout=dict(path=str(resource_path)),
        new_native_scoring_calls=1243)
    actual = dict(returncode=0, actual_waitpid_observed=True, pid=123, birth="456",
        protocol_id="p", coordinate=coordinate, eligibility=dict(id="eligible"))
    return attempt, result, resources, completed, actual


def test_unknown_metric_does_not_prevent_valid_scoring_execution_acceptance(tmp_path, monkeypatch):
    queue, coordinate = queue_fixture(tmp_path), "seed137/C1"
    attempt, result, resources, completed, actual = completed_evidence(tmp_path, coordinate)
    child = SimpleNamespace(process=SimpleNamespace(pid=123), birth="456", directory=attempt, resource_failure=None)
    queue.eligibility[coordinate] = dict(id="eligible")
    monkeypatch.setattr(e.b, "checked", lambda path: completed if Path(path).parent.name == "completed" else actual)
    monkeypatch.setattr(e.b, "read_ref", lambda ref: resources if "resource_closeout" in ref["path"] else result)
    monkeypatch.setattr(e.b, "entry", lambda path: dict(path=str(path)))
    records = []
    monkeypatch.setattr(e.b, "publish", lambda path, body: records.append(body))
    queue.accept(coordinate, child)
    assert queue.states[coordinate]["status"] == "COMPLETE"
    assert records[0]["UNKNOWN_not_asserted_known"] is True
    assert result["metrics"]["execution_accuracy"]["complete_dataset_mean"] is None


@pytest.mark.parametrize("mutation", ["wrong_pid", "unknown_exit", "partial", "wrong_protocol", "RSS", "host"])
def test_acceptance_retains_actual_exit_resource_and_dose_gates(tmp_path, monkeypatch, mutation):
    queue, coordinate = queue_fixture(tmp_path), "seed137/C1"
    attempt, result, resources, completed, actual = completed_evidence(tmp_path, coordinate)
    if mutation == "wrong_pid": actual["pid"] = 999
    elif mutation == "unknown_exit": actual["actual_waitpid_observed"] = False
    elif mutation == "partial": result["sessions"] = 1242
    elif mutation == "wrong_protocol": result["protocol_id"] = "old"
    elif mutation == "RSS": resources["peak_rss_bytes"] = 33 * e.GIB
    else: resources["minimum_host_available_bytes"] = 95 * e.GIB
    child = SimpleNamespace(process=SimpleNamespace(pid=123), birth="456", directory=attempt, resource_failure=None)
    queue.eligibility[coordinate] = dict(id="eligible")
    monkeypatch.setattr(e.b, "checked", lambda path: completed if Path(path).parent.name == "completed" else actual)
    monkeypatch.setattr(e.b, "read_ref", lambda ref: resources if "resource_closeout" in ref["path"] else result)
    with pytest.raises(ValueError, match="acceptance"):
        queue.accept(coordinate, child)


def test_new_scoring_owner_is_exclusive_but_science_owner_shared(tmp_path, monkeypatch):
    root, science = tmp_path / "new", tmp_path / "science"
    root.mkdir(); science.mkdir()
    queue = queue_fixture(root)
    queue.runtime = SimpleNamespace(birth=lambda pid: "123")
    queue.reap = lambda: None
    queue.accepted = {key: {} for key in e.coordinates()}
    queue.closeout = lambda status: dict(status=status)
    monkeypatch.setattr(e.b, "SCIENTIFIC_ROOT", science)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    monkeypatch.delenv("V54_GPU_LEASE_FD", raising=False)
    monkeypatch.setattr(e.b, "publish", lambda path, body: body)
    locks = []
    monkeypatch.setattr(e.fcntl, "flock", lambda file, operation: locks.append((Path(file.name), operation)))
    assert queue.run()["status"] == e.SEALED_STATUS
    assert locks == [(science / "owner.lock", e.fcntl.LOCK_SH | e.fcntl.LOCK_NB),
        (root / "owner.lock", e.fcntl.LOCK_EX | e.fcntl.LOCK_NB)]


def test_explicit_stop_never_signals_a_pid_with_changed_birth(tmp_path, monkeypatch):
    queue = queue_fixture(tmp_path)
    queue.runtime = SimpleNamespace(birth=lambda pid: "new-birth")
    child = SimpleNamespace(process=SimpleNamespace(pid=123), birth="old-birth")
    monkeypatch.setattr(e.os, "kill", lambda *args: pytest.fail("foreign identity must not be signaled"))
    queue.signal_child(child, e.signal.SIGTERM)


def test_early_observer_guard_and_frozen_source_check(tmp_path, monkeypatch):
    with pytest.raises(RuntimeError, match="precede"):
        e.require_early_install({"torch": SimpleNamespace(__file__="/torch/__init__.py")})
    monkeypatch.setattr(e.b, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="workspace"):
        e.verify_imported_modules(tmp_path, dict(sha256={}),
            modules={"finqa_v68_scoring": SimpleNamespace(__file__="/workspace/finqa_v68_scoring.py")})


def test_cpu_entry_installs_signal_observer_before_dispatch(tmp_path, monkeypatch):
    monkeypatch.setattr(e.b, "ROOT", tmp_path)
    monkeypatch.setattr(e, "__file__", str(tmp_path / "implementation/finqa_v68_entry.py"))
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    monkeypatch.delenv("V54_GPU_LEASE_FD", raising=False)
    observed = []
    monkeypatch.setattr(e, "checked_signal_registration", lambda root: observed.append("policy") or {})
    monkeypatch.setattr(e, "install_signal_observer", lambda *args: observed.append("observer") or
        SimpleNamespace(close=lambda: observed.append("close")))
    monkeypatch.setattr(e, "_dispatch", lambda *args: observed.append("dispatch") or dict(status=e.SEALED_STATUS))
    assert e.main(["--mode", "run", "--root", str(tmp_path)]) == 0
    assert observed == ["policy", "observer", "dispatch", "close"]


@pytest.mark.parametrize("status,mode,expected", [("PASS", "check-imports", 0), ("COMPLETE", "score", 0),
    ("PARTIAL_GROUP_SCORED", "score", 2), ("COMPLETE", "run", 2),
    (e.SEALED_STATUS, "run", 0), ("BLOCKED_OPERATOR_REQUIRED", "run", 2)])
def test_execution_status_is_not_global_science_completion(status, mode, expected):
    assert e.exit_status(dict(status=status), mode) == expected
