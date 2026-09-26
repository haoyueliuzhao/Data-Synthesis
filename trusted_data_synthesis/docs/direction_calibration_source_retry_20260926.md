# 新来源采集执行修订01：有限TLS诊断与固定路线重试

## 1. 授权和不变范围

2026-09-26用户同意“排查连接后，另行登记一轮有限来源采集重试”。本修订只处理原目录请求三次TLS EOF后的网络恢复和同规则有限采集，不改变来源选择、任务构造、组配额、三臂分布或统计口径，不授权自动扩大来源或训练剂量。

旧 `panel_sources` 全部文件的SHA随新合同登记，并在读取修订时核验；旧3次失败、请求意图、预算账本、原计划及 `needs_attention.json` 不删除、不覆盖。新文件独立放在：

```text
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/
qa_vnext_fixed_kernel_value/direction_calibration_cache_20260926/
panel_sources_retry_revision_01/
```

新增适配器为 `scripts/retry_direction_calibration_sources_20260926.py`。原collector、panel builder和科学代码保持冻结；通过独立函数命名空间复用旧采集逻辑，不全局替换旧RAW、urllib模块或旧路径。

## 2. 非网络配置检查所得事实

09:46之后检查发现，Python urllib的HTTPS和HTTP代理配置均指向 `http://127.0.0.1:7897`，两个SEC主机没有NO_PROXY豁免；该本机端口在监听。未打印其他环境变量或代理凭证。

虚拟环境使用OpenSSL 3.5.7，存在默认CA文件；未设置SSL_CERT_FILE、SSL_CERT_DIR、REQUESTS_CA_BUNDLE或CURL_CA_BUNDLE。系统curl使用另一OpenSSL版本并不自动证明原故障是版本问题。本修订不切换成curl获取，也不关闭证书校验。

原日志只有TLS EOF，没有收到可解释为SEC拒绝的HTTP状态。配置中存在代理只能说明原请求路径，不能单凭此断言代理就是根因。

## 3. 有限诊断、路线固定和停止规则

在新增适配器已提交、源码SHA和修订合同已登记后，最多进行两次TLS诊断连接，固定主机 `www.sec.gov:443`，每次超时20秒：

1. 原已配置的本机HTTP代理 `127.0.0.1:7897`；若需要，向该代理发CONNECT。
2. 仅当前项出现明确的网络EOF、timeout、reset/refused、DNS或不可达错误时，允许一次直连。

诊断仅完成证书与主机名验证的TLS握手，不向SEC发送GET/HEAD，不接收候选公司数据。代理CONNECT仍是单独计量的网络工作，不能冒称完全没有HTTP网络动作。所有代理CONNECT非2xx、证书验证失败以及其他程序错误均终止，不触发直连。意图已写而结果未保存时也停止，不因不知道先前结果就重试。

第一个TLS成功的路线写成不可变 `route.json`；重启复用，不重新择路。实际采集开始后的HTTP或TLS失败不得改变路线。固定代理handler不接受环境NO_PROXY的隐式直连，直连handler使用空代理表；不选择其他代理、不改User-Agent、不改主机、不跟随重定向。全部HTTPS保持默认信任库和原主机名验证。

任一旧或新 `access_blocked.json` 都会阻止后续网络工作；实际HTTP403/429沿用原全局停止规则，即使错误体读取失败也保留停止标记。

## 4. 物理预算和科学合同

| 工作 | 修订上限 |
| --- | ---: |
| TLS诊断连接 | 2（其中代理最多1次CONNECT；无SEC HTTP探测） |
| 新采集HTTP尝试 | 195 |
| 每资产HTTP尝试 | 3 |
| 原有HTTP尝试 | 3，原账本不变 |
| 原有＋修订HTTP尝试 | 最多198，另计最多2次TLS诊断连接 |
| 新模型生成／评分／SFT／Probe | 0 |

195不是195个成功资产，也不是自动用满的目标。任何单资产达到3次、拒绝访问、非5xx HTTP错误、无效内容或来源/配额不足均按原合同停止。采集仍单线程、间隔至少0.5秒；单响应64MiB上限，原始响应与失败保存，成功缓存按计划身份及字节摘要复用。

目录成功后，仍排除原100个CIK和8个历史ticker的所有CIK别名，沿用原dev source split和固定新hash排序，先冻结64个来源名单再取得companyfacts。名单不受已经得知的阶段一得分影响。全64个快照封存后才运行原确定性180题builder；三组各60题，不替源、不补旧题、不扩年份或修改金融语义。

新面板如构建成功，位于修订目录内部的 `calibration_panel`，与旧路径分开。它也不会自动获得阶段二执行信用；阶段二仍需独立冻结的调度、统计、预算和全量生成后评分合同。

## 5. 阶段一在此期间的实际状态

原机制核查于北京时间05:53:29完成：1711个响应、292条正轨迹、3个worker启动，没有额外响应尝试；新SFT、生成、金融评分和全G均为0。自动发布提交为 `92b1e4f9dd`。其结果不用于修改本轮来源顺序或筛选种子。

| seed | S1→2 | S2→1 | 两半C加权余弦 |
| --- | ---: | ---: | ---: |
| 11 | −2.8351586e−5 | −3.8111658e−5 | −0.0733791 |
| 29 | +3.2281194e−4 | +2.6662995e−4 | +0.5959874 |
| 47 | +4.7592641e−4 | +4.6223842e−4 | +0.7688997 |

三个种子的同点方向重复性不同；这些是原反馈拆半诊断，不能推出新任务泛化或正向训练价值已经成立，也不能因此删除seed11或保留部分种子。完整机器汇总见[阶段一完成记录](direction_reliability_completed_20260926.md)。

## 6. 实际运行补充

初版说明与实现于提交 `148e67da3fed9f3d41fd5490424c5e8968fb75c9` 冻结并推送后才开始登记。新增28项纯mock测试全部通过（3.12秒），ruff通过；没有通过真实请求调试或调整科学规则。

实际修订ID：

```text
direction_calibration_source_acquisition_plan:
c7ce0b7e3e644dfa0f6e6c3e477838918e7f06010ba522e5325972db28b6f87d
```

以上换行只用于显示，真实ID的冒号后直接连接64位摘要。时间记录如下（北京时间）：

| 时间 | 实际事件 |
| --- | --- |
| 10:00:51 | 新采集合同登记完成，尚未联网 |
| 10:01:09—10 | 原本机代理路径TLS握手成功，TLSv1.3、TLS_AES_256_GCM_SHA384，正常证书验证 |
| 10:01:10 | 将原代理路径封存为固定路线，预留目录GET尝试1 |
| 10:01:11 | 目录请求返回HTTP403，先写停止标记，再保留响应体与失败；执行退出 |
| 10:01:36 | 原阶段一守护与三个worker PID均已不存在 |

**结果：TLS层本次可通，但实际目录HTTP访问被拒绝。** 这不说明原TLS EOF的根因已经确定，也不能将TLS握手成功写成SEC数据可获取。

403响应体共1,925字节，保存于修订目录 `raw_attempts/directory/0001.bin`，SHA256为 `572d14b9bc5309c646cfd2b3e8911ea7201437c9ce8a586d50b6408d2350e3f8`。HTML标题为“SEC.gov | Request Rate Threshold Exceeded”，内容提示自动访问须符合SEC政策。该响应支持“本次收到访问拒绝”，**不单独证明本实验发送速率超标**；本修订实际上只进行了1次目录GET尝试，具体限制原因仍未知。

修订实际消耗1次TLS诊断连接、1次HTTP采集尝试。未进行直连诊断、未更换代理或身份、未发起第2次目录请求。加上原3次失败，累计4次HTTP采集尝试；原计划剩余额度不代表可以绕过新的403停止条件。

停止后的只读核验确认：旧 `panel_sources` 的全部文件摘要仍与登记时一致；旧账本requests=3，新账本requests=1；修订 `access_blocked.json` 存在。没有 `roster.json`、`source_registration.json`或生产 `calibration_panel`，没有取得64CIK名单、任何companyfacts或新180题。阶段二训练、生成、评分仍均未启动。

原始证据位于修订目录的 `acquisition_plan.json`、`diagnostic_intents/01.json`、`diagnostics/01.json`、`route.json`、`network/state.json`、`network/directory/0001.json`、`failures/directory/0001.json`、`access_blocked.json`、`needs_attention.json`及原始响应体。重复执行命令会保留并遵守停止标记，不自动重启采集。

## 7. 后续边界

本次授权的有限诊断与重试已执行并如实停止，未实现“新面板就绪”。后续需要确认合规访问恢复，或提供具有官方来源、获取时间及原始字节证据的合法独立数据材料，再另行修订准入与恢复合同。不能通过换IP、代理或身份绕过本次403，也不能把旧面板重新命名为新面板。阶段一已完成的结果和六个旧step240复用信用继续保留，不因该网络阻断而重算。
