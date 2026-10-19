# FinQA V61 六并发调度与评价前安全交接

## 授权范围与当前结论

用户于2026-10-19询问当前进度和预计完成时间，指出还有四张空闲GPU，并明确选择“允许总并发6个”。本次只将现行V54温度实验的总科学worker上限由4增至6，每卡仍最多1个，CPU初始化、资源等待与draining均计入名额。GPU0至7范围不变；yyy账户UID1000同卡禁用、归属未知禁用、原显存与主存硬门保持。空闲设备不是固定预占，不干预其他项目。

新控制主目录为 `automatic_recovery_01/concurrency_six_01/`。旧V59 `signal_recovery_04/` 和V60 `automatic_control_watchdog_01/` 的冻结文件不修改。原科学协议仍如实记载历史上限4，新独立控制协议明确登记有效上限6；不在同一协议ID下偷偷修改配置。

准备期旧任务继续运行。新账户cron先作为被动交接观察器，只有23个核心作业完整accepted、所有科学worker真实退出且全局队列为空时才接管；此后自动恢复也使用六并发控制。代码完成、协议冻结或观察器运行均不等于已经派发6个worker。最终实际安装与运行证据另列于文末。

## 不变的科学和资源合同

本次不改变反馈温度、训练数学、参数点、种子、状态顺序、四个逻辑class分片及统计口径，不新增API、采样、训练或评价额度。三组2100条完整反馈继续复用，新增optimizer总量仍1788次，评价仍为原登记的12267条会话。已accepted的任务、attempt历史、真实退出记录和累计等待继承；旧历史中11个精确缺waitpid例外不扩展，也不补造退出码。

当前两个response回放按各自原序累计，不分片、不迁移、不重放已封存前缀。三个seed的Hold与C05训练全部封存后，才开放九分支、18个模型快照所对应的45个评价作业。六并发的主要收益来自这一独立任务较多的阶段，不意味着当前两路回放能够使用六张卡。

原单进程allocated历史峰值上限76GiB、规定边界物理free至少2GiB、class RSS上限160GiB、其他科学worker RSS上限192GiB、全机有效可用RAM至少96GiB均不变。主存启动门沿用本轮原登记的分阶段预算：

| 阶段 | 每个worker启动预算 GiB |
| --- | ---: |
| class | 160 |
| feedback | 64 |
| replay | 48 |
| distribution | 64 |
| train | 48 |
| generate | 48 |

启动门为96GiB余量，加新worker预算，再加各活跃worker的 `max(0, 原阶段预算 − 当前RSS)` 未占用预留；同时服从宿主机和cgroup的有效可用容量。六个generate的冷启动总预算为384GiB，不是按六个192GiB RSS硬限相加。经验启动预算不保证未来峰值，运行中硬门继续检查。

## 交接顺序与停止语义

新观察器绑定旧04的controller attempt1及supervisor各自PID/birth，不自动追随之后变更的旧episode。健康等待仅检查轻量队列、绑定身份和停止状态，不反复导入Torch、读取反馈或审计Tensor。旧V60继续承担原池的外层异常恢复责任；新观察器在交接前不建立第二个恢复池。

满足训练核心accepted与新鲜空队列后，交接尝试一次性取得八个原GPU租约；任一卡不可取得即释放全部已取得锁，不逐张扣留迫使排空。全锁只是本项目派发屏障，不代表占用八张GPU的显存。取得全锁后，再新鲜核验获胜attempt的实际exit 0、已accepted结果、旧历史与控制身份。

真正交接依次执行：

1. 持有旧V60巡检互斥锁，为旧守护写入明确的被替代终态，禁止它建立竞争后继；不伪造用户STOP、不改旧冻结协议。
2. 新鲜读取账户crontab，只移除旧V60的精确标记行，保留新V61及其他任务；旧配置仅在本地私有临时目录备份。写前再次读取，写后精确核对；不把配置修改不明当作安全重试。
3. 对仍匹配PID/birth、UID1004的旧controller发送一次pidfd维护TERM。不信号科学worker，不直接信号旧supervisor。
4. 等待旧controller与supervisor实际消失。旧supervisor必须保存controller的真实waitpid结果及空worker收口，交接全程保留八锁，防止旧控制器在评价登记附近派发新worker。
5. 封存唯一授权交接回执，再由新守护执行一次原逐job持久状态审计，登记独立 `episodes/episodeNNNNNN/`。后继进程创建只有一次；创建结果不明时阻断，不盲目再次Popen。

原supervisor可能因controller写出的停止标记，转发一次TERM给该controller。新交接仅接受精确绑定supervisor发给精确controller、发生于主维护信号之后、与原停止标记一致、且有发送者PID/birth证据的一次原程序转发。核验保留原kernel信号回执和后续身份观测的区别，不把普通UID1004 TERM普遍当成维护信号。

旧controller在这条维护停止路径的预期真实退出码为2，不是0；科学作业的获胜attempt仍必须真实exit 0。supervisor本身没有外部waitpid时，其退出码保持未知。授权回执仅能覆盖这一精确控制交接：额外owner TERM、任意INT、明确STOP、UNKNOWN反馈、状态或数值失败仍终止新自动恢复。旧记录保留原本的停止含义，后继只附加新授权下的有限解释。

如果旧任务已经完成全部生成并进入统一评分，不再打断评分进行交接；如果旧控制器或episode改变、旧池发生失败，观察器停止交接、不自动追随。若交接尚未开始时旧V60按原规则建立后继，原实验可继续由旧四并发守护负责，不能把新六并发准备称为已生效。

## 核验与进度估计

117项不同CPU/mock用例通过：controller 5项、registration 5项、backend 24项、watchdog 26项、handoff 39项、cron 18项。定向覆盖六并发私有调度、原科学协议不改、原RAM公式、真实退出边界、精确维护信号、信号身份补充记录的落盘竞态、全部生成完成后不切换、cron配置保留及派发不明阻断。未重复执行科学数学审计，也未通过终止真实科学任务进行破坏性测试。

准备阶段的真实只读绑定检查通过：旧controller PID3878874、birth476360127；supervisor PID3878725、birth476359812；23个核心作业及11个原缺waitpid例外绑定一致，状态为 `WAITING_FOR_ACCEPTED_TRAINING_CORE`。此检查没有创建新科学episode、发送信号或占用GPU。

北京时间11:34的进度快照中，三组反馈和所有class任务已完成；seed137的782条回放已完成，seed251为459/790、seed389为394/803。六段新训练已完成四段，即1192/1788次optimizer更新，评价尚未开始。seed137 C05完整298步实际耗时3小时6分20秒，可用于粗估剩余同长度训练；seed389 Hold最后一次attempt仅覆盖184步，不能把其1小时55分当成完整298步耗时。

按当时回放平均速度与完整训练段耗时估计，训练可能在10月19日19至21时封存。若六并发交接成功且资源稳定，评价暂估8至12小时，整体可能在10月20日凌晨3至上午9时收口；若仍四并发，评价暂估12至18小时，对应上午7至下午3时。评价估计依据既有生成耗时与任务尾部，而不是本轮六并发实测；冷加载、长尾任务、共享资源波动和故障恢复均可能推迟。统一评分完成前不报告新的准确率结论。

## 查看与停止

旧池运行时，科学进度仍看 `signal_recovery_04/queue/status.json`。新主目录的 `handoff/status.json` 与 `cron/status.json` 表示交接观察状态；真正接管后，主目录 `state.json` 的 `current_episode` 才指向有效的新科学控制目录。没有新episode不等于观察器故障，也不能重复启动旧04入口。

以下命令从仓库根目录执行。只读检查V61账户任务是否存在：

```bash
FINQA_V61_ROOT=trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/concurrency_six_01
trusted_data_synthesis/.venv/bin/python "$FINQA_V61_ROOT/implementation/finqa_v61_cron.py" check
```

需要明确停止实验及新自动接管时，执行冻结入口的 `stop`；它保存新master停止屏障，并给当前及待接管的绑定episode写STOP。命令返回不代表worker已退出，仍应查看真实安全收口：

```bash
trusted_data_synthesis/.venv/bin/python "$FINQA_V61_ROOT/implementation/finqa_v61_cron.py" stop
```

`remove`只移除V61定时条目，不等价于停止已经运行的观察器或科学进程，也不应作为紧急停止方式。若只移除条目而保留活跃交接观察器，未来交接的已安装条目核验会阻断，但现有科学任务不因此被信号。不要删除STOP、terminal或已消费事务来强行重新运行。

## 正式冻结与实际激活

本节在源提交、冻结CPU依赖核验和真实cron触发后追加实际结果。当前源版本尚未执行交接，不宣称六个科学worker已经运行。
