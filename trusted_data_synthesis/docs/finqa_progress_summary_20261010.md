# FinQA实验进度与阶段结果汇总

截至2026年10月10日08:33的收口核验，原训练复制实验B仍安全冷暂停；V34末段补验已触发预登记的4小时运行上限并停止，未完成整轮验收。当前没有本轮GPU worker在运行，原控制器已退出；本次只整理结果，没有重启实验或追加计算预算。下文时间均为北京时间，GiB按2³⁰字节换算。

目前科学结果仍来自已完成的旧seed扩展A：C-only平均高于Full，但不能据此推断新seed稳定性。工程验证已证明固定四例的R3回放加速和实际断点冷恢复；完整生产准入尚未通过，不能把这些工程进展计作Student效用提升或B训练进展。

## 各阶段当前结论

| 阶段 | 已建立的结果 | 当前边界 |
| --- | --- | --- |
| A旧seed扩展 | 三个旧seed的C-only终点评价完成，与既有Static和Full结果汇总 | 事后描述性消融，不是新seed确认 |
| B新seed复制 | 5812个物理训练更新、9次outer提交、2个最终模型 | 保持暂停，九模型统一评分尚未执行 |
| V32回放性能验证 | 四例逐位对照通过，最快R2为1.120428倍 | 未达1.20倍门，完整cohort未启动 |
| V33激活驻留对照 | 四例R3为1.375889倍；完成response16冷恢复及573条回放 | 最终显存资源门失败，整轮未通过 |
| V34末段显存补验 | 已计算3107／4974个类梯度训练行，已记录的显存子条件均通过 | 4小时超时停止，类梯度pass及后续数值验收未完成 |

V32终态为 `STOPPED_NO_MATERIAL_SPEEDUP`；V33和V34各自保持 `STOPPED_FAILURE_NO_RETRY`。后续补验没有改写前轮失败记录，也没有恢复原B。

## A块已完成的科学结果

A使用旧seed11、29、47与同一官方test1147题。下表每个方法的分母均为三个seed乘1147，即3441；Static和Full复用原封存终点，A新生成的是三个C-only终点。

| 方法 | 总正确题数 | 执行准确率 |
| --- | ---: | ---: |
| Static | 1386／3441 | 40.279% |
| C-only | 1637／3441 | 47.573% |
| Full | 1505／3441 | 43.737% |

| 比较 | 三seed等权平均差 | 各seed方向 |
| --- | ---: | --- |
| C-only减Static | +7.294个百分点 | 2正、1负 |
| Full减C-only | −3.836个百分点 | 0正、3负 |
| Full减Static | +3.458个百分点 | 2正、1负 |

这些结果表明，在三个既有模型seed与已知test上，C-only平均优于Full，且Full减C-only三次均为负。A是在test已经可见之后开展的扩展，不能证明C-only普遍更好、把差异直接归因为某个算法部件，也不构成新seed重训稳定性或新任务泛化的确认。没有新增置信区间或p值，旧Full与Static的比较不算第二次独立确认。详细逐seed结果见[V31暂停与性能审计报告](finqa_v31_pause_and_performance_audit_20261008.md)。

## B块暂停进度与保留工作

原队列仍为 `PAUSED_BY_USER_CHECKPOINT_SAVED`，active children为空，`replication_scored=false`，`automatic_resume_authorized=false`。共24项GPU作业中10项完成、4项暂停、10项未派发；不同作业成本差异很大，作业数不能换算为时间完成率。

| 项目 | 已完成或封存 | 原预算 | 仍需完成 |
| --- | ---: | ---: | ---: |
| 物理optimizer更新 | 5812步 | 11622步 | 5810步 |
| 已提交outer | 9次 | 24次 | 15次 |
| 已封存feedback参数点 | 12个 | 24个 | 12个未来点 |
| 反馈轨迹 | 8400条 | 16800条 | 8400条未来新反馈 |
| 最终模型 | 2个 | 9个 | 7个 |
| 终点回答 | 2294条 | 10323条 | 8029条 |

5812／11622约为50.01%，仅是更新数量比例。剩余15次outer中，3次已各有700条封存反馈，恢复时只能绑定原参数点并重做未提交计算，不能重采样；另12次才是原预算内未来参数点的首次生成。已完成的两个最终模型为Static137与Static251，2294条终点回答均已保留。

| seed | Static有效步数 | C-only有效步数 | Full有效步数 |
| --- | ---: | ---: | ---: |
| 137 | 1490 | 1192 | 1192 |
| 251 | 1490 | 894 | 419 |
| 389 | 327 | 298 | 298 |

有效步数包含共同前缀；物理更新统计则每个seed的共同前缀仅计一次。B没有完整九模型汇总、新seed置信区间或六seed合并结果，仍须全部九模型终点封存后统一评分。三个未提交outer的部分内存计算没有完整断点，不能把“完整训练状态和反馈已保存”理解为每一步中间计算都能直接续接。原暂停证据及详细预算见[V31报告](finqa_v31_pause_and_performance_audit_20261008.md)与[V32科学工作边界](finqa_v32_bounded_replay_performance_20261009.md)。

## V32与V33建立的工程证据

V32在同一GPU3上以冷进程比较R0、R1、R2。四例正式总时间分别为202.795533、198.502805、180.998226秒；最快R2为1.120428倍，低于预登记1.20倍门，因此没有执行完整cohort、实际response16冷恢复或独立C与π验收。逐位数值检查通过不覆盖未执行阶段，也没有产生新Student效用结果。

V33在同一GPU7上另做新鲜R0与R3配对，四例正式总时间为197.853288与143.800344秒，得到1.375889倍加速、耗时减少27.3197%。四例logP与全部112个梯度张量逐位相等。该倍率仅属于四个固定案例，不是完整训练加速比，也没有重复测量的置信区间。

V33随后在第16个response保存实际累计梯度并退出，由新冷进程恢复游标16，继续完成573／573个实际response，对应87586个输出token。原700条轨迹中372条零奖励轨迹按原规则跳过，分母仍为700。最终 `response000573` 累计梯度已保存，CPU只读核验与原gJ逐位内容摘要一致。

V33于10月9日18:28:36在最终资源检查抛出 `observed CUDA memory envelope exceeded`，18:28:45停止。冻结控制流显示它已越过最终数值比较条件，但最终比较字典尚未落盘，不能记作独立成功结果。失败时allocated峰值与瞬时free没有独立保存，设备采样峰值79.13965GiB也不能直接解释为allocated超限。CPU累计梯度核验不替代这一失败资源门。完整结果分别见[V32报告](finqa_v32_bounded_replay_performance_20261009.md)与[V33报告](finqa_v33_bounded_activation_residency_20261009.md)。

## V34超时停止与实测资源

V34仅复用已保存gJ补做一次类梯度与后续C、π验收，不再回放573条response。GPU7 worker于10月10日00:00:38.440964启动；04:00:38.851943在第3107个类梯度行完成边界收到停止请求，记录 `TailStopRequested: stop requested at class_row_end`；04:01:08.614400封存退出记录，`returncode=1`、`timed_out=true`。停止原因是预登记4小时上限，不是CUDA OOM或数值不一致。

共3112条资源记录的 `allocated_pass` 与 `free_pass` 均为true；最后一条综合 `passed=false` 由停止标志触发，不应误写为显存门失败。已观测资源如下，包含模型加载，期间没有重置历史峰值。

| 指标 | 已观测值 | 口径 |
| --- | ---: | --- |
| PyTorch allocated历史峰值 | 16.173910GiB | 门槛不超过76GiB |
| PyTorch reserved历史峰值 | 22.992188GiB | 分配器保留量，不等于活跃张量 |
| 规定边界最小设备free | 55.461853GiB | 门槛至少2GiB |
| 按秒采样设备占用峰值 | 23.790039GiB | 成功样本最大值，不是连续精确峰值 |
| 进程RSS峰值 | 137.558174GiB | 主机内存，不是GPU显存 |

这表明已执行部分在原显存门内，但类梯度pass没有完成，不能外推余下输入与后续阶段的峰值。`point_comparison`、`numeric_comparison`、`storage_receipt`和最终 `result` 均未产生；聚合G、虚拟参数点、pullback、C和π的最终比较未执行，既不能称为数值通过，也不能称为数值失败。

已完成3107／4974个有效类梯度训练行，按行数为62.4648%，余1867行。完整分母4974来自原prefix material的已封存计数；V25实际训练登记绑定V18 material，后者引用相同V15 prefix binding和material_order_id，冻结pool只遍历有target的行。原始4978行中的4条零target行不计入forward。该比例是训练行数量，不是时间完成率，也不是573条feedback response的进度；本报告不据此线性推算剩余耗时。

3107行不是可恢复的中间断点。V34没有保存类梯度中间累加状态，后续若获准开展新补验，不能直接声称从第3108行接续；但V33最终gJ仍保存，无需因此重放573条response。

CPU卸载路径在已执行阶段体现出较低GPU显存需求，同时付出了超过4小时未完成及较高主机内存占用的代价。现有结果不能将全部时间或RSS归因到单一hook、传输或Python开销，也不能证明完整CUDA等价性或资源总体成功。详细合同与本轮收口见[V34末段补验报告](finqa_v34_tail_memory_validation_20261009.md)。

## 授权边界与后续决策

用户允许本轮占用额外空闲显卡，但V34实际只使用GPU7一个worker。该许可是资源许可，不会自动增加class pass、response回放或优化轮次，也没有建立保持原归约顺序的多卡实现。现有预算失败后停止，本次没有再次派发任务。

若另行授权修订，可围绕类梯度的并行计算与固定顺序归约、CPU保存和同步开销、可验证的类梯度累加断点，以及与实际成本匹配的有界运行时限登记新方案。这些只是待验证方向；新增pass、改变累加实现或延长已冻结时限都不能作为原V34自动重试执行。并行化仍须证明原数值合同，持久累加还须保存完整输入、游标和参数点绑定。

原B继续暂停。任何正式恢复都需要另行明确授权，并核验原完整状态、封存反馈字节和相同feedback参数点；不能裸用旧 `--resume` 触发新feedback目录或重采样。工程补验通过即使未来实现，也不等于A结论得到新seed确认或原B自动获准恢复。

## 证据位置

实验根为 `trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v25_training_replication_01/`。原始Tensor、回答与动态日志继续保留本地，不以CPU/mock夹具替代正式结果。

| 相对实验根目录 | 主要内容 |
| --- | --- |
| `c_only_test_extension/summary/record.json` | A三臂封存结果 |
| `four_gpu_release_01/queue/status.json` | 原B暂停状态与未评分屏障 |
| `four_gpu_release_01/experiment_pause_01/` | 原完整状态、反馈封存与暂停进度 |
| `replay_performance_01/closeout_01/record.json` | V32未达吞吐门的收口 |
| `replay_performance_02/closeout_01/record.json` | V33资源失败与CPU累计梯度核验 |
| `replay_performance_03/tail_validation/failure/record.json` | V34停止异常与逐边界资源实值 |
| `replay_performance_03/tail_validation/exit/record.json` | V34超时退出与不重试字段 |
| `replay_performance_03/queue/status.json` | V34最终停止状态 |
| `replay_performance_03/closeout_01/record.json` | V34超时收口、资源摘要、行数分母绑定与进程退出核验 |

V34收口记录ID为 `e85e319a491a16833231cc881e8653bbdc93f74f0ef30683d695ad1acb1ce023`。本次汇总没有新增API调用、采样、评分或真实optimizer更新；性能倍率、资源观察与科学准确率始终分开解释。
