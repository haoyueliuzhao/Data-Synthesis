"""Cold scientific stages for the bounded FinQA feedback-temperature experiment.

All writes belong to V54. Frozen V25 SFT and the existing class/Adam/C kernels
are consumed unchanged; T0.5 probability arithmetic is isolated in its own
module. The controller alone admits GPUs and accepts actual process exits.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import gc
import hashlib
import importlib
import io
import json
import os
import time
from pathlib import Path

import finqa_v54_training as training_api

STAGES = ("shard00", "shard01", "shard02", "shard03", "feedback_C05",
          "replay_C05", "distribution_C05", "train_Hold", "train_C1", "train_C05")
GIB = 1024 ** 3
require, digest, checked, publish = (training_api.require, training_api.digest,
                                   training_api.checked, training_api.publish)


def stage_root(root, seed, stage):
    require(seed in training_api.SEEDS and stage in STAGES, "unregistered scientific stage")
    return Path(root) / f"stages/seed{seed}/{stage}"


def job_spec(seed, stage):
    require(seed in training_api.SEEDS and stage in STAGES, "unregistered job")
    kind = ("class" if stage.startswith("shard") else "train" if stage.startswith("train_")
            else "feedback" if stage == "feedback_C05" else "replay"
            if stage == "replay_C05" else "distribution")
    return dict(id=f"seed{seed}.{stage}", seed=seed, stage=stage, kind=kind,
                arm=stage.removeprefix("train_") if kind == "train" else None)


def save_payload(directory, value, parent, stage, rt):
    from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

    stream = io.BytesIO()
    rt.torch.save(value, stream)
    raw = stream.getvalue()
    body = dict(schema="v54_actual_scientific_payload.v1", parent_id=parent["id"],
                parent_state_digest=parent["parent_state_digest"], stage=stage,
                state_sha256=hashlib.sha256(raw).hexdigest(), state_bytes=len(raw),
                state_digest=rt.v8._tree_digest(value), actual_tensors_saved=True)
    record = {**body, "id": digest(body)}
    write_immutable_artifact_directory(Path(directory) / "payload", {
        "state.pt": raw,
        "record.json": (json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2,
                                    allow_nan=False) + "\n").encode(),
    })
    return training_api.records.entry(Path(directory) / "payload/record.json")


def read_payload(directory, parent, stage, rt):
    base = Path(directory) / "payload"
    record = checked(base / "record.json")
    require(record["schema"] == "v54_actual_scientific_payload.v1"
            and record["parent_id"] == parent["id"]
            and record["parent_state_digest"] == parent["parent_state_digest"]
            and record["stage"] == stage and record["actual_tensors_saved"] is True,
            "stage payload belongs to a different parent or scientific operation")
    raw = (base / "state.pt").read_bytes()
    require(len(raw) == record["state_bytes"]
            and hashlib.sha256(raw).hexdigest() == record["state_sha256"],
            "actual scientific tensor bytes changed")
    value = rt.torch.load(io.BytesIO(raw), map_location="cpu", weights_only=False)
    require(rt.v8._tree_digest(value) == record["state_digest"],
            "scientific tensor semantic digest changed")
    return value


def _cpu(values):
    return {name: value.detach().cpu().clone() for name, value in values.items()}


def assert_live_parent(driver, parent, rt):
    require(rt.v8._tree_digest(driver._payload()) == parent["parent_state_digest"],
            "real parent parameters/buffers/Adam/RNG/pi/cursor changed")


class ScientificMonitor:
    """Small adapter for the existing saved-tensor/replay monitor protocol."""

    def __init__(self, guard, *, cooperative_replay=False):
        self.guard, self.torch = guard, guard.torch
        self.cooperative_replay = cooperative_replay

    def snapshot(self, label, *, boundary=False, **context):
        # The accumulator must save a whole response before honoring a signal.
        # Physical resource gates are still checked on every replay boundary.
        return self.guard.check(label, boundary=boundary, **context)

    def clear_unused(self, label):
        before = self.snapshot(label + ".before_cleanup", boundary=False)
        gc.collect()
        self.torch.cuda.empty_cache()
        after = self.snapshot(label + ".after_cleanup", boundary=True)
        return dict(before=before, after=after)

    def check_stop(self, label, **context):
        if self.guard.stop.requested:
            raise RuntimeError("scientific worker stop requested at " + label)


def load_cache(root, parent, rt):
    plan = training_api.records.read_ref(parent["task_plan"])
    if parent["old_class_context"]:
        old = training_api.records.read_ref(parent["old_class_context"])
        require(old["pre_state_digest"] == parent["parent_state_digest"]
                and old["task_plan"]["id"] == plan["id"]
                and old["task_binding"]["component_digest"] == parent["component_digests"],
                "inherited class gradients do not bind the exact actual parent")
        binding, cache_root = old["task_binding"], Path(old["task_cache_root"])
    else:
        binding = dict(schema="v54_same_parent_complete_task_binding.v1",
                       parent_id=parent["id"], parent_state_digest=parent["parent_state_digest"],
                       point_id=parent["point_id"], task_plan_id=plan["id"],
                       parameter_spec=parent["parameter_spec"],
                       scientific_sources=parent["scientific_sources"],
                       component_digests=parent["component_digests"],
                       cross_parameter_point_reuse=False)
        cache_root = Path(root) / f"parents/seed{parent['seed']}/task_cache"
    cache = training_api.task_cache.TaskCache(cache_root, binding, plan,
                                             parent["parameter_spec"], rt)
    return cache


def execute_shard(directory, parent, stage, driver, pool, cache, rt, monitor):
    require(parent["old_class_context"] is None,
            "complete inherited class tasks must never be dispatched again")
    memory = importlib.import_module("finqa_v34_tail_memory")
    tasks = cache.plan["assignments"][int(stage[-2:])]["task_ids"]
    new_tasks, reused, rows = [], [], 0
    assert_live_parent(driver, parent, rt)
    for task in tasks:
        monitor.check_stop("before_complete_class_task", task_id=task)
        if cache.has(task):
            reused.append(task)
            continue
        view = training_api.task_cache.TaskPoolView(pool, [task])
        values, receipt = memory.class_gradients_with_cpu_saves(
            rt, driver.model, view, device="cuda:0", monitor=monitor)
        require(list(values) == [task], "class kernel changed original task coverage")
        assert_live_parent(driver, parent, rt)
        monitor.clear_unused("complete_class_task")
        monitor.check_stop("before_complete_task_cache_commit", task_id=task)
        cache.commit(task, values[task].values_cpu, receipt=dict(
            parent_id=parent["id"], stage=stage, actual_parent_unchanged=True,
            saved_tensors=receipt, original_class_math_unchanged=True,
            new_feedback=0, optimizer_updates=0,
        ))
        new_tasks.append(task)
        rows += receipt["rows_completed"]
        del values
    assert_live_parent(driver, parent, rt)
    return dict(task_ids=tasks, task_count=len(tasks), new_complete_tasks=len(new_tasks),
                reused_complete_tasks=len(reused), new_effective_rows=rows,
                partial_rows_are_not_checkpoints=True, optimizer_updates=0)


def checked_old_point(parent, state, outer, rt):
    guard = importlib.import_module("finqa_v32_same_point_guard")
    require(guard.recompute_point_id(state, theta_bar=outer["theta_bar"],
                                    G=outer["G"], frozen_runtime=rt) == parent["point_id"],
            "persisted G/theta_bar is not the original complete parent point")


def execute_feedback(directory, parent, state, outer, driver, assets, science, rt, monitor,
                     *, recovery_root=None):
    temperature = importlib.import_module("finqa_v54_temperature")
    checked_old_point(parent, state, outer, rt)
    if (Path(directory) / "payload/record.json").exists():
        value = read_payload(directory, parent, "feedback_C05", rt)
        cohort, rewards = temperature.read_complete(value["feedback_root"], value["condition"])
        require(value["rewards"] == rewards and cohort.identity.point_id == parent["point_id"],
                "completed feedback payload no longer matches its actual sealed cohort")
        return dict(payload=training_api.records.entry(Path(directory) / "payload/record.json"),
                    condition_id=value["condition"]["id"], denominator=700,
                    new_feedback_sessions=0, total_feedback_sessions=700, temperature=0.5,
                    completed_payload_reused=True, real_parent_unchanged=True)
    theta = {name: value.to(driver.parameters[name].device)
             for name, value in outer["theta_bar"].items()}
    cfg = temperature.RunConfig.model_validate(science["feedback_config"])
    recovery_factory = None
    if recovery_root is not None:
        protocol = checked(Path(recovery_root) / "protocol/record.json")
        if "feedback_recovery" in protocol:
            recovery = importlib.import_module("finqa_v55_feedback_recovery")
            recovery_factory = lambda condition: recovery.registered_guard(
                recovery_root, parent["seed"], condition)
    collector = temperature.LocalFeedbackCollector(
        snapshot=assets["snapshot"], role_plan=assets["role_plan"],
        root=Path(directory) / "feedback", config=cfg.model_copy(update={"temperature": 0.5}),
        model_id=assets["assets"]["base_binding"]["id"], seeds=(11, 29),
        recovery_guard_factory=recovery_factory)

    def event(value):
        monitor.snapshot("feedback." + value["phase"], boundary=True,
                         feedback_condition_id=value.get("feedback_condition_id"),
                         draw_seed=value.get("draw_seed"))
        monitor.check_stop("feedback." + value["phase"])

    cohort, rewards = collector.collect(driver.model, driver.tokenizer, theta,
                                         point_id=parent["point_id"], event_sink=event)
    assert_live_parent(driver, parent, rt)
    value = dict(condition=collector.condition, feedback_root=str(collector.feedback_root),
                 point_id=parent["point_id"], rewards=list(rewards),
                 feedback_seal=cohort.model_dump(mode="json", exclude={"episodes"}),
                 feedback_files={name: training_api.file_ref(collector.feedback_root / name)
                    for name in ("intent/record.json", "cohort_seal/record.json",
                                 "native_rewards/record.json", "condition_cohort_binding/record.json",
                                 "draw0/generation_seal/seal.json", "draw1/generation_seal/seal.json")})
    reference = save_payload(directory, value, parent, "feedback_C05", rt)
    return dict(payload=reference, condition_id=collector.condition["id"], denominator=700,
                new_feedback_sessions=700, temperature=0.5, real_parent_unchanged=True)


def load_feedback(root, parent, rt):
    temperature = importlib.import_module("finqa_v54_temperature")
    payload = read_payload(stage_root(root, parent["seed"], "feedback_C05"),
                           parent, "feedback_C05", rt)
    for ref in payload["feedback_files"].values():
        require(training_api.sha(ref["path"]) == ref["sha256"],
                "condition-bound actual feedback bytes changed")
    condition = temperature.checked_condition(payload["condition"])
    require(condition["identity"]["point_id"] == parent["point_id"]
            and condition["temperature"] == 0.5,
            "C05 feedback belongs to another probability or parameter point")
    cohort, rewards = temperature.read_complete(payload["feedback_root"], condition)
    require(rewards == payload["rewards"]
            and cohort.model_dump(mode="json", exclude={"episodes"}) == payload["feedback_seal"],
            "stage payload no longer binds the sealed C05 feedback and rewards")
    return payload, cohort, rewards


def execute_replay(root, directory, parent, state, outer, driver, rt, monitor):
    temperature = importlib.import_module("finqa_v54_temperature")
    if (Path(directory) / "payload/record.json").exists():
        value = read_payload(directory, parent, "replay_C05", rt)
        report = value["report"]
        require(report["complete_replay"] is True and report["denominator"] == 700
                and report["point_id"] == parent["point_id"]
                and report["feedback_condition_id"] == value["condition"]["id"]
                and report["temperature"] == value["condition"]["temperature"] == 0.5
                and report["gJ_digest"] == rt.v8.parameter_digest(value["gJ"]),
                "saved complete C05 replay payload does not satisfy its original contract")
        return dict(payload=training_api.records.entry(Path(directory) / "payload/record.json"),
                    denominator=700, complete_replay=True, condition_id=value["condition"]["id"],
                    temperature=0.5, responses=report["response_checkpoint_binding"]["response_count"],
                    replayed_responses=0, completed_payload_reused=True, real_parent_unchanged=True)
    feedback, cohort, rewards = load_feedback(root, parent, rt)
    theta = {name: value.to(driver.parameters[name].device)
             for name, value in outer["theta_bar"].items()}
    profile_id = digest(dict(parent_id=parent["id"], condition_id=feedback["condition"]["id"],
                             scientific_stage="replay_C05"))

    def observe(value):
        monitor.snapshot("replay." + value["phase"], boundary=True,
                         response_backend_observation=value)

    def factory(model, parameters):
        return temperature.ReplaySession(
            model, parameters, temperature=0.5, condition_id=feedback["condition"]["id"],
            profile_id=profile_id, resident_kv_budget_bytes=2 * GIB,
            full_kv_budget_bytes=8 * GIB, activation_resident_budget_bytes=16 * GIB,
            allocated_memory_limit_bytes=76 * GIB, free_memory_reserve_bytes=2 * GIB,
            response_monitor=observe)

    rng_source = dict(checkpoint=dict(path=str(Path(parent["parent_checkpoint"]["path"]) / "state.pt"),
                                     sha256=parent["parent_checkpoint"]["state_sha256"]),
                      field="rng", digest=rt.v8._tree_digest(state["rng"]))
    monitor.clear_unused("before_C05_R3_replay")
    with rt.v8.installed_point(driver.model, theta) as installed:
        gradients, report = temperature.feedback_gradient(
            cohort, rewards, driver.model, installed, condition=feedback["condition"],
            root=Path(directory) / "checkpoints", profile_id=profile_id,
            backend_factory=factory, rng_restore_source=rng_source,
            pause_request=monitor.guard.stop, pause_after_response=None,
            checkpoint_every=16, event_sink=monitor.guard.event_sink)
    require(report["complete_replay"] is True and report["denominator"] == 700
            and report["point_id"] == parent["point_id"]
            and report["feedback_condition_id"] == feedback["condition"]["id"]
            and report["temperature"] == 0.5
            and report["gJ_digest"] == rt.v8.parameter_digest(gradients),
            "C05 complete replay probability/point binding failed")
    assert_live_parent(driver, parent, rt)
    value = dict(gJ=_cpu(gradients), report=report, condition=feedback["condition"],
                 point_id=parent["point_id"], rng_source=rng_source)
    reference = save_payload(directory, value, parent, "replay_C05", rt)
    return dict(payload=reference, denominator=700, complete_replay=True,
                condition_id=feedback["condition"]["id"], temperature=0.5,
                responses=report["response_checkpoint_binding"]["response_count"],
                restored_completed_responses=report["restored_completed_responses"],
                real_parent_unchanged=True)


def execute_distribution(root, directory, parent, state, outer, driver, cache, rt, monitor):
    if (Path(directory) / "payload/record.json").exists():
        value = read_payload(directory, parent, "distribution_C05", rt)
        require(value["point_id"] == parent["point_id"]
                and value["condition"]["temperature"] == 0.5
                and value["historical_G_theta_bar_bitwise_equal"] is True,
                "saved C05 distribution belongs to another virtual point")
        training_api.validate_distribution(value["q"], state["pi"])
        return dict(payload=training_api.records.entry(Path(directory) / "payload/record.json"),
                    condition_id=value["condition"]["id"],
                    distribution_digest=rt.v8._tree_digest(value["q"]), denominator=700,
                    historical_G_theta_bar_bitwise_equal=True, real_parent_unchanged=True,
                    complete_class_tasks=744, complete_class_rows=4974, optimizer_updates=0,
                    completed_payload_reused=True)
    replay = read_payload(stage_root(root, parent["seed"], "replay_C05"),
                          parent, "replay_C05", rt)
    require(replay["condition"]["temperature"] == 0.5
            and replay["condition"]["identity"]["point_id"] == parent["point_id"]
            and replay["report"]["complete_replay"] is True
            and replay["report"]["denominator"] == 700,
            "distribution requires the complete correct-temperature actual replay")
    gradients = cache.assemble(device="cuda:0")
    require(len(gradients) == 744, "full original class support required")
    prepared = rt.v8.prepare_virtual_point(driver.parameters, driver.optimizer, gradients,
                                           state["pi"], parent["mu"])
    for key in ("G", "theta_bar"):
        require(list(prepared[key]) == list(outer[key])
                and all(rt.torch.equal(value.detach().cpu(), outer[key][name])
                        for name, value in prepared[key].items()),
                "same-parent class rebuild differs from actual historical " + key)
    checked_old_point(parent, state, prepared, rt)
    monitor.clear_unused("same_parent_class_G_theta_bar_verified")
    gJ = {name: value.to(driver.parameters[name].device)
          for name, value in replay["gJ"].items()}
    result = rt.v8.update_distribution(
        prepared, gradients, gJ, state["pi"], state["prior"], parent["mu"],
        feedback_report=replay["report"], contribution_only=True,
        control_tasks=[task for task, row in state["prior"].items() if len(row) == 1],
        **rt.v8.PARAMETERS)
    q = result["distribution"]["pi_next"]
    training_api.validate_distribution(q, state["pi"])
    assert_live_parent(driver, parent, rt)
    evidence = {key: copy.deepcopy(value) for key, value in result.items() if key != "a"}
    value = dict(q=q, C=result["C"], pullback=_cpu(result["a"]), gJ=_cpu(gJ),
                 G=_cpu(prepared["G"]), theta_bar=_cpu(prepared["theta_bar"]),
                 evidence=evidence, condition=replay["condition"], point_id=parent["point_id"],
                 training_rng=copy.deepcopy(state["rng"]),
                 historical_G_theta_bar_bitwise_equal=True,
                 fixed_RMS_and_anchors=True, contribution_exponent=0.8, novelty_exponent=0)
    reference = save_payload(directory, value, parent, "distribution_C05", rt)
    monitor.clear_unused("C05_distribution_complete")
    return dict(payload=reference, condition_id=replay["condition"]["id"],
                distribution_digest=rt.v8._tree_digest(q), denominator=700,
                historical_G_theta_bar_bitwise_equal=True, real_parent_unchanged=True,
                complete_class_tasks=744, complete_class_rows=4974, optimizer_updates=0)


def run(root, seed, stage, gpu_index):
    root = Path(root).resolve()
    job = job_spec(seed, stage)
    plan = checked(root / "protocol/record.json")
    directory = stage_root(root, seed, stage)
    directory.mkdir(parents=True, exist_ok=True)
    require(not (directory / "result/record.json").exists(), "successful stage cannot execute again")
    with (directory / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        attempts = directory / "attempts"
        number = max((int(p.name.removeprefix("attempt")) for p in attempts.glob("attempt*")), default=0) + 1
        attempt = attempts / f"attempt{number:04d}"
        started = time.time()
        publish(attempt / "started/record.json", dict(schema="v54_scientific_worker_start.v1",
                protocol_id=plan["id"], job=job, gpu_index=gpu_index, pid=os.getpid(),
                started_epoch=started, automatic_retry_in_worker=False))
        try:
            training, rt = training_api.runtime()
            # Import scientific dependencies before restoring the actual training RNG.
            for module in ("finqa_v54_temperature", "finqa_v34_tail_memory",
                           "finqa_v32_same_point_guard",
                           "trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.trajectory_consumer",
                           "trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.optimizer_pullback",
                           "trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.distribution"):
                importlib.import_module(module)
            parent, state, outer = training_api.load_parent(root, seed, rt)
            require(parent["protocol_id"] == plan["id"], "parent belongs to another experiment protocol")
            science, pool, _prefix, assets = training.checked_launch(parent["training_root"])
            cache = load_cache(root, parent, rt) if stage.startswith("shard") or stage == "distribution_C05" else None
            guard_module = importlib.import_module("finqa_v54_runtime")
            with guard_module.execution_context(root, job, gpu_index) as guard:
                monitor = ScientificMonitor(guard, cooperative_replay=stage == "replay_C05")
                model, tokenizer, optimizer, scope, _fresh = rt.launcher._load_components(assets, seed)
                branch = job["arm"]
                driver_root = (training_api.branch_root(root, seed, branch) / "training"
                               if branch else directory / "unused_training")
                driver = training.adapters().TrainingDriver(
                    model, optimizer, pool, root=driver_root, seed=seed, arm="C-only",
                    device="cuda:0", tokenizer=tokenizer, adapter_scope=scope,
                    feedback_collector=None)
                driver.restore(parent["parent_checkpoint"]["path"])
                assert_live_parent(driver, parent, rt)
                monitor.clear_unused("after_model_load")
                if stage.startswith("shard"):
                    body = execute_shard(directory, parent, stage, driver, pool, cache, rt, monitor)
                elif stage == "feedback_C05":
                    body = execute_feedback(directory, parent, state, outer, driver,
                                            assets, science, rt, monitor, recovery_root=root)
                elif stage == "replay_C05":
                    body = execute_replay(root, directory, parent, state, outer, driver, rt, monitor)
                elif stage == "distribution_C05":
                    body = execute_distribution(root, directory, parent, state, outer,
                                                driver, cache, rt, monitor)
                else:
                    if branch == "Hold":
                        q, source = state["pi"], dict(parent_id=parent["id"], field="pi")
                    elif branch == "C1":
                        require(not parent["c1_reuse"]["eligible"],
                                "an admitted C1 path must be reused, never retrained")
                        q, source = outer["q_next"], parent["old_outer_inputs"]
                    else:
                        distribution = read_payload(stage_root(root, seed, "distribution_C05"),
                                                    parent, "distribution_C05", rt)
                        q = distribution["q"]
                        source = training_api.records.entry(stage_root(root, seed, "distribution_C05") / "payload/record.json")
                    completed = training_api.branch_root(root, seed, branch) / "completed/record.json"
                    if completed.exists():
                        branch_result = training_api.checked_branch_result(root, seed, branch)
                        require(branch_result["protocol_id"] == plan["id"]
                                and branch_result["parent_state_digest"] == parent["parent_state_digest"]
                                and branch_result["distribution_digest"] == rt.v8._tree_digest(q),
                                "saved complete branch belongs to another protocol/parent/q")
                        training_api.configure_fixed_window(driver)
                        driver.restore(branch_result["snapshots"]["894"]["path"])
                    else:
                        branch_result = training_api.execute_training(
                            root, seed, branch, plan["id"], driver, q, rt=rt, monitor=monitor,
                            distribution_source=source, resource_report=guard.report)
                    body = dict(branch_result=training_api.records.entry(
                                    training_api.branch_root(root, seed, branch) / "completed/record.json"),
                                final_step=894, optimizer_updates=298,
                                new_optimizer_updates=branch_result["new_optimizer_updates"])
                monitor.clear_unused("scientific_stage_complete")
                del driver, model, tokenizer, optimizer, pool, cache
                gc.collect()
                rt.torch.cuda.empty_cache()
                monitor.snapshot("after_model_release", boundary=True)
            resource_report = guard.report()
            result = publish(directory / "result/record.json", dict(
                schema="v54_scientific_stage_result.v1", status="COMPLETE",
                protocol_id=plan["id"], parent_id=parent["id"], seed=seed, stage=stage,
                job=job, gpu_index=gpu_index, started_epoch=started, finished_epoch=time.time(),
                resources=resource_report, model_released=True, **body))
            publish(attempt / "completed/record.json", dict(result=training_api.records.entry(
                    directory / "result/record.json"), protocol_id=plan["id"]))
            return result
        except BaseException as error:
            publish(attempt / "failure/record.json", dict(
                schema="v54_scientific_worker_failure.v1", protocol_id=plan["id"],
                job=job, gpu_index=gpu_index, exception_type=type(error).__name__,
                error=str(error), started_epoch=started, finished_epoch=time.time(),
                automatic_retry_in_worker=False, actual_durable_boundaries_only=True))
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--seed", type=int, choices=training_api.SEEDS, required=True)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--gpu-index", type=int, required=True)
    args = parser.parse_args()
    result = run(args.root, args.seed, args.stage, args.gpu_index)
    print(json.dumps(dict(status=result["status"], id=result["id"])))
