"""Bounded read-only V74 report, after accepted worker/CPU/controller real exits.

This stdlib-only derived report is outside the frozen science implementation.
It reads only sealed summaries and acceptance receipts, never raw episodes,
model/tool returns, checkpoints or private references; it never scores again.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v74_cross_history_continuation_01"
DIRECTIONS = {"L_from_P": "L←hP", "P_from_L": "P←hL"}
CATEGORIES = {"compliant_submit_candidate": "第一回应直接提交", "compliant_nonterminal_candidate": "第一回应非终末后续跑", "plain_no_tool_call": "第一回应无调用"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


class Reader:
    def __init__(self):
        self.cache, self.sources = {}, {}

    def read(self, value):
        ref = value if isinstance(value, dict) else None
        path = Path(ref["path"] if ref else value).resolve()
        require(path.name == "record.json" and not {"episodes","outputs","training","inputs","native_rows"}.intersection(path.parts),
                "report may read only bounded summaries and acceptance records")
        key = str(path)
        if key not in self.cache:
            raw = path.read_bytes(); body = json.loads(raw)
            require(body.get("id") == digest({k:v for k,v in body.items() if k != "id"}), "source record ID changed")
            self.cache[key] = body
            self.sources[key] = dict(path=key,sha256=hashlib.sha256(raw).hexdigest(),id=body["id"],bytes=len(raw))
        if ref:
            require(self.sources[key]["sha256"] == ref["sha256"]
                    and ("id" not in ref or self.sources[key]["id"] == ref["id"]), "source reference changed")
        return self.cache[key]


def _exit_zero(value):
    require(value.get("actual_waitpid_observed") is True and value.get("returncode") == 0,
            "actual waitpid exit zero required")


def extract(root=DEFAULT_ROOT, *, reader=None):
    root, r = Path(root).resolve(), reader or Reader()
    closeout = r.read(root/"closeout/record.json")
    require(closeout["status"] == "COMPLETE" and closeout["active_workers"] == 0
            and closeout["accepted_jobs"] == ["P.continuation"], "V74 is not complete; no interim result report")
    protocol = r.read(root/"protocol/record.json")
    require(closeout["protocol_id"] == protocol["id"] and set(protocol["jobs"]) == {"P.continuation"}, "fixed protocol changed")
    accepted = r.read(root/"jobs/P.continuation/accepted/record.json")
    actual, result = r.read(accepted["actual_exit"]), r.read(accepted["result"])
    launch = r.read(root/"jobs/P.continuation/attempts"/f"attempt{accepted['attempt']:04d}"/"launch/record.json")
    _exit_zero(actual)
    require(accepted["actual_exit_zero"] is True and accepted["resources_passed"] is True
            and result["resources"]["all_gates_passed"] is True and result["model_released"] is True,
            "worker resource or release gate failed")
    require(accepted["protocol_id"] == actual["protocol_id"] == result["protocol_id"] == launch["protocol_id"] == protocol["id"]
            and accepted["job_id"] == actual["job_id"] == result["job_id"] == "P.continuation"
            and result["job"] == launch["job"] == protocol["jobs"]["P.continuation"], "worker coordinate changed")
    require(result["id"] == accepted["result_id"] and result["status"] == "COMPLETE"
            and actual["pid"] == result["pid"] == launch["pid"] and actual["birth"] == launch["birth"]
            and actual["attempt"] == accepted["attempt"] == launch["attempt"]
            and actual["gpu_index"] == result["gpu_index"] == launch["gpu_index"], "worker actual identity changed")
    require(result["terminal_conditions"] == 192 and all(result[k] == 0 for k in
        ("new_first_responses","new_probability_sequences","optimizer_updates","native_scores","external_API_calls")),
        "registered generation/scoring separation changed")
    cpu_accepted = r.read(root/"final_analysis/accepted/record.json")
    cpu_exit, cpu_result, cpu_resources = [r.read(cpu_accepted[k]) for k in ("actual_exit","result","resources")]
    _exit_zero(cpu_exit)
    require(cpu_result["status"] == cpu_resources["status"] == "COMPLETE"
            and cpu_resources["all_gates_passed"] is True and cpu_resources["CUDA_initialized"] is False,
            "CPU result/resource gate incomplete")
    require(cpu_accepted["protocol_id"] == cpu_exit["protocol_id"] == cpu_result["protocol_id"] == cpu_resources["protocol_id"] == protocol["id"]
            and cpu_exit["pid"] == cpu_result["pid"] == cpu_resources["pid"]
            and cpu_exit["birth"] == cpu_resources["birth"], "CPU identity changed")
    require(cpu_accepted["analysis"] == cpu_result["analysis"] == closeout["analysis"], "accepted final summary changed")
    supervisor = r.read(root/"supervisor/closeout/record.json")
    controller_exit = r.read(supervisor["actual_controller_exit"])
    _exit_zero(controller_exit)
    require(supervisor["status"] == "COMPLETE" and supervisor["protocol_id"] == protocol["id"]
            and supervisor["automatic_restart_stopped"] is True, "supervisor not settled complete")
    # All real-exit gates precede the first read of final outcome/accuracy rows.
    final = r.read(cpu_accepted["analysis"])
    require(final["protocol_id"] == protocol["id"] and final["status"] in ("COMPLETE","COMPLETE_WITH_UNKNOWN")
            and final["distinct_tasks"] == 96 and final["conditional_trajectory_denominator"] == final["logical_native_scores"] == 192,
            "complete fixed final panel changed")
    require(final["costs"]["new_model_calls"] == result["new_model_calls"]
            and final["costs"]["new_model_calls"] <= protocol["scientific_contract"]["maximum_new_model_calls"],
            "actual model-call count changed or exceeded cap")
    require(len(final["results"]) == 192 and len({row["condition_id"] for row in final["results"]}) == 192,
            "final logical result coverage changed")
    for panel in final["panels"].values():
        for cell in panel.values():
            require(cell["denominator"] == 48 and sum(cell["states"].values()) == 48,
                    "full F/K conditional denominator changed")
    for row in final["results"]:
        require(row["new_model_calls"] <= row["maximum_new_model_calls"], "per-condition model-call cap exceeded")
    historical = final["context_structure"]
    context_rows = []
    for group in ("F","K"):
        for source in ("hP","hL"):
            selected = [row[source] for row in historical["rows"] if row["group"] == group]
            context_rows.append(dict(group=group,source=source,denominator=len(selected),
                source_b_counts=dict(sorted(Counter(str(row["source_call_index_zero_based"]) for row in selected).items())),
                historical_tool_events=sum(row["already_executed_tool_events"] for row in selected),
                successful_run_program=sum(row["run_program_success_count"] for row in selected),
                failed_run_program=sum(row["run_program_error_count"] for row in selected),
                read_source=sum(row["tool_counts"].get("read_source",0) for row in selected),
                list_sources=sum(row["tool_counts"].get("list_sources",0) for row in selected)))
    nonterminal = [row for row in final["results"] if row["first_action_category"] == "compliant_nonterminal_candidate"]
    history_facts = dict(rows=context_rows,
        total_historical_tool_events=sum(row["historical_tool_events"] for row in context_rows),
        nonterminal_condition_count=len(nonterminal),
        nonterminal_b0_count=sum(row["source_model_calls_before_first"] == 0 for row in nonterminal),
        **{k:historical[k] for k in ("actual_prompt_token_identical_count","programs_and_outputs_identical_count",
            "F_selected_clusters","K_selected_clusters","shared_F_K_cluster_count","union_source_cluster_count")})
    summary = dict(schema="v74_final_report_source_summary.v1",status="COMPLETE",execution_root=str(root),
        protocol_id=protocol["id"],source_commit=protocol["source_commit"],implementation=protocol["implementation"],
        scientific_contract=protocol["scientific_contract"],final_summary=final,context_facts=history_facts,
        execution=dict(closeout=closeout,worker=dict(accepted=accepted,actual_exit=actual,
            launch={k:launch[k] for k in ("pid","birth","gpu_index","gpu_uuid","started_epoch")},
            result={k:v for k,v in result.items() if k not in ("outcomes","output_refs","resources")},
            resources={k:result["resources"].get(k) for k in ("all_gates_passed","peak_allocated_bytes","peak_rss_bytes",
                "minimum_boundary_free_bytes","minimum_host_available_bytes","resource_wait_seconds",
                "single_process_lifetime_includes_loading","peak_resets_after_loading")}),
            final_CPU=dict(accepted=cpu_accepted,actual_exit=cpu_exit,result=cpu_result,
                resources={k:v for k,v in cpu_resources.items() if k != "observations"}),
            supervisor_closeout=supervisor,controller_actual_exit=controller_exit,
            supervisor_own_waitpid_exit_code_available=False),
        read_policy=dict(final_exit_gates_before_result_read=True,source_JSON_count=len(r.sources),
            raw_episodes_Tensors_model_tool_returns_private_references_opened=False,
            new_model_calls_tools_native_scores_optimizer_API=0,original_scientific_records_written=0),
        extractor=dict(path=str(Path(__file__).resolve()),sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        sources=list(r.sources.values()))
    summary["id"] = digest(summary)
    return summary


def number(value, digits=6):
    return "NA" if value is None else f"{value:.{digits}f}"


def count(value):
    if value is None:
        return "NA"
    return str(int(value)) if isinstance(value,(int,float)) and value == int(value) else str(value)


def timestamp(epoch):
    return datetime.fromtimestamp(epoch,ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "|" + "---|"*len(headers),
                      *("| " + " | ".join(str(v) for v in row) + " |" for row in rows)])


def render_report(data, *, report_date="2026-10-26", summary_filename="finqa_v74_report_summary_20261026.json"):
    final, execution, history = data["final_summary"], data["execution"], data["context_facts"]
    costs, panels = final["costs"], final["panels"]
    main_rows, subgroup_rows, direct_rows, paired_rows = [], [], [], []
    for group in ("F","K"):
        for direction,label in DIRECTIONS.items():
            panel = panels[group][direction]
            metrics,states = panel["metrics"],panel["states"]
            main_rows.append([group,label,count(metrics["execution_accuracy"]["correct"])+"/48",
                number(None if metrics["execution_accuracy"]["complete_dataset_mean"] is None else 100*metrics["execution_accuracy"]["complete_dataset_mean"]),
                count(metrics["program_accuracy"]["correct"])+"/48",*(states[s] for s in ("I","W","R","UNKNOWN"))])
            for category,name in CATEGORIES.items():
                sub=panel["by_first_response"][category]
                subgroup_rows.append([group,label,name,sub["denominator"],*(sub["states"][s] for s in ("I","W","R","UNKNOWN")),
                    sub["valid_terminal_submit_count"],sub["costs"]["new_model_calls"]])
            direct=panel["original_submit_candidates"]
            direct_rows.append([group,label,direct["denominator"],direct["native_nonexecutable"],
                direct["native_missing_or_invalid_submission"],direct["executable_wrong"],direct["executable_correct"],direct["unknown"]])
            for old in ("P","L"):
                pair=panel["paired_to_old_original"][old]
                paired_rows.append([group,label,old,pair["new_correct_known_pairs"],pair["lost_correct_known_pairs"],
                    count(pair.get("numerator")),number(None if pair["difference"] is None else 100*pair["difference"]),
                    pair["unknown_pair_count"],pair["program_accuracy"]["new_correct_known_pairs"],pair["program_accuracy"]["lost_correct_known_pairs"]])
    f_l=panels["F"]["L_from_P"]["states"]["R"]
    f_p=panels["F"]["P_from_L"]["states"]["R"]
    k_l=panels["K"]["L_from_P"]["states"]["R"]
    k_p=panels["K"]["P_from_L"]["states"]["R"]
    p_nonterm=sum(panels[g]["P_from_L"]["by_first_response"]["compliant_nonterminal_candidate"]["states"]["R"] for g in ("F","K"))
    parts=["# FinQA V74 最终实验报告：固定交叉历史上的完整条件续跑",
        f"报告日期：{report_date}，时间口径为北京时间。科学执行状态`{execution['closeout']['status']}`，终点评分摘要状态`{final['status']}`。",
        f"本轮已完成固定96题上的192条混合来源轨迹及首次统一native评分，逐字复用192条V73第一回应。实际新增P模型调用{costs['new_model_calls']}次、工具动作{costs['new_tool_calls']}次，工具状态重建{costs['reconstruction_tool_calls']}次；未新增训练、概率测量或外部API调用。",
        f"F组L←hP正确{f_l}/48、P←hL正确{f_p}/48；K组分别{k_l}/48、{k_p}/48。31条第一回应为非终末动作的P←hL条件中，{p_nonterm}条最终正确。UNKNOWN共{final['unknown_native_results']}条；未知不填零、不缩小分母。",
        "这些数值描述指定来源历史上的条件续跑，不能并入L原来的431/883，不能估计总体开发集提升或历史的因果占比。尤其31条需新推理的hL全是初始请求，不是L执行错误程序后的纠错实验。",
        f"完整逐条件结果、原P/L配对迁移和来源SHA见[机器摘要](report_data/{summary_filename})。本报告只读封存产物，没有重新评分或执行工具。",
        "## 1. 固定来源、预算与完整轨迹身份",
        "P为V71固定分布step1192原父点；L为V72低学习率step1490。F从旧P正确、L缺少有效终末提交的题目中固定选48；K固定为旧P/L均正确48题。本轮原样沿用V73名单、分组和第一回应，不重选、不追加H或随机draw。",
        table(["条件","来源历史","已有第一回应","新增推理"],[["L←hP","P原有效提交前的公开历史","V73的L(hP)","0次；未加载L"],["P←hL","L原末次调用前的公开历史","V73的P(hL)","仅非终末分支由P继续"]]),
        "来源turn、receipt、工具事件和身份保持原值，后继来自另一模型的来源被显式记录；Episode.provider仅描述后继行为者。没有把父后续答案、私人参考、尚未发生的工具结果或人工修正封套放入模型输入。",
        "第一回应固定为147个提交候选、31个合法非终末动作、14个无调用。无调用按原合同终止，不追加提醒或第二次机会。每条总模型预算仍为32，包含来源b次调用和复用第一回应；新增上限max(0,32−b−1)。31条非终末的b均为0，精确总上限961，不能把上限当实际用量。2048输出token与24576上下文上限保持，无截断历史。",
        "## 2. 四个固定面板的完整原生结果",
        "I为无有效或不可执行提交，W为可执行但答案错误，R为执行正确；PA另由原生程序等价规则给出。所有主面板分母均48。存在UNKNOWN时完整面板均值为NA，表中正确数仅是已知正确的数量。",
        table(["组","条件","EA正确/分母","EA %","PA正确/分母","I","W","R","UNKNOWN"],main_rows),
        "## 3. 第一回应类型与最终结果",
        table(["组","条件","第一回应类型","分母","I","W","R","UNKNOWN","有效终末提交","新增模型调用"],subgroup_rows),
        "分母为0的预定子组记NA，不将其当作0%准确率。第一回应为非终末动作不是失败；终点正确与否由真实后续交互和首次native评分决定。",
        table(["组","条件","原提交候选数","native不可执行","缺少/无效提交","可执行但错","正确","UNKNOWN"],direct_rows),
        "原生submit_program只记录程序并结束，不执行FinQA程序。本轮保持原行为，未额外插入run_program。上表的程序可执行性和正确性来自全192终点之后的原生离线评分。因此静态动作合法、提交工具返回成功、有效终末提交、程序可执行及答案正确是不同层级。",
        "## 4. 相对旧P/L原轨迹的配对变化",
        "方向固定为旧原轨迹→本轮混合轨迹；差值为混合减旧。旧评分只读复用，未重新评分。F本就以旧P正确、旧L无效为选样条件，F中的正数不能解释为独立总体改善。",
        table(["组","混合条件","旧参照","EA新增正确","EA丢失正确","净正确","差值pp","未知对","PA新增正确","PA丢失正确"],paired_rows),
        "机器摘要保留完整I/W/R/UNKNOWN迁移矩阵。以上配对只用于解释这批条件选样的后果，不给出总体因果效果、跨seed稳定性或训练收益保证。",
        "## 5. 来源上下文结构与解释限制",
        table(["组","历史","来源已调用次数b：题数","已有工具事件","成功run_program","失败run_program","read_source","list_sources"],
            [[r["group"],r["source"],"；".join(k+":"+str(v) for k,v in r["source_b_counts"].items()),r["historical_tool_events"],
              r["successful_run_program"],r["failed_run_program"],r["read_source"],r["list_sources"]] for r in history["rows"]]),
        f"来源历史共{history['total_historical_tool_events']}个已有工具事件。hP/hL实际prompt token完全相同{history['actual_prompt_token_identical_count']}/96题；已执行程序与输出数组逐值相同{history['programs_and_outputs_identical_count']}/96题，空数组相等另有标记，不能自动称为已经做过相同计算。F/K各{history['F_selected_clusters']}/{history['K_selected_clusters']}个来源簇，交集{history['shared_F_K_cluster_count']}，合并{history['union_source_cluster_count']}个独特簇。",
        f"31条非终末条件中，{history['nonterminal_b0_count']}/{history['nonterminal_condition_count']}条来源b=0。它们复用P在L初始请求上的第一动作，随后继续P；即使最终正确，也不能描述为在L执行错误动作或获得错误工具结果之后纠正。其余跨历史条件保留各自实际执行进度，父历史可能已经含关键计算结果，因此不能据此宣称L独立恢复原任务能力。",
        "## 6. 实际成本、资源与退出",
        table(["计数","实际量"],[["复用V73第一回应",costs["reused_first_responses"]],["真正新增P模型调用",costs["new_model_calls"]],
            ["本轮首次工具动作",costs["new_tool_calls"]],["其中：复用第一回应的工具动作",costs["reused_first_response_tool_calls"]],
            ["历史/持久工具状态重建",costs["reconstruction_tool_calls"]],["来源模型调用只读继承",costs["historical_model_calls_in_prefix"]],
            ["全路径模型调用（来源＋复用＋新增）",costs["total_path_model_calls_including_prefix_and_reused"]],
            ["达到32轮预算",costs["budget_exhausted"]],["上下文额度终止",costs["context_exceeded"]],
            ["首次native逻辑评分",192],["新增第一回应/NLL/反传/optimizer/outer/class/VJP/API",0]]),
        "复用第一回应的工具动作已经包含在新工具总数中，不能再次相加。重建调用为恢复真实工具状态的成本，不冒充模型新选择的动作；来源及复用模型调用不冒充本轮新推理。",
    ]
    worker=execution["worker"];res=worker["resources"]
    parts.extend([table(["执行项","实际证据"],[["唯一GPU worker",f"GPU{worker['launch']['gpu_index']}；attempt {worker['accepted']['attempt']}；waitpid=0"],
        ["worker派发/真实退出",timestamp(worker["launch"]["started_epoch"])+" / "+timestamp(worker["actual_exit"]["observed_epoch"])],
        ["科学收口",timestamp(execution["closeout"]["finished_epoch"])],
        ["GPU allocated历史峰GiB",number(res["peak_allocated_bytes"]/1024**3,3)],["worker RSS历史峰GiB",number(res["peak_rss_bytes"]/1024**3,3)],
        ["最小边界free GiB",number(res["minimum_boundary_free_bytes"]/1024**3,3)],["最小有效可用RAM GiB",number(res["minimum_host_available_bytes"]/1024**3,3)],
        ["资源验收",str(res["all_gates_passed"])],["最终CPU及controller", "两者实际waitpid=0；CPU未初始化CUDA"],
        ["监督器", "COMPLETE自收口并关闭恢复；无自身waitpid码，不补造"]]),
        f"总worker尝试数为{len(execution['closeout']['actual_attempts'])}；实际记录均保留在机器摘要。worker的forward计数字段明确是当前attempt口径，不能在存在恢复时称为全实验累计。模型加载计入GPU历史峰，阶段间不重置。",
        "## 7. 有限结论与后续边界",
        f"本轮把单步候选实际推进到终点：L在父历史上的F、K正确数分别为{f_l}/48、{k_l}/48，P在L历史上的F、K正确数分别为{f_p}/48、{k_p}/48；第一非终末分支最终正确{p_nonterm}/31。应同时检查K的保留损失和直接候选的实际程序结果，不能只报告F的正确续跑。",
        "正确的混合后继是指定条件下的行为见证。它不证明历史是唯一根因、所有合法动作都可恢复、L已重新获得独立开发集能力或这些见证用于训练一定有效；31条初始hL续跑的解释还受上述起始阶段事实限制。旧L成绩仍是431/883。",
        "本轮完成即止，不自动扩大探针、原样重训、继续修补1490或恢复Full。若后续修订训练材料，应在训练任务及训练来源内另行收集模型实际历史，由冻结教师真实续跑并验证；这96道开发题及本次结果不能直接进入训练后再在同一面板报告收益。改变材料或学习规则后Full需要重新估计对应Contribution，不能沿用旧C。",
        "## 8. 来源与报告操作",
        f"科学根：`{data['execution_root']}`。协议ID：`{data['protocol_id']}`；冻结科学源提交：`{data['source_commit']}`；最终科学摘要ID：`{final['id']}`。",
        f"报告提取器只读取{data['read_policy']['source_JSON_count']}份必要封存JSON，各文件仅读一次并保存字节SHA与记录ID。先验证worker、最终CPU和controller实际exit0及资源接受，再读取最终评分。未打开原始Episode、模型/工具逐次返回、Tensor或私人参考，未新评分、模型计算或执行工具，也未改写历史记录。报告派生摘要ID：`{data['id']}`。",
        "原始模型与完整返回保留在本机；Git中的报告、机器摘要及源码不是全部实验产物的远端备份。"])
    return "\n\n".join(parts)+"\n"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=DEFAULT_ROOT)
    parser.add_argument("--summary",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    require(not args.summary.exists() and not args.report.exists(),"derived output exists; never silently replace")
    value=extract(args.root)
    rendered=render_report(value,summary_filename=args.summary.name)
    args.summary.parent.mkdir(parents=True,exist_ok=True);args.report.parent.mkdir(parents=True,exist_ok=True)
    args.summary.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+"\n")
    args.report.write_text(rendered)
    print(json.dumps(dict(id=value["id"],source_JSON_count=value["read_policy"]["source_JSON_count"],
        report=str(args.report),summary=str(args.summary)),ensure_ascii=False))


if __name__ == "__main__":
    main()
