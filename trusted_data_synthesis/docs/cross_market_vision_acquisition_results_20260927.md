# 视觉模型文件获取01／冷却02：真实结果及只读审计

## 结论

冷却02执行结束，但模型文件仍未准备完成。18项固定文件中仅4项元数据成功，合计47,398 bytes；`generation_config.json`在初始GET收到HTTP429，随后13项未开始，其中包括全部4个权重分片。主流程已停止继续匿名尝试，没有开启第三轮、修改失败回执或切换来源。

02真实完成状态为`MODEL_ACQUISITION_NOT_READY_FAILED_OR_INTERRUPTED`。两轮累计7个文件attempt、11个含redirect的HTTP预约／请求；这不是7个成功文件，也不能把尚未使用的预算视为可以自动继续调用的授权。

CPU运行环境构建属于另一个阶段：协调控制端已报告CPU环境build成功，相关流程见[源码构建说明](cross_market_vision_source_build_20260927.md)及[缓存构建说明](cross_market_vision_cached_build_20260927.md)。本次审计不重新认证该构建；模型权重未齐仍是独立阻断，不能据CPU build成功声称模型已加载、视觉能力已经验证或实验整体已经完成。

## 固定来源与证据身份

两轮均绑定`OpenGVLab/InternVL3_5-8B-HF`，revision固定为`741a7d03020411e666c6109218ab71e08151ef86`，18项原manifest的文件名、URL、bytes及hash未改变。4个权重分片总计17,056,744,056 bytes，本次均未开始获取。

01记录：

- 协议：`cross_market_vision_weight_acquisition_protocol:249242df31c0cb63f89a7cbc614d0817c7f8980ed78b9a09693a09d1878946bb`。
- summary：`cross_market_vision_weight_acquisition_summary:d48110b3ccc9a71beacc9c4fb55e429d97e2534af3666f2b4a193b968df38e4c`。
- 原429回执：`cross_market_vision_artifact_receipt:abc837d6363bc1e08988aa28ac8186fa179504a4ee7f50cf51f7f95181c295e1`，UTC时间`2026-09-26T17:48:53.236132+00:00`。

冷却02记录：

- 代码commit：`75bab5b03fd9ec30bc7843b899296a573d39cecb`。
- 协议：`cross_market_vision_weight_cooldown_protocol:3bb3d086a713bbc50141c934fee5732fd9d511d3453b3f7d0c29a86883ed29e4`。
- summary：`cross_market_vision_weight_acquisition_summary:e0c83893fdbac493d1b33429e3a9f5639d0f1a1fd9788808bcb63cf1e47b04a8`。
- 登记：北京时间2026-09-27 02:08:11.065280。
- 完成：北京时间2026-09-27 02:09:44.552293。
- 新429回执：`cross_market_vision_artifact_receipt:9a16edc6cae47c8b1cbd2b1c43d994aed9718dba1f100b7d233d38b1186f1f67`。

原始记录分别保存在`cross_market_calibration_cache_20260926/original_evidence_revision_02/vision_model_acquisition_01/`和`vision_model_acquisition_cooldown_02/`。本报告没有修改这些输出。

## 冷却与低速执行核对

登记的not_before精确值为`2026-09-26T18:03:53.236132+00:00`，即北京时间02:03:53.236132，是01原429回执加900秒。

02首个paced GET记录为UTC`18:08:42.938813`，即北京时间02:08:42.938813，比not_before晚289.702681秒，距01的429已过去1,189.702681秒。实际启动满足登记的至少900秒冷却门槛；不是刚过5分钟窗口就立即再次请求。

以下为全部9次HTTP起始及观测结果。时间列均为北京时间2026-09-27；hop 0表示该文件初始GET，hop 1表示跟随官方307后的GET。

| 文件 | hop | paced start | 距上次start秒数 | HTTP |
|---|---:|---|---:|---:|
| README.md | 0 | 02:08:42.938813 | 首次 | 307 |
| README.md | 1 | 02:08:50.148437 | 7.209624 | 200 |
| added_tokens.json | 0 | 02:08:57.540565 | 7.392128 | 307 |
| added_tokens.json | 1 | 02:09:04.429448 | 6.888883 | 200 |
| chat_template.jinja | 0 | 02:09:11.589723 | 7.160275 | 307 |
| chat_template.jinja | 1 | 02:09:19.332085 | 7.742362 | 200 |
| config.json | 0 | 02:09:26.232489 | 6.900404 | 307 |
| config.json | 1 | 02:09:33.353136 | 7.120647 | 200 |
| generation_config.json | 0 | 02:09:42.021479 | 8.668343 | 429 |

相邻start间隔范围6.888883–8.668343秒，全部超过5秒。采用更保守的“上次响应头观测→下次start”口径，8个间隔也全部超过5秒，范围5.003671–5.011628秒。记录与单线程、每HTTP hop间隔至少5秒的设计一致。

这里只核对控制端持久化的预约、dispatch及响应观测时间，不把软件记录当作网络抓包；HTTP预约可能先于实际发送。不过本次9份预约都有对应paced start及HTTP observation，未发现缺失或悬空的配对记录。

## 文件结果及本地内容校验

| 文件／类别 | 状态 | 已验证final bytes | HTTP次数 |
|---|---|---:|---:|
| README.md | DOWNLOADED_HASH_VERIFIED_NOT_LOADED | 43,006 | 2 |
| added_tokens.json | DOWNLOADED_HASH_VERIFIED_NOT_LOADED | 913 | 2 |
| chat_template.jinja | DOWNLOADED_HASH_VERIFIED_NOT_LOADED | 481 | 2 |
| config.json | DOWNLOADED_HASH_VERIFIED_NOT_LOADED | 2,998 | 2 |
| generation_config.json | TRANSFER_FAILED_NOT_REFUNDED，HTTP429 | 0；未发布final | 1 |
| 剩余9项元数据及4项权重 | NOT_STARTED_INTERRUPTED | 0 | 0 |

4项成功文件的清单hash算法均为Git blob SHA-1。只读审计重新计算实际本地字节数、Git blob SHA-1及统一SHA-256，全部与原manifest／成功receipt相符：

| 文件 | Git blob SHA-1 | 文件SHA-256 |
|---|---|---|
| README.md | `bbd87a4cc296c77608f66adfe9411b6c7e84b1e8` | `d2d98f1570e294ae88b05b36f3c32a76f67a50c96933cbafb82788833a30cf8a` |
| added_tokens.json | `3ecaee9890f76c964b4bf550a85293b874b71b87` | `21d196327bf587cb24ec39db1dbe52cd68d243fdde8bc60dff2c867261b703fe` |
| chat_template.jinja | `0b19f45e0cd40b10374f24065639b0c2eee18a22` | `b3e3fa7cdeceec1d3dfe0d17b77724baf3857714e688f3a700261567e96140eb` |
| config.json | `e649dc4968d1a55b93277a3ee38951308c43b7c8` | `32a9a726c8fd4d2386038bb1eab9fd34c6e04cf89c070e44aab346a41d9454e6` |

47,398 bytes是这4个已验证final文件的内容总量，不是TCP／TLS／重定向header总流量，也不是网络计费总量。失败`generation_config.json`的partial为0字节，原样保留，没有重试或续传。

## 429与响应头：观察到什么，未能判断什么

新429出现在`generation_config.json`的hop 0。安全白名单响应头记录为`rate_headers={}`：该次没有可报告的Retry-After／RateLimit／RateLimit-Policy值，因此不能据它给出服务端明确reset时间。

此前8个成功／重定向响应保存了`RateLimit`及`RateLimit-Policy`诊断值，包含`"resolvers"`、`q=3000;w=300`及不同的remaining／reset秒数。例如首个307记录`r=2997;t=52`，config的200记录`r=2996;t=298`。这些响应头不能保证随后的请求必然成功，也不足以确定所有响应来自相同额度桶或解释此次429的触发层。

本次没有观察到403。报告不把429重新解释成token过期、鉴权失败、代理损坏、出口变化或服务器自身网络故障。代码使用相同direct连接配置、未主动切换代理／出口，但本阶段没有查询真实公网IP，不能声称已验证前后公网IP绝对相同。更不能以已有4项成功推断剩余权重可在再试一次后取得。

## 预算、谱系和原01保留

本次核对的02实际文件计数为：5个file attempts、9个HTTP reservations、9个paced starts、9个HTTP observations、5个receipts。request／start／observation的内容ID与protocol／filename／hop／reservation ID相互绑定全部通过；5个receipt内容ID有效，且与summary中的对应完整结果逐项一致。各receipt报告HTTP数之和为9。

02协议保存的三份01父引用——01 protocol、01 summary及原429 receipt——实际bytes与SHA-256仍全部匹配。01 README及added_tokens的receipt也仍与01 summary内记录完全一致；两个原0字节partial仍在，未被02覆盖、续传或删除。

| 阶段 | file attempts | 含redirect HTTP | 验证通过文件 |
|---|---:|---:|---:|
| 01 | 2 | 2 | 0 |
| 冷却02 | 5 | 9 | 4，全部为元数据 |
| 累计 | 7 | 11 | 4个唯一元数据文件 |

两轮均保留失败，不退款、不把旧attempt改成“未发生”。02的新429触发全局停发，13项未开始不是13项新网络失败，也不是已经读取／校验过13个文件。

## 下一步边界

主流程正在请求用户选择有明确权限的后续路径：提供已配置的授权`HF_TOKEN`、提供固定revision且可验证官方来源的完整snapshot，或选择具备真实视觉能力及独立审阅条件的API。任何路径仍需保存固定文件／模型身份、来源与执行预算；配置token本身也不保证解除当前限制。

在该选择明确前，不再进行匿名获取尝试，不自动注册第三轮，不调整代理／出口，不改为未核验镜像，不加载不完整模型。新的认证获取若获准，必须与这两轮匿名结果分开登记，保留旧失败，不能伪装成原请求的继续或预算退款。

本次02总结中的模型加载、GPU进程、依赖安装、PDF打开及语义证书均为0。这些0属于本获取阶段，不否认另一个独立CPU构建阶段的活动。整个实验仍需完整模型资源或替代真实视觉能力、受控能力验证以及实际原文／视觉审阅；仅有模型元数据不能产出全源审阅证书或正式训练价值结论。

## 审计方法

本报告为AI助手对已完成保存记录的一次只读审计：读取02协议／summary／全部9组HTTP谱系及5份receipt；复核精确时间门槛和间隔；对4个小型成功元数据文件重算原hash；检查已绑定01父引用及原receipt／partial留存。没有发网络请求，没有改变实验结果，没有重新运行获取、加载模型、打开PDF或调用视觉／文本API。软件证据核对不是人工签署或财务／视觉语义认证。
