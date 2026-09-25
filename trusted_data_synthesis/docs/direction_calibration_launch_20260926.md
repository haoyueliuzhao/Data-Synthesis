# 后继实验实际启动与来源阻断记录（2026-09-26）

## 1. 状态摘要与时间口径

本文记录用户“参照审计修订并开展后续实验”之后的实际状态，不是实验结果报告。时间均为北京时间，原始JSON使用UTC。状态快照截至2026-09-26 01:23:13；阶段一仍在运行，尚无方向可靠性结论；阶段二未启动。

已落实审计的两阶段路线：先复用原B反馈做同点方向可靠性分析，后续再做正向／Static／反向40步短程校准。原B执行成立但正向训练价值未确认的结论不变；没有增加旧确认集种子或用旧720题继续追求显著。

本轮首个实现提交：`1ba96445ae41a6636bc0e6ab901d5e9fda5acd32`，已推送远端main。运行来自独立工作树 `/tmp/data-synthesis-fixed-kernel-parallel-tail-20260914`；没有切换或覆盖canonical工作树本地main。后续文档与尚未启用的阶段二helper不改变已经登记的运行源码。

## 2. 实际登记与复用证据

新原始数据根目录记作 `RAW`：

```text
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/
qa_vnext_fixed_kernel_value/direction_calibration_cache_20260926
```

| 项目 | 实际身份／时间 |
| --- | --- |
| 阶段一登记 | `B_direction_reliability_protocol:7d46ee39bb5e3dfacac25456ab1f42c83df02d5df79dad78b8feb9053719fcd5` |
| 登记完成 | 2026-09-26 01:11:08 |
| 守护启动 | 2026-09-26 01:11:11，PID 2368696 |
| 材料准入 | `direction_calibration_material_admission:a26b727096848e42fcaadad25537658b127d6dc4a30b8bf35790120a0898b0e7` |
| 来源采集登记 | `direction_calibration_source_acquisition_plan:6dcfef2c0ddb347e897521650d42a024c6970b3a3009711abb2ce010d7087981` |
| 来源登记时间 | 2026-09-26 01:11:15 |

原审计文本保存于 `RAW/audit_directive.txt`。阶段一登记与准入分别在 `RAW/protocol.json`、`RAW/reuse_admission.json`；来源采集合同在 `RAW/panel_sources/acquisition_plan.json`。

实际CPU准入已核验3个prefix200和6个Static／正向step240保存点，以及原201..240逐步记录：真实参数、Adam状态、RNG、游标、材料、包系数与分支来源匹配。六个step240保存点因此获得复用信用。三臂短程校准只需要新增反向3×40=120个物理SFT更新；这120步尚未执行。

原B37个科学源码身份仍受原协议约束，未修改。阶段一登记同时冻结新增运行源码和原输入文件SHA，三份每份约15.47GiB的 `population.pt` 只读复用，不允许缺失时重做全G。原失败、旧控制标量表示修订及原B最终结论全部保留。

## 3. 阶段一确已运行和保存

`RAW/heartbeat.json` 的01:22:58心跳记录如下；01:23:13进程检查确认三worker和守护仍存活，`any_failure=false`。

| seed | GPU | worker PID | 尝试 | 已提交响应／必要响应 |
| --- | ---: | ---: | ---: | ---: |
| 11 | 0 | 2368842 | 1 | 19 / 593 |
| 29 | 1 | 2368845 | 1 | 18 / 546 |
| 47 | 2 | 2368848 | 1 | 25 / 572 |
| 合计 | — | — | — | 62 / 1711（3.62%） |

这是响应回放的进度，不是整个后继研究的完成比例。01:23:13的GPU总占用快照分别为45,803／45,555／45,241MiB，利用率77%／65%／64%；GPU总占用不是进程峰值保证。GPU编号只说明此刻分配，不约束后续已登记的资源恢复。

实际首个seed11响应保存点 `RAW/reliability/B_direction_reliability_11/responses/0001.pt` 已作一次CPU必要核验：30,345,535字节、cursor1、协议绑定正确；记录1个响应、38个采样token、76个缓存目标；总累计FP32和当前轨迹累计FP64的tensor摘要均匹配。各seed后续保存点由同一原子提交规则产生，没有重复加载全部大矩阵作冗余验证。

01:23:01预算账本已预留66次响应工作（seed11/29/47分别20/19/27），worker_start为3。预留发生在工作前，且与心跳不是同一时间，因此不能把66当作已保存响应数。权威完成量来自保存点和完成清单。

预算为1711个必要响应、至多2095个物理响应尝试，并分别受每seed R+128约束；每seed最多8次worker尝试，总启动24次。新反馈生成、金融评分、SFT更新、完整G重算预算均为0。每响应保存总累计、当前轨迹累计和游标；只有资源类失败允许有限恢复，身份或数值等价失败停止。该守护不等于服务器重启后的系统级开机服务。

完成后只发布阶段一机制结果，负交叉得分也正常报告，不删seed29或任务、不自动改变训练方案，也不会自动启动阶段二。

## 4. 新来源采集：三次TLS异常后按合同停止

实际仅尝试预登记目录URL `https://www.sec.gov/files/company_tickers.json`，没有任何companyfacts请求。目录尝试1、2、3分别在01:13:45、01:14:10、01:14:41记录失败，错误均为：

```text
URLError(SSLEOFError(8,
'[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1010)'))
```

01:14:41达到单资产3次上限，采集退出，`needs_attention.json`记录 `calibration_sources.asset_attempt_cap:directory`。证据为 `RAW/panel_sources/failures/directory/0001.json` 至 `0003.json`、`network/state.json`（requests=3）、`needs_attention.json`。

这是观测到的TLS传输异常，没有收到可用于判定的HTTP403或429；不能据此写成SEC明确拒绝此IP，也不能推断根因一定是SEC或本机配置。尚未取得目录快照、候选64个CIK名单或新companyfacts；`roster.json`、`source_registration.json`及生产 `calibration_panel` 均未生成。不能宣称新180题READY，更没有新评价会话或评价结果。

原有限预算不会通过删除账本、重新运行命令或替换代理／身份自动重置。不做第4次未登记目录请求，不使用旧720题或旧overflow补位。后续需要排查并恢复合法连接，再明确登记新的有限获取修订；也可由用户提供有官方来源与完整字节证据的独立数据材料，但同样需要重新准入，不能直接获得原采集信用。

该阻断不影响独立阶段一继续运行；阶段二新训练和评价仍未派发。

## 5. 尚未启用的阶段二准备与测试范围

已实现反向分布及训练worker、新面板builder、三臂评价wrapper和配对统计。评价wrapper对九个step240模型各安排随机两次、greedy一次，并在18个cohort全部4,860会话封存且生成worker退出后开放私有评分。统计保留四个比较、CIK整簇配对和随机／greedy分离，不能将短程机制支持等同完整训练价值确认。

这些helper尚无阶段二独立执行登记与完整调度／预算上下文，也没有新面板准入。未对真实新任务生成或评分；不能把mock测试通过解释成实验完成。

测试记录：最初92项CPU整合测试通过，采集18项mock通过；随后统计31项纯合成CPU测试通过，评价12项mock通过，各新增模块ruff通过。按测试集合合计153项，不宣称进行153项全套重跑。模拟覆盖包括有限重试、OOM续跑、跨模式身份、全量生成后的评分门、逐case恢复以及失败不得记作Q=0。

实施设计与统计口径详见[协议说明](direction_calibration_protocol_20260926.md)。后续结果必须以真实完成清单为准；本文不预判方向可靠性或正向训练价值。
