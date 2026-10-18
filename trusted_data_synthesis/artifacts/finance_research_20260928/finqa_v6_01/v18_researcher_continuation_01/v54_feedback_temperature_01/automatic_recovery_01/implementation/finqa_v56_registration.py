"""Immutable V56 registration for evidence-gated per-job automatic recovery."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import finqa_v54_registration as science
import finqa_v54_runtime as runtime
import finqa_v55_registration as previous

REPO, OLD_ROOT = science.REPO, previous.ROOT
ROOT = science.ROOT / "automatic_recovery_01"
FILES = (*previous.FILES, *("finqa_v56_" + name + ".py" for name in
          ("registration", "controller", "runtime", "worker", "feedback")))
SCHEMA = "v56_evidence_gated_automatic_recovery_protocol.v1"
IMPLEMENTATION_SCHEMA = "v56_frozen_automatic_recovery_implementation.v1"
PREPARED_SCHEMA = "v56_actual_durable_inheritance_ready.v1"
OLD_PROTOCOL_ID = "4d5edf332c3ab3114d21686042fd928a7782d4d04c357b97f92f69e6aa544d3f"
OLD_IMPLEMENTATION_ID = "7d1889c638bac3f93e3fed85d422619e2df6c1363a62052fab79da7c93479e0a"
OLD_PREPARED_ID = "52509ab593601c8a126e32ece9261ede90f70a4240408565b6a595a1a1c10752"
OLD_CLOSEOUT_ID = "c7f8025e1c45b6a959b79e84c48aef27b62898223c50769accf3f0f7028192d5"
require, checked, publish, entry, file_ref, read_ref, sha = (
    runtime.require, runtime.checked, runtime.publish, runtime.entry,
    runtime.file_ref, runtime.read_ref, runtime.sha,
)


def modules():
    # Match the actual CLI: complete scientific imports precede any historical
    # lifecycle observation, whose separately verified controller uses aliases.
    loaded = science.import_science()
    return loaded, *(importlib.import_module("finqa_v56_" + name)
                     for name in ("controller", "runtime", "worker", "feedback"))


def recovery_contract():
    return dict(
        explicit_authorization="处理各种常见问题，设置自动恢复",
        replaces_blanket_stop_pool_no_retry=True,
        original_scientific_experiment="V54 fixed-parent T1 versus T0.5",
        independent_output_root=str(ROOT), inherited_run=str(OLD_ROOT),
        unchanged_mathematical_and_evaluation_contract=True,
        full_complete_parent_audit_repeated=False,
        actual_parent_and_checkpoint_binding_required_at_consumption=True,
        inherited_complete_feedback_episodes=70, inherited_partial_returned_turns=3,
        inherited_complete_class_tasks=9, inherited_complete_class_rows=45,
        initial_new_UNKNOWN_calls=0, old_V54_UNKNOWN_records_preserved=2,
        prior_two_request_reexecution_allowances_remaining=0,
        new_reexecution_of_any_returned_model_call_allowed=False,
        new_UNKNOWN_call_automatic_retry_allowed=False,
        zero_call_pre_call_rejection_can_resume=True,
        complete_feedback_denominator_per_parent=700,
        remaining_feedback_episodes=2030, logical_feedback_target=2100,
        remaining_optimizer_updates=1788, evaluation_sessions=12267,
        inherited_C1_logical_branches=3, inherited_C1_snapshots=6,
        originally_required_new_class_tasks=1488, remaining_new_class_tasks=1479,
        completed_task_cache_overlay_preserves_original_binding=True,
        only_uncommitted_compute_may_be_repeated_with_explicit_overhead_accounting=True,
        old_failed_protocols_and_sources_rewritten=False,
        stable_scientific_state_with_separate_attempt_logs=True,
        confirmed_transient_failure_affects_only_its_job=True,
        independent_ready_jobs_may_continue=True,
        hash_state_numeric_and_unknown_failures_are_not_resources=True,
        no_resource_gate_relaxation_or_automatic_mathematical_fallback=True,
        explicit_stop_disables_automatic_relaunch=True,
    )


def original_evidence(*, verify_exited=False):
    paths = {name: OLD_ROOT / suffix for name, suffix in dict(
        protocol="protocol/record.json", implementation="implementation/record.json",
        prepared="prepared/record.json", controller_launch="launch/record.json",
        controller_closeout="closeout/record.json").items()}
    refs = {name: entry(path) for name, path in paths.items()}
    old = {name: read_ref(ref) for name, ref in refs.items()}
    require((old["protocol"]["id"], old["implementation"]["id"], old["prepared"]["id"],
             old["controller_closeout"]["id"])
            == (OLD_PROTOCOL_ID, OLD_IMPLEMENTATION_ID, OLD_PREPARED_ID, OLD_CLOSEOUT_ID),
            "V56 must inherit the actual stopped V55 run")
    closeout, prepared = old["controller_closeout"], old["prepared"]
    expected_jobs = {"seed137.feedback_C05", "seed251.feedback_C05",
                     "seed389.feedback_C05", "seed137.shard00"}
    require(closeout["status"] == "STOPPED_FAILURE_NO_RETRY" and closeout["active_workers"] == 0
            and closeout["accepted_jobs"] == [] and set(closeout["launched_jobs"]) == expected_jobs
            and closeout["reason"]["job_id"] == "seed389.feedback_C05",
            "initial stopped-job scope changed")
    require(old["protocol"]["scientific_contract"] == science.scientific_contract()
            and prepared["actual_new_optimizer_budget"] == 1788
            and prepared["new_feedback_sessions"] == 2100
            and prepared["new_evaluation_sessions"] == 12267,
            "inherited scientific dose changed")
    identities = [(old["controller_launch"]["pid"], old["controller_launch"]["birth"])]
    workers = {}
    for key in sorted(expected_jobs):
        coordinate, stage = key.split(".", 1)
        directory = OLD_ROOT / "stages" / coordinate / stage
        launched = checked(directory / "launch/record.json")
        exited = checked(directory / "actual_exit/record.json")
        require(exited["actual_waitpid_observed"] is True and exited["returncode"] == 1
                and (exited["pid"], exited["birth"]) == (launched["pid"], launched["birth"]),
                "old worker has no matching actual process exit")
        identities.append((launched["pid"], launched["birth"]))
        resource = OLD_ROOT / "resources" / key / f"pid{launched['pid']}"
        workers[key] = dict(launch=entry(directory / "launch/record.json"),
            actual_exit=entry(directory / "actual_exit/record.json"),
            failure=entry(directory / "attempts/attempt0001/failure/record.json"),
            resources=entry(resource / "closeout/record.json"),
            resource_log=file_ref(resource / "observations.jsonl"))
    primary = read_ref(workers["seed389.feedback_C05"]["resources"])["resources"]["observed_violation"]
    require(primary["label"] == "feedback.before_actual_feedback_call"
            and primary["free_bytes"] == 1855324160 and primary["free_pass"] is False
            and primary["allocated_pass"] is True and primary["host"]["passed"] is True,
            "initial resource failure is not the documented pre-call capacity gate")
    if verify_exited:
        require(all(runtime.birth(pid) != birth for pid, birth in identities),
                "a previous scientific/controller identity is still active")
    parents = {}
    for seed in science.SEEDS:
        parent = read_ref(prepared["parents"][str(seed)])
        require(parent["protocol_id"] == OLD_PROTOCOL_ID and parent["seed"] == seed
                and parent["c1_reuse"]["eligible"] is True, "wrong accepted original parent")
        read_ref(parent["task_plan"])
        for reference in (parent["parent_checkpoint"], parent["old_outer_checkpoint"],
                          *parent["c1_reuse"]["snapshots"].values()):
            require(sha(Path(reference["path"]) / "record.json") == reference["record_sha256"],
                    "actual registered checkpoint metadata changed")
        branch = read_ref(prepared["c1_branches"][f"seed{seed}/C1"])
        require(branch["status"] == "COMPLETE" and branch["new_optimizer_updates"] == 0
                and branch["training_binding"]["parent_id"] == parent["id"]
                and branch["snapshots"] == parent["c1_reuse"]["snapshots"],
                "read-only C1 proof changed")
        parents[str(seed)] = parent
    reexecution = closeout["feedback_request_recovery"]
    require(reexecution["actual_returned_reexecution_calls"] == 2
            and set(reexecution["actual_claims"]) == set(reexecution["actual_returned_receipts"])
                == {"137", "389"}, "prior single-request allowances are not fully consumed")
    for seed in ("137", "389"):
        claim, resolution = (read_ref(reexecution[name][seed]) for name in
                             ("actual_claims", "actual_returned_receipts"))
        require(resolution["claim_id"] == claim["id"] and resolution["new_actual_model_calls"] == 1
                and resolution["old_unknown_reclassified"] is False,
                "prior actual returned request evidence changed")
    return dict(records=old, parents=parents, references=dict(**refs, workers=workers),
        process_identities=[dict(pid=pid, birth=birth) for pid, birth in identities],
        inherited_feedback_reexecutions=dict(authorization_id=reexecution["authorization_id"],
            claims=reexecution["actual_claims"], resolutions=reexecution["actual_returned_receipts"],
            actual_returned_calls=2, new_old_request_reexecutions=0),
        inherited_resource_wait_seconds=closeout["resource_wait_seconds"])


def inherited_parent_body(parent, protocol_id, source, prepared):
    value = copy.deepcopy({k: v for k, v in parent.items() if k != "id"})
    value["protocol_id"] = protocol_id
    value["recovery_lineage"] = dict(schema="v56_same_scientific_parent_inheritance.v1",
        original_parent=source, original_prepared=prepared, source_parent_id=parent["id"],
        original_protocol_id=parent["protocol_id"], scientific_fields_unchanged=True)
    return value


def dependency_sources():
    modules()
    return {path: value for path, value in science.dependency_sources().items()
            if Path(path).name not in FILES}


def freeze(root, source_commit, dependencies, evidence):
    root = Path(root).resolve()
    require(root == ROOT and not root.exists(), "V56 requires one fresh independent root")
    commit = subprocess.check_output(["git", "rev-parse", source_commit + "^{commit}"], cwd=REPO, text=True).strip()
    original = checked(science.SOURCE_BUNDLE / "record.json")
    require(original["id"] == science.SOURCE_BUNDLE_ID and len(original["sha256"]) == 81,
            "original mathematical implementation changed")
    sources = {}
    for name, expected in original["sha256"].items():
        raw = (science.SOURCE_BUNDLE / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, "original source changed: " + name)
        sources[name] = raw
    for name in FILES:
        path = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", commit + ":" + path], cwd=REPO)
        require(hashlib.sha256(raw).hexdigest() == sha(REPO / path), "uncommitted recovery source: " + name)
        sources[name] = raw
    require(len(sources) == 96 and len(FILES) == 15, "96 registered execution files required")
    destination = root / "implementation"
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (destination / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    return publish(destination / "record.json", dict(schema=IMPLEMENTATION_SCHEMA, at=runtime.now(),
        source_commit=commit, committed_files=list(FILES),
        original_implementation=entry(science.SOURCE_BUNDLE / "record.json"),
        previous_V55_implementation=evidence["references"]["implementation"],
        sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        external_frozen_source_sha256=dependencies, frozen_source_root=str(science.FROZEN_SOURCE),
        original_81_scientific_files_modified=False, historical_failed_sources_modified=False))


def checked_implementation(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "unregistered V56 implementation root")
    value = checked(root / "implementation/record.json")
    original = read_ref(value["original_implementation"])
    require(value["schema"] == IMPLEMENTATION_SCHEMA and value["committed_files"] == list(FILES)
            and len(value["sha256"]) == 96 and original["id"] == science.SOURCE_BUNDLE_ID
            and set(value["sha256"]) == set(original["sha256"]) | set(FILES)
            and all(value["sha256"][name] == expected for name, expected in original["sha256"].items())
            and read_ref(value["previous_V55_implementation"])["id"] == OLD_IMPLEMENTATION_ID,
            "execution package or immutable mathematical lineage changed")
    for name, expected in value["sha256"].items():
        require(sha(root / "implementation" / name) == expected, "frozen execution bytes changed")
    for path, expected in value["external_frozen_source_sha256"].items():
        require(sha(path) == expected, "external frozen scientific dependency changed")
    return value


def checked_protocol(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "unregistered V56 automatic recovery root")
    protocol = checked(root / "protocol/record.json")
    controller, resources, worker, feedback = (
        importlib.import_module("finqa_v56_" + name)
        for name in ("controller", "runtime", "worker", "feedback"))
    old = read_ref(protocol["inherited_experiment"]["protocol"])
    require(protocol["schema"] == SCHEMA and protocol["output_root"] == str(root)
            and old["id"] == OLD_PROTOCOL_ID
            and protocol["scientific_contract"] == old["scientific_contract"] == science.scientific_contract()
            and protocol["evaluation"] == old["evaluation"]
            and protocol["recovery_contract"] == recovery_contract()
            and protocol["resource_policy"] == runtime.resource_policy()
            and protocol["auto_recovery_policy"] == controller.auto_recovery_policy()
            and protocol["resource_recovery_policy"] == resources.resource_recovery_policy()
            and "feedback_recovery" not in protocol
            and protocol["max_gpu_workers"] == 4 and protocol["max_workers_per_gpu"] == 1
            and protocol["allowed_gpu_indices"] == list(range(8))
            and protocol["gpu_uuids"] == runtime.GPU_UUIDS
            and protocol["cpu_affinity"] == runtime.CPU_AFFINITY
            and protocol["gpu_lease_root"] == str(science.TRAINING_ROOT / "locks")
            and set(protocol["gpu_priority"]) == set(range(8)) and len(protocol["gpu_priority"]) == 8
            and protocol["parents"] == {str(s): str(root / f"parents/seed{s}/record.json") for s in science.SEEDS},
            "registered automatic-recovery policy, science or device contract changed")
    closeout = read_ref(protocol["inherited_experiment"]["controller_closeout"])
    require(closeout["id"] == OLD_CLOSEOUT_ID
            and protocol["inherited_resource_wait_seconds"] == closeout["resource_wait_seconds"],
            "historical waiting accounting cannot reset")
    feedback.checked_inheritance(protocol["feedback_inheritance"])
    worker.checked_class_inheritance(protocol["class_cache_inheritance"])
    require(protocol["feedback_inheritance"]["old_root"] == str(OLD_ROOT)
            and protocol["class_cache_inheritance"]["old_root"] == str(OLD_ROOT)
            and protocol["feedback_inheritance"]["inherited_complete_episodes"] == 70
            and protocol["feedback_inheritance"]["inherited_partial_returned_turns"] == 3
            and protocol["class_cache_inheritance"]["total_inherited_tasks"] == 9
            and protocol["class_cache_inheritance"]["total_inherited_rows"] == 45,
            "initial feedback resume boundary changed")
    source_prepared = read_ref(protocol["inherited_experiment"]["prepared"])
    for seed in science.SEEDS:
        row = protocol["feedback_inheritance"]["seeds"][str(seed)]
        source = source_prepared["parents"][str(seed)]
        require(row["old_parent"] == {key: source[key] for key in ("path", "sha256")},
                "feedback inheritance must use the same accepted parent")
        require(protocol["class_cache_inheritance"]["seeds"][str(seed)]["original_parent"] == source,
                "class overlay must use the same accepted parent")
    recovered = closeout["feedback_request_recovery"]
    require(protocol["inherited_feedback_reexecutions"] == dict(
        authorization_id=recovered["authorization_id"], claims=recovered["actual_claims"],
        resolutions=recovered["actual_returned_receipts"], actual_returned_calls=2,
        new_old_request_reexecutions=0), "consumed one-shot requests must not receive another allowance")
    require(protocol["implementation"]["path"] == str(root / "implementation/record.json")
            and read_ref(protocol["implementation"])["schema"] == IMPLEMENTATION_SCHEMA,
            "wrong new execution package")
    return protocol


def checked_prepared(root=ROOT):
    root = Path(root).resolve()
    protocol, value = checked_protocol(root), checked(root / "prepared/record.json")
    original_ref = protocol["inherited_experiment"]["prepared"]
    old = read_ref(original_ref)
    require(value["schema"] == PREPARED_SCHEMA and read_ref(value["protocol"]) == protocol
            and old["id"] == OLD_PREPARED_ID and value["original_prepared"] == original_ref
            and set(value["parents"]) == {str(seed) for seed in science.SEEDS}
            and set(value["c1_branches"]) == {f"seed{seed}/C1" for seed in science.SEEDS}
            and value["actual_new_optimizer_budget"] == 1788
            and value["logical_optimizer_updates"] == 2682 and value["reused_C1_logical_updates"] == 894
            and value["new_feedback_sessions"] == 2100 and value["remaining_feedback_episodes"] == 2030
            and value["new_evaluation_sessions"] == 12267 and value["total_new_sessions"] == 14367
            and value["inherited_complete_feedback_episodes"] == 70
            and value["inherited_partial_returned_turns"] == 3
            and value["inherited_complete_class_tasks"] == 9 and value["inherited_class_rows"] == 45
            and value["remaining_new_class_tasks"] == 1479
            and value["old_single_request_allowance_remaining"] == 0,
            "prepared state or unchanged scientific dose differs")
    for seed in science.SEEDS:
        ref = value["parents"][str(seed)]
        parent, source = read_ref(ref), old["parents"][str(seed)]
        require(ref["path"] == protocol["parents"][str(seed)]
                and {k: v for k, v in parent.items() if k != "id"}
                    == inherited_parent_body(read_ref(source), protocol["id"], source, original_ref),
                "scientific parent changed beyond new audit lineage")
        read_ref(parent["task_plan"])
        branch_ref = value["c1_branches"][f"seed{seed}/C1"]
        branch = read_ref(branch_ref)
        require(branch_ref["path"] == str(root / f"branches/seed{seed}/C1/completed/record.json")
                and branch["protocol_id"] == protocol["id"] and branch["status"] == "COMPLETE"
                and (branch["seed"], branch["arm"], branch["optimizer_updates"], branch["new_optimizer_updates"])
                    == (seed, "C1", 298, 0)
                and branch["parent_state_digest"] == parent["parent_state_digest"]
                and branch["snapshots"] == parent["c1_reuse"]["snapshots"]
                and branch["distribution_digest"] == parent["c1_reuse"]["q_digest"]
                and branch["training_binding"]["parent_id"] == parent["id"]
                and branch["training_binding"]["c1_proof_digest"] == runtime.digest(parent["c1_reuse"])
                and branch["next_outer894_executed"] is False,
                "inherited C1 actual path proof changed")
    return value


def preflight(*, feedback_inheritance_cache=None, class_inheritance_cache=None):
    dependencies = dependency_sources()
    loaded, controller, resources, worker, feedback = modules()
    evidence = original_evidence(verify_exited=True)
    feedback_state = (feedback.build_inheritance(OLD_ROOT) if feedback_inheritance_cache is None
                      else feedback.checked_inheritance(json.loads(Path(feedback_inheritance_cache).read_bytes())))
    class_state = (worker.build_class_inheritance(OLD_ROOT) if class_inheritance_cache is None
                   else worker.checked_class_inheritance(json.loads(Path(class_inheritance_cache).read_bytes())))
    require(feedback_state["old_root"] == str(OLD_ROOT)
            and read_ref(feedback_state["old_closeout"])["id"] == OLD_CLOSEOUT_ID,
            "cached feedback manifest is not the actual stopped scientific source")
    worker.checked_class_inheritance(class_state)
    require(class_state["total_inherited_tasks"] == 9 and class_state["total_inherited_rows"] == 45,
            "actual original complete class cache differs")
    require(class_state["old_root"] == str(OLD_ROOT), "class cache lineage must remain the actual old V55 root")
    rows = runtime.inventory()
    require({r["index"]: r["uuid"] for r in rows} == {int(k): v for k, v in runtime.GPU_UUIDS.items()},
            "authorized physical device identities changed")
    require(not loaded[2].torch.cuda.is_initialized(), "recovery preflight must not initialize CUDA")
    return dependencies, evidence, feedback_state, class_state, rows, loaded


def prepare(root=ROOT, *, source_commit, feedback_inheritance_cache=None, class_inheritance_cache=None):
    root = Path(root).resolve()
    require(root == ROOT and not root.exists(), "automatic recovery requires the one fresh registered root")
    dependencies, evidence, feedback_state, class_state, rows, loaded = preflight(
        feedback_inheritance_cache=feedback_inheritance_cache, class_inheritance_cache=class_inheritance_cache)
    minimum = evidence["records"]["prepared"]["disk_minimum_admission_bytes"]
    available = shutil.disk_usage(root.parent).free
    require(available >= minimum, "insufficient disk for original actual gradient/checkpoint budget")
    implementation = freeze(root, source_commit, dependencies, evidence)
    old_protocol, old_prepared = evidence["records"]["protocol"], evidence["records"]["prepared"]
    body = copy.deepcopy({k: v for k, v in old_protocol.items()
                          if k not in ("id", "feedback_recovery", "recovery_contract")})
    body.update(schema=SCHEMA, at=runtime.now(), output_root=str(root),
        authorization="用户明确要求处理常见问题并设置自动恢复，继承实际完整反馈、部分返回和任务缓存",
        source_commit=implementation["source_commit"], implementation=entry(root / "implementation/record.json"),
        parents={str(s): str(root / f"parents/seed{s}/record.json") for s in science.SEEDS},
        recovery_contract=recovery_contract(), resource_policy=runtime.resource_policy(),
        auto_recovery_policy=importlib.import_module("finqa_v56_controller").auto_recovery_policy(),
        resource_recovery_policy=importlib.import_module("finqa_v56_runtime").resource_recovery_policy(),
        inherited_experiment=evidence["references"], feedback_inheritance=feedback_state,
        class_cache_inheritance=class_state, inherited_feedback_reexecutions=evidence["inherited_feedback_reexecutions"],
        inherited_resource_wait_seconds=evidence["inherited_resource_wait_seconds"],
        initial_resource_inventory=rows, automatic_scientific_retry="verified_durable_transient_only",
        scientific_failure_stops_pool=False, independent_failure_isolation=True,
        pre_scientific_resource_wait_only=False,
        bounded_pre_call_capacity_wait_and_durable_cold_restarts=True,
        manual_stop_is_terminal=True, new_UNKNOWN_feedback_retry=False,
        historical_worker_wait_overlaps_not_double_counted=True)
    protocol = publish(root / "protocol/record.json", body)
    parents, branches = {}, {}
    for seed in science.SEEDS:
        source = old_prepared["parents"][str(seed)]
        publish(root / f"parents/seed{seed}/record.json", inherited_parent_body(
            evidence["parents"][str(seed)], protocol["id"], source, evidence["references"]["prepared"]))
        parents[str(seed)] = entry(root / f"parents/seed{seed}/record.json")
        loaded[0].publish_c1_reuse(root, seed, protocol["id"])
        branches[f"seed{seed}/C1"] = entry(root / f"branches/seed{seed}/C1/completed/record.json")
    return publish(root / "prepared/record.json", dict(schema=PREPARED_SCHEMA, at=runtime.now(),
        protocol=entry(root / "protocol/record.json"), original_prepared=evidence["references"]["prepared"],
        parents=parents, c1_branches=branches, actual_new_optimizer_budget=1788,
        logical_optimizer_updates=2682, reused_C1_logical_updates=894,
        new_feedback_sessions=2100, reused_feedback_sessions=2100, remaining_feedback_episodes=2030,
        inherited_complete_feedback_episodes=70, inherited_partial_returned_turns=3,
        new_evaluation_sessions=12267, total_new_sessions=14367,
        new_class_task_count=1488, inherited_complete_class_tasks=9, remaining_new_class_tasks=1479,
        inherited_class_rows=45, inherited_resource_wait_seconds=evidence["inherited_resource_wait_seconds"],
        old_single_request_allowance_remaining=0, new_UNKNOWN_retry_authorized=False,
        inherited_feedback_manifest_id=feedback_state["id"], inherited_class_manifest_id=class_state["id"],
        read_only_preflight_manifest_reused=dict(feedback=feedback_inheritance_cache is not None,
                                               class_cache=class_inheritance_cache is not None),
        original_parent_mathematical_audit_reexecuted=False,
        disk_free_bytes=available, disk_minimum_admission_bytes=minimum,
        cpu_preparation_only=True, CUDA_initialized=False, scientific_supervisor_started=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--feedback-inheritance-cache", type=Path)
    parser.add_argument("--class-inheritance-cache", type=Path)
    args = parser.parse_args()
    result = prepare(args.root, source_commit=args.source_commit,
                     feedback_inheritance_cache=args.feedback_inheritance_cache,
                     class_inheritance_cache=args.class_inheritance_cache)
    print(json.dumps(dict(prepared_id=result["id"], root=str(args.root), remaining_feedback_episodes=2030)))


if __name__ == "__main__":
    main()
