# 原生产矩阵的连接中断终态修订

## 1. 实际故障与明确授权

原生产协议`5ed407ae0906a38698c13729e213cfb6178c0494bd26b54e864bd0e715f0361f`，
首次冻结源码`fd6184b15cd075865cdcfd543c4ca352516f8ae6`，北京时间13:52:57启动32并发。
13:53:25收口停止：93次provider派发，92次实际返回，1次`RemoteProtocolError`未取得完整响应或usage。
在途请求已经全部收口，pending=0。仅凭该异常类型不能确定是上游服务、代理还是连接复用导致，
没有把它误报为API key失效或金融答案错误，也没有重新测试付费模型或重发失败请求。

92个实际返回的峰值费率上界为4.238707元；该断连的2.228224元完整预留保留。
钱包累计已结算160.775113元、持有预留4.456448元（历史一条＋本次一条）、剩余有效额度
1034.768439元。未知预留不是已取得的账单或usage。原首次停止结果ID为
`7d38af6a7f879d4bb777d3eadc526c392ac8b2d6fb02627b235efe89458f4d0a`，原件保持不变。

用户随后明确回复：**“允许上述有限修订并继续同一矩阵”**。问题明确说明本次及同矩阵后续
同类连接中断，永久保留原预留、不重发、记为已尝试未返回unknown；从“全部返回”改为
“全部有真实终态记录”，实际返回单列、unknown不准训练、cap仍1200。

授权记录`network_terminal_authorization_01/record.json`，ID
`d8e44ec7270dd1764a78e408ee90bb9777d43abd01d7726158d6fb5d966f1300`。
这与费用授权不同，是一次明确的执行收口条件修订；不能宣称原全返回规则已经满足。

## 2. 不变项与改动边界

不改原protocol字节、13022个job、episode/invocation ID、namespace、原始候选、V8提示／规则、
容量或评分。原92个返回不重判成更好结果、不替换、不拼入技术样本。原第一次失败也不擦除。

新增独立`network_terminal_revision_01`绑定原protocol、原runtime、新冻结runtime及授权。
程序对关键V8语义、对齐、编码、公开harness和请求前检源码逐项核对原SHA；运行代码的合理
变更不能被用来偷偷修改有效性标准。每次恢复仍是同一矩阵，不注册另一个更容易完成的批次。

## 3. UNKNOWN的金融处理

仅覆盖RemoteProtocolError、ReadError、WriteError、ConnectError、ReadTimeout、WriteTimeout、
ConnectTimeout，且必须同时满足：原state=UNKNOWN、已落dispatched标记、没有完整响应／HTTP状态／
usage／settled金额、原reason一致、原请求body与注册job哈希一致、pending=0。

CancelledError、PoolTimeout、服务HTTP失败、模型不符、usage异常、无关halt均不在此授权内。
存在未覆盖的错误即停止，不将“同类”无限扩大。并发多条unknown在同一事务核对全部未确认项，
不能只确认当前halt指向的一条而掩盖其余项。

确认只追加逐条ack及批收据，保留原request行、state、全部费用／hold／请求计数和旧历史UNKNOWN。
永久预留继续计入1200元总占用，不释放、不凭估计填写usage；清除的只能是已核实属于这些原连接
中断的exact halt。原请求永不重发；新调用仍受原钱包事务的费用＋预留、全局请求和production子额约束。

## 4. 收口、返回和材料是三个不同判断

网络终态工件明确写`terminal_kind=acknowledged_connection_unknown_no_model_response`，
`model_response_received=false`，`usage/review_text/api_response_raw`均为None，
`actual_model_calls`为未知，不伪造一份模型回答。它引用真实原网络证据及保守ack，而非创造response正文。
原V8检查将其保持为unknown，derived=None、无正mask，永远不能成为joint-valid原包。

新`v9_production_completion_seal.v2`同时记录：

- expected_requests=13022；
- processed_jobs：有真实返回或已获授权连接unknown终态的job数；
- completed_requests：真正取得模型返回的数量；
- network_unknown_jobs：未取得模型返回的授权终态数量；
- 两者相加必须等于完整processed_jobs，所有13022个原坐标都在；
- all_registered_returns_present仅在unknown=0时为true。

旧v1继续要求全部返回，不能将缺失返回伪装成v1通过。新版loader绑定这项独立修订及每条ack，
对unknown强制validation=None；全部原job都处理完才可确定X*，不能把92份或其他成功前缀用于训练。

## 5. 有界继续与其他故障

新冻结版本`resume`先核对并终态化获授权的原网络unknown，再复用所有真实已返回原件，继续仅确认
未发送的既定job。未来同类中断先停止派发、完成在途收口、执行同一严格ack，随后继续同一矩阵。
每个恢复循环必须取得新的原job处理进展，不增加job或重试次数；最多受13022个注册坐标及1200元约束。

预算不足、本地映射／封存异常、非授权网络类型、UNKNOWN使用量/模型错误或partial反馈均不被该循环
绕过。训练仍须全材料、非平凡profile及Student前探索性规模决定，网络处理许可不等于训练许可。

## 6. 验证边界

临时SQLite及mock控制验证多个unknown同批确认、同scope后续确认、幂等、旧记录/hold不变、错误类型／
无关halt拒绝、无模型返回字段保持None、V8有效标签unknown、已处理和实际返回分开、新v2完整门，
并保留旧v1及条件loader回归。它们不构成真实审阅或材料产率结果。

真正生效的执行修订、实际账本确认和继续运行时间将在工件及主报告中追加，不能由这些CPU控制预填。
