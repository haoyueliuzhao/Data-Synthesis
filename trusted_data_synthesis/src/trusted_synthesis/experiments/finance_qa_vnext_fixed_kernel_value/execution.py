"""Gated new-kernel A-selection/B-confirmation execution with at most eight GPUs.

Preparation is read-only with respect to models. The explicit ``run`` entry
starts fresh scientific Students only after complete material and dose gates.
Public-generation workers receive no material rows, outcomes, or private task
fixtures. GPU failures stop new launches; failed outputs are never retried.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from ..finance_qa_vnext_basis_student.protocol import path_within
from ..finance_qa_vnext_eval_surface.overlay import public_object
from . import evaluation as e
from . import fast_materials, trajectory_materials
from . import protocol as p
from . import trajectory_training as training


def execution_policy():
    return p.record(
        "execution_policy",
        maximum_parallel_GPU_workers=8,
        one_worker_per_GPU=True,
        minimum_free_GPU_memory_MiB=76000,
        required_GPU_utilization_percent=0,
        GPU_allocation="ascending idle physical index; persistent UUID before spawn",
        worker_environment={"CUBLAS_WORKSPACE_CONFIG": ":4096:8", "OMP_NUM_THREADS": "2"},
        failure=(
            "stop launching; finish in-flight jobs; retain failures and not-started denominator"
        ),
        automatic_retry=False,
        partial_output_reused=False,
        maximum_training_runs=15,
        A_training_runs=9,
        A_dev_sessions=1620,
        B_training_runs_if_move=6,
        confirmation_sessions_if_move=8640,
        maximum_evaluation_sessions=10260,
        fixed_confirm_unique_tasks=720,
        seeds_multiply_independent_task_count=False,
        no_move="stop after A dev; no B training or confirmation",
        protected_surface_manifest_id=e.SURFACE_MANIFEST_ID,
        decoder_configuration="unchanged neutral greedy 2048-new-token / 24576-sequence contract",
        code_mutation_after_freeze=False,
        heldout_material_NLL=False,
    )


def code_root():
    return Path(__file__).resolve().parents[5]


def code_binding():
    """Bind committed Python bytes with one Git batch, not one process per file."""
    root = code_root()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    names = subprocess.check_output(
        ["git", "ls-files", "trusted_data_synthesis/src", "raw_financial_data_lake"],
        cwd=root,
        text=True,
    ).splitlines()
    names = sorted(name for name in names if name.endswith(".py"))
    required = {str(path.relative_to(root)) for path in Path(__file__).parent.glob("*.py")}
    p.require(required <= set(names), "execution.all_new_python_code_committed_before_training")
    p.require(
        all("\n" not in name and "\r" not in name for name in names),
        "execution.safe_git_object_spec",
    )
    requested = "".join(head + ":" + name + "\n" for name in names).encode()
    raw = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=root,
        input=requested,
        capture_output=True,
        check=True,
    ).stdout
    position, members = 0, []
    for name in names:
        line_end = raw.index(b"\n", position)
        header = raw[position:line_end].split()
        p.require(
            len(header) == 3 and header[1] == b"blob", "execution.exact_committed_python_blob"
        )
        width, begin = int(header[2]), line_end + 1
        committed = memoryview(raw)[begin : begin + width]
        p.require(
            raw[begin + width : begin + width + 1] == b"\n", "execution.complete_git_blob_frame"
        )
        actual = path_within(root, name).read_bytes()
        p.require(
            len(actual) == width and actual == committed,
            "execution.exact_committed_python_dependency",
        )
        members.append({"path": name, "sha256": p.sha(actual)})
        position = begin + width + 1
    p.require(position == len(raw), "execution.no_extra_git_blob_frames")
    return p.record(
        "execution_code_binding", code_root=str(root), head_commit=head, members=members
    )


def verify_code(bound):
    p.checked(bound, "execution_code_binding")
    p.require(bound["code_root"] == str(code_root()), "execution.frozen_code_root")
    for member in bound["members"]:
        p.require(
            p.sha(path_within(code_root(), member["path"])) == member["sha256"],
            "execution.frozen_dependency_bytes",
        )


def evaluation_registry(source_root):
    public = e.PublicOverlay(Path(source_root), e.SURFACE_DIRECTORY, e.SURFACE_MANIFEST_ID)
    result = {"dev": [], "confirm": []}
    for task in public.catalog["tasks"]:
        envelope = public.public_envelope(task["task_id"])
        value = public_object(envelope["messages"])
        result[task["split"]].append(
            {
                "task_id": task["task_id"],
                "group": task["family"],
                "source_cluster": value["period_contract"]["source_cluster"],
                "surface_version_id": task["surface_version_id"],
                "public_messages_sha256": task["public_messages_sha256"],
            }
        )
    for split in result:
        e._analysis_tasks(result[split], split, e.GROUPS)
    return result


def descriptor(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    p.require(path.is_relative_to(root), "execution.material_paths_in_experiment_root")
    relative = str(path.relative_to(root))
    path = path_within(root, relative)
    return {"path": relative, "bytes": path.stat().st_size, "sha256": p.sha(path)}


def load_descriptor(root, reference):
    p.require(set(reference) == {"path", "bytes", "sha256"}, "execution.closed_file_descriptor")
    path = path_within(root, reference["path"])
    raw = path.read_bytes()
    p.require(
        len(raw) == reference["bytes"] and p.sha(raw) == reference["sha256"],
        "execution.original_material_file_bytes",
    )
    return json.loads(raw)


def load_material_inputs(root, files, *, expected_kernel_id=None):
    """Build the complete immutable kernel once, bound to the actual material gate."""
    return fast_materials.load_material_inputs(root, files, expected_kernel_id=expected_kernel_id)


def binding(frozen):
    return {
        "study_freeze_id": frozen["study_freeze_id"],
        "surface_manifest_id": e.SURFACE_MANIFEST_ID,
        "kernel_id": frozen["kernel_id"],
        "training_configuration_id": frozen["training_configuration"]["id"],
        "decoder_config_id": frozen["decoder_configuration"]["id"],
    }


def _source_record(root, path, kind):
    """Read one parent metadata file once and bind exactly those observed bytes."""
    root = Path(root).resolve()
    path = Path(path)
    path = path if path.is_absolute() else root / path
    relative = str(path.relative_to(root))
    raw = path_within(root, relative).read_bytes()
    return p.checked(json.loads(raw), kind), {
        "path": relative,
        "bytes": len(raw),
        "sha256": p.sha(raw),
    }


def prepare(root, output, *, input_root, parent_freeze_path, parent_authority_path, workers=24):
    """Reuse the complete parent validation; build only compact fused trajectories."""
    root, output, input_root = (
        Path(root).resolve(),
        Path(output).resolve(),
        Path(input_root).resolve(),
    )
    p.require(
        output.is_relative_to(root)
        and output != root
        and not output.exists()
        and input_root != root
        and input_root.is_dir(),
        "execution.new_trajectory_output",
    )
    parent, parent_reference = _source_record(input_root, parent_freeze_path, "execution_freeze")
    authority, authority_reference = _source_record(
        input_root, parent_authority_path, "fast_execution_authority"
    )
    gate = p.checked(load_descriptor(input_root, parent["original_material_gate"]), "material_gate")
    p.require(
        parent["material_gate"]
        == parent["dose_gate"]
        == parent["training_gate"]
        == gate["material_gate"]
        == gate["dose_gate"]
        == gate["training_gate"]
        == "PASS"
        and authority["execution_freeze_id"] == parent["id"]
        and authority["original_kernel_id"] == parent["kernel_id"] == gate["kernel_id"]
        and authority["original_material_gate_id"]
        == parent["original_material_gate_id"]
        == gate["id"]
        and authority["original_registry_freeze_id"] == parent["study_freeze_id"]
        and authority["original_generation_report_id"] == gate["generation_report_id"]
        and authority["actual_full_original_kernel_ID_equal"] is True
        and parent["code_binding"]["code_root"] == str(input_root)
        and parent["material_verification"]["kernel_id"] == parent["kernel_id"],
        "execution.actual_parent_freeze_authority_gate_join",
    )
    # Fail missing/dirty source dependencies before doing cache work.
    source = code_binding()
    cache_root = output / "preparation" / "trajectory_cache"
    manifest = trajectory_materials.prepare_cache(
        input_root, cache_root, Path(input_root) / parent_reference["path"], workers=workers
    )
    p.checked(manifest, "trajectory_material_cache")
    p.require(
        manifest["parent_execution_freeze_id"] == parent["id"]
        and manifest["source_material_receipt"] == parent["material_input_receipt"]
        and manifest["kernel_id"] == parent["kernel_id"]
        and manifest["material_verification_id"] == parent["material_verification"]["id"]
        and manifest["source_material_budgets"] == parent["material_verification"]["pool_budgets"],
        "execution.trajectory_cache_original_global_authority",
    )
    for pool in p.POOLS:
        actual = manifest["pool_budgets"][pool]
        original = manifest["source_material_budgets"][pool]
        p.require(
            all(
                actual[field + suffix] == original[field + suffix]
                for field in ("packages", "target_tokens")
                for suffix in ("_per_epoch", "_all_epochs")
            )
            and all(
                actual[field + "_all_epochs"] == 10 * actual[field + "_per_epoch"]
                for field in ("packages", "rows", "target_tokens", "sequence_tokens")
            ),
            "execution.trajectory_preserves_physical_packages_targets_and_ten_visits",
        )
    cached = dict(
        cache_root=str(cache_root.relative_to(root)),
        manifest=descriptor(root, cache_root / "manifest.json"),
        manifest_id=manifest["id"],
    )
    frozen = p.record(
        "execution_freeze",
        study_freeze_id=parent["study_freeze_id"],
        output_directory=str(output.relative_to(root)),
        source_root=parent["source_root"],
        input_root=str(input_root),
        kernel_id=parent["kernel_id"],
        input_files=parent["input_files"],
        material_input_receipt=parent["material_input_receipt"],
        original_material_gate=parent["original_material_gate"],
        original_material_gate_id=parent["original_material_gate_id"],
        base_binding=parent["base_binding"],
        tokenizer_binding=parent["tokenizer_binding"],
        training_configuration=training.training_config(),
        decoder_configuration=parent["decoder_configuration"],
        execution_policy=execution_policy(),
        analysis_policy=parent["analysis_policy"],
        material_verification=parent["material_verification"],
        evaluation_registry=parent["evaluation_registry"],
        code_binding=source,
        physical_originals_sha256=parent["physical_originals_sha256"],
        material_gate="PASS",
        dose_gate="PASS",
        training_gate="PASS",
        parent_execution_freeze=parent_reference,
        parent_execution_freeze_id=parent["id"],
        parent_execution_authority=authority_reference,
        parent_authority=authority,
        parent_training_configuration_id=parent["training_configuration"]["id"],
        trajectory_cache=cached,
        trajectory_pool_budgets=manifest["pool_budgets"],
        source_material_budgets=manifest["source_material_budgets"],
        source_material_validation_reused=True,
        full_kernel_rebuilds=0,
        new_full_kernel_identity_measurement_claimed=False,
        new_token_encodings=0,
        new_API_calls=0,
        fresh_Students_required=True,
        parent_partial_Students_resumed=False,
        dropout_correlation_changed=True,
        bitwise_equivalence_claimed=False,
        objective_weights_labels_global_updates_epochs_and_seeds_preserved=True,
        Student_or_GPU_loaded=False,
    )
    p.write_once(output / "preparation" / "execution_freeze.json", frozen)
    return frozen


def validate_freeze(frozen):
    p.checked(frozen, "execution_freeze")
    p.require(
        frozen["training_configuration"] == training.training_config()
        and frozen["decoder_configuration"]
        == e.bind_policy(frozen["tokenizer_binding"], frozen["base_binding"])
        and frozen["execution_policy"] == execution_policy()
        and frozen["analysis_policy"] == e.analysis_policy()
        and frozen["training_gate"] == frozen["material_gate"] == frozen["dose_gate"] == "PASS",
        "execution.frozen_configuration_and_all_gates",
    )
    verify_code(frozen["code_binding"])


def jobs_for(phase, selected=None):
    if phase in ("A_train", "A_dev"):
        return [
            {
                "kind": "train" if phase == "A_train" else "generate",
                "pool": "A",
                "arm": arm,
                "seed": seed,
                **({"split": "dev"} if phase == "A_dev" else {}),
            }
            for seed in p.SEEDS
            for arm in p.ARMS
        ]
    p.require(selected in ("plus", "minus"), "execution.unique_strict_positive_direction")
    if phase == "B_train":
        return [
            {"kind": "train", "pool": "B", "arm": arm, "seed": seed}
            for seed in p.SEEDS
            for arm in ("alpha0", selected)
        ]
    p.require(phase == "confirm", "execution.registered_phase")
    return [
        {"kind": "generate", "pool": pool, "arm": arm, "seed": seed, "split": "confirm"}
        for pool in p.POOLS
        for seed in p.SEEDS
        for arm in ("alpha0", selected)
    ]


def job_name(job):
    return "_".join(str(job[key]) for key in ("kind", "pool", "arm", "seed")) + (
        "_" + job["split"] if "split" in job else ""
    )


def job_output(root, frozen, job, *, score=False):
    base = path_within(root, frozen["output_directory"])
    name = "_".join(str(job[key]) for key in ("pool", "arm", "seed"))
    if job["kind"] == "train":
        return base / "training" / name
    return base / ("scores" if score else "generation") / job["split"] / name


def _training_report(root, frozen, job):
    directory = job_output(root, frozen, {**job, "kind": "train"})
    report = p.checked(p.read_json(directory / "report.json"), "training_report")
    p.require(
        report["actual_complete"] is True
        and report["status"] == "COMPLETE_FINAL_CHECKPOINT"
        and report["optimizer_updates"] == 400
        and report["epochs_completed"] == 10,
        "execution.actual_complete_new_kernel_training",
    )
    p.require(
        all(
            report[key] == value
            for key, value in binding(frozen).items()
            if key != "decoder_config_id"
        )
        and all(report[key] == job[key] for key in ("pool", "arm", "seed")),
        "execution.exact_training_binding_and_variant",
    )
    budget = frozen["trajectory_pool_budgets"][job["pool"]]
    source_budget = frozen["material_verification"]["pool_budgets"][job["pool"]]
    p.require(
        report["actual_budget"] == budget
        and report["source_material_budget"] == source_budget
        and report["trajectory_cache_id"] == frozen["trajectory_cache"]["manifest_id"]
        and report["physical_originals_sha256"] == frozen["physical_originals_sha256"]
        and len(report["updates"]) == 400
        and all(
            type(item[field]) is int and item[field] > 0
            for item in report["updates"]
            for field in ("packages", "rows", "target_tokens", "sequence_tokens")
        )
        and all(
            sum(item[field] for item in report["updates"]) == budget[field + "_all_epochs"]
            for field in ("packages", "rows", "target_tokens", "sequence_tokens")
        ),
        "execution.identical_physical_original_budget_not_only_nominal_steps",
    )
    adapter = report["final_adapter"]
    path = path_within(directory, adapter["path"])
    p.require(
        path.stat().st_size == adapter["bytes"]
        and p.sha(path) == adapter["sha256"]
        and report["final_adapter_restored_identity_verified"] is True
        and adapter["parameter_digest"] == report["checkpoint_id"],
        "execution.exact_unique_final_adapter_bytes",
    )
    return report


def training_reports(root, frozen, jobs):
    reports = [_training_report(root, frozen, job) for job in jobs]
    for seed in p.SEEDS:
        paired = [report for report in reports if report["seed"] == seed]
        p.require(
            paired
            and len({report["initial_adapter_digest"] for report in paired}) == 1
            and len({report["schedule_id"] for report in paired}) == 1,
            "execution.paired_seed_initialization_and_task_schedule",
        )
    return reports


def public_generation_input(root, frozen, job):
    report = _training_report(root, frozen, job)
    identity = p.record(
        "model_identity",
        **binding(frozen),
        **{key: report[key] for key in ("pool", "arm", "seed", "checkpoint_id", "final_adapter")},
        training_report_id=report["id"],
        base_binding_id=frozen["base_binding"]["id"],
        tokenizer_binding_id=frozen["tokenizer_binding"]["id"],
        adapter_directory=report["adapter_directory"],
    )
    e.validate_model_identity(identity)
    return dict(
        model_identity=identity,
        base_binding=frozen["base_binding"],
        tokenizer_binding=frozen["tokenizer_binding"],
        decoder_configuration=frozen["decoder_configuration"],
        surface_directory=e.SURFACE_DIRECTORY,
        surface_manifest_id=e.SURFACE_MANIFEST_ID,
        source_root=frozen["source_root"],
        split=job["split"],
        output_directory=str(job_output(root, frozen, job).relative_to(root)),
    )


def available_gpus():
    raw = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=index,uuid,memory.free,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    )
    found = []
    for line in raw.splitlines():
        index, uuid, free, utilization = [item.strip() for item in line.split(",")]
        if int(free) >= 76000 and int(utilization) == 0:
            found.append(dict(index=int(index), uuid=uuid, free_memory_MiB=int(free)))
    return sorted(found, key=lambda item: item["index"])


def run_jobs(root, frozen, phase, *, selected=None, release=None, poll_seconds=10):
    p.require(0 < poll_seconds <= 60, "execution.bounded_poll_interval")
    root = Path(root).resolve()
    directory = path_within(root, frozen["output_directory"]) / "jobs" / phase
    p.require(not directory.exists(), "execution.no_phase_reexecution")
    jobs = jobs_for(phase, selected)
    p.write_once(
        directory / "registry.json",
        p.record(
            "worker_registry",
            phase=phase,
            jobs=jobs,
            execution_freeze_id=frozen["id"],
            **binding(frozen),
        ),
    )
    pending, running, finished, failures = list(jobs), {}, [], []
    while pending or running:
        for name, current in list(running.items()):
            code = current["process"].poll()
            if code is None:
                continue
            current["log"].close()
            result = p.record(
                "worker_exit",
                job=current["job"],
                return_code=code,
                gpu=current["gpu"],
                finished_at=p.now(),
            )
            p.write_once(directory / (name + "_exit.json"), result)
            (finished if code == 0 else failures).append(result)
            del running[name]
            print(
                p.encode({"event": "worker_exit", "job": name, "return_code": code}).decode(),
                flush=True,
            )
        if pending and not failures:
            used = {item["gpu"]["uuid"] for item in running.values()}
            free = [item for item in available_gpus() if item["uuid"] not in used]
            while pending and free and len(running) < 8:
                validate_freeze(frozen)
                job, gpu = pending.pop(0), free.pop(0)
                name = job_name(job)
                public = job["kind"] == "generate"
                if not public:
                    p.require(
                        release is not None
                        and {key: job[key] for key in ("pool", "arm", "seed")}
                        in release["allowed_runs"],
                        "execution.training_job_requires_explicit_release",
                    )
                payload = (
                    public_generation_input(root, frozen, job)
                    if public
                    else dict(
                        input_root=frozen["input_root"],
                        trajectory_cache=frozen["trajectory_cache"],
                        input_files=frozen["input_files"],
                        material_input_receipt=frozen["material_input_receipt"],
                        expected_kernel_id=frozen["kernel_id"],
                        expected_material_verification_id=frozen["material_verification"]["id"],
                        base_binding=frozen["base_binding"],
                        release=release,
                        output_directory=str(job_output(root, frozen, job).relative_to(root)),
                    )
                )
                worker_path = directory / (name + "_job.json")
                p.write_once(
                    worker_path,
                    p.record(
                        "worker_job",
                        job=job,
                        gpu=gpu,
                        code_binding=frozen["code_binding"],
                        execution_freeze_id=frozen["id"],
                        launched_at=p.now(),
                        **{"public_generation_input" if public else "training_input": payload},
                    ),
                )
                env = dict(os.environ)
                env.update(execution_policy()["worker_environment"])
                env["CUDA_VISIBLE_DEVICES"] = gpu["uuid"]
                env["PYTHONPATH"] = os.pathsep.join(
                    str(code_root() / path)
                    for path in ("raw_financial_data_lake", "trusted_data_synthesis/src")
                )
                log = (directory / (name + ".log")).open("xb")
                command = [
                    sys.executable,
                    "-m",
                    __package__ + ".execution",
                    "worker",
                    "--root",
                    str(root),
                    "--job",
                    str(worker_path),
                ]
                try:
                    process = subprocess.Popen(
                        command, cwd=code_root(), env=env, stdout=log, stderr=subprocess.STDOUT
                    )
                except Exception as error:
                    log.close()
                    result = p.record(
                        "worker_spawn_failure",
                        job=job,
                        gpu=gpu,
                        error_type=type(error).__name__,
                        error=str(error),
                        retry=False,
                    )
                    p.write_once(directory / (name + "_spawn_failure.json"), result)
                    failures.append(result)
                    break
                running[name] = dict(process=process, log=log, job=job, gpu=gpu)
                print(
                    p.encode(
                        {
                            "event": "worker_started",
                            "job": name,
                            "pid": process.pid,
                            "gpu": gpu,
                            "at": p.now(),
                        }
                    ).decode(),
                    flush=True,
                )
        if failures and not running:
            break
        if pending or running:
            time.sleep(poll_seconds)
    result = p.record(
        "worker_phase_report",
        phase=phase,
        execution_freeze_id=frozen["id"],
        status="COMPLETE_FIXED_WORKERS" if not failures and not pending else "STOP_WORKER_FAILURE",
        planned=len(jobs),
        finished=finished,
        failures=failures,
        not_started=pending,
        retries=0,
        partial_output_reused=False,
    )
    p.write_once(directory / "report.json", result)
    p.require(result["status"] == "COMPLETE_FIXED_WORKERS", "execution.worker_failure_no_retry")
    return result


def worker(root, job_path):
    root, job_path = Path(root).resolve(), Path(job_path).resolve()
    p.require(
        job_path.is_relative_to(root) and "jobs" in job_path.relative_to(root).parts,
        "execution.registered_worker_location",
    )
    supplied = p.checked(p.read_json(job_path), "worker_job")
    common = {
        "id",
        "schema_version",
        "job",
        "gpu",
        "code_binding",
        "execution_freeze_id",
        "launched_at",
    }
    verify_code(supplied["code_binding"])
    job = supplied["job"]
    if job["kind"] == "generate":
        p.require(
            set(supplied) == common | {"public_generation_input"},
            "execution.public_worker_no_private_material_or_freeze",
        )
        value = supplied["public_generation_input"]
        p.require(
            set(value)
            == {
                "model_identity",
                "base_binding",
                "tokenizer_binding",
                "decoder_configuration",
                "surface_directory",
                "surface_manifest_id",
                "source_root",
                "split",
                "output_directory",
            },
            "execution.closed_public_input",
        )
        identity = value["model_identity"]
        p.require(
            all(identity[key] == job[key] for key in ("pool", "arm", "seed"))
            and job["split"] == value["split"],
            "execution.public_job_variant_join",
        )
        output = path_within(root, value["output_directory"])
        p.require(not output.exists(), "execution.no_public_worker_retry")
        decoder = e.load_decoder(
            root,
            output / "decoder",
            identity,
            value["base_binding"],
            value["tokenizer_binding"],
            value["decoder_configuration"],
        )
        report = e.generate(
            root,
            output,
            surface_directory=value["surface_directory"],
            surface_manifest_id=value["surface_manifest_id"],
            split=value["split"],
            model_identity=identity,
            decoder=decoder,
            source_root=value["source_root"],
        )
    else:
        p.require(
            job["kind"] == "train" and set(supplied) == common | {"training_input"},
            "execution.closed_training_job",
        )
        value = supplied["training_input"]
        p.require(
            set(value)
            == {
                "input_root",
                "trajectory_cache",
                "input_files",
                "material_input_receipt",
                "expected_kernel_id",
                "expected_material_verification_id",
                "base_binding",
                "release",
                "output_directory",
            },
            "execution.closed_training_input",
        )
        inputs = fast_materials.load_authority(
            Path(value["input_root"]),
            value["material_input_receipt"],
            value["input_files"],
            expected_kernel_id=value["expected_kernel_id"],
        )
        cached = value["trajectory_cache"]
        manifest = load_descriptor(root, cached["manifest"])
        p.require(
            manifest["id"] == cached["manifest_id"], "execution.exact_frozen_trajectory_cache"
        )
        trajectories = trajectory_materials.load_pool(
            path_within(root, cached["cache_root"]), manifest, job["pool"]
        )
        p.require(
            inputs.verification["id"] == value["expected_material_verification_id"]
            and inputs["kernel"]["id"] == value["release"]["kernel_id"],
            "execution.worker_exact_global_material_verification",
        )
        report = training.run(
            root,
            path_within(root, value["output_directory"]),
            inputs["kernel"],
            inputs["population"],
            inputs["registry"],
            inputs["outcomes"],
            value["base_binding"],
            value["release"],
            pool=job["pool"],
            arm=job["arm"],
            seed=job["seed"],
            verified_inputs=inputs,
            trajectory_cache=trajectories,
        )
    p.require(report["actual_complete"] is True, "execution.actual_worker_completion_required")
    return report


def _score_one(arguments):
    return e.score(**arguments)


def score_jobs(root, frozen, jobs):
    arguments = []
    for job in jobs:
        generated = job_output(root, frozen, job)
        manifest = p.read_json(generated / "manifest.json")
        arguments.append(
            dict(
                root=root,
                generation_directory=generated,
                output=job_output(root, frozen, job, score=True),
                expected_generation_manifest_id=manifest["id"],
            )
        )
    with ProcessPoolExecutor(max_workers=min(len(arguments), p.CPU_WORKERS)) as executor:
        return list(executor.map(_score_one, arguments))


def run(root, frozen_path):
    root = Path(root).resolve()
    frozen = p.read_json(frozen_path)
    validate_freeze(frozen)
    output = path_within(root, frozen["output_directory"])
    p.write_once(
        output / "execution_started.json",
        p.record(
            "execution_started", at=p.now(), execution_freeze_id=frozen["id"], **binding(frozen)
        ),
    )
    phase = "material_reverification"
    try:
        inputs = fast_materials.load_authority(
            Path(frozen["input_root"]),
            frozen["material_input_receipt"],
            frozen["input_files"],
            expected_kernel_id=frozen["kernel_id"],
        )
        original_gate = p.checked(
            load_descriptor(Path(frozen["input_root"]), frozen["original_material_gate"]),
            "material_gate",
        )
        p.require(
            original_gate["id"] == frozen["original_material_gate_id"]
            and original_gate["kernel_id"] == frozen["kernel_id"]
            and original_gate["training_gate"] == "PASS",
            "execution.original_material_gate_unchanged_before_GPU",
        )
        verified = training.validate_materials(
            inputs["kernel"],
            inputs["population"],
            inputs["registry"],
            inputs["outcomes"],
            verified_inputs=inputs,
        )
        p.require(
            verified == frozen["material_verification"],
            "execution.material_reverification_before_GPU",
        )
        a_jobs = jobs_for("A_train")
        release = training.make_release(
            inputs["kernel"],
            study_freeze_id=frozen["study_freeze_id"],
            surface_manifest_id=e.SURFACE_MANIFEST_ID,
            allowed_runs=[{key: job[key] for key in ("pool", "arm", "seed")} for job in a_jobs],
            verified_inputs=inputs,
        )
        p.write_once(output / "A_release.json", release)
        phase = "A_train"
        run_jobs(root, frozen, phase, release=release)
        a_training = training_reports(root, frozen, a_jobs)
        phase = "A_dev"
        run_jobs(root, frozen, phase)
        dev = score_jobs(root, frozen, jobs_for(phase))
        decision = e.select_actual_direction(
            a_training, dev, binding=binding(frozen), dev_tasks=frozen["evaluation_registry"]["dev"]
        )
        p.write_once(output / "decision.json", decision)
        selected = decision["selected_arm"]
        if selected == "alpha0":
            report = p.record(
                "execution_report",
                status="COMPLETE_NO_POSITIVE_DIRECTION",
                actual_complete=True,
                **binding(frozen),
                decision_id=decision["id"],
                actual_training_runs=9,
                actual_evaluation_sessions=1620,
                B_training_runs=0,
                confirmation_sessions=0,
                independent_positive_effect_confirmed=False,
            )
        else:
            b_jobs = jobs_for("B_train", selected)
            release = training.make_release(
                inputs["kernel"],
                study_freeze_id=frozen["study_freeze_id"],
                surface_manifest_id=e.SURFACE_MANIFEST_ID,
                allowed_runs=[{key: job[key] for key in ("pool", "arm", "seed")} for job in b_jobs],
                verified_inputs=inputs,
            )
            p.write_once(output / "B_release.json", release)
            phase = "B_train"
            run_jobs(root, frozen, phase, selected=selected, release=release)
            all_training = training_reports(root, frozen, a_jobs + b_jobs)
            phase = "confirm"
            run_jobs(root, frozen, phase, selected=selected)
            confirm = score_jobs(root, frozen, jobs_for(phase, selected))
            result = e.confirm_actual(
                decision,
                all_training,
                confirm,
                binding=binding(frozen),
                confirm_tasks=frozen["evaluation_registry"]["confirm"],
            )
            p.write_once(output / "confirmation.json", result)
            report = p.record(
                "execution_report",
                status="COMPLETE_FIXED_CONFIRMATION",
                actual_complete=True,
                **binding(frozen),
                decision_id=decision["id"],
                confirmation_id=result["id"],
                actual_training_runs=15,
                actual_evaluation_sessions=10260,
                confirmation_sessions=8640,
                primary_pool="B",
                fixed_confirm_unique_tasks=720,
                independent_positive_effect_confirmed=result["status"]
                == "CONFIRMED_POSITIVE_AS_SCOPED",
            )
        verify_code(frozen["code_binding"])
        p.write_once(output / "report.json", report)
        e.seal_output(output, "fixed_kernel_value_execution", report)
        return report
    except BaseException as error:
        p.write_once(
            output / "execution_failure.json",
            p.record(
                "execution_failure",
                phase=phase,
                at=p.now(),
                error_type=type(error).__name__,
                error=str(error),
                actual_complete=False,
                automatic_retry=False,
                partial_outputs_retained=True,
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    launch = commands.add_parser("run")
    launch.add_argument("--root", required=True)
    launch.add_argument("--freeze", required=True)
    child = commands.add_parser("worker")
    child.add_argument("--root", required=True)
    child.add_argument("--job", required=True)
    prep = commands.add_parser("prepare")
    for name in ("root", "output", "input-root", "parent-freeze", "parent-authority"):
        prep.add_argument("--" + name, required=True)
    prep.add_argument("--workers", type=int, default=24)
    args = parser.parse_args()
    if args.command == "run":
        result = run(args.root, args.freeze)
    elif args.command == "worker":
        try:
            result = worker(args.root, args.job)
        except Exception as error:
            path = Path(args.job)
            p.write_once(
                path.with_name(path.stem + "_failure.json"),
                p.record(
                    "worker_failure",
                    at=p.now(),
                    error_type=type(error).__name__,
                    error=str(error),
                    automatic_retry=False,
                ),
            )
            raise
    else:
        result = prepare(
            args.root,
            args.output,
            input_root=args.input_root,
            parent_freeze_path=args.parent_freeze,
            parent_authority_path=args.parent_authority,
            workers=args.workers,
        )
    print(p.encode(result).decode(), flush=True)


if __name__ == "__main__":
    main()
