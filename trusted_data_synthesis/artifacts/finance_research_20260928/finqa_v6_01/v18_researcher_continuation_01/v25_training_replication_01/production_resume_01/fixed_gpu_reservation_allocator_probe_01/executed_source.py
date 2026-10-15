"""Bounded allocator-only check; no model, optimizer, provider, or experiment pass."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

GIB = 1024**3


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(args):
    check(not args.output.exists(), "probe output already exists")
    check(args.gib == 2, "this registered probe is limited to 2GiB")
    lock = args.lease_path.open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    rows = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=index,uuid,memory.free", "--format=csv,noheader,nounits"],
        text=True,
    )
    fields = [row.split(", ") for row in rows.strip().splitlines()]
    selected = [row for row in fields if row[0] == str(args.gpu_index)]
    check(len(selected) == 1 and selected[0][1] == args.uuid, "physical GPU identity changed")
    check(int(selected[0][2]) >= 10 * 1024, "insufficient capacity for bounded probe")
    os.environ["CUDA_VISIBLE_DEVICES"] = args.uuid
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "backend:native,expandable_segments:False"
    os.environ.pop("PYTORCH_ALLOC_CONF", None)
    import torch

    check(not torch.cuda.is_initialized(), "probe must use a fresh CUDA process")
    check(torch.cuda.memory.get_allocator_backend() == "native", "native allocator required")
    cpu_rng = torch.get_rng_state()
    gpu_rng = torch.cuda.get_rng_state()
    torch.cuda.empty_cache()
    before = dict(free=torch.cuda.mem_get_info()[0], reserved=torch.cuda.memory_reserved())
    check(before["reserved"] == 0, "allocator must be fresh")
    check(before["free"] >= 6 * GIB, "physical reserve unavailable after CUDA initialization")
    size = args.gib * GIB
    warm = torch.empty(size, dtype=torch.uint8, device="cuda:0")
    address = warm.data_ptr()
    del warm
    anchor = torch.empty(2 * 1024**2, dtype=torch.uint8, device="cuda:0")
    check(anchor.data_ptr() == address, "anchor did not reuse the warmed segment")
    torch.cuda.empty_cache()

    def segment():
        found = [s for s in torch.cuda.memory_snapshot() if s["address"] == address]
        check(len(found) == 1 and found[0]["total_size"] == size, "anchored segment changed")
        check(found[0]["active_size"] >= anchor.numel(), "anchor is not active")
        return found[0]

    anchored = segment()
    reusable = torch.empty(GIB, dtype=torch.uint8, device="cuda:0")
    check(address <= reusable.data_ptr() < address + size, "scientific-sized allocation missed segment")
    check(torch.cuda.memory_reserved() == size, "reuse unexpectedly allocated another segment")
    del reusable
    torch.cuda.empty_cache()
    reused = segment()
    check(torch.equal(cpu_rng, torch.get_rng_state()), "CPU RNG changed")
    check(torch.equal(gpu_rng, torch.cuda.get_rng_state()), "CUDA RNG changed")
    peak = torch.cuda.max_memory_allocated()
    free = torch.cuda.mem_get_info()[0]
    check(peak == size and free >= 2 * GIB, "probe physical memory contract failed")
    del anchor
    torch.cuda.empty_cache()
    released = torch.cuda.memory_reserved()
    check(released == 0, "probe did not release its native allocation")
    record = dict(
        schema="v47_native_allocator_anchor_probe.v1",
        status="COMPLETE",
        at=datetime.now(timezone.utc).isoformat(),
        pid=os.getpid(),
        gpu_index=args.gpu_index,
        gpu_uuid=args.uuid,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        torch_version=torch.__version__,
        allocator_configuration=os.environ["PYTORCH_CUDA_ALLOC_CONF"],
        allocator_backend="native",
        probe_bytes=size,
        anchor_bytes=2 * 1024**2,
        before=before,
        segment_after_empty_cache=anchored,
        segment_after_reuse_and_empty_cache=reused,
        lifetime_allocated_peak_bytes=peak,
        minimum_observed_free_bytes=free,
        reserved_after_release_bytes=released,
        cpu_and_cuda_rng_unchanged=True,
        model_calls=0,
        provider_calls=0,
        optimizer_updates=0,
        scientific_responses_replayed=0,
        scope="allocator behavior only; not a scientific-stage or full-size memory acceptance",
    )
    from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

    write_immutable_artifact_directory(
        args.output, {"record.json": json.dumps(record, sort_keys=True, indent=2).encode()}
    )
    lock.close()
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu-index", type=int, required=True)
    parser.add_argument("--uuid", required=True)
    parser.add_argument("--gib", type=int, default=2)
    parser.add_argument("--lease-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    result = run(parser.parse_args())
    print(json.dumps({key: result[key] for key in ("status", "torch_version", "gpu_index", "probe_bytes", "reserved_after_release_bytes", "scope")}))
