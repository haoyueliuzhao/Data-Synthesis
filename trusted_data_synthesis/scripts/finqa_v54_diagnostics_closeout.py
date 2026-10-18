"""Append recovered historical coverage and the bounded 18-case reading notes.

The first automatic diagnostic is immutable. This separate supplement resolves
one archive lookup gap and records actual qualitative reading; no rescoring.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

import finqa_v54_diagnostics as d

OBSERVATIONS = {
    ("seed137/static", "finqa/L/2009/page_84.pdf-1"):
        "一次run_program成功返回0.6062，第二次输出说明该结果后实际EOS；没有提交封套。工具成功不等于已提交原生答案。",
    ("seed137/static", "finqa/BLK/2015/page_124.pdf-4"):
        "首调用出现submit_program JSON，但在</tool_call>之前实际EOS；JSON中的程序字符串是const_50。本分析不补封套或检验修补后结果。",
    ("seed137/c_only", "finqa/AWK/2018/page_146.pdf-1"):
        "run_program返回20.0后，第二次输出用普通Program: submit_program(...)文字表示提交意图，没有工具封套，并实际EOS。",
    ("seed137/c_only", "finqa/SNA/2013/page_83.pdf-3"):
        "三次read_source后，第四次输出包含合法read_source封套，其后继续生成角色标记、伪工具消息与重复标记；原parser首先在封套后非空白处拒绝整段。",
    ("seed137/full", "finqa/JPM/2018/page_90.pdf-4"):
        "首调用只有R/U/Q说明及普通Program文字，未形成工具封套，随后实际EOS；本分析没有核对其金融数值正确性。",
    ("seed137/full", "finqa/FIS/2012/page_48.pdf-4"):
        "首调用多次重复讨论const_9.0，最后给出submit_program JSON而缺少关闭封套，并实际EOS。不能由补标签推断程序可执行或答案正确。",
    ("seed251/static", "finqa/LMT/2014/page_77.pdf-2"):
        "首调用文字提出322.4减326.5的计算，却没有任何工具封套，直接实际EOS。",
    ("seed251/static", "finqa/JPM/2009/page_175.pdf-4"):
        "七次read_source后，第八次合法封套后附角色标记及重复裸JSON；原parser因封套后非空白拒绝，不是没有可解析前缀。",
    ("seed251/c_only", "finqa/ZBH/2007/page_67.pdf-1"):
        "run_program成功返回-0.88636后，第二次仅文字解释结果，没有提交封套，随后实际EOS。",
    ("seed251/c_only", "finqa/CME/2017/page_40.pdf-2"):
        "两次run_program均得到实际ToolInputError；第三次合法封套后模型自行生成伪成功工具消息和提交封套，原parser首先因夹杂内容拒绝整段。伪工具成功不是实际工具事件。",
    ("seed251/full", "finqa/BKNG/2016/page_33.pdf-3"):
        "首调用反复重复执行/提交意图与R/U/Q文字，始终没有封套，达到2048 token长度上限；延长输出能否修复未知。",
    ("seed251/full", "finqa/BLK/2015/page_124.pdf-4"):
        "首调用submit_program JSON结束后实际EOS，缺少</tool_call>；程序内容为const_50，不对修补后的执行或正确性作推断。",
    ("seed389/static", "finqa/ZBH/2009/page_58.pdf-1"):
        "首调用以普通Program: divide(1127.6,2719.3)文字给出意图，没有工具封套，随后实际EOS。",
    ("seed389/static", "finqa/JPM/2009/page_175.pdf-4"):
        "两次真实read_source后，第三次合法封套后继续生成角色标记、伪工具响应和另一个工具调用；原parser在第一封套后的非空白处拒绝。",
    ("seed389/c_only", "finqa/AON/2007/page_188.pdf-1"):
        "run_program返回0.32075后，第二次输出普通Program: submit_program(...)文字而非封套，随后实际EOS。",
    ("seed389/c_only", "finqa/HOLX/2006/page_71.pdf-1"):
        "首个<tool_call>后直接出现大量角色标记而不是JSON，随后还有其他标签和对象；最先触发严格JSON异常，后续片段不被挽救。",
    ("seed389/full", "finqa/CDNS/2015/page_30.pdf-1"):
        "首调用反复重复计算说明和提交意图，没有工具封套，直到2048 token上限；不是已验证的可由增加长度修复的案例。",
    ("seed389/full", "finqa/JPM/2018/page_90.pdf-3"):
        "submit_program封套被原parser接受并真实提交，但program字符串是average interest-earning assets 2018自然语言；原评分为invalid。该例不是parser格式拒绝。",
}


def run(output=d.OUTPUT):
    from trusted_synthesis.finance_research.storage import load_public_snapshot

    output = Path(output).resolve()
    original, original_source = d.read(output / "summary/record.json")
    outers, outer_source = d.read(output / "outer_signals/record.json")
    row = next(row for row in outers["rows"]
               if (row["seed"], row["arm"], row["step"]) == (389,"c_only",894))
    feedback_root = output.parent / ("production_resume_01/recovery_04/contexts/seed389/"
        "c_only/step0894_outer/feedback_resume_view/"
        "dc03ecaa04ac96ea215e281ab5de848ddbf93ebb202fd32c541d637824c6c972")
    reward, reward_source = d.read(feedback_root / "native_rewards/record.json")
    run_record, run_source = d.read(feedback_root / "draw0/run.json")
    d.require(reward["cohort_seal_sha256"] == row["cohort_seal_sha256"]
              and run_record["provider"]["point_id"] == row["point_id"]
              and len(reward["rewards"]) == len(reward["scores"]) == 700,
              "recovered historical coverage differs from original saved point")
    _, tasks, lineages = load_public_snapshot(run_record["snapshot"])
    sources = {task.task_id: lineage.source_group for task,lineage in zip(tasks,lineages,strict=True)}
    successful = [score["task_id"] for value,score in zip(reward["rewards"],reward["scores"],strict=True)
                  if value == 1]
    d.require(len(successful) == row["successful_feedback_sessions"], "reward count changed")
    groups = Counter(sources[task] for task in successful)
    supplement = d.publish(output / "coverage_supplement", dict(
        schema="v54_historical_feedback_coverage_supplement.v1", prior_analysis=outer_source,
        coordinate="seed389/c_only/step0894", original_lookup_status=row["success_coverage"],
        reason="complete V43 resumed feedback was stored in feedback_resume_view, outside initial training_replication-only index",
        reward_source=reward_source, roster_source=run_source,
        point_id=row["point_id"], cohort_seal_sha256=row["cohort_seal_sha256"],
        successful_sessions=len(successful), unique_successful_tasks=len(set(successful)),
        unique_successful_source_groups=len(groups), source_group_session_counts=dict(groups),
        successful_sessions_by_draw=[sum(reward["rewards"][start:start+350]) for start in (0,350)],
        unique_successful_tasks_by_draw=[len({score["task_id"] for value,score in
            zip(reward["rewards"][start:start+350],reward["scores"][start:start+350],strict=True)
            if value == 1}) for start in (0,350)],
        all_24_outer_success_coverage_now_available=True, new_provider_or_scoring_calls=0,
    ))
    packet, packet_source = d.read(output / "invalid/reading_packet/record.json")
    examples, counts = [], Counter()
    for example in packet["examples"]:
        if counts[example["coordinate"]] >= 2:
            continue
        counts[example["coordinate"]] += 1
        key = (example["coordinate"], example["task_key"])
        d.require(key in OBSERVATIONS, "qualitative note does not match deterministic selection")
        examples.append(dict(coordinate=key[0], task_key=key[1], category=example["category"],
                             original_episode=example["original_episode"],
                             observation=OBSERVATIONS[key], correctness_rescored=False))
    d.require(len(examples) == len(OBSERVATIONS) == 18 and set(counts.values()) == {2},
              "manual reading must remain exactly two per model")
    reading = d.publish(output / "manual_reading", dict(
        schema="v54_bounded_manual_reading_18.v1", source_packet=packet_source,
        selection_rule="first two per model from the already sealed alphabetical-category/digest round-robin selection",
        candidate_packet_count=90, actual_cases_read=18, cases_per_model=dict(counts),
        full_saved_response_turns_and_tool_events_read=True, examples=examples,
        population_prevalence_not_inferred_from_purposeful_sample=True,
        observations_not_counterfactual_repairs=True,
        old_scores_changed=False, new_generation_or_scoring=0,
    ))
    return d.publish(output / "closeout", dict(
        schema="v54_bounded_historical_diagnostics_closeout.v1", initial_summary=original_source,
        initial_summary_id=original["id"], coverage_supplement_id=supplement["id"],
        manual_reading_id=reading["id"], all_24_outer_success_coverage_available=True,
        manual_reading_completed=True, manual_cases=18, automatic_invalid_cases=2979,
        original_scientific_records_unchanged=True,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        remaining_optional_gaps=[
            "No directly saved per-draw C/gJ in committed outer records; no additional backward or checkpoint deconvolution performed.",
            "No reason/tool/final coefficient attribution in available outer/package summaries; deriving it requires original supervision spans.",
            "No per-segment NLL/gradient attribution; coefficient mass is not actual loss/gradient.",
        ],
        new_GPU_backward_or_sampling_or_scoring_calls=0,
    ))


if __name__ == "__main__":
    result = run()
    print(result["id"])
