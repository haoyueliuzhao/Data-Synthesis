# FinQA V60 账户级定时守护与独立冷恢复

## 本次授权与目标

用户在2026-10-18要求恢复实验、限制异常SIGTERM对本实验的影响，随后明确询问“能否设置自动恢复，或者你定时检查恢复任务”，并要求不与yyy账户任务共享GPU。本次使用原账户UID1004的服务器cron，计划每分钟执行一次实验专用检查；不用sudo、口令或全机服务变更，不改其他账户的任务。

主目录独立为 `automatic_recovery_01/automatic_control_watchdog_01/`。初始只监视已运行的V59 `signal_recovery_04/`，不停止它、不迁移它、不重启其一次性入口，也不改写V59六文件冻结包或科学原始协议。V59的窄SIGTERM来源规则、yyy同卡禁用、最多4科学worker/每卡1、资源硬门、科学剂量均继续适用。

已查阅 [OpenAI官方定时任务说明](https://developers.openai.com/training/walkthroughs/scheduled-tasks)。本轮没有创建聊天端托管定时任务，也不把聊天窗口或模型持续在线当作服务器守护。定时检查和恢复由服务器上被冻结、可审计的固定代码执行。

## 能保护什么，不能保护什么

定时守护解决的是“监督器与科学进程一同退出后，没有进程能自行拉起”的空缺。它不阻止宿主机root发送SIGKILL，也不能保证cron服务、文件系统或整台机器持续可用。把实验改成root运行不能提供此保证；本次没有这么做。

V59已过滤其他UID的SI_USER SIGTERM，但保留UID1004的SIGTERM、所有SIGINT和明确STOP；V60继承该边界。对手或管理方若有宿主机权限，仍可强制停止、禁用调度服务或修改系统策略。真正的管理权限隔离需要权限受控的独占环境，不能通过本实验代码假装实现。

**要主动停止实验及自动恢复，必须使用登记的STOP入口，不要仅依赖kill -9。** SIGKILL无法提供发送者回执，定时守护可能把没有持久停止意图的消失按授权恢复类别处理；不能在这种情况下自动知道是谁主动停止。

## 恢复准入

健康巡检只读轻量队列和本实验PID/birth，不重扫反馈、不重哈希Tensor、不重复任务审计。任何已派科学worker（含CPU初始化、资源等待或draining）、controller、supervisor或启动runner仍活着时，禁止启动第二个科学池。

仅在以下条件全部满足后，才登记一个新的冷恢复episode：

1. 所有已登记的科学与控制进程身份均明确退出；不完整、不可读或不一致的身份信息只能等待或阻断。
2. 没有当前episode的owner TERM、任意INT、STOP、未知反馈、哈希/状态/数值失败或已知实现异常。
3. 原科学owner锁与八个项目GPU租约能以all-or-none方式全部取得并立即释放；不扣留卡促排空。这只是本项目进程退出条件，不是GPU容量准入。
4. 原逐job断点审计确认同科学状态、零UNKNOWN、已accepted结果有效、任务与提交顺序连续；已完成工作不丢弃，不重采样或重复提交。
5. 原资源等待及工作量统计继承；新进程仍执行原显存、RSS、有效RAM和yyy归属准入。

恢复类别严格区分：真实父进程waitpid记录的−9可称 `CONFIRMED_SIGKILL`；只有身份全部消失但没有真实退出码时称 `ALL_IDENTITIES_GONE_EXIT_UNKNOWN`，退出码保留None、原因未知。后者是本次用户新自动恢复要求下独立登记的许可，不回写V59以前的未知退出，也不等于未知科学错误获准重试。

完整任务、累计response梯度及训练提交断点继续复用；未封存计算可能重做，须作为故障开销而不是新增已提交科学剂量。当前三组2100条反馈已accepted，没有重新发放采样预算；原1788次新增optimizer更新与12267条登记评价会话仍按原协议完成。

## 独立episode与启动事务

每次恢复使用 `episodes/episodeNNNNNN/` 的新协议、prepared与控制记录，科学数据仍在原V56稳定目录。所有科学attempt序号连续，旧停止、未知退出和失败均保留。

每次cron检查有互斥锁；恢复请求、CPU审计、登记和派发意图分别持久保存。已经完成的同一异常episode审计只做一次。进程创建调用只有一次；如果检查进程恰好在创建子进程后中断，下次只能依据真实启动回执或明确的“未创建子进程”证据协调，不能因为没看到返回值就重复Popen。创建结果不明时永久阻断，要求人工核对。

单一非科学runner启动一个supervisor和一个只读observer，并记录实际waitpid。runner也被终止时仍保持未知，不伪造退出码。runner和observer不做模型/API/GPU工作，不增加科学worker并发额度。

旧只读observer不占科学名额，但不能无限积累。仅在全部科学与控制进程退出后，才可按PID/birth核验，对本账户、被注册为纯CPU只读的旧observer发送一次维护TERM并确认其退出；只记录在新维护证据中，不修改旧记录。新episode最多保留一个独立observer，观察器维护停止不冒充用户停止科学实验。

## 停止与终态

明确STOP、owner TERM或任何INT、未知反馈、状态/数值/源码绑定异常以及已知实现错误都会建立持久终止屏障。后续cron仍被触发时也不得恢复。解除屏障或改变科学/资源合同，需要用户新授权；不能自动删除停止标记或换目录绕过。

完成整轮并通过原统一评价的终态也不再派新任务。仅移除cron条目是关闭未来外层检查，不应偷偷终止当前正常科学worker；明确stop入口则应同时停止自动恢复和当前受绑定episode。

## 账户级配置与隐私

只读检查确认服务器cron服务运行、当前账户可使用crontab；当时账户尚无crontab。`systemd --user`可用但Linger未开启，因此本次不通过修改全机登录策略来获得常驻能力。

安装时必须新鲜读取并逐字保留本账户其他cron行，防止覆盖之后新增的任务；只增删本实验的精确标记行。旧配置备份仅本地0600保存，不打印或提交Git。定时日志、心跳与信号回执有容量限制，不按每分钟创建无界目录；候选root进程日志仍仅本地保存，不上传。没有收集其他项目的环境变量、完整命令行或私有文件。

## 核验与实际状态

已完成55项不同CPU/mock用例：守护状态机21项、登记与实际后端17项、cron入口12项、控制/观察适配5项。覆盖活池不接管、owner停止与未知反馈阻断、原锁文件不创建/不替换、派发意图协调、未观察到子进程创建结果的阻断、早期PID/birth回执、半登记幂等、逐job审计复用、cron配置并发检查和实现异常持久禁止恢复。修订后只重跑受影响用例，没有重复运行数学或反馈审计。

另一次真实只读healthy observe识别出4个活跃身份，无终止理由，没有导入Torch或创建master；pidfd兼容实现仅对测试自身进程执行open/close，未发送信号。没有实际中断科学进程验证恢复，不将CPU/mock通过等同于真实故障后的端到端恢复成功。

源版本提交时尚未安装cron，没有创建新的科学episode或启动runner。随后按以下顺序完成正式冻结与实际激活，V59原任务没有因准备守护而暂停。未通过杀死正在运行的科学任务来测试自动恢复。

### 正式冻结与真实激活（北京时间2026-10-19）

- 源提交：`72d4259d514b04fd46f6bdad5682eb088db2c6b4`。
- 13文件实施包：`341cc51eadf55b3fb390ac1285de78c1d937c86b532660ecff8f1dbceb35df3f`；原V59六文件逐字保留。
- 主协议：`3348cfe262cfdd12c6e4fb74b5b926d4845dc64301e4d3259df3261494f25b3b`；prepared：`536aafbaba2b63433ba5e85164fa2105da32e4f7be3cf38d9931d97cbd0e6925`。
- 冻结入口实际执行 `check-imports` 返回exit 0、`CPU_IMPORTS_VERIFIED`，原科学导入闭包通过且CUDA未初始化。核验回执 `cpu_verification/record.json` ID `4bc4af9c6d0b356fd5a89db3bbc11100caa4508653bb64b88fdee73fdff0cdf7`。完整导入结果只在内存返回，入口stdout只含结果ID；回执如实记录该限制，不虚构完整原始报告。
- 00:35:09手动巡检为 `WATCHING_LIVE_EPISODE`，未创建新episode或恢复请求。
- 00:35:31安装账户cron并逐字核验配置；00:36:01已观察到首次真实自动触发。00:37:01的后续自动触发被封存，实际进程祖父为 `cron`、父进程为 `sh`，执行UID/eUID均1004，不是由手动调用冒充定时激活。
- 00:37:04激活证据为 `activation_verification/record.json`，ID `0fc69d0e608509b561bca7ea61004a1b1b3a79a435297eb65396eba1f1aea14e`，状态 `ACTIVE_WATCHING_EXISTING_POOL`。真实cron心跳、当前轻量队列和最近完整资源边界一起封存；本地crontab原文备份、候选进程日志、Tensor和反馈不提交。其中installation是省略本地备份字段的摘录，其id标识原安装记录，不应把该摘录当成另一份完整安装记录单独重算id；完整安装记录仍仅在本地cron目录。

激活快照时原supervisor/controller仍为3878725/3878874，科学worker如下。它们由原V59控制器正常派发，不是V60新池：

| GPU | 作业 | attempt | PID |
| --- | --- | --- | --- |
| 2 | seed137.shard01 | 6 | 3879170 |
| 1 | seed137.shard03 | 4 | 3942008 |
| 0 | seed251.shard01 | 2 | 3973689 |

三worker最近完整资源边界均通过，yyy UID1000排除和归属可判定条件均通过。此为观测时刻证据，不是整台GPU永久独占承诺；外部项目之后自行进入同卡的瞬时窗口不能由本账户彻底消除，运行中检测到冲突后只让本实验按原安全边界退出/等待，不干预对方。

原队列此时有5个accepted job，包括三组已完成反馈和seed137的shard00、shard02；其余任务继续，评价尚未登记。V60未创建恢复请求、后继episode或runner，未退休原observer，未发送科学进程信号。**每分钟定时观察已经实际生效；真实异常后的冷恢复仍未发生，也未做破坏性端到端演练。** 不据此宣称已完成实验、已得到准确率、已防住SIGKILL或已解决未知信号来源。

## 查看、停止和移除

以下命令从仓库根目录执行，变量只用于缩短固定冻结路径：

```bash
FINQA_V60_ROOT=trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/automatic_control_watchdog_01
```

只读查看账户任务是否安装（不启动恢复）：

```bash
trusted_data_synthesis/.venv/bin/python "$FINQA_V60_ROOT/implementation/finqa_v60_cron.py" check
```

真正需要停止实验及自动恢复时，使用下列命令；它先持久禁止未来恢复，再向当前及待接管的已绑定episode写STOP。命令返回不代表worker已经全部退出，仍应查看原队列安全收口：

```bash
trusted_data_synthesis/.venv/bin/python "$FINQA_V60_ROOT/implementation/finqa_v60_cron.py" stop
```

仅关闭外层定时检查、但保留当前科学任务及其原监督器时，使用 `remove`；它只移除本实验精确任务行，保留本账户其他cron行：

```bash
trusted_data_synthesis/.venv/bin/python "$FINQA_V60_ROOT/implementation/finqa_v60_cron.py" remove
```

活跃守护状态在master的 `cron/status.json` 与 `queue/status.json`；当前科学状态仍在 `signal_recovery_04/queue/status.json`。只有将来真的发生合格冷恢复，master的 `state.json` 才会保存新episode事务，不能把初始健康阶段没有此文件当成异常。禁止重复运行旧04一次性入口；不要自行删除STOP或terminal来绕过新授权要求。
