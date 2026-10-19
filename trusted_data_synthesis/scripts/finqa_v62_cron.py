"""One account cron: passive initial handoff, then quiet recovery ticks.

No crontab is changed merely by importing this module. Raw old crontabs are
backed up only in private /tmp files, never copied into the repository or logs.
Unrelated lines are never printed. Root can still kill cron or any child.
"""
from __future__ import annotations

import argparse
import contextlib
import errno
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
sys.dont_write_bytecode = True
import tempfile
import time

from finqa_v62_binding import (MASTER_ROOT, PYTHON, SCIENCE_ROOT, SOURCE_CONTROL_ROOT,
    SOURCE_CONTROL_PROTOCOL_ID, SCIENTIFIC_PROTOCOL_ID, checked_record, digest, load_v59_module)

OWNER_UID = 1004
MARKER = "# FINQA_V62_ACCOUNT_WATCHDOG_01_UID1004"
TRANSIENT_ERRNOS = frozenset((errno.EAGAIN, errno.ENOMEM, errno.ENOSPC, errno.EDQUOT,
                             errno.EIO, errno.ESTALE, errno.ETIMEDOUT))


class CronError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class StopRequested(BaseException):
    pass


def require(condition, code):
    if not condition:
        raise CronError(code)


def cron_policy():
    return dict(schema="v62_single_account_cron_envelope.v1", owner_uid=OWNER_UID,
        root=str(MASTER_ROOT), schedule="* * * * *", marker=MARKER,
        command=[str(PYTHON), "-u", str(MASTER_ROOT/"implementation/finqa_v62_cron.py"),
                 "tick", "--root", str(MASTER_ROOT)],
        other_crontab_lines_preserved=True, other_crontab_content_logged=False,
        backup_location="private mkdtemp under /tmp, never the repository", backup_mode="0600",
        fresh_read_before_change=True, second_read_requires_identical_bytes=True,
        post_change_exact_verification=True, unrelated_writers_have_no_atomic_CAS_guarantee=True,
        tick_single_process_flock="cron/envelope.lock", tick_stdout_stderr_suppressed=True,
        bounded_status_path="cron/status.json", fixed_rotating_signal_directory="cron/signals",
        signal_log_max_bytes=64*1024**2, signal_log_total_files=4,
        initial_handoff_mode="passive_all_or_none_until_fixed_source04_boundary",
        initial_handoff_poll_seconds=0.25, initial_handoff_holds_envelope_across_polls=True,
        next_cron_invocation_skips_while_passive_guard_alive=True,
        SIGKILL_in_clear_waiting_state_may_reobserve_next_minute=True,
        interrupted_handoff_side_effects_read_only_reconcile_or_block=True,
        after_handoff_one_watchdog_tick_per_cron=True,
        owner_TERM_and_any_INT_persist_master_and_bound_episode_STOP=True,
        implementation_or_binding_failure_permanently_fences_automatic_recovery=True,
        transient_io_errnos=sorted(TRANSIENT_ERRNOS),
        hard_cron_failure_does_not_signal_or_stop_current_science=True,
        registered_pending_successor_also_fenced=True,
        envelope_process_signals_sent=False, separate_handoff_only_fixed_controller_TERM=True,
        current_tick_parent_and_grandparent_public_identity_recorded=True,
        no_argv_environment_credentials_or_history_read=True,
        root_can_kill_cron_and_SIGKILL_cannot_be_blocked=True,
        actual_automatic_tick_required_before_claiming_cron_activation=True)


def basic_root(root):
    value = Path(root)
    require(not value.is_symlink() and value.resolve() == MASTER_ROOT.resolve(), "UNREGISTERED_MASTER_ROOT")
    require(os.getuid() == os.geteuid() == OWNER_UID, "WRONG_ACCOUNT_UID")
    require(value.is_dir(), "MASTER_NOT_PREPARED")
    return value.resolve()


def checked_master(root):
    root = basic_root(root)
    registration = importlib.import_module("finqa_v62_registration")
    protocol = registration.checked_master_protocol(root)
    prepared = checked_record(root/"prepared/record.json")
    require(prepared["protocol_id"] == protocol["id"]
            and prepared["initial_episode"] == dict(root=str(SOURCE_CONTROL_ROOT),
                protocol_id=SOURCE_CONTROL_PROTOCOL_ID), "PREPARATION_BINDING_CHANGED")
    return protocol, prepared


def entry_admission(root):
    """Small pre-install source fence; watchdog performs its full own admission."""
    root = basic_root(root)
    protocol = checked_record(root/"protocol/record.json")
    manifest_path = root/"implementation/record.json"
    manifest_raw = manifest_path.read_bytes()
    manifest = checked_record(manifest_path)
    reference = protocol["implementation"]
    source = root/"implementation/finqa_v62_cron.py"
    require(protocol["root"] == str(root) and protocol["scientific_root"] == str(SCIENCE_ROOT)
            and Path(reference["path"]).resolve() == manifest_path
            and reference["id"] == manifest["id"]
            and reference["sha256"] == hashlib.sha256(manifest_raw).hexdigest()
            and Path(__file__).resolve() == source
            and hashlib.sha256(source.read_bytes()).hexdigest() == manifest["files"][source.name],
            "FROZEN_CRON_ENTRY_CHANGED")
    return protocol


def line(root=MASTER_ROOT):
    command = [str(PYTHON), "-u", str(Path(root)/"implementation/finqa_v62_cron.py"),
               "tick", "--root", str(Path(root))]
    return ("* * * * * "+" ".join(shlex.quote(value) for value in command)+" "+MARKER).encode()


def read_crontab(runner=None):
    result = (runner or subprocess.run)(["crontab", "-l"], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False)
    if result.returncode == 0:
        return dict(raw=result.stdout, existed=True)
    if result.returncode == 1 and b"no crontab" in result.stderr.lower():
        return dict(raw=b"", existed=False)
    raise CronError("CRONTAB_READ_FAILED")


def split_own(raw, target):
    kept, count = [], 0
    for row in raw.splitlines(keepends=True):
        content = row.rstrip(b"\r\n")
        if content == target:
            count += 1
        else:
            require(MARKER.encode() not in content, "TASK_MARKER_CONFLICT")
            kept.append(row)
    require(count <= 1, "DUPLICATE_TASK_LINE")
    return b"".join(kept), count


def backup(snapshot):
    directory = Path(tempfile.mkdtemp(prefix="finqa-v62-cron-uid1004-", dir="/tmp"))
    path = directory/"crontab.before"
    fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(snapshot["raw"])
        stream.flush()
        os.fsync(stream.fileno())
    return dict(path=str(path), mode="0600", existed=snapshot["existed"],
        bytes=len(snapshot["raw"]), sha256=hashlib.sha256(snapshot["raw"]).hexdigest(),
        outside_repository=True)


def _atomic(path, value, *, immutable=False):
    path = Path(path)
    require(not path.is_symlink(), "METADATA_SYMLINK_REJECTED")
    if immutable and path.exists():
        return
    body = {key: item for key, item in value.items() if key != "id"}
    value = {**body, "id": digest(body)}
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".cron-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        if immutable:
            try:
                os.link(temporary, path)
            except FileExistsError:
                require(path.is_file() and not path.is_symlink(), "STOP_TARGET_CHANGED")
        else:
            os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY|os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def change_crontab(root, action, *, runner=None):
    root = basic_root(root)
    protocol, _ = checked_master(root)
    require(action in ("install", "remove"), "UNKNOWN_CRON_MUTATION")
    if action == "install":
        require(not any((root/path).exists() for path in
            ("STOP", "control/stop_requested/record.json", "terminal/record.json")), "MASTER_ALREADY_STOPPED")
    directory = root/"cron"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory/"crontab_change.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        before = read_crontab(runner)
        other, count = split_own(before["raw"], line(root))
        if (action == "install" and count == 1) or (action == "remove" and count == 0):
            return dict(status="ALREADY_INSTALLED" if count else "ALREADY_ABSENT", changed=False)
        require(not other or other.endswith(b"\n"), "EXISTING_CRONTAB_LACKS_FINAL_NEWLINE")
        target = other+line(root)+b"\n" if action == "install" else other
        saved = backup(before)
        intent = dict(schema="v62_exact_crontab_mutation.v1", status="PREPARED_NO_CRONTAB_CHANGE_YET",
            protocol_id=protocol["id"], owner_uid=OWNER_UID, action=action, at_epoch=time.time(),
            original_backup=saved, exact_task_line=line(root).decode(), other_content_recorded=False)
        _atomic(directory/"installation_status.json", intent)
        fresh = read_crontab(runner)
        require(fresh == before, "CRONTAB_CHANGED_BEFORE_INSTALL")
        result = (runner or subprocess.run)(["crontab", "-"], input=target,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        require(result.returncode == 0, "CRONTAB_WRITE_FAILED")
        _atomic(directory/"installation_status.json", {**intent, "status": "CRONTAB_WRITE_RETURNED_NOT_YET_VERIFIED"})
        after = read_crontab(runner)
        remaining, installed = split_own(after["raw"], line(root))
        require(after["raw"] == target and remaining == other and installed == (1 if action == "install" else 0),
                "CRONTAB_POST_INSTALL_MISMATCH_NO_AUTOMATIC_ROLLBACK")
        record = dict(schema="v62_exact_crontab_mutation.v1", status="INSTALLED" if installed else "REMOVED",
            protocol_id=protocol["id"], owner_uid=OWNER_UID, action=action, at_epoch=time.time(),
            changed=True, original_backup=saved, exact_task_line=line(root).decode(),
            unrelated_lines_preserved=True, concurrent_edit_guard="second fresh read plus post-write verification",
            atomic_CAS_with_unrelated_crontab_writers=False, other_content_recorded=False)
        _atomic(directory/"installation_status.json", record)
        return record


def check(root, *, runner=None):
    root = basic_root(root)
    protocol, _ = checked_master(root)
    snapshot = read_crontab(runner)
    _, count = split_own(snapshot["raw"], line(root))
    return dict(status="INSTALLED" if count else "ABSENT", protocol_id=protocol["id"],
        owner_uid=OWNER_UID, exact_task_line_present=count == 1,
        master_stopped=any((root/p).exists() for p in ("STOP", "terminal/record.json")),
        actual_automatic_tick_claimed=False, crontab_modified=False)


def _episode(root, reference, protocol_id):
    path = Path(reference["root"])
    require(not path.is_symlink(), "EPISODE_SYMLINK_REJECTED")
    path = path.resolve()
    initial = path == SOURCE_CONTROL_ROOT.resolve()
    require(initial or (path.parent == root/"episodes" and re.fullmatch(r"episode[0-9]{6}", path.name)),
            "EPISODE_OUTSIDE_REGISTERED_NAMESPACE")
    protocol = checked_record(path/"protocol/record.json")
    require(protocol["id"] == reference["protocol_id"]
            and protocol["scientific_root"] == str(SCIENCE_ROOT)
            and protocol["scientific_protocol_id"] == SCIENTIFIC_PROTOCOL_ID
            and (protocol["id"] == SOURCE_CONTROL_PROTOCOL_ID if initial
                 else protocol["master_protocol_id"] == protocol_id), "EPISODE_PROTOCOL_BINDING_CHANGED")
    return path


def request_stop(root, *, reason="EXPLICIT_STOP_COMMAND", received_signal=None):
    root = basic_root(root)
    requested = dict(schema="v62_cron_owner_stop_fence.v1", at_epoch=time.time(),
        reason=reason, received_signal=received_signal, owner_uid=OWNER_UID,
        automatic_recovery_allowed=False, scientific_exit_claimed=False,
        process_signals_sent=False, new_user_authorization_required=True)
    # The fixed master fence is first, even if a damaged state later prevents
    # identifying the current episode. Existing stop/failure evidence is kept.
    _atomic(root/"STOP", requested, immutable=True)
    _atomic(root/"terminal/record.json", {**requested, "status": "STOPPED_NO_AUTO_RECOVERY"}, immutable=True)
    protocol = checked_record(root/"protocol/record.json")
    state_path = root/"state.json"
    if state_path.exists():
        state = checked_record(state_path)
        require(state["protocol_id"] == protocol["id"], "CURRENT_STATE_PROTOCOL_CHANGED")
        candidates = [state["current_episode"]]
        pending = state.get("pending_request")
        if pending:
            directory = Path(pending["directory"]).resolve()
            require(directory == root/"requests"/pending["request_id"]
                    and re.fullmatch(r"request[0-9]{6}", pending["request_id"]), "PENDING_REQUEST_PATH_CHANGED")
            receipt_path = directory/"registration/record.json"
            if receipt_path.exists():
                receipt = checked_record(receipt_path)
                require(receipt["request_id"] == pending["request_id"]
                        and receipt["predecessor_root"] == state["current_episode"]["root"],
                        "PENDING_SUCCESSOR_BINDING_CHANGED")
                candidates.append(dict(root=receipt["episode_root"], protocol_id=receipt["control_protocol_id"]))
    else:
        prepared = checked_record(root/"prepared/record.json")
        require(prepared["protocol_id"] == protocol["id"], "INITIAL_PREPARATION_CHANGED")
        candidates = [prepared["initial_episode"]]
    targets = []
    for reference in candidates:
        target = _episode(root, reference, protocol["id"])
        _atomic(target/"STOP", {**requested, "master_protocol_id": protocol["id"],
            "episode_protocol_id": reference["protocol_id"]}, immutable=True)
        targets.append(str(target))
    result = dict(requested, status="STOP_REQUESTED_MASTER_AND_BOUND_EPISODES_FENCED",
                  master_protocol_id=protocol["id"], episode_stop_targets=targets)
    _atomic(root/"cron/stop_status.json", result)
    return result


def _process(pid):
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
        fields = raw.rsplit(")", 1)[1].split()
        return dict(pid=int(pid), birth=fields[19], ppid=int(fields[1]),
                    comm=raw.split("(", 1)[1].rsplit(")", 1)[0][:256])
    except (OSError, ValueError, IndexError) as error:
        return dict(pid=int(pid), birth=None, comm=None, ppid=None,
                    observation_error_type=type(error).__name__)


def invocation_identity():
    own = _process(os.getpid())
    parent = _process(own["ppid"]) if own.get("ppid") else None
    grandparent = _process(parent["ppid"]) if parent and parent.get("ppid") else None
    return dict(pid=os.getpid(), birth=own.get("birth"), uid=os.getuid(), euid=os.geteuid(),
        observed_epoch=time.time(), parent=parent, grandparent=grandparent,
        ancestor_comm_indicates_cron=any(row and (row.get("comm") or "").lower() == "cron"
                                        for row in (parent, grandparent)),
        automatic_activation_not_claimed_from_line_installation=True,
        argv_environment_or_unrelated_processes_read=False)


def failure_outcome(root, error):
    fields = dict(error_type=type(error).__name__, error_code=getattr(error, "code", None),
                  actual_errno=getattr(error, "errno", None))
    if isinstance(error, OSError) and error.errno in TRANSIENT_ERRNOS:
        return dict(status="WAITING_FOR_TRANSIENT_CRON_IO", **fields)
    fence = dict(schema="v62_cron_permanent_implementation_failure.v1",
        status="BLOCKED_CRON_IMPLEMENTATION_OR_BINDING", reason="IMPLEMENTATION_FAILURE",
        at_epoch=time.time(), automatic_recovery_allowed=False,
        new_user_authorization_required=True, current_scientific_episode_STOP_written=False,
        process_signals_sent=False, **fields)
    try:
        _atomic(Path(root)/"terminal/record.json", fence, immutable=True)
    except Exception as failure:
        return dict(status="HARD_FAILURE_TERMINAL_WRITE_UNCONFIRMED",
            terminal_write_error_type=type(failure).__name__,
            terminal_write_errno=getattr(failure, "errno", None), **fields)
    return dict(status="TICK_FAILED_PERMANENTLY_FENCED", **fields)


def _run_handoff(root, envelope, protocol, origin, started, *, handoff_module=None, sleep=None):
    handoff = handoff_module or importlib.import_module("finqa_v62_handoff")
    pause = sleep or time.sleep
    heartbeat = 0.0
    session = {}
    while True:
        if (root/"STOP").exists() or (root/"control/stop_requested/record.json").exists():
            return dict(status="STOPPED_NO_AUTO_RECOVERY")
        if (root/"terminal/record.json").exists():
            return dict(status=checked_record(root/"terminal/record.json")["status"])
        result = handoff.advance_handoff(root, envelope=envelope, session=session)
        if result["status"] == "READY_FOR_WATCHDOG" or not result["status"].startswith("WAITING_"):
            return result
        if time.time() - heartbeat >= 15:
            heartbeat = time.time()
            _atomic(root/"cron/status.json", dict(schema="v62_cron_tick_heartbeat.v1",
                status="PASSIVE_HANDOFF_RUNNING", handoff_status=result["status"],
                protocol_id=protocol["id"], invocation=origin, started_epoch=started,
                heartbeat_epoch=heartbeat, partial_GPU_leases_retained=False,
                current_scientific_workers_signaled=False))
        pause(0.25)


def tick_once(root=MASTER_ROOT, *, backend=None, watchdog_module=None, signal_installer=None,
              handoff_module=None, sleep=None):
    root = basic_root(root)
    directory = root/"cron"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory/"envelope.lock").open("a") as envelope:
        try:
            fcntl.flock(envelope, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return dict(status="SKIP_ENVELOPE_ALREADY_RUNNING")
        origin, started = invocation_identity(), time.time()
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
        stopped = {}

        def owner_stop(number, _frame):
            try:
                stopped.update(request_stop(root, reason="CRON_MAIN_HANDLER_STOP", received_signal=number))
            except Exception as error:
                stopped.update(status="STOP_REQUESTED_FENCE_PARTIAL_FAILURE",
                    error_type=type(error).__name__, error_code=getattr(error, "code", None),
                    master_STOP_observed=(root/"STOP").exists())
            raise StopRequested()

        previous_handlers = {number: signal.signal(number, owner_stop)
                             for number in (signal.SIGTERM, signal.SIGINT)}
        monitor, outcome = None, None
        try:
            # Binding/installer imports are pure CPU. The fixed directory is
            # single-writer under envelope.lock and uses original 4-file rotation.
            installer = signal_installer or load_v59_module("finqa_v59_signals").install
            monitor = installer(directory/"signals", role="cron_tick",
                context=dict(automatic_watchdog_root=str(root), owner_uid=OWNER_UID))
            protocol = entry_admission(root)
            _atomic(directory/"status.json", dict(schema="v62_cron_tick_heartbeat.v1", status="RUNNING",
                protocol_id=protocol["id"], invocation=origin, started_epoch=started,
                heartbeat_epoch=time.time(), actual_cron_line_execution_not_inferred=True))
            handoff = _run_handoff(root, envelope, protocol, origin, started,
                handoff_module=handoff_module, sleep=sleep)
            if handoff["status"] == "READY_FOR_WATCHDOG":
                watchdog = watchdog_module or importlib.import_module("finqa_v62_watchdog")
                backend = backend or importlib.import_module("finqa_v62_backend")
                result = watchdog.tick(root, backend=backend)
                outcome = dict(status="TICK_COMPLETED", watchdog_status=result["status"],
                    watchdog_record_id=result.get("id"), protocol_id=protocol["id"])
            else:
                outcome = dict(status="HANDOFF_"+handoff["status"], handoff_status=handoff["status"],
                    handoff_record_id=handoff.get("id"), protocol_id=protocol["id"])
        except StopRequested:
            outcome = dict(stopped)
        except Exception as error:
            # Never emit exception messages or callback output to cron mail.
            # Preserve the failed guard admission visibly in one bounded record.
            outcome = failure_outcome(root, error)
        finally:
            if monitor is not None:
                try:
                    monitor.close()
                except StopRequested:
                    outcome = dict(stopped)
            for number, handler in previous_handlers.items():
                signal.signal(number, handler)
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        outcome = {**(outcome or dict(status="TICK_FAILED_SAFE")),
            "schema": "v62_cron_tick_heartbeat.v1", "invocation": origin,
            "started_epoch": started, "heartbeat_epoch": time.time(), "finished_epoch": time.time(),
            "other_crontab_content_recorded": False, "process_signals_sent_by_envelope": False,
            "handoff_side_effects_separately_recorded": True}
        _atomic(directory/"status.json", outcome)
        return outcome


@contextlib.contextmanager
def quiet_standard_streams():
    """Suppress native as well as Python output; cron must not send private mail."""
    saved = (os.dup(1), os.dup(2))
    null = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(null, 1)
        os.dup2(null, 2)
        yield
    finally:
        os.dup2(saved[0], 1)
        os.dup2(saved[1], 2)
        os.close(saved[0])
        os.close(saved[1])
        os.close(null)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("tick", "install", "check", "remove", "stop"))
    parser.add_argument("--root", type=Path, default=MASTER_ROOT)
    args = parser.parse_args()
    if args.action == "tick":
        with quiet_standard_streams():
            try:
                result = tick_once(args.root)
                return 2 if result["status"] in ("TICK_FAILED_PERMANENTLY_FENCED",
                    "HARD_FAILURE_TERMINAL_WRITE_UNCONFIRMED", "STOP_REQUESTED_FENCE_PARTIAL_FAILURE") else 0
            except Exception as error:
                # This final bounded record covers e.g. installer/lock IO failure.
                # A storage failure may also prevent recording; no science is
                # blindly retried and no private exception text is printed.
                try:
                    root = basic_root(args.root)
                    failure = failure_outcome(root, error)
                    _atomic(root/"cron/status.json", dict(schema="v62_cron_tick_heartbeat.v1",
                        heartbeat_epoch=time.time(), invocation=invocation_identity(), **failure))
                except Exception:
                    pass
                return 2
    try:
        if args.action in ("install", "remove"):
            result = change_crontab(args.root, args.action)
        elif args.action == "check":
            result = check(args.root)
        else:
            result = request_stop(args.root)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps(dict(status="REQUEST_FAILED", error_type=type(error).__name__,
                              error_code=getattr(error, "code", None)), sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
