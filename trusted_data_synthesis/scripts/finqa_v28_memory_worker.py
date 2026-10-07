"""Explicit high-cache or shared-checkpointed original scientific execution.

High-cache is best-effort memory reservation, NOT hardware compute exclusivity.
No separate placeholder process or retained reservation tensor is created.
Only the audited model-loading boundary is wrapped, after original GPU admission.
The unchanged loader and CLI retain their scientific arguments and return values.
Shared mode runs the original worker directly, preserving its durable-state and
partial-feedback rules. No mode silently falls back to another, and this wrapper
does not grant generic recovery or feedback-resampling permission.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RESERVATION_BYTES = 76 * 1024**3
MINIMUM_FREE_MIB = 80000
WORKER_HASHES = {
    "finqa_v25_training_replication.py":
        "6be6b697e1517cb87ceb5fc8e33bad73d7affef6e9d9cc8685e88724f019fa05",
    "finqa_v25_evaluation.py":
        "c4b0ac45534a6e0dd12e344bc3cf299c6e44991af7695700a615ce751f292285",
    "finqa_v23_test_confirmation.py":
        "780cc48eb0f23840eb400be138a6277c4261dff17253c162eff9c9cd309a2f74",
}
WORKER_COMMANDS = {
    "finqa_v25_training_replication.py": {"prefix", "train"},
    "finqa_v25_evaluation.py": {"generate"},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()).hexdigest()


def file_reference(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "regular source file required")
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def publish(directory, stage, value):
    path = Path(directory) / (stage + ".json")
    record = {
        "schema": "v28_same_process_memory_reservation.v1",
        "at": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "pid": os.getpid(),
        **value,
    }
    record["id"] = digest(record)
    with path.open("x") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return record


def gpu_snapshot(index):
    """nvidia-smi queries do not initialize a CUDA context in this process."""
    def query(fields, kind):
        result = subprocess.run(
            ["nvidia-smi", "-i", str(index), "--query-" + kind + "=" + fields,
             "--format=csv,noheader,nounits"],
            check=True, capture_output=True, text=True, timeout=30,
        )
        return list(csv.reader(line for line in result.stdout.splitlines() if line.strip()))

    rows = query("uuid,memory.total,memory.free", "gpu")
    require(len(rows) == 1 and len(rows[0]) == 3, "exact physical GPU query required")
    uuid, total, free = (item.strip() for item in rows[0])
    require(uuid.startswith("GPU-"), "physical GPU UUID missing")
    processes = []
    for row in query("gpu_uuid,pid,used_gpu_memory", "compute-apps"):
        require(len(row) == 3 and row[0].strip() == uuid, "unexpected GPU process query")
        processes.append({"pid": int(row[1].strip()), "used_mib": int(row[2].strip())})
    return {
        "gpu_index": index, "uuid": uuid, "total_mib": int(total), "free_mib": int(free),
        "compute_processes": sorted(processes, key=lambda item: item["pid"]),
    }


def check_gpu(snapshot, *, uuid=None, allow_self=False, minimum_free=True):
    require(uuid is None or snapshot["uuid"] == uuid, "GPU UUID changed")
    allowed = {os.getpid()} if allow_self else set()
    require(
        all(row["pid"] in allowed for row in snapshot["compute_processes"]),
        "foreign compute process present; reservation fails closed",
    )
    if minimum_free:
        require(snapshot["free_mib"] >= MINIMUM_FREE_MIB, "insufficient free GPU memory")


def checked_worker(worker, worker_args):
    worker = Path(worker)
    require(not worker.is_symlink(), "symlinked scientific worker is forbidden")
    worker = worker.resolve()
    require(worker.name in WORKER_COMMANDS, "only frozen V25 training/evaluation admitted")
    require(
        worker_args and worker_args[0] in WORKER_COMMANDS[worker.name],
        "only scientific GPU worker commands admitted",
    )
    require(worker_args.count("--gpu-index") == 1, "one original --gpu-index required")
    index = int(worker_args[worker_args.index("--gpu-index") + 1])
    require(index in range(8), "physical GPU index outside original scope")
    require(worker.parent.name == "implementation", "frozen implementation worker required")
    manifest_path = worker.parent / "record.json"
    manifest = json.loads(manifest_path.read_bytes())
    require(
        manifest["id"] == digest({k: v for k, v in manifest.items() if k != "id"}),
        "implementation manifest binding changed",
    )
    references = {}
    for name, sha in WORKER_HASHES.items():
        reference = file_reference(worker.with_name(name))
        require(reference["sha256"] == manifest["sha256"][name] == sha,
                "frozen scientific worker/dependency changed: " + name)
        references[name] = reference
    protocol = json.loads((worker.parent.parent / "protocol/record.json").read_bytes())
    require(
        protocol["id"] == digest({k: v for k, v in protocol.items() if k != "id"})
        and protocol["implementation_id"] == manifest["id"],
        "scientific protocol/implementation identity changed",
    )
    return worker, index, {
        "scientific_protocol_id": protocol["id"],
        "implementation_id": manifest["id"],
        "manifest": file_reference(manifest_path),
        "sources": references,
        "scientific_runtime": manifest["scientific_runtime"],
    }


def load_worker(path):
    # Sibling imports must resolve to the same frozen implementation directory.
    sys.path.insert(0, str(path.parent))
    for name in WORKER_HASHES:
        module_name = Path(name).stem
        if module_name in sys.modules:
            require(
                Path(sys.modules[module_name].__file__).resolve() == path.with_name(name),
                "scientific dependency already imported from another directory",
            )
    specification = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[path.stem] = module
    specification.loader.exec_module(module)
    return module


def reserve_cache(torch, index, uuid, receipt_dir):
    """Run only at the loader boundary, after the worker's original admission."""
    require(os.environ.get("CUDA_VISIBLE_DEVICES") == uuid,
            "reservation called before original GPU admission/UUID mapping")
    require(not torch.cuda.is_initialized(), "unexpected CUDA work before model loader")
    for variable in ("PYTORCH_CUDA_ALLOC_CONF", "PYTORCH_ALLOC_CONF"):
        require(os.environ.get(variable, "") in ("", "backend:native"),
                "custom CUDA allocator configuration would invalidate reusable cache")
    require(os.environ.get("PYTORCH_NO_CUDA_MEMORY_CACHING", "") in ("", "0"),
            "PyTorch CUDA memory caching must remain enabled")
    require(torch.cuda.memory.get_allocator_backend() == "native",
            "native reusable caching allocator required")
    before = gpu_snapshot(index)
    check_gpu(before, uuid=uuid, allow_self=True)
    publish(receipt_dir, "reservation_intent", {
        "gpu_before": before, "reservation_bytes": RESERVATION_BYTES,
        "original_GPU_admission_completed": True, "RNG_calls": 0,
        "tensor_is_temporary_and_cache_is_reusable": True,
        "hardware_compute_exclusive": False,
    })
    tensor = torch.empty(RESERVATION_BYTES, dtype=torch.uint8, device="cuda:0")
    del tensor
    torch.cuda.synchronize()
    reserved = torch.cuda.memory_reserved(0)
    allocated = torch.cuda.memory_allocated(0)
    require(reserved >= RESERVATION_BYTES and allocated == 0,
            "temporary allocation did not become fully reusable CUDA cache")
    after = gpu_snapshot(index)
    check_gpu(after, uuid=uuid, allow_self=True, minimum_free=False)
    publish(receipt_dir, "reserved", {
        "gpu_after": after, "reservation_bytes": RESERVATION_BYTES,
        "torch_memory_reserved_bytes": reserved, "torch_memory_allocated_bytes": allocated,
        "reservation_tensor_retained": False, "separate_placeholder_process": False,
        "cache_can_be_reused_by_original_model": True,
        "hardware_compute_exclusive": False,
        "does_not_guarantee_future_foreign_process_exclusion": True,
        "allocator_can_release_cache_if_required": True,
    })


def maintain_loaded_cache(torch, index, uuid, receipt_dir):
    """One post-loader check/refill, never a background memory-consuming loop."""
    before = gpu_snapshot(index)
    check_gpu(before, uuid=uuid, allow_self=True, minimum_free=False)
    reserved_before = torch.cuda.memory_reserved(0)
    allocated_before = torch.cuda.memory_allocated(0)
    refill_bytes = 0
    if reserved_before < RESERVATION_BYTES:
        # Allocating target-reserved could reuse existing free cache without
        # raising total reserved memory. target-allocated must coexist with all
        # live model tensors and therefore restores the full intended floor.
        refill_bytes = RESERVATION_BYTES - allocated_before
        require(refill_bytes > 0, "inconsistent CUDA allocator counters")
        tensor = torch.empty(refill_bytes, dtype=torch.uint8, device="cuda:0")
        del tensor
        torch.cuda.synchronize()
    reserved_after = torch.cuda.memory_reserved(0)
    allocated_after = torch.cuda.memory_allocated(0)
    require(reserved_after >= RESERVATION_BYTES and allocated_after == allocated_before,
            "post-loader reusable cache floor not retained")
    after = gpu_snapshot(index)
    check_gpu(after, uuid=uuid, allow_self=True, minimum_free=False)
    publish(receipt_dir, "model_loaded", {
        "gpu_after": after, "torch_memory_reserved_before_bytes": reserved_before,
        "torch_memory_reserved_bytes": reserved_after,
        "torch_memory_allocated_bytes": allocated_after,
        "post_load_refill_bytes": refill_bytes,
        "reservation_tensor_retained": False, "hardware_compute_exclusive": False,
        "no_periodic_memory_fill": True,
    })


def install_loader_hook(worker, runtime, index, uuid, receipt_dir):
    if worker.__name__ == "finqa_v25_training_replication":
        owner, attribute, torch = runtime.launcher, "_load_components", runtime.torch
    else:
        require(worker.__name__ == "finqa_v25_evaluation", "unrecognized worker module")
        owner, attribute, torch = runtime, "load_final_provider", runtime.torch
    original = getattr(owner, attribute)
    state = {"calls": 0, "loader_calls": 0}

    def wrapped(*args, **kwargs):
        require(state["calls"] == 0, "one original scientific model load required")
        state["calls"] += 1
        try:
            reserve_cache(torch, index, uuid, receipt_dir)
            # No altered seed, batch, dtype, precision, optimizer or RNG arguments.
            state["loader_calls"] += 1
            result = original(*args, **kwargs)
            maintain_loaded_cache(torch, index, uuid, receipt_dir)
            return result
        except BaseException as error:
            publish(receipt_dir, "loader_failure", {
                "error_type": type(error).__name__, "error": str(error),
                "automatic_retry": False, "scientific_loader_calls": state["loader_calls"],
            })
            raise

    setattr(owner, attribute, wrapped)
    return owner, attribute, original, state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--receipt-dir", type=Path, required=True)
    parser.add_argument(
        "--memory-mode", choices=("high_cache", "shared_checkpointed"), required=True
    )
    parser.add_argument("worker_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    require(args.worker_args and args.worker_args[0] == "--", "original CLI separator required")
    worker_args = args.worker_args[1:]
    worker_path, index, binding = checked_worker(args.worker, worker_args)
    before = gpu_snapshot(index)
    if args.memory_mode == "high_cache":
        check_gpu(before)
    args.receipt_dir.mkdir(parents=True, exist_ok=False)
    publish(args.receipt_dir, "wrapper_intent", {
        "source_binding": binding, "original_command": [str(worker_path), *worker_args],
        "gpu_before_import": before, "memory_mode": args.memory_mode,
        "reservation_bytes": RESERVATION_BYTES if args.memory_mode == "high_cache" else 0,
        "minimum_free_mib": MINIMUM_FREE_MIB if args.memory_mode == "high_cache" else None,
        "scientific_arguments_changed": False, "hardware_compute_exclusive": False,
        "original_worker_GPU_admission_preserved": True,
        "silent_mode_fallback": False,
        "checkpoint_policy": {
            "owned_by_unchanged_scientific_worker": True,
            "training_commits_after_each_optimizer_step": True,
            "training_state": ["model", "buffers", "Adam", "RNG", "pi", "step", "schedule"],
            "evaluation_commits_completed_episodes": True,
            "incomplete_feedback_retained_not_resampled": True,
            "resume_requires_explicit_safe_boundary_proof": True,
            "automatic_retry_authorized_by_wrapper": False,
        },
    })
    worker = load_worker(worker_path)
    hook = None
    if args.memory_mode == "high_cache":
        runtime = worker.load_runtime()
        hook = install_loader_hook(worker, runtime, index, before["uuid"], args.receipt_dir)
    original_argv = sys.argv
    try:
        sys.argv = [str(worker_path), *worker_args]
        worker.main()
        if hook is not None:
            require(hook[3]["calls"] == 1,
                    "scientific worker completed without its registered loader")
        publish(args.receipt_dir, "worker_returned", {
            "memory_mode": args.memory_mode,
            "scientific_loader_calls": hook[3]["loader_calls"] if hook else None,
            "original_cli_preserved": True,
            "reservation_performed": hook is not None,
            "RNG_calls_by_wrapper": 0,
        })
    except BaseException as error:
        publish(args.receipt_dir, "worker_failure", {
            "memory_mode": args.memory_mode,
            "error_type": type(error).__name__, "error": str(error),
            "automatic_retry": False, "feedback_resampling": False,
            "original_worker_durable_state_retained": True,
        })
        raise
    finally:
        sys.argv = original_argv
        if hook is not None:
            owner, attribute, original, _state = hook
            setattr(owner, attribute, original)


if __name__ == "__main__":
    main()
