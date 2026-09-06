# 同一 Share 任务的分层有效支持探索

阶段：`finance_qa_vnext_same_task_support_exploration_pilot`。本轮依据上一轮 `PASS_AS_SCOPED` 审计转向真实有效支持探索，不重开已经闭合的十五轨迹商测量，不补旧 S01，也不进行 Student/Contribution/VTDO 更新。

## 1. 科学对象和预先界定的边界

旧八任务开发面板已完成 15 个 Assignment、7 个等价同任务配对；八任务各自当前只有一个观察类，类间重分配自由度为 0。这不是“所有可能行为只有一种”的证明，也不能通过改变任务权重、错误计数或调度标签制造同任务多类。

新问题是：在同一个已绑定 Share Task、Context、Evidence、操作空间和验证标准下，一个明确登记的分层探索生成源，能否产生两种实际充分依据不同的完整有效行为？

- 披露支持：有效 Final 的 ratio 分母直接来自披露总额 Evidence。
- 重建支持：本会话实际执行 sum，模型独立 Update 接受 total Claim，后继 ratio 实际通过 Claim 输入消费这个 total，最终得到有效 Final。

仅调用 sum 不够；如果 ratio 后来仍使用披露总额，它仍是披露支持，并须保留已实际执行的 sum。模型文字声称采用重建、N/E 组名不同或离线改图得到差异，都不是新双支持见证。

主存在性指标 `W_support` 要求两条本轮独立 Qualified 轨迹分别满足上述实际链条，且当前适用规则下有确定的非等价比较证明。存在性见证与全量分布闭合分开：具体两条轨迹可以证明存在双支持，但其他有效轨迹未映射时完整分布仍为 null。

## 2. 固定任务、协议与历史来源

前驱提交：`4a810d51d2c7eccd70e3c241b4223c8bc3195fb9`。旧八任务面板、旧有限类及其点质量、成功率 `15/16` 和任务边际 `μ=1/8` 均保持不变。所有历史 Share 模型或 fixture 只作背景，不进入新分母、提示前缀或 Assignment。

复用原 Union Pacific Corporation and subsidiaries 的 2015 年 freight/total operating revenues Share 任务：

| 对象 | 固定身份或规则 |
| --- | --- |
| Task | `part_whole_share_task:0616bef8f302347723ff0ab8c84a570a9b76bb6cb09681e9a7dafec555a13a3f` |
| Context | `finance_qa_vnext_context:9a11fc330aee0bc054b1f0e62c0df9e69a4fffd52abcbae3b601ccd4e525d1c1` |
| Evidence | 原 freight、other、total、part_whole 公开记录及原总分关系 |
| Operation | 原 `relation_sum`、`share_ratio`、`scale_percent` 实现、oracle 和 registry |
| Action/Update | 原完整候选列表、所选 offer 绑定、公开判断及显式 Update 合同 |
| Final | 原精度 50、HALF_EVEN、六位量化与精确真实引用标准 |
| 监督表示 | 原 32,768 政策及同一 tokenizer 资产；新数据独立绑定 |

加载器直接解析已有 Share 注册与来源，不扫描或重新实例化其余金融任务。它比较实际 Context 的规范 JSON 与旧冻结 Context，全字段相同；不因 Python 内存 tuple 与 JSON array 的表示差异修改公开内容或身份。该接线差异曾在新代码预检中被拒绝，已在正式冻结前改为规范字节比较。

准备、运行及测量核对八个历史工件前缀的 12,984 个文件、653,652,590 字节，以及 898 个前驱 Python 文件。它们都必须等于前驱 Git blob；不重跑旧 102 项测试、旧资格/商解释或旧 113 条 Token。

本轮输入审计 SHA-256 为 `64524dee1a519236d9e3fc69e525fedb43b555f081390d0dac962c70f5ed35d3`，25,733 字节。全文另保存在准备工件中。来源已用于多轮开发，即使其档案文件名为 `test.json`，也不恢复盲测身份。

## 3. 八个新会话与两个精确提示 profile

探索源 `Γ_explore` 预先定义 `Pr(N)=Pr(E)=1/2`，采用固定分层采样，每层四会话。不是按同一随机种子构造反事实配对，不将有限差异解释为稳定提示因果效应。

| 固定波次 | 会话一 | 会话二 | 最大并发 |
| --- | --- | --- | ---: |
| 1 | N01 中性 | E01 软引导 | 2 |
| 2 | N02 中性 | E02 软引导 | 2 |
| 3 | N03 中性 | E03 软引导 | 2 |
| 4 | N04 中性 | E04 软引导 | 2 |

每波两会话均结束后才进入下一波。会话从独立初态开始，不读取彼此响应；后续提示、数量、顺序不根据已出现的支持类型改变。普通模型失败保留并继续；完整性或内部故障可停止未来波次，未启动登记仍进入完整八行结果。

N 复用原中性 system prompt。E 使用完全相同的中性前缀，接两个换行，再附以下精确 ASCII 段落（不追加答案、Action JSON、候选 ID 或历史轨迹）：

```text
Exploration preference, not a correctness requirement: While preserving the task goal and all legal actions, prefer trying to construct a usable denominator from the public component quantities and their composition relation. If you use this basis, subsequent calculations should actually consume the corresponding accepted Claim. You may still choose another legal basis. Do not claim unexecuted results or fabricate support.
```

这是生成偏好，不是正确性条件。E 合法使用披露总额仍可以 Qualified，只是没有提供重建支持。没有过滤候选、锁定动作、自动修复长 ID、补写 Update 或替换 denominator。

实际传输仍使用原 `OnlineModelCallback`、`HttpxSender` 和 `render_http_request`。它们本来支持每实例 `config.system_prompt`；本轮无需改变 Runtime 请求或复制在线回调。新配置子类只固定总量 256、记录 N/E profile，并准确描述 system profile 的含义。N/E 的公共请求规范字节完全相同，实际 HTTP messages 的 system 内容不同且分别落盘。

N/E profile 身份、完整提示、模型配置身份和共同探索条件在调用前冻结。每个新注册绑定自己的 profile/config 与共同 `run_condition_id`。旧资格检查仍按该会话的真实配置和实际 HTTP 字节验证，没有把重建偏好输入 QA 评分。

## 4. 资源上限与停止规则

教师配置沿用 `deepseek-v4-pro`、thinking disabled、temperature 0.7、top_p 1.0、JSON object、非流式。允许的实际模型响应别名和来源判定沿用原合同。这是实验配置复用，不保证远端模型权重或可用性始终不变。

| 项目 | 冻结上限 |
| --- | ---: |
| 新 Task 实例 | 0 |
| 新会话 | 8 |
| 每会话 Action | 12 |
| 每会话 Submission / Provider attempt | 32 / 32 |
| 总 Provider attempt | 256 |
| 单次 completion | 8,192 |
| 单次 HTTP body | 98,304 bytes |
| 单次 reserved allowance | 107,520 |
| 总 reserved allowance | 27,525,120 |
| 自动重试 / 模型回退 / 失败替换 | 0 / 0 / 0 |
| Student forward / 更新 / GPU | 0 / 0 / 0 |

有效 Final 后立即停止对应会话。缺少目标支持不追加调用、改提示或替换失败。在线目录已存在时禁止再次启动八会话；没有自动在线 resume。凭据只在准备和来源回读成功后加载，原始输出持久化沿用原先的先预约后发送及完整传输账本。

reserved allowance 是上限和预约量，不是测得的 Token 消耗；实际 Provider usage 另行报告。缺失 usage 或无法确定的尝试数保留 unknown，不补成零。

## 5. 新总体的语义投影、比较与 Assignment

不将新八会话塞入旧固定十六行分布器。本轮新增探索总体包装，复用上一轮已冻结的 `quotient_rule()`、`project_entry()` 与精确图比较器；禁止在看到新结果后扩充归约条件。

新的 `comparison_contract` 在调用前明确绑定共同探索源、N/E 两个合法 profile/config、相同 Task/Context/协议/registry 及冻结规则。包装层先核验每条原始登记、配置与资格父链，再把共同探索源作为比较的生成域。profile 标识保留在来源元数据中，不进入行为投影；没有临时删除原比较器的父身份检查。

同任务有效投影之间最多比较 `C(8,2)=28` 对。实际操作、输入/判断、生产与消费依赖、完整 Final 及规则要求的保留纠正关系均参与精确比较。新类和 Assignment 使用新的来源绑定身份，不直接继承旧 S 类 ID，也不以图哈希、提示组名或支持标签代替等价关系。

实际支持提取从有效 Final 的答案 Claim 开始，沿 percent → ratio → denominator 检查本会话执行、Observation、独立 accept Update、Claim 和输入引用。重建见证必须是实际消费总额 Claim；披露见证必须引用原 total Evidence。支持分类与一般商类数分别报告，有额外真实操作或保留交互时也应说明差异来源。

新事件若不在旧纠正规则适用域，保留有效资格与 `undetermined` 投影。存在未映射有效质量或必要比较未定时，不给完整条件分布；不得为得到多类删掉难解释的有效观察。

## 6. 分层、联合与条件分布

每层原分母固定 4，探索源原分母固定 8。所有登记结果可判定时：

```text
q_N = m_N / 4
q_E = m_E / 4
q_explore = (m_N + m_E) / 8
u_explore(z) = (n_N,z + n_E,z) / 8
π_explore(z | success) = (n_N,z + n_E,z) / (m_N + m_E)
```

成功条件下两层权重是 `m_N/(m_N+m_E)` 与 `m_E/(m_N+m_E)`，不能一般写成 `0.5π_N+0.5π_E`。组间成功率不同时，两种算法不同。

unknown/not_started 仍占原登记分母，成功率输出 null 和上下界；完整探索 π 也保守保留 null。可以另列明确仅限已观察有效样本的诊断分布，不能冒充完整探索源分布。各层单独判断其结果与映射闭合；已确定的具体双支持存在性见证不被其他未定会话否定。

零成功、单一支持、多类但非目标机制、全部成功但无重建，均是可接受的有界结果。只有真实 D/R 两条完整链并有确定语义分离才称 `W_support=1`；类数增加本身不构成 Contribution 或训练价值。

## 7. 新监督素材的原样表示

仅本轮 Qualified 会话的准入原响应进入新正向候选；失败前缀不拼接成成功。复用原 32,768 表示政策、完整包判定及小 CPU batch 机制，但独立生成新 data binding、Token 记录和包。

在编码前检查每行真实两条 messages：system 必须逐字等于该登记 profile 的冻结 prompt，user 必须等于对应原事件请求；目标必须仍是原准入响应。E 指导不被删除，不将引导条件下的目标配到伪造的中性输入上。新 sidecar 建立 profile/config → 原候选 → 新 Token/包的链接。

超长原响应和请求不截断、不清洗，保留 not_fit 与不完整包；不得为完整包率修改原轨迹。素材首先是探索证据，不直接继承旧 P/Q 权重，不把 N/E=1/2 当作最优类权重。没有训练采样器、Student 效用或权重干预。

## 8. 本轮接线检查与执行入口

新增局部测试覆盖：N/E 相同公共候选空间且精确提示不同；原八登记和固定波次；ordinary failure 不替换、unknown 后保留 not_started；profile 名字不是类别；同样 Final 不能遮蔽分母生产—消费差异；混合条件权重按成功质量；未映射质量和 unknown 不丢弃；E 指导不在导出中消失；零成功和超长表示正确收口。

这些是构造或隔离副本控制，不是新模型样本。准备、在线执行、各新会话资格核验、商测量和监督表示在同一阶段完成；分析直接读取在线 worker 已封存的新资格，不再独立重跑同内容语义审计。所有旧实验工件保持不变。

在项目根目录使用现有环境，提交冻结实现后：

```bash
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_support_exploration prepare
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_support_exploration run
```

新工件目录：`artifacts/qa_vnext_support_exploration/share_four_neutral_four_guided_v1_20260907`。准备目录保存精确设计、两 profile/config、比较合同、原规则、八登记、实际初始 HTTP、Token 政策、来源与实现身份；执行目录保存固定调度、原运行/传输证据、新资格、分析及封存 manifest。

### 8.1 正式执行结果与身份

源码冻结提交为 `a6a2c2c7528b0c84c189c1f7c37c1292028379c0`。准备成功后只执行了一次八会话在线入口，四波均按固定 N/E 顺序启动，未重试、回退、替换或追加样本。实际 202 次 Provider 调用，八条结果均证据完整、条件有效、模型来源验证通过；响应模型标识均为 `deepseek-v4-pro`。没有 unknown 或 not_started。

| 对象 | 正式 ID 的哈希部分 |
| --- | --- |
| 探索条件 | `1ce7cd127bdabb128949f389ed0f9dd9244a4ff48aa29eb9e61d72c80f89d0ca` |
| 比较合同 | `54f82514bb8a92c7607639fabb1d750d13bc9ca875947f107793723fd7513ed9` |
| 准备 manifest | `b89fa592ef49de187418ed4bfc636fdd06af5c3f3e606406f006cdbe40cf0a16` |
| 执行 manifest | `920893d34dd2409aa4a78f60c737a7bee008781efa945f3b37aadb91386aba6e` |
| 分析 manifest | `e0c540d5325991a5770732b2ee34c59f8384a51804b045aea2c8ea428c978fb3` |
| 正式报告 | `8cb45bb6748246a185f224d4909992608a0e6017a33401f56557ea1b743463d6` |

旧商规则 ID 原样复用：`qa_vnext_model_execution_panel_quotient_rule:0af6d8446a28f48387d6ea5697d9284c65907dc633422ee85393699b62d7cfb2`。在线开始后未修改任何源码、提示、资格标准或商归约规则。

完整身份与结果见[正式报告](../artifacts/qa_vnext_support_exploration/share_four_neutral_four_guided_v1_20260907/execution/report.json)、[冻结条件](../artifacts/qa_vnext_support_exploration/share_four_neutral_four_guided_v1_20260907/preparation/condition.json)和[比较合同](../artifacts/qa_vnext_support_exploration/share_four_neutral_four_guided_v1_20260907/preparation/comparison_contract.json)。

### 8.2 八会话分层结果

下表“支持”只给 Qualified 完整行为标注；失败前缀即使执行过相同计算，也不晋升为有效支持。深度按“结构／语义／可观察选择依赖”列示；失败行仅为 `reached_prefix`，不是完整行为深度。

| 会话 | 调用/提交 | A/U/F 准入 | 拒绝 | Qualified | 有效 Final 实际支持 | 新投影 | 深度 |
| --- | ---: | --- | ---: | --- | --- | --- | --- |
| N01 | 32 | 1/1/0 | 30 | false | — | ineligible | 1/1/1 前缀 |
| E01 | 32 | 3/3/0 | 26 | false | — | ineligible | 3/3/2 前缀 |
| N02 | 32 | 3/3/0 | 26 | false | — | ineligible | 3/3/2 前缀 |
| E02 | 16 | 3/3/1 | 9 | true | 重建 total Claim | undetermined | 3/3/2 完整 |
| N03 | 8 | 3/3/1 | 1 | true | 重建 total Claim | undetermined | 3/3/2 完整 |
| E03 | 32 | 3/3/0 | 26 | false | — | ineligible | 3/3/2 前缀 |
| N04 | 32 | 1/1/0 | 30 | false | — | ineligible | 1/1/1 前缀 |
| E04 | 18 | 3/3/1 | 11 | true | 披露总额 Evidence | supported | 2/2/1 完整 |

计数闭合：

```text
202 = 20 Action + 20 Update + 3 Final + 159 未准入提交
159 = 59 alternative_set + 8 public_judgment + 92 final_qa
42 = 三个有效会话的 21 准入 + 21 未准入
202 = 42 有效会话提交 + 5 × 32 失败会话提交
21 正向候选 = 9 Action + 9 Update + 3 Final
```

所有实际 Observation 的首次后继 Update 都完成 accept，共产生 20 个 accepted Claim；这不能把失败前缀当成完整成功。五条失败均为 `submission_budget_exhausted`，`qa_valid=null`，不是内部证据未知或被替换的会话。

### 8.3 获得了什么支持，为什么严格 W 尚未成立

实际支持核查确认：N03、E02 各自的有效 Final 真正依赖本会话执行 sum 并经显式 Update 接受的 total Claim；ratio 以 Claim 输入消费该结果，随后 percent 和有效 Final 完成。这是新的真实模型重建支持可达见证，且中性与软引导条件下各出现一次，不只是离线图修改或失败计算前缀。

E04 虽属软引导组，仍合法使用披露总额 Evidence 完成 Final；它也执行了 sum，但该 total Claim 未被后继 ratio 消费。它仍然 Qualified，证明本轮没有把探索偏好偷换成正确性约束。三条成功最终 result 均为 `{value:"93.508458",unit:"percent"}`，而 N03/E02 的实际 lineage 有三项，E04 有两项；最终数值相同不抹掉真实依据差异。

但严格定义的 `W_support` 还要求当前适用规则下的确定 D/R 商差异配对。本轮两个重建成功的新纠正形态没有被原规则完整解释：

| 会话 | 未定位置（T 从 1 起） | 具体原因 |
| --- | --- | --- |
| N03 | T1 | 被拒披露 ratio 提案后先执行 sum，后来 ratio 改用新 total Claim；不是原 S02 那种后来执行相同操作与相同实际输入的关系 |
| E02 | T1–T2 | 同上：后来实际 R 的 denominator 与原被拒 D 提案不同，冻结规则未定义这类支持转换历史 |
| E02 | T9、T11、T12、T14 | Final 引用遗漏真实重建支持中的 other Evidence，却加入披露 total Evidence；不是“保留完整真实 lineage，仅附加冗余引用”的原对齐域 |

具体测量原因码为 `panel_quotient.retained_later_proposal_execution_not_identified` 和 `panel_quotient.new_or_replaced_citation_support`。前者不是缺失 ratio 执行记录，而是找不到原规则要求的“相同 operation、inputs、parameters 的后续实际执行”；真实发生的是支持转换。后者不否定最终被接受 Final 的正确性，而是此前被拒引用改变不能按原规则归约。

E02 T10、T13、T15 的其他 Final 表示修正可以按原规则解释，但整条轨迹仍因上述未定项不获得投影。N03 T8 和 E02 T16 的有效 Final 资格继续成立，未重新判为失败。

E04 的 T1 被拒 D 提案 → T2 sum → T3 accept → T4 实际 D ratio，以及 T8–T17 到 T18 的同 Claim Final 对齐，均落在原规则域，因此获得一个正式 Assignment。其实际 sum 与未消费 Claim 继续保留，没有为了映射而删除。

结果应同时表述为：**实际 Qualified 支持中 D=1、R=2；supported=1、undetermined=2；正式 Assignment=1；全有效集合应有 3 对，但当前可比较的 supported 配对为 0。**

所以 `W_support=false` 表示预先要求的双支持商分离见证尚未建立，不表示重建支持没有发生，也不表示三个成功只有一个商类。`complete_class_count=null`，当前一个已赋类只是局部结果；完整 π 仍为 null。没有在看到这些事件后扩规则、删未映射成功或用部分实际图越过原支持 Gate。

具体来源见[商测量、逐事件解释与实际支持证明](../artifacts/qa_vnext_support_exploration/share_four_neutral_four_guided_v1_20260907/execution/analysis/quotient.json)，原始会话分别为 [N03](../artifacts/qa_vnext_support_exploration/share_four_neutral_four_guided_v1_20260907/execution/sessions/N03/runtime/session.json)、[E02](../artifacts/qa_vnext_support_exploration/share_four_neutral_four_guided_v1_20260907/execution/sessions/E02/runtime/session.json)、[E04](../artifacts/qa_vnext_support_exploration/share_four_neutral_four_guided_v1_20260907/execution/sessions/E04/runtime/session.json)。

### 8.4 成功率、未映射质量与分层权重

| 分层 | 登记 n | 成功 m | 成功比例 q | 已映射联合质量 | 未映射有效联合质量 | 失败质量 | 完整 π |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| N | 4 | 1 | 1/4 | 0/4 | 1/4 | 3/4 | null |
| E | 4 | 2 | 2/4 | 1/4 | 1/4 | 2/4 | null |
| Γ_explore | 8 | 3 | 3/8 | 1/8 | 2/8 | 5/8 | null |

质量守恒为 `1/8 + 2/8 + 5/8 = 1`，没有 unknown/not_started 质量。探索源成功比例为 `3/8=0.375`；N/E 成功条件下的混合权重分别为 `1/3`、`2/3`，不是各 `1/2`。

实际支持标签在三个成功中为披露 `1/3`、重建 `2/3`，这只是已核查的支持类型构成，**不能替代尚未闭合的完整商分布**。不能仅对 E04 重归一化为探索源 `π=1/1`；有效但未映射质量仍是 `2/3` 的成功池。

E 的成功率在这八个有限观察中高于 N，不构成稳定提示因果增益、自然路线偏好或统计显著性结论。两个 profile 是不同来源分层，数值本来可以相同或不同；条件中禁止用引导分布替代中性分布的约束不是预言二者数值必不相等。

机器统计见[分层及探索源测量](../artifacts/qa_vnext_support_exploration/share_four_neutral_four_guided_v1_20260907/execution/analysis/measurement.json)。

### 8.5 保留的负结果

N01 在 T4 起、N04 在 T3 起未正确提交完整当前候选列表，分别出现 29、30 次 `admission.alternative_set`。首个错误分别把正确 ID 尾段 `...7a9f4fbb3f40` 写成 `...7a9f4bbf3f40` 和 `...7a9f4bb3f40`。这些是不同的实际错误，不统一描述成同一种少字错误，也不把全部原始响应假定为完全相同。公开规则和反馈未被删改。

N02、E01、E03 完成了三个实际操作与三个 accept Update，但 Final 分别被拒 23、26、26 次，均未获得有效 Final。比如 E01 最后已经给出六位数值，却将披露 total 与重建支持共同作为四项 citation，而实际重建链要求的是自身真实 lineage；正确数值不能补偿引用不匹配。这里只报告已记录拒绝与输入输出，不推断模型动机或一般算术能力。

这些失败不触发接口修复、自动纠错或补样；它们完整进入本轮 `3/8` 的分母。

### 8.6 原始监督表示与成本边界

三条成功各有七个准入响应，全部形成原样新候选及完整包。E02、E04 的十四条候选保留其真实 E system 指导，N03 的七条保留真实 N prompt；没有给 E 目标重新配中性请求。

| 项目 | 实际结果 |
| --- | ---: |
| 原始正向候选 / fit | 21 / 21 |
| not_fit / 截断 | 0 / 0 |
| 完整包 | 3（另五条失败保留非完整、非正向包记录） |
| 最大序列长度 | 24,574，距 32,768 尚余 8,194 |
| prompt Token | 471,371 |
| 目标 Token | 18,019 |
| 协议 suffix Token | 42 |
| 总真实 Token | 489,432 |
| CPU batch | 12，每批至多 2 条 |
| padding Token | 6,208 |
| 含 padding 总位置 | 495,640 |

即 `471,371 + 18,019 + 42 = 489,432`，再加 `6,208` padding 得 `495,640`。目标 mask 与因果前驱计数均为 18,019，全部在 CPU 检查；不证明 Student 或 GPU 训练效用。Token 记录继承原资格的 Assignment 字段，新的商 Assignment 独立存于 quotient sidecar，不回写原候选或伪造其生成时已有类身份。

新表示 data binding 为 `qa_vnext_model_execution_task_panel_representation_data_binding:e2a2055a27a9af6cb7d8e8714566f3f72da448f2dbb7ff84f05a797d511f40ff`。详见[profile 与原始消息检查](../artifacts/qa_vnext_support_exploration/share_four_neutral_four_guided_v1_20260907/execution/analysis/representation_profile_checks.json)、[完整包](../artifacts/qa_vnext_support_exploration/share_four_neutral_four_guided_v1_20260907/execution/analysis/session_packages.json)及 [CPU 加载](../artifacts/qa_vnext_support_exploration/share_four_neutral_four_guided_v1_20260907/execution/analysis/cpu_loading.json)。

Provider 的 202 次实际 usage 均有 prompt/completion/total 字段：prompt 4,184,419，completion 110,368，合计 4,294,787；缓存命中 2,906,496、未命中 1,277,923，二者和为 prompt 总量。reasoning usage 字段在 202 条中均缺失，保留 null，不能由 thinking disabled 请求推断其测量值为零。

实际预约量 `202 × 107,520 = 21,719,040`，低于上限 27,525,120；最大实际 HTTP body 为 74,092 bytes，低于 98,304。N/E 初始 body 分别为 70,029/70,459 bytes。以上预约量、模型 usage 与本地监督 Token 是三种不同计量，不相加也不互相替代。[传输指标](../artifacts/qa_vnext_support_exploration/share_four_neutral_four_guided_v1_20260907/execution/analysis/transport_metrics.json)保留全部实际 attempt 来源。

### 8.7 检查、封存与范围结论

新增组件测试 **63/63 通过，22.83 秒**：plan/runner 7、quotient 26、measurement 21、representation 9。Ruff 全部通过，mypy 新增 10 个源码文件通过。[JUnit](../artifacts/qa_vnext_support_exploration/share_four_neutral_four_guided_v1_20260907/validation/component_tests.xml)保留逐用例结果。没有重跑旧测试或独立复做同内容语义审计。

正式在线阶段允许新 Share Runtime 和新资格核验，实际执行 20 个 Share 操作；非 Share 操作、Student 构造/权重读取和 CUDA 初始化禁止入口计数全零。离线测量/表示阶段 Provider、Runtime、Operation、资格/audit 重跑及 Student/GPU 的 16 个禁止入口计数全零。`cuda_initialized=false`。这是插桩入口的执行边界，不是对任意代码的形式化隔离证明。

历史 12,984 个工件、653,652,590 字节与 898 个前驱 Python 文件原字节不变，旧 113 条候选/Token 和旧 15 个完整包未重编码。新阶段共 2,893 个文件、143,825,264 字节：准备 manifest 32 个成员，执行 manifest 2,858 个成员（含分析目录和分析 manifest），另有准备/执行 manifest 本身及一份 JUnit；分析 manifest 单独绑定 34 个成员。发布前只核对封存成员与字节读回，没有新增模型样本。

本轮工作流已完成，结果不是“全部商测量闭合”：实际披露与重建的完整模型支持都已出现，重建生产—消费链在新条件下得到实证，但两条有效轨迹的纠正历史仍未映射，完整 π 与全量类数仍未定，严格 `W_support` 尚未建立。原有十五轨迹商测量对象继续保持已闭合；本轮没有回写它，也没有开启 Student/Contribution/VTDO 更新。

## 9. 正确收口与下一对象

若取得双支持，应停止重复证明同一任务的支持存在性，下一步另行固定跨真实任务绑定的机制复用、类内物化和独立评价对象，再考虑受益模型、Contribution 与类概率干预。若没有取得，也接受本轮有限负结果，区分“生成没有采用另一依据”与“合法行为语言不能表达它”，不通过改商规则或重复采样追求预期结果。

旧主线保持暂停。未授权为本轮追加新任务、补样、接口重设计或 Student/GPU 训练。
