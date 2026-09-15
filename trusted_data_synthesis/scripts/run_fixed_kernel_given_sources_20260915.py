"""Fixed 1800-session given-public-sources development comparison, not snapshot Q.

No adaptive sample/prompt/budget changes, training, B, or confirmation. Eight GPU
workers restore one unchanged checkpoint each; two wait for an admitted card.
All private financial assessments occur after generation processes have exited.
"""

# ruff: noqa: E501 -- frozen policy strings and generated report rows
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
from collections import Counter
from fractions import Fraction
from pathlib import Path

OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/given_sources_value_20260915"
PARENT = (
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/parallel_tail_execution_20260914"
)
R1 = "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/delivery_r1_contrast_20260915"
RUNTIME = "trusted_data_synthesis/runtime/fixed_kernel_given_sources_20260915"
SUMMARY = "trusted_data_synthesis/docs/fixed_kernel_given_sources_actual_results_20260915.md"
SCRIPT = "trusted_data_synthesis/scripts/run_fixed_kernel_given_sources_20260915.py"
HELPER = "trusted_data_synthesis/scripts/fixed_kernel_given_sources_execution_20260915.py"
SOURCES = (
    SCRIPT,
    HELPER,
    "trusted_data_synthesis/scripts/fixed_kernel_source_view_runtime_20260915.py",
    "trusted_data_synthesis/scripts/fixed_kernel_source_view_compact_20260915.py",
    "trusted_data_synthesis/scripts/fixed_kernel_source_view_compile_20260915.py",
)
GROUPS = ("dual_sufficient", "composition_required", "other_financial")
MINIMUM_FREE_MIB = 60 * 1024
MAX_WORKERS = 8
MAX_CALLS = 1800 * 32


def modules(root):
    for relative in (
        "trusted_data_synthesis/src",
        "raw_financial_data_lake",
        "trusted_data_synthesis/scripts",
    ):
        path = str(Path(root) / relative)
        if path not in sys.path:
            sys.path.insert(0, path)
    execution = importlib.import_module("fixed_kernel_given_sources_execution_20260915")
    previous = importlib.import_module("run_fixed_kernel_budget_reevaluation_20260915")
    return execution.p, execution, previous


def available(raw, allowed, used=()):
    result = []
    for line in raw.splitlines():
        index, uuid, free, utilization = [part.strip() for part in line.split(",")]
        if uuid in allowed and uuid not in used and int(free) >= MINIMUM_FREE_MIB:
            result.append(
                dict(
                    index=int(index),
                    uuid=uuid,
                    free_memory_MiB=int(free),
                    utilization_percent=int(utilization),
                )
            )
    return sorted(result, key=lambda row: row["index"])


def choose_direction(arm_utility):
    order = ("alpha0", "plus", "minus")
    scores = {arm: Fraction(arm_utility[arm]) for arm in order}
    best = max(order, key=lambda arm: scores[arm])
    return best if scores[best] > scores["alpha0"] else "alpha0"


def prepare(root):
    root = Path(root).resolve()
    p, e, previous = modules(root)
    output = root / OUTPUT
    p.require(not (output / "plan.json").exists(), "given_sources.one_fixed_matrix")
    inputs = p.checked(p.read_json(output / "inputs_v2/manifest.json"), "source_view_manifest_v2")
    admission = p.checked(
        p.read_json(output / "inputs_v2/admission.json"), "source_view_input_admission_v2"
    )
    controls = p.checked(
        p.read_json(output / "preflight/financial_controls.json"),
        "given_sources_financial_controls",
    )
    p.require(
        admission["passed"]
        and admission["passed_tasks"] == 180
        and admission["manifest_id"] == inputs["id"]
        and controls["passed"]
        and len(controls["results"]) == 5
        and controls["runtime_binding"] == admission["runtime_binding"] == e.views.binding()
        and controls["execution_script_sha256"] == p.sha(root / HELPER),
        "given_sources.all_new_inputs_and_financial_controls_admitted",
    )
    p.require(
        Counter(row["group"] for row in inputs["tasks"]) == dict.fromkeys(GROUPS, 60),
        "given_sources.fixed_180_equal_groups",
    )
    parent = p.read_json(root / PARENT / "preparation/execution_freeze.json")
    assets = {key: parent[key] for key in ("base_binding", "tokenizer_binding")}
    old_plan = p.checked(p.read_json(root / R1 / "plan.json"), "delivery_r1_plan")
    models = [
        {
            "key": row["key"],
            "model_kind": row["model_kind"],
            "checkpoint_id": row["checkpoint_id"],
            "original_model_identity": row["original_model_identity"],
        }
        for row in old_plan["models"]
    ]
    p.require(
        len(models) == 10
        and Counter(row["model_kind"] for row in models) == {"finetuned": 9, "unfinetuned_base": 1},
        "given_sources.nine_old_Students_and_honest_base",
    )
    from fixed_kernel_delivery_diagnostic_adapter_20260915 import base_checkpoint_identity

    for model in models:
        if model["model_kind"] == "finetuned":
            e.original.validate_model_identity(model["original_model_identity"])
            p.require(
                model["checkpoint_id"] == model["original_model_identity"]["checkpoint_id"],
                "given_sources.original_checkpoint_registration",
            )
        else:
            p.require(
                model["checkpoint_id"] == base_checkpoint_identity(assets["base_binding"])["id"],
                "given_sources.actual_base_files_identity_not_a_fake_LoRA",
            )
    config = e.configuration(assets, inputs["id"])
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    source_refs = []
    for path in SOURCES:
        reference = previous.file_reference(root, root / path)
        p.require(
            p.sha(subprocess.check_output(["git", "show", head + ":" + path], cwd=root))
            == reference["sha256"],
            "given_sources.committed_sources_before_freeze",
        )
        source_refs.append(reference)
    plan = p.record(
        "given_sources_value_plan",
        created_at=p.now(),
        source_view_manifest_id=inputs["id"],
        input_manifest=previous.file_reference(root, output / "inputs_v2/manifest.json"),
        input_admission_id=admission["id"],
        financial_controls_id=controls["id"],
        input_rule_parent="public_all_registered_metrics_period_window.v1 + lossless_metadata_pool.v2",
        user_audit_sha256="d82b24afd0d6eedbf7aa6b58b3d32982dc2010c344a8902eb6fee1a451c2bf2c",
        parent_execution_freeze_id=parent["id"],
        parent_freeze_path=PARENT + "/preparation/execution_freeze.json",
        source_root=parent["source_root"],
        models=models,
        tasks=inputs["tasks"],
        task_order="original180 development registry order; no outcome-based reordering",
        groups=list(GROUPS),
        tasks_per_group=60,
        models_count=10,
        full_sessions=1800,
        maximum_model_generation_calls=MAX_CALLS,
        budgets=dict(
            max_responses=32, max_tools=32, max_new_tokens=2048, maximum_sequence_length=24576
        ),
        decoder_configuration=config,
        source_binding=dict(root=str(root), commit=head, members=source_refs),
        utility_environment="J_sources_not_J_snapshot",
        primary_utility="equal mean of three fixed group financial qualification rates",
        SFT_effect="mean_seed J(alpha0) minus J(base)",
        distribution_effect="mean_seed same-task paired J(plus or minus) minus J(alpha0)",
        direction_rule="strictly positive three-seed mean paired primary utility; ties alpha0, plus, minus",
        fixed_failure_UNKNOWN_no_Final_denominator=True,
        no_new_Probe_or_training_or_B_or_confirmation=True,
        no_automatic_retries_or_sample_expansion=True,
        model_outputs_never_used_to_change_source_views=True,
        starts_with_empty_tool_results=True,
        prefix_histories_or_reference_answers_sent_to_model=False,
        GPU_UUIDs=list(previous.GPU_UUIDS),
        minimum_free_memory_MiB=MINIMUM_FREE_MIB,
        maximum_GPU_workers=MAX_WORKERS,
        GPU_utilization_must_be_zero=False,
        memory_admission_basis="R1 actual reserved peaks26.586-52.678GiB plus margin; not old24GiB estimate",
        training_lineage_note="A_minus_47 was trained by8GPU globalSUM with disclosed numerical/RNG differences; unchanged checkpoint reused",
        old_snapshot_scores_preserved=True,
        full_development_subjects_have_prior_researcher_exposure=True,
        source_and_task_gradient_training_isolation_from_input_admission=True,
    )
    p.write_once(output / "plan.json", plan)
    for row in models:
        old = row["original_model_identity"]
        identity = p.record(
            "given_sources_model_identity",
            model_key=row["key"],
            model_kind=row["model_kind"],
            checkpoint_id=row["checkpoint_id"],
            study_freeze_id=plan["id"],
            surface_manifest_id=inputs["id"],
            decoder_config_id=config["id"],
            base_binding_id=assets["base_binding"]["id"],
            tokenizer_binding_id=assets["tokenizer_binding"]["id"],
            original_model_identity=old,
            arm=old["arm"] if old else None,
            seed=old["seed"] if old else None,
            training_report_id=old["training_report_id"] if old else None,
            training_configuration_id=old["training_configuration_id"]
            if old
            else "not_applicable:unfinetuned_base",
            original_surface_identity_not_reused_for_new_inputs=True,
        )
        p.write_once(output / "models" / (row["key"] + ".json"), identity)
    return plan


def generate_worker(root, job_path, admission):
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
        p, e, _ = modules(root)
        started, rows, decoder, error, peak = time.monotonic(), [], None, None, None
        generation = root / OUTPUT / "generation" / job["model_key"]
        try:
            decoder = e.load_decoder(
                root, generation / "decoder", job["identity"], job["assets"], admission
            )
            p.write_once(generation / "model_identity.json", job["identity"])
            p.write_once(generation / "model_load_receipt.json", decoder.load_receipt)
            p.write_once(generation / "decoder_config.json", decoder.configuration)
            bound = e.views.build_runtime()
            for index, row in enumerate(job["tasks"]):
                view, identity = e.load_view(root, row, job["source_view_manifest_id"])
                before = dict(decoder.counters)
                visible = json.loads(view["public_messages"][0]["content"])
                session = bound.generate(
                    view["public_messages"],
                    identity,
                    bound.Sources(visible),
                    provider=decoder,
                    requested_basis="neutral",
                    max_responses=32,
                    max_tools=32,
                )
                path = generation / "sessions" / row["task_id"]
                p.write_once(path / "runtime_session.json", session)
                delta = {key: decoder.counters[key] - before[key] for key in e.COUNTERS}
                p.require(
                    delta["callback_attempts"] == session["provider_calls"],
                    "given_sources.all_callback_attempts_accounted",
                )
                result = p.record(
                    "given_sources_generation_result",
                    plan_id=job["plan_id"],
                    model_identity_id=job["identity"]["id"],
                    task_id=row["task_id"],
                    group=row["group"],
                    source_cluster=row["source_cluster"],
                    source_view_id=view["id"],
                    runtime_session_id=session["id"],
                    session_path=str((path / "runtime_session.json").relative_to(root)),
                    session_sha256=p.sha(p.encode(session)),
                    terminal=session["terminal"],
                    first_final_index=session["first_final_index"],
                    resource_delta=delta,
                    model_outputs_unmodified=True,
                    private_TaskBundles_opened=False,
                )
                p.write_once(path / "result.json", result)
                rows.append(
                    dict(
                        task_id=row["task_id"],
                        result_id=result["id"],
                        path=str((path / "result.json").relative_to(root)),
                    )
                )
                p.require(
                    decoder.fatal_error is None,
                    "given_sources.stop_on_execution_fault_not_on_bad_score",
                )
                if (index + 1) % 10 == 0:
                    print(
                        json.dumps(
                            dict(
                                completed_tasks=index + 1,
                                total_tasks=180,
                                model=job["model_key"],
                                at=p.now(),
                            )
                        ),
                        flush=True,
                    )
            import torch

            peak = dict(
                allocated_bytes=torch.cuda.max_memory_allocated(),
                reserved_bytes=torch.cuda.max_memory_reserved(),
            )
            p.require(
                decoder.counters["actual_model_generation_calls"] <= 180 * 32,
                "given_sources.worker_generation_cap",
            )
        except BaseException as failure:
            traceback.print_exc()
            error = dict(type=type(failure).__name__, message=str(failure), retry=False)
        report = p.record(
            "given_sources_generation_report",
            plan_id=job["plan_id"],
            model_key=job["model_key"],
            model_identity_id=job["identity"]["id"],
            model_kind=job["identity"]["model_kind"],
            checkpoint_id=job["identity"]["checkpoint_id"],
            actual_complete=error is None and len(rows) == 180,
            planned_tasks=180,
            completed_tasks=len(rows),
            results=rows,
            resource_usage=decoder.snapshot() if decoder is not None else None,
            GPU_peak_memory=peak,
            elapsed_seconds=time.monotonic() - started,
            finished_at=p.now(),
            process_id=os.getpid(),
            gpu=job["gpu"],
            error=error,
            financial_assessment_capability_opened=False,
            original_results_modified=False,
        )
        p.write_once(generation / "report.json", report)
        p.write_once(folder / "report.json", report)
        if error:
            raise RuntimeError(error["message"])


def assess_worker(root, job_path, private):
    root = Path(root).resolve()
    p, e, _ = modules(root)
    job = p.read_json(job_path)
    folder = root / OUTPUT / "workers" / job["model_key"]
    with (
        (folder / "assessment.log").open("x", buffering=1) as stream,
        contextlib.redirect_stdout(stream),
        contextlib.redirect_stderr(stream),
    ):
        generation = p.checked(
            p.read_json(folder / "report.json"), "given_sources_generation_report"
        )
        p.require(
            generation["actual_complete"]
            and generation["model_identity_id"] == job["identity"]["id"],
            "given_sources.only_complete_actual_generation_scored",
        )
        references = {row["task_id"]: row for row in generation["results"]}
        bound, outcomes, counted = e.views.build_runtime(), [], Counter()
        output = root / OUTPUT / "assessment" / job["model_key"]
        for row in job["tasks"]:
            reference = references[row["task_id"]]
            result = p.checked(
                p.read_json(root / reference["path"]), "given_sources_generation_result"
            )
            p.require(result["id"] == reference["result_id"], "given_sources.result_identity")
            raw = (root / result["session_path"]).read_bytes()
            p.require(
                p.sha(raw) == result["session_sha256"], "given_sources.saved_session_unchanged"
            )
            session = json.loads(raw)
            p.require(
                session["id"] == result["runtime_session_id"],
                "given_sources.saved_runtime_identity",
            )
            counted.update(e.resource_from_session(session, job["identity"], job["configuration"]))
            f = e.fixture(root, row, job["source_view_manifest_id"], private)
            score = bound.assess_session(session, f["bundle"], f["native_bindings"], f["sources"])
            p.write_once(output / "tasks" / (row["task_id"] + ".json"), score)
            tools = [event["tool_call"] for event in session["events"] if event["tool_call"]]
            diagnostic = {
                "numeric_read": any(
                    t["tool"] == "read_source" and t["status"] == "ok" for t in tools
                ),
                "successful_calculation": any(
                    t["tool"] == "calculate" and t["status"] == "ok" for t in tools
                ),
                "recognized_Final": session["first_final_index"] is not None,
                "tool_error": any(t["status"] == "error" for t in tools),
                "context_rejected": result["resource_delta"]["context_rejections"] > 0,
            }
            outcomes.append(
                {
                    key: score[key]
                    for key in (
                        "task_id",
                        "financial_valid",
                        "quantity_status",
                        "support_status",
                        "actual_method",
                        "reason",
                    )
                }
                | dict(
                    group=row["group"],
                    source_cluster=row["source_cluster"],
                    assessment_id=score["id"],
                    terminal=session["terminal"],
                    diagnostics=diagnostic,
                )
            )
        p.require(
            counted["actual_model_generation_calls"]
            == generation["resource_usage"]["actual_model_generation_calls"]
            and counted["generated_tokens"] == generation["resource_usage"]["generated_tokens"],
            "given_sources.one_pass_actual_resource_reconciliation",
        )
        report = p.record(
            "given_sources_assessment_report",
            plan_id=job["plan_id"],
            model_key=job["model_key"],
            model_identity_id=job["identity"]["id"],
            generation_report_id=generation["id"],
            actual_complete=len(outcomes) == 180,
            outcomes=outcomes,
            resource_usage=dict(counted),
            actual_assessment_model_calls=0,
            original_financial_qualification_unchanged=True,
            process_id=os.getpid(),
            finished_at=p.now(),
        )
        p.write_once(output / "report.json", report)
        p.write_once(folder / "assessment.json", report)


def summarize(root, plan, p):
    models, tables, outcome_maps, usage = [], [], {}, Counter()
    for registered in plan["models"]:
        key = registered["key"]
        generated = p.checked(
            p.read_json(root / OUTPUT / "workers" / key / "report.json"),
            "given_sources_generation_report",
        )
        score = p.checked(
            p.read_json(root / OUTPUT / "workers" / key / "assessment.json"),
            "given_sources_assessment_report",
        )
        p.require(
            generated["actual_complete"]
            and score["actual_complete"]
            and generated["id"] == score["generation_report_id"]
            and generated["plan_id"] == score["plan_id"] == plan["id"]
            and generated["checkpoint_id"] == registered["checkpoint_id"]
            and score["process_id"] != generated["process_id"],
            "given_sources.fixed_model_and_independent_offline_join",
        )
        rows = score["outcomes"]
        p.require(
            len(rows) == 180
            and {row["task_id"] for row in rows} == {row["task_id"] for row in plan["tasks"]},
            "given_sources.complete180_not_only_passed_tasks",
        )
        group_rows = {}
        for group in GROUPS:
            selected = [row for row in rows if row["group"] == group]
            p.require(len(selected) == 60, "given_sources.fixed_group_denominator")
            group_rows[group] = dict(
                tasks=60,
                qualified=sum(row["financial_valid"] for row in selected),
                reason_counts=dict(Counter(row["reason"] or "PASS" for row in selected)),
                diagnostics={
                    name: sum(row["diagnostics"][name] for row in selected)
                    for name in selected[0]["diagnostics"]
                },
            )
        utility = sum(Fraction(value["qualified"], 60) for value in group_rows.values()) / 3
        old = registered["original_model_identity"]
        item = dict(
            model_key=key,
            model_kind=registered["model_kind"],
            arm=old["arm"] if old else None,
            seed=old["seed"] if old else None,
            checkpoint_id=registered["checkpoint_id"],
            J_sources_exact=str(utility),
            J_sources=float(utility),
            groups=group_rows,
            qualified=sum(row["financial_valid"] for row in rows),
            total=180,
            generation_report_id=generated["id"],
            assessment_report_id=score["id"],
            elapsed_worker_seconds=generated["elapsed_seconds"],
            peak_GPU_memory=generated["GPU_peak_memory"],
            resource_usage=generated["resource_usage"],
            outcomes=rows,
        )
        models.append(item)
        outcome_maps[key] = {row["task_id"]: row for row in rows}
        usage.update(
            {
                name: generated["resource_usage"][name]
                for name in (
                    "actual_model_generation_calls",
                    "generated_tokens",
                    "context_rejections",
                    "model_weight_loads",
                    "final_adapter_loads",
                )
            }
        )
    arms = {
        arm: sum(Fraction(row["J_sources_exact"]) for row in models if row["arm"] == arm) / 3
        for arm in ("alpha0", "plus", "minus")
    }
    base = next(
        Fraction(row["J_sources_exact"])
        for row in models
        if row["model_kind"] == "unfinetuned_base"
    )
    selected = choose_direction(arms)
    effects = {
        "SFT_alpha0_minus_base": str(arms["alpha0"] - base),
        "pi_plus_minus_alpha0": str(arms["plus"] - arms["alpha0"]),
        "pi_minus_minus_alpha0": str(arms["minus"] - arms["alpha0"]),
    }
    for seed in (11, 29, 47):
        for task in plan["tasks"]:
            tid = task["task_id"]
            baseline = int(outcome_maps[f"A_alpha0_{seed}"][tid]["financial_valid"])
            tables.append(
                dict(
                    task_id=tid,
                    source_cluster=task["source_cluster"],
                    group=task["group"],
                    seed=seed,
                    alpha0=baseline,
                    plus_minus_alpha0=int(outcome_maps[f"A_plus_{seed}"][tid]["financial_valid"])
                    - baseline,
                    minus_minus_alpha0=int(outcome_maps[f"A_minus_{seed}"][tid]["financial_valid"])
                    - baseline,
                )
            )
    p.require(usage["actual_model_generation_calls"] <= MAX_CALLS, "given_sources.total_budget")
    started = p.read_json(root / OUTPUT / "started.json")
    report = p.record(
        "given_sources_final_report",
        plan_id=plan["id"],
        status="COMPLETE_FIXED_GIVEN_SOURCES_DEVELOPMENT",
        actual_complete=True,
        finished_at=p.now(),
        started_at=started["at"],
        source_view_manifest_id=plan["source_view_manifest_id"],
        full_sessions=1800,
        unique_tasks=180,
        source_clusters=len({row["source_cluster"] for row in plan["tasks"]}),
        utility_environment="J_sources_not_J_snapshot",
        models=models,
        paired_task_seed_rows=tables,
        arm_mean_utilities={key: str(value) for key, value in arms.items()},
        effects=effects,
        selected_direction=selected,
        strict_positive_direction=selected != "alpha0",
        B_training_authorized_or_started=False,
        confirmation_started=False,
        original_R0_R1_scores_replaced=False,
        no_statistical_significance_or_snapshot_improvement_claim=True,
        resource_usage=dict(usage),
        training_lineage_note=plan["training_lineage_note"],
        unchanged_frozen_task_denominator=True,
    )
    p.write_once(root / OUTPUT / "report.json", report)
    lines = [
        "# 给定公开来源：固定材料核的同接口训练价值实验结果",
        "",
        f"状态：`{report['status']}`；报告 `{report['id']}`。",
        "",
        "本轮完整执行10模型×180开发题，共1,800会话；三组各60题，固定分母不删失败、UNKNOWN或无Final。",
        "效用为J_sources：给定方法中立的原始公开来源后，从空工具表自主读取、计算和交付。不是完整快照J_snapshot，不覆盖旧R0/R1。",
        "",
        f"开始：{report['started_at']}；完成评分汇总：{report['finished_at']}（时间为UTC）。",
        "",
        "## 模型与三组结果",
        "",
        "| 模型 | 完整资格/180 | 双充分/60 | 三期均值/60 | 峰值后查询/60 | J_sources |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in models:
        values = [row["groups"][group]["qualified"] for group in GROUPS]
        lines.append(
            f"| {row['model_key']} | {row['qualified']}/180 | {values[0]}/60 | {values[1]}/60 | {values[2]}/60 | {row['J_sources']:.6f} |"
        )
    lines += [
        "",
        "## SFT效应与分布增量分开报告",
        "",
        f"三种子平均效用（精确分数）：`{report['arm_mean_utilities']}`。基座为`{base}`，不是alpha0或额外训练种子。",
        "",
        f"效应（精确分数）：`{effects}`。分布差异来自同题同种子配对，并与三个组等权主效用一致。",
        "",
        f"严格正收益/固定平局顺序下选择：**{selected}**。本次不自动获得B或确认准入。",
        "",
        "## 执行阶段诊断",
        "",
        "以下阶段可重叠，不加成临时总分。",
        "",
        "| 模型/组 | 数值读取 | 成功计算 | Final | 工具错误 | 上下文拒绝 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in models:
        for group, data in row["groups"].items():
            d = data["diagnostics"]
            lines.append(
                f"| {row['model_key']}/{group} | {d['numeric_read']} | {d['successful_calculation']} | {d['recognized_Final']} | {d['tool_error']} | {d['context_rejected']} |"
            )
    lines += ["", "## 方法与失败原因", ""]
    for row in models:
        lines += [
            f"- {row['model_key']}：方法 `{dict(Counter(item['actual_method'] for item in row['outcomes']))}`；原因 `{dict(Counter(item['reason'] or 'PASS' for item in row['outcomes']))}`。"
        ]
    lines += [
        "",
        "## 资源与边界",
        "",
        f"实际资源：`{dict(usage)}`；模型生成上限57,600。未使用调用容量不表示缺失会话。",
        "",
        "| 模型 | worker秒 | reserved显存峰值GiB |",
        "|---|---:|---:|",
    ]
    for row in models:
        lines.append(
            f"| {row['model_key']} | {row['elapsed_worker_seconds']:.2f} | {row['peak_GPU_memory']['reserved_bytes'] / 1024**3:.3f} |"
        )
    lines += [
        "",
        "180开发题未进入Student梯度训练，但已有研究者开发/诊断曝光，不能称为新盲测。来源与训练簇隔离通过；12个开发来源簇不能被任务×种子乘积替代为独立题量。",
        "公开窗口保留全部已注册指标记录，未按私有叶子选择；v2无损共享元数据只解决初始历史空间不足，未改SYSTEM、数值记录、指针或来源ID。",
        "端点、movement、均值和完整峰值依赖的必要新接口正控通过；不完整峰值支持的反例被拒绝。这些CPU脚本未发送给Student，不计入模型结果。",
        "金融资格仍核查首个Final、实际来源、单位、期间及完整符号/选择支持；来源提供不免除评分要求。",
        plan["training_lineage_note"],
        "效应只限此固定材料核与给定来源环境。没有据此宣布完整快照检索改善、总体统计显著、完整anchored或HierLoss有效。",
        "不重训、不再采Probe、不根据结果改来源或说明。B、720题确认及独立检索能力适配均未启动，需另行授权。",
        "原始会话、callback、源视图与原生材料留本地；仅发布明确的小型输入准入/计划/汇总和本文。",
        "",
    ]
    with (root / SUMMARY).open("x") as stream:
        stream.write("\n".join(lines))
    return report


def run(root, publish=True):
    root = Path(root).resolve()
    p, e, previous = modules(root)
    plan = p.checked(p.read_json(root / OUTPUT / "plan.json"), "given_sources_value_plan")
    for row in plan["source_binding"]["members"]:
        p.require(p.sha(root / row["path"]) == row["sha256"], "given_sources.frozen_source_bytes")
    parent = p.read_json(root / plan["parent_freeze_path"])
    assets = {key: parent[key] for key in ("base_binding", "tokenizer_binding")}
    p.write_once(
        root / OUTPUT / "started.json",
        p.record(
            "given_sources_started",
            plan_id=plan["id"],
            at=p.now(),
            process=previous.proc_identity(os.getpid()),
        ),
    )
    owned, pending, context, exits = (
        {},
        list(plan["models"]),
        multiprocessing.get_context("spawn"),
        [],
    )
    try:
        admission = e.isolation.make_host_admission(assets["base_binding"])
        while pending or owned:
            for key, current in list(owned.items()):
                process = current["process"]
                if process.is_alive():
                    continue
                process.join()
                exit_record = p.record(
                    "given_sources_worker_exit",
                    model_key=key,
                    pid=process.pid,
                    return_code=process.exitcode,
                    at=p.now(),
                )
                p.write_once(root / OUTPUT / "workers" / key / "generation_exit.json", exit_record)
                exits.append(exit_record)
                del owned[key]
                p.require(
                    process.exitcode == 0, "given_sources.execution_fault_stop_no_retry:" + key
                )
            if pending and len(owned) < MAX_WORKERS:
                raw = subprocess.check_output(
                    [
                        "nvidia-smi",
                        "--query-gpu=index,uuid,memory.free,utilization.gpu",
                        "--format=csv,noheader,nounits",
                    ],
                    text=True,
                )
                free = available(
                    raw, plan["GPU_UUIDs"], {row["gpu"]["uuid"] for row in owned.values()}
                )
                while pending and free and len(owned) < MAX_WORKERS:
                    model, gpu = pending.pop(0), free.pop(0)
                    key = model["key"]
                    folder = root / OUTPUT / "workers" / key
                    job = p.record(
                        "given_sources_public_worker_job",
                        plan_id=plan["id"],
                        model_key=key,
                        gpu=gpu,
                        assets=assets,
                        source_view_manifest_id=plan["source_view_manifest_id"],
                        tasks=plan["tasks"],
                        identity=p.read_json(root / OUTPUT / "models" / (key + ".json")),
                        configuration=plan["decoder_configuration"],
                        no_private_TaskBundles_in_job=True,
                    )
                    path = folder / "job.json"
                    p.write_once(path, job)
                    process = context.Process(
                        target=generate_worker,
                        args=(str(root), str(path), admission),
                        name="sources-" + key,
                    )
                    process.start()
                    owned[key] = dict(
                        process=process, identity=previous.proc_identity(process.pid), gpu=gpu
                    )
                    p.write_once(
                        folder / "started.json",
                        p.record(
                            "given_sources_worker_started",
                            model_key=key,
                            process=owned[key]["identity"],
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
        p.write_once(
            root / OUTPUT / "generation_phase.json",
            p.record(
                "given_sources_generation_phase",
                actual_complete=True,
                exits=exits,
                planned_models=10,
                completed_models=10,
                finished_at=p.now(),
            ),
        )
        # The parent obtains private dev fixtures once, only after all public GPU workers exited.
        private = e.offline_assets(root, Path(plan["source_root"]), plan["tasks"])
        for model in plan["models"]:
            key = model["key"]
            process = context.Process(
                target=assess_worker,
                args=(str(root), str(root / OUTPUT / "workers" / key / "job.json"), private),
                name="sources-offline-" + key,
            )
            process.start()
            owned[key] = dict(process=process, identity=previous.proc_identity(process.pid))
        score_exits = []
        for key, current in list(owned.items()):
            process = current["process"]
            while process.is_alive():
                process.join(10)
            process.join()
            exit_record = p.record(
                "given_sources_assessment_exit",
                model_key=key,
                pid=process.pid,
                return_code=process.exitcode,
                at=p.now(),
            )
            p.write_once(root / OUTPUT / "workers" / key / "assessment_exit.json", exit_record)
            score_exits.append(exit_record)
            del owned[key]
            p.require(
                process.exitcode == 0, "given_sources.offline_execution_fault_not_score_zero:" + key
            )
        p.write_once(
            root / OUTPUT / "score_phase.json",
            p.record(
                "given_sources_score_phase",
                actual_complete=True,
                exits=score_exits,
                model_calls=0,
                finished_at=p.now(),
            ),
        )
        result = summarize(root, plan, p)
        print(
            json.dumps(dict(event="fixed_given_sources_matrix_complete", report_id=result["id"])),
            flush=True,
        )
        if publish:
            paths = [OUTPUT + "/plan.json", OUTPUT + "/report.json", SUMMARY]
            p.require(
                all((root / path).stat().st_size < 5 * 1024 * 1024 for path in paths),
                "given_sources.exact_small_publish_files",
            )
            staged = subprocess.check_output(
                ["git", "diff", "--cached", "--name-only"], cwd=root, text=True
            ).splitlines()
            p.require(set(staged) <= set(paths), "given_sources.preserve_unrelated_staging")
            subprocess.run(
                ["git", "add", "--sparse", "--force", "--", *paths], cwd=root, check=True
            )
            subprocess.run(["git", "diff", "--cached", "--check"], cwd=root, check=True)
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    "Report fixed given-sources development training-value comparison",
                ],
                cwd=root,
                check=True,
            )
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip()
            subprocess.run(
                ["git", "push", "https://github.com/haoyueliuzhao/Data-Synthesis.git", "HEAD:main"],
                cwd=root,
                check=True,
            )
            p.write_once(
                root / RUNTIME / "publication.json",
                p.record(
                    "given_sources_publication",
                    commit=commit,
                    files=paths,
                    raw_sources_callbacks_sessions_published=False,
                    at=p.now(),
                ),
            )
        return result
    except BaseException as error:
        stopped = (
            previous.stop_own_workers(owned, p, "GIVEN_SOURCES_COORDINATOR_FAULT") if owned else []
        )
        p.write_once(
            root / OUTPUT / "coordinator_failure.json",
            p.record(
                "given_sources_coordinator_failure",
                plan_id=plan["id"],
                error_type=type(error).__name__,
                error=str(error),
                stopped_own_workers=stopped,
                at=p.now(),
                automatic_retry=False,
                original_results_overwritten=False,
            ),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("prepare", "run"), required=True)
    parser.add_argument("--no-publish", action="store_true")
    args = parser.parse_args()
    result = prepare(args.root) if args.mode == "prepare" else run(args.root, not args.no_publish)
    print(json.dumps({"id": result["id"], "status": result.get("status", "FROZEN")}))
