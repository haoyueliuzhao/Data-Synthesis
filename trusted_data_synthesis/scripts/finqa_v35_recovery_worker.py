"""Authorize a new attempt around the unchanged, sealed V35 task worker.

Only the controller binding is adapted.  The original worker, task cache,
storage backend, mathematical functions and all numerical/resource gates keep
their registered bytes.  This wrapper has no computation or replay fallback.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from pathlib import Path

CONTROLLER_NAME = "finqa_v35_recovery_controller"
ORIGINAL_CONTROL_NAME = "finqa_v35_task_controller"
ORIGINAL_WORKER_NAME = "finqa_v35_task_worker"


def run(root, stage, gpu_index, deadline_epoch):
    root = Path(root).resolve()
    recovery = importlib.import_module(CONTROLLER_NAME)
    recovery_directory = root / "recovery_implementation"
    recovery.require(
        Path(__file__).resolve() == recovery_directory / Path(__file__).name
        and Path(recovery.__file__).resolve() == recovery_directory / (CONTROLLER_NAME + ".py"),
        "only the sealed recovery worker/controller may run",
    )
    recovery.checked_recovery_implementation(root)
    recovery.checked_protocol(root)
    implementation = recovery.checked_math_implementation(root)
    original_path = root / "implementation" / (ORIGINAL_WORKER_NAME + ".py")
    recovery.require(
        hashlib.sha256(original_path.read_bytes()).hexdigest()
        == implementation["sha256"][original_path.name],
        "original V35 mathematical worker bytes changed",
    )
    recovery.require(
        ORIGINAL_CONTROL_NAME not in sys.modules or sys.modules[ORIGINAL_CONTROL_NAME] is recovery,
        "a different V35 controller is already imported",
    )
    recovery.require(
        ORIGINAL_WORKER_NAME not in sys.modules,
        "recovery requires a fresh original worker import",
    )
    # The imported worker's own checked_sources, run/attempt lock, point gate,
    # saved-gJ loader and resource observers remain its original functions.
    # The adapter changes only where that shell reads its authorized protocol.
    sys.modules[ORIGINAL_CONTROL_NAME] = recovery
    sys.path.insert(0, str(root / "implementation"))
    worker = recovery._module(original_path, ORIGINAL_WORKER_NAME)
    recovery.require(
        Path(worker.__file__).resolve() == original_path and worker.control is recovery,
        "original worker did not bind the validated recovery controller",
    )
    return worker.run(root, stage, gpu_index, deadline_epoch)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--gpu-index", type=int, required=True)
    parser.add_argument("--deadline-epoch", type=float, required=True)
    args = parser.parse_args()
    result = run(args.root, args.stage, args.gpu_index, args.deadline_epoch)
    print(json.dumps(dict(status=result["status"], id=result["id"])))
