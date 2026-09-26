# 2026-09-26 恢复说明：SEC原因核查与独立负向训练子阶段

## 1. 用户授权与当前证据

用户要求“排查原因，恢复实验”，随后确认可以沿用仓库Git配置的真实联系邮箱作SEC项目声明。用户提出可能key过期并手动核验；期间未发起新采集请求，之后用户明确反馈“DeepSeek API key 正常”。本次没有读取或打印`.env`或API key，没有为核验而调用DeepSeek。

现有SEC请求只使用HTTPS、User-Agent等常规头，代码不读取DeepSeek key、不使用该key作Authorization。因而，不能将这次SEC目录403归因于DeepSeek key过期；也不能据此推定所有代理凭证都正常。

本机只读检查发现：`127.0.0.1:7897`监听socket属本用户UID1004，位于09:15:19建立的SSH会话42439，相关可见进程为sshd。端口位于SSH会话中，但没有可读的转发目标、上游出口和聚合请求日志。当前会话晚于01:13—14原TLS失败；固定本地端口并不能证明前后有相同远端出口。因此，原TLS EOF的精确根因仍无法确定。

10:01已有证据明确显示正常验证的TLSv1.3握手成功，紧接着目录GET收到403及SEC风格拒绝页，参考号 `0.5052cd17.1790388070.c0f77413`。仅凭页面标题不能区分同出口聚合限流、出口信誉、身份声明等触发因素。没有发现本地GET/HTTPS CONNECT/证书校验实现错误。

同机另一个用户的代理进程不是已确认的本任务出口，没有读取其私有配置、订阅、凭证或连接历史。也没有通过IP检测站点、其他代理或浏览器伪装去探测被拒绝资源。

## 2. SEC合规声明修订的边界

[SEC开发者FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions)要求声明自动客户端，并给出机构名和管理员联系邮箱的请求头示例；访问拒绝未解决时可向其webmaster提供错误证据。[SEC安全政策](https://www.sec.gov/files/privacy.htm)说明聚合请求限额及低于阈值10分钟后的恢复安排。这些政策不保证一次修正就解除403，也不保证本机未发请求时其他共享出口用户同样静默。

原User-Agent有项目名和GitHub网址，没有联系邮箱。使用用户确认的真实项目联系邮箱是诚实完善声明，不是伪装成浏览器或其他机构。旧采集与修订01的全部SHA、失败、账本、403停止标记继续保留；**不解封或重启旧合同**。

新增 `prepare_calibration_sources_compliance_20260926.py` 使用独立目录：

```text
direction_calibration_cache_20260926/panel_sources_compliance_revision_02/
```

源码提交、冻结和单独登记后才执行。自原403至少等待600秒，仍固定使用原本机代理地址，不建立新的探测路线，不做TLS-only或直连探测。目录只允许1次GET尝试；若网络失败、5xx、403/429或内容错误，均不能重试目录以碰运气。403/429继续全局停止且先保存停止标记。

只有目录成功并按原规则封存64个CIK名单后，才能沿同一路线取得companyfacts；每资产至多3次、最小间隔2秒、总HTTP上限193=1+64×3。此前实际4次尝试另计，累计最多197；此前1次TLS诊断另存，不归零。保留64来源、dev split、全部历史排除、原hash排序、组配额、年份和builder；不依据阶段一得分或后续训练表现选源。所有来源封存后才构建180题，任何不足或拒绝均停止，不换源或补旧题。

## 3. 为什么可以先独立恢复训练

审计第352–368行规定同一真实step200→240、40步完整epoch及六个旧点核验后的复用。第372行明确“来源簇在生成前分割”，并未要求新面板在训练前就绪；第414行要求新的条件性方案单独登记。

已有材料准入 `direction_calibration_material_admission:a26b727096848e42fcaadad25537658b127d6dc4a30b8bf35790120a0898b0e7` 已核验三份真实prefix200、六份Static/正向240的参数、Adam、RNG、日程、材料和原包系数。此信用保留，不重复训练旧两臂，不将其“已存在”混写成新物理消费。

因此新增独立训练子阶段，而非修改阶段一的optimizer=0预算。采集仍可能BLOCKED、新面板仍NOT_READY时，只允许完成已经固定的反向尾段。它不是整个阶段二已经恢复，更不允许在旧720题上试评价。

## 4. 训练合同、有限资源恢复及保存

新增控制器 `scripts/run_fixed_kernel_calibration_training_20260926.py`，独立数据目录：

```text
direction_calibration_cache_20260926/training_stage_20260926/
```

固定seed11、29、47，三个作业 `B_negative_SEED`，只执行step201..240。分布仍为已准入的q⁻=2r−q⁺；不clip、重归一化或根据阶段一的负交叉得分筛选seed。原负向worker及原B科学代码不修改。

| 计量 | 固定合同 |
| --- | ---: |
| 新已提交更新 | 每seed40，共120 |
| optimizer物理尝试预留上限 | 每seed48，共144 |
| worker启动 | 每seed至多8，共24 |
| 成功提交的原包序列token | 53,435,082 |
| 成功提交的原包监督token | 2,946,264 |
| 新生成／评分／反馈／全G／Probe | 全部0 |
| 新Static／正向训练 | 0 |

恢复余量包括在144次尝试内，不是宣称失败成本为0；账本先预留后计算、不会回退。每步保存真实theta、Adam、全部RNG和游标；已经提交的步不重算。只对资源让位、OOM、内存不足或明确外部终止作有限恢复，身份或数值错误停止。

最多3个GPU worker，每worker32GiB自身容量门槛、冷启动另1GiB；新启动要求主机可用内存64GiB和数据盘余量100GiB。使用GPU UUID租约、PID出生身份和作业锁，守护重启可接管活worker，不重复派发；这不是开机服务。

三个seed全部保存点、剂量和报告通过才记录训练完成。结果仅表明训练端点齐备，不能确认训练价值。自动发布只提交本子阶段指定结果文件，推送失败只重试发布，不重训。评价不会自动开启，仍需新面板准入与单独执行登记。

## 5. 验证与实际执行补充

代码在提交 `188e4d049274e73f828ae126bd5818ce7fc85411` 冻结并推送后才登记、运行。新增训练控制52项纯CPU测试通过（2.73秒），采集合规22项纯mock测试通过（3.23秒），两模块ruff通过；没有以真实结果调整方案。

### 5.1 已实际登记并启动训练

训练协议为 `B_direction_calibration_training_protocol:cb82d4044d9cb935dc4d5fe0575cf4bf49d43f08478b1040cc2ecfdc9cfc42ad`，北京时间10:28:01登记。10:28:50启动守护PID2682910，10:28:57实际派发三个worker：

| seed | GPU | worker PID | 首次尝试 |
| --- | ---: | ---: | ---: |
| 11 | 0 | 2682975 | 1 |
| 29 | 1 | 2682979 | 1 |
| 47 | 2 | 2682983 | 1 |

10:30:17心跳显示三个worker均存活、无失败、评价未启动；10:30:27 GPU利用率均100%，显存分别24,341／23,937／24,921MiB（GPU总占用快照，不是承诺峰值）。10:29:29账本为3次worker_start与3次optimizer预留，三seed各1次。此时尚无已提交更新；预留或GPU繁忙不能冒充完成step201。实际保存进度另以 `training_stage_20260926/heartbeat.json`、各 `jobs/B_negative_SEED/updates` 和逐步日志为准。

随后三seed均真实提交step201：seed29在10:31:19、seed11在10:31:22、seed47在10:31:30保存 `.pt` 与对应 `.json`。10:32:57心跳为各1步、共3/120，三个worker仍为首次尝试、无失败，评价仍未启动。这提供了“训练已经恢复并实际保存”的证据，而不只是派发进程。

对seed11首个新保存点作一次必要CPU实读核验：文件30,566,427字节，协议与 `B_negative_11` 身份匹配，completed_updates与RNG游标均为201；真实状态与optimizer snapshot核验通过，内嵌update和JSON一致。snapshot ID为 `optimizer_binding:53e1bdc0619a06eaa33d31e8472e588a3356a8484ecc2ca59f0fecf411d20d84`。三个seed的step201报告也均通过内容身份校验，pool=B、arm=negative、optimizer_step_calls=1；没有重复加载全部旧保存点。

### 5.2 采集合规复验仍未恢复来源

来源修订为 `direction_calibration_source_acquisition_plan:58fd26a685d4daa594ae3aa4e5a9df522f660ccf5350a7cff8dc6bc6db67e446`，10:28:16登记，10:30:03预留唯一目录GET尝试。10:30:24记录：

```text
URLError(SSLEOFError(8,
'[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1010)'))
```

本次没有收到新的HTTP状态或目录内容，随后因目录单次上限退出。**这不是“更改邮箱后仍收到403”，也不是“邮箱修正已解除403”。** 真实声明在该次TLS失败链路上没有获得可解释的HTTP检验；原403仍是有效历史证据。

停止后的只读核验确认旧两个来源目录的全部SHA保持不变，新请求账本requests=1，无新HTTP拒绝标记（因为未收到HTTP响应），无新名单、来源注册或面板。包含此前4次，实际累计5次HTTP采集尝试；没有额外TLS-only探测、直连或换代理。该修订即使没有新的403标记，也受目录一次额度约束，不能重复运行来重新获取请求机会。

这表明SEC数据访问链路仍未恢复，但不能进一步归因于特定API key、代理凭证或远端服务。下一步所需的是对本用户SSH转发/代理上游的实际维护核验，或官方对访问限制的确认；不能用更换出口、虚假身份或旧题替代新源。可提供合法、可审计的官方快照作为另行登记的替代输入。

原始证据位于 `panel_sources_compliance_revision_02/acquisition_plan.json`、`network/directory/0001.json`、`network/state.json`、`failures/directory/0001.json`、`needs_attention.json`。该网络失败不改变已启动的训练子协议；整体状态为“训练已启动，来源／评价仍受阻”，不是整个后继实验已经完成。
