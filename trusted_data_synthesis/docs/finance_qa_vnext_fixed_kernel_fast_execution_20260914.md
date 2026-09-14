# 固定材料核的执行性能修订

## 已完成的科学输入

预算修订后的完整采集报告为 `material_generation_report:3a2b2255080b5a7b4ef91b1bc9338f92fccef091364031c3e9bc90a821c0f8b2`：10240个原slot全部结束，新增272个session、1401次HTTP、6323646 Token；9968个原finished保留，原未知请求不重试。之后24 CPU完成10240个材料结果，9418个编码包约3973192480字节。

原实现实际生成的材料门为 `material_gate:16d9491e7ca7b6b506bc5308b67dc9de5b2958e94cba0d2944c5b9395f23e763`，材料与剂量门均PASS；共同S=120，质量移动量1/10，空任务池0。正式train原包A=3547、B=3529；每epoch完整上下文序列Token分别84347252与83636655，目标Token分别991944与982088。上下文计算量不等于损失目标数量，实际训练吞吐/时长必须以真实运行测量为准。

正式核ID为 `fixed_kernel:f67d9edd0712d87d6d63d6e9535f8ff2db677cb81c884780afc8315c1d15c729`。本修订必须与这个**已实际由原实现算出的全量ID**相等，不能只凭小样本测试或摘要声称等价。

## 已观测的开销与限制

用户明确要求“减少冗余校验，尽快实验”。原完整材料核的组装在单核上持续处理，直到2026-09-14 01:01:55 UTC才写出材料门；这不是新增采集或模型训练。

仅做了一次175242字节、4行、9426序列Token的独立单包基准：deepcopy约7.91ms，canonical JSON编码2.50ms，SHA256本身0.166ms，原checked约10.12ms，不复制的同schema/content-ID校验约2.18ms。选定包ID完全一致。该单样本不能充当全量ETA，也不是对生产进程的栈采样；但源码明确显示hydrate、outcome/package校验、kernel构建，以及prepare/run/每个训练worker会重复深拷贝或重建同一材料。

## 执行修订的边界

在独立 `codex/fixed-kernel-fast-execution-20260914` 工作树实施，旧完成批源码与报告不改。只优化身份校验、不可变数据搬运及验证结果复用；保留公共record对可变输入的复制隔离语义。所有材料从既有原件读取并按内容SHA绑定，不再次请求Teacher，不重新tokenize，不变更train/sealed角色、任务概率、目标mask、方法/细状态分布或包保留规则。

原consumer数值计算、评估解码器、源工具运行时与语义规则保持源码字节一致；训练的Qwen/LoRA/优化器、400次Full更新、SEEDS、A三臂/开发选择/有条件B确认流程保持原科学条件。新执行freeze及独立performance authority记录实现变化和全量kernel-ID相等，不冒充原未修订源码执行。

2026-09-14 01:04:33 UTC，原材料门已PASS且旧Student execution_freeze/execution_started均尚未生成时，仅对主CPU协调进程3101807发出可逆SIGSTOP，以避免两条工作流重复训练。其独立材料封存子进程未受信号影响，原采集/编码产物不改；暂停记录保留在旧runtime。新工作树仅复制已完成package/outcome及必要metadata，19672文件、4011768198字节，零重采样与零新编码。

只运行与身份等价、不可变共享、验证receipt和执行入口有关的小范围控制；不重跑全套财务评估、349项旧控制或GPU工程检查。只有真实全量kernel-ID核对通过且正式执行freeze提交后才启动GPU。实际正式训练、确认效果及最终推送状态在结果到达后记录，不预判科学正效应。
