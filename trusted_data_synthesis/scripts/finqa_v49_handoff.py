"""CPU-only, dual-owner lease barrier for the native four-worker successor.

The sentinel receives all eight open-file descriptions before any lock waiter
starts.  Either manager or sentinel may die: the survivor keeps acquired locks
and stops the original uncapped supervisor before releasing them.  A simultaneous
loss of both independent owners is not claimed to be survivable.
"""

from __future__ import annotations

import argparse
import fcntl
import importlib
import math
import os
import select
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

import finqa_v41_handoff as base

GPUS = tuple(range(8))
SCHEMA = "v49_dual_owner_natural_cap_handoff.v1"
require, checked, publish = base.require, base.checked, base.publish
read, ref, check_ref = base.read, base.ref, base.check_ref
identity = base.process_identity


def entry(path):
    return dict(ref(path), id=checked(path)["id"])


def stamp():
    return base.timestamp(time.time())


def directory(root):
    return Path(root).resolve() / "handoff"


def same_process(expected, actual):
    return (
        actual is not None
        and actual["pid"] == expected["pid"]
        and str(actual["birth"]) == str(expected["birth"])
    )


def live(expected):
    return same_process(expected, identity(expected["pid"]))


def _signal_bound(expected):
    """A reused PID is never signalled; no bare-PID fallback."""
    actual = identity(expected["pid"])
    if not same_process(expected, actual):
        return False
    if "argv" in expected:
        require(actual == expected, "bound process command/uid changed")
    descriptor = base.open_pidfd(expected["pid"])
    try:
        require(identity(expected["pid"]) == actual, "process changed while opening pidfd")
        signal.pidfd_send_signal(descriptor, signal.SIGTERM)
    finally:
        os.close(descriptor)
    return True


def _attempt_roots(spec):
    parent = Path(spec["parent_supervision_root"])
    yield parent
    attempts = parent / "attempts"
    if attempts.exists():
        for candidate in sorted(attempts.glob("attempt[0-9]*")):
            if (candidate / "protocol/record.json").exists():
                yield candidate


def process_census(spec):
    """Include all registered attempts and workers, not only a queue snapshot."""
    controllers, workers = [], []
    for root in _attempt_roots(spec):
        protocol = checked(root / "protocol/record.json")
        require(
            Path(protocol["output_root"]).resolve() == root.resolve()
            and Path(protocol["supervision_root"]).resolve()
            == Path(spec["parent_supervision_root"]),
            "old attempt escaped its original supervision tree",
        )
        path = root / "launch_01/record.json"
        if path.exists():
            value = checked(path)
            require(value["protocol_id"] == protocol["id"], "foreign old controller launch")
            expected = dict(pid=value["pid"], birth=str(value["birth"]))
            actual = identity(value["pid"])
            if same_process(expected, actual):
                command = value.get("command")
                required_command = [
                    spec["supervisor_identity"]["argv"][0],
                    "-u",
                    str(root / "implementation/finqa_v48_controller.py"),
                    "run",
                    "--root",
                    str(root),
                ]
                require(
                    command == required_command
                    and command == actual["argv"]
                    and actual["uid"] == spec["supervisor_identity"]["uid"],
                    "old controller command/uid changed",
                )
                # Registration is under one original supervisor and a verified
                # protocol tree.  Carry the exact argv/uid into pidfd signalling.
                expected = actual
            controllers.append(expected)
        for subtree in ("contexts", "evaluations"):
            stages = root / subtree
            if not stages.exists():
                continue
            for path in sorted(stages.glob("**/launch/record.json")):
                value = checked(path)
                require(value["protocol_id"] == protocol["id"], "foreign old worker launch")
                workers.append(dict(pid=value["pid"], birth=str(value["birth"])))
    return dict(supervisor=spec["supervisor_identity"], controllers=controllers, workers=workers)


def old_execution_absent(spec):
    census = process_census(spec)
    return not any(
        live(value) for value in [census["supervisor"], *census["controllers"], *census["workers"]]
    )


def verify_release_authority(spec):
    """Normal release needs native cap4; a terminal stop cannot start science."""
    require(old_execution_absent(spec), "old execution remains alive")
    value = checked(directory(spec["root"]) / "release_authority/record.json")
    require(value["old_execution_absent"] is True, "release lacks stopped execution evidence")
    if value["mode"] == "NATIVE_FOUR_WORKER_SUCCESSOR":
        protocol = check_ref(value["new_protocol"])
        require(
            protocol.get("schema") == "v49_four_worker_supervised_protocol.v1"
            and protocol.get("output_root") == spec["root"]
            and protocol["max_gpu_workers"] == protocol["independent_total_worker_limit"] == 4
            and protocol["total_worker_limit_removed"] is False
            and protocol["gpu_admission_policy"]["admission"][
                "maximum_total_workers_including_initializing_and_draining"
            ]
            == 4,
            "normal lease release requires the frozen native four-worker protocol",
        )
    else:
        require(
            value["mode"] == "TERMINAL_STOP_NO_SUCCESSOR"
            and value["successor_launch_allowed"] is False,
            "unknown or nonterminal release authority",
        )
    return value


def stop_uncapped_until_absent(spec, *, sleep=time.sleep, on_wait=None):
    """Keep lease FDs open through this call; malformed evidence fails closed.

    Controllers may relay lawful SIGTERM to their own workers.  This helper
    never signals a scientific worker, never uses SIGKILL, and never restarts.
    """
    sent = set()
    while True:
        try:
            supervisor = spec["supervisor_identity"]
            key = (supervisor["pid"], str(supervisor["birth"]))
            if key not in sent and live(supervisor):
                _signal_bound(supervisor)
                sent.add(key)
            census = process_census(spec)
            for expected in [census["supervisor"], *census["controllers"]]:
                key = (expected["pid"], str(expected["birth"]))
                if key not in sent and live(expected):
                    _signal_bound(expected)
                    sent.add(key)
            if not any(
                live(value)
                for value in [census["supervisor"], *census["controllers"], *census["workers"]]
            ):
                return
            observation = dict(phase="FAIL_CLOSED_STOPPING_OLD_EXECUTION", signals=len(sent))
        except Exception as error:
            # Never let a failed diagnostic release the capacity constraint.
            observation = dict(
                phase="FAIL_CLOSED_EVIDENCE_WAIT", error_type=type(error).__name__, error=str(error)
            )
        if on_wait is not None:
            try:
                on_wait(observation)
            except Exception:
                pass
        sleep(1)


def latest_attempt(spec, *, clock=time.time):
    parent = Path(spec["parent_supervision_root"])
    require(live(spec["supervisor_identity"]), "original uncapped supervisor no longer alive")
    supervisor = read(parent / "supervisor/queue/status.json")
    require(
        supervisor.get("manual_stop_requested") is False, "old supervisor was explicitly stopped"
    )
    number = supervisor.get("attempt_number")
    require(type(number) is int and number >= 1, "invalid current attempt")
    root = parent if number == 1 else parent / "attempts" / f"attempt{number:04d}"
    if supervisor.get("phase") != "RUNNING":
        require(
            supervisor.get("phase")
            in {"BACKOFF_BEFORE_VERIFIED_RECOVERY", "WAITING_FOR_CHANGED_RECOVERY_CAPACITY"},
            "old supervision is terminal or unknown",
        )
        return None
    require(supervisor.get("attempt_root") == str(root), "current attempt escaped supervision root")
    dispatch_path = parent / "supervisor" / f"attempt{number:04d}" / "dispatch/record.json"
    dispatch = checked(dispatch_path)
    expected = dict(pid=dispatch["pid"], birth=str(dispatch["birth"]))
    require(
        same_process(expected, supervisor.get("child")),
        "live automatic attempt dispatch identity changed",
    )
    if not live(expected):
        # The fixed supervisor may not yet have published the child's actual
        # exit or its already-authorized safe recovery decision.
        return None
    if not (root / "launch_01/record.json").exists():
        # The bound supervisor may publish RUNNING while its new controller is
        # still checking the frozen package and has not written launch_01 yet.
        return None
    launch = checked(root / "launch_01/record.json")
    require(
        dispatch["attempt_number"] == number
        and dispatch["attempt_root"] == str(root)
        and launch["pid"] == expected["pid"]
        and str(launch["birth"]) == expected["birth"]
        and same_process(expected, supervisor.get("child"))
        and live(expected),
        "live controller/dispatch identity mismatch",
    )
    protocol = checked(root / "protocol/record.json")
    queue = read(root / "queue/status.json")
    require(
        queue["protocol_id"] == protocol["id"] == launch["protocol_id"], "old queue binding changed"
    )
    if queue.get("phase") == "REGISTERED_NOT_STARTED":
        require(
            queue.get("active_children") == [], "registered-only queue already contains workers"
        )
        return None
    require(-1 <= clock() - base.epoch(queue["at"]) <= 60, "old queue is stale")
    if number > 1:
        decision = checked(
            parent / "supervisor" / f"attempt{number - 1:04d}" / "recovery_decision/record.json"
        )
        require(
            decision.get("allowed") is True,
            "new old attempt lacks safe automatic-recovery approval",
        )
    return dict(
        root=root,
        number=number,
        queue=queue,
        protocol=protocol,
        controller_identity=expected,
        dispatch=entry(dispatch_path),
    )


def register(root, parent_root, authorization_ref=None):
    root, parent = Path(root).resolve(), Path(parent_root).resolve()
    require(root != parent, "new registration must not modify the old run")
    base.verify_pidfd_capability()
    protocol = checked(parent / "protocol/record.json")
    launch = checked(parent / "supervisor/launch/record.json")
    supervisor = identity(launch["pid"])
    require(same_process(launch, supervisor), "old supervisor is not the registered live process")
    require(
        protocol["allowed_gpu_indices"] == list(GPUS), "exact original eight device leases required"
    )
    authority = authorization_ref or entry(root / "authorization/record.json")
    check_ref(authority)
    spec = dict(
        schema=SCHEMA,
        at=stamp(),
        root=str(root),
        parent_supervision_root=str(parent),
        parent_protocol=entry(parent / "protocol/record.json"),
        supervisor_launch=entry(parent / "supervisor/launch/record.json"),
        supervisor_identity=supervisor,
        authorization=authority,
        training_root=protocol["training_root"],
        gpu_uuids=protocol["gpu_uuids"],
        cap=4,
        CPU_helpers_are_scientific_workers=False,
        initial_worker_signals_sent=0,
        two_independent_lock_owners=True,
        automatic_attempt_changes_follow_bound_original_supervisor=True,
    )
    latest_attempt(spec)
    return publish(directory(root) / "protocol/record.json", spec)


class DualOwnerBarrier:
    """All lease OFDs are shared with a sentinel before any waiter starts."""

    def __init__(self, spec, *, spawn=subprocess.Popen):
        self.spec, self.spawn = spec, spawn
        self.fds, self.paths, self.inodes, self.helpers = {}, {}, {}, {}
        self.held, self.sentinel, self.control = set(), None, None
        self.released = False

    def start(self):
        for gpu in GPUS:
            path = (
                Path(self.spec["training_root"])
                / "locks"
                / ("gpu-" + base.digest(self.spec["gpu_uuids"][str(gpu)]) + ".lock")
            )
            fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
            self.fds[gpu], self.paths[gpu] = fd, path
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode), "lease is not an existing regular file")
            self.inodes[gpu] = (info.st_dev, info.st_ino)
            require(
                (path.stat().st_dev, path.stat().st_ino) == self.inodes[gpu], "lease inode changed"
            )
        reader, writer = os.pipe()
        self.control = writer
        command = [
            sys.executable,
            "-u",
            str(Path(__file__).resolve()),
            "sentinel",
            "--root",
            self.spec["root"],
            "--control-fd",
            str(reader),
            "--lease-fds",
            ",".join(str(self.fds[gpu]) for gpu in GPUS),
        ]
        try:
            self.sentinel = self.spawn(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                pass_fds=(reader, *self.fds.values()),
            )
        finally:
            os.close(reader)
        ready = directory(self.spec["root"]) / "sentinel/ready/record.json"
        deadline = time.monotonic() + 30
        while not ready.exists():
            require(self.sentinel.poll() is None, "sentinel exited before readiness")
            require(time.monotonic() < deadline, "sentinel readiness timed out")
            time.sleep(0.02)
        receipt = checked(ready)
        require(
            receipt["pid"] == self.sentinel.pid
            and live(receipt)
            and receipt["inherited_lease_count"] == 8,
            "sentinel ownership receipt invalid",
        )
        for gpu in GPUS:
            process = self.spawn(
                [
                    sys.executable,
                    "-u",
                    str(Path(__file__).resolve()),
                    "waiter",
                    "--lock-fd",
                    str(self.fds[gpu]),
                    "--gpu",
                    str(gpu),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                pass_fds=(self.fds[gpu],),
            )
            self.helpers[gpu] = process

    def poll(self):
        require(
            self.sentinel is not None and self.sentinel.poll() is None,
            "sentinel unexpectedly exited",
        )
        for gpu, process in self.helpers.items():
            if gpu in self.held:
                continue
            code = process.poll()
            if code is None:
                continue
            raw = process.stdout.read()
            require(code == 0 and raw == b"ACQUIRED\n", "lease waiter failed without acquisition")
            info = self.paths[gpu].stat()
            require((info.st_dev, info.st_ino) == self.inodes[gpu], "project lease inode replaced")
            fcntl.flock(self.fds[gpu], fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.held.add(gpu)
        return self.snapshot()

    def snapshot(self):
        return dict(
            held_gpus=sorted(self.held),
            held_lease_count=len(self.held),
            enforced_maximum_old_workers=8 - len(self.held),
            requested_four_cap_active=len(self.held) >= 4,
            helpers=[
                dict(gpu=gpu, pid=p.pid, returncode=p.poll(), acquired=gpu in self.held)
                for gpu, p in self.helpers.items()
            ],
            sentinel_pid=self.sentinel.pid if self.sentinel else None,
            queued_helpers_are_not_claimed_as_held=True,
            CUDA_initialized=False,
        )

    @property
    def complete(self):
        return self.held == set(GPUS)

    def release_after_old_exit(self):
        verify_release_authority(self.spec)
        for process in self.helpers.values():
            if process.poll() is None:
                # All old users are absent, so every waiter can complete normally.
                process.wait(timeout=10)
            require(process.returncode == 0, "cannot release while a waiter failed")
        if self.sentinel is not None and self.sentinel.poll() is None:
            os.write(self.control, b"RELEASE\n")
            self.sentinel.wait(timeout=30)
            require(self.sentinel.returncode == 0, "sentinel refused safe release")
        self._close_fds()
        self.released = True

    def _close_fds(self):
        if self.control is not None:
            os.close(self.control)
            self.control = None
        for fd in self.fds.values():
            os.close(fd)
        self.fds.clear()
        for process in self.helpers.values():
            if process.stdout is not None:
                process.stdout.close()

    def fail_closed(self):
        # Manager must retain its copies even when the sentinel/helper was lost.
        stop_uncapped_until_absent(
            self.spec,
            on_wait=lambda body: base.status(
                directory(self.spec["root"]), dict(at=stamp(), **body, **self.snapshot())
            ),
        )
        authority = directory(self.spec["root"]) / "release_authority/record.json"
        if not authority.exists():
            publish(
                authority,
                dict(
                    at=stamp(),
                    mode="TERMINAL_STOP_NO_SUCCESSOR",
                    old_execution_absent=True,
                    successor_launch_allowed=False,
                ),
            )
        # Dead/failed helpers are not a scientific failure and need no retry.
        for process in self.helpers.values():
            if process.poll() is None:
                process.wait(timeout=30)
        if self.sentinel is not None and self.sentinel.poll() is None:
            os.write(self.control, b"RELEASE\n")
            self.sentinel.wait(timeout=30)
        self._close_fds()


def _sentinel(root, control_fd, lease_fds):
    spec = checked(directory(root) / "protocol/record.json")
    require(len(lease_fds) == 8 and len(set(lease_fds)) == 8, "sentinel needs all eight OFDs")
    for gpu, fd in zip(GPUS, lease_fds, strict=True):
        path = (
            Path(spec["training_root"])
            / "locks"
            / ("gpu-" + base.digest(spec["gpu_uuids"][str(gpu)]) + ".lock")
        )
        info, original = os.fstat(fd), path.stat()
        require(
            (info.st_dev, info.st_ino) == (original.st_dev, original.st_ino),
            "sentinel OFD binding changed",
        )
    stopped = []
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda signum, frame: stopped.append(signum))
    publish(
        directory(root) / "sentinel/ready/record.json",
        dict(
            at=stamp(),
            pid=os.getpid(),
            birth=identity(os.getpid())["birth"],
            inherited_lease_count=8,
            lease_inodes=[
                dict(gpu=gpu, device=os.fstat(fd).st_dev, inode=os.fstat(fd).st_ino)
                for gpu, fd in zip(GPUS, lease_fds, strict=True)
            ],
            CUDA_initialized=False,
        ),
    )
    buffer = b""
    while not stopped:
        ready, _, _ = select.select([control_fd], [], [], 1)
        if not ready:
            continue
        chunk = os.read(control_fd, 1024)
        if not chunk:
            break  # Manager death: inherited locks remain held by this process.
        buffer += chunk
        if buffer == b"RELEASE\n":
            verify_release_authority(spec)
            return
        require(len(buffer) <= 8 and b"\n" not in buffer, "invalid sentinel control message")
    stop_uncapped_until_absent(
        spec,
        on_wait=lambda body: base.status(directory(root) / "sentinel", dict(at=stamp(), **body)),
    )
    publish(
        directory(root) / "sentinel/fail_closed/record.json",
        dict(
            at=stamp(),
            old_execution_absent=True,
            manager_channel_closed=not stopped,
            received_signals=stopped,
            scientific_workers_signalled_directly=False,
        ),
    )


def _waiter(fd):
    fcntl.flock(fd, fcntl.LOCK_EX)
    print("ACQUIRED", flush=True)
    # Closing one duplicate must not unlock the shared open-file description.
    os.close(fd)


def _stopped_evidence(spec, current):
    parent = Path(spec["parent_supervision_root"])
    root, number = current["root"], current["number"]
    exited_path = parent / "supervisor" / f"attempt{number:04d}" / "actual_exit/record.json"
    exited, closed = checked(exited_path), checked(parent / "supervisor/closeout/record.json")
    require(
        exited["attempt_number"] == number
        and exited["attempt_root"] == str(root)
        and exited["manual_stop_requested"] is True
        and exited["stop_forwarded"] is True
        and same_process(current["controller_identity"], exited),
        "missing actual stopped-controller receipt",
    )
    require(
        closed["status"] == "STOPPED_BY_EXPLICIT_REQUEST"
        and closed["automatic_recovery_after_manual_stop"] is False
        and closed["final_attempt"] == number,
        "old automatic restart authority remains active",
    )
    queue = read(root / "queue/status.json")
    failure = checked(root / "failure/record.json")
    require(
        queue["active_children"] == []
        and queue["phase"] == "PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME"
        and failure["error_type"] == "DurablePause"
        and failure["error"] == "explicit safe stop requested"
        and failure["stop_error"] is None
        and failure["actual_progress_audit_error"] is None,
        "old execution did not stop at the clean natural boundary",
    )
    progress = checked(root / "actual_final_progress/record.json")
    require(
        progress["endpoint_scores_or_answers_read"] is False
        and progress["original_state_or_feedback_modified"] is False,
        "final state audit modified science",
    )
    return dict(
        supervisor_actual_controller_exit=entry(exited_path),
        supervisor_closeout=entry(parent / "supervisor/closeout/record.json"),
        actual_progress=entry(root / "actual_final_progress/record.json"),
        actual_final_progress=entry(root / "actual_final_progress/record.json"),
        parent_final_queue=ref(root / "queue/status.json"),
        global_resource_wait_seconds=math.ceil(queue["global_external_resource_wait_seconds"]),
    )


def clean_receipt_body(root, spec, current, *, elapsed_seconds):
    """The production producer, also exercised against the inheritance consumer."""
    evidence = _stopped_evidence(spec, current)
    return dict(
        schema="v49_clean_natural_handoff.v1",
        status="CLEAN_NATURAL_HANDOFF",
        at=stamp(),
        parent_root=str(current["root"]),
        parent_attempt_root=str(current["root"]),
        parent_supervision_root=spec["parent_supervision_root"],
        parent_protocol=entry(current["root"] / "protocol/record.json"),
        controller_launch=entry(current["root"] / "launch_01/record.json"),
        supervisor_launch=spec["supervisor_launch"],
        preflight=entry(directory(root) / "preflight/record.json"),
        all_gpu_locks_held=list(GPUS),
        fresh_empty_queue_verified=True,
        controller_original_process_exited=True,
        supervisor_original_process_exited=True,
        supervisor_signal_sent=True,
        supervisor_signals_sent=1,
        worker_signals_sent=0,
        launched_workers_all_complete_and_exit_zero=True,
        handoff_elapsed_seconds=elapsed_seconds,
        handoff_elapsed_not_added_again_to_parent_wait=True,
        **evidence,
    )


def run(
    root,
    *,
    control=None,
    supervisor_factory=None,
    barrier_factory=DualOwnerBarrier,
    sleep=time.sleep,
    clock=time.time,
):
    root = Path(root).resolve()
    control = control or importlib.import_module("finqa_v49_controller")
    supervisor_factory = (
        supervisor_factory or importlib.import_module("finqa_v49_supervisor").Supervisor
    )
    spec = checked(directory(root) / "protocol/record.json")
    require(spec["schema"] == SCHEMA and spec["root"] == str(root), "unregistered cap handoff")
    control.checked_implementation(root)
    check_ref(spec["authorization"])
    require(
        Path(__file__).resolve() == root / "implementation/finqa_v49_handoff.py",
        "only frozen handoff may execute",
    )
    stopped = []
    prior_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    for sig in prior_handlers:
        signal.signal(sig, lambda signum, frame: stopped.append(signum))
    barrier, native_ready, start, owns_registration = barrier_factory(spec), False, clock(), False
    (directory(root)).mkdir(parents=True, exist_ok=True)
    try:
        with (directory(root) / "owner.lock").open("a") as owner:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            publish(
                directory(root) / "launch/record.json",
                dict(
                    schema=SCHEMA,
                    at=stamp(),
                    pid=os.getpid(),
                    birth=identity(os.getpid())["birth"],
                    worker_signals_sent=0,
                ),
            )
            owns_registration = True
            require(not stopped, "explicit stop before cap acquisition")
            barrier.start()
            acquired_at = None
            while True:
                require(not stopped, "explicit stop during cap handoff")
                snapshot = barrier.poll()
                cap_record = directory(root) / "four_worker_cap_active/record.json"
                if len(barrier.held) >= 4 and not cap_record.exists():
                    publish(
                        cap_record,
                        dict(
                            at=stamp(),
                            actual_acquired_lease_evidence=snapshot,
                            cap4_enforced_by_real_project_leases=True,
                            initializing_and_draining_included=True,
                            kernel_queue_is_not_ownership=True,
                        ),
                    )
                current = latest_attempt(spec, clock=clock)
                if barrier.complete and acquired_at is None:
                    acquired_at = clock()
                    publish(
                        directory(root) / "barrier_acquired/record.json",
                        dict(
                            at=stamp(),
                            acquired_epoch=acquired_at,
                            all_gpu_locks_held=list(GPUS),
                            **snapshot,
                        ),
                    )
                base.status(
                    directory(root),
                    dict(
                        at=stamp(),
                        phase="DRAINING_NATURALLY",
                        **snapshot,
                        parent_attempt_root=str(current["root"]) if current else None,
                        active_children=current["queue"]["active_children"] if current else [],
                        worker_signals_sent=0,
                        supervisor_signals_sent=0,
                    ),
                )
                if (
                    current is None
                    or not barrier.complete
                    or current["queue"]["active_children"]
                    or base.epoch(current["queue"]["at"]) <= acquired_at
                ):
                    sleep(2)
                    continue
                audit = control.inheritance.preflight_clean_handoff(
                    current["root"], current["queue"]
                )
                require(
                    audit["status"] == "CLEAN_NATURAL_WORKER_BOUNDARY", "unsafe natural boundary"
                )
                publish(directory(root) / "preflight/record.json", dict(at=stamp(), **audit))
                require(not stopped, "explicit stop before legal supervisor handoff")
                fresh = latest_attempt(spec, clock=clock)
                require(
                    fresh is not None
                    and fresh["root"] == current["root"]
                    and fresh["controller_identity"] == current["controller_identity"]
                    and fresh["queue"]["active_children"] == []
                    and barrier.complete,
                    "attempt changed before legal supervisor handoff",
                )
                require(
                    _signal_bound(spec["supervisor_identity"]),
                    "supervisor exited before handoff signal",
                )
                publish(
                    directory(root) / "supervisor_signal/record.json",
                    dict(
                        at=stamp(),
                        target=spec["supervisor_identity"],
                        signals_sent=1,
                        worker_signals_sent=0,
                    ),
                )
                while not old_execution_absent(spec):
                    require(not stopped, "explicit stop while old supervisor exits")
                    barrier.poll()
                    sleep(1)
                receipt_path = directory(root) / "closeout/record.json"
                publish(
                    receipt_path,
                    clean_receipt_body(root, spec, current, elapsed_seconds=clock() - start),
                )
                require(not stopped, "explicit stop before successor initialization")
                protocol = control.initialize_with_handoff(receipt_path, root=root)
                require(
                    protocol["max_gpu_workers"] == 4
                    and protocol["independent_total_worker_limit"] == 4
                    and protocol["total_worker_limit_removed"] is False,
                    "successor did not freeze native cap4",
                )
                control.checked_protocol(root)
                require(not stopped, "explicit stop before lease release")
                publish(
                    directory(root) / "release_authority/record.json",
                    dict(
                        at=stamp(),
                        mode="NATIVE_FOUR_WORKER_SUCCESSOR",
                        old_execution_absent=True,
                        new_protocol=entry(root / "protocol/record.json"),
                    ),
                )
                barrier.release_after_old_exit()
                native_ready = True
                publish(
                    directory(root) / "barrier_release/record.json",
                    dict(
                        at=stamp(),
                        old_execution_absent=True,
                        native_cap=4,
                        protocol=entry(root / "protocol/record.json"),
                    ),
                )
                break
    except BaseException as error:
        if not owns_registration:
            raise
        barrier.fail_closed()
        failure_path = directory(root) / "failure/record.json"
        if not failure_path.exists():
            publish(
                failure_path,
                dict(
                    at=stamp(),
                    status="STOPPED_FAIL_CLOSED_NO_AUTOMATIC_HANDOFF_RETRY",
                    error_type=type(error).__name__,
                    error=str(error),
                    old_execution_absent=True,
                    explicit_stop=bool(stopped),
                    automatic_restart=False,
                ),
            )
        raise
    finally:
        for sig, handler in prior_handlers.items():
            signal.signal(sig, handler)
    require(native_ready and not stopped, "native successor cannot start after a stop")
    return supervisor_factory(root).run()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "sentinel", "waiter"))
    parser.add_argument("--root", type=Path)
    parser.add_argument("--control-fd", type=int)
    parser.add_argument("--lease-fds")
    parser.add_argument("--lock-fd", type=int)
    parser.add_argument("--gpu", type=int, choices=GPUS)
    args = parser.parse_args()
    if args.action == "waiter":
        _waiter(args.lock_fd)
    elif args.action == "sentinel":
        _sentinel(args.root, args.control_fd, tuple(map(int, args.lease_fds.split(","))))
    else:
        run(args.root)


if __name__ == "__main__":
    main()
