"""GPU0-only sequential continuation after an explicitly authorized durable stop.

The original 81 scientific files remain byte-identical. Finish remaining Full251
training first, then all other original training and endpoint work on GPU0 only.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import finqa_v40_signals as stop_signals
import finqa_v43_time_policy as time_policy
import finqa_v50_admission as admission
import finqa_v50_inheritance as inheritance
import finqa_v50_reservation as reservation

memory_policy = admission

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
SOURCE_ROOT = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01/v25_training_replication_01"
)
PARENT_ROOT = SOURCE_ROOT / "production_resume_01/host_memory_admission_01"
SOURCE_BUNDLE = PARENT_ROOT / "implementation"
LIVE_PARENT_ROOT = SOURCE_ROOT / "production_resume_01/resource_deferral_recovery_01"
ROOT = SOURCE_ROOT / "production_resume_01/single_gpu0_01"
DEFAULT_HANDOFF_RECORD = SOURCE_ROOT / (
    "production_resume_01/concurrency_four_01/"
    "superseded_single_gpu5_01/closeout/record.json"
)
FINAL_DEVICE_AUTHORIZATION_RECORD = (
    DEFAULT_HANDOFF_RECORD.parent.parent / "final_device_authorization/record.json"
)
RECOVERY_REVISION = "single_gpu0_full251_first_sequential_continuation_r1"
SOURCE_PROTOCOL_ID = "920ff2da160a3bbf055c6c3a5b0e9b3a080ca421deb90efce950959f17f735bf"
SOURCE_IMPLEMENTATION_ID = "c32c3a60ec4b3fa5c943bfa740cf53bdf985d7da7587f664c068ea8058857a6d"
PROTOCOL_SCHEMA = "v50_single_gpu0_supervised_protocol.v1"
FILES = (
    "finqa_v50_controller.py",
    "finqa_v50_supervisor.py",
    "finqa_v50_inheritance.py",
    "finqa_v50_reservation.py",
    "finqa_v50_cold_worker.py",
    "finqa_v50_worker.py",
    "finqa_v50_evaluation.py",
    "finqa_v50_admission.py",
)
ALLOWED_GPUS = (0,)
MAX_GPU_WORKERS = 1
DISPATCH_ORDER = (0,)
DISPATCH_POLL_SECONDS = 2


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


_runtime_directory = (
    Path(__file__).resolve().parent
    if Path(__file__).resolve().parent.name == "implementation"
    else SOURCE_BUNDLE
)
runtime = _module(_runtime_directory / "finqa_v43_controller.py", __name__ + "_runtime_v43")
verifier = _module(SOURCE_BUNDLE / "finqa_v45_controller.py", __name__ + "_historical_v45")
base, parent = runtime.base, runtime.parent
require, checked, publish = parent.require, parent.checked, parent.publish
entry, read_ref, file_ref = parent.entry, parent.read_ref, parent.file_ref
now, sha, birth, status = parent.now, parent.sha, parent.birth, parent.status
DurablePause = parent.DurablePause
_original_check_result = runtime._original_check_result
_original_module = runtime._original_module


def __getattr__(name):
    return getattr(runtime, name)


def allowed_root(root):
    root = Path(root).resolve()
    return root == ROOT or (
        root.parent == ROOT / "attempts"
        and root.name.startswith("attempt")
        and len(root.name) >= 11
        and root.name[7:].isdigit()
        and int(root.name[7:]) >= 2
    )


def device_capacity(protocol=None):
    indices = ALLOWED_GPUS if protocol is None else protocol["allowed_gpu_indices"]
    require(
        bool(indices) and len(indices) == len(set(indices)) and set(indices) <= set(ALLOWED_GPUS),
        "registered device capacity is invalid",
    )
    return len(indices)


def checked_source_bundle():
    protocol = verifier.checked_protocol(PARENT_ROOT)
    value = checked(SOURCE_BUNDLE / "record.json")
    require(
        protocol["id"] == SOURCE_PROTOCOL_ID
        and value["id"] == SOURCE_IMPLEMENTATION_ID
        and len(value["sha256"]) == 81,
        "the stopped V45 scientific source identity changed",
    )
    return value


def freeze(root, commit):
    commit = subprocess.check_output(
        ["git", "rev-parse", commit + "^{commit}"], cwd=REPO, text=True
    ).strip()
    old = checked_source_bundle()
    sources = {name: (SOURCE_BUNDLE / name).read_bytes() for name in old["sha256"]}
    for name, raw in sources.items():
        require(
            hashlib.sha256(raw).hexdigest() == old["sha256"][name],
            "original scientific bytes changed during freeze: " + name,
        )
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=REPO)
        require(
            hashlib.sha256(raw).hexdigest() == sha(REPO / relative),
            "uncommitted V50 source: " + name,
        )
        sources[name] = raw
    require(len(sources) == 89, "eight new and 81 byte-identical original files required")
    directory = Path(root) / "implementation"
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (directory / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    return publish(
        directory / "record.json",
        dict(
            schema="v50_phase_reservation_committed_implementation.v1",
            at=now(),
            source_commit=commit,
            committed_files=list(FILES),
            original_implementation=entry(SOURCE_BUNDLE / "record.json"),
            original_files_modified=False,
            sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        ),
    )


def checked_implementation(root=ROOT):
    root = Path(root).resolve()
    require(allowed_root(root), "unregistered V50 recovery root")
    value, old = checked(root / "implementation/record.json"), checked_source_bundle()
    require(
        value["schema"] == "v50_phase_reservation_committed_implementation.v1"
        and value["committed_files"] == list(FILES)
        and len(value["sha256"]) == 89
        and set(value["sha256"]) == set(old["sha256"]) | set(FILES)
        and value["original_implementation"] == entry(SOURCE_BUNDLE / "record.json"),
        "V50 execution ownership changed",
    )
    for name, expected in value["sha256"].items():
        require(sha(root / "implementation" / name) == expected, "frozen bytes changed: " + name)
        if name in old["sha256"]:
            require(expected == old["sha256"][name], "original V45 source modified")
    if root != ROOT:
        require(
            value == checked(ROOT / "implementation/record.json"),
            "automatic attempt changed frozen implementation",
        )
    return value


def policy_record():
    value = admission.gpu_policy_record()
    require(
        value["admission"]["maximum_total_workers_including_initializing_and_draining"] == 1
        and value["admission"]["maximum_project_workers_per_gpu"] == 1,
        "one total worker on GPU0, including initialization and draining",
    )
    return value


def host_policy_record():
    value = verifier.host_policy_record()
    require(
        isinstance(value.get("evidence_refs"), list) and value["evidence_refs"],
        "measured host policy needs evidence",
    )
    for reference in value["evidence_refs"]:
        read_ref(reference)
    return value


def reservation_policy_record():
    value = admission.reservation_policy_record()
    references = value.get("evidence_refs")
    require(
        isinstance(references, list) and references,
        "phase-sized reservation requires registered evidence",
    )
    for reference in references:
        read_ref(reference)
    return value


def live_parent_protocol(parentroot):
    """Read the actual stopped V48 parent without rewriting its protocol."""
    parentroot = Path(parentroot).resolve()
    require(
        parentroot == LIVE_PARENT_ROOT
        or (parentroot.parent == LIVE_PARENT_ROOT / "attempts"
            and parentroot.name.startswith("attempt")
            and parentroot.name[7:].isdigit()),
        "the handoff parent must belong to the current V48 supervision root",
    )
    plan = checked(parentroot / "protocol/record.json")
    require(
        plan["output_root"] == str(parentroot)
        and plan["supervision_root"] == str(LIVE_PARENT_ROOT)
        and plan["schema"] == "v48_resource_deferral_supervised_protocol.v1",
        "V50 handoff must inherit the actual V48 owner",
    )
    return plan


def _capacity_wait_reference(parentroot):
    parentroot = Path(parentroot).resolve()
    if not allowed_root(parentroot):
        return None
    number = 1 if parentroot == ROOT else int(parentroot.name.removeprefix("attempt"))
    path = ROOT / "supervisor" / f"attempt{number:04d}" / "capacity_wait/record.json"
    if not path.exists():
        return None
    value = checked(path)
    require(
        value["schema"] == "v50_supervisor_capacity_change_wait.v1"
        and value["parent_attempt_root"] == str(parentroot)
        and value["manual_stop_requested"] is False
        and value["capacity_ready"] is True
        and type(value["actual_elapsed_seconds"]) in (int, float)
        and math.isfinite(value["actual_elapsed_seconds"])
        and value["actual_elapsed_seconds"] >= 0,
        "capacity wait cannot be inherited without successful bound completion",
    )
    return entry(path)


def _additional_supervisor_wait(root):
    authority = checked(_active_authorization_path(root))
    reference = authority.get("supervisor_capacity_wait")
    if reference is None:
        return 0
    value = read_ref(reference)
    parent_protocol = read_ref(authority["parent_protocol"])
    require(
        value["schema"] == "v50_supervisor_capacity_change_wait.v1"
        and value["manual_stop_requested"] is False
        and value["capacity_ready"] is True
        and value["parent_attempt_root"] == parent_protocol["output_root"]
        and reference == _capacity_wait_reference(parent_protocol["output_root"]),
        "invalid inherited supervisor capacity wait",
    )
    elapsed = value["actual_elapsed_seconds"]
    require(
        type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0,
        "invalid capacity wait elapsed accounting",
    )
    return math.ceil(elapsed)


def _active_authorization_path(root):
    return Path(root).resolve() / "authorization/record.json"

def recovery_capacity_snapshot(conditions):
    require(
        isinstance(conditions, list) and conditions,
        "capacity recovery requires explicit typed conditions",
    )
    try:
        rows = parent.inventory()
    except (OSError, subprocess.CalledProcessError, TimeoutError) as error:
        return dict(ready=False, observation_error=type(error).__name__, inventory=[])
    readiness = [admission.check_retry_capacity(condition, rows) for condition in conditions]
    require(all(type(value) is bool for value in readiness), "invalid capacity readiness result")
    return dict(
        ready=all(readiness),
        condition_ready=readiness,
        inventory=[{key: row.get(key) for key in ("index", "uuid", "free_mib")} for row in rows],
    )


def authorization_body(*, parentroot, automatic):
    return dict(
        schema="v50_single_gpu0_authority.v1", at=now(),
        user_instruction="GPU5余量是否充足？考虑在GPU0运行后续程序",
        user_consent="改为GPU0单卡完成全部（推荐）",
        single_gpu0_authorized=True,
        final_device_authorization=entry(FINAL_DEVICE_AUTHORIZATION_RECORD),
        resource_retirement_authorized=True,
        explicit_parent_pause_recovery_authorized=not automatic,
        clean_handoff_authorized=False,
        source_supervision_root=str(ROOT if automatic else LIVE_PARENT_ROOT),
        pre_scientific_resource_wait_authorized=True,
        pre_model_resource_recovery_authorized=False,
        pre_scientific_wait_is_same_process=True,
        waiting_worker_retains_gpu_lease_and_slot=True,
        capacity_wait_does_not_stop_healthy_workers=True,
        no_scientific_operation_retried_during_resource_wait=True,
        recovery_revision=RECOVERY_REVISION,
        failed_registration_recovery_authorized=False,
        failed_registration_restarted_in_place=False,
        total_worker_limit_removed=False,
        independent_total_worker_limit=MAX_GPU_WORKERS,
        max_gpu_workers=MAX_GPU_WORKERS, max_workers_per_gpu=1,
        effective_device_capacity=device_capacity(),
        allowed_gpu_indices=list(ALLOWED_GPUS),
        steady_gpu_indices=[0], steady_max_gpu_workers=1,
        temporary_gpu0_full251_train_only=False,
        gpu_execution_policy=admission.execution_policy_record(),
        dispatch_priority=list(DISPATCH_ORDER),
        dispatch_poll_seconds=DISPATCH_POLL_SECONDS,
        fixed_gpu_reservation_authorized=True,
        phase_sized_shared_reservation_authorized=True,
        whole_device_exclusivity_required=False,
        mandatory_fixed_72GiB_pool=False,
        host_ram_runtime_hard_gates_unchanged=True,
        host_ram_admission_changed_from_parent=False,
        time_limits_removed=True, automatic_recovery_authorized=True,
        unknown_feedback_retry_allowed=False, automatic_attempt=automatic,
        known_failure_recovery_authorized=False,
        parent_failure=entry(Path(parentroot) / "failure/record.json"),
        parent_protocol=entry(Path(parentroot) / "protocol/record.json"),
        original_mathematical_parent_protocol=entry(PARENT_ROOT / "protocol/record.json"),
        original_mathematical_parent_failure=entry(PARENT_ROOT / "failure/record.json"),
        supervisor_capacity_wait=_capacity_wait_reference(parentroot) if automatic else None,
        new_sampling_or_optimizer_dose_authorized=False,
        logical_class_shards=4, manual_stop_terminates_supervision=True,
    )

def prepare(root=ROOT, *, source_commit, parentroot=LIVE_PARENT_ROOT,
            handoff_record=DEFAULT_HANDOFF_RECORD):
    root, parentroot = Path(root).resolve(), Path(parentroot).resolve()
    require(root == ROOT and not root.exists(), "one fresh V50 resource retirement")
    live_parent_protocol(parentroot)
    reference = handoff_record if isinstance(handoff_record, dict) else entry(handoff_record)
    authority = dict(authorization_body(parentroot=parentroot, automatic=False),
                     resource_retirement_receipt=reference)
    preview = inheritance.inspect_parent_handoff(
        root, parentroot, handoff_record=reference, authorization_body=authority)
    gpu_policy, host_policy, resource_policy = (
        policy_record(), host_policy_record(), reservation_policy_record())
    implementation = freeze(root, source_commit)
    publish(root / "authorization/record.json", authority)
    publish(root / "preflight/record.json", preview)
    return publish(root / "preparation/record.json", dict(
        schema="v50_single_gpu0_retirement_preparation.v1", at=now(),
        implementation=entry(root / "implementation/record.json"),
        source_commit=implementation["source_commit"],
        authorization=entry(root / "authorization/record.json"),
        parent_root=str(parentroot), parent_protocol=entry(parentroot / "protocol/record.json"),
        parent_pause=entry(parentroot / "failure/record.json"),
        resource_retirement_receipt=reference,
        recovery_preflight=entry(root / "preflight/record.json"),
        source_supervision_root=str(LIVE_PARENT_ROOT), recovery_revision=RECOVERY_REVISION,
        gpu_admission_policy=gpu_policy, host_admission_policy=host_policy,
        gpu_reservation_policy=resource_policy,
        gpu_execution_policy=admission.execution_policy_record(),
        max_gpu_workers=MAX_GPU_WORKERS, independent_total_worker_limit=MAX_GPU_WORKERS,
        total_worker_limit_removed=False, effective_device_capacity=device_capacity(),
        steady_gpu_indices=[0], steady_max_gpu_workers=1, max_workers_per_gpu=1,
        scientific_controller_started=False, historical_parent_modified=False,
        parent_durable_pause_required=True, live_handoff_required=False,
    ))


def checked_preparation():
    value = checked(ROOT / "preparation/record.json")
    parentroot = Path(value["parent_root"])
    require(
        value["schema"] == "v50_single_gpu0_retirement_preparation.v1"
        and value["implementation"] == entry(ROOT / "implementation/record.json")
        and value["authorization"] == entry(ROOT / "authorization/record.json")
        and value["parent_protocol"] == entry(parentroot / "protocol/record.json")
        and value["parent_pause"] == entry(parentroot / "failure/record.json")
        and value["source_supervision_root"] == str(LIVE_PARENT_ROOT)
        and value["recovery_revision"] == RECOVERY_REVISION
        and value["gpu_admission_policy"] == policy_record()
        and value["host_admission_policy"] == host_policy_record()
        and value["gpu_reservation_policy"] == reservation_policy_record()
        and value["gpu_execution_policy"] == admission.execution_policy_record()
        and value["max_gpu_workers"] == value["independent_total_worker_limit"] == 1
        and value["total_worker_limit_removed"] is False
        and value["effective_device_capacity"] == 1
        and value["steady_gpu_indices"] == [0] and value["steady_max_gpu_workers"] == 1
        and value["max_workers_per_gpu"] == 1
        and value["parent_durable_pause_required"] is True
        and value["live_handoff_required"] is False,
        "V50 retirement preparation changed",
    )
    read_ref(value["resource_retirement_receipt"])
    read_ref(value["recovery_preflight"])
    live_parent_protocol(parentroot)
    return value

def protocol_body(root, implementation, initial, *, at):
    root = Path(root).resolve()
    preparation = checked_preparation()
    inherited = checked(root / "inheritance/record.json")
    additional_wait = _additional_supervisor_wait(root)
    old = read_ref(inherited["parent_protocol"])
    body = copy.deepcopy({key: value for key, value in old.items() if key != "id"})
    body.update(
        schema=PROTOCOL_SCHEMA,
        at=at,
        output_root=str(root),
        supervision_root=str(ROOT),
        implementation_id=implementation["id"],
        source_commit=implementation["source_commit"],
        recovery_revision=RECOVERY_REVISION,
        failed_registration_restarted_in_place=False,
        authority="先在GPU0完成Full251末段训练，然后仅GPU0单worker串行完成全部剩余工作；资源硬门与剂量不变",
        pre_scientific_resource_wait=dict(
            schema="v50_pre_scientific_resource_wait_policy.v1",
            same_process_only=True,
            gpu_lease_and_worker_slot_retained=True,
            model_load_and_scientific_work_must_not_have_started=True,
            typed_capacity_shortage_only=True,
            healthy_workers_and_other_device_dispatch_continue=True,
            poll_seconds=2,
            heartbeat_max_age_seconds=60,
            wall_time_limit_seconds=None,
            no_scientific_operation_retry=True,
            manual_stop_is_terminal=True,
            binding_numeric_and_unknown_feedback_failures_are_not_capacity_waits=True,
        ),
        authorization=entry(_active_authorization_path(root)),
        audit=entry(root / "activation_registration/record.json"),
        preparation=entry(ROOT / "preparation/record.json"),
        parent_protocol=inherited["parent_protocol"],
        parent_failure=inherited["parent_pause"],
        inheritance=entry(root / "inheritance/record.json"),
        initial_state_snapshot=entry(root / "initial_state/record.json"),
        initial_progress=dict(
            completed_optimizer_updates=initial["completed_physical_updates"],
            remaining_optimizer_updates=initial["remaining_physical_updates"],
            completed_outer_updates=initial["completed_outers"],
            remaining_outer_updates=initial["remaining_outers"],
            **inherited["remaining_scientific_budget"],
        ),
        gpu_admission_policy=preparation["gpu_admission_policy"],
        host_admission_policy=preparation["host_admission_policy"],
        gpu_reservation_policy=preparation["gpu_reservation_policy"],
        allowed_gpu_indices=list(ALLOWED_GPUS),
        gpu_uuids=dict(admission.GPU_UUIDS), cpu_affinity=dict(admission.CPU_AFFINITY),
        gpu_execution_policy=admission.execution_policy_record(),
        steady_gpu_indices=[0], steady_max_gpu_workers=1,
        temporary_gpu0_full251_train_only=False,
        max_gpu_workers=MAX_GPU_WORKERS,
        independent_total_worker_limit=MAX_GPU_WORKERS,
        total_worker_limit_removed=False,
        max_workers_per_gpu=1,
        effective_device_capacity=device_capacity(),
        dispatch_priority=list(DISPATCH_ORDER),
        dispatch_poll_seconds=DISPATCH_POLL_SECONDS,
        host_ram_admission_changed=True,
        host_ram_admission_changed_from_parent=False,
        host_ram_runtime_hard_gates_unchanged=True,
        logical_class_shards=4,
        inherited_resource_wait_seconds=inherited["inherited_resource_wait_seconds"]
        + additional_wait,
        inherited_parent_resource_wait_seconds=inherited["inherited_resource_wait_seconds"],
        additional_supervisor_resource_wait_seconds=additional_wait,
        supervisor_capacity_wait=checked(_active_authorization_path(root)).get(
            "supervisor_capacity_wait"
        ),
        inherited_pilot_acceptance=entry(PARENT_ROOT / "pilot_acceptance/record.json"),
        pilot_repeated=False,
        clean_handoff_claimed=False,
        resource_retirement_receipt=preparation["resource_retirement_receipt"],
        manually_authorized_known_failure_recovery=False,
        historical_failures_unchanged=True,
        automatic_recovery=dict(
            fresh_independent_attempt_only=True,
            same_point_actual_boundaries_only=True,
            no_unknown_feedback_retry=True,
            numerical_or_binding_failure_stops=True,
            manual_stop_is_terminal=True,
            backoff_seconds=[30, 60, 120, 300],
            supervisor="finqa_v50_supervisor.py",
        ),
    )
    require(body["host_ram"] == parent.HOST_RAM, "host RAM runtime hard gates cannot change")
    return body


def _finish_initialization(root, implementation, inherited):
    actual = read_ref(inherited["actual_final_progress"])
    initial = publish(
        root / "initial_state/record.json",
        dict(
            **{key: value for key, value in actual.items() if key not in ("id", "schema", "at")},
            schema="v50_actual_boundary_initial_state.v1",
            at=now(),
            source_snapshot=inherited["actual_final_progress"],
        ),
    )
    publish(
        root / "pilot_acceptance/record.json",
        dict(
            schema="v50_read_only_inherited_pilot.v1",
            at=now(),
            original=entry(PARENT_ROOT / "pilot_acceptance/record.json"),
            newly_repeated_pilot=False,
        ),
    )
    plan = publish(
        root / "protocol/record.json", protocol_body(root, implementation, initial, at=now())
    )
    status(
        root,
        dict(
            phase="REGISTERED_NOT_STARTED",
            protocol_id=plan["id"],
            active_children=[],
            pilot_accepted=True,
            max_gpu_workers=MAX_GPU_WORKERS,
            independent_total_worker_limit=MAX_GPU_WORKERS,
            total_worker_limit_removed=False,
            effective_device_capacity=device_capacity(plan),
        ),
    )
    return plan


def initialize(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT and not (root / "protocol/record.json").exists(),
            "one explicit durable retirement initialization")
    implementation, preparation = checked_implementation(root), checked_preparation()
    parentroot = Path(preparation["parent_root"])
    inherited = inheritance.initialize_parent_handoff(
        root, parentroot, authorization_record=entry(_active_authorization_path(root)),
        handoff_record=preparation["resource_retirement_receipt"])
    publish(root / "activation_registration/record.json", dict(
        schema="v50_explicit_gpu_retirement_activation.v1", at=now(),
        preparation=entry(ROOT / "preparation/record.json"),
        parent_protocol=preparation["parent_protocol"],
        parent_pause=preparation["parent_pause"],
        resource_retirement_receipt=preparation["resource_retirement_receipt"],
        clean_handoff_claimed=False, scientific_controller_started=False,
    ))
    return _finish_initialization(root, implementation, inherited)

def prepare_automatic(root, *, parentroot):
    root, parentroot = Path(root).resolve(), Path(parentroot).resolve()
    require(
        allowed_root(root) and root != ROOT and not root.exists(),
        "automatic recovery requires a fresh sequential V50 attempt",
    )
    require(allowed_root(parentroot), "automatic parent escaped this supervision root")
    decision = inheritance.validate_safe_recovery(parentroot)
    require(decision.get("allowed") is True, "no verified safe automatic boundary")
    implementation = runtime.clone_implementation(root)
    publish(
        root / "authorization/record.json",
        authorization_body(parentroot=parentroot, automatic=True),
    )
    publish(
        root / "activation_registration/record.json",
        dict(
            schema="v50_automatic_activation.v1",
            at=now(),
            parent_failure=entry(parentroot / "failure/record.json"),
            scientific_controller_started=False,
        ),
    )
    inherited = inheritance.initialize_automatic_recovery(
        root, parentroot, authorization_record=entry(root / "authorization/record.json")
    )
    return _finish_initialization(root, implementation, inherited)


def checked_protocol(root=ROOT):
    root = Path(root).resolve()
    implementation = checked_implementation(root)
    plan, initial = (
        checked(root / "protocol/record.json"),
        checked(root / "initial_state/record.json"),
    )
    require(
        {key: value for key, value in plan.items() if key != "id"}
        == protocol_body(root, implementation, initial, at=plan["at"]),
        "V50 protocol changed",
    )
    admission.validate_plan(plan)
    time_policy.validate(plan)
    return plan


def check_result(protocol, stage, result, task_plan=None):
    _original_check_result(protocol, stage, result, task_plan)
    if protocol.get("schema") != PROTOCOL_SCHEMA:
        return
    reference = result.get("gpu_reservation")
    require(
        isinstance(reference, dict)
        and Path(reference["path"])
        .resolve()
        .is_relative_to(Path(protocol["output_root"]).resolve()),
        "current result must bind its actual same-attempt GPU reservation",
    )
    reserved = read_ref(reference)
    require(
        reserved["schema"] == protocol["gpu_reservation_policy"]["schema"]
        and reserved["protocol_id"] == protocol["id"]
        and reserved["context_id"] == result["context_id"]
        and reserved["stage"] == stage
        and reserved["gpu_index"] == result["gpu_index"]
        and reserved["gpu_uuid"] == result["gpu_uuid"]
        and reserved["all_passed"] is True
        and reserved["lifetime_peak_reset_calls"] == 1
        and reserved["reservation_held_through_final_scientific_boundary"] is True,
        "actual reservation binding or single lifetime-peak contract failed",
    )
    inherited = read_ref(protocol["inheritance"])
    items = [
        item
        for item in inherited["context_inheritances"]
        if item["original_context_id"] == result["context_id"]
    ]
    require(len(items) <= 1, "duplicate inherited result coordinate")
    if not items:
        return
    item = items[0]
    if stage == "virtual_point" and item.get("feedback_resume") is not None:
        binding = item["feedback_resume"]
        require(
            (item["seed"], item["arm"], item["step"]) == (389, "C-only", 894)
            and result["feedback_resume_binding_id"] == binding["id"]
            and result["inherited_feedback_episodes"] == 450
            and result["new_feedback_episodes"] == 250
            and result["first_time_feedback_episodes"] == 249
            and result["explicitly_reexecuted_unreturned_requests"] == 1
            and result["scoring_calls"] == 700
            and result["class_gradient_passes"] == result["virtual_point_recomputations"] == 0
            and result["old_unreturned_request_outcome_remains_unknown"] is True,
            "actual bounded partial-feedback completion dose changed",
        )
    if stage in parent.SHARDS and item.get("task_cache_overlay") is not None:
        old_tasks = set(item["task_cache_overlay"]["parent_task_ids"])
        assigned = task_plan["assignments"][parent.SHARDS.index(stage)]["task_ids"]
        require(
            result["reused_task_ids"] == [task for task in assigned if task in old_tasks],
            "partial shard must reuse exactly its registered complete parent tasks",
        )


def eligible(row, protocol, stage, context):
    return admission.eligible_gpu(row, protocol, stage, context)


def worker_environment(row):
    environment = dict(parent.worker_environment(row))
    configuration = "backend:native,expandable_segments:False"
    require(
        environment.get("PYTORCH_CUDA_ALLOC_CONF") in (None, "", configuration)
        and environment.get("PYTORCH_ALLOC_CONF") in (None, "")
        and environment.get("PYTORCH_NO_CUDA_MEMORY_CACHING") in (None, "", "0"),
        "unregistered allocator environment cannot launch a V50 worker",
    )
    environment["PYTORCH_CUDA_ALLOC_CONF"] = configuration
    environment.pop("PYTORCH_ALLOC_CONF", None)
    environment["PYTORCH_NO_CUDA_MEMORY_CACHING"] = "0"
    return environment


class LeasePool(parent.LeasePool):
    """Four lifetime slots, unique device leases and unchanged measured startup RAM."""

    def __init__(self, controller):
        super().__init__(controller)
        self.last_host_admission = None

    def _host_admission(self, stage):
        active = []

        def wait(reason, *, available=None, needed=None, error=None):
            self.last_host_admission = dict(
                at=now(),
                stage=stage,
                decision=reason,
                available_bytes=available,
                needed_bytes=needed,
                active=active,
                host_admission_policy=copy.deepcopy(
                    self.controller.protocol["host_admission_policy"]
                ),
            )
            if error is not None:
                self.last_host_admission["observation_error"] = type(error).__name__
            return False

        for lease in self.leases.values():
            item = lease.runner.active.get(lease.stage)
            launch = item.get("launch") if item is not None else None
            identity = dict(
                stage=lease.stage,
                gpu_index=lease.gpu,
                pid=launch.get("pid") if launch else None,
                birth=launch.get("birth") if launch else None,
            )
            if launch is None or launch.get("pid") is None or launch.get("birth") is None:
                active.append(dict(**identity, observed=False))
                return wait("WAIT_FOR_BOUND_PROCESS_OBSERVATION")
            try:
                before = birth(launch["pid"])
                memory = parent.process_memory(launch["pid"]) if before == launch["birth"] else None
                after = birth(launch["pid"])
            except Exception as error:
                active.append(dict(**identity, observed=False))
                return wait("WAIT_FOR_BOUND_PROCESS_OBSERVATION", error=error)
            if (
                not isinstance(memory, dict)
                or any(
                    type(memory.get(key)) is not int or memory[key] < 0
                    for key in ("rss_bytes", "peak_rss_bytes")
                )
                or memory["peak_rss_bytes"] < memory["rss_bytes"]
                or before != launch["birth"]
                or after != launch["birth"]
            ):
                active.append(dict(**identity, observed=False))
                return wait("WAIT_FOR_BOUND_PROCESS_OBSERVATION")
            active.append(
                dict(
                    **identity,
                    observed=True,
                    rss_bytes=memory["rss_bytes"],
                    peak_rss_bytes=memory["peak_rss_bytes"],
                )
            )
        # Invalid live observations return None; unknown stages or a malformed
        # frozen policy remain hard failures instead of being silently hidden.
        needed = admission.host_memory_requirement(stage, active)
        if type(needed) is not int or needed < parent.HOST_RAM["reserve_bytes"]:
            return wait("WAIT_FOR_VALID_LIVE_MEMORY")
        try:
            host = parent.host_memory()
            available = host.get("available_bytes") if isinstance(host, dict) else None
        except Exception as error:
            return wait("WAIT_FOR_HOST_MEMORY_OBSERVATION", needed=needed, error=error)
        if type(available) not in (int, float) or not math.isfinite(available) or available < 0:
            return wait("WAIT_FOR_HOST_MEMORY_OBSERVATION", needed=needed)
        allowed = available >= needed
        self.last_host_admission = dict(
            at=now(),
            stage=stage,
            available_bytes=available,
            needed_bytes=needed,
            active=active,
            host_admission_policy=copy.deepcopy(self.controller.protocol["host_admission_policy"]),
            decision="ADMIT_HOST_MEMORY" if allowed else "WAIT_FOR_HOST_MEMORY",
        )
        return allowed

    def try_acquire(self, runner, stage):
        allowed = set(self.controller.protocol["allowed_gpu_indices"])
        require(set(self.leases) <= allowed, "GPU lease escaped its registered device set")
        require(
            self.controller.protocol["max_gpu_workers"] == MAX_GPU_WORKERS,
            "GPU0-only single-worker cap missing from current protocol",
        )
        require(len(self.leases) <= MAX_GPU_WORKERS, "worker lifetime slot cap exceeded")
        if len(self.leases) >= MAX_GPU_WORKERS:
            return None
        completed = (251, "Full") in self.controller.completed_arms
        if not admission.bootstrap_stage_allows(stage, runner.context, full251_complete=completed):
            return None
        if not (allowed - set(self.leases)):
            return None
        if not self._host_admission(stage):
            return None
        projection = runner.disk_projection(stage)
        self.controller.disk_gate(projection)
        rows = {row["index"]: row for row in parent.inventory()}
        for gpu in DISPATCH_ORDER:
            if (
                gpu in self.leases
                or gpu not in allowed
                or gpu not in rows
                or not eligible(rows[gpu], self.controller.protocol, stage, runner.context)
            ):
                continue
            path = (
                parent.TRAINING_ROOT
                / "locks"
                / ("gpu-" + parent.digest(rows[gpu]["uuid"]) + ".lock")
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            lock = path.open("a")
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fresh = next((row for row in parent.inventory() if row["index"] == gpu), None)
                if fresh is None or not eligible(
                    fresh, self.controller.protocol, stage, runner.context
                ):
                    lock.close()
                    continue
            except BlockingIOError:
                lock.close()
                continue
            except BaseException:
                lock.close()
                raise
            lease = parent.Lease(self, gpu, lock, runner, stage, projection)
            self.leases[gpu] = lease
            require(len(self.leases) <= MAX_GPU_WORKERS, "worker lifetime slot cap exceeded")
            return fresh, lease
        return None


class ContextRunner(runtime.ContextRunner):
    def launch(self, stage, row, lease):
        self._lifecycle_launch_gate()
        require(admission.device_scope_allows(row["index"], stage, self.context),
                "only GPU0 is authorized")
        require(admission.bootstrap_stage_allows(
                    stage, self.context,
                    full251_complete=(251, "Full") in self.controller.completed_arms),
                "Full251 final training must finish before other GPU stages")
        require(
            stage in self.pending() and stage not in self.dispatched, "unregistered next V50 stage"
        )
        require(not (self.root / stage / "launch/record.json").exists(), "no automatic retry")
        self.controller.disk_gate(0)
        phase, _ = self.stage_limit(stage)
        current = time.monotonic()
        self.phase_started.setdefault(phase, current)
        deadline_epoch = None
        if self.evaluation:
            arguments = [
                str(self.controller.root / "implementation/finqa_v50_evaluation.py"),
                "generate",
                "--stage",
                "generate",
                "--root",
                str(self.controller.root),
                "--seed",
                str(self.context["seed"]),
                "--arm",
                parent.ARM_KEYS[self.context["arm"]],
                "--gpu-index",
                str(row["index"]),
            ]
        else:
            arguments = [
                str(self.controller.root / "implementation/finqa_v50_worker.py"),
                "--root",
                str(self.controller.root),
                "--context",
                str(self.root),
                "--stage",
                stage,
                "--gpu-index",
                str(row["index"]),
            ]
        command = [
            "/usr/bin/taskset",
            "--cpu-list",
            self.protocol["cpu_affinity"][str(row["index"])],
            str(parent.PYTHON),
            "-u",
            *arguments,
        ]
        directory = self.root / stage
        directory.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        with (directory / "worker.log").open("xb") as stream:
            process = subprocess.Popen(
                command,
                cwd=REPO,
                env=worker_environment(row),
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        launch = dict(
            schema="v50_device_leased_reserved_stage_launch.v1",
            at=now(),
            protocol_id=self.protocol["id"],
            context_id=self.context["id"],
            stage=stage,
            pid=process.pid,
            birth=birth(process.pid),
            worker=arguments[0],
            command=command,
            gpu_index=row["index"],
            gpu_uuid=row["uuid"],
            deadline_epoch=deadline_epoch,
            source_checkpoint=self.context.get("checkpoint"),
            no_automatic_retry=True,
            inherited_completed_stages_not_dispatched=True,
            memory_phase=memory_policy.phase_key(stage, self.context),
            minimum_free_mib=memory_policy.minimum_free_mib(stage, self.context),
            gpu_admission_policy_schema=admission.POLICY_SCHEMA,
            actual_dispatch_inventory=copy.deepcopy(row),
            gpu_reservation_policy=copy.deepcopy(self.protocol["gpu_reservation_policy"]),
            actual_host_admission=copy.deepcopy(self.controller.pool.last_host_admission),
            accepted_V40_pilot_repeated=False,
        )
        self.active[stage] = dict(
            process=process,
            launch=launch,
            lock=lease,
            started_monotonic=started,
            stage_deadline_monotonic=None,
        )
        self.dispatched.add(stage)
        require(launch["birth"] is not None, "worker exited before ownership established")
        self.active[stage]["launch"] = publish(directory / "launch/record.json", launch)
        self.update("RUNNING")


class Controller(runtime.Controller):
    def __init__(self, root=ROOT):
        super().__init__(root)
        self._additional_supervisor_wait = self.protocol[
            "additional_supervisor_resource_wait_seconds"
        ]
        self._original_inherited_wait += self._additional_supervisor_wait
        self.inherited["inherited_resource_wait_seconds"] = self._original_inherited_wait
        self._registered_at = datetime.fromisoformat(
            checked(self.root / "activation_registration/record.json")["at"]
        ).timestamp()

    def capture_wait(self, runner, stage, item, *, strict_freshness=True):
        # Original pre-CUDA admission retains its separate path, sequence and
        # closed interval. Post-CUDA pre-scientific capacity waits never replace
        # that evidence, and never raise a resource failure merely for waiting.
        super().capture_wait(runner, stage, item, strict_freshness=strict_freshness)
        paths = sorted((runner.root / stage / "reservation_wait").glob("*/status.json"))
        require(
            all(
                path.parent.name.startswith("episode")
                and len(path.parent.name) == 11
                and path.parent.name[7:].isdigit()
                and int(path.parent.name[7:]) >= 1
                for path in paths
            ),
            "unregistered pre-scientific resource wait episode",
        )
        for path in paths:
            self._capture_reservation_wait(
                runner, stage, item, path, strict_freshness=strict_freshness
            )

    def _capture_reservation_wait(self, runner, stage, item, path, *, strict_freshness):
        heartbeat, launch = checked(path), item["launch"]
        key = (runner.context["id"], stage, launch["pid"], str(launch["birth"]), str(path))
        require(
            self.protocol.get("schema") == PROTOCOL_SCHEMA
            and heartbeat["schema"] == reservation.WAIT_SCHEMA
            and heartbeat["protocol_id"] == self.protocol["id"]
            and heartbeat["context_id"] == runner.context["id"]
            and all(heartbeat[k] == launch[k] for k in ("stage", "pid", "gpu_index", "gpu_uuid"))
            and str(heartbeat["birth"]) == str(launch["birth"])
            and heartbeat["deadline_epoch"] is launch["deadline_epoch"] is None
            and heartbeat["cuda_initialized"] is True
            and heartbeat["memory_phase"] == memory_policy.phase_key(stage, runner.context)
            and heartbeat["minimum_dispatch_free_bytes"]
            == memory_policy.minimum_free_mib(stage, runner.context) * 1024**2
            and heartbeat["gpu_admission_policy_schema"] == admission.POLICY_SCHEMA
            and heartbeat["gpu_reservation_policy_schema"]
            == self.protocol["gpu_reservation_policy"]["schema"]
            and heartbeat["reason"] in reservation.WAIT_REASONS
            and heartbeat["model_load_started"] is False
            and heartbeat["proof_no_scientific_work"] is True
            and heartbeat["gpu_lease_retained"] is heartbeat["worker_slot_retained"] is True
            and heartbeat["automatic_retry"] is False
            and heartbeat["lifetime_peak_reset_calls"] == 1
            and all(
                type(heartbeat[k]) is int and heartbeat[k] == 0
                for k in (
                    "scientific_model_calls", "API_calls", "optimizer_commits",
                    "new_feedback_calls", "actual_response_calls",
                )
            ),
            "pre-scientific resource wait escaped actual owner, policy or zero-science binding",
        )
        fields = (
            "allocated_bytes", "reserved_bytes", "peak_allocated_bytes",
            "peak_reserved_bytes", "physical_free_bytes", "device_total_bytes",
        )
        for observation in (heartbeat["failed_observation"], heartbeat["observation"]):
            require(
                isinstance(observation, dict)
                and all(type(observation.get(k)) is int and observation[k] >= 0 for k in fields)
                and observation["allocated_bytes"] <= observation["reserved_bytes"]
                <= observation["device_total_bytes"]
                and observation["allocated_bytes"] <= observation["peak_allocated_bytes"]
                <= reservation.ALLOCATED_LIMIT_BYTES
                and observation["reserved_bytes"] <= observation["peak_reserved_bytes"]
                and observation["physical_free_bytes"] <= observation["device_total_bytes"],
                "invalid measured pre-scientific resource byte observation",
            )
        required = heartbeat["required_physical_free_bytes"]
        available = heartbeat["required_available_capacity_bytes"]
        require(
            type(required) is int and required >= reservation.FREE_RESERVE_BYTES
            and type(available) is int
            and 0 <= available <= heartbeat["observation"]["device_total_bytes"],
            "resource wait capacity predicate changed",
        )
        if heartbeat["reason"] in {
            "physical_boundary_free_exhausted", "post_cuda_capacity_below_admission_allowance"
        }:
            expected_required = (
                reservation.FREE_RESERVE_BYTES
                if heartbeat["reason"] == "physical_boundary_free_exhausted"
                else max(reservation.FREE_RESERVE_BYTES,
                         heartbeat["minimum_dispatch_free_bytes"] - 3 * 1024**3)
            )
            require(
                required == expected_required
                and heartbeat["failed_observation"]["physical_free_bytes"] < required,
                "resource wait has no measured physical capacity shortage",
            )
        else:
            require(
                type(heartbeat["requested_allocation_bytes"]) is int
                and heartbeat["requested_allocation_bytes"] > 0,
                "resource wait has no typed failed allocation size",
            )
        sequence, phase = heartbeat["sequence"], heartbeat["phase"]
        require(
            type(sequence) is int and sequence >= self._last_wait_sequences.get(key, -1)
            and phase in {"WAITING", "READY", "FAILED", "STOPPED"},
            "resource wait sequence reversed or phase unknown",
        )
        self._last_wait_sequences[key] = sequence
        if phase == "READY":
            observation = heartbeat["observation"]
            require(
                observation["physical_free_bytes"] >= required
                and observation["physical_free_bytes"] + observation["reserved_bytes"] >= available,
                "resource wait cannot become ready without actual capacity",
            )
        current, observed = time.monotonic(), heartbeat["observed_monotonic"]
        start, end = heartbeat["waiting_started_monotonic"], heartbeat["waiting_finished_monotonic"]
        elapsed = heartbeat["waiting_seconds"]
        require(
            all(type(value) in (int, float) and math.isfinite(value)
                for value in (observed, start, elapsed))
            and item["started_monotonic"] <= start <= observed <= current + 1
            and elapsed >= 0 and abs(elapsed - (observed - start)) <= 1e-6,
            "pre-scientific resource wait clock binding is invalid",
        )
        live = item["process"].poll() is None
        if phase == "WAITING":
            require(end is None, "open resource wait has a closed end")
            if strict_freshness and live:
                require(current - observed <= 60, "pre-scientific resource wait heartbeat stale")
            end = observed
        else:
            require(
                type(end) in (int, float) and math.isfinite(end) and start <= end == observed,
                "closed resource wait interval missing or reversed",
            )
        previous = self._worker_wait_intervals.get(key)
        require(
            previous is None or (previous[0] == start and previous[1] <= end),
            "pre-scientific resource wait decreased",
        )
        self._worker_wait_intervals[key] = (start, end)
        if phase == "WAITING" and live:
            self._pre_cuda_waiters[key] = dict(
                context_id=runner.context["id"], stage=stage, pid=launch["pid"],
                gpu_index=launch["gpu_index"], waiting_seconds=elapsed,
                admission_path=str(path), wait_kind="PRE_SCIENTIFIC_CAPACITY",
                reason=heartbeat["reason"], observation=heartbeat["observation"],
                gpu_lease_retained=True, worker_slot_retained=True,
            )
        else:
            self._pre_cuda_waiters.pop(key, None)

    def _capture_wait_path(self, runner, stage, item, path, *, strict_freshness):
        # V50 has its own producer schema. Keep every original identity, phase,
        # monotonic-clock, sequence and interval check; never relabel old records.
        heartbeat, launch = checked(path), item["launch"]
        key = (runner.context["id"], stage, launch["pid"], str(launch["birth"]), str(path))
        require(
            self.protocol.get("schema") == PROTOCOL_SCHEMA
            and heartbeat["schema"] == "v50_shared_pre_cuda_admission.v1"
            and heartbeat["protocol_id"] == self.protocol["id"]
            and heartbeat["context_id"] == runner.context["id"]
            and all(heartbeat[k] == launch[k] for k in ("stage", "pid", "gpu_index", "gpu_uuid"))
            and str(heartbeat["birth"]) == str(launch["birth"])
            and heartbeat["deadline_epoch"] == launch["deadline_epoch"]
            and heartbeat["cuda_initialized"] is False
            and heartbeat["memory_phase"] == memory_policy.phase_key(stage, runner.context)
            and heartbeat["minimum_free_mib"]
            == memory_policy.minimum_free_mib(stage, runner.context)
            and heartbeat["gpu_admission_policy_schema"] == admission.POLICY_SCHEMA
            and heartbeat["gpu_reservation_policy_schema"]
            == self.protocol["gpu_reservation_policy"]["schema"],
            "admission heartbeat does not belong to the actual worker/phase policy",
        )
        sequence = heartbeat["sequence"]
        require(
            type(sequence) is int and sequence >= self._last_wait_sequences.get(key, -1),
            "admission heartbeat sequence reversed",
        )
        self._last_wait_sequences[key] = sequence
        phase = heartbeat["phase"]
        require(
            phase in {"WAITING", "READY", "FAILED", "STOPPED", "TIMED_OUT"},
            "unknown admission state",
        )
        current, observed = time.monotonic(), heartbeat["observed_monotonic"]
        require(
            type(observed) in (int, float)
            and math.isfinite(observed)
            and item["started_monotonic"] <= observed <= current + 1,
            "invalid admission clock binding",
        )
        start, end = heartbeat["waiting_started_monotonic"], heartbeat["waiting_finished_monotonic"]
        if start is not None:
            require(
                type(start) in (int, float)
                and math.isfinite(start)
                and item["started_monotonic"] <= start <= observed,
                "wait outside worker lifetime",
            )
            if phase == "WAITING":
                require(end is None, "open wait already closed")
                if strict_freshness and item["process"].poll() is None:
                    require(current - observed <= 60, "pre-CUDA admission heartbeat stale")
                end = observed
            else:
                require(
                    type(end) in (int, float) and math.isfinite(end) and start <= end <= observed,
                    "closed wait interval missing or reversed",
                )
            previous = self._worker_wait_intervals.get(key)
            require(
                previous is None or (previous[0] == start and previous[1] <= end),
                "worker resource wait decreased",
            )
            self._worker_wait_intervals[key] = (start, end)
        else:
            require(
                phase != "WAITING" and end is None and heartbeat["waiting_seconds"] == 0,
                "unbound waiting duration",
            )
        if phase == "WAITING" and item["process"].poll() is None:
            self._pre_cuda_waiters[key] = dict(
                context_id=runner.context["id"],
                stage=stage,
                pid=launch["pid"],
                gpu_index=launch["gpu_index"],
                waiting_seconds=heartbeat["waiting_seconds"],
                admission_path=str(path),
            )
        else:
            self._pre_cuda_waiters.pop(key, None)

    def update(self, phase, **extra):
        require(
            all(
                admission.device_scope_allows(item["launch"]["gpu_index"], stage, runner.context)
                for runner in self.runs for stage, item in runner.active.items()
            ),
            "an active worker escaped the GPU0-only stage rule",
        )
        active = [
            dict(
                context_id=runner.context["id"],
                **{
                    key: item["launch"][key]
                    for key in ("stage", "pid", "birth", "gpu_index", "gpu_uuid")
                },
                lifecycle_state=item.get("lifecycle_state", "RUNNING"),
            )
            for runner in self.runs
            for item in runner.active.values()
        ]
        require(
            {row["gpu_index"] for row in active} <= set(self.protocol["allowed_gpu_indices"])
            and len({row["gpu_index"] for row in active}) == len(active)
            and len(active) <= MAX_GPU_WORKERS
            and len(self.pool.leases) <= MAX_GPU_WORKERS,
            "only one GPU0 worker, including initializing, waiting and draining",
        )
        waiters = list(self._pre_cuda_waiters.values())
        reservation_waiters = [
            row for row in waiters if row.get("wait_kind") == "PRE_SCIENTIFIC_CAPACITY"
        ]
        if phase == "RUNNING" and waiters and len(waiters) == len(active):
            phase = (
                "WAITING_FOR_PRE_SCIENTIFIC_RESOURCES" if reservation_waiters
                else "WAITING_FOR_PRE_CUDA_RESOURCES"
            )
        status(
            self.root,
            dict(
                phase=phase,
                protocol_id=self.protocol["id"],
                active_children=active,
                pilot_accepted=self.pilot_accepted,
                accepted_new_optimizer_updates=self.accepted_new_updates,
                accepted_new_outer_updates=self.accepted_new_outers,
                global_external_resource_wait_seconds=self.resource_wait_used,
                accepted_result_counters_not_a_substitute_for_actual_checkpoint_audit=True,
                completed_training_coordinates=[
                    dict(seed=seed, arm=arm) for seed, arm in sorted(self.completed_arms)
                ],
                completed_evaluation_coordinates=[
                    dict(seed=seed, arm=arm) for seed, arm in sorted(self.completed_evaluations)
                ],
                pre_cuda_waiters=[row for row in waiters if row not in reservation_waiters],
                pre_scientific_resource_waiters=reservation_waiters,
                resource_waiting_does_not_pause_other_device_dispatch=True,
                inherited_resource_wait_seconds=self.inherited["inherited_resource_wait_seconds"],
                stopped_admission_observation_errors=self._admission_stop_errors,
                original_B_resume_authorized=True,
                max_gpu_workers=MAX_GPU_WORKERS,
                independent_total_worker_limit=MAX_GPU_WORKERS,
                total_worker_limit_removed=False,
                effective_device_capacity=len(self.protocol["allowed_gpu_indices"]),
                currently_usable_gpu_indices=[0],
                effective_max_gpu_workers=1,
                full251_bootstrap_complete=(251, "Full") in self.completed_arms,
                steady_gpu_indices=[0], steady_max_gpu_workers=1,
                temporary_gpu0_full251_train_only=False,
                host_ram_admission_changed=True,
                host_ram_runtime_hard_gates_unchanged=True,
                last_host_admission=copy.deepcopy(self.pool.last_host_admission),
                **extra,
            ),
        )

    def run(self):
        require(
            Path(__file__).resolve() == self.root / "implementation" / FILES[0],
            "only the frozen V50 controller may run",
        )
        elapsed = time.time() - self._registered_at
        require(math.isfinite(elapsed) and elapsed >= 0, "initialization clock reversed")
        charged = math.ceil(self._original_inherited_wait + elapsed)
        self.inherited["inherited_resource_wait_seconds"] = charged
        self.resource_wait_used = charged
        self._resource_waiting, self._resource_accounting_at = True, time.monotonic()
        self.resource_wait_gate()
        publish(
            self.root / "launch_01/record.json",
            dict(
                schema="v50_single_device_leased_controller_launch.v1",
                at=now(),
                protocol_id=self.protocol["id"],
                pid=os.getpid(),
                birth=birth(os.getpid()),
                command=runtime.own_command(),
                max_gpu_workers=MAX_GPU_WORKERS,
                independent_total_worker_limit=MAX_GPU_WORKERS,
                total_worker_limit_removed=False,
                effective_device_capacity=len(self.protocol["allowed_gpu_indices"]),
                inherited_resource_wait_before_initialization=self._original_inherited_wait,
                additional_supervisor_resource_wait_seconds=self._additional_supervisor_wait,
                initialization_wall_seconds=elapsed,
                inherited_global_wait_at_dispatch=charged,
                preparation_wait_excluded_from_initialization_seconds=True,
                cumulative_resource_wait_limit_seconds=None,
                accepted_pilot_repeated=False,
                automatic_restart=False,
            ),
        )
        with stop_signals.audit_signal_installations(sink=self._record_signal_audit):
            return parent.Controller.run(self)


def _routed_module(path, name):
    if Path(path).name == "finqa_v37_evaluation.py" and allowed_root(Path(path).parent.parent):
        return _original_module(Path(path).with_name("finqa_v50_evaluation.py"), name)
    return _original_module(path, name)


# Only the new, isolated V43/V39/V37 execution shell is rebound. The historical
# verifier and all 81 source files remain unmodified and independently checked.
runtime.ROOT = ROOT
runtime.checked_protocol = checked_protocol
runtime.checked_implementation = checked_implementation
runtime.inheritance = inheritance
runtime.ContextRunner = ContextRunner
runtime.LeasePool = LeasePool
runtime.check_result = check_result
runtime.DISPATCH_ORDER = DISPATCH_ORDER
runtime.admission = admission
runtime.memory_policy = memory_policy
base.ROOT = ROOT
base.checked_protocol = checked_protocol
base.checked_implementation = checked_implementation
base.inheritance = inheritance
parent.checked_protocol = checked_protocol
parent.checked_implementation = checked_implementation
parent.ContextRunner = ContextRunner
parent.LeasePool = LeasePool
parent.check_result = check_result
parent._module = _routed_module
parent.POLL_SECONDS = DISPATCH_POLL_SECONDS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "initialize", "run", "inspect"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit")
    parser.add_argument("--parent-root", type=Path, default=LIVE_PARENT_ROOT)
    parser.add_argument("--handoff-record", type=Path, default=DEFAULT_HANDOFF_RECORD)
    args = parser.parse_args()
    if args.action == "prepare":
        require(args.source_commit is not None, "committed source required")
        value = prepare(args.root, source_commit=args.source_commit, parentroot=args.parent_root,
                        handoff_record=args.handoff_record)
    elif args.action == "initialize":
        value = initialize(args.root)
    elif args.action == "run":
        Controller(args.root).run()
        return
    else:
        value = (
            checked_protocol(args.root)
            if (args.root / "protocol/record.json").exists()
            else checked_preparation()
        )
    print(json.dumps(dict(id=value["id"], root=str(args.root)), sort_keys=True))


if __name__ == "__main__":
    main()
