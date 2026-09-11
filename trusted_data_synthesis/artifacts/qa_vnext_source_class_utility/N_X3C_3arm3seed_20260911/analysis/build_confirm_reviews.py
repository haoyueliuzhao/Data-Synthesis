"""Transcribe all 144 individually read, masked confirmation judgments.

This is a post-generation artifact writer, not a new evaluator or a classifier.
Every case assignment was decided from the complete public packet before any
confirmation identity map, private financial target, or per-arm result was read.
No frozen source file is changed and no prior review is rerun.
"""

# ruff: noqa: E501 -- multilingual review statements are data, kept readable.

import copy
import json
from pathlib import Path

from build_dev_reviews import actual_final_span, evidence

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.plan import sha
from trusted_synthesis.experiments.finance_qa_vnext_source_class_utility.student_review import (
    FIELDS,
    _evidence,
    _quantity_evidence,
)

OUTPUT = Path(__file__).resolve().parents[1]
STATUS = {"P": "PASS", "F": "FAIL", "U": "UNDETERMINED", "N": "NOT_ESTABLISHED"}
CASES = {}
DESCRIPTIONS = {}


def family(name, indices, states, formula, variables, units):
    assert len(states) == 5
    DESCRIPTIONS[name] = (formula, variables, units)
    for index in indices:
        assert index not in CASES, index
        CASES[index] = (name, states)


family(
    "coal_period_aggregate",
    [1, 25, 31, 40, 112, 143],
    "PPPPP",
    "三年煤炭收入之和除以同三年营业收入总和再乘 100，适用于期间总量的占比；不以年度比例的非加权均值代替。",
    "公开 2014–2016 煤炭 4127/3237/2440 与营业总收入 23988/21813/19941 对应正确的 t4/t9 单元格，分母包含其他收入，不是仅货运收入。",
    "两组金额均为百万美元，共同尺度相消，乘 100 后为百分比；命名变量的实际消费情况另外保留。",
)
family(
    "rent_future_payments_false_USD",
    [2, 13, 45, 51, 118, 132, 139],
    "PFFPP",
    "公开的新值减旧值、除旧值乘 100 是百分比变化形式；此项不认证所选对象和期间。",
    "538405 与 519034 是公共表 2017/2018 的未来租赁付款，不是问题所问 2012/2013 或 2013/2014 的历史 aggregate rent expense；q0 才披露 419.0/495.2/655.0 百万美元。",
    "模型明确把表内数额标为 USD，但表前 p11 明确为 thousands；没有正确尺度转换。比例数值抵消不使该明确错误的绝对单位声明成立。",
)
family(
    "UTB_wrong_beginning_years_and_direction",
    [3, 12, 74, 99, 135, 141],
    "FFPPP",
    "使用 4919 - 4277 的旧值减新值正数称作跨年 change，实际 Final 未声明下降幅度；不由参考答案反转符号。",
    "4919/4277 是 2011/2012 期初数，而问题的年度比较需对应年末 4277/4425；部分 Final 还把 change/original_value 对应到不相符的事实。未执行的 JSON 算式不补造成计算。",
    "公开计划为同货币尺度之比乘 100；没有显式错误的基础美元单位转换声明。",
)
family(
    "Danvers_earlier_base_bad_current_source_map",
    [4, 39, 68, 88, 90, 124],
    "PFPPP",
    "64350 相对 40000 的增长式适用于所问两段 Danvers 月度基本租金变化。",
    "当前 arguments.sources 明确把 new_value/original_value 绑定到不存在的 t16c1n0、t17n0 或 t17n3。正确财务正文和未消费的字面变量不能认证这个当前虚假来源断言；不将 t... 偷改成 p17。",
    "公开两项均为美元/月，同单位相消并乘 100，实际 Final 明确百分比。",
)
family(
    "final_allocation_liability_sum",
    [5, 7, 20, 50, 65, 72],
    "PPPPP",
    "按最终购买价分配表的有符号负债贡献，将 current liabilities 与 other non-current liabilities 相加，关系适用。",
    "当前使用 t5c1 的 -5536 与 t6c1 的 -38519，分别是真实最终分配的流动与非流动负债；正确 whole-cell 定位同样可由公共表核对，不添加 numeric-ID-only 门槛。",
    "公共 p3 将此分配表明确为千美元；同尺度求和，实际 Final 为 thousand dollars，负号按原分配列示保留。",
)
family(
    "Danvers_later_base_independent_pre_call_proof",
    [6, 59, 94, 106, 111, 120],
    "PPPPP",
    "(66000 - 64350) / 64350 * 100 适用于两段 Danvers 月度基本租金增长。",
    "调用前完整说明 Danvers、2010–2014 的 64350 美元/月和 2014–2016 的 66000 美元/月，与公共 p17 独立相符；当前输入没有相反的来源映射。Final 附带的未解析或无关来源列表不修复、不认证，也不作为这两个事实的依据。",
    "美元/月的共同单位相消，表达式乘 100，发布百分比；不从 Final 的工具 sibling 补造第二次执行。",
)
family(
    "outstanding_shares_correct_repaired_call",
    [8, 27, 119],
    "PPPPP",
    "2018 年末 outstanding shares 减 2016 年末 outstanding shares，适用于模型明确说明的年末比较。",
    "两次语法失败后，当前真实调用放弃旧 SEGMENT 映射，采用 1220 - 1217；此前/同调用的财务对象及年度与公共 t7c3/t3c3 相符。失败提案的映射和 Final 辅助列表均不被修复或认证。",
    "公共表与调用前说明均为百万股，实际 Final 明确 millions of shares，不解释为货币。",
)
family(
    "employee_separation_wrong_period",
    [9, 69, 82, 102, 137],
    "PFPPP",
    "当前重复或最终执行的 end - beginning 是净变化形式；不因为期间错误而把这种算术形式也称为错误。",
    "实际当前计划使用 2004 年初 2239，以及 2004 年末 665 或 2005 年末 301，覆盖 2004 或两年区间，而不是仅 2005 的 301 - 665；初始反向提案与未解析标识也不认证。",
    "公共 p15 明确表内金额为千美元，所选金额虽期间不适用，仍为同一货币尺度；没有 Final 时不补造发布单位。",
)
family(
    "ARO_2002_2004_difference",
    [10, 46, 73, 107, 114, 126],
    "PPPPP",
    "2004-09-25 的资产退休负债减 2002 期末余额，即 8.2 - 5.5，关系适用。",
    "调用前明确资产退休负债、2002 的 5.5 和 2004 的 8.2，可分别由公共 t0c1/t6c1 核对；当前有效来源声明另按每例说明。",
    "公共 p0 明确为百万美元，差额保留该尺度，实际 Final 为 million dollars 或 millions。",
)
family(
    "total_sales_2013_growth",
    [11, 56, 81, 85, 93, 121],
    "PPPPP",
    "(2013 总销售额 - 2012 总销售额) / 2012 总销售额 * 100 适用于 2013 年增长率。",
    "公开调用前明确 2013 的 44033 与 2012 的 47267，财务对象为总销售额而非单个产品或药品部门；额外列出的真实 2011 数未作为当前操作数。",
    "两项为同尺度百万美元，比例相消并乘 100；负增长值已经带方向，不再二次取负。",
)
family(
    "capital_principal_wrong_single_lease",
    [14, 19, 101, 109],
    "FPPNU",
    "把单份 44 台机车租赁的设备成本等同于全部资本租赁本金，属于分项代替总体的错误财务等式。",
    "所引用的 100 百万美元确实是公共 p2 的那份机车租赁成本；只确认这一被实际使用的分项事实，不认证它等于所问全部本金。",
    "正文的百万美元尺度与该分项原文一致；实际 Final 只有裸 100，不能从正文或问题补全其单位。",
)
family(
    "goodwill_2016_2017_total",
    [15, 42, 64, 77, 100, 117],
    "PPPPP",
    "(7167.1 - 6383) / 6383 * 100 适用于 2016 至 2017 总商誉账面金额的变化。",
    "调用前的总商誉、两年期间和金额与公共 t8c5/t13c5 相符，不误用某个分部或 2015 基数；Final 列表中未消费的 2015 真实事实不当作额外计算。",
    "公共表金额为百万美元，共同单位在比例中相消，发布百分比。",
)
family(
    "sales_wrong_2013_period_ratio_as_percent",
    [16, 30, 33, 63, 133],
    "PFFFP",
    "(new - old) / old 是增长比例形式，比例本身可以合法表达增长；问题在期间及后续百分比发布。",
    "实际使用 2013 的 44033 与 2012 的 47267，未计算所问 2012 相对 2011 的变化。",
    "真实表达式没有乘 100，输出为 ratio；却把 -0.0684 原样标成百分比，造成 100 倍尺度差。不能从 sibling 的 -6.84% 改写主字段。",
)
family(
    "cash_2016_operating_is_not_net_pseudo",
    [17, 62, 79, 84, 142],
    "FPPFP",
    "把单独经营活动现金流 262 直接当作净现金变化，遗漏投资与筹资活动，财务等式错误。",
    "262 确为 t1c2 的 2016 经营活动现金流，公开正文正确命名这一分项；不因此认证其等于总净变化。",
    "公共现金流表和实际 Final 为百万美元，尺度一致，但不证明所问总体金额正确。",
)
family(
    "goodwill_2015_2017_total",
    [18, 35, 76, 86, 103, 129],
    "PPPPP",
    "2017 总商誉相对 2015 的差额除以 2015 基数乘 100，关系适用。",
    "公共 t13c5 的 7167.1 和 t1c5 的 6490.8 与调用前的总商誉及年末期间一致；以实际当前调用为准，不认证已经放弃的失败提案辅助映射。",
    "公开两项为同尺度百万美元，比例相消再乘 100，实际 Final 为百分比。",
)
family(
    "capital_principal_wrong_including_interest",
    [21, 37],
    "FPPNP",
    "2975 是包含利息的租赁付款总额，不是 principal only；未排除 q2 的 914 利息。",
    "2975 确为当前明确引用 t3c1 的资本租赁总额；分项事实定位正确不认证错误的本金等式。",
    "公共表和实际 Final 均为百万美元。",
)
family(
    "capital_2020_pseudo_17_25",
    [22, 55, 92],
    "PPPNP",
    "2020 资本租赁付款 155 除以总最低付款 898 再乘 100，是适用的期间占比关系。",
    "当前公开年度、资本租赁列及 155/898 分别对应 t2c2/t7c2，未使用经营租赁或扣息后的现值作分母。",
    "两项均百万美元，比例相消，发布百分比；原主值 17.25 的准确性按其原显示精度单独判断。",
)
family(
    "employee_change_reversed_bad_day_source_base_USD",
    [23, 32, 34],
    "FFFFP",
    "20963 - 7327 是旧余额减新余额，实际 Final 又没有声明下降幅度；不能作为有符号净变化直接通过。",
    "当前把 20963 对应到 source:t0c1n0，而公共索引核对该事实为日期中的 31；真正金额为 n2。这个错误日数字—金额映射不因字面算术相等而成立。",
    "公共 p15 为千美元，前置 $ 处于该表上下文；Final 却明确发布基础美元 $13636，尺度不符。",
)
family(
    "contingent_upper_range_mixed_conversion",
    [24],
    "FFFUP",
    "实际表达式向金额加入负 FX，而移除负 FX 应取相反作用；还把潜在范围上限当作所问实际余额。",
    "实际使用 p2 的潜在付款上限 40.4，而不是 t7c1 的年末实际余额；FX 是另一真实事实，不使上限替代余额成立。",
    "乘 1000000 的转换与 -4934（源表为千美元、模型又标 million）的混用没有建立一致财务尺度；实际算术存在，但计算结果单位保持未定，不由 Final 的 million 倒填。",
)
family(
    "capital_2020_pseudo_wrong_high_precision",
    [26, 130],
    "PPPFP",
    "公开计划 155 / 898 * 100 的关系适用，但 calculate 字段不是实际工具执行。",
    "当前公开资本租赁 2020 金额和总最低付款的来源、期间及 155/898 相符。",
    "比例相消后为百分比；保留原始高精度主字段，不将主容差上限 0.005 当成所有精度的统一容差，也不用四舍五入的副答案替换主值。",
)
family(
    "rent_future_payments_ratio_without_false_base_unit",
    [28, 48, 52, 91, 144],
    "PFPPP",
    "通常的新值减旧值除旧值乘 100 形式适用；不认证其中的财务对象和期间。",
    "当前实际或计划使用 2017/2018 未来租赁付款 538405/519034，而不是所问历史 aggregate rent expense；清空来源字典并不能改变实际操作数的财务意义。",
    "使用同一表尺度的比值，或明确千美元后求比例，没有虚假的 ISO USD 基础尺度声明；发布缺单位时仍不从计划补全。",
)
family(
    "cash_2015_invented_two_stock_endpoints",
    [29, 43, 115],
    "PFPPP",
    "期末现金存量减期初现金存量这一净变化形式本身成立。",
    "把同一经营活动现金流 1277 同时称作期初和期末现金存量，没有公共来源支持；正确的存量差形式不能认证虚构的两个存量事实。",
    "模型调用前明确采用百万美元，原表中所误用的现金流也为百万美元；单位相符不证明财务对象相符。",
)
family(
    "outstanding_shares_mislabels_beginning_as_end",
    [36, 44, 140],
    "PFPPP",
    "模型声明比较 2018 与 2016 年末 outstanding shares，年末差这一关系形式适用。",
    "实际把 Jan 3, 2016 的 1214 说成 2016 年末；2016 年末是 t3c3 的 1217。此错误由模型自己明确的 end of 2016 声明及公共表确定，不依靠参考答案选期间。",
    "实际调用前与 Final 明确百万股，差额保留股数尺度。",
)
family(
    "capital_2021_pseudo_fake_result",
    [38],
    "PPPFP",
    "159 / 898 * 100 适用于 2021 资本租赁最低付款占比。",
    "公开 2021 付款、总最低付款及 t3c2/t7c2 的财务对象和数额相符。",
    "两项同尺度百万美元，相除乘 100，实际 Final 明确百分比。",
)
family(
    "cash_2015_operating_identity_after_header_read",
    [47, 54, 108],
    "FPPPP",
    "把经营活动现金流 1277 当作全部净现金变化，遗漏另外两类现金流，财务等式错误。",
    "当前正文命名的 2015 经营活动现金流 1277 可由原始公共 t1c3 独立核对；read_source 实际只返回表头年份 2015，不能声称它证明了 1277。持久化错误的当前来源属性按个案另外判失败。",
    "调用前说明及原公共现金流表为百万美元，真实常量计算的这一单位可确定；零算术操作的常量计算仍是真实调用。",
)
family(
    "cash_2016_financing_is_not_net",
    [49],
    "FPPPP",
    "把单独筹资现金流 -102 当作全部净现金变化，财务总体等式错误。",
    "调用前完整命名 2016 筹资活动 -102，真实分项在公共 t3c2；Final 辅助列表的经营现金流 t1c2 不认证、不用作该输入依据。这里只确认实际使用分项的独立前置来源，不认证其等于净额。",
    "原表、调用前解释和 Final 都为百万美元；主字段已为负，不因 decrease 一词重复取负。",
)
family(
    "contingent_correct_removal_wrong_claimed_millions",
    [53, 61, 78, 113, 131],
    "PPFPP",
    "移除 -4934 的 FX 对实际年末余额 28524 的影响，需要加回 4934；公开调用前明确说明这一反向作用。",
    "余额来自 t7c1，负 FX 来自 t5c1；取正的 4934 是调用前明说的反向移除，不是声称原负事实等于正数。提及的潜在 40.4 上限没有进入实际表达式。",
    "两项源表金额均为千美元，模型却都明确标 million，Final 也发布 33458 million，存在 1000 倍财务尺度错误。计算/发布对齐仅按模型自称的同一错误 million 单位作诊断，不认证源表尺度。",
)
family(
    "employee_change_reversed_correct_thousand_scale",
    [57, 58, 96],
    "FPPPP",
    "公开计算是旧余额减新余额，Final 没有下降幅度说明，却直接发布正净变化；方向不适用，不从参考结果倒推负号。",
    "当前明确的 2005/2006 员工离职负债余额 20963/7327 与公共表相符，没有将金额指向日数字的具体错误映射；错的是上述变化方向。",
    "源表千美元、Final 的 USD thousands 与其补充基础美元金额转换一致；Actual Final 内解释式的两个操作数不当作竞争答案。",
)
family(
    "rent_three_year_wrong_future_values_pseudo",
    [60, 66, 87],
    "PFPFP",
    "三个财政年度的租金费用相加这一总量形式适用；同一第一 Final 旁的工具不会实际执行。",
    "把未来租赁付款 758 和错误期间的 2700/2200 说成 2010–2012 租金费用；具体源映射还把 2700/2200 指向未来 128/4218，真实历史费用在 p26。",
    "公开基础美元到千美元的表示在各项间一致，Final 为 thousand dollars；财务对象和期间错误不自动变成单位错误。",
)
family(
    "RSU_wrong_group_percentage",
    [67, 125],
    "FFPPP",
    "以全体管理层持股乘其集团占公司比例推断 Oppenheimer 归属后股份，既没有按现有股份加其未归属 RSU，也没有成立的财务等式。",
    "9378423 与 1.09% 是管理层集团持股及其公司持股比例，不是 Oppenheimer RSU 占集团比例；公共脚注另有其 450000 未归属 RSU。",
    "109/10000 对应 1.09% 的无量纲比例，乘股数结果仍是 shares；单位代数不认证错误的集团/个人关系，不新增整数股数硬门槛。",
)
family(
    "rent_wrong_future_values_conflicting_million_prose",
    [70, 89],
    "PFFPF",
    "三个年度租金费用求和这一形式适用。",
    "实际输入 758/2700/2200 使用错误未来租赁事实和期间映射，不是 p26 的历史年度租金费用。",
    "调用和主字段为 5658 thousand dollars，但同一 Final 的答案文字为 $5,658,000 million，相差百万倍；不能删除 million 字样来制造一致。",
)
family(
    "sales_wrong_year_pseudo_percent",
    [83],
    "PFPFP",
    "公开计划为通常的 (new - old) / old * 100 百分比增长形式。",
    "计划比较 2013 与 2012，未计算所问 2012 相对 2011 的增长；来源单元格真实不使目标期间成立。",
    "公开式已经乘 100，金额共同尺度抵消，Final 明确百分比；不补造未发生的计算。",
)
family(
    "capital_percent_no_Final_pseudo_only",
    [80, 95, 98, 110],
    "PPPNU",
    "当年最低资本租赁付款除以全部最低付款再乘 100，公开计划关系适用。",
    "公开 2021 的 159 或 2020 的 155 与总额 898，对应当前题的资本租赁列和期间；不是经营租赁或现值。",
    "两项同尺度百万美元在比值中相消；没有实际 Final，不补造其数量或单位。",
)
family(
    "RSU_wrong_person_options_empty_Final_unit",
    [97],
    "PFPNU",
    "已有股数加新增股份是总持股的加法结构；此项不认证选项权就是题目的 RSU。",
    "120000 的 q47/q48 事实属于 Jobs 的股票期权，而不是 Oppenheimer 的未归属 RSU；错误人物和工具类型由公开原文确定。",
    "公开计划两项都是股数，维度可相加；实际 Final 的 unit 是空字符串且其答案没有单位，不从前文或问题填成 shares。",
)
family(
    "employee_first_Final_reversed_empty_unit",
    [105],
    "FFPNU",
    "当前提案是 665 - 301，旧余额减新余额，Final 也没有下降幅度说明；其净变化方向不适用。",
    "正文的 January 1, 2004 基期声明与实际指向的 December 31, 2004 单元格冲突，不能认证该当前期间对应。",
    "公开表中的货币金额为同一千美元尺度，但 Final 明确空 unit，不能把表内单位写入这个原字段。",
)
family(
    "capital_2021_pseudo_without_fake_reference",
    [116, 134],
    "PPPNP",
    "159 / 898 * 100 的 2021 占比关系适用，calculate 字段本身不是工具调用。",
    "当前题的 2021 资本租赁付款和总最低付款来源、期间及数额一致。",
    "同尺度百万美元相消，实际 Final 为百分比。",
)
family(
    "rent_other_future_values_K_to_M",
    [123],
    "PFFFF",
    "三个财政年度费用相加这一形式适用。",
    "758/863/32 是未来 2016/2015/2017 租赁付款，却被称为历史 2010/2011/2012 租金费用，财务对象与期间不符。",
    "当前实际计算明确千美元，但 Final 主字段为 1653 million dollars；补充文字又说 $1,653,000,000 in millions。保留尾随 in millions 的显示单位限定，不删除它来凑成一致。",
)
family(
    "RSU_group_residual_and_rounded_Final",
    [127],
    "FFPFP",
    "以个人现有股份加整个集团股份，再扣集团比例推断个人 RSU 归属总量，是没有成立依据的财务组合。",
    "集团 9378423 与其 1.09% 公司持股比例不对应个人 RSU；当前把 109/10000 指向不存在或不相符的百分比原子，也不认证。",
    "公开股数加减股数乘无量纲比例，结果维度仍为 shares；实际第一 Final 是单独的股数字符串，不从失败 tool:final 请求或 sibling 补回更精确数值。",
)
family(
    "RSU_person_plus_group_false_total",
    [128, 138],
    "FPPPP",
    "把个人当前股数与包含该个人的整个集团持股相加，不能表示个人 RSU 归属后持股，存在错误总体组合和重复包含。",
    "实际明确命名的个人 149768 与集团 9378423 本身可由公共 t9c1/t13c1 核对；只认证这两个被使用事实，不认证它们的错误组合关系。",
    "两项都是公开股数，可确定真实加法结果的 shares 维度；原 Final 的空单位若存在，仍保持空，不由文字替换主字段。",
)

family(
    "UTB_2007_2008_signed_percentage",
    [41, 71, 75, 104, 122, 136],
    "PPPPP",
    "(168 - 224) / 224 * 100 适用于所问年度未确认税收利益余额的有符号百分比变化。",
    "调用前明确 April 1, 2007 的 224 与 March 31, 2008 的 168 及其未确认税收利益对象，可由公共 t0c1/t2c1 独立核对；不以其他年度、含利息金额或金融对象替换。",
    "源表的共同千美元尺度在比值中相消，表达式乘 100；实际 Final 自身明确 -25%，不从工具补造 Final 单位或数值。",
)

assert set(CASES) == set(range(1, 145)), sorted(set(range(1, 145)) - set(CASES))

OVERRIDES = {
    1: "PPPFP",
    25: "PPPNP",
    13: "PFFNU",
    45: "PFFNU",
    118: "PFFNU",
    132: "PFFNU",
    139: "PFFNU",
    3: "FFPNU",
    99: "FFPNP",
    141: "FFPNP",
    9: "PFPNU",
    69: "PFPNU",
    102: "PFPNU",
    137: "PFPNU",
    126: "PFPPP",
    63: "PFFFF",
    91: "PFPNU",
    144: "PFPNP",
    54: "FFPPP",
    108: "FFPPP",
    66: "PFPNP",
    128: "FPPUP",
}
EXTRACTED = {}


def extracted(indices, value, unit):
    for index in indices:
        assert index not in EXTRACTED
        EXTRACTED[index] = (value, unit)


extracted([14, 19, 101, 109], "100", None)
extracted([29, 43, 115], "0", "million dollars")
extracted([41, 71, 75, 104, 122, 136], "-25%", "percent")
extracted([91], "-3.55", None)
extracted([108], "1277", "million")
extracted([127], "9425966", "shares")
extracted([144], "-3.57%", "percent")

SECONDARIES = {}


def secondary(indices, value, unit, direction=1):
    for index in indices:
        assert index not in SECONDARIES
        SECONDARIES[index] = (value, unit, direction)


secondary([6, 59, 94], "2.56%", "percent")
secondary([11, 63, 121], "-6.84%", "percent")
secondary([12, 74, 135], "13.05%", "percent")
secondary([15, 117], "12.28%", "percent")
secondary([26], "17.26%", "percent")
secondary([31, 40, 112, 143], "14.91%", "percent")
secondary([35], "10.42%", "percent")
secondary([49], "102", "USD_million", -1)
secondary([52], "-3.60%", "percent")
secondary([57, 58, 96], "13,636,000", "USD")
secondary([70, 89], "5,658,000", "USD_million")
secondary([123], "1,653,000,000", "USD_million")
secondary([128], "9,528,191", "shares")

# Manual units follow the public case interpretation above, never a private target.
CALC_UNIT_BY_PUBLIC_TASK = {
    "C01": "USD_thousand",
    "C02": "USD_thousand",
    "C04": "USD_million",
    "C08": "million shares",
    "C09": "USD_thousand",
    "C10": "USD_million",
    "C11": "USD_million",
    "C12": "USD_million",
    "C14": "shares",
    "C15": "USD_thousand",
}
RATIO_CASES = {16, 30, 33, 63, 133}
UNRESOLVED_CALC_UNIT = {24}


def build():
    destination = OUTPUT / "analysis/confirm_review_transcription"
    assert not destination.exists(), "one frozen review set, no score-driven re-review"
    templates = json.loads((OUTPUT / "assessment/confirm/review_template.json").read_bytes())
    reviews, packet_refs, semantic_fields = {}, {}, 0
    for index in range(1, 145):
        rid = f"confirm_{index:03d}"
        packet_path = OUTPUT / "assessment/confirm/public_review_packets" / (rid + ".json")
        raw_packet = packet_path.read_bytes()
        packet = json.loads(raw_packet)
        packet_refs[rid] = sha(raw_packet)
        review = copy.deepcopy(templates[rid])
        name, default = CASES[index]
        states = OVERRIDES.get(index, default)
        raw_messages = {int(k): v for k, v in packet["raw_messages"].items()}
        first_final = packet["first_final_index"]
        calculations = packet["calculations"]
        assert len(calculations) <= 1, (rid, "every actual calculation was individually read")
        selected = calculations[0] if calculations else None
        before = (
            evidence(packet, sorted({0, selected["response_index"]}))
            if selected
            else evidence(packet, sorted(raw_messages))
        )
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
        review.update(
            author="Codex assistant; same executor; explicit masked offline review; not independent expert",
            offline_post_generation=True,
            condition_inferred_from_self_description=False,
            review_case_family=name,
        )
        for position, field in enumerate(FIELDS):
            review[field]["status"] = STATUS[states[position]]
            group_evidence = final_evidence if position == 4 else before
            if position < 3 and states[position] == "F":
                group_evidence = before + final_evidence
            review[field]["evidence"] = copy.deepcopy(group_evidence)
            if position < 3:
                review[field]["explanation"] = DESCRIPTIONS[name][position]
        if index in {54, 108}:
            review["variable_correspondence"]["explanation"] = (
                "实际当前调用仍把 value=1277 与 source:t0c3n0 联系：显式 sources 映射或同一扁平 value/source/unit 元数据中的 source 属性。"
                "这个事实是年份 2015，read_source 的真实返回也已说明。变量没有被消费不认证公开来源声明；正确经营现金流正文不能抹掉当前虚假的日历—金额对应。"
            )
        if index == 126:
            review["variable_correspondence"]["explanation"] = (
                "当前 variables 的扁平 value=2.7/source:t6c1/unit:millions 元数据，把变化量对应到实际为 8.2 的年末余额单元格；"
                "按与其他扁平 source 属性相同的公开来源声明解释，该当前对应不成立。正确字面式 8.2-5.5 和未消费该元数据不能认证其来源声明。"
            )
        if index in {111, 120}:
            review["variable_correspondence"]["explanation"] += (
                " 本例辅助列表只有 t6c1n0，为无关未来租赁 128 千美元，并非月度基本租金依据；明确不认证此列表。"
                "当前完整财务依据来自调用前独立的 p17 对应，而非把该列表暗中改成正确来源。"
            )
            review["variable_correspondence"]["evidence"] += final_evidence
        if index == 86:
            review["variable_correspondence"]["explanation"] += (
                " 本例真实 tool:3 已清空原失败提案的 SEGMENT 映射，当前正确字面关系及原公开年度/金额独立可核对。"
            )
        publication = review["publication"]
        if index in EXTRACTED:
            assert publication["value"] is None and publication["unit"] is None, rid
            publication["value"], publication["unit"] = EXTRACTED[index]
        publication["direction_multiplier"] = None if first_final is None else 1
        publication["evidence"] = copy.deepcopy(final_evidence)
        publication["explanation"] = (
            "没有实际 Final；不从工具、先前消息或问题补造发布量。"
            if first_final is None
            else "原实际第一 Final.value/unit 及词法精度具有绝对优先级；缺字段时只从该 Final 自身提取。原有负号按有符号量解释一次，不由参考结果改变方向。"
        )
        if publication["unit"] == "":
            publication["explanation"] += (
                " 原 unit 为显式空字符串，保持空字符串；不以同 Final 文字或问题替换主字段。"
            )
        if index in {14, 19, 91, 101, 109}:
            publication["explanation"] += " 实际 Final 是没有单位的裸数，发布单位保持未定。"
        calc = review["calculation"]
        if selected:
            unit = CALC_UNIT_BY_PUBLIC_TASK.get(packet["task_key"], "percent")
            if index in RATIO_CASES:
                unit = "ratio"
            if index in UNRESOLVED_CALC_UNIT:
                unit = None
            calc.update(
                call_id=selected["call_id"],
                unit=unit,
                direction_multiplier=1,
                evidence=copy.deepcopy(before),
                explanation="选择唯一真实成功 calculate 调用；单位来自调用前/同调用公开财务解释及其源表定义，不由 Final 或参考金额倒填。",
            )
            if name == "contingent_correct_removal_wrong_claimed_millions":
                calc["explanation"] += (
                    " 此例 million 仅为模型预先对两项明确声称的同一错误单位，用于过程诊断；unit_handling=FAIL 保留与源表千美元的冲突，不认证财务尺度。"
                )
            if index == 24:
                calc["explanation"] += (
                    " 公开转换与混合尺度无法确定一致单位，保留 unit=None；实际标量计算成功不等于财务数量建立。"
                )
            if index in RATIO_CASES:
                calc["explanation"] += (
                    " 实际式未乘 100，结果是 ratio，不能按 Final 的百分号反向改为 percent。"
                )
        else:
            calc["explanation"] = (
                "没有实际成功 calculate；不重放伪 calculate 字段、对象值工具、同第一 Final 的 sibling、JSON 失败或未知 tool:final。"
            )

        p_status = review["publication_alignment"]["status"]
        review["publication_alignment"]["evidence"] = copy.deepcopy(before + final_evidence)
        if p_status == "PASS":
            explanation = "选定真实计算与原主字段发布量按公开单位、方向和冻结显示容差对齐；此分项不替代公式、来源、财务单位或同 Final 补充量的一致性判断。"
            if name == "contingent_correct_removal_wrong_claimed_millions":
                explanation += " 本例只在模型自称的错误 million 尺度下自洽，不能当作财务尺度 PASS。"
        elif p_status == "NOT_ESTABLISHED":
            explanation = "没有可与 Final 建立连接的真实成功 calculate；不因缺执行证据就自动宣称金融答案错误。"
        elif p_status == "UNDETERMINED":
            explanation = (
                "真实计算存在，但其财务单位因混合尺度尚未建立；不从 Final 倒填 million。"
                if index == 24
                else "真实工具输出股数明确，但原主字段 unit 为空，不能用补充文字替换主字段来确认物理数量连接。"
            )
        elif not selected:
            explanation = "实际 Final 引用的 calculate:... 没有对应真实成功计算；tool:3 若真实存在也只是未知工具错误输出，不是成功结果。"
        elif index == 127:
            explanation = "真实值 9425966.1893 shares 与实际 Final 9425966 shares 相差 0.1893，超过冻结主容差上限 0.005 股；普通整数四舍五入不能改变本轮已冻结的连接容差。"
        else:
            explanation = "真实计算的 ratio/千美元单位与原 Final 的 percent/基础美元/百万美元单位不一致，物理数量不能按相同裸标量直接连接。"
        review["publication_alignment"]["explanation"] = explanation
        consistency = review["final_answer_consistency"]
        if consistency["status"] == "FAIL":
            consistency["explanation"] = {
                63: "同一实际 Final 主字段 -0.0684% 与答案文字 -6.84% 相差 100 倍；保留主字段，不选其中更接近参考的一项。",
                70: "同一实际 Final 主字段 5658 千美元与文字 $5,658,000 million 是不同物理数量，不能删除 million 来凑一致。",
                89: "同一实际 Final 主字段 5658 千美元与文字 $5,658,000 million 是不同物理数量，不能删除 million 来凑一致。",
                123: "同一实际 Final 主字段 1653 million dollars 与文字 $1,653,000,000 in millions 不一致；尾随 in millions 按明确显示单位限定解释，不删除该限定。该文字拙劣的解释选择明确披露。",
            }[index]
        elif consistency["status"] == "UNDETERMINED":
            consistency["explanation"] = (
                "没有实际 Final，或其自身没有可解释的数量单位；不能从问题、先前模型消息或工具结果补全。"
            )
        else:
            consistency["explanation"] = (
                "实际第一 Final 的数量显示内部一致、答题对象单一；参考数值是否正确和当前财务公式/来源是否成立分别判断，不把数值错误重复当作内部冲突。"
            )
            if index == 128:
                consistency["explanation"] += (
                    " 本例原主单位保持空，Actual Final 文字中的唯一明确股数量作为独立 secondary 验证；这不把主单位补成 shares。"
                )
        if index in SECONDARIES:
            value, unit, direction = SECONDARIES[index]
            review["secondary"] = [
                {
                    "value": value,
                    "unit": unit,
                    "direction_multiplier": direction,
                    "evidence": copy.deepcopy(final_evidence),
                    "explanation": "此显示量确实在实际第一 Final 内，保留自己的数字、尺度、方向及精度；不取自工具或 sibling，不把解释式操作数当作竞争答案。正的减少幅度仅凭该 Final 明确 decrease 措辞取 -1。",
                }
            ]
        route = review["route_observation"]
        route["evidence"] = copy.deepcopy(before)
        route["description"] = (
            f"公开路线观察 {name}；实际成功 calculate={len(calculations)}。"
            "已逐条读完全部生成响应、事件和成功计算；read_source、语法错误、协议错误、未知工具和第一 Final 抑制的 sibling 保留原记录。"
            "路线观察不是分布身份、效用或理论 Contribution。"
        )
        # Exact-quote, original-field and lexical-evidence checks only; no target/arm input.
        _evidence(review, raw_messages)
        audit_subset = {"raw_messages": packet["raw_messages"], "first_final_index": first_final}
        lexical_final = (
            None
            if first_final is None
            else json.loads(raw_messages[first_final], parse_int=str, parse_float=str)["final"]
        )
        if isinstance(lexical_final, dict):
            for key in ("value", "unit"):
                if key in lexical_final:
                    assert publication[key] == lexical_final[key], (rid, key)
                    assert type(publication[key]) is type(lexical_final[key]), (rid, key)
        for quantity in [publication, *review["secondary"]]:
            expected = all(
                quantity[key] is not None for key in ("value", "unit", "direction_multiplier")
            )
            assert _quantity_evidence(quantity, audit_subset) == expected, (rid, quantity)
        if selected:
            expected = calc["unit"] is not None and calc["direction_multiplier"] is not None
            assert (
                _quantity_evidence(
                    {**calc, "value": selected["actual_exact_value"]},
                    audit_subset,
                    calculation=selected,
                )
                == expected
            ), rid
        semantic_fields += len(FIELDS)
        reviews[rid] = review
    store = DurableStore(destination)
    store.json("reviews.json", reviews)
    store.json(
        "provenance.json",
        {
            "reviewer": "same Codex executor; not independent expert",
            "reviewed_original_masked_packets": 144,
            "semantic_field_count": semantic_fields,
            "all_public_source_documents_read_before_any_confirmation_response": 24,
            "all_generated_public_strings_and_every_event_occurrence_read": True,
            "masked_packet_sha256": packet_refs,
            "identity_map_private_reference_values_and_per_arm_utilities_read_before_review": False,
            "execution_progress_metadata_was_visible": True,
            "fully_blinded": False,
            "explicit_arm_or_seed_inferred_from_model_self_description": False,
            "same_review_interpretations_as_development": True,
            "important_judgments": [
                "Complete pre/same-call financial metric, period and source amount descriptions can independently ground literal inputs; there is no numeric-ID-only format gate.",
                "Explicit current value/role-to-wrong or nonexistent source mappings are not certified, including flat value/source/unit metadata. Unused variables do not validate a false public claim.",
                "Abandoned failed mappings are not repaired; a subsequent correct current literal call can be grounded independently. Clearing sources does not repair wrong financial amounts or periods.",
                "Final-only auxiliary lists, including unrelated but real source:t6c1n0 in confirm_111/120, are not rewritten or certified; the source PASS there refers to independent correct pre-call facts, not to every Final metadata field.",
                "confirm_024 preserves an unresolved mixed calculation unit; confirm_053/061/078/113/131 retain the model's explicit single wrong million unit only for self-consistency diagnostics, while financial unit handling fails.",
                "Original empty Final.unit stays empty. A separately explicit secondary quantity is still checked, including confirm_128; no primary field is filled from prose.",
                "confirm_123 interprets the literal in millions qualifier as the secondary display unit, not as a removable typo; main source and thousand-to-million errors independently remain.",
                "confirm_127 applies the pre-frozen 0.005 primary cap to the actual integer-share Final; no post-hoc rounding relaxation and no invented earlier Final.",
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
                "semantic_fields": semantic_fields,
                "reviews_sha256": sha((destination / "reviews.json").read_bytes()),
                "no_identity_or_financial_grade_read": True,
            }
        )
    )


if __name__ == "__main__":
    build()
