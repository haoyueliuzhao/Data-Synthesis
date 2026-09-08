# FinQA 十二原题 E/F：v2.1 完整会话引用与金融操作诊断

## 状态与问题

本文件首次提交时为调用前登记方案，尚无本批在线结果。运行后的结果将追加在末尾；封存的 preparation/design_at_freeze.md 保留调用前原文。

唯一主问题：在已经明确公开 Observation 引用合同的同一有限工具环境中，模型能否完成原十二题；剩余问题实际出现在哪些证据选择、期间与输入配对、单位换算、方法或终局行为上？

依据用户审计附件，SHA-256：
f96b9cb41be695c8892d10580aaa023bd5d08d79d5300844d5dc84086d909d7b。
基线提交为 04026165aedab7b68590393817026cafaa31069c。
旧批原报告 [finance_qa_vnext_finqa_difficulty_ef.md](finance_qa_vnext_finqa_difficulty_ef.md)
和全部工件保持不变。原 v2 的 E 2/12、F 7/12、636 次请求及 2,769,305 Token 均保留；
它们是有效的冻结条件下完成记录，但不能归因为纯金融能力或证据难度效应。
已有 v2.1 修订只完成离线验证，本批才测量其在线表现。

## 固定内容与执行边界

| 项目 | 本批冻结条件 |
| --- | --- |
| 原题 | C1、C2、C3、E1、E2、E3、M1、M2、M3、J1、J2、J3 |
| 规模 | 每题 E/F 各一个全新会话，合计 24；每条件分母 12 |
| 唯一主要接口变化 | 使用既有 ReferenceExplicitRuntime，版本 finqa_source_numeric_h2.v2.1 |
| 问题与来源 | 原问题、绑定值、来源身份、E/F 完整公开 context 逐项等于旧 preparation |
| 工具与 Final | 原有限标量工具、Numeric Claim 语义、符号依据、数值、单位、引用和接受生命周期不变 |
| 模型 | deepseek-v4-pro；允许响应名 deepseek-v4-pro、deepseek-v4-pro-0813 |
| 采样 | temperature 0.7，top_p 1.0，Thinking disabled，max_tokens 8192，json_object |
| 消息 | 沿用原中性 SYSTEM，加当前公开请求；每次无额外历史消息 |
| 每会话预算 | 实际操作至多 12、提交至多 32、真实请求至多 32 |
| 全局预算 | 最多 768 请求；Token 预留上界 82,575,360，不是预计实际消耗 |
| HTTP 限制 | 原完整序列化请求 98,304 bytes、180 秒总超时、30 秒连接超时等不变 |
| 并发 | 固定三波，每波 8 个独立会话；只并行 HTTP 与本地检查，不改变会话内顺序 |
| 禁止 | 自动重试、模型替换、补样、续跑补成功、旧成功继承、旧响应改写、accept-only 在线校准 |
| 不做 | 重跑全量 census 或旧 H1/H2、重跑旧 67 项控制、新题型、新工具、提示优化包、Student、VTDO、训练权重或新 tokenizer 监督导出 |

E 是预定位证据，F 是 FinQA 条目保存的表格和前后文，**不是完整年报或原始 PDF**。
十二题是已检查的开发面板，覆盖 12 页面、11 报告、9 主体，含既往来源重叠。
E/F 是信息条件设计包，每题每条件仅一次，不能估计稳定能力排名或广泛泛化。

新 stage.py 显式构造 ReferenceExplicitRuntime，新 audit.py 也显式用同类重放。
不修改旧 stage/audit，不以更改版本标签或 monkeypatch 代替接线。
执行前核验每个 E/F context 与原工件完全相等，action/final Schema 不变，模型完整配置记录相等。
已有 v2.1 的 24 个静态可达见证只通过封存证据复用，不再执行整套可达性实验。
新增离线控制只针对新入口、实际 HTTP 字节中的 pending const、原响应重放和测量边界；
控制信封来源为 adapter_mock，不计入 Provider 或模型分母。

所有 Python 源码先提交并由 source_snapshot 冻结，再生成新条件和新会话身份。
每波启动及全部结束检查快照。旧工件、旧实验源码和测试由 history_guard 与基线比较。
完整原始 HTTP 请求体、HTTP 响应体、Provider usage、未修改 content、每轮公开请求和 transition、
最终状态、只读审计和分层 manifest 都分别保存。
完整性或条件漂移阻止下一波，负结果不触发补样；未启动/未知会话仍占原分母。

## 测量定义（调用前固定）

### 端到端

仅通过原完整 Final 与来源/算术/生命周期重放者计为 complete_valid。
计算正确但仍 pending、正确 Claim 已接受但没有 Final、预算耗尽或未知都不计为完整有效。
每条件完整有效数除以 12；旧成功不进入新分子，未知与失败不从分母移除。

### Observation 事件

每个**真实 action 执行产生**的 Observation 建立独立事件记录。
检查它仍 pending 时的第一次后续**实际模型提交**；只有精确 ID、准入合法且 disposition 为
accept 或 reject 的 Update 才算首次合法。合法 reject 同等计入，不能被改为必须 accept。
非法 JSON 仍是一次实际提交；transport 未返回 content 则不是模型提交，不虚构决策。

报告总 Observation 数、有首次后续提交数、首次合法 accept、首次合法 reject、首次非法、
没有后续提交数、首次合法率（合法数/有首次提交数）。
当预算或传输结束导致没有后续提交时，first_decision=null，并保留总事件数与会话分母；
若某会话零 Observation，事件率为 null，会话分母仍为 1。
这些事件来自同一批会话，不包装为相互独立的任务样本。

同一 pending 的全部 lifecycle.observation_binding 拒绝保存具体提交序号，
并按真实连续提交索引划分连续段；其他拒绝中断连续段，但不减少该 pending 的总引用拒绝。
记录最后是否 accept/reject/unresolved、何时处理、是否在该 pending 上预算耗尽。
所有 actual HTTP 请求核验 observation.description、公开 rules 以及 pending 时的精确 const。
若仍在完整公开合同下填入说明文字，应记为模型合同执行问题，而非重复声称合同未公开。

### 金融与方法轨迹

四个焦点：E1 尺度、M3 期间集合、J1 税后定义、J2 期间输入配对。
“到达”只是进入可检查位置，**不是错误或正确标签**。冻结机会定义见 metrics.financial_trace：

- E1：非 read 操作包含两个相关事实，或对一个相关事实与常数进行乘除。
- M3：sum/average/divide 的展开来源包含至少两个相关收入事实。
- J1：非 read 操作展开来源包含至少两个相关成本/税收利益事实。
- J2：multiply 展开来源包含至少两个相关股数/价格事实。

未发生上述操作则 NOT_REACHED，不能记作能力错误。保存所有实际 action 的输入、来源表达式、
数值、subgoal/reason、具体序号，所有实际 Final 尝试及其依据，以及最终 pending/claims/termination。
人工逐轨迹后验复核记录：具体错误证据、是否恢复、最终停点；明确这是描述性复核，不是盲标错误率。

中间式不得直接当作最终答案评分：例如 E1 先除再乘 1000 是合法的候选路径，
E3 的 0.997 可是百万到十亿的中间换算；M3 单年比率可成为后续加权组合的一部分；
J2 跨期乘积也可能用于合法代数分解。判断具体错误需依据真实目标声称、实际关系矛盾
或错误 Final，不能仅凭中间式不同于目标。off_reference_source_ids 只作查阅线索，
替代来源、探索性读取或未使用的正确数值不自动构成错误；全在参考集合也不自动证明期间/口径正确。
上述复核不反馈给在线模型，不回填财务角色准入，不修改 Final 的 Oracle。

## 实施与复现

新包：trusted_synthesis.experiments.finance_qa_vnext_finqa_reference_diagnostic。
本批唯一输出目录：
trusted_data_synthesis/artifacts/qa_vnext_finqa_reference_diagnostic/original_12_ef_v21_20260908。

调用前先提交代码和本文，再执行：

~~~bash
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_finqa_reference_diagnostic.stage prepare
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_finqa_reference_diagnostic.stage run
~~~

现有目录不可覆盖，run 不恢复旧 launch；上述在线命令会使用真实 API，不应为“复现结果”再次执行。
只读复核入口 closeout 重新验证现有原始响应与封存链，不调用 Provider。
其 --reviews 输入是逐会话后验解释，需覆盖全部 24 标签；封存前将它连同校验值写入 closeout。

## 解释边界与结束标准

v2.1 与原 v2 只能描述前后变化；没有同期旧版本对照，不能声称识别精确修复因果效应。
无需为获得该额外主张再运行一批旧接口。E/F 逐题差异也不能解释为纯检索效应。
既有有限符号 Oracle 认证的是答案来源依据，不是完整公开行为商，不生成 VTDO 状态概率。

结束标准是登记、固定有界执行、保留分母/负例/未知、成本闭合、源码与来源身份及对应版本重放可追查；
不要求 24/24，也不要求引用错误为零。结果出现后只提出有直接证据的下一焦点，
不在本批中同时改题、工具、反馈、验证或新增训练。

## 本批在线结果

待固定 24 会话实际完成后追加；调用前没有预填成功数或预期改进幅度。

