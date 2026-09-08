# FinQA E1：解释长度与动作准入解耦的 C/P 对照

## 1. 审计承接与唯一问题

依据 2026-09-08 用户审计附件，SHA-256：
`daee008f6a978e4100d5a97380d5b396a77743999ab2ccb1b6e1747a37067c06`。
父提交为 `dbf0afb97dfacac8ceab86139844ecc4079db1e3`。

上一轮八条 B/R 会话均触发目标拒绝、无完整恢复，R 实际曝光 61 次；五条有适当换算操作核心的
原始提议因 reason 超过 480 字符而在执行前被拒。这些限定结果接受并收口，不补样、不重标记。
五项未执行提议不是五条可补算成功，也不证明去掉长度门就一定能完成后续接受与消费。

本轮只检验：**将 reason 的 480 字符上限从硬准入改为资源有界的简洁要求，
能否让原本合法的操作实际进入执行，并形成完整有效任务或实际触发后的恢复。**
长理由没有固有价值，不奖励推理篇幅，也不把理由更长或更多操作当成正确性收益。

不叠加更强反馈、不建持续恢复计划、不改 J2，不新增候选限制、单位门、Claim 自动淘汰/修复、
知识撤销、Student、VTDO、权重更新或 tokenizer 导出。历史源码、工件、文档保留原样。

## 2. 两个新表达条件，反馈固定为原 R

| 条件 | reason 公开结构 | 实际解析/准入 | 其他要求 |
| --- | --- | --- | --- |
| C | 非空字符串，maxLength=480 | 超过 480 字符被原结构合同拒绝 | 原有约束保留 |
| P | 非空字符串，无 reason 局部 maxLength | 不仅因长度超过 480 拒绝 | 原有结构、动作语义及全局资源约束保留 |

两组固定使用原 R 的同一段 `REVIEW_TEXT`，仅当前 feedback 为
`final.target_not_established` 时显示；成功操作/Update 或其他错误覆盖反馈后清除。
不提前加入单位解法，不永久保存、不追加历史合适提议为示例。
固定 R 是控制实验条件，不代表已证明 R 有效或最优。

C 的公开请求对相同 session ID 等于上一轮 R；P 只修改 reason schema、对应说明，
以及声明新合同的 protocol.version 和由此派生的内容 ID。
P 公共协议为 `finqa_source_numeric_h2.v2.2.reason_policy`；
独立实验版本为 `finqa_reason_length_decoupling.v1`。
P 的公开说明固定为：

> Keep Action reason concise and nonempty; there is no per-reason character cap. Existing response-size and session resource limits still apply. subgoal: at most 240 characters.

P 不是“把 480 改为 1000/4000，再失败就继续增大”。本轮不设置新的 reason 局部硬上限。
subgoal 仍为非空字符串且最多 240 字符；Final、Update 的 schema 不变。
全量原始 reason 保存在原始响应和合法 Observation 的 model_action 中，不截短、不代写。
较长 reason 可能增大下一 pending 请求的体积，该成本与全局限制真实保留。

### 2.1 实际解析与原始数据责任

新执行与只读重放都构造 `ReasonPolicyRuntime`，调用
`parse(raw, expression_condition)`。C 使用原 Action 字段合同，P 仅移除 reason 的最大长度。
新转移方法为原数值 Runtime 转移主体的独立副本，只将 parse 调用接到条件解析器；
AST 控制核验其余转移主体不变，没有进程全局 monkeypatch，C/P 可并发执行。

JSON 必须完整、无歧义、为对象。两个条件共同拒绝重复键及 NaN 等非 JSON 常量；
这是将原公开“合法 JSON”要求明确落实到新公共解码入口，并非只对 P 施加/放宽。
相对旧实现的完整合法 JSON 输入域，C 保留原结构与执行语义；不声称旧解析器对全部畸形
输入的错误分类逐字一致。原字段、状态与资源检查仍执行，绝不从坏 JSON 中抽取 operation/inputs 执行。

必须满足正确 state_id、合法来源/Claim/常量引用、操作与参数合法、非 read 只消费已接受 Claim；
pending 时只能明确 accept/reject。原 Final 继续验证实际 Claim、数值容差、单位、精确引用、
来源符号目标与精确算术。没有 Host 修复或自动接受。
原始 Action 形状、结构合法和语义准入分别记录，不把未准入字段变成真实操作。

## 3. 八个全新会话、固定总体与资源

| 信息条件 | C | P | 单元分母 |
| --- | --- | --- | --- |
| E：预定位证据 | E1_E_C_01、E1_E_C_02 | E1_E_P_01、E1_E_P_02 | 2 |
| F：完整条目来源 | E1_F_C_01、E1_F_C_02 | E1_F_P_01、E1_F_P_02 | 2 |

线程池提交顺序预注册为：
`E1_E_C_01 → E1_E_P_01 → E1_F_C_01 → E1_F_P_01 → E1_F_P_02 → E1_F_C_02 → E1_E_P_02 → E1_E_C_02`。
单波最多八路并发；实际 HTTP 起始顺序受调度影响，不声称时间随机化或严格串行顺序。
无新增 seed，不是相同随机种子配对。

每个会话从空 Claims、无 pending 的初态开始，保留原 E1、原 E/F Context、来源数值/解释、
工具和常量。旧 R 四条不充当新 C；不接续历史被拒提议，不继承历史答案或已接受 Claim。
C/P 从首次请求起就不同，因此检验的是**完整求解表达合同**，不是同一错误状态上的纯恢复效应。
触发时刻、错误表达式与剩余预算可不同，需逐会话报告。

模型配置与上一轮记录完全一致，包括：
`deepseek-v4-pro`、中性 SYSTEM、temperature=0.7、top_p=1、Thinking disabled、
JSON object、max_tokens=8192、180 秒总超时、30 秒连接超时、无 native tools。
同名模型不证明供应商内部快照不可变。

每会话仍有 12 次实际操作、32 次模型提交、32 次 Provider 尝试上限；
全批至多 256 次尝试，预留 Token 上界 27,525,120（不是实际用量预测）。
每次 HTTP 请求体上限 98,304 字节、公开响应上限 1,048,576 字节、
HTTP 响应上限 2,097,152 字节等既有资源限制不变。
若长 reason 导致后续请求超过整体资源限制，真实终止并保留停机记录，不截短上下文或补跑。

无重试、fallback、替换、续跑、扩样到成功、补样制造长理由或错误。
有效 Final 仅停止自己的会话，其余预注册会话仍执行。任何未知/失败都在原分母与成本中。

## 4. 预先冻结的分层测量

### 4.1 每个原始提交的六个层次

| 层次 | 定义 | 不可混淆之处 |
| --- | --- | --- |
| 原始 Action 形状 | 完整无歧义 JSON 对象明确 kind=action | 非法 JSON 不按看似正确片段晋升 |
| 结构合法 Action | 满足 C 或 P 的完整 schema | 超长 reason 在 C 可有形状而结构不合法 |
| 语义准入 | 状态、引用、操作、参数、预算检查通过 | 有合法结构但错误输入仍不准入 |
| 实际执行 | 原转移产生真实 Observation | 只描述正确操作不算执行 |
| 接受与使用 | 明确 accept，并记录后续实际输入消费者与 Final 选择 | reject、未处理或选回旧量分别保留 |
| 完整恢复 | 确实触发目标拒绝后在原预算内通过原 Final | 未触发则不适用；直接成功仍算完整任务成功 |

每个事件保存原始内容哈希、JSON/结构错误、原始 operation/inputs、reason 字符数，
逐层布尔值、真实观察、处理状态、已接受 Claim ID、后续直接 Action 消费位置、
Final 选择位置及是否处于**有效 Final** 的真实依赖图。
语义准入与 Observation 数量必须一致；解析结果与实际 event.model_submission 必须一致。
“首次提议”不再单列模糊总称：分别报告首次目标拒绝之后各层第一次出现的位置。

另行统计原始长理由（>480，仅作诊断标记）、长理由结构合法数、长理由实际执行数、
仅 reason 长度引发的 schema 拒绝，以及 reason 总字符数/最大字符数。
P 不以 >480 作拒绝或奖励条件；字符数是表达与成本特征，不是质量标签。

### 4.2 尺度提议、实际尺度与接受消费

冻结原输入核心检查使用当前可见的已接受 Claim/常量、有序 inputs、operation、state、
parameters 和可执行资源位置，解读它描述的来源表达式；不改变 reason 或完整原始响应。
来源符号检查点沿用分母转换到分子尺度、分子转换到分母尺度、完整归一化比例、完整百分比。
允许等价运算顺序与已有比例的后续转换，不只认一个参考计划。

`proposed_core_expression/proposed_core_alignment_probes` 是对原提议字段的只读检查，
不是其完整结构已合法，更不是已执行、生成 Claim 或反事实完成。
有真实 Observation 时，另外记录 `actual_expression/actual_alignment_probes`。
这些检查只在审计测量中读取冻结任务目标，不用于构造公开提示或决定动作准入。
检查点不是所有可能合法中间量的完备分类；单个未完成中间量不自动判作错误工具操作。

复用已核验的真实 Claim 依赖测量，追溯有效 Final 的真实祖先，不以符号相同代替实际消费。
另外保存被后续 Action 真正用作输入的位置，以区分“已接受并继续计算”与“最终仍选旧错量”。
理由正确、新量出现、重复拒绝减少或接受某新量，都不能独立算完整恢复。

### 4.3 完整分母、恢复子集与成本

四个信息×表达单元各完整有效数/2，C/P 各汇总数/4，必须同时展示。
没有目标拒绝的会话恢复为 `NOT_APPLICABLE`，留在完整成功/失败分母。
有触发后才记录首次拒绝 Claim、表达式、位置、剩余预算、后续分层变化与最终状态；
这些触发子集是行为筛选子集，不是独立随机恢复队列。

保留重复目标拒绝、旧坏 Claim/等价坏表达式的重复 Final；
未知与未获得后续决策的 Observation 不填成失败 Update 或接受成功。
原 R 曝光只计真实 Provider 尝试请求，不计未发送的资源停止请求或终止后虚拟下一请求。
记录所有请求/提交/操作、成功与未成功的 Provider Token、HTTP 字节和资源停机。
未报告的用量 total=null，已观察小计和未知次数分别列出；不虚构零成本或费用估值。

## 5. 最小新增控制与封存链

只运行 `tests/test_qa_vnext_finqa_e1_reason_policy.py` 新控制，不重跑旧十七项测试、
历史模型失败、引用校准或完整十二题静态见证，也不重新遍历 FinQA 统计难度。
读取旧 bindings/manifest 仅核对冻结信息，不构成旧模型样本或新的可达性统计。

本地构造输入覆盖：

- 同一个合法操作的短/长 reason，包括 480/481 边界；C/P 公开 schema 与真实解析一致。
- reason 长度变化不改输入或表达式，原文与 Observation 理由完整保存。
- 空/非字符串 reason、subgoal 超长、错误状态、非法来源、raw source 算术、未接受输入、
  错误 Update 引用、额外字段、不合法/重复键 JSON 均仍拒绝。
- 新转移主体除解析调用外与原主体 AST 一致，无全局解析器替换。
- C/P × 三种等价恢复路径的模拟 HTTP、原始响应回放、长理由分层与实际消费。
  C 的构造长提议被拒后，若测试再给一个短提议，那是明确的新模拟提交，不是 Host 截短旧响应。
- 合适量已接受并用于后续计算但最终选旧错量，仍不算完整恢复。
- P 直接成功的恢复不适用、总体分组按 C/P 而非固定 R，报告字节与层次计数一致。
- 人工构造超大 P reason 仍触发后续全局请求大小停止，停止不是新增 Provider 尝试；
  传输失败没有虚构原始 Action。

这些都是 adapter mock，零 Provider，不是模型样本；超大字符串仅是资源边界测试，
不能当模型 max_tokens 下的典型输出长度。

源码、测试和本文先 Git 提交，再 prepare 将全 Python 源码成员及字节绑定到该提交，
复制本文为 `design_at_freeze.md`，记录八个注册、初态、配置、新测试输出与历史守卫并封存。
完整运行与只读回放明确使用同一新 Runtime/条件解析器。会话排他写入，禁止覆盖；
HTTP 请求/响应、原模型公开内容和转移逐次持久化。在线期间不再改源码或指标。
批后 reporter 也在冻结中，逐会话原文审阅注释明确标为 posthoc，再核验全部封存与分母、成本。

## 6. 工件与结束边界

输出根：`artifacts/qa_vnext_finqa_reason_policy/e1_ef_cp_2rep_20260908/`。

仓库根执行入口：

```bash
trusted_data_synthesis/.venv/bin/python -m pytest -q trusted_data_synthesis/tests/test_qa_vnext_finqa_e1_reason_policy.py
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_finqa_reason_policy.stage prepare
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_finqa_reason_policy.stage run
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_finqa_reason_policy.closeout --reviews <posthoc-review.json>
```

prepare/run/closeout 不允许在同一已写目录上重采样覆盖。`preparation/` 为冻结记录，
`online/sessions/<label>/` 为原文与审计，`online/summary.json` 为原总体汇总，
`closeout/` 为零 Provider 再核验与批后注释。

若 P 合适操作真实执行并最终恢复，仅支持取消该机械门槛的有限见证。
若执行正确尺度但未接受/未使用/仍失败，障碍位置据实际轨迹报告，不继续加长理由上限。
若 P 未提出/执行合适操作，不能把全部失败继续归因于 480；若无长理由或无错误触发，
机制暴露有限，不补样制造事件。成本增加无有效收益也客观保留。
如公开 schema 与解析器接线不一致，属于实现缺陷，不归因模型；需单独说明，不替换失败样本。

本轮不是长期字符阈值调参。无论结果如何均按八会话结束，不修改本批反馈或扩成其他条件。
一般金融能力、训练收益、稳定成功概率、E/F 纯证据效应均未由此证明。

## 7. 批后结果

八个预注册会话结束并只读核验后追加；冻结副本不含未来结果。

### 7.1 固定八会话：完整成功与恢复均为零

在线冻结提交 `98918b2afae485dc0913499a136142bbe05dae13` 已在采样前推送。
八条全部从新初态执行一次，无替换、续跑、重试、未启动或未知。全部在第 32 次模型提交
结束为 `budget_exhausted`；没有改动条件后补样。

| 单元 | 完整有效 | 实际触发 | 完整恢复 | 操作 | accept / reject | 请求/提交 | 总 Token |
| --- | --- | --- | --- | ---: | --- | ---: | ---: |
| E_C | 0/2 | 2/2 | 0/2 | 11 | 11 / 0 | 64 | 253,997 |
| E_P | 0/2 | 2/2 | 0/2 | 16 | 15 / 1 | 64 | 263,160 |
| F_C | 0/2 | 2/2 | 0/2 | 10 | 10 / 0 | 64 | 402,430 |
| F_P | 0/2 | 2/2 | 0/2 | 16 | 16 / 0 | 64 | 432,166 |
| C 合计 | 0/4 | 4/4 | 0/4 | 21 | 21 / 0 | 128 | 656,427 |
| P 合计 | 0/4 | 4/4 | 0/4 | 32 | 31 / 1 | 128 | 695,326 |

八条都在第 9 次首次提出未对齐的百分比 Final：
`(15.3 / 139549) ×100 ≈ 0.01096389082 percent`。
每条首次目标拒绝后都还剩 8 次操作、23 次提交；直接成功和恢复不适用数均为零。
虽然本次首次错误位置与核心表达式碰巧一致，C/P 仍从首次公开请求起改变了表达合同，
不能据此改称为从完全相同公开状态随机干预的恢复试验。

两个条件都没有产生命中冻结尺度检查点的真实 Observation，也无相应接受、有效 Final 消费
或完整恢复。P 的公开 schema 与实际解析/回放确实一致，不能把其负结果解释成仍误用旧480上限。

### 7.2 从原始提议到实际执行的分层结果

| 层次／特征 | C（4 会话） | P（4 会话） |
| --- | ---: | ---: |
| 合法、无歧义 JSON 的 Action 形状 | 28 | 33 |
| 所属条件下 schema 合法 Action | 22 | 33 |
| 语义准入并实际产生 Observation | 21 | 32 |
| 明确 accept 的 Observation | 21 | 31 |
| 明确 reject 的 Observation | 0 | 1 |
| 合法 JSON Action 中 reason >480 | 6 | 2 |
| 长 reason 实际执行 | 0 | 2 |
| 仅 reason 上限导致的 schema 拒绝 | 6 | 0 |
| 原输入核心命中尺度检查点的提议 | 2 | 0 |
| 尺度对齐的实际 Observation | 0 | 0 |
| 尺度量被有效 Final 真实消费 | 0 | 0 |

“仅 reason 导致 schema 拒绝”是**结构层**归因，不代表该提议在状态/输入语义层一定合法。
例如 C 中部分长理由还使用 raw source 作算术输入；去掉字符上限不等于允许这种输入。
核心检查只读解读原有字段，不补写提议、构造 Observation 或计算反事实成功。

另外有 3 次 JSON 语法失败：E_C_02/22、E_P_02/19、F_P_02/26。
它们保留原文和失败成本，不从文本片段中拼接或晋升为 Action。
本批未触发全局请求大小/响应大小停止，原始资源约束仍由控制测试验证有效。

分层指标在采样前已冻结，本次无需用批后脚本修补“首次提议”覆盖面。
具体例子是 F_C_01：拒绝后首次 raw Action 在第 30 次，schema 合法、语义准入和执行位置
都为 null；它确实提出了一个长理由读取请求，但没有执行。
这一区别直接保存在正式 `action_layers` 中，而非根据 `model_submission=null` 误称完全没有提议。

### 7.3 P 的两个长理由执行：机械门槛解除，但不是正确恢复

| P 会话／提交 | reason 字符数 | 实际操作与观察 | 明确处理 | 后续真实使用 |
| --- | ---: | --- | --- | --- |
| E_P_01／29 | 567 | 分母 Claim ×1000 =139,549,000 | 30 accept | 没有后续 Action 消费，也未被 Final 选择；31/32 仍选旧错量 |
| F_P_02／13 | 529 | 已有坏百分比 Claim ×1，仍为0.01096389082… | 14 accept | 15、22 选择该新 Claim 的 Final 均失败；没有有效 Final 消费 |

两条原始长 reason 完整进入实际 Observation，未被截短或 Host 重写。
因此本批提供了 **P 的理由长度解耦实际生效** 的在线见证。
但前者只将分母转换为美元，未同步建立与分子兼容的尺度，也未继续使用；
后者是恒等重复运算，不产生新符号依赖。不能把这两个执行/接受包装为任务恢复。

原始证据：
[E_P_01 第29次响应](../artifacts/qa_vnext_finqa_reason_policy/e1_ef_cp_2rep_20260908/online/sessions/E1_E_P_01/runtime/turns/028_response.raw)、
[F_P_02 第13次响应](../artifacts/qa_vnext_finqa_reason_policy/e1_ef_cp_2rep_20260908/online/sessions/E1_F_P_02/runtime/turns/012_response.raw)。
各自下一次 Update 和随后实际 Final 已由完整重放及 Claim 输入图核验。

E_P_01 还有更直接的理由/输入不一致：第25次理由说将分母除以1000，
实际选的却是值15.3的**分子** Claim，工具执行为0.0153；26次模型自己 reject。
P 没有通过放松局部理由长度而改变这个输入选择问题。
F_P_02 第10次将坏百分比再乘100得到1.096389…，11次接受，25次将其用于 Final 仍失败，
因为仍比原目标小十倍。

### 7.4 C 中仍有合适的未执行提议，但不能补算成功

| C 会话／提交 | 原有已接受输入所描述的核心 | reason 字符数 | 真实结果 |
| --- | --- | ---: | --- |
| E_C_01／32 | 分子 Claim ×1000 | 643 | schema 拒绝，无 Observation |
| E_C_02／20 | 分母 Claim ÷1000 | 1,077 | schema 拒绝，无 Observation |

这里没有用历史五项提议重新执行；两项来自本批全新 C 会话。
E_C_01 的合适提议已迟至最后一次提交，即便单步能执行，也没有剩余提交用于接受和 Final；
不能据此断言取消其长度门就能在原轨迹剩余预算内完成。
E_C_02 第20次仍有后续预算，但继续接受、运算和正确选答案的结果没有被该未执行提议证明。

原始证据：
[E_C_01 第32次响应](../artifacts/qa_vnext_finqa_reason_policy/e1_ef_cp_2rep_20260908/online/sessions/E1_E_C_01/runtime/turns/031_response.raw)、
[E_C_02 第20次响应](../artifacts/qa_vnext_finqa_reason_policy/e1_ef_cp_2rep_20260908/online/sessions/E1_E_C_02/runtime/turns/019_response.raw)。

P 本批没有出现命中同类冻结尺度检查点的原输入提议；这不是把这两条 C 响应换用 P 重新执行
的反事实试验，也不能将“C出现两项、P没有”外推为C更懂单位。
有限检查点不穷尽所有潜在合法中间方案，但完整记录中也未出现双方尺度完成配对的有效依赖。

### 7.5 八条会话逐条定位

| 会话 | 操作 | 后续首个 raw / schema / 实际 Action | 再次目标拒绝 | 主要实际行为与终止 |
| --- | ---: | --- | ---: | --- |
| E1_E_C_01 | 5 | 11 / 11 / 11 | 15 | 11仍直接相除；17/21/32长reason结构拒绝，32才提出合适分子换算；最后停在schema拒绝 |
| E1_E_C_02 | 6 | 12 / 12 / 12 | 14 | 12/25重复坏百分比；17 raw source算术被拒；20合适分母换算超长；32仍错Final |
| E1_E_P_01 | 8 | 10 / 10 / 10 | 13 | 25理由/实际Claim不一致，26 reject；29长理由执行分母×1000，30 accept但不使用；32旧错Final |
| E1_E_P_02 | 8 | 10 / 10 / 10 | 14 | 10/16/30重复坏百分比，27重复比值；31接受新重复量后32选回原错量 |
| E1_F_C_01 | 4 | 30 / null / null | 21 | 后续唯一raw Action为30的超长读取，未执行；32仍旧错Final |
| E1_F_C_02 | 6 | 10 / 10 / 10 | 17 | 没有长reason；10重复百分比、25重复比值；32仍旧错Final |
| E1_F_P_01 | 6 | 10 / 10 / 10 | 19 | 没有长reason或接口拒绝；10/24重复坏百分比，全部20次拒绝都是目标拒绝 |
| E1_F_P_02 | 10 | 10 / 10 / 10 | 8 | 错量×100、长reason错量×1及多次重复运算；32选回原Claim且引用不匹配 |

“再次目标拒绝”不包含各条的首次第9次拒绝，也不包含引用/JSON/结构等其他拒绝。
所有语义准入 Action 都真实执行；除了 E_P_01/26 的一次合法 reject 外，观察均被接受，
没有未获得后续 Update 的观察。本次是53/53首次合法（52 accept、1 reject），引用绑定拒绝零。

完整逐条审阅含具体输入、处理与终止证据：
[八会话 posthoc 审阅](../artifacts/qa_vnext_finqa_reason_policy/e1_ef_cp_2rep_20260908/closeout/posthoc_review_input.json)。
审阅不改变任何正式层次指标、原始响应或完整结果。

### 7.6 重复行为与完整成本

| 指标 | C | P |
| --- | ---: | ---: |
| 目标拒绝后有实际操作的会话 | 3/4 | 4/4 |
| 拒绝后的实际操作数（含重复） | 5 | 16 |
| 首次后的再次目标拒绝 | 67 | 54 |
| 后续 Final 重用已目标拒绝的同一 Claim | 71 | 48 |
| 后续 Final 重用已目标拒绝的符号等价表达式 | 74 | 56 |
| 总 Token | 656,427 | 695,326 |

P 多11次实际操作、少13次再次目标拒绝，但没有完整有效结果。
P 总 Token 比 C 多38,899，约5.93%；这是本批描述性成本差异，不是统计显著性或稳定因果效应。
更多操作、较少拒绝、较长或较短理由均不能代替正确依赖与成功指标。

合法 JSON Action 的 reason 字符总数 C=9,940、P=4,868，最大值分别1,467、567。
该特征**不包含无法解析 JSON 的内部字段**，不是模型全部输出长度，更不是内部推理量；
不可据此忽略三个原始 JSON 失败或反推总成本。Provider 用量仍是实际 Token 权威。

全部成本属于未完成会话，没有成功样本均值隐藏失败：

```text
256 = 53 次实际操作 + 52 次 accept + 1 次 reject + 0 次有效 Final + 150 次未准入
150 = 129 目标拒绝 + 10 Final 引用不匹配 + 9 JSON/schema 拒绝 + 2 非 accepted Claim 算术输入
129 = 8 次首次目标拒绝 + 121 次再次目标拒绝
61 个 raw Action形状 = 55 个schema合法 + 6 个仅reason长度结构拒绝
55 个schema合法Action = 53 次执行 + 2 次输入语义拒绝
1,300,668 prompt Token + 51,085 completion Token = 1,351,753 total Token
```

原始 HTTP 请求体4,725,825字节，响应体258,235字节。
全部256次Provider尝试都有原始模型提交及完整prompt/completion/total用量；
没有未发出的全局资源停止、重试、fallback或额外请求。
各会话仍有未用操作额度，全批96次可用操作用了53次、剩43次；提交预算不允许继续使用。
`reasoning_tokens` 未单独报告，total=null、unknown_attempts=256，不能由Thinking disabled虚构观察到零。

原 R 临时提示实际曝光 C=68、P=55，共123次。差异来自实际目标拒绝和后续转移序列，
不是更换了文本或触发/清除规则。所有返回模型标签为 `deepseek-v4-pro`，未出现条件flag。

### 7.7 核验与结束决定

46项新局部控制通过，未重跑旧十七项、历史失败或整面板控制。
八条原文重放、所属条件schema、实际解析、独立精确算术、原Final目标、Claim生命周期、
分层事件计数、四个单元和C/P汇总、HTTP原文及Token加和均核验通过。
冻结后没有修改在线Python源文件，历史守卫通过。

[完整封存报告](../artifacts/qa_vnext_finqa_reason_policy/e1_ef_cp_2rep_20260908/closeout/report.json)
ID：`finance_qa_vnext_e1_reason_policy_closeout:ea42cd91648d775f352f3ff1ac8aa91e45e4887ea2535ff99b7771c1b9aaf44f`。

本轮在八个会话处结束。获得的是**局部理由长度不再阻止P合法数值操作的机械执行见证**，
不是合适尺度操作到完整恢复的正见证。
本批没有支持P改善完整任务；同时，也不能将其失败继续统一归因于480限制。
真实输入选择、单位/比例解释和旧Claim选择仍有直接失败证据，不能仅靠重复计算解决。

不继续提高理由上限，不继续叠加复核提示，不把C中的好提议换用P补跑成成功。
若要继续，检验对象需另行独立决定；J2、一般知识管理、训练与旧有效轨迹用途本轮均未修改。
