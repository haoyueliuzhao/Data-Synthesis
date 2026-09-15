# 固定材料核方法分布训练价值实验：详细结果报告

报告日期：2026-09-15。文中运行时间均为北京时间（UTC+8），特别标注 UTC 的原始时间除外。

本报告汇总已经完成并封存的原轮实验，结果来源提交为 `9cff3a40b0`。本文是追加说明，不修改原始训练、生成、评分、选择或归档结果。用户随后授权“提高预算重新评估检验”；该项属于新的独立预算复评，不能回填本轮结果，见第 13 节。

## 1. 摘要与结论边界

本轮检验的问题是：在任务总体、合格训练材料、模型、训练剂量和评估合同固定时，仅调整 endpoint 与 movement 两类实际解题方法的训练概率权重，是否能够提高完整财务轨迹的合格率。

| 项目 | 本轮实际结果 |
| --- | --- |
| 固定采集登记 | 10,240 / 10,240 个会话终态闭合 |
| 可训练原包 | 7,076 个：A 池 3,547，B 池 3,529 |
| 可消费 sealed 原包 | 2,342 个；没有转入训练 |
| 共同干预支持 | 120 个目标任务全部具有两池双方法支持；全局质量移动 10% |
| A 训练 | 9 / 9 完成；每模型 10 轮、400 次全局更新 |
| A 开发集生成与评分 | 9 模型 × 180 题 = 1,620 会话，全部生成和评分工作流闭合 |
| 主指标 | 三臂、三个种子、三个评估分组全部为 0 |
| 直接评分原因 | 1,620 / 1,620 均为 `no_final` |
| 会话运行时终止 | 响应预算耗尽 1,601；provider error 19，后者全部对应上下文拒绝 |
| 方向选择 | `STOP_RETAIN_BASELINE`，保留 alpha0 |
| B 训练、确认实验 | 均未执行，符合预设条件分支 |

**科学结论：本轮原评估合同下，没有观察到可用于选择干预方向的正收益。**由于所有会话都没有记录到可识别的 Final，本轮没有形成可比较的完整作答结果，不能把主指标全零解释为“模型所有数值都答错”“endpoint 与 movement 已证明等效”或“VTDO 已被证明无效”。

**工程结论：材料、训练、离线评分和封存链路完成；轨迹合并减少了计算预算，八卡尾任务的实测墙钟明显短于单卡任务。**后者不是相同任务、相同负载下的受控加速比较。工程执行完成不等于模型任务成功，训练损失降低也不等于开发集财务资格改善。

## 2. 实验目标、总体与三臂干预

### 2.1 固定训练总体

训练总体为 200 个任务，各任务概率权重相同，`mu(x)=1/200`：

| 训练 family | 任务数 |
| --- | ---: |
| annual_flow | 40 |
| stock_rollforward | 40 |
| company_defined_metric | 40 |
| control | 80 |
| 合计 | 200 |

前三类合计 120 个目标任务；80 个控制任务保留共同的 neutral 合同，不通过删题或偏移控制任务质量增强干预。评估使用的 `dual_sufficient / composition_required / other_financial` 是另一套任务分组，不能与上述训练 family 一一等同。

### 2.2 三臂唯一的科学干预

| 训练臂 | endpoint 方法概率权重 | movement 方法概率权重 | 相对基线方向 |
| --- | ---: | ---: | --- |
| alpha0 | 1/2 | 1/2 | 基线 |
| plus | 1/3 | 2/3 | 偏向 movement |
| minus | 2/3 | 1/3 | 偏向 endpoint |

alpha0 同样是经过正式微调的 Student，不是未经微调的基础模型。三臂遍历同池的同一批合格原包，只调整损失系数，不给某一臂增加原包、监督 token、训练轮数或更新次数。方法身份取自实际轨迹资格与映射，不直接把 Teacher 请求中的路线指导当作实际采用的方法。

定义 S 为 A、B 两池中均有 endpoint 和 movement 合格训练支持的目标任务集合。本轮材料门记录 `|S|=120`，覆盖全部目标任务；不存在空的池×任务训练支持。相对基线的全局质量移动为：

`Delta_mass = |S| / (6 × 200) = 120 / 1200 = 10%`。

这高于事前 5% 的剂量门。剂量门通过说明预设干预可以按规定实施，不等于已经具备检出某一效果量的统计功效。S 决定干预作用范围，不是根据成功结果保留训练子集。

### 2.3 本轮与完整 VTDO 的关系

本轮是有限材料核上三种固定方法边际的训练价值基线，尚不是由当前 Student 和优化器状态反馈驱动的完整 VTDO 自适应闭环。这里没有在训练中持续估计并更新 `Contribution、Novelty、Phi、pi_next`，也没有把复杂性、罕见程度或组件数量冒充训练贡献。

因此，固定 plus/minus 没有显示收益，不推出所有任务条件化分布更新均无效；人工三臂也不是 VTDO 可实现收益的 oracle 上界。本报告不将通用组件已经实现或局部工程验证通过，表述为本轮已经落实并验证完整 VTDO。

## 3. A/B 材料角色、采集闭合与预算修订

### 3.1 A、B 不是通常意义上的训练集和测试集

A 和 B 是在同一组 200 训练任务上分别采集的两批训练材料，原包不混用。A 用于训练三臂并在开发集选择方向；如果选择出严格正方向，再用 B 的独立材料重训基线与候选以复验。独立评估题另有固定的 180 题开发集和 720 题确认集。

每池在 120 个目标任务上固定采集每题 endpoint 16 次、movement 16 次；80 个控制任务每题 neutral 16 次。每池共 5,120 次，两池共 10,240 次。每个池×任务×指导 cell 的 replicate 0–11 在结果产生前分配为 train，12–15 分配为 sealed，不能将 sealed 成功实例补进 train。

sealed 原包也不是本轮 720 道确认评估题；它是材料采集中的独立封存角色。

### 3.2 实际完成量及其分母

| 采集/材料字段 | 实际值 | 解释 |
| --- | ---: | --- |
| registered_sessions | 10,240 | 原固定登记分母 |
| finished_sessions | 10,240 | 原登记会话均有终态，不表示全部财务成功 |
| inherited_finished_sessions | 9,968 | 原已结束会话和资格结果继承，不重复请求或重新评估 |
| newly_generated_session_records | 272 | 本次预算续采处理的原未完成 slot |
| new_HTTP_request_count | 1,401 | 本次续采新增的实际 HTTP 请求 |
| actual_HTTP_request_count | 59,146 | 闭合 generation report 的累计实际 HTTP 请求字段 |
| 合格可训练原包 | 7,076 | A 3,547；B 3,529 |
| 合格可消费 sealed 原包 | 2,342 | 不进入训练核 |

272 个续采会话的报告中，270 个记有 first Final，2 个为 transport 会话终态；这仅是新增部分的计数，不能把 270 当成全 10,240 会话的 Final 总数或财务成功总数。

材料门为 `PASS`，训练门和剂量门也为 `PASS`；`all_valid_train_originals_retained=true`，`sealed_promoted=false`。本轮将所有合格且完整可消费的 train 原包纳入核，没有以“最好若干条”替代全部材料。10,240 个终态与 7,076 个训练包是不同层次的分母，不能直接当作同一成功率的分子分母。

### 3.3 预算并非原始未修订预注册

用户在原预算停止后授权提高预算完成采集。相关材料用途合并预算由 250,000,000 提高至 350,000,000 token，共同钱包上限仍为 1,000,000,000。原 STOP、原失败、未知用量保守扣款和父实验报告保留，不回写为 PASS。

闭合报告的 `kernel_conservative_debit=246,029,692`，`completion_conservative_debit=6,323,646`，`common_conservative_debit=631,739,586`。这些是各自账本范围下的保守 token 扣款字段，不是人民币/美元费用，也不应不加解释地等同于已知实际返回 token 的精确和。尤其不能仅因核字段小于 250M，就否认执行过程中涉及在途保留、历史用途和独立续采授权的预算修订。

原已结算响应前缀仅本地重放，不重复发送 HTTP；未知用量请求未借本次授权重试或退还保守扣款。报告显式记录 `amended_budget_not_original_preregistration=true`。

## 4. 正式训练配置与监督目标

| 配置项 | 实际执行设计 |
| --- | --- |
| 基础模型 | Qwen2.5-7B-Instruct |
| 基座 / 可训练参数精度 | 冻结 BF16 基座 / FP32 LoRA |
| LoRA 模块 | q_proj、v_proj |
| LoRA rank / alpha / dropout | 8 / 16 / 0.05 |
| 优化器 | AdamW；betas=(0.9, 0.999)，eps=1e-8，weight decay=0 |
| 学习率 | 1e-4，常数，warmup=0 |
| 全局梯度裁剪 | 最大范数 1 |
| 配对种子 | 11、29、47 |
| 训练剂量 | 200 题 × 10 轮；每轮 40 步；每模型 400 次全局更新 |
| 每个全局更新 | 三个目标 family 各一题，加两个 control，共五题的全部原包 |
| 单轨迹 microbatch | 1 |
| 内存/注意力优化 | 非 reentrant gradient checkpointing；FLASH_ATTENTION SDPA |
| 原序列边界 | 最大 24,576 token，不截断原包 |

每个目标 token 的监督系数为：

`pi(state | task) / (5 × n_state × whole_package_target_tokens)`。

分母中的目标 token 数来自整个原包所有正向响应，而不是当前响应行长度。五题全部原包的梯度累加后仅 clip 一次、step 一次；没有再次按 token 数、包数或 world size 做未经设计的平均。正向监督为实际成功公开工具响应和首个 Final，历史中的失败响应和反馈仍作为上下文保留，但不被提升为正确 target。

此前被暂停的逐响应训练没有可用于恢复的中间 AdamW 检查点；轨迹优化后的正式执行从相同基座与配对种子重新开始，没有继承原部分更新。随后接入八卡尾任务时，已经运行的八个轨迹版 Student 没有重启，其完成后的原始报告按原字节导入。

## 5. 工程优化与实际计算量

### 5.1 整轨迹合并和只读缓存

原逐响应训练在同一包上反复计算公共前缀。优化检查原输入前缀和监督位置一致后，使用最后完整轨迹及目标位置并集；不兼容包原本允许 fallback。本次 7,076 个训练包全部融合，fallback=0，包和监督目标均未删减。

| 每轮指标 | A 原响应行实现 | A 轨迹实现 | B 原响应行实现 | B 轨迹缓存预算 |
| --- | ---: | ---: | ---: | ---: |
| 原包数 | 3,547 | 3,547 | 3,529 | 3,529 |
| forward 序列数 | 19,574 | 3,547 | 19,423 | 3,529 |
| 序列 token | 84,347,252 | 17,942,299 | 83,636,655 | 17,811,694 |
| 监督目标 token | 991,944 | 991,944 | 982,088 | 982,088 |

A 每轮序列 token 计算预算约缩减至原来的 21.27%，而监督目标保持不变。24 CPU 的实际缓存转换阶段约 6.55 秒；这不是整个优化开发、暂停或准备阶段的总耗时。数字缓存为 150,912,612 字节，包索引为 7,397,390 字节；该阶段没有重新分词、Teacher/API 请求或 Student GPU 操作。

实际 A 每模型完整十轮处理 179,422,990 序列 token、9,919,440 监督目标 token、35,470 次原包呈现。九个模型合计 1,614,806,910 序列 token 和 89,274,960 目标 token。B 只准备了缓存，未训练，不能将 B 的预算计入本轮实际 Student token 或 GPU 时间。

因 LoRA dropout=0.05，逐响应与整轨迹实现改变前缀随机实现的相关性，因此是有记录的新执行设计，不是逐位等价的旧训练续跑。九个最终 A 模型统一使用轨迹表示。

### 5.2 第九项八卡并行

只有 A/minus/47 采用八卡后端。八张卡各持有完整 BF16 基座与 FP32 LoRA，按原全局五任务计划将轨迹分配到 rank，本地累加加权损失梯度，再执行 NCCL `SUM`、全局 clip 和一次 AdamW 更新；不除以 world size。最终仍是 400 次全局更新，不是 8 × 400 次训练步。

实际八个 rank 全部退出码为 0。运行记录的 dropout 策略为原单卡串行 native Philox offsets，报告保留掩码重放声明；本报告没有追加全模型掩码逐位审计。即使掩码路径匹配，FP32 归约顺序仍发生变化，不能声称梯度、优化器状态或最终参数逐位相同。正式结果保留混合配置 lineage，不把前八个模型历史配置改写成八卡配置。

GPU 调度先后修订为：尾任务每卡至少剩余 32 GiB 即可启动，不要求利用率为 0%；评估每卡至少剩余 76 GiB，不要求利用率为 0%。训练门槛不能直接套用于显存占用更高的评估。服务器期间存在其他用户作业共享 GPU，其负载变化会影响吞吐；未干预其他用户进程。

最后一个开发评估实际启动时观测剩余显存 81,154 MiB、利用率 0%，所以其成功启动不能单独证明放宽利用率条件在本轮产生了实测收益。

## 6. 九个训练模型的完成时间与训练损失摘要

训练墙钟由各 `started.json.time` 到 `report.json.finish_time` 计算；每项均为 `COMPLETE_FINAL_CHECKPOINT`、400 更新、10 轮、自动重试 0。

| 模型 | 开始（北京时间） | 完成（北京时间） | 墙钟小时 | GPU 数 | 首 5 步平均 weighted_loss | 末 5 步平均 weighted_loss |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| A_alpha0_11 | 09-14 11:32:01 | 09-15 01:23:07 | 13.85157 | 1 | 0.147744 | 0.016658 |
| A_plus_11 | 09-14 11:32:02 | 09-15 00:32:02 | 13.00024 | 1 | 0.152458 | 0.017192 |
| A_minus_11 | 09-14 11:32:02 | 09-15 00:30:04 | 12.96738 | 1 | 0.143090 | 0.016364 |
| A_alpha0_29 | 09-14 11:32:02 | 09-15 00:31:17 | 12.98755 | 1 | 0.148542 | 0.020660 |
| A_plus_29 | 09-14 11:32:02 | 09-15 00:32:59 | 13.01560 | 1 | 0.153192 | 0.020744 |
| A_minus_29 | 09-14 11:32:03 | 09-15 00:30:20 | 12.97134 | 1 | 0.143810 | 0.019756 |
| A_alpha0_47 | 09-14 11:32:03 | 09-15 00:29:06 | 12.95086 | 1 | 0.140621 | 0.017128 |
| A_plus_47 | 09-14 11:32:03 | 09-15 00:31:51 | 12.99661 | 1 | 0.147300 | 0.018051 |
| A_minus_47 | 09-15 01:23:30 | 09-15 03:02:22 | 1.64760 | 8 | 0.133554 | 0.016300 |

八个单卡任务墙钟中位数约 12.9921 小时，范围 12.9509–13.8516 小时；八卡尾任务约 5,931.365 秒，即 1 小时 38 分 51 秒。单卡中位数与尾任务的观察墙钟比约 7.89 倍，但它比较了不同臂、种子和启动时段负载，不是受控硬件加速基准，更不意味着费用下降 7.89 倍。

按“名义 GPU 数 × 任务墙钟”统计，八个单卡任务合计约 104.7412 GPU 小时，八卡尾任务约 13.1808 GPU 小时，正式 A 训练合计约 117.9220 GPU 小时。这不代表独占 GPU 利用时或计费量，也未包括旧被中止执行、开发检查和评估。

损失摘要仅取已有第 1–5 步与第 396–400 步报告，不是完整学习曲线。其下降说明所抽取训练损失变小，不能单独证明收敛、泛化或工具使用能力改善。不同臂损失权重不同、不同步题目也不同，不能按某臂数值更小就判其更优。

## 7. 开发集生成、评分资源与时间

九个生成任务各包含固定 180 题；最多八个单卡任务并行，第九个等待槽位。下表墙钟从 job `launched_at` 到进程退出观测 `finished_at`，含模型加载及调度观测延迟，不是纯 decode 时间。

| 模型 | 启动（09-15） | 退出观测（09-15） | 墙钟秒 | generated_tokens | 实际模型 generate 调用 |
| --- | --- | --- | ---: | ---: | ---: |
| A_alpha0_11 | 03:02:26 | 09:12:19 | 22,192.955 | 499,472 | 5,712 |
| A_plus_11 | 03:02:26 | 08:42:58 | 20,432.008 | 462,478 | 5,760 |
| A_minus_11 | 03:02:27 | 08:34:38 | 19,931.506 | 441,609 | 5,726 |
| A_alpha0_29 | 03:02:27 | 08:31:18 | 19,730.873 | 440,098 | 5,723 |
| A_plus_29 | 03:02:27 | 09:04:39 | 21,731.440 | 478,248 | 5,731 |
| A_minus_29 | 03:02:28 | 08:43:38 | 20,470.782 | 458,056 | 5,736 |
| A_alpha0_47 | 03:02:28 | 09:11:59 | 22,170.913 | 493,334 | 5,720 |
| A_plus_47 | 03:02:28 | 08:54:58 | 21,150.306 | 478,921 | 5,760 |
| A_minus_47 | 08:31:18 | 14:57:09 | 23,151.366 | 511,046 | 5,748 |

合计 `generated_tokens=4,263,262`，`public_content_tokens=4,211,718`，实际模型生成调用 51,616 次；callback 尝试 51,635 次，多出的 19 次在模型生成前因上下文拒绝停止。这些是本地 Student 推理统计，不能将 generate 调用次数误写成 DeepSeek HTTP 请求次数。

生成阶段从 03:02:26 到 14:57:09，约 11 小时 54 分 43 秒；各单卡生成 worker 墙钟累计约 53.0450 小时。尾项到 08:31:18 才获得第一个空闲槽位，随后仍需运行自身全部 180 题。串行工具会话和最后一个模型的排队，是本轮后半段墙钟的重要组成。

生成工作流记录九项全部完成、无工作流 failure、无未启动任务、自动重试为 0；原有评估 worker 未重启，未将部分输出冒充完整结果。所有生成 worker 退出 0。**这些是进程与工作流成功，不表示每个会话获得 Final；19 个上下文拒绝作为正式会话结果留在评分分母中。**

开发评分使用生成封存后的公开会话与离线私有判定材料，不调用 GPU、Student 或外部模型 API；主线程在九份评分闭合后才做方向选择。原轮约 14:58 完成评估与选择收口。

## 8. 主结果、辅助状态与完整分母

主指标是三组等权的完整轨迹财务资格：

`U(arm, seed) = (qualified_composition/60 + qualified_dual/60 + qualified_other/60) / 3`。

实现要求 `financial_valid == complete_trajectory_qualified`。unknown、无 Final、运行错误全部保留固定分母；主财务资格不要求细映射状态必须完成，`fine_mapping_required_for_primary=false`。

| 模型 | composition_required | dual_sufficient | other_financial | 全部合格 / 会话 | U |
| --- | ---: | ---: | ---: | ---: | ---: |
| A_alpha0_11 | 0/60 | 0/60 | 0/60 | 0/180 | 0 |
| A_alpha0_29 | 0/60 | 0/60 | 0/60 | 0/180 | 0 |
| A_alpha0_47 | 0/60 | 0/60 | 0/60 | 0/180 | 0 |
| A_plus_11 | 0/60 | 0/60 | 0/60 | 0/180 | 0 |
| A_plus_29 | 0/60 | 0/60 | 0/60 | 0/180 | 0 |
| A_plus_47 | 0/60 | 0/60 | 0/60 | 0/180 | 0 |
| A_minus_11 | 0/60 | 0/60 | 0/60 | 0/180 | 0 |
| A_minus_29 | 0/60 | 0/60 | 0/60 | 0/180 | 0 |
| A_minus_47 | 0/60 | 0/60 | 0/60 | 0/180 | 0 |

每臂合计 0/540 个会话，整体 0/1,620。仍然只有 180 道唯一开发题；三臂和三种子不能把独立题数放大九倍。开发题来自 12 个 CIK 公司来源簇，composition_required、dual_sufficient、other_financial 分别覆盖 12、8、12 簇，三组来源簇有重叠，不能相加为 32 个独立公司。

| 所有 1,620 个 outcome 的字段 | 统一状态 | 数量 |
| --- | --- | ---: |
| reason | no_final | 1,620 |
| quantity_status | UNDETERMINED | 1,620 |
| support_status | UNDETERMINED | 1,620 |
| full_mapping_status | PENDING_REVIEW | 1,620 |
| financial_valid | false | 1,620 |
| complete_trajectory_qualified | false | 1,620 |

评分器在 `first_final_index` 为空时直接返回 `reason=no_final`；后续数值和 Final 内容判定没有被推进。因此应表述为“没有记录到可识别的 Final，数值和支持未判定”，而不是“经数值比对后 1,620 个答案全部错误”。`PENDING_REVIEW` 在此是尚未推进的状态，不是导致全零的独立证据。

## 9. 无 Final 的运行时表现与代表性实例

### 9.1 全量已有摘要的终止分布

| 模型 | response_budget_exhausted | provider_error | context_rejected |
| --- | ---: | ---: | ---: |
| A_alpha0_11 | 177 | 3 | 3 |
| A_alpha0_29 | 175 | 5 | 5 |
| A_alpha0_47 | 177 | 3 | 3 |
| A_plus_11 | 180 | 0 | 0 |
| A_plus_29 | 178 | 2 | 2 |
| A_plus_47 | 180 | 0 | 0 |
| A_minus_11 | 178 | 2 | 2 |
| A_minus_29 | 177 | 3 | 3 |
| A_minus_47 | 179 | 1 | 1 |
| 合计 | 1,601 | 19 | 19 |

响应预算耗尽占 98.83%，provider error 占 1.17%；后者全部对应上下文拒绝。`context_rejected` 是另一个布尔字段，与这 19 个终止重合，不能再加成 38 个失败。本轮这里的 provider error 是本地生成接口包装出的终态类别，不是 DeepSeek 服务宕机，也没有这些条目由 GPU OOM 导致的证据。

原解码为 neutral greedy、单 beam，每响应最多 2,048 new tokens，总序列边界 24,576，最多 32 个响应和 32 个工具调用。完整 prompt 加预留输出超限时拒绝，不截断历史或临时换参数重跑。响应轮次预算、单响应生成预算和总上下文预算是三种不同限制。

### 9.2 实例一：合法空查询持续到响应轮次耗尽

模型 A_plus_29，任务 `task_49c7f2f2beef586893c4d2386f863a14f97bb1fd20528c558981db4056287ab2`：

- 共 32 次合法 `query_source` JSON，工具均返回 `status=ok`，但 `total=0`、`records=[]`；没有 protocol error。
- 查询循环使用 `concept='revenue'`、`label_contains` 中的 2011/2012/2013，以及 `unit='million USD'`。
- 32 个实际响应均以 EOS 结束，每次 68 个生成 token，并非触及 2,048 token 截断；原始响应未出现 final 文本，`first_final_index` 和 `raw_final` 均为空。

工具实现要求 concept 是 `namespace:tag` 的精确标识，`label_contains` 搜索概念标签/说明而不是日期，单位需匹配原单位；日期有独立 start/end 参数。因此，该例直接支持“模型查询参数没有正确利用工具合同，空结果后仍反复查询”的描述。它不证明所有会话采用相同错误查询，也不证明单纯增加每响应 token 就能解除循环。

原件：`generation/dev/A_plus_29/sessions/task_49c7f2f2beef586893c4d2386f863a14f97bb1fd20528c558981db4056287ab2/runtime_session.json`；首个对应生成收据为 `generation/dev/A_plus_29/decoder/callback_001945/receipt.json`。

### 9.3 实例二：长字符串未闭合，随后上下文拒绝

模型 A_alpha0_11，任务 `task_2d64bff88880418bfb2522dbcbdc8a380d070067092f23206284a4fe4022863c`：

- 实际产生 16 个响应：6 次合法空集 query_source，之后 10 次 read_source 字符串未闭合。
- 后 10 次输出的 `native_pointer` 在 `/facts/period/2018-12-31/USM100000000...` 形式上持续生成零，每次达到 2,048 new tokens；错误为 `Unterminated string starting at: line 1 column 116 (char 115)`。
- 16 条实际原始响应均无 final 文本。第 17 次 callback 的 prompt 为 24,326 token，加预留输出 2,048 后超过 24,576，记录 `context_rejected_before_model_generate`；该次 `GPU_generation_invoked=false`，新生成 token 为 0。

原件：`generation/dev/A_alpha0_11/sessions/task_2d64bff88880418bfb2522dbcbdc8a380d070067092f23206284a4fe4022863c/runtime_session.json`；拒绝收据为 `generation/dev/A_alpha0_11/decoder/callback_001201/receipt.json`。

### 9.4 已证实、推测与尚未验证

已证实的是全量摘要中的无 Final、终止分类，以及上述两个具体会话形态。两个样例都查看了其已有实际响应，不仅依赖评分标签；但本报告没有全量扫描 1,620 个会话原文，不能据两例推断各类根因的全量比例。

可以提出但尚未证实的解释包括：模型工具参数使用能力不足、训练与推理交付习惯存在差异、重复轨迹不能在当前预算内进入有效终局，或预算限制放大了循环与长字符串问题。现有证据不足以宣布统一根因，更没有证明是评分器 bug。提高预算是可检验干预，不是已经确认有效的修复；空查询与重复字符串也可能在更大预算下持续。

## 10. 方向选择、统计规则与未执行分支

| 项目 | alpha0 | plus | minus |
| --- | ---: | ---: | ---: |
| 跨三种子的平均 U | 0 | 0 | 0 |
| 相对 alpha0 的配对均值收益 | 0 | 0 | 0 |

原规则要求跨种子平均配对收益严格大于 0 才离开基线，不要求每个种子单独都大于 0；平局顺序为 alpha0、plus、minus。此次两候选均为精确 0，因此选择 alpha0，状态 `STOP_RETAIN_BASELINE`。选择没有使用 NLL 或方法产率代替财务主指标。

若出现正方向，计划为 B 池的“基线 + 唯一候选”各三个种子，共 6 次训练；不另跑 B dev。随后 A/B 两池、两臂、三种子在独立 720 题（三组各 240）上确认，最多 8,640 会话。该阶段 B 是主确认池，A 为辅助，不能用 A 的正结果替代 B。

确认原计划按 CIK 来源簇配对，使用固定种子 20260912 的 10,000 次共享簇权重 bootstrap，计算 95% paired percentile 区间；B 区间下界严格大于 0 才确认正收益。区间包含 0 是未确认，而非证明效应为零；5 个百分点是另行讨论的收益量级，不是“任何正收益”的定义。

**本轮并未进入该确认阶段，没有 B 效果估计，也没有实际确认区间。**最终记录 `B_training_runs=0`、`confirmation_sessions=0`、`independent_positive_effect_confirmed=false`。不能将未执行的 B/确认写成 B 失败、置信区间为零，或把 720 道题因多种子重复评价当作数千个独立样本。

## 11. 总结：本轮能回答和不能回答的问题

本轮已经完成材料闭合、支持与剂量准入、九个真实 Student 的规定剂量训练、原预算下完整开发评价和按规则终止。训练分布、材料角色与原始失败分母均保留，工程优化没有通过减少监督量获得加速。

本轮未观察到财务资格收益，直接障碍是原评估运行没有得到可识别的 Final。因此目前不能可靠排列三种方法配比的任务能力，更不能由本轮推出某方法普遍无用、VTDO 无效、或训练 loss 下降代表任务质量改善。

后续证据需要区分：预算放宽是否使相同模型获得 Final；获得 Final 后数值、来源、单位、实际期间和支持链是否真正合格；即便原开发集出现提升，是否能在未用于选方向的材料和题目上独立确认。新观察不得倒写为旧协议本已成功。

## 12. 结果来源、身份与复核范围

### 12.1 目录与源提交

- 原结果已发布来源提交：`9cff3a40b0`；远端仓库 `https://github.com/haoyueliuzhao/Data-Synthesis.git`，分支 `main`。
- 实际执行工作树：`/tmp/data-synthesis-fixed-kernel-parallel-tail-20260914`。
- 本文执行输出简称 `OUT`：`trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/parallel_tail_execution_20260914`。
- 原采集工作树：`/tmp/data-synthesis-fixed-kernel-completion-20260914`；原材料输出 `trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/study_20260914_budget_completion`。
- 前八份训练报告内部保留原 `trajectory_execution_20260914` 历史路径；现有导入文件在 `OUT/training/`，没有为统一外观重写原报告身份。

### 12.2 关键身份

| 记录 | 完整身份 |
| --- | --- |
| 材料生成闭合 | `material_generation_report:3a2b2255080b5a7b4ef91b1bc9338f92fccef091364031c3e9bc90a821c0f8b2` |
| 材料门 | `material_gate:16d9491e7ca7b6b506bc5308b67dc9de5b2958e94cba0d2944c5b9395f23e763` |
| 固定材料核 | `fixed_kernel:f67d9edd0712d87d6d63d6e9535f8ff2db677cb81c884780afc8315c1d15c729` |
| 轨迹缓存 | `trajectory_material_cache:587363af1e6e25da9236833df79da620669f8420278ec438f82f217fb554b8bf` |
| 八卡尾任务训练报告 | `training_report:d72b980706bf54543effadbfdb8af57c85f18607c7d72d1f5ee203eea7be118c` |
| 尾任务真实训练配置 | `training_configuration:9959a7beb582708e6e56e89a63d55e5cb44f2a2f524eadaef711ce1b3070e76d` |
| 混合执行 lineage | `heterogeneous_execution_lineage:48c2fae2ba55c57ff9f5d9d52517850b2ab2010d47ff24ece03a88ed82e8357a` |
| 实际方向选择 | `actual_direction_decision:b7b4121de17e0f163b5dc9f5b218e952aaf41a366f7ac5f8809786ac5b50d2a6` |
| 最终执行报告 | `execution_report:c2427de4084db9e0865521d53c4b32d2a61983f1f7e3332355b4b07a5b4a916e` |
| 原材料封存 manifest | `publication_manifest:457d6009f338c172a665ef177ce1ebb2fd7f528e508b1918cc18bc50212a4ae0` |
| 本执行结果封存 manifest | `publication_manifest:c4ca72e5703a238fc79c34ac939929ca7b1f3b9a74be75b2c3faaa7a538e342f` |

### 12.3 逐项证据位置

| 本文内容 | 直接来源 |
| --- | --- |
| 原协议、模型与统计计划 | [实验设计说明](finance_qa_vnext_fixed_kernel_value_experiment.md)，第 4–10 节 |
| 预算续采范围与修订性质 | [预算完成说明](finance_qa_vnext_fixed_kernel_budget_completion_20260914.md)；原材料 `generation_report.json`、`material_gate.json` |
| 原包角色与可消费量 | 原材料物化索引与材料门；`OUT/preparation/trajectory_cache/manifest.json` 的 train 预算 |
| 轨迹转换实际预算 | [轨迹执行说明](finance_qa_vnext_fixed_kernel_trajectory_execution_20260914.md)；缓存 manifest |
| 八卡来源与封存 | [并行执行说明](finance_qa_vnext_fixed_kernel_parallel_tail_20260914.md)、[原实际结果说明](fixed_kernel_parallel_tail_actual_results_20260914.md) |
| 训练时间、更新量 | `OUT/training/<model>/started.json`、`report.json` |
| 首末五步训练损失 | 同模型 `updates/0001`–`0005`、`0396`–`0400` 的 `report.json` |
| 开发生成与退出 | `OUT/generation/dev/<model>/report.json`；`OUT/jobs/A_dev/generate_<model>_dev_job.json`、对应 `_exit.json` |
| 财务指标与终止分布 | `OUT/scores/dev/<model>/report.json` 的 `group_counts`、`primary_utility`、`outcomes` |
| 方向与原轮终态 | `OUT/decision.json`、`OUT/report.json` |
| 两个失败样例 | 第 9 节所列 `runtime_session.json` 和 decoder receipt |

指标公式见 `src/trusted_synthesis/experiments/finance_qa_vnext_fixed_kernel_value/evaluation.py` 的实际评分、`_analysis_utility` 和 `select_actual_direction`；无 Final 的早返回见 `src/trusted_synthesis/experiments/finance_qa_vnext_eval_readiness/assessment.py` 的 `assess_session`；工具参数合同见同目录 `runtime.py`。

本报告仅利用已有汇总、必要的首末步数值和两个已有会话样例；未重新采集、训练、评分、跑完整测试套件或重复计算全量材料 hash。样例之外的机制解释已标注为推测，不将有限抽查扩写成全量根因审计。

## 13. 后续：独立提高预算复评的授权与状态

在本报告整理期间，用户追加授权“提高预算重新评估检验”。此项按独立复评处理：原轮 9 个已训练检查点、原轮成绩及其 `STOP_RETAIN_BASELINE` 结论保持封存；新的预算参数、解码配置、输出目录、执行来源和实际结果需在新的冻结/复评记录中明确。

本报告不能预先宣称更大预算一定带来 Final、财务收益或可进入 B 的方向，也不把新预算实验称为原协议未经修订的继续。独立方案拟采用 64 次响应、64 次工具调用、每响应 4,096 新 token、总上下文 32,768，复用原九个检查点，先做公开元数据固定三题的 27 会话配对 pilot。真实基座上下文上限为 32,768，不做 RoPE 外推。完整预算、子集和条件性补全规则见[高预算复评方案](fixed_kernel_budget_reevaluation_plan_20260915.md)，实际启动与完成量以新记录为准。

**截至本报告稿形成时，预算复评正在另行实施，尚待新的实际复评报告。**新结果应并列比较 Final 产生率、未判定比例、完整财务资格和实际资源消耗；若继续使用已观察过的 180 道开发题，须说明这是诊断性再评估，不冒充新的独立确认集。原报告的 0/1,620 与未执行 B/确认事实不因追加授权改变。
