# 当前文本审核：共享节流、429冷却与有限熔断

本辅助层只管理一次既有DeepSeek POST的发送时机，不自行重试，不改变端点、key、模型、source payload、`user_id`或代理配置。当前实验保留已登记`deepseek-v4-pro`以避免混合；用户要求的后续新实验固定`deepseek-flash`由项目后续协议执行，不能借本轮恢复偷偷换模型。

## 接口与固定限制

`expected_pacing(not_before)`返回登记字段，外层协议保存为`pacing`。`make_sender(state_root, protocol_reference, real_sender=None)`返回可直接注入既有Provider的`sender(payload_bytes, key)`；`state_root`须为`base.RAW`内独立目录。默认real_sender仅为原`transport.one_post`，仍只有一次固定官方路由调用。`paced_provider_class(old_provider, sender)`在构造时注入此sender，并尽可能在旧Provider保存物理回执前先检查熔断。

同进程、同state_root和协议引用的多次make_sender共用一个coordinator，统一限制最多4个在途sender、相邻dispatch起始至少2秒。不同Provider实例不能各自取得独立4并发额度。外层控制器原有单实例运行锁负责防止两个独立控制器进程同时运行；helper不改变该锁。

本轮初始not_before为`2026-09-27T02:01:33.973906+00:00`，等于最后已知429加300秒。等待以最多30秒的可唤醒条件变量等待分段执行，不启动新路由或在等待时发探测请求。

新429会保存安全限流头及`HTTPError.code`，全局冷却至少300秒；若有效Retry-After指定更长间隔或更晚HTTP日期，则遵循更长值。未有成功HTTP响应之间连续429按300／600／1200秒退避，此后每次至少1200秒。成功HTTP响应可以清零连续计数，但不清除已有冷却，也不清零本阶段累计429数。

累计第6个已观察429打开持久熔断，禁止之后的新POST。已在途最多4个调用允许结束，其响应仍保留，所以最终观察到的429数可能因已在途响应略超过6；这是在途结算，不是熔断后继续发新请求。状态重启不清零，不自动解熔断或补发；额外POST预算由外层另行登记和先记账，helper不增加或退款。

## 真实wire账和不确定性

`wire_attempts/<serial>/start.json`只在通过初始时间、冷却、并发和熔断门槛后写入；对应`outcome.json`保存真实sender返回／HTTP错误／传输错误。prewire拒绝不创建wire记录。旧Provider在并发竞争中可能已开始自身记录而随后被sender的最新熔断状态拦截，其旧receipt中的`physical_requests=1`不能独立作为真实HTTP计数依据；以新wire账区分有响应的调用、未结算dispatch和未进入wire的拒绝，绝不回写旧receipt。

软件start记录与真正服务器接收之间存在进程中断窗口。没有outcome的start仅为未结算dispatch，不证明服务端收到HTTP；外层已预约预算仍按保守原则保留。这里不是网络抓包或账单精确证明。响应体、授权头、key和HTTP错误正文不由pacer保存。

白名单包括Retry-After、RateLimit／Policy及常见request/token额度诊断头。最多512个可打印ASCII字符；包含当前key、URL、Bearer、控制字符或超长内容时只记withheld理由。忽略Authorization、Cookie等未登记头；HTTP错误body不读取。默认传输与外层已有安全响应存档保持不变。

## 证据边界与测试

官方错误码文档要求遇429降低速率；账号级额度不能由本地仅16并发反推，因此本阶段只执行保守节流，不声称已确定账号的总体用量或代理／IP根因。该层不会使HTTP／JSON技术失败自动成为财务排除，也不会改语义validator或模型审核结论。

11项必要合成测试使用虚拟时钟和假sender，覆盖初始not_before、2秒间隔、真实最多4在途、300／600／1200退避、Retry-After整数及HTTP日期、更长冷却、累计6次持久熔断、重启不解锁、HTTP错误正文不读／key不落盘、一次底层调用、key／模型变化拒绝、共享coordinator，以及prewire熔断不制造旧物理receipt。没有真实API、key读取或真实长等待。
