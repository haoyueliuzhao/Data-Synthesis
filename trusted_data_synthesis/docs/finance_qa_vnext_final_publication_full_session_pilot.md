# Final 公开规则与六个完整会话试验

阶段：`finance_qa_vnext_final_publication_full_session_pilot`。本轮依据新审计，修复 Final 公开输出要求与严格验证标准之间的对应缺口，然后用原三个已绑定任务各 N/E 一个全新完整会话检验可达性。

本文的设计、规则和预算在首次新 Provider 调用前固定。历史十二会话仍为 0/12；本地构造控制不是模型成功。正式结果在后续结果节单独记录。

## 1. 问题、接受的旧结果与不做的事项

上一轮三来源参数化与十二会话执行已经成立，十二会话都到达 accepted percent Claim，但没有有效 Final；384 次调用、0/12 Qualified、无正向候选均保持历史事实。失败前缀中 D/R 实际输入的出现，不是完整有效支持见证。

本轮只回答：**在不改变任务、计算与严格正确性标准的情况下，完整公开 Final 要求与针对性反馈后，模型能否从新初态完成这些任务？**

不重新打开 Action、Update 校准或商规则扩展，不增加来源，不接续旧失败状态，不给旧轨迹追加构造 Final，不由 Host 清洗／补字段／量化／修正引用后计为模型成功，不进行训练、Contribution、类权重或 VTDO 更新。原 UNP/2015 的已闭合双支持结论不受追溯修改。

审计原文 SHA-256：`b6a8b424d0cb6f2505a2b2a1af99a8960e1b51a6acfb92d6d2f9752ff4e37a6b`，21,273 字节、371 行；正式准备保留其原始字节。

## 2. 为什么需要 Final 专用说明

原基础 Final 的 result 仅声明为任意字段对象，但严格 verifier 要求该对象恰好是 value/unit、value 是规定量化后的字符串、unit 精确为 percent、citations 无重复且精确等于所选答案 Claim 的实际 Evidence lineage。

六位小数要求此前已经公开；本轮没有把所有旧错误都归于规则缺失。修复的是此前没有完整公开的类型、内层字段边界、支持声明要求及拒绝类别。Update 完整复制原精度命题与 Final 输出答案投影是两个不同责任。

## 3. 公开 Final 合同

新增 `finance_qa_final_public_contract.v1`，每次实际 Request 同时提供 `public_final_contract` 与细化的 `response_schemas.final`。

| 项目 | 新的完整公开要求 | 当前公开信息来源 |
| --- | --- | --- |
| kind | 固定 final | 专用 Schema |
| state_id | 原样使用本次 Request 的 State ID | /state/id |
| answer_claim_id | 选择当前允许的、已接受的 percent Claim | /final_claim_ids 与 /state/accepted_claims |
| result | 仅 value、unit 两个字段，不复制其他 metadata | 结果子 Schema |
| value | 字符串；按 precision=50、ROUND_HALF_EVEN、0.000001 量化，恰好六位小数，不附百分号 | 所选 Claim 的 /proposition/output/value 和 /context/numeric |
| unit | 精确字符串 percent | 公开常量 |
| citations | 唯一字符串列表，集合精确等于所选 Claim 的实际 Evidence lineage | 所选 Claim 的 /proposition/lineage |

合同提供字段类型、来源路径和变换规则，不选择具体 Claim，不预填 State／Claim ID，不提供三个题目的计算结果，也不生成填好的完整响应。原来源独立核算要求明确保留。

基本提交解析语言仍为原 v2：原 parser 不变，实际 Final 准入和原严格验证函数不变。这里新增的是有独立版本与身份的应用级公开约束；其身份另行进入新 generation condition、Request 和测量适用合同，不能因基础 protocol ID 未变而声称旧、新呈现完全相同。

## 4. 只诊断，不代写的反馈

新反馈保留原先实际触发的 error_code，并提供有限的 public_diagnostic：

- result 多字段／缺字段：列出 extra_fields／missing_fields。
- value 类型或量化形态不符：指出要求字符串、六位形式与现行量化规则；若已是六位但不等于所选 Claim 的投影，报告 mismatch，不给替代值。
- unit 不符：指出允许的 percent 常量。
- citations 不符：相对所选答案 Claim 的当前 lineage 给出 missing_ids／extra_ids／duplicate_ids。
- Claim 或 State 绑定不符：指向当前允许答案集合或本次 State 路径。

诊断只读取当前 Request 与本次提交。反馈不调用金融 Operation executor、来源答案 verifier 或 Runtime，不生成替代 Final，不改原响应，也不自动产生下一步修正。原始结果只有通过下一次新的模型提交才能改变。

先在 current_state 或 accepted_answer Gate 被拒的提交，不再冒称随后执行过 Final QA。若未知错误超出有限诊断域，保留原错误而非伪造原因。

## 5. 精确接线与严格标准不变

新增 `FinalPublishedShareTaskAdapter` 只提供明确的 publication opt-in，不覆盖来源构造、Context、registry 或 Final verifier。三个原 Task／Context／Evidence／source binding／语义合同与 registry 身份保持不变。

共享核心仅修改三个位置：

1. Runtime Request 构造在 opt-in adapter 下发布 Final 合同。
2. 独立只读审计的 Request 重建以相同规则发布同一对象。
3. 反馈路由只将新呈现下的 Final 分派到专用诊断；Action／Update 的原规则和内容不变。

原 `PublicQARuntime._admit`、独立 `_admission`、解析器、数值投影与 `BoundShareTaskAdapter.verify_final/verify_execution` 的源码片段逐字核对不变；不把三处有意接线改动描述为全部旧源码未改。

## 6. 冻结来源与十二个只读就绪状态

直接从上一轮已封存的 source_report、condition、session 与 qualification 恢复原三个 source 对象，不扫描 FinQA Archive，不重选来源、期间或指标。使用原污染登记；仍是开发任务，无已绑定独立评价集。

| 新总体任务 | 原来源与期间 | 新完整会话 |
| --- | --- | --- |
| T01 | UNP/2016/page_52.pdf-1，实际 2016 列 | T01_N01、T01_E01 |
| T02 | JPM/2014/page_70.pdf-1，实际 2014 列 | T02_N01、T02_E01 |
| T03 | JPM/2015/page_82.pdf-1，实际 2015 列 | T03_N01、T03_E01 |

就绪状态只用于本地接收端控制。对旧十二会话统一选择：首次接受 percent Claim 后、第一次准备提交 Final 的原 Request。保留其原 session／qualification／event／State 身份及哈希。旧失败前缀实际分母为 D 7、R 5；这不是十二条有效支持。

本地接收端只根据新公开合同中的路径、类型与转换构造控制响应，再交给原严格 Final Gate。四组控制分别是：

| 组 | 控制边界 |
| --- | --- |
| 合法投影 | 正确字符串、单位、恰好两个结果字段、实际 lineage |
| 结果对象与数值表示 | 额外 metadata、缺字段、JSON number、未量化、错误 unit 等 |
| 实际支持 | D/R 引用替换、missing、extra 可见但未用的 Evidence、重复引用 |
| 当前状态与答案绑定 | 已接受但不是允许答案的中间 Claim、错误 State ID |

同一控制对原 Request 和新 published Request 分别调用原 Gate，核对接受／拒绝边界不变。该过程只使用普通只读 view，不创建 Runtime、不执行旧 Operation、不调用历史 qualifier、不回写旧记录。准备阶段正式执行一次控制集，在线前回读只验证封存记录，不重复运行该控制集。

## 7. 六个全新完整会话与固定预算

每任务 N/E 各一个，从独立初态开始；旧 accepted Claims 与本地控制响应不作前缀、示例或新数据。显示标签可与历史标签重名，但新 condition、configuration 与 registration 生成独立 session ID。

N 与 E 沿用既有精确 system prompt 和采样参数；E 仍只是软重建偏好。合法的 E-D 与 N-R 都可以 Qualified，不预分配支持路线。教师配置仍为 deepseek-v4-pro、thinking disabled、temperature 0.7、top_p 1、JSON object、非流式；实际响应身份与 usage 单独记录。

固定一波六个并发会话，注册顺序为 T01_N01、T01_E01、T02_N01、T02_E01、T03_N01、T03_E01。不按结果调整成员、任务权重或调用上限。

| 资源 | 上限 |
| --- | ---: |
| 任务／会话 | 3／6 |
| 每会话 Action | 12 |
| 每会话 Submission／Provider attempt | 32／32 |
| 总 Provider attempts | 192 |
| 单次 completion | 8,192 |
| 单次 HTTP body | 98,304 bytes |
| 单次 reserved allowance | 107,520 |
| 总 reserved allowance | 20,643,840 |
| 原样监督序列 | 32,768 |
| 重试／回退／失败替换 | 0／0／0 |
| Student 更新／GPU | 0／0 |

192 是硬上限，不是调用目标；有效 Final 后立即停止。错误后的新模型提交不是网络重试。普通失败和 unknown 均保留原分母；已有 execution 目录禁止在线 resume。旧主线仍暂停。

本轮没有同期旧呈现对照。旧 0/12 与新结果可作时间分隔的描述性对照，不能给出精确的呈现修复因果增益。

## 8. 完整结果、首次 Final 与商测量分开

每任务分母为 2，每 profile 分母为 1，面板保持 μ=1/3：

```text
q_i,N = m_i,N / 1
q_i,E = m_i,E / 1
q_i = (m_i,N + m_i,E) / 2
q_panel = (q_1 + q_2 + q_3) / 3
u_i(z) = n_i,z / 2
π_i(z | success) = n_i,z / (m_i,N + m_i,E)
```

unknown、not_started、未映射有效质量继续分开。零成功时 π=null；有未定有效投影时也不对可映射子集偷偷重归一化。

每会话另外保存三个推进位置：

1. 真实模型 Update 是否接受 percent Claim及其原事件、Claim 身份。
2. 首次 Final 的原提交与回执是否合格；后续修正成功不改写首次失败。先前 raw 无法分类时保守保留首次指标未知。
3. 最终是否 Qualified；局部字段正确率不能替代完整任务成功。

只在同任务 Qualified 子集中比较，每任务最多一对，总最多三对。原参数化商规则 `922cd2d213677fb9f8d0f1be3695b13e4da0896104ecbe8313aa800c4ecc3a84` 原样复用，另冻结绑定新 Final 公告的 measurement_application；不扩事件归约域以适配结果。

每条实际 saved event Request 的 Final contract 与完整专用 Schema 都核对一致，再调用原投影逻辑。若新的有效纠正过程超域，保留 Qualified 与 projection undetermined 的区别。类身份仍绑定当前 Task／Context／生成条件，不按 N/E 或 D/R 标签预分配，也不跨任务合并 π。

某任务只有两条有效 D，或完整行为虽有多个类但支持机制相同，均不建立 D/R 见证。W_i 要求实际有效 D/R 加确定的完整语义分离；它不是工作流通过条件。

## 9. 新正向材料与评价边界

仅新 Qualified 会话的全部 admitted 原响应进入正向候选，真实 HTTP 中新增的 Final 说明、当前 State、反馈与实际 N/E prompt 原样保留。目标不清洗、不截断、不重写；32,768 Token 政策和同一 tokenizer 资产不变，完整包按所有 admitted events 判定。

无 Qualified 时导出为空、正表示不作通过结论；不对旧失败前缀重新分词。保留类成员的 profile/config、投影、完整包与目标 Token 引用，但不实施 Mψ 权重、Contribution 或 Student 对比。

旧来源污染与事实重叠政策原样保存。当前没有独立评价任务绑定，本轮不能称为盲评或一般金融泛化验证。

## 10. 验证、历史完整性与执行入口

局部验证只针对新 Final 公开合同、十二状态只读控制、新六会话人口、首次／最终指标与导出接线，不重跑旧整套校准。构造 HTTP 与内存 tokenizer 联测明确不是真实 Provider 或生产长度结果。

冻结前汇总检查为 **65 项新测试通过，22.96 秒**：Final 公开合同 15、来源／只读控制 20、计划／runner 21、分析包装 9；Ruff 与按项目配置检查的 18 个相关源码文件 mypy 均通过。完整六会话构造 HTTP 联测使用 37 个构造响应，保留一次首 Final metadata 拒绝后新提交成功，首次 Final 5/6 与最终 Qualified 6/6 没有混淆；这些数字不是正式模型结果。六个新初态 HTTP 请求都包含 Final 公告，最大 54,280 bytes。

十二状态控制集有 156 个构造控制：合法投影与引用顺序 24、结果表示反例 60、支持反例 48、Claim／State 绑定反例 24。24 个合法控制、132 个拒绝控制均符合预期；旧／新 Request 呈现分别通过同一个原准入函数，共 312 次只读准入、264 次原严格 Final verifier 调用。前置 Claim／State 拒绝不会被重复计为调用过 verifier。它们不改变历史 0/12，也不增加模型样本。

十一历史工件前缀共 21,269 文件、980,870,310 字节保持与实验保存锚点 `7a750ad92dd91601461161b53ab686c6bf3eeff8` 的 Git blob 相同。旧 src 的 932 个 Python 文件中只允许上述三个 publication 接线文件变化；其余 929 文件逐字不变，并独立核对八个原严格逻辑函数／方法片段未改。

完整新实现必须先 Git 提交；正式准备绑定全 src、软件、源对象、十二只读状态与控制、Final 公告、原商规则／新适用合同、六登记、初始实际 HTTP、Token 资产与政策。在线前再读回全部冻结身份；正式新 worker 只资格核验一次，后续直接读取保存结果，不重放资格或金融执行。

```bash
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_final_publication prepare
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_final_publication run
```

新目录：`artifacts/qa_vnext_final_publication/final_publication_v1_20260907`。以上设计在真实采集前冻结；实际一次性运行结果记录如下，未补样到成功或双支持。

## 11. 正式完整结果与首次 Final

源码冻结提交为 `29b152635088819d580ef6d2273b135825e12966`，直接 Git 父为 `69a0a6fd2b6c7fa42b86db8c4c4b55d8cd757a09`。实验历史保存锚点仍为上一轮结果提交 `7a750ad92dd91601461161b53ab686c6bf3eeff8`，不混淆实际 Git 祖先与实验历史对象。

正式 prepare 成功后只启动一次六会话完整 run。六会话全部成功，共 **51 次 Provider attempts／Runtime submissions**，远低于 192 的硬上限；未重试、回退、替换、补样或恢复旧会话。

| 任务 | N 的 q | E 的 q | 任务 q | 新 N 实际支持 | 新 E 实际支持 | 任务内类数 | W_i |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| T01：UNP 2016 | 1/1 | 1/1 | 2/2 | R | D | 2 | true |
| T02：JPM 2014 | 1/1 | 1/1 | 2/2 | D | R | 2 | true |
| T03：JPM 2015 | 1/1 | 1/1 | 2/2 | D | R | 2 | true |

面板在固定 μ=1/3 下为 `q=6/6`；known_failure、unknown、not_started 均为 0。所有资格记录的 qa_valid、trajectory_valid、end_to_end_success、evidence_complete、model_origin_verified 与 qualified 均为 true。旧十二会话仍为 0/12，不进入新分母。

A/U/F 表示实际 Action／accept Update／准入 Final；步骤从 1 起：

| 会话 | 调用 | A/U/F | 未准入 Action | percent Claim accept | 首次 Final | 最终 Qualified |
| --- | ---: | --- | ---: | --- | --- | --- |
| T01_N01 | 12 | 3/3/1 | 5 | T11 | T12，通过 | true |
| T01_E01 | 7 | 3/3/1 | 0 | T6 | T7，通过 | true |
| T02_N01 | 9 | 3/3/1 | 2 | T8 | T9，通过 | true |
| T02_E01 | 8 | 3/3/1 | 1 | T7 | T8，通过 | true |
| T03_N01 | 8 | 3/3/1 | 1 | T7 | T8，通过 | true |
| T03_E01 | 7 | 3/3/1 | 0 | T6 | T7，通过 | true |
| 合计 | 51 | 18/18/6 | 9 | 6/6 | 6/6 首次通过 | 6/6 |

`51 = 18 Action + 18 Update + 6 Final + 9 未准入 Action`。没有未准入 Update 或 Final。**首次 Final 全通过不等于全程无纠错**；前序九次 Action 拒绝全部是 `admission.public_judgment`。

三个任务的最终 value 分别是字符串 `"93.280177"`、`"53.681864"`、`"53.486632"`，unit 均为 `"percent"`。六个原始 result 都恰好只有 value/unit，citations 唯一且精确等于所选已接受答案 Claim 的真实 lineage，State ID 与本次请求一致。Host 未重写这些响应。

逐会话证据及三个推进位置见[正式报告](../artifacts/qa_vnext_final_publication/final_publication_v1_20260907/execution/report.json)和[实际进展](../artifacts/qa_vnext_final_publication/final_publication_v1_20260907/execution/analysis/actual_progress.json)。例如 T01_N01 的[原始首次 Final](../artifacts/qa_vnext_final_publication/final_publication_v1_20260907/execution/sessions/T01_N01/runtime/turns/011_response.txt)与[对应公开请求](../artifacts/qa_vnext_final_publication/final_publication_v1_20260907/execution/sessions/T01_N01/runtime/turns/011_request.json)均已保存。

## 12. 呈现、反馈与因果解释

只读逐字对照确认，51/51 实际 HTTP 请求的 user 内容等于对应原公共 Request，system 内容等于相应 N/E 的冻结 prompt；每个 Request 都包含与准备工件相同的 Final contract 和完整专用 Schema。新增说明并非只存在于离线文档或准备副本中。

本轮六次 Final 都首次准入，**在线 Final 专用 public_diagnostic 实际触发 0 次**。九次真实拒绝的诊断均来自原 Action 合同。不能声称“新 Final 反馈促成了这六条轨迹的实际纠错”。

Final 诊断分支的功能证据来自封存的本地控制：132 个负控制中，108 个触发 final_qa、12 个触发 final_accepted_claim、12 个触发 current_state；24 个合法控制无需拒绝诊断。这与真实模型结果是不同证据层。

旧条件 0/12 与新条件 6/6 是两个不同批次的观察。没有同期旧呈现对照，也未证明远端权重快照固定，因此不报告“呈现修复造成了某个精确百分比的因果改善”。本轮直接支持的是：在实际完整公开的 Final 条件下，三个任务均出现了从初态完成的模型可达见证。

## 13. 原规则下的纠正历史与正式分区

原资格记录的直接 domain projection 仍保留 **4 undetermined／2 supported**。四条未定原因均为 `reject_or_unadmitted_effect_not_quotiented`，原 qualifier 的 quotient_assignment_id 仍为 null。它不否定 Qualified，也没有被本轮改写为已经有类。

本轮随后调用的、预先冻结的纠正感知商规则没有变化：原规则 ID 仍为 `922cd2d213677fb9f8d0f1be3695b13e4da0896104ecbe8313aa800c4ecc3a84`。新独立投影结果是 **6 supported、0 undetermined、6 Assignments、6 个 Task／Context 绑定的有限类**。

九个未准入事件按已有适用域保留为四段关系：

| 会话 | 原步骤 | 被拒公开判断字段 | 既有规则给出的保留解释 |
| --- | --- | --- | --- |
| T01_N01 | T1–T5 | /decision/basis | 未准入 D 提议后，真实 sum、accept total Claim，随后 ratio 实际使用 R |
| T02_N01 | T1–T2 | /decision/obligation_id | 最近实际执行 sum 并接受结果，之后 ratio 仍使用披露 Evidence；sum Claim 无实际消费者 |
| T02_E01 | T1 | /decision/obligation_id | 未准入 D 提议后转到真实重建与消费链 |
| T03_N01 | T1 | /decision/basis、/decision/obligation_id | 先实际 sum／accept，之后仍实际使用 D，保留未消费 Claim |

九条完整 ledger 的 disposition 都是 `retained_behavior_relation`，errors 为空。重复提议次数的有限归一化不删除原始事件、反馈或预算记录。未准入提议没有被伪装成已执行 Action；顺序关系与实际数据依赖仍分开。

三个 D 会话也都真实执行过 sum；六个会话的 Action 数都等于 3。因此 D/R 差异**不是多做一步运算造成的标签区别**，而是后续 ratio 是否真正消费 accepted total Claim。R 的结构／语义依赖深度为 3，D 为 2；可观察选择依赖深度分别为 2／1，这些是实际图指标，不是模型内部思维深度。

三对同任务比较均为 `not_equivalent`、proof_verified=true；独立的 execution_support_contrast 均确立真实 denominator Evidence 与 accepted relation_sum Claim 的生产—消费差异。跨任务比较为 0。

| Task | 同任务配对 ID 哈希 | 实际分母差异证明 ID 哈希 |
| --- | --- | --- |
| T01 | `2aee1d47bf2d7d135b8d4e7c1b77b0b1c020f7f0dde323c05972eba01bd19d78` | `3006acda8ad495043920f48ab28d41f38fbd3d57c9b86937af763907873182e1` |
| T02 | `9696203ff106de7558567667cb25648c595eedbaeab367543078dd26dadc0deb` | `da4d73a6d862bf77eb4c2e6d2510f5e14b2e9fe318d5dac6a5c549de86666cab` |
| T03 | `3b2759aa8cfbbdfc4f3ba90c73e17040b552e847ff36d591778f16873afaba4d` | `02b94a1bfb0b798617dacec12309d31f24b17247a3ead33d63af31e8d3d77c29` |

完整图、逐事件解释、原 domain 层与新商层身份分别保存在[新投影](../artifacts/qa_vnext_final_publication/final_publication_v1_20260907/execution/analysis/projections.json)及[正式有限测量](../artifacts/qa_vnext_final_publication/final_publication_v1_20260907/execution/analysis/measurement.json)，没有在看到结果后扩展归约规则。

## 14. 三个任务内的分布与材料身份

每任务当前两类各一个成员，`u_i(z)=1/2`、`π_i(z|success)=1/2`；N/E 成功条件权重也各为 1/2，是本批每层一个成功的结果。三个任务各自的 π 完整闭合，不合并成一个跨任务条件分布。

面板质量为：

```text
mapped valid 6/6 + unmapped valid 0/6 + failure 0/6 + missing 0/6 = 1
```

六个 `(Task, class)` 的联合频率各为 `μ_i × u_i = 1/6`。D/R 描述性数量为 3/3，但不是两个跨任务通用 State ID。T01 的 N 实际为 R、E 实际为 D，直接说明 N/E 不等于固定支持类型，软引导没有变成资格约束。

| 会话／支持 | 正式类 ID 哈希 | 原样目标 Token 数 |
| --- | --- | ---: |
| T01_N01／R | `b6f932d8729a1a41a5a436eb6a9b7c7b03f7c081947fed369d2eaabd2785b2b4` | 7,212 |
| T01_E01／D | `15cd003efff3407c68f2c140bec80b13422edb009483f823c16554a791e756c0` | 6,432 |
| T02_N01／D | `489294bf754c683ba7dc49383a29e46236dee31efea9c8e785d0e3d3a0a754d1` | 6,362 |
| T02_E01／R | `24b68dca25ddb2634fda6c1db3a0b457d4b0fb6af2ab80cc6fcb1409635d5018` | 7,098 |
| T03_N01／D | `360500df6f7b5a63c5315a90f9d002cc97f10728b2e581656a8be40943e72800` | 6,413 |
| T03_E01／R | `d55cf85083d6c0e77ae35fdd4d45957af595d449ba93d31f1de205738266c2bb` | 7,123 |

类由精确语义配对与差异证明建立，表中的支持描述不是赋类依据。完整类成员记录还引用实际 profile/config、qualification、projection、完整 package 和 Token 数；没有引用旧十二会话或构造控制作为新成员。

## 15. 原样正向表示与执行成本

**42 个原始正候选 = 18 Action + 18 Update + 6 Final**，N/E 各 21。逐条只读对照原传输后确认，candidate.messages 等于实际 HTTP messages，target UTF-8 字节等于原 Runtime response，父 ID、原 raw SHA、byte count 和 admitted receipt 全部匹配。

51 个实际请求中，9 个带有此前拒绝反馈；42 个正候选中，4 个保留此前拒绝反馈。它们是 Action 纠正上下文，不是本次在线 Final 纠正。未准入的九个 Action 响应未被导入正目标，完整公共行为仍在原事件及投影 ledger 中保存。

| 正向表示／CPU 对象 | 实际结果 |
| --- | --- |
| candidate／Token records／fit／not-fit | 42／42／42／0 |
| 序列长度 | 17,080–21,640，均低于 32,768 |
| 截断／目标改写／旧行导入 | 全部 0 |
| 完整监督包 | 6 个，每包 7 个 admitted units |
| 目标 Token 合计 | 40,640 |
| CPU batch | 24：18 个双条、6 个单条 |
| CPU 已加载记录 | 42，batch size≤2 |
| Student 权重加载／forward／更新／GPU | 全部 0 |

原候选／Token 的 quotient_assignment_id 仍为 null，因为原样导出与表示先于独立投影；正式类与包的关系在测量 sidecar 中建立，不回写原始候选。42 条 Token 和六个 package 的原父链、class member package ID 与目标 Token 汇总一致。

40,640 是冻结监督 tokenizer 与掩码政策下的目标计数，不等于 Provider completion usage。表示与 CPU 加载已通过，不代表 Student 效用、训练可行性或 GPU 显存可行性通过。

[新候选](../artifacts/qa_vnext_final_publication/final_publication_v1_20260907/execution/analysis/supervision_candidates.json)、[Token 数据集](../artifacts/qa_vnext_final_publication/final_publication_v1_20260907/execution/analysis/token_representations.json)、[完整包](../artifacts/qa_vnext_final_publication/final_publication_v1_20260907/execution/analysis/session_packages.json)和[CPU 记录](../artifacts/qa_vnext_final_publication/final_publication_v1_20260907/execution/analysis/cpu_loading.json)分别封存。

| Provider 资源 | 实际值 |
| --- | ---: |
| attempts／submissions | 51／51 |
| 最大 HTTP body | 58,890 bytes |
| 已用 reserved allowance／上限 | 5,483,520／20,643,840 |
| prompt_tokens | 801,794 |
| completion_tokens | 38,012 |
| total_tokens | 839,806 |
| cache-hit／cache-miss tokens | 334,464／467,330 |
| reasoning_tokens | 全部 51 条未提供，observed_total=null |

上述五个已知 usage 字段各有 51 条完整记录。reasoning usage 未知，不能按 thinking disabled 配置补成 0；reserved allowance 不是实际 Token 或货币账单。51 个原 outcome 都是 deepseek-v4-pro／public_content／finish_reason=stop，host_repairs 与 condition_flags 为空。模型别名不证明远端权重快照固定。

## 16. 封存身份与收口

| 对象 | ID 哈希部分 |
| --- | --- |
| 新生成条件 | `7f104964cad3808ed037eb5a32369f9a39b5c461794e4b50b388affc5b19793c` |
| Final 公开合同 | `83b6f2c7ad0f18c9225cb71e44eed9086eb610be63f4c43adaf09f5488b30801` |
| 测量适用合同 | `09870d7986fa72244a8c7345d21e1a034f773841ef50ce35792a72c1a33459ca` |
| 比较合同 | `52acfacb599ed574fa5a17cbdbdc67bf67ae64d0942ba6cfe703c184e5a39443` |
| 十二状态只读控制 | `6a6e4ed48338cd751767949a724de48bd7006816b3333387d25c651a1c973d20` |
| 准备 manifest | `a5dfd63658706df25a8de01e1acde312c6fa073d9f8774c8a85221fbb515899f` |
| 执行 manifest | `e0f13c8f7412faa36ba3aa592156893f93726e3f98f9d16db99ef4fd192a19d1` |
| 分析 manifest | `3203cc4295e7ad5b73b5b77cca0936f066c6e73b06145311e4065a665de4fad2` |
| 正式报告 | `80e7b6fcca2683b320e6189ec62a4de54182c60b7fca81fd663f94728fe2f054` |
| 有限测量 | `58fd1f0729f7c5f85808f51f8a3621063daad97940af5f7499bcf6db871f9475` |
| Token 数据集 | `dc2816f7e5efd8cb69e9251bba7957438efccd3e23882321749ae974fb84e3d9` |
| 六个完整包的集合 | `20f4d38f667d305c3b0a03c0b85c1579b4962b59ecabf0641fe32f9e9c2d678d` |

正式目录共 **909 个文件、57,424,499 字节**；最大文件是 10,411,959 字节的 Token JSON。准备 manifest 有 36 个成员、10,816,832 字节；执行 manifest 有 870 个成员、46,459,405 字节；分析 manifest 的 44 个成员已包含在执行树中，不重复相加。

在线与分析后只做封存字节、父身份及统计回读，没有重新资格、重新投影或重新分词。旧 21,269 文件／980,870,310 字节保持不变；全 src 冻结快照为 947 个 Python 文件。三处旧核心发布接线与所有新增源码在首次新响应后均未再修改，原严格函数体保护和阶段 guards 均通过。

**本轮可以关闭这三个开发绑定上的 Final 完整公开与完整执行接入问题。** 同时在不扩商规则的条件下，三个绑定均得到实际有效 D/R 分离见证和完整有限经验分布。这里的六会话成功、三个严格见证与 42 条原样表示是分别检查的结果，未相互替代。

本轮没有新增来源、同期旧呈现对照、独立评价任务、Student 训练、Contribution 或 VTDO 更新；仍不能称为一般金融泛化或训练效用验证。各类当前只有一个观察成员，复制不会增加独立样本。旧 0/12 与既有 UNP/2015 结论不改写，旧主线继续暂停；后续评价与训练干预须另行固定对象和范围，不在本轮自动启动。
