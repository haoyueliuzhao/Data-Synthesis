# FinQA V67：回答封存序列化修复与最后一组生成

## 1. 授权、范围与当前状态

用户于2026-10-22要求“修复问题，此外最后一组是否可以开始生成了”。本次只修复已有回答的运行层封存，并首次执行原矩阵中最后 seed389/C05 的4项评价生成；不新增科学实验、训练、反馈、回放或评价剂量。

- 科学根 `S`：`trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v63_balanced_feedback_repetition_01/`。
- 原V65：`S/early_generation_01/`，20项、6215会话。
- 新V67：`S/evaluation_completion_01/`，独立冻结源码、协议、控制状态、修复证据和资源记录。
- 最后组生成仍是原4项、1243会话；全24项总7458会话不变。
- V67已独立冻结，并于2026-10-22北京时间13:24:59启动。实际派发与CPU修复验收见第8节；不代表全部生成或评分完成。

原六组训练均已完成，最后 seed389/C05 已封存894点、实际训练退出码0，`S/training_barrier/record.json` 已存在。因此最后4项不必等待原20项全部收尾：核验六组屏障及最后训练证据后，可以与旧剩余生成并行。

## 2. 实际故障与保留的证据

V65的 `seal_job` 直接对 `sealed_episodes()` 返回的原生 `Episode` 对象调用JSON哈希。该对象是Pydantic模型，不是普通JSON对象；直接 `json.dumps` 导致 `TypeError`。失败位置在原生回答已封存之后、运行层 `whole_queue_seal` 发布之前。

准备时已有17项作业具备完整原生回答和native seal，原GPU资源检查通过，但真实进程退出码为1，未通过最终运行层封存验收；另3项生成仍运行。17项的“回答完整”不等于“旧GPU worker成功退出”，两者不能混写。

旧 `failure`、真实exit1、原资源报告、native seal、回答文件及冻结源码均只读保留。不得将这次运行层错误描述为OOM、模型回答错误或原数值门失败，也不得把CPU补验收改写成旧GPU进程exit0。

## 3. 修复方式与零重复生成边界

新公共序列化函数先执行 `Episode.model_dump(mode="json")`，再按既定canonical JSON规则求哈希。已有JSON对象与恢复出的原生Episode必须得到同一哈希，不更改回答内容或模型输出。

旧20项由独立CPU修复路径逐项读取、核对原生成绑定、完整回答数、native seal、已结算provider调用、原资源报告及真实退出证据。准备时完整的17项可先修复；旧剩3项仅在原进程实际退出、全部内容已封存后才允许接入该路径。

CPU修复约束：

- 同时最多1个CPU修复child，登记64GiB主存预算；不加载GPU模型，不调用provider，不产生新forward或API调用。
- 只在V67新目录发布修复封存、引用和新CPU尝试退出证据；原回答不重写、不复制、不重新生成。
- 新CPU尝试必须实际成功退出后才可接受；旧exit1继续保留，不伪造旧GPU退出成功。
- UNKNOWN、缺失回答、未结算调用、状态/身份漂移、原资源门失败不能按序列化例外放行。
- 该例外仅覆盖已知 `Episode` 序列化收尾错误，不扩展V66单点梯度诊断例外。

修复后的20项采用只读引用，不能作为新4项注册计划中的可派发任务，也不能裸重跑原全24作业队列。

## 4. 最后组首次生成与身份保持

V67的 `evaluations/registration/record.json` 仅含 seed389/C05 原4项，共1243会话；primary development的883题作业优先调度，其余3项各120题。调度顺序改变不改变各作业内部任务顺序、cohort、角色、draw seed、解码配置或原科学剂量。

生成前核验：

1. 原 `S/training_barrier/record.json` 精确覆盖六组，完整分支记录与894快照哈希保持，原训练worker已结算、活动列表为空。
2. 最后组branch、result、accepted、actual_exit及launch五项绑定相符，298次训练提交、894点和实际exit0保持，资源检查通过。
3. 模型point identity仍由原科学protocol ID与原checkpoint确定；V67控制ID仅用于新控制、资源与修复证据，不替代科学身份。

原 seed389/C05 梯度均值FAIL及误差仍保留，沿用已授权单点继续执行例外；正式梯度和其他数值、状态门不修改。此次不重放830条、不重采样4200条、不重训已完成1788次更新。

## 5. 并发、设备与主存隔离

本次新增最多3个GPU worker，与旧V65剩余最多3个组成 `3+3≤6`；初始化、资源等待和draining均计入各自GPU名额。用户随后明确允许同一物理GPU上运行两个任务，本次仅将新运行层的每卡总上限登记为2，不修改旧V65冻结源码或其每卡1的历史协议。CPU修复child独立受单进程及64GiB预算约束，不占GPU槽，也不能借此增加GPU名额。

用户明确优先GPU0、6、7；资源不满足时按GPU2、4、5、3、1回退选择。每卡采用两个全局独立的EX租约槽：旧V65仍只持原GPU租约目录中的主槽，新V67始终最多占该卡一个次槽，次槽目录固定为原租约根下的 `v67-secondary-slot/`，两槽使用同一UUID哈希文件名。故每卡最多为“旧主槽1＋新次槽1”；即使旧主槽释放后重新取得，也不会出现第二个次槽或第三个本实验worker。V67不复制、解锁、替换或迁移旧worker的租约，未来同类新控制必须复用同一次槽目录，不能另建命名空间绕过上限。

两个槽均须真实EX锁、继承的文件描述符、路径/inode及WRITE FLOCK验证，并持有至对应worker真实退出；CPU初始化、资源等待和draining不提前让出槽。次槽并不保证一定能够同时容纳第二个worker：每次新派发仍须满足实际冻结生成阶段的GPU free至少24GiB、GPU隔离审计及原完整生命周期资源门，不因当前GPU利用率低而放宽显存要求。此处24GiB是GPU实时准入阈值，不能与每个生成worker的48GiB主存启动预算混淆；本轮没有新增或放宽二者。不干预其他项目或旧worker，也不将双槽许可描述成整卡独占。

新控制的主存启动计算额外全额预留旧3项 `3×48GiB` 与CPU修复 `64GiB`，共208GiB；不按旧进程较低的实际RSS抵扣。原全机96GiB有效RAM余量、阶段RSS、76GiB allocated历史峰、2GiB边界free以及阶段准入门保持，不以新拆分降低硬门。

旧17项均为已结算硬终态、不能由旧控制重新派发；旧3项范围与身份须在新派发前核验。对剩余集合异常、旧新身份漂移或未知未返回调用，不以本次修复授权盲目重试。

## 6. 全局封存不是评分或整轮完成

新4项与旧20项采用独立来源，最后只建立明确标注修复路径的24项全局封存证据：20项原生内容、历史GPU退出与新CPU补验收，4项新生成的真实退出及完整结果。

全局汇总不得声称“旧20个GPU worker均exit0”。全24项完整封存后仍只进入等待全局评分状态，本次不读取私人评分参考、不调用评分、不查看局部准确率，不把生成封存完成描述成科学整轮COMPLETE。任何后续评分必须遵守独立的完整24项屏障及原科学评价合同。

用户已撤销此前误发的历史清理命令，本次不删除历史数据或完整断点。

## 7. 必要核验与冻结

131项CPU回归已分项通过：评价/worker30项、CPU封存23项、登记35项、资源13项、控制器/入口30项。覆盖真实冻结 `Episode` 的旧TypeError重现、JSON模式哈希等价、原生回答封存、精确4项/1243剂量、六组训练屏障、最后组实际退出绑定、UNKNOWN阻塞、资源故障分类、合法停止、完整结果零调用复用与CPU派发日志刷盘间隙的孤儿进程处置。

一次集成回归中的两个失败属于新增测试假设错误：一个fixture缺少必需的GPU归属核验字段；另一个把48GiB主存预算误写成GPU门。均在冻结前修正并定向复验，实际运行门始终沿用24GiB，没有发生GPU失败或科学重试。

实施源提交 `f95d74dd62` 已推送远端，独立冻结8文件：binding、registration、runtime、evaluation、worker、sealing、controller、entry。实施包ID为 `653d3a7936ce8564756c8f61c1d0370bbd3b1b604a0aaf36af30b711c3962141`，协议ID为 `92d90941f2757278f94dd3bcdd73af39d1271fb2aa37bf896260aa4efa382a83`。

正式冻结入口实际核验342个依赖，结果PASS，未初始化CUDA、未加载模型或调用provider；另一次实际冷控制器构造确认恰好4个新job、20个旧修复job和已授权的设备顺序。CPU seal冷导入亦确认torch未加载。上述核验不算GPU小试或新增回答，证据分别位于 `frozen_worker_import_verification/record.json` 和 `frozen_controller_construction/record.json`。

## 8. 实际启动与观测

监督器于13:24:59启动，PID203450/birth507109416；控制器PID203516/birth507109451。启动前原V66控制及监督器已真实退出且COMPLETE，六组训练屏障通过；旧V65三个生成worker继续运行，没有向它们发送停止或迁移信号。

| 物理GPU | 原V65 worker PID | 新V67 worker PID | 最后组首次生成任务 |
|---|---:|---:|---|
| 0 | 3597208 | 203941 | development greedy，883题 |
| 6 | 3599779 | 203971 | calibration greedy，120题 |
| 7 | 4144818 | 204192 | calibration random T1/draw11，120题 |

三个新worker均已实际通过CUDA准入并持有次槽目录中的对应UUID锁；GPU进程表同时观察到上述六个进程，证明同卡双任务已经生效，不只是登记或派发意图。剩余calibration random T1/draw29的120题作业等待本控制名额，不能额外启动第4个新worker。

13:27:55实际验收时，最初失败的17项已全部CPU补封存并接受，每项新CPU实际exit0，旧GPU exit1完整保留，新增科学调用为0。CPU当前无活动child，仍待旧控制中3项生成实际收尾后补封存。三个新GPU worker已分别观测到14、14、11次 `after_durable_evaluation_response` 返回边界；这是真实模型返回次数，不是整题数、最终答案数或完整生成作业数。最新已观测资源边界均通过，全部新GPU作业仍处RUNNING，不声称已获得新的准确率或吞吐结论。

队列状态位于 `evaluation_completion_01/queue/status.json` 和 `journal/state.json`；旧三项仍查 `early_generation_01/queue/status.json`。禁止重复启动监督器或旧全24作业入口。首个启动请求位于 `startup_dispatch/`，后续实际验收快照见 `startup_verification/record.json`。
