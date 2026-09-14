"""Small CPU-only resource-admission controls; no model or GPU work."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/continue_fixed_kernel_parallel_tail_shared_gpu_20260914.py"
)
SPEC = importlib.util.spec_from_file_location("shared_gpu_admission", SCRIPT)
admission = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(admission)


def snapshot():
    return [
        dict(index=index, uuid=f"GPU-{index}", free_memory_MiB=32768, utilization_percent=100)
        for index in range(8)
    ]


def test_busy_gpus_with_enough_memory_are_admitted_in_physical_order():
    rows = snapshot()
    wanted = {row["uuid"] for row in rows}
    assert admission.eligible_devices(list(reversed(rows)), wanted) == rows


def test_one_mib_below_threshold_waits_and_unbound_gpu_cannot_replace_it():
    rows = snapshot()
    wanted = {row["uuid"] for row in rows}
    rows[3]["free_memory_MiB"] = 32767
    rows.append(dict(index=8, uuid="GPU-unbound", free_memory_MiB=81920, utilization_percent=0))
    actual = admission.eligible_devices(rows, wanted)
    assert len(actual) == 7
    assert {row["uuid"] for row in actual} == wanted - {"GPU-3"}


def test_duplicate_uuid_cannot_impersonate_eight_physical_devices():
    rows = snapshot()
    wanted = {row["uuid"] for row in rows}
    rows[-1] = dict(rows[0])
    with pytest.raises(ValueError):
        admission.eligible_devices(rows, wanted)
