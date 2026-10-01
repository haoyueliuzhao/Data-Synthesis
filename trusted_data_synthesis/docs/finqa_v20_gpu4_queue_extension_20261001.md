# FinQA 新增GPU4与五卡队列

后续更新：用户又将GPU0纳入，现行六卡队列和混合版本恢复规则见[新增GPU0与六卡队列](finqa_v21_gpu0_queue_extension_20261001.md)。新权威状态是`six_gpu_queue_01/queue/status.json`；本五卡调度器只继续回收既有子进程，Full seed29仍保留本版执行profile。

用户于2026年10月1日要求“增加GPU4为可用，调整排队任务”。本次仅将排队任务的有效设备从GPU1、2、3、6扩展为GPU1、2、3、4、6，总并发上限从4提高为5。原四个Student不迁移、不重启；数据、训练算法、outer反馈、回放实现与断点规则不变。V20是资源配置的后继版本，不是新的科学实验。

21时06分的只读资源检查显示，GPU4为A100 80GB，可用48815 MiB，另一项目进程当时占用32330 MiB。因此新增设备不表示GPU4独占或完全空闲；本次不向该进程发送信号。显存准入仍至少24576 MiB，并保留原GPU锁与加载前复查。该门槛不是整个outer或任意上下文都不会OOM的保证。

## 新队列及执行顺序

| 范围 | 执行规则 |
| --- | --- |
| GPU1、2、3、6上已有四个Student | 继续原进程和原代码，计入五个并发槽位 |
| 新增GPU4槽位 | 优先执行已登记的四例CUDA回放等价性及耗时检查 |
| 尚未启动的Full seed29与47 | 检查通过后按原顺序派发，先seed29，再seed47 |
| Static、Manual+、Manual−各三个seed | 保留原训练代码；在合法空闲槽位接续 |
| 后续dev与机制阶段 | 复用原完整主线，同样限定这五张卡、最多五项并发 |

检查占用一个真实GPU槽位，不另开第六个进程。只要GPU4维持准入条件，就无需等待原四个分支全部训练结束才能开始该检查。其他普通分支不依赖新回放后端，但也不能越过显存、GPU锁、全局并发数或既有失败策略。

GPU4的NUMA节点为1，新子进程使用CPU亲和性`38-75,114-151`，与GPU6相同。该设置不是CPU独占或内存绑定；原四个Student的CPU亲和性不变。

## 冻结代码与配置继承

新增单个资源包装脚本`finqa_v20_five_gpu_queue.py`。它复用V19的worker、CUDA检查、PID与birth冷恢复、退出记录和完整主线；只替换资源配置加载器，以及含硬编码四卡上限的派发入口。没有修改六个V19源文件、原V18恢复脚本或原科学Python包。

V19执行配置`7cee422a26730584c2992a8ab79c7e6c9470a5fbacec39ad0c1f9ae7a58dc02b`保持不可变。新登记逐字段继承原协议，仅允许变更设备清单、并发上限、GPU4的CPU亲和性及调度器交接信息，并绑定新增脚本的源码SHA。原运行时仍来自冻结提交`e99185b657`；新增包装器另行冻结，不热修改活动工作树。

注册前要求十一项arm仍未创建目录，旧V19队列没有启动新worker或CUDA检查。本次不是将已经生成部分反馈的优化分支改绑到另一个profile，也不跨版本拼接累计梯度。后续worker和断点显式引用新的资源执行profile，父profile引用一并保留。

## 不变的CUDA准入与失败边界

仍使用原四个固定响应，来自C-only seed11首outer的真实参数点与已经封口的反馈；不重新选样、不调用API、不生成新反馈。逐例要求logP和梯度bitwise一致、状态不变、实际覆盖GPU saved-KV路径，四例优化耗时总和／原耗时总和不得超过1.05。

GPU4与其他负载共享时，计时可能受竞争影响。本次不因此放宽阈值、重复挑选基准、假定提速已经成立或启用后端回退。CUDA检查失败或发生实际数值错误时，保存失败并停止新准入，不向其他仍在运行的Student发送信号；只有原规定的模型分配前显存不足可以回到资源等待队列。

本次扩容不修改每outer固定700条、固定块长8、2 GiB saved-KV驻留预算及每16个完整response提交累计gJ断点的设置。原每个optimizer step的模型、Adam、RNG、π、日程游标保存继续执行。不删除既有checkpoint、不重采部分反馈。

## 调度器交接及恢复

旧CPU调度器PID2927149在确认没有自己启动的Student子进程后暂停派发。原Student PID2777056、2777057、2777058、2777059及其父进程PID2769608继续原地运行。更早的CPU调度器PID895990也保持暂停；两者都不能恢复派发，否则可能与新队列冲突。

新的权威状态与恢复记录位于原V18目录下：

```text
five_gpu_queue_01/
  dispatcher_pause_intent/record.json
  dispatcher_pause_receipt/record.json
  registration/record.json
  controller_restore_settings/record.json
  launch_intent_01/record.json
  launch_01/record.json
  queue/status.json
  queue/controller.lock
  queue/jobs/
  worker_settings/
  validation/
```

首次启动使用新冻结脚本的`run`入口；调度器冷重启必须使用同一profile root和`resume`入口。完整命令、解释器、工作目录、环境、源码提交和锁文件路径保存在`controller_restore_settings/record.json`。恢复继续按durable launch的PID与birth观察存活worker，不因调度器重启重复启动Student。已记录的数值失败需要核查，不会自动恢复为可重试状态。

优化worker仍使用`run-arm`／`resume-arm`入口；GPU4在新资源包装器的CLI许可范围内，但其他GPU0、5、7不被此次授权覆盖。真正的回放、原训练提交与恢复字节码保持V19实现。

## 必要验证与结果边界

18项新增CPU／mock控制与16项相关V19队列及worker控制，共34项通过，用时3.21秒；Ruff通过。覆盖仅新增GPU4与一个槽位、四个原worker占槽时只允许新增一个检查任务、显存不足保持排队、拒绝GPU0／5／7和第六项、固定检查优先级、两项Full的路由，以及拒绝借资源扩容修改数值算法、断点频率、显存门槛或失败策略。

测试使用忽略目录`artifacts/test_tmp/`，没有启动真实子进程或GPU计算。实际CUDA运行及五卡状态以随后保存的启动和观察receipt为准，CPU通过不代表GPU检查通过。新增算力也不等于整体耗时固定缩短20%，尤其GPU4不是独占设备。

## 实际交接与启动证据

北京时间21时17分47秒，仅暂停旧CPU调度器PID2927149；四个原Student的PID与birth均匹配，原父进程未改变。暂停receipt为`0878e0ca17b3683d382086d234d29dfd7636b58c9a18186b2a6e75e425b44afd`。

21时18分07秒，新执行profile登记为`7f9855f0b7243be081070a9ac3b62c48123fed705e624edfdad5a299cec5eae9`。资源包装器冻结提交为`e3b342a90d`，独立脚本工作树为`.codex-worktrees/finqa-v20-five-gpu-20261001`。旧V19脚本及profile没有回写。

21时21分28秒，新持久调度器启动，PID4143342、birth ticks328528332。随后在GPU4启动CUDA检查，PID4143556、birth ticks328528629；其实际加载前检查在21时21分34秒记录空闲81151 MiB，GPU4没有其他已观察到的进程。这与21时06分的占用快照不同；本次未向原GPU4占用进程发信号。

21时24分17秒的定点观察确认：状态为`V20_FIVE_GPU_QUEUE_RUNNING`，许可设备为`[1,2,3,4,6]`，并发上限5；四个原Student及其父进程未变，GPU4上的检查进程存活，五个活动槽位齐全。队列仍有十一项原训练任务，尚未新启动Full分支；`failures=[]`。实际GPU进程查询也观察到检查进程已分配GPU4显存。

该观察时CUDA检查结果尚未生成，因此这里只确认五卡调度和真实检查启动，不宣称等价性已经通过或获得实测提速。检查通过后会自动接续Full seed29；如果检查失败，则遵守原失败保存与停止新准入规则。

| 不可变运行记录 | ID |
| --- | --- |
| 完整恢复设置 | `aa1f1ecdc72ae90222fdd835521cac42007360c33a095d30e97bb431fb633de3` |
| 新调度器启动receipt | `30e0bf6b7a855283166316750557c7303e697f205f4268fb9d89fcb12ca91cb5` |
| 五卡运行观察 | `fa5a18250073f74b1c13f397199909dbda8e569dcbda710dc9017446f2b4ed77` |

源码、测试、说明、登记、交接、恢复、启动、四项观察接管、GPU4任务launch／validation intent及定点观察记录提交Git。实时status、大日志、模拟测试产物和Student Tensor不提交；既有四卡登记、旧启动证据和原数值结果保留，没有删除原实验或断点。
