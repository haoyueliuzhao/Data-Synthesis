"""Wait for the original three prefixes, then run the unchanged five-arm matrix.

This supervisor never launches/restarts a prefix or retries adjudication. Its GPU
queue starts only after full six-task binding and three genuine step298 commits.
"""

from __future__ import annotations

import argparse
import fcntl
import signal
import time
from pathlib import Path

from .calibration import now, publish
from .v6_collection import bound, persist, require, sha
from .v10_workflow import Supervisor as ExistingSupervisor
from .v10_workflow import marker_complete
from .v13_material_registration import checked, entry, read_ref
from .v16_registration import OUTPUT, checked_plan

SOURCES = (
    "v16_workflow.py",
    "v16_material.py",
    "v16_continuation.py",
    "v16_arm_training.py",
    "v10_workflow.py",
    "v10_training.py",
    "v15_prefix_material.py",
    "v15_prefix_training.py",
    "v8_training_driver.py",
    "v9_conditional_training.py",
    "v9_training_launcher.py",
    "v9_final_evaluation.py",
    "v9_mechanism_execution.py",
    "v6_distribution.py",
)


def source_bindings():
    return {name: sha(Path(__file__).parent / name) for name in SOURCES}


def register_workflow(
    output=OUTPUT,
    *,
    allowed_gpu_indices,
    max_gpu_workers=8,
    plan_loader=None,
    source_loader=None,
    schema="v16_six_task_continuation_workflow.v1",
):
    output = Path(output).resolve()
    plan = (plan_loader or checked_plan)(output)
    definition = read_ref(plan["definition"])
    original = checked(Path(definition["source_root"]) / "prefix_training/registration/record.json")
    allowed = list(allowed_gpu_indices)
    require(
        allowed
        and len(allowed) == len(set(allowed))
        and set(allowed) <= set(original["device_policy"]["allowed_gpu_indices"])
        and 1 <= max_gpu_workers <= len(allowed),
        "explicit existing GPU scope and finite independent arm workers required",
    )
    value = bound(
        dict(
            schema=schema,
            at=now(),
            registration_id=plan["id"],
            successor_registration=entry(output / "registration/record.json"),
            original_prefix_root=str(Path(definition["source_root"]) / "prefix_training"),
            prospective_intent=definition["prospective_intent"],
            source_bindings=(source_loader or source_bindings)(),
            allowed_gpu_indices=allowed,
            max_gpu_workers=max_gpu_workers,
            minimum_free_mib=24576,
            independent_arm_workers=True,
            common_prefix_steps_per_seed=298,
            branch_steps_per_arm=1192,
            physical_main_matrix_steps=18774,
            arms=["Static", "Manual+", "Manual-", "C-only", "Full"],
            seeds=[11, 29, 47],
            feedback_denominator=700,
            final_dev_sessions=13245,
            original_prefix_control_untouched=True,
            prefix_restart_authorized=False,
            API_calls=0,
            no_automatic_mapping_retry=True,
            no_Student_data_in_mapping=True,
            no_feedback_or_dev_before_full_binding=True,
            no_GPU_placeholder=True,
            first_outer_is_formal_experiment=True,
            same_point_savings_assumed=False,
        )
    )
    persist(output / "workflow/registration", value)
    return value


class Supervisor(ExistingSupervisor):
    plan_loader = staticmethod(checked_plan)
    source_loader = staticmethod(source_bindings)
    scope_label = "SIX_TASK"
    mainline_schema = "v16_complete_mainline_result.v1"

    def __init__(self, output):
        self.output = Path(output).resolve()
        self.root = self.output / "workflow"
        self.plan = self.plan_loader(self.output)
        self.workflow = checked(self.root / "registration/record.json")
        require(
            self.workflow["registration_id"] == self.plan["id"]
            and self.workflow["source_bindings"] == self.source_loader(),
            "frozen fixed-task successor workflow required",
        )
        self.stop, self.children = False, {}
        self.max_gpu_workers = self.workflow["max_gpu_workers"]

    def produce_material(self):
        from .v16_material import produce

        return produce(self.output)

    def migrate(self):
        from .v16_continuation import register_and_migrate

        return register_and_migrate(
            self.output, allowed_gpu_indices=self.workflow["allowed_gpu_indices"]
        )

    def wait_for_inputs(self):
        """Only completion JSONs are polled: no model, checkpoint tensors or GPU held."""
        prefix_root = Path(self.workflow["original_prefix_root"])
        seal = self.output / "completion_seal/record.json"
        material = self.output / "material/result/record.json"
        while not self.stop:
            if self.admission_blocked():
                return False
            controller_result = self.output / "controller_result/record.json"
            if marker_complete(controller_result) and not marker_complete(seal):
                result = checked(controller_result)
                require(
                    result["registration_id"] == self.plan["id"],
                    "controller failure belongs to another plan",
                )
                self.update(
                    self.scope_label + "_API_FAILURE_SAVED_PREFIX_UNTOUCHED",
                    controller_result=entry(controller_result),
                    original_prefix_control_untouched=True,
                    no_branch_or_feedback_started=True,
                    no_retry=True,
                )
                return False
            if marker_complete(seal) and not marker_complete(material):
                self.produce_material()
            material_done = marker_complete(material)
            if material_done and not checked(material)["training_admitted"]:
                self.update(
                    self.scope_label + "_MAPPING_UNRESOLVED_PREFIX_UNTOUCHED",
                    mapping_result=entry(material),
                    no_branch_or_feedback_started=True,
                    original_prefix_control_untouched=True,
                    no_retry=True,
                )
                return False
            completed = [
                seed
                for seed in (11, 29, 47)
                if marker_complete(prefix_root / f"seed{seed}/result/record.json")
            ]
            if material_done and len(completed) == 3:
                return True
            self.update(
                "WAITING_FOR_ORIGINAL_PREFIX_AND_" + self.scope_label + "_BINDING",
                completed_prefix_seeds=completed,
                complete_material_ready=material_done,
                original_prefix_control_untouched=True,
                no_GPU_held=True,
                no_branch_or_feedback_started=True,
            )
            time.sleep(30)
        self.update("SUCCESSOR_WAIT_STOPPED_ORIGINAL_PREFIX_UNTOUCHED")
        return False

    def admission_blocked(self):
        """Successor-specific explicit holds precede every material/prefix check."""
        return False

    def run(self):
        if not self.wait_for_inputs():
            return None
        self.update("VERIFYING_FIXED_MATERIAL_AND_ZERO_UPDATE_MIGRATION")
        handoff = self.migrate()
        return self.run_remaining_mainline(handoff)

    def arm_jobs(self, launcher):
        from .v9_training_launcher import ARM_DIRECTORIES

        jobs = []
        # Formal automatic-arm outer feedback starts first, without a duplicate pilot.
        for arm in ("C-only", "Full", "Static", "Manual+", "Manual-"):
            for seed in (11, 29, 47):
                root = launcher / f"seed{seed}/arms" / ARM_DIRECTORIES[arm]
                jobs.append(
                    dict(
                        key=f"arm-{seed}-{ARM_DIRECTORIES[arm]}",
                        module="v16_arm_training",
                        gpu_flag="--gpu-index",
                        args=[
                            "resume-arm" if root.exists() else "run-arm",
                            "--output",
                            launcher,
                            "--seed",
                            seed,
                            "--arm",
                            arm,
                        ],
                        result=root / "result/record.json",
                    )
                )
        return jobs

    def run_remaining_mainline(self, handoff):
        from . import v9_final_evaluation as final
        from . import v9_mechanism_execution as mechanisms
        from .v16_arm_training import aggregate_seed

        launcher = Path(handoff["launcher"])
        allowed, seeds = self.workflow["allowed_gpu_indices"], (11, 29, 47)
        mechanism_root = self.output / "mechanisms"
        if not (mechanism_root / "registration/record.json").exists():
            mechanisms.register(launcher, mechanism_root)
        self.update("ORIGINAL_FIVE_ARM_TAILS_FIRST_FORMAL_OUTER")
        if not self.gpu_queue(self.arm_jobs(launcher), allowed):
            return None
        for seed in seeds:
            aggregate_seed(launcher, seed)
        evaluation = self.output / "final_evaluation"
        if not (evaluation / "registration/record.json").exists():
            final.register(launcher, evaluation)
        plan = final.checked_plan(evaluation)
        require(
            plan["total_models"] == 15
            and plan["total_episodes"] == 13245
            and len(plan["tasks"]) == 883
            and handoff["arms"] == list(final.ARMS),
            "unchanged complete fifteen-model dev evaluation required",
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
                schema=self.mainline_schema,
                at=now(),
                registration_id=self.plan["id"],
                prefix_retrained=False,
                original_738_authorities_unchanged=True,
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


def main(
    *,
    default_output=OUTPUT,
    workflow_register=None,
    supervisor_class=None,
    material_producer=None,
    migrator=None,
):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run", "material", "migrate"))
    parser.add_argument("--output", type=Path, default=default_output)
    parser.add_argument("--gpus", default="0,1,2,3,4,5,6,7")
    parser.add_argument("--max-gpu-workers", type=int, default=8)
    args = parser.parse_args()
    gpus = [int(i) for i in args.gpus.split(",")]
    if args.action == "register":
        result = (workflow_register or register_workflow)(
            args.output, allowed_gpu_indices=gpus, max_gpu_workers=args.max_gpu_workers
        )
    elif args.action == "material":
        from .v16_material import produce

        result = (material_producer or produce)(args.output)
    elif args.action == "migrate":
        from .v16_continuation import register_and_migrate

        result = (migrator or register_and_migrate)(args.output, allowed_gpu_indices=gpus)
    else:
        root = args.output / "workflow"
        root.mkdir(parents=True, exist_ok=True)
        with (root / "controller.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            supervisor = (supervisor_class or Supervisor)(args.output)

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
                        original_prefix_control_untouched=True,
                        no_implicit_retry=True,
                    )
                )
                publish(root / "blocked" / issue["id"], issue)
                supervisor.update("BLOCKED_SAVED", issue=issue)
                raise
    if result is not None:
        print(dict(id=result["id"]))


if __name__ == "__main__":
    main()
