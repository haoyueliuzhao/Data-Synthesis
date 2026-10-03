# 历史梯度缓存清理记录（2026-10-04）

用户授权清理存储，并明确要求不要影响当前实验。本次将历史梯度清理收窄到两个旧 VTDO 实验中的四个目录，只逐文件删除已审计的直接子级 `.safetensors`。北京时间 **2026-10-04 00:20:48**，执行结果登记为 `complete`：删除 **1,400 个文件**，原实际分配 **113,116,774,400 字节，约 105.3482 GiB**。

当前金融实验目录、所有 QA 缓存、九个固定 Student 保存点及原始来源均不在删除范围内。执行前后六个训练 worker 的 PID 与进程 birth 标识相同，权威队列均为 `V21_SIX_GPU_QUEUE_RUNNING`，`failures=[]`。本次没有修改实验算法、材料、旧结果或旧报告，也没有停止、重启或调度 GPU 实验。

## 精确删除范围与计量

以下路径相对于 `trusted_data_synthesis/artifacts/vtdo_experiment/`。每一行仅包含该目录直接子级的普通 `.safetensors` 文件，不包含目录元数据，也不递归扩展到相邻目录。

| 实验目录 | 梯度子目录 | 删除文件数 | 原逻辑字节 | 原实际分配字节 |
| --- | --- | ---: | ---: | ---: |
| `finance_v13_gradient_projection_dev30_k3_v12_production_candidate_v14_20260804` | `state_gradients` | 300 | 24,238,560,000 | 24,239,308,800 |
| 同上 | `common_token_gradients` | 300 | 24,238,560,000 | 24,239,308,800 |
| 同上 | `differential_token_gradients` | 300 | 24,238,560,000 | 24,239,308,800 |
| `finance_v22_development_exact_target_v1_20260808` | `state_gradients` | 500 | 40,397,600,000 | 40,398,848,000 |
| 合计 | 四个目录 | **1,400** | **113,113,280,000** | **113,116,774,400** |

逻辑字节来自 `st_size`，实际分配字节来自 `st_blocks × 512`，GiB 按 1024³ 字节计算。候选文件均为单硬链接普通文件，四个目录内没有其他文件或子目录。清理保留目录本身，因此目录继续存在是预期行为。

这次删除量与[2026-10-03 的清理](legacy_training_artifact_cleanup_20261003.md)分别登记，没有将已删除的旧缓存再次计入释放量。

## 历史实验性质与生成依据

### V13 梯度投影实验

该实验的原始 `report.json` 记录 `status=partial`、`production_authorized=false`，阻塞项包括 `gradient_numeric_precision_failed`、尚未运行的 post-global-update GP-C 和独立局部分布干预。清理不将它改写成完成、通过或生产授权状态。

生成代码为 [`phase1_contribution_gradient.py`](../src/trusted_synthesis/experiments/vtdo_experiment/phase1_contribution_gradient.py)：审计时约第 3000 行创建三类梯度目录，第 3006 行读取冻结的 `target_records_path`，第 3018 行起加载基础模型和 beneficiary adapter，第 3054 行起根据已登记的种子、记录和 token 分区计算梯度。这三类 `.safetensors` 是生成的中间梯度，不是 adapter 或训练保存点。

审计读取了保留的 `plan.json`。其中十个外部输入路径均存在，包括任务状态、当前分布、数值契约、Objective 支持记录及其 plan/report、原始 state realizations 及其 report、基础模型和 beneficiary adapter。另保留该实验自己的 `target_records.jsonl`、计划、报告和全部 worker 记录。

对以下五项已登记的 JSON/JSONL 输入计算文件 SHA256，结果均与计划登记值一致：

- `current_distributions_path`；
- `numeric_contract_path`；
- `source_records_path`；
- `target_records_path`；
- `state_realization_manifest.source_path`。

其他外部输入在本次核对其路径存在，没有笼统宣称所有输入均已重新计算哈希。原始计划中的 `beneficiary_adapter_tensor_sha256` 是模型张量内容摘要，其算法见 [`phase1_probe_gpu.py`](../src/trusted_synthesis/experiments/vtdo_experiment/phase1_probe_gpu.py) 约第 385 行；它不是 `adapter_model.safetensors` 文件字节的 SHA256。本次未加载完整模型重算该张量摘要。

### V22 Development exact-target 实验

该实验保留的 `report.json` 状态为 `development_target_variance_measured`。[原始报告](finance_v22_development_exact_target_report.md)日期为 2026-08-08，明确属于 Development-only，生产 Contribution 仍为零，不能用于宣称 Validation 成功或 Student 效果。报告记录两个 state worker 各完成 250/250 个梯度任务，共 500 个，与本次删除的 state gradient 文件数一致。

生成代码为 [`phase1_development_target.py`](../src/trusted_synthesis/experiments/vtdo_experiment/phase1_development_target.py)：审计时第 473 行定义 `run_state_gradient_worker`，第 488 行起读取原始 realizations，第 508 行创建 `state_gradients`，第 553 行起计算单个 realization 的梯度并写入 `.safetensors`。本次保留 Objective 梯度、各类均值与聚合梯度、global gradient/update、state gradient checkpoint JSON，以及报告中的 4,000 个目标观察记录。

保留的 `contract.json` 登记的十一个外部输入路径均存在。其 `inputs` 中以下九个文件的实际 SHA256 均与登记值一致：

- `development_contract`、`development_report`；
- `distributions`；
- `objective_records`、`objective_support`；
- `realization_report`、`realizations`；
- `source_gradient_plan`；
- `task_states`。

剩余两个外部输入为模型和 beneficiary adapter 目录。两实验共用的 `Qwen2.5-7B-Instruct-a09a35458c702b33eeacc393d103063234e8bc28` 模型目录中，四个权重分片、模型配置、权重索引和 tokenizer 文件均存在；`finance_phase1_mvp_v1/beneficiary_adapter/adapter_model.safetensors` 及配置也存在。本次没有读取全部模型分片或启动 GPU 来验证模型内容、重算历史梯度。

## 当前实验与后续队列依赖审计

清理前先检查当前进程的运行路径和参数，并结合源码依赖核对，不能仅以文件年龄或没有打开的文件描述符认定可删除。

当前活跃金融进程使用根项目 `trusted_data_synthesis/.venv`，运行工作树为 `finqa-v18-researcher-continuation-20260930`。其 V18/V19/V20/V21 队列及训练输出位于 `finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01` 下，本次完全保留该范围。

定向检查包括：

1. main 和活跃 V18 工作树的 `src/trusted_synthesis/finance_research`，以及有关队列脚本；未找到对 `vtdo_experiment/` 或两个候选历史实验路径的依赖。
2. 当前实验间接依赖的 `finqa-v10-proxy-frozen-20260930`、`finqa-v15-prefix-20260930`、`finqa-v16-six-continuation-20260930`、`finqa-v17-three-continuation-20260930` 四个工作树，对各自 `finance_research` 和 `scripts` 共八个根目录的 Python/shell 文件搜索，同样未找到上述路径引用。
3. 金融代码引用了旧 QA 的部分实现代码，`calibration.py` 中存在指向 `qa_vnext_fixed_kernel_value/cross_market_calibration_cache_20260926/evaluation_01` 的数据路径。该目录和全部 QA 缓存都保留，不能因其归属“历史缓存”而整目录删除。
4. 执行脚本在生成计划和实际删除前检查当前账户可见进程的 cwd、解释器、命令行、内存映射和文件描述符，未发现四个候选目录被使用。

这些证据支持候选梯度不属于本次观察到的当前训练或已登记队列依赖。路径搜索不能证明任意未来新增代码都不会引用旧数据，进程检查也受可见权限和采样时刻限制；本次没有把它们描述为对所有未来实验的永久保证。

## 保留边界与执行保护

本次完整保留以下内容：

- 整个 `finance_research_20260928`，当前模型、材料、训练状态、队列与恢复依赖；
- 全部 `qa_vnext_fixed_kernel_value`，包括两个 delayed 缓存、跨市场校准缓存、九个固定 Student，以及其原始 `updates/0240.pt` 等来源；
- 两个历史实验的 JSON/JSONL、原始输入、manifest、worker 记录、计划、报告、状态检查点元数据；
- 未列入四目录的所有张量，包括 state mean、task、evaluation、Objective、global 张量及 partial 分区；
- 基础模型、adapter、其他正式实验结果、账本及审计证据。

执行采用逐文件 `unlink`，没有递归删除整个实验目录。计划记录每个目标的路径、设备、inode、逻辑大小、分配字节、链接数、mtime 和 ctime。实际执行绑定计划 SHA256 与脚本 SHA256，拒绝符号链接或重定向路径、非普通文件、多硬链接文件、Git 跟踪文件，以及与计划身份不符的文件；清理前再次确认固定的 1,400 项与总分配字节。

九个固定 Student 的 `point.json`、adapter 和 `origin_checkpoint` 共 27 个文件，通过执行前后文件身份与状态对照，全部未变。此次是 stat 对照，没有重读所有大文件内容重算 SHA256。`result.json` 的 `retained_files_unchanged=0` 仅表示四个被清理目录内部没有其他需逐文件对照的文件；不表示周边报告、模型或其他保留范围为空，也不表示对全部周边产物做过内容哈希审计。

## 执行结果与动态限制

执行意向、执行前后状态及最终结果均登记在北京时间 **2026-10-04 00:20:48**；时间字段仅精确到秒，不能据此推断操作实际耗时为零。

| 核验项 | 结果 |
| --- | --- |
| 执行结果 | `complete` |
| 白名单文件 | 1,400 项全部不存在 |
| 删除文件原实际分配 | 113,116,774,400 字节，105.3482 GiB |
| 执行前磁盘空闲 | 473,240,027,136 字节 |
| 执行后磁盘空闲 | 586,357,600,256 字节 |
| 同期空闲量净增加 | 113,117,573,120 字节 |
| 固定 Student 保护文件 | 27 项 stat 状态未变 |
| 六个 worker | PID 和 birth 标识前后一致，均存活 |
| 队列阶段 | 前后均为 `V21_SIX_GPU_QUEUE_RUNNING` |
| 排队任务 | 前后均为 `arm-47-manual_minus` |
| 队列失败列表 | 前后均为 `[]` |

磁盘空闲净增加比被删文件分配字节多 798,720 字节。这两个指标分别是全盘动态快照差值与白名单文件原占用，不能混为一谈。同期训练或其他进程可能继续读写，目录/文件系统元数据也可能变化；本次没有单独测量并归因该差额。

删除不是全局原子操作，没有锁住整个项目或暂停实验。进程状态、目录内容和磁盘空间的核验分别发生在各自采样时刻。执行前后队列读取到相同的 heartbeat `2026-10-03T16:20:47.075852+00:00`，因此这里只报告边界时刻六个 worker 仍存活、状态一致且没有已登记失败，不把同一 heartbeat 解释成已观察到一轮新的训练进展，也不宣称完成了长期无影响验证。

## 恢复限制与审计材料

**被删除的原始梯度张量没有另做备份，不在 Git 中，不能通过 Git 恢复。** 保留生成输入、种子、代码和汇总结果意味着可以据此尝试重新计算，不等于保留原始张量，也不保证能重新得到逐字节相同的文件。需要重新配置相应运行环境并消耗 GPU 资源；本次没有为证明可复算性重新运行历史实验。

旧 V13 worker 会校验已登记梯度文件是否存在及其哈希，旧 V22 worker 同样会校验 `state_gradient_checkpoints` 中登记的文件。因此直接在原目录执行旧 resume 将因已删除梯度缺失而拒绝继续。未来若确实需要重新计算，应在隔离输出目录依据保留的计划、契约和输入重新生成，并单独登记重算结果；不要删除或改写原报告和旧 checkpoint JSON 来伪装成原运行无缝续跑。

操作材料位于 [`artifacts/storage_cleanup_20261004_gradients_01/`](../artifacts/storage_cleanup_20261004_gradients_01/)：

- [`cleanup.py`](../artifacts/storage_cleanup_20261004_gradients_01/cleanup.py)：固定四目录的一次性清理实现；
- [`plan.json`](../artifacts/storage_cleanup_20261004_gradients_01/plan.json)：逐文件身份、分配字节、保护对象和执行前状态；SHA256 为 `f8748f66c13f0a69873a5f45402a1d3b946e60009b416a5544e00645be2181aa`；
- [`execution_intent.json`](../artifacts/storage_cleanup_20261004_gradients_01/execution_intent.json)：实际执行前的计划绑定与队列状态；
- [`result.json`](../artifacts/storage_cleanup_20261004_gradients_01/result.json)：删除统计、保护对照、磁盘与运行状态结果。

上述文件是清理的审计索引与执行记录，不包含已删除张量的内容，不是恢复备份。本次存储清理不改变旧实验科学结论，也不构成实验指标改善或新效果的证据。
