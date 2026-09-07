# 跨真实来源绑定的双支持机制复用试验

阶段：`finance_qa_vnext_cross_binding_dual_support_transfer_pilot`。本轮依据输入审计的 `PASS_AS_SCOPED`，正式关闭旧 UNP/2015 单题的支持存在性问题，转向同一参数化机制的三个新真实任务实例。

本文前半部分是首次新 Provider 响应之前的冻结设计；正式结果仅在后续结果节填写，不将构造控制算作模型样本。

## 1. 继承结论、唯一新问题和边界

实验历史保存锚点为 `1df42747bedfce1ef874fb2a2f3fb7566513964a`。上一轮三个有效轨迹全部映射、三个同任务配对确定、三个完整行为商类、严格 D/R 支持见证成立；旧成功质量仍为 `3/8`。本轮不重跑其 83 项测试或 22 项控制，不重新解释这三个样本，不重新导出旧 Token，也不执行旧 P/Q 权重预检。

新问题是：在首次新响应前固定测量规则后，披露总额直取与实际重建后消费这两种支持机制，能否通过同一参数化 QA 链路迁移到多个真实主体／期间／来源绑定？

这增加一个任务类型的实例广度，不增加任务类型数量，不代表一般金融能力、自主规划、内部信念修订、Contribution 或 Student 效用。所有任务仍提供公开计划、完整合法候选和独立 Update 合同。旧主线继续暂停。

审计附件全文保存到新准备目录，SHA-256 为 `469fbc90f41bc081db469a1a53ee82e9a2357b637a14b125a58b9352e1082a91`，26,338 字节。旧报告中的计数措辞已更正为“三个错误断言段、两次 L→错误回退、三次错误→L 恢复”；不重建旧正式工件。

## 2. 真实来源与选期

使用已有来源关系见证指向的原 FinQA 冻结数据，而不是生成新数值或扫描原 QA／program／answer 选题。读取完整 JSON 容器仅为寻址；语义访问限于已有指定索引的 `id/filename/table_ori/pre_text/post_text`。

| 新任务 | 原页面记录 | 实际选中期间 | 目标组成项 | 另一组成项 | 独立披露总额 |
| --- | --- | --- | --- | --- | --- |
| T01 | UNP/2016/page_52.pdf-1 | 2016 | Total freight revenues：18,601 | Other revenues：1,340 | Total operating revenues：19,941 |
| T02 | JPM/2014/page_70.pdf-1 | 2014 | Noninterest revenue：50,571 | Net interest income：43,634 | Total net revenue：94,205 |
| T03 | JPM/2015/page_82.pdf-1 | 2015 | Noninterest revenue：50,033 | Net interest income：43,510 | Total net revenue：93,543 |

三表单位均为原表明确标注的 millions，币种只记录为 `dollar_as_disclosed`，不从美元符号推断未在该快照中明确给出的 ISO 币种代码。UNP 依据同页母公司与子公司、内部交易抵销和 freight subtotal 结构；JPM 依据 reported consolidated results 文本和收入分项结构。关系见证是已知开发来源的明确宿主解释，不伪装成未见数据自动发现。

选期规则是：检查实际列头，按年度降序、列索引升序，选择组成项和独立总额完整、同期间合同满足、分母非零的最新年度列。页面路径年份不是期间权威。三页均选中第 1 数值列；来源表、行列位置、原值、精确 JSON pointer、原始行列与上下文哈希保存在 source binding 中。

组成关系依赖原表层次与上下文，不因三数恰好相加而认定；不计算“总额减一项”制造另一项。源绑定阶段不求和或算占比。适配器的实际执行与独立 oracle 在新会话中验证数值。

三个语义实例键排除页面身份，包含主体、合并范围、期间、单位、币种、目标指标和总额指标；均不同。其他报告重复披露的比较列仍登记为事实重叠，不当作额外 Task。旧缺失营业利润的增长差值任务仍缺失，不由新占比任务补齐。

## 3. 新参数化入口

`BoundShareTaskAdapter(source)` 接受已验证的 `BoundShareSource`，不调用旧 `load_share_source`，不替换旧 Share adapter 的隐式数值。公开角色固定为：

- `target_component`：实际目标收入项；
- `other_component`：独立披露的另一组成项；
- `disclosed_total`：独立披露总额；
- `composition_relation`：同主体、期间、单位与范围的完整不重叠组成关系。

银行 Noninterest revenue 不使用虚假的 freight 标签。每个新任务拥有独立 Task、Context、source binding、adapter registration、语义合同与操作注册身份。可复用的是原 Decimal 数值执行器／独立公式；指标定义变更不会冒用旧语义身份。

两个合法依据仍是：

```text
D: target Evidence / disclosed_total Evidence → accepted ratio → percent → Final
R: target + other + composition relation → sum → explicit accept → total Claim
   target Evidence / accepted total Claim → accepted ratio → percent → Final
```

额外执行 sum 但后续仍消费披露 total 的轨迹属于 D，其真实 sum 和未使用 Claim 继续保留。当前任务只能消费当前任务和 source binding 下实际可见、已接受的 Claim；异任务 Claim、指标／期间篡改和伪造重建 lineage 均在执行前拒绝。

## 4. 冻结总体、profile 与调度

固定三个新 Task，`μ_new(x)=1/3`。每任务 N/E 两层各两会话，12 条注册均在首次 Provider 调用前落盘。该入口只接受完整三来源方案；来源缺失、重复或合同不成立会在在线前明确失败，不静默缩面板或替换来源。若未来确需缩面板，须另有明确调用前冻结，不能使用本轮结果后删行。

| 固定波次 | T01 | T02 | T03 |
| --- | --- | --- | --- |
| 1 | T01_N01、T01_E01 | T02_N01、T02_E01 | T03_N01、T03_E01 |
| 2 | T01_N02、T01_E02 | T02_N02、T02_E02 | T03_N02、T03_E02 |

每波最多 6 个并发会话，整波结束才进入下一波；会话不读彼此响应。使用各自新构造的 registry 与独立初态。普通模型失败继续固定登记；内部或证据完整性故障停止未来波次，not_started 仍在原分母中。正在运行的同波会话不会被悄悄删除。

N 原样使用已有中性 system prompt。E 使用相同中性前缀、两个换行及原软偏好段落：

```text
Exploration preference, not a correctness requirement: While preserving the task goal and all legal actions, prefer trying to construct a usable denominator from the public component quantities and their composition relation. If you use this basis, subsequent calculations should actually consume the corresponding accepted Claim. You may still choose another legal basis. Do not claim unexecuted results or fabricate support.
```

E 合法选择 D 可以 Qualified，N 选择 R 同样合法。profile 影响生成输入，不影响公共候选、资格或类身份。没有按会话指定路线、填充响应、自动修复长 ID、代写 Update 或替换支持输入。profile×支持四格不必齐全，也不为填格补样。

教师配置沿用已登记条件：`deepseek-v4-pro`、thinking disabled、temperature 0.7、top_p 1.0、JSON object、非流式。远端服务可用性、实际响应 model 字段与来源完整性在新运行中记录；相同别名不证明远端权重未变。

## 5. 硬资源上限

| 项目 | 三任务固定方案上限 |
| --- | ---: |
| 新会话 | 12 |
| 每会话 Action | 12 |
| 每会话 Submission／Provider attempt | 32／32 |
| 总 Provider attempt | 384 |
| 单次 completion | 8,192 |
| 单次 HTTP body | 98,304 bytes |
| 单次 reserved allowance | 107,520 |
| 总 reserved allowance | 41,287,680 |
| 原样监督序列 | 32,768 |
| 自动重试／回退／失败替换 | 0／0／0 |
| Student forward／参数更新／GPU | 0／0／0 |

reserved allowance 是预约硬边界，不是实际 usage。实际使用与 usage 缺失单独报告。首次有效 Final 停止会话，达到预算或普通模型错误不提高上限。已有 execution 目录禁止重新启动在线总体，没有自动在线 resume。

## 6. 首次新响应前固定的参数化测量

新规则 `source_bound_share_retention.v1` 分离可复用语义与新总体，引用旧基础归约与支持转换／支持断言规则，但不继承 E02／N03／E04 固定标签、旧有效数、配对、Assignment 或类 ID。

基底是每条新 worker 已独立审计并封存的实际图和 Final；不重新执行或重新资格审查。先应用原基础规则，再按同一预注册域解释：

1. 被拒 D 提案之后，最近实际 sum 与独立 accept 产生 total Claim；随后同目标 ratio 的实际分母改为该 Claim。前后输入明确不同，拒绝区间无执行不延伸到后续真实改变；观察顺序不等于因果。
2. 同一已接受答案 Claim 的完整 Final 支持断言段：逐次保存真实 lineage、声明集合、missing／extra、反馈与前后 State。错误支持声明不是实际 uses 边。仅已有数值与元数据投影、已公开引用及既定替换域可解释。
3. 既有已证明保留的其他交互不会因同轨迹另有未定事件而丢失。完整行为继续保留实际操作、输入类型、生产—消费依赖、公开判断与要求保留的纠正过程。

无新结果专用扩域开关。超域事件可以是 Qualified 但 projection undetermined；保留其未映射成功质量，不删困难样本凑完整分布。旧文档和历史规则描述仍表示当时的测量状态。

## 7. 同任务类、严格见证与分布

只比较同 Task／Context／协议／registry／规则下的 Qualified 轨迹。每任务最多 6 个配对，总最多 18；不对十二条轨迹跨任务两两比较。完整精确图对应／差异见证决定类，而非 profile、支持标签、错误次数或哈希。跨任务仅报告 D/R 机制出现情况，D/R 不是跨任务 State ID。

对任务 i：

```text
q_i,N = m_i,N / 2
q_i,E = m_i,E / 2
q_i   = (m_i,N + m_i,E) / 4
u_i(z) = (n_i,N,z + n_i,E,z) / 4
π_i(z | success) = (n_i,N,z + n_i,E,z) / (m_i,N + m_i,E)
```

成功条件下 profile 混合权重按实际成功数量，不默认各半。unknown、not_started、未映射有效质量分开记录；未闭合则完整条件 π 为 null，不对容易映射的子集重新归一化。

`W_i` 仅在该任务有真实 Qualified D 和 R，并有确定完整语义差异及真实 denominator 支持证明时成立。多个商类不等于多个分母机制；W 不是工作流必须通过的条件。面板 q 可按冻结 μ 汇总，不能用某任务成功补偿另一个任务从未执行或绑定失败。

## 8. 原样表示和后续类内物化边界

只导出新 Qualified 会话全部 admitted events 的原响应。保留真实 N/E system prompt、该次完整公共请求、State、反馈、原目标字符串与 HTTP 来源链接；不把 E 目标配到中性请求。失败前缀不拼成成功。

复用同一 tokenizer 资产和 32,768 表示政策，生成新的 data binding、Token 和 session package 身份；CPU 小 batch 上限为 2。超长不截断，包完整性按该会话所有 admitted events，而非 fit 子集判断。资格与表示是否适配是两个独立结果。

每类绑定成员轨迹、profile/config、完整监督包、目标 Token 数和纠正历史投影。它们只是后续固定 Mψ 的材料，不实施训练采样器、旧 P/Q 检查或权重干预。重复复制同一包不增加独立样本。未来类权重变化可能同时改变 profile 与纠正过程组成，不能无条件归因为重建支持的价值。

## 9. 评价隔离与污染登记

三个候选页已被阅读用于来源设计；它们都是机制迁移开发材料，不是新盲评。登记四个已知原表组（含旧 UNP/2015）、十二个 FinQA 别名记录；同页多个 ID 不增独立来源数量。

跨报告重复披露的比较期事实建立重叠边。JPM 两表中部分 noninterest／total 比较数值不同，明确记录差异；没有在此来源快照中确认原因，不推测为某种重述。相同 net interest 等事实仍建立重叠关联，组间不声称统计独立。

未来评价排除所有开发、提示调整和训练来源组、同表别名及传递重叠组；这四页账本不证明整个项目其余来源清洁。未来使用统一中性任务提示，正确性来自原始来源和独立计算，而不是模仿教师轨迹。

当前 `evaluation_readiness=not_ready`、已绑定干净评价任务数为 0。这是明确待实例化对象，不是本次开发采集的阻断 Gate。

## 10. 新局部控制与历史保存

控制集中于四个边界：真实来源与指标角色不可偷换；N/E 不改合法空间或资格；当前任务 Claim 不跨任务消费；新配对、分母与表示不借旧样本。

冻结前的新构造测试可执行新来源 fixture 来验证接线，明确禁止真实 Provider；fixture 不进入正式十二会话分母。表示测试使用可控内存 tokenizer，不重复旧 Token 实验。正式 prepare 的 instrumented guards 则禁止 Provider、Runtime 执行和资格重放；正式分析禁止再资格，所有阶段禁止 Student／GPU。

按前驱 Git blob 验证十个历史工件前缀的 15,908 文件、805,563,921 字节及 918 个旧 Python 文件。旧历史字节必须不变；用户已有 `.codex-worktrees/` 不在本轮修改范围。全部新源码需先提交，prepare 捕获全源码快照，首次调用前回读源、规则、profile、注册、初态请求和表示政策。在线后不因模型结果改源码或提示。

## 11. 执行入口与冻结前验证

冻结前汇总验证已完成：五个新测试文件共 84 项，通过耗时 65.56 秒（来源／adapter 22、计划／runner 16、投影 13、测量 21、表示 12）；Ruff 及按项目配置检查的 14 个新源码文件 mypy 均通过。这不是重跑上一轮的 83 项测试。

新集成测试分别覆盖六会话和完整十二登记的构造 HTTP worker 链路；后者真实接通导出、测试内存编码器、投影与逐任务测量。固定路线只是测试夹具行为，不是正式会话的路线约束；其中的成功、类和见证不进入正式分母。生产 Tokenizer 的本批长度结果尚未产生。

零调用初态检查的每任务 N/E HTTP body 为：T01 47,915／48,345、T02 43,785／44,215、T03 43,818／44,248 bytes。所有重复初态相同；该检查不保证后续任意生成 State 都适配长度上限。历史 15,908 文件及 918 个旧源码也已通过字节回读。

正式入口，在项目根目录使用现有环境：

```bash
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_cross_binding prepare
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_cross_binding run
```

新目录：`artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907`。准备保存审计、来源及污染政策、三个 Task／Context、profile／配置、十二登记、初始 HTTP、规则与比较合同、源码／软件和 Token 资产身份；执行保存原传输与 Runtime 工件、worker 资格、测量、原样表示与 manifest。

上述控制与设计均在首次新 Provider 响应前完成；正式一次性执行及其有界负结果记录如下。没有从构造控制推断模型必然成功，也没有因结果修改预冻结规则或补样。

## 12. 正式执行结果：十二个证据完整的已知失败

源码冻结提交为 `f697d953f749098eaecbd619becef35a61c39f6b`。正式 prepare 成功后只执行了一次 run，十二登记全部按两波原顺序启动；没有重试、回退、替换、补样、来源替换、提示调整或预算上调。源码与测试在首次新响应后保持不变。

本轮结论为：**三个新绑定已进入同一真实模型执行链路，但没有出现 Qualified 完整轨迹；没有获得跨绑定的有效 D/R 支持复用见证。** 这是给定提示、接口、教师服务和小样本预算下的有界负结果，不是“机制不可迁移”的证明。

| 任务 | N：成功／登记 | E：成功／登记 | 任务 q | 实际 Provider attempts | Qualified 类／Assignment／配对 | W_i | 成功条件 π |
| --- | --- | --- | --- | ---: | --- | --- | --- |
| T01：UNP 2016 | 0/2 | 0/2 | 0/4 | 128 | 0／0／0 | false | null |
| T02：JPM 2014 | 0/2 | 0/2 | 0/4 | 128 | 0／0／0 | false | null |
| T03：JPM 2015 | 0/2 | 0/2 | 0/4 | 128 | 0／0／0 | false | null |
| 固定面板 μ=1/3 | 0/6 | 0/6 | 0/12 | 384 | 0／0／0 | 0 个任务建立见证 | 不定义跨任务 pooled π |

十二个资格记录均为：

```text
status                 = known_failure
reason                 = submission_budget_exhausted
qualified              = false
end_to_end_success     = false
qa_valid               = null
evidence_complete      = true
model_origin_verified  = true
provider_attempt_count = runtime_submission_count = 32
```

`qa_valid=null` 表示没有获得被准入的完整 Final，并非把某个已有效 Final 重新判错。没有 unknown 或 not_started；没有 Provider 来源完整性故障导致的未知分母。

新测量 sidecar 的十二条状态均为 `ineligible`。有效的 supported 和 undetermined 都为 0，未映射有效数量为 0。旧通用 qualifier 字段仍可能显示 `projection_status=undetermined`，但这些记录全部不合格；不能据此声称“十二条有效纠正历史又超出了商规则”。

逐任务条件分布状态精确为 `no_qualified_observations`：m=0，因此 π 没有定义。空有效集合上的 `all_observed_qualified_mapped=true` 是空集合逻辑结果，不是新的模型映射成功证据。

质量闭合：

```text
已映射有效 0/12 + 未映射有效 0/12 + 已知失败 12/12 + 缺失结果 0/12 = 1
all_task_joint_frequencies_complete = true
all_task_distributions_complete     = false
```

后一个 false 的原因是成功条件分母为零，不是遗漏成功样本、必要配对未计算或新的事件归约域缺口。正式[逐任务测量](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/execution/analysis/measurement.json)与[总报告](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/execution/report.json)保留完整登记与父身份。

## 13. 实际计算完成与 Final 声明失败必须分开

下表仅描述原始失败轨迹中已发生的 `reached_prefix`，**不是 Qualified 支持，也不进入类或 W 的分母**。A/U 为实际成功执行 Action／accept Update；D/R 只标记 saved ratio 的实际分母是披露 Evidence／本会话已接受的 total Claim。步骤从 1 起。

| 会话 | A/U 准入 | public_judgment 拒绝 | final_qa 拒绝 | current_state 拒绝 | 失败前缀实际分母 | percent Claim accept 步骤 |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| T01_N01 | 3/3 | 3 | 23 | 0 | D | 9 |
| T01_E01 | 2/2 | 0 | 28 | 0 | D | 4 |
| T02_N01 | 3/3 | 1 | 25 | 0 | D | 7 |
| T02_E01 | 3/3 | 0 | 26 | 0 | D | 6 |
| T03_N01 | 2/2 | 0 | 28 | 0 | D | 4 |
| T03_E01 | 3/3 | 0 | 26 | 0 | R | 6 |
| T01_N02 | 3/3 | 0 | 25 | 1 | D | 6 |
| T01_E02 | 3/3 | 4 | 22 | 0 | R | 10 |
| T02_N02 | 2/2 | 0 | 28 | 0 | D | 4 |
| T02_E02 | 3/3 | 1 | 25 | 0 | R | 7 |
| T03_N02 | 3/3 | 0 | 26 | 0 | R | 6 |
| T03_E02 | 3/3 | 0 | 26 | 0 | R | 6 |
| 合计 | 33/33 | 9 | 308 | 1 | D 前缀 7／R 前缀 5 | 12/12 均存在 |

计数守恒为：

```text
384 submissions
  = 33 admitted Action + 33 accept Update + 309 Final submissions
    + 9 unadmitted Action proposals

309 Final submissions
  = 308 rejected at final_qa + 1 rejected earlier at current_state
```

十二会话全部已产生并接受 percent Claim，但最后都没有获得有效 Final。T01_N01、T02_N01、T02_E01、T01_N02 还实际执行并接受了 sum Claim，却在 ratio 中继续消费披露 total；它们不是 R。不能从三次 Action、执行 sum 或 E 组名推断重建支持。

三个任务在失败前缀中都曾实际使用两种输入机制；这个较弱的操作事实与“零条完整有效轨迹”可以同时成立。不得将这些前缀提升为有效样本，或以手动修正 Final 后的离线答案代替真实模型结果。正式[实际进展记录](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/execution/analysis/actual_progress.json)保留前缀深度范围。

## 14. Final 拒绝的原字段对照

以下是运行后对新原始记录的只读描述性统计，不重跑资格、Final verifier、投影或模型，也不构造“如果修正则成功”的替代轨迹。

以全部 309 个 Final 提交为分母：

| 原字段特征 | 数量 | 解释边界 |
| --- | ---: | --- |
| citations 集合精确等于当时答案 Claim 的真实 lineage | 212 | 引用正确不代表整个 Final 合格 |
| citations 与实际 lineage 不等 | 97 | 97 个均有 extra，其中 46 个还存在 missing；无重复 citation |
| result 带额外字段 | 278 | 与下一行可以重叠 |
| result 缺少 value 或 unit | 53 | 不与额外字段计数相加作为互斥分区 |
| value 为完整未量化 Claim 字符串 | 202 | 以下四行是 value 形态的互斥分区 |
| value 为形式上六位小数字符串 | 69 | 仅统计表示形态，不据此断言数值正确 |
| value 为 JSON 数值而非字符串 | 22 | 原数值词法不能用解码浮点的舍入展示代替 |
| result 没有 value | 16 | 202+69+22+16=309 |

若只统计 `admission.final_qa` 的 308 条，需去掉那个更早被 current_state 拒绝的提交：额外字段 277、完整 Claim 字符串 201、引用不等 96；引用精确仍为 212。不能声称该 current_state 提交随后又执行了 Final QA。

代表性原记录：

- **T01_N01 第 10 步**：[原响应](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/execution/sessions/T01_N01/runtime/turns/009_response.txt)的 value 为 `"93.280177"`、unit 为 `"percent"`，引用与实际 lineage 相等，但 result 额外包含 metric、period、subject。第 23 步的[原响应](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/execution/sessions/T01_N01/runtime/turns/022_response.txt)只有 value，缺少 unit。
- **T01_E01 第 18 步**：[原响应](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/execution/sessions/T01_E01/runtime/turns/017_response.txt)虽恰好只有 value/unit 且引用正确，value 实际是未加引号的 JSON 数值 `93.280176520736171706534276114537886765959580763252`，不是六位小数字符串。不能将解析器展示的浮点截短错误归给模型。
- **T03_E01 第 22 步**：[原响应](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/execution/sessions/T03_E01/runtime/turns/021_response.txt)恰好只有 value/unit 且引用正确，但 value 为完整字符串 `"53.486631816383909004415081834022855798937387084015"`，未按 `0.000001` 量化。
- **T03_E01 第 10 步**：[原响应](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/execution/sessions/T03_E01/runtime/turns/009_response.txt)使用六位表示并附额外 metadata，却声明 target+disclosed_total；实际重建 lineage 是 target+other+composition_relation，缺少后两项而多了披露 total。第 14 步[引用已经对齐](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/execution/sessions/T03_E01/runtime/turns/013_response.txt)，但仍有额外结果字段。
- **T01_N02 第 28 步**：[原响应](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/execution/sessions/T01_N02/runtime/turns/027_response.txt)的 State ID 尾部片段为 `...72fec...`，实际当次请求为 `...72ecf...`。所提交 ID 也不等于此前任何请求 State ID，应称 ID 不一致，不能称“复用旧 State”。该次在 current_state 阶段拒绝。
- **T03_N02 第 29 步**：[原响应](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/execution/sessions/T03_N02/runtime/turns/028_response.txt)只有 value/unit、引用正确，但 value 同样为不带引号的完整 JSON 数值。

这些观察把本批失败定位在最终提交的表示合同和支持声明一致性上，而非证明已经发生的加法／除法全部失败。它们没有揭示模型内部动机，也没有证明改某一个提示就能稳定改善结果。采集期间没有因此更改合同、给出补全目标或继续超预算调用。

## 15. 原样表示的实际零结果

新[候选导出](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/execution/analysis/supervision_candidates.json)为空；十二个会话的 export 分别记录不合格原因。真实 N/E 请求仍在原传输与 Runtime 记录中，未为失败响应重新配提示。

| 表示对象 | 本次实际结果 |
| --- | --- |
| 正向候选／Token 记录／fit／not-fit | 0／0／0／0 |
| 新正表示阶段 tokenizer_loaded | false |
| session package 记录 | 12 条，全部 ineligible_known_failure／not_eligible |
| 每个不合格包 | expected_units=null、units=[]、complete=false |
| 完整正向包／CPU batch／实际加载记录 | 0／0／0 |
| 正向表示是否得到本批验证 | false |
| Student forward／权重加载／更新／GPU | 全部 0 |

准备阶段已有 tokenizer 资产身份登记；此处的 false 仅表示新正向行表示阶段没有加载 tokenizer，不声称整个准备进程没有读取资产。零 fit、零 not-fit 不是“所有候选都适配”，也不是长度政策失败：本轮根本没有正向候选。没有将 66 条准入计算／Update 组成失败前缀的正向包，也没有调用 Student。

[包记录](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/execution/analysis/session_packages.json)、[Token 数据集状态](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/execution/analysis/token_representations.json)及[CPU 结果](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/execution/analysis/cpu_loading.json)分别保留资格与表示层边界。

## 16. 实际资源、来源身份与完整性

十二个保存资格记录的响应模型列表均为 `["deepseek-v4-pro"]`。384 次调用均有对应提交和完整来源证据；不据模型别名宣称远端权重快照不可变。

| 项目 | 实际值 |
| --- | ---: |
| Provider attempts／Runtime submissions | 384／384 |
| 最大实际 HTTP body | 53,384 bytes |
| 实际预约 allowance | 41,287,680（达到预冻结上限） |
| Provider prompt_tokens | 5,565,441 |
| Provider completion_tokens | 164,801 |
| Provider total_tokens | 5,730,242 |
| prompt_cache_hit_tokens／miss_tokens | 3,010,176／2,555,265 |
| reasoning_tokens | unknown：384 条均未提供此字段，observed_total=null |
| 重试／回退／替换／新增补样 | 全部 0 |

前五个 usage 数量字段均有 384 条已知记录。reasoning usage 未提供，不能写成 0；配置中 thinking disabled 不补足服务未回报的计数。预约 allowance 不等于实际 Token 消耗。完整[传输统计](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/execution/analysis/transport_metrics.json)逐次保存 usage 与实际请求上界。

主要冻结及结果身份（下表列哈希部分；完整带类型 ID 保存在相应 JSON）：

| 对象 | 哈希 |
| --- | --- |
| 新生成条件 | `8fccc95f4a8f40e9b41f6332043b1cc3f0e9498c1648f830ecd26f518480ce30` |
| 前瞻参数化测量规则 | `922cd2d213677fb9f8d0f1be3695b13e4da0896104ecbe8313aa800c4ecc3a84` |
| 比较合同 | `38a8ed29f3515450a3920248a6b85b175f1824998ec543a8b000589ad608bcf5` |
| 准备 manifest | `88c315661c95b8870ea57309e9042343dc0ce5e23b435e311c953005bb8bddcb` |
| 执行 manifest | `9f6057103efb442e9787d12f6c7f59ddfde557d19d5b746f1f2a66a2a966ae35` |
| 分析 manifest | `0fcc01ab1756348e57af30e3c6e4f2bf7c521c7c43105933edf0cb476c1d4c10` |
| 正式报告 | `67925903b401e608d51540b1528ff189070df673446988298cd5ed6c9312441b` |
| 逐任务测量 | `e9df8324681cd2a6eceb244d4925bbdddb25992485ef577da02a8e9cc9fe707b` |
| 来源报告 | `9f256e8998480d2ad713878c808c5f15b0f4cccb079d44cceff9f54e193a9577` |
| 评价污染登记 | `fbafbefc859b528be24dc85fde11c847e3457842bf82316dc4c68591e82b6aaf` |

新 Task／Context／source binding 独立身份见[冻结条件](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/preparation/condition.json)和[来源报告](../artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907/preparation/source_report.json)。未继承旧类、旧 Token 或旧模型会话 ID。

准备 manifest 覆盖 42 个成员，执行 manifest 覆盖 5,316 个成员，分析 manifest 覆盖 26 个成员（分析成员已包含在执行树中，不能重复相加）。整个新目录连同 manifest 和测试 XML 共 **5,361 个文件、175,306,389 字节**；最大文件为 4,987,747 字节的历史哈希清单。正式封存后只做字节／身份和统计回读，没有重新构建工件。

新执行结束后再次核验十个旧工件前缀的 15,908 文件、805,563,921 字节与 918 个旧 Python，全部与前驱 Git blob 相同；本轮全源码快照共 932 个 Python 文件。三个阶段的 instrumented forbidden-path counters 均为 0，保留其“入口监测而非任意代码形式隔离证明”的范围。

Git 历史与实验保存锚点另作区分：冻结提交的直接 Git 父提交是 `1f4650f74fd34fd95ab5984d66e266b21db8ce69`，不是上面的实验历史锚点。工作期间另有并行的轨迹导出／阅读文档提交；在线结束后的远端 main 为 `d4fcf87fb0153c6442d161b350113800bb8d0a96`，已包含本轮冻结提交。它们不在本轮模型总体或正向候选中，也没有改变本轮冻结的 src／测试或上述旧工件。本轮结果提交仅追加新实验目录和结果说明，保留并行工作；932 文件快照的范围是项目 src 树。

## 17. 本轮收口与后续边界

本轮完成了三真实来源的角色参数化、任务／μ／规则冻结、十二会话固定在线采集、有限测量与空正向表示的正确记录；科学结果是 **未观察到任何完整有效轨迹，因而没有跨绑定有效支持见证，也没有训练材料**。

同时保留两个较弱事实：新源码构造控制走通了三绑定两路线；真实模型失败前缀也确实执行过披露与实际重建输入链。这些事实不代替 Qualified、正式类、Mψ 或 Student 效用。

当前仍无已绑定独立评价集、Contribution 数值或 VTDO 更新。原 UNP/2015 已闭合的三轨迹与其 W=true 不被本次负结果推翻。后续若研究 Final 提交合同的可遵循性，应作为新的明确冻结实验，不能回写本轮、补足到成功或立即把失败前缀用于训练；本轮没有自动启动该后续实验。
