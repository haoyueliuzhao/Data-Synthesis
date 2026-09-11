"""The 36 public/private target decisions, fixed before the 18 local reviews."""

import ast
from collections import Counter
from pathlib import Path

from .core import (
    ALIGNMENTS,
    AUDIT,
    AUDIT_SHA,
    CASE_KEYS,
    DOCUMENT,
    OLD,
    OUTPUT,
    TASKS,
    implementation_references,
    read_json,
    record,
    reference,
    require,
    seal,
    sha,
)
from .policy import policy


def item(
    obj,
    period,
    sign,
    units,
    anchors,
    explanation,
    *,
    status="ALIGNED",
    alternatives=(),
    resolution=None,
    proposed_question=None,
):
    return {
        "public_object": obj,
        "public_period": period,
        "public_sign_semantics": sign,
        "public_unit_scope": units,
        "additional_public_segments": anchors.split(),
        "alignment_status": status,
        "explanation": explanation,
        "unresolved_public_interpretations": list(alternatives),
        "required_resolution": resolution,
        "proposed_public_question": proposed_question,
    }


PERCENT = "百分比；同口径金额的共同币种和尺度约去，不靠参考答案补量。"
CHANGE = "后期减前期的有符号变化；明确文字所述下降幅度可保留等价方向解释。"
SPECS = {
    "D01": item(
        "未确认税收利益的 gross liability，不含利息罚款",
        "2008 财政年度期初至期末",
        CHANGE,
        "千美元；表中期末 139549 对应公开约 139.5 百万美元。",
        "q0 t0c0 t6c0",
        "公开问题指定 gross liability，表首尾日期与 q0 数量尺度支持登记对象；不混入另列利息罚款。",
    ),
    "D02": item(
        "同一 gross liability 的相对变化",
        "2008 财政年度对 2007 期末/2008 期初",
        CHANGE,
        PERCENT,
        "q0 t0c0 t6c0",
        "问题明确百分比变化，首尾日期及前期基数对应登记期间；D01 的货币尺度不会改变比例。",
    ),
    "D03": item(
        "allowance for doubtful accounts 的下降",
        "2018 期初至 2018-12-31",
        "decline 已表达下降方向；负变化率与带下降说明的正幅度可指同一变化。",
        PERCENT,
        "t0c1 t1c0 t4c0",
        "2018 列的 beginning/end 与公开 decline 对齐。这里的显示方向约定不等于另选财务目标。",
    ),
    "D04": item(
        "gross unrecognized tax benefits 中归为 other long-term liabilities 的份额",
        "2012",
        "分类份额，而非负债余额变化。",
        PERCENT,
        "p9 q0 q1",
        (
            "p9 的税收利益总额表及 q0 的分类说明共同限定了问题中的 gross "
            "liabilities；不是公司全部负债。"
        ),
    ),
    "D05": item(
        "severance 与 lease termination 两项重组余额",
        "来源所述 1999 年末剩余余额",
        "两项余额的正金额合计，不含 canceled contracts。",
        "百万美元；q1 明示两个组成金额。",
        "q0 q1",
        "问题列明两项，q1 与总额/第三项明确区分；沿用其公开披露精度，不重新推导其他重组项目。",
    ),
    "D06": item(
        "additions charged to expense，不是 allowance 余额",
        "2011 至 2012",
        CHANGE,
        PERCENT,
        "t0c1 t0c2 t2c0",
        "问题直接指定变动组成项；表中费用计提行与年度列支撑登记的跨年增长量。",
    ),
    "D07": item(
        "公开市场回购普通股数",
        "2018 和 2017 两个截至 12-31 的年度",
        "两个年度实际回购股数合计。",
        "百万股；q5 区分股数与美元成本。",
        "q5",
        "问题同时指定 shares、两个年度和 millions；不将成本、授权余量或发行数代入。",
    ),
    "D08": item(
        "MFC 分部 total operating expenses",
        "2016",
        "经营费用金额，而不是经营利润。",
        "百万美元；p14 的 MFC 经营结果表及美元销售额。",
        "p10 p14 t0c1",
        (
            "问题本身略去分部名，但紧邻表的 p14 明确 MFC operating result"
            "s，p10 另起该分部标题；登记不是公司整体费用。"
        ),
    ),
    "D09": item(
        "实际资本化利息",
        "2017 至 2018",
        CHANGE,
        PERCENT,
        "p15",
        "p15 明确列示各年度实际资本化利息；不是未来支出计划或付息到期表。",
    ),
    "D10": item(
        "题面所称 deferred tax assets 与 regulatory assets，未明示是总余额还是特定调整额",
        "2013 至 2014",
        "资产余额变动与资产调整额的增长不是同一目标。",
        PERCENT,
        "p20 p21 p22",
        (
            "p22 披露 Medicare Part D 调整导致的递延税项资产减少及监管资"
            "产增加；私有目标只比较该调整额。题面未明确这个限定，不能称为"
            "总资产余额增长的公开认证。"
        ),
        status="PUBLIC_UNDERSPECIFIED",
        alternatives=(
            "所披露 Medicare Part D 对应调整额的跨年增长",
            "递延税项资产和监管资产总余额的跨年变化",
        ),
        resolution="在新开发任务版本明确只询问所披露调整额；若询问总余额，需要相应公开余额来源。",
        proposed_question=(
            "What was the percentage change from December 31, 2013 to Dec"
            "ember 31, 2014 in the disclosed Medicare Part D adjustment a"
            "mount, recorded as a reduction in deferred tax assets and an"
            " increase in regulatory assets?"
        ),
    ),
    "D11": item(
        "MFC operating profit 的算术平均",
        "2014、2015、2016 三个年度",
        "年度经营利润平均值。",
        "百万美元；题面与 p14 一致。",
        "p14 t0c1 t0c2 t0c3",
        "题面明确 MFC、平均及期间；三列经营利润均属于同一表内口径。",
    ),
    "D12": item(
        "MFC net sales 增长率",
        "2015 至 2016",
        CHANGE,
        PERCENT,
        "p10 p14 q0",
        (
            "p14 将表定位到 MFC，q0 也明确讨论 MFC 2016/2015 销售额；登记"
            "不是利润增长或公司整体销售额。"
        ),
    ),
    "C01": item(
        "employee separations liability 的净变化",
        "2006 年度",
        CHANGE,
        "千美元；来源明确表格尺度。",
        "p15",
        "公开年度及员工离职负债对象对齐。原一行表内日期和金额分开保留，不重新选择数值跨度。",
    ),
    "C02": item(
        "employee separations liability 的净变化",
        "2005 年度",
        CHANGE,
        "千美元；来源明确表格尺度。",
        "p15",
        "2005 年变动属于员工离职行，不是租赁终止或全部重组余额；登记使用对应期初期末。",
    ),
    "C03": item(
        "不含应计利息的 unrecognized tax benefits 余额变化率",
        "2007-04-01 至 2008-03-31",
        CHANGE,
        PERCENT,
        "p13 t0c0 t2c0",
        (
            "公开税收利益余额表的首尾日期和不含利息说明支持登记；含利息的"
            "约 0.2 百万 prose 不是同一余额。"
        ),
    ),
    "C04": item(
        "asset retirement liability 的累计净变化",
        "2002-09-29 至 2004-09-25",
        CHANGE,
        "百万美元；题面 in millions 及 p0 明示。",
        "p0 t0c0 t3c0 t6c0",
        (
            "表中 2002 起始余额与 2004-09-25 余额支撑原任务区间；2003 中"
            "间余额不是起点。来源字段的声明语义另在六条会话中核对。"
        ),
    ),
    "C05": item(
        "unrecognized tax benefits 余额的相对变化",
        "2011 年末至 2012 年末",
        CHANGE,
        PERCENT,
        "t0c2 t0c3 t7c0",
        (
            "问题指定 2011 到 2012 的余额变化，表的年末行和年度列支持登记"
            "；不是 2011 年初或 2013 年末。"
        ),
    ),
    "C06": item(
        "goodwill total carrying amount，不是单个分部",
        "2015 年末至 2017 年末",
        CHANGE,
        PERCENT,
        "t1c0 t13c0 t0c5",
        "题面 total 与总计列及 2015/2017 日期对齐；分部内部重分类不被误当成总额新增。",
    ),
    "C07": item(
        "goodwill total carrying amount，不是单个分部",
        "2016 年末至 2017 年末",
        CHANGE,
        PERCENT,
        "t8c0 t13c0 t0c5",
        "题面指定 2016 起点，总计列的两个年末口径一致；不能使用 C06 的 2015 基数。",
    ),
    "C08": item(
        "outstanding common shares 的净增加",
        "题面 period of 2016 to 2018 未明确年初还是年末起点",
        "增加为正；核心未定轴是区间，不是符号或股份类别。",
        "百万股；p25 与题面明确。",
        "p25 t0c3 t1c0 t3c0 t7c0",
        (
            "完整公开表同时列出 2016-01-03 期初、2016-12-31 期末与 2018-1"
            "2-29 期末；题面不独立指定前两者之一。登记采用完整三财政年度"
            "，但不能用私有目标排除公开的年末比较解释。"
        ),
        status="PUBLIC_UNDERSPECIFIED",
        alternatives=("2016-01-03 期初至 2018-12-29 期末", "2016-12-31 期末至 2018-12-29 期末"),
        resolution="新开发版本在公开题面明确起止日期；旧确认题不能因此重新成为独立确认。",
        proposed_question=(
            "What was the net increase in outstanding common shares from "
            "the opening balance on January 3, 2016 to the closing balanc"
            "e on December 29, 2018, in millions of shares?"
        ),
    ),
    "C09": item(
        "final purchase price allocation 中所问 sum of liabilities",
        "最终收购价分配，不是初步分配或经营期间流量",
        "承担负债的正金额与负债对净资产的有符号贡献是两种不同口径。",
        "千美元；p3 及表内美元金额。",
        "p3 t0c1 t5c0 t6c0",
        (
            "公开表以负号列示负债贡献，问题说 sum of liabilities 但未明确"
            "正金额或有符号贡献。正金额登记具有合理财务解释，不能直接判它"
            "错误；也不能仅靠该私有定义认证公开目标已唯一消歧。"
        ),
        status="PUBLIC_UNDERSPECIFIED",
        alternatives=("承担负债的正金额合计", "购买价分配表中负债对净资产的有符号贡献合计"),
        resolution="后继开发题面明确所问物理量和符号约定；不要把中间负贡献自动判错，须看终局是否完成请求。",
        proposed_question=(
            "Based on the final purchase price allocation, what was the t"
            "otal positive amount of liabilities assumed, in thousands of"
            " dollars, rather than their signed contribution to net asset"
            "s?"
        ),
    ),
    "C10": item(
        "排除 foreign currency translation adjustment 后的 contingent consideration",
        "2014",
        "去除一个有符号调整项；不能把其负号再次误用。",
        "题面要求百万，来源表为千美元。",
        "p3 t0c1",
        "公开反事实明确排除 FX；登记包含千到百万换算，不沿用旧原始注释遗漏的尺度转换。",
    ),
    "C11": item(
        "cash 的净变化；是否仅指三类活动合计未被公开明确限定",
        "2015 年度",
        CHANGE,
        "百万美元；现金流表明示。",
        "p1 p3 p24 t0c0",
        (
            "公开表只列经营、投资、筹资流量；原材料没有 2014/2015 现金端"
            "点或包含汇兑等影响的完整调节表。私有目标明示仅为活动合计，不"
            "能据缺失项推断其为完整现金余额变化。"
        ),
        status="NEED_SOURCE_CHECK",
        alternatives=(
            "公开题面通常所问的完整现金余额净变化",
            "私有登记限定的三类已披露活动净现金流合计",
        ),
        resolution="若保留完整现金净变动目标，需补充可公开的端点/调节资料；若改问已披露活动合计，另立明确的新任务版本，不回写旧题。",
    ),
    "C12": item(
        "cash 的净变化；是否仅指三类活动合计未被公开明确限定",
        "2016 年度",
        CHANGE,
        "百万美元；现金流表明示。",
        "p1 p3 p24 t0c0",
        (
            "仅有 2016/2017 现金余额，缺少 2015 起点；三类活动表没有完整"
            "汇兑等调节。不能将私有的活动合计限制当成公开题面对现金余额变"
            "化的定义。"
        ),
        status="NEED_SOURCE_CHECK",
        alternatives=(
            "公开题面通常所问的完整现金余额净变化",
            "私有登记限定的三类已披露活动净现金流合计",
        ),
        resolution="需要对应公开调节来源，或另立明确询问三类活动合计的新任务；本次不抓取新来源。",
    ),
    "C13": item(
        "capital lease obligations 的 principal only",
        "披露的合同义务总额口径",
        "本金正金额；排除该类租赁的利息，不排除其他债务的利息。",
        "百万美元；题面和表/附注口径。",
        "q0 q2 t0c0",
        "题面 principal only 与 q2 的资本租赁利息组成、q0 的本金说明对齐；不是全部含息支付。",
    ),
    "C14": item(
        "Oppenheimer 的已报告持股加上明确排除的待归属 RSUs",
        "题面假设 RSUs 归属后的状态",
        "股数合计；不重复加入已计入的间接持股。",
        "股，不是美元或百万股。",
        "t9c0 q62",
        "Oppenheimer 行与 footnote 11 明确区分已报告股份及未纳入的未归属 RSUs，支持该假设合计。",
    ),
    "C15": item(
        "actual total rent expense",
        "2010、2011、2012 三个财政年度",
        "三个年度费用合计，而非期末负债之差。",
        "百万美元；题面与 p26 一致。",
        "p26",
        "p26 给出过去三个财政年度实际租金费用；后面的未来最低付款表不是这一目标。",
    ),
    "C16": item(
        "coal revenue 占 total operating revenues 的期间份额",
        "2014、2015、2016 合并期间",
        "期间分子合计/期间分母合计，不是未加权年度百分比平均。",
        PERCENT,
        "t0c1 t0c2 t0c3 t4c0 t9c0",
        (
            "题面 total operating revenues 明确总经营收入；不是 freight-o"
            "nly，期间问题支持聚合后的份额。"
        ),
    ),
    "C17": item(
        "实际 aggregate rent expense",
        "2013 至 2014",
        CHANGE,
        PERCENT,
        "q0",
        "q0 明列三年度租金费用和年度次序；未来最低租赁付款不是实际历史费用。",
    ),
    "C18": item(
        "实际 aggregate rent expense",
        "2012 至 2013",
        CHANGE,
        PERCENT,
        "q0",
        "与 C17 共用来源但有独立的年度起终点；不把未来付款或另一年费用当成当前对象。",
    ),
    "C19": item(
        "Danvers 设施月度 base rent",
        "2008-11 至 2010-06 条款，对比 2010-07 至 2014-02 条款",
        "新月租基数相对旧月租基数的增长，不按不同合同年数累计。",
        PERCENT,
        "p17",
        "公开 p17 明确设施、每月金额和三个合同子期间；题面缩略年份可由该段消歧。",
    ),
    "C20": item(
        "Danvers 设施月度 base rent",
        "2010-07 至 2014-02 条款，对比 2014-03 至 2016-02 条款",
        "新月租基数相对旧月租基数的增长。",
        PERCENT,
        "p17",
        "p17 精确月份支持题面两个缩略期间，不是公司总租金或另一设施月租。",
    ),
    "C21": item(
        "Merck total sales 年同比增长",
        "2013 相对 2012",
        CHANGE,
        PERCENT,
        "t0c1 t0c2 t1c0",
        "growth in 2013 结合并列年度表按同比解释；total sales 排除仅制药分部或个别产品。",
    ),
    "C22": item(
        "Merck total sales 年同比增长",
        "2012 相对 2011",
        CHANGE,
        PERCENT,
        "t0c2 t0c3 t1c0",
        "同一总销售额行的 2012/2011 年度列支撑登记；不使用 C21 的 2013 年。",
    ),
    "C23": item(
        "2021 到期资本租赁最低支付占全部最低支付的份额",
        "2021 对全部列示期限",
        "支付金额份额；分母包括利息，不是净现值。",
        PERCENT,
        "t0c2 t3c0 t7c0",
        (
            "题面 minimum capital lease payments 与资本租赁列及总最低付款"
            "行对齐；不同于 operating leases 或扣息现值。"
        ),
    ),
    "C24": item(
        "2020 到期资本租赁最低支付占全部最低支付的份额",
        "2020 对全部列示期限",
        "支付金额份额；分母包括利息，不是净现值。",
        PERCENT,
        "t0c2 t2c0 t7c0",
        "只改变所问到期年份，仍保留原资本租赁最低付款总体，不能临时改成现值分母。",
    ),
}


def source_leaves(node):
    if isinstance(node, str):
        return [node] if node.startswith("source:") else []
    if isinstance(node, dict):
        return [leaf for child in node.get("args", []) for leaf in source_leaves(child)]
    return []


def literal_constant(path, name):
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            value = ast.literal_eval(node.value)
            require(isinstance(value, str), "contract.literal_string")
            return value
    raise ValueError("contract.constant_missing")


def build(root, guard, controls):
    root = Path(root).resolve()
    require(set(SPECS) == set(TASKS), "ledger.exact_36")
    require(controls["returncode"] == 0, "ledger.new_controls_passed")
    require(not (root / OUTPUT / "cases").exists(), "ledger.precedes_local_reviews")
    require(
        not (root / OUTPUT / "manual_reviews").exists(), "ledger.precedes_new_review_transcription"
    )
    private_path = OLD + "/preparation/private/evaluation_targets.json"
    private_ref = reference(root, private_path)
    targets = read_json(root / private_path)
    require(set(targets) == set(TASKS), "ledger.original_36_not_reselected")
    audit_raw = Path(AUDIT).read_bytes()
    require(sha(audit_raw) == AUDIT_SHA, "ledger.exact_user_audit")
    common = (
        "trusted_data_synthesis/src/trusted_synthesis/experiments/fin"
        "ance_qa_vnext_thinking_comparison/online/common.py"
    )
    suffix = (
        "trusted_data_synthesis/src/trusted_synthesis/experiments/fin"
        "ance_qa_vnext_trace_delivery/instructions.py"
    )
    contract = record(
        "public_contract",
        system=literal_constant(root / common, "SYSTEM")
        + "\n\n"
        + literal_constant(root / suffix, "TRACE_SUFFIX"),
        source_references=[reference(root, common), reference(root, suffix)],
        contract_is_existing_not_a_new_model_prompt=True,
    )
    policy_record = policy()
    entries, payloads = [], {}
    for key in TASKS:
        specification = SPECS[key]
        require(specification["alignment_status"] in ALIGNMENTS, "ledger.status")
        target = targets[key]
        public_path = OLD + f"/preparation/public/{key}.json"
        public = read_json(root / public_path)
        require(public["id"] == target["public_document_id"], "ledger.public_private_identity")
        operands = [target["facts"][f] for f in dict.fromkeys(source_leaves(target["target"]))]
        segment_ids = list(
            dict.fromkeys(
                [f["segment"] for f in operands] + specification["additional_public_segments"]
            )
        )
        require(
            all(k in public["segments"] for k in segment_ids),
            "ledger.all_public_anchors_exist:" + key,
        )
        entry = record(
            "target_ledger_entry",
            task_key=key,
            original_panel=target["panel"],
            current_research_role="known_development"
            if target["panel"] == "dev"
            else "historical_confirmation_now_known",
            public_document_reference=reference(root, public_path),
            public_document_id=public["id"],
            public_question=public["question"],
            public_target_review=specification,
            original_private_targets_reference=private_ref,
            original_goal_scope=target["goal_scope"],
            original_reference_unit=target["unit"],
            original_reference_expression=target["target"],
            reference_physical_quantity=target["goal_scope"]["quantity"],
            registered_operand_records_reused=operands,
            public_evidence=[
                {"segment_id": k, "original_segment": public["segments"][k]} for k in segment_ids
            ],
            new_reference_arithmetic_evaluations=0,
            public_task_not_rewritten=True,
            proposed_question_is_only_a_new_development_version_not_issued=True,
            eligible_as_fresh_independent_confirmation=False,
            reviewer="same execution assistant; known outputs; not independent or blind",
        )
        entries.append(entry)
        payloads[f"entries/{key}.json"] = entry
    report = record(
        "target_ledger",
        entries=entries,
        task_count=len(entries),
        alignment_counts=dict(
            Counter(e["public_target_review"]["alignment_status"] for e in entries)
        ),
        policy_id=policy_record["id"],
        public_contract_id=contract["id"],
        implementation=implementation_references(root),
        future_local_case_keys=[{"task": t, "arm": a, "seed": s} for t, a, s in CASE_KEYS],
        ledger_frozen_before_new_local_case_judgments=True,
        already_known_outcomes_not_a_blind_measurement=True,
        old_24_confirmation_questions_are_now_known_material=True,
        full_financial_source_reaudit_performed=False,
        new_controls={
            "command": controls["command"],
            "returncode": controls["returncode"],
            "stdout_sha256": sha(controls["stdout"]),
            "stderr_sha256": sha(controls["stderr"]),
            "historical_control_suites_rerun": False,
        },
        guard=guard.receipt(),
    )
    payloads.update(
        {
            "report.json": report,
            "policy.json": policy_record,
            "public_contract.json": contract,
            "source_audit.original.txt": audit_raw,
            "new_controls.stdout.txt": controls["stdout"],
            "new_controls.stderr.txt": controls["stderr"],
            "design_at_ledger_freeze.md": (root / DOCUMENT).read_bytes(),
        }
    )
    manifest = seal(root, "ledger", payloads)
    return {
        "id": report["id"],
        "manifest_id": manifest["id"],
        "alignment_counts": report["alignment_counts"],
    }
