"""Use user-authorized idle GPUs without changing frozen study or retry limits."""

import argparse
import copy
import json
import os
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import run_cross_market_authorized_retry_20260927 as retry

performance, previous, recovery, p = retry.performance, retry.previous, retry.recovery, retry.p
SCRIPT = "trusted_data_synthesis/scripts/run_cross_market_idle_gpu_20260927.py"
DIRECTORY = "idle_gpu_01"
PROTOCOL = "cross_market_idle_GPU_admission_protocol"
POLICY = dict(
    minimum_free_MiB=49152,
    maximum_idle_used_MiB=1024,
    maximum_idle_utilization_percent=5,
    continuous_idle_seconds=20,
    no_foreign_compute_process=True,
    recheck_before_worker_model_load=True,
    no_preemption_or_migration=True,
)


def require(condition, reason):
    p.require(condition, "cross_market_idle_GPU." + reason)


def read_gpu_snapshot():
    gpu_text = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=index,uuid,memory.used,memory.free,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    )
    app_text = subprocess.check_output(
        ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits"],
        text=True,
    )
    rows = []
    for line in gpu_text.splitlines():
        index, uuid, used, free, utilization = [value.strip() for value in line.split(",")]
        rows.append(
            dict(
                index=int(index),
                uuid=uuid,
                used_MiB=int(used),
                free_MiB=int(free),
                utilization_percent=int(utilization),
                processes=[],
            )
        )
    by_uuid = {row["uuid"]: row for row in rows}
    require(len(by_uuid) == len(rows) and bool(rows), "unique_visible_GPU_inventory")
    for line in app_text.splitlines():
        if not line.strip():
            continue
        uuid, pid = [value.strip() for value in line.split(",")]
        require(uuid in by_uuid, "compute_process_matches_visible_GPU")
        by_uuid[uuid]["processes"].append(int(pid))
    return rows


def is_idle(row, own_pid=None):
    return (
        row["free_MiB"] >= POLICY["minimum_free_MiB"]
        and row["used_MiB"] <= POLICY["maximum_idle_used_MiB"]
        and row["utilization_percent"] <= POLICY["maximum_idle_utilization_percent"]
        and not any(pid != own_pid for pid in row["processes"])
    )


class IdleAdmission:
    def __init__(self, allowed_uuids, observe=None, clock=None):
        self.allowed = frozenset(allowed_uuids)
        self.observe = read_gpu_snapshot if observe is None else observe
        self.clock = time.monotonic if clock is None else clock
        self.idle_since = {}

    def __call__(self, minimum):
        now, admitted, idle_now = self.clock(), [], set()
        for row in self.observe():
            uuid = row["uuid"]
            if uuid not in self.allowed or not is_idle(row) or row["free_MiB"] < minimum:
                continue
            idle_now.add(uuid)
            started = self.idle_since.setdefault(uuid, now)
            if now - started >= POLICY["continuous_idle_seconds"]:
                admitted.append(uuid)
        self.idle_since = {
            uuid: since for uuid, since in self.idle_since.items() if uuid in idle_now
        }
        return admitted


def register(root, raw=None):
    root, c = Path(root).resolve(), performance.context(raw)
    with c.locked(c.RAW / "control/coordinator.lock", blocking=False):
        if (c.RAW / DIRECTORY / "protocol.json").exists():
            return protocol(root, c.RAW)
        original, parent = c.read_protocol(root), retry.protocol(root, c.RAW)
        require(not (c.RAW / "generation_seal.json").exists(), "before_generation_completion")
        snapshot = read_gpu_snapshot()
        allowed = [row["uuid"] for row in snapshot]
        require(
            set(parent["gpu_allocation"]["allowed_gpu_uuids"]).issubset(allowed)
            and original["scheduling"]["max_GPU_workers"] == 8,
            "retain_existing_cards_and_original_eight_worker_ceiling",
        )
        inherited = []
        for path in sorted((c.RAW / "jobspecs").glob("*.json")):
            job = p.read_json(path)
            for row in previous.attempts(c, job):
                if row["alive"]:
                    inherited.append(dict(job_key=job["key"], **row))
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        source = (root / SCRIPT).read_bytes()
        require(
            source == subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root),
            "committed_operational_source_before_registration",
        )
        value = p.record(
            PROTOCOL,
            frozen=True,
            at=p.now(),
            authorization=dict(actor="user", request="可以使用空闲GPU"),
            evaluation_protocol=recovery.reference(c.RAW / "protocol.json"),
            evaluation_protocol_id=original["id"],
            previous_resource_and_retry_protocol=recovery.reference(
                c.RAW / retry.DIRECTORY / "protocol.json"
            ),
            previous_resource_and_retry_protocol_id=parent["id"],
            allowed_gpu_uuids=allowed,
            registered_GPU_snapshot=snapshot,
            admission_policy=POLICY,
            max_GPU_workers=8,
            previous_four_card_restriction_superseded_by_explicit_user_authorization=True,
            original_physical_budget=original["physical_budget"],
            registered_budget_snapshot=copy.deepcopy(c._budget_state()),
            inherited_active_workers=inherited,
            code_commit=head,
            sources={SCRIPT: p.sha(source)},
            old_protocol_files_and_worker_processes_unchanged=True,
            previous_target_only_two_additional_attempts_unchanged=True,
            scientific_conditions_and_private_scoring_barrier_unchanged=True,
            performance_policy_and_original_failure_history_preserved=True,
            new_training_updates=0,
            new_API_calls=0,
        )
        return c.write(c.RAW / DIRECTORY / "protocol.json", value)


def protocol(root, raw=None):
    root, c = Path(root).resolve(), performance.context(raw)
    value = p.checked(p.read_json(c.RAW / DIRECTORY / "protocol.json"), PROTOCOL)
    original, parent = c.read_protocol(root), retry.protocol(root, c.RAW)
    allowed = value["allowed_gpu_uuids"]
    require(
        value["frozen"] is True
        and recovery.checked_reference(value["evaluation_protocol"]) == original
        and value["evaluation_protocol_id"] == original["id"]
        and recovery.checked_reference(value["previous_resource_and_retry_protocol"]) == parent
        and value["previous_resource_and_retry_protocol_id"] == parent["id"]
        and allowed == [row["uuid"] for row in value["registered_GPU_snapshot"]]
        and len(allowed) == len(set(allowed))
        and set(parent["gpu_allocation"]["allowed_gpu_uuids"]).issubset(allowed)
        and value["admission_policy"] == POLICY
        and value["max_GPU_workers"] == original["scheduling"]["max_GPU_workers"] == 8
        and value["original_physical_budget"] == original["physical_budget"]
        and value["sources"] == {SCRIPT: p.sha(root / SCRIPT)},
        "same_frozen_idle_pool_and_original_budgets",
    )
    return value


def validate_worker(job, attempt, plan, original, retry_plan):
    require(
        all(os.environ.get(key) == value for key, value in recovery.ENVIRONMENT.items()),
        "real_worker_CUDA_environment",
    )
    if job["work_kind"] == "generate":
        require(
            os.environ.get("CUDA_VISIBLE_DEVICES") in plan["allowed_gpu_uuids"],
            "worker_GPU_in_registered_pool",
        )
    cap = original["scheduling"][
        "generation_attempts_per_shard"
        if job["work_kind"] == "generate"
        else "scoring_attempts_per_cohort"
    ]
    require(
        type(attempt) is int
        and 0 < attempt <= retry.attempt_cap(job, cap, retry_plan["target_job_id"]),
        "original_or_explicit_target_attempt_limit",
    )


def controller_namespace(plan, retry_plan, perf_plan, recovered):
    namespace = retry.controller_namespace(retry_plan, perf_plan, recovered)
    base_context = namespace["evaluation"].Context

    class IdleContext(base_context):
        def capacity_boundary(self, phase, required):
            if self._capacity_checks == 0:
                selected = os.environ.get("CUDA_VISIBLE_DEVICES")
                row = next((row for row in read_gpu_snapshot() if row["uuid"] == selected), None)
                if (
                    selected not in plan["allowed_gpu_uuids"]
                    or row is None
                    or not is_idle(row, own_pid=os.getpid())
                ):
                    raise previous.legacy.CapacityWait(
                        "generation: authorized idle GPU became occupied before model loading"
                    )
            return super().capacity_boundary(phase, required)

    namespace.update(
        SCRIPT=SCRIPT,
        available_gpus=IdleAdmission(plan["allowed_gpu_uuids"]),
        evaluation=SimpleNamespace(**{**vars(namespace["evaluation"]), "Context": IdleContext}),
    )
    return namespace


def execute(action, root, raw=None, job=None, attempt=None):
    root, c = Path(root).resolve(), performance.context(raw)
    if action == "register":
        return register(root, c.RAW)
    if action == "status":
        return previous.read(c.RAW / "control/status.json")
    plan, parent = protocol(root, c.RAW), retry.protocol(root, c.RAW)
    if action == "worker":
        item = p.checked(p.read_json(job), "cross_market_evaluation_work_unit")
        validate_worker(item, attempt, plan, c.read_protocol(root), parent)
    namespace = controller_namespace(
        plan, parent, performance.protocol(root, c.RAW), recovery.protocol(root, c.RAW)
    )
    if action != "worker":
        return namespace[action](root, c.RAW)
    result = namespace["worker"](root, c.RAW, job, attempt)
    for worker_context in namespace["performance_contexts"]:
        try:
            worker_context.record_worker_exit(result)
        except Exception as error:
            previous.emit("performance_telemetry_failed", error=repr(error))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "start", "coordinate", "worker", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--raw", type=Path, default=previous.RAW)
    parser.add_argument("--job", type=Path)
    parser.add_argument("--attempt", type=int)
    args = parser.parse_args()
    value = execute(args.action, args.root, args.raw, args.job, args.attempt)
    if args.action == "worker":
        return value
    if value is not None:
        print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
