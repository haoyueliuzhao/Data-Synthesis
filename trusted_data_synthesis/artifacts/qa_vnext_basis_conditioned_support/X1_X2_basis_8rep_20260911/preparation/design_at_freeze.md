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

采集前联合控制为 **228 passed in 8.20s**，Ruff 检查与二十个 Python 文件格式检查均通过：规则/身份/选样与原文控制 42 项、有限跨数量投影 28 项、实际方法与细类 36 项、Token 表示 44 项、固定选择消费门 21 项、隔离采集 27 项、费用 30 项。控制使用离线或显式脚本/Mock 场景；未调用真实 Provider、真实 tokenizer、Student 或 GPU。准备阶段会在相同冻结代码上再运行这七个新测试文件并封存 stdout/stderr；不复跑旧完整实验套件。

预检修正了两处新代码集成问题，均在新采集之前：评审 packet 以 `read_bytes().decode('utf-8')` 保留原 CRLF/CR，不做文本换行归一；新费用模块接受本轮真实 endpoint/movement 登记，而不冒用旧 N/E 标签或修改旧费用代码。支持不足与选定包超长/表示边界失败是登记的停止结果；来源原包验证或 tokenizer 资产加载失败则另记 `STOPPED_SOURCE_OR_ASSET_NOT_CERTIFIED`，不无条件宣称范围内成功。

当前为采集前冻结说明，尚未发起本轮在线请求，尚无新有效率、方法分层支持或 Token 消费结果。固定 32 会话及封存评审完成后，在本节追加实际数量、g×m 分布、细类组成、支持门、选择身份、消费性、成本口径和停止结论。不以预期效果替代观测。

成本仅按继承的条件性 Flash 人民币费率与请求 UTC 时间估算，不是当前价格验证或正式账单；分别保存 cache hit、cache miss、completion 与 reasoning 计数，reasoning 已含在 completion 中，不重复加总。

可执行入口（仓库根目录）：`PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -B -m trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.stage {prepare,collect,assess,finalize,show}`。`finalize` 需本轮完整 `--reviews` 文件；没有训练、重试、补采、提示换版或恢复模式。
