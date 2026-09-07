"""Render the fixed qualified QA export as concise Chinese reasoning summaries."""

import gzip
import hashlib
import json
import re
from decimal import Decimal
from html import escape
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


OP_NAMES = {
    "lookup": "读取资料",
    "registered_compare": "比较两个指标",
    "growth": "计算增长率",
    "aggregate": "计算平均值",
    "difference": "计算金额变化",
    "ratio": "计算利润收入比",
    "signed_percentage_point_gap": "计算增长率差",
    "absolute_percentage_point_gap": "取差值的绝对值",
    "relation_sum": "由分项重建总额",
    "share_ratio": "计算收入比例",
    "scale_percent": "转换为百分比",
}
GOALS = {
    "lookup": "取得可供引用和后续计算使用的数据结论。",
    "registered_compare": "确定哪个指标更高，以及两者相差多少。",
    "growth": "已有前后两期金额，还需要以较早一期为基数算出相对变化。",
    "aggregate": "已有三个季度的收入，还需要得到覆盖全部季度的平均值。",
    "difference": "已有前后两期收入，还需要得到带方向的金额变化。",
    "ratio": "已有营业利润和营业收入，还需要得到利润相对于收入的比值。",
    "signed_percentage_point_gap": "两个增长率已经分别得到，还需要将它们合并为百分点差。",
    "absolute_percentage_point_gap": "已经得到有正负号的差值，题目还要求差距的绝对幅度。",
    "relation_sum": "取得一个由分项计算得到的经营收入总额，作为可选择的整体依据。",
    "share_ratio": "已有货运收入，需要选定整体的依据并得到部分占整体的比例。",
    "scale_percent": "已得到收入比例，还需要将它转换为百分比。",
}
METHODS = {
    "lookup": "选择对应公司、期间和指标的资料，直接提取金额并保留来源。",
    "registered_compare": "两项资料属于同一季度且单位相同，可以比较金额并计算差值。",
    "growth": "采用（后一期−前一期）÷前一期×100，保留前后期顺序。",
    "aggregate": "题目要求使用全部三个季度，选择等权算术平均。",
    "difference": "题目要求金额变化，选择后一期减前一期，保留增减方向。",
    "ratio": "选择营业利润作分子、营业收入作分母，得到无量纲比值。",
    "signed_percentage_point_gap": "两个输入都是百分比增长率，可以相减得到百分点差。",
    "absolute_percentage_point_gap": "题目只关心差距幅度，选择对已接受的差值取绝对值。",
    "relation_sum": "资料明确说明货运收入与其他收入组成经营收入总额，因此选择按这一关系求和。",
    "share_ratio": "部分占整体的比例等于部分除以整体；本次分子为货运收入。",
    "scale_percent": "前一步结果是比值，乘以100才是题目要求的百分比。",
}
FIELD_NAMES = {
    "currency": "币种",
    "unit": "单位",
    "value": "数值",
    "metric": "指标名称",
    "definition": "指标定义",
    "lineage": "依赖清单",
    "period": "期间",
    "scope": "范围",
    "subject": "主体",
}


def tracking(record, evidence):
    """Bind operation -> observation -> explicit accept -> actual later consumers."""
    events = record["session"]["events"]
    operations = [e for e in events if e.get("execution")]
    step_by_submission = {e["submission"]["id"]: i for i, e in enumerate(operations, 1)}
    claims = {}
    for claim in record["session"]["claims"]:
        producer = next(
            e for e in operations if e["submission"]["id"] == claim["action_submission_id"]
        )
        accept = next(e for e in events if e.get("claim", {}).get("id") == claim["id"])
        assert producer["receipt"]["admitted"] and producer["execution"]["success"]
        assert accept["receipt"]["admitted"] and accept["parsed"]["disposition"] == "accept"
        assert accept["parsed"]["observation_id"] == producer["observation"]["id"]
        assert accept["claim"]["observation_id"] == producer["observation"]["id"]
        assert accept["sequence"] > producer["sequence"]
        assert accept["parsed"]["proposed_claim"] == producer["observation"]["proposition"]
        claims[claim["id"]] = {
            "claim": claim,
            "producer": producer,
            "accept": accept,
            "step": step_by_submission[producer["submission"]["id"]],
        }
    assert len(claims) == len(operations)

    def ref_name(ref):
        if ref in evidence:
            e = evidence[ref]
            if "value" not in e and "payload" not in e:
                return "“货运收入＋其他收入＝经营收入总额”的组成关系"
            return evidence_label(e)
        c = claims[ref]
        return f"步骤{c['step']}接受的{OP_NAMES[c['producer']['execution']['operation']]}结果"

    def consumers(claim_id):
        c = claims[claim_id]
        result = []
        for event in operations:
            used = [
                i
                for i in event["parsed"]["inputs"]
                if i["kind"] == "claim" and i["ref_id"] == claim_id
            ]
            if used:
                assert event["sequence"] > c["accept"]["sequence"]
                step = step_by_submission[event["submission"]["id"]]
                roles = {
                    "denominator": "作为分母",
                    "numerator": "作为分子",
                    "ratio": "作为待转换比例",
                }
                detail = "、".join(roles.get(i["role"], "作为计算输入") for i in used)
                result.append(
                    f"步骤{step}（T{event['sequence'] + 1}）{detail}，"
                    f"用于{OP_NAMES[event['execution']['operation']]}。"
                )
        final = record["session"]["final"]
        if final["answer"]["answer_claim_id"] == claim_id:
            event = next(e for e in events if e["submission"]["id"] == final["submission_id"])
            assert event["sequence"] > c["accept"]["sequence"]
            result.append(f"最终有效答案（T{event['sequence'] + 1}）直接引用此结论。")
        return "".join(result) or (
            "已被接受并保留在本会话状态中，但没有被后继运算或最终答案直接引用。"
            "不能据此认定它构成了最终计算路线，也不将“未使用”写成“撤销”。"
        )

    return operations, claims, ref_name, consumers


def output_text(event, evidence):
    out = event["execution"]["proposition"]["output"]
    op = event["execution"]["operation"]
    if op == "registered_compare":
        return f"{evidence_label(evidence[out['higher_ref']])}更高，相差{out['difference']}百万美元"
    value = brief(number(out))
    approximate = "约" if value != number(out) else ""
    if op in {"growth", "scale_percent"}:
        unit = "%"
    elif op in {"signed_percentage_point_gap", "absolute_percentage_point_gap"}:
        unit = "个百分点"
    elif op in {"ratio", "share_ratio"}:
        unit = "（比值）"
    else:
        unit = "百万美元"
    return f"{approximate}{value}{unit}"


class ReviewGraph:
    """Small Mermaid graph with explicit node and edge validation."""

    def __init__(self):
        self.nodes = {}
        self.edges = []

    def node(self, key, label, style):
        assert key not in self.nodes, key
        self.nodes[key] = (label, style)

    def edge(self, source, target, label="", dotted=False):
        edge = (source, target, label, dotted)
        if edge not in self.edges:
            self.edges.append(edge)

    @staticmethod
    def label(text):
        # Keep decimal strings, source locators, and HTML entities intact.
        lines = []
        for logical_line in text.split("\n"):
            current = ""
            for token in re.findall(r"[A-Za-z0-9_./:%+-]+|.", logical_line):
                if current and len(current) + len(token) > 26:
                    lines.append(current)
                    current = ""
                current += token
            if current:
                lines.append(current)
        return "<br/>".join(escape(line, quote=True) for line in lines)

    def markdown(self):
        lines = ["```mermaid", "flowchart TD"]
        for key, (label, style) in self.nodes.items():
            lines.append(f'    {key}["{self.label(label)}"]:::{style}')
        for source, target, label, dotted in self.edges:
            assert source in self.nodes and target in self.nodes, (source, target)
            arrow = "-.->" if dotted else "-->"
            suffix = f'|"{self.label(label)}"|' if label else ""
            lines.append(f"    {source} {arrow}{suffix} {target}")
        lines += [
            "    classDef evidence fill:#eff6ff,stroke:#2563eb,color:#172554",
            "    classDef judgment fill:#f5f3ff,stroke:#7c3aed,color:#2e1065",
            "    classDef operation fill:#ecfeff,stroke:#0891b2,color:#164e63",
            "    classDef observation fill:#fffbeb,stroke:#d97706,color:#78350f",
            "    classDef accepted fill:#f0fdf4,stroke:#16a34a,color:#14532d",
            "    classDef rejected fill:#fff1f2,stroke:#e11d48,color:#881337",
            "    classDef unused fill:#f3f4f6,stroke:#6b7280,color:#374151",
            "```",
        ]
        return "\n".join(lines)


ROLES = {
    "numerator": "分子",
    "denominator": "分母",
    "ratio": "待转换比例",
    "member": "组成分项",
    "relation": "组成关系",
    "earlier_value": "较早一期金额",
    "later_value": "较晚一期金额",
    "revenue_earlier_value": "较早一期收入",
    "revenue_later_value": "较晚一期收入",
    "income_earlier_value": "较早一期营业利润",
    "income_later_value": "较晚一期营业利润",
    "numerator_value": "分子",
    "denominator_value": "分母",
    "income_growth": "营业利润增长率",
    "revenue_growth": "收入增长率",
}


def reasoning_graph(record, evidence):
    operations, claims, _, _ = tracking(record, evidence)
    graph = ReviewGraph()
    graph.node("Q", "明确问题\n" + QUESTIONS[record["context"]["task_type"]], "judgment")
    evidence_nodes = {}
    for n, (ref, item) in enumerate(evidence.items(), 1):
        key = f"E{n}"
        evidence_nodes[ref] = key
        source = item.get("source_record_id", item.get("provenance", {}).get("source_record_id"))
        if "value" in item or "payload" in item:
            label = evidence_label(item) + "\n" + number(item) + "百万美元"
        else:
            label = "组成关系\n货运收入＋其他收入＝经营收入总额"
        graph.node(key, label + "\n来源：" + str(source), "evidence")
    claim_nodes = {ref: f"C{c['step']}" for ref, c in claims.items()}
    references = {**evidence_nodes, **claim_nodes}
    consumed = set()
    for n, event in enumerate(operations, 1):
        op = event["execution"]["operation"]
        claim_id = next(ref for ref, c in claims.items() if c["producer"] is event)
        accept = claims[claim_id]["accept"]
        method = METHODS[op]
        goal = GOALS[op]
        if op == "lookup":
            goal = "取得可引用的" + evidence_label(evidence[event["parsed"]["inputs"][0]["ref_id"]])
        if op == "share_ratio":
            denominator = next(i for i in event["parsed"]["inputs"] if i["role"] == "denominator")
            method += (
                "本次选择已接受的重建总额作分母。"
                if denominator["kind"] == "claim"
                else "本次选择直接披露总额作分母。"
            )
        graph.node(f"J{n}", f"步骤{n}：依据与判断\n目标：{goal}\n选择：{method}", "judgment")
        graph.node(
            f"A{n}",
            f"T{event['sequence'] + 1} 实际操作\n" + operation_text(event, evidence),
            "operation",
        )
        graph.node(f"O{n}", "观察结果（尚未接受）\n" + output_text(event, evidence), "observation")
        graph.node(
            f"C{n}",
            f"T{accept['sequence'] + 1} 明确接受\n"
            + output_text(event, evidence)
            + "\n成为可引用结论",
            "accepted",
        )
        graph.edge(f"J{n}", f"A{n}", "选择并执行")
        graph.edge(f"A{n}", f"O{n}", "返回")
        graph.edge(f"O{n}", f"C{n}", "模型另行提交接受")
        inputs = event["parsed"]["inputs"]
        input_refs = {i["ref_id"] for i in inputs}
        for item in inputs:
            ref = item["ref_id"]
            if item["kind"] == "claim":
                assert claims[ref]["accept"]["sequence"] < event["sequence"]
                consumed.add(ref)
            graph.edge(references[ref], f"J{n}", "采用：" + ROLES.get(item["role"], "计算输入"))
        basis = event["parsed"]["decision"]["basis"]
        for field in ("evidence_refs", "claim_refs"):
            for ref in basis[field]:
                if ref not in input_refs:
                    graph.edge(references[ref], f"J{n}", "公开依据", dotted=True)
        if not any(i["kind"] == "claim" for i in inputs):
            graph.edge("Q", f"J{n}", "任务目标", dotted=True)
    final = record["session"]["final"]
    final_event = next(
        e for e in record["session"]["events"] if e["submission"]["id"] == final["submission_id"]
    )
    answer_claim = final["answer"]["answer_claim_id"]
    consumed.add(answer_claim)
    final_operation = (
        "百分比保留六位小数；引用实际计算依据。"
        if record["context"]["task_type"] == "source_explicit_part_whole_share"
        else "按题目要求整理结果；引用实际依据。"
    )
    graph.node(
        "F",
        f"T{final_event['sequence'] + 1} 给出有依据的答案\n"
        + final_operation
        + "\n"
        + answer_text(record, evidence).replace("**", "")
        + "\n答案及引用校验通过，会话结束",
        "accepted",
    )
    graph.edge(claim_nodes[answer_claim], "F", "使用已接受的最终结论")
    for ref in final["answer"]["citations"]:
        graph.edge(references[ref], "F", "最终引用", dotted=True)
    for ref, claim in claims.items():
        if ref not in consumed:
            key = f"U{claim['step']}"
            graph.node(key, "已接受但未用于后继运算或有效答案\n保留在状态中，不等于撤销", "unused")
            graph.edge(claim_nodes[ref], key, "实际使用检查", dotted=True)
    return graph


def correction_graph(record, evidence):
    changes = correction_records(record, evidence)
    if not changes:
        return None
    graph = ReviewGraph()
    events = {e["sequence"]: e for e in record["session"]["events"]}
    proposals = {row["sequence"]: row["proposal"] for row in changes}
    for row in changes:
        sequence = row["sequence"]
        for seq in [sequence, sequence + 1]:
            key = f"T{seq + 1}"
            if key in graph.nodes:
                continue
            event = events[seq]
            if seq in proposals:
                label = proposals[seq]
            elif event["parsed"]["kind"] == "action":
                label = (
                    OP_NAMES[event["parsed"]["operation"]] + "实际执行\n后续观察与接受见上方主图"
                )
            else:
                label = "最终答案通过校验\n" + answer_text(record, evidence).replace("**", "")
            graph.node(
                key,
                f"T{seq + 1} 提交\n" + label,
                ("accepted" if event["parsed"]["kind"] == "final" else "operation")
                if event["receipt"]["admitted"]
                else "rejected",
            )
        graph.node(f"R{sequence + 1}", row["feedback"], "rejected")
        graph.node(f"M{sequence + 1}", "随后调整\n" + row["change"], "judgment")
        graph.edge(f"T{sequence + 1}", f"R{sequence + 1}", "收到反馈")
        graph.edge(f"R{sequence + 1}", f"M{sequence + 1}", "随后实际变化")
        graph.edge(f"M{sequence + 1}", f"T{sequence + 2}", "下一次提交")
    return graph


def action_problem(event, ref_name):
    p = event["parsed"]
    selected = next(
        a
        for a in event["request"]["available_actions"]
        if a["id"] == p["decision"]["selected_action_id"]
    )
    actual, expected = p["decision"], selected
    differences = []
    if actual["obligation_id"] != expected["obligation_id"]:
        differences.append("目标写成“取得总额”，但所选动作要求“计算比例”")
    for key in ("evidence_refs", "claim_refs"):
        a, b = actual["basis"][key], expected["basis"][key]
        if a == b:
            continue
        if set(a) == set(b):
            differences.append("依据清单顺序与所选公开候选不一致（数值分子、分母未因此互换）")
        else:
            missing, extra = set(b) - set(a), set(a) - set(b)
            if missing:
                differences.append("依据漏列" + "、".join(ref_name(x) for x in sorted(missing)))
            if extra:
                differences.append("依据多列" + "、".join(ref_name(x) for x in sorted(extra)))
    assert differences
    return "；".join(differences)


def result_difference(p, valid, ref_name):
    a, b = p["result"], valid["result"]
    parts = []
    if a.get("value") != b.get("value"):
        parts.append("百分比仍提交长小数，未采用最终要求的六位小数")
    extra = set(a) - set(b)
    if extra:
        parts.append(
            "结果附加了" + "、".join(FIELD_NAMES.get(k, k) for k in sorted(extra)) + "字段"
        )
    extra_refs, missing_refs = (
        set(p["citations"]) - set(valid["citations"]),
        set(valid["citations"]) - set(p["citations"]),
    )
    if extra_refs:
        parts.append("引用多列" + "、".join(ref_name(x) for x in sorted(extra_refs)))
    if missing_refs:
        parts.append("引用漏列" + "、".join(ref_name(x) for x in sorted(missing_refs)))
    assert parts
    return "；".join(parts)


def final_change(old, new, ref_name):
    changes = []
    a, b = old["result"], new["result"]
    for difference, verb in [(set(a) - set(b), "删除"), (set(b) - set(a), "添加")]:
        if difference:
            changes.append(
                verb + "结果中的" + "、".join(FIELD_NAMES.get(k, k) for k in sorted(difference))
            )
    if a.get("value") != b.get("value"):
        changes.append(
            "将数值改为六位小数"
            if len(str(b.get("value"))) < len(str(a.get("value")))
            else "数值又改回长小数"
        )
    for difference, verb in [
        (set(old["citations"]) - set(new["citations"]), "移除引用"),
        (set(new["citations"]) - set(old["citations"]), "加入引用"),
    ]:
        if difference:
            changes.append(verb + "：" + "、".join(ref_name(x) for x in sorted(difference)))
    if old.get("answer_claim_id") != new.get("answer_claim_id"):
        changes.append("调整最终所引用的中间结论")
    # Record changed metadata values too, without printing machine payloads.
    modified = [k for k in set(a) & set(b) if k != "value" and a[k] != b[k]]
    if modified:
        changes.append("修改结果中的" + "、".join(FIELD_NAMES.get(k, k) for k in sorted(modified)))
    return "；".join(changes) or "结果与引用未发生变化，再次提交"


def correction_records(record, evidence):
    events = record["session"]["events"]
    rejected = [e for e in events if not e["receipt"]["admitted"]]
    if not rejected:
        return []
    operations, _, ref_name, _ = tracking(record, evidence)
    valid = record["session"]["final"]["answer"]
    rows = []
    for event in rejected:
        p = event["parsed"]
        next_event = next(e for e in events if e["sequence"] == event["sequence"] + 1)
        next_p = next_event["parsed"]
        if p["kind"] == "action":
            proposal = (
                "拟用披露总额直接计算货运收入占比"
                if p["operation"] == "share_ratio"
                else "拟用已接受的两期收入计算收入增长率"
            )
            proposal += "；本次没有执行运算。"
            feedback = "动作未准入：" + action_problem(event, ref_name) + "。"
            if next_p["operation"] != p["operation"]:
                assert next_event.get("execution")
                change = (
                    "改为" + OP_NAMES[next_p["operation"]] + "，实际执行；这不是直接除法已成功。"
                )
            elif next_event["receipt"]["admitted"]:
                change = "补齐公开候选要求的来源依据后，原计划的增长率运算才实际执行。"
            else:
                change = "继续提交直接使用披露总额的除法；目标／依据校验仍未通过，没有执行。"
        else:
            assert p["kind"] == next_p["kind"] == "final"
            assert not any(e["sequence"] > event["sequence"] for e in operations)
            proposal = result_difference(p, valid, ref_name) + "。"
            feedback = "最终答案未通过校验；在线没有返回详细原因。"
            change = final_change(p, next_p, ref_name) + "。"
            change += (
                "本次通过，成为最终答案。"
                if next_event["receipt"]["admitted"]
                else "该次仍未通过。"
            )
            change += "没有重新计算。"
        rows.append(
            {
                "sequence": event["sequence"],
                "proposal": proposal,
                "feedback": feedback,
                "change": change,
            }
        )
    return rows


def render():
    source = DATA / "trajectories.qualified.jsonl.gz"
    raw = source.read_bytes()
    manifest = json.loads((DATA / "manifest.json").read_text())
    assert hashlib.sha256(raw).hexdigest() == manifest["files"][source.name]["sha256"]
    rows = [json.loads(line) for line in gzip.decompress(raw).splitlines()]
    index = [
        "# 合格 QA 轨迹人工审阅\n",
        "18条轨迹均按“明确问题 → 选择依据与方法 → 执行操作 → "
        "判断并接受结果 → 使用结果继续推导 → 给出有依据的答案”整理。"
        "每条轨迹用Mermaid依赖图展示目标、判断、操作、观察、明确接受和实际使用；另用调整图展示未通过的提案与后续修改。文字是基于公开决策、操作和引用关系的说明性转述，不是模型逐字原话。\n",
        "阅读时可重点比较B01/B02的多步增长率计算，以及Share轨迹中“直接使用披露总额”"
        "与“使用本会话求和结果”两种实际分母来源。\n",
        "| 轨迹 | 问题 | 实际运算次数 |",
        "| --- | --- | ---: |",
    ]
    execution_count = 0
    graph_count = 0
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
            "## 依据、推导与结果使用图\n",
            "紫色节点说明目标与判断；蓝色节点表示资料或操作；黄色节点表示尚未接受的观察；"
            "绿色节点表示已接受结论或有效答案；灰色节点标记已接受但未使用的结果。\n",
            "实线连接实际数据使用与操作—观察—接受；虚线表示任务目标、公开依据、引用或使用检查。"
            "图展示依赖结构，不表示并行执行；T编号保留真实提交顺序。"
            "判断文字为说明性转述，不是模型逐字原话。中间约数仅用于展示，实际计算保留完整精度。\n",
        ]
        lines.append(reasoning_graph(r, lookup).markdown())
        graph_count += 1
        lines += ["\n## 提案与答案调整图\n"]
        adjustments = correction_graph(r, lookup)
        if adjustments:
            graph_count += 1
            lines += [
                "红色节点表示未通过的提案及反馈，紫色节点说明随后实际修改。"
                "动作未通过时没有执行；答案字段与引用的修改不算重新计算。"
                "详细字段差异来自事后核对，不是在线反馈逐字原文。"
                "图中分开的片段发生于不同阶段，T编号与主图一致。\n",
                adjustments.markdown(),
            ]
        else:
            lines.append("本会话没有被拒提案或答案调整。\n")
        lines += ["\n[原始数据与字段说明](../README.md)\n"]
        text = "\n".join(lines).rstrip() + "\n"
        assert "```json" not in text and "finance_qa_vnext_" not in text
        (OUT / f"{label}.md").write_text(text, encoding="utf-8")
        index.append(f"| [{label}]({label}.md) | {question} | {len(operations)} |")
        execution_count += len(operations)
    index += [
        "\n计数中的运算包括读取数据和数值计算；接受中间结果、修改提交和提交最终答案不单独算作运算。\n",
        "所有58次操作分别核对观察结果、后续明确接受及消费顺序；全部28次未准入提交分别说明随后调整。已接受但未使用的结果明确标注。"
        "原始输入、精确数值与完整纠正历史保存在[数据包](../README.md)。\n",
        "重建命令：`python trusted_data_synthesis/scripts/render_qa_trajectory_review.py`。\n",
    ]
    (OUT / "README.md").write_text("\n".join(index).rstrip() + "\n", encoding="utf-8")
    print(
        f"Rendered {len(rows)} reviews / {graph_count} Mermaid graphs; "
        f"verified {execution_count} operations."
    )


if __name__ == "__main__":
    render()
