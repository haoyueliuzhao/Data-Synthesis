# 工作区未跟踪测试文件整理（2026-09-30）

用户要求处理大量未提交更改。核对发现：主工作区main、开发工作区均已到`8247b3a484`，主工作区没有已跟踪文件的未提交或暂存修改；实际噪声为11个未跟踪测试临时目录，共1476个Git可见未跟踪文件。目录的总磁盘占用为3,444,903,936字节（约3.208 GiB），含已忽略的测试数据库等内容；这两个数字分别是Git可见文件数与完整目录占用，不能混为同一口径。

开发工作区和最新代理冻结工作区的Git状态均干净，未发现漏提交源码。目录名、内部pytest用例路径和`synthetic-*`、`v10-test.sqlite`等模拟账本表明这11个目录是CPU/mock测试输出，不是本轮正式审阅/训练结果。整理时未发现仍在运行的pytest。

## 处理方式

11个目录整体移动到唯一、可恢复的本地归档：

`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/local_test_archive_20260930_9Yxnr7/`

已有根`.gitignore`的`trusted_data_synthesis/artifacts/`规则覆盖该路径，无需扩大忽略范围。目录内容未重写、未删除，也没有加入Git；本次是同文件系统移动，不是释放磁盘空间。正式实验原件、钱包、checkpoint、已提交审计记录和冻结工作区均未移动或改写，实验继续保持等待审计状态。

| 原仓库根目录名称 | Git可见未跟踪文件数 |
| --- | ---: |
| `.test-v10-final.pJhzDl` | 17 |
| `.test-v10-handoff.Nou12b` | 316 |
| `.test-v10-material.9hWZ7L` | 63 |
| `.test-v10-material.TCgPCG` | 60 |
| `.v10-concurrency-cpu-AmdL6O` | 221 |
| `.v10-final-retry-cpu-vi5TWx` | 131 |
| `.v10-funding-cpu-i7u9ca` | 21 |
| `.v10-network-retry-cpu-iJkG8R` | 132 |
| `.v10-proxy-cpu-UkztoQ` | 12 |
| `.v10-proxy-regression-k72b2F` | 416 |
| `.v10-workflow-cpu-kD4yrV` | 87 |

归档后确认11个同名目录均存在，主工作区`git status --short`已无输出。随后仅提交此整理说明和AGENTS中的临时测试目录约定，避免以后将测试缓存再次堆积在仓库根目录；没有重跑实验或为清理生成API/GPU费用。

## 恢复与后续约定

需要恢复某次测试上下文时，先确认原根目录下的对应路径不存在，再将归档里的同名目录移回原位置；不要覆盖新产生的同名目录。测试夹具中的原绝对路径/符号链接未被改写，恢复到原位置即可恢复其原有路径关系。

后续测试临时目录统一建在`trusted_data_synthesis/artifacts/test_tmp/`下，每次使用`mktemp -d`生成独立目录并传给pytest `--basetemp`。只有正式代码、说明文档与必要审计原件进入版本控制，模拟成绩和测试数据库不作为正式实验结果提交。
