"""Render every exported qualified QA session into Markdown for human review."""

import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/qa_vnext_revised_trajectories"
OUT = DATA / "review"
NAMES = {"action": "Action / 动作", "update": "Update / 接受或拒绝观察", "final": "Final / 答案"}


def js(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def cell(value):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text.replace("|", "&#124;").replace("\n", "<br>")


def block(value):
    return "\n```json\n" + js(value) + "\n```\n"


def details(title, value):
    return "\n<details>\n<summary>" + title + "</summary>\n" + block(value) + "\n</details>\n"


def render():
    source = DATA / "trajectories.qualified.jsonl.gz"
    raw = source.read_bytes()
    manifest = json.loads((DATA / "manifest.json").read_text())
    assert hashlib.sha256(raw).hexdigest() == manifest["files"][source.name]["sha256"]
    records = [json.loads(line) for line in gzip.decompress(raw).splitlines()]
    OUT.mkdir(exist_ok=True)
    index = [
        "# 合格 QA 轨迹人工审阅索引\n",
        "本目录展示上次抽取的全部18条合格轨迹：八任务面板15条、Share支持探索3条。"
        "每条轨迹单独成文，包含公开题目、最终答案、证据、逐次提交与反馈。\n",
        "合格会话内的未准入提交和纠正历史全部保留。步骤编号T1起算，对应原sequence+1。"
        "展开区域展示解析后的完整模型提交，JSON经过排版；原始响应字节见数据包及来源工件。"
        "此处展示公开决策与执行轨迹，资格沿用冻结结果，未新增模型调用或人工审阅结论。\n",
        "两个实验及Share的N/E提示条件分别标识，不将这些会话视作独立任务或合并统计总体。\n",
        "| 轨迹 | 任务类型 | 提交数 | 准入 | 未准入 | 题目 |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    total = admitted_total = 0
    for r in records:
        assert r["package"]["positive_eligible"] and r["package"]["complete"]
        context, session = r["context"], r["session"]
        task = context.get("public_task", context.get("task"))
        question = task.get("instruction", task.get("question"))
        assert question and session["final"]["qa_validation"]["qa_valid"]
        events = session["events"]
        assert [e["sequence"] for e in events] == list(range(len(events)))
        admitted = sum(e["receipt"]["admitted"] for e in events)
        total += len(events)
        admitted_total += admitted
        label = r["cohort"] + "_" + r["label"]
        index.append(
            f"| [{label}]({label}.md) | {cell(context['task_type'])} | {len(events)} | "
            f"{admitted} | {len(events) - admitted} | {cell(question)} |"
        )
        lines = [
            f"# {label}：合格 QA 轨迹\n",
            "[返回审阅索引](README.md)\n",
            "## 任务与结果\n",
            question + "\n",
            f"实验：`{r['cohort']}`；会话：`{r['label']}`；"
            f"提示分层：`{r['outcome'].get('profile', '统一面板条件')}`。\n",
            f"冻结资格：success；完整提交{len(events)}次，其中准入{admitted}次、"
            f"未准入{len(events) - admitted}次。\n",
            "最终答案（原始result字段，保持数值精度和单位）：\n",
            block(session["final"]["answer"]["result"]),
            details("展开最终答案、引用及既有验证结果", session["final"]),
            "## 执行顺序总览\n",
            "| 步骤 | 提交类型 | 操作或处置 | 准入结果 |",
            "| --- | --- | --- | --- |",
        ]
        for e in events:
            p = e.get("parsed") or {}
            status = (
                "准入" if e["receipt"]["admitted"] else "未准入：" + str(e["receipt"]["error_code"])
            )
            lines.append(
                f"| [T{e['sequence'] + 1}](#t{e['sequence'] + 1}) | "
                f"{cell(p.get('kind', 'parse_failure'))} | "
                f"{cell(p.get('operation', p.get('disposition', '提交答案')))} | {cell(status)} |"
            )
        lines += ["\n## 公开证据\n", "以下为同一任务的实际证据对象，包含数值、定义及来源定位。\n"]
        evidence = context["evidence"]
        items = evidence.items() if isinstance(evidence, dict) else enumerate(evidence, 1)
        for name, item in items:
            title = (
                str(name)
                + "："
                + str(item.get("metric", item.get("predicate", item.get("kind", "证据"))))
            )
            lines.append(details(title, item))
        lines += [
            details("展开公开任务与数值条件", {"task": task, "numeric": context.get("numeric")}),
            "\n## 逐次提交与反馈\n",
            "动作产生Observation；只有后续准入的Update才建立Claim。"
            "未准入的动作不会被写成已执行运算；每次纠正仍独立展示。\n",
        ]
        for e in events:
            turn = e["sequence"] + 1
            p = e.get("parsed") or {}
            kind = p.get("kind", "parse_failure")
            lines += [
                f'\n<a id="t{turn}"></a>\n',
                f"### T{turn} — {NAMES.get(kind, kind)}\n",
                (
                    "准入。\n"
                    if e["receipt"]["admitted"]
                    else f"**未准入**：`{e['receipt']['error_code']}`。\n"
                ),
            ]
            if kind == "action":
                lines += [f"模型请求操作：`{p.get('operation')}`。\n", block(p.get("inputs", []))]
                execution = e.get("execution")
                if execution:
                    lines += [
                        "实际解析输入：\n",
                        block(execution["resolved_inputs"]),
                        "实际执行输出：\n",
                        block(execution["proposition"]["output"]),
                    ]
                else:
                    lines.append("本次没有执行结果。\n")
            elif kind == "update":
                lines += [
                    f"模型处置：`{p.get('disposition')}`；后续子目标：`{p.get('next_subgoal')}`。\n"
                ]
                if e.get("claim"):
                    claim = e["claim"]
                    lines += [f"实际建立Claim：`{claim['id']}`。\n", block(claim["proposition"])]
                else:
                    lines.append("本次没有建立新的Claim。\n")
            elif kind == "final":
                lines += ["本次提交的答案（是否被接受以上方回执为准）：\n", block(p.get("result"))]
            lines += [
                "提交后实际反馈：\n",
                block(e["post_state"]["last_feedback"]),
                details("展开完整模型提交（parsed，保留全部字段）", e.get("parsed")),
                details(
                    "展开本次回执、观察及状态引用",
                    {
                        "sequence": e["sequence"],
                        "request_id": e["request"]["id"],
                        "submission": e["submission"],
                        "receipt": e["receipt"],
                        "observation": e.get("observation"),
                        "post_state_id": e["post_state"]["id"],
                    },
                ),
            ]
        lines += [
            "\n## 来源与审阅记录\n",
            f"来源实验：`{r['source_run']}`。\n",
            f"Session ID：`{session['id']}`。\n",
            f"Qualification ID：`{r['package']['qualification_id']}`。\n",
            "本页为审阅视图；完整请求、候选与状态在[合格轨迹数据包](../trajectories.qualified.jsonl.gz)中。\n",
            "人工审阅结论：待填写。\n\n审阅备注：待填写。\n",
        ]
        text = "\n".join(lines).rstrip() + "\n"
        assert text.count('<a id="t') == len(events)
        assert all(js(e.get("parsed")) in text for e in events)
        (OUT / f"{label}.md").write_text(text, encoding="utf-8")
    index += [
        f"\n合计展示{len(records)}条合格轨迹、{total}次提交，"
        f"其中{admitted_total}次准入、{total - admitted_total}次未准入。\n",
        "## 生成与验证\n",
        "源文件：`../trajectories.qualified.jsonl.gz`。SHA-256："
        f"`{hashlib.sha256(raw).hexdigest()}`。\n",
        "生成时校验源文件哈希、每条完整合格包及最终QA验证标记、连续事件序号，"
        "并确认每次提交均有独立步骤且完整parsed对象出现在对应页面。"
        "这验证审阅视图覆盖性，不重新判定模型或答案质量。\n",
        "仓库根目录重建命令：\n\n```bash\n"
        "python trusted_data_synthesis/scripts/render_qa_trajectory_review.py\n```\n",
    ]
    (OUT / "README.md").write_text("\n".join(index).rstrip() + "\n", encoding="utf-8")
    print(f"Rendered {len(records)} sessions, {total} submissions, {admitted_total} admitted.")


if __name__ == "__main__":
    render()
