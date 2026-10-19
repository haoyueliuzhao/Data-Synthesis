"""Private frozen-science worker with the independent V62 shared-GPU guard."""
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import finqa_v59_signals as signals

SCIENCE_ROOT = signals.SOURCE_ROOT.parent.parent
CONTROL_ROOT = SCIENCE_ROOT/"shared_gpu_admission_01"
FROZEN_ROOT = signals.SOURCE_ROOT
FROZEN_WORKER_SHA256 = "a398eaa063d15939a99e1b4f838df722bd4843f32c02002da129a40ea1e14434"
MONITORING_FILES = frozenset("finqa_v59_"+name+".py" for name in
                           ("registration", "controller", "signals", "observer", "worker", "gpu_isolation")) | frozenset(
    "finqa_v62_"+name+".py" for name in ("registration", "backend", "watchdog", "binding", "controller",
        "observer", "cron", "handoff", "worker", "gpu_isolation", "supersession"))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class _Imports:
    def import_module(self, name, package=None):
        if name == "finqa_v58_signals":
            return SimpleNamespace(install=install_worker_runtime)
        return importlib.import_module(name, package)

    def __getattr__(self, name):
        return getattr(importlib, name)


def _load_private_worker():
    require(Path(signals.__file__).resolve() == Path(__file__).resolve().with_name("finqa_v59_signals.py"),
            "V62 worker signal installer must be its adjacent registered V59 source")
    manifest = json.loads((FROZEN_ROOT/"record.json").read_bytes())
    source = FROZEN_ROOT/"finqa_v58_worker.py"
    require(manifest.get("id") == signals.SOURCE_IMPLEMENTATION_ID
            and manifest["id"] == _digest({k: v for k, v in manifest.items() if k != "id"})
            and manifest["files"].get(source.name) == FROZEN_WORKER_SHA256
            and hashlib.sha256(source.read_bytes()).hexdigest() == FROZEN_WORKER_SHA256,
            "registered control03 worker changed")
    name = "_v62_frozen03_worker_private"
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(name, source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    else:
        require(Path(module.__file__).resolve() == source, "private worker source mismatch")
    # The frozen V58 wrapper's own private-loader then binds install on the
    # frozen control02 worker. No public import function or source is mutated.
    module.importlib = _Imports()
    return module


def _gpu_isolation():
    source = Path(__file__).resolve().with_name("finqa_v62_gpu_isolation.py")
    name = "_v62_worker_bound_gpu_isolation"
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(name, source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    else:
        require(Path(module.__file__).resolve() == source, "GPU isolation helper source mismatch")
    return module


def install_worker_runtime(directory, *, role, context=None, cpu_check=False):
    # Signal mask/receiver must precede all worker imports and threads. The
    # original scientific path order then binds the original runtime objects;
    # the adjacent isolation helper installs resource-only hooks before CUDA.
    observer = signals.install(directory, role=role, context=context)
    _load_private_worker()._load_private_worker().configure_worker_paths(SCIENCE_ROOT)
    _gpu_isolation().install_worker_guard(cpu_check=cpu_check)
    return observer


def _monitoring_path(path, directory, manifest, old_manifest):
    path = Path(path).resolve()
    if path.name in MONITORING_FILES:
        require(path.parent == directory, "V62 monitoring source escaped its registered directory")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if manifest is not None:
            require(manifest["files"].get(path.name) == actual, "V62 monitoring source bytes changed")
        return dict(path=str(path), sha256=actual, origin="V62_master" if manifest else "prospective_workspace")
    if path.name in old_manifest["files"]:
        require(path.parent == FROZEN_ROOT, "V58 inherited monitoring source is not frozen control03")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        require(old_manifest["files"][path.name] == actual, "V58 inherited monitoring bytes changed")
        return dict(path=str(path), sha256=actual, origin="frozen_control03")
    return None


def check_worker_imports(root, *, legacy=None):
    """CPU diagnosis only: retain the original runtime and six+two imports."""
    root = Path(root).resolve()
    require(root == SCIENCE_ROOT, "original V56 science root required")
    inherited = legacy or _load_private_worker()
    original_wrapper = inherited._load_private_worker()
    implementation = original_wrapper.configure_worker_paths(root)
    science = json.loads((implementation/"record.json").read_bytes())
    require(science.get("id") == _digest({k: v for k, v in science.items() if k != "id"}),
            "original science implementation identity changed")
    directory = Path(__file__).resolve().parent
    manifest_path = directory/"record.json"
    manifest = json.loads(manifest_path.read_bytes()) if manifest_path.is_file() else None
    if manifest is not None:
        require(directory == CONTROL_ROOT/"implementation"
                and manifest.get("id") == _digest({k: v for k, v in manifest.items() if k != "id"})
                and set(manifest["files"]) == MONITORING_FILES, "V62 implementation binding changed")
    else:
        require(directory == Path(original_wrapper.AUXILIARY_SCRIPTS).resolve(),
                "only the prospective workspace may run an unfrozen CPU diagnostic")
    old_manifest = json.loads((FROZEN_ROOT/"record.json").read_bytes())
    original = importlib.import_module("finqa_v56_worker")
    _, runtime = original.scientific.training_api.runtime()
    for name in (*original_wrapper.WORKER_IMPORTS, *original_wrapper.RECOVERY_IMPORTS):
        importlib.import_module(name)
    require(not runtime.torch.cuda.is_initialized(), "CPU check initialized CUDA")
    installed_guard = importlib.import_module("finqa_v56_runtime").ResourceGuard
    isolation_helper = _gpu_isolation()
    require(installed_guard.__module__ == isolation_helper.__name__,
            "registered GPU isolation ResourceGuard is not actually installed")
    frozen_source = Path(science["frozen_source_root"]).resolve()
    external = science["external_frozen_source_sha256"]
    verified, aliases, monitoring = [], [], []
    for name, module in sorted(sys.modules.items()):
        origin = getattr(module, "__file__", None)
        if not origin:
            continue
        path = Path(origin).resolve()
        monitor = _monitoring_path(path, directory, manifest, old_manifest)
        if monitor is not None:
            monitoring.append(dict(module=name, **monitor))
            continue
        package = name == "trusted_synthesis" or name.startswith("trusted_synthesis.")
        script = path.name.startswith("finqa_") and not path.name.startswith("finqa_v57_")
        if not package and not script:
            continue
        require(not package or path.is_relative_to(frozen_source), "non-frozen science package imported")
        registered_path = str(path)
        if path.parent == implementation and path.name in science["sha256"]:
            expected = science["sha256"][path.name]
        elif str(path) in external:
            expected = external[str(path)]
        elif path.parent == Path(original_wrapper.AUXILIARY_SCRIPTS).resolve():
            matches = [(p, sha) for p, sha in external.items() if Path(p).name == path.name]
            require(bool(matches) and len({sha for _, sha in matches}) == 1, "unregistered auxiliary script")
            registered_path, expected = matches[0]
        else:
            raise RuntimeError("unregistered scientific dependency: "+str(path))
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        require(actual == expected, "scientific dependency bytes changed: "+str(path))
        item = dict(module=name, path=str(path), sha256=actual, registered_path=registered_path)
        verified.append(item)
        if registered_path != str(path):
            aliases.append(item)
    return dict(schema="v62_original_worker_cpu_import_check.v1", status="PASS",
        science_root=str(root), implementation_id=science["id"],
        inherited_worker_sha256=FROZEN_WORKER_SHA256, original_runtime_first=True,
        original_worker_import_order=list(original_wrapper.WORKER_IMPORTS),
        original_recovery_import_order=list(original_wrapper.RECOVERY_IMPORTS),
        verified_dependency_count=len(verified), verified_dependencies_digest=_digest(verified),
        registered_byte_identical_path_aliases=aliases, monitoring_sources=monitoring,
        monitoring_manifest_bound=manifest is not None, CUDA_initialized=False,
        installed_resource_guard=dict(module=installed_guard.__module__,
            qualname=installed_guard.__qualname__, isolation_helper_path=str(Path(isolation_helper.__file__).resolve()),
            isolation_helper_module_match=True),
        parent_loaded=False, model_loaded=False, scientific_calls=0, optimizer_updates=0)


def main():
    legacy = _load_private_worker()
    if sys.argv[1:3] != ["--mode", "check-imports"]:
        return legacy.main()
    directory = os.environ.get("V57_SIGNAL_LOG_DIR")
    require(bool(directory), "independent signal directory required")
    install_worker_runtime(directory, role="worker", context=dict(control_root=os.environ.get("V57_CONTROL_ROOT"),
        job_id=os.environ.get("V54_JOB_ID"), attempt_id=os.environ.get("V56_ATTEMPT_ID"), CPU_import_check=True), cpu_check=True)
    arguments = sys.argv[3:]
    require("--root" in arguments and arguments.index("--root")+1 < len(arguments), "science root required")
    print(json.dumps(check_worker_imports(arguments[arguments.index("--root")+1], legacy=legacy), sort_keys=True))


if __name__ == "__main__":
    main()
