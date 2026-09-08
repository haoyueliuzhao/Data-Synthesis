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
