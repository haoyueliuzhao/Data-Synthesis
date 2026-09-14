"""Continue the unstarted parallel tail with an explicit memory-only admission amendment.

The eight existing Students, original execution-start record, frozen scientific
sources and publisher are untouched. Only A/minus/47's GPU admission changes;
the original execution engine retains its policy for every later phase.
"""

import argparse
import os
import subprocess
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
    execution,
    fast_materials,
    parallel_lineage,
    parallel_training,
)
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
    parallel_study as s,
)
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
    protocol as p,
)

SCRIPT = "trusted_data_synthesis/scripts/continue_fixed_kernel_parallel_tail_shared_gpu_20260914.py"
MINIMUM_FREE_MIB = 32768
PREVIOUS_COORDINATOR_PID = 3363356


def query_gpu_snapshot():
    raw = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=index,uuid,memory.free,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    )
    rows = []
    for line in raw.splitlines():
        index, uuid, free, utilization = [item.strip() for item in line.split(",")]
        rows.append(
            dict(
                index=int(index),
                uuid=uuid,
                free_memory_MiB=int(free),
                utilization_percent=int(utilization),
            )
        )
    return rows


def eligible_devices(rows, wanted, minimum_free_mib=MINIMUM_FREE_MIB):
    wanted = list(wanted)
    p.require(
        len(wanted) == len(set(wanted)) == 8
        and all(isinstance(uuid, str) and uuid.startswith("GPU-") for uuid in wanted),
        "resource_admission.same_eight_unique_physical_GPU_UUIDs",
    )
    p.require(
        type(minimum_free_mib) is int and minimum_free_mib > 0,
        "resource_admission.positive_integer_memory_threshold",
    )
    p.require(
        len({row["uuid"] for row in rows}) == len(rows)
        and len({row["index"] for row in rows}) == len(rows),
        "resource_admission.no_duplicate_physical_GPUs_in_snapshot",
    )
    for row in rows:
        p.require(
            isinstance(row["uuid"], str)
            and row["uuid"].startswith("GPU-")
            and type(row["index"]) is int
            and row["index"] >= 0
            and type(row["free_memory_MiB"]) is int
            and row["free_memory_MiB"] >= 0
            and type(row["utilization_percent"]) is int
            and 0 <= row["utilization_percent"] <= 100,
            "resource_admission.valid_observed_GPU_snapshot",
        )
    return sorted(
        [
            row
            for row in rows
            if row["uuid"] in wanted and row["free_memory_MiB"] >= minimum_free_mib
        ],
        key=lambda row: row["index"],
    )


def _unstarted_boundary(root):
    output = root / s.OUTPUT
    forbidden = (
        "imports",
        "training",
        "jobs",
        "completed_parent_imports.json",
        "A_parallel_tail_release.json",
        "A_training_handoff.json",
        "report.json",
        "manifest.json",
        "execution_failure.json",
        "parallel_handoff_failure.json",
        "resource_admission_amendment.json",
        "resource_admission_coordinator_started.json",
        "resource_admission.json",
    )
    p.require(
        not any((output / name).exists() for name in forbidden),
        "resource_admission.only_before_first_parent_import_or_tail_launch",
    )


def _handoff(root, frozen, started):
    handoff = p.checked(
        p.read_json(root / s.OUTPUT / "resource_admission_handoff.json"),
        "resource_admission_handoff",
    )
    launch = p.checked(
        p.read_json(root / s.RUNTIME / "coordinator_launch.json"),
        "parallel_tail_coordinator_launch",
    )
    previous = handoff["previous_coordinator"]
    stopped, exited = handoff["stopped_observation"], handoff["exit_observation"]
    p.require(
        handoff["execution_freeze_id"] == frozen["id"] == launch["execution_freeze_id"]
        and handoff["execution_started_id"] == started["id"]
        and handoff["previous_coordinator_launch_id"] == launch["id"]
        and previous["pid"] == launch["pid"] == PREVIOUS_COORDINATOR_PID
        and previous["pid"] != os.getpid()
        and previous["pid"] not in {row["process"]["pid"] for row in frozen["parent_workers"]}
        and handoff["signaled_pids"] == [PREVIOUS_COORDINATOR_PID]
        and handoff["children_after_stop"] == []
        and handoff["training_workers_signaled"] is False
        and handoff["publisher_signaled"] is False,
        "resource_admission.exact_scheduler_only_handoff",
    )
    p.require(
        stopped["pid"] == previous["pid"] == exited["pid"]
        and stopped["state"] in ("T", "t")
        and stopped["start_ticks"] == previous["start_ticks"]
        and stopped["cmdline_sha256"] == previous["cmdline_sha256"]
        and previous["cmdline_sha256"]
        == p.sha(b"\0".join(x.encode() for x in launch["argv"]) + b"\0")
        and exited["state"] in ("Z", "X", "gone")
        and (exited["state"] == "gone" or exited["start_ticks"] == previous["start_ticks"]),
        "resource_admission.original_coordinator_identity_and_observed_exit",
    )
    actual = s.process_observation(previous["pid"], start_ticks=previous["start_ticks"])
    p.require(actual["state"] in ("Z", "X", "gone"), "resource_admission.old_coordinator_exited")
    children = Path("/proc") / str(previous["pid"]) / "task" / str(previous["pid"]) / "children"
    p.require(
        not children.exists() or not children.read_text().strip(),
        "resource_admission.no_previous_coordinator_children",
    )
    s.check_scheduler(frozen)
    return handoff, actual


def _source_capture(root):
    p.require(Path(__file__).resolve() == root / SCRIPT, "resource_admission.exact_external_script")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    committed = subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root)
    actual = (root / SCRIPT).read_bytes()
    p.require(committed == actual, "resource_admission.external_script_committed_before_start")
    return dict(head_commit=head, path=SCRIPT, bytes=len(actual), sha256=p.sha(actual))


def await_shared_devices(root, frozen, amendment, *, sleeper=s.time.sleep):
    wanted = [row["gpu"]["uuid"] for row in frozen["parent_workers"]]
    p.require(
        amendment["scope"] == s.TAIL
        and amendment["minimum_free_GPU_memory_MiB"] == MINIMUM_FREE_MIB
        and amendment["GPU_utilization_is_launch_condition"] is False,
        "resource_admission.exact_tail_only_memory_amendment",
    )
    while True:
        s.check_scheduler(frozen)
        snapshot = query_gpu_snapshot()
        eligible = eligible_devices(snapshot, wanted)
        if len(eligible) == 8:
            admission = p.record(
                "parallel_tail_shared_GPU_admission",
                at=p.now(),
                execution_freeze_id=frozen["id"],
                resource_admission_amendment_id=amendment["id"],
                scope=s.TAIL,
                devices=eligible,
                observed_all_GPUs=snapshot,
                minimum_free_GPU_memory_MiB=MINIMUM_FREE_MIB,
                GPU_utilization_is_launch_condition=False,
                snapshot_is_not_a_memory_reservation=True,
            )
            p.write_once(root / s.OUTPUT / "resource_admission.json", admission)
            return [row["uuid"] for row in eligible]
        sleeper(10)


def run(root):
    root = s.guard(root)
    output, phase = root / s.OUTPUT, "resource_admission_preflight"
    try:
        _unstarted_boundary(root)
        frozen = p.checked(
            p.read_json(output / "preparation/execution_freeze.json"), "execution_freeze"
        )
        started = p.checked(p.read_json(output / "execution_started.json"), "execution_started")
        authority = p.checked(
            p.read_json(output / "preparation/parallel_execution_authority.json"),
            "parallel_tail_execution_authority",
        )
        p.require(
            started["execution_freeze_id"] == authority["execution_freeze_id"] == frozen["id"]
            and authority["original_kernel_id"] == frozen["kernel_id"] == s.EXPECTED_KERNEL
            and authority["per_run_training_configuration_ids"]
            == frozen["per_run_training_configuration_ids"],
            "resource_admission.original_started_freeze_and_authority",
        )
        handoff, exited = _handoff(root, frozen, started)
        execution.validate_freeze(frozen)
        amendment = p.record(
            "parallel_tail_resource_admission_amendment",
            at=p.now(),
            user_directive="修订启动条件，有足够显存剩余即可启动",
            execution_freeze_id=frozen["id"],
            execution_started_id=started["id"],
            resource_admission_handoff_id=handoff["id"],
            external_source_capture=_source_capture(root),
            scope=s.TAIL,
            physical_GPU_UUIDs=[row["gpu"]["uuid"] for row in frozen["parent_workers"]],
            prior_minimum_free_GPU_memory_MiB=76000,
            prior_required_GPU_utilization_percent=0,
            minimum_free_GPU_memory_MiB=MINIMUM_FREE_MIB,
            GPU_utilization_is_launch_condition=False,
            observed_single_GPU_Student_reference_GiB=25.3,
            estimated_memory_margin_GiB=6.7,
            parallel_peak_memory_measured=False,
            memory_sufficiency_is_estimate_not_guarantee=True,
            snapshot_is_not_a_memory_reservation=True,
            first_eight_Students_must_complete_before_tail=True,
            frozen_records_and_scientific_source_bytes_rewritten=False,
            original_execution_started_record_reused=True,
            later_phase_admission_policy_changed=False,
            numerical_training_configuration_changed=False,
            preparation_cache_or_smoke_repeated=False,
            automatic_retry=False,
        )
        p.write_once(output / "resource_admission_amendment.json", amendment)
        p.write_once(
            output / "resource_admission_coordinator_started.json",
            p.record(
                "resource_admission_coordinator_started",
                at=p.now(),
                pid=os.getpid(),
                execution_freeze_id=frozen["id"],
                execution_started_id=started["id"],
                resource_admission_amendment_id=amendment["id"],
                previous_coordinator_exit_observation=exited,
                original_Students_restarted=False,
                publisher_restarted=False,
            ),
        )
        phase = "await_existing_eight_completed_Students"
        imported = s.await_parent_imports(root, frozen)
        imports = p.record(
            "completed_parent_training_imports",
            execution_freeze_id=frozen["id"],
            imports=imported,
            completed_parent_runs=8,
            original_report_IDs_preserved=True,
        )
        p.write_once(output / "completed_parent_imports.json", imports)
        paired = [
            row
            for row in imported
            if row["job"]["seed"] == 47 and row["job"]["arm"] in ("alpha0", "plus")
        ]
        p.require(
            len(paired) == 2
            and len({row["initial_adapter_digest"] for row in paired}) == 1
            and len({row["schedule_id"] for row in paired}) == 1,
            "resource_admission.original_seed47_pair_initialization_and_schedule",
        )
        phase = "await_same_eight_GPUs_with_sufficient_free_memory"
        devices = await_shared_devices(root, frozen, amendment)
        phase = "parallel_tail_A_minus_47"
        inputs = fast_materials.load_authority(
            Path(frozen["input_root"]),
            frozen["material_input_receipt"],
            frozen["input_files"],
            expected_kernel_id=frozen["kernel_id"],
        )
        release = parallel_training.make_release(
            inputs["kernel"],
            study_freeze_id=frozen["study_freeze_id"],
            surface_manifest_id=execution.e.SURFACE_MANIFEST_ID,
            allowed_runs=[{key: s.TAIL[key] for key in ("pool", "arm", "seed")}],
            verified_inputs=inputs,
        )
        p.write_once(output / "A_parallel_tail_release.json", release)
        report = parallel_training.launch(
            root,
            execution.job_output(root, frozen, s.TAIL),
            input_root=frozen["input_root"],
            material_input_receipt=frozen["material_input_receipt"],
            input_files=frozen["input_files"],
            expected_kernel_id=frozen["kernel_id"],
            trajectory_cache=frozen["trajectory_cache"],
            base_binding=frozen["base_binding"],
            release=release,
            devices=devices,
            expected_initial_adapter_digest=paired[0]["initial_adapter_digest"],
            expected_schedule_id=paired[0]["schedule_id"],
        )
        execution.validate_training_report(report, frozen, s.TAIL)
        reports = execution.training_reports(root, frozen, execution.jobs_for("A_train"))
        final_handoff = p.record(
            "parallel_tail_A_handoff",
            execution_freeze_id=frozen["id"],
            execution_started_id=started["id"],
            imported_parent_runs=8,
            new_parallel_runs=1,
            parent_import_manifest_id=imports["id"],
            tail_report_id=report["id"],
            training_report_ids=[item["id"] for item in reports],
            execution_lineage=parallel_lineage.execution_lineage(reports),
            resource_admission_amendment_id=amendment["id"],
            ended_at=p.now(),
        )
        p.write_once(output / "A_training_handoff.json", final_handoff)
        phase = "original_Adev_B_confirmation_chain"
        return execution.run(
            root, output / "preparation/execution_freeze.json", handoff=final_handoff
        )
    except BaseException as error:
        failure = output / "parallel_handoff_failure.json"
        if not failure.exists():
            p.write_once(
                failure,
                p.record(
                    "parallel_handoff_failure",
                    phase=phase,
                    error_type=type(error).__name__,
                    reason=str(error)[:2000],
                    old_training_workers_signaled=False,
                    partial_artifacts_retained=True,
                    automatic_retry=False,
                    resource_admission_continuation=True,
                    at=p.now(),
                ),
            )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    args = parser.parse_args()
    run(args.code_root)


if __name__ == "__main__":
    main()
