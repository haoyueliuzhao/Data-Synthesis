# V14 状态无关监督编码与追加式缓存（2026-09-30）

## 范围与不变条件

本实现把原包监督编码与状态分区/权重绑定分开。固定总体仍为 V13 已登记的 2468 个共同原包、744 个任务；已有明确监督权威的 2465 包可以先做 CPU 编码，不等待映射。先编码不等于先训练；缓存本身不生成材料 binding，也不授予任何训练权限。

本次没有修改冻结的 V13 编码、材料或运行记录。新增 `v14_student_encoding.py`、`v14_encoding_cache.py`；现有 `v10_training.py` 仅增加 `v14_material_binding.v1` 的显式加载分支，`v8_training_driver.py` 仅增加 V14 实际更新元数据映射。状态无关编码不读取 state、χ、π 或 `n_xz`，原损失和反馈机制未改变。

完整原始公开历史、真实工具观察、原参数字节、Student EOS 和 24576 上下文限制继续保留；不截断，不删除困难包。观察仍只进入输入。SFT 正向 mask 不替代反馈采样 Token/EOS 的概率域。目标分母 `L_P` 仍是整包的唯一监督 Token 数，不按 reason/tool/final 分层归一化。

## 原批准范围的幂等语义

V14 manifest 保存同一明确权威给出的全部原始字符范围，包含重复或相交范围。每个范围先独立按照既有规则选择“Token 完整落在该原批准范围内”的位置，然后对位置取布尔并集：

`T_positive = union_j T(original_approved_span_j)`。

不先合并字符区间。例如 Token 覆盖 `[4,8)`，原批准范围为 `[4,6)` 与 `[5,10)`，该 Token 不完整落入任何一个原批准范围，因此不能新增监督；若先合并字符区间会错误地批准该 Token。重复批准同一 Token 不重复计算 loss。是否确属无冲突、同权威正向冗余由独立 V14 表示复核确定，编码器不补做语义判断。

新 manifest schema 为 `v14_package_supervision.v1`，编码 schema 为 `v14_student_encoding.v1`，策略为 `v14_state_independent_original_span_union.v1`。权威引用、原投影、原包摘要和公开 view 都直接进入绑定；改变监督来源不能复用旧 mask。

## 缓存目录与调用约定

默认缓存目录为：

`trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v14_representation_01/encoding_cache/`。

- `registration/record.json`：固定全部 2468/744、V13 原始来源、tokenizer/template、软件版本、上下文和编码源码 SHA。
- `revisions/0000/record.json`：原 2465 权威与尚未解决的 3 包。后续编号只追加尚未解决的权威，不覆盖此前 manifest 或缓存。
- `manifests/<cache_key>/record.json`：包级固定监督 manifest。
- `encodings/<cache_key>/record.json`：实际编码或明确失败；cache key 同时绑定原 Episode 文件/内容、监督来源、manifest、tokenizer/template、上下文、实现源码及 tokenizer 软件版本。
- `runs/<authority_revision.id>/record.json`：该追加修订下所有已明确权威都有真实编码结果的完成标记。它不是训练材料 binding。

CLI 使用 `python -m trusted_synthesis.finance_research.v14_encoding_cache prepare|run|inspect|append --output <cache_root>`。`prepare` 只登记来源与 manifest，不编码；`run --workers 8` 只编码缺失 cache key；`append --authorities <list.json>` 只接受待补包的明确 V14 来源。每项追加结构为 `{slot_id, projection_authority, authority_record:{path,id,sha256}}`，权威类型为 `V14_derived_overlap` 或 `V14_completion_only`。

编码最多使用 8 个 CPU worker；worker 内显式 `TOKENIZERS_PARALLELISM=false`，主进程按登记顺序持久化。已存在的缓存不会重算来择优；失败也保留在全量结果中。源码冻结后若改变，会拒绝静默复用。

`load_cache(cache_root, require_complete=False)` 返回原固定 task/slot 列表、已有编码、manifest、相应文件引用、pending 列表及 tokenizer 绑定，不再次加载 tokenizer 或重做全量编码，但会核验原包字节及缓存/权威引用。`require_complete=True` 仅检查全 2468 包编码已齐且可用，不等于检查状态映射完成，也不授训练权限。最终 V14 材料消费者必须关联全部 744 题的状态、频数与 χ，并通过完整共同核检查后发布唯一训练 binding。

## 必要 CPU 控制及当前边界

仅运行 `tests/test_finance_v14_encoding_cache.py` 的 7 项必要测试，结果为 **7 passed，6.55 秒**；所改源码和测试 Ruff 通过。覆盖：

- 非重叠旧权威的 V10/V14 原始 rows、目标位置、EOS、`L_P` 完全相同。
- 合成偏移与真实 tokenizer 上均验证“先逐 span 选 Token 再 union”，不新增跨 span Token。
- 原重复批准保留在 manifest，目标和 loss 不重复。
- 权威改变导致不同 cache key；伪造 mask 被拒绝。
- 映射未提供时可完成包级编码；追加只补待补包，旧缓存字节保持不变。
- 缓存读取不重新调用 tokenizer；原包文件变化被拒绝；不完整总体不能通过 complete 检查。
- V14 显式 consumer dispatch 和一次真实 tiny CPU 更新元数据正确，未新增 batch 分母。

测试进程曾先运行线程库，产生两条 Python `fork()` 多线程环境弃用警告；控制运行完成，无 hang。测试均为明确合成来源、临时目录中的 CPU 控制，不是 2465 包正式编码、真实材料准入、GPU 吞吐或训练结果。正式缓存准备与编码由主工作流在源码/登记冻结后启动，不由本次控制测试触发。
