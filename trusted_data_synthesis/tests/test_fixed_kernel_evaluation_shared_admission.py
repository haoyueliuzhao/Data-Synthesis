"""Focused CPU-only controls for memory admission and actual child-exit evidence."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/fixed_kernel_evaluation_shared_gpu_scheduler_20260915.py"
)
SPEC = importlib.util.spec_from_file_location("evaluation_memory_admission", SCRIPT)
scheduler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scheduler)


def snapshot():
    return [
        dict(index=index, uuid=f"GPU-{index}", free_memory_MiB=77824, utilization_percent=100)
        for index in range(8)
    ]


def test_busy_card_with_sufficient_memory_is_allowed_but_own_active_card_is_not():
    rows = snapshot()
    wanted = {row["uuid"] for row in rows}
    actual = scheduler.eligible_devices(list(reversed(rows)), wanted, used={"GPU-2"})
    assert actual == rows[:2] + rows[3:]


def test_generation_does_not_use_training_threshold_or_unbound_devices():
    rows = snapshot()
    wanted = {row["uuid"] for row in rows}
    rows[0]["free_memory_MiB"] = 32768
    rows[1]["free_memory_MiB"] = 77823
    rows.append(dict(index=8, uuid="GPU-unbound", free_memory_MiB=81920, utilization_percent=0))
    assert scheduler.eligible_devices(rows, wanted) == rows[2:8]


def test_duplicate_device_snapshot_is_rejected():
    rows = snapshot()
    wanted = {row["uuid"] for row in rows}
    rows[-1] = dict(rows[0])
    with pytest.raises(ValueError):
        scheduler.eligible_devices(rows, wanted)


def test_adopted_child_requires_actual_bound_zero_exit_not_a_disappeared_process():
    process = dict(pid=101, start_ticks=456, ppid=3381543)
    bound = process
    actual = dict(**process, state="Z", exit_status_provable=True, return_code=0)
    scheduler.validate_original_exit(bound, actual)
    for changed in (
        dict(state="gone", exit_status_provable=False, return_code=None),
        dict(return_code=1),
        dict(start_ticks=457),
        dict(ppid=1),
    ):
        with pytest.raises(ValueError):
            scheduler.validate_original_exit(bound, {**actual, **changed})


def test_only_the_observed_standard_resource_tracker_is_an_auxiliary_child():
    argv = [
        scheduler.sys.executable,
        "-c",
        "from multiprocessing.resource_tracker import main;main(3)",
    ]
    observed = dict(
        pid=3408891,
        ppid=3381543,
        state="S",
        cmdline_sha256=scheduler.p.sha(b"\0".join(arg.encode() for arg in argv) + b"\0"),
    )
    scheduler.validate_resource_tracker(observed)
    for changed in (dict(pid=3419286), dict(ppid=1), dict(cmdline_sha256="another-command")):
        with pytest.raises(ValueError):
            scheduler.validate_resource_tracker({**observed, **changed})
