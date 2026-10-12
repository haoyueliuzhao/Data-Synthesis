"""Original-B production continuation with one global four-GPU lease pool.

Each real checkpoint owns its own durable context, complete-task cache, virtual
point, feedback, response accumulator and distribution. The first C137/1192
outer plus its next actual SFT step gates the remainder of the original matrix.
No fixed-reference replay, score-based selection, implicit retry or fallback.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("/data1/zhuxinrui/projects/Data-Synthesis")
SOURCE_ROOT = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01/v25_training_replication_01"
)
ROOT = SOURCE_ROOT / "production_resume_01"
TRAINING_ROOT = SOURCE_ROOT / "training_replication"
EVALUATION_ROOT = SOURCE_ROOT / "replication_evaluation"
MATH_SOURCE = SOURCE_ROOT / "replay_performance_04"
VERIFIED_SOURCE = MATH_SOURCE / "recovery_02"
PAUSE = SOURCE_ROOT / "four_gpu_release_01/experiment_pause_01"
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/08acbd89-e289-4bba-84e6-171504257744/已粘贴的文本.txt"
)
V36_RESULT_ID = "6503a38618e6456a80a9a126cde04f665bac7367158bf45b0d6d16e758d1e0d0"
V36_PROTOCOL_ID = "a3233f775b8590d9ded49a68a65df6b719c1fe73d43a74a2ecdf2b9179c5b819"
FILES = (
    "finqa_v37_controller.py",
    "finqa_v37_worker.py",
    "finqa_v37_task_cache.py",
    "finqa_v37_training.py",
    "finqa_v37_evaluation.py",
)
ALLOWED_GPUS = (3, 4, 5, 7)
SHARDS = tuple(f"shard{index:02d}" for index in range(4))
STAGES = (*SHARDS, "virtual_point", "replay_R3", "distribution", "train", "generate")
SEEDS = (137, 251, 389)
ARMS = ("Static", "C-only", "Full")
ARM_KEYS = dict(zip(ARMS, ("static", "c_only", "full"), strict=True))
FIRST = (137, "C-only")
INITIAL_STEPS = {
    (137, "Static"): 1490,
    (137, "C-only"): 1192,
    (137, "Full"): 1192,
    (251, "Static"): 1490,
    (251, "C-only"): 894,
    (251, "Full"): 419,
    (389, "Static"): 327,
    (389, "C-only"): 298,
    (389, "Full"): 298,
}
GIB = 1024**3
MAXIMUM_ALLOCATED_BYTES = 76 * GIB
MINIMUM_DEVICE_FREE_BYTES = 2 * GIB
MINIMUM_FREE_MIB = 72 * 1024
OUTER_COMPUTE_SECONDS = 24 * 3600
RESOURCE_WAIT_SECONDS = 24 * 3600
TERM_GRACE_SECONDS = 600
POLL_SECONDS = 10
STAGE_LIMITS = dict(
    class_gradients=12 * 3600,
    virtual_existing=2 * 3600,
    virtual_first_sampling=12 * 3600,
    replay_R3=16 * 3600,
    distribution=2 * 3600,
    train=8 * 3600,
    generate=12 * 3600,
)
HOST_RAM = dict(
    shard_rss_limit_bytes=160 * GIB, coordinator_rss_limit_bytes=192 * GIB, reserve_bytes=96 * GIB
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _sealed(path):
    body = json.loads(Path(path).read_bytes())
    actual = hashlib.sha256(
        json.dumps(
            {k: v for k, v in body.items() if k != "id"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    require(body.get("id") == actual, "record identity changed: " + str(path))
    return body


# These existing, immutable helpers contain no model construction at import.
_helper_directory = VERIFIED_SOURCE / "recovery_implementation"
_helper_manifest = _sealed(_helper_directory / "record.json")
for _name in ("finqa_v35_task_controller.py", "finqa_v36_controller.py", "finqa_v36_lifecycle.py"):
    require(
        hashlib.sha256((_helper_directory / _name).read_bytes()).hexdigest()
        == _helper_manifest["sha256"][_name],
        "verified lifecycle helper changed",
    )
_v36 = _module(_helper_directory / "finqa_v36_controller.py", __name__ + "_verified_v36")
base = _v36.base
LifecycleMixin = _v36.lifecycle.LifecycleMixin
checked, publish, digest, sha = base.checked, base.publish, base.digest, base.sha
entry, file_ref, read_ref, now = base.entry, base.file_ref, base.read_ref, base.now
inventory, birth, signal_owned = base.inventory, base.birth, base.signal_owned
host_memory, process_memory = base.host_memory, base.process_memory
worker_environment, frozen_training_module = base.worker_environment, base.frozen_training_module
status = base.status
PYTHON = REPO / "trusted_data_synthesis/.venv/bin/python"


def checked_engineering_evidence():
    result = checked(VERIFIED_SOURCE / "result/record.json")
    protocol = checked(VERIFIED_SOURCE / "protocol/record.json")
    require(
        result["id"] == V36_RESULT_ID
        and result["status"] == "COMPLETE"
        and result["numeric_pass"] is True
        and result["protocol_id"] == V36_PROTOCOL_ID
        and protocol["id"] == V36_PROTOCOL_ID,
        "completed fixed-point evidence changed",
    )
    _v36.checked_v36_implementation(VERIFIED_SOURCE)
    return protocol


def verify_old_controller_stopped():
    """Do not rewrite or reopen the historical queue; new authority is separate."""
    queue_root = SOURCE_ROOT / "four_gpu_release_01"
    snapshot = json.loads((queue_root / "queue/status.json").read_bytes())
    require(not snapshot.get("active_children"), "historical queue still owns live workers")
    for path in (
        queue_root / "launch_01/record.json",
        queue_root / "gpu_scope_01/launch_01/record.json",
    ):
        if path.exists():
            value = checked(path)
            pid = value.get("pid", value.get("controller_pid"))
            born = value.get("birth", value.get("controller_birth"))
            require(
                pid is not None and born is not None and birth(pid) != str(born),
                "historical controller is still live",
            )
    return snapshot


def freeze(root, commit):
    commit = subprocess.check_output(
        ["git", "rev-parse", commit + "^{commit}"], cwd=REPO, text=True
    ).strip()
    require(len(commit) == 40, "committed production sources required")
    original = base.checked_implementation(MATH_SOURCE)
    sources = {}
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=REPO)
        require(
            hashlib.sha256(raw).hexdigest() == sha(REPO / relative), "uncommitted source: " + name
        )
        sources[name] = raw
    for name, expected in original["sha256"].items():
        raw = (MATH_SOURCE / "implementation" / name).read_bytes()
        require(
            hashlib.sha256(raw).hexdigest() == expected, "inherited mathematical source changed"
        )
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
            schema="v37_committed_production_implementation.v1",
            at=now(),
            source_commit=commit,
            committed_files=list(FILES),
            original_mathematical_implementation=entry(MATH_SOURCE / "implementation/record.json"),
            lifecycle_implementation=entry(_helper_directory / "record.json"),
            sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        ),
    )


def checked_implementation(root):
    root = Path(root)
    manifest = checked(root / "implementation/record.json")
    original = base.checked_implementation(MATH_SOURCE)
    require(
        manifest["schema"] == "v37_committed_production_implementation.v1"
        and manifest["committed_files"] == list(FILES)
        and list(manifest["sha256"]) == [*FILES, *original["sha256"]]
        and manifest["original_mathematical_implementation"]
        == entry(MATH_SOURCE / "implementation/record.json")
        and manifest["lifecycle_implementation"] == entry(_helper_directory / "record.json"),
        "production source manifest changed",
    )
    for name, expected in manifest["sha256"].items():
        require(
            sha(root / "implementation" / name) == expected, "frozen source bytes changed: " + name
        )
        if name in original["sha256"]:
            require(expected == original["sha256"][name], "original mathematical code was modified")
    return manifest


def production_modules(root):
    checked_implementation(root)
    directory = Path(root) / "implementation"
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    training = frozen_training_module()
    rt = training.load_runtime()
    require(
        not rt.torch.cuda.is_initialized(), "controller context registration must remain CPU-only"
    )
    context = _module(directory / "finqa_v37_task_cache.py", __name__ + "_contexts")
    original_cache = _module(directory / "finqa_v35_task_cache.py", __name__ + "_original_cache")
    return training, rt, context, original_cache


def protocol_body(root, implementation, initial, *, at):
    root = Path(root)
    engineering = checked_engineering_evidence()
    return dict(
        schema="v37_original_B_controlled_production_protocol.v1",
        at=at,
        output_root=str(root),
        implementation_id=implementation["id"],
        source_commit=implementation["source_commit"],
        authority=(
            "2026-10-10: 参照审计修订并开展后续实验; "
            "original B controlled recovery and original remaining matrix"
        ),
        audit=entry(root / "audit/record.json"),
        original_B_resume_authorized=True,
        original_queue_restart_authorized=False,
        original_failures_reclassified=False,
        source_scientific_protocol=entry(SOURCE_ROOT / "protocol/record.json"),
        source_pause=entry(PAUSE / "checkpoint_audit/record.json"),
        verified_fixed_point_result=entry(VERIFIED_SOURCE / "result/record.json"),
        initial_state_snapshot=entry(root / "initial_state/record.json"),
        initial_progress=dict(
            completed_optimizer_updates=5812,
            remaining_optimizer_updates=5810,
            completed_outer_updates=9,
            remaining_outer_updates=15,
            reused_sealed_feedback_episodes=2100,
            first_sampling_feedback_episodes=8400,
            remaining_endpoint_answers=8029,
            total_endpoint_answers=10323,
        ),
        original_matrix=[dict(seed=seed, arm=arm) for seed in SEEDS for arm in ARMS],
        first_gate=dict(seed=137, arm="C-only", step=1192, next_actual_sft_step=1193),
        completed_Static137_Static251_not_retrained_or_regenerated=True,
        all_nine_seals_before_any_test_scoring=True,
        new_reference_point_rechecks=0,
        API_calls=0,
        api_model="deepseek-flash",
        API_model_fallback=False,
        source_evaluation_module=file_ref(SOURCE_ROOT / "implementation/finqa_v25_evaluation.py"),
        evaluation_root=str(EVALUATION_ROOT),
        training_root=str(TRAINING_ROOT),
        allowed_gpu_indices=list(ALLOWED_GPUS),
        max_gpu_workers=4,
        CPU_initialization_and_draining_count_as_workers=True,
        one_worker_per_physical_gpu=True,
        dynamic_logical_shards_on_whitelisted_idle_GPUs=True,
        gpu_uuids={str(i): engineering["gpu_uuids"][str(i)] for i in ALLOWED_GPUS},
        cpu_affinity={str(i): engineering["cpu_affinity"][str(i)] for i in ALLOWED_GPUS},
        minimum_start_free_mib=MINIMUM_FREE_MIB,
        allocated_memory_limit_bytes=MAXIMUM_ALLOCATED_BYTES,
        free_memory_reserve_bytes=MINIMUM_DEVICE_FREE_BYTES,
        host_ram=HOST_RAM,
        outer_compute_budget_seconds=OUTER_COMPUTE_SECONDS,
        resource_wait_budget_seconds=RESOURCE_WAIT_SECONDS,
        stage_limits_seconds=STAGE_LIMITS,
        resource_wait_scope=(
            "global cumulative ready-work idle gaps with zero owned GPU leases; "
            "normal queueing behind owned running/draining workers "
            "is reported separately, not charged"
        ),
        prior_reference_four_hour_deadline_inherited=False,
        no_new_speedup_gate=True,
        stop_grace_seconds=TERM_GRACE_SECONDS,
        safe_boundary_pause_preserves_actual_artifacts=True,
        automatic_retry=False,
        implicit_fallback=False,
        delete_old_or_new_caches_allowed=False,
        disk_policy=(
            "remaining scientific checkpoint reservation plus next durable stage projection "
            "plus 32GiB reserve"
        ),
        response_checkpoint_cadence=16,
        numerical_or_same_point_failure_stops_all_owned_workers=True,
    )


def initialize(root=ROOT, *, source_commit):
    root = Path(root).resolve()
    require(root == ROOT and not root.exists(), "one new production registration, never overwrite")
    verify_old_controller_stopped()
    checked_engineering_evidence()
    implementation = freeze(root, source_commit)
    raw = AUDIT.read_bytes()
    path = root / "audit/source.txt"
    path.parent.mkdir(parents=True)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    publish(
        root / "audit/record.json",
        dict(
            schema="v37_supplied_audit.v1",
            at=now(),
            source=file_ref(path),
            original_attachment=file_ref(AUDIT),
            linked_zip_or_standalone_report_provided=False,
            external_audit_calculations_are_not_local_GPU_results=True,
        ),
    )
    training, rt, contexts, _cache = production_modules(root)
    snapshot = contexts.production_snapshot(training=training, rt=rt, training_root=TRAINING_ROOT)
    require(
        {(r["seed"], r["arm"]): r["step"] for r in snapshot["arms"]} == INITIAL_STEPS
        and snapshot["completed_physical_updates"] == 5812
        and snapshot["remaining_physical_updates"] == 5810
        and snapshot["completed_outers"] == 9
        and snapshot["remaining_outers"] == 15
        and len(snapshot["pending_sealed_outers"]) == 3,
        "original B progress differs from the authorized pause",
    )
    initial = publish(root / "initial_state/record.json", snapshot)
    protocol = publish(
        root / "protocol/record.json", protocol_body(root, implementation, initial, at=now())
    )
    base.status(
        root,
        dict(
            phase="REGISTERED_NOT_STARTED",
            protocol_id=protocol["id"],
            active_children=[],
            original_B_resume_authorized=True,
        ),
    )
    return protocol


def checked_protocol(root=ROOT):
    root = Path(root).resolve()
    require(root == ROOT, "fixed production resume root required")
    implementation = checked_implementation(root)
    protocol = checked(root / "protocol/record.json")
    initial = checked(root / "initial_state/record.json")
    require(
        {k: v for k, v in protocol.items() if k != "id"}
        == protocol_body(root, implementation, initial, at=protocol["at"]),
        "production contract changed",
    )
    audit = read_ref(protocol["audit"])
    require(sha(audit["source"]["path"]) == audit["source"]["sha256"], "audit attachment changed")
    verify_old_controller_stopped()
    return protocol


def eligible(row, protocol):
    return (
        row["index"] in ALLOWED_GPUS
        and row["uuid"] == protocol["gpu_uuids"][str(row["index"])]
        and not row["processes"]
        and row["free_mib"] >= MINIMUM_FREE_MIB
    )


def stage_rss_limit(stage):
    return (160 if stage in SHARDS else 192) * GIB


def check_resources(resources, stage):
    require(
        resources["all_gates_passed"] is True
        and resources["limits_unchanged"] is True
        and resources["maximum_allocated_bytes"] == MAXIMUM_ALLOCATED_BYTES
        and resources["minimum_device_free_bytes"] == MINIMUM_DEVICE_FREE_BYTES
        and resources["peak_resets_before_model_load"] == 1
        and resources["peak_resets_after_model_loading_begins"] == 0
        and resources["helper_peak_reset_calls"] == 0,
        "production lifetime memory contract failed",
    )
    observations = resources["observations"]
    require(
        observations
        and observations[-1]["label"] == "model_released.after_cleanup"
        and any(r["label"] == "after_model_load.after_cleanup" for r in observations),
        "real model load/release resource boundaries required",
    )
    for row in observations:
        require(
            row["passed"] is True
            and row["allocated_pass"] is True
            and row["free_pass"] is True
            and row["stop_requested"] is False
            and row["deadline_pass"] is True
            and row["limits"]
            == dict(
                allocated_memory_limit_bytes=MAXIMUM_ALLOCATED_BYTES,
                free_memory_reserve_bytes=MINIMUM_DEVICE_FREE_BYTES,
            ),
            "production resource observation failed",
        )
        require(
            all(
                type(row[k]) is int and row[k] >= 0
                for k in (
                    "allocated_bytes",
                    "reserved_bytes",
                    "peak_allocated_bytes",
                    "peak_reserved_bytes",
                    "free_bytes",
                    "total_bytes",
                )
            )
            and row["allocated_bytes"] <= row["peak_allocated_bytes"] <= MAXIMUM_ALLOCATED_BYTES
            and row["allocated_bytes"] <= row["reserved_bytes"] <= row["peak_reserved_bytes"]
            and row["peak_allocated_bytes"] <= row["peak_reserved_bytes"]
            and row["free_bytes"] <= row["total_bytes"]
            and (not row["boundary"] or row["free_bytes"] >= MINIMUM_DEVICE_FREE_BYTES),
            "recorded GPU resource limit failed",
        )
        host = row["host"]
        require(
            host["passed"] is True
            and host["rss_pass"] is True
            and host["available_pass"] is True
            and host["rss_limit_bytes"] == stage_rss_limit(stage)
            and host["available_reserve_bytes"] == HOST_RAM["reserve_bytes"]
            and 0 <= host["rss_bytes"] <= host["peak_rss_bytes"] <= stage_rss_limit(stage)
            and host["available_bytes"] >= HOST_RAM["reserve_bytes"],
            "recorded host resource limit failed",
        )
    require(
        resources["observed_peak_allocated_bytes"]
        == max(r["peak_allocated_bytes"] for r in observations)
        and resources["observed_minimum_boundary_free_bytes"]
        == min(r["free_bytes"] for r in observations if r["boundary"]),
        "GPU resource summary contradicts observations",
    )
    host = resources["host"]
    require(
        host["all_passed"] is True
        and host["rss_limit_bytes"] == stage_rss_limit(stage)
        and host["available_reserve_bytes"] == HOST_RAM["reserve_bytes"]
        and host["max_observed_peak_rss_bytes"]
        == max(r["host"]["peak_rss_bytes"] for r in observations)
        and host["min_observed_available_bytes"]
        == min(r["host"]["available_bytes"] for r in observations),
        "host resource summary contradicts actual observations",
    )


def check_result(protocol, stage, result, task_plan=None):
    require(
        stage in STAGES
        and result["stage"] == stage
        and result["protocol_id"] == protocol["id"]
        and result["status"] == "COMPLETE"
        and result["model_released"] is True,
        "foreign or incomplete production stage",
    )
    require(
        result["gpu_index"] in ALLOWED_GPUS
        and result["gpu_uuid"] == protocol["gpu_uuids"][str(result["gpu_index"])],
        "wrong production GPU",
    )
    require(
        type(result["API_calls"]) is int and result["API_calls"] == 0,
        "unregistered external API call",
    )
    for key in ("new_sampling_calls", "scoring_calls", "optimizer_steps", "replayed_responses"):
        require(type(result[key]) is int and result[key] >= 0, "invalid scientific counter")
    if stage not in {"virtual_point", "generate"}:
        require(
            result["new_sampling_calls"] == result["scoring_calls"] == 0,
            "unauthorized generation or scoring",
        )
    if stage != "train":
        require(result["optimizer_steps"] == 0, "optimizer step outside training stage")
    if stage != "replay_R3":
        require(result["replayed_responses"] == 0, "response replay outside registered R3 stage")
    if stage not in {"train", "generate"}:
        require(
            result["model_optimizer_rng_buffers_unchanged"] is True,
            "nontraining stage changed real Student state",
        )
    if stage in SHARDS:
        assignment = task_plan["assignments"][SHARDS.index(stage)]
        require(
            result["task_ids"] == assignment["task_ids"]
            and result["task_count"] == len(assignment["task_ids"])
            and type(result["class_task_calls"]) is int
            and result["class_task_calls"] >= 0
            and len(set(result["reused_task_ids"])) == len(result["reused_task_ids"])
            and set(result["reused_task_ids"]) <= set(assignment["task_ids"])
            and result["class_task_calls"] + len(result["reused_task_ids"]) == result["task_count"],
            "whole-task shard scope changed",
        )
    elif stage in {"virtual_point", "replay_R3", "distribution"}:
        require(result["denominator"] == 700, "original 700-trajectory denominator changed")
    elif stage == "generate":
        require(
            result["session_count"] == result["new_generation_episodes"] == 1147
            and result["new_sampling_calls"] == result["actual_response_calls"]
            and result["scoring_calls"] == 0
            and result["private_test_scoring"] is False,
            "endpoint dose or scoring barrier changed",
        )
        read_ref(result["whole_test_seal"])
    check_resources(result["resources"], stage)
    return result


class DurablePause(RuntimeError):
    """Finite time/disk/resource-wait boundary; no automatic continuation."""


class Lease:
    def __init__(self, pool, gpu, lock, runner, stage, projection):
        self.pool, self.gpu, self.lock = pool, gpu, lock
        self.runner, self.stage, self.projection = runner, stage, projection
        self.closed = False

    def close(self):
        if not self.closed:
            self.closed = True
            self.lock.close()
            require(self.pool.leases.get(self.gpu) is self, "GPU lease identity changed")
            del self.pool.leases[self.gpu]


class LeasePool:
    """The single namespace for ALL contexts, CPU initialization and draining."""

    def __init__(self, controller):
        self.controller = controller
        self.leases = {}

    def try_acquire(self, runner, stage):
        if len(self.leases) >= 4:
            return None
        needed = HOST_RAM["reserve_bytes"] + stage_rss_limit(stage)
        for lease in self.leases.values():
            item = lease.runner.active.get(lease.stage)
            memory = process_memory(item["launch"]["pid"]) if item is not None else None
            # Available RAM already excludes current RSS; reserve only the
            # unconsumed part of each still-held worker's registered envelope.
            used = memory["rss_bytes"] if memory is not None else 0
            needed += max(0, stage_rss_limit(lease.stage) - used)
        if host_memory()["available_bytes"] < needed:
            return None
        projection = runner.disk_projection(stage)
        self.controller.disk_gate(projection)
        rows = {row["index"]: row for row in inventory()}
        for gpu in ALLOWED_GPUS:
            if (
                gpu in self.leases
                or gpu not in rows
                or not eligible(rows[gpu], self.controller.protocol)
            ):
                continue
            path = TRAINING_ROOT / "locks" / ("gpu-" + digest(rows[gpu]["uuid"]) + ".lock")
            path.parent.mkdir(parents=True, exist_ok=True)
            lock = path.open("a")
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                lock.close()
                continue
            fresh = next((item for item in inventory() if item["index"] == gpu), None)
            if fresh is None or not eligible(fresh, self.controller.protocol):
                lock.close()
                continue
            lease = Lease(self, gpu, lock, runner, stage, projection)
            self.leases[gpu] = lease
            return fresh, lease
        return None


class RunnerAPI:
    """V36 lifetime gates, with the registered per-production-stage RSS cap."""

    def __init__(self, runner):
        self.runner = runner

    def __getattr__(self, name):
        if name == "HOST_RAM":
            cap = 160 * GIB if all(stage in SHARDS for stage in self.runner.active) else 192 * GIB
            return dict(HOST_RAM, shard_rss_limit_bytes=cap)
        return globals()[name]


class ContextRunner(LifecycleMixin):
    def __init__(self, controller, root, context, *, evaluation=False):
        self.controller, self.root, self.context = controller, Path(root), context
        self.protocol = controller.protocol
        self.task_plan = read_ref(context["task_plan"]) if context.get("due_outer") else {}
        self.evaluation = evaluation
        self.active, self.results, self.dispatched = {}, {}, set()
        self.lifecycle_api = RunnerAPI(self)
        self.stop = False
        self.created_monotonic = self.last_accounting = time.monotonic()
        self.compute_used = self.wait_used = 0.0
        self.phase_started = {}
        self.deadline = float("inf")
        self.finished = False
        self.reported_finished = False

    def update(self, phase, **extra):
        status(
            self.root,
            dict(
                phase=phase,
                protocol_id=self.protocol["id"],
                context_id=self.context["id"],
                active_children=[
                    {
                        k: item["launch"][k]
                        for k in ("stage", "pid", "birth", "gpu_index", "gpu_uuid")
                    }
                    for item in self.active.values()
                ],
                completed_stages=list(self.results),
                compute_seconds=self.compute_used,
                unowned_wall_queue_seconds=self.wait_used,
                global_external_resource_wait_seconds=self.controller.resource_wait_used,
                original_B_resume_authorized=True,
                **extra,
            ),
        )

    def time_gate(self):
        if self.stop or self.controller.stop:
            raise DurablePause("explicit safe stop requested")
        if self.controller.resource_wait_used >= RESOURCE_WAIT_SECONDS:
            raise DurablePause("24-hour global external-resource idle budget exhausted")
        if self.context.get("due_outer") and self.compute_used >= OUTER_COMPUTE_SECONDS:
            raise DurablePause(
                "24-hour actual outer compute window exhausted; committed artifacts retained"
            )
        for item in self.active.values():
            if time.monotonic() >= item["stage_deadline_monotonic"]:
                raise DurablePause("registered stage compute deadline reached")

    def account(self):
        current = time.monotonic()
        elapsed = max(0, current - self.last_accounting)
        if self.active:
            self.compute_used += elapsed
        elif not self.finished:
            self.wait_used += elapsed
        self.last_accounting = current

    def pending(self):
        if self.finished or self.controller.has_draining():
            return []
        if self.evaluation:
            return [] if "generate" in self.dispatched else ["generate"]
        if not self.context["due_outer"]:
            return [] if "train" in self.dispatched else ["train"]
        if not set(SHARDS) <= set(self.results):
            return [stage for stage in SHARDS if stage not in self.dispatched]
        for stage in ("virtual_point", "replay_R3", "distribution", "train"):
            if stage not in self.results:
                return [] if stage in self.dispatched else [stage]
        return []

    def _lifecycle_enter_draining(self, stage, item, trusted):
        self._lifecycle_setup()
        if self.controller.draining_episode is not None:
            self._lifecycle_episode = self.controller.draining_episode
        else:
            self._lifecycle_episode_count = self.controller.draining_episode_count
        super()._lifecycle_enter_draining(stage, item, trusted)
        if self.controller.draining_episode is None:
            self.controller.draining_episode = self._lifecycle_episode
            self.controller.draining_episode_count = self._lifecycle_episode_count

    def _lifecycle_close_episode(self):
        local_drainers = any(
            item.get("lifecycle_state")
            in {"RESULT_COMMITTED_DRAINING", "EXITED_PENDING_VALIDATION"}
            for item in self.active.values()
        )
        if not local_drainers:
            self._lifecycle_episode = None
        if self.controller.draining_episode is not None and not self.controller.has_draining():
            episode = self.controller.draining_episode
            publish(
                self.controller.root
                / "draining_episodes"
                / f"episode{episode['episode']:04d}/end/record.json",
                dict(
                    schema="v37_global_draining_episode_complete.v1",
                    at=now(),
                    protocol_id=self.protocol["id"],
                    **episode,
                    all_context_drainers_actually_exited=True,
                ),
            )
            self.controller.draining_episode = None

    def stage_limit(self, stage):
        if stage in SHARDS:
            return "class_gradients", STAGE_LIMITS["class_gradients"]
        if stage == "virtual_point":
            key = (
                "virtual_existing"
                if self.context["feedback"]["mode"] == "sealed_existing"
                else "virtual_first_sampling"
            )
            return key, STAGE_LIMITS[key]
        return stage, STAGE_LIMITS[stage]

    def disk_projection(self, stage):
        if stage == "generate":
            return 1147 * 32 * 64 * 1024 + 256 * 1024**2
        specs = self.context.get("parameter_spec", [])
        parameters = sum(math.prod(item["shape"]) * 4 for item in specs)
        if stage in SHARDS:
            task_ids = set(self.task_plan["assignments"][SHARDS.index(stage)]["task_ids"])
            states = sum(
                len(task["state_ids"])
                for task in self.task_plan["tasks"]
                if task["task_id"] in task_ids
            )
            return math.ceil(parameters * states * 1.1) + 128 * 1024**2
        if stage == "replay_R3":
            responses = self.results["virtual_point"]["response_count"]
            return (math.ceil(responses / 16) + 2) * (2 * parameters + 4 * 1024**2)
        if stage == "virtual_point":
            return (
                4 * GIB
                if self.context["feedback"]["mode"] == "first_sampling"
                else 4 * parameters + 128 * 1024**2
            )
        if stage == "distribution":
            return 4 * parameters + 128 * 1024**2
        return 256 * 1024**2

    def lifecycle_result_validator(self, stage, result):
        require(
            result["context_id"] == self.context["id"],
            "stage belongs to another actual parameter context",
        )
        launch = self.active[stage]["launch"]
        require(
            (result["gpu_index"], result["gpu_uuid"]) == (launch["gpu_index"], launch["gpu_uuid"]),
            "stage did not run on its actual owned device",
        )
        if self.evaluation:
            require(
                (result["seed"], result["arm"]) == (self.context["seed"], self.context["arm"]),
                "wrong endpoint coordinate",
            )
        elif stage == "virtual_point":
            feedback = self.context["feedback"]
            require(
                result["feedback_mode"] == feedback["mode"] and result["response_count"] >= 0,
                "feedback execution scope changed",
            )
            if feedback["mode"] == "sealed_existing":
                require(
                    result["point_id"] == feedback["expected_point_id"]
                    and result["new_feedback_episodes"] == 0
                    and result["new_sampling_calls"] == result["scoring_calls"] == 0,
                    "sealed pending point changed or was resampled/rescored",
                )
            else:
                require(
                    result["new_feedback_episodes"] == 700,
                    "future outer must sample its original full cohort once",
                )
        elif stage == "replay_R3":
            require(
                result["current_point_only"] is True
                and result["response_count"] == self.results["virtual_point"]["response_count"]
                and result["restored_completed_responses"] + result["replayed_responses"]
                == result["response_count"],
                "R3 prefix/current-point completeness failed",
            )
            read_ref(result["final_checkpoint"])
        elif stage == "distribution":
            require(
                result["contribution_only"] is self.context["branch"]["contribution_only"]
                and result["b_N"] == self.context["branch"]["b_N"]
                and result["point_id"] == self.results["virtual_point"]["point_id"]
                and result["C_N_pi_saved"] is True
                and result["outer_commits"] == 0
                and result["reference_comparison_performed"] is False,
                "C-only/Full branch, current point or production distribution scope changed",
            )
        elif stage == "train":
            require(
                result["initial_step"] == self.context["step"]
                and result["committed_step"] > result["initial_step"]
                and result["actual_optimizer_steps"]
                == result["optimizer_steps"]
                == result["committed_step"] - result["initial_step"]
                and result["actual_optimizer_steps"] <= 298
                and result["outer_committed"] is self.context["due_outer"],
                "real training step/outer commit dose changed",
            )
            expected_stop = self.context.get("training_stop_step")
            if expected_stop is not None:
                require(
                    result["committed_step"] == expected_stop, "explicit first SFT gate was skipped"
                )
            validate_training_commit(self.context, result)

    def launch(self, stage, row, lease):
        self._lifecycle_launch_gate()
        require(
            stage in self.pending() and stage not in self.dispatched,
            "stage is not the registered next durable transition",
        )
        require(
            not (self.root / stage / "launch/record.json").exists(),
            "stage attempt already exists; no retry",
        )
        self.controller.disk_gate(0)
        phase, budget = self.stage_limit(stage)
        current = time.monotonic()
        start = self.phase_started.setdefault(phase, current)
        remaining = budget - (current - start)
        if self.context.get("due_outer"):
            remaining = min(remaining, OUTER_COMPUTE_SECONDS - self.compute_used)
        if remaining <= 0:
            raise DurablePause("stage or outer budget exhausted before dispatch")
        deadline_epoch = time.time() + remaining
        if self.evaluation:
            arguments = [
                str(self.controller.root / "implementation/finqa_v37_evaluation.py"),
                "generate",
                "--stage",
                "generate",
                "--root",
                str(self.controller.root),
                "--seed",
                str(self.context["seed"]),
                "--arm",
                ARM_KEYS[self.context["arm"]],
                "--gpu-index",
                str(row["index"]),
                "--deadline-epoch",
                str(deadline_epoch),
            ]
        else:
            arguments = [
                str(self.controller.root / "implementation/finqa_v37_worker.py"),
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
            str(PYTHON),
            "-u",
            *arguments,
        ]
        directory = self.root / stage
        directory.mkdir(parents=True, exist_ok=True)
        worker = arguments[0]
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
            schema="v37_owned_production_stage_launch.v1",
            at=now(),
            protocol_id=self.protocol["id"],
            context_id=self.context["id"],
            stage=stage,
            pid=process.pid,
            birth=birth(process.pid),
            worker=worker,
            command=command,
            gpu_index=row["index"],
            gpu_uuid=row["uuid"],
            deadline_epoch=deadline_epoch,
            source_checkpoint=self.context.get("checkpoint"),
            no_automatic_retry=True,
        )
        # Keep the lease even if writing the immutable launch record fails.
        self.active[stage] = dict(
            process=process,
            launch=launch,
            lock=lease,
            started_monotonic=started,
            stage_deadline_monotonic=current + remaining,
        )
        self.dispatched.add(stage)
        require(
            launch["birth"] is not None, "worker exited before its ownership could be established"
        )
        self.active[stage]["launch"] = publish(directory / "launch/record.json", launch)
        self.update("RUNNING")

    def record_exit(self, stage, *, stopped=False):
        item = self.active[stage]
        code = item["process"].poll()
        require(code is not None, "cannot release GPU/worker slot before actual exit")
        publish(
            self.root / stage / "exit/record.json",
            dict(
                schema="v37_actual_stage_exit.v1",
                at=now(),
                protocol_id=self.protocol["id"],
                context_id=self.context["id"],
                stage=stage,
                returncode=code,
                stop_requested=stopped,
                no_retry=True,
                elapsed_worker_wall_seconds=max(0, time.monotonic() - item["started_monotonic"]),
            ),
        )
        item["lock"].close()
        del self.active[stage]
        return code

    def tick(self):
        self.account()
        self.time_gate()
        self.collect_finished()
        if self.active:
            self.observe_host()
            self.collect_finished()
        terminal = "generate" if self.evaluation else "train"
        self.finished = terminal in self.results and not self.active


def checkpoint_reference(path):
    path = Path(path).resolve()
    record = json.loads((path / "record.json").read_bytes())
    require(
        sha(path / "state.pt") == record["state_sha256"],
        "actual committed training state bytes differ",
    )
    return dict(
        path=str(path),
        record=file_ref(path / "record.json"),
        state=file_ref(path / "state.pt"),
        actual_state_digest=record["actual_state_digest"],
        seed=record["seed"],
        arm=record["arm"],
        step=record["step"],
        phase=record["phase"],
    )


def validate_training_commit(context, result):
    reference = checkpoint_reference(result["next_checkpoint"])
    require(
        (reference["seed"], reference["arm"], reference["step"], reference["phase"])
        == (context["seed"], context["arm"], result["committed_step"], "step"),
        "next SFT checkpoint is not the actual committed coordinate",
    )
    directory = TRAINING_ROOT / f"seed{context['seed']}/arms/{ARM_KEYS[context['arm']]}/training"
    require(
        Path(reference["path"]) == directory / f"step{reference['step']:04d}_step",
        "training commit escaped original arm",
    )
    if context["due_outer"]:
        outer = checkpoint_reference(result["outer_checkpoint"])
        require(
            (outer["seed"], outer["arm"], outer["step"], outer["phase"])
            == (context["seed"], context["arm"], context["step"], "outer")
            and Path(outer["path"]) == directory / f"step{context['step']:04d}_outer"
            and result["outer_done"] == [*context["outer_done"], context["step"]]
            and result["first_sft_after_outer"]
            == str(directory / f"step{context['step'] + 1:04d}_step"),
            "exactly one current outer and its next genuine SFT step must commit",
        )
    else:
        require(
            result["outer_done"] == context["outer_done"],
            "SFT segment introduced an unregistered outer",
        )
    return reference


class Controller:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.protocol = checked_protocol(self.root)
        self.initial = read_ref(self.protocol["initial_state_snapshot"])
        self.training, self.rt, self.context_module, self.original_cache = production_modules(
            self.root
        )
        self.runs = []
        self.latest = {(r["seed"], r["arm"]): r["checkpoint"]["path"] for r in self.initial["arms"]}
        self.completed_arms = {
            (r["seed"], r["arm"]) for r in self.initial["arms"] if r["step"] == 1490
        }
        self.active_coordinate = {}
        self.completed_evaluations = set()
        self.pool = LeasePool(self)
        self.stop = False
        self.pilot_accepted = False
        self.accepted_new_updates = self.accepted_new_outers = 0
        self.draining_episode = None
        self.draining_episode_count = 0
        self.resource_wait_used = 0.0
        self._resource_waiting = False
        self._resource_accounting_at = time.monotonic()
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
        for seed, arm in self.completed_arms:
            seal = (
                EVALUATION_ROOT / f"models/seed{seed}/{ARM_KEYS[arm]}/whole_test_seal/record.json"
            )
            require(
                seal.exists(), "already-complete Static endpoint seal missing; do not regenerate"
            )
            checked(seal)
            self.completed_evaluations.add((seed, arm))

    def has_draining(self):
        return any(
            item.get("lifecycle_state")
            in {"RESULT_COMMITTED_DRAINING", "EXITED_PENDING_VALIDATION"}
            for runner in self.runs
            for item in runner.active.values()
        )

    def account_resource_wait(self):
        current = time.monotonic()
        if self._resource_waiting:
            self.resource_wait_used += max(0, current - self._resource_accounting_at)
        self._resource_accounting_at = current
        if self.resource_wait_used >= RESOURCE_WAIT_SECONDS:
            raise DurablePause("24-hour global external-resource idle budget exhausted")

    def update(self, phase, **extra):
        active = [
            dict(
                context_id=r.context["id"],
                **{
                    k: item["launch"][k] for k in ("stage", "pid", "birth", "gpu_index", "gpu_uuid")
                },
                lifecycle_state=item.get("lifecycle_state", "RUNNING"),
            )
            for r in self.runs
            for item in r.active.values()
        ]
        require(
            len(active) <= 4 and len({x["gpu_index"] for x in active}) == len(active),
            "global worker/device cap violated",
        )
        status(
            self.root,
            dict(
                phase=phase,
                protocol_id=self.protocol["id"],
                active_children=active,
                pilot_accepted=self.pilot_accepted,
                accepted_new_optimizer_updates=self.accepted_new_updates,
                global_external_resource_wait_seconds=self.resource_wait_used,
                accepted_new_outer_updates=self.accepted_new_outers,
                accepted_result_counters_not_a_substitute_for_actual_checkpoint_audit=True,
                completed_training_coordinates=[
                    dict(seed=s, arm=a) for s, a in sorted(self.completed_arms)
                ],
                completed_evaluation_coordinates=[
                    dict(seed=s, arm=a) for s, a in sorted(self.completed_evaluations)
                ],
                original_B_resume_authorized=True,
                **extra,
            ),
        )

    def disk_gate(self, new_projection):
        remaining_updates = max(0, 5810 - self.accepted_new_updates)
        remaining_outers = max(0, 15 - self.accepted_new_outers)
        checkpoint_reserve = (remaining_updates + remaining_outers) * math.ceil(
            self.checkpoint_size * 1.05
        )
        active_reserve = sum(lease.projection for lease in self.pool.leases.values())
        required = checkpoint_reserve + active_reserve + new_projection + 32 * GIB
        available = shutil.disk_usage(self.root).free
        if available < required:
            raise DurablePause(
                f"durable disk boundary: free={available}, "
                f"reserved_future_states+active+next+32GiB={required}; no deletion authorized"
            )

    def create_context(self, coordinate, *, pilot=False):
        seed, arm = coordinate
        checkpoint = Path(self.latest[coordinate])
        meta = json.loads((checkpoint / "record.json").read_bytes())
        step = meta["step"]
        due = arm != "Static" and step in (298, 596, 894, 1192) and meta["phase"] != "outer"
        directory = (
            self.root
            / f"contexts/seed{seed}/{ARM_KEYS[arm]}/step{step:04d}_{'outer' if due else 'train'}"
        )
        binding = dict(
            protocol=entry(self.root / "protocol/record.json"),
            implementation_id=checked_implementation(self.root)["id"],
        )
        if pilot:
            require(
                coordinate == FIRST and step == 1192 and due,
                "first production gate must be actual C137/1192",
            )
            binding["training_stop_step"] = 1193
        common = dict(
            training=self.training,
            rt=self.rt,
            sources=self.source_bindings,
            execution_binding=binding,
            training_root=TRAINING_ROOT,
        )
        if due:
            context = self.context_module.prepare_outer(
                directory, checkpoint, original_cache_module=self.original_cache, **common
            )
        else:
            context = self.context_module.prepare_training_context(directory, checkpoint, **common)
        runner = ContextRunner(self, directory, context)
        self.runs.append(runner)
        self.active_coordinate[coordinate] = runner
        return runner

    def create_evaluation(self, coordinate):
        seed, arm = coordinate
        directory = self.root / f"evaluations/seed{seed}_{ARM_KEYS[arm]}"
        context = dict(id=f"evaluation:{seed}:{ARM_KEYS[arm]}", seed=seed, arm=arm, due_outer=False)
        runner = ContextRunner(self, directory, context, evaluation=True)
        self.runs.append(runner)
        return runner

    def accept_finished(self, runner):
        if runner.reported_finished or not runner.finished:
            return
        runner.reported_finished = True
        coordinate = (runner.context["seed"], runner.context["arm"])
        if runner.evaluation:
            self.completed_evaluations.add(coordinate)
            return
        result = runner.results["train"]
        self.latest[coordinate] = result["next_checkpoint"]
        self.accepted_new_updates += result["actual_optimizer_steps"]
        self.accepted_new_outers += int(result["outer_committed"])
        del self.active_coordinate[coordinate]
        if not self.pilot_accepted:
            require(
                coordinate == FIRST
                and result["initial_step"] == 1192
                and result["committed_step"] == 1193
                and result["actual_optimizer_steps"] == 1
                and result["outer_committed"] is True,
                "production pilot did not commit its outer and next real SFT update",
            )
            publish(
                self.root / "pilot_acceptance/record.json",
                dict(
                    schema="v37_actual_first_outer_and_SFT_accepted.v1",
                    at=now(),
                    protocol_id=self.protocol["id"],
                    context=entry(runner.root / "context/record.json"),
                    train_result=entry(runner.root / "train/result/record.json"),
                    next_checkpoint=checkpoint_reference(result["next_checkpoint"]),
                    outer_checkpoint=checkpoint_reference(result["outer_checkpoint"]),
                    remaining_matrix_dispatch_authorized=True,
                    reference_step298_repeated=False,
                ),
            )
            self.pilot_accepted = True
        if result["endpoint_complete"]:
            require(result["committed_step"] == 1490, "endpoint incomplete")
            self.completed_arms.add(coordinate)
        publish(
            runner.root / "completion/record.json",
            dict(
                schema="v37_durable_context_complete.v1",
                at=now(),
                protocol_id=self.protocol["id"],
                context_id=runner.context["id"],
                result=entry(runner.root / "train/result/record.json"),
            ),
        )

    def enqueue_remaining(self):
        if not self.pilot_accepted:
            return
        for seed in SEEDS:
            for arm in ARMS:
                coordinate = (seed, arm)
                if (
                    coordinate not in self.completed_arms
                    and coordinate not in self.active_coordinate
                ):
                    self.create_context(coordinate)
                if (
                    coordinate in self.completed_arms
                    and coordinate not in self.completed_evaluations
                    and not any(
                        r.evaluation and (r.context["seed"], r.context["arm"]) == coordinate
                        for r in self.runs
                    )
                ):
                    self.create_evaluation(coordinate)

    def stop_all(self):
        """Signal the whole lease pool first; one shared bounded wait thereafter."""
        start = time.monotonic()
        deadlines = [
            r._lifecycle_episode["deadline_monotonic"]
            for r in self.runs
            if getattr(r, "_lifecycle_episode", None) is not None
        ]
        stop_deadline = min([start + TERM_GRACE_SECONDS, *deadlines])
        errors = []
        for runner in self.runs:
            runner._lifecycle_setup()
            runner._lifecycle_stopping = True
            for item in runner.active.values():
                if (
                    item["process"].poll() is None
                    and item["lifecycle_state"] != "RESULT_COMMITTED_DRAINING"
                ):
                    try:
                        signal_owned(item["launch"], signal.SIGTERM)
                    except BaseException as error:
                        errors.append(str(error))
        self.update("SAFE_BOUNDARY_STOP_REQUESTED", shared_stop_deadline_monotonic=stop_deadline)
        killed = False
        while any(r.active for r in self.runs):
            for runner in self.runs:
                for stage in tuple(runner.active):
                    item = runner.active[stage]
                    if item["process"].poll() is not None:
                        runner.record_exit(stage, stopped=True)
            if not any(r.active for r in self.runs):
                break
            if time.monotonic() >= stop_deadline and not killed:
                for runner in self.runs:
                    for item in runner.active.values():
                        try:
                            signal_owned(item["launch"], signal.SIGKILL)
                        except BaseException as error:
                            errors.append(str(error))
                killed = True
            require(
                not killed or time.monotonic() < stop_deadline + 60,
                "owned worker did not exit; manual inspection required",
            )
            time.sleep(1 if killed else min(POLL_SECONDS, max(0, stop_deadline - time.monotonic())))
        require(not errors, "owned process stop guard errors: " + str(errors))

    def save_actual_progress(self):
        require(
            not any(r.active for r in self.runs), "audit actual state only after owned workers exit"
        )
        value = self.context_module.production_snapshot(
            training=self.training, rt=self.rt, training_root=TRAINING_ROOT
        )
        return publish(self.root / "actual_final_progress/record.json", value)

    def run(self):
        require(
            Path(__file__).resolve() == self.root / "implementation" / FILES[0],
            "run only the frozen production controller",
        )
        path = self.root / "queue/controller.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            publish(
                self.root / "queue/run_intent/record.json",
                dict(
                    schema="v37_single_production_controller.v1",
                    at=now(),
                    protocol_id=self.protocol["id"],
                    pid=os.getpid(),
                    birth=birth(os.getpid()),
                    automatic_restart=False,
                ),
            )
            handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
            for sig in handlers:
                signal.signal(sig, lambda *_: setattr(self, "stop", True))
            try:
                self.create_context(FIRST, pilot=True)
                while len(self.completed_evaluations) < 9:
                    self.account_resource_wait()
                    if self.stop:
                        raise DurablePause("explicit safe stop requested")
                    for runner in self.runs:
                        if not runner.finished:
                            runner.tick()
                        self.accept_finished(runner)
                    self.enqueue_remaining()
                    for runner in self.runs:
                        for stage in runner.pending():
                            runner._lifecycle_launch_gate()
                            acquired = self.pool.try_acquire(runner, stage)
                            if acquired is None:
                                continue
                            row, lease = acquired
                            try:
                                runner.launch(stage, row, lease)
                            finally:
                                if stage not in runner.active:
                                    lease.close()
                    self.update(
                        "RUNNING" if self.pool.leases else "WAITING_FOR_REGISTERED_RESOURCES"
                    )
                    self._resource_waiting = not self.pool.leases and any(
                        r.pending() for r in self.runs
                    )
                    time.sleep(POLL_SECONDS)
                require(
                    not self.pool.leases and not any(r.active for r in self.runs),
                    "score barrier requires every owned child exited",
                )
                actual = self.save_actual_progress()
                require(
                    actual["remaining_physical_updates"] == actual["remaining_outers"] == 0,
                    "actual original training matrix is incomplete",
                )
                evaluator = _module(
                    self.root / "implementation/finqa_v37_evaluation.py", __name__ + "_evaluation"
                )
                scored = evaluator.score(self.root)
                publish(
                    self.root / "result/record.json",
                    dict(
                        schema="v37_original_B_matrix_complete.v1",
                        at=now(),
                        protocol_id=self.protocol["id"],
                        status="COMPLETE",
                        pilot=entry(self.root / "pilot_acceptance/record.json"),
                        actual_progress=entry(self.root / "actual_final_progress/record.json"),
                        scoring=entry(self.root / "scoring/result/record.json"),
                        nine_endpoint_models_complete=True,
                        score_result_id=scored["id"],
                        historical_failures_reclassified=False,
                    ),
                )
                self.update("COMPLETE")
                return True
            except BaseException as error:
                stop_error = progress_error = None
                try:
                    self.stop_all()
                except BaseException as issue:
                    stop_error = str(issue)
                if (
                    not any(r.active for r in self.runs)
                    and not (self.root / "actual_final_progress/record.json").exists()
                ):
                    try:
                        self.save_actual_progress()
                    except BaseException as issue:
                        progress_error = str(issue)
                phase = (
                    "PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME"
                    if isinstance(error, DurablePause)
                    else "STOPPED_FAILURE_NO_RETRY"
                )
                body = dict(
                    error_type=type(error).__name__,
                    error=str(error),
                    stop_error=stop_error,
                    actual_progress_audit_error=progress_error,
                    automatic_retry=False,
                    completed_task_response_and_step_artifacts_preserved=True,
                )
                self.update(phase, **body)
                publish(
                    self.root / "failure/record.json",
                    dict(
                        schema="v37_production_stop.v1",
                        at=now(),
                        protocol_id=self.protocol["id"],
                        phase=phase,
                        **body,
                    ),
                )
                raise
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)


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
    print(json.dumps(dict(id=plan["id"], original_B_resume_authorized=True)))


if __name__ == "__main__":
    main()
