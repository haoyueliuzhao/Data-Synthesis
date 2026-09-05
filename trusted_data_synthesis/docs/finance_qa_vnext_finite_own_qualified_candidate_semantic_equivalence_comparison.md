# 固定六条 own-qualified 轨迹的有限公开行为语义比较

日期：2026-09-05。

本轮在 F1、F2 各自的固定候选域内完成了公开行为语义比较：六个同任务无序配对全部为 `equivalent`。每个任务的主要候选 B/A 属于同一类，调度控制 C 也属于该类。四项完成 Gate 为 **4 PASS / 0 FAIL / 0 UNKNOWN**，22 项新增投影与比较器局部控制全部通过。

这个结果限于已冻结的六条确定性轨迹、已接受的任务与验证合同，以及本轮冻结的有限归约规则。它支持“当前候选族中的透明 lookup 转发、同一 Evidence 的直接引用及独立 growth 换序未产生新的保留行为语义”。它不证明全局只有一种有效解决行为，也不测量模型可达性、概率、关键推理深度、Contribution 或训练收益。

本轮没有新增候选声明、候选 Runtime 执行、任务、Evidence 或 Operation，没有调用 Provider、读取 API 凭证或启动 GPU 作业。历史 40 个已执行 Action 和 6 个 Final 工件全部保留原字节，旧主链继续暂停。

## 1. 实验对象与正式入口

阶段：

```text
finance_qa_vnext_finite_own_qualified_candidate_semantic_equivalence_comparison_only
```

正式目录：

```text
trusted_data_synthesis/artifacts/qa_reasoning_finite_comparison/
finance_qa_vnext_finite_own_qualified_candidate_semantic_equivalence_comparison_v1_20260905
```

本轮承接的[前轮可构造性报告](finance_qa_vnext_reasoning_behavior_typed_candidate_family_constructibility_preflight.md)已经证明 B/A/C 在各自实际路线下可执行并可验证，但将语义类数保留为 `null`。本轮执行的是该报告尚未开展的有限语义测量，没有将历史未评估值回写成前轮已知结论。

本轮外部审阅文本为 23,746 bytes，SHA-256 为 `4987d122e9f128db658544b89d46a076133eb8617d1c2c0378492f774c5d0450`；操作指令为“参照审计继续实验”。外部审阅本身访问的是前轮报告并进行了算术核对，未读取仓库实际工件或重跑验证器。本轮的原始文件读取、只读验证及图对应证据由本轮实现另行产生，不能将两者的访问范围混写。

主要工件可以从下列入口读取：

- [report.json](../artifacts/qa_reasoning_finite_comparison/finance_qa_vnext_finite_own_qualified_candidate_semantic_equivalence_comparison_v1_20260905/report.json)：结果、Gate 和来源身份汇总。
- [measurement_contract.json](../artifacts/qa_reasoning_finite_comparison/finance_qa_vnext_finite_own_qualified_candidate_semantic_equivalence_comparison_v1_20260905/measurement_contract.json)：比较前持久化的保留字段、归约条件及对应规则。
- [projection_audit.json](../artifacts/qa_reasoning_finite_comparison/finance_qa_vnext_finite_own_qualified_candidate_semantic_equivalence_comparison_v1_20260905/projection_audit.json)：六图的实际恢复与 16 个 lookup 实例检查。
- [pair_results.jsonl](../artifacts/qa_reasoning_finite_comparison/finance_qa_vnext_finite_own_qualified_candidate_semantic_equivalence_comparison_v1_20260905/pair_results.jsonl)：六个配对的完整节点双射、双向边核验和归约证据。
- [finite_comparison.json](../artifacts/qa_reasoning_finite_comparison/finance_qa_vnext_finite_own_qualified_candidate_semantic_equivalence_comparison_v1_20260905/finite_comparison.json)：每任务 primary/control 分区。
- [projection_controls.json](../artifacts/qa_reasoning_finite_comparison/finance_qa_vnext_finite_own_qualified_candidate_semantic_equivalence_comparison_v1_20260905/projection_controls.json)：22 项隔离局部控制及各项实际结果。
- [artifact_manifest.json](../artifacts/qa_reasoning_finite_comparison/finance_qa_vnext_finite_own_qualified_candidate_semantic_equivalence_comparison_v1_20260905/artifact_manifest.json)：正式目录成员及全部文件的哈希、字节数。

## 2. 输入冻结与源码身份

唯一轨迹来源仍为：

```text
trusted_data_synthesis/artifacts/qa_reasoning_candidate_family/
finance_qa_vnext_reasoning_behavior_typed_candidate_family_constructibility_preflight_v1_20260905
```

前轮正式目录共 278 个文件、1,176,762 bytes。其 Manifest 为：

```text
qa_reasoning_candidate_family_manifest:a9fa15d097fa30dada250c69ca17906cc4a197e0aa635b1d4b80b5f62931bb64
qa_reasoning_candidate_family_root:9e6be2dea9a8566e613374b726f654715a9f458ba9ca82fd490ed01e6696b83b
```

输入恢复读取已存的候选声明、执行描述、候选结果及独立验证结果，并按确切身份连接 Archive 中的原始行、EvidenceBundle 和 RealizedTaskPackage。恢复候选的 Pydantic 对象仅用于反序列化与已有内容身份校验，不构造一批新的候选。实现没有调用 `source_inventory`、`build_family`、`run_candidate` 或旧实验 builder。

前轮 Manifest/Root、原始 Archive、已接受设计、前轮源码成员及当前注册 Operation 合同均在读取阶段绑定。构建结束再次检查历史正式目录、Archive 和设计目录的全部文件字节未变。

本轮测量实现绑定到：

| 对象 | 精确身份 |
| --- | --- |
| 本轮实现 Commit | `b1e43da622c7fc10823c3d40d02d9b6445fdfe38` |
| 本轮实现 Tree | `b33869265ee66faa25b997c1029bae8f6f7115c9` |
| 前轮实现 Commit | `bc4a6217ab22e2f24e8a40ca14824291ae09b576` |
| 前轮实现 Tree | `a41d7d2748187a82f0ddcec35287b4b90c9c6966` |
| 本轮直接参考 Commit | `2109f8ce9cab0a73539cc4d29f731aaa0e6793f3` |

`source_authority.json` 分别核对本轮 7 个实现成员和 3 个直接参考成员的 Commit、Tree、Blob、当前字节；输入冻结还重新核对前轮声明的 26 个源码/参考成员。这里的结论是这些明确成员的来源闭合，没有声称完成任意传递导入或整个运行环境的闭合证明。

## 3. 固定任务、Evidence 和候选域

F1 的任务身份为 `task:8d0e3d8dd2b5f4f981b72d7c9e600798229e246dd909a15746b5232ad648d2af`，F2 为 `task:c3c91045437afe06ab99c74655f93989bb9525428e76b14d41f792dfbb595c28`。两个任务分别比较同一主体的收入与营业利润在对齐期间上的增长率，并报告两增长率之差的绝对值，单位为 `percentage_points`。

从实际 Evidence 恢复的标量如下。四项财务标量的单位均为 `million USD`，货币为 `USD`。

| 任务 | earlier / later | revenue earlier | revenue later | income earlier | income later | 已保存最终答案（percentage points） |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| F1 | 2014 Q2 / 2014 Q4 | 1719 | 1927 | 181 | 144 | `32.54204712363284576989705565` |
| F2 | 2014 Q1 / 2014 Q3 | 1594 | 1717 | 159 | 171 | `0.169266826069458582893397411` |

Evidence 的原始 JSON 定位前缀均为 `/HII/2015/page_121.pdf-1/table_ori/`。F1 的收入 earlier/later 分别位于 `2/2`、`2/4`，营业利润位于 `3/2`、`3/4`；F2 对应为 `2/1`、`2/3`、`3/1`、`3/3`。完整 Evidence ID、版本、断言、来源身份、文档版本、内容哈希、表格单元格、时间窗口与定义仍保存在各图的 Evidence 节点中。上表仅便于读者核对，不替代这些精确来源绑定。

上表答案来自冻结执行记录，并经本轮只读答案验证重新核验。本轮数值规范化精确保持已存 Decimal 的数值，不将已保存的有限小数表述成无限精度的实数计算结果；Operation 的计算、输出及验证语义沿用已冻结合同。

| 路线 | 历史实际路线 | 每任务已执行 Action | 本轮角色 |
| --- | --- | ---: | --- |
| B | 四个 lookup、两个 growth、signed gap、absolute gap | 8 | primary candidate |
| A | 直接 Evidence.value、两个 growth、signed gap、absolute gap | 4 | primary candidate |
| C | 保留 B 的 lookup 顺序，交换两个独立 growth 的执行顺序 | 8 | scheduling regression control |

F1、F2 均使用上述三条已冻结轨迹。因此实际输入是 4 个主要候选与 2 个调度控制，总计 6 条轨迹。没有跨任务配对，也没有将 F1/F2 的来源或数值差异当作同任务多类证据。

## 4. 比较前冻结的测量规则

本轮形式化对象为：

```text
N_R(G_public(actual_saved_trajectory_i))
    typed-isomorphic-to
N_R(G_public(actual_saved_trajectory_j))
```

`measurement_contract.json` 和包含六条确切候选身份的 `measurement_population.json` 在投影及正式配对比较前持久化，`rule_freeze_receipt.json` 绑定两者的实际字节及持久化事件。比较前和全部控制后均重新检查这些规则字节未变化。

候选及前轮执行结果已经被观察过，因此准确定位是“在已知候选上的测量规则实例化与有限比较”。本轮不声称数据盲确认，也没有按得到的类别数修改归约规则。

数值比较仅对明确类型化的数值字段应用有限 Decimal 精确相等，不使用两两容差、浮点近似或依赖 Decimal 上下文的 `normalize()`。例如 `1.0` 与 `1.000` 可规范化为同一数值，而第 39 位有效数字的差异仍保留。Evidence 抽取置信度、Task 难度等既有有限浮点元数据通过实际二进制浮点值精确保留；这些元数据不会被当成财务数值作容差归并。

Operation 参数 `{}` 来自确切注册合同的空参数约束及已通过的 own-source 验证。保留的 Operation 合同包括完整输入/输出模式、操作角色、输入顺序策略、公式、语义/执行器/验证器版本、参数、selector、兼容性、舍入和容差政策。

| Operation | semantic_version | formula_id |
| --- | --- | --- |
| lookup | `1.0.0` | `lookup.formula.v1` |
| growth | `1.0.1` | `growth.relative_change_abs_base.v1` |
| signed_percentage_point_gap | `1.0.0` | `percentage_point_gap.observed_minus_reference.v1` |
| absolute_percentage_point_gap | `1.0.0` | `percentage_point_gap.absolute_value.v1` |

有序输入始终保留。growth 的 earlier/later 分别占据 `baseline_or_earlier` / `comparison_or_later`；signed gap 的 reference 是营业利润增长率，observed 是收入增长率。最后取绝对值没有授权交换前面的 reference/observed 角色。

## 5. 从实际公开记录恢复的类型化结构

投影直接读取各步实际 `proposal`、`receipt`、`execution`、`observation`、`update`、相邻 State 以及 Final。图没有从 B/A 名称、候选模板或 Oracle 节点列表生成。

每张规范化图保留 12 种节点类型：

| 节点类型 | 每张规范化图数量 | 保留内容 |
| --- | ---: | --- |
| task | 1 | 精确 Task、公开问题、验证/答案合同、scope、绑定快照 |
| evidence | 4 | 精确角色、来源、定位、版本、期间、单位、定义、值与元数据 |
| host_comparability | 1 | 实际 Host 来源及期间/指标/定义/单位/货币/主体可比性检查 |
| decision | 4 | `requires` 关系、实际期望 Claim 语义、Evidence/Claim 依据边及字段来源 |
| receipt | 4 | 实际行动前持久承诺及 Host 来源 |
| operation | 4 | 完整注册语义合同、有序输入、实际输出、执行状态及来源 |
| observation | 4 | 实际 Operation 输出与 Host 来源 |
| claim | 4 | 实际值、单位、语义、verified 状态、Observation grounding 与 Evidence 支持 |
| update | 4 | 实际 Observation 支持的 Claim 接受与 Fixture 来源 |
| state_effect | 4 | 实际前后可见 Evidence、Claim 增加/修改/移除及完成/观察关系 |
| obligation | 5 | 五项必要义务及实际履行引用 |
| final | 1 | 由已验证 Claim 得出的答案 disposition、结果、完整引用关系及来源 |

上述数量合计 40 个节点。图中的生产、消费、依据、grounding、更新、State 成员关系、义务和 Final 引用共形成 127 条有向类型化边。`completes_operation` 等边表达 State 中的完成关系，不把图的所有关系误读成时间正向的执行步骤。

Host 的可比性检查始终保持 `host_derived`。提案、Claim、Update 和 Final 的确定性控制字段保持 `deterministic_fixture`；没有将 Host 判断改写成模型推理。五项必要义务为：可比性、收入增长、营业利润增长、有序 signed/absolute 精确合并、最终 grounding。各义务由独立验证结果中引用的实际 Claim、Evidence 或 Host 检查连接，并再次核对实际生产者与支持集合。

运行 ID、工件路径和纯装饰性路线标签进入审计信息；不冲突的线性调度不作为类别标签。实际就绪性仍根据已保存的生产—消费依赖和前一 State 检查，语义相关的 Claim 和来源边不会因忽略线性序号而消失。

每份投影同时保存 `audit.uncontracted_graph`、实际 State 快照、记录 ID 和读取文件哈希，以支持从归约结果回到原始公开结构。无法解释的额外字段、缺失字段、未知 typed semantic 或未授权效果均使 `normalization.complete=false`，进入 `undetermined` 路径。

## 6. 16 个实际 lookup 的条件性收缩

B/C 共涉及 `2 tasks × 2 routes × 4 lookups = 16` 个 lookup 实例。16 个实例均满足全部五项条件，结果和完整事实保存在 `lookup_contraction_witnesses.jsonl`。

| 条件 | 本轮读取并核对的事实 | 实际结果 |
| --- | --- | --- |
| 精确注册语义 | 实际 proposal 合同哈希绑定确切 lookup 版本、公式、`transparent_projection` 及输入角色 | 16/16 |
| 值与来源保持 | 实际 selected_ref、整份 payload、单位/货币、Evidence 角色、Observation 和 Claim 输出一致 | 16/16 |
| 引用可替代 | 每个实际消费者的生产 Claim、selector、位置、注册角色及替代后的精确值保持一致；无额外义务/Final 直接消费 | 16/16 |
| 当前信息合法 | lookup 及各消费者对应 State 已可见同一 Evidence，且 scope 绑定一致 | 16/16 |
| 无额外保留效应 | 完整前后 State、proposal、execution、observation、update 和 claim 的字段/增量检查只出现透明转发的承诺、观察及 verified Claim | 16/16 |

这里的 selector 组合来自实际保存字段：lookup 以 `selector=null` 读取 Evidence payload，其输出包装为 `{selected_ref, payload}`；growth 消费该 Claim 时使用 `payload.value`。A 的实际 growth 则直接从同一 Evidence 的 payload 使用 `value`。收缩将这两条引用路径对应到同一 Evidence、同一精确值和同一 growth 操作数位置。

透明 lookup 的 Claim 原本具有实际 Observation 支持并变成 verified。收缩许可来自其所证明的命题只是当前已可用 Evidence 的透明转发、其消费者和公开依据可以精确替代，且完整 State/Update 没有其他验证结论、拒绝、修订或失效效果。注册为透明 Operation 只是五项检查中的一项。

投影归约相应的 decision/receipt/operation/observation/claim/update/state-effect 结构，并移去仅指向该透明转发 Claim 的依据边；原始 Evidence 依据、消费者有序输入和来源关系继续保留。原历史执行文件没有删除或重写，A 也没有被补写成执行过 lookup。

| 任务/路线 | 历史 Action | 收缩前图节点/边 | 检查并通过的 lookup | 规范化图节点/边 |
| --- | ---: | --- | ---: | --- |
| F1/B | 8 | 68 / 195 | 4 | 40 / 127 |
| F1/A | 4 | 40 / 127 | 0 | 40 / 127 |
| F1/C | 8 | 68 / 195 | 4 | 40 / 127 |
| F2/B | 8 | 68 / 195 | 4 | 40 / 127 |
| F2/A | 4 | 40 / 127 | 0 | 40 / 127 |
| F2/C | 8 | 68 / 195 | 4 | 40 / 127 |

图节点数只描述本轮测量表示，Action 数描述历史执行。两者均没有被当作关键决策推理深度，也没有被转换成能力或成本效用提升结论。

## 7. 六个配对及完整对应证据

比较器按节点类型和全部属性构造有限候选对应，再检查所有有向边的多重集合。它保存可检查的完整节点双射和边双射，验证正向映射与反向映射、每个操作数角色、位置、selector、实际选值及语义。哈希与最终答案都没有被用作单独的等价判据。

| 任务 | 配对 | 目标 | 结果 | 搜索状态数 | 完整对应 |
| --- | --- | --- | --- | ---: | --- |
| F1 | B–C | 独立 growth 换序回归 | equivalent | 50 | 40 节点 / 127 边 |
| F1 | B–A | 透明转发与直接 Evidence | equivalent | 51 | 40 节点 / 127 边 |
| F1 | A–C | 两项归约的交叉一致性 | equivalent | 49 | 40 节点 / 127 边 |
| F2 | B–C | 独立 growth 换序回归 | equivalent | 47 | 40 节点 / 127 边 |
| F2 | B–A | 透明转发与直接 Evidence | equivalent | 51 | 40 节点 / 127 边 |
| F2 | A–C | 两项归约的交叉一致性 | equivalent | 56 | 40 节点 / 127 边 |

每次有限搜索的上限为 100,000 个状态；六次均已完成。六份证书的 `complete_node_bijection_verified`、`all_node_attributes_verified`、`all_directed_edges_forward_verified`、`all_directed_edges_backward_verified` 和 `ordered_roles_and_positions_preserved` 均为 true。

除比较器自身证书外，本轮还以不导入比较器、候选验证器或 Runtime 的独立只读脚本检查了已生成工件：逐项覆盖左右两侧各 40 个节点身份和属性、将全部 127 条左边按证书重映射并与右边多重集合相等比较，核对边证书左右索引均完整覆盖且引用的边就是实际保存的边。六份证书均通过。此检查是工件证书复核，不是新增候选执行或另一批样本。

分区结果为：

| 任务 | 主要候选分区 | 主要候选类数 | 含控制的完整分区 | C 是否为独立策略见证 |
| --- | --- | ---: | --- | --- |
| F1 | `{B, A}` | 1 | `{B, A, C}` | 否 |
| F2 | `{B, A}` | 1 | `{B, A, C}` | 否 |

这些是分别以 F1、F2 为任务条件的类数，不能相加后表述为“同一任务存在两类”。

## 8. 新增比较器的局部控制

四组控制共 22 项，均通过。

| 控制组 | 数量 | 关键实际行为 |
| --- | ---: | --- |
| 操作性不变性 | 6 | 一致的节点/边 ID 改名、纯标签、图序列化顺序、F1/F2 实际调度控制、Decimal 尾零表面变化均等价 |
| 保留语义差异 | 3 | Final 相同而 Evidence 来源改变、有序角色改变或超 28 位 Decimal 有效数字改变时，返回有差异位置的 `different_retained_semantics` |
| 透明额外效果保护 | 1 | 在实际 lookup witness 的 after State 中加入额外验证结论，重新计算条件后返回 `eligible=false, status=undetermined` |
| 不支持/缺失/未闭合 | 12 | 未知结构/Schema/字段，缺 Evidence/版本/Claim 角色/selector/归约记录，搜索预算为零，未准入输入及未知/矛盾关系均不产生虚假的确定分区 |

透明控制修改的是完整实际 State witness 中的 `additional_validation_outcome`，没有直接把某个 `passed` 摘要标志改成 false。检查器重新读取该 witness 的字段和状态增量，拒绝把新增结论随 lookup 一并消去。

`undetermined` 与输入未准入分开处理。前者保留未知位置并将对应未闭合域的类数保持 `null`；后者不进入三值语义关系，也不被计为新类。另有控制验证：B–C 已等价、涉及 A 的关系未知时，不能把 A 自行分开或并入；相互矛盾的等价/差异关系也不能形成确定分区。

这些控制是实际投影、归约 witness 或有限关系表的隔离修改，不是完整新 Qualified 金融轨迹，不计入正式商类见证。特别是保持 Final 的图修改可能不满足完整 Runtime 一致性；它们只检查新增比较器是否会错误忽略保留字段。本轮没有重做前轮的整套 Runtime 拒绝控制，也没有实施完整因果链联合伪造或真实动态 Evidence 到达实验。

## 9. 只读验证、执行预算和完成 Gate

正式构建对六条已保存轨迹各调用现有独立只读验证器一次。6/6 同时满足 QA 有效和轨迹有效，且重新产生的完整验证结果与前轮保存结果的规范字节一致。

| 项目 | 每次完整构建的数量 | 解释 |
| --- | ---: | --- |
| 冻结输入轨迹 | 6 | 每任务 B/A/C |
| 新候选声明 | 0 | 不扩展来源族 |
| 新候选 Runtime 执行 | 0 | 不调用 run_candidate |
| 原历史 Action | 40 | `2 × (8 + 4 + 8)`，原字节保留 |
| 原历史 Final | 6 | 原字节保留 |
| 只读验证器调用 | 6 | 各实际轨迹一次 |
| own-route Oracle 重放节点 | 40 | 候选自身验证工作 |
| 答案 Oracle 重放节点 | 48 | 六次冻结八节点答案合同验证 |
| 投影/比较 Operation executor 或 Oracle 调用 | 0 | 读取并比较已保存记录 |
| 同任务无序配对 | 6 | 每任务 B–C/B–A/A–C |
| 跨任务配对 | 0 | 不混合条件任务域 |
| Provider / API 凭证读取 / GPU | 0 / 0 / 0 | 当前阶段没有模型或资源实验 |

上述 Oracle 重放是验证工作，不能归属于候选实际行为。若为了重建一致性再次执行本轮完整构建，其相同的六次只读验证和比较应按再构建成本记录，不作为另一组六条独立采样候选。

| Gate | 要求 | 结果 |
| --- | --- | --- |
| G0 | 确切冻结的 own-qualified 输入域及 primary/control 身份 | PASS |
| G1 | 具有来源与实际状态效果依据的完整公开语义投影 | PASS |
| G2 | 六份可检查的有限对应、关系一致性与直接控制 | PASS |
| G3 | 无新执行及科学解释范围隔离 | PASS |

本轮 Gate 没有要求类数大于一。若完整公开行为缺乏解释，本轮设计要求保留 UNKNOWN；本次 16 个实例和六个配对均已闭合，因此实际 Gate 没有 UNKNOWN。

## 10. 工件身份、重建与结果边界

本轮正式工件的核心身份如下：

```text
measurement_contract:
qa_reasoning_finite_comparison_measurement_contract:e74bae34870ea80d4d23d76b78201f8a8397cc33dcd259c7fee53648353eb59d

rule_freeze_receipt:
qa_reasoning_finite_comparison_rule_freeze_receipt:8e9e417db3573e01cd29434847e3bb94b8ed7e053a9c71bb297455c009e95dca

report:
qa_reasoning_finite_comparison_report:3a6b0ea8b84908dc1c17954ceed4e12d1f5ce3c9bc6f2ac2fce3d68202793457

decision:
qa_reasoning_finite_comparison_decision:7b667025d0eec25b6fcc3fa31c2f335d697a7bc4c5e8746d5f68b8a6f58acbc6

transition:
qa_reasoning_finite_comparison_transition:7a6d325dd1721358deaa72d7f64799dc52fdacb516a8a9e446360b1bde15ddc4

manifest:
qa_reasoning_finite_comparison_manifest:3e612e9d6937ff6169ce9a88f284ef55cb9a8e3c81d91dcecad56ce170dce047

artifact_root:
qa_reasoning_finite_comparison_root:ef93a3154167c8c739d557066e49078e5b6564c7ece8f3afa0fa8a3cbc00ec00
```

Manifest 自身不在成员集合中：26 个成员合计 8,380,170 bytes；Manifest 为 4,042 bytes；全目录共 27 个文件、8,384,212 bytes。较大的字节量包含六张归约前后图、实际状态/来源 witness、完整双射证书及局部控制证据，没有增加候选域。

运行入口为 `trusted_synthesis.experiments.qa_reasoning_finite_comparison.preflight`，需显式传入仓库、外部审阅文本、本轮源码 Commit/Tree 和一个尚不存在的输出目录。实现先核对源码和输入，再冻结规则，随后执行只读验证、投影、六个配对、局部控制和 Manifest。正式输入与既有输出目录不作为覆盖目标。下列命令从仓库根目录运行，外部审阅文本读取正式工件内保存的副本，不依赖会话附件路径。

```bash
PYTHONPATH=trusted_data_synthesis/src python -m \
  trusted_synthesis.experiments.qa_reasoning_finite_comparison.preflight \
  --repo-root /data1/zhuxinrui/projects/Data-Synthesis \
  --external-audit trusted_data_synthesis/artifacts/qa_reasoning_finite_comparison/finance_qa_vnext_finite_own_qualified_candidate_semantic_equivalence_comparison_v1_20260905/external_review.txt \
  --source-commit b1e43da622c7fc10823c3d40d02d9b6445fdfe38 \
  --source-tree b33869265ee66faa25b997c1029bae8f6f7115c9 \
  --output-dir /tmp/qa_finite_comparison_reproduction_unique
```

示例输出路径必须在运行前确认尚不存在；此命令是重新生成测量工件，不生成或执行候选。

正式目录与首次在独立 Python 进程、空输出目录中完成的完整构建逐路径、逐文件实际字节相同：27 个文件、8,384,212 bytes，以及上列全部 Manifest/Root/规则/报告/决策身份均一致。另行使用 `diff -rq` 对两目录核对也未产生差异。这是同一冻结输入和规则的可复现性结果，没有增加候选或语义见证。

新增测试文件为 [test_qa_reasoning_finite_comparison.py](../tests/test_qa_reasoning_finite_comparison.py)，focused 运行 **18 passed，14.53 秒**。覆盖实际输入冻结、规则先持久化、16 个透明实例及额外状态效果保护、六个配对与分区、22 项局部控制、精确数值、独立证书复核、禁止旧 Runtime/builder/executor 调用、未知输入和未闭合流水线的 Gate 行为等。独立证书测试直接核验六组 40 个节点和 127 条边，不调用比较器的对应 helper；未定流水线控制确认 G1/G2 保持 UNKNOWN，不被补偿成完成。

```bash
PYTHONPATH=trusted_data_synthesis/src python -m pytest -q \
  trusted_data_synthesis/tests/test_qa_reasoning_finite_comparison.py
```

本轮新实现的 PyCompile、7 个源码成员的 `mypy --follow-imports=skip`，以及 7 个源码成员加新增测试共 8 个文件的 Ruff check/format 检查均通过。全 `src + tests` Ruff 检查仍有一处既有 `I001`，位于 `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution_models.py:2`；本轮未修改该历史文件，因此没有声称整个仓库 Ruff 零错误。

本轮没有执行会重跑旧 builder 或旧候选 Runtime 的相邻可构造性测试。新增测试和正式再构建运行的是当前测量流程；其中的只读验证重复成本与新增候选执行严格分开计数。

已完成的科学对象是“固定六条实际 own-qualified 轨迹的完整公开行为有限比较”。当前主要候选域每任务只有一个保留语义类，属于可收口的局部负结果。依据本轮实际 `transition.json`，停止沿 lookup 删除、同一来源直接引用、纯标签和独立调度这些已经比较闭合的轴机械扩样。

没有由此推断模型偏好、类间概率、训练价值或更广泛候选语言的唯一性，也没有启动下一阶段、恢复旧主链或修改 QA release/VTDO/生产数据。未来若开展新的行为来源或模型实验，需要明确新的问题和范围；本轮结果本身没有包含这些尚未实施的工作。
