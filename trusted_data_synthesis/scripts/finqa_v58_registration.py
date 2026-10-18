"""Authorized durable recovery plus bounded, non-privileged process telemetry.

V56 scientific IDs and state remain unchanged. This is a fresh control episode,
not a retry permission for unreturned calls or an override of legitimate stops.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import os
import subprocess
import time
from pathlib import Path

import finqa_v56_registration as scientific

REPO = scientific.REPO
SCIENCE_ROOT = scientific.ROOT
PREVIOUS_CONTROL_ROOT = SCIENCE_ROOT / "signal_recovery_02"
ROOT = SCIENCE_ROOT / "signal_recovery_03"
PREPARATION = SCIENCE_ROOT / "signal_recovery_preparation_02/record.json"
FILES = tuple("finqa_v58_" + name + ".py" for name in
              ("registration", "controller", "signals", "observer", "worker"))
SCIENTIFIC_PROTOCOL_ID = "53e084012b25dc34cc9a073cb53a1a3bf5d1dc7c4547937cd39e87e4d4be75af"
SCIENTIFIC_IMPLEMENTATION_ID = "e415b937f644b2afde65c1940ef0d0a7f9c0dca03d58d1079ab1e7253132e5e7"
PREVIOUS_CONTROL_PROTOCOL_ID = "0c67ed425dec0c64a6fdcb6b9e72625d70db2e15611029b10c54c416551ca920"
PREVIOUS_IMPLEMENTATION_ID = "280d0bb04947cf02d2c0c2c610205ab8df22ed078a50828ab7ba1227fdf0f313"
PREVIOUS_STOP_ID = "ad4015dca02dc29fabcbe97f068368f10ccc7873c0c84acd54f4bf3487631ec6"
ACCEPTED_JOBS = {"seed137.feedback_C05", "seed251.feedback_C05",
                 "seed389.feedback_C05", "seed137.shard00"}
UNKNOWN_EXIT_ATTEMPTS = {("seed251.feedback_C05", 1), ("seed389.feedback_C05", 1),
    ("seed137.shard01", 2), ("seed137.shard01", 4), ("seed137.shard02", 3),
    ("seed137.shard03", 2), ("seed251.shard00", 2)}
SCHEMA = "v58_authorized_root_signal_recovery_and_observation.v1"
PREPARED_SCHEMA = "v58_actual_same_science_control_ready.v1"
require, checked, publish, entry, file_ref, read_ref, sha = (
    scientific.require, scientific.checked, scientific.publish, scientific.entry,
    scientific.file_ref, scientific.read_ref, scientific.sha)


def recovery_contract():
    return dict(explicit_user_request="恢复任务，同时能否监控更多信息",
        scientific_root=str(SCIENCE_ROOT), independent_control_root=str(ROOT),
        previous_control_root=str(PREVIOUS_CONTROL_ROOT),
        scientific_protocol_unchanged=True, old_frozen_code_or_stop_evidence_rewritten=False,
        new_control_uses_exact_original_worker_mathematics_and_auxiliary_imports=True,
        inherited_complete_feedback_episodes=2100, remaining_feedback_episodes=0,
        returned_feedback_or_rewards_resampled=False, old_single_request_quota_remaining=0,
        inherited_complete_new_class_tasks=273, inherited_complete_class_rows=1834,
        remaining_new_class_tasks=1215, remaining_new_optimizer_updates=1788,
        new_evaluation_sessions=12267, previously_accepted_jobs=4,
        existing_actual_attempts=24, explicitly_bound_old_unknown_exit_attempts=7,
        old_missing_returncode_never_fabricated=True,
        historical_controller_and_supervisor_final_exit_status_unknown=True,
        old_stale_running_queue_not_treated_as_live_process=True,
        no_new_unknown_call_or_unknown_exit_automatic_retry_allowance=True,
        new_actual_process_exit_and_scientific_resource_validation_still_required=True,
        total_GPU_workers=4, per_GPU_workers=1, physical_GPUs=list(range(8)),
        extra_non_GPU_observer=1, no_external_system_permission_or_policy_changes=True,
        original_resource_limits_and_backoff_unchanged=True,
        requested_signal_shielding_not_enabled=True,
        SIGTERM_SIGINT_and_explicit_STOP_remain_terminal=True,
        SIGKILL_not_capturable_or_ignorable=True,
        telemetry_does_not_identify_a_human_without_evidence=True,
        brief_root_processes_may_escape_sampling=True,
        observer_may_share_the_same_login_cgroup_and_be_terminated_too=True,
        private_environments_command_lines_credentials_and_history_not_collected=True,
        unsealed_partial_class_compute_may_need_repeating_as_failure_overhead=True)


def modules():
    # Preserve the original science-before-historical-lifecycle import order.
    scientific.modules()
    return tuple(importlib.import_module("finqa_v58_" + name)
                 for name in ("controller", "signals", "observer", "worker"))


def validate_snapshot(value):
    require(value["scientific_root"] == str(SCIENCE_ROOT)
            and value["source_control_root"] == str(PREVIOUS_CONTROL_ROOT)
            and value["scientific_protocol_id"] == SCIENTIFIC_PROTOCOL_ID,
            "recovery snapshot belongs to another scientific/control run")
    require(set(value["accepted"]) == ACCEPTED_JOBS and len(value["attempt_history"]) == 24
            and value["evaluation_registered"] is False,
            "accepted jobs or historical attempt scope changed")
    require(value["total_complete_class_tasks"] == 273
            and value["total_complete_class_rows"] == 1834
            and value["remaining_new_class_tasks"] == 1215
            and value["remaining_feedback_episodes"] == 0
            and value["complete_feedback_episodes"] == 2100
            and value["new_feedback_sessions"] == 0 and value["UNKNOWN_feedback_calls"] == 0
            and value["remaining_new_optimizer_updates"] == 1788
            and value["evaluation_sessions"] == 12267,
            "actual durable work cannot be discarded or assigned a fresh sampling budget")
    require(value["all_old_process_identities_observed_gone"] is True
            and value["old_missing_returncode"] is None
            and value["immutable_old_records_rewritten"] is False,
            "old process disappearance cannot become a fabricated successful exit")
    rows = value["known_unobserved_attempts"]
    require(len(rows) == 7 and {(row["job_id"], row["attempt"]) for row in rows} == UNKNOWN_EXIT_ATTEMPTS
            and all(row["old_returncode"] is None for row in rows),
            "historical unknown exits must retain their exact scope and unknown status")
    for key, state in value["initial_job_states"].items():
        require((state["status"] == "COMPLETE") == (key in ACCEPTED_JOBS),
                "only previously accepted real-exit jobs can start complete")
        require(state["attempts"] == max((row["attempt"] for row in value["attempt_history"]
            if row["job_id"] == key), default=0), "attempt sequence cannot reset")
    for audit in value["resume_audits"].values():
        require(audit["resume_allowed"] is True and audit["unknown_calls"] == 0,
                "UNKNOWN or failed binding blocks authorized recovery")
    return value


def identity_gone(pid, birth):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return True
    return fields[19] != str(birth)


def prepare(source_commit, root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT and not root.exists(), "one fresh independently authorized control root required")
    controller, signals, observer, _worker = modules()
    original_protocol = scientific.checked_protocol(SCIENCE_ROOT)
    scientific.checked_implementation(SCIENCE_ROOT)
    require(original_protocol["id"] == SCIENTIFIC_PROTOCOL_ID, "original science protocol changed")
    snapshot = validate_snapshot(checked(PREPARATION))
    old_journal = read_ref(snapshot["old_journal"])
    require(old_journal["protocol_id"] == SCIENTIFIC_PROTOCOL_ID
            and old_journal["control_protocol_id"] == PREVIOUS_CONTROL_PROTOCOL_ID,
            "old journal control authorization differs")
    require(read_ref(snapshot["old_stop"])["id"] == PREVIOUS_STOP_ID,
            "actual root-signal stop record changed")
    for row in snapshot["process_identities"]:
        require(identity_gone(row["pid"], row["birth"]), "an old registered identity is still present")
    for row in snapshot["known_unobserved_attempts"]:
        read_ref(row["launch"])
        read_ref(row["identity_exit"])
    for reference in snapshot["accepted"].values():
        accepted = read_ref(reference)
        actual_exit = read_ref(accepted["actual_exit"])
        require(accepted["actual_exit_zero"] is True and actual_exit["returncode"] == 0
                and actual_exit["actual_waitpid_observed"] is True,
                "accepted result cannot lose its actual successful exit")
    commit = subprocess.check_output(["git", "rev-parse", source_commit + "^{commit}"], cwd=REPO, text=True).strip()
    sources = {}
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=REPO)
        require(hashlib.sha256(raw).hexdigest() == sha(REPO / relative),
                "uncommitted new monitoring/control source: " + name)
        sources[name] = raw
    implementation = root / "implementation"
    implementation.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (implementation / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    publish(implementation / "record.json", dict(schema="v58_frozen_control_and_observation_implementation.v1",
        source_commit=commit, files={name: sha(implementation / name) for name in FILES},
        original_scientific_implementation=entry(SCIENCE_ROOT / "implementation/record.json"),
        inherited_control_implementation=entry(PREVIOUS_CONTROL_ROOT / "implementation/record.json"),
        original_96_and_previous_4_files_modified=False))
    protocol = publish(root / "protocol/record.json", dict(schema=SCHEMA,
        registered_epoch=time.time(), scientific_root=str(SCIENCE_ROOT), control_root=str(root),
        scientific_protocol_id=SCIENTIFIC_PROTOCOL_ID, recovery_contract=recovery_contract(),
        implementation=entry(implementation / "record.json"), preparation_audit=entry(PREPARATION),
        scientific_protocol=entry(SCIENCE_ROOT / "protocol/record.json"),
        previous_control_protocol=entry(PREVIOUS_CONTROL_ROOT / "protocol/record.json"),
        old_journal=snapshot["old_journal"], old_stop=snapshot["old_stop"],
        adapter_contract=controller.adapter_contract(), signals_policy=signals.signals_policy(),
        observer_policy=observer.observer_policy(), max_gpu_workers=4, per_gpu_workers=1,
        inherited_auto_recovery_policy=original_protocol["auto_recovery_policy"],
        old_final_exit_code=None, old_terminal_closeout_fabricated=False))
    copied = {key: copy.deepcopy(snapshot[key]) for key in (
        "initial_job_states", "attempt_history", "accepted", "evaluation_registered",
        "resource_wait_seconds", "known_unobserved_attempts", "all_old_attempts",
        "resume_audits", "process_identities", "old_journal")}
    prepared = publish(root / "prepared/record.json", dict(schema=PREPARED_SCHEMA,
        protocol=entry(root / "protocol/record.json"), preparation_audit=entry(PREPARATION),
        scientific_protocol_id=SCIENTIFIC_PROTOCOL_ID, scientific_root=str(SCIENCE_ROOT),
        **copied, remaining_feedback_episodes=0, remaining_new_class_tasks=1215,
        remaining_new_optimizer_updates=1788, evaluation_sessions=12267,
        old_single_request_quota_remaining=0, old_missing_returncode=None,
        old_active_jobs_reset_only_in_new_control=True))
    return dict(protocol_id=protocol["id"], prepared_id=prepared["id"], source_commit=commit)


def checked_implementation(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "unregistered control/observer root")
    value = checked(root / "implementation/record.json")
    require(set(value["files"]) == set(FILES) and value["original_96_and_previous_4_files_modified"] is False,
            "registered control/observer module set changed")
    for name, expected in value["files"].items():
        require(sha(root / "implementation" / name) == expected, "new frozen code changed: " + name)
    parent = read_ref(value["inherited_control_implementation"])
    require(parent["id"] == PREVIOUS_IMPLEMENTATION_ID, "frozen control adapter source changed")
    for name, expected in parent["files"].items():
        require(sha(PREVIOUS_CONTROL_ROOT / "implementation" / name) == expected, "inherited control bytes changed")
    require(read_ref(value["original_scientific_implementation"])["id"] == SCIENTIFIC_IMPLEMENTATION_ID,
            "original scientific bundle changed")
    return value


def checked_protocol(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "unregistered control root")
    value = checked(root / "protocol/record.json")
    require(value["schema"] == SCHEMA and value["scientific_root"] == str(SCIENCE_ROOT)
            and value["control_root"] == str(ROOT) and value["scientific_protocol_id"] == SCIENTIFIC_PROTOCOL_ID
            and value["recovery_contract"] == recovery_contract(), "control recovery authorization changed")
    controller = importlib.import_module("finqa_v58_controller")
    signals = importlib.import_module("finqa_v58_signals")
    observer = importlib.import_module("finqa_v58_observer")
    require(value["adapter_contract"] == controller.adapter_contract()
            and value["signals_policy"] == signals.signals_policy()
            and value["observer_policy"] == observer.observer_policy(), "registered observation/adapter behavior changed")
    require(read_ref(value["scientific_protocol"])["id"] == SCIENTIFIC_PROTOCOL_ID
            and read_ref(value["previous_control_protocol"])["id"] == PREVIOUS_CONTROL_PROTOCOL_ID
            and read_ref(value["old_stop"])["id"] == PREVIOUS_STOP_ID,
            "old scientific/stop records changed")
    read_ref(value["old_journal"])
    return value


def checked_prepared(root=ROOT):
    protocol = checked_protocol(root)
    value = checked(Path(root) / "prepared/record.json")
    snapshot = validate_snapshot(read_ref(value["preparation_audit"]))
    require(value["schema"] == PREPARED_SCHEMA and read_ref(value["protocol"])["id"] == protocol["id"]
            and value["scientific_root"] == str(SCIENCE_ROOT)
            and value["scientific_protocol_id"] == SCIENTIFIC_PROTOCOL_ID
            and value["remaining_feedback_episodes"] == 0 and value["remaining_new_class_tasks"] == 1215
            and value["remaining_new_optimizer_updates"] == 1788 and value["evaluation_sessions"] == 12267
            and value["old_single_request_quota_remaining"] == 0 and value["old_missing_returncode"] is None,
            "prepared scientific budget or unknown historical exit changed")
    require(all(value[key] == snapshot[key] for key in (
        "initial_job_states", "attempt_history", "accepted", "known_unobserved_attempts",
        "resource_wait_seconds", "evaluation_registered")), "actual durable bootstrap snapshot changed")
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
