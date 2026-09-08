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

### 固定批次已完成（2026-09-08）

调用时冻结源码：a5cd967d6a791144d991c2fc256e2f4843840a1e。
新 condition 身份：
finance_qa_vnext_finqa_v21_condition:0ebf75045889450ec4e982d3884a7de17c678168dfa03c89871cf5089e1fb0c7。
三波共 24 个新会话均实际执行一次，没有完整性/条件漂移停波、未知、补样、重试或续跑。
397 个 Provider 响应均报告模型名 deepseek-v4-pro；该名字不是不可变权重快照证明。

结果与主要证据：

- [调用前登记](../artifacts/qa_vnext_finqa_reference_diagnostic/original_12_ef_v21_20260908/preparation/condition.json)
- [逐会话在线审计汇总](../artifacts/qa_vnext_finqa_reference_diagnostic/original_12_ef_v21_20260908/online/summary.json)
- [只读收口报告](../artifacts/qa_vnext_finqa_reference_diagnostic/original_12_ef_v21_20260908/closeout/report.json)
- [全部实际运算、Observation 与逐轨迹解释](../artifacts/qa_vnext_finqa_reference_diagnostic/original_12_ef_v21_20260908/closeout/trajectory_review.json)
- [源码、重放和报告程序身份](../artifacts/qa_vnext_finqa_reference_diagnostic/original_12_ef_v21_20260908/closeout/source_integrity.json)

### 端到端与完整成本

| 条件 | 完整有效 | 预算耗尽 | 实际操作 | 显式 accept | 显式 reject | 模型提交/请求 | 未准入提交 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| E | 9/12 | 3 | 67 | 65 | 2 | 200 | 57 |
| F | 9/12 | 3 | 70 | 67 | 2 | 197 | 49 |
| 合计 | 18/24 | 6 | 137 | 132 | 4 | 397 | 106 |

注意“模型合法 reject Observation”与“宿主拒绝不合法提交”是不同事件。
本批提交分解闭合为：

~~~text
E：200 = 67 action + 65 accept + 2 reject + 9 Final + 57 未准入
F：197 = 70 action + 67 accept + 2 reject + 9 Final + 49 未准入
全批：397 = 137 action + 132 accept + 4 reject + 18 Final + 106 未准入
~~~

实际 397/768 请求；371 次未用额度没有转为补样。实际操作 137/288。
18 条成功会话消耗 205 请求、999,389 Token；6 条失败消耗 192 请求、990,576 Token，全部保留。

| 条件 | Prompt Token | Completion Token | Total Token |
| --- | ---: | ---: | ---: |
| E | 727,490 | 32,712 | 760,202 |
| F | 1,196,444 | 33,319 | 1,229,763 |
| 合计 | 1,923,934 | 66,031 | 1,989,965 |

731,904 个缓存命中 Prompt Token + 1,192,030 个缓存未命中 = 1,923,934。
Provider 的 prompt/completion/total 字段在全部 397 请求均有记录，和数闭合。
reasoning_tokens 在全部 397 请求未提供，保持 total=null、unknown_attempts=397；
observed_subtotal=0 仅表示没有观测到可加的明细，**不是声明实际 reasoning Token 为零**。
HTTP 实际请求体合计 6,917,361 bytes，响应体合计 363,120 bytes。
本报告不使用当前价格倒算美元账单，也不将 Token 预留上界当作实耗。

### 每题结果

表中记法为“完整有效；操作/提交/未准入”。每个单元的会话分母都是 1。

| 原题 | E | F |
| --- | --- | --- |
| C1 | 是；3/7/0 | 是；3/7/0 |
| C2 | 是；4/9/0 | 是；4/9/0 |
| C3 | 是；3/7/0 | 是；3/7/0 |
| E1 | 否；4/32/24 | 否；4/32/24 |
| E2 | 是；3/7/0 | 是；4/9/0 |
| E3 | 是；6/13/0 | 是；5/11/0 |
| M1 | 是；4/9/0 | 是；4/9/0 |
| M2 | 是；6/13/0 | 是；6/13/0 |
| M3 | 是；11/26/3 | 否；8/32/17 |
| J1 | 否；6/32/20 | 是；10/21/0 |
| J2 | 否；11/32/10 | 否；12/32/8 |
| J3 | 是；6/13/0 | 是；7/15/0 |

分层完整有效数（每格分母 3）：E 控制 3、证据 2、方法 3、联合 1；
F 控制 3、证据 2、方法 2、联合 2。总计相同并不意味着逐题行为相同：
M3 仅 E 成功，J1 仅 F 成功；不能据此建立稳定能力排序。

### 引用执行：首次合法不等于一律接受

| 条件 | 总 Observation | 有首次后续提交 | 首次合法 accept | 首次合法 reject | 首次非法 | 没有后续提交 | 首次合法率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| E | 67 | 67 | 65 | 2 | 0 | 0 | 67/67 |
| F | 70 | 69 | 67 | 2 | 0 | 1 | 69/69 |
| 合计 | 137 | 136 | 132 | 4 | 0 | 1 | 136/136 |

全批 lifecycle.observation_binding=0；同一 pending 的连续引用拒绝最大长度=0。
全部实际 HTTP 请求中，pending 状态均公开与其 ID 一致的精确 const、字段说明和复制规则；
全部原始响应通过 v2.1 重放。结论是**本批未观察到引用拒绝**，不是已证明长期零错误。

唯一未观察到首次决策的是 M3_F 第 32 次提交产生的 2015 总收入 Observation。
它保留在 137 个事件、M3_F 的原分母及 6 个失败中；不能写成“137/137 首次合法”，
也不能将它记为一次非法 Update。

四次合法 reject 均是真实模型选择：

| 会话 | 产生/拒绝提交序号 | 实际观察与后续 |
| --- | --- | --- |
| E3_E | 5/6 | 997/7 的结果被拒；随后显式 7×1000，正确完成 |
| M3_E | 16/17 | 错把 2016 煤收入当总收入组成分母；拒绝后补读总收入并完成 |
| J2_F | 17/18 | 一个错误年份/单位目标声称下的乘积被拒；后续有正确乘积，但最终仍失败 |
| J3_F | 3/4 | 原欲读取金额 22.3，却实际读取年份 2017；拒绝后改读并完成 |

Update 只公开 accept/reject，不包含解释文字，因此这些拒绝的“内在原因”不能直接获知；
上表描述的是被拒的实际操作、其公开 reason 与随后真实行为，不替模型编写隐藏推理。

### 剩余拒绝与金融诊断

106 次未准入提交分布如下。零 Observation 引用拒绝不等于零生命周期或接口错误。

| 拒绝码 | 次数 |
| --- | ---: |
| final.target_not_established | 87 |
| lifecycle.accepted_claim_input_only | 8 |
| final.citations | 5 |
| numeric.arity | 3 |
| schema.invalid_submission | 2 |
| lifecycle.no_pending_observation | 1 |

87 次 target 拒绝分别来自 E1_E 22、E1_F 23、M3_F 14、J1_E 16、J2_E 7、J2_F 5。
原接口引用循环不再出现，但错误答案与错误依据被重复提交，错误恢复仍是实质问题。
所有金融归类是逐轨迹后验描述，不是独立能力错误率。

四焦点共八条轨迹都到达了调用前冻结的可检查位置（REACHED=8，NOT_REACHED=0）。
这只是说明本批可检查，不证明所有方法都已充分探索。

**E1：尺度错误与重复错误 Final。**
E/F 都正确读取 15.3 百万元和 139549 千元，第 5 次直接相除，第 7 次只乘 100，
从第 9 次起发布约 0.01096389082%。冻结目标是
15.3/(139549/1000)×100≈10.96389082%，相差一千倍。
第 5 次除法本身可以是后续再乘 1000 的合法中间式；**确证错误的是将未换算结果作为 Final**。
两条都没有执行尺度恢复，全部四个 Observation 已接受，无 pending，最后停在第 32 次错误 Final。
E1_E 的公开 reason 曾写出 139.549，却实际引用 139549 Claim，体现说明与实际依赖并不等价。
E1_E 还尝试用单输入 average“认证”答案，因 arity 未准入；宿主未代做任何认证操作。

**M3：期间集合与分母输入，既有错误也有真实恢复。**
E 第 9 次正确求三年煤收入 9804；第 16 次宣称求三年总营业收入，
却把 2016 煤收入 2440 与 23988、21813 相加，得到 48241。
第 17 次合法 reject 后，第 18 次补读 19941，第 20 次得到正确分母 65742，
最终第 26 次完整发布 9804/65742×100≈14.912841106142%。
F 则先将 2016 单年 2440/19941×100≈12.23609648% 当三年结果 Final，
后来才补读并在第 29 次正确求三年煤收入；第 31 次仍发布旧单年答案，
第 32 次读取 2015 总收入后预算结束。记录为“部分恢复、未完成”，
不能说它完全没识别三年方法，也不能把单年比率这个中间式本身一律判错。

**J1：税后定义与执行差异。**
E 第 5—9 次计算税前增长率 (18.1−14.6)/14.6×100≈23.97260274%，并以此 Final。
第 14、21 次公开 reason 已说明应计入负税收利益，但用尚未读取/接受的 source 直接做加法未准入；
第 29/30 次才读取并接受 −6.3，最终第 32 次仍发布税前结果。
因此有明确目标口径错误和未完成恢复，不是“从未说出正确公式”。
F 读取四项事实，实际算出 18.1+(−6.3)=11.8、14.6+(−5.2)=9.4，
再算差额、比例及百分比，最终第 21 次完整发布约 25.531914893617%。
差额重复执行一次增加成本，但未见具体已执行的税后口径错误。

**J2：错误配对可在得到正确中间结果后继续污染 Final。**
E 第 7 次正确构造 2017 值 11×33.32=366.52，
第 10 次却把 2016 股数 13 配上 2017 单价 33.32，称其为 2016 值，
得到 433.16；随后发布 −66.64，又取绝对值发布 66.64。
第 18 次补读 26.93 后，实际恢复正确年度乘积 366.52 与 350.09，
但没有把它们相减，而在第 32 次继续发布旧错误 absolute Claim。
实际操作只用 11/12，不宜把失败归为必然被实际操作上限卡住。

F 第 15 次同样将 13×33.32=433.16 声称为 2017 值。
它合法拒绝过第 17 次的另一乘积，随后第 19、21/23 次已经得到正确的 366.52、350.09，
但第 27 次仍选择旧错误 433.16，形成 83.07 并持续 Final；
12/12 操作与 32/32 提交耗尽。正确目标为 366.52−350.09=16.43 百万美元。
这些是实际输入与目标年份声称矛盾、错误终局依赖的证据，
不是把任何跨期乘积或股数乘百万的中间换算都自动判错。
两条都属于“局部正确结果已出现，但未形成并消费正确终局依赖”，不能笼统称为不会乘法。

额外恢复例 E3_E、J3_F 如上表。唯一 off_reference_source_ids 非空的是 J3_F 的 source:p1n1：
确定其为错误读取的依据是公开 reason 想读金额而实际读到年份，并非单纯因不在参考集合。
反过来，M3_E 的错误分母和 J2 的错误配对都只用了参考集合内数值。

### 与旧 v2 的描述性前后变化

| 记录 | 原 v2（保留） | 新 v2.1 |
| --- | ---: | ---: |
| E 完整有效 | 2/12 | 9/12 |
| F 完整有效 | 7/12 | 9/12 |
| Observation 引用拒绝 | 410 | 0 |
| 真实请求 | 636 | 397 |
| 实际 Total Token | 2,769,305 | 1,989,965 |

新批观察到了更顺畅的引用执行，以及更多完整结果和可检查的真实金融行为。
**没有同期 v2 对照，也没有每题重复采样，因此不能把这些差值宣称为修复的精确因果效应。**
尤其不能从旧 636 中机械减去 410 来预测新成本；实际新轨迹消耗的是独立测得的 397 请求。
E/F 本批都为 9/12，不证明条件等价，也不建立稳定成功率或金融能力水平。

### 接线验证、报告修订与封存边界

调用前 15 项新增离线控制通过；只检查新 v2.1 入口、HTTP 字节公开 const、
完整原响应重放、合法 reject、重复引用段、无后续提交、零 Observation 及 transport 无响应。
未重跑旧 67 项控制、全量 census 或旧 H1/H2，也未新增 24 次静态可达实验。
收口重新校验了全部 24 个 session/transport seal、全部原始 HTTP/content、v2.1 transition、
独立有理数算术与 Final，以及所有冻结源码成员和成员集合；在线工件没有被改写。

首次运行冻结的 closeout.py 时发现报告字节统计将整数 stat.st_size 写成了 stat.st_size()，
导致 TypeError。它是只读报告代码的笔误，不在 stage.run 的在线路径上；
首次报告未生成 closeout 目录，也未请求 Provider，全部 online 已提前完整封存。
为了保留调用时整个源码快照，未修改该冻结文件，而新增独立批后脚本
[scripts/finqa_v21_closeout.py](../scripts/finqa_v21_closeout.py)，
除绝对导入和脚本身份元数据外，计算修订仅为将上述调用改为属性读取。
脚本 SHA-256 与原因写入 source_integrity.json。该脚本完成了最终全部重放与字节统计。
这不是新 Runtime 版本、模型合同改动、结果替换或重新采样。

收口报告身份：
finance_qa_vnext_finqa_v21_closeout:7507cd22bb4ebcacff3a6317d620e8a0600f87e69868f50b25600c2c11b8235b。

只读复核现有会话可以运行以下代码，不使用 API，不写入原目录：

~~~bash
trusted_data_synthesis/.venv/bin/python - <<'PY'
from pathlib import Path
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.panel import Panel
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reference_diagnostic.audit import read, verify_session
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reference_diagnostic.stage import OUTPUT
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import verify_source_snapshot
root = Path.cwd()
p = root / OUTPUT
for name in ("preparation", "online", "closeout"):
    manifest(p / name)
verify_source_snapshot(root, read(p / "preparation/implementation.json"))
panel = Panel(root)
for r in read(p / "preparation/registrations.json"):
    d = p / "online/sessions" / r["label"]
    manifest(d)
    assert verify_session(panel, r, d) == read(d / "audit.json")
print("24 frozen v2.1 sessions verified; 0 Provider calls")
PY
~~~

### 本批结论与建议的下一焦点

本批可按 PASS_AS_SCOPED 收口：新条件登记、固定 24 会话执行、完整分母与失败、
引用事件及缺失后续决策、全部实耗和对应版本重放均已闭合。
范围内结论是：**本批明确合同下未见 Observation 引用循环；剩余失败呈现可定位的金融目标、
期间/输入配对与错误终局依赖消费问题，同时也出现合法 reject 后自主恢复的完整轨迹。**

最小后继建议优先针对 E1 的单位对齐与错误 Final 后恢复：它在两条件下均有具体失败见证，
且不再被引用循环遮蔽。若另做 J2，应聚焦“已有正确中间结果时为什么仍消费旧错误 Claim”，
而不是笼统扩充乘法工具。上述只是根据轨迹提出的后续实验对象，并未在本批再改反馈、
增加工具、扩题或发起额外请求；也不据此声称一般失败概率、Oracle 穷尽性、行为商闭合
或 VTDO/Student 收益。

