# 八任务开发面板：纠正历史感知的有限商测量

阶段：`finance_qa_vnext_panel_correction_aware_finite_quotient_measurement_only`。本轮根据已通过限定审计的八任务面板继续，仅扩展测量规则，不重开生成、资格、监督表示或 Student 训练。

## 1. 对象、边界与冻结

输入为已发布提交 `d64357ec850a98f31c6fe58013a0ad33b77d87f7` 中的 `qa_vnext_task_panel/fixed_eight_task_panel_v1_20260906`。该目录有 2,771 个文件、196,734,857 字节。新源码位于独立的 `finance_qa_vnext_panel_quotient` 包，所有 888 个前驱 Python 文件保持原字节。

原模型条件 ID 为 `qa_vnext_model_execution_task_panel_condition:eef6edd96efb988b605a80108e9331e31d6e6e7c78624bb6bb8d6d2818568355`。新增 `panel_quotient_condition` 是测量条件，不是新的教师生成条件。它绑定原 16 个登记、会话、资格 ID、有效集合、来源 Git blob、原报告、解释规则及测量实现提交。

本轮审计附件 SHA-256：`b3e216d6f125c72b5dc820da7aeb49fde03ef41030af4304c3831ee4322b7da1`，25,350 字节。它建议对已经观察过的纠正过程实例化有限规则。因此，即使在正式物化前冻结实现，也不能将本轮描述成数据盲确认。

固定历史数量：

| 对象 | 数量及处理 |
| --- | --- |
| 登记会话 | 16，八任务各 2，不替换失败 |
| 原始提交 | 152，全部保留 |
| Qualified | 15，直接复用已接受资格，不重新判定 |
| 有效会话原始提交 | 120＝113 准入＋7 未准入 |
| 已支持投影 | 12，基底语义原样复用 |
| 新解释会话 | D01、B01、S02 |
| S01 | 32 次提交，仍是已知失败，无有效 Assignment |
| 原正向候选及 Token 记录 | 各 113，全部原字节引用 |
| 原完整监督包 | 15；另有原 S01 非完整包记录，不能称为第 16 个完整包 |
| 新 Provider / 模型会话 / Runtime / Operation | 全部 0 |
| 重新资格验证 / Token 化 / Student forward、更新 / GPU | 全部 0 |

此前七个历史工件前缀共 12,947 个文件、647,963,136 字节。准备与测量末尾核对原字节；这只是保存性检查，不重跑旧能力验证、来源扫描或实验。原报告 D/B/S 的 `π=null` 和三个旧 `projection_supported=false` 保持不变，它们是当时规则域下正确的测量结果。

## 2. 三层对象与一般规则

原始完整交互 → 带来源的逐事件解释 → 任务相关行为投影。

原始层保存请求、响应引用、反馈、State、计数和预算；解释层为七条未准入提交分别绑定原事件摘要、原解析值、前后完整 State、最近准入后继、条件证明和处置。投影才决定哪些差异区分类别。没有执行 `ledger=[]`，没有修改旧支持标志，没有重写响应或把被拒提案当作成功执行。

新投影的 `nodes` 和 `final` 直接复制原 `finite_projection`，追加 `retained_interactions`。实际操作、输入角色、参数、Evidence、Claim 生产者、判断依据、Observation/Update disposition、真实消费边、非 Final 祖先中的实际操作都继续存在。引用 ID 只用于定位；关系判断仍使用原精确带标签 DAG 同构及可检查的对应映射，不用“图哈希相同”替代等价证明。

“无效果”在这里仅指保存的公共执行状态没有新增语义效果。每个被拒事件必须：

- 没有 execution、observation、claim 或额外效果记录；
- 除 State ID、最后反馈和提交计数外，前后 State 完整相等；计数恰增加 1；
- 拒绝后的 State 与下一请求的 State 完整衔接；
- Context、公开候选、Final Claim 列表及 Action/Update 合同在区间内不变；
- 使用最近的准入事件作为后继，不能跨过任何已准入 Action 或 Update。

这些条件不声称反馈没有影响后续生成、成本或成功率。预算和反馈仍留在解释账本，不因在类别投影中归约而消失。

## 3. D01：同一既有答案 Claim 的 Final 表示对齐

T7 被拒，最近准入后继是 T8 Final。两者答案 Claim 相同，citation 集合相同，值字符串均为 `125`。T7 的额外 `currency=USD` 和 `unit=million USD` 来自已公开 `answer_schema.result_context`，并非该答案 Claim 的输出字段。T8 是公开合同要求的 `{value:"125"}`。

归约必须同时检查：同一既有答案 Claim、原支持 lineage、相同结果核心、额外字段逐项等于公开 result_context、答案 schema 禁止额外结果字段，以及上述无效果区间。不能把两个数值恰好相同的不同 Claim 或不同支持当成一次表示修正。

解释处置为 `same_claim_public_final_alignment`，该修正不单独区分类别；原 T7 事件、拒绝反馈和计数变化仍保留。D01/D02 是否同类另由完整实际图比较决定。

## 4. B01：同一 growth Action 的既有 Evidence basis 补足

T5 被拒，最近准入后继是 T6 growth。拒绝前后均只有两个已接受 lookup Claim，无中间执行。实际 operation、按角色排列的 inputs、parameters、所选公开候选、目标及判断不变；差别是空 Evidence basis 补齐为所选候选已经公开的精确 basis。

实现要求左 Evidence basis 是右集合的真子集，右 basis 完整等于公开 offer；除 State ID、登记候选集合顺序以及这一个补足字段外，提交必须一致，反馈指出的违例字段必须恰为 `/decision/basis`。换用实际输入、所选支持、Claim、目标或其他判断字段均不能走该归约。

解释处置为 `same_action_public_basis_completion`。它不是把不同操作看成相同答案，也不是假定所有 branch 会话等价；B01/B02 仍需实际依赖图的对应证明。

## 5. S02：保留提案、反馈、sum 与后续披露总额 ratio 的关系

T1–T2 提交的是被拒 `share_ratio` 提案；最近实际准入的是 T3 `relation_sum`，T4 Update 接受其 total Claim。T5 才实际执行披露总额 ratio，T6 接受 ratio Claim，T7 执行 percent，T8 接受 percent Claim。

这一段不适用 B01 的直接同动作修正。新投影保留：

- 当时公开候选、已接受信息与不确定性；
- 实际 ratio 提案的操作、输入、参数、所选候选和公开判断；
- 拒绝的公开规则与违例字段、无执行的反馈关系；
- 最近实际 sum 生产者、明确 accept Update 及 total Claim；
- 后续实际 ratio 生产者、其真实输入，以及上述可观察顺序；
- total Claim 的实际输入/判断消费者及是否为 Final 答案。

`observed_order` 是交互中已发生的先后关系，不是新添的数据依赖或模型动机。仅保留两个无依赖节点还不足以表达这段关系，因此额外的顺序链接属于保留语义。sum 节点不会因为未进入 Final 祖先图而删除；ratio 分母仍是披露总额 Evidence，不会伪称消费了 total Claim。

T1 和 T2 在去除 State 等原始标识后，提案和相关公开信息、反馈关系相同。它们在原始账本仍是两条；在保留的行为关系中仅折叠连续相同提案的重复次数。若提案目标或判断确实改变，则保留变化顺序。接口错误数本身不是新增解决策略类的依据。

T9–T11 的 Final 提交另行处理，最近准入后继均为 T12，围绕同一个已接受 percent Claim，无中间执行：

| 提交 | value 字符串 | 其他表示差异 |
| --- | --- | --- |
| T9 | 既有 Claim 的完整精度 | 附加既有结果元数据；多引用公开 relation Evidence |
| T10 | `93.508458` | 附加既有元数据；多引用 relation Evidence 和既有 Claims |
| T11 | 既有 Claim 的完整精度 | 附加既有元数据与 lineage；citation 已为答案 lineage |
| T12 | `93.508458` | 合同要求的 value/unit 与精确答案 lineage |

完整精度值为 `93.508458258836473662494842525099711181405583826159`，与六位值不是相等字符串。可归约的依据是同一既有 Claim 和公开 `final_quantum=0.000001`、`ROUND_HALF_EVEN`，不是数值容忍度。这里只对已保存值做 Decimal 表示投影，不运行 Finance Operation 或 Final 验证器。被拒值必须是原 Claim 的精确字符串或该显式量化字符串；任意相近值不接受。

额外元数据逐项等于原 Claim 输出；citation 至少保留完整答案 lineage，多出的引用仅限当时已公开 Evidence 或已接受 Claim，不能替换实际答案支持。若任一条件不能证明，则保留 `undetermined`，不为凑齐十五个 Assignment 改规则。

## 6. 比较、正式 Assignment 与三种分母

七任务有两个有效观察，S 仅有 S02。完整同任务配对数为 7，不补采 S。F/C/G/A/R 五个既有配对在验证十二个干净投影基底不变、原审计父对象及旧对应映射仍精确成立后复用，不再搜索；主要新增 D、B 两次同构搜索。

Assignment 同时绑定 Task/Context/协议/registry、原生成条件、新测量条件和规则、登记、原资格、实际会话与图、新投影和比较证明。类 ID 是有限来源绑定的引用，不是全域“所有可能轨迹”的通用类 ID。只有一个有效观察也可获得当前观察支持中的局部类身份。

每任务登记分母保持 `n_i=2`，有效数为 `m_i`，登记任务边际 `μ_i=1/8`：

- 成功比例 `q_i=m_i/2`，总体 `q_panel=15/16`；
- 联合出现频率 `u_i(z)=n_i,z/2`，完整映射时总和等于 `q_i`；
- 有效条件频率 `π_i(z|Y=1)=n_i,z/m_i`。

若仍有未映射有效样本，输出映射质量和未映射质量，并使完整 `π_i=null`；不能删除有效样本后重归一。S 的 `π=1/1`（若投影完成）绝不替换其 `q=1/2` 或 `u=1/2`。每任务类集合互相分离，八任务各一类不能拼成一个任务八类。

## 7. 直接控制与实现检查

正式测量内一次输出四类隔离控制：十二条基底及旧五对兼容；伪无效果/换支持纠正不能归约；删除 S02 的真实 sum 或换成 Claim 分母必须区别；S01 晋升、删有效样本或缩减分母必须拒绝。对未映射有效样本另检查完整条件分布保持 null。

控制用已加载对象的副本或构造记录，不是新模型样本，不产生正式有效轨迹。组件测试也不运行旧资格、Runtime、Operation、Token 化或 Provider。没有在正式测量之后再设置一次相同内容的独立审计阶段。

实现开发中曾捕获一个读取形状错误：Share 的 `context.evidence` 是角色映射，初版按列表迭代导致两个投影测试失败；修正为 `.values()` 后对应 11 项测试全部通过。这是新测量实现的开发缺陷，不是旧 S02 资格或答案的失败。另补强了保留关系的显式顺序绑定，避免仅有无依赖节点无法表达实际 sum/Claim 先后。

## 8. 可复现入口与正式结果

在项目根目录，使用已有环境，先提交/冻结源码，再执行：

```bash
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_panel_quotient prepare
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_panel_quotient run
```

新工件位于 `artifacts/qa_vnext_panel_quotient/correction_aware_v1_20260907`。`preparation/` 保存规则、条件、实现快照、原来源与表示引用、历史清单和零执行 guards；`measurement/` 保存十六个独立投影 sidecar、七个比较、Assignment、类引用、分布、四类控制及报告。成功封存后的再次入口只核对封存和源码后读回结果，不产生第二次正式测量。部分未封存目录不覆盖、不悄然重建。

正式物化结果将在执行完成后补入本节；冻结设计时不预填成功、等价或闭合结论。

## 9. 允许结论与下一步边界

只有十五条有效轨迹全部完成投影和所需比较，才称这批固定面板的商测量闭合。无论是否闭合，15/16 的历史成功率和 S01 失败都不变。

若八个任务的当前观察支持均是单点，当前类内没有跨类概率重分配自由度；这不是 VTDO 干预实验，也不是“每个任务全域只有一种行为”的证据。下一研究对象应是另行明确探索条件下的真实任务相关其他有效支持，而不是回头补 S01 到 16/16。罕见性、错误次数、无用操作或长度不自动构成正 Contribution。

本轮没有训练权重物化、受益模型、独立效用评价或 Student 更新。当前来源多次用于开发，即使文件名含 `test.json` 也不是盲测；一般化和学习收益需要另行固定的评价对象。旧主线仍暂停。
