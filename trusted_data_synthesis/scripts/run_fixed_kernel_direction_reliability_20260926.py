"""Register and durably supervise the three-seed, existing-feedback direction audit."""

# ruff: noqa: E501 -- frozen scope, provenance and durable stage contracts
import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

import fixed_kernel_B_direction_reliability_20260926 as worker
import fixed_kernel_direction_calibration_common_20260926 as c
import fixed_kernel_direction_calibration_materials_20260926 as materials
import run_fixed_kernel_delayed_C_migration_20260921 as identity

p = c.p
SCRIPT = "trusted_data_synthesis/scripts/run_fixed_kernel_direction_reliability_20260926.py"
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/34567c43-798c-472a-aa20-36a6c7d744a4/已粘贴的文本.txt"
)
PUBLIC = "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/direction_calibration_20260926/public"


def read(path):
    return p.read_json(path) if path.exists() else None


def input_ref(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=p.sha(path))


def register(root):
    path = c.RAW / "protocol.json"
    if path.exists():
        return c.read_protocol(root)
    parent = c.b.read_protocol(root)
    previous = p.checked(p.read_json(c.b.RAW / "complete.json"), "B_confirm_completed_study")
    p.require(
        previous["protocol_id"] == parent["id"]
        and previous["status"] == "COMPLETE_B_MAIN_CONFIRMATION"
        and previous["positive_effect_confirmed"] is False,
        "direction.completed_B_not_positive_confirmation",
    )
    admission = materials.admit(root, c.b.RAW)
    names = [
        SCRIPT,
        c.SCRIPT,
        worker.SCRIPT,
        materials.SCRIPT,
        "trusted_data_synthesis/scripts/fixed_kernel_proxy_direction_20260919.py",
        "trusted_data_synthesis/scripts/fixed_kernel_proxy_numeric_20260919.py",
        "trusted_data_synthesis/scripts/fixed_kernel_proxy_inputs_20260919.py",
        identity.SCRIPT,
    ]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = {}
    for name in names:
        payload = (root / name).read_bytes()
        p.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "direction.committed_code_before_registration",
        )
        sources[name] = p.sha(payload)
    inputs = {}
    for seed in parent["seeds"]:
        folder = c.b.RAW / "outer" / f"B_delayed_c_{seed}"
        inventory = p.checked(
            p.read_json(folder / "response_inventory.json"), "B_feedback_response_inventory"
        )
        paths = dict(
            population=folder / "population.pt",
            final_vectors=folder / "final_vectors.pt",
            prefix_checkpoint=c.b.RAW / "jobs" / f"B_prefix_{seed}" / "updates/0200.pt",
            prefix_report=c.b.RAW / "jobs" / f"B_prefix_{seed}" / "report.json",
            feedback_generation=c.b.RAW
            / "generation/feedback"
            / f"B_delayed_c_{seed}"
            / "generation_manifest.json",
            feedback_scoring=c.b.RAW
            / "generation/feedback"
            / f"B_delayed_c_{seed}"
            / "scoring_report.json",
        )
        paths.update(
            {
                name: folder / (filename + ".json")
                for name, filename in dict(
                    full_G="full_G",
                    gJ="gJ",
                    C="C",
                    distribution_update="distribution_update",
                    outer_report="report",
                    prepare_report="prepare_report",
                    response_inventory="response_inventory",
                ).items()
            }
        )
        c.emit(
            dict(
                event="direction_binding_saved_inputs",
                seed=seed,
                population_bytes=paths["population"].stat().st_size,
            )
        )
        inputs[str(seed)] = dict(
            job_key=f"B_direction_reliability_{seed}",
            original_job_key=f"B_delayed_c_{seed}",
            original_stage_directory=str(folder),
            required_responses=inventory["required_responses"],
            positive_trajectories=len(inventory["positives"]),
            expected_output_tokens=sum(row["tokens"] for row in inventory["responses"]),
            files={name: input_ref(value) for name, value in paths.items()},
        )
    p.require(
        sum(row["required_responses"] for row in inputs.values()) == 1711
        and sum(row["positive_trajectories"] for row in inputs.values()) == 292,
        "direction.exact_existing_feedback_workload",
    )
    plan = p.record(
        "B_direction_reliability_protocol",
        frozen=True,
        authorization="2026-09-26 user: 参照审计修订并开展后续实验",
        audit_attachment_sha256=p.sha(AUDIT),
        code_commit=head,
        sources=sources,
        parent_B_protocol_id=parent["id"],
        parent_B_completion_id=previous["id"],
        parent_B_scope="PASS_AS_SCOPED; execution complete; positive training effect NOT confirmed",
        prior_confirm720_exposed_not_fresh_for_successor=True,
        seeds=[11, 29, 47],
        jobs=[dict(key=f"B_direction_reliability_{seed}", seed=seed) for seed in (11, 29, 47)],
        reliability_inputs=inputs,
        new_feedback_sessions=0,
        new_scoring_cases=0,
        existing_feedback_sessions=1080,
        required_positive_trajectories=292,
        required_responses=1711,
        new_training_updates=0,
        new_population_passes=0,
        fixed_total_denominator=360,
        fixed_repeat_denominator=180,
        total_accumulator="original GPU FP32 response order, alpha=1/360",
        trajectory_accumulator="CPU FP64 sum of original FP32 response gradients, no resampling",
        CPU_operator="original saved-point Adam derivative coefficients; no stable formula substitution",
        linkage_limits=dict(gJ_rtol=1e-5, gJ_atol=1e-6, C_relative_RMS=1e-5, pi_weighted_TV=1e-5),
        diagnostics=[
            "S_1_to_2",
            "S_2_to_1",
            "repeat_C_cosine_and_scale",
            "task_and_CIK_vector_influence",
            "fixed_denominator_leave_one_task_or_CIK_out",
        ],
        no_seed_or_task_exclusion_based_on_diagnostics=True,
        no_automatic_algorithm_change=True,
        no_directional_sign_gate_for_stage2=True,
        physical_budget=dict(
            reliability_response=2095,
            worker_start=24,
            optimizer=0,
            population=0,
            generate_call=0,
            score_case=0,
        ),
        extra_responses_per_seed=128,
        maximum_attempts_per_job=8,
        resources=dict(
            maximum_parallel_workers=3,
            required_MiB=51200,
            cold_extra_MiB=1024,
            host_free_bytes=128 * 2**30,
            minimum_disk_free_bytes=100 * 2**30,
            CPU_projection_threads_each=16,
            approximate_checkpoint_storage_GiB=51,
            resource_only_retry=True,
            boot_service=False,
        ),
        prospective_stage2_material_admission_id=admission["id"],
        prospective_stage2=dict(
            arms=["static", "positive", "negative"],
            seeds=[11, 29, 47],
            start=200,
            stop=240,
            qminus="2*r-qplus, no clipping or normalization",
            reuse_checked=True,
            new_SFT_updates=120,
            calibration_tasks=180,
            group_quota=60,
            evaluations_each_model=dict(stochastic_repeats=2, greedy_repeats=1),
            total_new_sessions=4860,
            committed_generate_call_cap=155520,
            panel_status="NOT_READY_new_source_catalog_and_input_admission_required",
            stage2_requires_separate_frozen_execution_registration=True,
            old_confirm720_not_reused_or_expanded=True,
        ),
        at=p.now(),
    )
    c.RAW.mkdir(parents=True, exist_ok=True)
    c.b.durable.atomic_bytes(c.RAW / "audit_directive.txt", AUDIT.read_bytes(), immutable=True)
    c.write(c.RAW / "reuse_admission.json", admission)
    c.write(path, plan)
    c.emit(
        dict(
            event="direction_reliability_registered",
            protocol_id=plan["id"],
            code_commit=head,
            reused_step240_models=6,
            new_counterfactual_steps_if_stage2_admitted=120,
        )
    )
    return plan


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
        path = c.RAW / "gpu_leases" / (uuid.strip() + ".lock")
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
    key = f"B_direction_reliability_{seed}"
    result = dict(key=key, seed=seed, attempt=attempt, started_at=p.now())
    try:
        plan = c.read_protocol(root)
        c.write(
            c.RAW / "worker_identities" / key / f"{attempt:04d}.json",
            dict(
                key=key,
                seed=seed,
                attempt=attempt,
                identity=identity.identity(os.getpid()),
                at=p.now(),
            ),
        )
        value = worker.run(root, seed, attempt, required)
        result.update(returncode=0, protocol_id=plan["id"], report_id=value["id"])
    except c.CapacityWait as error:
        result.update(returncode=43, error=str(error))
    except Exception as error:
        retry = isinstance(error, (c.torch.OutOfMemoryError, MemoryError))
        result.update(
            returncode=42 if retry else 1,
            error=repr(error),
            traceback=traceback.format_exc(),
            resource_retry_allowed=retry,
        )
    result["finished_at"] = p.now()
    c.write(c.RAW / "results" / key / f"{attempt:04d}.json", result)
    return result["returncode"]


def publish(root, report):
    receipt_path = c.RAW / "publication.json"
    prior = read(receipt_path)
    if prior and prior["status"] == "PUBLISHED":
        p.require(prior["report_id"] == report["id"], "direction.published_same_report")
        return True
    if prior and time.time() < prior["not_before"]:
        return False
    attempt = 1 if prior is None else prior["attempt"] + 1
    p.require(attempt <= 8, "direction.publication_cap_no_scientific_retry")
    path = root / PUBLIC / "reliability_completed.json"
    doc = root / "trusted_data_synthesis/docs/direction_reliability_completed_20260926.md"
    body = (
        "# B 同点方向可靠性核查完成\n\n仅复用原反馈；交叉得分与删除敏感性是机制证据，不是新任务泛化或训练价值确认，不据此删除seed/任务或自动改算法。阶段二仍须新面板及独立登记。\n\n```json\n"
        + json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n```\n"
    )
    try:
        if path.exists():
            p.require(p.read_json(path) == report, "direction.same_public_report")
        else:
            p.write_once(path, report)
        if doc.exists():
            p.require(doc.read_text() == body, "direction.same_completion_document")
        else:
            c.b.durable.atomic_bytes(doc, body.encode(), immutable=True)
        paths = [str(path.relative_to(root)), str(doc.relative_to(root))]
        subprocess.run(["git", "add", "--sparse", "-f", "--", *paths], cwd=root, check=True)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet", "--", *paths], cwd=root)
        p.require(diff.returncode in (0, 1), "direction.git_diff")
        if diff.returncode:
            subprocess.run(
                [
                    "git",
                    "commit",
                    "--only",
                    "-m",
                    "Publish fixed B same-point direction reliability",
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
        c.write(
            receipt_path,
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
        c.write(
            receipt_path,
            dict(
                status="PUBLICATION_PENDING_NO_SCIENTIFIC_RETRY",
                report_id=report["id"],
                attempt=attempt,
                not_before=time.time() + 300,
                error=repr(error),
                at=p.now(),
            ),
            immutable=False,
        )
        return False


def finish(root, plan):
    path = c.RAW / "report.json"
    if path.exists():
        report = p.checked(p.read_json(path), "B_direction_reliability_completed")
        p.require(
            report["protocol_id"] == plan["id"]
            and report["complete"] is True
            and report["status"] == "COMPLETE_SAME_POINT_MECHANISM_DIAGNOSTIC",
            "direction.reused_completed_same_protocol",
        )
    else:
        values = []
        for job in plan["jobs"]:
            value = read(c.RAW / "reliability" / job["key"] / "report.json")
            if value is None:
                return False
            p.checked(value, "B_direction_reliability_report")
            p.require(
                value["complete"]
                and value["plan_id"] == plan["id"]
                and value["equivalence_passed"],
                "direction.complete_bound_result",
            )
            registered = plan["reliability_inputs"][str(job["seed"])]
            p.require(
                value["seed"] == job["seed"]
                and value["job_key"] == job["key"]
                and value["required_responses"] == registered["required_responses"]
                and value["positive_trajectories"] == registered["positive_trajectories"],
                "direction.exact_registered_seed_and_workload",
            )
            analysis = value["analysis"]
            values.append(
                dict(
                    seed=job["seed"],
                    report_id=value["id"],
                    positive_trajectories=value["positive_trajectories"],
                    responses=value["required_responses"],
                    cross=analysis["cross"],
                    half_C_comparison=analysis["half_C_comparison"],
                )
            )
        p.require(
            sum(row["responses"] for row in values) == plan["required_responses"]
            and sum(row["positive_trajectories"] for row in values)
            == plan["required_positive_trajectories"],
            "direction.complete_registered_workload",
        )
        report = p.record(
            "B_direction_reliability_completed",
            protocol_id=plan["id"],
            complete=True,
            status="COMPLETE_SAME_POINT_MECHANISM_DIAGNOSTIC",
            seeds=values,
            new_generation_calls=0,
            new_financial_scoring=0,
            new_SFT_updates=0,
            new_population_passes=0,
            budget=p.read_json(c.RAW / "budget/state.json")["counts"],
            no_selection_or_algorithm_change=True,
            stage2_panel_not_automatically_admitted=True,
            at=p.now(),
        )
        c.write(path, report)
    if not publish(root, report):
        return False
    c.write(c.RAW / "complete.json", report)
    return True


def coordinate(root):
    plan = c.read_protocol(root)
    state_path = c.RAW / "control/state.json"
    with c.locked(c.RAW / "controller.lock", blocking=False):
        c.write(
            c.RAW / "control/controller_identity.json",
            identity.identity(os.getpid()),
            immutable=False,
        )
        state = read(state_path) or dict(jobs={}, active={})
        children = {}
        for job in plan["jobs"]:
            state["jobs"].setdefault(
                job["key"], dict(attempt=0, failures=0, not_before=0, stopped=None)
            )
        for path in sorted((c.RAW / "worker_identities").glob("*/*.json")):
            row = p.read_json(path)
            state["jobs"][row["key"]]["attempt"] = max(
                state["jobs"][row["key"]]["attempt"], row["attempt"]
            )
            if identity.same_process(row["identity"]):
                prior = state["active"].get(row["key"])
                p.require(
                    prior is None
                    or not identity.same_process(prior["identity"])
                    or prior["identity"]["pid"] == row["identity"]["pid"],
                    "direction.one_live_worker_per_seed",
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
                result = read(c.RAW / "results" / key / f"{row['attempt']:04d}.json")
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
                        c.write(
                            c.RAW / "resource_exits" / f"{key}_{row['attempt']:04d}.json",
                            dict(
                                observed_exit_code=code,
                                inferred_external_exit_not_numeric_pass=True,
                                at=p.now(),
                            ),
                        )
                elif result["returncode"] != 0:
                    status["stopped"] = result
            c.write(state_path, state, immutable=False)
            failed = any(row["stopped"] for row in state["jobs"].values())
            if failed:
                c.write(
                    c.RAW / "needs_attention.json",
                    dict(jobs=state["jobs"], at=p.now()),
                    immutable=False,
                )
            if not failed and not state["active"] and finish(root, plan):
                return 0
            for job in plan["jobs"] if not failed else ():
                key = job["key"]
                status = state["jobs"][key]
                if (
                    key in state["active"]
                    or (c.RAW / "reliability" / key / "report.json").exists()
                    or time.time() < status["not_before"]
                ):
                    continue
                if status["attempt"] >= plan["maximum_attempts_per_job"]:
                    status["stopped"] = dict(reason="registered_attempt_cap", at=p.now())
                    break
                if (
                    len(state["active"]) >= 3
                    or c.old.host_memory()["MemAvailable_bytes"]
                    < plan["resources"]["host_free_bytes"]
                ):
                    continue
                if (
                    os.statvfs(c.RAW).f_bavail * os.statvfs(c.RAW).f_frsize
                    < plan["resources"]["minimum_disk_free_bytes"]
                ):
                    continue
                required = min(77824, 51200 + 4096 * status["failures"])
                try:
                    gpu, lease = admit_gpu(required)
                except (OSError, subprocess.SubprocessError):
                    continue
                if gpu is None:
                    continue
                status["attempt"] += 1
                number = status["attempt"]
                c.write(state_path, state, immutable=False)
                try:
                    c.reserve("worker_start", key, number, 0)
                    child = spawn(
                        root,
                        "worker",
                        c.RAW / "logs" / f"{key}_{number:04d}.log",
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
                    c.emit(
                        dict(
                            event="direction_worker_launched",
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
            c.write(state_path, state, immutable=False)
            progress = {
                job["key"]: len(
                    list((c.RAW / "reliability" / job["key"] / "responses").glob("*.pt"))
                )
                for job in plan["jobs"]
            }
            c.write(
                c.RAW / "heartbeat.json",
                dict(
                    protocol_id=plan["id"],
                    at=p.now(),
                    active=state["active"],
                    committed_responses=progress,
                    jobs=state["jobs"],
                    any_failure=any(row["stopped"] for row in state["jobs"].values()),
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
    parser.add_argument("--required-MiB", type=int, default=51200)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "register":
        register(root)
        return 0
    if args.mode == "worker":
        return run_worker(root, args.seed, args.attempt, args.required_MiB)
    c.read_protocol(root)
    if args.mode == "start":
        current = read(c.RAW / "control/watchdog_identity.json")
        if current and identity.same_process(current):
            c.emit(dict(event="direction_already_running", pid=current["pid"]))
            return 0
        child = spawn(root, "watch", c.RAW / "watchdog.log")
        c.write(
            c.RAW / "control/watchdog_identity.json", identity.identity(child.pid), immutable=False
        )
        c.emit(dict(event="direction_supervision_started", pid=child.pid))
        return 0
    if args.mode == "watch":
        with c.locked(c.RAW / "watchdog.lock", blocking=False):
            c.write(
                c.RAW / "control/watchdog_identity.json",
                identity.identity(os.getpid()),
                immutable=False,
            )
            while True:
                child = spawn(root, "coordinate", c.RAW / "coordinator.log")
                code = child.wait()
                c.write(
                    c.RAW / "watchdog_status.json",
                    dict(returncode=code, at=p.now()),
                    immutable=False,
                )
                if code not in (-9, -15, 42):
                    return code
                time.sleep(30)
    try:
        return coordinate(root)
    except (MemoryError, subprocess.TimeoutExpired) as error:
        c.emit(dict(event="direction_controller_resource_retry", error=repr(error)))
        return 42
    except Exception as error:
        c.write(
            c.RAW / "controller_failure.json",
            dict(error=repr(error), traceback=traceback.format_exc(), at=p.now()),
            immutable=False,
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
