"""Same-parent fixed-distribution FinQA branches, using the frozen SFT step.

The original C-only step596 *step* checkpoint is the sole real training
starting point. The virtual point is only an input to feedback. Historical
C1 paths are reused only after a bounded provenance and actual-state audit.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.util
import io
import json
import math
import re
import sys
from fractions import Fraction
from pathlib import Path

import finqa_v37_task_cache as records
import finqa_v35_task_cache as task_cache

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
V18 = REPO / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01"
V25 = V18 / "v25_training_replication_01"
DEFAULT_TRAINING_ROOT = V25 / "training_replication"
SEEDS, ARMS = (137, 251, 389), ("Hold", "C1", "C05")
PARENT_STEP, SNAPSHOT_STEPS, END_STEP = 596, (745, 894), 894
require, digest, sha, file_ref, checked, publish = (
    records.require, records.digest, records.sha, records.file_ref,
    records.checked, records.publish,
)
_TRAINING = None


def frozen_training():
    global _TRAINING
    if _TRAINING is None:
        path = V25 / "implementation/finqa_v25_training_replication.py"
        spec = importlib.util.spec_from_file_location("_v54_original_v25_training", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _TRAINING = module
    return _TRAINING


def runtime():
    training = frozen_training()
    return training, training.load_runtime()


def checkpoint_ref(directory):
    directory = Path(directory).resolve()
    raw = (directory / "record.json").read_bytes()
    record = json.loads(raw)
    return dict(path=str(directory), record_sha256=hashlib.sha256(raw).hexdigest(),
                state_sha256=record["state_sha256"],
                actual_state_digest=record["actual_state_digest"],
                step=record["step"], phase=record["phase"])


def read_checkpoint(reference, rt):
    if isinstance(reference, (str, Path)):
        reference = checkpoint_ref(reference)
    directory = Path(reference["path"])
    require(sha(directory / "record.json") == reference["record_sha256"],
            "bound checkpoint record changed")
    state, native = records.read_checkpoint(directory, rt)
    require(native["actual_state_digest"] == reference["actual_state_digest"]
            and native["state"]["sha256"] == reference["state_sha256"],
            "bound checkpoint actual state changed")
    return state


def validate_parent_state(state, *, seed, rt):
    require(seed in SEEDS and (state["seed"], state["arm"], state["step"])
            == (seed, "C-only", 596) and state["outer_done"] == [298],
            "parent must be C-only step596 before the second outer")
    require(bool(state["optimizer"]["state"]) and state["model_training"] is True,
            "parent requires nonempty Adam and actual SFT training mode")
    require(state["rng"]["cuda"] is not None and bool(state["rng"]["cuda"]),
            "parent must retain actual CUDA training RNG")
    for value in state["optimizer"]["state"].values():
        require(int(value["step"].item()) == 596
                and set(value) >= {"step", "exp_avg", "exp_avg_sq"},
                "parent Adam moments/cursor are incomplete")
    require(len(state["pi"]) == len(state["prior"]) == 744
            and state["execution_plan"]["outer_steps"] == [298, 596, 894, 1192],
            "parent support or original schedule differs")
    return state


def read_outer_inputs(reference, record, rt):
    raw = Path(reference["path"]).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == reference["sha256"]
            == record["outer_inputs_sha256"], "old actual outer bytes changed")
    value = rt.torch.load(io.BytesIO(raw), map_location="cpu", weights_only=False)
    require(rt.v8._tree_digest(value) == record["outer_inputs_digest"]
            and value["schema"] == "v9_real_outer_inputs.v1"
            and value["actual_tensors_saved"] is True,
            "old outer payload is incomplete or changed")
    return value


def validate_old_outer(parent, post, outer, evidence, *, rt):
    require(rt.v8._tree_digest(outer["pre_state"]) == rt.v8._tree_digest(parent),
            "old T1 outer does not originate in the complete real parent")
    for key in records.COMPONENTS:
        if key not in ("pi", "outer_done"):
            require(rt.v8._tree_digest(parent[key]) == rt.v8._tree_digest(post[key]),
                    "old outer mutated real training component: " + key)
    require(post["pi"] == outer["q_next"] == evidence["distribution"]["pi_next"]
            and post["outer_done"] == [298, 596]
            and outer["C"] == evidence["C"], "old C1 q/C/history binding differs")
    distribution = evidence["distribution"]
    require(distribution.get("contribution_only") is True
            and distribution.get("effective_novelty_exponent") == 0,
            "old update is not the original C-only N=0 update")
    require(outer["feedback_seal"]["denominator"] == 700
            and len(outer["rewards"]) == 700
            and all(type(v) in (int, float) and v in (0, 1) for v in outer["rewards"])
            and outer["feedback_report"]["denominator"] == 700,
            "complete fixed700 old feedback required")
    for key, bound in (("G", "population_gradient_digest"),
                       ("theta_bar", "actual_virtual_theta_digest"),
                       ("gJ", "feedback_gradient_digest"), ("pullback", "pullback_digest")):
        require(rt.v8.parameter_digest(outer[key]) == evidence[bound],
                "old actual outer tensor differs: " + key)


def audit_c1_path(training_directory, parent, post, outer, *, rt):
    """One metadata pass, plus actual 745/894 states, not repeated tensor scans.

    The frozen step method performs exactly one registered batch and never
    changes pi. The sole next outer is 894 and is excluded from this path.
    All 298 actual update receipts and the unchanged initial training RNG are
    bound; endpoint state tensors independently confirm q and Adam cursors.
    """
    directory = Path(training_directory)
    fixed = ("seed", "arm", "pool_id", "prior", "schedule", "execution_plan",
             "adapter_binding", "frozen_base_digest")
    ledger = []
    for step in range(597, 895):
        path = directory / f"step{step:04d}_step/record.json"
        raw = path.read_bytes()
        row = json.loads(raw)
        report = row["evidence"]
        expected_batch = parent["schedule"]["batches"][step - 1]
        require((row["step"], row["phase"], row["arm"], row["seed"])
                == (step, "step", "C-only", parent["seed"])
                and row["pool_id"] == parent["pool_id"]
                and row["schedule_sha256"] == parent["schedule"]["schedule_sha256"],
                "old C1 receipt coordinate differs")
        require(report["actual_parameter_update"] is True
                and report["CPU_control_only"] is False
                and report["optimizer_step_calls"] == report["clip_calls"] == 1
                and report["execution_design"] == "original_unfused_response_rows_v18"
                and report["supervision_policy"] == "v14_state_independent_original_span_union.v1"
                and report["additional_batch_division"] is False
                and report["additional_loss_scaling"] is False
                and report["task_batch"]["task_ids"] == expected_batch["task_ids"]
                and report["task_batch"]["step"] == step
                and report["task_batch"]["schedule_id"] == row["schedule_sha256"],
                "old C1 real update/loss/schedule receipt differs")
        require((path.parent / "state.pt").is_file(), "old C1 actual step state missing")
        ledger.append(dict(step=step, record=file_ref(path),
                           state_sha256=row["state_sha256"],
                           actual_state_digest=row["actual_state_digest"],
                           update_id=report["id"]))
    require(not any(directory.glob("step0[6-8][0-9][0-9]_outer"))
            or all(int(p.name[4:8]) == 894
                   for p in directory.glob("step0[6-8][0-9][0-9]_outer")),
            "unexpected intervening outer in old fixed-q path")
    snapshots = {}
    for step in SNAPSHOT_STEPS:
        reference = checkpoint_ref(directory / f"step{step:04d}_step")
        state = read_checkpoint(reference, rt)
        require(state["step"] == step and state["outer_done"] == [298, 596]
                and state["pi"] == outer["q_next"] and state["model_training"] is True,
                "old snapshot is not the fixed-q pre-outer endpoint")
        for key in fixed:
            require(rt.v8._tree_digest(state[key]) == rt.v8._tree_digest(parent[key]),
                    "old snapshot scientific binding differs: " + key)
        require(all(int(v["step"].item()) == step for v in state["optimizer"]["state"].values()),
                "old snapshot Adam cursor differs")
        snapshots[str(step)] = reference
    return dict(eligible=True, logical_optimizer_updates=298, new_optimizer_updates=0,
                initial_training_rng_digest=rt.v8._tree_digest(parent["rng"]),
                initial_post_outer_rng_digest=rt.v8._tree_digest(post["rng"]),
                q_digest=rt.v8._tree_digest(outer["q_next"]),
                update_receipts=ledger, snapshots=snapshots,
                audit_mode="all298_update_receipts_plus_actual_parent_outer_745_894_states",
                intermediate_tensor_bytes_rehashed=False,
                original_frozen_step_source=file_ref(rt.v8.__file__),
                inherited_step_function=True, next_outer894_excluded=True)


def prepare_parent(root, seed, training_root=DEFAULT_TRAINING_ROOT, protocol_id=None,
                   *, loaded=None):
    """CPU-only parent registration and C1 reuse proof, called once per seed."""
    require(seed in SEEDS, "unregistered parent seed")
    root, training_root = Path(root).resolve(), Path(training_root).resolve()
    training, rt = runtime()
    science, pool, _prefix, assets = loaded or training.checked_launch(training_root)
    base = training_root / f"seed{seed}/arms/c_only/training"
    parent_ref, outer_ref = checkpoint_ref(base / "step0596_step"), checkpoint_ref(base / "step0596_outer")
    parent = validate_parent_state(read_checkpoint(parent_ref, rt), seed=seed, rt=rt)
    post = read_checkpoint(outer_ref, rt)
    require(parent["pool_id"] == pool.cache_id
            and parent["schedule"] == training.build_task_schedule(pool.task_ids, seed)
            and parent["prior"] == pool._manifest.registration.pi0,
            "parent material/schedule/prior binding differs")
    outer_record = json.loads((base / "step0596_outer/record.json").read_bytes())
    inputs_ref = file_ref(base / "step0596_outer/outer_inputs.pt")
    outer = read_outer_inputs(inputs_ref, outer_record, rt)
    validate_old_outer(parent, post, outer, outer_record["evidence"], rt=rt)
    guard = importlib.import_module("finqa_v32_same_point_guard")
    require(guard.recompute_point_id(parent, theta_bar=outer["theta_bar"],
                                    G=outer["G"], frozen_runtime=rt) == outer["point_id"],
            "old G/theta_bar does not match the complete parent point identity")
    feedback_root = base.parent / "feedback" / rt.v8.digest(outer["point_id"])
    intent = json.loads((feedback_root / "intent/record.json").read_bytes())
    cohort, rewards, feedback_bindings = guard._load_sealed(feedback_root, intent, rt)
    require(cohort.model_dump(mode="json", exclude={"episodes"}) == outer["feedback_seal"]
            and rewards == outer["rewards"]
            and cohort.identity.parameter_digest == rt.v8.parameter_digest(outer["theta_bar"])
            and all(ep.config.temperature == 1.0 for ep in cohort.episodes),
            "old C1 gJ/C/q do not bind the original complete T1 cohort")
    spec = [dict(name=k, shape=list(v.shape), dtype=str(v.dtype))
            for k, v in parent["parameters"].items()]
    task_plan = task_cache.make_task_plan(pool, spec, shards=4)
    directory = root / f"parents/seed{seed}"
    task_plan_path = directory / "task_plan/record.json"
    old_context = None
    if seed == 389:
        source = training_root.parent / "production_resume_01/recovery_02/contexts/seed389/c_only/step0596_outer/context/record.json"
        candidate = checked(source)
        require(candidate["pre_state_digest"] == parent_ref["actual_state_digest"]
                and candidate["task_plan"]["id"] == task_plan["id"]
                and candidate["parameter_spec"] == spec
                and candidate["pool_id"] == pool.cache_id,
                "old class cache is not the same complete parent and task plan")
        require(all((Path(candidate["task_cache_root"]) / f"task{i:04d}/gradient.pt").is_file()
                    for i in range(744)), "same-point inherited class cache incomplete")
        old_context = records.entry(source)
    c1 = audit_c1_path(base, parent, post, outer, rt=rt)
    publish(task_plan_path, {k: v for k, v in task_plan.items() if k != "id"})
    body = dict(schema="v54_actual_parent.v1", protocol_id=protocol_id, seed=seed,
                parent_checkpoint=parent_ref, parent_state_digest=parent_ref["actual_state_digest"],
                old_outer_checkpoint=outer_ref, old_outer_inputs=inputs_ref,
                old_outer_inputs_digest=outer_record["outer_inputs_digest"],
                training_root=str(training_root), training_protocol_id=science["id"],
                training_protocol=file_ref(training_root / "registration/record.json"),
                pool_id=pool.cache_id, task_plan=records.entry(task_plan_path),
                parameter_spec=spec, mu=copy.deepcopy(outer["mu"]),
                point_id=outer["point_id"],
                component_digests={k: rt.v8._tree_digest(parent[k]) for k in records.COMPONENTS},
                original_T1_feedback_seal=outer["feedback_seal"],
                original_T1_feedback_root=str(feedback_root),
                original_T1_feedback_bindings=feedback_bindings,
                original_T1_receipts_verified=True, original_T1_new_generation=0,
                original_T1_q=outer["q_next"], parent_pi=parent["pi"],
                old_class_context=old_context, new_class_task_count=0 if old_context else 744,
                c1_reuse=c1, scientific_sources=dict(training=file_ref(training.__file__),
                    driver=file_ref(rt.v8.__file__), material=file_ref(rt.material.__file__)),
                real_parent_is_virtual_point=False, original_files_written=False)
    return publish(directory / "record.json", body)


def checked_parent(root, seed):
    parent = checked(Path(root) / f"parents/seed{seed}/record.json")
    require(parent["schema"] == "v54_actual_parent.v1" and parent["seed"] == seed,
            "parent registration mismatch")
    return parent


def load_parent(root, seed, rt):
    parent = checked_parent(root, seed)
    state = read_checkpoint(parent["parent_checkpoint"], rt)
    validate_parent_state(state, seed=seed, rt=rt)
    old_record = json.loads((Path(parent["old_outer_checkpoint"]["path"]) / "record.json").read_bytes())
    require(sha(Path(parent["old_outer_checkpoint"]["path"]) / "record.json")
            == parent["old_outer_checkpoint"]["record_sha256"], "old outer record changed")
    outer = read_outer_inputs(parent["old_outer_inputs"], old_record, rt)
    require(rt.v8._tree_digest(outer["pre_state"]) == parent["parent_state_digest"],
            "old virtual point no longer binds the actual parent")
    return parent, state, outer


def branch_root(root, seed, arm):
    require(seed in SEEDS and arm in ARMS, "unregistered branch")
    return Path(root) / f"branches/seed{seed}/{arm}"


def _result_body(root, seed, arm, protocol_id, *, snapshots, q_digest,
                 new_updates, binding, resources=None):
    parent = checked_parent(root, seed)
    return dict(schema="v54_fixed_q_branch_complete.v1", status="COMPLETE",
                protocol_id=protocol_id, seed=seed, arm=arm, logical_optimizer_updates=298,
                optimizer_updates=298, new_optimizer_updates=new_updates,
                start_step=596, end_step=894, parent_state_digest=parent["parent_state_digest"],
                distribution_digest=q_digest, snapshots=snapshots,
                training_binding=binding, next_outer894_executed=False,
                real_training_dropout=0.05, resources=resources)


def publish_c1_reuse(root, seed, protocol_id):
    parent = checked_parent(root, seed)
    proof = parent["c1_reuse"]
    require(proof["eligible"] is True, "C1 path did not pass same-parent audit")
    body = _result_body(root, seed, "C1", protocol_id,
                        snapshots=proof["snapshots"], q_digest=proof["q_digest"], new_updates=0,
                        binding=dict(parent_id=parent["id"], c1_proof_digest=digest(proof),
                                     source="read_only_original_path"))
    return publish(branch_root(root, seed, "C1") / "completed/record.json", body)


def checked_branch_result(root, seed, arm):
    result = checked(branch_root(root, seed, arm) / "completed/record.json")
    require(result["schema"] == "v54_fixed_q_branch_complete.v1"
            and result["status"] == "COMPLETE" and result["seed"] == seed
            and result["arm"] == arm and result["optimizer_updates"] == 298
            and set(result["snapshots"]) == {"745", "894"}
            and result["next_outer894_executed"] is False,
            "branch is not the prescribed full fixed-q learning window")
    for step, ref in result["snapshots"].items():
        require(ref["step"] == int(step) and ref["phase"] == "step"
                and sha(Path(ref["path"]) / "record.json") == ref["record_sha256"],
                "actual branch snapshot record changed")
    return result


def validate_distribution(q, parent_pi):
    require(set(q) == set(parent_pi), "fixed-q task support differs")
    for task, values in q.items():
        probabilities = [float(Fraction(str(value))) for value in values.values()]
        require(set(values) == set(parent_pi[task])
                and all(math.isfinite(value) and value > 0 for value in probabilities)
                and abs(sum(probabilities) - 1) < 1e-9,
                "fixed-q state support/probability changed")


def configure_fixed_window(driver):
    """Change only orchestration gates; frozen step/loss/optimizer stay inherited."""
    require(driver.arm == "C-only", "the original C-only SFT implementation is required")
    driver.outer_steps = ()
    driver.final_step = END_STEP


def latest_branch_checkpoint(directory):
    candidates = []
    for path in Path(directory).glob("step*_*"):
        match = re.fullmatch(r"step(\d{4})_(branch|step)", path.name)
        require(match is not None, "fixed-q branch has an unexpected outer checkpoint")
        step = int(match[1])
        require((step == 596 and match[2] == "branch") or (597 <= step <= 894 and match[2] == "step"),
                "fixed-q checkpoint escaped its authorized interval")
        require((path / "record.json").is_file() and (path / "state.pt").is_file(),
                "partial training checkpoint cannot resume")
        candidates.append((step, path))
    return max(candidates)[1] if candidates else None


def execute_training(root, seed, arm, protocol_id, driver, q, *, rt, monitor,
                     distribution_source, resource_report=None):
    """298 actual frozen optimizer calls with a durable checkpoint after each."""
    require(arm in ("Hold", "C05", "C1"), "unregistered fixed distribution arm")
    parent = checked_parent(root, seed)
    validate_distribution(q, parent["parent_pi"])
    if arm == "Hold":
        require(q == parent["parent_pi"], "Hold must preserve the current parent pi")
    directory = branch_root(root, seed, arm)
    require(driver.root.resolve() == (directory / "training").resolve(),
            "new branch cannot write the historical trainer directory")
    require(not (directory / "completed/record.json").exists(), "completed branch cannot retrain")
    binding = dict(schema="v54_fixed_q_training_binding.v1", protocol_id=protocol_id,
                   seed=seed, arm=arm, parent_id=parent["id"],
                   parent_state_digest=parent["parent_state_digest"],
                   training_rng_digest=parent["component_digests"]["rng"],
                   distribution_digest=rt.v8._tree_digest(q),
                   distribution_source=distribution_source, real_parent_not_theta_bar=True,
                   frozen_step_source=parent["scientific_sources"]["driver"],
                   start_step=596, end_step=894, snapshots=[745, 894],
                   outer_schedule_during_window=[], dropout=0.05)
    binding_path = directory / "binding/record.json"
    if binding_path.exists():
        require(checked(binding_path) == {**binding, "id": digest(binding)},
                "cold branch restore has a different parent/q/scientific source")
    else:
        publish(binding_path, binding)
    committed = latest_branch_checkpoint(driver.root)
    configure_fixed_window(driver)
    if committed is None:
        driver.restore(parent["parent_checkpoint"]["path"])
        require(rt.v8._tree_digest(driver._payload()) == parent["parent_state_digest"],
                "real training parent did not restore exactly")
        driver.pi = copy.deepcopy(q)
        driver.commit("branch", {**binding, "logical_branch": arm,
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
                "fixed distribution or real update count changed")
        monitor.clear_unused("sft_committed_step%04d" % driver.step_index)
    snapshots = {str(step): checkpoint_ref(driver.root / f"step{step:04d}_step")
                 for step in SNAPSHOT_STEPS}
    body = _result_body(root, seed, arm, protocol_id, snapshots=snapshots,
                        q_digest=binding["distribution_digest"], new_updates=298,
                        binding=records.entry(binding_path),
                        resources=resource_report() if resource_report else None)
    body["updates_in_final_worker"] = END_STEP - started_step
    return publish(directory / "completed/record.json", body)
