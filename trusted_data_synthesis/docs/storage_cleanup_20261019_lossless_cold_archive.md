# 旧实验载荷无损冷归档

## 范围与恢复合同

用户于2026-10-19要求“进一步清理压缩旧实验产物”。本轮使用独立 `storage_cleanup_20261019_cold_archive_01/` 计划，只把已核对不在当前执行依赖链中的旧载荷转为本机无损冷归档。所有压缩包完成逐成员内容校验并持久保存后，才移除展开原件；保留目录和未选中文件。它不延续本日上午的不可恢复中间状态删除，也不重启任何旧清理计划。

候选为8,932个文件，原分配块占用174,315,012,096字节。这个数字是待转换原件的体积，不是预计净释放量；压缩后的内容副本仍占磁盘。主要部分是真实类梯度，不是可重新制造的缓存垃圾。

| 分组 | 文件数 | 原分配字节 |
| --- | ---: | ---: |
| 两份历史钱包快照 | 2 | 4,937,846,784 |
| 旧性能profiling轨迹 | 1 | 3,645,366,272 |
| 旧seed389第894步outer反馈封存载荷 | 1 | 157,585,408 |
| seed137旧非596任务梯度 | 1,488 | 27,595,702,272 |
| seed251旧非596任务梯度 | 2,976 | 55,191,404,544 |
| seed389旧非596任务梯度 | 4,464 | 82,787,106,816 |

精确文件范围和各context计数由[scope.json](../artifacts/storage_cleanup_20261019_cold_archive_01/scope.json)登记，执行计划再保存逐文件身份。没有按目录整体删除或自动扫描扩展下一批。

两份数据库只限 `v15_prefix_completion_01/wallet_before_v15_mapping.sqlite3` 和 `v12_rereview_02/wallet_before_v12_request_transfer.sqlite3`。它们是历史钱包一致性备份，不是模拟数据库；复制原始字节，不打开SQLite、不VACUUM、不checkpoint、不合并或丢弃sidecar。若出现新sidecar则停止。

旧性能载荷只限V25 `replay_performance_01/micro_R0/profile/trace.json`。旧反馈载荷只限 `production_resume_01/recovery_04/contexts/seed389/c_only/step0894_outer/feedback_resume_view/dc03ecaa04ac96ea215e281ab5de848ddbf93ebb202fd32c541d637824c6c972/cohort_seal/record.json`。相关profile记录、context、协议、失败、收口和接受记录均保留原样；归档不改变旧实验事实。

8,928份梯度只来自清单列出的13个历史生产context，形状严格为 `contexts/seed{137,251,389}/{c_only,full}/step{0298,0894,1192}_outer/task_cache/taskNNNN/gradient.pt`。11个目录各有744个完整任务；seed251 C-only1192的父186题和新558题分处两个恢复目录，合计仍是一套744任务，不能当作两套已完成计算。每任务 `record.json`、task_plan及context等留在原位，不修改科学SHA或替换为“未生成”。

## 当前实验的保留边界

整个V54温度实验及全部恢复、V59/V60/V61控制守护目录均排除。整个旧B `training_replication/` 也保留，包含三个596父点、C1的597至894完整窗口、745/894评价模型、其他epoch终点、最终模型及旧T1反馈。所有旧 `step0596_outer` context及继承缓存不动；当前seed389唯一旧类梯度引用位于 `production_resume_01/recovery_02/contexts/seed389/c_only/step0596_outer/task_cache/`。

当前真实训练仍会通过 `V25.checked_launch → V18.load_training_pool` 读取早期材料链。V10原episode与注册、V12第二版pairs/reviews、V13权威记录、V14监督与编码、V15 prefix材料和任务计划、V16/V17来源记录、V18 material及训练/评价registration都继续保留，不能因为版本旧就归档移走。所有冻结源码、基座模型、工作树、Git、虚拟环境和锁文件也不处理。

定向代码与封存引用检查表明：两份before钱包不属于当前活钱包读取路径；当前V54不进行旧V32 profiling；C1止于894_step而不执行894_outer；当前类梯度旧引用只指向seed389的596点；V59至V61的断点审计限定当前科学根的job/attempt。因此所选旧0298/0894/1192梯度及单个894封存载荷可冷存。该结论针对已核对的当前执行链，不保证任意未来动态构造路径都不需要这些内容。

此前七份冷归档、两轮本地测试归档、publication gzip及全部恢复清单和代码均保留。它们是已移除原件的内容来源，不能当作过期缓存再删除。

## 压缩与必要校验

新包装复用已固定SHA的20261010冷归档引擎，使用新OUTPUT、BACKUP与白名单，不修改旧实现或结果。最多3个并行CPU packer，每个Zstandard为2线程、level6；执行使用较低CPU与I/O调度优先级，不占GPU、不调用API、不暂停或信号实验。暂存容量仍按原件分配量的两倍再加4GiB检查，不依靠乐观压缩率放宽。

只接受规范化路径、普通文件、单硬链接、同设备、未被Git跟踪的精确对象。计划绑定源身份、范围及实现；打包读取时同时计算每成员SHA256，随后完整流式解压一次，核对成员路径、类型、数量、顺序、大小和内容摘要。归档、逐成员清单和verified凭证全部落盘后，再核对源身份、保护锚点及同账户可读进程占用，最后逐文件移除。压缩包实际分配占用不小于该组源占用时不移除该组源文件。

同账户FD、mmap、显式路径和工作目录检查属于当时快照；其他账户、已识别受限系统进程以及未来动态打开不在全面保证范围内。变化或占用检查失败就保留原件，不绕过保护门重试。不要求正在运行的科学队列内容保持不变，只保护不可变来源与锁身份。

此前只对一份旧Full389 step298 task0528梯度做过无落盘试压：10,160,479字节压至9,490,538字节，约节省6.6%。它用于判断收益，不是154GiB整体压缩率的实测；其他任务张量大小和分布不同。全部内容仍须正式打包与逐成员核验，不能用试样替代。

新包装的9项不同CPU/mock用例通过，覆盖精确钱包/trace/cohort白名单、非596梯度尾部、范围与字节总量、源文件变化和数据库sidecar、完整任务元数据缓存、正收益门、context消费者占用及恢复绑定。一次真实metadata预检确认8,932个目标、174,315,012,096分配字节、174,300,868,702逻辑字节和17个窄scope目录，未读取Tensor载荷；这不替代正式计划中的占用检查及后续内容校验。

## 本机归档与显式恢复

内容归档存放在 `trusted_data_synthesis/artifacts/cold_archive_20261019_01/`，分为 `legacy_wallets`、`profiling_trace`、`old_feedback_cohort` 和三个 `old_class_seed137/251/389` 的 `.tar.zst`。内容包只在本机保留，不提交Git；Git中的计划、清单及SHA不能单独重建这些字节。

当前loader没有压缩文件透明回退。以后需要旧实验逐张量审计或历史性能追溯时，必须先显式恢复所需分组，再按原科学记录核验后放回原路径。不要裸启动旧controller，也不要将冷存期间原路径缺失解释为历史计算从未发生。

恢复入口只允许既有、规范化且为空的隔离目录，拒绝覆盖已有文件：

```bash
python3 -B trusted_data_synthesis/artifacts/storage_cleanup_20261019_cold_archive_01/archive.py restore \
  --group old_class_seed137 \
  --destination /absolute/path/to/an/existing/empty/restore-directory
```

恢复内容保留仓库相对路径，恢复基本权限及mtime，但不承诺原inode、ctime、ACL或扩展属性。原GPU租约和科学owner锁因此绝不归档。正式校验要求一次全量流式解压；本轮不额外重复全量落盘恢复演练。

## 实际执行结果

本节在一次性计划及正式归档完成后填写实际文件数、包大小、净释放和运行状态；当前仍为准备阶段，不把候选体积或试样压缩率当作已释放空间。
