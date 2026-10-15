"""Measured host-memory admission after a verified natural zero-worker handoff.

The complete V44 package remains byte-identical. This shell changes startup RAM
reservation only; five-worker capacity, runtime hard gates and maths stay fixed.
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
import finqa_v41_memory_policy as memory_policy
import finqa_v43_time_policy as time_policy
import finqa_v45_admission as admission
import finqa_v45_inheritance as inheritance

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
SOURCE_ROOT = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01/v25_training_replication_01"
)
PARENT_ROOT = SOURCE_ROOT / "production_resume_01/recovery_04"
SOURCE_BUNDLE = SOURCE_ROOT / "production_resume_01/concurrency_five_01/implementation"
ROOT = SOURCE_ROOT / "production_resume_01/host_memory_admission_01"
SOURCE_PROTOCOL_ID = "93d74f870865e1ecd40b93c77155d8a2fb00d33ef47960cd33c99847af731d60"
PARENT_IMPLEMENTATION_ID = "6a2fff0351f5716ad971df6ad1d25ab898dd9e650feec9f8b339b1bfaaaeb209"
SOURCE_IMPLEMENTATION_ID = "91b1f5b0c5fb4e57e746f48128fdb67c0ddef5e30d84f41263d38505769a4256"
SOURCE_PREPARATION_ID = "218c1620fa3d0a5ac2ab547e95dad3ec36944eb455e110e933a7feef9a7eae87"
SOURCE_SUPERSESSION_ID = "ab3569b9334a623e6bf43224069c701f1031ad38ab39084d78700333282e1e66"
PROTOCOL_SCHEMA = "v45_five_worker_supervised_protocol.v1"
MAX_GPU_WORKERS = 5
FILES = (
    "finqa_v45_controller.py",
    "finqa_v45_supervisor.py",
    "finqa_v45_inheritance.py",
    "finqa_v45_handoff.py",
    "finqa_v45_worker.py",
    "finqa_v45_evaluation.py",
    "finqa_v45_admission.py",
)
ALLOWED_GPUS = tuple(range(8))
DISPATCH_ORDER = (5, 2, 0, 4, 3, 7, 1, 6)


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
verifier = _module(SOURCE_BUNDLE / "finqa_v43_controller.py", __name__ + "_historical_v43")
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


def checked_source_bundle():
    protocol = verifier.checked_protocol(PARENT_ROOT)
    original = verifier.checked_implementation(PARENT_ROOT)
    value = checked(SOURCE_BUNDLE / "record.json")
    preparation = checked(SOURCE_BUNDLE.parent / "preparation/record.json")
    require(
        protocol["id"] == SOURCE_PROTOCOL_ID
        and original["id"] == PARENT_IMPLEMENTATION_ID
        and len(original["sha256"]) == 67
        and value["id"] == SOURCE_IMPLEMENTATION_ID
        and len(value["sha256"]) == 74
        and preparation["id"] == SOURCE_PREPARATION_ID
        and preparation["implementation"] == entry(SOURCE_BUNDLE / "record.json")
        and preparation["parent_protocol"] == entry(PARENT_ROOT / "protocol/record.json"),
        "frozen V44 source preparation or V43 scientific parent identity changed",
    )
    for name, expected in value["sha256"].items():
        require(sha(SOURCE_BUNDLE / name) == expected, "frozen V44 source changed: " + name)
        if name in original["sha256"]:
            require(expected == original["sha256"][name], "original V43 source changed")
    return value


def freeze(root, commit):
    commit = subprocess.check_output(
        ["git", "rev-parse", commit + "^{commit}"], cwd=REPO, text=True
    ).strip()
    old = checked_source_bundle()
    sources = {name: (SOURCE_BUNDLE / name).read_bytes() for name in old["sha256"]}
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=REPO)
        require(
            hashlib.sha256(raw).hexdigest() == sha(REPO / relative),
            "uncommitted V45 source: " + name,
        )
        sources[name] = raw
    require(len(sources) == 81, "seven new and 74 byte-identical original files required")
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
            schema="v45_five_worker_committed_implementation.v1",
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
    require(allowed_root(root), "unregistered five-worker root")
    value, old = checked(root / "implementation/record.json"), checked_source_bundle()
    require(
        value["schema"] == "v45_five_worker_committed_implementation.v1"
        and value["committed_files"] == list(FILES)
        and len(value["sha256"]) == 81
        and set(value["sha256"]) == set(old["sha256"]) | set(FILES)
        and value["original_implementation"] == entry(SOURCE_BUNDLE / "record.json"),
        "V45 execution ownership changed",
    )
    for name, expected in value["sha256"].items():
        require(sha(root / "implementation" / name) == expected, "frozen bytes changed: " + name)
        if name in old["sha256"]:
            require(expected == old["sha256"][name], "original V44 source modified")
    if root != ROOT:
        require(
            value == checked(ROOT / "implementation/record.json"),
            "automatic attempt changed frozen implementation",
        )
    return value


def policy_record():
    value = copy.deepcopy(verifier.policy_record())
    require(
        value["admission"]["maximum_total_workers_including_initializing_and_draining"] == 4,
        "historical admission cap changed",
    )
    value["admission"]["maximum_total_workers_including_initializing_and_draining"] = (
        MAX_GPU_WORKERS
    )
    return value


def host_policy_record():
    value = admission.host_policy_record()
    references = value.get("evidence_refs")
    require(isinstance(references, list) and references, "measured host policy needs evidence")
    for reference in references:
        require(isinstance(reference, dict), "host policy evidence reference required")
        read_ref(reference)
    return value


def checked_supersession():
    path = SOURCE_BUNDLE.parent / "superseded_host_admission_01/record.json"
    value = checked(path)
    closeout = read_ref(value["handoff_closeout"])
    read_ref(value["intent"])
    target = value["target"]
    require(
        value["id"] == SOURCE_SUPERSESSION_ID
        and value["schema"] == "v45_unactivated_v44_migration_superseded.v1"
        and value["target_process_exited"] is True
        and value["scientific_protocol_created"] is False
        and value["original_science_continues"] is True
        and value["migration_signals_sent"] == 1
        and value["worker_signals_sent"] == 0
        and value["scientific_supervisor_signals_sent"] == 0
        and value["scientific_controller_signals_sent"] == 0
        and closeout["status"] == "STOPPED_NO_MIGRATION"
        and birth(target["pid"]) != target["birth"]
        and not (SOURCE_BUNDLE.parent / "protocol/record.json").exists(),
        "previous unactivated V44 migration must be verifiably stopped before V45 preparation",
    )
    return entry(path)


def authorization_body(*, parentroot, automatic):
    return dict(
        schema="v45_explicit_five_worker_authority.v1",
        at=now(),
        user_instruction="修改此问题",
        user_consent="修改此问题",
        five_worker_authorization="暂时增至五个",
        dispatch_priority_authorization="GPU2，5应当都可派发任务，此轮修订尽量将这两张显卡利用起来",
        dispatch_priority=list(DISPATCH_ORDER),
        max_gpu_workers=5,
        max_workers_per_gpu=1,
        host_ram_admission_changed=True,
        host_ram_runtime_hard_gates_unchanged=True,
        time_limits_removed=True,
        automatic_recovery_authorized=True,
        unknown_feedback_retry_allowed=False,
        automatic_attempt=automatic,
        prior_time_and_safe_recovery_authority_inherited=True,
        new_sampling_or_optimizer_dose_authorized=False,
        logical_class_shards=4,
        parent_protocol=entry(Path(parentroot) / "protocol/record.json"),
        manual_stop_terminates_supervision=True,
    )


def prepare(root=ROOT, *, source_commit, parentroot=PARENT_ROOT):
    root, parentroot = Path(root).resolve(), Path(parentroot).resolve()
    require(root == ROOT and not root.exists(), "one fresh five-worker preparation")
    supersession = checked_supersession()
    original = verifier.checked_protocol(parentroot)
    require(
        original["schema"] == "v43_explicit_no_deadline_supervised_protocol.v1",
        "only current V43 may undergo this resource transition",
    )
    host_policy = host_policy_record()
    implementation = freeze(root, source_commit)
    publish(
        root / "authorization/record.json",
        authorization_body(parentroot=parentroot, automatic=False),
    )
    preparation = publish(
        root / "preparation/record.json",
        dict(
            schema="v45_natural_five_worker_transition_preparation.v1",
            at=now(),
            implementation=entry(root / "implementation/record.json"),
            source_commit=implementation["source_commit"],
            authorization=entry(root / "authorization/record.json"),
            parent_root=str(parentroot),
            parent_protocol=entry(parentroot / "protocol/record.json"),
            prior_unactivated_migration_supersession=supersession,
            max_gpu_workers=5,
            host_ram_admission_changed=True,
            host_ram_runtime_hard_gates_unchanged=True,
            host_admission_policy=host_policy,
            handoff_mode="pinned_natural_lease_drain",
            worker_signals_allowed=False,
            new_scientific_controller_started=False,
            live_parent_modified=False,
        ),
    )
    handoff = _module(root / "implementation/finqa_v45_handoff.py", __name__ + "_new_handoff")
    handoff.register(root, parentroot, entry(root / "authorization/record.json"))
    return preparation


def checked_preparation():
    value = checked(ROOT / "preparation/record.json")
    require(
        value["schema"] == "v45_natural_five_worker_transition_preparation.v1"
        and value["max_gpu_workers"] == 5
        and value["host_ram_admission_changed"] is True
        and value["host_ram_runtime_hard_gates_unchanged"] is True
        and value["host_admission_policy"] == host_policy_record()
        and value["prior_unactivated_migration_supersession"] == checked_supersession()
        and value["handoff_mode"] == "pinned_natural_lease_drain"
        and value["worker_signals_allowed"] is False
        and value["implementation"] == entry(ROOT / "implementation/record.json")
        and value["authorization"] == entry(ROOT / "authorization/record.json"),
        "five-worker transition preparation changed",
    )
    return value


def protocol_body(root, implementation, initial, *, at):
    root = Path(root).resolve()
    preparation = checked_preparation()
    inherited = checked(root / "inheritance/record.json")
    old = read_ref(preparation["parent_protocol"])
    body = copy.deepcopy({key: value for key, value in old.items() if key != "id"})
    body.update(
        schema=PROTOCOL_SCHEMA,
        at=at,
        output_root=str(root),
        supervision_root=str(ROOT),
        implementation_id=implementation["id"],
        source_commit=implementation["source_commit"],
        authority="修改过保守主存准入；暂时五 worker、运行硬门和科学合同不变",
        authorization=entry(root / "authorization/record.json"),
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
        gpu_admission_policy=policy_record(),
        max_gpu_workers=MAX_GPU_WORKERS,
        max_workers_per_gpu=1,
        dispatch_priority=list(DISPATCH_ORDER),
        host_ram_admission_changed=True,
        host_ram_runtime_hard_gates_unchanged=True,
        host_admission_policy=preparation["host_admission_policy"],
        logical_class_shards=4,
        inherited_resource_wait_seconds=inherited["inherited_resource_wait_seconds"],
        inherited_pilot_acceptance=entry(PARENT_ROOT / "pilot_acceptance/record.json"),
        pilot_repeated=False,
        clean_handoff_claimed=root == ROOT,
        historical_failures_unchanged=True,
        automatic_recovery=dict(
            fresh_independent_attempt_only=True,
            same_point_actual_boundaries_only=True,
            no_unknown_feedback_retry=True,
            numerical_or_binding_failure_stops=True,
            manual_stop_is_terminal=True,
            backoff_seconds=[30, 60, 120, 300],
            supervisor="finqa_v45_supervisor.py",
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
            schema="v45_actual_boundary_initial_state.v1",
            at=now(),
            source_snapshot=inherited["actual_final_progress"],
        ),
    )
    publish(
        root / "pilot_acceptance/record.json",
        dict(
            schema="v45_read_only_inherited_pilot.v1",
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


def initialize(root=ROOT, *, handoff_record):
    root = Path(root).resolve()
    require(
        root == ROOT and not (root / "protocol/record.json").exists(),
        "one clean handoff initialization",
    )
    implementation, preparation = checked_implementation(root), checked_preparation()
    publish(
        root / "activation_registration/record.json",
        dict(
            schema="v45_clean_handoff_activation.v1",
            at=now(),
            handoff=entry(Path(handoff_record)),
            preparation=entry(ROOT / "preparation/record.json"),
            scientific_controller_started=False,
        ),
    )
    inherited = inheritance.initialize_parent_handoff(
        root,
        Path(preparation["parent_root"]),
        handoff_record=handoff_record,
        authorization_record=entry(root / "authorization/record.json"),
    )
    return _finish_initialization(root, implementation, inherited)


def prepare_automatic(root, *, parentroot):
    root, parentroot = Path(root).resolve(), Path(parentroot).resolve()
    require(
        allowed_root(root) and root != ROOT and not root.exists(),
        "automatic recovery requires a fresh numbered five-worker attempt",
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
            schema="v45_automatic_activation.v1",
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
        "five-worker protocol changed",
    )
    admission.validate_plan(plan)
    time_policy.validate(plan)
    return plan


def check_result(protocol, stage, result, task_plan=None):
    _original_check_result(protocol, stage, result, task_plan)
    if protocol.get("schema") != PROTOCOL_SCHEMA:
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
    return runtime.eligible(row, protocol, stage, context)


class LeasePool(parent.LeasePool):
    """Five-worker capacity with measured startup RAM and unchanged hard gates."""

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
        if len(self.leases) >= MAX_GPU_WORKERS:
            return None
        if not self._host_admission(stage):
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


class ContextRunner(runtime.ContextRunner):
    def launch(self, stage, row, lease):
        self._lifecycle_launch_gate()
        require(
            stage in self.pending() and stage not in self.dispatched, "unregistered next V45 stage"
        )
        require(not (self.root / stage / "launch/record.json").exists(), "no automatic retry")
        self.controller.disk_gate(0)
        phase, _ = self.stage_limit(stage)
        current = time.monotonic()
        self.phase_started.setdefault(phase, current)
        deadline_epoch = None
        if self.evaluation:
            arguments = [
                str(self.controller.root / "implementation/finqa_v45_evaluation.py"),
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
                str(self.controller.root / "implementation/finqa_v45_worker.py"),
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
                env=parent.worker_environment(row),
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        launch = dict(
            schema="v45_five_worker_stage_launch.v1",
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
        self._registered_at = datetime.fromisoformat(
            checked(self.root / "activation_registration/record.json")["at"]
        ).timestamp()

    def update(self, phase, **extra):
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
            len(active) <= MAX_GPU_WORKERS
            and len({row["gpu_index"] for row in active}) == len(active),
            "five-worker or one-worker-per-device cap violated",
        )
        waiters = list(self._pre_cuda_waiters.values())
        if phase == "RUNNING" and waiters and len(waiters) == len(active):
            phase = "WAITING_FOR_PRE_CUDA_RESOURCES"
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
                pre_cuda_waiters=waiters,
                inherited_resource_wait_seconds=self.inherited["inherited_resource_wait_seconds"],
                stopped_admission_observation_errors=self._admission_stop_errors,
                original_B_resume_authorized=True,
                max_gpu_workers=5,
                host_ram_admission_changed=True,
                host_ram_runtime_hard_gates_unchanged=True,
                last_host_admission=copy.deepcopy(self.pool.last_host_admission),
                **extra,
            ),
        )

    def run(self):
        require(
            Path(__file__).resolve() == self.root / "implementation" / FILES[0],
            "only the frozen five-worker controller may run",
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
                schema="v45_single_five_worker_controller_launch.v1",
                at=now(),
                protocol_id=self.protocol["id"],
                pid=os.getpid(),
                birth=birth(os.getpid()),
                command=runtime.own_command(),
                max_gpu_workers=5,
                inherited_resource_wait_before_initialization=self._original_inherited_wait,
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
        return _original_module(Path(path).with_name("finqa_v45_evaluation.py"), name)
    return _original_module(path, name)


# Only the new, isolated V43/V39/V37 execution shell is rebound. The historical
# verifier and all 74 source files remain unmodified and independently checked.
runtime.ROOT = ROOT
runtime.checked_protocol = checked_protocol
runtime.checked_implementation = checked_implementation
runtime.inheritance = inheritance
runtime.ContextRunner = ContextRunner
runtime.LeasePool = LeasePool
runtime.check_result = check_result
runtime.DISPATCH_ORDER = DISPATCH_ORDER
runtime.admission = admission
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "initialize", "run", "inspect"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit")
    parser.add_argument("--parent-root", type=Path, default=PARENT_ROOT)
    parser.add_argument("--handoff-record", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        require(args.source_commit is not None, "committed source required")
        value = prepare(args.root, source_commit=args.source_commit, parentroot=args.parent_root)
    elif args.action == "initialize":
        require(args.handoff_record is not None, "verified clean handoff receipt required")
        value = initialize(args.root, handoff_record=args.handoff_record)
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
