# V9：固定经验支持域的真实训练接线（2026-09-29）

## 结论与边界

本修订不重启第三批生成，不追溯改变 V8 审阅规则、原 1000 题训练停止记录、原生评分或数学内核。它把后继训练总体明确改为本批全部经过原生正确与双审有效核验的任务支持域 X*，任务边际由原 1/1000 改为 1/N。

这是研究总体修订，不是原协议通过，也不是把 820 题声明为已准入。原 1000 题 / 8000 槽仍作为完整覆盖分母。N 在生产材料全部处理与冻结前未知；不按长度、状态数、χ、C、Student 结果选取任务。单状态任务仍全部保留。

实现复用 V8 已有真实 optimizer、Adam、原包消费、虚拟点、反馈 replay、C/N 与 π 内核。没有再写一个平行训练框架。本文所述 CPU 控制不是 Qwen/CUDA 验收，也不证明真实 700 反馈、材料资格或训练收益。

## 严格材料边界

新入口为 `v9_conditional_training.load_training_pool(binding_path)`。仅接受 `v9_conditional_training_binding.v1`：

- `review_policy_id` 绑定原 V8 单目标政策 `8bef2630…`。
- `generation_protocol`、`generation_seal`、`native_support`：现有 V8 真实父库存，每项是 `{path, sha256}` 字节引用；允许附加内容 `id`。
- `production_protocol`、`production_completion_seal`：本次生产协议及全部已返回结算记录的共同封存。
- `support_manifest`：全部资格处理之后冻结的实际 X*、全部共同有效槽、状态、χ、token 统计与执行坐标。
- `resolutions`：以原 1000 任务为完整键集，不能只传成功任务。
- `encodings`：恰好包含所有双侧有限语义核验有效且 native 正确的原包，不能遗漏难包，也不能混入技术样本。
- `tokenizer_binding`：实际 Student tokenizer 与 chat template 的二元身份。

所有引用在首次读取时核验字节 SHA 并缓存。加载器核验完整原始生成协议、1000×8 名册、全部原包封存和 native roster；核验生产调用固定矩阵、每个响应与 assessment 的绑定；从两侧已核验的 `validation` 重新计算 joint 集合，不接受模型未经核验的自报 valid。普通格式或一致性失败作为 unknown 留在完整生产集合里，不能被解释为新有效包。

共同有效包即使 mask 不一致、整题状态映射失败或完整编码超长，也不能删掉它或整题来恢复 ready。该问题阻止整个共同训练核冻结。Q=False 保持 `not_assessed_native_ineligible`，不是一次并未发生的过程否定审阅。

最终 `support_manifest` 必须与全部 resolutions / encodings 机械重算结果完全相同。空 X* 可留作库存结果，但不能训练。加载器不会将任意子集传给 `VerifiedPool` 后宣称生产验证；生产池必须含父库存、完整生产封存与精确支持域绑定。

## 能力与规模判断在 Student 结果前完成

`build_support_manifest(protocol, completion, resolutions, encodings)` 是纯记录构造函数；它不代替加载器对真实文件、请求和原件的核验，也不发 API。

其 capability profile 记录实际 N、总状态数、总包数、每状态包数直方图、Dπ、Mflex、同题 χ=0/1 的任务数和质量、单状态题数及只有一个原包的题数。报告 `nontrivial_pi` 和 `nontrivial_manual`，但不以这些必要条件冒充检验功效。`power_established` 固定为 false；训练启动前还需要另行记录基于该实际 profile 的规模判断。

当前冻结编码只提供 `reason / tool / final` 三层，其中 reason 合并公开 R 与 U，tool 为非终局 A，final 为 F；EOS 按原 action 层归属。profile 如实统计三层，并明确 `separate_R_U_token_counts_available=false`，不伪造原编码没有记录的独立 R/U 数量。它不改变原监督 mask。

若 Dπ=0，分布干预没有自由度；若同题没有两类 χ，Manual±归一化后不改变分布。此时可以保留真实库存，不应启动数学上相同却名义不同的五臂。本模块不挑删单状态题来增加这些指标；真实 launcher 另行执行非平凡条件和显式前瞻规模决策。

## 可变 N 日程与真实尾批

令 s=ceil(N/5)，每个种子 11/29/47 使用局部固定 RNG，每遍从相同原序任务清单做置换，共十遍。每个任务恰好出现十次；所有臂使用同一具体 schedule。最后 1—4 题构成真实尾批，不补假题、不重复任务、不删题。

| 坐标 | 后继定义 |
|---|---|
| 共同暖启动 | 2s |
| 四次外更新 | 2s / 4s / 6s / 8s |
| 终点 | 10s |
| C 方向机制点 | 3s |
| N 局部机制点 | 5s |
| 700 反馈 | 始终保持原 350×2 |

实际任务批 B_j 的每个监督 Token 权重为 `π(z|x)/(B_j*n_xz*L_P)`。实现继续调用原 `TaskBatch` 和 `execute_task_batch_update`，由原 `μ/(B*p_s)` 系数消去 uniform μ 与任务采样概率；没有额外除 N、B、全局 Token 数或包数。每步恰好一次梯度裁剪和 Adam 更新。

例如 N=7 时 s=2，每遍为 5 题及 2 题两个批；共同前缀 4 步、外层 4/8/12/16、终点 20 步。该例只是 CPU 控制，不是实际 N。N=820 的 1640 步同样只是假定上界的算术，不是已登记训练规模。

尾批改变梯度方差和 Adam 历史，故不宣称与原 1000 题训练逐位等价。G、C 和 RMS 直接使用严格池中的实际 `μ=1/N`；反馈分母不随 N 改为较小值。全零反馈沿用原规则保持 π。

## 驱动、保存与共享

`ConditionalTrainingDriver` 继承原 V8 driver，接口继续为 `step / run_until / outer_update / restore / commit`。仅向 V8 添加可选 `execution_plan` 和已重算核验的 `task_schedule`。不传新参数时，旧 1000 题默认 400/800/1200/1600/2000 与固定五任务行为保持原样。

真实 checkpoint 保存模型参数、buffer、Adam、RNG、π、prior、schedule 与新 execution plan；恢复必须逐项绑定。共享分叉只能来自真实 2s checkpoint，不能在任意 step 修改计数冒充暖启动。Manual±仍使用同一 prior 和 χ；C-only/Full 到达外更新点之后，不完成真实外更新便不能继续下一训练批。

同点共享判定仍检查真实 θ、Adam、RNG、π、日程、反馈身份与梯度证据；新版仅将首个共享坐标由固定 400 改为 2s。6s 后 point identity 保持臂特异。共享只是允许优化，不是自动根据相同奖励推定成立；保守执行可以不共享，不能虚报减少的物理步骤。

新模块不装载模型、不选择 GPU、不发送 API。正式模型 fresh 初始化、CUDA 资源准入、各 seed 五臂启动与显式恢复由 `v9_training_launcher` 接续。本次未提前占用 GPU。

## 必要 CPU 控制与尚未验收项

本次新增针对 1/4/5/7/819/820/1000 的日程算术控制；覆盖十遍全任务计数、真实尾批、动态坐标、不可重写日程。小型 CPU 模型实际执行二任务尾批的 backward/clip/Adam，验证不额外除批大小；实际运行共享四步、Manual 分叉与二十步终点，核对保存恢复的参数和 Adam 历史。

另以原本地 provider 的真实 CPU TokenReceipt 检查动态首外层实际虚拟点与全零反馈规则；该控制只有两个合成反馈轨迹，不冒充真实 700 Qwen 会话。生产 driver 仍强制真实 collector、完整 700 分母以及不允许测试 callback。

材料控制保留合成 1000/8000 父分母，检测缺失原任务、缺失 joint 原包、失败映射、超长编码、未完成生产前缀、Q=False 重判和无效 χ 均不能冻结训练核。singleton 可以进入真实共同支持，但不能制造非平凡五臂能力。

当前仍未验收：全部真实生产双审与对齐、实际 X* 完整编码冻结、前瞻规模决策、原始 Qwen fresh/CUDA 运行、真实 700 反馈闭环及十五个训练终点。CPU 通过不替代其中任何一项。API 支出仍受原钱包和用户授权上限约束，本文不扩大预算。
