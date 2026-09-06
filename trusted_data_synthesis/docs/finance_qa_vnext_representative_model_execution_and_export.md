# 统一 QA vNext：代表任务真实模型执行与原始监督表示实验

本轮已完成：12个真实会话中 C03 成功，其余11个在32次提交上限处终止。
C/B/S 分别为1/4、0/4、0/4；共374个真实请求，没有替换或补采样。
导出C03的3条原始监督候选并全部通过Token表示检查；未进行Student训练。
主要拒绝集中于Update完整命题接受，且发现公开呈现缺口；详见第9–12节的证据与限定。

## 1. 本轮问题和授权范围

用户本轮指令为“参照实验设计方案进行后续实验”。据此执行附件建议的
`finance_qa_vnext_representative_model_execution_and_export_pilot`，不是再次进行设计审计。
附件原始文件为 27,149 bytes，SHA-256：
`b6fdec3498d77da346dd1c4dc4891fee8665ef14ea439cfcecd7ee1800174593`。
准备工件保存附件原始字节，包括原来的 CRLF；不把设计稿中的预期写成实验结果。

主问题：在给定公开计划、合法候选和验证合同的条件下，真实模型能否通过同一个
QA Runtime 完成三个已有来源任务，产生独立可验、可归属、可原样导出的公开轨迹？

这不是自主规划实验，不测量隐藏推理质量，不声称金融任务总体能力、深度因果效应、
Student 收益或 VTDO 有效性。旧主链保持暂停。没有新来源搜索、路线补样、P/Q
权重迁移、Student 参数加载、forward、反向传播、参数更新、GPU 作业或训练 Release。

## 2. 调用前固定的总体

| 组 | 固定任务 | 会话数 | 历史 fixture 提交数（不预测模型调用数） |
| --- | --- | ---: | ---: |
| C | `registered_cross_metric_comparison` 的既有来源实例 | 4 | 3 |
| B | `branch_cdw_fy2015_fy2016 / derived_growth_absolute_spread` | 4 | 17 |
| S | 既有 `source_explicit_part_whole_share` | 4 | 5 或 7 |

先登记全部 12 个会话：C01/B01/S01，C02/B02/S02，C03/B03/S03，C04/B04/S04。
每轮按 C/B/S 的固定启动顺序安排，最多三个线程；完成当前轮才启动下一轮。
每个会话独立初始化，不读其他会话响应，不把先前成功内容注入后续请求。
已启动会话不会替换；实现或证据完整性异常停止后续轮次，已经启动的同轮会话仍受原预算约束。

S 的四个会话使用同一个中性提示，不指定 disclosed 或 reconstructed，不要求两条路径均出现。
最终支持见证从 Final Claim → scale_percent → ratio Claim → denominator 的真实依赖重建。
只有 denominator 实际消费 relation_sum 的 accepted Claim 才记为 reconstructed_total；
曾经调用 relation_sum 本身不构成该见证。

三个当前 Task/context 必须与前一统一入口固定报告中的身份逐项一致。
前驱提交：`fadcf13f91fbbff1ee9ddfcd8784627b3dd11373`。
前驱统一入口报告：
`finance_qa_vnext_entry_report:e0c20b27fbc35fb981f90141c0f0a93e07ec675e9715d13c6a04ad6d805ad7c6`。
前驱报告身份重新计算后再比对，不仅信任文件内的 id 字符串。

完整广度表仍为 11 类：3 类选入本轮、5 类有来源但未测量、3 类没有当前允许范围内的合法来源。
重复四次只增加同一固定任务的会话数，不增加任务或来源数量。

## 3. 冻结配置与预算

| 项 | 冻结值 |
| --- | --- |
| Endpoint / 请求模型 | `https://api.deepseek.com/chat/completions` / `deepseek-v4-pro` |
| 可接受响应模型名称 | `deepseek-v4-pro`、`deepseek-v4-pro-0813` |
| thinking | `disabled`，显式发送 |
| temperature / top_p | 0.7 / 1.0 |
| max_tokens | 8,192 |
| response_format / stream | JSON object / false |
| 原生 tool calls / fallback / 自动重试 / redirect | 均不启用 |
| HTTP 总期限 / connect | 180 秒 / 30 秒 |
| 每会话实际 Action / Submission / Provider attempt | 12 / 32 / 32（Submission 包括 Final） |
| 全部 Provider attempts | 不超过 384 |
| 完整序列化 HTTP 请求字节上限 | 98,304 bytes |
| 输入准入 allowance Imax | 99,328，即请求字节上限加 1,024 allowance |
| 每 attempt 预留 allowance | 107,520 = 99,328 + 8,192 |
| 每会话 / 全试验预留上限 | 3,440,640 / 41,287,680 |
| HTTP 响应接收上限 / 公共 Parser 上限 | 2,097,152 / 1,048,576 bytes |

输入字节加 allowance 是保守的离线准入规则，不是 DeepSeek 精确 Token 化，也不是实际计费量。
实际 usage 从响应逐条保留，缺失时未知，不用 allowance 冒充实际消耗。
离线控制的最长请求只说明所覆盖 State 的长度，不能穷尽未来 State。
每次发送前重新检查完整实际请求，超限则停止；不截断 Evidence、候选、Proposition 或旧反馈。

180 秒使用 asyncio 的总期限，另有 HTTP connect 期限；单独的 read timeout 不充当总期限。
该在线执行环境使用 Python 3.12.13（总期限接口要求至少 3.11），已装 httpx 0.28.1；
项目以 online extra 声明 httpx，未为本轮升级环境。software.json 同时绑定 pydantic 2.13.4、
transformers 5.14.1、tokenizers 0.22.2、jinja2 3.1.6、huggingface-hub 1.25.1。
HTTP 客户端禁用环境代理、redirect 和底层 retries。
本轮不请求私有推理；若响应意外包含 reasoning/native-tool 字段，保留实际 HTTP envelope 并记录条件异常，
不把它视作符合冻结生成条件的成功，也不评价其私有内容质量。

模型名称沿用历史候选条件，并非不可变模型快照证明。当前服务是否接受请求及其实际响应身份，
只由本轮真实响应见证；不单独发可用性探测而产生第 13 个样本。
配置参数参考官方 [Chat Completion API](https://api-docs.deepseek.com/api/create-chat-completion/)
及 [Thinking 模式说明](https://api-docs.deepseek.com/guides/thinking_mode/)。文档不能证明本轮服务内部权重不变。

## 4. 一个 Runtime，增加实际传输与终止证据

继续使用 `domains/finance/qa_vnext/PublicQARuntime`、ProgramTaskAdapter、ShareTaskAdapter、
同一 FinanceQACatalog 和共享 OperationRegistry。公共合同仍为 `finance_qa_public_decision_protocol.v2`。
Program 保留 precision=28；Share 保留 precision=50 和 Final 六位量化，均为 ROUND_HALF_EVEN。

| 内容 | 责任与证据 |
| --- | --- |
| Task、计划骨架、合法候选、允许的 transition | Host 的公开合同 |
| Action 选择、完整 decision 字段、Update disposition、Final | 实际模型公共字符串 |
| 数值执行及 pending Observation | 已准入 Action 对应的 Host Operation |
| accepted Claim | 后续独立模型 Update 被准入且选择 accept 后产生 |
| Final 正确性、事件与来源合法性 | 独立验证器 |

在线 callback 只将完整当前 PublicRequest 渲染为 system+user messages，发送一次 HTTP 请求，
并把非空 `choices[0].message.content` 的原始 UTF-8 字节直接交给现有 Parser。
不补 operation、basis、candidate IDs、expected effect、proposed Claim 或 Final 引用。
没有备用 fixture callback，也不修改原始响应。

实际链路逐项绑定：registration → 当前 Request/State → HTTP request 原始 body →
发送前持久化的 attempt reservation → 实际 HTTP response body → 公共 content →
Runtime Submission → Receipt → 执行／Update／Final。每层有内容身份和完整字节清单。
传输前保存请求及 reservation，执行前保存原始响应和 Receipt，均执行 file/目录 fsync 与读回。

模型归属不是单独检查 `origin=model`：独立 reader 检查实际 sender 类型、实现源码字节、配置、
全部请求／响应／reservation 的父关系、事件顺序、响应模型、content 与 Submission 的字节一致性。
本地 manifest 是可复核的工程来源证据，不是 Provider 数字签名或抵抗宿主伪造的远程证明。
单元测试用替代 I/O 构造的合成 HTTP 数据明确留在测试目录，不进入正式总体。

无公共内容、模型身份不符、超时等情况保存 typed Provider outcome 和 Runtime callback_stop；
不产生虚假的空 Submission 或 Receipt。公共非空字符串即使是错误 JSON 也先原样进入 Parser，
后续纠正是一条新模型提交，仍消耗固定预算，不是网络自动重试。

## 5. 资格、失败与有限测量

每个登记行保留 `success / known_failure / unknown / not_started`。
完整记录的无响应、超时、资源终止或 32 次提交耗尽可以判定端到端失败；无 Final 时 QA=null。
文件缺失、父关系不能确认、执行器内部异常或终止不明保留 unknown，不填成失败。
已登记未启动的行也为 Y=null；已开始但无完整 session 的行保留 execution_started=true、Y=null。

同一任务的四行都可判定时才报告 successes/4；否则比例为 null。
总体等任务权重平均也仅在 12 行均可判定时给出。不会删除未知行重新归一化。
允许 `Qualified=true` 且 `projection_status=undetermined`，包括曾发生未准入纠正的有效会话。

深度由实际事件重建 structural / semantic-operation / observable-choice 三种依赖深度。
完整会话与未完成前缀分列，不从题型预填，不用 callback 次数代替深度。
三个任务同时具有结构、来源、操作和输出要求差异；任何成功率差异不构成深度因果效应。

仅同任务、完整合格模型轨迹进行有限比较，最多 18 对；受支持时给出完整节点 correspondence
或 retained-difference witness，纠正／reject 支持域外保持 undetermined。
本轮所有 quotient_assignment_id 均为 null，不物化新商类概率，不移植旧 State 或 P/Q。

## 6. 原始监督候选与 Token 表示

仅导出模型归属和条件核验通过、所在会话 Qualified、实际 Receipt admitted 的提交。
输入严格取同一真实 HTTP body 的 messages，目标严格取同一原始响应公共字符串。
保留当时 feedback、候选、State、数字格式及独立 Request/Response/Submission/Receipt/Qualification IDs。
失败会话的合法前缀也不进入正向候选；纠正历史仍保留，只有未准入目标被排除。

本层叫“新协议原始监督候选集”，不是已赋类权重的 Mψ。Runtime State 和 quotient assignment
分别命名；后者 null 不阻断原始监督候选。不继承旧 27 行、旧类内核或旧 (4/5,1/5)。

只复用已固定的本地 tokenizer/config 五文件资产和 chat template，重新 Token 化新 messages 与目标。
检查完整 prefix/target/suffix、UTF-8 解码一致性、目标边界不跨 token、target-only label/mask、causal shift=1。
固定最大序列长度 24,576，不加载 Student 权重。不适配时保存完整长度、边界和原始候选引用，
标记 not_fit、不产生可消费 token 数组，不截断，不回写 QA 失败。
零 Qualified 会话时候选为零，不加载正向 Token 对象，不以空集合声称正向表示已验证。

## 7. 冻结、运行及只读再分析

源码提交后，准备程序将全部 Python 源文件逐字节对照 Git archive，保存 source commit/tree 与完整清单。
首次在线调用前保存原始设计、条件、配置、12 注册行、公共协议、Catalog、广度表、tokenizer 资产和零调用控制。
准备清单与工作树源码在正式执行和再分析时重新核对。
`preparation` 对应唯一同级 `execution` 目录，首次启动排他创建；已存在时拒绝重跑，不提供补样／resume 开关。

```bash
cd /data1/zhuxinrui/projects/Data-Synthesis
trusted_data_synthesis/.venv/bin/trusted-synthesis finance-qa-vnext-model prepare \
  --repo-root "$PWD" --output-dir <experiment-root>/preparation \
  --design <original-design-attachment> --run-tag representative_v1_20260906
trusted_data_synthesis/.venv/bin/trusted-synthesis finance-qa-vnext-model run \
  --repo-root "$PWD" --prepared-dir <experiment-root>/preparation
trusted_data_synthesis/.venv/bin/trusted-synthesis finance-qa-vnext-model analyze \
  --repo-root "$PWD" --prepared-dir <experiment-root>/preparation \
  --output-dir <new-readonly-analysis-output>
```

prepare 和 analyze 不使用 API key。run 只在进程内从现有 `trusted_data_synthesis/.env` 读取 DEEPSEEK_API_KEY，
不写入参数、日志、请求证据或 Git。analyze 仅读已有字节，不调用 callback 或 Task executor，
不通过再次运行 12 会话来声称结果可复现。

## 8. 调用前验证和后续结果记录

当前源码准备阶段的零网络控制包括：完整 B（17 提交）、C 错 state 后新提交纠正（4 提交）、
C 空公共内容（1 attempt / 0 Submission）、C 错模型身份（1 / 0）。控制共 23 次 mock attempt，
真实 Provider attempts=0；全部显式 adapter_mock，不进入 12 行总体，不导出模型监督候选。
所覆盖请求最大 HTTP body 68,396 bytes、输入 proxy 69,420，低于冻结准入上限；不是未来状态长度保证。
新旧协议、未来 State、字节篡改、假模型归属、mask 与超长等边界由无网络测试另外覆盖。

冻结前 337 项唯一测试的最终状态通过，按组执行：原统一入口／数值／测量／Registry 回归
170 passed（130.26 秒）；新实验 167 项覆盖传输20、callback终止3、资格19、表示57、
局部控制7、计划38、完整编排及凭据23。
第一次联合新测试为 162 passed / 2 failed（167.62 秒）：两个失败来自测试替身未随新增
Token 统计字段提供 `records`，并非真实 Token 数据缺该字段；补齐测试替身后，两项调度测试
与最终19项资格测试合跑 21 passed（41.90 秒）。新增3项资格测试覆盖“已开始但session缺失”
和错误start身份／父引用。这里按唯一测试最终状态计数，不将重复运行累加为更多独立验证。
全部八个新模块通过 Python3.12/follow-imports=silent 的 mypy；新代码与测试 Ruff/format 通过。
完整无网络编排演练的12条合成会话产生100条真实tokenizer可容纳候选，
所有再分析输出逐字节一致且禁止 Provider/callback/executor；这些仍不是模型样本。

正式结果将在同一文档的后续节附上实际源码冻结身份、执行证据、每任务分子／分母、失败位置、
真实深度、Share 最终支持、usage、比较关系、候选／Token 数量、只读重建和分层 Gate。
本节尚不宣称真实模型成功。历史 V26.113 已确认的旧 scripted-fixture 基线失败与 18 个旧严格类型诊断
不是本轮模型执行前提；本轮不修改它们或将其隐去。

### 8.1 首次发送前的真实入口读回修复

首次源码提交 `e83c7f0abf8cf9c0113b867b7160def223489b56` 的正式零调用 preparation 已成功封存，
但实际 CLI run 在 `_prepared` 的 `run.frozen_population` 检查退出，尚未读取 .env、
创建 execution 目录、启动任何会话或进行 Provider attempt。原 preparation 原样保留，
不删除其初始登记，也不把它当作正式12会话中的模型失败。

具体原因：公开 Registry manifest 中5类 tuple 字段经过 JSON 后成为 list；三个context、
13个Operation共195处表示类型差异。重新计算的 condition.id 和 canonical JSON 字节均完全一致，
只有 Python 内存 `==` 为 false；registrations 和 coverage 没有差异。
修复仅将已序列化总体对象的复核改为 canonical JSON 字节比较，同时避免 bool/int 宽松相等。
不改模型配置、公开 Task/context/protocol、预算或选择规则。

先前完整编排测试为了隔离 scheduler 替代了 `_prepared`，所以没有覆盖这一真实入口读回路径。
新增零网络 prepare→真实 `_prepared` 回归补上该覆盖；首次响应前重新提交源码并使用新的准备目录，
原零调用准备轮标记为 superseded。正式模型总体仅来自修复后首次实际执行的12个会话，
不存在已失败模型会话替换或额外模型采样。
新增真实读回回归通过（1 passed，13.13 秒），包括 tuple/list 正常读回及 false→0 篡改拒绝；
源快照/Git和dummy设计输入仅在测试中隔离，其余 Catalog、四个控制、软件、tokenizer 与 `_prepared`
均实际运行，网络与凭据读取被禁止。相关唯一测试的最终通过数因此增至338。

第二次源码冻结 `45db3b4b0f333e81d2569576e98a9620bf5d47b4` 的真实读回已通过，
但首次密钥读取使用了错误的仓库根 `.env` 路径，因此触发 FileNotFoundError；
现有、已被 `.gitignore` 排除的文件实际为 `trusted_data_synthesis/.env`。
该次仍未创建 execution 目录、启动会话或发送 HTTP。入口随后只修正这一已存在配置文件的路径，
不复制、不打印密钥，不更改生成条件，再于首个实际 Provider attempt 前冻结源码与准备工件。
实际配置位置检查不发送 HTTP，只确认项目现有文件可由同一解析器读取。
增加调用前路径解析测试，并更新隔离 fixture 对配置位置的断言后，完整编排测试
24 passed（132.43 秒），包括100条合成候选的真实分词和只读再分析。
加上真实prepare读回与既有回归，相关唯一测试最终状态为339项通过；
两个准备轮的0-call诊断分别保留，最终只有修复后启动的12会话进入模型总体。

## 9. 正式运行中的公开 Update 呈现定位（不修改冻结条件）

首轮 C01、B01、S01 均真实收到 `deepseek-v4-pro` 响应，并在32次提交后以
`submission_budget_exhausted` 终止。独立核验确认模型归属、生成配置及前缀事件完整，
但无有效 Final，QA=null、Qualified=false。下列定位读取已经保存的实际 HTTP 字节与 Receipt，
没有调用模型、重放执行器或修补响应；后续轮次继续原已登记条件，不将此分析注入模型请求。

| 已保存提交 | 实际 `proposed_claim` | 与 Observation 的关系 | 该提交准入错误 |
| --- | --- | --- | --- |
| C01 / turn001 | null，disposition=accept | 没有提交观察命题 | `admission.exact_observation_acceptance` |
| B01 / turn002 | 自建扁平 Claim | `12988.7` 与 lookup 观察值相同，但缺 outer output、lineage、operation、operation_contract_id | 同上 |
| S01 / turn007 | 自建 ID 与扁平 numeric Claim | `21813` 及三个来源引用与 relation_sum 观察一致，但对象包装不同 | 同上 |

这三份请求均包含完整 `state.pending_observation.proposition`，因此不是未提供数值数据。
但实际公开 Update schema 的 `proposed_claim` 仅为任意 object 或 null，没有 accept/reject
与该字段的条件关系或完整复制说明。transition options 只包含新解锁义务、不确定性和 next_subgoal；
中性系统提示也只泛称遵循协议和 schema。实际 HTTP 请求没有传递 `contract()` 中的
`callback_submits_complete_claim=true`，更没有明确写出整对象 canonical equality 条件。

宿主 `runtime.py` 的真实准入规则则要求：accept 时 `proposed_claim` 与整个
pending Observation 的 proposition 规范化 JSON 字节相等；reject 时为 null。
离线 `PublicFixtureCallback` 在代码里直接 deepcopy 完整 proposition，已经内置这项构造知识。
因此，离线 fixture 成功不是模型侧协议说明充分的证据。

证据位置均在正式根 `execution/sessions/SESSION/`：
`transport/attempts/NNN_http_request.body`、`NNN_http_response.body`、`NNN_public_content.txt`，
以及 `runtime/turns/NNN_receipt.json`。选取的三个 NNN 为001、002、007。
HTTP user JSON 与 Runtime request 的 canonical 字节、HTTP content 与公共原始响应字节均已核对一致。
对应源码为 `protocol.py` 的 Update、`runtime.py` 的 request/_admit、
`transport.py` 的 SYSTEM_PROMPT 和 `callbacks.py` 的 fixture Update。

实测结论是：在当前冻结呈现条件下，这些提交违反了宿主的完整命题接受规则。
“公开呈现不足可能促成失败”是有具体证据支撑的解释，但尚无修订条件对照，不能证明它是唯一原因。
尤其不能由 B01/S01 的这两次数值一致而结构不符的响应，推断模型数学算错或深度导致失败。
这不是工件丢失或执行证据被污染；仍按原预算完成已登记总体，既不改提示、放宽准入，也不补样。
本轮的配置／来源完整性检查通过，不等于“模型获得了无遗漏的全部条件语义”这一更强命题成立。
以上是首轮诊断时保留的运行策略；最终12个会话已按相同冻结条件全部完成，不是三组最终均为零成功。

## 10. 正式12会话结果

唯一正式根：`artifacts/qa_vnext_model_execution/representative_v1_final_20260906/`。
实际执行源码提交 `bbc713c6ee1c6c3ef6c0ce57dd9c67c4bbc13955`，tree
`0863d39c0ba34d8f24c90f50b2ca51e9dacd7fa5`；850个Python源文件在执行后与冻结版本逐字节一致。
首次／末次发送前reservation分别为2026-09-06 05:11:33.454983和05:24:37.185484 UTC，
即北京时间13:11:33–13:24:37；这是预留时间范围，不冒充整个分析流程的wall time。
固定的是每轮C/B/S调度登记及线程提交顺序；并行线程的实际HTTP发送／返回顺序可以交错，
首次reservation实际来自B01，不是根据模型结果动态重排。

### 10.1 分母、状态与实际资源

| 固定任务 | Success / 登记数 | Known failure | Unknown | Not started | 实际attempts |
| --- | ---: | ---: | ---: | ---: | ---: |
| C：注册跨指标比较 | 1/4 = 25% | 3 | 0 | 0 | 118 |
| B：分支合并 | 0/4 = 0% | 4 | 0 | 0 | 128 |
| S：来源明确的部分／整体占比 | 0/4 = 0% | 4 | 0 | 0 | 128 |
| 合计 | 1/12 = 8.33% | 11 | 0 | 0 | 374 |

三个固定任务的等权平均为1/12。每任务只有4个重复会话，这不是稳定能力估计或整个Finance QA覆盖率。
11个失败均为有完整证据的 `submission_budget_exhausted`，不是HTTP错误、超时或缺失证据；
无Final时QA=null，但端到端成功为false。全部12份独立资格检查均确认模型归属、生成配置和轨迹／前缀有效。

374次HTTP均返回200，374个不同Provider response ID；返回模型均为 `deepseek-v4-pro`，
finish_reason均为stop，条件异常flag为0。观察到的system_fingerprint均为
`a307abda487cd1b463329ccb945ce396`；相同opaque fingerprint不是不可变权重证明。
无自动重试、fallback、会话替换、额外可用性探测或路线定向补样。
实际374次预留allowance为40,212,480，低于41,287,680的冻结上限；C03的有效Final节省了10次请求。

| Provider实报usage | 总量 | 缺失情况 |
| --- | ---: | --- |
| prompt_tokens | 6,150,285 | 0次缺失 |
| completion_tokens | 177,057 | 0次缺失 |
| total_tokens | 6,327,342 | 0次缺失 |
| prompt_cache_hit_tokens | 5,173,632 | 0次缺失 |
| prompt_cache_miss_tokens | 976,653 | 0次缺失 |
| reasoning_tokens | null | 374次均未提供，不能填0 |

实际最大HTTP请求body为63,313 bytes，输入准入proxy为64,337；最大HTTP响应body为2,819 bytes，
最大公共content为2,191 bytes。实报usage不是预留额度，也不是价格估算。
当前最大请求小于离线完整branch控制，是因为真实B会话均未越过首个lookup的Update，
不能据此推断真实完整branch请求的长度或Token适配性。

### 10.2 每个会话的完整状态与实际深度

深度列依次为 structural / semantic-operation / observable-choice。
“前缀”不是完整任务深度；只有C03的数值来自完整合格会话。

| 会话 | 状态 | attempts / submissions | 已准入Action/Update/Final | 实际执行Operation | 深度及范围 |
| --- | --- | ---: | --- | --- | --- |
| C01 | known_failure | 32 / 32 | 1 / 0 / 0 | registered_compare | 1 / 1 / 0，前缀 |
| B01 | known_failure | 32 / 32 | 1 / 0 / 0 | lookup | 1 / 0 / 0，前缀 |
| S01 | known_failure | 32 / 32 | 1 / 0 / 0 | relation_sum | 1 / 1 / 1，前缀 |
| C02 | known_failure | 32 / 32 | 1 / 0 / 0 | registered_compare | 1 / 1 / 0，前缀 |
| B02 | known_failure | 32 / 32 | 1 / 0 / 0 | lookup | 1 / 0 / 0，前缀 |
| S02 | known_failure | 32 / 32 | 1 / 0 / 0 | relation_sum | 1 / 1 / 1，前缀 |
| C03 | success | 22 / 22 | 1 / 1 / 1 | registered_compare | 1 / 1 / 0，完整 |
| B03 | known_failure | 32 / 32 | 1 / 0 / 0 | lookup | 1 / 0 / 0，前缀 |
| S03 | known_failure | 32 / 32 | 1 / 0 / 0 | share_ratio | 1 / 1 / 1，前缀 |
| C04 | known_failure | 32 / 32 | 1 / 0 / 0 | registered_compare | 1 / 1 / 0，前缀 |
| B04 | known_failure | 32 / 32 | 1 / 0 / 0 | lookup | 1 / 0 / 0，前缀 |
| S04 | known_failure | 32 / 32 | 1 / 0 / 0 | relation_sum | 1 / 1 / 1，前缀 |

共53份声明为Action的公共提交、320份Update、1份Final；实际准入并执行12个Action，
只有1个Update产生accepted Claim，只有1个有效Final。其余360次未准入。
单会话声明为Action的提交最多11次，实际Operation调用均只有1次，没有越过12的Action上限。

| Receipt中的首个错误代码 | 次数 |
| --- | ---: |
| `admission.exact_observation_acceptance` | 319 |
| `admission.alternative_set` | 18 |
| `admission.public_judgment` | 21 |
| `admission.selected_action_content` | 2 |
| JSON解析／结构Schema错误 | 0 |

这是每份Receipt记录的首个准入错误，不是穷尽同一提交的全部潜在违规。
319/360的未准入事件首先失败于完整命题接受；不能将“接口语义准入失败”统称为JSON生成失败。
四个B会话都停留在第一个lookup的pending Observation，没有见证语义操作深度三的模型完成轨迹。

Share的实际初始执行是3次relation_sum、1次share_ratio；S01/S02/S04调用relation_sum的turn为6/0/10，
S03调用share_ratio的turn为6。四者均没有accepted Claim或Final。
因此仅有两种初始支持选择的前缀观察，完整disclosed/reconstructed支持见证均为0，不能称为两类成功路线。

### 10.3 商状态与广度

仅C03合格，且保留19条未准入历史，故projection_status=undetermined。
没有同任务合格轨迹对，实际有限比较数为0（上限18）；不把所有失败前缀送入比较器制造类数。
所有quotient_assignment_id仍为null，没有新的商类分布、旧State ID继承或P/Q加权。

完整11类表位于 `execution/analysis/measurement.json`：3类本轮执行、5类有来源但未做模型测量、
3类仍无合法当前来源。三个选定任务中只有1个获得完整成功见证；这不是整个Finance QA的1/3覆盖率。

## 11. 三条原始监督候选与可消费Token表示

唯一来源会话C03：
`finance_qa_vnext_session:7b70df0b9e2e2fcb57c710d6e79b5d710ec26daacbb72fb8b9f3d05157e6787e`。
实际准入turn为2（Action）、20（accept Update）、21（Final）。
前两次Action和中间17次Update未准入；没有删除这些历史来换取纯accept投影。
三个真实请求依次保留 `selected_action_content`、`exact_observation_acceptance`、`claim_accepted` 反馈。

| C03 turn | 目标类型 | Prompt tokens | Target tokens | Suffix tokens | 总长度 | 目标UTF-8 bytes | Token适配 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2 | Action | 13,878 | 694 | 2 | 14,574 | 1,532 | fit |
| 20 | Update | 14,526 | 763 | 2 | 15,291 | 1,437 | fit |
| 21 | Final | 13,785 | 407 | 2 | 14,194 | 701 | fit |

目标Token共1,864；三个序列共44,059 Token，均未截断、无padding，低于24,576上限。
目标区间分别为[13878,14572)、[14526,15289)、[13785,14192)；causal shift=1，
logit对应区间两端各减1。Suffix IDs为[151645,198]，与prompt一样不纳入目标label，值为-100。
全部input_ids、attention、target_mask、labels逐位置核验；目标decode后的UTF-8与同次Provider公共content、
transport保存文本、Runtime response和导出target逐字节一致。

374条公共提交中正向保留3条、排除371条：失败11会话整组排除352条（包括11条已准入Action），
成功C03排除19条未准入提交。失败export的excluded_submission_count=0表示整会话先行排除，
不表示失败会话不存在rejection。三个候选均projection=undetermined、Assignment=null、未赋类权重。

这验证了一个真实成功比较会话的“当前请求—原响应—正向候选—Token表示”链路。
不声称B/S已取得正向训练表示、不声称新的Mψ或类概率已闭合；没有Student参数加载、forward、
反向传播、参数更新或GPU作业。依赖导入可能涉及PyTorch，不等于加载受益模型或进行训练。

## 12. 只读复核、工件身份与下一步

正式 `execution/` 为5,128文件、186,480,659 bytes，其中transport子树3,040文件／114,832,209 bytes，
Runtime子树1,980文件／66,142,709 bytes，analysis为43文件／2,601,616 bytes。
独立核对3,632个canonical JSON、38份递归manifest，完整成员集合／字节数／SHA均通过。
374条真实HTTP→reservation→response→公共文本→Submission链逐一成立；没有空内容填补或隐式修复。

同一冻结实现对12份资格记录的只读重验全部逐字节复现；完整再分析也与原analysis全部43个文件同字节。
重验时对网络、Provider、callback及Task executor设置禁止调用保护，计数全部为0。
12个export与完整Token dataset另行独立复算同字节，审计前后360个对应工件hash不变。
`checks/` 为46文件、2,792,271 bytes，保存完整再分析及源快照证明。

三份preparation各405文件，均完整核验；模型配置、software、protocol、catalog、coverage、tokenizer资产、
原始设计和task_contexts三份完全同字节。condition仅id／implementation_id／run_tag变化，registration
仅相应派生ID变化；850个Python源文件中只有runner.py在两个调用前修复中发生变化。
两份superseded准备根均无execution，诊断中的started_sessions、Provider attempts、replacements均为0。

`publication_validation/`另保存8文件／82,889 bytes，包括5份JUnit原文（保留中间失败／错误）
及验证汇总。按测试身份去重并按执行顺序取最终状态，169项新增测试全部通过；
加上调用前170项既有回归，共339项相关测试最终通过，最终collect-only亦为339。
既有170项保存的是执行计数与stdout依据，不伪称另有JUnit；没有宣称整个仓库测试全绿。
架构检查实际以 `--source-root src` 扫描197个共享层源文件、发现0违规，未把空扫描当作验证。
新8模块mypy及相关Ruff再次通过。源码、测试及依赖文件与正式冻结提交完全相同。

整个新工件前缀共6,401文件／227,427,292 bytes，包含两个0-call准备轮和正式结果；
正式根5,587文件／202,045,174 bytes。最大单文件2,026,228 bytes。
封存前检查没有实际API key字节匹配，不包含.env或Student权重；没有清理或改写原始响应。

在与冻结源快照一致的当前工作树中，可只读复核（输出目录必须不存在，不重新运行模型）：

```bash
trusted_data_synthesis/.venv/bin/trusted-synthesis finance-qa-vnext-model analyze \
  --repo-root /data1/zhuxinrui/projects/Data-Synthesis \
  --prepared-dir /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/qa_vnext_model_execution/representative_v1_final_20260906/preparation \
  --output-dir /tmp/qa-vnext-model-readonly-review
```

关键身份：

- 正式condition：`qa_vnext_model_execution_condition:7093a766457da0c4c75aa9ddad2443ba21905c5829f9122c07ce2d62dd9982ea`。
- 正式preparation：`qa_vnext_model_execution_preparation:40bffaabf533831b1312b7b291a8e6a1829e6600c061c9ab6af0c9a0953e80cb`。
- 实验report：`qa_vnext_model_execution_pilot_report:8a113f97cccc14838eae5405c27c2dc31615ddad57b5d1fa5dce48c5671e30fd`。
- Token dataset：`qa_vnext_model_execution_token_representation_dataset:b939dc2dcf4a0fb75045898adfe91e66b73d2aa56b7fab9bf6985352746daac5`。
- 只读checks：`qa_vnext_model_execution_readonly_reanalysis_checks:a0c31b1f6ef05ec1b9e2d5074eb57f319589bf972c2ccde9e98abc0ca98c095f`。
- execution manifest SHA-256：`6697418c533ae7f4d8b08b9889a287932607b1425c318d865ca60da7eec172b6`。
- preparation manifest SHA-256：`a83d706ce7614e3de6b4ff7747a9b930f4cd6893a6d509961f820bb9916e1e9b`。

### 分层结论

| 对象 | 本轮结论 |
| --- | --- |
| G0–G3工作流：冻结、真实归属、证据核验、原样导出与表示检查 | 闭合；不是模型全成功的PASS |
| 三个代表任务均可由模型完整完成 | 未成立，仅C取得1个见证 |
| 完整branch深度三／Share完整支持路线 | 未取得模型见证 |
| 新协议正向候选与Token表示 | 在C03的3条目标上成立 |
| 新商映射／类概率／P/Q干预 | 未建立或执行 |
| Student效果、Contribution、VTDO收益或训练Release | 未测量，不作结论 |

当前唯一优先后续方向是把Update的条件语义和校验反馈明确公开，并在另行登记的新条件下做有界对照：
说明accept必须提交整个观察proposition、reject必须为null；给出模型可读且与真实准入一致的结构要求。
这是建议，不是本轮已实施修复或已经得到的因果效应。C03的一次成功不消除呈现缺口，
其余失败也不能归结为模型普遍不会计算。此时不先扩大来源／题型、不再补样当前冻结总体，
不重做旧Registry／P/Q实验，不开始Student更新。旧主链继续暂停。
