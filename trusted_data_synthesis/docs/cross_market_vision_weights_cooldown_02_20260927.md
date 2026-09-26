# 官方模型获取02：429后独立、有限、低速冷却阶段

## 为什么新建阶段

获取01实际执行了2次HTTP预约／请求，18个固定文件中0个哈希通过。`added_tokens.json`收到HTTP429；README在途线程随共享停发标志退出，保留0字节partial；其余16项没有开始。01所有协议、attempt、请求记录、receipt、partial及summary保持不变，已花预算不退回。

绑定的真实01记录：

- 获取协议：`cross_market_vision_weight_acquisition_protocol:249242df31c0cb63f89a7cbc614d0817c7f8980ed78b9a09693a09d1878946bb`。
- 完成记录：`cross_market_vision_weight_acquisition_summary:d48110b3ccc9a71beacc9c4fb55e429d97e2534af3666f2b4a193b968df38e4c`。
- 429回执：`cross_market_vision_artifact_receipt:abc837d6363bc1e08988aa28ac8186fa179504a4ee7f50cf51f7f95181c295e1`。
- 429回执时间：`2026-09-26T17:48:53.236132+00:00`，即北京时间2026-09-27 01:48:53.236132。

观察到的是429限流，不是403鉴权拒绝。控制端于2026-09-27核验[Hugging Face官方rate-limit说明](https://huggingface.co/docs/hub/rate-limits)，文档描述5分钟窗口及等待reset后再试的处理方式。本阶段选择至少15分钟冷却，并分散每一次请求；这是单独登记的合规退避，不是修改01失败、切换身份或绕过访问控制。15分钟是固定保守下限，不保证共享出口的服务端额度届时必然恢复，也不伪造01未保存的Retry-After／RateLimit响应头。

## 严格not_before

02的`not_before`由01真实429回执时间加900秒确定：

**UTC 2026-09-26 18:03:53.236132，即北京时间2026-09-27 02:03:53.236132。**

只有代码提交冻结之后才能登记新协议。`register`本身不联网，可在冷却期内完成；`run`在读取并复核协议后、取得执行锁或创建任何file／HTTP预约之前检查时间。如果未到not_before，立即报错退出，不发GET、不占新尝试预算、不启动15分钟sleep或自动定时重试。控制端必须在达到门槛后明确再调用run。

## 新预算与不变条件

新脚本为`acquire_cross_market_vision_weights_cooldown_02_20260927.py`。通过隔离函数namespace复用已冻结01字节限制、hash、redirect、保存／恢复、拒绝停发及summary逻辑，不修改01模块全局变量或科学门槛。

| 项目 | 02约束 |
|---|---|
| 模型／revision | `OpenGVLab/InternVL3_5-8B-HF`／`741a7d03020411e666c6109218ab71e08151ef86`，不变 |
| 文件及顺序 | 01固定manifest全部18项，文件名／URL／精确bytes／hash／顺序均不变 |
| 并发 | 从01的2降低为1；单线程按原顺序处理 |
| 起始间隔 | 每一个HTTP GET起始至少间隔5秒，包括同文件redirect hop；每次控制端运行首次发送也先保留5秒缓冲 |
| 单文件次数 | 每项最多1次初始GET，最多4次官方allowlist HTTPS重定向；无阶段内重试 |
| 新阶段总量 | 最多18个初始GET、90个含redirect的HTTP预约 |
| 两阶段累计上界 | 01已用2，加02上限，最多20个初始GET、92个含redirect预约；不是给01退款 |
| 字节与hash | 继续精确清单bytes+1哨兵、权重SHA-256／元数据指定算法，不通过不发布final |
| 磁盘／超时 | 沿用50GB空闲下限、120秒socket、3,600秒文件deadline及检查点限制 |
| 认证／代理／来源 | 不认证、不读key、原direct配置、默认TLS、原官方URL，不更换镜像或域名单 |
| 安装／加载／GPU／PDF | 均为0 |

脚本不主动修改代理或出口，不执行IP查询，不选择或轮换IP。**本阶段没有独立测量真实公网IP，不能声称已经验证前后公网IP绝对相同。**不因外部网络配置可能发生变化而自动改路由；仍只使用同一direct连接方式和固定官方地址。

5秒节流是最大5秒的短等待循环，可被停发事件中断；实际实现还在前一次响应头观察结束时更新间隔时钟，使下一请求不早于此前响应头观察后5秒，严格强于仅按请求起始间隔。它不替代前述900秒启动门槛，也不根据服务端返回内容自动申请第三轮预算。所有新请求仍先保存不可变HTTP reservation，实际dispatch之前再记录paced start。预约先于发送，因此进程若在两者之间中断，预约数仍按保守上界报告，不退款或把其视为可以重放。

## 安全限流头观测

02额外保存以下响应头的有限诊断值：`Retry-After`、`RateLimit`、`RateLimit-Policy`、`RateLimit-Limit`、`RateLimit-Remaining`、`RateLimit-Reset`。适用于成功、redirect及HTTP错误，均绑定当前文件、hop、HTTP reservation和paced start。

只记录最多512字符的可打印ASCII值；带控制字符、超长内容、URL或Bearer标记的值只保留hash／长度及withheld说明。不保存Authorization、Cookie、Set-Cookie或错误正文；signed redirect query继续仅保留完整URL的hash，不能进入日志。HTTP日期格式Retry-After可以作为诊断记录，但绝不会自动执行其重试建议。

新的429或403都立即保留失败并停发剩余文件。02为单线程，不会继续向其他文件轮换请求；再次执行同一02阶段时，已有429／403仍阻止新的发送。脚本没有自动第三轮、进一步换源、改身份、改代理、变更allowlist或清空失败状态的代码路径。

## 隔离与保存

唯一新输出根：

`cross_market_calibration_cache_20260926/original_evidence_revision_02/vision_model_acquisition_cooldown_02/`

最终文件位于此根的`models/<revision>/`。既不复用01的失败partial，也不对其发Range续传。01曾尝试的2项如果02到时执行，属于清楚登记的新阶段尝试；另外16项也受同一02单次预算限制。所有01产物保留原hash和路径。

除继承的`attempts/`、`HTTP_requests/`、`receipts/`、`models/`及不可变`runs/`总结外，新增：

- `HTTP_starts/<filename>/<hop>.json`：节流后、发送前的不可变dispatch记录；绑定reservation ID及安全目的摘要。
- `HTTP_observations/<filename>/<hop>.json`：HTTP状态、有限安全rate headers、观察时间及错误类型；显式标注`automatic_retry_scheduled=false`。

02自身已失败或未结算尝试仍不可重放；成功final可按01规则重新核验精确hash后复用。控制端中断前未开始的文件，只有在原02预算仍有余量且该阶段未出现429／403时才可能在正常恢复中开始。旧总结版本仍保留在`runs/`，最新summary原子更新。

## 证据及完成边界

新协议绑定01 protocol、summary及429 receipt的完整路径／bytes／SHA-256，复核相互ID归属、18项／0通过／2请求／429时间和文件manifest身份。每次恢复还检查冻结源代码hash、单线程、固定not_before、5秒间隔及18／90预算，不能通过改本地JSON降低门槛。

只有18项全部精确内容通过才能报告固定文件准备完成且`NOT_LOADED`。这仍不是模型依赖兼容、视觉推理能力、独立财务语义审阅或全源证书。本代码与文档编写阶段没有真实注册或发起02 GET；真实时间、状态、服务端头、传输字节及失败结果须由后续不可变记录报告，不能把此计划写成执行成果。

合成测试用虚拟时钟，无900秒／5秒真实等待、无网络。覆盖冷却边界之前零预约、精确微秒门槛、逐GET及redirect间隔、单线程新namespace与01全局不变、响应头白名单与敏感／异常值不落盘、新429／403不再请求、节流中断、未知尝试不重放及新旧预算不混用。
