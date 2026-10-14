# FinQA V45 按阶段实测峰值修订主存准入

日期：2026年10月14日，时间均为北京时间。产物路径以 `trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v25_training_replication_01/production_resume_01/` 为基准。

用户指出“我们的任务应该不需要这么多内存”，并明确要求“修改此问题”。本次在独立 `host_memory_admission_01/` 登记主存启动预算，不再把所有非class阶段的192GiB进程RSS硬上限当成启动时必须全额预留的额度。总worker上限仍为此前授权的5，每卡最多1个，初始化与draining均计入名额。运行时160/192GiB RSS硬上限、全机96GiB有效可用主存余量、GPU资源门、原实验数学和剂量不变。

新版本通过自然阶段边界交接生效。现有V43科学进程和冻结源码不热改，V44原准备和停止记录保留。实现准备、交接启动、新协议启用、实际五worker运行分别记录，不能混称。

## 原因与实测依据

原启动公式为：96GiB全机余量，加新worker的阶段RSS硬上限，再加每个活跃worker“RSS硬上限减当前RSS”的非负余额。活跃进程已经使用的RSS已经反映在系统MemAvailable中，原公式没有把这部分重复相加；问题是它将所有进程未来都可涨到硬上限的极端组合当成了每次派发的必要条件。

22:27三个非class worker合计RSS约23GiB，新增class按原公式要求约809GiB有效可用RAM，当时约696GiB，因此没有派发。809GiB是全池悲观预留门，不是新增任务或当前实验的实测内存需求。23:11当前两个R3与一个训练worker合计RSS约10.71GiB，原新增class门反而升至约821.29GiB；这也说明该数值随现有进程RSS变化，不是固定任务需求。

最初检查V43已完成的三个补片只得到59.89至60.90GiB。完整历史核对表明，该样本不能代表完整类梯度分片：V40完整class分片曾达到124.536GiB。因此本次不把class启动预算降到96GiB。

23:18:50的只读审计扫描原production根及 `recovery_01/`、`recovery_02/`、`recovery_04/` 的直接contexts和evaluations，纳入结果为COMPLETE、资源门通过且实际退出码0的91个阶段。读取字段为 `resources.host.max_observed_peak_rss_bytes`，没有读取模型Tensor、终点回答或准确率。证据在 `host_memory_admission_evidence_01/record.json`，逐项保存结果与退出回执来源。阶段样本可能来自相同参数点的不同分片，不能当作91次独立实验。

| 阶段 | 成功阶段数 | 历史最高进程RSS GiB | 新启动预算 GiB | 原运行硬上限 GiB |
| --- | ---: | ---: | ---: | ---: |
| class完整任务分片 | 44 | 124.536 | 160 | 160 |
| train | 15 | 16.334 | 48 | 192 |
| replay_R3 | 9 | 16.433 | 48 | 192 |
| 终点generate | 3 | 15.402 | 48 | 192 |
| virtual_point | 11 | 29.288 | 64 | 192 |
| distribution | 9 | 29.573 | 64 | 192 |

启动预算统一按“历史最高RSS乘1.125，加16GiB，再向上取整到16GiB倍数”确定。它是有明确余量的经验估计，不是未来峰值的数学上界。不同阶段不能因名称相近而互换预算；四个逻辑class分片统一保留160GiB，不按低峰值补片特殊缩减。

## 新准入规则与原保护

新worker先预留其冻结阶段预算。每个活跃worker继续预留“固定阶段预算”与“进程历史VmHWM按同一余量公式上浮”两者中的较大值，再减去已经占用的实时RSS，余额下界为0。全池另外保留96GiB有效可用主存。VmHWM上升会增加后续派发的预留，不能因当前RSS下降而忘记已发生的高峰。

进程内存读取缺失或无效时，本轮派发拒绝并等待后续正常观测，不把缺失值当作0，也不因退出观测竞态将整池判失败。未知阶段、协议预算或绑定被修改则拒绝执行。原实际运行资源监测与验收仍使用160/192GiB硬上限及96GiB全机余量；新启动预算不是新的运行硬限，超过48或64GiB本身不构成终止条件。

按23:11同一个快照计算，三个活跃非class worker各预留48GiB，新增class门为 `96 + 160 + 3×48 − 10.71 = 389.29GiB`，低于原821.29GiB。这是对同一快照的公式对照，不是已经增派或实现吞吐提升的证据。五worker混合队列仍需逐次通过有效MemAvailable、GPU显存、租约、磁盘及状态绑定检查，不能承诺始终满载。

用户随后补充“GPU2，5应当都可派发任务，此轮修订尽量将这两张显卡利用起来”。GPU范围仍为0至7，新版本把GPU5、2放在前两位，完整优先顺序为5、2、0、4、3、7、1、6；每张物理卡最多一个本实验worker。两卡满足资源门且存在可派任务时优先承接原队列，不迁移现有worker，也不新增科学任务来填卡。原分阶段共享显存准入、76GiB allocated历史峰值和2GiB边界free不变，不干预其他项目。原无实验截止、保留累计耗时、安全断点自动恢复及明确停止后不得自动拉起的合同继续沿用。

## 替换尚未生效的V44交接

V44原 `finqa_v44_supervisor.py migrate` 的PID2823865、birth `441367537` 在此次修订前仍为DRAINING_NATURALLY，尚未创建新科学protocol或launch。23:20:26核验PID、birth、UID和完整命令后，仅向该待生效迁移进程发送一次pidfd停止信号，并确认其实际退出。V44以STOPPED_NO_MIGRATION封存，向科学worker、旧科学监督器及控制器发送的信号均为0，三个V43 worker继续运行。

该停止只替换尚未生效的资源策略，不是科学阶段失败或重试。证据为 `concurrency_five_01/superseded_host_admission_01/record.json`，ID `ab3569b9334a623e6bf43224069c701f1031ad38ab39084d78700333282e1e66`。V44原74文件、准备记录和关闭记录不回写，也不得再次启动原migrate。

V45仍直接继承实际运行中的V43。新交接逐张持有自然释放的项目GPU租约，不向科学worker发信号。全部已派阶段成功封存并实际exit0、八卡项目锁全部取得、全局队列新鲜且为空、同点状态继承预检通过后，才停止身份核验过的旧科学监督器。其监督器和控制器真实退出并保存合法停止回执后，单次初始化V45并启动新监督器。旧attempt、身份或科学状态出现异常则停止交接，不暗中追随或另启旁路任务。

## 实施与核验范围

新实施包保留V44冻结包中全部74个源文件原字节，再增加7个V45入口及策略文件。V43仍是科学父协议；V44只提供逐字保留的实施来源与被替换迁移的停止证据，不能虚构一个尚未存在的V44科学协议。

CPU核验重点覆盖预算映射、上取整与安全余量、实时RSS与历史峰值计账、读取缺失时不派发、第五个worker与同卡限制、冻结协议绑定，以及继承、消费者路由和自然交接停止语义。测试只使用隔离目录，不额外运行科学class、response回放、API、采样、optimizer更新或终点评分。

本次100项不同CPU/mock用例通过：controller、supervisor和inheritance共69项，用时20.71秒；admission、消费者路由与handoff共31项，用时3.09秒。相关脚本和测试静态检查通过，重跑的中间调试用例不重复计数。缺失观测、进程退出竞态、第五槽位、GPU5优先及GPU5不满足时选择GPU2均有覆盖。

81文件候选包的实际CPU依赖核验通过，加载新入口、原V43和cold worker、原V37评价及交接原语，逐一确认来自同一候选封存路径。历史证据绑定和新计划校验通过，23:11样例的新class准入结果为389.29GiB；CUDA未初始化、模型未构造、API及科学阶段派发均为0。正式封存后的核验和启动状态另列如下。

## 正式冻结与交接启动

源提交 `bdcad252f583e56e9a873503bc6b6d280a985531` 已推送。81文件实施包ID为 `c32c3a60ec4b3fa5c943bfa740cf53bdf985d7da7587f664c068ea8058857a6d`，准备ID为 `a027dd7eddd35524a3ed548d5c649e97ec1016b7bc69c94b23f4374a6af9ebd2`。正式包CPU依赖与主存策略核验通过，记录ID `10b3a36d0098d0bc9319657ed0507e13466c5721e5213ca82b07d720c68e5609`，仍未初始化CUDA或执行科学阶段。

唯一冻结 `finqa_v45_supervisor.py migrate` 入口于23:41:10实际启动，PID2911728、birth `441686539`。该进程在自然交接通过后转为V45监督器，不另起第二个迁移或监督入口。23:42:20核验为DRAINING_NATURALLY，持有GPU1、2、5、6、7的项目租约；这些租约不独占物理显卡、不占用显存，也不是GPU2或GPU5已被科学派发的证据。向科学worker和旧监督器发送的信号均为0。

此时V43实际worker为GPU4 C-only389 step894 distribution、GPU0 Full389 step596 R3回放、GPU3 Static389训练。C-only389的R3已自然结束并进入distribution，不再沿用先前“两R3加一训练”的描述。新V45科学protocol和launch均尚未创建，当前旧科学调度仍按V43规则运行；五worker新上限、主存预算和GPU5/2优先序尚未生效。

同一23:42快照的有效可用RAM为733.07GiB，新增class按原公式需要820.05GiB，按新预算则为404.05GiB。该对照明确以“假设新策略已启用”记录，没有旁路派发任务。GPU2与GPU5分别空闲60979MiB和77487MiB，约59.55GiB和75.67GiB，均满足目前最严格48GiB阶段GPU准入；实际派发仍须在交接后重新观测。

启动证据见 `host_memory_admission_01/handoff_started_verification/record.json`，ID `4bd9925c2c4121b1195db74102a09659031c2f29b86257b5048ee311b67cc346`。交接期间查看新 `handoff_01/status.json` 及旧 `recovery_04/queue/status.json`；新科学运行以 `host_memory_admission_01/supervisor/queue/status.json`、当前attempt队列和真实launch回执为准。不得重复运行prepare、migrate或旧V44入口，不以准备完成代替实际生效证据。
