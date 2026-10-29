# 2026-10-29 旧冷归档跨盘迁移

用户明确选择“先整理历史数据，腾出数据盘空间”。本次登记独立计划，只迁移2026-10-19已经完成成员校验的三个`old_class`冷归档；全部内容可恢复，保留原路径访问、原归档SHA、原成员清单及恢复脚本。

当前状态：单次apply已以COMPLETE完成，三包均通过复制时源SHA、目标完整读回SHA及fsync后，原路径原子切换为符号链接。原恢复入口和归档内容保持。V76仍须在派发时使用实时磁盘及GPU资源准入，迁移完成不等于科学实验已经启动。

## 范围与目的

/data1准备时剩余约1.7GiB，无法满足新实验的128GiB磁盘准入。本次将旧冷归档存放到其他本机持久文件系统，在/data1原文件路径保留指向已验证目的文件的符号链接。这是**跨盘搬移，不是全机净回收144GiB**，也没有删除任何科学内容。

| 归档 | 字节数 | GiB | 新位置 |
|---|---:|---:|---|
| old_class_seed137.tar.zst | 25,826,693,087 | 24.052982 | `/data0/zhuxinrui/cold_storage/Data-Synthesis/cold_archive_20261019_01/` |
| old_class_seed251.tar.zst | 51,650,203,894 | 48.103004 | 同上 |
| old_class_seed389.tar.zst | 77,479,236,857 | 72.158165 | `/home/zhuxinrui/cold_storage/Data-Synthesis/cold_archive_20261019_01/` |
| 合计 | 154,956,133,838 | 144.314146 | 两个不同于/data1的文件系统 |

原位置均为`trusted_data_synthesis/artifacts/cold_archive_20261019_01/`。新目录权限700、新文件600，仅本用户管理。`/home/zhuxinrui/datatmp`实际指向/data1，未选为目的地；没有使用临时目录长期存放归档。

准备时data0预计剩余31.37GiB、系统盘预计剩余66.13GiB。apply开始和复制期间仍检查真实可用容量，预留至少16GiB，不能把这份准备快照当作未来容量保证。

## 一次执行规则

1. prepare仅读取原receipt、源inode/大小/所有权及目的容量，固定三包和实施源码，不读取全部144GiB内容、不复制归档。
2. apply要求三份源仍为本人拥有的普通单链接文件，inode、大小、mtime、ctime等身份与计划相同；目的文件及临时文件均不能已存在。
3. 至多三个复制线程。复制时计算完整源SHA，必须匹配原`*_verified.json`中的SHA；复制后完整重读目标文件，再核对同一SHA。
4. 三包目标文件及目录全部fsync且完整验证后，才发布`all_copies_verified.json`。在此之前，三个源路径均保持原普通文件。
5. 逐包建立临时符号链接，并用同目录`os.replace`原子替换原归档文件路径；替换前再次核对源身份和目标身份。没有先删源再创建链接的空窗。
6. 每包保存替换证据。异常保留原件或已经验证的目的内容及部分状态，记录`PARTIAL_STOPPED_NO_RETRY`，不自动重启已消费的apply。

本次不压缩新科学产物，不改模型、Adam、RNG、反馈、评分、梯度缓存或冻结代码，不给任何实验进程发信号。

## 原恢复接口兼容性

原2026-10-19包装器仍调用2026-10-10冻结恢复引擎。该引擎对归档文件做原路径字符串与原SHA检查，随后通过zstd打开；它没有要求归档文件本身必须不是符号链接。因此，只要目的完整字节保持原SHA，原路径上的文件符号链接继续满足恢复接口。

恢复的输出位置仍须是已有、空的canonical目录；该要求没有放宽。原恢复脚本、receipt、成员清单和SHA均不修改。恢复命令见[原冷归档说明](storage_cleanup_20261019_lossless_cold_archive.md)。

## 未采用的压缩方案

一次只读范围检查发现，指定V54/V63/V70/V71历史训练目录共有4782个state.pt、约136.66GiB，原登记SHA中没有跨inode逐字重复候选。对其中三个相邻V54/Hold checkpoint进行有界试压：原总92,058,981字节，首基zstd加两个原始字节XOR增量zstd共75,273,465字节，节省约18.23%，两个增量均逐字解码并匹配原SHA。该比例不足以达到此次空间目标，因此没有据此归档或移除任何checkpoint。

## 计划与必要核验

独立目录：`trusted_data_synthesis/artifacts/storage_cleanup_20261029_cold_relocation_01/`。

计划ID：`0f7e7c78039591b85c4e3beaa924b13b2595df68251600228acbb2abeec1701f`。

冻结执行器：同目录`relocate.py`，SHA256 `2c27ae33470f57daec67afb53707d3be885070f36a05fb7b8afc94bf008ede11`。源实现位于`scripts/storage_cleanup_20261029_cold_relocation.py`。

9项小型CPU测试使用临时目录及/dev/shm中的实际字节，覆盖全三包验证先于首个源替换、双SHA、原路径可读、目标权限、源变化/坏SHA/目标读回不一致时保留原件、不覆盖目标、同盘不冒充腾空间及禁止重复apply。测试数据已由fixture清理，没有触及真实三包归档。

准备阶段仅登记方案；下节依据单次apply的`result.json`补记实际迁移、目的验证、原路径替换和磁盘观测。科学实验是否启动由V76自己的launch与验收记录决定。


## 实际完成记录

迁移结果ID：`417a6b930d54842a1f89b1441c841c2157501e701ee924c1d06f12171306c8a4`。三包全部验证后才第一次替换源路径，原数据盘文件已解除链接的allocated总量为144.314152GiB；报告观察到/data1可用145.942GiB。该可用空间读数也受其他进程影响，不将全部磁盘变化归因本操作。

目的地最终观察：`/data0/zhuxinrui/cold_storage/Data-Synthesis/cold_archive_20261019_01`可用31.362GiB；`/home/zhuxinrui/cold_storage/Data-Synthesis/cold_archive_20261019_01`可用66.109GiB。新目录700、目标归档600，三个原路径均可访问。原receipt及SHA保持，未解压重验归档成员或再次全量hash；使用单次apply已经记录的完整读回验证证据。

[机器摘要](report_data/storage_cleanup_20261029_summary.json)，ID `6d29310b59f80f52fcb2356d240072da82eebe7cfcbc2cf1af83f33f9125f3cd`。执行没有新GPU、模型、API或科学调度操作；三个apply复制线程已经完成，没有自动后继迁移。
