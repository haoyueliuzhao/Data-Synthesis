"""Five-slot binding over byte-unchanged V43 phase admission/resource checks."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path


def _load():
    name = __name__ + "_sealed_v43_admission"
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name("finqa_v43_admission.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


original = _load()
_original_validate = original.validate_plan


def __getattr__(name):
    return getattr(original, name)


def validate_plan(plan):
    _original_validate(plan)
    original._require(
        plan.get("max_gpu_workers") == 5
        and plan.get("max_workers_per_gpu") == 1
        and plan["gpu_admission_policy"]["admission"][
            "maximum_total_workers_including_initializing_and_draining"
        ]
        == 5
        and plan["gpu_admission_policy"]["admission"]["maximum_project_workers_per_gpu"] == 1,
        "V44 requires exactly the authorized five-slot, one-worker-per-GPU envelope",
    )
    return plan


def wait_for_pre_cuda_admission(*args, **kwargs):
    readers = ("inventory", "host_memory", "process_memory", "birth")
    if any(kwargs.get(key) is None for key in readers):
        control = importlib.import_module("finqa_v44_controller")
        for key in readers:
            if kwargs.get(key) is None:
                kwargs[key] = getattr(control, key)
    previous = original.validate_plan
    original.validate_plan = validate_plan
    try:
        return original.wait_for_pre_cuda_admission(*args, **kwargs)
    finally:
        original.validate_plan = previous
