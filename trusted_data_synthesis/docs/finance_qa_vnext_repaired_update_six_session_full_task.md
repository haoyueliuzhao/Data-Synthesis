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

调用前版本：实现与边界正在冻结，尚无本轮真实 Provider 结果。本节将在六行执行或显式未启动记录、独立重分析与工件核对完成后填写。不能把本地测试或前序 R 12/12 作为这里的成功率。
