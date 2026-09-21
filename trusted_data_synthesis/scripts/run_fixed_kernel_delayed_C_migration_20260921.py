"""Controlled same-GPU SFT admission amendment; adopt the other worker unchanged."""

# ruff: noqa: E501 -- explicit control-plane provenance and safety gates

import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path

import run_fixed_kernel_delayed_C_recovery_20260921 as r
import torch

p, old = r.p, r.old
SCRIPT = "trusted_data_synthesis/scripts/run_fixed_kernel_delayed_C_migration_20260921.py"
DIRECTORY = "gpu5_sft_capacity_20260921"
MOVING, RETAINED = "A_delayed_c_47", "A_delayed_c_29"
SFT_CAPACITY_MIB = 40960
SFT_COLD_START_MIB = SFT_CAPACITY_MIB + 1024


def identity(pid):
    directory = Path("/proc") / str(pid)
    fields = (directory / "stat").read_text().rsplit(")", 1)[1].split()
    return dict(
        pid=pid,
        uid=directory.stat().st_uid,
        start_ticks=int(fields[19]),
        command=(directory / "cmdline").read_bytes().decode().rstrip("\0").split("\0"),
        state=fields[0],
    )


def same_process(expected):
    try:
        actual = identity(expected["pid"])
    except FileNotFoundError:
        return False
    return actual["state"] != "Z" and all(
        actual[key] == expected[key] for key in ("pid", "uid", "start_ticks", "command")
    )


def signal_owned(expected, signum):
    p.require(
        expected["pid"] > 1 and expected["uid"] == os.getuid() and same_process(expected),
        "migration.exact_owned_process_before_signal",
    )
    # This Python build lacks os.pidfd_open. Bind PID, UID, birth tick and argv immediately before signaling.
    os.kill(expected["pid"], signum)


def wait_gone(expected):
    for _ in range(100):
        if not same_process(expected):
            return
        time.sleep(0.1)
    raise RuntimeError("migration.registered_process_did_not_exit")


def terminate_stopped(expected):
    signal_owned(expected, signal.SIGTERM)
    if same_process(expected):
        signal_owned(expected, signal.SIGCONT)
    wait_gone(expected)


def last_event(path):
    for line in reversed(path.read_text().splitlines()):
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def latest_launch(out, key):
    paths = list((out / "launches").glob(key + "_*.json"))
    path = max(paths, key=lambda value: int(value.stem.rsplit("_", 1)[1]))
    row = p.read_json(path)
    actual = identity(row["pid"])
    p.require(
        "--run" in actual["command"]
        and actual["command"][actual["command"].index("--run") + 1] == key,
        "migration.run_identity",
    )
    return row, actual


def paused_boundary(event, wchan):
    return (
        event is not None
        and event.get("event") == "waiting_for_GPU_headroom"
        and wchan == "hrtimer_nanosleep"
    )


def target_gpu(index):
    raw = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=index,uuid,memory.free", "--format=csv,noheader,nounits"],
        text=True,
    )
    for line in raw.splitlines():
        number, uuid, free = [part.strip() for part in line.split(",")]
        if int(number) == index:
            return dict(index=index, uuid=uuid, free_MiB=int(free))
    raise ValueError("migration.target_GPU_not_found")


def reserve_target(root, index, *, minimum=61440):
    gpu = target_gpu(index)
    p.require(gpu["free_MiB"] >= minimum, "migration.target_has_required_free_capacity")
    path = root / r.OUTPUT / "runtime/gpu_leases" / (gpu["uuid"] + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    lease = path.open("a")
    try:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        lease.close()
        raise
    return gpu, lease


def projected_capacity(gpu, process):
    raw = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-compute-apps=gpu_uuid,pid,used_gpu_memory",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    )
    own = 0
    for line in raw.splitlines():
        uuid, pid, used = [part.strip() for part in line.split(",")]
        if uuid == gpu["uuid"] and int(pid) == process["pid"]:
            own += int(used)
    p.require(own > 0, "resource_amendment.source_GPU_allocation_identified")
    return gpu["free_MiB"] + own


def set_sft_policy(key):
    p.require(key == MOVING, "resource_amendment.only_seed47_SFT")
    r.s.MIN_OWN_CAPACITY_MIB = SFT_CAPACITY_MIB


def worker_with_policy(root, key, attempt):
    registration = p.checked(
        p.read_json(root / r.OUTPUT / DIRECTORY / "registration.json"),
        "delayed_C_resource_admission_amendment",
    )
    plan, _ = r.plans(root)
    p.require(
        registration["recovery_plan_id"] == plan["id"]
        and registration["source_sha256"] == p.sha(root / SCRIPT)
        and registration["SFT_capacity_MiB"] == SFT_CAPACITY_MIB,
        "resource_amendment.frozen_scope",
    )
    set_sft_policy(key)
    original_emit = r.emit

    def with_memory(value):
        if value.get("event") == "real_optimizer_update_checkpointed":
            value = dict(
                value,
                CUDA_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                CUDA_peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                peak_scope="since_worker_start_including_model_load",
                SFT_capacity_MiB=SFT_CAPACITY_MIB,
            )
        original_emit(value)

    r.emit = with_memory
    original_emit(
        dict(
            event="SFT_only_capacity_amendment",
            run=key,
            own_capacity_MiB=SFT_CAPACITY_MIB,
            feedback_capacity_unchanged_MiB=61440,
            final_capacity_unchanged_MiB=73728,
        )
    )
    return r.worker(root, key, attempt)


def launch(root, key, number, gpu, lease, migration_id):
    out = root / r.OUTPUT
    stream = (out / "logs" / f"{key}_attempt{number}.log").open("x")
    env = dict(
        os.environ,
        CUDA_VISIBLE_DEVICES=gpu["uuid"],
        CUBLAS_WORKSPACE_CONFIG=":4096:8",
        OMP_NUM_THREADS="2",
        OPENBLAS_NUM_THREADS="2",
        MKL_NUM_THREADS="2",
        TOKENIZERS_PARALLELISM="false",
    )
    process = subprocess.Popen(
        [
            sys.executable,
            str(root / (SCRIPT if key == MOVING else r.SCRIPT)),
            "--root",
            str(root),
            "--mode",
            "worker",
            "--run",
            key,
            "--attempt",
            str(number),
        ],
        cwd=root,
        env=env,
        stdout=stream,
        stderr=subprocess.STDOUT,
        pass_fds=(lease.fileno(),),
        start_new_session=True,
    )
    p.write_once(
        out / "launches" / f"{key}_{number}.json",
        p.record(
            "delayed_recovery_launch",
            run=key,
            attempt=number,
            gpu=gpu,
            pid=process.pid,
            migration_id=migration_id,
            at=p.now(),
        ),
    )
    r.emit(
        dict(
            event="migrated_or_resource_restarted_worker",
            run=key,
            attempt=number,
            gpu=gpu["index"],
            pid=process.pid,
        )
    )
    return dict(
        process=process, identity=identity(process.pid), lease=lease, stream=stream, attempt=number
    )


def handoff(root, target):
    old.OUTPUT = r.OUTPUT
    plan, _ = r.plans(root)
    out, directory = root / r.OUTPUT, root / r.OUTPUT / DIRECTORY
    controller = identity(p.read_json(out / "coordinator_started.json")["pid"])
    moving_launch, moving = latest_launch(out, MOVING)
    retained_launch, retained = latest_launch(out, RETAINED)
    for process in (controller, moving, retained):
        p.require(
            str(root / r.SCRIPT) in process["command"] and process["uid"] == os.getuid(),
            "migration.only_exact_registered_runner",
        )
    p.require(
        controller["command"][controller["command"].index("--mode") + 1] == "coordinate",
        "migration.original_controller_role",
    )
    logfile = out / "logs" / f"{MOVING}_attempt{moving_launch['attempt']}.log"
    p.require(
        paused_boundary(
            last_event(logfile), (Path("/proc") / str(moving["pid"]) / "wchan").read_text().strip()
        ),
        "migration.only_waiting_checkpoint_boundary",
    )
    p.require(
        moving_launch["attempt"] + 1 <= plan["budget"]["maximum_resource_failures_per_run"],
        "migration.within_registered_startup_cap",
    )
    p.require(
        target == moving_launch["gpu"]["index"] == 5, "resource_amendment.authorized_same_GPU5"
    )
    gpu, lease = target_gpu(target), None
    before_capacity = projected_capacity(gpu, moving)
    p.require(
        before_capacity >= SFT_COLD_START_MIB, "resource_amendment.projected_cold_start_capacity"
    )
    stopped = []
    committed = False
    try:
        signal_owned(controller, signal.SIGSTOP)
        stopped.append(controller)
        signal_owned(moving, signal.SIGSTOP)
        stopped.append(moving)
        p.require(same_process(retained), "migration.healthy_worker_remains_alive")
        p.require(
            last_event(logfile)["event"] == "waiting_for_GPU_headroom",
            "migration.no_uncheckpointed_update_started",
        )
        checkpoint_path = max((r.RAW / MOVING / "updates").glob("*.pt"))
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        cursor = checkpoint["completed_updates"]
        p.require(
            checkpoint["plan_id"] == plan["id"]
            and checkpoint["run_key"] == MOVING
            and checkpoint["rng"]["schedule_cursor"] == cursor,
            "migration.same_checkpoint_and_RNG",
        )
        r.s.check_saved_state(checkpoint["state"], checkpoint["snapshot"], cursor)
        report = p.read_json(out / "runs" / MOVING / "updates" / f"{cursor:04d}" / "report.json")
        p.require(
            report["id"] == checkpoint["update_report"]["id"], "migration.committed_update_pair"
        )
        p.require(
            projected_capacity(target_gpu(target), moving) >= SFT_COLD_START_MIB,
            "resource_amendment.projected_capacity_rechecked_before_stop",
        )
        registration = p.record(
            "delayed_C_resource_admission_amendment",
            recovery_plan_id=plan["id"],
            authorization="2026-09-21 user: 当前任务是否真的需要60GB显存？尝试恢复五号上的运行",
            moved_run=MOVING,
            same_GPU_restart=True,
            original_shared_capacity_MiB=61440,
            SFT_capacity_MiB=SFT_CAPACITY_MIB,
            cold_start_free_MiB=SFT_COLD_START_MIB,
            projected_free_after_old_worker_exit_MiB=before_capacity,
            feedback_capacity_unchanged_MiB=61440,
            final_capacity_unchanged_MiB=73728,
            all_workload_peak_upper_bound_not_claimed=True,
            real_SFT_peak_memory_logged=True,
            resume_after_step=cursor,
            checkpoint_sha256=p.sha(checkpoint_path),
            target_gpu=gpu,
            original_controller=controller,
            stopped_worker=moving,
            retained_worker=retained,
            migration_controller_pid=os.getpid(),
            worker_numerical_sources_unchanged=True,
            extra_completed_optimizer_updates=0,
            new_feedback_sessions=0,
            consumes_existing_startup_slot=moving_launch["attempt"] + 1,
            source_sha256=p.sha(root / SCRIPT),
            code_commit=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            at=p.now(),
        )
        p.write_once(directory / "registration.json", registration)
        # From this record onward the new controller owns supervision. Only these two recorded PIDs are stopped.
        terminate_stopped(controller)
        committed = True
        terminate_stopped(moving)
        # CUDA context destruction can trail process exit briefly; no other user's process is touched.
        for _ in range(30):
            if target_gpu(target)["free_MiB"] >= SFT_COLD_START_MIB:
                break
            time.sleep(1)
        gpu, lease = reserve_target(root, target, minimum=SFT_COLD_START_MIB)
        replacement = launch(
            root, MOVING, moving_launch["attempt"] + 1, gpu, lease, registration["id"]
        )
        retained_state = dict(
            process=None,
            identity=retained,
            lease=None,
            stream=None,
            attempt=retained_launch["attempt"],
        )
        p.write_once(
            directory / "handoff_complete.json",
            p.record(
                "delayed_C_control_handoff_complete",
                registration_id=registration["id"],
                controller_pid=os.getpid(),
                moved_worker_pid=replacement["identity"]["pid"],
                retained_worker_pid=retained["pid"],
                retained_worker_alive=same_process(retained),
                resume_after_step=cursor,
                old_GPU_lease_released=True,
                target_gpu=gpu["index"],
                at=p.now(),
            ),
        )
        r.emit(
            dict(
                event="migration_handoff_complete",
                moved_run=MOVING,
                resume_after_step=cursor,
                target_gpu=target,
                retained_pid=retained["pid"],
                replacement_pid=replacement["identity"]["pid"],
            )
        )
        return plan, registration, {MOVING: replacement, RETAINED: retained_state}
    except BaseException:
        if not committed:
            for process in reversed(stopped):
                if same_process(process):
                    signal_owned(process, signal.SIGCONT)
        if lease is not None:
            lease.close()
        raise


def supervise(root, plan, registration, active):
    out, directory = root / r.OUTPUT, root / r.OUTPUT / DIRECTORY
    attempts = {key: value["attempt"] for key, value in active.items()}
    pending, failed = [], {}
    while pending or active:
        for key, value in list(active.items()):
            process = value["process"]
            code = (
                process.poll()
                if process is not None
                else (None if same_process(value["identity"]) else -1)
            )
            if code is None:
                continue
            for resource in (value["lease"], value["stream"]):
                if resource is not None:
                    resource.close()
            del active[key]
            report_path = out / "runs" / key / "report.json"
            failure_path = out / "runs" / key / "attempts" / f"{value['attempt']:04d}_failure.json"
            if report_path.exists():
                report = p.read_json(report_path)
                p.require(
                    report["status"] == "COMPLETE_RECOVERED_FIXED_FINAL"
                    and report["plan_id"] == plan["id"],
                    "migration.only_complete_run_published",
                )
                r.d.audit.publish(
                    root,
                    r.OUTPUT,
                    key + "_recovered_final",
                    report,
                    "运行在控制面迁移后完成。训练/梯度实现和恢复预算保持冻结；迁移不是新的实验或种子筛选。",
                )
            elif (
                failure_path.exists()
                and p.read_json(failure_path)["resource_retry_allowed"]
                and attempts[key] < plan["budget"]["maximum_resource_failures_per_run"]
            ):
                pending.append(key)
            else:
                failed[key] = dict(returncode=code, attempt=value["attempt"])
                r.emit(dict(event="worker_failed_other_run_continues", run=key, returncode=code))
        if pending and old.host_memory()["MemAvailable_bytes"] >= 256 * 2**30:
            for key in list(pending):
                old.MIN_FREE_MIB = SFT_COLD_START_MIB if key == MOVING else 61440
                choices = old.claim_gpus(root, maximum=1)
                old.MIN_FREE_MIB = 61440
                if not choices:
                    continue
                gpu, lease = choices[0]
                pending.remove(key)
                attempts[key] += 1
                active[key] = launch(root, key, attempts[key], gpu, lease, registration["id"])
        if pending or active:
            time.sleep(20)
    if failed:
        p.write_once(
            directory / "coordinator_failure.json",
            p.record(
                "delayed_migration_incomplete",
                failed=failed,
                healthy_workers_not_killed=True,
                at=p.now(),
            ),
        )
    else:
        r.publish_final(root, plan)
        p.write_once(
            directory / "complete.json",
            p.record("delayed_migration_supervision_complete", at=p.now()),
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("start", "coordinate", "worker"), required=True)
    parser.add_argument("--target-gpu", type=int, default=5)
    parser.add_argument("--run")
    parser.add_argument("--attempt", type=int, default=2)
    args = parser.parse_args()
    root = args.root.resolve()
    directory = root / r.OUTPUT / DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    if args.mode == "worker":
        raise SystemExit(worker_with_policy(root, args.run, args.attempt))
    if args.mode == "start":
        with (directory / "coordinator.log").open("x") as stream:
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(root / SCRIPT),
                    "--root",
                    str(root),
                    "--mode",
                    "coordinate",
                    "--target-gpu",
                    str(args.target_gpu),
                ],
                cwd=root,
                stdout=stream,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        r.emit(dict(event="migration_controller_starting", pid=process.pid))
        return
    try:
        plan, registration, active = handoff(root, args.target_gpu)
        supervise(root, plan, registration, active)
    except BaseException as failure:
        p.write_once(
            directory / "handoff_or_supervision_failure.json",
            p.record(
                "delayed_migration_control_failure",
                error=repr(failure),
                traceback=traceback.format_exc(),
                healthy_workers_not_killed=True,
                at=p.now(),
            ),
        )
        raise


if __name__ == "__main__":
    main()
