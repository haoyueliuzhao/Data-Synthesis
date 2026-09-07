# 支持选择转换与 Final 支持断言修正的有限商测量

阶段：`finance_qa_vnext_support_transition_and_grounding_assertion_measurement_only`。本轮依据已接受的八会话探索审计，零新增模型执行，解释 N03/E02 的七个未定事件，同时保留完整交互、E04 已支持语义和全部原分母。

## 1. 已成立事实与本轮对象

上一轮已真实获得三个 Qualified 行为：N03、E02 的 ratio 实际消费本会话 sum 经模型独立 Update 接受的 total Claim；E04 实际使用披露总额 Evidence，虽然它也执行过 sum。真实重建可达不是本轮需要再次采样证明的问题。

旧结果为 N `1/4`、E `2/4`、探索源 `3/8`。两条重建轨迹的纠正过程不在当时冻结投影域中，因此只有 E04 获得 Assignment，完整类数与 π 为 null，旧严格 `W_support=false` 表示证明未建立。所有这些旧结果保持不变。

新问题是在保留实际支持变化、错误支持声明和执行依赖的前提下，把这些现有有效行为纳入一个明确的有限商域。本轮不是新生成条件、QA 放宽、Student 实验或通用知识修订系统；新规则在已知轨迹上定义，不称数据盲确认。

## 2. 固定输入与零执行边界

前驱发布提交为 `6d05782ad3e4e47978f2da19ba0bd5e3ac041fc2`，来源目录为 `qa_vnext_support_exploration/share_four_neutral_four_guided_v1_20260907`，2,893 个文件、143,825,264 字节。

| 输入 | 本轮处理 |
| --- | --- |
| 原八个登记、N/E profile/config、Outcome | 原字节保留 |
| 正式有效集合 | E02、N03、E04，固定三条 |
| 全部原始提交 | 202，不增加 |
| 有效会话完整提交 | 42＝21 准入＋21 未准入 |
| 新解释位置 | N03 T1；E02 T1、T2、T9、T11、T12、T14，共七条 |
| 旧已解释位置 | 十四条，逐条完整解释记录原样复用 |
| 五个已知失败 | 仍为 ineligible，不从正确前缀获得有效 Assignment |
| 原候选 / Token / 完整包 | 21 / 21 / 3，仅引用原 ID 与文件哈希 |
| 新 Provider / Runtime / Operation | 0 / 0 / 0 |
| 重新资格核验 / 支持重新分类 / Token 化 | 0 / 0 / 0 |
| Student forward / 更新 / GPU | 0 / 0 / 0 |

九个历史工件前缀共 15,877 个文件、797,477,854 字节及 908 个前驱 Python 文件，均逐文件绑定前驱 Git blob。新源码位于独立 `finance_qa_vnext_support_transition` 包；旧 Runtime、资格、投影、比较、分布和表示实现不修改。读取完整原交互服务于新增关系的来源绑定，不重跑旧资格或已完成的支持检测。

本轮审计附件 25,030 字节，SHA-256 为 `f983897faf58560a818cfa6ac6d41f8c450d149a1c661851924759f1ae36c030`。完整原附件保存在准备工件；其原换行、文本和哈希不清洗。

## 3. 原生成条件与新测量条件分别绑定

原生成条件仍为 `qa_vnext_model_execution_support_exploration_condition:1ce7cd127bdabb128949f389ed0f9dd9244a4ff48aa29eb9e61d72c80f89d0ca`。它的 `rule_id` 仍指向旧 `0af6d844…` 规则，禁止采集过程中事后扩规则的字段也保持原值。

新建 `support_transition_condition` 绑定原生成条件、原比较合同、原报告/quotient、八个登记/资格/会话、三个有效资格、原 profile/config、源工件、实现提交和新规则。新规则另有 `extends_rule_id` 指向旧规则。没有修改并重新哈希旧生成条件，再把它冒称同一次执行。

新的比较合同显式继承原探索源中 N/E 两个分层的允许比较域，同时绑定新的测量规则。profile 标签不进入行为相等判断，但其来源身份保留在投影、Assignment 和分布中。原父身份检查不删除，候选/Token 中的真实 E 提示不抹去。

## 4. 关系一：未准入提案后的支持选择转换

N03 T1 与 E02 T1–T2 都提出使用披露 total Evidence 的 ratio，但未准入。之后最近准入的是 sum，产生 Observation；模型独立 accept Update 建立 total Claim，后继 ratio 实际改用这个 Claim，随后 percent 与有效 Final 完成。

本轮保留三种性质不同的部分：

```text
被拒、未执行的 D 提案及反馈
    ──观察到的先后关系──▶ 实际 sum → 独立 accept → 新 total Claim
                                             └──真实 denominator 输入依赖──▶ 实际 R
```

“无新增语义效果”只检查拒绝区间到最近准入 sum 之前：不存在 execution/Observation/Claim 等效果记录；前后 State 除 ID、反馈和一次提交计数外相同；后状态与下一请求衔接，Context/候选/合同不变。不能把其后的实际 sum、Observation 和 Claim 接受也叫无效果。

实际重建与消费根据原已验证 `old_support` 中的 total/ratio/percent trace 定位，再核对所需原事件、graph 节点、Observation、显式 Update、Claim、resolved input 与接受先后。这些是新增关系的证据连接检查，不调用执行器、oracle、资格器或完整 `actual_support()` 重分类。

前后 ratio 保留同一任务目标与输出义务、操作合同、parameters 和 numerator；denominator 分别绑定原 Evidence 与新 Claim，并明确 `inputs_are_equal=false`。新 Claim 必须在消费前存在于 accepted State，图中生产者和原输入/ref/resolved value 必须一致，后继 percent/Final 沿该链完成。

新关系类型为 `support_choice_transition_after_unadmitted_proposal`。保留当时完整候选、模型原判断、所选公开 offer、违例字段、拒绝关系、实际 sum/accept/R 的顺序及真实依赖；不虚构 D 已执行过，不撤销原知识，不推断反馈在内部导致策略转换。

连续相同提案的重复次数可以归一化，但原每条事件继续存在。N03 的原提案公开判断 `obligation_id=total`，E02 为 `ratio`；这类实际判断差别也保留，不能因两者最终都重建就擅自消去。

## 5. 关系二：同一答案上的支持断言修正

E02 Final 段以同一个已接受 percent Claim 为锚，真实 lineage 固定为 freight、other、part_whole。每次提交的 citations 是另一层“模型支持声明”，不能当作实际执行依赖。

对完整 T9–T16 的每个事件都记录原 citations、`missing=L−C`、`extra=C−L`、result、实际拒绝或准入反馈、完整 State 和预算，以及旧解释引用。不能只截取四个错误片段，省掉中间曾恢复完整 lineage 的上下文。

| 提交 | 原声明的支持集合 | 与真实 lineage 的关系 | 旧处置 |
| --- | --- | --- | --- |
| T9 | freight、total、part_whole | 缺 other，额外断言 total | undetermined |
| T10 | freight、other、part_whole、total | 完整 lineage 加冗余 total | 普通表示对齐 |
| T11 | freight、total、part_whole | 缺 other，额外断言 total | undetermined |
| T12 | freight、total、part_whole | 同上 | undetermined |
| T13 | freight、other、part_whole | 等于真实 lineage | 普通表示对齐 |
| T14 | freight、total、part_whole | 缺 other，额外断言 total | undetermined |
| T15 | freight、other、part_whole、total | 完整 lineage 加冗余 total | 普通表示对齐 |
| T16 | freight、other、part_whole | 等于真实 lineage；合法 Final | admitted |

数字与附加结果字段沿用原 Share 表示合同：允许既有 Claim 的完整精度字符串或按 `0.000001`、HALF_EVEN 的显式量化字符串，其他附加字段须等于该既有 Claim 输出。这里单独检验数字/元数据谓词，不把错误 citations 临时改成正确集合再调用旧归约。任意相近值或未绑定外部引用仍保持未定。

新关系 `same_answer_grounding_assertion_correction` 保留错误断言、拒绝、后续断言和最终合法同 Claim Final。错误 citations 不进入 `nodes.inputs`、`input_dependencies` 或任何实际 `uses` 边。真实答案链与错误支持声明同时存在，不彼此替代。

归一化分两层：

- 完整声明账本保存全部八次原集合、反馈、数值和旧处置，包括 T10/T13/T15，不能被压缩掉。
- 行为投影仍尊重已证明的普通表示对齐：完整 lineage 上的冗余引用归一为 L；缺失/替换真实 Evidence 的错误集合不归约为 L。只合并连续相同的归一化断言状态，不合并其间已回到 L 后再次发生的错误声明。

因此其规范支持断言变化为 `错误替换 → L → 错误替换 → L → 错误替换 → L`。T11/T12 的连续重复、T15/T16 在旧规则下的表面对齐不单独制造类别；最终 admitted 锚和每次真实反馈仍在关系/账本中。中间“支持集合回到 L”不等于该次 Final 已准入，也不证明模型理解了来源语义。

这段过程可以使 E02 与 N03 不同类，但是否相同由完整比较决定，不预设必须恰好两个类。

## 6. 基底、旧处置与 E04 兼容

所有新有效投影继续原样复制原 `finite_projection.nodes` 和 `final`。实际 Operation、参数、输入角色、Evidence/Claim 类型、判断、生产与消费依赖、Update disposition 和真实但未进入 Final 的操作全部保留。

E04 的整个已有 `behavior_projection` 和十一条已解释事件保持规范字节一致；E02 的 T10/T13/T15 三条旧解释也完整复用，共十四条。旧解释对象不回写；新七条解释通过独立 sidecar 记录旧未定原因与新增保留关系。

不存在清空 ledger、强制改旧支持标志或只按最终答案判类的操作。无法绑定的新关系仍保留 undetermined，不因预期类数改变规则。

## 7. 三个配对、Assignment 与 W

固定登记 N03/E04、N03/E02、E02/E04 三对，先检查 N03/E04 不会删除 E02。任何未支持配对也保留明确的 undetermined 记录，不缩减应有三对的范围。

完整比较沿用精确带标签 DAG 同构，同时比较 `nodes`、`final`、`retained_interactions`。对于 D/R 配对，额外提供明确的实际 denominator 对照：

```text
D：denominator ← 披露 total Evidence
R：denominator ← 本会话 accepted total Claim ← 实际 sum
```

差异见证必须绑定原支持证明及图中输入角色、类型、生产者和真实依赖。不能只写“保留事件多了一项”。若这些被保留的实际 D/R 依赖被比较器判等，视为比较合同违反，不能称模型支持坍缩。

新的类与 Assignment 绑定新测量条件、原生成条件、原 profile/config、资格与完整会话、实际图、新规则/投影、比较合同及关系证明。类 ID 是有限来源绑定引用，不是全域策略定义，也不通过 profile 名称或错误次数赋类。

只要 N03/E04 已形成确定支持差异，即使 E02 仍未定，新的 W 也可成立；但完整三轨迹类数和 π 仍须保留 null。存在性和全量测量继续分开，没有增加新的通过层级。

## 8. 三种分母与来源构成

无论最终分为几个类，N/E/探索源成功比例分别固定为 `1/4`、`2/4`、`3/8`；八个结果早已完整可判定，不能因商映射缺口将成功率改为 null。

全映射后，对每个正式类 z：`u_Γ(z)=(n_N,z+n_E,z)/8`、`π_Γ(z|success)=(n_N,z+n_E,z)/3`，联合质量总和 `3/8`、有效条件质量总和 1。各层原登记分母 4；有效分母分别为 N 的 1 和 E 的 2。

若仍未映射，保持 `mapped/8 + unmapped_valid/8 + 5/8 failure = 1`，不删除成功或重归一。成功条件下来源权重仍为 N `1/3`、E `2/3`，不是各 `1/2`。

两条 R 来自不同 profile，D 仅来自 E。以后类内物化 Mψ 必须保存这种原始输入条件构成；本轮只绑定它，不建立训练权重、改变 μ、抹去 E 引导或提前进行权重预检。

## 9. 本轮直接控制与复现入口

新增控制仅针对被拒提案假执行、删除实际 sum/伪造 Claim 消费、错误支持断言误归约，以及删有效样本/晋升失败/profile 赋类；另检查 E04 和十四条旧处置兼容。控制是已载对象副本，不是新模型轨迹，不进行新的 Runtime/Operation/资格/Token 执行。

准备、一次正式测量、有限比较、Assignment、分布与局部控制在同一轮完成，没有同内容的额外独立审计。源码、规则及输入引用在正式物化前冻结，仍明确这是已知数据上的规则实例化。

在项目根目录使用现有环境，冻结源码后执行：

```bash
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_support_transition prepare
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_support_transition run
```

新工件目录为 `artifacts/qa_vnext_support_transition/support_transition_grounding_v1_20260907`。准备目录保存新条件/规则、原生成条件引用、比较合同、源绑定和表示引用、历史清单、实现及 guard；测量目录保存八个状态 sidecar、三对、类/Assignment/分布、控制、保存性结果及报告。旧工件不修改，成功封存后入口只核对并读回，不重建。

正式结果将在测量完成后补入，不在冻结设计中预填类数或 W。

## 10. 后继边界

若新解释及 D/R 差异证明成立，应关闭当前单题支持存在性对象，不再为了提高成功次数重复 Share。下一步才是另行固定其他真实任务绑定、机制复用、类内物化、任务边际和独立评价对象。

当前是单题、多次开发接触、给定公开计划下的有限结果；不是自主算法发现、一般信念修订或泛化收益证据。不同保留过程不自动对应正 Contribution。Student/GPU 与 VTDO 更新均未实施，旧主线继续暂停。
