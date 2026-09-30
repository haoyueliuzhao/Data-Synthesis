# FinQA 排队任务回放优化与断点恢复

本次根据用户2026年10月1日“针对正在排队的任务做优化，正在运行的实验不受干预，同时注意保存断点及恢复相关的设置，优化完毕之后继续在这四张卡上排队”的要求，仅升级未启动任务的执行层。V19是执行配置版本，科学实验仍是原V18五臂实验，不重新注册科学问题、不更换数据或Student。

已完成固定八token回放的存储优化、response级断点、四卡排队与冷恢复实现。35项CPU控制和Ruff通过；实际CUDA等价性与耗时检查登记为待空卡执行，不能把CPU通过写成GPU提速已经成立。新回放只允许用于尚未启动的Full seed29与47，且必须先通过该CUDA检查。登记和实际启动证据见文末。

## 任务范围与活动进程保护

| 任务 | 数量 | 本次处理 |
| --- | ---: | --- |
| C-only seed11、29、47与Full seed11 | 4 | 保留原PID、原代码、原GPU、原断点策略，整个worker生命周期不升级 |
| Full seed29、47 | 2 | 通过CUDA准入后使用新回放存储实现与response断点 |
| Static、Manual+、Manual−各三个seed | 9 | 保留原训练实现；新进程设置GPU邻近CPU亲和性 |
| 原dev与机制阶段 | 原完整规模 | 保留原主线实现；所有GPU任务继续限于GPU1、2、3、6 |

四个受保护Student分别是PID2777056、2777057、2777058、2777059，对应GPU1、2、3、6；birth ticks分别为318187132、318187132、318187133、318187133。原父进程PID2769608继续等待并记录真实退出结果。本次没有向这些进程发送信号，没有热修改原冻结工作树，没有改动它们的反馈或保存点。

10月1日00时41分55秒暂停的只有旧的CPU排队调度器PID895990，birth ticks319331700。暂停前确认它没有自己启动的Student子进程，十一项待办仍未创建arm目录；暂停后确认四个原Student identity未变。旧调度器保持暂停，不向它发送SIGCONT，避免两个调度器同时派发。该操作不是暂停Student，也不影响原父进程回收子进程。旧调度器及历史receipt保留，没有删除实验数据。

## 固定数值路径与改变的存储实现

新增六个脚本位于`trusted_data_synthesis/scripts/`，不向参与原`runtime_binding()`的训练包加入文件。原科学实现仍从冻结提交`e99185b657`加载。新执行配置单独登记六个脚本、保留的四个回放辅助脚本、旧队列实现的SHA，以及原科学运行时、材料和launcher引用。不能只报旧运行时ID而隐去执行层变化。

`finqa_v19_optimized_replay.py`在复制的函数全局依赖表中绑定新存储组件，复用原`segmented_logp`、反向分块与prefill checkpoint等函数的数值字节码，不持久修改旧模块的全局变量。SDPA与saved-tensor临时上下文的安装和恢复仍受明确的作用域管理。

具体改变如下。

1. 原token逐步前向的最终KV留在当前GPU，避免完整KV先转到CPU、再按反向块搬回GPU。边界KV仍由原函数构造需要梯度的叶节点，保留完整前缀的伴随量传播，不把历史导数截断。
2. 同一虚拟参数点内跨response复用冻结权重的连续布局缓存及owner索引。每个保存／取回操作仍检查相关张量版本和范围，完整owner检查放在response前后；不再每八个token重复构造所有owner或运行监控线程。
3. 已识别的SDPA K/V保存事件可在GPU上保存独立连续副本，总计同时存活预算固定为2 GiB。每次保存都有独立副本，不做激活去重、不按地址复用旧激活。超过预算的保存事件使用原CPU offload，这是预先登记的存储策略，不是发生OOM后临时切换算法。
4. 参数点完整digest在session建立时计算，response间检查同一参数的存储／版本元信息；参数点变化必须重新创建session。每个response完成后核对缓存中没有残留的存活保存张量。

块长仍为8，token顺序、反向块顺序、prefill路径、Flash Attention、参数dtype、完整误答与EOS token、奖励分母及梯度累加顺序不变。没有改成16／32块、近似梯度、detach前缀、缩短上下文、混合精度替换或跳过正奖励response。没有修改全类G、虚拟Adam、pullback、C、N、π更新与实际AdamW步骤。

以上是实现边界与测试覆盖，不等同于已证明真实模型的所有输入均bitwise等价或都不会OOM。额外的完整KV与2 GiB保存预算会增加GPU驻留量，长上下文的实际峰值仍需观察。

## 完整反馈与response断点

`finqa_v19_replay_state.py`先验证完整cohort、参数点、全部receipt及全部奖励。生产分母固定700；Unknown、缺分数或不完整反馈不能按0处理。仅沿用原算法跳过奖励为0的轨迹，其贡献仍在700分母内，不改成“有效样本平均”。

正奖励轨迹按原episode和turn顺序展开；每项仍执行原`total.add_(gradient, alpha=reward/700)`。每完成16个response及最后一个response，就以不可变目录保存一次累计梯度、计数、cursor、RNG摘要和绑定信息。一个完整response内部不落半个反向图的断点。

保存位置为对应Full分支的`training/replay_checkpoints/<cohort_seal>/responseNNNNNN/`，包含`state.pt`与`record.json`。每个断点绑定执行配置、完整cohort seal、奖励hash、response顺序、实际point与参数digest、块长8及间隔16。恢复会验证文件hash、结构digest、形状、dtype、有限性、cursor与计数、当前恢复RNG；不允许将另一点、另一版本或另一批反馈的部分梯度接上来。

恢复从已提交的response前缀后继续，最多重算15个已经完成但尚未提交的response；中断中的那个response需要完整重算。已提交部分不会重复累加。整个回放已完成时可直接读取完整累计结果，无需再次执行回放。完整700条都为0时保留零梯度与原内核的无信息反馈处理，不捏造回放数量。

原每个optimizer step保存的模型、Adam、RNG、π、训练cursor和outer输入证据继续保留。新执行配置放在原子提交的`record.json`元数据中，不塞进计算状态payload；否则原same-point机制按计算状态比较时，会把纯执行标记误当成算法差异。恢复优化分支时必须使用同一个执行配置；初次分支仍只允许从原seed对应的shared298点创建。

`progress/status.json`在每个完整response后更新，区分本进程已执行数、从断点恢复数、总response数与当前耗时。不可变断点和可变进度不是同一种证据：进度可能比最后durable cursor靠后，不能据此跳过未提交梯度。

## 空卡后的CUDA准入

CUDA检查在新队列中是一项占用单个GPU槽位的任务，优先使用自然释放且仍有至少24576 MiB可用显存的GPU1、2、3或6。它还需等待原C-only seed11首次outer的真实`step0298_outer/outer_inputs.pt`，由原checkpoint验证器读取实际虚拟参数及buffer，不从伪造或近似点构造基准。不会为检查重启当前Student或抢占它的卡。

四个配对用例在启动前，从该原始完整700条反馈中按长度确定：最长prompt、最长输出、总长中位数和最短总长，去重后不足四条时按同一长度序列补足。不按χ、题目得分高低或优化后的耗时挑选。只从原算法需要回放的正奖励response中选取，episode文件和receipt均登记hash。

实际登记的四例prompt／目标token数依次为7499／163、4116／969、4192／106、2634／149。它们来自当前已有的完整反馈，不为制造较短基准重新生成响应。

同一空闲GPU上先运行全部四个原后端用例，再运行全部四个新后端用例。要求logP与全部梯度的内容digest逐项相同，坐标、形状和dtype一致，模型参数、buffer、RNG、模块模式不变，且没有optimizer step；还要求实际进入新的GPU saved-KV分支。仅CPU数学SDPA路径通过不能满足这一条件。

准入阈值为四例优化耗时总和／原耗时总和不超过1.05。这是一次有限用例的非明显退化检查，允许5%计时波动，不是“至少提升某倍”的目标，也不是严格随机交错、多次warmup的性能研究。先原后新的固定顺序可能受缓存或初始化影响，报告必须展示实际逐例时间、峰值与顺序，不能把一次比值泛化成全700条的提速保证。

任何bitwise不一致、未实际覆盖KV驻留、非有限值、OOM或准入失败，都保留真实失败并停止新准入，不自动换后端、缩上下文、重采反馈或重新挑用例。汇总`admitted=true`不足以覆盖逐例矛盾，Full worker会再次核对各个用例。检查尚未完成时Full seed29／47等待；不需要该后端的九个普通分支可按空闲槽位继续。

## 四卡队列与冷恢复

`finqa_v19_queued_scheduler.py`只读观察四个原worker，将它们计入四卡并发数。所有后续训练、CUDA检查、dev及机制任务的有效设备范围均为`[1,2,3,6]`，总数不超过4，显存门槛不降低，原GPU锁继续使用。

新子进程通过已登记hash的`taskset`启动：GPU1／2／3使用CPU`0-37,76-113`，GPU6使用`38-75,114-151`。这是NUMA邻近CPU亲和性，不是独占CPU资源或内存绑定；GPU1／2／3共享同一CPU集合。原`OMP_NUM_THREADS=4`与`MKL_NUM_THREADS=4`保持不变，旧Student的affinity未调整。

当前权威队列目录为：

```text
trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/
  v18_researcher_continuation_01/queued_optimization_01/
    registration/record.json
    controller_restore_settings/record.json
    launch_intent_01/record.json
    launch_01/record.json
    queue/controller.lock
    queue/status.json
    queue/jobs/<job>/adopt001/adoption/record.json
    queue/jobs/<job>/attemptNNN/launch/record.json
    worker_settings/<Full job>/attemptNNN/intent/record.json
    validation/cases/
    validation/result/record.json
```

`run`仅用于首次启动；重启调度器必须显式使用`resume`，复用原profile root和冻结脚本。恢复会根据durable launch中的PID与birth识别仍存活的子进程，不重复启动已有任务，锁文件防止同一新队列双开。只重启调度器不会自动重启Student。

原受保护worker的退出码仍取自原父进程receipt。调度器冷重启后，其自己原先启动的非子进程若已经退出，只能在最终结果通过检查时记录“有durable最终结果、OS退出码未知”；不会把缺失的操作系统退出码伪造为0。没有最终结果的未知退出、没有durable PID的中断launch或已登记数值失败都会阻断并要求核查。

唯一可以自动退回资源队列的情形仍是模型分配前的确切显存准入错误，且没有arm目录；CUDA检查对应要求还没有validation intent。真正开始后的失败不走自动retry。

优化Full worker的恢复入口为`finqa_v19_profiled_worker.py resume-arm`，参数保留原`--output`、seed、`--arm Full`、选定四卡之一及同一个`--profile-root`。原训练checkpoint负责恢复模型／Adam／RNG等状态，新回放checkpoint负责恢复该点的累计gJ。该入口不是数值失败自动批准器：必须先核查失败记录、反馈是否完整、进程是否已经退出和GPU锁／显存。部分700条反馈的分支仍按原规则阻断，不能为凑齐分母重采。已有失败attempt不会被删除或改写；本版不提供不经核查的失败清除命令。

冻结解释器路径、工作目录、环境和完整`run`／`resume`命令另外保存到`controller_restore_settings/record.json`，各次优化worker的settings记录实际恢复checkpoint引用与profile。后续恢复以这些记录为准，不能从可变主工作树直接运行，也不能恢复旧PID895990的派发功能。

## 不变的科学范围

744题／2468包、三个shared298迁移点、原完整十五分支、outer点298／596／894／1192、机制点447／745与终点1490保持不变。每outer仍为完整700条；十五模型×883个dev会话及原机制主线继续复用。public test1147仍关闭，没有新增能力小试、重新裁定、改变χ或重训共同前缀。

本次无外部API调用；协议显式保留`deepseek-flash`政策，不设置模型回退。本地Student已有反馈的回放和CUDA校验不是新的DeepSeek请求。新执行后端的登记不是放宽原反馈或科学准入规则。

## 验证结果与证据限制

35项测试实际通过，用时6.89秒，Ruff通过。测试目录位于被忽略的`artifacts/test_tmp/`，未向正式实验目录写入模拟Tensor或假结果。

| 测试范围 | 实际验证内容 |
| --- | --- |
| CPU微型Qwen回放 | 1／9／17目标token跨块控制；原与新logP及梯度bitwise一致，模型与RNG未变化 |
| 存储控制 | 复用冻结bank、固定块长、无逐块监控线程、独立KV副本及预算；CPU显式注册saved-tensor反向梯度控制 |
| 断点恢复 | 16个response后中断、恢复后精确累加、已提交前缀不重算；拒绝错点、错profile、错reward、改字节或RNG；完整缓存可复用 |
| worker边界 | 只允许排队Full29／47与四卡；执行元数据不改变计算payload；原提交与恢复路径绑定 |
| 队列及准入 | 四个原进程占槽、新Full等待检查、普通任务可派发、无数值重试、冷恢复不伪造退出码；拒绝汇总通过但逐例矛盾 |

CPU数学SDPA会在保存前变换K/V，微型整模型CPU测试本身没有覆盖CUDA Flash Attention的原始K/V驻留分支。因此另外使用显式注册保存张量做CPU存储语义控制，并要求实际CUDA检查证明确实进入驻留分支。这两类证据不可相互替代。

截至这次部署核查，没有对新实现运行实际GPU检查，没有提速倍数、首outer成功、最终dev或VTDO收益结论。四例检查将来即使通过，也只能支持登记的用例与执行准入，不能证明全量运行无OOM或性能稳定提升。

## 磁盘与保留策略

10月1日部署期间`/data1`可用681162133504字节，约634.38 GiB。以现有shared状态文件30637495字节作为粗略代理，十五分支从298到1490的17880个普通step保存文件合计约510.18 GiB，尚未计入outer证据、反馈、dev和其他用户写入；这是容量估计，不是未来实际产物大小。

新断点只保存累计gJ而不是整份模型。若沿用当前C-only seed11这批493个正奖励response的规模，约31个断点／outer，按约10 MB单份估算约0.3 GB／outer；两个Full共八个outer约2.5 GB。若700条都达到32个response，则上界场景约1400份／outer，八个outer约104 GiB。后者是极端容量估计，不是当前任务已产生的数据量。

磁盘余量不能视为整个实验的容量保证；没有为提速删除旧保存点、缩减原保留周期或上传Student Tensor。所有完成的回放断点继续保留，可变progress与大日志不提交Git。若后续空间不足，应保留真实失败并另行决定容量处置，不能悄悄删证据或改变科学保存要求。

## 执行登记与实际启动记录

北京时间10月1日01时54分15秒，执行配置登记为`7cee422a26730584c2992a8ab79c7e6c9470a5fbacec39ad0c1f9ae7a58dc02b`。登记核对十一项arm仍未启动，原材料binding为`4274b700270f2a3995e6ff84dbb6f4be4bd0b153f5e92361b9a43588c45c5dc6`，并绑定旧调度器暂停receipt`ea1acd1c75dbcd6c3759a45b95f45cfc70af7a94f66c0ae9d4695b9a3cc392fa`。

优化代码冻结为提交`305dfcd558`，脚本工作树为`.codex-worktrees/finqa-v19-queued-optimization-20261001`。科学Python包仍从原`.codex-worktrees/finqa-v18-researcher-continuation-20260930`加载。登记之后未热改任何已绑定源码；报告和后续运行receipt可单独提交，不改变冻结代码。

10月1日02时00分06秒，持久新调度器启动，PID2927149，birth ticks321560146。02时01分26秒的只读观察确认状态为`V19_FOUR_GPU_QUEUE_RUNNING`，四个原Student的PID、birth与GPU未变，进程均非停止状态，原父进程继续保留。旧CPU调度器仍为T状态，未恢复派发。

当时待办为11个原训练任务加1项CUDA准入检查；新队列的GPU子任务启动数为0，`failures=[]`。这表示队列已实际恢复运行并等待自然空卡，不表示待办已开始训练。原C-only seed11的首outer完成证据仍未就绪，CUDA检查尚未执行，两个优化Full不能越过该检查。`failures=[]`也不否认先前保留的旧显存准入失败。

| 不可变运行记录 | ID |
| --- | --- |
| 调度器恢复设置 | `89f1f2ecdddce76a49d51706d047e8139c0d511d881f362fbf2f9b46d41d914d` |
| 新调度器启动receipt | `628ec164e304f3c28ac2a33dc72ccc79ede303e1beb7ed331bd70ccce2d3f14b` |
| 四进程与队列定点观察 | `cad9ea562d29bb190db32dbfbd40af7a3291bb5f16446fa80bcb6b4b694992c6` |

代码、测试、报告、执行登记、暂停交接、恢复设置、启动、四项观察接管和定点观察记录提交Git。未提交模拟测试产物、可变status、大日志、Student Tensor或`.env`；没有删除旧实验或断点。
