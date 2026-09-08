# FinQA E1 / J2：可读来源—输入—结果绑定视图

## 1. 审计承接与限定问题

依据 2026-09-08 用户审计附件，SHA-256：
`750b32660ad13629190146a86b22112e1e4906d850d753d1962dc9b97d338eea`。
父提交为 `d43b5eb803ee07558dee309eee018fb0046d5811`。

上一轮 P 的理由长度解耦确已进入公开合同、解析与真实操作；C/P 各0/4、无尺度恢复的
负结果与分层测量接受并收口，不重跑、不补样。理由上限与原始提议覆盖问题不再校准。

本轮只检验一个新假设：**机械地把已有结果的原ID、来源、实际有序输入和值对应展示，
能否帮助模型将公开判断落实到正确对象、目标依赖与完整答案。**
这是待检验的信息呈现辅助，不预先认定长ID、排版、记忆或单位知识是唯一失败原因。

固定 P 和原 R；只用原 E 信息条件，在已有开发任务 E1 与 J2 上各做 V0/V1 两次新会话。
不改问题、来源解释、工具、常量、接受生命周期或 Final，不给财务角色/正确公式，
不做 Claim 自动删除、筛选、候选限制、强制反思、一般知识修订、Student、VTDO 或 tokenizer 导出。
旧 F 结果和历史十八条有效轨迹保持，不宣称本轮覆盖完整来源 F，旧主线不在此恢复。

## 2. V0 与 V1 的公开差异

| 条件 | 当前公开请求 |
| --- | --- |
| V0 | 原 P 的 Context、Claims、pending、P表达规则和原R反馈，不增加字段 |
| V1 | 完整保留 V0 内容，另加 `accepted_result_bindings` |

V0 与相同 session ID 下的 `ReasonPolicyRuntime(P)` 请求和转移完全一致。
V1 只追加视图及派生 request ID；原 state、协议、schema、规则和 Context 不改写。
两个条件的协议均为 `finqa_source_numeric_h2.v2.2.reason_policy`；
本次独立呈现版本为 `finqa_readable_accepted_bindings.v1`。

V1 的每一行对应一个已接受 Claim：

| 内容 | 机械来源 |
| --- | --- |
| 完整原 claim_id、value、exact_value、actual_expression | 原 Claim / Observation，数值原样保留 |
| source_ids 与来源记录 | 原 lineage；原 numeric_catalog 项和原文本片段/行列标签/位置 |
| execution.operation 与 operation_submission | 实際已经发生的操作与原提交编号 |
| execution.ordered_inputs | 操作当时的完整输入ID、值、精确值和来源ID；顺序不变 |
| numeric_derivation_display | 用实际 operation 和实际有序输入值拼成可读数字式，右侧复制原输出值 |
| acceptance | 原 accept Update、观察ID、提交编号与请求ID |

例如显示 `divide(15.3, 1000) -> 0.0153` 时，它必须确实引用15.3的原Claim；
即使模型理由声称想换算另一个量，也不把显示改为它本来想算的式子。
read 的显示使用原 source ID；常量值来自原常量ID，其他输入值来自执行前已接受 Claim。

所有已接受结果按原接受顺序列出：同值不同来源不合并，同源重复读取或重复计算也不合并，
曾被错误 Final 使用和未使用的结果不删除、不降序或推荐。常量运算所得无来源 Claim 同样保留。
pending 或被 reject 的观察不冒充已接受可消费结果；原 pending 内容仍在 V0状态原位置。

来源文本、行列标签和数值 token 完全复制，不清洗成“正确分母”“2017正确价值”等标签。
原来源未明确给出的单位不补齐；派生量不获单位或财务角色认证。
比如J2价格原文用多个年份和价格的 respectively 顺序表达，显示器保留原文与token位置，
**不代模型推断并新增某价格的年份字段**。原表格已有的年份列标签可以原样显示。

### 2.1 视图的信息边界与构造责任

视图函数的输入只有当前公开 Context/Claims、既往已公开的实际 Observation/Update 记录。
不读取隐藏 target、gold、参考程序、方法检查点或模型 reason 来构造结果、次序或标签。
执行与重放均使用 `ReadableBindingRuntime`，直接继承已冻结 P 的解析和 transition；
无全局 monkeypatch、ID别名、模糊匹配、输入重写或额外模型语义字段。

V1 会重新展示过往公开事件中的直接输入与接受记录，而原 P 的无历史调用当前状态主要保留
展开表达式、数值和lineage。因此本轮**不声称只是等信息量的纯排版变化**：
它是机械重述公开历史的绑定信息包，不增加外部事实或隐藏答案。
即使改善，也不能精确归于某个排版元素，或声称无此辅助也有同样表现。

当前错误 Final 不会触发视图筛选、坏Claim标记或推荐排序；视图始终保留全部接受记录。
原R文字仍只在当前反馈为 `final.target_not_established` 时显示，其他成功转移或错误覆盖后清除。
不强化、不永久保存、不添加换算因子或参考解法。

## 3. 八个新完整会话与预算

| 任务 | V0 | V1 | 每单元分母 |
| --- | --- | --- | --- |
| E1：尺度与实际输入 | E1_E_V0_01、E1_E_V0_02 | E1_E_V1_01、E1_E_V1_02 | 2 |
| J2：期间配对与中间量消费 | J2_E_V0_01、J2_E_V0_02 | J2_E_V1_01、J2_E_V1_02 | 2 |

固定线程池提交顺序：
`E1_E_V0_01 → E1_E_V1_01 → J2_E_V0_01 → J2_E_V1_01 → J2_E_V1_02 → J2_E_V0_02 → E1_E_V1_02 → E1_E_V0_02`。
单波最多八路并发；HTTP实际开始时间受调度影响，不宣称严格串行或时间随机化。
没有新增seed或相同随机种子配对。

每个视图内 E1/J2 等权各占一半；主结果分别报告任务×视图的完整有效数/2，
再报告每个视图的合计/4。旧C/P、B/R和十二题面板均不并入新分母。
J2是已有开发题加入新的呈现诊断，不是新来源或盲测。

全部从空 Claims、无 pending 的新初态开始，不接续历史错误或合适提议。
原 E Context、题目、来源ID/数值/解释、工具、常量、Final数值/单位/引用与符号目标不变。
直接成功也有价值；未触发错误Final的恢复为 NOT_APPLICABLE，不补样制造错误。

固定原模型配置和全部资源限制：
`deepseek-v4-pro`、原中性SYSTEM、temperature=0.7、top_p=1、Thinking disabled、
JSON object、max_tokens=8192、180秒总超时、30秒连接超时，无native tools。
每会话12次实际操作、32次模型提交、最多32次Provider尝试；
全批最多256次请求，预留Token上界27,525,120，不是实际用量预测。
98,304字节序列化请求上限、原公开响应/HTTP响应上限均保持。

视图会增加输入内容；不为避免预算失败而截短原Context、删Claim、裁剪视图或追加额度。
资源停止、传输未知、失败与未处理观察如实留档，保持原分母。
无重试、fallback、替换、续跑或扩样。有效Final仅停止自己的会话，不取消其他预注册会话。

## 4. 预先冻结的过程测量

### 4.1 保留原始提议分层

继续从原始字节区分：
合法无歧义JSON的Action形状、完整P结构合法、语义准入、真实Observation、明确接受/拒绝、
后续实际Action消费者、失败Final选择和有效Final的真实依赖。
非法JSON不从片段晋升为Action。长reason只是表达/成本特征，不当作质量或奖励。

分别保存错误Final后各层首次出现位置，而非模糊“首次提议”总称。
完整恢复仍要求实际触发目标拒绝后，在原预算内通过原Final。
正确的新量出现、接受、更多操作或更少拒绝，均不独立等于恢复。

### 4.2 E1/J2分开的只读方法诊断

新的 `recovery.py` 为两题分别定义检查点，不把E1的目标拆解套在J2：

- E1：分母与分子同尺度、分子与分母同尺度、归一化比例、完整百分比目标。
- J2：原目标的两个年度乘积项、完整差额目标。

检查采用原来源符号等价关系，允许交换乘法次序、不同尺度转换顺序与已有比例的后续调整。
J2可用代数分解，完整目标匹配不限于参考两个乘积再相减；
跨期乘积不一律标为错误，它可能是等价分解的一部分。
这些有限检查点只用于审计定位，既不穷尽所有合法中间量，也不参与视图或动作准入。

真实依赖图从实际有序Claim输入与明确Update建立，不把“另一个符号相同的Claim”当作真正被使用。
记录方法检查点是否执行、接受、被后续Action消费，及是否进入有效Final真实祖先。
已有正确量之后才选错、或首先未形成正确量，应据此区别，不统一归因终局选择。

### 4.3 公开意图与实际选择：先定口径，批后逐条审阅

这是**未盲化的批后人工描述性标注**，不声称自动读出模型意图或唯一根因。
覆盖每条合法无歧义JSON、kind=action的原始提议，包括结构/语义被拒的提议；
实际执行子集另行汇总。JSON不合法的原始失败保留，但不臆造意图标签。

| 标签 | 口径 |
| --- | --- |
| MATCH | 当前步骤的公开表述足够具体，所述对象/次序与选中ID、值和可核对来源相符 |
| MISMATCH | 明确的当前步骤对象、操作、数值次序或来源期间声称与实际所选对象矛盾 |
| UNDETERMINABLE | 表述含糊、对象无法定位，或有互相竞争的计划而当前选择不明确 |

每条标注都附解释；MATCH/MISMATCH必须附原reason/subgoal的精确引文，
并说明核对维度：operation、ordered_values、source_identity或stated_period。
封存脚本检查引文确在原响应、所有原始Action形状恰好标注一次。
脚本只验证引用与分母，不自动证明人工语义判断正确；读者可以核对原文复审。

不把长计划中所有未来步骤都要求在当前一步执行，也不以“目标未成立”倒推意图错配。
“乘13与33.32”与实际同样相乘可以在数值意图上相符，却不因此是正确年度方法；
如果明确声称正在处理2017的数量，而实际来源列是2016，则可依据原来源标注期间错配。
“需要算百分比”而未具体说明当前对象/步骤，不据实际工具结果猜测成MATCH或MISMATCH。
多项公开声称若不能辨认其当前选择，则保留UNDETERMINABLE。

意图相符不等于财务方法正确；错配也不自动证明由长ID或显示造成。
统计同时保留全部Action分母、明确可判断数、UNDETERMINABLE数、执行子集和错误Final后子集。
若展示改变了表述明确性，可判断子集也会改变，不能把该子集当独立随机样本或一般能力概率。

### 4.4 提示/视图曝光与成本

R曝光和视图曝光仅按真实Provider尝试请求统计，区分空初态视图与含已接受结果的视图，
不把终止后请求或未发送的资源停止计为模型曝光。
`binding_view_content_bytes` 是视图字段自身规范JSON的UTF-8字节累计，
不是外层HTTP序列化的精确增量；实际输入成本以完整HTTP请求体与Provider用量另外报告。
不比较不同后续状态的字节差异后声称只是版式自身的因果成本。

记录调用、提交、操作、重复表达式与已拒目标Claim的复用，成功和失败全部Token/字节成本。
缺失用量total=null，已观察小计与未知次数分开，不从Thinking设置虚构推理Token为零。

## 5. 最小新增控制、执行与封存

只运行 `tests/test_qa_vnext_finqa_readable_bindings.py`，不重跑旧46项、引用校准、
FinQA全量统计或完整历史静态控制。
新增局部构造输入检查：视图与真实Claim一致、同值不同来源/同源重复不合并、有序输入不颠倒、
理由不改写实际输入、未接受/被拒观察不列为可消费Claim、坏Final不筛掉旧结果、常量结果保留、
不读隐藏Oracle/理由、篡改显示会被核验拒绝、新请求与原始重放一致。
两题都有新的完整入口/回放控制，J2包括等价的跨项代数分解；
它们是零Provider的adapter mock，不是历史响应重执行或在线样本。
另检查直接成功的恢复不适用、引用标注分母与原文校验、未知调用和八个固定标签/权重。

先提交新源码、测试和设计，再prepare绑定全Python源码成员/字节与Git提交，
复制本文为 `design_at_freeze.md`，记录注册、初始请求、原绑定与配置、新测试输出、
意图审阅口径与历史守卫并封存。在线期间不改变视图、解析、测量、提示或样本数。
请求、原始响应和实际转移逐次持久化；执行与回放均用同一新视图Runtime。
批后逐会话审阅后，closeout重新核验原文来源、视图事实、独立算术与Final、生命周期、
逐题/逐视图分母、层次计数、实际消费者、引文标注和全部成本。

## 6. 工件、入口与结束边界

输出根：`artifacts/qa_vnext_finqa_binding_view/e1_j2_e_v0v1_2rep_20260908/`。
`preparation/`为冻结；`online/sessions/<label>/`为逐会话原文与审计；
`online/summary.json`为固定总体汇总；`closeout/`为零Provider再核验与人工审阅。

仓库根入口：

```bash
trusted_data_synthesis/.venv/bin/python -m pytest -q trusted_data_synthesis/tests/test_qa_vnext_finqa_readable_bindings.py
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_finqa_binding_view.stage prepare
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_finqa_binding_view.stage run
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_finqa_binding_view.closeout --reviews <posthoc-review.json>
```

同一输出目录排他写入，以上命令不允许覆盖旧批次或重复采样。
若V1减少明确错配并形成正确依赖与答案，只称为可读绑定辅助的有限正结果。
若仍在方法、单位/期间解释或终局消费失效，按真实层次报告，不继续叠加显示字段直到同题成功。
两组都成功或机制未暴露时也不补样制造错误；成本增加无有效收益时保留负结果。
本轮不能外推一般金融能力、无辅助能力、稳定概率、纯排版因素效果或训练收益。
八会话结束即收口，不把所有困难题修到满分作为既有有效轨迹的使用前提。

## 7. 批后结果

八个新完整会话结束并只读核验后追加；冻结副本不包含未来结果。
