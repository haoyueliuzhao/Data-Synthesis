"""Fixed mapping adjudication parallel with genuine all-package common prefixes."""

from __future__ import annotations

import argparse
import fcntl
import os
import signal
import time
from pathlib import Path

from .calibration import gpu_inventory, identity, now, publish
from .v6_collection import bound, persist, require, sha
from .v10_workflow import Supervisor as ExistingSupervisor
from .v10_workflow import available_gpus, marker_complete
from .v13_material_registration import checked, entry

OUTPUT = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "finance_research_20260928/finqa_v6_01/v15_prefix_completion_01"
)
SOURCES = (
    "v15_workflow.py",
    "v15_material.py",
    "v15_prefix_material.py",
    "v15_prefix_training.py",
    "v15_continuation.py",
    "v10_workflow.py",
    "v10_training.py",
    "v8_training_driver.py",
    "v9_conditional_training.py",
    "v9_training_launcher.py",
    "v9_mechanism_execution.py",
    "v9_final_evaluation.py",
    "v6_distribution.py",
)


def source_bindings():
    return {name: sha(Path(__file__).parent / name) for name in SOURCES}


def register_workflow(output=OUTPUT, *, allowed_gpu_indices, max_gpu_workers=3):
    from .v15_continuation import register_intent
    from .v15_mapping_registration import checked_plan
    from .v15_prefix_training import checked_launch

    output = Path(output).resolve()
    plan = checked_plan(output)
    prefix_plan, _, _ = checked_launch(output / "prefix_training")
    require(
        1 <= max_gpu_workers <= 3
        and allowed_gpu_indices
        and list(allowed_gpu_indices) == prefix_plan["device_policy"]["allowed_gpu_indices"],
        "same explicit GPU scope, at most three real seed workers",
    )
    intent = register_intent(output)
    result = bound(
        dict(
            schema="v15_parallel_prefix_mapping_workflow.v1",
            at=now(),
            registration_id=plan["id"],
            mapping_plan=entry(output / "registration/record.json"),
            prefix_launcher=entry(output / "prefix_training/registration/record.json"),
            continuation_intent_id=intent["id"],
            source_bindings=source_bindings(),
            allowed_gpu_indices=list(allowed_gpu_indices),
            max_gpu_workers=max_gpu_workers,
            minimum_free_mib=24576,
            common_prefix_steps_per_seed=298,
            prefix_physical_updates=894,
            no_temporary_states=True,
            all744_tasks_all2468_packages=True,
            mapping_inputs_frozen_before_prefix=True,
            no_Student_data_in_mapping=True,
            prefix_does_not_wait_for_mapping_completion=True,
            full_branches_require_complete_mapping_and_actual_prefix=True,
            no_GPU_placeholder=True,
            no_automatic_mapping_retry=True,
            no_feedback_or_dev_before_full_binding=True,
            no_prefix_retraining=True,
        )
    )
    persist(output / "workflow/registration", result)
    return result


class Supervisor(ExistingSupervisor):
    def __init__(self, output):
        from .v15_mapping_registration import checked_plan

        self.output = Path(output).resolve()
        self.root = self.output / "workflow"
        self.plan = checked_plan(self.output)
        self.workflow = checked(self.root / "registration/record.json")
        require(
            self.workflow["registration_id"] == self.plan["id"]
            and self.workflow["source_bindings"] == source_bindings(),
            "frozen V15 parallel execution dependency contract required",
        )
        self.stop, self.children = False, {}
        self.max_gpu_workers = self.workflow["max_gpu_workers"]

    def parallel_prefix_and_mapping(self):
        prefix_root = self.output / "prefix_training"
        pending = [
            dict(
                key=f"prefix-seed{seed}",
                module="v15_prefix_training",
                gpu_flag="--gpu-index",
                args=[
                    "resume-seed" if (prefix_root / f"seed{seed}").exists() else "run-seed",
                    "--output",
                    prefix_root,
                    "--seed",
                    seed,
                ],
                result=prefix_root / f"seed{seed}/result/record.json",
            )
            for seed in (11, 29, 47)
        ]
        pending = [j for j in pending if not marker_complete(j["result"])]
        seal = self.output / "completion_seal/record.json"
        material = self.output / "material/result/record.json"
        api_job = dict(
            key="fixed54-adjudication",
            module="v15_mapping_controller",
            args=["--output", self.output],
            result=seal,
        )
        material_job = dict(
            key="whole-state-join",
            module="v15_workflow",
            args=["material", "--output", self.output],
            result=material,
        )
        if not marker_complete(seal):
            self.launch(api_job)
        failures, stop_forwarded, join_launched = [], False, False
        prefix_launch_blocked = False
        while (
            pending
            or self.children
            or (marker_complete(seal) and not marker_complete(material) and not join_launched)
        ):
            new_failures = self.reap()
            failures.extend(new_failures)
            if any(f["key"].startswith("prefix-") for f in new_failures):
                prefix_launch_blocked = True
            # A mapping stop never cancels the already authorized state-free prefix.
            if (
                not self.stop
                and marker_complete(seal)
                and not marker_complete(material)
                and not join_launched
            ):
                self.launch(material_job)
                join_launched = True
            if not self.stop and not prefix_launch_blocked:
                gpu_children = [c for c in self.children.values() if c["gpu"] is not None]
                free = available_gpus(
                    gpu_inventory(),
                    allowed=self.workflow["allowed_gpu_indices"],
                    occupied=[c["gpu"] for c in gpu_children],
                    minimum_free_mib=self.workflow["minimum_free_mib"],
                )
                while pending and free and len(gpu_children) < self.max_gpu_workers:
                    job = pending.pop(0)
                    self.launch(job, gpu=free.pop(0))
                    gpu_children.append(self.children[job["key"]])
            if self.stop and not stop_forwarded:
                for item in self.children.values():
                    if identity(item["pid"]) == item["birth"]:
                        os.kill(item["pid"], signal.SIGTERM)
                stop_forwarded = True
            self.update(
                "COMMON_PREFIX_AND_FIXED_MAPPING",
                queued_prefixes=[j["key"] for j in pending],
                mapping_complete=marker_complete(seal),
                failures=failures,
                no_prefix_loss_or_dev_used_for_mapping=True,
            )
            if not self.children and (self.stop or prefix_launch_blocked):
                break
            if pending or self.children:
                time.sleep(10)
        prefix_results = [prefix_root / f"seed{s}/result/record.json" for s in (11, 29, 47)]
        prefix_done = all(marker_complete(p) for p in prefix_results)
        if not prefix_done or not marker_complete(material) or failures or self.stop:
            self.update(
                "PREFIX_OR_MAPPING_SAVED",
                prefix_complete=prefix_done,
                failures=failures,
                queued_prefixes=[j["key"] for j in pending],
                no_branch_started=True,
                no_new_mapping_attempt=True,
            )
            return False
        return True

    def run(self):
        if not self.parallel_prefix_and_mapping():
            return None
        material = checked(self.output / "material/result/record.json")
        binding = self.output / "material/binding/record.json"
        if not binding.exists():
            self.update(
                "COMMON_PREFIX_COMPLETE_WAITING_FOR_MAPPING",
                material_result=material,
                committed_steps_per_seed=298,
                GPUs_released=True,
                no_branch_or_feedback_started=True,
                no_subset_training=True,
            )
            return None
        from .v15_continuation import register_and_migrate

        self.update("VERIFYING_COMPLETE_MAPPING_AND_PREFIX_MIGRATION")
        handoff = register_and_migrate(
            self.output, allowed_gpu_indices=self.workflow["allowed_gpu_indices"]
        )
        return self.run_remaining_mainline(handoff)

    def run_remaining_mainline(self, handoff):
        from . import v9_final_evaluation as final
        from . import v9_mechanism_execution as mechanisms

        launcher = Path(handoff["launcher"])
        allowed, seeds = self.workflow["allowed_gpu_indices"], (11, 29, 47)
        mechanism_root = self.output / "mechanisms"
        if not (mechanism_root / "registration/record.json").exists():
            mechanisms.register(launcher, mechanism_root)
        jobs = [
            dict(
                key=f"five-arm-seed{s}",
                module="v9_training_launcher",
                args=["resume-seed", "--output", launcher, "--seed", s],
                result=launcher / f"seed{s}/result/record.json",
            )
            for s in seeds
        ]
        if not self.gpu_queue(jobs, allowed):
            return None
        evaluation = self.output / "final_evaluation"
        if not (evaluation / "registration/record.json").exists():
            final.register(launcher, evaluation)
        plan = final.checked_plan(evaluation)
        require(
            plan["total_models"] == 15
            and plan["total_episodes"] == 13245
            and len(plan["tasks"]) == 883
            and handoff["arms"] == list(final.ARMS),
            "unchanged complete fifteen-model dev evaluation",
        )
        jobs = []
        for seed in seeds:
            for arm in handoff["arms"]:
                coord = final.coordinate(seed, arm)
                root = final.model_root(evaluation, plan["jobs"][coord])
                jobs.append(
                    dict(
                        key="final-" + coord,
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
                key=f"mechanism-seed{s}",
                module="v9_mechanism_execution",
                gpu_flag="--gpu-index",
                args=["run-seed", "--output", mechanism_root, "--seed", s],
                result=mechanism_root / f"seed{s}/result/record.json",
            )
            for s in seeds
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
        report = mechanisms.aggregate(mechanism_root)
        value = bound(
            dict(
                schema="v15_complete_mainline_result.v1",
                at=now(),
                registration_id=self.plan["id"],
                prefix_retrained=False,
                final_evaluation_id=final_report["id"],
                mechanism_report_id=report["id"],
                test1147_opened=False,
                Experiment5_started=False,
                dynamic_student_convergence_proved=False,
            )
        )
        persist(self.root / "result", value)
        self.update("FIXED_FIVE_ARM_MAINLINE_COMPLETE", result_id=value["id"])
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["register", "run", "material"])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--gpus", default="0,1,2,3,4,5,6,7")
    args = parser.parse_args()
    if args.action == "register":
        result = register_workflow(
            args.output, allowed_gpu_indices=[int(i) for i in args.gpus.split(",")]
        )
    elif args.action == "material":
        from .v15_material import produce

        result = produce(args.output)
    else:
        root = args.output / "workflow"
        root.mkdir(parents=True, exist_ok=True)
        with (root / "controller.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            supervisor = Supervisor(args.output)

            def stop_requested(signum, frame):
                supervisor.stop = True

            signal.signal(signal.SIGTERM, stop_requested)
            signal.signal(signal.SIGINT, stop_requested)
            try:
                result = supervisor.run()
            except Exception as exc:
                issue = bound(
                    dict(
                        at=now(),
                        error_type=type(exc).__name__,
                        error=str(exc),
                        no_implicit_sampling_or_prefix_retraining=True,
                    )
                )
                publish(root / "blocked" / issue["id"], issue)
                supervisor.update("BLOCKED_SAVED", issue=issue)
                raise
    if result is not None:
        print(dict(id=result["id"]))


if __name__ == "__main__":
    main()
