"""Frozen early-generation entry: legal-stop observation before model imports."""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import re
import sys

import finqa_v65_binding as binding

MODES = ("supervise", "run", "generate", "check-imports")
SEALED_STATUS = "GENERATIONS_SEALED_AWAITING_GLOBAL_SCORING"
_OBSERVER = None


def signal_api():
    return binding.source_module("finqa_v63_signals")


def checked_signal_registration(root, *, protocol=None):
    binding.require(Path(root).resolve() == binding.ROOT.resolve(), "foreign early-generation signal root")
    protocol = binding.checked(Path(root) / "protocol/record.json") if protocol is None else protocol
    original = binding.checked(binding.SCIENTIFIC_ROOT / "protocol/record.json")
    signals = signal_api()
    binding.require(original["id"] == binding.BASE_PROTOCOL_ID
                    and protocol["scientific_protocol_id"] == original["id"]
                    and protocol["signal_policy"] == original["signal_policy"] == signals.signals_policy()
                    and protocol["signal_source_bindings"] == original["signal_source_bindings"]
                        == signals.external_source_bindings(),
                    "early generation must retain the exact authorized legal-stop signal policy")
    return protocol


def require_early_install(modules=None):
    allowed = {"finqa_v65_binding.py", "finqa_v65_entry.py", "finqa_v64_binding.py",
               "finqa_v63_binding.py", "finqa_v63_signals.py", "finqa_v59_signals.py",
               "finqa_v58_signals.py", "finqa_v58_observer.py"}
    for name, module in (sys.modules if modules is None else modules).items():
        origin = getattr(module, "__file__", None)
        if (name == "torch" or name.startswith("torch.") or name == "trusted_synthesis"
                or name.startswith("trusted_synthesis.")
                or origin and Path(origin).name.startswith("finqa_") and Path(origin).name not in allowed):
            raise RuntimeError("V65 signal observation must precede every scientific import: " + name)


def install_signal_observer(root, args, protocol):
    global _OBSERVER
    binding.require(_OBSERVER is None, "generation signal observer installs only once")
    binding.require(os.getuid() == os.geteuid() == binding.OWNER_UID,
                    "the unchanged legal-stop filter requires registered nonroot UID1004")
    require_early_install()
    if args.mode == "generate":
        directory = args.attempt_root.resolve() / "signals"
    elif args.mode == "run":
        directory = root / "controllers" / f"attempt{args.controller_attempt:04d}" / "signals"
    elif args.mode == "supervise":
        directory = root / "supervisor/signals"
    else:
        directory = root / "frozen_worker_import_verification/signals"
    binding.require(directory.is_relative_to(root), "signal evidence escaped independent generation root")
    _OBSERVER = signal_api()._reference().install(directory, role=args.mode, context=dict(
        mode=args.mode, control_root=str(root), control_protocol_id=protocol["id"],
        scientific_root=str(binding.SCIENTIFIC_ROOT), scientific_protocol_id=binding.BASE_PROTOCOL_ID,
        job_id=os.environ.get("V54_JOB_ID"), attempt_id=os.environ.get("V63_ATTEMPT_ID"),
        inherited_signal_policy_unchanged=True, CPU_import_check=args.mode == "check-imports"))
    return _OBSERVER


def initialize_science():
    binding.source_module("finqa_v63_binding").install_scientific_paths()
    original = binding.source_module("finqa_v63_entry")
    original.install_registered_auxiliary()
    return original


def verify_imported_modules(root, implementation, *, modules=None):
    root = Path(root).resolve()
    binding.require(root == binding.ROOT.resolve(), "foreign early-generation dependency root")
    source_modules, additions = {}, []
    for name, module in sorted((sys.modules if modules is None else modules).items()):
        origin = getattr(module, "__file__", None)
        if not origin:
            continue
        path = Path(origin).resolve()
        if path.name.startswith("finqa_v65_") or name.startswith("finqa_v65_"):
            binding.require(path.parent == root / "implementation" and path.name in implementation["sha256"],
                            "unregistered or workspace early-generation module: " + str(path))
            actual = binding.sha(path)
            binding.require(actual == implementation["sha256"][path.name],
                            "frozen early-generation source bytes changed")
            additions.append(dict(module=name, path=str(path), sha256=actual,
                                  origin="new_frozen_generation_only_operational_bundle"))
        else:
            source_modules[name] = module
    predecessor = binding.predecessor_module("finqa_v64_entry")
    parent_root = Path(predecessor.__file__).resolve().parent.parent
    parent_implementation = binding.checked(parent_root / "implementation/record.json")
    original = predecessor.verify_imported_modules(parent_root, parent_implementation, modules=source_modules)
    verified = original["verified_dependencies"] + additions
    return dict(original, verified_dependencies=verified, verified_dependency_count=len(verified),
        verified_dependencies_digest=binding.digest(verified), early_generation_sources=additions,
        original_scientific_protocol_id=binding.BASE_PROTOCOL_ID,
        new_operational_protocol_does_not_replace_scientific_identity=True,
        private_lifecycle_adapters_explicitly_bound_by_new_frozen_source=True)


def check_imports(root):
    root = Path(root).resolve()
    original = initialize_science()
    registration = importlib.import_module("finqa_v65_registration")
    protocol = registration.checked_protocol(root)
    checked_signal_registration(root, protocol=protocol)
    implementation = registration.checked_implementation(root)
    training = binding.source_module("finqa_v63_training")
    _, runtime = training.runtime()
    for name in (*original.WORKER_IMPORTS, *original.RECOVERY_IMPORTS, *original.NEW_IMPORTS):
        importlib.import_module(name)
    for name in ("finqa_v65_runtime", "finqa_v65_evaluation", "finqa_v65_worker", "finqa_v65_controller"):
        importlib.import_module(name)
    binding.require(not runtime.torch.cuda.is_initialized(), "CPU generation dependency check cannot initialize CUDA")
    resources = importlib.import_module("finqa_v65_runtime")
    controller = importlib.import_module("finqa_v65_controller")
    binding.require(controller.MAX_WORKERS == 5 and controller.OTHER_CONTROL_STARTUP_GIB == 64,
                    "generation CPU preflight must retain its partition and cross-control RAM reservation")
    dependencies = verify_imported_modules(root, implementation)
    body = dict(schema="v65_actual_frozen_generation_CPU_import_check.v1", status="PASS",
        protocol_id=protocol["id"], control_protocol_id=protocol["id"],
        scientific_protocol_id=binding.BASE_PROTOCOL_ID,
        implementation_id=implementation["id"], scientific_root=str(binding.SCIENTIFIC_ROOT),
        control_root=str(root), CUDA_initialized=False, parent_loaded=False, model_loaded=False,
        scientific_calls=0, optimizer_updates=0, scoring_calls=0,
        installed_resource_guard=dict(module=resources.ResourceGuard.__module__, qualname=resources.ResourceGuard.__qualname__),
        standalone_machine_wide_observer_started=False, **dependencies)
    return dict(body, id=binding.digest(body))


def _arguments(argv):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=MODES)
    parser.add_argument("--root", type=Path, default=binding.ROOT)
    parser.add_argument("--controller-attempt", type=int, default=1)
    parser.add_argument("--job")
    parser.add_argument("--gpu", type=int)
    parser.add_argument("--attempt-root", type=Path)
    return parser.parse_args(argv)


def _validate_arguments(args):
    root = args.root.resolve()
    binding.require(root == binding.ROOT.resolve(), "entry requires its independent registered generation root")
    binding.require(Path(__file__).resolve().parent == root / "implementation",
                    "generation entry must execute from its frozen implementation")
    binding.require(type(args.controller_attempt) is int and args.controller_attempt >= 1,
                    "positive independent controller attempt required")
    if args.mode == "generate":
        binding.require(isinstance(args.job, str) and args.job and "/" not in args.job and "\\" not in args.job
                        and args.gpu in range(8) and args.attempt_root is not None,
                        "registered generation job, GPU and attempt required")
        attempt = args.attempt_root.resolve()
        binding.require(not args.attempt_root.is_symlink()
                        and attempt.parent == root / "evaluations/jobs" / args.job / "attempts"
                        and re.fullmatch(r"attempt[0-9]{4,}", attempt.name) is not None,
                        "generation attempt escaped its independent job")
        binding.require(os.environ.get("V63_ATTEMPT_DIR") == os.environ.get("V56_ATTEMPT_DIR") == str(attempt)
                        and os.environ.get("V63_ATTEMPT_ID") == os.environ.get("V56_ATTEMPT_ID") == attempt.name
                        and os.environ.get("V65_CONTROL_ROOT") == str(root)
                        and os.environ.get("V54_JOB_ID") == args.job,
                        "generation attempt aliases or control root differ")
    return root


def _dispatch(root, args):
    if args.mode == "check-imports":
        return check_imports(root)
    registration = importlib.import_module("finqa_v65_registration")
    protocol = registration.checked_protocol(root)
    registration.checked_implementation(root)
    if args.mode in ("supervise", "run"):
        controller = importlib.import_module("finqa_v65_controller")
        return controller.supervise(root) if args.mode == "supervise" else controller.Controller(
            root, controller_attempt=args.controller_attempt).run()
    binding.require(os.environ.get("V65_CONTROL_PROTOCOL_ID") == protocol["id"],
                    "generation worker launch control protocol differs")
    resources = importlib.import_module("finqa_v65_runtime")
    return importlib.import_module("finqa_v65_evaluation").worker(
        root, args.job, args.gpu, execution_context=resources.execution_context)


def exit_status(result, mode):
    if mode == "check-imports":
        return 0 if result.get("status") == "PASS" else 2
    if result.get("status") == "CONTROLLER_TRANSIENT_FAILURE":
        return 75
    if mode == "generate":
        return 0 if result.get("status") == "COMPLETE" else 2
    return 0 if result.get("status") == SEALED_STATUS else 2


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
