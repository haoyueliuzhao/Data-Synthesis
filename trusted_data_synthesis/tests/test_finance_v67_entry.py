"""Independent CPU seal entry preserves legal-stop order and frozen scope."""
from types import SimpleNamespace
import pytest
import finqa_v67_binding as binding
import finqa_v67_entry as entry


def seal_args(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(entry, "__file__", str(tmp_path / "implementation/finqa_v67_entry.py"))
    attempt = tmp_path / "repairs/job/attempt0001"
    for version in ("V63", "V56", "V67"):
        monkeypatch.setenv(version + "_ATTEMPT_DIR", str(attempt))
        monkeypatch.setenv(version + "_ATTEMPT_ID", attempt.name)
    monkeypatch.setenv("V67_CONTROL_ROOT", str(tmp_path))
    monkeypatch.setenv("V54_JOB_ID", "job")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    monkeypatch.delenv("V54_GPU_LEASE_FD", raising=False)
    return ["--mode", "seal", "--root", str(tmp_path), "--job", "job", "--attempt-root", str(attempt)]


def test_cpu_entry_is_distinct_cuda_disabled_and_lease_free(tmp_path, monkeypatch):
    args = entry._arguments(seal_args(tmp_path, monkeypatch))
    assert entry._validate_arguments(args) == tmp_path
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    with pytest.raises(ValueError, match="CUDA-disabled"):
        entry._validate_arguments(args)


def test_cpu_entry_installs_observer_without_science_initializer(tmp_path, monkeypatch):
    args = seal_args(tmp_path, monkeypatch)
    events = []
    monkeypatch.setattr(entry, "checked_signal_registration", lambda root: {})
    monkeypatch.setattr(entry, "install_signal_observer", lambda *args: events.append("observer") or
        SimpleNamespace(close=lambda: events.append("close")))
    monkeypatch.setattr(entry, "initialize_science", lambda: pytest.fail("CPU seal must not initialize science runtime"))
    monkeypatch.setattr(entry, "_dispatch", lambda *args: events.append("dispatch") or dict(status="COMPLETE"))
    assert entry.main(args) == 0
    assert events == ["observer", "dispatch", "close"]


def test_no_core_worker_entry_and_only_global_seal_is_control_success():
    assert "worker" not in entry.MODES
    assert entry.exit_status(dict(status="COMPLETE"), "run") == 2
    assert entry.exit_status(dict(status=entry.SEALED_STATUS), "run") == 0
    assert entry.exit_status(dict(status="COMPLETE"), "seal") == 0


def test_early_import_guard_rejects_torch_before_observer():
    with pytest.raises(RuntimeError):
        entry.require_early_install({"torch": SimpleNamespace(__file__="/torch/__init__.py")})
