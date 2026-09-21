"""Resource-only persistent supervision of the two already admitted Delayed-C runs."""

# ruff: noqa: E501 -- explicit audit fields
import argparse
import fcntl
import os
import signal
import subprocess
import sys
import time
import traceback
from collections import Counter
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import fixed_kernel_delayed_C_autorun_state_20260921 as a
import run_fixed_kernel_delayed_C_migration_20260921 as m
import torch

r, p, old = a.r, a.p, a.old
KEYS = ("A_delayed_c_47", "A_delayed_c_29")


def lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a")
    try:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        stream.close()
        raise
    return stream


def policy(root):
    record = p.checked(p.read_json(a.CONTROL / "registration.json"), "delayed_C_aggressive_autorun")
    for name, digest in record["sources"].items():
        p.require(p.sha(root / name) == digest, "autorun.frozen_control_source")
    return record


def environment(gpu=None):
    return dict(
        os.environ,
        CUDA_VISIBLE_DEVICES="" if gpu is None else gpu["uuid"],
        CUBLAS_WORKSPACE_CONFIG=":4096:8",
        OMP_NUM_THREADS="2",
        OPENBLAS_NUM_THREADS="2",
        MKL_NUM_THREADS="2",
        TOKENIZERS_PARALLELISM="false",
    )


def spawn(root, mode, log, *, args=(), gpu=None, lease=None):
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as stream:
        return subprocess.Popen(
            [sys.executable, str(root / a.SCRIPT), "--root", str(root), "--mode", mode, *args],
            cwd=root,
            env=environment(gpu),
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            pass_fds=() if lease is None else (lease.fileno(),),
        )


def start(root):
    a.CONTROL.mkdir(parents=True, exist_ok=True)
    with lock(a.CONTROL / "bootstrap.lock"):
        if (a.CONTROL / "watchdog_identity.json").exists():
            identity = p.read_json(a.CONTROL / "watchdog_identity.json")
            if m.same_process(identity):
                r.emit(dict(event="autorun_already_supervised", pid=identity["pid"]))
                return
        if (a.CONTROL / "registration.json").exists():
            policy(root)
        else:
            plan, _ = r.plans(root)
            out = root / r.OUTPUT
            previous = p.read_json(out / m.DIRECTORY / "handoff_complete.json")
            controller = m.identity(previous["controller_pid"])
            p.require(
                str(root / m.SCRIPT) in controller["command"]
                and controller["command"][controller["command"].index("--mode") + 1]
                == "coordinate",
                "autorun.exact_predecessor_controller",
            )
            active = {}
            for key in KEYS:
                launched, identity = m.latest_launch(out, key)
                p.require(
                    identity["uid"] == os.getuid()
                    and any(
                        str(root / script) in identity["command"] for script in (r.SCRIPT, m.SCRIPT)
                    ),
                    "autorun.only_registered_owned_worker",
                )
                active[key] = dict(
                    identity=identity,
                    attempt=launched["attempt"],
                    gpu=launched["gpu"],
                    phase=a.phase(root, key),
                    adopted=True,
                )
            registration = p.record(
                "delayed_C_aggressive_autorun",
                recovery_plan_id=plan["id"],
                authorization="2026-09-21 user: 调整后续其他任务，采取积极运行策略，做好保存与自动恢复运行",
                runs=list(KEYS),
                minimum_own_capacity_MiB=a.FLOORS,
                cold_start_extra_MiB=1024,
                OOM_capacity_increment_MiB=4096,
                maximum_capacity_MiB=77824,
                retry_backoff_seconds=[60, 120, 240, 480, 900],
                resource_startup_count_cap_removed=True,
                extra_incomplete_final_generate_call_upper_bound_per_run=a.EXTRA_CALL_CAP_PER_RUN,
                committed_final_sessions_per_run=180,
                effective_updates_per_run=400,
                feedback_resampling_or_rescoring=0,
                B_and_confirmation=0,
                no_model_or_gradient_or_decoding_or_score_formula_change=True,
                thresholds_are_aggressive_admission_not_proven_upper_bounds=True,
                scope="remaining admitted SFT, feedback replay, fixed final generation and CPU scoring only",
                prior_controller=controller,
                adopted_workers=active,
                sources={name: p.sha(root / name) for name in (a.SCRIPT, a.HELPER)},
                code_commit=subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=root, text=True
                ).strip(),
                at=p.now(),
            )
            m.signal_owned(controller, signal.SIGSTOP)
            committed = False
            try:
                for key, value in active.items():
                    latest, _ = m.latest_launch(out, key)
                    p.require(
                        latest["pid"] == value["identity"]["pid"]
                        and m.same_process(value["identity"]),
                        "autorun.adoption_race_guard",
                    )
                a.archive_metadata(root, {})
                a.write(a.CONTROL / "registration.json", registration, immutable=True)
                a.write(
                    a.CONTROL / "state.json",
                    {
                        key: dict(
                            active=value,
                            attempt=value["attempt"],
                            failures={name: 0 for name in a.FLOORS},
                            not_before=0,
                            stopped=None,
                        )
                        for key, value in active.items()
                    },
                )
                for name in (a.SCRIPT, a.HELPER):
                    a.atomic_bytes(
                        a.CONTROL / "code" / name, (root / name).read_bytes(), immutable=True
                    )
                m.terminate_stopped(controller)
                committed = True
            finally:
                if not committed and m.same_process(controller):
                    m.signal_owned(controller, signal.SIGCONT)
        process = spawn(root, "watch", a.CONTROL / "watchdog.log")
        a.write(a.CONTROL / "watchdog_identity.json", m.identity(process.pid))
        r.emit(
            dict(
                event="aggressive_autorun_started",
                watchdog_pid=process.pid,
                persistent_directory=str(a.CONTROL),
            )
        )


def safe_adopted_yield(root, key, active):
    """Upgrade legacy policy only at an explicit resource wait; never kill a busy worker."""
    if not active.get("adopted"):
        return False
    identity = active["identity"]
    logfile = root / r.OUTPUT / "logs" / f"{key}_attempt{active['attempt']}.log"
    event = m.last_event(logfile)
    allowed = {"waiting_for_GPU_headroom", "waiting_for_final_generation_headroom"}
    if not event or event.get("event") not in allowed:
        return False
    if (Path("/proc") / str(identity["pid"]) / "wchan").read_text().strip() != "hrtimer_nanosleep":
        return False
    m.signal_owned(identity, signal.SIGSTOP)
    stopped = False
    try:
        if m.last_event(logfile) != event:
            return False
        if event["event"] == "waiting_for_final_generation_headroom":
            p.require(a.cursor(key) == 400, "autorun.final_handoff_after_step400")
            if (root / r.OUTPUT / "runs" / key / "final/point.json").exists():
                return False  # An original sampler may have started in the narrow signal race.
        elif key.endswith("_29") and a.cursor(key) == 200:
            p.require(
                (r.RAW / key / "population.pt").exists(),
                "autorun.preserve_full_G_before_replay_handoff",
            )
        a.write(
            a.CONTROL / "handoffs" / f"{key}_{active['attempt']:04d}.json",
            dict(
                identity=identity,
                event=event,
                completed_training=a.cursor(key),
                reason="lower_phase_floor_or_reschedule_after_durable_wait",
                at=p.now(),
            ),
            immutable=True,
        )
        m.terminate_stopped(identity)
        stopped = True
        return True
    finally:
        if not stopped and m.same_process(identity):
            m.signal_owned(identity, signal.SIGCONT)


def failure_record(root, key, active):
    for path in (
        a.CONTROL / "results" / key / f"{active['attempt']:04d}.json",
        root / r.OUTPUT / "runs" / key / "attempts" / f"{active['attempt']:04d}_failure.json",
    ):
        if path.exists():
            return p.read_json(path)
    return None


def classify_exit(result, phase_now, previous_phase):
    if result is not None:
        if result.get("returncode") in (0, 43):
            return "progress", result.get("phase", previous_phase)
        if result.get("resource_retry_allowed"):
            return "oom", result.get("phase", previous_phase)
        error = result.get("error", "")
        if (
            error.startswith("OutOfMemoryError(")
            or "decoder_fault_not_zero_reward:OutOfMemoryError:" in error
        ):
            return "oom", phase_now
        return "fatal", result.get("phase", previous_phase)
    # A disappeared process without an application failure is a preemption inference, not a numerical pass.
    return "lost", phase_now


def gpu_choice(root, minimum):
    raw = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=index,uuid,memory.free", "--format=csv,noheader,nounits"],
        text=True,
        timeout=12,
    )
    rows = [line.split(",") for line in raw.splitlines()]
    for index, uuid, free in sorted(rows, key=lambda value: -int(value[2])):
        if int(free) < minimum:
            continue
        gpu = dict(index=int(index), uuid=uuid.strip(), free_MiB=int(free))
        try:
            lease = lock(root / r.OUTPUT / "runtime/gpu_leases" / (gpu["uuid"] + ".lock"))
        except BlockingIOError:
            continue
        return gpu, lease
    return None, None


def publish(root, plan):
    original = p.read_json(root / r.d.OUTPUT / "runs/A_delayed_c_11/report.json")
    rows = [p.read_json(root / r.OUTPUT / "runs" / key / "report.json") for key in KEYS]
    p.require(
        all(
            row["status"] == "COMPLETE_RECOVERED_FIXED_FINAL"
            and row["plan_id"] == plan["id"]
            and row["effective_optimizer_updates"] == 400
            and row["final_greedy_sessions"] == row["denominator"] == 180
            for row in rows
        ),
        "autorun.complete_registered_runs_only",
    )
    parent = p.read_json(root / r.d.inputs.PARENT / "report.json")
    qualified = original["final_qualified"] + sum(row["final_qualified"] for row in rows)
    successes, uncertain = Counter(), []
    for path in (a.CONTROL / "update_attempts").rglob("*.json"):
        value = p.read_json(path)
        if value["returned_successfully"]:
            successes[(value["run"], value["step"])] += 1
        else:
            uncertain.append(str(path))
    known_repeated = sum(max(0, count - 1) for count in successes.values())
    overhead = sum(row.get("interrupted_attempt_generate_call_upper_bound", 0) for row in rows)
    p.require(
        sum(row["new_generate_calls"] for row in rows) <= 11520 and overhead <= 11520,
        "autorun.final_compute_budget",
    )
    a.write(a.CONTROL / "interrupted_update_intents.json", uncertain)
    report = p.record(
        "delayed_C_recovered_matrix",
        status="COMPLETE_THREE_DELAYED_C_RUNS_AFTER_RECOVERY",
        recovery_plan_id=plan["id"],
        resource_amendment_id=policy(root)["id"],
        original_plan_id=plan["parent_plan_id"],
        Delayed_C_qualified=qualified,
        Static_qualified=parent["Static_qualified"],
        original_C_only_qualified=parent["C_only_qualified"],
        original_Full_qualified=parent["Full_qualified"],
        denominator_per_condition=540,
        primary_mean_difference=(qualified - parent["Static_qualified"]) / 540,
        primary_direction="POSITIVE_FIXED_DEV_DELAYED_DIRECTION"
        if qualified > parent["Static_qualified"]
        else "RETAIN_STATIC_NO_POSITIVE_DELAYED_DIRECTION",
        effective_optimizer_updates=1200,
        physical_completed_optimizer_updates_lower_bound=1303 + known_repeated,
        physical_exact_count_not_claimed=True,
        known_additional_repeated_completed_updates=known_repeated,
        interrupted_update_intents_with_unknown_completion_count=len(uncertain),
        interrupted_final_generate_call_upper_bound=overhead,
        new_feedback_sessions=0,
        original_resource_failure_preserved=True,
        development_is_not_independent_confirmation=True,
        B_or_confirmation_started=False,
        no_Full_or_Novelty_success_relabel=True,
        runs=[
            dict(run=row["run"], qualified=row["final_qualified"], report_id=row["id"])
            for row in [original, *rows]
        ],
        at=p.now(),
    )
    path = root / r.OUTPUT / "report.json"
    if path.exists():
        report = p.read_json(path)
    else:
        a.write(path, report, immutable=True)
    r.d.audit.publish(
        root,
        r.OUTPUT,
        "complete_delayed_C_aggressive_autorun_20260921",
        report,
        "资源调度修订后完成。有效剂量仍为每种子400步，最终每种子固定180条；中断会话的额外生成尝试独立记账。原103步重放保留，未把有效剂量当作物理计算总量；未新增随机反馈、未重评已封存反馈、未启动B或确认。",
    )
    a.archive_metadata(root, {})
    a.write(a.CONTROL / "complete.json", report, immutable=True)


def coordinate(root):
    old.OUTPUT = r.OUTPUT
    policy(root)
    plan, _ = r.plans(root)
    a.restore_metadata(root)
    children, known = {}, {}
    with lock(a.CONTROL / "controller.lock"):
        a.write(a.CONTROL / "controller_identity.json", m.identity(os.getpid()))
        state = p.read_json(a.CONTROL / "state.json")
        # Recover launches made just before a controller interruption, without duplicating their workers.
        for key, row in state.items():
            for path in sorted(
                [
                    *(a.CONTROL / "worker_identities" / key).glob("*.json"),
                    *(a.CONTROL / "self_registrations" / key).glob("*.json"),
                ]
            ):
                active = p.read_json(path)
                row["attempt"] = max(row["attempt"], active["attempt"])
                if m.same_process(active["identity"]):
                    p.require(
                        not row["active"]
                        or not m.same_process(row["active"]["identity"])
                        or all(
                            row["active"]["identity"][field] == active["identity"][field]
                            for field in ("pid", "uid", "start_ticks", "command")
                        ),
                        "autorun.one_live_worker_per_run",
                    )
                    row["active"] = active
        while True:
            a.archive_metadata(root, known)
            for key, row in state.items():
                active = row["active"]
                if active:
                    yielded = False
                    if m.same_process(active["identity"]):
                        try:
                            yielded = safe_adopted_yield(root, key, active)
                        except (FileNotFoundError, ProcessLookupError, ValueError):
                            # A process can exit between the identity probe and boundary inspection.
                            if m.same_process(active["identity"]):
                                raise
                        if not yielded:
                            if m.same_process(active["identity"]):
                                continue
                    child = children.pop(key, None)
                    if child is not None:
                        child.wait(timeout=2)
                    result = failure_record(root, key, active)
                    phase_now = a.phase(root, key)
                    outcome, failed_phase = (
                        ("progress", active["phase"])
                        if yielded or phase_now == "done"
                        else classify_exit(result, phase_now, active["phase"])
                    )
                    row["active"] = None
                    if outcome == "fatal":
                        row["stopped"] = dict(
                            reason="non_resource_failure_requires_review",
                            attempt=active["attempt"],
                            result=result,
                            at=p.now(),
                        )
                    elif outcome in ("oom", "lost"):
                        if failed_phase not in a.FLOORS:
                            failed_phase = active["phase"]
                        if outcome == "oom":
                            row["failures"][failed_phase] += 1
                        row["not_before"] = time.time() + a.cooldown(
                            max(1, row["failures"][failed_phase])
                        )
                        a.write(
                            a.CONTROL / "resource_exits" / f"{key}_{active['attempt']:04d}.json",
                            dict(
                                outcome=outcome,
                                active=active,
                                result=result,
                                completed_training=a.cursor(key),
                                next_eligible_unix=row["not_before"],
                                uncheckpointed_work_may_be_repeated=True,
                                at=p.now(),
                            ),
                            immutable=True,
                        )
                    else:
                        row["not_before"] = time.time() + (
                            60
                            if result
                            and result.get("returncode") == 43
                            and phase_now == active["phase"]
                            else 0
                        )
                    a.write(a.CONTROL / "state.json", state)
                if row["stopped"] or time.time() < row["not_before"]:
                    continue
                current = a.phase(root, key)
                if current == "done":
                    continue
                required = {
                    name: a.threshold(name, failures) for name, failures in row["failures"].items()
                }
                gpu, lease = None, None
                if current != "score":
                    host_required = (128 if current == "feedback" else 64) * 2**30
                    if old.host_memory()["MemAvailable_bytes"] < host_required:
                        continue
                    try:
                        gpu, lease = gpu_choice(root, required[current] + 1024)
                    except (subprocess.SubprocessError, OSError) as failure:
                        r.emit(dict(event="GPU_query_temporarily_unavailable", error=repr(failure)))
                        continue
                    if gpu is None:
                        continue
                row["attempt"] += 1
                number = row["attempt"]
                # Persist the assigned number before launch so it is never reused after controller loss.
                a.write(a.CONTROL / "state.json", state)
                try:
                    child = spawn(
                        root,
                        "worker",
                        a.CONTROL / "logs" / f"{key}_{number:04d}.log",
                        args=(
                            "--run",
                            key,
                            "--attempt",
                            str(number),
                            "--phase",
                            current,
                            "--sft-floor",
                            str(required["sft"]),
                            "--feedback-floor",
                            str(required["feedback"]),
                            "--final-floor",
                            str(required["final"]),
                        ),
                        gpu=gpu,
                        lease=lease,
                    )
                finally:
                    if lease is not None:
                        lease.close()
                row["active"] = dict(
                    identity=m.identity(child.pid),
                    attempt=number,
                    gpu=gpu,
                    phase=current,
                    adopted=False,
                )
                children[key] = child
                a.write(
                    a.CONTROL / "worker_identities" / key / f"{number:04d}.json",
                    row["active"],
                    immutable=True,
                )
                a.write(a.CONTROL / "state.json", state)
                r.emit(
                    dict(
                        event="autorun_worker_launched",
                        run=key,
                        phase=current,
                        attempt=number,
                        gpu=gpu,
                        pid=child.pid,
                    )
                )
            a.write(
                a.CONTROL / "heartbeat.json",
                dict(
                    pid=os.getpid(),
                    at=p.now(),
                    runs={
                        key: dict(phase=a.phase(root, key), completed_training=a.cursor(key), **row)
                        for key, row in state.items()
                    },
                ),
            )
            if all(a.phase(root, key) == "done" for key in KEYS):
                publish(root, plan)
                return 0
            if all(row["stopped"] or a.phase(root, key) == "done" for key, row in state.items()):
                a.write(
                    a.CONTROL / "needs_attention.json",
                    dict(state=state, healthy_workers_not_killed=True, at=p.now()),
                )
                return 1
            time.sleep(20)


def worker(root, args):
    policy(root)
    key, attempt = args.run, args.attempt
    p.require(key in KEYS, "autorun.registered_run_only")
    with lock(a.CONTROL / "run_locks" / (key + ".lock")):
        a.write(
            a.CONTROL / "self_registrations" / key / f"{attempt:04d}.json",
            dict(
                identity=m.identity(os.getpid()),
                attempt=attempt,
                gpu={"uuid": os.environ.get("CUDA_VISIBLE_DEVICES", "")},
                phase=args.phase,
                adopted=False,
            ),
            immutable=True,
        )
        result = dict(
            run=key, attempt=attempt, phase=args.phase, resource_retry_allowed=False, at=p.now()
        )
        try:
            if args.phase in ("sft", "feedback"):
                code = a.training_worker(
                    root, key, attempt, dict(sft=args.sft_floor, feedback=args.feedback_floor)
                )
            elif args.phase == "final":
                code = a.final_worker(root, key, attempt, args.final_floor)
            else:
                code = a.score_worker(root, key, attempt)
            result.update(
                returncode=code, phase=a.phase(root, key), resource_retry_allowed=code == 42
            )
            if code not in (0, 43):
                path = root / r.OUTPUT / "runs" / key / "attempts" / f"{attempt:04d}_failure.json"
                if path.exists():
                    result["original_failure"] = p.read_json(path)
        except a.BoundaryYield:
            result["returncode"] = 43
        except Exception as failure:
            retry = isinstance(failure, (torch.OutOfMemoryError, MemoryError, BrokenProcessPool))
            result.update(
                returncode=42 if retry else 1,
                resource_retry_allowed=retry,
                error=repr(failure),
                traceback=traceback.format_exc(),
            )
        a.write(a.CONTROL / "results" / key / f"{attempt:04d}.json", result, immutable=True)
        return result["returncode"]


def watch(root):
    with lock(a.CONTROL / "watchdog.lock"):
        a.write(a.CONTROL / "watchdog_identity.json", m.identity(os.getpid()))
        while True:
            policy(root)
            child = spawn(root, "coordinate", a.CONTROL / "coordinator.log")
            code = child.wait()
            a.write(
                a.CONTROL / "watchdog_status.json", dict(coordinator_returncode=code, at=p.now())
            )
            if code not in (-9, -15, 42):
                return code
            # Resource/preemption restart only. An integrity/protocol failure (1) stays stopped.
            time.sleep(30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("start", "watch", "coordinate", "worker"), required=True)
    parser.add_argument("--run")
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--phase", choices=("sft", "feedback", "final", "score"))
    for name in ("sft", "feedback", "final"):
        parser.add_argument("--" + name + "-floor", type=int, default=a.FLOORS[name])
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "start":
        start(root)
        return 0
    if args.mode == "watch":
        return watch(root)
    if args.mode == "worker":
        return worker(root, args)
    try:
        return coordinate(root)
    except (MemoryError, subprocess.TimeoutExpired) as failure:
        r.emit(dict(event="controller_resource_restart", error=repr(failure)))
        return 42
    except Exception as failure:
        a.write(
            a.CONTROL / "controller_failure.json",
            dict(error=repr(failure), traceback=traceback.format_exc(), at=p.now()),
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
