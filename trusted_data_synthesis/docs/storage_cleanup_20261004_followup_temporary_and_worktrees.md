# 后续测试夹具与工作树空间整理（2026-10-04）

用户再次授权清理历史无用数据，并要求不影响当前实验。本轮在北京时间 2026-10-04 10:47:31 +08:00 至 2026-10-04 10:47:35 +08:00 清理6组已闲置CPU/mock/pytest夹具，原分配块占用合计 **4,407,644,160 字节（4.104939 GiB）**，共6,178个普通文件、66个pytest符号链接。所有计划项已执行，没有扩大到整个工作树或正式实验目录。

本轮保留全部20个现存工作树（19个FinQA工作树及1个未合并QA工作树），没有移除Git工作树登记、修改代码、覆盖未提交脚本或改变训练配置。同期历史VTDO/QA张量清理使用其他清单，本记录不统计其删除量。

## 清理前空间与增长

本轮只做一次全项目分层 `du -x -B1 --max-depth=3`，不跟随符号链接。以下为约北京时间10:44的清理前快照，不是任务结束后的静止总量。

| 范围 | 本轮快照字节 | GiB |
| --- | ---: | ---: |
| `项目合计` | 1,016,691,007,488 | 946.87 |
| `trusted_data_synthesis/artifacts` | 973,007,261,696 | 906.18 |
| `artifacts/finance_research_20260928` | 655,197,970,432 | 610.20 |
| `artifacts/vtdo_experiment` | 191,792,664,576 | 178.62 |
| `artifacts/qa_vnext_fixed_kernel_value` | 104,245,854,208 | 97.09 |
| `.codex-worktrees` | 23,340,703,744 | 21.74 |
| `.git` | 11,113,586,688 | 10.35 |

首次排查的 `finance_research_20260928` 为559,305,412,608字节，本轮为655,197,970,432字节，增加 **95,892,557,824字节（89.31 GiB）**。这与持续运行实验的输出增长一致，但本轮没有逐文件归因其增长，也没有据此删除训练检查点。

主工作区 `artifacts/test_tmp` 在上一轮清空后仍为空，根目录mypy/pytest/Ruff缓存也未重建；本轮没有触碰这些空路径。保留工作树内另有约2.5 MiB的工具缓存，本轮没有为这类小额占用扩大清理或审计范围。

## 实际清理清单

下表均相对项目根目录，字节包含目录元数据。三个主工作区的旧测试运行目录整体移除；三个保留工作树只移除 `test_tmp` 内明确命名的5个测试运行子目录，保留空的 `test_tmp` 父目录。

| 分组与路径 | 清理前字节 | 清理后字节 | 用途证据 |
| --- | ---: | ---: | --- |
| `trusted_data_synthesis/artifacts/v10-retry-cpu.WZaKYF` | 417,488,896 | 0 | v9-synthetic-parent、synthetic-v10-history及test_*夹具，包含v10-test.sqlite。 |
| `trusted_data_synthesis/artifacts/v10-retry-regression.yn4Y3A` | 391,200,768 | 0 | 旧retry回归测试；synthetic-new-v10、test_*及模拟钱包。 |
| `trusted_data_synthesis/artifacts/v10-network-retry-cpu.YIb0E8` | 304,828,416 | 0 | 旧网络重试CPU测试；synthetic父任务及test_group_*测试数据库。 |
| `.codex-worktrees/finqa-v12-rereview-20260930/trusted_data_synthesis/artifacts/test_tmp` | 2,194,804,736 | 0 | 3组v12-budget测试：Na5nHm、final-zOO9iO、tQIJWt；v12-funded-fixture及预算边界用例。 |
| `.codex-worktrees/finqa-v13-material-20260930/trusted_data_synthesis/artifacts/test_tmp` | 1,097,949,184 | 0 | v13-execution-PzvmyJ；模拟history、v12-funded-fixture与控制器test_*用例。 |
| `.codex-worktrees/finqa-v13-c16-20260930/trusted_data_synthesis/artifacts/test_tmp` | 1,372,160 | 0 | v13-c16-hJ4VtC；固定16任务及模拟预算注册test_*用例。 |

主工作区三组测试夹具合计1,113,518,080字节；保留工作树内部测试夹具合计3,294,126,080字节。这些旧文件最后修改时间均位于2026-09-29至2026-09-30，尚未发现本轮运行继续写入。

## 执行边界与当前实验核验

- 已读取相关工作树AGENTS.md，测试临时目录的用途与约定一致。每组清理前均核对没有Git跟踪内容、没有硬链接、路径祖先没有符号链接重定向，元数据身份摘要与固定计划一致；任何变动按保留处理。
- 所有66个符号链接均指向对应候选树内的pytest路径。使用不跟随符号链接的删除实现；没有通过链接访问或移除树外内容。
- 当前训练代码、队列脚本与runtime记录未检索到候选测试目录的精确路径或 `artifacts/test_tmp` 引用。新鲜 `/proc` 检查的cwd、绝对路径命令参数、打开文件没有候选使用者。当前账户不可访问或已退出的4个进程条目保留在结果中，结论不扩展为其他账户的全面进程审计。
- 当前实验的cwd/PYTHONPATH仍为v18研究工作树，环境为主项目 `.venv`；其FinQA v18→v17→v16→v15及v10恢复依赖链、v19-v21控制树全部保留。没有把“当前无进程”当作这些工作树可删除的证明。
- 5个Data-Synthesis实验进程在清理前后PID/birth标识一致：`73792`、`73851`、`895990`、`1475362`、`2927149`。其中包括v21队列与seed47 Full、v18恢复控制、seed47 Manual- worker及v19控制。此前已结束的worker不再套用上一轮进程列表。
- 3个涉及测试夹具的FinQA工作树，清理前后Git状态完全一致。v13-material内用户未跟踪的 `trusted_data_synthesis/scripts/finqa_v13_support_report.py` 的文件身份、大小、mtime/ctime和小文件SHA256均未变；未对其提交或覆盖。
- 未停止或重启任何实验，没有运行新模型/API调用，也没有为清理重新执行科学实验。进程身份核验说明同一批进程仍存活，不单独证明科学结果正确。

## 计量、保留与恢复限制

回收量按已删除对象原分配块占用计算，不将并行训练写入及其他清理造成的磁盘空闲净变化归因于这6组测试夹具；为减少重复扫描，没有在执行后再次遍历整个项目。正式训练保存点、模型环境、钱包与原始数据均不在本清单内。

工作树本体继续保留，尤其是存在当前/恢复依赖的FinQA树、未合并QA树和未提交用户脚本。本轮没有宣称任何正式产物或备份已证明重复，没有对其删除。

已删除的mock数据库和测试上下文没有另作内容备份，不可通过本审计文件恢复原数据；可以重新执行对应测试生成新夹具，但不保证逐字节一致。审计清单只记录路径与元数据，不是原文件备份。

## 审计位置

`trusted_data_synthesis/artifacts/storage_cleanup_20261004_followup_temporary_01/`：

- `plan.json`：固定6组目录、测试子目录结构、字节数、最后修改时间与身份摘要。
- 计划SHA256：`dde2e84451de36292493dbf58ca9872fa918224ff26ae8928f54fd23e85cb75f`。
- `result.json`：逐组前后占用、进程身份、工作树Git状态及用户脚本保护结果。
- `cleanup.py`：本次固定计划的一次性执行程序副本；其原始运行输入位于 `/tmp`，不构成自动清理或再次执行的承诺。
