"""Resource-owner CPU mocks; no CUDA, actual child spawn or process signal."""

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

_SOURCE = Path(__file__).parents[1] / "scripts/finqa_v46_reservation_watch.py"
_SPEC = importlib.util.spec_from_file_location("v46_reservation_cpu_subject", _SOURCE)
subject = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(subject)


@pytest.fixture
def episode(tmp_path, monkeypatch):
    handoff, progress = tmp_path / "handoff", tmp_path / "progress.json"
    monkeypatch.setattr(subject, "HANDOFF", handoff)
    monkeypatch.setattr(subject, "PROGRESS", progress)
    holder = tmp_path / "holder.py"
    holder.write_text("# CPU placeholder; never executed\n")
    monkeypatch.setattr(subject, "HOLDER_SHA256", hashlib.sha256(holder.read_bytes()).hexdigest())
    state = SimpleNamespace(time=0.0, stop=False, worker_alive=True, queued_alive=True)
    commands, processes, signals, waits = [], [], [], []

    def update(count):
        progress.write_text(
            json.dumps(
                dict(
                    context_id=subject.CONTEXT_ID,
                    assigned_task_count=186,
                    committed_task_count=count,
                )
            )
        )

    update(169)

    def identity(pid):
        if pid == subject.WORKER["pid"]:
            return subject.WORKER["birth"] if state.worker_alive else None
        if pid == 777:
            return "queued-birth" if state.queued_alive else None
        return "birth-" + str(pid)

    def unavailable_pidfd(_pid):
        raise OSError("CPU fixture has no real process")

    monkeypatch.setattr(subject.os, "pidfd_open", unavailable_pidfd, raising=False)

    class Process:
        def __init__(self, pid):
            self.pid, self.returncode = pid, None

        def poll(self):
            return self.returncode

        def wait(self, timeout):
            waits.append(self.pid)
            assert self.returncode is not None
            return self.returncode

    def spawn(command, **kwargs):
        commands.append(command)
        assert kwargs["start_new_session"] is True
        process = Process(100 + len(commands))
        processes.append(process)
        return process

    def send(child, signum):
        assert child["process"] in processes
        assert child["birth"] == identity(child["process"].pid)
        signals.append((child["process"].pid, int(signum)))
        child["process"].returncode = 0
        return "CPU_owned_child"

    def cleanup(children, output):
        return subject.close_children(children, output, send=send)

    def inventory():
        return {
            index: dict(uuid=uuid, free_mib=81159, occupied=False)
            for index, uuid in subject.GPUS.items()
        }

    def run(sleep, ttl=900):
        return subject.watch(
            tmp_path / "output",
            ttl,
            holder,
            stopped=lambda: state.stop,
            spawn=spawn,
            clock=lambda: state.time,
            sleep=sleep,
            identity=identity,
            inventory=inventory,
            cleanup=cleanup,
        )

    return SimpleNamespace(**locals())


@pytest.mark.parametrize(
    "trigger", ["progress", "waiters", "closeout", "worker_exit", "v46_exit", "stop", "ttl"]
)
def test_only_bound_idle_gpus_held_and_every_release_boundary_reaps_them(episode, trigger):
    e = episode
    if trigger == "v46_exit":
        subject.publish(e.handoff / "entry_launch/record.json", dict(pid=777, birth="queued-birth"))

    def sleep(seconds):
        e.state.time += seconds
        if trigger == "progress":
            e.update(183)
        elif trigger in ("waiters", "closeout"):
            marker = "waiters_registered" if trigger == "waiters" else "closeout"
            subject.publish(e.handoff / marker / "record.json", dict(CPU=True))
        elif trigger == "worker_exit":
            e.state.worker_alive = False
        elif trigger == "v46_exit":
            e.state.queued_alive = False
        elif trigger == "stop":
            e.state.stop = True

    result = e.run(sleep, ttl=1 if trigger == "ttl" else 900)
    assert result["status"] == "RESOURCE_HOLDS_RELEASED"
    assert result["children_launched"] == 2
    assert set(subject.GPUS) == {5, 7}
    assert [command[command.index("--gpu") + 1] for command in e.commands] == list(
        subject.GPUS.values()
    )
    for command in e.commands:
        assert "--lease-path" not in command and "--watch" not in command
        assert command[command.index("--mib") + 1] == "73728"
        assert 0 < int(command[command.index("--ttl") + 1]) <= 900
    assert e.waits == [101, 102]
    assert e.signals == [(101, 15), (102, 15)]
    assert all(
        row["actual_exit_observed"] and row["returncode"] == 0
        for row in result["actual_child_exits"]
    )
    assert result["project_gpu_leases_acquired"] is result["scientific_progress"] is False


def test_near_complete_progress_prevents_any_new_reservation(episode):
    e = episode
    e.update(183)
    result = e.run(lambda seconds: pytest.fail("must not wait"))
    assert result["children_launched"] == 0
    assert not e.commands and not e.signals


def test_release_condition_between_two_spawns_prevents_second_child(episode):
    e = episode
    original = e.spawn

    def spawn(command, **kwargs):
        process = original(command, **kwargs)
        e.update(183)
        return process

    result = subject.watch(
        e.tmp_path / "output",
        900,
        e.holder,
        spawn=spawn,
        clock=lambda: 0,
        identity=e.identity,
        inventory=e.inventory,
        cleanup=e.cleanup,
    )
    assert result["children_launched"] == 1
    assert e.waits == [101]


def test_failed_holder_releases_peer_without_retry(episode):
    e = episode

    def sleep(seconds):
        e.state.time += seconds
        e.processes[0].returncode = 1

    result = e.run(sleep)
    assert result["status"] == "RESERVATION_FAILURE"
    assert result["reason"] == "RESERVATION_CHILD_EXITED_NO_RETRY"
    assert len(e.commands) == 2 and e.waits == [101, 102]
    assert e.signals == [(102, 15)]


def test_nonidle_or_rebound_device_is_rejected_before_holder_spawn(monkeypatch):
    gpu5, gpu7 = subject.GPUS[5], subject.GPUS[7]
    answers = iter([f"5, {gpu5}, 81159\n7, {gpu7}, 81159\n", f"{gpu5}, 98765\n"])
    monkeypatch.setattr(subject.subprocess, "check_output", lambda *a, **k: next(answers))
    with pytest.raises(ValueError, match="fully idle"):
        subject.idle_inventory()


def test_pidfd_preferred_and_fallback_never_signals_recycled_pid(monkeypatch):
    sent = []
    process = SimpleNamespace(pid=123, poll=lambda: None, send_signal=lambda sig: sent.append(sig))
    monkeypatch.setattr(subject.signal, "pidfd_send_signal", lambda fd, sig: sent.append((fd, sig)))
    child = dict(process=process, pidfd=77, birth="original")
    assert subject.signal_owned(child, 15) == "pidfd"
    assert sent == [(77, 15)]
    child["pidfd"] = None
    with pytest.raises(ValueError, match="unverified"):
        subject.signal_owned(child, 15, identity=lambda pid: "recycled")
    assert sent == [(77, 15)]


def test_ttl_or_holder_source_cannot_expand(episode):
    e = episode
    with pytest.raises(ValueError, match="1..900"):
        e.run(lambda seconds: None, ttl=901)
    e.holder.write_text("# changed original holder\n")
    with pytest.raises(ValueError, match="holder bytes changed"):
        e.run(lambda seconds: None)
    assert not e.commands
