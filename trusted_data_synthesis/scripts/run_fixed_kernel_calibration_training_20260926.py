"""Separately register and supervise the three fixed negative-direction epochs.

The new evaluation panel remains NOT_READY. This controller cannot generate or
score anything, acquire sources, change a direction, or train either reused arm.
"""

# ruff: noqa: E501 -- explicit finite, durable and independent execution contracts
import argparse
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

import fixed_kernel_direction_calibration_common_20260926 as stage1
import fixed_kernel_direction_calibration_materials_20260926 as materials
import fixed_kernel_direction_calibration_training_20260926 as worker
import run_fixed_kernel_delayed_C_migration_20260921 as identity

b, p, s, old, torch = stage1.b, stage1.p, stage1.s, stage1.old, stage1.torch
CapacityWait = b.CapacityWait
capacity_boundary, locked, emit = b.capacity_boundary, b.locked, b.emit
RAW = stage1.RAW / "training_stage_20260926"
SCRIPT = "trusted_data_synthesis/scripts/run_fixed_kernel_calibration_training_20260926.py"
PUBLIC = "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/direction_calibration_20260926/public/training_completed.json"
PROTOCOL = "B_direction_calibration_training_protocol"
COMPLETED = "B_direction_calibration_training_completed"
SEEDS = [11, 29, 47]
_verified_final = {}


def read(path):
    path = Path(path)
    return p.read_json(path) if path.exists() else None


def write(path, value, immutable=True):
    path = Path(path)
    p.require(
        path.resolve().is_relative_to(RAW.resolve()) and ".." not in path.parts,
        "negative_training.confined_new_artifact",
    )
    b.durable.write(path, value, immutable=immutable)
    return value


def input_ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=p.sha(path))


def _admission(value, expected_id):
    value = p.checked(value, "direction_calibration_material_admission")
    p.require(
        value["passed"] is True and value["id"] == expected_id and value["seeds"] == SEEDS,
        "negative_training.previously_admitted_all_seeds",
    )
    references = {(row["job_key"], row["step"]) for row in value["reusable_refs"]}
    expected = {(f"B_prefix_{seed}", 200) for seed in SEEDS} | {
        (f"B_{arm}_{seed}", 240) for seed in SEEDS for arm in ("static", "delayed_c")
    }
    p.require(
        references == expected and len(value["reusable_refs"]) == 9,
        "negative_training.exact_three_prefix_and_six_reused_points",
    )
    p.require(
        value["accounting"]["new_negative_tail_updates"] == 120
        and value["accounting"]["newly_required_sequence_tokens"] == 53435082
        and value["accounting"]["newly_required_target_tokens"] == 2946264,
        "negative_training.fixed_epoch_accounting",
    )
    for seed in SEEDS:
        worker._registered(dict(seeds=SEEDS, materials_admission=value), seed)
    return value


def read_protocol(root):
    root = Path(root)
    plan = p.checked(p.read_json(RAW / "protocol.json"), PROTOCOL)
    previous = stage1.read_protocol(root)
    p.require(
        plan["frozen"] is True
        and plan["seeds"] == SEEDS
        and plan["jobs"] == [dict(key=f"B_negative_{seed}", seed=seed) for seed in SEEDS]
        and plan["condition"] == "negative"
        and plan["start"] == 200
        and plan["stop"] == 240
        and plan["per_seed_committed_updates"] == 40
        and plan["new_positive_or_static_updates"] == 0
        and plan["reused_step240_models"] == 6
        and plan["no_directional_sign_gate"] is True
        and plan["no_seed_or_task_selection"] is True
        and plan["parent_B_protocol_id"] == previous["parent_B_protocol_id"]
        and plan["stage1_protocol_id"] == previous["id"]
        and plan["panel_status"] == "NOT_READY"
        and plan["committed_optimizer_updates"] == 120
        and plan["physical_budget"]
        == dict(
            optimizer=144,
            worker_start=24,
            generate_call=0,
            score_case=0,
            feedback=0,
            population=0,
            probe=0,
        )
        and plan["per_seed_optimizer_attempt_cap"] == 48
        and plan["maximum_attempts_per_job"] == 8
        and plan["auto_evaluation"] is False,
        "negative_training.frozen_training_only_scope",
    )
    for name, expected in plan["sources"].items():
        p.require(p.sha(root / name) == expected, "negative_training.frozen_source:" + name)
    for name, reference in plan["registration_inputs"].items():
        path = Path(reference["path"])
        p.require(
            path.is_relative_to(stage1.RAW)
            and path.stat().st_size == reference["bytes"]
            and p.sha(path) == reference["sha256"],
            "negative_training.frozen_registration_input:" + name,
        )
    _admission(plan["materials_admission"], previous["prospective_stage2_material_admission_id"])
    return plan


def register(root):
    root = Path(root).resolve()
    if (RAW / "protocol.json").exists():
        return read_protocol(root)
    previous = stage1.read_protocol(root)
    completed = p.checked(
        p.read_json(stage1.RAW / "complete.json"), "B_direction_reliability_completed"
    )
    p.require(
        completed["complete"] is True
        and completed["protocol_id"] == previous["id"]
        and completed["status"] == "COMPLETE_SAME_POINT_MECHANISM_DIAGNOSTIC",
        "negative_training.stage1_completed_identity_only_no_score_gate",
    )
    admitted = _admission(
        p.read_json(stage1.RAW / "reuse_admission.json"),
        previous["prospective_stage2_material_admission_id"],
    )
    parent = b.read_protocol(root)
    p.require(
        admitted["original_protocol_id"] == parent["id"], "negative_training.original_B_identity"
    )
    # Admission has already loaded and checked all nine saved points. Preserve
    # those exact references; the worker rechecks its prefix before GPU work.
    for reference in admitted["reusable_refs"]:
        path = Path(reference["path"])
        p.require(
            path.is_absolute() and path.is_relative_to(b.RAW) and path.is_file(),
            "negative_training.existing_original_point",
        )
    names = sorted(
        set(previous["sources"])
        | set(parent["scientific_sources"])
        | {
            SCRIPT,
            worker.SCRIPT,
            materials.SCRIPT,
            stage1.SCRIPT,
            b.SCRIPT,
            identity.SCRIPT,
        }
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = {}
    for name in names:
        payload = (root / name).read_bytes()
        p.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "negative_training.committed_code_before_registration:" + name,
        )
        sources[name] = p.sha(payload)
    plan = p.record(
        PROTOCOL,
        frozen=True,
        authorization="2026-09-26 user: 排查原因，恢复实验; finite training-only substage of audited successor",
        code_commit=head,
        sources=sources,
        parent_B_protocol_id=parent["id"],
        stage1_protocol_id=previous["id"],
        stage1_completion_id=completed["id"],
        no_directional_sign_gate=True,
        no_seed_or_task_selection=True,
        materials_admission=admitted,
        registration_inputs={
            name: input_ref(stage1.RAW / filename)
            for name, filename in dict(
                stage1_protocol="protocol.json",
                stage1_complete="complete.json",
                admission="reuse_admission.json",
            ).items()
        },
        seeds=SEEDS,
        jobs=[dict(key=f"B_negative_{seed}", seed=seed) for seed in SEEDS],
        condition="negative",
        start=200,
        stop=240,
        qminus="2*r-qplus; registered distribution; no clipping or normalization",
        reused_step240_models=6,
        committed_optimizer_updates=120,
        per_seed_committed_updates=40,
        per_seed_optimizer_attempt_cap=48,
        maximum_attempts_per_job=8,
        physical_budget=dict(
            optimizer=144,
            worker_start=24,
            generate_call=0,
            score_case=0,
            feedback=0,
            population=0,
            probe=0,
        ),
        resource_recovery_attempts_included_in_optimizer_cap=True,
        prior_protocol_budget_not_reused=True,
        new_positive_or_static_updates=0,
        panel_status="NOT_READY",
        panel_ready_not_required_for_training_only=True,
        source_acquisition_block_unchanged=True,
        auto_evaluation=False,
        evaluation_requires_new_source_panel_admission_and_separate_registration=True,
        original_confirm720_never_used_for_this_training_substage=True,
        resources=dict(
            maximum_parallel_workers=3,
            required_MiB=32768,
            cold_extra_MiB=1024,
            host_free_bytes=64 * 2**30,
            minimum_disk_free_bytes=100 * 2**30,
            resource_only_retry=True,
            boot_service=False,
        ),
        publication=dict(paths=[PUBLIC], maximum_attempts=8, backoff_seconds=300),
        at=p.now(),
    )
    write(RAW / "protocol.json", plan)
    emit(
        dict(
            event="negative_training_registered",
            protocol_id=plan["id"],
            code_commit=head,
            committed_updates=120,
            optimizer_attempt_cap=144,
            panel_status="NOT_READY",
        )
    )
    return plan


def _component(value):
    value = str(value)
    p.require(bool(re.fullmatch(r"[A-Za-z0-9_.-]+", value)), "negative_training.safe_budget_key")
    return value


def reserve(kind, job_key, attempt, unit):
    plan = p.checked(p.read_json(RAW / "protocol.json"), PROTOCOL)
    p.require(job_key in {row["key"] for row in plan["jobs"]}, "negative_training.registered_job")
    p.require(
        type(attempt) is int and 1 <= attempt <= plan["maximum_attempts_per_job"],
        "negative_training.registered_attempt",
    )
    p.require(
        (kind == "optimizer" and type(unit) is int and 201 <= unit <= 240)
        or (kind == "worker_start" and unit == 0),
        "negative_training.only_registered_training_work",
    )
    marker = (
        RAW
        / "budget/intents"
        / _component(kind)
        / _component(job_key)
        / _component(attempt)
        / (_component(unit) + ".json")
    )
    with locked(RAW / "budget.lock"):
        p.require(not marker.exists(), "negative_training.no_same_attempt_repeat")
        state = read(RAW / "budget/state.json") or dict(counts={}, at=p.now())
        counts = state["counts"]
        used, slot = counts.get(kind, 0), kind + ":" + job_key
        per_seed_cap = (
            plan["per_seed_optimizer_attempt_cap"]
            if kind == "optimizer"
            else plan["maximum_attempts_per_job"]
        )
        p.require(
            used < plan["physical_budget"][kind] and counts.get(slot, 0) < per_seed_cap,
            "negative_training.finite_attempt_budget_exhausted",
        )
        if kind == "optimizer":
            launch = RAW / "budget/intents/worker_start" / job_key / str(attempt) / "0.json"
            p.require(launch.exists(), "negative_training.worker_start_reserved_first")
        counts[kind], counts[slot] = used + 1, counts.get(slot, 0) + 1
        state["at"] = p.now()
        write(RAW / "budget/state.json", state, immutable=False)
        write(
            marker,
            dict(
                protocol_id=plan["id"],
                kind=kind,
                job_key=job_key,
                attempt=attempt,
                unit=unit,
                reservation=used + 1,
                at=p.now(),
            ),
        )


def spawn(root, mode, log, *, arguments=(), gpu=None, lease=None):
    log.parent.mkdir(parents=True, exist_ok=True)
    env = dict(
        os.environ,
        CUDA_VISIBLE_DEVICES="" if gpu is None else gpu["uuid"],
        OMP_NUM_THREADS="2",
        OPENBLAS_NUM_THREADS="2",
        MKL_NUM_THREADS="2",
        CUBLAS_WORKSPACE_CONFIG=":4096:8",
        TOKENIZERS_PARALLELISM="false",
    )
    with log.open("ab") as stream:
        return subprocess.Popen(
            [sys.executable, str(root / SCRIPT), "--root", str(root), "--mode", mode, *arguments],
            cwd=root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            pass_fds=() if lease is None else (lease.fileno(),),
        )


def admit_gpu(required):
    import fcntl

    output = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=index,uuid,memory.free", "--format=csv,noheader,nounits"],
        text=True,
        timeout=15,
    )
    for number, uuid, free in sorted(
        [line.split(",") for line in output.splitlines()], key=lambda row: -int(row[2])
    ):
        if int(free) < required + 1024:
            continue
        path = RAW / "gpu_leases" / (uuid.strip() + ".lock")
        path.parent.mkdir(parents=True, exist_ok=True)
        lease = path.open("a")
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lease.close()
            continue
        return dict(index=int(number), uuid=uuid.strip(), free_MiB=int(free)), lease
    return None, None


def run_worker(root, seed, attempt, required):
    key = f"B_negative_{seed}"
    result = dict(key=key, seed=seed, attempt=attempt, started_at=p.now())
    try:
        plan = read_protocol(root)
        p.require(
            seed in SEEDS and type(seed) is int and type(attempt) is int and 1 <= attempt <= 8,
            "negative_training.worker_arguments",
        )
        p.require(
            required == plan["resources"]["required_MiB"], "negative_training.registered_capacity"
        )
        launch = read(RAW / "budget/intents/worker_start" / key / str(attempt) / "0.json")
        p.require(
            launch is not None and launch["protocol_id"] == plan["id"],
            "negative_training.no_unregistered_worker",
        )
        write(
            RAW / "worker_identities" / key / f"{attempt:04d}.json",
            dict(
                key=key,
                seed=seed,
                attempt=attempt,
                identity=identity.identity(os.getpid()),
                at=p.now(),
            ),
        )
        value = worker.run(sys.modules[__name__], root, seed, attempt, required_MiB=required)
        result.update(returncode=0, protocol_id=plan["id"], report_id=value["id"])
    except CapacityWait as error:
        result.update(returncode=43, error=str(error))
    except Exception as error:
        retry = isinstance(error, (torch.OutOfMemoryError, MemoryError))
        result.update(
            returncode=42 if retry else 1,
            error=repr(error),
            traceback=traceback.format_exc(),
            resource_retry_allowed=retry,
        )
    result["finished_at"] = p.now()
    write(RAW / "results" / key / f"{attempt:04d}.json", result)
    return result["returncode"]


def publish(root, report):
    path = RAW / "publication.json"
    previous = read(path)
    if previous and previous["status"] == "PUBLISHED":
        p.require(previous["report_id"] == report["id"], "negative_training.same_published_report")
        return True
    if previous and time.time() < previous["not_before"]:
        return False
    attempt = 1 if previous is None else previous["attempt"] + 1
    p.require(attempt <= 8, "negative_training.publication_cap_no_retraining")
    try:
        target = root / PUBLIC
        if target.exists():
            p.require(p.read_json(target) == report, "negative_training.same_public_report")
        else:
            p.write_once(target, report)
        subprocess.run(["git", "add", "--sparse", "-f", "--", PUBLIC], cwd=root, check=True)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet", "--", PUBLIC], cwd=root)
        p.require(diff.returncode in (0, 1), "negative_training.publication_diff")
        if diff.returncode:
            subprocess.run(
                [
                    "git",
                    "commit",
                    "--only",
                    "-m",
                    "Publish fixed negative-direction training endpoints",
                    "--",
                    PUBLIC,
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
        write(
            path,
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
        write(
            path,
            dict(
                status="PUBLICATION_PENDING_NO_RETRAINING",
                report_id=report["id"],
                attempt=attempt,
                not_before=time.time() + 300,
                error=repr(error),
                at=p.now(),
            ),
            immutable=False,
        )
        return False


def _final_saved_point(value, job, plan):
    checkpoint = RAW / "jobs" / job["key"] / "updates/0240.pt"
    p.require(
        Path(value["checkpoint_path"]).resolve() == checkpoint.resolve() and checkpoint.exists(),
        "negative_training.actual_final_saved_point",
    )
    stat = checkpoint.stat()
    fingerprint = (str(checkpoint), stat.st_size, stat.st_mtime_ns, value["checkpoint_sha256"])
    if fingerprint not in _verified_final:
        p.require(
            p.sha(checkpoint) == value["checkpoint_sha256"],
            "negative_training.final_checkpoint_bytes",
        )
        _verified_final[fingerprint] = True
    admitted = plan["materials_admission"]
    reflection = admitted["distributions"][str(job["seed"])]
    reference = next(
        row
        for row in admitted["reusable_refs"]
        if row["job_key"] == f"B_prefix_{job['seed']}" and row["step"] == 200
    )
    branch = p.checked(value["prefix_binding"], "direction_calibration_negative_branch_binding")
    p.require(
        value["original_prefix_sha256"] == reference["sha256"]
        and value["distribution_sha256"] == reflection["distribution_sha256"]["negative"]
        and branch["id"] == value["branch_binding_id"]
        and branch["plan_id"] == plan["id"]
        and branch["job_key"] == job["key"]
        and branch["reflection_id"] == reflection["id"]
        and branch["prefix_checkpoint_sha256"] == reference["sha256"]
        and branch["distribution_sha256"] == value["distribution_sha256"],
        "negative_training.final_exact_registered_branch",
    )


def finish(root, plan):
    p.require(
        plan["jobs"] == [dict(key=f"B_negative_{seed}", seed=seed) for seed in SEEDS],
        "negative_training.complete_exact_three_jobs",
    )
    values = []
    for job in plan["jobs"]:
        value = read(RAW / "jobs" / job["key"] / "report.json")
        if value is None:
            p.require(
                not (RAW / "report.json").exists(),
                "negative_training.aggregate_requires_job_reports",
            )
            return False
        p.checked(value, "direction_calibration_training_report")
        p.require(
            value["complete"] is True
            and value["plan_id"] == plan["id"]
            and value["job_key"] == job["key"]
            and value["seed"] == job["seed"]
            and value["condition"] == "negative"
            and value["start"] == 200
            and value["stop"] == 240
            and value["physical_optimizer_updates"] == 40
            and value["full_original_epochs"] == 1
            and value["material_admission_id"] == plan["materials_admission"]["id"]
            and value["generation_sessions"]
            == value["scoring_sessions"]
            == value["new_positive_or_static_updates"]
            == 0,
            "negative_training.complete_bound_job",
        )
        _final_saved_point(value, job, plan)
        values.append(
            {
                name: value[name]
                for name in (
                    "seed",
                    "job_key",
                    "id",
                    "checkpoint_path",
                    "checkpoint_sha256",
                    "snapshot_id",
                    "RNG_binding",
                    "physical_optimizer_updates",
                    "physical_job_totals",
                    "distribution_sha256",
                    "branch_binding_id",
                )
            }
        )
    budget = read(RAW / "budget/state.json")
    p.require(budget is not None, "negative_training.required_attempt_accounting")
    counts = budget["counts"]
    p.require(
        120 <= counts.get("optimizer", 0) <= 144
        and 3 <= counts.get("worker_start", 0) <= 24
        and all(40 <= counts.get("optimizer:" + job["key"], 0) <= 48 for job in plan["jobs"])
        and all(1 <= counts.get("worker_start:" + job["key"], 0) <= 8 for job in plan["jobs"])
        and all(
            counts.get(kind, 0) == 0
            for kind in ("generate_call", "score_case", "feedback", "population", "probe")
        )
        and all(
            counts[kind] == sum(counts[kind + ":" + job["key"]] for job in plan["jobs"])
            for kind in ("optimizer", "worker_start")
        ),
        "negative_training.bounded_complete_accounting",
    )
    p.require(
        sum(row["physical_job_totals"]["sequence_tokens"] for row in values) == 53435082
        and sum(row["physical_job_totals"]["target_tokens"] for row in values) == 2946264,
        "negative_training.complete_fixed_token_dose",
    )
    expected = dict(
        protocol_id=plan["id"],
        complete=True,
        status="COMPLETE_TRAINING_ONLY_EVALUATION_BLOCKED",
        seeds=values,
        reused_step240_models=6,
        committed_optimizer_updates=120,
        optimizer_attempt_reservations=counts["optimizer"],
        failed_or_uncommitted_reservations=counts["optimizer"] - 120,
        committed_physical_sequence_tokens=53435082,
        committed_physical_target_tokens=2946264,
        budget=counts,
        new_generation_calls=0,
        new_scoring_cases=0,
        new_feedback=0,
        new_population_passes=0,
        new_Probe=0,
        new_positive_or_static_updates=0,
        panel_status="NOT_READY",
        auto_evaluation=False,
        no_training_value_conclusion_without_new_evaluation=True,
    )
    path = RAW / "report.json"
    if path.exists():
        report = p.checked(p.read_json(path), COMPLETED)
        p.require(
            all(report[name] == value for name, value in expected.items()),
            "negative_training.reused_completion_identity",
        )
    else:
        report = p.record(COMPLETED, **expected, at=p.now())
        write(path, report)
    # Scientific completion is independent of remote publication; a push failure
    # must never cause another optimizer step or erase already saved endpoints.
    write(RAW / "complete.json", report)
    return publish(root, report)


def coordinate(root):
    plan = read_protocol(root)
    state_path = RAW / "control/state.json"
    with locked(RAW / "controller.lock", blocking=False):
        write(
            RAW / "control/controller_identity.json",
            identity.identity(os.getpid()),
            immutable=False,
        )
        state = read(state_path) or dict(jobs={}, active={})
        children = {}
        for job in plan["jobs"]:
            state["jobs"].setdefault(
                job["key"], dict(attempt=0, failures=0, not_before=0, stopped=None)
            )
        for path in sorted((RAW / "worker_identities").glob("*/*.json")):
            row = p.read_json(path)
            p.require(row["key"] in state["jobs"], "negative_training.adopt_only_registered_job")
            state["jobs"][row["key"]]["attempt"] = max(
                state["jobs"][row["key"]]["attempt"], row["attempt"]
            )
            if identity.same_process(row["identity"]):
                prior = state["active"].get(row["key"])
                p.require(
                    prior is None
                    or not identity.same_process(prior["identity"])
                    or prior["identity"]["pid"] == row["identity"]["pid"],
                    "negative_training.one_live_worker_per_seed",
                )
                state["active"][row["key"]] = {**(prior or {}), **row}
        while True:
            for key, row in list(state["active"].items()):
                child = children.get(key)
                if child is not None:
                    code = child.poll()
                    if code is None:
                        continue
                    children.pop(key)
                else:
                    if identity.same_process(row["identity"]):
                        continue
                    code = None
                state["active"].pop(key)
                status = state["jobs"][key]
                result = read(RAW / "results" / key / f"{row['attempt']:04d}.json")
                if result is None and code not in (None, -9, -15):
                    result = dict(
                        returncode=1, reason="unclassified_exit", exit_code=code, at=p.now()
                    )
                if result is None or result["returncode"] in (42, 43):
                    status["failures"] += int(result is not None and result["returncode"] == 42)
                    status["not_before"] = time.time() + min(
                        900, 60 * 2 ** min(status["failures"], 4)
                    )
                    if result is None:
                        write(
                            RAW / "resource_exits" / f"{key}_{row['attempt']:04d}.json",
                            dict(
                                observed_exit_code=code,
                                inferred_external_exit_not_numeric_pass=True,
                                at=p.now(),
                            ),
                        )
                elif result["returncode"] != 0:
                    status["stopped"] = result
            # Persist removals before completion/publication can return.
            write(state_path, state, immutable=False)
            failed = any(row["stopped"] for row in state["jobs"].values())
            if failed:
                write(
                    RAW / "needs_attention.json",
                    dict(jobs=state["jobs"], at=p.now()),
                    immutable=False,
                )
            if not failed and not state["active"] and finish(root, plan):
                return 0
            for job in plan["jobs"] if not failed else ():
                key, status = job["key"], state["jobs"][job["key"]]
                if (
                    key in state["active"]
                    or (RAW / "jobs" / key / "report.json").exists()
                    or time.time() < status["not_before"]
                ):
                    continue
                if status["attempt"] >= plan["maximum_attempts_per_job"]:
                    status["stopped"] = dict(reason="registered_attempt_cap", at=p.now())
                    break
                if (
                    len(state["active"]) >= plan["resources"]["maximum_parallel_workers"]
                    or old.host_memory()["MemAvailable_bytes"]
                    < plan["resources"]["host_free_bytes"]
                ):
                    continue
                filesystem = os.statvfs(RAW)
                if (
                    filesystem.f_bavail * filesystem.f_frsize
                    < plan["resources"]["minimum_disk_free_bytes"]
                ):
                    continue
                required = plan["resources"]["required_MiB"]
                try:
                    gpu, lease = admit_gpu(required)
                except (OSError, subprocess.SubprocessError):
                    continue
                if gpu is None:
                    continue
                status["attempt"] += 1
                number = status["attempt"]
                write(state_path, state, immutable=False)
                try:
                    reserve("worker_start", key, number, 0)
                    child = spawn(
                        root,
                        "worker",
                        RAW / "logs" / f"{key}_{number:04d}.log",
                        arguments=(
                            "--seed",
                            str(job["seed"]),
                            "--attempt",
                            str(number),
                            "--required-MiB",
                            str(required),
                        ),
                        gpu=gpu,
                        lease=lease,
                    )
                    state["active"][key] = dict(
                        key=key,
                        seed=job["seed"],
                        attempt=number,
                        gpu=gpu,
                        identity=identity.identity(child.pid),
                    )
                    children[key] = child
                    emit(
                        dict(
                            event="negative_training_worker_launched",
                            key=key,
                            attempt=number,
                            pid=child.pid,
                            gpu=gpu,
                        )
                    )
                except Exception as error:
                    status["stopped"] = dict(error=repr(error), at=p.now())
                finally:
                    lease.close()
            write(state_path, state, immutable=False)
            progress = {
                job["key"]: len(
                    list((RAW / "jobs" / job["key"] / "updates").glob("[0-9][0-9][0-9][0-9].pt"))
                )
                for job in plan["jobs"]
            }
            write(
                RAW / "heartbeat.json",
                dict(
                    protocol_id=plan["id"],
                    at=p.now(),
                    active=state["active"],
                    committed_updates=progress,
                    target_committed_updates=120,
                    jobs=state["jobs"],
                    any_failure=any(row["stopped"] for row in state["jobs"].values()),
                    panel_status="NOT_READY",
                    evaluation_started=False,
                ),
                immutable=False,
            )
            if any(row["stopped"] for row in state["jobs"].values()) and not state["active"]:
                return 1
            time.sleep(20)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--mode", required=True, choices=("register", "start", "watch", "coordinate", "worker")
    )
    parser.add_argument("--seed", type=int)
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--required-MiB", type=int, default=32768)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "register":
        register(root)
        return 0
    if args.mode == "worker":
        return run_worker(root, args.seed, args.attempt, args.required_MiB)
    read_protocol(root)
    if args.mode == "start":
        current = read(RAW / "control/watchdog_identity.json")
        if current and identity.same_process(current):
            emit(dict(event="negative_training_already_running", pid=current["pid"]))
            return 0
        child = spawn(root, "watch", RAW / "watchdog.log")
        write(RAW / "control/watchdog_identity.json", identity.identity(child.pid), immutable=False)
        emit(dict(event="negative_training_supervision_started", pid=child.pid))
        return 0
    if args.mode == "watch":
        with locked(RAW / "watchdog.lock", blocking=False):
            write(
                RAW / "control/watchdog_identity.json",
                identity.identity(os.getpid()),
                immutable=False,
            )
            while True:
                child = spawn(root, "coordinate", RAW / "coordinator.log")
                code = child.wait()
                write(
                    RAW / "watchdog_status.json", dict(returncode=code, at=p.now()), immutable=False
                )
                if code not in (-9, -15, 42):
                    return code
                time.sleep(30)
    try:
        return coordinate(root)
    except (MemoryError, subprocess.TimeoutExpired) as error:
        emit(dict(event="negative_training_controller_resource_retry", error=repr(error)))
        return 42
    except Exception as error:
        write(
            RAW / "controller_failure.json",
            dict(error=repr(error), traceback=traceback.format_exc(), at=p.now()),
            immutable=False,
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
