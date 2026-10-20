"""Two new fixed-q branches per unchanged real parent; no historical retraining."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import finqa_v63_binding as binding
binding.install_scientific_paths()
import finqa_v54_training as original

REPO, V18, ROOT, OLD_ROOT = binding.REPO, binding.V18, binding.ROOT, binding.OLD_ROOT
SEEDS, ARMS, BATCH = binding.SEEDS, binding.ARMS, binding.BATCH
PARENT_STEP, SNAPSHOT_STEPS, END_STEP = 596, (745, 894), 894
require, digest, sha, file_ref, checked, publish = (
    binding.require, binding.digest, binding.sha, binding.file_ref,
    binding.checked, binding.publish)
records, task_cache = original.records, original.task_cache
runtime = original.runtime
checkpoint_ref, read_checkpoint = original.checkpoint_ref, original.read_checkpoint
validate_parent_state, read_outer_inputs = original.validate_parent_state, original.read_outer_inputs
validate_distribution = original.validate_distribution
configure_fixed_window = original.configure_fixed_window
latest_branch_checkpoint = original.latest_branch_checkpoint


def prepare_parent(root, seed, protocol_id):
    require(Path(root).resolve() == ROOT and seed in SEEDS, "unregistered new parent")
    path = OLD_ROOT / f"parents/seed{seed}/record.json"
    parent = checked(path)
    require(parent["protocol_id"] == binding.OLD_PROTOCOL_ID
            and parent["seed"] == seed and parent["c1_reuse"]["eligible"] is True,
            "the already accepted old parent/reuse proof is required")
    for arm in ("Hold", "C1", "C05"):
        completed = checked(OLD_ROOT / f"branches/seed{seed}/{arm}/completed/record.json")
        require(completed["status"] == "COMPLETE"
                and completed["parent_state_digest"] == parent["parent_state_digest"],
                "all nine prior branches must be complete at the same real parents")
    body = copy.deepcopy({k: v for k, v in parent.items() if k != "id"})
    body.update(schema="v63_inherited_complete_parent.v1", protocol_id=protocol_id,
        original_parent=binding.entry(path), feedback_batch=BATCH,
        new_class_task_count=0, all_original_class_tasks_read_only=True,
        original_parent_validation_reused=True, new_C1_branch_is_not_old_C1_reuse=True)
    return publish(Path(root) / f"parents/seed{seed}/record.json", body)


def checked_parent(root, seed):
    require(Path(root).resolve() == ROOT and seed in SEEDS, "foreign parent root or seed")
    parent = checked(Path(root) / f"parents/seed{seed}/record.json")
    old = binding.read_ref(parent["original_parent"])
    require(parent["schema"] == "v63_inherited_complete_parent.v1"
            and parent["seed"] == old["seed"] == seed
            and parent["feedback_batch"] == BATCH
            and parent["new_class_task_count"] == 0,
            "new experiment parent identity changed")
    for key in ("parent_checkpoint", "parent_state_digest", "old_outer_checkpoint",
                "old_outer_inputs", "old_outer_inputs_digest", "parameter_spec",
                "pool_id", "task_plan", "mu", "point_id", "component_digests",
                "parent_pi", "old_class_context", "scientific_sources"):
        require(parent[key] == old[key], "inherited parent field changed: " + key)
    return parent


def load_parent(root, seed, rt):
    parent = checked_parent(root, seed)
    state = read_checkpoint(parent["parent_checkpoint"], rt)
    validate_parent_state(state, seed=seed, rt=rt)
    path = Path(parent["old_outer_checkpoint"]["path"]) / "record.json"
    require(sha(path) == parent["old_outer_checkpoint"]["record_sha256"],
            "old outer metadata changed")
    outer = read_outer_inputs(parent["old_outer_inputs"], json.loads(path.read_bytes()), rt)
    require(rt.v8._tree_digest(outer["pre_state"]) == parent["parent_state_digest"],
            "actual virtual-point input belongs to another real parent")
    return parent, state, outer


def branch_root(root, seed, arm):
    require(Path(root).resolve() == ROOT and seed in SEEDS and arm in ARMS,
            "only the six new batch-one branches may be written")
    return Path(root) / f"branches/seed{seed}/{arm}"


def checked_branch_result(root, seed, arm):
    result = checked(branch_root(root, seed, arm) / "completed/record.json")
    require(result["schema"] == "v63_fixed_q_branch_complete.v1"
            and result["status"] == "COMPLETE"
            and (result["seed"], result["arm"], result["feedback_batch"]) == (seed, arm, BATCH)
            and result["temperature"] == binding.TEMPERATURES[arm]
            and result["optimizer_updates"] == result["new_optimizer_updates"] == 298
            and set(result["snapshots"]) == {"745", "894"}
            and result["next_outer894_executed"] is False,
            "branch is not a new complete batch-one fixed-q training window")
    for step, reference in result["snapshots"].items():
        require(reference["step"] == int(step) and reference["phase"] == "step"
                and sha(Path(reference["path"]) / "record.json") == reference["record_sha256"],
                "actual new branch checkpoint metadata changed")
    return result


def execute_training(root, seed, arm, protocol_id, driver, q, *, rt, monitor,
                     distribution_source, resource_report=None):
    """The original 298 actual step calls and checkpoint order, for either T."""
    parent = checked_parent(root, seed)
    validate_distribution(q, parent["parent_pi"])
    directory = branch_root(root, seed, arm)
    require(driver.root.resolve() == (directory / "training").resolve(),
            "new branch cannot write a historical training directory")
    require(not (directory / "completed/record.json").exists(),
            "completed new branch cannot retrain")
    contract = dict(schema="v63_fixed_q_training_binding.v1", protocol_id=protocol_id,
        seed=seed, arm=arm, feedback_batch=BATCH, temperature=binding.TEMPERATURES[arm],
        parent_id=parent["id"], parent_state_digest=parent["parent_state_digest"],
        training_rng_digest=parent["component_digests"]["rng"],
        distribution_digest=rt.v8._tree_digest(q), distribution_source=distribution_source,
        real_parent_not_theta_bar=True, frozen_step_source=parent["scientific_sources"]["driver"],
        start_step=596, end_step=894, snapshots=[745, 894],
        outer_schedule_during_window=[], dropout=0.05)
    path = directory / "binding/record.json"
    if path.exists():
        require(checked(path) == {**contract, "id": digest(contract)},
                "cold branch restore differs in parent, batch or q")
    else:
        publish(path, contract)
    committed = latest_branch_checkpoint(driver.root)
    configure_fixed_window(driver)
    if committed is None:
        driver.restore(parent["parent_checkpoint"]["path"])
        require(rt.v8._tree_digest(driver._payload()) == parent["parent_state_digest"],
                "new branch real parent did not restore exactly")
        driver.pi = copy.deepcopy(q)
        driver.commit("branch", {**contract, "logical_branch": arm,
                                 "actual_optimizer_updates": 0, "outer_commit": False})
    else:
        driver.restore(committed)
        require(driver.pi == q and driver.outer_done == [298]
                and 596 <= driver.step_index <= 894, "cold branch checkpoint differs")
    started_step = driver.step_index
    while driver.step_index < END_STEP:
        monitor.check_stop("before_real_sft_update", step=driver.step_index + 1)
        report = driver.step()
        require(driver.pi == q and driver.outer_done == [298]
                and report["optimizer_step_calls"] == report["clip_calls"] == 1,
                "fixed distribution or actual update count changed")
        monitor.clear_unused("sft_committed_step%04d" % driver.step_index)
    snapshots = {str(step): checkpoint_ref(driver.root / f"step{step:04d}_step")
                 for step in SNAPSHOT_STEPS}
    return publish(directory / "completed/record.json", dict(
        schema="v63_fixed_q_branch_complete.v1", status="COMPLETE", protocol_id=protocol_id,
        seed=seed, arm=arm, feedback_batch=BATCH, temperature=binding.TEMPERATURES[arm],
        logical_optimizer_updates=298, optimizer_updates=298, new_optimizer_updates=298,
        start_step=596, end_step=894, parent_state_digest=parent["parent_state_digest"],
        distribution_digest=contract["distribution_digest"], snapshots=snapshots,
        training_binding=binding.entry(path), next_outer894_executed=False,
        real_training_dropout=0.05, resources=resource_report() if resource_report else None,
        updates_in_final_worker=END_STEP - started_step))
