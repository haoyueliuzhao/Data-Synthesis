"""Empirical host admission with unchanged V43 GPU and runtime resource gates."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path


def _load():
    name = __name__ + "_sealed_v43_admission"
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name("finqa_v43_admission.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


original = _load()
_original_validate = original.validate_plan
GIB = 1024**3
DISPATCH_ORDER = (5, 2, 0, 4, 3, 7, 1, 6)
HOST_POLICY_SCHEMA = "v45_empirical_phase_specific_host_admission.v1"
HOST_RESERVE_BYTES = 96 * GIB
STARTUP_BUDGET_GIB = dict(
    class_=160, train=48, replay_R3=48, generate=48, virtual_point=64, distribution=64
)
STARTUP_BUDGET_GIB["class"] = STARTUP_BUDGET_GIB.pop("class_")
HISTORICAL_PEAK_BYTES = dict(
    class_=133719773184,
    replay_R3=17644838912,
    generate=16537333760,
    virtual_point=31447461888,
    distribution=31753560064,
    train=17538539520,
)
HISTORICAL_PEAK_BYTES["class"] = HISTORICAL_PEAK_BYTES.pop("class_")
EVIDENCE_REF = dict(
    path="/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/"
    "v25_training_replication_01/production_resume_01/host_memory_admission_evidence_01/record.json",
    sha256="7a8fa852f8650d1b26161b83bd9c04413383ea26f7d48ba2a1ab209f2a6b7246",
    id="5e87ca240e266595c3dbf34bd9013cf61db961232209b5d94b34903447970ad0",
)
SUMMARY_SHA256 = "7d9581c3ec7392a772debca512f9d3a5f5ab4038559ced6d9416cf2af934e87b"


def host_phase(stage):
    if stage in original.SHARDS:
        return "class"
    original._require(
        stage in STARTUP_BUDGET_GIB and stage != "class", "unknown registered host-memory stage"
    )
    return stage


def startup_budget_bytes(stage):
    return STARTUP_BUDGET_GIB[host_phase(stage)] * GIB


def padded_peak_bytes(peak_bytes):
    original._require(
        type(peak_bytes) is int and peak_bytes >= 0, "invalid peak for host-memory padding"
    )
    quantum = 16 * GIB
    # Exact integer ceil-to-16GiB(9/8 * peak + 16GiB), without float rounding.
    numerator = 9 * peak_bytes + 8 * quantum
    return ((numerator + 8 * quantum - 1) // (8 * quantum)) * quantum


def host_policy_record(*, evidence_refs=None):
    references = [dict(EVIDENCE_REF)] if evidence_refs is None else evidence_refs
    original._require(
        references == [EVIDENCE_REF], "unregistered host-admission evidence reference"
    )
    return dict(
        schema=HOST_POLICY_SCHEMA,
        evidence_refs=[dict(reference) for reference in references],
        historical_summary_sha256=SUMMARY_SHA256,
        historical_successful_process_count=91,
        historical_peak_bytes_by_phase=dict(HISTORICAL_PEAK_BYTES),
        startup_budget_bytes_by_phase={
            phase: value * GIB for phase, value in STARTUP_BUDGET_GIB.items()
        },
        host_reserve_bytes=HOST_RESERVE_BYTES,
        runtime_rss_limit_bytes={"class": 160 * GIB, "other": 192 * GIB},
        padding=dict(
            peak_multiplier_numerator=9,
            peak_multiplier_denominator=8,
            additive_margin_bytes=16 * GIB,
            round_up_multiple_bytes=16 * GIB,
        ),
        dynamic_unconsumed_reservation="max(0,max(startup_budget,padded_lifetime_peak)-current_RSS)",
        current_RSS_alone_is_not_future_peak_estimate=True,
        missing_or_invalid_live_memory="defer_dispatch_without_zero_fallback_or_pool_stop",
        unknown_stage_or_policy="hard_error",
        historical_peaks_are_not_future_upper_bounds=True,
        host_runtime_hard_gates_unchanged=True,
        GPU_admission_and_runtime_memory_gates_unchanged=True,
    )


def host_memory_requirement(stage, active):
    """Required current effective RAM, or None for an untrustworthy live reading.

    Missing/exiting process observations defer new dispatch; they are never zero
    RSS. Existing workers retain their original hard runtime gates. Unknown
    stages are registration errors, not resource scarcity.
    """
    needed = HOST_RESERVE_BYTES + startup_budget_bytes(stage)
    if not isinstance(active, (list, tuple)):
        return None
    for row in active:
        if not isinstance(row, dict):
            return None
        phase = host_phase(row.get("stage"))
        rss, peak = row.get("rss_bytes"), row.get("peak_rss_bytes")
        hard_limit = (160 if phase == "class" else 192) * GIB
        if (
            row.get("observed", True) is not True
            or type(rss) is not int
            or type(peak) is not int
            or not 0 <= rss <= peak <= hard_limit
        ):
            return None
        reservation = max(STARTUP_BUDGET_GIB[phase] * GIB, padded_peak_bytes(peak))
        needed += max(0, reservation - rss)
    return needed


def __getattr__(name):
    return getattr(original, name)


def validate_plan(plan):
    _original_validate(plan)
    original._require(
        plan.get("max_gpu_workers") == 5
        and plan.get("max_workers_per_gpu") == 1
        and plan["gpu_admission_policy"]["admission"][
            "maximum_total_workers_including_initializing_and_draining"
        ]
        == 5
        and plan["gpu_admission_policy"]["admission"]["maximum_project_workers_per_gpu"] == 1,
        "V45 requires exactly the authorized five-slot, one-worker-per-GPU envelope",
    )
    original._require(
        plan.get("host_admission_policy") == host_policy_record()
        and plan.get("host_ram_admission_changed") is True
        and plan.get("host_ram_runtime_hard_gates_unchanged") is True,
        "V45 registered empirical host policy or unchanged hard gates differ",
    )
    original._require(
        plan.get("dispatch_priority") == list(DISPATCH_ORDER),
        "V45 must prefer authorized GPU5 and GPU2 in the registered order",
    )
    return plan


def wait_for_pre_cuda_admission(*args, **kwargs):
    readers = ("inventory", "host_memory", "process_memory", "birth")
    if any(kwargs.get(key) is None for key in readers):
        control = importlib.import_module("finqa_v45_controller")
        for key in readers:
            if kwargs.get(key) is None:
                kwargs[key] = getattr(control, key)
    previous = original.validate_plan
    original.validate_plan = validate_plan
    try:
        return original.wait_for_pre_cuda_admission(*args, **kwargs)
    finally:
        original.validate_plan = previous
