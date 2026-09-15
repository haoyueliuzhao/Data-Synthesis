"""Continue actual in-flight evaluation with an explicit memory-only GPU amendment.

Existing generation workers and their output bytes are retained. The original
science, decoder, scoring, decision and optional training contracts do not change.
"""

import argparse
import os
import subprocess
from pathlib import Path

import fixed_kernel_evaluation_shared_gpu_scheduler_20260915 as scheduler

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import execution as x
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import parallel_study as s
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

SOURCES = (
    "trusted_data_synthesis/scripts/continue_fixed_kernel_evaluation_shared_gpu_20260915.py",
    "trusted_data_synthesis/scripts/fixed_kernel_evaluation_shared_gpu_scheduler_20260915.py",
)


def source_capture(root):
    p.require(Path(__file__).resolve() == root / SOURCES[0], "evaluation_shared.correct_entrypoint")
    p.require(
        Path(scheduler.__file__).resolve() == root / SOURCES[1],
        "evaluation_shared.correct_scheduler_helper",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    members = []
    for name in SOURCES:
        raw = (root / name).read_bytes()
        committed = subprocess.check_output(["git", "show", head + ":" + name], cwd=root)
        p.require(raw == committed, "evaluation_shared.committed_operator_before_start")
        members.append(dict(path=name, bytes=len(raw), sha256=p.sha(raw)))
    return dict(head_commit=head, members=members)


def complete_after_Adev(root, frozen, training_handoff, a_training, amendment):
    """Original post-Adev scientific chain; no replay of completed admission or training."""
    output = root / s.OUTPUT
    dev = x.score_jobs(root, frozen, x.jobs_for("A_dev"))
    decision = x.e.select_actual_direction(
        a_training, dev, binding=x.binding(frozen), dev_tasks=frozen["evaluation_registry"]["dev"]
    )
    p.write_once(output / "decision.json", decision)
    selected = decision["selected_arm"]
    common = dict(
        actual_complete=True,
        **x.binding(frozen),
        heterogeneous_execution=True,
        per_run_training_configuration_ids=frozen["per_run_training_configuration_ids"],
        imported_completed_parent_training_runs=8,
        parallel_tail_A_handoff_id=training_handoff["id"],
        decision_id=decision["id"],
        evaluation_resource_admission_amendment_id=amendment["id"],
    )
    if selected == "alpha0":
        report = p.record(
            "execution_report",
            status="COMPLETE_NO_POSITIVE_DIRECTION",
            **common,
            execution_lineage=x.parallel_lineage.execution_lineage(a_training),
            actual_training_runs=9,
            actual_evaluation_sessions=1620,
            B_training_runs=0,
            confirmation_sessions=0,
            independent_positive_effect_confirmed=False,
        )
    else:
        p.require(selected in ("plus", "minus"), "evaluation_shared.original_selected_direction")
        # The existing A-dev coordinator already admitted the original material
        # authority. Load it only if actual selection releases new B training.
        inputs = x.fast_materials.load_authority(
            Path(frozen["input_root"]),
            frozen["material_input_receipt"],
            frozen["input_files"],
            expected_kernel_id=frozen["kernel_id"],
        )
        b_jobs = x.jobs_for("B_train", selected)
        release = x.training.make_release(
            inputs["kernel"],
            study_freeze_id=frozen["study_freeze_id"],
            surface_manifest_id=x.e.SURFACE_MANIFEST_ID,
            allowed_runs=[{key: job[key] for key in ("pool", "arm", "seed")} for job in b_jobs],
            verified_inputs=inputs,
        )
        p.write_once(output / "B_release.json", release)
        # This request is about evaluation: B-training scheduling stays frozen.
        x.run_jobs(root, frozen, "B_train", selected=selected, release=release)
        all_training = x.training_reports(root, frozen, x.jobs_for("A_train") + b_jobs)
        scheduler.run_new_phase(root, frozen, "confirm", selected=selected, amendment=amendment)
        confirm = x.score_jobs(root, frozen, x.jobs_for("confirm", selected))
        result = x.e.confirm_actual(
            decision,
            all_training,
            confirm,
            binding=x.binding(frozen),
            confirm_tasks=frozen["evaluation_registry"]["confirm"],
        )
        p.write_once(output / "confirmation.json", result)
        report = p.record(
            "execution_report",
            status="COMPLETE_FIXED_CONFIRMATION",
            **common,
            execution_lineage=x.parallel_lineage.execution_lineage(all_training),
            confirmation_id=result["id"],
            actual_training_runs=15,
            actual_evaluation_sessions=10260,
            confirmation_sessions=8640,
            primary_pool="B",
            fixed_confirm_unique_tasks=720,
            independent_positive_effect_confirmed=result["status"]
            == "CONFIRMED_POSITIVE_AS_SCOPED",
        )
    x.verify_code(frozen["code_binding"])
    p.write_once(output / "report.json", report)
    x.e.seal_output(output, "fixed_kernel_value_execution", report)
    return report


def run(root):
    root = s.guard(root)
    output = root / s.OUTPUT
    phase = "evaluation_resource_handoff"
    try:
        forbidden = (
            "evaluation_resource_admission_amendment.json",
            "evaluation_resource_coordinator_started.json",
            "jobs/A_dev/report.json",
            "scores",
            "decision.json",
            "B_release.json",
            "confirmation.json",
            "report.json",
            "manifest.json",
            "execution_failure.json",
            "parallel_handoff_failure.json",
        )
        p.require(
            not any((output / name).exists() for name in forbidden),
            "evaluation_shared.no_phase_reexecution",
        )
        frozen = p.checked(
            p.read_json(output / "preparation/execution_freeze.json"), "execution_freeze"
        )
        started = p.checked(p.read_json(output / "execution_started.json"), "execution_started")
        handoff = p.checked(
            p.read_json(output / "evaluation_resource_handoff.json"), "evaluation_resource_handoff"
        )
        training_handoff = p.checked(
            p.read_json(output / "A_training_handoff.json"), "parallel_tail_A_handoff"
        )
        p.require(
            started["execution_freeze_id"]
            == training_handoff["execution_freeze_id"]
            == frozen["id"]
            and training_handoff["execution_started_id"] == started["id"],
            "evaluation_shared.original_execution_and_completed_training",
        )
        scheduler.validate_handoff(root, frozen, handoff)
        x.validate_freeze(frozen)
        a_training = [
            p.checked(
                p.read_json(x.job_output(root, frozen, job) / "report.json"), "training_report"
            )
            for job in x.jobs_for("A_train")
        ]
        p.require(
            training_handoff["training_report_ids"] == [row["id"] for row in a_training]
            and all(row["actual_complete"] for row in a_training)
            and p.read_json(output / "A_execution_lineage.json")
            == x.parallel_lineage.execution_lineage(a_training),
            "evaluation_shared.reuse_original_completed_A_lineage",
        )
        amendment = p.record(
            "evaluation_resource_admission_amendment",
            at=p.now(),
            user_directive="调整优化（评估 GPU 显存准入）",
            execution_freeze_id=frozen["id"],
            execution_started_id=started["id"],
            A_training_handoff_id=training_handoff["id"],
            evaluation_resource_handoff_id=handoff["id"],
            external_source_capture=source_capture(root),
            scopes=["A_dev", "confirm"],
            physical_GPU_UUIDs=[row["gpu"]["uuid"] for row in frozen["parent_workers"]],
            prior_minimum_free_GPU_memory_MiB=76000,
            prior_required_GPU_utilization_percent=0,
            minimum_free_GPU_memory_MiB=77824,
            GPU_utilization_is_launch_condition=False,
            observed_generation_process_memory_MiB=[
                57716,
                54500,
                55958,
                75680,
                65654,
                65186,
                69620,
                49640,
            ],
            reference_max_observed_GPU_memory_MiB=75680,
            estimated_memory_margin_MiB=2144,
            measured_values_include_allocator_reservations=True,
            memory_sufficiency_is_estimate_not_guarantee=True,
            snapshot_is_not_a_memory_reservation=True,
            maximum_parallel_GPU_workers=8,
            one_active_own_worker_per_GPU=True,
            B_training_admission_changed=False,
            already_running_generation_workers_restarted=False,
            frozen_records_or_scientific_sources_rewritten=False,
            decoder_or_scoring_configuration_changed=False,
            material_validation_or_training_repeated=False,
            automatic_retry=False,
        )
        p.write_once(output / "evaluation_resource_admission_amendment.json", amendment)
        p.write_once(
            output / "evaluation_resource_coordinator_started.json",
            p.record(
                "evaluation_resource_coordinator_started",
                pid=os.getpid(),
                at=p.now(),
                execution_freeze_id=frozen["id"],
                execution_started_id=started["id"],
                evaluation_resource_handoff_id=handoff["id"],
                resource_admission_amendment_id=amendment["id"],
                adopted_existing_processes=8,
                existing_workers_or_publisher_signaled=False,
            ),
        )
        phase = "adopt_existing_Adev_and_launch_only_pending_job"
        scheduler.run_adopted_Adev(root, frozen, handoff, amendment)
        phase = "original_scoring_selection_and_conditional_confirmation"
        return complete_after_Adev(root, frozen, training_handoff, a_training, amendment)
    except BaseException as error:
        failure = output / "execution_failure.json"
        if not failure.exists():
            p.write_once(
                failure,
                p.record(
                    "execution_failure",
                    phase=phase,
                    at=p.now(),
                    error_type=type(error).__name__,
                    error=str(error)[:2000],
                    actual_complete=False,
                    automatic_retry=False,
                    partial_outputs_retained=True,
                    existing_generation_workers_signaled=False,
                ),
            )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    args = parser.parse_args()
    print(p.encode(run(args.code_root)).decode(), flush=True)


if __name__ == "__main__":
    main()
