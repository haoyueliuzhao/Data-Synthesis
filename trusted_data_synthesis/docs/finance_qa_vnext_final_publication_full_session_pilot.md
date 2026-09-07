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

新目录：`artifacts/qa_vnext_final_publication/final_publication_v1_20260907`。这份设计写入时尚未启动真实模型采集；后续按原固定条件记录全部结果，不补样到成功或双支持。
