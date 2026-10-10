# 剩余历史载荷与本地缓存冷归档

用户要求“继续审计数据构成，清理或者压缩历史数据”。本次采用独立的第二轮冷归档计划，保留历史内容的可恢复压缩副本，核验全部成员后才移除展开原件；没有重复执行上一轮计划，没有清理模型、当前实验状态或Git工作树。

**本轮于2026年10月10日北京时间22:52:39完成，状态为 `COMPLETE`。** 共归档并移除122,129个展开文件，原实际分配8,773,083,136字节。四份新归档实际分配357,056,512字节，完成结果生成前审计材料分配10,633,216字节；按该口径净回收 **8,405,393,408字节，7.828133 GiB**。45,302个范围内非目标文件的stat元数据摘要及显式保护对象均未变。

V37在本轮计划登记之前已经停止。其失败时间、原因记录与本次存储操作的先后关系单独列于下文；存储归档完成不表示V37恢复或数值验收成功。

## 归档前的数据构成

以下是本轮归档前的实际分配快照，GiB按1024³字节计算。子目录项不能与其父目录重复相加。

| 路径 | 实际分配字节 | GiB | 处理边界 |
| --- | ---: | ---: | --- |
| `trusted_data_synthesis/artifacts` | 440,157,814,784 | 409.928909 | 仅处理本轮固定白名单 |
| 其中 `finance_research_20260928` | 407,631,781,888 | 379.636681 | 占artifacts约92.61%；当前与原15模型基线保留 |
| `.codex-worktrees` | 20,046,622,720 | 18.669872 | 所有实际工作树保留 |
| `.git` | 11,143,888,896 | 10.378555 | Git对象及注册元数据保留 |
| 其中 `.git/worktrees` | 7,419,990,016 | 6.910404 | 不因索引较大而删除有效工作树登记 |
| 实际环境 `trusted_data_synthesis/.venv` | 7,897,726,976 | 7.355331 | 完整保留 |

Git只读检查共见70个工作树登记，65个实际路径存在，5个路径缺失。`git worktree prune --dry-run --verbose --expire now`仅列出后五个登记，实际合计3,715,072字节，约3.54 MiB：`trusted_synthesis_pro_flash`、`v26_60_worktree`、`Data-Synthesis-v26.110`、`Data-Synthesis-v26.112`、`Data-Synthesis-v26.141`。五个登记没有锁，各自索引与登记分支的只读比较一致。

本轮没有执行prune、worktree remove或Git GC，五个失效登记也保留。约156 MB的大索引主要属于仍存在的工作树，不能把整个 `.git/worktrees` 当作可再建缓存。包含原始反馈的 `/tmp/data-synthesis-fixed-kernel-parallel-tail-20260914` 等实际工作树继续保留。

## 固定归档范围

下表“原分配字节”按源文件 `st_blocks × 512` 求和；压缩包列为文件逻辑大小，与四包合计实际分配357,056,512字节是不同指标。

| 分组 | 原文件数 | 原分配字节 | 压缩包逻辑字节 |
| --- | ---: | ---: | ---: |
| `retired_review_inputs` | 14,438 | 5,064,216,576 | 120,910,399 |
| `legacy_qa_databases_and_intents` | 89,152 | 2,186,137,600 | 165,677,354 |
| `vtdo_small_text` | 14,904 | 1,253,564,416 | 29,436,038 |
| `rebuildable_caches` | 3,635 | 269,164,544 | 41,023,606 |
| 合计 | 122,129 | 8,773,083,136 | 357,047,397 |

### 已退出主线的审核输入

路径相对于 `artifacts/finance_research_20260928/finqa_v6_01/`，只处理下列四个目录内的未跟踪JSON：

| 目录 | 文件数 | 原分配字节 |
| --- | ---: | ---: |
| `review_revision_01/inputs` | 1,000 | 489,566,208 |
| `review_revision_02/inputs` | 1,000 | 603,983,872 |
| `review_revision_03/slot_inputs` | 1,000 | 2,109,407,232 |
| `v12_rereview_01/requests` | 11,438 | 1,861,259,264 |

R1/R2各保留12条实际审核记录，历史状态为容量或格式门阻断；R3由技术门阻断，没有进入训练。V12第一版在派发前被替代，模型调用和钱包登记均为零，实际后续权威使用V12第二版。13份关键登记的定向核查未发现直接依赖这些候选路径；这不是对任意未来动态引用的全面保证。

本次保留registration、status、gate、实际reviews/jobs、definition、preparation及superseded记录。归档对象是历史输入载荷，不改写其当时失败或未派发状态。

### 早期QA数据库与旧预算意向

四个数据库路径相对于 `artifacts/`：

- `qa_vnext_task_build/runtime_20260911/qa_build.sqlite3`；
- `qa_vnext_task_build/runtime_20260911/native_fact_qa.sqlite3`；
- `qa_vnext_surface_build/runtime_20260912/native_fact_qa.sqlite3`；
- `qa_vnext_surface_build/runtime_20260912/rewrite_budget.sqlite3`。

它们实际分配合计1,820,987,392字节，是真实历史恢复数据库，不是测试模拟数据。执行要求没有新出现的同名数据库sidecar；归档仅复制原始字节，没有打开SQLite、VACUUM、checkpoint或重写数据库。

同组还包含 `qa_vnext_fixed_kernel_value/delayed_C_B_confirmation_cache_20260922/budget/intents/` 下89,148个未跟踪JSON。其逻辑大小合计22,303,533字节，实际分配365,150,208字节；小文件分配开销解释了两者差异，不能把实际分配量解释为同等大小的科学内容。

主分支及已检查的V18、V25、V37链未发现对这些候选产物的直接引用。九个历史QA固定Student、跨市场校准、epoch保存点和最后反馈状态均保留。旧工作流若需要这些数据库或意向文件，须先恢复，不能直接把原路径缺失解释为原实验从未生成过记录。

### 剩余VTDO小型文本

只处理 `artifacts/vtdo_experiment/` 中未被Git跟踪、普通单硬链接的 `.json`、`.jsonl`，要求逻辑大小小于1 MiB；相对路径任意位置匹配 `report|manifest|index`（不区分大小写）的文件全部排除，整个 `finance_phase1_mvp_v1/beneficiary_adapter/` 也排除。

本组包括14,324个JSON和580个JSONL。其内容包括旧原始响应、状态记录和其他历史载荷；不是经内容去重证明可丢弃的副本。44,342个Git跟踪文件、585个未跟踪报告/manifest/index及adapter继续留在原位。上轮已经归档的大文本和此前已删除的张量不重复计量。

### 工具与有源码的字节码缓存

仅包括 `raw_financial_data_lake/` 与 `trusted_data_synthesis/` 内现存 `.mypy_cache`、`.pytest_cache`、`.ruff_cache`，以及数据湖目录和 `trusted_data_synthesis/{src,scripts,tests}/` 下有对应本地源码的 `__pycache__/*.pyc`。没有进入 `.venv` 或工作树缓存。

数据湖部分441项、21,254,144字节；trusted部分3,194项、247,910,400字节。全部未被Git跟踪，源码保持原位并纳入保护。12个找不到当前对应源码的旧字节码共499,712字节，继续保留，不将其描述为可即时再生。虽然本组属于可再建缓存，本轮仍先保留可校验的内容归档再移除展开文件。

数据湖原剩余约83.43 MiB不全是缓存。89个Git跟踪的配置及benchmark文件已占61,210,624字节，连同源码、文档及安装元数据继续保留。

## 实现绑定与实际核验

新入口为 [第二轮archive.py](../artifacts/storage_cleanup_20261010_cold_archive_02/archive.py)，复用上一轮已封存引擎，其SHA256固定为 `ee61e44d33c7c7f9fbe51d2d5a4239d953eb73a79f55d5e2ab552a551493318e`。新包装器把计划及归档输出分别绑定到独立的 `_02` 目录，并将引擎的实现文件绑定指向新包装器；旧计划没有重启。计划另绑定辅助检查代码、Zstandard程序和本轮范围说明。

准备阶段第一次选择检查发现，标准 `source_from_cache()`不能解析带点号pytest版本的字节码名，因而在固定缓存计数门处拒绝，尚未发布计划或移除源文件。随后新增严格匹配 `module.cpython-NNN-pytest-X.Y.Z.pyc` 的分支，仍要求对应源码存在、路径规范化且位于仓库内。缓存固定数量和字节没有缩减，无源字节码仍排除；修正后的包装器才进入正式计划。该准备期修订记录在 [preparation_observation_01.json](../artifacts/storage_cleanup_20261010_cold_archive_02/preparation_observation_01.json)。

四组归档共享最多3个并行压缩任务，每个Zstandard进程使用2线程、level6。写入tar时逐成员计算SHA256，之后重新流式解压整个归档，核对成员路径、类型、大小、数量、顺序及内容摘要。归档、逐成员压缩清单、校验凭证及目录项先持久化；全部四组完成后才再次检查目标身份、Git跟踪、保留对象和进程占用，再逐文件unlink。不删除任何源目录，不放宽变化门或自动重试。

最终45,302个范围内非目标文件的stat摘要及显式保护文件均未变。最终占用检查覆盖33个可读同账户进程，未命中目标；四个已识别systemd/PAM/sshd进程的受限部分及其他账户不属于全面检查范围。本存储任务没有调用GPU/API、向实验进程发信号或修改实验代码及数学。

## V37停止与本轮存储操作时间线

所有时间均为2026年10月10日北京时间，原记录使用UTC。

| 时间 | 已记录事件 |
| --- | --- |
| 22:47:48 | V37的 `distribution` worker报错 `GPU is not fully idle or UUID changed` |
| 22:48:26 | V37控制器以 `STOPPED_FAILURE_NO_RETRY` 停止 |
| 22:49:08 | 本轮冷归档计划登记 |
| 22:50:33 | 本轮归档执行意向登记，此时已观察到V37停止 |
| 22:51:57 | 四组全部备份验证通过；源文件移除发生在此后复核通过之后 |
| 22:52:39 | 本轮存储操作 `COMPLETE` |

V37首点仍为seed137、C-only、step1192，已提交outer列表为298、596、894；本次停止观察记录中的新optimizer更新和新outer更新均为零，`pilot_accepted=false`，没有活跃child。错误文本只支持空闲/UUID联合门失败，不能据此选择性断言究竟是非空闲还是UUID改变。

上述时间线表明该worker错误早于本轮计划和源文件移除；它不构成对所有潜在资源影响的因果证明，也不能把存储完成写成V37成功。本存储任务没有自动重启实验，没有重写原停止记录。用户随后另行授权的修复与受控恢复属于独立工作，正在进行中；本文不宣称已恢复成功或通过数值验收。完整只读观察见 [experiment_stop_observation.json](../artifacts/storage_cleanup_20261010_cold_archive_02/experiment_stop_observation.json)。

## 本机归档与恢复边界

四份内容归档位于 `trusted_data_synthesis/artifacts/cold_archive_20261010_02/`，仅保存在本机，不作为Git内容提交：

| 文件 | SHA256 |
| --- | --- |
| `retired_review_inputs.tar.zst` | `1547b9e96e8ed575a8de75a541201457fe15b5a7dbcd9d2076e249b0a0093a6d` |
| `legacy_qa_databases_and_intents.tar.zst` | `11c9771ab127d75023407ebe71574e02ae0edf49ab1d56edecc8934b9c93917f` |
| `vtdo_small_text.tar.zst` | `7ceb2d0b43a03b2eab29d4ec6773362730f2606d0fd73936703f1b304df405a9` |
| `rebuildable_caches.tar.zst` | `c638995047f8803e23909c5fecc1b71296f5df14c3bfd261929d44a6fef3aaf3` |

审计清单只含路径、元数据及内容摘要，不是内容备份。若本机归档丢失，不能仅凭Git中的清单还原这些未跟踪原件。恢复入口保留原文件内容、基本权限与mtime，不承诺原inode、ctime、ACL、扩展属性或数据库在全局瞬时意义上的事务状态。

从仓库根目录调用本轮包装器，`--group`选上述四个文件名去掉`.tar.zst`后的名称；目标须为用户指定、已存在且为空的规范化绝对路径：

```bash
python3 -B trusted_data_synthesis/artifacts/storage_cleanup_20261010_cold_archive_02/archive.py restore \
  --group vtdo_small_text \
  --destination /absolute/path/to/an/existing/empty/restore-directory
```

恢复依赖同一hash固定的上一轮引擎及其辅助实现，须保留这些代码和本轮清单。入口核对归档、清单及逐成员内容，只向隔离空目录写入，拒绝覆盖现有文件；恢复目录内保留仓库相对路径。人工核对后才可将所需文件恢复到原位置，避免覆盖后续新数据。

本轮四组均完成完整流式解压和逐成员内容校验，**没有再做一次全量落盘恢复演练**。上一轮曾对其数据库组实际恢复，不把那次结果当作本轮四组已经逐一做过落盘演练。

## 空间结果与证据

本轮净回收按以下固定文件计量计算：

```text
8,773,083,136 原文件分配字节
- 357,056,512 新归档分配字节
-  10,633,216 结果生成前审计分配字节
= 8,405,393,408 字节 = 7.828132629 GiB
```

后续新增少量结果凭证、说明及Git对象未包含在该精确值中。沿用此前198.540565 GiB的累计口径，本轮后累计约 **206.368698 GiB**；不重复加入更早清理、上轮已移除原件或原有压缩副本。

执行前后卷空闲分别为596,594,589,696和604,952,305,664字节。之后最后一次空间快照为空闲604,919,234,560字节，约563.374939 GiB，使用率85%。卷空闲是动态快照，其他进程仍可读写；不将其变化等同于白名单逐文件净回收，也不据此推断实验进度。

主要证据位于 [storage_cleanup_20261010_cold_archive_02](../artifacts/storage_cleanup_20261010_cold_archive_02/)：

- [scope_and_dependencies.json](../artifacts/storage_cleanup_20261010_cold_archive_02/scope_and_dependencies.json)：四组精确范围、来源判断及保留边界。
- [plan.json](../artifacts/storage_cleanup_20261010_cold_archive_02/plan.json)：独立计划，ID `911e74f822b3479e18e3a5b2a0f3d28118d135e3d48b32a248a835fa714381cb`；源文件身份另存于压缩清单。
- [backup_verified.json](../artifacts/storage_cleanup_20261010_cold_archive_02/backup_verified.json)：全部备份先于源移除验证通过，ID `bca941f4cf5e9e86157941af0c4b516d02a1877094910afd5b692948856badb9`。
- [result.json](../artifacts/storage_cleanup_20261010_cold_archive_02/result.json)：实际移除量、归档量、保留检查与空间快照，ID `377a6f17563f96b1160e4b7c0ab40383a52ce5a7239d3c3b1ed17d668aa683ad`。
- [experiment_stop_observation.json](../artifacts/storage_cleanup_20261010_cold_archive_02/experiment_stop_observation.json)：V37只读停止观察及时间线，ID `72f7bd9cd3e5010056060a5eac74c1f7fabadc7a75ad81832eddcc1038355746`。

本次是可恢复存储变换，不产生新的科学实验结果、准确率或吞吐结论，也不改写历史成功、失败或暂停记录。
