# 历史梯度缓存后续清理（2026-10-04）

用户再次要求排查、清理历史无用数据，继续以不影响当前实验为约束。本轮北京时间 **2026-10-04 10:54:30** 完成逐文件清理，共删除 **1,542 项、原实际分配 80,069,025,792 字节，约 74.57 GiB**。其中旧 VTDO 梯度及方向张量 912 项，QA 早期累积反馈梯度快照 630 项。该统计与[当天前一轮](historical_gradients_cleanup_20261004.md)分别登记，不重复计入已删除文件。

执行前后两个训练 worker 的 PID/birth 标识一致，权威队列保持 `V21_SIX_GPU_QUEUE_RUNNING`，`failures=[]`。九个固定 Student 的 27 个保护文件，加上 QA 最后累积梯度和 population 两个文件，共 29 项 stat 未变。没有修改旧实验报告、实验算法、训练材料或运行策略。

## 精确范围

下表实验路径相对于 `trusted_data_synthesis/artifacts/vtdo_experiment/`；只删除所列目录直接子级、已登记的 `.safetensors`。花括号表示分别列出的目录，不是执行时扩大范围的匹配规则。

| 旧实验路径 | 子目录 | 文件数 | 原实际分配字节 |
| --- | --- | ---: | ---: |
| `finance_v19_sealed_causal_pilot_fp32_alg_v2_20260806` | `gradient/{state_gradients,common_token_gradients,differential_token_gradients}` | 180（各 60） | 14,543,585,280 |
| `finance_v20_target_identifiability_gradient_projection6_k3_v1_20260806` | `{state_gradients,common_token_gradients,differential_token_gradients}` | 180（各 60） | 14,543,585,280 |
| `finance_phase15_gradient_projection_30task_v1` | `state_gradients` | 90 | 7,271,792,640 |
| `finance_phase18_gradient_projection_30task_v1` | `state_gradients` | 90 | 7,271,792,640 |
| `finance_phase16_batch_symmetric_30task_v1` | `{coordinate_gradients,batch_directions}` | 124（60 + 64） | 10,018,914,304 |
| `finance_phase17_gp_abc_30task_v1` | `{optimizer_coordinates,optimizer_batch_directions}` | 124（60 + 64） | 10,018,914,304 |
| `finance_phase18_contribution_authorization_v1` | `{optimizer_coordinates,optimizer_directions}` | 124（60 + 64） | 10,018,914,304 |
| VTDO 小计 | 14 个目录 | **912** | **73,687,498,752** |

QA 仅删除 `trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/delayed_C_recovery_cache_20260921/A_delayed_c_29/feedback/` 中 **`0001.pt` 至 `0630.pt`**，共 630 项、6,381,527,040 字节。`0631.pt`、同级实验的 `population.pt` 和所有 `updates` 均保留。

全部删除文件逻辑大小合计 80,066,083,530 字节。实际分配按 `st_blocks × 512` 统计，逻辑大小按 `st_size` 统计，均不含保留的目录元数据。此次只使用逐文件审计清单，没有删除整个实验目录或泛化清理所有 `.pt`、`.safetensors`。

## 七个旧实验的原始状态与输入

以下是审计时读取到的历史状态，清理不改变其科学含义：

| 实验 | 保留记录中的状态 |
| --- | --- |
| 旧 V19 sealed causal pilot | 梯度 report 为 `partial`；数值执行通过，但独立 finite-target 的 Estimation/Validation 门槛失败，GP-C 未执行，Contribution 未获授权并保持零 |
| 旧 V20 target identifiability | 梯度 report 为 `partial`；最终 finite-target 报告为 `failed`，属于 Development-only，不能用于 GP-C 或下游效果结论 |
| phase15 gradient projection | `partial`，阻塞项为 `independent_distribution_intervention_not_run` |
| phase18 gradient projection | `partial`，阻塞项同上 |
| phase16 batch symmetric | `failed`，包含 Estimation/Validation rank gate 失败和数值预检选用非生产学习率 |
| phase17 GP A/B/C | 原 report 为 `passed`；本次保持该历史记录，不将存储清理解释成新的验证 |
| phase18 contribution authorization | `calibration.json` 为 `failed`，阻塞项为 `primary_internal_gate_failed` |

旧 V19、V20 结论分别见[sealed causal pilot 报告](finance_v19_sealed_causal_pilot_report.md)和[target identifiability 报告](finance_v20_target_identifiability_report.md)。它们是 2026-08 的实验，与当前金融队列中的 V19/V20 命名不同。

审计递归提取七份 `plan.json` 中的外部绝对路径，全部存在，逐项结果保存在本轮 `audit.json/input_presence`。这些引用包括原始任务状态、分布、state realizations、数值契约、Objective 支持记录、源 plan/report、基础模型和 beneficiary adapter。V19、V20、phase15、phase18 四份梯度计划的 `target_records_path` 也均存在，约为 3.26、3.27、5.21、4.92 MB，继续保留。本轮进行存在性与元数据核验，没有重新计算大模型或全部原始输入的内容哈希，没有启动 GPU 重算。

生成代码与张量性质依据如下：

- [`phase1_contribution_gradient.py`](../src/trusted_synthesis/experiments/vtdo_experiment/phase1_contribution_gradient.py)从冻结目标记录、模型、adapter 和种子计算 state/token 梯度；它们是中间导数，不是最终模型保存点。
- [`phase1_batch_distribution_intervention.py`](../src/trusted_synthesis/experiments/vtdo_experiment/phase1_batch_distribution_intervention.py)约第 247 行创建 coordinate gradients，第 512 行创建 batch directions，第 520 行组合方向。
- [`phase1_gp_abc_validation.py`](../src/trusted_synthesis/experiments/vtdo_experiment/phase1_gp_abc_validation.py)约第 281、587 行创建 optimizer coordinates 和 batch directions。
- [`phase1_contribution_authorization.py`](../src/trusted_synthesis/experiments/vtdo_experiment/phase1_contribution_authorization.py)约第 446、769 行创建 optimizer coordinates 和 directions。该类文件是梯度经优化器映射得到的方向，不是模型参数检查点。

**重算存在多阶段依赖。** phase16/17/18 的方向依赖本轮同样删除的 phase15/18 state gradients。未来需要先依据保留原始记录重新计算 state gradients，再重建坐标与方向；不能只凭保留源 plan/report 直接恢复原张量。已有 worker 元数据仍引用原始文件，原目录直接 resume 或逐张量重放可能因缺失文件而报错。需要在隔离输出目录重新登记计算，保留旧报告与失败记录，不保证环境、数值或文件字节与原运行完全一致。

## QA 累积快照及原始回执保护

[`run_fixed_kernel_delayed_C_recovery_20260921.py`](../scripts/run_fixed_kernel_delayed_C_recovery_20260921.py) 的 `completed_replay` 从原始 generation/scoring 记录与回执建立固定反馈顺序；约第 184 行排序 `feedback/*.pt`，仅加载最后一个 `saved[-1]`，约第 220 行在每个 response 后保存截至当时的累计梯度 `sum` 及 cursor。因此本次保留 `0631.pt`，仅释放此前 630 份累计状态；不会删除用于训练恢复的 `updates`。

保留 `0631.pt` 维持该代码读取最新累计反馈状态的路径。删除早期快照意味着不能再直接加载某个早期 response 边界的梯度状态；若需逐步验证需重新计算。这不等于将所有中间轨迹无损保留，也没有通过实际重跑证明旧完整环境仍可直接恢复。`population.pt` 是独立保留的输入，未纳入删除计划。

原始反馈证据位于 **`/tmp/data-synthesis-fixed-kernel-parallel-tail-20260914`**。其中 `trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/anchored_sources_20260916/delayed_C_20260919/runs/A_delayed_c_29/rounds/epoch5/feedback/` 的 generation/scoring manifest 均为 `complete=true`，360 个 generation manifest 引用的原始回执文件全部存在，评分记录为 99 qualified，与删除范围无交集。完整路径及存在性结果保存在 `audit.json/qa_source_evidence`。本轮未重新解压全部回执或重算其内容哈希。

**今后不得仅因上述原始证据目录位于 `/tmp`，便将其当作无用临时目录清除。** 若调整存储位置，应先核对并迁移完整证据与引用关系。该目录保存恢复与审计输入，不属于本轮清理白名单。

## 当前依赖与保留范围

本轮新鲜进程快照显示当前金融进程仍使用根 `.venv` 和 V18 源码链。定向搜索 main、V18、V10-proxy、V15、V16、V17 共六个 `finance_research` 源码根，没有发现对 VTDO 产物路径、QA A29 recovery 或 `population.pt` 的引用。结合当前队列、进程参数和依赖链审计，未发现本轮候选属于当前训练或已登记队列输入。执行前还检查当前账户可见进程的 cwd、解释器、命令行、内存映射和文件描述符，未发现白名单目录被使用。

整个 `finance_research_20260928`、九个固定 Student 及原始来源、全部训练 `updates`、基础模型和 adapter 均保留。除 QA 630 个明列文件外，其余 QA 内容保持；七个 VTDO 实验的 JSON/JSONL、原始输入、账本、报告、worker 元数据及未列入清单的 global/task/mean/evaluation 张量继续保留。路径搜索与进程快照支持本轮边界判断，不构成对未来新增实验或任意动态依赖的永久保证。

## 执行保护、结果与局限

本轮 [`cleanup.py`](../artifacts/storage_cleanup_20261004_followup_history_01/cleanup.py) 使用包装脚本复用前次安全核验 helper。包装脚本先校验 helper SHA256 `1e6af39b698fac1a9c9a6a5f3e1d2b19b6d9bc4e637f86fbc33745f2cfe040ab` 和 `audit.json` SHA256 `511a23386bb80641634e49da33d8e1bf309764fd83c3ce1aa10e1ce7e866c0b4`；计划再绑定包装脚本哈希，实际执行绑定计划哈希。复用不意味着接受可变的旧脚本或重新生成宽泛删除范围。

执行只接受审计清单中的路径与文件身份，检查设备、inode、大小、分配字节、链接数和 mtime/ctime，拒绝路径重定向、非普通文件、多硬链接及 Git 跟踪目标，再逐文件 `unlink`。QA 另外约束 basename 为 `0001.pt` 至 `0630.pt`。29 个明确保护文件执行前后 stat 全部一致；`retained_files_unchanged=1` 对应删除目录内保留的 `0631.pt`，它也计入明确保护对象，因此两数字不能相加解释为 30 个不同文件。

| 项目 | 实际结果 |
| --- | --- |
| 完成时间（北京时间，秒精度） | 2026-10-04 10:54:30 |
| 结果 | `complete`，1,542 个目标全部不存在 |
| 删除文件原实际分配 | 80,069,025,792 字节 |
| 执行前磁盘空闲 | 345,589,911,552 字节 |
| 执行后磁盘空闲 | 425,659,125,760 字节 |
| 同期空闲量净增加 | 80,069,214,208 字节 |
| 两个训练 worker | `arm-47-full` PID 73851；`arm-47-manual_minus` PID 1475362；PID/birth 前后一致 |
| 队列 | 前后均 `V21_SIX_GPU_QUEUE_RUNNING`，`queued=[]`，`failures=[]` |
| 明确保护对象 | 29 项 stat 未变 |

磁盘净空闲增长与目标原占用相差 188,416 字节；前者是动态全盘快照，后者是逐文件分配计量，不能将差额直接归因于某种未经测量的因素。删除没有暂停实验或锁住整个项目，不是全局原子操作。执行前后记录读取到同一 heartbeat `2026-10-04T02:54:30.002831+00:00`，只支持当时两个 worker 存活且没有已登记失败，不能作为长期无影响或新训练进展的证据。保护核验为 stat 对照，没有重新读取大文件内容验证哈希。

## 审计文件与恢复边界

材料位于 [`artifacts/storage_cleanup_20261004_followup_history_01/`](../artifacts/storage_cleanup_20261004_followup_history_01/)：`audit.json` 为逐文件候选和输入存在性证据；`cleanup.py` 为绑定 helper/audit 的一次性包装脚本；`plan.json`、`execution_intent.json`、`result.json` 分别登记精确计划、执行前状态和实际结果。计划 SHA256 为 `e4746f80d0f114a9b6fadf3cc302239252253abae756071288e1913854ae10eb`。

**删除的中间文件没有另做备份，不在 Git 中，无法通过 Git 还原。** 审计清单不是内容备份；保留源信息也不保证逐字节复现。所有旧报告和结论保持原样，本次释放空间不构成实验结果改善或新科学结论。
