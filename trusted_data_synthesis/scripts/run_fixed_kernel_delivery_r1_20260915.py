"""One frozen R1 matrix: 60 complete sessions and 60 public-history continuations.

Each GPU worker restores one checkpoint once, runs both prospectively ordered
documentation conditions, then makes six independent single-step predictions.
Only after all GPU children exit do separate CPU workers obtain offline scoring
capabilities. No original experiment, source module, training, or B is modified.
"""

import argparse
import contextlib
import importlib
import json
import multiprocessing
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

PACKAGE = "trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value"
BASE = "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value"
OUTPUT = BASE + "/delivery_r1_contrast_20260915"
PARENT = BASE + "/parallel_tail_execution_20260914"
PILOT = BASE + "/budget_reevaluation_20260915"
DIAGNOSTIC = BASE + "/delivery_diagnostic_20260915"
SCRIPT = "trusted_data_synthesis/scripts/run_fixed_kernel_delivery_r1_20260915.py"
SUMMARY = "trusted_data_synthesis/docs/fixed_kernel_delivery_r1_actual_results_20260915.md"
RUNTIME = "trusted_data_synthesis/runtime/fixed_kernel_delivery_r1_20260915"
AUDIT_SHA = "12a65a825a738d5524912a6f85ad3fe45f92298543f528f024e375e6ed35f309"
CONDITIONS = ("original", "gamma_doc")
MINIMUM_FREE_MIB = 24576
MAX_GPU_WORKERS = 8
MAX_MODEL_CALLS = 1980
NEW_SCRIPTS = (
    SCRIPT,
    "trusted_data_synthesis/scripts/fixed_kernel_delivery_r1_adapter_20260915.py",
    "trusted_data_synthesis/scripts/fixed_kernel_delivery_prefix_semantics_20260915.py",
    "trusted_data_synthesis/scripts/fixed_kernel_delivery_r1_report_20260915.py",
)
REUSED_SCRIPTS = (
    "trusted_data_synthesis/scripts/fixed_kernel_delivery_diagnostic_adapter_20260915.py",
    "trusted_data_synthesis/scripts/fixed_kernel_query_null_repair_20260915.py",
    "trusted_data_synthesis/scripts/fixed_kernel_delivery_failure_ledger_20260915.py",
    "trusted_data_synthesis/scripts/run_fixed_kernel_budget_reevaluation_20260915.py",
    "trusted_data_synthesis/scripts/fixed_kernel_budget_reevaluation_adapter_20260915.py",
)


def require(value, message):
    if not value:
        raise ValueError("delivery_r1." + message)


def modules(root):
    root = Path(root).resolve()
    for relative in (
        "trusted_data_synthesis/src",
        "raw_financial_data_lake",
        "trusted_data_synthesis/scripts",
    ):
        path = str(root / relative)
        if path not in sys.path:
            sys.path.insert(0, path)
    return (
        importlib.import_module(PACKAGE + ".protocol"),
        importlib.import_module(PACKAGE + ".evaluation"),
        importlib.import_module("fixed_kernel_delivery_r1_adapter_20260915"),
        importlib.import_module("run_fixed_kernel_budget_reevaluation_20260915"),
    )


def matrix_models():
    keys = ["unfinetuned_base"] + [
        f"A_{arm}_{seed}" for seed in (11, 29, 47) for arm in ("alpha0", "plus", "minus")
    ]
    return [
        {
            "key": key,
            "model_kind": "unfinetuned_base" if index == 0 else "finetuned",
            "condition_order": list(CONDITIONS if index % 2 == 0 else reversed(CONDITIONS)),
            "queue_index": index,
        }
        for index, key in enumerate(keys)
    ]


def eligible_gpus(raw, allowed, used=()):
    rows = []
    for line in raw.splitlines():
        index, uuid, free, utilization = [part.strip() for part in line.split(",")]
        if uuid in allowed and uuid not in used and int(free) >= MINIMUM_FREE_MIB:
            rows.append(
                dict(
                    index=int(index),
                    uuid=uuid,
                    free_memory_MiB=int(free),
                    utilization_percent=int(utilization),
                )
            )
    return sorted(rows, key=lambda row: row["index"])


def prepare(root):
    root = Path(root).resolve()
    p, original, adapter_module, previous = modules(root)
    output = root / OUTPUT
    require(not (output / "plan.json").exists(), "no_second_freeze")
    parent = p.checked(
        p.read_json(root / PARENT / "preparation/execution_freeze.json"), "execution_freeze"
    )
    pilot = p.checked(p.read_json(root / PILOT / "plan.json"), "budget_reevaluation_plan")
    stage_b = p.checked(
        p.read_json(root / DIAGNOSTIC / "stage_B/report.json"), "delivery_stage_B_report"
    )
    require(stage_b["status"] == "PASS_AS_SCOPED", "existing_B_closed_as_scoped")
    task_ids = pilot["pilot_task_ids"]
    require(len(task_ids) == len(set(task_ids)) == 3, "same_three_fixed_tasks")
    prefixes = stage_b["public_prefixes"]
    require(
        len(prefixes) == 6 and len({row["id"] for row in prefixes}) == 6,
        "six_existing_frozen_prefixes",
    )
    preflight = p.read_json(output / "preflight/report.json")
    require(preflight.get("actual_complete") is True, "R1_wiring_and_three_roundtrips_passed")
    require(
        preflight["adapter_source_sha256"] == p.sha(root / NEW_SCRIPTS[1]),
        "preflight_uses_current_R1_adapter",
    )
    require(
        preflight["task_ids"] == task_ids
        and preflight["snapshot_files_read"] == 3
        and len(preflight["outcomes"]) == 3
        and all(
            row["status"] == "PASS_QUERY_RETURNED_POINTER_NUMERIC_READ"
            for row in preflight["outcomes"]
        ),
        "three_registered_source_roundtrips",
    )
    prefix_control = p.read_json(output / "preflight/prefix_semantics_binding.json")
    require(
        prefix_control["status"] == "PASS_AS_SCOPED"
        and prefix_control["grader_sha256"] == p.sha(root / NEW_SCRIPTS[2])
        and prefix_control["synthetic_reference_replays"] == 6
        and prefix_control["Student_capability_result"] is False,
        "six_public_prefix_grader_bindings_not_Student_results",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = []
    for path in (*NEW_SCRIPTS, *REUSED_SCRIPTS):
        reference = previous.file_reference(root, root / path)
        committed = subprocess.check_output(["git", "show", head + ":" + path], cwd=root)
        require(p.sha(committed) == reference["sha256"], "committed_execution_sources:" + path)
        sources.append(reference)
    adapters = {
        condition: adapter_module.build_adapter(task_ids, parent, condition)
        for condition in CONDITIONS
    }
    configurations = {
        condition: ad.bind_policy(parent["tokenizer_binding"], parent["base_binding"])
        for condition, ad in adapters.items()
    }
    for ad in adapters.values():
        require(
            tuple(
                ad.policy()[key]
                for key in (
                    "max_responses",
                    "max_tools",
                    "max_new_tokens",
                    "maximum_sequence_length",
                )
            )
            == (32, 32, 2048, 24576),
            "original_response_tool_token_context_limits",
        )
    models = matrix_models()
    parents = {row["model"]: row for row in pilot["models"]}
    for model in models:
        model["original_model_identity"] = (
            None
            if model["model_kind"] == "unfinetuned_base"
            else parents[model["key"]]["original_model_identity"]
        )
        model["checkpoint_id"] = (
            adapters["original"].base_checkpoint_identity["id"]
            if model["model_kind"] == "unfinetuned_base"
            else model["original_model_identity"]["checkpoint_id"]
        )
    plan = p.record(
        "delivery_r1_plan",
        created_at=p.now(),
        user_audit_sha256=AUDIT_SHA,
        explicit_user_request="参照审计继续实验：同R1两说明十模型三题及六前缀固定对照",
        parent_execution_freeze_id=parent["id"],
        parent_freeze=previous.file_reference(
            root, root / PARENT / "preparation/execution_freeze.json"
        ),
        prior_pilot_plan_id=pilot["id"],
        stage_B_report_id=stage_b["id"],
        previous_gate_preserved="AB_COMPLETE_QUERY_REPAIR_COMPLETE_C_NOT_RELEASED",
        independent_successor_not_edit_of_previous_C=True,
        task_ids=task_ids,
        unique_development_tasks=3,
        models=models,
        prefixes=prefixes,
        conditions=list(CONDITIONS),
        decoder_configurations=configurations,
        adapter_transforms={
            condition: ad.transform_provenance for condition, ad in adapters.items()
        },
        preflight=previous.file_reference(root, output / "preflight/report.json"),
        prefix_semantics_binding_control=previous.file_reference(
            root, output / "preflight/prefix_semantics_binding.json"
        ),
        full_sessions=60,
        single_prefix_responses=60,
        maximum_model_generation_calls=MAX_MODEL_CALLS,
        increase_over_old_C=dict(complete_sessions=27, maximum_model_generation_calls=864),
        R0_new_model_generations=0,
        original_experiment_results_overwritten=False,
        condition_order="prospective alternating order by fixed model queue index; five each order",
        one_physical_model_and_tokenizer_load_per_worker=True,
        every_session_has_fresh_history_results_and_generation_cache=True,
        prefix_reference_never_sent_to_model=True,
        prefix_semantics_separate_from_autonomous_financial_qualification=True,
        source_binding=dict(root=str(root), head_commit=head, members=sources),
        GPU_UUIDs=list(previous.GPU_UUIDS),
        maximum_GPU_workers=MAX_GPU_WORKERS,
        minimum_free_memory_MiB=MINIMUM_FREE_MIB,
        GPU_utilization_must_be_zero=False,
        memory_admission_basis=dict(
            estimated_BF16_parameter_bytes=7615616512 * 2,
            estimated_maximum_KV_bytes=28 * 2 * 4 * 128 * 24576 * 2,
            estimate_not_measured_peak=True,
            flash_attention_and_logits_to_keep_one_unchanged=True,
        ),
        no_response_retry=True,
        no_outcome_dependent_early_stop_or_expansion=True,
        no_new_training_or_B_or_confirmation=True,
        full_dev_1593_requires_separate_authorization=True,
        historical_R0_summary_path=PILOT + "/comparison.json",
        publication=(
            "exact small plan/report/documentation only; no callback/session/prefix raw payload"
        ),
    )
    p.write_once(output / "plan.json", plan)
    for model in models:
        for condition, ad in adapters.items():
            identity = ad.make_model_identity(
                model["original_model_identity"], plan["id"], condition
            )
            p.write_once(output / "models" / condition / (model["key"] + ".json"), identity)
    return plan


def worker_generate(root, job_path, host_admission):
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
    folder = root / OUTPUT / "workers" / job["model_key"]
    with (
        (folder / "generation.log").open("x", buffering=1) as stream,
        contextlib.redirect_stdout(stream),
        contextlib.redirect_stderr(stream),
    ):
        p, original, adapter_module, _ = modules(root)
        started, decoder, reports, predictions = time.monotonic(), None, {}, []
        error, peak = None, None
        try:
            for condition in job["condition_order"]:
                ad = adapter_module.build_adapter(
                    job["task_ids"], job["public_parent"], condition, host_admission=host_admission
                )
                value = job["conditions"][condition]
                generation = root / OUTPUT / "generation" / condition / job["model_key"]
                if decoder is None:
                    decoder = ad.load_decoder(
                        root,
                        generation / "decoder",
                        value["identity"],
                        job["public_parent"]["base_binding"],
                        job["public_parent"]["tokenizer_binding"],
                        value["configuration"],
                    )
                else:
                    decoder = ad.reuse_decoder(
                        decoder,
                        root,
                        generation / "decoder",
                        value["identity"],
                        value["configuration"],
                    )
                generated = ad.generate(
                    root,
                    generation,
                    surface_directory=original.SURFACE_DIRECTORY,
                    surface_manifest_id=original.SURFACE_MANIFEST_ID,
                    split="dev",
                    model_identity=value["identity"],
                    decoder=decoder,
                    source_root=job["source_root"],
                )
                reports[condition] = dict(
                    path=str((generation / "report.json").relative_to(root)), id=generated["id"]
                )
                require(
                    generated["actual_complete"] is True, "actual_three_session_generation_complete"
                )
            # Prefix history is independent of either condition: no Gamma_doc or
            # complete-session history is added by predict_prefix.
            for prefix in job["prefixes"]:
                record = p.read_json(root / prefix["path"])
                require(record["id"] == prefix["id"], "existing_prefix_identity")
                target = (
                    root
                    / OUTPUT
                    / "prefix"
                    / job["model_key"]
                    / (prefix["family"] + "_" + prefix["prefix_kind"])
                )
                prediction = ad.predict_prefix(decoder, record, target)
                predictions.append(
                    dict(
                        prefix_id=prefix["id"],
                        prediction_path=str((target / "result.json").relative_to(root)),
                        prediction_id=prediction["id"],
                    )
                )
                require(prediction["error"] is None, "prefix_model_not_faulted")
            import torch

            peak = dict(
                allocated_bytes=torch.cuda.max_memory_allocated(),
                reserved_bytes=torch.cuda.max_memory_reserved(),
                measured_not_admission_estimate=True,
            )
        except BaseException as failure:
            traceback.print_exc()
            error = dict(type=type(failure).__name__, message=str(failure), automatic_retry=False)
        calls = sum(
            p.read_json(root / row["path"])["resource_usage"]["actual_model_generation_calls"]
            for row in reports.values()
        )
        calls += sum(
            p.read_json(root / row["prediction_path"])["actual_model_generation_calls"]
            for row in predictions
        )
        require(calls <= 198, "per_model_at_most_six_times_32_plus_six")
        result = p.record(
            "delivery_r1_generation_worker",
            plan_id=job["plan_id"],
            model_key=job["model_key"],
            model_kind=job["model_kind"],
            actual_complete=error is None,
            condition_order=job["condition_order"],
            generation_reports=reports,
            prefix_results=predictions,
            actual_model_generation_calls=calls,
            calls_in_faulted_unreported_work_may_be_additional=error is not None,
            maximum_model_generation_calls=198,
            process_id=os.getpid(),
            gpu=job["gpu"],
            elapsed_seconds=time.monotonic() - started,
            finished_at=p.now(),
            error=error,
            peak_GPU_memory=peak,
            offline_assessment_capability_opened=False,
            physical_model_loads=1 if decoder is not None else None,
            session_history_and_tools_never_shared=True,
            generation_cache_cross_call_reuse=False,
        )
        p.write_once(folder / "report.json", result)
        if error is not None:
            raise RuntimeError(error["message"])


def worker_assess(root, job_path):
    root = Path(root).resolve()
    p, _, adapter_module, _ = modules(root)
    job = p.read_json(job_path)
    folder = root / OUTPUT / "workers" / job["model_key"]
    with (
        (folder / "assessment.log").open("x", buffering=1) as stream,
        contextlib.redirect_stdout(stream),
        contextlib.redirect_stderr(stream),
    ):
        generated = p.read_json(folder / "report.json")
        scores, semantics, failures = {}, [], []
        for condition in job["condition_order"]:
            generation = root / OUTPUT / "generation" / condition / job["model_key"]
            if not (generation / "manifest.json").exists():
                failures.append(dict(condition=condition, error="generation_manifest_missing"))
                continue
            try:
                ad = adapter_module.build_adapter(job["task_ids"], job["public_parent"], condition)
                target = root / OUTPUT / "assessment" / condition / job["model_key"]
                manifest = p.read_json(generation / "manifest.json")
                score = ad.score(
                    root, generation, target, expected_generation_manifest_id=manifest["id"]
                )
                scores[condition] = dict(
                    path=str((target / "report.json").relative_to(root)), id=score["id"]
                )
                require(score["actual_complete"] is True, "complete_offline_assessment")
            except Exception as failure:
                traceback.print_exc()
                failures.append(
                    dict(condition=condition, type=type(failure).__name__, error=str(failure))
                )
        grader = importlib.import_module("fixed_kernel_delivery_prefix_semantics_20260915")
        prefixes = {row["id"]: row for row in job["prefixes"]}
        for row in generated["prefix_results"]:
            try:
                prefix = p.read_json(root / prefixes[row["prefix_id"]]["path"])
                prediction = p.read_json(root / row["prediction_path"])
                result = grader.grade_prefix(prefix, prediction)
                target = (root / row["prediction_path"]).parent / "semantics.json"
                p.write_once(target, result)
                semantics.append(
                    dict(
                        prefix_id=row["prefix_id"],
                        semantics_path=str(target.relative_to(root)),
                        semantics_id=result["id"],
                    )
                )
            except Exception as failure:
                traceback.print_exc()
                failures.append(
                    dict(
                        prefix_id=row["prefix_id"], type=type(failure).__name__, error=str(failure)
                    )
                )
        result = p.record(
            "delivery_r1_assessment_worker",
            plan_id=job["plan_id"],
            model_key=job["model_key"],
            model_kind=job["model_kind"],
            generation_worker_report_id=generated["id"],
            assessment_reports=scores,
            prefix_semantics=semantics,
            errors=failures,
            actual_complete=not failures and len(scores) == 2 and len(semantics) == 6,
            actual_model_generation_calls=0,
            process_id=os.getpid(),
            finished_at=p.now(),
        )
        p.write_once(folder / "assessment.json", result)
        if not result["actual_complete"]:
            raise RuntimeError("delivery_r1.incomplete_offline_assessment")


def jobs_and_generation(root, plan, parent, admission, p, previous, owned):
    context = multiprocessing.get_context("spawn")
    pending, exits = list(plan["models"]), []
    public_parent = modules(root)[2].public_parent_binding(parent)
    while pending or owned:
        for key, current in list(owned.items()):
            process = current["process"]
            if process.is_alive():
                continue
            process.join()
            result = p.record(
                "delivery_r1_worker_exit",
                model_key=key,
                pid=process.pid,
                return_code=process.exitcode,
                finished_at=p.now(),
                automatic_retry=False,
                gpu=current["gpu"],
            )
            p.write_once(root / OUTPUT / "workers" / key / "generation_exit.json", result)
            exits.append(result)
            del owned[key]
            require(process.exitcode == 0, "worker_execution_fault_not_a_zero_score:" + key)
        if pending and len(owned) < MAX_GPU_WORKERS:
            raw = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=index,uuid,memory.free,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                text=True,
            )
            free = eligible_gpus(
                raw, plan["GPU_UUIDs"], {row["gpu"]["uuid"] for row in owned.values()}
            )
            while pending and free and len(owned) < MAX_GPU_WORKERS:
                model, gpu = pending.pop(0), free.pop(0)
                key = model["key"]
                folder = root / OUTPUT / "workers" / key
                job = p.record(
                    "delivery_r1_public_worker_job",
                    plan_id=plan["id"],
                    model_key=key,
                    model_kind=model["model_kind"],
                    condition_order=model["condition_order"],
                    task_ids=plan["task_ids"],
                    prefixes=plan["prefixes"],
                    gpu=gpu,
                    public_parent=public_parent,
                    source_root=parent["source_root"],
                    conditions={
                        condition: dict(
                            identity=p.read_json(
                                root / OUTPUT / "models" / condition / (key + ".json")
                            ),
                            configuration=plan["decoder_configurations"][condition],
                        )
                        for condition in CONDITIONS
                    },
                )
                path = folder / "job.json"
                p.write_once(path, job)
                process = context.Process(
                    target=worker_generate, args=(str(root), str(path), admission), name="r1-" + key
                )
                process.start()
                captured = previous.proc_identity(process.pid)
                require(captured["start_ticks"] is not None, "captured_own_child_identity")
                owned[key] = dict(process=process, identity=captured, gpu=gpu)
                p.write_once(
                    folder / "started.json",
                    p.record(
                        "delivery_r1_worker_started",
                        model_key=key,
                        process=captured,
                        gpu=gpu,
                        at=p.now(),
                    ),
                )
                print(
                    json.dumps(
                        dict(
                            event="GPU_worker_started",
                            model=key,
                            gpu=gpu["index"],
                            pid=process.pid,
                            at=p.now(),
                        )
                    ),
                    flush=True,
                )
        if pending or owned:
            time.sleep(10)
    report = p.record(
        "delivery_r1_generation_phase",
        plan_id=plan["id"],
        exits=exits,
        actual_complete=len(exits) == 10 and all(row["return_code"] == 0 for row in exits),
        automatic_retry=False,
        fixed_matrix_no_outcome_gate=True,
        finished_at=p.now(),
    )
    p.write_once(root / OUTPUT / "generation_phase.json", report)
    return report


def score_all(root, plan, p, previous, owned):
    require(not owned, "all_generation_processes_exited_before_offline_scoring")
    context = multiprocessing.get_context("spawn")
    workers, exits = [], []
    for model in plan["models"]:
        key = model["key"]
        folder = root / OUTPUT / "workers" / key
        if not (folder / "report.json").exists():
            continue
        process = context.Process(
            target=worker_assess,
            args=(str(root), str(folder / "job.json")),
            name="r1-offline-" + key,
        )
        process.start()
        owned[key] = dict(process=process, identity=previous.proc_identity(process.pid))
        workers.append((key, process))
    for key, process in workers:
        while process.is_alive():
            process.join(10)
        process.join()
        result = p.record(
            "delivery_r1_score_exit",
            model_key=key,
            pid=process.pid,
            return_code=process.exitcode,
            at=p.now(),
        )
        p.write_once(root / OUTPUT / "workers" / key / "assessment_exit.json", result)
        exits.append(result)
        owned.pop(key)
    report = p.record(
        "delivery_r1_score_phase",
        plan_id=plan["id"],
        exits=exits,
        actual_complete=len(exits) == 10 and all(row["return_code"] == 0 for row in exits),
        generation_and_assessment_same_process=False,
        finished_at=p.now(),
    )
    p.write_once(root / OUTPUT / "score_phase.json", report)
    return report


def publish_small(root, p, plan):
    # An explicit three-file allowlist, never a recursive add of the ignored
    # artifact tree. Session ledgers, prefix histories, callbacks and weights stay local.
    paths = [OUTPUT + "/plan.json", OUTPUT + "/report.json", SUMMARY]
    require(
        all(
            (root / path).is_file() and (root / path).stat().st_size < 2 * 1024 * 1024
            for path in paths
        ),
        "explicit_small_publication_allowlist",
    )
    staged = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only"], cwd=root, text=True
    ).splitlines()
    require(set(staged) <= set(paths), "preserve_unrelated_staged_changes")
    subprocess.run(["git", "add", "--sparse", "--force", "--", *paths], cwd=root, check=True)
    subprocess.run(["git", "diff", "--cached", "--check"], cwd=root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Report fixed-checkpoint R1 documentation contrast"],
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
            "delivery_r1_publication",
            plan_id=plan["id"],
            commit=commit,
            files=paths,
            at=p.now(),
            raw_sessions_prefixes_callbacks_or_models_published=False,
        ),
    )


def run(root, publish=True):
    root = Path(root).resolve()
    p, _, adapter_module, previous = modules(root)
    output = root / OUTPUT
    plan = p.checked(p.read_json(output / "plan.json"), "delivery_r1_plan")
    require(plan["source_binding"]["root"] == str(root), "same_frozen_worktree")
    for row in plan["source_binding"]["members"]:
        require(p.sha(root / row["path"]) == row["sha256"], "frozen_source_before_execution")
    parent = p.read_json(root / plan["parent_freeze"]["path"])
    require(parent["id"] == plan["parent_execution_freeze_id"], "same_original_assets")
    p.write_once(
        output / "started.json",
        p.record(
            "delivery_r1_started",
            plan_id=plan["id"],
            process=previous.proc_identity(os.getpid()),
            at=p.now(),
        ),
    )
    owned = {}
    try:
        # Exactly one physical base-file SHA admission for all ten trusted spawned workers.
        admission = adapter_module.make_host_admission(parent["base_binding"])
        generation = jobs_and_generation(root, plan, parent, admission, p, previous, owned)
        scores = score_all(root, plan, p, previous, owned)
        reporter = importlib.import_module("fixed_kernel_delivery_r1_report_20260915")
        result = reporter.run(root, output, plan)
        # This is a generated experiment document, not an edit of frozen source.
        with (root / SUMMARY).open("x") as stream:
            stream.write((output / "report.md").read_text())
        print(
            json.dumps(
                dict(
                    event="fixed_matrix_closed",
                    generation_complete=generation["actual_complete"],
                    scoring_complete=scores["actual_complete"],
                    report_id=result["id"],
                )
            ),
            flush=True,
        )
        if publish:
            publish_small(root, p, plan)
        return result
    except BaseException as error:
        actions = previous.stop_own_workers(owned, p, "R1_COORDINATOR_ERROR") if owned else []
        p.write_once(
            output / "coordinator_failure.json",
            p.record(
                "delivery_r1_coordinator_failure",
                plan_id=plan["id"],
                at=p.now(),
                error_type=type(error).__name__,
                error=str(error),
                stopped_own_workers=actions,
                automatic_retry=False,
                original_experiment_modified=False,
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("prepare", "run"), required=True)
    parser.add_argument("--no-publish", action="store_true")
    args = parser.parse_args()
    result = prepare(args.root) if args.mode == "prepare" else run(args.root, not args.no_publish)
    print(json.dumps({"id": result["id"], "status": result.get("status", "FROZEN")}), flush=True)


if __name__ == "__main__":
    main()
