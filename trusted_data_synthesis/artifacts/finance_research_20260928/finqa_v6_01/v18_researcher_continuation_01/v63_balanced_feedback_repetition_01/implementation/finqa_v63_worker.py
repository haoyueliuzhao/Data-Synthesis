"""Cold batch-one scientific stages; both temperatures consume new feedback."""
from __future__ import annotations

import copy
import fcntl
import gc
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import time

import finqa_v63_binding as binding
binding.install_scientific_paths()
import finqa_v63_training as training_api
import finqa_v54_worker as original

ROOT, SEEDS, ARMS, BATCH = binding.ROOT, binding.SEEDS, binding.ARMS, binding.BATCH
STAGES = tuple(f"{phase}_{arm}" for arm in ARMS
               for phase in ("feedback", "replay", "distribution", "train"))
GIB = 1024 ** 3
require, digest, checked, publish = binding.require, binding.digest, binding.checked, binding.publish
ScientificMonitor = original.ScientificMonitor
assert_live_parent, checked_old_point = original.assert_live_parent, original.checked_old_point
_cpu = original._cpu


def stage_root(root, seed, stage):
    require(Path(root).resolve() == ROOT and seed in SEEDS and stage in STAGES,
            "unregistered V63 scientific stage")
    return Path(root) / f"stages/seed{seed}/{stage}"


def job_spec(seed, stage):
    require(seed in SEEDS and stage in STAGES, "unregistered V63 scientific job")
    phase, arm = stage.split("_", 1)
    return dict(id=f"seed{seed}.{stage}", job_id=f"seed{seed}.{stage}",
                seed=seed, stage=stage, kind=phase, memory_phase=phase,
                arm=arm, feedback_batch=BATCH, temperature=binding.TEMPERATURES[arm])


def save_payload(directory, value, parent, stage, rt):
    from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
    directory = Path(directory).resolve()
    job = job_spec(parent["seed"], stage)
    require(directory == stage_root(ROOT, parent["seed"], stage), "payload escaped its condition")
    stream = io.BytesIO()
    rt.torch.save(value, stream)
    raw = stream.getvalue()
    body = dict(schema="v63_actual_scientific_payload.v1", parent_id=parent["id"],
        parent_state_digest=parent["parent_state_digest"], stage=stage,
        feedback_batch=BATCH, arm=job["arm"], temperature=job["temperature"],
        state_sha256=hashlib.sha256(raw).hexdigest(), state_bytes=len(raw),
        state_digest=rt.v8._tree_digest(value), actual_tensors_saved=True)
    record = {**body, "id": digest(body)}
    write_immutable_artifact_directory(directory / "payload", {
        "state.pt": raw,
        "record.json": (json.dumps(record, ensure_ascii=False, sort_keys=True,
                                  indent=2, allow_nan=False) + "\n").encode()})
    return binding.entry(directory / "payload/record.json")


def read_payload(directory, parent, stage, rt):
    directory = Path(directory).resolve()
    job = job_spec(parent["seed"], stage)
    require(directory == stage_root(ROOT, parent["seed"], stage), "foreign payload directory")
    base = directory / "payload"
    record = checked(base / "record.json")
    require(record["schema"] == "v63_actual_scientific_payload.v1"
            and record["parent_id"] == parent["id"]
            and record["parent_state_digest"] == parent["parent_state_digest"]
            and (record["stage"], record["arm"], record["feedback_batch"], record["temperature"])
                == (stage, job["arm"], BATCH, job["temperature"])
            and record["actual_tensors_saved"] is True, "payload scientific identity changed")
    raw = (base / "state.pt").read_bytes()
    require(len(raw) == record["state_bytes"]
            and hashlib.sha256(raw).hexdigest() == record["state_sha256"],
            "actual payload bytes changed")
    value = rt.torch.load(io.BytesIO(raw), map_location="cpu", weights_only=False)
    require(rt.v8._tree_digest(value) == record["state_digest"], "payload semantic state changed")
    return value


def load_cache(root, parent, rt):
    require(Path(root).resolve() == ROOT, "foreign class-cache consumer")
    old_parent = binding.read_ref(parent["original_parent"])
    require(old_parent["parent_state_digest"] == parent["parent_state_digest"]
            and old_parent["point_id"] == parent["point_id"],
            "class cache must belong to the identical actual parent")
    # The original loader preserves the nine-task V55 overlay for seed137 and
    # the original complete seed389 context, including their original bindings.
    cache = original.load_cache(binding.OLD_ROOT, old_parent, rt)
    require(cache.plan["id"] == parent["task_plan"]["id"]
            and len(cache.plan["task_ids"]) == 744, "complete original task plan required")
    return cache


def _condition(value, parent, arm):
    temperature = importlib.import_module("finqa_v63_temperature")
    condition = temperature.checked_condition(value)
    require(condition["identity"]["point_id"] == parent["point_id"]
            and condition["arm"] == arm and condition["feedback_batch"] == BATCH
            and condition["temperature"] == binding.TEMPERATURES[arm],
            "new feedback condition belongs to another point, temperature or batch")
    return condition


def execute_feedback(directory, parent, state, outer, driver, assets, science, rt, monitor,
                     *, arm, attempt_root):
    temperature = importlib.import_module("finqa_v63_temperature")
    stage = "feedback_" + arm
    checked_old_point(parent, state, outer, rt)
    if (Path(directory) / "payload/record.json").exists():
        value = read_payload(directory, parent, stage, rt)
        condition = _condition(value["condition"], parent, arm)
        cohort, rewards = temperature.read_complete(value["feedback_root"], condition)
        require(value["rewards"] == rewards and cohort.denominator == 700,
                "completed batch-one feedback payload changed")
        return dict(payload=binding.entry(Path(directory) / "payload/record.json"),
            condition_id=condition["id"], denominator=700, new_feedback_sessions=700,
            new_feedback_calls_in_this_attempt=0, completed_payload_reused=True,
            real_parent_unchanged=True)
    theta = {name: value.to(driver.parameters[name].device)
             for name, value in outer["theta_bar"].items()}
    config = temperature.RunConfig.model_validate(science["feedback_config"])
    collector = temperature.LocalFeedbackCollector(
        snapshot=assets["snapshot"], role_plan=assets["role_plan"],
        root=Path(directory) / "feedback",
        config=config.model_copy(update={"temperature": binding.TEMPERATURES[arm]}),
        model_id=assets["assets"]["base_binding"]["id"], arm=arm, batch=BATCH,
        seeds=binding.DRAW_SEEDS, attempt_root=Path(attempt_root) / "generation")

    def event(value):
        monitor.snapshot("feedback." + value["phase"], boundary=True,
            feedback_condition_id=value.get("feedback_condition_id"),
            draw_seed=value.get("draw_seed"))
        monitor.check_stop("feedback." + value["phase"])

    cohort, rewards = collector.collect(driver.model, driver.tokenizer, theta,
        point_id=parent["point_id"], event_sink=event)
    _condition(collector.condition, parent, arm)
    assert_live_parent(driver, parent, rt)
    value = dict(condition=collector.condition, feedback_root=str(collector.feedback_root),
        point_id=parent["point_id"], rewards=list(rewards),
        feedback_seal=cohort.model_dump(mode="json", exclude={"episodes"}),
        feedback_files={name: binding.file_ref(collector.feedback_root / name) for name in
            ("intent/record.json", "cohort_seal/record.json", "native_rewards/record.json",
             "condition_cohort_binding/record.json", "draw0/generation_seal/seal.json",
             "draw1/generation_seal/seal.json")})
    reference = save_payload(directory, value, parent, stage, rt)
    return dict(payload=reference, condition_id=collector.condition["id"], denominator=700,
                new_feedback_sessions=700, real_parent_unchanged=True)


def load_feedback(root, parent, rt, arm):
    temperature = importlib.import_module("finqa_v63_temperature")
    stage = "feedback_" + arm
    payload = read_payload(stage_root(root, parent["seed"], stage), parent, stage, rt)
    for reference in payload["feedback_files"].values():
        require(binding.sha(reference["path"]) == reference["sha256"],
                "sealed new feedback bytes changed")
    condition = _condition(payload["condition"], parent, arm)
    cohort, rewards = temperature.read_complete(payload["feedback_root"], condition)
    require(rewards == payload["rewards"]
            and cohort.model_dump(mode="json", exclude={"episodes"}) == payload["feedback_seal"],
            "complete condition-bound feedback and rewards changed")
    return payload, cohort, rewards


def execute_replay(root, directory, parent, state, outer, driver, rt, monitor, *, arm):
    temperature = importlib.import_module("finqa_v63_temperature")
    stage = "replay_" + arm
    if (Path(directory) / "payload/record.json").exists():
        value = read_payload(directory, parent, stage, rt)
        condition = _condition(value["condition"], parent, arm)
        report = value["report"]
        require(report["complete_replay"] is True and report["denominator"] == 700
                and report["gJ_digest"] == rt.v8.parameter_digest(value["gJ"])
                and value["draw_diagnostics_passed"] is True
                and set(value["draw_gJ"]) == {101, 103},
                "complete replay must contain both actual diagnostic draw accumulators")
        return dict(payload=binding.entry(Path(directory) / "payload/record.json"),
            denominator=700, complete_replay=True, condition_id=condition["id"],
            responses=report["response_checkpoint_binding"]["response_count"],
            replayed_responses=0, completed_payload_reused=True,
            draw_diagnostics_passed=True, real_parent_unchanged=True)
    feedback, cohort, rewards = load_feedback(root, parent, rt, arm)
    theta = {name: value.to(driver.parameters[name].device)
             for name, value in outer["theta_bar"].items()}
    profile_id = digest(dict(parent_id=parent["id"], condition_id=feedback["condition"]["id"],
                             scientific_stage=stage, feedback_batch=BATCH))

    def observe(value):
        monitor.snapshot("replay." + value["phase"], boundary=True,
                         response_backend_observation=value)

    def factory(model, parameters):
        class CapacityCheckedSession(temperature.ReplaySession):
            def __call__(self, model, theta, prompt, targets, **kwargs):
                monitor.guard.prepare_replay_response(self, model, len(prompt), len(targets))
                return super().__call__(model, theta, prompt, targets, **kwargs)
        return CapacityCheckedSession(model, parameters,
            temperature=binding.TEMPERATURES[arm], condition_id=feedback["condition"]["id"],
            profile_id=profile_id, resident_kv_budget_bytes=2 * GIB,
            full_kv_budget_bytes=8 * GIB, activation_resident_budget_bytes=16 * GIB,
            allocated_memory_limit_bytes=76 * GIB, free_memory_reserve_bytes=2 * GIB,
            response_monitor=observe)

    rng_source = dict(checkpoint=dict(
        path=str(Path(parent["parent_checkpoint"]["path"]) / "state.pt"),
        sha256=parent["parent_checkpoint"]["state_sha256"]),
        field="rng", digest=rt.v8._tree_digest(state["rng"]))
    components = {}
    monitor.clear_unused("before_batch1_R3_replay")
    with rt.v8.installed_point(driver.model, theta) as installed:
        gradients, report = temperature.feedback_gradient(
            cohort, rewards, driver.model, installed, condition=feedback["condition"],
            root=Path(directory) / "checkpoints", profile_id=profile_id,
            backend_factory=factory, rng_restore_source=rng_source,
            pause_request=monitor.guard.stop, pause_after_response=None,
            checkpoint_every=16, event_sink=monitor.guard.event_sink,
            draw_components_out=components, mean_tolerances=temperature.MEAN_TOLERANCES,
            component_monitor=observe)
    require(report["complete_replay"] is True and report["denominator"] == 700
            and report["point_id"] == parent["point_id"]
            and report["feedback_condition_id"] == feedback["condition"]["id"]
            and report["temperature"] == binding.TEMPERATURES[arm]
            and report["gJ_digest"] == rt.v8.parameter_digest(gradients)
            and set(components) == {101, 103}, "actual batch-one replay/draw binding failed")
    assert_live_parent(driver, parent, rt)
    value = dict(gJ=_cpu(gradients), draw_gJ=components, report=report,
        condition=feedback["condition"], point_id=parent["point_id"],
        rng_source=rng_source, draw_diagnostics_passed=True)
    reference = save_payload(directory, value, parent, stage, rt)
    return dict(payload=reference, denominator=700, complete_replay=True,
        condition_id=feedback["condition"]["id"],
        responses=report["response_checkpoint_binding"]["response_count"],
        restored_completed_responses=report["restored_completed_responses"],
        draw_diagnostics_passed=True, real_parent_unchanged=True)


def draw_contributions(prepared, gradients, replay, formal_C, state, parent, rt, monitor):
    """Two analytic VJPs and original centered-C calls; never normalize draw q."""
    from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import optimizer_pullback as adam
    temperature = importlib.import_module("finqa_v63_temperature")
    require(set(replay["draw_gJ"]) == {101, 103}, "both diagnostic draw covectors required")
    started = time.monotonic()
    components, pullback_digests = {}, {}
    for seed in binding.DRAW_SEEDS:
        monitor.check_stop("before_diagnostic_draw_VJP", draw_seed=seed)
        vector = {name: value.to(prepared["G"][name].device)
                  for name, value in replay["draw_gJ"][seed].items()}
        pulled = adam.pullback(prepared["binding"], prepared["G"],
                               {name: -value for name, value in vector.items()})
        centered = adam.centered_contributions(gradients, state["pi"], parent["mu"], pulled["a"])
        components[str(seed)] = centered["C"]
        pullback_digests[str(seed)] = rt.v8.parameter_digest(pulled["a"])
        del vector, pulled, centered
        monitor.clear_unused("diagnostic_draw_VJP_complete")
    atol, rtol = (temperature.MEAN_TOLERANCES[k] for k in ("atol", "rtol"))
    largest = 0.0
    for task, states in formal_C.items():
        for slot, formal in states.items():
            mean = (components["101"][task][slot] + components["103"][task][slot]) / 2
            error = abs(mean - formal)
            largest = max(largest, error)
            if not error <= atol + rtol * abs(formal):
                from finqa_v63_draw_components import DrawDiagnosticError
                raise DrawDiagnosticError("diagnostic raw C mean differs from formal original-order C")
    return dict(schema="v63_same_operator_raw_draw_Contribution_diagnostic.v1",
        C_by_draw=components, draw_denominator=350, formal_denominator=700,
        formal_C_digest=digest(formal_C), pullback_digests=pullback_digests,
        original_fixed_optimizer_binding_id=prepared["binding"].snapshot["id"],
        mean_tolerances=temperature.MEAN_TOLERANCES, maximum_absolute_C_mean_error=largest,
        mean_comparison_passed=True, normalized_draw_q_computed=False,
        formal_q_uses_only_formal_C=True, additional_analytic_VJPs=2,
        additional_centered_inner_product_passes=2, new_class_forward_passes=0,
        new_response_replays=0, elapsed_seconds=time.monotonic() - started)


def execute_distribution(root, directory, parent, state, outer, driver, cache, rt, monitor, *, arm):
    stage = "distribution_" + arm
    if (Path(directory) / "payload/record.json").exists():
        value = read_payload(directory, parent, stage, rt)
        condition = _condition(value["condition"], parent, arm)
        require(value["point_id"] == parent["point_id"]
                and value["historical_G_theta_bar_bitwise_equal"] is True
                and value["draw_C_diagnostics"]["mean_comparison_passed"] is True,
                "saved distribution lacks same-point and draw diagnostic proof")
        training_api.validate_distribution(value["q"], state["pi"])
        return dict(payload=binding.entry(Path(directory) / "payload/record.json"),
            condition_id=condition["id"], distribution_digest=rt.v8._tree_digest(value["q"]),
            denominator=700, historical_G_theta_bar_bitwise_equal=True,
            real_parent_unchanged=True, complete_class_tasks=744, complete_class_rows=4974,
            optimizer_updates=0, completed_payload_reused=True, draw_C_diagnostics_passed=True)
    replay_stage = "replay_" + arm
    replay = read_payload(stage_root(root, parent["seed"], replay_stage), parent, replay_stage, rt)
    _condition(replay["condition"], parent, arm)
    require(replay["report"]["complete_replay"] is True
            and replay["report"]["denominator"] == 700
            and replay["draw_diagnostics_passed"] is True,
            "distribution requires the complete actual new replay")
    gradients = cache.assemble(device="cuda:0")
    require(len(gradients) == 744, "complete original class support required")
    prepared = rt.v8.prepare_virtual_point(driver.parameters, driver.optimizer, gradients,
                                         state["pi"], parent["mu"])
    for key in ("G", "theta_bar"):
        require(list(prepared[key]) == list(outer[key])
                and all(rt.torch.equal(value.detach().cpu(), outer[key][name])
                        for name, value in prepared[key].items()),
                "same-parent class reconstruction differs from original " + key)
    checked_old_point(parent, state, prepared, rt)
    monitor.clear_unused("same_parent_G_theta_bar_verified")
    gJ = {name: value.to(driver.parameters[name].device) for name, value in replay["gJ"].items()}
    result = rt.v8.update_distribution(
        prepared, gradients, gJ, state["pi"], state["prior"], parent["mu"],
        feedback_report=replay["report"], contribution_only=True,
        control_tasks=[task for task, row in state["prior"].items() if len(row) == 1],
        **rt.v8.PARAMETERS)
    q = result["distribution"]["pi_next"]
    training_api.validate_distribution(q, state["pi"])
    q_before_diagnostics = rt.v8._tree_digest(q)
    draws = draw_contributions(prepared, gradients, replay, result["C"], state, parent, rt, monitor)
    require(rt.v8._tree_digest(q) == q_before_diagnostics, "diagnostics changed the formal q")
    assert_live_parent(driver, parent, rt)
    value = dict(q=q, C=result["C"], pullback=_cpu(result["a"]), gJ=_cpu(gJ),
        G=_cpu(prepared["G"]), theta_bar=_cpu(prepared["theta_bar"]),
        evidence={key: copy.deepcopy(value) for key, value in result.items() if key != "a"},
        condition=replay["condition"], point_id=parent["point_id"],
        training_rng=copy.deepcopy(state["rng"]), historical_G_theta_bar_bitwise_equal=True,
        fixed_RMS_and_anchors=True, contribution_exponent=0.8, novelty_exponent=0,
        draw_C_diagnostics=draws)
    reference = save_payload(directory, value, parent, stage, rt)
    monitor.clear_unused("batch1_distribution_complete")
    return dict(payload=reference, condition_id=replay["condition"]["id"],
        distribution_digest=rt.v8._tree_digest(q), denominator=700,
        historical_G_theta_bar_bitwise_equal=True, real_parent_unchanged=True,
        complete_class_tasks=744, complete_class_rows=4974, optimizer_updates=0,
        draw_C_diagnostics_passed=True)


def run(root, seed, stage, gpu_index, *, attempt_root=None):
    import finqa_v63_runtime as resources
    import finqa_v63_worker_audit as audit
    root = Path(root).resolve()
    job = job_spec(seed, stage)
    protocol = checked(root / "protocol/record.json")
    directory = stage_root(root, seed, stage)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        attempt = audit.checked_attempt_directory(root, job, attempt_root)
        started = time.time()
        publish(attempt / "started/record.json", dict(schema="v63_scientific_worker_start.v1",
            protocol_id=protocol["id"], job=job, gpu_index=gpu_index, pid=os.getpid(),
            started_epoch=started, automatic_retry_in_worker=False))
        guard = None
        try:
            if (directory / "result/record.json").exists():
                return audit.reuse_complete_result(root, job, attempt)
            training, rt = training_api.runtime()
            for module in ("finqa_v63_temperature", "finqa_v34_tail_memory",
                           "finqa_v32_same_point_guard", "finqa_v56_feedback",
                           "trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.trajectory_consumer",
                           "trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.optimizer_pullback",
                           "trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.distribution"):
                importlib.import_module(module)
            parent, state, outer = training_api.load_parent(root, seed, rt)
            require(parent["protocol_id"] == protocol["id"], "new parent protocol changed")
            science, pool, _prefix, assets = training.checked_launch(parent["training_root"])
            cache = load_cache(root, parent, rt) if job["kind"] == "distribution" else None
            with resources.execution_context(root, job, gpu_index) as guard:
                monitor = ScientificMonitor(guard, cooperative_replay=job["kind"] == "replay")
                model, tokenizer, optimizer, scope, _fresh = rt.launcher._load_components(assets, seed)
                driver_root = (training_api.branch_root(root, seed, job["arm"]) / "training"
                               if job["kind"] == "train" else directory / "unused_training")
                driver = training.adapters().TrainingDriver(model, optimizer, pool, root=driver_root,
                    seed=seed, arm="C-only", device="cuda:0", tokenizer=tokenizer,
                    adapter_scope=scope, feedback_collector=None)
                driver.restore(parent["parent_checkpoint"]["path"])
                assert_live_parent(driver, parent, rt)
                monitor.clear_unused("after_model_load")
                if job["kind"] == "feedback":
                    body = execute_feedback(directory, parent, state, outer, driver, assets,
                        science, rt, monitor, arm=job["arm"], attempt_root=attempt)
                elif job["kind"] == "replay":
                    body = execute_replay(root, directory, parent, state, outer, driver,
                                          rt, monitor, arm=job["arm"])
                elif job["kind"] == "distribution":
                    body = execute_distribution(root, directory, parent, state, outer, driver,
                                                cache, rt, monitor, arm=job["arm"])
                else:
                    distribution_stage = "distribution_" + job["arm"]
                    distribution_root = stage_root(root, seed, distribution_stage)
                    distribution = read_payload(distribution_root, parent, distribution_stage, rt)
                    _condition(distribution["condition"], parent, job["arm"])
                    q = distribution["q"]
                    completed = training_api.branch_root(root, seed, job["arm"]) / "completed/record.json"
                    if completed.exists():
                        branch_result = training_api.checked_branch_result(root, seed, job["arm"])
                        require(branch_result["protocol_id"] == protocol["id"]
                                and branch_result["distribution_digest"] == rt.v8._tree_digest(q),
                                "completed new branch belongs to a different q")
                        training_api.configure_fixed_window(driver)
                        driver.restore(branch_result["snapshots"]["894"]["path"])
                    else:
                        branch_result = training_api.execute_training(root, seed, job["arm"],
                            protocol["id"], driver, q, rt=rt, monitor=monitor,
                            distribution_source=binding.entry(distribution_root / "payload/record.json"),
                            resource_report=guard.report)
                    body = dict(branch_result=binding.entry(completed), final_step=894,
                                optimizer_updates=298, new_optimizer_updates=298)
                monitor.clear_unused("scientific_stage_complete")
                del driver, model, tokenizer, optimizer, pool, cache
                gc.collect()
                rt.torch.cuda.empty_cache()
                monitor.snapshot("after_model_release", boundary=True)
            result = publish(directory / "result/record.json", dict(
                schema="v63_scientific_stage_result.v1", status="COMPLETE",
                protocol_id=protocol["id"], parent_id=parent["id"], seed=seed, stage=stage,
                arm=job["arm"], temperature=job["temperature"], feedback_batch=BATCH,
                job=job, gpu_index=gpu_index, started_epoch=started, finished_epoch=time.time(),
                actual_worker_pid=os.getpid(), actual_attempt_root=str(attempt),
                resources=guard.report(), model_released=True, **body))
            publish(attempt / "completed/record.json", dict(
                result=binding.entry(directory / "result/record.json"), protocol_id=protocol["id"]))
            publish(attempt / "result/record.json", dict(protocol_id=protocol["id"],
                job_id=job["job_id"], stable_result=binding.entry(directory / "result/record.json"),
                actual_worker_pid=os.getpid(), scientific_result_reused=False))
            return result
        except BaseException as error:
            audit.record_attempt_failure(root, job, attempt, error, guard=guard)
            raise


def audit_job_resume(*args, **kwargs):
    from finqa_v63_worker_audit import audit_job_resume as function
    return function(*args, **kwargs)


def classify_attempt(*args, **kwargs):
    from finqa_v63_worker_audit import classify_attempt as function
    return function(*args, **kwargs)


def reuse_complete_result(*args, **kwargs):
    from finqa_v63_worker_audit import reuse_complete_result as function
    return function(*args, **kwargs)


def record_attempt_failure(*args, **kwargs):
    from finqa_v63_worker_audit import record_attempt_failure as function
    return function(*args, **kwargs)
