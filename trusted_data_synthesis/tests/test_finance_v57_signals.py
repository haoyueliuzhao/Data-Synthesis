"""CPU process tests for kernel-provided signal provenance and stop semantics."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def start_target(tmp_path, behavior):
    source = "\n".join((
        "import os, signal, sys, time",
        "from finqa_v57_signals import install",
        f"observer = install({str(tmp_path)!r}, role='cpu_test', context={{'case': 'sender_identity'}})",
        "import threading",
        behavior,
    ))
    environment = dict(os.environ, PYTHONPATH=str(SCRIPTS))
    process = subprocess.Popen([sys.executable, "-u", "-c", source], env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    assert process.stdout.readline().strip() == "READY"
    return process


def send_from_child(target, number):
    # Keep the sender alive briefly so /proc identity can be observed, rather
    # than asserting that an already-exited sender magically remains readable.
    source = ("import os, signal, sys, time; print(os.getpid(), flush=True); "
              "os.kill(int(sys.argv[1]), int(sys.argv[2])); time.sleep(0.5)")
    sender = subprocess.Popen([sys.executable, "-u", "-c", source, str(target.pid), str(number)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    pid = int(sender.stdout.readline().strip())
    return sender, pid


def received(tmp_path):
    return [json.loads(line) for line in (tmp_path / "received.jsonl").read_text().splitlines()
            if json.loads(line)["schema"] == "v57_actual_received_signal.v1"]


@pytest.mark.parametrize("number", [signal.SIGTERM, signal.SIGINT])
def test_actual_sender_and_current_handler_run_in_main_thread(tmp_path, number):
    target = start_target(tmp_path, "\n".join((
        "def stopped(number, frame):",
        "    print(f'STOPPED {number} {threading.current_thread().name}', flush=True)",
        "    raise SystemExit(0)",
        "signal.signal(signal.SIGTERM, stopped)",
        "signal.signal(signal.SIGINT, stopped)",
        "print('READY', flush=True)",
        "while True: time.sleep(0.05)",
    )))
    sender, sender_pid = send_from_child(target, number)
    stdout, stderr = target.communicate(timeout=5)
    sender.communicate(timeout=5)
    assert target.returncode == 0, stderr
    assert f"STOPPED {number} MainThread" in stdout
    row, = received(tmp_path)
    assert row["si_pid"] == sender_pid and row["si_uid"] == os.getuid()
    assert row["si_code"] == 0 and row["signal"] == number
    assert row["sender"]["ppid"] == os.getpid()
    assert row["sender"]["executable"] and row["sender"]["birth"]
    assert row["sender"]["cgroup"] is not None
    assert "environ" not in row and "command_line" not in row


def test_default_term_preserves_negative_signal_exit_status(tmp_path):
    target = start_target(tmp_path, "print('READY', flush=True)\nwhile True: time.sleep(0.05)")
    sender, sender_pid = send_from_child(target, signal.SIGTERM)
    target.communicate(timeout=5)
    sender.communicate(timeout=5)
    assert target.returncode == -signal.SIGTERM
    assert received(tmp_path)[0]["si_pid"] == sender_pid


def test_default_int_preserves_keyboard_interrupt(tmp_path):
    target = start_target(tmp_path, "\n".join((
        "print('READY', flush=True)",
        "try:",
        "    while True: time.sleep(0.05)",
        "except KeyboardInterrupt:",
        "    print('ORIGINAL_KEYBOARD_INTERRUPT', flush=True)",
        "    raise SystemExit(17)",
    )))
    sender, _ = send_from_child(target, signal.SIGINT)
    stdout, _ = target.communicate(timeout=5)
    sender.communicate(timeout=5)
    assert target.returncode == 17 and "ORIGINAL_KEYBOARD_INTERRUPT" in stdout


def test_telemetry_io_failure_does_not_suppress_stop(tmp_path):
    target = start_target(tmp_path, "\n".join((
        "def stopped(number, frame): raise SystemExit(19)",
        "signal.signal(signal.SIGTERM, stopped)",
        "os.close(observer.fd)",
        "print('READY', flush=True)",
        "while True: time.sleep(0.05)",
    )))
    sender, _ = send_from_child(target, signal.SIGTERM)
    _, stderr = target.communicate(timeout=5)
    sender.communicate(timeout=5)
    assert target.returncode == 19
    assert "telemetry unavailable" in stderr


@pytest.mark.parametrize("mode,entry,arguments", [
    ("science", "finqa_v56_worker.py", ["--seed", "137", "--stage", "shard01", "--gpu-index", "2"]),
    ("evaluation", "finqa_v54_evaluation.py", ["worker", "--job", "dummy", "--gpu", "2"]),
])
def test_wrapper_dispatches_original_entry_after_observer(tmp_path, mode, entry, arguments):
    root = tmp_path / "science"
    implementation = root / "implementation"
    implementation.mkdir(parents=True)
    (implementation / entry).write_text("\n".join((
        "import json, signal, sys",
        "from finqa_v57_signals import _OBSERVER",
        "assert _OBSERVER is not None",
        "assert {signal.SIGTERM, signal.SIGINT} <= signal.pthread_sigmask(signal.SIG_BLOCK, set())",
        "print(json.dumps({'arguments': sys.argv[1:], 'entry': __file__}))",
    )))
    original = [*arguments, "--root", str(root)]
    environment = dict(os.environ, PYTHONPATH=str(SCRIPTS),
                       V57_SIGNAL_LOG_DIR=str(tmp_path / "signals"), V57_CONTROL_ROOT=str(tmp_path / "control"))
    result = subprocess.run([sys.executable, str(SCRIPTS / "finqa_v57_worker.py"), "--mode", mode,
                             *original], env=environment, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["arguments"] == original
    assert payload["entry"] == str(implementation / entry)


def test_missing_sender_identity_is_explicit_unknown():
    from finqa_v57_signals import _sender
    value = _sender(999999999)
    assert value["status"] == "PARTIAL_OR_UNKNOWN"
    assert value["executable"] is None and value["ppid"] is None and value["cgroup"] is None
    assert set(value["read_errors"]) == {"executable", "process_identity", "cgroup"}
