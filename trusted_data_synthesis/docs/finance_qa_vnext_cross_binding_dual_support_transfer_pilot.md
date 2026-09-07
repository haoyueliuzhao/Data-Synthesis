# 跨真实来源绑定的双支持机制复用试验

阶段：`finance_qa_vnext_cross_binding_dual_support_transfer_pilot`。本轮依据输入审计的 `PASS_AS_SCOPED`，正式关闭旧 UNP/2015 单题的支持存在性问题，转向同一参数化机制的三个新真实任务实例。

本文前半部分是首次新 Provider 响应之前的冻结设计；正式结果仅在后续结果节填写，不将构造控制算作模型样本。

## 1. 继承结论、唯一新问题和边界

前驱提交为 `1df42747bedfce1ef874fb2a2f3fb7566513964a`。上一轮三个有效轨迹全部映射、三个同任务配对确定、三个完整行为商类、严格 D/R 支持见证成立；旧成功质量仍为 `3/8`。本轮不重跑其 83 项测试或 22 项控制，不重新解释这三个样本，不重新导出旧 Token，也不执行旧 P/Q 权重预检。

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

## 11. 执行入口与待填结果

冻结前汇总验证已完成：五个新测试文件共 84 项，通过耗时 65.56 秒（来源／adapter 22、计划／runner 16、投影 13、测量 21、表示 12）；Ruff 及按项目配置检查的 14 个新源码文件 mypy 均通过。这不是重跑上一轮的 83 项测试。

新集成测试分别覆盖六会话和完整十二登记的构造 HTTP worker 链路；后者真实接通导出、测试内存编码器、投影与逐任务测量。固定路线只是测试夹具行为，不是正式会话的路线约束；其中的成功、类和见证不进入正式分母。生产 Tokenizer 的本批长度结果尚未产生。

零调用初态检查的每任务 N/E HTTP body 为：T01 47,915／48,345、T02 43,785／44,215、T03 43,818／44,248 bytes。所有重复初态相同；该检查不保证后续任意生成 State 都适配长度上限。历史 15,908 文件及 918 个旧源码也已通过字节回读。

正式入口，在项目根目录使用现有环境：

```bash
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_cross_binding prepare
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_cross_binding run
```

新目录：`artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907`。准备保存审计、来源及污染政策、三个 Task／Context、profile／配置、十二登记、初始 HTTP、规则与比较合同、源码／软件和 Token 资产身份；执行保存原传输与 Runtime 工件、worker 资格、测量、原样表示与 manifest。

正式结果尚未执行，不能从来源加和或构造控制推断未来模型的 D/R 支持、成功率、类数或表示完整率。结果出现后按原固定分母和预冻结规则填写；低成功率、单一支持、未映射有效或不完整表示均接受为有界结果，不自动补样。
