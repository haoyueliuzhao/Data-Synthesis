"""One C-only initialized, explicitly Full, two-window continuation.

The original checkpoint is restored before the single declared arm transition.
Only this module commits the two new outer applications. The inherited SFT step
is unchanged and its automatic outer dispatcher is never called.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

import finqa_v70_binding as binding

binding.install_scientific_paths()
original = binding.old_module("finqa_v54_training")
records = binding.old_module("finqa_v37_task_cache")
task_cache = binding.old_module("finqa_v35_task_cache")

ROOT, POINTS, SEED = binding.ROOT, (894, 1192, 1490), 137
WINDOWS = {894: 1192, 1192: 1490}
require, checked, publish = binding.require, binding.checked, binding.publish
runtime = original.runtime
checkpoint_ref, read_checkpoint = original.checkpoint_ref, original.read_checkpoint
validate_distribution = original.validate_distribution


def point_root(root, step):
    require(Path(root).resolve() == ROOT.resolve() and step in POINTS,
            "unregistered V70 actual point")
    return Path(root) / "points" / f"step{step:04d}"


def initial_checkpoint():
    path = binding.SOURCE_ROOT / "branches/seed137/C1/completed/record.json"
    result = checked(path)
    require(result["status"] == "COMPLETE" and result["seed"] == 137
            and result["arm"] == "C1" and result["feedback_batch"] == 1
            and result["end_step"] == 894 and result["next_outer894_executed"] is False,
            "the accepted seed137 C1 b1 endpoint is required")
    return result["snapshots"]["894"]


def expected_outer_history(step):
    # The b1 parent applied its 596 q through a branch commit, not an outer
    # commit. Do not invent or backfill a 596 entry in its historical state.
    return [298] + [coordinate for coordinate in WINDOWS if coordinate < step]


def validate_point_state(state, step, rt):
    require(step in POINTS and (state["seed"], state["step"]) == (SEED, step)
            and state["arm"] == ("C-only" if step == 894 else "Full")
            and state["outer_done"] == expected_outer_history(step),
            "actual point arm, coordinate or unmodified outer history differs")
    require(state["model_training"] is True and state["optimizer"]["state"]
            and state["rng"]["cuda"], "complete actual Adam/training RNG is required")
    for value in state["optimizer"]["state"].values():
        require(set(value) >= {"step", "exp_avg", "exp_avg_sq"}
                and int(value["step"].item()) == step,
                "Adam moments or actual optimizer cursor differ")
    require(len(state["pi"]) == len(state["prior"]) == 744
            and state["execution_plan"]["outer_steps"] == [298, 596, 894, 1192]
            and state["execution_plan"]["final_step"] == 1490,
            "original support or ten-epoch schedule changed")
    validate_distribution(state["pi"], state["prior"])
    return state


def prepare_point(root, step, protocol_id, checkpoint_reference=None, training_root=None):
    """CPU registration of one real point; never inherit a class tensor cache."""
    directory = point_root(root, step)
    destination = directory / "context/record.json"
    if destination.exists():
        point = checked_point(root, step)
        require(point["protocol_id"] == protocol_id
                and (checkpoint_reference is None
                     or point["parent_checkpoint"] == checkpoint_reference),
                "existing point registration belongs to another protocol/state")
        return point
    training, rt = runtime()
    inherited = checked(binding.SOURCE_ROOT / "parents/seed137/record.json")
    require(training_root is None or Path(training_root).resolve()
            == Path(inherited["training_root"]).resolve(), "foreign original material launch")
    training_root = Path(inherited["training_root"])
    science, pool, _prefix, _assets = training.checked_launch(training_root)
    reference = (initial_checkpoint() if step == 894 else
                 checkpoint_ref(Path(root) / "training" / f"step{step:04d}_step"))
    require(checkpoint_reference is None or checkpoint_reference == reference,
            "new point must use the registered preceding endpoint")
    state = validate_point_state(read_checkpoint(reference, rt), step, rt)
    require(state["pool_id"] == pool.cache_id
            and state["schedule"] == training.build_task_schedule(pool.task_ids, SEED)
            and state["prior"] == pool._manifest.registration.pi0,
            "actual material, original task schedule or prior changed")
    if step > 894:
        preceding = next(start for start, end in WINDOWS.items() if end == step)
        completed = checked(point_root(root, preceding) / "train/completed/record.json")
        require(completed["final_checkpoint"] == reference
                and completed["optimizer_updates"] == 298
                and completed["outer_updates"] == 1,
                "next actual point requires its complete preceding window")
    spec = [dict(name=name, shape=list(value.shape), dtype=str(value.dtype))
            for name, value in state["parameters"].items()]
    plan = task_cache.make_task_plan(pool, spec, shards=4)
    require((len(plan["task_ids"]), plan["state_count"], plan["package_count"],
             plan["row_count"]) == (744, 1360, 2468, 4974),
            "fresh class pass must retain the complete original support")
    publish(directory / "task_plan/record.json", plan)
    sources = dict(driver=binding.file_ref(rt.v8.__file__),
                   frozen_training=binding.file_ref(training.__file__),
                   class_memory=binding.file_ref(binding.old_module("finqa_v34_tail_memory").__file__),
                   task_cache=binding.file_ref(task_cache.__file__))
    state_digest = rt.v8._tree_digest(state)
    components = {name: rt.v8._tree_digest(state[name]) for name in records.COMPONENTS}
    class_binding = dict(schema="v37_actual_outer_task_gradient_binding.v1",
        protocol_id=protocol_id, seed=SEED, arm="Full", checkpoint_arm=state["arm"], step=step,
        checkpoint=reference, pre_state_digest=state_digest, component_digest=components,
        pool_id=pool.cache_id, task_plan_id=plan["id"], parameter_spec=spec,
        branch=dict(contribution_only=False, b_N=0.2, parameters=rt.v8.PARAMETERS),
        numerical_sources=sources, cross_parameter_point_reuse=False)
    return publish(destination, dict(schema="v70_actual_continuous_point.v1",
        protocol_id=protocol_id, seed=SEED, step=step, algorithm="Full", temperature=1.0,
        parent_checkpoint=reference, parent_state_digest=state_digest,
        pre_state_digest=state_digest, checkpoint_arm=state["arm"],
        outer_done=list(state["outer_done"]), parent_pi=copy.deepcopy(state["pi"]),
        prior=copy.deepcopy(state["prior"]), mu=copy.deepcopy(pool._manifest.registration.mu),
        component_digests=components, pool_id=pool.cache_id, parameter_spec=spec,
        task_plan=binding.entry(directory / "task_plan/record.json"), task_binding=class_binding,
        task_cache_root=str(directory / "task_cache"), old_class_context=None,
        training_root=str(training_root), scientific_sources=sources,
        fresh_complete_class_required=True, cross_parameter_point_cache_reuse=False,
        original_outer_history_not_rewritten=True, probe_only=step == 1490,
        initialization_from_C_only=step == 894, new_training_arm="Full",
        original_schedule_sha256=state["schedule"]["schedule_sha256"]))


def checked_point(root, step):
    directory = point_root(root, step)
    point = checked(directory / "context/record.json")
    require(point["schema"] == "v70_actual_continuous_point.v1"
            and point["seed"] == SEED and point["step"] == step
            and point["algorithm"] == "Full" and point["temperature"] == 1.0
            and point["probe_only"] is (step == 1490)
            and point["task_cache_root"] == str(directory / "task_cache")
            and point["task_binding"]["pre_state_digest"] == point["parent_state_digest"]
            and point["cross_parameter_point_cache_reuse"] is False,
            "V70 point context binding changed")
    return point


def load_point(root, step, rt):
    point = checked_point(root, step)
    state = validate_point_state(read_checkpoint(point["parent_checkpoint"], rt), step, rt)
    require(rt.v8._tree_digest(state) == point["parent_state_digest"],
            "actual point complete state differs from its context")
    return point, state


def load_cache(root, point, rt):
    directory = point_root(root, point["step"])
    plan = binding.read_ref(point["task_plan"])
    return records.ProductionTaskCache(directory / "task_cache", point["task_binding"],
        plan, point["parameter_spec"], rt, original_cache_module=task_cache)


def configure_fixed_window(driver, start):
    require(start in WINDOWS, "terminal probe cannot open a training window")
    driver.outer_steps = ()
    driver.final_step = WINDOWS[start]


def latest_window_checkpoint(directory, start):
    require(start in WINDOWS, "probe has no training checkpoint")
    end = WINDOWS[start]
    found = []
    for path in Path(directory).glob("step*_*"):
        match = re.fullmatch(r"step(\d{4})_(outer|step)", path.name)
        require(match is not None and path.is_dir(), "unexpected continuous training entry")
        coordinate, phase = int(match[1]), match[2]
        require((phase == "outer" and coordinate in WINDOWS)
                or (phase == "step" and 895 <= coordinate <= 1490),
                "continuous training escaped the registered two windows")
        require((path / "record.json").is_file() and (path / "state.pt").is_file(),
                "partial training checkpoint is not a resume boundary")
        if coordinate == start and phase == "outer" or start < coordinate <= end:
            found.append((coordinate, phase == "step", path))
    return max(found, key=lambda row: row[:2])[2] if found else None


def restore_completed_window(point, completed, driver, q, rt):
    """A result record alone is not a cold actual-state acceptance waiver."""
    start = point["step"]
    require(start in WINDOWS and completed["point_context_id"] == point["id"]
            and completed["protocol_id"] == point["protocol_id"]
            and completed["status"] == "COMPLETE"
            and completed["initial_step"] == start and completed["final_step"] == WINDOWS[start]
            and completed["optimizer_updates"] == completed["new_optimizer_updates"] == 298
            and completed["outer_updates"] == 1
            and completed["distribution_digest"] == rt.v8._tree_digest(q),
            "completed window metadata differs from the registered state or dose")
    reference = completed["final_checkpoint"]
    require(checkpoint_ref(reference["path"]) == reference,
            "completed actual endpoint metadata changed")
    configure_fixed_window(driver, start)
    driver.arm = "Full"
    driver.restore(reference["path"])
    require(driver.step_index == WINDOWS[start] and driver.pi == q
            and driver.outer_done == [*point["outer_done"], start]
            and rt.v8._tree_digest(driver._payload()) == reference["actual_state_digest"],
            "completed actual theta/Adam/RNG/pi endpoint did not restore exactly")
    return completed


def execute_training(root, point, state, driver, q, *, rt, monitor, distribution_source,
                     resource_report=None):
    start = point["step"]
    require(start in WINDOWS and not point["probe_only"],
            "1490 is a candidate-only probe; applying it is forbidden")
    end = WINDOWS[start]
    validate_distribution(q, state["pi"])
    directory = point_root(root, start) / "train"
    require(driver.root.resolve() == (Path(root) / "training").resolve(),
            "continuous SFT cannot write an old branch")
    contract = dict(schema="v70_fixed_q_window_binding.v1", protocol_id=point["protocol_id"],
        point_context_id=point["id"], parent_state_digest=point["parent_state_digest"],
        seed=SEED, arm="Full", start_step=start, end_step=end,
        distribution_digest=rt.v8._tree_digest(q), distribution_source=distribution_source,
        parent_training_rng_digest=point["component_digests"]["rng"],
        original_task_schedule_sha256=point["original_schedule_sha256"],
        outer_schedule_during_window=[], optimizer_updates=298, task_exposures=1488,
        initial_checkpoint_arm=state["arm"], explicit_C_only_to_Full_transition=start == 894)
    publish(directory / "binding/record.json", contract)
    completed = directory / "completed/record.json"
    require(not completed.exists(), "completed window cannot execute again")
    latest = latest_window_checkpoint(driver.root, start)
    configure_fixed_window(driver, start)
    history = [*state["outer_done"], start]
    if latest is None:
        require(rt.v8._tree_digest(driver._payload()) == point["parent_state_digest"],
                "Full transition requires exact real parent restoration first")
        monitor.check_stop("before_explicit_Full_outer_commit", step=start)
        driver.arm = "Full"
        driver.pi = copy.deepcopy(q)
        driver.outer_done = history
        payload = driver._payload()
        for name in records.COMPONENTS:
            if name not in ("pi", "outer_done"):
                require(rt.v8._tree_digest(payload[name]) == rt.v8._tree_digest(state[name]),
                        "distribution application changed real component " + name)
        driver.commit("outer", dict(**contract, optimizer_steps_performed=0,
            explicit_applied_update=True, original_driver_outer_update_called=False,
            parent_checkpoint_arm=state["arm"], checkpoint_arm="Full"))
    else:
        driver.arm = "Full"
        driver.restore(latest)
        require(driver.pi == q and driver.outer_done == history
                and start <= driver.step_index <= end,
                "durable continuous window state or q changed")
    began = driver.step_index
    while driver.step_index < end:
        monitor.check_stop("before_real_sft_update", step=driver.step_index + 1)
        report = driver.step()
        require(driver.pi == q and driver.outer_done == history
                and report["optimizer_step_calls"] == report["clip_calls"] == 1,
                "fixed q, original optimizer dose or outer history changed")
        monitor.clear_unused("sft_committed_step%04d" % driver.step_index)
    reference = checkpoint_ref(driver.root / f"step{end:04d}_step")
    return publish(completed, dict(schema="v70_continuous_window_complete.v1",
        status="COMPLETE", protocol_id=point["protocol_id"], point_context_id=point["id"],
        seed=SEED, arm="Full", initial_step=start, final_step=end,
        optimizer_updates=298, new_optimizer_updates=298, task_exposures=1488,
        outer_updates=1, outer_checkpoint=checkpoint_ref(driver.root / f"step{start:04d}_outer"),
        final_checkpoint=reference, snapshots={str(end): reference},
        distribution_digest=contract["distribution_digest"],
        updates_in_final_worker=end - began, next_outer_automatically_executed=False,
        training_binding=binding.entry(directory / "binding/record.json"),
        resources=resource_report() if resource_report else None))
