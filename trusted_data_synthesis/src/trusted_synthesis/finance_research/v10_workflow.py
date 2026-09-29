"""One fixed V10 cohort through generation, review, five arms and evaluations.

This supervisor never changes prompts, limits, samples or masks. It allocates a
GPU only for actual work with sufficient observed headroom, and preserves every
failed attempt. Partial feedback/evaluation is not silently sampled again.
"""

from __future__ import annotations

import argparse
import fcntl
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .calibration import gpu_inventory, identity, now, publish, status
from .storage import read_json
from .v6_collection import bound, persist, require
from .v10_generation import OUTPUT, checked, checked_plan

WORKTREE = Path(__file__).resolve().parents[4]


def available_gpus(inventory, *, allowed, occupied=(), minimum_free_mib=24576):
    """No claim of CUDA acceptance; workers recheck and take their original locks."""
    allowed, occupied = set(allowed), set(occupied)
    return [
        row["index"]
        for row in sorted(inventory, key=lambda r: (-r["free"], r["index"]))
        if row["index"] in allowed
        and row["index"] not in occupied
        and row["free"] >= minimum_free_mib
    ]


def generation_ready(output, plan):
    output = Path(output)
    if (
        not (output / "generation_seal/record.json").exists()
        or not (output / "native_support/record.json").exists()
    ):
        return False
    seal, native = (
        checked(output / "generation_seal/record.json"),
        checked(output / "native_support/record.json"),
    )
    require(
        seal["protocol_id"] == native["protocol_id"] == plan["id"]
        and native["generation_seal_id"] == seal["id"]
        and seal["denominator"] == len(seal["slots"]) == 8000,
        "no prefix or other batch can enter the workflow",
    )
    require(
        native["slot_denominator"] == len(native["rows"]) == 8000
        and [r["slot"] for r in seal["slots"]]
        == [r["slot"] for r in native["rows"]]
        == plan["slots"],
        "complete native and generation rosters must be the same original 8000",
    )
    return True


def marker_complete(path):
    path = Path(path)
    if not path.is_file():
        return False
    checked(path)
    return True


def child_command(module, arguments):
    return [
        sys.executable,
        "-u",
        "-m",
        "trusted_synthesis.finance_research." + module,
        *map(str, arguments),
    ]


class Supervisor:
    def __init__(self, output, *, max_gpu_workers=3):
        self.output = Path(output).resolve()
        self.root = self.output / "workflow"
        self.plan = checked_plan(self.output)
        self.stop = False
        self.children = {}
        self.max_gpu_workers = max_gpu_workers
        require(1 <= max_gpu_workers <= 3, "at most the three fixed seeds in parallel")

    def update(self, phase, **extra):
        status(
            self.root,
            dict(
                at=now(),
                protocol_id=self.plan["id"],
                batch_id=self.plan["batch_id"],
                phase=phase,
                max_gpu_workers=self.max_gpu_workers,
                no_GPU_placeholder=True,
                no_resampling=True,
                active_children=[
                    dict(
                        pid=item["pid"],
                        birth=item["birth"],
                        gpu=item["gpu"],
                        attempt=item["attempt"],
                        job_key=item["job"]["key"],
                        result=str(item["job"]["result"]),
                    )
                    for item in self.children.values()
                ],
                **extra,
            ),
        )

    def launch(self, job, *, gpu=None):
        directory = self.root / "jobs" / job["key"]
        attempt = directory / f"attempt{len(list(directory.glob('attempt*'))) + 1:03d}"
        attempt.mkdir(parents=True, exist_ok=False)
        command = child_command(
            job["module"],
            job["args"] + ([] if gpu is None else [job.get("gpu_flag", "--gpu"), gpu]),
        )
        with (attempt / "controller.log").open("xb") as log:
            process = subprocess.Popen(
                command,
                cwd=WORKTREE,
                env=os.environ.copy(),
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        birth = identity(process.pid)
        record = bound(
            dict(
                at=now(),
                key=job["key"],
                pid=process.pid,
                process_start_time_ticks=birth,
                command=command,
                gpu_index=gpu,
                worktree=str(WORKTREE),
                protocol_id=self.plan["id"],
                result=str(job["result"]),
                new_sampling_retry=False,
            )
        )
        publish(attempt / "launch", record)
        self.children[job["key"]] = dict(
            process=process, pid=process.pid, birth=birth, gpu=gpu, attempt=str(attempt), job=job
        )

    def reap(self):
        failures = []
        for key, item in list(self.children.items()):
            code = item["process"].poll()
            if code is None:
                continue
            complete = code == 0 and marker_complete(item["job"]["result"])
            record = bound(
                dict(
                    at=now(),
                    key=key,
                    pid=item["pid"],
                    exit_code=code,
                    completed=complete,
                    result=str(item["job"]["result"]),
                    retry_performed=False,
                    failed_attempt_retained=True,
                )
            )
            publish(Path(item["attempt"]) / "exit", record)
            del self.children[key]
            if not complete:
                failures.append(record)
        return failures

    def plain_job(self, job, phase):
        """Run the API stage in its own process with its existing drain handlers."""
        if marker_complete(job["result"]):
            return True
        self.launch(job)
        stop_forwarded = False
        while self.children:
            failures = self.reap()
            if failures:
                self.update("BLOCKED_API_STAGE_SAVED", failures=failures)
                return False
            if self.stop and not stop_forwarded:
                for item in self.children.values():
                    if identity(item["pid"]) == item["birth"]:
                        os.kill(item["pid"], signal.SIGTERM)
                stop_forwarded = True
            self.update(phase)
            if self.children:
                time.sleep(10)
        return not self.stop and marker_complete(job["result"])

    def gpu_queue(self, jobs, allowed):
        pending = [job for job in jobs if not marker_complete(job["result"])]
        failures = []
        while pending or self.children:
            failures.extend(self.reap())
            if failures:
                # Do not cancel other actual model work; no new jobs are admitted.
                if not self.children:
                    self.update(
                        "BLOCKED_GPU_JOB_SAVED",
                        failures=failures,
                        unstarted=[j["key"] for j in pending],
                    )
                    return False
            elif not self.stop:
                free = available_gpus(
                    gpu_inventory(),
                    allowed=allowed,
                    occupied=[j["gpu"] for j in self.children.values()],
                )
                while pending and free and len(self.children) < self.max_gpu_workers:
                    self.launch(pending.pop(0), gpu=free.pop(0))
            self.update(
                "WAITING_FOR_GPU_HEADROOM"
                if pending and not self.children and not failures
                else "GPU_WORK_RUNNING",
                queued=[j["key"] for j in pending],
                failures=failures,
            )
            if self.stop and not self.children:
                return False
            if pending or self.children:
                time.sleep(10)
        return not failures

    def await_generation(self):
        launch = checked(self.output / "generation_launch_01/record.json")
        stop_forwarded = False
        while identity(launch["pid"]) == launch["process_start_time_ticks"]:
            live = (
                read_json(self.output / "status.json")
                if (self.output / "status.json").exists()
                else {}
            )
            self.update(
                "GENERATION_RUNNING",
                generation_pid=launch["pid"],
                generation={
                    k: live.get(k)
                    for k in ("at", "phase", "completed", "denominator", "network_unknown_slots")
                },
            )
            if self.stop and not stop_forwarded:
                if identity(launch["pid"]) == launch["process_start_time_ticks"]:
                    os.kill(launch["pid"], signal.SIGTERM)
                stop_forwarded = True
            time.sleep(10)
        if self.stop:
            self.update("USER_STOPPED_GENERATION_SAVED")
            return False
        if not generation_ready(self.output, self.plan):
            self.update(
                "BLOCKED_GENERATION_SAVED",
                generation_status_path=str(self.output / "status.json"),
                no_prefix_training=True,
            )
            return False
        return True

    def run(self):
        if not self.await_generation():
            return None
        self.update("PROCESS_REVIEW_AND_ONCE_MAPPING")
        if not self.plain_job(
            dict(
                key="process-review-and-mapping",
                module="v10_production",
                args=["--output", self.output],
                result=self.output / "material/result/record.json",
            ),
            "PROCESS_REVIEW_AND_ONCE_MAPPING",
        ):
            return None
        material = checked(self.output / "material/result/record.json")
        binding = self.output / "material/binding/record.json"
        if not binding.is_file():
            self.update("BLOCKED_MATERIAL_SAVED", material_result=material, no_prefix_training=True)
            return None
        from .v10_training import register_exploratory_training

        allowed = [row["index"] for row in gpu_inventory()]
        handoff = register_exploratory_training(
            binding, self.output / "training", allowed_gpu_indices=allowed
        )
        persist(self.root / "training_handoff", bound(handoff))
        launcher = Path(handoff["launcher"])
        # Mechanism design freezes before any actual Student result is generated.
        from . import v9_mechanism_execution as mechanisms

        mechanism_root = self.output / "mechanisms"
        if not (mechanism_root / "registration/record.json").exists():
            mechanisms.register(launcher, mechanism_root)
        seeds = (11, 29, 47)
        jobs = [
            dict(
                key=f"train-seed{seed}",
                module="v9_training_launcher",
                args=[
                    "resume-seed" if (launcher / f"seed{seed}").exists() else "run-seed",
                    "--output",
                    launcher,
                    "--seed",
                    seed,
                ],
                result=launcher / f"seed{seed}/result/record.json",
            )
            for seed in seeds
        ]
        if not self.gpu_queue(jobs, allowed):
            return None
        from . import v9_final_evaluation as final

        evaluation = self.output / "final_evaluation"
        if not (evaluation / "registration/record.json").exists():
            final.register(launcher, evaluation)
        final_plan = final.checked_plan(evaluation)
        require(
            handoff["arms"] == list(final.ARMS)
            and final_plan["total_models"] == 15
            and final_plan["total_episodes"] == 15 * 883
            and len(final_plan["tasks"]) == 883
            and set(final_plan["jobs"])
            == {final.coordinate(seed, arm) for seed in seeds for arm in final.ARMS},
            "all fifteen fixed endpoints on the original dev883 required",
        )
        jobs = []
        for seed in seeds:
            for arm in handoff["arms"]:
                job = final_plan["jobs"][final.coordinate(seed, arm)]
                root = final.model_root(evaluation, job)
                jobs.append(
                    dict(
                        key="final-" + final.coordinate(seed, arm),
                        module="v9_final_evaluation",
                        args=[
                            "resume-model" if (root / "attempts").exists() else "run-model",
                            "--output",
                            evaluation,
                            "--seed",
                            seed,
                            "--arm",
                            arm,
                        ],
                        result=root / "scores/record.json",
                    )
                )
        if not self.gpu_queue(jobs, allowed):
            return None
        final_report = final.aggregate(evaluation)
        jobs = [
            dict(
                key=f"mechanisms-seed{seed}",
                module="v9_mechanism_execution",
                gpu_flag="--gpu-index",
                args=["run-seed", "--output", mechanism_root, "--seed", seed],
                result=mechanism_root / f"seed{seed}/result/record.json",
            )
            for seed in seeds
        ]
        if not self.gpu_queue(jobs, allowed):
            return None
        jobs = []
        for seed in seeds:
            for mechanism in ("C_direction", "N_same_point"):
                result = checked(mechanism_root / f"seed{seed}" / mechanism / "result/record.json")
                conditions = (
                    result["directions"] if mechanism == "C_direction" else result["conditions"]
                )
                for condition in conditions:
                    jobs.append(
                        dict(
                            key=f"mechanism-eval-{seed}-{mechanism}-{condition}",
                            module="v9_mechanism_execution",
                            gpu_flag="--gpu-index",
                            args=[
                                "evaluate-point",
                                "--output",
                                mechanism_root,
                                "--seed",
                                seed,
                                "--mechanism",
                                mechanism,
                                "--condition",
                                condition,
                            ],
                            seed=seed,
                            mechanism=mechanism,
                            condition=condition,
                            result=mechanism_root
                            / f"seed{seed}/evaluation"
                            / mechanism
                            / condition
                            / "whole_seal/record.json",
                        )
                    )
        if not self.gpu_queue(jobs, allowed):
            return None
        for job in jobs:
            mechanisms.score_point(mechanism_root, job["seed"], job["mechanism"], job["condition"])
        mechanism_report = mechanisms.aggregate(mechanism_root)
        result = bound(
            dict(
                schema="v10_new_batch_mainline_result.v1",
                at=now(),
                protocol_id=self.plan["id"],
                material_binding_id=checked(binding)["id"],
                final_evaluation_id=final_report["id"],
                mechanism_report_id=mechanism_report["id"],
                Experiment4="reuse existing limited mathematics; no dynamic convergence claim",
                Experiment5="separate future registered batch, not automatically dispatched",
                old_stock_spliced=False,
            )
        )
        publish(self.root / "result", result)
        self.update("FIXED_FIVE_ARM_MAINLINE_COMPLETE", result_id=result["id"])
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--max-gpu-workers", type=int, default=3)
    args = parser.parse_args(argv)
    root = Path(args.output) / "workflow"
    root.mkdir(parents=True, exist_ok=True)
    with (root / "controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        supervisor = Supervisor(args.output, max_gpu_workers=args.max_gpu_workers)

        def stop_requested(signum, frame):
            supervisor.stop = True

        signal.signal(signal.SIGTERM, stop_requested)
        signal.signal(signal.SIGINT, stop_requested)
        try:
            supervisor.run()
        except Exception as exc:
            issue = bound(
                dict(
                    at=now(),
                    error_type=type(exc).__name__,
                    error=str(exc),
                    no_retry_or_new_cohort=True,
                )
            )
            publish(root / "blocked" / issue["id"], issue)
            supervisor.update("BLOCKED_SAVED", issue=issue)
            raise


if __name__ == "__main__":
    main()
