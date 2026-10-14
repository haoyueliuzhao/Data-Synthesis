"""Pure, phase-specific V41 GPU admission policy; no GPU or runtime imports.

This module only decides whether an observed device has sufficient free memory.
It neither dispatches work nor relaxes any running-worker numerical/resource gate.
The controller owns global worker accounting and the one-project-worker GPU lease.
Callers must check fresh inventory both at dispatch and immediately before CUDA;
the latter caller must supply ``worker_pid`` and separately ensure CUDA is unstarted.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from types import MappingProxyType

GIB = 1024**3
MIB_PER_GIB = 1024
SHARDS = ("shard00", "shard01", "shard02", "shard03")
PHASE_MINIMUM_FREE_GIB = MappingProxyType(
    {
        "class": 28,
        "train": 32,
        "replay_R3": 48,
        "virtual_existing": 24,
        "virtual_first_sampling": 32,
        "distribution": 24,
        "generate": 48,
    }
)
_DIRECT_STAGES = frozenset(("train", "replay_R3", "distribution", "generate"))
_VIRTUAL_MODES = MappingProxyType(
    {"sealed_existing": "virtual_existing", "first_sampling": "virtual_first_sampling"}
)


class MemoryPolicyError(ValueError):
    """The requested phase or registration cannot use this fixed policy."""


def phase_key(stage: str, context: Mapping | None) -> str:
    """Map a real worker stage and the original context to one registered phase.

    In particular, callers cannot pass a cheap virtual-phase alias to bypass the
    original context's first-sampling mode. No unknown stage has a default budget.
    """
    if not isinstance(stage, str):
        raise MemoryPolicyError(f"unregistered GPU stage: {stage!r}")
    if stage in SHARDS:
        return "class"
    if stage in _DIRECT_STAGES:
        return stage
    if stage == "virtual_point":
        feedback = context.get("feedback") if isinstance(context, Mapping) else None
        mode = feedback.get("mode") if isinstance(feedback, Mapping) else None
        if not isinstance(mode, str) or mode not in _VIRTUAL_MODES:
            raise MemoryPolicyError("virtual_point requires sealed_existing or first_sampling mode")
        return _VIRTUAL_MODES[mode]
    raise MemoryPolicyError(f"unregistered GPU stage: {stage!r}")


def minimum_free_mib(stage: str, context: Mapping | None) -> int:
    """Return a fixed stage-specific admission threshold, not an observed peak."""
    return PHASE_MINIMUM_FREE_GIB[phase_key(stage, context)] * MIB_PER_GIB


def _positive_pid(value) -> bool:
    return type(value) is int and value > 0


def _valid_scope(scope) -> bool:
    if not isinstance(scope, Mapping):
        return False
    indices, uuids = scope.get("allowed_gpu_indices"), scope.get("gpu_uuids")
    if not isinstance(indices, (list, tuple)) or not indices or not isinstance(uuids, Mapping):
        return False
    if any(type(index) is not int or index not in range(8) for index in indices):
        return False
    if len(set(indices)) != len(indices):
        return False
    registered = [uuids.get(str(index)) for index in indices]
    return all(
        isinstance(uuid, str) and uuid.startswith("GPU-") and len(uuid) > 4 for uuid in registered
    ) and len(set(registered)) == len(registered)


def eligible_gpu(
    row: Mapping,
    protocol: Mapping,
    stage: str,
    context: Mapping | None,
    *,
    worker_pid: int | None = None,
) -> bool:
    """Accept shared devices only with complete identity and free-memory data.

    An external PID is no longer itself grounds for rejection. Missing/invalid
    inventory, a changed UUID, or this pre-CUDA worker already appearing in the
    compute-process inventory is always rejected. Leases, worker limits, host
    RAM, stop/deadline checks, and CUDA initialization state are caller duties.
    ``None`` for worker_pid is only intended for the CPU controller's dispatch
    decision; the actual worker must pass its identity before starting CUDA.
    """
    required_mib = minimum_free_mib(stage, context)
    if worker_pid is not None and not _positive_pid(worker_pid):
        raise MemoryPolicyError("worker_pid must be a positive integer when supplied")
    if not isinstance(row, Mapping) or not _valid_scope(protocol):
        return False
    index = row.get("index")
    if type(index) is not int or index not in protocol["allowed_gpu_indices"]:
        return False
    expected_uuid = protocol["gpu_uuids"][str(index)]
    if row.get("uuid") != expected_uuid:
        return False
    processes = row.get("processes")
    if not isinstance(processes, list):
        return False
    observed_pids = set()
    for process in processes:
        if not isinstance(process, Mapping) or not _positive_pid(process.get("pid")):
            return False
        pid = process["pid"]
        if pid == worker_pid or pid in observed_pids:
            return False
        if "gpu_uuid" in process and process["gpu_uuid"] != expected_uuid:
            return False
        observed_pids.add(pid)
    free_mib = row.get("free_mib")
    if isinstance(free_mib, bool) or not isinstance(free_mib, (int, float)):
        return False
    return math.isfinite(free_mib) and free_mib >= required_mib


def policy_record(*, scope: Mapping, evidence_refs: Sequence[Mapping]) -> dict:
    """Construct a registration body without reading files or changing state.

    The caller supplies verified evidence references and seals the returned body
    in a new protocol. Historical records and a live V40 protocol are not edited.
    """
    if not _valid_scope(scope):
        raise MemoryPolicyError("valid authorized physical GPU scope and UUID bindings required")
    if isinstance(evidence_refs, (str, bytes)) or not isinstance(evidence_refs, Sequence):
        raise MemoryPolicyError("evidence_refs must be a sequence of verified reference mappings")
    if not evidence_refs or any(not isinstance(ref, Mapping) for ref in evidence_refs):
        raise MemoryPolicyError("at least one verified resource-evidence reference required")
    return {
        "schema": "v41_phase_specific_shared_gpu_admission.v1",
        "scope": deepcopy(dict(scope)),
        "evidence_refs": [deepcopy(dict(ref)) for ref in evidence_refs],
        "minimum_free_gib_by_phase": dict(PHASE_MINIMUM_FREE_GIB),
        "virtual_feedback_modes": dict(_VIRTUAL_MODES),
        "evidence_interpretation": {
            "historical_observations_are_not_upper_bounds": True,
            "basis": "historical process-lifetime peak_reserved_bytes including model loading",
            "non_torch_and_cuda_allowance_gib": 1,
            "required_boundary_free_gib": 2,
            "additional_unobserved_variation_allowance_gib_at_least": 4,
            "thresholds_rounded_up_and_frozen_not_automatically_lowered": True,
            "whole_device_nvml_peaks_may_include_external_processes": True,
            "future_response_lengths_and_external_growth_not_bounded_by_observations": True,
        },
        "admission": {
            "external_compute_process_presence_is_not_a_veto": True,
            "complete_compute_process_identity_observation_required": True,
            "physical_uuid_match_required": True,
            "worker_own_compute_pid_forbidden_before_cuda": True,
            "cuda_uninitialized_check_required_in_worker": True,
            "fresh_check_at_dispatch_and_before_cuda": True,
            "gpu_lease_required": True,
            "maximum_total_workers_including_initializing_and_draining": 4,
            "maximum_project_workers_per_gpu": 1,
            "external_processes_must_not_be_interfered_with": True,
            "shared_device_competition_remains_a_risk": True,
            "automatic_retry": False,
            "deadline_or_wait_budget_reset": False,
        },
        "unchanged_runtime": {
            "maximum_historical_allocated_bytes": 76 * GIB,
            "minimum_boundary_free_bytes": 2 * GIB,
            "model_loading_counts_in_peak": True,
            "peak_resets_after_model_loading_begins": 0,
            "R3_nonKV_activation_residency_bytes": 16 * GIB,
            "mathematics_changed": False,
            "host_resource_gates_changed": False,
            "failure_stops_pool_without_automatic_retry": True,
        },
    }
