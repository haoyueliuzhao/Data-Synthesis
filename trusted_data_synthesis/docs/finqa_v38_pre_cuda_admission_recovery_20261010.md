# FinQA V38：CUDA前准入修复与同点恢复说明

日期：2026年10月10日。除明确标注UTC外，本文时间均为北京时间。

## 当前状态与授权范围

本说明编写时，V38尚未启动。新代码的CPU/mock验证不代表GPU生产恢复已经通过；首点的distribution、真实outer提交和SFT1193仍待执行。后续启动、资源等待和实际完成状态应另行补记，并以新运行目录的封存记录为准。

用户针对V37在distribution阶段的GPU准入失败明确要求“修复问题，继续实验”。本次恢复使用独立目录：

```text
trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/
  v18_researcher_continuation_01/v25_training_replication_01/
    production_resume_01/recovery_01/
```

本次只修复CUDA初始化前的资源等待与已完成阶段继承，接续原B剩余矩阵。原V37的`STOPPED_FAILURE_NO_RETRY`、失败原因、退出记录和冻结实现保持原样；V32至V36的历史结果也不回写。新恢复不解释为原失败attempt自行重试，更不通过删除旧`attempt`、`launch`或`run_intent`文件来绕过禁止覆盖的约束。

## 已确认的失败原因

原C-only137、step1192的distribution worker已经派发，但仍在CPU上读取和检查当前点的缓存及封存载荷。此时另一个项目在GPU4建立了计算进程，使该卡不再满足原先登记的完全空闲准入条件。

| 时间 | 已有证据 |
|---|---|
| 22:45:30.376 | 前一`replay_R3` worker真实退出，退出码0；随后distribution于22:45:30.771派发，PID2585007，物理GPU4。 |
| 22:46:06.345 | distribution的`attempt/record.json`落盘，绑定原step1192完整状态和原context。 |
| 22:46:21.673 | `lifecycle/event002674`记录GPU4没有计算进程，free为81154MiB。 |
| 22:46:26 | 只读进程检查显示PID2586067在此时启动；该进程属于同一账户下的ProWorkSim项目。 |
| 22:47:02.378 | `event002678`记录GPU4上已有PID2586067，进程显存22476MiB，设备free为58669MiB。 |
| 22:47:43.135 | `event002682`仍记录该PID，进程显存24714MiB，设备free为56431MiB。 |
| 22:47:48.182 | distribution在模型加载前的二次GPU准入检查抛出`GPU is not fully idle or UUID changed`。 |
| 22:47:53.141 | distribution真实退出码为1。 |
| 22:48:26.099 | 原控制器以`STOPPED_FAILURE_NO_RETRY`结束，全局`active_children=[]`。 |

GPU4在上述历史观察中的UUID始终为`GPU-ae8978c8-5100-933e-78d1-46ed781a8a0e`，与原协议及launch绑定一致。GPU进程列表中的占用者是2586067，未出现本次distribution的PID2585007。结合当前进程的启动时间和可执行文件路径，可将占用明确归于ProWorkSim，而非仅凭显存数字猜测来源。

原worker在报错位置之前刚检查过`not torch.cuda.is_initialized()`；模型加载、峰值初始化、资源采样器和distribution数学计算均在该位置之后。失败记录的`resources`与`telemetry`均为null，该阶段没有`payload`或`result`。这些证据支持“在CPU准备后、CUDA初始化前因外部占卡被拒绝”，没有观察到本阶段产生C、π或optimizer更新。

具体被触发的准入条件有两项：GPU计算进程非空，以及free低于72GiB，即73728MiB。原错误字符串把空卡条件与UUID条件合并，单独阅读字符串无法确定哪项失败；历史GPU观察补足了这一点。

原控制器的GPU文件锁只协调本实验内部的worker，其他项目没有使用该锁，因此它不构成全机排他租约。原生命周期观察将CPU初始化阶段记为RUNNING，检查进程身份、主存和GPU UUID，但不会把CPU准备期间出现的外部计算进程立即视为模型运行资源越界。最终拒绝由worker的二次空卡门正确触发。此次要修复的是对这种CUDA前资源竞争的处理方式，原空卡门槛不降低。

## 新的准入处理

`finqa_v38_admission.py`在原科学阶段开始使用CUDA之前执行有界等待。每次轮询都检查CUDA尚未初始化、原绝对阶段截止时间、停止请求、进程RSS和全机有效可用主存，再观察已登记物理GPU。CPU观测函数返回后、发布READY之前，再检查CUDA状态、停止请求与截止时间，防止较慢的观测调用跨过时间边界后仍准入。

- 物理GPU缺失、UUID不符、主存观测缺失、RSS超限、有效可用主存不足、CUDA提前初始化均是硬失败，不能通过等待或默认值掩盖。
- 仅外部计算进程占用或设备空闲显存不足72GiB进入WAITING。该worker继续持有本项目GPU租约、原参数点锁及worker名额；不退出、不重采样、不创建新的科学attempt，也不占用GPU显存进行“占位”。
- 等待期间不调用模型、不重置CUDA峰值、不改变参数、Adam、RNG、分布或反馈。达到截止时间或收到停止请求必须退出等待路径，不能随后继续加载模型。
- 只有同一登记UUID满足完全空闲条件，且其余边界继续成立，才进入READY并接续原阶段。其他项目的进程不被发送信号或干预。

每次观测原子更新`<新stage>/pre_cuda_wait/status.json`，并保留不可覆盖的`eventNNNNNN/record.json`。记录包含协议、context、阶段、PID及birth、GPU UUID、观察时间、等待起止时刻、累计等待秒数和资源观察。READY以及失败、停止、超时终态仍保留已经发生的等待区间，避免短暂等待在两次控制器轮询之间消失。

评价入口存在等价的CUDA前准入检查。新`finqa_v38_evaluation.py`通过控制接口代理接入相同等待机制，继续调用新实现目录中原样封存的V37生成和评分函数。原V25实际生成、回答封存、九模型评分屏障及评分规则不变；不重新生成已封存的Static137/251回答，不提前查看这两份Static的准确率。

## 已完成阶段与继承边界

本次首点仍是C-only137、step1192，原context ID为：

```text
c5b4ff1eb6feba057306a243866a77a8b7ce5e7e11b22692c3bb59c1305bbe08
```

原point ID为：

```text
c07e70cc25add945f46a87646a237679d093ad26f15cd94a9efc4d0a2a2c402a
```

| 父阶段 | 实际已保存内容 | 已有完成证据 |
|---|---|---|
| shard00 | 186个完整任务、1248个有效训练行的实际CPU梯度 | COMPLETE、资源门通过、退出码0 |
| shard01 | 186个完整任务、1229行 | COMPLETE、资源门通过、退出码0 |
| shard02 | 186个完整任务、1263行 | COMPLETE、资源门通过、退出码0 |
| shard03 | 186个完整任务、1234行 | COMPLETE、资源门通过、退出码0 |
| virtual_point | 实际G、虚拟参数、Adam绑定、原point及封存反馈引用 | COMPLETE、原封存point匹配、退出码0 |
| replay_R3 | 527个完整response的实际累计gJ及最终载荷 | COMPLETE、`complete_replay=true`、资源门通过、退出码0 |

四分片合计完整覆盖744题、1360状态、2468包和4974个有效训练行。**527是本参数点全部需回放的response数量，700是固定反馈轨迹分母**；不存在“还缺173条response”的缺口。V33固定step298补验中的573条response属于另一个参数点，不能用于本次恢复。

首点完整gJ的已有语义摘要为：

```text
28586fe160fdbc16de9a32b8678612bb1aa7d8ea485758bf06a9e7f440a89be5
```

父`virtual_point/payload/state.pt`和`replay_R3/payload/state.pt`保存实际Tensor，后者为10,187,295字节；另有`replay_R3/checkpoints/response000527/`的完整回放断点。这些是可以验证和消费的实际值，不是单独的完成布尔标记。

新`finqa_v38_inheritance.py`登记父、子输出之间的引用关系。原context和父六阶段的协议、内容ID及路径保持原义，新attempt单独写入`recovery_01/`。真实只读继承检查已核对父协议与冻结源码哈希、停止状态、六阶段COMPLETE、真实exit0、完整资源观察、任务覆盖和载荷元数据，得到下述27219/143/143秒继承结果。这是有界元数据与来源检查，不是新的GPU数值验收。

744份梯度Tensor只做存在性、文件stat与对应元数据摘要检查，没有重新读取或计算全部大Tensor哈希。实际`cohort_seal` JSON为149,980,390字节，超过本次64MiB元数据解析界限；登记对其保留stat和原SHA绑定，通过`deferred_feedback_content_verification`明确列为延后内容验证。两个引用指向同一个实际文件，去重后为一项。实际worker在使用父材料和载荷前，仍须执行原内容哈希、Tensor摘要、完整反馈封存、当前状态及同点检查，不能用这次只读检查替代。

首次恢复不重算744题的类梯度，不重放527个response，不生成或重新评分原700条反馈。`distribution`尚未产生成功载荷，因此应从保存的G、虚拟点和gJ执行一次原pullback、C及π复算。

## 首点通过条件与剩余矩阵

恢复次序固定为：

```text
只读核验六个父阶段和原step1192完整状态
  → distribution计算并保存实际C、N、π及outer输入
  → 从真实trainer提交一次outer1192
  → 执行一次真实SFT到1193
  → 验证资源、状态及worker真实退出
  → 开放其余原定矩阵
```

原`step1192_outer`和`step1193_step`在本次登记前均不得已存在；若核验发现状态已前进，不能继续套用本恢复计划重复提交。完成distribution不等于真实outer已提交，完成outer也不等于SFT1193已完成，结果封存不等于进程已经退出。

原B剩余科学剂量保持：5810次optimizer更新、15次outer、8029条终点回答。三个旧反馈点仍是C-only137/1192、Full137/1192和C-only251/894，共2100条旧反馈，必须同点复用；后续12个新点各首次采样700条，共8400条。首点实际提交及SFT计入这些原定剂量，不另做一份重复“正式运行”。

Static137/251原模型和回答继续只读复用。全部九模型回答封存、生成worker真实退出后，才允许原统一评分。后续统计仍区分原A与新B，不能用恢复工程完成替代训练效果或准确率结论。

## 时间预算继承与全局等待计费

原context的`compute_seconds=27045.04046258703`是distribution派发时保存的快照，未包含随后失败worker的142.37239307863638秒。恢复不能直接拿该旧快照作为最终已用时间，更不能从零开始累计。

当前继承实现采用如下保守规则，正式初始化记录将保存输入时间和计算结果：

```text
继承outer已用秒数 = ceil(max(
    父失败记录时刻 - 最早父成功阶段launch时刻,
    旧context计算秒数 + 失败distribution worker寿命
))
继承distribution已用秒数 = ceil(失败distribution worker寿命)
继承全局资源等待秒数 = ceil(父全局等待秒数 + 失败distribution worker寿命)
```

按当前父记录，前两项outer估计分别约27218.706355秒和27187.412856秒，因此继承值为27219秒。distribution和全局资源等待各继承143秒。将失败worker的全部CPU寿命计入资源等待是保守收费，不声称外部GPU占用恰好持续了143秒，也不改写旧队列中等待为0的历史记录。

| 时间预算 | 原上限 | 本次继承已用 | 恢复前剩余额 |
|---|---:|---:|---:|
| 首点outer累计worker计算窗口 | 86400秒 | 27219秒 | 59181秒 |
| distribution阶段 | 7200秒 | 143秒 | 7057秒 |
| 全池外部资源等待 | 86400秒 | 143秒 | 86257秒 |

恢复控制器依据累计未用额度构造新派发的绝对deadline，不重新发放完整2小时或24小时窗口。已经停止且没有worker的间隔不冒充实际GPU计算时间；父失败运行的已用时间不被遗忘。

新控制器对所有worker的WAITING区间与原零租约资源等待区间取墙钟并集，计入同一全局24小时资源等待预算。同时发生的多worker等待不按worker数重复收费，已经结束但两次控制器轮询之间未被看到的短等待，也通过READY保留的区间补记。

CPU等待worker仍占名额和GPU租约，其时间同时进入该阶段窗口与所属outer累计计算窗口；资源等待预算不是延长阶段deadline的理由。CPU初始化、等待和draining均不得从“最多四个总worker”的口径中排除。原600秒draining episode规则继续适用，不能每次轮询重置。

## 资源和科学约束不变

物理GPU白名单仍为3、4、5、7，最多四个总worker、每卡最多一个本实验worker；0、1、2、6不参与调度。CUDA前完全空闲准入仍要求free至少72GiB；真实计算时历史allocated峰值仍不得超过76GiB，规定边界设备free仍至少2GiB。模型加载计入峰值，模型加载开始后不重置峰值。

分片RSS上限仍为160GiB，其余阶段为192GiB；全机有效可用主存至少保留96GiB，使用包含cgroup限制的有效观测，缺失值不能当作0或视为通过。CUDA前等待不放松任何一项门槛。

C-only继续保持`b_N=0`，Full保持`b_N=0.2`。原C指数、温度、历史锚、先验锚、完整轨迹logP、700分母及optimizer数学不改。不得使用V36任务梯度或V33 gJ替代本点材料。新增API调用预算为0；如果未来另行授权API工作，仍须遵守项目的`deepseek-flash`约束。

## 当前验证证据与限制

V38五模块最终联合验证为**76项CPU/mock测试全部通过，用时3.14秒**，覆盖准入helper、继承、worker、评价wrapper和控制器；原V37控制器、worker、评价与训练的**54项回归测试通过，用时4.68秒**。Ruff检查通过。以上采用最终联合执行结果，早期分组测试不再作为额外项数累加。

对应测试文件为`test_finance_v38_admission.py`、`test_finance_v38_inheritance.py`、`test_finance_v38_worker.py`、`test_finance_v38_evaluation.py`和`test_finance_v38_controller.py`。覆盖同点父阶段继承、原成功退出及资源边界、实际载荷消费、首点提交顺序、外部占卡后就地等待、完整等待区间并集计费、原deadline、停止请求、每轮CUDA未初始化检查、观测期间跨越deadline或收到停止后的READY拒绝、设备缺失/UUID变化、RSS和主存门、未知观测拒绝、同worker身份、禁止覆盖已有准入记录，以及原评价生成和评分函数的委托。Unicode进程名测试确认心跳和事件与控制器一致使用`ensure_ascii=False`的UTF-8规范JSON，避免合法非ASCII字段导致内容ID误拒绝。

上述验证只使用CPU/mock，没有运行GPU、调用API或读取当前B的Static评分；临时产物使用已忽略的`trusted_data_synthesis/artifacts/test_tmp/`独立目录。冻结实施清单与正式启动应以随后实际记录为准。CPU测试通过不证明新的distribution、C/π、outer提交、SFT1193或其余矩阵已经完成；旧V37上游阶段的成功，也不追认旧失败attempt整轮通过。

## 关键原始证据

以下链接指向本次恢复前已有记录；文档不是这些Tensor、反馈和原始记录的备份。

- [V37协议](../artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v25_training_replication_01/production_resume_01/protocol/record.json)
- [distribution派发](../artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v25_training_replication_01/production_resume_01/contexts/seed137/c_only/step1192_outer/distribution/launch/record.json)、[失败](../artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v25_training_replication_01/production_resume_01/contexts/seed137/c_only/step1192_outer/distribution/failure/record.json)、[真实退出](../artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v25_training_replication_01/production_resume_01/contexts/seed137/c_only/step1192_outer/distribution/exit/record.json)
- [CPU准备时空卡观察](../artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v25_training_replication_01/production_resume_01/contexts/seed137/c_only/step1192_outer/lifecycle/event002674/record.json)、[外部PID首次出现](../artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v25_training_replication_01/production_resume_01/contexts/seed137/c_only/step1192_outer/lifecycle/event002678/record.json)、[失败前最后GPU观察](../artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v25_training_replication_01/production_resume_01/contexts/seed137/c_only/step1192_outer/lifecycle/event002682/record.json)
- [同点虚拟点结果](../artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v25_training_replication_01/production_resume_01/contexts/seed137/c_only/step1192_outer/virtual_point/result/record.json)、[527个response完整回放](../artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v25_training_replication_01/production_resume_01/contexts/seed137/c_only/step1192_outer/replay_R3/result/record.json)、[实际gJ载荷记录](../artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v25_training_replication_01/production_resume_01/contexts/seed137/c_only/step1192_outer/replay_R3/payload/record.json)
- [原全局停止状态](../artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v25_training_replication_01/production_resume_01/queue/status.json)、[V37实施说明](finqa_v37_controlled_B_resume_20261010.md)
