"""Explicit V54 recovery: immutable inherited parents and two one-shot requests.

The failed V54 protocol, implementation and UNKNOWN calls remain historical
evidence. This registration never re-runs the original complete parent audit or
training. Scientific parent fields are inherited byte-bound without alteration.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import math
import os
import shutil
import subprocess
from pathlib import Path

import finqa_v54_registration as base
import finqa_v54_runtime as runtime

REPO, OLD_ROOT = base.REPO, base.ROOT
ROOT = OLD_ROOT / "recovery_01"
FILES = (*base.FILES, "finqa_v55_registration.py", "finqa_v55_feedback_recovery.py")
SCHEMA = "v55_explicit_feedback_request_recovery_protocol.v1"
IMPLEMENTATION_SCHEMA = "v55_frozen_explicit_recovery_implementation.v1"
PREPARED_SCHEMA = "v55_three_inherited_parent_ready.v1"
OLD_PROTOCOL_ID = "0df7315a5443623a705e96ca9371f28fe9470e86b30b16820f6ae583373724f4"
OLD_PREPARED_ID = "32de8dbfcf97acb7ffd487312f8ad62878ced8e9b2b76ba193b3aa4f8708865f"
OLD_IMPLEMENTATION_ID = "d3ffbe95fa28c5881c44b6e225af2e7e6dc9d9e5fdb70c793720ac6dc27eaebf"
OLD_CLOSEOUT_ID = "b25b5424c176637d3f87d9bfb054c7c6ac58add587514328fa38b8c7db593c13"
OLD_AUDIT_ID = "f462756743de7d02cd8f55e31a3175ae9c02e649b18e6cac49cd31380f2835a8"
OLD_WAITING_ID = "c89f256370dafc54bcd0833aca4ff67f461cbafc64259de926b3c7f336419071"
require, checked, publish, entry, file_ref, sha, read_ref = (
    runtime.require, runtime.checked, runtime.publish, runtime.entry,
    runtime.file_ref, runtime.sha, runtime.read_ref,
)


def recovery_contract():
    return dict(
        old_root=str(OLD_ROOT), old_protocol_id=OLD_PROTOCOL_ID,
        explicit_user_authorization="同意为旧137/389两个UNKNOWN请求各重新执行一次，修复后恢复本轮",
        initial_unknown_request_seeds=[137, 389], per_old_unknown_request_attempt_budget=1,
        old_unknown_total=2, old_unknowns_remain_unknown=True,
        seed251_has_no_old_provider_call=True,
        old_unreturned_provider_attempts_not_counted_as_complete_feedback=True,
        old_partial_episodes_not_copied_into_new_collector=True,
        scientific_request_point_condition_temperature_roster_and_seed_unchanged=True,
        no_new_general_automatic_retry_authorization=True,
        future_unknown_requires_explicit_disposition=True,
        complete_parent_audit_reexecuted=False,
        actual_parent_tensor_verification_still_required_before_science=True,
        inherited_parent_changes_only=["protocol_id", "recovery_lineage"],
        old_class_task_plan_and_C1_proof_read_only=True,
        original_81_scientific_files_unchanged=True,
        new_class_tasks=1488, new_optimizer_updates=1788,
        new_complete_feedback_sessions=2100, new_evaluation_sessions=12267,
        old_failed_attempts_rewritten=False, old_controller_restarted=False,
        deterministic_CUBLAS_workspace_config=runtime.CUBLAS_WORKSPACE_CONFIG,
        all_other_scientific_and_evaluation_contracts_unchanged=True,
    )


def _guard_module():
    return importlib.import_module("finqa_v55_feedback_recovery")


def _old_record(path, identity):
    value = checked(path)
    require(value["id"] == identity, "wrong historical recovery authority: " + str(path))
    return value


def original_evidence(*, verify_exited=False):
    """Metadata and hash inheritance, without reloading old model/Adam tensors."""
    waiting = _old_record(OLD_ROOT / "closeout_verification_01/waiting_supplement/record.json", OLD_WAITING_ID)
    audit = read_ref(waiting["parent_audit"])
    require(audit["id"] == OLD_AUDIT_ID, "historical failure audit differs")
    references = {key: audit[key] for key in (
        "protocol", "implementation", "prepared", "controller_launch", "controller_closeout")}
    old = {key: read_ref(reference) for key, reference in references.items()}
    require(old["protocol"]["id"] == OLD_PROTOCOL_ID
            and old["implementation"]["id"] == OLD_IMPLEMENTATION_ID
            and old["prepared"]["id"] == OLD_PREPARED_ID
            and old["controller_closeout"]["id"] == OLD_CLOSEOUT_ID,
            "old protocol/prepared/implementation/failure identity changed")
    require(old["controller_closeout"]["status"] == "STOPPED_FAILURE_NO_RETRY"
            and old["controller_closeout"]["accepted_jobs"] == []
            and old["controller_closeout"]["active_workers"] == 0
            and set(old["controller_closeout"]["launched_jobs"])
                == {f"seed{seed}.feedback_C05" for seed in base.SEEDS},
            "recovery scope is only the failed initial three-feedback dispatch")
    require(old["protocol"]["scientific_contract"] == base.scientific_contract()
            and old["prepared"]["actual_new_optimizer_budget"] == 1788
            and old["prepared"]["new_feedback_sessions"] == 2100
            and old["prepared"]["new_evaluation_sessions"] == 12267
            and set(old["prepared"]["c1_branches"])
                == {f"seed{seed}/C1" for seed in base.SEEDS},
            "original accepted scientific matrix or remaining dose changed")
    parents = {}
    for seed in base.SEEDS:
        reference = old["prepared"]["parents"][str(seed)]
        parent = read_ref(reference)
        require(parent["schema"] == "v54_actual_parent.v1" and parent["seed"] == seed
                and parent["protocol_id"] == OLD_PROTOCOL_ID and parent["c1_reuse"]["eligible"] is True,
                "original accepted parent/C1 proof differs")
        read_ref(parent["task_plan"])
        for checkpoint in (parent["parent_checkpoint"], parent["old_outer_checkpoint"],
                           *parent["c1_reuse"]["snapshots"].values()):
            require(sha(Path(checkpoint["path"]) / "record.json") == checkpoint["record_sha256"],
                    "registered original checkpoint metadata bytes changed")
        branch = read_ref(old["prepared"]["c1_branches"][f"seed{seed}/C1"])
        require(branch["protocol_id"] == OLD_PROTOCOL_ID and branch["status"] == "COMPLETE"
                and branch["new_optimizer_updates"] == 0
                and branch["snapshots"] == parent["c1_reuse"]["snapshots"]
                and branch["training_binding"]["parent_id"] == parent["id"]
                and branch["distribution_digest"] == parent["c1_reuse"]["q_digest"],
                "original C1 logical branch is not the inherited proof")
        parents[str(seed)] = parent
    workers, identities = {}, []
    controller = old["controller_launch"]
    identities.append(dict(role="controller", pid=controller["pid"], birth=controller["birth"]))
    require(len(audit["workers"]) == 3 and {row["seed"] for row in audit["workers"]} == set(base.SEEDS),
            "all three original worker dispositions required")
    for row in audit["workers"]:
        launch, exit_record = read_ref(row["launch"]), read_ref(row["actual_exit"])
        for key in ("failure", "resources", "resource_observations"):
            reference = row[key]
            require(sha(reference["path"]) == reference["sha256"], "old failure/resource bytes changed")
        require((exit_record["pid"], exit_record["birth"], exit_record["returncode"])
                == (launch["pid"], launch["birth"], 1)
                and exit_record["actual_waitpid_observed"] is True
                and row["complete_feedback_episodes"] == row["returned_token_receipts"] == 0
                and row["unknown_calls"] == (0 if row["seed"] == 251 else 1)
                and row["actual_model_calls"] == (0 if row["seed"] == 251 else 1),
                "old worker exit or UNKNOWN disposition changed")
        workers[str(row["seed"])] = {key: row[key] for key in (
            "launch", "actual_exit", "failure", "resources", "resource_observations")}
        identities.append(dict(role=f"seed{row['seed']}.feedback_C05", pid=launch["pid"], birth=launch["birth"]))
    if verify_exited:
        require(all(runtime.birth(row["pid"]) != row["birth"] for row in identities),
                "an original controller or worker identity is still alive; no recovery dispatch")
    return dict(records=old, parents=parents, references=dict(
        **references, failure_audit=entry(OLD_ROOT / "closeout_verification_01/record.json"),
        waiting_supplement=entry(OLD_ROOT / "closeout_verification_01/waiting_supplement/record.json"),
        workers=workers, stopped_process_identities=identities),
        inherited_resource_wait_seconds=old["controller_closeout"]["resource_wait_seconds"])


def inherited_parent_body(parent, protocol_id, source_reference, old_prepared_reference):
    body = copy.deepcopy({k: v for k, v in parent.items() if k != "id"})
    body["protocol_id"] = protocol_id
    body["recovery_lineage"] = dict(schema="v55_read_only_actual_parent_inheritance.v1",
        original_parent=source_reference, original_prepared=old_prepared_reference,
        original_protocol_id=parent["protocol_id"], source_parent_id=parent["id"],
        scientific_fields_unchanged=True, original_task_plan_reference_preserved=True)
    return body


def validate_inherited_parent(parent, original, protocol_id, reference, old_prepared):
    expected = inherited_parent_body(original, protocol_id, reference, old_prepared)
    require({k: v for k, v in parent.items() if k != "id"} == expected,
            "inherited parent may change only protocol_id and explicit recovery lineage")
    return parent


def dependency_sources():
    base.import_science()
    _guard_module()
    return {path: value for path, value in base.dependency_sources().items()
            if Path(path).name not in FILES}


def freeze(root, source_commit):
    root = Path(root).resolve()
    require(root == ROOT and not root.exists(), "V55 requires the single fresh recovery_01 directory")
    evidence = original_evidence(verify_exited=True)
    commit = subprocess.check_output(["git", "rev-parse", source_commit + "^{commit}"], cwd=REPO, text=True).strip()
    original = checked(base.SOURCE_BUNDLE / "record.json")
    require(original["id"] == base.SOURCE_BUNDLE_ID and len(original["sha256"]) == 81,
            "original immutable scientific implementation changed")
    sources = {}
    for name, expected in original["sha256"].items():
        raw = (base.SOURCE_BUNDLE / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, "original scientific source changed: " + name)
        sources[name] = raw
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=REPO)
        require(hashlib.sha256(raw).hexdigest() == sha(REPO / relative), "uncommitted recovery source: " + name)
        sources[name] = raw
    dependencies = dependency_sources()
    require(len(sources) == 91, "recovery implementation must contain original81 + V54eight + V55two")
    destination = root / "implementation"
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (destination / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    return publish(destination / "record.json", dict(schema=IMPLEMENTATION_SCHEMA, at=runtime.now(),
        source_commit=commit, committed_files=list(FILES),
        original_implementation=entry(base.SOURCE_BUNDLE / "record.json"),
        original_failed_V54_implementation=evidence["references"]["implementation"],
        sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        external_frozen_source_sha256=dependencies, frozen_source_root=str(base.FROZEN_SOURCE),
        original_81_files_modified=False, failed_V54_89_files_modified=False))


def checked_implementation(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "unregistered V55 recovery implementation root")
    value = checked(root / "implementation/record.json")
    original = read_ref(value["original_implementation"])
    require(value["schema"] == IMPLEMENTATION_SCHEMA and value["committed_files"] == list(FILES)
            and len(value["sha256"]) == 91 and original["id"] == base.SOURCE_BUNDLE_ID
            and set(value["sha256"]) == set(original["sha256"]) | set(FILES)
            and all(value["sha256"][name] == expected for name, expected in original["sha256"].items()),
            "recovery must preserve original81 and bind exactly ten new execution files")
    require(read_ref(value["original_failed_V54_implementation"])["id"] == OLD_IMPLEMENTATION_ID,
            "wrong failed V54 implementation lineage")
    for name, expected in value["sha256"].items():
        require(sha(root / "implementation" / name) == expected, "frozen recovery execution bytes changed")
    for path, expected in value["external_frozen_source_sha256"].items():
        require(sha(path) == expected, "external frozen scientific dependency changed")
    return value


def checked_protocol(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "unregistered explicit V55 recovery root")
    protocol = checked(root / "protocol/record.json")
    old = read_ref(protocol["inherited_experiment"]["protocol"])
    require(old["id"] == OLD_PROTOCOL_ID and protocol["schema"] == SCHEMA
            and protocol["output_root"] == str(root)
            and protocol["scientific_contract"] == old["scientific_contract"] == base.scientific_contract()
            and protocol["evaluation"] == old["evaluation"]
                == importlib.import_module("finqa_v54_evaluation").evaluation_contract()
            and protocol["source_parent_checkpoints"] == old["source_parent_checkpoints"]
            and protocol["evaluation_source_registration"] == old["evaluation_source_registration"]
            and protocol["training_source_registration"] == old["training_source_registration"]
            and protocol["recovery_contract"] == recovery_contract()
            and protocol["resource_policy"] == runtime.resource_policy()
            and protocol["gpu_uuids"] == runtime.GPU_UUIDS
            and protocol["allowed_gpu_indices"] == list(range(8))
            and protocol["max_gpu_workers"] == 4 and protocol["max_workers_per_gpu"] == 1
            and protocol["cpu_affinity"] == runtime.CPU_AFFINITY
            and protocol["gpu_lease_root"] == str(base.TRAINING_ROOT / "locks")
            and len(protocol["gpu_priority"]) == 8 and set(protocol["gpu_priority"]) == set(range(8))
            and protocol["parents"] == {str(seed): str(root / f"parents/seed{seed}/record.json") for seed in base.SEEDS},
            "explicit recovery must retain the same scientific/evaluation/resource contract")
    closeout = read_ref(protocol["inherited_experiment"]["controller_closeout"])
    require(closeout["id"] == OLD_CLOSEOUT_ID
            and protocol["inherited_resource_wait_seconds"] == closeout["resource_wait_seconds"]
            and math.isfinite(protocol["inherited_resource_wait_seconds"])
            and protocol["inherited_resource_wait_seconds"] >= 0,
            "inherited resource waiting must not reset or invent elapsed time")
    implementation = read_ref(protocol["implementation"])
    require(protocol["implementation"]["path"] == str(root / "implementation/record.json")
            and implementation["schema"] == IMPLEMENTATION_SCHEMA,
            "recovery implementation identity differs")
    authorization = _guard_module().checked_authorization(protocol["feedback_recovery"])
    old_prepared = read_ref(protocol["inherited_experiment"]["prepared"])
    require(authorization["old_root"] == str(OLD_ROOT) and authorization["recovery_root"] == str(root)
            and authorization["old_protocol"] == {k: protocol["inherited_experiment"]["protocol"][k]
                                                  for k in ("path", "sha256")}
            and authorization["old_closeout"] == {k: protocol["inherited_experiment"]["controller_closeout"][k]
                                                  for k in ("path", "sha256")}
            and all(authorization["seeds"][str(seed)]["old_parent"]
                    == {k: old_prepared["parents"][str(seed)][k] for k in ("path", "sha256")}
                    for seed in base.SEEDS),
            "single-request recovery authorization belongs to different historical evidence")
    return protocol


def checked_prepared(root=ROOT):
    root = Path(root).resolve()
    protocol, value = checked_protocol(root), checked(root / "prepared/record.json")
    old_prepared_ref = protocol["inherited_experiment"]["prepared"]
    old_prepared = read_ref(old_prepared_ref)
    require(old_prepared["id"] == OLD_PREPARED_ID and value["schema"] == PREPARED_SCHEMA
            and read_ref(value["protocol"]) == protocol and value["original_prepared"] == old_prepared_ref
            and set(value["parents"]) == {str(seed) for seed in base.SEEDS}
            and set(value["c1_branches"]) == {f"seed{seed}/C1" for seed in base.SEEDS}
            and value["actual_new_optimizer_budget"] == 1788
            and value["new_feedback_sessions"] == 2100 and value["new_evaluation_sessions"] == 12267
            and value["total_new_sessions"] == 14367,
            "recovery parent membership or unchanged scientific dose differs")
    for seed in base.SEEDS:
        reference = value["parents"][str(seed)]
        parent = read_ref(reference)
        old_ref = old_prepared["parents"][str(seed)]
        require(reference["path"] == protocol["parents"][str(seed)], "new parent envelope path changed")
        validate_inherited_parent(parent, read_ref(old_ref), protocol["id"], old_ref, old_prepared_ref)
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
                "new C1 logical reference must preserve the original complete training proof")
    return value


def prepare(root=ROOT, *, source_commit):
    root = Path(root).resolve()
    implementation = freeze(root, source_commit)
    evidence = original_evidence(verify_exited=True)
    training_api, _training, rt, evaluation, _temperature = base.import_science()
    old_protocol, old_prepared = evidence["records"]["protocol"], evidence["records"]["prepared"]
    authorization = _guard_module().build_registration(OLD_ROOT)
    _guard_module().checked_authorization(authorization)
    rows = runtime.inventory()
    require({row["index"]: row["uuid"] for row in rows} == {int(k): v for k, v in runtime.GPU_UUIDS.items()},
            "all eight physical GPU identities must match recovery authorization")
    protocol_body = copy.deepcopy({k: v for k, v in old_protocol.items() if k != "id"})
    protocol_body.update(schema=SCHEMA, at=runtime.now(), output_root=str(root),
        authorization="用户明确同意独立recovery_01，两个旧UNKNOWN各一次，原实验剂量及四并发不变",
        source_commit=implementation["source_commit"], implementation=entry(root / "implementation/record.json"),
        parents={str(seed): str(root / f"parents/seed{seed}/record.json") for seed in base.SEEDS},
        resource_policy=runtime.resource_policy(), initial_resource_inventory=rows,
        inherited_experiment=evidence["references"], recovery_contract=recovery_contract(),
        feedback_recovery=authorization, inherited_resource_wait_seconds=evidence["inherited_resource_wait_seconds"],
        historical_worker_wait_observations_preserved=True,
        worker_wait_overlaps_not_added_to_controller_wallclock=True)
    require(protocol_body["evaluation"] == evaluation.evaluation_contract(), "evaluation dose changed during recovery")
    protocol = publish(root / "protocol/record.json", protocol_body)
    parent_records, branches = {}, {}
    for seed in base.SEEDS:
        old_ref = old_prepared["parents"][str(seed)]
        body = inherited_parent_body(evidence["parents"][str(seed)], protocol["id"],
            old_ref, evidence["references"]["prepared"])
        publish(root / f"parents/seed{seed}/record.json", body)
        parent_records[str(seed)] = entry(root / f"parents/seed{seed}/record.json")
        training_api.publish_c1_reuse(root, seed, protocol["id"])
        branches[f"seed{seed}/C1"] = entry(root / f"branches/seed{seed}/C1/completed/record.json")
    minimum_disk = old_prepared["disk_minimum_admission_bytes"]
    free_disk = shutil.disk_usage(root).free
    require(free_disk >= minimum_disk, "insufficient disk for unchanged recovery gradients/checkpoints")
    require(not rt.torch.cuda.is_initialized(), "recovery registration must remain CPU-only")
    return publish(root / "prepared/record.json", dict(schema=PREPARED_SCHEMA, at=runtime.now(),
        protocol=entry(root / "protocol/record.json"), original_prepared=evidence["references"]["prepared"],
        parents=parent_records, c1_branches=branches,
        actual_new_optimizer_budget=1788, logical_optimizer_updates=2682, reused_C1_logical_updates=894,
        new_feedback_sessions=2100, reused_feedback_sessions=2100, new_evaluation_sessions=12267,
        total_new_sessions=14367, new_class_task_count=1488,
        inherited_resource_wait_seconds=evidence["inherited_resource_wait_seconds"],
        original_parent_mathematical_audit_reexecuted=False, original_class_task_plan_reused=True,
        old_failed_episodes_not_promoted_to_complete=True, old_unknown_requests_authorized_once_each=2,
        disk_free_bytes=free_disk, disk_minimum_admission_bytes=minimum_disk,
        cpu_preparation_only=True, CUDA_initialized=False, scientific_controller_started=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    result = prepare(args.root, source_commit=args.source_commit)
    print(json.dumps(dict(root=str(args.root), prepared_id=result["id"],
                         actual_new_optimizer_budget=result["actual_new_optimizer_budget"])))


if __name__ == "__main__":
    main()
