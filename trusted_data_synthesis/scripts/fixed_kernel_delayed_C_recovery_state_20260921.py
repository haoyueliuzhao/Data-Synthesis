"""Durable recovery of the stopped Delayed-C run; original artifacts stay immutable."""

import math
import os
import random
import time
from pathlib import Path

import numpy as np
import run_fixed_kernel_delayed_C_20260919 as d
import torch
from safetensors.torch import load_file

p, old = d.p, d.old
OUTPUT = d.inputs.BASE + "/delayed_C_recovery_20260921"
RAW = d.inputs.CACHE.parent / "delayed_C_recovery_cache_20260921"
MIN_OWN_CAPACITY_MIB = 61440


def atomic_torch(path, value):
    """An immutable complete checkpoint, made visible only after fsync."""
    path = Path(path)
    p.require(not path.exists(), "recovery.no_checkpoint_overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".partial.{os.getpid()}")
    with temporary.open("xb") as stream:
        torch.save(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.rename(temporary, path)
    handle = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


def capture_rng(cursor, *, cuda=True):
    return dict(
        cpu=torch.get_rng_state(),
        cuda=torch.cuda.get_rng_state_all() if cuda else [],
        python=random.getstate(),
        numpy=np.random.get_state(),
        schedule_cursor=cursor,
    )


def restore_rng(value, *, cuda=True):
    torch.set_rng_state(value["cpu"])
    random.setstate(value["python"])
    np.random.set_state(value["numpy"])
    if cuda:
        p.require(len(value["cuda"]) == torch.cuda.device_count() == 1, "recovery.one_CUDA_RNG")
        torch.cuda.set_rng_state_all(value["cuda"])


def check_saved_state(state, snapshot, step):
    expected = set()
    for row in snapshot["parameters"]:
        p.require(row["step"] == step and row["state_initialized"], "recovery.actual_Adam_step")
        for field, prefix in (
            ("parameter", "theta"),
            ("first_moment", "first_moment"),
            ("second_moment", "second_moment"),
        ):
            key = prefix + "/" + row["name"]
            expected.add(key)
            actual, wanted = state[key], row[field]
            p.require(
                list(actual.shape) == wanted["shape"]
                and str(actual.dtype) == wanted["dtype"]
                and p.sha(actual.contiguous().reshape(-1).view(torch.uint8).numpy().tobytes())
                == wanted["sha256"],
                "recovery.exact_saved_parameter_and_moments",
            )
    p.require(set(state) == expected, "recovery.no_extra_or_missing_state")


def restore_optimizer(names, optimizer, state, snapshot, *, step):
    check_saved_state(state, snapshot, step)
    p.require(set(names) == {row["name"] for row in snapshot["parameters"]}, "recovery.names")
    p.require(len(optimizer.param_groups) == len(snapshot["groups"]), "recovery.groups")
    identity = {id(value): name for name, value in names.items()}
    for group, wanted in zip(optimizer.param_groups, snapshot["groups"], strict=True):
        p.require(
            [identity[id(value)] for value in group["params"]] == wanted["parameter_names"],
            "recovery.optimizer_parameter_order",
        )
        for key in (
            "lr",
            "eps",
            "weight_decay",
            "maximize",
            "foreach",
            "fused",
            "capturable",
            "differentiable",
            "amsgrad",
        ):
            p.require(group.get(key) == wanted[key], "recovery.group_setting:" + key)
        p.require(tuple(group["betas"]) == (wanted["beta1"], wanted["beta2"]), "recovery.betas")
    optimizer.state.clear()
    for row in snapshot["parameters"]:
        name = row["name"]
        value = names[name]
        with torch.no_grad():
            value.copy_(state["theta/" + name].to(value.device))
        step_meta = row["step_storage"]
        p.require(step_meta["device"] == "cpu", "recovery.original_CPU_Adam_step")
        counter = torch.tensor(step, dtype=getattr(torch, step_meta["dtype"].split(".")[-1]))
        counter = counter.reshape(step_meta["shape"])
        p.require(old.adam._tensor_record(counter) == step_meta, "recovery.exact_step_storage")
        optimizer.state[value] = dict(
            step=counter,
            exp_avg=state["first_moment/" + name].to(value.device).clone(),
            exp_avg_sq=state["second_moment/" + name].to(value.device).clone(),
        )
    actual = old.adam.bind_adamw(names, optimizer, clip_max_norm=snapshot["clip"]["max_norm"])
    p.require(actual.snapshot == snapshot, "recovery.exact_live_optimizer_snapshot")
    return actual


def prefix(directory):
    info = p.read_json(directory / "full_G.json")
    values = load_file(str(directory / "real_point_and_optimizer.safetensors"), device="cpu")
    check_saved_state(values, info["optimizer_snapshot"], 200)
    rng = torch.load(directory / "prefix_RNG.pt", map_location="cpu", weights_only=False)
    p.require(rng["schedule_cursor"] == 200 and len(rng["cuda"]) == 1, "recovery.prefix_RNG")
    return values, info["optimizer_snapshot"], rng


def save_training(path, names, optimizer, step, report, plan_id, run_key):
    bound = old.adam.bind_adamw(names, optimizer, clip_max_norm=1.0)
    state = {}
    for row in bound.parameters:
        for prefix, value in (
            ("theta", row.theta),
            ("first_moment", row.first),
            ("second_moment", row.second),
        ):
            state[prefix + "/" + row.name] = value.detach().cpu().clone()
    atomic_torch(
        path,
        dict(
            kind="delayed_C_recovery_training",
            plan_id=plan_id,
            run_key=run_key,
            completed_updates=step,
            snapshot=bound.snapshot,
            state=state,
            rng=capture_rng(step),
            update_report=report,
        ),
    )


def compare_replayed_update(actual, original, *, atol=1e-8, rtol=1e-5):
    """A necessary live gate on every duplicated SFT step, not a new evaluation."""
    for key in (
        "tasks",
        "packages",
        "target_tokens",
        "sequence_tokens",
        "optimizer_step_calls",
        "physical_package_count",
        "packages_completed",
        "rows_completed",
        "loss_rule",
    ):
        p.require(actual[key] == original[key], "recovery.same_replayed_update:" + key)
    pairs = [(actual[key], original[key]) for key in ("weighted_loss", "preclip_gradient_norm")]
    p.require(
        len(actual["package_losses"]) == len(original["package_losses"]), "recovery.package_count"
    )
    for one, two in zip(actual["package_losses"], original["package_losses"], strict=True):
        p.require(
            one["package_id"] == two["package_id"] and one["target_tokens"] == two["target_tokens"],
            "recovery.same_replayed_package",
        )
        pairs.append((one["target_nll_sum"], two["target_nll_sum"]))
    p.require(
        all(math.isclose(a, b, abs_tol=atol, rel_tol=rtol) for a, b in pairs),
        "recovery.replayed_loss_or_gradient_mismatch_STOP",
    )
    return dict(
        exact_report_id=actual["id"] == original["id"],
        atol=atol,
        rtol=rtol,
        maximum_absolute_difference=max(abs(a - b) for a, b in pairs),
    )


def wait_capacity(event):
    """Do not evict other users. Wait at a durable boundary when own headroom shrinks."""
    while True:
        torch.cuda.empty_cache()
        free, _ = torch.cuda.mem_get_info()
        own_capacity = (free + torch.cuda.memory_reserved()) / 2**20
        if own_capacity >= MIN_OWN_CAPACITY_MIB:
            return
        event(
            dict(
                event="waiting_for_GPU_headroom",
                own_capacity_MiB=own_capacity,
                required_MiB=MIN_OWN_CAPACITY_MIB,
            )
        )
        time.sleep(20)


def recovery_budget(completed):
    p.require(completed == {11: 400, 29: 200, 47: 303}, "recovery.fixed_failed_attempt_inventory")
    return dict(
        original_completed_optimizer_updates=sum(completed.values()),
        resumed_optimizer_updates=400,
        repeated_completed_optimizer_updates=103,
        cumulative_completed_optimizer_updates=1303,
        effective_final_optimizer_updates=1200,
        original_partial_step304_optimizer_updates=0,
        new_feedback_sessions=0,
        new_private_feedback_scores=0,
        reused_feedback_sessions=720,
        new_final_greedy_sessions=360,
        new_final_generate_call_cap=11520,
        extra_successful_class_passes=1,
        maximum_class_pass_attempts=3,
        repeated_original_feedback_responses=58,
        required_seed29_feedback_responses=631,
        maximum_resource_failures_per_run=3,
        B_and_confirmation=0,
    )
