# FinQA GPU0 单卡接续与设备范围修订

本次最终授权为仅使用物理GPU0，以一个worker顺序完成原九模型矩阵的全部剩余工作。用户先要求收缩到当前设备并最终保留GPU5，随后查看GPU0与GPU5余量后，明确选择“改为GPU0单卡完成全部”。这一新选择替代“Full251训完后归还GPU0”和“最终只用GPU5”的安排，不修改历史授权及停止记录。

新运行根为 `production_resume_01/single_gpu0_01/`。GPU0 UUID固定为 `GPU-f813ce38-39d7-ab21-f72b-55f87284eaa5`，GPU1至7均不再派发。本次不减少或增加科学剂量，不修改原数学81文件，也不重启V48或V49旧入口。

## 旧GPU5任务为何暂停

2026年10月16日13:08:42北京时间，助手为取消尚未激活的V49四并发后继，对身份核验后的交接管理器PID1451212发送了一次pidfd绑定的SIGTERM。旧交接器采用失败关闭逻辑：保留项目锁，先协作停止旧监督器和控制器，待科学worker实际退出后才释放锁。因此该操作同时暂停了GPU0和GPU5，而不只是停止GPU1的显存等待。

GPU5不是因OOM或数值错误自行退出。它收到合法停止信号后，在完整response210边界保存了实际累计梯度，再以 `ReplayPaused` 退出。该切换路径中断了GPU5原本持续运行的任务；不能把它表述成“GPU5没有被中断”或“仅GPU1已归还”。助手已向用户说明这一实际影响。

GPU0的Full251也在实际optimizer更新提交后响应停止。停止发生在 `after_real_optimizer_step.before_cleanup`，并非撤销尚未提交的更新。GPU1在CUDA初始化前退出，没有新模型调用或回放。

| 旧任务 | 最后真实保存点 | 退出结果 |
| --- | --- | --- |
| Full251训练 | step1334/1490，实际模型、Adam、RNG、π已保存 | `TailStopRequested`，13:09:28，exit1 |
| Full389 step894回放 | response210/540，原133加本进程77条 | `ReplayPaused`，13:09:14，exit1 |
| C-only389 step1192回放 | 原真实前缀240/419不变 | `AdmissionStopped`，13:08:46，exit1，未初始化CUDA |

Full389的response210记录ID为 `78abcf3cce9daf4ffd6605936a9218c2cbf673675cb11bcd870ddd856ce2c385`，Tensor文件SHA256为 `968eee607bfb67604f1fd5eb3a87cd698d55edd1e20fbc6315a1617885636a4f`。Full251 step1334的state SHA256为 `be0b71f8e3203bb5a04192c4d72eb18bc8bb97df1ae6c1939711be24b2fbd5c4`，实际state digest为 `cd663759eb09e0764ed17fb64ac4fbb78da901b108ecfb005effa7fe00284eb1`。新worker仍须在实际消费时执行原完整状态与同点绑定检查，不能仅以计数替代Tensor恢复。

Full389已观测资源门通过。Full251历史 `resources.all_gates_passed=false` 仅对应末条停止标记：该条的allocated、free、host及deadline数值子门均通过。历史字段保留false，不改写为整段资源验收成功。GPU1的 `resources=null` 表示未进入对应GPU监测，不能据此宣称完成了显存数值验收。

## 停止收口和最新设备选择

旧V48监督器于13:10:02以 `STOPPED_BY_EXPLICIT_REQUEST` 收口，不自动拉起；最终控制器队列为空。V49交接以 `explicit_stop=true`、`automatic_restart=false` 结束，释放授权为 `TERMINAL_STOP_NO_SUCCESSOR`，不再启动四并发后继。旧监督器、控制器、三个worker、管理器、监护进程及八个辅助进程均已退出；八个辅助进程的退出码均为0。V49新科学协议和新科学监督器从未创建。

相关记录保存在 `concurrency_four_01/superseded_single_gpu5_01/`。该目录名称保留最初停止时的GPU5选择，不能因后来的GPU0选择而重命名或覆写历史。operator stop记录ID为 `d85fe709e1715fe58a3c6b3633449792341984531f7806aee6b3909cff1c70e6`，实际停止收口ID为 `a89441545c8b975f2ae6f3a1eec896cba740f9d0bc67bbace64d7614443b516c`。

13:15:37实测GPU0 free为67845MiB，约66.3GiB；GPU5为49960MiB，约48.8GiB。前者满足R3的56GiB准入，后者不满足。用户随后明确选择GPU0单卡；最新授权单独封存在 `final_device_authorization/record.json`，ID `ec4fb262d47a06d5ba0fe0b1bd677d2dbc4ed219224c104f167870ce8d17683c`。这只是当时的资源快照，新派发仍须重新检查实际余量。

## GPU0单worker合同

从新运行开始即固定GPU0、总并发1。CPU初始化、CUDA前等待、模型加载前资源等待、实际计算及退出收尾均计入唯一名额。不保留“暂时GPU0加GPU5”的双卡分支，资源不足时等待，不自动改用其他设备。

第一项科学工作必须从Full251的真实step1334继续训练至1490。在它完成前，不派发其他回放、训练、类梯度或终点生成；如果后续自动恢复时实际完整checkpoint已经达到1490，不重复这段训练。之后原剩余阶段及三个模型的终点回答全部在GPU0顺序执行，四个逻辑class分片保持原任务划分，但逐个运行。

初始剩余剂量为1050次optimizer更新、3次outer、3441条终点回答，六个已有终点只读复用。C-only389从240/419接续，Full389从210/540接续；两个未提交旧参数点的1400条反馈与冻结奖励不重新采样。未来Full389 step1192仍仅首次采样原预算700条。全部九模型封存后才统一评分。

沿用分阶段共享GPU准入、同进程可复用显存预留、生命周期allocated峰值76GiB、科学边界free至少2GiB、RSS160/192GiB及全机有效可用RAM至少96GiB。无资源或阶段截止，原已用时间与等待统计继续继承。自动恢复只允许已验证的实际断点和资源故障，明确停止、未知反馈、绑定错误及数值错误不作为自动重试许可。

此前按四并发给出的30至40小时估计不再适用于新的单卡安排。单卡下class、各模型训练和终点生成不能按原四并发重叠，需要在新运行稳定后按实际吞吐重新估算。

## 验证与实际启动状态

真实停止收口和GPU0最新授权的只读预检已通过。代码完成、准备冻结、正式CPU依赖核验、监督器启动及实际训练推进分别记录，不把准备工作当成科学任务已恢复。新根只允许一次正式初始启动，此后由该根的监督器生成安全后继attempt；不得再运行旧V48、V49入口或尚未登记的GPU5方案。

最终154项不同CPU/mock用例联合通过，用时14.82秒，相关源码与测试的Ruff及差异格式检查通过。覆盖单设备UUID与唯一名额、Full251优先门、等待与draining计数、真实1334/240/210前沿、历史停止与最新GPU0授权分离、未知错误拒绝以及原同进程显存等待。测试没有调用GPU模型、API或读取终点答案。
