"""Only V62 control namespace/policy deltas; no scientific replay or real launch."""
import ast
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

import finqa_v62_backend as backend
import finqa_v62_binding as binding
import finqa_v62_cron as cron
import finqa_v62_observer as observer
import finqa_v62_watchdog as watchdog


def test_registered_namespace_and_cron_line_are_independent():
    assert binding.MASTER_ROOT == binding.SCIENCE_ROOT / "shared_gpu_admission_01"
    assert binding.SOURCE_CONTROL_ROOT == binding.SCIENCE_ROOT / "signal_recovery_04"
    assert watchdog.ROOT == binding.MASTER_ROOT
    line = cron.line().decode()
    assert "FINQA_V62_ACCOUNT_WATCHDOG_01_UID1004" in line
    assert "/shared_gpu_admission_01/implementation/finqa_v62_cron.py" in line
    assert "/concurrency_six_01/" not in line


def test_policy_removes_only_known_account_exclusion():
    value = watchdog.policy()
    assert value["known_account_exclusion_removed_under_V62"] is True
    assert value["unknown_GPU_ownership_and_unattributed_MPS_blocked"] is True
    assert value["original_GPU_resource_gates_required"] is True
    assert "original_GPU_isolation_required" not in value
    assert value["scientific_worker_limit"] == 6
    resources = value["resource_override"]
    assert resources["max_gpu_workers"] == 6 and resources["per_gpu_workers"] == 1
    assert resources["allocated_lifetime_limit_gib"] == 76
    assert resources["boundary_free_reserve_gib"] == 2
    assert resources["effective_host_available_reserve_gib"] == 96
    assert value["independent_observer_limit"] == 1
    assert {"OWNER_TERM", "SIGINT", "STOP", "UNKNOWN_FEEDBACK"} <= set(value["permanent_stop_reasons"])


@pytest.mark.parametrize("kind,names", [
    ("backend", ("audit_durable", "retire_observer", "launch_registered", "reconcile_launch", "_early_startup")),
    ("watchdog", ("observation_decision", "checked_audits", "probe_original_leases")),
    ("cron", ("request_stop", "change_crontab", "_atomic")),
    ("observer", ("checked_control", "main")),
])
def test_critical_control_bodies_are_namespace_only_copies(kind, names):
    directory = Path(inspect.getfile(watchdog)).parent
    old = ast.parse((directory / f"finqa_v61_{kind}.py").read_text().replace("v61", "v62").replace("V61", "V62"))
    new = ast.parse((directory / f"finqa_v62_{kind}.py").read_text())
    for name in names:
        expected = next(node for node in old.body if isinstance(node, ast.FunctionDef) and node.name == name)
        actual = next(node for node in new.body if isinstance(node, ast.FunctionDef) and node.name == name)
        assert ast.dump(actual, include_attributes=False) == ast.dump(expected, include_attributes=False), name


@pytest.fixture
def guard(tmp_path, monkeypatch):
    root, science, initial = (tmp_path / name for name in ("new-master", "science", "source04"))
    for directory in (root, science, initial):
        directory.mkdir()
    monkeypatch.setattr(watchdog, "ROOT", root)
    monkeypatch.setattr(watchdog, "SCIENCE_ROOT", science)
    monkeypatch.setattr(watchdog, "INITIAL_EPISODE_ROOT", initial)
    episode = dict(root=str(initial), protocol_id="unchanged-source04")
    observation = dict(episode_root=str(initial), control_protocol_id=episode["protocol_id"],
        identity_roster_complete=True, identities=[dict(role="controller", pid=123, birth="456", alive=False)],
        known_terminal_reason=None, stop_marker_present=False, experiment_complete=False,
        actual_waitpid_observed=False, actual_returncode=None)
    callbacks = SimpleNamespace(
        checked_protocol=lambda _root: dict(id="new-master-protocol", root=str(root),
            scientific_root=str(science), policy=watchdog.policy()),
        checked_prepared=lambda _root: dict(protocol_id="new-master-protocol", initial_episode=episode),
        observe_episode=lambda *args: dict(observation),
        checked_authorized_handoff=lambda _observation: None)
    return root, callbacks, observation


def test_no_completed_handoff_cannot_take_over_even_disappeared_source04(guard):
    root, callbacks, _ = guard
    result = watchdog.tick(root, backend=callbacks,
        lease_probe=lambda _: pytest.fail("V62 has no source04 takeover authority yet"))
    assert result["status"] == "WAITING_FOR_AUTHORIZED_HANDOFF"
    assert not (root / "requests").exists()


@pytest.mark.parametrize("reason", ["OWNER_TERM", "SIGINT", "STOP", "UNKNOWN_FEEDBACK"])
def test_new_namespace_never_waives_user_stop_or_unknown_feedback(guard, reason):
    root, callbacks, observation = guard
    observation["known_terminal_reason"] = reason
    result = watchdog.tick(root, backend=callbacks,
        lease_probe=lambda _: pytest.fail("stop cannot acquire leases or create a child"))
    assert result["status"] == "STOPPED_NO_AUTO_RECOVERY"
    assert result["reason"] == reason


def test_backend_precise_handoff_imports_only_new_handoff(tmp_path, monkeypatch):
    root, initial = tmp_path / "master62", tmp_path / "source04"
    monkeypatch.setattr(backend, "MASTER_ROOT", root)
    monkeypatch.setattr(backend, "SOURCE_CONTROL_ROOT", initial)
    seen = []
    def module(name):
        seen.append(name)
        return SimpleNamespace(validate_authorized_stop=lambda *args: None)
    monkeypatch.setattr(backend.importlib, "import_module", module)
    observation = dict(episode_root=str(initial), control_protocol_id=backend.SOURCE_CONTROL_PROTOCOL_ID,
        identities=[dict(pid=123, birth="456", alive=False)], identity_roster_complete=True,
        any_sigint_observed=False, unfiltered_unknown_stop_signal=False,
        known_hard_block=False, known_implementation_failure=False, known_terminal_reason="OWNER_TERM")
    assert backend.checked_authorized_handoff(observation) is None
    assert seen == ["finqa_v62_handoff"]
    assert observation["known_terminal_reason"] == "OWNER_TERM"


def test_old_dispatch_token_cannot_launch_new_namespace(tmp_path, monkeypatch):
    root = tmp_path / "master62"
    control = root / "episodes/episode000001"
    directory = root / "backend/launches/request000001/attempt0001"
    monkeypatch.setattr(backend, "MASTER_ROOT", root)
    monkeypatch.setattr(backend, "episode_root", lambda value: Path(value))
    backend.write_record(directory / "intent/record.json", dict(dispatch_token_sha256=backend.digest("secret")), immutable=True)
    monkeypatch.setenv("V61_DISPATCH_TOKEN", "secret")
    monkeypatch.delenv("V62_DISPATCH_TOKEN", raising=False)
    with pytest.raises(ValueError, match="missing or wrong early-startup token"):
        backend._early_startup(SimpleNamespace(root=control, dispatch_directory=directory, action="run-episode"))
    assert not (control / "runner/launch/record.json").exists()


def test_observer_remains_one_readonly_monitor_under_new_resource_contract(monkeypatch):
    signals = dict(owner_SIGTERM_dispatches_original_stop=True, every_SIGINT_dispatches_original_stop=True)
    helper = SimpleNamespace(load_original=lambda: SimpleNamespace(observer_policy=lambda: {"readonly": True}),
        signals_policy=lambda: signals)
    monkeypatch.setattr(observer, "load_v59_module", lambda _name: helper)
    policy = observer.observer_policy()
    assert policy["schema"] == "v62_single_bound_episode_observer.v1"
    assert policy["scientific_worker_limit"] == 6 and policy["only_one_independent_observer"] is True
    assert policy["signals_policy"] == signals
    assert policy["other_processes_signaled"] is False
