"""One explicitly authorized control episode over unchanged V56 scientific data.

The stopped V56 controller, terminal marker and missing historical exit codes are
never rewritten. Only new worker attempts may continue durable scientific work.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import finqa_v56_registration as scientific

REPO = scientific.REPO
SCIENCE_ROOT = scientific.ROOT
ROOT = SCIENCE_ROOT / "signal_recovery_01"
PREPARATION_ROOT = SCIENCE_ROOT / "signal_recovery_preparation_01"
FILES = tuple("finqa_v57_" + name + ".py" for name in
              ("registration", "controller", "signals", "worker"))
SCIENTIFIC_PROTOCOL_ID = "53e084012b25dc34cc9a073cb53a1a3bf5d1dc7c4547937cd39e87e4d4be75af"
SCIENTIFIC_IMPLEMENTATION_ID = "e415b937f644b2afde65c1940ef0d0a7f9c0dca03d58d1079ab1e7253132e5e7"
OLD_STOP_ID = "3340c7030479e01366329159fab412523827c1496d4c2938247c1c0819dca610"
OLD_SUPERVISOR_CLOSEOUT_ID = "45381008ad8fa847fc174ea2abaf1583a74376781992601591ba32f20b545b7c"
SCHEMA = "v57_authorized_signal_recovery_control_protocol.v1"
PREPARED_SCHEMA = "v57_same_science_control_episode_ready.v1"
require, checked, publish, entry, file_ref, read_ref, sha = (
    scientific.require, scientific.checked, scientific.publish, scientific.entry,
    scientific.file_ref, scientific.read_ref, scientific.sha)


def recovery_contract():
    return dict(explicit_user_request="尽快恢复任务，同时排查异常信号来源",
        scientific_root=str(SCIENCE_ROOT), independent_control_root=str(ROOT),
        unchanged_scientific_protocol_id=SCIENTIFIC_PROTOCOL_ID,
        no_scientific_parent_or_feedback_ID_rebinding=True,
        old_stop_marker_and_failed_controller_history_immutable=True,
        old_unknown_exit_code_never_fabricated=True,
        old_all_worker_identities_must_be_gone=True,
        user_authorized_initial_attempts_only=True,
        new_attempts_append_original_scientific_stage=True,
        original_accepted_jobs_reused=2,
        complete_unaccepted_stage_requires_new_CPU_finalization_and_actual_exit_zero=True,
        inherited_complete_feedback_episodes=2054,
        remaining_feedback_episodes=46, inherited_partial_returned_turns=1,
        UNKNOWN_feedback_reexecution=False, old_single_request_quota_remaining=0,
        inherited_complete_new_class_tasks=208, inherited_class_rows=1421,
        remaining_new_class_tasks=1280,
        remaining_new_optimizer_updates=1788, evaluation_sessions=12267,
        max_gpu_workers=4, per_gpu_workers=1, physical_GPUs=list(range(8)),
        original_mathematics_dose_resource_gates_and_auto_recovery_unchanged=True,
        signal_sender_audit=True, SIGKILL_cannot_be_caught=True,
        signal_sender_telemetry_failure_does_not_suppress_stop=True,
        explicit_new_SIGTERM_SIGINT_or_STOP_remains_terminal=True,
        no_new_sampling_replay_or_training_budget=True)


def process_identity_gone(pid, birth):
    try:
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return True
    # A zombie is not granted an invented exit status. Reuse of a PID is safe
    # only because the recorded birth proves it is a different process.
    return stat[19] != str(birth)


def initial_job_states(old, audits, *, attempt_counts):
    """Reset dispatchability only under this new authorization, never old facts."""
    require(set(attempt_counts) <= set(old["job_states"]), "unknown old scientific job")
    states = {}
    for key, state in old["job_states"].items():
        count = attempt_counts.get(key, 0)
        require(count == state["attempts"], "journal differs from actual attempt directories")
        if key in old["accepted"]:
            require(state["status"] == "COMPLETE", "accepted job lost successful state")
            states[key] = copy.deepcopy(state)
            continue
        require(state["status"] in ("PENDING", "RUNNING", "DRAINING", "HARD_BLOCKED",
                                    "DEPENDENCY_BLOCKED", "BACKOFF", "RESOURCE_COOLDOWN"),
                "unregistered old control state")
        if count:
            require(key in audits, "started job requires actual durable audit")
            audit = audits[key]
            require(audit["resume_allowed"] is True and audit["unknown_calls"] == 0
                    and audit["progress_units"] >= state["progress_units"],
                    "UNKNOWN, failed binding or lost durable progress blocks recovery")
            progress, digest = audit["progress_units"], audit["durable_progress_digest"]
        else:
            progress, digest = 0, None
        states[key] = dict(status="PENDING", attempts=count,
            no_progress_failures=state["no_progress_failures"], next_eligible_epoch=0.0,
            progress_units=progress, durable_progress_digest=digest,
            initial_authorized_signal_recovery=True)
    return states


def collect_evidence():
    # Import the scientific closure before old lifecycle helpers can alias it.
    scientific.modules()
    protocol = scientific.checked_protocol(SCIENCE_ROOT)
    scientific.checked_implementation(SCIENCE_ROOT)
    original_prepared = scientific.checked_prepared(SCIENCE_ROOT)
    require(protocol["id"] == SCIENTIFIC_PROTOCOL_ID, "wrong V56 scientific protocol")
    implementation = checked(SCIENCE_ROOT / "implementation/record.json")
    require(implementation["id"] == SCIENTIFIC_IMPLEMENTATION_ID, "wrong frozen V56 code")
    old = checked(SCIENCE_ROOT / "journal/state.json")
    old_stop = checked(SCIENCE_ROOT / "control/stop_requested/record.json")
    old_closeout = checked(SCIENCE_ROOT / "supervisor/closeout/record.json")
    require(old_stop["id"] == OLD_STOP_ID
            and old_closeout["id"] == OLD_SUPERVISOR_CLOSEOUT_ID
            and old_closeout["status"] == "STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME",
            "this authorization is tied to the actual V56 signal stop")
    require(not old["evaluation_registered"] and set(old["accepted"]) == {
        "seed137.feedback_C05", "seed137.shard00"}, "initial accepted scientific scope changed")
    feedback_path = PREPARATION_ROOT / "feedback_audit/record.json"
    lifecycle_path = PREPARATION_ROOT / "lifecycle_audit/record.json"
    feedback, lifecycle = checked(feedback_path), checked(lifecycle_path)
    require(lifecycle["science_root"] == str(SCIENCE_ROOT)
            and lifecycle["all_old_worker_identities_observed_gone"] is True
            and lifecycle["total_complete_class_tasks"] == 208
            and lifecycle["total_complete_class_rows"] == 1421,
            "actual lifecycle/task audit differs from this recovery")
    require(feedback["complete_feedback_episodes"] == 2054
            and feedback["remaining_complete_episodes"] == 46
            and feedback["UNKNOWN_calls"] == 0
            and feedback["uncompleted_episode_returned_turns"] == 1
            and feedback["all_seed_feedback_resume_allowed"] is True,
            "actual feedback audit differs from this one recovery authorization")
    # Lifecycle shape is produced by the real stopped-attempt audit, not test data.
    attempts, counts, identities, unobserved = [], {}, [], []
    for launched in sorted(SCIENCE_ROOT.glob("stages/seed*/*/attempts/attempt*/launch/record.json")):
        row = checked(launched)
        directory, job = launched.parent.parent, row["job"]["job_id"]
        number = row["attempt"]
        require(row["protocol_id"] == protocol["id"] and number >= 1,
                "old attempt scientific identity differs")
        counts[job] = max(counts.get(job, 0), number)
        require(process_identity_gone(row["pid"], row["birth"]), "old scientific worker is still alive")
        identity = dict(pid=row["pid"], birth=row["birth"], gone=True,
                        observed_epoch=time.time(), observed_exit_code=None)
        identities.append(identity)
        attempt = dict(job_id=job, attempt=number, directory=str(directory), launch=entry(launched),
                       pid=row["pid"], birth=row["birth"], identity_observation=identity)
        exit_path = directory / "actual_exit/record.json"
        if exit_path.exists():
            exited = checked(exit_path)
            require(exited["actual_waitpid_observed"] is True
                    and (exited["pid"], exited["birth"]) == (row["pid"], row["birth"]),
                    "mismatched historical actual exit")
            attempt.update(actual_exit=entry(exit_path), old_returncode=exited["returncode"])
        else:
            attempt.update(actual_exit=None, old_returncode=None,
                           missing_exit_zero_not_fabricated=True)
            unobserved.append(attempt)
        attempts.append(attempt)
    require(len(attempts) == 7 and {item["job_id"] for item in unobserved} == {
        "seed251.feedback_C05", "seed389.feedback_C05", "seed137.shard01"},
        "one-time missing-waitpid exception scope changed")
    for path in (SCIENCE_ROOT / "supervisor/launch/record.json",
                 SCIENCE_ROOT / "controllers/attempt0001/launch/record.json"):
        launch = checked(path)
        require(process_identity_gone(launch["pid"], launch["birth"]), "old control identity still alive")
        identities.append(dict(pid=launch["pid"], birth=launch["birth"], gone=True,
                               observed_epoch=time.time(), launch=entry(path)))
    for key, reference in old["accepted"].items():
        accepted = read_ref(reference)
        result, exited = read_ref(accepted["result"]), read_ref(accepted["actual_exit"])
        require(accepted["actual_exit_zero"] is True and exited["returncode"] == 0
                and result["status"] == "COMPLETE" and result["resources"]["all_gates_passed"] is True,
                "previous accepted job no longer has successful scientific/resource/exit evidence")
    audits = {}
    for seed in (137, 251, 389):
        row = feedback["seeds"][str(seed)]
        audits[f"seed{seed}.feedback_C05"] = {name: row[name] for name in
            ("resume_allowed", "unknown_calls", "progress_units", "durable_progress_digest")}
    # Reuse the real stopped-run audit already performed once. The original
    # cold consumers validate tensor bytes/numerical bindings before actual use.
    for key in counts:
        if key not in audits:
            audits[key] = lifecycle["resume_audits"][key]
    states = initial_job_states(old, audits, attempt_counts=counts)
    require(audits["seed137.shard00"]["progress_units"] == 186
            and audits["seed137.shard01"]["progress_units"] == 0
            and audits["seed137.shard02"]["progress_units"] == 22,
            "complete task cursor changed from stopped V56 audit")
    return dict(old=old, attempts=attempts, identities=identities,
        known_unobserved_attempts=unobserved, initial_job_states=states, audits=audits,
        references=dict(old_journal=entry(SCIENCE_ROOT / "journal/state.json"),
            old_stop=entry(SCIENCE_ROOT / "control/stop_requested/record.json"),
            old_supervisor_closeout=entry(SCIENCE_ROOT / "supervisor/closeout/record.json"),
            old_controller_exit=entry(SCIENCE_ROOT / "supervisor/attempts/attempt0001/actual_exit/record.json"),
            feedback_audit=entry(feedback_path), lifecycle_audit=entry(lifecycle_path),
            incident_trace=entry(PREPARATION_ROOT / "incident_trace/record.json"),
            scientific_protocol=entry(SCIENCE_ROOT / "protocol/record.json"),
            scientific_implementation=entry(SCIENCE_ROOT / "implementation/record.json"),
            scientific_prepared=entry(SCIENCE_ROOT / "prepared/record.json")))


def prepare(source_commit, root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT and not root.exists(), "new control episode must be prepared exactly once")
    evidence = collect_evidence()
    commit = subprocess.check_output(["git", "rev-parse", source_commit + "^{commit}"], cwd=REPO, text=True).strip()
    sources = {}
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=REPO)
        require(hashlib.sha256(raw).hexdigest() == sha(REPO / relative),
                "new recovery source must be committed before freezing")
        sources[name] = raw
    implementation = root / "implementation"
    implementation.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (implementation / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    publish(implementation / "record.json", dict(schema="v57_frozen_control_episode_implementation.v1",
        source_commit=commit, files={name: sha(implementation / name) for name in FILES},
        original_scientific_implementation=evidence["references"]["scientific_implementation"],
        original_96_files_modified=False))
    identity_path = root / "initial_identity_observation/record.json"
    publish(identity_path, dict(schema="v57_authorized_old_identity_exit_observation.v1",
        observed_epoch=time.time(), identities=evidence["identities"], all_observed_gone=True,
        old_missing_returncodes_not_inferred=True))
    for row in evidence["known_unobserved_attempts"]:
        row["identity_exit"] = entry(identity_path)
    protocol = publish(root / "protocol/record.json", dict(schema=SCHEMA,
        registered_epoch=time.time(), scientific_root=str(SCIENCE_ROOT), control_root=str(root),
        scientific_protocol_id=SCIENTIFIC_PROTOCOL_ID,
        implementation=entry(implementation / "record.json"),
        recovery_contract=recovery_contract(), **evidence["references"],
        inherited_automatic_resource_recovery_policy=read_ref(evidence["references"]["scientific_protocol"])["auto_recovery_policy"],
        max_gpu_workers=4, per_gpu_workers=1, old_unknown_exit_reclassified=False,
        process_identities=evidence["identities"]))
    old = evidence["old"]
    prepared = publish(root / "prepared/record.json", dict(schema=PREPARED_SCHEMA,
        protocol=entry(root / "protocol/record.json"), scientific_protocol_id=SCIENTIFIC_PROTOCOL_ID,
        scientific_root=str(SCIENCE_ROOT), initial_job_states=evidence["initial_job_states"],
        attempt_history=copy.deepcopy(old["attempt_history"]), accepted=copy.deepcopy(old["accepted"]),
        evaluation_registered=False, resource_wait_seconds=old["resource_wait_seconds"],
        known_unobserved_attempts=evidence["known_unobserved_attempts"],
        all_old_attempts=evidence["attempts"], initial_durable_audits=evidence["audits"],
        old_journal=evidence["references"]["old_journal"], old_active_jobs_reset_only_in_new_control=True,
        old_missing_returncode=None, remaining_feedback_episodes=46,
        remaining_new_class_tasks=1280, remaining_new_optimizer_updates=1788,
        evaluation_sessions=12267, old_single_request_quota_remaining=0,
        complete_unaccepted_stage_requires_new_finalizer=True))
    return dict(protocol_id=protocol["id"], prepared_id=prepared["id"], source_commit=commit)


def checked_implementation(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "unregistered independent control root")
    value = checked(root / "implementation/record.json")
    require(set(value["files"]) == set(FILES) and value["original_96_files_modified"] is False,
            "control execution package changed")
    for name, expected in value["files"].items():
        require(sha(root / "implementation" / name) == expected, "frozen V57 source changed")
    require(read_ref(value["original_scientific_implementation"])["id"] == SCIENTIFIC_IMPLEMENTATION_ID,
            "scientific execution package changed")
    return value


def checked_protocol(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "unregistered independent control root")
    value = checked(root / "protocol/record.json")
    require(value["schema"] == SCHEMA and value["scientific_root"] == str(SCIENCE_ROOT)
            and value["control_root"] == str(ROOT) and value["scientific_protocol_id"] == SCIENTIFIC_PROTOCOL_ID
            and value["recovery_contract"] == recovery_contract(), "control recovery authorization differs")
    require(read_ref(value["scientific_protocol"])["id"] == SCIENTIFIC_PROTOCOL_ID
            and read_ref(value["old_stop"])["id"] == OLD_STOP_ID
            and read_ref(value["old_supervisor_closeout"])["id"] == OLD_SUPERVISOR_CLOSEOUT_ID,
            "historical protocol or signal-stop evidence changed")
    require(value["max_gpu_workers"] == 4 and value["per_gpu_workers"] == 1,
            "control episode cannot enlarge concurrency")
    read_ref(value["old_journal"])
    return value


def checked_prepared(root=ROOT):
    protocol = checked_protocol(root)
    value = checked(Path(root) / "prepared/record.json")
    require(read_ref(value["protocol"])["id"] == protocol["id"]
            and value["schema"] == PREPARED_SCHEMA
            and value["scientific_root"] == str(SCIENCE_ROOT)
            and value["scientific_protocol_id"] == SCIENTIFIC_PROTOCOL_ID
            and value["remaining_feedback_episodes"] == 46
            and value["remaining_new_class_tasks"] == 1280
            and value["remaining_new_optimizer_updates"] == 1788
            and value["evaluation_sessions"] == 12267
            and value["old_single_request_quota_remaining"] == 0
            and value["old_missing_returncode"] is None
            and value["complete_unaccepted_stage_requires_new_finalizer"] is True,
            "prepared scientific scope or unknown historical exit changed")
    require(set(value["accepted"]) == {"seed137.feedback_C05", "seed137.shard00"}
            and len(value["attempt_history"]) == 7
            and len(value["known_unobserved_attempts"]) == 3
            and value["evaluation_registered"] is False,
            "initial stopped-attempt exception changed")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "check"))
    parser.add_argument("--source-commit", default="HEAD")
    args = parser.parse_args()
    result = prepare(args.source_commit) if args.action == "prepare" else checked_prepared()
    print(json.dumps(result if args.action == "prepare" else dict(id=result["id"], status="READY")))


if __name__ == "__main__":
    main()
