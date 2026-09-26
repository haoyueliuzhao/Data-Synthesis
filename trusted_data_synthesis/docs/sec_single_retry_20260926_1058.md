# SEC目录单次重试记录（2026-09-26 10:58）

## 授权、范围与结果

用户明确要求“重试SEC”。本轮只请求原目录 `https://www.sec.gov/files/company_tickers.json` 一次，保持7897、已确认的真实项目联系邮箱、默认CA及主机名校验。不换出口、不直连、不跟随跳转，不自动重试，不抓companyfacts或构建面板。

北京时间10:58:32登记，10:58:33收到 **HTTP403 Forbidden** 并停止。原始HTML仍提示SEC自动访问政策，标题为“SEC.gov | Request Rate Threshold Exceeded”。这证明本次目录HTTP访问受到拒绝，但不能单凭标题证明本实验超速或确定封禁触发因素。

响应参考号：`0.d73edc3d.1790391513.179c6354`。响应体1,925字节，SHA256：

```text
bb68d650bef2802c0a3f17a39d7a43138e42a99fb163ce1ba658743286ae67e9
```

本次请求在带真实联系邮箱、距上次SEC尝试超过20分钟后，仍未恢复目录访问。此前10:48的非SEC检测中，7897在curl和实验Python下均正常，见[代理连通性记录](proxy_connectivity_diagnostic_20260926.md)。因此不能将当前问题笼统描述为整个7897代理失效；SEC目标的具体规则、出口限制和间歇链路问题仍需结合本机代理日志核查。

## 单次预算与证据保留

执行源码提交：`7bd3fcf44e`。独立登记：

```text
SEC_directory_single_retry_plan:3581669018fc9389d685ee18e9bf904e536cc01d6907094cde58635cb0042e67
```

HTTP总上限1、每资产上限1。此前三轮实际请求分别3、1、1，旧记录均不重置；本轮账本requests=1，累计SEC采集尝试6。所有旧文件摘要与登记时一致。没有第二次目录请求，也没有改变任何已有403停止标记、训练协议、预算或保存点。

新证据根目录：

```text
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/
qa_vnext_fixed_kernel_value/direction_calibration_cache_20260926/
sec_directory_single_retry_20260926_1054/
```

目录名1054是本轮准备时间，实际网络请求发生于10:58；时间以JSON中的UTC时间为准。关键文件：`plan.json`、`network/state.json`、`network/directory/0001.json`、`failures/directory/0001.json`、`raw_attempts/directory/0001.bin`、`access_blocked.json`、`latest_result.json`。

## 核验与日志问题

执行前做了最小纯mock核验：200情形两次调用仅一次GET且第二次复用；403情形第二次不发GET；旧三轮证据无误写，无下游采集。ruff通过。模拟测试未使用真实网络。

真实运行中，HTTP失败、原始响应、停止标记、请求次数以及顶层结果都已成功保存。随后控制台输出调用把结果中的`at`再次传给自带`at`的日志函数，产生 `TypeError: dict() got multiple values for keyword argument 'at'`。该问题发生在结果持久化之后，不是SEC拒绝原因，没有引起新请求或破坏保存记录。

通过只读 `latest_result.json`、失败收据及账本确认实际结果为403、requests=1、old_evidence_unchanged=true。已执行的一次性源码保持原字节供审计，不热改冻结记录，也不通过重新运行网络来修复控制台输出。该一次性脚本不作为通用重试器继续使用。

结论仅为“目录重试仍被拒绝”。没有取得有效目录JSON或新校准面板，不能据此开放新评价；既有独立训练不受这次只读网络请求影响。
