"""CPU-only tests; production observers and worker processes are not started."""
from __future__ import annotations

import signal
from types import SimpleNamespace

import pytest

import finqa_v63_binding as binding
import finqa_v63_entry as entry
import finqa_v63_signals as signals


@pytest.mark.parametrize(("number", "pid", "uid", "code", "filtered"), [
    (signal.SIGTERM, 123, 0, 0, True),
    (signal.SIGTERM, 123, 1005, 0, True),
    (signal.SIGTERM, 123, 1004, 0, False),
    (signal.SIGINT, 123, 0, 0, False),
    (signal.SIGTERM, 0, 0, 0, False),
    (signal.SIGTERM, 123, 0, -1, False),
    (signal.SIGTERM, 123, -1, 0, False),
    (signal.SIGTERM, 123, 4294967295, 0, False),
    (signal.SIGKILL, 123, 0, 0, False),
])
def test_exact_original_authorized_filter_no_broader_stop_suppression(number, pid, uid, code, filtered):
    result = signals.signal_decision(number, pid, uid, code)
    assert result["filtered"] is filtered
    assert result["dispatch_original_stop"] is not filtered


def test_signal_manifest_chain_and_unchanged_legal_stop_contract():
    refs = signals.external_source_bindings()
    assert refs["control04_manifest"]["id"] == signals.CONTROL04_ID
    assert refs["control03_manifest"]["id"] == signals.CONTROL03_ID
    assert refs["v59_signals"]["sha256"] == signals.SIGNAL59_SHA
    assert refs["v58_signals"]["sha256"] == signals.SIGNAL58_SHA
    assert refs["v58_observer"]["sha256"] == signals.OBSERVER58_SHA
    policy = signals.signals_policy()
    assert policy["owner_uid"] == 1004 and policy["filtered_si_codes"] == [0]
    assert policy["owner_SIGTERM_dispatches_original_stop"]
    assert policy["every_SIGINT_dispatches_original_stop"] and policy["explicit_STOP_unchanged"]
    assert not policy["SIGKILL_capturable"] and not policy["historical_sources_modified"]
    assert policy["no_machine_wide_observer_started"]


def test_early_install_rejects_any_science_or_torch_before_observer():
    signals.require_early_install({"finqa_v63_binding": SimpleNamespace(__file__="/new/finqa_v63_binding.py")})
    for name, path in (
        ("torch", "/venv/torch/__init__.py"),
        ("trusted_synthesis.finance_research.contracts", "/frozen/contracts.py"),
        ("finqa_v63_worker", "/new/finqa_v63_worker.py"),
    ):
        with pytest.raises(RuntimeError, match="precede scientific imports"):
            signals.require_early_install({name: SimpleNamespace(__file__=path)})


def test_install_is_new_root_only_uid_bound_and_once_without_real_threads(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path / "new")
    monkeypatch.setattr(signals, "_OBSERVER", None)
    monkeypatch.setattr(signals.os, "getuid", lambda: 1004)
    monkeypatch.setattr(signals.os, "geteuid", lambda: 1004)
    calls = []
    monkeypatch.setattr(signals, "require_early_install", lambda: calls.append("early"))
    observer = SimpleNamespace()
    monkeypatch.setattr(signals, "_reference", lambda: SimpleNamespace(
        install=lambda directory, **kwargs: calls.append((directory, kwargs)) or observer))
    with pytest.raises(ValueError, match="new experiment root"):
        signals.install(tmp_path / "old/signals", role="worker")
    actual = signals.install(binding.ROOT / "signals", role="worker", context={"job_id": "job"})
    assert actual is observer and calls[0] == "early"
    assert calls[1][1]["context"]["job_id"] == "job"
    with pytest.raises(ValueError, match="once"):
        signals.install(binding.ROOT / "again", role="worker")


@pytest.mark.parametrize(("status", "mode", "code"), [
    ("PASS", "check-imports", 0), ("FAIL", "check-imports", 2),
    ("COMPLETE", "worker", 0), ("COMPLETE", "generate", 0),
    ("CONTROLLER_TRANSIENT_FAILURE", "run", 75),
    ("STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME", "supervise", 2),
    ("BLOCKED_OPERATOR_REQUIRED", "run", 2),
])
def test_exit_status_mapping(status, mode, code):
    assert entry.exit_status(dict(status=status), mode) == code


def test_entry_installs_signal_before_paths_auxiliary_and_science_dispatch(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(entry, "__file__", str(tmp_path / "implementation/finqa_v63_entry.py"))
    order = []
    monkeypatch.setattr(entry, "checked_signal_registration",
                        lambda root: order.append("registered_signal_contract"))
    monkeypatch.setattr(signals, "install", lambda *args, **kwargs: (
        order.append("signal") or SimpleNamespace(close=lambda: order.append("close"))))
    monkeypatch.setattr(binding, "install_scientific_paths", lambda: order.append("paths"))
    monkeypatch.setattr(entry, "install_registered_auxiliary", lambda: order.append("auxiliary"))
    monkeypatch.setattr(entry, "_dispatch", lambda *args: (
        order.append("dispatch") or dict(status="COMPLETE", id="result")))
    assert entry.main(["--mode", "supervise", "--root", str(tmp_path)]) == 0
    assert order == ["registered_signal_contract", "signal", "paths", "auxiliary", "dispatch", "close"]
    assert '"status": "COMPLETE"' in capsys.readouterr().out


def test_workspace_entry_is_not_a_production_or_preflight_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(entry, "__file__", "/workspace/scripts/finqa_v63_entry.py")
    args = entry._arguments(["--mode", "check-imports", "--root", str(tmp_path)])
    with pytest.raises(ValueError, match="new frozen implementation"):
        entry._validate_arguments(args)


@pytest.mark.parametrize("mismatched", ["signal_policy", "signal_source_bindings"])
def test_registration_mismatch_blocks_before_observer_or_scientific_import(tmp_path, monkeypatch, mismatched):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(entry, "__file__", str(tmp_path / "implementation/finqa_v63_entry.py"))
    expected = dict(signal_policy={"owner_uid": 1004},
                    signal_source_bindings={"frozen_source": {"path": "/registered", "sha256": "a" * 64}})
    protocol = dict(expected)
    protocol[mismatched] = {"unexpected": True}
    reads = []
    monkeypatch.setattr(binding, "checked", lambda path: reads.append(path) or protocol)
    monkeypatch.setattr(signals, "signals_policy", lambda: expected["signal_policy"])
    monkeypatch.setattr(signals, "external_source_bindings", lambda: expected["signal_source_bindings"])
    monkeypatch.setattr(signals, "install", lambda *args, **kwargs: pytest.fail("mismatch installed an observer"))
    monkeypatch.setattr(binding, "install_scientific_paths",
                        lambda: pytest.fail("mismatch imported scientific paths"))
    with pytest.raises(ValueError, match="registered V63 signal"):
        entry.main(["--mode", "check-imports", "--root", str(tmp_path)])
    assert reads == [tmp_path / "protocol/record.json"]


def test_exact_signal_registration_is_pure_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    protocol = dict(signal_policy={"owner_uid": 1004},
                    signal_source_bindings={"registered": {"path": "/registered", "sha256": "a" * 64}})
    monkeypatch.setattr(binding, "checked", lambda path: protocol)
    monkeypatch.setattr(signals, "signals_policy", lambda: protocol["signal_policy"])
    monkeypatch.setattr(signals, "external_source_bindings", lambda: protocol["signal_source_bindings"])
    monkeypatch.setattr(entry.importlib, "import_module",
                        lambda *args, **kwargs: pytest.fail("signal metadata check imported science"))
    assert entry.checked_signal_registration(tmp_path) is protocol


def test_formal_import_check_rechecks_protocol_signal_binding_before_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    imported = []
    registration = SimpleNamespace(checked_protocol=lambda root: dict(
        id="protocol", signal_policy={"wrong_owner": 0}, signal_source_bindings={}))
    def import_module(name):
        imported.append(name)
        assert name == "finqa_v63_registration", "runtime import preceded signal-contract verification"
        return registration
    monkeypatch.setattr(entry.importlib, "import_module", import_module)
    monkeypatch.setattr(signals, "signals_policy", lambda: {"owner_uid": 1004})
    monkeypatch.setattr(signals, "external_source_bindings", lambda: {})
    with pytest.raises(ValueError, match="registered V63 signal policy"):
        entry.check_imports(tmp_path)
    assert imported == ["finqa_v63_registration"]


def test_worker_attempt_alias_and_own_job_path_must_match(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    monkeypatch.setattr(entry, "__file__", str(tmp_path / "implementation/finqa_v63_entry.py"))
    attempt = tmp_path / "stages/seed137/feedback_C1/attempts/attempt0001"
    for key in ("V63_ATTEMPT_DIR", "V56_ATTEMPT_DIR"):
        monkeypatch.setenv(key, str(attempt))
    for key in ("V63_ATTEMPT_ID", "V56_ATTEMPT_ID"):
        monkeypatch.setenv(key, attempt.name)
    monkeypatch.setenv("V54_JOB_ID", "seed137.feedback_C1")
    args = entry._arguments(["--mode", "worker", "--root", str(tmp_path),
                            "--seed", "137", "--stage", "feedback_C1",
                            "--gpu-index", "0", "--attempt-root", str(attempt)])
    assert entry._validate_arguments(args) == tmp_path
    monkeypatch.setenv("V56_ATTEMPT_ID", "attempt0002")
    with pytest.raises(ValueError, match="attempt identities"):
        entry._validate_arguments(args)


def import_fixture(tmp_path, monkeypatch):
    root, old, frozen = tmp_path / "new", tmp_path / "old", tmp_path / "frozen"
    canonical = tmp_path / "v25/implementation/finqa_v25_training_replication.py"
    alias = tmp_path / "workspace/scripts/finqa_v25_training_replication.py"
    monkeypatch.setattr(binding, "OLD_ROOT", old)
    monkeypatch.setattr(entry, "AUXILIARY_CANONICAL", canonical)
    monkeypatch.setattr(entry, "AUXILIARY_WORKSPACE_ALIAS", alias)
    paths = {
        "new": root / "implementation/finqa_v63_worker.py",
        "package": frozen / "trusted_synthesis/finance_research/contracts.py",
        "aux": canonical, "alias": alias,
        "signals": tmp_path / "control04/finqa_v59_signals.py",
        "old": old / "implementation/finqa_v54_temperature.py",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("VALUE = 1\n")
    implementation = dict(sha256={paths["new"].name: binding.sha(paths["new"])})
    science = dict(
        frozen_source_root=str(frozen),
        sha256={paths["old"].name: binding.sha(paths["old"])},
        external_frozen_source_sha256={
            str(canonical): binding.sha(canonical),
            str(paths["package"]): binding.sha(paths["package"]),
        })
    external_signals = {"v59_signals": binding.file_ref(paths["signals"])}
    modules = {
        "finqa_v63_worker": SimpleNamespace(__file__=str(paths["new"])),
        "trusted_synthesis.finance_research.contracts": SimpleNamespace(__file__=str(paths["package"])),
        "finqa_v25_training_replication": SimpleNamespace(__file__=str(canonical)),
        "_v63_frozen59_signals_private": SimpleNamespace(__file__=str(paths["signals"])),
        "finqa_v54_temperature": SimpleNamespace(__file__=str(paths["old"])),
    }
    return root, implementation, science, external_signals, modules, paths


def test_exact_dependency_bindings_and_explicit_unique_v25_alias(tmp_path, monkeypatch):
    root, implementation, science, signal_refs, modules, paths = import_fixture(tmp_path, monkeypatch)
    result = entry.verify_imported_modules(root, implementation, science, signal_refs, modules=modules)
    assert result["verified_dependency_count"] == 5 and not result["registered_byte_identical_path_aliases"]
    modules["finqa_v25_training_replication"].__file__ = str(paths["alias"])
    aliased = entry.verify_imported_modules(root, implementation, science, signal_refs, modules=modules)
    assert len(aliased["registered_byte_identical_path_aliases"]) == 1
    row = aliased["registered_byte_identical_path_aliases"][0]
    assert row["path"] == str(paths["alias"]) and row["registered_path"] == str(paths["aux"])
    paths["alias"].write_text("VALUE = 2\n")
    with pytest.raises(ValueError, match="source bytes differ"):
        entry.verify_imported_modules(root, implementation, science, signal_refs, modules=modules)


def test_workspace_package_pollution_rejected_even_when_bytes_identical(tmp_path, monkeypatch):
    root, implementation, science, signal_refs, modules, paths = import_fixture(tmp_path, monkeypatch)
    contaminated = tmp_path / "workspace/src/trusted_synthesis/finance_research/contracts.py"
    contaminated.parent.mkdir(parents=True)
    contaminated.write_text(paths["package"].read_text())
    modules["trusted_synthesis.finance_research.contracts"].__file__ = str(contaminated)
    with pytest.raises(ValueError, match="workspace/non-frozen"):
        entry.verify_imported_modules(root, implementation, science, signal_refs, modules=modules)


def test_no_general_same_filename_workspace_alias_is_admitted(tmp_path, monkeypatch):
    root, implementation, science, signal_refs, modules, paths = import_fixture(tmp_path, monkeypatch)
    contaminated = tmp_path / "workspace/scripts/finqa_v54_temperature.py"
    contaminated.write_text(paths["old"].read_text())
    modules["finqa_v54_temperature"].__file__ = str(contaminated)
    with pytest.raises(ValueError, match="unregistered scientific"):
        entry.verify_imported_modules(root, implementation, science, signal_refs, modules=modules)


def test_import_check_uses_runtime_before_dependencies_and_never_loads_parent(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, "ROOT", tmp_path)
    order = []
    rt = SimpleNamespace(torch=SimpleNamespace(cuda=SimpleNamespace(is_initialized=lambda: False)))
    guard = type("ResourceGuard", (), {})
    guard.__module__ = "finqa_v63_runtime"
    modules = {
        "finqa_v63_registration": SimpleNamespace(
            checked_protocol=lambda root: dict(id="protocol", signal_policy={"owner_uid": 1004},
                                                signal_source_bindings={}),
            checked_implementation=lambda root: dict(id="new-implementation")),
        "finqa_v63_training": SimpleNamespace(
            runtime=lambda: order.append("runtime") or (None, rt),
            load_parent=lambda *args: pytest.fail("CPU preflight must never load a parent")),
        "finqa_v63_runtime": SimpleNamespace(ResourceGuard=guard),
    }
    def imported(name):
        order.append(name)
        return modules.get(name, SimpleNamespace())
    monkeypatch.setattr(entry.importlib, "import_module", imported)
    monkeypatch.setattr(binding, "checked", lambda path: dict(id=binding.OLD_IMPLEMENTATION_ID))
    monkeypatch.setattr(entry, "install_registered_auxiliary", lambda: dict(path="canonical", path_alias=False))
    monkeypatch.setattr(signals, "external_source_bindings", lambda: {})
    monkeypatch.setattr(signals, "signals_policy", lambda: {"owner_uid": 1004})
    monkeypatch.setattr(entry, "verify_imported_modules", lambda *args: dict(verified_dependency_count=1))
    result = entry.check_imports(tmp_path)
    assert order.index("runtime") < order.index(entry.WORKER_IMPORTS[0])
    assert result["status"] == "PASS" and not result["CUDA_initialized"]
    assert not result["parent_loaded"] and not result["model_loaded"]
    assert result["scientific_calls"] == result["optimizer_updates"] == 0
