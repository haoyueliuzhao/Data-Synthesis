# Finance QA vNext：同期间收入构成占比的不同充分依据预检

本轮采用已经获得来源见证的 Union Pacific 收入总分表，新建单期间货运收入占比任务。
来源绑定已完成：实际表头选择 2015 年，货运收入、其他收入和经营收入总额分别为
20,397、1,416 和 21,813，共同单位为原表所示 `Millions`。
这些数值是三个分别披露的原始来源值；来源绑定阶段没有计算求和或占比答案。

本轮已完成 D/S 各一次实际 Runtime 执行：D 两步、S 三步，两条均通过答案与轨迹验证，
最终答案均为 **93.508458%**。有限比较得到 `different_retained_semantics`，
`W_share = 1`，正式有限语义类数为 2；五项 Gate 全部通过，八个直接控制全部被拒绝。

这一结果证明该固定任务上，两条确定性构造的有效行为保留了不同的分母支持及推导关系。
它不改写旧任务的 `W = null`，也不构成模型可达性、推理深度或训练效果的结果。

阶段身份为：

```text
finance_qa_vnext_part_whole_share_dual_support_preflight_only
```

## 1. 为什么新建任务，以及保留哪些历史结果

上一轮限定审计结论为 `PASS_AS_SCOPED`，通过对象是“有界来源检查及正确停止”。
上一轮实际结果继续保持：

```text
3 PASS / 0 FAIL / 1 NOT_INSTANTIATED / 1 NOT_RUN
source_not_instantiated
W = null
```

上一轮在固定 Archive 中已经找到真实收入总分关系，但没有落实与之相容的两期营业利润，
因此没有实例化收入增长率与营业利润增长率差值任务，也没有执行 D/S。
“找到了收入总分关系”与“旧复合任务尚未实例化”同时成立。
本轮没有改变旧任务目标后回写通过，也没有把旧的 `W = null` 改成 0 或 1。
旧来源阶段的 20 个正式文件以及更早 F1/F2 的有限比较结果均保留。

本轮研究问题收缩为：在同一期间、同一主体、同一冻结来源及答案目标下，
披露总额直取和真实分项重建能否形成两条 own-qualified，且具有不同保留支持语义的公开行为。
这使实验直接针对“不同充分依据”机制，不再要求与该机制无直接关系的营业利润或第二期间。

这种任务调整有明确代价：本轮不检验旧增长率差值任务的分支合并深度。
即使 S 多一步，也不能推断关键推理更深、共同 coverage 更高或 Contribution 更大。
本轮也不比较训练分布，不把新旧任务的差异归因于 VTDO 的策略分布更新。

## 2. 外部审计输入及其证据层级

本轮外部审查输入身份为：

```text
review bytes   22,925
review SHA256  91ed0480d5e235c0438c01a89a8ea58add7a03fe6872523ce4f6b2d6b4837125
directive      参照审计继续实验
directive SHA256
b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb
```

外部审查声明其依据是前一轮报告全文、已有理论合同及报告内数量关系；没有读取仓库中的
FinQA 原始文件、正式 JSON 工件或源码，也没有重跑来源检查器和测试。
本轮接受该审查在其已说明范围内的结论，不将它扩写为针对新 Runtime 或新语义比较的独立审计。

本轮代码与测试另行完成目标原始记录的引用复现。来源引用复现、局部执行有效性与有限语义比较
是三个不同层次，分别需要自己的实际证据。

## 3. 固定来源域：一个页面组，四个保存索引

唯一物理原材料仍为已有冻结 FinQA 文件：

```text
path    trusted_data_synthesis/benchmarks/finqa/frozen/test.json
bytes   14,395,143
SHA256  831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc
records 1,147
```

`SourceAuthority = curated_database`，`provider = FinQA`。
这是仓库已有财务文档快照，不是本轮新增的发行人原始申报文件 authority。
本轮没有重新检索整个 Archive，没有扩展到其他 split、发行人、报告年度、页面组或外部来源，
也没有访问废弃的 financial data lake。

目标来源固定为 `UNP/2015/page_56.pdf-1` 所属页面组。
实现先读取历史 `source_relation_witnesses.jsonl` 中零基索引为 2 的那一行，
只解析目标见证，不重新解释其他三行来源见证。

```text
saved witness file SHA256
f62e894779a381a4646c1c94d73271761930471aee6899041a0784bfca2157ce

saved target line SHA256
44b27b6136e05f6eeb28387c9ab5afe976276c025f3bf685badb3d39e4115143
```

目标行中保存的索引和记录 ID 必须与以下固定域完全一致：

| 原始数组索引 | FinQA 记录 ID |
| ---: | --- |
| 30 | `UNP/2015/page_56.pdf-1` |
| 981 | `UNP/2015/page_56.pdf-2` |
| 1065 | `UNP/2015/page_56.pdf-3` |
| 1099 | `UNP/2015/page_56.pdf-4` |

源文件需要完整读取、校验哈希并解析 JSON 容器，但是语义访问只发生于这四个保存索引。
实现没有遍历 1,147 条记录寻找匹配 ID，没有重新执行旧表格标签筛选，也没有进行同报告收入或利润搜索。
每条目标记录只投影以下字段：

```text
id, filename, table_ori, pre_text, post_text
```

`qa`、`question`、`answer`、`program`、`exe_ans` 不进入来源选择、期间解释或数值绑定。
“不访问 QA 语义值”不表示读取容器字节时能够跳过 QA 字段的物理字节。
这项离线构造性使用没有产生训练授权、数据盲资格、总体覆盖率或 Benchmark 抽样频率声明。

## 4. 先固定列规则，再绑定实际期间

首次读取本轮目标列头和数值前，先明确下述选择规则；新来源模块保存该规则，
并在正式来源重放前持久化。这里不将正式文件的保存时间倒写成首次原文阅读时间：

> 只在固定页面组内选择最新、年度期间可解释、三个 F/O/T 单元格均为完整有限十进制数，
> 且具有明确共同单位和合并主体范围的列；年份降序、同年份列索引升序。

该规则不使用 F 与 O 的和是否等于 T，不使用占比答案或路线执行结果。
若固定目标不能完成绑定，应保留具体来源缺口并停止，不更换页面、问题或候选直到得到两个类。

本轮属于 `known_source_targeted_mechanism_design_not_data_blind`。
它沿用已知来源结构开展定向机制设计；对页面层次及上下文的解释是已知来源上的 host annotation，
不能描述为首次看到任意文档之前已经预注册的通用识别器。

实际原始表头为：

```text
/30/table_ori/0 = ["Millions", "2015", "2014", "2013"]
```

三个年份列均通过完整有限数值检查，因此选择列索引 1，即表头中的 `2015`。
期间来自实际表头，且由同页讨论 2015、2014、2013 年收入的上下文加以佐证。
目录名中的 `2015` 没有被用作财务期间证据；也没有凭空补入精确期末日期。

## 5. 三个数值来源及口径

以下行列索引均为零基索引。三个值保留为精确十进制字符串，没有浮点转换。

| 角色 | 实际行标签 | 原始单元格 | 规范十进制字符串 | 单元格 JSON pointer |
| --- | --- | --- | --- | --- |
| F | `Total freight revenues` | `$20,397` | `20397` | `/30/table_ori/7/1` |
| O | `Other revenues` | `1,416` | `1416` | `/30/table_ori/8/1` |
| T | `Total operating revenues` | `$21,813` | `21813` | `/30/table_ori/9/1` |

数值规范化仅移除货币符号和千位分隔符，使用有限 `Decimal` 解析；不计算求和或目标占比。
F、O、T 保持三个不同指标：

```text
total_freight_revenues
other_revenues
total_operating_revenues
```

三个 `definition` 分别保留各自原始行标签，没有将 F/O 改写为总额指标或总额定义。

主体及口径的实际依据为：

| 来源引用 | 用于绑定的内容 |
| --- | --- |
| `/30/pre_text/0` | 说明 Union Pacific Corporation 及其子公司，包括 Union Pacific Railroad Company |
| `/30/pre_text/10` | 说明后续表格提供按 commodity group 列示的 freight revenue |
| `/30/post_text/2` | 同页讨论 2015、2014、2013 年相关货运收入，佐证实际年份列含义 |
| `/30/post_text/7` | 明确合并财务报表包含 Union Pacific Corporation 及所有子公司账户 |
| `/30/post_text/9` | 明确消除全部内部交易 |

统一绑定为：

```text
subject  Union Pacific Corporation and subsidiaries
scope    consolidated_issuer
period   2015
unit     millions
currency dollar_as_disclosed
```

`Millions` 是实际表头。表中 F/T 使用 `$`，O 继承同一货币表格的记账单位。
允许的快照没有在这些引用中明确给出 ISO 币种代码，所以不额外断言 `USD`。
这一限定在来源解释中明确保存。占比任务的分子、分母使用相同货币与规模，不进行货币兑换。

## 6. 总分关系是结构证据，不是假造的数值证据

实际表格共 10 行：第 0 行为表头，第 1–6 行为六个 commodity 明细，
第 7 行为货运收入小计，第 8 行为 Other revenues，第 9 行为总经营收入。
六个明细位于货运收入小计内部，不是与该小计并列的额外顶层组成项。

完整表格中，`Total freight revenues` 和 `Other revenues` 紧接在
`Total operating revenues` 之前；结合合并范围及内部交易抵销说明，
本轮解释为两个完整且不重叠的顶层收入类别组成该总额。
这里允许明确列示的 `Other revenues` 作为补集；不能仅因为名称含有 Other 就自动拒绝。

这是对固定来源表格层次和上下文的有限 host interpretation。
它不声称原始数据存在一个写着 `F + O = T` 的数值单元格，也不以数值恰好相等证明组成关系。
关系证据类型为 `part_whole`，没有 `value` 字段，保存：

```text
member_ids = [F 的内容 ID, O 的内容 ID]
total_id = T 的内容 ID
exhaustive = true
nonoverlapping = true
numeric_value_cell_exists = false
numeric_sum_computed_for_admission = false
```

关系证据包含完整十行表格和相关上下文引用，因此其来源片段也包含披露总额行。
这不意味着 S 的数值执行可以读取 T 作为分母；是否实际使用披露总额，须由执行输入及后续 Claim 依赖判断。
关系中的 `total_id` 用来说明重建目标的指标身份，不能冒充 S 已经消费 T 的数值，也不能取代真实求和。

## 7. 同页别名及引用复现

四条 FinQA 记录的来源字段哈希不同，但表格哈希一致；实际使用的表头、F/O/T 三行也完全相同。
实现对每个成员逐一核对来源字段哈希、整表哈希、所用行哈希以及历史保存指针的原始值。
只凭相同 `filename` 不足以成立本轮别名关系。

四条记录始终计为一个来源页面，不计为四套独立充分依据。
本轮不要求未使用上下文全部相同，也不宣称整条 FinQA 记录字节相同。

来源绑定对象中引用出现次数的实际分解为：

| 存放位置 | 引用出现次数 |
| --- | ---: |
| 绑定根对象的完整表格与上下文 | 15 |
| `selected_raw_cells` 的三个数值单元格 | 3 |
| 三个数值 Evidence 的引用 | 24 |
| 非数值关系 Evidence 的引用 | 15 |
| 四个别名成员各四个所用行引用 | 16 |
| 合计 | 73 |

这 73 次出现对应 33 个不同 JSON pointer。
重复出现来自不同工件对象对同一原始位置的引用，不是新增来源或独立证据数量。
测试使用独立 JSON 序列化及 SHA-256，逐引用解析原始值和哈希，并核对绑定及四个 Evidence 的内容 ID。

来源绑定的已核对身份为：

```text
part_whole_share_source_binding:
c1936c263ade54d4391eef11d3c1c93932e3bd959dd4e18b6c1c5a412612a254

canonical JSON bytes 61,877
```

该来源身份不包含答案计算、候选执行或语义类数。

## 8. 同一任务、共同信息与两条实际支持路线

新任务问题为：Union Pacific Corporation 及子公司在 2015 年，货运收入占总经营收入的百分比是多少，
按冻结格式报告并给出实际计算支持的引用。

共同目标为：

\[
y = 100\frac{F}{T}.
\]

D/S 共享同一任务身份、验证上下文、Evidence universe、可用工具、答案 Oracle、输出格式和预算。
共同可见 Evidence universe 包含 F、O、T 以及真实总分关系。
共同可见信息相同，不要求实际支持子集相同。

| 路线 | 分母的真实来源 | 冻结的公开操作 |
| --- | --- | --- |
| D | 读取披露总额 Evidence T | `share_ratio → scale_percent` |
| S | 使用 F/O 及关系证据实际求和得到总额 Claim | `relation_sum(method=sum) → share_ratio → scale_percent` |

D 的冻结计划为两次操作，S 的冻结计划为三次操作；正式执行分别完成 2 次和 3 次操作，
与计划一致。每条路线只执行了一次，没有替换候选或追加 Runtime 尝试。
分子 F 在两条路线中保持相同，唯一研究因素是分母支持与推导关系。

所有行动前提案和接受 Observation 的更新均标记 `deterministic_fixture`。
不能把确定性控制器生成提案的行为描述为模型已经学会自主选择依据或根据 Observation 更新。

## 9. 为什么新增局部 relation-aware 接口

已有 `aggregate` 默认使用 `mean`，并检查 predicate、payload_context、definition 等同指标兼容性。
F/O 是不同的真实指标，直接把二者的元数据改成 Total 会抹掉本轮要研究的来源差异。

本轮使用独立、有限的 `relation_sum` 合同，其参数必须精确为 `method=sum`。
它在求和前检查实际成员集合、重复或遗漏、共同期间、单位、币种、主体范围以及来源关系身份，
并要求原始分项的数值、指标和定义未被改写。

求和内核只读取两个成员的数值。输出是推导的总额 Claim，保留 F、O、关系三个 Evidence 的 lineage，
不创建一个没有来源链的新原始事实。
T 的指标和定义用于声明输出类型，不把披露的 T 数值作为求和内核输入。

`share_ratio` 另行检查 freight 分子和 operating-revenue 分母角色。
分母可以是绑定的披露总额 Evidence，也可以是具有实际 `relation_sum` 生产节点及分项 lineage 的已接受 Claim。
S 后续比例步骤必须消费该推导 Claim，不能仅在解释文字中声称使用了分项、实际仍消费 T。

局部新接口不修改旧 aggregate Validator，不提升为通用金融组合系统，也不自动注册到旧主链。

## 10. 冻结数值合同、执行与独立验证边界

新合同固定使用 50 位 Decimal 工作精度、`ROUND_HALF_EVEN`，最终输出六位小数，量化粒度为 `0.000001`。
来源重建与披露总额核对容差为 0，最终答案容差为 0；这些规则已在正式执行前冻结。
若显示精度造成差异，应按固定合同报告失败，不事后调整容差或将重建值强行替换为披露值。

每步的实际顺序应是：解析当前可见输入，持久化行动前 proposal，执行语义准入，
持久化 receipt 并回读 proposal/receipt 字节，然后调用数值内核，保存 execution、Observation、
已接受 Claim、update 和更新后 state。文件使用 no-replace 写入，并同步文件及目录。
接口同时检查 source、contract、task 的来源绑定身份一致。

这项顺序要求把“实际执行前已有提案及准入证据”与执行后重写解释区别开来。
由确定性控制器执行该顺序，不形成模型决策能力声明。

有效性继续定义为：

\[
V_Q = V_{\mathrm{QA}} \land V_{\mathrm{trajectory}}.
\]

共同任务义务为期间与范围、分子和分母角色、百分比单位、Final grounding。
S 另有完整不重叠分项及实际总额 Claim 被消费的路线前提，但这些前提不要求 D 必须执行求和，
也不改变共同 coverage 分母。

答案 Oracle 可以从披露 F/T 计算共同答案目标。
独立轨迹验证则须从实际分项重算 S，并检查 ratio 的真实 Claim 消费边、来源链、参数、更新及 Final。
Oracle 计算不能被记录成 S 执行过的操作。

## 11. 有限比较与科学见证

新测量合同只解释本轮必要对象：显式 `sum` 参数、来源关系依据、异质分项角色、非透明总额 Claim、
可交换求和成员及有序比例角色。它不是通用 Mapper。

有限比较应保留真实支持使用边、分子与分母身份、合法组成关系、Claim grounding、推导依赖和实际更新。
两个合法求和成员换序可以不改变语义，但重复一个成员、遗漏成员或替换成员不能借交换律通过。
路线标签、输出值相同或多一个操作节点，都不能独自决定等价或不等价。

新任务使用独立见证：

\[
W_{\mathrm{share}}(x)=\mathbf{1}
\left[V_Q(\tau_D)=V_Q(\tau_S)=1
\land \tau_D\not\sim_{\Omega_x}\tau_S\right].
\]

两条轨迹均通过 own-validation 且投影完整解释保留对象时，等价对应 0，保留语义不同对应 1。
若来源或任务合同未落实，见证保持 null；若两条均有效但新结构无法完整解释，比较保持 undetermined，
见证及相应类数也保持 null。完整、已绑定的两条轨迹都完成评估但某条无效时，代码记录无多类见证
（W_share 为 0），不为不完整的 Qualified 域赋予正式类数；候选失败保留，不修改规则或替换候选。

即使最终获得 `W_share = 1`，也只说明这个固定任务存在两种确定性构造支持行为，
不证明统计独立来源、多任务覆盖、更高模型能力、训练分布改善或任务深度提升。

## 12. 来源测试

新增来源测试文件为 `tests/test_qa_reasoning_part_whole_share_source.py`。
首次限定运行结果为 **8 passed in 0.41s**，Ruff 检查通过。
来源模块本身的 Ruff、Mypy 及只读加载检查也通过。

这八项测试覆盖：

1. 唯一物理来源、精确四索引、一个页面组、零来源算术及权限声明。
2. 全部 73 次引用的原始值、哈希、33 个不同指针以及五个来源对象的内容 ID。
3. 实际 guard 禁止容器遍历和非目标索引访问，并禁止白名单外字段访问。
4. 实际表头年份、共同 Millions 单位、币种限定及合并范围上下文。
5. 三个真实指标和定义保持不同，关系没有数值单元格。
6. 四条别名的所用行相同，但来源字段哈希不同，始终只计一个页面。
7. Archive 字节在内存中改变时，于重新解释来源之前停止。
8. 历史见证文件字节在内存中改变时，于重新解释来源之前停止。

这些测试不调用候选构造器、Runtime、数值执行器或答案 Oracle；字节篡改仅通过测试替身发生在内存中，
原始 Archive 和历史见证文件没有被改写。
来源只读重放不能冒充两条候选的正式执行，也不支持提前填写 `W_share`。

最终专项验证覆盖三个测试文件，合计 **27/27 通过，2.13 秒**：

| 专项 | 通过数 | 范围 |
| --- | ---: | --- |
| 来源 | 8 | 四索引、引用、字段访问及类型边界 |
| 独立语义验证与比较 | 12 | 实际依赖、保留语义及相关直接控制 |
| 编排与无 Runtime 重建 | 7 | 冻结、文件完整性、零新增执行和重建字节一致性 |
| 合计 | 27 | 本轮专项 |

11 个本轮源码／测试文件的 Ruff check 与 format 检查通过，8 个源码文件的 Mypy 检查通过，
源码 PyCompile 检查通过。另行扩大到整个 `src/tests` 的 Ruff 检查仅报告一个已有问题：
`phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution_models.py:2` 的 `I001` 导入排序；
该历史文件不在本轮修改范围内，没有为修复它改动历史实现。

无 Runtime 重建测试将 `run_candidate`、三个数值执行器的 `execute`，
以及旧来源 `scan_archive` 全部替换为禁止调用的 guard。
然后使用正式目录作为 `replay_from`，复制原 Runtime 字节，独立复算来源绑定、验证及报告。
重建结果与正式目录的 65 个文件逐路径、逐文件字节完全一致，总量仍为 254,479 字节；
旧来源阶段 20 个文件也保持不变。

这一重建产生的新 Runtime 调用数为 **0**。它复用了两条既有执行的持久化结果，
没有重新运行两条轨迹，也不是新增的候选采样。整个实验的正式正向 Runtime 总数仍为 **2**。

## 13. 实际执行、own-validation 与有限语义差异

正式执行和验证结果如下，全部来自已有工件的实际内容：

| 项目 | D | S |
| --- | --- | --- |
| 实际 Runtime 候选次数 | 1 | 1 |
| 实际操作数 | 2 | 3 |
| 操作顺序 | ratio → percent | sum → ratio → percent |
| ratio 实际分母类型 | 披露总额 Evidence | 已接受的推导总额 Claim |
| ratio 实际分母数值 | 21813 | 21813 |
| Final | 93.508458 percent | 93.508458 percent |
| `qa_valid` | true | true |
| `trajectory_valid` | true | true |
| `qualified` | true | true |
| 共同 coverage | 4/4 | 4/4 |

两条轨迹的工作精度下 ratio Observation 均为：

```text
0.93508458258836473662494842525099711181405583826159
```

百分比 Observation 均为：

```text
93.508458258836473662494842525099711181405583826159
```

Final 依照执行前冻结的六位小数量化规则输出 `93.508458`，单位 `percent`。
这里的数值摘录来自实际 execution / Observation / Final，不是额外的 Runtime 执行。

两条路线的支持链实际不同：

```text
D
  F Evidence ──────────────┐
  T disclosed Evidence ────┴→ ratio Claim → percent Claim → Final

S
  F Evidence ─┐
  O Evidence ─┼→ relation_sum(method=sum) → accepted total Claim ─┐
  relation ───┘                                               │
  F Evidence ─────────────────────────────────────────────────┴→ ratio Claim
                                                               → percent Claim → Final
```

S 的 `relation_sum` 实际输入为 F=`20397`、O=`1416` 及非数值关系 Evidence，
实际输出 `21813`。随后 `share_ratio` 的 denominator 引用确实指向这一步的 Claim：

```text
part_whole_share_claim:59909b4d140b098505050a71b3db559d16da78357263bb4cc31f1fa44510070a
```

D 的对应 denominator 引用则指向披露总额 Evidence：

```text
part_whole_share_numeric_evidence:033a430a60a5d3243f701d231a10b71564b48b2abeae58d635c42a2811e7638f
```

D 的 Final grounding 为 F/T 两个数值 Evidence；S 的 Final grounding 为 F/O/关系三项 Evidence。
S 的关系来源片段包含完整表格，不改变 ratio 实际消费的是推导 Claim 这一事实。
其分母生成与使用链没有被披露总额直取替代。

独立验证分别检查两条完整实际轨迹及持久化对象，未导入 Runtime 或准入函数来替代自身验证。
D 与 S 的共同四项任务义务均满足，没有通过改变共同 coverage 分母使 S 显得覆盖更多。
来源重建一致性核对在列选择之后进行，差值为 0、容差为 0；该核对标记为验证器检查，
不计为 D 的额外候选操作，也不用于重新选择来源。

有限比较只进行一个同任务配对，测量版本为：

```text
part_whole_share_retained_support_comparison.v1
```

比较器最多保存 20 条差异见证，本次实际保存了 20 条。其中包括分母的原始 Evidence 身份与
已接受推导 Claim 的差异、真实成员使用边、显式求和参数、实际输出、Observation、Claim 与接受更新。
20 是有界记录的见证条目数，不是全部差异的穷举总数，也不是来源数、候选数、深度或语义类数。

最终比较为 `different_retained_semantics`，两条均 Qualified，有限类数为 2，
因此 `W_share = 1`。比较器没有使用路线标签、图哈希、节点数或最终答案相同作为判定 authority。
比较和 own-validation 的 `candidate_runtime_executions = 0` 表示这些验证步骤没有派发新候选，
不表示此前两条正式 Runtime 未执行。

## 14. 直接控制结果与五项 Gate

八个负向控制的实际结果全部为拒绝：

| 控制 | 实际拒绝阶段 | 守住的边界 |
| --- | --- | --- |
| `missing_component` | `admission.roles` | 成员遗漏不能通过 |
| `duplicate_component` | `admission.complete_members` | 重复成员不能伪装完整分项集合 |
| `wrong_period` | `admission.period` | 分项期间必须一致 |
| `wrong_unit` | `admission.unit` | 分项单位必须一致 |
| `wrong_scope` | `admission.scope` | 分项合并主体范围必须一致 |
| `missing_sum` | `admission.parameters` | 不能省略明确 sum 参数 |
| `mean_parameter` | `admission.parameters` | 不能采用 mean 替代 sum |
| `claimed_reconstruction_consumes_disclosed_total` | `replay.claimed_denominator_support` | 声称重建不能掩盖实际消费披露总额 |

前七项是局部准入反例，没有调用数值执行内核。
最后一项从已有记录构造伪 S：保留正确答案字节，将 ratio 分母改成实际消费披露总额，
并重新计算全部 prospective 对象的内容身份。它没有因为旧 ID 不匹配提前失败，
而是在实际支持重放时得到：

```text
qa_valid         true
trajectory_valid false
qualified        false
first_failure    replay.claimed_denominator_support
reason           declared denominator support is contradicted by the actual consumed input
```

因此，即使答案正确且相关对象已经全部重新散列，也不能取得虚假的分项重建路线见证。
该控制是 `direct_admission_and_prospective_record_replay_not_executed_candidates`，
没有产生第三次 Runtime，也没有增加正式语义配对。

另有一次合法成员换序的准入核对通过；它只验证成员集合交换的合法性，不把换序当成新候选或新语义类。
这些直接控制支持本轮必要边界，不构成任意复杂结构、所有潜在攻击或通用 Mapper 的完整性声明。

五项 Gate 的实际结果为：

| Gate | 结果 | 对应范围 |
| --- | --- | --- |
| G0 | PASS | 新授权范围与历史工件保持不变 |
| G1 | PASS | 固定来源、新任务及局部合同 |
| G2 | PASS | 两条实际路线与独立 own-validation |
| G3 | PASS | 固定域有限语义解释完整 |
| G4 | PASS | 直接控制与零外部执行 |

Gate 合同明确 `second_class_required_for_pass = false`。
本轮取得第二类是实际科学结果，不是把“必须出现第二类”写成通过标准后筛选得到的结果。

## 15. 正式工件、源码冻结与内容身份

正式目录：

```text
trusted_data_synthesis/artifacts/qa_reasoning_part_whole_share/
finance_qa_vnext_part_whole_share_dual_support_preflight_v1_20260905
```

逐文件读取实际字节并核对 Manifest 后，目录计数如下：

| 范围 | 文件数 | 字节数 |
| --- | ---: | ---: |
| 根目录直接文件，包含 Manifest | 22 | 186,110 |
| `runtime/D` | 18 | 23,346 |
| `runtime/S` | 25 | 45,023 |
| 总计 | 65 | 254,479 |

自排除的 Manifest 绑定 64 个成员、245,007 字节；Manifest 自身为 9,472 字节。
全部 64 个成员的实际路径、字节数与 SHA-256 均已复核。
这里的文件计数包括执行 proposal、receipt、execution、Observation、Claim、update、state 等工件，
不能把文件数解释为候选次数。

实现源码冻结为：

```text
implementation commit b6783ac6676c6b821ab819f9215961fbd0605e84
implementation tree   475ff81d9e26d9424c1f6942de5cf7eb5cda1fb2
implementation files  8
implementation bytes  127,765

reference commit      595ff258a67f78ecd1779df0cda7fa7d8e1611a9
reference tree        bea5f53bb3a535043c1b6f3f49029107df948458
declared references   6 files / 55,950 bytes

archive Git blob      59958c7c3bb3b21f4dff6bc912a0fe0ae710aee0
```

`source_authority.json` 保存上述八个实现文件、六个声明引用文件以及 Archive 成员的 Git blob、
实际 SHA-256 和已提交／当前字节一致性。它明确不声称全部传递导入或完整 Runtime 环境闭包。
报告或测试文档后续提交不改变本次执行绑定的实现提交与树。

关键内容身份为：

```text
task
part_whole_share_task:0616bef8f302347723ff0ab8c84a570a9b76bb6cb09681e9a7dafec555a13a3f

contract
part_whole_share_contract:5266609cc280585c8ef3a28583968069c09d2e2b9642595f44a3c57752a9a028

registration
part_whole_share_registration_receipt:4a24e3eb947092083e3a8db4961a9b35bfec0edfa93454803e40d14d276f6764

source authority
part_whole_share_source_authority:f4912050398ec2f7bb098a6575c6aa70d7cfdfbd7a4354fe763c15ba1fc9d77c

candidate D
part_whole_share_candidate:2aa9125f1b61c1c27d78d6ca3fad015eff9d20247acd8edb7386bf108acc9c73

candidate S
part_whole_share_candidate:9ccd3e10f2f5c91e09ac83de4139c5b2ea946318e616d2479c0e5194e0f65997

Final D
part_whole_share_final:e3440f93f6f04d312392e95265795f0fa10e5980f08475729fe91eacedc8cc2f

Final S
part_whole_share_final:a06acad202ced80bf0b132f058c405e6a22dc3199ecfd8d6577484b5699bfb12

controls
part_whole_share_controls:ebc1e64b0d22f0552d20c1b6ebd24757e1a5f33626b9fabcdd12358ad9539197

Gate
part_whole_share_gate:92839eeb696c1dd47c654bcb93b7ae6232d436047cb7e1ffc1e29c156af99485

decision
part_whole_share_decision:f0adb26c7e177aad4eb407dfe2664e4b87a08d634c0d4874e36bd9325fcd3506

report
part_whole_share_report:9f287a99652050c7c1fd4fb2c6afe0d38c5e2f205d5548121a9f23e3a152ea90

manifest
part_whole_share_manifest:21a2e52198336101d1cf273af76a3bb0d26eb9baefb68dcd946c28261630a251

artifact root
part_whole_share_root:4a18be9c78b3f7bae7308339de50a0233db81c08484b5fa7fc3791c60fb1b221
```

两个 own-validation 文件与 comparison 文件没有额外的对象 `id` 字段，其原始 JSON 字节由正式 Manifest 绑定：

```text
validation_D.json SHA256
8c80df06b02ecedea07ccef1a5adc4b86e5a7dd758e6ae54a049b952ba1b2d3b

validation_S.json SHA256
97cbdedc16c1fcc7a9107f96f581164f39556ee3638d46f654d9826924faf8f7

comparison.json SHA256
8d798d1c72449af9b3e58a1d01df2713ce6e693be65b8987f342da82d178a4be
```

## 16. 执行规模、停止决定与结论边界

本轮实际规模为一个来源页面组、四条目标来源记录、一个新任务、两个预注册候选，
D/S 各一次 Runtime、合计五个实际操作和一个正式同任务语义配对。
Runtime 内 Oracle 调用为零；独立答案与轨迹复算属于验证，不新增候选执行。
Provider、凭证读取、GPU、在线授权、训练、QA Release 和 VTDO 生产行均为零。

旧来源阶段的 20 个文件、1,251,021 字节及其原始 Gate 分层保持不变，原科学见证继续为 null。
旧主链继续暂停；本轮没有修改旧任务或旧 F1/F2 的结论。

停止原因是预先固定的两条候选均已执行并完成独立验证与有限比较，当前有界预检已完成。
本轮没有在失败后替换候选，也没有继续扩样或搜索其他页面。
正式 `transition.json` 的 `next_stage_authorized = false`，
模型可达性、Provider、GPU、训练、Release 与 VTDO 均没有因这个局部正结果自动获得下一阶段授权。

本轮可以陈述的科学结果是：在固定的 2015 年 Union Pacific 收入占比任务上，
两条确定性构造的 own-qualified 行为具有可重放的不同分母依据与推导依赖，
因而得到 `W_share = 1` 和两个有限保留语义类。
模型能否自主产生这两种行为、该现象在更大任务域中的频率，以及训练或推理深度收益，仍未测量。
