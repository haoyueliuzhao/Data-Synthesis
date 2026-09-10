"""Author A's explicit offline semantic reviews of 36 sealed Student sessions.

This is a review-input constructor, not a model runner or evaluator-policy edit.
The human-readable decisions below were made after reading actual raw messages,
source packets and the frozen policy. Full original assistant responses are used
as exact evidence quotes; all five semantic judgments remain explicit.
No Final cases retain the frozen template unchanged except for the author.
"""

import copy
import json
import os
from collections import Counter
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_pq_student import evaluate


OUTPUT = Path(__file__).resolve().parents[1]
AUTHOR = "Codex 代理离线语义评审（非独立人类专家）"
VARIANTS = ("P_11", "Q_11", "P_29", "Q_29", "P_47", "Q_47")
TASKS = ("T1", "T2", "T3", "R1", "R2", "R3")
ASSESSMENT_ID = (
    "offline_assessment:"
    "c10c949addf7a772a24c1eede1d62a5c0a9a825b5f6d29b58dde6d9dcd1afc7d"
)
ASSESSMENT_MANIFEST_ID = (
    "qa_vnext_model_execution_pq_student_assessment_manifest:"
    "6fc282c6525c6e4d1ff502e4f2cf781494a8ee4b1c5dd533fed695f58fa46cfb"
)
NO_FINAL = {"Q_47/T2", "P_11/R3", "Q_11/R3"}
T3_CONTRADICTORY_SOURCE = {"P_11", "Q_11", "Q_47"}
R2_REVERSED_FORMULA = {"Q_11", "P_47"}


def read(path):
    return json.loads(path.read_bytes())


def evidence(audit, *indices):
    result = []
    for index in dict.fromkeys(indices):
        raw = audit["raw_messages"][str(index)]
        assert isinstance(raw, str) and raw
        result.append({"response_index": index, "quote": raw})
    return result


def semantic(review, audit, field, explanation, indices, status="PASS"):
    assert field in evaluate.FIELDS
    review[field] = {
        "status": status,
        "evidence": evidence(audit, *indices),
        "explanation": explanation,
    }


def selected_calculation(review, audit, call_id, expression, unit, indices, explanation):
    selected = next(item for item in audit["calculations"] if item["call_id"] == call_id)
    assert selected["original_expression"] == expression
    assert selected["independent_execution_verified"] is True
    assert all(index <= selected["response_index"] for index in indices)
    review["calculation"] = {
        "call_id": call_id,
        "unit": unit,
        "direction_multiplier": 1,
        "evidence": evidence(audit, *indices),
        "explanation": explanation,
    }
    return selected


def publication_and_consistency(review, audit, task):
    final = evaluate._lexical_final(audit)
    index = audit["first_final_index"]
    assert isinstance(final, dict) and index is not None
    assert "value" in final and "unit" in final
    # All 33 delivered cases in this assigned scope have explicit value/unit.
    # Never replace either field or shorten its numeric lexical precision.
    assert review["publication"]["value"] == final["value"]
    assert type(review["publication"]["value"]) is type(final["value"])
    assert review["publication"]["unit"] == final["unit"]
    assert type(review["publication"]["unit"]) is type(final["unit"])
    review["publication"].update(
        direction_multiplier=1,
        evidence=evidence(audit, index),
        explanation=(
            "保留实际首个 Final.value 的完整原词法及 Final.unit，不从工具或 answer "
            "替换主数值。本案原数值已具有其公开符号，不作减少幅值的额外翻转。"
        ),
    )
    calculation_index = next(
        item["response_index"]
        for item in audit["calculations"]
        if item["call_id"] == review["calculation"]["call_id"]
    )
    semantic(
        review,
        audit,
        "publication_alignment",
        "首个 Final 在实际成功计算之后公开该计算的数值或其原显示精度舍入；"
        "若同条消息附带另一个 tool 对象，它因首个 Final 终止而未执行，不将其当作计算证据。"
        "此项只判断计算与发布的对齐，不宣称所选财务公式正确。",
        [calculation_index, index],
    )
    semantic(
        review,
        audit,
        "final_answer_consistency",
        "仅据实际首个 Final 的原文核对对象、期间、方向、原单位和公开字段之间的一致性；"
        "未用先前消息替代 Final。PASS 不等同于主数值对参考正确，后者由冻结数值比较另判；"
        "来源声明是否与实际输入对应由 variable_correspondence 独立记录。",
        [index],
    )
    # Only an actual Final.answer answer quantity is added here. Dates, input
    # values, source-ID digits and outer sibling tool expressions are not
    # additional Final answer quantities under the frozen Final-only policy.
    if "answer" in final:
        answer = final["answer"]
        assert isinstance(answer, str)
        if task.startswith("R"):
            expected = {"R1": "16.53%", "R2": "18.92%", "R3": "25.43%"}[task]
            assert answer == expected
            secondary_value, secondary_unit = answer, "%"
        else:
            secondary_value = final["value"]
            secondary_unit = final["unit"]
            assert str(secondary_value) in answer
        assert answer in audit["raw_messages"][str(index)]
        review["secondary"] = [{
            "value": secondary_value,
            "unit": secondary_unit,
            "direction_multiplier": 1,
            "evidence": [{"response_index": index, "quote": answer}],
            "explanation": (
                "这是实际 Final.answer 另行公开的答案量，保留其自己的词法精度；"
                "百分号属于完整原词元。按 secondary 显示允差单独比较，不救回主答案。"
            ),
        }]


def route(review, audit, description, indices):
    review["route_observation"] = {
        "description": description,
        "evidence": evidence(audit, *indices),
        "mechanistic_not_utility": True,
    }


def review_t1(review, audit, variant):
    selected_calculation(
        review, audit, "tool:1", "148.8 - 134.8", "USD_million", [0],
        "同调用消息明确 $148.8 million 为 2008 期末、$134.8 million 为期初；"
        "实际执行期末减期初，结果单位继承两项共同的百万美元。",
    )
    semantic(
        review, audit, "formula_applicability",
        "模型在执行前明确 2008 年未确认税收优惠的净变化为期末减期初；"
        "实际 148.8-134.8 对应该期间同一账户余额，不加入利息罚款或未来预计变化。",
        [0],
    )
    semantic(
        review, audit, "variable_correspondence",
        "同条原话已把 148.8 和 134.8 对应到 2008 期末、期初；与公开 t7c1/t1c1 一致。"
        "cell 级 source:t7c1/source:t1c1 省略 n0 本身不是财务冲突；"
        "某些数字字符串键的 variables 未被字面量表达式消费，不据此虚构 resultrefs。",
        [0],
    )
    semantic(
        review, audit, "unit_handling",
        "同调用原话明确两余额均为 $... million；同单位相减且无缩放，计算为 USD_million。",
        [0],
    )
    route(
        review, audit,
        "实际采用已报告余额差 148.8-134.8；没有执行完整期间明细求和。"
        "这只是所观察路线，不代表路线效用或抽象类贡献。",
        [0],
    )


def review_t2(review, audit, variant):
    selected_calculation(
        review, audit, "tool:1", "99 - 110", "USD_million", [0],
        "原话明确 2008-12-31 的 $99 million 和 2007-12-31 的 $110 million；"
        "实际相减得到有符号 -11，无须将正减少幅值翻转。",
    )
    semantic(
        review, audit, "formula_applicability",
        "实际算式 99-110 比较题目要求的两年年末未确认税收优惠应计余额；"
        "不是 2007 年初余额、有效税率子集或利息罚款变化。",
        [0],
    )
    semantic(
        review, audit, "variable_correspondence",
        "执行前原话与显式 source:t9c1n0/source:t9c2n0 都将 99、110 正确对应到"
        "2008、2007 年末同一负债；数字字符串变量键虽未被 AST 名称消费，字面量"
        "表达式和财务角色说明仍能逐项核对。",
        [0],
    )
    semantic(
        review, audit, "unit_handling",
        "同调用清楚给出两项均为百万美元；有符号相减，不增加百分比或额外单位缩放。",
        [0],
    )
    route(
        review, audit,
        "实际采用 2008 与 2007 年末余额差 99-110；未执行 2008 全部滚动表变动求和。",
        [0],
    )


def review_t3(review, audit, variant):
    if variant in T3_CONTRADICTORY_SOURCE:
        selected_calculation(
            review, audit, "tool:1", "665 - 2239", "USD_thousand", [0],
            "实际执行有符号 665-2239；调用内两值明确写 thousand dollars，"
            "因此计算单位解释已建立。其显式来源映射冲突另判，不由正确算术消除。",
        )
        semantic(
            review, audit, "formula_applicability",
            "模型原话明确 employee separations 行、2004 年 12 月 31 日余额减"
            "1 月 1 日余额，实际算式亦为 665-2239；该余额差公式适用。",
            [0],
        )
        semantic(
            review, audit, "variable_correspondence",
            "FAIL：模型显式把 665 绑定到 source:t0c4n0、2239 绑定到"
            " source:t0c1n1；公开事实前者是标题中的日期 31，后者是年份 2004，"
            "并非这两个金额。不是省略 n0 的格式问题，而是真实数值/角色冲突。"
            "不能替模型到 t1c4n0/t1c1n0 找正确金额来忽略其显式矛盾。"
            "正确的余额差原话及最终数值不消除此来源对应失败。",
            [0], status="FAIL",
        )
        semantic(
            review, audit, "unit_handling",
            "原调用明确将 665、2239 写为 thousand dollars；实际同单位相减，"
            "与公开重组表 p15 的千美元口径相符。来源对象冲突由对应字段独立判 FAIL。",
            [0],
        )
        route(
            review, audit,
            "执行字面量余额差 665-2239，但显式源值声明误指日期/年份标题；"
            "未观察到期间明细求和。数值正确与来源轨迹失败分开记录。",
            [0],
        )
        return

    call_id, call_index = ("tool:5", 4) if variant == "P_47" else ("tool:6", 5)
    selected_calculation(
        review, audit, call_id, "665 - 2239", "USD_thousand", [2, call_index],
        "成功调用之前已在 response2 明确更正 t1c4n0=665、t1c1n0=2239，"
        "并反复说明 2004 员工离职项的期末、期初；公开同一表 p15 为 in thousands，"
        "成功算式原样使用这两金额且无缩放。P_47 的 unit 字段为空，此处是有限的"
        "离线来源单位解释，不声称模型曾写出单位，也不借后来 Final 补单位。",
    )
    semantic(
        review, audit, "formula_applicability",
        "成功执行前已明确 2004 employee separations 期末减期初；"
        "最终实际工具采用 665-2239。此前含冒号源名的语法失败保留，"
        "但未将未执行表达式或错误输出当作成功证据。",
        [2, call_index],
    )
    semantic(
        review, audit, "variable_correspondence",
        "最初不存在的 source:t1c0n0 已在成功调用之前更正为 source:t1c1n0；"
        "response2 的 t1c4n0=665、t1c1n0=2239 与公开员工离职行相符，"
        "成功调用消费同两字面值。依实际更正链判断，不由 reviewer 静默修写。",
        [2, call_index],
    )
    semantic(
        review, audit, "unit_handling",
        "成功调用之前已经明确选中同一公开重组表的 2004 员工离职两余额；"
        "p15 明确 in thousands，原样同单位相减保留 USD_thousand。"
        + (
            "P_47 的 unit 字段确为空；不强加冻结政策没有的必填字段要求，"
            "也不使用后到 Final 作为此前单位证据。"
            if variant == "P_47"
            else "response2 的变量还明确给出 thousand，早于成功执行。"
        ),
        [2, call_index],
    )
    route(
        review, audit,
        "先尝试把 source:... 写入 Python 算式而发生语法错误，随后改成实际成功的"
        "字面量余额差 665-2239。"
        + ("期间先读回了两项来源。" if variant != "P_47" else "本会话没有读源调用。")
        + "该错误/更正链被保留，不等于额外执行了期间明细路线。",
        [0, 2, call_index],
    )


def review_r1(review, audit, variant):
    expression = (
        "102400 / 619314 * 100" if variant == "P_29" else "(102400 / 619314) * 100"
    )
    selected_calculation(
        review, audit, "tool:1", expression, "percent", [0],
        "实际调用明确以 2012 年 12 月回购股数除第四季度总回购股数并乘 100；"
        "同种股数单位相消，结果为百分比，不是支出或剩余授权金额。",
    )
    semantic(
        review, audit, "formula_applicability",
        "原话及实际公式为 December 2012 purchases / fourth quarter purchases *100，"
        "适用于题目所问季度中 12 月股数份额。",
        [0],
    )
    semantic(
        review, audit, "variable_correspondence",
        "原话与 sources 将 102400 对应 source:t3c1n0 的 12 月股数、"
        "619314 对应 source:t4c1n0 的季度总股数；与公开表及 p0 一致，"
        "未混入平均股价、金额或 2013 年后续购股。",
        [0],
    )
    semantic(
        review, audit, "unit_handling",
        "模型执行前已说明计算股数比例及百分比；同单位股数相除后乘 100，"
        "无需把剩余授权列的 million 单位带入。",
        [0],
    )
    route(
        review, audit,
        "实际采用 12 月股数/已报告季度总股数，不是另行累加三个月。"
        + (
            "首个 Final 所在消息还写了一个 tool，但该 tool 未执行；"
            "只选择先前实际 tool:1。"
            if variant == "P_29" else ""
        ),
        [0, audit["first_final_index"]] if variant == "P_29" else [0],
    )


def review_r2(review, audit, variant):
    reversed_formula = variant in R2_REVERSED_FORMULA
    if reversed_formula:
        call_id, call_index, expression = "tool:1", 0, "t3c1 / t2c1 * 100"
    elif variant in {"P_11", "Q_29"}:
        call_id, call_index = "tool:3", 2
        expression = "(541 / 2859) * 100" if variant == "P_11" else "((541 / 2859) * 100)"
    else:
        call_id, call_index, expression = "tool:1", 0, "541 / 2859 * 100"
    indices = [0] if call_index == 0 else [0, call_index]
    selected_calculation(
        review, audit, call_id, expression, "percent", indices,
        "依实际成功调用解释单位：模型已指定 2012 年商业贷款与 TDR 总额，"
        "金额均为百万美元，同单位相除并乘 100。"
        + (
            "实际顺序为总额/商业，结果是错误的反比；仍保留这个真实计算，绝不换为正确公式。"
            if reversed_formula else "实际成功顺序为商业/总额。"
        ),
    )
    semantic(
        review, audit, "formula_applicability",
        (
            "FAIL：实际 t3c1/t2c1*100 是 2859/541*100，即 TDR 总额除商业贷款，"
            "与所问商业贷款占总额的份额相反；不能把选取正确的两数等同于公式正确。"
            if reversed_formula else
            "原话已说明商业贷款/总 TDR *100；成功实际式 541/2859*100"
            "使用同一 2012 年末金额口径，不把余额变动、准备金或贷款笔数混入。"
        ),
        indices, status="FAIL" if reversed_formula else "PASS",
    )
    semantic(
        review, audit, "variable_correspondence",
        "原调用把 541 与商业贷款、2859 与总 TDR 的 2012 年值对应，"
        "与公开 t2c1/t3c1 金额一致。"
        + (
            "两项显式 source IDs 都对应正确金额，错误是比值顺序而不是取值/期间映射。"
            if reversed_formula else
            "此前源名语法失败后成功式仍保留原两值及其原财务角色。"
            if call_index else
            "执行前消息还直接明确两个财务角色及其美元百万金额。"
        )
        + (
            "Q_29 的 SEGMENT12 不是可解析公开来源，作为引用缺陷保留；"
            "但前序原变量名 source:t2c1n0/source:t3c1n0、金额和明确商业/总额公式"
            "已提供可核对的角色依据。没有把该失效引用冒充已验证事实，也不新设必填ID门。"
            if variant == "Q_29" else ""
        ),
        indices,
    )
    semantic(
        review, audit, "unit_handling",
        "执行前原变量/消息明确两项相同百万美元口径；实际相除并乘100得到 percent。"
        "反比错误若存在，由 formula_applicability 判 FAIL，不混同为单位换算错误。",
        indices,
    )
    route(
        review, audit,
        (
            "实际执行总 TDR/商业贷款的反比 2859/541*100，并发布 528.47%；"
            "首个 Final 同消息的常数 tool 未执行。"
            if reversed_formula else
            "实际采用商业贷款/已报告总额 541/2859*100，未另做消费者或状态分组重建。"
            + ("此前两次源名表达式语法错误被保留。" if call_index else "")
            + ("Final 保留无法解析的 SEGMENT12 引用。" if variant == "Q_29" else "")
        ),
        [0, call_index, audit["first_final_index"]],
    )


def review_r3(review, audit, variant):
    selected_calculation(
        review, audit, "tool:1", "(1279337 - 1019953) / 1019953 * 100", "percent", [0],
        "原话明确新值2016、旧值2015、(new-old)/old*100；实际对应公开同一营运资本行。"
        "同口径金额单位在比例中相消，结果为percent。",
    )
    semantic(
        review, audit, "formula_applicability",
        "模型执行前给出 (new_value-old_value)/old_value*100，"
        "实际使用2015营运资本作基期分母；没有将总资产减总债务替代公司营运资本。",
        [0],
    )
    semantic(
        review, audit, "variable_correspondence",
        "原话、new_value/old_value 与 source:t2c1n0/source:t2c2n0"
        "把1279337映射2016、1019953映射2015，和公开已报告营运资本行一致。",
        [0],
    )
    semantic(
        review, audit, "unit_handling",
        "原公式比较同一表同口径营运资本金额，差额除以同单位基期值后乘100；"
        "单位相消得到percent，不需要用后来Final补出一个此前未执行的金额换算。",
        [0],
    )
    route(
        review, audit,
        "实际采用已报告营运资本的基期增长率；没有虚构流动资产/流动负债分项重建。"
        "首个Final同条消息写出的重复tool未执行，只认实际先前tool:1。",
        [0, audit["first_final_index"]],
    )


def main():
    destination = OUTPUT / "review_inputs/reviewer_a.json"
    assert not destination.exists(), "reviewer_a.json already exists; no overwrite"
    assessment = read(OUTPUT / "assessment/report.json")
    assert assessment["id"] == ASSESSMENT_ID and assessment["sessions"] == 84
    assert read(OUTPUT / "assessment/manifest.json")["id"] == ASSESSMENT_MANIFEST_ID
    assert read(OUTPUT / "preparation/evaluation_policy.json") == evaluate.policy()
    templates = read(OUTPUT / "assessment/review_templates.json")["reviews"]
    reviews, grades = {}, {}
    handlers = {
        "T1": review_t1, "T2": review_t2, "T3": review_t3,
        "R1": review_r1, "R2": review_r2, "R3": review_r3,
    }
    for variant in VARIANTS:
        for task in TASKS:
            key = variant + "/" + task
            audit = read(OUTPUT / ("assessment/audits/" + key + ".json"))
            packet = read(OUTPUT / ("assessment/packets/" + key + ".json"))
            assert packet["audit"] == audit
            public = packet["public"]
            private = packet["private_reference_for_offline_review_only"]
            assert private["key"] == task
            assert private["public_document_id"] == public["id"] == audit["public_document_id"]
            assert audit["model_identity"]["variant"] == variant
            review = copy.deepcopy(templates[key])
            assert review["audit_id"] == audit["id"]
            review["author"] = AUTHOR
            if key in NO_FINAL:
                assert audit["first_final_index"] is None
                assert audit["terminal"] == "response_budget_exhausted"
                expected = copy.deepcopy(templates[key])
                expected["author"] = AUTHOR
                assert review == expected
            else:
                assert audit["first_final_index"] is not None
                handlers[task](review, audit, variant)
                publication_and_consistency(review, audit, task)
            grade = evaluate.qualify(audit, review, public, private)
            reviews[key] = review
            grades[key] = grade
    expected_keys = {variant + "/" + task for variant in VARIANTS for task in TASKS}
    assert set(reviews) == expected_keys and len(reviews) == 36

    by_task = {}
    for task in TASKS:
        selected = [grades[variant + "/" + task] for variant in VARIANTS]
        by_task[task] = {
            "answer": dict(Counter(item["task_answer_status"] for item in selected)),
            "trace": dict(Counter(item["trace_status"] for item in selected)),
        }
    summary = {
        "sessions": len(grades),
        "answer": dict(Counter(item["task_answer_status"] for item in grades.values())),
        "trace": dict(Counter(item["trace_status"] for item in grades.values())),
        "by_task": by_task,
    }
    payload = {
        "metadata": {
            "author": AUTHOR,
            "reviewer_is_blinded": False,
            "reviewer_is_independent_human_expert": False,
            "offline_post_generation": True,
            "assessment_id": ASSESSMENT_ID,
            "assessment_manifest_id": ASSESSMENT_MANIFEST_ID,
            "policy_id": evaluate.policy()["id"],
            "scope": sorted(expected_keys),
            "in_memory_qualify_completed": True,
            "no_Final_cases_only_author_changed": sorted(NO_FINAL),
            "original_Final_value_and_unit_preserved": True,
            "no_model_or_training_or_finalize_invoked": True,
            "new_semantic_gate_added": False,
        },
        "reviews": reviews,
    }
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    with destination.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    assert destination.read_bytes() == encoded
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
