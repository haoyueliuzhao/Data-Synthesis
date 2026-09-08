# FinQA E1：错误 Final 后的通用反馈恢复诊断

## 1. 审计依据与边界

本轮依照 2026-09-08 用户审计继续，附件 SHA-256：
`e097dff61478af07cd4ebde83767afd1d99ffd404a8c06230fc9445a5b21a9fe`。
父提交：`e10686e42f5ba6ee6019388232b434f60c4f44ae`。

上一轮 v2.1 限定结论接受并收口：136 个有首次后续提交的 Observation 均合法处理，
另一个无后续提交；E/F 各 9/12 完整有效。上述是历史结果，不作为本轮 B 的样本，
也不据此声称普遍消除了引用错误。历史代码、工件、报告不改写。

唯一研究对象：固定 E1 中实际发生 `final.target_not_established` 后，
固定、任务无关的语义复核文字是否伴随真实依赖修正和原预算内完整恢复。
这是小样本开发诊断，不是盲测、稳定成功概率估计、一般金融能力或训练收益实验。

不做十二题新面板、历史十五项控制、全量 FinQA 静态统计、引用 accept-only 校准、
J2 修改、异尺度运算准入门、Claim 自动删除/修复、知识撤销、Student、VTDO、
权重更新或新 tokenizer 导出。只读既有绑定与清单核对一致性，不重新执行历史控制。

## 2. 预注册总体与预算

八个全新、空 Claims、无 pending Observation 的完整会话：

| 信息条件 | B：现有反馈 | R：固定复核反馈 | 每单元分母 |
| --- | --- | --- | --- |
| E：预定位证据 | E1_E_B_01、E1_E_B_02 | E1_E_R_01、E1_E_R_02 | 2 |
| F：完整条目来源 | E1_F_B_01、E1_F_B_02 | E1_F_R_01、E1_F_R_02 | 2 |

预注册提交到线程池的顺序：
`E1_E_B_01 → E1_E_R_01 → E1_F_B_01 → E1_F_R_01 → E1_F_R_02 → E1_F_B_02 → E1_E_R_02 → E1_E_B_02`。
单波、最多八路并发；实际 HTTP 起始顺序受调度影响，不声称严格时间顺序或时间随机化。
未新增 seed；两次重复不是共同随机种子配对。

每会话仍为 12 次实际操作、32 次模型提交、32 次 Provider 尝试上限。
全批至多 256 次请求、27,525,120 预留 Token；预留上界不是实际用量预测。
无自动重试、fallback、续跑、替换、扩样到成功或补采样制造错误。
有效 Final 仅停止自己的原会话，不取消其他已注册会话。失败和未知保留原总体与成本。

保留原 E1 问题、E/F Context、来源 ID 与解释、数值、工具、常量、Final 单位/引用/数值与
符号验证。配置沿用原中性 SYSTEM、`deepseek-v4-pro`、temperature 0.7、top_p 1、
Thinking disabled、JSON object、max_tokens 8192、180 秒总超时、30 秒连接超时，
每次序列化请求上限 98,304 字节。仅全批 cap 和派生配置 ID 不同，逐请求参数不变。
同一模型名称不证明供应商内部快照不可变。

## 3. 唯一呈现差异

执行与只读回放均显式构造 `FinalRecoveryRuntime`。公开协议仍为原
`finqa_source_numeric_h2.v2.1`，独立呈现条件为 `finqa_final_recovery_feedback.v1`。
新类只扩展 `request()`，不覆盖 `transition()`。

B 全程等于原 v2.1。R 首次目标拒绝前也等于原请求（相同 session ID 下可逐字段检查；
正式会话有各自独立 ID）。R 仅在当前 `state.feedback == final.target_not_established`
时于 `rules.target_failure_review` 加入下列固定英文文字，并保留原错误码：

> The selected Claim establishes a numeric derivation, but has not established the target asked by the question. Compare the original question and sources with the metric, periods, unit scales, and actual inputs used. Changing Final wording, unit labels, or citations does not change the Claim's executed derivation. If correction is needed, execute and explicitly accept the new calculation before selecting the answer.

构造文字不读 Oracle、正确值、参考公式、表达式差异或下一动作。
文字不包含 E1 公式、具体换算因子、答案或下一输入 ID。
下一次成功操作/Update 或其他拒绝替换当前 feedback 后提示清除；再次目标拒绝则再次出现。
这不是触发后永久新增记忆区。原传输仍是中性 system 加当前请求、无对话历史。

R 不强制 Action、不禁止重复 Final、不代填 Update、不替模型接受或删除 Claim。
模型仍须实际操作、明确接受并选择答案；Final 直接改旧 Claim 的数值仍由原
`final.unexecuted_value_change` 拒绝。同一坏答案仍可提出，再由原目标验证拒绝。
新文字正常改变 request ID 和下游内容寻址 ID，不是 Host 修复模型引用。

## 4. 冻结测量口径

### 4.1 完整成功与触发分开

每 E/F × B/R 单元完整有效数/2，B/R 各自汇总数/4，同时报告。
直接成功留在完整分母；未触发目标拒绝的恢复是 `NOT_APPLICABLE`，不是恢复成功。
触发后通过原 Final 是 `COMPLETE_RECOVERY`；否则 `NOT_COMPLETED`，并保留预算耗尽或传输未知
等具体状态。未知不能解释为已证明不会恢复。触发子集是描述性、行为筛选子集，
不是另行独立随机分配的恢复队列。缺少触发不补样本。

保存首次错误 Final 的原始提交、Claim ID、展开表达式、精确数值与位置，
保存全部目标拒绝位置和首次之后重复次数。全部提交编号从 1 开始。

### 4.2 实际调整与重复错误

分别记录首次后续 Action 提议和首次准入执行；被拒 Action 不算操作。
保存全部后续提议、准入状态、operation、有序输入 ID、原理由、表达式与 lineage。
首次“新相关实际操作”：首次拒绝后准入，表达式与此前全部执行表达式不符号等价，
且真实 lineage 与目标绑定来源相交；允许 read。该代理位置不是正确性认证，
完整操作列表保留，避免丢弃未被代理捕捉的路径。
仅改理由、重复读取、乘 1、换分组不因新 ID 就算新语义依赖。
同时记录展开树是否重复与符号是否等价。后续所有 Final 记录是否重用此前目标拒绝的
同一 Claim，或换 ID 却沿用同一/符号等价坏表达式。

### 4.3 尺度、接受与真实消费

批后来源符号检查点包括：分母换到分子尺度、分子换到分母尺度、归一化比例、完整百分比。
检查点从冻结 E1 目标导出，仅测量，不进入公开提示或准入。可识别分母换算、分子换算、
已有比例或百分比补做等价换算等顺序，不要求参考操作链。
它不是所有合法中间量的完备分类；初次直接相除不自动是非法步骤，尺度中间量也不是最终答案。

每个观察记录 unresolved/accept/reject、处理编号与产生 Claim ID。
根据实际 Action 输入建立 Claim 依赖图，从有效 Final 答案递归追踪真实祖先。
“消费”须在实际图上，不能仅凭符号等价断言使用了某条新 Claim。
`fresh_dependency_recovery_witness` 进一步要求：首次拒绝后新执行、非旧等价的尺度检查点，
明确接受、位于有效 Final 依赖图中，并完整成功。
只改选此前已有正确 Claim 也算完整恢复，但不算新增依赖恢复。
只说“单位一致”、新量未接受、拒绝新量或接受后仍选旧错量，不算完整恢复。

### 4.4 曝光和成本

提示曝光仅计实际 HTTP ledger 请求，不计终止后未发送的下一请求。
第 32 次首次拒绝可以触发却无后续曝光/响应，保留这种情况。
报告调用、模型提交、操作、合法 accept/reject、未准入、重复目标拒绝，
以及 Provider 实报 prompt/completion/total Token；成功与未成功均统计。
缺失用量 total=null，另列观察小计、未知次数，不以零代未知，不将预留当实际费用。

## 5. 新增检查、冻结与收口

只执行 `tests/test_qa_vnext_finqa_e1_final_recovery.py` 新控制，不执行历史整面板控制。
覆盖 B 原样、触发前 B/R 相同、R 触发/清除、不读 Oracle、原转移继承、重复 Final 可提出、
未执行改值被拒；三种恢复路径分别通过 B/R 模拟 HTTP 与原文回放；理由和真实依赖区别；
未接受/拒绝/未消费正确量；提议与执行区别；第 32 次拒绝无虚构曝光；直接成功不适用；
传输未知；报告 HTTP 字节计数；八个标签与仅总 cap 不同。
这些都是零 Provider 的 adapter mock，不是模型样本，脚本可完成不代表模型可完成。

先提交新代码、测试与设计，再 prepare 绑定全 Python 源码集合与字节到该 Git 提交，
复制本文为 `design_at_freeze.md`，写注册、初态、配置、测试结果、历史守卫并封存。
排他持久目录拒绝覆盖，原 HTTP 请求/响应和模型原文逐调用保留。
回放核验条件请求、原文、原转移、独立精确算术、生命周期和目标验证。
在线期间不再改源码，批后 reporter 也纳入冻结。

结束后逐条阅读实际轨迹，单列 posthoc 人工审阅注释；closeout 再验证八条原文回放/清单、
每单元分母、操作/Update/Final/拒绝分解和 Token 加和。
若完整性异常不能通过核验，不隐藏或补跑，单独说明。

仓库根入口：

```bash
trusted_data_synthesis/.venv/bin/python -m pytest -q trusted_data_synthesis/tests/test_qa_vnext_finqa_e1_final_recovery.py
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_finqa_final_recovery.stage prepare
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_finqa_final_recovery.stage run
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_finqa_final_recovery.closeout --reviews <posthoc-review.json>
```

后三步不是可对同一输出目录反复执行的重采样命令。
工件根：`artifacts/qa_vnext_finqa_final_recovery/e1_ef_br_2rep_20260908/`；
`preparation/` 为冻结记录，`online/sessions/<label>/` 为逐会话原始证据，
`online/summary.json` 为固定总体汇总，`closeout/` 为零 Provider 再核验。

若 R 出现新尺度依赖且用于有效 Final，仅称为有限反馈辅助恢复见证；
若都直接成功，恢复缺少触发；若都不恢复，不循环叠加更强提示。
同一题每单元两次不支撑稳定概率、一般金融能力、纯证据效应或训练收益结论。
E/F 是信息设计包，J2 留作独立后续对象。

## 6. 批后结果

原八会话全部结束并只读核验后追加；冻结副本不包含未来结果。

### 6.1 完整结果：未获得恢复见证

冻结提交为 `09315838df7240561365235fc4ffc6ae7a384516`，在 Provider 调用前已推送。
八个预注册会话均从新初态完整运行一次，无未启动、替换、未知或重试。
每条都在第 32 次模型提交耗尽提交预算；实际操作为 4–9 次，未耗尽 12 次操作额度。
四个单元都是 0/2，B/R 汇总都是 0/4。八条都实际触发过目标拒绝，因此恢复分母也是各组 4，
而非“没有触发所以不能观察”；本次 recovery 不适用数为 0。

| 单元 | 完整有效 | 实际触发 | 完整恢复 | 操作 | accept / reject / 无后续 | 请求/提交 | 总 Token |
| --- | --- | --- | --- | ---: | --- | ---: | ---: |
| E_B | 0/2 | 2/2 | 0/2 | 13 | 12 / 1 / 0 | 64 | 251,521 |
| E_R | 0/2 | 2/2 | 0/2 | 11 | 10 / 1 / 0 | 64 | 245,926 |
| F_B | 0/2 | 2/2 | 0/2 | 8 | 8 / 0 / 0 | 64 | 387,806 |
| F_R | 0/2 | 2/2 | 0/2 | 14 | 12 / 1 / 1 | 64 | 410,212 |
| B 合计 | 0/4 | 4/4 | 0/4 | 21 | 20 / 1 / 0 | 128 | 639,327 |
| R 合计 | 0/4 | 4/4 | 0/4 | 25 | 22 / 2 / 1 | 128 | 656,138 |

原文及独立算术/转移回放都没有出现尺度对齐的实际观察；接受且被有效 Final 消费的新尺度量也是 0。
R 的实际 HTTP 中共 61 次正确出现固定说明，B 为 0。全部 256 个返回模型标签为
`deepseek-v4-pro`，没有模型条件 flag、无 Provider 返回后未进入 Runtime 的内容、无 Host 代填/改写。
因此本次结果不能解释为“新提示没有进入在线链路”。

本次得到的是**该固定文本、当前呈现与原约束下，八个新会话未完成 E1 恢复**。
不据此声称任何通用提示都无效，也不声称已经估计模型的稳定失败概率。

### 6.2 重复减少与实际调整分开

| 对象 | B：4 会话 | R：4 会话 |
| --- | ---: | ---: |
| 首次目标拒绝后的再次目标拒绝 | 70 | 60 |
| 拒绝后有实际新一轮操作的会话（含重复计算） | 1 | 4 |
| 拒绝后的实际操作次数（含重复） | 3 | 9 |
| 后续 Final 重用已目标拒绝的同一 Claim | 74 | 61 |
| 后续 Final 重用已目标拒绝的符号等价表达式 | 75 | 64 |
| 真正建立尺度对齐的实际操作 | 0 | 0 |
| 完整恢复 | 0 | 0 |

重用统计包含后续因引用/数值问题先被拒的 Final，故不必等于“重复目标拒绝”次数。
R 中更少的目标拒绝与更多操作只描述交互轨迹变化，没有转化为有效答案。
这不是推理收益，也不能从小样本次数差异精确归因提示的因果效果。

### 6.3 八条轨迹逐条定位

下表编号均是实际模型提交；“新相关”沿用冻结符号新颖性代理，不自动意味着正确。

| 会话 | 首次目标拒绝 | 后续首个实际操作 / 首个新相关 | 再次目标拒绝 | 原文与终止要点 |
| --- | ---: | --- | ---: | --- |
| E1_E_B_01 | 10 | 无 / 无 | 20 | 初始坏百分比反复 Final；24 有合适分母换算原始提议但 reason 超长，未执行；32 仍旧坏 Claim |
| E1_E_B_02 | 14 | 15 / 17 | 10 | 首个 Final 甚至是原直接比值；17 补乘 100 仍缺尺度；20 合适补乘 1000 提议超长失败；32 仍坏百分比 |
| E1_E_R_01 | 9 | 21 / 无 | 16 | 15 合适换算原始提议超长；18 又把 raw source 用作算术输入被拒；21 只重算旧百分比；32 仍错误 |
| E1_E_R_02 | 9 | 11 / 无 | 14 | 11 理由说换算但仍直接相除；18 分子换算提议超长；20 raw source 算术被拒；24 合法 reject 重复量；32 旧坏 Claim |
| E1_F_B_01 | 9 | 无 / 无 | 19 | 没有后续 Action；重复旧 Claim，夹杂引用改动；32 目标拒绝 |
| E1_F_B_02 | 10 | 无 / 无 | 21 | 没有后续 Action；15 把数值舍入成 0.011 超容差被拒，并非已经报出正确目标；32 目标拒绝 |
| E1_F_R_01 | 9 | 12 / 26 | 17 | 12 重算旧百分比；26 分母 ×1000，27 明确 reject；29 分母 /1000 提议超长；32 仍选坏百分比 |
| E1_F_R_02 | 9 | 12 / 12 | 13 | 12 在坏百分比上再乘 100 得 1.096389，13 接受、14 Final 仍拒；32 重复该操作后留下无人处理的观察 |

除 E_B_02 首次 Final 为 `15.3 / 139549 ≈ 0.000109638908` percent 外，
其他七条首次 Final 均为 `(15.3 / 139549) ×100 ≈ 0.01096389082` percent。
按原绑定尺度，原目标为 `15.3 / (139549/1000) ×100 ≈ 10.96389082` percent；
它只用于既有 Final 检验及批后说明，没有进入 R 的提示。

E_B_02 的第 7 次实际是 `1000/139549`，不是理由中说的分母除以 1000；
第 10 次是 `15.3×100=1530`，未形成正确答案依赖。
F_R_01 的分母换成美元可以是更长合法方案的中间步骤，因此不把该乘法自动判为错误工具操作；
但本会话未同步换算分子，且自己拒绝了新量，没有完成对齐。
F_R_02 的 `1.096389…` 仍比正确目标小十倍；它确实被接受并用于**失败** Final，
不能把“接受并选择过某新量”直接等同于有效消费。

详尽人工审阅为明确标记的批后注释：
[八条审阅输入](../artifacts/qa_vnext_finqa_final_recovery/e1_ef_br_2rep_20260908/closeout/posthoc_review_input.json)；
每条原文及请求位于对应 `online/sessions/<label>/runtime/turns/`，完整机器轨迹位于各自 `audit.json`。

### 6.4 新发现：部分合适动作核心在执行前被原长度合同拒绝

不能把八条失败统称为“模型没有单位知识”。
在五条会话的公开原始 JSON 中，操作和当时已接受 Claim/常量输入已经描述了合适的尺度转换，
但 `reason` 超过原 480 字符限制，schema 层就拒绝了整个响应：

| 会话 / 提交 | 原始操作核心（仅释义） | reason 字符 | 实际结果 |
| --- | --- | ---: | --- |
| E1_E_B_01 / 24 | 已接受分母 / 1000 | 1,209 | schema 拒绝，无 Observation |
| E1_E_B_02 / 20 | 已接受坏百分比 × 1000 | 3,571 | schema 拒绝，无 Observation |
| E1_E_R_01 / 15 | 已接受分母 / 1000 | 2,245 | schema 拒绝，无 Observation |
| E1_E_R_02 / 18 | 已接受分子 × 1000 | 965 | schema 拒绝，无 Observation |
| E1_F_R_01 / 29 | 已接受分母 / 1000 | 513 | schema 拒绝，无 Observation |

这些是 B 两条、R 三条中的**未执行提议**，不是恢复样本，不是已认证 Claim，
更不是“如果忽略限制必然成功”的反事实结论。
检查仅在原状态下解读原 operation 和有序输入，并符号比较它描述的表达式；
未删除/截短理由、未制造修复后的模型响应、未调用 Runtime 准入、未产生新轨迹。

其他失败层也同时存在：E_R_01/18 和 E_R_02/20 直接把 `source:t6c1n0` 传给非 read，
违背原 accepted-Claim 输入合同；F_R_02/18 把 Action.operation 写成 final、inputs 为空，
且理由超长；F_R_02/25 的原始 JSON 含未转义引号而不合法。
本批 13 次 schema 拒绝中，12 次可解析 JSON 均有 reason 超长（其中一次还为空输入），
另一次是 JSON 语法错误。

因此更准确的定位是：**公开语义判断与实际动作依赖不一致、恢复提议未通过原接口合同、
旧 Claim 继续被选择，三者都有直接证据**。本轮不能单独分离各自因果贡献。
原 480 字符限制和粗粒度 schema 错误反馈未修改；也未为这些提议补跑或代执行。

### 6.5 冻结提议测量的局限与只读补充

冻结 `first_post_trigger_action_proposal` 与 `operations` 使用
`event.model_submission`；原 schema 解析失败时该字段为 null，
所以它只覆盖**schema 可解析的 Action 提议**，并不覆盖所有 Action 形状的原始响应。
准备测试验证了可解析但未准入的 Action，未覆盖此处“长 reason 在解析层被拒”的位置统计。
这是本轮发现的**提议位置测量范围缺口**，不隐藏，也不覆盖已经冻结的指标。

| 会话 | 冻结首个可解析 Action | 批后首个合法 JSON、kind=action 原始响应 | 首个实际执行 |
| --- | --- | --- | --- |
| E1_E_B_01 | null | 24 | null |
| E1_E_R_01 | 18 | 15 | 21 |

其余六条在此首位置上相同。语法不合法的 JSON 不推测为已解析 Action。
这个差别不改变真实执行、接受、有效 Final、成功/恢复分母或任何成本。

新增独立批后脚本
[finqa_e1_recovery_posthoc.py](../scripts/finqa_e1_recovery_posthoc.py)
仅检查原文，文件 SHA 绑定在
[原始提议检查结果](../artifacts/qa_vnext_finqa_final_recovery/e1_ef_br_2rep_20260908/posthoc/raw_proposal_inspection.json)。
它位于冻结源码集合外，检查在线源字节及封存清单未变，无 Provider 调用。
未重写原 `metrics.py`、`audit.json` 或 `online/summary.json`。
后续若再使用“首次提议”这个指标，应先明确语法/结构解析边界；本次不因此追加模型样本。

### 6.6 完整成本、引用事件与核验闭合

全部 256 次尝试都有原始模型提交和 prompt/completion/total 用量；没有传输未知、缺失提交或重试。
成功会话为 0，全部实际用量都属于未完成会话：

```text
256 = 46 次操作 + 42 次 accept + 3 次 reject + 0 次有效 Final + 165 次未准入
165 = 138 目标拒绝 + 13 schema 拒绝 + 10 引用不匹配
      + 2 非 accepted Claim 算术输入 + 1 未执行数值改动 + 1 read 来源错误
138 = 8 次首次目标拒绝 + 130 次后续目标拒绝
1,246,674 prompt Token + 48,791 completion Token = 1,295,465 total Token
```

原始 HTTP 请求体共 4,553,460 字节，响应体共 252,690 字节。
未尝试额度为 0；仍剩 50 次实际操作额度，但不能突破提交预算继续。
`reasoning_tokens` 未由 Provider 单独报告，256 次均为 unknown、total=null；
不能因为 Thinking disabled 就虚构观察到零 reasoning Token。已观察小计 0 与总量未知分开保留。

46 个实际 Observation 中 45 个有首次后续模型提交，42 accept、3 reject，首次非法 0，
Observation 引用拒绝 0。唯一无后续的是 F_R_02 第 32 次产生的 pending Observation。
因此是 45/45 首次合法，不是 46/46；它仍在总事件、失败与成本中。
这只是保留引用事件账目，没有启动新的引用校准或泛化验证。

17 项新增离线控制通过；八条完整原始回放、实际 HTTP 条件呈现、独立精确算术、
生命周期、单元汇总、Token 加和及历史守卫通过。本批没有运行其他历史面板/控制。
[封存完整报告](../artifacts/qa_vnext_finqa_final_recovery/e1_ef_br_2rep_20260908/closeout/report.json)
ID 为 `finance_qa_vnext_e1_recovery_closeout:c5266e6303e21d29f224292c237e73d9897b815225b74b70e7420bc291a09e58`。

### 6.7 本轮结束决定

八会话固定实验在此结束，不扩样、不接续、不把历史四条 E1 失败并入新 B，
也不在看过结果后继续加强提示。没有产生可称为反馈辅助完整恢复的新见证。
本结果支持进一步区分语义—动作落实、原接口限制与旧状态选择的研究问题，
但没有验证某个后续修订一定有效；后续方案应独立审议、独立冻结，而非本轮补救采样。
J2、Student、VTDO 与旧十八条有效轨迹的后续用途均未变动。
