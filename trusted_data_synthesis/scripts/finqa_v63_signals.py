"""V63's private reuse of the already authorized, byte-frozen signal filter.

No observer or threads are started on import.  Only this process's original
V59 SignalObserver is installed; no machine-wide observer is launched.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

import finqa_v63_binding as binding

CONTROL04 = binding.OLD_ROOT / "signal_recovery_04/implementation"
CONTROL03 = binding.OLD_ROOT / "signal_recovery_03/implementation"
CONTROL04_ID = "21ed26b65a2aa3d7fddc93a970a7f1af5f3ac3683fd30972bd824cbed7eacd4d"
CONTROL03_ID = "63525be8d361117a8dd0ee2f10265d9fa97e675da969e622580fadece8060e6f"
SIGNAL59_SHA = "679dc618490f4645a25dc0ca0d89d353f295861bcd32dd6226b886ea6d58d4d1"
SIGNAL58_SHA = "3c9cdc1133003fa8cd1c2a3324c0443bc471b3695fae73965b4a159376eb2230"
OBSERVER58_SHA = "1431a463064cf5c0aa0e86a455ae0cf3d9f662ff7142cd953807604406fbc55b"
OWNER_UID = 1004
_REFERENCE = None
_OBSERVER = None


def external_source_bindings():
    manifest04 = binding.checked(CONTROL04 / "record.json")
    manifest03 = binding.checked(CONTROL03 / "record.json")
    binding.require(manifest04["id"] == CONTROL04_ID and manifest03["id"] == CONTROL03_ID,
                    "registered historical signal implementation identity changed")
    refs = dict(control04_manifest=binding.entry(CONTROL04 / "record.json"),
                control03_manifest=binding.entry(CONTROL03 / "record.json"))
    for key, directory, name, expected, manifest in (
        ("v59_signals", CONTROL04, "finqa_v59_signals.py", SIGNAL59_SHA, manifest04),
        ("v58_signals", CONTROL03, "finqa_v58_signals.py", SIGNAL58_SHA, manifest03),
        ("v58_observer", CONTROL03, "finqa_v58_observer.py", OBSERVER58_SHA, manifest03),
    ):
        reference = binding.file_ref(directory / name)
        binding.require(manifest["files"].get(name) == expected and reference["sha256"] == expected,
                        "registered signal source bytes changed: " + name)
        refs[key] = reference
    return refs


def _reference():
    global _REFERENCE
    if _REFERENCE is None:
        refs = external_source_bindings()
        path = Path(refs["v59_signals"]["path"])
        name = "_v63_frozen59_signals_private"
        binding.require(name not in sys.modules, "V63 private signal namespace already occupied")
        spec = importlib.util.spec_from_file_location(name, path)
        binding.require(spec is not None and spec.loader is not None, "frozen signal loader unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
            binding.require(module.OWNER_UID == OWNER_UID
                            and Path(module.SOURCE_ROOT).resolve() == CONTROL03.resolve()
                            and module.SOURCE_IMPLEMENTATION_ID == CONTROL03_ID
                            and module.SOURCE_SIGNAL_SHA256 == SIGNAL58_SHA
                            and module.SOURCE_OBSERVER_SHA256 == OBSERVER58_SHA,
                            "inherited signal source chain differs from the exact registered chain")
        except BaseException:
            sys.modules.pop(name, None)
            raise
        _REFERENCE = module
    return _REFERENCE


def signals_policy():
    return dict(_reference().signals_policy(),
        schema="v63_inherited_owner_uid_scoped_sigterm_filter.v1",
        inherited_filter_implementation_id=CONTROL04_ID,
        inherited_filter_source_sha256=SIGNAL59_SHA,
        observer_installed_before_scientific_imports=True,
        new_root_only=True, no_machine_wide_observer_started=True,
        historical_sources_modified=False)


def signal_decision(number, sender_pid, sender_uid, si_code, *, owner_uid=OWNER_UID):
    return _reference().signal_decision(number, sender_pid, sender_uid, si_code, owner_uid=owner_uid)


def require_early_install(modules=None):
    allowed = {"finqa_v63_binding.py", "finqa_v63_entry.py", "finqa_v63_signals.py",
               "finqa_v59_signals.py", "finqa_v58_signals.py", "finqa_v58_observer.py"}
    for name, module in (sys.modules if modules is None else modules).items():
        origin = getattr(module, "__file__", None)
        if (name == "torch" or name.startswith("torch.")
                or name == "trusted_synthesis" or name.startswith("trusted_synthesis.")
                or origin and Path(origin).name.startswith("finqa_") and Path(origin).name not in allowed):
            raise RuntimeError("V63 signal observer must precede scientific imports: " + name)


def install(log_directory, *, role, context=None):
    global _OBSERVER
    directory = Path(log_directory).resolve()
    binding.require(directory.is_relative_to(binding.ROOT.resolve()),
                    "V63 signal logs must remain inside the new experiment root")
    binding.require(_OBSERVER is None, "V63 signal observer is installed once per process")
    binding.require(os.getuid() == os.geteuid() == OWNER_UID,
                    "V63 signal filter requires the registered real/effective nonroot UID1004")
    require_early_install()
    reference = _reference()
    _OBSERVER = reference.install(directory, role=role,
        context=dict(context or {}, v63_root=str(binding.ROOT.resolve()),
                     inherited_filter_implementation_id=CONTROL04_ID))
    return _OBSERVER
