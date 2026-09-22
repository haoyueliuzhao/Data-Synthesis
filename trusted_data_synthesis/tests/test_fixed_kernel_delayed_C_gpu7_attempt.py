"""Admission and ownership checks only; no GPU allocation or real process signals."""

import importlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
t = importlib.import_module("run_fixed_kernel_delayed_C_gpu7_attempt_20260922")


def test_only_requested_gpu_with_saved_final_and_enough_headroom():
    row = dict(active=None, stopped=None, attempt=6)
    gpu = dict(index=7, free_MiB=35767)
    assert t.admission(row, gpu, phase="final", step=400, completed=169) == 7
    for change, match in (({"index": 0}, "requested_GPU7"), ({"free_MiB": 33791}, "cold_start")):
        with pytest.raises(ValueError, match=match):
            t.admission(row, {**gpu, **change}, phase="final", step=400, completed=169)


def test_never_duplicates_busy_run_or_restarts_training():
    row = dict(active=None, stopped=None, attempt=6)
    gpu = dict(index=7, free_MiB=35767)
    with pytest.raises(ValueError, match="inactive_nonfailed"):
        t.admission({**row, "active": {"pid": 12}}, gpu, phase="final", step=400, completed=169)
    with pytest.raises(ValueError, match="only_step400_final"):
        t.admission(row, gpu, phase="sft", step=399, completed=169)
    with pytest.raises(ValueError, match="sealed_cohort"):
        t.admission(row, gpu, phase="final", step=400, completed=180)


def test_controller_check_rejects_worker_role(tmp_path, monkeypatch):
    identity = dict(uid=os.getuid(), command=[str(tmp_path / t.a.SCRIPT), "--mode", "worker"])
    monkeypatch.setattr(t.p, "read_json", lambda path: identity)
    monkeypatch.setattr(t.m, "same_process", lambda expected: True)
    with pytest.raises(ValueError, match="exact_registered_coordinate"):
        t.registered_controller(tmp_path, tmp_path / "identity.json", "coordinate")
