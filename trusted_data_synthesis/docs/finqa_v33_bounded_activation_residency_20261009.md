# FinQA有界激活驻留性能对照设计与验收

2026年10月9日，用户在获知V32未达到吞吐准入门后明确选择“另行登记一次有界优化对照”。本次V33只验证一个新候选R3：在原R2存储路径上增加有界的非KV保存激活GPU驻留，以新鲜R0为对照；不恢复原B训练，不采样、不重评分、不执行真实Student更新。当前终态为 `STOPPED_FAILURE_NO_RETRY`：GPU7上的四例配对取得1.375889倍加速并通过逐位数值门，随后完成实际response16冷恢复及573条response回放，但独立类梯度与C、π复算后的最终显存验收失败，整轮未通过。北京时间23:16:43的收口核验确认控制器和四个阶段worker均已退出，原B继续暂停，未启动重试或新实验。

V32的终态仍为 `STOPPED_NO_MATERIAL_SPEEDUP`。其R0、R1、R2四例非profiler总时间分别为202.795533375、198.502805174、180.998226056秒，最快R2为1.120428倍，未达到原1.20倍门槛。本轮不改写该结论、旧协议或旧阶段记录，也不把旧R0时间作为新候选的计时分母。完整前序结果见[V32收口报告](finqa_v32_bounded_replay_performance_20261009.md)。

## 授权范围与独立实验目录

新实验唯一输出目录为 `trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v25_training_replication_01/replay_performance_02/`。初始化拒绝覆盖已有目录，登记绑定V32已封存的共同协议、实现字节及未准入收口记录，并保存本次明确授权的问答与范围。原 `replay_performance_01/` 仅作不可改写的证据来源。

原B在 `four_gpu_release_01/` 的状态必须继续是 `PAUSED_BY_USER_CHECKPOINT_SAVED`，没有active children且没有自动恢复授权。新控制器在协议检查、各阶段派发及cohort恢复前核验这一条件；原B不再保持冷暂停时，新性能实验拒绝派发。即使本轮全部通过，也不获得原B恢复授权；正式接续仍需用户另行明确授权，并验证原完整状态与同一feedback参数点。

本轮API、新采样、评分调用和optimizer更新预算均为0。协议保留 `api_model=deepseek-flash` 的明确约束，但实际执行不创建新反馈、不调用provider，也不使用API弥补输入或校验失败。A扩展结果、原B预算、九个Student终点评分屏障均不变。

## 依据与待验证假设

V32的R0单response诊断发现大量细粒度dispatch、同步、复制及矩阵运算事件：约105万次CUDA kernel launch、约10.3万次stream synchronization；Pinned H→D与D→Pinned各约10万次。R2减少部分KV往返后四例耗时降低10.7484%，但仍未准入。该profile包含嵌套范围和诊断开销，不能把它们相加为互斥占比，也不能据此宣称全部瓶颈来自PCIe。

本轮待验证的假设是：在不改变算术和保存张量布局的前提下，将部分非KV保存激活的独立副本留在GPU，可能减少其CPU往返与相关同步，换取额外显存占用。GPU复制、分配、hook及审计本身也有成本，因此不预设必然达到1.20倍；旧profile只用于提出该假设，不进入本轮加速比，也不构成R3成功证据。

本轮只有这个候选和固定16GiB激活预算，不设置预算扫描、候选搜索或失败后的自动调参。新的profile预算为0，不再重复V32诊断。若R3不满足数值、资源或吞吐门，则本轮按实际原因停止，不追加案例、不改门槛、不自动回到R1或R2。

## 唯一候选的存储变化

R3继承R2的完整KV驻留、saved-KV驻留及冻结权重layout复用，只改变不属于冻结owner、也不属于已登记SDPA K/V的保存张量分支。

| 存储部分 | 本轮处理 | 独立界限 |
| --- | --- | ---: |
| 冻结owner及其canonical layout | 复用原实现及变更检测 | 不纳入下述激活预算 |
| 完整KV | 复用R2同设备完整KV路径 | 完整KV估算及实际字节均不超过8GiB |
| saved-KV | 复用原独立设备副本及预算外CPU保存 | live副本最多2GiB |
| 非KV保存激活 | 每次save独立分配同shape、dtype的contiguous设备buffer并复制 | live副本最多16GiB |

非KV分支不保留原view，不复用不同save事件的激活，不做激活去重，不跨response缓存激活。设备副本采用独立contiguous布局，以保持原 `save_on_cpu(pin_memory=True)` 保存及取回的布局合同；复制前后检查源签名，unpack检查副本未被修改。副本释放按真实对象生命周期记账，response边界必须满足live字节和live数量均为0、累计分配与累计释放一致。

16GiB预算是所有嵌套store共享的非KV live预算。某次save在分配前已确定会超过该预算时，直接沿用原生CPU保存路径；这是预登记的存储分流，不是发生OOM后重试。实现不捕获OOM以改变预算、后端或案例；OOM使该阶段及后续工作失败停止。非KV累计复制字节、释放字节、live及peak数量、预算外CPU分流次数与host分配字节分别记录，累计复制量不等于峰值驻留量或PCIe流量。

## 数值和科学协议保持不变

R3通过会话局部的依赖绑定复用原算术函数，仅替换保存张量store；不持久修改旧数值模块，也不创建第三套梯度算法。继承的完整前向、块伴随、prefill伴随、KV边界梯度、类梯度、虚拟参数点、pullback和C与π计算保持原路径。

固定项包括块长8、原prompt及完整生成token顺序、全部112个可训练张量的FP32路径、原混合精度与attention后端、梯度累加顺序及700分母。不新增batching、融合算子、量化、截断、精度转换或长度归一化，不缩减梯度范围。原C/N、先验、训练材料、reward及零奖励跳过规则均不改变。

采样logP检查继续使用 `atol=1e-6`、`rtol=1e-5`。微观候选还必须与本轮新R0的logP及全部112个梯度张量逐位相等，shape、dtype、key一致；单例失败不能被汇总pass覆盖。加载真实完整状态及非空Adam后，模型、Adam、buffer、RNG和mode必须保持不变，不以新建空optimizer的自相等代替实际状态核验。代码复用与CPU检查不是GPU逐位一致的替代证明。

## 固定输入与十次微观回放预算

基准仍为已完成的C-only137 outer298，point_id为 `946a8dacfdd859ee75515ce946589c7832156995956e6e974b44087e54148238`。通过原manifest核验保存的pre-state、G、虚拟θ、原intent、双draw seal、700条episode字节、奖励及顺序；不调用旧collector，不重评分，也不为本轮另建反馈参数点。

原700条轨迹中328条为正奖励，372条零奖励按原规则跳过；实际待回放为573个response、87586个输出token，分母仍为700。案例沿用V32按prompt和output长度中位数事先选择的四格首例，阈值为prompt4123、output140，不根据R3表现重新选例。

| 固定案例 | 原response索引 | episode索引 | turn索引 | prompt token | output token |
| --- | ---: | ---: | ---: | ---: | ---: |
| 短prompt长output | 0 | 2 | 0 | 3648 | 177 |
| 短prompt短output | 2 | 4 | 0 | 2761 | 120 |
| 长prompt长output | 8 | 11 | 0 | 6755 | 147 |
| 长prompt短output | 9 | 11 | 1 | 7021 | 125 |

本轮按R0、R3顺序各运行一个冷进程。每个版本先回放一次同样的短prompt短output案例预热，再按表中原顺序正式测量四例，共2次预热加8次正式计时，微观调用上限为10次既有完整response；不同response仍只有4条。没有新profiling、追加预热、替代案例或自动重测。

正式加速比只使用本轮四例非profiler墙钟总和，即 `新R0总时间／R3总时间`。模型加载、预热、输入核验及其他阶段成本单独入账，不混入回放倍率；也不使用V32旧202.795533375秒作为分母。只有R3数值和资源检查全部通过、且该加速比至少1.20倍，才准入后续唯一一次完整cohort验收。1.20倍是固定工程门槛，不等于耗时减少20%，也不代表统计显著性或全负载收益。

## 显存准入与物理设备约束

只允许物理GPU3、4、5、7。整个V33同时最多1个worker，CPU初始化中的已派发worker也计入；不抢占其他作业，不启动原B。每阶段启动必须设备无compute进程且至少72GiB空闲，经二次核验后绑定UUID。微观R0、R3及获准后的cohort两阶段始终使用本轮首次选定的同一物理GPU；阶段退出后释放设备，若其他作业随后使用它，只等待原卡重新满足条件，不换卡配对。

R3在每个response前计算完整KV估算量，并执行以下额外准入：

`物理空闲 + max(本进程torch reserved − allocated, 0) ≥ 完整KV估算 + 2GiB saved-KV预算 + 16GiB非KV预算 + 2GiB余量`。

同时要求物理空闲至少2GiB，并保留原R2更严格的raw-free完整KV与saved-KV准入检查。allocator中未分配给活跃张量的本进程reserved部分只作为潜在可重用量估算；它不是对碎片、驱动分配或OOM安全的保证。实现不为了占位而申请16GiB空白buffer，不声明所有其他激活、权重和梯度已被上述预算覆盖。

继承的观测allocated峰值上限为76GiB，response边界设备空闲余量至少2GiB；预热与最终类梯度复算也纳入资源检查。上述门是准入和实测验收条件，不是强制allocator上限。记录每例allocated/reserved峰值、整阶段每秒目标间隔的设备占用和利用率、进程RSS以及checkpoint序列化与写入墙钟。设备峰值只按成功样本报告，采样错误单列；不能将采样峰值或GPU利用率均值视为精确GPU计算小时。

## 获准后的单次完整验收

仅在微观门通过后，R3按原700条cohort对应的573个实际response工作序列完成一次完整回放，不重跑一份R0完整cohort，也不使用旧历史8.4868小时墙钟作为同期完整基线。

第一进程必须在第16个完整response完成logP检查、全部梯度检查及一次有序累加后，提交真实累计梯度H₁₆并退出。断点绑定协议、point、参数摘要、cohort seal、奖励向量、完整response顺序、RNG来源、后端版本和源文件字节；控制器在恢复前核验 `response000016/record.json`、state Tensor文件SHA及选择记录。

第二个冷进程必须恢复该实际断点，确认 `restored_completed_responses=16`，继续剩余557个response。缺少断点、Tensor字节漂移或绑定不符时停止，不从0重放后宣称恢复成功，也不重复累加前16条。运行期间仍每16个完整response保存实际累计量；信号handler只设标志，在当前完整response安全边界保存并退出。非登记暂停、超时或失败不自动恢复或重试。

完整回放结束后，实际累计gJ必须与原保存gJ逐位一致。原outer只保存聚合G而未保存1360个类梯度，因此本轮另计恰好一次原始class-gradients重建，用真实pre-state和optimizer独立重建G及虚拟θ；二者须逐位等于原值，重算point必须匹配原封存参数点。随后按原数学路径复算pullback、C与π：pullback逐位相等，C与π完整值相等，同时检查模型、Adam、RNG和buffer未变。不能复制旧C或π并宣称独立验收完成。

全程无真实optimizer.step，cohort回放和类梯度成本属于独立性能验证，不计作原B新训练进展。即使全部通过，也只建立这一固定既有点上的完整一致性与恢复证据，不保证全部未来输入或所有C-only/Full分支已验收。

## 控制器时限与停止规则

累计资源等待上限24小时。两个微观阶段和cohort首16条阶段各限2小时；cohort冷恢复及完整G、C与π验收阶段限14小时。这些是停止上限，不是预计耗时。

阶段超时或收到停止请求时，控制器先向已核验PID、birth及命令的本次worker请求安全边界退出；最多宽限10分钟，之后仍未退出才终止该已核验worker。不处理其他项目或账户进程。OOM、数值失败、绑定漂移、资源超限或阶段失败后停止所有后续派发，不设置奖励0、不更换案例、不降精度、不修改预算、不切换候选。已存在stage launch或attempt、控制器run intent的任务不能悄悄重复；新目录也不能覆盖初始化。

只有数值、资源、吞吐、实际response16冷恢复及最终独立复算均通过，才能记录完整性能验证成功。未达到1.20倍时记录 `STOPPED_NO_MATERIAL_SPEEDUP`，不启动cohort；其他故障按实际错误收口，不将故障重新分类为科学效用失败。

## 实现继承与证据封存

新增实现只有[激活存储适配](../scripts/finqa_v33_activation_residency.py)、[有界控制器](../scripts/finqa_v33_bounded_controller.py)和[测量worker适配](../scripts/finqa_v33_performance_worker.py)。冻结时要求这三个文件来自已提交字节，并复制V32已封存的依赖文件，逐项核验其原SHA；旧依赖及旧实验记录不就地修改。

worker继承V32测量、逐位比较、计时和实际恢复流程，只对已封存源码进行固定位置的AST适配：控制器依赖、阶段白名单、cohort候选枚举、禁用诊断profile及其计数共五处。每种匹配必须恰好出现一次，否则拒绝运行；数值回放和累加函数不重写。R3 session通过新依赖注入，累计梯度函数仅局部绑定新的后端版本元数据，实际耐久checkpoint保持R3身份。控制器为了复用旧枚举检查，只在校验副本中将R3枚举归一到R2，不修改真实断点身份或其他绑定字段。

正式证据包括授权、实现manifest、固定协议、各stage launch与exit、逐case结果、选择记录、实际断点及最终比较；Tensor、大trace、动态日志和CPU/mock夹具不作为普通Git文本产物提交。每轮报告分别保留实际结果、未执行工作和原因，不将前序结果移植为本轮通过项。

## 实现与验证状态

三个新增实现已形成，静态交叉审查覆盖存储分支、显存准入、固定10次微观预算、原B暂停门以及response16恢复绑定。已完成的联合CPU/mock测试为155项通过，用时10.30秒，其中V33后端52项、控制器42项、worker适配9项、旧V32控制器回归52项；六个新增Python实现和测试文件的Ruff检查全部通过。检查覆盖独立副本、生命周期和预算分流、元数据拒绝及worker适配范围；CPU/mock通过不代表CUDA逐位对照、吞吐准入或完整cohort已经通过。

实现从提交 `99d849e235609453d73f8e09b67a0506372deb99` 冻结，协议ID为 `7ad6c31cff714508e137f2d6b50797b34aa56172e6387f568614c760af96c68a`。另在独立CPU进程核验实际冻结副本的worker、控制器、门禁、V33后端及V32/V19依赖导入路径；累计梯度函数复用原字节码，版本元数据为V33，CUDA未初始化。这次冻结集成检查及上述联合测试结果封存在 `CPU_validation/record.json`，ID为 `578480e8a084e7cc787e503e502ad5a3c86345a8e2f714f5a02d28333dccc2fe`。

10月9日10:02:01，独立CPU控制器PID4082504、birth393571678启动，启动记录位于 `launch_01/record.json`。10:02:53观察核验该PID及birth仍存活，队列为 `WAITING_FOR_IDLE_GPU`、待执行 `micro_R0`、active child为空。快照中GPU3、4、5、7空闲量依次为53,421、47,561、53,461、49,765MiB，且各有已有compute进程，不满足无compute进程且至少73,728MiB空闲的准入条件。本实验GPU worker为0，未选定配对GPU UUID；GPU0、1、2、6虽为空闲，仍不允许使用。观察封存在 `observation_01/record.json`，包含当时完整队列快照，不将动态队列文件当成不可变结果。

上述10:02:53观察是启动初期的历史快照，不是当前状态。其后控制器按登记顺序在同一物理GPU7执行R0、R3及条件性完整验收，最终按资源失败规则停止。以下实测收口保留微观通过项、真实恢复与完整回放事实，同时区分最终验收失败及尚需另行授权的后续工作。

## 微观配对实测结果

本轮R0和R3均使用物理GPU7，UUID为 `GPU-ab6e97cc-19e4-64b8-f792-7b6920a45434`。R0于北京时间10:36:23完成，R3于10:40:29完成；每个版本各有1次预热、4次正式既有response回放，没有新profile。逐例结果如下，秒数来自各例非profiler回放墙钟。

| 固定案例 | 新R0秒 | R3秒 | 新R0除以R3 |
| --- | ---: | ---: | ---: |
| 短prompt长output | 56.374714 | 42.456082 | 1.327836倍 |
| 短prompt短output | 37.660111 | 28.649979 | 1.314490倍 |
| 长prompt长output | 56.030031 | 39.155711 | 1.430954倍 |
| 长prompt短output | 47.788432 | 33.538572 | 1.424880倍 |
| 四例总和 | 197.853288 | 143.800344 | 1.375889倍 |

正式选择使用总时间比 `197.85328842327 / 143.8003437584266 = 1.3758888417933697`，对应回放耗时减少27.3197%，超过预登记的1.20倍门槛。`selection/record.json` 于10:40:34选定R3，未使用V32旧计时。四例的logP及全部梯度均逐位相等，shape、dtype、key一致；每例状态未变，两个阶段的模型、optimizer、RNG和buffers核验均通过。以上是固定四例的实测工程准入，不是统计显著性检验，也不是完整训练吞吐或任务效果的结论。

| 固定案例 | R0 allocated峰值GiB | R3 allocated峰值GiB | R0 reserved峰值GiB | R3 reserved峰值GiB |
| --- | ---: | ---: | ---: | ---: |
| 短prompt长output | 42.459 | 31.179 | 42.889 | 33.352 |
| 短prompt短output | 42.289 | 30.594 | 42.889 | 33.352 |
| 长prompt长output | 42.490 | 33.179 | 43.904 | 35.703 |
| 长prompt短output | 43.034 | 33.354 | 43.904 | 37.320 |

R3四例的非KV保存激活live峰值最大为2,920,647,128字节，即约2.720GiB，预算外CPU分流次数均为0；每例结束后的live字节和数量均归零。登记的16GiB是该存储分支的上限，不是实际驻留量，更不是模型总显存上限。R0和R3整阶段每秒采样的设备占用峰值分别为44.4834GiB和37.8818GiB；它们与表中的PyTorch allocated、reserved口径不同，也不代表连续设备峰值。本次观测不能推出增加激活驻留会对所有输入降低总显存。

证据位于本轮根目录下的 `micro_R0/result/record.json`、`micro_R3/result/record.json`、各阶段 `cases/case00` 至 `case03/record.json` 及 `selection/record.json`。两个微观阶段的API、新采样、评分及optimizer steps均为0。

## 实际冷恢复与完整回放结果

`cohort_first/result/record.json` 于北京时间10:51:05记录 `PAUSED_AT_REGISTERED_BOUNDARY`，在第16个完整response提交累计梯度并退出。回放墙钟为568.384823秒，包含point context和checkpoint写入；整个阶段为627.131047秒。该阶段allocated、reserved峰值分别约33.365GiB、38.471GiB。response16断点ID为 `2894490629c8bb4a8bee48fff72dbe88c5e82c03799bffbcd80d92ebd399b8de`，不是在第二进程中从0重新计算后模拟出的恢复点。

第二个冷进程仍在同一GPU7运行。封存的最终progress记录明确为 `restored_completed_responses=16`，随后继续剩余557条；于北京时间16:48:35完成573/573条response并提交 `response000573` 断点。完整回放对应87,586个输出token、175,172个cached forward target positions，跳过原372条零奖励轨迹，分母仍为700。恢复进程记录的回放时间为21,377.271240秒，含35次checkpoint提交，checkpoint写入累计2.061898秒。

这建立了登记response16的实际冷恢复和完整response回放证据，但 `complete_replay=true` 仅表示回放阶段完成，不等于其后的独立G、虚拟参数点、pullback、C、π及资源总验收通过。完整回放证据位于 `cohort_replay/checkpoints/progress/status.json`、`cohort_replay/checkpoints/response000573/record.json`，最终progress快照另封存在 `closeout_01/record.json`，避免将动态progress文件本身作为唯一不可变证据。

## 最终资源验收失败

573条response回放后，worker继续执行登记的独立class-gradients重建以及G、虚拟参数点、pullback、C和π复算。北京时间18:28:36，`cohort_resume` 在冻结的 `implementation/finqa_v32_performance_worker.py` 第663行调用最终资源检查时抛出 `ValueError: observed CUDA memory envelope exceeded`。控制器于18:28:45记录 `STOPPED_FAILURE_NO_RETRY`，不再派发后续任务；累计资源等待为1,763.726141秒。该终态不是吞吐门失败，也不是反馈效用失败。

冻结控制流中的第662行先要求全部最终数值比较成立，第663行才调用资源检查。结合实际traceback，可以判定执行已越过gJ、聚合G、虚拟参数点、pullback、C、π及模型、optimizer、RNG、buffers的比较条件；这属于冻结控制流与异常位置提供的证据。由于异常发生在成功结果落盘之前，最终比较字典没有独立序列化，`cohort_resume/result/record.json` 不存在，因此不能把这一事实记为独立成功结果或整轮验收通过。

最终资源合同同时要求PyTorch allocated峰值不超过76GiB、设备空闲量至少2GiB，但失败时这两个具体读数未被保存，现有记录不能区分究竟是哪一项或两项同时触发。失败阶段按秒采样的设备占用峰值为84,975,550,464字节，即约79.13965GiB；这是设备占用的采样峰值，不是PyTorch allocated峰值，也不是失败瞬间的空闲量，不能将其直接写成“allocated超过76GiB”的证据。现有数据同样不足以把资源失败归因到某一类张量的存储或生命周期。

错误、采样资源与调用位置分别保留在 `cohort_resume/failure/record.json`、`cohort_resume/worker.log` 和冻结worker源码；控制器终止记录为 `failure/record.json`。本轮的 `full_validation_pass` 为false，原始失败分类和阶段产物均不改写。

## CPU封存核验与当前边界

北京时间23:16:43完成的CPU只读收口核验加载最终10,189,983字节checkpoint及原outer数据，核对state文件SHA256、语义摘要、绑定和RNG；CUDA未初始化。最终累计gJ与原实际gJ的逐位内容摘要相等，二者均为 `a75897647fccc988d55edb8e03d7b2bce29d40688390aabbb80d9df41f32c5e5`。这一核验进一步确认已封存的573条累计结果可追溯，并不替代失败的GPU资源门或补写最终C、π成功记录。

收口同时按原登记PID和birth核验控制器及四个阶段worker均已退出，GPU worker数为0；API、新采样、评分与真实optimizer更新均为0。原B仍为 `PAUSED_BY_USER_CHECKPOINT_SAVED`，没有恢复授权。不可变收口记录为 `closeout_01/record.json`，ID为 `1b410399abc5e0d3425dd9344474ef2cbca8434cbe3e413450487b9e45c562c4`。

后续方案是另行登记一次末段显存修订与独立验收：复用已经核验的最终gJ，不重采样、不重评分、不重做573条response，不放宽原显存门，限定修改和复算范围并保留本轮失败记录。用户随后对这一提案明确回复“授权”，新范围单独登记为[V34末段补验](finqa_v34_tail_memory_validation_20261009.md)；不重启V33控制器，不改写本轮失败结果，也不恢复原B训练。
