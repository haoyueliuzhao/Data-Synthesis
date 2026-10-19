"""Real, conservative lifecycle callbacks for the independently frozen watchdog.

Normal observations use only small lifecycle JSON and /proc identities. Original
scientific imports and audits are delayed until every blocking identity is gone.
No callback changes scientific data, guesses an OS exit code, or signals workers.
"""
from __future__ import annotations

import argparse
import copy
import ctypes
import hashlib
import importlib
import json
import os
from pathlib import Path
import runpy
import secrets
import signal
import subprocess
import sys
import time

from finqa_v61_binding import (MASTER_ROOT, PYTHON, REPO, SCIENCE_ROOT, SOURCE_CONTROL_ROOT,
    SOURCE_CONTROL_PROTOCOL_ID, SCIENTIFIC_PROTOCOL_ID, checked_record, digest,
    episode_root, load_v59_module, require, resource_override)
import finqa_v61_registration as registration
from finqa_v61_watchdog import bound, write_record, TRANSIENT_ERRNOS

checked_protocol = registration.checked_protocol
checked_prepared = registration.checked_prepared
checked_master_protocol = registration.checked_master_protocol
entry, read_ref = registration.entry, registration.read_ref


def identity(pid, birth):
    require(type(pid) is int and pid > 0 and isinstance(birth, str) and birth,
            "real PID and birth are required")
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return dict(pid=pid, birth=birth, alive=False, disposition="PID_ABSENT")
    return dict(pid=pid, birth=birth, alive=fields[19] == birth,
        observed_birth=fields[19], proc_state=fields[0],
        disposition="SAME_IDENTITY" if fields[19] == birth else "PID_REUSED")


def current_birth(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (FileNotFoundError, ProcessLookupError):
        return None


def _checked_optional(path, *, plain=False):
    path = Path(path)
    if not path.is_file():
        return None
    return json.loads(path.read_bytes()) if plain else checked_record(path)


def _episode_protocol(episode):
    root = Path(episode["root"]).resolve()
    require(root == SOURCE_CONTROL_ROOT or episode_root(root) == root, "unregistered predecessor root")
    value = checked_record(root / "protocol/record.json")
    require(value["id"] == episode["protocol_id"] and value["scientific_root"] == str(SCIENCE_ROOT)
            and value["scientific_protocol_id"] == SCIENTIFIC_PROTOCOL_ID,
            "predecessor scientific/control binding changed")
    if root == SOURCE_CONTROL_ROOT:
        require(value["id"] == SOURCE_CONTROL_PROTOCOL_ID, "initial V59 protocol changed")
    return value


def _journal(root, protocol):
    value = _checked_optional(root / "journal/state.json")
    if value is not None:
        require(value["protocol_id"] == SCIENTIFIC_PROTOCOL_ID
                and value["control_protocol_id"] == protocol["id"], "foreign scientific journal")
        return value
    prepared = checked_record(root / "prepared/record.json")
    return dict(prepared, job_states=prepared["initial_job_states"], active_jobs=[])


def _attempt_path(row):
    path = Path(row["directory"]).resolve()
    require(path.is_relative_to(SCIENCE_ROOT) and path.parent.name == "attempts"
            and path.name == f"attempt{row['attempt']:04d}", "scientific attempt escaped its stable root")
    return path


def _launch(path, row=None):
    value = checked_record(path)
    require(value["protocol_id"] == SCIENTIFIC_PROTOCOL_ID, "foreign scientific launch")
    if row is not None:
        require(value["job"]["job_id"] == row["job_id"] and value["attempt"] == row["attempt"],
                "scientific launch attempt changed")
    require(type(value["pid"]) is int and isinstance(value["birth"], str) and value["birth"],
            "launch lacks a real complete identity")
    return value


def _signal_paths(root, current_attempts):
    paths = list(root.glob("signals/*/received.jsonl"))
    paths.extend(Path(row["directory"]) / "signals/received.jsonl" for row in current_attempts)
    return sorted({path for path in paths if path.is_file()})


def _stop_evidence(root, journal, current_attempts):
    marker = (root / "STOP").exists() or (root / "control/stop_requested/record.json").exists()
    owner_term, any_int, unknown_signal = False, False, False
    signal_refs = []
    maintenance = _checked_optional(root / "observer/retirement_intent/record.json")
    for path in _signal_paths(root, current_attempts):
        raw = path.read_bytes()
        signal_refs.append(dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw)))
        for line in raw.splitlines():
            event = json.loads(line)
            # A monitor is not a scientific stop authority. Its own ordinary
            # termination is separately visible as monitor lifecycle evidence.
            if event.get("role") == "observer":
                continue
            if event.get("schema") != "v59_received_signal_kernel_receipt.v1":
                # Non-signal observation records cannot assert a safe signal.
                if event.get("signal") in (2, 15):
                    unknown_signal = True
                continue
            number = event.get("signal")
            expected = load_v59_module("finqa_v59_signals").signal_decision(
                number, event.get("si_pid"), event.get("si_uid"), event.get("si_code"))
            require(event.get("decision") == expected and event.get("provenance") == "kernel_sigwaitinfo",
                    "signal decision is not the registered kernel-field policy")
            allowed_retirement = bool(maintenance and event.get("role") == "observer"
                and event.get("pid") == maintenance["pid"] and number == 15
                and event.get("si_uid") == 1004 and event.get("si_pid") == maintenance["sender_pid"]
                and event.get("at_epoch", 0) >= maintenance["created_epoch"])
            if allowed_retirement:
                continue
            if number == 2:
                any_int = True
            elif number == 15 and event.get("decision", {}).get("filtered") is not True:
                if event.get("si_uid") == 1004:
                    owner_term = True
                else:
                    unknown_signal = True
    hard = any(value.get("status") in ("HARD_BLOCKED", "DEPENDENCY_BLOCKED")
               for value in journal["job_states"].values())
    implementation = False
    # A previously recorded retry-safe resource decision is preserved. A
    # failed current attempt without such a decision is never called SIGKILL.
    errors = []
    for path in sorted(root.glob("controllers/attempt*/failure/record.json")):
        failure = checked_record(path)
        expected_control = journal.get("control_protocol_id") or checked_record(root / "protocol/record.json")["id"]
        require(failure.get("control_protocol_id") == expected_control,
            "controller failure belongs to another episode")
        retry_safe = (failure.get("transient_without_active_children") is True
                      and failure.get("actual_errno") in TRANSIENT_ERRNOS
                      and failure.get("active_children") == [])
        implementation |= not retry_safe
        errors.append(dict(path=str(path), error_type=failure.get("error_type"), retry_safe=retry_safe))
    runner_failure = _checked_optional(root / "runner/failure/record.json")
    if runner_failure:
        implementation = True
        errors.append(dict(path=str(root / "runner/failure/record.json"),
                           error_type=runner_failure.get("error_type"), retry_safe=False))
    for row in current_attempts:
        directory = Path(row["directory"])
        launch = _checked_optional(directory / "launch/record.json")
        if launch:
            resource_path = SCIENCE_ROOT / "resources" / row["job_id"] / f"pid{launch['pid']}/closeout/record.json"
            resource = _checked_optional(resource_path)
            if resource:
                require(resource["pid"] == launch["pid"] and resource["job_id"] == row["job_id"],
                        "resource closeout belongs to another scientific process")
                report = resource["resources"]
                rss_limit = (160 if launch["job"]["kind"] == "class" else 192) * (1024 ** 3)
                hard |= (report.get("peak_allocated_bytes", 0) > 76 * (1024 ** 3)
                         or report.get("peak_rss_bytes", 0) > rss_limit)
                if report.get("received_signals"):
                    unknown_signal = True
        for basename in ("launch_failure", "acceptance_failure"):
            path = directory / basename / "record.json"
            problem = _checked_optional(path)
            if problem:
                safe = (basename == "launch_failure" and problem.get("actual_child_created") is False
                        and problem.get("classification") == "RETRY_SAFE_IO"
                        and problem.get("actual_errno") in TRANSIENT_ERRNOS)
                implementation |= not safe
                errors.append(dict(path=str(path), error_type=problem.get("error_type"), retry_safe=safe))
        failure = _checked_optional(directory / "failure/record.json")
        if failure is not None:
            actual = _checked_optional(directory / "actual_exit/record.json")
            state = journal["job_states"][row["job_id"]]
            settled_retry = actual is not None and state["status"] in (
                "BACKOFF", "RESOURCE_COOLDOWN", "PENDING", "RUNNING", "COMPLETE", "PRE_DISPATCH_AUDIT_WAIT")
            types = {item["type"] for item in failure.get("exception_chain", [])}
            if types & {"ExplicitStop", "KeyboardInterrupt", "ReplayPaused"}:
                unknown_signal = True
            if not settled_retry:
                implementation = True
            errors.append(dict(path=str(directory / "failure/record.json"),
                               exception_type=failure.get("exception_type"), settled_retry=settled_retry))
    reason = ("STOP" if marker else "SIGINT" if any_int else "OWNER_TERM" if owner_term
              else "HARD_BLOCKED" if hard else "IMPLEMENTATION_FAILURE" if implementation
              else "OWNER_TERM" if unknown_signal else None)
    return dict(known_terminal_reason=reason, stop_marker_present=marker,
        owner_term_observed=owner_term, any_sigint_observed=any_int,
        unfiltered_unknown_stop_signal=unknown_signal, known_hard_block=hard,
        known_implementation_failure=implementation, signal_logs=signal_refs, failures=errors)


def observe_episode(root, episode, state):
    root = Path(root).resolve()
    require(root == MASTER_ROOT, "foreign watchdog root")
    protocol = _episode_protocol(episode)
    control = Path(episode["root"])
    journal = _journal(control, protocol)
    roster, unresolved, current_attempts = {}, [], []

    def add(value, role, path=None):
        key = (value["pid"], value["birth"])
        row = dict(identity(*key), role=role)
        if path:
            row["launch_path"] = str(path)
        require(key not in roster or roster[key]["role"] == role, "identity changed lifecycle role")
        roster[key] = row

    controls = [(control / "supervisor/launch/record.json", "supervisor"),
                (control / "runner/launch/record.json", "runner")]
    controls.extend((path, "controller") for path in sorted(control.glob("controllers/attempt*/launch/record.json")))
    controls.extend((path, "controller") for path in sorted(control.glob("supervisor/attempts/attempt*/launch/record.json")))
    for path, role in controls:
        launch = _checked_optional(path)
        if launch:
            require(launch.get("control_protocol_id") == protocol["id"], "foreign control launch")
            add(launch, role, path)
    # Token-bound child startup is earlier than heavy scientific imports and
    # the legacy supervisor launch. It closes that observation gap.
    for role in ("supervisor",):
        directory = control / "runner/children" / role
        intent = _checked_optional(directory / "intent/record.json")
        startup = _checked_optional(directory / "startup/record.json")
        launched = _checked_optional(directory / "launch/record.json")
        if startup:
            require(intent and startup["dispatch_token_sha256"] == intent["dispatch_token_sha256"]
                    and startup["control_protocol_id"] == protocol["id"], "unbound early child startup")
            add(startup, role, directory / "startup/record.json")
        elif launched:
            require(intent and launched["control_protocol_id"] == protocol["id"]
                    and launched["role"] == role and launched["actual_child_created"] is True,
                    "unbound parent-observed child launch")
            add(launched, role, directory / "launch/record.json")
        elif intent and not (directory / "launch_failure/record.json").is_file():
            unresolved.append(str(directory))
    for row in journal["active_jobs"]:
        add(row, "scientific_worker")
    live = any(row["alive"] for row in roster.values())
    # Only a stopped roster needs a complete per-attempt directory audit.
    if not live:
        # The immutable legacy supervisor creates this directory before its
        # controller Popen. Neither a launch nor the child's own launch means
        # child creation is unobserved, not that no child exists.
        for directory in sorted((control / "supervisor/attempts").glob("attempt*")):
            own_launch = control / "controllers" / directory.name / "launch/record.json"
            if directory.is_dir() and not (directory / "launch/record.json").is_file() and not own_launch.is_file():
                unresolved.append(str(directory))
        history_paths = {_attempt_path(row) for row in journal["attempt_history"]}
        disk_paths = {path.parent.parent.resolve() for pattern in
            ("stages/seed*/*/attempts/attempt*/dispatch_intent/record.json",
             "evaluations/jobs/*/attempts/attempt*/dispatch_intent/record.json")
            for path in SCIENCE_ROOT.glob(pattern)}
        unresolved.extend(str(path) for path in disk_paths - history_paths)
        for row in journal["attempt_history"]:
            directory = _attempt_path(row)
            launch = _checked_optional(directory / "launch/record.json")
            intent = _checked_optional(directory / "dispatch_intent/record.json")
            if launch:
                launch = _launch(directory / "launch/record.json", row)
                if launch.get("control_protocol_id") == protocol["id"]:
                    add(launch, "scientific_worker", directory / "launch/record.json")
                    current_attempts.append(row)
            elif intent and intent.get("control_protocol_id") == protocol["id"]:
                current_attempts.append(row)
                failed = _checked_optional(directory / "launch_failure/record.json")
                if failed is None or failed.get("actual_child_created") is not False:
                    unresolved.append(str(directory))
    else:
        # Healthy path stays light; no checkpoint, task or feedback tree reads.
        active = {(row["job_id"], row["attempt"]) for row in journal["active_jobs"]}
        current_attempts = [row for row in journal["attempt_history"]
                            if (row["job_id"], row["attempt"]) in active]
    stop = _stop_evidence(control, journal, current_attempts)
    complete = _checked_optional(control / "closeout/record.json")
    actual = _checked_optional(control / "runner/supervisor_actual_exit/record.json")
    # Initial control04 was not our child. Its disappearance remains unknown;
    # a successor runner can bind a real observed supervisor waitpid.
    if actual:
        require(actual["control_protocol_id"] == protocol["id"] and actual["actual_waitpid_observed"] is True
                and type(actual["returncode"]) is int
                and any(row["role"] == "supervisor" and (row["pid"], row["birth"]) == (actual["pid"], actual["birth"])
                        for row in roster.values()),
                "runner exit observation is not the actual supervisor waitpid")
    if complete:
        require(complete["protocol_id"] == SCIENTIFIC_PROTOCOL_ID
                and complete["control_protocol_id"] == protocol["id"], "foreign scientific closeout")
    return dict(episode_root=str(control), control_protocol_id=protocol["id"],
        scientific_protocol_id=SCIENTIFIC_PROTOCOL_ID, identities=list(roster.values()),
        identity_roster_complete=bool(roster and not unresolved), unresolved_dispatches=unresolved,
        actual_waitpid_observed=actual is not None, actual_returncode=actual["returncode"] if actual else None,
        experiment_complete=bool(complete and complete.get("status") == "COMPLETE"),
        journal_id=journal.get("id"), observation_epoch=time.time(), **stop)


def _load_science():
    sys.path.insert(0, str(SCIENCE_ROOT / "implementation"))
    scientific = importlib.import_module("finqa_v56_registration")
    require(Path(scientific.__file__).resolve() == SCIENCE_ROOT / "implementation/finqa_v56_registration.py",
            "durable audits must use the original frozen scientific registration")
    scientific.modules()  # Bind the original scientific closure before lifecycle helpers.
    return (importlib.import_module("finqa_v56_worker"),
            importlib.import_module("finqa_v54_controller"),
            importlib.import_module("finqa_v54_evaluation"))


def checked_authorized_handoff(observation):
    """Normalize only the exact completed maintenance stop, preserving raw evidence.

    observe_episode itself remains conservative: owner TERM and STOP are always
    visible there. The handoff validator is the sole authority for this one
    transition, and cannot authorize a user STOP, SIGINT, hard failure or another
    episode. Successor episodes continue through the unchanged ordinary guards.
    """
    if Path(observation["episode_root"]).resolve() != SOURCE_CONTROL_ROOT:
        return None
    if "id" not in observation:
        observation = bound({"schema": "v61_original_handoff_observation.v1", **observation})
    require(observation["control_protocol_id"] == SOURCE_CONTROL_PROTOCOL_ID,
            "handoff source control identity changed")
    require(not (MASTER_ROOT / "STOP").exists()
            and not (MASTER_ROOT / "control/stop_requested/record.json").exists()
            and not (SOURCE_CONTROL_ROOT / "STOP").exists(),
            "explicit STOP cannot be maintenance authorization")
    require(observation.get("any_sigint_observed") is False
            and observation.get("unfiltered_unknown_stop_signal") is False
            and observation.get("known_hard_block") is False
            and observation.get("known_implementation_failure") is False,
            "SIGINT, unknown signal or hard error cannot be an authorized handoff")
    require(observation.get("known_terminal_reason") in (None, "OWNER_TERM", "STOP"),
            "scientific or numerical failure cannot be an authorized handoff")
    require(observation.get("identity_roster_complete") is True
            and observation.get("identities")
            and all(row.get("alive") is False for row in observation["identities"]),
            "authorized handoff requires every registered identity to be gone")
    episode = dict(root=str(SOURCE_CONTROL_ROOT), protocol_id=SOURCE_CONTROL_PROTOCOL_ID)
    receipt = importlib.import_module("finqa_v61_handoff").validate_authorized_stop(
        MASTER_ROOT, episode, observation)
    if receipt is None:
        return None
    require(receipt.get("status") == "FINAL_AUTHORIZED_STOP" and receipt.get("id"),
            "handoff validation did not return its completed bound receipt")
    fields = ("known_terminal_reason", "stop_marker_present", "owner_term_observed",
              "any_sigint_observed", "unfiltered_unknown_stop_signal", "known_hard_block",
              "known_implementation_failure", "signal_logs", "failures")
    original = {key: copy.deepcopy(observation.get(key)) for key in fields}
    value = {key: copy.deepcopy(item) for key, item in observation.items() if key != "id"}
    value.update(schema="v61_precisely_authorized_handoff_observation.v1",
        original_observation_id=observation["id"], original_stop_evidence=original,
        authorized_handoff=receipt, known_terminal_reason=None, stop_marker_present=False,
        owner_term_observed=False, stop_flags_are_effective_after_precise_handoff_authorization=True)
    return bound(value)


def audit_durable(root, episode, observation):
    require(observation["identity_roster_complete"] is True and observation["identities"]
            and all(row["alive"] is False for row in observation["identities"])
            and observation["known_terminal_reason"] is None, "stopped safe roster required before original audits")
    control = Path(episode["root"])
    protocol = _episode_protocol(episode)
    journal = _journal(control, protocol)
    require(journal["id"] == observation["journal_id"], "journal changed after stopped observation")
    fresh = observe_episode(root, episode, {})
    if Path(episode["root"]).resolve() == SOURCE_CONTROL_ROOT:
        fresh = checked_authorized_handoff(fresh)
        require(fresh is not None and observation.get("authorized_handoff", {}).get("id")
                == fresh["authorized_handoff"]["id"], "initial audit lacks its exact final handoff authority")
    require(fresh["identity_roster_complete"] and all(row["alive"] is False for row in fresh["identities"])
            and fresh["known_terminal_reason"] is None, "process or stop evidence changed before durable audit")
    directory = Path(root) / "backend/audits" / observation["id"]
    complete_path = directory / "record.json"
    if complete_path.exists():
        return checked_record(complete_path)
    accepted = copy.deepcopy(journal["accepted"])
    accepted_details = {}
    for key, reference in accepted.items():
        value = read_ref(reference)
        actual, result = read_ref(value["actual_exit"]), read_ref(value["result"])
        require(value["actual_exit_zero"] is True and actual["actual_waitpid_observed"] is True
                and actual["returncode"] == 0 and result["status"] == "COMPLETE"
                and result["resources"]["all_gates_passed"] is True,
                "accepted job lost its actual exit or scientific/resource validation")
        accepted_details[key] = dict(accepted=reference, result=value["result"], actual_exit=value["actual_exit"])
    worker, controller, evaluation = _load_science()
    parents = {str(seed): checked_record(SCIENCE_ROOT / f"parents/seed{seed}/record.json") for seed in (137, 251, 389)}
    jobs = controller.core_jobs(parents)
    if journal["evaluation_registered"]:
        plan = evaluation.checked_plan(SCIENCE_ROOT)
        jobs.update({key: dict(job, kind="generate", dependencies=list(jobs), priority=6)
                     for key, job in plan["jobs"].items()})
    require(set(jobs) == set(journal["job_states"]), "original job roster changed")
    required = sorted(set(jobs) - set(accepted))
    audits, before, states = {}, {}, copy.deepcopy(journal["job_states"])
    for key in required:
        cache = directory / "jobs" / key / "record.json"
        if cache.exists():
            saved = checked_record(cache)
            require(saved["observation_id"] == observation["id"] and saved["job"] == jobs[key],
                    "cached original audit belongs to another stopped boundary")
            audit = saved["audit"]
        else:
            audit = worker.audit_job_resume(SCIENCE_ROOT, jobs[key])
            write_record(cache, dict(schema="v61_once_original_job_audit.v1", observation_id=observation["id"],
                job=jobs[key], original_worker=str(worker.__file__), audit=audit), immutable=True)
        previous = journal["job_states"][key]
        require(audit["resume_allowed"] is True and audit["unknown_calls"] == 0
                and audit["progress_units"] >= previous["progress_units"], "durable binding, UNKNOWN or progress regression")
        audits[key], before[key] = audit, previous["progress_units"]
        states[key].update(status="PENDING", next_eligible_epoch=max(0.0, previous.get("next_eligible_epoch", 0.0)),
            progress_units=audit["progress_units"], durable_progress_digest=audit["durable_progress_digest"],
            watchdog_same_state_recovery=True)
        for stale in ("pid", "birth", "gpu_index"):
            states[key].pop(stale, None)
    previous_prepared = checked_record(control / "prepared/record.json")
    all_audits = copy.deepcopy(previous_prepared["resume_audits"])
    all_audits.update(audits)
    # Accepted jobs are reused from their actual accepted result; do not rescan
    # 2,100 complete feedback episodes merely to update a cosmetic progress ID.
    for key in accepted:
        if key not in all_audits:
            all_audits[key] = dict(resume_allowed=True, unknown_calls=0,
                progress_units=states[key]["progress_units"], evidence=[accepted[key]],
                durable_progress_digest=digest(accepted_details[key]), accepted_readonly_reuse=True)
    history = copy.deepcopy(journal["attempt_history"])
    unknown, attempts, identities = [], [], []
    for row in history:
        path = _attempt_path(row)
        launch = _checked_optional(path / "launch/record.json")
        if launch is None:
            failure = checked_record(path / "launch_failure/record.json")
            require(failure["actual_child_created"] is False, "unsettled Popen hole cannot be replayed")
            attempts.append(dict(row, actual_child_created=False, launch_failure=entry(path / "launch_failure/record.json")))
            continue
        launch = _launch(path / "launch/record.json", row)
        observed = identity(launch["pid"], launch["birth"])
        require(observed["alive"] is False, "an inherited registered worker is still present")
        identities.append(dict(observed, role="scientific_worker", job_id=row["job_id"], attempt=row["attempt"]))
        value = dict(row, pid=launch["pid"], birth=launch["birth"], launch=entry(path / "launch/record.json"),
                     old_returncode=None, actual_exit=None)
        actual = _checked_optional(path / "actual_exit/record.json")
        if actual:
            require(actual["actual_waitpid_observed"] is True
                    and (actual["pid"], actual["birth"], actual["job_id"], actual["attempt"])
                    == (launch["pid"], launch["birth"], row["job_id"], row["attempt"]), "actual exit binding differs")
            value.update(old_returncode=actual["returncode"], actual_exit=entry(path / "actual_exit/record.json"))
        else:
            unknown.append(value)
        attempts.append(value)
    for key, state in states.items():
        sequence = sorted(row["attempt"] for row in history if row["job_id"] == key)
        require(sequence == list(range(1, state["attempts"] + 1)), "actual attempt count cannot reset or skip")
        require((state["status"] == "COMPLETE") == (key in accepted), "only accepted actual exits may remain COMPLETE")
    identity_record = write_record(directory / "identities/record.json", dict(
        schema="v61_same_state_old_worker_identity_observation.v1", observation_id=observation["id"],
        identities=identities, old_missing_returncode=None, exit_zero_not_fabricated=True), immutable=True)
    del identity_record
    for row in unknown:
        row["identity_exit"] = entry(directory / "identities/record.json")
    journal_path = control / "journal/state.json"
    source_journal = journal_path if journal_path.is_file() else control / "prepared/record.json"
    bootstrap = dict(initial_job_states=states, attempt_history=history, accepted=accepted,
        evaluation_registered=journal["evaluation_registered"], resource_wait_seconds=journal["resource_wait_seconds"],
        known_unobserved_attempts=unknown, all_old_attempts=attempts, resume_audits=all_audits,
        process_identities=identities, old_journal=entry(source_journal))
    require(not sys.modules["torch"].cuda.is_initialized(), "durable admission audit must remain CPU-only")
    return write_record(complete_path, dict(schema="v61_original_same_science_durable_admission.v1",
        observation_id=observation["id"], stop_audit_complete=True, same_scientific_state=True,
        accepted_records_valid=True, historical_budgets_and_attempts_preserved=True, original_job_audits_used=True,
        owner_term_observed=False, any_sigint_observed=False, stop_marker_present=False,
        known_hard_block=False, known_implementation_failure=False, required_jobs=required,
        progress_before=before, jobs=audits, bootstrap=bootstrap, accepted_details=accepted_details,
        authorized_handoff=observation.get("authorized_handoff"),
        original_stop_evidence=observation.get("original_stop_evidence"),
        stop_flags_are_effective_after_precise_handoff_authorization=bool(observation.get("authorized_handoff")),
        resource_override=resource_override(),
        new_feedback_budget=0, model_or_API_calls=0, CUDA_initialized=False), immutable=True)


def _observer_launch(control):
    path = control / "observer/launch/record.json"
    value = _checked_optional(path, plain=True)
    early = _checked_optional(control / "runner/children/observer/startup/record.json")
    intent = _checked_optional(control / "runner/children/observer/intent/record.json")
    launched = _checked_optional(control / "runner/children/observer/launch/record.json")
    if value:
        require(value["schema"] == "v58_independent_observer_launch.v1"
                and value["root"] == str(control) and value["science_root"] == str(SCIENCE_ROOT),
                "observer is not the registered read-only scientific monitor")
        if early:
            require((value["pid"], value["birth"]) == (early["pid"], early["birth"]), "observer startup identity changed")
        return value
    if early:
        require(intent and early["dispatch_token_sha256"] == intent["dispatch_token_sha256"]
                and early["role"] == "observer", "unbound early observer identity")
        return early
    if launched:
        require(intent and launched["control_protocol_id"] == intent["control_protocol_id"]
                and launched["role"] == "observer" and launched["actual_child_created"] is True,
                "unbound parent-observed observer launch")
        return launched
    require(intent is None or (control / "runner/children/observer/launch_failure/record.json").is_file(),
            "unsettled observer launch cannot be ignored")
    return None


def _owner_uids(pid):
    status = Path(f"/proc/{pid}/status").read_text()
    return tuple(map(int, next(line.split()[1:] for line in status.splitlines() if line.startswith("Uid:"))))


def _pidfd_syscall(number, *arguments):
    # This project's Python does not expose os.pidfd_open, although the Linux
    # x86-64 kernel supports it. Bind the documented architecture, never guess
    # syscall numbers on another platform and never fall back to a racy kill.
    require(sys.platform == "linux" and os.uname().machine == "x86_64",
            "pidfd syscall fallback is only registered for Linux x86-64")
    library = ctypes.CDLL(None, use_errno=True)
    library.syscall.restype = ctypes.c_long
    result = library.syscall(ctypes.c_long(number), *arguments)
    if result < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return int(result)


def _pidfd_open(pid):
    return (os.pidfd_open(pid, 0) if hasattr(os, "pidfd_open") else
            _pidfd_syscall(434, ctypes.c_int(pid), ctypes.c_uint(0)))


def _pidfd_term(descriptor):
    if hasattr(signal, "pidfd_send_signal"):
        signal.pidfd_send_signal(descriptor, signal.SIGTERM)
    else:
        _pidfd_syscall(424, ctypes.c_int(descriptor), ctypes.c_int(signal.SIGTERM),
                       ctypes.c_void_p(), ctypes.c_uint(0))


def retire_observer(root, episode, observation, request_id):
    require(observation["identity_roster_complete"] and observation["identities"]
            and all(row["alive"] is False for row in observation["identities"]),
            "observer retirement requires a fresh fully stopped scientific roster")
    for row in observation["identities"]:
        require(identity(row["pid"], row["birth"])["alive"] is False, "scientific identity revived before observer retirement")
    control = Path(episode["root"])
    protocol = _episode_protocol(episode)
    observer = _observer_launch(control)
    common = dict(scientific_processes_signaled=False, unowned_processes_signaled=False,
        observer_roster_verified=True, request_id=request_id, episode_root=str(control))
    intent = control / "observer/retirement_intent/record.json"
    delivery = control / "observer/retirement_dispatch/record.json"
    if observer is None or identity(observer["pid"], observer["birth"])["alive"] is False:
        retired = delivery.exists()
        return dict(common, status="AUTHORIZED_MONITOR_RETIRED" if retired else "NO_LIVE_OBSERVER",
            remaining_independent_observers=0, all_observer_identities_gone=True,
            reason="authorized_monitor_retirement", observer_owner_uid=1004,
            verified_readonly_CPU_observer=True, only_signal_sent=15 if retired else None,
            retirement_signal_outcome_unknown=intent.exists() and not retired)
    require(protocol["observer_policy"] == (
        load_v59_module("finqa_v59_observer").observer_policy() if control == SOURCE_CONTROL_ROOT
        else importlib.import_module("finqa_v61_observer").observer_policy()), "observer policy changed")
    require(_owner_uids(observer["pid"]) == (1004, 1004, 1004, 1004),
            "observer is not entirely owned by the registered account")
    if not intent.exists():
        descriptor = _pidfd_open(observer["pid"])
        try:
            require(identity(observer["pid"], observer["birth"])["alive"] is True,
                    "observer changed before authorized TERM")
            write_record(intent, dict(schema="v61_authorized_readonly_monitor_retirement.v1", request_id=request_id,
                control_protocol_id=protocol["id"], pid=observer["pid"], birth=observer["birth"],
                sender_pid=os.getpid(), sender_birth=current_birth(os.getpid()), created_epoch=time.time(),
                reason="authorized_monitor_retirement", only_signal_authorized=15, pidfd_bound=True,
                signal_delivery_observed=False,
                scientific_processes_signaled=False), immutable=True)
            _pidfd_term(descriptor)
            write_record(delivery, dict(schema="v61_actual_pidfd_observer_retirement_dispatch.v1",
                intent=entry(intent), pid=observer["pid"], birth=observer["birth"], only_signal_sent=15,
                pidfd_send_returned_successfully=True), immutable=True)
        finally:
            os.close(descriptor)
    return dict(common, status="WAITING_FOR_OBSERVER_EXIT", pid=observer["pid"], birth=observer["birth"],
                retirement_signal_outcome_unknown=not delivery.exists(), automatic_signal_repeated=False)


def register_episode(root, predecessor, observation, audits, request_id):
    return registration.register_successor(root, predecessor, observation, audits, request_id)


def _dispatch_directory(root, request_id, attempt):
    require(request_id.startswith("request") and request_id[7:].isdigit() and type(attempt) is int and attempt > 0,
            "invalid launch transaction")
    return Path(root) / "backend/launches" / request_id / f"attempt{attempt:04d}"


def _launch_receipt(receipt, request_id, pid, birth):
    return dict(status="LAUNCHED", actual_child_created=True, episode_root=receipt["episode_root"],
        request_id=request_id, control_protocol_id=receipt["control_protocol_id"], pid=pid, birth=birth)


def reconcile_launch(root, receipt, request_id, launch_attempt):
    directory = _dispatch_directory(root, request_id, launch_attempt)
    result = _checked_optional(directory / "result/record.json")
    if result:
        return result
    intent = _checked_optional(directory / "intent/record.json")
    startup = _checked_optional(Path(receipt["episode_root"]) / "runner/launch/record.json")
    if intent and startup:
        require(startup["dispatch_token_sha256"] == intent["dispatch_token_sha256"]
                and startup["dispatch_directory"] == str(directory)
                and startup["control_protocol_id"] == receipt["control_protocol_id"],
                "early runner receipt does not match this dispatch")
        return _launch_receipt(receipt, request_id, startup["pid"], startup["birth"])
    return dict(status="UNKNOWN_CHILD_CREATION", actual_child_created=None, automatic_duplicate_launch=False)


def launch_registered(root, receipt, request_id, launch_attempt):
    require(os.getuid() == os.geteuid() == 1004, "runner launch must retain the registered account")
    episode = episode_root(receipt["episode_root"])
    prepared = checked_prepared(episode)
    require(prepared["id"] == receipt["registration_id"]
            and prepared["protocol_id"] == receipt["control_protocol_id"], "launch registration changed")
    require(not (Path(root) / "STOP").exists() and not (episode / "STOP").exists(), "explicit STOP forbids launch")
    directory = _dispatch_directory(root, request_id, launch_attempt)
    require(not (directory / "intent/record.json").exists(), "a dispatch intent must only be reconciled, never repeated")
    token = secrets.token_hex(32)
    command = [str(PYTHON), "-u", str(MASTER_ROOT / "implementation/finqa_v61_backend.py"),
               "run-episode", "--root", str(episode), "--dispatch-directory", str(directory)]
    write_record(directory / "intent/record.json", dict(schema="v61_token_bound_runner_dispatch.v1",
        request_id=request_id, launch_attempt=launch_attempt, control_protocol_id=receipt["control_protocol_id"],
        episode_root=str(episode), dispatch_token_sha256=digest(token), command=command,
        created_epoch=time.time()), immutable=True)
    environment = dict(os.environ, V61_DISPATCH_TOKEN=token,
        PYTHONPATH=os.pathsep.join((str(MASTER_ROOT / "implementation"), str(SCIENCE_ROOT / "implementation"),
                                  str(REPO / "trusted_data_synthesis/scripts"))))
    try:
        with (directory / "runner.log").open("xb") as log:
            process = subprocess.Popen(command, cwd=REPO, env=environment, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True)
    except OSError as error:
        return write_record(directory / "result/record.json", dict(status="NOT_LAUNCHED",
            actual_child_created=False, retry_safe_pre_child=error.errno in TRANSIENT_ERRNOS,
            actual_errno=error.errno, error_type=type(error).__name__, request_id=request_id,
            episode_root=str(episode)), immutable=True)
    birth = current_birth(process.pid)
    if birth is None:
        # The child may already have exited. Reconcile its durable early receipt;
        # absence is an unknown dispatch, never evidence to create another child.
        return reconcile_launch(root, receipt, request_id, launch_attempt)
    return write_record(directory / "result/record.json",
                        _launch_receipt(receipt, request_id, process.pid, birth), immutable=True)


def _early_startup(args):
    require(os.getuid() == os.geteuid() == 1004, "runner identity cannot change account")
    control = episode_root(args.root)
    directory = Path(args.dispatch_directory).resolve()
    require(directory.is_relative_to(MASTER_ROOT), "dispatch receipt escaped master namespace")
    intent = checked_record(directory / "intent/record.json")
    token = os.environ.pop("V61_DISPATCH_TOKEN", None)
    require(token and digest(token) == intent["dispatch_token_sha256"], "missing or wrong early-startup token")
    protocol = checked_record(control / "protocol/record.json")
    require(intent["control_protocol_id"] == protocol["id"], "early process belongs to another episode")
    role = "runner" if args.action == "run-episode" else args.role
    destination = control / "runner/launch/record.json" if role == "runner" else directory / "startup/record.json"
    own_birth = current_birth(os.getpid())
    require(isinstance(own_birth, str) and own_birth, "early startup requires the actual nonempty process birth")
    return write_record(destination, dict(schema="v61_early_token_bound_process_identity.v1",
        control_protocol_id=protocol["id"], role=role, pid=os.getpid(), birth=own_birth,
        owner_uid=os.getuid(), dispatch_directory=str(directory),
        dispatch_token_sha256=intent["dispatch_token_sha256"], started_epoch=time.time()), immutable=True)


def _spawn_child(control, role, protocol_id):
    directory = control / "runner/children" / role
    require(not directory.exists(), "runner child is single-use")
    token = secrets.token_hex(32)
    command = [str(PYTHON), "-u", str(MASTER_ROOT / "implementation/finqa_v61_backend.py"),
        "run-child", "--root", str(control), "--role", role, "--dispatch-directory", str(directory)]
    write_record(directory / "intent/record.json", dict(schema="v61_single_runner_child_intent.v1",
        role=role, control_protocol_id=protocol_id, dispatch_token_sha256=digest(token), command=command), immutable=True)
    try:
        with (directory / "child.log").open("xb") as log:
            process = subprocess.Popen(command, cwd=REPO, env=dict(os.environ, V61_DISPATCH_TOKEN=token),
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    except OSError as error:
        write_record(directory / "launch_failure/record.json", dict(actual_child_created=False,
            actual_errno=error.errno, error_type=type(error).__name__), immutable=True)
        raise
    birth = current_birth(process.pid)
    require(birth is not None, "child exited before a complete launch identity was observed")
    write_record(directory / "launch/record.json", dict(control_protocol_id=protocol_id, role=role,
        pid=process.pid, birth=birth, command=command, actual_child_created=True), immutable=True)
    return process, birth


def _wait_observer_ready(control, process, birth, requested, *, timeout=60):
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        if requested or (MASTER_ROOT / "STOP").exists() or (control / "STOP").exists() or (
                control / "control/stop_requested/record.json").exists():
            return False
        require(process.poll() is None and identity(process.pid, birth)["alive"] is True,
                "read-only observer exited before scientific supervisor admission")
        launch = _observer_launch(control)
        heartbeat = _checked_optional(control / "observer/queue/status.json", plain=True)
        if launch and heartbeat:
            require((launch["pid"], launch["birth"]) == (process.pid, birth)
                    and (heartbeat["pid"], heartbeat["birth"]) == (process.pid, birth)
                    and heartbeat["schema"] == "v58_independent_observer_heartbeat.v1"
                    and heartbeat["root"] == str(control), "observer heartbeat belongs to another process")
            if (heartbeat["status"] == "RUNNING" and heartbeat["current_discovery_readable"] is True
                    and 0 <= time.time() - heartbeat["at_epoch"] <= 10):
                write_record(control / "runner/observer_ready/record.json", dict(
                    schema="v61_actual_observer_supervisor_admission.v1", pid=process.pid, birth=birth,
                    heartbeat_epoch=heartbeat["at_epoch"], observed_epoch=time.time(),
                    actual_alive=True, current_discovery_readable=True), immutable=True)
                return True
        time.sleep(0.25)
    raise RuntimeError("read-only observer did not provide a fresh readable heartbeat within its 60-second startup admission")


def _run_episode(control, startup):
    requested = []
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda signum, _frame: requested.append(signum))
    load_v59_module("finqa_v59_signals").install(control / "signals" / f"runner-{os.getpid()}",
        role="runner", context=dict(control_root=str(control), automatic_watchdog_root=str(MASTER_ROOT)))
    checked_prepared(control)
    if (control / "STOP").exists() or (MASTER_ROOT / "STOP").exists() or requested:
        return 2
    observer, observer_birth = _spawn_child(control, "observer", startup["control_protocol_id"])
    if not _wait_observer_ready(control, observer, observer_birth, requested):
        return 2
    if requested or (MASTER_ROOT / "STOP").exists() or (control / "STOP").exists() or (
            control / "control/stop_requested/record.json").exists():
        return 2
    process, birth = _spawn_child(control, "supervisor", startup["control_protocol_id"])
    while process.poll() is None:
        if requested and not (control / "control/stop_requested/record.json").exists():
            write_record(control / "control/stop_requested/record.json", dict(schema="v61_runner_explicit_stop.v1",
                control_protocol_id=startup["control_protocol_id"], signals=requested,
                automatic_restart_allowed=False, source="registered_runner_owner_stop"), immutable=True)
        # Legacy supervisor honors the persistent marker and stops only its own
        # children. The runner/guard never directly signals scientific workers.
        time.sleep(1)
    write_record(control / "runner/supervisor_actual_exit/record.json", dict(
        schema="v61_actual_supervisor_waitpid.v1", control_protocol_id=startup["control_protocol_id"],
        pid=process.pid, birth=birth, returncode=process.returncode,
        actual_waitpid_observed=True, observed_epoch=time.time()), immutable=True)
    return process.returncode if process.returncode >= 0 else 128 - process.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run-episode", "run-child"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--dispatch-directory", type=Path, required=True)
    parser.add_argument("--role", choices=("observer", "supervisor"))
    args = parser.parse_args()
    startup = _early_startup(args)  # No scientific import precedes this identity.
    control = episode_root(args.root)
    if args.action == "run-episode":
        try:
            return _run_episode(control, startup)
        except Exception as error:
            write_record(control / "runner/failure/record.json", dict(schema="v61_actual_runner_failure.v1",
                control_protocol_id=startup["control_protocol_id"], error_type=type(error).__name__,
                actual_errno=getattr(error, "errno", None), error=str(error), automatic_retry_requested=False), immutable=True)
            raise
    require(args.role in ("observer", "supervisor"), "one registered child role required")
    path = MASTER_ROOT / "implementation" / ("finqa_v61_observer.py" if args.role == "observer" else "finqa_v61_controller.py")
    sys.argv = ([str(path), "--root", str(control), "--science-root", str(SCIENCE_ROOT)] if args.role == "observer"
                else [str(path), "supervise", "--root", str(control)])
    runpy.run_path(str(path), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
