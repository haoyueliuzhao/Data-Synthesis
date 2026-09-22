"""One explicitly authorized GPU7 admission trial, retaining the existing supervisor."""

import argparse
import os
import signal
import subprocess
import time
from pathlib import Path

import run_fixed_kernel_delayed_C_autorun_20260921 as c

a, m, p = c.a, c.m, c.p
KEY = "A_delayed_c_47"
TARGET = 7
CAPACITY = 32768
COLD_START = CAPACITY + 1024
SCRIPT = "trusted_data_synthesis/scripts/run_fixed_kernel_delayed_C_gpu7_attempt_20260922.py"
DIRECTORY = "gpu7_seed47_attempt_20260922"


def admission(row, gpu, *, phase, step, completed):
    p.require(
        row["active"] is None and row["stopped"] is None,
        "gpu7_trial.only_inactive_nonfailed_run",
    )
    p.require(phase == "final" and step == 400, "gpu7_trial.only_step400_final")
    p.require(169 <= completed < 180, "gpu7_trial.preserve_already_sealed_cohort")
    p.require(gpu["index"] == TARGET, "gpu7_trial.only_requested_GPU7")
    p.require(gpu["free_MiB"] >= COLD_START, "gpu7_trial.cold_start_headroom")
    return row["attempt"] + 1


def registered_controller(root, path, role):
    expected = p.read_json(path)
    command = expected["command"]
    p.require(
        expected["uid"] == os.getuid()
        and str(root / a.SCRIPT) in command
        and "--mode" in command
        and command[command.index("--mode") + 1] == role
        and m.same_process(expected),
        "gpu7_trial.exact_registered_" + role,
    )
    return expected


def run(root):
    original_policy = c.policy(root)
    p.require(c.old.host_memory()["MemAvailable_bytes"] >= 64 * 2**30, "gpu7_trial.host_headroom")
    directory = a.CONTROL / DIRECTORY
    p.require(not (directory / "registration.json").exists(), "gpu7_trial.one_attempt_only")
    final = root / a.r.OUTPUT / "runs" / KEY / "final"
    point = p.checked(p.read_json(final / "point.json"), "anchored_model_parameter_point")
    evaluation = final.parent / "final_greedy"
    registered = p.checked(
        p.read_json(evaluation / "registration.json"), "anchored_trajectory_registration"
    )
    records = a.inventory(root, evaluation, registered["jobs"], point)
    p.require(
        registered["point_id"] == point["id"] and not registered["stochastic"],
        "gpu7_trial.same_fixed_greedy_point",
    )
    controller = registered_controller(root, a.CONTROL / "controller_identity.json", "coordinate")
    watchdog = registered_controller(root, a.CONTROL / "watchdog_identity.json", "watch")
    # Avoid handing off while the predecessor is in the middle of launching a worker.
    for _ in range(30):
        if (
            Path("/proc") / str(controller["pid"]) / "wchan"
        ).read_text().strip() == "hrtimer_nanosleep":
            break
        time.sleep(0.2)
    else:
        raise RuntimeError("gpu7_trial.controller_not_at_wait_boundary")
    stopped, changed, ended = [], False, False
    lease = guard = None
    try:
        m.signal_owned(watchdog, signal.SIGSTOP)
        stopped.append(watchdog)
        m.signal_owned(controller, signal.SIGSTOP)
        stopped.append(controller)
        with c.lock(a.CONTROL / "bootstrap.lock"):
            state = p.read_json(a.CONTROL / "state.json")
            guard = c.lock(a.CONTROL / "run_locks" / (KEY + ".lock"))
            gpu, lease = m.reserve_target(root, TARGET, minimum=COLD_START)
            number = admission(
                state[KEY],
                gpu,
                phase=a.phase(root, KEY),
                step=a.cursor(KEY),
                completed=len(records),
            )
            kept = state["A_delayed_c_29"]["active"]
            registration = p.record(
                "delayed_C_GPU7_admission_trial",
                authorization="2026-09-22 user: 尝试在GPU7上运行seed47",
                original_resource_policy_id=original_policy["id"],
                run=KEY,
                attempt=number,
                target_gpu=gpu,
                final_own_capacity_MiB=CAPACITY,
                cold_start_free_MiB=COLD_START,
                original_final_capacity_MiB=a.FLOORS["final"],
                one_low_capacity_trial_only=True,
                all_workload_peak_upper_bound_not_claimed=True,
                preserved_final_sessions=len(records),
                preserved_session_ids={str(index): row["id"] for index, row in records.items()},
                sole_final_point_id=point["id"],
                parameter_digest=point["parameter_digest"],
                retained_seed29_identity=kept["identity"] if kept else None,
                retained_seed29_not_signaled=True,
                model_decoding_and_scoring_unchanged=True,
                new_feedback_sessions=0,
                extra_incomplete_call_cap_unchanged=a.EXTRA_CALL_CAP_PER_RUN,
                original_controller=controller,
                original_watchdog=watchdog,
                source_sha256=p.sha(root / SCRIPT),
                code_commit=subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=root, text=True
                ).strip(),
                at=p.now(),
            )
            a.write(directory / "registration.json", registration, immutable=True)
            state[KEY]["attempt"] = number
            state[KEY]["not_before"] = 0
            a.write(a.CONTROL / "state.json", state)
            changed = True
            # Only the new worker takes this run lock. The old coordinator is still stopped.
            guard.close()
            guard = None
            process = c.spawn(
                root,
                "worker",
                a.CONTROL / "logs" / f"{KEY}_{number:04d}.log",
                args=(
                    "--run",
                    KEY,
                    "--attempt",
                    str(number),
                    "--phase",
                    "final",
                    "--final-floor",
                    str(CAPACITY),
                ),
                gpu=gpu,
                lease=lease,
            )
            active = dict(
                identity=m.identity(process.pid),
                attempt=number,
                gpu=gpu,
                phase="final",
                adopted=False,
                resource_override_id=registration["id"],
            )
            a.write(
                a.CONTROL / "worker_identities" / KEY / f"{number:04d}.json",
                active,
                immutable=True,
            )
            state[KEY]["active"] = active
            a.write(a.CONTROL / "state.json", state)
            # Restart only the controller: its new instance will adopt both live workers from disk.
            m.terminate_stopped(controller)
            ended = True
            a.write(
                directory / "launched.json",
                dict(
                    registration_id=registration["id"],
                    active=active,
                    predecessor_controller_exited=True,
                    retained_seed29_alive=bool(kept and m.same_process(kept["identity"])),
                    watchdog_will_restart_controller=True,
                    at=p.now(),
                ),
                immutable=True,
            )
            c.r.emit(
                dict(
                    event="GPU7_low_capacity_trial_launched",
                    run=KEY,
                    pid=process.pid,
                    attempt=number,
                    preserved_sessions=len(records),
                    gpu=TARGET,
                )
            )
    finally:
        if guard is not None:
            guard.close()
        if lease is not None:
            lease.close()
        if changed and not ended and m.same_process(controller):
            # Never resume a controller whose in-memory state predates the new launch record.
            m.terminate_stopped(controller)
        for expected in reversed(stopped):
            if m.same_process(expected):
                m.signal_owned(expected, signal.SIGCONT)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    run(args.root.resolve())
