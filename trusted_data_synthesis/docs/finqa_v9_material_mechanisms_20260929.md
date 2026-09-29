# V9 材料暴露诊断与真实 C/N 机制接线

## 范围与实际完成状态

本次按 2026-09-29 后续审计补齐两个零模型材料诊断和原定机制实验的执行连接，不更改条件总体、审阅政策、全部有效原包、五臂数学内核、原预算账本或正在运行的生产源码。

新增 `v9_material_diagnostics.py` 与 `v9_mechanism_execution.py`；V8 driver 仅在外更新时增加真实输入保存。实现及有限 CPU 控制已开展，尚未实际运行 Qwen/CUDA、机制短训、5400 机制评测，也没有在本文工作中调用 API。材料诊断需要实际共同核形成后才可产生本轮数值，不能预填 N=820。

## 1. 固定日程中的实际暴露

每个监督 Token 的原系数仍为 `π(z|x)/(B_j*n_xz*L_P)`。不改变 batch、尾批、Adam 或 μ。

新只读统计针对三个种子 11/29/47 的已固定十遍日程计算：

\[
c_x=\sum_{j:x\in\mathcal B_j}1/B_j.
\]

每题记录访问次数、进入不足五题尾批的次数、精确有理数 c_x、`c_x/(10s)`，以及三个种子的 c_x 范围与尾批次数差异。守恒检查是每题访问十次、所有 c_x 总和为 10s，不是所有 c_x 相等。

N=7 的 CPU 例子中，若某题十遍有 k 次进入两题尾批，则 `c_x=(10-k)/5+k/2`；对均匀重排取期望为 `20/7`，但固定日程中的 c_x 一般不同。将各批梯度等权平均，在固定参数处对应 `c_x/(10s)`；它也不是不断更新参数的真实 Adam 路径等价证明。

全总体 G 仍使用均匀 μ=1/N；真实训练使用有限随机重排与尾批。各臂共享同一实际日程，π 保持为条件间干预变量。本文不将尾批暴露差异称为算法效果，也不为“均衡”它而改权重。

## 2. Manual 的实际剂量

对每题以原 prior 和有证据的 χ 计算：

\[
p=r(\chi=1),\quad p^+=2p/(1+p),\quad p^-=p/(2-p).
\]

\[
TV_+=p(1-p)/(1+p),\quad TV_-=p(1-p)/(2-p).
\]

报告逐题的 p、p±、完整 q±、TV±，以及按实际 μ 汇总的全局剂量；精确有理数计算同时与全状态半 L1 距离核对。p=0 或 1 时不发生干预。

例如 p=1/3 时，p+=1/2、p−=1/5，TV+=1/6、TV−=2/15，两个方向不等幅。Manual−不是严格等 TV 的 C 镜像控制。

材料报告还保存实际来源组、来源层级、公司/报告/年份与 lineage 身份；全部完整编码序列长度、每响应监督 Token、整包 L_P 和层统计。零目标历史行仍计入序列长度，不通过 `row_arrays()` 的反向优化视图遗漏它们。reason 明确记为 R＋U，另有 tool=A、final=F，不制造独立 R、U 数字。

命令为：

```bash
python -m trusted_synthesis.finance_research.v9_material_diagnostics \
  --binding ACTUAL_TRAINING_BINDING --output NEW_DIAGNOSTIC_DIRECTORY
```

该入口严格加载实际材料后只做 CPU 统计，没有模型调用、筛题或改日程。

## 3. 保存可真正复用的外层证据

旧 outer checkpoint 保存 C 和若干张量 digest，但 digest 本身不足以执行“复用同一点已有反馈与 C，只切 N”。新增 `outer_inputs.pt`，与原 `state.pt` 和 `record.json` 同目录原子封存，包含：

- 外更新前真实 θ、buffers、Adam、RNG、π、固定 prior、日程、pool/seed/step。
- 实际 G、虚拟 θ、gJ、pullback 张量，实际 C 和 q_next。
- 原反馈 seal 元数据、全部原 episode 哈希、固定分母、真实 reward 向量与 replay report。

不重复嵌入 700 条完整会话正文；原会话继续保留于 collector 的既有目录。外层 summary 同时记录张量文件字节 SHA、内容树 digest 和真实字节数。额外 checkpoint 存储是实际新增成本，不宣称免费；由这些字节数累计核算，而非提前猜测总磁盘量。

机制读取会核对以上真实输入、前后 optimizer/RNG 不推进、原核 q_next、完整 feedback seal 与所有张量摘要。生产反馈仍必须为 700；CPU 两条轨迹的控制不能通过该生产检查。

## 4. C 方向：真实 2s→3s 镜像短训

首次 C-only 外层定义 q+。读取其真实 pre-state，与原 shared2s 的 θ/Adam/RNG/π/prior/日程逐项核对，并要求 current=prior。

调用既有 `first_direction_reverse` 构造 `q−=2r−q+`，拒绝非正支持；不是 Manual−。从真实 shared checkpoint 恢复原训练器，只将机制分支 π 设为 q−，按同一 s 步任务日程训练至 3s。三个种子新增 3s 步。

Static3s 与 C-only3s 使用主实验的预定中间点；检查它们的真实起点、保存的连续步骤、固定 π、prior 和日程。新反向分支内部复用 `Static` 消费器以避免添加另一套优化器或修改主五臂枚举，但机制 manifest 明确标记为 C_reverse，不称为主 Static 或主 Manual−，也不覆盖其文件。

正反 TV 在数学上等幅；KL 与熵不要求相等。全零反馈时可能没有方向，仍按实际报告，不人为制造正向效应。

## 5. N 同点：严格复用或预登记的固定 C-only 锚点

对 C-only4s 与 Full4s 检查真实 pre θ/Adam/RNG/π/prior/日程、G、gJ、C、虚拟点、pullback、reward 向量及反馈 seal。仅奖励个数相同不成立。全部相同才复用原 4s→5s 中间点。

若不相同，按事前固定的 C-only4s 锚点：

1. 读取该点原有的完整反馈、G/gJ/C 和 current/prior；不重采反馈。
2. 使用与实际 driver 完全相同的冻结 anchored kernel，仅由 C-only 切换到 Full 的 N 项。
3. 恢复 C-only4s 已提交 checkpoint（其 θ/Adam/RNG 未被外层更新推进），将 π 设为上述 Full 结果，真实训练 s 步至 5s。

这最多另增三个种子共 3s 步。内部复用 `C-only` 消费器，manifest 显式记为同点 N 控制，而非修改主 C-only。prior 从未改写；若 π 未因 N 改变，报告 `N_activated=false`。

必要实现细节：旧 `same_point_n_diagnostics` 是纯算术 helper，没有传入真实 driver 的 singleton control_tasks。真实 driver 在 RMS 温度中排除这些恒等控制任务。新机制 wrapper 直接调用同一个冻结 `anchored_update`，携带原 `PARAMETERS` 与相同 singleton 控制清单；并核对重算 C-only q 与原实际 q 一致。没有修改数学核或把旧 helper 的不同 RMS 范围冒充同点干预。

## 6. 原 5400 机制评价：与终点 dev883 分离

来源与规模沿用原 V6 training plan 的 `mechanism` 及原总纲第七节：原 calibration120，C 为三方向×三种子×120×三次=3240，N 为两条件×三种子×120×三次=2160，合计 5400。

本次在 Student 结果前明确采样实施参数：两个随机 repeat 使用 seed11/29，greedy 使用 20260928；这是本次前瞻实施选择，不声称原稿已经指定了这些数值。各条件配对使用相同种子。V7公开输入、工具、模板、32响应、2048输出与24576上下文保持；仅角色为原 calibration，两个采样 draw 为 T=1，greedy 为 T=0。

机制 evaluator 复用终点评价模块的真实模型参数安装，以及现有 `prepare_run/execute_run/LocalTorchProvider`。每点全部三次、360会话共同封存之后才读取原生评分参考；unknown不转0。完整 15 个机制点的 5400 条结果才能生成总报告。

`aggregate` 同时报告正方向−Static和正方向−反向，不把“少受反向伤害”称为正训练价值。N报告同点 Full−C-only，而不是用主实验最终闭环差代替。calibration是已曝光诊断，不是盲测；机制分数不用于选中间 checkpoint、改 prior 或停掉较差主臂。

## 7. 操作入口与恢复边界

```bash
python -m trusted_synthesis.finance_research.v9_mechanism_execution register \
  --launcher ACTUAL_LAUNCHER --output NEW_MECHANISM_DIRECTORY

python -m trusted_synthesis.finance_research.v9_mechanism_execution run-seed \
  --output MECHANISM_DIRECTORY --seed 11 --gpu-index GPU

python -m trusted_synthesis.finance_research.v9_mechanism_execution evaluate-point \
  --output MECHANISM_DIRECTORY --seed 11 --mechanism C_direction \
  --condition positive --gpu-index GPU

python -m trusted_synthesis.finance_research.v9_mechanism_execution score-point \
  --output MECHANISM_DIRECTORY --seed 11 --mechanism C_direction --condition positive

python -m trusted_synthesis.finance_research.v9_mechanism_execution aggregate \
  --output MECHANISM_DIRECTORY
```

必须在 Student 运行前冻结机制登记；实际短训要求主臂相关3s/5s checkpoint及新真实 outer evidence存在。GPU入口沿用原模型和显存准入，没有占位或等待持卡。设置CUDA确定性所需的 CUBLAS_WORKSPACE_CONFIG。

失败会保留实际 checkpoint、张量、生成和未完成目录；当前机制入口禁止隐式重复短训或重新采样，不宣传为完整自动恢复器。已全封存生成可单独重新调用 `score-point` 完成原冻结评分；部分生成/短训需明确检查后从原提交恢复，不创建新批来替代失败。运行状态与实际 CUDA 验收仍须另行记录。

## 8. CPU 控制边界

必要控制覆盖精确 c_x、尾批次数、Manual 不等 TV、完整零目标历史长度、真实小模型 shared→C镜像短训、同点 N复用及RNG不同后的固定锚点补支、外层张量篡改拒绝、production700门、singleton RMS复用范围，以及第三个 draw 未封存时禁止读参考。

这些结果是代码/CPU证据，不是 FinQA能力、实际N、GPU吞吐、机制效应或统计功效。本次未重跑 Base、原数学演示或任何 API 技术批。
