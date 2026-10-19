"""One fixed, passive source04 handoff; no worker signal or launch operation.

The new cron must already exist. A complete natural GPU-lease boundary is
acquired all-or-none, then the old recovery duty is fenced before the fixed
controller is stopped. Every external side effect has a write-ahead intent.
An interrupted transaction is reconciled read-only, never replayed blindly.
"""
from __future__ import annotations

import contextlib
import ctypes
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time

from finqa_v61_binding import (MASTER_ROOT, SCIENCE_ROOT, SOURCE_CONTROL_ROOT,
    SOURCE_CONTROL_PROTOCOL_ID, SCIENTIFIC_PROTOCOL_ID, PYTHON, checked_record,
    digest, load_v59_module)

OLD_MASTER = SCIENCE_ROOT / "automatic_control_watchdog_01"
OLD_PROTOCOL_ID = "3348cfe262cfdd12c6e4fb74b5b926d4845dc64301e4d3259df3261494f25b3b"
OWNER_UID = 1004
POLL_SECONDS = 0.25
JOURNAL_MAX_AGE_SECONDS = 20
OLD_MARKER = "# FINQA_V60_ACCOUNT_WATCHDOG_01_UID1004"


class HandoffError(ValueError):
    pass


class HandoffEvidencePending(HandoffError):
    """A known exact receipt is durable; its writer may still enrich identity."""


def require(condition, message):
    if not condition:
        raise HandoffError(message)


def policy():
    return dict(schema="v61_passive_all_or_none_source04_handoff.v1",
        source_root=str(SOURCE_CONTROL_ROOT), source_protocol_id=SOURCE_CONTROL_PROTOCOL_ID,
        old_watchdog_root=str(OLD_MASTER), old_watchdog_protocol_id=OLD_PROTOCOL_ID,
        fixed_controller_attempt=1, passive_poll_seconds=POLL_SECONDS,
        original_GPU_lease_count=8, partial_leases_immediately_released=True,
        GPU_capacity_not_a_CPU_handoff_condition=True,
        core_jobs_all_accepted_before_handoff=True, accepted_winning_attempts_actual_exit_zero=True,
        historical_failure_and_missing_waitpid_exceptions_not_reclassified=True,
        initialization_and_draining_workers_must_be_gone=True,
        old_episode_or_control_identity_change_stops_handoff=True,
        new_account_cron_installed_before_old_recovery_retirement=True,
        old_cron_envelope_locked_during_retirement=True,
        old_watchdog_superseded_terminal_without_source_STOP=True,
        old_cron_exact_line_only_removed=True, unrelated_cron_lines_preserved=True,
        maintenance_signal=15, maintenance_only_fixed_controller=True,
        supervisor_natural_exit_without_signal_required=True,
        allowed_frozen_supervisor_forwarded_controller_TERM_maximum=1,
        forwarded_TERM_requires_primary_receipt_marker_and_sender_birth_evidence=True,
        post_signal_enrichment_not_claimed_as_kernel_birth=True,
        original_controller_explicit_stop_returncode=2,
        pidfd_and_PID_birth_UID_verified=True, scientific_workers_signaled=False,
        signal_sender_PID_birth_UID_and_exact_kernel_receipts_bound=True,
        receiver_observed_while_sender_identity_alive_required=True,
        unknown_signal_dispatch_permanently_blocks=True,
        interrupted_side_effects_reconciled_read_only=True,
        source_or_master_STOP_and_any_INT_always_block=True,
        observer_retirement_deferred_to_original_backend=True,
        science_owner_lock_and_actual_control_exit_before_successor=True,
        all_generation_accepted_or_scientific_finish_started_forbids_handoff=True,
        new_scientific_jobs_or_feedback_added=False)


def _write(path, body, *, immutable=False):
    path = Path(path)
    require(not path.is_symlink(), "HANDOFF_METADATA_SYMLINK")
    body = {k: v for k, v in body.items() if k != "id"}
    value = {**body, "id": digest(body)}
    path.parent.mkdir(parents=True, exist_ok=True)
    if immutable and path.exists():
        require(checked_record(path) == value, "IMMUTABLE_HANDOFF_EVIDENCE_CHANGED")
        return value
    fd, temporary = tempfile.mkstemp(prefix=".handoff-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        if immutable:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()
    return value


def _ref(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    value = checked_record(path)
    return dict(path=str(path), id=value["id"], sha256=hashlib.sha256(raw).hexdigest())


def _read_ref(reference):
    path = Path(reference["path"])
    raw = path.read_bytes()
    value = checked_record(path)
    require(hashlib.sha256(raw).hexdigest() == reference["sha256"]
        and ("id" not in reference or value["id"] == reference["id"]), "HANDOFF_REFERENCE_CHANGED")
    return value


def _identity(pid, birth):
    require(type(pid) is int and pid > 0 and isinstance(birth, str) and birth,
            "HANDOFF_IDENTITY_INCOMPLETE")
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return dict(pid=pid, birth=birth, alive=False, disposition="PID_ABSENT")
    return dict(pid=pid, birth=birth, alive=fields[19] == birth, observed_birth=fields[19],
        proc_state=fields[0], disposition="SAME_IDENTITY" if fields[19] == birth else "PID_REUSED")


def _uids(pid):
    text = Path(f"/proc/{pid}/status").read_text()
    return tuple(map(int, next(line.split()[1:] for line in text.splitlines() if line.startswith("Uid:"))))


def _sender():
    pid = os.getpid()
    birth = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    require(os.getuid() == os.geteuid() == OWNER_UID and _uids(pid) == (OWNER_UID,) * 4,
            "HANDOFF_SENDER_UID_CHANGED")
    return dict(pid=pid, birth=birth, uid=OWNER_UID, euid=OWNER_UID)


def _inode(path):
    path = Path(path)
    row = path.lstat()
    require(stat.S_ISREG(row.st_mode), "HANDOFF_LOCK_NOT_ORIGINAL_REGULAR_FILE")
    return dict(path=str(path), device=row.st_dev, inode=row.st_ino)


def _current_old_episode():
    path = OLD_MASTER / "state.json"
    if path.exists():
        state = checked_record(path)
        require(state["protocol_id"] == OLD_PROTOCOL_ID and state.get("pending_request") is None
            and state["phase"] in ("WATCHING", "TERMINAL"), "OLD_WATCHDOG_RECOVERY_ALREADY_ADVANCED")
        return state["current_episode"]
    return checked_record(OLD_MASTER / "prepared/record.json")["initial_episode"]


def snapshot_binding():
    """Pure read-only preparation snapshot; no lock is created or acquired."""
    old = checked_record(OLD_MASTER / "protocol/record.json")
    source = checked_record(SOURCE_CONTROL_ROOT / "protocol/record.json")
    prepared = checked_record(SOURCE_CONTROL_ROOT / "prepared/record.json")
    require(old["id"] == OLD_PROTOCOL_ID and source["id"] == SOURCE_CONTROL_PROTOCOL_ID,
            "FIXED_HANDOFF_PROTOCOL_CHANGED")
    require(source["scientific_protocol_id"] == SCIENTIFIC_PROTOCOL_ID,
            "HANDOFF_SCIENTIFIC_PROTOCOL_CHANGED")
    controls = {}
    for role, relative in (("controller", "controllers/attempt0001/launch/record.json"),
                           ("supervisor", "supervisor/launch/record.json")):
        path = SOURCE_CONTROL_ROOT / relative
        value = checked_record(path)
        controls[role] = dict(role=role, pid=value["pid"], birth=value["birth"], launch=_ref(path))
    body = dict(schema="v61_fixed_source04_passive_handoff_binding.v1",
        source_episode=dict(root=str(SOURCE_CONTROL_ROOT), protocol_id=SOURCE_CONTROL_PROTOCOL_ID),
        old_watchdog=dict(root=str(OLD_MASTER), protocol_id=OLD_PROTOCOL_ID),
        old_watchdog_current_episode=_current_old_episode(),
        source_protocol=_ref(SOURCE_CONTROL_ROOT / "protocol/record.json"),
        source_prepared=_ref(SOURCE_CONTROL_ROOT / "prepared/record.json"),
        old_watchdog_protocol=_ref(OLD_MASTER / "protocol/record.json"),
        old_watchdog_prepared=_ref(OLD_MASTER / "prepared/record.json"),
        controls=controls, controller_attempt=1,
        core_job_ids=sorted(prepared["initial_job_states"]),
        inherited_attempt_history_digest=digest(prepared["attempt_history"]),
        inherited_unobserved_attempts=[dict(job_id=row["job_id"], attempt=row["attempt"],
            directory=row["directory"]) for row in prepared["known_unobserved_attempts"]],
        original_lock_bindings=old["original_lock_bindings"],
        old_watchdog_envelope_lock=_inode(OLD_MASTER / "cron/envelope.lock"),
        old_watchdog_change_lock=_inode(OLD_MASTER / "cron/crontab_change.lock"))
    value = {**body, "id": digest(body)}
    return checked_binding(value, require_live=True)


def checked_binding(value, *, require_live=False, allow_superseded=False):
    require(value["id"] == digest({k: v for k, v in value.items() if k != "id"}),
            "HANDOFF_BINDING_ID_CHANGED")
    expected = dict(root=str(SOURCE_CONTROL_ROOT), protocol_id=SOURCE_CONTROL_PROTOCOL_ID)
    require(value["schema"] == "v61_fixed_source04_passive_handoff_binding.v1"
        and value["source_episode"] == value["old_watchdog_current_episode"] == expected
        and value["old_watchdog"] == dict(root=str(OLD_MASTER), protocol_id=OLD_PROTOCOL_ID)
        and value["controller_attempt"] == 1, "HANDOFF_BOUND_EPISODE_CHANGED")
    source, previous = _read_ref(value["source_protocol"]), _read_ref(value["old_watchdog_protocol"])
    prepared = _read_ref(value["source_prepared"])
    _read_ref(value["old_watchdog_prepared"])
    require(source["id"] == SOURCE_CONTROL_PROTOCOL_ID and previous["id"] == OLD_PROTOCOL_ID
        and source["scientific_protocol_id"] == SCIENTIFIC_PROTOCOL_ID,
        "HANDOFF_ORIGINAL_PROTOCOL_CHANGED")
    require(value["core_job_ids"] == sorted(prepared["initial_job_states"])
        and len(value["core_job_ids"]) == 23 and prepared["evaluation_registered"] is False
        and value["inherited_attempt_history_digest"] == digest(prepared["attempt_history"])
        and value["inherited_unobserved_attempts"] == [dict(job_id=r["job_id"], attempt=r["attempt"],
            directory=r["directory"]) for r in prepared["known_unobserved_attempts"]],
        "HANDOFF_CORE_OR_HISTORY_BINDING_CHANGED")
    require(value["original_lock_bindings"] == previous["original_lock_bindings"]
        and len(value["original_lock_bindings"]) == 9, "HANDOFF_ORIGINAL_LOCK_BINDINGS_CHANGED")
    require(_current_old_episode() == expected, "OLD_WATCHDOG_EPISODE_CHANGED_DO_NOT_FOLLOW")
    require(set(value["controls"]) == {"controller", "supervisor"}, "HANDOFF_CONTROL_ROSTER_CHANGED")
    require(not any(SOURCE_CONTROL_ROOT.glob("controllers/attempt000[2-9]/launch/record.json"))
        and len(list(SOURCE_CONTROL_ROOT.glob("controllers/attempt*/launch/record.json"))) == 1,
        "OLD_CONTROLLER_ATTEMPT_CHANGED_DO_NOT_FOLLOW")
    for role, row in value["controls"].items():
        original = _read_ref(row["launch"])
        require(row["role"] == role and (row["pid"], row["birth"]) == (original["pid"], original["birth"])
            and original["control_protocol_id"] == SOURCE_CONTROL_PROTOCOL_ID
            and (role != "controller" or original["controller_attempt"] == 1), "HANDOFF_CONTROL_IDENTITY_CHANGED")
        if require_live:
            observed = _identity(row["pid"], row["birth"])
            require(observed["alive"] and observed.get("proc_state") not in ("Z", "X", "x")
                and _uids(row["pid"]) == (OWNER_UID,) * 4,
                    "OLD_CONTROL_IDENTITY_NOT_LIVE_OWNER")
    for key in ("old_watchdog_envelope_lock", "old_watchdog_change_lock"):
        require(_inode(value[key]["path"]) == value[key], "OLD_WATCHDOG_LOCK_INODE_CHANGED")
    require(not (OLD_MASTER / "STOP").exists(), "OLD_WATCHDOG_USER_STOP")
    terminal = OLD_MASTER / "terminal/record.json"
    if terminal.exists():
        record = checked_record(terminal)
        superseded = (record.get("schema") == "v61_old_watchdog_superseded.v1"
            and record.get("protocol_id") == OLD_PROTOCOL_ID
            and record.get("handoff_binding_id") == value["id"] and record.get("successor_master") == str(MASTER_ROOT))
        complete = False
        if (record.get("protocol_id") == OLD_PROTOCOL_ID
                and record.get("status") == "COMPLETE_NO_FURTHER_RECOVERY" and record.get("reason") == "COMPLETE"):
            final_path = SOURCE_CONTROL_ROOT / "closeout/record.json"
            if final_path.exists():
                final = checked_record(final_path)
                complete = (final.get("status") == "COMPLETE"
                    and final.get("protocol_id") == SCIENTIFIC_PROTOCOL_ID
                    and final.get("control_protocol_id") == SOURCE_CONTROL_PROTOCOL_ID)
        require(allow_superseded and (superseded or complete),
            "OLD_WATCHDOG_ALREADY_TERMINAL")
    return value


def _admission(root):
    root = Path(root).resolve()
    require(root == MASTER_ROOT.resolve() and os.getuid() == os.geteuid() == OWNER_UID,
            "UNREGISTERED_HANDOFF_ROOT_OR_UID")
    protocol = importlib.import_module("finqa_v61_registration").checked_master_protocol(root)
    prepared = checked_record(root / "prepared/record.json")
    binding = protocol["handoff_binding"]
    require(prepared["protocol_id"] == protocol["id"] and prepared["handoff_binding"] == binding,
            "HANDOFF_PREPARATION_CHANGED")
    return protocol, checked_binding(binding, allow_superseded=True)


def _passive_check(binding):
    """Only mutable small lifecycle state during 0.25s waiting, never tensors.

    Immutable implementation/prepared bindings were checked on invocation
    admission and are freshly checked again after acquiring all eight leases.
    """
    closeout_path = SOURCE_CONTROL_ROOT / "closeout/record.json"
    if closeout_path.exists() and checked_record(closeout_path).get("status") == "COMPLETE":
        return "COMPLETE_NO_MIGRATION"
    require(not (OLD_MASTER / "terminal/record.json").exists(), "OLD_WATCHDOG_ALREADY_TERMINAL")
    state_path = OLD_MASTER / "state.json"
    if state_path.exists():
        state = checked_record(state_path)
        require(state["protocol_id"] == OLD_PROTOCOL_ID
            and state["current_episode"] == binding["source_episode"]
            and state.get("pending_request") is None and state["phase"] == "WATCHING",
            "OLD_WATCHDOG_EPISODE_CHANGED_DO_NOT_FOLLOW")
    for row in binding["controls"].values():
        observed = _identity(row["pid"], row["birth"])
        require(observed["alive"] and observed.get("proc_state") not in ("Z", "X", "x"),
                "OLD_CONTROL_IDENTITY_NOT_LIVE_OWNER")
    require(not (SOURCE_CONTROL_ROOT / "control/stop_requested/record.json").exists(),
            "SOURCE_STOP_BEFORE_HANDOFF")
    require(not (SOURCE_CONTROL_ROOT / "controllers/attempt0001/failure/record.json").exists(),
            "SOURCE_CONTROLLER_FAILED")
    journal = checked_record(SOURCE_CONTROL_ROOT / "journal/state.json")
    require(journal["protocol_id"] == SCIENTIFIC_PROTOCOL_ID
        and journal["control_protocol_id"] == SOURCE_CONTROL_PROTOCOL_ID
        and journal["controller_attempt"] == 1, "SOURCE_JOURNAL_BINDING_CHANGED")
    require(not any(row["status"] in ("HARD_BLOCKED", "DEPENDENCY_BLOCKED", "UNKNOWN")
        for row in journal["job_states"].values()), "SOURCE_SCIENCE_HARD_FAILURE")
    if not 0 <= time.time() - journal["updated_epoch"] <= JOURNAL_MAX_AGE_SECONDS:
        return "WAITING_FOR_FRESH_SOURCE_JOURNAL"
    if not _remaining_generation_or_unregistered(journal):
        return "NO_HANDOFF_REMAINING_WORK"
    if not set(binding["core_job_ids"]) <= set(journal["accepted"]):
        return "WAITING_FOR_ACCEPTED_TRAINING_CORE"
    if journal["active_jobs"]:
        return "WAITING_FOR_NATURAL_GLOBAL_EMPTY"
    return None


def _remaining_generation_or_unregistered(journal):
    # All generation accepted means the old controller may already be scoring
    # or publishing promotion. It must finish under its existing owner.
    return not journal.get("evaluation_registered", False) or bool(
        set(journal["job_states"]) - set(journal["accepted"]))


@contextlib.contextmanager
def _locks(rows):
    """No creation, no partial retention, and no GPU-capacity queries."""
    acquired = []
    available = True
    try:
        for row in rows:
            path = Path(row["path"])
            stream = path.open("r+")
            try:
                opened = os.fstat(stream.fileno())
                require(stat.S_ISREG(opened.st_mode)
                    and (opened.st_dev, opened.st_ino) == (row["device"], row["inode"])
                    and _inode(path) == row, "ORIGINAL_HANDOFF_LEASE_CHANGED")
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                require(_inode(path) == row, "ORIGINAL_HANDOFF_LEASE_REPLACED")
            except BlockingIOError:
                stream.close()
                available = False
                break
            except BaseException:
                stream.close()
                raise
            acquired.append(stream)
        if not available:
            for stream in acquired:
                stream.close()
            acquired.clear()
        yield available
    finally:
        for stream in acquired:
            stream.close()


def _lease_rows(binding, *, owner=False):
    rows = [dict(path=path, **value) for path, value in binding["original_lock_bindings"].items()
            if (Path(path) == SCIENCE_ROOT / "owner.lock") == owner]
    require(len(rows) == (1 if owner else 8), "HANDOFF_LOCK_COUNT_CHANGED")
    return sorted(rows, key=lambda row: row["path"])


def _source_stop(root):
    require(not (Path(root) / "STOP").exists() and not (SOURCE_CONTROL_ROOT / "STOP").exists()
        and not (OLD_MASTER / "STOP").exists(), "EXPLICIT_STOP_NOT_MAINTENANCE")
    require(not (Path(root) / "control/stop_requested/record.json").exists(), "MASTER_STOP_NOT_MAINTENANCE")


def _signal_events(extra_paths=()):
    result = []
    paths = set(SOURCE_CONTROL_ROOT.glob("signals/*/received.jsonl"))
    for candidate in extra_paths:
        path = Path(candidate).resolve()
        require(path.is_relative_to(SCIENCE_ROOT) and path.name == "received.jsonl",
                "STOP_SIGNAL_PATH_ESCAPED_SCIENCE")
        paths.add(path)
    for path in sorted(paths):
        for line in path.read_bytes().splitlines():
            row = json.loads(line)
            if row.get("role") == "observer":
                continue
            if row.get("signal") not in (2, 15):
                continue
            require(row.get("schema") == "v59_received_signal_kernel_receipt.v1"
                and row.get("provenance") == "kernel_sigwaitinfo", "UNKNOWN_STOP_SIGNAL_RECEIPT")
            expected = load_v59_module("finqa_v59_signals").signal_decision(
                row["signal"], row.get("si_pid"), row.get("si_uid"), row.get("si_code"))
            require(row.get("decision") == expected, "STOP_SIGNAL_POLICY_RECEIPT_CHANGED")
            if expected["filtered"] is not True:
                result.append(dict(path=str(path), event=row))
    return result


def _journal(binding, *, require_fresh=True):
    value = checked_record(SOURCE_CONTROL_ROOT / "journal/state.json")
    require(value["protocol_id"] == SCIENTIFIC_PROTOCOL_ID
        and value["control_protocol_id"] == SOURCE_CONTROL_PROTOCOL_ID
        and value["controller_attempt"] == 1, "SOURCE_JOURNAL_BINDING_CHANGED")
    if require_fresh:
        require(0 <= time.time() - value["updated_epoch"] <= JOURNAL_MAX_AGE_SECONDS,
                "SOURCE_JOURNAL_NOT_FRESH")
    require(not any(row["status"] in ("HARD_BLOCKED", "DEPENDENCY_BLOCKED", "UNKNOWN")
        for row in value["job_states"].values()), "SOURCE_SCIENCE_HARD_FAILURE")
    prepared = _read_ref(binding["source_prepared"])
    require(value["attempt_history"][:len(prepared["attempt_history"])] == prepared["attempt_history"],
            "SOURCE_ATTEMPT_HISTORY_CHANGED")
    require(not (SOURCE_CONTROL_ROOT / "controllers/attempt0001/failure/record.json").exists(),
            "SOURCE_CONTROLLER_FAILED")
    return value


def _boundary_digest(journal):
    return digest(dict(accepted=journal["accepted"], attempt_history=journal["attempt_history"]))


def _accepted_and_exited(binding, journal):
    """Small winning receipts only; retain historical nonzero/unknown facts."""
    require(not journal["active_jobs"] and set(binding["core_job_ids"]) <= set(journal["accepted"]),
            "TRAINING_OR_GLOBAL_DRAINING_NOT_COMPLETE")
    accepted = {}
    for key, reference in journal["accepted"].items():
        value = _read_ref(reference)
        actual, result = _read_ref(value["actual_exit"]), _read_ref(value["result"])
        require(value["protocol_id"] == actual["protocol_id"] == SCIENTIFIC_PROTOCOL_ID
            and value["job_id"] == actual["job_id"] == key and value["attempt"] == actual["attempt"]
            and value["result_id"] == result["id"]
            and journal["job_states"][key]["status"] == "COMPLETE"
            and value["actual_exit_zero"] is True and actual["actual_waitpid_observed"] is True
            and actual["returncode"] == 0 and result["status"] == "COMPLETE"
            and result["resources"]["all_gates_passed"] is True, "ACCEPTED_WINNER_NOT_ACTUAL_EXIT_ZERO")
        require(_identity(actual["pid"], actual["birth"])["alive"] is False,
                "ACCEPTED_WORKER_STILL_PRESENT")
        accepted[key] = dict(accepted=reference, actual_exit=value["actual_exit"], result=value["result"])
    missing_allowed = {(r["job_id"], r["attempt"], r["directory"])
                       for r in binding["inherited_unobserved_attempts"]}
    history = []
    for row in journal["attempt_history"]:
        directory = Path(row["directory"]).resolve()
        require(directory.is_relative_to(SCIENCE_ROOT) and directory.name == f"attempt{row['attempt']:04d}"
            and directory.parent.name == "attempts", "HISTORICAL_ATTEMPT_PATH_CHANGED")
        launch_path = directory / "launch/record.json"
        if not launch_path.exists():
            failure = checked_record(directory / "launch_failure/record.json")
            require(failure["actual_child_created"] is False, "UNSETTLED_WORKER_CREATION")
            history.append(dict(job_id=row["job_id"], attempt=row["attempt"], actual_child_created=False))
            continue
        launch = checked_record(launch_path)
        require(launch["protocol_id"] == SCIENTIFIC_PROTOCOL_ID
            and launch["job"]["job_id"] == row["job_id"] and launch["attempt"] == row["attempt"],
            "HISTORICAL_LAUNCH_BINDING_CHANGED")
        require(_identity(launch["pid"], launch["birth"])["alive"] is False,
                "INITIALIZING_OR_DRAINING_WORKER_STILL_PRESENT")
        actual_path = directory / "actual_exit/record.json"
        if actual_path.exists():
            actual = checked_record(actual_path)
            require(actual["actual_waitpid_observed"] is True
                and (actual["pid"], actual["birth"]) == (launch["pid"], launch["birth"]),
                "HISTORICAL_ACTUAL_EXIT_CHANGED")
            code = actual["returncode"]
        else:
            require((row["job_id"], row["attempt"], row["directory"]) in missing_allowed,
                    "NEW_WORKER_EXIT_UNKNOWN")
            code = None
        history.append(dict(job_id=row["job_id"], attempt=row["attempt"], pid=launch["pid"],
            birth=launch["birth"], actual_returncode=code, historical_exit_not_reclassified=True))
    return dict(accepted=accepted, historical_worker_exits=history,
        core_count=len(binding["core_job_ids"]), active_workers=0,
        boundary_digest=_boundary_digest(journal), inherited_unknowns_preserved=True)


def _old_line():
    import shlex
    command = [str(PYTHON), "-u", str(OLD_MASTER / "implementation/finqa_v60_cron.py"),
               "tick", "--root", str(OLD_MASTER)]
    return ("* * * * * " + " ".join(shlex.quote(v) for v in command) + " " + OLD_MARKER).encode()


def _split_old(raw):
    kept, count = [], 0
    for line in raw.splitlines(keepends=True):
        content = line.rstrip(b"\r\n")
        if content == _old_line():
            count += 1
        else:
            require(OLD_MARKER.encode() not in content, "OLD_CRON_MARKER_CONFLICT")
            kept.append(line)
    require(count <= 1, "DUPLICATE_OLD_CRON_LINE")
    return b"".join(kept), count


def _installed_new(root, *, runner=None):
    cron = importlib.import_module("finqa_v61_cron")
    snapshot = cron.read_crontab(runner)
    _, count = cron.split_own(snapshot["raw"], cron.line(root))
    require(count == 1, "NEW_GUARD_NOT_INSTALLED_BEFORE_HANDOFF")
    return cron, snapshot


def _retire_old_watchdog(root, transaction, *, runner=None):
    binding = transaction["binding"]
    # This check precedes even the old recovery fence, not just line removal.
    _, initial_cron = _installed_new(root, runner=runner)
    require(_split_old(initial_cron["raw"])[1] == 1,
            "OLD_CRON_LINE_CHANGED_BEFORE_RETIREMENT")
    old_terminal = OLD_MASTER / "terminal/record.json"
    intent = _write(root / "handoff/old_watchdog_supersede_intent/record.json", dict(
        schema="v61_old_watchdog_supersede_intent.v1", transaction_id=transaction["id"],
        at_epoch=time.time(), old_terminal=str(old_terminal), scientific_STOP_written=False), immutable=True)
    require(not old_terminal.exists(), "OLD_WATCHDOG_TERMINAL_ALREADY_EXISTS")
    _write(old_terminal, dict(schema="v61_old_watchdog_superseded.v1",
        protocol_id=OLD_PROTOCOL_ID, status="SUPERSEDED_BY_V61_PASSIVE_HANDOFF", reason="MAINTENANCE_SUPERSEDED",
        at_epoch=time.time(), handoff_binding_id=binding["id"], successor_master=str(root),
        transaction_id=transaction["id"], supersede_intent_id=intent["id"],
        automatic_recovery_allowed=False, source_scientific_STOP_written=False), immutable=True)
    _write(root / "handoff/old_watchdog_superseded/record.json", dict(
        schema="v61_old_watchdog_superseded_receipt.v1", transaction_id=transaction["id"],
        terminal=_ref(old_terminal), at_epoch=time.time()), immutable=True)
    with _locks([binding["old_watchdog_change_lock"]]) as available:
        require(available, "OLD_CRONTAB_CHANGE_IN_PROGRESS")
        cron, before = _installed_new(root, runner=runner)
        target, count = _split_old(before["raw"])
        require(count == 1, "OLD_CRON_LINE_CHANGED_BEFORE_RETIREMENT")
        saved = cron.backup(before)
        change = _write(root / "handoff/old_cron_removal/intent/record.json", dict(
            schema="v61_exact_old_cron_removal_intent.v1", transaction_id=transaction["id"],
            at_epoch=time.time(), before_sha256=hashlib.sha256(before["raw"]).hexdigest(),
            target_sha256=hashlib.sha256(target).hexdigest(), original_backup=saved,
            exact_removed_line=_old_line().decode(), unrelated_content_recorded=False), immutable=True)
        require(cron.read_crontab(runner) == before, "CRONTAB_CHANGED_BEFORE_OLD_REMOVAL")
        result = (runner or subprocess.run)(["crontab", "-"], input=target,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        require(result.returncode == 0, "OLD_CRON_REMOVAL_RESULT_UNKNOWN")
        after = cron.read_crontab(runner)
        require(after["raw"] == target and _split_old(after["raw"])[1] == 0
            and cron.split_own(after["raw"], cron.line(root))[1] == 1,
            "OLD_CRON_REMOVAL_VERIFICATION_FAILED_NO_ROLLBACK")
        _write(root / "handoff/old_cron_removal/result/record.json", dict(
            schema="v61_exact_old_cron_removed.v1", transaction_id=transaction["id"],
            intent_id=change["id"], at_epoch=time.time(), status="REMOVED",
            target_sha256=change["target_sha256"], unrelated_lines_preserved=True,
            new_guard_line_retained=True), immutable=True)


def _pidfd_open(pid):
    if hasattr(os, "pidfd_open"):
        return os.pidfd_open(pid, 0)
    require(sys.platform == "linux" and os.uname().machine == "x86_64", "PIDFD_PLATFORM_NOT_REGISTERED")
    return _syscall(434, ctypes.c_int(pid), ctypes.c_uint(0))


def _syscall(number, *args):
    library = ctypes.CDLL(None, use_errno=True)
    library.syscall.restype = ctypes.c_long
    result = library.syscall(ctypes.c_long(number), *args)
    if result < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return int(result)


def _pidfd_term(fd):
    if hasattr(signal, "pidfd_send_signal"):
        signal.pidfd_send_signal(fd, signal.SIGTERM)
    else:
        _syscall(424, ctypes.c_int(fd), ctypes.c_int(signal.SIGTERM), ctypes.c_void_p(), ctypes.c_uint(0))


def _matches(event, intent):
    return bool(event.get("schema") == "v59_received_signal_kernel_receipt.v1"
        and event.get("provenance") == "kernel_sigwaitinfo" and event.get("signal") == 15
        and event.get("role") == intent["target"]["role"] and event.get("pid") == intent["target"]["pid"]
        and event.get("si_pid") == intent["sender"]["pid"] and event.get("si_uid") == OWNER_UID
        and event.get("si_code") == 0 and event.get("at_epoch", 0) >= intent["at_epoch"])


def _maintenance_marker(transaction, *, maximum_signals=2):
    path = SOURCE_CONTROL_ROOT / "control/stop_requested/record.json"
    marker = checked_record(path)
    reason = marker.get("reason")
    require(marker.get("schema") == "v57_terminal_explicit_stop.v1"
        and marker.get("protocol_id") == SCIENTIFIC_PROTOCOL_ID
        and marker.get("control_protocol_id") == SOURCE_CONTROL_PROTOCOL_ID
        and marker.get("at_epoch", 0) >= transaction["at_epoch"]
        and isinstance(reason, dict) and reason.get("marker") is False
        and isinstance(reason.get("signals"), list)
        and 1 <= len(reason["signals"]) <= maximum_signals
        and all(number == 15 for number in reason["signals"]),
        "OLD_CONTROL_STOP_NOT_EXACT_MAINTENANCE")
    return marker


def _relay_sender_evidence(path, event, supervisor):
    """Kernel PID/UID plus post-signal birth evidence, never kernel birth."""
    for line in Path(path).read_bytes().splitlines():
        row = json.loads(line)
        if row.get("schema") != "v58_received_signal_identity_enrichment.v1" or row.get("receipt_id") != event["receipt_id"]:
            continue
        processes = row.get("sender_parent_chain", {}).get("processes", [])
        sender = processes[0] if processes else {}
        require(row.get("pid") == event["pid"] and row.get("role") == "controller"
            and row.get("receipt_at_epoch") == event["at_epoch"]
            and row.get("kernel_receipt_fsynced_before_proc_reads") is True
            and row.get("identities_are_post_signal_observations") is True,
            "SUPERVISOR_RELAY_ENRICHMENT_BINDING_CHANGED")
        require(not (sender.get("identity_consistent") is True
            and sender.get("pid") == supervisor["pid"] and sender.get("birth") != supervisor["birth"]),
            "SUPERVISOR_RELAY_SENDER_BIRTH_CONTRADICTED")
        if (sender.get("identity_consistent") is True
                and (sender.get("pid"), sender.get("birth")) == (supervisor["pid"], supervisor["birth"])
                and sender.get("ruid") == sender.get("euid") == OWNER_UID
                and event["at_epoch"] <= sender.get("observed_at_epoch", 0) <= row.get("observed_at_epoch", 0)):
            return dict(kind="ORIGINAL_POST_SIGNAL_IDENTITY_ENRICHMENT", enrichment_digest=digest(row),
                receipt_id=event["receipt_id"], sender_pid=supervisor["pid"], sender_birth=supervisor["birth"],
                sender_uid=OWNER_UID, observed_epoch=row["observed_at_epoch"],
                kernel_birth_claimed=False, observation_is_not_atomic_with_signal=True)
    try:
        before = _identity(supervisor["pid"], supervisor["birth"])
        if before["alive"] and _uids(supervisor["pid"]) == (OWNER_UID,) * 4:
            after = _identity(supervisor["pid"], supervisor["birth"])
            if after["alive"]:
                return dict(kind="SAME_LIVE_SUPERVISOR_POST_SIGNAL_OBSERVATION",
                    sender_pid=supervisor["pid"], sender_birth=supervisor["birth"], sender_uid=OWNER_UID,
                    observed_epoch=time.time(), kernel_birth_claimed=False,
                    observation_is_not_atomic_with_signal=True)
    except (FileNotFoundError, ProcessLookupError):
        pass
    # The original logger first fsyncs the kernel receipt and only then reads
    # /proc and appends enrichment. Wait for that same live receiver's writer,
    # never authorize the signal before the evidence exists.
    controller_launch = checked_record(SOURCE_CONTROL_ROOT / "controllers/attempt0001/launch/record.json")
    if _identity(controller_launch["pid"], controller_launch["birth"])["alive"]:
        raise HandoffEvidencePending("WAITING_FOR_EXACT_RELAY_IDENTITY_ENRICHMENT")
    raise HandoffError("SUPERVISOR_RELAY_SENDER_BIRTH_UNPROVEN")


def _bind_supervisor_relay(root, transaction):
    """At most one exact frozen-parent relay; no additional signal is sent."""
    proof_path = root / "handoff/derived_supervisor_relay/record.json"
    if proof_path.exists():
        return checked_record(proof_path)
    primary_path = root / "handoff/signals/controller/receipt/record.json"
    require(primary_path.is_file(), "SUPERVISOR_RELAY_REQUIRES_BOUND_PRIMARY_RECEIPT")
    primary = checked_record(primary_path)
    controller, supervisor = (transaction["binding"]["controls"][key] for key in ("controller", "supervisor"))
    candidates = [row for row in _signal_events() if row["event"].get("si_pid") == supervisor["pid"]]
    if not candidates:
        return None
    require(len(candidates) == 1, "MULTIPLE_SUPERVISOR_FORWARDED_TERMS")
    candidate, event = candidates[0], candidates[0]["event"]
    require(primary["transaction_id"] == transaction["id"]
        and event.get("role") == "controller" and event.get("pid") == controller["pid"]
        and event.get("signal") == 15 and event.get("si_uid") == OWNER_UID and event.get("si_code") == 0
        and event["at_epoch"] >= primary["event"]["at_epoch"], "SUPERVISOR_SIGNAL_NOT_BOUND_STOP_RELAY")
    marker = _maintenance_marker(transaction)
    require(marker["at_epoch"] <= event["at_epoch"], "SUPERVISOR_RELAY_PRECEDES_MAINTENANCE_MARKER")
    evidence = _relay_sender_evidence(candidate["path"], event, supervisor)
    return _write(proof_path, dict(schema="v61_exact_frozen_supervisor_stop_relay.v1",
        transaction_id=transaction["id"], primary_receipt_id=primary["id"],
        event=event, sender=supervisor, target=controller, sender_evidence=evidence,
        signal_log_path=candidate["path"], marker=_ref(SOURCE_CONTROL_ROOT / "control/stop_requested/record.json"),
        bound_epoch=time.time(), original_frozen_stop_forwarding=True,
        handoff_did_not_dispatch_this_second_signal=True, maximum_derived_TERMs=1), immutable=True)


def _await_supervisor_relay(root, transaction):
    while True:
        _source_stop(root)
        try:
            return _bind_supervisor_relay(root, transaction)
        except HandoffEvidencePending:
            _status(root, "WAITING_FOR_EXACT_RELAY_IDENTITY_ENRICHMENT")
            time.sleep(POLL_SECONDS)


def _dispatch_term(root, transaction, role):
    row, sender = transaction["binding"]["controls"][role], transaction["sender"]
    require(_sender() == sender, "MAINTENANCE_SENDER_IDENTITY_CHANGED")
    require(_identity(row["pid"], row["birth"])["alive"] and _uids(row["pid"]) == (OWNER_UID,) * 4,
            "MAINTENANCE_TARGET_IDENTITY_CHANGED")
    descriptor = _pidfd_open(row["pid"])
    try:
        require(_identity(row["pid"], row["birth"])["alive"] and _uids(row["pid"]) == (OWNER_UID,) * 4,
                "MAINTENANCE_TARGET_CHANGED_AFTER_PIDFD")
        directory = root / "handoff/signals" / role
        require(not (directory / "intent/record.json").exists(), "MAINTENANCE_SIGNAL_CANNOT_REPEAT")
        intent = _write(directory / "intent/record.json", dict(
            schema="v61_exact_maintenance_TERM_intent.v1", transaction_id=transaction["id"],
            at_epoch=time.time(), target=row, sender=sender, signal=15,
            pidfd_identity_verified=True, scientific_workers_signaled=False), immutable=True)
        _pidfd_term(descriptor)
        require(_sender() == sender, "MAINTENANCE_SENDER_CHANGED_AFTER_DISPATCH")
        dispatched = _write(directory / "dispatch/record.json", dict(
            schema="v61_pidfd_TERM_dispatch_returned.v1", transaction_id=transaction["id"],
            intent_id=intent["id"], returned_epoch=time.time(), sender=sender,
            pidfd_send_returned_success=True, receiver_receipt_not_yet_claimed=True), immutable=True)
    finally:
        os.close(descriptor)
    while True:
        _source_stop(root)
        require(_sender() == sender, "SENDER_IDENTITY_NOT_AVAILABLE_TO_BIND_RECEIPT")
        matching = [r for r in _signal_events() if _matches(r["event"], intent)]
        require(len(matching) <= 1, "MULTIPLE_MAINTENANCE_SIGNAL_RECEIPTS")
        if matching:
            receipt = matching[0]
            require(_sender() == sender, "SENDER_CHANGED_DURING_RECEIPT_BINDING")
            return _write(directory / "receipt/record.json", dict(
                schema="v61_exact_maintenance_kernel_receipt_bound.v1", transaction_id=transaction["id"],
                intent_id=intent["id"], dispatch_id=dispatched["id"], event=receipt["event"],
                signal_log_path=receipt["path"], sender=sender, receipt_bound_epoch=time.time(),
                receiver_observed_while_sender_same_identity=True), immutable=True)
        require(_identity(row["pid"], row["birth"])["alive"], "TARGET_EXIT_WITHOUT_EXACT_KERNEL_SIGNAL_RECEIPT")
        time.sleep(POLL_SECONDS)


def _check_maintenance_signals(root, transaction, *, final=False, extra_paths=()):
    proofs = {}
    require(not (root / "handoff/signals/supervisor/intent/record.json").exists(),
            "SUPERVISOR_TERM_NOT_AUTHORIZED")
    for role in ("controller",):
        directory = root / "handoff/signals" / role
        intent_path = directory / "intent/record.json"
        if not intent_path.exists():
            continue
        intent = checked_record(intent_path)
        require(intent["transaction_id"] == transaction["id"] and intent["sender"] == transaction["sender"]
            and intent["target"] == transaction["binding"]["controls"][role], "MAINTENANCE_INTENT_CHANGED")
        require((directory / "dispatch/record.json").is_file()
            and (directory / "receipt/record.json").is_file(), "UNKNOWN_SIGNAL_DISPATCH_NO_RETRY")
        dispatch, receipt = checked_record(directory / "dispatch/record.json"), checked_record(directory / "receipt/record.json")
        require(dispatch["transaction_id"] == receipt["transaction_id"] == transaction["id"]
            and dispatch["schema"] == "v61_pidfd_TERM_dispatch_returned.v1"
            and dispatch["pidfd_send_returned_success"] is True
            and dispatch["sender"] == transaction["sender"]
            and dispatch["returned_epoch"] >= intent["at_epoch"]
            and receipt["schema"] == "v61_exact_maintenance_kernel_receipt_bound.v1"
            and dispatch["intent_id"] == receipt["intent_id"] == intent["id"]
            and receipt["dispatch_id"] == dispatch["id"]
            and receipt["receiver_observed_while_sender_same_identity"] is True
            and receipt["sender"] == transaction["sender"] and _matches(receipt["event"], intent)
            and receipt["event"]["at_epoch"] <= receipt["receipt_bound_epoch"], "MAINTENANCE_RECEIPT_CHANGED")
        proofs[role] = receipt
    if final:
        require("controller" in proofs, "CONTROLLER_MAINTENANCE_RECEIPT_REQUIRED")
    relay_path = root / "handoff/derived_supervisor_relay/record.json"
    if relay_path.exists():
        relay = checked_record(relay_path)
        supervisor = transaction["binding"]["controls"]["supervisor"]
        controller = transaction["binding"]["controls"]["controller"]
        evidence, event = relay["sender_evidence"], relay["event"]
        require("controller" in proofs and relay["transaction_id"] == transaction["id"]
            and relay["primary_receipt_id"] == proofs["controller"]["id"]
            and relay["sender"] == supervisor and relay["target"] == controller
            and relay["handoff_did_not_dispatch_this_second_signal"] is True
            and relay["maximum_derived_TERMs"] == 1 and event["signal"] == 15
            and event["pid"] == controller["pid"] and event["role"] == "controller"
            and event["si_pid"] == supervisor["pid"] and event["si_uid"] == OWNER_UID and event["si_code"] == 0
            and event["at_epoch"] >= proofs["controller"]["event"]["at_epoch"]
            and (evidence["sender_pid"], evidence["sender_birth"], evidence["sender_uid"])
                == (supervisor["pid"], supervisor["birth"], OWNER_UID)
            and evidence["kernel_birth_claimed"] is False
            and event["at_epoch"] <= evidence["observed_epoch"] <= relay["bound_epoch"],
            "SUPERVISOR_RELAY_PROOF_CHANGED")
        marker = _read_ref(relay["marker"])
        require(marker["at_epoch"] <= event["at_epoch"], "SUPERVISOR_RELAY_MARKER_CHANGED")
        if evidence["kind"] == "ORIGINAL_POST_SIGNAL_IDENTITY_ENRICHMENT":
            require(_relay_sender_evidence(relay["signal_log_path"], event, supervisor) == evidence,
                    "SUPERVISOR_RELAY_ENRICHMENT_CHANGED")
        else:
            require(evidence["kind"] == "SAME_LIVE_SUPERVISOR_POST_SIGNAL_OBSERVATION",
                    "SUPERVISOR_RELAY_IDENTITY_EVIDENCE_UNKNOWN")
        proofs["supervisor_forwarded_controller_TERM"] = relay
    actual = _signal_events(extra_paths)
    allowed = {r["event"]["receipt_id"]: r["event"] for r in proofs.values()}
    require(len(actual) == len(allowed) and all(r["event"].get("receipt_id") in allowed
        and r["event"] == allowed[r["event"]["receipt_id"]] for r in actual),
        "UNAUTHORIZED_OWNER_TERM_OR_INT_NOT_MAINTENANCE")
    return proofs


def _status(root, status, **fields):
    path = root / "handoff/state.json"
    previous = checked_record(path) if path.exists() else None
    if previous and previous["status"] == status and time.time() - previous["at_epoch"] < 15:
        return previous
    return _write(path, dict(schema="v61_passive_handoff_state.v1", status=status,
        at_epoch=time.time(), scientific_workers_signaled=False, **fields))


def _block(root, code):
    path = root / "handoff/blocked/record.json"
    if not path.exists():
        _write(path, dict(schema="v61_handoff_permanent_block.v1", status="BLOCKED", reason=code,
            at_epoch=time.time(), automatic_retry_allowed=False, worker_signals_sent=False,
            old_historical_records_reclassified=False), immutable=True)
    return _status(root, "BLOCKED", reason=checked_record(path)["reason"])


def _no_migration(root, status):
    path = root / "handoff/no_migration/record.json"
    if not path.exists():
        _write(path, dict(schema="v61_no_remaining_generation_no_migration.v1", status=status,
            at_epoch=time.time(), old_watchdog_retired=False, old_control_signaled=False,
            original_scoring_and_promotion_remain_with_old_controller=True), immutable=True)
    return _status(root, checked_record(path)["status"])


def _finalize(root, transaction):
    binding = transaction["binding"]
    _source_stop(root)
    checked_binding(binding, allow_superseded=True)
    _await_supervisor_relay(root, transaction)
    proofs = _check_maintenance_signals(root, transaction, final=True)
    require(all(not _identity(r["pid"], r["birth"])["alive"] for r in binding["controls"].values()),
            "OLD_CONTROL_NOT_GONE")
    _maintenance_marker(transaction, maximum_signals=len(proofs))
    journal = _journal(binding, require_fresh=False)
    require(not journal["active_jobs"] and _boundary_digest(journal) == transaction["boundary"]["boundary_digest"],
            "SCIENTIFIC_DISPATCH_OR_ACCEPTED_STATE_CHANGED_DURING_HANDOFF")
    actual_path = SOURCE_CONTROL_ROOT / "supervisor/attempts/attempt0001/actual_exit/record.json"
    actual = checked_record(actual_path)
    controller = binding["controls"]["controller"]
    require(actual["protocol_id"] == SCIENTIFIC_PROTOCOL_ID
        and actual["control_protocol_id"] == SOURCE_CONTROL_PROTOCOL_ID
        and actual["actual_waitpid_observed"] is True and actual["returncode"] == 2
        and (actual["pid"], actual["birth"]) == (controller["pid"], controller["birth"]),
        "MAINTENANCE_CONTROLLER_REAL_WAITPID_EXPECTED_STOP_CODE_REQUIRED")
    closeout = checked_record(SOURCE_CONTROL_ROOT / "supervisor/closeout/record.json")
    require(closeout["protocol_id"] == SCIENTIFIC_PROTOCOL_ID
        and closeout["control_protocol_id"] == SOURCE_CONTROL_PROTOCOL_ID
        and closeout["status"] == "STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME"
        and closeout["controller_attempts"] == 1 and closeout["automatic_restart_stopped"] is True,
        "OLD_SUPERVISOR_DID_NOT_CLOSE_SAFELY")
    orphan = checked_record(SOURCE_CONTROL_ROOT / "supervisor/orphan_stop/record.json")
    require(orphan["protocol_id"] == SCIENTIFIC_PROTOCOL_ID
        and orphan["control_protocol_id"] == SOURCE_CONTROL_PROTOCOL_ID
        and orphan["workers"] == [] and orphan["all_identities_observed_exited"] is True,
            "MAINTENANCE_MUST_NOT_SIGNAL_ANY_WORKER")
    with _locks(_lease_rows(binding, owner=True)) as available:
        if not available:
            return _status(root, "WAITING_FOR_SCIENCE_OWNER_RELEASE")
        result = _write(root / "handoff/completed/record.json", dict(
            schema="v61_completed_authorized_source04_stop.v1", status="FINAL_AUTHORIZED_STOP",
            transaction_id=transaction["id"], handoff_binding_id=binding["id"],
            source_episode=binding["source_episode"], finished_epoch=time.time(), sender=transaction["sender"],
            authorized_signal_receipts={key: value["id"] for key, value in proofs.items()},
            final_journal_id=journal["id"], boundary_digest=_boundary_digest(journal),
            old_control_STOP=_ref(SOURCE_CONTROL_ROOT / "control/stop_requested/record.json"),
            controller_actual_exit=_ref(actual_path), supervisor_closeout=_ref(SOURCE_CONTROL_ROOT / "supervisor/closeout/record.json"),
            controller_actual_returncode=actual["returncode"],
            controller_zero_exit_not_claimed=True, supervisor_received_maintenance_signal=False,
            supervisor_actual_waitpid_observed=False, supervisor_OS_returncode=None,
            original_eight_GPU_leases_exclusive=True, scientific_owner_observed_available=True,
            accepted_winners_actual_exit_zero=True, old_worker_history_preserved=True,
            observer_retirement_not_performed=True, scientific_worker_signals_sent=False), immutable=True)
    return _status(root, "READY_FOR_WATCHDOG", completed_id=result["id"])


def _reconcile(root, transaction):
    """Read-only external-state reconciliation. Never resend TERM or crontab."""
    binding = transaction["binding"]
    checked_binding(binding, allow_superseded=True)
    _source_stop(root)
    terminal = checked_record(OLD_MASTER / "terminal/record.json")
    require(terminal.get("transaction_id") == transaction["id"], "UNRESOLVED_OLD_WATCHDOG_RETIREMENT")
    _, snapshot = _installed_new(root)
    require(_split_old(snapshot["raw"])[1] == 0, "UNRESOLVED_OLD_CRON_REMOVAL_NO_RETRY")
    removal = root / "handoff/old_cron_removal/result/record.json"
    require(removal.is_file() and checked_record(removal)["transaction_id"] == transaction["id"],
            "UNKNOWN_CRONTAB_DISPATCH_NO_RETRY")
    _await_supervisor_relay(root, transaction)
    proofs = _check_maintenance_signals(root, transaction, final=True)
    del proofs
    if any(_identity(row["pid"], row["birth"])["alive"] for row in binding["controls"].values()):
        return _status(root, "WAITING_FOR_OLD_CONTROL_EXIT_READONLY")
    return _finalize(root, transaction)


def _execute(root, protocol, binding, journal, boundary):
    if not _remaining_generation_or_unregistered(journal):
        return _no_migration(root, "NO_HANDOFF_REMAINING_WORK")
    require(not _signal_events() and not (SOURCE_CONTROL_ROOT / "control/stop_requested/record.json").exists(),
            "STOP_BEFORE_MAINTENANCE")
    transaction = _write(root / "handoff/transaction/record.json", dict(
        schema="v61_single_passive_handoff_transaction.v1", protocol_id=protocol["id"],
        at_epoch=time.time(), binding=binding, boundary=boundary,
        pre_stop_journal_id=journal["id"], sender=_sender(),
        fresh_global_empty=True, original_eight_leases_exclusive=True,
        only_fixed_control_processes_may_receive_TERM=True), immutable=True)
    _retire_old_watchdog(root, transaction)
    # Leases remain held through both control exits. No worker can be dispatched.
    _source_stop(root)
    _dispatch_term(root, transaction, "controller")
    while _identity(binding["controls"]["controller"]["pid"], binding["controls"]["controller"]["birth"])["alive"]:
        _source_stop(root)
        _await_supervisor_relay(root, transaction)
        _check_maintenance_signals(root, transaction)
        time.sleep(POLL_SECONDS)
    supervisor = binding["controls"]["supervisor"]
    # The frozen supervisor observes its child's actual waitpid and stop marker,
    # publishes its empty orphan audit, and exits naturally. Do not race that
    # path with an unnecessary second TERM or a forwarded controller TERM.
    while _identity(supervisor["pid"], supervisor["birth"])["alive"]:
        _source_stop(root)
        _await_supervisor_relay(root, transaction)
        _check_maintenance_signals(root, transaction)
        time.sleep(POLL_SECONDS)
    return _finalize(root, transaction)


def advance_handoff(root=MASTER_ROOT, *, envelope=None, session=None):
    """One passive poll, or finish the one acquired, write-ahead transaction.

    Cron passes its already-held envelope. Direct callers take the same lock;
    import/registration/snapshot never calls this function implicitly.
    """
    root = Path(root).resolve()
    require(root == MASTER_ROOT.resolve() and os.getuid() == os.geteuid() == OWNER_UID,
            "UNREGISTERED_HANDOFF_ROOT_OR_UID")
    if envelope is None:
        path = root / "cron/envelope.lock"
        with path.open("a") as owned:
            try:
                fcntl.flock(owned, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return dict(status="WAITING_FOR_HANDOFF_ENVELOPE")
            return advance_handoff(root, envelope=owned, session=session)
    require(Path(envelope.name).resolve() == root / "cron/envelope.lock", "WRONG_HANDOFF_ENVELOPE")
    fcntl.flock(envelope, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        _source_stop(root)
        no_migration_path = root / "handoff/no_migration/record.json"
        if no_migration_path.exists():
            return _status(root, checked_record(no_migration_path)["status"])
        if session is None:
            session = {}
        if "admission" not in session:
            session["admission"] = _admission(root)
        protocol, binding = session["admission"]
        _source_stop(root)
        if (root / "handoff/blocked/record.json").exists():
            return _status(root, "BLOCKED", reason=checked_record(root / "handoff/blocked/record.json")["reason"])
        if (root / "handoff/completed/record.json").exists():
            return _status(root, "READY_FOR_WATCHDOG", completed_id=checked_record(root / "handoff/completed/record.json")["id"])
        transaction_path = root / "handoff/transaction/record.json"
        if not transaction_path.exists():
            waiting = _passive_check(binding)
            if waiting:
                if waiting in ("NO_HANDOFF_REMAINING_WORK", "COMPLETE_NO_MIGRATION"):
                    return _no_migration(root, waiting)
                return _status(root, waiting)
        with _locks(_lease_rows(binding)) as available:
            if not available:
                return _status(root, "WAITING_FOR_ALL_OR_NONE_GPU_LEASES")
            with _locks([binding["old_watchdog_envelope_lock"]]) as old_available:
                if not old_available:
                    return _status(root, "WAITING_FOR_OLD_CRON_ENVELOPE")
                fresh_protocol, fresh_binding = _admission(root)
                require(fresh_protocol == protocol and fresh_binding == binding,
                        "HANDOFF_IMMUTABLE_ADMISSION_CHANGED_DURING_WAIT")
                if transaction_path.exists():
                    return _reconcile(root, checked_record(transaction_path))
                checked_binding(binding, require_live=True)
                _installed_new(root)
                journal = _journal(binding)
                if not _remaining_generation_or_unregistered(journal):
                    return _no_migration(root, "NO_HANDOFF_REMAINING_WORK")
                if journal["active_jobs"]:
                    return _status(root, "WAITING_FOR_FRESH_EMPTY_JOURNAL")
                boundary = _accepted_and_exited(binding, journal)
                fresh = _journal(binding)
                require(_boundary_digest(fresh) == _boundary_digest(journal) and not fresh["active_jobs"],
                        "BOUNDARY_CHANGED_DURING_ACCEPTANCE_CHECK")
                return _execute(root, protocol, binding, fresh, boundary)
    except Exception as error:
        return _block(root, str(error) if isinstance(error, HandoffError) else type(error).__name__)


def validate_authorized_stop(root, episode, observation):
    """None without a final receipt; otherwise only this exact maintenance stop.

    The backend retains original_stop_evidence before its narrowly scoped
    effective classification. A later owner TERM/INT/STOP is never waived.
    """
    root = Path(root).resolve()
    path = root / "handoff/completed/record.json"
    if not path.exists():
        return None
    protocol, binding = _admission(root)
    _source_stop(root)
    require(not (root / "handoff/blocked/record.json").exists(), "HANDOFF_ALREADY_BLOCKED")
    final = checked_record(path)
    transaction = checked_record(root / "handoff/transaction/record.json")
    require(episode == binding["source_episode"] and final["source_episode"] == episode
        and observation["episode_root"] == episode["root"]
        and observation["control_protocol_id"] == episode["protocol_id"]
        and observation["identity_roster_complete"] is True
        and observation["identities"] and all(row["alive"] is False for row in observation["identities"]),
        "AUTHORIZED_HANDOFF_REQUIRES_COMPLETE_GONE_SOURCE04_ROSTER")
    require(transaction["protocol_id"] == protocol["id"] and transaction["binding"] == binding
        and final["transaction_id"] == transaction["id"] and final["handoff_binding_id"] == binding["id"],
        "AUTHORIZED_HANDOFF_TRANSACTION_CHANGED")
    require(observation.get("any_sigint_observed") is False
        and observation.get("unfiltered_unknown_stop_signal") is False
        and observation.get("known_hard_block") is False
        and observation.get("known_implementation_failure") is False,
        "STOP_OR_HARD_FAILURE_NOT_MAINTENANCE")
    proofs = _check_maintenance_signals(root, transaction, final=True,
        extra_paths=[row["path"] for row in observation.get("signal_logs", [])])
    require(final["authorized_signal_receipts"] == {k: v["id"] for k, v in proofs.items()},
            "AUTHORIZED_SIGNAL_SET_CHANGED")
    _read_ref(final["old_control_STOP"])
    _read_ref(final["controller_actual_exit"])
    _read_ref(final["supervisor_closeout"])
    journal = _journal(binding, require_fresh=False)
    require(journal["id"] == final["final_journal_id"] == observation["journal_id"]
        and _boundary_digest(journal) == final["boundary_digest"] and not journal["active_jobs"],
        "POST_HANDOFF_SOURCE_STATE_CHANGED")
    return final
