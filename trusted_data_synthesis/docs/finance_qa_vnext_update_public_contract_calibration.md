# Finance QA vNext：Update 条件公开修复与单步配对校准

日期：2026-09-06。阶段：`finance_qa_vnext_update_public_contract_repair_and_paired_calibration`。

本轮已完成：原呈现 O 为 **0/12**，修复呈现 R 为 **12/12**，12 对均为仅 R 成功；固定 24 调用全部证据完整。修复正确性、执行完整性与预设工程门槛均通过，但完整任务成功尚未重新测量。以下 1–8 节是发送前设计，9 节为实际结果。准备检查通过不是模型结果。

## 1. 审计决定与本轮边界

接受用户审计中的两个同时成立的判断：上一轮 12 会话执行及原始监督导出具有完整、有界的证据；Update 的模型可见条件没有完整覆盖实际准入规则。

历史结果提交为 `13e19866b894c4018d795a564076a86b8e1edb17`，实验实现冻结提交为 `bbc713c6ee1c6c3ef6c0ce57dd9c67c4bbc13955`。C/B/S 的完整成功数仍为 1/4、0/4、0/4，总体仍为 1/12，实际请求数仍为 374。C03 的 3 条原请求—原响应监督候选及 1,864 个目标 Token 原样保留。不改历史分母，不替换失败，不回写旧 Response、Receipt、Claim、计数或 Token 工件。

新实验只回答：对于 12 个既有、已验证的首次 pending Observation，指定模型提交 accept 后，完整公开原有 Update 条件能否提高一次提交的合法完整接受比例。它不是完整 QA 会话成功率、未见任务泛化、接受意愿、一般知识修订或 VTDO 效用实验。

本轮止于修复及固定 24 调用校准。六个完整会话属于后继的独立冻结阶段；本轮不会因发现好结果而自动追加，也不会因差异不足而补样。来源扩张、商映射／类权重测量、Student 训练与 GPU 作业均不在本轮。

## 2. 修复：公开规则，不改变接受集合

新增 `finance_qa_update_public_contract.v1`。新的 Runtime Request 仅增加 `public_update_contract` 并重算 Request 身份；原协议版本、Submission Schema、State 与 Operation 合同不变。规则对所有新 Request 可见，在 Update 阶段按 pending Observation 与 disposition 条件应用。

| 原实际检查 | 新公开规则／来源 |
| --- | --- |
| 当前父 State | `state_id = /state/id`，terminal 必须为 false |
| pending Observation | `/state/pending_observation` 非 null；`observation_id` 等于其 id |
| accept 命题 | `proposed_claim` 等于整个 `/state/pending_observation/proposition` |
| reject 命题 | `proposed_claim = null` |
| assessment.relation | accept 为 `accepts_observed_proposition`；reject 为 `declines_observation` |
| assessment.observation_refs | 当前 Observation id 的单元素数组 |
| assessment.evidence_refs | 当前 proposition 的完整、有序 lineage 数组 |
| assessment.fulfills_obligation | accept 为 Observation 的 obligation_id；reject 为 null |
| remaining_uncertainty_refs | 当前 disposition 对应 transition 分支中的同名数组，完整、有序相等 |
| newly_enabled_obligation_ids | 当前 disposition 对应 transition 分支中的同名数组，完整、有序相等 |
| next_subgoal | 同分支 `allowed_next_subgoals` 中的一个字符串成员 |

整对象相等仍使用原 `canonical_json_bytes`，不是原始响应字符串逐字相等。空白、对象键顺序可以不同；不能改字段、字符串、JSON 类型、数组顺序或数值内容，不能加入容差、舍入或隐式类型转换。单个数值、output 本身、扁平自建 Claim、完整 Observation 外壳、未来 Host accepted-Claim 外壳都不能替代 proposition。当前四种命题均具有 lineage、operation、operation_contract_id、output 外层字段。

公开内容是路径与条件表达式，不是已填好的完整响应。模型仍需自行生成所有字段。参考 fixture 改为读取同一份版本化规则；独立控制接收端单独解释公开表达式，不导入旧 `update_response()`，不读取 Runtime 私有状态。该接收端只用于局部控制，绝不生成本轮模型样本。

失败反馈保留原 error code，并在适用时附规则版本／身份、rule_id、响应字段路径、公开来源映射及有限要求。反馈不提供修正后的 Response、不创建新提交、不引用未来 Oracle。新 Runtime 与独立测量器共用该公开呈现；各自原语义准入函数保持不变。

## 3. 同一个冻结评分器与只读保证

`evaluate_update_readonly` 首先调用原 Parser；仅允许 Update 进入评分分支，然后调用原 `PublicQARuntime._admit`。传入的是只具有 copied pending 与 terminal 两个字段的 frozen 只读上下文，不构造 Runtime，没有 adapter、store、计数器、Action 执行器或 Claim 提交方法。非 Update 在分派前停止。

评分前后检查整个 Request、复制 Request 和 pending 内容哈希／规范化字节不变。原 `_admit` 与独立测量 `_admission` 相对基线的 AST 必须一致；`protocol.py` 和 `canonical_json.py` 必须逐字节一致。这些条件在准备及运行前重读检查中强制执行。

两组均使用这一评分入口。完整合法 reject 可以单独标记 `update_admitted=true`，但 `complete_accept=false`。校准评估记录采用独立 namespace，不声称是 Qualified 会话，不生成监督训练行，也不改历史会话。

## 4. 历史挑战的无结果筛选规则

选择规则为：每个原注册会话的首次实际成功 Action 执行后，第一次带 pending Observation 的公开请求。读取已有执行及 HTTP 工件，不重新运行 Action；不以之后是否成功、错误码、长度或输出风格筛选。

| 配对 | 原零起始 Update turn | 命题形态 | 两组顺序 |
| --- | ---: | --- | --- |
| C01 | 1 | registered_compare | O → R |
| B01 | 2 | lookup | O → R |
| S01 | 7 | relation_sum | O → R |
| C02 | 1 | registered_compare | R → O |
| B02 | 7 | lookup | R → O |
| S02 | 1 | relation_sum | R → O |
| C03 | 3 | registered_compare | O → R |
| B03 | 11 | lookup | O → R |
| S03 | 7 | share_ratio | O → R |
| C04 | 1 | registered_compare | R → O |
| B04 | 1 | lookup | R → O |
| S04 | 11 | relation_sum | R → O |

C03 选择的是首次观察态 turn 3，不是后来成功的 turn 20。形态覆盖为 4/4/3/1；这些是相似或重复任务上的历史观察态，不是 12 种独立财务问题。

旧 execution manifest 的固定 SHA-256 为 `6697418c533ae7f4d8b08b9889a287932607b1425c318d865ca60da7eec172b6`。准备时核对其全部成员、原注册顺序、Action—Execution—Observation—Request 关系及原 HTTP body 中的公开请求。另冻结整个旧 `qa_vnext_model_execution` 工件树的成员、长度和哈希，在新阶段重读时核对不变。

## 5. O/R 呈现与模型调用条件

O 保留原公开 Request 原对象；R 只增加版本化 Update 规则及由此改变的 Request id。两组的 State、accepted Claims、pending Observation、数值、lineage、Context、合法候选、transition、Schema 均相同。

两组共同使用原中性系统提示，加一段相同的新校准指令：当前 Observation 已验证，本次只测完整 accept 编码，返回一个 `disposition=accept` 的 Update，不返回 Action、Final、reject，不进行下一次尝试。因此 O 也不是历史提示的逐字复跑，旧历史响应不能用作新的 O 样本。

模型及单次生成条件与旧冻结配置逐字段检查一致：DeepSeek `deepseek-v4-pro`，允许的响应 model 为 `deepseek-v4-pro` 或 `deepseek-v4-pro-0813`，thinking disabled，temperature 0.7，top_p 1.0，max_tokens 8,192，JSON object，非 stream，无原生工具、无重试、无 fallback、无 redirect。模型别名不意味着跨时间不可变权重，观察到的 model 字段会原样报告。

| 冻结限制 | 数量 |
| --- | ---: |
| 单次完整 HTTP body UTF-8 上限 | 98,304 bytes |
| 输入 allowance（字节加 1,024 的保守口径） | 99,328 |
| 单次输出预算 | 8,192 tokens |
| 单次预留 | 107,520 |
| 单校准调用最大尝试 | 1 |
| 校准调用总数 | 24 |
| 总预留上限 | 2,580,480 |
| 总 deadline／连接 deadline | 180／30 秒 |
| HTTP response／public content 上限 | 2,097,152／1,048,576 bytes |

这是预留上限，不是实际 Token 使用量预测；真实消耗以保存的 Provider usage 为准，缺失不补零。全部 24 个实际序列化请求在任何调用前写入、fsync、readback，并检查预算；超界直接拒绝发送，不截断。

## 6. 执行、证据与失败保留

分四轮，每轮 C/B/S 三对并行；每对内部两组顺序执行，前一个完成后才开始后一个。六对 O→R、六对 R→O，且每个任务组内部各两对。第二组请求在第一组发送前已经冻结，不读第一组输出作为范例、反馈或提示。每轮及每次发送前核对冻结输入。

复用现有单次 HTTP 传输：请求与预算 reservation 在发送前持久化；保存实际原始 HTTP request/response body、响应头、原 message.content 字符串、Provider 身份、usage、终止与 fsync／send／receive 日志。传输预算参数改为可冻结的 1 次／24 次；原完整会话默认 32 次及原 pilot 默认 384 次不变。

独立单调用 reader 重新核对文件集合／哈希、注册及 source binding、真实发送体、预算先于发送、一次调用的日志、原 HTTP envelope 与原公开 content。不能仅凭 `origin=model` 得到模型归属。没有 Runtime Submission，不伪造完整会话的 qualification。

每次只生成一次，不进行 Update commit、不调用金融 Action、不生成 Final、不发送错误反馈再试。完全记录的 HTTP 错误、无内容、Schema 或语义失败保留为失败。若已观察到模型或生成条件违例，原语义评分另存，但不计为冻结条件下的成功。实现／证据不完整则保留未知，不冒充模型失败；停止该对剩余调用与未来轮次，已开始的其他并发前缀仍保留。未启动项为 null。无替换、无补样、无按完成数重算分母。

## 7. 发送前控制与统计决定

四种形态使用 C01、B01、S01、S03。控制包含完整 accept、完整 reject、键顺序／空白改变、null accept、数值／扁平对象／output／Observation 外壳替代、单独修改数值／类型／lineage／operation／contract、字段增删、父引用、assessment 各字段和 transition 各字段。局部控制不进入 24 模型调用分母。

主要事件是 `结构合法 ∧ accept ∧ 完整 proposition 一致 ∧ assessment 合法 ∧ transition 合法`。各组固定分母均为 12，报告 pO、pR、Δ=pR−pO，及仅 R、仅 O、两者、均未、未知的配对格数。按 C/B/S 和四种命题形态分层；有不可判定项时对应点估计及差值为 null，同时保留已知成功、失败、未知和固定分母。

三个判断分开：

1. 修复正确性：公开接收端可编码原合法对象，非法对象不因准入放宽而通过。
2. 执行完整性：24 调用或实际停止前缀的证据是否完整、无替换、无历史污染。
3. 工程推进标准：24 项证据完整，R 至少 10/12，且 C/B/S 的 R 各至少 3/4。

第三项是本轮预先冻结的工程标准，不是统计可靠性下界。R 达标但 O 也高时只说明修复后可用，增益证据可能不足；不为追求差异追加样本。R 不达标时记录首先剩余的具体条件错误，不扩来源或训练绕过。新反馈只做局部检查，24 次单步对照不测反馈的交互纠错效果。

## 8. 可复现入口

在仓库根运行；先提交所有实现源码，准备器会核对全部 Python 源码与当前 Git 提交一致。以下命令中的准备目录必须不存在，run 的 execution 目录也必须不存在，禁止恢复或覆盖已有正式执行。

```bash
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_update_calibration.runner prepare \
  --preparation trusted_data_synthesis/artifacts/qa_vnext_update_calibration/update_public_v1_20260906/preparation \
  --design /path/to/original/user-audit.txt

trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_update_calibration.runner run \
  --preparation trusted_data_synthesis/artifacts/qa_vnext_update_calibration/update_public_v1_20260906/preparation

trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_update_calibration.runner analyze \
  --preparation trusted_data_synthesis/artifacts/qa_vnext_update_calibration/update_public_v1_20260906/preparation \
  --output trusted_data_synthesis/artifacts/qa_vnext_update_calibration/update_public_v1_20260906/reanalysis
```

只有 run 读取项目 `trusted_data_synthesis/.env` 的 `DEEPSEEK_API_KEY`。prepare/analyze 不读取凭据、不开网络、不运行 Action 或模型。新版本测量器面向新公开呈现；复现旧会话应使用其原冻结源码，不修改旧工件以适配新 renderer。

## 9. 实际结果

### 9.1 实现冻结与发送前验证

实现提交为 `0e8d92ed6d297d07dacdece385f441fca3839e64`；随后增加真实准备／读回测试的提交为 `98157c09ad9b761e5a3eaf680ba815669bfa0c6c`。正式准备绑定后者，共 857 个 Python 源文件。整个真实执行和只读重建期间源码未改变。

正式准备一次完成，全部 24 个实际 HTTP 请求均已在发送前保存及读回。O 的完整 body 范围为 50,642–61,751 bytes；R 为 55,409–66,518 bytes。每个配对的 R 比 O 增加 4,767 bytes，所有请求均低于 98,304-byte 上限，没有截断。

实际公开规则控制为 **118 项，全部通过**，覆盖四种原命题形态；这是零 Provider 的有限控制，不是 118 个模型样本。新增校准测试先通过 51 项，真实源码快照／历史输入／prepare／24 次 adapter_mock／readback／analyze 全流程另通过 1 项；其 socket、真实凭据读取、Runtime 构造均为零，24 个 adapter_mock 响应均不标记为 model sample。

最终相关全量回归为 **386/386 通过**，耗时 285.17 秒。另有 Ruff 通过、8 个相关源码文件的 mypy 检查通过。架构检查实际扫描 core/runtime/architecture 的 197 个文件、0 项违规；不将这个范围误写成扫描全部 857 个源文件。

开发中的失败也保留：最初独立测量测试的 11 项失败来自其手工 Request 仍使用旧呈现，同步测试输入后相关 122 项通过；后来全量检查为 382/383，通过其中 1 个失败发现 Action 阶段的无效 JSON 被附加 Update 专用诊断。修订诊断适用阶段、增加两个边界测试后，原监督表示回归 57 项通过，最终全量 386 项通过。此前零 Provider 控制还发现并修正过新评估记录的 `kind` 命名冲突。所有这些修订均发生在正式调用前，不是失败模型调用的替换，也没有放宽准入函数。

### 9.2 固定总体结果

真实 run 开始于 2026-09-06 07:17:47.274052 UTC，最后一轮完成于 07:18:59.459047 UTC，约 72.18 秒。四轮全部完成，没有触发完整性停止。24 项均启动并完成一次实际请求，未知、未启动、HTTP 失败、自动重试、fallback 和替换均为零。

| 分层 | O 完整合法 accept | R 完整合法 accept | Δ（R−O） |
| --- | ---: | ---: | ---: |
| C：注册跨指标比较 | 0/4 | 4/4 | +1.00 |
| B：分支任务首次 lookup | 0/4 | 4/4 | +1.00 |
| S：部分／整体占比首次观察态 | 0/4 | 4/4 | +1.00 |
| **合计** | **0/12** | **12/12** | **+1.00（100 个百分点）** |

配对格数为：仅 R 成功 12、仅 O 成功 0、两者成功 0、两者均未成功 0、未知 0。

命题形态分层：registered_compare 为 O 0/4、R 4/4；lookup 为 O 0/4、R 4/4；relation_sum 为 O 0/3、R 3/3；share_ratio 为 O 0/1、R 1/1。这里不能把 ratio 的一次观察扩写为稳定的一般成功率。

24 个原始响应全部通过 JSON／结构 Schema，全部提交 `disposition=accept`，没有通过 reject 绕开命题复制。R 的 12 个响应均经原同一个准入分支通过完整 proposition、assessment 和 transition 检查。O 的 12 个响应全部首先失败于 `admission.exact_observation_acceptance`，而不是 JSON 生成失败。

O 的实际形态为：11 次 `proposed_claim=null`，另一次 C03_O 在正确 proposition 外另套自建 Claim 对象，带 `claim_id`、`obligation_id`、`proposition`、`citations`。其内部 proposition 含正确的 comparison 输出及 lineage，但外层对象不是契约要求的 proposition 本身，因此被拒绝。不能因首错统计而声称 O 的其余所有 assessment／transition 字段均正确。

### 9.3 模型条件与真实用量

24 个保存的 Provider 响应均报告 `deepseek-v4-pro`；已观察的模型条件违例为零。没有据此宣称此别名跨时间绑定不可变权重。

| 实际 Provider usage | O | R | 合计 |
| --- | ---: | ---: | ---: |
| prompt_tokens | 197,293 | 210,421 | 407,714 |
| completion_tokens | 4,694 | 7,841 | 12,535 |
| total_tokens | 201,987 | 218,262 | 420,249 |

总 prompt cache hit 为 267,904、miss 为 139,810，合计与 prompt_tokens 一致。reasoning_tokens 未提供，保留 null，不填零。全部 24 次均各预留 107,520，总预留 2,580,480；这与 420,249 的实际报告消耗是不同口径。

### 9.4 独立复核、历史不变与工件

对正式目录两次执行真实 `analyze`，并同时禁止凭据读取、Provider send、socket 连接、Runtime 构造、Program 和 Share 执行器。六类 guard 计数全部为零，没有新增 Provider 请求。两次重建的 report、audits 和 manifest 三个文件逐字节一致；report、audits 也与正式 execution 对应文件逐字节一致。每次重建均重新检查源码快照、旧树全部 6,401 个工件及每个调用的真实 HTTP 证据。

核心工件目录为 `artifacts/qa_vnext_update_calibration/update_public_v1_20260906/`：

| 子目录 | 文件数 | 字节数 | 角色 |
| --- | ---: | ---: | --- |
| preparation | 94 | 9,888,375 | 原审计、注册、来源、规则控制、24 个冻结输入与 HTTP body |
| execution | 420 | 8,074,056 | 实际 24 调用原始传输、只读评分、调度与报告 |
| reanalysis | 3 | 51,858 | 第一次独立重建 |
| guarded_reanalysis | 3 | 51,858 | 第二次独立重建 |
| readonly_checks | 2 | 1,186 | guard 计数和逐字节一致性检查 |
| publication_validation | 12 | 2,266,803 | 历次测试、架构检查、描述统计、历史不变与密钥检查 |

新目录合计 534 个文件、20,334,136 bytes。以实际 API key 对新工件逐字节扫描，匹配数为 0；未导出 .env 或模型权重。旧实验目录没有增删或改写；其 6,401 个文件、227,427,292 bytes 保持不变，历史 1/12、374 次提交、C03 三条原始监督及 Token 结果全部保持原定义。

主要身份：

- Condition：`qa_vnext_update_calibration_condition:b42514d5eca6971cc7b6ab262d3ef96df4c7cef46b207d349febb5e2e8f7b3f0`。
- Preparation manifest：`qa_vnext_model_execution_update_calibration_preparation_manifest:d652abbc25ad946790f6b5bf62576c0b41f90af31966493fc41833bc6216a46a`。
- Execution manifest：`qa_vnext_model_execution_update_calibration_execution_manifest:be00977c358516a8df8cb2019a03d98c33abadc4d54b08afe03cdb8834a78a02`。
- Result：`qa_vnext_update_calibration_summary:f1a343ea8b7c4be4e859e84753eba3181cd511d018544a79c7adee810611c5bf`。
- Readonly checks：`qa_vnext_update_calibration_readonly_checks:cc4a934cf59266a23fa852cdb7fbf3883dbd2e544f3f89ecfec3ad020ea1cfb9`。
- Publication validation：`qa_vnext_update_calibration_publication_validation:e23097ce2af08afc3dc97f4d4dc647cb1e7ed907c8c2d2f30f2c5497df833a7f`。

### 9.5 结论与下一边界

三个决定均通过：原准入标准未变且公开接收端控制通过；24 项模型证据完整；R 12/12 且 C/B/S 各 4/4，超过预设的 10/12 与各 3/4 工程门槛。当前有限配对对照支持：完整公开既有 Update 条件，对指定 accept 的一次合法完整提交产生了明确的观察改善。

这不证明全部旧失败都只由该缺口造成，也不证明模型数学／任务深度能力已经普遍成立。两组共享新增 accept-only 指令，O 不是历史逐字复跑；观察态来自已有任务且重复相似，样本少，模型别名与服务条件并非不可变；没有检验自主 accept/reject、反馈交互纠错、后续 Claim 消费、深度三运算、完整 Final 或新商类。

本轮实际 Action 执行、Update commit、创建 Claim、完整 Qualified 会话、监督训练行、Student／GPU 作业均为零。**R 的 12 次单步接受成功不等于 12 个完整 QA 会话成功，更不替换历史 q=1/12。**

当前已具备进入后继有限完整任务检验的预设工程条件。建议下一阶段单独冻结原三个任务各 2 个新完整会话，共 6 个，恢复 accept/reject 自由选择，观察后续实际语义操作、Claim 消费及有效 Final；本轮没有执行这些后继会话，没有继续补样。
