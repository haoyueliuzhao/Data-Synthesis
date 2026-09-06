# QA vNext：统一条件八任务面板与十六会话采集

预登记与采集日期：2026-09-06；结果整理日期：2026-09-07。阶段：
`finance_qa_vnext_fixed_task_panel_collection_and_representation_pilot`。

## 1. 当前审计与新阶段的授权边界

用户提供的 565 行审计附件 SHA-256：
`67199bf4810f0e6d01da5069429326459ccc29c90fd410f73e23cd4d70ad65d1`，
原始大小 25,917 字节。用户本轮指令为“参照审计继续实验”，据此实施审计提出的
8 个既有来源任务 × 2 个新会话，而不是仅从上一轮 PASS 自动扩大运行范围。

上一轮原样长度适配按 `PASS_AS_SCOPED` 收口：原 34 条候选在独立 32,768 条件下
全部可消费、两个完整包成立，旧 24,576 的 `contains_not_fit` 继续正确。
本轮不重复长度适配、B 完整可达性证明、单步接口校准或全部历史审计链。

新阶段只研究同一固定 QA 面板中的来源、真实模型有效行为、实际依赖深度、有限
同任务行为关系以及原始监督表示，分别记录这些维度。不进行 VTDO 概率更新、
Contribution 估计、Student 权重加载、forward、参数更新或 GPU 作业。

## 2. 八个精确任务与固定边际

继续使用统一 Catalog 中已经实例化的七个 Program 任务和一个 Share 任务。
它们必须与已发布统一入口报告的精确 case/context/task/source binding 相同，
无法恢复任何一个绑定时在调用前报出缺口，不换题、不补源、不用合成数值填空。

| 组 | 已有任务类型 | 既有任务 ID 前缀 | 新会话 |
| --- | --- | --- | ---: |
| F | `fact_retrieval` | `task:d4b3c6a0898f` | 2 |
| C | `registered_cross_metric_comparison` | `task:ee3b90ed728e` | 2 |
| G | `temporal_growth` | `task:668b95e003e3` | 2 |
| A | `temporal_average` | `task:e9f05d7f04cb` | 2 |
| D | `temporal_absolute_change` | `task:196de8d8f17e` | 2 |
| R | `registered_ratio` | `task:eff2ad9f3242` | 2 |
| B | `derived_growth_absolute_spread` | `task:52858dad45af` | 2 |
| S | `source_explicit_part_whole_share` | `part_whole_share_task:0616bef8f302` | 2 |

表中仅缩写身份便于阅读，实际准备条件保存全部完整 ID 和上下文。
Share 的既有两条离线路线共享同一任务和来源绑定，在面板中只占一个任务，不拆分
D/S 任务、不预分配路线、不因某种支持方式未出现而追加采样。

另外三类仍为来源未实例化：`comparison`、`derived_growth_comparison`、
`registered_margin_target_gap`。覆盖表保留全部 11 类型，三类未测量的尝试数为 0、
成功比例为 null，不进入本轮八任务的统计分母。

面板边际在调用前固定为 `mu_panel(x_i)=1/8`。这是工程设计选择，不是现实金融需求
分布的估计，也不是最优训练比例。每类型只选一个实例，不能外推为该类型的主体、
期间、数值范围和来源变体均已覆盖。

这些已多次阅读和调试的来源明确标记为开发用途；原档案路径即使名为 `test.json`，
也不恢复为未见盲评集。

## 3. 统一生成条件、次序与硬预算

全部十六会话从独立初态使用相同的 Public Protocol v2、Update publication v1、
Action publication v1、中性完整任务 SYSTEM_PROMPT 和教师配置。仍是给定公开计划、
合法候选下的选择与明确提交，不新增自主规划、私有推理请求或一般知识修订。
历史 B、C/S、Share 和校准会话既不进入统计总体，也不作为提示示例或响应前缀。

| 资源 | 冻结值 |
| --- | ---: |
| 固定任务／每任务会话／总会话 | 8／2／16 |
| 单会话 Action 上限 | 12 |
| 单会话 Submission／Provider attempt 上限 | 32／32 |
| 总 Provider attempt 上限 | 512 |
| 单次 Completion 上限 | 8,192 |
| 单次 HTTP body 上限 | 98,304 bytes |
| 输入字节准入代理上限（含 1,024 allowance） | 99,328 |
| 单次 reserved allowance | 107,520 |
| 全总体 reserved allowance | 55,050,240 |
| 表示完整序列上限 | 32,768 |
| 自动重试／模型回退／失败替换 | 0／0／0 |
| Student 权重／forward／更新／GPU | 0／0／0／0 |

教师配置为现有 `deepseek-v4-pro`、thinking disabled、temperature 0.7、top_p 1.0、
非流式单 JSON 对象。保留当前 transport 的 response-model 检查及实际 usage 记录，
不声称服务可用性或远端权重不可变。512 和 55,050,240 是上限，不是必须用满的调用数、
实际 Token 用量或费用估计；有效 Final 后立即停止。

旧 TransportConfig 的历史总体上限仍为 384，不改写旧源文件。新包装仅以受限制的
PanelTransportConfig 子类型把本面板总体字段固定为 512，继承完全相同的单次请求、
32-attempt 会话限制和 transport 序列化。十六个不可重复启动的登记 × 每个最多 32 次，
给出真实调用的 512 上限；不依赖运行后才计算的总数来补救越界。

冻结次序为两轮，每轮四个双会话波次：

```text
第一轮：(F01,C01) → (G01,A01) → (D01,R01) → (B01,S01)
第二轮：(F02,C02) → (G02,A02) → (D02,R02) → (B02,S02)
```

每个波次最多并发 2，等待该对结束后才启动下一固定对，不按结果或完成快慢重排。
普通完整模型失败保留但不触发替换；unknown、未分类内部执行/transport 错误或凭据
异常使后续未启动波次停下，仍给所有剩余登记写出 `not_started`。已启动的同波次
会话继续保存其结果。整个登记总体始终为 16。

## 4. 只扩展必要接线，原执行语义不变

新增包 `finance_qa_vnext_task_panel` 负责总体、政策、统计和导出；使用同一 Catalog、
Program/Share adapter、PublicQARuntime、OnlineModelCallback、HTTP sender 和独立
qualification。父提交 `171035326e1f88b9e8691e02742cadacdcb94dce` 的全部 Python
实现文件必须字节不变；不放宽 Schema、Operation、Action/Update、Final 或 Mapper。

准备检查八个真实初始请求、统一入口九条既有离线会话最后两步的请求形态，以及
上一轮两个 B/T16 的已知长状态，共 28 个形态。已有请求仅用于预算和 publication
接线检查，绝不进入新在线前缀。初步只读检查为 28/28 在预算内、最大 body 78,532
bytes；正式准备还会重新绑定这些检查。它不证明所有未来生成状态都在预算内，
每次实际请求仍由原 transport 作独立长度准入。

初始形态 body 字节分别为 F 53,082、C 58,951、G 59,900、A 66,432、D 60,027、
R 60,002、B 73,393、S 70,029；它们不是 tokenizer 的精确 Token 数。

新增统计观察器必须正确读取两种已合法支持的 Claim 引用：Program 的标量 selector
和 Share 的无 selector 引用。它保留实际完整 input reference，并区分字段缺席和 null，
不为 Share 自动补 selector，也不修改任何已接受动作。

## 5. 可复用表示政策与新数据身份

本轮复用同一五文件 tokenizer/config 资产及版本；实际位置上限须为至少 32,768，
RoPE 不扩展，tokenizer 声明的 131,072 不提供额外位置权限。
旧 24,576 binding、旧长度适配 condition 和原 34 候选身份均不修改。

新表示 POLICY 只定义资产、32,768 上限、模板、assistant-only mask、suffix、因果
位移及 CPU 小批次规则，不绑定 B01/B02 或具体候选。采集完成后再创建 DATA BINDING，
绑定本轮生成条件、全部十六个登记/资格结果及实际可导出的候选 ID。

正向候选仍只能来自：真实模型来源已核验、会话 Qualified、提交 admitted。
原 messages、target UTF-8、反馈和 State 原样保留，不规范化目标 JSON，不拼接未来
状态或失败会话。失败、unknown、not_started 均不产生虚构的正向完整包。

所有候选统一不截断编码。超过 32,768 的记录保留候选与诊断，消费数组为空；不临时
加长、不删行后重新定义包分母、不通过表示状态回写模型资格。
完整包分母来自该有效会话全部实际 admitted events，不从 fit 子集反推，不硬编码 17。
每个包是一组逐真实请求的响应监督，不是把全部请求串成一条长对话。

可消费记录按同会话最多两行生成动态右侧 padding 的 CPU 整数数组，验证精确 UTF-8
恢复、prompt/header/suffix/padding 非目标 mask、labels 和因果前驱，以及 NPZ 回读。
这不构成 GPU 训练可行性或 Student 学习收益的证据，不运行旧 P/Q 损失预检。

## 6. 分层测量与结束条件

对每个固定任务，只有两个结果均可判定时才给出 `q_i=成功数/2`；全体可判定时才给出
`q_panel=成功数/16=sum_i (1/8)*q_i`。unknown/not_started 保持 null，不算模型失败，
也不从分母中删除。完整记录的模型失败是有效实验结果，不由其他任务成功抵消。

实际 Action、Update、Claim 消费、结构依赖深度、语义操作深度和可观察选择依赖深度
均从本轮轨迹核对，完整轨迹和失败前缀分开。不给 B 预填深度三，也不把不同任务的
成功率差异解释为深度因果效应或隐藏推理能力。

同任务最多一个配对、全体最多八对，只比较真实 Qualified 且现有投影 supported 的
轨迹。允许 Qualified 同时 projection undetermined；也允许两条 Qualified 等价。
至少两个商类不是完成条件，不用旧 Share 类或新调度差异充当两类。

经验条件频率只在该任务有成功且全部有效观察已映射时报告：`n_i,z/m_i`。零成功时为
null；存在未映射有效轨迹时也为 null，不删掉它们后缩分母。单个映射成功或两个等价
成功可形成当前有限观察中的点质量；它不是所有可能行为只有一个类的证明。

分别保存以下比例/计数，避免隐去筛选造成的任务边际变化：

- 登记面板的精确 `1/8` 边际和每任务 2 次尝试；
- 每任务成功、已映射成功和完整表示包数；
- 实际成功池任务比例 `m_i/sum_k m_k`；
- 完整包池比例、fit 行池比例和完整包内行数比例。

“每任务至少有一个完整可消费包”只表示全支持的素材条件可用；本轮不生成最终任务/
类权重，因此 `full_support_training_materialized=false`。若有任务缺少支持，明确
记录不可物化该完整面板，不删除任务来假装实现固定边际。

工作流的完成对象是冻结、无替换记录、分层测量和来源/完整性衔接，不要求 16/16
成功、不要求全部投影可判定或所有记录 fit。“八任务各有一个完整成功见证”单列为
科学观察结果，而不是否定正确记录失败的通过门槛。

## 7. 预先登记的运行入口

从仓库根目录使用既有环境；源码提交冻结后准备，准备核验后启动唯一登记总体：

```bash
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python \
  -m trusted_synthesis.experiments.finance_qa_vnext_task_panel prepare \
  --root /data1/zhuxinrui/projects/Data-Synthesis \
  --design /home/zhuxinrui/.codex/attachments/2942fc0e-c982-484c-a179-8cb06dfb051a/pasted-text.txt \
  --run-tag fixed_eight_task_panel_v1_20260906 \
  --output trusted_data_synthesis/artifacts/qa_vnext_task_panel/fixed_eight_task_panel_v1_20260906/preparation

OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python \
  -m trusted_synthesis.experiments.finance_qa_vnext_task_panel run \
  --root /data1/zhuxinrui/projects/Data-Synthesis \
  --preparation trusted_data_synthesis/artifacts/qa_vnext_task_panel/fixed_eight_task_panel_v1_20260906/preparation
```

已有 execution 不覆盖、不恢复或追加会话。`analyze --preparation ... --execution ...
--output <新目录>` 是独立资格与表示的只读重分析，不调用 Provider 或 Finance Operation。
准备/分析阶段对这些入口安装抛错计数器；所有阶段禁止 Student Module、权重和 CUDA
初始化。守卫是受监测入口证据，不声称任意第三方代码的形式化隔离。

CPU 进程使用上面显式给出的 2 个 OpenMP/MKL 线程设置，适用于每批最多两条的小张量
检查；不据此声称已优化训练性能。它不改变 Tokenizer、内容、整数数组、mask、长度
政策或教师 HTTP 参数。

正式调用前的新增组件控制 72 项通过；三个构造 HTTP 集成场景也通过：完整十六会话、
F01 完整失败但其余会话继续、F01 内部异常且 C01 完成/剩余十四个保留未启动。
初版新面板在前两个场景的 Share 进度统计遇到合法引用缺少 `selector` 的读取错误；
资格结果本身有效，未发生真实 Provider 调用。新通用观察器保留缺席字段及原引用后，
上述场景及只读重分析均通过，旧 B 观察器、Runtime、Schema 和准入标准没有修改。
这些测试不是本轮十六个新模型会话，也不是通过测试扩大样本数。

## 8. 正式采集与实测结果

### 8.1 冻结与总体结果

第 1–7 节及实现先于真实调用冻结并推送。源提交为
`555a76100c8c3f197cb9fc1058e838f2f6a0d6e1`，源码树
`563de0bfb68361abec83e9e5e446812899649820`，绑定全部 888 个 Python 实现文件。
其中父提交的 879 个实现文件逐字节保持不变，只有新面板包装被加入。

本轮生成条件：
`qa_vnext_model_execution_task_panel_condition:eef6edd96efb988b605a80108e9331e31d6e6e7c78624bb6bb8d6d2818568355`。
表示政策：
`qa_vnext_model_execution_task_panel_representation_policy:6e324a447eecc9e5e975044ffbf923be43231a7795e7cdb0c5762bf4b92dc856`。
正式报告：
`qa_vnext_model_execution_task_panel_report:3173425beb07bccba47b47aafa53229817bad07c613f9030b6eb140399bb987a`。

全部十六个会话按预登记两轮/八波次完成：15 个 Qualified、1 个已判定失败，
unknown/not_started 均为 0。没有替换、额外探测、网络重试、模型回退或停止后的补采。
失败会话 S01 用满 32 次提交；其他会话在有效 Final 后立即停止。

因此本固定面板的有限观察为 `q_panel=15/16=0.9375`，八个任务均至少有一个完整
成功见证。它不是稳定总体能力的精确估计，也不与历史 B、C/S 或其他条件拼接。

| 任务 | 成功／登记 | 调用数 01，02 | 正向候选／fit | 完整包 | 可映射成功 |
| --- | ---: | ---: | ---: | ---: | ---: |
| F 事实检索 | 2/2 | 3，3 | 6/6 | 2 | 2 |
| C 注册跨指标比较 | 2/2 | 3，3 | 6/6 | 2 | 2 |
| G 跨期增长率 | 2/2 | 7，7 | 14/14 | 2 | 2 |
| A 跨期平均 | 2/2 | 9，9 | 18/18 | 2 | 2 |
| D 跨期绝对变化 | 2/2 | 8，7 | 14/14 | 2 | 1 |
| R 注册比率 | 2/2 | 7，7 | 14/14 | 2 | 2 |
| B 两增长率绝对差 | 2/2 | 18，17 | 34/34 | 2 | 1 |
| S 来源明确部分／整体占比 | 1/2 | 32，12 | 7/7 | 1 | 0 |
| 合计 | 15/16 | 152 次 | 113/113 | 15 | 12 |

三类来源未实例化仍保留为未测量，而不是失败任务；它们没有进入八任务的 1/8 边际。

### 8.2 实际执行、依赖深度与拒绝

总量闭合为：

```text
152 次实际调用／提交
  = 50 次准入 Action + 50 次准入 Update + 15 次准入 Final + 37 次未准入提交

115 次准入
  - S01 失败前缀中的 1 Action、1 Update
  = 113 条正向监督候选（49 Action + 49 Update + 15 Final）
```

50 个实际 Observation 的首次后继提交均为合格 accept Update，产生 50 个 Claim；
其中 48 个随后由准入 Action 或有效 Final 消费。未消费的是 S01 和 S02 的两个
求和 total Claim。37 次拒绝是 Runtime 准入拒绝，不是模型主动 reject Observation。

拒绝分布为 D01 1 次、B01 1 次、S01 30 次、S02 5 次；错误码汇总为
`admission.alternative_set` 29 次、`admission.public_judgment` 4 次、
`admission.final_qa` 4 次。没有观察到 Update 错误。

下表深度依次为“实际结构／实际语义操作／可观察选择依赖”，不是解释长度或隐藏推理。

| 任务 | 01 深度 | 02 深度 | 实际范围 |
| --- | --- | --- | --- |
| F | 1／0／0 | 1／0／0 | 两个完整会话；lookup 在当前语义权重中透明 |
| C | 1／1／0 | 1／1／0 | 两个完整会话 |
| G | 2／1／0 | 2／1／0 | lookup Claim 被 growth 实际消费 |
| A | 2／1／0 | 2／1／0 | 多个 lookup Claim 被汇聚运算消费 |
| D | 2／1／0 | 2／1／0 | 两个完整会话；D01 额外 Final 拒绝不增加深度 |
| R | 2／1／0 | 2／1／0 | 两个完整会话 |
| B | 4／3／0 | 4／3／0 | 均完成 lookup→growth→signed gap→absolute |
| S | 1／1／1 | 2／2／1 | S01 仅为失败前缀；S02 为完整会话 |

除了 S01 的 `reached_prefix`，其余十五条均为 `complete_session`。
本轮确实测到不同登记结构的统一接入，但任务间的来源、输入、操作和输出同时变化，
不能把成功率差异单独解释为深度效应。

### 8.3 S01：已知失败及反复错写的候选 ID

S01 的证据完整、真实模型来源可核验、已到达前缀的轨迹有效，但没有 Final，
`qa_valid=null`、`Qualified=false`，终止原因为 `submission_budget_exhausted`。

| 提交 | 实际事件 |
| --- | --- |
| T1 | `share_ratio` 被拒，`admission.public_judgment`：basis 的两项 evidence_refs 顺序与所选候选相反。 |
| T2–T3 | `relation_sum` Action、accept Update 准入，形成一个 total Claim。 |
| T4–T32 | 29 次 `share_ratio` Action 被 `admission.alternative_set` 拒绝，完整候选列表持续包含同一个错误 ID。 |

正确 ID 与错误 ID 分别是：

```text
正确：finance_qa_vnext_offered_action:7edc356d1ae7b1592fc0d099579983cee41dea3745868fa4567e7a9f4fbb3f40
错误：finance_qa_vnext_offered_action:7edc356d1ae7b1592fc0d099579983cee41dea3745868fa4567e7a9f4bb3f40
```

错误串少一个 `f`，哈希部分为 63 而非 64 字符。29 次对应的 missing/extra ID 相同，
T5–T32 的全部 28 个请求均已给出这组精确反馈。T13、T17、T25、T31 曾改选合法的
reconstructed-total 候选，但完整列表仍含错误 disclosed-total ID，因此仍被拒。
不能将这一现象写成“29 次响应完全相同”或“模型从未改变选择”。

最终没有实际后继 Claim 消费或比例运算执行，不能据此断言模型不会计算占比。
32/32 实际请求都含冻结的 Action/Update publication，唯一 Update 也已通过；
现有证据支持公开规则下的内容复制/提交合规失败，不支持将其改写成缺失 Update
公开合同。为什么持续错写仍属未测量的模型内部原因。

### 8.4 三个成功但投影未定的会话

D01 的 T7 Final 被拒，T8 后准入。两次 result 分别为带 `currency`、`unit` 的
`{value:"125",...}` 和 `{value:"125"}`；answer Claim 相同、citation 集合相同但顺序
发生变化。已接受 difference Claim 的 output 为 `{value:"125"}`。
记录的错误是聚合 `admission.final_qa`，不把观察到的字段差异冒称为分别落盘的
验证子项结果。D01 最终完成 3 Action、3 Update、1 Final，另有 1 次拒绝。

B01 的 T5 revenue-growth Action 被拒：basis.claim_refs 正确，但 evidence_refs
为空，公开所选候选要求两个 evidence refs。T6 保留同一 operation/inputs/parameters，
补齐所要求的 basis 后准入，T7 接受其 Observation。被拒步骤没有执行或 Observation，
拒绝前后 accepted Claims 均为两个。最终仍完整执行 8 Action、8 Update 和有效 Final；
绝对差为 `2.757665967870018967554982530 percentage_points`。额外调用不是更深推理。

S02 的 12 次提交中有 7 次准入、5 次拒绝：

| 提交 | 实际事件 |
| --- | --- |
| T1–T2 | `share_ratio` 的 decision.obligation_id 写成 total，候选要求 ratio；basis 两项 evidence_refs 同时逆序，被 public_judgment 拒绝。 |
| T3–T4 | 求和 20,397＋1,416 并 accept，得到 total=21,813 Claim。 |
| T5–T6 | `share_ratio` 使用分子 Evidence 20,397 和披露总额 Evidence 21,813，随后 accept。 |
| T7–T8 | `scale_percent` 消费 ratio Claim，随后 accept。 |
| T9–T11 | 三次 Final 被 `admission.final_qa` 拒绝。 |
| T12 | Final 准入，result 为 `{"unit":"percent","value":"93.508458"}`。 |

求和 total Claim 没有被后继准入 Action/Final 消费；实际答案路线为 disclosed_total，
不是因为调用过求和就归为 reconstructed_total。ratio Claim 为
`0.93508458258836473662494842525099711181405583826159`，percent Claim 为
`93.508458258836473662494842525099711181405583826159`，最终按公开的
`share_percent_quantized`、`final_quantum="0.000001"` 投影至六位小数。

失败 Final 的具体差异保留如下，四次 unit 始终为 percent，并没有单位修正：

| Final | result 相对最后准入版本的差异 | citations 差异 |
| --- | --- | --- |
| T9 | 完整精度数值，另有 currency/definition/metric/period/scope/subject | 多出 relation Evidence |
| T10 | 数值已六位小数，仍有上述六项字段 | 多出 relation Evidence 和三个 Claim ID |
| T11 | 完整精度、上述字段及 lineage | 已是最终正确的两项 Evidence |
| T12 | 仅 unit/value，六位小数 | 实际分子与披露总额 Evidence |

源码可核对 Final checker 对 result 对象及最终 Claim lineage 引用集合的要求；
本次诊断没有重跑 checker，也不把聚合错误解释为已经分别实测每个子条件。

上述 D01、B01、S02 保存的投影限制均为
`reject_or_unadmitted_effect_not_quotiented`。当前 Mapper 未解释拒绝、反馈和预算
历史的商关系，因此三个 Qualified 成功保持有效，同时 projection 为 undetermined。
没有通过忽略这些事件、删除有效轨迹或临时扩展 Mapper 填满类数。

### 8.5 有限比较与真实任务池比例

F/C/G/A/R 的各两个 Qualified 轨迹均 supported，共五个实际同任务配对，关系全部
为 equivalent。这五个任务可报告各自本有限样本的点质量频率 `2/2`，不称为全体可能
行为仅有一类，也不把五个不同任务合并为一个统一商分布。

D/B 各有一个未映射成功；S 的唯一成功本身未映射。因此三组条件经验 π 均为 null。
没有用 D02/B02 单独重新归一，也没有给 S02 强行分配已确认类。十二个 mapped 成功
与十五个 Qualified 是不同计数。

| 任务 | 预登记 μ | 成功池／完整包池比例 | fit 行池比例 |
| --- | ---: | ---: | ---: |
| F | 1/8 | 2/15 | 6/113 |
| C | 1/8 | 2/15 | 6/113 |
| G | 1/8 | 2/15 | 14/113 |
| A | 1/8 | 2/15 | 18/113 |
| D | 1/8 | 2/15 | 14/113 |
| R | 1/8 | 2/15 | 14/113 |
| B | 1/8 | 2/15 | 34/113 |
| S | 1/8 | 1/15 | 7/113 |

本轮所有正向行均 fit，因此 fit 行池和完整包内行池比例相同，但二者均不等于
预登记 1/8。S 的失败改变成功池比例；不同会话的准入单元数又改变平铺行比例。
八任务都已有可消费包，所以基础监督素材的全支持条件可用；没有生成最终任务/类
权重，`full_support_training_materialized=false`、`final_training_weights=null`。
这也不意味着尚未完整映射的 D/B/S 条件分布已经可用于商类优化。

### 8.6 原样监督表示、CPU 与实际资源

113 条正向候选均从本轮十五个 Qualified 会话的原 HTTP messages/原响应导出，
全部 fit，形成十五个完整的逐请求监督包。S01 两条准入前缀原始证据保留，但由于
会话未 Qualified，不进入正向池；没有把它们拼入 S02。

新 DATA BINDING：
`qa_vnext_model_execution_task_panel_representation_data_binding:b0058a319fc5903747151b2b0bfc1675b2a88cda0fd7af31ff1ec5a67ee67f83`。
新 Token 数据集：
`qa_vnext_model_execution_task_panel_token_representation_dataset:4f039114de5e2638ee70ebc92180b17af9789a5f531db08015670a240dde4bf2`。
它们没有冒用上一轮固定 34 条候选的 condition 或数据身份。

实际序列长度为 14,219–24,950，统一上限仍为 32,768，无截断、删字段、重写 target
或超限重定义。64 个同会话小批次覆盖全部 113 行，磁盘 NPZ 数组逐行与正式记录一致。
本地 tokenizer 计数如下，不能与 DeepSeek usage 混用：

```text
prompt                2,132,942
target                   75,368
suffix                      226
完整序列位置           2,208,536
动态 padding              26,165
含 padding 的序列位置   2,234,701
```

实际 Provider usage 为 prompt 2,861,564、completion 84,665、total 2,946,229；
cache hit 1,571,968、cache miss 1,289,596，两者之和等于 prompt。
152 次响应都没有提供 reasoning_tokens，因此其总量为 null，不填成 0。
观察到的模型名均为 `deepseek-v4-pro`，生成条件违规计数为空；没有 HTTP 失败或隐式重试。

152 次 reservation 对应 allowance 16,343,040，低于冻结的 55,050,240；它不是实际
usage 或费用。最大实际 body 78,532 bytes、输入代理 79,556，均在原预算内。
reservation 的 UTC 范围为 `2026-09-06T14:54:35.838877+00:00` 至
`2026-09-06T15:04:04.362244+00:00`，不是精确会话结束时间或性能基准。

没有加载 Student 权重、运行 forward、更新参数或使用 GPU。CPU 加载通过不等于
显存、训练栈可运行性或学习收益已经验证。

### 8.7 检查、复现与历史不变

最终通过的新增测试为 `72 + 3 + 1 = 76` 项：组件/进度控制、三个构造 HTTP 集成场景、
冻结提交上的真实入口接线测试。最后一项使用真实 source snapshot/Catalog/adapter/
Runtime/qualification/Tokenizer，只有外部 HTTP/凭据输入被替换为测试 I/O；仍不计作
实际模型样本。最初两个 Share 观察器接线失败的 JUnit 一并保留，未掩盖开发修订过程。

正式准备的 28 个请求形态控制全部通过。真实 152/152 个 HTTP 请求包含同一中性
提示及两种 publication。只读重分析生成与原分析逐字节一致的全部 155 个文件、
49,636,814 字节，包括完整报告、候选、Token 和 CPU NPZ；未重新调用 Provider 或执行
Finance Operation。发布回读又核对了 52 个嵌套清单和磁盘数组/候选/实际事件绑定。

全部 10,176 个历史工件、451,228,279 字节保持不变；父提交 879 个 Python 实现文件
和本轮冻结的全部 888 个 Python 文件均未漂移。准备、只读分析和回读的禁用执行入口
计数为 0，在线阶段 Student/CUDA 禁用入口计数也为 0。发布前另作本地精确密钥字节
检查，匹配数为 0；密钥没有进入工件或文档。

发布核验记录：
`qa_vnext_model_execution_task_panel_publication_verification:4449279beaad5aadd3fb241ead671aba5f37ccf7058bb251030ab7dfb63d4b96`。
本轮未重跑完整历史 Action/Update 审计链、旧长度实验或 P/Q 预检。

### 8.8 工件入口

新根目录 `artifacts/qa_vnext_task_panel/fixed_eight_task_panel_v1_20260906/` 共
2,771 个文件、196,734,857 字节。所有实际原始响应、失败证据、资格、正向候选、
非映射状态和完整表示都保留。

- [正式报告](../artifacts/qa_vnext_task_panel/fixed_eight_task_panel_v1_20260906/execution/analysis/report.json)
- [逐任务测量与边际](../artifacts/qa_vnext_task_panel/fixed_eight_task_panel_v1_20260906/execution/analysis/measurement.json)
- [十六会话结果](../artifacts/qa_vnext_task_panel/fixed_eight_task_panel_v1_20260906/execution/analysis/session_outcomes.json)
- [完整包清单](../artifacts/qa_vnext_task_panel/fixed_eight_task_panel_v1_20260906/execution/analysis/session_packages.json)
- [有限配对](../artifacts/qa_vnext_task_panel/fixed_eight_task_panel_v1_20260906/execution/analysis/finite_comparisons.json)
- [CPU 批次索引](../artifacts/qa_vnext_task_panel/fixed_eight_task_panel_v1_20260906/execution/analysis/cpu_loading.json)
- [发布核验与测试日志索引](../artifacts/qa_vnext_task_panel/fixed_eight_task_panel_v1_20260906/publication_validation/report.json)

## 9. 收口与下一科学对象

本轮固定面板采集、分层测量和完整监督接口已完成，不因 S01 失败或三个成功投影未定
追加样本、换题或修改旧结论。获得多类型成功和完整 CPU 包，不意味着 VTDO 概率更新、
任务/类权重物化或 Student 效用已经成立。

本轮具体保留的后续问题，是 D/B/S 中已实际出现的拒绝/反馈/修正历史的有限商解释，
以及 S01 在公开规则下的提交可靠性。若下一阶段补 Mapper，应针对这些实际事件定义
明确的有限解释，不重开来源、Action/Update publication 或长度适配来重复已关闭问题。
更多真实任务绑定、真正独立评价集和新协议有限分布优化仍需各自固定对象。
本轮不启动这些后续实验，旧主线保持暂停。
