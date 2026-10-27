"""One exact P1192 parent with two fixed teacher-suffix supervision slots.

The native row consumer, checkpoint serializer and optimizer step stay
unchanged; old task masses and new teacher packages are composed explicitly. The original parent is restored and matched before any parameter
group LR is changed. A separate step1192_lr_intervention checkpoint saves the
actual new state; the following 298 native SFT commits keep pi0 and history.
"""
from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path

import finqa_v75_binding as binding

binding.install_scientific_paths()
previous = binding.source_v71("finqa_v71_training")
original, records = previous.original, previous.records
ROOT, SEED = binding.ROOT, 137
POINTS, WINDOWS = (1192, 1490), {1192: 1490}
ARM, CONDITION = "StateDemo1192", "state_demonstration_from_fixed1192"
OLD_LR, NEW_LR = 1e-4, 1e-5
PARENT_STATE_DIGEST = "2dbeeb60a2eb99c8dac36768faf7eb09c8acdffc2b0ae3f4444a0204fcdaa340"
INTERVENTION_PHASE = "lr_intervention"
FIXED_COMPONENTS = previous.FIXED_COMPONENTS
require, checked, publish = binding.require, binding.checked, binding.publish
runtime, checkpoint_ref, read_checkpoint = previous.runtime, previous.checkpoint_ref, previous.read_checkpoint
validate_distribution = previous.validate_distribution



def point_root(root, step):
    require(Path(root).resolve() == ROOT.resolve() and step in POINTS,
            "unregistered V75 low-LR coordinate")
    return Path(root) / "points" / f"step{step:04d}"


def initial_checkpoint():
    """Use the already accepted V71 first-window endpoint, never latest."""
    completed = checked(binding.V71_ROOT / "points/step0894/train/completed/record.json")
    reference = completed["final_checkpoint"]
    require(completed["protocol_id"] == binding.V71_PROTOCOL_ID
            and completed["status"] == "COMPLETE" and completed["arm"] == "Fixed894"
            and completed["initial_step"] == 894 and completed["final_step"] == 1192
            and completed["optimizer_updates"] == 298 and completed["outer_updates"] == 0
            and completed["outer_done"] == [298]
            and Path(reference["path"]).resolve() == binding.V71_ROOT / "training/step1192_step"
            and reference["actual_state_digest"] == PARENT_STATE_DIGEST
            and reference["step"] == 1192 and reference["phase"] == "step",
            "V75 requires the registered actual V71 fixed-pi1192 parent")
    return reference


def _learning_rates(optimizer_state):
    groups = optimizer_state["param_groups"]
    require(isinstance(groups, list) and groups, "actual Adam parameter groups required")
    rates = [group["lr"] for group in groups]
    require(all(type(rate) in (int, float) and math.isfinite(rate) and rate > 0 for rate in rates),
            "actual learning rates must be finite positive scalars")
    return rates


def _without_lr(groups):
    return [{key: value for key, value in group.items() if key != "lr"} for group in groups]


def state_with_learning_rate(state, rate):
    """Structural copy for a declared digest comparison; never mutates state."""
    _learning_rates(state["optimizer"])
    groups = [dict(group, lr=rate) for group in state["optimizer"]["param_groups"]]
    return dict(state, optimizer=dict(state["optimizer"], param_groups=groups))


def validate_point_state(state, step, rt, *, learning_rate):
    require(type(step) is int and 1192 <= step <= 1490
            and (state["seed"], state["step"], state["arm"]) == (SEED, step, "C-only")
            and state["outer_done"] == [298], "low-LR branch coordinate/history changed")
    require(state["model_training"] is True and state["optimizer"]["state"]
            and state["rng"]["cuda"], "complete actual Adam/training RNG required")
    for value in state["optimizer"]["state"].values():
        require(set(value) >= {"step", "exp_avg", "exp_avg_sq"}
                and int(value["step"].item()) == step, "actual Adam cursor or moments differ")
    require(all(rate == learning_rate for rate in _learning_rates(state["optimizer"])),
            "actual optimizer learning rate differs from this condition")
    require(len(state["pi"]) == len(state["prior"]) == 744
            and state["execution_plan"]["outer_steps"] == [298, 596, 894, 1192]
            and state["execution_plan"]["final_step"] == 1490,
            "original support or ten-epoch execution plan changed")
    validate_distribution(state["pi"], state["prior"])
    return state


def validate_parent_state(state, rt):
    validate_point_state(state, 1192, rt, learning_rate=OLD_LR)
    require(rt.v8._tree_digest(state) == PARENT_STATE_DIGEST,
            "original pre-intervention parent theta/Adam/RNG/pi differs")
    return state


def assert_fixed_state(state, context, rt):
    previous.assert_fixed_state(state, context, rt)
    require(rt.v8._tree_digest(_without_lr(state["optimizer"]["param_groups"]))
            == context["optimizer_groups_except_lr_digest"],
            "Adam parameter membership or non-LR hyperparameters changed")
    return state


def validate_low_lr_state(state, step, context, rt):
    validate_point_state(state, step, rt, learning_rate=NEW_LR)
    return assert_fixed_state(state, context, rt)


def prepare_initial(root, protocol_id):
    return prepare_window(root, 1192, protocol_id)


def prepare_window(root, start, protocol_id):
    require(start == 1192, "only one low-LR1192 window is registered")
    protocol = checked(Path(root) / "protocol/record.json")
    require(protocol["id"] == protocol_id, "candidate window protocol differs")
    prepared_material = checked(Path(root) / "materials/record.json")
    require(prepared_material["status"] == "COMPLETE" and prepared_material["protocol_id"] == protocol_id and prepared_material["packages"], "NO_USABLE_DEMONSTRATIONS or incomplete teacher material")
    destination = point_root(root, start) / "context/record.json"
    if destination.exists():
        value = checked_window(root, start)
        require(value["protocol_id"] == protocol_id, "existing window protocol differs")
        return value
    training, rt = runtime()
    reference = initial_checkpoint()
    require(reference == protocol["initial_parent"]["checkpoint"], "registered parent checkpoint differs")
    source_context = checked(binding.V71_ROOT / "points/step0894/context/record.json")
    state = validate_parent_state(read_checkpoint(reference, rt), rt)
    previous.assert_fixed_state(state, source_context, rt)
    require(rt.v8._tree_digest(state) == protocol["initial_parent"]["source_state_digest"]
            and rt.v8._tree_digest(state["pi"]) == protocol["initial_parent"]["distribution_digest"],
            "exact original state/pi0 binding differs")
    _science, pool, _prefix, _assets = training.checked_launch(Path(source_context["training_root"]))
    require(state["pool_id"] == pool.cache_id == source_context["pool_id"]
            and state["schedule"] == training.build_task_schedule(pool.task_ids, SEED)
            and state["prior"] == pool._manifest.registration.pi0
            and state["schedule"]["schedule_sha256"] == source_context["original_schedule_sha256"],
            "actual material, prior or exact task schedule changed")
    batches = state["schedule"]["batches"][1192:1490]
    require(len(batches) == 298 and sum(len(row["task_ids"]) for row in batches) == 1488
            and sorted(len(row["task_ids"]) for row in batches) == [4, 4] + [5] * 296,
            "exact298 batches with two four-task tails required")
    planned = rt.v8._tree_digest(state_with_learning_rate(state, NEW_LR))
    require(planned != PARENT_STATE_DIGEST, "LR-only intervention must change complete state digest")
    return publish(destination, dict(schema="v75_fixed_pi_low_lr_window.v1",
        protocol_id=protocol_id, seed=SEED, arm=ARM, condition=CONDITION,
        checkpoint_arm="C-only", step=1192, final_step=1490,
        parent_checkpoint=reference, initial_checkpoint=reference,
        parent_state_digest=PARENT_STATE_DIGEST, parent_pi=copy.deepcopy(state["pi"]),
        fixed_pi=copy.deepcopy(state["pi"]), fixed_pi_digest=rt.v8._tree_digest(state["pi"]),
        prior=copy.deepcopy(state["prior"]), outer_done=[298],
        fixed_component_digests={key: rt.v8._tree_digest(state[key]) for key in FIXED_COMPONENTS},
        component_digests={key: rt.v8._tree_digest(state[key]) for key in records.COMPONENTS},
        optimizer_groups_except_lr_digest=rt.v8._tree_digest(_without_lr(state["optimizer"]["param_groups"])),
        parameter_group_count=len(state["optimizer"]["param_groups"]),
        initial_learning_rate=OLD_LR, learning_rate=NEW_LR,
        planned_post_intervention_state_digest=planned,
        planned_digest_is_not_actual_intervention_execution=True,
        LR_intervention_after_complete_parent_restore=True,
        pool_id=pool.cache_id, original_schedule_sha256=state["schedule"]["schedule_sha256"],
        window_task_batches=copy.deepcopy(batches), window_task_exposures=1488,
        training_root=source_context["training_root"],
        source_v71_context=binding.entry(binding.V71_ROOT / "points/step0894/context/record.json"),
        scientific_sources=dict(driver=binding.file_ref(rt.v8.__file__),
                                frozen_training=binding.file_ref(training.__file__)),
        demonstration_materials=binding.entry(Path(root) / "materials/record.json"),
        planned_demonstration_per_step=prepared_material["dose"]["per_step"],
        demonstration_policy=__import__("finqa_v75_materials").material_policy(),
        new_outer_updates=0, automatic_outer_disabled=True,
        original_outer_history_not_rewritten=True, new_feedback_sessions=0,
        new_class_passes=0, new_response_replay=0, new_VJP=0))


def checked_window(root, start):
    require(start == 1192, "unregistered low-LR window")
    point = checked(point_root(root, start) / "context/record.json")
    require(point["schema"] == "v75_fixed_pi_low_lr_window.v1"
            and (point["seed"], point["step"], point["final_step"]) == (SEED, 1192, 1490)
            and point["arm"] == ARM and point["condition"] == CONDITION
            and point["checkpoint_arm"] == "C-only" and point["outer_done"] == [298]
            and point["new_outer_updates"] == 0 and point["automatic_outer_disabled"] is True
            and point["initial_learning_rate"] == OLD_LR and point["learning_rate"] == NEW_LR
            and point["parent_pi"] == point["fixed_pi"]
            and point["parent_state_digest"] != point["planned_post_intervention_state_digest"],
            "low-LR fixed-pi context changed")
    return point


def load_window(root, start, rt):
    point = checked_window(root, start)
    state = validate_parent_state(read_checkpoint(point["parent_checkpoint"], rt), rt)
    require(rt.v8._tree_digest(state) == point["parent_state_digest"], "actual parent digest differs")
    assert_fixed_state(state, point, rt)
    return point, state


def configure_fixed_window(driver, start):
    require(start == 1192, "only1193–1490 training is authorized")
    driver.outer_steps = ()
    driver.final_step = 1490


def intervention_directory(root):
    return Path(root) / "training" / "step1192_lr_intervention"


def _intervention_evidence(point):
    return dict(schema="v75_actual_LR_only_intervention.v1", protocol_id=point["protocol_id"],
        point_context_id=point["id"], pre_state_digest=point["parent_state_digest"],
        post_state_digest=point["planned_post_intervention_state_digest"], step=1192,
        initial_learning_rates=[OLD_LR] * point["parameter_group_count"],
        learning_rates=[NEW_LR] * point["parameter_group_count"],
        changed_fields=[f"optimizer.param_groups[{index}].lr" for index in range(point["parameter_group_count"])],
        exact_parent_restored_before_intervention=True, all_other_actual_state_unchanged=True,
        Adam_moments_and_cursor_preserved=True, training_RNG_preserved=True,
        optimizer_step_calls=0, clip_calls=0, new_outer_updates=0, new_model_calls=0)


def _native_intervention_metadata(root, point):
    directory = intervention_directory(root)
    require(directory.is_dir() and (directory / "state.pt").is_file()
            and (directory / "record.json").is_file(), "partial LR intervention is not durable")
    row = json.loads((directory / "record.json").read_bytes())
    require((row["step"], row["phase"], row["arm"], row["seed"])
            == (1192, INTERVENTION_PHASE, "C-only", SEED)
            and row["actual_state_digest"] == point["planned_post_intervention_state_digest"]
            and row["pool_id"] == point["pool_id"]
            and row["schedule_sha256"] == point["original_schedule_sha256"]
            and row["checkpoint_contains_actual_model_Adam_RNG_pi"] is True
            and row["evidence"] == _intervention_evidence(point),
            "actual LR intervention metadata or preserved parent binding changed")
    return checkpoint_ref(directory)


def validate_only_lr_intervention(before, after, point, rt):
    require(rt.v8._tree_digest(before) == point["parent_state_digest"]
            and all(rate == OLD_LR for rate in _learning_rates(before["optimizer"]))
            and all(rate == NEW_LR for rate in _learning_rates(after["optimizer"]))
            and rt.v8._tree_digest(state_with_learning_rate(after, OLD_LR)) == point["parent_state_digest"]
            and rt.v8._tree_digest(after) == point["planned_post_intervention_state_digest"]
            and rt.v8._tree_digest(before) != rt.v8._tree_digest(after),
            "intervention must change only actual LR after exact parent restore")


def ensure_lr_intervention(root, point, parent_state, driver, rt):
    """Seal once or restore the actual LR-only state without optimizer steps."""
    require(driver.step_index == 1192 and rt.v8._tree_digest(driver._payload()) == point["parent_state_digest"],
            "complete actual parent must be restored before LR intervention or recovery")
    native = intervention_directory(root)
    if native.exists():
        reference = _native_intervention_metadata(root, point)
        driver.restore(native)
    else:
        before = driver._payload()
        for group in driver.optimizer.param_groups:
            group["lr"] = NEW_LR
        after = driver._payload()
        validate_only_lr_intervention(before, after, point, rt)
        driver.commit(INTERVENTION_PHASE, _intervention_evidence(point))
        reference = _native_intervention_metadata(root, point)
    actual = driver._payload()
    validate_only_lr_intervention(parent_state, actual, point, rt)
    validate_low_lr_state(actual, 1192, point, rt)
    proof_path = point_root(root, 1192) / "train/lr_intervention/record.json"
    return publish(proof_path, dict(schema="v75_LR_intervention_actual_checkpoint_sealed.v1",
        protocol_id=point["protocol_id"], point_context_id=point["id"],
        parent_checkpoint=point["parent_checkpoint"], actual_checkpoint=reference,
        pre_state_digest=point["parent_state_digest"], post_state_digest=reference["actual_state_digest"],
        initial_learning_rate=OLD_LR, learning_rate=NEW_LR,
        evidence=_intervention_evidence(point), optimizer_updates=0, outer_updates=0))


def checked_intervention(root, point):
    proof_path = point_root(root, 1192) / "train/lr_intervention/record.json"
    proof = checked(proof_path)
    require(proof["schema"] == "v75_LR_intervention_actual_checkpoint_sealed.v1"
            and proof["protocol_id"] == point["protocol_id"] and proof["point_context_id"] == point["id"]
            and proof["actual_checkpoint"] == _native_intervention_metadata(root, point)
            and proof["parent_checkpoint"] == point["parent_checkpoint"]
            and proof["pre_state_digest"] == point["parent_state_digest"]
            and proof["post_state_digest"] == point["planned_post_intervention_state_digest"]
            and proof["evidence"] == _intervention_evidence(point)
            and proof["optimizer_updates"] == proof["outer_updates"] == 0,
            "actual LR intervention proof changed")
    return proof


def latest_window_checkpoint(directory, start):
    require(start == 1192, "unregistered low-LR training resume")
    found = []
    for path in Path(directory).glob("step*_*"):
        if path.name == "step1192_lr_intervention":
            require(path.is_dir() and (path / "record.json").is_file() and (path / "state.pt").is_file(),
                    "partial LR intervention is not durable")
            continue
        match = re.fullmatch(r"step(\d{4})_step", path.name)
        require(match is not None and path.is_dir(), "low-LR continuation forbids new outer or foreign checkpoints")
        step = int(match[1])
        require(1193 <= step <= 1490, "training escaped its exact298-update dose")
        require((path / "record.json").is_file() and (path / "state.pt").is_file(),
                "partial checkpoint is not a durable resume boundary")
        found.append((step, path))
    return max(found)[1] if found else None


def _contract(point):
    return dict(schema="v75_fixed_pi_low_lr_window_binding.v1", protocol_id=point["protocol_id"],
        point_context_id=point["id"], parent_state_digest=point["parent_state_digest"],
        planned_post_intervention_state_digest=point["planned_post_intervention_state_digest"],
        seed=SEED, arm=ARM, checkpoint_arm="C-only", condition=CONDITION,
        start_step=1192, end_step=1490, distribution_digest=point["fixed_pi_digest"],
        parent_training_rng_digest=point["component_digests"]["rng"],
        original_task_schedule_sha256=point["original_schedule_sha256"],
        initial_learning_rate=OLD_LR, learning_rate=NEW_LR,
        LR_change_after_exact_restore=True, old_loss_component_unchanged=True,
        native_optimizer_and_clip_unchanged=True, demonstration_materials=point["demonstration_materials"],
        demonstration_policy=point["demonstration_policy"],
        outer_schedule_during_window=[], optimizer_updates=298, task_exposures=1488,
        outer_updates=0, original_outer_done=[298], initial_checkpoint=point["initial_checkpoint"],
        reinitialize_training_rng_after_restore=False)


def _driver_rates(driver):
    return [group["lr"] for group in driver.optimizer.param_groups]


def execute_training(root, point, state, driver, *, rt, monitor, resource_report=None):
    require(point["step"] == 1192 and driver.root.resolve() == (Path(root) / "training").resolve(),
            "low-LR training must stay in its independent one-window branch")
    directory = point_root(root, 1192) / "train"
    publish(directory / "binding/record.json", _contract(point))
    completed = directory / "completed/record.json"
    require(not completed.exists(), "completed low-LR window cannot execute again")
    configure_fixed_window(driver, 1192)
    intervention = ensure_lr_intervention(root, point, state, driver, rt)
    latest = latest_window_checkpoint(driver.root, 1192)
    if latest is not None:
        driver.restore(latest)
    actual = driver._payload()
    validate_low_lr_state(actual, driver.step_index, point, rt)
    require(1192 <= driver.step_index <= 1490, "durable low-LR cursor escaped registered window")
    install_demonstration_consumer(driver, point)
    began = driver.step_index
    while driver.step_index < 1490:
        monitor.check_stop("before_real_low_lr_sft_update", step=driver.step_index + 1)
        require(driver.outer_steps == () and driver.pi == point["fixed_pi"] and driver.outer_done == [298]
                and _driver_rates(driver) == [NEW_LR] * point["parameter_group_count"],
                "actual fixed pi0, LR or outer history changed before SFT")
        report = driver.step()
        _check_step_report(report, point, driver.step_index)
        require(driver.pi == point["fixed_pi"] and driver.outer_done == [298]
                and _driver_rates(driver) == [NEW_LR] * point["parameter_group_count"],
                "actual LR, fixed distribution or original history changed during SFT")
        monitor.clear_unused("low_lr_sft_committed_step%04d" % driver.step_index)
    final_state = driver._payload()
    validate_low_lr_state(final_state, 1490, point, rt)
    reference = checkpoint_ref(driver.root / "step1490_step")
    require(reference["actual_state_digest"] == rt.v8._tree_digest(final_state),
            "live final model/Adam/RNG/LR differs from actual committed endpoint")
    ledger = _window_receipts(root, point, 1490)
    return publish(completed, dict(schema="v75_low_lr_window_complete.v1", status="COMPLETE",
        protocol_id=point["protocol_id"], point_context_id=point["id"], seed=SEED,
        arm=ARM, checkpoint_arm="C-only", condition=CONDITION,
        initial_step=1192, final_step=1490, optimizer_updates=298, new_optimizer_updates=298,
        task_exposures=1488, outer_updates=0, outer_done=[298], fixed_distribution=True,
        initial_learning_rate=OLD_LR, learning_rate=NEW_LR,
        learning_rate_intervention=binding.entry(directory / "lr_intervention/record.json"),
        post_intervention_state_digest=intervention["post_state_digest"],
        learning_rate_checked_before_and_after_every_update=True,
        final_checkpoint=reference, snapshots={"1490": reference},
        distribution_digest=point["fixed_pi_digest"], fixed_distribution_digest=point["fixed_pi_digest"],
        initial_checkpoint=point["initial_checkpoint"], update_receipts=ledger,
        updates_in_final_worker=1490 - began, next_outer_automatically_executed=False,
        training_binding=binding.entry(directory / "binding/record.json"),
        demonstration_materials=point["demonstration_materials"],
        actual_demonstration_consumption=summarize_consumption(root, point, ledger),
        resources=resource_report() if resource_report else None))


def _validate_completed(point, completed):
    require(completed["schema"] == "v75_low_lr_window_complete.v1" and completed["status"] == "COMPLETE"
            and completed["point_context_id"] == point["id"] and completed["protocol_id"] == point["protocol_id"]
            and (completed["initial_step"], completed["final_step"], completed["optimizer_updates"],
                 completed["new_optimizer_updates"], completed["task_exposures"], completed["outer_updates"])
            == (1192, 1490, 298, 298, 1488, 0)
            and completed["outer_done"] == [298] and completed["arm"] == ARM
            and completed["fixed_distribution"] is True
            and completed["distribution_digest"] == point["fixed_pi_digest"]
            and completed["initial_learning_rate"] == OLD_LR and completed["learning_rate"] == NEW_LR
            and completed["post_intervention_state_digest"] == point["planned_post_intervention_state_digest"]
            and completed["learning_rate_checked_before_and_after_every_update"] is True,
            "completed low-LR window dose/state/intervention metadata differs")
    require(completed["demonstration_materials"] == point["demonstration_materials"]
        and completed["actual_demonstration_consumption"]["status"] == "PASS"
        and completed["actual_demonstration_consumption"]["material_id"] == point["demonstration_materials"]["id"],
        "complete candidate must prove actual registered teacher consumption")
    return completed


def restore_completed_window(point, completed, driver, rt):
    _validate_completed(point, completed)
    root = driver.root.parent
    proof = checked_intervention(root, point)
    require(completed["learning_rate_intervention"] == binding.entry(
        point_root(root, 1192) / "train/lr_intervention/record.json")
        and proof["post_state_digest"] == completed["post_intervention_state_digest"],
        "completed actual learning-rate intervention changed")
    reference = completed["final_checkpoint"]
    require(checkpoint_ref(reference["path"]) == reference, "actual endpoint metadata changed")
    configure_fixed_window(driver, 1192)
    driver.restore(reference["path"])
    payload = driver._payload()
    validate_low_lr_state(payload, 1490, point, rt)
    require(driver.step_index == 1490 and rt.v8._tree_digest(payload) == reference["actual_state_digest"],
            "complete endpoint did not restore exact actual theta/Adam/RNG/pi/LR")
    return completed


def audit_training_resume(root, job):
    require(job["stage"] == "train" and job["step"] == 1192, "foreign low-LR resume")
    point = checked_window(root, 1192)
    directory = point_root(root, 1192) / "train"
    evidence = [binding.entry(point_root(root, 1192) / "context/record.json")]
    contract = directory / "binding/record.json"
    if contract.exists():
        require(checked(contract) == dict(_contract(point), id=binding.digest(_contract(point))),
                "low-LR training binding changed")
        evidence.append(binding.entry(contract))
    native = intervention_directory(root)
    proof_path = directory / "lr_intervention/record.json"
    if native.exists():
        require(contract.exists(), "actual LR intervention lacks its registered training binding")
        _native_intervention_metadata(root, point)
        evidence.append(binding.file_ref(native / "record.json"))
    if proof_path.exists():
        checked_intervention(root, point)
        evidence.append(binding.entry(proof_path))
    latest = latest_window_checkpoint(Path(root) / "training", 1192)
    progress = 0
    if latest is not None:
        require(contract.exists() and proof_path.exists(), "SFT commits precede actual LR intervention proof")
        step = int(latest.name[4:8])
        ledger = _window_receipts(root, point, step)
        evidence.extend(row["record"] for row in ledger)
        progress = step - 1192
    completed_path = directory / "completed/record.json"
    if completed_path.exists():
        _validate_completed(point, checked(completed_path))
        require(progress == 298, "completion cannot skip actual optimizer commits")
        evidence.append(binding.entry(completed_path))
    return dict(resume_allowed=True, unknown_calls=0, progress_units=progress, evidence=evidence,
        complete_stage=(directory / "result/record.json").exists(),
        full_tensor_validation_before_cold_scientific_use=True,
        details=dict(durable_optimizer_commits=progress, new_outer_commits=0,
                     actual_lr_intervention_checkpoint_present=native.exists()),
        durable_progress_digest=binding.digest(dict(progress_units=progress, evidence=evidence)))


def validate_training_result(root, job, result):
    point = checked_window(root, job["step"])
    completed_path = point_root(root, 1192) / "train/completed/record.json"
    completed = _validate_completed(point, checked(completed_path))
    proof = checked_intervention(root, point)
    require(result["branch_result"] == binding.entry(completed_path)
            and result["final_checkpoint"] == completed["final_checkpoint"]
            and (result["initial_step"], result["final_step"], result["optimizer_updates"],
                 result["new_optimizer_updates"], result["outer_updates"]) == (1192, 1490, 298, 298, 0)
            and result["applied"] is False and result["fixed_distribution"] is True
            and result["point_context_id"] == point["id"] and result["parent_state_digest"] == point["parent_state_digest"]
            and result["initial_learning_rate"] == OLD_LR and result["learning_rate"] == NEW_LR
            and result["learning_rate_intervention"] == completed["learning_rate_intervention"]
            and result["post_intervention_state_digest"] == proof["post_state_digest"],
            "low-LR result does not bind its actual intervention and zero-outer completion")
    return completed


def training_contract():
    from finqa_v75_materials import material_policy
    return dict(schema="v75_state_demonstration_training_contract.v1",arm=ARM,condition=CONDITION,
        parent_step=1192,final_step=1490,new_optimizer_updates=298,task_exposures=1488,
        original_task_schedule_and_batch_sizes=True,fixed_original_pi=True,learning_rate=NEW_LR,
        original_outer_done=[298],new_outer_updates=0,new_Contribution=0,new_VJP=0,
        original_complete_Adam_RNG_restored_before_lr_change=True,
        original_loss_component_and_optimizer_unchanged=True,
        demonstration_policy=material_policy(),two_slot_weights=["1/4","1/4"],
        old_task_weight="1-1/4*I_initial-1/4*I_post",missing_mass_not_redistributed=True,
        teacher_suffix_loss_normalization="sum CE / all actual new teacher response tokens in complete suffix",
        teacher_rows_after_original_rows_in_registered_task_and_slot_order=True,
        one_zero_grad_one_clip1_one_Adam_update=True,
        dropout_RNG_consumption_differs_when_extra_forwards_run=True,
        same_updates_not_same_compute=True,old_control_reused_not_independent_replication=True)


def baseline_compatibility_policy():
    import importlib
    training,rt=runtime()
    materials=importlib.import_module("trusted_synthesis.finance_research.materials")
    consumer=importlib.import_module("trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.trajectory_consumer")
    return dict(schema="v75_existing_V72_control_compatibility.v1",status="UNCHANGED_COMMON_CONTRACT",
        reused_control_root=str(binding.V72_ROOT),control_EA_correct=431,parent1192_EA_correct=536,denominator=883,
        original_894_EA525_is_not_this_parent=True,
        unchanged_sources={"task_batch_materials":binding.file_ref(materials.__file__),
            "native_row_consumer":binding.file_ref(consumer.__file__),"native_driver":binding.file_ref(rt.v8.__file__),
            "frozen_training":binding.file_ref(training.__file__)},
        old_masks_whole_package_normalization_clip_and_Adam_rules_unchanged=True,
        model_configuration_and_native_greedy_evaluation_unchanged=True,
        no_shared_consumer_fix=True,baseline_retraining=0,
        additional_teacher_forwards_change_RNG_consumption=True)


def _material_record(point):
    import finqa_v75_materials as materials
    value=binding.read_ref(point["demonstration_materials"])
    require(value["status"]=="COMPLETE" and value["protocol_id"]==point["protocol_id"]
        and value["policy"]==materials.material_policy() and value["packages"],
        "training requires nonempty admitted frozen teacher material")
    return value


def load_demonstrations(point):
    value=_material_record(point)
    packages={key:binding.read_ref(ref) for key,ref in value["packages"].items()}
    for key,package in packages.items():
        require(package["package_id"]==key and package["protocol_id"]==point["protocol_id"]
            and package["student_prefix_target_count"]==0 and package["target_tokens"]>0
            and package["target_mask_check"]=="PASS_EXACT_NEW_TEACHER_RESPONSES_ONLY",
            "registered new teacher package lost its exact mask/source contract")
    return value,packages


def consume_task_batch(model,optimizer,pool,pi,batch,*,device,arm,material_record,packages,
                       original_materials=None,trajectory_consumer=None,event_sink=None):
    """Keep the old consumer verbatim; compose weighted rows before its one step."""
    import importlib
    from fractions import Fraction
    from finqa_v75_materials import slot_weights
    original_materials=original_materials or importlib.import_module("trusted_synthesis.finance_research.materials")
    trajectory_consumer=trajectory_consumer or importlib.import_module("trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.trajectory_consumer")
    slots=[]
    for task in batch.task_ids:
        row=material_record["tasks"].get(task,{"slots":{}})
        for name in ("initial","post"):
            slot=row["slots"].get(name)
            if slot is not None:slots.append((task,name,slot,packages[slot["package_id"]]))
    consumption=dict(schema="v75_actual_step_demonstration_consumption.v1",
        materials_id=material_record["id"],step=batch.step,slots=[],teacher_target_tokens=0,
        teacher_input_positions=0,teacher_microbatches=0,teacher_trajectories=0,
        old_consumer_exact_delegation_when_no_slots=not slots,
        original_materials_all_rows_consumed=True,student_prefix_target_count=0)
    if not slots:
        report=original_materials.execute_task_batch_update(model,optimizer,pool,pi,batch,
            device=device,arm=arm,event_sink=event_sink)
    else:
        examples=original_materials.task_batch_examples(pool,pi,batch)
        old_count=len(examples)
        for package in examples:
            row=material_record["tasks"].get(package["task_id"],{"slots":{}})
            w=slot_weights(row["slots"].get("initial") is not None,row["slots"].get("post") is not None)
            coefficient=Fraction(package["target_token_coefficient"])*w["old"]
            package["target_token_coefficient"],package["coefficient_float"]=str(coefficient),float(coefficient)
            package["old_task_retained_mass"]=str(w["old"])
        for task,name,slot,encoded in slots:
            # Same native mu/(B*p_s) factor as all original task packages.
            task_mass=Fraction(str(pool._manifest.registration.mu[task]))/(len(batch.task_ids)*Fraction(str(batch.sampling_probability[task])))
            task_weight=task_mass*Fraction(1,4)
            coefficient=task_weight/encoded["target_tokens"]
            examples.append(dict(package_id=slot["package_id"],task_id=task,state_id="v75_teacher_"+name,
                slot=name,whole_package_target_tokens=encoded["target_tokens"],
                target_token_coefficient=str(coefficient),coefficient_float=float(coefficient),n_state=1,
                task_draw_index=list(batch.task_ids).index(task),teacher_suffix=True))
            consumption["slots"].append(dict(task_id=task,slot=name,package_id=slot["package_id"],
                task_coefficient=str(task_weight),target_tokens=encoded["target_tokens"],
                input_positions=encoded["input_positions"],teacher_turns=encoded["teacher_turns"]))
            consumption["teacher_target_tokens"]+=encoded["target_tokens"]
            consumption["teacher_input_positions"]+=encoded["input_positions"]
            consumption["teacher_microbatches"]+=encoded["teacher_turns"]
        consumption["teacher_trajectories"]=len(slots)
        class Cache:
            cache_id="v75_augmented_rows:"+binding.digest([pool.cache_id,material_record["id"]])
            def row_arrays(self,key):
                return packages[key]["rows"] if key in packages else pool.row_arrays(key)
        raw=trajectory_consumer.execute_update(model,optimizer,examples,{"tasks":list(batch.task_ids)},
            pool=pool._manifest.registration.dataset,arm=arm,device=device,trajectory_cache=Cache(),event_sink=event_sink)
        report={k:v for k,v in raw.items() if k not in {"id","schema_version","loss_rule","execution_design","loss_domain"}}
        report.update(schema_version="finance_research.v75_task_batch_update.v1",
            loss_rule="mu/(B*p_s) * ((1-.25I0-.25I1)*old_task_loss + .25I0*teacher0_token_mean + .25I1*teacher1_token_mean)",
            loss_domain="unchanged old targets plus exact new teacher suffix assistant tokens",
            execution_design="v75_original_rows_plus_teacher_suffix_rows",full_pool_update=False,
            batch_size=len(batch.task_ids),additional_batch_division=False,task_batch=batch.model_dump(mode="json"),
            legacy_consumer_result_sha256=binding.digest(raw),
            qualification_registration_id=pool._manifest.registration.qualification_registration_id,
            validator_binding_id=pool._manifest.registration.validator_binding_id,state_semantics_independently_proven=False,
            original_package_count=old_count,teacher_package_count=len(slots))
        report["id"]="v75_task_batch_update:"+binding.digest(report)
    legacy_id=report["id"]
    report.update(demonstration_consumption=consumption,old_consumer_underlying_update_id=legacy_id,
        demonstration_materials_id=material_record["id"],demonstration_slots_do_not_renormalize=True)
    report["id"]="v75_composed_task_batch_update:"+binding.digest({k:v for k,v in report.items() if k!="id"})
    return report


def install_demonstration_consumer(driver,point):
    """Private step adapter: identical native cursor/commit logic, new loss+labels."""
    import inspect,textwrap
    from types import MethodType
    material_record,packages=load_demonstrations(point)
    original_step=type(driver).step
    source=textwrap.dedent(inspect.getsource(original_step))
    substitutions={
        'loss_domain="review-approved original token spans/actions/EOS; full-package L_P"':
            'loss_domain="unchanged original targets plus exact complete new teacher assistant suffix targets"',
        'execution_design=f"original_unfused_response_rows_{material_version}"':
            'execution_design="v75_original_rows_plus_teacher_suffix_rows"',
        'supervision_policy=supervision_policy,':
            'supervision_policy="v75_exact_teacher_suffix_plus_unchanged_old.v1", original_supervision_policy=supervision_policy,'}
    for old,new in substitutions.items():
        require(source.count(old)==1,"native driver step metadata structure changed")
        source=source.replace(old,new)
    namespace=dict(original_step.__globals__)
    def consume(*args,**kwargs):
        return consume_task_batch(*args,**kwargs,material_record=material_record,packages=packages)
    namespace["execute_task_batch_update"]=consume
    exec(compile(source,__file__+"::private_native_step_metadata_and_consumer_adapter","exec"),namespace)
    driver.step=MethodType(namespace["step"],driver)
    driver.v75_materials=material_record
    return material_record


def _check_step_report(report,point,step):
    expected=point["window_task_batches"][step-point["step"]-1]
    require(report["optimizer_step_calls"]==report["clip_calls"]==report["zero_grad_calls"]==1
        and report["actual_parameter_update"] is True and report["CPU_control_only"] is False
        and report["execution_design"]=="v75_original_rows_plus_teacher_suffix_rows"
        and report["supervision_policy"]=="v75_exact_teacher_suffix_plus_unchanged_old.v1"
        and report["original_supervision_policy"]=="v14_state_independent_original_span_union.v1"
        and report["additional_batch_division"] is False
        and report["additional_loss_scaling"] is False
        and report["task_batch"]["task_ids"]==expected["task_ids"]
        and report["task_batch"]["step"]==step
        and report["task_batch"]["schedule_id"]==point["original_schedule_sha256"],
        "actual V75 optimizer step, original task order or declared consumer differs")
    consumed=report["demonstration_consumption"]
    require(consumed["materials_id"]==point["demonstration_materials"]["id"]
        and consumed["step"]==step and consumed["student_prefix_target_count"]==0
        and consumed["original_materials_all_rows_consumed"] is True
        and report["demonstration_slots_do_not_renormalize"] is True,
        "actual V75 material consumption identity or mask changed")
    planned=point["planned_demonstration_per_step"][step-1193]
    require(planned["step"]==step and consumed["slots"]==planned["demonstrations"],
        "actual per-step teacher consumption differs from the preregistered dose")


def _window_receipts(root,point,through):
    refs=[]
    for step in range(point["step"]+1,through+1):
        path=Path(root)/"training"/f"step{step:04d}_step/record.json"
        record=json.loads(path.read_bytes())
        require((record["step"],record["phase"],record["arm"],record["seed"])==(step,"step","C-only",SEED)
            and record["pool_id"]==point["pool_id"]
            and record["schedule_sha256"]==point["original_schedule_sha256"]
            and record["checkpoint_contains_actual_model_Adam_RNG_pi"] is True
            and (path.parent/"state.pt").is_file(),"actual candidate training receipt or checkpoint missing")
        _check_step_report(record["evidence"],point,step)
        refs.append(dict(step=step,record=binding.file_ref(path),state_sha256=record["state_sha256"],
            actual_state_digest=record["actual_state_digest"],update_id=record["evidence"]["id"],
            demonstration_consumption=record["evidence"]["demonstration_consumption"]))
    return refs


def summarize_consumption(root,point,ledger):
    from collections import Counter
    material=_material_record(point);planned=material["dose"]
    totals=Counter();slots=Counter()
    require(len(ledger)==298,"actual candidate training ledger incomplete")
    for row,expected in zip(ledger,planned["per_step"],strict=True):
        actual=row["demonstration_consumption"]
        require(row["step"]==expected["step"] and actual["slots"]==expected["demonstrations"],
            "actual teacher slots/tokens/microbatches differ from pretraining dose")
        for key in ("teacher_target_tokens","teacher_input_positions","teacher_microbatches","teacher_trajectories"):
            totals[key]+=actual[key]
        for slot in actual["slots"]:slots[slot["slot"]]+=1
    require(totals["teacher_target_tokens"]==sum(planned["planned_teacher_target_tokens"].values())
        and totals["teacher_input_positions"]==sum(planned["planned_teacher_input_positions"].values())
        and totals["teacher_microbatches"]==sum(planned["planned_teacher_microbatches"].values()),
        "actual teacher supervision dose does not equal the frozen planned dose")
    return dict(schema="v75_complete_actual_demonstration_consumption.v1",status="PASS",
        material_id=material["id"],updates=298,task_exposures=1488,**dict(totals),
        teacher_trajectory_exposures_by_slot=dict(slots),all298_actual_receipts_match_frozen_slots=True,
        fixed_missing_slot_mass_retained_in_old=True,student_prefix_target_count=0,
        original_task_frequency_unchanged=True,extra_forward_RNG_not_bitwise_paired_to_B=True)


validate_candidate_state=validate_low_lr_state


def job_spec(step=1192,stage="train"):
    require(step==1192 and stage=="train","only one candidate window is registered")
    return dict(id="step1192.train",job_id="step1192.train",seed=SEED,step=1192,stage="train",
        kind="train",memory_phase="train",arm=ARM,condition=CONDITION,fixed_distribution=True,
        outer_updates=0,initial_learning_rate=OLD_LR,learning_rate=NEW_LR)


def execute(root,job,attempt_root,guard):
    import gc
    expected=job_spec()
    require(all(job.get(k)==v for k,v in expected.items() if k not in ("id","job_id")),
        "job differs from the one registered candidate")
    training,rt=runtime();context,state=load_window(root,1192,rt)
    _science,pool,_prefix,assets=training.checked_launch(Path(context["training_root"]))
    require(context["protocol_id"]==guard.protocol["id"],"resource and candidate training protocol differ")
    monitor=binding.source_v72("runtime").ScientificMonitor(guard,cooperative_replay=False)
    monitor.check_stop("before_actual_candidate_model_load")
    model,tokenizer,optimizer,scope,_fresh=rt.launcher._load_components(assets,SEED)
    driver=training.adapters().TrainingDriver(model,optimizer,pool,root=Path(root)/"training",
        seed=SEED,arm="C-only",device="cuda:0",tokenizer=tokenizer,adapter_scope=scope,feedback_collector=None)
    configure_fixed_window(driver,1192);driver.restore(context["parent_checkpoint"]["path"])
    restored=driver._payload();validate_parent_state(restored,rt)
    require(rt.v8._tree_digest(restored)==context["parent_state_digest"],"complete original parent restore must precede LR intervention")
    del restored
    monitor.clear_unused("after_exact_parent_model_Adam_RNG_pi_restore_before_intervention")
    directory=point_root(root,1192)/"train";completed=directory/"completed/record.json"
    result=restore_completed_window(context,checked(completed),driver,rt) if completed.exists() else execute_training(
        root,context,state,driver,rt=rt,monitor=monitor,resource_report=guard.report)
    body=dict(branch_result=binding.entry(completed),initial_step=1192,final_step=1490,
        optimizer_updates=298,new_optimizer_updates=298,outer_updates=0,applied=False,fixed_distribution=True,
        initial_learning_rate=OLD_LR,learning_rate=NEW_LR,learning_rate_intervention=result["learning_rate_intervention"],
        post_intervention_state_digest=result["post_intervention_state_digest"],fixed_distribution_digest=context["fixed_pi_digest"],
        final_checkpoint=result["final_checkpoint"],new_feedback_sessions=0,new_class_passes=0,new_response_replay=0,new_VJP=0,
        demonstration_materials=context["demonstration_materials"],actual_demonstration_consumption=result["actual_demonstration_consumption"])
    monitor.clear_unused("candidate_training_complete")
    del driver,model,tokenizer,optimizer,pool,state
    gc.collect();rt.torch.cuda.empty_cache();monitor.snapshot("after_model_release",boundary=True)
    return dict(body,point_context_id=context["id"],parent_state_digest=context["parent_state_digest"],
        seed=SEED,step=1192,stage="train",arm=ARM,condition=CONDITION,model_released=True)
