"""The only production process entry: install signal receipt handling first."""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys

import finqa_v63_binding as binding
import finqa_v63_signals as signals

WORKER_IMPORTS = (
    "finqa_v63_temperature", "finqa_v34_tail_memory", "finqa_v32_same_point_guard",
    "finqa_v56_feedback",
    "trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.trajectory_consumer",
    "trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.optimizer_pullback",
    "trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.distribution",
)
RECOVERY_IMPORTS = ("finqa_v56_worker", "finqa_v63_worker_audit")
NEW_IMPORTS = (
    "finqa_v63_draw_components", "finqa_v63_training",
    "finqa_v63_runtime", "finqa_v63_worker", "finqa_v63_evaluation",
    "finqa_v63_controller", "finqa_v63_diagnostics", "finqa_v63_registration",
)
AUXILIARY_NAME = "finqa_v25_training_replication"
AUXILIARY_CANONICAL = binding.V18 / "v25_training_replication_01/implementation/finqa_v25_training_replication.py"
AUXILIARY_WORKSPACE_ALIAS = binding.REPO / "trusted_data_synthesis/scripts/finqa_v25_training_replication.py"
MODES = ("supervise", "run", "worker", "generate", "check-imports")


def checked_signal_registration(root, *, protocol=None):
    """Read only pure metadata before the observer or any science is imported."""
    root = Path(root).resolve()
    binding.require(root == binding.ROOT.resolve(), "foreign signal registration root")
    protocol = binding.checked(root / "protocol/record.json") if protocol is None else protocol
    binding.require(protocol.get("signal_policy") == signals.signals_policy(),
                    "registered V63 signal policy differs from the installed inherited filter")
    binding.require(protocol.get("signal_source_bindings") == signals.external_source_bindings(),
                    "registered V63 signal sources differ from the exact frozen source chain")
    return protocol


def _registered_auxiliary(science):
    path = AUXILIARY_CANONICAL.resolve()
    external = science["external_frozen_source_sha256"]
    binding.require(str(path) in external,
                    "the exact original V25 auxiliary path must be registered")
    expected = external[str(path)]
    binding.require(binding.sha(path) == expected, "original V25 auxiliary source bytes changed")
    return dict(path=str(path), sha256=expected)


def install_registered_auxiliary():
    """Load the one canonical external dependency; never add workspace paths."""
    science = binding.checked(binding.OLD_ROOT / "implementation/record.json")
    binding.require(science["id"] == binding.OLD_IMPLEMENTATION_ID,
                    "original scientific implementation changed")
    reference = _registered_auxiliary(science)
    existing = sys.modules.get(AUXILIARY_NAME)
    if existing is not None:
        origin = Path(existing.__file__).resolve()
        binding.require(origin in (AUXILIARY_CANONICAL.resolve(), AUXILIARY_WORKSPACE_ALIAS.resolve())
                        and binding.sha(origin) == reference["sha256"],
                        "preimported auxiliary must be the one registered byte-identical V25 source")
        return dict(reference, actual_path=str(origin), path_alias=str(origin) != reference["path"])
    spec = importlib.util.spec_from_file_location(AUXILIARY_NAME, reference["path"])
    binding.require(spec is not None and spec.loader is not None, "registered auxiliary loader unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[AUXILIARY_NAME] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(AUXILIARY_NAME, None)
        raise
    return dict(reference, actual_path=reference["path"], path_alias=False)


def verify_imported_modules(root, implementation, science, external_signals, *, modules=None):
    """Reject workspace science, even if the apparent module name is frozen."""
    root = Path(root).resolve()
    directory = root / "implementation"
    old_directory = (binding.OLD_ROOT / "implementation").resolve()
    frozen_source = Path(science["frozen_source_root"]).resolve()
    external = science["external_frozen_source_sha256"]
    signal_sources = {str(Path(ref["path"]).resolve()): ref["sha256"]
                      for ref in external_signals.values() if Path(ref["path"]).suffix == ".py"}
    aux = _registered_auxiliary(science)
    observed, aliases, hashes = [], [], {}
    for name, module in sorted((sys.modules if modules is None else modules).items()):
        origin = getattr(module, "__file__", None)
        if not origin:
            continue
        path = Path(origin).resolve()
        package = name == "trusted_synthesis" or name.startswith("trusted_synthesis.")
        script = path.name.startswith("finqa_") or name.startswith("finqa_")
        if not package and not script and str(path) not in signal_sources:
            continue
        binding.require(not package or path.is_relative_to(frozen_source),
                        "workspace/non-frozen trusted_synthesis package imported: " + str(path))
        registered_path = str(path)
        if path.parent == directory and path.name in implementation["sha256"]:
            expected, category = implementation["sha256"][path.name], "new_frozen_bundle"
        elif str(path) in signal_sources:
            expected, category = signal_sources[str(path)], "registered_external_signal_source"
        elif str(path) in external:
            expected, category = external[str(path)], "original_external_frozen_science"
        elif path.parent == old_directory and path.name in science["sha256"]:
            expected, category = science["sha256"][path.name], "original_byte_frozen_96_source"
        elif path == AUXILIARY_WORKSPACE_ALIAS.resolve():
            registered_path, expected = aux["path"], aux["sha256"]
            category = "explicit_original_V25_byte_identical_path_alias"
        else:
            raise ValueError("unregistered scientific/import source: " + str(path))
        if str(path) not in hashes:
            hashes[str(path)] = binding.sha(path)
        actual = hashes[str(path)]
        binding.require(actual == expected, "imported source bytes differ from registration: " + str(path))
        row = dict(module=name, path=str(path), sha256=actual,
                   registered_path=registered_path, origin=category)
        observed.append(row)
        if registered_path != str(path):
            aliases.append(row)
    return dict(
        verified_dependencies=observed, verified_dependency_count=len(observed),
        verified_dependencies_digest=binding.digest(observed),
        registered_byte_identical_path_aliases=aliases,
        implicit_workspace_scientific_path_allowed=False,
        allowed_auxiliary_aliases={str(AUXILIARY_WORKSPACE_ALIAS.resolve()): aux},
    )


def check_imports(root):
    """Actual cold worker dependency imports, without parent/model/CUDA work."""
    root = Path(root).resolve()
    binding.require(root == binding.ROOT.resolve(), "foreign CPU dependency-check root")
    registration = importlib.import_module("finqa_v63_registration")
    protocol = registration.checked_protocol(root)
    checked_signal_registration(root, protocol=protocol)
    implementation = registration.checked_implementation(root)
    science = binding.checked(binding.OLD_ROOT / "implementation/record.json")
    binding.require(science["id"] == binding.OLD_IMPLEMENTATION_ID,
                    "original mathematical source identity changed")
    auxiliary = install_registered_auxiliary()
    training = importlib.import_module("finqa_v63_training")
    _, runtime = training.runtime()
    for name in (*WORKER_IMPORTS, *RECOVERY_IMPORTS, *NEW_IMPORTS):
        importlib.import_module(name)
    binding.require(not runtime.torch.cuda.is_initialized(),
                    "CPU import check must not initialize CUDA")
    external_signals = signals.external_source_bindings()
    dependencies = verify_imported_modules(root, implementation, science, external_signals)
    resources = importlib.import_module("finqa_v63_runtime")
    binding.require(resources.ResourceGuard.__module__ == "finqa_v63_runtime",
                    "actual V63 resource guard is not installed")
    value = dict(
        schema="v63_actual_frozen_worker_cpu_import_check.v1", status="PASS",
        protocol_id=protocol["id"], implementation_id=implementation["id"],
        original_implementation_id=science["id"], science_root=str(root),
        original_runtime_first=True, actual_worker_import_order=list(WORKER_IMPORTS),
        actual_recovery_import_order=list(RECOVERY_IMPORTS), new_import_order=list(NEW_IMPORTS),
        registered_auxiliary=auxiliary, external_signal_sources=external_signals,
        installed_resource_guard=dict(module=resources.ResourceGuard.__module__,
                                      qualname=resources.ResourceGuard.__qualname__),
        CUDA_initialized=False, parent_loaded=False, model_loaded=False,
        scientific_calls=0, optimizer_updates=0, standalone_machine_wide_observer_started=False,
        **dependencies,
    )
    return dict(value, id=binding.digest(value))


def _arguments(argv):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--root", type=Path, default=binding.ROOT)
    parser.add_argument("--controller-attempt", type=int, default=1)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--stage")
    parser.add_argument("--gpu-index", type=int)
    parser.add_argument("--job")
    parser.add_argument("--gpu", type=int)
    parser.add_argument("--attempt-root", type=Path)
    return parser.parse_args(argv)


def _validate_arguments(args):
    root = args.root.resolve()
    binding.require(root == binding.ROOT.resolve(), "V63 entry accepts only its registered new root")
    binding.require(Path(__file__).resolve().parent == root / "implementation",
                    "production entry and CPU preflight must execute from the new frozen implementation")
    binding.require(type(args.controller_attempt) is int and args.controller_attempt >= 1,
                    "positive controller attempt required")
    if args.mode in ("worker", "generate"):
        binding.require(args.attempt_root is not None,
                        "a worker must have its dispatched independent attempt root")
        attempt = args.attempt_root.resolve()
        binding.require(not args.attempt_root.is_symlink()
                        and attempt.is_relative_to(root) and attempt.parent.name == "attempts"
                        and attempt.name.startswith("attempt") and attempt.name[7:].isdigit()
                        and len(attempt.name[7:]) >= 4,
                        "worker attempt escaped the registered root or attempt format")
        binding.require(os.environ.get("V63_ATTEMPT_DIR") == str(attempt)
                        and os.environ.get("V56_ATTEMPT_DIR") == str(attempt)
                        and os.environ.get("V63_ATTEMPT_ID") == attempt.name
                        and os.environ.get("V56_ATTEMPT_ID") == attempt.name,
                        "new and inherited resumable attempt identities must agree")
    if args.mode == "worker":
        stages = {f"{phase}_{arm}" for phase in ("feedback", "replay", "distribution", "train")
                  for arm in binding.ARMS}
        binding.require(args.seed in binding.SEEDS and args.stage in stages
                        and args.gpu_index in range(8), "unregistered science worker coordinate")
        expected = root / "stages" / f"seed{args.seed}" / args.stage / "attempts"
        binding.require(args.attempt_root.resolve().parent == expected
                        and os.environ.get("V54_JOB_ID") == f"seed{args.seed}.{args.stage}",
                        "science worker attempt and project job identity differ")
    elif args.mode == "generate":
        binding.require(isinstance(args.job, str) and args.job
                        and args.gpu in range(8), "registered generation job/GPU required")
        binding.require(args.attempt_root.resolve().parent == root / "evaluations/jobs" / args.job / "attempts"
                        and os.environ.get("V54_JOB_ID") == args.job,
                        "evaluation attempt and project job identity differ")
    return root


def _signal_directory(root, args):
    if args.mode in ("worker", "generate"):
        return args.attempt_root.resolve() / "signals"
    if args.mode == "run":
        return root / "controllers" / f"attempt{args.controller_attempt:04d}" / "signals"
    if args.mode == "supervise":
        return root / "supervisor/signals"
    return root / "frozen_worker_import_verification/signals"


def _dispatch(root, args):
    if args.mode == "check-imports":
        return check_imports(root)
    if args.mode in ("supervise", "run"):
        controller = importlib.import_module("finqa_v63_controller")
        return (controller.supervise(root) if args.mode == "supervise"
                else controller.Controller(root, controller_attempt=args.controller_attempt).run())
    if args.mode == "worker":
        return importlib.import_module("finqa_v63_worker").run(
            root, args.seed, args.stage, args.gpu_index, attempt_root=args.attempt_root.resolve())
    return importlib.import_module("finqa_v63_evaluation").worker(root, args.job, args.gpu)


def exit_status(result, mode):
    status = result.get("status")
    if mode == "check-imports":
        return 0 if status == "PASS" else 2
    if status == "CONTROLLER_TRANSIENT_FAILURE":
        return 75
    return 0 if status == "COMPLETE" else 2


def main(argv=None):
    args = _arguments(sys.argv[1:] if argv is None else argv)
    root = _validate_arguments(args)
    checked_signal_registration(root)
    observer = signals.install(_signal_directory(root, args), role=args.mode, context=dict(
        mode=args.mode, job_id=os.environ.get("V54_JOB_ID"),
        attempt_id=os.environ.get("V63_ATTEMPT_ID"), feedback_batch=binding.BATCH,
        CPU_import_check=args.mode == "check-imports"))
    try:
        binding.install_scientific_paths()
        install_registered_auxiliary()
        result = _dispatch(root, args)
        print(json.dumps(result if args.mode == "check-imports" else dict(
            schema=result.get("schema"), id=result.get("id"), status=result.get("status")), sort_keys=True))
        return exit_status(result, args.mode)
    finally:
        observer.close()


if __name__ == "__main__":
    raise SystemExit(main())
