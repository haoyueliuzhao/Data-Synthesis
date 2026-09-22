"""Persistent DAG for frozen B shared-prefix training and sealed 720-task confirmation."""

# ruff: noqa: E501 -- explicit protocol provenance and stage contracts
import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from collections import Counter
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from types import SimpleNamespace

import fixed_kernel_B_common_20260922 as b
import fixed_kernel_B_confirm_views_20260922 as views
import fixed_kernel_B_confirmation_statistics_20260922 as statistics
import fixed_kernel_B_generation_20260922 as generation
import fixed_kernel_B_outer_worker_20260922 as outer
import fixed_kernel_B_scoring_20260922 as scoring
import fixed_kernel_B_training_worker_20260922 as training
import run_fixed_kernel_delayed_C_migration_20260921 as identity

p, old = b.p, b.old
SCRIPT = "trusted_data_synthesis/scripts/run_fixed_kernel_B_confirmation_20260922.py"
PUBLIC = b.d.inputs.BASE + "/delayed_C_B_confirmation_20260922"
KINDS = ("train", "outer_prepare", "outer_replay", "generate", "score")


def _read(path):
    return p.read_json(path) if path.exists() else None


def implementation(root, plan):
    path = b.RAW / "implementation.json"
    if path.exists():
        value = p.checked(p.read_json(path), "B_execution_implementation")
        p.require(value["protocol_id"] == plan["id"], "B.execution_protocol")
        for name, expected in value["sources"].items():
            p.require(p.sha(root / name) == expected, "B.execution_source_unchanged")
        return value
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    names = [SCRIPT, identity.SCRIPT]
    sources = {}
    for name in names:
        payload = (root / name).read_bytes()
        p.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "B.execution_committed",
        )
        sources[name] = p.sha(payload)
    value = p.record(
        "B_execution_implementation",
        protocol_id=plan["id"],
        stages=list(KINDS),
        sources=sources,
        code_commit=head,
        at=p.now(),
    )
    b.write(path, value)
    return value


def spec(plan, key, kind, **fields):
    value = p.record(
        "B_registered_work_unit", protocol_id=plan["id"], key=key, work_kind=kind, **fields
    )
    b.write(b.RAW / "jobspecs" / (key + ".json"), value)
    return value


def cohort(plan, phase, model, point_path, tasks, source_manifest_id):
    point = p.checked(p.read_json(point_path), "anchored_model_parameter_point")
    stochastic = phase == "feedback"
    directory = b.RAW / "generation" / phase / model["key"]
    jobs = []
    for row in tasks:
        for repeat in (1, 2) if stochastic else (0,):
            jobs.append(
                dict(
                    index=len(jobs),
                    task=row,
                    repeat=repeat,
                    seed=old.feedback.trajectory_seed(
                        "B", model["seed"], 1 if stochastic else 2, row["task_id"], repeat
                    ),
                )
            )
    registration = p.record(
        "B_generation_registration",
        protocol_id=plan["id"],
        point_id=point["id"],
        source_manifest_id=source_manifest_id,
        seed=model["seed"],
        condition=model["condition"],
        stochastic=stochastic,
        jobs=jobs,
    )
    b.write(directory / "registration.json", registration)
    count = 6 if stochastic else 16
    shards = []
    for shard in range(count):
        key = f"{phase}_{model['key']}_{shard:02d}"
        shards.append(
            spec(
                plan,
                key,
                "generate",
                phase=phase,
                seed=model["seed"],
                condition=model["condition"],
                point_path=str(point_path),
                point_id=point["id"],
                source_manifest_id=source_manifest_id,
                directory=str(directory),
                registration_path=str(directory / "registration.json"),
                jobs=jobs[shard::count],
            )
        )
    return directory, point, registration, shards


def seal_cohort(plan, directory, point, registration, shards):
    path = directory / "generation_manifest.json"
    if path.exists():
        value = p.checked(p.read_json(path), "anchored_generation_manifest")
        p.require(
            value["point_id"] == point["id"]
            and value["source_manifest_id"] == registration["source_manifest_id"]
            and value["complete"],
            "B.reused_complete_generation_manifest",
        )
        return value
    if not all((directory / "job_reports" / (job["key"] + ".json")).exists() for job in shards):
        return None
    jobs = registration["jobs"]
    records = generation.inventory(
        directory,
        {job["index"]: job for job in jobs},
        jobs,
        point,
        stochastic=registration["stochastic"],
    )
    p.require(set(records) == set(range(len(jobs))), "B.all_registered_trajectories_sealed")
    ordered = [records[index] for index in range(len(jobs))]
    tasks = (
        [job["task"] for job in jobs[::2]]
        if registration["stochastic"]
        else [job["task"] for job in jobs]
    )
    manifest = p.record(
        "anchored_generation_manifest",
        protocol_id=plan["id"],
        complete=True,
        point_id=point["id"],
        stochastic=registration["stochastic"],
        tasks=tasks,
        source_manifest_id=registration["source_manifest_id"],
        trajectories=ordered,
        total_generate_calls=sum(row["actual_generate_calls"] for row in ordered),
        total_generated_tokens=sum(row["generated_tokens"] for row in ordered),
        planned_sampling_shards=len(shards),
        successful_sampling_attempt_directories=sorted(
            {str(Path(row["path"]).parent.parent) for row in ordered}
        ),
        sealed_before_private_scoring=True,
        at=p.now(),
    )
    p.require(manifest["total_generate_calls"] <= len(jobs) * 32, "B.sealed_generation_call_budget")
    b.write(path, manifest)
    return manifest


def final_point(plan, model, source_manifest_id):
    directory = b.RAW / "points" / model["key"]
    if (directory / "point.json").exists():
        point = p.checked(p.read_json(directory / "point.json"), "anchored_model_parameter_point")
        p.require(
            point["source_manifest_id"] == source_manifest_id
            and point["step"] == 400
            and point["run"] == model,
            "B.fixed_final_point",
        )
        return directory / "point.json"
    report = p.checked(
        p.read_json(b.RAW / "jobs" / model["key"] / "report.json"), "B_training_job_report"
    )
    p.require(
        report["complete"]
        and report["completed_updates"] == 400
        and report["plan_id"] == plan["id"],
        "B.only_final400_model",
    )
    saved = b.load_training(Path(report["checkpoint_path"]), plan["id"], [model["key"]], step=400)
    theta = {
        name.removeprefix("theta/"): value
        for name, value in saved["state"].items()
        if name.startswith("theta/")
    }
    # Serialization only: no model forward, optimizer update, or GPU is needed here.
    adapter_model = SimpleNamespace(named_parameters=lambda: theta.items())
    directory.mkdir(parents=True, exist_ok=True)
    adapter_path = directory / "adapter.safetensors"
    if adapter_path.exists():
        adapter_path.rename(
            directory / ("uncommitted_adapter_" + str(time.time_ns()) + ".safetensors")
        )
    adapter = old.components.save_adapter(adapter_model, adapter_path)
    with adapter_path.open("rb") as stream:
        os.fsync(stream.fileno())
    point = p.record(
        "anchored_model_parameter_point",
        point_kind="B_sole_step400_confirmation",
        run=model,
        step=400,
        origin_id=saved["update_report"]["id"],
        source_manifest_id=source_manifest_id,
        parameter_digest=old.gate.tensor_digest(theta),
        adapter=adapter,
        adapter_directory=str(directory.relative_to(b.RAW)),
        base_binding_id=plan["materials"]["assets"]["base_binding"]["id"],
        training_report_id=report["id"],
        shared_prefix_binding_id=p.checked(
            p.read_json(b.RAW / "jobs" / model["key"] / "branch_binding.json"),
            "B_shared_prefix_branch_binding",
        )["id"],
    )
    b.write(directory / "point.json", point)
    return directory / "point.json"


def graph(plan, active):
    """Only frozen dependencies make work eligible; no score-dependent selection."""
    ready = []
    models = [
        dict(key=job["key"], seed=job["seed"], pool="B", condition=job["condition"])
        for job in plan["training_jobs"]
        if job["condition"] != "prefix"
    ]
    for job in plan["training_jobs"]:
        if (b.RAW / "jobs" / job["key"] / "report.json").exists():
            continue
        if (
            job["condition"] != "prefix"
            and not (b.RAW / "jobs" / job["prefix_key"] / "report.json").exists()
        ):
            continue
        if (
            job["condition"] == "delayed_c"
            and not (b.RAW / "outer" / job["key"] / "report.json").exists()
        ):
            continue
        ready.append(spec(plan, job["key"], "train", seed=job["seed"], condition=job["condition"]))
    for seed in plan["seeds"]:
        key = f"B_delayed_c_{seed}"
        model = dict(key=key, seed=seed, pool="B", condition="delayed_c")
        directory = b.RAW / "outer" / key
        if (
            not (b.RAW / "jobs" / f"B_prefix_{seed}" / "report.json").exists()
            or (directory / "report.json").exists()
        ):
            continue
        if not (directory / "prepare_report.json").exists():
            ready.append(spec(plan, "prepare_" + key, "outer_prepare", seed=seed, model_key=key))
            continue
        gen_dir, point, registration, shards = cohort(
            plan,
            "feedback",
            model,
            directory / "virtual_point/point.json",
            plan["dev_tasks"],
            plan["materials"]["source_manifest_id"],
        )
        for job in shards:
            if not (gen_dir / "job_reports" / (job["key"] + ".json")).exists():
                ready.append(job)
        manifest = seal_cohort(plan, gen_dir, point, registration, shards)
        if manifest is None:
            continue
        if not (gen_dir / "scoring_report.json").exists():
            ready.append(
                spec(
                    plan,
                    "score_feedback_" + key,
                    "score",
                    phase="feedback",
                    directory=str(gen_dir),
                    point_id=point["id"],
                    source_manifest_id=point["source_manifest_id"],
                    seed=seed,
                    condition="delayed_c",
                )
            )
        else:
            ready.append(spec(plan, "replay_" + key, "outer_replay", seed=seed, model_key=key))
    if not all((b.RAW / "jobs" / model["key"] / "report.json").exists() for model in models):
        return ready
    view_manifest = p.checked(
        p.read_json(b.RAW / "confirm_views/manifest.json"), "source_view_manifest_v2"
    )
    p.require(
        p.read_json(b.RAW / "confirm_views/admission.json")["passed"], "B.confirm_input_admitted"
    )
    sealed = []
    for model in models:
        point_path = final_point(plan, model, view_manifest["id"])
        directory, point, registration, shards = cohort(
            plan, "confirm", model, point_path, view_manifest["tasks"], view_manifest["id"]
        )
        for job in shards:
            if not (directory / "job_reports" / (job["key"] + ".json")).exists():
                ready.append(job)
        manifest = seal_cohort(plan, directory, point, registration, shards)
        if manifest is not None:
            path = directory / "generation_manifest.json"
            sealed.append(
                dict(
                    **model,
                    point_id=point["id"],
                    generation_manifest_path=str(path),
                    generation_manifest_sha256=p.sha(path),
                )
            )
    seal_path = b.RAW / "confirmation_generation_seal.json"
    if len(sealed) == 6 and not any(row["kind"] == "generate" for row in active.values()):
        if not seal_path.exists():
            b.write(
                seal_path,
                p.record(
                    "B_confirm_generation_seal",
                    protocol_id=plan["id"],
                    source_manifest_id=view_manifest["id"],
                    complete=True,
                    all_generation_workers_exited=True,
                    total_trajectories=4320,
                    models=sealed,
                    at=p.now(),
                ),
            )
        views.require_generation_seal(Path(plan["repository_root"]), plan, view_manifest, seal_path)
        for model in models:
            directory = b.RAW / "generation/confirm" / model["key"]
            if not (directory / "scoring_report.json").exists():
                point = p.read_json(b.RAW / "points" / model["key"] / "point.json")
                ready.append(
                    spec(
                        plan,
                        "score_confirm_" + model["key"],
                        "score",
                        phase="confirm",
                        directory=str(directory),
                        point_id=point["id"],
                        source_manifest_id=view_manifest["id"],
                        seed=model["seed"],
                        condition=model["condition"],
                        seal_path=str(seal_path),
                    )
                )
    return ready


def phase(job):
    return {
        "train": "SFT",
        "outer_prepare": "population",
        "outer_replay": "feedback",
        "generate": "generation",
        "score": "CPU",
    }[job["work_kind"]]


def admit_gpu(required):
    result = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=index,uuid,memory.free", "--format=csv,noheader,nounits"],
        text=True,
        timeout=12,
    )
    for number, uuid, free in sorted(
        [line.split(",") for line in result.splitlines()], key=lambda row: -int(row[2])
    ):
        if int(free) < required + 1024:
            continue
        path = b.RAW / "gpu_leases" / (uuid.strip() + ".lock")
        path.parent.mkdir(parents=True, exist_ok=True)
        lease = path.open("a")
        try:
            import fcntl

            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lease.close()
            continue
        return dict(index=int(number), uuid=uuid.strip(), free_MiB=int(free)), lease
    return None, None


def _spawn(root, mode, log, *, args=(), gpu=None, lease=None):
    log.parent.mkdir(parents=True, exist_ok=True)
    env = dict(
        os.environ,
        CUDA_VISIBLE_DEVICES="" if gpu is None else gpu["uuid"],
        CUBLAS_WORKSPACE_CONFIG=":4096:8",
        TOKENIZERS_PARALLELISM="false",
        OMP_NUM_THREADS="2",
        OPENBLAS_NUM_THREADS="2",
        MKL_NUM_THREADS="2",
    )
    with log.open("ab") as stream:
        return subprocess.Popen(
            [sys.executable, str(root / SCRIPT), "--root", str(root), "--mode", mode, *args],
            cwd=root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            pass_fds=() if lease is None else (lease.fileno(),),
        )


def worker(root, key, attempt, required):
    plan = b.read_protocol(root)
    implementation(root, plan)
    job = p.checked(p.read_json(b.RAW / "jobspecs" / (key + ".json")), "B_registered_work_unit")
    p.require(job["protocol_id"] == plan["id"] and job["key"] == key, "B.worker_spec_binding")
    with b.locked(b.RAW / "job_locks" / (key + ".lock"), blocking=False):
        b.write(
            b.RAW / "worker_identities" / key / f"{attempt:04d}.json",
            dict(
                identity=identity.identity(os.getpid()),
                key=key,
                kind=job["work_kind"],
                attempt=attempt,
                required_MiB=required,
                at=p.now(),
            ),
        )
        result = dict(
            protocol_id=plan["id"],
            key=key,
            kind=job["work_kind"],
            attempt=attempt,
            started_at=p.now(),
            resource_retry_allowed=False,
        )
        try:
            if job["work_kind"] == "train":
                value = training.run(root, key, attempt, required)
            elif job["work_kind"] == "outer_prepare":
                value = outer.prepare(root, job["seed"], attempt, required)
            elif job["work_kind"] == "outer_replay":
                value = outer.replay(root, job["seed"], attempt, required)
            elif job["work_kind"] == "generate":
                value = generation.run(root, job, attempt, required)
            else:
                value = scoring.run(root, job, attempt)
            result.update(returncode=0, completed_record_id=value["id"])
        except b.CapacityWait as error:
            result.update(returncode=43, reason=str(error))
        except Exception as error:
            retry = isinstance(error, (b.torch.OutOfMemoryError, MemoryError, BrokenProcessPool))
            result.update(
                returncode=42 if retry else 1,
                resource_retry_allowed=retry,
                error=repr(error),
                traceback=traceback.format_exc(),
            )
        result["finished_at"] = p.now()
        b.write(b.RAW / "results" / key / f"{attempt:04d}.json", result)
        return result["returncode"]


def publish_completed(root, report):
    """Retry publication only; never repeat a completed scientific computation."""
    receipt = b.RAW / "publication.json"
    previous = _read(receipt)
    if previous and previous["status"] == "PUBLISHED":
        p.require(previous["report_id"] == report["id"], "B.published_report_identity")
        return True
    attempt = 1 if previous is None else previous["attempt"] + 1
    if previous and time.time() < previous.get("not_before", 0):
        return False
    p.require(attempt <= 8, "B.publication_retry_cap_no_scientific_retry")
    path = root / PUBLIC / "public/completed_B_main_confirmation_20260922.json"
    doc = root / "trusted_data_synthesis/docs/B_confirmation_completed_20260922.md"
    body = (
        "# B 材料主确认完成\n\n"
        "Static 与 Delayed-C 共用各 seed 的真实 step200 参数、Adam 和 RNG；"
        "六模型均有效400步。720确认题不参与反馈或选择。预登记主判据为 CIK 配对区间下界严格大于0；"
        "跨零只表示未确认，不表示等效。固定三个训练种子的来源聚类区间不覆盖全部训练随机性。\n\n"
        "完整逐项分析及资源账本保存在已注册数据盘目录，公开记录仅含聚合数据。\n\n```json\n"
        + json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n```\n"
    )
    try:
        if path.exists():
            p.require(p.read_json(path) == report, "B.unchanged_completed_public_report")
        else:
            p.write_once(path, report)
        if doc.exists():
            p.require(doc.read_text() == body, "B.unchanged_completed_document")
        else:
            doc.parent.mkdir(parents=True, exist_ok=True)
            with doc.open("x") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
        paths = [str(path.relative_to(root)), str(doc.relative_to(root))]
        subprocess.run(["git", "add", "--sparse", "-f", "--", *paths], cwd=root, check=True)
        changed = subprocess.run(["git", "diff", "--cached", "--quiet", "--", *paths], cwd=root)
        p.require(changed.returncode in (0, 1), "B.publication_git_diff")
        if changed.returncode == 1:
            subprocess.run(
                [
                    "git",
                    "commit",
                    "--only",
                    "-m",
                    "Publish frozen B main confirmation result",
                    "--",
                    *paths,
                ],
                cwd=root,
                check=True,
            )
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        subprocess.run(
            ["git", "-c", "http.proxy=", "push", "origin", "HEAD:main"],
            cwd=root,
            check=True,
            timeout=180,
        )
        b.write(
            receipt,
            dict(
                status="PUBLISHED",
                report_id=report["id"],
                commit=commit,
                attempt=attempt,
                at=p.now(),
            ),
            immutable=False,
        )
        return True
    except Exception as error:
        b.write(
            receipt,
            dict(
                status="PUBLICATION_PENDING_NO_SCIENTIFIC_RETRY",
                report_id=report["id"],
                attempt=attempt,
                error=repr(error),
                not_before=time.time() + 300,
                at=p.now(),
            ),
            immutable=False,
        )
        return False


def finish(root, plan):
    model_jobs = [row for row in plan["training_jobs"] if row["condition"] != "prefix"]
    if not all(
        (b.RAW / "generation/confirm" / row["key"] / "scoring_report.json").exists()
        for row in model_jobs
    ):
        return False
    output = b.RAW / "report.json"
    if output.exists():
        report = p.checked(p.read_json(output), "B_confirm_completed_study")
        p.require(report["protocol_id"] == plan["id"], "B.completed_protocol_identity")
        if not publish_completed(root, report):
            return False
        b.write(b.RAW / "complete.json", report)
        return True
    view_manifest = p.checked(
        p.read_json(b.RAW / "confirm_views/manifest.json"), "source_view_manifest_v2"
    )
    seal_path = b.RAW / "confirmation_generation_seal.json"
    views.require_generation_seal(root, plan, view_manifest, seal_path)
    registry = [
        dict(task_id=row["task_id"], group=row["group"], cik=row["source_cluster"])
        for row in plan["confirm_registry"]
    ]
    values, models = [], []
    for model in model_jobs:
        directory = b.RAW / "generation/confirm" / model["key"]
        point = p.checked(
            p.read_json(b.RAW / "points" / model["key"] / "point.json"),
            "anchored_model_parameter_point",
        )
        p.require(
            point["run"]["key"] == model["key"]
            and point["run"]["seed"] == model["seed"]
            and point["run"]["condition"] == model["condition"]
            and point["step"] == 400,
            "B.final_score_model_identity",
        )
        score_job = dict(
            phase="confirm",
            point_id=point["id"],
            source_manifest_id=view_manifest["id"],
            seed=model["seed"],
            condition=model["condition"],
        )
        frozen = scoring._sealed_cohort(plan, score_job, directory)
        score = p.checked(
            p.read_json(directory / "scoring_report.json"),
            "anchored_independent_scoring",
        )
        scoring._validate_report(score, frozen, score_job)
        p.require(
            score["complete"] and score["denominator"] == 720,
            "B.complete_confirmation_before_analysis",
        )
        values.extend(
            dict(
                task_id=row["task_id"],
                seed=model["seed"],
                arm=model["condition"],
                Q=row["Q"],
                group=row["group"],
            )
            for row in score["scores"]
        )
        models.append(
            dict(
                key=model["key"],
                seed=model["seed"],
                condition=model["condition"],
                qualified=score["qualified"],
                denominator=720,
                scoring_report_id=score["id"],
            )
        )
    analysis_path = b.RAW / "confirmation_analysis.json"
    if analysis_path.exists():
        analysis = p.read_json(analysis_path)
    else:
        analysis = statistics.analyze_confirmation(registry, values)
        b.write(analysis_path, analysis)
    budget = p.read_json(b.RAW / "budget/state.json")
    report = p.record(
        "B_confirm_completed_study",
        protocol_id=plan["id"],
        status="COMPLETE_B_MAIN_CONFIRMATION"
        if analysis["status"] == "COMPLETE"
        else "COMPLETE_SCORES_INTERVAL_INCOMPLETE",
        primary="B Delayed-C minus B Static",
        models=models,
        point_estimate=analysis["point_estimate"],
        ci95=analysis["ci95"],
        positive_effect_confirmed=analysis["positive_effect_confirmed"],
        effective_model_updates=2400,
        planned_physical_updates_base=1800,
        reserved_physical_optimizer_attempts=budget["counts"].get("optimizer", 0),
        attempted_generate_call_upper_bound=budget["counts"].get("generate_call", 0),
        new_feedback_sessions=1080,
        confirmation_sessions=4320,
        B_final_dev_sessions=0,
        A_auxiliary_sessions=0,
        no_candidate_switch=True,
        fixed_seed_source_cluster_interval_not_all_training_randomness=True,
        at=p.now(),
    )
    b.write(output, report)
    if not publish_completed(root, report):
        return False
    b.write(b.RAW / "complete.json", report)
    return True


def coordinate(root):
    plan = b.read_protocol(root)
    implementation(root, plan)
    p.require(
        p.read_json(b.RAW / "confirm_views/admission.json")["passed"],
        "B.public_confirm_interface_ready_before_training",
    )
    state_path = b.RAW / "control/state.json"
    with b.locked(b.RAW / "controller.lock", blocking=False):
        b.write(
            b.RAW / "control/controller_identity.json",
            identity.identity(os.getpid()),
            immutable=False,
        )
        state = _read(state_path) or dict(jobs={}, active={})
        children = {}
        for path in sorted((b.RAW / "worker_identities").glob("*/*.json")):
            row = p.read_json(path)
            status = state["jobs"].setdefault(
                row["key"], dict(attempt=0, failures=0, not_before=0, stopped=None)
            )
            status["attempt"] = max(status["attempt"], row["attempt"])
            if identity.same_process(row["identity"]):
                existing = state["active"].get(row["key"])
                p.require(
                    existing is None
                    or not identity.same_process(existing["identity"])
                    or existing["identity"]["pid"] == row["identity"]["pid"],
                    "B.one_live_worker_per_unit",
                )
                state["active"][row["key"]] = row
        while True:
            for key, row in list(state["active"].items()):
                if identity.same_process(row["identity"]):
                    continue
                child = children.pop(key, None)
                exit_code = child.wait(timeout=3) if child is not None else None
                del state["active"][key]
                status = state["jobs"][key]
                result = _read(b.RAW / "results" / key / f"{row['attempt']:04d}.json")
                if result is None and exit_code not in (None, -9, -15):
                    result = dict(
                        returncode=1,
                        reason="unclassified_worker_exit_requires_review",
                        process_returncode=exit_code,
                        at=p.now(),
                    )
                if result is None or result.get("returncode") in (42, 43):
                    if result and result["returncode"] == 42:
                        status["failures"] += 1
                    status["not_before"] = time.time() + min(
                        900, 60 * 2 ** min(status["failures"], 4)
                    )
                    if result is None:
                        b.write(
                            b.RAW / "resource_exits" / f"{key}_{row['attempt']:04d}.json",
                            dict(
                                outcome="process_disappeared_without_failure_record",
                                inference_not_numeric_pass=True,
                                process_returncode=exit_code,
                                at=p.now(),
                            ),
                        )
                elif result["returncode"] != 0:
                    status["stopped"] = result
                b.write(state_path, state, immutable=False)
            has_failure = any(row["stopped"] for row in state["jobs"].values())
            if has_failure:
                b.write(
                    b.RAW / "needs_attention.json",
                    dict(jobs=state["jobs"], at=p.now()),
                    immutable=False,
                )
                if not state["active"]:
                    return 1
                # Let already running independent units save and exit; admit no
                # successor after an identity/numeric error or exhausted budget.
                time.sleep(20)
                continue
            if not state["active"] and finish(root, plan):
                return 0
            ready = graph(plan, state["active"])
            counts = Counter(row["kind"] for row in state["active"].values())
            # Training/prefix work is prioritized, while free GPUs serve fixed inference shards.
            priority = {
                "train": 0,
                "outer_prepare": 1,
                "outer_replay": 1,
                "score": 2,
                "generate": 3,
            }
            for job in sorted(ready, key=lambda row: (priority[row["work_kind"]], row["key"])):
                key, kind = job["key"], job["work_kind"]
                status = state["jobs"].setdefault(
                    key, dict(attempt=0, failures=0, not_before=0, stopped=None)
                )
                if (
                    key in state["active"]
                    or status["stopped"]
                    or time.time() < status["not_before"]
                ):
                    continue
                if status["attempt"] >= plan["physical_budget"]["maximum_attempts_per_job"]:
                    status["stopped"] = dict(
                        reason="registered_worker_attempt_cap_exhausted", at=p.now()
                    )
                    continue
                if kind in ("outer_prepare", "outer_replay") and counts[kind] >= 1:
                    continue
                if kind == "score" and counts[kind] >= 2:
                    continue
                gpu, lease = None, None
                required = (
                    0
                    if kind == "score"
                    else min(77824, b.FLOORS[phase(job)] + 4096 * status["failures"])
                )
                if kind != "score":
                    if sum(number for name, number in counts.items() if name != "score") >= 8:
                        continue
                    if (
                        old.host_memory()["MemAvailable_bytes"]
                        < (128 if kind.startswith("outer") else 64) * 2**30
                    ):
                        continue
                    try:
                        gpu, lease = admit_gpu(required)
                    except (subprocess.SubprocessError, OSError) as error:
                        b.emit(dict(event="B_GPU_query_wait", error=repr(error)))
                        continue
                    if gpu is None:
                        continue
                status["attempt"] += 1
                number = status["attempt"]
                b.write(state_path, state, immutable=False)
                try:
                    b.reserve("worker_start", key, number, 0)
                    child = _spawn(
                        root,
                        "worker",
                        b.RAW / "logs" / f"{key}_{number:04d}.log",
                        args=(
                            "--job",
                            key,
                            "--attempt",
                            str(number),
                            "--required-MiB",
                            str(required),
                        ),
                        gpu=gpu,
                        lease=lease,
                    )
                except Exception as error:
                    status["stopped"] = dict(reason=repr(error), at=p.now())
                    b.write(state_path, state, immutable=False)
                    continue
                finally:
                    if lease is not None:
                        lease.close()
                active = dict(
                    identity=identity.identity(child.pid),
                    key=key,
                    kind=kind,
                    attempt=number,
                    gpu=gpu,
                    required_MiB=required,
                )
                state["active"][key] = active
                children[key] = child
                counts[kind] += 1
                b.write(state_path, state, immutable=False)
                b.emit(
                    dict(
                        event="B_worker_launched",
                        key=key,
                        kind=kind,
                        attempt=number,
                        pid=child.pid,
                        gpu=gpu,
                    )
                )
            progress = {
                job["key"]: max(
                    [
                        int(path.stem)
                        for path in (b.RAW / "jobs" / job["key"] / "updates").glob("*.pt")
                    ],
                    default=job["start"],
                )
                for job in plan["training_jobs"]
            }
            b.write(
                b.RAW / "heartbeat.json",
                dict(
                    protocol_id=plan["id"],
                    at=p.now(),
                    pid=os.getpid(),
                    training_steps=progress,
                    active=state["active"],
                    jobs=state["jobs"],
                    any_scientific_failure=any(row["stopped"] for row in state["jobs"].values()),
                ),
                immutable=False,
            )
            b.write(state_path, state, immutable=False)
            if (
                not state["active"]
                and any(row["stopped"] for row in state["jobs"].values())
                and not any(not state["jobs"].get(row["key"], {}).get("stopped") for row in ready)
            ):
                b.write(
                    b.RAW / "needs_attention.json",
                    dict(jobs=state["jobs"], at=p.now()),
                    immutable=False,
                )
                return 1
            time.sleep(20)


def watch(root):
    with b.locked(b.RAW / "watchdog.lock", blocking=False):
        b.write(
            b.RAW / "control/watchdog_identity.json",
            identity.identity(os.getpid()),
            immutable=False,
        )
        while True:
            child = _spawn(root, "coordinate", b.RAW / "coordinator.log")
            code = child.wait()
            b.write(
                b.RAW / "watchdog_status.json",
                dict(returncode=code, finished_at=p.now()),
                immutable=False,
            )
            if code not in (-9, -15, 42):
                return code
            time.sleep(30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--mode", choices=("prepare_views", "start", "watch", "coordinate", "worker"), required=True
    )
    parser.add_argument("--job")
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--required-MiB", type=int, default=32768)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "prepare_views":
        manifest, admission = views.prepare_views(root, b.read_protocol(root))
        b.emit(
            dict(
                event="B_confirm_public_views_prepared",
                manifest_id=manifest["id"],
                passed=admission["passed"],
                compiled=len(manifest["tasks"]),
                failed=len(admission["failures"]),
            )
        )
        return 0 if admission["passed"] else 1
    if args.mode == "start":
        plan = b.read_protocol(root)
        implementation(root, plan)
        p.require(
            p.read_json(b.RAW / "confirm_views/admission.json")["passed"],
            "B.no_GPU_work_before_public_input_admission",
        )
        old_watch = _read(b.RAW / "control/watchdog_identity.json")
        if old_watch and identity.same_process(old_watch):
            b.emit(dict(event="B_already_running", pid=old_watch["pid"]))
            return 0
        child = _spawn(root, "watch", b.RAW / "watchdog.log")
        b.write(
            b.RAW / "control/watchdog_identity.json", identity.identity(child.pid), immutable=False
        )
        b.emit(dict(event="B_supervision_started", pid=child.pid))
        return 0
    if args.mode == "watch":
        return watch(root)
    if args.mode == "worker":
        try:
            return worker(root, args.job, args.attempt, args.required_MiB)
        except Exception as error:
            # Fail closed even when protocol/source/lock checks fail before the
            # stage body's handler; these are not silent resource preemptions.
            b.write(
                b.RAW / "results" / args.job / f"{args.attempt:04d}.json",
                dict(
                    key=args.job,
                    attempt=args.attempt,
                    returncode=1,
                    resource_retry_allowed=False,
                    error=repr(error),
                    traceback=traceback.format_exc(),
                    finished_at=p.now(),
                ),
            )
            return 1
    try:
        return coordinate(root)
    except (MemoryError, subprocess.TimeoutExpired) as error:
        b.emit(dict(event="B_controller_resource_restart", error=repr(error)))
        return 42
    except Exception as error:
        b.write(
            b.RAW / "controller_failure.json",
            dict(error=repr(error), traceback=traceback.format_exc(), at=p.now()),
            immutable=False,
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
