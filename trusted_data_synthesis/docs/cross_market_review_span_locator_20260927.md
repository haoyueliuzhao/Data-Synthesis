# 新前瞻span协议：无序边界、跨段证据和重叠谱系

本修订**扩展定位表达能力**，不是单纯的02代码bug修复，不把01/02失败回复重新解释为成功。02要求同segment、有序line_start/end；新协议预先声明boundary_a/b无序并允许同一原packet内跨segment/跨页。它可能使证据范围更宽，因此接口通过率与finding数量不能直接和前两轮作为语义准确率比较。

新模块：`scripts/cross_market_review_span_locator_20260927.py`。原01/02代码、请求、回复和失败不改；本模块不调用API、不解析/修补HTTP JSON、不注册预算、不打开PDF/图片。真正调用须由另一个前瞻冻结的执行器承担。

## 原文与来源身份不变

`project_packet`复用冻结line组件的完整原文表示，再增加原页绝对字符位置：`segment.start + line局部start/end`。原segments副本、全部逐行text、全部task intervals、四指标、原PDF/页文本身份和视觉未审警报都保留，不加入答案、witness、Student身份或Q。

L行ID仍是原segment执行splitlines(keepends=True)得到的文字行，不宣称等同PDF物理版面行或具有词级语义准确性。每个新span ledger都有独立hash，绑定原packet及所有来源映射。

## 前瞻无序边界的明确含义

每个finding精确包含`id, boundary_a, boundary_b, metric, kind, period_start, period_end, reason`。两个边界必须是该packet内真实L行ID，顺序任意，也可相同；其它packet/文档不允许引用。

代码按**原页码＋原页绝对字符位置**计算包含两条完整原行的最小包络。不能仅按L编号、segment序号或模型填写顺序排序：重叠segment的后一个L行可能对应更早的原文位置。Prompt要求最小必要支持区间；可表示更宽范围不代表主张更可信。

新reason要求合法JSON中的单行具体短句，不硬截断、不删除发现。旧line_start/end、quote或字符offset字段不兼容，也不自动转为新边界。JSON损坏仍由现有严格解析直接失败，不补引号、不补转义或换行。

## 完整覆盖与精确派生

1. 包络涉及的每个中间原页都必须在当前packet实际提供。同页的page文本hash与字符总数必须一致，缺页不能联网或从其它包补取。
2. 对每个原segment求与该原页包络的交集，生成该segment局部start/end及原text切片。全部交集的并集必须无字符缺口地覆盖要求区间。
3. 重叠文字逐字符比较，任何冲突均失败。保存每一对重叠segment的区间、字符数及文字hash，不用模糊匹配或Unicode正规化对齐。
4. 原空文本中间页保留空segment及页覆盖谱系，但不生成假的零长度quote。视觉内容依然未审；零文字不是无财务信息。
5. 每个非空交集成为可被冻结`core.validate_scan`验证的精确quote片段。所有来源字符均来自原segment，模型不生成quote、也不计算偏移。

代码不会因跨段范围而自动合并财务口径、实际期间或汇总定义。跨两页出现的不同数字可能根本不属于同一个金融事实；独立来源语义与视觉裁定门槛仍在。

## 一个proposal组，不是多个真实observations

每个原proposal保存独立`range_group_id`及原始proposal；同一原文包络另有`canonical_source_range_id`。每个证据片段有独立derived finding ID并链接range group。

对于重叠segment，原片段都保留，另用固定排序分配不重叠的`canonical_owned_page_intervals`，明确记录重复覆盖。三重重叠时，成对重叠长度不能直接相加；实现分别记录片段总字符、组内去重字符、重复字符，以及跨全部proposal去重的原文字符并集。

结果区分：原定位proposal组数量、精确quote片段数量、不同原文包络数量与去重字符数。`financial_observation_count`明确为null，片段显式标为`evidence_fragment_not_financial_observation=true`。不得把拆片当成多个真实财务观察、多个aggregate或多个独立样本；真正aggregate清单仍由独立裁定产生。

后续审阅界面应展示group/overlap谱系。冻结core仍可要求每个derived finding都有决策，但这些决策不能被计作额外独立证据票数。

## 接口与保存

- `project_packet(packet, reference)`：独立span投影。
- `render_request(..., maximum_request_bytes=..., transport_fields=...)`：内外层canonical UTF-8 JSON，返回FrozenRequest；最终body按真实字节cap检查，不截断，输出上限仍4096。
- `validate_span_scan(packet, projection, rawpayload)`：返回标准core结果（仍passed=false），另附`raw_span_payload`与`span_mapping_proof`。

`span_mapping_proof`保存原packet/投影/账本/原始及派生payload的hash、每组原proposal、规范包络、全部片段/重叠谱系/去重计数。主执行器还须保存原HTTP content/envelope原字节，不以派生JSON替换原回复。原始JSON格式错误没有此派生过程。

## 必要核验

18项纯合成测试通过，包括无序边界的原页位置排序与L编号不一致、同一边界、跨页空段不伪造quote、双/三重overlap的一致性与非加和去重、重复proposal保留而全局字符union去重、缺字符/缺页/冲突原文拒绝、未知ID/旧字段/缺段/多行reason/错指标/重复ID拒绝、原文与区间不改、canonical wire及文件读回不变、4096/cap不变、重算hash的投影篡改仍拒绝。Ruff通过。

这些测试验证定位表达和谱系，不证明模型理解、金融语义、视觉覆盖或训练价值。预期可表达02中部分跨段候选，但不得预填真实试运行成功率或据此宣称更高词级准确率。
