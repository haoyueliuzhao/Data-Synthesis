"""Frozen V64 entry: unchanged legal-stop filter before scientific imports."""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import re
import sys

import finqa_v64_binding as binding

MODES = ("supervise", "run", "worker", "generate", "check-imports")
_OBSERVER = None


def signal_api():
    return binding.source_module("finqa_v63_signals")


def checked_signal_registration(root, *, protocol=None):
    """Pure source/record checks; do not import runtime or model dependencies."""
    root = Path(root).resolve()
    binding.require(root == binding.ROOT.resolve(), "foreign protection signal root")
    protocol = binding.checked(root / "protocol/record.json") if protocol is None else protocol
    original = binding.checked(binding.SCIENTIFIC_ROOT / "protocol/record.json")
    binding.require(original["id"] == binding.BASE_PROTOCOL_ID
                    and protocol["scientific_protocol_id"] == original["id"],
                    "protection signal registration changed scientific identity")
    signals = signal_api()
    binding.require(protocol["signal_policy"] == original["signal_policy"] == signals.signals_policy()
                    and protocol["signal_source_bindings"] == original["signal_source_bindings"]
                        == signals.external_source_bindings(),
                    "registered signal filter must remain the exact authorized V63 policy")
    return protocol


def require_early_install(modules=None):
    allowed = {"finqa_v64_binding.py", "finqa_v64_entry.py", "finqa_v63_binding.py",
               "finqa_v63_signals.py", "finqa_v59_signals.py", "finqa_v58_signals.py",
               "finqa_v58_observer.py"}
    for name, module in (sys.modules if modules is None else modules).items():
        origin = getattr(module, "__file__", None)
        if (name == "torch" or name.startswith("torch.")
                or name == "trusted_synthesis" or name.startswith("trusted_synthesis.")
                or origin and Path(origin).name.startswith("finqa_") and Path(origin).name not in allowed):
            raise RuntimeError("V64 signal observation must precede every scientific import: " + name)


def install_signal_observer(root, args, protocol):
    global _OBSERVER
    binding.require(_OBSERVER is None, "protection signal observer is installed only once")
    binding.require(os.getuid() == os.geteuid() == binding.OWNER_UID,
                    "the unchanged legal-stop filter requires registered nonroot UID1004")
    require_early_install()
    if args.mode in ("worker", "generate"):
        directory = args.attempt_root.resolve() / "signals"
    elif args.mode == "run":
        directory = root / "controllers" / f"attempt{args.controller_attempt:04d}" / "signals"
    elif args.mode == "supervise":
        directory = root / "supervisor/signals"
    else:
        directory = root / "frozen_worker_import_verification/signals"
    binding.require(directory.is_relative_to(binding.SCIENTIFIC_ROOT.resolve()),
                    "signal evidence escaped its registered science/control directories")
    # The V63 wrapper's early allowlist deliberately knows no V64 entry. Reuse
    # its exact already-verified V59 filter, with our stricter early allowlist,
    # instead of mutating that old module or expanding the filtering policy.
    _OBSERVER = signal_api()._reference().install(directory, role=args.mode, context=dict(
        mode=args.mode, control_root=str(root), control_protocol_id=protocol["id"],
        scientific_root=str(binding.SCIENTIFIC_ROOT), scientific_protocol_id=binding.BASE_PROTOCOL_ID,
        job_id=os.environ.get("V54_JOB_ID"), attempt_id=os.environ.get("V63_ATTEMPT_ID"),
        inherited_signal_policy_unchanged=True, CPU_import_check=args.mode == "check-imports"))
    return _OBSERVER


def initialize_science():
    old_binding = binding.source_module("finqa_v63_binding")
    old_binding.install_scientific_paths()
    original_entry = binding.source_module("finqa_v63_entry")
    original_entry.install_registered_auxiliary()
    return original_entry


def verify_imported_modules(root, implementation, *, modules=None):
    """Only exact new frozen files plus the original frozen source closure."""
    root = Path(root).resolve()
    binding.require(root == binding.ROOT.resolve(), "foreign protection dependency root")
    new_directory = root / "implementation"
    source_modules, new_modules = {}, []
    supplied = sys.modules if modules is None else modules
    for name, module in sorted(supplied.items()):
        origin = getattr(module, "__file__", None)
        if not origin:
            continue
        path = Path(origin).resolve()
        if path.name.startswith("finqa_v64_") or name.startswith("finqa_v64_"):
            binding.require(path.parent == new_directory and path.name in implementation["sha256"],
                            "unregistered or workspace protection module: " + str(path))
            actual = binding.sha(path)
            binding.require(actual == implementation["sha256"][path.name],
                            "frozen protection source bytes changed: " + str(path))
            new_modules.append(dict(module=name, path=str(path), sha256=actual,
                                    origin="new_frozen_operational_protection_bundle"))
        else:
            source_modules[name] = module
    old_binding = binding.source_module("finqa_v63_binding")
    original_entry = binding.source_module("finqa_v63_entry")
    original_implementation = binding.checked(binding.SCIENTIFIC_ROOT / "implementation/record.json")
    binding.require(original_implementation["id"] == binding.BASE_IMPLEMENTATION_ID,
                    "original V63 implementation identity changed")
    science = old_binding.checked(old_binding.OLD_ROOT / "implementation/record.json")
    binding.require(science["id"] == old_binding.OLD_IMPLEMENTATION_ID,
                    "original mathematical source bundle changed")
    original = original_entry.verify_imported_modules(binding.SCIENTIFIC_ROOT, original_implementation,
        science, signal_api().external_source_bindings(), modules=source_modules)
    values = original["verified_dependencies"] + new_modules
    return dict(original, verified_dependencies=values, verified_dependency_count=len(values),
        verified_dependencies_digest=binding.digest(values), operational_sources=new_modules,
        original_scientific_protocol_id=binding.BASE_PROTOCOL_ID,
        original_scientific_implementation_id=binding.BASE_IMPLEMENTATION_ID,
        new_operational_protocol_does_not_replace_scientific_identity=True)


def check_imports(root):
    root = Path(root).resolve()
    binding.require(root == binding.ROOT.resolve(), "foreign protection dependency-check root")
    original_entry = initialize_science()
    registration = importlib.import_module("finqa_v64_registration")
    protocol = registration.checked_protocol(root)
    checked_signal_registration(root, protocol=protocol)
    implementation = registration.checked_implementation(root)
    training = binding.source_module("finqa_v63_training")
    _, runtime = training.runtime()
    for name in (*original_entry.WORKER_IMPORTS, *original_entry.RECOVERY_IMPORTS,
                 *original_entry.NEW_IMPORTS):
        importlib.import_module(name)
    for name in ("finqa_v64_runtime", "finqa_v64_worker", "finqa_v64_controller", "finqa_v64_handoff"):
        importlib.import_module(name)
    binding.require(not runtime.torch.cuda.is_initialized(),
                    "protection CPU dependency check must not initialize CUDA")
    resources = importlib.import_module("finqa_v64_runtime")
    worker = importlib.import_module("finqa_v64_worker")
    binding.require(resources.ResourceGuard.__module__ == "finqa_v64_runtime"
                    and worker._worker.ScientificMonitor is resources.ScientificMonitor,
                    "the actual private worker must install the registered protection guard and monitor")
    dependencies = verify_imported_modules(root, implementation)
    body = dict(schema="v64_actual_frozen_worker_CPU_import_check.v1", status="PASS",
        protocol_id=binding.BASE_PROTOCOL_ID, control_protocol_id=protocol["id"],
        implementation_id=implementation["id"], scientific_root=str(binding.SCIENTIFIC_ROOT),
        control_root=str(root), CUDA_initialized=False, parent_loaded=False, model_loaded=False,
        scientific_calls=0, optimizer_updates=0, standalone_machine_wide_observer_started=False,
        installed_resource_guard=dict(module=resources.ResourceGuard.__module__,
                                      qualname=resources.ResourceGuard.__qualname__),
        memory_protection_policy=resources.memory_protection_policy(), **dependencies)
    return dict(body, id=binding.digest(body))


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
    binding.require(root == binding.ROOT.resolve(), "V64 entry requires its independent registered control root")
    binding.require(Path(__file__).resolve().parent == root / "implementation",
                    "production entry and CPU preflight must execute from the new frozen implementation")
    binding.require(type(args.controller_attempt) is int and args.controller_attempt >= 1,
                    "positive controller attempt required")
    if args.mode in ("worker", "generate"):
        binding.require(args.attempt_root is not None, "worker requires an independently dispatched attempt")
        attempt = args.attempt_root.resolve()
        binding.require(not args.attempt_root.is_symlink()
                        and attempt.is_relative_to(binding.SCIENTIFIC_ROOT.resolve())
                        and attempt.parent.name == "attempts"
                        and re.fullmatch(r"attempt[0-9]{4,}", attempt.name) is not None,
                        "worker attempt escaped the unchanged scientific root")
        binding.require(os.environ.get("V63_ATTEMPT_DIR") == str(attempt)
                        and os.environ.get("V56_ATTEMPT_DIR") == str(attempt)
                        and os.environ.get("V63_ATTEMPT_ID") == attempt.name
                        and os.environ.get("V56_ATTEMPT_ID") == attempt.name
                        and os.environ.get("V64_CONTROL_ROOT") == str(root),
                        "old attempt aliases or new protection root differ")
    if args.mode == "worker":
        allowed = {f"{phase}_{arm}" for phase in ("feedback", "replay", "distribution", "train")
                   for arm in ("C1", "C05")}
        binding.require(args.seed in (137, 251, 389) and args.stage in allowed
                        and args.gpu_index in range(8), "unregistered scientific worker coordinate")
        expected = binding.SCIENTIFIC_ROOT / "stages" / f"seed{args.seed}" / args.stage / "attempts"
        binding.require(args.attempt_root.resolve().parent == expected
                        and os.environ.get("V54_JOB_ID") == f"seed{args.seed}.{args.stage}",
                        "scientific job and unchanged attempt directory differ")
    elif args.mode == "generate":
        binding.require(isinstance(args.job, str) and args.job and "/" not in args.job
                        and "\\" not in args.job and args.gpu in range(8),
                        "registered evaluation job and GPU required")
        binding.require(args.attempt_root.resolve().parent == binding.SCIENTIFIC_ROOT / "evaluations/jobs" / args.job / "attempts"
                        and os.environ.get("V54_JOB_ID") == args.job,
                        "evaluation job and unchanged attempt directory differ")
    return root


def _dispatch(root, args):
    if args.mode == "check-imports":
        return check_imports(root)
    registration = importlib.import_module("finqa_v64_registration")
    protocol = registration.checked_protocol(root)
    registration.checked_implementation(root)
    if args.mode in ("supervise", "run"):
        controller = importlib.import_module("finqa_v64_controller")
        return (controller.supervise(root) if args.mode == "supervise" else
                controller.Controller(root, controller_attempt=args.controller_attempt).run())
    binding.require(os.environ.get("V64_CONTROL_PROTOCOL_ID") == protocol["id"],
                    "worker launch protection protocol differs")
    if args.mode == "worker":
        return importlib.import_module("finqa_v64_worker").run(binding.SCIENTIFIC_ROOT,
            args.seed, args.stage, args.gpu_index, attempt_root=args.attempt_root.resolve())
    resources = importlib.import_module("finqa_v64_runtime")
    return binding.source_module("finqa_v63_evaluation").worker(binding.SCIENTIFIC_ROOT,
        args.job, args.gpu, execution_context=resources.execution_context)


def exit_status(result, mode):
    if mode == "check-imports":
        return 0 if result.get("status") == "PASS" else 2
    if result.get("status") == "CONTROLLER_TRANSIENT_FAILURE":
        return 75
    return 0 if result.get("status") == "COMPLETE" else 2


def main(argv=None):
    args = _arguments(sys.argv[1:] if argv is None else argv)
    root = _validate_arguments(args)
    protocol = checked_signal_registration(root)
    observer = install_signal_observer(root, args, protocol)
    try:
        initialize_science()
        result = _dispatch(root, args)
        print(json.dumps(result if args.mode == "check-imports" else dict(
            schema=result.get("schema"), id=result.get("id"), status=result.get("status")), sort_keys=True))
        return exit_status(result, args.mode)
    finally:
        observer.close()


if __name__ == "__main__":
    raise SystemExit(main())
