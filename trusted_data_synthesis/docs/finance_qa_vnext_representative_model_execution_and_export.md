# 统一 QA vNext：代表任务真实模型执行与原始监督表示实验

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

prepare 和 analyze 不使用 API key。run 只在进程内从项目 .env 读取 DEEPSEEK_API_KEY，
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
