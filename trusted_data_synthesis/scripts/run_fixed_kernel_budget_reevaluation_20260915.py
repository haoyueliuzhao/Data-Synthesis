"""Frozen, outcome-blind budget diagnostic; never reopens the parent experiment.

Prepare is CPU-only. Run admits the base once, spawns independent GPU generation
processes, and scores only after those processes exit. Three fixed public tasks
gate an optional 177-task complement; no Student training or B release exists.
"""

# ruff: noqa: E501 -- exact policy strings and emitted Markdown table rows

import argparse
import contextlib
import hashlib
import importlib
import itertools
import json
import multiprocessing
import os
import signal
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

PACKAGE = "trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value"
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/budget_reevaluation_20260915"
RUNTIME = "trusted_data_synthesis/runtime/fixed_kernel_budget_reevaluation_20260915"
PARENT_OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/parallel_tail_execution_20260914"
)
SCRIPT = "trusted_data_synthesis/scripts/run_fixed_kernel_budget_reevaluation_20260915.py"
ADAPTER = "trusted_data_synthesis/scripts/fixed_kernel_budget_reevaluation_adapter_20260915.py"
SUMMARY = "trusted_data_synthesis/docs/fixed_kernel_budget_reevaluation_actual_results_20260915.md"
SALT = "higher_budget_pilot_20260915:v1"
GROUPS = ("dual_sufficient", "composition_required", "other_financial")
GPU_UUIDS = (
    "GPU-f813ce38-39d7-ab21-f72b-55f87284eaa5",
    "GPU-0a62363e-fb3c-74fd-c5fe-1a2720c7e66a",
    "GPU-88a33540-ff55-746e-d82b-45821b463102",
    "GPU-004a2d75-6298-df4d-7b95-103bc6c1b02a",
    "GPU-ae8978c8-5100-933e-78d1-46ed781a8a0e",
    "GPU-f731a280-01e3-2359-ace9-aa2ad2112f55",
    "GPU-6cf85ebf-ae89-905b-5d97-46f83b295526",
    "GPU-ab6e97cc-19e4-64b8-f792-7b6920a45434",
)
PILOT_WALL_SECONDS = 90 * 60
MINIMUM_FREE_MIB = 80000


def require(value, code):
    if not value:
        raise ValueError("budget_reevaluation." + code)


def modules(root):
    root = Path(root).resolve()
    for relative in (
        "trusted_data_synthesis/src",
        "raw_financial_data_lake",
        "trusted_data_synthesis/scripts",
    ):
        value = str(root / relative)
        if value not in sys.path:
            sys.path.insert(0, value)
    return (
        importlib.import_module(PACKAGE + ".protocol"),
        importlib.import_module(PACKAGE + ".evaluation"),
        importlib.import_module("fixed_kernel_budget_reevaluation_adapter_20260915"),
    )


def select_pilot_tasks(dev_rows):
    """Select from public metadata only, independent of input order and outcomes."""
    require(len({row["task_id"] for row in dev_rows}) == len(dev_rows), "unique_public_tasks")
    ranked = []
    for group in GROUPS:
        rows = [row for row in dev_rows if row.get("group", row.get("family")) == group]
        require(rows, "every_public_group_present")
        ranked.append(
            sorted(
                rows,
                key=lambda row: (
                    hashlib.sha256((SALT + ":" + row["task_id"]).encode()).hexdigest(),
                    row["task_id"],
                ),
            )
        )
    # At most 60^3 tiny metadata combinations; normally the first is already distinct.
    selected = next(
        (
            rows
            for rows in itertools.product(*ranked)
            if len({row["source_cluster"] for row in rows}) == 3
        ),
        None,
    )
    require(selected is not None, "three_distinct_public_company_clusters_required")
    return [row["task_id"] for row in selected]


def remaining_task_ids(dev_rows, pilot_ids):
    chosen = set(pilot_ids)
    require(len(chosen) == len(pilot_ids), "unique_pilot")
    require(chosen <= {row["task_id"] for row in dev_rows}, "pilot_in_dev")
    return [row["task_id"] for row in dev_rows if row["task_id"] not in chosen]


def decide_next_stage(scores, expected=27):
    """Operational budget gate, not a statistical effect test or B authorization."""
    if not scores or any(score.get("actual_complete") is not True for score in scores):
        return "INCOMPLETE_PILOT"
    outcomes = [row for score in scores for row in score.get("outcomes", [])]
    if len(outcomes) != expected:
        return "INCOMPLETE_PILOT"
    return (
        "FULL_DEV_REEVALUATION"
        if any(row.get("financial_valid") is True for row in outcomes)
        else "STOP_ZERO_QUALIFIED"
    )


def file_reference(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    require(path.is_relative_to(root) and not path.is_symlink(), "scoped_regular_reference")
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(root)),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def source_capture(root, parent, p):
    """One source verification before use; workers inherit trusted spawned code."""
    members = []
    for row in parent["code_binding"]["members"]:
        actual = file_reference(root, Path(root) / row["path"])
        require(actual["sha256"] == row["sha256"], "parent_python_dependency_unchanged")
        members.append(actual)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    for name in (SCRIPT, ADAPTER):
        actual = file_reference(root, Path(root) / name)
        committed = subprocess.check_output(["git", "show", head + ":" + name], cwd=root)
        require(
            hashlib.sha256(committed).hexdigest() == actual["sha256"],
            "new_external_source_committed_before_prepare",
        )
        members.append(actual)
    return p.record(
        "budget_reevaluation_source_binding", root=str(root), head_commit=head, members=members
    )


def prepare(root):
    root = Path(root).resolve()
    p, original, adapter_module = modules(root)
    output = root / OUTPUT
    require(not output.exists(), "no_prepare_reexecution")
    parent_dir = root / PARENT_OUTPUT
    parent = p.checked(
        p.read_json(parent_dir / "preparation/execution_freeze.json"), "execution_freeze"
    )
    parent_report = p.checked(p.read_json(parent_dir / "report.json"), "execution_report")
    require(
        parent_report["actual_complete"] is True
        and parent_report["status"] == "COMPLETE_NO_POSITIVE_DIRECTION",
        "parent_remains_terminal",
    )
    public_rows = parent["evaluation_registry"]["dev"]
    require(
        len(public_rows) == 180
        and Counter(row["group"] for row in public_rows) == Counter(dict.fromkeys(GROUPS, 60)),
        "original_180_task_dev",
    )
    pilot_ids = select_pilot_tasks(public_rows)
    # Outcomes are opened only below this deterministic public-metadata selection.
    identities, parents = {}, []
    for seed in (11, 29, 47):
        for arm in ("alpha0", "plus", "minus"):
            name = f"A_{arm}_{seed}"
            generation = parent_dir / "generation/dev" / name
            score_path = parent_dir / "scores/dev" / name / "report.json"
            identity = p.checked(p.read_json(generation / "model_identity.json"), "model_identity")
            score = p.checked(p.read_json(score_path), "evaluation_report")
            training_path = parent_dir / "training" / name / "report.json"
            training = p.checked(p.read_json(training_path), "training_report")
            require(
                score["actual_complete"] is True
                and len(score["outcomes"]) == 180
                and score["model_identity_id"] == identity["id"],
                "complete_original_paired_score",
            )
            require(
                training["actual_complete"] is True
                and training["id"] == identity["training_report_id"]
                and training["checkpoint_id"] == identity["checkpoint_id"],
                "same_completed_student",
            )
            original.validate_model_identity(identity)
            identities[name] = identity
            parents.append(
                {
                    "model": name,
                    "training_report": file_reference(root, training_path),
                    "training_report_id": training["id"],
                    "generation_report": file_reference(root, generation / "report.json"),
                    "score_report": file_reference(root, score_path),
                    "score_report_id": score["id"],
                    "original_model_identity": identity,
                }
            )
    sources = source_capture(root, parent, p)
    adapted = adapter_module.build_adapter(pilot_ids, parent)
    decoder = adapted.bind_policy(parent["tokenizer_binding"], parent["base_binding"])
    require(
        {
            key: decoder["policy"][key]
            for key in ("max_responses", "max_tools", "max_new_tokens", "maximum_sequence_length")
        }
        == {
            "max_responses": 64,
            "max_tools": 64,
            "max_new_tokens": 4096,
            "maximum_sequence_length": 32768,
        },
        "exact_fixed_higher_budget",
    )
    plan = p.record(
        "budget_reevaluation_plan",
        created_at=p.now(),
        output_directory=OUTPUT,
        purpose="independent post-hoc budget sensitivity diagnostic; not original registered A/B continuation",
        parent_execution_report_id=parent_report["id"],
        parent_execution_freeze_id=parent["id"],
        parent_freeze=file_reference(root, parent_dir / "preparation/execution_freeze.json"),
        parent_report=file_reference(root, parent_dir / "report.json"),
        models=parents,
        public_dev_tasks=public_rows,
        public_selection_salt=SALT,
        pilot_task_ids=pilot_ids,
        pilot_selection="SHA256(salt + ':' + task_id) per group, lexicographic first three-distinct-source-cluster combination; no outcomes",
        pilot_company_clusters=[
            next(row["source_cluster"] for row in public_rows if row["task_id"] == task)
            for task in pilot_ids
        ],
        full_complement_task_ids=remaining_task_ids(public_rows, pilot_ids),
        pilot_sessions=27,
        full_unique_sessions=1620,
        additional_full_sessions=1593,
        decoder_configuration=decoder,
        original_decoder_configuration=parent["decoder_configuration"],
        source_binding=sources,
        GPU_UUIDs=list(GPU_UUIDS),
        minimum_free_memory_MiB=MINIMUM_FREE_MIB,
        GPU_utilization_must_be_zero=False,
        maximum_GPU_workers=8,
        one_worker_per_GPU=True,
        pilot_wall_limit_seconds=PILOT_WALL_SECONDS,
        pilot_clock_starts="first actual GPU worker process start",
        full_gate="all 27 pilot sessions and offline scores complete and at least one financial_valid true",
        zero_or_incomplete_gate="stop; do not claim larger budgets alone restore validity, preserve missing/censored denominator",
        no_automatic_retry=True,
        no_old_generation_repeated=True,
        no_training_or_B_release=True,
        original_results_overwritten=False,
        model_checkpoints_unchanged=True,
        initial_GPU_loads=0,
        private_outcomes_never_passed_to_generation=True,
    )
    p.write_once(output / "plan.json", plan)
    for name, identity in identities.items():
        fields = {
            key: value for key, value in identity.items() if key not in ("id", "schema_version")
        }
        fields.update(study_freeze_id=plan["id"], decoder_config_id=decoder["id"])
        p.write_once(output / "models" / (name + ".json"), p.record("model_identity", **fields))
    return plan


def proc_identity(pid):
    try:
        value = (Path("/proc") / str(pid) / "stat").read_text()
        fields = value[value.rfind(")") + 2 :].split()
        return {"pid": pid, "start_ticks": int(fields[19]), "state": fields[0]}
    except FileNotFoundError:
        return {"pid": pid, "start_ticks": None, "state": "gone"}


def available_gpus(used=()):
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
        index, uuid, free, utilization = [part.strip() for part in line.split(",")]
        if uuid in GPU_UUIDS and uuid not in used and int(free) >= MINIMUM_FREE_MIB:
            rows.append(
                {
                    "index": int(index),
                    "uuid": uuid,
                    "free_memory_MiB": int(free),
                    "utilization_percent": int(utilization),
                }
            )
    return sorted(rows, key=lambda row: row["index"])


def worker_generation(root, job_path, host_admission):
    """Spawn target gets only the public task subset and frozen decoder assets."""
    root = Path(root).resolve()
    job = json.loads(Path(job_path).read_bytes())
    os.environ.update(
        CUDA_VISIBLE_DEVICES=job["gpu"]["uuid"],
        OMP_NUM_THREADS="2",
        MKL_NUM_THREADS="2",
        OPENBLAS_NUM_THREADS="1",
        TOKENIZERS_PARALLELISM="false",
        CUBLAS_WORKSPACE_CONFIG=":4096:8",
    )
    output = root / job["generation_output"]
    with (
        (root / job["log_path"]).open("x", buffering=1) as stream,
        contextlib.redirect_stdout(stream),
        contextlib.redirect_stderr(stream),
    ):
        p, _original, adapter_module = modules(root)
        started = time.monotonic()
        try:
            value = job["public_input"]
            adapted = adapter_module.build_adapter(
                job["task_ids"], job["public_parent"], host_admission=host_admission
            )
            decoder = adapted.load_decoder(
                root,
                output / "decoder",
                value["model_identity"],
                value["base_binding"],
                value["tokenizer_binding"],
                value["decoder_configuration"],
            )
            report = adapted.generate(
                root,
                output,
                surface_directory=value["surface_directory"],
                surface_manifest_id=value["surface_manifest_id"],
                split="dev",
                model_identity=value["model_identity"],
                decoder=decoder,
                source_root=value["source_root"],
            )
            require(report["actual_complete"] is True, "complete_actual_generation")
            p.write_once(
                root / job["worker_result"],
                p.record(
                    "budget_generation_worker_result",
                    actual_complete=True,
                    job_id=job["id"],
                    generation_report_id=report["id"],
                    process_id=os.getpid(),
                    finished_at=p.now(),
                    elapsed_seconds=time.monotonic() - started,
                    actual_base_verification_mode=adapted.actual_base_verification_mode,
                    adapter_transform_id=adapted.transform_provenance["id"],
                ),
            )
        except BaseException as error:
            traceback.print_exc()
            p.write_once(
                root / job["worker_result"],
                p.record(
                    "budget_generation_worker_result",
                    actual_complete=False,
                    job_id=job["id"],
                    process_id=os.getpid(),
                    finished_at=p.now(),
                    elapsed_seconds=time.monotonic() - started,
                    error_type=type(error).__name__,
                    error=str(error),
                    retry=False,
                ),
            )
            raise


def worker_score(root, job_path):
    root = Path(root).resolve()
    p, _original, adapter_module = modules(root)
    job = p.read_json(job_path)
    with (
        (root / job["log_path"]).open("x", buffering=1) as stream,
        contextlib.redirect_stdout(stream),
        contextlib.redirect_stderr(stream),
    ):
        try:
            adapted = adapter_module.build_adapter(job["task_ids"], job["public_parent"])
            generation = root / job["generation_output"]
            manifest = p.read_json(generation / "manifest.json")
            report = adapted.score(
                root,
                generation,
                root / job["score_output"],
                expected_generation_manifest_id=manifest["id"],
            )
            require(report["actual_complete"] is True, "complete_actual_offline_score")
        except BaseException:
            traceback.print_exc()
            raise


def stop_own_workers(running, p, reason):
    """Only live children with the captured PID start time can receive a signal."""
    actions = []
    for name, current in running.items():
        process, captured = current["process"], current["identity"]
        if not process.is_alive():
            continue
        actual = proc_identity(process.pid)
        require(
            actual["start_ticks"] == captured["start_ticks"] and actual["pid"] == captured["pid"],
            "only_identical_owned_child_signal",
        )
        os.kill(process.pid, signal.SIGTERM)
        actions.append(
            {
                "model": name,
                "pid": process.pid,
                "start_ticks": actual["start_ticks"],
                "signal": "SIGTERM",
                "reason": reason,
            }
        )
    deadline = time.monotonic() + 10
    for current in running.values():
        process = current["process"]
        process.join(max(0, deadline - time.monotonic()))
        if process.is_alive():
            actual = proc_identity(process.pid)
            require(
                actual["start_ticks"] == current["identity"]["start_ticks"],
                "same_owned_child_before_KILL",
            )
            os.kill(process.pid, signal.SIGKILL)
            process.join(5)
            actions.append({"pid": process.pid, "signal": "SIGKILL", "reason": reason})
    return actions


def run_generation(
    root, plan, parent, phase, task_ids, host_admission, pilot_clock, p, original, owned_workers
):
    stage = root / OUTPUT / phase
    directory = stage / "jobs"
    require(not directory.exists(), "no_phase_retry")
    directory.mkdir(parents=True)
    require(not owned_workers, "no_live_workers_from_prior_phase")
    pending, running, finished, failures, stopped = (
        [row["model"] for row in plan["models"]],
        owned_workers,
        [],
        [],
        [],
    )
    started = time.monotonic()
    censored = False
    context = multiprocessing.get_context("spawn")
    adapter_module = modules(root)[2]
    public_parent = adapter_module.public_parent_binding(parent)
    while pending or running:
        for name, current in list(running.items()):
            process = current["process"]
            if process.is_alive():
                continue
            process.join()
            result = p.record(
                "budget_worker_exit",
                model=name,
                phase=phase,
                pid=process.pid,
                return_code=process.exitcode,
                GPU=current["gpu"],
                finished_at=p.now(),
            )
            p.write_once(directory / (name + "_exit.json"), result)
            (finished if process.exitcode == 0 else failures).append(result)
            del running[name]
        if (
            phase == "pilot"
            and pilot_clock["first_started_monotonic"] is not None
            and time.monotonic() - pilot_clock["first_started_monotonic"] >= PILOT_WALL_SECONDS
            and (pending or running)
        ):
            censored = True
            stopped = stop_own_workers(running, p, "PILOT_90_MINUTE_WALL_LIMIT")
            for name, current in running.items():
                result = p.record(
                    "budget_worker_exit",
                    model=name,
                    phase=phase,
                    pid=current["process"].pid,
                    return_code=current["process"].exitcode,
                    finished_at=p.now(),
                    censored=True,
                )
                p.write_once(directory / (name + "_exit.json"), result)
                failures.append(result)
            running.clear()
            break
        if pending and not failures:
            free = available_gpus({row["gpu"]["uuid"] for row in running.values()})
            while pending and free and len(running) < 8:
                name, gpu = pending.pop(0), free.pop(0)
                identity = p.read_json(root / OUTPUT / "models" / (name + ".json"))
                value = {
                    "model_identity": identity,
                    "base_binding": parent["base_binding"],
                    "tokenizer_binding": parent["tokenizer_binding"],
                    "decoder_configuration": plan["decoder_configuration"],
                    "source_root": parent["source_root"],
                    "surface_directory": original.SURFACE_DIRECTORY,
                    "surface_manifest_id": original.SURFACE_MANIFEST_ID,
                }
                job = p.record(
                    "budget_generation_job",
                    plan_id=plan["id"],
                    model=name,
                    phase=phase,
                    task_ids=task_ids,
                    gpu=gpu,
                    public_input=value,
                    public_parent=public_parent,
                    generation_output=str((stage / "generation" / name).relative_to(root)),
                    log_path=str((directory / (name + ".log")).relative_to(root)),
                    worker_result=str((directory / (name + "_result.json")).relative_to(root)),
                    source_binding_id=plan["source_binding"]["id"],
                    launched_at=p.now(),
                )
                path = directory / (name + "_job.json")
                p.write_once(path, job)
                process = context.Process(
                    target=worker_generation,
                    args=(str(root), str(path), host_admission),
                    name="budget-" + phase + "-" + name,
                )
                try:
                    process.start()
                except Exception as error:
                    failure = p.record(
                        "budget_worker_spawn_failure",
                        model=name,
                        error_type=type(error).__name__,
                        error=str(error),
                        retry=False,
                    )
                    p.write_once(directory / (name + "_spawn_failure.json"), failure)
                    failures.append(failure)
                    break
                captured = proc_identity(process.pid)
                require(captured["start_ticks"] is not None, "spawned_worker_identity_captured")
                running[name] = {"process": process, "identity": captured, "gpu": gpu}
                p.write_once(
                    directory / (name + "_started.json"),
                    p.record(
                        "budget_worker_started",
                        model=name,
                        phase=phase,
                        process=captured,
                        gpu=gpu,
                        at=p.now(),
                    ),
                )
                if phase == "pilot" and pilot_clock["first_started_monotonic"] is None:
                    pilot_clock["first_started_monotonic"] = time.monotonic()
                    p.write_once(
                        stage / "first_worker_started.json",
                        p.record(
                            "budget_pilot_clock",
                            first_worker_pid=process.pid,
                            at=p.now(),
                            wall_limit_seconds=PILOT_WALL_SECONDS,
                        ),
                    )
        if failures and not running:
            break
        if pending or running:
            time.sleep(10)
    report = p.record(
        "budget_generation_phase",
        plan_id=plan["id"],
        phase=phase,
        actual_complete=not failures and not pending and not censored,
        planned_models=9,
        tasks_per_model=len(task_ids),
        completed_workers=finished,
        failures=failures,
        not_started=pending,
        stopped_owned_workers=stopped,
        status="CENSORED_PILOT_WALL_LIMIT"
        if censored
        else "COMPLETE"
        if not failures and not pending
        else "INCOMPLETE_WORKER_FAILURE",
        elapsed_seconds=time.monotonic() - started,
        automatic_retry=False,
    )
    p.write_once(stage / "generation_phase.json", report)
    return report


def run_scores(root, plan, parent, phase, task_ids, p, owned_workers, deadline=None):
    stage = root / OUTPUT / phase
    directory = stage / "score_jobs"
    directory.mkdir(parents=True, exist_ok=False)
    context, workers = multiprocessing.get_context("spawn"), []
    public_parent = modules(root)[2].public_parent_binding(parent)
    for item in plan["models"]:
        if deadline is not None and time.monotonic() >= deadline:
            break
        name = item["model"]
        generation = stage / "generation" / name
        if not (generation / "report.json").exists():
            continue
        generated = p.read_json(generation / "report.json")
        if generated.get("actual_complete") is not True:
            continue
        job = p.record(
            "budget_score_job",
            model=name,
            plan_id=plan["id"],
            task_ids=task_ids,
            public_parent=public_parent,
            generation_output=str(generation.relative_to(root)),
            score_output=str((stage / "scores" / name).relative_to(root)),
            log_path=str((directory / (name + ".log")).relative_to(root)),
        )
        path = directory / (name + "_job.json")
        p.write_once(path, job)
        process = context.Process(
            target=worker_score, args=(str(root), str(path)), name="budget-score-" + name
        )
        process.start()
        owned_workers[name] = {"process": process, "identity": proc_identity(process.pid)}
        workers.append((name, process))
    results = []
    for name, process in workers:
        process.join(None if deadline is None else max(0, deadline - time.monotonic()))
        if process.is_alive():
            stopped = stop_own_workers(
                owned_workers, p, "PILOT_90_MINUTE_WALL_LIMIT_DURING_SCORING"
            )
            p.write_once(
                stage / "scoring_censored.json",
                p.record(
                    "budget_scoring_censored",
                    plan_id=plan["id"],
                    stopped_owned_workers=stopped,
                    at=p.now(),
                ),
            )
        p.write_once(
            directory / (name + "_exit.json"),
            p.record(
                "budget_score_worker_exit",
                model=name,
                pid=process.pid,
                return_code=process.exitcode,
                finished_at=p.now(),
            ),
        )
        if process.exitcode == 0:
            results.append(p.read_json(stage / "scores" / name / "report.json"))
        owned_workers.pop(name, None)
    p.write_once(
        stage / "score_phase.json",
        p.record(
            "budget_score_phase",
            plan_id=plan["id"],
            phase=phase,
            actual_complete=len(results) == 9,
            completed_models=len(results),
            process_count=len(workers),
            same_generation_process=False,
        ),
    )
    return results


def session_metrics(root, generation, outcome, p):
    result = p.read_json(generation / "sessions" / outcome["task_id"] / "result.json")
    # Saved runtime Final parsing, not free-text string matching or presumed correctness.
    session = p.read_json(generation / result["runtime_session_path"])
    return {
        "financial_valid": outcome["financial_valid"],
        "recognized_Final": session["first_final_index"] is not None,
        "reason": outcome["reason"],
        "terminal": outcome["runtime_terminal"],
        "context_rejected": outcome["context_rejected"],
        "resource_usage": result["resource_delta"],
        "generation_result_id": result["id"],
        "assessment_id": outcome["assessment_id"],
    }


def comparison(root, plan, phases, task_ids, p):
    pairs = []
    for model in plan["models"]:
        name = model["model"]
        old_score = p.read_json(root / model["score_report"]["path"])
        require(old_score["id"] == model["score_report_id"], "original_score_identity_unchanged")
        old = {row["task_id"]: row for row in old_score["outcomes"]}
        completed = {}
        for phase in phases:
            path = root / OUTPUT / phase / "scores" / name / "report.json"
            if not path.exists():
                continue
            for row in p.read_json(path)["outcomes"]:
                require(row["task_id"] not in completed, "pilot_never_regenerated_in_full")
                completed[row["task_id"]] = (phase, row)
        for task_id in task_ids:
            old_metrics = session_metrics(
                root, root / PARENT_OUTPUT / "generation/dev" / name, old[task_id], p
            )
            if task_id in completed:
                phase, row = completed[task_id]
                new_metrics = session_metrics(
                    root, root / OUTPUT / phase / "generation" / name, row, p
                )
            else:
                new_metrics = None
            pairs.append(
                {
                    "model": name,
                    "task_id": task_id,
                    "group": old[task_id]["group"],
                    "source_cluster": old[task_id]["source_cluster"],
                    "old": old_metrics,
                    "higher_budget": new_metrics,
                }
            )

    def aggregate(which):
        rows = [row[which] for row in pairs if row[which] is not None]
        resources = Counter()
        for row in rows:
            resources.update(
                {
                    key: value
                    for key, value in row["resource_usage"].items()
                    if type(value) in (int, float)
                }
            )
        return {
            "planned_sessions": len(pairs),
            "completed_scored_sessions": len(rows),
            "missing_or_censored_sessions": len(pairs) - len(rows),
            "recognized_Final": sum(row["recognized_Final"] for row in rows),
            "financial_valid": sum(row["financial_valid"] for row in rows),
            "no_Final": sum(not row["recognized_Final"] for row in rows),
            "terminal_counts": dict(Counter(row["terminal"] for row in rows)),
            "context_rejected": sum(row["context_rejected"] for row in rows),
            "resource_usage": dict(resources),
            "recognized_Final_rate_of_planned": sum(row["recognized_Final"] for row in rows)
            / len(pairs),
            "financial_valid_rate_of_planned": sum(row["financial_valid"] for row in rows)
            / len(pairs),
        }

    return p.record(
        "budget_paired_comparison",
        plan_id=plan["id"],
        phases=phases,
        unique_tasks=len(task_ids),
        paired_sessions=len(pairs),
        old_budget=aggregate("old"),
        higher_budget=aggregate("higher_budget"),
        pairs=pairs,
        same_nine_checkpoints=True,
        no_old_sessions_regenerated=True,
        missing_not_claimed_complete=True,
        rates_not_independent_VTDO_effect_estimates=True,
        decoder_callback_elapsed_not_reparsed=True,
        timing_scope="new worker and phase wall clocks only; old callback files are not rescanned for incomparable hardware timing",
    )


def write_summary(root, plan, result, p):
    report = root / SUMMARY
    require(not report.exists(), "summary_no_overwrite")
    payload = result.get("comparison", {})
    old, new = payload.get("old_budget", {}), payload.get("higher_budget", {})
    text = f"""# 固定材料实验：提高预算后的独立复评实测记录（2026-09-15）

本记录是事后预算敏感性诊断，不替换原实验结果，不重新选择方法方向，不授权 B 训练。

- 计划：`{plan["id"]}`。
- 结束状态：`{result["status"]}`；时间：`{result["finished_at"]}`。
- 旧预算：每会话 32 次响应 / 32 次工具调用，每次 2,048 新 token，序列上限 24,576。
- 新预算：每会话 64 次响应 / 64 次工具调用，每次 4,096 新 token，序列硬上限 32,768；不裁剪历史，不自动续写或重试。
- 模型：原 A 阶段 9 个最终检查点不变；greedy、neutral、工具与评分语义不变。
- Pilot：3 个公开任务，三组各 1 题；基于预先固定 salt 与任务 ID 排序，尽可能不同公司，不依据旧 outcome 选样。完整 27 会话至少出现 1 个财务合格结果，才自动补充其余 177 题 × 9 模型；pilot 会话不重生成。
- Pilot 时限：首个 GPU worker 实际启动后 90 分钟。超时仅终止本诊断自己的新 worker，缺失或截尾结果不冒充完整结果。

## 实测汇总

| 指标 | 原预算（复用既有记录） | 提高预算 |
|---|---:|---:|
| 计划会话 | {old.get("planned_sessions", "NA（未汇总）")} | {new.get("planned_sessions", "NA（未汇总）")} |
| 已完成并评分 | {old.get("completed_scored_sessions", "NA（未汇总）")} | {new.get("completed_scored_sessions", "NA（未汇总）")} |
| 识别到 Final | {old.get("recognized_Final", "NA（未汇总）")} | {new.get("recognized_Final", "NA（未汇总）")} |
| 财务合格 | {old.get("financial_valid", "NA（未汇总）")} | {new.get("financial_valid", "NA（未汇总）")} |
| 缺失/截尾 | {old.get("missing_or_censored_sessions", "NA（未汇总）")} | {new.get("missing_or_censored_sessions", "NA（未汇总）")} |

原预算终态计数：`{json.dumps(old.get("terminal_counts", {}), ensure_ascii=False, sort_keys=True)}`。

新预算终态计数：`{json.dumps(new.get("terminal_counts", {}), ensure_ascii=False, sort_keys=True)}`。

逐模型、逐任务配对结果与生成 token / callback 等资源计数见独立输出目录的 comparison 与 report。实际新 worker / phase 墙钟耗时见 jobs 与 generation_phase；不重复扫描旧 callback 大文件来构造硬件条件不可比的耗时比。

## 结论边界

若完整 pilot 财务合格数为零，只能说明这一固定小样本上提高到当前预算未恢复财务合格输出，不能证明更高预算普遍无效，也不能证明财务计算均错误。若 pilot 不完整或超时，结论是不确定而非零效果。若通过门控并完成 1,620 会话，仍属于改变评估预算后的独立结果，不等同原注册实验的确认试验，更不能单凭本诊断声称 VTDO 有效。

## 保存和发布范围

所有原实验文件保持不变。新原始生成文本、token ID、callback 收据、会话、manifest 与评分附件保留在本地 `{root / OUTPUT}`。远端仅提交计划、模型身份、逐模型 generation / score 汇总、配对比较、进程收口、总报告与本说明；不推送每个 callback 的大 JSON / token 原文或逐文件 manifest。远端汇总引用的原始文件仅保存在本地，不表示全部原始内容已发布。
"""
    report.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive documentation creation is an application output, never source editing.
    with report.open("x") as stream:
        stream.write(text)


def publish_small(root, plan, p):
    output = root / OUTPUT
    paths = [
        path
        for path in output.rglob("*.json")
        if (
            path.parent == output
            or path.parent.name == "models"
            or path.name
            in (
                "report.json",
                "model_identity.json",
                "decoder_config.json",
                "model_load_receipt.json",
                "registration.json",
                "generation_phase.json",
                "score_phase.json",
                "comparison.json",
                "first_worker_started.json",
                "gate.json",
                "scoring_censored.json",
            )
            and "decoder" not in path.relative_to(output).parts
            and "sessions" not in path.relative_to(output).parts
            and "assessments" not in path.relative_to(output).parts
            or path.parent.name in ("jobs", "score_jobs")
            and path.name.endswith(("_exit.json", "_result.json", "_started.json"))
        )
    ]
    paths.append(root / SUMMARY)
    require(
        all(path.stat().st_size < 20 * 1024 * 1024 for path in paths),
        "small_publication_files_only",
    )
    paths = sorted({str(path.relative_to(root)) for path in paths})
    staged = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only"], cwd=root, text=True
    ).splitlines()
    require(set(staged) <= set(paths), "do_not_commit_unrelated_staged_changes")
    subprocess.run(["git", "add", "--sparse", "--force", "--", *paths], cwd=root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Report independent higher-budget reevaluation results"],
        cwd=root,
        check=True,
    )
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    subprocess.run(
        ["git", "push", "https://github.com/haoyueliuzhao/Data-Synthesis.git", "HEAD:main"],
        cwd=root,
        check=True,
    )
    p.write_once(
        root / RUNTIME / "publication.json",
        p.record(
            "budget_publication",
            plan_id=plan["id"],
            commit=commit,
            remote="https://github.com/haoyueliuzhao/Data-Synthesis.git",
            ref="main",
            files=paths,
            raw_decoder_files_published=False,
            automatic_retry=False,
            completed_at=p.now(),
        ),
    )


def run(root):
    root = Path(root).resolve()
    p, original, adapter_module = modules(root)
    output = root / OUTPUT
    plan = p.checked(p.read_json(output / "plan.json"), "budget_reevaluation_plan")
    require(plan["source_binding"]["root"] == str(root), "frozen_execution_root")
    for row in plan["source_binding"]["members"]:
        require(
            file_reference(root, root / row["path"])["sha256"] == row["sha256"],
            "frozen_source_bytes_before_run",
        )
    parent = p.checked(p.read_json(root / plan["parent_freeze"]["path"]), "execution_freeze")
    require(parent["id"] == plan["parent_execution_freeze_id"], "same_parent_freeze")
    p.write_once(
        output / "started.json",
        p.record(
            "budget_reevaluation_started",
            plan_id=plan["id"],
            at=p.now(),
            process=proc_identity(os.getpid()),
            source_binding_id=plan["source_binding"]["id"],
        ),
    )
    started = time.monotonic()
    result, pilot_clock, owned_workers = None, {"first_started_monotonic": None}, {}
    try:
        # CPU-only SHA admission once; object can only enter workers by trusted spawn.
        host_admission = adapter_module.make_host_admission(parent["base_binding"])
        pilot = run_generation(
            root,
            plan,
            parent,
            "pilot",
            plan["pilot_task_ids"],
            host_admission,
            pilot_clock,
            p,
            original,
            owned_workers,
        )
        pilot_deadline = (
            pilot_clock["first_started_monotonic"] + PILOT_WALL_SECONDS
            if pilot_clock["first_started_monotonic"] is not None
            else time.monotonic()
        )
        scores = run_scores(
            root,
            plan,
            parent,
            "pilot",
            plan["pilot_task_ids"],
            p,
            owned_workers,
            deadline=pilot_deadline,
        )
        gate = decide_next_stage(scores)
        if pilot["actual_complete"] is not True:
            gate = "INCOMPLETE_PILOT"
        pilot_comparison = comparison(root, plan, ["pilot"], plan["pilot_task_ids"], p)
        p.write_once(output / "pilot/comparison.json", pilot_comparison)
        p.write_once(
            output / "pilot/gate.json",
            p.record(
                "budget_pilot_gate",
                plan_id=plan["id"],
                status=gate,
                score_report_ids=[row["id"] for row in scores],
                qualified=pilot_comparison["higher_budget"]["financial_valid"],
                no_training_or_B_release=True,
            ),
        )
        full = None
        if gate == "FULL_DEV_REEVALUATION":
            full = run_generation(
                root,
                plan,
                parent,
                "full_complement",
                plan["full_complement_task_ids"],
                host_admission,
                pilot_clock,
                p,
                original,
                owned_workers,
            )
            full_scores = run_scores(
                root,
                plan,
                parent,
                "full_complement",
                plan["full_complement_task_ids"],
                p,
                owned_workers,
            )
            compared = comparison(
                root,
                plan,
                ["pilot", "full_complement"],
                [row["task_id"] for row in plan["public_dev_tasks"]],
                p,
            )
            complete = (
                full["actual_complete"]
                and len(full_scores) == 9
                and compared["higher_budget"]["completed_scored_sessions"] == 1620
            )
            status = (
                "COMPLETE_INDEPENDENT_FULL_BUDGET_REEVALUATION"
                if complete
                else "INCOMPLETE_FULL_REEVALUATION"
            )
        else:
            compared = pilot_comparison
            status = (
                "COMPLETE_PILOT_ZERO_QUALIFIED"
                if gate == "STOP_ZERO_QUALIFIED"
                else "INCOMPLETE_OR_CENSORED_PILOT"
            )
        p.write_once(output / "comparison.json", compared)
        result = p.record(
            "budget_reevaluation_report",
            plan_id=plan["id"],
            status=status,
            actual_complete=status
            in ("COMPLETE_INDEPENDENT_FULL_BUDGET_REEVALUATION", "COMPLETE_PILOT_ZERO_QUALIFIED"),
            pilot_gate=gate,
            comparison=compared,
            pilot_generation_phase_id=pilot["id"],
            full_generation_phase_id=full["id"] if full else None,
            elapsed_seconds=time.monotonic() - started,
            finished_at=p.now(),
            original_experiment_unchanged=True,
            no_training_or_B_release=True,
            diagnostic_not_VTDO_confirmation=True,
        )
    except Exception as error:
        traceback.print_exc()
        stopped = stop_own_workers(owned_workers, p, "COORDINATOR_DIAGNOSTIC_ERROR")
        result = p.record(
            "budget_reevaluation_report",
            plan_id=plan["id"],
            status="STOP_DIAGNOSTIC_ERROR",
            actual_complete=False,
            error_type=type(error).__name__,
            error=str(error),
            stopped_owned_workers=stopped,
            elapsed_seconds=time.monotonic() - started,
            finished_at=p.now(),
            original_experiment_unchanged=True,
            no_training_or_B_release=True,
            retry=False,
        )
    p.write_once(output / "report.json", result)
    write_summary(root, plan, result, p)
    try:
        publish_small(root, plan, p)
    except Exception as error:
        p.write_once(
            root / RUNTIME / "publication_failure.json",
            p.record(
                "budget_publication_failure",
                plan_id=plan["id"],
                error_type=type(error).__name__,
                error=str(error),
                automatic_retry=False,
                at=p.now(),
            ),
        )
        raise
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "run"))
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    result = prepare(args.root) if args.phase == "prepare" else run(args.root)
    print(
        json.dumps(
            {"id": result["id"], "status": result.get("status", "PREPARED")}, ensure_ascii=False
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
