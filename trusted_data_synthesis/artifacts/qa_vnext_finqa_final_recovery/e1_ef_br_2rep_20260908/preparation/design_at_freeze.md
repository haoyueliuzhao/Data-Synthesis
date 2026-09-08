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
