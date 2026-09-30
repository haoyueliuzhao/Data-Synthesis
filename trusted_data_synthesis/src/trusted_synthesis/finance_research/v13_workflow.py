"""Fixed measurements -> whole material -> original five arms; never subset training."""

from __future__ import annotations

import argparse
import fcntl
import signal
from pathlib import Path

from .calibration import gpu_inventory, now, publish
from .v6_collection import bound, persist, require, sha
from .v10_workflow import Supervisor as ExistingSupervisor
from .v13_material_registration import OUTPUT, checked, checked_plan

DOWNSTREAM_SOURCES = (
    "v13_workflow.py",
    "v13_material.py",
    "v13_student_encoding.py",
    "v13_training.py",
    "v10_training.py",
    "v10_workflow.py",
    "v10_student_encoding.py",
    "v8_training_driver.py",
    "v6_distribution.py",
    "v9_conditional_training.py",
    "v9_training_launcher.py",
    "v9_final_evaluation.py",
    "v9_mechanism_execution.py",
)


def downstream_binding():
    return {name: sha(Path(__file__).parent / name) for name in DOWNSTREAM_SOURCES}


def register_workflow(output=OUTPUT, *, allowed_gpu_indices, max_gpu_workers=3):
    output = Path(output).resolve()
    plan = checked_plan(output)
    require(
        1 <= max_gpu_workers <= 3
        and allowed_gpu_indices
        and len(set(allowed_gpu_indices)) == len(allowed_gpu_indices)
        and all(type(i) is int and i >= 0 for i in allowed_gpu_indices),
        "explicit GPU scope and at most three actual seed workers required",
    )
    record = bound(
        dict(
            schema="v13_fixed_material_workflow.v1",
            protocol_id=plan["protocol_identity"],
            registration_id=plan["id"],
            downstream_source_bindings=downstream_binding(),
            allowed_gpu_indices=list(allowed_gpu_indices),
            minimum_free_mib=24576,
            max_gpu_workers=max_gpu_workers,
            no_GPU_placeholder=True,
            prerequisites=(
                "all1316 terminal, all2468 field authorities/mapping/encoding, nontrivial support"
            ),
            skip_new_AB_and_generation=True,
            no_partial_training=True,
            no_automatic_retry=True,
            unchanged_arms=["Static", "Manual+", "Manual-", "C-only", "Full"],
            seeds=[11, 29, 47],
            feedback=700,
            feedback_tasks=350,
            dev_tasks=883,
            test1147_opened=False,
            rerun_Base=False,
            Experiment5=False,
            GPU_allocation_before_material_admission=False,
        )
    )
    persist(output / "workflow/registration", record)
    return record


class Supervisor(ExistingSupervisor):
    def __init__(self, output):
        self.output = Path(output).resolve()
        self.root = self.output / "workflow"
        self.plan = checked_plan(self.output)
        self.workflow = checked(self.root / "registration/record.json")
        require(
            self.workflow["registration_id"] == self.plan["id"]
            and self.workflow["downstream_source_bindings"] == downstream_binding(),
            "registered unchanged V13 downstream execution source required",
        )
        self.stop, self.children = False, {}
        self.max_gpu_workers = self.workflow["max_gpu_workers"]

    def run(self):
        if not self.plain_job(
            dict(
                key="fixed-material-measurements",
                module="v13_material_controller",
                args=["--output", self.output],
                result=self.output / "completion_seal/record.json",
            ),
            "PROJECTION_AND_MAPPING_RUNNING",
        ):
            return None
        if not self.plain_job(
            dict(
                key="whole-material",
                module="v13_workflow",
                args=["material", "--output", self.output],
                result=self.output / "material/result/record.json",
            ),
            "WHOLE_MATERIAL_ENCODING_OR_BLOCKERS",
        ):
            return None
        material = checked(self.output / "material/result/record.json")
        binding = self.output / "material/binding/record.json"
        if not binding.exists():
            self.update(
                "BLOCKED_WHOLE_MATERIAL_SAVED",
                material_result=material,
                no_failed_candidate_dropped=True,
                no_prefix_training=True,
            )
            return None
        from .v9_training_launcher import material_identity
        from .v13_material import load_training_pool

        pool = load_training_pool(binding)
        candidate = material_identity(pool, require_nontrivial=False)
        profile = candidate["capability_profile"]
        if not (profile["D_pi"] > 0 and profile["chi_flexible_tasks"] > 0):
            self.update(
                "BLOCKED_ALGEBRAIC_EQUIVALENCE_SAVED",
                actual_material_identity=candidate,
                no_manufactured_state_or_chi=True,
            )
            return None
        del pool
        from .v13_training import register_exploratory_training

        allowed = self.workflow["allowed_gpu_indices"]
        handoff = register_exploratory_training(
            binding, self.output / "training", allowed_gpu_indices=allowed
        )
        persist(self.root / "training_handoff", bound(handoff))
        launcher = Path(handoff["launcher"])
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
            "all fifteen unchanged endpoints and complete dev883 required",
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
                schema="v13_fixed_kernel_mainline_result.v1",
                at=now(),
                protocol_id=self.plan["protocol_identity"],
                registration_id=self.plan["id"],
                material_binding_id=checked(binding)["id"],
                final_evaluation_id=final_report["id"],
                mechanism_report_id=mechanism_report["id"],
                Experiment4="retain limited existing mathematics, no dynamic convergence claim",
                Experiment5="separate future batch, not automatically dispatched",
                old_stock_spliced=False,
            )
        )
        publish(self.root / "result", result)
        self.update("FIXED_FIVE_ARM_MAINLINE_COMPLETE", result_id=result["id"])
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["register", "run", "material"])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--gpus", default=None)
    args = parser.parse_args()
    if args.action == "register":
        allowed = (
            [int(i) for i in args.gpus.split(",")]
            if args.gpus is not None
            else [r["index"] for r in gpu_inventory()]
        )
        value = register_workflow(args.output, allowed_gpu_indices=allowed)
        print(dict(id=value["id"], GPU_allocated=False))
        return
    if args.action == "material":
        from .v13_material import produce

        value = produce(args.output)
        print(dict(id=value["id"], API_calls=0))
        return
    root = Path(args.output) / "workflow"
    root.mkdir(parents=True, exist_ok=True)
    with (root / "controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        supervisor = Supervisor(args.output)

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
