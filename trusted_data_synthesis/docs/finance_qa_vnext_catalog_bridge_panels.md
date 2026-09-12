# Catalog Bridge：隔离评测面板的有界构建合同

## 运行后状态更新：v3 审计阻断正式评测

下文是生产前的有限构建合同，不是最终面板准入结论。生产实际导出 874 条记录：
dev 166（双依据 46、均值 60、峰值关联 60），confirm 708（234、237、237）。
原计划仍分别缺 14、12 个记录；不能把 180 / 720 计划写成已经完成。

最新独立运行后审计 **v3 = `BLOCKED_PUBLIC_PERIOD_MISMATCH`**：
874 条记录虽均通过现有 QA，来源 / 父链 / 数值层核对也通过，但峰值关联组中
dev 18、confirm 78，共 96 题把非日历财政年度称为 `calendar year`，构成公共题面准入阻断。
全部冻结题面与目标保留不变，没有删除、修订、替换或补题；没有由剩余记录重算成功面板。
正式评测 primary worker 未建立资格，不能启动正式 Teacher / Student 效用实验。

v1 是审计器字段名称错误记录，v2 只覆盖来源 / 父链 / 数值有限层；**v3 最新结论优先**。
完整受影响 ID、期间、原问题和 SHA，以及计数与相关结构，见
[独立运行后审计说明](finance_qa_vnext_catalog_panels_postrun_audit.md) 和
`artifacts/qa_vnext_catalog_bridge/independent_panel_audit_20260912_v3.json`。

实际来源簇为 dev 12、confirm 71；其中双依据组仅 dev 3、confirm 27 个 CIK。
确认侧 12 个未导出目标是 6 个缺少唯一真实 DerivedFact 父、6 个 candidate
语义约束拒绝而未发出 sample；实际 708 个 QA 的验证拒绝数为 0，不是 12 个 QA 验证失败。

## 原构建合同与预冻结控制

本文件记录面板实现和预冻结控制，不把计划的 180 / 720 题写成已生产结果。
真实生产数量、QA 拒绝、各组不足和来源相关结构以父阶段冻结后生成的
`evaluation_panels/report.json` 及两个分面板 `catalog.json` 为准。本模块不发送模型请求。

## 1. 来源独立性与已知开发依据

继续使用 `basis_task_factory_sources_20260911.v1:` 盐、55 桶和原有 CIK 分组，
没有因供给量更换盐，也不以更改 `split` 字段替代来源资格。
冻结旧归档的 100 家美国实体按原盐分别为 train 14、dev 13、confirm 73。
读上述数字只访问原实体和 raw-object 元信息，不读取新的评测公司金额。

旧确认的权威登记为：

`qa_vnext_bidirectional_utility/three_tasks_24rep_flash_rerun_20260910/preparation/panel_selection.json`

其 `company_clusters.confirm` 必须与源码 `panel_specs.CONFIRM` 的 24 题发行人一致。
登记的 8 个 ticker 为 AAPL、ABMD、AMT、BKR、ECL、KHC、MRK、UNP。
新面板按旧确认的发行人簇隔离，而不只是删除相同旧题 ID。
在当前 100 家归档实体中，精确 ticker / CIK 元信息连接得到：

| Ticker | 原归档 CIK | 原盐 split | 本次评测处理 |
| --- | --- | --- | --- |
| AAPL | 0000320193 | confirm | 排除 |
| MRK | 0000310158 | dev | 排除 |
| UNP | 0000100885 | train | 本来不在新评测来源内 |

其余 5 个旧确认 ticker 不在固定 100 家实体登记中。这个检查不是一次跨全球公司更名史的
开放实体消歧。没有未经必要性论证而再排除所有历史 train / dev 发行人。
因此本轮有限来源候选为 dev 12 个 CIK、confirm 72 个 CIK；这不保证每个 CIK 都有合格任务。
源选择先于金额检查：每 CIK 在原 RawObject 参考中按 snapshot date、raw-object ID 选一份。
原始字节大小、SHA-256、payload CIK、实际期间、tag、币种和年度筛选均重新验证。

## 2. 三组不是同模板换公司

计划 dev 每组 60、confirm 每组 240，固定封顶后不以 QA 结果回填。

| 组 | 本次有限目标 | 注册 Pattern | 主要资格要求 |
| --- | --- | --- | --- |
| 双充分依据 | 相邻年度毛利变化额或正前期基数增长率 | pinned_annual_metric_change / growth | 两期毛利端点，以及各期完整营收减营业成本，概念定义、共同申报、单位、期间和数值闭合同时成立 |
| 确需组成整合 | 恰好三个连续实际年度流量的算术均值 | entity_metric_temporal_average | 每期均有独立的非零 1/3 系数；仅首末年度流量不能决定中间年度；不用 stock 平均冒充 flow 整合 |
| 其他金融任务 | 三年度营收最大年度，并取该年度净利润或营业利润 | temporal_argmax_then_metric_lookup | 主指标三个年度完整、最大值唯一、次指标同实际期间完整、定义和财务范围一致 |

组成组的指标固定为营收、净利润、营业利润、经营活动净现金流。
此处的“组成”包含时间区间组成，不将其称为公司定义 FCF 明细整合或 stock roll-forward。
若完整原快照中同一原概念存在覆盖整个三年目标窗口的 USD 记录，组成组保留拒绝，
不把该记录藏掉，也不按答案相等与否挑选一个便利解释。
该规则仅处理登记的年度流量语义，不声称对任意财报自然语言完成了充分性判定。
峰值组不受另一组均值资格结果筛选；即使某个窗口有公开三年汇总，仍独立判定峰值题。
主指标并列最大时保留拒绝，不用次指标大小打破平局。

这三个结构能区分变化、时间组成和排序后关联取值，但不是覆盖广泛金融任务的基准声明。
所有候选按 CIK 轮转、实际结束期间和语义任务 ID 固定枚举；不使用 Teacher、Student、
改写接受率、质量分数或答案难易度排序。缺额保留，不换组、不增加 seed 乘数、不开放搜索。

## 3. 真正的事实与 QA 父链

开发和确认各自建立新的隔离 SQLite 数据库。原始 companyfacts 记录进入既有原子事实接口，
再执行真实 standardization、fact quality、DerivedFact 与 KG Build。
仅实际成功 KG 中的 Fact 能用于候选。所有叶子必须同时满足原盐所属分面板和
`allowed_uses=[split]`，既在绑定时检查，也在编译和导出时复核。

之后使用既有 `finraw.qa.pipeline._graph_pattern_candidate`、已登记 Pattern、真实
`generate_qa_samples` 和 `validate_qa_samples`。差额 / 增长率仍要求同轮真实 DerivedFact 父；
均值及峰值任务通过真实 Fact → KG → Pattern / plan → QA 链生成，不伪造三年 DerivedFact。
题面为既有确定性模板，QA 的题面 roundtrip 检查仍执行，没有新的评测改写请求。

导出前再次从事实用独立 Decimal 计算核对答案；峰值题同时核对被选年度。
每题记录完整父 Build、candidate、plan、QA 检查和私有见证，但见证不是 Teacher 轨迹。
固定 cap 之后的 QA 拒绝不再触发下一批补题。

## 4. 公开资料、私有 Oracle 与评分

每个发行人只存一份 `panel_public_source_document` 索引。它包含任务枚举前选中的全部
年度原记录，不是仅包含参考执行所需叶子的删减视图；同时提供完整原 companyfacts
snapshot 的固定路径、字节大小、SHA-256 和原 URL。
`read_complete_source` 通过公开来源引用返回完整原 JSON 或精确 JSON pointer，
不读取 TaskBundle 的 `private`。任何原概念、单位、年份、出现位置都仍可公开读取。
不把相同的巨大完整 JSON 为每道题重复存 900 次。

后继在线评测必须接通这里声明的 `read_source` 合同；不能只有目录就认为在线评测已经接通。
本轮普通训练任务 worker 的通过，不自动证明这个完整快照读取入口已完成在线会话验收。
本轮面板不发 Teacher / Student 请求，也不启动 tokenizer 或 GPU。

公开问题、资料身份、数量合同和离线评分规则都先固定。金额答案按 million USD，
增长率按 percent，以 Decimal 四舍五入至两位（half away from zero）；峰值题还必须给对年度。
第一 Final 的完整来源支持执行才是主效用。`score_final` 只做次要的目标正确性检查，
明确返回 `complete_trajectory_qualified=None` 和 `is_primary_utility_score=False`，
不能以答案相等替代完整轨迹资格。
参考表达式不是唯一程序；无 Final、错误单位、错误峰值年度不能记为主效用成功。
完整公共读取、工具执行事件和轨迹资格仍须在正式评测前进行相应端到端验收。

## 5. 控制和运行边界

26 项独立合成控制通过，涵盖两种 split、四个 Pattern、双依据输入不相交、
中间年度反事实、完整三年汇总不能被隐藏、组间独立枚举、CIK / split 重贴标签、
缺期 / 不连续 / 口径 / 单位 / 并列最大、错误 Final、完整公开原文读取和来源相关计数。

其中一项执行了真实 native facts → standardization → quality → DerivedFact → KG →
QA generation / validation → TaskBundle 导出完整链：24 条合成金额事实产生 18 题，
其中双依据 6、组成 8、其他 4，18 题 QA 通过且导出拒绝 0。
这里复用了旧归档的本体 / 来源注册元信息，但所有金额都是明确合成夹具；不是生产面板结果。
测试不需要外网或模型。

父阶段先把 `panels.policy()`、`panels.inspect_source_metadata(root)` 的 ID 和本轮代码纳入冻结，
随后才可调用 `panels.run(root, output, work, expected_policy_id=...,`
`expected_source_metadata_id=..., freeze_id=...)`。重复输出目录 / 数据库会被拒绝。

报告分别给出任务数、CIK 数、原 snapshot 数、每 CIK 题数、发行人—期间共同成员数和
重叠窗口关联。720 只是计划题数；不由此推算独立样本数、有效样本量或检出能力。
若无法满足三组数量，则产出真实部分、完整拒绝和缺额，状态为
`PARTIAL_REAL_PANELS_SUPPLY_SHORTFALL`，不将其写为面板就绪。
