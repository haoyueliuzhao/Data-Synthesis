# 固定材料实验：提高预算后的独立复评实测记录（2026-09-15）

本记录是事后预算敏感性诊断，不替换原实验结果，不重新选择方法方向，不授权 B 训练。

- 计划：`budget_reevaluation_plan:e4a610ccf93a3f6fb05f9463bf935caddf22486be460c6a0cf200599ac29c918`。
- 结束状态：`COMPLETE_PILOT_ZERO_QUALIFIED`；时间：`2026-09-15T10:08:34.107513+00:00`。
- 旧预算：每会话 32 次响应 / 32 次工具调用，每次 2,048 新 token，序列上限 24,576。
- 新预算：每会话 64 次响应 / 64 次工具调用，每次 4,096 新 token，序列硬上限 32,768；不裁剪历史，不自动续写或重试。
- 模型：原 A 阶段 9 个最终检查点不变；greedy、neutral、工具与评分语义不变。
- Pilot：3 个公开任务，三组各 1 题；基于预先固定 salt 与任务 ID 排序，尽可能不同公司，不依据旧 outcome 选样。完整 27 会话至少出现 1 个财务合格结果，才自动补充其余 177 题 × 9 模型；pilot 会话不重生成。
- Pilot 时限：首个 GPU worker 实际启动后 90 分钟。超时仅终止本诊断自己的新 worker，缺失或截尾结果不冒充完整结果。

## 实测汇总

| 指标 | 原预算（复用既有记录） | 提高预算 |
|---|---:|---:|
| 计划会话 | 27 | 27 |
| 已完成并评分 | 27 | 27 |
| 识别到 Final | 0 | 0 |
| 财务合格 | 0 | 0 |
| 缺失/截尾 | 0 | 0 |

原预算终态计数：`{"response_budget_exhausted": 27}`。

新预算终态计数：`{"response_budget_exhausted": 27}`。

逐模型、逐任务配对结果与生成 token / callback 等资源计数见独立输出目录的 comparison 与 report。实际新 worker / phase 墙钟耗时见 jobs 与 generation_phase；不重复扫描旧 callback 大文件来构造硬件条件不可比的耗时比。

## 结论边界

若完整 pilot 财务合格数为零，只能说明这一固定小样本上提高到当前预算未恢复财务合格输出，不能证明更高预算普遍无效，也不能证明财务计算均错误。若 pilot 不完整或超时，结论是不确定而非零效果。若通过门控并完成 1,620 会话，仍属于改变评估预算后的独立结果，不等同原注册实验的确认试验，更不能单凭本诊断声称 VTDO 有效。

## 保存和发布范围

所有原实验文件保持不变。新原始生成文本、token ID、callback 收据、会话、manifest 与评分附件保留在本地 `/tmp/data-synthesis-fixed-kernel-parallel-tail-20260914/trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/budget_reevaluation_20260915`。远端仅提交计划、模型身份、逐模型 generation / score 汇总、配对比较、进程收口、总报告与本说明；不推送每个 callback 的大 JSON / token 原文或逐文件 manifest。远端汇总引用的原始文件仅保存在本地，不表示全部原始内容已发布。
