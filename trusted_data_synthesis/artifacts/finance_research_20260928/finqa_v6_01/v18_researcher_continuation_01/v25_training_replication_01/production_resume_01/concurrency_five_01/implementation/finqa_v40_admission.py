"""Explicitly broadened V40 device policy over the unchanged CPU wait machine.

The heartbeat schema remains v39_pre_cuda_admission.v1 because that state
machine is unchanged; each heartbeat still binds the actual V40 protocol ID.
No fallback import may select an old controller or modify the device scope.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

# Load an isolated copy: the actual historical V39 module and its five-device
# validator must not gain any authority from the user's new V40 permission.
_name = __name__ + "_unchanged_wait_machine"
_spec = importlib.util.spec_from_file_location(
    _name, Path(__file__).with_name("finqa_v39_admission.py")
)
original = importlib.util.module_from_spec(_spec)
sys.modules[_name] = original
_spec.loader.exec_module(original)

ALLOWED_GPUS = tuple(range(8))
DISPATCH_ORDER = (3, 4, 5, 7, 0, 1, 2, 6)
GPU_UUIDS = {
    "0": "GPU-f813ce38-39d7-ab21-f72b-55f87284eaa5",
    "1": "GPU-0a62363e-fb3c-74fd-c5fe-1a2720c7e66a",
    "2": "GPU-88a33540-ff55-746e-d82b-45821b463102",
    "3": "GPU-004a2d75-6298-df4d-7b95-103bc6c1b02a",
    "4": "GPU-ae8978c8-5100-933e-78d1-46ed781a8a0e",
    "5": "GPU-f731a280-01e3-2359-ace9-aa2ad2112f55",
    "6": "GPU-6cf85ebf-ae89-905b-5d97-46f83b295526",
    "7": "GPU-ab6e97cc-19e4-64b8-f792-7b6920a45434",
}
CPU_AFFINITY = {str(gpu): "0-37,76-113" if gpu < 4 else "38-75,114-151" for gpu in ALLOWED_GPUS}
MINIMUM_FREE_MIB = original.MINIMUM_FREE_MIB
HOST_RESERVE_BYTES = original.HOST_RESERVE_BYTES
SHARDS, STAGES, GIB = original.SHARDS, original.STAGES, original.GIB
AdmissionError = original.AdmissionError
AdmissionStopped = original.AdmissionStopped
AdmissionDeadlineExceeded = original.AdmissionDeadlineExceeded


def validate_plan(plan):
    original._require(
        plan.get("allowed_gpu_indices") == list(ALLOWED_GPUS)
        and plan.get("gpu_uuids") == GPU_UUIDS,
        "V40 requires the fixed authorized GPU0..7 indices and physical UUIDs",
    )
    return plan


original.ALLOWED_GPUS = ALLOWED_GPUS
original.GPU_UUIDS = GPU_UUIDS
original.validate_plan = validate_plan


def wait_for_pre_cuda_admission(*args, **kwargs):
    names = ("inventory", "host_memory", "process_memory", "birth")
    if any(kwargs.get(name) is None for name in names):
        control = importlib.import_module("finqa_v40_controller")
        kwargs = {
            **kwargs,
            **{
                name: getattr(control, name) if kwargs.get(name) is None else kwargs[name]
                for name in names
            },
        }
    return original.wait_for_pre_cuda_admission(*args, **kwargs)
