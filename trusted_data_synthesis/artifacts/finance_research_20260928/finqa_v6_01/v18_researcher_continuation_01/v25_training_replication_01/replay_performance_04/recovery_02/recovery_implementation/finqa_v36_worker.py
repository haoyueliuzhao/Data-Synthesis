"""Narrow overlay-cache adapter around the byte-identical V35 worker.

The only worker dependency replacement is TaskCache storage lookup.  Whole-task
class calculation, source/pre-state loading, actual V33 gJ input, coordinator
math, numerical admission and resource gates remain the original functions.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
from pathlib import Path

CONTROLLER_NAME = "finqa_v36_controller"
CACHE_NAME = "finqa_v36_cache"
ORIGINAL_CONTROL_NAME = "finqa_v35_task_controller"
ORIGINAL_WORKER_NAME = "finqa_v35_task_worker"
STAGE_GPUS = {"shard01": 4, "coordinator": 7}


def install_overlay_dependency(worker, root, overlay_module, control, *, cache_instances=None):
    """Replace the dependency cache slot, not any numerical function or pool."""
    original_dependencies = worker.dependencies
    unchanged = {
        name: getattr(worker, name)
        for name in (
            "run",
            "execute_shard",
            "execute_coordinator",
            "checked_sources",
            "state_identity",
        )
    }

    def dependencies(given_root):
        control.require(Path(given_root).resolve() == root, "foreign overlay dependency root")
        tail, original_cache, values = original_dependencies(given_root)
        adapter = overlay_module.overlay_adapter(root, original_cache, control)
        control.require(
            adapter.TaskPoolView is original_cache.TaskPoolView
            and adapter.make_task_plan is original_cache.make_task_plan,
            "overlay must not replace task views or mathematical planning",
        )
        control.require(
            all(getattr(worker, name) is function for name, function in unchanged.items()),
            "original scientific worker functions changed",
        )
        if cache_instances is not None:
            factory = adapter.TaskCache

            def tracked_cache(*args, **kwargs):
                control.require(not cache_instances, "one task cache instance per worker")
                cache = factory(*args, **kwargs)
                cache_instances.append(cache)
                return cache

            adapter.TaskCache = tracked_cache
        return tail, adapter, values

    worker.dependencies = dependencies


def install_verification_publisher(control, root, stage, protocol, cache_instances):
    """Seal actual in-process read counts BEFORE the original terminal record.

    This reads metadata already held by the overlay, never re-reads tensors.
    Result publication can fail after this receipt is written; a subsequent
    failure publication may reuse only an identical sealed summary. Numerical
    and resource records at other paths are passed through without changes.
    """
    original_publish = control.publish
    result_path = root / stage / "result/record.json"
    failure_path = root / stage / "failure/record.json"
    receipt_path = root / stage / "cache_tensor_verification/record.json"

    def publish(path, body):
        path = Path(path)
        if path not in (result_path, failure_path):
            return original_publish(path, body)
        control.require(len(cache_instances) <= 1, "ambiguous cache verification provenance")
        summary = (
            cache_instances[0].verification_summary()
            if cache_instances
            else dict(
                index_id=protocol["cache_index"]["id"],
                process_id=os.getpid(),
                parent_tasks_strictly_verified=0,
                local_tasks_strictly_verified=0,
                strict_payload_file_reads=0,
                verified_task_ids=[],
                cross_process_verification_waiver=False,
                parent_gradient_payload_bytes_copied=0,
            )
        )
        if path == result_path:
            expected_parent, expected_local = (183, 0) if stage == "shard01" else (741, 3)
            total = expected_parent + expected_local
            control.require(
                len(cache_instances) == 1
                and summary["index_id"] == protocol["cache_index"]["id"]
                and summary["process_id"] == os.getpid()
                and type(summary["parent_tasks_strictly_verified"]) is int
                and summary["parent_tasks_strictly_verified"] == expected_parent
                and type(summary["local_tasks_strictly_verified"]) is int
                and summary["local_tasks_strictly_verified"] == expected_local
                and type(summary["strict_payload_file_reads"]) is int
                and summary["strict_payload_file_reads"] == total
                and len(summary["verified_task_ids"])
                == len(set(summary["verified_task_ids"]))
                == total
                and summary["cross_process_verification_waiver"] is False
                and summary["parent_gradient_payload_bytes_copied"] == 0,
                "successful stage lacks exact actual cache tensor verification",
            )
        evidence = dict(
            schema="v36_actual_cache_tensor_verification.v1",
            protocol_id=protocol["id"],
            stage=stage,
            cache_constructed=bool(cache_instances),
            summary_from_current_process_overlay=True,
            tensor_payloads_reread_for_receipt=False,
            local_production_validation_is_separate_from_payload_read_counts=True,
            numerical_or_resource_acceptance_not_implied=True,
            **summary,
        )
        if receipt_path.exists():
            old = control.checked(receipt_path)
            control.require(
                {k: v for k, v in old.items() if k not in {"id", "at"}} == evidence,
                "existing tensor verification receipt differs; never overwrite",
            )
        else:
            original_publish(receipt_path, dict(at=control.now(), **evidence))
        return original_publish(
            path, dict(body, cache_tensor_verification=control.entry(receipt_path))
        )

    control.publish = publish


def run(root, stage, gpu_index, deadline_epoch):
    root = Path(root).resolve()
    control = importlib.import_module(CONTROLLER_NAME)
    directory = root / "recovery_implementation"
    control.require(
        Path(__file__).resolve() == directory / Path(__file__).name
        and Path(control.__file__).resolve() == directory / (CONTROLLER_NAME + ".py"),
        "only the sealed V36 worker/controller may run",
    )
    control.require(
        stage in STAGE_GPUS and gpu_index == STAGE_GPUS[stage],
        "V36 permits only GPU4 shard01 then GPU7 coordinator",
    )
    control.checked_v36_implementation(root)
    protocol = control.checked_protocol(root)
    implementation = control.checked_math_implementation(root)
    original_path = root / "implementation" / (ORIGINAL_WORKER_NAME + ".py")
    control.require(
        hashlib.sha256(original_path.read_bytes()).hexdigest()
        == implementation["sha256"][original_path.name],
        "original V35 mathematical worker bytes changed",
    )
    control.require(
        ORIGINAL_CONTROL_NAME not in sys.modules or sys.modules[ORIGINAL_CONTROL_NAME] is control,
        "a different V35 controller is already imported",
    )
    control.require(
        ORIGINAL_WORKER_NAME not in sys.modules, "V36 requires a fresh original worker import"
    )
    sys.modules[ORIGINAL_CONTROL_NAME] = control
    sys.path.insert(0, str(root / "implementation"))
    worker = control._module(original_path, ORIGINAL_WORKER_NAME)
    control.require(
        Path(worker.__file__).resolve() == original_path and worker.control is control,
        "original worker did not bind the validated V36 controller",
    )
    overlay_path = directory / (CACHE_NAME + ".py")
    overlay = control._module(overlay_path, CACHE_NAME)
    control.require(
        Path(overlay.__file__).resolve() == overlay_path,
        "overlay module is outside the sealed V36 implementation",
    )
    cache_instances = []
    install_overlay_dependency(worker, root, overlay, control, cache_instances=cache_instances)
    install_verification_publisher(control, root, stage, protocol, cache_instances)
    return worker.run(root, stage, gpu_index, deadline_epoch)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--stage", choices=tuple(STAGE_GPUS), required=True)
    parser.add_argument("--gpu-index", type=int, required=True)
    parser.add_argument("--deadline-epoch", type=float, required=True)
    args = parser.parse_args()
    result = run(args.root, args.stage, args.gpu_index, args.deadline_epoch)
    print(json.dumps(dict(status=result["status"], id=result["id"])))
