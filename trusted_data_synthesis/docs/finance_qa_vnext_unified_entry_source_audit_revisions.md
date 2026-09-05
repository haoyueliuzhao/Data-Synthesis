# Finance QA vNext：独立源码审计逐项修订与统一入口

## 1. 本次任务与结论边界

本次依据用户指令“此为单独审计，并非对刚才实验的审计，参照审计报告逐项修订问题”，
处理通用 QA 的源码接线、协议迁移和统一验证；不是对上一轮五轨迹训练表示／权重预检的审计，
也没有再增加一次模型采样、Student 训练或权重干预。

外部审计的明确对象是 GitHub `main` 的固定提交
`f964b115ead7354e7982900d87fd64908cca8f1e`，tree
`3a08517462172371a80fbded6ddd091e24d789ba`。
用户提供的报告为 23,620 字节，SHA-256
`bac83c68d9e68ba120420c01e97f10265f2115912c6fd39e3f5d4ffef7f7d25f`。
原报告是静态源码与调用关系审计，未声称运行复现；本文的运行结果来自本次实际回归，二者不混淆。

这次的主要交付是 `domains/finance/qa_vnext/` 与正式 CLI `finance-qa-vnext`。
它不是 `experiments/*preflight*` 中另一份平行执行器：Catalog、共享 Registry、
source-bound Task、公开 callback、Runtime、逐步独立数值验证、终端 QA、轨迹核验与有限比较
已连接成同一条新链。旧 `finance-pilot` 的确定性生成器继续保留，同时修复其真实 Registry 缺陷。

结论限定为：**当前冻结来源域上的统一离线接入已实现；广泛真实模型覆盖及一般知识修订未建立。**
测试通过率不是来源覆盖率，也不是模型成功率；历史 `PASS_AS_SCOPED` 和旧商状态不作追溯重写。

## 2. 对照审计逐项修订

下表的 R 编号是本文为跟踪修订设立的映射，不冒充外部审计原有编号。

| 项目 | 原问题 | 本次实现与证据 | 仍保留的限制 |
| --- | --- | --- | --- |
| R1 | 通用 Pilot 编译／执行／验证使用不同 Registry | `run_finance_pilot()` 创建一次 `finance_vnext_operation_registry()`，向 Task、Reference、Candidate、Quality、Proof、Workflow、manifest、portfolio 和 replay 传同一实例；真实入口回归包含 `registered_compare` | 旧 Pilot 仍是确定性执行后渲染的工作流，不变成模型协议 |
| R2 | 八类基础、两类扩展、Share 互不统一 | `FinanceQACatalog` 同时 resolve/compile 历史八个 Pattern 与两个深度三 Pattern；Share 作为第十一类显式 adapter family 注册，共用已扩展的 Registry | Share 明确是 adapter materialization，不谎称 TaskPattern 编译 |
| R3 | 注册、默认请求、来源、执行等列被横向拼接 | 新入口默认请求全部十一类；每条 coverage row 绑定该次 context/task/session/audit/graph；三类缺少合法来源时保留未实例化行 | 当前固定来源池不是任意金融数据湖的总覆盖 |
| R4 | 通用生成器先执行整个 Program，再补 PLAN 和理由 | 新 Runtime 在执行前保存 callback 原始 JSON、Submission、Receipt 并回读；每次只调用被准入的一个注册 operation | Program skeleton 是公开给定的计划，不据此声称自主发现隐藏计划 |
| R5 | 关键公开判断未进入真实响应语言 | Action 包含 obligation、subgoal、完整候选集、选择、类型化依据、uncertainty refs、expected effect；Update 包含明确 assessment、后续义务和 next subgoal，并实质约束状态转移 | 当前实例的 uncertainty 为真实空集；不编造不确定性或强迫长解释 |
| R6 | 已接受知识修订与 Observation reject 混淆 | 公开合同只支持 pending Observation 的 accept/reject；accepted Claim 仅由独立 Update 产生，明确不支持 retraction/replacement/descendant invalidation | 不宣称一般知识修订；reject／未准入修正账本不强行投影到旧商域 |
| R7 | 深度、关键决策图、有限商测量没有接到同一轨迹 | 只读核验器由真实 Action、Observation、Update、Claim 依赖重建图，给三类深度及同任务精确标签图同构比较 | 不把 callback 数或固定 workflow 阶段数称为模型 reasoning depth；不是通用 Mapper |

## 3. 实际入口与版本合同

从仓库根目录运行（输出目录必须不存在）：

```bash
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.cli finance-qa-vnext \
  --repo-root "$PWD" \
  --output-dir /tmp/finance-qa-vnext-example
```

只运行审计建议的三个代表类型时：

```bash
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.cli finance-qa-vnext \
  --repo-root "$PWD" \
  --task-type registered_cross_metric_comparison \
  --task-type derived_growth_absolute_spread \
  --task-type source_explicit_part_whole_share \
  --output-dir /tmp/finance-qa-vnext-three-representatives
```

两个命令使用完全相同的入口和 Runtime；默认 Share callback 产生 D/S 两条离线 fixture。
显式空集合、重复名称、未知题型会拒绝；Share-only 不隐式运行十个 Pattern。
CLI `--output` 只能指向不可变输出目录外的另一个报告文件，不能覆盖已入 manifest 的成员。
退出码 0 只代表实际实例化案例全部合格，不代表所有注册题型均已有来源。
没有任何可实例化案例时不会以空集上的 `all()` 得出成功。

当前版本：

- 域 Catalog：`finance.qa_vnext.catalog.v1`。
- 执行入口：`finance_qa_vnext_entry.v2`。
- 公开决策协议：`finance_qa_public_decision_protocol.v2`。
- Program adapter：`registered_public_program_obligations.v2`。
- Share adapter：`source_explicit_share_obligations.v2`。

`catalog.py` 复用既有、已注册的 Pattern／operation 定义和纯来源发现函数，
不调用旧 Share Runtime、旧商状态分配或旧 `FinanceNumericCandidateGenerator`。
基础八类和深度扩展共用实际编译 API，不再只把十个名称列在扩展专用 facade 中。
定义来源位于旧实验模块的部分仍被明确导入；本次没有改写这些历史定义或历史实验工件。

## 4. Registry 修复的真实调用范围

`FinanceTaskPlugin`、`FinanceNumericCandidateGenerator` 和
`compile_finance_realization_portfolio` 支持显式 Registry 注入。
`run_finance_pilot()` 的同一实例传播到：

```text
TaskPatternCompiler / realization portfolio
ReferenceWorkflowCompiler / ReferenceWorkflowVerifier
Candidate generator / CandidateWorkflowVerifier
QualityContractCompiler / ProofCarryingSampleCompiler
Finance plugin manifest / Release manifest / reproducibility replay
```

真实入口回归在临时合成的 SEC-shaped archive 上执行 adapter、采样、原始字节 grounding、
任务编译、candidate/reference、proof、portfolio 和 release replay。
这里“真实入口”指真正调用 `run_finance_pilot()`，不表示这些临时公司的数值来自线上 SEC。
另行通过默认四题型各六条的 24-task 配额验证旧默认使用方式。
测试还监视同一 Registry 对象是否抵达全部消费者，并验证八类默认／显式注入得到相同任务与候选身份。

负例将该工厂换回缺少注册扩展的 `default_registry()`，真实入口立即失败；
`registered_compare` 没有被降级成普通 `compare`。

此次真实 Pilot 回归同时暴露既有架构检查中的一个 wire-schema 误判：
`prospective_two_stage_exact_response_grammar` 把已冻结的 protocol 列读取写成 domain-field 形式。
修订为先检查完整 `FIELD_ORDER`，再按对齐列重建常量；未放松架构检查、未新增整文件豁免。
冻结 Grammar ID、1,518-byte wire 表示及 SHA-256 保持不变，损坏 protocol／错位列的负例仍拒绝。
这是一项为真实入口回归清除的独立接线问题，不计入 QA 来源或模型覆盖。

整组历史测试初次执行时，两条 v26.112/.113 exact-source rebuild 测试因当前 Grammar
源码字节变化而失败。这不是允许更换历史报告 ID 的理由：修订后的测试从不可变提交
`5d68a52c6a8b42021cdc8057d23afb475ff752f8` 读取原 24,922-byte Grammar，核验 SHA-256
`305cd3c917afe5008498458b86cbcd758327d6ba0b1beca772dac3828c1f0dd7`，并校验全部
61 个声明的历史 source member，再在独立临时源码视图／子进程重建。
两份原报告 ID 与 builder 的强制 source guards 均保持不变；当前 wire／坏列测试仍针对新源码。

## 5. 来源覆盖：同一条链上的逐类型记录

默认 Pattern 来源仅来自此前冻结的 FinQA table-cell adapter 域：
九个 branch-and-merge binding 去重后为十四个实际单元格。
读取并校验原 source manifest、四个来源成员及 14,395,143-byte 冻结 `test.json`，
后者 SHA-256 为 `831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc`。
不是在全体 FinQA 中重新检索或扩展来源；旧运行是否通过不充当新协议执行证据。

每个 Pattern 默认最多实例化一条；来源不足不拼造跨主体记录或虚构目标值。
来源绑定能重新校验，单纯向 compiler 提供 fixture evidence 只得到
`supplied_evidence_not_source_revalidated`，不能由此获得 QA source-valid。

| 注册题型 | 当前固定来源的默认实例数 | 说明 |
| --- | ---: | --- |
| fact_retrieval | 1 | 真实来源 lookup |
| comparison | 0 | 该十四单元格池没有满足公共语义约束的比较绑定 |
| registered_cross_metric_comparison | 1 | 保持 registered_compare 合同 |
| temporal_growth | 1 | lookup → growth |
| temporal_average | 1 | 多个 lookup → aggregate |
| temporal_absolute_change | 1 | lookup → difference |
| registered_ratio | 1 | 注册分子／分母合同 |
| derived_growth_comparison | 0 | 缺少合法的对齐跨主体增长比较绑定 |
| derived_growth_absolute_spread | 1 | 真实 branch-and-merge 深度三绑定 |
| registered_margin_target_gap | 0 | 权威 gross_margin_target 证据缺失 |
| source_explicit_part_whole_share | 2 个 fixture 会话、1 个任务 | 原 Share source 的直接／重建支持 |

因此这里是十一类注册、八类有实际来源实例（七个 Pattern 类型加 Share）、九个执行会话。
三个未实例化类型不是 trajectory failure，也不进入九条的成功率分母。
对它们同时记录 `registered=true`、`compiled=false`、原因及不可提供的执行／QA 字段，
而不是宣称“十一类全可生成”。

## 6. callback 与 Host 的责任

`PublicFixtureCallback` 和 `ExternalJSONCallback` 接收相同的完整 public request，
输出相同的原始 JSON bytes。后者允许已有调用端接入，但不会将普通 callable
自动认证为模型样本；Provider transport、attempt reservation 和真实模型归属证据不在此泛型适配器中伪造。
这次实际输出的 `origin=fixture`、Provider calls 为零，新的 verified model samples 为零。

Host 公开合法动作的结构与合同，包括 operation/input/parameter、合法依据引用和预期产物；
它也机械列出每种 Update disposition 实际会解锁的后续义务。
callback 必须自己在响应中选择、完整提交并承担这些公开判断。
Host 不补齐缺失字段、不替 callback 自动接受观察、也不从最终答案倒排一段归属于模型的“推理”。
这是一种受约束的公开计划／选择协议，不等同于自由文本解释或不受限规划。

一次合法 Action 的顺序是：

```text
生成并持久化实际 request → callback 的原始 bytes
→ Submission / 准入 Receipt 落盘、fsync、回读
→ 唯一被准入 operation 的实际执行 → 独立 output verifier
→ pending Observation → 新 callback 的 Update
→ accept 才生成 accepted Claim → 后继动作才可消费该 Claim
→ callback Final → 独立终端 QA
```

Action 准入检查当前 State、完整候选集、选择与实际内容一致、类型化 subgoal/basis/effect、
仅引用已接受的 Claim 及 adapter 的注册输入／兼容性合同。
JSON 重复键、非有限数值、未知／多余字段均拒绝；命题比较使用 canonical JSON，
不能利用 Python 中 `0 == False` 的宽松相等绕过完整命题接受。

Update 的 accept 必须提交 pending Observation 的完整命题，并准确声明本次满足的义务、
仍有的不确定性、实际新启用的义务和合法下一子目标。
reject 仅清除 pending，不创建 Claim，不撤销任何先前 accepted Claim。
一般 accepted-knowledge revision 在 schema 与报告中均为不支持，而不是“留空即已实现”。

Program 数值合同固定 precision=28、ROUND_HALF_EVEN；Share 使用独立冻结的
precision=50、ROUND_HALF_EVEN 与六位小数最终量化。
逐步 executor、独立 Oracle、公共答案投影和 Final QA 均隔离外部 Decimal 精度／舍入上下文。
低精度、ROUND_DOWN 和 ROUND_UP 控制验证不再改变结果或 Claim 身份。

## 7. 独立验证、实际图与有限比较

`measurement.audit_session()` 读取原始 request/response、Receipt、执行输入／输出、
Observation、Update、Claim、event 和 session manifest。
它独立解码 raw JSON、重建准入和状态转移、调用纯输入准入与独立 Oracle；
不调用 Runtime、callback、adapter.execute 或旧 quotient。
清单覆盖完整文件集合、每项字节数和 SHA-256，检查记录的 fsync/readback/dispatch 次序。
存储实现还逐级 fsync 新建目录项的父目录，避免仅同步文件与叶目录却漏掉新 `turns/` 的持久化。
这是持久化字节与实际代码路径的证据，不冒称第三方对内核 fsync 的外部远程认证。

实际图包含每个实际 Action 的 operation contract、参数、typed inputs、原 Evidence ID、
accepted Claim 的生产者依赖、basis、subgoal、selection rule、expected effect、观察命题和 disposition。
独立的 event bindings 连接实际 sequence、Submission、Receipt、execution、Observation、Update、Claim；
不由预先列出的 D/S 类别或旧 State IDs 充当图标签。

分开输出以下量：

1. `actual_action_dependency_structural_depth`：沿实际被消费的已接受输入依赖计算，每个 Action 权重一。
2. `actual_action_dependency_semantic_depth`：同一实际依赖图，透明 lookup 权重零、语义 operation 权重一。
3. `observable_choice_dependency_depth`：只在同一 alternative group 有至少两个不同语义选择时计一，沿实际决策依赖累加。

不同并行义务的调度顺序不自动成为语义选择。
默认 branch fixture 的语义操作依赖深度三不意味着“三层自主关键模型推理”；
它的 observable-choice depth 为零。Share D/S 的有限公开依据选择可被观察，
但该计数仍不是隐藏推理质量／难度的测量。原 Program depth 可作为对照单独列出，
其固定 `workflow_interaction_depth` 公式绝不替代实际 callback 或 reasoning depth。

`compare_sessions()` 仅比较 task/context、protocol 和 Registry 均相同且已独立合格的会话。
内容哈希用于工件身份，不决定等价关系；关系由完整保留标签的实际依赖图同构确定，
等价时返回逐节点 correspondence，并检查完整重映射结果。
保留的 typed operand、Evidence 身份和非交换输入不能因答案相同而被抹掉。
独立分支合法交换执行先后可以得到等价，而实际 D/S 支持差异得到不等价。

当前有限投影只接纳完整合格、纯 accept 的事件域。
包含有意义 reject／未准入修正账本、不同上下文、缺少持久化证据或超出同构搜索界限时保持
`undetermined`，不借用旧 Share 两类／经验频率替代解释。
callback 异常和数值 executor 异常会终止并保留失败记录；当前只读证明域不将未闭合会话认证为合格。
这些失败不是被默默替换成成功 fixture。

## 8. 回归、工件与不作出的声明

源码回归分别覆盖真实旧 Pilot 入口、十 Pattern Catalog、七条真实来源 Program、
Share D/S、原始提交负例、明确 Update、独立终端 Oracle、原始工件破坏控制、
有限图同构、CLI 子集与完整 manifest。详细实测结果及冻结源码提交见本文后续“最终验证记录”。

输出目录包含 catalog/protocol/entry/report、各 case 的 validations、完整 sessions 及总 manifest。
每个 session 中留存原始响应，且每个 Action 与对应 Update 为不同 Submission。
这是一份当前域入口的确定性集成回归，不是新模型实验，不用于估计 q、p(z|x)、贡献或训练收益。

以下结论仍不成立：所有金融题型有来源；广泛深度任务已被真实模型执行；
一般不确定性消解或 accepted Claim 修订已实现；任意 QA 的通用 Mapper 已建立；
现有局部通过足以授权整体训练或解除旧训练主线暂停。

旧五条 Qualified 轨迹、原始六会话、两个商状态、五个 Assignment、经验频率及上一轮
27-row 训练表示／权重预检全部保留原有边界；本次没有改写其工件。

## 9. 最终验证记录（2026-09-06）

### 9.1 冻结源码与主入口实测

实际执行使用本地冻结源码提交 `19f2672fb8d848d2cd41ac1c5b857d697685de08`，
tree `325a7fadef514b9cde22df600b19cf1fcf73ddac`。
生成工件前再次核对十五个直接修订的源码文件与该提交逐字一致；本节及工件在后续结果提交中补充，
不改变已用于执行的源码。`checks/source_provenance.json` 保存逐文件身份。

工件根目录：
`artifacts/qa_vnext_integration/finance_qa_vnext_unified_entry_v2_20260906/`。
两套自排除清单共覆盖 **619 个文件、16,346,177 字节**：

- `entry/`：495 个文件、12,701,557 字节，包含九个主入口会话的完整原始提交与验证。
- `checks/`：124 个文件、3,644,620 字节，包含只读复核、完整重建核对、反序 branch 会话及同构证明。

固定身份：

```text
entry report:
finance_qa_vnext_entry_report:e0c20b27fbc35fb981f90141c0f0a93e07ec675e9715d13c6a04ad6d805ad7c6
entry manifest:
finance_qa_vnext_entry_manifest:49eea3c274149d6de8a5bafe4eaac529e87e365170784e6035c4805164af4211
checks manifest:
finance_qa_vnext_checks_manifest:ba389f9e298efefca6364b179b17cd4cf050d50b938c9cd18062a63cbbe56a9b
integration checks:
finance_qa_vnext_integration_checks:40c98b528a7d560ed79a4942acedde76728ca087de989c4c5786a6deae712f21
```

主入口实际 **9/9 qualified**，共 28 Action、28 个独立 Update、9 Final，即 65 个 callback Submission。
这九条均为 fixture；没有把测试回调改名成模型。

| 实际主入口案例 | Action 数 | Submission 数 | 实际结构依赖深度 | 实际语义操作依赖深度 | 可观察选择依赖深度 |
| --- | ---: | ---: | ---: | ---: | ---: |
| branch_cdw_fy2015_fy2016 / derived_growth_absolute_spread | 8 | 17 | 4 | 3 | 0 |
| fact_retrieval | 1 | 3 | 1 | 0 | 0 |
| registered_cross_metric_comparison | 1 | 3 | 1 | 1 | 0 |
| registered_ratio | 3 | 7 | 2 | 1 | 0 |
| temporal_absolute_change | 3 | 7 | 2 | 1 | 0 |
| temporal_average | 4 | 9 | 2 | 1 | 0 |
| temporal_growth | 3 | 7 | 2 | 1 | 0 |
| Share：disclosed_total | 2 | 5 | 2 | 2 | 1 |
| Share：reconstructed_total | 3 | 7 | 3 | 3 | 2 |

每行均来自该案例本轮 session/independent audit，未借用旧 Program 测试或旧模型会话的列。
branch 最终结果为 `2.757665967870018967554982530 percentage_points`；
Share 两条最终结果同为 `93.508458 percent`，但保持不同的实际依据与 Claim 依赖。
这些是当前有限绑定的数值结果，不外推总体模型正确率。

### 9.2 只读复核与完整重建

九个已保存会话分别重新构造其 source-bound adapter，并将其 `execute` 显式替换成会抛错的守卫，
然后调用只读 audit。九份独立报告均与首次报告逐字一致，adapter Action executor 调用为零。
独立核验所需的 Oracle 计算正常保留，不能把“不执行候选 Action”误说成完全不计算。

另在全新临时输出目录再次运行同一公共入口。
完整文件集合及 **495 个文件的每个字节** 与正式 `entry/` 相同，包含全部清单、原始 response、
Receipt、Observation、Update、session、QA 和测量，而不只是最终 report hash 相同。

对同一真实来源 branch Task，额外运行 `reverse_ready_order=True` 的公共 fixture：
它产生不同 session 与实际调度顺序，仍通过独立 QA／trajectory 核验；
同任务比较返回 `equivalent`，并保存完整节点 correspondence。
这条反序会话是单独的等价控制，不混入主入口九条覆盖计数。

Share 同任务直接／重建两条比较为 `not_equivalent`。
差异见证不仅记录 2/3 个实际 Action，还保留左右 operation、真实 Evidence ID、typed inputs、
accepted-input dependencies 与公开判断。未调用旧两类分配器或重估其经验概率。

### 9.3 测试与静态检查：保留失败，不宣称全绿

最终一次合并运行十四个相关测试文件，结果为 **247 passed、1 failed，150.40 秒**。
不是全仓库测试总数；唯一失败与新统一入口的九条合格轨迹属于不同对象。

| 测试组 | 实测结果 |
| --- | --- |
| 新域 Catalog | 33 passed |
| 新通用 Runtime／原始提交／明确 Update／持久化 | 88 passed |
| 新公共 Entry／CLI／完整 manifest | 22 passed |
| 独立实际图／深度／有限比较 | 14 passed |
| Program／Share 数值上下文隔离 | 8 passed |
| 真实旧 Pilot Registry 接线与身份回归 | 5 passed |
| 七份历史相关 Finance／depth-three／Share 协议测试文件 | 67 passed |
| exact-response Grammar 与历史重放 | 10 passed、1 既有失败 |

唯一失败是 `test_v26_113_runner_preflight_rebuilds_byte_identically`。
恢复精确旧源码后，它已越过冻结 source guards，但旧脚本 fixture 的
`cross_check_evidence` 在语义反编译／准入阶段产生
`semantic acquisition selects a non-effective tool`。
随后从不可变 `5d68a52c6a8b42021cdc8057d23afb475ff752f8` 用 Git archive 提取完整
833 个源码文件（不是仅替换一个当前模块），在独立子进程中复现同一失败。
因此这项更深层不一致在本次修订前已存在；本任务未修改旧实验业务逻辑、原报告、哈希或准入规则。
它没有被 skip、xfail 或错误计为通过，也不是新 QA 入口验证失败。

Ruff 覆盖全部变更源码与测试，检查通过；`git diff --check` 通过。
全局 generalization audit 扫描 197 个 core/runtime/architecture 文件，violation 为零，
没有新增 domain-import／domain-field／dispatch 豁免。

类型检查的选项须分别说明：

- 新九个域模块：`mypy --python-version 3.12 --follow-imports=silent` 通过。
- 新九模块加五个旧修订模块：项目现有配置（Python 3.10、`follow_imports=skip`）检查十四文件通过。
- 同十四模块改用 Python 3.12 / silent，会报告旧 realization 的 5 项、旧 Grammar 的 13 项，
  共 18 项既有类型诊断。对修订前源码作 shadow-file 对照，除行号位移外诊断完全一致；
  本次未把这些诊断藏为“严格十四模块全通过”。

复跑最终测试可使用：

```bash
trusted_data_synthesis/.venv/bin/python -m pytest -q \
  trusted_data_synthesis/tests/test_qa_vnext_catalog.py \
  trusted_data_synthesis/tests/test_qa_vnext_runtime.py \
  trusted_data_synthesis/tests/test_qa_vnext_entry.py \
  trusted_data_synthesis/tests/test_finance_qa_vnext_measurement.py \
  trusted_data_synthesis/tests/test_qa_vnext_numeric_context.py \
  trusted_data_synthesis/tests/test_finance_pilot_registry.py \
  trusted_data_synthesis/tests/test_phase1_v26_exact_response_grammar_preflight.py \
  trusted_data_synthesis/tests/test_finance_pilot.py \
  trusted_data_synthesis/tests/test_finance_archive_adapter.py \
  trusted_data_synthesis/tests/test_finance_numeric_generator_totality.py \
  trusted_data_synthesis/tests/test_qa_semantic_depth_three_plus_preflight.py \
  trusted_data_synthesis/tests/test_qa_semantic_depth_three_catalog_integration_preflight.py \
  trusted_data_synthesis/tests/test_qa_reasoning_share_public_protocol_preflight.py \
  trusted_data_synthesis/tests/test_qa_reasoning_share_public_protocol_guards.py
```

本次执行、只读核验、重建及局部控制均没有真实 Provider 消耗、GPU 任务或 Student 参数更新。
本次成果不解除“广泛新模型覆盖未建立、三类来源未实例化、一般 accepted Claim 修订未实现”的边界。
