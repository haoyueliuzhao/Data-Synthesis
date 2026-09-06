# Action 公开合同修复与原 B 任务两会话完整可达性

日期：2026-09-06。阶段：`finance_qa_vnext_action_public_contract_repair_and_branch_reachability_pilot`。

## 1. 授权与不变的历史结论

本轮由用户“参照审计继续实验”授权实施。用户审计原文 552 行、27,163 bytes，SHA-256 `faed220ec5e344741d239883beb3d05020f1d65e82d045a3c98bca19aec0ebeb`；实际准备将保存完整原始字节。

前序结果保留：最早完整试验 1/12，指定 accept 的单步 O/R 校准 0/12 与 12/12，随后六个完整会话 C 2/2、B 0/2、S 2/2（4/6）。六会话中的 13 个动态 Observation 都首次 accept 并 commit，C/S 已有完整见证；B 的主要消耗为 54 次 Action 候选全集遗漏拒绝，尚未进入真实增长和分支合并。

本轮只修复已经由源码和实际请求共同定位的 Action 模型侧公开缺口，然后只对原 B 任务运行两个全新完整会话。不重复 C/S 或 24 次单步校准，不修改历史工件，不将不同生成条件的成功拼成“同条件 6/6”，不声称无同期对照的前后差值是精确因果效应。

## 2. 有限 Action publication 与反馈

新增 `finance_qa_action_public_contract.v1`，以当前请求中的 `public_action_contract` 给出静态公开关系和表达式。Runtime Request 与独立测量重建均加入此 publication 并获得新 Request ID；原 `finance_qa_public_decision_protocol.v2`、Submission Schema 和 `finance_qa_update_public_contract.v1` 保持原样。

| Action 响应字段 | 公开来源或规则 |
| --- | --- |
| state_id | 当前 `/state/id` |
| decision.candidate_action_ids | 当前全部 `/available_actions` 的 id，集合相等且不重复，清单顺序不限 |
| decision.selected_action_id | 模型自行选择当前可用集合中的一个 id |
| operation / inputs / parameters | 完整对应这同一个选中项，保留原 JSON 内容与数组顺序 |
| decision.obligation_id / subgoal / basis / expected_effect | 同一个选中项的对应字段，不混用其他候选 |
| decision.selection_rule | 该选中项 selection_rules 的一个成员 |
| decision.unresolved_uncertainty_refs | 原规则要求的空数组 |
| Claim 依赖 | 当前 State 中 status=accepted 的 Claim；保持原角色、selector 和依赖约束 |

`candidate_action_ids` 是接口要求的完整当前清单，不是选中项、不只是模型考虑的子集，也不是某个 obligation 内的候选。新 growth 可能在接受 lookup Claim 后出现，不能实现为从初始四个 ID 单调删除。只有候选 ID 清单按无序集合比较；inputs、basis 等其他数组仍按原合同处理。列全 ID 本身不是逐个内部比较、关键推理或 VTDO Contribution 的证据。

对 `admission.alternative_set`，新反馈只提供该公开 rule_id、当前 ID 的集合路径以及 missing_ids / extra_ids / duplicate_ids。选中项字段不一致时只标出字段和 selected binding 来源。不会替模型选择 Action、补齐其清单、修改原响应或在没有新模型提交时继续执行。Update 及 Final 的反馈分支原样委托既有实现；不改 Final 答案投影或 Share 路线偏好。

## 3. 原标准保持与局部零调用检查

基线提交为 `5df110cc6b98bd65658ad4204c3ccd5b4ec1c9a7`。准备要求：

- `protocol.py`、`canonical_json.py`、`update_public_contract.py`、Program/Share adapter 字节均不变；因此 Schema、数值与 Final 验证标准不变。
- Runtime `_admit` 与独立测量 `_admission` 的 AST 不变。运行新增 readonly Action 入口时，直接调用原 `_admit`，包括既有纯 adapter.prepare；不构造运行会话、不执行金融 Operation、不 commit、不调用 Provider。

控制优先读取前序真实 B01/B02 Request：覆盖 2/3/4 个可用候选，以及 lookup 接受后出现非初始 growth 候选的动态状态；另读一个 C 单候选、一个 S 多候选请求作局部接线检查。隔离接收端仅解释 publication 的公开路径、集合、选中项绑定和选择表达式，不导入旧 action_response 或 Runtime 私有构造。

共 6 个实际来源请求、69 个局部控制，每个响应在原请求和加入 publication 的请求上都走同一原准入路径（138 次只读准入评价）。包括任一合法选中项、候选清单换序、选中项/合法子集遗漏、重复、额外、旧初始全集、错误选中 ID、混用 operation/basis，以及 inputs 换序仍拒绝。两种呈现的合法/非法结果和错误码必须一致；这些不是 69 个模型样本。

读取既有完整 B fixture 的 17 个阶段请求，仅检查新完整 HTTP 请求字节预算，不重新执行旧 lookup/growth。检查包括后期增长、signed gap、absolute gap 及 Final；当前检查最大为 78,532 bytes，低于 98,304。真实在线每次请求仍由原传输层单独执行字节准入，不按离线结果豁免。

## 4. 调用前冻结的在线总体

| 项目 | 冻结值 |
| --- | --- |
| Task/Context/Evidence/Operation | 原 B：CDW FY2015/FY2016 分支合并，完全沿用原来源和数值 |
| 会话 | 新 B01、B02，两条独立新 session/transport 身份，不续接历史 Claim |
| 初态 | accepted Claims=[]、pending=null、计数 0、feedback=null |
| 调度 | 一个固定轮次，按 B01/B02 登记启动，并发最多 2；不按结果调整顺序 |
| 教师条件 | deepseek-v4-pro；thinking disabled；temperature=0.7；top_p=1.0 |
| 消息 | 原中性完整任务 SYSTEM_PROMPT + 当前完整公共 Request；无 accept-only 或固定执行脚本 |
| 每会话 Action / Submission / Provider attempt | 12 / 32 / 32，含 Final |
| Provider 总上限 | 64 |
| 输出 | JSON object，非 stream，max_tokens=8192 |
| 完整 HTTP body 上限 | 98,304 bytes；输入准入代理 body bytes+1024，上限 99,328 |
| 时限 | 总 deadline 180 秒，连接 30 秒 |
| allowance | 每次 107,520，每会话 3,440,640，总上限 6,881,280；不是实际用量 |
| 自动网络重试 / 回退 / 失败替换 | 0 / 0 / 0 |
| 新来源 / C/S 在线重复 / Student / GPU | 0 / 0 / 0 / 0 |

合法 Final 立即停止；两条都失败也不提高上限、不补样。结构或公开语义拒绝后的纠正是新的模型响应，计入原预算；旧响应不修写。完整记录的资源/超时/无内容终止按既有资格规则判断，缺失或内部无法确定的证据保留 unknown。已启动的并发会话均保留，不因另一条失败而替换。

准备绑定设计、全部 Python 源文件与提交、软件与 tokenizer-only 资源、生成配置、两行登记、两个初始 Request/HTTP、局部控制，以及前三阶段的完整工件清单。TaskPanel 的本轮 coverage 只选 B（1 个类型）；另 7 个有来源类型未在本轮在线测量，3 个类型来源未实例化。旧 C/S 见证不挪入这一新条件。

## 5. 主结果、真实推进与附加测量

完整成功仍为有效 Final ∧ 独立 QA 验证 ∧ 轨迹验证。两行均可判定时 q_B,new=(Y1+Y2)/2；unknown/not_started 不填零、不删除后重归一化。至少一个 Qualified 完整 B 会话即可提供当前条件的构造见证，不要求 2/2；两个样本也不能精确估计稳定总体能力。

逐会话报告当前全集准入、lookup Claim commit、第一个实际非透明操作、growth 对 accepted lookup Claim 的真实消费、两条 growth 依照原角色进入 signed gap、signed gap 进入 absolute，最后是否有效 Final。每个阶段引用实际 Receipt、Observation、Claim 与输入角色/selector；只说“要做 growth”不计执行。

实际深度从既有事件图恢复，完整轨迹和失败前缀分开。lookup 是透明操作，不把 lookup 个数或纠正次数充当语义深度。逐 Observation 的第一次 Update、最终 accept/reject、处理提交数及 Claim 消费仍保留；候选全集正确率不得补偿没有完成的任务。

若存在 Qualified B，会同轮通过原导出器保存完整真实请求—原样准入响应监督候选，排除失败前缀和未准入响应；做既有 24,576 Token 检查，过长保留原候选与诊断、不截断、不回写为轨迹失败。至多一个同任务 Qualified 无序配对交由既有限投影；纠正导致 projection undetermined 时仍保留资格。不构建新 Mapper、Assignment、类权重、Contribution 或训练。

## 6. 入口、测试和工件管理

从仓库根目录运行：

```bash
PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python \
  -m trusted_synthesis.experiments.finance_qa_vnext_action_branch prepare \
  --root "$PWD" --preparation /absolute/new-run/preparation \
  --design /absolute/audit.txt --run-tag action-branch-20260906

PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python \
  -m trusted_synthesis.experiments.finance_qa_vnext_action_branch run \
  --root "$PWD" --preparation /absolute/new-run/preparation

PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python \
  -m trusted_synthesis.experiments.finance_qa_vnext_action_branch analyze \
  --root "$PWD" --preparation /absolute/new-run/preparation --output /absolute/new-analysis
```

真实运行不可 resume、重复启动或覆盖已有目录；read-only analyze 不可写入已封存 execution。历史原始工件不变。本轮代码、文档和新工件按用户授权提交并推送同一仓库 main。

新增接线测试包括全集和对应字段的反馈、两种合法调度、纠正、已知失败、unknown、空正向池、64 次上限及只读重分析。另在提交源码后执行真实 CLI prepare/读回/完整双 B 模拟 HTTP 往返；模拟数据不是 Provider 样本。相关 Runtime/测量/资格回归的手写测试轨迹需要加入新 publication；初次遗漏使 11 项先报 `event.actual_request`，现仅更新测试请求呈现，不放宽读者或原标准。初次失败记录将与最终通过记录分别保留。

## 7. 实际结果

### 7.1 冻结身份与完整结果

本轮已经完成。真实调用使用冻结提交 `1cf4d520d8bca30ffbdda7bfb059b5e8607cd8dd` 的 871 个 Python 源文件；之后没有更改源码、测试、采样配置、候选集合或验证标准。工件根为 `trusted_data_synthesis/artifacts/qa_vnext_action_branch/action_contract_branch_v1_20260906/`，以下相对路径从此处起算。

| 冻结对象 | 实际身份 |
| --- | --- |
| Condition | `qa_vnext_model_execution_action_branch_condition:ba20f2e9fc60c60f557240c9627f9c4734025967176cd21b869c90ed222fa2e9` |
| Preparation | `qa_vnext_model_execution_action_branch_preparation:b721f65c1c7f85308c2934f085549e3e450e84bf5a9f7887ab90e52a4aca86d1` |
| Action publication | `finance_qa_vnext_action_public_contract:fe48fd87bdf017de09f3091503230f48a83ce4ece83faf20e0c06dedec6baff8` |
| 实际报告 | `qa_vnext_model_execution_pilot_report:4a3d9a7f1aad76406cf3e56bab824c27ed8e9f5e6ff35d23964f839c16d13c49` |
| Execution manifest | `qa_vnext_model_execution_execution_manifest:6d0ae251cf016d2131c059fb49b1a3204573988c972230a2a56473e08eef7a42` |

| 会话 | Provider / Submission | 准入 Action / Update / Final | 未准入 | 完整结果 |
| --- | ---: | ---: | ---: | --- |
| B01 | 17 / 17 | 8 / 8 / 1 | 0 | 有效 Final，独立 QA/轨迹通过，Qualified |
| B02 | 17 / 17 | 8 / 8 / 1 | 0 | 有效 Final，独立 QA/轨迹通过，Qualified |
| 合计 | 34 / 34 | 16 / 16 / 2 | 0 | 2/2 |

两行完整、可判定，q_B,new=2/2=1；known_failure、unknown、not_started 均为零。至少一个完整 B 见证的冻结科学条件满足，执行工作流亦完整。每会话在第 17 次提交的有效 Final 后立即停止；没有补样、网络重试、回退、替换、Host 响应修复或两会话之后的新 Provider 调用。

34 条实际响应全部通过 JSON/结构 Schema，HTTP 均为 200，身份均为 `deepseek-v4-pro`，无观测到的条件偏离。34/34 实际 HTTP body 都含中性完整任务指令、原 Update publication 和新 Action publication；两个实际首请求分别与调用前冻结的空初态 Request/HTTP 一致。

这回答了“B 在新 Action 公开条件下能否完整完成”的有限构造问题，而不是稳定总体能力的精确估计。没有同期 O 组，不将旧 B 0/2 与新 B 2/2 的差值当成精确因果效应；模型响应身份也不构成服务权重不可变的保证。

### 7.2 候选全集约束已进入真实执行

16/16 个实际 Action 都在第一次提交时列全当前候选且无重复、选择当前合法项并通过后续对应关系与依赖检查。没有 alternative_set、selected_action_content 或 public_judgment 拒绝。没有把仅通过集合条件、但后续拒绝的 Action 计作执行成功。

下表 T 为从 1 起算的 Submission 序号。两条会话并非被强制成唯一执行脚本：

| Action T | B01 实际操作（当时可用候选数） | B02 实际操作（当时可用候选数） |
| ---: | --- | --- |
| 1 | revenue_earlier lookup（4） | revenue_earlier lookup（4） |
| 3 | revenue_later lookup（3） | revenue_later lookup（3） |
| 5 | revenue_growth（3） | income_earlier lookup（3） |
| 7 | income_earlier lookup（2） | income_later lookup（2） |
| 9 | income_later lookup（1） | revenue_growth（2） |
| 11 | income_growth（1） | income_growth（1） |
| 13 | signed_percentage_point_gap（1） | signed_percentage_point_gap（1） |
| 15 | absolute_percentage_point_gap（1） | absolute_percentage_point_gap（1） |

例如前两个 revenue lookup 接受后，当前集合出现新的 revenue_growth ID，而非仅删除旧 ID；两个模型会话均正确使用这一当前集合。实际候选清单恰好都采用 Request 内的列出顺序，但并没有据此增加排序标准：清单换序仍合法由零调用控制证明，不冒称实际模型尝试过所有排列。

新反馈的 missing/extra/duplicate 与字段来源功能通过局部和模拟纠正测试；本轮真实会话没有拒绝，所以没有真实模型使用新增拒绝反馈来纠正的样本，不能单独声称测得反馈改善。

### 7.3 实际 Claim 消费与分支推进

| 位置 | B01 实际证据 | B02 实际证据 |
| --- | --- | --- |
| 首 Action 全集准入 | T1，四个当前候选完整声明 | T1，同左 |
| 首 lookup Claim commit | T2 | T2 |
| 首非透明操作与 Claim 消费 | T5 revenue_growth 使用 T2/T4 接受的 lookup Claim | T9 revenue_growth 使用 T2/T4 接受的 lookup Claim |
| 第二个 growth 分支 | T11 income_growth 使用 T8/T10 Claim | T11 income_growth 使用 T6/T8 Claim |
| 分支合并 | T13 按原 income_growth、revenue_growth 输入角色消费两条已接受增长结果 | T13，同样的角色和依赖关系 |
| absolute 后继 | T15 消费 T14 接受的 signed_gap Claim | T15，同左 |
| 有效 Final | T17 使用 T16 接受的 result Claim | T17，同左 |

不是只在文本中提出 growth：每一步都存在原样模型 Action、已准入 Receipt、真实执行记录、Observation、后续模型 Update、accepted Claim 和后继引用。完整 ID、输入角色及 selector 见 `execution/analysis/progress/B01.json`、`B02.json`；数值输出亦由独立资格器复验。

下面按每个实际 Observation 列出处理与消费。每一行均为首次 Update 合格、处理提交数 1、最终 accept、首次拒绝 null；Claim 都有真实后继消费者。

| 会话 | Observation 义务 | Action T | Update T | Claim 后继消费者 |
| --- | --- | ---: | ---: | --- |
| B01 | revenue_earlier_value | 1 | 2 | growth T5 |
| B01 | revenue_later_value | 3 | 4 | growth T5 |
| B01 | revenue_growth | 5 | 6 | signed gap T13 |
| B01 | income_earlier_value | 7 | 8 | growth T11 |
| B01 | income_later_value | 9 | 10 | growth T11 |
| B01 | income_growth | 11 | 12 | signed gap T13 |
| B01 | signed_gap | 13 | 14 | absolute T15 |
| B01 | result | 15 | 16 | Final T17 |
| B02 | revenue_earlier_value | 1 | 2 | growth T9 |
| B02 | revenue_later_value | 3 | 4 | growth T9 |
| B02 | income_earlier_value | 5 | 6 | growth T11 |
| B02 | income_later_value | 7 | 8 | growth T11 |
| B02 | revenue_growth | 9 | 10 | signed gap T13 |
| B02 | income_growth | 11 | 12 | signed gap T13 |
| B02 | signed_gap | 13 | 14 | absolute T15 |
| B02 | result | 15 | 16 | Final T17 |

因此本轮首次接受为 16/16 个实际到达的 Observation：lookup 8、growth 4、signed gap 2、absolute gap 2；reject、Update 拒绝和终止时待处理 pending 均为零。growth、signed gap 和 absolute gap 从前序仅有局部控制，推进到了新条件下的真实模型 Update/commit/消费见证。不把 16 个 Observation 写成 16 个完整任务。

两会话的已验证数值相同：revenue lookup 为 `12988.7`、`13981.9`，income lookup 为 `742`、`819.2`（原数据单位 million USD）。原 Operation 得到 revenue growth `7.646646700593592892283292400`、income growth `10.40431266846361185983827493`，signed gap 为 `-2.757665967870018967554982530` percentage_points；absolute 及 Final 为 `2.757665967870018967554982530` percentage_points。计算由冻结 Operation 执行，本轮不把它解释成模型脱离工具自行心算这些数值。

### 7.4 实际深度与有限比较

| 会话 | 实际结构深度 | 实际语义操作深度 | 可观察选择依赖深度 | 证据范围 |
| --- | ---: | ---: | ---: | --- |
| B01 | 4 | 3 | 0 | complete_session |
| B02 | 4 | 3 | 0 | complete_session |

结构路径包含 lookup→growth→signed gap→absolute 四层；lookup 在既有语义权重中透明，故实际语义深度为三。这是执行依赖深度，不是隐藏思维、关键内部推理深度或“17 次提交所以深度 17”。多个独立义务的合法调度不被现有测量当作新的语义选择；候选数也不是推理深度。

两个 Qualified 会话的投影均 supported，唯一同任务无序配对在既有限投影下 equivalent。B01 提前执行 revenue_growth，B02 先完成四个 lookup；该合法调度差异没有被自动包装为两个不同语义商状态。没有新 Assignment、类权重、完整商分布、Contribution 或 Student 训练。

### 7.5 原响应候选完整保留；Token 表示为部分可用

两条完整 Qualified 会话各导出 17 条真实请求—准入原响应，共 34 条原始监督候选。本轮所有提交都准入，无失败前缀混入，也不读取历史 C/S、旧 B 或单步校准响应作为正向行。

在冻结的 24,576 Token 限制下，32 条可用、2 条过长；全部序列长度范围 20,882–24,924。两条过长记录如下：

| 会话 / 提交 | 对象 | prompt tokens | target tokens | 全序列 tokens | 超出上限 |
| --- | --- | ---: | ---: | ---: | ---: |
| B01 / T16 | 接受 absolute result Observation 的 Update | 23,913 | 970 | 24,885 | 309 |
| B02 / T16 | 同上 | 23,932 | 990 | 24,924 | 348 |

全序列另包含该 tokenizer 表示中的两个 suffix tokens。它们是完整任务后期较长状态下的原样 Update 候选，不是无效轨迹。两条原始候选及未截断 Token 记录都保留，`truncated=false`，没有放大长度上限、裁剪公共上下文、丢弃字段或重写任务资格。

因此应如实记录 `status=contains_not_fit`、`positive_representation_validated=false`，而不是宣称全量正向表示通过。32 个可消费轮次也不自动等于两个完备的可训练整会话包；本轮没有构建训练分布或启动训练。表示的这个局部长度缺口不否定 B 的完整有效 Final 与轨迹见证。

原始候选、所有 Token 记录以及逐行长度见 `execution/analysis/supervision_candidates.json`、`token_representations.json` 和 `publication_validation/token_lengths.json`。两条过长的候选身份分别以 `719feea50307f70a...`、`71d6d1dec420b8e4...` 开始，完整 ID 保存在长度诊断中。

### 7.6 真实用量与执行边界

| 会话 | Prompt tokens | Completion tokens | Total tokens |
| --- | ---: | ---: | ---: |
| B01 | 355,919 | 10,036 | 365,955 |
| B02 | 356,724 | 10,072 | 366,796 |
| 合计 | 712,643 | 20,108 | 732,751 |

缓存命中 328,320 + 未命中 384,323 = prompt 712,643。34 条 reasoning_tokens 均缺失，保持 null，不填零。实际 34 次调用预留 allowance 为 3,655,680，设计上限为 6,881,280；二者不是实际 Token 消耗，也不是成本报价。

最大实际 HTTP body 为 78,532 bytes，输入代理最大 79,556，均未触发上限。Teacher HTTP 字节准入与附加 tokenizer 的 24,576 序列限制是不同边界：不能因前者通过，隐去上节两个过长候选。

最早 reservation 为 UTC `2026-09-06T11:58:25.844944+00:00`，最晚为 `2026-09-06T12:00:28.075908+00:00`；它们是预留记录时间，不冒称完整会话起止时间。本轮实际 C/S 调用、新来源、新题型、网络自动重试、fallback、替换、后追加 Provider 调用、Student 权重加载/forward/更新、GPU 作业均为零。

### 7.7 测试、独立复核与发布完整性

最终通过的不同测试共 145 项：新增 23 项接线/模拟完整执行测试，1 项冻结提交下实际 CLI prepare→原样读回→两条 B 完整模拟 HTTP 往返，以及 121 项相关 Runtime/测量/资格回归。69 项局部 Action 控制也全部通过。没有重做原 118 项 Update 审计、来源或 Registry 构造实验。

初次相关回归中的 11 项失败来自手写测试轨迹没有加入新 Action publication，首错均提前落在 `event.actual_request`；只更新测试请求呈现后，121 项全部通过。该初始失败 JUnit 与最终通过记录分别保留于 `publication_validation/tests/`，不当成真实模型失败或隐藏掉。真实 CLI 往返没有模拟 source/preparation/configuration 检查，HTTP I/O 才由本地测试替代，不能当作另两条 Provider 样本。

真实执行结束后，两次串行只读重分析各产生 17 个文件、15,449,594 bytes，均与正式 `execution/analysis` 逐文件字节一致。两个财务执行器、Runtime 构造、Callback、Provider、socket 和凭据入口均设禁止调用保护，计数全部为零。重新验证全部 871 个冻结源文件、原验证标准保持记录和 12 个 preparation/execution/analysis 递归 manifest。领域中立架构检查 197 个文件、0 个违反。

历史三阶段共 8,813 个文件、345,828,010 bytes，与准备时清单逐项哈希一致。新工件没有 `.env` 或权重文件；实际 API Key 字节扫描零命中。当前修改没有回写原 1/12、O/R 0/12 vs 12/12 或六会话 4/6 的任何定义和原始证据。

| 新工件子目录 | 文件数 | bytes |
| --- | ---: | ---: |
| preparation | 106 | 4,317,739 |
| execution | 546 | 37,521,515 |
| reanalysis | 17 | 15,449,594 |
| guarded_reanalysis | 17 | 15,449,594 |
| readonly_verification | 4 | 10,093 |
| publication_validation | 11 | 2,233,743 |
| 合计 | 701 | 74,982,278 |

最大单文件为 9,675,716 bytes 的 Token 记录。审计原文 CRLF、模型原响应空白及失败 JUnit 文本保留原字节，不为格式检查重新正规化工件。

只读复核身份为 `qa_vnext_model_execution_action_branch_readonly_verification:8e5b5e6888c6516402c0456065226c7d07c53eb1945e2d99b25c37d016cb55a0`；发布核对身份为 `qa_vnext_model_execution_action_branch_publication_validation:fda095f598010591a2d10c8e615bcf9a9ef836614e575252698e998dc72937c7`。复核脚本与完整检查结果均随对应目录保存。

## 8. 收口

当前 Action 公开缺口按本轮有限范围完成修复，并获得两条真实 B 完整可达见证；原 B 接入缺口可以关闭，不再重复同内容证明。原 Update 修复保留，并在本轮实际到达的 growth/signed gap/absolute gap 上获得新的动态接受与消费见证。

这不是同一新条件下 C/B/S 六会话全部成功，也不是一般数学能力、通用规划或 VTDO 训练效用证明。后续若建设统一任务面板或研究训练表示，应另行固定统一生成与表示条件；本轮不因两个 Token 候选过长而自动改写表示合同、提高预算或开始训练。两个登记会话及附加测量到此结束，旧主线保持暂停。
