"""Cancellable kernel-waiting project leases; helpers never initialize a GPU.

Each short-lived helper inherits exactly one parent-opened lock description.
After blocking flock succeeds, helper exit leaves that same description held by
the parent. No file is replaced and no scientific process receives a signal.
Linux flock does not promise FIFO ordering: this removes polling blind spots,
not the possibility of an adversarial immediate lock reacquisition.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import fcntl
import hashlib
import json
import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

GPUS = tuple(range(8))
SCHEMA = "v46_same_ofd_queued_gpu_barrier.v1"
CANCEL_GRACE_SECONDS = 2.0
KILL_GRACE_SECONDS = 2.0


class BarrierError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise BarrierError(message)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def birth(pid):
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
    except FileNotFoundError:
        return None
    return raw[raw.rfind(")") + 2 :].split()[19]


def lock_path(training_root, uuid):
    return Path(training_root) / "locks" / ("gpu-" + digest(uuid) + ".lock")


def open_pidfd(pid):
    """Use native or libc pidfd_open, never a bare-PID signal fallback."""
    require(type(pid) is int and 0 < pid <= 2**31 - 1, "positive signed pid_t required")
    native = getattr(os, "pidfd_open", None)
    if callable(native):
        return native(pid, 0)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        exported = libc.pidfd_open
    except (AttributeError, OSError) as exc:
        raise BarrierError("pidfd_open is unavailable") from exc
    exported.argtypes, exported.restype = (ctypes.c_int, ctypes.c_uint), ctypes.c_int
    ctypes.set_errno(0)
    descriptor = exported(pid, 0)
    if descriptor < 0:
        code = ctypes.get_errno() or errno.EIO
        raise OSError(code, os.strerror(code))
    return descriptor


def _kernel_waiters():
    """Read actual blocked flock entries, not userspace about-to-call messages."""
    rows = []
    for line in Path("/proc/locks").read_text().splitlines():
        fields = line.split()
        if len(fields) < 9 or fields[1:5] != ["->", "FLOCK", "ADVISORY", "WRITE"]:
            continue
        major, minor, inode = fields[6].split(":")
        rows.append(
            dict(
                pid=int(fields[5]),
                device_major=int(major, 16),
                device_minor=int(minor, 16),
                inode=int(inode),
            )
        )
    return rows


class QueuedBarrier:
    """Eight owned CPU helpers, then parent-only lock ownership.

    Call ``waiters_ready(required_gpus)`` before stopping an old migration that
    currently owns those leases. Pipe WAITING and kernel-blocked are separate
    observations. ``close`` cancels/reaps helpers before closing parent copies.
    """

    def __init__(self, training_root, gpu_uuids):
        self.paths = {
            int(gpu): lock_path(training_root, uuid) for gpu, uuid in gpu_uuids.items()
        }
        require(tuple(sorted(self.paths)) == GPUS, "barrier requires exactly the eight GPU locks")
        self.held, self.waiters = {}, {}
        self.started = self.closed = self.closing = False
        self.parent_pid, self.parent_birth = os.getpid(), birth(os.getpid())
        self.cancel_started = None

    def start_waiters(self):
        require(not self.started and not self.closed, "queued barrier may start exactly once")
        require(
            callable(getattr(signal, "pidfd_send_signal", None)),
            "pidfd cancellation support is required",
        )
        capability = open_pidfd(os.getpid())
        os.close(capability)
        self.started = True
        try:
            for gpu in GPUS:
                path = self.paths[gpu]
                # Existing lock inode only: never create, unlink or replace it.
                fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
                info = os.fstat(fd)
                row = dict(
                    fd=fd,
                    device=info.st_dev,
                    device_major=os.major(info.st_dev),
                    device_minor=os.minor(info.st_dev),
                    inode=info.st_ino,
                    process=None,
                    pidfd=None,
                    birth=None,
                    buffer=b"",
                    records=[],
                    cancel_signal=None,
                    exit=None,
                )
                self.waiters[gpu] = row
                require(stat.S_ISREG(info.st_mode), "project lease is not a regular file")
                require(
                    (path.stat().st_dev, path.stat().st_ino) == (info.st_dev, info.st_ino),
                    "project lock inode changed during open",
                )
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-u",
                        str(Path(__file__).resolve()),
                        "--helper",
                        "--lock-fd",
                        str(fd),
                        "--gpu",
                        str(gpu),
                        "--parent-pid",
                        str(self.parent_pid),
                        "--parent-birth",
                        self.parent_birth,
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                    pass_fds=(fd,),
                )
                row["process"] = process
                row["pidfd"] = open_pidfd(process.pid)
                row["birth"] = birth(process.pid)
                require(row["birth"] is not None, "helper identity unavailable after launch")
                os.set_blocking(process.stdout.fileno(), False)
        except BaseException:
            self.close()
            raise
        return self.snapshot()

    def _read(self, gpu, row):
        process = row["process"]
        while True:
            try:
                part = os.read(process.stdout.fileno(), 4096)
            except BlockingIOError:
                break
            if not part:
                break
            row["buffer"] += part
            require(len(row["buffer"]) <= 8192, "helper receipt exceeded registered bound")
        while b"\n" in row["buffer"]:
            line, row["buffer"] = row["buffer"].split(b"\n", 1)
            receipt = json.loads(line)
            expected = "WAITING" if not row["records"] else "ACQUIRED"
            require(
                len(row["records"]) < 2
                and receipt
                == dict(
                    schema=SCHEMA,
                    event=expected,
                    gpu=gpu,
                    pid=process.pid,
                    birth=row["birth"],
                    parent_pid=self.parent_pid,
                    parent_birth=self.parent_birth,
                    device=row["device"],
                    inode=row["inode"],
                    gpu_initialized=False,
                ),
                "helper event or original inode/process binding changed",
            )
            row["records"].append(receipt)

    def acquire_available(self):
        require(not self.closed and not self.closing, "queued barrier already closing")
        if not self.started:
            self.start_waiters()
        acquired = []
        for gpu, row in self.waiters.items():
            if gpu in self.held:
                continue
            self._read(gpu, row)
            process = row["process"]
            code = process.poll()
            row["exit"] = code
            if code is None:
                continue
            # A final read handles exit between the preceding read and waitpid.
            self._read(gpu, row)
            require(
                code == 0 and len(row["records"]) == 2 and not row["buffer"],
                "queued lock helper exited without its complete acquisition receipt",
            )
            require(
                (self.paths[gpu].stat().st_dev, self.paths[gpu].stat().st_ino)
                == (row["device"], row["inode"]),
                "original project lock inode changed before acquisition",
            )
            # This is the SAME open-file description used by the exited helper.
            fcntl.flock(row["fd"], fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.held[gpu] = row["fd"]
            acquired.append(gpu)
        return acquired

    @property
    def complete(self):
        return not self.closed and tuple(sorted(self.held)) == GPUS

    def snapshot(self):
        kernel = _kernel_waiters() if self.started and not self.closed else []
        rows = []
        for gpu, row in sorted(self.waiters.items()):
            process = row["process"]
            identity = dict(
                pid=process.pid if process is not None else None,
                device_major=row["device_major"],
                device_minor=row["device_minor"],
                inode=row["inode"],
            )
            rows.append(
                dict(
                    gpu=gpu,
                    path=str(self.paths[gpu]),
                    **identity,
                    birth=row["birth"],
                    waiting_pipe_receipt=bool(row["records"]),
                    acquired_pipe_receipt=len(row["records"]) == 2,
                    kernel_queued=identity in kernel,
                    held_by_parent_same_open_description=gpu in self.held,
                    actual_helper_exit=row["exit"],
                    cancellation_signal=row["cancel_signal"],
                    scientific_worker=False,
                    gpu_initialized=False,
                )
            )
        return dict(
            schema=SCHEMA,
            started=self.started,
            closed=self.closed,
            helpers=rows,
            held_gpus=sorted(self.held),
            helper_gpu_worker_count=0,
            helper_role="CPU_only_project_lock_coordination",
            kernel_fifo_guaranteed=False,
        )

    def waiters_ready(self, required_gpus=None):
        required = set(GPUS if required_gpus is None else required_gpus)
        require(required <= set(GPUS), "unknown GPU in waiter readiness request")
        self.acquire_available()
        rows = {row["gpu"]: row for row in self.snapshot()["helpers"]}
        return all(
            gpu in rows
            and (
                rows[gpu]["held_by_parent_same_open_description"]
                or (rows[gpu]["waiting_pipe_receipt"] and rows[gpu]["kernel_queued"])
            )
            for gpu in required
        )

    def _signal_helpers(self, signum):
        for row in self.waiters.values():
            process = row["process"]
            if process is None or process.poll() is not None:
                continue
            # Only direct children created above; never a caller-supplied PID.
            if row["pidfd"] is None:
                row["pidfd"] = open_pidfd(process.pid)
            try:
                signal.pidfd_send_signal(row["pidfd"], signum)
                row["cancel_signal"] = signum
            except ProcessLookupError:
                pass

    def _reap(self, deadline):
        pending = []
        for row in self.waiters.values():
            process = row["process"]
            if process is None:
                continue
            try:
                row["exit"] = process.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pending.append(row)
        return pending

    def close(self):
        if self.closed:
            return
        self.closing = True
        if self.cancel_started is None:
            self.cancel_started = time.monotonic()
        error = None
        try:
            self._signal_helpers(signal.SIGTERM)
            pending = self._reap(self.cancel_started + CANCEL_GRACE_SECONDS)
            if pending:
                self._signal_helpers(signal.SIGKILL)
                pending = self._reap(
                    self.cancel_started + CANCEL_GRACE_SECONDS + KILL_GRACE_SECONDS
                )
            require(not pending, "owned lock helper failed to exit after bounded cancellation")
        except BaseException as exc:
            error = exc
            # Fail closed even if observation/reaping fails; entry must stop.
            # PDEATHSIG is a second safeguard if entry subsequently exits.
            try:
                self._signal_helpers(signal.SIGKILL)
                self._reap(self.cancel_started + CANCEL_GRACE_SECONDS + KILL_GRACE_SECONDS)
            except BaseException:
                pass
        finally:
            for row in self.waiters.values():
                process = row["process"]
                if process is not None and process.stdout is not None:
                    try:
                        process.stdout.close()
                    except BaseException as exc:
                        error = error or exc
                for key in ("fd", "pidfd"):
                    if row[key] is not None:
                        try:
                            os.close(row[key])
                        except BaseException as exc:
                            error = error or exc
                        row[key] = None
            self.held.clear()
            self.closed = True
        if error is not None:
            raise error


Barrier = QueuedBarrier


def _helper(fd, gpu, parent_pid, parent_birth):
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    libc = ctypes.CDLL(None, use_errno=True)
    # If the entry dies while flock blocks, the child exits and drops its copy.
    require(libc.prctl(1, signal.SIGTERM, 0, 0, 0) == 0, "cannot bind helper parent death")
    require(
        os.getppid() == parent_pid and birth(parent_pid) == parent_birth,
        "helper parent changed before parent-death binding",
    )
    info = os.fstat(fd)
    require(stat.S_ISREG(info.st_mode), "helper inherited a non-regular lock")
    body = dict(
        schema=SCHEMA,
        gpu=gpu,
        pid=os.getpid(),
        birth=birth(os.getpid()),
        parent_pid=parent_pid,
        parent_birth=parent_birth,
        device=info.st_dev,
        inode=info.st_ino,
        gpu_initialized=False,
    )
    print(json.dumps(dict(body, event="WAITING")), flush=True)
    fcntl.flock(fd, fcntl.LOCK_EX)
    print(json.dumps(dict(body, event="ACQUIRED")), flush=True)
    # Never LOCK_UN: parent owns another descriptor for this same lock.
    os.close(fd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--helper", action="store_true", required=True)
    parser.add_argument("--lock-fd", type=int, required=True)
    parser.add_argument("--gpu", type=int, choices=GPUS, required=True)
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--parent-birth", required=True)
    args = parser.parse_args()
    _helper(args.lock_fd, args.gpu, args.parent_pid, args.parent_birth)
