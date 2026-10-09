# FinQA末段显存修订与独立补验

用户在2026年10月9日明确授权“另行登记一次末段显存修订与补验：复用已保存梯度，不重采样、不重放573条、不放宽显存门，原B仍暂停”。本轮V34仅在新的冷进程中，读取V33已完成的573条response累计梯度，执行一次原类梯度重建、虚拟参数点和C与π独立复算，并检验修订后的末段存储路径能否满足原资源门。它不是重启V33控制器，不是重新开展完整cohort实验，也不恢复原B。

本说明按授权日期命名；实际协议冻结、启动、观察和结果的时间以各封存记录为准，用户可见时间统一按北京时间解释。当前登记的是一次有界补验，不预先声称显存修订有效或CUDA数值验收通过。V33的 `STOPPED_FAILURE_NO_RETRY` 终态、原协议和失败记录始终保留。

北京时间10月10日00:00启动独立控制器及GPU7 worker。00:03:39封存观察时为 `RUNNING`，已记录14个类梯度行完成后的资源门通过；尚无本轮最终G、C、π数值比较或完整资源验收结果。额外空闲GPU使用许可已记录，实际仍为GPU7单worker。

## 前序事实与本轮问题

[V33实测报告](finqa_v33_bounded_activation_residency_20261009.md)记录了同一物理GPU7上的新鲜R0与R3四例配对。正式回放总时间分别为197.85328842327秒和143.8003437584266秒，加速比为1.3758888417933697，超过1.20倍工程准入门，逐例logP和全部梯度逐位相等。随后完成response16实际冷恢复及573条response回放，最终累计梯度已经保存。

V33在独立类梯度及C、π复算后的最终资源门抛出 `observed CUDA memory envelope exceeded`。冻结控制流与traceback显示执行越过了全部最终数值比较，但比较字典没有单独落盘，不能把这一控制流证据写成独立成功记录。失败时allocated峰值与设备free具体读数同样没有封存，不能确定是76GiB峰值门、2GiB空闲余量门，还是两者同时触发。

北京时间10月9日23:16:43的CPU只读收口核验确认最终gJ与原实际gJ逐位内容摘要相等，checkpoint状态文件及语义摘要有效，原登记控制器和worker均已退出。V34据此复用已经产生的累计梯度，不再支付573条response的回放成本；但CPU核验不替代新的独立C、π记录或GPU资源验收。

本轮待验证的工程假设是：原类梯度计算中的部分保存张量可以在保持数值、shape、stride与storage offset合同的条件下转存CPU，减少末段活跃GPU显存；阶段间释放未使用的allocator缓存也可能改善边界free。现有V33记录不足以证明这些张量或缓存就是原失败的唯一原因，因此该方案是待验证修订，不是已经确认的故障归因。

## 独立目录与授权边界

本轮唯一输出根目录为 `trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v25_training_replication_01/replay_performance_03/`，以下称V34根目录。初始化拒绝覆盖已有登记。V32、V33以及原B的目录仅作为只读证据来源，不原地修改旧失败记录，不把补验结果写回旧成功字段。

原B必须保持 `PAUSED_BY_USER_CHECKPOINT_SAVED`，且没有active children。协议检查与worker派发都受这一暂停门约束。本轮即使全部通过，也只增加新的末段补验证据；原B恢复仍须另行明确授权，并验证其完整状态及同一feedback参数点。

| 项目 | 本轮固定预算或限制 |
| --- | --- |
| 类梯度重建 | 恰好一次原始class-gradients pass |
| 虚拟点和分布计算 | 对该次新类梯度执行一次原prepare及update路径 |
| 新response回放 | 0，不重放已完成的573条 |
| 新API调用与采样 | 0；协议仍显式登记 `api_model=deepseek-flash` |
| 新评分与真实optimizer更新 | 均为0 |
| 新微观基准与profiling | 均为0，不重测1.20倍吞吐门 |
| GPU worker | 全程最多1个，CPU初始化中的已派发worker也计入 |
| 失败处理 | 停止，不自动重试、回退或扩展优化轮次 |

新增class pass属于这次独立工程补验，不计作原B新增训练或科学预算进展。V33的四例吞吐、实际冷恢复和完整response回放仅作为既有证据引用，不重复标为V34新实测。

## 保存梯度与真实状态的来源

本轮绑定V33的 `closeout_01/record.json`、原固定point manifest、原完整pre-state及最终 `cohort_replay/checkpoints/response000573/record.json`。输入核验包括来源文件SHA、封存记录ID、point、response数量与顺序、原700分母、cohort seal、后端身份及RNG绑定；缺失或漂移即停止，不生成替代输入。

| 来源字段 | 已封存值 |
| --- | --- |
| 固定point ID | `946a8dacfdd859ee75515ce946589c7832156995956e6e974b44087e54148238` |
| V33收口记录ID | `1b410399abc5e0d3425dd9344474ef2cbca8434cbe3e413450487b9e45c562c4` |
| response573记录ID | `b4552c908f2aef48f466c0e3de0bb8307e02da596fce59ae6bb62506beff9605` |
| response573状态文件SHA256 | `a17beb9c26309d1075126fe547853e429449544b2597bb37b81bf59e7cd1072c` |
| 最终gJ逐位内容摘要 | `a75897647fccc988d55edb8e03d7b2bce29d40688390aabbb80d9df41f32c5e5` |
| 已完成response及分母 | 573条，分母700 |

实际送入本轮分布复算的gJ必须从V33最终checkpoint tensor恢复。原outer中的gJ只允许作为比较参考，不能直接加载原参考值充当新的checkpoint恢复结果。原pre-state提供真实模型、buffers、非空Adam状态、RNG及mode；禁止用新建空optimizer的自相等替代原完整状态核验。

类梯度在原pre-state对应参数上重新计算，使用原训练pool、顺序及累加规则。随后独立重建聚合G和虚拟θ，逐位对比原保存值并重新核对point ID，再由新重建的类梯度、虚拟点和已恢复gJ执行原pullback、C与π计算。不复制旧C、π作为补验输出，不采集新feedback参数点。

## 类梯度保存张量的布局保持修订

本轮新增后端版本固定为 `v34_layout_preserving_class_saved_tensors.v1`。修订只管理autograd保存张量的存储位置和生命周期，不修改原class-gradients的算术、训练样本、损失、梯度范围、精度或累加顺序。

原类梯度基线不是CPU offload路径，不能直接套用原生 `save_on_cpu` 并把取回张量的contiguous布局当成原布局。某些反向算子可能使用输入布局选择计算路径；保留原shape、stride及storage offset是本轮显式合同，最终仍以逐位数值比较为准。

| 保存张量类别 | 预登记的处理 |
| --- | --- |
| 已绑定冻结owner的view | 保留原GPU view，按storage身份及version检查绑定，不复制或改变布局 |
| 可证明无重叠的受支持非owner strided张量 | 每次save建立独立contiguous CPU pinned副本，精确复制值；unpack按原shape、stride及offset恢复GPU布局 |
| overlap或不支持的布局 | 在保存前判定并保留原GPU张量，不尝试改变表示 |

各save事件独立持有副本，不跨事件去重或复用。source与保存副本的变更检测、恢复布局检查及生命周期记账属于存储合同。无法证明支持时保留GPU是预登记分支，不是OOM后改变算法；发生OOM或绑定错误立即失败，不捕获异常后改预算、换后端或重跑。

原 `class_gradients` 函数、字节码和globals绑定均保持不变。执行时直接在保存张量hook上下文中调用原函数，仅使用只读pool迭代代理记录原CPU累加完成后的行边界；模型前向、梯度运算和原有累加仍调用原实现。这种复用减少实现偏差，但字节码一致、CPU测试或布局检查都不能替代真实GPU逐位对照。

## 阶段释放与显存证据

仍使用原资源门：全阶段观测PyTorch allocated峰值不超过76GiB，规定边界设备空闲量至少2GiB。不得提高门槛、把reserved直接解释为allocated，或以数值通过覆盖资源失败。

冷进程仅在模型加载前执行一次 `reset_peak_memory_stats`，模型加载本身纳入观测，此后不在阶段之间重置。阶段边界可执行垃圾回收和 `empty_cache`，仅释放已经无活跃引用的对象及allocator未使用缓存。释放前后都保留allocated、reserved、设备free及历史peak；清理前仍执行allocated历史峰值硬门，清理后的边界同时执行峰值与free两项门。不会在清理后重置累计峰值来隐藏本阶段先前的超限。清理后free改善只能说明新进程当前边界状态，不能证明V33旧进程当时资源通过。

每完成一行类梯度即执行峰值与free两项资源检查，阶段性记录按计算进展封存；资源检查先写入原始读数、阈值和各子条件，再对失败抛出异常。因此若本轮再次超限，应能区分allocated峰值和边界free触发项。按秒采样的设备占用与PyTorch峰值分别报告，采样缺口或错误不冒充连续峰值。

最终数值比较独立封存后，再形成资源总验收与最终结果。若数值已通过而资源失败，应保留可核查的比较记录，同时明确本轮仍失败；不得依赖异常行号间接推断比较结果，也不得因最终写入失败而补造成功状态。

## 单次执行与通过条件

唯一GPU阶段为 `tail_validation`。一次worker按下列固定顺序执行，不派发额外微观或完整response阶段：

1. 核验授权协议、冻结实现、V33最终checkpoint与原B暂停状态；恢复原完整pre-state和checkpoint gJ，确认真实Adam、RNG及参数绑定。
2. 运行一次原class-gradients pass，通过布局保持后端管理其保存张量并记录行边界资源。
3. 运行原 `prepare_virtual_point`，比较新G、虚拟θ和point ID；继续运行原 `update_distribution`，独立计算pullback、C和π。
4. 独立封存完整数值比较、模型与Adam及RNG、buffers、mode不变检查，再执行原资源总门；仅两类验收全部通过才记录本轮成功。

数值门要求恢复gJ、新G、虚拟θ和pullback逐位相等，C与π完整值相等，point ID一致，且真实状态未被修改。门槛不改为近似相等，不减少可训练张量范围，也不以汇总平均掩盖单项失败。

成功的解释限于：V33已保存gJ与本轮新类梯度和分布复算在固定点上保持一致，且修订后的单次冷进程末段满足原资源合同。这不能证明V33原cohort进程的完整生命周期已通过显存门，不能新增完整训练加速比，也不能自动授权原B接续或后续优化。

## 设备绑定与有界停止

V34固定使用V33实际运行的同一物理GPU7，UUID为 `GPU-ab6e97cc-19e4-64b8-f792-7b6920a45434`。虽然项目白名单为GPU3、4、5、7，本轮不会切换到其他卡；GPU0、1、2、6始终不参与。派发前要求GPU7没有compute进程且至少72GiB空闲，并在启动时再次核验设备身份及准入。

协议冻结后，用户进一步表示“本轮实验可以占用额外的空闲显卡”。这扩大了可讨论的资源使用范围，不增加本轮唯一class pass或response预算。当前原类梯度按固定顺序累加，尚无已登记且验证等价的多卡拆分路径，因此实际执行保持上述GPU7单worker方案，未派发额外GPU；新许可单独保存在 `resource_authorization_01/record.json`，不改写本轮冻结协议或恢复原B。

累计等待资源最多24小时，唯一GPU阶段最多4小时，安全退出宽限最多10分钟。这些值是停止上限，不是耗时预测。资源不足时只等待原卡，不驱逐其他作业，不尝试占位缓存，不调低输入规模。

超时或停止请求仅针对本轮已核验PID、birth和命令的worker处理。先请求在安全边界退出，宽限结束仍未退出才终止该worker；不触碰其他项目或账户进程。已有run intent或attempt不得重复启动，任一数值、资源、输入绑定、源代码绑定或阶段失败都停止本轮，不自动retry、fallback或创建第四轮目录。

## 当前实现与验证状态

本轮新增实现为[布局保持存储后端](../scripts/finqa_v34_tail_memory.py)、[单次补验控制器](../scripts/finqa_v34_tail_controller.py)和[末段worker](../scripts/finqa_v34_tail_worker.py)。联合CPU/mock测试163项通过，用时6.60秒，包括存储52项、控制器76项、worker35项；六个Python实现和测试文件的Ruff检查通过。检查覆盖非连续及带offset张量的值和布局、真实小型class pass逐位等价、保存对象和CPU副本释放、输入变异拒绝、资源实值与峰值不可清零、末门失败仍保留实际C与π，以及无回放或真实更新入口。这些检查不是V34 GPU通过结论；仍须冻结已提交源码并执行上述唯一GPU阶段。正式启动、资源等待和结果以V34根目录中的不可变协议、launch、阶段证据及结果记录为准，不把设计条款当成已经执行的事实。

本轮文档后续只追加其自身实施和实测状态；V33原终态与失败证据不回写。原B继续暂停。

## 冻结实现与首次运行观察

实现从提交 `da7d16072b9880aeaa60309d9a4e8f590142b27f` 冻结；新协议ID为 `480be5d26130d0b869afa11c5b33cfbd138bcf2ca4be269a5805229351de7a46`。冻结后又在独立CPU进程核验实际依赖导入路径、response573 tensor与原gJ内容摘要一致、RNG与绑定有效，CUDA未初始化；证据为 `CPU_validation/record.json`，ID为 `0dc6385c639187f07ab73a8c00321c7b1a5793470b82209daf05547740aab3c9`。

北京时间10月10日00:00:17启动控制器PID592539、birth398601281；00:00:38派发GPU7 worker PID592774、birth398603361。GPU7启动观察无其他compute进程且空闲81,154MiB，满足登记门槛。模型加载和原pre-state恢复完成后，于00:01:39记录历史allocated峰值约14.214GiB、设备空闲约64.550GiB，两项门均通过。

00:03:39核验控制器和worker的PID及birth仍存活，队列为 `RUNNING`。封存的 `event000018` 记录已完成14个类梯度行，历史allocated峰值约15.136GiB、设备空闲约61.507GiB，资源门通过。这只是早期固定时点的进展，不能外推后续最长输入峰值、完整耗时、最终数值相等或整轮成功。观察记录为 `observation_01/record.json`，ID为 `afd612e23fe97fb7bff52c69a84e467ef165a951ed392a9935b00bcfca66cad0`；包含当时队列及资源快照。

目前本实验只有一个GPU worker，无新增response回放、API、采样、评分或真实optimizer更新。后续应查看新根的 `queue/status.json`、`tail_validation/resources/`、独立 `numeric_comparison/record.json` 和最终 `result/record.json`，不得以本次启动观察代替终态验收。
