# 固定任务上的依据条件化合成：端点与期间组成的完整轨迹支持构建

## 1. 本轮身份、授权与冻结范围

本文件登记一个新的支持构建实验。用户于 2026-09-11 提供后继审计并要求“参照审计继续实验”，据此接受审计第四节的直接后继：X1、X2 × 两种显式依据条件 × 每格八个独立空历史 Teacher 会话。条件性效用研究不是本支持批次的默认执行内容。

审计原附件 SHA-256：`021f8d41be81af33bd2c0b9f398bb480c5d78761d30b09f5323458791f7ec25b`。此前 DR 支持实验已在 `9743e7e057ff484249713276c7848e6fc744e645` 终结并推送，结论仍为 `INPUT_INADEQUATE`。原新 32 E/X2 候选为 29 个完整财务与交付有效包，其中 28 个纯 D、零个纯 R、一个有效但完整映射未定；与历史八条构成的固定候选核为 35 D、1 R，另有一个有效未映射包。37 是财务有效包数，36 是落入指定 D/R 的包数，两者不混用。历史候选不进入本轮新目标支持池。

已经完成的 36 题目标账本、18 条有限案例、252 条旧失败交集工作以及旧 D/A 的九次训练、108 开发和 144 确认会话均不重开。旧训练的确认未获收益结论不变；原 DR 工作的 Token 消费性、训练与效用未执行，不能解释为效用等于零。

本轮代码位于 `src/trusted_synthesis/experiments/finance_qa_vnext_basis_conditioned_support/`，工件位于 `artifacts/qa_vnext_basis_conditioned_support/X1_X2_basis_8rep_20260911/`。准备、采集、自动审计、完整资格、选样、表示和收口为不同的只写一次、内容寻址与清单封存阶段。规则代码、测试和本说明先提交并推送，再建立准备封存，再发起请求；采集后不修改这些规则文件。

## 2. 两个公开任务与不同的财务对象

共同来源为已封存 `qa_vnext_soft_detail_exploration/three_tasks_NE_8rep_20260910/preparation` 中的原公开任务，问题、完整文本、表格和 numeric catalog 原字节不改。旧私有材料只提取目标范围、公开源事实对应的 D/R 源符号规范形；旧条件或完整类 ID 不复用到本研究。

| 任务 | 公开比较目标 | 公开关系；仅用于离线登记，绝不附加给模型 |
| --- | --- | --- |
| X1，`ETR/2004/page_239.pdf-2` | Entergy Mississippi 2003 年减 2002 年的公司定义 net revenue | 披露年度端点 426.6、380.2 百万美元；解释变动的基础费率 48.3 与其他 −1.9 百万美元 |
| X2，`PPG/2006/page_42.pdf-4` | 2006 年末减 2005 年末产品保修准备金 | 披露余额 10、4 百万美元；2006 年费用 4、收购承担义务 7、现金支出 5 百万美元 |

X1 的公开 p3/p4 说明 net revenue 是公司定义的 gross margin 指标，不能误称净利润，也不能把两个年度比较端点当作存量余额。其关系分别为 `e-b` 与 `rate+other`，参考差额为 46.4 百万美元。`t3c1` 的原文是 `-1.9 (1.9)`，已公开 catalog 只有带负号的 `source:t3c1n0`；不能为括号里的排版另造正值 source ID。若实际模型明确采用正的下降幅度再相减，须在公开语义和转换证据成立时记录真实的符号变换，不进行宿主自动符号修复。

X2 的期间费用是 `source:q12n3`（2006 年的 4），不能用同值的 `q12n5`（2004 年的 4）代替。期末与期初余额分别是 `q11n3` 和 `q11n4`，而 `q11n0/q11n1` 是日期 31 和年份 2006。金额相等不建立来源或期间对应。固定目标为 6 百万美元。公开目标关系和来源锚点记录在 `target_ledgers.json`；私有正确答案、规范形和核对关系不向在线 worker 开放。

## 3. 新的生成条件 g：只改变一段共同合同之后的依据指令

共同 SYSTEM 使用上一版本 N 的工具、交付和公共数量合同，即 `SYSTEMS_NEW['N']`，不携带旧 E 的软明细优先段落。下列两段是本轮实际冻结英文原文，不是示意。各段分别拼接于完全相同的共同 SYSTEM 之后，以两个换行隔开：

`endpoint`：

> Use the two comparison endpoints disclosed directly in the source as the main basis of your published answer. Identify the financial object, comparison periods, sources and expression yourself from the complete document, and actually execute the calculation supporting the requested change or difference. If you cannot establish a sufficient valid basis of this kind, say so honestly and finish without inventing one.

`movement`：

> Use the components or changes explaining the comparison as the main basis of your published answer, rather than directly subtracting the two disclosed comparison endpoints as the main answer calculation. Identify the items, signs, sources and expression yourself from the complete document, and actually execute the requested net change or difference calculation. If you cannot establish a sufficient valid basis of this kind, say so honestly and finish without inventing one.

这是显式依据条件化合成，不是原 E 下的无指导或软指导自然选择率。没有每题公式、金额、source ID、参考答案或逐题计划提示；不隐藏端点、不强制第二次核对、不在一次 D 输出后追加重来、不据结果选择新提示版本。模型无法建立依据时允许如实结束。真实指导前缀必须留在后续原始监督输入中。

固定 requested model 为 `deepseek-flash`，thinking enabled、reasoning_effort high，temperature/top_p 不发送。保持原隔离 worker、公开响应投影、工具实现、响应与历史接收合同。`reasoning_content` 不进入公开训练内容；公开响应投影不冒称完整原 HTTP 返回。无 catalog、校准或 fallback 模型请求。此设置不保证提供商权重或采样分布与历史日期相同。

## 4. 不可扩充的采集总体与停止规则

| 登记项 | 本轮固定值 |
| --- | ---: |
| 任务 × 指导条件 × 独立 replicate | 2 × 2 × 8 |
| 新 Teacher 会话 | 32 |
| 每会话请求 / 工具上限 | 32 / 32 |
| 总 Provider 请求上限 | 1,024 |
| 并行 worker | 24 |
| 两个固定 wave | 24、8 |
| Student、训练、greedy、B0、辅助 NLL | 全部 0 |

标签 `endpoint_X1_01` 等唯一标识独立会话。固定调度顺序为 replicate 递增，然后 X1、X2，然后 endpoint、movement；前六个 replicate 为第一 wave，后两个为第二 wave，每个 wave 的四格完全平衡。两波之间不人工评审、不根据结果反馈或改参数。全部 32 worker 终止后才开始自动与人工评审。

每次 Provider 请求在发送前有配额预留，首次实际 Final 立即停会话，网络错误、空公开响应、模型标识不符等按原终止合同保留，不另开替代会话。无自动网络重试、失败补采、历史恢复、换模型或提示补救。私有评审与评价材料通过独立 worker 的访问限制在请求前检查，API key 只经文件描述符传入，不进入工件。

## 5. 资格、实际方法 m、完整类 z 三层分开

数量资格沿用 `public_quantity_interpretation.v1.1`，来源与目标绑定沿用 `public_task_target_binding.v2`。不扩展 Final 多金额提取；只评估实际 `final` 子树，不把顶层兄弟字段拼成答案。数量、源值对应、公开目标适用性、实际计算结果到 Final 的支持链、现存来源断言分别审核。当前错误输入断言不因未消费或最终数值正确而自动撤回；推导来源和一般引用不被一律当作直接 numeric ID 数值断言。

人工 packet 省略 g、replicate、SYSTEM、模型与费用，但公开自述可能暴露条件，且执行助手团队能访问登记信息；因此只称“元数据遮蔽”，不称真正盲评或独立认证。全部采集终止后可由执行助手团队并行审阅分区，主助手合并核对。每条原始公开消息及事件均须检查，保留实际引文、响应索引、源文本引文、断言角色与撤回依据。

实际方法由 Final 的主要支持链及其源符号计算判断，不由 g、答案等值或私有目标命中推断：

| 实际 Final 主要支持 | 方法特征 |
| --- | --- |
| 两个披露比較端点之差 | endpoint |
| 解释本次比较的期间组成/增减项目实际算出所问差额 | movement |
| 端点主要答案 + 实际明细期末余额核对 | endpoint，核对另保留 |
| 两种共同主要依据 | MIXED，不为配额强制二分 |
| 支持链接或规范形不足 | UNDETERMINED |

方法层不是新的等价关系。完整类仍保留新条件身份、公开任务与文档、目标范围、实际主答案源符号规范形、活动来源、实质修订路径、同目标量核对与有限跨数量核对。未知完整投影不改变原财务资格，也不自动获得完整类准入。即便 m 已可知，完整类未映射仍不能填支持配额。多个主要依据但投影不能完整编码其主次关系时，保留完整映射未定。

完整类 ID 只属于本轮新条件；同一方法层可以有多个细类。重复文本如实记录，四个独立会话不等于四种方法。汇总保留全部注册分母与全部有效分母，不丢弃有效但完整映射未定的质量后重新归一。

## 6. 有限跨数量表示扩展，不改写历史 B2_07

只为未改的 X2 登记“实际重建 2006 年末产品保修准备金并与披露期末核对”的公开关系。令 `e,b,c,a,o` 分别为披露期末、期初、期间费用、收购承担义务和现金支出：

```text
D = e - b
R = c + a - o
B = b + c + a - o
离线说明：D - R = e - B
```

恒等式是离线数学解释，不是模型额外执行了 R 或残差计算；D 与 B 还共享期初来源，不称统计独立测量。只有原工具真实执行了 B、来源对象/期间/单位匹配，且原调用与实际 Final 保留公开核对联系，才记录跨数量核对。实际表达式、结果、被核对的披露量、来源角色、原文链接、依赖链与离线解释分开保存。

有限实现只认登记原型和有限明确的英文核对陈述；错误期间、不同单位、文字-only、由原答案机械倒推、相同来源端点消去、缺原 Final 联系或无法唯一解释的陈述均不以数值相等强认。额外计算不自动是独立核对。与本有限关系不一致的行为仍保留未定，不围绕新输出无限扩展解析器。

旧 `E_X2_B2_07` 只用作新准备的离线边界控制：它实际工具 1 为 `10-4=6`，工具 2 为 `4+4+7-5=10`，Final 主要结果链接工具 1，第二条是期末核对。原先把第二条预报为 6、后来在 Final 修正成 10 的实质修订保留。新表示测试不得擦掉此修订或核对。旧记录的 `projection.check_same_answer_quantity_only` 未定、旧纯 D/R 计数和历史清单完全不改。

## 7. 方法层支持选择与一次性消费门

仅本 32 新候选参加选择。每个实际 `(task,m)` 层需要至少四个完整财务与交付有效、完整类已映射、m 唯一的独立原包。先检查四层原始支持；任何一层不足，则本次固定实验终结 `INPUT_INADEQUATE`，全部 selection 为空，tokenizer 加载与表示检查为零，不增采、不先训练已足部分。

每层可混合两个 requested g，但真实指导前缀和 g/细类构成全部保存。选择顺序为 replicate 递增；同 replicate 先 requested endpoint 后 requested movement。这是审计没有给出跨 g 同序打破办法时，本轮事前登记的实现选择，不是审计原句。排序使用与标签及冻结条件一致的身份元数据，审核者不能借改 replicate、task 或 g 重排。

若四层原始支持均成立，按此顺序每层第一、二、三包登记 future_train，第四包 heldout，共 12+4。先独立封存这 16 个完整原包身份和角色，再加载原绑定的本地 tokenizer 进行一次完整表示检查。只检查被选 16 包，不能按消费结果向后替换。单包内成功工具、合法公共消息及实际 Final 原文作为正目标；失败请求只保留在后续真实输入历史，不裁剪/重写/再序列化原目标，不插离线注释或中性 SYSTEM。

Tokenizer 使用已有精确本地资产与 chat template。旧绑定中历史任务的 24,576 字段不改写；沿用已登记的实际模型位置边界 32,768、无 RoPE 扩展、无截断。检查渲染前后缀、目标 UTF-8 回译、Unicode offset 覆盖（允许 byte fallback offset 重叠）、因果一位位移、prompt/role/eos/padding 的零目标 mask。超长或边界失败保留原包和诊断，不输出可消费数组；任何一个预选包失败即停止，不能裁剪、替换或改 SYSTEM。

留出四包只允许表示检查，不进入训练、分布方向选择、同题 greedy 或 NLL。表示通过仅证明这一固定候选核的消费性；本轮无 27 包训练总体或权重视图物化，无模型参数加载/前向/训练/GPU。即使支持与消费性全部成立，`training_allowed=false` 仍保持。

## 8. 固定条件化材料核的解释范围与未执行的效用方案

后继若单独接受并冻结效用实验，可写为：

```text
D_alpha,psi(x,g,tau) = mu(x) sum_m alpha(m|x) K_psi(g,tau|x,m)
K_psi(g,tau|x,m) = sum_z q_psi(g,z|x,m) M_psi(tau|x,g,z)
```

层内指导条件、细完整类比例、原样文本、表示和取样规则都固定在 K 中；改变 alpha 时不再选 q 或 M。这识别的是固定条件化合成材料核的质量效用，不是剥离指导提示因素后的抽象方法效应，也不是原 E 纯 D/R 分布的干预。

条件性六任务总体为旧 G1/G2/F1 控制九包、固定 N/X3C D/A 六包、新 X1 两方法各三包、新 X2 两方法各三包，共 27 包。旧 X1/X2 目标包被替换，因此新 pi0 与历史 pi0 非单因素可比。六题质量各 1/6，X3C D/A 各半固定；新 X1/X2 的基线两方法各半。仅分别移动一个任务，形成 pi0、X1+、X1−、X2+、X2− 五臂。单任务方法质量从 (1/2,1/2) 改为 (1/3,2/3) 或 (2/3,1/3)，全局转移 1/36；受干预任务每包分别为基线 1/36、plus 的 endpoint 1/54 和 movement 1/27（minus 反向）。这些是数学设计描述，不是本支持阶段已经实例化的训练权重。

沿用既有基础 checkpoint、LoRA、种子 11/29/47、十遍完整遍历与最终 checkpoint 规则。条件性最多 15 训练、180 开发、144 全新独立确认会话，B0、同题 greedy、辅助 NLL 为零。目标 Token 预算必须按新选材料实际长度冻结 `10*sum(L_tau)`，不能沿用旧 68,190。开发旧十二题只称已知材料，D10 须使用明确特定调整额的新版本；确认须另选未用二十四题，不能旧确认改写复用。

主效用仍为三组等权完整可验证轨迹产率；三个配对种子平均增量严格大于零才移动，事前冻结同分顺序，确认前封存唯一候选，确认失败不换第二名。评测 SYSTEM 不含本轮依据合成指令。上述内容在本轮只保留为后继设计，绝不由消费门通过自动启动。

## 9. 实际执行与结果记录

采集前联合控制为 **228 passed in 8.20s**，Ruff 检查与二十个 Python 文件格式检查均通过：规则/身份/选样与原文控制 42 项、有限跨数量投影 28 项、实际方法与细类 36 项、Token 表示 44 项、固定选择消费门 21 项、隔离采集 27 项、费用 30 项。控制使用离线或显式脚本/Mock 场景；未调用真实 Provider、真实 tokenizer、Student 或 GPU。准备阶段随后又在相同冻结代码上运行了这七个新测试文件，并已封存 stdout/stderr；未复跑旧完整实验套件。

预检修正了两处新代码集成问题，均在新采集之前：评审 packet 以 `read_bytes().decode('utf-8')` 保留原 CRLF/CR，不做文本换行归一；新费用模块接受本轮真实 endpoint/movement 登记，而不冒用旧 N/E 标签或修改旧费用代码。支持不足与选定包超长/表示边界失败是登记的停止结果；来源原包验证或 tokenizer 资产加载失败则另记 `STOPPED_SOURCE_OR_ASSET_NOT_CERTIFIED`，不无条件宣称范围内成功。

采集前说明的原样副本封存于 `preparation/design_at_freeze.md`；其中“尚未发起本轮在线请求”是冻结时的进度事实。以下结果来自随后一次固定批次，未修改冻结规则、重开采集或根据资格结果重写原响应。

成本仅按继承的条件性 Flash 人民币费率与请求 UTC 时间估算，不是当前价格验证或正式账单；分别保存 cache hit、cache miss、completion 与 reasoning 计数，reasoning 已含在 completion 中，不重复加总。

可执行入口（仓库根目录）：`PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -B -m trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.stage {prepare,collect,assess,finalize,show}`。`finalize` 需本轮完整 `--reviews` 文件；没有训练、重试、补采、提示换版或恢复模式。

### 9.1 冻结、采集与实际资源用量

规则与二十个 Python 源码/测试文件先在 `d543b3bf31379c0b4fb830673eda0c38c026af0c` 提交推送。准备阶段再次获得 **228 passed in 8.21s**，所有被禁止入口计数为零，然后在 `c41273aad48f6eb927f8b8af5a7d00897dce87eb` 封存并推送准备工件。首次新 Provider 请求发生在这两个提交之后。

固定 32 会话全部终止；实际 72 次预约与请求，72 个返回均为 HTTP 200、公开模型标识 `deepseek-flash`、finish_reason `stop`，32 个首次实际 Final。采集程序测得总 wall time 16.819 秒，两波分别为 9.299 秒和 7.502 秒；这些是本次程序计时，不是提供商性能的稳定估计，也不是累计请求延迟。没有补采、网络重试、模型替换、catalog 请求或指导重写。

72 个公开响应分解为：

| 实际公开事件 | 数量 |
| --- | ---: |
| 成功执行 `calculate` | 32 |
| 首次实际 Final | 32 |
| 合法非终止、无工具公共消息 | 6 |
| JSON framing 协议错误，未执行工具 | 2 |
| 合计 | 72 |

全部会话都只有一次实际计算，32 次工具全部成功；两个协议错误不能说成两次工具错误。`endpoint_X1_05` 的前两条响应附带 DSML 结束标签，JSON 解析失败，第三条才真正计算 `426.6−380.2`，随后 Final。原错误消息和格式恢复均保留，没有把失败请求当作成功执行。另有六条 answer-shaped 但无 `final` 的合法消息保留到后续完整历史中，不虚构它们是早期 Final 或语义修订。

本阶段真实 tokenizer 加载一次，且发生在全部资格与固定 16 包选择封存之后。Student 权重加载、Student 前向、训练、生成、GPU 初始化、B0、同题 greedy、辅助 NLL 以及留出训练/NLL 均为零。离线执行防护覆盖了所登记入口；这不是对任意代码的形式化隔离证明。

### 9.2 资格、实际方法与完整映射

数量提取/数值资格为 **31 PASS、1 FAIL**；完整财务与交付资格为 **27 PASS、2 FAIL、3 UNDETERMINED**。二者不同：数值正确不撤销错误来源声明，也不解决当前来源引用的角色歧义。

| 任务与请求 g（每格 8 会话） | 完整资格 PASS / FAIL / UND | 实际 endpoint / movement / UND | 完整有效且完整映射的目标方法支持 |
| --- | --- | --- | ---: |
| X1 / endpoint | 8 / 0 / 0 | 8 / 0 / 0 | endpoint 8 |
| X1 / movement | 8 / 0 / 0 | 0 / 8 / 0 | movement 8 |
| X2 / endpoint | 7 / 1 / 0 | 7 / 0 / 1 | endpoint 7 |
| X2 / movement | 4 / 1 / 3 | 0 / 8 / 0 | movement 4 |

实际方法特征在全部 32 会话上的数量为 endpoint 15、movement 16、未定 1，没有 MIXED。这里 16 个 movement **不是** 16 个完整有效包，其中包括一个来源 FAIL 和三个资格未定；可准入的 movement 为 X1 的 8 个加 X2 的 4 个。请求依据与已建立的实际依据一致者 31 个，另一个实际方法未定；不能把“31 个依据吻合”称作“31 个完整有效”。

27 个完整有效包均完成本轮完整类映射，本批没有“完整有效但完整类未定”的新增包。三个资格未定包不自动移入有效分母或完整类分母。这里完整有效分母为 27，已映射有效质量为 27/27；这一事实不改变上一批 28/29 加 1/29 映射未定的历史分解。

### 9.3 五个未准入包及保留的执行边界

| 原标签（遮蔽评审号） | 冻结规则下的处理 | 直接依据 |
| --- | --- | --- |
| `movement_X2_02`（016） | FAIL；实际 movement 特征仍可记录 | 当前嵌套 `charges_2006={value:4, source:q12n0}` 将 4 指向年份 2006，未被撤回。表达式实际是字面量 `4+7−5`，不消费该变量，但不消费不撤销错误源值断言；Final 为 6 也不能修复它。 |
| `endpoint_X2_08`（022） | FAIL；实际方法未定 | 实际表达式为 `2006−2005`，工具返回 1，Final 发布 `$1 million`。元数据里名为 `2006`、`2005` 的 10/4 对象未被表达式读取；不能把数值字面量解释为变量，再替模型执行 `10−4`。 |
| `movement_X2_06`（002） | UNDETERMINED；实际 movement 已知，不完整类准入 | 主要组件输入与计算正确，但 Final 的未结构化来源列表含 `q11n2`（年份 2005）及 `q11n3`（期末 10）。它可以是期间背景引用，也可能意图对应叙述中的期初金额，原文未唯一确定其角色。 |
| `movement_X2_01`（007） | UNDETERMINED；实际 movement 已知，不完整类准入 | 主要组件输入正确，Final 另列 `q11n0/n1/n2`（日期 31、年份 2006/2005）。不强制将列表当成金额-ID 配对判 FAIL，也不因数值正确便强称一般引用 PASS。 |
| `movement_X2_04`（023） | UNDETERMINED；实际 movement 已知，不完整类准入 | 唯一工具实际执行组件差额并得到 6；Final 的 `q11n2` 引用角色仍未定。Final 文本叙述余额恒等式并不构成额外实际计算，也不消除来源列表歧义。 |

016 的 Final 列表还存在未定引用，但其资格 FAIL 不依赖对这个列表强选解释；明确错误的嵌套源值断言已经足够。上述歧义均按既有 v2 保留，不扩充 parser、不将 numeric ID 格式当作唯一准入门，也不降格为无条件一般引用。执行助手团队分四区完成原始消息、事件与来源审核，主助手复核全部原始公开响应及关键边界，随后用冻结规则验证全部 32 条；这仍是非独立、非保证盲评。

### 9.4 观察到的细完整类与没有观察到的行为

| 任务 / 实际方法 | 本批有效映射细类 ID（去共同前缀 `basis_complete_behavior_class:`） | 包数 |
| --- | --- | ---: |
| X1 / endpoint | `e55c8c20c0e63dce3cf61b97659f50181fb91f7fddc65094b28eb4c524bdff36` | 8 |
| X1 / movement | `360e0389f4a1ae9f47d81314fb6f18658f54b93be0c2ea640e5e9d6a0516a245` | 8 |
| X2 / endpoint | `bf863eb68db88762e70a57b1ae34727028c21b262092512fbc9cb631d95e047b` | 7 |
| X2 / movement | `6f2f1ea28360857905e0211ddffe4b0c27b6307265986f4f5fcdea2f453789b3` | 4 |

这些 ID 绑定各自新 g、任务、来源、目标、主支持规范形、实质修订和核对结构，不是旧 N/E 类标识。这批观察中，每个实际方法层恰好只有一个已认证细类，并且均来自同名指导条件；这不是实现将方法层当成完整类，也不是拒绝未来同层不同细类。格式恢复、命名和合法重复消息不被误当作新的金融依据；它们仍留在原始序列和证据账中。

原始会话中有多处文字“consistent/reconciles/check”或余额说明，但没有第二次实际工具计算，因此新样本的实际同量核对和跨数量核对都为零，实质修订也为零。`endpoint_X1_05` 有两个保留的 format-only 恢复记录。有限跨数量扩展本轮通过历史 B2_07 和定向反例的准备控制，但**没有采到新的该类核对实例**，不能把扩展测试当作本批生成收益。

完整公共响应序列逐字节去重检查未发现跨会话完全重复；这仍不意味着每包代表一种不同方法。`movement_X1_05` 在同一会话中有两条完全相同的合法无 Final 消息，原样保留，而不是新增方法类。

### 9.5 固定 16 包与实际消费性结果

四个原始方法支持层分别有 8、8、7、4 个完整有效且已映射原包，达到冻结的各层至少四包要求。选择先独立封存，再进行表示检查：

| 任务 / 实际方法 | future_train 三个完整原包 | heldout 完整原包 |
| --- | --- | --- |
| X1 / endpoint | `endpoint_X1_01`、`endpoint_X1_02`、`endpoint_X1_03` | `endpoint_X1_04` |
| X1 / movement | `movement_X1_01`、`movement_X1_02`、`movement_X1_03` | `movement_X1_04` |
| X2 / endpoint | `endpoint_X2_01`、`endpoint_X2_02`、`endpoint_X2_03` | `endpoint_X2_04` |
| X2 / movement | `movement_X2_03`、`movement_X2_05`、`movement_X2_07` | `movement_X2_08` |

X2 movement 的 01/02/04/06 因上述资格原因不在合格池，03/05/07/08 是按预先规则得到的全部四包，不是看到 Token 长度后更换出来的四包。本批消费过程中没有替换、裁剪、指导前缀中性化或响应修订。

| 表示检查项 | 实际结果 |
| --- | ---: |
| 检查原包 / future_train / heldout | 16 / 12 / 4 |
| 整包检查 PASS / FAIL | 16 / 0 |
| 原始正目标响应检查次数 | 34，全部一次且 PASS |
| 其中 future_train / heldout 响应 | 26 / 8 |
| 全部十六包目标 Token | 6,759 |
| 十二个 future_train 包目标 Token | 5,188 |
| 四个 heldout 包目标 Token | 1,571 |
| 实际完整单响应序列长度范围 | 4,577–10,745 |
| 冻结最大位置边界 | 32,768 |
| 真实 tokenizer 加载次数 | 1 |
| 消费性失败、重试、替换 | 全部 0 |

两个被选包各含一条额外合法无 Final 消息：`movement_X1_01` 与 `endpoint_X2_03` 各三条正目标，其他被选包各两条。正目标不是一律“一个计算加一个 Final”的人工改写；输入中保留实际完整公共历史与真实指导 SYSTEM。

26 条 future_train 响应和 8 条 heldout 响应只是本次表示计数，**没有训练**。5,188 不等于后继 27 包训练总体的监督量，更不能乘十之后冒称已冻结整体训练 Token 预算。没有建立旧控制包与本轮包的 27 包合并训练视图，没有 alpha 权重或十五次训练计划的实际物化。留出只作表示检查，未作 greedy、NLL、模型或方向选择。

### 9.6 请求费用与可解释范围

本次完整记录的用量为：cache hit 335,872、cache miss 157,862，合计 prompt 493,734；completion 30,144，total 523,878。reasoning 17,859 是 completion 内部子集，未再加一次。72 次请求全部落在继承费率的 offpeak UTC 窗口，按该**未重新核价、非账单**口径估算：

```text
(335872 × 0.05 + 157862 × 1.5 + 30144 × 4.5) / 1,000,000
= 0.3892346 元
```

成本账保留所有 32 会话，包括失败和未定，不仅计入合格包；没有把请求 Token 当作监督目标 Token。与旧 E/X2 的不同费用、长度或方法计数均不能单独说明稳定生成概率、提供商能力变化或训练效用。

### 9.7 收口结论与证据入口

本轮状态为：

```text
scope_status = PASS_AS_SCOPED
collection_status = FIXED_32_CLOSED
raw_support_status = RAW_METHOD_SUPPORT_ESTABLISHED
consumable_input_status = SUPPORT_REPRESENTATION_ESTABLISHED
selected = 12 future_train + 4 heldout original packages
training_allowed = false
Student_training_runs = Student_sessions = NLL = 0
```

本次证明的是：在这两个固定公开任务和已明确指导的生成机制下，冻结批次提供了足够的完整有效、完整映射且可消费的方法层原包。它没有证明原 E 的自然纯 R 供给已改善，没有证明 movement 的抽象方法效应，更没有得到 Student 效用收益或独立确认。

可供后继独立接受并冻结的效用设计仍见第 8 节；这次支持成立不自动授权或执行该十五次训练计划。后继若启动，还须先完成 27 包固定总体、实际 Token 预算、开发 D10 新版和全新确认题 panel 的准备。不得用原八/四十候选替换本次选定材料，或将本次已知样本当作全新独立确认。

主要证据入口：

- [封存准备与控制](../artifacts/qa_vnext_basis_conditioned_support/X1_X2_basis_8rep_20260911/preparation/manifest.json)。
- [固定采集报告](../artifacts/qa_vnext_basis_conditioned_support/X1_X2_basis_8rep_20260911/online/report.json)。
- [32 条资格与原包索引](../artifacts/qa_vnext_basis_conditioned_support/X1_X2_basis_8rep_20260911/qualification/report.json)。
- [固定选择](../artifacts/qa_vnext_basis_conditioned_support/X1_X2_basis_8rep_20260911/selection/support_selection.json)，ID `basis_fixed_support_selection:aae0f5af72b50a7b514c14d5e307ae43d119b5b76829622344dcc38cf95cd83f`。
- [一次性消费报告](../artifacts/qa_vnext_basis_conditioned_support/X1_X2_basis_8rep_20260911/consumption/report.json)，ID `basis_support_consumption_report:ff37eb0f3b75d383bc6eb8182c8488a36caffe38bfe02b9a48382cb82bc8049c`。
- [最终收口报告](../artifacts/qa_vnext_basis_conditioned_support/X1_X2_basis_8rep_20260911/closeout/report.json)，ID `basis_bounded_support_report:0726836c2ccac88a7155f48fcbe0709dff8219e93e50effc4229b2a19ceb802c`。
