"""Necessary CPU tests: bounded stops, actual sender, identity and observer IO."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

import finqa_v58_observer as observer

SCRIPTS = Path(__file__).resolve().parents[1]/"scripts"


def _target(tmp_path, tail):
    source = "\n".join(("import os, signal, time", "from finqa_v58_signals import install",
        f"monitor=install({str(tmp_path)!r}, role='cpu_test')", tail))
    child = subprocess.Popen([sys.executable, "-u", "-c", source],
        env=dict(os.environ, PYTHONPATH=str(SCRIPTS)), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, start_new_session=True)
    assert child.stdout.readline().strip() == "READY"
    return child


def test_kernel_receipt_precedes_enrichment_and_preserves_sender(tmp_path):
    child = _target(tmp_path, "\n".join((
        "stopped=[]", "signal.signal(signal.SIGTERM, lambda number, frame: stopped.append(number))",
        "print('READY', flush=True)", "while not stopped: time.sleep(0.01)",
        "time.sleep(0.15)", "print(stopped[0], flush=True)",
    )))
    os.kill(child.pid, signal.SIGTERM)
    stdout, stderr = child.communicate(timeout=5)
    assert child.returncode == 0, stderr
    assert str(signal.SIGTERM) in stdout
    rows = [json.loads(line) for line in (tmp_path/"received.jsonl").read_text().splitlines()]
    receipt = next(row for row in rows if row["schema"] == "v58_received_signal_kernel_receipt.v1")
    detail = next(row for row in rows if row["schema"] == "v58_received_signal_identity_enrichment.v1")
    assert receipt["si_pid"] == os.getpid() and receipt["si_uid"] == os.getuid() and receipt["si_code"] == 0
    assert rows.index(receipt) < rows.index(detail)
    assert detail["kernel_receipt_fsynced_before_proc_reads"] is True
    identity = detail["sender_parent_chain"]["processes"][0]
    assert identity["pid"] == os.getpid() and identity["identity_consistent"] is True
    assert identity["ruid"] == os.getuid() and identity["euid"] == os.geteuid()
    assert len(detail["sender_parent_chain"]["processes"]) <= 4


@pytest.mark.parametrize("failure", ["slow", "error"])
def test_bad_storage_cannot_delay_default_term(tmp_path, failure):
    action = "time.sleep(2)" if failure == "slow" else "raise OSError('test storage unavailable')"
    child = _target(tmp_path, "\n".join((
        "original=monitor.log.append", "def bad(record, **kwargs):",
        "    if record['schema'] == 'v58_received_signal_kernel_receipt.v1':",
        "        "+action, "    return original(record, **kwargs)",
        "monitor.log.append=bad", "print('READY', flush=True)",
        "while True: time.sleep(0.01)",
    )))
    started = time.monotonic()
    os.kill(child.pid, signal.SIGTERM)
    child.communicate(timeout=1)
    assert child.returncode == -signal.SIGTERM
    assert time.monotonic()-started < 0.8


def test_default_int_still_raises_keyboard_interrupt(tmp_path):
    child = _target(tmp_path, "print('READY', flush=True)\ntry:\n    time.sleep(5)\nexcept KeyboardInterrupt:\n    raise SystemExit(17)")
    os.kill(child.pid, signal.SIGINT)
    child.communicate(timeout=2)
    assert child.returncode == 17


def test_identity_birth_race_discards_metadata(tmp_path, monkeypatch):
    states = iter([dict(pid=99, comm="test", state="S", ppid=1, birth="11"),
                   dict(pid=99, comm="test", state="S", ppid=1, birth="12")])
    monkeypatch.setattr(observer, "_stat", lambda *_: next(states))
    result = observer.process_identity(99, proc_root=tmp_path)
    assert result["status"] == "IDENTITY_CHANGED_DURING_READ"
    assert result["identity_consistent"] is False and result["metadata_discarded"] is True


def test_rotating_log_has_total_file_not_backup_bound(tmp_path):
    log = observer.RotatingJSONLog(tmp_path/"events.jsonl", max_bytes=100, total_files=4)
    for index in range(20):
        log.append(dict(index=index, content="x"*45))
    files = list(tmp_path.iterdir())
    assert len(files) == 4 and sum(path.stat().st_size for path in files) <= 400
    assert not (tmp_path/"events.jsonl.4").exists()


def test_observer_does_not_treat_unreadable_journal_as_settled(tmp_path):
    monitor = observer.Observer(tmp_path, tmp_path/"science")
    path = tmp_path/"supervisor/launch/record.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(dict(pid=999999999, birth="1")))
    (tmp_path/"STOP").touch()
    monitor.discover()
    assert monitor.discovery_ok is False
    assert monitor.poll_experiment() == []
    assert monitor.terminal() is True
    # Root marker alone cannot turn a missing current journal into a claim
    # that every current scientific process has been safely observed exited.


def test_observer_ignores_prepared_old_pids_and_closes_on_current_terminal(tmp_path):
    prepared = tmp_path/"prepared/record.json"
    prepared.parent.mkdir()
    prepared.write_text(json.dumps(dict(old_pid=os.getpid(), old_birth="unrelated")))
    (tmp_path/"STOP").touch()
    monitor = observer.Observer(tmp_path, tmp_path/"science")
    status = monitor.run()
    assert status["status"] == "STOPPED" and status["tracked_identities"] == []
    assert status["scientific_processes_signaled"] is False
    launch = json.loads((tmp_path/"observer/launch/record.json").read_text())
    heartbeat = json.loads((tmp_path/"observer/queue/status.json").read_text())
    assert launch["pid"] == os.getpid() and launch["birth"]
    assert heartbeat["status"] == "STOPPED"
