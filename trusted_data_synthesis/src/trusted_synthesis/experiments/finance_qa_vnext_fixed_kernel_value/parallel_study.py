"""Import eight completed Students unchanged, then run only the queued tail on eight GPUs.

This successor never signals the old workers/controller. It requires the old
scheduler to remain stopped, waits for bound workers to exit, and preserves all
imported file bytes and record IDs. Only model-identity adapter locations point
to their new physical copies; historical report paths remain historical.
"""

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from . import execution, fast_materials, parallel_lineage, parallel_training
from . import protocol as p

BRANCH = "codex/fixed-kernel-parallel-tail-20260914"
PARENT_COMMIT = "413c386c3a6b6ba45234ac48ed946bc1e8481d2b"
PARENT_ROOT = Path("/tmp/data-synthesis-fixed-kernel-trajectory-execution-20260914")
MATERIALS_ROOT = Path("/tmp/data-synthesis-fixed-kernel-completion-20260914")
DATA_ROOT = Path("/data1/zhuxinrui/projects/Data-Synthesis")
MATERIALS = (
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/study_20260914_budget_completion"
)
PARENT_OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/trajectory_execution_20260914"
)
OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/parallel_tail_execution_20260914"
)
RUNTIME = "trusted_data_synthesis/runtime/fixed_kernel_parallel_tail_execution_20260914"
PARENT_RUNTIME = "trusted_data_synthesis/runtime/fixed_kernel_trajectory_execution_20260914"
EXPECTED_GATE = "material_gate:16d9491e7ca7b6b506bc5308b67dc9de5b2958e94cba0d2944c5b9395f23e763"
EXPECTED_KERNEL = "fixed_kernel:f67d9edd0712d87d6d63d6e9535f8ff2db677cb81c884780afc8315c1d15c729"
TAIL = {"kind": "train", "pool": "A", "arm": "minus", "seed": 47}
PARENT_CONTROLLER_PID = 3169168


def root_path():
    return Path(__file__).resolve().parents[5]


def guard(root):
    root = Path(root).resolve()
    p.require(
        root == root_path() and root not in (PARENT_ROOT, MATERIALS_ROOT),
        "parallel_study.independent_source_root",
    )
    p.require(
        subprocess.check_output(["git", "branch", "--show-current"], cwd=root, text=True).strip()
        == BRANCH,
        "parallel_study.registered_successor_branch",
    )
    return root


def process_observation(pid, *, start_ticks=None):
    proc = Path("/proc") / str(pid)
    try:
        raw = (proc / "stat").read_text()
    except FileNotFoundError:
        return {"pid": pid, "state": "gone", "return_code": None, "exit_status_provable": False}
    fields = raw[raw.rfind(")") + 2 :].split()
    ticks = int(fields[19])
    p.require(start_ticks is None or ticks == start_ticks, "parallel_study.bound_PID_not_reused")
    state = fields[0]
    result = dict(
        pid=pid,
        state=state,
        ppid=int(fields[1]),
        start_ticks=ticks,
        return_code=None,
        exit_status_provable=False,
    )
    if state == "Z" and len(fields) >= 50:
        result.update(
            raw_wait_status=int(fields[49]),
            exit_status_provable=True,
            return_code=os.waitstatus_to_exitcode(int(fields[49])),
        )
    if state not in ("Z", "X"):
        result["cmdline_sha256"] = p.sha((proc / "cmdline").read_bytes())
    return result


def source_workers(parent, pause):
    p.require(
        pause["ninth_task_not_started"] is True
        and pause["active_training_workers_signaled"] is False,
        "parallel_study.explicit_scheduler_only_handoff",
    )
    controller = process_observation(PARENT_CONTROLLER_PID)
    prior = next(row for row in pause["paused_processes"] if row["pid"] == PARENT_CONTROLLER_PID)
    p.require(
        controller["state"] in ("T", "t")
        and controller["cmdline_sha256"] == prior["cmdline_sha256"],
        "parallel_study.original_scheduler_stopped_before_registration",
    )
    ids = (
        (
            Path("/proc")
            / str(PARENT_CONTROLLER_PID)
            / "task"
            / str(PARENT_CONTROLLER_PID)
            / "children"
        )
        .read_text()
        .split()
    )
    jobs = {execution.job_name(job): job for job in execution.jobs_for("A_train") if job != TAIL}
    observed = {}
    for value in ids:
        pid = int(value)
        command = (Path("/proc") / value / "cmdline").read_bytes().split(b"\0")
        args = [item.decode() for item in command if item]
        if "--job" not in args:
            continue
        job_path = Path(args[args.index("--job") + 1])
        name = job_path.name.removesuffix("_job.json")
        if name not in jobs:
            continue
        expected = PARENT_ROOT / PARENT_OUTPUT / "jobs/A_train" / (name + "_job.json")
        p.require(
            job_path == expected and name not in observed,
            "parallel_study.exact_parent_worker_command",
        )
        request, reference = execution._source_record(PARENT_ROOT, job_path, "worker_job")
        p.require(
            request["job"] == jobs[name]
            and request["execution_freeze_id"] == parent["id"]
            and request["code_binding"] == parent["code_binding"],
            "parallel_study.original_worker_job_binding",
        )
        observed[name] = dict(
            job=jobs[name],
            request=reference,
            request_id=request["id"],
            release_id=request["training_input"]["release"]["id"],
            gpu=request["gpu"],
            process=process_observation(pid),
        )
    p.require(set(observed) == set(jobs), "parallel_study.exact_eight_live_parent_workers")
    return controller, [
        observed[execution.job_name(job)] for job in execution.jobs_for("A_train") if job != TAIL
    ]


def check_scheduler(frozen):
    bound = frozen["parent_controller"]
    observed = process_observation(bound["pid"], start_ticks=bound["start_ticks"])
    p.require(
        observed["state"] in ("T", "t", "Z", "X", "gone"),
        "parallel_study.old_scheduler_must_not_launch_queued_tail",
    )
    tail = PARENT_ROOT / PARENT_OUTPUT / "training/A_minus_47"
    job = PARENT_ROOT / PARENT_OUTPUT / "jobs/A_train/train_A_minus_47_job.json"
    p.require(not tail.exists() and not job.exists(), "parallel_study.parent_tail_never_launched")
    return observed


def _signature(path):
    value = path.stat()
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def _tree_files(root):
    p.require(
        root.is_dir() and not any(item.is_symlink() for item in (root, *root.parents)),
        "parallel_study.regular_source_directory",
    )
    values = []
    for path in sorted(root.rglob("*")):
        p.require(not path.is_symlink(), "parallel_study.no_import_symlink")
        if path.is_dir():
            continue
        p.require(
            path.is_file() and ".git" not in path.relative_to(root).parts,
            "parallel_study.only_regular_scientific_files",
        )
        values.append(path.relative_to(root).as_posix())
    return values


def copy_tree_once(source, destination, *, expected=None):
    """One read/copy/SHA pass; no rewriting records, arrays or historical paths."""
    names = _tree_files(source)
    p.require(
        not destination.exists() and not any(x.is_symlink() for x in destination.parents),
        "parallel_study.exclusive_import_destination",
    )
    if expected is not None:
        p.require(set(names) == set(expected), "parallel_study.exact_frozen_cache_file_inventory")
    destination.mkdir(parents=True)
    members = []
    for name in names:
        original, target = source / name, destination / name
        before = _signature(original)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest, count = hashlib.sha256(), 0
        with original.open("rb") as incoming, target.open("xb") as outgoing:
            for block in iter(lambda: incoming.read(1024 * 1024), b""):
                outgoing.write(block)
                digest.update(block)
                count += len(block)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        row = dict(path=name, bytes=count, sha256=digest.hexdigest())
        p.require(
            _signature(original) == before and target.stat().st_size == count,
            "parallel_study.import_source_stable",
        )
        if expected is not None:
            p.require(
                all(row[key] == expected[name][key] for key in ("bytes", "sha256")),
                "parallel_study.exact_frozen_cache_file_bytes",
            )
        members.append(row)
    p.require(_tree_files(source) == names, "parallel_study.closed_source_namespace_unchanged")
    return members


def prepare(root):
    root = guard(root)
    output = root / OUTPUT
    p.require(not output.exists(), "parallel_study.one_new_successor_prepare")
    source_code = execution.code_binding()
    parent, parent_ref = execution._source_record(
        PARENT_ROOT, PARENT_OUTPUT + "/preparation/execution_freeze.json", "execution_freeze"
    )
    authority, authority_ref = execution._source_record(
        PARENT_ROOT,
        PARENT_OUTPUT + "/preparation/trajectory_execution_authority.json",
        "trajectory_execution_authority",
    )
    pause, pause_ref = execution._source_record(
        PARENT_ROOT,
        PARENT_RUNTIME + "/parallel_tail_handoff_pause.json",
        "parallel_tail_handoff_pause",
    )
    p.require(
        authority["execution_freeze_id"] == parent["id"]
        and parent["kernel_id"] == authority["original_kernel_id"] == EXPECTED_KERNEL
        and parent["original_material_gate_id"]
        == authority["original_material_gate_id"]
        == EXPECTED_GATE
        and parent["training_configuration"] == execution.training.training_config(),
        "parallel_study.exact_parent_trajectory_authority",
    )
    controller, workers = source_workers(parent, pause)
    source_cache = PARENT_ROOT / parent["trajectory_cache"]["cache_root"]
    manifest = p.checked(
        execution.load_descriptor(PARENT_ROOT, parent["trajectory_cache"]["manifest"]),
        "trajectory_material_cache",
    )
    p.require(
        manifest["id"] == parent["trajectory_cache"]["manifest_id"]
        and manifest["kernel_id"] == EXPECTED_KERNEL
        and manifest["pool_budgets"] == parent["trajectory_pool_budgets"]
        and manifest["source_material_budgets"] == parent["source_material_budgets"],
        "parallel_study.reuse_exact_existing_trajectory_cache",
    )
    expected = {
        row["path"]: row
        for pool in p.POOLS
        for row in (
            manifest["pools"][pool][key]
            for key in ("input_ids", "target_positions", "package_index")
        )
    }
    expected["manifest.json"] = {**parent["trajectory_cache"]["manifest"], "path": "manifest.json"}
    expected["started.json"] = execution.descriptor(source_cache, source_cache / "started.json")
    destination = output / "preparation/trajectory_cache"
    copied = copy_tree_once(source_cache, destination, expected=expected)
    copy_receipt = p.record(
        "parallel_tail_cache_copy",
        source_root=str(PARENT_ROOT),
        source_cache_root=parent["trajectory_cache"]["cache_root"],
        destination_cache_root=str(destination.relative_to(root)),
        cache_id=manifest["id"],
        members=copied,
        new_fusion_or_encoding=False,
    )
    p.write_once(output / "preparation/cache_copy.json", copy_receipt)
    fields = {key: value for key, value in parent.items() if key not in {"id", "schema_version"}}
    fields.pop("dropout_correlation_changed", None)
    fields.update(
        parent_training_configuration_id=parent["training_configuration"]["id"],
        parent_trajectory_dropout_correlation_changed=parent.get("dropout_correlation_changed"),
        parallel_tail_rng_policy=parallel_training.training_config()["parallel_rng_policy"],
        output_directory=OUTPUT,
        execution_policy=execution.execution_policy(),
        code_binding=source_code,
        trajectory_cache=dict(
            cache_root=str(destination.relative_to(root)),
            manifest=execution.descriptor(root, destination / "manifest.json"),
            manifest_id=manifest["id"],
        ),
        parent_source_root=str(PARENT_ROOT),
        parent_execution_output=PARENT_OUTPUT,
        parent_execution_freeze=parent_ref,
        parent_execution_freeze_id=parent["id"],
        parent_execution_authority=authority_ref,
        parent_authority=authority,
        parent_controller=controller,
        parent_workers=workers,
        scheduler_handoff=pause_ref,
        scheduler_handoff_id=pause["id"],
        cache_copy_id=copy_receipt["id"],
        heterogeneous_execution=True,
        per_run_training_configuration_ids=parallel_lineage.configuration_ids(),
        imported_completed_parent_runs_required=8,
        only_new_A_run=TAIL,
        parallel_tail_training_configuration=parallel_training.training_config(),
        source_material_validation_reused=True,
        new_full_kernel_rebuilds=0,
        new_fusion_operations=0,
        new_tokenizer_encodings=0,
        old_workers_signaled=False,
        parent_completed_report_bytes_rewritten=False,
        bitwise_equivalence_claimed=False,
    )
    frozen = p.record("execution_freeze", **fields)
    check_scheduler(frozen)
    p.write_once(output / "preparation/execution_freeze.json", frozen)
    admitted = p.record(
        "parallel_tail_execution_authority",
        execution_freeze_id=frozen["id"],
        parent_execution_freeze_id=parent["id"],
        parent_execution_authority_id=authority["id"],
        parent_source_root=str(PARENT_ROOT),
        original_material_source_root=str(MATERIALS_ROOT),
        original_material_gate_id=EXPECTED_GATE,
        original_kernel_id=EXPECTED_KERNEL,
        original_generation_report_id=authority["original_generation_report_id"],
        completion_freeze_id=authority["completion_freeze_id"],
        original_registry_freeze_id=parent["study_freeze_id"],
        training_configuration_id=parent["training_configuration"]["id"],
        per_run_training_configuration_ids=parallel_lineage.configuration_ids(),
        trajectory_cache_id=manifest["id"],
        trajectory_cache=frozen["trajectory_cache"],
        cache_copy_id=copy_receipt["id"],
        scheduler_handoff_id=pause["id"],
        imported_completed_parent_runs_required=8,
        only_new_A_run=TAIL,
        heterogeneous_execution=True,
        original_report_IDs_and_bytes_preserved=True,
        parent_workers_signaled=False,
        source_material_validation_reused=True,
        fresh_parallel_tail_only=True,
        optimizer_partial_state_reused=False,
        bitwise_equivalence_claimed=False,
        user_directive="调整第九任务为并行",
        created_at=p.now(),
    )
    p.write_once(output / "preparation/parallel_execution_authority.json", admitted)
    return {"execution_freeze": frozen, "authority": admitted}


def import_completed_run(root, frozen, bound, observation):
    job = bound["job"]
    source = execution.job_output(PARENT_ROOT, {**frozen, "output_directory": PARENT_OUTPUT}, job)
    p.require(
        observation["state"] in ("Z", "X", "gone")
        and (not observation["exit_status_provable"] or observation["return_code"] == 0),
        "parallel_study.parent_worker_exited_successfully_when_provable",
    )
    p.require(not (source / "failure.json").exists(), "parallel_study.no_failed_parent_run")
    report = execution.validate_training_report(p.read_json(source / "report.json"), frozen, job)
    p.require(
        report["release_id"] == bound["release_id"], "parallel_study.original_training_release"
    )
    destination = execution.job_output(root, frozen, job)
    members = copy_tree_once(source, destination)
    by_name = {row["path"]: row for row in members}
    adapter = report["final_adapter"]
    p.require(
        adapter["path"] == "final_adapter.safetensors"
        and adapter["parameter_digest"] == report["checkpoint_id"]
        and report["final_adapter_restored_identity_verified"] is True
        and all(by_name[adapter["path"]][key] == adapter[key] for key in ("bytes", "sha256"))
        and by_name["report.json"]["sha256"] == p.sha(p.encode(report)),
        "parallel_study.copied_actual_final_adapter_and_original_report",
    )
    return p.record(
        "completed_parent_training_import",
        job=job,
        source_root=str(PARENT_ROOT),
        source_directory=str(source.relative_to(PARENT_ROOT)),
        destination_directory=str(destination.relative_to(root)),
        source_execution_freeze_id=frozen["parent_execution_freeze_id"],
        source_worker_job_id=bound["request_id"],
        training_report_id=report["id"],
        training_configuration_id=report["training_configuration_id"],
        original_adapter_directory=report["adapter_directory"],
        checkpoint_id=report["checkpoint_id"],
        initial_adapter_digest=report["initial_adapter_digest"],
        schedule_id=report["schedule_id"],
        source_worker_exit_observation=observation,
        members=members,
        report_ID_or_historical_paths_rewritten=False,
        resumed_partial_state=False,
        source_files_or_processes_modified=False,
        imported_at=p.now(),
    )


def await_parent_imports(root, frozen, *, sleeper=time.sleep):
    pending = list(frozen["parent_workers"])
    imported = {}
    while pending:
        check_scheduler(frozen)
        for bound in list(pending):
            name = execution.job_name(bound["job"])
            source = execution.job_output(
                PARENT_ROOT, {**frozen, "output_directory": PARENT_OUTPUT}, bound["job"]
            )
            p.require(
                not (source / "failure.json").exists(), "parallel_study.parent_training_failed"
            )
            observation = process_observation(
                bound["process"]["pid"], start_ticks=bound["process"]["start_ticks"]
            )
            if observation["state"] not in ("Z", "X", "gone"):
                continue
            p.require(
                (source / "report.json").is_file(),
                "parallel_study.exited_parent_without_complete_report",
            )
            value = import_completed_run(root, frozen, bound, observation)
            p.write_once(root / OUTPUT / "imports" / (name + ".json"), value)
            imported[name] = value
            pending.remove(bound)
            print(
                p.encode(
                    {
                        "event": "parent_training_imported",
                        "job": name,
                        "report_id": value["training_report_id"],
                    }
                ).decode(),
                flush=True,
            )
        if pending:
            sleeper(10)
    return [imported[execution.job_name(row["job"])] for row in frozen["parent_workers"]]


def await_devices(frozen, *, sleeper=time.sleep):
    wanted = {row["gpu"]["uuid"] for row in frozen["parent_workers"]}
    p.require(len(wanted) == 8, "parallel_study.same_eight_physical_GPUs")
    while True:
        check_scheduler(frozen)
        available = [row for row in execution.available_gpus() if row["uuid"] in wanted]
        if len(available) == 8:
            return [row["uuid"] for row in available]
        sleeper(10)


def run(root):
    root = guard(root)
    output = root / OUTPUT
    frozen = p.checked(
        p.read_json(output / "preparation/execution_freeze.json"), "execution_freeze"
    )
    authority = p.checked(
        p.read_json(output / "preparation/parallel_execution_authority.json"),
        "parallel_tail_execution_authority",
    )
    p.require(
        authority["execution_freeze_id"] == frozen["id"]
        and authority["original_kernel_id"] == frozen["kernel_id"] == EXPECTED_KERNEL
        and authority["per_run_training_configuration_ids"]
        == frozen["per_run_training_configuration_ids"],
        "parallel_study.actual_successor_authority",
    )
    execution.validate_freeze(frozen)
    started = p.record(
        "execution_started",
        at=p.now(),
        execution_freeze_id=frozen["id"],
        **execution.binding(frozen),
        heterogeneous_execution=True,
        inherited_running_parent_Students_not_restarted=True,
    )
    p.write_once(output / "execution_started.json", started)
    phase = "await_existing_eight_completed_Students"
    try:
        imported = await_parent_imports(root, frozen)
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
            "parallel_study.existing_seed47_pair_initialization_and_schedule",
        )
        phase = "await_eight_released_GPUs"
        devices = await_devices(frozen)
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
            allowed_runs=[{key: TAIL[key] for key in ("pool", "arm", "seed")}],
            verified_inputs=inputs,
        )
        p.write_once(output / "A_parallel_tail_release.json", release)
        report = parallel_training.launch(
            root,
            execution.job_output(root, frozen, TAIL),
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
        execution.validate_training_report(report, frozen, TAIL)
        reports = execution.training_reports(root, frozen, execution.jobs_for("A_train"))
        handoff = p.record(
            "parallel_tail_A_handoff",
            execution_freeze_id=frozen["id"],
            execution_started_id=started["id"],
            imported_parent_runs=8,
            new_parallel_runs=1,
            parent_import_manifest_id=imports["id"],
            tail_report_id=report["id"],
            training_report_ids=[item["id"] for item in reports],
            execution_lineage=parallel_lineage.execution_lineage(reports),
            ended_at=p.now(),
        )
        p.write_once(output / "A_training_handoff.json", handoff)
        phase = "original_Adev_B_confirmation_chain"
        return execution.run(root, output / "preparation/execution_freeze.json", handoff=handoff)
    except BaseException as error:
        p.write_once(
            output / "parallel_handoff_failure.json",
            p.record(
                "parallel_handoff_failure",
                phase=phase,
                error_type=type(error).__name__,
                reason=str(error)[:2000],
                old_training_workers_signaled=False,
                partial_artifacts_retained=True,
                automatic_retry=False,
                at=p.now(),
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, default=root_path())
    parser.add_argument("--phase", choices=("prepare", "run"), required=True)
    args = parser.parse_args()
    result = {"prepare": prepare, "run": run}[args.phase](args.code_root)
    if args.phase == "prepare":
        print(
            json.dumps(
                {
                    "execution_freeze_id": result["execution_freeze"]["id"],
                    "authority_id": result["authority"]["id"],
                    "imported_parent_runs_required": 8,
                }
            ),
            flush=True,
        )
    else:
        print(p.encode(result).decode(), flush=True)


if __name__ == "__main__":
    main()
