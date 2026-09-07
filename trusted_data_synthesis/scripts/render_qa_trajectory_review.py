"""Render the fixed qualified QA export as concise Chinese reasoning summaries."""

import gzip
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/qa_vnext_revised_trajectories"
OUT = DATA / "review"
METRICS = {
    "revenue": "营业收入",
    "operating_income": "营业利润",
    "total_freight_revenues": "货运收入",
    "other_revenues": "其他收入",
    "total_operating_revenues": "营业总收入",
}
QUESTIONS = {
    "fact_retrieval": ("Huntington Ingalls Industries 在2014年第一季度的营业收入是多少？"),
    "registered_cross_metric_comparison": (
        "Huntington Ingalls Industries 在2014年第四季度的营业收入和营业利润，哪项更高？相差多少？"
    ),
    "temporal_growth": (
        "Huntington Ingalls Industries 的营业收入从2014年第二季度到第三季度变化了百分之多少？"
    ),
    "temporal_average": (
        "Huntington Ingalls Industries 在2014年第二至第四季度的平均营业收入是多少？"
    ),
    "temporal_absolute_change": (
        "Huntington Ingalls Industries 的营业收入从2014年第一季度到第二季度增加或减少了多少金额？"
    ),
    "registered_ratio": ("CDW 在2016财年的营业利润与营业收入之比是多少？"),
    "derived_growth_absolute_spread": (
        "CDW 从2015财年到2016财年的营业收入增长率和营业利润增长率，相差多少个百分点（取绝对值）？"
    ),
    "source_explicit_part_whole_share": (
        "Union Pacific 及其子公司在2015财年的货运收入占营业总收入的百分比是多少？保留六位小数。"
    ),
}


def number(value):
    if isinstance(value, dict):
        return number(value.get("payload", value.get("value")))
    return str(value)


def brief(value):
    """Approximate display only; exact values remain in the source and final answer."""
    value = str(value)
    return format(Decimal(value), ".6f").rstrip("0").rstrip(".") if len(value) > 18 else value


def evidence_label(e):
    period = e.get("period", e.get("temporal_context", {}).get("label", ""))
    metric = e.get("metric", e.get("predicate"))
    return f"{period} {METRICS.get(metric, metric)}".strip()


def operation_text(event, evidence):
    x = event["execution"]
    op = x["operation"]
    inputs = x["resolved_inputs"]
    values = [number(i["value"]) for i in inputs]
    out = x["proposition"]["output"]
    result = brief(number(out)) if "value" in out or "payload" in out else None
    if op == "lookup":
        label = evidence_label(evidence[inputs[0]["ref_id"]])
        return f"读取{label}：{values[0]}百万美元。"
    if op == "registered_compare":
        higher = evidence_label(evidence[out["higher_ref"]])
        return (
            f"比较同一季度的两个指标：{values[0]} − {values[1]} = "
            f"{out['difference']}百万美元，{higher}更高。"
        )
    if op == "growth":
        return (
            f"计算增长率，以前一期为基数：（{values[1]} − {values[0]}）"
            f"÷ {values[0]} × 100 ≈ {result}%。"
        )
    if op == "aggregate":
        assert out["method"] == "mean"
        return f"将三个季度等权平均：（{' + '.join(values)}）÷ {len(values)} ≈ {result}百万美元。"
    if op == "difference":
        return f"用后一期减前一期：{values[1]} − {values[0]} = {result}百万美元，表示收入增加。"
    if op == "ratio":
        return f"营业利润除以营业收入：{values[0]} ÷ {values[1]} ≈ {result}。这是比值。"
    if op == "signed_percentage_point_gap":
        return (
            f"按本次操作顺序，营业收入增长率减去营业利润增长率："
            f"{brief(values[1])}% − {brief(values[0])}% ≈ {result}个百分点。"
        )
    if op == "absolute_percentage_point_gap":
        return f"对差值取绝对值：|{brief(values[0])}| ≈ {result}个百分点，得到题目要求的幅度。"
    if op == "relation_sum":
        members = [number(i["value"]) for i in inputs if i["value"].get("role") == "member"]
        return (
            f"依据来源中的组成关系，将货运收入和其他收入相加：{' + '.join(members)}"
            f" = {result}百万美元，得到一个重建的营业总收入。"
        )
    if op == "share_ratio":
        denominator = next(i for i in event["parsed"]["inputs"] if i["role"] == "denominator")
        support = (
            "本会话前一步求和并确认的总收入"
            if denominator["kind"] == "claim"
            else "来源表直接披露的总收入；先前求和结果未被这次除法使用"
        )
        return f"货运收入除以营业总收入：{values[0]} ÷ {values[1]} ≈ {result}。分母使用{support}。"
    if op == "scale_percent":
        return f"把前一步比值乘以100，转换为百分比，约为{result}%。"
    raise ValueError(f"Unsupported operation: {op}")


def answer_text(record, evidence):
    out = record["session"]["final"]["answer"]["result"]
    kind = record["context"]["task_type"]
    if "higher_ref" in out:
        label = evidence_label(evidence[out["higher_ref"]])
        return f"{label}更高，相差 **{out['difference']}百万美元**。"
    value = number(out)
    if kind in {"fact_retrieval", "temporal_average", "temporal_absolute_change"}:
        unit = "百万美元"
    elif kind in {"temporal_growth", "source_explicit_part_whole_share"}:
        unit = "%"
    elif kind == "derived_growth_absolute_spread":
        unit = "个百分点"
    else:
        unit = "（比值，无量纲）"
    return f"**{value}{unit}**。"


def corrections(events):
    rejected = [e for e in events if not e["receipt"]["admitted"]]
    if not rejected:
        return "本会话未发生提交被拒绝的情况。"
    groups = Counter(e["receipt"]["error_code"] for e in rejected)
    texts = []
    for code, count in groups.items():
        if code == "admission.public_judgment":
            texts.append(
                f"{count}次动作请求因所写的依据或目标与所选动作不一致而被拒绝；修正后才执行。"
            )
        elif code == "admission.final_qa":
            texts.append(
                f"{count}次最终答案未通过输出或引用校验；后续提交调整后通过。"
                "这些是答案提交的修订，没有增加新的财务计算。"
            )
        else:
            raise ValueError(f"Unexplained correction: {code}")
    return "".join(texts)


def render():
    source = DATA / "trajectories.qualified.jsonl.gz"
    raw = source.read_bytes()
    manifest = json.loads((DATA / "manifest.json").read_text())
    assert hashlib.sha256(raw).hexdigest() == manifest["files"][source.name]["sha256"]
    rows = [json.loads(line) for line in gzip.decompress(raw).splitlines()]
    index = [
        "# 合格 QA 轨迹人工审阅\n",
        "18条轨迹均按“问题 → 关键证据 → 主要推理与操作 → 最终答案 → 纠正情况”整理。"
        "说明依据实际公开执行记录编写；中间长小数以约数展示，最终答案保留原精度。\n",
        "阅读时可重点比较B01/B02的多步增长率计算，以及Share轨迹中“直接使用披露总额”"
        "与“使用本会话求和结果”两种实际分母来源。\n",
        "| 轨迹 | 问题 | 实际运算次数 |",
        "| --- | --- | ---: |",
    ]
    execution_count = 0
    for r in rows:
        assert r["package"]["positive_eligible"] and r["package"]["complete"]
        assert r["session"]["final"]["qa_validation"]["qa_valid"]
        events = r["session"]["events"]
        operations = [e for e in events if e.get("execution")]
        evidence = r["context"]["evidence"]
        items = list(evidence.values()) if isinstance(evidence, dict) else evidence
        lookup = {e.get("evidence_id", e.get("id")): e for e in items}
        label = r["cohort"] + "_" + r["label"]
        question = QUESTIONS[r["context"]["task_type"]]
        cohort = "八任务面板" if r["cohort"] == "task_panel" else "Share支持探索"
        profile = {"N": "中性提示", "E": "软引导提示"}.get(r["outcome"].get("profile"))
        lines = [
            f"# {r['label']}：{question}\n",
            "[返回轨迹索引](README.md)\n",
            f"来源：{cohort}" + (f"，{profile}" if profile else "") + "。\n",
            "## 问题\n",
            question + "\n",
            "## 关键证据\n",
            "| 数据项 | 数值 | 来源记录 |",
            "| --- | ---: | --- |",
        ]
        for e in items:
            if "value" not in e and "payload" not in e:
                continue
            source_id = e.get("source_record_id", e.get("provenance", {}).get("source_record_id"))
            lines.append(f"| {evidence_label(e)} | {number(e)}百万美元 | {source_id} |")
        lines += [
            "\n## 主要推理与操作\n",
            "以下按实际执行顺序整理；结果经后续提交确认后用于下一步。长小数仅在展示时简化，实际后续计算使用完整精度。\n",
        ]
        for n, event in enumerate(operations, 1):
            # Bind every narrated operation to its actual accepted observation/claim.
            assert event["receipt"]["admitted"] and event["execution"]["success"]
            assert any(
                c["action_submission_id"] == event["submission"]["id"]
                for c in r["session"]["claims"]
            )
            lines.append(f"{n}. {operation_text(event, lookup)}")
        if r["context"]["task_type"] == "source_explicit_part_whole_share":
            lines.append(
                f"{len(operations) + 1}. 按题目要求，将百分比保留六位小数，"
                "提交实际计算所用证据的引用。"
            )
        else:
            lines.append(
                f"{len(operations) + 1}. 使用上述结果形成最终答案，并提交来源引用；最终校验通过。"
            )
        lines += [
            "\n## 最终答案\n",
            answer_text(r, lookup) + "\n",
            "## 纠正情况\n",
            corrections(events) + "\n",
            "[原始数据与字段说明](../README.md)\n",
        ]
        text = "\n".join(lines).rstrip() + "\n"
        assert "```json" not in text and "finance_qa_vnext_" not in text
        (OUT / f"{label}.md").write_text(text, encoding="utf-8")
        index.append(f"| [{label}]({label}.md) | {question} | {len(operations)} |")
        execution_count += len(operations)
    index += [
        "\n计数中的运算包括读取数据和数值计算；接受中间结果、修改提交和提交最终答案不单独算作运算。\n",
        "各页说明对应各自会话的实际路径，未将重复执行合并为同一个会话。"
        "原始输入、精确数值与完整纠正历史保存在[数据包](../README.md)。\n",
        "重建命令：`python trusted_data_synthesis/scripts/render_qa_trajectory_review.py`。\n",
    ]
    (OUT / "README.md").write_text("\n".join(index).rstrip() + "\n", encoding="utf-8")
    print(f"Rendered {len(rows)} concise reviews; verified {execution_count} accepted operations.")


if __name__ == "__main__":
    render()
