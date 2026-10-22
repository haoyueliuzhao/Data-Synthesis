"""Real same-state class/feedback/R3/Full operations for three V70 points.

The lifecycle controller owns dispatch, resource guards and actual exit
acceptance. This module performs one admitted operation and returns evidence;
it never starts a worker, changes an old artifact, retries UNKNOWN feedback,
chooses a model by score, or applies the terminal probe.
"""
from __future__ import annotations

import copy
import gc
import hashlib
import importlib
import io
import json
from pathlib import Path

import finqa_v70_binding as binding
import finqa_v70_training as training_api

binding.install_scientific_paths()
reference = binding.source_module("finqa_v63_worker")
original = binding.old_module("finqa_v54_worker")
ROOT, POINTS, SEED = binding.ROOT, (894, 1192, 1490), 137
STAGES = ("shard00", "shard01", "shard02", "shard03", "virtual_point",
          "replay", "distribution", "train")
GIB = 1024 ** 3
require, checked, publish = binding.require, binding.checked, binding.publish


class ScientificMonitor(original.ScientificMonitor):
    """Retain the own native allocator cache, as in the admitted V64 policy."""

    def clear_unused(self, label):
        before = self.snapshot(label + ".before_cleanup", boundary=False)
        gc.collect()
        after = self.snapshot(label + ".after_cleanup", boundary=True)
        return dict(before=before, after=after, routine_allocator_cache_retained=True)


def stage_root(root, step, stage):
    require(stage in STAGES and not (step == 1490 and stage == "train"),
            "unregistered continuous scientific stage")
    return training_api.point_root(root, step) / stage


def job_spec(step, stage):
    stage_root(ROOT, step, stage)
    kind = "class" if stage.startswith("shard") else (
        "feedback" if stage == "virtual_point" else stage)
    return dict(id=f"step{step}.{stage}", job_id=f"step{step}.{stage}",
        seed=137, step=step, stage=stage, kind=kind, memory_phase=kind,
        arm="Full", temperature=1.0, probe_only=step == 1490)


def _cpu(values):
    return {name: value.detach().cpu().clone() for name, value in values.items()}


def assert_live_point(driver, context, rt):
    require(rt.v8._tree_digest(driver._payload()) == context["parent_state_digest"],
            "scientific operation changed actual theta/Adam/RNG/pi/history")


def save_payload(directory, value, context, stage, rt):
    from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
    directory = Path(directory).resolve()
    require(directory.is_relative_to(training_api.point_root(ROOT, context["step"]).resolve()),
            "actual tensor payload escaped its registered point")
    stream = io.BytesIO()
    rt.torch.save(value, stream)
    raw = stream.getvalue()
    body = dict(schema="v70_actual_scientific_payload.v1", point_context_id=context["id"],
        parent_state_digest=context["parent_state_digest"], step=context["step"], stage=stage,
        point_id=value.get("point_id"),
        state_sha256=hashlib.sha256(raw).hexdigest(), state_bytes=len(raw),
        state_digest=rt.v8._tree_digest(value), actual_tensors_saved=True)
    record = dict(body, id=binding.digest(body))
    write_immutable_artifact_directory(directory / "payload", {
        "state.pt": raw, "record.json": (json.dumps(record, ensure_ascii=False,
            sort_keys=True, indent=2, allow_nan=False) + "\n").encode()})
    return binding.entry(directory / "payload/record.json")


def read_payload(directory, context, stage, rt):
    directory = Path(directory).resolve()
    require(directory.is_relative_to(training_api.point_root(ROOT, context["step"]).resolve()),
            "cross-point scientific tensor read forbidden")
    base = directory / "payload"
    record = checked(base / "record.json")
    require(record["schema"] == "v70_actual_scientific_payload.v1"
            and record["point_context_id"] == context["id"]
            and record["parent_state_digest"] == context["parent_state_digest"]
            and record["step"] == context["step"] and record["stage"] == stage
            and record["actual_tensors_saved"] is True,
            "scientific payload belongs to another complete state or operation")
    raw = (base / "state.pt").read_bytes()
    require(len(raw) == record["state_bytes"]
            and hashlib.sha256(raw).hexdigest() == record["state_sha256"],
            "scientific payload bytes changed")
    value = rt.torch.load(io.BytesIO(raw), map_location="cpu", weights_only=False)
    require(rt.v8._tree_digest(value) == record["state_digest"],
            "scientific payload tensor identity changed")
    require(value.get("point_id") == record["point_id"],
            "actual payload point differs from its metadata")
    return value


def _checked_point_values(values, context, state, rt):
    guard = binding.old_module("finqa_v32_same_point_guard")
    require(values["pre_state_digest"] == context["parent_state_digest"]
            and guard.recompute_point_id(state, theta_bar=values["theta_bar"],
                G=values["G"], frozen_runtime=rt) == values["point_id"],
            "new virtual values do not bind this complete actual point")
    return values


def _condition(value, context, point_id):
    temperature = importlib.import_module("finqa_v70_temperature")
    condition = temperature.checked_condition(value)
    require(condition["identity"]["point_id"] == point_id
            and condition["arm"] == "C1" and condition["temperature"] == 1.0
            and condition["denominator"] == 700
            and condition["draw_seeds"] == [101, 103],
            "fresh T1 feedback condition or new virtual point differs")
    return condition


def load_feedback(root, context, state, rt):
    temperature = importlib.import_module("finqa_v70_temperature")
    directory = stage_root(root, context["step"], "virtual_point")
    value = _checked_point_values(read_payload(directory, context, "virtual_point", rt),
                                  context, state, rt)
    condition = _condition(value["condition"], context, value["point_id"])
    expected = directory / "feedback" / condition["id"]
    require(Path(value["feedback_root"]).resolve() == expected.resolve(),
            "old or cross-point feedback cannot be inherited")
    for item in value["feedback_files"].values():
        require(binding.sha(item["path"]) == item["sha256"], "sealed feedback bytes changed")
    cohort, rewards = temperature.read_complete(expected, condition)
    require(rewards == value["rewards"] and cohort.denominator == 700
            and cohort.model_dump(mode="json", exclude={"episodes"}) == value["feedback_seal"],
            "complete T1 cohort/reward binding differs")
    return value, cohort, rewards


def execute_virtual(root, directory, context, state, driver, cache, assets, science, rt,
                    monitor, attempt_root):
    temperature = importlib.import_module("finqa_v70_temperature")
    if (directory / "payload/record.json").exists():
        point, cohort, _rewards = load_feedback(root, context, state, rt)
        return dict(payload=binding.entry(directory / "payload/record.json"),
            point_id=point["point_id"], condition_id=point["condition"]["id"],
            denominator=700, new_feedback_sessions=700, total_feedback_sessions=700,
            new_feedback_calls_in_this_attempt=0,
            new_actual_response_calls=0,
            new_feedback_sessions_is_logical_condition_total_not_new_attempt=True,
            cohort_cumulative_response_calls=sum(episode.actual_model_calls for episode in cohort.episodes),
            completed_payload_reused=True, real_parent_unchanged=True)
    computed = directory / "computed_point"
    if (computed / "payload/record.json").exists():
        point = _checked_point_values(read_payload(computed, context, "computed_point", rt),
                                      context, state, rt)
    else:
        gradients = cache.assemble(device="cuda:0")
        require(len(gradients) == 744, "complete fresh class cache required")
        prepared = rt.v8.prepare_virtual_point(driver.parameters, driver.optimizer,
            gradients, state["pi"], context["mu"])
        guard = binding.old_module("finqa_v32_same_point_guard")
        point_id = guard.recompute_point_id(state, theta_bar=prepared["theta_bar"],
                                            G=prepared["G"], frozen_runtime=rt)
        point = dict(G=_cpu(prepared["G"]), theta_bar=_cpu(prepared["theta_bar"]),
            update=_cpu(prepared["update"]), diagnostics=copy.deepcopy(prepared["diagnostics"]),
            adam_binding_snapshot=copy.deepcopy(prepared["binding"].snapshot),
            point_id=point_id, pre_state_digest=context["parent_state_digest"])
        assert_live_point(driver, context, rt)
        save_payload(computed, point, context, "computed_point", rt)
        del prepared, gradients
        # This stage will never consume class gradients again. Drop only its
        # in-process verified copies; immutable complete-task tensors remain.
        # The next cold distribution worker performs its own strict read.
        cache.verified_state.values.clear()
    monitor.clear_unused("fresh_virtual_point_durably_saved")
    theta = {name: value.to(driver.parameters[name].device)
             for name, value in point["theta_bar"].items()}
    config = temperature.RunConfig.model_validate(science["feedback_config"])
    collector = temperature.LocalFeedbackCollector(snapshot=assets["snapshot"],
        role_plan=assets["role_plan"], root=directory / "feedback",
        config=config.model_copy(update={"temperature": 1.0}),
        model_id=assets["assets"]["base_binding"]["id"], arm="C1", batch=1,
        seeds=(101, 103), attempt_root=Path(attempt_root) / "generation")

    current_return_count = 0

    def event(value):
        nonlocal current_return_count
        # The frozen durable sink emits this only for new provider returns,
        # never for reconstruction of an already persisted returned prefix.
        if value["phase"] == "after_durable_feedback_return":
            current_return_count += 1
        monitor.snapshot("feedback." + value["phase"], boundary=True,
                         feedback_condition_id=value.get("feedback_condition_id"))
        monitor.check_stop("feedback." + value["phase"])

    cohort, rewards = collector.collect(driver.model, driver.tokenizer, theta,
        point_id=point["point_id"], event_sink=event)
    _condition(collector.condition, context, point["point_id"])
    assert_live_point(driver, context, rt)
    attempt_draws = []
    for draw in range(2):
        path = Path(attempt_root) / "generation" / f"draw{draw}" / "result/record.json"
        if path.exists():
            record = checked(path)
            require(record["schema"] == "v56_generation_attempt_result.v1"
                    and record["complete"] is True
                    and type(record["new_actual_model_calls"]) is int
                    and record["new_actual_model_calls"] >= 0,
                    "actual durable draw-attempt call count changed")
            attempt_draws.append((record, binding.entry(path)))
    actual_calls = sum(record["new_actual_model_calls"] for record, _ref in attempt_draws)
    require(actual_calls == current_return_count,
            "new response accounting differs from the actual durable-return events")
    call_accounting = publish(Path(attempt_root) / "feedback_call_accounting/record.json", dict(
        schema="v70_actual_feedback_attempt_calls.v1", point_context_id=context["id"],
        feedback_condition_id=collector.condition["id"], new_actual_response_calls=actual_calls,
        durable_new_return_events=current_return_count,
        draw_attempt_results=[ref for _record, ref in attempt_draws],
        cohort_cumulative_response_calls=sum(ep.actual_model_calls for ep in cohort.episodes),
        logical_condition_sessions=700, old_returned_prefix_calls_counted_as_new=False))
    point.update(condition=collector.condition, feedback_root=str(collector.feedback_root),
        rewards=list(rewards), feedback_seal=cohort.model_dump(mode="json", exclude={"episodes"}),
        computed_point_payload=binding.entry(computed / "payload/record.json"),
        feedback_files={name: binding.file_ref(collector.feedback_root / name) for name in
            ("intent/record.json", "cohort_seal/record.json", "native_rewards/record.json",
             "condition_cohort_binding/record.json", "draw0/generation_seal/seal.json",
             "draw1/generation_seal/seal.json")})
    reference = save_payload(directory, point, context, "virtual_point", rt)
    return dict(payload=reference, point_id=point["point_id"],
        condition_id=collector.condition["id"], denominator=700, new_feedback_sessions=700,
        total_feedback_sessions=700, real_parent_unchanged=True,
        new_feedback_sessions_is_logical_condition_total_not_new_attempt=True,
        new_actual_response_calls=actual_calls, new_feedback_calls_in_this_attempt=actual_calls,
        actual_response_call_accounting=binding.entry(Path(attempt_root) / "feedback_call_accounting/record.json"),
        complete_class_tasks=744, complete_class_rows=4974,
        cohort_cumulative_response_calls=call_accounting["cohort_cumulative_response_calls"])


def execute_replay(root, directory, context, state, driver, rt, monitor):
    temperature = importlib.import_module("finqa_v70_temperature")
    point, cohort, rewards = load_feedback(root, context, state, rt)
    if (directory / "payload/record.json").exists():
        value = read_payload(directory, context, "replay", rt)
        _condition(value["condition"], context, point["point_id"])
        report = value["report"]
        require(report["complete_replay"] is True and report["denominator"] == 700
                and report["gJ_digest"] == rt.v8.parameter_digest(value["gJ"])
                and value["draw_diagnostics_passed"] is True
                and set(value["draw_gJ"]) == {101, 103},
                "complete actual replay and both strict draw diagnostics required")
        return dict(payload=binding.entry(directory / "payload/record.json"),
            point_id=point["point_id"], denominator=700, complete_replay=True,
            replayed_responses=0, completed_payload_reused=True,
            draw_diagnostics_passed=True, real_parent_unchanged=True)
    theta = {name: value.to(driver.parameters[name].device)
             for name, value in point["theta_bar"].items()}
    profile_id = binding.digest(dict(point_context_id=context["id"],
        condition_id=point["condition"]["id"], stage="replay", algorithm="Full"))

    def observe(value):
        monitor.snapshot("replay." + value["phase"], boundary=True,
                         response_backend_observation=value)

    def factory(model, parameters):
        class CapacityCheckedSession(temperature.ReplaySession):
            def __call__(self, model, theta, prompt, targets, **kwargs):
                monitor.guard.prepare_replay_response(self, model, len(prompt), len(targets))
                return super().__call__(model, theta, prompt, targets, **kwargs)
        return CapacityCheckedSession(model, parameters, temperature=1.0,
            condition_id=point["condition"]["id"], profile_id=profile_id,
            resident_kv_budget_bytes=2 * GIB, full_kv_budget_bytes=8 * GIB,
            activation_resident_budget_bytes=16 * GIB, allocated_memory_limit_bytes=76 * GIB,
            free_memory_reserve_bytes=2 * GIB, response_monitor=observe)

    rng_source = dict(checkpoint=dict(path=str(Path(context["parent_checkpoint"]["path"]) / "state.pt"),
        sha256=context["parent_checkpoint"]["state_sha256"]), field="rng",
        digest=rt.v8._tree_digest(state["rng"]))
    components = {}
    monitor.clear_unused("before_fresh_T1_R3_replay")
    with rt.v8.installed_point(driver.model, theta) as installed:
        gJ, report = temperature.feedback_gradient(cohort, rewards, driver.model, installed,
            condition=point["condition"], root=directory / "checkpoints", profile_id=profile_id,
            backend_factory=factory, rng_restore_source=rng_source,
            pause_request=monitor.guard.stop, pause_after_response=None, checkpoint_every=16,
            event_sink=monitor.guard.event_sink, draw_components_out=components,
            mean_tolerances=temperature.MEAN_TOLERANCES, component_monitor=observe)
    require(report["complete_replay"] is True and report["denominator"] == 700
            and report["point_id"] == point["point_id"]
            and report["feedback_condition_id"] == point["condition"]["id"]
            and report["gJ_digest"] == rt.v8.parameter_digest(gJ)
            and set(components) == {101, 103}, "fresh complete T1 replay binding failed")
    assert_live_point(driver, context, rt)
    value = dict(gJ=_cpu(gJ), draw_gJ=components, report=report,
        condition=point["condition"], point_id=point["point_id"], rng_source=rng_source,
        draw_diagnostics_passed=True)
    reference = save_payload(directory, value, context, "replay", rt)
    return dict(payload=reference, point_id=point["point_id"], denominator=700,
        complete_replay=True, responses=report["response_checkpoint_binding"]["response_count"],
        restored_completed_responses=report["restored_completed_responses"],
        draw_diagnostics_passed=True, real_parent_unchanged=True)


def execute_distribution(root, directory, context, state, driver, cache, rt, monitor):
    point, cohort, rewards = load_feedback(root, context, state, rt)
    if (directory / "payload/record.json").exists():
        value = read_payload(directory, context, "distribution", rt)
        _condition(value["condition"], context, point["point_id"])
        require(value["same_point_G_theta_bar_bitwise_equal"] is True
                and value["draw_C_diagnostics"]["mean_comparison_passed"] is True
                and value["applied"] is False, "unverified saved candidate")
        diagnostic = binding.read_ref(value["frozen_diagnostics"])
        require(diagnostic["binding"]["point_context_id"] == context["id"]
                and diagnostic["binding"]["actual_point_id"] == point["point_id"],
                "saved CPU diagnostics belong to another actual point")
        if context["step"] != 894:
            binding.read_ref(value["tracking_diagnostics"])
        training_api.validate_distribution(value["q"], state["pi"])
        return dict(payload=binding.entry(directory / "payload/record.json"),
            point_id=point["point_id"], distribution_digest=rt.v8._tree_digest(value["q"]),
            denominator=700, complete_class_tasks=744, complete_class_rows=4974,
            draw_C_diagnostics_passed=True, real_parent_unchanged=True,
            applied=False, probe_only=context["probe_only"], completed_payload_reused=True)
    replay_root = stage_root(root, context["step"], "replay")
    replay = read_payload(replay_root, context, "replay", rt)
    _condition(replay["condition"], context, point["point_id"])
    require(replay["report"]["complete_replay"] is True
            and replay["report"]["denominator"] == 700
            and replay["draw_diagnostics_passed"] is True, "complete fresh replay required")
    gradients = cache.assemble(device="cuda:0")
    prepared = rt.v8.prepare_virtual_point(driver.parameters, driver.optimizer, gradients,
                                          state["pi"], context["mu"])
    for key in ("G", "theta_bar"):
        require(list(prepared[key]) == list(point[key])
                and all(rt.torch.equal(value.detach().cpu(), point[key][name])
                        for name, value in prepared[key].items()),
                "new point reconstruction differs bitwise from saved " + key)
    require(prepared["binding"].snapshot == point["adam_binding_snapshot"],
            "actual same-point Adam pullback binding changed")
    gJ = {name: value.to(driver.parameters[name].device) for name, value in replay["gJ"].items()}
    controls = [task for task, row in state["prior"].items() if len(row) == 1]
    result = rt.v8.update_distribution(prepared, gradients, gJ, state["pi"], state["prior"],
        context["mu"], feedback_report=replay["report"], contribution_only=False,
        control_tasks=controls, **rt.v8.PARAMETERS)
    q = result["distribution"]["pi_next"]
    training_api.validate_distribution(q, state["pi"])
    q_digest = rt.v8._tree_digest(q)
    draws = reference.draw_contributions(prepared, gradients, replay, result["C"], state,
                                         context, rt, monitor)
    # Diagnostic q uses each real 350-denominator C independently. It never
    # replaces the formal original-order 700-denominator C or its single q.
    from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import distribution
    from trusted_synthesis.finance_research import v6_distribution
    import finqa_v70_diagnostics as diagnostics
    zero = all(reward == 0 for reward in rewards)
    require((result["distribution"].get("status") == "UNINFORMATIVE_FEEDBACK") is zero,
            "formal uninformative branch differs from actual complete rewards")
    draw_zero = {str(seed): all(reward == 0 for ep, reward in zip(cohort.episodes, rewards)
                              if ep.config.seed == seed) for seed in (101, 103)}
    draw_updates = {}
    for seed in ("101", "103"):
        C = draws["C_by_draw"][seed]
        draw_updates[seed] = (v6_distribution.automatic_update(state["pi"], state["prior"], C,
            context["mu"], arm="Full", feedback_all_zero=True) if draw_zero[seed] else
            distribution.anchored_update(state["pi"], state["prior"], C, context["mu"],
                contribution_only=False, control_tasks=controls, **rt.v8.PARAMETERS))
    diagnostic = diagnostics.analyze_frozen_point(current=state["pi"], prior=state["prior"],
        mu=context["mu"], formal_update=result["distribution"], draw_updates=draw_updates,
        feedback_all_zero=zero, draw_feedback_all_zero=draw_zero,
        binding=dict(point_context_id=context["id"], parent_state_digest=context["parent_state_digest"],
            actual_point_id=point["point_id"], feedback_condition_id=point["condition"]["id"],
            replay_payload=binding.entry(replay_root / "payload/record.json"),
            C_digest=binding.digest(result["C"]), formal_denominator=700, draw_denominator=350))
    publish(directory / "frozen_diagnostics/record.json", diagnostic)
    tracking = None
    if context["step"] != 894:
        previous_step = 894 if context["step"] == 1192 else 1192
        previous = checked(stage_root(root, previous_step, "distribution") /
                           "frozen_diagnostics/record.json")
        publish(directory / "tracking_diagnostics/record.json",
                diagnostics.compare_frozen_points(previous, diagnostic))
        tracking = binding.entry(directory / "tracking_diagnostics/record.json")
    require(rt.v8._tree_digest(q) == q_digest, "CPU diagnostics changed the formal candidate")
    assert_live_point(driver, context, rt)
    value = dict(q=q, C=result["C"], pullback=_cpu(result["a"]),
        evidence={key: copy.deepcopy(item) for key, item in result.items() if key != "a"},
        condition=point["condition"], point_id=point["point_id"],
        same_point_G_theta_bar_bitwise_equal=True, draw_C_diagnostics=draws,
        draw_distribution_updates=draw_updates, feedback_all_zero=zero,
        diagnostic_draw_candidates_computed=True,
        draw_feedback_all_zero=draw_zero, applied=False, probe_only=context["probe_only"],
        frozen_diagnostics=binding.entry(directory / "frozen_diagnostics/record.json"),
        tracking_diagnostics=tracking)
    reference_payload = save_payload(directory, value, context, "distribution", rt)
    return dict(payload=reference_payload, point_id=point["point_id"],
        distribution_digest=q_digest, denominator=700, complete_class_tasks=744,
        complete_class_rows=4974, draw_C_diagnostics_passed=True, real_parent_unchanged=True,
        applied=False, probe_only=context["probe_only"], optimizer_updates=0,
        feedback_all_zero=zero, frozen_diagnostics=value["frozen_diagnostics"])


def execute(root, job, attempt_root, guard):
    """Run one already admitted cold stage and release all model references."""
    expected = job_spec(job["step"], job["stage"])
    require(all(job.get(key) == value for key, value in expected.items()
                if key not in ("id", "job_id")), "job differs from the single V70 path")
    step, stage = job["step"], job["stage"]
    directory = stage_root(root, step, stage)
    training, rt = training_api.runtime()
    # Import once before actual training RNG restore; never repair RNG after
    # science to conceal a mutation.
    for name in ("finqa_v70_temperature", "finqa_v70_diagnostics",
                 "finqa_v34_tail_memory", "finqa_v32_same_point_guard",
                 "trusted_synthesis.finance_research.v6_distribution",
                 "trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.trajectory_consumer",
                 "trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.optimizer_pullback",
                 "trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.distribution"):
        importlib.import_module(name)
    context, state = training_api.load_point(root, step, rt)
    science, pool, _prefix, assets = training.checked_launch(context["training_root"])
    require(context["protocol_id"] == guard.protocol["id"], "resource/scientific protocol differs")
    monitor = ScientificMonitor(guard, cooperative_replay=stage == "replay")
    cache = training_api.load_cache(root, context, rt) if stage.startswith("shard") or stage in (
        "virtual_point", "distribution") else None
    monitor.check_stop("before_actual_model_load")
    model, tokenizer, optimizer, scope, _fresh = rt.launcher._load_components(assets, SEED)
    driver_root = Path(root) / "training" if stage == "train" else directory / "unused_training"
    driver = training.adapters().TrainingDriver(model, optimizer, pool, root=driver_root,
        seed=SEED, arm=state["arm"], device="cuda:0", tokenizer=tokenizer,
        adapter_scope=scope, feedback_collector=None)
    driver.restore(context["parent_checkpoint"]["path"])
    assert_live_point(driver, context, rt)
    monitor.clear_unused("after_exact_real_model_Adam_RNG_pi_restore")
    if stage.startswith("shard"):
        body = original.execute_shard(directory, context, stage, driver, pool, cache, rt, monitor)
        assigned = cache.plan["assignments"][int(stage[-2:])]
        body.update(assigned_tasks=len(assigned["task_ids"]), assigned_rows=assigned["row_count"],
                    complete_class_tasks=len(assigned["task_ids"]),
                    complete_class_rows=assigned["row_count"], real_parent_unchanged=True)
    elif stage == "virtual_point":
        body = execute_virtual(root, directory, context, state, driver, cache, assets,
                               science, rt, monitor, attempt_root)
    elif stage == "replay":
        body = execute_replay(root, directory, context, state, driver, rt, monitor)
    elif stage == "distribution":
        body = execute_distribution(root, directory, context, state, driver, cache, rt, monitor)
    else:
        source = stage_root(root, step, "distribution")
        distribution = read_payload(source, context, "distribution", rt)
        require(distribution["applied"] is False and distribution["probe_only"] is False,
                "training requires an unapplied nonterminal Full candidate")
        completed = directory / "completed/record.json"
        if completed.exists():
            result = checked(completed)
            training_api.restore_completed_window(context, result, driver, distribution["q"], rt)
        else:
            result = training_api.execute_training(root, context, state, driver,
                distribution["q"], rt=rt, monitor=monitor,
                distribution_source=binding.entry(source / "payload/record.json"),
                resource_report=guard.report)
        body = dict(branch_result=binding.entry(completed), point_id=distribution["point_id"],
            initial_step=step, final_step=result["final_step"], optimizer_updates=298,
            new_optimizer_updates=298, outer_updates=1, applied=True,
            final_checkpoint=result["final_checkpoint"])
    monitor.clear_unused("scientific_stage_complete")
    del driver, model, tokenizer, optimizer, pool, cache, state
    gc.collect()
    rt.torch.cuda.empty_cache()
    monitor.snapshot("after_model_release", boundary=True)
    return dict(body, point_context_id=context["id"],
                parent_state_digest=context["parent_state_digest"], seed=SEED, step=step, stage=stage,
                algorithm="Full", temperature=1.0, model_released=True)
