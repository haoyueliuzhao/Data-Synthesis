"""CPU-only sender policy simulation plus actual owner-child stop tests."""
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

import finqa_v59_signals as observed

SCRIPTS = Path(__file__).resolve().parents[1]/"scripts"


@pytest.mark.parametrize("number,pid,uid,code,filtered", [
    (signal.SIGTERM, 42, 0, 0, True),
    (signal.SIGTERM, 42, 1005, 0, True),
    (signal.SIGTERM, 42, 1004, 0, False),
    (signal.SIGINT, 42, 0, 0, False),
    (signal.SIGINT, 42, 1004, 0, False),
    (signal.SIGTERM, 42, 0, -1, False),
    (signal.SIGTERM, 42, 0, -6, False),
    (signal.SIGTERM, 42, 0, 128, False),
    (signal.SIGTERM, 0, 0, 0, False),
    (signal.SIGTERM, -1, 0, 0, False),
    (signal.SIGTERM, 42, -1, 0, False),
    (signal.SIGTERM, 42, None, 0, False),
])
def test_exact_kernel_policy(number, pid, uid, code, filtered):
    decision = observed.signal_decision(number, pid, uid, code)
    assert decision["filtered"] is filtered
    assert decision["dispatch_original_stop"] is (not filtered)


def _synthetic_monitor(full=False):
    monitor = object.__new__(observed.SignalObserver)
    monitor.time, monitor.threading, monitor.queue = time, threading, queue
    monitor.role, monitor.context, monitor.receipt_queue_drops = "synthetic_cpu_test", {"synthetic": True}, 0
    monitor.records, monitor.pending = queue.Queue(maxsize=1), queue.SimpleQueue()
    if full:
        monitor.records.put_nowait("already_full")
    return monitor


@pytest.mark.parametrize("full", [False, True])
def test_synthetic_foreign_term_keeps_kernel_receipt_and_never_dispatches(full, monkeypatch):
    monitor = _synthetic_monitor(full)
    monkeypatch.setattr(os, "kill", lambda *_: pytest.fail("filtered TERM must not wake main stop handler"))
    info = SimpleNamespace(si_signo=signal.SIGTERM, si_pid=4242, si_uid=0, si_code=0)
    decision = monitor._accept_siginfo(info)
    assert decision["filtered"] is True and monitor.pending.empty()
    if full:
        assert monitor.receipt_queue_drops == 1
    else:
        receipt, _, enrich = monitor.records.get_nowait()
        assert (receipt["si_pid"], receipt["si_uid"], receipt["si_code"], receipt["signal"]) == (4242, 0, 0, signal.SIGTERM)
        assert receipt["decision"] == decision and enrich is True


@pytest.mark.parametrize("number", [signal.SIGTERM, signal.SIGINT])
def test_real_owner_signal_reaches_current_main_handler(tmp_path, number):
    source = "\n".join((
        "import signal, threading, time", "from finqa_v59_signals import install",
        f"monitor=install({str(tmp_path)!r}, role='actual_owner_cpu_test')",
        "stopped=[]", "def handler(number, frame): stopped.append((number, threading.current_thread().name))",
        "signal.signal(signal.SIGTERM, handler)", "signal.signal(signal.SIGINT, handler)",
        "print('READY', flush=True)", "while not stopped: time.sleep(0.01)",
        "time.sleep(0.1)", "print(stopped, flush=True)",
    ))
    child = subprocess.Popen([sys.executable, "-u", "-c", source],
        env=dict(os.environ, PYTHONPATH=str(SCRIPTS)), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, start_new_session=True)
    assert child.stdout.readline().strip() == "READY"
    os.kill(child.pid, number)
    stdout, stderr = child.communicate(timeout=5)
    assert child.returncode == 0, stderr
    assert "MainThread" in stdout
    records = [json.loads(line) for line in (tmp_path/"received.jsonl").read_text().splitlines()]
    row = next(row for row in records if row["schema"] == "v59_received_signal_kernel_receipt.v1")
    assert row["si_pid"] == os.getpid() and row["si_uid"] == os.getuid() == 1004
    assert row["decision"]["action"] == "DISPATCH_ORIGINAL_STOP"


def test_owner_binding_fails_closed_before_thread_start(monkeypatch, tmp_path):
    monkeypatch.setattr(os, "getuid", lambda: 0)
    with pytest.raises(RuntimeError, match="UID1004"):
        observed.SignalObserver(tmp_path, role="test")
