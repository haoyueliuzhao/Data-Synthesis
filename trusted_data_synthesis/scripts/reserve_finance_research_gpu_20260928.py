"""Explicit user-requested short GPU reservation; no model, sampling, or training."""

import argparse
import json
import multiprocessing
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def write(path, value):
    from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

    write_immutable_artifact_directory(
        path, {"record.json": json.dumps(value, sort_keys=True).encode()}
    )


def hold(args):
    if not (0 < args.ttl <= 3600 and 0 < args.mib <= 61440):
        raise ValueError("bounded reservation required")
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu
    current = subprocess.check_output(
        ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits"],
        text=True,
    )
    if any(line.split(",")[0].strip() == args.gpu for line in current.splitlines()):
        raise RuntimeError("GPU acquired by another process; do not reserve")
    import torch

    current = subprocess.check_output(
        ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits"],
        text=True,
    )
    if any(line.split(",")[0].strip() == args.gpu for line in current.splitlines()):
        raise RuntimeError("GPU acquired during startup; do not reserve")
    free, _ = torch.cuda.mem_get_info()
    if free < (args.mib + 4096) * 2**20:
        raise RuntimeError("insufficient idle capacity")
    allocation = torch.empty(args.mib * 2**20, dtype=torch.uint8, device="cuda:0")
    stopped = [False]
    signal.signal(signal.SIGTERM, lambda *_: stopped.__setitem__(0, True))
    signal.signal(signal.SIGINT, lambda *_: stopped.__setitem__(0, True))
    start = time.monotonic()
    write(
        args.output / "reserved",
        dict(
            at=datetime.now(timezone.utc).isoformat(),
            pid=os.getpid(),
            gpu=args.gpu,
            MiB=args.mib,
            ttl_seconds=args.ttl,
            model_calls=0,
            optimizer_steps=0,
            reason="user requested reserving idle GPUs for the pending audited experiment",
        ),
    )
    while not stopped[0] and time.monotonic() - start < args.ttl:
        time.sleep(1)
    del allocation
    torch.cuda.empty_cache()
    write(
        args.output / "released",
        dict(
            at=datetime.now(timezone.utc).isoformat(),
            pid=os.getpid(),
            gpu=args.gpu,
            reason="handoff_signal" if stopped[0] else "bounded_lease_expired",
        ),
    )


def watch(args):
    # Import once before fork, without initializing CUDA, so short idle windows do
    # not require each child to wait for the full framework import.
    import torch

    if torch.cuda.is_initialized():
        raise RuntimeError("reservation watcher must never initialize CUDA")
    context = multiprocessing.get_context("fork")
    children, attempts = {}, 0
    started = time.monotonic()
    write(
        args.output / "watch_started",
        dict(
            pid=os.getpid(),
            maximum_GPUs=4,
            maximum_seconds=args.ttl,
            allocation_MiB=args.mib,
            model_calls=0,
        ),
    )
    while time.monotonic() - started < args.ttl and attempts < 32:
        for gpu, (process, _directory) in list(children.items()):
            if not process.is_alive():
                process.join()
                del children[gpu]
        reserved = [
            gpu
            for gpu, (_, directory) in children.items()
            if (directory / "reserved/record.json").exists()
        ]
        if len(reserved) >= 4:
            write(
                args.output / "watch_filled",
                dict(gpus=reserved, at=datetime.now(timezone.utc).isoformat()),
            )
            break
        rows = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,uuid,memory.used,memory.free",
                "--format=csv,noheader,nounits",
            ],
            text=True,
        )
        for line in rows.splitlines():
            index, gpu, used, free = [value.strip() for value in line.split(",")]
            if (
                gpu in children
                or len(children) >= 4
                or int(used) > 1024
                or int(free) < args.mib + 4096
            ):
                continue
            attempts += 1
            directory = args.output / f"attempt_{attempts:03d}_gpu{index}"
            child_args = argparse.Namespace(gpu=gpu, output=directory, ttl=args.ttl, mib=args.mib)
            process = context.Process(target=hold, args=(child_args,))
            process.start()
            children[gpu] = (process, directory)
            print(
                json.dumps(dict(event="reservation_candidate", gpu=gpu, pid=process.pid)),
                flush=True,
            )
        time.sleep(1)
    for process, _ in children.values():
        process.join()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ttl", type=int, default=1800)
    parser.add_argument("--mib", type=int, default=49152)
    args = parser.parse_args()
    if not (0 < args.ttl <= 3600 and 0 < args.mib <= 61440):
        raise ValueError("bounded reservation required")
    if args.watch:
        watch(args)
    elif args.gpu:
        hold(args)
    else:
        parser.error("provide --gpu or --watch")


if __name__ == "__main__":
    main()
