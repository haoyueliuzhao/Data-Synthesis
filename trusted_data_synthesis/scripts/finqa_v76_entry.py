"""Only frozen production entry for V76; install the stop filter before science."""
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import sys

import finqa_v76_binding as binding
import finqa_v76_signals as signals

MODES = ("supervise", "run", "worker", "generate", "score", "check-imports")


def _arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--root", type=Path, default=binding.ROOT)
    parser.add_argument("--controller-attempt", type=int, default=1)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--stage")
    parser.add_argument("--job")
    parser.add_argument("--gpu-index", type=int)
    parser.add_argument("--gpu", type=int)
    parser.add_argument("--attempt-root", type=Path)
    return parser.parse_args(argv)


def _validate_arguments(args):
    root = args.root.resolve()
    binding.require(root == binding.ROOT.resolve()
                    and Path(__file__).resolve().parent == root / "implementation",
                    "V76 execution and CPU preflight require its registered frozen entry")
    binding.require(type(args.controller_attempt) is int and args.controller_attempt >= 1,
                    "positive controller attempt required")
    if args.mode in ("worker", "generate"):
        binding.require(args.attempt_root is not None, "a worker needs its independent dispatched attempt")
        attempt = args.attempt_root.resolve()
        binding.require(not args.attempt_root.is_symlink() and attempt.is_relative_to(root)
                        and attempt.parent.name == "attempts" and attempt.name.startswith("attempt")
                        and attempt.name[7:].isdigit() and len(attempt.name[7:]) >= 4,
                        "invalid worker attempt directory")
        for prefix in ("V76", "V63", "V56"):
            binding.require(os.environ.get(prefix + "_ATTEMPT_DIR") == str(attempt)
                            and os.environ.get(prefix + "_ATTEMPT_ID") == attempt.name,
                            "new/inherited durable attempt aliases disagree")
    if args.mode == "worker":
        queue = importlib.import_module("finqa_v76_queue_base")
        binding.require(args.seed == 137 and args.stage in queue.core_jobs()
                        and args.gpu_index in range(8), "unregistered V76 job/device")
        job = queue.core_jobs()[args.stage]
        binding.require(args.attempt_root.resolve().parent == queue.job_directory(root,job)/"attempts"
                        and os.environ.get("V54_JOB_ID") == job["job_id"],
                        "scientific attempt and project lease identity disagree")
    if args.mode == "generate":
        binding.require(isinstance(args.job, str) and args.job and "/" not in args.job
                        and args.gpu in range(8)
                        and args.attempt_root.resolve().parent == root / "evaluations/jobs" / args.job / "attempts"
                        and os.environ.get("V54_JOB_ID") == args.job,
                        "evaluation attempt/job/device changed")
    if args.mode == "score":
        binding.require(args.attempt_root is not None
                        and args.attempt_root.resolve() == root / "final_analysis/attempt0001"
                        and os.environ.get("V76_CPU_ANALYSIS_ATTEMPT") == str(args.attempt_root.resolve()),
                        "only the registered single final CPU analysis child is allowed")
    return root


def _signal_directory(root, args):
    if args.mode in ("worker", "generate", "score"):
        return args.attempt_root.resolve() / "signals"
    if args.mode == "run":
        return root / "controllers" / f"attempt{args.controller_attempt:04d}" / "signals"
    return root / ("supervisor/signals" if args.mode == "supervise" else "frozen_worker_import_verification/signals")


def verify_imported_sources(root, implementation, *, modules=None):
    registration = importlib.import_module("finqa_v76_registration")
    allowed = registration.allowed_import_sources(root)
    frozen_package = Path(implementation["frozen_source_root"]).resolve()
    rows, actual_hashes = [], {}
    for name, module in sorted((sys.modules if modules is None else modules).items()):
        origin = getattr(module, "__file__", None)
        if not origin:
            continue
        path = Path(origin).resolve()
        package = name == "trusted_synthesis" or name.startswith("trusted_synthesis.")
        script = path.name.startswith("finqa_") or name.startswith("finqa_")
        if not package and not script:
            continue
        binding.require(not package or path.is_relative_to(frozen_package),
                        "workspace/non-frozen scientific package imported: " + str(path))
        binding.require(str(path) in allowed, "unregistered imported source: " + str(path))
        if str(path) not in actual_hashes:
            actual_hashes[str(path)] = binding.sha(path)
        binding.require(actual_hashes[str(path)] == allowed[str(path)],
                        "actual imported source bytes changed: " + str(path))
        rows.append(dict(module=name, path=str(path), sha256=actual_hashes[str(path)]))
    return dict(verified_dependencies=rows, verified_dependency_count=len(rows),
                verified_dependencies_digest=binding.digest(rows),
                implicit_workspace_scientific_path_allowed=False)


def check_imports(root):
    registration = importlib.import_module("finqa_v76_registration")
    protocol = registration.checked_protocol(root)
    implementation = registration.checked_implementation(root)
    binding.install_registered_auxiliary()
    training = importlib.import_module("finqa_v76_training")
    _training, runtime = training.runtime()
    modules = ("finqa_v76_resources", "finqa_v76_queue_base", "finqa_v76_runtime",
               "finqa_v76_worker", "finqa_v76_controller", "finqa_v76_evaluation",
               "finqa_v76_diagnostics")
    for name in modules:
        importlib.import_module(name)
    evaluation = importlib.import_module("finqa_v76_evaluation")
    preflight = importlib.import_module("finqa_v76_resources").validate_registered_contract(protocol)
    binding.require(not runtime.torch.cuda.is_initialized(), "CPU preflight must not initialize CUDA")
    dependencies = verify_imported_sources(root, implementation)
    body = dict(schema="v76_actual_frozen_worker_cpu_import_check.v1", status="PASS",
        protocol_id=protocol["id"], implementation_id=implementation["id"],
        science_root=str(root), actual_worker_import_order=list(modules),
        CUDA_initialized=False, model_loaded=False, parent_loaded=False,
        scientific_calls=0, optimizer_updates=0, evaluation_preflight=preflight,
        old_numeric_or_UNKNOWN_exceptions_imported=False, **dependencies)
    return dict(body, id=binding.digest(body))


def _dispatch(root, args):
    if args.mode == "check-imports":
        return check_imports(root)
    if args.mode in ("supervise", "run"):
        controller = importlib.import_module("finqa_v76_controller")
        return controller.supervise(root) if args.mode == "supervise" else controller.Controller(
            root, controller_attempt=args.controller_attempt).run()
    if args.mode == "score":
        return importlib.import_module("finqa_v76_analysis").run(root, args.attempt_root.resolve())
    queue = importlib.import_module("finqa_v76_queue_base")
    if args.mode == "worker":
        job = queue.core_jobs()[args.stage]
        gpu = args.gpu_index
    else:
        job, gpu = queue.generation_jobs()[args.job], args.gpu
    return importlib.import_module("finqa_v76_worker").run(
        root, job, gpu, attempt_root=args.attempt_root.resolve())


def exit_status(result, mode):
    if mode == "check-imports":
        return 0 if result.get("status") == "PASS" else 2
    if result.get("status") == "CONTROLLER_TRANSIENT_FAILURE":
        return 75
    return 0 if result.get("status") == "COMPLETE" else 2


def main(argv=None):
    args = _arguments(sys.argv[1:] if argv is None else argv)
    root = _validate_arguments(args)
    protocol = binding.checked(root / "protocol/record.json")
    binding.require(protocol["signal_policy"] == signals.signals_policy()
                    and protocol["signal_source_bindings"] == signals.external_source_bindings(),
                    "registered original signal filter changed")
    observer = signals.install(_signal_directory(root, args), role=args.mode,
        context=dict(mode=args.mode, job_id=os.environ.get("V54_JOB_ID"),
                     attempt_id=os.environ.get("V76_ATTEMPT_ID"), experiment="V76"))
    try:
        binding.install_scientific_paths()
        binding.install_registered_auxiliary()
        result = _dispatch(root, args)
        print(json.dumps(result if args.mode == "check-imports" else
                         {key: result.get(key) for key in ("schema", "id", "status")}, sort_keys=True))
        return exit_status(result, args.mode)
    finally:
        observer.close()


if __name__ == "__main__":
    raise SystemExit(main())
