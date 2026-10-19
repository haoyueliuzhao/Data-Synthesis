"""CPU-only frozen worker routing and V62 monitoring namespace checks."""
import hashlib
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import finqa_v59_signals as signals
import finqa_v62_worker as worker


def test_private_installer_and_adjacent_helper_do_not_modify_public_imports():
    import importlib
    original = importlib.import_module
    inherited = worker._load_private_worker()
    legacy = inherited._load_private_worker()
    assert legacy.install is worker.install_worker_runtime
    assert Path(inherited.__file__).resolve() == worker.FROZEN_ROOT / 'finqa_v58_worker.py'
    assert Path(worker._gpu_isolation().__file__).name == 'finqa_v62_gpu_isolation.py'
    assert importlib.import_module is original


@pytest.mark.parametrize('cpu_check', [False, True])
def test_signal_then_original_paths_then_bound_GPU_guard(monkeypatch, cpu_check):
    calls, token = [], object()
    monkeypatch.setattr(signals, 'install', lambda *a, **k: calls.append('signals') or token)
    original = SimpleNamespace(configure_worker_paths=lambda root: calls.append(('paths', root)))
    monkeypatch.setattr(worker, '_load_private_worker', lambda: SimpleNamespace(_load_private_worker=lambda: original))
    monkeypatch.setattr(worker, '_gpu_isolation', lambda: SimpleNamespace(
        install_worker_guard=lambda **kwargs: calls.append(('guard', kwargs))))
    assert worker.install_worker_runtime('synthetic', role='worker', cpu_check=cpu_check) is token
    assert calls == ['signals', ('paths', worker.SCIENCE_ROOT), ('guard', {'cpu_check': cpu_check})]


def test_science_main_delegates_original_argv_without_CPU_override(monkeypatch):
    calls = []
    argv = ['finqa_v62_worker.py', '--mode', 'science', '--root', str(worker.SCIENCE_ROOT), '--stage', 'generate']
    monkeypatch.setattr(sys, 'argv', argv)
    monkeypatch.setattr(worker, '_load_private_worker', lambda: SimpleNamespace(main=lambda: calls.append(list(sys.argv))))
    worker.main()
    assert calls == [argv]


def test_CPU_import_main_explicitly_enables_master_check_only(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, 'argv', ['finqa_v62_worker.py', '--mode', 'check-imports', '--root', str(worker.SCIENCE_ROOT)])
    monkeypatch.setenv('V57_SIGNAL_LOG_DIR', 'synthetic')
    monkeypatch.setattr(worker, '_load_private_worker', lambda: object())
    monkeypatch.setattr(worker, 'install_worker_runtime', lambda *args, **kwargs: calls.append(kwargs))
    monkeypatch.setattr(worker, 'check_worker_imports', lambda *args, **kwargs: dict(status='PASS'))
    worker.main()
    assert calls[0]['cpu_check'] is True


def test_new_and_inherited_monitoring_files_are_exactly_scoped(tmp_path):
    assert len(worker.MONITORING_FILES) == 17
    source = tmp_path / 'finqa_v62_gpu_isolation.py'
    source.write_text('synthetic')
    manifest = dict(files={source.name: hashlib.sha256(source.read_bytes()).hexdigest()})
    row = worker._monitoring_path(source, tmp_path, manifest, dict(files={}))
    assert row['origin'] == 'V62_master'
    with pytest.raises(RuntimeError, match='escaped'):
        worker._monitoring_path(source, tmp_path / 'elsewhere', manifest, dict(files={}))
    assert worker._monitoring_path(tmp_path / 'unrelated.py', tmp_path, manifest, dict(files={})) is None

