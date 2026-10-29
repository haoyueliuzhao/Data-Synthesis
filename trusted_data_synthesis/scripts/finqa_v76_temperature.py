"""Private V63 probability/replay implementation bound to new V76 artifacts.

Only the independent output root and probability-contract names are replaced.
T1, 350 x two draws, durable returns, unknown-call stop semantics, original R3
arithmetic and strict atomic draw diagnostics remain the frozen implementation.
The probability label C1 means T1; the optimization arm is separately Full.
"""
from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import finqa_v76_binding as binding

reference = binding.source_module("finqa_v63_temperature")
_shim = SimpleNamespace(**{name: getattr(reference.binding, name)
                         for name in dir(reference.binding) if not name.startswith("__")})
_shim.ROOT = binding.ROOT
_shim.install_scientific_paths = binding.install_scientific_paths
_shim.ARMS, _shim.TEMPERATURES = ("C1",), {"C1": 1.0}
_shim.require = binding.require


def _adapt():
    source = Path(reference.__file__).read_text()
    replacements = (
        ("import finqa_v63_binding as binding", "binding = _v76_binding", 1),
        ('BACKEND_VERSION = "v63_balanced_b1_exact_temperature_r3.v1"',
         'BACKEND_VERSION = "v76_T1_Full_exact_temperature_r3.v1"', 1),
        ('"schema": "v63_balanced_b1_feedback_probability.v1"',
         '"schema": "v76_T1_Full_feedback_probability.v1"', 1),
        ('schema="v63_pre_generation_balanced_feedback_condition.v1"',
         'schema="v76_fresh_continuous_feedback_condition.v1"', 1),
        ('schema="v63_condition_actual_cohort_binding.v1"',
         'schema="v76_condition_actual_cohort_binding.v1"', 1),
    )
    for before, after, count in replacements:
        binding.require(source.count(before) == count, "frozen V63 probability adapter changed")
        source = source.replace(before, after)
    module = ModuleType("_v76_frozen_T1_probability")
    module.__file__ = __file__
    module.__package__ = ""
    module._v76_binding = _shim
    sys.modules[module.__name__] = module
    exec(compile(source, reference.__file__ + "::V76_new_root", "exec"), module.__dict__)
    return module


_implementation = _adapt()


def __getattr__(name):
    return getattr(_implementation, name)
