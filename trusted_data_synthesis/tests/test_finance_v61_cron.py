"""No real crontab mutations: an in-memory runner owns every cron command."""
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest

import finqa_v61_cron as cron

SCRIPTS = Path(__file__).resolve().parents[1]/"scripts"


class FakeCron:
    def __init__(self, raw=b"", *, existed=True, replace_on_read=None):
        self.raw, self.existed, self.replace_on_read = raw, existed, replace_on_read or {}
        self.reads, self.writes, self.commands = 0, 0, []

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        if command == ["crontab", "-l"]:
            self.reads += 1
            if self.reads in self.replace_on_read:
                self.raw = self.replace_on_read[self.reads]
            return SimpleNamespace(returncode=0 if self.existed else 1,
                stdout=self.raw, stderr=b"" if self.existed else b"no crontab for test-account\n")
        assert command == ["crontab", "-"]
        self.writes += 1
        self.raw, self.existed = kwargs["input"], True
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(cron, "basic_root", lambda value: Path(value).resolve())
    monkeypatch.setattr(cron, "checked_master", lambda _: ({"id": "registered-test-master"}, {}))
    monkeypatch.setattr(cron, "_run_handoff", lambda *a, **k: {"status": "READY_FOR_WATCHDOG"})
    return tmp_path


def test_install_preserves_other_bytes_and_private_backup(root):
    original = b"MAILTO=synthetic_secret_value\n13 2 * * * /existing/task  --unchanged\n"
    runner = FakeCron(original)
    result = cron.change_crontab(root, "install", runner=runner)
    assert runner.raw == original+cron.line(root)+b"\n"
    assert runner.reads == 3 and runner.writes == 1
    saved = Path(result["original_backup"]["path"])
    assert saved.read_bytes() == original and saved.is_relative_to(Path("/tmp"))
    assert stat.S_IMODE(saved.stat().st_mode) == 0o600
    assert stat.S_IMODE(saved.parent.stat().st_mode) == 0o700
    assert "synthetic_secret_value" not in json.dumps(result)


def test_absent_crontab_installs_only_exact_line(root):
    runner = FakeCron(existed=False)
    result = cron.change_crontab(root, "install", runner=runner)
    assert runner.raw == cron.line(root)+b"\n" and result["status"] == "INSTALLED"


def test_remove_only_exact_task_line_never_uses_remove_all(root):
    before = b"# other private task\n1 1 * * * /other\n"
    after = b"7 7 * * * /another\n"
    runner = FakeCron(before+cron.line(root)+b"\n"+after)
    result = cron.change_crontab(root, "remove", runner=runner)
    assert runner.raw == before+after and result["status"] == "REMOVED"
    assert ["crontab", "-r"] not in runner.commands


def test_second_read_concurrent_change_aborts_without_write(root):
    runner = FakeCron(b"# initial\n", replace_on_read={2: b"# concurrent private change\n"})
    with pytest.raises(cron.CronError, match="CRONTAB_CHANGED_BEFORE_INSTALL"):
        cron.change_crontab(root, "install", runner=runner)
    assert runner.writes == 0 and runner.raw == b"# concurrent private change\n"


def test_post_change_mismatch_never_blindly_rolls_back(root):
    runner = FakeCron(b"# initial\n", replace_on_read={3: b"# newer external change\n"})
    with pytest.raises(cron.CronError, match="POST_INSTALL_MISMATCH"):
        cron.change_crontab(root, "install", runner=runner)
    assert runner.writes == 1 and runner.raw == b"# newer external change\n"


def test_conflicting_marker_fails_without_exposing_contents(root):
    runner = FakeCron(b"* * * * * /unrelated_command "+cron.MARKER.encode()+b"\n")
    with pytest.raises(cron.CronError, match="TASK_MARKER_CONFLICT") as captured:
        cron.change_crontab(root, "install", runner=runner)
    assert runner.writes == 0 and "unrelated_command" not in str(captured.value)


def test_check_and_idempotent_install_do_not_modify_crontab(root, monkeypatch):
    runner = FakeCron(cron.line(root)+b"\n")
    monkeypatch.setattr(cron, "backup", lambda *_: pytest.fail("read-only check must not back up or write"))
    assert cron.check(root, runner=runner)["exact_task_line_present"] is True
    assert cron.change_crontab(root, "install", runner=runner)["status"] == "ALREADY_INSTALLED"
    assert runner.writes == 0


def setup_episodes(root, *, pending=False):
    cron._atomic(root/"protocol/record.json", dict(root=str(root), scientific_root=str(cron.SCIENCE_ROOT)))
    master = cron.checked_record(root/"protocol/record.json")
    current = root/"episodes/episode000001"
    cron._atomic(current/"protocol/record.json", dict(scientific_root=str(cron.SCIENCE_ROOT),
        scientific_protocol_id=cron.SCIENTIFIC_PROTOCOL_ID, master_protocol_id=master["id"]))
    episode = cron.checked_record(current/"protocol/record.json")
    state = dict(protocol_id=master["id"], current_episode=dict(root=str(current), protocol_id=episode["id"]),
                 pending_request=None)
    targets = [current]
    if pending:
        following = root/"episodes/episode000002"
        cron._atomic(following/"protocol/record.json", dict(scientific_root=str(cron.SCIENCE_ROOT),
            scientific_protocol_id=cron.SCIENTIFIC_PROTOCOL_ID, master_protocol_id=master["id"], successor=True))
        new_protocol = cron.checked_record(following/"protocol/record.json")
        directory = root/"requests/request000001"
        state["pending_request"] = dict(directory=str(directory), request_id="request000001")
        cron._atomic(directory/"registration/record.json", dict(request_id="request000001",
            predecessor_root=str(current), episode_root=str(following), control_protocol_id=new_protocol["id"]))
        targets.append(following)
    cron._atomic(root/"state.json", state)
    return master, targets


def test_stop_fences_master_current_and_registered_pending_only(root, monkeypatch):
    _, targets = setup_episodes(root, pending=True)
    monkeypatch.setattr(os, "kill", lambda *_: pytest.fail("STOP must never signal a process"))
    result = cron.request_stop(root)
    assert (root/"STOP").exists() and (root/"terminal/record.json").exists()
    assert set(result["episode_stop_targets"]) == {str(path) for path in targets}
    assert all((path/"STOP").exists() for path in targets)
    saved = (root/"STOP").read_bytes()
    cron.request_stop(root)
    assert (root/"STOP").read_bytes() == saved


def test_bad_episode_reference_keeps_master_fenced_but_does_not_touch_outside(root):
    master, _ = setup_episodes(root)
    outside = root.parent/"unrelated-project"
    cron._atomic(root/"state.json", dict(protocol_id=master["id"],
        current_episode=dict(root=str(outside), protocol_id="untrusted"), pending_request=None))
    with pytest.raises(cron.CronError, match="EPISODE_OUTSIDE"):
        cron.request_stop(root)
    assert (root/"STOP").exists() and not (outside/"STOP").exists()


def test_one_healthy_tick_delegates_once_and_records_only_own_ancestry(root, monkeypatch):
    calls, backend = [], object()
    monkeypatch.setattr(cron, "entry_admission", lambda _: {"id": "master"})
    watchdog = SimpleNamespace(tick=lambda target, *, backend: calls.append((target, backend)) or
                              {"status": "WATCHING_LIVE_EPISODE", "id": "guard-status"})
    installer = lambda *a, **k: SimpleNamespace(close=lambda: None)
    result = cron.tick_once(root, backend=backend, watchdog_module=watchdog, signal_installer=installer)
    assert calls == [(root, backend)] and result["watchdog_status"] == "WATCHING_LIVE_EPISODE"
    assert result["invocation"]["pid"] == os.getpid() and result["invocation"]["birth"]
    assert "parent" in result["invocation"] and "grandparent" in result["invocation"]
    assert not result["invocation"]["argv_environment_or_unrelated_processes_read"]
    assert (root/"cron/status.json").exists()


def test_mock_owner_term_persists_fences_and_aborts_test_tick(root, monkeypatch):
    _, targets = setup_episodes(root)
    monkeypatch.setattr(cron, "entry_admission", lambda _: {"id": "test-master"})
    def tick(*args, **kwargs):
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        pytest.fail("owner handler must abort tick")
    installer = lambda *a, **k: SimpleNamespace(close=lambda: None)
    result = cron.tick_once(root, backend=object(),
        watchdog_module=SimpleNamespace(tick=tick), signal_installer=installer)
    assert result["status"] == "STOP_REQUESTED_MASTER_AND_BOUND_EPISODES_FENCED"
    assert (root/"STOP").exists() and all((path/"STOP").exists() for path in targets)

def test_entry_binding_failure_persistently_fences_auto_but_not_current_science(root, monkeypatch):
    _, targets = setup_episodes(root)
    monkeypatch.setattr(cron, "entry_admission", lambda _: (_ for _ in ()).throw(cron.CronError("FROZEN_CRON_ENTRY_CHANGED")))
    watchdog = SimpleNamespace(tick=lambda *a, **k: pytest.fail("failed entry must not reach watchdog"))
    installer = lambda *a, **k: SimpleNamespace(close=lambda: None)
    result = cron.tick_once(root, backend=object(), watchdog_module=watchdog, signal_installer=installer)
    assert result["status"] == "TICK_FAILED_PERMANENTLY_FENCED"
    fence = cron.checked_record(root/"terminal/record.json")
    assert fence["automatic_recovery_allowed"] is False and fence["new_user_authorization_required"] is True
    assert not (root/"STOP").exists() and not any((path/"STOP").exists() for path in targets)


def test_initial_passive_poll_keeps_one_envelope_and_uses_quarter_second(tmp_path):
    import fcntl
    directory = tmp_path / "cron"
    directory.mkdir()
    calls, sleeps = [], []
    with (directory / "envelope.lock").open("a") as envelope:
        fcntl.flock(envelope, fcntl.LOCK_EX | fcntl.LOCK_NB)
        def advance(root, *, envelope, session):
            calls.append(id(session))
            with (directory / "envelope.lock").open("a") as other:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return dict(status="WAITING_FOR_ACCEPTED_TRAINING_CORE" if len(calls) < 3 else "READY_FOR_WATCHDOG")
        result = cron._run_handoff(tmp_path, envelope, {"id": "test"}, {}, 0,
            handoff_module=SimpleNamespace(advance_handoff=advance), sleep=sleeps.append)
    assert result["status"] == "READY_FOR_WATCHDOG"
    assert sleeps == [0.25, 0.25] and len(set(calls)) == 1


def test_next_minute_cron_skips_while_passive_envelope_held(root):
    import fcntl
    directory = root / "cron"
    directory.mkdir(exist_ok=True)
    with (directory / "envelope.lock").open("a") as envelope:
        fcntl.flock(envelope, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert cron.tick_once(root)["status"] == "SKIP_ENVELOPE_ALREADY_RUNNING"


@pytest.mark.parametrize("state", ["BLOCKED", "NO_HANDOFF_REMAINING_WORK", "COMPLETE_NO_MIGRATION"])
def test_handoff_terminal_never_runs_watchdog(root, monkeypatch, state):
    monkeypatch.setattr(cron, "entry_admission", lambda _: {"id": "test"})
    monkeypatch.setattr(cron, "_run_handoff", lambda *a, **k: {"status": state})
    watchdog = SimpleNamespace(tick=lambda *a, **k: pytest.fail("no successor permitted"))
    installer = lambda *a, **k: SimpleNamespace(close=lambda: None)
    assert cron.tick_once(root, backend=object(), watchdog_module=watchdog,
        signal_installer=installer)["status"] == "HANDOFF_"+state


def test_STOP_during_passive_poll_aborts_before_next_observation(tmp_path):
    directory = tmp_path / "cron"
    directory.mkdir()
    calls = []
    def advance(*a, **k):
        calls.append(1)
        return {"status": "WAITING_FOR_NATURAL_GLOBAL_EMPTY"}
    with (directory / "envelope.lock").open("a") as envelope:
        result = cron._run_handoff(tmp_path, envelope, {"id": "test"}, {}, 0,
            handoff_module=SimpleNamespace(advance_handoff=advance),
            sleep=lambda _: (tmp_path / "STOP").touch())
    assert result["status"] == "STOPPED_NO_AUTO_RECOVERY" and calls == [1]
