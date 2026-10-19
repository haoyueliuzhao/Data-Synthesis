"""One-shot, account-level recovery guard; never a second live scientific pool.

This module does not install cron or modify any scientific episode. A separately
frozen registration backend supplies the following methods:

* checked_protocol(root), checked_prepared(root): immutable guard authorization;
* observe_episode(root, episode, state): lightweight status/proc observation;
* audit_durable(root, episode, observation): original per-job audits and complete
  stop/error evidence, only after every registered identity has exited;
* retire_observer(root, episode, observation, request_id): only the byte-bound,
  identity-verified, account-owned, read-only CPU observer may receive TERM;
  return a gone receipt before a successor can start another observer;
* register_episode(root, predecessor, observation, audits, request_id): an
  idempotent, registration-only successor transaction, with no process launch;
* launch_registered(root, receipt, request_id, launch_attempt): at most one
  process creation, returning a real launch or proved pre-child failure;
* reconcile_launch(root, receipt, request_id, launch_attempt): read-only proof
  after an interrupted launch transaction. An unknown launch is never repeated.

Callbacks must preserve the scientific protocol, accepted jobs, original
attempt ordinals, durable units, GPU isolation and cumulative budget. Callback
results and decisions are separately preserved in the guard namespace.
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import importlib
import json
import os
import re
import stat
import tempfile
import time
from pathlib import Path

from finqa_v61_binding import (MASTER_ROOT, REPO, SCIENCE_ROOT, SOURCE_CONTROL_ROOT,
                              resource_override)

ROOT = MASTER_ROOT
INITIAL_EPISODE_ROOT = SOURCE_CONTROL_ROOT
GPU_LEASE_ROOT = SCIENCE_ROOT.parent.parent / "v25_training_replication_01/training_replication/locks"
OWNER_UID = 1004
TRANSIENT_ERRNOS = frozenset((errno.EAGAIN, errno.ENOMEM, errno.ENOSPC, errno.EDQUOT,
                             errno.EIO, errno.ESTALE, errno.ETIMEDOUT))
RECOVERY_CATEGORIES = frozenset(("CONFIRMED_SIGKILL", "ALL_IDENTITIES_GONE_EXIT_UNKNOWN",
                                 "AUTHORIZED_V61_HANDOFF"))
TERMINAL_REASONS = frozenset(("OWNER_TERM", "SIGINT", "STOP", "UNKNOWN_FEEDBACK",
    "HASH_OR_STATE_FAILURE", "NUMERICAL_FAILURE", "IMPLEMENTATION_FAILURE", "HARD_BLOCKED"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def policy():
    return dict(schema="v61_account_one_shot_recovery_policy.v1", owner_uid=OWNER_UID,
        intended_interval_seconds=60, guard_root=str(ROOT), scientific_root=str(SCIENCE_ROOT),
        initial_episode_root=str(INITIAL_EPISODE_ROOT), account_only=True,
        cron_installed_by_this_module=False, process_UID_changed=False,
        original_GPU_isolation_required=True, scientific_worker_limit=6,
        original_scientific_worker_limit=4, resource_override=resource_override(),
        initial_episode_requires_final_authorized_handoff=True,
        initial_episode_disappearance_is_not_ordinary_recovery_authority=True,
        tick_nonblocking_exclusive_lock=True, live_identity_prevents_a_second_pool=True,
        blocking_roster_roles=["supervisor", "controller", "runner", "scientific_worker"],
        readonly_observer_not_a_scientific_worker=True, independent_observer_limit=1,
        monitor_retirement="identity-bound own read-only CPU observer TERM only after blocking roster is gone",
        authorized_monitor_retirement_is_not_scientific_stop_intent=True,
        healthy_pool_observation="lightweight status and process identity only",
        healthy_pool_reaudits_or_tensor_hashes=False,
        recovery_categories=sorted(RECOVERY_CATEGORIES),
        disappearance_alone_is_not_called_SIGKILL_or_exit_zero=True,
        manual_SIGKILL_may_be_recovered_if_no_durable_stop_intent=True,
        permanent_stop_reasons=sorted(TERMINAL_REASONS), dedicated_STOP_is_terminal=True,
        complete_stop_error_evidence_and_original_job_audits_required=True,
        all_original_project_GPU_leases_probe="all or none, immediately release every lease",
        science_owner_lock_probe_required=True, lease_probe_is_not_GPU_capacity_admission=True,
        registered_original_lock_inodes_required=True, missing_or_replaced_lock_is_terminal=True,
        scientific_attempts_budgets_and_accepted_results_never_reset=True,
        successor_requires_fresh_independent_registered_episode=True,
        old_one_shot_entry_reexecution=False, ambiguous_launch_reexecuted=False,
        known_no_child_transient_launch_failure_may_retry=True,
        scientific_or_unowned_processes_signaled=False, root_SIGKILL_immunity_claimed=False)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def bound(value):
    return {**value, "id": digest(value)}


def checked(path):
    value = json.loads(Path(path).read_bytes())
    require(value.get("id") == digest({key: item for key, item in value.items() if key != "id"}),
            "guard record identity changed: " + str(path))
    return value


def _fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_record(path, value, *, immutable=False):
    path = Path(path)
    value = value if "id" in value else bound(value)
    require(value["id"] == digest({key: item for key, item in value.items() if key != "id"}),
            "invalid callback or watchdog record identity")
    path.parent.mkdir(parents=True, exist_ok=True)
    if immutable and path.exists():
        require(checked(path) == value, "cannot replace immutable watchdog evidence")
        return value
    fd, temporary = tempfile.mkstemp(prefix=".watchdog-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        if immutable:
            os.link(temporary, path)
            os.unlink(temporary)
        else:
            os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()
    return value


def _episode(episode, root):
    require(isinstance(episode, dict) and isinstance(episode.get("protocol_id"), str)
            and episode["protocol_id"], "an immutable registered episode identity is required")
    path = Path(episode["root"]).resolve()
    allowed_successor = path.parent == Path(root).resolve() / "episodes" and re.fullmatch(r"episode[0-9]{6}", path.name)
    require(path == INITIAL_EPISODE_ROOT.resolve() or allowed_successor,
            "episode root escaped the registered automatic recovery namespace")
    return episode


def observation_decision(observation, episode):
    require(observation["episode_root"] == episode["root"]
            and observation["control_protocol_id"] == episode["protocol_id"],
            "observation belongs to another registered episode")
    reason = observation.get("known_terminal_reason")
    require(reason is None or reason in TERMINAL_REASONS, "unrecognized terminal classification")
    if reason is not None or observation.get("stop_marker_present") is True:
        return dict(action="TERMINAL", status="STOPPED_NO_AUTO_RECOVERY", reason=reason or "STOP")
    if observation.get("experiment_complete") is True:
        return dict(action="TERMINAL", status="COMPLETE_NO_FURTHER_RECOVERY", reason="COMPLETE")
    identities = observation.get("identities")
    require(isinstance(identities, list), "explicit process identity roster required")
    require(all(row.get("role") in ("supervisor", "controller", "runner", "scientific_worker")
                for row in identities), "only blocking scientific/control roles belong in the live-pool roster")
    require(all(type(row.get("pid")) is int and row["pid"] > 0 for row in identities),
            "blocking identities must have real positive process IDs")
    require(len({(row["pid"], str(row["birth"])) for row in identities}) == len(identities),
            "duplicate observed process identity")
    if any(row.get("alive") is True for row in identities):
        return dict(action="WAIT", status="WATCHING_LIVE_EPISODE",
                    live_identities=sum(row.get("alive") is True for row in identities))
    if observation.get("identity_roster_complete") is not True or not identities or any(
            row.get("alive") is not False or not isinstance(row.get("birth"), str) or not row["birth"]
            for row in identities):
        return dict(action="WAIT", status="WAITING_FOR_COMPLETE_EXIT_OBSERVATION")
    waited, code = observation.get("actual_waitpid_observed"), observation.get("actual_returncode")
    require(type(waited) is bool, "exit observation must distinguish real waitpid from disappearance")
    if waited:
        require(type(code) is int, "real waitpid requires its actual return code")
        if code == -9:
            return dict(action="AUDIT", status="RECOVERY_CANDIDATE", category="CONFIRMED_SIGKILL")
        return dict(action="TERMINAL", status="BLOCKED_KNOWN_UNSAFE_EXIT", reason="KNOWN_EXIT_NOT_AUTHORIZED",
                    actual_returncode=code)
    require(code is None, "an unobserved OS exit code must remain unknown")
    return dict(action="AUDIT", status="RECOVERY_CANDIDATE", category="ALL_IDENTITIES_GONE_EXIT_UNKNOWN")


def checked_audits(value, observation):
    require(value["observation_id"] == observation["id"], "durable audit is not bound to this stopped roster")
    if observation.get("authorized_handoff") is not None:
        require(value.get("authorized_handoff") == observation["authorized_handoff"]
                and value.get("original_stop_evidence") == observation.get("original_stop_evidence"),
                "handoff durable audit must preserve its exact authority and original stop evidence")
    required_true = ("stop_audit_complete", "same_scientific_state", "accepted_records_valid",
                     "historical_budgets_and_attempts_preserved", "original_job_audits_used")
    require(all(value.get(key) is True for key in required_true), "complete original same-state audits are required")
    required_false = ("owner_term_observed", "any_sigint_observed", "stop_marker_present",
                      "known_hard_block", "known_implementation_failure")
    require(all(value.get(key) is False for key in required_false), "stop or hard error evidence forbids automatic recovery")
    jobs = value["jobs"]
    require(isinstance(jobs, dict) and isinstance(value["required_jobs"], list)
            and len(jobs) == len(value["required_jobs"]) and set(jobs) == set(value["required_jobs"]),
            "every required scientific job needs its original durable audit")
    for key, audit in jobs.items():
        require(audit.get("resume_allowed") is True and type(audit.get("unknown_calls")) is int
                and audit["unknown_calls"] == 0 and type(audit.get("progress_units")) is int
                and audit["progress_units"] >= value["progress_before"][key]
                and isinstance(audit.get("durable_progress_digest"), str) and audit["durable_progress_digest"],
                "UNKNOWN, lost progress or failed durable binding prevents recovery")
    return value


def probe_original_leases(protocol):
    require(Path(protocol["gpu_lease_root"]).resolve() == GPU_LEASE_ROOT.resolve()
            and set(protocol["gpu_uuids"]) == {str(gpu) for gpu in range(8)},
            "watchdog must probe the original eight project leases")
    paths = [SCIENCE_ROOT / "owner.lock"]
    paths.extend(GPU_LEASE_ROOT / ("gpu-" + digest(protocol["gpu_uuids"][str(gpu)]) + ".lock")
                 for gpu in range(8))
    bindings = protocol.get("original_lock_bindings")
    require(isinstance(bindings, dict) and set(bindings) == {str(path) for path in paths},
            "all nine original lock inode bindings must be registered")
    acquired = []
    try:
        for path in paths:
            expected = bindings[str(path)]
            require(type(expected.get("device")) is int and expected["device"] >= 0
                    and type(expected.get("inode")) is int and expected["inode"] > 0,
                    "invalid registered original lock inode")
            # Never create a replacement lock inode and call it the original.
            lease = path.open("r+")
            try:
                opened, current = os.fstat(lease.fileno()), path.lstat()
                identity = (opened.st_dev, opened.st_ino)
                require(stat.S_ISREG(opened.st_mode) and stat.S_ISREG(current.st_mode)
                        and identity == (current.st_dev, current.st_ino)
                        and identity == (expected["device"], expected["inode"]),
                        "original lease path or inode changed: " + str(path))
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                current = path.lstat()
                require(stat.S_ISREG(current.st_mode) and identity == (current.st_dev, current.st_ino),
                        "original lease path changed during its lock probe: " + str(path))
            except BlockingIOError:
                lease.close()
                return dict(available=False, busy_path=str(path), all_acquired_released=True,
                            leases_retained=0, is_GPU_capacity_admission=False)
            except BaseException:
                lease.close()
                raise
            acquired.append(lease)
        return dict(available=True, original_GPU_leases=8, scientific_owner_lock=True,
                    all_acquired_released=True, leases_retained=0, is_GPU_capacity_admission=False)
    finally:
        for lease in acquired:
            lease.close()


class Watchdog:
    def __init__(self, root, backend, *, lease_probe=probe_original_leases):
        self.root, self.backend, self.lease_probe = Path(root).resolve(), backend, lease_probe
        require(self.root == ROOT.resolve() and os.getuid() == os.geteuid() == OWNER_UID,
                "watchdog is restricted to its registered namespace and unprivileged account")
        self.protocol = backend.checked_protocol(self.root)
        require(self.protocol["policy"] == policy() and self.protocol["root"] == str(self.root)
                and self.protocol["scientific_root"] == str(SCIENCE_ROOT), "watchdog authorization changed")
        prepared = backend.checked_prepared(self.root)
        require(prepared["protocol_id"] == self.protocol["id"], "watchdog preparation belongs to another authorization")
        path = self.root / "state.json"
        if path.exists():
            self.state = checked(path)
            require(self.state["protocol_id"] == self.protocol["id"], "watchdog state belongs to another authorization")
        else:
            require(Path(prepared["initial_episode"]["root"]).resolve() == INITIAL_EPISODE_ROOT.resolve(),
                    "a fresh watchdog must initially observe the registered V59 episode")
            self.state = dict(schema="v61_guard_state.v1", protocol_id=self.protocol["id"],
                current_episode=_episode(prepared["initial_episode"], self.root), phase="WATCHING",
                next_episode_number=1, pending_request=None, launches_observed=0)
        _episode(self.state["current_episode"], self.root)
        require(self.state["phase"] in ("WATCHING", "AUDIT_PENDING", "REGISTERED", "DISPATCHING", "TERMINAL")
                and type(self.state["next_episode_number"]) is int and self.state["next_episode_number"] >= 1,
                "guard recovery state is malformed")
        pending = self.state["pending_request"]
        if pending is not None:
            require(pending["request_id"] == f"request{pending['episode_number']:06d}"
                    and Path(pending["directory"]).resolve() == self.root / "requests" / pending["request_id"]
                    and type(pending["launch_attempt"]) is int and pending["launch_attempt"] >= 1,
                    "pending request escaped its registered sequence/directory")

    def save(self):
        body = {key: value for key, value in self.state.items() if key != "id"}
        self.state = write_record(self.root / "state.json", body)

    def status(self, status, **fields):
        return write_record(self.root / "queue/status.json", dict(schema="v61_watchdog_tick_status.v1",
            protocol_id=self.protocol["id"], status=status, at_epoch=time.time(),
            current_episode=self.state["current_episode"], phase=self.state["phase"],
            automatic_recovery_terminal=(self.root / "terminal/record.json").exists(), **fields))

    def terminal(self, status, reason, **fields):
        path = self.root / "terminal/record.json"
        if not path.exists():
            write_record(path, dict(schema="v61_permanent_automatic_recovery_stop.v1",
                protocol_id=self.protocol["id"], status=status, reason=reason, at_epoch=time.time(),
                current_episode=self.state["current_episode"], automatic_recovery_allowed=False,
                new_user_authorization_required=True, **fields), immutable=True)
        self.state["phase"] = "TERMINAL"
        self.save()
        return self.status(status, reason=reason, **fields)

    def _observe(self):
        episode = self.state["current_episode"]
        raw = self.backend.observe_episode(self.root, episode, self.state)
        if Path(episode["root"]).resolve() == INITIAL_EPISODE_ROOT.resolve() and "id" not in raw:
            raw = bound({"schema": "v61_original_handoff_observation.v1", **raw})
        decision = observation_decision(raw, episode)
        if Path(episode["root"]).resolve() == INITIAL_EPISODE_ROOT.resolve():
            # V60 retains responsibility for control04 until the separately
            # registered, passive handoff has actually stopped it. Neither a
            # disappearance nor preparing six-worker code transfers authority.
            if decision["action"] == "TERMINAL" and decision["reason"] not in ("OWNER_TERM", "STOP"):
                return raw, decision
            identities = raw.get("identities", [])
            if (raw.get("identity_roster_complete") is True and identities
                    and all(row.get("alive") is False for row in identities)):
                authorized = self.backend.checked_authorized_handoff(raw)
                if authorized is not None:
                    require(authorized.get("authorized_handoff", {}).get("status")
                            == "FINAL_AUTHORIZED_STOP"
                            and authorized.get("original_observation_id") == raw.get("id"),
                            "precise completed handoff authorization is required")
                    accepted = observation_decision(authorized, episode)
                    require(accepted["action"] == "AUDIT" or (accepted["action"] == "TERMINAL"
                            and accepted["reason"] == "KNOWN_EXIT_NOT_AUTHORIZED"),
                            "handoff did not authorize a safe stopped roster")
                    return authorized, dict(action="AUDIT", status="RECOVERY_CANDIDATE",
                                            category="AUTHORIZED_V61_HANDOFF")
            if decision["action"] == "AUDIT":
                decision = dict(action="WAIT", status="WAITING_FOR_AUTHORIZED_HANDOFF")
        return raw, decision

    def _request(self, observation, category):
        pending = self.state["pending_request"]
        if pending is None:
            number = self.state["next_episode_number"]
            request_id = f"request{number:06d}"
            directory = self.root / "requests" / request_id
            intent_path = directory / "intent/record.json"
            if intent_path.exists():
                intent = checked(intent_path)
                require(intent["predecessor"] == self.state["current_episode"]
                        and intent["protocol_id"] == self.protocol["id"], "partial recovery request belongs to another predecessor")
            else:
                intent = write_record(intent_path, dict(schema="v61_cold_recovery_request.v1",
                    protocol_id=self.protocol["id"], request_id=request_id, episode_number=number,
                    predecessor=self.state["current_episode"], recovery_category=category,
                    old_exit_code_not_inferred=observation.get("actual_waitpid_observed") is False,
                    created_epoch=time.time()), immutable=True)
            pending = dict(request_id=request_id, directory=str(directory), intent_id=intent["id"],
                           episode_number=number, launch_attempt=1)
            self.state.update(pending_request=pending, next_episode_number=number + 1, phase="AUDIT_PENDING")
            self.save()
        return pending, Path(pending["directory"])

    def _accept_launch(self, receipt, launch):
        require(launch["status"] == "LAUNCHED" and launch["actual_child_created"] is True
                and launch["episode_root"] == receipt["episode_root"]
                and launch["request_id"] == receipt["request_id"]
                and launch["control_protocol_id"] == receipt["control_protocol_id"]
                and type(launch["pid"]) is int and launch["pid"] > 0
                and isinstance(launch["birth"], str) and launch["birth"],
                "actual successor launch identity is required")
        self.state.update(current_episode=dict(root=receipt["episode_root"], protocol_id=receipt["control_protocol_id"]),
            phase="WATCHING", pending_request=None, launches_observed=self.state["launches_observed"] + 1)
        self.save()
        return self.status("SUCCESSOR_LAUNCH_OBSERVED", actual_launch=launch,
                           launch_is_not_scientific_completion=True)

    def _retire_observer(self, observation, pending, directory):
        path = directory / "observer_retirement/record.json"
        if path.exists():
            result = checked(path)
        else:
            result = self.backend.retire_observer(self.root, self.state["current_episode"], observation,
                                                  pending["request_id"])
            require(result.get("scientific_processes_signaled") is False
                    and result.get("unowned_processes_signaled") is False
                    and result.get("observer_roster_verified") is True,
                    "monitor retirement must never target science or an unverified observer")
            if result.get("status") == "WAITING_FOR_OBSERVER_EXIT":
                write_record(directory / "observer_retirement_wait.json", result)
                return False
            require(result.get("status") in ("NO_LIVE_OBSERVER", "AUTHORIZED_MONITOR_RETIRED")
                    and result.get("remaining_independent_observers") == 0
                    and result.get("all_observer_identities_gone") is True,
                    "the old independent observer must be confirmed gone before its successor")
            if result["status"] == "AUTHORIZED_MONITOR_RETIRED":
                require(result.get("reason") == "authorized_monitor_retirement"
                        and result.get("observer_owner_uid") == OWNER_UID
                        and result.get("verified_readonly_CPU_observer") is True
                        and result.get("only_signal_sent") == 15,
                        "only the registered account's pure CPU observer TERM is permitted")
            write_record(path, result, immutable=True)
        return True

    def _launch(self, receipt, pending, directory):
        attempt = pending["launch_attempt"]
        launch_dir = directory / "launches" / f"attempt{attempt:04d}"
        if (launch_dir / "intent/record.json").exists():
            # A dead cron tick may have created its child before saving a reply.
            # Never invoke a second Popen unless a real no-child failure proves it safe.
            result = self.backend.reconcile_launch(self.root, receipt, pending["request_id"], attempt)
            if result.get("status") == "LAUNCHED":
                write_record(launch_dir / "reconciliation/record.json", result, immutable=True)
                return self._accept_launch(receipt, result)
            if result.get("status") != "NOT_LAUNCHED" or result.get("actual_child_created") is not False:
                return self.terminal("BLOCKED_AMBIGUOUS_LAUNCH", "UNOBSERVED_CHILD_CREATION_NOT_REPEATED")
            require(result.get("retry_safe_pre_child") is True and result.get("actual_errno") in TRANSIENT_ERRNOS,
                    "only proved transient pre-child failure permits another launch attempt")
            write_record(launch_dir / "no_child_proof/record.json", result, immutable=True)
            pending["launch_attempt"] += 1
            self.state["phase"] = "REGISTERED"
            self.save()
            return self.status("WAITING_AFTER_PROVED_PRE_CHILD_FAILURE")
        # Recheck only lightweight lifecycle/stop evidence after a potentially
        # long CPU registration; do not re-run the already completed job audit.
        latest, decision = self._observe()
        if decision["action"] == "TERMINAL":
            return self.terminal(decision["status"], decision["reason"])
        if decision["action"] != "AUDIT":
            return self.status(decision["status"], observation=latest)
        leases = self.lease_probe(self.protocol)
        if not leases["available"]:
            return self.status("WAITING_FOR_ORIGINAL_PROJECT_LEASES", lease_probe=leases)
        if (self.root / "STOP").exists() or (self.root / "control/stop_requested/record.json").exists():
            return self.terminal("STOPPED_NO_AUTO_RECOVERY", "STOP")
        write_record(launch_dir / "intent/record.json", dict(schema="v61_single_child_launch_intent.v1",
            protocol_id=self.protocol["id"], request_id=pending["request_id"], launch_attempt=attempt,
            episode_root=receipt["episode_root"], registration_id=receipt["registration_id"],
            created_epoch=time.time()), immutable=True)
        self.state["phase"] = "DISPATCHING"
        self.save()
        try:
            result = self.backend.launch_registered(self.root, receipt, pending["request_id"], attempt)
        except Exception as error:
            write_record(launch_dir / "callback_interrupted/record.json", dict(
                schema="v61_launch_callback_interrupted.v1", error_type=type(error).__name__,
                actual_errno=getattr(error, "errno", None), actual_child_created=None,
                automatic_duplicate_launch=False), immutable=True)
            return self.status("WAITING_FOR_LAUNCH_RECONCILIATION")
        write_record(launch_dir / "result/record.json", result, immutable=True)
        if result.get("status") == "LAUNCHED":
            return self._accept_launch(receipt, result)
        # A failed return still enters the same evidence-only reconciliation
        # path on the next tick; no launch is repeated in this invocation.
        return self.status("WAITING_FOR_LAUNCH_RECONCILIATION")

    def run(self):
        terminal_path = self.root / "terminal/record.json"
        if terminal_path.exists():
            terminal = checked(terminal_path)
            return self.status(terminal["status"], reason=terminal["reason"])
        if (self.root / "STOP").exists() or (self.root / "control/stop_requested/record.json").exists():
            return self.terminal("STOPPED_NO_AUTO_RECOVERY", "STOP")
        observation, decision = self._observe()
        if decision["action"] == "TERMINAL":
            return self.terminal(decision["status"], decision["reason"])
        pending = self.state["pending_request"]
        if pending is not None:
            directory = Path(pending["directory"])
            receipt_path = directory / "registration/record.json"
            intent_path = directory / "launches" / f"attempt{pending['launch_attempt']:04d}" / "intent/record.json"
            if receipt_path.exists() and intent_path.exists():
                # A created successor can already own leases and append new
                # scientific dispatches absent from its predecessor's journal.
                # Only its token-bound actual launch may resolve that window;
                # an existing intent takes the read-only branch in _launch.
                return self._launch(checked(receipt_path), pending, directory)
        if decision["action"] == "WAIT":
            return self.status(decision["status"], observation=observation)
        # This probe retains no locks and does not authorize CUDA allocation.
        leases = self.lease_probe(self.protocol)
        if not leases["available"]:
            return self.status("WAITING_FOR_ORIGINAL_PROJECT_LEASES", lease_probe=leases)
        pending, directory = self._request(observation, decision["category"])
        observation_path = directory / "exit_observation/record.json"
        observed = checked(observation_path) if observation_path.exists() else write_record(observation_path, {
            "schema": "v61_actual_exit_roster_observation.v1", **observation}, immutable=True)
        receipt_path = directory / "registration/record.json"
        if receipt_path.exists():
            receipt = checked(receipt_path)
        else:
            audit_path = directory / "durable_audit/record.json"
            if audit_path.exists():
                audits = checked_audits(checked(audit_path), observed)
            else:
                raw_audits = self.backend.audit_durable(self.root, self.state["current_episode"], observed)
                audits = checked_audits(write_record(audit_path, raw_audits, immutable=True), observed)
            # Stop markers arriving during CPU-only audit take precedence.
            if (self.root / "STOP").exists() or (self.root / "control/stop_requested/record.json").exists():
                return self.terminal("STOPPED_NO_AUTO_RECOVERY", "STOP")
            latest, retirement_decision = self._observe()
            if retirement_decision["action"] == "TERMINAL":
                return self.terminal(retirement_decision["status"], retirement_decision["reason"])
            if retirement_decision["action"] != "AUDIT":
                return self.status(retirement_decision["status"], observation=latest)
            retirement_admission = write_record(directory / "latest_monitor_retirement_admission.json", {
                "schema": "v61_fresh_monitor_retirement_admission.v1", **latest})
            if not self._retire_observer(retirement_admission, pending, directory):
                return self.status("WAITING_FOR_OWN_READONLY_OBSERVER_EXIT")
            receipt = self.backend.register_episode(self.root, self.state["current_episode"], observed,
                                                    audits, pending["request_id"])
            expected = self.root / "episodes" / f"episode{pending['episode_number']:06d}"
            require(Path(receipt["episode_root"]).resolve() == expected
                    and receipt["scientific_root"] == str(SCIENCE_ROOT)
                    and receipt["request_id"] == pending["request_id"]
                    and receipt["predecessor_root"] == self.state["current_episode"]["root"]
                    and receipt["ready_for_launch"] is True
                    and receipt["budgets_reset"] is False and receipt["attempts_reset"] is False
                    and isinstance(receipt["control_protocol_id"], str) and receipt["control_protocol_id"]
                    and isinstance(receipt["registration_id"], str) and receipt["registration_id"],
                    "successor must be a fresh same-budget registered episode")
            receipt = write_record(receipt_path, receipt, immutable=True)
            self.state["phase"] = "REGISTERED"
            self.save()
        return self._launch(receipt, pending, directory)


def tick(root=ROOT, *, backend=None, lease_probe=probe_original_leases):
    root = Path(root).resolve()
    require(root == ROOT.resolve() and root.is_dir() and os.getuid() == os.geteuid() == OWNER_UID,
            "watchdog must be prepared in its registered namespace and run as its original account")
    with (root / "tick.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return dict(status="SKIP_TICK_ALREADY_RUNNING", new_scientific_processes=0)
        terminal_path = root / "terminal/record.json"
        if terminal_path.exists():
            return checked(terminal_path)
        if (root / "STOP").exists() or (root / "control/stop_requested/record.json").exists():
            return write_record(terminal_path, dict(schema="v61_preflight_terminal_fence.v1",
                status="STOPPED_NO_AUTO_RECOVERY", reason="STOP", at_epoch=time.time(),
                automatic_recovery_allowed=False, new_user_authorization_required=True), immutable=True)
        try:
            backend = backend or importlib.import_module("finqa_v61_registration")
            guard = Watchdog(root, backend, lease_probe=lease_probe)
        except OSError as error:
            if error.errno in TRANSIENT_ERRNOS:
                return write_record(root / "queue/status.json", dict(schema="v61_preflight_io_wait.v1",
                    status="WAITING_FOR_TRANSIENT_PREFLIGHT_IO", actual_errno=error.errno,
                    at_epoch=time.time(), new_scientific_processes=0))
            return write_record(terminal_path, dict(schema="v61_preflight_terminal_fence.v1",
                status="BLOCKED_PREFLIGHT_CONTRACT", reason="PREFLIGHT_IO_OR_BINDING_FAILURE",
                error_type=type(error).__name__, actual_errno=error.errno,
                automatic_recovery_allowed=False, new_user_authorization_required=True), immutable=True)
        except Exception as error:
            return write_record(terminal_path, dict(schema="v61_preflight_terminal_fence.v1",
                status="BLOCKED_PREFLIGHT_CONTRACT", reason="PREFLIGHT_IMPLEMENTATION_OR_BINDING_FAILURE",
                error_type=type(error).__name__, automatic_recovery_allowed=False,
                new_user_authorization_required=True), immutable=True)
        try:
            return guard.run()
        except OSError as error:
            if error.errno in TRANSIENT_ERRNOS:
                return guard.status("WAITING_FOR_TRANSIENT_READ_OR_REGISTRATION_IO", actual_errno=error.errno)
            return guard.terminal("BLOCKED_GUARD_IO_OR_STATE", "UNCLASSIFIED_IO", actual_errno=error.errno)
        except Exception as error:
            return guard.terminal("BLOCKED_DURABLE_OR_IMPLEMENTATION_AUDIT", "ORIGINAL_AUDIT_OR_CONTROL_CONTRACT_FAILED",
                                  error_type=type(error).__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    result = tick(args.root)
    print(json.dumps(dict(status=result["status"], id=result.get("id")), sort_keys=True))


if __name__ == "__main__":
    main()
