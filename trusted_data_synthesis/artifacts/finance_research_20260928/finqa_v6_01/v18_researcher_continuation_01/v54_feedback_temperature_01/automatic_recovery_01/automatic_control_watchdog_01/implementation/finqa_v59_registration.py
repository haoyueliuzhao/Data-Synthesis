"""One newly authorized durable recovery with owner-scoped TERM observation.

Scientific IDs, old stop records and unknown historical exit codes stay intact.
Signal filtering is process-local and bound to the separately frozen policy;
it grants no system privilege, SIGKILL immunity or new sampling budget.
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

REPO, SCIENCE_ROOT = scientific.REPO, scientific.ROOT
PREVIOUS_CONTROL_ROOT = SCIENCE_ROOT / "signal_recovery_03"
ROOT = SCIENCE_ROOT / "signal_recovery_04"
PREPARATION = SCIENCE_ROOT / "signal_recovery_preparation_03/record.json"
FILES = tuple("finqa_v59_" + name + ".py" for name in
              ("registration", "controller", "signals", "observer", "worker", "gpu_isolation"))
SCIENTIFIC_PROTOCOL_ID = "53e084012b25dc34cc9a073cb53a1a3bf5d1dc7c4547937cd39e87e4d4be75af"
SCIENTIFIC_IMPLEMENTATION_ID = "e415b937f644b2afde65c1940ef0d0a7f9c0dca03d58d1079ab1e7253132e5e7"
PREVIOUS_CONTROL_PROTOCOL_ID = "8b40efeeaf4ddff85957efb6eb05c3846084c0655f2216469549a20d9b66554e"
PREVIOUS_IMPLEMENTATION_ID = "63525be8d361117a8dd0ee2f10265d9fa97e675da969e622580fadece8060e6f"
PREVIOUS_STOP_ID = "f4441433f65405a46c54e55f4f474f69aecf12aa055e6090b400e1ec5637d017"
ACCEPTED_JOBS = {"seed137.feedback_C05", "seed251.feedback_C05", "seed389.feedback_C05", "seed137.shard00"}
UNKNOWN_EXIT_ATTEMPTS = {
    ("seed251.feedback_C05", 1), ("seed389.feedback_C05", 1), ("seed137.shard01", 2),
    ("seed137.shard01", 4), ("seed137.shard02", 3), ("seed137.shard03", 2), ("seed251.shard00", 2),
    ("seed137.shard01", 5), ("seed137.shard02", 4), ("seed137.shard03", 3), ("seed251.shard00", 3),
}
SCHEMA = "v59_authorized_owner_signal_recovery_control.v1"
PREPARED_SCHEMA = "v59_actual_same_science_control_ready.v1"
SNAPSHOT_SCHEMA = "v59_stopped_same_science_boundary_preparation.v1"
require, checked, publish, entry, file_ref, read_ref, sha = (
    scientific.require, scientific.checked, scientific.publish, scientific.entry,
    scientific.file_ref, scientific.read_ref, scientific.sha)
BOOTSTRAP_FIELDS = (
    "initial_job_states", "attempt_history", "accepted", "evaluation_registered",
    "resource_wait_seconds", "known_unobserved_attempts", "all_old_attempts",
    "resume_audits", "process_identities", "old_journal",
)


def recovery_contract():
    return dict(explicit_user_request="尽快恢复任务",
        additional_signal_authorization="仅在本实验进程内过滤已证实的外部UID普通SIGTERM",
        scientific_root=str(SCIENCE_ROOT), independent_control_root=str(ROOT),
        previous_control_root=str(PREVIOUS_CONTROL_ROOT), scientific_protocol_unchanged=True,
        old_frozen_code_stop_history_or_UNKNOWN_exit_rewritten=False,
        inherited_complete_feedback_episodes=2100, remaining_feedback_episodes=0,
        feedback_rewards_or_returned_turns_resampled=False, old_single_request_quota_remaining=0,
        inherited_complete_new_class_tasks=756, inherited_complete_class_rows=5032,
        remaining_new_class_tasks=732, remaining_new_optimizer_updates=1788,
        new_evaluation_sessions=12267, previously_accepted_jobs=4,
        existing_actual_attempts=28, explicitly_bound_old_unknown_exit_attempts=11,
        old_missing_returncode_never_fabricated=True, historical_root_signal_operator_intent_unknown=True,
        old_stale_RUNNING_queue_not_treated_as_live_process=True,
        no_new_unknown_call_or_unknown_exit_automatic_retry_allowance=True,
        original_resource_auto_recovery_and_backoff_preserved=True,
        external_watchdog_or_extra_outer_recovery_not_added=True,
        new_actual_exit_and_scientific_resource_validation_required=True,
        total_GPU_workers=4, per_GPU_workers=1, physical_GPUs=list(range(8)), extra_non_GPU_observer=1,
        sharing_a_device_with_registered_yyy_owner_forbidden=True,
        GPU_owner_isolation_exactly_bound_by_gpu_isolation_policy=True,
        GPU_owner_conflict_yields_only_this_experiment_without_signaling_other_users=True,
        owner_uid=1004, narrow_filter_details_bound_only_by_signals_policy=True,
        owner_SIGTERM_all_SIGINT_explicit_STOP_and_unknown_semantics_remain_terminal=True,
        SIGKILL_not_capturable_ignorable_or_prevented=True,
        system_permissions_other_processes_and_administrative_policy_unchanged=True,
        root_or_sudo_not_used=True, no_human_attribution_without_evidence=True,
        unsealed_partial_class_compute_may_repeat_as_failure_overhead=True)


def modules():
    scientific.modules()
    return tuple(importlib.import_module("finqa_v59_" + name)
                 for name in ("controller", "signals", "observer", "worker", "gpu_isolation"))


def validate_snapshot(value):
    require(value["schema"] == SNAPSHOT_SCHEMA and value["scientific_root"] == str(SCIENCE_ROOT)
            and value["source_control_root"] == str(PREVIOUS_CONTROL_ROOT)
            and value["scientific_protocol_id"] == SCIENTIFIC_PROTOCOL_ID
            and value["source_control_protocol_id"] == PREVIOUS_CONTROL_PROTOCOL_ID,
            "snapshot belongs to another authorized scientific/control episode")
    require(set(value["accepted"]) == ACCEPTED_JOBS and len(value["attempt_history"]) == 28
            and value["evaluation_registered"] is False,
            "accepted jobs or actual attempt scope changed")
    require(value["total_complete_class_tasks"] == 756 and value["total_complete_class_rows"] == 5032
            and value["remaining_new_class_tasks"] == 732
            and value["complete_feedback_episodes"] == 2100 and value["remaining_feedback_episodes"] == 0
            and value["new_feedback_sessions"] == 0 and value["UNKNOWN_feedback_calls"] == 0
            and value["remaining_new_optimizer_updates"] == 1788 and value["evaluation_sessions"] == 12267,
            "saved scientific work or remaining dose changed")
    require(value["all_old_process_identities_observed_gone"] is True
            and value["old_missing_returncode"] is None and value["immutable_old_records_rewritten"] is False,
            "old identity disappearance cannot become a fabricated successful exit")
    unknown = value["known_unobserved_attempts"]
    require(len(unknown) == 11 and {(row["job_id"], row["attempt"]) for row in unknown} == UNKNOWN_EXIT_ATTEMPTS
            and all(row["old_returncode"] is None for row in unknown),
            "old unknown exits must retain their exact registered scope and unknown status")
    require(set(value["resume_audits"]) == set(value["initial_job_states"]), "resume-audit job roster changed")
    for key, state in value["initial_job_states"].items():
        sequence = sorted(row["attempt"] for row in value["attempt_history"] if row["job_id"] == key)
        require(sequence == list(range(1, state["attempts"] + 1)), "actual attempt sequence cannot reset or skip")
        require((state["status"] == "COMPLETE") == (key in ACCEPTED_JOBS),
                "only accepted successful exits may start COMPLETE")
        audit = value["resume_audits"][key]
        require(audit["resume_allowed"] is True and audit["unknown_calls"] == 0,
                "UNKNOWN generation or invalid durable binding blocks recovery")
    return value


def identity_gone(pid, birth):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return True
    return fields[19] != str(birth)


def _previous_implementation():
    value = checked(PREVIOUS_CONTROL_ROOT / "implementation/record.json")
    require(value["id"] == PREVIOUS_IMPLEMENTATION_ID and len(value["files"]) == 5,
            "the frozen control03 implementation changed")
    for name, expected in value["files"].items():
        require(sha(PREVIOUS_CONTROL_ROOT / "implementation" / name) == expected,
                "previous frozen source bytes changed: " + name)
    require(read_ref(value["original_scientific_implementation"])["id"] == SCIENTIFIC_IMPLEMENTATION_ID,
            "original scientific implementation identity changed")
    return value


def prepare(source_commit, root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT and not root.exists(), "one fresh signal_recovery_04 control root required")
    require(os.getuid() == os.geteuid() == 1004, "registration must run as the experiment owner without elevation")
    controller, signals, observer, _worker, gpu_isolation = modules()
    original = checked(SCIENCE_ROOT / "protocol/record.json")
    require(original["id"] == SCIENTIFIC_PROTOCOL_ID, "original scientific protocol changed")
    _previous_implementation()
    snapshot = validate_snapshot(checked(PREPARATION))
    journal = read_ref(snapshot["old_journal"])
    require(journal["protocol_id"] == SCIENTIFIC_PROTOCOL_ID
            and journal["control_protocol_id"] == PREVIOUS_CONTROL_PROTOCOL_ID
            and read_ref(snapshot["old_stop"])["id"] == PREVIOUS_STOP_ID,
            "historical scientific journal or root-signal stop changed")
    for row in snapshot["process_identities"]:
        require(identity_gone(row["pid"], row["birth"]), "an old registered process identity is still present")
    for row in snapshot["known_unobserved_attempts"]:
        read_ref(row["launch"])
        read_ref(row["identity_exit"])
    for reference in snapshot["accepted"].values():
        accepted = read_ref(reference)
        exited = read_ref(accepted["actual_exit"])
        require(accepted["actual_exit_zero"] is True and exited["returncode"] == 0
                and exited["actual_waitpid_observed"] is True, "accepted job lost its real successful exit")
    commit = subprocess.check_output(["git", "rev-parse", source_commit + "^{commit}"], cwd=REPO, text=True).strip()
    sources = {}
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=REPO)
        require(hashlib.sha256(raw).hexdigest() == sha(REPO / relative), "uncommitted V59 source: " + name)
        sources[name] = raw
    implementation = root / "implementation"
    implementation.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (implementation / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    publish(implementation / "record.json", dict(schema="v59_frozen_owner_signal_control_implementation.v1",
        source_commit=commit, files={name: sha(implementation / name) for name in FILES},
        original_scientific_implementation=entry(SCIENCE_ROOT / "implementation/record.json"),
        inherited_control_implementation=entry(PREVIOUS_CONTROL_ROOT / "implementation/record.json"),
        old_scientific_and_control_files_modified=False))
    protocol = publish(root / "protocol/record.json", dict(schema=SCHEMA, registered_epoch=time.time(),
        scientific_root=str(SCIENCE_ROOT), control_root=str(root), scientific_protocol_id=SCIENTIFIC_PROTOCOL_ID,
        recovery_contract=recovery_contract(), implementation=entry(implementation / "record.json"),
        preparation_audit=entry(PREPARATION), scientific_protocol=entry(SCIENCE_ROOT / "protocol/record.json"),
        previous_control_protocol=entry(PREVIOUS_CONTROL_ROOT / "protocol/record.json"),
        old_journal=snapshot["old_journal"], old_stop=snapshot["old_stop"],
        adapter_contract=controller.adapter_contract(), signals_policy=signals.signals_policy(),
        observer_policy=observer.observer_policy(), gpu_isolation_policy=gpu_isolation.gpu_isolation_policy(),
        max_gpu_workers=4, per_gpu_workers=1,
        inherited_auto_recovery_policy=original["auto_recovery_policy"],
        old_final_exit_code=None, old_terminal_closeout_fabricated=False))
    copied = {key: copy.deepcopy(snapshot[key]) for key in BOOTSTRAP_FIELDS}
    prepared = publish(root / "prepared/record.json", dict(schema=PREPARED_SCHEMA,
        protocol=entry(root / "protocol/record.json"), preparation_audit=entry(PREPARATION),
        scientific_protocol_id=SCIENTIFIC_PROTOCOL_ID, scientific_root=str(SCIENCE_ROOT), **copied,
        remaining_feedback_episodes=0, remaining_new_class_tasks=732,
        remaining_new_optimizer_updates=1788, evaluation_sessions=12267,
        old_single_request_quota_remaining=0, old_missing_returncode=None,
        old_active_jobs_reset_only_in_new_control=True))
    return dict(protocol_id=protocol["id"], prepared_id=prepared["id"], source_commit=commit)


def checked_implementation(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "unregistered control04 implementation root")
    value = checked(root / "implementation/record.json")
    require(set(value["files"]) == set(FILES) and value["old_scientific_and_control_files_modified"] is False,
            "new implementation file scope changed")
    for name, expected in value["files"].items():
        require(sha(root / "implementation" / name) == expected, "new frozen source changed: " + name)
    require(read_ref(value["inherited_control_implementation"])["id"] == PREVIOUS_IMPLEMENTATION_ID,
            "original control03 implementation binding changed")
    _previous_implementation()
    require(read_ref(value["original_scientific_implementation"])["id"] == SCIENTIFIC_IMPLEMENTATION_ID,
            "original scientific package binding changed")
    return value


def checked_protocol(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "unregistered control04 root")
    value = checked(root / "protocol/record.json")
    require(value["schema"] == SCHEMA and value["scientific_root"] == str(SCIENCE_ROOT)
            and value["control_root"] == str(root) and value["scientific_protocol_id"] == SCIENTIFIC_PROTOCOL_ID
            and value["recovery_contract"] == recovery_contract(), "control04 authorization changed")
    controller, signals, observer, gpu_isolation = (importlib.import_module("finqa_v59_" + name)
                                     for name in ("controller", "signals", "observer", "gpu_isolation"))
    require(value["adapter_contract"] == controller.adapter_contract()
            and value["signals_policy"] == signals.signals_policy()
            and value["observer_policy"] == observer.observer_policy()
            and value["gpu_isolation_policy"] == gpu_isolation.gpu_isolation_policy(),
            "bound signal/observer/adapter/GPU-owner-isolation policy changed")
    require(value["max_gpu_workers"] == 4 and value["per_gpu_workers"] == 1,
            "signal recovery cannot enlarge resource concurrency")
    require(read_ref(value["scientific_protocol"])["id"] == SCIENTIFIC_PROTOCOL_ID
            and read_ref(value["previous_control_protocol"])["id"] == PREVIOUS_CONTROL_PROTOCOL_ID
            and read_ref(value["old_stop"])["id"] == PREVIOUS_STOP_ID,
            "original scientific or historical stop binding changed")
    read_ref(value["old_journal"])
    return value


def checked_prepared(root=ROOT):
    protocol = checked_protocol(root)
    value = checked(Path(root) / "prepared/record.json")
    snapshot = validate_snapshot(read_ref(value["preparation_audit"]))
    require(value["schema"] == PREPARED_SCHEMA and read_ref(value["protocol"])["id"] == protocol["id"]
            and value["scientific_root"] == str(SCIENCE_ROOT)
            and value["scientific_protocol_id"] == SCIENTIFIC_PROTOCOL_ID
            and value["remaining_feedback_episodes"] == 0 and value["remaining_new_class_tasks"] == 732
            and value["remaining_new_optimizer_updates"] == 1788 and value["evaluation_sessions"] == 12267
            and value["old_single_request_quota_remaining"] == 0 and value["old_missing_returncode"] is None,
            "remaining scientific budget or unknown historical exit changed")
    require(all(value[key] == snapshot[key] for key in BOOTSTRAP_FIELDS), "actual durable bootstrap snapshot changed")
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
