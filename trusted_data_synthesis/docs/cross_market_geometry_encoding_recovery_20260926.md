# 几何编码失败：仅缓存的无损保存修订

## 范围与用途

本修订是用户已授权原文补证中的缓存保存工作，不新增原PDF读取，不提高原440次预算，不替换原几何失败摘要，也不释放下游财务资格或模型评价。实现为`cross_market_geometry_encoding_recovery_20260926.py`，正式运行前提交冻结并登记，输出独立放在`original_evidence_revision_02/geometry_encoding_recovery_01/`。

唯一输入集合是原正式几何摘要列出的全部4份`UnicodeEncodeError`失败：HK00857的2019、2020、2021、2022报告。不能按恢复后的财务值择取文件，也不能补读原PDF。每份缓存派生最多1次，合4次；未完成预约不得退款重试。15份图像目录容量失败不属于本修订。

## 问题与无损表示

原几何采集器已经完成这4份PDF的遍历和原空文本页渲染，但在最终JSON按UTF-8编码时失败，Python异常repr保留了整个待编码JSON。只读诊断发现282个孤立surrogate码点全部位于141个图像目录`cs-name`字段；金融词框/文本没有此类码点。不能据此把这些字符改成空串或替换符。

恢复程序仅接受有限大小、严格形状的异常表达式，以AST常量读取参数，不执行任何表达式。随后核对异常repr、待编码JSON的规范重建、固定页选择及完整页序、计数/上限、已有PNG的路径/hash/字节数/尺寸；任何不一致保持失败。

新的payload采用`ensure_ascii=True`、有序键、紧凑分隔符、禁止NaN的JSON字节表示，保存surrogate为ASCII转义，读取后对象完全往返。它不是修改旧UTF-8编码规则，也不是将不合法Unicode强制解释为正常金融文字。新元数据使用独立记录种类，绑定原失败记录、原几何协议/摘要及payload字节hash；不得伪造旧几何记录的身份或直接写入旧`geometry/documents/`。

## 对下游的影响

可保存的缓存内容为69个几何页、1,180页覆盖目录、16,413词和19幅已有PNG；正式恢复结果与此前只读诊断计数一致。原几何完成状态仍是421成功/19失败；4份缓存派生成功也不意味着原440份几何已完整。

本程序不生成财务事实、任务、gold或来源审阅证书，不调用API/模型、不评分/训练、不使用GPU，不打开或哈希原PDF。恢复4份后仍有15份缺少几何，且冻结下游要求全部440份完整；因此不会通过缓存恢复自动解除阻断。原图像容量问题如需重新采集，必须另行登记有限新增PDF预算。

## 实际执行结果

实现冻结前22项针对性合成测试及Ruff通过，覆盖严格AST、无损往返、错误surrogate位置、页/图不一致、缓存预算不退款、原文件隔离以及复用时payload缺失/篡改拒绝。没有运行真实PDF或模型测试。

实现冻结于`8ea0b5aa36`，2026-09-26北京时间22:00:04登记，22:00:59正式完成。4次缓存预约全部成功，状态`FOUR_CACHE_PAYLOADS_PRESERVED_NOT_ADMITTED`。

- 协议：`cross_market_geometry_encoding_recovery_protocol:3465cc0a3b96a5f2e5bf2e088078b2d7a2dede1aec1c65646e278a7b61b84ef4`。
- 完成：`cross_market_geometry_encoding_recovery_completed:a8733941b6537077f69f2b80d4a4db657d5e23dc51d64eef8218dd0b482532c6`。
- 实际69个几何页、1,180页覆盖、16,413词、19幅已存在PNG；141字段中的282个surrogate码点原样保存，无删改/替换字符。
- 新payload保存在`geometry_encoding_recovery_01/payloads/`，逐份来源/新hash/编码及码点位置保存在`documents/`，4次预约及完成摘要独立保存。
- 原几何协议、完成摘要和4份失败文件hash均核对未变；原421／19状态不变。
- 新增原PDF读取、网络、API、GPU、模型调用、评分和训练更新均0；`geometry_complete=false`、`downstream_authorized=false`、`evaluation_started=false`。

[正式完成摘要公开副本](../artifacts/qa_vnext_fixed_kernel_value/cross_market_calibration_20260926/public/geometry_encoding_recovery_01_completed.json)保留原内容身份及逐份恢复结果引用；仅JSON显示缩进不同。它不是金融准入证书或完整几何通过证书。后续仍需处理另外15份容量失败，并履行原财务/完整来源审阅门槛。
