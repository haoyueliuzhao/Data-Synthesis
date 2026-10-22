# FinQA V69：GPU6空闲后接续GPU0长任务

## 1. 本次授权与精确目标

用户于2026-10-22明确要求“GPU0有其他任务，GPU6空闲后将任务迁移至6”。此前等待GPU0旧seed251/C05剩余6题自然完成的决定已经执行；本次是新的、不同的长任务迁移授权，不回写前次决定。

独立控制目录为原V63科学根下 `gpu0_to_gpu6_migration_01/`。唯一目标是V67的 `step894_dev883_greedy_seed389_C05_b1_draw20260928`，源GPU0、attempt0001、PID203941/birth507110006；源控制器203516/birth507109451。14:11:55只读观察目标完成147/883题，仍在运行。

目标GPU6当前作业为同组calibration random T1 draw29，attempt0001、PID1254401/birth507299393，当时36/120题。本次不抢占或信号该作业；必须等其完整封存、资源通过、实际exit0并被原V67接受后，再考虑迁移。

## 2. 等待与准入

迁移控制先等待以下条件同时成立：

1. 原V67其余三个GPU生成作业均完整接受、真实成功退出，原GPU队列除目标外无待派任务；CPU补封存可继续，不要求旧20份CPU修复全部结束。
2. 源目标和源控制器PID/birth、固定job、attempt、原protocol及plan均保持绑定；不能自动追随另一尝试或未知停止。
3. GPU6没有已观测compute/graphics进程，UUID一致，原生成显存准入free至少24GiB。取得原全局 `v67-secondary-slot/` 中GPU6的EX租约后再次检查；不创建第三套槽位绕过每卡上限。
4. 保守主存启动门为512GiB有效可用RAM，覆盖96GiB余量、六GPU启动预算6×48GiB、V67修复64GiB、V68评分2×32GiB；不按较低实际RSS抵扣。

条件不满足就等待，源GPU0继续工作，不提前停机。GPU6租约只在实际符合准入后取得；保持至交接结束或新worker真实退出。仅持本次控制目录ownerEX与科学根ownerSH，不争抢仍运行的V67 ownerEX，也不向其控制器或其他worker发送停止信号。

这里的“空闲”是迁移准入时的实际观察，不保证其他项目未来不会新占GPU6；不得干预其他项目，后续仍执行原共享GPU与资源门。

## 3. 单次安全停止与原返回保留

取得目标卡准入后，只对绑定PID/birth的GPU0目标发送一次合法owner SIGTERM，并保存发送意图、实际sender身份和原worker内核接收证据。旧资源handler仅设置停止标志；已在进行的模型调用正常返回后，先封存durable return与settlement，再在原安全边界协作退出。

不得SIGKILL目标，不把未知失败伪装成资源暂停。停止后须由旧父控制器实际waitpid确认退出，再核验原worker已不存活、原控制状态为不可自动重派的HARD、job/generation锁释放、全部返回状态明确且UNKNOWN=0。等待实际结算共限600秒，未结算即停止本次交接，不强杀或追加重试。

允许的停止形态仅为与本次SIGTERM接收证据一致的ExplicitStop，或包含该已知预调用暂停的GenerationPreCallPause。旧资源收口可为 `FAILED_OR_STOPPED`，必须保留原义，同时核验无实际资源硬门违规、无未知deferred失败。不能误要求旧暂停进程exit0或资源收口COMPLETE，也不能接受无本次因果证据的任意异常。

原完整Episode、已返回调用及其绑定在实际旧进程退出后形成不可变哈希基线。新尝试只读复用已返回内容；prefix逻辑重构不等于再次执行forward。任何UNKNOWN、原返回改写、模型点/请求/任务顺序差异均阻断接续，不以迁移授权允许重采样。

若目标在发送信号前已自然完成并被接受，记录无需迁移，不建立attempt0002。

## 4. 新尝试与后续评分兼容

新控制器只派发一次GPU6 worker，直接执行原冻结V67 generate入口，不修改原模型数学、native生成、显存管理、合法停止过滤或科学protocol。新的尝试为同一C67 job目录下新建的 `attempt0002`，所有V56/V63/V67尝试别名一致；原generation目录、run、point、checkpoint、config、cohort、draw与任务顺序保持。

本次明确允许在该唯一job命名空间追加新的attempt2派发/launch/真实退出及最终accepted。新worker自然追加尚未生成的内容及原格式result、seal、资源记录；旧attempt1、旧failure、原冻结文件、旧controller journal均不覆盖或回写。其他job目录不作迁移修改。

新父控制器实际观察worker退出码；只有exit0、完整883题、全部provider调用结算、原资源门及旧缓存前缀哈希保持均通过，才追加最终accepted，并绑定本次迁移授权和实际退出来源。旧、冷进程的资源历史分别检查；不能用新进程峰值掩盖旧进程历史。

原C67控制器会保留目标HARD，可能最终以BLOCKED收口；这是本次合法交接后保留的旧控制历史，不将其改写成COMPLETE。新实际接续进度应查本次独立控制目录及目标attempt2。V68已冻结接纳逻辑支持同一job新attempt的真实GPU exit0，能够读取新的原格式accepted；因此最后一组的自动评分不用热改或重启。

## 5. 范围与停止边界

新增同时最多一个GPU worker，旧目标实际退出后才派发，GPU6沿用同一全局次槽；原总并发不超过6、每卡最多两个本实验worker不变。原allocated历史峰76GiB、边界free2GiB、生成RSS192GiB及全机有效RAM96GiB硬门不变。

不增加回答分母、反馈、训练、评分或科学实验次数。明确停止迁移协调器必须停止后续接续；已派发的新child只由本控制核验身份后合法停止，保留其真实退出与返回。任何身份、状态、数值、返回完整性或资源失败均停止本次，不自动重试或换卡。

## 6. 冻结、核验与实际等待

源提交 `00a16b5499` 已推送远端，独立冻结4文件：binding、registration、worker_bridge、entry。实施包ID为 `d83e9d3780b561af2bea2fb3a3ec72c440db3226b71ff2dc852c00ff7ad5be7f`，协议ID为 `3c884498d7fa74aa14786939ef2a697784ab75668c5e9581ee57d381cc49c956`。

69项必要CPU回归通过：登记23项、桥接14项、入口32项。覆盖精确身份/单次信号、真实空闲与租约、原返回缓存不重算、停止形态与来源、旧HARD保留、实际退出、早退子进程证据、禁止重试及追加写入范围。真实源run、缓存目录、资源与native audit字段均与冻结实现核对；只读检查没有暂停或调用模型。

项目Python没有 `os.pidfd_open`，实际发送路径为两次核验PID/birth后单次 `os.kill`，不能宣称已使用pidfd。只新建的CPU测试子进程验证了该路径的kernel `si_code=0`、发送PID及UID1004；该验证没有操作既有实验进程。正式冻结入口核验345个依赖，原V67 worker闭包与冷迁移控制构造均PASS，未初始化CUDA、发信号或执行模型调用。

2026-10-22北京时间14:35:34，迁移协调器PID2727365/birth507532935实际启动。14:36:29观察为 `WAITING_GPU6_IDLE_AND_SAFE_SOURCE`，尚未取得GPU6租约、没有发送源停止信号、没有新GPU worker。此时GPU0目标227/883，GPU6 draw29为113/120；GPU0仍继续原工作。

等待启动证据为 `startup_verification/record.json`，ID `14dbd16905c10e1c05e9f4c40644f22524be9ae06f82bc8307f06f9d8cf507f3`。后续查本目录 `queue/status.json`、`signal/`、`baseline/`、`worker/` 及目标原目录attempt0002；禁止重复启动同一协调器。等待协调器启动不代表迁移已经完成。

## 7. 实际交接：GPU0退出、GPU6接续

GPU6 draw29完成120题、实际exit0并被原控制接受后，协调器于14:38:23发送唯一一次登记SIGTERM。源203941/birth507110006于14:38:26被原父控制器实际waitpid确认exit1，原状态保留EXPLICIT_STOP/HARD_BLOCKED及资源FAILED_OR_STOPPED；内核receipt发送者与本次协调器一致。此exit1是已授权协作停止，不是OOM或数值失败，也没有改写成旧进程成功退出。

停止后的实际断点为235题完整回答、454次已返回模型调用，UNKNOWN＝0。原job/generation锁释放、资源历史硬门及同点请求绑定核验通过，完整Episode、候选、返回、tool和调用记录形成不可变前缀基线。未重新采样已有回答。

新GPU6 worker为PID2731998/birth507551516，原C67目标目录下attempt0002，执行未修改的冻结V67入口。实际CUDA准入已核验GPU6 UUID与同一secondary EX租约，模型加载计入新进程历史峰；没有使用旁路新槽位。

14:41:17验收时，新进程已观察到12次实际新模型返回，完整回答由235推进到241，最新实际资源边界通过；旧GPU0身份已退出，本实验不再占用GPU0。GPU7旧seed389/C1仍继续，V68仍保留四组已接受评分并等待剩余完整组，没有对其他worker/controller发送信号。

实际交接证据为 `handoff_verification/record.json`，ID `78a3dbd717d1900ae32a88ed283db415912b1cd6666c9bb7111ebfa7e0d9ec80`。当前状态为 `RUNNING_MIGRATED_TARGET`：迁卡已生效，但883题完整生成及新worker最终exit0/accepted尚未完成。最终原返回前缀、实际新增调用数量和完整结果还会由已冻结桥接器在真实退出时核验；不能将本次启动验收当作整项生成完成。

后续进度必须合并V69新worker，而不能只看旧C67 journal中的HARD：旧状态是保留的交接历史。未来原C67可能因此BLOCKED收口，不表示GPU6新worker已停止；应以本次独立队列与实际attempt0002结果区分。完成后V68自动评分接纳同一job的新增accepted，无需重复生成或重启评分。
