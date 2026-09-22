# Delayed-C 三种子实验：最终审计报告

## 0. 文档状态与审计范围

- 报告日期：2026-09-22；下文时间均为北京时间（UTC+8），原始 JSON/日志通常采用 UTC。
- 审计对象：2026-09-19 登记、2026-09-20 放行，经过资源故障恢复，于 **2026-09-22 19:26** 完成的 Delayed-C 实验。原 A 矩阵和前置代理审计仅作为比较基线、设计依据与准入证据，不重记为本轮新增训练结果。
- 证据基线提交：`ecd1e6b30157ffb9879662c0d8e86be707448fe7`，即本轮最终汇总已发布的提交。报告编制本身不修改冻结的实验实现、计划、评分或失败记录。
- 交付物：[本报告](fixed_kernel_delayed_C_audit_report_20260922.md)、[机器可读证据与计算附件](audit_reports/delayed_C_20260922/evidence.json)、[只读复核脚本](../scripts/audit_fixed_kernel_delayed_C_report_20260922.py)。原始简要汇总见[阶段完成报告](proxy_audit_20260919/complete_delayed_C_aggressive_autorun_20260921.md)。
- 审计方法：核对预登记与修订记录、保存的评分和任务集合、运行/生成/评分 ID 关联、完整更新账目、逐步复现记录、资源事件和完成状态。**没有重新训练、生成、私有评分、加载大张量或发起 API 请求**。
- 审计性质：这是基于现有本地工件的事后记录一致性审计，不是第三方独立执行复现，也不是独立确认实验。

## 1. 执行摘要

三种子均完成各 400 次有效 optimizer 更新、一次 step200 的 360 条随机反馈，以及唯一 step400 的 180 条最终 greedy 评测。seed11 的原完成结果保留；seed29、seed47 通过单独登记的恢复分支完成。最终生成、评分、汇总及自动推送均完成，最后的协调器返回0并结束守护；本实验已释放 GPU。此前的OOM和非零退出另行保留，不被最终成功状态抹去。

| 条件 | seed11 /180 | seed29 /180 | seed47 /180 | 合计 /540 | 财务合格率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Static | 67 | 66 | 37 | 170 | 31.4815% |
| 原 C-only | 62 | 45 | 48 | 155 | 28.7037% |
| 原 Full | 60 | 48 | 45 | 153 | 28.3333% |
| **Delayed-C** | **66** | **59** | **51** | **176** | **32.5926%** |

预登记主比较 Delayed-C−Static 为 **+6/540，即 +1.1111 个百分点**。三个种子的净差分别为 **−1、−7、+14**；seed47 的正差抵消另两个种子合计 −8 的负差。因此可以报告“固定开发集上的汇总正方向”，不能报告“跨种子一致提升”“稳定优于 Static”或“统计显著提升”。

还有四个必须同时保留的结论边界：

1. 540 是同一组 180 道题在三个训练种子下的评分记录，不是 540 道独立题；这些开发题还参与了反馈元优化。
2. 原 Full 相对 Static 的负结果未被改写；本轮不是 Full 或 Novelty 成功的证据。
3. 有效训练剂量为 1,200 步，但可追踪完整物理更新至少 1,303 步，含 seed47 的 103 步重放；不能声称原物理训练预算未增加。
4. B 池、720 题独立确认及独立检索适配均未启动；本轮不是独立确认。

## 2. 研究问题、预登记与准入

### 2.1 本轮实际检验的问题

在旧 Full/C-only 开发结果已经暴露的前提下，本轮提出后继方案：取消冷启动时的分布更新，先以固定 prior 完成 200 步 SFT，在非空 Adam 状态的 step200 计算一次 C-only 更新，再执行后 200 步，观察最终固定开发集 greedy 效用是否改善。

- 主比较：`Delayed-C minus Static`。
- 辅助比较：`Delayed-C minus original C-only`。
- 方向判据：三种子合计合格数严格高于 Static 时，登记为 `POSITIVE_FIXED_DEV_DELAYED_DIRECTION`；否则保留 Static、不给出正方向结论。
- 没有预登记显著性检验、p 值阈值或置信区间。本报告不追加这些统计推断，也不把工程数值阈值当作显著性阈值。

Delayed-C 在本轮实际结果产生之前登记，但不是整条研究路线在从未看过开发结果的条件下首次盲选。因此，原开发集上的选择与复用是解释边界的一部分。

### 2.2 前置代理审计并非“全部方向可靠”证明

| 事件 | 时间 | 记录 |
| --- | --- | --- |
| 前置代理审计计划登记 | 09-19 10:50:55.995 | `proxy_direction_audit_20260919/plan.json` |
| Delayed-C 条件计划登记 | 09-19 11:06:26.750 | `delayed_C_20260919/plan.json` |
| 前置审计按范围完成 | 09-20 00:06:34.180 | `proxy_direction_audit_20260919/report.json` |
| Delayed-C 实际放行 | 09-20 00:06:56.164 | `delayed_C_20260919/admission.json` |

准入要求计划绑定正确、12 个保存点的数值门全部通过、方向审计已按范围完成。它不要求所有交叉方向为正；前置报告明确 `direction_stability_not_assumed=true`。

前置审计的实际发现是：冷启动三个种子的双向交叉分数均为负；旧 warm/epoch5 点的 seed11、47 双向为正，seed29 双向为负。热启动逐正项删除的最大相对 C 变化较低，但仍不是所有热启动方向可靠。两个 repeat 的交叉比较复用同任务、同点的旧轨迹，不等于独立预测验证，也不等于本轮新 step200 点的多步效用检验。

实际代理审计使用 6 个经参数、优化器、虚拟点和反馈内容绑定后可复用的唯一点，完成 6 次额外全类遍历、107,653,794 个类序列 token、326 条正奖励轨迹/1,863 段响应回放、83,173 个原采样输出 token；cached forward target positions 为 166,346。新生成及新财务评分均为 0。这些是**前置审计成本**，与本轮 Delayed-C 的新增生成和 SFT 分开计量。

### 2.3 不能把辅助比较解释为纯粹单因素时机效应

旧 C-only 在 epoch0 和 epoch5 各更新一次，每个运行有 720 条反馈；Delayed-C 删除 epoch0 更新及其 360 条反馈，只保留 step200 一次。因此辅助比较同时改变首次启用时机、外层更新次数和反馈总量，不能单独识别“只改变时机”的纯因果效应。

相对 Static，两者 SFT 有效剂量、配对初始化和任务日程对齐，但 Delayed-C 多出反馈生成、评分、全类梯度、回放与分布更新成本；这不是总计算量匹配的效率比较。

## 3. 任务、材料与评价口径

### 3.1 训练与开发任务

| 用途 | 唯一任务数 | 构成 | 本轮使用 |
| --- | ---: | --- | --- |
| A 池训练 | 200 | annual_flow 40、company_defined_metric 40、stock_rollforward 40、control 80 | 三种子各十遍；均匀任务权重 μ=1/200 |
| 反馈与最终评价 | 180 | composition_required 60、dual_sufficient 60、other_financial 60 | step200 每题两次随机反馈；step400 每题一次 greedy |

训练与开发 task_id 无交集，但开发题参与反馈元优化，不能因其不进入直接 SFT 就称为未参与学习的独立测试集。全部 12 个“条件×种子”的最终评分任务集合一致；评估来源共 12 个 CIK 簇，组间有重叠。

训练材料每次全类遍历包含 3,547 个 package、1,681 个当前 Mapper 状态，覆盖全部 200 个任务。1,681 是当前材料上的状态数，不是理论状态空间已被穷尽。

开发输入沿用 `given_sources_value_20260915/inputs_v2/views/` 的 given-sources 公开视图。其 v2 manifest 声明没有相对父视图新增或删除数值记录，属于无损布局修订。本轮没有新增独立检索适配，也不据此声称自由检索场景下的能力收益。

### 3.2 Q 的含义与评分隔离

本报告的分数是已保存评分器的 `Q=int(financial_valid)` 通过数，称“财务合格率”，不擅自改称某个外部标准基准的准确率。

- 反馈 360 条或最终 180 条生成必须先完整封存，再交由独立 CPU 进程使用私有参考评分。
- 私有参考不发送给生成器；复用固定 source manifest、runtime、工具限制和评分规则。
- `anchored_independent_scoring` 中的 independent 表示评分执行与生成隔离，**不表示评价数据是独立确认集**。
- 保存结果中的 `financial_rule_unchanged=true`、`scoring_after_all_generation_complete=true`、`confirm_tasks_opened=0` 已核对。
- 资源故障不计为 Q=0，不因结果不理想补抽、改规则、修补最终答案或重选种子。

## 4. 模型、优化器与固定执行设计

| 项目 | 本轮配置 |
| --- | --- |
| 基座 | Qwen2.5-7B-Instruct，本地 revision `a09a35458c702b33eeacc393d103063234e8bc28` |
| 基座参数量 | 7,615,616,512；按本地文件内容绑定，不仅依据目录名称 |
| 精度 | 基座 BF16；LoRA 与 Adam 状态 FP32 |
| LoRA | q_proj/v_proj，rank=8，alpha=16，dropout=0.05；不训练 bias、embedding、lm_head |
| 可训练坐标 | 2,523,136；112 组 LoRA 参数张量 |
| 优化器 | AdamW，lr=1e-4，betas=(0.9,0.999)，eps=1e-8，weight_decay=0 |
| 调度与裁剪 | constant，warmup=0；完整全局 L2 gradient clip，max_norm=1.0 |
| 更新粒度 | 每步固定计划的五个任务；处理其全部原始有效 package，clip 一次、optimizer.step 一次 |
| 总剂量 | 每种子 400 步/十遍，每包十次；只采用唯一最终更新，不按中间效果选 checkpoint |
| 包内监督 | `trajectory_prefix_union_v1`，保留原公开响应监督域；不重新分词、不截断、不加额外全局除数 |
| token 系数 | `pi(state\|task)/(5*n_state*whole_package_target_tokens)` |
| 执行 | SDPA/FLASH_ATTENTION，gradient checkpointing，deterministic algorithms，关闭 TF32 |
| 上下文与输出 | 最大上下文 24,576；单次生成最多 2,048 token；每会话最多 32 响应/32 工具 |
| 随机反馈 | temperature=1、top_p=1、top_k=0；两次 repeat 使用登记的 trajectory seed |
| 最终评价 | 原 greedy 后端，不修改解码参数 |
| 登记软件绑定 | torch 2.7.1+cu128、transformers 5.14.1、tokenizers 0.22.2、safetensors 0.8.0 |

以上软件版本来自实验绑定工件，不是报告阶段重新查询的软件安装清单。基座自带 `generation_config.json` 中的默认采样值不等于本轮实际采用的反馈/greedy 配置。

`training_configuration` 沿用的元数据中存在历史 `arms`、A/B pools 等字段；实际执行范围以 Delayed-C 计划的三条 `runs` 为准，不能据这些继承字段推断本轮执行了 B、alpha± 或其他新条件。

共享前缀 package 执行的 dropout 相关性不同于逐响应独立 forward；原配置对此有明确说明。不能泛称它与更早的逐响应实现逐位等价。本轮比较固定使用同一执行设计。

## 5. Delayed-C 流程与贡献符号

本轮每个种子的有效流程为：

```text
配对新初始化、空Adam
  → 200步固定prior的Static策略
  → 同一step200点的一次全类G、虚拟Adam、360反馈、C-only更新
  → 200步使用更新后pi的SFT
  → 唯一步400最终点、180条greedy、封存后评分
```

前 200 步通过 prior 权重、相同配置、初始化摘要和固定日程约束为 Static 策略；本轮没有对旧 Static 的 step200 完整参数做逐位快照比较，故不把该策略约束升级成“已经验证200步参数逐位一致”。恢复所用 checkpoint 来自本轮新运行，不是从旧 Static/Full 模型暖启动。

设 `g_xz` 为当前 LoRA 坐标中类内原包 NLL 平均梯度，`U` 为含实际 Adam 历史状态及完整裁剪的单步更新量：

\[
G=\sum_x\mu(x)\sum_z\pi(z|x)g_{xz},\qquad
\bar\theta=\theta-U(G).
\]

在该虚拟点，奖励 score-function 梯度为：

\[
\widehat g_J=\frac1{360}\sum_{i=1}^{360}Q_i
\nabla_{\bar\theta}\log P_{\bar\theta}(\tau_i).
\]

正奖励轨迹包括所有实际采样 token、错误/恢复响应与 EOS，不按长度归一化；Q=0 精确省去梯度回放，但仍保留在固定 360 分母中。它不是用 SFT 正样本 mask 代替整条轨迹，也不是直接用 policy gradient 更新 Student。

\[
a=DU(G)^\top(-\widehat g_J),\qquad
C(x,z)=\mu(x)\left\langle a,
g_{xz}-\sum_{z'}\pi(z'|x)g_{xz'}\right\rangle.
\]

负号来自虚拟步 `θ−U(G)`；正 C 是该局部代理下的有利方向，不代表已经取得最终 greedy 或多步训练效用的精确导数。

C-only 使用非控制任务上的 `C/μ` 加权 RMS 构造全局尺度R（floor=1e-8），再乘任务权重得到逐任务温度。贡献指数 α_C=0.8、Novelty 指数=0，双 KL 锚系数 current=4、prior=1：

\[
R=\max\left\{\sqrt{
\frac{\sum_{x\notin control}\mu(x)\sum_z\pi(z|x)[C(x,z)/\mu(x)]^2}
{\sum_{x\notin control}\mu(x)}},10^{-8}\right\},
\qquad T_C(x)=\mu(x)R.
\]

\[
\phi_C(x,z)=0.05+0.9\,\mathrm{sigmoid}\!\left(\frac{C(x,z)}{T_C(x)}\right)
=0.05+0.9\,\mathrm{sigmoid}\!\left(\frac{C(x,z)/\mu(x)}R\right),
\]

\[
\pi^+(z|x)\propto
\exp\left\{\frac{4\log\pi(z|x)+\log\pi_0(z|x)+0.8\log\phi_C(x,z)}5\right\}.
\]

0.05 是势映射下限，不是状态概率下限。控制任务 identity 更新，不参与非控制 RMS 和势优化；无额外 clipping/概率修补。解的是冻结势函数下的双 KL 问题，工件明确不保证真实任务效用单调提高。

### 5.1 实际分布更新幅度

以下为保存的 `distribution_update.json` 标量诊断，不是本次新计算：

| seed | 非控制 `C/μ` 加权 RMS | 更新的全任务加权 TV | KL(next,current)=KL(next,prior) | 最大最优性残差 |
| --- | ---: | ---: | ---: | ---: |
| 11 | 0.01006387739 | 0.01324787594 | 0.001268199159 | 4.33e-15 |
| 29 | 0.01692234879 | 0.01296984219 | 0.001209347605 | 4.00e-15 |
| 47 | 0.01371858958 | 0.01311271474 | 0.001187310023 | 4.11e-15 |

三者均为 `FEEDBACK_UPDATE_COMPUTED`、`NONZERO_EMPIRICAL_PROXY`，控制任务精确保留，Novelty 未激活。表中RMS本轮均等于R，不是逐任务T_C；例如seed11的T_C为0.00005031938696（μ=1/200）。两个 KL 相同与本次更新前 current=prior 一致。这里约 1.3% 的 TV 是**实际分布更新幅度**，不是下面数值参考的误差 TV，更不是 movement 成功率或合格率增幅。

## 6. 数值门与故障恢复等价性

### 6.1 数值门的阈值和实测结果

前置与新点门使用事前固定的工程容差：非控制任务 `C/μ` 的相对加权 RMS 误差≤1e-3；参考与实际更新分布的加权 TV≤1e-5。原 Adam 表达式用于实际计算，稳定 FP64 参考仅用于比较，不因结果改变而静默替换公式。

前置12点全部通过：C 相对 RMS 误差约3.5583e-8至1.6818e-6，分布误差 TV约7.2792e-11至2.2707e-8。

| 新 step200 点 | 反馈正奖励项 /360 | C 相对加权 RMS 误差 | 参考分布误差 TV | a 相对 L2 误差 | 结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| seed11 | 101 | 3.486095e-8 | 9.232556e-11 | 9.306047e-8 | 通过 |
| seed29（恢复完成） | 99 | 3.970176e-8 | 7.935454e-11 | 9.288486e-8 | 通过 |
| seed47（原运行，恢复复用） | 104 | 3.900396e-8 | 7.840111e-11 | 9.292047e-8 | 通过 |

三个点 C 的符号分歧均为0，均记录 `original_Adam_used_for_actual_update=true`、`reference_not_substituted=true`。这些结果支持“本次点上原式与参考差异未实质改变 C/pi”，不证明多步代理具有正确因果效应或保证最终获益。

### 6.2 两种恢复路径

- **seed47**：原运行只保留了 step200 的完整模型/Adam/RNG，step303没有完整 checkpoint。恢复从200开始，复用原有 C-only 更新，重放201–303后继续至400。103份 `replay_equivalence` 完整覆盖201–303，均为相同更新报告 ID，记录最大绝对差0；登记容差为 atol=1e-8、rtol=1e-5。
- **seed29**：从本轮step200参数、Adam与RNG恢复，重建 G，复用已完成的360条反馈与评分，仅回放其631段正奖励响应；不再采样或重新私有评分。

运行时代码对保存的112组LoRA参数及Adam两组矩共336个张量、Adam步计数与组设置进行恢复绑定；包括CPU/CUDA/Python/NumPy RNG和调度游标。seed29首次G重建必须通过 `bitwise_original_G`，虚拟点必须通过 `exact_saved_virtual_point`，之后 outer 报告和新点数值门实际完成。

本次文档审计验证的是这些完成记录、内容 ID 和等价报告，没有重算大张量摘要。尤其原step303没有完整checkpoint，不能声称已在该点直接比较了两份完整参数/Adam状态；证据是完整step200状态恢复及103份逐步更新报告一致。

## 7. 实际执行时间线

| 时间（北京时间） | 事件 |
| --- | --- |
| 09-20 00:06:56 | seed11 原运行启动，GPU1 |
| 09-20 00:07:16 | seed29 原运行启动，GPU5 |
| 09-20 03:31:26 | seed47 原运行启动，GPU6 |
| 09-21 00:15:16 | seed11 的400步训练报告落盘 |
| 09-21 04:25:16 | seed11 最终生成与评分完成，66/180 |
| 09-21 13:42:54 | seed47 原最后完整更新为303；304仅有局部计算 |
| 09-21 13:42:56.926 | seed29 worker落盘OOM失败记录，阶段为single_epoch5_outer |
| 09-21 13:43:20 | 原协调器因seed29反馈梯度OOM记录失败并终止其余worker |
| 09-21 18:42:58 | 独立恢复计划登记 |
| 09-21 18:43:59 | seed47、seed29恢复attempt1启动，分别GPU5、GPU7 |
| 09-21 22:24:09–10 | seed47在step231保存点移交，GPU5 SFT门槛降至32 GiB |
| 09-21 23:23:05 | 积极调度与持续持久化修订登记；先接管健康worker |
| 09-22 07:22:37 | seed47实际完成400步 |
| 09-22 09:09:22 | seed29恢复outer及数值门完成 |
| 09-22 10:04:57–10:05:57 | seed47最终评测保存169/180后因容量不足正常让位 |
| 09-22 10:36:22 | 按用户指令在GPU7以32 GiB门槛进行单次续跑 |
| 09-22 10:52:20 | seed47完成180条生成并释放GPU；10:52:43评分完成，51/180 |
| 09-22 16:52:13 | seed29实际完成400步 |
| 09-22 19:25:35–36 | seed29完成180条生成并释放GPU；19:25:50评分完成，59/180 |
| 09-22 19:26:06 | 三种子汇总完成 |
| 09-22 19:26:19 | 协调器返回0，守护正常收尾；最终汇总已提交推送 |

原worker的`runs/A_delayed_c_29/failure.json`明确记录13:42:56.926的OOM异常、`stage=single_epoch5_outer`和`automatic_retry=false`；13:43:20.155是随后协调器记录失败并收口的时刻。两者不能混用，也不应只因纯文本traceback本身没有时间字段就忽略worker失败工件。对话中的ETA是各时点资源假设下的估计，不作为实际执行耗时证据。

从实际放行至最终汇总约67小时19分钟，包含并行、资源等待、恢复和保存时间，**不是GPU有效计算小时数**；本轮没有足够独占利用率/功耗记录来给出准确GPU-hours、能耗或商业API费用。

## 8. 原故障、资源修订与自动恢复

### 8.1 原始失败保留

seed29 在反馈梯度 `segmented_logp → torch.autograd.grad` 路径发生一次明确的 CUDA OOM：尝试申请92 MiB，记录只剩59.38 MiB；本进程约45.67 GiB，同卡另一进程约33.47 GiB。结合启动记录，该卡是**物理GPU5**，traceback中的GPU0是进程内编号。这支持共享显存竞争导致资源不足，不是数值公式失败的证据。

原协调器按原“不重试、失败即收口”策略停止其他worker；seed47没有OOM traceback，最后完整步303，原计划记录step304局部工作的 optimizer 更新数为0。原目录、failure和日志均保留，恢复成功不覆盖原失败事实。

### 8.2 资源策略的版本顺序

| 修订阶段 | SFT容量 | 反馈回放容量 | 最终生成容量 | 主要变化 |
| --- | ---: | ---: | ---: | --- |
| 初始恢复计划 | 60 GiB | 60 GiB | 72 GiB | 每完成更新/响应保存；每run最多3次启动/资源重试 |
| GPU5 SFT修订 | seed47为32 GiB | 60 GiB | 72 GiB | 只调整seed47 SFT，不改数学实现 |
| 积极自动恢复 | 32 GiB | 50 GiB | 56 GiB | 去除总启动次数硬上限；资源退避、按阶段重排；CPU评分不占GPU |
| GPU7一次性尝试 | 不变 | 不变 | 仅seed47一次32 GiB | 定向补完11条，不全局修改评测门槛 |

自身容量定义为 CUDA空闲显存+本进程PyTorch已保留显存；冷启动多留1 GiB。OOM后对应阶段门槛增加4 GiB、最高76 GiB，并以60/120/240/480/900秒退避。租约仅协调本实验worker，不是全机GPU独占，也不驱逐其他任务。

恢复期间 worker 启动计数为17次（seed29 attempts1–9、seed47 attempts1–8，含两次CPU评分）；另有原训练worker3次。此口径不含原采样子进程、controller和watchdog。

14份新autorun结果中有4次返回0、10次返回43，不能把43都叫失败：其中8次为保存边界的容量让位、2次为训练完成后正常切阶段；另有3次登记的旧worker控制移交。恢复日志未发现新的OOM，最终phase failure计数均0。没有通过自动重试掩盖数值或数据错误。

### 8.3 GPU7尝试的实际结果

登记时GPU7空闲35,767 MiB（约34.93 GiB），低于原最终生成门槛。用户明确授权单次尝试后，采用自身32 GiB/冷启动33 GiB，复用已有169条结果，不改变精度、上下文、工具预算、模型参数点或greedy实现。

attempt7确实生成indices169–179共11条；11份meter均与completed记录对应，合计187次调用意图、187次返回、187次已提交调用，10,769个输出token。最后一条于10:52:20完成。seed29未因该次控制移交被停止。

这证明在当时共享卡环境中能以该准入策略补完剩余11条；不证明全部540条长上下文工作负载的峰值均低于32 GiB，也不意味着当前所有后续评测已全局采用32 GiB。

## 9. 有效剂量、物理开销与生成账目

### 9.1 预登记、恢复修订与实际量分别列示

| 项目 | 原登记 | 最终观察/说明 |
| --- | ---: | --- |
| 新训练运行 | 3种子 | 保持11/29/47，没有新增或重选种子 |
| 有效optimizer更新 | 1,200 | 1,200；各最终模型400步 |
| 原物理optimizer预算 | 1,200 | 后续授权恢复修订；完整物理更新下界1,303 |
| 随机反馈会话 | 1,080 | 1,080；恢复新增反馈/重新私有反馈评分均0 |
| 最终greedy会话 | 540 | 540；恢复完成其中360条 |
| 总会话 | 1,620 | 1,620；同一已完成会话不重新生成 |
| 原generate调用上限 | 51,840 | 已提交调用26,665 |
| 恢复最终新增调用上限 | 11,520 | 实际6,413，仅seed29/47最终生成 |
| 未提交最终尝试的额外调用授权 | 积极修订另设每恢复run 5,760 | 两run上限11,520；实际计量上界为0 |
| 原完整类G遍历 | 3次 | 另有seed29一次成功重建；不与前置审计6次混算 |

早期恢复的三次启动上限已被后续显式登记替代。原计划的“不从旧checkpoint恢复”“不提高物理预算”等要求不能在事后假装未变；本轮是保留失败记录、以用户授权的恢复计划完成，最终模型的有效剂量仍固定。

最终矩阵里的 `new_feedback_sessions=0` 指**恢复阶段新增量**，不是整轮没有做反馈。生成调用低于原上限，也不能掩盖物理训练次数已经增加。

### 9.2 完整optimizer报告对应的实际训练账目

以下从已保存的 `updates/*/report.json` 聚合，而不只引用计划：

| 阶段 | 完整更新 | packages/rows | sequence tokens | target tokens |
| --- | ---: | ---: | ---: | ---: |
| 原seed11 | 400 | 35,470 | 179,422,990 | 9,919,440 |
| 原seed29 | 200 | 17,735 | 89,711,495 | 4,959,720 |
| 原seed47 | 303 | 26,869 | 135,978,450 | 7,513,816 |
| 恢复seed29 | 200 | 17,735 | 89,711,495 | 4,959,720 |
| 恢复seed47 | 200 | 17,735 | 89,711,495 | 4,959,720 |
| **完整报告对应物理合计** | **1,303** | **115,544** | **584,535,925** | **32,312,416** |
| **最终有效三条训练轨迹** | **1,200** | **106,410** | **538,268,970** | **29,758,320** |

已知重复的103步对应额外9,134包、46,266,955序列token、2,554,096监督token。上述物理账目只覆盖完整更新报告，不含step304局部工作、OOM中的部分工作、全类G和反馈梯度重放等，因此不是全部实验计算量。

完成工件明确保留 `physical_completed_optimizer_updates_lower_bound=1303`、`physical_exact_count_not_claimed=true`。已知额外重复完整更新及新journal中完成状态不明的update intent计数均0，不等于已经证明历史所有阶段的物理总量恰好只有1,303次。

seed29恢复梯度报告记录631段响应、99条正奖励轨迹、30,167个带参数导数的采样token、60,334 cached forward target positions；261条零奖励梯度被精确省去但仍在360分母中。原失败前已处理但未保存累加器的58段响应属于重复回放成本，不能称为631条新增生成。

### 9.3 已封存生成调用与输出token

| 阶段 | 会话 | generate调用 | generated tokens |
| --- | ---: | ---: | ---: |
| seed11 feedback | 360 | 5,863 | 363,740 |
| seed29 feedback | 360 | 5,714 | 334,844 |
| seed47 feedback | 360 | 5,721 | 326,927 |
| **feedback合计** | **1,080** | **17,298** | **1,025,511** |
| seed11 final | 180 | 2,954 | 137,701 |
| seed29 final | 180 | 3,046 | 140,544 |
| seed47 final | 180 | 3,367 | 167,961 |
| **final合计** | **540** | **9,367** | **446,206** |
| **总计** | **1,620** | **26,665** | **1,471,717** |

恢复前已完成20,252次调用、1,163,212输出token；恢复新增6,413次调用、308,505输出token。这里是本地Student的 `model.generate` 计量，不是DeepSeek商业API请求数；输出token也不是所有prompt、前缀重算、反传或完整算力成本。

## 10. 主结果的配对分解与分组结果

### 10.1 每种子的同任务配对

`0→1` 表示 Static 不合格而 Delayed-C 合格，`1→0` 反之。

| seed | 0→1 | 1→0 | 两者均1 | 两者均0 | 净差 | 差值（百分点） |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 11 | 9 | 10 | 57 | 104 | −1 | −0.5556 |
| 29 | 3 | 10 | 56 | 111 | −7 | −3.8889 |
| 47 | 15 | 1 | 36 | 128 | +14 | +7.7778 |
| **合计** | **27** | **21** | **149** | **343** | **+6** | **+1.1111** |

净增6条由27条改善与21条退化共同构成，不是所有原有成功均保留。按同一任务跨三个种子联合观察，140题三个种子都无变化，20题只有非负变化且至少一个正差，15题只有非正变化且至少一个负差，5题既出现正差又出现负差。这些只是事后描述，不提供独立推断。

### 10.2 分组总表

每组分母为60道固定任务×3种子=180条评分记录：

| group | Static | C-only | Full | Delayed-C | D−Static | 改善 | 退化 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| composition_required | 74 | 68 | 68 | 77 | +3 | 17 | 14 |
| dual_sufficient | 96 | 87 | 85 | 99 | +3 | 10 | 7 |
| other_financial | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

两个非零组各贡献+3；other_financial在所有条件和种子中均为0。本次没有重新查看其原始失败会话或重新评分，因此不能由全零直接确定是模型能力、标签、工具、材料还是评分规则的原因；也没有删除该组或改变分母来提高合格率。

### 10.3 分组逐种子表

每行分母为60：

| seed | group | Static | C-only | Full | Delayed-C | D−Static |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 11 | composition_required | 33 | 33 | 31 | 32 | −1 |
| 11 | dual_sufficient | 34 | 29 | 29 | 34 | 0 |
| 11 | other_financial | 0 | 0 | 0 | 0 | 0 |
| 29 | composition_required | 31 | 16 | 19 | 27 | −4 |
| 29 | dual_sufficient | 35 | 29 | 29 | 32 | −3 |
| 29 | other_financial | 0 | 0 | 0 | 0 | 0 |
| 47 | composition_required | 10 | 19 | 18 | 18 | +8 |
| 47 | dual_sufficient | 27 | 29 | 27 | 33 | +6 |
| 47 | other_financial | 0 | 0 | 0 | 0 | 0 |

### 10.4 辅助比较与解释边界

Delayed-C相对原C-only为+21/540（+3.8889个百分点），相对Full为+23/540（+4.2593个百分点）。这些比较描述本轮保存结果；它们不能替代预登记主比较，也不能把Novelty未激活的Delayed-C结果改称Full/Novelty成功。

本报告没有把540条记录当独立伯努利样本构造置信区间，没有在事后追加显著性检验，没有把三个seed中的最好一个作为候选替代总体结果。即使Q由独立CPU进程判定，反馈元优化、旧开发分析、重复任务和来源簇依赖仍然存在。

## 11. 保存、自动恢复与可复现范围

### 11.1 路径约定

```text
ROOT = /tmp/data-synthesis-fixed-kernel-parallel-tail-20260914
BASE = ROOT/trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/anchored_sources_20260916
OLD  = BASE/delayed_C_20260919
REC  = BASE/delayed_C_recovery_20260921
RAW  = /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/delayed_C_recovery_cache_20260921
AUTO = RAW/aggressive_autorun_20260921
```

数据盘保留seed29/47各200个完整update checkpoint、seed29的631个反馈累加器checkpoint、population、最终adapter/参数点、会话和评分。每步checkpoint包含模型、Adam、RNG、游标及更新报告；新会话按完整会话提交，先数据刷盘再提交完成记录。旧目录及早期 `preservation_*` 快照保留。

控制JSON通过临时文件、fsync、原子提交/替换及父目录fsync持久化。登记、结果和封存记录采用不可变提交：相同内容可复用、冲突内容拒绝覆盖；运行state、heartbeat、meter等状态允许原子更新。反馈与训练在已保存边界让位，资源不足不表示回滚已提交的工作。生成全部封存后GPU worker退出，再启动CPU评分。

Git中不提交模型、原始会话、梯度矩阵和大checkpoint；本次提交的是详细说明、派生聚合量、路径/内容摘要及只读复核代码。**仅clone仓库不足以完整复现**，还需要原始材料、模型和RAW数据盘工件。

REC最终目录是指向RAW的绝对软链接；manifest还包含工作树相对路径，启动命令也引用原`/tmp/...`。持久化意味着数据和恢复副本已保存，不意味着可以任意删除临时工作树后无需恢复路径就直接运行。整机重启自启动服务未安装，守护自身被杀、磁盘不可写等情形也不能宣称已全自动解决。

### 11.2 需特别注意的字段语义

1. autorun worker结果的 `at` 在执行前设置，结束时只更新phase/returncode等；例如GPU7结果文件的10:36:25不是生成结束时间。meter的`at`也为会话开始时刻。结束时间应使用`trajectory_complete`、generation manifest的`at`、scoring的`finished_at`。
2. 新manifest中的 `actual_sampling_GPU_workers=1` 是单worker路径常量，不表示全程只用过一张物理卡。seed47最终生成实际跨GPU0和GPU7顺序完成。
3. GPU编号需结合launch中的UUID解读，进程内CUDA0不等于物理GPU0。
4. `new_feedback_sessions=0`、`interrupted_final_generate_call_upper_bound=0`均有明确阶段/计量口径，不能泛化为没有历史反馈、没有训练重放或全部故障成本为0。
5. 旧设计文档中的“尚待执行”“最多3次启动”“最终72 GiB”等是当时快照；本报告与带时间的登记修订解释最终执行状态，不追溯覆盖旧记录。

## 12. 证据链与复核入口

### 12.1 关键内容身份

| 工件 | 内容 ID |
| --- | --- |
| 原A计划 | `anchored_registered_A_plan:a48f25774415bafa7f1fcbfdce72de51aebcbb1df3b320d37af2bdebba31f9b1` |
| Delayed-C计划 | `delayed_C_registered_plan:b632bc2cdcfe0ed9b3470e2c0efc3bf64c007a7adbfe0f5f4d93cbc4655ddd04` |
| 实际准入 | `delayed_C_actual_admission:c255798d61da57b6529947a9e608d29f7168e279d7b0c53ab8d284c5dab24228` |
| 恢复计划 | `delayed_C_recovery_plan:2248bdf67dab199b0b97a818e5fad51895524913ff89c1702d3d24c11a6864d9` |
| 积极恢复修订 | `delayed_C_aggressive_autorun:35d514700597ec2b5eaf4544038eb81351dc65a373a0a3a9babd224c2d8fbbcd` |
| GPU7单次修订 | `delayed_C_GPU7_admission_trial:32483808251eabdaefedf1672a353dc4b37cb18c18c56e5328393e5e9b66894e` |
| 最终矩阵 | `delayed_C_recovered_matrix:3beabcba5e1bfd94d82789cd840e4b807877bb903ecd0f1b726ea1978f171bde` |
| 共同source manifest | `source_view_manifest_v2:a947dbdd028d6ac68da16c168de26544187fedd4e10c6a2602a51868b67f10ea` |
| Static评分汇总 | `given_sources_final_report:a358507ef3de20e1a82dca176ad94622b1ef9b07248dd564f6b1519020de9e7c` |

每个种子的运行、生成、评分、参数点ID，以及文件字节数/SHA-256见机器可读附件。其 `ROOT/`、`RAW/` 前缀按上节展开；部分工件不跟踪进Git，GitHub单独浏览不保证可访问这些路径。

### 12.2 优先核查的文件

| 审计问题 | 主要工件 |
| --- | --- |
| 是否事前登记、是否准入后才启动 | `OLD/plan.json`、`OLD/admission.json`、`OLD/launches/*.json`、代理审计plan/report |
| 原失败是否保留 | `OLD/runs/A_delayed_c_29/failure.json`、`OLD/coordinator_failure.json`、`OLD/A_delayed_c_29.log`、seed47原更新与局部日志 |
| 恢复是否另行授权、是否更改有效剂量 | `REC/plan.json`、GPU5修订、`AUTO/registration.json`、GPU7修订 |
| 是否完成固定180任务且无挑选 | 各final generation manifest、scoring report、run report；以task_id和session_id关联 |
| Static原分数从何而来 | `ROOT/trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/given_sources_value_20260915/report.json` 的 `A_alpha0_*` outcomes |
| 旧C-only/Full是否被改写 | `BASE/registered_A/report.json` 与对应final scoring reports |
| 重放是否完整、是否只是计划声称 | `REC/runs/A_delayed_c_47/replay_equivalence/0201…0303.json` |
| 完整物理更新与token账目 | 原/恢复 `updates/*/report.json`；附件中的分段ledger与inventory摘要 |
| 32 GiB尝试是否真做了新工作 | GPU7登记、`0007_0169…0179` 的meter/completed、`0007.log` |
| 是否完成释放与正常退出 | final manifest、score finished_at、`AUTO/complete.json`、`AUTO/watchdog_status.json` |

### 12.3 不触发实验的复核命令

在原工件可访问的环境中，从ROOT执行：

```bash
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/.venv/bin/python \
  trusted_data_synthesis/scripts/audit_fixed_kernel_delayed_C_report_20260922.py \
  --root /tmp/data-synthesis-fixed-kernel-parallel-tail-20260914
```

脚本仅使用标准库读取元数据并把结果输出到stdout；不会导入torch、调用CUDA、访问网络、启动worker或重新评分。可用`--raw-root`指定持久数据目录；`--output 新文件.json`只创建不存在的新附件，不覆盖原实验工件。

脚本核验记录内容ID、固定任务及分组、Q二值性、保存分数合计、生成/评分/运行/参数点关联、逐项session对应、生成调用与输出token汇总、计划/完成矩阵关联、完整更新报告连续性、103步复现、GPU7 meter归属和正常退出。原始大张量、原会话工具重放和私有评分器的语义正确性不在这次轻量复核范围。

本次导出器的4项必要CPU单元测试通过，覆盖重复/缺失任务、错误分组或非二值Q、配对退化项及分母保留、内容ID篡改拒绝；实际工件校验通过。附件逐文件索引包括188份元数据，另对1,303份完整更新报告做内容ID校验与分段账目聚合；为避免正文堆积逐步明细，每段保存其有序路径、文件SHA及record ID清单的整体摘要。

附件中的文件SHA和内容ID用于本地一致性与追踪，不构成外部时间戳或第三方真实性证明。运行代码曾做的全张量验证与本次只读取其结果的复核是不同证据层级，应保持区别。

## 13. 结论、审计保留项与收口

### 可支持的结论

- 三个预定种子均完成，固定训练/评价剂量和任务集合闭合；恢复无新增种子、无新增随机反馈或重评原反馈。
- 已保存结果与最终矩阵一致：Delayed-C为176/540，Static为170/540；预登记方向判据为正。
- 正向汇总由seed47的收益驱动，另外两种子均为负差，且存在21条从合格转为不合格的配对记录。
- 运行时数值门及保存的恢复等价报告支持原数学实现未因资源调整而被替换；资源策略修改与统计样本/有效剂量分开登记。
- 故障、额外训练重放、资源等待和阶段切换被保留并分别计量；GPU7最后11条评测确实完成，不只是进程启动成功。

### 不能支持、或本次尚未核验的结论

- 不支持统计显著、跨种子稳定、全任务普遍提升或独立确认成功。
- 不支持将C-only辅助差异归为纯单因素“时机”因果效应，也不支持改写原Full/Novelty结论。
- 不支持540个独立任务的推断、开发集未参与学习、或独立检索泛化结论。
- 不支持原物理预算未增加、精确GPU-hours/能耗、全阶段显存峰值≤32 GiB。
- 没有重新加载checkpoint做完整张量核验，没有重新执行评分器或调查other_financial全零组的错误原因；没有新增显著性分析或确认实验。

若后续要检查全零组原因、比较真实多步代理效度或进行独立确认，应另列方案和证据范围，不以修改本轮评分、移除任务、重复筛种子或扩大本轮结论代替。

本轮以“**完成预定实验、保留失败与预算修订、观察到有限开发集正向汇总、尚无独立确认**”收口。报告阶段未开启新实验，未改变已发布结果。
