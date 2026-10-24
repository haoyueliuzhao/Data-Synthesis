"""Private root-only reuse of the registered UID-scoped V59 signal filter."""
from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType

import finqa_v71_binding as binding


def _load():
    directory = binding.SOURCE_ROOT / "implementation"
    manifest = binding.checked(directory / "record.json")
    path = directory / "finqa_v63_signals.py"
    binding.require(manifest["id"] == binding.BASE_IMPLEMENTATION_ID
                    and binding.sha(path) == manifest["sha256"][path.name],
                    "frozen signal adapter source changed")
    raw = path.read_text()
    before = "import finqa_v63_binding as binding"
    binding.require(raw.count(before) == 1, "signal adapter import structure changed")
    raw = raw.replace(before, "import finqa_v71_binding as binding")
    raw = raw.replace('"finqa_v63_binding.py", "finqa_v63_entry.py", "finqa_v63_signals.py",',
        '"finqa_v63_binding.py", "finqa_v63_entry.py", "finqa_v63_signals.py", '
        '"finqa_v71_binding.py", "finqa_v71_entry.py", "finqa_v71_signals.py",')
    raw = raw.replace("_v63_frozen59_signals_private", "_v71_frozen59_signals_private")
    module = ModuleType("_v71_frozen_signal_adapter")
    module.__file__, module.__package__ = str(path), ""
    sys.modules[module.__name__] = module
    exec(compile(raw, str(path) + "::V71_root_only_signal_adapter", "exec"), module.__dict__)
    return module


_original = _load()
external_source_bindings = _original.external_source_bindings
signals_policy = _original.signals_policy
signal_decision = _original.signal_decision
require_early_install = _original.require_early_install
install = _original.install
