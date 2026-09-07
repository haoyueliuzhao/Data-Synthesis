# H0/H1/H2：接口简化与有限方法开放的责任对照

## 1. 范围与审计来源

本轮响应“参照审计继续实验”，实施《本轮审计与后续实验修订方案》的新优先级。
审计原文 SHA-256：`ecbd7f870150564b2ea6afbb12d73c7c798ad74b073d6567c8bbfd7f8e0a98e6`。
前继结果提交为 `d91f0e55d4a67dd2c8b183939d979ec3ed6c4226`。

审计接受的历史支持转换商测量保持原状态；附件审阅的是旧测量材料，不能作为后续
Final 发布修订的运行证据。仓库已有的 Final 六会话结果也不重跑，不进入本轮分母。
本轮只检验有限工具环境中 Harness 与模型的责任分配，不恢复旧主线，不训练 Student，
不更新 VTDO 权重，不检验一般知识撤销、替换或后代失效传播。

本文前半部分在调用前冻结。冻结副本、源码提交、模型参数、六个初始实际 HTTP 请求、
十二条注册及测量规则保存于新阶段 `preparation/`。结果只在固定运行完成后追加。

## 2. 两个原任务与三个独立生成条件

| 对象 | 固定内容 |
| --- | --- |
| S | 原 Union Pacific FY2015 Share 任务；FinQA `UNP/2015/page_56.pdf-1`；货运收入占营业收入百分比；原披露总额及完整非重叠部件关系 |
| B | 原 CDW FY2015→FY2016 收入与营业利润增长率绝对百分点差；FinQA `CDW/2017/page_38.pdf-1`；四条原始金额证据 |
| H0 | 原公开计划、原绑定合法候选、原完整 Action/Update 提交与原准入；共同补齐 Final 规则 |
| H1 | 同 H0 的公开计划和可执行候选；简短引用与显式整观察接受；保留模型自己的动作选择 |
| H2 | 同样采用简化交互框架；给问题、原证据、定义、有限工具规则、已接受结果；模型提出子目标、短理由、操作及有序输入 |

H0/H1 的动作集合来自原 `ShareTaskAdapter` / `ProgramTaskAdapter`，没有借机扩大或缩小。
H2 不调用原候选生成函数来放行动作，不按参考节点名验证，也不读取参考图来生成下一步。
H2 请求采用正面字段清单：不包含 `program_skeleton`、节点角色映射、拓扑元数据、
完整后继义务、绑定正确候选或原目录解析对象。Reference Oracle 仅在 Final 后验核验答案。

H0/H1/H2 分别是 `Gamma_H0`、`Gamma_H1`、`Gamma_H2`，不能混成一个采样分布。
H1−H0、H2−H1 都是设计包的有限对照，不识别单字段或单句提示的因果贡献。

## 3. 新语言的责任界限

新接口版本：`harness_responsibility_compact.v1`。旧响应不按新语言重新解释。

H1 Action 必须明确提交 `kind/state_id/action`，其中 `action` 是实际展示的单一候选别名。
Host 根据这项明确选择绑定原候选的完整操作、输入、参数、依据和预期产物。
模型没有重新独立生成这些展开字段；完整候选集合也属于 Host 的展示记录。

H2 Action 必须提交 `kind/state_id/subgoal/reason/operation/inputs/parameters`。
短理由仅与真实选择一起记录，不要求列举假想方案、不强制不确定性或自我纠错，
也不解释成模型的私有思考过程。

H1/H2 Update 必须明确提交 `kind/state_id/observation/disposition`。
`accept` 的公开语义就是接受所指观察的**整个原始命题**，不是 Host 猜测或替模型接受。
缺少对象、错别名、未来 Claim、Observation 冒充 Claim、跨任务长 ID 均不能模糊修复。
E/C/O/A 是会话局部的一一对应别名；`Tn` 精确绑定当前提交状态。别名表随每轮留存。

H1 中原协议要求的候选清单、观察命题、确定性后继字段被明确标为 SYSTEM 派生。
原 `next_subgoal` 字段展开为排序后允许集合的首项，仅充当内部调度占位符，不是模型判断，
不执行下一步；后续实际 Action 仍必须由模型另行选择。H2 没有这份参考义务清单。

每轮保留实际模型 `response.txt`、解析对象、独立 `language_binding.json`、准入 Receipt、
实际执行输入、观察、明确接受的 Claim 和后继状态。原始响应从不被展开 JSON 覆盖。
数值执行前读回原响应、语言绑定和 Receipt；未经准入不执行，未经接受不消费。

## 4. H2 有限合法组合及限制

S 使用原三个工具：`relation_sum`、`share_ratio`、`scale_percent`，复用原来源语义准入。
求和必须引用明确的完整、互不重叠部件关系；支持部件顺序交换。
分母必须是合法披露总额或已接受的重建总额。禁止通过数值碰巧相等来编造部件关系。
这是任务族受限的 Share 语义工具，不声称支持任意分子、任意比例或任意代数变换。

B 使用原四类算子：`lookup`、`growth`、`signed_percentage_point_gap`、
`absolute_percentage_point_gap`。实际执行与独立公式验证继续使用已注册实现。
新准入维护实际来源传播的语义类型：金额、百分比、百分点，以及指标、定义、单位、
币种、主体、期间、范围和来源。增长率采用 `(later-earlier)/abs(earlier)*100`；
有符号差采用第二输入减第一输入；绝对值保留百分点单位。

H2 可直接用原始金额证据算增长率，也可先 `lookup` 再消费结果，允许两类输入混合。
两个增长率的减法顺序可以交换，再取绝对值；允许模型重新执行、建立未必有用的合法结果，
但这些不会自动计为更高训练价值。原参考 B 需要八次 Action；合法直接组合可只需四次，
这是开放方法空间的设计差异，不是偷偷把旧八节点轨迹缩短后仍称为同一完整行为。

零调用控制必须证明直接输入、混合 lookup 和反向差值均能形成通过原数值答案标准的 Final。
同样必须证明错误期间、跨指标增长、错误单位、未来依赖与缺失实际引用被拒绝。
模型在线未使用这些替代组合时，局部控制也不能冒充模型见证。

## 5. 所有条件共同的 Final

外层严格为 `kind/state_id/answer_claim_id/result/citations`；result 严格只含 `value/unit`。
选择当前已接受的可答 Claim，不能存在待处理观察；引用须与该 Claim 的实际 Evidence
lineage 唯一集合完全一致，不能替换成所有可见证据或未执行支持。

S 保留 Decimal precision 50、ROUND_HALF_EVEN、量化 `0.000001`，值是六位小数字符串，
单位严格 `percent`。B 保留 Decimal precision 28、ROUND_HALF_EVEN 和原答案核验语义，
公开要求保留被选结果原精度，不额外套用 Share 六位量化，单位严格 `percentage_points`。
Final 数值、单位和引用由模型自己提交；Host 不填正确答案，也不修正错误结果。
三条件共同发布完整规则，并提供字段、值投影、单位、被选 Claim 和实际引用的针对性诊断。
诊断只比较当前公开 Claim，不执行新的财务操作或泄露隐藏 Oracle 答案。

## 6. 固定预算、顺序和停止规则

两个任务 × 三条件 × 两个独立新会话，共十二会话。每条件下两个任务各占 1/2。
同一中性系统提示，不叠加历史 N/E 重建偏好。

第一波固定启动顺序：S_H0_01、B_H0_01、S_H1_01、B_H1_01、S_H2_01、B_H2_01。
第二波相同顺序、后缀 02。每波最多六会话并行，波间屏障；并行 HTTP 实际到达次序不固定。
顺序在调用前注册，不依据成功、路线、签名或错误数量调整。

沿用 `deepseek-v4-pro`、thinking disabled、temperature 0.7、top_p 1、max_tokens 8192、
JSON object。模型端可接受名称仍为原传输的 `deepseek-v4-pro` / `deepseek-v4-pro-0813`；
不声称供应商提供不可变模型快照。单 HTTP 硬截止 180 秒、连接 30 秒。

单会话最多 12 次实际 Action、32 次模型提交和 32 次 Provider attempt；总 attempt ≤384。
实际 HTTP 请求体上限 98,304 字节，单次保留 Token 上界 107,520，总保留上界 41,287,680。
成功立即结束；没有网络自动重试、模型回退、失败替换、在线续跑或补采样。
普通模型失败不改变后续注册；若出现工件完整性／内部故障，已启动波完成记录，
尚未启动注册记为未知，不删行，也不凭修复重新消费同一轮授权。

实际 Provider usage、输入／输出字节及调用量逐会话单独记录，缺失 usage 保持未知。
相同提交上限不等于相同实际计算成本；H0/H1/H2 的请求长度本来就是干预的一部分。
不加载 Student，无训练 GPU 消费；网络会话并行与 CPU 验证足以覆盖本轮工作。

## 7. 资格、只读审计和有限行为描述

`q_(task,condition) = 完整有效会话数 / 2`；已知失败与证据缺失未知分列，原分母不变。
独立只读审计核对实际请求和原 Provider 字节、精确展开、准入、生产—观察—接受—消费顺序、
实际执行输入及独立数值验证、最终结果和真实支持。公开语言准入函数与运行器共享，
但执行结果由独立公式 verifier 核验；审计不调用生产 executor、Runtime.run/step 或 API。

接口错误码集合调用前冻结。候选集合、内容复述、观察复述、引用和状态错误归入接口负担；
Final 单列；语义／阶段错误单列；不能解释的码保持 `unclassified`，不临场改规则。
H2 无效引用既可能是机械错误也可能是错误依赖判断，报告代码及实际对象，不作单因果归因。

决策来源记录实际操作及输入是否在请求中作为绑定候选完整出现。
H0/H1 的候选选择不能称为自行构造方法；H2 只有在未获完整候选、执行前提出、
实际执行并被最终答案消费时，才构成有限环境的方法构造见证。

本轮**不继承旧完整行为商**。仅冻结一种描述性有效方法签名：从 Final Claim 的真实支持树
递归记录算子、参数、有序输入和 Evidence 身份；折叠透明 lookup；仅将关系求和的两个
部件输入对称化；有符号差输入方向保留。措辞、调度和未使用工作不进入这个方法签名，
但原事件仍完整留存。这不是把它们从“完整行为”中抹掉，也不是训练价值估计。
只在同任务同条件内列签名，不把跨条件类别混合成新的 π 更新。

报告同时给出被接受结果是否实际被消费、Final 支持祖先和已接受但未使用的结果。
没有有效 Final 的轨迹不进入有效方法签名集合。

## 8. 实现与复核入口

实现位于 `src/trusted_synthesis/experiments/finance_qa_vnext_harness_responsibility/`：
`adapters.py` 是独立有限语义准入；`interface.py` 是新语言与共同 Final；`runtime.py`
记录责任分离事件；`audit.py` 做只读核验与方法支持图；`stage.py` 冻结并执行固定人口。
旧 adapter、旧协议、旧运行器和旧正式工件不改写。

专门控制：`tests/test_qa_vnext_harness_responsibility.py`。仅覆盖本轮新增风险。
运行入口：

```bash
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.stage prepare
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.stage run
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.stage verify
```

`prepare`/`run` 均拒绝覆盖既存目标。`verify` 只核对新工件封存，不再发模型请求。

## 9. 结果

调用前状态：尚未启动在线会话。固定运行结果及局限将在执行结束后追加；
`preparation/design_at_freeze.md` 永远保留调用前版本，不用事后结果重写预注册。
