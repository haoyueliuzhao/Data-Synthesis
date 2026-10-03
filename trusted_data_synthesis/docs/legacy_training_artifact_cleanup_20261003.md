# 早期训练中间产物清理记录

2026年10月3日，用户在看到约228 GiB的精确候选范围及旧张量复算、断点续训损失说明后，回复“确认清理无用数据”。本次已删除5,302个白名单文件，原实际占用244,386,717,696字节，约227.60 GiB。没有递归删除整个实验目录。

当前 FinQA 训练材料、V14编码、V15共同前缀、V18训练与断点，以及九个固定Student保存点均保留。六个训练进程在清理前后持续存活，没有新增队列失败。本次只回收存储，不修改实验算法或结果，不新增API、GPU实验或模型训练。

## 实际删除范围

以下路径相对于 `trusted_data_synthesis/artifacts/`。表中的实际占用按文件 `st_blocks × 512` 求和，GiB按1024³字节计算；没有将保留下来的目录元数据计入删除量。

| 分组 | 删除文件数 | 原实际占用字节 |
| --- | ---: | ---: |
| 8月已取消的旧VTDO v21张量 | 169 | 13,654,810,624 |
| 从未派发的V13旧请求草稿 | 1,316 | 351,555,584 |
| 旧代理审计梯度 | 332 | 108,375,097,344 |
| 旧B确认实验outer梯度 | 1,714 | 67,169,419,264 |
| 旧方向可靠性响应梯度 | 1,711 | 51,924,168,704 |
| 六个早期可行性训练的断点载荷 | 60 | 2,911,666,176 |
| 合计 | 5,302 | 244,386,717,696 |

8月取消实验仅删除以下两个目录内的 `.safetensors`，不是当前六卡队列的V21版本：

- `vtdo_experiment/finance_v21_target_observability_local_updates_v1_20260807/`
- `vtdo_experiment/finance_v21_direct_target_observability_study_v1_20260807/`

该运行只完成两个角色各9／32项观察，取消状态和部分结果继续保留，依据见[旧取消报告](finance_v21_target_observability_report.md)。删除其张量不将取消状态改成完成或通过。

V13仅删除 `finance_research_20260928/finqa_v6_01/v13_material_01/requests/` 中的请求草稿文件，保留原definition、preparation和superseded记录。该矩阵在派发前被 `v13_material_02` 替代，模型调用和钱包登记均为0；它不是当前正式材料来源。

三组旧梯度缓存的共同前缀是 `qa_vnext_fixed_kernel_value/`，精确范围为：

| 子目录 | 允许删除的文件 |
| --- | --- |
| `proxy_audit_cache_20260919/jobs/A_full_{11,29,47}_epoch{0,5}/` | `class_gradients.npy`、直接位于 `positive_gradients/` 的 `.safetensors` |
| `delayed_C_B_confirmation_cache_20260922/outer/B_delayed_c_{11,29,47}/` | `population.pt`、直接位于 `replay/` 的 `.pt` |
| `direction_calibration_cache_20260926/reliability/B_direction_reliability_{11,29,47}/` | 直接位于 `responses/` 的 `.pt` |

这些旧实验已有完成报告，但“已完成”不等于张量没有历史价值。本次按用户选择放弃这些中间张量的本地保留；报告、实际结果及失败记录不改写。特别保留B确认实验的 `virtual_point/adapter.safetensors`，没有删除整个outer目录，也没有删除任何 `jobs/*/updates/0240.pt`。

早期可行性训练共同前缀为 `feasibility/architecture_mvp_20260730/`，仅处理下列六个运行的 `trainer_state/`：

- `training_D2`
- `training_C2_current`
- `training_C2_80k`
- `prompt_v5/train_D2`
- `prompt_v6/train_D2`
- `prompt_v6_complete_contract/train_D2`

比原候选范围进一步收窄：只删除其 `checkpoint-*/` 中的 `optimizer.pt`、`rng_state.pth`、`scheduler.pt`、`training_args.bin` 和内嵌 `adapter_model.safetensors`，保留36个JSON／README。六个同级最终 `adapter/` 目录均完整保留，因此最终模型仍可加载，但不能再凭删除的旧优化器／RNG状态精确续训。

## 保留范围与删除边界

执行前核对每个目标均为项目artifact范围内的普通单链接文件，路径及其祖先没有重定向；目标没有Git跟踪记录，也未发现当前账户可见进程打开这些文件。逐文件计划记录路径、设备、inode、大小、分配字节以及mtime／ctime，执行要求脚本、计划哈希和文件状态保持一致。

具体操作为逐文件 `unlink`，不递归移除目录。请求草稿之外的JSON／JSONL、报告、预算与钱包、原始回复和生成轨迹不在删除名单中。清理后核对同一批目录内226个保留文件的身份、大小和mtime／ctime均未变；空目录可以继续存在，不代表清理未完成。

另有69个显式保护文件通过前后对照，包含九个Student的point元数据、adapter、原始step240保存点，以及六个早期训练的最终adapter目录文件。其中九个adapter和九个原始step240文件的SHA256均与对应 `point.json` 登记值一致，清理后再次核对一致。整个 `cross_market_calibration_cache_20260926` 不在清理范围内。

本次不清理当前 `finance_research_20260928` 的其他数据，不改V10至V18的材料与恢复依赖；也没有扩大到整个旧VTDO目录、其他固定核缓存、财务备份、测试临时目录、pip缓存、模型环境或其他工作树。

## 运行核验与空间结果

北京时间11:49:44生成清理计划。11:51:09实际执行前，数据盘空闲404,832,452,608字节；11:51:11执行完成，空闲649,219,641,344字节，约604.63 GiB。同期空闲量净增加244,387,188,736字节，约227.60 GiB。

删除文件原占用与磁盘空闲净变化是不同指标。并行训练和其他进程仍可能写入，目录元数据分配也可能变化；本次不将二者微小差额归因于未经单独计量的原因。

| 核验项 | 实际结果 |
| --- | --- |
| 白名单文件 | 5,302项全部不存在 |
| 同范围保留文件 | 226项状态未变 |
| 显式保护文件 | 69项核对未变 |
| 九个固定Student及其原始step240文件 | 哈希与登记值一致 |
| 权威队列 | `V21_SIX_GPU_QUEUE_RUNNING` |
| 当前任务 | 六项运行、五项排队、`failures=[]` |
| 六个worker | PID与birth标识前后一致，均存活 |
| 训练信号或运行策略修改 | 无 |

没有重跑旧科学实验来证明其可恢复性。必要核验限于清理边界、保护对象、删除结果、磁盘与当前运行状态。

## 恢复限制和审计文件

被删除的张量和草稿原件没有另做备份，且不在Git历史中，不能通过Git恢复。保留报告和最终模型不等于保留了旧中间梯度，也不保证能重新得到逐字节相同的张量。旧运行如需逐张量验证或从被删除的优化器状态续训，原有本地路径已不可用；本次不宣称无损去重。

操作证据位于 `artifacts/storage_cleanup_20261003_legacy_training_01/`：

- `cleanup.py`：仅用于本次固定白名单的一次性操作代码，不是通用自动清理服务。
- `plan.json`：逐文件身份清单、分组、保留文件和保护对象快照。其SHA256为 `dff4e3a2188fdbe2f9e9e8d4f43defbe562db4ab82c5b5835c345f7907901dce`。
- `execution_intent.json`：执行前计划绑定和运行状态。
- `result.json`：实际删除量、保护核验、磁盘和训练状态。

这些清单是审计索引，不包含被删除文件的内容，不是恢复备份。本次说明和必要操作证据纳入Git；已删除的大文件不会作为本次提交内容上传。
