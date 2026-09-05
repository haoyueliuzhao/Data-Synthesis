# Share 公开协议真实模型适配与固定六会话工程试验

## 1. 文档状态与本轮问题

阶段名称：`finance_qa_vnext_share_public_protocol_model_adapter_and_six_session_engineering_pilot`。

本文件首先登记设计、边界与执行前检查。首次编写时，适配层的 20 个隔离单元用例已经通过；本轮正式的两个完整 adapter/mock 控制、两个单轮失败控制以及六个在线会话均尚未执行。以下标为“计划”“预计”“上限”的内容不是实际结果。正式执行后的计数、源码身份、目录身份、逐会话结果与结论，应以本文件的结果节和对应原始工件为准，不得从预期路径推算。

本轮只回答一个问题：在固定任务、公开信息、工具与协议下，真实模型能否以自己的公开提交完成 Action、显式 Observation Update 和 Final，且 Host 不代替它选择语义内容或修复输出？

“工作流完成”和“模型成功”是不同对象。六个会话不必全部成功，也不要求两种依据使用方式都出现。完整记录的模型失败可以成为本轮的有界负结果；自动补全 Claim、隐式重写响应、失真的请求来源或缺失的失败记录则是接入机制缺陷，不能被正确答案抵消。

## 2. 审计、授权和前驱边界

外部审计接受前一阶段的限定声明 `PASS_AS_SCOPED`，未提出强制修订。它接受的是固定策略 fixture 下公开回调和显式 Update 的最小协议接通，不是模型接入或模型自主依据选择。前驱说明见 [公开 State 与显式 Update 协议报告](finance_qa_vnext_share_public_state_proposal_action_observation_update_protocol_preflight.md)。

本轮审计输入按原始字节绑定：27,072 bytes，SHA-256 为 `1fc713f450529c16094ca7ff63c69b2d6b5f2342908151c0bf3f678c6d590b0f`。审计文本本身只提出方案、不授予在线执行权。本轮执行依据是当前“参照审计开展后续实验”的操作指令与项目已经明确给出的 API 资源授权；准备记录必须把这两类来源分开，不能从前驱 PASS 自动推导授权。

前驱公开协议工件身份为：

```text
manifest = public_share_protocol_manifest:8935da52f4f8146c290a5f9875e1e319b4e9f3d7d347efe4dec07aed163dbb66
root     = public_share_protocol_root:69c83461068a0ff5c583e93b05b7dab59455d92e12606c389f2105ba075100de
source commit = 606b13c35cb3aca4107ee5497451ba51378bb843
source tree   = 6736228347d4d8519c7ac099378a409dc45b8053
```

新阶段建立新的模型配置、协议条件、适配器登记、调用和会话身份，不覆写前驱正式 JSON 或历史结论。冻结输入来自既有工件，不重新扫描来源材料，不重跑旧候选 Runtime，不增加旧 D/S 商比较或重新证明两类行为存在。

本轮不扩张到训练、GPU 作业、更多任务、定向提示对照、通用 Mapper、State Catalog 或旧主链重启。较早任务的 `W=null` 不改变；本轮新的语义类数、类概率和 VTDO 收益不作估计。后继阶段不会因本轮结束而自动获得授权。

## 3. 保持不变的任务与公开协议

Task、四项 Evidence（F、O、T 和 part-whole 关系）、`relation_sum`、`share_ratio`、`scale_percent` 的语义与准入规则、Decimal 精度、舍入和答案容差均保留原合同。每个会话仍限制为 3 Action、3 Update、12 Submission；单条公开响应上限仍是 32,768 UTF-8 bytes。

每轮公开内容完全来自既有 `request_for(State)`，包括当前 State、合法提交种类、实际阶段 schema、公开操作规则与剩余预算。Action 阶段的 Action/Final 选择以及 Update 阶段的独立提交要求不被适配器缩减。

生成器必须自己提供以下语义内容：

- Action：operation、带角色的 inputs、parameters 和 public basis。
- accept Update：observation 引用和完整 proposed Claim，包括 value、metric、definition、subject、scope、period、unit、currency、lineage。
- reject Update：明确的拒绝 disposition 与对应公开 basis。
- Final：已接受 Claim 的引用、答案、citations 和公开 basis。

Host 保留状态发布、引用/类型/来源准入、数值执行、Observation、提交内容核验、工件持久化和内容身份生成的职责。Action 执行后只增加 pending Observation，不增加 accepted Claim；只有后续独立且准入的 accept Update 才新增可消费 Claim。合法 reject 会清除 pending，但不会产生被接受的 Claim。

公开请求不传入旧 Final、答案实例、Oracle、D/S 标签、目标类、候选脚本或预制执行节点。后续真实工具 Observation 中出现计算值属于当前公开状态，而不是事前给答案。这里的 Update 仍是完整 Observation 命题的接受或拒绝，不声称实现了任意命题推导、部分接受、旧 Claim 修订或一般信念更新。

## 4. 模型配置及官方资料

配置权威为 [models.py](../src/trusted_synthesis/experiments/qa_reasoning_share_model_pilot/models.py) 的 `model_config()`。首次在线调用前必须完成配置和源码冻结；看到输出后不得在同一试验身份下调整模型、提示词、温度或 token 预算。

2026-09-05 核对的官方模型页列出请求名 `deepseek-v4-pro`，对应文档版本 `DeepSeek-V4-Pro-0813`。本轮记录两者，但不把文档版本称为可请求的 immutable snapshot，也不声称固定了 Provider 内部权重。来源：[DeepSeek Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/)。

| 条件 | 本轮固定值 |
| --- | --- |
| 请求端点 | `https://api.deepseek.com/chat/completions` |
| 请求 model | `deepseek-v4-pro` |
| 文档版本 | `DeepSeek-V4-Pro-0813`，不是可请求的不可变快照承诺 |
| 允许的实际响应 model 字符串 | `deepseek-v4-pro`、`deepseek-v4-pro-0813` |
| thinking | `{"type":"disabled"}` |
| temperature / top_p | `0.7` / `1.0` |
| max_tokens | `8192` |
| response_format | `{"type":"json_object"}` |
| stream | `false` |
| 原生 tools / function calls | 不启用 |
| 总超时 / 连接超时 | 180 秒 / 30 秒 |
| 自动重试 / 重定向 / 模型回退 | 0 / 0 / 0 |

官方 Thinking Mode 文档区分 `content` 与私有 `reasoning_content`，并说明 thinking 可显式禁用。本轮选择 non-thinking 条件，不请求或回传私有推理；即使响应意外附带该字段，也不持久化、不计算其摘要。来源：[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)。

JSON Output 只解决 JSON 输出形式，不能替代本项目的 Action/Update/Final schema 与语义准入。官方文档仍提醒空内容与截断情况。本轮提示中明确要求 JSON，并给出既有权威 schema；不添加路线示例或答案实例，也不因空内容修改提示或补发请求。来源：[JSON Output](https://api-docs.deepseek.com/guides/json_mode/)。

请求/响应字段及结束原因依据 [Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)。这里允许的是一个精确请求模型配置；响应模型白名单用于核验返回身份，不意味着允许在两个模型间切换。`received_model` 保留实际返回值，缺失或不在白名单时终止为 `provider.model_identity_mismatch`，不能拿请求名补成实际模型名。`system_fingerprint` 有则保存受限字符串，无则为 null；它也不构成独立的权重证明。

本轮不依赖模型自动发现、旧运行器默认模型或模型回退，不为获取身份先增加一个模型探测调用，也不根据价格页面估算实际账单。未来重跑时官方别名可能已指向新版本，应建立新的条件身份，不能把本次配置名称当作跨时间的权重固定保证。

## 5. 请求、来源和传输链

实际实现见 [adapter.py](../src/trusted_synthesis/experiments/qa_reasoning_share_model_pilot/adapter.py)。每轮 stateless 呈现只有两条消息：固定中性 system message，以及完整当前公开 Request 的 canonical JSON user message。不给模型以前的私有推理，不读取其他会话作为示例，不添加第二份手写近似 schema。

请求工件保存实际 HTTP body 的精确 UTF-8 JSON、摘要、字节数、公开 Request/State/phase、session/turn/call parent、端点和模型配置身份。body 包含 model、messages、thinking、temperature、top_p、max_tokens、response_format、stream，没有原生 tools 字段。

关键顺序为：

```text
当前 PublicState
  → request_for(State) 的完整公开 Request
  → 确定性 wire body + 请求工件
  → durable Provider attempt reservation（写入并读回）
  → 登记的 CurlTransport.send，仅一次 HTTP POST
  → 受限 envelope 核验与 message.content 提取
  → 原样严格 Parser
  → Submission / Receipt
  → admitted Action execution 或显式 Update / Final
  → 下一公开 State
```

`DeepSeekAdapter.perform` 与 transport 的实际 bound method 绑定到 module、class、method、源文件字节及编译所得方法代码。`CurlTransport` 的来源为 `model`；独立登记的 `MockTransport` 的来源只能是 `adapter_mock`。公开 JSON 不能靠自报 `origin=model` 获得模型身份，Mock handler 也不能作为在线失败的备用生成器。

这个检查覆盖本轮声明的适配器/回调来源与执行链，不是完整传递依赖或运行环境闭包，也不是 Provider 对响应签署的密码学证明。正式 source authority 应列出声明的实现和引用文件及其 commit/tree，不应把未覆盖的库、curl 二进制、远端服务或运行环境描述为已经全部冻结。

传输使用单独的 curl 子进程，不继承项目旧客户端的自动发现、重试、代码围栏清理或 fixture 回退。参数固定禁止 curlrc、重试和重定向，设连接/总超时及 HTTP body 大小限制。精确 body 通过标准输入发送；认证 header 通过继承的匿名管道传入，不出现在 argv、请求工件或磁盘 header 文件中。stderr、异常字符串和整个 HTTP envelope 不落入正式记录。

预留 attempt 后即使发生超时、HTTP 错误或没有公开内容，该 attempt 仍然被消耗。curl 总超时和父进程 watchdog 共同避免只依赖“读空闲超时”而被持续空白数据无限延长。传输失败不重发、不更换模型、不调用 mock。

## 6. 资源预算与两个独立计数

| 预算项目 | 每请求/每会话 | 全在线试验 |
| --- | ---: | ---: |
| 正式会话数 | — | 6 |
| 并行会话数上限 | — | 6 |
| Action / Update | 每会话 3 / 3 | 各最多 18 |
| 公开 Submission | 每会话最多 12 | 最多 72 |
| Provider attempt | 每会话最多 12 | 最多 72 |
| 实际序列化请求 body | 每请求最多 65,536 bytes | 不用它替代累计 token 账本 |
| 输入 token 准入预算 | 每请求 66,560 | 按每次预留累计 |
| 输出 token 请求上限 | 每请求 8,192 | 按每次预留累计 |
| 单次预留 token allowance | 74,752 | 最多 5,382,144 |
| 会话预留 token allowance | 897,024 | 六会话最多 5,382,144 |
| 公开 message.content | 每响应最多 32,768 bytes | 逐条 Parser 检查 |
| 整个 HTTP response body | 每请求最多 2,097,152 bytes | 不持久化整个 body |
| GPU 作业 | 0 | 0 |

离线输入准入规则是“实际序列化请求 UTF-8 字节数 + 1,024 allowance”；它是本轮的保守预算规则，不声称执行了官方模型的精确离线分词。32,768 bytes 是公开提交的字节限制，绝不能称作 32,768 tokens。官方说明实际 token 用量以响应 `usage` 为准，通用字符比值不能替代实际计量。来源：[Token & Token Usage](https://api-docs.deepseek.com/quick_start/token_usage/)。

每次 attempt 在发送前预留固定的 74,752 tokens；失败也不回收预留额度以产生额外调用。实际 usage 的 prompt、completion、total、cache hit/miss 和 reasoning token 数分别保留；缺失保持 null，不补成 0，也不把预留数冒充实际 token 消耗。

如果实际返回的 prompt、completion 或 total 超过各自冻结限额，记录 `provider.actual_token_cap` 并停止该会话；三项均存在但 prompt + completion 不等于 total 时记录 `provider.usage_inconsistent`。这些是响应到达后的观测检查，不能倒推未返回 usage 的超时请求没有消耗 tokens，也不能撤销已经发生的远端使用。额度账本与实际 usage 必须分列。

Provider attempts 与 Submission 是不同计数：

- 收到公开文本，包括空字符串、非法 JSON 或缺字段 JSON：消耗 attempt；形成公开 Submission 和类型化 Receipt；按原合同计入 submission_count，可在剩余预算内继续。
- 没有公开内容，包括超时、HTTP/envelope 失败或 content 缺失/null：消耗 attempt；不伪造 Submission/Receipt，不增加 submission_count，按类型化原因结束。
- 已有有效 Final 或其他终止状态：不为耗尽额度继续调用。

因此，12 次是 Provider attempt 的硬上限，不是保证运行 12 次的目标；72 是六个固定会话的总上限，不是允许失败替换的额外池。

## 7. 响应边界、无修复规则和证据层级

envelope 必须有单条 choice、非空 response id、`object=chat.completion`、`index=0` 和 assistant message。HTTP 非成功状态、非法 JSON envelope、不可用公开 content、模型身份不符等均使用有限的类型化代码，不保存远端错误 body 或 Python 异常文本。

本轮登记的 finish_reason 有限集为 stop、length、content_filter、tool_calls、insufficient_system_resource。原生 tool call 被禁止；资源中断作为类型化传输失败结束。stop/length/content_filter 若确有公开 content，仍将该字符串原样交给严格 Parser，不能把 length 自动修成完整 JSON，也不能把字符串截取成看似合法的局部对象。

适配器不移除 Markdown 围栏、不从长文抽取 JSON 子串、不重命名字段、不填默认 operand 或 basis、不构造缺失 proposed Claim、不替模型添加 citations。深度受限 JSON 解析产生的 `RecursionError` 映射为 `schema.public_submission` 接收端诊断，不改变旧合同的有效语法。

| 响应类别 | 持久化证据 | 可以核验的对象 | 不能声称的对象 |
| --- | --- | --- | --- |
| 通过严格 schema 的公开 JSON | 原始公开 JSON、解析对象、hash/bytes、后续事件 | 从已保存公开原文独立重放结构、引用与语义 | 模型内部思维过程 |
| 未通过 schema 的公开文本 | 仅公开文本 hash/bytes 和 typed parser code | 接收端记录了该摘要的格式失败及后续计数/状态 | 仅靠 hash 独立复验原文究竟少了哪个字段 |
| transport 失败 | attempt、请求 parent、安全错误代码及终止 | 有界尝试和停止的接收端观测 | 没有返回 usage 就代表零 token 消耗 |
| envelope 失败 | 安全元数据、typed code、无公开提交的终止 | 接收端 envelope 诊断和关联 | 对未保存 envelope 的原文逐字重放 |
| 请求关联、终止或工件缺失 | evidence incomplete / UNKNOWN | 明确指出缺失环节 | 擅自补成一次普通模型失败或零成功 |

对应 evidence_level 分别是 `public_submission_replayable`、`receiver_diagnosis_only`、`typed_transport_observation` 和 `receiver_envelope_diagnosis_only`。失败证据的独立性弱于有原文的公开提交重放，报告不能混称为“全部原始响应已独立验证”。

整个 HTTP envelope 只短暂存在于内存，不保存其原文或整体摘要。`reasoning_content` 不作为公共 content 的备用来源，不保存、不哈希、不参与下一轮提示。usage 中的 reasoning token 计数可以记录，但它不等于保存私有推理文本。

每轮响应记录绑定 session、turn、call、公开 Request、HTTP request、State、phase、模型配置、transport 和 attempt，同时记录实际模型字符串、可选 fingerprint、finish_reason、usage、公开内容 hash/bytes、parser status/code。Engine 应核对这些 parent 与实际 raw bytes，并检查自身重新解析结果与适配器诊断一致。

## 8. 本地控制计划：两个完整会话与两个单轮失败接缝

以下四个控制属于 `adapter_mock`，不进入正式六会话分母。它们只检查新模型适配接缝，不重新执行旧 D/S 候选族或复制前轮攻击矩阵。

| 控制 | 预登记提交过程 | 预计 callback / Action / Update | 当前执行状态 |
| --- | --- | --- | --- |
| direct | ratio → accept → percent → accept → Final | 5 / 2 / 2 | 待正式准备执行 |
| reject_then_direct | sum → reject → ratio 用披露 T → accept → percent → accept → Final | 7 / 3 / 3 | 待正式准备执行 |
| invalid_json | 单轮非法公开 JSON | 1 / 0 / 0 | 待正式准备执行 |
| transport_failure | 单轮类型化 transport 失败 | 1 / 0 / 0 | 待正式准备执行 |

四个控制合计上限/预期为 14 mock callbacks、5 数值 kernel calls、5 Update（4 accept、1 reject），真实 Provider 调用为 0。这里的总数是注册计划，不是测试通过前可以填写的实际结果。

reject_then_direct 检查的是：实际 reject commit 后 pending 清空、不创建总额 accepted Claim，后续合法消费同一 Evidence universe 中披露的 T。它允许拒绝一个正确工具结果，不是“模型识别了错误工具输出”，也不证明模型会自主重新规划。只有这条完整控制真正执行并通过核验后，才可报告该局部状态转换的运行见证。

两个失败控制分别核对：非法公开文本不被修复且 submission 计数增加；无公开 content 的 transport 失败只有 attempt 与终止，没有伪造 Submission/Receipt。它们不是第三、第四条完整正向会话。

## 9. 六个正式会话与测量约定

六个会话预登记为 M01–M06，采用相同任务、协议和模型配置。每个会话有独立可变状态，不读取其他会话的返回内容。初始公开内容相同可以拥有相同的内容地址 State id；会话身份、请求 parent 和后续工件仍分开。

会话可以六路并行，但同一会话内部严格按 State → 提交 → Receipt → 新 State 的次序串行。模型原始响应中的 operation、inputs、basis、完整 Update 和 Final 引用是它承担公开语义责任的证据，不能把一次返回拆成多次模型回调。

主指标为每会话的 Qualified 条件：存在有效 Final，且 protocol-valid 与 QA-valid 同时成立。只有六会话证据都完整且可判定时，才报告：

```text
observed_public_protocol_success = qualified_model_sessions / 6
```

这是固定单任务、固定模型条件下的小规模工程观察比例，不是旧主链 `q_first`，也不是一般金融 Agent 能力、广泛任务成功率或精确模型概率估计。没有成功但证据完整时，可以得到 0/6 的有界负结果；存在证据缺失时，主比例保持不可判定，而不是把 UNKNOWN 当作失败补零。

次指标按实际到达的阶段给出条件分母，包括公开内容可用率、严格 schema 结果、Action 准入与执行、Update accept/reject 及完整 Claim 核验、Final/QA/协议检查，以及首个可定位失败。没有请求过 Update 阶段时，该阶段保持未评估；分母为 0 的条件比例使用 null。

依据使用方式只在运行后从实际依赖描述，例如 `disclosed_total`、`reconstructed_total_claim`、`other_or_mixed`、`unresolved`。应沿 Final → accepted percent Claim → ratio producer/denominator 的实际依赖追踪，并保留此前被拒绝的操作历史。不能只看到出现过 sum 就把最终支持叫作重建总额，也不能强行把混合轨迹归入旧 D/S 商身份。

本轮不为“两种路线都出现”追加样本、不把六会话预分成三 D 三 S、不在失败后换会话、不对某一路线增加定向提示。后续若研究不同提示条件，需要新的实验身份与授权。

## 10. 冻结、落盘与独立核验计划

实现入口见 [preflight.py](../src/trusted_synthesis/experiments/qa_reasoning_share_model_pilot/preflight.py)，状态推进见 [engine.py](../src/trusted_synthesis/experiments/qa_reasoning_share_model_pilot/engine.py)，独立检查见 [independent.py](../src/trusted_synthesis/experiments/qa_reasoning_share_model_pilot/independent.py)。

准备阶段计划完成前驱 manifest/root 与字节不变性检查、授权记录、source authority、model config、协议身份、六会话注册、确定性初始请求与大小检查，以及第 8 节控制。准备阶段不读取凭证、不进行真实 Provider 调用。公开官方文档的只读核对不属于模型生成尝试。

完成源码 commit/tree 和准备工件 manifest 冻结后，在线阶段复核其身份。凭证只在正式在线入口读取，以参数传给 transport；适配器构造器和零调用准备不能隐式读取 `.env`。首次运行后不得把同一目录当作可重复执行的试验位置，也不得重新跑六会话后覆盖失败记录。

每会话至少保留初始/逐轮 State、Request、调用声明、精确 HTTP request、预留 attempt、受限 provider response、generator turn、存在时的 Submission/Receipt、实际 execution/Observation/Claim/Final、终止及会话 manifest。没有公开 response 的轮次不创建形式上完整的虚假提交链。

独立检查的目标是从现有工件自行复算内容身份、parent、计数、公开语法、引用关系、Observation-to-Claim 边界、数值和支持依赖，而不是调用 Engine、旧提交解析器或正式 kernel 重生成一条“看起来一致”的会话。对未保存原文的失败，它只能核对接收端诊断的记录与闭合关系，应保留该证据等级的限制。

正式报告应包括实际调用/提交/内核/Update 计数、失败与终止、原始目录几何、source/manifest/root 身份以及独立验证结果。计划中的路径/身份必须在实际产生后再填写，不使用占位 hash 冒充实际绑定。

## 11. 已完成的隔离单元验证

首次设计文档写入前，适配器隔离测试实际结果为：`20 passed in 0.71s`。同一适配器文件的 ruff 与 mypy 均通过。测试文件为 [test_qa_reasoning_share_model_pilot_adapter.py](../tests/test_qa_reasoning_share_model_pilot_adapter.py)。

这些用例覆盖确定性 wire body 与原 schema、公开内容/元数据选择、私有推理和 envelope 不落盘/不哈希、非法/空/围栏/缺字段公开内容无修复、实际模型身份、usage 缺失与越界、无公开内容、HTTP 错误、先 reservation 后 timeout、异常文本丢弃、curl 精确 stdin/凭证管道/总超时参数、未登记 send 拒绝以及 envelope 身份边界。

其中深度解析异常用例定点模拟 `RecursionError`，验证它映射成 `schema.public_submission` 且保留公开 hash/bytes；这避免依赖不同 Python 构建下不相同的 JSON 递归阈值，不代表实测模型生成了深嵌套 JSON。

所有 HTTP 进程在单元测试中均被 mock；这些用例没有实际 Provider 调用、凭证访问、完整协议会话或数值内核执行。不能把 20 个单元用例并入六会话分母，也不能称为 20 次模型失败/成功。

可独立复查单元与静态检查，不会调用正式试验入口：

```bash
cd trusted_data_synthesis
.venv/bin/pytest -q tests/test_qa_reasoning_share_model_pilot_adapter.py
.venv/bin/ruff check src/trusted_synthesis/experiments/qa_reasoning_share_model_pilot/adapter.py tests/test_qa_reasoning_share_model_pilot_adapter.py
.venv/bin/mypy src/trusted_synthesis/experiments/qa_reasoning_share_model_pilot/adapter.py
```

完整 `prepare` 与 `online` 命令不属于上述单元检查；前者包含一次正式控制执行，后者会消耗最多六会话的在线预算。正式执行命令和输出目录应在执行记录中报告，不能把一般复查单元测试的命令替代它们。

## 12. 正式执行结果：待填写

本节在设计初稿时尚无正式控制或在线结果。下列项目保持待记录，而不是用“预期通过”或零计数填补尚未运行的试验：

| 项目 | 初稿状态 |
| --- | --- |
| source commit / tree 与 source authority | 待首次正式冻结记录 |
| 准备工件目录、manifest、root、字节数 | 待正式准备执行 |
| direct / reject_then_direct 完整控制 | 未执行 |
| invalid_json / transport_failure 单轮控制 | 未执行 |
| M01–M06 在线会话 | 未执行 |
| 实际 Provider attempts / submissions / kernel calls / Updates | 尚无正式在线结果 |
| 逐会话证据完整性、终止、首个失败 | 待实际工件 |
| Qualified 分子与六会话主比例 | 未评估 |
| 阶段条件指标与实际支持描述 | 未评估 |
| 最终 artifact manifest/root 与独立核验 | 待实际工件 |

正式执行后应替换/补充本节并更新文档开头的状态。若实际失败与计划不同，保留真实失败；若证据不完整，明确 UNKNOWN。若工程检查需要修改源码，记录修改发生在首次在线调用之前还是之后，并且不能把修改后的新条件混入先前冻结条件。

## 13. 可接受结论与停止条件

本轮可以在完整证据下报告：获得至少一个该条件下的公开协议模型可达见证；或没有成功、但固定六会话已完整执行的有界负结果。若所有有效会话都使用披露 T，仅能说本轮没有见证重建方式，不能推出另一方式不可达。

以下均不由本轮自动推出：一般推理修订能力、私有思维真实性、两条路线等概率、语义类概率、VTDO 优化收益、训练有效、更多任务可达或旧主链可恢复。

六个预登记会话达到有效 Final、明确失败或预算终止后停止；0 自动重试、0 会话替换、0 为追求路线覆盖追加调用。后继实验需另行明确范围。本轮之外的旧主链保持暂停。
