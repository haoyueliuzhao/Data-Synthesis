"""Render the fixed qualified QA export as concise Chinese reasoning summaries."""

import gzip
import hashlib
import json
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


def table_row(label, text):
    return f"| **{label}** | {text.replace('|', '&#124;').replace(chr(10), '<br>')} |"


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


def reasoning_steps(record, evidence):
    operations, claims, ref_name, consumers = tracking(record, evidence)
    lines = []
    for n, event in enumerate(operations, 1):
        op = event["execution"]["operation"]
        claim_id = next(cid for cid, c in claims.items() if c["producer"] is event)
        accept = claims[claim_id]["accept"]
        basis = event["parsed"]["decision"]["basis"]
        references = [
            ref_name(ref) for key in ("evidence_refs", "claim_refs") for ref in basis[key]
        ]
        judgment = "已有依据：" + "；".join(references) + "。" + METHODS[op]
        if op == "share_ratio":
            denominator = next(i for i in event["parsed"]["inputs"] if i["role"] == "denominator")
            judgment += (
                "分母选择本会话求和并明确接受的总额。"
                if denominator["kind"] == "claim"
                else "分母选择资料直接披露的总额，未选用本会话先前的求和结论。"
            )
        lines += [
            f"\n### 步骤{n}：{OP_NAMES[op]}"
            f"（操作T{event['sequence'] + 1}，接受T{accept['sequence'] + 1}）\n",
            "| 部分 | 人工阅读说明 |",
            "| --- | --- |",
            table_row(
                "当前目标",
                (
                    "取得可引用的"
                    + evidence_label(evidence[event["parsed"]["inputs"][0]["ref_id"]])
                    + "数值；当前还缺少经操作读取并接受的数据结论。"
                    if op == "lookup"
                    else GOALS[op]
                ),
            ),
            table_row("主要判断", judgment),
            table_row("实际操作", operation_text(event, evidence)),
            table_row(
                "结果与接受",
                f"T{event['sequence'] + 1}操作返回{output_text(event, evidence)}；"
                f"此时只是观察结果。T{accept['sequence'] + 1}模型另行提交明确接受，"
                "将该结果确立为可引用的中间结论。",
            ),
            table_row("后续使用", consumers(claim_id)),
        ]
    final = record["session"]["final"]
    final_event = next(
        e for e in record["session"]["events"] if e["submission"]["id"] == final["submission_id"]
    )
    answer_claim = claims[final["answer"]["answer_claim_id"]]
    cites = "；".join(ref_name(ref) for ref in final["answer"]["citations"])
    lines += [
        f"\n### 最后一步：给出有依据的答案（T{final_event['sequence'] + 1}）\n",
        "| 部分 | 人工阅读说明 |",
        "| --- | --- |",
        table_row("当前目标", "把已接受的最终计算结果整理为题目要求的答案，并给出实际支持依据。"),
        table_row("主要判断", f"使用步骤{answer_claim['step']}已经接受的结论；实际引用：{cites}。"),
        table_row(
            "实际操作",
            (
                "将已接受的百分比保留六位小数，整理实际计算依赖的引用。"
                if record["context"]["task_type"] == "source_explicit_part_whole_share"
                else "按题目要求整理结果与来源引用，不新增一次数值计算。"
            ),
        ),
        table_row(
            "结果与接受", answer_text(record, evidence) + "本次最终提交通过既有答案及引用校验。"
        ),
        table_row("后续使用", "作为本会话最终答案，会话结束。"),
    ]
    return lines


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


def corrections(record, evidence):
    events = record["session"]["events"]
    rejected = [e for e in events if not e["receipt"]["admitted"]]
    if not rejected:
        return ["本会话未发生被拒提案；各次结果接受及后续使用见上表。\n"]
    operations, _, ref_name, _ = tracking(record, evidence)
    valid = record["session"]["final"]["answer"]
    lines = [
        "下表按真实提交顺序记录调整。动作反馈含公开字段诊断；答案反馈只给出“最终答案未通过校验”。"
        "具体字段差异来自事后对实际提交与公开候选或有效答案的比较，不是反馈逐字原文，也不推测模型内部动机。\n",
        "| 未通过的提交 | 原先提出什么／实际差异 | 收到的反馈 | 随后修改及结果 |",
        "| --- | --- | --- | --- |",
    ]
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
        values = [
            f"T{event['sequence'] + 1}",
            proposal,
            feedback,
            f"T{next_event['sequence'] + 1}：{change}",
        ]
        lines.append("| " + " | ".join(v.replace("|", "&#124;") for v in values) + " |")
    if record["context"]["task_type"] == "source_explicit_part_whole_share":
        ratio = next(e for e in operations if e["execution"]["operation"] == "share_ratio")
        denominator = next(i for i in ratio["parsed"]["inputs"] if i["role"] == "denominator")
        used = (
            "实际执行并接受分项求和，后续真正用该求和结论作分母，采用重建路线。"
            if denominator["kind"] == "claim"
            else "虽然实际执行并接受过分项求和，后续除法仍使用披露总额作分母，采用直接披露路线。"
        )
        lines.append("\n**最后实际采用：**" + used + "\n")
    return lines


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
        "每一步分别说明当前目标、主要判断、实际操作、结果与接受、后续使用。文字是基于公开决策、操作和引用关系的说明性转述，不是模型逐字原话。\n",
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
            "以下是对实际公开决策与依赖关系的说明性转述，不是模型逐字原话。T编号对应原始提交顺序。工具返回结果和模型接受结果分开记录；“后续使用”只记实际引用。中间长小数仅在展示时简化，后续计算使用完整精度，最终答案保留原精度。\n",
        ]
        lines.extend(reasoning_steps(r, lookup))
        lines += ["\n## 发生过的调整\n"]
        lines.extend(corrections(r, lookup))
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
    print(f"Rendered {len(rows)} concise reviews; verified {execution_count} accepted operations.")


if __name__ == "__main__":
    render()
