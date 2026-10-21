"""Private V63 worker adapter: identical science, explicit V64 resource guard."""
from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType

import finqa_v64_binding as binding
import finqa_v64_runtime as runtime


def _private_worker():
    original = binding.source_module("finqa_v63_worker")
    source = Path(original.__file__).read_text()
    before = "import finqa_v63_runtime as resources"
    binding.require(source.count(before) == 1,
                    "original worker resource import structure changed")
    source = source.replace(before, "import finqa_v64_runtime as resources")
    module = ModuleType("_v64_private_scientific_worker")
    module.__file__ = str(Path(original.__file__).resolve())
    module.__package__ = ""
    sys.modules[module.__name__] = module
    exec(compile(source, module.__file__ + "::V64_private_worker", "exec"), module.__dict__)
    module.ScientificMonitor = runtime.ScientificMonitor
    return module


_worker = _private_worker()


def run(root, seed, stage, gpu_index, *, attempt_root=None):
    return _worker.run(root, seed, stage, gpu_index, attempt_root=attempt_root)


def audit_job_resume(*args, **kwargs):
    return _worker.audit_job_resume(*args, **kwargs)


def classify_attempt(*args, **kwargs):
    return _worker.classify_attempt(*args, **kwargs)


def __getattr__(name):
    return getattr(_worker, name)
