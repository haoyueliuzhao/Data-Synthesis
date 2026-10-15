"""Bounded GPU5/7 resource holds, released before queued scientific handoff.

This owner never takes a project GPU lease, imports Torch or starts science.
The byte-pinned original holder retains both of its empty-device checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
PRODUCTION = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01/v25_training_replication_01/production_resume_01"
)
HANDOFF = PRODUCTION / "host_memory_admission_01/queued_handoff_01"
PROGRESS = PRODUCTION / (
    "recovery_04/contexts/seed251/full/step1192_outer/shard03/queue/status.json"
)
WORKER = dict(pid=3571767, birth="444416151")
CONTEXT_ID = "c668b6cd96ac72b559a253e31cbcb18e93d1a9c2299f32ce2f6920d9532aa693"
GPUS = {
    5: "GPU-f731a280-01e3-2359-ace9-aa2ad2112f55",
    7: "GPU-ab6e97cc-19e4-64b8-f792-7b6920a45434",
}
MIB = 73728
HOLDER = REPO / "trusted_data_synthesis/scripts/reserve_finance_research_gpu_20260928.py"
HOLDER_SHA256 = "6f16dba63062f42fe4fa0a348de8dd1975d070e123690635092eb968f3b73a16"


def require(value, message):
    if not value:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def birth(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (FileNotFoundError, ProcessLookupError):
        return None


def publish(path, body):
    path = Path(path)
    raw = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    value = {**body, "id": hashlib.sha256(raw).hexdigest()}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return value


def release_reason(started, ttl, stopped, *, clock=time.monotonic, identity=birth):
    if stopped():
        return "EXPLICIT_OWNER_STOP"
    if clock() - started >= ttl:
        return "OWNER_TTL_EXPIRED"
    for marker in ("waiters_registered", "closeout", "continuation_failure"):
        if (HANDOFF / marker / "record.json").exists():
            return "QUEUED_HANDOFF_" + marker.upper()
    if identity(WORKER["pid"]) != WORKER["birth"]:
        return "ORIGINAL_GPU3_WORKER_EXITED_OR_REPLACED"
    progress = json.loads(PROGRESS.read_text())
    count = progress.get("committed_task_count")
    require(
        progress.get("context_id") == CONTEXT_ID
        and progress.get("assigned_task_count") == 186
        and type(count) is int
        and 0 <= count <= 186,
        "original complete-task progress binding changed",
    )
    if count >= 183:
        return "THREE_OR_FEWER_COMPLETE_TASKS_REMAIN"
    entry = HANDOFF / "entry_launch/record.json"
    if entry.exists():
        owner = json.loads(entry.read_text())
        require(type(owner.get("pid")) is int and owner.get("birth"), "invalid V46 entry identity")
        if identity(owner["pid"]) != str(owner["birth"]):
            return "QUEUED_HANDOFF_ENTRY_EXITED_OR_REPLACED"
    return None


def idle_inventory():
    devices = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=index,uuid,memory.free", "--format=csv,noheader,nounits"],
        text=True,
    )
    processes = subprocess.check_output(
        ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits"],
        text=True,
    )
    occupied = {line.split(",")[0].strip() for line in processes.splitlines() if line.strip()}
    rows = {}
    for line in devices.splitlines():
        index, uuid, free = [value.strip() for value in line.split(",")]
        if int(index) in GPUS:
            rows[int(index)] = dict(uuid=uuid, free_mib=float(free), occupied=uuid in occupied)
    for index, uuid in GPUS.items():
        row = rows.get(index, {})
        require(
            row.get("uuid") == uuid
            and row.get("occupied") is False
            and row.get("free_mib", 0) >= MIB + 4096,
            f"GPU{index} is not the bound fully idle device with 76GiB free",
        )
    return rows


def signal_owned(child, signum, *, identity=birth):
    process = child["process"]
    if process.poll() is not None:
        return "already_exited"
    descriptor = child["pidfd"]
    if descriptor is not None:
        signal.pidfd_send_signal(descriptor, signum)
        return "pidfd"
    require(
        child["birth"] is not None and identity(process.pid) == child["birth"],
        "refuse to signal an unverified reservation child",
    )
    process.send_signal(signum)
    return "owned_Popen_with_birth_check"


def close_children(children, output, *, send=signal_owned):
    receipts = []
    for child in children:
        process, sent, error = child["process"], [], None
        try:
            if process.poll() is None:
                sent.append(dict(signal=int(signal.SIGTERM), transport=send(child, signal.SIGTERM)))
            try:
                code = process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                sent.append(dict(signal=int(signal.SIGKILL), transport=send(child, signal.SIGKILL)))
                code = process.wait(timeout=10)
        except Exception as caught:
            code, error = process.poll(), repr(caught)
        finally:
            if child["pidfd"] is not None:
                os.close(child["pidfd"])
            child["log"].close()
        receipts.append(
            publish(
                output / f"gpu{child['index']}/actual_exit/record.json",
                dict(
                    at=now(),
                    pid=process.pid,
                    birth=child["birth"],
                    gpu_uuid=GPUS[child["index"]],
                    returncode=code,
                    actual_exit_observed=code is not None,
                    signals=sent,
                    cleanup_error=error,
                    scientific_worker=False,
                ),
            )
        )
    return receipts


def watch(
    output,
    ttl=900,
    holder=HOLDER,
    *,
    stopped=lambda: False,
    spawn=subprocess.Popen,
    clock=time.monotonic,
    sleep=time.sleep,
    identity=birth,
    inventory=idle_inventory,
    cleanup=close_children,
):
    output, holder = Path(output).resolve(), Path(holder).resolve()
    require(type(ttl) is int and 0 < ttl <= 900, "resource hold TTL must be 1..900 seconds")
    require(
        hashlib.sha256(holder.read_bytes()).hexdigest() == HOLDER_SHA256,
        "original holder bytes changed",
    )
    started, children, reason, error = clock(), [], None, None
    publish(
        output / "owner_launch/record.json",
        dict(
            schema="v46_bounded_idle_gpu_reservation_owner.v1",
            at=now(),
            pid=os.getpid(),
            birth=identity(os.getpid()),
            gpu_uuids=GPUS,
            MiB_per_gpu=MIB,
            ttl_seconds=ttl,
            holder_script=str(holder),
            holder_sha256=HOLDER_SHA256,
            watcher_script=str(Path(__file__).resolve()),
            watcher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            project_gpu_leases_acquired=False,
            scientific_progress=False,
            model_calls=0,
            original_worker=WORKER,
            complete_task_release_threshold=183,
        ),
    )
    try:
        reason = release_reason(started, ttl, stopped, clock=clock, identity=identity)
        if reason is None:
            observed = inventory()
            for index, uuid in GPUS.items():
                reason = release_reason(started, ttl, stopped, clock=clock, identity=identity)
                if reason is not None:
                    break
                directory = output / f"gpu{index}"
                directory.mkdir(parents=True, exist_ok=False)
                command = [
                    sys.executable,
                    "-u",
                    str(holder),
                    "--gpu",
                    uuid,
                    "--output",
                    str(directory),
                    "--ttl",
                    str(max(1, int(ttl - (clock() - started)))),
                    "--mib",
                    str(MIB),
                ]
                stream = (directory / "holder.log").open("xb")
                try:
                    process = spawn(
                        command,
                        cwd=REPO,
                        stdout=stream,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                except BaseException:
                    stream.close()
                    raise
                child = dict(process=process, index=index, birth=None, pidfd=None, log=stream)
                children.append(child)
                if hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"):
                    try:
                        child["pidfd"] = os.pidfd_open(process.pid)
                    except OSError:
                        pass
                child["birth"] = identity(process.pid)
                require(
                    child["birth"] is not None or process.poll() is not None,
                    "reservation child identity unavailable",
                )
                publish(
                    directory / "launch/record.json",
                    dict(
                        at=now(),
                        pid=process.pid,
                        birth=child["birth"],
                        gpu_index=index,
                        gpu_uuid=uuid,
                        command=command,
                        pidfd_owned=child["pidfd"] is not None,
                        initial_inventory=observed[index],
                        project_gpu_lease=None,
                        scientific_worker=False,
                    ),
                )
        while reason is None:
            if any(child["process"].poll() is not None for child in children):
                reason = "RESERVATION_CHILD_EXITED_NO_RETRY"
                break
            reason = release_reason(started, ttl, stopped, clock=clock, identity=identity)
            if reason is None:
                sleep(1)
    except BaseException as caught:
        reason, error = "FAIL_CLOSED_RELEASE", repr(caught)
    finally:
        exits = cleanup(children, output)
    failed = error is not None or any(
        row["cleanup_error"] or not row["actual_exit_observed"] or row["returncode"] != 0
        for row in exits
    )
    return publish(
        output / "closeout/record.json",
        dict(
            schema="v46_bounded_idle_gpu_reservation_closeout.v1",
            at=now(),
            status="RESERVATION_FAILURE" if failed else "RESOURCE_HOLDS_RELEASED",
            reason=reason,
            error=error,
            elapsed_owner_seconds=max(0, clock() - started),
            actual_child_exits=exits,
            children_launched=len(children),
            automatic_retry=False,
            project_gpu_leases_acquired=False,
            scientific_progress=False,
            model_calls=0,
            optimizer_steps=0,
            sampling_calls=0,
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ttl", type=int, default=900)
    parser.add_argument("--holder-script", type=Path, default=HOLDER)
    args = parser.parse_args()
    state = dict(stopped=False)
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    for sig in handlers:
        signal.signal(sig, lambda *_: state.__setitem__("stopped", True))
    try:
        value = watch(args.output, args.ttl, args.holder_script, stopped=lambda: state["stopped"])
        print(
            json.dumps({key: value[key] for key in ("status", "reason", "children_launched")}),
            flush=True,
        )
        return 1 if value["status"] == "RESERVATION_FAILURE" else 0
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
