# 110条失败毛利锚点：完整只读缓存审计

本次按用户授权，对 `financial_locator_revision_03` 中全部110条 `gross_profit` 失败候选进行AI辅助只读缓存核查，不是抽样。它们按原报告、页、缓存表/行/标签形成55组；逐组在已保存几何页上均定位到唯一目标GP行，最终确认55个物理行，覆盖45份原报告，均为HKEX来源。

结果：[完整逐行JSON](../artifacts/qa_vnext_fixed_kernel_value/cross_market_calibration_20260926/public/gross_profit_anchor_audit_20260926.json)。每个旧候选ID只在 `rows[].failed_candidates[].candidate_id` 出现一次；每行保留原失败、旧金额/期间/币种/比例、原页短引文、缓存hash及尚缺证明。原始PDF路径仅作来源标识，本次未打开PDF或PNG。

## 结论与分类范围

| AI缓存审计分类 | 物理行 | 原失败候选 | 含义 |
| --- | ---: | ---: | --- |
| 定位证据存在，未准入 | 18 | 36 | 原标题、日期、单位或双语显示行确实存在具体定位限制证据；并不表示其余门槛通过。 |
| 定位问题与具体来源/组件问题并存 | 13 | 26 | 同时见重述、持续经营、会计过渡、合并范围绑定或配对成本概念问题。 |
| 明确来源门槛，非仅定位 | 24 | 48 | 包括多语义列、季度、摘要精度/单位、真实重述等。不能靠放宽标签或截两列直接通过。 |
| 合计 | 55 | 110 | 三类互斥统计，逐行 `issue_tags` 保留复合问题。 |

这不是18个“可恢复窗口”或36道新题，也没有计算新增题数。原40道双路径候选仍是20个来源窗口上的difference/relative-change两种题型，不是40个独立窗口。GP行是否能够用于双路径，还取决于同报告同期间Revenue/Cost准入、完整符号/范围关系、版本和最终公开视图等；本子审计不替代并行成本及18条关系审计。

## 从原文实际发现的关键区别

- 双语显示、英文日期序数词和字距确有工程定位限制。龙湖/华润多份原行是“毛利 Gross profit”；恒安、BYD是“Gross profit 毛利”。Swire年度句用“31st December”；Geely部分标题被导航栏穿插或字距拆开。它们不同于原文没有标题、日期或指标。
- 真正多语义列不能被称为定位误拒。WH全部7行每年均分“生物公允价值调整前／调整／Total”，共6金额列；旧两候选实际取了上年调整额和上年Total，却标当前年/上年。Geely2025页143是2024并购重述的5列调节，不是2025/2024年度对照；旧候选把合并调整额 `(306,802)` 当作2025毛利。
- 真正季度不能变成年份。Tencent页13、17分别明确三个月、第四季对第四季／同年第三季，并标未审计；旧候选却记为全年。页8的全年MD&A另有Restated，仍需摘要范围及版本证明。
- 摘要列和正式表不能混用。Longfor五个Performance Highlights行以RMB billion显示摘要金额（示例含小数），与正式RMB’000表的展示单位和精度不同；2020—2022还含Growth百分数。旧候选出现取上年值/增长百分数、HKD或million错绑定。同报告正式RMB’000损益表是另一个物理行，不以其存在就修改摘要锚点。
- SMIC2019分别出现5年摘要和3年正式表；旧候选机械取得尾部年份的数值却标较新年份。正式表页脚又披露比较列报reclassified，不能因原失败叫header_empty就当成单一表头工程问题。
- 真实版本/口径提示继续保留。New World、Tencent、Shenhua、BYD、部分Swire/Geely/华润表头确有Restated；New World/Swire另有Continuing operations。Geely2019页脚说明采用HKFRS16、比较数据“不重述”，这是会计过渡提示，不能反写成“已重述”，也不能跳过基准连续性核验。
- BYD2020原单位明确RMB’ 000/人民幣千元，而旧候选scale为million、单位证据来自另一段金额叙述。当前原单位被拆为RMB’和000词，存在表头被误当金额行截断的实现风险；无论后续怎样修定位，都不能保留旧million当gold。

## 逐物理行审计

下表页码为原PDF 1-based页面，行号对应JSON审计键末尾编号。报告年是冻结元数据年，不被当作事实年期证明；所有条目仍未准入。

| 行 | 证券 | 报告年 | 原页 | 分类 | 原文核查结论 |
| ---: | --- | ---: | ---: | --- | --- |
| 1 | 00017 | 2022 | 179 | 明确来源门槛 | 原合并损益表、30 June 2022年度句和HK$m均在；年列表头明确(restated)，不是仅缺定位。 |
| 2 | 00017 | 2024 | 168 | 明确来源门槛 | 2024合并损益表同时印有(Restated)与Continuing operations，GP两列存在。 |
| 3 | 00017 | 2025 | 178 | 定位＋来源/组件问题 | 原表明确For the year ended 30 June 2025和两处HK$m；旧native_scale_unresolved不等于来源未披露单位。 |
| 4 | 00019 | 2020 | 133 | 定位证据存在（未准入） | 完整年度句为For the year ended 31st December 2020；标题、HK$M、两年度列及GP均在。 |
| 5 | 00019 | 2021 | 125 | 定位＋来源/组件问题 | 年度句含31st；原表另印Continuing operations和比较列(Note 1c)。 |
| 6 | 00019 | 2022 | 127 | 定位＋来源/组件问题 | 31st December 2022年度句明确，表头又有(Restated)与Continuing operations。 |
| 7 | 00019 | 2023 | 131 | 定位＋来源/组件问题 | 31st December 2023、两列HK$M及GP可见，表内明确Continuing operations。 |
| 8 | 00019 | 2024 | 146 | 定位证据存在（未准入） | For the year ended 31st December 2024与两列HK$M在同页标题下，GP及相邻成本可见。 |
| 9 | 00175 | 2019 | 94 | 定位＋来源/组件问题 | 真正的CONSOLIDATED/INCOME STATEMENT被导航词EDITORIAL、MANAGEMENT REPORT等穿插；年度、RMB’000与GP存在。页脚明确HKFRS 16初次采用且比较信息未重述。 |
| 10 | 00175 | 2022 | 113 | 定位证据存在（未准入） | 原页113印字距拆开的CONSOLIDATED INCOME STATEMENT及For the year ended 31 December 2022；两个年度及RMB’000明确。旧period_source_page=109与当前原表页不同。 |
| 11 | 00175 | 2025 | 124 | 定位＋来源/组件问题 | 2025实际合并损益表标题被侧栏导航穿插；同页明确(Restated)，GP两列存在。 |
| 12 | 00175 | 2025 | 143 | 明确来源门槛 | 原页是会计政策附注对2024损益的并购/同控影响调节，含Original amounts、三类调整、Restated amounts共五金额列。旧候选将合并调整(306,802)标为2025年度。 |
| 13 | 00288 | 2019 | 64 | 明确来源门槛 | 原表每年度均有Results before biological fair value adjustments、Biological fair value adjustments和Total，合计六金额列。旧两候选取上年调整额/上年Total却标当前年/上年。 |
| 14 | 00288 | 2020 | 64 | 明确来源门槛 | 原表每年度均有Results before biological fair value adjustments、Biological fair value adjustments和Total，合计六金额列。旧两候选取上年调整额/上年Total却标当前年/上年。 |
| 15 | 00288 | 2021 | 63 | 明确来源门槛 | 原表每年度均有Results before biological fair value adjustments、Biological fair value adjustments和Total，合计六金额列。旧两候选取上年调整额/上年Total却标当前年/上年。 |
| 16 | 00288 | 2022 | 65 | 明确来源门槛 | 原表每年度均有Results before biological fair value adjustments、Biological fair value adjustments和Total，合计六金额列。旧两候选取上年调整额/上年Total却标当前年/上年。 |
| 17 | 00288 | 2023 | 66 | 明确来源门槛 | 原表每年度均有Results before biological fair value adjustments、Biological fair value adjustments和Total，合计六金额列。旧两候选取上年调整额/上年Total却标当前年/上年。 |
| 18 | 00288 | 2024 | 62 | 明确来源门槛 | 原表每年度均有Results before biological fair value adjustments、Biological fair value adjustments和Total，合计六金额列。旧两候选取上年调整额/上年Total却标当前年/上年。 |
| 19 | 00288 | 2025 | 67 | 明确来源门槛 | 原表每年度均有Results before biological fair value adjustments、Biological fair value adjustments和Total，合计六金额列。旧两候选取上年调整额/上年Total却标当前年/上年。 |
| 20 | 00700 | 2023 | 8 | 明确来源门槛 | 该页标题为Management Discussion and Analysis，比较2023/2022全年且有Restated*；有年度摘要数值，但非当前明确合并报表标题。 |
| 21 | 00700 | 2023 | 13 | 明确来源门槛 | 原文明确第四季度对第四季度、Unaudited、Three months ended；旧候选却记为两年全年。 |
| 22 | 00700 | 2023 | 17 | 明确来源门槛 | 原文为2023第四季度对2023第三季度、三个月且未审计，两列均2023；旧候选却标2023/2022全年。 |
| 23 | 00700 | 2023 | 129 | 明确来源门槛 | 正式合并损益表明确Restated(Note 2.2)。收入先列四类业务，再列无Revenue标签的总计，之后为Cost和GP。 |
| 24 | 00960 | 2019 | 140 | 定位证据存在（未准入） | 正式合并损益表、完整年度及RMB’000明确；原行是毛利 Gross profit，中文在英文短标签之前。 |
| 25 | 00960 | 2020 | 87 | 明确来源门槛 | 董事会Performance Highlights标RMB billion，GP为54.03/50.80及6.4%增长。旧候选取50.80与6.4%，并继承HKD/million。 |
| 26 | 00960 | 2020 | 115 | 定位证据存在（未准入） | 正式报表标题、December 31, 2020和RMB’000明确；GP原行含中文毛利前缀。 |
| 27 | 00960 | 2021 | 89 | 明确来源门槛 | Performance Highlights以RMB billion给出56.54/54.03及4.6%；旧候选却取54.03和4.6%并标million。 |
| 28 | 00960 | 2021 | 116 | 定位证据存在（未准入） | 2021正式合并损益表和两列RMB’000在原页；目标为毛利 Gross profit。 |
| 29 | 00960 | 2022 | 80 | 明确来源门槛 | Performance Highlights原单位RMB billion，GP为53.04/56.54及-6.19%；旧两锚值为56.54和增长百分数。 |
| 30 | 00960 | 2022 | 110 | 定位证据存在（未准入） | 正式合并损益表的2022/2021列、RMB’000和毛利 Gross profit原行均清楚。 |
| 31 | 00960 | 2023 | 75 | 明确来源门槛 | 董事会摘要仅两金额列，但标题仍为Performance Highlights，原单位RMB billion；旧候选比例为million。 |
| 32 | 00960 | 2023 | 106 | 定位证据存在（未准入） | 2023正式合并损益表的原文同时有中文毛利及英文Gross profit，年期和RMB’000明确。 |
| 33 | 00960 | 2024 | 68 | 明确来源门槛 | 董事会Performance Highlights明确RMB billion，GP20.41/30.58；旧候选为HKD/million。 |
| 34 | 00960 | 2024 | 98 | 定位证据存在（未准入） | 2024正式表中毛利 Gross profit、完整年度日期、两年度列和RMB’000在同页。 |
| 35 | 00960 | 2025 | 86 | 定位证据存在（未准入） | 2025正式表中毛利 Gross profit有两个年度金额，标题/完整年期/原币千元证据都存在。 |
| 36 | 00981 | 2019 | 19 | 明确来源门槛 | 原页明确summary consolidated financial data，年度列为2019/2018/2017/2016/2015五年；旧候选抓2016/2015数值却标2019/2018。 |
| 37 | 00981 | 2019 | 111 | 定位＋来源/组件问题 | 正式表明确2019/2018/2017三年度及12/31/xx列；旧候选取后两年数值错配。页脚还披露政府资金列报政策改变及比较数据reclassified。 |
| 38 | 00981 | 2020 | 129 | 定位证据存在（未准入） | 正式合并表实际是2020和2019两年度，年度句使用years ended，列名为12/31/20与12/31/19，USD’000及GP明确。 |
| 39 | 00981 | 2021 | 129 | 定位＋来源/组件问题 | 原页抬头为公司AND SUBSIDIARIES，随后STATEMENT OF PROFIT OR LOSS，未直接印CONSOLIDATED；原日期及12/31/21、12/31/20存在。 |
| 40 | 01044 | 2023 | 103 | 定位＋来源/组件问题 | 正式表目标原行Gross profit 毛利，中文位于英文之后；紧邻成本标签是Cost of goods sold 銷售成本。 |
| 41 | 01044 | 2024 | 105 | 定位＋来源/组件问题 | 2024正式表原行Gross profit 毛利，RMB’000及完整年期明确；成本为Cost of goods sold。 |
| 42 | 01044 | 2025 | 101 | 定位＋来源/组件问题 | 2025正式表原行Gross profit 毛利及两年原币千元；成本仍为Cost of goods sold。 |
| 43 | 01088 | 2022 | 204 | 明确来源门槛 | 正式表明确(Restated)；收入标题Revenue下一行是Goods and services，随后成本和GP。 |
| 44 | 01088 | 2023 | 220 | 明确来源门槛 | 2023正式表明确(Restated)，收入通过Revenue/Goods and services分两行表达。 |
| 45 | 01088 | 2025 | 240 | 明确来源门槛 | 2025正式表年列表头明确(Restated)，收入与Goods and services分行后接成本/GP。 |
| 46 | 01109 | 2019 | 117 | 定位证据存在（未准入） | 正式合并收益表中原行毛利 Gross profit；年度短句For the year ended 31 December的年份放在随后2019/2018列。 |
| 47 | 01109 | 2020 | 122 | 定位＋来源/组件问题 | 2020正式收益表原行中文在前，表头同时有（經重列）/(Restated)；年份位于后续比较列。 |
| 48 | 01109 | 2021 | 130 | 定位证据存在（未准入） | 2021原正式合并收益表、毛利 Gross profit及RMB’000均在；年度年份在比较列而非日期同一行。 |
| 49 | 01109 | 2022 | 150 | 定位证据存在（未准入） | 2022实际表在页150，标题/日期短句/年度列/GP清楚；旧period_source_page=139与真实目标页不同。 |
| 50 | 01109 | 2023 | 133 | 定位证据存在（未准入） | 2023实际合并损益表在页133，旧period_source_page=126；原毛利 Gross profit、RMB’000及2023/2022列存在。 |
| 51 | 01109 | 2024 | 149 | 定位证据存在（未准入） | 2024合并损益表原行毛利 Gross profit，日期与年份分行，原币单位RMB’000清楚。 |
| 52 | 01109 | 2025 | 159 | 定位＋来源/组件问题 | 2025原合并损益表有毛利 Gross profit及（經重列*）/(Restated*)，日期和年份分行。 |
| 53 | 01211 | 2019 | 51 | 明确来源门槛 | 2019正式合并表有完整年度、RMB’000和GP，年列表头明确(Restated)。 |
| 54 | 01211 | 2020 | 93 | 定位证据存在（未准入） | 正式表原单位为RMB’ 000/人民幣千元，原行Gross profit 毛利；旧候选scale=million，unit_evidence却取自另一段金额叙述。 |
| 55 | 01211 | 2021 | 103 | 定位证据存在（未准入） | 2021正式表完整日期、RMB’ 000/RMB’000及Gross profit 毛利清楚，中文是同一行的显示标签。 |

## 保留、核验和不能宣称的事项

父财务协议：`cross_market_layout_qualification_protocol:f0a6d7d1a3b3f477dd9d7d13d60cce62ef1077955c83a59a80cf7bb48f5eb02c`。父完成记录：`cross_market_financial_qualification_completed:061431eb41f7870d3580466b2bf7c93fc224fa03a2bc71f56b96f72998602ad3`。JSON绑定两个父文件的原字节hash，并逐行绑定财务记录ID、几何记录ID、原PDF hash/官方URL、完整页文本/原提取/协调几何缓存及对应页/词索引。55个实际GP行均已显示核对，不把“Gross profit margin”当目标GP行。

核验范围是全部110失败锚点及相关表头、GP行、必要页脚，不是对45份PDF每页完整内容的穷尽语义审阅。本报告是assistant/AI-assisted read-only cache inspection，**不是人工签字证书，也不是153份来源“没有现成三年汇总”的独立审阅证明**。

本次原PDF/PNG打开、原parser、`certify`、`financial_facts`、`compile_candidates`、新任务枚举、API、Student、GPU和既有数据修改均为0；只使用 `lines_for_page` 显示已存词位置，并读取已存文本/候选/失败。未依据算术闭合准入或改数，未改门槛、名单、配额、模型、种子，未覆盖任何失败。

后续若要求实现修订，应先按这些不同证据类型另行定义有界合同；不能从本审计直接推出足够新增20道题、一定满足60题配额或正向训练价值。
