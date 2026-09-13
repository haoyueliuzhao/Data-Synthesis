# Experiment 0.1：Probe 行为覆盖实验

日期：2026-09-13。独立分支：codex/probe-coverage-20260913。承接Phase0提交5f7e102c955ecb4a2fa2f63fc8e16238f004a4d3。

## 1. 定位

本轮按最新审计进入“训练支持恢复”的前置Probe覆盖实验，不进行Student、VTDO、Hierarchical Loss训练，也不修改任何Loss、alpha或训练超参数。

Phase0已证明：原24,640条采集中，已认证movement在完整mapper和tokenizer之前即为0；原410项参考脚本可以通过工具/评价器，但不能证明真实Probe能形成同样支持。本实验用新的真实返回检验这一缺口。

本轮只改变公开生成SYSTEM协议。原任务、事实、来源、公共问句、实际期间、私有参考、有限财务判据和旧完整事件mapper均不变。不把requested guidance作为actual method；不把参考脚本作为真实Probe；不按金额相等放宽来源绑定；不重写模型返回或删除失败轨迹。

本实验使用原有限mapper，不宣称已验证独立anchored-VTDO状态目录或VTDO理论全部假设。即使发现正例，也不自动获得原共同A/B、每stratum 8+2和180–200任务总体的训练准入。

## 2. 事前固定设计

以下维度由代理在用户“继续Probe覆盖实验”及现有API资源授权下事前选择和登记，不是把过去的某项子额度自动继承，也不是声称用户逐项指定了这些数值。

| 项目 | 固定设计 |
| --- | --- |
| 总候选目录 | 原255任务，保持原父manifest |
| Probe任务 | 12个dual任务；不形成新训练总体 |
| 分层 | annual_flow、stock_rollforward、company_defined_metric × difference、relative_change |
| 每层选择 | 按TaskID排序，取前2个不同source_cluster；不使用旧资格或成功率 |
| 协议 | P0_original、P1_delivery、P2_method_delivery |
| 指导 | endpoint、movement |
| 每task/profile/guidance | 2个rollout |
| 总登记 | 12×3×2×2＝144个rollout |
| 执行顺序 | 完整矩阵预先打乱，固定顺序seed＝20260913 |
| 并发 | 12个生成线程；4个CPU评价进程 |
| 每rollout | 最多32响应／32工具；首次Final立即终止 |
| 最大请求数 | 4,608；无HTTP重试、无轨迹补抽 |
| 新用途Token子额 | 40,000,000，计入原1,000,000,000共同总账 |
| 单请求保守租约 | 99,328输入＋16,384输出＝115,712 Token |
| 序列可消费性检查 | 原本地Qwen2.5-7B-Instruct tokenizer，24,576上限，不截断 |

顺序seed不是模型生成seed；请求不设置温度、top_p或生成seed。每cell仅2次采样，不足以精确估计总体生成概率。报告使用完整注册分母下的描述性频数与覆盖，不做显著性检验或按结果选择“主协议”。

4,000万子额不保证所有144个rollout都能用满32响应：所有请求仍逐个保守预留并结算。若子额或共同上限阻断，则停止后续请求，保留全部144登记及未请求状态，不能补抽或拿成功前缀冒充完整总体。

### 2.1 三个协议

- P0：保留原SYSTEM＋原guidance的逐字节内容，作为同批、同模型的新鲜对照，不仅复用历史分数。
- P1：增加来源引用和交付要求。财务数值必须先经read_source，再用真实result_id计算；不能把证据复制成裸数；Final必须引用已执行的最终结果。只增加公开通用JSON示例和单位／期间提醒，不提供目标答案或正确来源ID列表。
- P2：在P1上进一步明确请求路线。movement指导下要求主动从披露组件、滚动变化或公司定义重建目标，并使Final依赖该链；endpoint指导也有对应端点路线说明。实际标签仍由原评价器从执行支持证明得到，允许模型不遵循指导但被按其真实方法计数。

P1与P2是组合协议，不把观察到的差异拆称为已识别的单一心理机制。两者均未改变工具实现，也没有提供来源索引之外的新事实或资格反馈。

### 2.2 模型与HTTP合同

所有协议固定deepseek-flash，thinking enabled、reasoning_effort high、JSON object、max_tokens 16,384、非流式；不切换模型、不回退。准备阶段对官方/models做了1次只读GET，返回Flash和V4 Pro；保留解析ID和响应SHA，不把该查询算作Probe生成。

官方当前文档列出Flash账号级并发上限2,500；本次冻结12，不调整旧批次。并发是账号级共用，不代表独占配额。[官方并发说明](https://api-docs.deepseek.com/quick_start/rate_limit/)

JSON模式可能返回空内容。本轮不通过自动重试隐藏它；分别记录是否字符串、是否非空、字节数、finish_reason和usage。[JSON输出说明](https://api-docs.deepseek.com/guides/json_mode/)，[模型列表接口](https://api-docs.deepseek.com/api/list-models/)

保留原序列化输入上限98,304 UTF-8字节和额外1,024输入预留，公开内容上限65,536字节，HTTP响应上限2 MiB，180秒总超时／30秒连接超时，无重试或重定向。字节界是保守输入准入界，不冒称精确DeepSeek tokenizer计数。

## 3. 原总账保护

准备时原共同保守扣账为381,449,247，剩余618,550,753：

- 原prior_debits：221,538；
- 既有题面增量改写：10,819；
- 原Teacher已知结算：379,523,523；
- 原9笔网络usage_unknown仍全额保留：1,041,408；
- 评测题面改写：651,959。

真实运行在同一个既有SQLite账本增加独立Probe表与第四用途SQL守卫，不新建可用于真实请求的钱包，不重新扣prior，也不回收未知费用。旧表行和旧trigger SQL在前后做逻辑SHA核对。SQLite文件物理字节因新增用途会变化，不声称它不变。

先在临时副本上验证真实旧schema的迁移和模拟结算；该副本绝不连接模型，也不作为真实预算来源。新增真实用途只在全部输入、源码、CPU测试及已提交的预登记检查之后注册。

四用途扣账在同一事务中计入共同上限，旧客户端插入也受新总额守卫约束。旧报告是历史快照；新总额应以四用途读取器为准。已知费用只释放未使用租约；未知费用保留全额。HTTP200计费未知、模型不匹配或预算突破会停止；已在途请求仍须结算。普通网络或公开内容失败终止该rollout，不重试。

## 4. 真实性、资格与诊断

每个真实返回保留确切公开请求体、上下文、响应模型、usage、公开内容及收据，核对注册身份、请求SHA、实际返回与账本结算。callback的live_teacher_callback字面值不是真实性证据。模型私有reasoning文本不保存，不作为参考或训练目标；完整wire只保留SHA，不声称可由公开投影还原。

离线阶段先完整重放新运行时，再调用原catalog_bridge.assessment.assess_replayed_session。原financial／support／actual_method／full_mapping结果均保留。未更改私有证书、别名规则或mapper来提高接受率。

结构诊断另外分析：

1. 是否执行过可唯一定位的movement-exclusive组件读取；
2. 该读取是否进入首次Final的语法引用闭包；
3. 原评价器是否认证movement金融支持；
4. 完整映射、真实性与CPU token可消费性是否成立。

结构信号不是有效代数支持，更不是财务资格。来源空匹配不等于金额错误，不能排除未识别组件意图。参考脚本不能替代真实覆盖。

所有真实完整、可信、financial valid且MAPPED的rollout，在完整登记采样结束后统一检查CPU表示；失败整包保留，不截断或替换。只保存紧凑的可重现表示诊断，原始公开响应及历史仍在会话记录中；不导出A/B训练包或设置train／heldout身份。

## 5. 指标与准入

按task/profile/guidance、family/quantity/profile/guidance及profile汇总，均保留注册分母：

- actual method分布及UNDETERMINED／NOT_REQUESTED；
- financial movement数量；
- authentic＋financial＋MAPPED movement数量；
- 完整包再通过CPU可消费性检查的movement数量；
- 两种方法是否在同task/profile中均出现；
- 旧fine class观测覆盖，以及组件侧读、Final引用、来源未绑定、输送/内容失败等诊断。

Financial valid、完整轨迹资格和token可消费性是分开的门。发现某task的单个movement正例只是存在性证据，不能直接称“训练材料已就绪”。即使每dual组都有正例，本轮12任务、无原A/B池、每cell 2次也不满足原训练总体与8+2规则。

主三臂、VTDO和HierLoss保持暂停。后续需先恢复合格多状态材料，再事前冻结固定分布训练价值比较；本轮不据Probe结果启动训练或调整Loss。

## 6. 冻结与证据

预登记在首个真实请求前完成Git提交。执行入口核对冻结记录、源码/测试SHA、提交中的相同文件、原代码依赖、完整固定任务集合、来源父manifest及私有bundle身份、原钱包快照。

原main、anchored、HierLoss和Phase0分支的源码/配置/测试/文档保持原样。只有共同运行账本按本轮授权追加新用途；既有科学归档和原资格不修改。

最终记录位于artifacts/qa_vnext_probe_coverage/probe_20260913/：

- freeze／registry／policy／selected_tasks：事前注册；
- scripted_preflight／CPU测试／真实schema副本控制：工程准入，非真实Probe；
- requests和sessions：实际请求与公开返回、离线资格；
- coverage_metrics／token_diagnostics：完整分母与可消费性；
- report／请求账本投影／预算finalization：运行状态、实际费用与关闭边界；
- artifact_manifest与无损raw_evidence.tar.gz：原JSON逐字节哈希及紧凑发布。

原始requests／sessions等大量未压缩文件保留本地并忽略；Git只发布明确清单和无损压缩证据，不提交运行SQLite、锁或.env。部分事前小型证据已随预登记直接提交，后续封存不会删除它们；其中非direct成员也进入完整压缩包，属于有意保留的重复证据。若预算/合同提前停止，未请求项明确保留，不能发布为完整成功实验。

真实结果将在固定批次结束后追加；事前设计不会按采样成功率改写。

## 7. 实际执行与总体结果（批次关闭后追加）

本节及以后均为事后结果；不改变第2节的固定设计、模型、样本顺序或资格规则。

结论是：**真实Probe的多方法轨迹存在性得到局部支持，但完整训练材料仍未准入。**
本批P2产生17条原财务规则认证的movement，其中13条通过完整映射、真实请求链和
原CPU表示检查。它们覆盖8个任务、4个family×quantity分层。company_defined_metric
两个分层仍没有完整可消费的movement；本批没有建立共同A/B、train/heldout或8+2材料。

预登记提交为`7c2c921aecf0fc7bec19e298aa9ff3af34665151`，在首个真实请求前已推送。
启动记录时间为2026-09-13 11:22:01 UTC（北京时间19:22:01），报告关闭时间为
11:25:46 UTC（北京时间19:25:46）。运行计时226.56秒，包括启动前检查、生成与离线
收尾；不能把它解释为单请求延迟或纯模型推理时间。

| 执行项 | 实际值 |
| --- | ---: |
| 注册／记录rollout | 144／144 |
| 未请求／补抽／HTTP重试 | 0／0／0 |
| 新Probe请求 | 758 |
| 每rollout请求数最小／最大 | 2／14 |
| HTTP 200且模型名deepseek-flash | 758 |
| 非空公开响应／空公开响应 | 754／4 |
| 首次Final／公开内容合同失败终态 | 140／4 |
| quantity PASS | 127 |
| 原financial valid | 92 |
| actual endpoint／movement／UNDETERMINED | 75／17／52 |
| 真实完整MAPPED endpoint／movement | 60／13 |
| CPU可消费完整包 | 73／73 |
| CPU原始响应表示检查 | 344／344 |
| Student运行／权重加载／GPU操作 | 0／0／0 |

每个计数均来自完整144项注册表。UNDETERMINED保留在分母中，不重新标为指导方法；
四个空响应终态也未删除。73个包是Probe可消费性诊断，不是73个正式训练样本。

### 7.1 按公开协议比较

表中“完整E/M”指真实性、financial valid、旧完整mapper及CPU可消费性全部通过；
E为endpoint，M为movement，U为UNDETERMINED。

| 协议 | 注册 | 首次Final | actual E/M/U | 财务有效 | 完整E/M | 组件读取进入Final闭包 |
| --- | ---: | ---: | --- | ---: | --- | ---: |
| P0_original | 48 | 44 | 24/0/24 | 24 | 14/0 | 0 |
| P1_delivery | 48 | 48 | 34/0/14 | 34 | 31/0 | 0 |
| P2_method_delivery | 48 | 48 | 17/17/14 | 34 | 15/13 | 24 |
| 合计 | 144 | 140 | 75/17/52 | 92 | 60/13 | 24 |

P1增加交付和引用要求后，本批财务有效数与完整endpoint数高于P0，但没有观察到
movement-exclusive组件读取或有效movement。P2的movement指导下24条轨迹均执行了
至少一个唯一定位的movement-exclusive读取，且进入首次Final语法闭包；其中17条
具有正确财务支持，13条具有可映射、可消费的完整轨迹。

这些观察支持“公开路线要求能够在本批部分任务上恢复真实movement支持”，而不是
“原模型绝不具备movement能力”。它们没有单独识别某个提示句的因果效果，也没有
证明P2在总体上显著优于其他协议。P1/P2是组合干预，任务只有12个，模型侧未固定
随机seed，同一供应商模型名也不等于已固定不可变权重。

### 7.2 指导条件不等于实际方法

| 协议 | requested guidance | 注册 | actual E/M/U | 完整E/M |
| --- | --- | ---: | --- | --- |
| P0 | endpoint | 24 | 10/0/14 | 6/0 |
| P0 | movement | 24 | 14/0/10 | 8/0 |
| P1 | endpoint | 24 | 17/0/7 | 15/0 |
| P1 | movement | 24 | 17/0/7 | 16/0 |
| P2 | endpoint | 24 | 17/0/7 | 15/0 |
| P2 | movement | 24 | 0/17/7 | 0/13 |

特别是P0/P1的movement指导下，分别有14和17条被认证为endpoint，而不是movement。
因此本次实际标签并未用guidance代填。

在完整注册分母下，财务有效movement频数为17/144＝11.81%，完整可消费movement
为13/144＝9.03%。P2自身对应17/48＝35.42%、13/48＝27.08%；只在P2 movement指导
子集中，对应17/24＝70.83%、13/24＝54.17%。这些是不同明确分母下的**样本比例**，
不是总体生成概率估计；没有按成功结果重选分母、置信区间或显著性检验。

## 8. 分层和任务覆盖

以下表格固定为P2、movement指导，每层2任务×2重复，共4条。

| family | quantity | 注册 | 财务有效M | 完整映射M | CPU可消费M |
| --- | --- | ---: | ---: | ---: | ---: |
| annual_flow | difference | 4 | 4 | 4 | 4 |
| annual_flow | relative_change | 4 | 3 | 2 | 2 |
| stock_rollforward | difference | 4 | 4 | 4 | 4 |
| stock_rollforward | relative_change | 4 | 4 | 3 | 3 |
| company_defined_metric | difference | 4 | 2 | 0 | 0 |
| company_defined_metric | relative_change | 4 | 0 | 0 | 0 |

P2中8/12个task同时具有完整可消费endpoint与movement；P0、P1均为0/12。
P2的8个任务恰好是本批全部annual_flow和stock_rollforward任务。可消费movement覆盖
4/6个分层，不覆盖company_defined_metric。财务有效movement覆盖9/12个任务、5/6
个分层；不能把这个较宽的口径替代完整可消费口径。

| TaskID唯一前缀 | family | quantity | P2财务M | P2完整M | P2完整E |
| --- | --- | --- | ---: | ---: | ---: |
| task_0052499d | annual_flow | difference | 2 | 2 | 2 |
| task_0fcc20ab | annual_flow | difference | 2 | 2 | 2 |
| task_0b8490c5 | annual_flow | relative_change | 1 | 1 | 1 |
| task_0be82011 | annual_flow | relative_change | 2 | 1 | 2 |
| task_0314c117 | stock_rollforward | difference | 2 | 2 | 2 |
| task_0b1fd02e | stock_rollforward | difference | 2 | 2 | 2 |
| task_05c96f11 | stock_rollforward | relative_change | 2 | 2 | 2 |
| task_1172fd15 | stock_rollforward | relative_change | 2 | 1 | 2 |
| task_293e89f1 | company_defined_metric | difference | 0 | 0 | 0 |
| task_43f7f900 | company_defined_metric | difference | 2 | 0 | 0 |
| task_01bd8584 | company_defined_metric | relative_change | 0 | 0 | 0 |
| task_157d29fc | company_defined_metric | relative_change | 0 | 0 | 0 |

完整TaskID、source_cluster和原始bundle身份保存在selected_tasks.json及registry.json。
每task/profile观测到的旧fine class数量之和为P0＝9、P1＝14、P2＝23；这是任务内
已观测类别计数的和，不是跨任务共享状态数量，也不是相对于未知全状态空间的覆盖率。
本轮仍未调用anchored状态目录来认证VTDO状态。

## 9. 恢复后的剩余失败层

### 9.1 已形成组件引用，不等于财务支持有效

P2 movement指导的24条中，7条未通过原财务规则：

- 6条为`assessment.source_not_uniquely_bound_to_fact`，全部属于company_defined_metric；
- 1条annual_flow relative_change为`assessment.program_not_equivalent_to_financial_target`。

六条公司指标失败的注册ordinal为0、11、27、50、56、138。结构诊断中相应issuer表格
cell locator的`fact_ids`为空，属于零候选UNBOUND_SOURCE，而不是已证实的多个候选
冲突。部分其他组件虽唯一定位且进入Final，但不足以补齐整条财务证明。这里不能把
“空绑定”直接解释成金额错误，也不能依据最终数字相等增加别名或放宽资格。

在全144条中，来源绑定失败34条、Final未由所命名结果支持7条、程序不等价7条、
无Final 4条，合计52条财务无效。结构诊断的Final闭包出现UNBOUND_SOURCE为35条；
它与原财务首个失败原因是不同统计口径，不要求逐项相等。

### 9.2 财务有效movement到完整映射仍有4条损失

四条真实性均通过，金融支持也通过；被保留排除的具体理由如下。ordinal从0开始。

| ordinal | family / quantity | 原完整mapper待审理由 |
| ---: | --- | --- |
| 29 | annual_flow / relative_change | non_support_calculation_intent_unresolved |
| 71 | stock_rollforward / relative_change | failed_tool_requires_complete_class_review；format_recovery_complete_class_review；non_support_calculation_intent_unresolved |
| 97 | company_defined_metric / difference | failed_tool_requires_complete_class_review；format_recovery_complete_class_review |
| 104 | company_defined_metric / difference | failed_tool_requires_complete_class_review |

它们的失败工具、格式恢复和未解析侧计算均保留在完整原轨迹中。没有删除错误前缀、
剪成成功后缀，或把financial valid直接提升为MAPPED。

这不推翻Phase0的定位：旧固定数据进入完整mapper前movement已为0；本轮新生成
先恢复17条财务movement后，才实际观察到17→13的完整映射门损失。新批次不能倒写
旧数据的失败层，也不能把这4条待审自动称为mapper错误。

### 9.3 四条公开空响应

P0的ordinal 49、78、81、137在第二次请求（response_index＝1）收到空字符串，
立即进入公开内容合同失败终态，没有HTTP重试或rollout补抽。其可观测事实为：

- HTTP 200，模型名deepseek-flash，finish_reason全部为stop；
- public content是字符串，长度0字节；
- completion_tokens分别为47、48、50、51这一集合，均由usage报告为reasoning tokens；
- 单次总计费Token为2,575、2,625、3,086、3,088这一集合，费用全部结算。

这里只能确认“有计费、无非空公开内容”，不能由reasoning计数推断推理质量，也
不能归因于输出达到16,384上限。私有reasoning文本没有保存或读取为训练证据。

全部758个响应finish_reason均为stop；最大completion为6,024 Token，最大prompt
为7,431 Token，最大公开内容315字节，最大请求体30,220字节；均未触及注册上限。

### 9.4 tokenizer不是本批13条movement的清除层

73个完整候选包全部可消费，共344条原始正向公开响应，17,638个目标Token。
单条表示序列长度范围1,752–7,704，低于24,576上限；原始输入历史完整保留，
没有截断、压缩改写或替代响应。13个movement包无token过滤损失。

这只是可表示性，不是训练收益。没有导出编码数组为训练数据，没有加载Student
权重，不能推断Student会学会同一路线。

## 10. 两条真实公开支持链示例

以下示例在批次结束后，按注册ordinal分别选择两个family中最早的完整可消费
difference movement，仅用于解释；所有统计仍使用全部注册样本。这不是脚本正对照。

### 10.1 annual_flow：AMD毛利变化（ordinal 2）

任务比较2017-12-31至2018-12-29与2018-12-30至2019-12-28两个实际期间。
会话为`probe01_session_3eff4ef5c9dbd7ab51d95e47976028e9950a120a4025b744221a03bbe07d29f4`。
模型实际执行4次read_source，读取两期收入6,475、6,731和营业成本4,028、3,863
（均为million USD）；随后实际执行：

```text
tool:5 = tool:2 - tool:4 = 6,731 - 3,863 = 2,868
tool:6 = tool:1 - tool:3 = 6,475 - 4,028 = 2,447
tool:7 = tool:5 - tool:6 = 421
Final.result_id = tool:7; value = 421.00; unit = million USD
```

收入和成本组件的来源指针、单位转换、执行结果及Final引用全部进入支持证明。
不是把两个直接披露毛利端点相减后贴上movement标签。

### 10.2 stock_rollforward：NIKE现金变化（ordinal 18）

任务比较2023-05-31与2024-05-31期末现金及受限现金。
会话为`probe01_session_b0a703f7a26372a6d65fb094f77044ccb95fa9f7e0b8291b1eafeeff7890d4fa`。
模型实际读取经营7,429、投资894、融资−5,888、汇率影响−16（million USD），然后执行：

```text
tool:5 = tool:1 + tool:2 + tool:3 + tool:4
       = 7,429 + 894 - 5,888 - 16 = 2,419
Final.result_id = tool:5; value = 2419.00; unit = million USD
```

本例Final由真实现金流组件支持，不是由指导标签或单纯答案数值相等赋方法。
两例原始session和qualification均在raw_evidence.tar.gz的对应sessions目录内。

## 11. 费用、工程检查和不可变边界

| 总账项 | Token |
| --- | ---: |
| 本批输入Token | 2,706,366 |
| 本批输出Token | 284,578 |
| 本批已结算扣账 | 2,990,944 |
| 本批未知计费／在途未结算 | 0／0 |
| 共同旧保守扣账 | 381,449,247 |
| 共同新保守扣账 | 384,440,191 |
| 共同剩余额度 | 615,559,809 |
| 本批40,000,000子额未使用 | 37,009,056 |

Probe用途已经关闭；未使用子额不是追加采样许可。旧9笔未知费用1,041,408仍全额
保留在共同扣账中。生成后钱包快照与用途关闭后快照仅相差确切的
`probe01_finalization`标记及相应记录ID，扣账、注册和请求记录不变；该正常关闭标记
位于`persisted_stops`字段，不是新发生的生成合同失败。

准备期130项CPU测试通过；真实运行结束后同一集合再次130/130通过（10.55秒）。
144项脚本对照全部通过，但继续只表示协议/工程支持。新源码、测试和事后复核脚本
Ruff检查通过。

新增`scripts/verify_probe_coverage_20260913.py`是事后只读复核器，不是事前评价器，
也不是另一个独立实现或外部独立审计。它在禁用HTTP Provider的条件下：

- 验证758个请求、公开响应和计费收据，包含4个空响应；
- 从原始公开历史重放144个会话并重新运行未修改的原财务／完整mapper；
- 重建全部73个token包和344条响应表示，逐记录相等；
- 重算整个覆盖汇总，保持144注册顺序、原始身份与指标字节一致；
- 核对旧表行、原trigger SQL及四个受保护工作树，钱包写入和新增HTTP均为0。

复核报告为`postrun_replay_audit:120a7533b963bc79df1cc431442600b67c846c3c14603112caf9892b3eb0026e`。
复核脚本开发时曾将“生成结束”快照误当成“用途关闭”快照逐字节比较，因此在读取
终态标记处拒绝；修正为只允许上述确切finalization增量后，全量复核通过。此处只
修改了事后复核器，未修改实验运行代码、费用、轨迹或资格。格式化前后两次通过的
复核结果只相差复核脚本SHA和派生报告ID；开发记录可恢复保留在本地runtime，不作为
另一个采样批次或额外实验成功。

四个受保护提交为：

- main：`30284a2f139b7981bc96413646459c51b76e57d5`；
- anchored-VTDO：`bab60b79fdcec2742ee5d88b729c1b50ae3d17a6`；
- Hierarchical Loss：`89368f2823f6c9ecc7cd19a053c85334afb83e10`；
- Phase0：`5f7e102c955ecb4a2fa2f63fc8e16238f004a4d3`。

未修改原资格、旧科学归档、A/B材料或任何训练参数。本轮新增用途在原共同SQLite
账本中记账，但SQLite及密钥不进入Git。

## 12. 结论、限制与下一步

当前可以支持的结论：

1. 在本次固定公开协议和原资格规则下，真实Probe能够产生不止endpoint的一类有效轨迹；
   13条完整可消费movement提供存在性证据。
2. 只加强交付要求的P1没有在本批恢复movement；P2观察到组件采用、Final引用和
   有效财务支持。这是有限组合协议的观察结果，不是总体零概率或最优协议证明。
3. 完整支持恢复仍不均衡：company_defined_metric无完整movement，且有效财务
   支持之后仍存在完整轨迹mapper待审门。tokenizer未继续清除本批已完整映射的包。

当前不能支持：总体π(z|x)已准确估计、完整训练支持恢复、共同A/B或8+2通过、
Student能力提升、VTDO优化有效、HierLoss科学验证通过。

后续应先对company_defined_metric的实际cell locator绑定和失败/恢复轨迹做独立
诊断，明确是来源表达、工具调用还是完整轨迹语义缺口；任何新协议都应另行事前
冻结和采样，不回填本批结果、不按数值相等放宽原资格。随后才可能构建多状态
材料并检查全组8+2和共同A/B，再决定固定分布训练价值实验。

本轮终态为`COMPLETE_PROBE_COVERAGE / PARTIAL_MULTIMETHOD_SUPPORT / TRAINING_NOT_ADMITTED`。
主三臂、VTDO和HierLoss真实训练继续暂停；HierLoss仍是实现通过、科学验证等待
数据支持，而不是由本次Probe结果自动转为可训练。

## 13. 主要证据与复核入口

- [预登记freeze](../artifacts/qa_vnext_probe_coverage/probe_20260913/freeze.json)：
  `coverage_freeze:c376cfa35a3d516cd23c531c5c03b9d0d0641e3e2b834ec85ace8b54232d3f5a`。
- [运行报告](../artifacts/qa_vnext_probe_coverage/probe_20260913/report.json)：
  `probe_coverage_report:406f4cb14d6d62e764063a27810a9a679a575c69132101797d5211725abb8247`。
- [全分母覆盖](../artifacts/qa_vnext_probe_coverage/probe_20260913/coverage_metrics.json)：
  `coverage_metrics:f436db9e7e26f72da6745187ea7e463ad2df7ea94a7f0cf73d8029f309b37d7d`。
- [token诊断](../artifacts/qa_vnext_probe_coverage/probe_20260913/token_diagnostics.json)：
  `probe_token_diagnostics:5da82ac6bc738d5f1570f11d997c45022d7446f7e931c8654297e9554e5cca80`。
- [证据Manifest](../artifacts/qa_vnext_probe_coverage/probe_20260913/artifact_manifest.json)与
  [无损原始证据包](../artifacts/qa_vnext_probe_coverage/probe_20260913/raw_evidence.tar.gz)：
  绑定原始JSON/XML逐文件字节、公开请求/响应和资格记录；不含私有reasoning文本或钱包。
- [事后全量复核脚本](../scripts/verify_probe_coverage_20260913.py)：同一冻结实现的零HTTP复算。

在独立Probe工作树中，配置项目Python环境与本地原始父数据后，可执行：

```bash
PYTHONPATH=raw_financial_data_lake:trusted_data_synthesis/src \
  /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/.venv/bin/python \
  trusted_data_synthesis/scripts/verify_probe_coverage_20260913.py \
  --code-root /tmp/data-synthesis-probe-coverage-uPr3h7 \
  --data-root /data1/zhuxinrui/projects/Data-Synthesis
```

该入口不重新生成样本，也不改账本；从Git新检出时需先在对应证据目录恢复压缩包
内的原JSON文件。运行源码及事前测试SHA仍必须与freeze完全一致。

最终封存绑定2,594个原始JSON/XML文件、49,947,159字节，其中2,575个成员进入
6,099,540字节的无损压缩包，19个文件列为direct。预登记已直接跟踪14个小型证据，
其中4个也出现在压缩包；没有删除这些事前文件。解压往返、逐文件哈希与密钥扫描
全部通过，密钥命中0。
Manifest为`probe_artifact_manifest:3d0535646b331b82e81c321fdca18713da1216fd2f767b6822d077a78bbf3e9e`；
压缩包SHA-256为`4438fa3e938be1aaa86f4b3c7f4e75c1a93b1e7d0b6ded038d5664378f2f717b`。
