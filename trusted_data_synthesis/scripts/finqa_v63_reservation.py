"""One user-requested, bounded GPU7 reservation; no scientific model or calls."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import tempfile
import time
from datetime import datetime, timezone

import finqa_v63_gpu_isolation as ownership

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
V18 = REPO / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01"
ROOT = V18 / "v63_resource_reservation_gpu7_20261020_01"
GPU = "GPU-ab6e97cc-19e4-64b8-f792-7b6920a45434"
LEASE = V18 / "v25_training_replication_01/training_replication/locks/gpu-23de3b19331d75a07aa41aef48e1af06933180307d9643e0e1770a6a9502d2ce.lock"
GIB = 1024 ** 3


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def birth(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (FileNotFoundError, ProcessLookupError):
        return None


def publish(name, body):
    value = {**body, "id": digest(body)}
    directory = ROOT / name
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "record.json"
    if path.exists():
        raise RuntimeError("one-shot reservation record already exists")
    fd, temporary = tempfile.mkstemp(prefix=".reservation-", dir=directory)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return value


def known_owners():
    value = ownership.probe_gpus([GPU])[GPU]
    if not value["allowed"]:
        raise RuntimeError("GPU7 process ownership unresolved; no reservation")
    return value


def hold():
    if os.getuid() != 1004 or os.geteuid() != 1004:
        raise RuntimeError("reservation only belongs to the registered account")
    if (ROOT / "intent/record.json").exists():
        raise RuntimeError("reservation already attempted; no automatic retry")
    os.environ["CUDA_VISIBLE_DEVICES"] = GPU
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "backend:native,expandable_segments:False"
    os.environ.pop("PYTORCH_ALLOC_CONF", None)
    stopped = [False]
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: stopped.__setitem__(0, True))
    with LEASE.open("r+") as lease:
        old = LEASE.stat()
        opened = os.fstat(lease.fileno())
        if not stat.S_ISREG(old.st_mode) or (
                opened.st_dev, opened.st_ino) != (old.st_dev, old.st_ino):
            raise RuntimeError("original GPU7 lease is not a regular file")
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = LEASE.stat()
        if (old.st_dev, old.st_ino) != (current.st_dev, current.st_ino):
            raise RuntimeError("GPU7 lease inode changed")
        owner_snapshot = known_owners()
        intent = publish("intent", dict(schema="v63_explicit_GPU7_reservation.v1",
            requested_GiB=64, maximum_seconds=3600, startup_free_margin_GiB=4,
            runtime_free_floor_GiB=2, GPU=GPU, pid=os.getpid(), birth=birth(os.getpid()),
            at=datetime.now(timezone.utc).isoformat(),
            lease=dict(path=str(LEASE), device=old.st_dev, inode=old.st_ino),
            source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            ownership_source_sha256=hashlib.sha256(Path(ownership.__file__).read_bytes()).hexdigest(),
            known_existing_processes=len(owner_snapshot["known_processes"]),
            other_processes_modified=False, model_calls=0, optimizer_updates=0))
        allocation = None
        reason = "reservation_failed"
        try:
            import torch
            known_owners()
            free, _ = torch.cuda.mem_get_info()
            if stopped[0] or free < 68 * GIB:
                raise RuntimeError("GPU7 no longer has 64GiB plus 4GiB margin")
            allocation = torch.empty(64 * GIB, dtype=torch.uint8, device="cuda:0")
            remaining = torch.cuda.mem_get_info()[0]
            if remaining < 4 * GIB:
                raise RuntimeError("GPU7 headroom changed during reservation")
            started = time.monotonic()
            reserved = publish("reserved", dict(schema="v63_GPU7_reservation_started.v1",
                intent_id=intent["id"], GPU=GPU, gpu_index=7, pid=os.getpid(),
                birth=birth(os.getpid()), at=datetime.now(timezone.utc).isoformat(),
                ttl_seconds=3600, allocated_bytes=torch.cuda.memory_allocated(),
                free_bytes=remaining, model_calls=0, optimizer_updates=0,
                scientific_worker_started=False, exclusive_project_lease=True,
                exclusive_physical_GPU_claimed=False))
            reason = "bounded_lease_expired"
            while time.monotonic() - started < 3600:
                request = ROOT / "release_request/record.json"
                if stopped[0]:
                    reason = "owner_signal"
                    break
                if request.exists():
                    value = json.loads(request.read_bytes())
                    if (value.get("reserved_id"), value.get("pid"), value.get("birth")) != (
                            reserved["id"], os.getpid(), reserved["birth"]):
                        raise RuntimeError("release request identity differs")
                    reason = "registered_handoff_request"
                    break
                if torch.cuda.mem_get_info()[0] < 2 * GIB:
                    reason = "release_own_reservation_to_preserve_free_floor"
                    break
                time.sleep(1)
        except BaseException as error:
            publish("failure", dict(schema="v63_reservation_failure.v1", intent_id=intent["id"],
                error_type=type(error).__name__, error=str(error), automatic_retry=False))
            raise
        finally:
            if allocation is not None:
                del allocation
                torch.cuda.empty_cache()
            publish("released", dict(schema="v63_GPU7_reservation_released.v1",
                intent_id=intent["id"], GPU=GPU, pid=os.getpid(), birth=birth(os.getpid()),
                at=datetime.now(timezone.utc).isoformat(), reason=reason,
                model_calls=0, optimizer_updates=0))


def release():
    value = json.loads((ROOT / "reserved/record.json").read_bytes())
    if birth(value["pid"]) != value["birth"]:
        raise RuntimeError("reserved process no longer has its original identity")
    return publish("release_request", dict(reserved_id=value["id"], pid=value["pid"],
        birth=value["birth"], GPU=GPU, request_epoch=time.time(),
        other_processes_signaled=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("hold", "release"))
    args = parser.parse_args()
    result = hold() if args.action == "hold" else release()
    print(json.dumps(result, ensure_ascii=False))
