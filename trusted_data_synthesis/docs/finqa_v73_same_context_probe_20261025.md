# FinQA V73 同上下文提交行为探针

日期：2026-10-25，北京时间。依据V72后续审计及用户“参照审计修订并开展后续实验”授权。

当前状态：独立`execution_revision_02/`已于22:31:55以`COMPLETE`收口，789次生成、288条概率测量全部完成，六GPU及最终CPU/controller实际exit0、资源门通过，监督器随后退出。288个逻辑对角线的原文/token全部复现，UNKNOWN为0。F组L(hP)有45/48合规提交候选、L(hL)为0；同hP仍失去动作的3题中结构NLL为2降1升，不能统一归为语法遗忘。完整分析见[最终实验报告](finqa_v73_final_experiment_report_20261025.md)。以下22:20:28启动快照保留其历史时间含义；旧01失败和所有准备记录不回写，不启动后续训练或Full。

本轮检查两个相互补充的问题：给定同一真实交互历史，后继模型是否仍更容易放弃合法下一动作；进一步固定父回应的前置文字后，对相同关键动作token的条件预测是否也变化。结果用于定位后续训练应验证的因素，不产生新的FinQA准确率，也不自动启动训练或Full。

独立目录：

`trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v73_same_context_probe_01/`

上列父目录保留选样、输入准备及未启动首版。`execution_revision_01/`保留首次冷worker失败。新的受控执行根为该目录下的`execution_revision_02/`；不能启动父目录或01旧入口。

## 1. 三个已有模型与固定样本

| 简称 | 实际checkpoint | 作用 |
|---|---|---|
| P | V71 `execution_revision_01/training/step1192_step` | V72未干预共同父点 |
| H | V71 `execution_revision_01/training/step1490_step` | 原学习率1e−4后继 |
| L | V72 `training/step1490_step` | 低学习率1e−5后继 |

每个模型绑定原完整checkpoint记录、state字节SHA、实际状态digest、已接受训练结果/真实退出及原生成model identity。worker只读已有参数和buffer，底座沿用原BF16、SDPA及tokenizer；从已有A/B张量直接建立原LowRankLinear实例，使用原forward，不创建optimizer，不随机初始化新的LoRA，不反传。

| 条件组 | 固定候选规则 | 候选题数 / 报告来源簇 | 选中题数 / 来源簇 |
|---|---|---:|---:|
| F，残余失效 | P=R，L=I；L终末类别为缺少有效提交且停止原因为`no_tool_call` | 125 / 87 | 48 / 48 |
| K，保持正确 | P=R，L=R；不限制H结果 | 380 / 174 | 48 / 48 |

分别按已保存`source_group`报告簇分组，使用固定盐`finqa-v73-same-context-20261025-v1`和完整task key哈希排序，按簇轮转各取48题。每组实际选中48个簇、每簇1题；候选集合、簇顺序、名单与来源计数先于原请求准备封存。缺档不换题，不按新结果调整名单。

这96题是条件性机制样本。F/K必须分别报告；人为设置的50:50比例不是883题的实际失效率，96题也不是96次训练重复。

## 2. 实际历史、输入重建与事前去重

每题的三个历史分别是：

- hP：P原episode实际成功`submit_program`那次模型调用之前的完整输入。通过真实tool event、call ID及原final_program定位，不能用普通文字提及submit替代。
- hH：H原episode最后一次模型调用之前的完整输入。
- hL：L原episode最后一次模型调用之前的完整输入。

读取所选原episode、已封存run/seal和receipt，保留真实messages、tools、配置、已有工具观察及错误恢复；不添加提醒、未发生的工具输出、原分数或私人答案。父模型当前回应只进入独立targets概率通道，不进入自由生成contexts。

重建必须同时满足原request语义绑定、原rendered prompt SHA及全部`prompt_input_ids`相同。保存的JSON使用sort_keys，而Qwen模板中的tools JSON保留字典插入顺序；因此用**原冻结工具工厂**恢复已丢失的键顺序。恢复前要求完整工具对象逐值及canonical digest完全相等，不能用工厂覆盖语义变化。原提示字节和逐token门不放宽；运行前以及真正provider调用前都应用同一恢复函数，避免再次经过JSON落盘后失配。

输入去重键包含实际prompt IDs、tools、配置、tokenizer与chat template digest。相同输入在每个模型下只生成一次，保留全部来源标签和每个来源自己的旧回应SHA，不挑选多个新输出。

| 准备结果 | 实际计数 |
|---|---:|
| 固定任务 / 每组任务 | 96 / 48 |
| 已核对来源历史 / UNKNOWN历史 | 288 / 0 |
| 去重后实际不同输入 | 263 |
| 合并的来源历史槽位 | 25 |
| 三模型逻辑生成格子 | 864 |
| 三模型实际计划生成调用 | 789 |
| 父回应目标 / UNKNOWN目标 | 96 / 0 |
| 三模型实际计划概率序列 | 288 |
| 原输入长度范围 | 2711—8967 tokens |
| 父回应长度范围，含实际EOS | 72—160 tokens |

## 3. 单回应生成与静态动作指标

三个模型分别在hP/hH/hL上生成一次assistant回应，沿用原greedy、seed20260928、T0/top_p1/top_k0、2048新token上限和24576 context上限。每格只调用一次provider；不执行新工具、不追加观察、不继续下一轮、不调用native scorer。

| 互斥动作类别 | 判定 |
|---|---|
| 合规提交候选 | 恰好一个submit_program，原封套、参数及纯程序语法通过 |
| 合规非终末动作候选 | 恰好一个登记的非终末动作，参数结构/必要纯语法通过 |
| 尝试提交但不合规 | 已解析submit_program但参数或程序表示不合规 |
| 普通文字且无工具调用 | 没有原生工具封套；文字声称提交不算实际调用 |
| 其他合同失败 | 多调用、未登记工具、封套/JSON/非终末参数等失败 |

A为“至少有一个静态合规下一动作”的指示量；本轮原合同只接受单调用，故A=1对应前两类。S=1只对应合规提交候选。合法非终末动作不会自动被归为失效，A/S都不证明程序能执行或答案正确。

实际EOS、finish_reason、响应长度和截断标签单独保存。没有EOS且finish_reason为length时，只有达到token上限才称按上限截断；不足上限单列。UNKNOWN不并入无调用，也不填零。

F、K分别输出三模型×三历史的A/S及五类计数、普通文字率和同题获得/丢失。hP列的跨模型配对是首要读数；同时保存固定历史比较模型、固定模型比较历史两个方向。源模型在源历史上的对角线记录原始回应字节与实际token是否重现，差异不通过重试或换题消除；P/L相关旧结果参与题目选样，H旧回应只作再现参照，不能说H参与了筛选。

不同历史含有的信息与执行进度可能不同，跨列差异只描述上下文敏感性，不分配“历史造成多少退化”的因果比例。

## 4. 固定父回应的独立概率测量

对同一实际hP与父回应yP，计算原始完整词表logits的float32 log_softmax；目标token及前缀都使用父receipt实际保存的IDs，不重新生成或重新分词替换父回应。模型只运行推理前向，输入为`prompt + target[:-1]`，最后len(target)个logits按因果位置预测target，包含原来实际生成的EOS。

每条序列执行一次模型前向，Qwen只输出响应对应位置的logits，再按64个位置分块做完整词表log_softmax。块处理不调整温度、不缩词表、不反传；记录实际model/transformer/lm_head forward及输入位置，不能把288条序列称为288次底层算子调用。

逐目标token按实际ByteLevel字节边界冻结分组，不能把程序数值或算式变化归为工具语法变化：

| 分组 | 含义 | 96条父回应的目标token总数 |
|---|---|---:|
| pre_action_text | 工具动作之前的公开文字 | 7206 |
| action_structure | 封套、动作名、JSON字段及结构 | 1728 |
| program_parameter_content | program字符串内部内容 | 1550 |
| actual_terminal_EOS | 原实际终末EOS | 96 |
| boundary_mixed | 跨上述字节边界的BPE token，单列 | 0 |
| post_action_whitespace | 动作之后的空白，单列 | 0 |

六组覆盖全部目标token，缺组的sum/mean记NA而非0。本次96条中前四组均存在，后两组全部NA。对F/K分别报告每组序列平均NLL、分布摘要和token池化值，以及H−P、L−P、L−H同题差值、正/负/零数量及NA/UNKNOWN。

若H/L在hP上失去动作且固定父前缀后结构NLL也变差，可支持关注相同条件下的动作保持；若自由生成失败而该结构NLL未变差，更应考虑当前回应内部的续写路径。对父模型一种表达的NLL变化不代表所有合法表达的变化，须与实际生成读数并列解释。

## 5. 固定预算与零操作项

| 项目 | 审计上限 | 本次冻结准备的实际计划 |
|---|---:|---:|
| 既有checkpoint | 3 | 3 |
| 独特任务 | 96 | 96 |
| 单回应生成 | 864 | 789，事前去重 |
| 固定父回应概率序列 | 288 | 288 |
| 新工具执行、native EA/PA评分 | 各0 | 各0 |
| optimizer更新、新LoRA随机初始化、反传 | 各0 | 各0 |
| outer、反馈、class、梯度回放、VJP | 各0 | 各0 |
| 外部API调用、新训练条件、Full恢复 | 各0 | 各0 |

父回应概率目标不馈入自由生成通道。没有额外随机draw，不因为对角线不复现或结果不明显而重复生成。所有比较条件、样本、输入和指标在推理前冻结。

## 6. 并行、持久返回与退出验收

P/H/L各分成两个固定分片，按去重context ID和task key稳定哈希分派，最多6个worker、每物理GPU1个。分片只划分既定项目，不重复输入或增加预算；每worker加载一次对应模型，完成分配的生成和概率测量。

沿用GPU0—7，优先6、7、2、4、5、3、1、0；共享准入但不干预其他项目，UNKNOWN归属/MPS仍阻断。生成/概率同属推理生命周期：准入free24GiB，启动RAM48GiB/worker并按原公式补足已运行worker预留，全机有效可用RAM保留96GiB；allocated历史峰限76GiB、规定边界free至少2GiB、worker RSS限192GiB，模型加载计峰且不重置。初始化、等待和draining占用名额及原GPU租约。

每项计算先保存独立intent；真实返回先原子封存，再做调用后资源检查和纯CPU分类。已返回项在后续attempt只读复用，不重新调用模型。只有确认的资源故障且处于实际持久边界，才允许300秒退避；连续三次无进展后停止。若声称“尚未调用”，须同时有forward增量和provider实际生成调用增量均为0的证据。任何未解决的intent、UNKNOWN新返回、绑定/数值/实现错误均停止，不盲目重试。

每次attempt独立保存launch、PID/birth、结果、资源及真实waitpid。写完结果但尚未退出时保留租约和名额，六个作业全部实际exit0并接受后建立退出屏障，才启动独立CPU汇总。CPU启动RAM160GiB、RSS64GiB、host余量96GiB，隐藏CUDA；其实际exit0与资源验收后才收口。

监督器只启动本轮控制器一次；控制器异常退出不自动重启，先核对并停止本项目已登记子进程。明确STOP或合法owner信号禁止恢复；沿用原已授权的进程内信号处理边界，不启动全机观察器或新cron。运行和资源等待不设置任意墙钟截止；停止后的600秒宽限由本轮活跃进程共用，不逐worker重置。

## 7. 准备期问题及修订证据

第一项准备错误发生在原episode读取前：注册器添加来源引用后，把旧的内存selection ID传给下游，而发布记录已产生新ID。后续使用实际封存记录，保持同一名单，没有重新抽样；记录位于`preparation_attempts/attempt0001/record.json`。

首次原请求重建把JSON保存后的tools键顺序直接传入模板，288份历史均未通过原render SHA门，全部记UNKNOWN，0份可执行新输入。没有GPU、模型、工具或评分调用。该记录保留在`inputs/record.json`，旧生产源码保存在`preparation_sources_01/`，阻断证据为`preparation_attempts/attempt0002/record.json`。

对唯一选中的父请求做有界诊断后确认：用原冻结工具工厂恢复相同工具对象的插入顺序，提示SHA及3572个token全部恢复一致。输入准备和实际调用共同使用这一修订，而不是绕过哈希；诊断记录为`prompt_order_diagnostic_01/record.json`，ID：

`26484508d805d6d833b944a95effa2884eea84a30f01a2468ebf719e96eef24c`

随后对同一96题完成一次独立修订准备，原288份历史全部通过。正式协议只会引用修订输入，首版UNKNOWN记录不回写。

| 准备证据 | ID |
|---|---|
| 固定选样 `selection/record.json` | `a49e8f8fcf396673506e85b3d8b77761d715de3d4f8d2d40cd0a9bc8460cdb97` |
| 正式输入 `inputs_revision_01/record.json` | `a73295d38d0d81c23d7ddba127e9b711d726385b406067cc3bdade8777c3c11d` |

正式输入字节SHA256为`1ed986e7fcbfa458136ea5868926d65e2b71b8a3ca62367de0016a01ae6f8aff`。上述均为CPU准备结果，不能称对角线已复现或模型行为假说已获支持。

源提交`4bc17b2c12`的首版冻结协议`220f99e6cc1b1887a86469e1c2dc3c82f29467ef9a9dedee038fb7edfe0132f5`及11文件包`9940769b548997ee10c53c7aa681615ea6397866d7d28d6e4e375b71e7b734a7`在正式CPU导入检查时被拒绝。遗漏项是原`metric_vendor/__init__.py`的77字节文档字符串；原纯程序分词文件也需把既有PROVENANCE中的SHA显式纳入允许导入表。修订仅绑定这些原字节，不修改vendor或执行其评分函数，也不取消导入来源门。

该次entry退出码为1，GPU/模型/工具/评分/optimizer均0，收口记录为父目录`preparation_closeout/record.json`。旧包、协议、输入和失败保持不变；新执行在独立`execution_revision_01/`重新登记，复用原选样及已通过的修订输入，不重做288份历史准备。

`execution_revision_01/`从源提交`60cbbfd1b4`登记，协议ID`839d2dda3327eeb3bce9be8b2427c02309e4bdc1d5b35f561d16c51b311902f3`，实施包ID`bd052197e409280114ba06385a7588dd975b3fac81bfdcdfd5a2cab2f9b5e3a1`，正式CPU导入核验ID`0a8a20afd070bb31d78c25568c0d3bda25ccf7e7d544e382c37091c66b938953`。21:54:41实际启动监督器1961180/birth536087594、controller1961250/birth536087624；首个H.shard0派发到GPU6，PID1961814/birth536087860。

该worker在继承的V56资源守卫构造器中被`resource_recovery_policy`登记一致性检查拒绝：协议有本轮`recovery_policy`，但漏了资源守卫单独要求的顶层字段。错误发生在原V54构造器、`__enter__`、CUDA set_device和Predictor之前。实际worker exit1、controller exit2，21:54:56以`STOPPED_FAILURE_NO_RETRY`收口；不是显存不足或数值失败。21:57核对三个身份均已退出，intent、模型加载证明、实际返回均为0。

01的收口ID为`eb20ce571739facab2767d01d0fa49d67fd4871b8bd01454e107df4ecaa4848d`，补充边界证据为01下`cold_entry_failure_audit/record.json`。自动恢复没有重试此实现故障。当前任务修正通过独立02登记：补齐同一资源政策字段并在冷入口直接检查完整资源构造契约，保持原输入、模型、数学、预算和硬资源门；不重启01、不将原失败改写为准备成功或资源故障、不重做选样/上下文。

## 8. 结果解释及后续边界

完成后得到F/K分别的“模型状态×相同历史”动作矩阵和固定父回应的分组概率变化。对角线大量不复现时，应明确测量再现性限制；没有预设“多少例算大量”的统计晋级门，不根据结果删除题目。合法非终末动作与提交选择、公开文字续写与结构条件概率、静态候选与可执行正确答案均分别解释。

本轮不能证明必须从头训练、旧模型不可修复、某学习率最优或唯一内部根因。任何新训练、1490续训修复、底座/seed/学习率网格或Full恢复均不属于本轮；如后续改变内层学习规则，Full虚拟更新及Contribution也须重新绑定新规则。

## 9. 实施核验

共159项不同的针对性CPU/mock用例通过：输入16、动作与概率测量26、统计汇总11、推理适配21、worker持久返回13、注册/入口适配7、控制器生命周期27、最终CPU独立退出屏障16、完整资源构造契约22。受影响路径在修订后回归；没有重新跑旧科学测试或GPU小试。资源新增用例包含真实继承构造器的CPU沙箱，禁止进入`__enter__`、查询设备、启动监控线程或初始化CUDA；明确验证worker容量等待policy与controller重试policy不能互相替代。另以纯JSON夹具连接worker输出、概率分组和最终汇总，检查UNKNOWN保留48分母、NA不补零及对角线来源SHA。

实际加载证明由每个真正加载模型的attempt另行封存，包括原架构、实际identity、直接安装A/B及零随机LoRA初始化/optimizer/backward；只复用全部既有返回的新attempt不会补造加载证明。最终CPU入口自身核对六个accepted、退出屏障、launch/actual PID-birth和资源/剂量，不仅依赖控制器的布尔状态。

## 10. 独立02已实际启动

源提交`040384d40c`已推送。11文件实施包ID`9d3b2c748fbc0fc0610f04dc4e4da59ffa1676d2e52d12417dea32db106b9cad`，协议ID`6ca6c4b8775b30a96cbe6346e5b5a188713a58299d2a14cf736e5fbbc9da0bac`。正式冷入口实际297项依赖及完整资源构造契约通过，CUDA未初始化、模型未加载；核验ID`8ee89904e527977b0b6587cec70a560952bc59f9e6840b1f242b7859bb425565`。

2026-10-25 22:12:47北京时间单次启动监督器2127332/birth536196184、controller2127400/birth536196214。22:20:28的启动验收中六个worker均为attempt0001，实际模型参数/buffer身份、直接A/B加载及首批返回均已封存；旧01未重启。

| 作业 | GPU | PID / birth | 已完成 / 计划生成 | 已完成 / 计划概率序列 |
|---|---:|---|---:|---:|
| H.shard0 | 6 | 2127964 / 536196459 | 55 / 142 | 0 / 45 |
| H.shard1 | 7 | 2128309 / 536196670 | 60 / 121 | 0 / 51 |
| L.shard0 | 2 | 2128911 / 536196945 | 64 / 142 | 0 / 45 |
| L.shard1 | 4 | 2129452 / 536197249 | 63 / 121 | 0 / 51 |
| P.shard0 | 3 | 2129864 / 536197511 | 58 / 142 | 0 / 45 |
| P.shard1 | 1 | 2130481 / 536197782 | 58 / 121 | 0 / 51 |
| 合计 | 六卡 | 六个模型实例 | 358 / 789 | 0 / 288 |

worker先完成各自生成，再对分配的父目标做概率测量；0/288是该快照时的进度，不是取消概率通道。358是已完整封存且归一化的实际单回应结果，不是预登记槽位数或完整Agent轨迹数。

已读取的资源日志前缀按长度和SHA固定，下面单位为GiB，只描述截至快照的观测：

| 作业 | 资源观测数 | allocated历史峰 | RSS峰 | 最小边界free | 最小有效可用RAM |
|---|---:|---:|---:|---:|---:|
| H.shard0 | 171 | 15.293703 | 15.318481 | 29.784546 | 610.163879 |
| H.shard1 | 186 | 15.226955 | 15.321064 | 61.592712 | 610.167862 |
| L.shard0 | 196 | 15.293703 | 15.315464 | 32.077515 | 610.066666 |
| L.shard1 | 195 | 15.226955 | 15.318077 | 12.714172 | 609.719044 |
| P.shard0 | 180 | 15.293703 | 15.313278 | 10.230286 | 609.626968 |
| P.shard1 | 178 | 15.226955 | 15.340057 | 29.364624 | 610.191906 |

全部已观测门通过，不保证后续峰值；规定运行边界free为2GiB，与启动24GiB门分开。启动验收仅额外读取JSON、已登记PID身份及资源日志前缀，没有新增模型、GPU、API、工具执行或评分。

启动验收ID`01354348f70af3e657d8feb59a61ff2fe73b19eea3834bfa61303217756cd9e8`，保存在02的`startup_verification/record.json`，仓库启动摘要与该文件逐字相同，SHA256为`55aab1aeeadee592a64a98fa25273319b80cfa6079298c87f4f131e06394ce43`。

进度只看02的`queue/status.json`、`supervisor/queue/status.json`及各`jobs/*/progress/status.json`。终态须看实际退出、最终CPU接受及`closeout/record.json`；不重复activate、不启动旧根或01，不因中间行为结果改变名单/日程。

## 11. 实际完成

22:31:55科学closeout为`COMPLETE`，ID`f56de120229879fa86e1960b88c115bcea0cc296de4a1047131d0a4e7174f6ed`；最终摘要ID`d8dd69595a529a0a387345547a6646cda60017b66a76347f229e2fd411e431e7`，状态COMPLETE。六作业均在02首次attempt完成789/789生成、288/288概率并真实exit0；最终CPU实际exit0、未初始化CUDA，资源PASS。监督器22:31:58收口且已登记身份退出，没有自身waitpid码；不追认01失败。

新生成95947 tokens，实际model/transformer/lm_head forward各96235次；固定父回应目标累计31740 tokens。新工具执行、native评分、训练、反传、外部API均0，无自动后继。完整F/K矩阵、NLL、同题失败交叉分析、资源和来源见最终报告及两份机器摘要。
