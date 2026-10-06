"""One-off V26 controller-only handoff; read-only unless --execute is given.

Never signal a process group or a scientific worker.  Freeze the verified old
controller at its polling sleep, audit the stopped queue, and kill that one
controller only.  Before that irreversible boundary, every failure continues
the same controller identity.  The original queue is never rewritten.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import signal
import time
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
SOURCE_ROOT = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01/v25_training_replication_01"
)
OLD_ROOT = SOURCE_ROOT / "execution_continuation_01"
NEW_ROOT = SOURCE_ROOT / "same_run_recovery_01"
OLD_PID = 3863280
OLD_BIRTH = "369457482"
OLD_PROTOCOL_ID = "2f9e2e5280694db567082718371e0ff4070880a4fd0b4da77f97f3d8bf538a52"
SCIENCE_ID = "bf2f8bfd34469400444d7597a8d9893678adbd6af296c89b0a69c5e9b5ba6d45"
OLD_COMMIT = "764f9760a6d2065fa3be4a8850eb2e60043b91d0"
FAILED_JOB = "replication-train-seed137-c_only"
CONTROLLER_NAME = "finqa_v26_execution_continuation.py"
SLEEP_WCHANS = {"hrtimer_nanosleep", "do_nanosleep"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def read_json(path, *, bound=False):
    path = Path(path)
    require(
        path.is_file() and not path.is_symlink(), "regular JSON evidence required: " + str(path)
    )
    raw = path.read_bytes()
    value = json.loads(raw)
    require(isinstance(value, dict), "JSON object required")
    if bound:
        require(
            value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
            "bound record changed: " + str(path),
        )
    ref = dict(path=str(path.resolve()), sha256=hashlib.sha256(raw).hexdigest())
    if bound:
        ref["id"] = value["id"]
    return value, ref


def publish(path, value):
    require("id" not in value, "new record must not supply id")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bound = {**value, "id": digest(value)}
    with path.open("x") as stream:
        json.dump(bound, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return bound


def verify_manifest(root, expected_id, *, commit=None):
    manifest, ref = read_json(root / "implementation/record.json", bound=True)
    require(manifest["id"] == expected_id, "implementation binding changed")
    if commit:
        require(manifest["source_commit"] == commit, "frozen execution commit changed")
    for name, sha in manifest["sha256"].items():
        require(Path(name).name == name, "implementation filename escapes its root")
        path = root / "implementation" / name
        require(path.is_file() and not path.is_symlink(), "missing regular frozen source")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == sha, "frozen source changed")
    return ref


def verify_frozen():
    plan, plan_ref = read_json(OLD_ROOT / "protocol/record.json", bound=True)
    require(plan["id"] == OLD_PROTOCOL_ID, "unexpected predecessor protocol")
    verify_manifest(OLD_ROOT, plan["implementation_id"], commit=OLD_COMMIT)
    science, science_ref = read_json(SOURCE_ROOT / "protocol/record.json", bound=True)
    require(science["id"] == SCIENCE_ID, "original scientific protocol changed")
    require(plan["scientific_protocol"] == science_ref, "predecessor science binding changed")
    science_manifest = verify_manifest(SOURCE_ROOT, science["implementation_id"])
    require(
        plan["scientific_implementation"] == science_manifest, "scientific source binding changed"
    )
    require(plan["jobs"] == science["jobs"], "fixed job matrix changed")
    launch, launch_ref = read_json(OLD_ROOT / "launch_01/record.json", bound=True)
    require(
        launch["protocol_id"] == plan["id"]
        and launch["scientific_protocol_id"] == science["id"]
        and launch["pid"] == OLD_PID
        and launch["birth"] == OLD_BIRTH,
        "unexpected predecessor launch identity",
    )
    command = launch["command"]
    require(
        len(command) == 6
        and command[0] == str(REPO / "trusted_data_synthesis/.venv/bin/python")
        and command[1:]
        == [
            "-u",
            str(OLD_ROOT / "implementation" / CONTROLLER_NAME),
            "run",
            "--root",
            str(OLD_ROOT),
        ],
        "unexpected predecessor controller command",
    )
    return plan, plan_ref, launch, launch_ref


class LinuxProcesses:
    """Narrow process access, kept replaceable by an entirely fake CPU backend."""

    def snapshot(self, pid):
        try:
            path = Path("/proc") / str(pid)
            fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
            return dict(
                pid=pid,
                state=fields[0],
                ppid=int(fields[1]),
                pgrp=int(fields[2]),
                session=int(fields[3]),
                birth=fields[19],
                uid=path.stat().st_uid,
            )
        except FileNotFoundError:
            return None

    def command(self, pid):
        return [
            part.decode()
            for part in (Path("/proc") / str(pid) / "cmdline").read_bytes().split(b"\0")
            if part
        ]

    def wchan(self, pid):
        return (Path("/proc") / str(pid) / "wchan").read_text().strip()

    def children(self, pid):
        path = Path("/proc") / str(pid) / "task" / str(pid) / "children"
        return {int(value) for value in path.read_text().split()}

    def open_handle(self, pid, birth):
        fd = os.pidfd_open(pid, 0) if hasattr(os, "pidfd_open") else None
        current = self.snapshot(pid)
        if current is None or current["birth"] != birth or current["state"] == "Z":
            if fd is not None:
                os.close(fd)
            raise ValueError("controller identity changed before opening signal handle")
        return dict(pid=pid, birth=birth, fd=fd)

    def send(self, handle, signum):
        require(
            handle["pid"] == OLD_PID and handle["birth"] == OLD_BIRTH,
            "only fixed controller may be signaled",
        )
        current = self.snapshot(handle["pid"])
        require(
            current is not None and current["birth"] == handle["birth"] and current["state"] != "Z",
            "signal target identity changed",
        )
        if handle["fd"] is not None and hasattr(signal, "pidfd_send_signal"):
            signal.pidfd_send_signal(handle["fd"], signum)
        else:
            os.kill(handle["pid"], signum)

    def close_handle(self, handle):
        if handle["fd"] is not None:
            os.close(handle["fd"])

    def wait(self, predicate, seconds=5):
        limit = time.monotonic() + seconds
        while not predicate():
            require(time.monotonic() < limit, "process-state observation timed out")
            time.sleep(0.02)


def same_alive(backend, pid, birth):
    current = backend.snapshot(pid)
    return current is not None and current["birth"] == birth and current["state"] != "Z"


def verify_controller(backend, launch, *, stopped=False):
    current = backend.snapshot(OLD_PID)
    require(current is not None and current["birth"] == OLD_BIRTH, "predecessor PID/birth mismatch")
    require(current["uid"] == os.geteuid(), "controller is not owned by the executing account")
    require(backend.command(OLD_PID) == launch["command"], "controller cmdline changed")
    if stopped:
        require(current["state"] in {"T", "t"}, "controller was not stopped")
    else:
        require(
            current["state"] == "S" and backend.wchan(OLD_PID) in SLEEP_WCHANS,
            "controller is not at its nanosleep polling boundary",
        )
    return current


def complete_result(job):
    value, ref = read_json(job["result"], bound=True)
    if job["kind"] == "test":
        require(
            value.get("denominator") == 1147
            and value.get("all_generation_complete") is True
            and value.get("all_provider_calls_settled") is True
            and len(value.get("episode_sha256", {})) == 1147,
            "test result is not fully sealed",
        )
    elif job["kind"] == "prefix":
        require(
            value.get("complete_prefix") is True
            and value.get("actual_new_updates") == 298
            and value.get("migration_optimizer_steps") == 0,
            "prefix is not complete",
        )
    else:
        require(value.get("result", {}).get("committed_step") == 1490, "arm is not complete")
    return ref


def worker_snapshot(backend, row, launch):
    pid, birth = row["pid"], row["birth"]
    current = backend.snapshot(pid)
    if current is None or current["birth"] != birth or current["state"] == "Z":
        return None
    require(current["ppid"] in {OLD_PID, 1}, "live worker has an unexpected parent")
    require(
        current["session"] == pid and current["pgrp"] == pid,
        "worker is not a detached process/session",
    )
    command = launch["command"]
    actual = backend.command(pid)
    require(
        actual == command
        or (command[:2] == ["/usr/bin/taskset", "--cpu-list"] and actual == command[3:]),
        "live worker cmdline differs from its launch",
    )
    return current


def queue_snapshot(backend, plan):
    """Read only queue metadata and sealed result headers, never episode payloads."""
    status, status_ref = read_json(OLD_ROOT / "queue/status.json")
    require(
        status.get("protocol_id") == plan["id"]
        and status.get("scientific_protocol_id") == SCIENCE_ID,
        "foreign predecessor status",
    )
    require(
        status.get("phase") == "DRAINING_AFTER_FAILURE",
        "predecessor is not draining its one known failure",
    )
    failures = status.get("failures", [])
    require(
        len(failures) == 1 and failures[0].get("job") == FAILED_JOB,
        "unexpected or additional controller failure",
    )
    require(
        status.get("extension_scored") is False and status.get("replication_scored") is False,
        "unexpected scoring stage",
    )
    jobs = {job["key"]: job for job in plan["jobs"]}
    launch_records = {}
    known_refs = []
    record_refs = []
    for path in sorted((OLD_ROOT / "queue/jobs").glob("*/attempt*/*/record.json")):
        value, ref = read_json(path, bound=True)
        record_refs.append(ref)
        job_key = path.parents[2].name
        require(
            job_key in jobs and value.get("protocol_id") == plan["id"],
            "unknown job or protocol in predecessor queue",
        )
        if path.parent.name == "launch":
            require(value["job"] == jobs[job_key], "worker job differs from fixed registration")
            launch_records[str(path.parents[1])] = (value, ref)
            known_refs.append(ref)
        elif path.parent.name == "exit":
            require(value.get("key") == job_key, "exit key does not match its directory")
            if value.get("completed"):
                require(
                    value.get("result") == complete_result(jobs[job_key]),
                    "completed exit/result mismatch",
                )
    active = status.get("active_children", [])
    require(len({row["pid"] for row in active}) == len(active), "duplicate live worker PID")
    active_attempts = set()
    live, finished, permitted_children = [], [], set()
    for row in active:
        key = row["job"]["key"]
        require(row["job"] == jobs.get(key), "status worker is not a fixed job")
        attempt = row["attempt"]
        require(attempt in launch_records, "active worker is missing its complete launch record")
        launch, ref = launch_records[attempt]
        require(
            all(launch[field] == row[field] for field in ("pid", "birth", "gpu")),
            "status/launch worker identity mismatch",
        )
        require(
            not (Path(attempt) / "exit/record.json").exists(),
            "active worker already has a terminal exit",
        )
        active_attempts.add(attempt)
        item = dict(job_key=key, pid=row["pid"], birth=row["birth"], gpu=row["gpu"], launch=ref)
        if worker_snapshot(backend, row, launch) is not None:
            live.append(item)
            permitted_children.add(row["pid"])
        else:
            item["result"] = complete_result(jobs[key])
            finished.append(item)
            current = backend.snapshot(row["pid"])
            if current is not None and current["birth"] == row["birth"]:
                permitted_children.add(row["pid"])
    for attempt, (launch, _) in launch_records.items():
        if attempt not in active_attempts:
            require(
                not same_alive(backend, launch["pid"], launch["birth"]),
                "unaccounted live worker is absent from status",
            )
            require(
                (Path(attempt) / "exit/record.json").is_file(),
                "unaccounted unsealed worker attempt",
            )
    children = backend.children(OLD_PID)
    require(children <= permitted_children, "controller has an extra child (possibly CPU scorer)")
    for key in status.get("completed", []):
        require(key in jobs, "unknown completed job")
        complete_result(jobs[key])
    return dict(
        predecessor_status_snapshot={**status_ref, "value": status},
        predecessor_status=status,
        known_worker_launches=known_refs,
        queue_record_entries=record_refs,
        live_workers=live,
        workers_completed_during_handoff=finished,
        no_extra_controller_children=True,
    )


def released_controller_locks(stack):
    """Inspect only two controller locks, never a GPU, seed or worker lock."""
    references = []
    for path in (SOURCE_ROOT / "queue/controller.lock", OLD_ROOT / "queue/controller.lock"):
        require(path.is_file() and not path.is_symlink(), "missing regular controller lock")
        stream = stack.enter_context(path.open("r"))
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        references.append(str(path))
    return references


def handoff(*, execute=False, backend=None):
    backend = backend or LinuxProcesses()
    require(
        not (NEW_ROOT / "protocol/record.json").exists(),
        "handoff must precede recovery initialization",
    )
    require(not (NEW_ROOT / "handoff/record.json").exists(), "controller handoff is already sealed")
    plan, plan_ref, launch, launch_ref = verify_frozen()
    verify_controller(backend, launch)
    before = queue_snapshot(backend, plan)
    preview = dict(
        schema="v27_controller_only_handoff_dry_run.v1",
        at=now(),
        execute=False,
        controller_pid=OLD_PID,
        birth=OLD_BIRTH,
        predecessor_protocol=plan_ref,
        predecessor_controller_launch=launch_ref,
        **before,
        no_signals_sent=True,
        no_files_written=True,
    )
    if not execute:
        return preview
    # Exclusive directory is also the interlock against two simultaneous tools.
    intent_dir = NEW_ROOT / "handoff_intent"
    intent_dir.parent.mkdir(parents=True, exist_ok=True)
    intent_dir.mkdir()
    publish(
        intent_dir / "record.json",
        {
            **{
                k: v
                for k, v in preview.items()
                if k not in {"schema", "execute", "no_signals_sent", "no_files_written"}
            },
            "schema": "v27_exclusive_controller_handoff_intent.v1",
            "explicit_execute": True,
            "authorized_signal_pid": OLD_PID,
            "authorized_signal_birth": OLD_BIRTH,
            "worker_signals_authorized": False,
        },
    )
    handle = None
    stopped = killed = False
    signal_events = []
    try:
        handle = backend.open_handle(OLD_PID, OLD_BIRTH)
        verify_controller(backend, launch)
        backend.send(handle, signal.SIGSTOP)
        stopped = True
        signal_events.append(dict(at=now(), pid=OLD_PID, birth=OLD_BIRTH, signal="SIGSTOP"))
        backend.wait(lambda: (backend.snapshot(OLD_PID) or {}).get("state") in {"T", "t"})
        verify_controller(backend, launch, stopped=True)
        # Recheck frozen bytes and all complete JSON after stopping; no write can
        # now be in progress in this controller, and workers remain detached.
        verify_frozen()
        snapshot = queue_snapshot(backend, plan)
        publish(
            intent_dir / "stopped_snapshot/record.json",
            {
                "schema": "v27_stopped_controller_consistent_snapshot.v1",
                "at": now(),
                **snapshot,
            },
        )
        verify_controller(backend, launch, stopped=True)
        backend.send(handle, signal.SIGKILL)
        killed = True
        signal_events.append(dict(at=now(), pid=OLD_PID, birth=OLD_BIRTH, signal="SIGKILL"))
        backend.wait(lambda: not same_alive(backend, OLD_PID, OLD_BIRTH))
        jobs = {job["key"]: job for job in plan["jobs"]}
        live, completed = [], list(snapshot["workers_completed_during_handoff"])
        for row in snapshot["live_workers"]:
            if same_alive(backend, row["pid"], row["birth"]):
                live.append(row)
            else:
                completed.append({**row, "result": complete_result(jobs[row["job_key"]])})
        with ExitStack() as stack:
            locks = released_controller_locks(stack)
            return publish(
                NEW_ROOT / "handoff/record.json",
                dict(
                    schema="v27_controller_only_handoff.v1",
                    at=now(),
                    predecessor_protocol=plan_ref,
                    predecessor_controller_launch=launch_ref,
                    controller_pid=OLD_PID,
                    birth=OLD_BIRTH,
                    **{
                        k: v
                        for k, v in snapshot.items()
                        if k not in {"live_workers", "workers_completed_during_handoff"}
                    },
                    stopped_only_controller=True,
                    no_worker_signals=True,
                    post_handoff_controller_absent=True,
                    live_workers=live,
                    workers_completed_during_handoff=completed,
                    controller_locks_released=locks,
                    worker_locks_touched=False,
                    signal_events=signal_events,
                    used_pidfd=handle.get("fd") is not None,
                    old_queue_modified=False,
                ),
            )
    except BaseException as exc:
        continued = False
        continue_error = None
        if (
            stopped
            and not killed
            and handle is not None
            and same_alive(backend, OLD_PID, OLD_BIRTH)
        ):
            try:
                backend.send(handle, signal.SIGCONT)
                continued = True
                signal_events.append(dict(at=now(), pid=OLD_PID, birth=OLD_BIRTH, signal="SIGCONT"))
            except Exception as resume_error:
                continue_error = f"{type(resume_error).__name__}: {resume_error}"
        publish(
            NEW_ROOT / "handoff_failed/record.json",
            dict(
                schema="v27_controller_handoff_failed.v1",
                at=now(),
                controller_pid=OLD_PID,
                birth=OLD_BIRTH,
                error_type=type(exc).__name__,
                error=str(exc),
                controller_killed=killed,
                controller_continued=continued,
                continue_error=continue_error,
                no_worker_signals=True,
                old_queue_modified=False,
                signal_events=signal_events,
            ),
        )
        raise
    finally:
        if handle is not None:
            backend.close_handle(handle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="signal only the fixed verified predecessor controller",
    )
    args = parser.parse_args()
    print(json.dumps(handoff(execute=args.execute), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
