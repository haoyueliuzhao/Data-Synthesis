"""Private installer delegation only; no scientific calls or CUDA."""
from pathlib import Path
import sys
from types import SimpleNamespace

import finqa_v59_signals as signals
import finqa_v59_worker as worker


def test_private_frozen_worker_binds_new_installer_without_global_import_patch():
    import importlib
    original = importlib.import_module
    inherited = worker._load_private_worker()
    legacy = inherited._load_private_worker()
    assert legacy.install is worker.install_worker_runtime
    assert Path(inherited.__file__).resolve() == worker.FROZEN_ROOT/"finqa_v58_worker.py"
    assert importlib.import_module is original
    assert legacy.configure_worker_paths is not None


def test_science_cli_delegates_original_main_without_mutating_arguments(monkeypatch):
    calls = []
    argv = ["finqa_v59_worker.py", "--mode", "science", "--root", str(worker.SCIENCE_ROOT),
            "--seed", "137", "--stage", "shard01", "--gpu-index", "2"]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(worker, "_load_private_worker", lambda: SimpleNamespace(main=lambda: calls.append(list(sys.argv))))
    worker.main()
    assert calls == [argv]


def test_worker_installs_signals_before_paths_and_pre_cuda_guard(monkeypatch):
    calls, token = [], object()
    monkeypatch.setattr(signals, "install", lambda *a, **k: calls.append("signals") or token)
    original = SimpleNamespace(configure_worker_paths=lambda root: calls.append(("paths", root)))
    monkeypatch.setattr(worker, "_load_private_worker", lambda: SimpleNamespace(_load_private_worker=lambda: original))
    monkeypatch.setattr(worker, "_gpu_isolation", lambda: SimpleNamespace(install_worker_guard=lambda: calls.append("gpu_guard")))
    assert worker.install_worker_runtime("synthetic", role="test") is token
    assert calls == ["signals", ("paths", worker.SCIENCE_ROOT), "gpu_guard"]
