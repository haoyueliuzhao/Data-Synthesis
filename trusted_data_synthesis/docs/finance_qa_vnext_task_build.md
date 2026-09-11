# 从实际事实链路构建 QA 与 vNext TaskBundle

阶段标识：task_factory_20260911。开发跨越北京时间 2026-09-11／12。

## 1. 对象与边界

本阶段落实“先合成任务，再合成轨迹”的源码审计要求。上轮来源盘点提交
459e6d66d11ca48244d61a4375e7092220ef47c6 及其 PASS_AS_SCOPED 结论保留；
不把上轮“未调用任务工厂”改称“任务合成零产率”，也不重跑旧 193 项盘点控制。

用户提供的 439 行审计文本 SHA-256 为
92540bfcd9dda6c6dbb7408143be70e242f7ca44fd96beee4298cc5d501411c4。
本阶段直接交付有真实父产物的 QA Build、问题和 TaskBundle，不是另一本来源关键词清单。

本节随实现首次提交时，正式来源任务尚未运行；实际结果在文末据产物补充。
代码、规则冻结不表示两池材料、训练总体、token 表示或整套效用实验已经冻结。
本轮不调用问题生成 LLM、Teacher、Student，不加载 tokenizer 或模型权重，不使用 GPU。
参考计划执行是 Oracle 运算，不是模型行为，不进入训练轨迹池。

## 2. 实际输入与隔离工作库

配置的 PostgreSQL localhost:5432 拒绝连接；当前进程没有可用的 Docker 管理权限。
这没有被解释为项目不存在可信事实。实际使用项目保存的成功 KG 存档：

raw_financial_data_lake/data/kg_archive/kg_build_id=kg_20260723_191638_396e6b92/

核验原 manifest、Parquet 字节 SHA-256、长度、行数，以及 KG 的 success／passed 状态。
原 KG 已被后续历史构建取代且不活跃；本阶段没有重新激活，也不宣称生产数据库在线。

| 上游对象 | 原存档标识 |
| --- | --- |
| KG | kg_20260723_191638_396e6b92 |
| 标准化事实 | fact_standardization_20260723_185711_494c7bf6 |
| 原子事实／文档 | fact_build_20260723_183450_a48fea09 |
| 实体 | entity_normalization_20260723_151202_4ff03a59 |
| 指标 | metric_ontology_20260723_165801_15d8702f |
| 来源定义 | source_definitions_20260723_185646_076d1e44 |
| DerivedFact | qa_ready_20260723_191242_fc4796e4 |

原图行在隔离 SQLite 中逐行恢复。服务表投影只使用原节点属性及真实边：

- Fact.graph_ready 来自已通过质量门的有效 Fact 节点、原 graph_ready_reason=ready
  和已验证状态，不依据关键词或金额闭合。
- DerivedFact.input_fact_ids 来自完整 DERIVED_FROM 边，不猜运算输入。
- 原属性没有保留的上游字段仍不可用；服务表默认时间戳不是历史事实创建时间。
- 旧存储前缀 /workspace/Data Synthesis/ 仅在本地解析并核对字节，不改写父存档。

恢复库为 artifacts/qa_vnext_task_build/runtime_20260911/qa_build.sqlite3；
新事实与 QA 使用另一隔离库 native_fact_qa.sqlite3。这些运行库不提交 Git。
原 PostgreSQL、原存档及历史实验产物不做写入。

## 3. 来源、用途和规模规则

公司取自存档的 US company 实体，不从 FinQA 原题筛出 200 个任务。
同一 canonical CIK 是来源簇；不要求先进行所有历史公司代码的无界法律实体认证。

任务生成前固定 SHA256(固定盐 + cik: + CIK10) mod 55：
盐为 basis_task_factory_sources_20260911.v1:；桶 0..9 为 train，
10..18 为 dev、19..54 为 confirm。本次只构建 train。
这是原始事实来源的新用途划分，不把 FinQA test 目录重新标成训练集。
直接事实、DerivedFact 展开的叶事实、以及仅用于私有关系校验的叶事实，
均须在绑定和导出时同时满足用途和 split。

候选上限为年度流量 54、存量滚动 53、公司定义指标 53、控制 100，
合计最多 160 双依据和 100 控制。先在同一阶段导出 12 双依据＋8 控制的 20 题，
再连续构建剩余候选，不插入效用训练、同内容复审或追加采集申请。
两批可有不同的实际 QA Build ID，但输入 KG、规则、代码、模板和枚举策略相同。

枚举按公司 CIK 轮转、实际期间、目标身份排序，不按模型正确率或效用排序。
变化额与合法正基数变化率是不同数量目标，可以分别生成；措辞或参考路线变化不是新任务。
同源目标共享来源簇，不能用目标数扩大独立样本量。

最终设计仍是三组各 40 个双依据任务＋80 控制；约 180—200 的最终总体只能在后续
两池共同就绪交集上按原规则锁定。候选目录达到某个数字不等于该总体已经就绪。

## 4. 只为实际缺失的事实和期间回补

诊断发现部分 SEC 披露 fy 被用于观测年度，有的“跨年变化”实际引用同一期间，
且归档组成项覆盖不足。本阶段不改写旧事实，不据此断言历史发布 QA 受影响。

原生适配器从已有 SEC companyfacts JSON 读取有限注册指标：毛利、收入、成本、利润、
现金、受限现金、经营／投资／筹资现金流、资本开支，以及相应口径的汇率影响和完整现金变动。

- 原始 USD；10-K／10-K/A；观测结束年 2010—2025。
- 流量须有 330—380 天的实际期间，不能只因 fp=FY 就认作全年。
- fy 与观测结束年一致只是有限筛选条件，不是通用财政年度解码器。
- 同公司／指标／实际期间先按登记概念优先序，再按 filed／accession 选择，
  不搜索能令关系闭合的金额。
- 同概念、单位、期间、精确金额的全部原始披露位置保留，用于同 accession 核验。

公开问题使用真实起止日期。披露 fy 和目录年份提示不替代题面期间合同。
新增事实实际经过原子事实 Build、标准化、事实质量门、DerivedFact Build 和 KG Build。
graph_ready 由现有事实质量门写回，不直接给来源线索加资格标志。

美元转换使用 Decimal 百万尺度，并将 SQLite 数值与原始精确值核对；
不能精确保留的绑定记录排除，不静默舍入准入。表内签名调整额不统一改成正数费用。

## 5. 三类关系合同与两种见证

### 年度流量组成

有限首版实现毛利变化。每个期间必须有原始 GrossProfit 定义、完整收入／成本口径、
统一单位、合并实体作用域和共同披露 accession，再检查金额是否满足定义。
单纯 CostOfGoodsSold 不因金额闭合就被当作完整商品和服务成本。

端点见证执行两期毛利差；组成见证执行两期收入和成本变化。
变化率的组成见证也从前期组成重建分母。

### 存量账户滚动

现金及现金等价物，与包含受限现金的更宽口径分开登记。
需要期初／期末、经营、投资、筹资及相应口径的汇率项，缺项不假设为零。
同一披露的完整现金变动量另作私有完整性校验，且要求共同 accession；
这个直接变化量不进入公共输入，不冒充 movement 轨迹。

端点见证做余额差，movement 做四类签名期间流量之和。
变化率允许共享必要的期初基数；两种充分依据不等于所有叶事实必须完全互斥。

### 公司定义指标

从相同训练 CIK 的本地 10-K HTML 定向读取 FCF 调节表。
不把 GAAP 毛利划入此组，也不统一套用 CFO−capex。

必须有发行人定义或明确按下表计算的表述、一个 CFO 起始行、一个已报告 FCF 总量行、
完整签名调整行、明确年度列头／百万尺度，以及同公司同 accession 的精确 USD CFO 锚点。
原目录 period／filed 只作诊断；可用时用 HTML DEI DocumentPeriodEndDate 及原始 filed 核对。

首版是有限的定义词汇和金融组成角色解释器，不是通用自然语言财务审阅器。
定义与完整行集合必须一致；未知调整、缺行、嵌套小计、歧义期间和不支持布局均拒绝。
法律／并购调整、CHIPS 补助等必须在该发行人的定义与完整表中出现才可纳入。
不是先加减金额，再反推出定义。

未标明含义的破折号不自动解释成零。拒绝记录须定位文档、表格和期间，
不能概括成“公司指标不存在”。最新已完全核验的期间记录优先，
不宣称一定采用最新可用披露；较新失败记录与较旧重复版本均保留。

端点见证用两期已报告 FCF，组成见证用全部签名调节行；
变化率分母也重建前期完整组成。期间之间定义变化时不混用。

## 6. 已有 QA 链路的实际接入

新注册 pinned_annual_metric_change 和 pinned_annual_metric_growth 两个 Pattern，
复用 materialize_plan／execute_plan。linear_combination 要求逐项 ±1 系数和一致尺寸；
ratio_percent 要求相同尺寸及严格正基数，输出 percent、currency=null。

实际调用：

1. build_qa_candidates 建立真实 QA Build，关闭全部默认大配额；
2. 从同 KG 查找相应真实 DerivedFact，核验其全部叶事实用途；
3. _graph_pattern_candidate 从注册 Pattern、事实及计划构建 Candidate／OperationPlan；
4. generate_qa_samples 使用既有确定性模板和受保护槽位生成题目；
5. validate_qa_samples 独立解析已保存题面，重验语义、证据、输入、单位和执行；
6. 导出时再次核验源金额、期间、定义、叶事实用途及独立 Decimal 目标计算。

没有伪造 mined proposal、发布分数或 Compilation 成功状态。
适配器记录保存真实 Pattern／Candidate／Plan 父引用、实际入口与绑定；
所有实际父表另行分块导出。

局部修复：

- validate_plan 在核验前驱引用后才登记当前步骤 ID，拒绝自引用、前向引用和重复 ID。
  原执行器已有失败路径；静态缺陷不是历史坏样本发布的证据。
- SQLite MetadataDB 原缺少 update_standardized_graph_ready。实际 Build 合成控制暴露缺口，
  已补齐接口，不绕过事实质量门。
- 新增 bound_facts.count 与 actual_periods/adjacent_annual 语义检查，
  让现有 QA 验证器直接重验真实期间，而不只信适配器的一次筛选。

## 7. TaskBundle、公共输入与目录

每个 TaskBundle 保存规范任务身份、QA／Candidate／Pattern／编译记录／Plan，
KG／事实／实体／来源定义／文档、全部叶事实父引用、实际检查 ID、split 和来源簇。

公共白名单只有问题、原始来源视图、数量及共同工具合同。
JSON 来源保留概念、定义、期间、金额与原指针；发行人表保留原行列及定义上下文。
不复制 canonical_semantics、source_metadata、answer_payload 或私有正确角色表。
私有对象单独保存规范目标、精确答案、可执行参考与 Oracle 见证。

SynthesizedTaskCatalog 要求显式指定本阶段 manifest ID。
public_messages(task_id) 只返回冻结公共消息；private_oracle(task_id) 是分离的离线接口。
没有默认回退至 FinQA test 或 X1/X2。后续 A/B 读取同一任务、同一题面与同一公共来源。

teacher_visible.json 是将来的公开输入，不是已经发生的 Teacher 会话。
实际模型会话、训练材料和 tokenizer 产物为空。

## 8. 冻结、运行与复核

仓库根目录下使用 trusted_data_synthesis/.venv/bin/python，
设置 PYTHONPATH=raw_financial_data_lake:trusted_data_synthesis/src。
模块入口 trusted_synthesis.experiments.finance_qa_vnext_task_build.stage，
依次使用 freeze、run、verify 子命令。

freeze 要求实施代码已提交，记录实际 commit、代码 SHA-256、规则和存档引用。
同冻结版本运行一次，执行来源回补和真实 Build，再连续输出首批与候选批。
产物目录为 artifacts/qa_vnext_task_build/task_factory_20260911/。

开发时已见来源字段和几个报告例子，不声称从未看过来源的盲法。
正式总体及任务输出不在冻结前试跑。合成控制与正式来源分开，不计入真实任务数。
复核成员集合、长度、SHA-256、身份唯一性和公共消息一致性；实际父表每 500 行分块，
SQLite 运行库排除在 manifest 和 Git 外。

凭据、线上模型、CUDA、权重加载等入口设零执行守卫。
这是已插桩入口的证据，不是任意代码的形式化沙箱证明。

## 9. 保留但未执行的后继

保留 25,280 Teacher 会话／808,960 请求及累计 10 亿输入输出 token 上限。
以后如调用模型抽取或审核任务，需另登记，不得藏入离线准备。

N=200 时每池 2,560 训练包＋640 封存包，三臂方法质量、五题（3 双依据＋2 控制）
64 包更新、十遍 400 更新，以及 A 开发选择／B 不做开发评测等设计不变。
真实 token 预算须来自后续原样物化。

本轮未执行线上原子预留、五任务 Trainer 训练、两池材料共同就绪、
180 开发题或 720 确认题，也没有 Student 效用结论。
不能只打开旧离线字典账本的开关就宣称下一阶段可执行。

## 10. 实际运行结果

待同一次冻结 TaskBuild 正式运行后，按 manifest、QA 验证记录及 TaskBundle 补充。
当前开发验证为 184 项新接口及相关 QA 回归测试通过（13.16 秒）；不是旧 193 项盘点的复跑。
