# V15 无状态共同 Static 前缀执行（2026-09-30）

## 目的与权限边界

本模块只执行固定 744 题、2468 包的既定共同前缀。全部监督权威与 V14 编码已经完成；不等状态映射，不把未完成任务移除，也不人为给原包配置临时状态。

`v15_prefix_material.PrefixPool` 是独立的无状态材料消费者：包仅含 `package_id`、`task_id`、`whole_package_target_tokens`、`fused=False`；没有 `_manifest`、state、χ、prior 或 π。`v15_prefix_training.PrefixDriver` 明确拒绝假装完整训练池的输入。生产入口要求前缀专用 binding、全部 744/2468、已先冻结的定点映射计划和完整原始编码来源。

真实前缀仍为种子 11/29/47，每 seed 298 步。Driver 没有 outer/反馈/Manual/dev 方法；`step()` 和 `run_until()` 对共同前缀上限均有硬检查。到第 298 步保存停止，运行进程可释放 GPU 等待完整映射。前缀损失下降不作为材料裁定或后继训练的准入标准。

## 权重、顺序与实际数值路径

固定频数先验和类内均匀核下：

`r(z|x)/(B_j*n_xz*L_P) = 1/(B_j*n_x*L_P)`。

生产前缀直接用右式，不先构造 state 或 π 再求相消。系数以 `Fraction` 计算后只转一次浮点。实际批大小包含真实 4 题尾批，不额外除 N、全局 Token 数或再除批大小。

每个任务批按原任务日程顺序，再按材料的原包顺序，消费原正目标响应行。零目标行不额外 forward，以免改变 dropout RNG；它们仍通过全行 SHA 和后续完整输入历史保持绑定。`material_order_id` 绑定全部原行，`execution_order_id` 另绑定实际正目标行顺序。

实际 forward、逐行 summed FP32 CE、backward、一次 `zero_grad`、一次非有限梯度拒绝的 clip 和一次 AdamW step，复用原 `trajectory_consumer.execute_update` 热路径。该函数只需给定包系数与原响应数组；前缀没有套用 `VerifiedPool` 或提供伪造 π。原消费报告里的历史描述字段由明确 V15 元数据替换，底层实际更新 ID 保留为来源。

模型使用原 `_load_components`：原始 Qwen2.5-7B-Instruct、冻结 BF16 Base、全层 q/v 新 `LowRankLinear`，rank8/alpha16/dropout0.05、可训练 FP32 A/B。AdamW 保持 lr=1e-4、betas=(0.9,0.999)、eps=1e-8、weight_decay=0、foreach=False、fused=False。没有修改数学公式或训练目标。

## 正式第一步就是验收步骤

第一个预登记任务批执行成功后，立即保存 `step0001_step`，检查更新后 θ/Adam 有限，然后从这个真实保存点恢复同一模型、Adam、RNG 和游标，核实际状态摘要一致。该检查不再做 forward/backward，不执行第二次 optimizer step。验收记录为 `shared/first_step_acceptance/record.json`。

前缀保存点含真实 θ、buffer、Adam 矩与 step、Python/Torch/CUDA RNG、任务日程与游标、材料和执行顺序绑定、实际累计消费计数；不含 state、χ、prior、π 或 outer 状态。恢复时从 CPU 载入保存点，让非 capturable Adam step 和 RNG 保留其 CPU 语义，再由 optimizer 按参数设备恢复矩。

每次成功更新必须落成不可变保存点后才算提交。资源失败、数值失败、IO/保存失败分开记录；记录最后提交步、是否已经进入 optimizer step、是否可能存在未提交部分更新，以及已完成的包/行阶段。失败不会自动重试；显式恢复不得重复已经成功提交的第一步。

## Launcher 与资源记录

入口为 `register(prefix_binding, output, allowed_gpu_indices=...)` 和 `run_seed(output, seed, gpu_index, resume=False)`；CLI action 为 `register`、`run-seed`、`resume-seed`。

登记只读取材料，不查询或分配 GPU。实际运行才按注册 GPU 范围检查至少 24576 MiB 空闲、取得 seed/GPU 排他锁、载入原模型。该空闲阈值是启发式门槛，不是 CUDA 验收保证。加载峰值单独写入 launch attempt 的 `loaded` 记录；后续更新和 seed 结果记录实际训练显存峰值。没有占位进程、等卡时已加载模型或自动换模型/截历史的路径。

Launcher 绑定 12 个实际执行源码及 torch/transformers/tokenizers 版本，禁止在登记后静默改变执行实现。生产首步是否真正通过、显存和耗时必须以之后真实 GPU 记录为准；本实现文档不预报通过。

## 完整映射后的显式迁移

`migrate_prefix_checkpoint(prefix_checkpoint, prefix_pool, full_pool, output_dir)` 只接受唯一的已完成共同前缀和真正完整、非退化且已准入的 full pool。迁移前核同一 task/package/all-row/正目标行顺序、tokenizer、材料 binding、执行日程，以及 full pool 的确切频数先验。

只有此时，才在新 shared 保存点中加入真实已完成映射对应的 prior/π。θ、buffer、Adam、RNG、seed、游标与日程的实际计算摘要必须保持一致。迁移不执行 optimizer step，也不重训前缀；证明记录明确注明原前缀不存在 π。

输出可由原 `ConditionalTrainingDriver.restore(..., branch=True)` 消费。它位于共同点 298、`outer_done=[]`；C-only/Full 在离开此点前仍必须完成原第一次真实 outer，迁移不执行或跳过反馈。Static/Manual±/C-only/Full 后续规则、机制点与终点评价保持原计划。

## 必要 CPU 验证与实测范围

仅运行 `tests/test_finance_v15_prefix_training.py`，最终为 **8 passed，3.97 秒**；新增模块与测试 Ruff 通过。覆盖：

- 从真实非空 Adam 状态及相同 dropout RNG 出发，直接包均值与单状态、逐包状态、不等大小状态三种合法分区的 prior 系数对照；5 题批与 4 题尾批下，loss、clip 前后梯度、θ、Adam、RNG 摘要完全一致。
- 正式第一步真实保存/恢复，optimizer 只新增一步；中途恢复至共同前缀末尾与不中断执行的实际状态完全相同。
- 资源异常与 NaN 分别记录，未提交更新不计为完成，禁止隐式续算。
- 不完整映射阻断迁移；完整合成映射迁移保留实际计算状态，原五臂能读该点，自动臂不能跳过首次 outer。
- 无状态保存点不含伪造分布；材料检查失败在 GPU 查询之前停止。

这些是明确合成 CPU 控制，不是生产 Qwen/CUDA 的逐位验收、GPU 吞吐结果或模型效用证明。未由测试或本模块实现过程自行调用 API、启动正式训练或评价。
