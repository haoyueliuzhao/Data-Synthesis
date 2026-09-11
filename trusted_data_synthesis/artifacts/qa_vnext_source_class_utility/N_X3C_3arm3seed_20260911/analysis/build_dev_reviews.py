"""Transcribe 108 already-read masked reviews; never infer a score from an arm.

This post-generation review aid is outside the frozen implementation. The case
assignments below are explicit offline judgments by the same assistant that ran
the study, not an independent expert or an automatic financial classifier.
Only masked public packets and their blank templates are read. No identity map,
training log, private financial target, qualification, or group score is read.
"""

# ruff: noqa: E501 -- preserve readable, unsplit multilingual review statements.

import copy
import json
import re
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.plan import sha
from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.student_review import (
    FIELDS,
    _evidence,
    _quantity_evidence,
)

OUTPUT = Path(__file__).resolve().parents[1]
ASSIGNMENTS = {}
DESCRIPTIONS = {}
STATUS = {"P": "PASS", "F": "FAIL", "U": "UNDETERMINED", "N": "NOT_ESTABLISHED"}


def family(name, cases, statuses, formula, variables, units):
    assert len(statuses) == 5
    DESCRIPTIONS[name] = (formula, variables, units)
    for index in cases:
        assert index not in ASSIGNMENTS
        ASSIGNMENTS[index] = (name, statuses)


family(
    "average_header_amount_map",
    [1, 15, 17, 29, 60, 71],
    "PFPNP",
    "2014、2015、2016 三年 MFC 营业利润的算术平均是适用关系；公开计划列出三项再除以 3。计划不等于真实执行。",
    "结构化来源断言把 1018、1282、1344 等利润金额对应到 t0 的年份表头，而非 t2 利润单元格；明确错误的金额—来源映射不能因正文另有正确数字而被认证。",
    "公共文档 MFC 表的单位为百万美元；三项同尺度平均保留该尺度。",
)
family(
    "percentage_false_cents",
    [2],
    "PFFPP",
    "期末减期初，再除以期初乘 100，适用于该年度负债百分比变化。",
    "当前输入把期初金额指向不存在的 t0c1n1，并用所谓 cents 的转换构造与字面表达式不同的变量金额；未消费变量不能认证错误的当前来源断言。",
    "明确声称原表为 cents 并除以 100，与公共文档的负债金额尺度矛盾；比例数值偶然抵消不能使该单位解释成立。",
)
family(
    "percentage_invalid_tool_no_final",
    [3],
    "PFFNU",
    "公开尝试包含适用的期末减期初、除期初乘 100 关系，但对象值 tool 导致未知工具错误，没有成功计算。",
    "公开尝试把期初绑定到不存在的 t0c1n1；不对这个标识符做修复。后续字面重试也未形成真实工具绑定。",
    "初始公开声明把表内千美元金额直接当作 USD，未给出一致的尺度转换；q0 的约 139.5 百万美元提供独立尺度核对。",
)
family(
    "shares_wrong_cost_no_formula",
    [4, 9, 107],
    "UFPNP",
    "直接发布 1.3 百万股，并列两年的回购量，但未公开明确求和式或实际计算；不补造心算过程。",
    "Final 明确把 2018/2017 股数对应到 q5n2/q5n3；这两个事实是 45/54 百万美元回购成本，不是 q5n0/q5n1 的 0.6/0.7 百万股。",
    "实际 Final 明确为 million shares；这属于股数，不解释成百万美元。",
)
family(
    "sales_correct_plan_pseudo_result",
    [5],
    "PPPFP",
    "公开计划为 (2016 销售额 - 2015 销售额) / 2015 销售额 * 100，方向和范围适用。",
    "调用计划前的财务对象、期间和 6608/6770 金额与 MFC 公共销售表相符，来源 t1c1/t1c2 也相符。",
    "同尺度销售额在比例中抵消，乘 100 给出百分比；不把表内简写美元数当作额外绝对单位结论。",
)
family(
    "expense_addition_wrong_balance_sources",
    [6, 21, 26, 63, 94, 101],
    "PFPPP",
    "2012 费用计提增加额相对 2011 的 (29.7 - 21.0) / 21.0 * 100 关系适用。",
    "当前明确金额映射指向 t1c1n0/t1c2n0 的期初准备金 48.1/50.9，而题目所需费用计提 29.7/21.0 在 t2c1/t2c2。正确字面算术不认证错误的财务来源绑定。",
    "两项费用同币种同尺度，比例抵消；公开式乘 100，发布百分比。",
)
family(
    "expense_addition_planned_only",
    [7, 28, 88],
    "PPPNP",
    "公开式 (29.7 - 21.0) / 21.0 * 100 适用于费用计提的跨年百分比变化。",
    "公开模型在尝试前用 2012_additions=29.7、2011_additions=21.0 和财务指标名说明来源，符合公共表 t2；没有相反的金额—错误事实断言。",
    "公开式同尺度相消并乘 100，实际 Final 自身带百分号；对象值 tool 的失败不补造成功计算。",
)
family(
    "expenses_equal_profit_wrong_header",
    [8, 18, 58, 64, 78, 79, 96],
    "FFPNP",
    "把 operating profit 1018 直接当作 total operating expenses 是错误财务等式；该 MFC 表的费用应来自销售额减营业利润。",
    "声明的 source:t0c1n0 是年份 2016 表头，不是利润金额或费用来源；指标混淆与金额来源声明均不能认证。",
    "Final 的百万美元尺度与该 MFC 表一致；尺度正确不证明所选财务指标正确。",
)
family(
    "deferred_assets_wrong_UTB_object",
    [10, 61, 72, 77, 84, 95],
    "PFPPP",
    "通常的跨年差额除以前期再乘 100 这一比例形式适用；此项不认证操作数的财务对象。",
    "实际使用 195237/177947 的未确认税收利益负债端点，而所问 DTA/监管资产相关调整在 p22 为 6348/6241。即使引用真实 UTB 单元格，财务对象仍错误。",
    "共同货币尺度在比例中抵消，乘 100 后是百分比；不把单位正确等同于指标正确。",
)
family(
    "gross_change_wrong_base_USD",
    [11, 22, 33, 36, 38, 103],
    "PPFPP",
    "经过三次语法失败，真实 tool:4 执行期末 139549 减期初 201808；年度净变化关系适用。",
    "选择当前修正后的字面调用；此前及同调用正文明确区分 2008-11-28 期末与 2007-12-01 期初，公共表可对应这两个金额。早期失败调用中的非规范/不存在标识符不认证、不替换。",
    "模型预先明确宣称 USD 并按该解释发布 -62259 USD，但公共表金额为千美元（q0 约 139.5 百万美元可核对）。这是实际单位错误；过程对齐使用模型声明的 USD 不等于认证财务尺度。",
)
family(
    "shares_correct_direct_no_formula",
    [12, 42, 87, 102],
    "UPPNP",
    "直接发布股数，未公开明确求和式或实际工具运算；不从正确最终数值反推一个已执行的加法。",
    "公开说明两年 0.6/0.7 百万股，Final 引用 q5n0/q5n1，确为回购股数而非美元成本。",
    "实际 Final 明确 million shares，与文档股数单位一致。",
)
family(
    "sales_wrong_growth_direction",
    [13, 68, 91, 108],
    "FPPPP",
    "明确称作 growth，却实际计算 (2015 - 2016) / 2015 * 100 并发布正值；不是按实际 Final 声明的下降幅度，不从题目或参考答案反转方向。",
    "所用 6770 和 6608 分别是公共 MFC 表 2015、2016 净销售额；错误在增长关系方向而非这两个事实本身。",
    "同尺度销售额相消，乘 100，实际 Final 为百分比。",
)
family(
    "sales_no_final_pseudo_calls",
    [14],
    "PPPNU",
    "公开 calculate 字段持续计划正确的销售增长关系，但它不是工具协议的实际调用。",
    "公开期间、净销售指标和 6608/6770 与 t1 的公共事实相符。",
    "公开计划为同尺度销售额的百分比变化；没有实际 Final，不补全发布单位。",
)
family(
    "capitalized_interest_correct",
    [16, 46, 62, 82, 89, 105],
    "PPPPP",
    "(2018 - 2017) / 2017 * 100 适用于资本化利息增长，真实调用计算 (30.4 - 29) / 29 * 100。",
    "调用前完整说明资本化利息、2018 的 30.4 百万美元、2017 的 29.0 百万美元，与公共 p15 独立相符。Final 附带 t15n... 列表非规范且未解析，不改写为 p15、不将其认证为依据；判定依靠调用前财务事实说明，不新增 Final 引用格式硬门槛。",
    "两项均明确百万美元，比例尺度抵消，输出百分比。",
)
family(
    "other_long_term_share_correct",
    [19, 23, 25, 54, 80, 106],
    "PPPPP",
    "其他长期分类金额除以同年度未确认税收利益毛负债乘 100，适用于题目所问分类比例。",
    "调用前引用 q0 的 2012 其他长期负债 74360，并说明表内 2012 毛负债 180993；whole-cell t6c1 可由公开表及正文定位，不凭相同数值修复为别的来源。",
    "分子分母共同货币尺度抵消，乘 100 成百分比；只认证这一比例，不据未定义的绝对表尺度推断额外 USD 单位事实。",
)
family(
    "gross_change_wrong_million",
    [20, 53, 100],
    "PPFFP",
    "三次语法错误后真实 tool:4 执行 139549 - 201808；该净变化关系适用。",
    "当前修正调用和先前正文明确期末 2008-11-28、期初 2007-12-01 与对应金额；公共表提供独立事实依据。早期错误 n1 引用不认证。",
    "预先只有表上下文的 $，原表实际为千美元（公共 q0 约 139.5 百万美元核对）；Final 却声称 -62259 百万美元。不能从 Final 倒填工具的 million 尺度。",
)
family(
    "allowance_decline_correct_signed",
    [24, 43, 56, 66, 85],
    "PPPPP",
    "(2018 期末 34.3 - 期初 38.9) / 38.9 * 100 是该年度准备金下降的有符号变化，真实计算为负。",
    "调用前财务对象、年度和金额清楚，t4c1n0/t1c1n0 分别支持当前期末/期初，不用 2017 的 44 作为当前期初。",
    "公开两项为同尺度百万美元，百分比计算相消并乘 100；负数已经带方向，不再因 declined 一词重复取负。",
)
family(
    "restructuring_extra_cancelled_contract",
    [27, 31, 35, 44, 55, 81, 83, 92, 104],
    "FPPPP",
    "题目只问 severance 和 lease termination 余额，公开计划却把 cancelled contracts 0.4 也加入 0.3 + 0.1；多纳入财务组成部分，关系范围错误。",
    "公开说明的 0.3 遣散、0.1 租约终止、0.4 合同取消可分别由 q1 支持；只认证各事实对应，不认证把第三项纳入所问总额。Final 的 SEGMENT13 等未解析附带标记不替代这些公开事实。",
    "调用/尝试前明确三项以百万美元计，求和保留尺度。若实际 Final 缺少单位，仍不从这段历史补造发布单位。",
)
family(
    "deferred_assets_wrong_UTB_period",
    [30, 48],
    "PFPPP",
    "差额除以前期乘 100 是百分比变化形式；此项不认证操作数对象及时间区间。",
    "实际取 195237 和 180993 的 UTB 负债，且覆盖 2013 年初至 2014 年末，而非所问 2013/2014 DTA/监管资产调整 6241/6348；对象与期间均错。",
    "共同货币尺度相消，公开输出百分比。",
)
family(
    "classification_is_not_liability_change",
    [32, 99],
    "FFPPP",
    "把毛负债净增加 180993 - 158578 = 22415 等同于其他长期负债分类金额没有财务依据；分项应由 q0 分类披露支持。",
    "22415 未作为所问分类事实披露，输入映射还将它指向毛负债期末单元格、另一金额指向不存在的 n1；手写中间差额不是独立来源绑定。",
    "公开计划两金额之比乘 100 是百分比；单位抵消不能认证错误分类关系。",
)
family(
    "DTA_plan_correct_final_wrong_source_map",
    [34],
    "PFPNP",
    "公开计划使用 (6348 - 6241) / 6241 * 100，适用于公共 p22 的年度相关调整。",
    "Final 明确将两年调整金额对应到 t6c1 的 195237 UTB 负债单元格；这不是只有无效格式的附带列表，而是错误财务事实对应。",
    "公开计划为百分比，相同调整金额尺度抵消。",
)
family(
    "capitalized_interest_wrong_year",
    [37, 70],
    "PFPPP",
    "公开使用通常的跨年增长关系 (new - old) / old * 100，关系形式适用。",
    "把公共 p15 的 2016 年 33.7 百万美元误标为 2017；2017 实际披露为 29.0。不能因为 33.7 是真实数字而通过期间绑定。",
    "所用货币数额同尺度，相除乘 100 是百分比；不认证错配的期间。",
)
family(
    "expenses_equal_profit_true_profit_cell",
    [39, 52],
    "FPPFP",
    "错误把营业利润直接等同营业费用；营业费用需销售额减营业利润。",
    "当前声称使用的 1018 确实是 t2c1 的 2016 MFC 营业利润；此项只确认实际所用利润事实，不确认利润等于所问费用。",
    "公共 MFC 表与 Final 均为百万美元尺度。",
)
family(
    "decline_invalid_JSON_no_final",
    [40],
    "PFPNU",
    "明确计划以 (initial - final) / initial * 100 表示下降幅度，形式适用；未加引号的 389/10 等使 JSON 无法解析，未产生实际工具运算。",
    "期初声明指向年份表头 t0c1n0，不能支持准备金 38.9；SEGMENT13 未定位，不补造引用。",
    "公开计划为同币种准备金之比乘 100；没有实际 Final。",
)
family(
    "average_correct_prose_partial_header_list",
    [41],
    "PPPFP",
    "正确计划三年 MFC 营业利润相加除以 3；calculate 字段不是已执行工具。",
    "前置正文完整列出三年的利润 1344、1282、1018，与公共 t2 相符。Final 仅有表头 ID 列表，可支持年份但不能认证金额来源；它没有将具体金额错误映射到表头，不把它用作当前依据或新增格式门槛。",
    "公共 MFC 表和 Final 的量纲均为百万美元。",
)
family(
    "gross_percentage_correct_independent_prose",
    [45, 76, 93],
    "PPPPP",
    "真实调用用 (139549 - 201808) / 201808 * 100 或同一正确尺度转换后的两数，适用年度百分比变化。",
    "调用前明确毛负债、2007 期初/2008 期末和正确数额，独立匹配公共表。Final 附带不存在的 t0c1n1 等列表不修复、不认证；当前实际字面输入依赖前置财务事实，不以 Final 列表格式作为新增门槛。",
    "公共表千美元数或正确同时乘 1000 后的基础美元数，在百分比中尺度抵消；没有 false cents 声明。",
)
family(
    "decline_wrong_period_final_orientation_unknown",
    [47, 50, 57],
    "PFPNU",
    "公开计划为非负下降幅度 (initial - final) / initial * 100，形式本身适用；实际 Final 是否声明下降需单独检查。",
    "把 2017 期初 44 用作 2018 的期初，且来源表头/前一年度单元格与所声明金额、期间不相符；当前应依据 38.9 和 34.3。",
    "公开百分比关系尺度抵消；实际 Final 为正值但没有下降/减少说明，不从题目、sibling message 或参考答案给 Final 补方向。",
)
family(
    "sales_wrong_plan_direct_negative_Final",
    [49],
    "FPPNP",
    "公开所称增长式为 (2015 - 2016) / 2015 * 100，方向错误且未实际执行；不以最终负号修补这个计划。",
    "公开 2015/2016 销售额及来源 t1c1/t1c2 对应正确财务事实。",
    "Final 明确百分比，计划同尺度金额之比。",
)
family(
    "gross_percentage_invalid_tool_then_Final",
    [51, 67],
    "PPPNP",
    "公开比例关系正确，但对象值 tool 触发未知工具错误，没有实际成功计算。",
    "公开尝试列出正确毛负债、期间及 201808/139549，与公共表相符；不从结果数值单独反推来源。",
    "公开计划同尺度之比乘 100；只有实际 Final 自己给出的百分号可用于发布量，不能从 sibling 补全裸数单位。",
)
family(
    "interest_current_sources_wrong_obligations",
    [59],
    "PFPPP",
    "真实调用的 (30.4 - 29) / 29 * 100 适用于资本化利息百分比变化。",
    "当前 input.sources 把 new_value 指向 t1c5n0 的五年以上长期债务 1767383，把 old_value 指向 t2c5n0 的未来经营租赁 52626；这些是明确错误的现有财务事实，不因正文正确或变量未使用而被认证。",
    "正文给出两年百万美元，比例抵消，实际发布百分比。",
)
family(
    "average_correct_no_Final",
    [65],
    "PPPNU",
    "公开计划 1344、1282、1018 相加除以 3，适用于三年营业利润均值；所有 calculate 字段均未实际执行。",
    "公开期间、MFC 营业利润指标和三项数额与公共 t2 一致，没有相反金额来源声明。",
    "公共文档与问题给出百万美元平均量；没有实际 Final，不补造其单位。",
)
family(
    "gross_percentage_first_Final_wrong_input_ref",
    [69, 73],
    "PFPNP",
    "公开计划的期末减期初除期初乘 100 适用；同一响应先出现 Final，工具 sibling 不执行。",
    "明确计划/来源将期初指向不存在的 source:t0c1n1.value；不修复这个未成立的绑定。",
    "实际 Final 自身给出百分比，公共比例计划中共同尺度抵消。",
)
family(
    "classification_invalid_tool_conflicting_ratio",
    [74],
    "FFPNU",
    "虽有正确 74360/180993 正文，实际反复提交的对象值 tool 表达式却为 source:t6c1.value/source:t6c0.value，结构化比例与所问分类关系冲突。",
    "提交内容将 180993/118314 作为操作数，且 t6c0 为标签不是 118314 的金额事实；不能用正确正文覆盖当前冲突的绑定。",
    "公开计划为百分比；不补造没有生成的 Final。",
)
family(
    "sales_growth_correct_executed",
    [75, 98],
    "PPPPP",
    "真实调用计算 (6608 - 6770) / 6770 * 100，符合净销售额 2015 至 2016 的有符号增长。",
    "调用前明确 MFC 净销售额与 2016/2015 两年数额，公共 t1c1/t1c2 支持，未引入相反当前绑定。",
    "公共同尺度销售额在比例中抵消，公开式乘 100，Final 明确负百分比。",
)
family(
    "shares_first_Final_suppresses_planned_sum",
    [86, 97],
    "PFPNP",
    "公开同响应明确计划 0.6 + 0.7，求两年回购股数总量的关系适用；第一 Final 优先，旁边的工具并未实际执行。",
    "当前明确把 0.6/0.7 股数指向 q5n2/q5n3 的美元成本 45/54，而非 q5n0/q5n1 股数。",
    "公开计划及实际 Final 都明确百万股，不是百万美元。",
)
family(
    "average_correct_sources_pseudo_result",
    [90],
    "PPPFP",
    "公开三年 MFC 营业利润平均式适用，但 calculate 字段未构成实际调用。",
    "前置正文的 2014/2015/2016 利润金额 1344/1282/1018 与 t2 相符，Final whole-cell 列表也指利润行；不从错误 Final 数值反推公式已执行。",
    "公开表和 Final 的尺度为百万美元，平均保持该尺度。",
)

assert set(ASSIGNMENTS) == set(range(1, 109))
OVERRIDES = {
    17: "PFPFP",
    60: "PFPFP",
    31: "FFPPP",
    44: "FPPNU",
    92: "FPPNU",
    104: "FPPNU",
    50: "PFPUU",
    57: "PFPUU",
    58: "FFPFP",
    96: "FFPFP",
    67: "PPPNU",
}
EXTRACTED_PUBLICATIONS = {
    7: ("41.43%", "percent"),
    28: ("41.43%", "percent"),
    44: ("0.8", None),
    51: ("-30.85%", "percent"),
    67: ("-30.85", None),
    69: ("-30.0%", "percent"),
    88: ("41.43%", "percent"),
    92: ("3.8", None),
    104: ("1.8", None),
}
SECONDARIES = {}


def secondary(cases, value, unit, direction):
    for index in cases:
        assert index not in SECONDARIES
        SECONDARIES[index] = (value, unit, direction)


secondary([6, 26, 63, 94, 101], "41.43%", "percent", 1)
secondary([19, 25, 54], "41.08%", "percent", 1)
secondary([24, 43, 56, 66, 85], "-11.83%", "percent", 1)
secondary([13], "2.39%", "percent", 1)
secondary([32, 99], "12.38%", "percent", 1)
secondary([37, 70], "-9.79%", "percent", 1)
secondary([45, 76, 93], "30.85%", "percent", -1)
secondary([48], "7.87%", "percent", 1)
secondary([50, 57], "22.05%", "percent", None)
secondary([53, 100], "62,259", "USD_million", -1)
secondary([73], "-30.0", "percent", 1)


def actual_final_span(raw):
    """Return an exact raw substring, never reserialize or include sibling fields."""
    decoder = json.JSONDecoder(parse_int=str, parse_float=str)
    whole = json.loads(raw, parse_int=str, parse_float=str)
    candidates = []
    for match in re.finditer(r'"final"\s*:\s*', raw):
        value, end = decoder.raw_decode(raw[match.end() :])
        if value == whole["final"]:
            candidates.append(raw[match.end() : match.end() + end])
    assert len(candidates) == 1
    return candidates[0]


def evidence(packet, indices):
    seen, result = set(), []
    for index in indices:
        raw = packet["raw_messages"][str(index)]
        if raw not in seen:
            result.append({"response_index": index, "quote": raw})
            seen.add(raw)
    return result


def build():
    target = OUTPUT / "analysis/dev_review_transcription/reviews.json"
    assert not target.exists(), "single transcription; no score-driven re-review"
    templates = json.loads((OUTPUT / "assessment/dev/review_template.json").read_bytes())
    reviews, public_refs, checked_fields = {}, {}, 0
    for index in range(1, 109):
        rid = f"dev_{index:03d}"
        path = OUTPUT / "assessment/dev/public_review_packets" / (rid + ".json")
        raw_packet = path.read_bytes()
        packet = json.loads(raw_packet)
        public_refs[rid] = sha(raw_packet)
        review = copy.deepcopy(templates[rid])
        family_name, default = ASSIGNMENTS[index]
        states = OVERRIDES.get(index, default)
        first_final = packet["first_final_index"]
        calculations = packet["calculations"]
        assert len(calculations) <= 1, "all 108 actual packets were individually read"
        selected = calculations[0] if calculations else None
        raw_messages = {int(k): v for k, v in packet["raw_messages"].items()}
        if selected:
            pre_evidence = evidence(packet, sorted({0, selected["response_index"]}))
        else:
            pre_evidence = evidence(packet, sorted(raw_messages))
        final_evidence = (
            []
            if first_final is None
            else [
                {
                    "response_index": first_final,
                    "quote": actual_final_span(raw_messages[first_final]),
                }
            ]
        )
        review["author"] = "Codex assistant; explicit masked offline review; not independent expert"
        review["condition_inferred_from_self_description"] = False
        review["review_case_family"] = family_name
        for position, field in enumerate(FIELDS):
            review[field]["status"] = STATUS[states[position]]
            review[field]["evidence"] = copy.deepcopy(
                final_evidence if position == 4 else pre_evidence
            )
            if position < 3:
                review[field]["explanation"] = DESCRIPTIONS[family_name][position]
        if index == 31:
            review["variable_correspondence"]["explanation"] = (
                "虽然前置正文列出 q1 的三项金额，实际 Final 又明确把 0.3/0.1/0.4 映射到 "
                "t1c2n0/t1c3n0/t1c4n0 的计提、现金支出和调整金额，属于相反的具体事实绑定，不是仅有非规范附带列表。"
            )
            review["variable_correspondence"]["evidence"] += final_evidence
        if index in {1, 15, 17, 29, 34, 60, 71}:
            review["variable_correspondence"]["evidence"] += final_evidence

        publication = review["publication"]
        if index in EXTRACTED_PUBLICATIONS:
            assert publication["value"] is None and publication["unit"] is None
            publication["value"], publication["unit"] = EXTRACTED_PUBLICATIONS[index]
        publication["direction_multiplier"] = (
            None if first_final is None or index in {47, 50, 57} else 1
        )
        publication["evidence"] = final_evidence
        publication["explanation"] = (
            "没有实际 Final；数值、单位与方向均不从工具、先前消息、问题或参考答案补造。"
            if first_final is None
            else "保留实际第一 Final 的原始 value/unit 字段及词法精度；缺字段时仅提取该 Final 自身的明确数值/单位。负数字面值按有符号变化解释一次。"
        )
        if index in {47, 50, 57}:
            publication["explanation"] += (
                " 此 Final 正值没有下降/减少说明，方向未定；不从 sibling message 或问题推断下降幅度。"
            )
        if index in {44, 67, 92, 104}:
            publication["explanation"] += " 实际 Final 为无单位裸数，单位保持未定。"
        calc = review["calculation"]
        if selected:
            unit = "percent"
            if packet["task_key"] == "D01":
                unit = "USD_thousand" if index in {20, 53, 100} else "USD"
            elif packet["task_key"] == "D05":
                unit = "USD_million"
            calc.update(
                call_id=selected["call_id"],
                unit=unit,
                direction_multiplier=-1 if index in {50, 57} else 1,
                evidence=copy.deepcopy(pre_evidence),
                explanation="选择唯一真实成功计算，并使用调用前/同调用的公开财务尺度和方向；不从 Final 或参考结果补造计算。",
            )
            if packet["task_key"] == "D01":
                calc["explanation"] += (
                    " 表中千美元尺度由公开 q0 的约 139.5 百万美元核对；预先 $ 未明确声称 million。"
                    if unit == "USD_thousand"
                    else " USD 是模型预先明确宣称的基础美元解释，仅用于诊断其过程对齐；unit_handling=FAIL 已记录该声明与公共表千美元尺度不符。"
                )
        else:
            calc["explanation"] = (
                "没有实际成功计算；未把 calculate 字段、对象值 tool、同第一 Final 的工具 sibling 或虚构结果引用当作执行。"
            )

        p_status = review["publication_alignment"]["status"]
        review["publication_alignment"]["evidence"] = copy.deepcopy(pre_evidence + final_evidence)
        review["publication_alignment"]["explanation"] = {
            "PASS": "实际选定工具结果与该 Final 发布量在公开单位、方向及其显示精度下对齐；这只认证实际过程连接，不替代财务对象/公式/数量正确性。",
            "FAIL": "不存在与实际 Final result_id 对应的真实成功工具结果；不把模型自造的 calculate:... 当作执行证据。",
            "UNDETERMINED": "虽然实际工具产生公开说明的下降幅度，Final 未明确方向，无法认证有符号发布量与工具结果一致。",
            "NOT_ESTABLISHED": "未发生可与 Final 连接的真实成功计算；无伪造结果承诺时记未建立，不据此宣称已证实金融答案错误。",
        }[p_status]
        if index in {20, 53, 100}:
            review["publication_alignment"]["explanation"] = (
                "实际工具输出的源金额尺度为千美元，而 Final 明确为百万美元；同一个 -62259 不能证明数量尺度一致。"
            )
        c_status = review["final_answer_consistency"]["status"]
        review["final_answer_consistency"]["explanation"] = (
            "实际第一 Final 给出单一明确的数值、单位和答题范围，没有互相竞争的最终量；其参考数值是否正确由冻结数量评价单独判断，当前其他财务错误保留在对应语义字段。"
            if c_status == "PASS"
            else "没有实际 Final，或其自身缺少可确定的单位/下降方向；不从 sibling message、工具结果或问题补全。"
        )
        if index in {24, 43, 56, 66, 85}:
            review["final_answer_consistency"]["explanation"] += (
                " 对 declined by -11.83% 的冗余措辞按已经带负号的有符号变化解释一次，不二次取负；这是明确披露的离线解释判断。"
            )
        if index in SECONDARIES:
            value, unit, direction = SECONDARIES[index]
            review["secondary"] = [
                {
                    "value": value,
                    "unit": unit,
                    "direction_multiplier": direction,
                    "evidence": copy.deepcopy(final_evidence),
                    "explanation": "该数值确实来自实际 Final 内的另一个最终答案显示，不是等式操作数或 sibling。保留自身精度；正的减少幅度仅在该 Final 有明确减少措辞时取 -1，已有负号不重复取负。",
                }
            ]
        route = review["route_observation"]
        route["evidence"] = copy.deepcopy(pre_evidence)
        route["description"] = (
            f"公开路线观察 {family_name}；真实成功计算 {len(calculations)} 次。"
            "上述财务对象/来源及协议判断不代表训练臂、来源类 Contribution 或受益效用；"
            "合法 message、未知工具、语法/JSON 错误和第一 Final 抑制的 sibling 均保留原记录，不重放。"
        )
        # Validation has no target or arm input and produces no financial grades.
        _evidence(review, raw_messages)
        audit_subset = {"raw_messages": packet["raw_messages"], "first_final_index": first_final}
        assert not final_evidence or all(e["response_index"] == first_final for e in final_evidence)
        final_lexical = (
            None
            if first_final is None
            else json.loads(raw_messages[first_final], parse_int=str, parse_float=str)["final"]
        )
        if isinstance(final_lexical, dict):
            for key in ("value", "unit"):
                if key in final_lexical:
                    assert publication[key] == final_lexical[key]
                    assert type(publication[key]) is type(final_lexical[key])
        for quantity in [publication, *review["secondary"]]:
            expected_clear = all(
                quantity[key] is not None for key in ("value", "unit", "direction_multiplier")
            )
            assert _quantity_evidence(quantity, audit_subset) == expected_clear, (rid, quantity)
        if selected:
            assert _quantity_evidence(
                {**calc, "value": selected["actual_exact_value"]},
                audit_subset,
                calculation=selected,
            )
        checked_fields += len(FIELDS)
        reviews[rid] = review
    store = DurableStore(OUTPUT / "analysis/dev_review_transcription")
    store.json("reviews.json", reviews)
    store.json(
        "provenance.json",
        {
            "reviewer": "same Codex assistant; not independent expert",
            "reviewed_original_masked_packets": 108,
            "all_generated_public_strings_and_every_event_occurrence_read": True,
            "all_twelve_public_source_documents_read": True,
            "masked_packet_sha256": public_refs,
            "semantic_field_count": checked_fields,
            "identity_map_training_NLL_and_per_arm_utilities_read_before_review": False,
            "progress_metadata_exposure": (
                "Training monitoring exposed worker identities and completion progress. In one read-only "
                "filename check before masked review, pi0_11/D12 was seen to reach response index 031. "
                "No response text, financial score, identity map, or per-arm utility was read then. "
                "Episode length could permit inference, so this is partial masking, not full blindness."
            ),
            "explicit_arm_or_seed_inferred_from_model_self_description": False,
            "judgment_notes": [
                "No numeric-ID-only or Final-source-list format gate was added. Complete pre/same-call financial metric, period, and quantity descriptions can ground literal inputs independently.",
                "Explicit current amount-to-wrong-existing-fact mappings are failures even when unconsumed variables or correct prose contain the expected literal numbers.",
                "Ancillary unresolved Final locator lists were not corrected or certified; the actual independent source evidence and limitations are described case by case.",
                "A negative lexical value with redundant declined wording is interpreted once; a positive ambiguous decline Final without its own directional wording stays undetermined.",
                "Frozen evaluation source, tool runtime, tolerance, class IDs, training configurations, and panels remain unchanged. This script transcribes judgments, not a new evaluation rule.",
            ],
            "source_code_changed": False,
            "Teacher_requests": 0,
            "Student_generation": 0,
            "financial_qualification_calls": 0,
            "group_or_arm_scores_computed": 0,
        },
    )
    print(
        json.dumps(
            {
                "reviews": len(reviews),
                "semantic_fields": checked_fields,
                "reviews_sha256": sha(target.read_bytes()),
                "no_identity_or_financial_grade_read": True,
            }
        )
    )


if __name__ == "__main__":
    build()
