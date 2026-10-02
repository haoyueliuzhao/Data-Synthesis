# VS Code 文件监听额度耗尽排查（2026-09-30）

> 2026-10-02 至 10-03 复查：新会话再次记录过 ENOSPC，但随后实际监听占用已低于上限，本项目保留范围的 204 个目录全部已有监听。详见文末；下文原始结论及“尚未验证”描述保留其 9 月 30 日的时间范围。

## 结论

本次“无法监视文件更改”警告的直接原因是远端 Linux 当前用户的 inotify watch 配额耗尽。VS Code 递归监听了包含大量实验产物和嵌套工作树的项目目录。日志明确报告 `Inotify limit reached (ENOSPC)`，因此本次错误指向监听额度；不能仅凭 `ENOSPC` 字样解释为磁盘容量不足。

项目根目录原先没有 `.vscode/settings.json`。本次新增 `files.watcherExclude`，排除实验产物、原始数据、虚拟环境、嵌套工作树和 Python 缓存的递归监听。当前窗口尚需重新加载才能确认恢复；没有把配置落盘等同于运行中的告警已经消失。

## 实测证据

采样日期为 2026-09-30，日志时间为服务器本地时间（Asia/Shanghai）。进程与目录在采样期间可能变化，以下为排查时的观测值，不是静态库存或历史峰值。

| 指标 | 观测值 |
| --- | ---: |
| `fs.inotify.max_user_watches` | 1,048,576 |
| `fs.inotify.max_user_instances` | 128 |
| `fs.inotify.max_queued_events` | 16,384 |
| 当前 UID 下可读取的 inotify 实例数 | 11 |
| 当前 UID 下可读取的 watch 项数 | 1,048,562 |
| VS Code `--type=fileWatcher` 进程 PID 4036536 的 watch 项数 | 1,048,322 |

watch 数通过读取当前 UID 下 `/proc/<pid>/fd` 中的 inotify 描述符，再统计相应 `fdinfo` 中的 `inotify wd:` 行得到。这是可见描述符的合计，不是内核提供的原子配额统计；其他进程可能同时增减监听，共享描述符也可能影响合计。因此不能把与上限相差的 14 项视为保证可用的余量。日志中的 `ENOSPC` 与接近上限的实测占用共同确认本次故障。实例数没有接近 128，本次未见实例数耗尽的证据。

错误日志位于 `~/.vscode-server/data/logs/20260927T181602/remoteagent.log`：

- 13:52:29：`File Watcher ('parcel')` 对 `/home/zhuxinrui/datatmp/projects/Data-Synthesis` 报告 `Inotify limit reached (ENOSPC)`。
- 13:55:12：同类错误指向 `/data1/zhuxinrui/projects/Data-Synthesis`。
- 13:59:23：Node.js 文件监听器连 `trusted_data_synthesis/docs/finqa_v15_prefix_and_mapping_execution_20260930.md` 也无法监听，错误为 `System limit for number of file watchers reached`。
- 14:04:32：新增配置后，日志报告无法监听 `.vscode/settings.json` 和 `.vscode`，仍为 `ENOSPC`。

两个项目路径已通过 `os.path.samefile` 确认指向同一个目录，不能将其算作两份独立数据。日志出现两个路径也不足以单独量化重复监听的额外开销。

## 目录规模

使用一次目录树遍历统计，不跟随目录符号链接，不读取实验数据内容，也没有清理任何目录。目录数包含各统计子树的根目录。

| 目录 | 目录数 |
| --- | ---: |
| `trusted_data_synthesis/artifacts/` | 976,510 |
| `.codex-worktrees/` | 219,784 |
| `raw_financial_data_lake/data/` | 20,800 |
| `trusted_data_synthesis/.venv/` | 6,156 |

上述四类目录合计 1,223,250，已超过单用户 1,048,576 的 watch 上限。实际 watch 数取决于排除规则、监听实现和其他窗口，不能与目录数直接画等号。在工作树中，`finqa-v14-representation-20260930` 子树有 165,144 个目录；本次只记录规模，不推断这些目录是否仍有实验用途。

`.gitignore` 已经忽略了若干大目录，但 Git 忽略规则不等于 VS Code 的文件监听排除设置。

## 修复内容及影响

新增项目根目录 `.vscode/settings.json`，配置以下排除项：

- `**/.codex-worktrees/**`
- `**/raw_financial_data_lake/data/**`
- `**/trusted_data_synthesis/artifacts/**`
- `**/.venv/**`
- `**/__pycache__/**`
- `**/.pytest_cache/**`
- `**/.mypy_cache/**`
- `**/.ruff_cache/**`

配置只控制工作区的文件监听，未修改数据、实验协议、API 模型、训练进程、Git 忽略规则或系统 sysctl 参数。源代码、测试、文档和配置目录继续保留监听资格。被排除目录的外部变化可能不再自动反映到资源管理器，应按需刷新；文件仍可打开，编辑器或扩展也可能为显式打开的文件建立单独监听。

嵌套工作树从父项目的递归监听中排除。需要编辑某个工作树时可单独打开该工作树，并为它配置适用的产物排除规则；本次没有向各独立工作树复制设置。

采用项目级排除符合 [VS Code 官方 Linux 排障说明](https://code.visualstudio.com/docs/setup/linux#_visual-studio-code-is-unable-to-watch-for-file-changes-in-this-large-workspace-error-enospc)中先排除大型目录的建议。当前系统上限已经是 1,048,576，本次不套用文档示例的 524,288 数值。

## 必要核验与生效步骤

- JSON 解析通过；对主要排除目录和保留的源码、测试、文档、配置目录做了规则意图核验。
- 按上述排除目录剪枝、不跟随目录符号链接，剩余目录为 681 个。这是目录规模检查，不是 VS Code 实际 watch 数，也不是对 VS Code glob 实现的完整测试；该统计尚包含 `.git`，其默认排除规则可能进一步减少监听。
- 14:05:18 复查时可见 watch 合计仍为 1,048,562，当前监听进程没有释放配额。不能据此声称运行中的 VS Code 已恢复。
- 本次仅修改编辑器配置和排查说明，没有运行业务测试、调用模型 API 或启动 GPU 任务。

在打开本项目的 VS Code 窗口中运行命令面板的 `Developer: Reload Window`（开发人员：重新加载窗口）。如果同时通过两个路径打开了同一项目，各窗口都需要加载新配置；持有旧监听的窗口也需要重载或关闭。重载会重启该窗口的扩展宿主，应在当前交互任务结束后操作。本次没有主动重启窗口或杀死其进程。

重载后应检查是否仍有新时间戳的 `Inotify limit reached` / `ENOSPC`，并观察文件变化是否恢复自动刷新；历史日志里的旧错误不会自动删除。GUI 重载及重载后的实际占用下降尚未验证。


## 2026-10-02 至 10-03 再次告警复查

### 新错误与当前状态

用户再次报告 VS Code 的“无法监视文件更改。请按照说明链接来解决此问题”警告。最新服务端日志为 `~/.vscode-server/data/logs/20261002T095833/remoteagent.log`，其中第 88 行记录：

```text
2026-10-02 23:53:22.710 [error] [File Watcher ('parcel')] Inotify limit reached (ENOSPC) (path: /home/zhuxinrui/datatmp/projects/Data-Synthesis)
```

这是本次会话的新错误，不能用 9 月 30 日的旧日志替代解释。相关窗口在 23:52:31 左右建立连接；本次 `/proc` 采样发生在错误之后，没有采到报错瞬间的 watch 峰值。以下为复查观测值，不能回填为报错瞬间的状态。

| 指标 | 复查值 |
| --- | ---: |
| `fs.inotify.max_user_watches` | 1,048,576 |
| `fs.inotify.max_user_instances` | 128 |
| `fs.inotify.max_queued_events` | 16,384 |
| 当前 UID 可读取的 inotify watch 合计 | 162,533 |
| 当前 UID 可读取的 inotify 实例数 | 12 |
| 本项目 fileWatcher PID 4165109 的 watch 数 | 437 |
| 另一工作区 fileWatcher PID 4084783 的 watch 数 | 161,998 |
| 项目所在磁盘可用空间（`df -h` 舍入值） | 466 GB |

PID 4084783 的监听集合包含另一工作区的根目录；结合对应窗口的 Git 日志，可将该进程识别为另一工作区的监听器。没有修改该仓库或终止其进程。当前用户的配额由各进程共享，但复查占用没有接近上限，不能把另一窗口的占用直接认定为本次错误的原因。

### 已有规则的实际生效检查

根目录 `.vscode/settings.json` 已有 9 月 30 日加入的八条排除规则，远端 Machine 设置文件为空对象。复查没有重复添加设置。

仅遍历保留目录，剪枝既有排除项和 `.git`，不跟随目录符号链接，再与 PID 4165109 的 `/proc/<pid>/fdinfo/27` 中的实际监听 inode 匹配：

| 保留目录分组 | 目录数 | 已有实际监听 |
| --- | ---: | ---: |
| 项目根目录 | 1 | 1 |
| `.github` | 2 | 2 |
| `raw_financial_data_lake`（排除 `data`） | 25 | 25 |
| `trusted_data_synthesis`（排除产物、虚拟环境、缓存） | 175 | 175 |
| `.vscode` | 1 | 1 |
| 合计 | 204 | 204 |

四个大型目录 `.codex-worktrees`、`trusted_data_synthesis/artifacts`、`raw_financial_data_lake/data` 和 `trusted_data_synthesis/.venv` 的根目录 inode 均不在该监听器集合中。源码、测试、文档及配置目录则有实际监听。204 是上述核验范围的目录数，437 是该监听器全部 watch 数，两者统计范围不同。

另核对当前安装版本 `@parcel/watcher 2.5.6` 的排除匹配逻辑：现有四条大型目录 glob 均能匹配目录本身及其子目录，也能匹配 `/home/zhuxinrui/datatmp/…` 和 `/data1/zhuxinrui/…` 两个路径别名。这项核验不支持“末尾 `/**` 漏掉目录本身”或“路径别名导致这四条规则失效”的解释。[Parcel 扫描实现](https://github.com/parcel-bundler/watcher/blob/v2.5.6/src/unix/fts.cc)在遇到排除目录时直接跳过该子树，正常流程不会先给全部排除目录添加监听。

### 结论、边界与处理

日志确认此次警告属于文件监听 ENOSPC；当前磁盘空间与该条明确的 inotify 错误不支持磁盘已满的解释。报错后的实际监听已覆盖全部核验目录，排除规则生效，当前也没有配额持续耗尽的证据。

现有日志没有记录报错瞬间的完整监听请求、规则加载顺序或内核资源占用，因此不能确定为何新会话曾触发 ENOSPC。“启动阶段先建立大范围监听，再加载排除规则”只是一种待验证解释，不作为本次根因结论。实际安装的 VS Code 监听器代码会对 ENOSPC 错误去重，因此后续没有新错误日志不能单独证明恢复。目录已有监听也不等同于已经验证客户端事件投递或警告消失。

依照 [VS Code 官方 Linux 排障说明](https://code.visualstudio.com/docs/setup/linux#_visual-studio-code-is-unable-to-watch-for-file-changes-in-this-large-workspace-error-enospc)，优先排除无需监听的大目录。本项目这一步已经落实并通过实际监听核验；本次没有必要继续扩大排除范围或提高系统限额，更不能把现有 1,048,576 覆盖成文档示例的 524,288。

如果客户端仍保留该通知，可先关闭通知并观察源码或文档的外部修改是否正常刷新。若刷新仍异常，在保存编辑后运行 `Developer: Reload Window`（开发人员：重新加载窗口）。若重载后再次出现新告警，应采集新时间戳对应的文件监视日志和当时的配额占用；不能仅凭本次状态断言以后不会复发。

本次仅补充排查记录；未修改监听配置、系统限额或实验代码，未重启编辑器或实验进程，也未运行模型 API、GPU 或业务测试。客户端 GUI 的最终显示状态尚未直接验证。
