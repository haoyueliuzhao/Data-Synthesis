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

原始未压缩文件保留本地并忽略；Git只发布明确清单和无损压缩证据，不提交运行SQLite、锁或.env。若预算/合同提前停止，未请求项明确保留，不能发布为完整成功实验。

真实结果将在固定批次结束后追加；事前设计不会按采样成功率改写。
