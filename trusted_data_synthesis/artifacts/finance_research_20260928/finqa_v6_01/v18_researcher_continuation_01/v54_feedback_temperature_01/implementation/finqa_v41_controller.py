"""Phase-specific shared-GPU admission after a passive, zero-worker V40 handoff.

Preparation never pauses the parent. Only a naturally empty queue permits the
one handoff. Completed work, actual state and consumed budgets stay unchanged.
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
import signal
import subprocess
import sys
import time
from pathlib import Path

import finqa_v40_signals as stop_signals
import finqa_v41_admission as admission
import finqa_v41_handoff as handoff
import finqa_v41_inheritance as inheritance
import finqa_v41_memory_policy as memory_policy

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
SOURCE_ROOT = handoff.SOURCE_ROOT
PARENT_ROOT = handoff.PARENT_ROOT
ROOT = SOURCE_ROOT / "production_resume_01/admission_relaxation_01"
HANDOFF_ROOT = handoff.HANDOFF_ROOT
PARENT_PROTOCOL_ID = inheritance.PARENT_PROTOCOL_ID
PARENT_IMPLEMENTATION_ID = "79709aee2dc6c72a7d837875ad58513b9b49dcadbb8140a1c530b197dcc53c24"
MODE = "passive_all_or_none"
SWITCH_CONSENT = "保持满额，自然空队列时切换"
FILES = (
    "finqa_v41_controller.py",
    "finqa_v41_handoff.py",
    "finqa_v41_inheritance.py",
    "finqa_v41_memory_policy.py",
    "finqa_v41_admission.py",
    "finqa_v41_worker.py",
    "finqa_v41_evaluation.py",
    "finqa_v41_task_view.py",
)
ALLOWED_GPUS = admission.ALLOWED_GPUS
DISPATCH_ORDER = admission.DISPATCH_ORDER


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


# Historical validation and new execution have independent module globals.
_source = inheritance.checked(PARENT_ROOT / "implementation/record.json")
inheritance.require(_source["id"] == PARENT_IMPLEMENTATION_ID, "V40 source seal changed")
_runtime_directory = (
    Path(__file__).resolve().parent
    if Path(__file__).resolve().parent.name == "implementation"
    else PARENT_ROOT / "implementation"
)
for _name in ("finqa_v40_controller.py", "finqa_v39_controller.py"):
    inheritance.require(
        hashlib.sha256((_runtime_directory / _name).read_bytes()).hexdigest()
        == _source["sha256"][_name],
        "unchanged historical shell required: " + _name,
    )
verifier = _module(
    PARENT_ROOT / "implementation/finqa_v40_controller.py", __name__ + "_historical_v40"
)
base = _module(_runtime_directory / "finqa_v39_controller.py", __name__ + "_runtime_shell")
parent = base.parent
require, checked, publish = parent.require, parent.checked, parent.publish
entry, read_ref, file_ref = parent.entry, parent.read_ref, parent.file_ref
now, sha, birth, status = parent.now, parent.sha, parent.birth, parent.status
DurablePause = parent.DurablePause
check_result = base.check_result
merged_intervals = base.merged_intervals
_original_module = base._base_module


def __getattr__(name):
    return getattr(parent, name)


def checked_parent():
    value = verifier.checked_protocol(PARENT_ROOT)
    require(value["id"] == PARENT_PROTOCOL_ID, "V40 scientific protocol changed")
    return value


def checked_source_bundle():
    value = verifier.checked_implementation(PARENT_ROOT)
    require(
        value["id"] == PARENT_IMPLEMENTATION_ID and len(value["sha256"]) == 43,
        "original 43-file V40 implementation changed",
    )
    return value


def freeze(root, commit):
    commit = subprocess.check_output(
        ["git", "rev-parse", commit + "^{commit}"], cwd=REPO, text=True
    ).strip()
    old, sources = checked_source_bundle(), {}
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=REPO)
        require(
            hashlib.sha256(raw).hexdigest() == sha(REPO / relative), "uncommitted source: " + name
        )
        sources[name] = raw
    for name, expected in old["sha256"].items():
        raw = (PARENT_ROOT / "implementation" / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, "historical source changed: " + name)
        sources[name] = raw
    require(len(sources) == 51, "eight new plus 43 unchanged source files required")
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
            schema="v41_committed_phase_admission_implementation.v1",
            at=now(),
            source_commit=commit,
            committed_files=list(FILES),
            unchanged_parent_implementation=entry(PARENT_ROOT / "implementation/record.json"),
            sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        ),
    )


def checked_implementation(root=ROOT):
    root = Path(root).resolve()
    if root == PARENT_ROOT:
        return checked_source_bundle()
    require(root == ROOT, "fixed independent admission_relaxation_01 root required")
    value, old = checked(root / "implementation/record.json"), checked_source_bundle()
    require(
        value["schema"] == "v41_committed_phase_admission_implementation.v1"
        and value["committed_files"] == list(FILES)
        and list(value["sha256"]) == [*FILES, *old["sha256"]]
        and len(value["sha256"]) == 51
        and value["unchanged_parent_implementation"]
        == entry(PARENT_ROOT / "implementation/record.json"),
        "new or historical implementation ownership changed",
    )
    for name, expected in value["sha256"].items():
        require(sha(root / "implementation" / name) == expected, "frozen bytes changed: " + name)
        if name in old["sha256"]:
            require(expected == old["sha256"][name], "historical mathematics changed")
    return value


def checked_evidence(refs):
    require(isinstance(refs, list) and bool(refs), "verified resource evidence list required")
    paths = set()
    for ref in refs:
        require(
            isinstance(ref, dict) and set(ref) == {"path", "sha256"},
            "resource evidence must be an exact path/sha256 file reference",
        )
        path = Path(ref["path"])
        require(
            path.is_absolute() and path == path.resolve() and str(path) not in paths,
            "resource evidence paths must be unique absolute resolved paths",
        )
        require(sha(path) == ref["sha256"], "resource evidence bytes changed")
        checked(path)
        paths.add(str(path))
    return copy.deepcopy(refs)


def prepare(
    root=ROOT,
    *,
    source_commit,
    mode=MODE,
    evidence_refs,
    user_consent="此条件是否过于严苛，根据实际需求放宽",
):
    root = Path(root).resolve()
    require(
        root == ROOT and not root.exists(), "one independent preparation, no overwrite or retry"
    )
    require(
        mode == MODE, "user selected passive_all_or_none; no draining mode or automatic upgrade"
    )
    require(
        user_consent == "此条件是否过于严苛，根据实际需求放宽", "resource-policy authority changed"
    )
    old, evidence = checked_parent(), checked_evidence(evidence_refs)
    pilot = checked(PARENT_ROOT / "pilot_acceptance/record.json")
    require(
        pilot["protocol_id"] == old["id"] and pilot["remaining_matrix_dispatch_authorized"] is True,
        "V40 pilot must already be accepted; this change cannot repeat it",
    )
    implementation = freeze(root, source_commit)
    preparation = publish(
        root / "preparation/record.json",
        dict(
            schema="v41_explicit_passive_admission_change_preparation.v1",
            at=now(),
            implementation=entry(root / "implementation/record.json"),
            parent_protocol=entry(PARENT_ROOT / "protocol/record.json"),
            parent_accepted_pilot=entry(PARENT_ROOT / "pilot_acceptance/record.json"),
            source_commit=implementation["source_commit"],
            user_consent=user_consent,
            handoff_user_consent=SWITCH_CONSENT,
            mode=mode,
            mode_automatically_upgraded=False,
            accepted_question=(
                "保持当前满额计算，仅在自然空队列窗口接入新策略；不打断worker、不重采样、不重置预算"
            ),
            gpu_admission_policy=memory_policy.policy_record(
                scope=dict(allowed_gpu_indices=list(ALLOWED_GPUS), gpu_uuids=admission.GPU_UUIDS),
                evidence_refs=evidence,
            ),
            maximum_workers=4,
            maximum_project_workers_per_gpu=1,
            live_parent_protocol_or_source_modified=False,
            worker_signals_allowed=False,
            incremental_gpu_lock_draining_allowed=False,
            scientific_math_dose_runtime_memory_and_host_gates_unchanged=True,
            original_budgets_reset=False,
            automatic_retry=False,
        ),
    )
    handoff.register(
        HANDOFF_ROOT,
        parent_root=PARENT_ROOT,
        training_root=parent.TRAINING_ROOT,
        authorization=dict(
            user_consent=SWITCH_CONSENT,
            mode=mode,
            accepted_question=preparation["accepted_question"],
            resource_policy_user_consent=user_consent,
            preparation=entry(root / "preparation/record.json"),
            max_total_gpu_workers=4,
        ),
        mode=mode,
        source_commit=implementation["source_commit"],
    )
    return preparation


def checked_preparation(root):
    value = checked(Path(root) / "preparation/record.json")
    require(
        value["schema"] == "v41_explicit_passive_admission_change_preparation.v1"
        and value["mode"] == MODE
        and value["handoff_user_consent"] == SWITCH_CONSENT
        and value["mode_automatically_upgraded"] is False
        and value["implementation"] == entry(Path(root) / "implementation/record.json")
        and value["parent_protocol"] == entry(PARENT_ROOT / "protocol/record.json")
        and value["parent_accepted_pilot"] == entry(PARENT_ROOT / "pilot_acceptance/record.json"),
        "explicit preparation/parent bindings or selected passive mode changed",
    )
    expected = memory_policy.policy_record(
        scope=dict(allowed_gpu_indices=list(ALLOWED_GPUS), gpu_uuids=admission.GPU_UUIDS),
        evidence_refs=checked_evidence(value["gpu_admission_policy"]["evidence_refs"]),
    )
    require(value["gpu_admission_policy"] == expected, "fixed empirical memory policy changed")
    return value


def protocol_body(root, implementation, initial, *, at):
    root = Path(root)
    old, preparation = checked_parent(), checked_preparation(root)
    inherited = checked(root / "inheritance/record.json")
    body = copy.deepcopy({key: value for key, value in old.items() if key != "id"})
    for key in (
        "first_gate",
        "recovery_pilot",
        "recovery_scope",
        "parent_failure",
        "failed_handoff",
        "partial_class_completion",
        "partial_class_completion_authorization",
        "only_explicitly_authorized_class_deadline_extended",
        "device_admission_override",
        "inherited_compute_seconds",
        "inherited_distribution_seconds",
        "minimum_start_free_mib",
        "dynamic_logical_shards_on_whitelisted_idle_GPUs",
        "resource_authorization",
    ):
        body.pop(key, None)
    body.update(
        schema="v41_phase_specific_shared_gpu_protocol.v1",
        at=at,
        output_root=str(root),
        implementation_id=implementation["id"],
        source_commit=implementation["source_commit"],
        authority="按实际显存需求放宽；保持满额，自然空队列时切换",
        audit=entry(root / "preparation/record.json"),
        parent_protocol=entry(PARENT_ROOT / "protocol/record.json"),
        parent_pause=entry(PARENT_ROOT / "failure/record.json"),
        controlled_handoff=inherited["handoff"],
        inheritance=entry(root / "inheritance/record.json"),
        initial_state_snapshot=entry(root / "initial_state/record.json"),
        original_initial_progress=old["original_initial_progress"],
        initial_progress=dict(
            completed_optimizer_updates=initial["completed_physical_updates"],
            remaining_optimizer_updates=initial["remaining_physical_updates"],
            completed_outer_updates=initial["completed_outers"],
            remaining_outer_updates=initial["remaining_outers"],
            **inherited["remaining_scientific_budget"],
        ),
        inherited_pilot_acceptance=entry(PARENT_ROOT / "pilot_acceptance/record.json"),
        pilot_repeated=False,
        already_complete_evaluations_regenerated=False,
        gpu_admission_policy=copy.deepcopy(preparation["gpu_admission_policy"]),
        historical_V40_device_scope_authorization=old["resource_authorization"],
        historical_V40_unified_idle_admission_is_active=False,
        dynamic_logical_shards_on_phase_eligible_GPUs=True,
        allowed_gpu_indices=list(ALLOWED_GPUS),
        gpu_uuids=admission.GPU_UUIDS,
        dispatch_priority=list(DISPATCH_ORDER),
        cpu_affinity=admission.CPU_AFFINITY,
        max_gpu_workers=4,
        max_workers_per_gpu=1,
        device_admission_override=dict(
            original_scientific_evaluation_plan_unchanged=True,
            both_old_evaluator_idle_predicates_replaced=True,
            real_process_inventory_never_masked=True,
            physical_GPU_UUIDs_bound=True,
            minimum_free_mib="fixed phase-specific gpu_admission_policy, not original 73728",
        ),
        selected_handoff_mode=MODE,
        incremental_lock_draining=False,
        inherited_resource_wait_seconds=inherited["inherited_resource_wait_seconds"],
        per_context_compute_and_phase_deadlines_in_inheritance=True,
        handoff_and_initialization_wall_charged_conservatively=True,
        original_budgets_reset=False,
        outer_and_global_budgets_reset=False,
        new_class_completion_window_authorized=False,
        clean_handoff_claimed=True,
        automatic_retry=False,
        migration_scope=dict(
            no_failed_or_unexited_parent_stage=True,
            inherited_class_phases_all_four_shards_complete=True,
            per_stage_actual_protocol_owners_retained=True,
            completed_C251_parent186_plus_local558_read_only=True,
            parent_task_caches_read_only=True,
            parent_tensors_copied=False,
            all_completed_stage_values_read_only=True,
            completed_stages_redispatched=False,
            new_phase_outputs_only_in_new_episode=True,
            full_remaining_original_matrix=True,
            historical_failures_unchanged=True,
            accepted_pilot_not_repeated=True,
        ),
    )
    return body


def initialize(root=ROOT, *, handoff_record):
    root = Path(root).resolve()
    require(
        root == ROOT and not (root / "protocol/record.json").exists(),
        "one initialized passive migration; never overwrite",
    )
    manifest = checked_implementation(root)
    checked_preparation(root)
    require(
        Path(handoff_record).resolve() == HANDOFF_ROOT / "closeout/record.json",
        "only this registered clean handoff may initialize V41",
    )
    require(
        checked(handoff_record)["mode"] == MODE, "handoff mode differs from selected passive mode"
    )
    inherited = inheritance.initialize_parent_migration(root, PARENT_ROOT, handoff_record)
    actual = read_ref(inherited["actual_final_progress"])
    initial = publish(
        root / "initial_state/record.json",
        dict(
            **{key: value for key, value in actual.items() if key not in ("id", "schema", "at")},
            schema="v41_read_only_actual_initial_state.v1",
            at=now(),
            source_snapshot=inherited["actual_final_progress"],
            actual_state_recomputed=False,
        ),
    )
    publish(
        root / "pilot_acceptance/record.json",
        dict(
            schema="v41_read_only_already_accepted_V40_pilot.v1",
            at=now(),
            original=entry(PARENT_ROOT / "pilot_acceptance/record.json"),
            newly_repeated_pilot=False,
            original_result_relabelled=False,
        ),
    )
    protocol = publish(
        root / "protocol/record.json", protocol_body(root, manifest, initial, at=now())
    )
    status(
        root,
        dict(
            phase="REGISTERED_NOT_STARTED",
            protocol_id=protocol["id"],
            active_children=[],
            pilot_accepted=True,
        ),
    )
    return protocol


def checked_protocol(root=ROOT):
    root = Path(root).resolve()
    if root == PARENT_ROOT:
        return checked_parent()
    require(root == ROOT, "fixed admission relaxation root required")
    implementation = checked_implementation(root)
    plan, initial = (
        checked(root / "protocol/record.json"),
        checked(root / "initial_state/record.json"),
    )
    require(
        {key: value for key, value in plan.items() if key != "id"}
        == protocol_body(root, implementation, initial, at=plan["at"]),
        "registered V41 protocol changed",
    )
    inherited = read_ref(plan["inheritance"])
    require(
        inherited["parent_pause"] == entry(PARENT_ROOT / "failure/record.json"),
        "parent successful handoff pause changed",
    )
    result = read_ref(plan["controlled_handoff"])
    require(
        result["status"] == "COMPLETE"
        and result["mode"] == MODE
        and result["controller_exited"] is True
        and result["children_exited"] is True
        and result["workers_signalled"] is False,
        "clean passive handoff required",
    )
    launch = checked(PARENT_ROOT / "launch_01/record.json")
    require(birth(launch["pid"]) != str(launch["birth"]), "old controller still live")
    admission.validate_plan(plan)
    return plan


def eligible(row, protocol, stage, context):
    if not memory_policy.eligible_gpu(row, protocol, stage, context):
        return False
    if row["index"] == 6:
        withdrawal = Path(protocol["output_root"]) / "queue/gpu6_withdrawal/record.json"
        if withdrawal.exists():
            value = checked(withdrawal)
            require(
                value["protocol_id"] == protocol["id"]
                and value["gpu_index"] == 6
                and value["stop_future_dispatch"] is True,
                "invalid future GPU6 withdrawal",
            )
            return False
    return True


class LeasePool(parent.LeasePool):
    """Same global four-worker/host/disk envelope; phase-aware GPU selection."""

    def try_acquire(self, runner, stage):
        if len(self.leases) >= 4:
            return None
        needed = parent.HOST_RAM["reserve_bytes"] + parent.stage_rss_limit(stage)
        for lease in self.leases.values():
            item = lease.runner.active.get(lease.stage)
            memory = parent.process_memory(item["launch"]["pid"]) if item is not None else None
            used = memory["rss_bytes"] if memory is not None else 0
            needed += max(0, parent.stage_rss_limit(lease.stage) - used)
        if parent.host_memory()["available_bytes"] < needed:
            return None
        projection = runner.disk_projection(stage)
        self.controller.disk_gate(projection)
        rows = {row["index"]: row for row in parent.inventory()}
        for gpu in DISPATCH_ORDER:
            if (
                gpu in self.leases
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
            return fresh, lease
        return None


class ContextRunner(base.ContextRunner):
    def launch(self, stage, row, lease):
        self._lifecycle_launch_gate()
        require(
            stage in self.pending() and stage not in self.dispatched, "unregistered next V41 stage"
        )
        require(not (self.root / stage / "launch/record.json").exists(), "no automatic retry")
        self.controller.disk_gate(0)
        phase, budget = self.stage_limit(stage)
        current = time.monotonic()
        start = self.phase_started.setdefault(phase, current)
        absolute = (
            (getattr(self, "inherited", None) or {}).get("phase_deadlines_epoch", {}).get(phase)
        )
        # stage_limit already subtracts wall time to an inherited absolute deadline.
        remaining = budget if absolute is not None else budget - (current - start)
        if self.context.get("due_outer"):
            remaining = min(remaining, parent.OUTER_COMPUTE_SECONDS - self.compute_used)
        if remaining <= 0:
            raise DurablePause("original phase or outer budget exhausted before V41 dispatch")
        deadline_epoch = time.time() + remaining
        if absolute is not None:
            deadline_epoch = min(deadline_epoch, absolute)
        if self.evaluation:
            arguments = [
                str(self.controller.root / "implementation/finqa_v41_evaluation.py"),
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
                "--deadline-epoch",
                str(deadline_epoch),
            ]
        else:
            arguments = [
                str(self.controller.root / "implementation/finqa_v41_worker.py"),
                "--root",
                str(self.controller.root),
                "--context",
                str(self.root),
                "--stage",
                stage,
                "--gpu-index",
                str(row["index"]),
                "--deadline-epoch",
                str(deadline_epoch),
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
                env=parent.worker_environment(row),
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        launch = dict(
            schema="v41_phase_admission_stage_launch.v1",
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
            accepted_V40_pilot_repeated=False,
        )
        self.active[stage] = dict(
            process=process,
            launch=launch,
            lock=lease,
            started_monotonic=started,
            stage_deadline_monotonic=current + remaining,
        )
        self.dispatched.add(stage)
        require(launch["birth"] is not None, "worker exited before ownership established")
        self.active[stage]["launch"] = publish(directory / "launch/record.json", launch)
        self.update("RUNNING")

    def lifecycle_result_validator(self, stage, result):
        super().lifecycle_result_validator(stage, result)
        require(
            result["memory_phase"] == memory_policy.phase_key(stage, self.context)
            and result["minimum_free_mib"] == memory_policy.minimum_free_mib(stage, self.context)
            and result["gpu_admission_policy_schema"] == admission.POLICY_SCHEMA,
            "result changed its dispatched phase-specific memory policy",
        )


class Controller(base.Controller):
    def __init__(self, root=ROOT):
        super().__init__(root)
        self.pool = LeasePool(self)
        self.pilot_accepted = True

    def create_context(self, coordinate, *, pilot=False):
        if not pilot:
            return parent.Controller.create_context(self, coordinate, pilot=False)
        require(
            coordinate == parent.FIRST and not self._frontier_installed and not self.runs,
            "only one installation of accepted V40 frontier; no new pilot",
        )
        self._frontier_installed = True
        for item in self.inherited["context_inheritances"]:
            directory = Path(item["new_context_directory"])
            context = read_ref(item["original_context"])
            require(
                inheritance.resolve_origin_context(directory, self.protocol)
                == Path(item["origin_context_directory"]),
                "inherited actual context changed",
            )
            runner = ContextRunner(self, directory, context)
            runner.inherited = item
            for stage, binding in item["stage_bindings"].items():
                if binding["protocol_scope"] != "parent":
                    continue
                result, exited = read_ref(binding["result"]), read_ref(binding["exit"])
                owner = read_ref(binding["protocol_ref"])
                require(
                    owner["id"] == binding["protocol_id"]
                    and exited["returncode"] == 0
                    and exited["stop_requested"] is False,
                    "inherited stage owner/actual exit changed",
                )
                check_result(owner, stage, result, runner.task_plan)
                runner.results[stage] = result
                runner.dispatched.add(stage)
            require(
                set(parent.SHARDS) <= runner.results.keys() and "train" not in runner.results,
                "only unfinished contexts with complete class phases may migrate",
            )
            runner.compute_used = item["inherited_compute_seconds"]
            require(
                0 <= runner.compute_used < parent.OUTER_COMPUTE_SECONDS,
                "inherited outer budget exhausted",
            )
            self.runs.append(runner)
            self.active_coordinate[(context["seed"], context["arm"])] = runner
            runner.update("INHERITED_COMPLETED_PHASES_READY")
        self.enqueue_remaining()
        return None

    def capture_wait(self, runner, stage, item, *, strict_freshness=True):
        directory = runner.root / stage
        paths = [directory / "pre_cuda_wait/status.json"]
        # The endpoint has two subsequent pre-CUDA checks; charge their waits
        # too, under unique identity keys but the same global interval union.
        if stage == "generate":
            nested = sorted(directory.glob("pre_cuda_rechecks/*/pre_cuda_wait/status.json"))
            require(
                all(path.parent.parent.name in {"check0001", "check0002"} for path in nested),
                "unregistered endpoint admission recheck",
            )
            paths.extend(nested)
        for path in paths:
            if path.exists():
                self._capture_wait_path(
                    runner, stage, item, path, strict_freshness=strict_freshness
                )

    def _capture_wait_path(self, runner, stage, item, path, *, strict_freshness):
        heartbeat, launch = checked(path), item["launch"]
        key = (runner.context["id"], stage, launch["pid"], str(launch["birth"]), str(path))
        require(
            heartbeat["schema"] == "v39_pre_cuda_admission.v1"
            and heartbeat["protocol_id"] == self.protocol["id"]
            and heartbeat["context_id"] == runner.context["id"]
            and all(heartbeat[k] == launch[k] for k in ("stage", "pid", "gpu_index", "gpu_uuid"))
            and str(heartbeat["birth"]) == str(launch["birth"])
            and heartbeat["deadline_epoch"] == launch["deadline_epoch"]
            and heartbeat["cuda_initialized"] is False
            and heartbeat["memory_phase"] == memory_policy.phase_key(stage, runner.context)
            and heartbeat["minimum_free_mib"]
            == memory_policy.minimum_free_mib(stage, runner.context)
            and heartbeat["gpu_admission_policy_schema"] == admission.POLICY_SCHEMA,
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

    def _record_signal_audit(self, evidence):
        publish(
            self.root / "signal_audit/record.json",
            dict(
                schema="v41_controller_stop_signal_audit.v1",
                at=now(),
                protocol_id=self.protocol["id"],
                **evidence,
                original_stop_handlers_preserved=True,
                automatic_retry=False,
            ),
        )

    def run(self):
        require(
            Path(__file__).resolve() == self.root / "implementation" / FILES[0],
            "run only the new frozen V41 controller after its clean handoff",
        )
        self.resource_wait_gate()
        with stop_signals.audit_signal_installations(sink=self._record_signal_audit):
            return parent.Controller.run(self)


def _routed_module(path, name):
    if (
        Path(path).name == "finqa_v37_evaluation.py"
        and Path(path).parent == ROOT / "implementation"
    ):
        return _original_module(Path(path).with_name("finqa_v41_evaluation.py"), name)
    return _original_module(path, name)


# Scope only the independent V39/V37 execution shell, never historical verifier.
base.ROOT = ROOT
base.checked_protocol = checked_protocol
base.checked_implementation = checked_implementation
base.inheritance = inheritance
base.ALLOWED_GPUS = ALLOWED_GPUS
parent.ALLOWED_GPUS = DISPATCH_ORDER
parent.checked_protocol = checked_protocol
parent.checked_implementation = checked_implementation
parent.ContextRunner = ContextRunner
parent.LeasePool = LeasePool
parent.check_result = check_result
parent._module = _routed_module


def preflight_quiescent(_plan, queue):
    checked_implementation(ROOT)
    checked_preparation(ROOT)
    checked_parent()
    return inheritance.preflight_quiescent(PARENT_ROOT, queue)


def own_command():
    identity = handoff.process_identity(os.getpid())
    require(
        identity is not None and identity["birth"] == birth(os.getpid()),
        "coordinator identity unavailable",
    )
    return identity["argv"]


def bridge_observer_stop(controller, observer_stop):
    """Retain any lawful stop throughout the observer/controller handler seam."""

    def request(*_):
        observer_stop["requested"] = True
        controller.stop = True

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, request)
    # A signal can arrive before either installation or between the two. The
    # observer flag remains authoritative until the original run loop takes it.
    controller.stop = controller.stop or observer_stop["requested"]


def migrate(root=ROOT):
    root = Path(root).resolve()
    require(
        root == ROOT and Path(__file__).resolve() == root / "implementation" / FILES[0],
        "only the prepared frozen passive migration entry may run",
    )
    checked_implementation(root)
    preparation = checked_preparation(root)
    plan = checked(HANDOFF_ROOT / "plan/record.json")
    require(plan["mode"] == preparation["mode"] == MODE, "registered handoff mode changed")
    publish(
        root / "migration_launch/record.json",
        dict(
            schema="v41_single_passive_handoff_observer.v1",
            at=now(),
            preparation=entry(root / "preparation/record.json"),
            pid=os.getpid(),
            birth=birth(os.getpid()),
            command=own_command(),
            mode=MODE,
            automatic_retry=False,
            workers_signalled=False,
            scientific_controller_started=False,
        ),
    )
    stop = {"requested": False}
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    for sig in handlers:
        signal.signal(sig, lambda *_: stop.__setitem__("requested", True))

    def continue_once(_closeout, release_barrier):
        require(not stop["requested"], "observer stop requested before successor initialization")
        initialize(root, handoff_record=HANDOFF_ROOT / "closeout/record.json")
        controller = Controller(root)
        bridge_observer_stop(controller, stop)
        require(not stop["requested"], "observer stop requested during initialization")
        billing = release_barrier()
        charged = max(
            controller.inherited["inherited_resource_wait_seconds"],
            math.ceil(billing["global_resource_wait_seconds"]),
        )
        controller.inherited["inherited_resource_wait_seconds"] = charged
        controller.resource_wait_used = charged
        controller._resource_waiting = True
        controller._resource_accounting_at = time.monotonic()
        controller.resource_wait_gate()
        publish(
            root / "launch_01/record.json",
            dict(
                schema="v41_single_passive_handoff_continuation.v1",
                at=now(),
                protocol_id=controller.protocol["id"],
                pid=os.getpid(),
                birth=birth(os.getpid()),
                command=own_command(),
                barrier_release=entry(HANDOFF_ROOT / "barrier_release/record.json"),
                inherited_global_wait_at_dispatch=charged,
                automatic_restart=False,
                new_pilot_repeated=False,
                handoff_mode=MODE,
            ),
        )
        require(not stop["requested"], "observer stop requested before successor dispatch")
        return controller.run()

    try:
        return handoff.run(
            HANDOFF_ROOT,
            on_quiesced=continue_once,
            validate_quiescent=preflight_quiescent,
            stop_requested=lambda: stop["requested"],
        )
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "migrate", "inspect"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit")
    parser.add_argument("--mode", choices=(MODE,), default=MODE)
    parser.add_argument("--evidence-json", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        require(
            args.source_commit is not None and args.evidence_json is not None,
            "committed source and resource evidence JSON list required",
        )
        result = prepare(
            args.root,
            source_commit=args.source_commit,
            mode=args.mode,
            evidence_refs=json.loads(args.evidence_json.read_bytes()),
        )
    elif args.action == "migrate":
        migrate(args.root)
        return
    else:
        result = (
            checked_protocol(args.root)
            if (args.root / "protocol/record.json").exists()
            else checked_preparation(args.root)
        )
    print(json.dumps(dict(id=result["id"], root=str(args.root)), sort_keys=True))


if __name__ == "__main__":
    main()
