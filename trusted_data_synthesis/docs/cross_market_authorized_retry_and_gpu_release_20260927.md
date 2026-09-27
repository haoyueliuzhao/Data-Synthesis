# 单分片有限恢复授权与四卡让出

## 两项用户授权

2026-09-27，用户明确批准此前提出的“一个耗尽原重试次数的分片，额外两次恢复机会”。随后追加要求：“此外我有其他项目需要运行，暂时先空出四张卡”。本修订同时落实两项要求，不把前者扩展成所有分片无限重试，也不因继续实验而重新占满被让出的 GPU。

唯一追加恢复对象是 `generate_negative_11_stochastic_0`，注册工作单元 ID 为 `cross_market_evaluation_work_unit:aa9a8febd5e1dd0d35bb0977523c94022914af69caf990cc2d0c4ba4f94d6f23`。原上限为 4，本次只准许 attempt5 和 attempt6；若两次仍未完成，attempt7 继续阻断，不自行追加。

## 四张卡已经实际释放

先核对并停止本项目原 coordinator PID `3973364`，防止释放后立即补占。再从本轮 jobspec／attempt ledger 和 `/proc` 命令行核对四个在途进程的工作单元、PID、出生标识、worker 脚本和 GPU UUID，仅向以下本项目 worker 发送 SIGTERM：

|让出 GPU|原 worker PID|工作单元|已消耗 attempt|
|---|---:|---|---:|
|2|3977736|negative29 stochastic_0|2|
|3|3977737|negative29 stochastic_1|2|
|4|3977738|negative29 stochastic_2|2|
|5|3977739|negative29 greedy_0|2|

四个进程均已确认退出；随后 `nvidia-smi` 显示 GPU2／3／4／5 各占用 0 MiB、可用 81,154 MiB。刚退出时 GPU utilization 的采样值可能短暂保留，不等于 CUDA 进程仍存活。这里保证的是本项目已释放占用，不承诺其他项目随后不会自行使用这些卡。

释放操作前全局已提交 463 个会话。它们的持久数据和预算计账均保留，不删除 completed/session 文件，不移动或重写模型保存点。本阶段是固定参数点评价，没有正在更新的训练 optimizer 状态需要临时保存。正在执行但尚未提交的会话可能需要以后完整重跑，其已预留调用和 attempt 消耗不退款。

原 worker 未能自然写出 outcome 的情况，保持原始事实：不伪造 worker 成功，不把人工停止伪装成 CapacityWait。独立 `evaluation_01/gpu_release_01/request.json` 记录用户要求、精确四个进程、卡号及释放前预算；`released.json` 记录已核实的退出。原调度器本就允许恢复“已有进程身份但已退出、无最终 outcome”的尝试，新 worker 将按原 inventory 复用有效完成会话、重新执行缺失会话。

GPU0／1／6／7 的在途 worker 不发送任何停止信号，继续运行。

## 新调度限制

新启动器 `run_cross_market_authorized_retry_20260927.py` 继承已有 `performance_01` 协议：逐 token logprob 合并回传、48 GiB 门槛、最多 120 秒会话边界容量宽限、显存遥测和精确旧 CuBLAS 恢复范围不变。

增加独立、冻结的 `authorized_retry_01` 运行协议，绑定：

- 唯一目标工作单元及其原四次失败的实际文件哈希。
- 用户明确批准的 attempt5／6，原先四次不清零、不隐藏。
- 原科学协议、性能协议、全局预算、登记时已完成会话及在途进程。
- 此次四卡释放记录和硬件 UUID 白名单，只允许 GPU0／1／6／7。
- 已提交源代码及 coordinator 的唯一 AST 变更绑定。

GPU 准入先沿用原 48 GiB 检查，再过滤至四个保留 UUID；每张卡仍只允许一个本轮 worker，因此本轮最多四卡并行。原科学协议的 `max_GPU_workers=8` 不篡改为另一值再冒用旧协议 ID；实际更严格的四卡限制写入新运行协议。worker 入口也检查真实 `CUDA_VISIBLE_DEVICES`，禁止在让出的卡上启动本轮生成。CPU 评分不受 GPU UUID 门禁影响。

该白名单不会因为 GPU2／3／4／5 空闲就自动解除。日后重新使用这些卡需要新的用户指示及显式资源修订；当前不争抢其他项目资源。

## 恢复次数与科学不变条件

独立 coordinator 副本只将原 `cap = plan["scheduling"][...]` 的取值包装为“确切目标身份时加 2”；通过唯一 AST 匹配、反向还原及整棵 AST 一致性约束，其他循环、FATAL 处理、封存与评分隔离逻辑不变。目标 key 相同但 ID／工作类型不符会直接拒绝，而不是获得恢复额度。

全局 `worker_start_cap=216`、`generate_call_cap=157824`、`incomplete_generate_call_cap=2304`、`score_case_cap=5100` 不变。其他分片仍遵守原最多四次生成尝试。此次人为停止的 negative29 四个分片没有获得额外次数；它们通常可用原剩余 attempt3／4 恢复，若以后耗尽则如实报告，不能借本次批准扩大授权。

九个 step240 参数点、180 题、重复数、随机种子、采样参数、精度、输入／输出上限和全部 4,860 会话的评分隔离保持不变。已生成及已消耗记录不改写。没有新增 API 调用、训练或 Student A/B 实验。运行修订不说明任何训练价值结论。

目标分片的恢复以有空闲保留 GPU 且达到原准入门槛为条件；不强停 GPU0／1／6／7 的在途会话来抢占空位。登记成功仅表示解除原次数阻塞并重新进入待调度队列，不等于 attempt5 已经开始，更不等于实验已完成。

## 验证与部署记录

仅执行 CPU/mock 定向测试：目标第 5、6 次放行，第 7 次阻断，非目标与评分次数上限不变；完整 coordinator code tree 只有 cap 表达式差异；原 FATAL 不洗白；旧 worker 接管、CUDA 环境、性能适配、原四次失败绑定和 worker 入口限制保留；白名单外 GPU 被过滤且不能从 worker 入口绕过。

真实登记 ID、接管后的队列状态、进度和最终代码提交将在部署完成后追加，并保存定向公共快照。不以计划代替真实启动或完成状态。
