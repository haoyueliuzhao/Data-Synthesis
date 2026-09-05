# Finance QA vNext：模型可见 State 与公开提案—Action—Observation—Update 协议预检

本轮将已经通过有限 D/S 验证的收入占比任务接入公开交互协议。
研究对象是生成器能否通过真实回调提交行动及后续 Update，Host 能否依据当前 State 验证并执行这些提交，
而不是再次证明旧的两条确定性路线有不同支持语义。

这是零 Provider 的最小接入预检。唯一正向交互采用已登记的确定性 fixture，
不使用模型，不把 fixture 的选择描述为模型行为，也不测量模型可达性或生成分布。
正式执行结果、工件身份及测试总量统一记录在第 15 节；前面的接口说明不能替代实际执行证据。

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
全部传递依赖、运行时全局绑定或完整执行环境已经闭合。最终源码与工件中的对应检查在正式结果区核对。

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
合计七次回调。是否完整达到该计划，只能由正式交互记录决定。
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
它们是固定状态上的接口反例，不是额外实际失败轨迹或额外模型样本。

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

## 14. 预期解释与停止边界

如果唯一交互和协议验证通过，本轮最多支持：固定任务可以经当前公开 JSON 协议完成一次
由已登记确定性 fixture 提交、Host 验证执行、生成器显式接受更新的有限交互。
这使未来模型接入的责任边界具体化，但不等于模型接入或模型能力测试已经完成。

本轮不赋予新的 `W_share`，不新增旧任务语义类数，不依据七次 fixture 回调估计模型概率，
不声称完整规划多样性、reject 后重新规划、模型依据选择能力、Contribution、Novelty 或训练收益。
旧 `W_share = 1` 和更早 `W = null` 作为不同历史对象分别保留。

完成唯一预注册交互和固定控制后即停止，不替换 fixture 或扩展来源直到出现更好的结果。
如果 callback 失败，保留有类型的错误，不由 Host 换入备用提案；协议预算耗尽时按冻结规则结束。
Provider 适配器、模型可达性、在线调用、训练、Release、VTDO 及旧主链恢复都需要另外明确的后继范围。

## 15. 正式结果与工件身份

本节为唯一正式结果区。正式执行尚未写入本文，不从前述源码、计划或 preview 设计推定通过。
后续仅根据实际工件补齐：唯一会话的 callback／Action／Update／Final 计数、独立验证结果、
三个正向 preview 与九个负向 preview 的实际准入状态、callback 实现来源绑定、测试总量、
前驱字节不变性、正式文件与字节计数、关键内容 ID、源码提交／树绑定及停止决定。
