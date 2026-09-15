"""One result pass over the fixed R1 matrix; no generation, grading or old rescan.

Inputs are the immutable GPU worker and separate CPU assessment receipts.  Each
of the 60 new runtime sessions is read once using the already published stage-A
pure observational analyzer.  Financial Q comes only from the new assessments;
prefix semantics remain conditional diagnostics and never enter autonomous Q.
"""

from __future__ import annotations

# ruff: noqa: E501 -- complete observational definitions and generated report sentences
import argparse
from collections import Counter
from pathlib import Path

import fixed_kernel_delivery_failure_ledger_20260915 as observational

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

CONDITIONS = ("original", "gamma_doc")
MODEL_KINDS = ("finetuned", "unfinetuned_base")
DEFAULT_OUTPUT = Path(
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/delivery_r1_contrast_20260915"
)
PREFIX_BOOLEAN_FIELDS = (
    "strict_json_object",
    "immediate_final",
    "tool_executable",
    "referenced_results_supported",
    "requested_quantity_matches_public_reference",
    "source_expression_equivalent_to_public_reference",
    "numeric_quantity_matches_public_reference",
    "final_unit_matches_request",
    "final_value_matches_supported_result",
    "final_quantity_matches_public_reference",
    "semantic_calculation_success",
    "semantic_immediate_final_success",
)
STAGE_DEFINITIONS = {
    "nonempty_discovery_return": "any nonempty query_source/list_concepts/read_json return; not financial correctness",
    "nonempty_query_observed": "a successful query_source returned at least one original record",
    "numeric_source_read_observed": "successful numeric read_source or original /val observed through read_json",
    "successful_calculation_observed": "successful numeric calculate; requested quantity not inferred from this flag",
    "runtime_recognized_final": "runtime recorded the first parsed top-level final, regardless of financial validity",
    "financial_qualified": "complete trajectory financial qualification from the separately sealed R1 score",
    "any_tool_error": "at least one actual tool error; may overlap all other stages",
    "repeat_query_without_new_public_evidence": "same canonical query and unchanged public evidence state",
    "query_source_string_concatenation_NoneType_error_observed": "original null-concatenation signature remains observable",
}


def _record_id(item):
    p.require(isinstance(item, dict) and isinstance(item.get("id"), str), "R1_report.record_id")
    expected = item["id"].split(":", 1)
    p.require(
        len(expected) == 2
        and expected[1]
        == p.sha(p.encode({key: value for key, value in item.items() if key != "id"})),
        "R1_report.content_addressed_record",
    )


def _path(root, output, value):
    path = Path(value)
    path = path if path.is_absolute() else root / path
    p.require(
        ".." not in path.parts
        and path.resolve().is_relative_to(output)
        and not any(part.is_symlink() for part in (path, *path.parents)),
        "R1_report.only_new_non_symlink_output_records",
    )
    return path


def _read(root, output, value, *, expected_id=None, maximum=16 * 1024 * 1024):
    path = _path(root, output, value)
    item, reference = observational.read_bound(root, path, maximum)
    _record_id(item)
    p.require(expected_id is None or item["id"] == expected_id, "R1_report.exact_input_record_join")
    return item, reference


def _reference(root, output, reference):
    p.require(set(reference) >= {"path", "id"}, "R1_report.bound_report_reference")
    return _read(root, output, reference["path"], expected_id=reference["id"])


def session_stages(ledger, qualified):
    flags = ledger["flags"]
    return {
        name: bool(ledger["observed_counts"].get(name, 0))
        if name == "nonempty_discovery_return"
        else bool(qualified)
        if name == "financial_qualified"
        else bool(flags.get(name, False))
        for name in STAGE_DEFINITIONS
    }


def summarize_matrix(rows, task_ids, models):
    """Pure paired descriptive summary; all expected cells are mandatory."""
    keys = [row["key"] for row in models]
    p.require(
        len(keys) == len(set(keys)) and len(task_ids) == len(set(task_ids)),
        "R1_report.unique_models_and_tasks",
    )
    expected = {
        (key, condition, task) for key in keys for condition in CONDITIONS for task in task_ids
    }
    cells = {(row["model_key"], row["condition"], row["task_id"]): row for row in rows}
    p.require(
        len(cells) == len(rows) and set(cells) == expected, "R1_report.complete_paired_matrix"
    )
    p.require(
        all(type(row["financial_valid"]) is bool for row in rows), "R1_report.boolean_financial_Q"
    )
    model_rows, pairs = [], []
    for model in models:
        p.require(model["model_kind"] in MODEL_KINDS, "R1_report.honest_model_kind")
        local = []
        for task in task_ids:
            old = cells[model["key"], "original", task]
            documented = cells[model["key"], "gamma_doc", task]
            p.require(
                old["model_kind"] == documented["model_kind"] == model["model_kind"],
                "R1_report.paired_same_model_kind",
            )
            pair = {
                "model_key": model["key"],
                "model_kind": model["model_kind"],
                "task_id": task,
                "Q_R1_original": int(old["financial_valid"]),
                "Q_R1_gamma_doc": int(documented["financial_valid"]),
                "delta_doc_Q": int(documented["financial_valid"]) - int(old["financial_valid"]),
                "original_assessment_id": old.get("assessment_id"),
                "gamma_doc_assessment_id": documented.get("assessment_id"),
                "stage_deltas": {
                    name: int(documented["stages"][name]) - int(old["stages"][name])
                    for name in STAGE_DEFINITIONS
                },
            }
            local.append(pair)
            pairs.append(pair)
        model_rows.append(
            {
                "model_key": model["key"],
                "model_kind": model["model_kind"],
                "arm": model.get("arm"),
                "seed": model.get("seed"),
                "unique_tasks": len(task_ids),
                "original_qualified": sum(row["Q_R1_original"] for row in local),
                "gamma_doc_qualified": sum(row["Q_R1_gamma_doc"] for row in local),
                "paired_delta_Q_sum": sum(row["delta_doc_Q"] for row in local),
                "paired_mean_delta_Q": sum(row["delta_doc_Q"] for row in local) / len(task_ids),
                "transition_counts": dict(
                    Counter(
                        str(row["Q_R1_original"]) + "->" + str(row["Q_R1_gamma_doc"])
                        for row in local
                    )
                ),
            }
        )
    populations = {}
    for kind in MODEL_KINDS:
        populations[kind] = {}
        for condition in CONDITIONS:
            subset = [
                row for row in rows if row["model_kind"] == kind and row["condition"] == condition
            ]
            populations[kind][condition] = {
                "sessions": len(subset),
                "unique_tasks": len({row["task_id"] for row in subset}),
                "financial_qualified": sum(row["financial_valid"] for row in subset),
                "stage_session_counts": {
                    name: sum(row["stages"][name] for row in subset) for name in STAGE_DEFINITIONS
                },
                "reason_counts": dict(Counter(row["reason"] for row in subset)),
                "terminal_counts": dict(Counter(row["runtime_terminal"] for row in subset)),
                "quantity_status_counts": dict(Counter(row["quantity_status"] for row in subset)),
                "support_status_counts": dict(Counter(row["support_status"] for row in subset)),
                "stage_flags_overlap_not_an_added_score": True,
            }
    return {
        "complete_sessions": len(rows),
        "unique_development_tasks": len(task_ids),
        "paired_model_task_comparisons": len(pairs),
        "model_rows": model_rows,
        "paired_task_rows": pairs,
        "separate_model_kind_populations": populations,
        "base_excluded_from_alpha0_plus_minus_denominators": True,
        "statistical_inference": "descriptive_fixed_three_task_diagnostic_no_CI_or_significance_claim",
    }


def summarize_prefixes(rows):
    """Nullable component denominators; string match is not a success criterion."""
    p.require(
        all(
            value is None or type(value) is bool
            for row in rows
            for key in PREFIX_BOOLEAN_FIELDS
            for value in (row["semantics"].get(key),)
        ),
        "R1_report.nullable_boolean_semantics",
    )
    output = {}
    for kind in MODEL_KINDS:
        output[kind] = {}
        for boundary in ("calculate", "final"):
            selected = [
                row for row in rows if row["model_kind"] == kind and row["boundary"] == boundary
            ]
            output[kind][boundary] = {
                "responses": len(selected),
                "status_counts": dict(Counter(row["semantics"]["status"] for row in selected)),
                "components": {
                    key: {
                        "true": sum(row["semantics"].get(key) is True for row in selected),
                        "false": sum(row["semantics"].get(key) is False for row in selected),
                        "not_applicable_or_undetermined": sum(
                            row["semantics"].get(key) is None for row in selected
                        ),
                        "determined_denominator": sum(
                            type(row["semantics"].get(key)) is bool for row in selected
                        ),
                    }
                    for key in PREFIX_BOOLEAN_FIELDS
                },
                "exact_reference_text_matches_descriptive_only": sum(
                    row["prediction"].get("exact_reference_response_match") is True
                    for row in selected
                ),
            }
    return {
        "responses": len(rows),
        "by_model_kind_and_boundary": output,
        "financial_qualification_score": None,
        "autonomous_task_success_claimed": False,
        "Probe_prefix_counted_as_Student_generation": False,
        "exact_text_match_is_not_semantic_pass_criterion": True,
        "continuing_a_tool_does_not_prove_never_final": True,
    }


def historical_background(root, plan):
    """Read one existing small comparison, never old sessions or callback files."""
    relative = Path(plan["historical_R0_summary_path"])
    p.require(
        not relative.is_absolute() and ".." not in relative.parts,
        "R1_report.historical_summary_relative_path",
    )
    old, reference = observational.read_bound(root, root / relative, 4 * 1024 * 1024)
    _record_id(old)
    expected = {
        (model["key"], task)
        for model in plan["models"]
        if model["model_kind"] == "finetuned"
        for task in plan["task_ids"]
    }
    pairs = {(row["model"], row["task_id"]): row for row in old["pairs"]}
    p.require(
        len(pairs) == len(old["pairs"]) == 27 and set(pairs) == expected,
        "R1_report_exact_historical_27_model_task_pairs",
    )
    return {
        "scope": "nine_existing_finetuned_models_times_three_fixed_tasks_descriptive_only",
        "summary_record_id": old["id"],
        "source": reference,
        "old_budget_summary": old["old_budget"],
        "old_model_task_rows": [
            {
                "model_key": model,
                "task_id": task,
                "old_R0_Q": int(row["old"]["financial_valid"]),
                "old_R0_recognized_Final": row["old"]["recognized_Final"],
                "old_assessment_id": row["old"]["assessment_id"],
            }
            for (model, task), row in pairs.items()
        ],
        "new_R0_generation_calls": 0,
        "old_sessions_rescanned": 0,
        "old_scores_recomputed": 0,
        "not_in_same_R1_doc_effect": True,
        "hardware_and_time_not_controlled_between_R0_history_and_new_R1": True,
    }


def render_markdown(report):
    matrix = report["R1_same_tool_documentation_comparison"]
    lines = [
        "# R1 固定检查点、公共说明与交付诊断结果",
        "",
        f"结果身份：`{report['id']}`。计划身份：`{report['plan_id']}`。",
        "",
        "本轮完成 60 个完整会话及 60 次公开历史单步续接。完整会话只有 **3 个独特开发任务**，",
        "在 9 个微调检查点和 1 个未微调基座、2 个同 R1 工具说明条件下重复执行。",
        "基座不属于 alpha0，单步续接不计自主任务成功或完整财务资格。",
        "",
        "## 同 R1 工具下的主要配对结果",
        "",
        "Q 为既定完整轨迹财务资格；Δ_doc = Q(R1, Γ_doc) − Q(R1, Γ_0)。每格分母均为 3 题。",
        "",
        "| 模型 | 类型 | 原说明 Q | 澄清说明 Q | 配对平均 Δ_doc |",
        "|---|---|---:|---:|---:|",
    ]
    for row in matrix["model_rows"]:
        lines.append(
            f"| {row['model_key']} | {row['model_kind']} | {row['original_qualified']}/3 | "
            f"{row['gamma_doc_qualified']}/3 | {row['paired_mean_delta_Q']:+.4f} |"
        )
    lines += [
        "",
        "## 执行阶段观测",
        "",
        "下列均为‘会话至少出现一次’的计数，阶段可重叠，不能相加为根因或临时总分；计算成功本身不证明所求数量正确。",
        "",
        "| 模型群 / 条件 | 会话 | 非空发现 | 非空查询 | 数值读取 | 成功计算 | Final | 完整 Q | 工具错误 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for kind, conditions in matrix["separate_model_kind_populations"].items():
        for condition, group in conditions.items():
            stages = group["stage_session_counts"]
            values = [
                stages[key]
                for key in (
                    "nonempty_discovery_return",
                    "nonempty_query_observed",
                    "numeric_source_read_observed",
                    "successful_calculation_observed",
                    "runtime_recognized_final",
                    "financial_qualified",
                    "any_tool_error",
                )
            ]
            lines.append(
                f"| {kind} / {condition} | {group['sessions']} | "
                + " | ".join(map(str, values))
                + " |"
            )
    lines += [
        "",
        "## 已见公开历史的单步条件能力",
        "",
        "计算前与 Final 前的续接分别汇总，语义检查允许合法替代表达式；逐字匹配仅作描述。null 表示不适用或未确定，不合并为失败。",
        "",
        "| 模型群 / 前缀边界 | 响应 | 语义计算成功 | 语义立即 Final 成功 |",
        "|---|---:|---:|---:|",
    ]
    for kind, boundaries in report["conditional_prefix_diagnostic"][
        "by_model_kind_and_boundary"
    ].items():
        for boundary, group in boundaries.items():
            cells = []
            for key in ("semantic_calculation_success", "semantic_immediate_final_success"):
                value = group["components"][key]
                cells.append(
                    f"{value['true']}/{value['determined_denominator']}（未定/不适用 {value['not_applicable_or_undetermined']}）"
                )
            lines.append(
                f"| {kind} / {boundary} | {group['responses']} | " + " | ".join(cells) + " |"
            )
    lines += [
        "",
        "### 前缀各层语义与未知分母",
        "",
        "单元格为 true / 已确定分母；括号列出不适用或未确定。所求数量与来源表达式的判定采用固定公开参考，不能将未证明等价直接称为错误。",
        "",
        "| 模型群 / 边界 | 语义字段 | true / 已确定 | 未定或不适用 |",
        "|---|---|---:|---:|",
    ]
    for kind, boundaries in report["conditional_prefix_diagnostic"][
        "by_model_kind_and_boundary"
    ].items():
        for boundary, group in boundaries.items():
            for field, value in group["components"].items():
                lines.append(
                    f"| {kind} / {boundary} | `{field}` | {value['true']}/{value['determined_denominator']} | {value['not_applicable_or_undetermined']} |"
                )
            lines += ["", f"{kind} / {boundary} 状态分布：`{group['status_counts']}`。", ""]
    history = report["history_R0"]["old_budget_summary"]
    lines += [
        "",
        "## 历史 R0 背景（不纳入同 R1 说明效应）",
        "",
        f"复用旧条件九个微调模型 × 同三题的 {history['completed_scored_sessions']} 条已评分结果：Final {history['recognized_Final']}，完整 Q {history['financial_valid']}。没有新增 R0 生成或评分。",
        "这些历史观测只来自既有小比较摘要，不重新扫描旧会话；其运行时间和硬件占用与本轮不同，不能混入 Δ_doc。",
        "",
    ]
    lines += [
        "## 每模型运行资源",
        "",
        "下表为 worker 内实际耗时及实测峰值，不含排队，不能把十行耗时相加当总墙钟时长。",
        "",
        "| 模型 | 预定条件顺序 | worker 秒 | 实际模型调用 | 实测保留显存峰值 GiB |",
        "|---|---|---:|---:|---:|",
    ]
    for row in report["worker_execution"]:
        peak = row["peak_GPU_memory"]
        reserved = peak.get("reserved_bytes") if isinstance(peak, dict) else None
        peak_text = (
            f"{reserved / (1024**3):.3f}" if isinstance(reserved, (int, float)) else "未记录"
        )
        lines.append(
            f"| {row['model_key']} | {' → '.join(row['condition_order'])} | {row['elapsed_seconds']:.2f} | {row['actual_model_generation_calls']} | {peak_text} |"
        )
    usage = report["resource_usage"]
    lines += [
        "",
        "## 资源及解释边界",
        "",
        f"实际模型生成调用：{usage['actual_model_generation_calls']}，固定上限 1,980；实际生成 token：{usage['generated_tokens']}。",
        "旧 R0 及高预算结果不重算、不回填。本轮两条件同为 R1，主对照不混入历史硬件和运行时条件差异。",
        "三个独特任务不足以推出总体显著收益、某分布更优或 VTDO 有效/无效。基座比较只能提供条件相关的诊断线索。",
        "来源发现、Final 恢复与完整财务合格是不同层次；Probe 提供的公开历史不能计作 Student 自主证据获取能力。",
        "固定矩阵完成即收口：不因正例提前停止，不因零结果追加样本，不自动扩展剩余 1,593 个开发会话，也不恢复 B、确认实验、训练或改变损失。",
        "",
        "逐任务配对值、未知/失败分母及回执见 `trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/delivery_r1_contrast_20260915/report.json`；新会话的只读观测账另保留在该运行目录 `session_ledgers/`。",
        "",
    ]
    return "\n".join(lines)


def run(root, output, plan):
    root = Path(root).resolve()
    output = Path(output)
    output = output if output.is_absolute() else root / output
    output = output.resolve()
    p.require(
        output.is_relative_to(root) and output != root and output.is_dir(), "R1_report.output_scope"
    )
    p.require(
        not (output / "report.json").exists() and not (output / "report.md").exists(),
        "R1_report.one_final_aggregation",
    )
    _record_id(plan)
    tasks, models, prefixes = list(plan["task_ids"]), list(plan["models"]), list(plan["prefixes"])
    p.require(
        len(tasks) == len(set(tasks)) == 3
        and len(models) == 10
        and Counter(row["model_kind"] for row in models) == {"finetuned": 9, "unfinetuned_base": 1}
        and len(prefixes) == 6
        and len({row["id"] for row in prefixes}) == 6,
        "R1_report.exact_registered_60_plus_60_design",
    )
    prefix_ids = {row["id"] for row in prefixes}
    references, rows, prefix_rows, ledgers, worker_execution = [], [], [], [], []
    usage = Counter()
    reports_by_condition = {condition: [] for condition in CONDITIONS}
    actual_models = []
    for model in models:
        key = model["key"]
        p.require(isinstance(key, str) and key == Path(key).name, "R1_report.model_directory_key")
        worker, worker_ref = _read(root, output, output / "workers" / key / "report.json")
        scored, scored_ref = _read(root, output, output / "workers" / key / "assessment.json")
        p.require(
            worker["plan_id"] == scored["plan_id"] == plan["id"]
            and worker["model_key"] == scored["model_key"] == key
            and worker["model_kind"] == scored["model_kind"] == model["model_kind"]
            and worker["actual_complete"] is True
            and scored["actual_complete"] is True
            and scored["generation_worker_report_id"] == worker["id"]
            and scored["process_id"] != worker["process_id"]
            and scored["actual_model_generation_calls"] == 0,
            "R1_report.actual_independent_generation_and_CPU_assessment_workers",
        )
        worker_execution.append(
            {
                key: worker[key]
                for key in (
                    "model_key",
                    "condition_order",
                    "elapsed_seconds",
                    "actual_model_generation_calls",
                    "peak_GPU_memory",
                    "finished_at",
                    "physical_model_loads",
                )
            }
        )
        references.extend((worker_ref, scored_ref))
        generations, assessments = worker["generation_reports"], scored["assessment_reports"]
        p.require(
            set(generations) == set(assessments) == set(CONDITIONS),
            "R1_report.both_conditions_present",
        )
        checkpoint_ids = set()
        metadata = dict(model)
        for condition in CONDITIONS:
            generation, reference = _reference(root, output, generations[condition])
            score, score_ref = _reference(root, output, assessments[condition])
            references.extend((reference, score_ref))
            p.require(
                generation["actual_complete"] is True
                and score["actual_complete"] is True
                and generation["condition"] == score["condition"] == condition
                and generation["model_kind"] == score["model_kind"] == model["model_kind"]
                and score["generation_report_id"] == generation["id"]
                and score["model_identity_id"] == generation["model_identity_id"]
                and generation["checkpoint_id"] == score["checkpoint_id"] == model["checkpoint_id"]
                and generation["execution_kind"] == "actual_local_model"
                and generation["requested_task_count"] == generation["completed_task_count"] == 3,
                "R1_report.complete_same_bound_model_condition",
            )
            checkpoint_ids.add(generation["checkpoint_id"])
            metadata.update(arm=generation["arm"], seed=generation["seed"])
            outcomes = {row["task_id"]: row for row in score["outcomes"]}
            p.require(
                len(outcomes) == len(score["outcomes"]) == 3 and set(outcomes) == set(tasks),
                "R1_report.exact_three_task_score_denominator",
            )
            result_rows = {row["task_id"]: row for row in generation["results"]}
            p.require(
                len(result_rows) == len(generation["results"]) == 3
                and set(result_rows) == set(tasks),
                "R1_report.exact_three_actual_sessions",
            )
            generation_directory = (root / reference["path"]).parent
            for task in tasks:
                result_row = result_rows[task]
                result, result_ref = _read(
                    root,
                    output,
                    generation_directory / result_row["result_path"],
                    expected_id=result_row["result_id"],
                )
                session, session_ref = _read(
                    root,
                    output,
                    generation_directory / result["runtime_session_path"],
                    expected_id=result["runtime_session_id"],
                    maximum=observational.MAX_SESSION_BYTES,
                )
                p.require(
                    session["identity"]["task_id"] == task
                    and session["max_responses"] == session["max_tools"] == 32,
                    "R1_report.original_budget_saved_session",
                )
                ledger, _ = observational.analyze_session(
                    session, session_ref, key, "R1/" + condition
                )
                ledger_path = output / "session_ledgers" / condition / key / (task + ".json")
                p.write_once(ledger_path, ledger)
                outcome = outcomes[task]
                p.require(
                    not outcome["financial_valid"] or ledger["flags"]["runtime_recognized_final"],
                    "R1_report_qualified_requires_runtime_Final",
                )
                rows.append(
                    {
                        "model_key": key,
                        "model_kind": model["model_kind"],
                        "condition": condition,
                        "task_id": task,
                        "group": outcome["group"],
                        "financial_valid": outcome["financial_valid"],
                        "reason": outcome["reason"],
                        "quantity_status": outcome["quantity_status"],
                        "support_status": outcome["support_status"],
                        "runtime_terminal": session["terminal"],
                        "assessment_id": outcome["assessment_id"],
                        "generation_result_id": result["id"],
                        "runtime_session_id": session["id"],
                        "ledger_id": ledger["id"],
                        "ledger_path": str(ledger_path.relative_to(root)),
                        "stages": session_stages(ledger, outcome["financial_valid"]),
                    }
                )
                ledgers.append(ledger)
                references.extend((result_ref, session_ref))
            current = generation["resource_usage"]
            for field in (
                "actual_model_generation_calls",
                "actual_GPU_generation_calls",
                "generated_tokens",
                "context_rejections",
                "callback_attempts",
                "model_weight_loads",
                "final_adapter_loads",
            ):
                p.require(
                    type(current[field]) is int and current[field] >= 0,
                    "R1_report_explicit_nonnegative_resource_counts",
                )
                usage[field] += current[field]
            reports_by_condition[condition].append(
                {
                    "model_key": key,
                    "generation_report_id": generation["id"],
                    "assessment_report_id": score["id"],
                }
            )
        p.require(len(checkpoint_ids) == 1, "R1_report_same_checkpoint_in_both_conditions")
        actual_models.append(metadata)
        predictions = {row["prefix_id"]: row for row in worker["prefix_results"]}
        semantics = {row["prefix_id"]: row for row in scored["prefix_semantics"]}
        p.require(
            len(predictions)
            == len(worker["prefix_results"])
            == len(semantics)
            == len(scored["prefix_semantics"])
            == 6
            and set(predictions) == set(semantics) == prefix_ids,
            "R1_report_all_six_fixed_prefixes_per_model",
        )
        for prefix_id in sorted(prefix_ids):
            pred_ref, sem_ref = predictions[prefix_id], semantics[prefix_id]
            prediction, source = _read(
                root, output, pred_ref["prediction_path"], expected_id=pred_ref["prediction_id"]
            )
            semantic, semantic_source = _read(
                root, output, sem_ref["semantics_path"], expected_id=sem_ref["semantics_id"]
            )
            p.require(
                prediction["prefix_record_id"] == semantic["prefix_record_id"] == prefix_id
                and semantic["prediction_record_id"] == prediction["id"]
                and prediction["model_kind"] == model["model_kind"]
                and prediction["checkpoint_id"] in checkpoint_ids
                and prediction["boundary"] == semantic["boundary"]
                and semantic["autonomous_task_success_claimed"] is False
                and semantic["financial_qualification_score"] is None,
                "R1_report_conditional_prefix_semantics_not_autonomous_score",
            )
            prefix_rows.append(
                {
                    "model_key": key,
                    "model_kind": model["model_kind"],
                    "prefix_id": prefix_id,
                    "boundary": prediction["boundary"],
                    "prediction": prediction,
                    "semantics": semantic,
                }
            )
            references.extend((source, semantic_source))
            usage["prefix_actual_model_generation_calls"] += prediction[
                "actual_model_generation_calls"
            ]
            usage["prefix_actual_GPU_generation_calls"] += prediction["actual_GPU_generation_calls"]
            usage["prefix_generated_tokens"] += len(prediction["generated_token_ids"])
    p.require(
        len(rows) == len(ledgers) == 60 and len(prefix_rows) == 60,
        "R1_report_complete_fixed_matrix",
    )
    usage["full_session_actual_model_generation_calls"] = usage["actual_model_generation_calls"]
    usage["full_session_generated_tokens"] = usage["generated_tokens"]
    usage["actual_model_generation_calls"] += usage["prefix_actual_model_generation_calls"]
    usage["actual_GPU_generation_calls"] += usage["prefix_actual_GPU_generation_calls"]
    usage["generated_tokens"] += usage["prefix_generated_tokens"]
    p.require(
        usage["actual_model_generation_calls"] <= 1980, "R1_report_authorized_1980_generation_bound"
    )
    p.require(
        usage["actual_model_generation_calls"]
        == sum(row["actual_model_generation_calls"] for row in worker_execution),
        "R1_report_worker_and_saved_generation_count_join",
    )
    report = p.record(
        "delivery_r1_final_report",
        plan_id=plan["id"],
        status="COMPLETE_FIXED_R1_DIAGNOSTIC",
        R1_same_tool_documentation_comparison=summarize_matrix(rows, tasks, actual_models),
        conditional_prefix_diagnostic=summarize_prefixes(prefix_rows),
        new_session_observations_by_condition={
            condition: observational.aggregate(
                [row for row in ledgers if row["population"] == "R1/" + condition], 30
            )
            for condition in CONDITIONS
        },
        resource_usage=dict(usage),
        resource_limit_model_generation_calls=1980,
        worker_execution=worker_execution,
        score_and_generation_reports=reports_by_condition,
        complete_session_rows=rows,
        prefix_semantics_rows=[
            {key: value for key, value in row.items() if key != "prediction"} for row in prefix_rows
        ],
        observation_definitions=STAGE_DEFINITIONS,
        input_references=references,
        history_R0=historical_background(root, plan),
        audit_scope={
            "new_runtime_sessions_read_once": 60,
            "old_1647_runtime_sessions_read": 0,
            "decoder_callback_files_read": 0,
            "financial_regrading_performed": 0,
            "original_stage_A_pure_analyzer_reused": True,
        },
        decision="FIXED_MATRIX_COMPLETE_STOP_NO_AUTOMATIC_EXPANSION",
        original_R0_and_budget_results_overwritten=False,
        new_training_B_or_confirmation_authorized_by_report=False,
        isolated_three_task_diagnostic_not_population_effect_proof=True,
    )
    p.write_once(output / "report.json", report)
    with (output / "report.md").open("x", encoding="utf-8") as stream:
        stream.write(render_markdown(report))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.root, args.output, p.read_json(args.plan))
    print(result["id"])


if __name__ == "__main__":
    main()
