"""Signal-observed thin entry over the byte-bound frozen control02 worker.

Science and evaluation execute the original wrapper unchanged, except for its
private ``install`` reference. The CPU-only import check separately recognizes
the exact new monitoring files; it never weakens scientific byte validation.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import sys
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
SCIENCE_ROOT = REPO / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01"
FROZEN_CONTROL = SCIENCE_ROOT / "signal_recovery_02"
FROZEN_IMPLEMENTATION_ID = "280d0bb04947cf02d2c0c2c610205ab8df22ed078a50828ab7ba1227fdf0f313"
FROZEN_WORKER_SHA256 = "db164577754e3bc995bf8f58a37cc33d562c061b18e38b962fca67a45315f4b9"
MONITORING_FILES = frozenset("finqa_v58_" + name + ".py" for name in
                           ("registration", "controller", "signals", "observer", "worker"))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _load_private_worker():
    directory = FROZEN_CONTROL / "implementation"
    manifest = json.loads((directory / "record.json").read_bytes())
    source = directory / "finqa_v57_worker.py"
    require(manifest.get("id") == FROZEN_IMPLEMENTATION_ID
            and manifest["id"] == _digest({key: value for key, value in manifest.items() if key != "id"})
            and manifest["files"][source.name] == FROZEN_WORKER_SHA256
            and hashlib.sha256(source.read_bytes()).hexdigest() == FROZEN_WORKER_SHA256,
            "the registered frozen control02 worker changed")
    name = "_finqa_v58_frozen_control02_worker_private"
    if name in sys.modules:
        module = sys.modules[name]
        require(Path(module.__file__).resolve() == source
                and getattr(module, "_v58_source_sha256", None) == FROZEN_WORKER_SHA256,
                "incompatible private frozen worker already exists")
    else:
        spec = importlib.util.spec_from_file_location(name, source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        previous_path = list(sys.path)
        try:
            # The original unused signal import also resolves to its frozen
            # source. No global module aliases or import functions are patched.
            sys.path.insert(0, str(directory))
            spec.loader.exec_module(module)
        finally:
            sys.path[:] = previous_path
        module._v58_source_sha256 = FROZEN_WORKER_SHA256
    module.install = importlib.import_module("finqa_v58_signals").install
    return module


def _monitoring_file(path, directory, manifest):
    """Exclude only an exact, same-directory registered control source name."""
    path, directory = Path(path).resolve(), Path(directory).resolve()
    if path.name not in MONITORING_FILES:
        return None
    require(path.parent == directory, "monitoring module came from another source directory: " + str(path))
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if manifest is not None:
        require(manifest["files"].get(path.name) == actual,
                "monitoring module differs from the new frozen manifest: " + str(path))
    return dict(path=str(path), sha256=actual,
                source_binding="new_immutable_manifest" if manifest is not None else "prospective_workspace_bytes")


def check_worker_imports(root, *, legacy=None):
    """Original runtime -> six science imports -> two recovery imports, CPU only."""
    root = Path(root).resolve()
    require(root == SCIENCE_ROOT, "worker must retain the original V56 scientific root")
    legacy = legacy or _load_private_worker()
    implementation = legacy.configure_worker_paths(root)
    manifest = json.loads((implementation / "record.json").read_bytes())
    require(manifest.get("id") == _digest({key: value for key, value in manifest.items() if key != "id"}),
            "original scientific implementation manifest changed")
    directory = Path(__file__).resolve().parent
    new_manifest_path = directory / "record.json"
    new_manifest = json.loads(new_manifest_path.read_bytes()) if new_manifest_path.is_file() else None
    if new_manifest is not None:
        require(new_manifest.get("schema") == "v58_frozen_control_and_observation_implementation.v1"
                and new_manifest.get("id") == _digest({key: value for key, value in new_manifest.items() if key != "id"})
                and set(new_manifest["files"]) == MONITORING_FILES,
                "new monitoring implementation manifest changed")
    else:
        require(directory == Path(legacy.AUXILIARY_SCRIPTS).resolve(),
                "only prospective workspace CPU checks may precede a new frozen manifest")
    original = importlib.import_module("finqa_v56_worker")
    _, runtime = original.scientific.training_api.runtime()
    for name in (*legacy.WORKER_IMPORTS, *legacy.RECOVERY_IMPORTS):
        importlib.import_module(name)
    require(not runtime.torch.cuda.is_initialized(), "CPU import check unexpectedly initialized CUDA")
    frozen_source = Path(manifest["frozen_source_root"]).resolve()
    external = manifest["external_frozen_source_sha256"]
    verified, aliases, monitoring = [], [], []
    for name, module in sorted(sys.modules.items()):
        origin = getattr(module, "__file__", None)
        if not origin:
            continue
        path = Path(origin).resolve()
        monitor = _monitoring_file(path, directory, new_manifest)
        if monitor is not None:
            monitoring.append(dict(module=name, **monitor))
            continue
        scientific_package = name == "trusted_synthesis" or name.startswith("trusted_synthesis.")
        scientific_script = path.name.startswith("finqa_") and not path.name.startswith("finqa_v57_")
        if not scientific_package and not scientific_script:
            continue
        require(not scientific_package or path.is_relative_to(frozen_source),
                "worker imported a non-frozen scientific package: " + str(path))
        registered_path = str(path)
        if path.parent == implementation and path.name in manifest["sha256"]:
            expected = manifest["sha256"][path.name]
        elif str(path) in external:
            expected = external[str(path)]
        elif path.parent == Path(legacy.AUXILIARY_SCRIPTS).resolve():
            matches = [(source, sha) for source, sha in external.items() if Path(source).name == path.name]
            require(bool(matches) and len({sha for _, sha in matches}) == 1,
                    "auxiliary script has no original registered byte identity: " + str(path))
            registered_path, expected = matches[0]
        else:
            raise RuntimeError("worker imported an unregistered scientific dependency: " + str(path))
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        require(actual == expected, "worker dependency differs from registered bytes: " + str(path))
        row = dict(module=name, path=str(path), sha256=actual, registered_path=registered_path)
        verified.append(row)
        if registered_path != str(path):
            aliases.append(row)
    return dict(schema="v58_original_worker_cpu_import_check.v1", status="PASS",
                science_root=str(root), implementation_id=manifest["id"],
                private_worker_source_sha256=FROZEN_WORKER_SHA256, original_runtime_first=True,
                original_worker_import_order=list(legacy.WORKER_IMPORTS),
                original_recovery_import_order=list(legacy.RECOVERY_IMPORTS),
                verified_dependencies=verified, verified_dependency_count=len(verified),
                verified_dependencies_digest=_digest(verified),
                registered_byte_identical_path_aliases=aliases,
                monitoring_sources=monitoring,
                monitoring_manifest_bound=new_manifest is not None,
                CUDA_initialized=False, parent_loaded=False, model_loaded=False,
                scientific_calls=0, optimizer_updates=0)


def main():
    legacy = _load_private_worker()
    arguments = sys.argv[1:]
    if arguments[:2] != ["--mode", "check-imports"]:
        # The sole adaptation in this private instance is install. The frozen
        # mode parser, path ordering and runpy entry remain the original code.
        return legacy.main()
    directory = os.environ.get("V57_SIGNAL_LOG_DIR")
    require(bool(directory), "worker CPU check requires its independent signal log directory")
    legacy.install(directory, role="worker", context=dict(
        control_root=os.environ.get("V57_CONTROL_ROOT"), job_id=os.environ.get("V54_JOB_ID"),
        attempt_id=os.environ.get("V56_ATTEMPT_ID"), CPU_import_check=True))
    arguments = arguments[2:]
    require("--root" in arguments and arguments.index("--root") + 1 < len(arguments),
            "original V56 scientific root is required")
    result = check_worker_imports(arguments[arguments.index("--root") + 1], legacy=legacy)
    result.pop("verified_dependencies")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
