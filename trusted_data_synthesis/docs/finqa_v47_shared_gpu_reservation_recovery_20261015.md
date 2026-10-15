# FinQA V47 共享GPU显存预留与原矩阵恢复

日期：2026年10月15日。本文时间均为北京时间，产物相对路径以 `trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v25_training_replication_01/production_resume_01/` 为基准。

用户先要求恢复任务并申请固定高显存占用，随后明确“资源紧张，开放限制，采取更激进的任务分配占用策略”和“取消任务并发数限制”。本次取消独立的五worker总上限，允许与其他项目共享GPU，按实际可用容量提前预留显存。GPU范围仍为本机0至7，每张物理卡最多一个本实验worker，初始化和退出清理期间继续持有该卡租约。因此八张卡全部可用时可以同时运行八个worker，但这只是当前设备数决定的容量，不是另设的任务总上限。四个逻辑class分片、阶段依赖和原实验剂量不变。

首次登记 `fixed_gpu_reservation_01/` 已因实现错误停止，未增加科学剂量；用户随后明确授权“授权修复后重新启动”。修复版在独立 `fixed_gpu_reservation_02/` 重新登记，继承最新已停止attempt的实际状态与累计时间。第一次失败、错误自动恢复判断及所有冻结文件保留，详见后文。

现有V45已停止，不能继续运行旧监督器、旧交接入口或裸用旧resume。新入口明确继承实际持久化状态，旧失败与原81文件实施包只读保留。资源等待及阶段仍不设截止，保留累计耗时；安全断点自动恢复继续生效，用户明确停止后不得自动拉起。共享GPU上的预留可以减少外部任务取得本进程已经保留的显存，但不提供操作系统级独占，也不能消除外部信号、设备故障或其他进程耗尽剩余安全余量的风险。

## 本次停止与实际恢复边界

2026年10月15日21:20:15，C-only389 step1192的R3回放抛出 `ValueError: insufficient free memory for R3 KV/non-KV residency plus reserve`。这是原R3内部驻留预算检查失败，不是已记录的CUDA OOM。最后资源记录中，物理空闲显存约6.93GiB，allocated约28.54GiB，reserved约36.85GiB，历史allocated峰值约33.18GiB；原外层allocated、free和主存硬门均通过。旧自动恢复分类只识别外层资源门失败，因此没有将该内部预算错误判为可自动恢复。

控制器随后停止其他worker，并于21:21:50封存 `STOPPED_FAILURE_NO_RETRY`；监督器于21:21:52以 `STOPPED_UNSAFE_FOR_AUTOMATIC_RECOVERY` 停止。旧控制器PID3752585和监督器PID3726919均已退出。新恢复授权不改写上述历史终态，也不把任意未知错误归为资源不足。

| 坐标 | 已保存的真实状态 | 本次接续范围 |
| --- | --- | --- |
| C-only389 step1192 R3 | 累计response240，完整前缀和Tensor已保存；日志曾观察到251 | 从241继续至419，剩179条；其中11条曾观察但未封存，必须重新计算 |
| Full389 step894 R3 | 全池停止信号后在response133边界封存，累计目标540 | 从134继续至540，剩407条 |
| Full251 step1192 train | outer1192已经提交一次，真实SFT断点为step1213 | 下一次optimizer更新为1214；不再执行该outer、R3或distribution |

两个R3断点必须恢复原Tensor、累积梯度、response顺序、参数点、后端绑定和RNG，不能以日志计数代替断点。只读继承完整class梯度、虚拟点、700题同点反馈及其冻结奖励。Full251旧阶段尚未完整返回成功，但训练提交已经发生，恢复判断以真实训练账本和step1213状态为准，不重复原outer。

父目录 `actual_final_progress/record.json` 的实际累计进度为10451次optimizer更新、21次outer，剩1171次optimizer更新和3次outer。剩余训练分别为Full251的277步、C-only389的298步、Full389的596步。六个模型和终点回答已经封存，余三个模型共3441条终点回答；全九模型封存后才统一评分。

两个未提交旧outer各有700题已封存反馈，合计1400题只读复用。Full251 step1192的700题已随其outer提交消耗，不能再算作待提交反馈。未来Full389 step1192仍有原剂量内的首次700题采样，API模型保持 `deepseek-flash`。本次恢复不能概括为“所有剩余阶段零新采样”，也不减少原矩阵的科学剂量。

## 共享GPU准入与显存预留

新策略不等待整张GPU空闲，不以其他项目进程存在为由拒绝，也不要求每个worker都取得72GiB。调度器根据阶段的必要显存预算选择当前能够运行的任务，先经过项目GPU租约、UUID、主存及显存检查，再由同一个科学worker尽早建立可复用预留。任务等待不占用另一张卡的worker名额；不得新造科学任务填满设备，也不得停止、迁移或修改其他项目进程。

新隔离控制器的调度轮询由10秒改为2秒，旧控制器和冻结源码不修改。优先顺序继续为GPU5、2、0、4、3、7、1、6，但每次均以实时UUID、租约与资源为准；前面的设备不满足条件时继续检查后面的设备，不以偏好顺序阻塞其他可用卡。

| 阶段 | 原GPU准入free GiB | V47 GPU准入free GiB |
| --- | ---: | ---: |
| class | 28 | 24 |
| train | 32 | 26 |
| generate | 48 | 24 |
| virtual首次采样 | 32 | 22 |
| virtual复用反馈 | 24 | 22 |
| distribution | 24 | 22 |
| R3回放 | 48 | 56 |

除R3外，新经验门使用历史allocated峰值乘1.125再加4GiB，向上取整到2GiB倍数；原reserved缓存高峰不再直接等同必要活跃Tensor占用。这些是经验准入值，不是未来峰值上界。105个成功阶段的元数据证据封存在 `fixed_gpu_reservation_evidence_01/record.json`，ID为 `a5c0dc5a23df30bf8c7b2922fc3ca02cd4c67c3a347c0261380e521fa25f307d`，包含阶段结果和实际退出引用、峰值统计、R3边界观测及原配置绑定，不读取终点回答或准确率。R3必须额外满足原内部预算：成功历史的response前allocated最高约28.559GiB，之后还需16GiB非KV、2GiB saved KV、实际完整KV及2GiB余量。原48GiB入场值不覆盖这组条件，因此R3不能沿用其他阶段的降门公式。

本轮原feedback配置为context_limit24576、max_new_tokens2048；绑定的Qwen模型有28层、4个KV头、head_dim128，KV使用bfloat16。即按prompt与输出合计26624 token估计，完整KV约1.421875GiB。新资源估计取2GiB预期完整KV上界，R3预留块之外保留8GiB空闲目标，包含原2GiB余量、2GiB saved KV、2GiB完整KV和2GiB额外缓冲。原后端的8GiB完整KV硬预算及两个逐response检查不修改，实际调用仍使用实际KV估计；56GiB入场包含CUDA及估计差异余量。R3比旧48GiB更严格，其他阶段更宽松，不能把此次策略表述为所有显存门一律放宽。

预留目标根据CUDA初始化后的真实空闲显存和登记安全余量确定，并设72GiB目标上界。worker内目标固定，实际科学Tensor复用同一预留块，不另起一个占位进程与科学worker竞争显存。GPU的76GiB进程allocated历史峰值、规定边界至少2GiB物理free保持，预分配本身也计入历史峰值，不在模型加载或阶段中途重置峰值。

原经验主存准入继续使用V45冻结证据：class160GiB、train及R3和generate48GiB、virtual及distribution64GiB；活跃worker按固定预算与实际VmHWM上浮值的较大者预留未使用余额。class160GiB和其他阶段192GiB运行RSS硬限、全机96GiB有效可用主存余量不变。取消总并发上限不等于取消这些运行保护。

### 预留块为何可以复用

在本机PyTorch native allocator中，先分配目标大小的块，将其交还给进程缓存，再从同一大块分出2MiB活跃锚点。该锚点整个阶段保持有效，其余空间供原科学计算使用。原代码的 `empty_cache` 调用保持原样；由于该大块仍有活跃部分，完整segment不会被释放给外部进程。PyTorch 2.7.1的[原生分配器释放实现](https://github.com/pytorch/pytorch/blob/v2.7.1/c10/cuda/CUDACachingAllocator.cpp#L2834-L2856)仅释放非split块，本机行为另经下述实测验证。正式worker必须通过实际allocator快照证明锚点位于目标segment，不能仅凭allocated或reserved数字宣称预留成功。

这一策略只调整显存生命周期，不改变模型、数学、dtype、奖励、采样种子或R3后端源码。native后端、分裂设置及segment事实必须符合登记条件；不支持的配置应明确拒绝，不悄悄切换数学实现。分配碎片和科学计算的新峰值仍可能造成失败，冷worker退出也会释放该进程的显存，不能宣称跨进程永久占有。

### 本机小规模行为验证

GPU2上进行了一次2GiB allocator检查，PyTorch版本为2.7.1+cu128。该进程取得本项目GPU2租约，保留原物理UUID，允许同卡已有外部进程；没有构造模型、调用API、执行forward、response回放或optimizer更新。

实际结果为：2GiB预分配释放到缓存后，2MiB锚点复用相同起始地址；调用原 `empty_cache` 后目标segment仍完整存在。另一个1GiB Tensor使用相同segment且reserved没有增加，释放该Tensor并再次清理缓存后预留仍存在。CPU与CUDA RNG均未改变；最后释放锚点后reserved归零，进程退出码0。证据在 `fixed_gpu_reservation_allocator_probe_01/record.json`。

该结果只验证本机allocator行为，不是全尺寸预留、R3数值等价或整个实验成功的证据。正式worker仍须保存自身的实际预留记录、资源历史及原数值验收结果。

## 版本隔离与启动验收

初始恢复针对已停止V45的三个明确坐标和对应失败记录登记。后续自动恢复只能来自本次新协议的顺序attempt，使用真实完整任务、response累计梯度或训练提交状态；未知反馈返回、状态绑定异常、数值失败不能盲目重试。任何人工停止要求优先于自动恢复。

R3的新资源外壳在下一条response尚未forward前读取真实allocated、reserved、物理free、历史峰值及实际KV估计，仍执行原两项容量公式。资源不足时封存类型化证据，不靠任意ValueError文本识别，也不伪造旧外层资源门失败。独立继承检查核对同一worker、参数点、冻结生产者、原数学源码、真实checkpoint及所有字节算式。超过76GiB硬限、设备总容量或固定headroom无法满足的条件停止，不不断冷重试。

可恢复的容量失败也不会立即重新启动同一条件：监督器先等待新的空闲量同时满足所需派发容量，并超过失败时“物理free加本进程reserved”至少4GiB。该4GiB中3GiB用于抵消旧CUDA上下文退出可能归还的容量，另1GiB要求实际改善；等待期间仍响应明确停止，真实等待时长计入下一attempt资源统计。它是有证据约束的资源恢复条件，不是任意失败无限重试。

源码冻结、CPU与必要实际依赖核验、正式协议创建、监督器启动、科学worker派发、预留成功和原矩阵完成分别记录。只有真实launch和worker记录存在后才能称相应策略已经实际运行；准备代码或本机allocator小试不代表科学任务已经恢复。

新版本首次入口依次为：工作区 `finqa_v47_controller.py prepare --source-commit <已提交版本>`、正式冻结包 `finqa_v47_controller.py initialize`、正式冻结包 `finqa_v47_supervisor.py run --root <新根目录>`。这是一次性准备与启动顺序，不是日后再次运行的恢复指令。监督器运行后由其登记安全后继attempt，人工不得重复启动run、重新初始化或重启任何历史migrate。

最终130项不同CPU/mock用例联合通过，用时15.35秒，相关源文件及测试静态检查通过。覆盖取消总并发限制、八卡独立租约、实测主存门、早预留与唯一峰值重置、原数学及checkpoint绑定、两个实际前缀、训练已提交状态、类型化容量证明和停止语义；终点入口还完整模拟了一次生成流程，验证两次检查如实报告CUDA已初始化、模型只加载一次且最终资源报告绑定本worker预留。中间重跑用例不重复计数。此处CPU/mock通过与前述2GiB实际allocator小试，均不代替正式科学worker的实际启动及数值资源验收。

## 首次启动失败与修复

首次源提交 `8b24d9e09c` 已推送，89文件实施包ID为 `706d24e7ea25da3fe84cb2d6bd8196ec29c915cce78e6fcff929a586f1486ae3`，协议ID为 `6330364ea55d14a37aee89bd3a954397bb166dd52cdd711197eda4013834ab84`。正式CPU依赖核验通过后，唯一监督器PID2080363、birth449890817实际启动。随后的失败表明，130项测试没有覆盖新心跳生产者与继承控制器之间的完整格式合同；原模拟夹具仍使用旧schema，因此漏掉了下面的错误。

第一attempt在GPU2派发Full251 step1213 train。worker实际预留31GiB，并验证原 `empty_cache` 后锚点和整块预留仍在。新准入模块发出 `v47_shared_pre_cuda_admission.v1` 心跳，但继承的V43控制器捕获函数仍硬要求 `v39_pre_cuda_admission.v1`，于是于22:29:17触发全池停止。worker在 `before_model_load` 读取到停止标记后退出，没有加载模型或提交训练更新。其allocated、物理free和主存子门均通过，资源汇总为false的原因是合法停止标记，不是OOM。

自动恢复分类又暴露第二个错误：它只看到了train保存状态及合法停止后果，没有先拒绝控制器的身份及策略校验根因，因而错误记录allowed=true并启动第二attempt。此判断保留原样，不能改写为一次正确的资源自动恢复。

第二attempt于22:31:39在GPU2派发C-only389 step1192 R3。当时该卡外部显存占用已经释放，worker实际预留70GiB；同一心跳错误再次触发停止。worker于22:31:47记录SIGTERM，随后完成模型加载与父response240状态读取，在22:33:25仍以response240暂停，22:33:27真实exit1。它没有新增response forward。实际五条原资源观测均通过，历史allocated峰值70GiB，规定边界free最小约8.726GiB。这证明大额预留在该次模型加载中保持有效，但不能证明R3计算或整轮实验验收通过。

为防止第三次重复尝试，助手于22:32:33经PID、birth、UID、完整命令和pidfd核验后，仅向监督器发送SIGTERM。第二worker此前的信号早于这一操作，其handler没有发送者PID，因此不把该worker信号归因给这次监督器停止操作。监督器以 `STOPPED_BY_EXPLICIT_REQUEST` 封存，该状态对应助手的安全停机，不虚构用户曾要求停止。本次没有创建attempt3；监督器、两个控制器和两个worker均已核验退出，监督器OS退出码没有观测到，不能写成exit0。

两次attempt结束后，九个arm的checkpoint路径、SHA和状态摘要与初始快照逐项相同。实际累计仍为10451次optimizer更新和21次outer，剩1171次更新、3次outer、三个模型3441条终点回答。新增API、反馈采样、response forward、optimizer、outer和终点回答均为0。第二attempt重存的response240 Tensor实际SHA与原V45文件逐字一致，均为 `da2c49d7f5f51e1dc0ae33301a28c4def1e90de04451f476804f75763f3478c8`。

收口证据为 `fixed_gpu_reservation_01/closeout_01/record.json`，ID `1d721b807e8bbaa94cdb5347b00328ee081be80a4563cd29f4d1fc5b9a6828ba`，终态为 `STOPPED_IMPLEMENTATION_FAILURE_NO_SCIENTIFIC_PROGRESS`；监督器停止证据见 `operator_guard_stop/record.json`。原helper的actual_final_progress里部分反馈预算字段不能作为新采样授权，本次仍按继承合同保留两旧点1400题反馈和未来唯一首次700题预算。

工作区离线修复包括两项。新的控制器捕获函数明确接受当前V47心跳，同时保留PID、birth、参数点、GPU、阈值、序号及时间区间检查，不通过改写心跳来伪装兼容。自动恢复先校验控制器根因，再要求同阶段存在可核验的实际资源主失败；`TailStopRequested`、`ReplayPaused`等只可作为合法停止后果，不能单独授权重启。回归直接读取首次真实launch和READY心跳，并证明旧方法拒绝、新方法接受；未知控制器错误以及身份、策略或时钟篡改仍拒绝。

## 修复版独立重新登记

用户在获知两次失败及零新增科学剂量后，明确回复“授权修复后重新启动”。新目录为 `fixed_gpu_reservation_02/`，不重启或热改第一次监督器及其冻结包。数学实现仍采用原V45的81个源文件；修订的执行外壳另以新提交冻结。实际恢复父目录为第一次运行的 `attempts/attempt0002/`，继承最新完整断点、phase与outer已用时间及资源等待统计，不退回V45的旧计时值。

重新登记还须核验两次已知心跳失败、助手停止记录、监督器收口和全部注册进程退出，绑定新的用户授权，并证明科学前沿没有变化。C-only389可以只读使用第二attempt实际重存的response240；它与原Tensor相同，但记录ID不同，不伪造为原记录。Full389的response133和Full251的step1213仍保留，原九模型剂量、共享资源策略和无独立总并发上限不变。

修复后的实际元数据预检通过，继承累计资源等待94114秒、C-only389 step1192 outer已用42784秒、Full389 step894 outer已用36192秒，均不设新截止。修复版173项不同CPU/mock用例联合通过，用时15.26秒，相关静态检查通过；该总数包含前述用例及新增真实故障回归，不与首次130项相加。新回归覆盖真实心跳生产与消费、未知控制器根因拒绝、合法停止不能冒充资源主因、新授权与最新父状态及计时绑定。正式启动结果另行记录。

## 修复版启动与实际资源自动恢复

修复源提交 `f4c57232bdf39bb9a32ac9e4142d476aa75d81a6` 已推送。新89文件实施包ID为 `d8313eee822ba047c1feb6cd34b88defd88e498021516ada7413468ad2725fb5`，协议ID为 `fcd1b4b5cfb2dab3a9a758c377cc4334fe3e2bd9dd23473a50777a5c4b9131f3`；正式CPU依赖核验ID为 `3900afd874ac2db3fa2a91eca888fad74870cbdeb7b5fb9b8b1e75c8ab2485b5`，确认实际新控制器拥有修正后的心跳捕获函数。

唯一新监督器于23:01:39启动，PID2143408、birth450089459。最初设备容量不足，控制器正常等待；GPU3随后出现可用容量，23:03:26左右实际派发Full251 train，PID2146839、birth450100133。23:03:32同一worker真实预留26GiB，继承step1213，并实际提交1214、1215两次训练更新。新心跳已被正确消费，没有重复第一次的编排错误。

第一attempt随后在 `after_real_optimizer_step.after_cleanup` 边界观察到物理free为1734148096字节，约1.615GiB，低于原2GiB门。allocated约14.287GiB、历史峰值26GiB，allocated及主存门通过；这不是已记录的CUDA OOM或76GiB峰值超限。不能从此记录推断具体外部进程的归因，实际原因按“规定边界物理free不足”登记。step1215已提交保留，worker真实退出后控制器以原失败终态收口。

本次自动恢复与前一次错误放行不同：新的审计核对控制器确实报告train失败，并绑定这个没有停止信号、实际free_pass=false的worker资源主因。监督器实际创建第二attempt，继承step1215，不重复1214或1215，也不重复outer1192。23:10:47，新train worker PID2163413、birth450144285被派往GPU4；23:10:54真实预留28GiB，继续从1215训练。23:14的观察为RUNNING，实际训练目录已出现完整step1216记录；当前观察到的资源门通过，尚未完成整个训练段。

启动证据见 `fixed_gpu_reservation_02/startup_verification/record.json`，ID `f3408d76c1cf900702a549547dace472822e2c282188d19e5f7542b10ea74303`。实际资源恢复证据见 `fixed_gpu_reservation_02/resource_recovery_verification/record.json`，ID `d7d9a49b289ca7e0c8e75c63f51dd84de499bc1b5a90e267e500051efbc9874b`。固定显存预留不能替代共享设备的物理free门；此次真实停止与跨卡接续表明该安全门和实际断点自动恢复已经执行，不能宣称共享GPU从此不会再受容量变化影响。

最新进度应先看 `fixed_gpu_reservation_02/supervisor/queue/status.json` 指向的当前attempt，再看该attempt的 `queue/status.json`。根目录第一次attempt的失败记录继续保留，不代表监督器停止；23:14时当前为 `attempts/attempt0002/`、GPU4一个训练worker，两个R3阶段仍等待容量。总worker上限已经取消，但并发仍由八卡独立租约、实际显存与主存及任务依赖决定。原九模型和统一评分尚未完成，禁止重复启动监督器或旧入口。
