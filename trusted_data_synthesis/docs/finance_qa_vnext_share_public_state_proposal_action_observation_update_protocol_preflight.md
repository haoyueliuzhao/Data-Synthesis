# Finance QA vNext：模型可见 State 与公开提案—Action—Observation—Update 协议预检

本轮将已经通过有限 D/S 验证的收入占比任务接入公开交互协议。
研究对象是生成器能否通过真实回调提交行动及后续 Update，Host 能否依据当前 State 验证并执行这些提交，
而不是再次证明旧的两条确定性路线有不同支持语义。

本轮正式结果为 `passed_as_scoped`：唯一确定性 fixture 会话实际完成七次回调、三次 Action、
三次显式 accept Update、三个 accepted Claim 和一个 Final，答案为 **93.508458%**。
独立协议验证与 QA 均通过，五项 Gate 全部通过；三个正向 preview 均准入，九个负向 preview 均拒绝。

这是零 Provider 的最小接入预检。不使用模型，不把 fixture 的选择描述为模型行为，
也不测量模型可达性或生成分布。正式执行证据、工件身份及测试记录集中列于第 15 节。

阶段名称：

```text
finance_qa_vnext_share_public_state_proposal_action_observation_update_protocol_preflight_only
```

## 1. 已完成对象与本轮新对象

上一轮的限定结论继续保留：在同一冻结占比任务上，D/S 各实际执行一次，均 own-qualified，
保留了不同的分母支持和推导依赖，因此在两个旧候选的有限集合中 `W_share = 1`、类数为 2。
该结果没有证明该任务全部可能行为恰好只有两类，也没有证明模型采用任意一类的概率大于零。
各构造一条轨迹不意味着模型概率各为二分之一。

本轮接受该对象已经收口，不重新扫描来源，不增加第三条旧式确定性候选，
不重跑旧 D/S、不重做商类证明，也不追加同内容独立审计。
更早的增长率差值任务仍为未实例化，旧 `W = null` 不变；旧主链继续暂停。

本轮要接通的对象是：

> 同一公开 State 可以容许生成器提交不同合法支持选择；行动后的实际 Observation 由另一次生成器提交
> 明确接受或拒绝，Host 验证该提交后才改变可消费的 Claim 集合。

从旧确定性 Runtime 到这个接口，关键变化不在于更换 API 名称，而在于责任分配：
Host 不接收路线标签或下一节点计划，不替生成器选择操作、填写遗漏 Claim 或自动接受 Observation。
操作与 Update 的语义字段必须来自实际 callback 返回的公开 JSON。

## 2. 本轮审查输入及授权边界

外部审查输入身份为：

```text
review bytes   15,329
review SHA256  2e1bef7f9691f56931db9f22a8c0330f8bf557e66daa286e316f6b68b93cfab1
directive      参照审计继续实验
directive SHA256
b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb
```

审查结论为 `PASS_AS_SCOPED`，未发现在已审阅范围内推翻旧限定声明的 Blocking defect，无强制修订。
审查说明其完整阅读了上传报告、对照既有行为与商等价设计，并独立复算数值和数量关系；
没有访问仓库、原始 FinQA 文件、全部正式 JSON 工件，也没有执行 Runtime、验证器或比较器。
本轮不将该报告审查扩写成对新公开协议源码或工件的独立重放。

旧报告中的 `next_stage_authorized = false` 没有被解释为 Provider、训练或旧主链恢复权限。
本轮后继操作依据新的“参照审计继续实验”指令，范围限定为离线公开协议预检。
Provider、凭证读取、GPU、在线模型调用、训练、Release 和 VTDO 生产均不在本轮范围内。

## 3. 精确复用旧 65 个正式工件中的任务与来源

唯一前驱正式目录为：

```text
trusted_data_synthesis/artifacts/qa_reasoning_part_whole_share/
finance_qa_vnext_part_whole_share_dual_support_preflight_v1_20260905
```

该前驱目录包含 65 个文件、254,479 字节，Manifest 身份为：

```text
part_whole_share_manifest:21a2e52198336101d1cf273af76a3bb0d26eb9baefb68dcd946c28261630a251
```

其 artifact root 为：

```text
part_whole_share_root:4a18be9c78b3f7bae7308339de50a0233db81c08484b5fa7fc3791c60fb1b221
```

本轮的来源入口读取旧 `source_binding.json` 与 `contract.json`，复用已经冻结的值、语义和身份。
不调用旧来源 `load_source`、`scan_archive` 或旧候选构建器；没有根据这轮交互结果重新选择来源。
对旧目录的字节检查是前驱不变性验证，不是新增来源搜索或新增旧候选执行。

复用身份为：

```text
source binding
part_whole_share_source_binding:c1936c263ade54d4391eef11d3c1c93932e3bd959dd4e18b6c1c5a412612a254

task
part_whole_share_task:0616bef8f302347723ff0ab8c84a570a9b76bb6cb09681e9a7dafec555a13a3f

legacy operation/numeric contract
part_whole_share_contract:5266609cc280585c8ef3a28583968069c09d2e2b9642595f44a3c57752a9a028
```

本轮新建的是协议、公开上下文和交互会话身份，不重新创建一个财务 Task。
公开任务原样复制旧 Task 的完整内容，因此旧 Task ID 仍然是该完整对象的内容身份，
没有把它贴在删改字段后的不同对象上。

四个 Evidence 也完整复制，继续保留原内容 ID：

| 证据 | 指标或关系 | 值或成员 | 原内容 ID 的 SHA-256 部分 |
| --- | --- | --- | --- |
| F | `total_freight_revenues` | `20397` | `f8ad13511fa22b6d64183fb4b5f5cd114faaf185520d57b0d1f4c7571573ad7a` |
| O | `other_revenues` | `1416` | `b06f192aa1fe09cd004309de456a2ed1a9e37cbf74cf91c2496d618c528e4f67` |
| T | `total_operating_revenues` | `21813` | `033a430a60a5d3243f701d231a10b71564b48b2abeae58d635c42a2811e7638f` |
| 关系 | `part_whole` | F/O 完整、不重叠地组成 T | `44ffd67e2791d65c99ccb101ebc29d15e37fce35939fd0ab9bcbbaf9ff218386` |

三个数值证据的 ID 前缀为 `part_whole_share_numeric_evidence:`，关系证据前缀为
`part_whole_share_relation_evidence:`。关系没有数值 `value` 字段，原始分项指标与定义没有被改写。

共同上下文继续为 Union Pacific Corporation 及其子公司、`consolidated_issuer`、2015、
`millions`、`dollar_as_disclosed`。期间仍来自旧绑定中的实际年度表头，不从目录名重新推断；
不会把原始 `$` 符号额外改写为未经明确来源证明的 ISO 币种代码。
SourceAuthority 继续是 `curated_database / FinQA`，不是本轮新取得发行人完整申报文件的 authority。

## 4. 三个操作与数值合同不变

公开协议复用三个已冻结操作合同：

| 操作 | 关键输入和参数 | 输出 | 原操作合同 SHA-256 部分 |
| --- | --- | --- | --- |
| `relation_sum` | 两个真实成员和关系，精确 `method=sum` | 推导总经营收入 | `7d1f4e6625470c79e209268bc719fce1b315a44fce6dfa310a613c9ab9775e3b` |
| `share_ratio` | 有序 numerator/denominator | 货运收入占比 ratio | `75a8bccdb2fe2141928e52182b2dfad811a479ae666c31c5c0f1301b3e53a54a` |
| `scale_percent` | 已接受 ratio Claim | percent | `bc2d6626b7d1653f7f71a48acaad0f2a71629fffde60d4ae619fecf4cbf1dda2` |

以上 ID 前缀均为 `part_whole_share_operation_contract:`。
操作的语义字段、输入角色、顺序规则、输出指标、单位及参数原样进入公开上下文。
旧异质成员准入与数值内核可以作为新 Host 的工具实现复用；这不等于再次调用旧的 D/S Runtime。

数值合同同样保持：

```text
precision                       50
rounding                        ROUND_HALF_EVEN
final_quantum                   0.000001
source_reconciliation_tolerance 0
answer_tolerance                0
```

共同任务义务仍为期间与范围、分子分母角色、百分比单位、Final grounding，分母为四项。
本轮不更改旧答案目标，不调整精度或容差，也不重新比较旧任务深度和商类。

## 5. PublicContext 与模型可见 State

`public_context` 对外层旧合同采用字段白名单，只包含：

```text
task
evidence
operations
numeric
shared_obligations
answer_schema
actual_support_citations_required
all_visible_evidence_citations_required
```

旧合同的 `measurement`、`route_specific_preconditions`、D/S 标签、预制 `nodes`、
候选家族、Oracle、expected answer、旧 Final、验证结果及类数都不会作为公开上下文传入。
公开目标公式与答案格式是任务的一部分，允许保留；已知正确答案实例不是初始 State 的输入。

PublicState 复制任务、四项 Evidence、三个工具、数值合同、共同义务和答案 Schema，
并只允许以下八个动态字段：

```text
phase
accepted_claims
pending_observation
action_count
update_count
submission_count
last_feedback
terminal
```

另保存 `context_id`、`protocol_id` 和由冻结预算减去当前计数得到的 `remaining_bounds`。
完整 State 有自己的新内容 ID。初始 State 不包含已接受 Claim 或 pending Observation。

State、Request、冻结上下文及动态记录之间使用深拷贝。
生成器修改收到的嵌套字典，不会改写 Host 的原始 Evidence、工具参数、此前 State 或已接受 Claim。
字段边界之外还有补充性私有字段检查；无泄漏结论主要依靠白名单及完整投影核对，
不依靠搜索某个正确答案字符串。

T 仍在共同 Evidence universe 中，关系 Evidence 仍包含完整来源表格和总额行。
本轮不屏蔽 T，不声称生成器看不到总额，也不检验信息隔离后的独立求解能力。
真实 Action 之后的 Observation 可以公开其计算结果；该值碰巧等于正确答案，不构成 Oracle 注入。

## 6. 阶段、预算与单次 Request

协议冻结预算为：

```text
actions     3
updates     3
submissions 12
```

前三者分别计数实际获准 Action、获准 Update、以及所有提交尝试，不可相互混同。
额外提交预算容纳不合法请求的反馈，但不增加 Action 或 Update 上限。

| State 阶段 | pending Observation | 允许下一次生成器提交 |
| --- | --- | --- |
| `action` 且仍有 Action 预算 | null | 一个 Action 或 Final |
| `action` 且 Action 预算耗尽 | null | 一个 Final |
| `update` | 当前实际 Observation | 一个 Update |
| `terminal` | null | 不再生成 Request 或调用生成器 |

`request_for` 返回当前 State 的完整独立副本、允许的提交 kind、对应 Pydantic JSON Schema，
以及要求只返回一个公开 JSON 对象的简短指令。它不选择下一个 operation 或填入 operand 引用。
Request 不含 `generator_kind` 或自称来源字段；实际生成器来源由 Host 登记和 transport 记录负责绑定。

当 `submission_count` 达到 12 且尚未以 Final 终止，Host 将会话标记为
`submission_budget_exhausted`，不再调用生成器。若当时仍有未接受 Observation，
它保留在实际事件中，但不会因此自动创建 Claim；terminal State 清除 pending 引用。

## 7. 公开提交语言与决策责任

三类提交都必须绑定当前 `state_id`，使用严格 JSON 对象，不允许额外字段、重复 JSON key 或非法 kind。
公开响应字节上限为 32,768。非法响应不会被 Host 补齐或改写成合法提案。

| 提交 | 生成器必须提交的内容 | Host 的责任 |
| --- | --- | --- |
| Action | operation、实际 operands、parameters、`public_basis` | 当前状态和预算、可见输入、工具语义及依据准入 |
| Update | 当前 Observation、accept/reject、完整 proposed Claim 或 null、`public_basis` | 核对 Observation 父对象和完整 Claim 内容，决定是否可接受 |
| Final | 已接受百分比 Claim、量化后的 answer、实际 citations、`public_basis` | 核对 Claim 存在、百分比类型、答案与 grounding 一致 |

Action 的 `public_basis` 为 `relation=requires`、真实 Evidence 引用、所用 Claim 引用和目标指标。
引用必须对应实际 operands 及其 lineage，不能用一句解释替换输入边。

接受 Update 的 `public_basis` 为 `relation=supports`，指向当前 Observation 及其来源链。
拒绝 Update 则为 `relation=declines`，并明确 `proposed_claim=null`。
这些是可验证的公开依据声明，不是私有 chain-of-thought；协议不要求或存储私有推理过程。

对于直接选择披露 T 的合法 Action，Host 不施加“S 路线必须使用 Claim”的全局规则。
Host 按该次真实提交的操作、引用和公开依据验证，而不按隐藏路线标签给出预设下一步。

## 8. 从 Request 到 Action Observation：尚不产生 Claim

每次交互的实际实现顺序是：

```text
当前 PublicState
  → 持久化 generator_request
  → 独立调用 generator.generate(该 Request 的深拷贝)
  → 绑定返回原始字节的 generator_turn
  → 保存 parsed submission 及原始公开 JSON
  → 对原提交进行准入
  → 持久化 receipt 并回读提交／receipt 字节
  → 仅获准 Action 派发指定数值内核
  → 保存 execution 和实际 Observation
  → State 进入 update；accepted_claims 不增加
```

这里“独立调用”指单独发生的生成器回调与提交边界，不意味着独立抽样、不同模型实例或统计独立决策。
`generator_turn` 绑定 Request、State、生成器 binding，以及返回响应的 SHA-256、字节数和回调错误状态。
Host 没有把预先写好的 Action 当作 callback 已经返回的结果。

只有通过严格公开 Schema 的 JSON 才按原始公开文本保存；不合法响应绑定哈希和字节数，
不将任意未解析文本扩展为公开提案或私有推理记录。
提交对象记录 `host_repairs=[]`，Receipt 明确不填遗漏字段、不改写响应。

Action 的执行输出与 Observation 属于 `host_derived`。
输出中的数值、指标、单位、定义和 lineage 来自实际工具执行及合法输入；
这个输出还不是生成器已经接受的 Claim，不能在下一次 Action 中直接冒充可消费 Claim。

## 9. 独立 Update 才能使 Observation 成为可消费 Claim

Host 发出新的 update Request，其中包含刚产生的 pending Observation。
生成器必须通过另一次 callback 提交 Update，不能把 Action 返回后的自动回填视为生成器更新。

完整 `proposed_claim` 必须包含：

```text
value, metric, definition, subject, scope, period, unit, currency, lineage
```

在 `disposition=accept` 时，Host 检查：

1. `state_id` 指向当前 State。
2. `observation_id` 与 `public_basis.observation_refs` 指向同一个当前 pending Observation。
3. `public_basis.evidence_refs` 与该 Observation 的真实 lineage 一致。
4. `proposed_claim` 完整存在，且规范 JSON 内容与实际 Observation output 精确一致。

缺失 Claim 不能由 Host 从 Observation 自动补入；数值、指标或 lineage 不一致时也不能自动纠正。
检查通过后，Host 才将生成器实际提交的 proposition 物化为内容寻址的 accepted Claim，
同时绑定该 Update submission、generator turn、Observation 和实际生产 operation。
后续 Action 引用这个已接受 Claim ID 才能消费它。

在 `disposition=reject` 时，合法提交必须明确拒绝关系且 `proposed_claim=null`。
实现语义是清除 pending Observation、增加 Update 计数并返回 action 阶段，不创建 accepted Claim。
这一合法分支在本轮只做准入 preview；不因接口支持 reject 就宣称实际完成了拒绝与重新规划。

## 10. 回调身份与真实字段来源

生成器提交 Schema 没有 `origin` 字段。提交中添加 `origin=model` 会被当作额外字段拒绝，
不能靠调用者自己写一个标签取得模型来源身份。

Schema 拒绝自报标签与真实 callback 实现身份绑定是两个不同检查。
本轮采用的 callback 来源合同要求以下链条，而不是仅比较任意对象提供的 binding 字典：

1. fixture binding 记录固定 module、class、method、source path 及该源码的 SHA-256。
2. GeneratorRegistration 将 binding ID 与 source authority ID、声明源码成员哈希关联。
3. 每次 callback 前检查实际 bound method 的实例、类型、模块和方法身份。
4. 对精确哈希源码只执行 compile，不执行模块，从编译结果定位目标 class.generate 的 CodeType，
   并与实际 `__func__.__code__` 比较，拒绝实例级或类级方法替换。
5. 实际函数的 globals 必须来自已加载的同一模块 globals，不能拿另一个 namespace 中的函数替代。

generator turn 再绑定通过这些检查的登记对象，因此来源不是公开提交者自行填写的标签。
这项合同只声明实际 callback 的源码 authority；不把模块 globals 身份相同扩写为
全部传递依赖、运行时全局绑定或完整执行环境已经闭合。对应实际源码及登记工件已核对，身份与检查范围见第 15 节。

唯一正向生成器是 `PublicRequestFixture.generate`。
其策略已明确写在 fixture 代码中：优先重建总额，再根据公开 State 中已经接受的指标继续比例和百分比，
每次 pending Observation 都提交显式 accept Update，最后从已接受百分比 Claim 生成 Final。

这些选择属于确定性 fixture，不属于模型。Host 没有 route 或 node-plan 参数，
但 fixture 自身依然是一套已知、有限的策略；不能据此宣称生成器算法已经开放探索或有多样模型分布。
`generator_turn`、submission、accepted Claim 和 Final 的来源应准确记录为 `deterministic_fixture`；
工具 execution / Observation 则为 `host_derived`。

## 11. 唯一正向交互与三个正向 preview

冻结的唯一正向交互是：

```text
callback 1  Action: relation_sum(method=sum)
callback 2  Update: accept，显式提交重建总额 Claim
callback 3  Action: share_ratio，分母引用已接受总额 Claim
callback 4  Update: accept，显式提交 ratio Claim
callback 5  Action: scale_percent，输入引用已接受 ratio Claim
callback 6  Update: accept，显式提交 percent Claim
callback 7  Final: 引用已接受 percent Claim、答案及实际支持
```

预算因此是一个完整协议会话、三个实际 Action、三个显式 accept Update 和一个 Final，
合计七次回调。正式会话实际完成了这七轮，逐轮 State 与 Claim 形成记录见第 15 节。
操作形状与旧 S 相似，但本轮验证的是独立提交和 Update 的接口责任，不重复测量旧 S 的语义类别。

此外只安排三个不执行内核、不提交状态更新的正向 preview：

| Preview | 使用状态 | 能支持的结论 | 不能支持的结论 |
| --- | --- | --- | --- |
| 直接总额作为第一个 Action | 同一个初始 PublicState | 接口准入允许 F/T 的合法比例操作 | 没有实际执行第二条完整交互 |
| 分项重建作为第一个 Action | 同一个初始 PublicState | 接口准入允许 F/O/关系的求和操作 | 不构成又一次重建执行或新类别 |
| 显式 reject Update | 唯一会话实际产生的 pending State | reject 提交可以准入且不应创建 Claim | 未实际提交 reject，未观察拒绝后重新规划 |

初始两个合法 Action 的 preview 共享同一 State、同一 Evidence universe 和工具。
它们支持环境没有把第一步锁成唯一旧路线，但不支持完整多样行为的实际可达性。
所有 preview 都保存 `kernel_calls=0`、`committed_updates=0`，不计为 callback 或完整会话。

## 12. 九个负向 preview 控制

九个负向控制针对公开协议当前直接相关的边界：

| 控制 | 被破坏的条件 |
| --- | --- |
| `incorrect_parameters_not_repaired` | 将 sum 改成 mean，Host 不应自动修复参数 |
| `action_blocked_until_generator_update` | pending Observation 尚未经 Update 就提交新 Action |
| `observation_is_not_an_accepted_claim` | 把 Observation ID 冒充可消费的 Claim ID |
| `stale_state_update` | Update 使用旧 State ID |
| `cross_observation_update` | Update 指向其他或伪造的 Observation |
| `missing_proposed_claim_not_host_filled` | accept Update 不提交完整 proposed Claim |
| `proposed_claim_disagrees_with_observation` | 提交 Claim 的数值与实际 Observation 不同 |
| `caller_cannot_claim_model_origin` | 调用者在公开 JSON 中自报 `origin=model` |
| `final_requires_accepted_percentage_claim` | 直接用 Observation 或未接受对象作为 Final 答案 Claim |

这些控制调用纯准入 `preview`，不调用生成器、不执行数值内核、不提交 Update，
也不修改唯一真实会话的初始 State 或实际 event 记录。
它们是固定状态上的接口反例，不是额外实际失败轨迹或额外模型样本。实际准入结果见第 15 节。

控制中可以出现故意错误的数值或先验正确答案，但它们属于 Host 的离线验证输入，
不会被放入初始生成器 Request，也不作为选择真实正向 Action 的依据。

## 13. 独立验证与公开视图测试的责任

独立检查应核对每个实际 Request、generator turn、原始公开提交、Receipt、execution、Observation、
Update、Claim、State 和 Final 的身份、内容、顺序及依赖；不能用调用 Engine 再生成结果替代独立验证。
对实际算术的验证可以独立复算，但不能把验证器的计算记录为 callback 提交或 Action 执行。

公开投影测试主要检查：完整旧 Task/Evidence/operation 身份保留、外层私有合同字段排除、
动态字段白名单、仅代码反馈、深拷贝隔离、pending 阶段、剩余预算和终止后的请求禁止。
这些测试只构造或核对公开对象，不派发模型或金融 Action。

因此，公开视图测试通过不能单独证明七次真实回调已经发生；接口 preview 通过也不能单独证明
State 已经经过对应更新。正式结论需要把协议级测试与实际会话证据分开列示。

## 14. 本轮解释与停止边界

唯一交互和协议验证已经通过，本轮的限定结论是：固定任务可以经当前公开 JSON 协议完成一次
由已登记确定性 fixture 提交、Host 验证执行、生成器显式接受更新的有限交互。
这使未来模型接入的责任边界具体化，但不等于模型接入或模型能力测试已经完成。

本轮不赋予新的 `W_share`，不新增旧任务语义类数，不依据七次 fixture 回调估计模型概率，
不声称完整规划多样性、reject 后重新规划、模型依据选择能力、Contribution、Novelty 或训练收益。
旧 `W_share = 1` 和更早 `W = null` 作为不同历史对象分别保留。

完成唯一预注册交互和固定控制后即停止，不替换 fixture 或扩展来源直到出现更好的结果。
如果 callback 失败，保留有类型的错误，不由 Host 换入备用提案；协议预算耗尽时按冻结规则结束。
Provider 适配器、模型可达性、在线调用、训练、Release、VTDO 及旧主链恢复都需要另外明确的后继范围。

## 15. 正式结果与工件身份

### 15.1 唯一实际会话与独立验证

正式会话实际计数为：

| 项目 | 实际数量或结果 |
| --- | --- |
| 完整正向协议会话 | 1 |
| 生成器 callback／原始公开响应 | 7／7 |
| 获准 Action／数值内核调用 | 3／3 |
| 显式 accept Update | 3 |
| accepted Claim | 3 |
| Final | 1 |
| 实际拒绝提交／callback 失败 | 0／0 |
| Final 答案 | 93.508458 percent |
| `protocol_valid` | true |
| `qa_valid` | true |
| `qualified` | true |
| 终止原因 | `final_submitted` |

独立报告保存 `raw_public_responses_replayed=7`，实际重放七个原始公开响应与后续事件。
它没有导入 Engine、提交解析器、准入函数或 Runtime 来替代自身检查，
也没有重新计算旧商关系。离线 QA Oracle 得到 `93.508458`；
该 Oracle 值没有放入生成器 Request，不计为生成器或 Action 执行。

`candidate_runtime_executions=0` 是独立验证步骤没有新增候选执行的计数，
不能用它抹去本轮已发生的三个 Action／数值内核调用。
本轮也没有调用旧的 D/S 候选 Runtime。

### 15.2 实际 State、Action 与显式接受阶段

下表的 `A/U/S` 分别表示 Action、Update、submission 的累计数量。
`Q0` 至 `Q7` 是便于阅读的文档标签，不是协议输入，也不用于驱动生成器。

| 轮次／State | 该轮真实提交 | 轮后 phase | A/U/S | 已接受 Claim 数 | 轮后 pending／新增对象 |
| --- | --- | --- | --- | ---: | --- |
| 初始 Q0 | 无 | action | 0/0/0 | 0 | 无 |
| 1 → Q1 | `relation_sum(method=sum)` | update | 1/0/1 | 0 | 总额 Observation=`21813`；没有 Claim |
| 2 → Q2 | accept Update，完整提交总额 proposition | action | 1/1/2 | 1 | 总额 Claim 被接受；pending 清空 |
| 3 → Q3 | `share_ratio`，分母为上一轮 accepted Claim | update | 2/1/3 | 1 | ratio Observation；没有新增 Claim |
| 4 → Q4 | accept Update，完整提交 ratio proposition | action | 2/2/4 | 2 | ratio Claim 被接受；pending 清空 |
| 5 → Q5 | `scale_percent`，输入为 accepted ratio Claim | update | 3/2/5 | 2 | percent Observation；没有新增 Claim |
| 6 → Q6 | accept Update，完整提交 percent proposition | action | 3/3/6 | 3 | percent Claim 被接受；pending 清空 |
| 7 → Q7 | Final，消费 accepted percent Claim | terminal | 3/3/7 | 3 | `final_submitted` |

三次 Action 后没有当轮 Claim；三个 Claim 分别由第 2、4、6 轮的另一条生成器 Update 提交产生。
这些 Update 的完整 `proposed_claim` 与对应实际 Observation output 相等，Host 未填补缺失 Claim。
七次 callback 都有各自 Request、generator turn、原始公开 JSON、Submission、Receipt 和轮后 State，
不是将单个回调的返回值拆成七个阶段标签。

实际 ratio 与 percent Observation 分别为：

```text
ratio
0.93508458258836473662494842525099711181405583826159

percent
93.508458258836473662494842525099711181405583826159
```

第 7 轮依据已接受 percent Claim 和冻结量化规则提交 `93.508458`。
这些值来自已有会话工件，本节没有另外调用数值内核计算它们。

初始与最终 State 身份为：

```text
Q0
public_share_protocol_public_state:50d045a62af58d6f319f68e92564749eb97e9a2fec0439a37711fbb881430439

Q7
public_share_protocol_public_state:b94c3cd0c556252ced5920ae3f02df7b63224be390ae2c1cb2c4fa5ef86fbf89
```

终止时剩余 Action/Update/submission 预算为 `0/0/5`。
会话因有效 Final 停止，没有为了耗尽 submission 预算追加请求。

### 15.3 实际分母消费与公开总额边界

第 1 轮 Action 的三个实际支持输入为原 F、O 和非数值关系 Evidence，
输出的总额 Observation 身份为：

```text
public_share_protocol_observation:c15f1d4203de8fb185d55e395a0e2009c1b7b87ba8f9ae2ba5c07484cd6c4aab
```

第 2 轮的显式 accept Update 才产生总额 Claim：

```text
public_share_protocol_claim:72cf9b163c5b0169bc08d754ae93d11fd7ad2417b8be318f689ade45d268970e
```

第 3 轮提交和实际 execution 的 denominator 均为：

```json
{
  "role": "denominator",
  "kind": "claim",
  "ref_id": "public_share_protocol_claim:72cf9b163c5b0169bc08d754ae93d11fd7ad2417b8be318f689ade45d268970e"
}
```

后续 ratio 和 percent 的已接受 Claim 分别为：

```text
ratio Claim
public_share_protocol_claim:1c1d891bd89c960e20310cac48b6e518ff0063827715a02410a7ca26e936e709

percent Claim
public_share_protocol_claim:df3e4fde2a669660ec881c8cebce469ab0dc8362b25889ad4a630a75875500f3
```

第 5 轮消费上述 ratio Claim，第 7 轮 Final 消费上述 percent Claim。
Final citations 是 F、O、关系三个旧 Evidence ID。
本轮由这些真实提交和消费边确认“Update 后才能使用 Claim”的协议行为，不重新授予旧 S 一个新语义类。

逐个读取七个 Request 后，确认其 task、四项 evidence、三项 operations、numeric、
shared obligations 和 answer schema 均与同一个 PublicContext 相等。
全部七个 Request 都包含披露总额 T=`21813`，关系 Evidence 也一直包含完整来源表格的总额行。
所以本轮支持 fixture 实际提交并消费了重建 Claim，不支持它从未看到 T、信息隔离后仍能求解，
也不支持两套来源统计独立。

### 15.4 三个正向 preview 与九个负向 preview

两个合法初始 Action 均以同一 Q0 为输入，实际 preview 结果均为 `admitted.action`：

- 直接使用 F/T 的 `share_ratio`。
- 使用 F/O/关系、参数明确为 sum 的 `relation_sum`。

这证明固定接口在同一初始环境准入两个不同第一动作。
这里没有执行完整直接路线，更没有重新做一次 D/S 有限商比较。

对唯一会话第 1 轮之后的真实 pending State，显式 reject Update 的 preview 结果为：

```text
admitted             true
code                 admitted.update
would_clear_pending  true
would_create_claim   false
committed_updates    0
kernel_calls         0
```

这项结果只支持 reject 接口的准入语义。
唯一正式会话的三个 Update 全部为 accept，实际拒绝数为 0；
reject 后的真实状态转换、替代选择或重新规划没有在本轮执行。

九个负向 preview 的实际拒绝阶段为：

| 控制 | 实际拒绝代码 |
| --- | --- |
| `incorrect_parameters_not_repaired` | `admission.parameters` |
| `action_blocked_until_generator_update` | `admission.pending_update` |
| `observation_is_not_an_accepted_claim` | `admission.accepted_claim` |
| `stale_state_update` | `admission.current_state` |
| `cross_observation_update` | `admission.observation_parent` |
| `missing_proposed_claim_not_host_filled` | `admission.explicit_proposed_claim` |
| `proposed_claim_disagrees_with_observation` | `admission.observed_claim_content` |
| `caller_cannot_claim_model_origin` | `schema.public_submission` |
| `final_requires_accepted_percentage_claim` | `admission.final_accepted_claim` |

三个正向 preview 与九个负向 preview 合计没有产生 callback、内核执行、提交更新或额外完整会话，
实际 State 和 transcript 字节保持不变。九个负向 preview 的“拒绝”不应与会话中的实际拒绝次数混写。

### 15.5 Callback 源码身份与五项 Gate

实际 GeneratorRegistration 保存 `before_first_callback=true`，绑定 fixture 文件：

```text
path
trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_share_public_protocol/fixture.py

bytes   6,172
SHA256  3b73baed69120c0f2771292a8767dad42769fb186e095402ce1f78dab673dfd8
Git blob
05a261a3f3f648a8df8a25c3d9f287c7af974407
```

该文件是源码 authority 中的已提交成员，当前字节与已提交字节一致；
binding 指向 `PublicRequestFixture.generate`，每轮调用前进行已加载类、bound method、
源码编译 CodeType 及实际 globals 身份检查。登记审计实际结果为 `passed=true`、
`errors=[]`，并明确其自身没有执行 callback。

独立 guard 测试还核对原生 callback、实例方法伪造和类方法替换。
类方法替换测试保留真实模块 globals，使其通过该层身份条件，再在
`generator.compiled_method` 被拒绝；因此检查并非只依赖自报字符串。
这仍不是全部传递代码、运行时全局绑定或完整环境闭包的证明。

五个正式 Gate 均通过，失败数为零：

| Gate | 实际结果 | 限定范围 |
| --- | --- | --- |
| G0 | PASS | 新范围、前驱不变性及已提交声明源码 |
| G1 | PASS | 公开投影及登记 callback 责任 |
| G2 | PASS | 唯一实际生成器／Update 会话及独立 QA |
| G3 | PASS | 固定状态上的直接准入控制 |
| G4 | PASS | 零外部执行及历史见证不扩张 |

### 15.6 文件计数、源码 authority 与内容身份

正式目录为：

```text
trusted_data_synthesis/artifacts/qa_reasoning_share_public_protocol/
finance_qa_vnext_share_public_state_proposal_action_observation_update_protocol_preflight_v1_20260905
```

逐成员读取实际文件并验证 SHA-256 后，目录实际为：

| 范围 | 文件数 | 字节数 |
| --- | ---: | ---: |
| 根目录直接文件，包含 Manifest | 17 | 100,002 |
| `session` | 54 | 548,046 |
| 总计 | 71 | 648,048 |

自排除的 Manifest 绑定 70 个成员、637,560 字节；Manifest 自身为 10,488 字节。
全部 70 个成员的实际字节数和 SHA-256 已核对。
文件大小包含每轮完整公开 Request 与 State，不能解释为独立来源数或生成器样本量。

本轮冻结的是 8 个新实现文件、116,544 字节；8 个声明引用文件、79,483 字节，
后者包括旧任务所需的既有工具与支持实现。来源 Task 为 1、Evidence 为 4、操作合同为 3；
没有新增财务 Task、来源页面组或 Archive 扫描。

```text
implementation commit 606b13c35cb3aca4107ee5497451ba51378bb843
implementation tree   6736228347d4d8519c7ac099378a409dc45b8053

reference commit      b6783ac6676c6b821ab819f9215961fbd0605e84
reference tree        475ff81d9e26d9424c1f6942de5cf7eb5cda1fb2
```

关键身份如下：

```text
public context
public_share_protocol_public_context:8b8a2e0ef5eadd71addb113c785a51115f8792d258f61794b88db917f02e234b

protocol
public_share_protocol_contract:784dc1b48c9341949d8528b15c0c73e1ab1f0b9711459f7ce00848e97fcc211c

source authority
public_share_protocol_source_authority:dc55252c9b54648985204c8f809b46d8491d02438293a7aa03843578ea68f4a6

generator binding
public_share_protocol_generator_binding:1d5832df115b8cbb9e20eb0fcec781d937f42769060f11f293ae65c6fba706db

generator registration
public_share_protocol_generator_registration:7b9141467cd9a9e7738e68bffa2ac282955ff0d9fc3580c0248264c57801b911

session manifest
public_share_protocol_session_manifest:ce12bd49ef71f38910a69186ea85b4498d652ac51f8dc4a9429941514e370643

Final
public_share_protocol_final:922696e8fc2b80355d3ae3b7cdb5ee04dc439c3d7a439716d85148e26f3914b2

controls
public_share_protocol_controls:e9bc9717d868227c000f43f8402795446ad53aa195bbf93eb62f1a63168d56e8

Gate
public_share_protocol_gate_evaluation:b4b6b129cc8894d82b4badd1a556a280d26b1152efff4c29ba39af01895103cd

report
public_share_protocol_report:bdd0312614c253858d614b03660685965d593f47ab0eb89f1bf6dbf46352eb10

decision
public_share_protocol_decision:ec3ce0b7c75843c1fcf58e09319bdc9f3beb1f2163dbe3ffb13e64360cffeea2

manifest
public_share_protocol_manifest:8935da52f4f8146c290a5f9875e1e319b4e9f3d7d347efe4dec07aed163dbb66

artifact root
public_share_protocol_root:69c83461068a0ff5c583e93b05b7dab59455d92e12606c389f2105ba075100de
```

独立报告没有另加对象 `id` 字段，其 5,310 字节由正式 Manifest 绑定：

```text
independent_validation.json SHA256
e923063ea98820ccce4c5c475e3507a5efe18c33a58459e81c1b01496442ece1
```

### 15.7 测试记录与前驱保持

本轮四组专项测试合计 **51 项通过，组合运行 1.78 秒**：

| 测试组 | 通过数 | 主要范围 |
| --- | ---: | --- |
| 公开视图 | 13 | 原对象与公开字段、预算、阶段、深拷贝 |
| callback／parser／copy guards | 11 | 实际 callback 身份、严格 JSON 与动态对象隔离 |
| preflight／无执行重建 | 10 | 前驱与工件绑定、冻结、重建及禁止额外执行 |
| 独立语义验证 | 17 | 完整事件重放、语义篡改、登记链和文件／fsync 异常 |
| 合计 | 51 | 本轮专项，不是模型样本 |

独立测试中包括七项完整重算相关内容 ID 后的语义篡改拒绝、三项登记链篡改，
以及三项文件／fsync 异常检查等。这些是测试输入，不增加正式 `direct_controls.json` 的九个负向 preview，
也不增加 callback、内核调用或科学样本量。

无执行重建测试将 Engine、`generate`、三个数值内核、旧来源入口和旧 Runtime 调用设为禁止，
只读取正式会话的既有字节并独立重算验证及报告。重建目录与正式目录全部 71 个文件逐路径、
逐字节相等，仍为 648,048 字节。这个验证没有重新运行唯一会话，
新增完整协议会话、callback 和内核调用均为零；本轮科学样本量始终为一个实际会话。

本轮 12 个源码／测试文件的 Ruff check／format 通过，8 个源码文件 Mypy 和编译检查通过。
扩大到整个 `src/tests` 的 Ruff 检查仍只报告历史文件
`phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution_models.py:2`
的 `I001` 导入排序问题；该文件未改动，不把历史问题包装为本轮已修复。

前驱 65 个文件、254,479 字节保持不变，旧 Task、四项 Evidence、三个操作和 numeric 继续精确复用。
旧 `W_share=1`、两个旧候选有限类及更早 `W=null` 分别保持；
本轮 `new_W_share`、`new_semantic_class_count`、模型类别概率和训练效用均为 null。
独立报告将模型可达性标为 `NOT_MEASURED`，这不是模型失败或模型概率为零的结果。

实际 `source_rescans=0`、`old_candidate_runtime_calls=0`、
`new_quotient_comparisons=0`；Provider、凭证读取、GPU 均为零。
唯一实际会话与固定控制完成后停止，`next_stage_authorized=false`，
旧主链仍为 `remains_paused`。本轮没有通过这一协议正结果恢复在线模型、训练或后继主链权限。

### 15.8 只复用既有会话的复核命令

以下命令在新的临时子目录重建已有正式工件。必须保留 `--replay-from`；
省略该参数会进入新建会话分支，本轮复核不应再次运行该分支。

```bash
protocol_repo=/data1/zhuxinrui/projects/Data-Synthesis
protocol_formal="$protocol_repo/trusted_data_synthesis/artifacts/qa_reasoning_share_public_protocol/finance_qa_vnext_share_public_state_proposal_action_observation_update_protocol_preflight_v1_20260905"
protocol_check_dir="$(mktemp -d /tmp/share-public-protocol-check.XXXXXX)"

PYTHONPATH="$protocol_repo/trusted_data_synthesis/src" \
  "$protocol_repo/trusted_data_synthesis/.venv/bin/python" \
  -m trusted_synthesis.experiments.qa_reasoning_share_public_protocol.preflight \
  --repo-root "$protocol_repo" \
  --external-audit "$protocol_formal/external_review.txt" \
  --source-commit 606b13c35cb3aca4107ee5497451ba51378bb843 \
  --source-tree 6736228347d4d8519c7ac099378a409dc45b8053 \
  --replay-from "$protocol_formal" \
  --output-directory "$protocol_check_dir/replay"
```

成功重建要求全目录字节相等，返回的 `new_generator_callbacks` 和 `new_kernel_calls` 均为 0。
报告内部仍保留原实际会话的七次 callback 和三次内核调用，这是既有执行计数，不是重建新增执行。

四个专项测试的独立命令为：

```bash
cd /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis
.venv/bin/pytest -q \
  tests/test_qa_reasoning_share_public_protocol_view.py \
  tests/test_qa_reasoning_share_public_protocol_guards.py \
  tests/test_qa_reasoning_share_public_protocol_preflight.py \
  tests/test_qa_reasoning_share_public_protocol_independent.py
```
