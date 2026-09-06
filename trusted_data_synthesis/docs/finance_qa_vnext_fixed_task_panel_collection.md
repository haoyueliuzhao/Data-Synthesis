# QA vNext：统一条件八任务面板与十六会话采集

日期：2026-09-06。阶段：
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

## 8. 实测结果（运行后填写）

本节保留为空，待新增接线测试和冻结源下的正式采集、资格及表示结果完成后填写。
不预填成功率、商类数、实际深度或全量表示通过。上一轮已通过条件不再次作为新样本。

本阶段完成即收口。后续任务扩展、独立评价集、有限分布优化、实际事件的 Mapper
补充或 Student 实验，只能基于本轮实际结果选择，不自动补采至期待结果。
