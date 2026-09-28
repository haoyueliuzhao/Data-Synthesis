"""Report a completed conditional Probe inventory, never inspect in-flight quality.

Reads only protocol.json, generation_seal/record.json and
inventory_complete/record.json. No episode, private reference, API or model access;
no qualification rerun, native rescoring, Student encoding or training.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def bound(value, field="id", prefix=""):
    require(
        value.get(field)
        == prefix + digest({key: row for key, row in value.items() if key != field}),
        f"content identity mismatch: {field}",
    )


def count_verdicts(rows):
    counts = {purpose: Counter() for purpose in ("train", "sealed_diagnostic")}
    for row in rows:
        require(row["purpose"] in counts, "unknown slot purpose")
        verdict = row["decision"]["verdict"]
        require(verdict in {"CompletePass", "invalid", "unknown"}, "unknown qualification verdict")
        counts[row["purpose"]].update([verdict])
    return {
        purpose: {verdict: values[verdict] for verdict in ("CompletePass", "invalid", "unknown")}
        for purpose, values in counts.items()
    }


def analyze(run_root):
    root = Path(run_root).resolve()
    # Check both barriers before opening ANY qualification-bearing artifact.
    require(
        (root / "generation_seal/record.json").is_file()
        and (root / "inventory_complete/record.json").is_file(),
        "generation and inventory must both be sealed complete before this report",
    )
    sources = []

    def read(relative):
        raw = (root / relative).read_bytes()
        sources.append(dict(path=relative, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw)))
        return json.loads(raw)

    plan = read("protocol.json")
    seal = read("generation_seal/record.json")
    bound(plan)
    bound(seal)
    registration = plan["inventory"]
    bound(registration, "inventory_id", "finqa_probe_inventory:")
    scope = plan["conditional_scope"]
    require(isinstance(scope, dict), "this report requires the explicitly conditional study")
    bound(scope, "scope_id", "finqa_conditional_scope:")
    require(
        registration["conditional_scope"] == scope
        and registration["scope_id"] == seal["scope_id"] == scope["scope_id"],
        "protocol/inventory/generation scope binding differs",
    )
    original, active, coverage = (
        scope["original_task_ids"],
        scope["task_ids"],
        scope["coverage_rows"],
    )
    require(
        len(original) == len(set(original)) == len(coverage) == 1000,
        "original 1,000-task denominator or exclusion ledger changed",
    )
    require(
        [row["task_id"] for row in coverage] == original
        and [row["task_id"] for row in coverage if row["included"]] == active,
        "conditional roster is not the preserved original-order scope",
    )
    require(
        active == plan["task_ids"] == registration["task_ids"]
        and scope["scoped_task_count"] == plan["active_task_denominator"] == len(active),
        "active task denominator differs",
    )
    require(
        scope["selection_uses_probe_outcomes"] is False
        and plan["original_1000_training_admitted"] is False
        and plan["automatic_training_authorized"] is False,
        "conditional scope or training-authorization boundary changed",
    )
    slots = registration["slots"]
    require(
        len(slots)
        == len(active) * 8
        == registration["registered_slot_denominator"]
        == plan["active_slot_denominator"]
        == seal["denominator"]
        == len(seal["slots"]),
        "fixed eight-slot denominator changed",
    )
    require(
        seal["protocol_id"] == plan["id"]
        and seal["complete"] is True
        and seal["all_API_requests_settled"] is True,
        "generation seal is incomplete or foreign",
    )
    completed = {row["slot"]["slot_id"]: row for row in seal["slots"]}
    require(
        len(completed) == len(slots) and set(completed) == {row["slot_id"] for row in slots},
        "sealed slot roster changed",
    )
    for slot in slots:
        item = completed[slot["slot_id"]]
        require(
            item["slot"] == slot
            and item["status"] == "COMPLETE"
            and item["all_provider_calls_settled"] is True,
            "unsettled or substituted generation slot",
        )
    budget = seal["budget"]
    require(
        budget["run_id"] == plan["id"]
        and not budget["halt"]
        and budget["unknown_requests"]
        == budget["pending_requests"]
        == budget["held_microcny"]
        == 0,
        "unknown/unsettled cost ledger cannot become a completed report",
    )

    # All generation/scope checks precede this only qualification-bearing read.
    frozen = read("inventory_complete/record.json")
    bound(frozen, "frozen_inventory_id", "finqa_frozen_probe_support:")
    require(
        frozen["inventory_id"] == registration["inventory_id"]
        and frozen["conditional_scope"] == scope
        and frozen["scope_id"] == scope["scope_id"],
        "qualified inventory belongs to another scope",
    )
    require(
        frozen["original_candidate_count"] == 1000
        and frozen["original_1000_admitted"] is False
        and frozen["training_authorized"] is False
        and frozen["sealed_packages_in_training"] == 0,
        "original-population or training admission was incorrectly promoted",
    )
    results = frozen["slot_results"]
    require(
        frozen["candidate_task_count"] == len(active)
        and frozen["slot_denominator"] == len(results) == len(slots)
        and frozen["train_slot_denominator"] == len(active) * 6
        and frozen["sealed_slot_denominator"] == len(active) * 2,
        "qualified inventory denominator changed",
    )
    require(
        [row["slot_id"] for row in results] == [row["slot_id"] for row in slots],
        "qualification slot order or roster changed",
    )
    for row, slot in zip(results, slots, strict=True):
        bound(row, "slot_result_id", "finqa_probe_slot_result:")
        require(
            row["inventory_id"] == registration["inventory_id"]
            and all(row[key] == value for key, value in slot.items())
            and row["episode_sha256"]
            == completed[slot["slot_id"]]["episode_sha256"]
            == row["decision"]["episode_sha256"]
            and row["decision"]["task_id"] == slot["task_id"],
            "foreign qualification result",
        )
        require(
            row["qualification_rule_id"] == registration["qualification_rule_id"]
            and row["mapper_rule_id"] == registration["mapper_rule_id"]
            and row["all_provider_calls_settled"] is True
            and row["episode_complete"] is True,
            "qualification rule drift or incomplete slot",
        )
    verdicts = count_verdicts(results)
    for purpose, counts in verdicts.items():
        require(
            Counter(frozen["verdict_counts"][purpose]) == Counter(counts),
            "stored qualification totals differ from fixed slot results",
        )
    retained = [
        row["slot_id"]
        for row in results
        if row["purpose"] == "train" and row["decision"]["verdict"] == "CompletePass"
    ]
    require(
        retained == frozen["retained_train_slot_ids"]
        and [row["slot_id"] for row in results if row["purpose"] == "sealed_diagnostic"]
        == frozen["sealed_diagnostic_slot_ids"],
        "selective retention or sealed/train mixing",
    )
    missing = [task for task in active if not frozen["train_state_counts"][task]]
    require(
        missing == frozen["missing_train_task_ids"]
        and len(missing) == frozen["missing_train_task_count"]
        and frozen["admitted"] == (not missing),
        "missing-support/admission mismatch",
    )
    if not frozen["admitted"]:
        require(frozen["material_registration"] is None, "missing task was silently dropped")
    calls = sum(row["actual_model_calls"] for row in results)
    require(
        calls
        == sum(row["actual_model_calls"] for row in seal["slots"])
        == budget["requests_dispatched"]
        == budget["requests_reserved"],
        "actual request accounting differs from the sealed tariff ledger",
    )
    require(
        budget["actual_prompt_tokens_settled"]
        == budget["actual_cache_hit_tokens_settled"] + budget["actual_cache_miss_tokens_settled"],
        "cache usage totals differ",
    )
    source_code_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    summary = dict(
        schema="finqa_conditional_probe_descriptive_report.v1",
        run_root=str(root),
        protocol_id=plan["id"],
        execution_source_commit=plan["source_commit"],
        scope_id=scope["scope_id"],
        inventory_id=registration["inventory_id"],
        frozen_inventory_id=frozen["frozen_inventory_id"],
        original_task_denominator=1000,
        active_task_denominator=len(active),
        excluded_original_tasks=1000 - len(active),
        conditional_scope_source=str(root / "protocol.json"),
        complete_inventory_source=str(root / "inventory_complete/record.json"),
        original_exclusion_reason_counts=dict(
            Counter(row["reason"] for row in coverage if not row["included"])
        ),
        original_1000_admitted=False,
        conditional_qualified_support_admitted=frozen["admitted"],
        admission_scope=frozen["admission_scope"],
        training_authorized=False,
        student_encoding_admission_separate=True,
        slot_denominator=len(slots),
        train_slot_denominator=len(active) * 6,
        sealed_slot_denominator=len(active) * 2,
        verdict_counts=verdicts,
        retained_qualified_train_packages=len(retained),
        sealed_packages_in_training=0,
        missing_train_task_count=len(missing),
        missing_train_task_ids=missing,
        single_state_tasks=len(frozen["single_state_static_task_ids"]),
        multi_state_tasks=len(frozen["multi_state_task_ids"]),
        single_state_task_ids=frozen["single_state_static_task_ids"],
        multi_state_task_ids=frozen["multi_state_task_ids"],
        nontrivial_pi_support_present=frozen["nontrivial_pi_support_present"],
        nonpass_reason_counts={
            purpose: {
                verdict: dict(
                    Counter(
                        row["decision"]["reason"]
                        for row in results
                        if row["purpose"] == purpose and row["decision"]["verdict"] == verdict
                    )
                )
                for verdict in ("invalid", "unknown")
            }
            for purpose in verdicts
        },
        API_model=plan["collection_policy"]["model"],
        actual_API_requests=calls,
        spending_peak_upper_bound_CNY=format(
            Decimal(budget["settled_tariff_microcny"]) / Decimal(1000000), ".6f"
        ),
        spending_is_provider_invoice=False,
        sealed_budget=budget,
        actual_prompt_tokens=budget["actual_prompt_tokens_settled"],
        actual_cache_hit_tokens=budget["actual_cache_hit_tokens_settled"],
        actual_cache_miss_tokens=budget["actual_cache_miss_tokens_settled"],
        actual_completion_tokens=budget["actual_completion_tokens_settled"],
        generation_sealed_at=seal["at"],
        qualification_rule_id=registration["qualification_rule_id"],
        mapper_rule_id=registration["mapper_rule_id"],
        source_evidence=sources,
        report_script_sha256=source_code_sha256,
        new_model_calls=0,
        new_private_reference_reads=0,
        new_qualification_or_native_scoring=False,
        training_value_claimed=False,
        qualification_meaning="limited frozen qualification, not universal financial correctness",
    )
    summary["id"] = digest(summary)
    return summary


def markdown(summary):
    s = summary
    lines = [
        "# FinQA 条件性 Probe 材料库存报告",
        "",
        f"协议：`{s['protocol_id']}`；执行提交：`{s['execution_source_commit']}`。",
        "",
        f"原始候选 **1000 题**；预先登记静态支持子总体 **{s['active_task_denominator']} 题**；"
        f"另 **{s['excluded_original_tasks']} 题**保留排除记录，不冒称原总体已准入。",
        "",
        f"固定采集 **{s['slot_denominator']} 会话**，其中 train **{s['train_slot_denominator']}**、"
        f"sealed 表示／支持诊断 **{s['sealed_slot_denominator']}**。所有槽完成封存后才统一判定。",
        "",
        "| 用途 | CompletePass（有限资格） | invalid | unknown |",
        "|---|---:|---:|---:|",
    ]
    for purpose in ("train", "sealed_diagnostic"):
        row = s["verdict_counts"][purpose]
        lines.append(f"| {purpose} | {row['CompletePass']} | {row['invalid']} | {row['unknown']} |")
    admitted = (
        "成立（仅条件子总体的原包支持）"
        if s["conditional_qualified_support_admitted"]
        else "未成立"
    )
    lines += [
        "",
        f"条件子总体材料支持准入：**{admitted}**。合格 train 原包全部保留："
        f"**{s['retained_qualified_train_packages']} 包**；sealed 进入训练 **0 包**。",
        "",
        f"缺合格 train 支持：**{s['missing_train_task_count']} 题**；单状态："
        f"**{s['single_state_tasks']} 题**；多状态：**{s['multi_state_tasks']} 题**。"
        "缺支持任务不再删除、不补采；单状态不提供 π 重权自由度。",
        "",
        "## 调用与费用",
        "",
        f"模型固定 `{s['API_model']}`，实际 API 请求 **{s['actual_API_requests']}**。"
        "按真实 usage 和最高峰价逐请求向上取整得到的费用上界为 "
        f"**¥{s['spending_peak_upper_bound_CNY']}**，"
        "不是供应商实际账单。",
        "",
        f"输入 Token：**{s['actual_prompt_tokens']}**（缓存命中 {s['actual_cache_hit_tokens']}，"
        f"未命中 {s['actual_cache_miss_tokens']}）；"
        f"输出 Token：**{s['actual_completion_tokens']}**。",
        "",
        f"生成封存时间（原记录）：`{s['generation_sealed_at']}`。",
        "",
        "## 解释边界",
        "",
        "本报告仅聚合已冻结的资格、状态及结算记录，不重新评分、生成或读取私有答案。"
        "unknown 不等同于答案错误；CompletePass 仅代表已登记有限规则范围内的资格。",
        "",
        "原 1000 题未获整体准入；Student 编码准入与正式训练仍是独立后续步骤。"
        "本轮不授权训练，不声称 SFT、Delayed-C 或 VTDO 收益。缺支持名册、原因计数和文件哈希"
        "见 summary.json；完整排除记录与逐题状态不重复复制，保留在绑定的原库存中。",
        "",
        f"[查看原库存]({s['complete_inventory_source']})；"
        f"[查看原范围登记]({s['conditional_scope_source']})。",
    ]
    lines += [
        "",
        "## 非通过资格的原因计数",
        "",
        "以下是有限判定器的判定原因，不是金融错误率。未获语义验证的附加自然语言说明"
        "反映当前判定覆盖边界，不能直接断言这些说明或最终金融答案错误。"
        "这类 unknown 是先触发的阻断原因，不表示后续工具／Final 已被完整核验，"
        "也不能反向解释为这些 unknown 其实都正确。"
        "原规则、原判定保持，不通过修改规则重判来增加材料。",
        "",
        "| 用途 | 判定 | 原因 | 会话数 |",
        "|---|---|---|---:|",
    ]
    for purpose, verdicts in s["nonpass_reason_counts"].items():
        for verdict, counts in verdicts.items():
            for reason, count in sorted(counts.items(), key=lambda row: (-row[1], row[0])):
                safe_reason = reason.replace("|", "\\|").replace("\n", " ")
                lines.append(f"| {purpose} | {verdict} | {safe_reason} | {count} |")
    return "\n".join(lines) + "\n"


def write_once(path, data):
    if path.exists():
        require(path.read_bytes() == data, f"refuse to overwrite different report bytes: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report-md", type=Path)
    args = parser.parse_args()
    summary = analyze(args.run_root)
    write_once(
        args.output / "summary.json",
        (
            json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            + "\n"
        ).encode(),
    )
    report_path = args.report_md or args.output / "report.md"
    write_once(report_path, markdown(summary).encode())
    print(
        json.dumps(
            {
                "id": summary["id"],
                "active_tasks": summary["active_task_denominator"],
                "slots": summary["slot_denominator"],
                "conditional_qualified_support_admitted": summary[
                    "conditional_qualified_support_admitted"
                ],
                "training_authorized": False,
                "report_md": str(report_path),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
