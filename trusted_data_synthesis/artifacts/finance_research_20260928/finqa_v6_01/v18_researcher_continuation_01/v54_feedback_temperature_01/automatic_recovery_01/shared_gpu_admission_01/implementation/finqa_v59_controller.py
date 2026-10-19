"""Control04 recovery with the separately authorized narrow TERM filter.

Only a private control02 module's root, registration lookup and two executable
arguments are redirected. New wrappers retain frozen control03 science; the
registered signal policy preserves owner TERM, all INT and explicit STOP.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
SCIENTIFIC_ROOT = REPO / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01"
ROOT = SCIENTIFIC_ROOT / "signal_recovery_04"
FROZEN_CONTROL = SCIENTIFIC_ROOT / "signal_recovery_02"
REUSED_CONTROL = SCIENTIFIC_ROOT / "signal_recovery_03"
FROZEN_IMPLEMENTATION_ID = "280d0bb04947cf02d2c0c2c610205ab8df22ed078a50828ab7ba1227fdf0f313"
FROZEN_CONTROLLER_SHA256 = "6236043316b750bd7b49e31906fea91bf87abca50fff060c3c97afc84d51a214"
REUSED_IMPLEMENTATION_ID = "63525be8d361117a8dd0ee2f10265d9fa97e675da969e622580fadece8060e6f"
REUSED_FILE_SHA256 = {
    "finqa_v58_worker.py": "a398eaa063d15939a99e1b4f838df722bd4843f32c02002da129a40ea1e14434",
    "finqa_v58_signals.py": "3c9cdc1133003fa8cd1c2a3324c0443bc471b3695fae73965b4a159376eb2230",
    "finqa_v58_observer.py": "1431a463064cf5c0aa0e86a455ae0cf3d9f662ff7142cd953807604406fbc55b",
}
PYTHON = REPO / "trusted_data_synthesis/.venv/bin/python"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def checked_reused_bundle():
    directory = REUSED_CONTROL / "implementation"
    manifest = json.loads((directory / "record.json").read_bytes())
    require(manifest.get("id") == REUSED_IMPLEMENTATION_ID
            and manifest["id"] == _digest({key: value for key, value in manifest.items() if key != "id"}),
            "registered control03 implementation manifest changed")
    for name, expected in REUSED_FILE_SHA256.items():
        require(manifest["files"][name] == expected
                and hashlib.sha256((directory / name).read_bytes()).hexdigest() == expected,
                "reused frozen control03 entry changed: " + name)
    return directory


def _arguments(*, early=False):
    parser = argparse.ArgumentParser(description=__doc__, add_help=not early)
    parser.add_argument("action", choices=("run", "supervise", "check-imports"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--controller-attempt", type=int, default=1)
    return parser.parse_known_args()[0] if early else parser.parse_args()


if __name__ == "__main__":
    early_args = _arguments(early=True)
    from finqa_v59_signals import install
    # Install the new independently registered policy before science imports.
    install(
        early_args.root / "signals" / f"{early_args.action}-{os.getpid()}",
        role="supervisor" if early_args.action == "supervise" else "controller",
        context=dict(control_root=str(early_args.root),
                     controller_attempt=early_args.controller_attempt,
                     reused_monitoring_root=str(REUSED_CONTROL)))


def adapter_contract():
    return dict(schema="v59_private_frozen_control_adapter.v1",
        source_implementation_record=str(FROZEN_CONTROL / "implementation/record.json"),
        source_implementation_id=FROZEN_IMPLEMENTATION_ID,
        source_controller_sha256=FROZEN_CONTROLLER_SHA256,
        independent_control_root=str(ROOT), unchanged_scientific_root=str(SCIENTIFIC_ROOT),
        reused_implementation_record=str(REUSED_CONTROL / "implementation/record.json"),
        reused_implementation_id=REUSED_IMPLEMENTATION_ID,
        reused_entry_sha256=REUSED_FILE_SHA256,
        registration_redirect={"finqa_v57_registration": "finqa_v59_registration"},
        executable_redirect={
            str(ROOT / "implementation/finqa_v57_controller.py"): str(ROOT / "implementation/finqa_v59_controller.py"),
            str(ROOT / "implementation/finqa_v57_worker.py"): str(ROOT / "implementation/finqa_v59_worker.py")},
        actual_argv_mutated_before_Popen_and_launch_record=True,
        original_worker_auxiliary_import_path_preserved=True,
        signal_policy_wrapper_separately_registered=True,
        controller_inventory_isolation_installed_before_original_constructor=True,
        scientific_math_implementation_unchanged=True,
        global_importlib_subprocess_and_public_module_aliases_unchanged=True,
        frozen_bytes_mathematics_resources_and_owner_stop_rules_unchanged=True)


class _ImportRouter:
    def __init__(self, delegate):
        self.delegate = delegate

    def import_module(self, name, package=None):
        actual = "finqa_v59_registration" if name == "finqa_v57_registration" else name
        return self.delegate.import_module(actual, package)

    def __getattr__(self, name):
        return getattr(self.delegate, name)


class _ProcessRouter:
    def __init__(self, delegate, control_root=ROOT):
        self.delegate = delegate
        directory = Path(control_root) / "implementation"
        self.redirect = {
            str(directory / "finqa_v57_controller.py"): str(directory / "finqa_v59_controller.py"),
            str(directory / "finqa_v57_worker.py"): str(directory / "finqa_v59_worker.py")}

    def Popen(self, command, *args, **kwargs):
        if isinstance(command, (list, tuple)):
            matches = [index for index, value in enumerate(command)
                       if isinstance(value, str) and value in self.redirect]
            if matches:
                require(isinstance(command, list) and len(matches) == 1,
                        "one mutable original argv is required for an exact control entrypoint redirect")
                index = matches[0]
                require(index >= 2 and command[index - 2:index] == [str(PYTHON), "-u"],
                        "control redirect must be the original Python executable argument")
                command[index] = self.redirect[command[index]]
        return self.delegate.Popen(command, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.delegate, name)


def _load_private_controller():
    directory = FROZEN_CONTROL / "implementation"
    manifest = json.loads((directory / "record.json").read_bytes())
    source = directory / "finqa_v57_controller.py"
    require(manifest["id"] == FROZEN_IMPLEMENTATION_ID
            and manifest["id"] == _digest({key: value for key, value in manifest.items() if key != "id"})
            and manifest["files"][source.name] == FROZEN_CONTROLLER_SHA256
            and hashlib.sha256(source.read_bytes()).hexdigest() == FROZEN_CONTROLLER_SHA256,
            "registered frozen control02 implementation changed")
    checked_reused_bundle()
    name = "_finqa_v59_frozen_control02_private"
    if name in sys.modules:
        existing = sys.modules[name]
        require(Path(existing.__file__).resolve() == source
                and getattr(existing, "_v59_adapter_contract", None) == adapter_contract()
                and existing.ROOT == ROOT and existing.SCIENTIFIC_ROOT == SCIENTIFIC_ROOT,
                "an incompatible private control adapter already exists")
        return existing
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    require(module.ROOT == FROZEN_CONTROL and module.SCIENTIFIC_ROOT == SCIENTIFIC_ROOT,
            "frozen controller roots differ from the registered source")
    module.ROOT = ROOT
    module.importlib = _ImportRouter(importlib)
    module.subprocess = _ProcessRouter(subprocess)
    module._v59_adapter_contract = adapter_contract()
    return module


frozen = _load_private_controller()
evaluation = frozen.evaluation
TEMPORARY_CONTROLLER_EXIT = frozen.TEMPORARY_CONTROLLER_EXIT

if __name__ == "__main__":
    require(Path(frozen.inherited.__file__).resolve() == SCIENTIFIC_ROOT / "implementation/finqa_v56_controller.py",
            "V59 must inherit the original frozen V56 science controller")


class Controller(frozen.Controller):
    def __init__(self, root=ROOT, *, controller_attempt=1, runtime=None,
                 registration=None, scientific_registration=None):
        registration = registration or importlib.import_module("finqa_v59_registration")
        original_runtime = runtime or importlib.import_module("finqa_v54_runtime")
        isolation = importlib.import_module("finqa_v59_gpu_isolation")
        runtime = isolation.install_controller_runtime(original_runtime)
        require(runtime is not None, "registered GPU isolation must supply a controller runtime proxy")
        super().__init__(root, controller_attempt=controller_attempt, runtime=runtime,
                         registration=registration, scientific_registration=scientific_registration)


def supervise(root=ROOT):
    return frozen.supervise(root)


def main():
    args = _arguments()
    result = (frozen.check_imports() if args.action == "check-imports" else
              supervise(args.root) if args.action == "supervise" else
              Controller(args.root, controller_attempt=args.controller_attempt).run())
    print(json.dumps(dict(status=result["status"], id=result["id"]), sort_keys=True))
    if result["status"] == "CONTROLLER_TRANSIENT_FAILURE":
        return TEMPORARY_CONTROLLER_EXIT
    return 0 if result["status"] in ("COMPLETE", "CPU_IMPORTS_VERIFIED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
