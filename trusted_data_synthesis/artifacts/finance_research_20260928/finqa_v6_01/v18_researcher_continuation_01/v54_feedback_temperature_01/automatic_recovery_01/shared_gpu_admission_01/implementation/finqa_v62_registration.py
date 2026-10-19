"""Freeze the account watchdog without taking over the active scientific pool.

The master authorizes observations first. A successor is independently registered
only from the guard's stopped-identity and original durable-audit transaction.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import stat
import subprocess
import time

from finqa_v62_binding import (MASTER_ROOT, REPO, SCIENCE_ROOT, SOURCE_CONTROL_ROOT,
    SOURCE_CONTROL_PROTOCOL_ID, SCIENTIFIC_PROTOCOL_ID, checked_record, digest,
    episode_root, checked_v59_implementation, load_v59_module, require,
    PARENT_WATCHDOG_ROOT, PARENT_WATCHDOG_PROTOCOL_ID, resource_override,
    SUPERSEDED_MASTER_ROOT, SUPERSEDED_MASTER_PROTOCOL_ID, PREPARATION_ROOT)

ROOT = MASTER_ROOT
MASTER_SCHEMA = "v62_registered_account_watchdog.v1"
EPISODE_SCHEMA = "v62_registered_same_science_successor.v1"
NEW_FILES = tuple("finqa_v62_" + name + ".py" for name in
    ("registration", "backend", "watchdog", "binding", "controller", "observer", "cron", "handoff",
     "worker", "gpu_isolation", "supersession"))
INHERITED_FILES = tuple("finqa_v59_" + name + ".py" for name in
    ("registration", "controller", "signals", "observer", "worker", "gpu_isolation"))
FILES = INHERITED_FILES + NEW_FILES
BOOTSTRAP_FIELDS = ("initial_job_states", "attempt_history", "accepted", "evaluation_registered",
    "resource_wait_seconds", "known_unobserved_attempts", "all_old_attempts",
    "resume_audits", "process_identities", "old_journal")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def entry(path):
    path = Path(path).resolve()
    value = checked_record(path)
    return dict(path=str(path), id=value["id"], sha256=sha(path))


def read_ref(reference):
    path = Path(reference["path"])
    require(sha(path) == reference["sha256"], "immutable record bytes changed: " + str(path))
    value = checked_record(path)
    # Original evaluation bindings contain path+SHA only; their record's own
    # canonical ID is still checked. New references additionally bind the ID.
    require("id" not in reference or value["id"] == reference["id"], "immutable record identity changed")
    return value


def publish(path, value):
    from finqa_v62_watchdog import write_record
    return write_record(path, value, immutable=True)


def policy_modules():
    return tuple(importlib.import_module("finqa_v62_" + name)
                 for name in ("watchdog", "controller", "observer"))


def original_lock_paths(protocol):
    from finqa_v62_watchdog import GPU_LEASE_ROOT
    require(Path(protocol["gpu_lease_root"]).resolve() == GPU_LEASE_ROOT
            and set(protocol["gpu_uuids"]) == {str(index) for index in range(8)},
            "original eight registered GPU leases required")
    return [SCIENCE_ROOT / "owner.lock", *[GPU_LEASE_ROOT /
        ("gpu-" + digest(protocol["gpu_uuids"][str(index)]) + ".lock") for index in range(8)]]


def bind_original_locks(protocol):
    result = {}
    for path in original_lock_paths(protocol):
        value = path.lstat()
        require(stat.S_ISREG(value.st_mode), "original lease is not a regular existing file")
        result[str(path)] = dict(device=value.st_dev, inode=value.st_ino)
    return result


def recovery_contract():
    return dict(schema="v62_same_science_account_guard_contract.v1", owner_uid=1004,
        scientific_root=str(SCIENCE_ROOT), scientific_protocol_id=SCIENTIFIC_PROTOCOL_ID,
        initial_control_root=str(SOURCE_CONTROL_ROOT), initial_control_protocol_id=SOURCE_CONTROL_PROTOCOL_ID,
        initial_action="observe_only_until_authorized_safe_handoff", old_files_or_stops_rewritten=False,
        accepted_jobs_attempt_ordinals_and_durable_values_preserved=True,
        cumulative_resource_wait_never_reset=True, new_feedback_budget=0,
        original_scientific_dose_unchanged=True, unknown_feedback_blocks_recovery=True,
        known_hash_state_numeric_or_implementation_failure_blocks_recovery=True,
        same_account_stop_SIGTERM_all_SIGINT_and_STOP_terminal=True,
        unknown_OS_exit_never_fabricated=True, manual_SIGKILL_may_recover_without_stop_intent=True,
        all_scientific_and_control_identities_gone_before_successor=True,
        original_all_or_none_project_leases_and_owner_lock_required=True,
        fresh_registered_successor_only=True, initial_one_shot_controller_not_reexecuted=True,
        independent_GPU_workers=6, per_GPU_workers=1, independent_CPU_observers=1,
        original_scientific_max_gpu_workers=4, effective_resource_override=resource_override(),
        old_watchdog_root=str(PARENT_WATCHDOG_ROOT), old_watchdog_protocol_id=PARENT_WATCHDOG_PROTOCOL_ID,
        initial_passive_handoff_required=True, all_core_training_accepted_before_handoff=True,
        initial_registered_maintenance_TERM_only_with_exact_receipt=True,
        unregistered_owner_TERM_all_INT_and_root_STOP_remain_terminal=True,
        old_stop_history_not_reclassified=True, worker_signals_from_handoff=False,
        additional_CPU_runner_per_successor=1, runner_owns_actual_supervisor_waitpid=True,
        readonly_observer_startup_admission_seconds=60, observer_heartbeat_max_age_seconds=10,
        observer_retirement_only_verified_own_readonly_CPU_after_science_exit=True,
        unowned_or_scientific_process_signals_from_guard=False,
        known_account_GPU_exclusion_cancelled=True,
        unknown_owner_and_original_resource_gates_unchanged=True,
        prior_passive_V61_guard_must_be_superseded_without_scientific_STOP=True,
        healthy_observations_do_not_import_torch_or_audit_tensors=True,
        original_job_audit_once_per_stopped_episode=True,
        cron_installation_is_separate_registered_account_action=True,
        root_sudo_or_system_permission_changes=False)


def checked_implementation(root=ROOT):
    root = Path(root).resolve()
    require(root == MASTER_ROOT or episode_root(root) == root, "unregistered watchdog implementation root")
    value = checked_record(MASTER_ROOT / "implementation/record.json")
    require(set(value["files"]) == set(FILES) and value["old_files_modified"] is False,
            "watchdog implementation scope changed")
    for name, expected in value["files"].items():
        require(sha(MASTER_ROOT / "implementation" / name) == expected,
                "frozen watchdog implementation changed: " + name)
    original = read_ref(value["initial_control_implementation"])
    require(set(original["files"]) == set(INHERITED_FILES)
            and all(value["files"][name] == original["files"][name] for name in INHERITED_FILES),
            "original six V59 files must remain byte-identical")
    return value


def checked_master_protocol(root=ROOT):
    root = Path(root).resolve()
    require(root == MASTER_ROOT, "unregistered account watchdog root")
    value = checked_record(root / "protocol/record.json")
    watchdog, _controller, _observer = policy_modules()
    require(value["schema"] == MASTER_SCHEMA and value["root"] == str(root)
            and value["scientific_root"] == str(SCIENCE_ROOT)
            and value["scientific_protocol_id"] == SCIENTIFIC_PROTOCOL_ID
            and value["policy"] == watchdog.policy() and value["recovery_contract"] == recovery_contract(),
            "account watchdog authorization changed")
    require(read_ref(value["initial_control_protocol"])["id"] == SOURCE_CONTROL_PROTOCOL_ID
            and read_ref(value["scientific_protocol"])["id"] == SCIENTIFIC_PROTOCOL_ID,
            "original scientific/control identity changed")
    require(read_ref(value["implementation"])["id"] == checked_implementation(root)["id"],
            "master implementation reference changed")
    require(value["signals_policy"] == load_v59_module("finqa_v59_signals").signals_policy()
            and value["gpu_isolation_policy"] == importlib.import_module("finqa_v62_gpu_isolation").gpu_isolation_policy()
            and value["cron_policy"] == importlib.import_module("finqa_v62_cron").cron_policy(),
            "registered signal or shared-GPU ownership safety policy changed")
    require(set(value["original_lock_bindings"]) == {str(path) for path in original_lock_paths(value)}
            and all(type(row["device"]) is int and type(row["inode"]) is int
                    for row in value["original_lock_bindings"].values()),
            "all nine original lock inode bindings are required")
    require(value["original_scientific_max_gpu_workers"] == 4 and value["max_gpu_workers"] == 6
            and value["per_gpu_workers"] == 1 and value["resource_override"] == resource_override(),
            "six-worker authorization or unchanged hard-resource contract changed")
    require(read_ref(value["prior_watchdog_protocol"])["id"] == PARENT_WATCHDOG_PROTOCOL_ID,
            "the prior four-worker watchdog authorization changed")
    supersession = importlib.import_module("finqa_v62_supersession").checked_completed()
    require(read_ref(value["prior_pending_master_protocol"])["id"] == SUPERSEDED_MASTER_PROTOCOL_ID
            and read_ref(value["pending_master_supersession"]) == supersession,
            "prior pending V61 retirement evidence changed")
    handoff = importlib.import_module("finqa_v62_handoff")
    require(value["handoff_policy"] == handoff.policy(), "registered passive handoff policy changed")
    handoff.checked_binding(value["handoff_binding"], require_live=False, allow_superseded=True)
    return value


def checked_protocol(root=ROOT):
    root = Path(root).resolve()
    if root == MASTER_ROOT:
        return checked_master_protocol(root)
    episode_root(root)
    master = checked_master_protocol()
    value = checked_record(root / "protocol/record.json")
    _watchdog, controller, observer = policy_modules()
    require(value["schema"] == EPISODE_SCHEMA and value["control_root"] == str(root)
            and value["scientific_root"] == str(SCIENCE_ROOT)
            and value["scientific_protocol_id"] == SCIENTIFIC_PROTOCOL_ID
            and value["master_protocol_id"] == master["id"]
            and value["implementation"] == master["implementation"]
            and value["adapter_contract"] == controller.adapter_contract(root)
            and value["observer_policy"] == observer.observer_policy()
            and value["signals_policy"] == master["signals_policy"]
            and value["gpu_isolation_policy"] == master["gpu_isolation_policy"]
            and value["max_gpu_workers"] == 6 and value["original_scientific_max_gpu_workers"] == 4
            and value["per_gpu_workers"] == 1 and value["resource_override"] == resource_override(),
            "successor changed the original control, resource or signal contract")
    read_ref(value["durable_audit"])
    read_ref(value["exit_observation"])
    return value


def checked_prepared(root=ROOT):
    root = Path(root).resolve()
    protocol = checked_protocol(root)
    value = checked_record(root / "prepared/record.json")
    require(value["protocol_id"] == protocol["id"], "preparation belongs to another authorization")
    if root == MASTER_ROOT:
        require(value["pending_master_supersession_id"] == read_ref(protocol["pending_master_supersession"])["id"],
                "initial preparation must bind the exact completed V61 retirement")
        require(value["handoff_binding"] == protocol["handoff_binding"]
            and value["initial_episode"] == dict(root=str(SOURCE_CONTROL_ROOT),
            protocol_id=SOURCE_CONTROL_PROTOCOL_ID) and value["initial_action"] == "observe_only_until_authorized_safe_handoff",
            "fresh master must only observe its exact original active episode")
    else:
        audit = read_ref(value["preparation_audit"])
        require(value["scientific_root"] == str(SCIENCE_ROOT)
                and value["scientific_protocol_id"] == SCIENTIFIC_PROTOCOL_ID
                and all(value[key] == audit["bootstrap"][key] for key in BOOTSTRAP_FIELDS)
                and value["old_missing_returncode"] is None and value["new_feedback_budget"] == 0,
                "successor cannot reset state, attempts, budget or unknown exits")
    return value


def prepare(source_commit="HEAD", root=ROOT):
    root = Path(root).resolve()
    require(root == MASTER_ROOT and not root.exists(), "one fresh independent master root required")
    require(os.getuid() == os.geteuid() == 1004, "master must be prepared by the registered account")
    watchdog, _controller, _observer = policy_modules()
    supersession = importlib.import_module("finqa_v62_supersession").checked_completed()
    old = checked_v59_implementation()
    science = checked_record(SCIENCE_ROOT / "protocol/record.json")
    require(science["id"] == SCIENTIFIC_PROTOCOL_ID, "original scientific protocol changed")
    commit = subprocess.check_output(["git", "rev-parse", source_commit + "^{commit}"], cwd=REPO, text=True).strip()
    sources = {}
    for name in NEW_FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=REPO)
        require(hashlib.sha256(raw).hexdigest() == sha(REPO / relative), "uncommitted watchdog source: " + name)
        sources[name] = raw
    for name in INHERITED_FILES:
        raw = (SOURCE_CONTROL_ROOT / "implementation" / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == old["files"][name], "source V59 bytes changed")
        sources[name] = raw
    handoff = importlib.import_module("finqa_v62_handoff")
    handoff_binding = handoff.snapshot_binding()
    handoff.checked_binding(handoff_binding, require_live=True, allow_superseded=False)
    require(science["max_gpu_workers"] == 4, "the original scientific worker limit must remain four")
    directory = root / "implementation"
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (directory / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    publish(directory / "record.json", dict(schema="v62_frozen_account_watchdog_implementation.v1",
        source_commit=commit, files={name: sha(directory / name) for name in FILES}, old_files_modified=False,
        initial_control_implementation=entry(SOURCE_CONTROL_ROOT / "implementation/record.json"),
        original_scientific_implementation=entry(SCIENCE_ROOT / "implementation/record.json"),
        prior_watchdog_implementation=entry(PARENT_WATCHDOG_ROOT / "implementation/record.json"),
        prior_pending_master_implementation=entry(SUPERSEDED_MASTER_ROOT / "implementation/record.json")))
    lease_fields = dict(gpu_lease_root=str(watchdog.GPU_LEASE_ROOT), gpu_uuids=science["gpu_uuids"])
    lock_bindings = bind_original_locks(lease_fields)
    protocol = publish(root / "protocol/record.json", dict(schema=MASTER_SCHEMA, root=str(root),
        scientific_root=str(SCIENCE_ROOT), scientific_protocol_id=SCIENTIFIC_PROTOCOL_ID,
        registered_epoch=time.time(), implementation=entry(directory / "record.json"),
        original_scientific_max_gpu_workers=4, max_gpu_workers=6, per_gpu_workers=1,
        resource_override=resource_override(), handoff_policy=handoff.policy(), handoff_binding=handoff_binding,
        prior_watchdog_protocol=entry(PARENT_WATCHDOG_ROOT / "protocol/record.json"),
        prior_pending_master_protocol=entry(SUPERSEDED_MASTER_ROOT / "protocol/record.json"),
        pending_master_supersession=entry(PREPARATION_ROOT / "completed/record.json"),
        scientific_protocol=entry(SCIENCE_ROOT / "protocol/record.json"),
        initial_control_protocol=entry(SOURCE_CONTROL_ROOT / "protocol/record.json"),
        policy=watchdog.policy(), recovery_contract=recovery_contract(),
        **lease_fields, original_lock_bindings=lock_bindings,
        cron_policy=importlib.import_module("finqa_v62_cron").cron_policy(),
        signals_policy=load_v59_module("finqa_v59_signals").signals_policy(),
        gpu_isolation_policy=importlib.import_module("finqa_v62_gpu_isolation").gpu_isolation_policy()))
    prepared = publish(root / "prepared/record.json", dict(schema="v62_initial_observation_ready.v1",
        protocol_id=protocol["id"], initial_action="observe_only_until_authorized_safe_handoff",
        initial_episode=dict(root=str(SOURCE_CONTROL_ROOT), protocol_id=SOURCE_CONTROL_PROTOCOL_ID),
        handoff_binding=handoff_binding, resource_override=resource_override(),
        pending_master_supersession_id=supersession["id"],
        cron_installed=False, scientific_workers_started=0, observer_retired=False))
    return dict(protocol_id=protocol["id"], prepared_id=prepared["id"], source_commit=commit)


def register_successor(root, predecessor, observation, audits, request_id):
    master = checked_master_protocol(root)
    require(request_id.startswith("request") and request_id[7:].isdigit(), "invalid recovery request")
    destination = episode_root(Path(root) / "episodes" / ("episode" + request_id[7:]))
    request = Path(root) / "requests" / request_id
    require(read_ref(entry(request / "durable_audit/record.json")) == audits
            and read_ref(entry(request / "exit_observation/record.json")) == observation,
            "successor requires immutable guard admission records")
    from finqa_v62_watchdog import checked_audits
    checked_audits(audits, observation)
    _watchdog, controller, observer = policy_modules()
    body = dict(schema=EPISODE_SCHEMA, control_root=str(destination), scientific_root=str(SCIENCE_ROOT),
        scientific_protocol_id=SCIENTIFIC_PROTOCOL_ID, master_protocol_id=master["id"],
        request_id=request_id, predecessor=predecessor, implementation=master["implementation"],
        scientific_protocol=master["scientific_protocol"],
        durable_audit=entry(request / "durable_audit/record.json"),
        exit_observation=entry(request / "exit_observation/record.json"),
        adapter_contract=controller.adapter_contract(destination), observer_policy=observer.observer_policy(),
        signals_policy=master["signals_policy"], gpu_isolation_policy=master["gpu_isolation_policy"],
        original_scientific_max_gpu_workers=4, max_gpu_workers=6, per_gpu_workers=1,
        resource_override=resource_override(), new_feedback_budget=0, old_missing_returncode=None)
    protocol = publish(destination / "protocol/record.json", body)
    bootstrap = copy.deepcopy(audits["bootstrap"])
    prepared = publish(destination / "prepared/record.json", dict(schema="v62_same_state_successor_ready.v1",
        protocol_id=protocol["id"], scientific_root=str(SCIENCE_ROOT), scientific_protocol_id=SCIENTIFIC_PROTOCOL_ID,
        preparation_audit=entry(request / "durable_audit/record.json"), **bootstrap,
        new_feedback_budget=0, old_missing_returncode=None, attempts_reset=False, budgets_reset=False))
    return dict(episode_root=str(destination), scientific_root=str(SCIENCE_ROOT), request_id=request_id,
        predecessor_root=predecessor["root"], ready_for_launch=True, budgets_reset=False, attempts_reset=False,
        control_protocol_id=protocol["id"], registration_id=prepared["id"])


# The original one-shot driver can keep its default backend module name.
def __getattr__(name):
    if name in {"observe_episode", "checked_authorized_handoff", "audit_durable", "retire_observer", "register_episode",
                "launch_registered", "reconcile_launch"}:
        return getattr(importlib.import_module("finqa_v62_backend"), name)
    raise AttributeError(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "check"))
    parser.add_argument("--source-commit", default="HEAD")
    args = parser.parse_args()
    value = prepare(args.source_commit) if args.action == "prepare" else checked_prepared()
    print(json.dumps(value if args.action == "prepare" else dict(status="READY", id=value["id"]), sort_keys=True))


if __name__ == "__main__":
    main()
