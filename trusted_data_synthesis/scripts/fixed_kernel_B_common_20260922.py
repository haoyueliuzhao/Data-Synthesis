"""Shared durable contracts for the frozen B replication and confirmation study."""

import fcntl
import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path

import fixed_kernel_delayed_C_autorun_state_20260921 as durable
import fixed_kernel_delayed_C_recovery_state_20260921 as s
import run_fixed_kernel_delayed_C_20260919 as d
import torch

p, old = d.p, d.old
RAW = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/delayed_C_B_confirmation_cache_20260922"
)
SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_B_common_20260922.py"
FLOORS = dict(SFT=32768, population=32768, feedback=51200, generation=57344)


class CapacityWait(BaseException):
    """A yield at a committed boundary, not a numerical failure."""


def emit(value):
    print(json.dumps(dict(at=p.now(), **value)), flush=True)


def write(path, value, immutable=True):
    path = Path(path)
    p.require(path.is_relative_to(RAW) and ".." not in path.parts, "B.confined_artifact_write")
    durable.write(path, value, immutable=immutable)
    return value


@contextmanager
def locked(path, *, blocking=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        yield stream


def read_protocol(root):
    value = p.checked(p.read_json(RAW / "protocol.json"), "B_confirm_protocol")
    p.require(
        value["frozen"] and value["candidate"] == "Delayed-C" and value["baseline"] == "Static",
        "B.frozen_candidate",
    )
    for name, digest in value["scientific_sources"].items():
        p.require(p.sha(Path(root) / name) == digest, "B.frozen_scientific_source:" + name)
    return value


def capacity_boundary(phase, required_MiB=None):
    required = FLOORS[phase] if required_MiB is None else required_MiB
    for check in range(4):
        torch.cuda.empty_cache()
        free, _ = torch.cuda.mem_get_info()
        capacity = (free + torch.cuda.memory_reserved()) / 2**20
        if capacity >= required:
            return
        emit(
            dict(
                event="B_waiting_at_saved_boundary",
                phase=phase,
                own_capacity_MiB=capacity,
                required_MiB=required,
            )
        )
        if check < 3:
            time.sleep(20)
    raise CapacityWait("GPU capacity unavailable at committed boundary")


def _component(value):
    value = str(value)
    p.require(bool(re.fullmatch(r"[A-Za-z0-9_.-]+", value)), "B.safe_ledger_component")
    return value


def _budget_state():
    path = RAW / "budget/state.json"
    return (
        p.read_json(path)
        if path.exists()
        else dict(counts={}, committed_generation={}, replay_required={}, updated_at=p.now())
    )


def reserve(kind, job_key, attempt, unit):
    """Charge before work. A crash between counter and receipt is conservatively overcharged."""
    plan = p.checked(p.read_json(RAW / "protocol.json"), "B_confirm_protocol")
    marker = (
        RAW
        / "budget/intents"
        / _component(kind)
        / _component(job_key)
        / _component(attempt)
        / (_component(unit) + ".json")
    )
    with locked(RAW / "budget.lock"):
        p.require(not marker.exists(), "B.no_unmetered_same_attempt_retry")
        state = _budget_state()
        current = state["counts"].get(kind, 0)
        cap = plan["physical_budget"][kind + "_cap"]
        p.require(current < cap, "B.physical_budget_exhausted:" + kind)
        if kind == "generate_call":
            credited = sum(row["calls"] for row in state["committed_generation"].values())
            p.require(
                current - credited < plan["physical_budget"]["incomplete_generate_call_cap"],
                "B.incomplete_generation_budget_exhausted",
            )
        if kind == "feedback_response":
            required = state["replay_required"][job_key]
            used = state["counts"].get("feedback_response:" + job_key, 0)
            p.require(
                used < required + plan["physical_budget"]["extra_replayed_responses_per_seed"],
                "B.feedback_replay_budget_exhausted",
            )
            state["counts"]["feedback_response:" + job_key] = used + 1
        state["counts"][kind] = current + 1
        state["updated_at"] = p.now()
        write(RAW / "budget/state.json", state, immutable=False)
        write(
            marker,
            dict(
                plan_id=plan["id"],
                kind=kind,
                job_key=job_key,
                attempt=attempt,
                unit=unit,
                reservation_number=current + 1,
                at=p.now(),
            ),
        )


def set_replay_required(job_key, responses):
    p.require(0 <= responses <= 360 * 32, "B.finite_registered_feedback_responses")
    with locked(RAW / "budget.lock"):
        state = _budget_state()
        old_value = state["replay_required"].get(job_key)
        p.require(
            old_value is None or old_value == responses, "B.fixed_sealed_feedback_replay_inventory"
        )
        state["replay_required"][job_key] = responses
        write(RAW / "budget/state.json", state, immutable=False)


def generation_committed(point_id, index, record):
    p.checked(record, "anchored_generated_trajectory")
    p.require(
        record["point_id"] == point_id
        and record["job"]["index"] == index
        and 0 <= record["actual_generate_calls"] <= 32,
        "B.committed_generation_identity",
    )
    with locked(RAW / "budget.lock"):
        state = _budget_state()
        key = point_id + ":" + str(index)
        value = dict(record_id=record["id"], calls=record["actual_generate_calls"])
        prior = state["committed_generation"].get(key)
        p.require(prior is None or prior == value, "B.one_committed_session_per_registered_job")
        state["committed_generation"][key] = value
        p.require(
            sum(row["calls"] for row in state["committed_generation"].values())
            <= state["counts"].get("generate_call", 0),
            "B.committed_calls_have_prior_reservations",
        )
        write(RAW / "budget/state.json", state, immutable=False)


def save_training(path, names, optimizer, step, report, plan_id, job_key):
    bound = old.adam.bind_adamw(names, optimizer, clip_max_norm=1.0)
    state = {}
    for parameter in bound.parameters:
        for prefix, value in (
            ("theta", parameter.theta),
            ("first_moment", parameter.first),
            ("second_moment", parameter.second),
        ):
            state[prefix + "/" + parameter.name] = value.detach().cpu().clone()
    s.atomic_torch(
        path,
        dict(
            kind="B_shared_training_state",
            plan_id=plan_id,
            job_key=job_key,
            completed_updates=step,
            snapshot=bound.snapshot,
            state=state,
            rng=s.capture_rng(step),
            update_report=report,
        ),
    )


def load_training(path, plan_id, allowed_job_keys, step=None):
    value = torch.load(path, map_location="cpu", weights_only=False)
    p.require(
        value["kind"] == "B_shared_training_state"
        and value["plan_id"] == plan_id
        and value["job_key"] in allowed_job_keys,
        "B.checkpoint_plan_and_lineage",
    )
    p.require(
        value["completed_updates"] == value["rng"]["schedule_cursor"]
        and (step is None or value["completed_updates"] == step),
        "B.checkpoint_schedule_cursor",
    )
    s.check_saved_state(value["state"], value["snapshot"], value["completed_updates"])
    return value


def restore_prefix_model(root, seed):
    plan = read_protocol(root)
    materials = plan["materials"]
    key = f"B_prefix_{seed}"
    report = p.read_json(RAW / "jobs" / key / "report.json")
    path = Path(report["checkpoint_path"])
    p.require(
        report["completed_updates"] == 200 and report["checkpoint_sha256"] == p.sha(path),
        "B.sealed_shared_prefix",
    )
    saved = load_training(path, plan["id"], [key], step=200)
    model, _ = old.trajectory_training.load_registered_student(
        materials["assets"]["base_binding"], seed, trainable=True
    )
    names = {name: value for name, value in model.named_parameters() if value.requires_grad}
    optimizer = old.trajectory_training.optimizer_factory(
        list(names.values()), materials["training_configuration"]
    )
    s.restore_optimizer(names, optimizer, saved["state"], saved["snapshot"], step=200)
    s.restore_rng(saved["rng"])
    return plan, report, saved, model, names, optimizer


def point_record(directory, model, theta, plan, run, *, step, kind, origin, source_manifest_id):
    """Same adapter and point contract as the frozen implementation; root is the data volume."""
    directory = Path(directory)
    path = directory / "point.json"
    actual_digest = old.gate.tensor_digest(theta)
    if path.exists():
        point = p.checked(p.read_json(path), "anchored_model_parameter_point")
        p.require(
            point["parameter_digest"] == actual_digest
            and point["run"] == run
            and point["step"] == step
            and point["source_manifest_id"] == source_manifest_id,
            "B.reused_identical_parameter_point",
        )
        return point
    directory.mkdir(parents=True, exist_ok=True)
    adapter_path = directory / "adapter.safetensors"
    if adapter_path.exists():
        adapter_path.rename(
            directory / ("uncommitted_adapter_" + str(time.time_ns()) + ".safetensors")
        )
    adapter = old.feedback.at_point(
        model, theta, lambda actual: old.components.save_adapter(actual, adapter_path)
    )
    with adapter_path.open("rb") as stream:
        os.fsync(stream.fileno())
    point = p.record(
        "anchored_model_parameter_point",
        point_kind=kind,
        run=run,
        step=step,
        origin_id=origin,
        source_manifest_id=source_manifest_id,
        parameter_digest=actual_digest,
        adapter=adapter,
        adapter_directory=str(directory.relative_to(RAW)),
        base_binding_id=plan["materials"]["assets"]["base_binding"]["id"],
    )
    write(path, point)
    return point
