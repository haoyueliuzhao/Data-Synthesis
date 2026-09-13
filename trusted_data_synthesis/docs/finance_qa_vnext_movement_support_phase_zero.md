# Phase 0：真实 movement 支持缺失的分层诊断

日期：2026-09-13。分支：`codex/movement-support-20260913`。

本轮响应 Hierarchical Loss 审计，暂停扩大 Loss 实现，先查清真实材料中的 movement 为何缺失。本报告是**材料支持与执行接口诊断**，不是 Hierarchical Loss、VTDO 或 Student 金融效用结果。

## 1. 本轮范围与结论

本轮读取完整的 24,640 条原登记会话及资格、原材料编码清单和 255 个原训练任务。未补采、未改来源或资格阈值、未重选总体、未启动 Student/GPU，也没有覆盖任何原始资格记录。

主要结论：

1. 原评价器在进入完整状态映射之前，已认证的 movement 就是 0；不是有一批已认证 movement 随后统一被 mapper 或 tokenizer 清掉。
2. 对真实保存的公开执行事件作来源引用分析：首次 Final 的**可唯一定位、按原 witness fact-ID 角色识别的语法依赖闭包**中，movement-exclusive 来源引用为 0。全执行历史只有 2 条会话出现这种来源侧读，两条均未把它带入 Final 支持链。
3. 原 255 任务的 410 项脚本接口正对照全部通过，其中 155 项 movement 全部由原评价器认定为 movement。原公开工具及有限评价器能够表达和接受这些登记路线。
4. 公司定义题还存在明显的来源覆盖问题：4,255 条 Final 闭包存在当前 native 索引空匹配；其中 3,918 条在原资格评价中以 `source_not_uniquely_bound_to_fact` 终止。它们不是本轮发现的多候选别名碰撞，也不能统称为答错。
5. 没有发现足以授权对本批直接放宽资格、自动补齐 movement 标签或启动训练的证据。下一步重点是公开生成协议与来源定位覆盖，而非继续调 Loss。

“movement-exclusive=0”是上述有限测量的观测数，**不是**总体生成概率为 0，也不排除未绑定来源、裸数计算或未被分析的文字中存在组件计算意图。本轮不读取私有 reasoning 内容来推断方法。

## 2. 实验隔离与固定输入

独立诊断基于 main `30284a2f139b7981bc96413646459c51b76e57d5`，没有合并进 main、anchored-VTDO 或 Hierarchical Loss 分支。

| 输入 | 固定标识 |
| --- | --- |
| 本轮审计文本 SHA256 | `9ab9d290a74db96925c1da57fcb41c71a882c304d6f48bb6a0590f7a6fc8c3e8` |
| Teacher collection manifest | `manifest:97e3df4ec4728be4169f80abb3b1f1c7d535fefb4b115d9015e507034311dbd8` |
| 原材料 archive manifest | `manifest:1f3a4056e2caefb89c7b4b34a392321a788a48e374f433b1cf406ea76ffbceba` |
| 原材料业务 manifest | `fixed_AB_material_manifest:307dc06e72fbfc8ae6ef5c4792697a213bfdca24b48b4178ff9e99a6ba115981` |
| 训练任务 catalog | `composed_task_catalog:73a2a900c7e35ae3d83f872aa783c3f9614e44f44f45f292a892d724759ce46a` |

原 collection `fixed_AB_20260912`、材料 `fixed_AB_20260912_materials` 与 revision 均只读。main、anchored 和 HierLoss 的既有源码/配置/测试/文档做执行前后 SHA 快照；稀疏工作树未展开文件明确登记为 skip-worktree 缺席，不被伪称为读取过的文件。

完整预检分别校验 408,398、13,507、266 个 manifest 成员。使用既有 LinearParent 逐件字节 SHA 和精确目录集合核验，不使用会反复重哈希 84 MB manifest 的旧二次方路径。任务依赖另逐件校验 513 个成员：255 bundle、255 公共消息、3 native bindings；不声称重扫了这些三个任务父归档中的每个无关成员。

最终执行额外绑定：full/public/collection 的完整唯一任务集合、每条原资格的私有 `bundle_id`、公共身份及消息原字节、新诊断源码/测试执行前后 SHA、410 个 spawn 子进程作业各自执行前后代码一致性。

## 3. 方法与分母

### 3.1 原资格漏斗

实际训练入口为：

`collection.run → training_runtime.generate → training_assessment.assess_session → catalog_bridge.assessment.assess_replayed_session`。

它不是 900 题评估的 `eval_readiness.assessment`，也不是独立 anchored 状态目录。首先证明 Final 引用及财务支持，随后给方法标签，最后做旧完整事件映射；真实性和编码是后续的门。

本轮不重新执行 24,640 条原工具轨迹，也不重新认定它们的财务资格；资格漏斗消费原封存结论。公开执行信号只分析保存的执行事件，其内容 ID、父 manifest SHA、任务/表述及资格身份逐条核对。

原固定登记：155 dual 任务，每 task/pool 分 endpoint、movement 指导各 32 条；100 control 任务，每 task/pool 24 条。两池合计 24,640 条。所有登记和失败都保留，不删 UND、不挑成功子集、不把指导标签当实际方法。

### 3.2 公开执行信号

从第一个 Final 的 `result_id` 逆向读取实际计算表达式中使用的变量引用，保留其先前执行依赖。诊断同时记录全历史读取，以区分探索侧读与最终支持。

来源匹配沿原 source locator 与 native 绑定，只计能唯一匹配的原 witness 输入角色。`movement-exclusive` 表示在 movement witness 输入集合、但不在 endpoint witness 输入集合中的 fact-ID；它不是新的方法分类器。

语法闭包不会把 `x-x` 的引用当成经代数证明有效的支持，也不会因出现常数 100 而抹掉真实引用。未绑定、歧义、缺失引用、无来源闭包分别保留；金额、期间、单位和金融充分性不由该结构信号重新认证。

### 3.3 脚本正对照

在读取对照结果前固定全部 255 task/basis 枚举：155 endpoint、155 movement、100 control，共 410 项。沿用原 witness 脚本构造、原 32-response/32-tool 运行时、完整脚本重放和原语义评价器；8 个 CPU worker 并行，无 HTTP、Tokenizer、Student 或 GPU。

运行时对脚本 callback 仍保留字面 `origin=live_teacher_callback`；报告另明确记录真实来源 `test_only_scripted_reference_callback`。所有脚本结果的 Teacher 认证、representation 和 training 资格均为 False，训练样本数恒为 0。脚本能通过不等于真实 Teacher 生成过该路线。

脚本对照没有经过真实 transport/HTTP 请求链，不能据此验证真实请求体、输入预算准入、网络超时或模型遵循度。这些限制与公开工具/原评价器对登记参考路线的支持是不同层面。

## 4. 结果

### 4.1 完整资格漏斗

| 阶段 | 全部 | endpoint 指导 | movement 指导 | control 指导 |
| --- | ---: | ---: | ---: | ---: |
| 原登记 | 24,640 | 9,920 | 9,920 | 4,800 |
| 有首次 Final | 23,260 | 9,497 | 9,171 | 4,592 |
| 原数值 PASS | 17,723 | 7,224 | 7,118 | 3,381 |
| 原支持 PASS／financial valid | 11,855 | 4,569 | 4,401 | 2,885 |
| 原完整映射 MAPPED | 6,750 | 2,580 | 2,271 | 1,899 |
| 原 representation eligible | 6,750 | 2,580 | 2,271 | 1,899 |
| 原 token consumable | 6,750 | 2,580 | 2,271 | 1,899 |

本批上述累计数恰与对应边际数相同，不把这一巧合假设为其他数据上的普遍规律。原 actual method：endpoint 8,970、control 2,885、UNDETERMINED 12,785、movement 0。原 financial=False 中有 5,868 条 quantity=PASS，因此“未获得财务资格”不能替换为“金额错误”。

原 1,380 条无 Final：1,379 条为 transport session terminal，1 条耗尽响应上限。固定采集完成表示全部登记会话已到终态，不表示全部调用或 Final 成功。

补充只读核查了全部1,379条 transport 终止的原会话错误元数据：1,370条为 `transport.nonempty_bounded_public_content`、8条为 HTTP I/O、1条为 timeout；其中3条在首个公开响应前、8条已有响应但无工具、1,368条已有工具后终止。该公共内容合同错误码不足以再区分空内容、非字符串或超字节，不能将1,379条统称超时或输入预算耗尽。本项只统计保存的短错误码，未读取/输出 provider 私有 reasoning、headers 或重发请求，也未修改正式漏斗。

### 4.2 原前置拒绝原因

| 原 reason | 会话数 |
| --- | ---: |
| 程序不等价于金融目标 | 5,350 |
| 来源未唯一绑定（本次核查为 native 空匹配） | 3,918 |
| Final 不受指定结果支持 | 1,640 |
| 无 Final | 1,380 |
| Final 引用未知或失败结果 | 459 |
| 单位维度冲突 | 33 |
| Final shape／支持引用格式 | 4 |
| 非法数值字面量 | 1 |

其余 11,855 条 reason=None。上述是原评价器首先返回的失败原因，不能当作所有同时存在的缺陷总表。

11,855 条已通过财务支持的轨迹中，5,105 条未通过完整映射。pending 原因按包含该原因的会话计，可重叠：格式恢复 3,675、失败工具 1,716、非主支持计算意图未解释 620、失败支持结果 8。没有已分类 movement 可在该层被清除。6,750 个进入编码的原包全部可消费，编码失败不是本批 movement=0 的来源。

### 4.3 首次 Final 的公开来源结构

| 结构信号 | 全部 | endpoint 指导 | movement 指导 | control 指导 |
| --- | ---: | ---: | ---: | ---: |
| 仅引用 endpoint 输入 | 17,671 | 6,856 | 6,518 | 4,297 |
| 来源未绑定 | 4,255 | 2,135 | 2,120 | 0 |
| 结构未解决（含缺 Final／引用等） | 1,843 | 570 | 910 | 363 |
| 闭包无来源引用 | 871 | 359 | 372 | 140 |
| 唯一绑定 movement-exclusive 进入闭包 | 0 | 0 | 0 | 0 |

“仅 endpoint 输入”不是 endpoint 财务合格数；其中仍可存在错误算式、错误 Final 或未通过旧证明。4,255 条来源未绑定全部属于公司定义题，在已扫描的闭包中未出现多候选歧义。

全历史只有两条唯一绑定的 movement-exclusive 侧读，按原注册顺序：

- index 617：movement 指导／公司定义题。component 为 `tool:3`，Final 仅引用 `tool:6` 的纯数字计算，原 reason 为程序不等价。
- index 20677：endpoint 指导／存量滚动题。component 侧读为 `tool:4`；Final 闭包保留 `tool:1/2/3` 的 endpoint 链，原 reason 为 Final 不受指定结果支持。

这两条不能被补标为 movement，也不是“有效 movement 支持链进入 Final 后被误拒”的已证实例。完整注册 ID、task ID 和原 qualification ID 在最终 summary 的侧读病例清单中保留。

### 4.4 两例来源空匹配的有限人工核查

按原注册顺序各取 endpoint/movement 指导下首个公司定义未绑定病例，得到 index 88、120；两者是**同一任务的两条会话**，不能称为两个独立来源样本。

任务 `task_01bd8584a1cf4dc01f01a5113decf5df6e0a149f48219ef550ff5129cde4b21c`：CSCO 自由现金流 2019→2020 增长率。

两者 `tool:3` 都读取公开表 `issuer_table_15f4d3f79da1c4c206b33a1e` 的 `[[4,5],[4,6]]`（`$`、`14,656`），去掉货币符号后为 `[[4,6]]`。该列公开表头是 July 25, 2020，不是误取2019列。旧 native 在这张表仅登记该指标2019期的规范 locator `[[4,10]]`；目标2020期的 native 绑定位于另一公开表 `issuer_table_07672f7e5b8cc00a61264219` 的 `[[4,10]]`。

这说明两例是“公开可见的另一报告目标年单元格未进入旧 native 精确 locator 集合”，不是美元符号、括号或坐标顺序过滤问题。没有用数值相等创建别名或自动改判：跨报告实体、指标定义、实际期间与修订一致性仍需独立证据。不能把这两例外推到全部 4,255 条。

### 4.5 接口与假设排查

410/410 原接口正对照通过：年度流量 54 endpoint +54 movement；存量滚动 53+53；公司定义 48+48；control 100。所有155个 movement 对照均 financial valid、actual_method=movement、MAPPED，但来源是脚本，无训练资格。

| 假设 | 本轮证据与判断 |
| --- | --- |
| 原接口不可能表达 movement | 全任务参考正对照不支持此假设；不代表 Teacher 自然生成行为 |
| growth wrapper 漏 `change`，把百分比当金额 delta | 155个真实movement witness风险探针全False；正常 producer 统一保留 change；不支持这是本批原因 |
| 多个相同语义 fact-ID 的源别名碰撞造成批量拒绝 | 合成反例能复现旧严格判据的此风险，但255真实任务索引多候选为0，不能归因到本批 |
| fine mapper 清掉全部 movement | 原方法赋值阶段已为0；不支持 |
| tokenizer 或长度门清掉全部 movement | 6,750个原编码包全可消费；不支持 |
| 真实交付偏向 endpoint／没有保留组件支持引用 | 唯一可绑定来源范围内有直接观测支持；未绑定来源和字面量意图仍未解决 |

## 5. 训练仍未准入，下一阶段边界

原 `STOP_INSUFFICIENT_COMMON_AB_MATERIALS` 保持不变；population 尚未选择（`selected=[]`, `tasks=None`），不要称已经选出了一个正式 N=0 实验。

除 movement 全缺外，control 共同就绪仅 43/100，低于原最低72；仅看 endpoint，两池均≥10包的任务数分别为年度34、公司定义6、存量31，也未达到每dual组最低36。恢复部分 movement 并不自动满足180–200任务总体或8 train+2 heldout规则。

下一阶段应先事前登记两个相互独立的修订目标：

1. **生成与完整交付协议试验**：保持明确的原始事实/目标身份，检验如何让组件路线保留真实来源引用和 Final 支持，不靠指导标签、正确数值、脚本或私有 reasoning 补标。若修改公共来源定位说明/工具协议，必须另设版本，不悄悄覆盖原公共输入。
2. **来源定位覆盖核查**：在金额答案之外证明跨报告的实体、定义、实际期间和修订一致性，再考虑建立隔离的来源别名/资格衍生版本。空匹配不能仅按“看上去数字相同”放行。

新的 Teacher probe 若实施，必须先固定任务选择、模型/公共协议、指导、请求/Token上限、共同账本用途、失败终态及全分母报告；不按接受率追加、不替换本批失败、不把 probe 变成看过结果后的正式材料选集。本轮没有启动该新批次。

真实材料通过原门之后，才进入同任务、同原轨迹、同 pi0、seed、初始化和训练预算的 Full vs Hier 配对；TF `(0, .5, .2)` 的公开工具/Final条件可以事前登记，但本轮没有重新选择profile或声称已验证其效用。后续2×2分布×Loss交互分析仍未执行。

## 6. 最终证据与可复现性

最终CPU回归：197项通过（132项新增诊断测试、65项原Teacher运行时/评价器回归），失败、错误、跳过均0。pytest终端计时22.87秒；精确JUnit计时与文件SHA在封存manifest中记录。Ruff检查通过。测试覆盖原记录/任务身份、固定分母、语法依赖和来源角色边界、脚本来源隔离、压缩往返及发布前全通过门，不是金融效用实验。

独立复核确认：首轮和最终的资格漏斗、公开执行信号、脚本控制、原witness诊断四个文件，内容ID、原JSON文件SHA与字节全部一致；新增14个源码/测试文件执行前后相同。逐child代码门由冻结源码执行，report汇总410/all-true，但没有另存410份单独代码回执，不能声称已从磁盘逐份独立复核。

最终 report：`cohort_report:61a8e70251ff2f53e2ed47d027620ef74837b12cbe46209e6c4dcec8581a9a6a`。

最终 summary：`phase_zero_summary:902c8cd026cab47fa1470b8cf7546203b7677e951aba82dafced83a4fa9b1f05`。

最终产物目录：`artifacts/qa_vnext_movement_support/diagnosis_20260913_final/`。

- `phase_zero_summary.json`：固定分母交叉表、候选侧读病例、假设边界。
- `cohort_report.json`：执行时长、父记录、代码身份、无新增模型运行与隔离状态。
- `qualification_funnel.json.gz`：24,640条逐资格紧凑行及聚合。
- `public_execution_signals.json.gz`：24,640条逐原事件结构诊断。
- `scripted_control_plan.json`、`scripted_interface_controls.json`：事前410列表与410独立脚本结果。
- `original_witness_diagnostics.json`、`fixture_dependencies.json`：255任务风险探针与513原依赖SHA。
- `archive_preflight.json`、前后源码快照、`cpu_tests.xml`：完整原归档校验与工程测试。
- `artifact_manifest.json`：发布文件及压缩前后的字节数/SHA；gzip使用固定mtime，解压必须与原JSON逐字节相等。

大型派生JSON及源码快照无损压缩后才纳入Git；本地未压缩原件保留且忽略。没有删除、压缩或改写 main 中的任何旧科学文件，也没有再加入原来的40余万份原始轨迹文件。

开发期间曾完整运行一次同档案诊断（`diagnosis_20260913`），随后根据独立复核补足 private bundle、完整任务集合和新代码身份绑定，在 `_final` 目录重扫同固定总体。首轮草稿只在本地保留并忽略，不与最终分母相加、不作为新的Teacher样本；两轮都是CPU离线诊断。本轮脚本全矩阵执行次数为首轮410+最终410，非820条真实Teacher采集。

复现需要 main 的原始封存数据，以及另一个新的、符合分支和输出隔离门的工作树；输出使用 exclusive create，不允许在已完成证据目录直接覆盖重跑。程序入口为本分支 `finance_qa_vnext_movement_support.run` 的 `preflight`、`cohort` 两阶段，完成CPU回归后由 `seal` 无损封存。

最终状态：**诊断完成；真实训练仍未准入；HierLoss/VTDO科学收益尚未验证。**
