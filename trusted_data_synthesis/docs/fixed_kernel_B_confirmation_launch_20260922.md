# B 主确认实验：登记、准入与实际启动记录

本文是 [预登记说明](fixed_kernel_B_confirmation_protocol_20260922.md) 的实际执行补充，不改变已冻结的候选、任务、数学公式、统计判据或预算。时间均注明时区；本轮尚无 B 最终效应结论。

## 1. 已完成的必要核验与代码冻结

- 全部新增 B 相关合成 CPU 测试：93 项通过，耗时 9.28 秒；ruff 通过。
- 测试包含真实 Adam/checkpoint 的 CPU 序列化与恢复、共享前缀依赖、训练与生成预算、响应回放中断恢复、720 确认隔离、精确配对 bootstrap、错误模型评分拒绝和发布失败恢复。测试通过不替代真实 GPU 执行结果。
- 科学实现提交：`0e8770c40b0f88128bf48c8e5e5fc0b7baad0564`；启动前已推送 `origin/main`。
- 原 A 数学实现和既有结果没有修改；B 使用新执行模块，原失败与恢复记录保留。

## 2. 实际登记与公开输入准入

2026-09-22 22:12:47（Asia/Shanghai，UTC 14:12:47），新协议已冻结：

```text
B_confirm_protocol:0dba5b5625fbf37d7e4f93fc0b7636cba1df66a1fec611e6af67d6a5710bbe1a
```

2026-09-22 22:13:09，公开输入编译完成：**720/720，通过，编译失败0**。此操作只使用确认题公开正文和公开来源；私有 bundle 读取为0，没有模型调用，没有私有充分性检查，没有生成或评分确认答案，也没有删题或修题。

公开视图身份：

```text
source_view_manifest_v2:d8dec4f25c7110eba28ccc9da58b0fd60f7246cd0ce594a7092ccc54b160aa00
```

元数据再次确认：确认集71个CIK，dev180共12个CIK，二者交集为0；不将其扩推为与所有上游材料完全独立。

原始证据统一保存于：

```text
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/
qa_vnext_fixed_kernel_value/delayed_C_B_confirmation_cache_20260922
```

对应 `protocol.json`、`public_registration.json`、`audit_directive.txt`、`confirm_views/manifest.json`、`confirm_views/admission.json` 和 `implementation.json`。科学协议与公开编译代码绑定冻结提交及源码 SHA；后续进程拒绝静默修改这些源码。

## 3. 实际启动

2026-09-22 22:14:03 启动独立 watchdog，PID `3444161`；coordinator PID `3444224`。22:14:09 首次并行派发三个真实共同前缀：

| 工作单元 | 首次 GPU | 首次 worker PID | 目标 |
| --- | ---: | ---: | --- |
| B_prefix_11 | 7 | 3444243 | B 的真实 π₀ 训练0→200 |
| B_prefix_29 | 0 | 3444249 | B 的真实 π₀ 训练0→200 |
| B_prefix_47 | 3 | 3444263 | B 的真实 π₀ 训练0→200 |

PID/GPU 是启动时观察，不是永久分配；自动恢复可能更换 PID 和 GPU。22:14:29 首次心跳显示三个前缀均为 attempt1、无已记录科学失败，当时尚无提交训练步。基座权重加载已在各 worker 日志完成。

22:16:27，seed11 的第1个真实更新完成并原子保存。22:17:23 对该完整 checkpoint 做 CPU 读取核验，参数/Adam 快照与游标一致，文件30,567,387字节：

```text
optimizer_binding:a40f93b264e12746592fa0c434ed6f09f4b5e559b0925016f76bc1f584cdff03
optimizer_update:839151cdb03f55a1ed27b072a93c895396501d8baa7d6e864efc49f349392224
```

该核验只确认首步训练与完整保存链路已实际工作，不证明其余步骤或后续阶段已完成。该时点seed29/47仍在第1步，不能按GPU进程存在推算为已完成更新。

注意：原始 `heartbeat.training_steps` 对尚未启动的尾段显示注册起点200，这只表示尾段日程范围从200开始，**不表示这些尾段已执行200步，也不表示共同前缀已经完成**。实际物理进度必须按 `jobs/*/updates/*.pt` 的已提交保存点、相应 JSON 和完整报告判断；预算 reservation 是尝试计数，不能当作成功更新数。

## 4. 持续执行与审计边界

已启用逐训练步完整保存、逐反馈响应保存、逐会话/评分 case 提交、有限资源重试和持久化调度。机器重启后的自动拉起不在本轮承诺内；数据盘保存点仍保留。数值、材料、源码或评分身份错误触发停止，不自动扩充预算或改变科学条件。

当前执行目标仍是三个共同前缀、六个唯一step400模型、1,080反馈及4,320确认会话。六模型全部确认生成完成并退出生成worker、建立全局seal后，才开启确认私有评分。未开展A辅助确认、B末态dev评测或机制消融。

本记录不提供根据模型加载速度外推的完成时间。真实吞吐、资源中断与长上下文生成尚需实测；不能把“已启动”写成“B效果已确认”。最终是否确认正向效果只按预登记CIK配对区间判据判断。
