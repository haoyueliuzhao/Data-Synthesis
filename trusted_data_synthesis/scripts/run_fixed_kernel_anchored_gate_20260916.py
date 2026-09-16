"""Queue exactly one bounded numerical gate by remaining memory; never train A/B."""

import argparse
import fcntl
import importlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p


def run(root, module_name):
    gate = importlib.import_module(module_name)
    root = Path(root).resolve()
    directory = root / gate.BASE / gate.GATE_DIRECTORY
    p.require((directory / "plan.json").exists(), "anchored_queue.register_before_waiting")
    with (directory / "queue.lock").open("a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        p.require(not (directory / "started.json").exists(), "anchored_queue.no_retry")
        p.write_once(
            directory / "queue_started.json",
            p.record("anchored_sources_gate_queue_started", pid=os.getpid(), at=p.now()),
        )
        while True:
            raw = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=index,uuid,memory.free,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                text=True,
            )
            rows = []
            for line in raw.splitlines():
                index, uuid, free, utilization = (part.strip() for part in line.split(","))
                rows.append(
                    dict(index=int(index), uuid=uuid, free=int(free), utilization=int(utilization))
                )
            admitted = [row for row in rows if row["free"] >= gate.MIN_FREE_MIB]
            print(json.dumps(dict(at=p.now(), waiting=not admitted, memory=rows)), flush=True)
            if admitted:
                selected = max(admitted, key=lambda row: (row["free"], -row["index"]))
                p.write_once(
                    directory / "gpu_admission.json",
                    p.record("anchored_sources_gate_GPU_admission", selected=selected, at=p.now()),
                )
                command = [
                    sys.executable,
                    str(root / gate.SCRIPT),
                    "--root",
                    str(root),
                    "--mode",
                    "run",
                ]
                env = dict(
                    os.environ,
                    CUDA_VISIBLE_DEVICES=selected["uuid"],
                    CUBLAS_WORKSPACE_CONFIG=":4096:8",
                )
                with (directory / "worker.log").open("x") as log:
                    result = subprocess.run(
                        command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT
                    )
                print(json.dumps(dict(worker_returncode=result.returncode, at=p.now())), flush=True)
                return result.returncode
            time.sleep(30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--gate-module",
        choices=(
            "fixed_kernel_anchored_sources_gpu_gate_20260916",
            "fixed_kernel_anchored_sources_cached_replay_20260916",
            "fixed_kernel_anchored_memory_profile_20260916",
            "fixed_kernel_anchored_production_admission_20260916",
        ),
        default="fixed_kernel_anchored_sources_gpu_gate_20260916",
    )
    args = parser.parse_args()
    raise SystemExit(run(args.root, args.gate_module))
