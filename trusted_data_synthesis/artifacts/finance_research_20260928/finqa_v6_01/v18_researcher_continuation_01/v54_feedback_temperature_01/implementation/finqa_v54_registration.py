"""Prospective immutable registration of the bounded T1 versus T0.5 experiment."""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import finqa_v54_runtime as runtime

REPO, V18, ROOT = runtime.REPO, runtime.V18, runtime.ROOT
V25 = V18 / "v25_training_replication_01"
TRAINING_ROOT = V25 / "training_replication"
FROZEN_SOURCE = REPO / ".codex-worktrees/finqa-v18-researcher-continuation-20260930/trusted_data_synthesis/src"
SOURCE_BUNDLE = V25 / "production_resume_01/host_memory_admission_01/implementation"
SOURCE_BUNDLE_ID = "c32c3a60ec4b3fa5c943bfa740cf53bdf985d7da7587f664c068ea8058857a6d"
USER_PLAN = Path("/home/zhuxinrui/.codex/attachments/a254510e-9640-4f99-bfc0-cf0f4d0645ef/已粘贴的文本.txt")
FILES = tuple("finqa_v54_" + name + ".py" for name in (
    "registration", "runtime", "controller", "training", "worker", "temperature", "evaluation", "statistics"))
SEEDS, ARMS = (137, 251, 389), ("Hold", "C1", "C05")
SCHEMA = "v54_temperature_fixed_parent_protocol.v1"
require, checked, publish, entry, file_ref, sha = (
    runtime.require, runtime.checked, runtime.publish, runtime.entry, runtime.file_ref, runtime.sha,
)


def scientific_contract():
    return dict(
        parent_training_seeds=list(SEEDS), parent_arm="C-only", parent_step=596,
        parent_phase="step", parent_outer_done=[298], real_training_start_is_theta_bar=False,
        arms=list(ARMS), intervention="feedback_policy_temperature_0.5_only",
        feedback_temperatures=dict(C1=1.0, C05=0.5),
        Hold_distribution="actual_parent_pi_not_historical_Static_prior",
        C1_feedback="read_only_original_sealed_700_per_parent",
        C05_feedback="new_independent_condition_700_per_parent",
        feedback_task_count=350, feedback_draw_seeds=[11, 29], feedback_denominator=700,
        feedback_task_roster_and_original_reward_unchanged=True,
        zero_rewards_remain_in_denominator=True,
        probability="softmax(raw_logits/T), full generated tokens including actual EOS",
        replay_derivative="derivative of log_softmax(raw_logits/T), including normalization and 1/T",
        SFT_mask_in_feedback_gradient=False, trajectory_length_normalized=False,
        old_gJ_rescaled_as_new_temperature=False,
        separate_feedback_condition_identity=True,
        fixed_training_update_interval=[597, 894], logical_updates_per_branch=298,
        snapshots=[745, 894], primary_endpoint=894, outer_at_894_allowed=False,
        fixed_q_through_894=True, contribution_exponent=0.8, novelty_exponent=0.0,
        original_RMS_floor_sigmoid_KL_anchors_unchanged=True,
        class_eval_and_SFT_dropout_005_unchanged=True,
        materials=dict(tasks=744, states=1360, packages=2468, effective_rows=4974),
        logical_training_branches=9, logical_optimizer_updates=2682,
        actual_optimizer_budget_ceiling=2682,
        C1_reuse_requires_complete_parent_q_rng_schedule_loss_optimizer_and_snapshot_proof=True,
        actual_optimizer_budget_if_three_C1_reused=1788,
        new_feedback_sessions=2100, old_feedback_sessions_reused=2100,
        new_calibration_evaluation_sessions=4320, new_development_evaluation_sessions=7947,
        total_new_sessions=14367, new_test1147_sessions=0,
        new_QA_or_probe_material=0, external_API_budget=0, api_model="deepseek-flash",
        generation_provider="local_frozen_Student",
        all_training_then_evaluation_generation=True,
        each_complete_panel_before_private_scoring=True,
        primary="C05-C1 on complete dev883 greedy native execution accuracy",
        key_secondary="C05-Hold on complete dev883 greedy native execution accuracy",
        also_report="C1-Hold", independent_parent_count=3,
        IWR_transition_decomposition_required=True, UNKNOWN_never_zero=True,
        advancement="both exact mean differences strictly positive and all contracts complete",
        exact_zero_retains_baseline=True, advancement_is_not_significance_or_stability=True,
        complete_closed_loop_followup_automatically_started=False,
        historical_diagnostics=dict(
            nine_B_models_all_available_original_records=True,
            parser_first_rejection_exclusive_categories=True,
            qualitative_per_model_cap=10, qualitative_total_cap=90,
            qualitative_selection="presealed categories and digest order",
            old_outers=24, new_old_draw_backward_passes=0,
            unavailable_optional_payload="report unavailable, do not regenerate",
            old_native_scores_rewritten=False,
            supervised_coefficient_mass_is_not_actual_loss_or_gradient=True),
    )


def import_science():
    # The original V25 loader rejects a workspace package already imported.
    import finqa_v54_training as training_api
    training, rt = training_api.runtime()
    evaluation = importlib.import_module("finqa_v54_evaluation")
    temperature = importlib.import_module("finqa_v54_temperature")
    evaluation._runtime()
    require(not rt.torch.cuda.is_initialized(), "registration must remain CPU-only")
    return training_api, training, rt, evaluation, temperature


def dependency_sources():
    training_api, training, _rt, evaluation, _temperature = import_science()
    # Complete the public-only runtime imports before collecting dependencies.
    source = V18 / "final_evaluation/registration/record.json"
    evaluation._public_source(dict(evaluation_source_registration=file_ref(source)), evaluation._runtime())
    original = checked(SOURCE_BUNDLE / "record.json")
    require(original["id"] == SOURCE_BUNDLE_ID and len(original["sha256"]) == 81,
            "original dependency source bundle changed")
    result = {}
    for name, module in sorted(sys.modules.items()):
        raw = getattr(module, "__file__", None)
        if not raw:
            continue
        path = Path(raw).resolve()
        if name == "trusted_synthesis" or name.startswith("trusted_synthesis."):
            require(path.is_relative_to(FROZEN_SOURCE), "non-frozen science package in registration")
            if path.is_file():
                result[str(path)] = sha(path)
        elif path.name.startswith("finqa_") and path.suffix == ".py" and path.is_file():
            if path.name in original["sha256"]:
                require(sha(path) == original["sha256"][path.name],
                        "preparation imported a different original helper: " + str(path))
            elif path.name not in FILES:
                result[str(path)] = sha(path)
    for path in (Path(training.__file__), V25 / "implementation/record.json"):
        result[str(path.resolve())] = sha(path)
    return result


def freeze(root, source_commit):
    root = Path(root).resolve()
    require(root == ROOT and not root.exists(), "V54 requires one fresh independent registered root")
    commit = subprocess.check_output(["git", "rev-parse", source_commit + "^{commit}"], cwd=REPO, text=True).strip()
    original = checked(SOURCE_BUNDLE / "record.json")
    require(original["id"] == SOURCE_BUNDLE_ID and len(original["sha256"]) == 81,
            "original scientific implementation bundle changed")
    sources = {}
    for name, expected in original["sha256"].items():
        raw = (SOURCE_BUNDLE / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, "original scientific source changed: " + name)
        sources[name] = raw
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=REPO)
        require(hashlib.sha256(raw).hexdigest() == sha(REPO / relative), "uncommitted V54 source: " + name)
        sources[name] = raw
    dependencies = dependency_sources()
    require(len(sources) == 89, "81 original and eight new implementation files required")
    destination = root / "implementation"
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (destination / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    return publish(destination / "record.json", dict(
        schema="v54_frozen_temperature_execution_implementation.v1", at=runtime.now(),
        source_commit=commit, committed_files=list(FILES),
        original_implementation=entry(SOURCE_BUNDLE / "record.json"),
        sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        external_frozen_source_sha256=dependencies,
        frozen_source_root=str(FROZEN_SOURCE), original_files_modified=False,
        temperature_probability_implementation_is_new=True))


def checked_implementation(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "unregistered V54 root")
    value = checked(root / "implementation/record.json")
    require(value["schema"] == "v54_frozen_temperature_execution_implementation.v1"
            and value["committed_files"] == list(FILES) and len(value["sha256"]) == 89,
            "frozen V54 implementation contract differs")
    original = runtime.read_ref(value["original_implementation"])
    require(original["id"] == SOURCE_BUNDLE_ID
            and set(value["sha256"]) == set(original["sha256"]) | set(FILES)
            and all(value["sha256"][name] == expected for name, expected in original["sha256"].items()),
            "original 81 scientific files must remain byte-identical in the 89-file package")
    for name, expected in value["sha256"].items():
        require(sha(root / "implementation" / name) == expected, "frozen execution source changed: " + name)
    for path, expected in value["external_frozen_source_sha256"].items():
        require(sha(path) == expected, "original scientific package changed: " + path)
    return value


def checked_protocol(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "unregistered V54 protocol root")
    protocol = checked(root / "protocol/record.json")
    require(protocol["schema"] == SCHEMA and protocol["output_root"] == str(root)
            and protocol["scientific_contract"] == scientific_contract()
            and protocol["resource_policy"] == runtime.resource_policy()
            and protocol["allowed_gpu_indices"] == list(range(8))
            and protocol["gpu_uuids"] == runtime.GPU_UUIDS
            and protocol["max_gpu_workers"] == 4 and protocol["max_workers_per_gpu"] == 1
            and protocol["cpu_affinity"] == runtime.CPU_AFFINITY
            and protocol["gpu_lease_root"] == str(TRAINING_ROOT / "locks")
            and len(protocol["gpu_priority"]) == 8
            and set(protocol["gpu_priority"]) == set(range(8))
            and protocol["parents"] == {str(seed): str(root / f"parents/seed{seed}/record.json") for seed in SEEDS}
            and protocol["evaluation"] == importlib.import_module("finqa_v54_evaluation").evaluation_contract(),
            "V54 science, resource scope, or four-worker cap changed")
    implementation = runtime.read_ref(protocol["implementation"])
    require(protocol["implementation"]["path"] == str(root / "implementation/record.json")
            and protocol["implementation"]["id"] == implementation["id"],
            "protocol implementation identity differs")
    return protocol


def checked_prepared(root=ROOT):
    root = Path(root).resolve()
    protocol = checked_protocol(root)
    value = checked(root / "prepared/record.json")
    require(value["schema"] == "v54_three_parent_ready.v1"
            and value["protocol"]["id"] == protocol["id"]
            and value["protocol"]["path"] == str(root / "protocol/record.json")
            and runtime.read_ref(value["protocol"]) == protocol
            and set(value["parents"]) == {str(s) for s in SEEDS}
            and value["new_feedback_sessions"] == 2100
            and value["new_evaluation_sessions"] == 12267
            and value["total_new_sessions"] == 14367,
            "V54 actual parent preparation/budget differs")
    parents = {}
    for seed, reference in value["parents"].items():
        parent = runtime.read_ref(reference)
        parents[seed] = parent
        require(parent["schema"] == "v54_actual_parent.v1"
                and parent["protocol_id"] == protocol["id"] and parent["seed"] == int(seed)
                and reference["path"] == protocol["parents"][seed]
                and parent["parent_checkpoint"] == protocol["source_parent_checkpoints"][seed]["parent"]
                and parent["old_outer_checkpoint"] == protocol["source_parent_checkpoints"][seed]["old_outer"],
                "prepared parent ownership or registered source point differs")
    reused = {f"seed{seed}/C1" for seed, parent in parents.items() if parent["c1_reuse"]["eligible"]}
    require(set(value["c1_branches"]) == reused
            and value["actual_new_optimizer_budget"] == 2682 - 298 * len(reused)
            and value["reused_C1_logical_updates"] == 298 * len(reused)
            and value["logical_optimizer_updates"] == 2682,
            "C1 reuse membership and exact physical optimizer budget differ")
    for coordinate, reference in value["c1_branches"].items():
        branch = runtime.read_ref(reference)
        seed = coordinate.split("/")[0].removeprefix("seed")
        parent, proof = parents[seed], parents[seed]["c1_reuse"]
        require(reference["path"] == str(root / "branches" / f"seed{seed}" / "C1/completed/record.json")
                and branch["schema"] == "v54_fixed_q_branch_complete.v1"
                and branch["status"] == "COMPLETE" and branch["protocol_id"] == protocol["id"]
                and (branch["seed"], branch["arm"], branch["optimizer_updates"], branch["new_optimizer_updates"])
                    == (int(seed), "C1", 298, 0)
                and branch["parent_state_digest"] == parent["parent_state_digest"]
                and branch["distribution_digest"] == proof["q_digest"]
                and branch["snapshots"] == proof["snapshots"]
                and branch["training_binding"]["parent_id"] == parent["id"]
                and branch["training_binding"]["c1_proof_digest"] == runtime.digest(proof)
                and branch["next_outer894_executed"] is False,
                "read-only C1 reuse branch differs from the actual complete parent proof")
    return value


def prepare(root=ROOT, *, source_commit):
    root = Path(root).resolve()
    implementation = freeze(root, source_commit)
    training_api, training, rt, evaluation, _temperature = import_science()
    original_plan = USER_PLAN.read_bytes()
    archive = root / "user_plan/source.txt"
    archive.parent.mkdir(parents=True, exist_ok=False)
    with archive.open("xb") as stream:
        stream.write(original_plan)
        stream.flush()
        os.fsync(stream.fileno())
    user_plan = publish(root / "user_plan/record.json", dict(
        schema="v54_actual_user_supplied_plan.v1", at=runtime.now(),
        source_path=str(USER_PLAN), source_sha256=hashlib.sha256(original_plan).hexdigest(),
        archive=file_ref(archive), pasted_plan_read_in_full=True,
        separately_linked_sandbox_markdown_was_not_attached=True,
        request="参照方案修订并开展后续实验，本轮实验开放GPU使用限制，并发数暂设为4"))
    parent_sources = {str(seed): {
        phase: training_api.checkpoint_ref(TRAINING_ROOT / f"seed{seed}/arms/c_only/training" / name)
        for phase, name in (("parent", "step0596_step"), ("old_outer", "step0596_outer"),
                            ("snapshot745", "step0745_step"), ("snapshot894", "step0894_step"))
    } for seed in SEEDS}
    rows = runtime.inventory()
    require({row["index"]: row["uuid"] for row in rows} == {int(k): v for k, v in runtime.GPU_UUIDS.items()},
            "all eight physical device identities must match the new authorization")
    protocol = publish(root / "protocol/record.json", dict(
        schema=SCHEMA, at=runtime.now(), output_root=str(root),
        authorization="用户明确授权本轮固定低温验证，物理GPU0至7可选，总worker暂限4，每卡最多1",
        source_commit=implementation["source_commit"], implementation=entry(root / "implementation/record.json"),
        user_plan=entry(root / "user_plan/record.json"), scientific_contract=scientific_contract(),
        parents={str(seed): str(root / f"parents/seed{seed}/record.json") for seed in SEEDS},
        source_parent_checkpoints=parent_sources,
        evaluation=evaluation.evaluation_contract(),
        evaluation_source_registration=file_ref(V18 / "final_evaluation/registration/record.json"),
        training_source_registration=file_ref(TRAINING_ROOT / "registration/record.json"),
        resource_policy=runtime.resource_policy(), allowed_gpu_indices=list(range(8)),
        gpu_uuids=runtime.GPU_UUIDS, gpu_priority=[2, 1, 4, 6, 7, 0, 3, 5],
        cpu_affinity=runtime.CPU_AFFINITY, max_gpu_workers=4, max_workers_per_gpu=1,
        gpu_lease_root=str(TRAINING_ROOT / "locks"),
        cpu_initialization_and_draining_count_as_active_workers=True,
        initial_resource_inventory=rows,
        no_wallclock_deadlines=True, resource_wait_statistics_preserved=True,
        scientific_failure_stops_pool=True, automatic_scientific_retry=False,
        pre_scientific_resource_wait_only=True, manual_stop_is_terminal=True,
        unknown_partial_feedback_never_automatically_regenerated=True,
        explicit_cold_recovery_requires_actual_durable_state=True,
        stop_shared_grace_seconds=600, historical_experiments_not_restarted=True,
        CPU_diagnostics_do_not_authorize_extra_model_passes=True))
    loaded = training.checked_launch(TRAINING_ROOT)
    parent_records, c1_records = {}, {}
    for seed in SEEDS:
        parent = training_api.prepare_parent(root, seed, TRAINING_ROOT, protocol["id"], loaded=loaded)
        parent_records[str(seed)] = entry(root / f"parents/seed{seed}/record.json")
        if parent["c1_reuse"]["eligible"]:
            training_api.publish_c1_reuse(root, seed, protocol["id"])
            c1_records[f"seed{seed}/C1"] = entry(root / f"branches/seed{seed}/C1/completed/record.json")
        gc.collect()
    parameter_bytes = sum(
        int(rt.torch.empty((), dtype=getattr(rt.torch, x["dtype"].split(".")[-1])).element_size())
        * __import__("math").prod(x["shape"])
        for x in parent["parameter_spec"])
    new_class_states = sum(1360 for seed in SEEDS if checked(parent_records[str(seed)]["path"])["old_class_context"] is None)
    # Stage checkpoints also retain real parameter/Adam/RNG values at every update.
    minimum_disk = new_class_states * parameter_bytes * 2 + 96*runtime.GIB
    free_disk = shutil.disk_usage(root).free
    require(free_disk >= minimum_disk, "insufficient disk for the registered actual gradients and checkpoints")
    require(not rt.torch.cuda.is_initialized(), "CPU parent preparation initialized CUDA")
    return publish(root / "prepared/record.json", dict(
        schema="v54_three_parent_ready.v1", at=runtime.now(), protocol=entry(root / "protocol/record.json"),
        parents=parent_records, c1_branches=c1_records,
        actual_new_optimizer_budget=2682 - 298*len(c1_records),
        reused_C1_logical_updates=298*len(c1_records), logical_optimizer_updates=2682,
        new_feedback_sessions=2100, reused_feedback_sessions=2100,
        new_evaluation_sessions=12267, total_new_sessions=14367,
        new_class_task_count=sum(checked(p["path"])["new_class_task_count"] for p in parent_records.values()),
        preserved_parent_and_original_outputs=True,
        disk_free_bytes=free_disk, disk_minimum_admission_bytes=minimum_disk,
        cpu_preparation_only=True, CUDA_initialized=False,
        scientific_controller_started=False, user_plan_id=user_plan["id"]))


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
