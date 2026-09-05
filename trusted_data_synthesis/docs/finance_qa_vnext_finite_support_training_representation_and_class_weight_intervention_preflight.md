# QA vNext：固定有效支持上的训练表示与类级权重干预预检

日期：2026-09-06。阶段：`finance_qa_vnext_finite_support_training_representation_and_class_weight_intervention_preflight_only`。

本轮已完成有限支持上的训练表示与类级权重干预预检：真实来源的 27 条准入响应已导出、分词并形成可消费 CPU 张量，固定类内核下 P/Q 的目标 Token 质量分别实现 `(4/5,1/5)` 与 `(1/2,1/2)`。98 项测试、13 项隔离控制和 18 项受控损失检查通过。没有 Student 参数加载、forward 或更新。开发时已见过这批历史数据，不声称数据盲确认。

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

实现位于 `src/trusted_synthesis/experiments/qa_reasoning_share_training_preflight/`。正式目录为：

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

## 9. 正式执行结果（不是后续计划）

### 9.1 冻结顺序、输入不变与运行范围

正式物化前完成源码提交 `065501db40d5088c805e4924184062e57b617206`，tree `145aa15d11e85ca0e660fb1bfd439b3254dee8d2`。正式运行之后没有再修改这 10 个实现文件；其声明成员总计 124,177 bytes，六个引用文件总计 135,121 bytes。开发单元测试中的 source authority 是明确标注的 isolated test-only authority，不冒充真实执行前 Git 冻结；本次正式 CLI 则核对真实 commit/tree/blob 与当前字节。

正式执行的网络、credential、模型权重打开和 CUDA 初始化尝试计数均为 0，`CUDA_initialized=false`。CPU intra-op threads 固定为 8，退出后恢复原线程数。实际环境 Python 3.12.13、torch 2.7.1+cu128；CUDA 版 torch 的安装不表示本轮使用 CUDA。tokenizer 依赖为 transformers 5.14.1、tokenizers 0.22.2、Jinja2 3.1.6、huggingface-hub 1.25.1。

原 785 文件 pilot、51 文件商测量目录及本地 tokenizer/config 均保持不变。新运行没有重算原资格或商关系。正式 `materialize` 执行一次，其内置 `validate` 对同一组已保存监督单元重新分词并复核，不增加统计样本。

### 9.2 实际 Token 数和损失系数

27 个目标原始公开字符串合计 **30,938 UTF-8 bytes**；实际监督 Token 是 **15,939**，两者不可混用。逐轨迹的实际分母与施加系数为：

| 原轨迹 | 准入行 | 实际目标 Token T_j | P 每目标 Token 系数 | Q 每目标 Token 系数 |
| --- | ---: | ---: | ---: | ---: |
| M02 | 5 | 2,812 | 1/14060 | 1/22496 |
| M03 | 7 | 4,691 | 1/23455 | 1/9382 |
| M04 | 5 | 2,793 | 1/13965 | 1/22344 |
| M05 | 5 | 2,817 | 1/14085 | 1/22536 |
| M06 | 5 | 2,826 | 1/14130 | 1/22608 |

全体输入 prompt（含真实可见 Host 条件内容和角色头）共 352,876 Token，目标内容 15,939 Token，模板 EOS／尾换行共 54 Token，因此原始完整序列共 368,869 Token。单行完整长度范围 **12,716–15,110**，低于上限 24,576；最大行仍有 9,466 Token 空间，没有截断或丢弃监督单元。

实际基础批次 shape 为 `[27,15110]`，共 407,970 个位置；右侧 padding 为 39,101 个位置。只有 15,939 个位置具有正向目标 mask。prompt、角色头、suffix、EOS 和 padding 的标签均为 `-100`，mask 均为 0。实际系数矩阵 shape 为 `[27,15109]`，对应因果位移后的位置，而不是将 labels 本身提前 shift 两次。

在 27 行等权、且各行先做自己的目标 Token 均值时，B 的隐含质量是 `7/27≈25.9259%`；全体目标 Token 直接等权时是 `4691/15939≈29.4310%`。两种总质量虽都是 1，都不等于 P 的 B 质量 20%；本轮两个负控制均识别了这个差异。

### 9.3 实际受控损失结果

两视图共 18 项 probe 全部通过；全 1 损失聚合都为 1，class indicator 分别得到 P 的 `(4/5,1/5)` 与 Q 的 `(1/2,1/2)`；五个 trajectory indicator 分别复现表中的轨迹概率。不是只在 Manifest 中声明这些质量。

位置变化的测试损失取：第 `i` 行、因果 NLL 的第 `p` 位置为 `(7(i+1)+(p mod 13))/17`，只使用目标位置，行号从 0 开始。结果为：

| 视图 | 精确有理数参考 | 完整 CPU batch 的 float64 结果 |
| --- | --- | ---: |
| P | `153251869611856531/24298656097170420` | 6.307010107843072 |
| Q | `212672134193546515/38877849755472672` | 5.470264830261338 |

所有完整 batch probe 相对于有理数参考转为 float64 后的最大绝对误差为 `8.326672684688674e-17`；固定系数微批次求和的最大误差为 `8.881784197001252e-16`，均低于 `1e-12`。每项精确参考、实际值及误差保存在[受控损失记录](../artifacts/qa_reasoning_share_training_preflight/finance_qa_vnext_finite_support_training_representation_and_class_weight_intervention_preflight_v1_20260906/loss_checks.json)。

这是人为设计 NLL 的组装控制，以上两个数值**不是 Student 的实际训练损失或效用**，不能用来比较 P/Q 学习优劣。有理数的大整数应通过 Python 的精确整数 JSON 解析，或直接读取 `exact` 字符串；不要用会将大整数转成 IEEE-754 Number 的解析方式重新序列化这些参考值。

### 9.4 13 项隔离控制的实际拒绝位置

| # | 控制 | 实际失败代码 |
| --- | --- | --- |
| 1 | `target_numeric_or_field_rewrite` | `text.exact_original_input_and_target` |
| 2 | `request_replaced_with_future_state` | `text.exact_original_input_and_target` |
| 3 | `rejected_qualified_promoted` | `text.positive_membership_order` |
| 4 | `M01_intermediate_promoted` | `text.positive_membership_order` |
| 5 | `equal_row_mean_instead_of_trajectory_mean` | `independent.fixed_per_target_token_coefficient` |
| 6 | `global_target_token_mean` | `independent.fixed_per_target_token_coefficient` |
| 7 | `within_class_kernel_changed` | `independent.fixed_uniform_within_state_kernel` |
| 8 | `Q_text_identity_changed` | `independent.shared_representation_only_class_intervention` |
| 9 | `Q_tokenizer_identity_changed` | `independent.shared_representation_only_class_intervention` |
| 10 | `target_mask_includes_prompt` | `independent.exact_content_only_mask` |
| 11 | `target_mask_includes_EOS` | `independent.exact_content_only_mask` |
| 12 | `padding_supervised` | `independent.zero_loss_right_padding` |
| 13 | `causal_labels_shifted_twice` | `independent.unshifted_causal_labels` |

每次只修改隔离副本；被修改对象重新计算内容身份，必要时同步关联 kernel／batch／view 的身份，使 mask 与权重控制不只是被旧哈希拦下。类内核控制将 A 的选择改为 `(1/2,1/6,1/6,1/6)`，并相应调整 Q 的轨迹系数，类边际仍为 1/2，但不再是固定原 M，因此被拒绝。

原始文本／目标改写控制直接在来源核对处失败；晋升控制引用真实排除 Submission／Receipt，并在正向成员列表检查处失败。这些拒绝是预期的控制结果，不是正式数据导出失败。完整控制记录见[控制汇总](../artifacts/qa_reasoning_share_training_preflight/finance_qa_vnext_finite_support_training_representation_and_class_weight_intervention_preflight_v1_20260906/controls.json)。

### 9.5 四个 Gate 与 98 项测试

| Gate | 限定对象 | 正式结果 |
| --- | --- | --- |
| G0 | 原准入响应的真实来源、原输入和完整排除覆盖 | PASS |
| G1 | 实际 Token 化、content mask、padding、无截断 | PASS |
| G2 | 固定有限类内核和精确 P/Q 质量 | PASS |
| G3 | 实际 CPU 损失恒等与隔离控制 | PASS |

| 专项测试文件 | 通过数 |
| --- | ---: |
| `test_qa_reasoning_share_training_inputs.py` | 12 |
| `test_qa_reasoning_share_training_tokenization.py` | 30 |
| `test_qa_reasoning_share_training_loss.py` | 32 |
| `test_qa_reasoning_share_training_independent.py` | 12 |
| `test_qa_reasoning_share_training_preflight.py` | 12 |
| 合计 | **98** |

主进程汇总复跑前四组得到 86 PASS / 92.29 秒；端到端 12 项为 12 PASS / 488.95 秒，包含多次同数据物化／重建／只读校验与 I/O 保护检查。两组曾并行运行，不把时长相加当成一次实验墙钟耗时。重复测试不增加正式控制数、训练样本数或模型调用数。

15 个本轮 source/test 文件的 Ruff 与 format 检查通过；10 个源码模块 Mypy（显式 `--python-version 3.12 --follow-imports=silent`）和编译通过。全项目 source/tests Ruff 仍只报告未改动历史 v26 文件的 I001 import-order 问题；本轮没有修订该无关历史源码，也没有声称全项目 lint 已清零。

### 9.6 工件字节与身份

正式目录共 **40 个文件 / 7,523,887 bytes**。自排除 Manifest 列出 39 个成员 / 7,517,920 bytes，Manifest 本身 5,967 bytes。持久化记录覆盖其之前 38 个文件及 76 个 file／directory fsync 事件；它自己和 Manifest 不属于其覆盖成员。

主要可消费对象：27 行 [JSONL](../artifacts/qa_reasoning_share_training_preflight/finance_qa_vnext_finite_support_training_representation_and_class_weight_intervention_preflight_v1_20260906/training_rows.jsonl)（1,038,696 bytes）、[基础批次元数据](../artifacts/qa_reasoning_share_training_preflight/finance_qa_vnext_finite_support_training_representation_and_class_weight_intervention_preflight_v1_20260906/base_batch.json)与基础 `base_batch.npz`（231,498 bytes）、[P 视图](../artifacts/qa_reasoning_share_training_preflight/finance_qa_vnext_finite_support_training_representation_and_class_weight_intervention_preflight_v1_20260906/view_P.json)、[Q 视图](../artifacts/qa_reasoning_share_training_preflight/finance_qa_vnext_finite_support_training_representation_and_class_weight_intervention_preflight_v1_20260906/view_Q.json)，以及实际 `weights/P.npz`（3,898 bytes）和 `weights/Q.npz`（3,892 bytes）。保存 JSONL、完整 dataset JSON 和 token／batch 两层表示是同一 27 行的不同容器，不是重复计入 54 行或更多独立样本。

| 对象 | 正式身份 |
| --- | --- |
| `source_authority` | `share_training_source_authority:3d0476b8fec3f8bfd523e61e1f9dada74c1cb2ca56e69e1c453ca154ed272de2` |
| `parent_freeze` | `share_training_parent_freeze:d2ce3664875b0dab313c59fcdc166c8ec77c6aef102e0bdcd9f8ea17404f0cc9` |
| `tokenizer_binding` | `share_training_tokenizer_binding:19bd113181c70cdc83291facccc25e7bc28ecd789588be5020ba9940d4fbaf58` |
| `representation_contract` | `share_training_representation_contract:2afb65db38b1a3a6aad34f90fadfe9f7a248456af194a9d01d47b9060c8f7d36` |
| `text_dataset` | `share_training_text_dataset:7acb8fd02722c33751abd4ebc8b251a96082dcb07af1b08be959251cf64a2aa2` |
| `tokenized_dataset` | `share_training_tokenized_dataset:e0483c89b1da0df0ec074b44aa37feb821fa9f3d429e71a7d8ff4bf8820d29ca` |
| `materialization_kernel` | `share_training_materialization_kernel:65ec649d8747c0c955717ed26d94229ab254c461f32949e2ce90a4a0445cea68` |
| `base_batch` | `share_training_base_batch:2e2615a59354312ea02a373350bdfe1b5f83885f99a8f403cd5d33b968c1201b` |
| `view_P` | `share_training_weight_view:207c0711bb9f2d51b3f28015495ba47972d8f24558af10f966149d68fbfc694f` |
| `view_Q` | `share_training_weight_view:48fc353e95e3f0e17294a75cfc3814e5255561eebe5ddd09c8eae3322f44576a` |
| `independent_validation` | `share_training_independent_validation:4e94e4cd5d9c7a2f88b2886a913dbe143e825c6ba867c5a2eae765f879b6ed27` |
| `loss_checks` | `share_training_loss_checks:87e23e1aa776a7245fcf7ce534a9fe56daceb1a2ca82f0a0266918df28706860` |
| `controls` | `share_training_controls:ee38ca3cb588250dc57b5fca78069f08ca59d8d058b0e2c10edc733fd92aa1a3` |
| `gate_evaluation` | `share_training_gate_evaluation:561dd0f456cfe01e0be843c4654b7ac6786019c30d38d21dd266bb3b709cdee9` |
| Report | `share_training_report:f81f7c13609f34c6ec67348173537fe7771e06714fe6dc2a5e8a39995f4b921a` |
| Manifest | `share_training_manifest:8b79e5183a6540dacfe371f2a3c69ae8f1deb29aec85f18109d2d691fb3b456b` |
| Root | `share_training_root:c82fcc4f94de982115fad8937734ef53142d4fdb49cf895f9c111a7759a2c11c` |

[正式报告](../artifacts/qa_reasoning_share_training_preflight/finance_qa_vnext_finite_support_training_representation_and_class_weight_intervention_preflight_v1_20260906/report.json)与[完整 Manifest](../artifacts/qa_reasoning_share_training_preflight/finance_qa_vnext_finite_support_training_representation_and_class_weight_intervention_preflight_v1_20260906/artifact_manifest.json)保存其余成员和完整哈希。B 仍只有 M03 一个独立实现；上调其系数不增加有效样本量。

### 9.7 完整重建与复验入口

真实冻结 Git 源的单独全量重建已完成：40 个文件 / 7,523,887 bytes 全部逐字节一致，原正式目录及两个父目录均未改变。该重建再次导出同一 27 行、使用同一本地 tokenizer、重新组装 CPU 数组及 P/Q 系数，并重算本轮 18 probes／13 controls；不调用旧资格／投影／十对比较，不进行 Student forward。

以下只读验证命令不会覆盖原工件；需要本仓库已绑定父输入、本地 tokenizer 五文件及记录中的软件版本：

```bash
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.qa_reasoning_share_training_preflight.preflight \
  --mode validate \
  --repo-root /data1/zhuxinrui/projects/Data-Synthesis \
  --replay-from /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/qa_reasoning_share_training_preflight/finance_qa_vnext_finite_support_training_representation_and_class_weight_intervention_preflight_v1_20260906
```

如需重建，在新的临时目录创建子目录；不会覆盖正式目录：

```bash
training_replay_dir=$(mktemp -d /tmp/share-training-replay.XXXXXX)
trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.qa_reasoning_share_training_preflight.preflight \
  --mode replay \
  --repo-root /data1/zhuxinrui/projects/Data-Synthesis \
  --replay-from /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/qa_reasoning_share_training_preflight/finance_qa_vnext_finite_support_training_representation_and_class_weight_intervention_preflight_v1_20260906 \
  --output-directory "$training_replay_dir/rebuilt"
```

当前完成对象是“既有有限支持上的类级训练权重干预已准确实例化”。Contribution、Student 效用、独立目标泛化评估均仍为未测；旧主链保持暂停，未自动授予下一阶段训练权限。
