"""Entry ordering and frozen dependency boundaries; no real observer or CUDA."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import finqa_v64_binding as binding
import finqa_v64_entry as entry


def test_observer_precedes_all_scientific_imports(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(entry, "__file__", str(tmp_path / "implementation/finqa_v64_entry.py"))
    order = []
    monkeypatch.setattr(entry, "checked_signal_registration", lambda root: order.append("policy") or {})
    monkeypatch.setattr(entry, "install_signal_observer", lambda *args: order.append("observer") or
                        SimpleNamespace(close=lambda: order.append("close")))
    monkeypatch.setattr(entry, "initialize_science", lambda: order.append("science"))
    monkeypatch.setattr(entry, "_dispatch", lambda *args: order.append("dispatch") or dict(status="COMPLETE", id="result"))
    assert entry.main(["--mode", "supervise", "--root", str(tmp_path)]) == 0
    assert order == ["policy", "observer", "science", "dispatch", "close"]
    assert '"status": "COMPLETE"' in capsys.readouterr().out


def test_early_signal_install_rejects_torch_runtime_worker_and_package():
    entry.require_early_install({"finqa_v64_binding": SimpleNamespace(__file__="/new/finqa_v64_binding.py")})
    for name, filename in (("torch", "/torch/__init__.py"),
                           ("trusted_synthesis.core", "/frozen/core.py"),
                           ("finqa_v64_runtime", "/frozen/finqa_v64_runtime.py"),
                           ("finqa_v63_worker", "/old/finqa_v63_worker.py")):
        with pytest.raises(RuntimeError, match="precede"):
            entry.require_early_install({name: SimpleNamespace(__file__=filename)})


def test_foreign_or_workspace_entry_cannot_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(entry, "__file__", "/workspace/finqa_v64_entry.py")
    args = entry._arguments(["--mode", "run", "--root", str(tmp_path)])
    with pytest.raises(ValueError, match="frozen implementation"):
        entry._validate_arguments(args)


def test_worker_keeps_old_stable_attempt_but_requires_new_control_root(tmp_path, monkeypatch):
    science, control = tmp_path / "science", tmp_path / "science/protection"
    monkeypatch.setattr(binding, "ROOT", control)
    monkeypatch.setattr(binding, "SCIENTIFIC_ROOT", science)
    monkeypatch.setattr(entry, "__file__", str(control / "implementation/finqa_v64_entry.py"))
    attempt = science / "stages/seed137/replay_C05/attempts/attempt0003"
    for name in ("V63_ATTEMPT_DIR", "V56_ATTEMPT_DIR"):
        monkeypatch.setenv(name, str(attempt))
    for name in ("V63_ATTEMPT_ID", "V56_ATTEMPT_ID"):
        monkeypatch.setenv(name, attempt.name)
    monkeypatch.setenv("V64_CONTROL_ROOT", str(control))
    monkeypatch.setenv("V54_JOB_ID", "seed137.replay_C05")
    args = entry._arguments(["--mode", "worker", "--root", str(control), "--seed", "137",
        "--stage", "replay_C05", "--gpu-index", "7", "--attempt-root", str(attempt)])
    assert entry._validate_arguments(args) == control
    monkeypatch.setenv("V56_ATTEMPT_ID", "attempt0001")
    with pytest.raises(ValueError, match="aliases"):
        entry._validate_arguments(args)


@pytest.mark.parametrize(("status", "mode", "code"), [
    ("PASS", "check-imports", 0), ("FAIL", "check-imports", 2),
    ("COMPLETE", "worker", 0), ("COMPLETE", "generate", 0),
    ("CONTROLLER_TRANSIENT_FAILURE", "run", 75),
    ("STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME", "supervise", 2),
])
def test_exit_mapping(status, mode, code):
    assert entry.exit_status(dict(status=status), mode) == code


def test_changed_legal_stop_policy_is_rejected_before_any_science(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path / "control")
    monkeypatch.setattr(binding, "SCIENTIFIC_ROOT", tmp_path / "science")
    monkeypatch.setattr(binding, "BASE_PROTOCOL_ID", "original")
    original = dict(id="original", signal_policy={"owner_term": True}, signal_source_bindings={"source": "frozen"})
    protocol = dict(scientific_protocol_id="original", signal_policy={"owner_term": False},
                    signal_source_bindings=original["signal_source_bindings"])
    monkeypatch.setattr(binding, "checked", lambda path: original)
    monkeypatch.setattr(entry, "signal_api", lambda: SimpleNamespace(
        signals_policy=lambda: original["signal_policy"],
        external_source_bindings=lambda: original["signal_source_bindings"]))
    with pytest.raises(ValueError, match="exact authorized"):
        entry.checked_signal_registration(binding.ROOT, protocol=protocol)


def test_workspace_v64_source_cannot_hide_in_import_closure(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    module = SimpleNamespace(__file__="/workspace/finqa_v64_runtime.py")
    with pytest.raises(ValueError, match="workspace protection"):
        entry.verify_imported_modules(tmp_path, dict(sha256={"finqa_v64_runtime.py": "a" * 64}),
                                      modules={"finqa_v64_runtime": module})
