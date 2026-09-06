# 修复公开呈现下的六个完整代表任务会话

日期：2026-09-06。阶段：`finance_qa_vnext_repaired_update_six_session_full_task_pilot`。

## 1. 授权、前序结论与本轮问题

用户本轮指令为“参照审计继续实验”。审计明确关闭此前 Update 公开缺口，要求直接进入原 C/B/S 三个任务各两个全新完整会话。本轮不增加相同单步校准、不重开来源或 Registry 审计，不启动旧主线或 Student/GPU 训练。

前序提交 `140c012a55f04c0f4ffc6f22d6128cc2790eb3cd` 的结论保持不变：历史完整会话 1/12；随后指定 accept 的单步配对 O 0/12、R 12/12。它们与本轮分母、生成条件、工件完全独立，不能合成一个成功率。

本轮只问：给定原公开任务计划及合法候选，在修复后的公开合同和有限反馈下，模型能否从初始 State 完成 Action、显式 Update commit、实际 Claim 消费及有效 Final？这是条件内选择与执行，不是自主发现全部计划，也不是通用推理能力或训练效用实验。

用户审计原文作为 preparation/experiment_design.txt 保留原始字节：24,739 bytes，SHA-256 `08cb42f52e679c5ebb4b6646a03003bb69174b57a0e5f006cb4b6a6f75778042`。

## 2. 调用前冻结的总体与停止边界

| 项目 | 冻结值 |
| --- | --- |
| 任务 | 原 C 注册跨指标比较、B CDW FY2015/FY2016 分支合并、S 部分/整体占比 |
| 会话 | C01/B01/S01，随后 C02/B02/S02；新 condition 与 session 身份 |
| 调度 | 两轮，每轮按 C/B/S 登记启动，并发最多 3；下一轮等待本轮结束 |
| 初态 | accepted Claims=[]，pending Observation=null，各计数 0，反馈 null |
| 每会话 Action / Submission / Provider attempt | 12 / 32 / 32，Submission 含 Final |
| Provider attempt 总上限 | 192，不重试网络、不回退、不替换失败会话 |
| 教师生成条件 | deepseek-v4-pro，thinking disabled，temperature=0.7，top_p=1.0 |
| 输出 | 单一 JSON object、非 stream、max_tokens=8192 |
| 请求限制 | 完整 HTTP body 98,304 bytes；输入准入代理为 body bytes+1024，上限 99,328 |
| allowance | 每次 107,520；每会话 3,440,640；全体最多 20,643,840 |
| HTTP 时限 | 总 deadline 180 秒，连接 deadline 30 秒 |
| 科学见证条件 | 三个任务各至少一个有效完整 Qualified 会话 |
| 工作流完成 | 证据完整、分母及原样评分正确；不要求 6/6 或 Share 两条路线 |

实际请求采用原完整任务的中性 SYSTEM_PROMPT，允许当前阶段合法 Action、Update accept/reject 或 Final；不使用校准的 configuration()、accept-only 指令或一次调用限制。保留 `finance_qa_public_decision_protocol.v2`、`finance_qa_update_public_contract.v1`、真实反馈以及所有数值、来源、State、Claim、Final 检查。响应字段由模型填写，Host 不修复、不补字段、不替换失败响应。

有效 Final 立即终止；32 是上限，不是必须用满的目标。公开拒绝之后的纠正是新的真实模型提交，计入预算，旧响应保持原样。完整记录的超时、无内容及资源终止按照现有资格器判断 known_failure；工件缺失、内部异常或无法确定终止保留 unknown，并暂停未开始的下一轮。不把 unknown/not_started 写成失败，也不删除后归一化。已启动的本轮会话仍保留其完整或部分证据。

## 3. 实现与零调用衔接检查

新增模块 `experiments/finance_qa_vnext_repaired_full_task/` 单独登记六行、两轮和 192 上限；不修改原十二会话模块、校准执行模块、领域 Runtime、协议或独立准入器。共用既有单会话 `_run_session`、真实 OnlineModelCallback、传输持久化、独立资格器、Share 支持回溯和原响应导出器。原有底层 wire record 身份继续用于严格资格验证，但新 condition、run tag、session ID 和执行目录与旧总体分开。

prepare 要求全部 Python 实现已提交；读取既有 TaskPanel 时只保留原三个 Task/Context/Evidence/Operation 绑定，coverage 中每个选定任务登记数改为 2。冻结原始设计、实现 Git commit/tree/全部 Python 字节、软件版本、生成配置、六行 manifest、六份初始 Request/HTTP、tokenizer-only 资源及两棵旧实验工件完整清单。

新增离线检查只覆盖：

1. 三个真实 Runtime 的初始 request 与独立重建的冻结初始 request 一致；空 Claim、无 pending、12/32 边界、公开规则及完整任务指令正确。检查不调用 callback 或 Runtime.run。
2. 读取既有完整 B、Share disclosed/reconstructed fixture 的已保存 Request，补上公开规则后，通过隔离公开表达式解释器构造局部 accept/reject，并交由原 `evaluate_update_readonly()` 判定。共 13 个既有 Observation × 2 disposition=26 个接线控制，覆盖 lookup、growth、signed_percentage_point_gap、absolute_percentage_point_gap、relation_sum、share_ratio、scale_percent。
3. 本地模拟 HTTP 练习完整六会话 Runner、已知失败继续、unknown 暂停下一轮、纠正与合法 reject 的保存、原响应导出、真实 tokenizer-only 及无网络/无执行器的重分析。模拟数据只存在测试临时目录，绝不是 Provider 样本。

这些控制不重新执行历史财务 Operation，不从中创建在线前缀，也不复验前序 118 项闭合审计。首次开发测试发现新 progression 读取 Final 字段时混淆了模型顶层 `answer_claim_id` 与 Host 保存包装，以及操作名称测试预期拼写不符；在真实调用前修正。初始失败测试输出保留，不作成功证据。

## 4. 主结果与推进位置

会话成功指标仍是有效 Final ∧ 独立 QA 验证 ∧ 轨迹验证。每任务固定分母 2；六个指标全可判定时等权任务均值=成功数/6，否则完整均值为 null，仍报告每个任务的成功数、known_failure、unknown、not_started。

每会话新增 progression：首个实际准入并执行的 Action；首个实际 accept commit 产生的 Claim；后续实际 Action 或有效 Final 对 Claim 的消费；完整成功；第一个实际拒绝或终止证据。C 的 Claim 可直接由 Final 消费，不强行增加 Action。首个拒绝可被后续纠正，不等于会话最终失败。

Observation 单独列行：创建次序、操作/义务、pending 期间所有模型提交数、第一次 pending 提交是否准入、第一次结构解析为 Update 的提交是否准入、最终 accept/reject、首次拒绝条件、committed Claim 与后续真实消费者。结构错误不伪装成一个已解析 Update，但计入处理该 Observation 的提交数。同一 Observation 的多次纠正不是多个独立任务。

另从实际 HTTP body 解析中性完整任务 SYSTEM_PROMPT 和公开合同，验证 body user Request 与已绑定 public_request 一致、首次实际 Request 与预冻结初态一致。规则出现而模型违例，和接口未发送规则，必须分别报告。

深度直接复用实际事件导出的结构依赖深度、语义操作深度、可观察选择依赖深度及其 scope；完整会话与失败前缀分开，不将 Update 次数或错误纠正当作深度。coverage 仍为三个选定类型、五个已有来源但本轮未测量类型、三个来源未实例化类型。不同任务的成功差异不是深度因果效应。

## 5. 附加测量，不增加模型接入门槛

Share 只从有效 Final Claim → scale_percent → share_ratio → 实际 denominator 回溯。若 denominator 为 Claim，还需它来自真正执行并被接受的 relation_sum；仅调用过 sum 不构成完整重建支持见证。无有效完整会话时不猜支持方式。

每任务两个会话，最多 3 个同任务无序配对，仅对真实 Qualified 会话交给既有有限投影比较。纠正/reject 可以 Qualified=true 而 projection_status=undetermined。不构建一般 Mapper、不要求两类、不继承旧 Assignment、4/5:1/5 或 P/Q 权重。

仅从完整 Qualified 会话导出真实请求—原样准入响应监督候选；未准入提交、失败前缀、历史响应与 24 次单步响应均不进入正向池。沿用冻结 tokenizer-only 和 24,576 Token 限制；过长保留原候选及长度诊断，不截断，不回写轨迹失败。空导出不能声称正向表示验证通过。不加载 Student 权重，不训练，不使用 GPU。

## 6. 可复现入口与工件

仓库根目录使用现有虚拟环境与 PYTHONPATH：

```bash
PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python \
  -m trusted_synthesis.experiments.finance_qa_vnext_repaired_full_task prepare \
  --root "$PWD" --preparation /absolute/new-run/preparation \
  --design /absolute/pasted-text.txt --run-tag repaired-six-20260906

PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python \
  -m trusted_synthesis.experiments.finance_qa_vnext_repaired_full_task run \
  --root "$PWD" --preparation /absolute/new-run/preparation

PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python \
  -m trusted_synthesis.experiments.finance_qa_vnext_repaired_full_task analyze \
  --root "$PWD" --preparation /absolute/new-run/preparation --output /absolute/new-reanalysis
```

准备与运行目录均不得已存在。run 在检查已有 execution 后才读取 `.env`；不允许 resume 或再次执行同一总体。分析不得写入已封存 execution。所有 HTTP 原始 body、响应文本、Usage（缺失为 null）、请求/响应/Submission 父链、Runtime 事件、资格报告及导出文件均按既有耐久协议保存并封存。

## 7. 实际执行结果

### 7.1 冻结身份与总体结果

本轮已完成，停止于登记的六个会话，没有补采样。实际实现冻结提交为 `1d4a7c87eb90e363273479946755ea72b55655e5`，绑定全部 863 个 Python 源文件；初版实现提交为 `611d2c47`，随后在真实调用前修正 CLI 的 prepare 导入并加入真实 CLI 往返测试。运行之后没有更改实现或准入标准。

工件根目录为 `trusted_data_synthesis/artifacts/qa_vnext_repaired_full_task/finance_qa_vnext_repaired_update_six_session_full_task_20260906/`。以下相对路径均从该目录开始。

- Condition：`qa_vnext_model_execution_repaired_full_condition:0b61c1cc591eef74bc5f994870dc8fd57c71397804e608907be383bd103bb063`。
- Preparation：`qa_vnext_model_execution_repaired_preparation:d24018efe52f6e3b0345532bb8b30391bd14b7f8c43fcbbf91da384f0eaca500`。
- 实际报告：`qa_vnext_model_execution_pilot_report:69d985855ec1f139d1e4664ad37ccac03e8aef0cd829baaa0418e0c3dfd1430b`。
- Execution manifest：`qa_vnext_model_execution_execution_manifest:2940f50b0c736c60866e03ab96f3077a41250f64e1ce9682b3d1b25108241302`。

| 任务 | 完整成功 / 固定会话数 | known_failure | unknown / not_started | 本轮完整成功比例 |
| --- | ---: | ---: | ---: | ---: |
| C | 2/2 | 0 | 0/0 | 1 |
| B | 0/2 | 2 | 0/0 | 0 |
| S | 2/2 | 0 | 0/0 | 1 |
| 总体 | 4/6 | 2 | 0/0 | 2/3（66.67%） |

六行证据均完整且可判定，执行测量工作流完成；但“三个任务各至少一个完整见证”的科学条件尚未满足，仅 C/S 两个任务获得见证。B 两行都因 `submission_budget_exhausted` 终止。不能据此宣布三个任务的完整模型接入问题全部关闭，也不能把 B 的失败改成模型数值推导错误：实际尚未进入增长和合并运算。

共 116 次真实 Provider attempt/Submission，全部返回 `deepseek-v4-pro`，全部通过 JSON/结构 Schema。实际 HTTP 请求均包含完整公开 Update 合同和中性完整任务指令；六个首请求逐一匹配冻结的真实初态。未观察到身份/生成条件偏离、HTTP 失败、未知终止、自动网络重试、模型回退、Host 响应修复或会话替换。

### 7.2 实际推进位置

以下 T 是从 1 起算的模型提交序号；原 JSON 中 sequence 从 0 起算。

| 会话 | Provider / Submission | 执行 Action / accepted Claim | 首 Action / 首 accept | 实际后继依赖消费 | 有效 Final | 首个拒绝 |
| --- | ---: | ---: | --- | --- | --- | --- |
| C01 | 3 / 3 | 1 / 1 | T1 / T2 | 首 Claim → Final T3 | T3，Qualified | 无 |
| B01 | 32 / 32 | 3 / 3 | T9 / T10 | 三个 lookup Claim 均未被后继操作消费 | 无 | T1 alternative_set |
| S01 | 14 / 14 | 3 / 3 | T5 / T6 | 首个 total Claim 未使用；ratio → scale T10；percent → Final T14 | T14，Qualified | T1 public_judgment |
| C02 | 3 / 3 | 1 / 1 | T1 / T2 | 首 Claim → Final T3 | T3，Qualified | 无 |
| B02 | 32 / 32 | 2 / 2 | T2 / T3 | 两个 lookup Claim 均未被后继操作消费 | 无 | T1 alternative_set |
| S02 | 32 / 32 | 3 / 3 | T1 / T2 | 首个 total Claim 未使用；ratio → scale T5；percent → Final T32 | T32，Qualified | T7 final_qa |

`progress.first_claim_consumption` 特指第一个 accepted Claim 后来是否被消费，不泛指“任意一个 Claim”。因此两个 S 的该字段为 null，但并非整个会话没有 Claim 消费：其后续 ratio 和 percent Claim 构成真实成功依赖链。逐 Observation 消费记录保留这种区别。

### 7.3 逐 Observation 的 Update 结果

13 个新 Observation 均只用一次模型提交完成合法 accept 并实际 commit；首次 Update 合格 13/13，最终 accept 13、reject 0、pending 未处理 0。没有要求模型 accept，这些是本轮实际选择。此处的 13 是动态 Observation 数，不能用作任务成功率分母。

| 会话与 Observation | Action T | 首 Update T | pending 模型提交数 | 最终处置 | Claim 后续消费者 |
| --- | ---: | ---: | ---: | --- | --- |
| C01 registered_compare | 1 | 2 | 1 | accept | Final T3 |
| B01 revenue_earlier lookup | 9 | 10 | 1 | accept | 无 |
| B01 revenue_later lookup | 15 | 16 | 1 | accept | 无 |
| B01 income_earlier lookup | 26 | 27 | 1 | accept | 无 |
| S01 relation_sum | 5 | 6 | 1 | accept | 无 |
| S01 share_ratio | 8 | 9 | 1 | accept | Action T10 |
| S01 scale_percent | 10 | 11 | 1 | accept | Final T14 |
| C02 registered_compare | 1 | 2 | 1 | accept | Final T3 |
| B02 revenue_earlier lookup | 2 | 3 | 1 | accept | 无 |
| B02 revenue_later lookup | 7 | 8 | 1 | accept | 无 |
| S02 relation_sum | 1 | 2 | 1 | accept | 无 |
| S02 share_ratio | 3 | 4 | 1 | accept | Action T5 |
| S02 scale_percent | 5 | 6 | 1 | accept | Final T32 |

每行完整 Observation/Claim ID、Receipt、Submission 及消费者父链见 `execution/analysis/progress/*.json` 和 `publication_validation/observation_rows.json`。所有行的首次 Update 拒绝条件均为 null。

实际 Observation 形态为 comparison 2、lookup 5、sum 2、ratio 2、percent 2；并非全部 B 后续形态均获得模型证据。growth、signed gap、absolute gap 只通过本轮既有完整 fixture 的局部接线检查，实际 B 会话没有执行到这些操作。

### 7.4 剩余阻塞与已纠正问题：只按原始证据定位

| 会话 | Action 候选集合拒绝 | Action judgment 拒绝 | Final QA 拒绝 | Update 拒绝 |
| --- | ---: | ---: | ---: | ---: |
| C01/C02 | 0 | 0 | 0 | 0 |
| B01 | 26 | 0 | 0 | 0 |
| B02 | 28 | 0 | 0 | 0 |
| S01 | 1 | 4 | 2 | 0 |
| S02 | 0 | 0 | 25 | 0 |
| 总计 | 55 | 4 | 27 | 0 |

116 个结构有效提交中，实际准入 Action 13、Update 13、Final 4；未准入 Action 59、Final 27，共 86 次公开语义拒绝。纠正没有被抹去，也没有作为独立会话扩充分母。

**当前阻断 B 完整可达的首个具体点是 `admission.alternative_set`，不是整对象 Update 接受。** B01 首请求给出四个 lookup，模型只列一个候选；B02 首次亦如此。B 的全部 54 次该类拒绝都是遗漏当前可用 ID，没有额外/虚构 ID或重复 ID：

| 会话 | 可用数 / 声明数 / 遗漏数 | 次数 |
| --- | --- | ---: |
| B01 | 4 / 1 / 3 | 8 |
| B01 | 3 / 1 / 2 | 11 |
| B01 | 3 / 2 / 1 | 2 |
| B01 | 2 / 1 / 1 | 5 |
| B02 | 4 / 1 / 3 | 1 |
| B02 | 3 / 1 / 2 | 22 |
| B02 | 3 / 2 / 1 | 5 |

原 Runtime 要求 `candidate_action_ids` 不重复，且其集合等于当前全部 `available_actions[].id`。实际 HTTP 的该字段 Schema 只有 string array、minItems=1 等结构要求，没有明示这个“列全当前全部可用候选”的集合等式；当前新增 publication 又明确只覆盖 Update。源码与实际请求因而支持一个局部 Action 呈现缺口的诊断。这不说明模型的其余 Action 字段必然正确，也尚未验证补充该规则后 B 会成功。对模型为何反复只列子集的内部原因不作推断。

下一项最小修订应限定为公开这一既有 Action 集合约束及其反馈来源，保留原集合等式、不预填响应、不削减可用候选；本轮不在六会话运行中或结果出来后偷偷改变条件，不追加 Provider 调用来追求成功。前序 Update 缺口不重开，来源/Registry/旧 D/S 与权重也不扩展。

S01 首个 `public_judgment` 拒绝可进一步定位为提交中的 obligation_id 和 basis 与其所选公开 candidate 不一致，selection_rule 本身属于所选候选的合法选项；这些错误随后被模型纠正。S 的 Final 问题也与 Update 不同：Update 必须保留完整高精度 proposition，Final 则必须按已有公开数值条件输出投影 `{"value":"93.508458","unit":"percent"}` 并提供精确 lineage citations。

两个 S 的 27 个失败 Final 全部 result 不符合该投影；部分还存在 citation 不符。实际例子包括加入 metadata 外层字段、直接保留高精度值、把字符串改为 JSON number、添加 `%` 后缀或漏 unit。S01 T13 仅 value 仍为高精度，T14 原样新响应才正确；S02 最终 T32 才同时满足 result 与 citation 标准。完整逐 Final 只读验证见 `publication_validation/new_blocker_diagnostics.json`。诊断中的 expected projection 从未回送模型，不能冒充在线反馈。

### 7.5 深度、支持和有限比较

| 会话 | 实际结构深度 | 实际语义操作深度 | 可观察选择依赖深度 | 范围 |
| --- | ---: | ---: | ---: | --- |
| C01/C02 | 1 | 1 | 0 | complete_session |
| B01/B02 | 1 | 0 | 0 | reached_prefix；只有透明 lookup |
| S01/S02 | 2 | 2 | 1 | complete_session |

B 没有真正执行增长分支、合并或 absolute，所以未取得完整语义深度三见证；不能把 32 次提交写成深度 32。任务差异未作独立控制，不能据此声称深度导致了成功率差异。

两个 S 均执行并接受 `relation_sum`，但最终 ratio 的 denominator 都是披露总额 Evidence，不是 sum 产生的 total Claim。因此两个实际 Final 支持均记为 `disclosed_total`，完整重建支持见证为零；这不否定其 QA/轨迹资格，也不能自动将 sum 调用记作第二条完整支持路线。

实际 Qualified 会话仅 C01/C02/S01/S02，形成两个同任务无序配对（不超过上限 3）。C 配对在当前投影下 equivalent；S 配对因为包含纠正，projection_status 与比较关系均为 undetermined。没有 B 配对，没有新商类 Assignment、完整分布或 P/Q 权重。不因 S 的投影未定删除其合格历史。

### 7.6 原响应导出、用量与隔离边界

仅四条完整 Qualified 会话导出 20 条监督候选：C01/C02 各 3，S01/S02 各 7。59 个未准入 Action、27 个未准入 Final 以及 B 的失败前缀全部不进入正向池；历史 12 会话及 24 次校准响应也不进入。纠正提示状态仍保留在真实准入轮次的输入中，不抹去在线反馈历史。

20/20 Token 序列满足 24,576 上限，长度为 15,169–22,952；原响应及目标 mask 按既有导出器校验，没有截断。这个结果只支持当前正向表示可用，不支持 Student 效果。Student 权重加载、forward、训练更新及 GPU 作业均为零。

| 会话 | Prompt tokens | Completion tokens | Total tokens |
| --- | ---: | ---: | ---: |
| C01 | 44,209 | 1,521 | 45,730 |
| B01 | 614,795 | 15,762 | 630,557 |
| S01 | 267,258 | 8,397 | 275,655 |
| C02 | 44,170 | 1,509 | 45,679 |
| B02 | 619,433 | 15,993 | 635,426 |
| S02 | 618,011 | 13,138 | 631,149 |
| 总计 | 2,207,876 | 56,320 | 2,264,196 |

缓存命中 1,650,432 + 未命中 557,444 = prompt 2,207,876。reasoning_tokens 在 116 条 usage 中均缺失，保留 null，不填零。实际 116 次预留 allowance=12,472,320，设计总上限=20,643,840，二者均不是实际 Token 消耗。最大实际 HTTP body 为 69,233 bytes。

本轮最早 reservation 为 UTC `2026-09-06T09:10:53.213437+00:00`，最晚为 `2026-09-06T09:16:37.219145+00:00`；这些是实际预留时间，不冒充完整 Session 起止时间。

### 7.7 复核、开发失败及发布清单

冻结版本的 10 项接线回归及 1 项真实 CLI prepare→读回→六会话模拟 HTTP 往返检查全部通过（11 个不同测试，不是模型样本）。三个真实初态及 26 项后续 accept/reject 接线控制通过。没有重跑上一轮的 118/386 项审计或重新构建来源/Registry。

正式结果之外，两份实际只读重分析均与 `execution/analysis` 的 37 个文件、8,725,792 bytes 完全一致。凭据、Provider、Callback、socket、Runtime 构造及两个财务执行器受到禁止调用保护；完成的顺序复核计数全部为 0。初次并发复核一支在本地导入 AutoTokenizer 时遇到 ImportError，另一支已成功封存；保留成功分支，缺失分支改为顺序执行后完成。并发惰性导入冲突是可能解释，未独立证明；没有更改实验源码、在线轨迹或再次调用模型。

本地发布核对脚本首次把 `host_repairs=[]` 错按数值 0 比较而中断。该错误属于核对脚本，不是在线修复事件；修正为显式检查空数组后通过。首次局部目录完整保留为 `publication_validation_initial_local_failure`。开发初始 6 个测试失败、CLI 导入错误及其修正也保留记录，不计作正式会话失败或成功。

复核验证了 preparation/execution/两份 analysis 下共 24 个递归 manifest；所有 863 个冻结源文件和测试未变，领域中立架构检查 197 个文件、0 个违反。前序两棵实验树的 6,935 个文件、247,761,428 bytes 全部保持冻结时的哈希。实际凭据字节扫描命中为零，无 `.env` 或模型权重进入发布工件。

| 新工件子目录 | 文件数 | bytes |
| --- | ---: | ---: |
| preparation | 94 | 5,574,171 |
| execution | 1,689 | 74,803,595 |
| reanalysis | 37 | 8,725,792 |
| guarded_reanalysis | 37 | 8,725,792 |
| readonly_verification | 4 | 12,868 |
| publication_validation_initial_local_failure | 6 | 46,647 |
| publication_validation | 11 | 177,717 |
| 合计 | 1,878 | 98,066,582 |

最大单文件 5,334,713 bytes。原始设计 CRLF、响应空白及 JUnit 失败消息保持原字节，不为了格式检查而正规化证据。关键复核身份：`repaired_readonly_verification:e7b38170e4aea3f76e4ce39c7f74ec9809bd4c4cfb75061d17ee3cdc67179061`、`repaired_publication_validation:e53a6cd303297c4d1953f55a0a002fe3932c71f0acc95e0d767c1d0aa3d9b6a7`（完整记录的前缀均为 `qa_vnext_model_execution_`）。

## 8. 本轮收口

本轮获得 C/S 的真实 Action→Update commit→后继 Claim 使用→有效 Final 见证，保留 Update 修复的限定有效性；同时接受 B 0/2 的有界负结果。当前主要后续对象已从首次 Update 转为 Action 全候选集合公开条件。只定位这个具体新阻塞，不把 4/6 包装成广泛财务 QA 成功，也不将 13/13 Update 或 20 个 Token 候选替代完整任务验证。

六个登记会话及附加测量到此结束，没有重跑、替换或追加模型调用。旧主线保持暂停。
