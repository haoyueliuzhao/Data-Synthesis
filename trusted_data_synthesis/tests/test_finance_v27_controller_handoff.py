"""Controller handoff is tested with fake PIDs/signals only; no GPU or API work."""

import importlib.util
import json
import os
import signal
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location(
    "v27_handoff_tests", SCRIPTS / "finqa_v27_controller_handoff.py"
)
h = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h)


def forbidden(*args, **kwargs):
    raise AssertionError("real process signaling is forbidden in these CPU tests")


class FakeProcesses:
    def __init__(self, controller_command, worker_command):
        self.processes = {
            h.OLD_PID: dict(
                pid=h.OLD_PID,
                birth=h.OLD_BIRTH,
                state="S",
                uid=os.geteuid(),
                ppid=1,
                pgrp=h.OLD_PID,
                session=h.OLD_PID,
            ),
            10001: dict(
                pid=10001,
                birth="worker-birth",
                state="R",
                uid=os.geteuid(),
                ppid=h.OLD_PID,
                pgrp=10001,
                session=10001,
            ),
        }
        self.commands = {h.OLD_PID: controller_command, 10001: worker_command}
        self.events = []
        self.sleep_location = "hrtimer_nanosleep"
        self.extra_children = set()
        self.on_stop = None
        self.on_kill = None
        self.closed = False

    def snapshot(self, pid):
        return self.processes.get(pid)

    def command(self, pid):
        return self.commands[pid]

    def wchan(self, pid):
        return self.sleep_location

    def children(self, pid):
        return self.extra_children | {
            key for key, row in self.processes.items() if row["ppid"] == pid
        }

    def open_handle(self, pid, birth):
        assert (pid, birth) == (h.OLD_PID, h.OLD_BIRTH)
        return dict(pid=pid, birth=birth, fd=123)

    def send(self, handle, signum):
        assert handle["pid"] == h.OLD_PID
        assert self.processes[h.OLD_PID]["birth"] == h.OLD_BIRTH
        self.events.append((h.OLD_PID, signum))
        if signum == signal.SIGSTOP:
            self.processes[h.OLD_PID]["state"] = "T"
            if self.on_stop:
                self.on_stop()
        elif signum == signal.SIGCONT:
            self.processes[h.OLD_PID]["state"] = "S"
        elif signum == signal.SIGKILL:
            self.processes.pop(h.OLD_PID)
            for row in self.processes.values():
                if row["ppid"] == h.OLD_PID:
                    row["ppid"] = 1
            if self.on_kill:
                self.on_kill()
        else:
            raise AssertionError("unexpected signal")

    def wait(self, predicate, seconds=5):
        assert predicate()

    def close_handle(self, handle):
        self.closed = True


@pytest.fixture
def setup(tmp_path, monkeypatch):
    source = tmp_path / "science"
    old = source / "execution_continuation_01"
    new = source / "same_run_recovery_01"
    monkeypatch.setattr(h, "SOURCE_ROOT", source)
    monkeypatch.setattr(h, "OLD_ROOT", old)
    monkeypatch.setattr(h, "NEW_ROOT", new)
    monkeypatch.setattr(h.os, "kill", forbidden)
    monkeypatch.setattr(h.os, "killpg", forbidden)
    if hasattr(h.signal, "pidfd_send_signal"):
        monkeypatch.setattr(h.signal, "pidfd_send_signal", forbidden)
    for root in (source, old):
        (root / "queue").mkdir(parents=True, exist_ok=True)
        (root / "queue/controller.lock").touch()
    job = dict(
        key="replication-train-seed137-static",
        kind="arm",
        result=str(source / "static/result/record.json"),
    )
    failed = dict(key=h.FAILED_JOB, kind="arm", result=str(source / "c_only/result/record.json"))
    plan = dict(id=h.OLD_PROTOCOL_ID, jobs=[job, failed])
    command = ["/cpu-fixture/python", "-u", "frozen-controller.py", "run"]
    launch = dict(pid=h.OLD_PID, birth=h.OLD_BIRTH, command=command)
    plan_ref = dict(path=str(old / "protocol/record.json"), sha256="plan-sha", id=h.OLD_PROTOCOL_ID)
    launch_ref = dict(path=str(old / "launch_01/record.json"), sha256="launch-sha", id="launch-id")
    monkeypatch.setattr(h, "verify_frozen", lambda: (plan, plan_ref, launch, launch_ref))
    attempt = old / "queue/jobs" / job["key"] / "attempt001"
    worker_command = ["/cpu-fixture/python", "-u", "frozen-worker.py"]
    worker = dict(
        protocol_id=plan["id"],
        scientific_protocol_id=h.SCIENCE_ID,
        job=job,
        pid=10001,
        birth="worker-birth",
        gpu=5,
        command=["/usr/bin/taskset", "--cpu-list", "0-3", *worker_command],
    )
    h.publish(attempt / "launch/record.json", worker)
    status = dict(
        protocol_id=plan["id"],
        scientific_protocol_id=h.SCIENCE_ID,
        phase="DRAINING_AFTER_FAILURE",
        failures=[dict(job=h.FAILED_JOB)],
        extension_scored=False,
        replication_scored=False,
        completed=[],
        active_children=[
            dict(job=job, attempt=str(attempt), pid=10001, birth="worker-birth", gpu=5)
        ],
    )
    status_path = old / "queue/status.json"
    status_path.write_text(json.dumps(status))
    backend = FakeProcesses(command, worker_command)
    return SimpleNamespace(
        source=source,
        old=old,
        new=new,
        job=job,
        plan=plan,
        launch=launch,
        status=status,
        status_path=status_path,
        backend=backend,
        attempt=attempt,
    )


def rewrite_status(fixture):
    fixture.status_path.write_text(json.dumps(fixture.status))


def test_default_dry_run_has_no_writes_or_signals(setup):
    before = {str(p): p.read_bytes() for p in setup.source.rglob("*") if p.is_file()}
    result = h.handoff(backend=setup.backend)
    assert result["execute"] is False and result["no_signals_sent"] is True
    assert not setup.new.exists() and setup.backend.events == []
    assert before == {str(p): p.read_bytes() for p in setup.source.rglob("*") if p.is_file()}


def test_execute_signals_only_controller_and_preserves_worker(setup):
    result = h.handoff(execute=True, backend=setup.backend)
    assert setup.backend.events == [(h.OLD_PID, signal.SIGSTOP), (h.OLD_PID, signal.SIGKILL)]
    assert result["no_worker_signals"] and result["post_handoff_controller_absent"]
    assert result["live_workers"][0]["pid"] == 10001
    assert result["live_workers"][0]["job_key"] == setup.job["key"]
    assert result["worker_locks_touched"] is False
    assert result["used_pidfd"] is True
    assert setup.backend.closed
    assert h.read_json(setup.new / "handoff/record.json", bound=True)[0] == result


@pytest.mark.parametrize(
    "case",
    [
        "birth",
        "cmdline",
        "sleep",
        "phase",
        "extra_failure",
        "extra_child",
        "not_detached",
        "malformed_record",
    ],
)
def test_preflight_refusal_sends_no_signal(setup, case):
    if case == "birth":
        setup.backend.processes[h.OLD_PID]["birth"] = "reused"
    elif case == "cmdline":
        setup.backend.commands[h.OLD_PID] = ["another-program"]
    elif case == "sleep":
        setup.backend.sleep_location = "do_wait"
    elif case == "phase":
        setup.status["phase"] = "CPU_SCORING"
        rewrite_status(setup)
    elif case == "extra_failure":
        setup.status["failures"].append(dict(job="unexpected"))
        rewrite_status(setup)
    elif case == "extra_child":
        setup.backend.extra_children.add(90000)
    elif case == "not_detached":
        setup.backend.processes[10001]["session"] = h.OLD_PID
    else:
        (setup.attempt / "launch/record.json").write_text("{")
    with pytest.raises(ValueError):
        h.handoff(execute=True, backend=setup.backend)
    assert setup.backend.events == [] and not setup.new.exists()


def test_post_stop_failure_continues_same_controller(setup):
    setup.backend.on_stop = lambda: setup.backend.extra_children.add(90000)
    with pytest.raises(ValueError, match="extra child"):
        h.handoff(execute=True, backend=setup.backend)
    assert setup.backend.events == [(h.OLD_PID, signal.SIGSTOP), (h.OLD_PID, signal.SIGCONT)]
    failure = h.read_json(setup.new / "handoff_failed/record.json", bound=True)[0]
    assert failure["controller_continued"] is True
    assert failure["controller_killed"] is False
    assert not (setup.new / "handoff/record.json").exists()


def test_half_written_json_after_stop_is_not_killed(setup):
    setup.backend.on_stop = lambda: setup.status_path.write_text("{")
    with pytest.raises(ValueError):
        h.handoff(execute=True, backend=setup.backend)
    assert setup.backend.events[-1] == (h.OLD_PID, signal.SIGCONT)


def test_worker_completion_during_handoff_is_preserved(setup):
    def complete():
        setup.backend.processes.pop(10001)
        h.publish(setup.job["result"], dict(result=dict(committed_step=1490)))

    setup.backend.on_kill = complete
    result = h.handoff(execute=True, backend=setup.backend)
    assert result["live_workers"] == []
    assert result["workers_completed_during_handoff"][0]["job_key"] == setup.job["key"]
    assert len(result["known_worker_launches"]) == 1


def test_worker_death_without_result_refuses_receipt(setup):
    setup.backend.on_kill = lambda: setup.backend.processes.pop(10001)
    with pytest.raises(ValueError, match="regular JSON"):
        h.handoff(execute=True, backend=setup.backend)
    assert not (setup.new / "handoff/record.json").exists()
    assert signal.SIGCONT not in [sig for _, sig in setup.backend.events]
    failure = h.read_json(setup.new / "handoff_failed/record.json", bound=True)[0]
    assert failure["controller_killed"] is True


def test_exclusive_intent_prevents_second_signal_attempt(setup):
    (setup.new / "handoff_intent").mkdir(parents=True)
    with pytest.raises(FileExistsError):
        h.handoff(execute=True, backend=setup.backend)
    assert setup.backend.events == []


def test_frozen_source_hash_change_is_rejected(tmp_path):
    source = tmp_path / "implementation/source.py"
    source.parent.mkdir()
    source.write_text("original")
    manifest = h.publish(
        source.parent / "record.json",
        dict(
            source_commit=h.OLD_COMMIT,
            sha256={"source.py": h.hashlib.sha256(b"original").hexdigest()},
        ),
    )
    h.verify_manifest(tmp_path, manifest["id"], commit=h.OLD_COMMIT)
    source.write_text("modified")
    with pytest.raises(ValueError, match="frozen source changed"):
        h.verify_manifest(tmp_path, manifest["id"], commit=h.OLD_COMMIT)


def test_linux_signal_method_rejects_noncontroller_identity(monkeypatch):
    monkeypatch.setattr(h.os, "kill", forbidden)
    with pytest.raises(ValueError, match="only fixed controller"):
        h.LinuxProcesses().send(dict(pid=10001, birth="worker-birth", fd=None), signal.SIGKILL)
