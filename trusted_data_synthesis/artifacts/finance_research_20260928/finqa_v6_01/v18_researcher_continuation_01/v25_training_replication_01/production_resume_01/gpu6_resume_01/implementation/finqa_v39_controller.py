"""One clean GPU6 handoff and continuation of the unchanged original matrix.

No live worker is adopted or interrupted. The old controller is paused only
behind its original GPU lease locks after every dispatched stage exited zero.
The new episode inherits completed values, actual states and consumed budgets.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import finqa_v39_admission as admission
import finqa_v39_handoff as handoff
import finqa_v39_inheritance as inheritance

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
SOURCE_ROOT = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01/v25_training_replication_01"
)
PARENT_ROOT = SOURCE_ROOT / "production_resume_01/recovery_01"
ROOT = SOURCE_ROOT / "production_resume_01/gpu6_resume_01"
HANDOFF_ROOT = PARENT_ROOT / "controlled_handoff_gpu6_01"
RESOURCE_AUTHORIZATION = PARENT_ROOT / "resource_authorization_gpu6_20261012_01/record.json"
PARENT_PROTOCOL_ID = "28a3d931f15acc5240a07da7c126c42418c4ed50ab665811d072d1d290706462"
PARENT_IMPLEMENTATION_ID = "2446c3b89a5214245657e7fb4f90a42764c5378ff6193b6dfd6897a2e50354a7"
FILES = (
    "finqa_v39_controller.py",
    "finqa_v39_worker.py",
    "finqa_v39_admission.py",
    "finqa_v39_inheritance.py",
    "finqa_v39_evaluation.py",
    "finqa_v39_handoff.py",
)
ALLOWED_GPUS = admission.ALLOWED_GPUS


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


# The verifier and runtime are separate modules. The original validator must
# retain its original four-card constants when checking historical protocols.
_manifest = inheritance.checked(PARENT_ROOT / "implementation/record.json")
inheritance.require(_manifest["id"] == PARENT_IMPLEMENTATION_ID, "parent implementation changed")
for _name in ("finqa_v38_controller.py", "finqa_v37_controller.py"):
    inheritance.require(
        hashlib.sha256((PARENT_ROOT / "implementation" / _name).read_bytes()).hexdigest()
        == _manifest["sha256"][_name],
        "parent controller bytes changed",
    )
verifier = _module(
    PARENT_ROOT / "implementation/finqa_v38_controller.py", __name__ + "_parent_verifier"
)
_runtime_directory = (
    Path(__file__).resolve().parent
    if Path(__file__).resolve().parent.name == "implementation"
    else PARENT_ROOT / "implementation"
)
inheritance.require(
    hashlib.sha256((_runtime_directory / "finqa_v37_controller.py").read_bytes()).hexdigest()
    == _manifest["sha256"]["finqa_v37_controller.py"],
    "runtime parent bytes changed",
)
parent = _module(_runtime_directory / "finqa_v37_controller.py", __name__ + "_runtime")
require, checked, publish = parent.require, parent.checked, parent.publish
entry, read_ref, file_ref = parent.entry, parent.read_ref, parent.file_ref
now, sha, birth, status = parent.now, parent.sha, parent.birth, parent.status
DurablePause = parent.DurablePause
_base_runner = parent.ContextRunner
_base_check_result = parent.check_result
_base_module = parent._module


def __getattr__(name):
    return getattr(parent, name)


def checked_parent():
    value = verifier.checked_protocol(PARENT_ROOT)
    require(value["id"] == PARENT_PROTOCOL_ID, "parent scientific protocol changed")
    return value


def freeze(root, commit):
    commit = subprocess.check_output(
        ["git", "rev-parse", commit + "^{commit}"], cwd=REPO, text=True
    ).strip()
    original = verifier.checked_implementation(PARENT_ROOT)
    require(original["id"] == PARENT_IMPLEMENTATION_ID, "parent sources changed")
    sources = {}
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=REPO)
        require(hashlib.sha256(raw).hexdigest() == sha(REPO / relative), "uncommitted " + name)
        sources[name] = raw
    for name, expected in original["sha256"].items():
        raw = (PARENT_ROOT / "implementation" / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, "parent source changed: " + name)
        sources[name] = raw
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
            schema="v39_committed_resource_handoff_implementation.v1",
            at=now(),
            source_commit=commit,
            committed_files=list(FILES),
            unchanged_parent_implementation=entry(PARENT_ROOT / "implementation/record.json"),
            sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        ),
    )


def checked_implementation(root):
    root = Path(root).resolve()
    if root == PARENT_ROOT:
        return verifier.checked_implementation(root)
    require(root == ROOT, "fixed new resource handoff root required")
    manifest = checked(root / "implementation/record.json")
    original = verifier.checked_implementation(PARENT_ROOT)
    require(
        manifest["schema"] == "v39_committed_resource_handoff_implementation.v1"
        and manifest["committed_files"] == list(FILES)
        and list(manifest["sha256"]) == [*FILES, *original["sha256"]]
        and manifest["unchanged_parent_implementation"]
        == entry(PARENT_ROOT / "implementation/record.json"),
        "resource handoff execution seal changed",
    )
    for name, expected in manifest["sha256"].items():
        require(sha(root / "implementation" / name) == expected, "frozen bytes changed: " + name)
        if name in original["sha256"]:
            require(expected == original["sha256"][name], "parent mathematics/source changed")
    return manifest


def prepare(root=ROOT, *, source_commit):
    root = Path(root).resolve()
    require(root == ROOT and not root.exists(), "one new resource episode; no overwrite")
    old = checked_parent()
    permission = checked(RESOURCE_AUTHORIZATION)
    require(
        permission["user_instruction"] == "可以临时占用GPU6"
        and permission["scope"]["additional_gpu_uuid"] == admission.GPU_UUIDS["6"]
        and permission["scope"]["max_total_gpu_workers"] == 4,
        "temporary resource permission changed",
    )
    manifest = freeze(root, source_commit)
    preparation = publish(
        root / "preparation/record.json",
        dict(
            schema="v39_explicit_safe_handoff_preparation.v1",
            at=now(),
            implementation=entry(root / "implementation/record.json"),
            parent_protocol=entry(PARENT_ROOT / "protocol/record.json"),
            resource_authorization=entry(RESOURCE_AUTHORIZATION),
            user_consent="同意",
            accepted_question=(
                "是否安排一次受控切换：让当前阶段完整封存后，换用支持GPU6的调度器，"
                "保留原状态、反馈和剩余预算？"
            ),
            source_commit=manifest["source_commit"],
            allowed_gpu_indices=list(ALLOWED_GPUS),
            gpu_uuids=admission.GPU_UUIDS,
            max_total_gpu_workers=4,
            scientific_dose_math_and_original_time_limits_unchanged=True,
            signal_live_worker_allowed=False,
            automatic_retry=False,
        ),
    )
    handoff.register(
        HANDOFF_ROOT,
        parent_root=PARENT_ROOT,
        training_root=parent.TRAINING_ROOT,
        authorization=dict(
            user_consent=preparation["user_consent"],
            accepted_question=preparation["accepted_question"],
            preparation=entry(root / "preparation/record.json"),
            resource_authorization=entry(RESOURCE_AUTHORIZATION),
            max_total_gpu_workers=old["max_gpu_workers"],
        ),
        source_commit=manifest["source_commit"],
    )
    return preparation


def protocol_body(root, implementation, initial, *, at):
    root = Path(root)
    old = checked_parent()
    inherited = checked(root / "inheritance/record.json")
    body = copy.deepcopy({k: v for k, v in old.items() if k != "id"})
    for key in (
        "first_gate",
        "recovery_scope",
        "inherited_compute_seconds",
        "inherited_distribution_seconds",
        "inherited_resource_wait_seconds",
    ):
        body.pop(key, None)
    body.update(
        schema="v39_safe_gpu6_resource_migration_protocol.v1",
        at=at,
        output_root=str(root),
        implementation_id=implementation["id"],
        source_commit=implementation["source_commit"],
        authority="临时占用GPU6；用户同意当前阶段完整封存后的受控调度切换",
        audit=entry(root / "preparation/record.json"),
        parent_protocol=entry(PARENT_ROOT / "protocol/record.json"),
        parent_pause=entry(PARENT_ROOT / "failure/record.json"),
        controlled_handoff=inherited["handoff"],
        resource_authorization=entry(RESOURCE_AUTHORIZATION),
        inheritance=entry(root / "inheritance/record.json"),
        initial_state_snapshot=entry(root / "initial_state/record.json"),
        original_initial_progress=old["initial_progress"],
        initial_progress=dict(
            completed_optimizer_updates=initial["completed_physical_updates"],
            remaining_optimizer_updates=initial["remaining_physical_updates"],
            completed_outer_updates=initial["completed_outers"],
            remaining_outer_updates=initial["remaining_outers"],
            **inherited["remaining_scientific_budget"],
        ),
        original_first_gate=old["first_gate"],
        inherited_pilot_acceptance=entry(PARENT_ROOT / "pilot_acceptance/record.json"),
        pilot_repeated=False,
        already_complete_evaluations_regenerated=False,
        allowed_gpu_indices=list(ALLOWED_GPUS),
        gpu_uuids=admission.GPU_UUIDS,
        cpu_affinity={**old["cpu_affinity"], "6": old["cpu_affinity"]["7"]},
        max_gpu_workers=4,
        temporary_GPU6_only=True,
        temporary_GPU6_withdrawal=(
            "A sealed queue/gpu6_withdrawal/record.json stops only future GPU6 dispatch; "
            "an already dispatched worker retains its slot until natural completion/exit"
        ),
        device_admission_override=dict(
            original_scientific_evaluation_plan_unchanged=True,
            scoped_old_evaluator_device_check_adapter=True,
            overridden_fields=["allowed_gpu_indices", "minimum_free_mib"],
            minimum_free_mib="max(original minimum,73728)",
            physical_GPU_UUIDs_bound=True,
        ),
        inherited_resource_wait_seconds=inherited["inherited_resource_wait_seconds"],
        per_context_compute_and_phase_deadlines_in_inheritance=True,
        handoff_and_initialization_wall_charged_conservatively=True,
        original_budgets_reset=False,
        migration_scope=dict(
            no_failed_or_unexited_parent_stage=True,
            inherited_class_phases_all_four_shards_complete=True,
            parent_task_caches_read_only=True,
            parent_tensors_copied=False,
            all_completed_stage_values_read_only=True,
            completed_stages_redispatched=False,
            new_phase_outputs_only_in_new_episode=True,
            full_remaining_original_matrix=True,
        ),
    )
    return body


def initialize(root=ROOT, *, handoff_record):
    root = Path(root).resolve()
    require(
        root == ROOT and not (root / "protocol/record.json").exists(),
        "one new initialized migration, never overwrite",
    )
    manifest = checked_implementation(root)
    inherited = inheritance.initialize_parent_migration(root, PARENT_ROOT, handoff_record)
    actual = read_ref(inherited["actual_final_progress"])
    initial = publish(
        root / "initial_state/record.json",
        dict(
            **{k: v for k, v in actual.items() if k not in ("id", "schema", "at")},
            schema="v39_read_only_initial_actual_state_snapshot.v1",
            at=now(),
            source_snapshot=inherited["actual_final_progress"],
            actual_state_recomputed=False,
        ),
    )
    publish(
        root / "pilot_acceptance/record.json",
        dict(
            schema="v39_read_only_previously_accepted_pilot.v1",
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
    require(root == ROOT, "fixed resource migration root required")
    implementation = checked_implementation(root)
    plan, initial = (
        checked(root / "protocol/record.json"),
        checked(root / "initial_state/record.json"),
    )
    require(
        {k: v for k, v in plan.items() if k != "id"}
        == protocol_body(root, implementation, initial, at=plan["at"]),
        "resource migration protocol changed",
    )
    inherited = read_ref(plan["inheritance"])
    require(
        inherited["parent_pause"] == entry(PARENT_ROOT / "failure/record.json"),
        "parent authorized pause changed",
    )
    handoff_result = read_ref(plan["controlled_handoff"])
    require(
        handoff_result["status"] == "COMPLETE"
        and handoff_result["controller_exited"]
        and handoff_result["children_exited"],
        "parent handoff is not complete",
    )
    launch = checked(PARENT_ROOT / "launch_01/record.json")
    require(birth(launch["pid"]) != str(launch["birth"]), "parent controller still live")
    admission.validate_plan(plan)
    return plan


def eligible(row, protocol):
    if (
        row["index"] not in ALLOWED_GPUS
        or row["uuid"] != protocol["gpu_uuids"].get(str(row["index"]))
        or row["processes"]
        or row["free_mib"] < parent.MINIMUM_FREE_MIB
    ):
        return False
    if row["index"] == 6:
        withdrawal = Path(protocol["output_root"]) / "queue/gpu6_withdrawal/record.json"
        if withdrawal.exists():
            value = checked(withdrawal)
            require(
                value["protocol_id"] == protocol["id"]
                and value["gpu_index"] == 6
                and value["stop_future_dispatch"] is True,
                "invalid temporary GPU withdrawal",
            )
            return False
    return True


def check_result(protocol, stage, result, task_plan=None):
    require(
        result["gpu_index"] in protocol["allowed_gpu_indices"],
        "result device outside its actual protocol owner",
    )
    return _base_check_result(protocol, stage, result, task_plan)


def merged_intervals(intervals):
    merged = []
    for start, end in sorted(intervals):
        require(
            all(type(v) in (int, float) and math.isfinite(v) for v in (start, end))
            and 0 <= start <= end,
            "invalid external-resource wait interval",
        )
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


class ContextRunner(_base_runner):
    def stage_limit(self, stage):
        phase, limit = _base_runner.stage_limit(self, stage)
        if getattr(self, "inherited", None) is not None:
            deadline = self.inherited["phase_deadlines_epoch"].get(phase)
            if deadline is not None:
                # Completed phases are not dispatched; this also fails closed
                # if a future scope ever attempts to continue an expired phase.
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise DurablePause("original inherited phase deadline exhausted")
                limit = min(limit, remaining)
        return phase, limit

    def launch(self, stage, row, lease):
        self._lifecycle_launch_gate()
        require(stage in self.pending() and stage not in self.dispatched, "unregistered next stage")
        require(not (self.root / stage / "launch/record.json").exists(), "no automatic retry")
        self.controller.disk_gate(0)
        phase, budget = self.stage_limit(stage)
        current = time.monotonic()
        start = self.phase_started.setdefault(phase, current)
        remaining = budget - (current - start)
        if self.context.get("due_outer"):
            remaining = min(remaining, parent.OUTER_COMPUTE_SECONDS - self.compute_used)
        if remaining <= 0:
            raise DurablePause("original stage or outer budget exhausted before dispatch")
        deadline_epoch = time.time() + remaining
        if self.evaluation:
            arguments = [
                str(self.controller.root / "implementation/finqa_v39_evaluation.py"),
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
                str(self.controller.root / "implementation/finqa_v39_worker.py"),
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
            schema="v39_owned_production_stage_launch.v1",
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
        )
        self.active[stage] = dict(
            process=process,
            launch=launch,
            lock=lease,
            started_monotonic=started,
            stage_deadline_monotonic=current + remaining,
        )
        self.dispatched.add(stage)
        require(launch["birth"] is not None, "worker exited before ownership was established")
        self.active[stage]["launch"] = publish(directory / "launch/record.json", launch)
        self.update("RUNNING")

    def record_exit(self, stage, *, stopped=False):
        # A short WAITING->READY can occur entirely between controller polls.
        # Capture its closed interval before the active item/lease is discarded.
        error = None
        try:
            self.controller.capture_wait(self, stage, self.active[stage], strict_freshness=False)
            self.controller.recount_resource_wait()
        except BaseException as issue:
            error = issue
            if stopped:
                self.controller._admission_stop_errors.append(str(issue))
        # Even malformed telemetry cannot prevent releasing an actually exited
        # process during all-pool shutdown. Normal acceptance still fails closed.
        code = super().record_exit(stage, stopped=stopped)
        if not stopped:
            if error is not None:
                raise error
            self.controller.resource_wait_gate()
        return code


class Controller(parent.Controller):
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.protocol = checked_protocol(self.root)
        self.initial = read_ref(self.protocol["initial_state_snapshot"])
        self.inherited = read_ref(self.protocol["inheritance"])
        self.training, self.rt, self.context_module, self.original_cache = (
            parent.production_modules(self.root)
        )
        self.runs = []
        self.latest = {(r["seed"], r["arm"]): r["checkpoint"]["path"] for r in self.initial["arms"]}
        self.completed_arms = {
            (r["seed"], r["arm"]) for r in self.initial["arms"] if r["step"] == 1490
        }
        self.active_coordinate = {}
        self.completed_evaluations = {
            (r["seed"], r["arm"]) for r in self.inherited["completed_evaluations"]
        }
        self.pool = parent.LeasePool(self)
        self.stop = False
        self.pilot_accepted = True
        self.accepted_new_updates = self.inherited["accepted_new_optimizer_updates"]
        self.accepted_new_outers = self.inherited["accepted_new_outer_updates"]
        self.draining_episode = None
        self.draining_episode_count = 0
        self.resource_wait_used = self.inherited["inherited_resource_wait_seconds"]
        self._resource_waiting = False
        self._resource_accounting_at = time.monotonic()
        self._idle_wait_intervals = []
        self._worker_wait_intervals = {}
        self._pre_cuda_waiters = {}
        self._last_wait_sequences = {}
        self._admission_stop_errors = []
        self._frontier_installed = False
        self.checkpoint_size = max(
            Path(r["checkpoint"]["state"]["path"]).stat().st_size for r in self.initial["arms"]
        )
        self.source_bindings = dict(
            original_training_module=file_ref(
                SOURCE_ROOT / "implementation/finqa_v25_training_replication.py"
            ),
            original_class_source=file_ref(self.rt.v8.__file__),
            storage_source=file_ref(self.root / "implementation/finqa_v34_tail_memory.py"),
            task_cache_source=file_ref(self.root / "implementation/finqa_v35_task_cache.py"),
            production_implementation=entry(self.root / "implementation/record.json"),
        )

    def create_context(self, coordinate, *, pilot=False):
        if not pilot:
            return super().create_context(coordinate, pilot=False)
        require(
            coordinate == parent.FIRST and not self._frontier_installed and not self.runs,
            "one restoration of the already accepted frontier",
        )
        self._frontier_installed = True
        for item in self.inherited["context_inheritances"]:
            directory = Path(item["new_context_directory"])
            context = read_ref(item["original_context"])
            require(
                inheritance.resolve_origin_context(directory, self.protocol)
                == Path(item["origin_context_directory"]),
                "parent alias changed",
            )
            runner = ContextRunner(self, directory, context)
            runner.inherited = item
            for stage, binding in item["stage_bindings"].items():
                if binding["protocol_scope"] != "parent":
                    continue
                result, exited = read_ref(binding["result"]), read_ref(binding["exit"])
                require(exited["returncode"] == 0, "inherited stage has not actually exited zero")
                check_result(read_ref(item["parent_protocol"]), stage, result, runner.task_plan)
                runner.results[stage] = result
                runner.dispatched.add(stage)
            runner.compute_used = item["inherited_compute_seconds"]
            self.runs.append(runner)
            self.active_coordinate[(context["seed"], context["arm"])] = runner
            runner.update("INHERITED_COMPLETED_PHASES_READY")
        # The old run() calls this seam once before its normal queue loop.
        # All other actual coordinates are prepared by its existing factory.
        self.enqueue_remaining()
        return None

    def capture_wait(self, runner, stage, item, *, strict_freshness=True):
        path = runner.root / stage / "pre_cuda_wait/status.json"
        if not path.exists():
            return
        heartbeat = checked(path)
        launch = item["launch"]
        key = (runner.context["id"], stage, launch["pid"], str(launch["birth"]))
        require(
            heartbeat["schema"] == "v39_pre_cuda_admission.v1"
            and heartbeat["protocol_id"] == self.protocol["id"]
            and heartbeat["context_id"] == runner.context["id"]
            and all(heartbeat[k] == launch[k] for k in ("stage", "pid", "gpu_index", "gpu_uuid"))
            and str(heartbeat["birth"]) == str(launch["birth"])
            and heartbeat["deadline_epoch"] == launch["deadline_epoch"]
            and heartbeat["cuda_initialized"] is False,
            "pre-CUDA wait heartbeat does not belong to the owned worker",
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
        current = time.monotonic()
        observed = heartbeat["observed_monotonic"]
        require(
            type(observed) in (int, float)
            and math.isfinite(observed)
            and item["started_monotonic"] <= observed <= current + 1,
            "invalid admission clock binding",
        )
        start = heartbeat["waiting_started_monotonic"]
        end = heartbeat["waiting_finished_monotonic"]
        if start is not None:
            require(
                type(start) in (int, float)
                and math.isfinite(start)
                and item["started_monotonic"] <= start <= observed,
                "wait starts outside owned worker lifetime",
            )
            if phase == "WAITING":
                require(end is None, "open wait has a closed endpoint")
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
            )
        else:
            self._pre_cuda_waiters.pop(key, None)

    def account_resource_wait(self):
        current = time.monotonic()
        if self._resource_waiting:
            self._idle_wait_intervals = merged_intervals(
                [
                    *self._idle_wait_intervals,
                    (self._resource_accounting_at, current),
                ]
            )
        self._resource_accounting_at = current
        for runner in self.runs:
            for stage, item in runner.active.items():
                self.capture_wait(runner, stage, item)
        self.recount_resource_wait()
        self.resource_wait_gate()

    def recount_resource_wait(self):
        intervals = merged_intervals(
            [
                *self._idle_wait_intervals,
                *self._worker_wait_intervals.values(),
            ]
        )
        self.resource_wait_used = self.inherited["inherited_resource_wait_seconds"] + sum(
            end - start for start, end in intervals
        )

    def resource_wait_gate(self):
        if self.resource_wait_used >= parent.RESOURCE_WAIT_SECONDS:
            raise DurablePause("original cumulative 24-hour resource wait budget exhausted")

    def update(self, phase, **extra):
        waiters = list(self._pre_cuda_waiters.values())
        if phase == "RUNNING" and waiters and len(waiters) == sum(len(r.active) for r in self.runs):
            phase = "WAITING_FOR_PRE_CUDA_RESOURCES"
        super().update(
            phase,
            pre_cuda_waiters=waiters,
            inherited_resource_wait_seconds=self.inherited["inherited_resource_wait_seconds"],
            original_time_budgets_reset=False,
            stopped_admission_observation_errors=self._admission_stop_errors,
            **extra,
        )

    def run(self):
        require(
            Path(__file__).resolve() == self.root / "implementation" / FILES[0],
            "run only the committed frozen resource controller",
        )
        self.resource_wait_gate()
        return super().run()


def _routed_module(path, name):
    if (
        Path(path).name == "finqa_v37_evaluation.py"
        and Path(path).parent == ROOT / "implementation"
    ):
        return _base_module(Path(path).with_name("finqa_v39_evaluation.py"), name)
    return _base_module(path, name)


# Only this isolated runtime changes its device scope. Historical validators
# stay untouched, as do every frozen old source and protocol on disk.
parent.ALLOWED_GPUS = ALLOWED_GPUS
parent.checked_protocol = checked_protocol
parent.checked_implementation = checked_implementation
parent.ContextRunner = ContextRunner
parent.eligible = eligible
parent.check_result = check_result
parent._module = _routed_module


def preflight_quiescent(_plan, queue):
    """Validate saved mathematical/stage metadata before signalling old control."""
    checked_implementation(ROOT)
    protocol = checked_parent()
    require(not queue["active_children"], "preflight requires empty parent queue")
    for record in sorted((PARENT_ROOT / "contexts").glob("seed*/*/step*/context/record.json")):
        directory = record.parent.parent
        context, _alias = inheritance._read_context(directory)
        task_plan = read_ref(context["task_plan"]) if context["due_outer"] else None
        for stage in inheritance.STAGES:
            inheritance.inspect_stage(directory / stage, protocol, context, stage, task_plan)
    for path in sorted((PARENT_ROOT / "evaluations").glob("*/generate/launch/record.json")):
        launch = checked(path)
        prefix, arm_key = path.parents[2].name.split("_", 1)
        seed = int(prefix.removeprefix("seed"))
        arm = next(name for name, key in parent.ARM_KEYS.items() if key == arm_key)
        context = dict(id=f"evaluation:{seed}:{arm_key}", seed=seed, arm=arm)
        require(launch["context_id"] == context["id"], "endpoint context changed")
        binding = inheritance.inspect_stage(path.parent.parent, protocol, context, "generate")
        result = read_ref(binding["result"])
        check_result(protocol, "generate", result)


def own_command():
    identity = handoff.process_identity(os.getpid())
    require(
        identity is not None and identity["birth"] == birth(os.getpid()),
        "coordinator process identity unavailable",
    )
    return identity["argv"]


def migrate(root=ROOT):
    root = Path(root).resolve()
    require(
        root == ROOT and Path(__file__).resolve() == root / "implementation" / FILES[0],
        "run only the prepared frozen migration entry",
    )
    checked_implementation(root)
    preparation = checked(root / "preparation/record.json")
    require(preparation["user_consent"] == "同意", "controlled handoff consent missing")
    publish(
        root / "migration_launch/record.json",
        dict(
            schema="v39_single_controlled_handoff_launch.v1",
            at=now(),
            preparation=entry(root / "preparation/record.json"),
            pid=os.getpid(),
            birth=birth(os.getpid()),
            command=own_command(),
            automatic_retry=False,
            workers_signalled=False,
        ),
    )

    def continue_once(_closeout, release_barrier):
        # Old processes have exited. Build all CPU state while old leases remain
        # blocked; only then release and continue in this same coordinator PID.
        initialize(root, handoff_record=HANDOFF_ROOT / "closeout/record.json")
        controller = Controller(root)
        billing = release_barrier()
        charged_wait = max(
            controller.inherited["inherited_resource_wait_seconds"],
            math.ceil(billing["global_resource_wait_seconds"]),
        )
        controller.inherited["inherited_resource_wait_seconds"] = charged_wait
        controller.resource_wait_used = charged_wait
        controller._resource_waiting = True
        controller._resource_accounting_at = time.monotonic()
        controller.resource_wait_gate()
        publish(
            root / "launch_01/record.json",
            dict(
                schema="v39_single_continuation_launch.v1",
                at=now(),
                protocol_id=controller.protocol["id"],
                pid=os.getpid(),
                birth=birth(os.getpid()),
                command=own_command(),
                barrier_release=entry(HANDOFF_ROOT / "barrier_release/record.json"),
                inherited_global_wait_at_dispatch=charged_wait,
                automatic_restart=False,
                new_pilot_repeated=False,
            ),
        )
        return controller.run()

    return handoff.run(
        HANDOFF_ROOT, on_quiesced=continue_once, validate_quiescent=preflight_quiescent
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "migrate", "inspect"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    if args.action == "prepare":
        require(args.source_commit is not None, "committed source required")
        result = prepare(args.root, source_commit=args.source_commit)
    elif args.action == "migrate":
        migrate(args.root)
        return
    else:
        result = checked_protocol(args.root)
    print(json.dumps(dict(id=result["id"], root=str(args.root)), sort_keys=True))


if __name__ == "__main__":
    main()
