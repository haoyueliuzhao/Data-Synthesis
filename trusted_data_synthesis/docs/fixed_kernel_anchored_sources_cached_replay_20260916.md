# 同一虚拟点、同一已采样token的缓存回放修复

状态：`PASS_AS_SCOPED_CACHED_LOGP_CONTROL`。完成：`2026-09-16T02:46:57.588736+00:00`（UTC）。
报告：`anchored_sources_cached_replay_report:61848b2ad90b298e4b682b0b2b2e3983ffec8a1b8fc49741fbbd9f3629a5271f`；冻结代码：`2a80f9a0b187b67e9a6f2b4fdef49068403bfd1a`。

## 执行范围

只使用原GPU检查保存的两段输出，2+8个token。未新增model.generate、随机回答、
金融评分或optimizer.step。旧整段回放的长上下文失配报告保留，没有改写为通过。
修复重建原诊断梯度和虚拟参数并要求摘要完全一致，随后采用同样的prefill/逐token
KV路径；缓存不detach，反传保存张量移至CPU，不替换概率、不放宽容差。

| 上下文 | 输入token | 已有输出token | 最大logP差 | 容差通过 | 梯度有限 |
|---|---:|---:|---:|---|---|
| synthetic_reply_only_OK | 26 | 2 | 0 | True | True |
| task_61edaeef92f176e7e779a53c74468212b487879794b81c92cda6ec99ae54d7f4 | 12219 | 8 | 0 | True | True |

实际耗时210.09秒；CUDA reserved峰值19.289GiB；真实参数、optimizer、grad、mode及RNG保持不变：`True`。
原atol=1e-6、rtol=1e-5不变；这是所列token的检查，不是误差上界证明。

## 证据边界与后续

通过时只说明该反例在同点同token的缓存路径得到修复；不证明所有长序列或所有
360条反馈均已具备生产条件。失败时保留实际错误，不自动重跑或改阈值。
CPU offload短输出结果不可直接外推到24,576上下文×2,048输出，后者的缓存图
内存与调度仍需生产适配。完整反馈生成/封存后独立评分、全总体G与pullback接线、
最终训练日程尚未完成整体生产准入。自适应A、B及确认均未由本控制放行。

当前分布实验仍保留原alpha0；没有新的anchored训练收益结论。
新增必要CPU控制累计8项通过，未重复旧157项测试或既有1,620会话扫描。
