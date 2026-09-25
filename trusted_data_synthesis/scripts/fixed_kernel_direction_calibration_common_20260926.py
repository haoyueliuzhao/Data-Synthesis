"""Finite, separately registered B direction-reliability execution contracts."""

import re
from pathlib import Path

import fixed_kernel_B_common_20260922 as b

p, s, old, torch = b.p, b.s, b.old, b.torch
RAW = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "qa_vnext_fixed_kernel_value/direction_calibration_cache_20260926"
)
SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_direction_calibration_common_20260926.py"
CapacityWait = b.CapacityWait
capacity_boundary, locked, emit = b.capacity_boundary, b.locked, b.emit
_verified = {}


def write(path, value, immutable=True):
    path = Path(path)
    p.require(
        path.resolve().is_relative_to(RAW.resolve()) and ".." not in path.parts,
        "direction.confined_new_artifact",
    )
    b.durable.write(path, value, immutable=immutable)
    return value


def read_protocol(root):
    plan = p.checked(p.read_json(RAW / "protocol.json"), "B_direction_reliability_protocol")
    parent = b.read_protocol(root)
    p.require(
        plan["frozen"]
        and plan["parent_B_protocol_id"] == parent["id"]
        and plan["seeds"] == [11, 29, 47]
        and plan["new_feedback_sessions"] == plan["new_scoring_cases"] == 0,
        "direction.frozen_existing_feedback_only",
    )
    for name, expected in plan["sources"].items():
        p.require(p.sha(Path(root) / name) == expected, "direction.frozen_source:" + name)
    return plan


def require_input(plan, seed, name):
    reference = plan["reliability_inputs"][str(seed)]["files"][name]
    path = Path(reference["path"])
    p.require(path.is_absolute() and path.is_relative_to(b.RAW), "direction.original_B_input")
    stat = path.stat()
    key = (str(path), reference["sha256"], stat.st_size, stat.st_mtime_ns)
    if key not in _verified:
        p.require(
            stat.st_size == reference["bytes"] and p.sha(path) == reference["sha256"],
            "direction.frozen_input_bytes:" + name,
        )
        _verified[key] = True
    return path


def _component(value):
    value = str(value)
    p.require(bool(re.fullmatch(r"[A-Za-z0-9_.-]+", value)), "direction.safe_budget_key")
    return value


def reserve(kind, job_key, attempt, unit):
    plan = p.checked(p.read_json(RAW / "protocol.json"), "B_direction_reliability_protocol")
    marker = (
        RAW
        / "budget/intents"
        / _component(kind)
        / _component(job_key)
        / _component(attempt)
        / (_component(unit) + ".json")
    )
    with locked(RAW / "budget.lock"):
        p.require(not marker.exists(), "direction.no_same_attempt_unmetered_repeat")
        path = RAW / "budget/state.json"
        state = p.read_json(path) if path.exists() else dict(counts={}, at=p.now())
        used = state["counts"].get(kind, 0)
        p.require(
            kind in plan["physical_budget"] and used < plan["physical_budget"][kind],
            "direction.physical_budget_exhausted:" + kind,
        )
        if kind == "reliability_response":
            required = {
                v["job_key"]: v["required_responses"] for v in plan["reliability_inputs"].values()
            }
            p.require(job_key in required, "direction.only_registered_seed")
            slot = kind + ":" + job_key
            per_seed = state["counts"].get(slot, 0)
            p.require(
                per_seed < required[job_key] + plan["extra_responses_per_seed"],
                "direction.per_seed_replay_cap",
            )
            state["counts"][slot] = per_seed + 1
        state["counts"][kind] = used + 1
        state["at"] = p.now()
        # Counter first: a crash may conservatively overcharge, never silently undercount.
        write(path, state, immutable=False)
        write(
            marker,
            dict(
                protocol_id=plan["id"],
                kind=kind,
                job_key=job_key,
                attempt=attempt,
                unit=unit,
                reservation=used + 1,
                at=p.now(),
            ),
        )
