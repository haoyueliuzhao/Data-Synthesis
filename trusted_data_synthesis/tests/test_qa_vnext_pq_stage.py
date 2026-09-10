"""Synthetic scheduling and CPU loss controls; no subprocess or GPU is started."""

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_pq_student import stage, weights
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.plan import OUTPUT

ROOT = Path(__file__).resolve().parents[2]


def test_CPU_exact_probe_uses_only_fixed_original_weight_view():
    probe = stage.cpu_loss_probe(weights.build(ROOT))
    assert probe["exactly_equal"] and probe["all_blocks_add_exactly"]
    assert not probe["Student_loaded"]
    assert probe["measured_Q_minus_P"] == probe["expected_L1_identity"]


def test_GPU_admission_filters_busy_or_different_devices(monkeypatch):
    monkeypatch.setattr(
        stage.subprocess,
        "check_output",
        lambda *a, **k: (
            "0, NVIDIA A100-SXM4-80GB, 16355\n"
            "1, NVIDIA A100-SXM4-80GB, 70000\n"
            "4, NVIDIA A100-SXM4-80GB, 81154\n"
            "5, NVIDIA A100-SXM4-40GB, 75000\n"
            "9, NVIDIA A100-SXM4-80GB, 81154\n"
        ),
    )
    assert stage.available_devices() == [1, 4]


def test_worker_environment_is_offline_and_does_not_inherit_credentials(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-not-a-secret")
    monkeypatch.setenv("HF_TOKEN", "synthetic-not-a-secret")
    env = stage.worker_environment(ROOT, 3)
    assert env["CUDA_VISIBLE_DEVICES"] == "3"
    assert env["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"
    assert env["HF_HUB_OFFLINE"] == env["TRANSFORMERS_OFFLINE"] == "1"
    assert "DEEPSEEK_API_KEY" not in env and "HF_TOKEN" not in env


def setup_runner(monkeypatch, devices):
    monkeypatch.setattr(stage, "check_preparation", lambda root: {"id": "synthetic-preparation"})
    monkeypatch.setattr(stage, "available_devices", lambda: devices)
    monkeypatch.setattr(stage, "history_guard", lambda root: {})
    monkeypatch.setattr(stage, "verify_pairing", lambda root: {"id": "synthetic-pairing"})
    monkeypatch.setattr(stage.time, "sleep", lambda seconds: None)


def test_no_free_GPU_leaves_execution_uncreated_and_never_launches(tmp_path, monkeypatch):
    setup_runner(monkeypatch, [])
    monkeypatch.setattr(stage, "launch", lambda *args: pytest.fail("must not launch"))
    with pytest.raises(ValueError, match="wait_for_free_A100"):
        stage.run(tmp_path)
    assert not (tmp_path / OUTPUT / "execution").exists()


class FakeProcess:
    def __init__(self):
        self.polls = 0

    def wait(self):
        return 0

    def poll(self):
        self.polls += 1
        return 0 if self.polls >= 2 else None


def test_one_free_GPU_runs_baseline_then_six_serial_variants(tmp_path, monkeypatch):
    setup_runner(monkeypatch, [5])
    started = []

    def launch(root, variant, gpu):
        started.append((variant, gpu))
        return FakeProcess()

    monkeypatch.setattr(stage, "launch", launch)
    assert stage.run(tmp_path)["id"] == "synthetic-pairing"
    assert started == [
        (variant, 5) for variant in ("B0", "P_11", "Q_11", "P_29", "Q_29", "P_47", "Q_47")
    ]
    report = json.loads((tmp_path / OUTPUT / "execution/process_report.json").read_bytes())
    assert report["all_seven_completed"] and report["unstarted"] == []


def test_launch_failure_drains_active_worker_and_keeps_pending_registered(tmp_path, monkeypatch):
    setup_runner(monkeypatch, [0, 1])
    started, active = [], FakeProcess()

    def launch(root, variant, gpu):
        started.append(variant)
        if variant == "Q_11":
            raise ValueError("synthetic resource race")
        return active if variant == "P_11" else FakeProcess()

    monkeypatch.setattr(stage, "launch", launch)
    with pytest.raises(ValueError, match="worker_failure_no_automatic_retry"):
        stage.run(tmp_path)
    assert started == ["B0", "P_11", "Q_11"] and active.polls == 2
    report = json.loads((tmp_path / OUTPUT / "execution/process_report.json").read_bytes())
    assert not report["all_seven_completed"]
    assert report["unstarted"] == ["P_29", "Q_29", "P_47", "Q_47"]
    assert next(row for row in report["rows"] if row["variant"] == "Q_11")["started"] is False
