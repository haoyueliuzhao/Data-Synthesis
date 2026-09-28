# FinQA 五臂 Experiment 1–3：执行设计与 CPU 准备（2026-09-29）

## 状态与范围

本次新增 `finance_research/v6_training_plan.py`，恢复原五臂总纲的执行设计、固定日程和材料准入检查。它不是训练器，不启动模型、API、GPU、评分或优化器。这里没有 Experiment 1–3 的真实训练结果、性能结果或正向结论。

依据是用户提供的《下一轮：同一真实推理轨迹核上的五臂实验》（附件 `a8d52978-a220-40a7-abee-ae7d084d7f01/已粘贴的文本.txt`），已完整阅读。该文中的次数是待登记执行剂量，不是已经执行的事实。本模块也不恢复撤销的作者程序脚本或单程序 SFT。

当前若没有完整材料，`build_execution_plan(..., material_claim=None)` 给出 `BLOCKED_MATERIAL_CLAIMS`。无论是否提交结构完整的材料声明，`execution_admitted` 永远为 `false`：真实执行还须核验原工件字节、来源、角色、Student 编码及资源登记。用户授权推进其他实验不等于伪造已具备材料。

## 五臂与精确时点

种子固定 11、29、47；每个 seed 共享真实前 400 步、完整模型/Adam/RNG/任务日程游标。所有最终模型拥有 2,000 步有效历史。

| 条件 | 0→400 | 400→2000 | 外层更新 |
|---|---|---|---|
| Static | r | r | 无 |
| Manual+ | r | 固定归一化 `r·2^χ` | 无 |
| Manual− | r | 固定归一化 `r·2^(−χ)` | 无 |
| C-only | r | C 自动更新 | 400、800、1200、1600 |
| Full | r | C、N 自动更新 | 400、800、1200、1600 |

Manual±不读 C、Student NLL 或未来成绩；不等于反方向机制控制。χ=1 须有证据的实质核验/修订及其后果，工具次数或冗余验证不能造出 χ。单状态和只有一个粗组的任务保持原分布，不人工制造状态。

唯一最终评价 checkpoint 为 2000。600 和 1000 是预定机制诊断中间点，不用于挑选最终模型。之前某项诊断没有正收益，不构成删除 seed、改主候选或停止其他已登记分支的理由。

## 五任务日程和监督

`build_task_schedule(original_task_ids, seed)` 要求原顺序的 1,000 个唯一任务 ID。使用独立 `random.Random(seed)`；每遍从原名册的新副本洗牌，分为 200 个完整五任务 batch，十遍共 2,000 次更新。返回具体 batch 列表和内容 hash。同 seed 五臂绑定同一份日程，不随观察结果变更；准备阶段能生成日程，但不能据此声称训练已经发生。

原始 Qwen2.5-7B-Instruct 基座冻结 BF16；新 q/v LoRA rank8、alpha16、dropout0.05，LoRA/Adam FP32；AdamW lr=1e-4、betas=(0.9,0.999)、eps=1e-8、weight_decay=0，常量学习率、无 warmup。完整五任务累积后 clip1、更新一次。

所有共同合格原包保留，`μ=1/1000`，`r(z|x)=n_xz/n_x`。同状态多条原轨迹是类内实例，不是新状态。包损失为被批准 R/U/动作/Final/登记 EOS 的总 NLL 除以全包 `L_P`；系数为 `π/(5 n_xz L_P)`，不再次除以 batch size，也不逐层重归一。工具观察只作输入；撤回错误留在完整上下文，目标为零。五臂采用同一 mask。完整 Student 上下文上限 24576，不截断或按长度丢包。

## 真实工件共享只能按证据成立

400→800 的 C-only/Full 共享只是条件性节省，不能预填。`assess_400_800_sharing()` 对模型参数、checkpoint、Adam、训练 RNG、日程/游标、共同材料/编码/mask、prior、更新后 π、G/gJ/C、700条反馈生成封存等声明 hash 逐项比较。缺失或不同即不满足共享条件；奖励计数相同没有替代作用。

该函数仍是声明级检查，不打开或验证文件，所以不会自动减少预算。step800 的 N 局部比较须来自同一真实 θ/Adam/π/G/gJ/C 和训练 RNG；若同点证据不成立，就不能把不同模型点之差称为 N 的同点干预。1200/1600 在各分支自己的真实状态重算 G、反馈和 C。

## 反馈、机制和评价剂量

每个自动臂每个外层点固定 350 题×2 repeat=700条反馈；全部生成封存后评分，分母固定 700。代理/G 计算关闭 dropout，真实训练保留0.05。反馈使用真正本地 `TokenReceipt` 的实际采样 token/logP，包含成功轨迹中的错误和恢复，不套 SFT 正向 mask；API 离线编码不冒充反馈 token receipt。全部反馈奖励为零则保持当前 π，不追加采样或靠 N 单独移动。

- C 方向：共同400→600，Static、q⁺、`2r−q⁺`；反方向新增每seed200步、共600步，不是 Manual−。120题×3方向×3seed×(2随机+1greedy)=3240会话。
- N 同点：800→1000 的 C-only/Full 预定分支，120题×2条件×3seed×3 repeat=2160会话。无额外主训练分支；N未改变分布应报告未激活。
- 最终 dev：15最终模型加一次Base，各883题greedy，共14128会话。主比较Full−Static，次比较Full−C-only，Manual±分别对Static；Static−Base仅为普通学习诊断。

| 计划量（不是实际执行量） | 保守 | 同点共享经真实核验后 |
|---|---:|---:|
| 15模型有效历史步数 | 30000 | 30000 |
| 核心物理SFT步数 | 25200 | 24000 |
| 反方向机制新增步数 | 600 | 600 |
| 随机反馈会话 | 16800 | 12600 |
| 最终dev会话 | 14128 | 14128 |
| C/N机制会话 | 5400 | 5400 |
| 本地会话合计 | 36328 | 32128 |
| 每会话最多32次生成的上界 | 1162496 | 1028096 |

未填实际材料 Token、峰值显存、GPU 小时或完工时间；这些需要真实材料和资源测量。Probe/语义审阅继续单独计入原有限费用账本，不因新计划重置额度。后续API模型仍只允许 `deepseek-flash`。

## 材料声明检查：不是另造材料格式或授予启动权限

`assess_material_admission()` 读取一个纯函数参数 wrapper，而不要求未来材料迁移到新 artifact schema：

- `inventory_producer="v6_decomposed_review.inventory"`；`inventory={record,file_sha256}` 保留现有无 schema 的库存汇总。
- `resolutions[task_id]={record,file_sha256}` 使用现有 `v6_decomposed_pair_resolution.v3`，或新的 `v7_decomposed_pair_resolution.v1`。
- `encodings[original_slot_id]={record,file_sha256}` 使用现有 `v6_student_encoding.v1` 或 `v7_student_encoding.v1`。

核对原1000名册、全部8000槽被保留和评估（不意味着8000槽全部合格）、登记审阅分母与完成数、每题至少一个共同合格原包、整题Mapper完成、共同合格原包集合无遗漏、mask双审一致、逐包编码覆盖精确一致、episode/mask摘要绑定及完整正向Student编码。任何缺题、缺包、未知schema、未编码、截断或缺hash都阻断；不退回165/54等子总体，也不混接独立批次的成功材料。

`r`由保留原包数重建为精确有理数字符串。单状态题自然得到1，不删去这些题。库存原记录的 `Student_encoding_complete=False` 是其封存时事实；之后另产生编码，不要求改写旧库存使该字段变成true。

`claims_structurally_admitted=True` **仅表示提交声明在这些边界上自洽**。模块不验证所指文件的实际字节，不重新做语义资格，不检查完整token数组；输出始终带 `claim_validation_only=True`、`actual_launch_requires_artifactverification=True`、`execution_admitted=False`。真实材料存在、文件 hash 正确及模型调用结算等事实仍须由后续加载/启动步骤确认。CPU测试中的材料声明是显式合成fixture，绝非8000条真实合格材料或训练结果。

## 后续范围

Experiment4数学/零模型分布计算可独立推进，但不能替代真实闭环结果。Experiment5保持独立下一批：Full、Hierarchical 0.3/0.5/0.2、Tool-only、Final-only；固定同材料、历史、mask及π=r，另行登记。不自动展开核心消融全因子组合。public test仅预定Static与Full各3seed、1147题，共6882会话，候选和统计方案冻结后另行执行。
