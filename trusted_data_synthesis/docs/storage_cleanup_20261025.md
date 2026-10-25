# 2026-10-25 历史闲置数据清理与恢复

本次依据用户“清理历史无用数据”要求，对明确闲置的测试夹具、可重建工具缓存、已保留正式副本的临时输出，以及四份历史账本快照执行了有界清理。三批均已完成。**数据盘净回收约9.414913GiB；系统盘`/tmp`另移除152.949219MiB，跨两个文件系统合计约9.564278GiB。**

测试数据和历史账本先完成可恢复归档、逐成员验证，再移除展开原件；四份临时重复输出在与保留正式副本逐字一致后才删除。唯一模型/Adam/RNG训练断点、反馈、评价、主账本及其WAL/SHM、旧冷归档、冻结工作树、本地AGENTS和当前V72全树不在删除范围内。

清理后V72仍为`RUNNING`，原监督器、控制器和GPU2的最终dev worker身份保持；三个作业已接受，最后一组生成继续。本次没有暂停、重启、发信号或新增GPU/API/模型计算。清理完成不代表科学实验完成。

## 1. 范围与实际回收

单次artifact元数据库存覆盖3,319,528个文件、3,255,155个目录，不跟随符号链接、不读取大型载荷，盘点约743.926GiB。整个卷约3.6TiB占用不等于这些artifact的占用，本次未扩展到其他项目、模型缓存或整个账户。

| 完成范围 | 移除对象 | 原分配块字节 |
|---|---|---:|
| 项目测试与缓存 | `artifacts/test_tmp`19个旧子目录，加`.mypy_cache`、`.pytest_cache`、scripts/tests下两个工作区`__pycache__`，共23根 | 60,444,672 |
| 四份历史钱包快照 | V13、V14、V16、V17各一份明确的`wallet_before`备份 | 10,643,730,432 |
| 系统盘旧测试夹具 | 16个精确的FinQA CPU/mock/pytest临时目录 | 130,150,400 |
| 系统盘重复输出 | 4份与S71/S72正式文件逐字相同的临时副本 | 30,228,480 |

项目测试/缓存于16:52:41北京时间完成；四账本冷归档于16:55:27完成；系统盘临时清理于17:05:56完成。原`test_tmp`父目录保留，未建立持续通配符或定时清理规则。

| 新备份与操作审计，均存于数据盘 | 实际分配块字节 |
|---|---:|
| 项目测试归档与审计 | 10,665,984 |
| 钱包归档与审计 | 581,894,144 |
| `/tmp`测试归档与审计 | 2,428,928 |
| 合计 | 594,989,056 |

数据盘原件移除量为10,704,175,104字节，扣除以上全部新备份/操作审计后，净回收10,109,186,048字节；系统盘原件移除量为160,378,880字节。上述数值不含此后新增的小型汇总、本文、Git对象及目录元数据差异，因此对外采用约9.41GiB和152.95MiB。

完成后`df -h`显示数据盘可用约136GiB、使用率97%，系统盘可用约149GiB。其他任务同时写盘，整个卷可用空间的变化没有全部归因于本次清理。

## 2. 四份账本采用无损冷存

以下路径均相对于`trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/`：

| 历史快照 | 处理 |
|---|---|
| `v13_material_02/wallet_before_v13_material_purposes.sqlite3` | 内容归档并验证后移除展开副本 |
| `v14_representation_01/wallet_before_v14_residual.sqlite3` | 同上 |
| `v16_six_task_continuation_01/wallet_before_v16.sqlite3` | 同上 |
| `v17_three_task_continuation_01/wallet_before_v17.sqlite3` | 同上 |

四文件均为原登记明确保存的一致性备份，普通单链接、未被Git追踪，未出现WAL/SHM/journal。旧运行的`budget_database`仍指向主`experiment0_01/budget.sqlite3`，该主账本及其现存sidecar完整排除；另外两份账本也没有处理。

快照本身具有历史用途，并未当作无备份垃圾丢弃。旧V13/V14/V16/V17重新登记时会核对原备份路径和SHA，因此未来重登记或历史恢复前，必须先按下文恢复到原路径。当前V72读取链不需要这些快照；不修改旧登记记录、SHA或预算账本内容来绕过缺失。

新归档使用原固定zstd引擎，一个打包进程、两个压缩线程，以较低CPU/I/O优先级执行。保留原可用空间门“源分配量×2＋4GiB”，没有通过先删除原件来凑压缩空间。四成员全部流式解压核验内容，并与各自原登记备份SHA匹配后，才发生任何源unlink。

压缩内容逻辑大小580,754,030字节，实际分配580,755,456字节。611项固定保护锚点与8个邻近非目标文件元数据检查通过；所有源目录、原登记及非目标文件保留。未打开SQLite连接、执行VACUUM或修改数据库格式。

## 3. 测试缓存与临时副本

项目23个目录的归档完整验证17,615个成员后才删除；608项固定科学输入、源码、端点和锁元数据保持不变。目录都是预先审阅的CPU/mock夹具或可重建缓存，未清理`.venv`、正式材料、冻结源码或整个工作树。

系统盘最初审阅17个目录。正式预检时发现`/tmp/pytest-of-zhuxinrui/pytest-1997`已经不存在，检查立即在创建操作目录和删除任何源之前停止。保留原预检源码与审阅证据后，将名单只缩小为仍存在的16个原候选；该已消失目录的45,056字节不计入本次主动回收，也不猜测其删除来源。

缩小后的16目录完整归档并验证5,109个成员后才移除。检查根身份、UID、成员数量、分配量及时间范围，不跟随测试符号链接，不接受特殊文件、外部UID、硬链接或被替换的候选。`pytest-current`若已指向新测试或身份变化便保留；本次没有删除该别名。

随后移除四份已核对逐字相同的临时副本，正式内容保留于对应科学根：

| 已删除临时副本 | 保留的正式内容 |
|---|---|
| `/tmp/v71_existing_mechanism_analysis_20261024.json` | S71 `existing_mechanism_analysis/record.json` |
| `/tmp/v72_existing_analysis_20261025.json` | S72 `existing_analysis/record.json` |
| `/tmp/v72_static_audit_20261025.json` | S72 `static_supervision_audit/record.json` |
| `/tmp/v72_static_audit_before_vendor_binding.py` | S72 `existing_analysis/producer.py` |

其中S71为`v71_fixed_distribution_control_01/execution_revision_01`，S72为`v72_low_lr_continuation_01`。临时副本与正式副本SHA在移除前匹配；历史记录里的原生产路径不改写，正式来源和生产源码内容继续可用。系统盘清理的606项固定保护锚点检查通过。

## 4. 恢复文件与命令

全部新备份保存在本机，不提交Git；Git中的清单和摘要不包含被移除内容，不能替代压缩包。

| 内容包 | 位置：`trusted_data_synthesis/artifacts/`下 | SHA256 |
|---|---|---|
| 项目测试夹具 | `local_test_archive_20261025_01/test_fixtures.tar.gz` | `bd388421b9f30f1e86083a2759059055aecaaf731e2511d6922526a12bf5bd05` |
| 系统盘测试夹具 | `local_test_archive_20261025_tmp_01/test_fixtures.tar.gz` | `bc5d9dcb1f69c11a7a65c62e8e34d149c984df55aed866858b4d2386e167600e` |
| 四份钱包快照 | `cold_archive_20261025_wallet_snapshots_01/wallet_before_snapshots.tar.zst` | `8d4a2438c79ae34f7f1888430f131d98ce07a984ae8ea1808f762ff792d9c965` |

两个测试归档目录各有`member_manifest.json.gz`。项目测试清单SHA为`610fd52604f7eeec34b606e8b84a60fe54cd6b425649f8ed4e6d925c24d74433`；系统盘清单SHA为`e5cb1a457544fb27b2f2c7070c410933387e783f754ace97089a6ab62a005318`。归档迁移后位置另行封存，原完成记录不回写。

钱包恢复使用已冻结入口，目标目录必须事先存在、为空且没有符号链接重定向。例如从仓库根运行：

```bash
mkdir trusted_data_synthesis/artifacts/wallet_restore_review_20261025
python -B trusted_data_synthesis/artifacts/storage_cleanup_20261025_wallet_snapshots_01/archive.py restore \
  --group wallet_before_snapshots \
  --destination /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/wallet_restore_review_20261025
```

恢复器先核对原归档及成员清单，恢复到隔离目录并再次核验；人工确认后，按归档内仓库相对路径放回原位置，避免覆盖后来创建的同名内容。旧注册会继续检查原SHA。恢复保留内容和基本文件属性，不承诺原inode、ctime、ACL或扩展属性。

测试归档也先在独立空目录中解压并对照成员清单。项目测试包路径相对于仓库根，系统盘测试包路径相对于`/tmp`；部分测试符号链接指向旧绝对路径，应检查后再放回，不覆盖新测试目录。不要直接把带绝对链接的隔离解压目录视作已经完整恢复到原环境。

## 5. 保护与核验边界

没有删除训练/模型Tensor、当前及历史反馈、原始回答、评分、协议、失败记录、工作树、GPU租约或已有冷归档。V35继承缓存不能仅凭字节相同进行合并，既有约145GiB冷归档也可能是已移除原件的唯一内容，本次均保留。

占用检查覆盖当前账户可读的FD、mmap、工作目录、显式路径和选定路径类环境变量；资格审阅也查看了其他可读进程。权限受限或其他账户不可见表不构成全机零占用保证。候选身份变化或占用命中就保留，不停止科学进程配合清理。

三个新包装器共22项不同的必要合成用例通过，覆盖精确范围、源变化保留、链接/硬链接拒绝、真实小型备份验证后删除、恢复和一次性执行。实际归档又逐成员完成内容核验；没有重读模型大载荷或重跑科学实验来“证明可恢复”。临时范围因一个已不存在目录而缩小，原预检证据保留，没有放宽安全检查。

清理结束时V72仍处第1次controller attempt，最后dev worker为GPU2 PID1665121、birth533694005，身份匹配；科学队列的自然进度没有被要求冻结。保护锚点是固定的不可变对象，运行队列作为动态快照单独记录。

## 6. 审计与收口

| 操作 | 审计目录 | 完成ID |
|---|---|---|
| 项目测试/缓存 | `storage_cleanup_20261025_test_cache_01/` | `579d0e7788c1524ce45b23832d7ff4db0253c645a31621ddde6fb381e0ec1fda` |
| 四钱包冷存 | `storage_cleanup_20261025_wallet_snapshots_01/` | `7b816f3f0283e9247ac2bc73023ad0a682b8cad1b96e8fd5274e4a1a75924cf9` |
| 系统盘测试与重复输出 | `storage_cleanup_20261025_tmp_tests_01/` | `67e8ae3689146220dc0c4f14db4c6a23440be5cf2fd28cc4f668e5bfb9748c24` |

统一摘要见[storage_cleanup_20261025_summary.json](report_data/storage_cleanup_20261025_summary.json)，同时保存于`artifacts/storage_cleanup_20261025_summary_01/record.json`，ID为`6b679b1b545aebc5bd39ab2a9a517b6b8273b17025d6093c7b86ab5f266829fb`。

本次精确计划均已消费，不再次prepare/apply或借旧白名单继续删除其他数据。后续需要内容时使用恢复流程，保持原历史SHA与记录。本地AGENTS继续忽略、不重新提交远端。
