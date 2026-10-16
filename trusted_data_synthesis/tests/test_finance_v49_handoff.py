"""CPU-only lease tests; all processes and lock inodes belong to tmp_path."""

import fcntl
import importlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
h = importlib.import_module("finqa_v49_handoff")


def until(predicate, timeout=10):
    end = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < end, "CPU-only ownership test timed out"
        time.sleep(0.01)


def own(path):
    fd = os.open(path, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        os.close(fd)
        raise
    return fd


def unavailable(path):
    try:
        fd = own(path)
    except BlockingIOError:
        return True
    os.close(fd)
    return False


@pytest.fixture
def case(tmp_path):
    root, parent, training = tmp_path / "new", tmp_path / "old", tmp_path / "training"
    (training / "locks").mkdir(parents=True)
    uuids = {str(gpu): f"CPU-ONLY-{gpu}" for gpu in h.GPUS}
    paths = {
        gpu: training / "locks" / ("gpu-" + h.base.digest(uuids[str(gpu)]) + ".lock")
        for gpu in h.GPUS
    }
    for path in paths.values():
        path.write_text("original CPU-only test inode\n")
    protocol = h.publish(
        parent / "protocol/record.json",
        dict(
            output_root=str(parent),
            supervision_root=str(parent),
            allowed_gpu_indices=list(h.GPUS),
            training_root=str(training),
            gpu_uuids=uuids,
        ),
    )
    processes = []

    def dummy(script="import time; time.sleep(60)", command=None):
        process = subprocess.Popen(command or [sys.executable, "-c", script])
        processes.append(process)
        until(lambda: h.identity(process.pid) is not None)
        return process, h.identity(process.pid)

    supervisor, supervisor_identity = dummy()
    controller_script = parent / "implementation/finqa_v48_controller.py"
    controller_script.parent.mkdir(parents=True)
    controller_script.write_text("import time; time.sleep(60)\n")
    controller, controller_identity = dummy(
        command=[sys.executable, "-u", str(controller_script), "run", "--root", str(parent)]
    )
    h.publish(
        parent / "launch_01/record.json",
        dict(
            protocol_id=protocol["id"], command=controller_identity["argv"], **controller_identity
        ),
    )
    h.publish(parent / "supervisor/launch/record.json", supervisor_identity)
    (parent / "supervisor/queue").mkdir()
    spec = h.publish(
        h.directory(root) / "protocol/record.json",
        dict(
            schema=h.SCHEMA,
            root=str(root),
            parent_supervision_root=str(parent),
            supervisor_identity=supervisor_identity,
            gpu_uuids=uuids,
            training_root=str(training),
        ),
    )
    yield dict(
        root=root,
        parent=parent,
        spec=spec,
        paths=paths,
        dummy=dummy,
        supervisor=supervisor,
        controller=controller,
        protocol=protocol,
    )
    # Only test-owned processes; never a scientific or external PID.
    for process in processes:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=5)


def stop_owned_old(case):
    for key in ("supervisor", "controller"):
        case[key].terminate()
        case[key].wait(timeout=5)


def terminal_release(case):
    h.publish(
        h.directory(case["root"]) / "release_authority/record.json",
        dict(
            mode="TERMINAL_STOP_NO_SUCCESSOR",
            old_execution_absent=True,
            successor_launch_allowed=False,
        ),
    )


def test_actual_acquisitions_not_queued_waiters_define_four_cap(case):
    prior = {gpu: own(path) for gpu, path in case["paths"].items()}
    barrier = h.DualOwnerBarrier(case["spec"])
    try:
        barrier.start()
        assert barrier.poll()["held_lease_count"] == 0
        assert not barrier.snapshot()["requested_four_cap_active"]
        for gpu in (0, 1, 2, 3):
            os.close(prior.pop(gpu))
        until(lambda: (barrier.poll(), len(barrier.held) == 4)[1])
        assert barrier.snapshot()["enforced_maximum_old_workers"] == 4
        assert barrier.snapshot()["requested_four_cap_active"]
        assert all(unavailable(path) for path in case["paths"].values())
        # Every helper inherited only its own lease, never the sentinel pipe.
        lock_names = {str(path) for path in case["paths"].values()}
        for gpu in (4, 5, 6, 7):
            fds = {os.readlink(p) for p in Path(f"/proc/{barrier.helpers[gpu].pid}/fd").iterdir()}
            assert fds & lock_names == {str(case["paths"][gpu])}
            assert not any(name == os.readlink(f"/proc/self/fd/{barrier.control}") for name in fds)
    finally:
        for fd in prior.values():
            os.close(fd)
        stop_owned_old(case)
        terminal_release(case)
        barrier.release_after_old_exit()
    assert all(not unavailable(path) for path in case["paths"].values())


def test_normal_release_needs_actual_exit_and_native_four_protocol(case):
    protocol = h.publish(
        case["root"] / "protocol/record.json",
        dict(
            max_gpu_workers=4,
            schema="v49_four_worker_supervised_protocol.v1",
            output_root=str(case["root"]),
            independent_total_worker_limit=4,
            total_worker_limit_removed=False,
            gpu_admission_policy=dict(
                admission=dict(maximum_total_workers_including_initializing_and_draining=4)
            ),
        ),
    )
    h.publish(
        h.directory(case["root"]) / "release_authority/record.json",
        dict(
            mode="NATIVE_FOUR_WORKER_SUCCESSOR",
            old_execution_absent=True,
            new_protocol=h.entry(case["root"] / "protocol/record.json"),
        ),
    )
    with pytest.raises(h.base.HandoffError, match="alive"):
        h.verify_release_authority(case["spec"])
    stop_owned_old(case)
    assert h.verify_release_authority(case["spec"])["new_protocol"]["id"] == protocol["id"]


def test_uncapped_protocol_cannot_authorize_normal_release(case):
    stop_owned_old(case)
    h.publish(
        case["root"] / "protocol/record.json",
        dict(
            max_gpu_workers=None,
            independent_total_worker_limit=None,
            total_worker_limit_removed=True,
        ),
    )
    h.publish(
        h.directory(case["root"]) / "release_authority/record.json",
        dict(
            mode="NATIVE_FOUR_WORKER_SUCCESSOR",
            old_execution_absent=True,
            new_protocol=h.entry(case["root"] / "protocol/record.json"),
        ),
    )
    with pytest.raises(h.base.HandoffError, match="native four"):
        h.verify_release_authority(case["spec"])


def test_manager_process_exit_leaves_sentinel_holding_until_all_old_workers_exit(case):
    allow_exit = case["root"] / "allow_owned_worker_exit"
    worker, bound = case["dummy"](
        "import pathlib,time; p=pathlib.Path(" + repr(str(allow_exit)) + "); "
        "exec('while not p.exists(): time.sleep(.02)')"
    )
    h.publish(
        case["parent"] / "contexts/seed1/full/step1/train/launch/record.json",
        dict(protocol_id=case["protocol"]["id"], **bound),
    )
    code = """
import os,sys,time
sys.path.insert(0,sys.argv[1])
import finqa_v49_handoff as h
b=h.DualOwnerBarrier(h.checked(h.directory(sys.argv[2])/'protocol/record.json'))
b.start()
while not b.complete:
    b.poll(); time.sleep(.01)
print('READY',flush=True)
os._exit(0)
"""
    manager = subprocess.Popen(
        [sys.executable, "-u", "-c", code, str(SCRIPTS), str(case["root"])],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert manager.stdout.readline().strip() == "READY"
        assert manager.wait(timeout=10) == 0
        until(
            lambda: case["supervisor"].poll() is not None and case["controller"].poll() is not None
        )
        assert worker.poll() is None
        # Manager and acquisition helpers are gone: these OFDs belong to sentinel.
        assert all(unavailable(path) for path in case["paths"].values())
        sentinel = h.checked(h.directory(case["root"]) / "sentinel/ready/record.json")
        assert h.live(sentinel)
        allow_exit.touch()
        assert worker.wait(timeout=5) == 0
        until(lambda: not h.live(sentinel))
        assert all(not unavailable(path) for path in case["paths"].values())
        record = h.checked(h.directory(case["root"]) / "sentinel/fail_closed/record.json")
        assert record["old_execution_absent"] and record["manager_channel_closed"]
    finally:
        allow_exit.touch()
        if manager.poll() is None:
            manager.terminate()
            manager.wait(timeout=10)


def test_sentinel_death_keeps_parent_fds_and_triggers_fail_closed(case):
    barrier = h.DualOwnerBarrier(case["spec"])
    barrier.start()
    until(lambda: (barrier.poll(), barrier.complete)[1])
    # Deliberate failure of our owned CPU test sentinel, never a worker.
    barrier.sentinel.kill()
    barrier.sentinel.wait(timeout=5)
    with pytest.raises(h.base.HandoffError, match="sentinel unexpectedly"):
        barrier.poll()
    assert all(unavailable(path) for path in case["paths"].values())
    barrier.fail_closed()
    assert case["supervisor"].wait(timeout=5) < 0
    assert case["controller"].wait(timeout=5) < 0
    assert all(not unavailable(path) for path in case["paths"].values())


def test_helper_failure_does_not_remove_parent_or_sentinel_ownership(case):
    prior = own(case["paths"][7])
    barrier = h.DualOwnerBarrier(case["spec"])
    try:
        barrier.start()
        until(lambda: (barrier.poll(), len(barrier.held) == 7)[1])
        barrier.helpers[7].terminate()
        barrier.helpers[7].wait(timeout=5)
        with pytest.raises(h.base.HandoffError, match="waiter failed"):
            barrier.poll()
        assert all(unavailable(case["paths"][gpu]) for gpu in range(7))
    finally:
        os.close(prior)
        barrier.fail_closed()
    assert all(not unavailable(path) for path in case["paths"].values())


def test_pidfd_bound_dummy_stop_supports_libc_fallback(case, monkeypatch):
    # Mirrors the registered venv where os.pidfd_open is not exported.
    monkeypatch.delattr(os, "pidfd_open", raising=False)
    process, bound = case["dummy"]()
    assert h._signal_bound(bound)
    assert process.wait(timeout=5) == -signal.SIGTERM
    assert not h._signal_bound(bound)  # Never signal an exited/reused PID.


def test_stop_observation_error_does_not_release_owned_lease(case, monkeypatch):
    fd = own(case["paths"][0])
    original, calls = h.process_census, []

    def flaky(spec):
        calls.append(1)
        if len(calls) == 1:
            raise PermissionError("CPU mock inaccessible process evidence")
        return original(spec)

    monkeypatch.setattr(h, "process_census", flaky)
    try:
        h.stop_uncapped_until_absent(
            case["spec"],
            sleep=lambda _: time.sleep(0.01),
            on_wait=lambda _: unavailable(case["paths"][0]) or pytest.fail("lease lost"),
        )
        assert len(calls) >= 2
        assert unavailable(case["paths"][0])
    finally:
        os.close(fd)


def test_same_process_rejects_reused_pid():
    assert not h.same_process(dict(pid=123, birth="a"), dict(pid=123, birth="b"))
    assert not h.same_process(dict(pid=123, birth="a"), None)


def test_endpoint_worker_counts_until_actual_exit(case):
    worker, bound = case["dummy"]()
    h.publish(
        case["parent"] / "evaluations/seed1/full/generate/launch/record.json",
        dict(protocol_id=case["protocol"]["id"], **bound),
    )
    stop_owned_old(case)
    assert not h.old_execution_absent(case["spec"])
    worker.terminate()
    worker.wait(timeout=5)
    assert h.old_execution_absent(case["spec"])


def test_backoff_status_without_attempt_root_is_a_safe_wait(case):
    status = case["parent"] / "supervisor/queue/status.json"
    status.write_text(
        json.dumps(
            dict(
                phase="BACKOFF_BEFORE_VERIFIED_RECOVERY",
                attempt_number=1,
                manual_stop_requested=False,
            )
        )
    )
    assert h.latest_attempt(case["spec"]) is None


def test_auto_controller_initial_launch_publication_is_a_safe_wait(case):
    dispatch = h.publish(
        case["parent"] / "supervisor/attempt0001/dispatch/record.json",
        dict(
            attempt_number=1,
            attempt_root=str(case["parent"]),
            pid=case["controller"].pid,
            birth=h.identity(case["controller"].pid)["birth"],
        ),
    )
    (case["parent"] / "supervisor/queue/status.json").write_text(
        json.dumps(
            dict(
                phase="RUNNING",
                attempt_number=1,
                attempt_root=str(case["parent"]),
                manual_stop_requested=False,
                child={key: dispatch[key] for key in ("pid", "birth")},
            )
        )
    )
    # Only this fixture's fake launch is hidden to model the startup window.
    launch = case["parent"] / "launch_01/record.json"
    launch.rename(launch.with_name("saved.json"))
    assert h.latest_attempt(case["spec"]) is None


def test_registered_queue_is_not_misclassified_as_a_stale_live_queue(case):
    dispatch = h.publish(
        case["parent"] / "supervisor/attempt0001/dispatch/record.json",
        dict(
            attempt_number=1,
            attempt_root=str(case["parent"]),
            pid=case["controller"].pid,
            birth=h.identity(case["controller"].pid)["birth"],
        ),
    )
    (case["parent"] / "supervisor/queue/status.json").write_text(
        json.dumps(
            dict(
                phase="RUNNING",
                attempt_number=1,
                attempt_root=str(case["parent"]),
                manual_stop_requested=False,
                child={key: dispatch[key] for key in ("pid", "birth")},
            )
        )
    )
    queue = case["parent"] / "queue/status.json"
    queue.parent.mkdir()
    queue.write_text(
        json.dumps(
            dict(
                phase="REGISTERED_NOT_STARTED",
                at="2000-01-01T00:00:00+00:00",
                protocol_id=case["protocol"]["id"],
                active_children=[],
            )
        )
    )
    assert h.latest_attempt(case["spec"]) is None
