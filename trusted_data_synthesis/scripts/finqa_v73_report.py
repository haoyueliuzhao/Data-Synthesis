"""Read-only V73 final-report extraction, gated on accepted actual exits.

This standalone stdlib tool is outside the scientific frozen implementation.
It never imports model/scorer modules, opens raw episodes/tensors/operation
returns, or changes an experiment record. Output files must be new.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo


REPO = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v73_same_context_probe_01/execution_revision_02"
MODELS = ("P", "H", "L")
JOBS = {f"{model}.shard{shard}" for model in MODELS for shard in range(2)}
CATEGORIES = ("compliant_submit_candidate", "compliant_nonterminal_candidate", "attempted_invalid_submit", "plain_no_tool_call", "other_contract_failure", "UNKNOWN")
MAIN_GROUPS = ("pre_action_text", "action_structure", "program_parameter_content", "actual_terminal_EOS")
GROUP_LABELS = dict(pre_action_text="动作前公开文字", action_structure="工具结构、动作名及字段结构",
    program_parameter_content="程序参数内容", actual_terminal_EOS="实际终末EOS",
    boundary_mixed="跨类别边界token", post_action_whitespace="动作后空白")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class Reader:
    def __init__(self):
        self.sources, self.cache = {}, {}

    def read(self, path_or_ref):
        ref = path_or_ref if isinstance(path_or_ref, dict) else None
        path = Path(ref["path"] if ref else path_or_ref).resolve()
        require(path.name == "record.json" and not {"episodes", "outputs", "training"}.intersection(path.parts),
            "report input must be a bounded summary/acceptance record, never a raw scientific payload")
        key = str(path)
        if key not in self.cache:
            raw = path.read_bytes()
            value = json.loads(raw)
            require(value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
                "immutable report source ID changed: " + key)
            self.cache[key] = value
            self.sources[key] = dict(path=key, sha256=hashlib.sha256(raw).hexdigest(), id=value["id"], bytes=len(raw))
        if ref:
            require(self.sources[key]["sha256"] == ref["sha256"] and self.sources[key]["id"] == ref["id"],
                "report source reference changed: " + key)
        return self.cache[key]


def _exit_zero(record):
    require(record.get("actual_waitpid_observed") is True and record.get("returncode") == 0,
        "report requires observed waitpid exit zero")


def extract(root=DEFAULT_ROOT, *, reader=None):
    """Gate first; do not inspect interim classifications if execution is live."""
    root, reader = Path(root).resolve(), reader or Reader()
    closeout = reader.read(root / "closeout/record.json")
    require(closeout["status"] == "COMPLETE" and closeout["active_workers"] == 0,
        "V73 has not completed; no interim report or extra work is authorized")
    require(set(closeout["accepted_jobs"]) == JOBS, "six accepted GPU shards are required")
    protocol = reader.read(root / "protocol/record.json")
    require(closeout["protocol_id"] == protocol["id"] and set(protocol["jobs"]) == JOBS,
        "final protocol or fixed job matrix changed")
    jobs, identities = {}, set()
    for name in sorted(JOBS):
        directory = root / "jobs" / name
        accepted = reader.read(directory / "accepted/record.json")
        actual, result = reader.read(accepted["actual_exit"]), reader.read(accepted["result"])
        launch = reader.read(directory / "attempts" / f"attempt{accepted['attempt']:04d}" / "launch/record.json")
        _exit_zero(actual)
        require(accepted["actual_exit_zero"] is True and accepted["resources_passed"] is True,
            "shard acceptance is incomplete")
        require(accepted["protocol_id"] == actual["protocol_id"] == result["protocol_id"] == launch["protocol_id"] == protocol["id"],
            "shard protocol identity mismatch")
        require(accepted["job_id"] == actual["job_id"] == result["job_id"] == name
            and result["job"] == protocol["jobs"][name] == launch["job"], "shard job identity mismatch")
        require(actual["pid"] == result["pid"] == launch["pid"] and actual["birth"] == launch["birth"]
            and actual["attempt"] == accepted["attempt"] == launch["attempt"]
            and actual["gpu_index"] == result["gpu_index"] == launch["gpu_index"], "actual worker identity mismatch")
        require((actual["pid"], actual["birth"]) not in identities, "one worker cannot count as two shards")
        identities.add((actual["pid"], actual["birth"]))
        require(result["status"] == "COMPLETE" and result["id"] == accepted["result_id"]
            and result["resources"]["all_gates_passed"] is True and result["model_released"] is True,
            "actual shard result/resource gate incomplete")
        require(all(result[k] == 0 for k in ("optimizer_updates", "tools_executed", "native_scores", "external_API_calls")),
            "report cannot reclassify an expanded scientific budget")
        jobs[name] = dict(accepted=accepted, actual_exit=actual, launch={k: launch[k]
            for k in ("pid", "birth", "gpu_index", "gpu_uuid", "started_epoch")},
            result={k: v for k, v in result.items() if k not in ("output_refs", "resources")},
            resources={k: result["resources"].get(k) for k in ("all_gates_passed", "peak_allocated_bytes", "peak_rss_bytes",
                "minimum_boundary_free_bytes", "minimum_host_available_bytes", "resource_wait_seconds",
                "received_signals", "observed_violation", "single_process_lifetime_includes_loading", "peak_resets_after_loading")})
    cpu_accepted = reader.read(root / "final_analysis/accepted/record.json")
    cpu_exit, cpu_result = reader.read(cpu_accepted["actual_exit"]), reader.read(cpu_accepted["result"])
    cpu_resources = reader.read(cpu_accepted["resources"])
    _exit_zero(cpu_exit)
    require(cpu_result["status"] == cpu_resources["status"] == "COMPLETE"
        and cpu_resources["all_gates_passed"] is True and cpu_resources["CUDA_initialized"] is False,
        "final CPU analysis/resource gate incomplete")
    require(cpu_accepted["protocol_id"] == cpu_exit["protocol_id"] == cpu_result["protocol_id"] == cpu_resources["protocol_id"] == protocol["id"],
        "final CPU protocol mismatch")
    require(cpu_exit["pid"] == cpu_result["pid"] == cpu_resources["pid"]
        and cpu_exit["birth"] == cpu_resources["birth"], "actual final CPU identity mismatch")
    require(cpu_accepted["analysis"] == cpu_result["analysis"] == closeout["analysis"],
        "CPU accepted result differs from final scientific analysis")
    supervisor = reader.read(root / "supervisor/closeout/record.json")
    controller_exit = reader.read(supervisor["actual_controller_exit"])
    _exit_zero(controller_exit)
    require(supervisor["status"] == "COMPLETE" and supervisor["protocol_id"] == protocol["id"]
        and supervisor["automatic_restart_stopped"] is True, "supervisor has not settled COMPLETE")
    # The first final classifications/probabilities read occurs only after all
    # six GPU + final CPU + controller actual-exit gates above.
    final = reader.read(cpu_accepted["analysis"])
    require(final["protocol_id"] == protocol["id"] and final["status"] in ("COMPLETE", "COMPLETE_WITH_UNKNOWN"),
        "final summary belongs to another or incomplete run")
    require(final["panel_denominator"] == 96 and final["group_denominators"] == {"F": 48, "K": 48},
        "conditional panel denominator changed")
    for panel in final["panels"].values():
        for model in MODELS:
            for source in MODELS:
                cell = panel["single_response_action_matrix"][model][source]
                require(cell["denominator"] == 48 and sum(cell["categories"].values()) == 48,
                    "report category denominator inconsistent")
                require(cell["A"]["positive_count"] == sum(cell["categories"][name] for name in CATEGORIES[:2])
                    and cell["S"]["positive_count"] == cell["categories"][CATEGORIES[0]], "report A/S category arithmetic inconsistent")
    require(final["physical_generation_results"] == closeout["generation_calls"]
        == sum(row["result"]["generation_results"] for row in jobs.values()), "physical generation count differs")
    require(final["physical_probability_results"] == closeout["probability_sequences"]
        == sum(row["result"]["probability_results"] for row in jobs.values()), "physical probability count differs")
    require(final["physical_generation_results"] <= 864 and final["physical_probability_results"] <= 288,
        "probe exceeded its registered upper bound")
    selection = reader.read(protocol["selection"])
    prior_failure = reader.read(protocol["prior_execution_failure"])
    prior_audit = reader.read(protocol["prior_cold_entry_audit"])
    preparation = reader.read(protocol["rejected_preparation"])
    events = sorted((time, delta) for row in jobs.values() for time, delta in
        ((row["launch"]["started_epoch"], 1), (row["actual_exit"]["observed_epoch"], -1)))
    active = peak = 0
    for _, delta in events:
        active += delta
        peak = max(peak, active)
    result = dict(schema="v73_final_report_source_summary.v1", status="COMPLETE",
        execution_root=str(root), protocol_id=protocol["id"], source_commit=protocol["source_commit"],
        implementation=protocol["implementation"], scientific_contract=protocol["scientific_contract"],
        model_bindings=protocol["model_bindings"], measurement_policy=protocol["measurement_policy"],
        resource_policy=protocol["resource_policy"], final_summary=final,
        selection={k: v for k, v in selection.items() if k not in ("candidates", "original_source_refs")},
        execution=dict(closeout=closeout, jobs=jobs, peak_dispatched_worker_concurrency=peak,
            final_CPU=dict(accepted=cpu_accepted, actual_exit=cpu_exit, result=cpu_result,
                resources={k: v for k, v in cpu_resources.items() if k != "observations"}),
            supervisor_closeout=supervisor, controller_actual_exit=controller_exit,
            supervisor_own_waitpid_exit_code_available=False),
        historical_records=dict(prior_execution_failure=prior_failure, prior_cold_entry_audit=prior_audit,
            rejected_preparation=preparation, reclassified_as_pass=False),
        report_read_policy=dict(final_exit_gates_before_classification_read=True,
            raw_episodes_or_Tensors_or_operation_returns_opened=False,
            new_models_or_GPU_or_API_or_tools_or_native_scores_or_optimizer_updates=0,
            original_scientific_records_written=0, source_JSON_count=len(reader.sources)),
        extractor=dict(path=str(Path(__file__).resolve()), sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        sources=list(reader.sources.values()))
    result["id"] = digest(result)
    return result


def number(value, digits=6):
    return "NA" if value is None else f"{value:.{digits}f}"


def timestamp(epoch):
    return datetime.fromtimestamp(epoch, ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers),
        *("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)])


def render_report(data, *, report_date="2026-10-25", summary_filename="finqa_v73_report_summary_20261025.json"):
    final, execution = data["final_summary"], data["execution"]
    closeout, jobs = execution["closeout"], execution["jobs"]
    parts = ["# FinQA V73 最终实验报告：同上下文提交行为与固定父回应概率",
        f"报告日期：{report_date}，时间口径为北京时间。科学执行状态：`{closeout['status']}`；观测摘要状态：`{final['status']}`。",
        f"本轮仅使用P、H、L三个既有checkpoint，在固定48道残余失效题F及48道保留题K上比较单步回应。实际完成{final['physical_generation_results']}次去重后的单回应生成和{final['physical_probability_results']}条固定父回应概率测量；逻辑矩阵仍为864格生成、288格概率。工具执行、native EA/PA评分、训练和外部API调用均为0。",
        "**A表示静态合规下一动作，S表示静态合规提交候选；二者都不是答案正确率。**合法非终末工具动作计入A，不能自动算作失败。四部分概率指标衡量同一份父模型实际回应在固定前缀下的拟合，不覆盖所有合法表达。",
        f"完整计数、配对迁移、来源SHA及身份见[机器摘要](report_data/{summary_filename})。本报告仅整理已封存结果，没有补跑任务或改写原评分。",
        "## 1. 固定模型、样本与输入",
        table(["模型", "既有状态", "用途"], [["P", "V71固定分布step1192，未做LR干预", "共同父点"],
            ["H", "V71固定分布step1490，原后段LR=1e−4", "高学习率后继"],
            ["L", "V72低LR step1490，后段LR=1e−5", "低学习率后继"]]),
        "F从125道P原生R、L原生I且缺少有效终末提交、以no_tool_call结束的题中选48；K从380道P与L均原生R的题中选48，未额外要求H正确。按固定盐值、完整任务ID和既有来源簇哈希排序后轮转选样，先封存名单，缺档不换题。",
        table(["组", "候选数", "固定样本数", "选中来源簇数", "单簇最多选题"], [[group,
            data["selection"]["candidate_counts"][group], 48,
            len(data["selection"]["source_distributions"][group]["selected"]),
            max(data["selection"]["source_distributions"][group]["selected"].values(), default=0)] for group in ("F", "K")]),
        "hP是P原来有效submit_program前的完整真实输入，hH/hL是H/L原episode最后一次模型调用前的完整真实输入。所有原消息、工具结果和错误历史保持；从保存请求重建后核对原prompt字节SHA和每个token。父当前回应只进入独立概率通道，不进入自由生成输入。",
        f"96×3共有288个逻辑来源历史；按实际输入事前去重后对应{final['physical_generation_results'] // 3}个独特上下文。相同模型和输入共享一次新结果，保留全部来源标签，不重复调用挑选结果。两组是按旧结果条件选出的机制样本，不能把50∶50比例当作883题总体失效率，也不是96次独立训练重复。",
        "## 2. F与K的三模型乘三历史动作矩阵",
        "表格单元为A阳性数/S阳性数，完整分母均为48。UNKNOWN单列，未观测结果不算普通文字或阴性。"]
    for group in ("F", "K"):
        panel = final["panels"][group]
        rows = []
        for model in MODELS:
            values = []
            for source in MODELS:
                cell = panel["single_response_action_matrix"][model][source]
                values.append(f"A {cell['A']['positive_count']}/48；S {cell['S']['positive_count']}/48；UNKNOWN {cell['unknown_count']}")
            rows.append([model, *values])
        parts.extend([f"### {group}组", table(["模型", "hP", "hH", "hL"], rows)])
        categories = []
        for model in MODELS:
            for source in MODELS:
                counts = panel["single_response_action_matrix"][model][source]["categories"]
                categories.append([f"{model}(h{source})", *(counts[name] for name in CATEGORIES)])
        parts.append(table(["格子", "合规提交", "合规非终末", "提交尝试不合规", "普通文字无调用", "其他合同失败", "UNKNOWN"], categories))
    parts.extend(["## 3. 首要读数：同一父历史hP上的跨模型获得与丢失",
        "方向始终为参照→候选；新增是0→1，丢失是1→0。若存在未知配对，只给已知对的计数，完整面板差值记NA，不以删题缩分母。"])
    pairs = []
    for group in ("F", "K"):
        for name, pair in final["panels"][group]["primary_hP_paired_models"].items():
            for metric in ("A", "S"):
                x = pair[metric]
                pairs.append([group, name.replace("_minus_", "−"), metric, x["gained"], x["lost"],
                    x["net_known_pairs"], number(x["complete_panel_difference"] * 100 if x["complete_panel_difference"] is not None else None), pair["unknown_pair_count"]])
    parts.append(table(["组", "候选−参照", "指标", "新增", "丢失", "已知对净数", "完整分母差，百分点", "未知对"], pairs))
    parts.append("同一hP下跨模型的差异排除了调用前历史不一致，但本次回应内部仍可生成不同前置文字，不能仅由动作矩阵宣布工具语法遗忘。跨hP/hH/hL列的差异反映上下文敏感性；历史包含的信息和执行阶段不同，不能转化为退化的历史因果占比。所有固定历史的模型配对、固定模型的历史配对及完整类别迁移均保留在机器摘要。")
    parts.extend(["## 4. 源模型在原历史上的再现核查",
        "旧对角线结果用于选样，本身不是新发现。下表比较新单回应与对应旧实际回应的原文SHA、完整生成token序列；差异保留，不重试或替换。"])
    rows = []
    for group in ("F", "K"):
        for model in MODELS:
            diag = final["panels"][group]["source_model_source_history_reproduction"][model]
            rows.append([group, f"{model}(h{model})", diag["raw_identical"], diag["raw_different"], diag["raw_unknown"],
                diag["token_ids_identical"], diag["token_ids_different"], diag["token_ids_unknown"]])
    parts.append(table(["组", "对角线", "原文相同", "原文不同", "原文未知", "token相同", "token不同", "token未知"], rows))
    parts.append("原文相同和token完全相同分开报告。若对角线无法再现，应优先限制比较有效性的解释；本轮没有事后发明允许多少差异的晋级门，也不据此自动启动重训。")
    parts.extend(["## 5. 固定父回应的条件NLL",
        "每个模型在相同hP及相同父回应前缀下，对原实际目标token计算完整词表原始logits的float32 log_softmax，无温度变换、词表筛选或反传。因果位置取目标token之前的logit。NLL越大，只表示对这份指定父表达的条件拟合更差。",
        "主表为每条序列组内平均NLL的跨题均值与中位数，单位nat/token；不是把所有token混在一起加权的均值。没有该部分记NA，不填零；未取得测量记UNKNOWN。两种情况与合法测量中的数值0不同。"])
    for group in ("F", "K"):
        rows = []
        for part in MAIN_GROUPS:
            for model in MODELS:
                value = final["panels"][group]["fixed_parent_response_probability"][model][part]
                stats = value["per_sequence_mean_nll"]
                rows.append([GROUP_LABELS[part], model, number(stats["mean"]), number(stats["median"]),
                    value["measured_sequences"], value["NA_empty_group_sequences"], value["UNKNOWN_sequences"]])
        parts.extend([f"### {group}组四个主要部分", table(["部分", "模型", "跨题均值", "跨题中位数", "测得/48", "NA", "UNKNOWN"], rows)])
        differences = []
        for name, sections in final["panels"][group]["paired_probability_changes"].items():
            for part in MAIN_GROUPS:
                value = sections[part]; stats = value["candidate_minus_reference_mean_nll"]
                differences.append([name.replace("_minus_", "−"), GROUP_LABELS[part], number(stats["mean"]), number(stats["median"]),
                    f"{value['positive_delta_count']}/{value['negative_delta_count']}/{value['exact_zero_delta_count']}", value["measured_pairs"],
                    value["NA_empty_group_pairs"], value["UNKNOWN_pairs"]])
        parts.append(table(["候选−参照", "部分", "同题Δ均值", "同题Δ中位数", "正/负/精确零", "测得对/48", "NA", "UNKNOWN"], differences))
    parts.append("正Δ表示候选对固定父表达的NLL更高，负Δ表示更低；没有将某个容差或p值作为成功门。程序参数字符串内容与工具结构分开，跨类别BPE token和动作后空白各自独立保存，不偷偷归入结构。四组的计数、池化token均值以及两个辅助组的全部统计均在机器摘要。")
    boundary_rows = []
    for group in ("F", "K"):
        for part in ("boundary_mixed", "post_action_whitespace"):
            for model in MODELS:
                value = final["panels"][group]["fixed_parent_response_probability"][model][part]
                boundary_rows.append([group, GROUP_LABELS[part], model, value["measured_target_token_count"],
                    number(value["per_sequence_mean_nll"]["mean"]), value["NA_empty_group_sequences"], value["UNKNOWN_sequences"]])
    parts.append(table(["组", "辅助部分", "模型", "测得目标token", "跨题NLL均值", "NA", "UNKNOWN"], boundary_rows))
    parts.extend(["## 6. 实际计算成本、资源与退出",
        f"科学收口时间为{timestamp(closeout['finished_epoch'])}。六个GPU分片全部accepted并有真实waitpid=0；最终CPU分析及controller也有真实waitpid=0。监督器记录为COMPLETE并关闭自动恢复；没有监督器自身父进程waitpid码，不能补造。按派发至真实退出计算的最大worker并行为{execution['peak_dispatched_worker_concurrency']}。"])
    rows = []
    for name, row in jobs.items():
        value = row["result"]
        rows.append([name, value["gpu_index"], row["accepted"]["attempt"], timestamp(row["launch"]["started_epoch"]),
            timestamp(row["actual_exit"]["observed_epoch"]), value["generation_results"], value["probability_results"]])
    parts.append(table(["作业", "GPU", "attempt", "派发时间", "真实退出", "单回应生成", "概率序列"], rows))
    cost_labels = {"actual_model_generate_calls": "实际model.generate调用", "probability_sequences": "固定父回应概率序列",
        "generation_prompt_tokens": "生成输入token累计", "new_response_tokens": "新生成token累计（含实际EOS）",
        "probability_prompt_tokens": "概率测量输入历史token累计", "fixed_response_tokens": "固定父回应目标token累计",
        "model_forward_calls": "模型forward调用", "transformer_forward_calls": "Transformer forward调用", "lm_head_forward_calls": "lm_head forward调用",
        "model_input_positions": "模型forward输入位置累计", "transformer_input_positions": "Transformer输入位置累计", "lm_head_input_positions": "lm_head输入位置累计"}
    parts.append(table(["实际计数", "数量"], [[cost_labels.get(key, key), value] for key, value in sorted(final["actual_costs"].items())]))
    parts.append("单回应生成不是完整Agent轨迹，概率序列不是新回答；自回归内部forward与输入任务数量分别报告。以上是本次已保存返回的实际计数，不用逻辑864+288替代底层计算次数。")
    resources = []
    for name, row in jobs.items():
        value = row["resources"]
        resources.append([name, *(number(value[key] / 1024 ** 3 if value[key] is not None else None, 3) for key in
            ("peak_allocated_bytes", "peak_rss_bytes", "minimum_boundary_free_bytes", "minimum_host_available_bytes"))])
    parts.append(table(["作业", "allocated峰GiB", "RSS峰GiB", "最小边界free GiB", "最小有效可用RAM GiB"], resources))
    cpu = execution["final_CPU"]["resources"]
    parts.append(f"GPU资源门均通过；初始化、资源等待和draining计入worker名额，模型加载计入历史峰值。最终CPU未初始化CUDA，RSS峰{number(cpu['peak_rss_bytes'] / 1024 ** 3, 3)}GiB，运行{number(cpu['finished_epoch'] - cpu['started_epoch'], 2)}秒，资源门通过。控制器累计资源等待记录为{number(closeout['resource_wait_seconds'], 2)}秒，worker各自等待另存，不能混同。")
    parts.extend(["## 7. 准备修订、历史失败与解释边界",
        "原准备记录包括来源引用封存顺序及tools字典插入顺序问题；后者来自原JSON按键排序与Qwen tools|tojson保留插入顺序的差异。修订只从冻结工具工厂恢复顺序，要求工具值和语义digest完全相同，再严格匹配原render SHA及每个token，没有改写历史或放宽输入门。",
        f"旧execution_revision_01终态为`{data['historical_records']['prior_execution_failure']['status']}`。其冷入口审计与停止记录完整保留，不因本次execution_revision_02完成而追认为通过。本报告不修改上述历史记录，也不把CPU准备或来源核验当作已完成模型计算。",
        "本轮只能分别观察调用前历史、本次回应自由续写及固定父前缀下的局部条件预测。若动作失效与结构NLL上升同时出现，可以支持关注相同条件下的动作保持；若只有自由生成动作变化而固定前缀结构NLL没有变差，则不能直接称工具语法遗忘。结果也可能混合，不能强行归于单一原因。",
        "条件选样、单一父点和既有训练随机实现限制外推；没有新的训练重复、开发集整体EA/PA、测试集验证或学习率搜索。本轮不证明必须从头训练、旧模型不可恢复或任何内层规则最优。结束后不自动重训、追加1490修复或恢复Full。",
        "## 8. 来源与本次报告操作",
        f"科学根：`{data['execution_root']}`。协议ID：`{data['protocol_id']}`。科学源提交：`{data['source_commit']}`。最终观测摘要ID：`{final['id']}`。",
        f"报告提取器只读取{data['report_read_policy']['source_JSON_count']}份必要封存JSON，每份字节只读一次并保存SHA256与原记录ID。先检查科学COMPLETE、六GPU/最终CPU/controller实际退出成功，再读取最终分类和概率摘要。没有打开原episode、Tensor、逐操作返回或重跑评分，也没有修改科学记录。报告派生摘要ID：`{data['id']}`。",
        "本地原始响应、逐token概率、模型状态和冻结实现仍保留原目录；Git中的报告与机器摘要不是全部实验产物的远端备份。"])
    return "\n\n".join(parts) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--summary", type=Path, default=REPO / "trusted_data_synthesis/docs/report_data/finqa_v73_report_summary_20261025.json")
    parser.add_argument("--report", type=Path, default=REPO / "trusted_data_synthesis/docs/finqa_v73_final_experiment_report_20261025.md")
    parser.add_argument("--report-date", default="2026-10-25")
    args = parser.parse_args(argv)
    require(not args.summary.exists() and not args.report.exists(), "report outputs already exist; do not overwrite a published report")
    data = extract(args.root)
    report = render_report(data, report_date=args.report_date, summary_filename=args.summary.name)
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.summary.open("x", encoding="utf-8") as stream:
        stream.write(raw)
    with args.report.open("x", encoding="utf-8") as stream:
        stream.write(report)
    print(json.dumps(dict(id=data["id"], summary_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        summary=str(args.summary), report=str(args.report), source_JSON_count=len(data["sources"])), ensure_ascii=False))


if __name__ == "__main__":
    main()
