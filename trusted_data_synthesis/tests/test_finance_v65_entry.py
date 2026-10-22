"""No-model regressions for early-generation entry authorization and exits."""
from types import SimpleNamespace

import pytest

import finqa_v65_binding as binding
import finqa_v65_entry as entry


def test_observer_precedes_science_and_only_sealed_status_is_control_success(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(entry, "__file__", str(tmp_path / "implementation/finqa_v65_entry.py"))
    events = []
    monkeypatch.setattr(entry, "checked_signal_registration", lambda root: events.append("policy") or {})
    monkeypatch.setattr(entry, "install_signal_observer", lambda *args: events.append("observer") or
                        SimpleNamespace(close=lambda: events.append("close")))
    monkeypatch.setattr(entry, "initialize_science", lambda: events.append("science"))
    monkeypatch.setattr(entry, "_dispatch", lambda *args: events.append("dispatch") or dict(status=entry.SEALED_STATUS))
    assert entry.main(["--mode", "supervise", "--root", str(tmp_path)]) == 0
    assert events == ["policy", "observer", "science", "dispatch", "close"]


def test_early_import_guard_rejects_model_runtime_and_scientific_workers():
    entry.require_early_install({"finqa_v65_binding": SimpleNamespace(__file__="/new/finqa_v65_binding.py")})
    for name, filename in (("torch", "/torch/__init__.py"),
                           ("finqa_v65_runtime", "/new/finqa_v65_runtime.py"),
                           ("finqa_v63_worker", "/old/finqa_v63_worker.py")):
        with pytest.raises(RuntimeError, match="precede"):
            entry.require_early_install({name: SimpleNamespace(__file__=filename)})


def test_no_worker_mode_can_dispatch_blocked_core():
    assert "worker" not in entry.MODES
    with pytest.raises(SystemExit):
        entry._arguments(["--mode", "worker"])


def test_workspace_entry_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(entry, "__file__", "/workspace/finqa_v65_entry.py")
    with pytest.raises(ValueError, match="frozen implementation"):
        entry._validate_arguments(entry._arguments(["--mode", "run", "--root", str(tmp_path)]))


def test_generation_uses_own_attempt_root_and_aliases(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(entry, "__file__", str(tmp_path / "implementation/finqa_v65_entry.py"))
    attempt = tmp_path / "evaluations/jobs/job/attempts/attempt0001"
    for name in ("V63_ATTEMPT_DIR", "V56_ATTEMPT_DIR"):
        monkeypatch.setenv(name, str(attempt))
    for name in ("V63_ATTEMPT_ID", "V56_ATTEMPT_ID"):
        monkeypatch.setenv(name, attempt.name)
    monkeypatch.setenv("V65_CONTROL_ROOT", str(tmp_path))
    monkeypatch.setenv("V54_JOB_ID", "job")
    args = entry._arguments(["--mode", "generate", "--root", str(tmp_path), "--job", "job",
        "--gpu", "0", "--attempt-root", str(attempt)])
    assert entry._validate_arguments(args) == tmp_path
    monkeypatch.setenv("V56_ATTEMPT_ID", "attempt0002")
    with pytest.raises(ValueError, match="aliases"):
        entry._validate_arguments(args)


@pytest.mark.parametrize(("status", "mode", "code"), [
    ("PASS", "check-imports", 0), ("FAIL", "check-imports", 2),
    ("COMPLETE", "generate", 0), ("COMPLETE", "run", 2), ("COMPLETE", "supervise", 2),
    (entry.SEALED_STATUS, "run", 0), (entry.SEALED_STATUS, "supervise", 0),
    ("CONTROLLER_TRANSIENT_FAILURE", "run", 75), ("BLOCKED_OPERATOR_REQUIRED", "run", 2),
])
def test_exit_mapping(status, mode, code):
    assert entry.exit_status(dict(status=status), mode) == code


def test_workspace_source_cannot_hide_in_frozen_closure(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="workspace early-generation"):
        entry.verify_imported_modules(tmp_path, dict(sha256={"finqa_v65_runtime.py": "a" * 64}),
            modules={"finqa_v65_runtime": SimpleNamespace(__file__="/workspace/finqa_v65_runtime.py")})
