# 当前 Agent 架构详细审计报告

审计日期：2026-08-23  
审计对象：Finance v26.117-v26.120 Canonical Semantic Action Agent 及其直接依赖  
审计基线：Git a55434e27ac52a6b11f15006ee93313d967d06df  
审计性质：只读架构与实现审计；不是新实验、经验测量、历史重分类或执行授权

## 1. 执行摘要

当前主线 Agent 已经从“模型自由生成 Tool 与 Arguments”的开放式 Agent，演化为一个
闭世界、候选动作驱动、两阶段、Host 执行、独立验证的实验 Agent：

1. Host 从当前公开状态构造完整合法动作集合；
2. Stage 1 模型只返回 state_id、action_id、decision_kind 和 protocol；
3. Host 验证动作仍属于当前状态的可选集合；
4. Stage 2 将同一个 action_id 确定性编译成 Tool Call，且不调用 Provider；
5. Finance Runtime 执行 Tool Call 并产生内容寻址的公开 Observation；
6. 状态重新构造，循环直到模型选择 Final；
7. 最终答案通过单独的模型请求产生，并应在运行后进入 Verifier v3、独立有效性和机制评分。

这一架构对 Tool 参数语法漂移、不可执行 Operation 选择、重复失败调用、Host 静默修复模型
语义、Provider 路由漂移、预算超限、私有 reasoning 持久化和历史实验污染控制得较好。它的
实际测量对象不是一般意义上的开放式 Agent 能力，而是：

~~~text
在 Host 枚举的完整公开合法动作空间中，模型解释当前状态并选择一个规范动作的能力
~~~

| 维度 | 结论 | 说明 |
| --- | --- | --- |
| 语义权限边界 | 强 | 模型选择完整动作；Stage 2 不选择或修复 Tool、Node、Operator、Operand、Evidence |
| 状态与 ABI 约束 | 强 | 当前状态、候选集合、四字段响应、协议和 Commit 均强类型并内容寻址 |
| 静态可构造性 | 已通过 | v26.117-v26.119 的静态路径、候选完整性、脚本 Runner 和破坏性控制均通过 |
| 真实模型可用性 | 未测量 | v26.120 尚未执行，v26.119 的 32 Job 是脚本客户端控制，不是 Flash 行为 |
| 整批执行就绪度 | 实现已形成、经验结果未产生 | v26.120 已纳入完整 32-Job 执行、检查点、恢复、独立评分、聚合和报告入口；尚无真实运行 Artifact |
| exactly-once 暴露 | 不完备 | Provider 调用意图没有在网络调用前持久化，存在无法区分“未调用”和“已调用但未落盘”的崩溃窗口 |
| 独立验证 | 实现链存在、线上证据未产生 | v26.120 已实现 Verifier v3、独立 validity、mechanism scoring 和结果聚合；当前只有脚本测试证据 |
| 可维护性 | 中等偏低 | 当前 Runner 大量复用历史实验模块、类型和私有函数，科学绑定强但工程耦合重 |
| 扩展性 | 受限 | 验证 Candidate 对 Evidence 非空子集做组合枚举，并在多于 8 个 Evidence 时直接失败 |

综合判断：当前 Agent 的语义安全边界设计成熟，静态证据链很强，v26.120 整批控制面也已经
进入 Git；但 Provider 调用前缺少耐久 invocation intent，使崩溃条件下的 exactly-once 暴露
仍不能闭合。该问题应在真实校准前解决，并以改变后的执行实现建立新身份和零 Provider 预检；
不能仅凭整批脚本测试把当前实现解释为可安全启动或真实 Flash 可用性证据。

## 2. 审计范围与证据等级

### 2.1 纳入范围

| 层 | 主要文件 | 职责 |
| --- | --- | --- |
| Semantic Action 协议 | runtime/agent/prospective_semantic_action_protocol.py | 公开状态、候选动作、Proposal、Commit、语义拒绝、Stage 2 编译 |
| 四字段响应 ABI | runtime/agent/prospective_semantic_action_response_grammar.py | Candidate 展示、三类 Prompt、精确 Parser |
| Thinking 策略 | runtime/agent/prospective_thinking.py | 强制 thinking.type=enabled 并绑定配置身份 |
| Stage 1 客户端 | runtime/agent/prospective_two_stage_stage1_client.py | 精确模型路由、请求体证书、响应遥测和 reasoning 隐私裁剪 |
| Tool 公共接口 | runtime/tools.py | Tool Spec、Call、Result、Observation 和 Host 元数据隔离 |
| Finance Runtime | domains/finance/interactive_agent_runtime.py | 离线 Archive 工具、操作状态和可重放业务结果 |
| v26.118 控制面 | phase1_v26_semantic_action_rematerialization.py | Candidate 权威、资源 Contract、Task/Path/Job/Manifest 新身份 |
| v26.119 Runner 内核 | phase1_v26_semantic_action_calibration_execution.py | 单 Job 调用、证书、Raw、恢复、Commit、Observation 和终止 |
| v26.119 预检 | phase1_v26_semantic_action_runner_preflight.py | 脚本全路径、恢复、Usage、Raw recovery、破坏性测试和转移 Contract |
| v26.120 整批执行控制面 | phase1_v26_semantic_action_calibration_online.py | Source Replay、32-Job 调度、检查点、恢复、独立评分、聚合和报告 |

前六个相对路径以 trusted_data_synthesis/src/trusted_synthesis/ 为根；后四个实验文件位于
experiments/vtdo_experiment/。

### 2.2 权威冻结证据

- v26.117：48 条 Compiler 路径、324 个公开状态、276 个 Tool Call、48 个 Final 决策；
- v26.118：1,095 个 Candidate、228 个多 Candidate 状态、771 个合法替代动作；
- v26.118：48/48 静态完整路径上界为 209,836-366,495 tokens，冻结 400,000-token rollout；
- v26.119：32 个脚本 Job、256 个 Stage 1 fixture calls、224 个 Commit、192 个 Observation；
- v26.119：一个 ABI Rescue 后再发生 Semantic Recovery 的组合控制通过；
- v26.119：16/16 Runner 破坏性变异在零真实 Provider 调用下失败闭合；
- Git a55434e 新增并跟踪 v26.120 整批执行控制面及测试；本次聚焦测试 6/6 通过，四个
  Agent 核心/在线源文件的 focused Ruff 和 Mypy 通过；
- 当前唯一许可转移仍是 semantic_action_calibration_execution_only；
- 仓库中仍不存在 v26.120 在线执行目录或结果报告。

### 2.3 证据等级

本报告严格区分四类证据：

1. 代码事实：可由当前 Git 树中的类型、函数、调用顺序直接确认；
2. 冻结静态证据：v26.117-v26.119 的内容寻址 Artifact 和零 Provider fixture；
3. 历史经验事实：v26.110、v26.114 等已完成 Provider 实验，只用于解释设计演进；
4. 审计推断：例如崩溃窗口、共同实现偏差和扩展性风险，均显式标注为风险，不冒充线上故障。

## 3. 当前架构全景

### 3.1 控制面与数据面

~~~text
                         控制面

 Git 源码 + 历史 Artifact + Profile
                 |
                 v
          全量 Source Replay
                 |
                 v
  Candidate Authority / Resource Contract
                 |
                 v
 TaskPackage -> Path Audit -> Execution Contract
                 |                    |
                 +------> Manifest -> 32 Jobs
                                      |
                                      v
                         Runner Contract / Transition


                         数据面

 TaskPublicSpec + Environment + Observations
                 |
                 v
       build_semantic_action_state()
                 |
                 +--> Tool Grammars / Source References
                 +--> Operation Frontier
                 +--> Blocked Calls / Semantic Rejections
                 +--> Complete Visible Candidates
                                      |
                                      v
                        Salted Candidate Presentation
                                      |
                                      v
 Stage 1 Provider --four-field JSON--> Exact ABI Parser
                                      |
                                      v
                         Proposal Acceptance Gate
                              /               \
                             /                 \
                    typed rejection         accepted
                          |                     |
                  Semantic Recovery       Stage 2 Compiler
                                                |
                                      reversible same action_id
                                                |
                                                v
                                      Host Tool Execution
                                                |
                                                v
                                      Public Observation
                                                |
                                                +---- loop
                                                |
                                         Final readiness
                                                |
                                      Separate final-answer call
                                                |
                                      Raw Execution Artifact
                                                |
                              Verifier v3 / validity / mechanism
~~~

控制面决定“允许执行什么”；数据面决定“一个 Job 实际发生了什么”。两者使用内容寻址身份绑定，
模型不能在运行时更换模型 Profile、协议、候选语言、资源上界或 Task。当前缺口是数据面只实现
到 SemanticActionRawExecution，缺少正式运行的批量控制面和运行后聚合。

### 3.2 核心对象

~~~text
SemanticActionState
  ├─ tool_grammars
  ├─ variable_affordances
  ├─ source_references
  ├─ document_references
  ├─ operation_frontier
  ├─ acquisition_history
  ├─ active_blocked_public_calls
  ├─ blocked_actions
  ├─ action_candidates
  ├─ semantic_rejections
  └─ final readiness fields

CanonicalPublicAction
  ├─ acquire_public_input
  ├─ execute_public_operation
  ├─ verify_terminal_operation
  └─ emit_final_answer

CanonicalActionProposal
  └─ state_id + action_id + decision_kind

CanonicalActionCommit
  ├─ same state_id / proposal_id / action_id
  ├─ call_tool -> AgentToolCall
  └─ emit_final -> no Tool Call
~~~

关键 Pydantic Model 均设置 frozen=True 与 extra=forbid。身份字段通过去除自身后对规范 JSON
计算哈希生成。这使对象的字段集、父引用和内容变更可检测，但不提供第三方签名或外部时间戳
意义上的真实性证明。

## 4. 决策与执行流程审计

### 4.1 公开状态构造

build_semantic_action_state() 先调用旧版 build_public_action_state() 获取公开 Tool Grammar、
变量 Affordance、已解析 Binding、未解析 Symbol 和终止状态，再补充：

- 每个公开 Symbol 到 Evidence 或 Operation 的唯一 PublicSourceReference；
- 从已公开文档结果构造的 PublicDocumentReference；
- 四分 Operation Frontier：blocked_dependencies、dependency_ready、executable、
  terminal_verifiable；
- 所有历史 acquisition 事件；
- 所有失败调用的内容签名；
- 从合法动作集合中移除的 blocked actions；
- 至多一个公开 Semantic Rejection。

只有 executable Operation 会进入执行 Candidate；terminal_verifiable 只产生验证 Candidate，
不会重新作为 Operation 执行。这一分区修复了 v26.114 中“依赖已就绪但 Operand 尚未解析”的
Operation 被模型过早选择的问题。

### 4.2 Candidate 生成

| Decision kind | 模型实际选择 | Host 负责 |
| --- | --- | --- |
| acquire_public_input | Symbol、acquisition mode、已公开文档引用 | 按冻结 recipe 生成 wire arguments |
| execute_public_operation | 可执行 Node、Operator、规范 Source References | 将引用解码成 Evidence/Operation operands，并加入固定参数 |
| verify_terminal_operation | 一个非空 Evidence Reference 子集 | 构造 terminal operation claim 和 Evidence IDs |
| emit_final_answer | 是否进入 Final 阶段 | 另起最终答案请求，不由 Stage 2 填写答案 |

“模型拥有语义权限”的准确含义是：模型在 Host 预先物化的完整语义动作菜单中选择。模型不拥有
开放式参数构造权，也不能发明新 Tool、Node、Operator、Operand 或 Evidence。v26.118 Contract
已正确把测量对象限制为 public_state_interpretation_and_canonical_action_selection，并明确禁止
将其解释为开放式 Semantic Action 构造能力。

### 4.3 Candidate 完整性与展示

生产 Candidate builder 位于协议模块；另一个 enumerator 从公开状态字段重新生成可选集合，并
与生产列表按规范序列化逐项比较。Candidate 的 canonical order 按 action_id 排序，但 Prompt
展示顺序使用 Job、逻辑请求序号、状态和恢复计数派生的 salt 重新排序。

该设计满足状态身份不依赖展示顺序、展示顺序在 Provider 调用前绑定、删除合法干扰项失败、
blocked action 不可选以及禁止 Host alias normalization。但 v26.118 的顺序稳定性与同长度
opaque-ID 控制是静态参考策略控制，不是线上模型对位置、ID 形态或候选长度不敏感的经验结论。

### 4.4 Stage 1 响应 ABI

当前响应只允许：

~~~json
{
  "state_id": "<current state id>",
  "action_id": "<one visible action id>",
  "decision_kind": "<selected action kind>",
  "protocol": "prospective_semantic_action_exact_response.v1"
}
~~~

Parser 要求恰好四个顶层字段，拒绝 wrapper、extra field、missing field 和错误类型。固定 Stage
元数据已移出模型响应，成为 Host-bound metadata。这直接消除了 v26.114 中 27 个仅由固定 stage
常量造成的机械失败。

### 4.5 Proposal 接受与 Stage 2 Commit

evaluate_canonical_action_proposal() 仅使用当前 State、Proposal 和 call index：

1. state_id 必须等于当前状态；
2. blocked action 被识别为重复失败调用；
3. action_id 必须属于当前可见集合；
4. decision_kind 必须与 Candidate 一致；
5. 通过后才调用 _compile_action_call()；
6. 生成的 Call 必须能通过 decompile_canonical_public_call() 唯一映射回同一 action_id。

Stage 2 不包含 Provider Profile 或 Provider 路由。它的权限接近类型安全 adapter，而不是第二个
Agent。该边界是当前架构最强的部分。

### 4.6 Tool 执行与 Observation

Tool 由 Host 执行，模型不能使用 Provider-native tools。AgentToolSpec 验证必需和额外字段；
AgentToolResult 与 AgentToolObservation 分离业务结果、Evidence lineage、Host events 和错误。
公开业务结果会递归拒绝保留给 Host 的字段与 marker。

Finance Runtime 绑定只读 Archive Snapshot，当前 Manifest 要求 network_policy=forbidden。因此
即使模型受到文档文本影响，也无法越过 Candidate 和 Tool Manifest 发起任意网络或系统操作；
主要剩余影响是选错合法动作或生成错误最终答案。

### 4.7 双恢复通道

每个 Job 最多具有一个全局 ABI Rescue 和一个独立 Semantic Recovery。前者处理 Completion
failure、JSON/channel parse 或四字段 ABI 失败；后者处理 stale state、未知 action、decision
kind mismatch 或 blocked identical call。

Semantic Rejection 是公开、action-neutral、非终止的 Observation，不暴露正确动作、参数 patch
或精确失败 arguments。第一次错误不会因恢复成功而从 SemanticChoiceRecord 中消失。两个计数
彼此独立，但第二次同类失败会结束 Job。

### 4.8 Final 阶段

模型先选择 emit_final_answer Candidate，表示公开状态已达到 Final readiness；随后 Runner 使用
compact final Prompt 发出单独最终答案请求。最终答案至少要求已有公开 Evidence citation。

这里的“完成”只表示 Runtime 产生结构化 Final Result；科学有效性仍必须由 Verifier v3、独立
validity 和 mechanism scoring 决定。v26.119 fixture 做了这些检查；v26.120 已实现整批运行后
的结果投影与报告聚合，但尚未产生真实在线 denominator，不能把实现存在写成经验通过。

## 5. Provider、资源与持久化边界

### 5.1 精确 Provider 路由

Stage 1 只允许 DeepSeek、固定 Endpoint、deepseek-v4-flash、max_tokens=16384、
thinking.type=enabled、JSON object response format、一个模型尝试、无 fallback、无 discovery、
无 generic contract repair。普通 complete_json() 入口直接失败；必须提交与实际 Prompt 和规范
请求体完全一致的单次证书。

### 5.2 reasoning 隐私

Provider response 在严格内容投影前提取 response model、finish reason、public content hash/length、
native tool presence、reasoning presence/length/tokens 和 Usage。reasoning 正文、reasoning hash、
Raw HTTP body 和 Raw request body 都不持久化。

该保证的准确含义是“Provider reasoning channel 不落盘”，不是“任意模型可见 JSON 中不可能
出现带分析含义的文本”。当前 Raw payload 会拒绝字段名包含非注册 reasoning 的对象，但不能
从语义上识别所有同义内容。

### 5.3 资源证书

~~~text
prompt upper bound      = UTF-8 bytes + 256
completion accounting  = 16,384 + 1
request upper bound     = prompt upper bound + 16,385
projected total         = cumulative actual usage
                        + current request upper bound
                        + remaining ABI reserve
                        + remaining Semantic Recovery reserve
                        + Final reserve
~~~

16,385 Completion tokens 可被承认但完整计费；16,386 或更高属于 Instrument failure。实际 Usage
不裁剪。把 UTF-8 bytes 当 token 上界会高估资源，但对防止越界是安全方向。

### 5.4 Raw-first 与恢复

对成功返回的调用，Runner 先写 RawActionProviderCall，再进行四字段 ABI 和语义投影。完整
SemanticActionRawExecution 可零调用重放；若发现 Provider 文件而没有完整 Raw Execution，则
作为 orphan 失败闭合，不自动重试。

该机制覆盖“响应已返回并已写 Provider Artifact，随后 Job 未完成”的场景；它没有覆盖“请求已
发出但 Provider Artifact 尚未成功写入”的场景，详见 F-01。

## 6. 信任边界与威胁模型

| 边界 | 已有控制 | 剩余风险 |
| --- | --- | --- |
| Oracle -> Public | Public Task 类型隔离、私有 key denylist、AST forbidden-symbol audit | denylist 和符号扫描不能证明语义级非干扰 |
| Host -> Model | 只发送公开状态、Candidate、typed failure；不发送正确动作或 patch | Host 枚举定义闭世界，测量对象不是开放式规划 |
| Model -> Host | 精确四字段 ABI、当前 state binding、Candidate membership | 合法但错误的动作仍是模型结果；Prompt injection 可影响选择 |
| Stage 1 -> Stage 2 | 同一 action ID 可逆 Commit，Stage 2 零 Provider | 编译器和独立 enumerator 仍共享部分类型与假设 |
| Host -> Tool Runtime | Tool Manifest、规范 Arguments、离线 Snapshot | 工具类型检查部分依赖具体 Runtime |
| Provider -> Artifact | exact-model/Usage/Thinking telemetry、Raw-first redaction | 调用到落盘之间存在不确定崩溃窗口 |
| Raw -> Verifier | Verifier v3 Replay、独立 validity、机制评分和 v26.120 聚合入口 | 仅有脚本测试，尚无真实在线 denominator |
| Artifact -> 审计者 | 内容哈希、父身份、Source Replay、Git | 内容寻址不等于外部签名或可信时间戳 |

恶意或失常模型最多能返回错误 ABI、stale/unknown/mismatched action、选择合法但错误的动作、
重复失败动作、过早 Final 或错误最终答案。Candidate 和 Runtime 阻止权限扩大；错误最终答案仍
依赖运行后的独立 Verifier 拒绝。

Archive 文档与公开 semantic record 会进入 Prompt。当前没有单独的内容级 Prompt injection
classifier 或 provenance-aware instruction/data delimiter Contract。由于动作空间闭合且工具离线，
注入无法直接获得任意执行能力，但仍可能改变合法选择分布、诱导 ABI failure 或污染最终答案。
若未来接入网络或有副作用工具，必须在扩大权限前重做威胁模型。

## 7. 主要优势

1. 权限最小化且边界可逆：模型只选择 Candidate，Commit 必须反编译回同一动作。
2. 当前状态足以决定接受集合：Proposal 接受不读取 Oracle 或 Reference Workflow。
3. 机械 ABI 与语义错误分离：两类恢复不会相互覆盖，第一次语义失败被保留。
4. 资源和 Provider 约束前置：Profile、Prompt、request body、Usage 和 reserve 都有证书。
5. 历史证据不被新协议重写：新协议使用新身份，旧终止分类保持不变。
6. 破坏性测试覆盖较广：包含 Candidate 删除、身份变异、预算边界、Raw recovery、orphan、
   双恢复和 Stage 2 零 Provider。
+
## 8. 风险发现

### F-01 高：Provider 调用缺少持久化 write-ahead intent，exactly-once 暴露不能闭合

代码事实：JournaledSemanticActionClient.prepare() 在内存中创建证书；invoke() 随后直接调用
Delegate；Delegate 返回或抛错后才由 _persist() 写 RawActionProviderCall。_used_preparations
也是进程内集合。write_json_atomic() 使用临时文件加 replace()，但没有在 Provider 调用前落盘
invocation intent，也没有文件或目录 fsync。

风险推断：若进程在以下窗口崩溃：

~~~text
Provider 已收到请求
        -> Provider 已计费或已产生响应
        -> 本地尚未写出 RawActionProviderCall
~~~

重启后既看不到完整 Raw Execution，也看不到 orphan Provider 文件，现有逻辑会把 Job 当作从未
调用并可能再次发出同一请求。由此无法仅依赖当前 Artifact 证明“每个 Job 身份只暴露一次”。

影响：

- 可能重复模型暴露和重复计费；
- 破坏冻结 denominator 的 exactly-once 解释；
- 发生时无法区分“未调用”和“调用结果丢失”；
- 当前 orphan 测试不能覆盖这个无文件窗口。

建议在任何真实 v26.120 调用前增加持久化 write-ahead invocation ledger：

1. 原子写入并同步 prepared/in_flight 记录；
2. 记录 Job、logical index、Prompt hash、全部证书、单次 nonce；
3. 同步文件和目录后才允许网络调用；
4. 收到响应后写 Provider Artifact，再将 intent 标记为 completed；
5. 重启发现未决 intent 时禁止自动重试，进入“暴露状态不确定”的专门 Recovery Contract；
6. 若 Provider 支持 idempotency key，将 nonce 同时发送；若不支持，仍应按最保守方式退休该
   Job，而不是推断未调用。

这一修复会改变已绑定 Runner 字节，必须使用新身份并重新完成零 Provider 预检。

### F-02 中：v26.120 整批控制面已纳入 Git，但尚无独立执行前 Artifact 或在线结果

审计开始时 HEAD 4be1a3d 中只有 phase1_v26_semantic_action_calibration_execution.py 的单 Job
kernel；校验期间，仓库并发提交 a55434e 将
phase1_v26_semantic_action_calibration_online.py 及其测试纳入 Git。本报告未创建或提交这两个
文件。只读审阅确认该实现已包括：

- 在 profile parsing、credential lookup 和 client construction 前重放 2,228 个绑定文件；
- 32-Job preexecution validity fixture；
- 精确 Client factory、prepare-only 和 main()；
- ThreadPoolExecutor 有界并发；
- canonical checkpoint 和完整运行零调用恢复；
- Job-level choice diagnostics 与 result projection；
- Verifier v3、独立 validity 和 mechanism scoring；
- Raw Lineage、Cell/Decision load summaries 和 Outcome Funnel 聚合；
- 完整 denominator 后生成 report.json；
- 对 ABI Rescue 与 Semantic Recovery 分离的额外测试。

因此，“整批执行实现缺失”已不再是当前 Git 树事实。当前剩余证据缺口是：a55434e 只提交了
执行实现和测试，没有随提交生成正式 v26.120 执行前 Artifact、双构建报告或在线结果；其
Source Replay 会在执行阶段绑定自身，符合历史执行模块模式，但尚不能证明完整真实 denominator
已经运行。更重要的是，源码进入 Git 并未解决 F-01 的 durable intent 问题。

建议：

1. 本次 focused Ruff、Mypy 和 Pytest 已通过；另行完成独立双构建和 exact prepare-only 审计；
2. 将其作为明确的 v26.120 execution implementation 身份纳入执行前 Source Replay；
3. 校验 prepare-only 确实在 credential lookup 前结束；
4. 增加 F-01 所列崩溃注入和跨进程单次授权测试；
5. 修复后使用新的干净 Git 基线和内容身份，不能沿用 a55434e 的执行身份；
6. 不把脚本客户端 32/32 结果写成真实 Flash 可用性证据。

### F-03 中：当前实现对历史实验模块和私有函数耦合过重

当前 Runner 将旧 phase1_v26_two_stage_semantic_proposal_execution 整体别名为 legacy，复用其
Model Config、Request Certificate、Telemetry、Raw descriptors、Runtime Binding、hash/load、
final rescue，并直接调用 _runtime()、_execute_observation() 和 _selected_evidence_ids()。

这对短期实验继承有两个优点：历史语义不漂移、既有 Artifact 可重放。但长期问题是：

- 新协议依赖旧实验文件的内部布局而不是稳定 Runtime API；
- 私有函数改名或清理历史代码会改变当前 Runner；
- 通用 Runtime 与实验版本层混杂，难以确认哪一层是生产实现；
- 五个 v26.117-v26.119 主文件合计约 6,971 行，身份模型、实验组装和 Runtime 控制重复较多；
  v26.120 在线控制面又增加约 2,039 行实验控制代码。

建议在下一次新身份协议中，将 Provider certification、Raw journal、resource ledger、Runtime
binding、Observation execution 和 Verifier projection 抽到稳定非实验模块。历史实验模块保持
只读，新实验只依赖稳定公共接口和明确版本化 adapter。

### F-04 中：Candidate “独立枚举”仍有共同实现偏差风险

独立 enumerator 确实不读取待测 Candidate list，这是有效差分控制；但它仍与生产 builder：

- 使用同一个 SemanticActionState；
- 使用同一个 CanonicalPublicAction Schema 和身份算法；
- 重复相同 acquisition recipe、frontier 和 verification-subset 假设；
- 位于同一代码库并由同一个 build 函数执行。

AST audit 检查七个函数是否读取特定 forbidden symbol，不能证明通过别名、间接 helper、派生字段
或等价语义泄露不存在。formal/independent build 主要证明确定性和字节复现，并非两个实现栈的
独立复核。

建议增加最小的真正独立 verifier：只消费序列化 Public State、Tool JSON Schema 和 Operation
Contract，不导入生产 Candidate builder 或 helper，并做以下 property test：

~~~text
enumerator set == validator-accepted set
compile(action) -> decompile(call) == action
blocked(action) -> action not visible
~~~

### F-05 中：公开/私有隔离以 key denylist 和 AST 名称扫描为主

_reject_private_keys() 会递归拒绝已知私有字段名，这是有价值的 fail-closed 控制；但
semantic_record、public metadata 或新字段可以用未登记名称携带等价信息。AST audit 同样只能
阻止已知名字直接读取。

风险不是当前 Finance fixture 已经泄漏，而是未来 Schema 扩展时，开发者可能误把“denylist
通过”解释为“Oracle 非干扰已证明”。建议改为 capability-based public projection：每个公开
字段必须来自显式 allowlisted typed constructor，禁止任意 dict 直接穿过边界；并建立双运行
noninterference test——只改变 Oracle/Gold/Reference 数据时，公开字节必须不变。

### F-06 中：Verification Candidate 枚举是指数型并带硬编码 8-Evidence 上限

终止可验证时，当前实现枚举所有公开 Evidence References 的非空子集，复杂度为 2^n - 1；
Evidence 数超过 8 时直接失败。当前 324 个状态的最大 Candidate 数为 8，因此静态样本安全，
但这不是一般扩展性保证。

不能通过 Host 后验删减“看起来错误”的 Evidence 组合修复，否则会引入语义选择。未来可让模型
先选择验证策略，再通过第二个有界、可逆阶段选择 Evidence；或使用公开、任务无关的组合语法，
同时保持 Host 不选择证据。任何改变都必须重做 Candidate authority 和资源资格。

### F-07 中：稳定内容地址可能形成跨状态线索，线上位置/ID 不变性尚未测量

action_id 是完整动作内容的 SHA-256 内容地址，不是真正随机的不透明 token。相同动作语义会
产生稳定 ID；低熵动作空间还可离线枚举。当前模型同时看到 Candidate 内容，所以主要风险不是
保密，而是跨状态记忆、ID 相关策略和实验分布偏差。

v26.118 的 opaque relabeling 与展示 salt 控制只证明参考策略保持语义，不证明线上模型不利用
位置或稳定 ID。v26.120 应保留 Candidate position 并报告 first-choice 结果，不能把静态控制
当作模型不变性证据。当前协议禁止 Host alias normalization，不能在执行时临时加入。

### F-08 中：失败闭合优先于可用性，单 Job 崩溃会使整批进入恢复审计

当前不做 transient retry；完整 Raw 可重放，任何 orphan 直接阻止重试。这符合科学实验中避免
重复暴露的优先级，但一次本地 I/O、进程退出或网络不确定性就可能阻塞完整 32-Job denominator。

完整控制面需预先冻结 HTTP 明确失败是否允许 retry、HTTP 成功但持久化失败如何退休 Job、未决
intent 如何分类、部分 denominator 是否禁止计算比例，以及是否只能通过新 Recovery Contract
继续未打开 Jobs。这些规则不能根据观察到的成功率临时决定。

### F-09 低：顶层架构文档和 CLI 未反映当前主线

docs/architecture.md 仍标记 Architecture v0.7；README 的 Active Method Boundary 仍以
vtdo_experiment.v6 为中心。两者都没有当前 State、Candidate、双恢复、两阶段、Raw journal
和 Verifier v3 数据流。

当前 Semantic Action 构建与预检也未注册到 trusted-synthesis CLI，主要通过模块直接运行。
这增加了选错历史 Runner、漏掉 prepare-only 或使用非冻结参数的风险。完整 Runner 冻结后应
提供绑定明确的 CLI，默认先 prepare，并禁止覆盖模型、Profile、Completion、rollout、recovery
和 Manifest。

### F-10 低：内容寻址保证一致性，但外部真实性信任根未显式建立

Artifact 通过内部哈希和 Git 历史形成强一致性链，但 scoped implementation 中没有独立签名、
透明日志或外部时间戳。若攻击者能同时改写根报告、预期哈希和 Git 历史，自洽重放不能证明原始
真实性。在受控单仓库环境中这是低优先级风险；跨组织审计或发布前，建议对顶层报告、Manifest
和 Source Replay root 离线签名，并将签名或 Merkle root 发布到仓库外不可变位置。

## 9. 风险优先级

| 优先级 | 项目 | 处理要求 |
| --- | --- | --- |
| P0 | F-01 durable invocation intent | 真实 Provider 调用前解决并重新预检 |
| P1 | F-02 v26.120 在线控制面证据闭合 | 对已跟踪实现完成独立静态校验、双构建和执行前身份冻结 |
| P1 | F-03 历史实验私有 API 耦合 | 下一协议代际抽取稳定 Runtime，不回改历史 Artifact |
| P1 | F-04 独立 Candidate verifier | 降低同源实现的共同偏差 |
| P1 | F-05 typed public projection | 将非干扰保证从 denylist 提升为 allowlist/capability |
| P1 | F-08 失败与恢复状态机 | 调用前冻结不确定暴露和部分 denominator 处理 |
| P2 | F-06 Candidate 扩展性 | 新任务扩大 Evidence 数前解决 |
| P2 | F-07 线上位置/ID 诊断 | v26.120 只测量并保留，不做后验协议修改 |
| P2 | F-09 文档与 CLI | v26.120 执行身份最终冻结后统一维护入口 |
| P3 | F-10 外部真实性锚 | 跨组织或发布前引入 |

## 10. 建议的下一版闭环

### 10.1 调用前

~~~text
replay all bound bytes
-> parse exact Profile/Contract/Manifest
-> verify 32 exact Jobs and zero completed report conflict
-> inspect durable checkpoint and invocation intents
-> only then read credential and construct client
~~~

### 10.2 每个 Provider 调用

~~~text
render actual Prompt
-> bind state + candidate order
-> build exact request-body certificate
-> build resource certificate
-> durably persist single-use invocation intent
-> fsync file and parent directory
-> invoke Provider with idempotency key when available
-> persist redacted Raw Provider artifact
-> mark intent completed
-> project ABI / semantic result
~~~

### 10.3 每个 Job

~~~text
Raw Provider sequence
-> Attempts
-> First choices
-> Rejections and recoveries
-> Commits
-> Observations
-> Final result
-> Verifier v3 Replay
-> independent validity
-> mechanism/path scoring
-> canonical JobResult checkpoint
~~~

### 10.4 整批结束

只在以下条件全部满足后生成报告：

- 32/32 Job identities 恰好出现一次；
- 没有 unresolved invocation intent；
- 每个 Provider call 都有调用前证书和 Raw descriptor；
- 所有累计 Usage 与资源 Contract 一致；
- Stage 2 Provider calls 为零；
- 每个 Raw Execution 可独立重放；
- first choice 与 eventual recovery 指标分离；
- Verifier v3、独立 validity、mechanism/path 指标完成；
- 未完成或 Instrument 行不被静默排除；
- 报告只给出 executable_behavior_under_canonical_semantic_action_interface 范围内的解释。

## 11. 建议增加的测试

本次运行三个已跟踪的 focused test 文件，共 6 个测试：覆盖 v26.117 协议、v26.118-v26.119
重物化与 Runner，以及 v26.120 脚本整批执行和双恢复，结果为 6/6 通过。四个 Agent 核心/在线
源文件的 focused Ruff 和 Mypy 也通过。建议继续新增：

1. Provider 调用前进程退出：必须留下 unresolved intent，重启不得调用；
2. 请求发送后、响应前退出：必须进入暴露不确定状态；
3. 响应返回后、Provider Artifact rename 前退出；
4. Provider Artifact 写入后、Raw Execution 写入前退出；
5. 临时文件存在、目标文件不存在以及目录未同步的恢复；
6. 两个进程并发打开同一 Job，最多一个获得持久化授权；
7. 31/32、32/32、重复第 32 行、未知 Job 和跨 Contract checkpoint；
8. Verifier v3 exception 不得改变已经冻结的 Raw terminal；
9. 修改 Oracle-only 数据后 Public State bytes 必须不变；
10. 随机小状态下生产 Candidate 与独立 enumerator 双向集合等价；
11. Evidence 数为 8 和 9 的边界行为；
12. Prompt injection fixture 只能影响合法选择，不能扩大 Tool/Arguments 权限；
13. Final answer 无 Evidence、错误 Evidence、正确格式错误语义和正确语义四类分离；
14. 真实执行 prepare-only 必须在 credential lookup 和 client construction 前完成。

## 12. 最终结论与声明边界

当前 Agent 架构在“闭世界公开动作选择”这一明确目标上合理且严谨。它通过 Candidate Authority、
精确状态绑定、强 ABI、可逆 Stage 2、Host Tool Runtime、双恢复和资源证书，把过去主要的 wire
grammar 与不可执行动作问题前移到静态构造阶段，设计质量明显高于旧版自由 Arguments Agent。

但以下陈述目前不能成立：

- “v26.120 已执行”——没有执行 Artifact；
- “真实 Flash 已经能使用 Semantic Action Interface”——只有脚本控制通过；
- “当前整批在线 Runner 已有正式经验结论”——实现虽已进入 Git，但尚无正式在线执行 Artifact；
- “每个 Provider 调用在崩溃下仍可证明 exactly once”——缺少 durable pre-call intent；
- “该协议证明开放式 Agent 规划能力”——模型只在 Host 枚举的动作菜单中选择；
- “静态顺序/opaque-ID 控制证明线上模型不受展示影响”——尚无在线证据；
- “内容哈希等于第三方真实性证明”——当前信任根仍是 Git 与受控操作环境。

本报告不改变 v26.119 的冻结 Artifact、历史终止分类或许可转移，也不授权 Provider 调用、历史
重跑、协议修改、角色实验、State Mapping、训练、发布或生产 Contribution。P0 建议会改变
Runner 源码，因此如被采纳，应在新身份链中重新预检，而不是修改 v26.117-v26.119 证据。
