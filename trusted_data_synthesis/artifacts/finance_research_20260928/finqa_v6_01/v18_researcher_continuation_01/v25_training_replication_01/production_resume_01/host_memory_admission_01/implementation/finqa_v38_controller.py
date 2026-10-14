"""One explicitly authorized V37 recovery, with bounded CPU-only admission.

The original controller, lifecycle, mathematics and training are copied verbatim
into this episode's implementation. Only stage routing, parent inheritance and
pre-CUDA external-resource accounting are adapted here. No failed old controller
is restarted, no completed parent work is relabeled and no budget is reset.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import finqa_v38_inheritance as inheritance

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
PARENT_ROOT = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01/v25_training_replication_01/production_resume_01"
)
ROOT = PARENT_ROOT / "recovery_01"
FILES = (
    "finqa_v38_controller.py",
    "finqa_v38_worker.py",
    "finqa_v38_admission.py",
    "finqa_v38_inheritance.py",
    "finqa_v38_evaluation.py",
)
PARENT_PROTOCOL_ID = "9f0b0ad6450a8c0d4aec697901e6c28f5bca4d291c45942f3238ffecca14c255"
PARENT_IMPLEMENTATION_ID = "97d06d127334a0d18a85345c709cbae6faa09ad902714e1b99b2b86d8154b27e"


def _load_parent():
    directory = Path(__file__).resolve().parent
    source = (
        directory if directory.name == "implementation" else PARENT_ROOT / "implementation"
    ) / "finqa_v37_controller.py"
    manifest = inheritance.checked(PARENT_ROOT / "implementation/record.json")
    inheritance.require(manifest["id"] == PARENT_IMPLEMENTATION_ID, "parent seal changed")
    inheritance.require(
        hashlib.sha256(source.read_bytes()).hexdigest() == manifest["sha256"][source.name],
        "original controller source changed",
    )
    name = __name__ + "_sealed_parent"
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


parent = _load_parent()
_parent_checked_protocol = parent.checked_protocol
_parent_checked_implementation = parent.checked_implementation
_parent_module = parent._module
require, checked, publish = parent.require, parent.checked, parent.publish
entry, read_ref, file_ref = parent.entry, parent.read_ref, parent.file_ref
now, sha, birth, status = parent.now, parent.sha, parent.birth, parent.status
DurablePause = parent.DurablePause


def __getattr__(name):
    return getattr(parent, name)


def verify_parent_stopped():
    plan = _parent_checked_protocol(PARENT_ROOT)
    require(plan["id"] == PARENT_PROTOCOL_ID, "only the audited failed V37 episode may recover")
    failure = checked(PARENT_ROOT / "failure/record.json")
    queue = json.loads((PARENT_ROOT / "queue/status.json").read_bytes())
    require(
        failure["phase"] == queue["phase"] == "STOPPED_FAILURE_NO_RETRY"
        and failure["protocol_id"] == queue["protocol_id"] == plan["id"]
        and not queue["active_children"]
        and not queue["pilot_accepted"]
        and queue["accepted_new_optimizer_updates"] == queue["accepted_new_outer_updates"] == 0,
        "parent is not the audited, uncommitted stopped episode",
    )
    launch = checked(PARENT_ROOT / "launch_01/record.json")
    require(birth(launch["pid"]) != str(launch["birth"]), "parent controller is still live")
    return plan


def freeze(root, commit):
    commit = subprocess.check_output(
        ["git", "rev-parse", commit + "^{commit}"], cwd=REPO, text=True
    ).strip()
    require(len(commit) == 40, "committed recovery sources required")
    original = _parent_checked_implementation(PARENT_ROOT)
    require(original["id"] == PARENT_IMPLEMENTATION_ID, "parent implementation changed")
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
            schema="v38_committed_admission_recovery_implementation.v1",
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
        return _parent_checked_implementation(root)
    require(root == ROOT, "fixed independent recovery root required")
    manifest = checked(root / "implementation/record.json")
    original = _parent_checked_implementation(PARENT_ROOT)
    require(
        original["id"] == PARENT_IMPLEMENTATION_ID
        and manifest["schema"] == "v38_committed_admission_recovery_implementation.v1"
        and manifest["committed_files"] == list(FILES)
        and list(manifest["sha256"]) == [*FILES, *original["sha256"]]
        and manifest["unchanged_parent_implementation"]
        == entry(PARENT_ROOT / "implementation/record.json"),
        "recovery execution seal changed",
    )
    for name, expected in manifest["sha256"].items():
        require(sha(root / "implementation" / name) == expected, "frozen source changed: " + name)
        if name in original["sha256"]:
            require(expected == original["sha256"][name], "parent scientific code changed")
    return manifest


def protocol_body(root, implementation, initial, *, at):
    root = Path(root)
    inherited = checked(root / "inheritance/record.json")
    body = parent.protocol_body(root, implementation, initial, at=at)
    body.update(
        schema="v38_same_point_admission_recovery_protocol.v1",
        authority="用户明确要求：修复问题，继续实验；独立登记一次原V37受控恢复",
        parent_protocol=entry(PARENT_ROOT / "protocol/record.json"),
        parent_failure=entry(PARENT_ROOT / "failure/record.json"),
        inheritance=entry(root / "inheritance/record.json"),
        inherited_compute_seconds=inherited["inherited_compute_seconds"],
        inherited_distribution_seconds=inherited["inherited_distribution_seconds"],
        inherited_resource_wait_seconds=inherited["inherited_resource_wait_seconds"],
        original_budgets_reset=False,
        resource_wait_scope=(
            "global union of zero-owned-lease ready-work idle intervals and all worker "
            "pre-CUDA GPU admission wait intervals; plus conservative inherited time; "
            "pre-CUDA wait also consumes unchanged stage and outer compute deadlines"
        ),
        recovery_scope=dict(
            completed_parent_stages=list(inheritance.INHERITED_STAGES),
            parent_tasks=744,
            parent_valid_rows=4974,
            parent_completed_responses=527,
            inherited_response_denominator=700,
            first_new_stage="distribution",
            first_outer_commits=1,
            first_SFT_step=1193,
            inherited_stages_redispatched=False,
            inherited_context_rewritten=False,
            inherited_results_relabelled=False,
            rest_of_original_matrix_after_real_pilot_exit=True,
        ),
        pre_cuda_admission=dict(
            busy_GPU_same_worker_bounded_wait=True,
            worker_slot_GPU_lease_and_point_locks_retained=True,
            CUDA_must_remain_uninitialized=True,
            wrong_or_missing_UUID_hard_failure=True,
            host_memory_stop_and_deadline_gates_unchanged=True,
            after_CUDA_no_retry=True,
            process_interference_allowed=False,
            poll_seconds=10,
            heartbeat_freshness_seconds=60,
        ),
    )
    return body


def initialize(root=ROOT, *, source_commit):
    root = Path(root).resolve()
    require(root == ROOT and not root.exists(), "one fresh recovery registration; never overwrite")
    verify_parent_stopped()
    implementation = freeze(root, source_commit)
    publish(
        root / "audit/record.json",
        dict(
            schema="v38_user_authorized_pre_cuda_recovery.v1",
            at=now(),
            user_instruction="修复问题，继续实验",
            parent_failure=entry(PARENT_ROOT / "failure/record.json"),
            diagnosis="External GPU4 process arrived during CPU preparation; unchanged UUID",
            observed_parent_lifecycle=[
                entry(
                    PARENT_ROOT
                    / inheritance.FIRST_CONTEXT
                    / "lifecycle"
                    / f"event{number:06d}/record.json"
                )
                for number in (2674, 2678, 2682)
            ],
            historical_failure_reclassified=False,
            explicit_single_recovery=True,
            automatic_retry=False,
        ),
    )
    inheritance.initialize_parent_recovery(root, PARENT_ROOT)
    training, rt, contexts, _cache = parent.production_modules(root)
    snapshot = contexts.production_snapshot(
        training=training, rt=rt, training_root=parent.TRAINING_ROOT
    )
    require(
        {(r["seed"], r["arm"]): r["step"] for r in snapshot["arms"]} == parent.INITIAL_STEPS
        and snapshot["completed_physical_updates"] == 5812
        and snapshot["remaining_physical_updates"] == 5810
        and snapshot["completed_outers"] == 9
        and snapshot["remaining_outers"] == 15
        and len(snapshot["pending_sealed_outers"]) == 3,
        "original matrix advanced outside this controlled recovery",
    )
    initial = publish(root / "initial_state/record.json", snapshot)
    plan = publish(
        root / "protocol/record.json", protocol_body(root, implementation, initial, at=now())
    )
    status(
        root,
        dict(phase="REGISTERED_NOT_STARTED", protocol_id=plan["id"], active_children=[]),
    )
    return plan


def checked_protocol(root=ROOT):
    root = Path(root).resolve()
    if root == PARENT_ROOT:
        return _parent_checked_protocol(root)
    require(root == ROOT, "fixed independent recovery root required")
    implementation = checked_implementation(root)
    plan = checked(root / "protocol/record.json")
    initial = checked(root / "initial_state/record.json")
    require(
        {k: v for k, v in plan.items() if k != "id"}
        == protocol_body(root, implementation, initial, at=plan["at"]),
        "recovery protocol changed",
    )
    verify_parent_stopped()
    return plan


def merged_intervals(intervals):
    """Union elapsed monotonic intervals so simultaneous waits are not multiplied."""
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


class ContextRunner(parent.ContextRunner):
    def stage_limit(self, stage):
        phase, budget = super().stage_limit(stage)
        if (
            stage == "distribution"
            and self.context["id"] == self.controller.inherited["original_context_id"]
        ):
            budget -= self.controller.inherited["inherited_distribution_seconds"]
        return phase, budget

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
                str(self.controller.root / "implementation/finqa_v38_evaluation.py"),
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
                str(self.controller.root / "implementation/finqa_v38_worker.py"),
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
            schema="v38_owned_production_stage_launch.v1",
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
        super().__init__(root)
        self.inherited = read_ref(self.protocol["inheritance"])
        self.resource_wait_used = self.inherited["inherited_resource_wait_seconds"]
        self._idle_wait_intervals = []
        self._worker_wait_intervals = {}
        self._pre_cuda_waiters = {}
        self._last_wait_sequences = {}
        self._admission_stop_errors = []

    def create_context(self, coordinate, *, pilot=False):
        if not pilot:
            return super().create_context(coordinate, pilot=False)
        require(coordinate == parent.FIRST and not self.runs, "one inherited first gate only")
        context = read_ref(self.inherited["original_context"])
        directory = Path(self.inherited["new_context_directory"])
        require(
            inheritance.resolve_origin_context(directory, self.protocol)
            == Path(self.inherited["origin_context_directory"]),
            "parent alias changed",
        )
        runner = ContextRunner(self, directory, context)
        for stage in inheritance.INHERITED_STAGES:
            binding = self.inherited["stage_bindings"][stage]
            result, exited = read_ref(binding["result"]), read_ref(binding["exit"])
            require(exited["returncode"] == 0, "parent stage did not actually exit successfully")
            parent.check_result(
                read_ref(self.inherited["parent_protocol"]), stage, result, runner.task_plan
            )
            runner.results[stage] = result
            runner.dispatched.add(stage)
        runner.compute_used = self.inherited["inherited_compute_seconds"]
        self.runs.append(runner)
        self.active_coordinate[coordinate] = runner
        runner.update("INHERITED_COMPLETE_STAGES_READY_FOR_DISTRIBUTION")
        return runner

    def capture_wait(self, runner, stage, item, *, strict_freshness=True):
        path = runner.root / stage / "pre_cuda_wait/status.json"
        if not path.exists():
            return
        heartbeat = checked(path)
        launch = item["launch"]
        key = (runner.context["id"], stage, launch["pid"], str(launch["birth"]))
        require(
            heartbeat["schema"] == "v38_pre_cuda_admission.v1"
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
            "run only the committed frozen recovery controller",
        )
        return super().run()


def _routed_module(path, name):
    # The original final all-nine-seal barrier calls this one evaluator seam.
    if (
        Path(path).name == "finqa_v37_evaluation.py"
        and Path(path).parent == ROOT / "implementation"
    ):
        return _parent_module(Path(path).with_name("finqa_v38_evaluation.py"), name)
    return _parent_module(path, name)


# Adapt the copied original module in memory, never its frozen file or old root.
# Its ROOT/FILES stay unchanged so its original parent validator remains valid.
parent.checked_protocol = checked_protocol
parent.checked_implementation = checked_implementation
parent.ContextRunner = ContextRunner
parent._module = _routed_module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize", "run", "inspect"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    if args.action == "initialize":
        require(args.source_commit is not None, "committed source required")
        plan = initialize(args.root, source_commit=args.source_commit)
    elif args.action == "run":
        Controller(args.root).run()
        return
    else:
        plan = checked_protocol(args.root)
    print(json.dumps(dict(id=plan["id"], output_root=str(ROOT)), sort_keys=True))


if __name__ == "__main__":
    main()
