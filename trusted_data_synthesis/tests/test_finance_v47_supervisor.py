"""CPU-only persistent-owner, fresh-attempt, backoff and manual-stop checks."""

import importlib
import json
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v47_supervisor")


def require(ok, message):
    if not ok:
        raise ValueError(message)


@pytest.fixture
def episode(tmp_path, monkeypatch):
    root = tmp_path / "episode"
    root.mkdir()
    state = SimpleNamespace(time=0.0, spawns=[], prepared=[], decisions=[], processes=[])

    def publish(path, body):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as stream:
            json.dump(body, stream)
        return body

    def sleep(seconds):
        state.time += seconds

    def prepare(target, *, parentroot):
        state.prepared.append((target, parentroot))
        target.mkdir(parents=True)

    control = SimpleNamespace(
        ROOT=root,
        REPO=tmp_path,
        require=require,
        now=lambda: "CPU_TIME",
        publish=publish,
        status=lambda *a, **k: None,
        birth=lambda pid: str(pid),
        checked=lambda path: json.loads(Path(path).read_bytes()),
        checked_protocol=lambda path: dict(id="protocol"),
        entry=lambda p: dict(path=str(p)),
        parent=SimpleNamespace(PYTHON=sys.executable),
        prepare_automatic=prepare,
        inheritance=SimpleNamespace(validate_safe_recovery=lambda root: state.decisions.pop(0)),
    )

    def spawn(command, **kwargs):
        attempt = Path(command[-1])
        state.spawns.append(attempt)
        outcome = state.outcomes.pop(0)
        process = SimpleNamespace(pid=100 + len(state.spawns), returncode=None, polls=0)

        def poll():
            process.polls += 1
            if process.polls >= 5:
                process.returncode = outcome
            return process.returncode

        process.poll = poll
        state.processes.append(process)
        if outcome == 0:
            publish(
                attempt / "result/record.json",
                dict(status="COMPLETE", nine_endpoint_models_complete=True),
            )
        return process

    supervisor = subject.Supervisor(
        root, control=control, spawn=spawn, sleep=sleep, clock=lambda: state.time
    )
    monkeypatch.setattr(subject, "__file__", str(root / "implementation/finqa_v47_supervisor.py"))
    monkeypatch.setattr(
        subject.original, "__file__", str(root / "implementation/finqa_v43_supervisor.py")
    )
    return SimpleNamespace(**locals())


def test_verified_failure_gets_new_attempt_not_relaunch(episode):
    e = episode
    e.state.outcomes = [1, 0]
    e.state.decisions = [dict(allowed=True, reason="verified CPU admission failure")]
    assert e.supervisor.run() == "COMPLETE"
    assert e.state.spawns == [e.root, e.root / "attempts/attempt0002"]
    assert e.state.prepared == [(e.root / "attempts/attempt0002", e.root)]
    assert e.state.time >= 30
    assert (e.root / "supervisor/attempt0001/actual_exit/record.json").exists()
    with pytest.raises(FileExistsError):
        e.supervisor.run()


def test_unknown_feedback_or_numerical_failure_is_terminal(episode):
    e = episode
    e.state.outcomes = [1]
    e.state.decisions = [dict(allowed=False, reason="unknown feedback call")]
    assert e.supervisor.run() == "STOPPED_UNSAFE_FOR_AUTOMATIC_RECOVERY"
    assert e.state.spawns == [e.root]
    assert not e.state.prepared


def test_typed_capacity_failure_waits_for_changed_capacity_before_fresh_attempt(episode):
    e = episode
    e.state.outcomes = [1, 0]
    e.state.decisions = [
        dict(
            allowed=True,
            retry_capacity_conditions=[dict(schema="CPU_TYPED")],
            retry_capacity_evidence_refs=[dict(path="CPU_PROOF")],
        )
    ]
    observations = []

    def capacity(conditions):
        observations.append(conditions)
        assert len(e.state.spawns) == 1 and not e.state.prepared
        return dict(ready=len(observations) >= 2)

    e.control.recovery_capacity_snapshot = capacity
    assert e.supervisor.run() == "COMPLETE"
    assert len(observations) == 2 and len(e.state.spawns) == 2
    value = e.control.checked(e.root / "supervisor/attempt0001/capacity_wait/record.json")
    assert value["actual_elapsed_seconds"] == 10 and value["capacity_ready"] is True
    assert value["retry_capacity_evidence_refs"] == [dict(path="CPU_PROOF")]


def test_explicit_stop_during_capacity_wait_never_prepares_new_attempt(episode):
    e = episode
    e.state.outcomes = [1]
    e.state.decisions = [dict(allowed=True, retry_capacity_conditions=[dict(schema="CPU_TYPED")])]
    e.control.recovery_capacity_snapshot = lambda conditions: dict(ready=False)

    def sleep(seconds):
        e.state.time += seconds
        if seconds == 10:
            e.supervisor.request_stop(signal.SIGTERM)

    e.supervisor.sleep = sleep
    assert e.supervisor.run() == "STOPPED_BY_EXPLICIT_REQUEST"
    assert not e.state.prepared and len(e.state.spawns) == 1
    value = e.control.checked(e.root / "supervisor/attempt0001/capacity_wait/record.json")
    assert value["manual_stop_requested"] is True and value["capacity_ready"] is False


def test_audit_exception_never_means_safe_to_retry(episode):
    e = episode
    e.state.outcomes = [1]

    def rejected(_root):
        raise ValueError("checkpoint binding mismatch")

    e.control.inheritance.validate_safe_recovery = rejected
    assert e.supervisor.run() == "STOPPED_UNSAFE_FOR_AUTOMATIC_RECOVERY"
    assert not e.state.prepared


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
def test_manual_stop_is_forwarded_once_and_disables_auto_recovery(episode, monkeypatch, signum):
    e = episode
    e.state.outcomes = [1]
    signals = []

    def sleep(seconds):
        e.state.time += seconds
        if not e.supervisor.stopped:
            e.supervisor.request_stop(signum)

    monkeypatch.setattr(subject.original.os, "kill", lambda pid, sig: signals.append((pid, sig)))
    e.supervisor.sleep = sleep
    assert e.supervisor.run() == "STOPPED_BY_EXPLICIT_REQUEST"
    assert signals == [(101, signal.SIGTERM)]
    assert not e.state.prepared


def test_direct_controller_stop_also_terminates_supervision(episode):
    e = episode
    e.state.outcomes = [1]
    e.publish(e.root / "signal_audit/record.json", dict(received_signals=[dict(signal_number=15)]))
    assert e.supervisor.run() == "STOPPED_BY_EXPLICIT_REQUEST"
    assert not e.state.prepared


def test_pid_reuse_does_not_signal_another_process(episode, monkeypatch):
    e = episode
    e.supervisor.child = SimpleNamespace(pid=77, poll=lambda: None)
    e.supervisor.child_identity = dict(pid=77, birth="old")
    monkeypatch.setattr(
        subject.original.os, "kill", lambda *args: pytest.fail("foreign PID signalled")
    )
    with pytest.raises(ValueError, match="PID/birth"):
        e.supervisor.stop_owned_child_once()


def test_late_stop_before_spawn_never_creates_controller(episode):
    e = episode
    e.state.outcomes = []
    checks = []

    def protocol(_root):
        checks.append(True)
        if len(checks) == 2:
            e.supervisor.request_stop(signal.SIGTERM)
        return dict(id="protocol")

    e.control.checked_protocol = protocol
    assert e.supervisor.run() == "STOPPED_BY_EXPLICIT_REQUEST"
    assert e.state.spawns == []
    assert not e.state.prepared


def test_stop_received_inside_spawn_forwards_immediately_and_once(episode, monkeypatch):
    e = episode
    e.state.outcomes = [1]
    spawn = e.supervisor.spawn

    def stopped_spawn(*args, **kwargs):
        child = spawn(*args, **kwargs)
        e.supervisor.request_stop(signal.SIGTERM)
        return child

    e.supervisor.spawn = stopped_spawn
    received = []
    monkeypatch.setattr(subject.original.os, "kill", lambda pid, sig: received.append((pid, sig)))
    assert e.supervisor.run() == "STOPPED_BY_EXPLICIT_REQUEST"
    assert received == [(101, signal.SIGTERM)]
    assert not e.state.prepared
