"""One explicitly authorized bounded recovery of the stopped original matrix.

Completed values stay read-only. Only registered wait/distribution and one unknown
feedback-request exceptions change; original scientific dose and math remain.
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
import finqa_v41_admission as admission
import finqa_v41_memory_policy as memory_policy
import finqa_v42_inheritance as inheritance

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
SOURCE_ROOT = (
    REPO
    / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01"
    / "v18_researcher_continuation_01/v25_training_replication_01"
)
PARENT_ROOT = SOURCE_ROOT / "production_resume_01/recovery_02"
ROOT = SOURCE_ROOT / "production_resume_01/recovery_03"
SOURCE_BUNDLE = SOURCE_ROOT / "production_resume_01/admission_relaxation_01/implementation"
PARENT_PROTOCOL_ID = "8732c9297d5a08cda1cb3990622cc8ee1d0868714c4aaf4de2c252e4a0b97160"
PARENT_IMPLEMENTATION_ID = "79709aee2dc6c72a7d837875ad58513b9b49dcadbb8140a1c530b197dcc53c24"
SOURCE_IMPLEMENTATION_ID = "3b2fae948fe19714e4ca69a118de432d5a80f7868c69c2cda88362e91f5bf585"
RESOURCE_WAIT_LIMIT_SECONDS = 129600
INHERITED_RESOURCE_WAIT_SECONDS = 93466
FILES = (
    "finqa_v42_controller.py",
    "finqa_v42_worker.py",
    "finqa_v42_evaluation.py",
    "finqa_v42_inheritance.py",
    "finqa_v42_task_overlay.py",
    "finqa_v42_feedback_resume.py",
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
    else SOURCE_BUNDLE
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
_original_check_result = base.check_result
merged_intervals = base.merged_intervals
_original_module = base._base_module


def __getattr__(name):
    return getattr(parent, name)


def checked_parent():
    value = verifier.checked_protocol(PARENT_ROOT)
    require(value["id"] == PARENT_PROTOCOL_ID, "V40 scientific protocol changed")
    return value


def checked_source_bundle():
    value = checked(SOURCE_BUNDLE / "record.json")
    require(
        value["id"] == SOURCE_IMPLEMENTATION_ID and len(value["sha256"]) == 51,
        "fixed 51-file V41 source package changed",
    )
    for name, expected in value["sha256"].items():
        require(sha(SOURCE_BUNDLE / name) == expected, "frozen V41 bytes changed: " + name)
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
            hashlib.sha256(raw).hexdigest() == sha(REPO / relative),
            "uncommitted V42 source: " + name,
        )
        sources[name] = raw
    for name, expected in old["sha256"].items():
        raw = (SOURCE_BUNDLE / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, "parent source changed: " + name)
        sources[name] = raw
    require(len(sources) == 57, "six new and 51 unchanged files required")
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
            schema="v42_explicit_bounded_recovery_implementation.v1",
            at=now(),
            source_commit=commit,
            committed_files=list(FILES),
            unchanged_source_implementation=entry(SOURCE_BUNDLE / "record.json"),
            sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        ),
    )


def checked_implementation(root=ROOT):
    root = Path(root).resolve()
    if root == PARENT_ROOT:
        return verifier.checked_implementation(root)
    require(root == ROOT, "fixed independent recovery_03 root required")
    value, old = checked(root / "implementation/record.json"), checked_source_bundle()
    require(
        value["schema"] == "v42_explicit_bounded_recovery_implementation.v1"
        and value["committed_files"] == list(FILES)
        and list(value["sha256"]) == [*FILES, *old["sha256"]]
        and len(value["sha256"]) == 57
        and value["unchanged_source_implementation"] == entry(SOURCE_BUNDLE / "record.json"),
        "new or original source ownership changed",
    )
    for name, expected in value["sha256"].items():
        require(sha(root / "implementation" / name) == expected, "frozen bytes changed: " + name)
        if name in old["sha256"]:
            require(expected == old["sha256"][name], "original source modified")
    return value


def verify_parent_stopped():
    old = checked_parent()
    failure = checked(PARENT_ROOT / "failure/record.json")
    launch = checked(PARENT_ROOT / "launch_01/record.json")
    require(failure["protocol_id"] == old["id"], "parent failure owner changed")
    require(birth(launch["pid"]) != str(launch["birth"]), "old controller is still live")
    observer_root = SOURCE_ROOT / "production_resume_01/admission_relaxation_01"
    observer = checked(observer_root / "migration_launch/record.json")
    require(birth(observer["pid"]) != str(observer["birth"]), "old V41 observer still live")
    require(
        not (observer_root / "protocol/record.json").exists()
        and not (observer_root / "launch_01/record.json").exists(),
        "unexpected V41 scientific successor",
    )


def exceptions():
    return dict(
        global_resource_wait=dict(
            previous_limit_seconds=86400,
            new_cumulative_limit_seconds=RESOURCE_WAIT_LIMIT_SECONDS,
            inherited_used_seconds=INHERITED_RESOURCE_WAIT_SECONDS,
            initialization_wall_charged=True,
            counter_reset=False,
        ),
        distribution=dict(
            coordinate=[251, "Full", 894],
            window_seconds=7200,
            starts_at_first_dispatch=True,
            automatic_retry=False,
        ),
        feedback=dict(
            coordinate=[389, "C-only", 894],
            read_only_complete_episodes=450,
            one_unreturned_request_reexecution=1,
            never_dispatched_episodes=249,
            original_episode_budget=700,
            automatic_retry=False,
        ),
    )


def policy_record():
    preparation = checked(SOURCE_BUNDLE.parent / "preparation/record.json")
    policy = preparation["gpu_admission_policy"]
    expected = memory_policy.policy_record(
        scope=dict(allowed_gpu_indices=list(ALLOWED_GPUS), gpu_uuids=admission.GPU_UUIDS),
        evidence_refs=policy["evidence_refs"],
    )
    require(policy == expected, "previously authorized shared-device policy changed")
    return copy.deepcopy(policy)


def protocol_body(root, implementation, initial, *, at):
    old = checked_parent()
    inherited = checked(Path(root) / "inheritance/record.json")
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
        schema="v42_explicit_bounded_same_point_recovery_protocol.v1",
        at=at,
        output_root=str(root),
        implementation_id=implementation["id"],
        source_commit=implementation["source_commit"],
        authority="重启实验；批准有界等待/阶段及唯一未返回反馈请求例外",
        audit=entry(Path(root) / "authorization/record.json"),
        authorization=entry(Path(root) / "authorization/record.json"),
        bounded_exceptions=exceptions(),
        parent_protocol=entry(PARENT_ROOT / "protocol/record.json"),
        parent_failure=entry(PARENT_ROOT / "failure/record.json"),
        inheritance=entry(Path(root) / "inheritance/record.json"),
        initial_state_snapshot=entry(Path(root) / "initial_state/record.json"),
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
        gpu_admission_policy=policy_record(),
        historical_V40_unified_idle_admission_is_active=False,
        allowed_gpu_indices=list(ALLOWED_GPUS),
        gpu_uuids=admission.GPU_UUIDS,
        dispatch_priority=list(DISPATCH_ORDER),
        cpu_affinity=admission.CPU_AFFINITY,
        max_gpu_workers=4,
        max_workers_per_gpu=1,
        resource_wait_budget_seconds=RESOURCE_WAIT_LIMIT_SECONDS,
        inherited_resource_wait_seconds=inherited["inherited_resource_wait_seconds"],
        inherited_outer_used_seconds_preserved=True,
        per_context_compute_and_phase_deadlines_in_inheritance=True,
        only_Full251_894_distribution_deadline_exception=True,
        original_cumulative_wait_counter_reset=False,
        clean_handoff_claimed=False,
        automatic_retry=False,
        accepted_pilot_not_repeated=True,
        all_completed_stage_values_read_only=True,
        new_phase_outputs_only_in_new_episode=True,
        historical_failures_unchanged=True,
    )
    return body


def prepare(root=ROOT, *, source_commit):
    root = Path(root).resolve()
    require(root == ROOT and not root.exists(), "one independent recovery, no overwrite/retry")
    registered_at = now()
    verify_parent_stopped()
    implementation = freeze(root, source_commit)
    publish(
        root / "authorization/record.json",
        dict(
            schema="v42_explicit_bounded_restart_authority.v1",
            at=registered_at,
            user_instruction="重启实验",
            bounded_exception_answer="批准",
            user_consent="批准",
            global_resource_wait_budget_seconds=129600,
            distribution_window_seconds=7200,
            unknown_request_reexecution_authorized=True,
            parent_failure=entry(PARENT_ROOT / "failure/record.json"),
            source_commit=implementation["source_commit"],
            bounded_exceptions=exceptions(),
            prior_memory_policy=entry(SOURCE_BUNDLE.parent / "preparation/record.json"),
            original_outer_compute_budget_seconds=86400,
            no_new_pilot=True,
            automatic_retry=False,
            old_records_modified=False,
        ),
    )
    inherited = inheritance.initialize_parent_recovery(
        root, PARENT_ROOT, authorization_record=entry(root / "authorization/record.json")
    )
    require(
        inherited["inherited_resource_wait_seconds"] == INHERITED_RESOURCE_WAIT_SECONDS,
        "old merged waiting usage must be retained exactly",
    )
    actual = read_ref(inherited["actual_final_progress"])
    initial = publish(
        root / "initial_state/record.json",
        dict(
            **{key: value for key, value in actual.items() if key not in ("id", "schema", "at")},
            schema="v42_read_only_actual_initial_state.v1",
            at=now(),
            source_snapshot=inherited["actual_final_progress"],
            actual_state_recomputed=False,
        ),
    )
    require(
        initial["remaining_physical_updates"] == 2355 and initial["remaining_outers"] == 7,
        "actual original matrix remaining dose changed",
    )
    publish(
        root / "pilot_acceptance/record.json",
        dict(
            schema="v42_inherited_already_accepted_V40_pilot.v1",
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
        ),
    )
    return plan


def checked_protocol(root=ROOT):
    root = Path(root).resolve()
    if root == PARENT_ROOT:
        return checked_parent()
    require(root == ROOT, "fixed recovery_03 root required")
    implementation = checked_implementation(root)
    plan, initial = (
        checked(root / "protocol/record.json"),
        checked(root / "initial_state/record.json"),
    )
    require(
        {key: value for key, value in plan.items() if key != "id"}
        == protocol_body(root, implementation, initial, at=plan["at"]),
        "registered V42 protocol changed",
    )
    authorization = checked(root / "authorization/record.json")
    require(
        authorization["bounded_exception_answer"] == "批准"
        and authorization["bounded_exceptions"] == exceptions(),
        "explicit bounded recovery authority changed",
    )
    verify_parent_stopped()
    admission.validate_plan(plan)
    return plan


def check_result(protocol, stage, result, task_plan=None):
    _original_check_result(protocol, stage, result, task_plan)
    if protocol.get("schema") != "v42_explicit_bounded_same_point_recovery_protocol.v1":
        return
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
    def time_gate(self):
        if (
            not self.stop
            and not self.controller.stop
            and self.controller.resource_wait_used >= RESOURCE_WAIT_LIMIT_SECONDS
        ):
            raise DurablePause("explicit cumulative 36-hour resource wait budget exhausted")
        return super().time_gate()

    def distribution_exception(self, stage):
        item = getattr(self, "inherited", None) or {}
        exception = item.get("phase_deadline_overrides", {}).get("distribution")
        if stage != "distribution" or exception is None:
            return False
        require(
            (self.context["seed"], self.context["arm"], self.context["step"]) == (251, "Full", 894)
            and exception["window_seconds"] == 7200
            and exception["starts_at_first_dispatch"] is True
            and exception["only_authorized_coordinate"] == [251, "Full", 894],
            "distribution exception scope changed",
        )
        return True

    def stage_limit(self, stage):
        if self.distribution_exception(stage):
            return "distribution", 7200
        return super().stage_limit(stage)

    def launch(self, stage, row, lease):
        self._lifecycle_launch_gate()
        require(
            stage in self.pending() and stage not in self.dispatched, "unregistered next V42 stage"
        )
        require(not (self.root / stage / "launch/record.json").exists(), "no automatic retry")
        self.controller.disk_gate(0)
        phase, budget = self.stage_limit(stage)
        current = time.monotonic()
        start = self.phase_started.setdefault(phase, current)
        absolute = (
            (getattr(self, "inherited", None) or {}).get("phase_deadlines_epoch", {}).get(phase)
        )
        if self.distribution_exception(stage):
            absolute = None
        # stage_limit already subtracts wall time to an inherited absolute deadline.
        remaining = budget if absolute is not None else budget - (current - start)
        if self.context.get("due_outer"):
            remaining = min(remaining, parent.OUTER_COMPUTE_SECONDS - self.compute_used)
        if remaining <= 0:
            raise DurablePause("original phase or outer budget exhausted before V42 dispatch")
        deadline_epoch = time.time() + remaining
        if absolute is not None:
            deadline_epoch = min(deadline_epoch, absolute)
        if self.evaluation:
            arguments = [
                str(self.controller.root / "implementation/finqa_v42_evaluation.py"),
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
                str(self.controller.root / "implementation/finqa_v42_worker.py"),
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
        if self.distribution_exception(stage):
            publish(
                self.root / "distribution_recovery_window/record.json",
                dict(
                    schema="v42_single_bounded_distribution_completion_window.v1",
                    at=now(),
                    protocol_id=self.protocol["id"],
                    context_id=self.context["id"],
                    coordinate=[251, "Full", 894],
                    started_epoch=deadline_epoch - remaining,
                    deadline_epoch=deadline_epoch,
                    window_seconds=7200,
                    original_deadline_epoch=self.inherited["phase_deadlines_epoch"]["distribution"],
                    inherited_outer_used_seconds=self.compute_used,
                    authorization=self.protocol["authorization"],
                    automatic_retry=False,
                ),
            )
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
            schema="v42_phase_admission_stage_launch.v1",
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
        binding = (getattr(self, "inherited", None) or {}).get("feedback_resume")
        if stage == "virtual_point" and binding is not None:
            # The unchanged V37 branch requires 700 *new* episodes. This one
            # registered continuation has 450 old + 250 newly completed episodes;
            # retain its identity/device checks without relabelling that evidence.
            launch = self.active[stage]["launch"]
            require(
                (self.context["seed"], self.context["arm"], self.context["step"])
                == (389, "C-only", 894)
                and result["context_id"] == self.context["id"] == binding["original_context_id"]
                and (result["gpu_index"], result["gpu_uuid"])
                == (launch["gpu_index"], launch["gpu_uuid"])
                and result["point_id"] == binding["point_id"]
                and result["feedback_mode"] == self.context["feedback"]["mode"] == "first_sampling"
                and result["response_count"] >= 0,
                "resumed virtual result identity/device/point differs",
            )
            check_result(self.protocol, stage, result, self.task_plan)
        else:
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
        self._registered_at = datetime.fromisoformat(
            checked(self.root / "authorization/record.json")["at"]
        ).timestamp()
        self._original_inherited_wait = self.inherited["inherited_resource_wait_seconds"]

    def resource_wait_gate(self):
        if self.resource_wait_used >= RESOURCE_WAIT_LIMIT_SECONDS:
            raise DurablePause("explicit cumulative 36-hour resource wait budget exhausted")

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
                "train" not in runner.results,
                "only unfinished original contexts may be restored",
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
                schema="v42_controller_stop_signal_audit.v1",
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
            "run only the committed V42 recovery controller",
        )
        elapsed = time.time() - self._registered_at
        require(math.isfinite(elapsed) and elapsed >= 0, "initialization clock reversed")
        charged = math.ceil(self._original_inherited_wait + elapsed)
        self.inherited["inherited_resource_wait_seconds"] = charged
        self.resource_wait_used = charged
        self._resource_waiting = True
        self._resource_accounting_at = time.monotonic()
        self.resource_wait_gate()
        publish(
            self.root / "launch_01/record.json",
            dict(
                schema="v42_single_bounded_recovery_launch.v1",
                at=now(),
                protocol_id=self.protocol["id"],
                pid=os.getpid(),
                birth=birth(os.getpid()),
                command=own_command(),
                inherited_resource_wait_before_initialization=self._original_inherited_wait,
                initialization_wall_seconds=elapsed,
                inherited_global_wait_at_dispatch=charged,
                cumulative_resource_wait_limit_seconds=RESOURCE_WAIT_LIMIT_SECONDS,
                accepted_pilot_repeated=False,
                independent_recovery_not_clean_handoff=True,
                automatic_restart=False,
            ),
        )
        with stop_signals.audit_signal_installations(sink=self._record_signal_audit):
            return parent.Controller.run(self)


def _routed_module(path, name):
    if (
        Path(path).name == "finqa_v37_evaluation.py"
        and Path(path).parent == ROOT / "implementation"
    ):
        return _original_module(Path(path).with_name("finqa_v42_evaluation.py"), name)
    return _original_module(path, name)


# Scope only the independent V39/V37 execution shell, never historical verifier.
base.ROOT = ROOT
base.checked_protocol = checked_protocol
base.checked_implementation = checked_implementation
base.inheritance = inheritance
base.ALLOWED_GPUS = ALLOWED_GPUS
parent.ALLOWED_GPUS = DISPATCH_ORDER
parent.RESOURCE_WAIT_SECONDS = RESOURCE_WAIT_LIMIT_SECONDS
parent.checked_protocol = checked_protocol
parent.checked_implementation = checked_implementation
parent.ContextRunner = ContextRunner
parent.LeasePool = LeasePool
parent.check_result = check_result
parent._module = _routed_module


def own_command():
    return [
        part.decode()
        for part in Path(f"/proc/{os.getpid()}/cmdline").read_bytes().split(bytes([0]))
        if part
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "inspect"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    if args.action == "prepare":
        require(args.source_commit is not None, "committed source required")
        result = prepare(args.root, source_commit=args.source_commit)
    elif args.action == "run":
        Controller(args.root).run()
        return
    else:
        result = checked_protocol(args.root)
    print(json.dumps(dict(id=result["id"], root=str(args.root)), sort_keys=True))


if __name__ == "__main__":
    main()
