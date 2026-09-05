# Share 公开协议真实模型适配与固定六会话工程试验

当前正式状态：固定六个在线会话已完成，51 次真实 Provider attempts；5/6 Qualified，1 个提交预算耗尽失败完整保留，六会话均 evidence-complete / protocol-valid。四个本地控制和 G0–G3 均按限定范围通过。46 项测试通过；详细实际结果、用量、失败轨迹和只读重放方法见第 12 节。旧主链继续暂停，不授权追加采样。

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

| 控制 | 预登记提交过程 | 预计 callback / Action / Update | 预登记时状态 |
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

## 12. 正式执行结果：准备通过，固定六会话已完成

本节是正式工件落盘后的实际结果，取代前文初稿表格中的“待执行”状态；前文保留执行前设计与预算，不把它们改写成事后选择。正式报告状态为 `workflow_completed_as_scoped`：6/6 会话证据完整且 protocol-valid，5/6 Qualified，M01 是完整记录的预算耗尽失败。

正式工件根目录为 [finance_qa_vnext_share_public_protocol_model_adapter_six_session_pilot_v1_20260905](../artifacts/qa_reasoning_share_model_pilot/finance_qa_vnext_share_public_protocol_model_adapter_six_session_pilot_v1_20260905/)。以下所有会话、控制和用量均直接读取该目录的冻结 JSON；没有为撰写本节重新调用 Provider、回放 kernel 或补跑会话。

### 12.1 冻结与实际工件身份

| 对象 | 实际身份或规模 |
| --- | --- |
| 实现 source commit | `55fb6aab8d7122b4d930d1c31843e7d3653ccd19` |
| 实现 source tree | `dc9c8c59c7e9b96e1cf0033d6aa9563faa06ce44` |
| 声明实现文件 | 7 个，均与上述提交中的字节相等 |
| 声明前驱引用文件 | 12 个，绑定前驱 commit/tree；不声称完整运行环境闭包 |
| source authority | `share_model_pilot_source_authority:b5163f9e6fe37892e7934996cda0166a4bfda6236f8d462b2098c4d79e60fead` |
| model configuration | `share_model_pilot_model_config:47626f1bc6c9586fb44a4b394ba490c7fbf6a9b8841ba6766251323ef5e37e86` |
| 新协议条件 | `public_share_protocol_contract:0e352eb0aa3849d10ed9732f7d7196a553f117f7f1b76261d712c9092d87dd30` |
| pilot registration | `share_model_pilot_pilot_registration:64b318f7fe42e913bebfe60715bd4583df1490dfeb789abcef09c7e999546811` |
| 准备报告 | `share_model_pilot_preparation_report:f5355c171d3313c74e9d9c8aaa13417b447963a6f49feee22cee2eb612dfa65e` |
| 准备 manifest | `share_model_pilot_preparation_manifest:8a37db24437b6aa01dbe5d8e5ed8cc2b1aaeefbbcacd39400990a1f34d983b78` |
| 准备 manifest 自排除成员 | 197 个，1,906,433 bytes；manifest 自身 31,834 bytes |
| 最终 report | `share_model_pilot_report:29457220bfe21f469d893bf9f1115e98b59a5ad0ab17bca8d796f88b3cb5b9b4` |
| 最终 manifest | `share_model_pilot_manifest:73dbba1f2af7cfb26fe1092fe5a6716b3b58df061a965244c10b615c6401af62` |
| 最终 root | `share_model_pilot_root:fcc52ce717a9de0e764a6a4feca1f96f367e3f974595a0678ce609f07c3d5ae6` |
| 最终 manifest 自排除成员 | 784 个，8,191,735 bytes |
| 最终 manifest 自身 | 120,586 bytes |
| 含最终 manifest 的目录几何 | 785 个文件，8,312,321 bytes |

实际初始 HTTP body 为 33,132 UTF-8 bytes，body SHA-256 为 `b334a1c092f8fa7a5c1060bbf95525267391d222702bc5d631d861b5c331a1f4`；输入保守准入数为 34,156，精确离线 token 数保持 null。它通过 65,536-byte 请求上限，不是用 32,768-byte 公开输出上限约束输入。准备记录的 Provider attempts、credential reads、online sessions started 均为 0。

### 12.2 四个本地控制的实际结果

[准备报告](../artifacts/qa_reasoning_share_model_pilot/finance_qa_vnext_share_public_protocol_model_adapter_six_session_pilot_v1_20260905/preparation_report.json) 记录 `all_controls_passed=true`，合计实际 14 mock callbacks、5 kernel calls、0 Provider attempts、0 credential reads。

| 控制 | 实际 callback / Action / Update | 接缝结论 | 完整会话核验 |
| --- | --- | --- | --- |
| direct | 5 / 2 / 2 | 两个独立 accept 后提交有效 Final | evidence complete；protocol/QA/Qualified 均 true |
| reject_then_direct | 7 / 3 / 3 | 实际 commit 1 reject，再以披露 T 完成 ratio/percent | evidence complete；protocol/QA/Qualified 均 true |
| invalid_json | 1 / 0 / 0 | 保留 21-byte 公开内容摘要；schema 拒绝；submission_count=1 | 非 terminal 单轮接缝，完整会话结论保持 UNKNOWN |
| transport_failure | 1 / 0 / 0 | 1 次 mock attempt 后 `transport.timeout`；无 Submission/Receipt | evidence complete；protocol-valid=true；Qualified=false；QA=null |

reject 控制第 2 次回调后，实际 State 为 action 阶段、pending=null、accepted_claims=[]，action_count=1、update_count=1、submission_count=2，反馈 `observation_rejected`。被拒绝的 sum Observation id 为 `public_share_protocol_observation:40ea94694126949347b308967403bd7c7a48dfff646e5431e9212318b430fcde`。后续两个 accept 仅新增 ratio 和 percent Claims，因此最终 accepted Claim 数为 2，而不是自动留下被拒绝的总额 Claim。

invalid_json 的公开摘要为 `70139560a841f0bfa0e9f7b44cce1f8f6ba08d6537d7f514516fb2e30e4028a3`，证据等级为 `receiver_diagnosis_only`；未保存非法公开原文。该控制故意只运行一轮且未达终止，独立完整会话审计返回 `evidence.terminal_stop`，相关 Qualified/protocol/QA 字段为 null。这不是新增“失败模型会话”，也不是丢失了一个被声称完整的在线结果；单轮失败接缝的通过与完整会话 UNKNOWN 必须同时报告。

两个完整 mock 的成功均不进入模型成功分子或六会话分母，控制记录的模型样本指标 Y 也保持 null。真实模型没有提交 reject；本轮实际 reject 见证只有上述一个明确标记的 mock 控制。

### 12.3 固定六会话总览

下表 callback 数与 Provider attempts、公开 Submission 数在本次均相等；Action/Update 指实际准入并 commit 的数量，而非所有曾提交的该类 JSON。所有 6 个会话证据完整、protocol-valid=true、无机制缺陷或 UNKNOWN 在线会话。

| 会话 | Provider attempts / Submissions | Action / Update / accepted Claims | 有效 Final / QA / Y | 真实终止 | Final 实际支持描述 |
| --- | ---: | ---: | --- | --- | --- |
| [M01](../artifacts/qa_reasoning_share_model_pilot/finance_qa_vnext_share_public_protocol_model_adapter_six_session_pilot_v1_20260905/online_reports/M01.json) | 12 / 12 | 3 / 3 / 3 | false / null / 0 | submission_budget_exhausted | unresolved |
| [M02](../artifacts/qa_reasoning_share_model_pilot/finance_qa_vnext_share_public_protocol_model_adapter_six_session_pilot_v1_20260905/online_reports/M02.json) | 7 / 7 | 2 / 2 / 2 | true / true / 1 | final_submitted | disclosed_total |
| [M03](../artifacts/qa_reasoning_share_model_pilot/finance_qa_vnext_share_public_protocol_model_adapter_six_session_pilot_v1_20260905/online_reports/M03.json) | 12 / 12 | 3 / 3 / 3 | true / true / 1 | final_submitted | reconstructed_total_claim |
| [M04](../artifacts/qa_reasoning_share_model_pilot/finance_qa_vnext_share_public_protocol_model_adapter_six_session_pilot_v1_20260905/online_reports/M04.json) | 6 / 6 | 2 / 2 / 2 | true / true / 1 | final_submitted | disclosed_total |
| [M05](../artifacts/qa_reasoning_share_model_pilot/finance_qa_vnext_share_public_protocol_model_adapter_six_session_pilot_v1_20260905/online_reports/M05.json) | 9 / 9 | 2 / 2 / 2 | true / true / 1 | final_submitted | disclosed_total |
| [M06](../artifacts/qa_reasoning_share_model_pilot/finance_qa_vnext_share_public_protocol_model_adapter_six_session_pilot_v1_20260905/online_reports/M06.json) | 5 / 5 | 2 / 2 / 2 | true / true / 1 | final_submitted | disclosed_total |
| 合计 | 51 / 51 | 14 / 14 / 14 | 5 个有效 Final | 5 完成、1 预算失败 | 4 disclosed、1 reconstructed、1 unresolved |

因此主结果是 `5/6 = 0.8333333333333334`，即约 83.33% 的固定六会话工程观察比例；不是 51 个独立样本的成功率。没有替换 M01，没有因尚有 21 次总调用余量而补出第七会话，也没有因 M03 是重建方式而另加定向样本。

protocol-valid=true 表示 Host 正确处理实际提交和拒绝、状态及证据链闭合，不表示模型每条提交都得到准入。M01 没有有效 Final，QA 检查未到达，故 QA=null 而非“QA 错答案”；它的完整预算终止证据仍允许主指标 Y=0。

五个有效 Final 的答案均为 `93.508458 percent`，由已接受 percent Claim 及实际支持引用进入独立离线 QA。该答案没有在请求中作为正确答案实例提前提供。

### 12.4 逐会话实际拒绝与恢复轨迹

本小节的“第 n 次回调”从 1 开始，对应原工件 `turn_index=n-1`。这些是已保存公开 JSON/Receipt 的观察，不推断模型内部思考。

- M01：第 1–2 次 sum/accept 成功；第 3–5 次 ratio 都因 `admission.public_basis` 被拒绝，第 6 次 ratio 才准入，第 7 次 accept 成功。第 8 次 percent 的 basis 再被拒绝；第 9 次 Final 引用 ratio Claim，因 `admission.final_percent_claim` 被拒绝。第 10 次 percent 准入，第 11 次 accept 因 proposed value 不等于完整 Observation 而拒绝；第 12 次 accept 准入，但提交预算随即耗尽，未剩一次合法 Final。最终已有 3 个 accepted Claims 也不能替代缺失的有效 Final。
- M02：第 1–4 次完成直接 ratio/accept/percent/accept；第 5–6 次 Final 因 `admission.final_grounding` 拒绝。两次都在实际 F/T 支持之外额外列入 part-whole 关系。第 7 次模型原始提交改为实际 F/T 引用后通过；Host 没有替它删除多余 citation。
- M03：第 1–5 次依次完成 sum/accept/ratio/accept/percent。第 6–9 次 accept 全因 `admission.observed_claim_content` 拒绝；第 10 次提交完整 Observation 值后 accept 准入。第 11 次 Final 用 F/T/关系引用代替真实 F/O/关系支持，因 `admission.final_grounding` 拒绝；第 12 次改为真实支持后才形成有效 Final。
- M04：第 3 次 percent Action 的 basis 只列了 ratio Claim，漏掉其实际 Evidence lineage，因 `admission.public_basis` 被拒绝；第 4 次新公开提交补足对应 evidence refs，随后 accept 与 Final 通过，共 6 次。
- M05：第 3 次 percent Action 在直接 F/T 支持之外多列 part-whole 关系，basis 被拒绝；第 4 次准入。第 5–7 次 accept 都因提前舍入 proposed value 被拒绝，第 8 次完整提交后准入，第 9 次 Final 通过。
- M06：实际 5 次 callback 顺序为 ratio → accept → percent → accept → Final，没有任何提交拒绝。

M01 第 3 次 ratio 的 basis 多列披露 T，第 4–5 次又只列 F、漏掉总额 Claim 的 O/关系 lineage；第 8 次 percent 则漏列实际消费的 ratio claim_refs。以上六个 basis 拒绝与三次 Final grounding 拒绝，均不是 schema 缺字段，也不是“引用越多越好”：它们要求准确对应实际消费的依据。

8 次 `admission.observed_claim_content` 拒绝都涉及 percent Update 把真实 Observation 的完整值提前舍入成最终六位答案：

| 项目 | 实际公开值 |
| --- | --- |
| 工具 percent Observation / 合法 proposed Claim | `93.508458258836473662494842525099711181405583826159` |
| 8 次被拒绝 Update 的 proposed value | `93.508458` |
| 允许在 Final 使用的答案表示 | `93.508458` |

M03 第 9 次回调还把 definition 从 `freight share in percent` 改为另一种表述；其余 7 次上述 Update 拒绝，在完整字段比较中仅 value 与 Observation 不同。模型后来新的公开提交才给出匹配内容，旧响应及拒绝记录原样保留。这里见证的是公开协议反馈后的后续提交，不是 Host 修复，也不应解释为一般学习或内部信念修订能力已经验证。

### 12.5 阶段分母、错误分布与公开所有权

| 实际测量对象 | 分子 / 条件分母 |
| --- | ---: |
| 收到公开 content / Provider attempts | 51 / 51 |
| 严格 schema 通过 / 收到的公开 content | 51 / 51 |
| action-or-final 请求阶段的 schema 通过 | 29 / 29 |
| update 请求阶段的 schema 通过 | 22 / 22 |
| Action 准入 / Action 提交 | 14 / 20 |
| Update 准入 / Update 提交 | 14 / 22 |
| 完整 proposed Claim 一致 / accept Update 提交 | 14 / 22 |
| Final 准入 / Final 提交 | 5 / 9 |
| QA-valid / 实际到达有效 Final 的会话 | 5 / 5 |
| Qualified / 完整证据的正式会话 | 5 / 6 |

51 条公开提交中，33 条准入（14 Action、14 Update、5 Final），18 条拒绝。拒绝分布为 `admission.public_basis` 6 次、`admission.observed_claim_content` 8 次、`admission.final_grounding` 3 次、`admission.final_percent_claim` 1 次。本次在线没有 transport/envelope 失败、空公开 content 或 schema 拒绝；这不抹去本地失败控制的必要性，也不是声称这些失败不可能发生。

所有 51 条在线公开响应均作为严格 schema 通过的原始公开 JSON 保存，证据等级为 `public_submission_replayable`；其中 18 条仍然未通过语义准入。故本次在线的具体错误可以从原始公开提交复查，不仅依赖 hash。完整 HTTP envelope 和私有 reasoning_content 仍未保存或重放。

14 次在线 accepted Claim 均由新的模型 Update 明确提交完整命题后创建，Action 本身没有自动接受。所有模型 Update 都选择 accept，实际模型 reject 提交数及 commit 数均为 0。五个成功会话中，M02–M05 都经历过至少一次拒绝后的新提交，只有 M06 是无拒绝的最短直接过程。

本次首先观察到的困难落在 public basis 的准确覆盖、完整 Observation 命题与 Final 舍入表示的区别、以及最终实际支持引用，而不是 JSON schema 生成。该判断只描述这六条运行及具体错误，不能外推为一般任务上的错误概率或可靠性排序。

### 12.6 实际支持见证，不新增旧商映射

M02、M04、M05、M06 的有效 Final 最终依赖披露总额 Evidence。M03 的有效 Final 则依赖被显式接受的重建总额 Claim：

```text
accepted total Claim
  = public_share_protocol_claim:927d24ecd31b1c6e280bd9c2be57c52a5ba75862311d3081f86d50802b2f70c7

ratio execution consuming that denominator
  = public_share_protocol_execution:1724bdbdc382fe4a44cb0c130104fb494b590da3e459291d1fec72f102b5884e

accepted percent Claim consumed by the valid Final
  = public_share_protocol_claim:7e614c1c48f4549c08f59a8e6e68e6e2bbd9a30ce09dc41f0a6e55f57a6c6bfa
```

M03 最终引用的真实 lineage 是 F、O 和 part-whole 关系，不是披露 T。该结论来自实际 Final-to-Claim-to-execution 关系，而非因为看到一次 sum 就赋予路线标签。

M01 也确实执行并接受了重建总额，ratio 实际消费了该 Claim；但它没有有效 Final，最终支持描述因此保持 `unresolved`。不能把这条未完成轨迹补计成第二个重建成功，也不能删除它来计算仅成功轨迹的主指标。

本轮因此获得了两种实际支持使用方式的模型运行观察，但 `old_quotient_mapping=false`、`new_W_share=null`、新的语义/商类数为 null。没有把这些描述绑定到旧 D/S 商 ID，没有估计类分布，更没有据此宣称均匀概率或 VTDO 收益。

### 12.7 实际模型元数据、token 用量与预算

51 次实际响应的 model 字符串均为 `deepseek-v4-pro`，可选 fingerprint 均为 `a307abda487cd1b463329ccb945ce396`，finish_reason 均为 `stop`。这些是接收端提取的真实返回元数据，不是把文档版本 `DeepSeek-V4-Pro-0813` 填成实际响应，也不证明远端权重的独立不可变身份。

| 会话 | prompt tokens | completion tokens | actual total tokens | 发送前累计预留 allowance |
| --- | ---: | ---: | ---: | ---: |
| M01 | 134,088 | 6,014 | 140,102 | 897,024 |
| M02 | 76,919 | 3,278 | 80,197 | 523,264 |
| M03 | 137,190 | 6,740 | 143,930 | 897,024 |
| M04 | 64,947 | 2,481 | 67,428 | 448,512 |
| M05 | 97,869 | 4,119 | 101,988 | 672,768 |
| M06 | 54,069 | 2,220 | 56,289 | 373,760 |
| 合计 | 565,082 | 24,852 | 589,934 | 3,812,352 |

所有 51 次响应都有 prompt/completion/total usage，且逐次和汇总满足 prompt + completion = total。本次 cache-hit tokens 合计为 0，cache-miss 为 565,082；reasoning_tokens 在 51 条记录中均缺失并保持 null，不能报告为“实测 reasoning tokens=0”。

实际 HTTP request body 范围为 33,132–36,740 bytes，累计 1,787,607 bytes；最大输入保守准入数为 37,764。公开 response content 范围为 632–1,568 bytes，累计 60,644 bytes。3,812,352 是 51 次发送前固定预留额度之和，不是实际消耗；本次实际 usage 总数为 589,934。均不应混用为费用或模型内部推理长度。

实际在线数值 kernel 调用为 14；与四个本地控制的 5 次分开记账，总共 19 次本轮新接缝/在线数值执行。真实 Provider 尝试合计仍只有 51，mock callbacks 不算 Provider。无 GPU、无旧候选 Runtime 重跑、无 session replacement、无自动网络 retry。

### 12.8 Gate 与限定收口

正式 [Gate 记录](../artifacts/qa_reasoning_share_model_pilot/finance_qa_vnext_share_public_protocol_model_adapter_six_session_pilot_v1_20260905/gate_evaluation.json) 的 G0–G3 均通过：

| Gate | 实际覆盖对象 | 结果 |
| --- | --- | --- |
| G0 | 请求/响应与登记的当前 State 身份关系 | PASS |
| G1 | 两个完整 mock 和两个单轮失败控制 | PASS（保留单轮 UNKNOWN 限定） |
| G2 | 六个固定会话、无替换、实际尝试受界 | PASS |
| G3 | 独立协议核验与有限解释 | PASS |

本轮可以收口为：真实模型的公开返回值已在不被 Host 补写语义内容的条件下进入既有协议；五个会话形成可归属、可公开重放的 Action/Update/Final 完整闭环，一个预算失败会话完整保留。公开模型可达性获得有限见证，同时完整命题与实际支持引用仍存在实测提交失败。

报告不要求所有模型会话成功或两种支持方式都出现。旧主链继续 `remains_paused`，`next_stage_authorized=false`。本节报告的是既定六会话已经完成的结果，不授权追加采样或新任务。

### 12.9 最终验证与安全的无新增调用重放

最终本轮定向测试实际为 `46 passed in 3.44s`，分组如下：

| 测试组 | 实际通过数 | 主要对象 |
| --- | ---: | --- |
| adapter | 20 | 精确呈现、受限响应提取、无修复、私有字段/凭证边界、模拟 HTTP |
| contract | 7 | 冻结模型与协议条件、权限和资源界限 |
| independent | 10 | 固定实际工件的独立结构/语义/证据与分母检查 |
| preflight / replay | 9 | 冻结、51 次账本、禁止在线重启、完整字节重建 |
| 合计 | 46 | 不增加正式科学样本 |

本轮 7 个实现源码与 4 个测试文件，共 11 个文件的 Ruff 检查及 format 检查通过；7 个实现源码文件的 Mypy 通过。全项目范围另存在历史 v26 文件的 Ruff `I001`，本轮未改该历史文件，因而这里不声称整个仓库零静态检查问题。

完整重建测试把模型 adapter、curl transport、mock transport、Scenario handler、Engine 构造、三个数值 kernel 的 execute 以及凭证读取入口全部替换为“被调用即测试失败”的哨兵。随后 `replay_pilot` 只读取既有执行字节、独立重建验证报告/汇总/manifest，并得到与原目录逐文件完全相同的 785 个文件、8,312,321 bytes。原正式目录也保持字节不变。

因此，这次重建的新增 Provider attempts、mock callbacks、kernel calls 和 credential reads 均为 0。它复用的是已经完成的六个模型会话，不是第二批模型会话；同样不重新执行两个完整 mock。另一个测试对已启动过的正式 cohort 调用在线入口时，在读取凭证前拒绝为 `pilot.no_online_restart_or_replacement`，并核对原目录不变。

如只需复查当前正式结果，可从仓库根目录执行下面的 `replay` 命令。该命令不传入凭证参数，replay 分支不读取凭证，也不调用 `prepare` 或 `online`；目标是新临时父目录中的尚不存在的 `rebuilt` 子目录，避免覆盖正式工件：

```bash
cd trusted_data_synthesis
share_pilot_replay_tmp="$(mktemp -d /tmp/share-pilot-replay.XXXXXX)"
PYTHONPATH=src .venv/bin/python -m trusted_synthesis.experiments.qa_reasoning_share_model_pilot.preflight \
  --mode replay \
  --repo-root .. \
  --replay-from artifacts/qa_reasoning_share_model_pilot/finance_qa_vnext_share_public_protocol_model_adapter_six_session_pilot_v1_20260905 \
  --output-directory "$share_pilot_replay_tmp/rebuilt"
```

运行前应保留本轮冻结源码及前驱工件；重放会检查声明的 source commit/tree 和配置身份。上面命令只是已有证据的独立核验/重建，不是重新采样的许可，也不应改成使用正式目录作为输出目标。生成的临时副本可保留供检查，本命令不删除任何文件。

## 13. 可接受结论与停止条件

本轮可以在完整证据下报告：获得至少一个该条件下的公开协议模型可达见证；或没有成功、但固定六会话已完整执行的有界负结果。若所有有效会话都使用披露 T，仅能说本轮没有见证重建方式，不能推出另一方式不可达。

以下均不由本轮自动推出：一般推理修订能力、私有思维真实性、两条路线等概率、语义类概率、VTDO 优化收益、训练有效、更多任务可达或旧主链可恢复。

六个预登记会话达到有效 Final、明确失败或预算终止后停止；0 自动重试、0 会话替换、0 为追求路线覆盖追加调用。后继实验需另行明确范围。本轮之外的旧主链保持暂停。
