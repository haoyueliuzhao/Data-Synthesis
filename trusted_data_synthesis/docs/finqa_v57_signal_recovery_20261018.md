# FinQA V57 停止信号排查与断点恢复

2026-10-18，V56 在收到停止信号后退出。用户随后明确要求“尽快恢复任务，同时排查异常信号来源”。本次恢复沿用 V56 的科学目录、协议、父参数点和实际断点；首个新控制目录 `automatic_recovery_01/signal_recovery_01/` 遇到CUDA前依赖导入失败，修正版独立使用 `signal_recovery_02/`。不删除旧停止标记，不把未知退出码补成成功，不重新采样已返回内容。

## 停止原因与信号来源

下列时间均为北京时间，来自实际保存的进程与资源记录。

| 时间 | 已观测事实 | 含义 |
|---|---|---|
| 19:26:42 | seed137 shard01 首次尝试在 CUDA 前显存不足，等待60秒后让渡 | 属于可恢复资源不足，不是本次全池停止原因 |
| 19:45:28 | 同任务在 GPU2 启动 attempt0002 | 自动资源重派已实际发生，不再只是模拟测试 |
| 19:45:58.711 | seed137 shard02 收到 SIGTERM | 比控制器停止标记早约14.46秒，不能归因为该标记之后的停池动作 |
| 19:46:13.174 | 控制器保存 `signals=[15]`、`marker=false` 的终止记录 | 控制器实际收到 SIGTERM，进入既定明确停止流程 |
| 19:47:01.670 | 监督器记录控制器实际退出码 -9，并以 `STOPPED_EXPLICIT_REQUEST_NO_AUTO_RESUME` 收口 | 控制器随后被 SIGKILL；旧自动拉起已终止 |

最初 SIGTERM 和后续 SIGKILL 的发送者没有保存在旧记录中。原监督器没有向控制器发送 SIGKILL 的路径，且本次距离停止记录不足一分钟，不能解释为十分钟停止宽限耗尽。已经观测的科学资源边界通过，记录中没有把本次停止归为 CUDA OOM；这些事实仍不能证明 SIGKILL 的外部来源。

本次按[官方排障文档中的会话日志位置](https://learn.chatgpt.com/docs/reference/troubleshooting#feedback-and-logs)，只读检索了相邻时间内与执行有关的记录，没有找到可归因到这些 PID 的信号发送命令。可读日志不等于完整系统审计；内核日志和系统 journal 访问受限，非交互 sudo 也需要密码。因此不能把信号归因给用户、管理员、Codex、其他项目或 OOM。没有更改系统权限、安装全机追踪器或干预其他进程。

旧队列停留在 `STOPPING` 或仍列出旧 PID，是控制器被 SIGKILL 后未刷新状态；所有旧 worker、控制器和监督器身份已经观察为退出。实际旧终态以监督器收口及退出证据为准。

## 保留的科学状态

| 部分 | 实际保存状态 | 本次接续 |
|---|---|---|
| seed137 feedback | 700题完成，结果、资源与真实exit0均已验收 | 只读复用，不再派发 |
| seed389 feedback | 700题和奖励、结果、资源收口已完整，但缺失worker实际waitpid记录 | 新CPU收尾尝试只读验证完整结果，实际exit0后才开放依赖；旧退出码仍未知 |
| seed251 feedback | 654题完成，下一题turn0已经实际返回，UNKNOWN为0 | 重建原消息与工具状态后接续余46题，不重新调用turn0 |
| seed137 class shard00 | 186题、1248行，包括V55父缓存9题45行；已验收真实exit0 | 只读复用，不再派发 |
| seed137 class shard02 | 22题、173行完整缓存；旧worker明确停止、真实exit1 | 只补该分片其余164题 |
| seed137 shard01与shard03、seed251四分片 | 没有完整新任务缓存 | 按原分配完成剩余任务 |

共有2054/2100条完整反馈、一个未完成episode中的已返回turn、208个完整类梯度任务1421行。类梯度两次原新pass共1488题，剩1280题；seed389原完整同点缓存继续只读使用。余1788次新optimizer更新、12267条评价会话、所有科学剂量及九分支十八快照之后统一评价的门槛不变。

全部7次旧worker尝试均已观察为退出；其中seed251反馈、seed389反馈、seed137 shard01第二次尝试没有实际waitpid退出码。本次用户恢复授权只允许这三个精确旧尝试在可靠状态审计后接续，绝不为它们补写exit0。新尝试仍须独立记录真实退出；不能把本次例外扩展为今后所有未知退出的自动接管权限。

反馈审计封存于 `signal_recovery_preparation_01/feedback_audit/record.json`；生命周期、任务分配与退出审计封存于 `signal_recovery_preparation_01/lifecycle_audit/record.json`；信号时序与追查范围封存于同准备目录的 `incident_trace/record.json`。没有重复扫描完整Tensor，原冷消费者仍在实际使用前核验保存值与绑定。旧未封存任务中的中断行不是梯度断点，必要的重新计算单独属于故障开销，不能声称所有物理forward都零重复。

## 新控制与停止保护

V57 保持原 `automatic_recovery_01/` 为科学ROOT；原protocol、parent、condition、task cache、feedback和分支保存点均不重绑定。控制器、监督器、journal、STOP、收口与信号记录按 `signal_recovery_01/`、`signal_recovery_02/` 分别独立保存。新worker继续在原科学stage下追加递增attempt，绝不覆盖旧attempt。

原V56的96文件科学实施包逐字保留。新包仅包含登记、控制器、信号采集与worker包装四个模块。采样、轨迹概率、温度梯度、R3、任务累计顺序和训练数学仍执行原冻结入口。资源仍是GPU0至7、最多4worker、每卡1个，初始化/等待/draining计入名额；76GiB allocated历史峰值、2GiB边界free、RSS160/192GiB和全机96GiB余量不放宽。

可确认资源不足与可恢复I/O仍按原退避和可靠断点自动接续。新明确STOP或SIGTERM/SIGINT仍终止自动拉起；本次没有通过忽略合法停止信号维持运行。科学ROOT和新控制ROOT同时持有owner锁，避免双控制器派发。

新进程在科学导入和线程初始化前安装信号观察器，由内核`sigwaitinfo`类接口取得SIGTERM/SIGINT的发送PID、UID、si_code，再交给主线程原停止handler。只读取发送方可访问的exe、父PID、birth和cgroup，不读取环境变量、命令行或密钥；`/proc`信息是信号递送后的快照，不伪装为发送瞬间身份。记录失败仍执行停止。SIGKILL无法由接收进程捕获，新采集不能补出历史发送者，也不能保证能归因没有先行TERM的直接KILL。

## 必要核验与实际状态

当前新增28项不同CPU用例已通过：9项信号/包装入口测试、10项控制器生命周期测试、9项登记与剂量测试。实测子进程覆盖真实发送者PID/UID、主线程原handler、默认TERM退出为-15、默认INT的KeyboardInterrupt以及遥测写失败仍停止。控制测试覆盖旧停止隔离、仅精确旧缺失waitpid例外、未知新退出不得自动恢复、双控制路径、GPU lease/attempt继承及临时审计I/O等待；另覆盖监督器异常退出审计失败时安全停止己方遗留worker，原因保留为未知控制器故障，不冒充用户停止。未重复旧全量数学测试。

### 首个新控制入口的实际失败

源提交 `085098d114` 的01控制包于20:11:47启动，控制协议ID `52e142e71d8344f78c42cd228bf7a1d9865b219362d210d2df4f40361a3ff81a`。其新包装入口漏掉原V56 worker环境中的辅助脚本目录，导致 `finqa_v32_same_point_guard` 导入 `finqa_v25_training_replication` 失败；这是本次恢复实现错误，不是未知信号再次发生，也不是显存故障。此前控制器导入核验没有覆盖worker函数内部的全部实际导入链，不能将那次核验通过称为完整worker可执行性保证。

01实际派发12次新worker：389的CPU收尾成功，真实exit0且已accepted，科学调用0；其余11次均有相同ModuleNotFoundError、CUDA未初始化、真实exit1。新增feedback、class任务、optimizer和评价均为0，2054条完整反馈与251的已返回turn0保持不变。为修正该确定实现错误，在核验监督器身份后于20:14:04发送SIGTERM，20:14:10全池安全退出。此次停止发送者是本次维护命令PID3552678、UID1004；新采集器真实记录到该身份，这不能用于解释19:45的历史未知信号。

修正版02恢复原辅助目录，并要求实际解析到的辅助脚本字节与原V56登记依赖相同；`finqa_v25_training_replication.py` 在辅助目录和原V25封存目录的SHA均为 `6be6b697e1517cb87ceb5fc8e33bad73d7affef6e9d9cc8685e88724f019fa05`。96文件科学包仍优先，不把路径别名冒充旧manifest原已登记路径。新增真实worker原序导入预检已通过，未加载parent/model或初始化CUDA。新增三项回归分别覆盖辅助目录、实际包装布局缺失依赖与已成功389不重派。

02只继承01已经成功的389收尾及原两项accepted；19次历史attempt全部保留。11项确定CUDA前导入失败获本次实现修正后重新接续，不被改判成资源失败或删除；原三项历史未知退出例外不增加，科学剩余剂量不变。

02修正版尚待源提交、正式冻结worker入口核验及唯一监督器启动。准备完成和CPU用例不代表科学任务已恢复；实际派发和断点接续将在启动后补充。
