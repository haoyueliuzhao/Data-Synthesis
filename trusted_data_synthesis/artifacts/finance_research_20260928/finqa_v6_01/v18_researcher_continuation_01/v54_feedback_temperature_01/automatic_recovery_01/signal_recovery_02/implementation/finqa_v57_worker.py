"""V57 signal-observed entry for the unchanged V56 science/evaluation workers."""

import os
import sys

from finqa_v57_signals import install


AUXILIARY_SCRIPTS = "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/scripts"
WORKER_IMPORTS = (
    "finqa_v54_temperature", "finqa_v34_tail_memory", "finqa_v32_same_point_guard",
    "trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.trajectory_consumer",
    "trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.optimizer_pullback",
    "trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.distribution",
)
RECOVERY_IMPORTS = ("finqa_v56_feedback", "finqa_v56_worker")


def configure_worker_paths(root):
    """Match V56's original worker search path, not just its 96-file bundle."""
    implementation = root / "implementation"
    # In particular, same_point_guard imports the original V25 helper by its
    # ordinary module name. It lives outside the 96-file bundle. Frozen science
    # files keep precedence; runtime() subsequently selects FROZEN_SOURCE first.
    paths = [str(implementation), AUXILIARY_SCRIPTS]
    sys.path[:] = paths + [path for path in sys.path if path not in paths]
    return implementation


def check_worker_imports(root):
    """Run precisely the pre-parent-load worker import chain, on CPU only."""
    import hashlib
    import importlib
    import json
    from pathlib import Path

    implementation = configure_worker_paths(root)
    manifest_path = implementation / "record.json"
    manifest = json.loads(manifest_path.read_bytes())
    digest = lambda value: hashlib.sha256(json.dumps(value, ensure_ascii=False,
        sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    if manifest.get("id") != digest({k: v for k, v in manifest.items() if k != "id"}):
        raise RuntimeError("original scientific implementation manifest changed")
    frozen_source = Path(manifest["frozen_source_root"]).resolve()
    original = importlib.import_module("finqa_v56_worker")
    # finqa_v54_worker.run does runtime() first, then these six imports in this
    # order, then the two recovering imports. Do not call run/load_parent here.
    _, runtime = original.scientific.training_api.runtime()
    for name in (*WORKER_IMPORTS, *RECOVERY_IMPORTS):
        importlib.import_module(name)
    if runtime.torch.cuda.is_initialized():
        raise RuntimeError("CPU worker-import check unexpectedly initialized CUDA")
    external = manifest["external_frozen_source_sha256"]
    verified, aliases = [], []
    for name, module in sorted(sys.modules.items()):
        origin = getattr(module, "__file__", None)
        if not origin:
            continue
        path = Path(origin).resolve()
        scientific_package = name == "trusted_synthesis" or name.startswith("trusted_synthesis.")
        scientific_script = path.name.startswith("finqa_") and not path.name.startswith("finqa_v57_")
        if not scientific_package and not scientific_script:
            continue
        if scientific_package and not path.is_relative_to(frozen_source):
            raise RuntimeError("worker imported a non-frozen scientific package: " + str(path))
        registered_path = str(path)
        if path.parent == implementation and path.name in manifest["sha256"]:
            expected = manifest["sha256"][path.name]
        elif str(path) in external:
            expected = external[str(path)]
        elif path.parent == Path(AUXILIARY_SCRIPTS).resolve():
            matches = [(source, sha) for source, sha in external.items() if Path(source).name == path.name]
            if not matches or len({sha for _, sha in matches}) != 1:
                raise RuntimeError("auxiliary script has no original registered byte identity: " + str(path))
            registered_path, expected = matches[0]
        else:
            raise RuntimeError("worker imported an unregistered scientific dependency: " + str(path))
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError("worker dependency differs from registered bytes: " + str(path))
        row = dict(module=name, path=str(path), sha256=actual, registered_path=registered_path)
        verified.append(row)
        if registered_path != str(path):
            aliases.append(row)
    return dict(schema="v57_original_worker_cpu_import_check.v1", status="PASS",
        science_root=str(root), implementation_id=manifest["id"],
        original_runtime_first=True, original_worker_import_order=list(WORKER_IMPORTS),
        original_recovery_import_order=list(RECOVERY_IMPORTS),
        auxiliary_scripts=AUXILIARY_SCRIPTS, frozen_source_root=str(frozen_source),
        verified_dependencies=verified, verified_dependency_count=len(verified),
        verified_dependencies_digest=digest(verified),
        registered_byte_identical_path_aliases=aliases,
        CUDA_initialized=False, parent_loaded=False, model_loaded=False,
        scientific_calls=0, optimizer_updates=0)


def main():
    # Do not import argparse, the frozen worker, torch or training before this.
    directory = os.environ.get("V57_SIGNAL_LOG_DIR")
    if not directory:
        raise RuntimeError("V57 requires an independent actual-attempt signal log directory")
    install(directory, role="worker", context={
        "control_root": os.environ.get("V57_CONTROL_ROOT"),
        "job_id": os.environ.get("V54_JOB_ID"),
        "attempt_id": os.environ.get("V56_ATTEMPT_ID")})
    arguments = sys.argv[1:]
    if len(arguments) < 2 or arguments[0] != "--mode" or arguments[1] not in ("science", "evaluation", "check-imports"):
        raise RuntimeError("V57 worker requires --mode science|evaluation|check-imports then original arguments")
    mode, arguments = arguments[1], arguments[2:]
    if "--root" not in arguments or arguments.index("--root") + 1 >= len(arguments):
        raise RuntimeError("original V56 scientific root is required")
    from pathlib import Path
    import runpy

    root = Path(arguments[arguments.index("--root") + 1]).resolve()
    implementation = configure_worker_paths(root)
    if mode == "check-imports":
        import json
        result = check_worker_imports(root)
        result.pop("verified_dependencies")
        print(json.dumps(result, sort_keys=True))
        return
    entry = implementation / ("finqa_v56_worker.py" if mode == "science" else "finqa_v54_evaluation.py")
    if not entry.is_file():
        raise RuntimeError("original frozen scientific entry is missing")
    # The wrapper observes lifecycle only. Original scientific imports, payload
    # paths, probability implementation, resource gates and RNG stay frozen.
    sys.argv = [str(entry), *arguments]
    runpy.run_path(str(entry), run_name="__main__")


if __name__ == "__main__":
    main()
