# QA vNext：固定有效支持上的训练表示与类级权重干预预检

日期：2026-09-06。阶段：`finance_qa_vnext_finite_support_training_representation_and_class_weight_intervention_preflight_only`。

本文件记录审计后的实现选择与有界实验；正式物化结果、测试总数和工件身份将在冻结代码后的执行完成时补入。开发时已见过这批历史数据，并已做本地 tokenizer 探测，不声称数据盲确认。

## 1. 审计收口与本轮唯一新增对象

上一轮[冻结模型轨迹有限商测量](finance_qa_vnext_six_session_model_trajectory_finite_quotient_measurement.md)已获外部 `PASS_AS_SCOPED`；没有强制修订，不重开六会话模型接入，不补跑 M01，也不再执行旧资格判定、图投影、十个历史配对或旧商测量控制。

本轮承接用户“参照审计继续实验”，直接实例化：原 Request 条件下的真实准入响应监督、一个固定有限类内物化核、两套只改变类概率的视图，以及可消费的 Token 张量和实际加权 CPU 损失接口。不是仅编写下一轮设计。

新增 Provider 调用、credential 读取、新候选 Runtime、新模型会话、新来源／任务、Student 参数加载、Student forward、Student 参数更新、GPU 作业均为 0；不创建训练或生产 Release，旧主链仍暂停。下文的“训练目标”是可执行数学目标和加载表示，不表示已经训练了模型。

外部审计原文 24,437 bytes，SHA-256 `4df85efb69a45d5fafb6c93a74b077682da9fd1130e0d16ca2ebb28af110a339`。物化时原样保存；其审阅范围是报告证据与数理核对，不冒充对历史工件的又一次源码重建。

## 2. 固定父输入，不再次计算历史有效性

| 输入 | 完整文件数 | 总字节 | 本轮作用 |
| --- | ---: | ---: | --- |
| 原六会话模型 pilot | 785 | 8,312,321 | 实际 HTTP Request、原公开响应、Submission、Receipt、事件、资格和失败历史 |
| 已闭合有限商测量 | 51 | 1,086,642 | 两个 State、五个 Assignment、分区、纠正账本及经验频率 |

父目录均在原位置完整读／哈希，父 Manifest 自身也进入新 `parent_freeze` 的成员列表；不复制父目录的全部字节，不修改历史工件。本轮使用完整父绑定和旧纯记录读取函数，不调用旧 QA／模型 adapter／候选执行器／投影器／比较器。声明的源文件集合不是完整依赖及运行环境闭包。

本轮直接复用的状态如下，A/B 只是本报告简称，不是新的 State ID。

| 类 | 既有正式 State ID | 原 Qualified 会话 |
| --- | --- | --- |
| A | `share_quotient_quotient_state:e28821613cfbbb9cfa893fb96cffce4afd8d51aa05c5abcc80baeb09713c7e24` | M02、M04、M05、M06 |
| B | `share_quotient_quotient_state:fda7bb3c703072097de094c6ec8441ec97cf973190cdb6e4e1588983b0dfa54c` | M03 |

原六会话经验量仍是 `q=5/6`、联合状态频率 `(4/6,1/6)`、成功条件经验频率 `(4/5,1/5)`，M01 保留失败质量 `1/6`。本轮不把训练池分母五解释为总体分母已改为五。

## 3. 监督单元的来源和保留边界

每条正向监督行必须同时满足：属于原 Qualified 会话；有既有 Assignment；原 Receipt 的 `admitted=true`；该 Receipt 与对应原 Request、HTTP 请求、原响应、Submission、event 及会话路径一致。

输入直接取对应已保存 HTTP `body_json` 中的 `messages`，保持实际两个消息及其原 `content`；不是将会话重新拼成多轮对话。目标取同一实际 Submission 中的原始 `raw_public_json` 字符串，并交叉核对 Provider response 的公开内容字节数及哈希；不根据 parsed JSON 重新序列化，也不缩短数值或补 citations。

每行保存原 session／Assignment／State／qualification／session manifest／Request／provider request／provider response／Submission／Receipt／event／source state ID，原 HTTP body 和目标的字节绑定，以及分属 pilot 和 quotient 两根的来源路径。

| 会话 | 正向准入行（1-based 原 turn） | 行数 | 排除项 |
| --- | --- | ---: | --- |
| M01 | 无 | 0 | 全部 12 条，包括 6 条准入中间提交 |
| M02 | 1、2、3、4、7 | 5 | 2 条未准入 |
| M03 | 1、2、3、4、5、10、12 | 7 | 5 条未准入 |
| M04 | 1、2、4、5、6 | 5 | 1 条未准入 |
| M05 | 1、2、4、8、9 | 5 | 4 条未准入 |
| M06 | 1、2、3、4、5 | 5 | 无 |

27 是逐 Receipt 来源重建后再对预期数量的检查，不是先生成 27 个无来源占位对象。实际类型为 11 Action、11 Update、5 Final。另 24 条进入显式排除账本：12 条 Qualified 拒绝加 M01 全 12 条。排除记录不含正向文本目标，权重为零，保留完整父记录引用。

协议纠正的商归约不是训练清理授权。后续准入请求中的 `last_feedback`、accepted Claims、pending Observation、预算计数、parent 与 State 均原样保留。9 条正向单元发生在该会话至少一次拒绝之后，其中 6 条直接携带上一步拒绝反馈：M02 turn 7；M03 turns 10、12；M04 turn 4；M05 turns 4、8。它们不是五条无错误的新轨迹，也不证明去掉反馈后模型仍会作出同样选择。

Host Request、Observation、Receipt 等只可以作为真实请求中的条件上下文，不作为 assistant 正向目标。目标仅包含模型本次原始公开提交；不请求或监督私有推理。零正向权重是本版 imitation 目标选择，不是断言拒绝记录没有研究价值。

## 4. 本地 Student tokenizer 与真实边界

沿用仓库已有配置所指向的本地 `Qwen/Qwen2.5-7B-Instruct` tokenizer；本地配置记录 revision `a09a35458c702b33eeacc393d103063234e8bc28`。不新选或下载模型，不重新验证远端权重，不加载参数。配置文件仅提取 `base_model`、`model_revision`、`max_seq_length`、`max_new_tokens` 四项作引用；旧 optimizer、LoRA、步数或 Release 设置不继承为本轮权限。

本地目录：`/data1/zhuxinrui/models/Qwen2.5-7B-Instruct-a09a35458c702b33eeacc393d103063234e8bc28`。

| 冻结文件 | bytes | SHA-256 |
| --- | ---: | --- |
| `config.json` | 663 | `7463bb0ea78315365e6c6b74de4e73bbcc8359dfb0c5a737584e077d42c0b03c` |
| `tokenizer_config.json` | 7,305 | `5b5d4f65d0acd3b2d56a35b56d374a36cbc1c8fa5cf3b3febbbfabf22f359583` |
| `tokenizer.json` | 7,031,645 | `c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539` |
| `merges.txt` | 1,671,839 | `599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3` |
| `vocab.json` | 2,776,833 | `ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910` |

五文件合计 11,488,285 bytes；只引用而不复制模型权重。模板位于 `tokenizer_config.json`，2,507 UTF-8 bytes，SHA-256 `cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f`。不存在另一份获授权的独立 `chat_template.jinja`。额外模板／special-token sidecar 会被拒绝，不能悄悄改变加载结果。

加载显式 `local_files_only=True, token=False, trust_remote_code=False, use_fast=True`，实际类为 fast `Qwen2Tokenizer`。运行依赖版本随 binding 保存；transformers 可能导入 torch，这不等于加载模型或执行 GPU 作业。

最大序列长度固定 24,576，不截断。模型 `config.json.max_position_embeddings=32,768` 且没有 `rope_scaling`；tokenizer 自报的 131,072 不作为模型上下文上限授权。运行模板得到：原 prompt + 完全相同的 target + `<|im_end|>\n`，尾部两个 Token 不承担本版监督。

边界检查逐行验证完整渲染字符串、前缀 Token ID 精确相同、fast offsets 不跨 prompt／target／suffix 边界、target offsets 连续覆盖原字符区间、目标 Token 解码恢复原 UTF-8 字节，以及无内部 special token。若超长、边界跨越或内容改变则拒绝，不静默丢 Token。模板没有提供适用的 automatic assistant mask；本轮没有伪称使用该 API。

`labels[t]=input_ids[t]` 仅在原 assistant 内容区成立；prompt、角色头、EOS、尾换行和 padding 均为 `-100`。每条行先无 padding；共同批次再向右补齐。因果损失位置 `t` 预测 `labels[t+1]`，只 shift 一次。

## 5. 固定类内物化核与 P/Q

有限核只在原五条完整 Qualified 轨迹上定义：A 内四条各 `1/4`，B 内 M03 为 `1`。`ψ` 共同冻结原请求／响应选择、监督范围、tokenizer/template、内容 mask、行序、padding 和轨迹内 Token 归一化。没有新鲜轨迹生成；增加 M03 权重不会增加 B 内独立实现数。

P 显式选择原经验条件分布 `(4/5,1/5)` 为基准，不将经验频率解释为最优权重。Q 采用 `(1/2,1/2)` 为概率质量干预控制，不是覆盖先验 `r`、Novelty 更新或效用证据。

| 轨迹 | 类内核 M | P 轨迹概率 | Q 轨迹概率 |
| --- | ---: | ---: | ---: |
| M02 | 1/4 | 1/5 | 1/8 |
| M03 | 1 | 1/5 | 1/2 |
| M04 | 1/4 | 1/5 | 1/8 |
| M05 | 1/4 | 1/5 | 1/8 |
| M06 | 1/4 | 1/5 | 1/8 |

每条原轨迹所有准入目标合计 `T_j` 个实际监督 Token。每个属于该轨迹的目标 Token 系数为 `ω_j=π(z_j) M(j|z_j)/T_j`。实际总损失是 `Σ_j ω_j Σ_target NLL`，不是按 27 行、全体目标 Token 数或当前 batch 大小再求均值。权重以约分有理数保存，真正应用时为 CPU float64 系数张量。

P/Q 共用完全相同的 27 行顺序和一份 `input_ids/labels/attention_mask/target_mask` 基础 NPZ；视图只携带类别、轨迹及逐行系数，另保存实际因果位置系数 NPZ。目标不复制成新样本，P/Q 也不分别重分词。

## 6. 损失组装控制与独立检查的准确范围

`aggregate_loss` 接收外部提供的 unreduced 逐 Token NLL，并在 CPU 依据 `labels[:,1:]` 与对应系数做加权求和。当前没有 Student 来产生 NLL；以后接入真实模型、微批次重采样或 optimizer 需要另外定义协议。

两视图各检查 9 个可控损失：全 1、两个 class indicator、五个 trajectory indicator、随原行号和因果 Token 位置变化的有理数损失。每项同时比较完整 batch 与固定系数分块求和，共 18 个 probe；预期值以 `Fraction` 计算，float64 绝对误差容差 `1e-12`。非目标位置刻意设置 NaN，必须由 mask 排除；活动位置的 NaN、负 NLL 或非法系数会被拒绝。该分块恒等式不是任意随机优化过程等价性。

独立检查器不调用 text exporter、tokenizer、kernel/view 构造器、collator 或 loss producer。它通过原来源验证检查文本，使用已绑定的原分词记录逐 Token 检查 mask／labels／因果边界，逐数组检查右 padding，并从既有 Assignment 和实际目标 mask 总数独立重建有限核及精确 P/Q 质量。独立检查器不声称独立重分词、独立解码、重编码 NPZ 或执行 loss 函数。

完整工件验证另外使用同一已冻结 tokenizer 对相同 27 行重新分词，逐完整分词记录核对；解码基础 NPZ 后交独立检查器；同一冻结 loss/control driver 重算实际损失和隔离控制。这不是重做旧商测量，也不是新增模型样本。

13 项本轮隔离控制覆盖：补写目标字段、未来 Request State 替换、Qualified 拒绝晋升、M01 准入中间步骤晋升、27 行等权、全目标 Token 等权、类内核变化、Q 文本 identity 改变、Q tokenizer identity 改变、prompt 入 mask、EOS 入 mask、padding 被监督、因果 labels 二次 shift。控制保留确定输入变更与失败原因；不增加正式正向池、State 或模型样本。不会重跑上一轮 12 项商测量控制。

## 7. 工件与可复现性

实现位于 `src/trusted_synthesis/experiments/qa_reasoning_share_training_preflight/`。正式目录预计为：

```text
artifacts/qa_reasoning_share_training_preflight/
  finance_qa_vnext_finite_support_training_representation_and_class_weight_intervention_preflight_v1_20260906/
```

工件保存原审计／当前指令、授权、完整父绑定、实际 Git 源身份、tokenizer binding、表示契约、27 行完整文本 dataset 与 JSONL、Token 记录、共用基础批次、有限核、两视图、两系数 NPZ、质量诊断、文本验证、独立验证、18 probes、13 controls、运行范围、Gate、报告和持久化／Manifest。

新根与文件只创建不覆盖，采用 file fsync 后 directory fsync。源身份、表示契约、tokenizer 和父输入先持久化，再导出训练表示。NPZ 使用固定顺序、dtype、ZIP 时间戳与压缩设置，不包含 pickle。Manifest 自排除并记录所有其它成员的路径、字节数和哈希。

运行保护阻断网络连接／解析、`.env` 和 Hugging Face credential 文件、常见模型权重文件打开及 CUDA lazy initialization；记录实际尝试计数。加上有界调用路径与测试，支持本轮零执行声明，但不冒充完整操作系统沙箱证明。

## 8. 科学解释与后续边界

预检成功可支持：固定同一任务、既有 Assignment 和 `ψ` 时，P/Q 的类概率质量已准确作用到真实监督 Token 和可消费损失接口上，不因拆成 27 行或轨迹长度不同而隐含改变。

它不支持：Q 比 P 更好、B 的 Contribution 为正、罕见状态更有价值、VTDO 已有效、跨任务泛化提高，或 Student 已获训练 Release。原有 `q` 和经验频率不变。这里只有一个任务和 B 的一个原有效实现；控制与重建次数不是独立样本数。

下一轮若开展 Student 对比，仍需明确受益模型参数、优化协议和独立评价目标；在这道训练题上复现答案不能作为泛化收益。当前不擅自开始该阶段。
