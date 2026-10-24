"""One exact V70 parent continued under its actual step894 distribution.

The native SFT step, Adam, batch schedule and checkpoint format are inherited.
No outer is applied: the native checkpoint arm remains C-only, while the new
experimental condition is named Fixed894. The historic outer_done=[298] is
retained literally. Runtime outer dispatch is disabled without rewriting the
saved original execution plan.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import finqa_v71_binding as binding

binding.install_scientific_paths()
original = binding.old_module("finqa_v54_training")
records = binding.old_module("finqa_v37_task_cache")
ROOT, SEED = binding.ROOT, 137
POINTS, WINDOWS = (894, 1192, 1490), {894: 1192, 1192: 1490}
ARM, CONDITION = "Fixed894", "fixed_pi894"
require, checked, publish = binding.require, binding.checked, binding.publish
runtime = original.runtime
checkpoint_ref, read_checkpoint = original.checkpoint_ref, original.read_checkpoint
validate_distribution = original.validate_distribution
FIXED_COMPONENTS = ("seed", "arm", "pool_id", "schedule", "execution_plan", "prior",
                    "adapter_binding", "frozen_base_digest", "pi", "outer_done")


def point_root(root, step):
    require(Path(root).resolve() == ROOT.resolve() and step in POINTS,
            "unregistered V71 fixed-distribution coordinate")
    return Path(root) / "points" / f"step{step:04d}"


def initial_checkpoint():
    """Use the point bound by V70, never latest-checkpoint discovery."""
    context = checked(binding.V70_ROOT / "points/step0894/context/record.json")
    require(context["schema"] == "v70_actual_continuous_point.v1"
            and context["seed"] == 137 and context["step"] == 894
            and context["checkpoint_arm"] == "C-only"
            and context["outer_done"] == [298]
            and context["initialization_from_C_only"] is True,
            "V70 original actual parent binding differs")
    reference = context["parent_checkpoint"]
    require(Path(reference["path"]).resolve() == (binding.SOURCE_ROOT /
            "branches/seed137/C1/training/step0894_step").resolve()
            and reference["step"] == 894 and reference["phase"] == "step"
            and reference["actual_state_digest"] == context["parent_state_digest"],
            "fixed-distribution control must use V70's exact original parent")
    return reference


def validate_point_state(state, step, rt):
    require(step in POINTS and (state["seed"], state["step"], state["arm"])
            == (SEED, step, "C-only") and state["outer_done"] == [298],
            "fixed branch coordinate or original outer history changed")
    require(state["model_training"] is True and state["optimizer"]["state"]
            and state["rng"]["cuda"], "complete actual Adam/training RNG required")
    for value in state["optimizer"]["state"].values():
        require(set(value) >= {"step", "exp_avg", "exp_avg_sq"}
                and int(value["step"].item()) == step,
                "actual Adam cursor or moments differ")
    require(len(state["pi"]) == len(state["prior"]) == 744
            and state["execution_plan"]["outer_steps"] == [298, 596, 894, 1192]
            and state["execution_plan"]["final_step"] == 1490,
            "original support or ten-epoch schedule changed")
    validate_distribution(state["pi"], state["prior"])
    return state


def assert_fixed_state(state, context, rt):
    require(state["pi"] == context["fixed_pi"]
            and rt.v8._tree_digest(state["pi"]) == context["fixed_pi_digest"]
            and state["outer_done"] == [298] and state["arm"] == "C-only",
            "actual pi0 or original outer history changed")
    for name, expected in context["fixed_component_digests"].items():
        require(rt.v8._tree_digest(state[name]) == expected,
                "fixed parent component changed: " + name)
    return state


def prepare_initial(root, protocol_id):
    return prepare_window(root, 894, protocol_id)


def _accepted_previous_window(root, protocol_id):
    path = point_root(root, 894) / "train/accepted/record.json"
    accepted = checked(path)
    actual = binding.read_ref(accepted["actual_exit"])
    result = binding.read_ref(accepted["result"])
    require(accepted["protocol_id"] == actual["protocol_id"] == result["protocol_id"] == protocol_id
            and accepted["job_id"] == actual["job_id"] == result["job_id"] == "step894.train"
            and accepted["actual_exit_zero"] is True and accepted["resources_passed"] is True
            and actual["actual_waitpid_observed"] is True and actual["returncode"] == 0
            and accepted["result_id"] == result["id"]
            and result["final_step"] == 1192 and result["optimizer_updates"] == 298
            and result["outer_updates"] == 0,
            "second window requires previous training accepted actual exit zero")
    return binding.entry(path)


def prepare_window(root, start, protocol_id):
    require(start in WINDOWS, "only two fixed training windows are registered")
    protocol = checked(Path(root) / "protocol/record.json")
    require(protocol["id"] == protocol_id, "fixed window protocol identity differs")
    predecessor = _accepted_previous_window(root, protocol_id) if start == 1192 else None
    directory = point_root(root, start)
    destination = directory / "context/record.json"
    if destination.exists():
        result = checked_window(root, start)
        require(result["protocol_id"] == protocol_id, "existing fixed window protocol differs")
        return result
    training, rt = runtime()
    old = checked(binding.V70_ROOT / "points/step0894/context/record.json")
    reference = initial_checkpoint() if start == 894 else checkpoint_ref(
        Path(root) / "training" / f"step{start:04d}_step")
    state = validate_point_state(read_checkpoint(reference, rt), start, rt)
    science, pool, _prefix, _assets = training.checked_launch(Path(old["training_root"]))
    require(state["pool_id"] == pool.cache_id == old["pool_id"]
            and state["schedule"] == training.build_task_schedule(pool.task_ids, SEED)
            and state["prior"] == pool._manifest.registration.pi0
            and state["schedule"]["schedule_sha256"] == old["original_schedule_sha256"],
            "actual material, prior or exact original task schedule changed")
    if start == 894:
        require(rt.v8._tree_digest(state) == old["parent_state_digest"]
                and state["pi"] == old["parent_pi"]
                and reference == protocol["initial_parent"]["checkpoint"]
                and rt.v8._tree_digest(state) == protocol["initial_parent"]["source_state_digest"]
                and rt.v8._tree_digest(state["pi"]) == protocol["initial_parent"]["distribution_digest"],
                "initial full theta/Adam/RNG/pi must match V70's actual parent")
        fixed = {name: rt.v8._tree_digest(state[name]) for name in FIXED_COMPONENTS}
        pi = copy.deepcopy(state["pi"])
        initial_reference = reference
    else:
        initial = checked_window(root, 894)
        assert_fixed_state(state, initial, rt)
        previous = checked(point_root(root, 894) / "train/completed/record.json")
        require(previous["final_checkpoint"] == reference
                and previous["optimizer_updates"] == 298 and previous["outer_updates"] == 0,
                "second fixed window requires its actual completed first endpoint")
        fixed, pi = initial["fixed_component_digests"], initial["fixed_pi"]
        initial_reference = initial["initial_checkpoint"]
    batches = state["schedule"]["batches"][start:WINDOWS[start]]
    require(len(batches) == 298 and sum(len(row["task_ids"]) for row in batches) == 1488
            and sorted(len(row["task_ids"]) for row in batches) == [4, 4] + [5] * 296,
            "window must retain its 298 real batches including both four-task tails")
    return publish(destination, dict(schema="v71_fixed_distribution_window.v1",
        protocol_id=protocol_id, seed=SEED, arm=ARM, condition=CONDITION,
        checkpoint_arm="C-only", step=start, final_step=WINDOWS[start],
        parent_checkpoint=reference, initial_checkpoint=initial_reference,
        parent_state_digest=rt.v8._tree_digest(state), parent_pi=copy.deepcopy(pi),
        fixed_pi=copy.deepcopy(pi), fixed_pi_digest=rt.v8._tree_digest(pi),
        prior=copy.deepcopy(state["prior"]), outer_done=[298],
        fixed_component_digests=fixed,
        component_digests={name: rt.v8._tree_digest(state[name]) for name in records.COMPONENTS},
        pool_id=pool.cache_id, original_schedule_sha256=state["schedule"]["schedule_sha256"],
        window_task_batches=copy.deepcopy(batches), window_task_exposures=1488,
        training_root=old["training_root"], original_v70_context=binding.entry(
            binding.V70_ROOT / "points/step0894/context/record.json"),
        previous_training_accepted_actual_exit=predecessor,
        scientific_sources=dict(driver=binding.file_ref(rt.v8.__file__),
                                frozen_training=binding.file_ref(training.__file__)),
        new_outer_updates=0, automatic_outer_disabled=True,
        original_outer_history_not_rewritten=True, new_feedback_sessions=0,
        new_class_passes=0, new_response_replay=0, new_VJP=0))


def checked_window(root, start):
    require(start in WINDOWS, "unregistered fixed training window")
    point = checked(point_root(root, start) / "context/record.json")
    require(point["schema"] == "v71_fixed_distribution_window.v1"
            and (point["seed"], point["step"], point["final_step"])
            == (SEED, start, WINDOWS[start])
            and point["arm"] == ARM and point["condition"] == CONDITION
            and point["checkpoint_arm"] == "C-only" and point["outer_done"] == [298]
            and point["new_outer_updates"] == 0 and point["automatic_outer_disabled"] is True
            and point["parent_pi"] == point["fixed_pi"],
            "fixed-distribution window context changed")
    return point


def load_window(root, start, rt):
    context = checked_window(root, start)
    state = validate_point_state(read_checkpoint(context["parent_checkpoint"], rt), start, rt)
    require(rt.v8._tree_digest(state) == context["parent_state_digest"],
            "complete actual fixed-window starting state differs")
    return context, assert_fixed_state(state, context, rt)


def configure_fixed_window(driver, start):
    require(start in WINDOWS, "no training past1490 is registered")
    driver.outer_steps = ()
    driver.final_step = WINDOWS[start]


def latest_window_checkpoint(directory, start):
    require(start in WINDOWS, "unregistered fixed window")
    found = []
    for path in Path(directory).glob("step*_*"):
        match = re.fullmatch(r"step(\d{4})_step", path.name)
        require(match is not None and path.is_dir(),
                "fixed-distribution control forbids all new outer or foreign checkpoints")
        coordinate = int(match[1])
        require(895 <= coordinate <= 1490, "training escaped its exact596-update dose")
        require((path / "record.json").is_file() and (path / "state.pt").is_file(),
                "partial checkpoint is not a durable resume boundary")
        if start < coordinate <= WINDOWS[start]:
            found.append((coordinate, path))
    return max(found)[1] if found else None


def _contract(point):
    return dict(schema="v71_fixed_pi_window_binding.v1", protocol_id=point["protocol_id"],
        point_context_id=point["id"], parent_state_digest=point["parent_state_digest"],
        seed=SEED, arm=ARM, checkpoint_arm="C-only", condition=CONDITION,
        start_step=point["step"], end_step=WINDOWS[point["step"]],
        distribution_digest=point["fixed_pi_digest"], fixed_pi_digest=point["fixed_pi_digest"],
        parent_training_rng_digest=point["component_digests"]["rng"],
        original_task_schedule_sha256=point["original_schedule_sha256"],
        outer_schedule_during_window=[], optimizer_updates=298, task_exposures=1488,
        outer_updates=0, original_outer_done=[298], initial_checkpoint=point["initial_checkpoint"],
        reinitialize_training_rng_after_restore=False)


def _check_step_report(report, point, step):
    expected = point["window_task_batches"][step - point["step"] - 1]
    require(report["optimizer_step_calls"] == report["clip_calls"] == 1
            and report["actual_parameter_update"] is True and report["CPU_control_only"] is False
            and report["execution_design"] == "original_unfused_response_rows_v18"
            and report["supervision_policy"] == "v14_state_independent_original_span_union.v1"
            and report["additional_batch_division"] is False
            and report["additional_loss_scaling"] is False
            and report["task_batch"]["task_ids"] == expected["task_ids"]
            and report["task_batch"]["step"] == step
            and report["task_batch"]["schedule_id"] == point["original_schedule_sha256"],
            "actual optimizer, original loss/mask or task batch order differs")


def _window_receipts(root, point, through):
    refs = []
    for step in range(point["step"] + 1, through + 1):
        path = Path(root) / "training" / f"step{step:04d}_step/record.json"
        record = json.loads(path.read_bytes())
        require((record["step"], record["phase"], record["arm"], record["seed"])
                == (step, "step", "C-only", SEED)
                and record["pool_id"] == point["pool_id"]
                and record["schedule_sha256"] == point["original_schedule_sha256"]
                and record["checkpoint_contains_actual_model_Adam_RNG_pi"] is True
                and (path.parent / "state.pt").is_file(),
                "actual training receipt or complete checkpoint missing")
        _check_step_report(record["evidence"], point, step)
        refs.append(dict(step=step, record=binding.file_ref(path),
                         state_sha256=record["state_sha256"],
                         actual_state_digest=record["actual_state_digest"],
                         update_id=record["evidence"]["id"]))
    return refs


def execute_training(root, point, state, driver, *, rt, monitor, resource_report=None):
    start = point["step"]
    require(start in WINDOWS and driver.root.resolve() == (Path(root) / "training").resolve(),
            "fixed training must remain in its independent two-window branch")
    end = WINDOWS[start]
    directory = point_root(root, start) / "train"
    publish(directory / "binding/record.json", _contract(point))
    completed = directory / "completed/record.json"
    require(not completed.exists(), "completed fixed window cannot execute again")
    configure_fixed_window(driver, start)
    latest = latest_window_checkpoint(driver.root, start)
    if latest is None:
        require(rt.v8._tree_digest(driver._payload()) == point["parent_state_digest"],
                "training requires the exact real parent Adam/RNG restoration")
    else:
        driver.restore(latest)
    actual = driver._payload()
    assert_fixed_state(actual, point, rt)
    require(start <= driver.step_index <= end and driver.arm == "C-only",
            "durable fixed branch cursor or checkpoint arm differs")
    began = driver.step_index
    while driver.step_index < end:
        monitor.check_stop("before_real_fixed_sft_update", step=driver.step_index + 1)
        require(driver.outer_steps == () and driver.pi == point["fixed_pi"]
                and driver.outer_done == [298], "automatic outer or actual pi0 changed")
        report = driver.step()
        _check_step_report(report, point, driver.step_index)
        require(driver.pi == point["fixed_pi"] and driver.outer_done == [298],
                "fixed distribution or original history changed during SFT")
        monitor.clear_unused("fixed_sft_committed_step%04d" % driver.step_index)
    final_state = driver._payload()
    validate_point_state(final_state, end, rt)
    assert_fixed_state(final_state, point, rt)
    reference = checkpoint_ref(driver.root / f"step{end:04d}_step")
    require(reference["actual_state_digest"] == rt.v8._tree_digest(final_state),
            "live final model/Adam/RNG does not match actual committed endpoint")
    ledger = _window_receipts(root, point, end)
    return publish(completed, dict(schema="v71_fixed_distribution_window_complete.v1",
        status="COMPLETE", protocol_id=point["protocol_id"], point_context_id=point["id"],
        seed=SEED, arm=ARM, checkpoint_arm="C-only", condition=CONDITION,
        initial_step=start, final_step=end, optimizer_updates=298, new_optimizer_updates=298,
        task_exposures=1488, outer_updates=0, outer_done=[298], fixed_distribution=True,
        final_checkpoint=reference, snapshots={str(end): reference},
        distribution_digest=point["fixed_pi_digest"], fixed_distribution_digest=point["fixed_pi_digest"],
        initial_checkpoint=point["initial_checkpoint"], update_receipts=ledger,
        updates_in_final_worker=end - began, next_outer_automatically_executed=False,
        training_binding=binding.entry(directory / "binding/record.json"),
        resources=resource_report() if resource_report else None))


def _validate_completed(point, completed):
    require(completed["schema"] == "v71_fixed_distribution_window_complete.v1"
            and completed["status"] == "COMPLETE"
            and completed["point_context_id"] == point["id"]
            and completed["protocol_id"] == point["protocol_id"]
            and (completed["initial_step"], completed["final_step"])
            == (point["step"], WINDOWS[point["step"]])
            and completed["optimizer_updates"] == completed["new_optimizer_updates"] == 298
            and completed["task_exposures"] == 1488 and completed["outer_updates"] == 0
            and completed["outer_done"] == [298] and completed["arm"] == ARM
            and completed["fixed_distribution"] is True
            and completed["distribution_digest"] == point["fixed_pi_digest"],
            "completed fixed window metadata or dose differs")
    return completed


def restore_completed_window(point, completed, driver, rt):
    _validate_completed(point, completed)
    reference = completed["final_checkpoint"]
    require(checkpoint_ref(reference["path"]) == reference, "complete actual endpoint metadata changed")
    configure_fixed_window(driver, point["step"])
    driver.restore(reference["path"])
    payload = driver._payload()
    validate_point_state(payload, WINDOWS[point["step"]], rt)
    assert_fixed_state(payload, point, rt)
    require(driver.step_index == WINDOWS[point["step"]]
            and rt.v8._tree_digest(payload) == reference["actual_state_digest"],
            "complete endpoint did not restore exact actual theta/Adam/RNG/pi")
    return completed


def audit_training_resume(root, job):
    """Metadata-only durable prefix check; the cold worker checks actual tensors."""
    start = job["step"]
    require(job["stage"] == "train" and start in WINDOWS, "foreign fixed training resume")
    path = point_root(root, start) / "context/record.json"
    if not path.exists():
        require(start == 1192 and latest_window_checkpoint(Path(root) / "training", start) is None,
                "missing context cannot hide dispatched fixed training")
        return dict(resume_allowed=True, unknown_calls=0, progress_units=0, evidence=[],
            complete_stage=False, full_tensor_validation_before_cold_scientific_use=True,
            durable_progress_digest=binding.digest(dict(job_id=job["job_id"], pending_window=True)),
            details=dict(awaiting_registered_previous_training=True))
    point = checked_window(root, start)
    evidence = [binding.entry(path)]
    directory = path.parent.parent / "train"
    contract = directory / "binding/record.json"
    latest = latest_window_checkpoint(Path(root) / "training", start)
    if contract.exists():
        require(checked(contract) == dict(_contract(point), id=binding.digest(_contract(point))),
                "fixed training binding changed")
        evidence.append(binding.entry(contract))
    progress = 0
    if latest is not None:
        require(contract.exists(), "durable actual training lacks fixed-window binding")
        step = int(latest.name[4:8])
        ledger = _window_receipts(root, point, step)
        evidence.extend(row["record"] for row in ledger)
        progress = step - start
    completed_path = directory / "completed/record.json"
    if completed_path.exists():
        _validate_completed(point, checked(completed_path))
        require(progress == 298, "completion cannot skip actual optimizer commits")
        evidence.append(binding.entry(completed_path))
    return dict(resume_allowed=True, unknown_calls=0, progress_units=progress, evidence=evidence,
        complete_stage=(directory / "result/record.json").exists(),
        full_tensor_validation_before_cold_scientific_use=True,
        details=dict(durable_optimizer_commits=progress, new_outer_commits=0),
        durable_progress_digest=binding.digest(dict(progress_units=progress, evidence=evidence)))


def validate_training_result(root, job, result):
    point = checked_window(root, job["step"])
    completed_path = point_root(root, job["step"]) / "train/completed/record.json"
    completed = _validate_completed(point, checked(completed_path))
    require(result["branch_result"] == binding.entry(completed_path)
            and result["final_checkpoint"] == completed["final_checkpoint"]
            and (result["initial_step"], result["final_step"], result["optimizer_updates"],
                 result["new_optimizer_updates"], result["outer_updates"])
            == (job["step"], WINDOWS[job["step"]], 298, 298, 0)
            and result["applied"] is False and result["fixed_distribution"] is True
            and result["point_context_id"] == point["id"]
            and result["parent_state_digest"] == point["parent_state_digest"],
            "fixed training result does not bind its true zero-outer completion")
    return completed
