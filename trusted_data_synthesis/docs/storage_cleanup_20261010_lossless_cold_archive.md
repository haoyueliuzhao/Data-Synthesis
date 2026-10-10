# 闲置历史数据无损冷归档

用户要求继续释放空间，并允许对目前不用的数据作无损压缩。本次只处理已定向核对无当前输入依赖、未被Git跟踪的历史载荷；全部内容须有可验证的压缩副本后才移除展开原件。原15任务主实验、当前V37及其来源链、模型、Git跟踪材料和小型审计记录继续留在原位。

**已于2026年10月10日北京时间22:11:32完成，状态为 `COMPLETE`。** 全部51,336个展开原件已移除，内容由三个新归档或原有四份gzip保留。扣除新归档及当时的审计文件后，净释放25,973,354,496字节，约24.19 GiB。随后数据库组的实际隔离恢复与落盘回读也通过，临时恢复副本已移除。

## 固定范围

| 分组 | 文件数 | 原分配字节 | 处理方式 |
| --- | ---: | ---: | --- |
| 旧VTDO大文本 | 978 | 14,666,502,144 | 新建可恢复Zstandard压缩tar |
| 旧钱包及两组旧任务载荷 | 50,342 | 8,148,070,400 | 新建可恢复Zstandard压缩tar |
| 三组早期QA闲置数据库及sidecar | 12 | 2,875,015,168 | 原字节归档，不打开或重写数据库 |
| 已有publication的QA大JSON原件 | 4 | 1,107,484,672 | 复用已有gzip，不重复压缩 |
| 合计 | 51,336 | 26,797,072,384 | 原件约24.956718 GiB，非预计净释放量 |

新归档的实际逻辑大小分别为：VTDO 440,124,468字节（约419.74 MiB），旧钱包及任务194,568,014字节（约185.55 MiB），QA数据库184,924,838字节（约176.36 MiB）。三份合计分配819,621,888字节，约781.65 MiB。四份旧gzip此前已存在，没有把它们再算作新增空间开销。原文件字节占用不能直接当作净释放量。

VTDO仅选 `artifacts/vtdo_experiment/` 中逻辑大小至少1 MiB的普通单硬链接 `.json`、`.jsonl`，排除Git跟踪文件及basename含report的文件。唯一beneficiary adapter保留；小于1 MiB的索引、manifest和其他文件留在原位。部分大型freeze、audit或manifest载荷也在归档中，不能将其称为垃圾；旧脚本读这些文件前须恢复原路径。

旧钱包只包括 `finance_research_20260928/finqa_v6_01/v10_wallet_prelaunch_AalG7W/` 与 `v10_funding_backup_2mcs6281/` 内的 `wallet.sqlite3` 及现存wal/shm，不触碰正式 `experiment0_01` 钱包。前者receipt留在原位，两个快照不被当作重复数据库；不做VACUUM、dump或内容迁移。

两组旧任务分别为 `finance_research_20260928/audit_followup_01/jobs/` 和 `reference_revision_01/jobs/`，仅处理各16个固定任务的 `generation/episodes/`、`generation/events/`。原run、seal、attempts、receipt、锁、G/G2均保留。两批各480条episode的已登记摘要无交集，不能视为重复实验；压缩只是保留完整字节的存储变换。

QA数据库位于 `qa_vnext_readiness_revision`、`qa_vnext_eval_readiness`、`qa_vnext_catalog_bridge` 各自的 `runtime_20260912/`，共10个SQLite及2个现存sidecar。全部纳入同组归档，以保持原文件集合，不在归档中隐式checkpoint或合并wal。

四份现有gzip对应eval与catalog两组的 `panels/confirm/parents/qa_candidates/{0000,0001}.json`。核对现有publication记录ID、原科学manifest及成员绑定，原件内容SHA256和gzip解压后SHA256均须等于原登记。gzip及索引是已有Git跟踪文件，留在原位；旧记录中的“当时没有删除原件”仍是原发布时间的事实，不改写旧科学记录。

## 保留边界

本次不会以“早于10月”判断数据无用。原15模型基线为seed11、29、47×五臂，保留训练与dev、后继test、机制、原始反馈及V10至V18来源链，当前V25/V37不变。九个历史QA固定Student、跨市场校准、现存epoch保存点和反馈证据也不在本次范围。

三组QA中427,310个已跟踪文件、原分配10,439,696,384字节，全部保持原位；其中readiness的422,178个JSON不是本次可移动冷数据。VTDO中44,342个已跟踪文件也排除，不通过删除Git工作区文件或改变sparse-checkout方式腾空间。源目录全部保留，不删除整个实验树。

## 完整性与执行规则

固定计划绑定实现、辅助检查代码、Zstandard程序及完整源文件元数据。目标拒绝路径重定向、特殊文件、多硬链接和跨设备项；执行前及删除前核对Git、文件身份、保护对象及本账户可读进程占用。四个已识别systemd/PAM/sshd进程的受限部分及其他账户不属于全面审计范围。

三组新归档最多同时3个CPU压缩进程，每个Zstandard使用2线程、level6；不占GPU、不调用API、不对实验进程发信号。写入tar时逐文件计算SHA256，压缩完成后重新流式解压全部成员，核对路径、类型、大小、数量、顺序及内容SHA256。归档文件、清单、校验凭证和目录项先持久化；四份既有gzip也在核验后同步落盘。

只有全部新归档与既有gzip均通过，并重新核对源文件和保留对象，才逐文件unlink。没有直接清除目录的步骤。源文件变化或保护门失败时保留源副本，不自动放宽门槛、重写科学manifest或发起新科学实验。

实际执行后，60,254个非目标范围内文件的元数据摘要和显式保护对象均未变。最终进程检查覆盖31个可读同账户进程，没有目标占用命中。V37队列仍为 `RUNNING`，控制器PID1662074/birth404084608和回放worker PID1868092/birth404873110身份匹配；这只是清理完成时的运行快照，不将其表述为原B或首点数值验收已经完成。

## 本地归档与恢复

新内容归档统一位于 `trusted_data_synthesis/artifacts/cold_archive_20261010_01/`：

- `vtdo_text.tar.zst`：978个旧VTDO文本文件。
- `finance_payloads.tar.zst`：旧钱包和两组旧任务的50,342个载荷文件。
- `qa_databases.tar.zst`：12个闲置数据库及sidecar文件。

这些内容归档仅保存在本机，不提交Git。审计目录 `storage_cleanup_20261010_cold_archive_01/` 保存计划、摘要、逐文件元数据与内容摘要清单，但不含原始数据内容。Git中的这些证据不能单独重建内容；删除本机冷归档会丢失该恢复来源。

三个归档SHA256分别为：

| 归档 | SHA256 |
| --- | --- |
| `vtdo_text.tar.zst` | `7d63637c4771d97355f156ef8440b8e4c1b7827918b0735763153808d6f6d8c8` |
| `finance_payloads.tar.zst` | `ef600cedf418ccb5cd9b9ddbdf4990d3a22704caa3d0023fe50fe6b4b5c438ca` |
| `qa_databases.tar.zst` | `54f0c81743be3289a68ad1634af5348d4eaf2fef4ebf99a26c4e00deb826ecf9` |

归档保留原始文件内容，隔离恢复入口也恢复基本权限及mtime；不承诺恢复inode、ctime、ACL、扩展属性或全局瞬时数据库事务状态。旧工作流的路径在冷存期间不可直接读取，使用前需恢复所需文件，再按原科学manifest核验。

对一组新归档，可先创建独立空目录，再执行以下恢复入口，`--group` 可选上述三个文件名前缀：

```bash
python3 -B trusted_data_synthesis/artifacts/storage_cleanup_20261010_cold_archive_01/archive.py restore \
  --group qa_databases \
  --destination /absolute/path/to/an/existing/empty/restore-directory
```

该入口核对归档与清单摘要，只向空的规范化目录写入，逐成员核验内容，拒绝覆盖已有文件。恢复目录内保留仓库相对路径；审核之后再把所需文件放回原位置，不覆盖后来产生的新文件。恢复失败时应检查隔离目录中的部分输出，不把部分写入当成完整恢复。

四份已有gzip继续使用 `package_qa_vnext_catalog_bridge.py` 的 `restore(root, artifact=...)` 接口，分别指定catalog或eval的真实artifact。命令行默认仅catalog，不应误以为一次CLI调用会恢复两组；该入口会核验gzip和科学manifest，并拒绝覆盖不一致的现有文件。

本次实际恢复检查只选最小的 `qa_databases` 组：在Git忽略的 `artifacts/test_tmp/` 下通过 `mktemp -d` 创建独立目录，完整恢复12个文件，不打开SQLite；再回读全部文件，验证内容SHA256、基本权限和纳秒mtime。全部通过后，仅删除该精确临时目录，保留冷归档。其余两个新归档均已完整流式解压并逐成员核验，但没有额外生成全量落盘恢复副本；不把内容校验夸大为三组均做过落盘恢复演练。

## 审计证据

操作材料位于 [storage_cleanup_20261010_cold_archive_01](../artifacts/storage_cleanup_20261010_cold_archive_01/)。计划ID为 `82bca036ffb5b8c240e75e8e0b081737907b9decf6f3a7eb1ff8f4445e1b61a4`，完成结果ID为 `aae772dd0b2991c5c70c7dde430c29d34f221421b0e03d87bc5a020256ab13e5`，隔离恢复检查ID为 `97845a5340ca5beaf97376e7103796750a11cb9862d1fd804d91751bf2b1661a`。压缩的逐成员清单仅含文件路径、元数据和摘要，可作为审计提交；原始内容tar.zst不提交。

本次净释放量已扣除新归档819,621,888字节及完成结果生成前的审计文件4,096,000字节，后续少量恢复凭证、说明和Git对象未计入该精确值。清理执行前后卷空闲分别为572,362,813,440和598,262,140,928字节；并行实验仍在写入，不能把动态卷差值等同于本次逐文件净回收。

恢复临时副本移除后，一次空间快照为空闲598,197,387,264字节，约557.11 GiB，使用率86%。与此前[数据湖和VTDO](storage_cleanup_20261010_retired_lake_and_vtdo.md)、[旧QA中间状态](storage_cleanup_20261010_qa_intermediate_states.md)清理相加，最近这几轮累计净回收约198.54 GiB；不重复计量更早的测试夹具清理、10月3日至6日清理、已删除文件或现存gzip。
