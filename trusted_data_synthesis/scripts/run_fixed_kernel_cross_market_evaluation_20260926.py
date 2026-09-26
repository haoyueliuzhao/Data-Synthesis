"""Register/start/resume the finite cross-market nine-model evaluation only.

Preparation reads CPU checkpoints to serialize their existing LoRA parameters;
there is no optimizer, retraining, model selection, SEC access or source repair.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

import fixed_kernel_cross_market_evaluation_20260926 as evaluation

p, prior, legacy = evaluation.p, evaluation.prior, evaluation.legacy
SCRIPT = "trusted_data_synthesis/scripts/run_fixed_kernel_cross_market_evaluation_20260926.py"
BASE = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value"
)
RAW = BASE / "cross_market_calibration_cache_20260926/evaluation_01"
PARENT = BASE / "direction_calibration_cache_20260926"
SOURCE_FILES = [
    SCRIPT,
    evaluation.SCRIPT,
    "trusted_data_synthesis/scripts/fixed_kernel_cross_market_runtime_20260926.py",
    prior.SCRIPT,
    "trusted_data_synthesis/scripts/fixed_kernel_B_generation_20260922.py",
    "trusted_data_synthesis/scripts/fixed_kernel_B_scoring_20260922.py",
    "trusted_data_synthesis/scripts/fixed_kernel_anchored_feedback_20260916.py",
    "trusted_data_synthesis/scripts/cross_market_statistics_20260926.py",
    "trusted_data_synthesis/scripts/fixed_kernel_direction_calibration_statistics_20260926.py",
]


def emit(event, **fields):
    print(json.dumps(dict(event=event, at=p.now(), **fields)), flush=True)


def read(path):
    return p.read_json(path) if Path(path).exists() else None


def reference(path):
    path = Path(path).resolve()
    value = p.read_json(path)
    return dict(path=str(path), sha256=p.sha(path), bytes=path.stat().st_size, id=value["id"])


def training_credits():
    admission = p.checked(
        p.read_json(PARENT / "reuse_admission.json"), "direction_calibration_material_admission"
    )
    complete = p.checked(
        p.read_json(PARENT / "training_stage_20260926/complete.json"),
        "B_direction_calibration_training_completed",
    )
    p.require(
        admission["passed"] is True
        and complete["complete"] is True
        and complete["committed_optimizer_updates"] == 120,
        "cross_market_controller.previous_training_admitted",
    )
    return admission, complete


def register(root, panel_references, raw=RAW):
    c = evaluation.Context(raw)
    if (c.RAW / "protocol.json").exists():
        plan = c.read_protocol(root)
        p.require(
            plan["panel"] == p.read_json(panel_references),
            "cross_market_controller.same_registered_panel",
        )
        return plan
    panel = p.read_json(panel_references)
    manifest = prior.public_manifest({"panel": panel})
    admission, complete = training_credits()
    models = []
    for row in admission["reusable_refs"]:
        if row["step"] != 240:
            continue
        p.require(
            row["parameters_Adam_and_RNG_verified"] is True,
            "cross_market_controller.existing_checkpoint_credit",
        )
        models.append(
            dict(
                key=f"{row['condition']}_{row['seed']}",
                condition=row["condition"],
                seed=row["seed"],
                path=row["path"],
                sha256=row["sha256"],
                snapshot_id=row["snapshot_id"],
                provenance_id=admission["id"],
            )
        )
    for row in complete["seeds"]:
        models.append(
            dict(
                key=f"negative_{row['seed']}",
                condition="negative",
                seed=row["seed"],
                path=row["checkpoint_path"],
                sha256=row["checkpoint_sha256"],
                snapshot_id=row["snapshot_id"],
                provenance_id=complete["id"],
            )
        )
    p.require(
        len(models) == 9
        and {(r["condition"], r["seed"]) for r in models}
        == {(a, s) for a in prior.ARMS for s in prior.SEEDS},
        "cross_market_controller.exact_nine_models",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    scientific_sources = {}
    for name in SOURCE_FILES:
        payload = (Path(root) / name).read_bytes()
        p.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "cross_market_controller.code_committed_before_registration",
        )
        scientific_sources[name] = p.sha(payload)
    plan = p.record(
        evaluation.PROTOCOL_KIND,
        frozen=True,
        panel=panel,
        source_manifest_id=manifest["id"],
        materials=dict(
            assets=admission["materials"]["assets"], runtime_binding=evaluation.views.binding()
        ),
        models=sorted(models, key=lambda row: row["key"]),
        parent_reuse_admission=reference(PARENT / "reuse_admission.json"),
        negative_training_completion=reference(PARENT / "training_stage_20260926/complete.json"),
        scientific_sources=scientific_sources,
        code_commit=head,
        totals=dict(models=9, cohorts=18, tasks=180, stochastic=3240, greedy=1620, sessions=4860),
        physical_budget=dict(
            generate_call_cap=4860 * 32 + 2304,
            incomplete_generate_call_cap=2304,
            score_case_cap=5100,
            worker_start_cap=216,
        ),
        scheduling=dict(
            generation_shards_stochastic=3,
            generation_shards_greedy=2,
            max_GPU_workers=8,
            minimum_free_MiB=49152,
            max_score_cohorts=2,
            score_workers_per_cohort=12,
            generation_attempts_per_shard=4,
            scoring_attempts_per_cohort=2,
            polling_seconds=20,
        ),
        paired_sampling_seed_rule=(
            "trajectory_seed(cross_market_20260926,training_seed,mode_round,task_id,repeat); no arm"
        ),
        private_barrier="all4860 sessions sealed and all generation workers exited",
        new_training_updates=0,
        source_currency_adapter_changed=True,
        financial_support_principle_unchanged=True,
        registered_at=p.now(),
    )
    c.write(c.RAW / "protocol.json", plan)
    emit("evaluation_registered", protocol_id=plan["id"], sessions=4860)
    return plan


def prepare_point(c, plan, model):
    directory = c.RAW / "points" / model["key"]
    path = directory / "point.json"
    if path.exists():
        point = p.checked(p.read_json(path), "anchored_model_parameter_point")
        p.require(
            point["origin_checkpoint"] == model
            and point["source_manifest_id"] == plan["source_manifest_id"]
            and point["step"] == 240,
            "cross_market_controller.same_existing_point",
        )
        return path, point
    checkpoint = Path(model["path"])
    p.require(
        checkpoint.is_absolute() and p.sha(checkpoint) == model["sha256"],
        "cross_market_controller.checkpoint_bytes",
    )
    saved = legacy.torch.load(checkpoint, map_location="cpu", weights_only=False)
    p.require(
        saved["completed_updates"] == 240 and saved["snapshot"]["id"] == model["snapshot_id"],
        "cross_market_controller.same_saved240_snapshot",
    )
    theta = {
        name.removeprefix("theta/"): value
        for name, value in saved["state"].items()
        if name.startswith("theta/")
    }
    p.require(
        theta and all(name.endswith((".lora_A", ".lora_B")) for name in theta),
        "cross_market_controller.existing_adapter_only",
    )
    directory.mkdir(parents=True, exist_ok=True)
    adapter_path = directory / "adapter.safetensors"
    if adapter_path.exists():
        adapter_path.rename(directory / f"uncommitted_adapter_{time.time_ns()}.safetensors")
    adapter = legacy.old.components.save_adapter(
        SimpleNamespace(named_parameters=lambda: theta.items()), adapter_path
    )
    with adapter_path.open("rb") as stream:
        os.fsync(stream.fileno())
    point = p.record(
        "anchored_model_parameter_point",
        point_kind="cross_market_fixed_existing_step240",
        run=dict(seed=model["seed"], condition=model["condition"]),
        step=240,
        origin_id=saved["update_report"]["id"],
        origin_checkpoint=model,
        source_manifest_id=plan["source_manifest_id"],
        parameter_digest=legacy.old.gate.tensor_digest(theta),
        adapter=adapter,
        adapter_directory=str(directory.relative_to(c.RAW)),
        base_binding_id=plan["materials"]["assets"]["base_binding"]["id"],
    )
    c.write(path, point)
    return path, point


def prepare_cohorts(c, plan):
    tasks = prior.public_manifest(plan)["tasks"]
    cohorts = []
    for model in plan["models"]:
        point_path, point = prepare_point(c, plan, model)
        for mode in prior.MODES:
            key = f"{model['key']}_{mode}"
            directory = c.RAW / "cohorts" / key
            jobs = []
            for task in tasks:
                for repeat in (1, 2) if mode == "stochastic" else (0,):
                    jobs.append(
                        dict(
                            index=len(jobs),
                            task=task,
                            repeat=repeat,
                            seed=legacy.old.feedback.trajectory_seed(
                                "cross_market_20260926",
                                model["seed"],
                                1 if mode == "stochastic" else 2,
                                task["task_id"],
                                repeat,
                            ),
                        )
                    )
            registration = p.record(
                "direction_calibration_generation_registration",
                protocol_id=plan["id"],
                point_id=point["id"],
                source_manifest_id=plan["source_manifest_id"],
                seed=model["seed"],
                condition=model["condition"],
                phase=mode,
                stochastic=mode == "stochastic",
                jobs=jobs,
            )
            registration_path = directory / "registration.json"
            c.write(registration_path, registration)
            common = dict(
                phase=mode,
                seed=model["seed"],
                condition=model["condition"],
                point_path=str(point_path),
                point_id=point["id"],
                source_manifest_id=plan["source_manifest_id"],
                directory=str(directory),
                registration_path=str(registration_path),
            )
            count = plan["scheduling"]["generation_shards_" + mode]
            shards = []
            for index in range(count):
                job = p.record(
                    "cross_market_evaluation_work_unit",
                    protocol_id=plan["id"],
                    key=f"generate_{key}_{index}",
                    work_kind="generate",
                    jobs=jobs[index::count],
                    **common,
                )
                c.write(c.RAW / "jobspecs" / (job["key"] + ".json"), job)
                shards.append(job)
            score = p.record(
                "cross_market_evaluation_work_unit",
                protocol_id=plan["id"],
                key="score_" + key,
                work_kind="score",
                seal_path=str(c.RAW / "generation_seal.json"),
                **common,
            )
            c.write(c.RAW / "jobspecs" / (score["key"] + ".json"), score)
            cohorts.append(
                dict(
                    key=key,
                    common=common,
                    point=point,
                    registration=registration,
                    shards=shards,
                    score=score,
                )
            )
    return cohorts


def seal_cohort(c, plan, cohort):
    directory = Path(cohort["common"]["directory"])
    path = directory / "generation_manifest.json"
    if path.exists():
        return p.checked(p.read_json(path), "anchored_generation_manifest")
    if not all(
        (directory / "job_reports" / (job["key"] + ".json")).exists() for job in cohort["shards"]
    ):
        return None
    registration = cohort["registration"]
    jobs = registration["jobs"]
    records = prior._helpers(c).inventory(
        directory,
        {row["index"]: row for row in jobs},
        jobs,
        cohort["point"],
        stochastic=registration["stochastic"],
    )
    p.require(
        set(records) == set(range(len(jobs))), "cross_market_controller.exact_completed_cohort"
    )
    trajectories = [records[index] for index in range(len(jobs))]
    value = p.record(
        "anchored_generation_manifest",
        complete=True,
        stochastic=registration["stochastic"],
        point_id=cohort["point"]["id"],
        source_manifest_id=plan["source_manifest_id"],
        tasks=prior.public_manifest(plan)["tasks"],
        trajectories=trajectories,
        trajectory_count=len(trajectories),
        private_assessment_performed=False,
    )
    c.write(path, value)
    return value


def process_identity(pid):
    try:
        content = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return None if content[0] == "Z" else content[19]
    except (FileNotFoundError, ProcessLookupError):
        return None


def worker(root, raw, job_path, attempt):
    c = evaluation.Context(raw)
    plan = c.read_protocol(root)
    job = p.checked(p.read_json(job_path), "cross_market_evaluation_work_unit")
    p.require(
        job["protocol_id"] == plan["id"]
        and Path(job_path).resolve() == c.RAW / "jobspecs" / (job["key"] + ".json")
        and (
            c.RAW / "budget/intents/worker_start" / job["key"] / str(attempt) / "process.json"
        ).is_file(),
        "cross_market_controller.registered_precharged_worker",
    )
    directory = c.RAW / "control/attempts" / job["key"] / str(attempt)
    with c.locked(c.RAW / "control/job_locks" / (job["key"] + ".lock"), blocking=False):
        c.write(
            directory / "started.json",
            dict(
                pid=os.getpid(),
                process_identity=process_identity(os.getpid()),
                job_key=job["key"],
                attempt=attempt,
                at=p.now(),
            ),
        )
        try:
            if job["work_kind"] == "generate":
                c.capacity_boundary("generation", plan["scheduling"]["minimum_free_MiB"])
                report = evaluation.run_generation(
                    c, root, job, attempt, required=plan["scheduling"]["minimum_free_MiB"]
                )
            else:
                report = evaluation.run_scoring(c, root, job, attempt)
            outcome = dict(status="COMPLETE", report_id=report["id"], at=p.now())
        except (legacy.CapacityWait, legacy.torch.OutOfMemoryError, MemoryError) as error:
            outcome = dict(
                status="RESOURCE_RETRY",
                exception_type=type(error).__name__,
                message=str(error),
                at=p.now(),
            )
        except BaseException as error:
            traceback.print_exc()
            outcome = dict(
                status="FATAL", exception_type=type(error).__name__, message=str(error), at=p.now()
            )
        c.write(directory / "outcome.json", outcome)
        emit(
            "evaluation_worker_finished", key=job["key"], attempt=attempt, status=outcome["status"]
        )
        return (
            0
            if outcome["status"] == "COMPLETE"
            else 75
            if outcome["status"] == "RESOURCE_RETRY"
            else 1
        )


def attempts(c, job):
    rows = []
    for directory in sorted(
        (c.RAW / "control/attempts" / job["key"]).glob("*"), key=lambda path: int(path.name)
    ):
        reserved, started, launched, outcome = (
            read(directory / name)
            for name in ("reserved.json", "started.json", "launched.json", "outcome.json")
        )
        if reserved is None:
            continue
        process = started or launched
        alive = (
            process is not None and process_identity(process["pid"]) == process["process_identity"]
        )
        rows.append(
            dict(
                attempt=int(directory.name),
                alive=alive,
                outcome=outcome,
                process=process,
                reserved=reserved,
            )
        )
    return rows


def available_gpus(minimum):
    output = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=uuid,memory.free", "--format=csv,noheader,nounits"], text=True
    )
    return [
        row.split(",")[0].strip()
        for row in output.splitlines()
        if int(row.split(",")[1].strip()) >= minimum
    ]


def launch(c, root, job, attempt, gpu):
    c.reserve("worker_start", job["key"], attempt, "process")
    directory = c.RAW / "control/attempts" / job["key"] / str(attempt)
    c.write(directory / "reserved.json", dict(gpu=gpu, at=p.now()))
    environment = {
        **os.environ,
        "CUDA_VISIBLE_DEVICES": gpu or "",
        "PYTHONPATH": str(root / "trusted_data_synthesis/scripts")
        + ":"
        + str(root / "trusted_data_synthesis/src"),
        "OMP_NUM_THREADS": "8",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "8",
        "TOKENIZERS_PARALLELISM": "false",
    }
    command = [
        sys.executable,
        str(root / SCRIPT),
        "worker",
        "--root",
        str(root),
        "--raw",
        str(c.RAW),
        "--job",
        str(c.RAW / "jobspecs" / (job["key"] + ".json")),
        "--attempt",
        str(attempt),
    ]
    with (directory / "worker.log").open("ab") as log:
        process = subprocess.Popen(
            command,
            cwd=root,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    c.write(
        directory / "launched.json",
        dict(pid=process.pid, process_identity=process_identity(process.pid), at=p.now()),
    )
    emit("evaluation_worker_started", key=job["key"], attempt=attempt, pid=process.pid, gpu=gpu)


def complete_job(job):
    directory = Path(job["directory"])
    return (
        (directory / "job_reports" / (job["key"] + ".json")).exists()
        if job["work_kind"] == "generate"
        else (directory / "scoring_report.json").exists()
    )


def coordinate(root, raw=RAW):
    root = Path(root).resolve()
    c = evaluation.Context(raw)
    with c.locked(c.RAW / "control/coordinator.lock", blocking=False):
        plan = c.read_protocol(root)
        if (c.RAW / "complete.json").exists():
            completed = p.checked(
                p.read_json(c.RAW / "complete.json"), "cross_market_evaluation_completed"
            )
            p.require(
                completed["complete"] is True
                and completed["protocol_id"] == plan["id"]
                and completed["source_manifest_id"] == plan["source_manifest_id"]
                and completed["scored_sessions"] == 4860
                and len(completed["scoring_reports"]) == 18,
                "cross_market_controller.existing_completion_binding",
            )
            for registered in [*completed["scoring_reports"], completed["generation_seal"]]:
                p.require(
                    reference(registered["path"]) == registered,
                    "cross_market_controller.completed_artifact_unchanged",
                )
            return completed
        cohorts = prepare_cohorts(c, plan)
        generate_jobs = [job for cohort in cohorts for job in cohort["shards"]]
        score_jobs = [cohort["score"] for cohort in cohorts]
        all_jobs = generate_jobs + score_jobs
        while True:
            history = {job["key"]: attempts(c, job) for job in all_jobs}
            active = {key: rows[-1] for key, rows in history.items() if rows and rows[-1]["alive"]}
            sealed = [seal_cohort(c, plan, cohort) for cohort in cohorts]
            generation_active = any(job["key"] in active for job in generate_jobs)
            if (
                all(sealed)
                and not generation_active
                and not (c.RAW / "generation_seal.json").exists()
            ):
                rows = [
                    {
                        "key": cohort["key"],
                        **{
                            key: cohort["common"][key]
                            for key in ("seed", "condition", "phase", "point_id")
                        },
                        "generation_manifest_path": str(
                            Path(cohort["common"]["directory"]) / "generation_manifest.json"
                        ),
                        "generation_manifest_sha256": p.sha(
                            Path(cohort["common"]["directory"]) / "generation_manifest.json"
                        ),
                    }
                    for cohort in cohorts
                ]
                seal = p.record(
                    "calibration_generation_seal",
                    protocol_id=plan["id"],
                    source_manifest_id=plan["source_manifest_id"],
                    complete=True,
                    all_generation_workers_exited=True,
                    total_trajectories=4860,
                    cohorts=rows,
                    at=p.now(),
                )
                c.write(c.RAW / "generation_seal.json", seal)
                prior.require_generation_seal(
                    c, plan, prior.public_manifest(plan), str(c.RAW / "generation_seal.json")
                )
                emit("all4860_generation_sealed", seal_id=seal["id"])
            scores_allowed = (c.RAW / "generation_seal.json").exists()
            if scores_allowed and all(complete_job(job) for job in score_jobs) and not active:
                reports = [
                    reference(Path(job["directory"]) / "scoring_report.json") for job in score_jobs
                ]
                completion = p.record(
                    "cross_market_evaluation_completed",
                    complete=True,
                    protocol_id=plan["id"],
                    source_manifest_id=plan["source_manifest_id"],
                    scored_sessions=4860,
                    scoring_reports=reports,
                    generation_seal=reference(c.RAW / "generation_seal.json"),
                    physical_budget=c._budget_state(),
                    scientific_inference_pending_issuer_cluster_statistics=True,
                    at=p.now(),
                )
                c.write(c.RAW / "complete.json", completion)
                emit("cross_market_evaluation_complete", completion_id=completion["id"])
                return completion
            eligible = score_jobs if scores_allowed else generate_jobs
            running = [job for job in eligible if job["key"] in active]
            maximum = plan["scheduling"][
                "max_score_cohorts" if scores_allowed else "max_GPU_workers"
            ]
            gpus = [] if scores_allowed else available_gpus(plan["scheduling"]["minimum_free_MiB"])
            used = {row["reserved"]["gpu"] for row in active.values()}
            gpus = [gpu for gpu in gpus if gpu not in used]
            blocked = []
            for job in eligible:
                rows = history[job["key"]]
                if complete_job(job) or job["key"] in active:
                    continue
                if rows:
                    last = rows[-1]
                    outcome = last["outcome"]
                    if outcome is None and last["process"] is None:
                        blocked.append(
                            dict(key=job["key"], reason="unsettled_worker_exit_requires_review")
                        )
                        continue
                    if outcome is not None and outcome["status"] == "FATAL":
                        blocked.append(dict(key=job["key"], reason=outcome["message"]))
                        continue
                attempt = (rows[-1]["attempt"] if rows else 0) + 1
                cap = plan["scheduling"][
                    "scoring_attempts_per_cohort"
                    if scores_allowed
                    else "generation_attempts_per_shard"
                ]
                if attempt > cap:
                    blocked.append(dict(key=job["key"], reason="finite_attempt_budget_exhausted"))
                    continue
                if len(running) >= maximum or (not scores_allowed and not gpus):
                    continue
                launch(c, root, job, attempt, None if scores_allowed else gpus.pop(0))
                running.append(job)
            status = dict(
                at=p.now(),
                protocol_id=plan["id"],
                phase="SCORING" if scores_allowed else "GENERATION",
                generation_shards_complete=sum(complete_job(job) for job in generate_jobs),
                generation_shards=45,
                scoring_cohorts_complete=sum(complete_job(job) for job in score_jobs),
                active_workers=len(running),
                blocked=blocked,
            )
            c.write(c.RAW / "control/status.json", status, immutable=False)
            if blocked and not active and not running:
                emit("evaluation_blocked", blockers=blocked)
                return status
            time.sleep(plan["scheduling"]["polling_seconds"])


def start(root, raw=RAW):
    c = evaluation.Context(raw)
    c.read_protocol(root)
    path = c.RAW / "control/coordinator.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                str(Path(root) / SCRIPT),
                "coordinate",
                "--root",
                str(root),
                "--raw",
                str(raw),
            ],
            cwd=root,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    emit("evaluation_coordinator_started", pid=process.pid, log=str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "start", "coordinate", "worker", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--raw", type=Path, default=RAW)
    parser.add_argument("--panel-references", type=Path)
    parser.add_argument("--job", type=Path)
    parser.add_argument("--attempt", type=int)
    args = parser.parse_args()
    if args.action == "register":
        p.require(
            args.panel_references is not None, "cross_market_controller.panel_references_required"
        )
        register(args.root, args.panel_references, args.raw)
    elif args.action == "start":
        start(args.root, args.raw)
    elif args.action == "coordinate":
        coordinate(args.root, args.raw)
    elif args.action == "worker":
        return worker(args.root, args.raw, args.job, args.attempt)
    else:
        print(json.dumps(read(args.raw / "control/status.json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
