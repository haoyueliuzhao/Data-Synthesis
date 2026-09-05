# Finance QA vNext：不同充分依据路线的构造与有限分离预检

本轮完成了当前授权范围内的来源检查分支，结果为
`source_not_instantiated`。冻结 Archive 中确有明确的二分收入总分结构：
四个独立页面、十二条带不同 FinQA 记录 ID 的记录分别披露了两个组成项及其总额。
但是，同一发行主体、同一年度报告的已冻结原文没有提供完成当前增长率差值任务所需的
两期营业利润。因此没有实例化新任务，也没有创建或执行 D/S 候选。

科学见证 `W = null`，语义类数和同任务路线关系也均为 `null`。
这不是 `W = 0`，不是 D/S 已执行后的负结果，也不是证明真实不同的有效解决行为不存在。
本轮更不能写成“Archive 没有总分关系”：真实收入总分关系已经获得来源见证，
缺失的是与其相容的另外两个必要财务角色。

阶段名称为：

```text
finance_qa_vnext_source_distinct_support_route_constructibility_
and_finite_separation_preflight_only
```

## 1. 与上一轮结果及本轮授权的关系

本轮输入的外部评审及操作指令精确绑定如下：

```text
external review bytes   24,654
external review SHA256  e279cc6ee587766a87b430588fe1632a0d48a3c84f6b9c97a86908523e768dce
operator directive     参照审计继续实验
directive bytes        24
directive SHA256       b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb
```

外部评审说明其访问范围是报告全文、公开标量的独立 Decimal 算术复算及数量关系核对；
没有访问仓库、读取正式目录中的全部原始工件，或执行投影器、比较器与证书检查脚本。
本轮接受其限定审计结论，不将该评审写成额外的源码／正式工件独立重放。

外部评审接受了上一轮固定六条 own-qualified 轨迹的有限公开行为语义比较，
结论是 `PASS_AS_SCOPED`。旧 F1/F2 各自的 B/A/C 在已冻结比较合同下归为一类；
本轮保留这一历史结论，不重新生成旧候选，不追加同内容的独立语义证书审计，
也不继续沿透明 lookup 删除、标签变化或独立运算换序扩样。

本轮根据评审提出的新方向，检查一个新任务是否具有两套真实、独立的充分依据。
设计目标仍是收入增长率与营业利润增长率的绝对差值：

\[
g(v_0,v_1)=\frac{v_1-v_0}{|v_0|}\times100,
\qquad
a=|g(R_0,R_1)-g(I_0,I_1)|.
\]

计划中的 D 路线直接使用已披露的收入总额；S 路线应使用两个独立的收入分项及合法总分依据，
先重建相同期间的收入总额，再完成相同目标。两条路线只有在同一个新冻结任务、
同一个 Evidence universe、同一个答案 Oracle 和验证合同下才可比较。
上述对象在本轮属于待准入设计，没有因读取来源表格而自动成为已实例化的 Task、Binding、
Candidate 或运行授权消费记录。

本轮边界为至多一个新任务、D/S 各一条、来源和合同准入后至多两次实际本地 Runtime 执行。
来源未通过完整绑定准入，所以实际新任务、候选声明、Runtime 执行、own-validation、
有限语义比较均为零。Provider 调用、凭证读取、GPU 使用、训练和分布估计也均为零。
旧主链继续暂停。

## 2. 物理来源与 SourceAuthority

唯一原材料是上一系列已冻结的 FinQA 财务文档快照：

```text
path    trusted_data_synthesis/benchmarks/finqa/frozen/test.json
bytes   14,395,143
SHA256  831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc
records 1,147
```

该来源沿用 `SourceAuthority = curated_database`、`provider = FinQA`。
它是仓库已有的研究数据快照；本轮没有检索发行人原始申报文件，
因此不将其来源权限描述为新增的 original-filing authority。

旧任务曾从该物理 Archive 选中 CDW 与 HII 的两个记录。这两个旧绑定没有被扩充或改写。
本轮新任务的有限来源检查范围是同一个已冻结文件的完整 1,147 条记录；
这不包含其他 FinQA split、TAT-QA、外部网站或废弃的 `raw_financial_data_lake`。

原有 FinQA `test` 的评估用途限制没有转化为训练授权。
本轮只是在当前明确授权下，把既有不可变文件作为离线财务来源材料进行构造性检查；
没有将其题目或答案用于训练、模型采样、Benchmark 频率或任务分布估计。

JSON 容器必须完整解析，但决策只访问：

```text
id, filename, table_ori, pre_text, post_text
```

`qa`、`question`、`answer`、`program`、`exe_ans` 没有进入来源选择或解释。
“未使用 QA 字段”指没有访问这些字段的语义值用于决策，不声称读取文件字节时跳过了
同一 JSON 容器中的某些字节。

## 3. 检查前固定的规则与检查后形成的解释

本轮先固定物理来源、访问字段、结构条件、排序和停止条件，再进行一次有限来源检查。
形式化模块中同时保存两个不同对象：

1. 检查前固定的机械结构筛选规则。
2. 对筛出的有限记录阅读原文后形成的来源解释注释。

第二项明确标记为 `known_source_annotations_not_data_blind`。
注释是已观察来源上的解释结果，不是数据盲的预注册自动选择器。
正式构建和测试中的重放用于检查同一个已固定来源检查是否可复现，
不被计为新候选搜索或额外的科学采样。

### 3.1 机械结构筛选

程序按来源记录 ID 的词典序遍历全部 1,147 条记录。
它取 `table_ori` 每行首项作为行标签，执行 `casefold` 后连接，要求同时满足：

```text
收入标签：\brevenues?\b|\bsales\b

结构标签：\btotal\b|\boperating (income|profit)\b|
          \bincome from operations\b|\bproducts?\b|\bservices?\b
```

筛选保存全部 1,147 条记录的精确 ID、原始数组位置、来源字段哈希、表格哈希、
行标签以及两个机械条件的命中结果。它得到 59 条结构候选，对应 19 个不同来源页面。
这里的“候选”是来源结构候选，不是待执行的 Candidate 轨迹对象。

该筛选不是对 Archive 任意自然语言表述的完备理解器。没有命中固定表格标签结构，
只能表示记录没有进入本轮适配器域，不能据此证明自然语言中不存在其他财务关系。

### 3.2 完整绑定的准入条件

本轮固定采用恰好两个独立披露的收入组成项。来源必须支持它们完整且不重叠地组成目标总额，
期间、单位、币种、定义和合并主体范围相容。不能省略额外的第三项、抵销项或其他未解释组成项。
来源明确列出的 `Other revenues` 可以作为完整补集使用；不能仅因其名称含有 `Other` 而拒绝。

分项总额之外，还必须存在早期收入及两期营业利润。
允许同一来源记录，或同一发行主体、同一报告年度的其他冻结记录共同提供这些角色；
不允许跨主体拼接或在没有定义与范围依据时跨报告年移植数值。
若全部角色落实，早期增长率基数还必须非零。

如果存在多个完整绑定，预先固定的顺序是：来源记录 ID 词典序、later 财务期间升序、
最近的可比 earlier 期间、支持记录 ID 词典序，选择首个完整准入的绑定。
本轮没有任何完整绑定，所以没有选择新任务的早晚期间，也没有计算增长率差值答案。

没有按两数之和是否恰好等于总额筛选，没有通过执行两条路线寻找答案相同的案例，
也没有在失败后替换候选直到成功。

### 3.3 来源解释与精确绑定

19 个已观察页面的解释按精确 `filename` 绑定。
每条实际候选另绑定记录 ID、原始数组位置、来源字段 SHA-256、表格 SHA-256，
并保存表格行及相关 `pre_text` / `post_text` 的精确 JSON pointer、原始来源值和哈希。
它不是仅凭公司代码推断拒绝原因的通用分类器。

59 条注释合计包含 1,083 个来源引用。
哈希采用规范 JSON 序列化后的 UTF-8 字节；引用保存的是原始字符串或原始表格行的值，
不把 JSON 格式空白差异误称为原始数值变化。

## 4. 来源结果与具体缺口

59 条结构候选的有限来源解释如下：

| 拒绝条件 | 记录数 | 具体来源边界 |
| --- | ---: | --- |
| 存在收入与营业利润，但没有完整的二分收入披露 | 6 | CDW、HII；`Sales and service revenues` 是一行标量，不能拆成两个原始 Evidence |
| 分部范围且没有完整二分收入结构 | 16 | APD、IP、LMT 的相关分部表格 |
| 明示组成项超过两个 | 10 | ANSS 地域收入、FIS 三项分部收入、MRK 多项顶层收入；本轮不改成多分项路线 |
| 真实合并收入二分结构存在，但同报告两期营业利润缺失 | 12 | JPM 与 UNP 的四个独立来源页面 |
| Special Asset Pool 范围且营业利润缺失 | 2 | Citi 的 SAP 表格，不能冒称集团合并收入 |
| total 不是本期收入总额 | 13 | 处置收益净额、衍生工具损失或应计负债等表格 |
| 合计 | 59 | 全部来源结构候选均保留 |

这些计数不是模型采样频率，也不是新任务数或语义类数。

### 4.1 已获得来源见证的真实收入二分结构

| 代表记录 | 两个独立披露组成项 | 总额 | 表格行索引 | 同页记录数 |
| --- | --- | --- | --- | ---: |
| `JPM/2014/page_70.pdf-1` | Noninterest revenue；Net interest income | Total net revenue | 9、10 → 11 | 2 |
| `JPM/2015/page_82.pdf-1` | Noninterest revenue；Net interest income | Total net revenue | 9、10 → 11 | 2 |
| `UNP/2015/page_56.pdf-1` | Total freight revenues；Other revenues | Total operating revenues | 7、8 → 9 | 4 |
| `UNP/2016/page_52.pdf-1` | Total freight revenues；Other revenues | Total operating revenues | 7、8 → 9 | 4 |

行索引均从零开始，来源列头、组成项和总额的原始行已保存于工件。
JPM 的上下文明确是 reported basis 下的 consolidated results of operations，
表格单位为 millions。其前面的手续费等明细位于 Noninterest revenue 小计之内，
不是与该小计并列的额外收入组成项。

UNP 的上下文说明主体是 Union Pacific Corporation 及其子公司，
同页原文还说明合并范围和内部交易抵销。
六个货运品类位于 Total freight revenues 小计之内，
该小计与单独披露的 Other revenues 共同构成 Total operating revenues。
这些关系来自来源表格层次及上下文解释，没有用数值碰巧相等代替完整性和不重叠依据。

### 4.2 同页记录别名的处理

十二条记录对应四个来源页面；本轮不将它们计为十二套独立来源。
每个关系见证的 alias group 对所有同页记录重新读取实际使用的列头、两条组成项行和总额行，
并要求这些原始行完全相同。
每个成员分别保存来源字段哈希、整表哈希、所用行哈希及所用行的精确来源引用。

实际检查得到四组成员数 `2 / 2 / 4 / 4`，每组所用行哈希均只有一个不同值。
相同 `filename` 本身不足以成立别名关系；实际所用来源行相等才是本轮的有限依据。
这不宣称整条 FinQA 记录字节相同，也不要求未使用的上下文一定完全相同。

这是一项来源别名核对，没有创建或执行“别名攻击”Runtime 轨迹，
也没有据此宣称完成了新路线验证器的别名负控。

### 4.3 缺失的营业利润角色

对上述可形成二分收入结构的发行主体与报告年度，以及 Citi SAP 候选，
来源检查进一步核对同一报告域的全部冻结记录：

| 同一发行主体／报告年度 | 记录数 |
| --- | ---: |
| `C/2009` | 9 |
| `JPM/2014` | 4 |
| `JPM/2015` | 6 |
| `UNP/2015` | 4 |
| `UNP/2016` | 4 |
| 合计 | 27 |

程序从这 27 条记录的真实 `table_ori`、`pre_text` 和 `post_text` 重算营业利润词项命中，
识别 `operating income/profit/earnings/loss`、`income from operations` 和
`profit from operations`。实际命中为零。
精确记录域、访问字段、元素数、来源字段哈希和实际命中列表均已保存。

词项检查是对有限原文阅读结论的可复现支持，不是任意自然语言“绝不存在”的形式证明。
限定结论是：本轮允许的同主体、同报告年度来源快照，未落实 `income_earlier` 与
`income_later` 两个必要角色。

不能将净利润、税前利润、经营费用或 SAP 的其他收益概念替代营业利润，
也不能通过计算一个数字并将其标为原始 Evidence 来补齐这两个角色。

## 5. Primitive 检查仅限元数据

本轮检查了现有 `aggregate`、`growth`、有序百分点差和绝对百分点差的注册合同。
这是注册元数据及实际实现约束的只读检查，没有针对一个已实例化 Binding 完成相容性准入。

`aggregate` 的注册语义版本为 `1.1.0`，输入次序策略为 `permutation_invariant`，
可变长输入角色为 `observations`。实际 executor 默认聚合方式是 `mean`；
未来若来源和合同允许重建收入总额，必须明确要求 `method = sum`，不能依赖默认值。

实际 `same_metric_unit_definition` 相容性检查比较
`predicate`、`payload_context`、`definition`。
`growth` 的 `same_series` 还比较主体、时间基准、频率和 scope type 等字段。
这些字段从实际 `validate_compatibility` 实现中检查，不能因为 executor 可以计算数字，
就绕过真实 Evidence 的相容性要求。

上述 primitive 没有自行证明来源组成项完整、不重叠、同期间、同主体范围或抵销关系。
如果未来分项与总额的实际定义不相容，不能通过借用总额的 Evidence、改写分项元数据或空 lineage
声称已通过。具体处理取决于未来真正实例化的来源和新局部合同；本轮没有对此给出通过结论。

本轮没有新增 primitive、Catalog 注册、总分重建组合合同、Task/Binding Schema 或无来源可运行的
Runtime，也没有调用 primitive executor 或数值 oracle。
旧四 Evidence Runtime 和旧有序、空参数的公开图投影器，没有被假定为已支持新的 aggregate 路线。

## 6. Gate 与科学结果的解释

本轮 Gate 要区分已完成检查、未实例化对象与未执行分支：

| Gate | 对象 | 正确状态与含义 |
| --- | --- | --- |
| G0 | 授权与冻结输入身份 | `PASS` |
| G1 | 有界来源检查及缺失角色证据 | `PASS` |
| G2 | 完整新任务及两套充分支持的来源绑定 | `NOT_INSTANTIATED` |
| G3 | 新路线执行、own-validation 和有限语义比较 | `NOT_RUN_SOURCE_UNAVAILABLE` |
| G4 | `null` 见证与零执行边界 | `PASS` |

Gate 汇总为 `3 PASS / 0 FAIL / 1 NOT_INSTANTIATED / 1 NOT_RUN`。
不得将来源分支完成写成全部 Gate 通过，也不得以元数据检查、来源引用数量或控制通过数，
补偿未落实的营业利润 Evidence。

计划中的多类见证是：

\[
W(x^\ast)=\mathbf 1[
V_Q(\tau_D)=V_Q(\tau_S)=1
\;\land\;
\tau_D\not\sim_{\Omega_{x^\ast}}\tau_S].
\]

本轮没有足够输入使这个命题获得 `0` 或 `1`：`x*` 没有实例化，
两条轨迹、对应 Validity 以及比较关系均不存在。因此：

```text
status                         source_not_instantiated
scientific_witness W           null
formal_semantic_class_count    null
same_task_finite_relation      null
new_task_instances             0
candidate_runtime_executions   0
own_route_validations          0
finite_comparisons             0
```

这既不是“多状态构造成功”，也不是“已证明只有一个状态”。

## 7. 可复现性与独立来源引用复核

来源实现位于：

```text
trusted_data_synthesis/src/trusted_synthesis/experiments/
qa_reasoning_source_distinct_support/source.py
```

`selection_policy()` 可在正式来源重放前单独保存选择规则。
`scan_archive(repo_root)` 验证冻结 Archive 字节身份，重放同一个 1,147 条记录的固定结构检查，
并恢复已观察来源上的注释、真实总分关系见证与缺失角色证据。

对正式来源模块的输出还执行了一条独立只读复核路径。
复核器使用标准库 `json` 与 `hashlib` 独立实现相同的规范 JSON 编码，
没有导入来源模块的哈希辅助函数或复用其引用判定逻辑。
它逐项回到冻结原文解析 JSON pointer，并比较原始来源值及其哈希。

| 独立复核项目 | 实际结果 |
| --- | ---: |
| 完整记录目录的来源字段与表格哈希 | 1,147 通过 |
| 有限来源解释注释 | 59 通过 |
| 注释的来源定位与值哈希 | 1,083 通过 |
| 加上关系见证和别名成员后的全部来源引用 | 1,159 通过 |
| 真实收入关系页面／所用行别名记录 | 4 / 12 通过 |
| 同报告营业利润支持域 | 27 条记录逐项核对 |
| 独立重算的营业利润词项命中 | 0 |

这项复核证明本轮保存的定位、引用值、哈希、别名所用行和有限词项结果与冻结原文一致。
它不是 D/S 执行验证，不替代未来的来源完整性合同，也不证明适配器覆盖任意自然语言。
源码的 Ruff 格式与 lint 检查通过。

正式实现另有五项来源结果 Schema 控制：分别尝试把来源未实例化改写为 `W = 0`、
`W = 1`、一个语义类、一次 Runtime 执行以及两路线构造通过。
五项实际尝试全部被严格的未实例化结果合同拒绝。它们是结果边界控制，
不是分项遗漏、期间不匹配或错误消费总额等金融 Runtime 攻击。
本轮没有为尚未实例化的 D/S 轨迹声称完成后者。

### 7.1 正式工件与精确身份

正式目录：

```text
trusted_data_synthesis/artifacts/qa_reasoning_source_distinct_support/
finance_qa_vnext_source_distinct_support_route_constructibility_and_finite_separation_preflight_v1_20260905
```

目录实际包含 20 个文件、1,251,021 字节。自排除的 Manifest 绑定 19 个成员、
1,247,928 字节；Manifest 自身为 3,093 字节。
正式目录与首次空目录临时构建逐路径、逐文件字节相同。
形式化源码绑定为：

```text
implementation commit 82e5505dbb16a83cf704399f405602614c0a0d25
implementation tree   ea0b53e5b3b4dc81c053aef401f62052163fe81d
implementation files  5
implementation bytes  53,117
```

五个实现文件和十个声明引用文件的已提交／当前字节匹配，Archive 也独立绑定原 Git blob。
这一冻结没有宣称全部传递导入或完整运行环境闭包。

关键正式身份如下：

```text
source policy
qa_source_distinct_support_source_policy:4a8d507e09d9caac455c3242cf3fa535eea5d115728eb1e1cb3aa1e31ce1c061

source census
qa_source_distinct_support_source_census_summary:947200a0ce03e7ca48dca4a68a6013ef4c07b1d32c9c41bc8ef0f00e7178ef30

Gate
qa_source_distinct_support_gate:629172091ec6b2e6b182a040488a78c10fb01ce8e47ea28d66c17eeaab79d76e

decision
qa_source_distinct_support_decision:1e55344b7cabc4d8a38776e9c1eeb4e6c1aab1c0560bed3bfdcfbd0f8dccae59

report
qa_source_distinct_support_report:aed6e919f195286c251db61f9f34c6f95bc13bd1b50ab7ecc62220b0926e1baf

transition
qa_source_distinct_support_transition:155fa49a154f8ff5594698f59e67a84fe3dd68e94cf3058b271651cd6270ceda

manifest
qa_source_distinct_support_manifest:7d1f92e85a9cfaadbde5f3774a5898283270d1bf7d4a75409513bbff3e790f3c

artifact root
qa_source_distinct_support_root:27047db451b404e972da64ca7b61902cdf79db05bdae129aa3a260d2946e4e60
```

来源目录、59 条注释、四个关系见证和 27 条营业利润检查分别保存在
`archive_record_catalog.jsonl`、`candidate_source_dispositions.jsonl`、
`source_relation_witnesses.jsonl` 和 `same_report_income_check.json`。
完整汇总与来源选择规则分别保存在 `source_census_summary.json` 和 `source_policy.json`。

`policy_freeze_receipt.json` 记录来源重放开始前的持久化：
策略 JSON 的写入及相应目录同步在正式重放前完成。
这里冻结的是已声明规则和已知来源注释的重放上下文，不把形式化持久化的时间，
回写为第一次人工阅读原文之前就已存在的来源解释。

### 7.2 专项验证

正式专项测试为 `17 / 17 PASS`，本次执行耗时 3.77 秒。
Mypy 对五个实现文件的检查以及 Python 编译检查均通过。
本轮五个实现文件与一个测试文件的专项 Ruff 检查全部通过，六个文件的格式检查通过。

对整个 `src` / `tests` 运行 Ruff 时仍有一项既有诊断：
`phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution_models.py:2`
的 `I001` 导入排序问题，与旧轮报告一致。
因此本报告不将全包 Ruff 描述为通过；本轮没有改写该历史模型源码。

专项测试包括：

- 原始外部评审和旧工件的精确冻结身份。
- 固定来源域、机械筛选数量、已知来源注释及无答案选择。
- 真实收入二分结构与完整任务未实例化的区分。
- 27 条原文的营业利润缺口重算，以及 1,159 个来源引用的独立定位／哈希核对。
- 实际所用行的来源别名依据；不以同页记录数作为独立支持数。
- 对 QA 字段访问设置保护，确认来源适配器只访问已列明的五个字段。
- 来源策略在正式重放前持久化。
- 对旧 Runtime、旧比较 builder、primitive executor 和 oracle 设置禁止调用保护。
- 具体 Evidence 相容性未评估与注册元数据检查通过的区分。
- 五项禁止伪造 `W`、类数、执行数或两路线成功的结果 Schema 控制。
- Gate 状态、空目录确定性重建以及历史工件不变；对复用已存在输出目录予以拒绝。

可复现的专项测试命令：

```bash
cd trusted_data_synthesis
.venv/bin/pytest -q tests/test_qa_reasoning_source_distinct_support.py
```

测试重建使用新的临时输出目录，不覆盖正式目录，不新增候选 Runtime 执行。
这些测试和正式来源构建不是 D/S 科学执行；通过测试不能将 `W = null` 改写为其他值。

## 8. 收口与下一步边界

本轮来源分支可以收口：当前授权的有限来源对象已经检查，拒绝原因和缺失角色已经保存，
来源未落实的执行分支保持未运行，没有继续更换变化轴搜索成功案例。

后续若要实现同一个增长率差值任务的 D/S 路线，需要在另行确定的来源范围中补齐：
具有真实完整二分收入结构的同一主体、相同财务期间、相同单位和定义下的两期营业利润。
也可以在后续明确授权下重新设计任务或分项数；不能把这种范围变化倒写成本轮原合同的结果。

即使未来来源落实，仍须针对实际 Evidence 检查 primitive 相容性、冻结新任务共同上下文、
执行各一条真实路线、完成 own-validation，并在新测量版本中解释真实依据支持与非透明推导依赖。
本轮的元数据检查不能替代这些尚未实施的步骤。

本轮没有提供模型可达性、生成概率、状态频率、Contribution、训练贡献或 VTDO 更新的证据。
