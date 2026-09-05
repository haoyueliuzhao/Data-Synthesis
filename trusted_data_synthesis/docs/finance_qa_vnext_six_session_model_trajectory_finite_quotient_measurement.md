# 冻结六会话的有限商映射与经验条件分布测量

## 1. 当前状态与本轮问题

本轮零 Provider 测量已于 2026-09-06 完成。五条既有 Qualified 轨迹全部完成有限投影和 Assignment；十个配对得到 6 个等价、4 个保留语义差异、0 个未定，形成两个有效商状态。端到端比例仍为 5/6，成功条件下的经验商分布为 (4/5,1/5)，M01 的完整失败不进入有效类。四个 Gate、12 个隔离测量控制、51 项定向测试通过，真实冻结源码的完整重建复现全部 51 个正式文件的精确字节。规则与限定见下文，正式实测见第 13 节；两类不是预设通过条件。

阶段名称：`finance_qa_vnext_six_session_model_trajectory_finite_quotient_measurement_only`。

正式目录：

```text
trusted_data_synthesis/artifacts/qa_reasoning_share_quotient_measurement/
finance_qa_vnext_six_session_model_trajectory_finite_quotient_measurement_v1_20260906
```

本轮只回答：在已经完整保存的同任务、同生成条件模型轨迹中，哪些完整有效行为按显式冻结的保留/归约规则等价，哪些仍有实际保留语义差异；由此能否物化这批固定样本的经验商分布？

这里要新建的是正式投影、有限等价关系和 Assignment，不是重新证明模型能够完成协议。此前已经观察到的 `disclosed_total` 与 `reconstructed_total_claim` 只是支持描述，不能直接当作本轮 State ID 或等价结论。

## 2. 审计、授权和已知数据性质

本轮依据的审计完整文本为 24,120 bytes，SHA-256 为 `d5d64a7acf39a0400773d8d1cd8db012f3846597d29d038edfce83b2f010d743`。审计接受前一轮真实模型接入与固定六会话结果 `PASS_AS_SCOPED`，无强制修订；它建议使用现有轨迹开展有限商测量，不要求补跑 M01、不要求第七会话，也不建议同时优化提示词。

当前“参照审计继续实验”的指令落实为本轮有界测量，不扩张成新的在线调用许可。Provider、凭证读取、新模型会话、候选 Runtime、数值 kernel、新来源扫描和 GPU 作业预算均为 0。旧主链保持暂停，Contribution、训练发布和 Student 比较不在本轮范围内。

这些模型轨迹及其中的错误已经被观察过。因此本轮准确性质是“已知模型轨迹上的测量规则实例化”，不是数据盲确认或预先不知道结果的验证集评估。可以在正式执行之前冻结本轮规则与代码，但不能由此倒推这些规则是在看到六会话之前确定的。

规则必须逐项公开，不以预期类数作为 Gate。遇到尚不能解释的因果关系，应保留 `undetermined`，不能为得到期望分区而事后选择性删除某些错误。

## 3. 固定历史输入与资格复用

父阶段说明见 [真实模型六会话工程试验报告](finance_qa_vnext_share_public_protocol_model_adapter_six_session_pilot.md)。父目录仍为 2026-09-05 的正式目录：

```text
trusted_data_synthesis/artifacts/qa_reasoning_share_model_pilot/
finance_qa_vnext_share_public_protocol_model_adapter_six_session_pilot_v1_20260905
```

| 父输入对象 | 冻结身份或规模 |
| --- | --- |
| 完整父目录 | 785 files，8,312,321 bytes |
| 自排除 manifest 成员 | 784 files，8,191,735 bytes |
| manifest 自身 | 120,586 bytes |
| parent manifest | `share_model_pilot_manifest:73dbba1f2af7cfb26fe1092fe5a6716b3b58df061a965244c10b615c6401af62` |
| parent root | `share_model_pilot_root:fcc52ce717a9de0e764a6a4feca1f96f367e3f974595a0678ce609f07c3d5ae6` |
| parent source commit | `55fb6aab8d7122b4d930d1c31843e7d3653ccd19` |
| parent source tree | `dc9c8c59c7e9b96e1cf0033d6aa9563faa06ce44` |
| 现有完整模型会话 | 6 |
| 原始公开 Submission | 51，全部具有已保存的 schema-valid 原始公开 JSON |
| Qualified 候选 | 5，来自既有资格报告，不重新推断 |
| 非 Qualified Outcome | 1，M01，完整失败证据仍保留 |
| 本轮同任务无序配对域 | 10，即 `5 choose 2` |

父阶段已有且不由本轮重新采样的事实是：51 次实际 Provider attempts，14 Action、14 Update、5 Final 得到准入，18 条公开提交被拒绝；六会话 evidence-complete / protocol-valid，五会话 Qualified。实际 usage 是 565,082 prompt + 24,852 completion = 589,934 tokens。本轮不会把重新读取这些数字记为新增 Provider 消耗。

| 会话 | 父回调数 | 父 Qualified / Y | 本轮角色 |
| --- | ---: | --- | --- |
| M01 | 12 | false / 0；QA=null | 完整失败 Outcome；不进入有效 Assignment |
| M02 | 7 | true / 1 | 已映射：状态 A |
| M03 | 12 | true / 1 | 已映射：状态 B |
| M04 | 6 | true / 1 | 已映射：状态 A |
| M05 | 9 | true / 1 | 已映射：状态 A |
| M06 | 5 | true / 1 | 已映射：状态 A |

五条 Qualified 轨迹共有 39 条原始提交，其中 27 条准入、12 条拒绝；M01 的 12 条提交、6 条拒绝及预算失败仍在六会话完整总体中。39、51、5 和 6 是不同统计对象，不能互换分母。

输入实现见 [inputs.py](../src/trusted_synthesis/experiments/qa_reasoning_share_quotient_measurement/inputs.py)。`load_inputs` 校验父 manifest/root、完整文件几何、已声明源码的 commit/tree/current-byte 一致性、六个预登记 declaration、原 qualification、各 session manifest/stop 及固定条件，随后只用父 `read_session_records` 读取有序事件。

本轮不导入父 preflight，不调用父 `audit_session`、`audit_records` 或 `replay_pilot` 重做整个适配器/QA 审计。资格 authority 明确为未修改、已被父 manifest 绑定的 `online_reports/M01.json` 至 `M06.json`；新输入层核对这些资格记录的 parent 和固定总体，不产生新的 QA 判决。

新 `parent_freeze` 列出全部 785 个父文件的路径、hash 和 bytes，包括父 manifest 自身，并绑定六个会话的 declaration、qualification、session manifest、initial State 和 stop 引用。原始交互留在父目录，新的投影不必复制整套 8.3 MB；引用链和输入不变性检查保证它们没有被“删除后只剩最终路线”。

## 4. 生成条件与验证语义不变

模型、提示、Update schema、Task、Evidence、Operation 和数值合同均不在本轮修改。条件从父冻结资料直接引用：请求模型 `deepseek-v4-pro`，文档版本标注 `DeepSeek-V4-Pro-0813`，thinking disabled，temperature=0.7，top_p=1.0，每会话 3 Action、3 Update、12 Submission。

这里仅引用 2026-09-05 已冻结条件，不重新浏览模型目录、探测端点或读取凭证。文档版本与父响应 model/fingerprint 也不构成远端权重不可变证明；本轮绑定的是既有请求条件与实际接收记录，不声称现在重新调用仍会得到相同权重或行为。

`condition_binding` 绑定精确 Task、PublicContext、协议、model configuration、pilot registration、本轮 measurement contract、数值规则、答案 schema 和共同义务。Qualification 引用进一步绑定到实际 session manifest 与原始轨迹。

旧 D/S fixture 的证据和更早商语义文档可用作规则解释，但不进入本轮模型总体或状态频率；旧 State ID、历史“两类”以及父 `support_description` 不作为新比较器的判定 authority。更早任务的 `W=null` 也不因本轮测量被覆写。

## 5. 三层记录，避免两个相反错误

本轮表示为“类型化有向公开因果多重图 + 完整协议纠正账本”，而不是一个最终答案字符串或分母标签。规则入口见 [models.py](../src/trusted_synthesis/experiments/qa_reasoning_share_quotient_measurement/models.py)，当前有限事件解释见 [projection.py](../src/trusted_synthesis/experiments/qa_reasoning_share_quotient_measurement/projection.py)。

| 层次 | 记录内容 | 是否可直接决定新策略类 |
| --- | --- | --- |
| 原始交互轨迹 | 全部提交、Receipt、反馈、计数、预算、原顺序与终止 | 不能省略；也不能仅按回调次数分新类 |
| 任务解决行为图 | 实际 Action/execution/Observation、显式 accept Update、accepted Claim、实际依据边和 Final | 保留的语义结构是有限比较对象 |
| 协议纠正账本 | 每条拒绝、前后提案、字段差异、下一次准入、C0–C4 检查和成本 | 只有明确满足归约前提时不用于分类；原证据仍保留 |

不能“删除所有拒绝，再只看最后分母，输出两个类”；也不能“每多一次接口拒绝就创建一个策略类”。这两种做法都绕开了应明确的语义保留/归约规则。

前一次未获准提案与后一次新的合法提交是不同原始对象。特别是，模型曾提出一个六位 proposed value，不等于系统接受了该值后又撤销或修订它。是否存在真正的知识状态变化，必须从 Receipt、实际 execution/Claim 和前后 State 中判断。

## 6. 保留的类型化行为图

有限图节点种类为 evidence、action、execution、observation、update、claim、final。PublicContext 中四项 Evidence 都作为固定上下文保留；“可见”不等于“使用”，实际使用由 operand、basis、lineage、grounding 和 citation 边标明，不能仅按 Evidence 节点是否存在判断支持路线。

每条有效轨迹至少保留下列信息：

- Evidence 的实际来源、authority、locator、内容、数值/关系、metric 和上下文。
- Action 前的 public basis、operation 合同、parameters、operands 的角色和顺序，以及实际 resolved input 内容。
- Action → execution → Observation 的生产关系，以及 Observation 当时仍处于 pending、没有自动新增 accepted Claim 的状态边界。
- Observation → 显式 Update → accepted Claim 的因果关系、完整 proposed Claim、grounding、lineage、accepted status 和公开所有权。
- Claim 的生产—消费依赖、真实 Final 所消费的 accepted Claim、答案、citations、basis 和终止语义。
- 所有实际执行及接受的对象，不只保留 Final 的祖先；不能把执行后未用于 Final 的真实语义活动无条件裁掉。

例如，如果某轨迹确实消费了重建总额，图中必须保留 F/O/关系 → relation_sum → Observation → accept Update → 总额 Claim → share_ratio 的生产链；直接使用披露 T 的轨迹则保留 T → share_ratio 的实际输入边。两者并不能靠重命名运行时 ID 消除差异，但仍须比较其余完整保留结构，不能让这个示意替代正式十个配对。

受控的表面变化包括一致的节点 ID 双射、纯显示标签和已登记集合字段的顺序。evidence_refs、claim_refs、observation_refs、lineage、grounding、citations 按集合语义处理；实际 operand 顺序默认保留，仅 `relation_sum` 两个同角色 member 槽位依原操作合同允许交换，relation 槽位不随意移动。

有限 Decimal 正规化只消除真正数值相等的表面表示，例如有限数字的冗余尾零；不用 float 容差或近似相等归并不同命题。metric、definition、subject、scope、period、unit、currency 等类型化字段不能因数值一样而被抹去。

节点的原始 record id、event/submission 引用和 turn ordinal 放在 provenance 中。它们用于追溯，但不把某个会话的偶然 runtime ID 本身作为语义标签。实际来源身份、操作合同与证据定位不属于可以随意重命名的“偶然 ID”。

## 7. C0–C4：协议纠正可以归约的具体前提

归约不是看到某个错误代码就直接删除。对每条被拒绝的公开提交，先找到其后最近的一次准入提交，检查从当前拒绝到该次准入之前的连续事件块；若没有后继或解释不足，不能假想一次成功纠正。

| 规则 | 必须检查的实际条件 | 禁止的简化 |
| --- | --- | --- |
| C0 | 当前及该拒绝块都未准入；没有 execution、Observation、Claim 或 Final 对象及相应事件 ID | 把有真实效果的事件当作无效文本删掉 |
| C1 | 拒绝块中的知识状态保持不变：accepted Claims、pending Observation、阶段、实际 Action/Update 计数及其剩余额度等没有改变 | 只看最后答案相同，忽略已接受状态变化 |
| C2 | 后继是最近的实际准入提交；种类和语义目标相同，中间没有别的准入事实 | 跨过一次真实依据切换，把远处成功当作原提案修复 |
| C3 | 变化仅落在下面登记的 Action/Update/Final 对齐范围内，且以实际已有公开事实为准 | 仅按同名 error code 断言等价 |
| C4 | 保存具体字段差异、前后提案、事件/提交/Receipt/State parent、后继准入，以及真实 attempt/submission 和预算影响 | 商归并后把失败消耗也抹掉 |

C1 的知识状态比较允许忽略内容地址 State id、last_feedback、submission_count 和表示其变化的提交剩余计数，但这些字段仍在原记录与成本账本中保留。Action/Update 剩余额度、已接受命题和 pending Observation 不因此被忽略。

C3 的有限范围如下：

| 提交种类 | 登记的拒绝 code | 可以对齐的字段 | 必须保持的语义目标 |
| --- | --- | --- | --- |
| Action | `admission.public_basis` | public basis 与真实 inputs/Claim/lineage 对齐 | operation、有序 inputs、parameters 不变 |
| accept Update | `admission.observed_claim_content` | proposed value/definition 对齐已存在的完整 Observation output | 同一 pending Observation、accept disposition、basis、lineage 与其余类型化上下文不变 |
| Final | `admission.final_grounding` | citations/public basis 对齐既有 accepted answer Claim 的实际 grounding | 同一 accepted answer Claim 与同一 answer 不变 |

Update 的后继合法 proposed Claim 必须完整等于原先已存在的 Observation output，而不是两个不同数字只因“足够接近”而被视为等价。Final 的后继引用则必须符合它实际消费的已接受 Claim；不是给定任意六位答案就允许删改支持。

每条 correction 记录保存 `checks`、`changed_fields`、前后 proposal、相关 parent IDs、following admitted turn、`budget_impact` 和是否保留原始证据。满足全部检查时才标记 `reduce_protocol_correction`；Qualified 轨迹中的解释失败标记 `undetermined`。M01 的纠正记录采用 `excluded_nonqualified`，它不是通过减少错误次数被“修成”有效轨迹。

### 7.1 为什么八次数值变化不是 Decimal 表面等价

父六会话中八次被拒绝的 percent Update 将完整 Observation 值提前写成六位 Final 值。二者如下：

```text
完整 Observation value:
93.508458258836473662494842525099711181405583826159

被拒绝 proposed value / 可用于最终答案的六位表示:
93.508458
```

这两个 Decimal 数不相等。本轮不能通过放宽精度、套用 Final 容差或“表面格式相同”使它们相等。

可能成立的归约理由只能是：较短值从未成为 accepted Claim；pending Observation 一直是同一个完整命题；拒绝没有产生任何执行或知识状态效果；后来的独立模型提交才对齐该既有 Observation；其余 C0–C4 也都满足。正式投影已经逐条保存这些检查结果，实际 12 条 Qualified 拒绝的归约和 M01 六条排除分别见第 13 节。

这八次属于父批次的历史计数，其中一次在 M01；不能把 M01 的 rejected Update 或最终已有的 percent Claim 变成有效 Assignment。其余七次位于五条 Qualified 轨迹内，本轮已逐条完成具体因果检查；归约依据不是父会话后来成功这一标签。另有一次还变更过 definition，必须把该字段差异写入纠正账本，不能只报告 value。

### 7.2 有意义的拒绝或修订不能归约为接口纠正

实际准入的 reject、已接受 Claim 的撤销/替换、新验证事实、真实分母来源切换或下游依赖变化，不能按 C0–C4 当作普通接口纠正删除。当前有限投影只覆盖三种注册操作及显式 accept 的已有事件域；有意义的 reject/revision 若超出该域，应保留完整原事件并返回 `undetermined`，不是“erase 后继续分配类”。

此限制不会抹去父 mock 的实际 reject：mock 不在本轮有效模型候选域，原证据仍由父目录保留。本轮新增的隔离测量控制可以用受控图/记录变体检查“有意义修订不能被忽略”，但不能将这些变体包装为新模型行为。

## 8. 有限比较、关系一致性和 Assignment

本轮无序配对域固定为：

```text
M02–M03  M02–M04  M02–M05  M02–M06
M03–M04  M03–M05  M03–M06
M04–M05  M04–M06
M05–M06
```

比较结果只有 `equivalent`、`different_retained_semantics`、`undetermined`。等价需有完整的语义标签保持节点双射，并保留带角色的有向边及多重性；差异需指出实际保留的节点标签或依赖边差异；未知需报告具体未解释对象或搜索界限。

图 hash 可用于内容身份和缓存，不能作为“hash 不同所以语义不同”的独立判据。最终答案相同、分母描述标签相同、Correction 次数不同，也都不能单独决定等价关系。当前规则登记 canonical permutation 上限为 4,096；超过有限可解释/可判定域时应保持未知，不默认不同。

十个配对之后检查有限关系的完整性、自反、对称和传递一致性，再生成 Assignment。状态身份应绑定固定任务/验证语义、当前协议/生成条件、本轮规则与实际保留语义图；每条 Assignment 另外绑定原 trajectory 和 qualification 证据。不能把旧 D/S State ID 直接复制给新模型轨迹。

规则没有“正好两个类”的通过条件。四条最终支持描述都为 disclosed_total 的会话是否等价，必须由图及纠正判定得出；M03 是否存在另一保留语义类，也必须由实际结构对应关系得出，而不是按旧名称提前分配。

若任一 Qualified 投影或必要配对仍未定，不制造完整分区。应保存未映射对象和未知原因，不能只对容易映射的子集输出一个看似完备的五轨迹经验分布。

## 9. 三种分母与未映射质量守恒

端到端成功与条件分布分开。父六会话已保存的端到端比例继续是 `q_hat = 5/6`；本轮复用该资格结果，不重新计算 QA 或补全 M01。

在全部五条 Qualified 轨迹都完成有效 Assignment 时，对每个本轮状态 z 记录真实计数 n_z：

| 对象 | 计算规则 | 分母含义 |
| --- | --- | --- |
| 端到端成功比例 | `q_hat = 5/6` | 全部六个固定模型 Outcome，包括 M01 |
| 有效状态联合出现频率 | `u_hat(z) = n_z/6` | 全部六个固定 Outcome |
| 成功条件下经验商分布 | `pi_hat_gen(z given Y=1) = n_z/5` | 五条已 Qualified 轨迹 |

完整映射时 `sum(n_z)=5`，`sum(u_hat)=5/6`，`sum(pi_hat_gen)=1`。剩余的 `1/6` 是没有形成 Qualified 终局的历史会话质量，不是一个可进入 VTDO 有效支持集合的成功状态。

若有未映射 Qualified 对象，应明确 `sum(n_z)+n_unmapped=5`，保留成功条件分母 5 与联合分母 6；不能删掉未映射对象，再按较小分母重新归一化并称其为“全部成功轨迹的分布”。必要时完整分布字段保持 null/undetermined，同时报告已知计数和未映射质量。

只有正式配对及分区支持计数结构时才物化对应分数。本轮十对比较和完整分区已经支持计数 (4,1)，因此物化联合频率 (4/6,1/6) 和成功条件下经验分布 (4/5,1/5)；这不是把父支持标签的次数直接升级为商分布。

这些是固定、已知六会话经验数据在本轮规则下的推前频率，不是总体概率、无条件模型能力、训练目标 `pi_t`、最优权重或跨版本稳定分布。Correction 即使不用于区分类，仍会改变这批历史执行的成本与预算失败风险；本轮不消除其实际消耗。

## 10. 新测量对象的有限控制

控制只针对新投影/比较/分母边界，不重做父适配器攻击矩阵、不运行模型/mock 会话、不调用金融 kernel。

| 控制类型 | 要求检查的边界 |
| --- | --- |
| 一致重命名、纯显示标签和获准表面变化 | 不产生伪新类；映射提供完整一致对应 |
| 实际分母生产链或支持使用边改变 | 即使 Final 答案相同，也不能抹平保留语义差异 |
| 有意义的 Claim/Update 因果关系改变 | 不能按普通协议纠正删除；当前有限域不足时保持 unknown |
| 非 Qualified M01 或未定对象被强制 Assignment / 更改分母 | 必须拒绝或保持未定；不把六改五、不把五改已映射数 |

这些控制是输入/图的隔离测量检查，不是新科学样本，不占用或增加固定十个真实无序配对。实际冻结的 12 个控制全部符合预期；具体输入变化、返回类别与限定见第 13.6 节和正式 controls 记录。

## 11. 产物、源码绑定与可重建性

本轮新的 source authority 只声明实际测量实现及所使用的只读引用文件，绑定新的 source commit/tree/current bytes；不声称完整传递依赖或远端模型环境闭包。父 source authority 作为输入引用保持不变，不修改 2026-09-05 的正式源或工件。

正式产物已覆盖以下相互独立的对象；文件、源码和内容身份见第 13 节：

- 外部审计原字节、当前操作指令及本轮零新增执行授权边界。
- 新 source authority、完整 parent freeze、测量合同和固定生成/验证条件。
- 六个原 Outcome 与资格引用；M01 明确 nonqualified，mock/旧 fixture 明确排除。
- 五条有效轨迹的有限图、全部逐事件保留/归约决定、纠正账本和原始 provenance；M01 的原始失败及成本说明继续可追溯。
- 十个配对的三值判定与具体对应/差异/未知证据，有限关系一致性检查。
- 仅在条件满足时产生的 Assignment、状态定义和经验测量；未知不得填成类。
- Gate、限定报告、停止决定及新目录 manifest/root。

新运行前后使用 `assert_unchanged` 核对全部父文件字节。原始输入读取与结构/Decimal 复算是验证，不计作候选 Runtime 执行。记录中的 historical Provider attempts 属于父六会话，本轮新增 Provider 次数始终要求为 0。

重建目标是从同一冻结输入和测量规则重新得到相同新产物，不读取凭证、不创建新模型轨迹、不补跑 M01、不调用旧适配器或金融内核。重建和隔离单元用例也不扩充十配对或六会话科学总体。

安全 CLI 已按实际 preflight 接口列于第 13.8 节。重建会重新计算同一冻结轨迹的投影、十个配对和测量控制；它不是再次运行模型，也不是只复制文件后宣称完成新的语义计算。

## 12. 最终测试与独立验证

本轮四组定向测试合计 51 项通过。冻结前完整运行结果为 `51 passed in 14.38s`；正式工件生成后再次运行得到 `51 passed in 14.63s`，不增加模型样本。

| 测试组 | 用例数 | 主要覆盖 |
| --- | ---: | --- |
| [inputs](../tests/test_qa_reasoning_share_quotient_inputs.py) | 9 | 固定父目录、六个 Outcome、原资格引用、51 原始提交、mock/失败晋升/条件替换拒绝 |
| [projection](../tests/test_qa_reasoning_share_quotient_projection.py) | 20 | C0–C4、完整图、重命名/集合变化、实际因果差异、失败排除、未定及固定分母 |
| [independent](../tests/test_qa_reasoning_share_quotient_independent.py) | 12 | 不调用生产侧测量函数的图/纠正/十对证书/状态/Assignment/频率独立核验，及重哈希篡改反例 |
| [preflight](../tests/test_qa_reasoning_share_quotient_preflight.py) | 10 | 不覆盖输出、审计/源码身份拒绝、完整重建、fsync 顺序、缺失工件、伪造配对/控制/分母拒绝 |
| 合计 | 51 | 都不是新增科学样本 |

测试把 Provider/model/mock 传输、ModelProtocolEngine、三个数值 executor、凭证入口和旧资格重算设为“调用即失败”。独立检查器测试在准备纯内存测量夹具后，还禁用生产侧 projector、comparator 和 measurement producer；独立核验仍能完成其五类检查。

持久化单元测试使用显式标注 `test_only_not_a_formal_source_authority=true` 的隔离源码权威，不能用它冒充真实执行前的 Git 冻结证明。第 13 节的正式测量及独立临时目录重建则真实校验了本轮已提交的 source commit/tree/current bytes。两类验证的证据范围分开记录。

本轮 9 个实现源码与 4 个测试文件共 13 个文件的 Ruff check/format 检查通过；9 个源码文件的 Mypy 与编译检查通过。全项目 `src tests` Ruff 仍只有历史 v26 文件的 `I001`：

```text
src/trusted_synthesis/experiments/vtdo_experiment/
phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution_models.py:2
```

该旧文件没有修改，本轮不声称整个仓库已经零静态检查问题，也没有为扩大测试总数运行旧候选实验。

## 13. 正式测量结果

### 13.1 完成状态、源码和精确输入

正式报告状态为 `finite_quotient_measurement_completed_as_scoped`。本轮源码在正式投影物化前提交冻结：

```text
source commit = aa1451ae261b47218b2a5887f6fbe8f7f01ff871
source tree   = 3ae1cc3639bec151a6f81850aa8f3de7c4ede016
```

9 个实现成员合计 158,165 bytes，6 个声明引用合计 153,546 bytes。引用包括 canonical JSON、只读输入/源码绑定、持久化 writer、父会话只读 reader，以及旧商比较和行为语义设计的声明参照；没有执行旧候选比较器。源码没有在正式测量后修改。这里仍只声明这些成员，不是完整传递依赖或运行环境闭包。

父目录全部 785 个文件、8,312,321 bytes 在测量、验证和重建前后保持不变。新输入没有产生第七会话，没有把四个旧 mock 或确定性 D/S fixture 纳入分母。五条合格轨迹的资格来自父独立报告，不是本轮重新计算出的五次 QA 成功。

### 13.2 六个 Outcome 与五个 Assignment

下表的 A/B 只是便于阅读的新状态简称，不是从旧 D/S 标签继承的类别。正式身份在表后给出。

| 会话 | 历史提交 / 准入 / 拒绝 | 本轮投影状态 | Qualified 纠正归约数 | 有效 Assignment |
| --- | --- | --- | ---: | --- |
| M01 | 12 / 6 / 6 | `not_qualified` | 0 | 无 |
| M02 | 7 / 5 / 2 | `mapped` | 2 | A |
| M03 | 12 / 7 / 5 | `mapped` | 5 | B |
| M04 | 6 / 5 / 1 | `mapped` | 1 | A |
| M05 | 9 / 5 / 4 | `mapped` | 4 | A |
| M06 | 5 / 5 / 0 | `mapped` | 0 | A |
| 合计 | 51 / 33 / 18 | 5 mapped，0 unmapped，1 非 Qualified | 12 | 5 个 |

M01 不是缺失证据或 `undetermined` 投影；它是已知完整失败。其 `graph=null`、无有效 Assignment，六条拒绝按 `excluded_nonqualified` 保留。已经接受的最终 percent Claim 仍不能替代一个实际有效 Final。

正式 State ID：

```text
A = share_quotient_quotient_state:e28821613cfbbb9cfa893fb96cffce4afd8d51aa05c5abcc80baeb09713c7e24
B = share_quotient_quotient_state:fda7bb3c703072097de094c6ec8441ec97cf973190cdb6e4e1588983b0dfa54c
```

A 的成员为 M02、M04、M05、M06，B 的成员为 M03。每个 Assignment 独立绑定新 State ID、实际 projection、原 qualification、session manifest 和固定 condition，而不是靠显示名称赋类。

### 13.3 十个配对及保留语义证书

| 配对 | 正式结果 | 证书类型 |
| --- | --- | --- |
| M02–M03 | `different_retained_semantics` | 实际保留节点语义差异 |
| M02–M04 | `equivalent` | 完整节点双射及所有带角色边保持 |
| M02–M05 | `equivalent` | 完整节点双射及所有带角色边保持 |
| M02–M06 | `equivalent` | 完整节点双射及所有带角色边保持 |
| M03–M04 | `different_retained_semantics` | 实际保留节点语义差异 |
| M03–M05 | `different_retained_semantics` | 实际保留节点语义差异 |
| M03–M06 | `different_retained_semantics` | 实际保留节点语义差异 |
| M04–M05 | `equivalent` | 完整节点双射及所有带角色边保持 |
| M04–M06 | `equivalent` | 完整节点双射及所有带角色边保持 |
| M05–M06 | `equivalent` | 完整节点双射及所有带角色边保持 |

因此是 6 等价、4 保留差异、0 未定。全域完整性、自反、对称和传递检查均通过，随后才生成完整分区。没有“必须两类”的 Gate。

四条 A 轨迹分别有 15 个节点、57 条边，M03 有 20 个节点、113 条边。每条图都含四个共同可见 Evidence；图大小不是差异判据。完整对应还覆盖了 Action 的参数和 basis、实际 resolved inputs、Observation、显式 Update、accepted Claim、grounding、依赖和 Final。

M03 的核心区别不是“执行过一次 sum”这句描述，而是如下已保存的实际生产—消费链：

```text
accepted total Claim
= public_share_protocol_claim:927d24ecd31b1c6e280bd9c2be57c52a5ba75862311d3081f86d50802b2f70c7

ratio execution actually consuming that Claim as denominator
= public_share_protocol_execution:1724bdbdc382fe4a44cb0c130104fb494b590da3e459291d1fec72f102b5884e

accepted percent Claim actually consumed by its valid Final
= public_share_protocol_claim:7e614c1c48f4549c08f59a8e6e68e6e2bbd9a30ce09dc41f0a6e55f57a6c6bfa
```

M03 的实际支持是 F/O/part-whole 关系经 `relation_sum`、Observation 和模型显式 accept 后形成总额 Claim，再作为 ratio 的分母；四条 A 轨迹直接消费披露总额 Evidence。各条 Final 的答案同为 93.508458%，并不能消除实际来源和依赖差异。所有轨迹仍可见披露 T，本轮没有构造信息隔离条件或检查模型私有推理。

### 13.4 12 条归约与 6 条排除的逐项边界

以下轮次均为 1 基回调序号。括号中的后继是最近的实际准入提交；每条归约记录都实际通过 C0–C4，未跨过任何中间准入事件。

| 会话 | 拒绝轮次 → 后继准入 | 原始错误与后续对齐 | 决定 |
| --- | --- | --- | --- |
| M02 | Final 5、6 → Final 7 | F/T/关系引用改为该既有答案 Claim 的实际 F/T grounding | 两条归约 |
| M03 | Update 6、7、8、9 → Update 10 | 提前舍入值改为同一完整 Observation；第 9 次还对齐 definition | 四条归约 |
| M03 | Final 11 → Final 12 | 同一 answer Claim 下的 F/T/关系引用改为实际 F/O/关系 grounding | 一条归约 |
| M04 | Action 3 → Action 4 | percent 操作及 inputs 不变，补齐实际 evidence basis | 一条归约 |
| M05 | Action 3 → Action 4 | percent 操作及 inputs 不变，移除无实际使用的关系 basis | 一条归约 |
| M05 | Update 5、6、7 → Update 8 | 提前舍入值对齐同一完整 Observation | 三条归约 |
| M06 | 无拒绝 | 无纠正块 | 零条 |
| M01 | 六条拒绝保留在失败轨迹 | 不因算术链相似或终态已有 Claim 晋升为成功 | 六条 `excluded_nonqualified` |

M03 的 Final 引用由 T 改为 O 不是运行中换了一条实际计算依据：两次 Final 仍指向同一个 accepted answer Claim，此前实际 ratio 一直消费重建总额。类似地，七次错误 Update 的短值都未被接受；这里没有先接受错误值再修订 Claim。

归约只影响本轮类别表示，不抹去 12 次提交的预算消耗，也不删除 M01 的六次错误。全部原始公开 JSON、拒绝 Receipt、State 反馈、顺序和实际成本继续由父工件与新账本引用。

### 13.5 三种经验对象及有限结论

| 对象 | 本轮实际值 |
| --- | --- |
| 端到端成功比例 | `q_hat=5/6` |
| 状态 A 的联合频率 | `u_hat(A)=4/6` |
| 状态 B 的联合频率 | `u_hat(B)=1/6` |
| 联合有效质量 | `4/6+1/6=5/6` |
| 成功条件下状态 A 频率 | `pi_hat_gen(A given Y=1)=4/5` |
| 成功条件下状态 B 频率 | `pi_hat_gen(B given Y=1)=1/5` |
| Qualified 已映射 / 未映射 | `5 / 0` |
| 完整失败质量 | `1/6`，不是有效商状态 |

正式商类数为 2，只对应这一固定 Task、协议、生成条件、规则和五条有效轨迹。这里不再把新的有限商状态及其经验频率保持为未测量，但也不把它扩大成总体分布或训练目标。

独立的 unknown 控制使一条 Qualified 投影未定后，本实现保守地不物化完整分区：五条 Qualified 都保留为 unmapped，联合/条件分母仍分别为 6/5，完整条件分布为 null，端到端比例仍为 5/6。它没有删掉未知对象后重新归一化。

历史旧 `W_share=1` 及更早 compound Task 的 W null 均保持原样；本轮没有新增 W 计算。覆盖先验、Contribution、类内物化、训练权重和 Student 比较仍为未执行对象。

### 13.6 十二个隔离测量控制

| 控制 | 实际结果 |
| --- | --- |
| 一致图 key 双射、显示标签及序列化顺序变化 | equivalent |
| 已登记 typed set 顺序变化 | equivalent |
| 真正相等的有限 Decimal 表面变化 | equivalent |
| 改变实际分母使用边、保持 Final 答案 | different_retained_semantics |
| 改变 Observation → Update 因果边、保持 Final 答案 | different_retained_semantics |
| 拒绝块中改变已接受 Claim | undetermined |
| 拒绝块中改变 pending Observation | undetermined |
| 被拒绝 Action 与后继之间改变实际 operand | undetermined |
| 被拒绝 Final 与后继之间改变 answer Claim | undetermined |
| 强行将 M01 加入有效投影域 | rejected |
| Qualified 映射未定时保留原分母和五条 unmapped | preserved_unknown |
| 删除 M01 并将总体分母改为五 | rejected |

12 个控制全部符合预期。这些是已知输入/图的隔离变体及测量机制检查，不是新模型行为，也没有为变体重新做 own-qualification。反事实图的差异结果不能增加正式模型类数，正式同任务配对仍只有原五条有效轨迹的十对。

独立检查器对正式图、纠正、配对证书、Assignment 和经验测量作独立核验；保存的控制结果另外由同一冻结 control driver 重算核对，不能把后者描述成独立的第二套控制分类器。

### 13.7 四个 Gate、工件几何及身份

| Gate | 对象 | 结果 |
| --- | --- | --- |
| G0 | 固定历史总体及原资格 | PASS |
| G1 | 有限投影与明确纠正决定 | PASS |
| G2 | 十对、关系一致性与 Assignment | PASS |
| G3 | 经验分母、控制及独立验证 | PASS |

正式目录共 51 个文件、1,086,642 bytes。自排除 Manifest 绑定 50 个成员、1,079,099 bytes；Manifest 自身 7,543 bytes。持久化 receipt 覆盖其前面的 49 个成员及 98 个有序 file/directory fsync 事件，receipt 本身与最终 Manifest 不在该 receipt 的自我覆盖中。

51 个文件不是 51 次新增 Provider 调用。新目录包含六个投影/排除记录、十个配对、两个 State、五个 Assignment、十二个控制以及根级身份、账本、报告和持久化对象；原 51 次公开交互仍保留在父目录。

关键正式身份：

```text
measurement contract
= share_quotient_measurement_contract:1f09e3be2856880fae1936414148bafa694c7a0437bdd3ddaf5ec568c96751be

source authority
= share_quotient_source_authority:027789ca29775927cd1b06090f8dfb7d725a0992fb19c588cd1806959255d43e

parent freeze
= share_quotient_parent_freeze:3dc72c755d66256042a4c185c7438c42969504c2ccd968499cf64d4361b6dd56

partition
= share_quotient_partition:dbf43e852cdb21cd8d876bd64e238f36cf34f3004213b1c823baf07c1f4ee6ea

empirical measurement
= share_quotient_empirical_measurement:9b8e33c8c46aeb3263e7cae76a18ff2d9bd1e5ae86b40476c373a53f20b49757

independent validation
= share_quotient_independent_validation:3e72c8c7f7aaaabcfe5b03254982132e3ceb9fb13d7c5e338acb0762f58e331d

report
= share_quotient_report:839cae2ad653cf8c081731a6fb1225b6d491f469cb6e978bc2a0a8515cce7416

manifest
= share_quotient_manifest:cb6731e6dcbc39e37d148e09836b709b4a6b182f0d487a37662474982944531c

root
= share_quotient_root:57452a01a2aa34be08ae0244bc602410468a62fe03aa8eda2e215274395a8cde
```

正式 [报告](../artifacts/qa_reasoning_share_quotient_measurement/finance_qa_vnext_six_session_model_trajectory_finite_quotient_measurement_v1_20260906/report.json)、[分区与 Assignment](../artifacts/qa_reasoning_share_quotient_measurement/finance_qa_vnext_six_session_model_trajectory_finite_quotient_measurement_v1_20260906/relation_partition.json)、[纠正账本](../artifacts/qa_reasoning_share_quotient_measurement/finance_qa_vnext_six_session_model_trajectory_finite_quotient_measurement_v1_20260906/correction_ledger.json) 和 [Manifest](../artifacts/qa_reasoning_share_quotient_measurement/finance_qa_vnext_six_session_model_trajectory_finite_quotient_measurement_v1_20260906/artifact_manifest.json) 可分别核对这些对象。

### 13.8 真实冻结源码重建与安全 CLI

正式测量后，在独立临时目录中使用正式 source authority 的真实 Git commit/tree 重新运行 `replay_measurement`。全部 51 个文件、1,086,642 bytes 与原正式目录逐文件、逐字节一致；原目录及父 785 文件均未修改。

本次重建会重新进行同一有限投影、十个配对和控制的计算，并独立核验结果；不是新增十对统计观察，也不声称完全禁止了生产侧 projector/comparator。新增 Provider、凭证读取、模型会话、候选 Runtime、数值 kernel 执行、GPU 作业和统计样本都为 0。

只需检查保存工件时，可从仓库根目录执行：

```bash
cd trusted_data_synthesis
PYTHONPATH=src .venv/bin/python -m trusted_synthesis.experiments.qa_reasoning_share_quotient_measurement.preflight \
  --mode validate \
  --repo-root .. \
  --replay-from artifacts/qa_reasoning_share_quotient_measurement/finance_qa_vnext_six_session_model_trajectory_finite_quotient_measurement_v1_20260906
```

`validate` 独立核验正式测量对象，并重算隔离测量控制；它不生成新的正式目录，也不执行模型或旧候选。若需验证完整产物可重建性，同样从仓库根目录执行下列命令，输出到新临时父目录中尚不存在的子目录：

```bash
cd trusted_data_synthesis
share_quotient_replay_tmp="$(mktemp -d /tmp/share-quotient-replay.XXXXXX)"
PYTHONPATH=src .venv/bin/python -m trusted_synthesis.experiments.qa_reasoning_share_quotient_measurement.preflight \
  --mode replay \
  --repo-root .. \
  --replay-from artifacts/qa_reasoning_share_quotient_measurement/finance_qa_vnext_six_session_model_trajectory_finite_quotient_measurement_v1_20260906 \
  --output-directory "$share_quotient_replay_tmp/rebuilt"
```

两条命令均不接受模型凭证参数，不调用父 `prepare`/`online`，也不续跑 M01。输出目录必须不存在；实现采用 no-replace 写入，不应把正式目录作为新的输出目标。临时副本可保留检查，以上命令不删除任何文件。

## 14. 完成条件与不扩张的后续边界

本轮完成条件只有四类：精确六会话输入总体不变；每个保留/归约决定有实际事件和冻结规则依据；十个配对、有限关系与 Assignment 一致；经验计数、成功条件分母、未映射质量和生成条件明确分开。不是“所有轨迹成功”“必须两类”或“必须得到期望比例”。

本轮五条有效模型轨迹已经完成非退化的正式分区，因此支持“固定条件下多个有效商状态与这批样本的经验分布已被实例化”的有限声明。若尚有未解释纠正因果，只修复该测量解释边界，不重新采样、重扫来源或返回整个 callback 安全审计。

无论哪种结果，都不自动授权 Contribution、覆盖先验、训练目标权重、Student 比较或旧主链恢复。父执行结果、失败记录与模型条件保持原样；本轮之后的新任务仍需明确范围。
