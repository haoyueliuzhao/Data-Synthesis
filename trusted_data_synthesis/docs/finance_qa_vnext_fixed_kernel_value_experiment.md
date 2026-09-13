# 固定经验材料核上的有限方法分布价值实验

本文件登记审计后继方案、实现边界和实际运行。**本次首次正式采集因本地 SQLite 账本锁错误按规则关闭，训练门为 FAIL；完整材料支持、剂量及 Student 效用未测。下文工程 PASS 不是科学效果 PASS。** 用户随后授权修复并继续，后继修订条件另行冻结，不改写本次停止结果。

协议包：`finance_qa_vnext_fixed_kernel_value`；协议/原始输出版本标签：`study_20260913`。目录标签和洗牌种子不是实际执行时间，时间以各运行工件保存的 UTC 字段为准。

## 1. 研究问题与不变的旧结论

本轮问题是：在同一批真实、完整、可消费的原始材料上，保持任务质量、材料本身、模型和 Loss 不变，只调整已认证实际方法的训练概率质量，能否改善独立 Student 效用？

这不是继续寻找一种能让每个格子凑齐指定数量的提示，也不是把材料生成或支持诊断改名为分布优化。

- 旧 Probe 0.1 已结束。其 144 条真实轨迹、P2 的 17 条财务有效 movement、其中 13 条完整可消费 movement 保留原始结论。P0、P1 的完整 movement 为零。
- P2 与 P1 的财务有效数同为 34/48；完整可消费总量分别是 28/48 与 31/48。P2 恢复局部方法支持，不等于证明总体材料质量或训练价值更高。
- 旧 24,640 条大规模材料不足、旧 A/B 的停止和旧 8+2 门槛失败不回写。新方案不把旧样本补进新 A/B，不声称原门槛已经通过。
- 不增加 P3/P4，不按本轮 13 个正例名单、旧产率或 Student 分数选题，不通过持续追加采样追逐“双路齐备”。
- 允许同题多次抽样，目的是一次性物化有限经验支持，不按 NLL、长度、文风、稀有度或未来收益挑 Top-k。

旧 144 条只承担已知开发/回归证据的角色。新版本重新表示某些开发轨迹，不使它们变成“新独立采样”，也不改旧报告数字。

## 2. 对象：生成条件、材料核、目标分布分别负责什么

固定公开生成条件下，Teacher 轨迹来自：

\[
\tau\sim P_{\theta_{\rm Probe},\Gamma_{P2,g}}(\cdot\mid x).
\]

后继训练对象是：

\[
D_{\pi,\psi}(x,g,\tau)
=\mu(x)\sum_z\pi(z\mid x)M_\psi(g,\tau\mid x,z).
\]

P2 决定材料从何种条件产生；来源/执行资格决定哪些实际轨迹能进入核；本轮三臂真正改变的是 \(\pi\)。没有比较“P0 原包训练的模型”和“P2 新原包训练的模型”来归因纯分布效应。

同一个池内，三臂使用相同原包、相同指导前缀、相同来源组织、相同失败历史及相同 Token 表示。只有有效权重不同。材料中与方法同时出现的词汇、来源选择和执行习惯仍属于该固定经验核，因此效应是这个有限核上的分布效应，不是对模型内部认知机制的鉴定。

## 3. 一次性来源与执行历史边界

### 3.1 来源：保留原位置，不凭 gold 数值建立别名

`source_boundary.py` 只处理公开来源的离线覆盖，不读取 Student 输出，也不修改公开题面。父链由原 revision catalog 和三个既有数据父清单的内容身份、文件 SHA 验证。

公司定义指标的已定位问题是：公开原表保留了多个报告的重复披露列，而旧 `native_bindings` 只选了一个报告位置。读取另一个合法重复 cell 时，旧 locator 查找可能为空。这不是自动的金额错误，也不自动授权跨报告等价。

新 occurrence 映射至少同时要求：

1. 同实体、同来源簇；真实 HTML 的 table XPath、原行列坐标、逻辑列跨度、原文本、定义段落能够重放。
2. 同完整公司定义和组件标签。指标/source-definition 身份从原定义构造核对，不把通用 FCF 公式套在所有公司上。
3. 来源报告 accession 与原始 CFO JSON disclosure 的 accession 一致；从该原记录绑定实际 start/end 与 filed，而非从文件名、财年标签或答案推断实际期间。
4. 明确 USD 与 million USD 的尺度及原符号；单位一致性是来源验证，不是把数值匹配当定位器。
5. 来源列与规范列的完整带符号 reconciliation 向量一致；该数值检查发生在实体、定义、期间和原文定位已成立之后，只作为版本相容性的一部分。
6. 对绑定定义到表格及表后 600 个规范化字符的局部说明窗口检查显式 restated/recast/revision/reclassification 标志。出现标志或规范定义/版本冲突时继续 UNKNOWN。本规则不声称证明整份报告完全没有任何修订。

证明同时保存 occurrence fact ID、原 fact ID（如原映射已存在）、canonical fact ID、原 cell reference、原/规范报告 SHA、原 document/raw-object 身份、同 accession 的 CFO 期间锚及其原 JSON pointer。新增 occurrence 不覆盖旧 fact。旧原件仍在，原公开表的其他行也仍可访问；未认证位置明确记录为未认证，不能通过只开放 gold 用到的位置来获得通过。

原 255 目录的一次工程覆盖检查验证了 23 张公开公司表、37 个 HTML/CFO 原文件。新增 316 条 task-local 位置映射，对应 89 个不同原始 occurrence，影响 36 个公司定义任务；2 个不同 table-period 在 4 个 task-local 列位置仍缺少同 accession 实际期间锚。这些数目是**原目录来源覆盖诊断**，不是正式 200 题的 Teacher 命中率或可消费材料产量。

### 3.2 执行历史：新版本表示确定事件，不推断心理意图

`semantic_mapping.py` 保留旧 `assess_replayed_session()` 结果，并另存新来源扩展结果与新执行历史签名。财务有效和完整映射继续分开。

四条已指定开发记录的实际内容是：

| Probe ordinal | 原 pending 的实际来源 | 新表示边界 |
| --- | --- | --- |
| 29 | 无 Final 依赖的收入差侧计算；另有显式百分比计算修订 | 保留已执行、源绑定的非 Final 依赖程序；显式修订仍保持显式 |
| 71 | 两次单位维度拒绝、一次 DSML/JSON 格式拒绝、错误符号侧计算 | 记录确定拒绝及非主支持程序，不编造隐式 revision/心理纠错边 |
| 97 | 多行/跨列读取拒绝、格式拒绝、常数表达式维度拒绝，之后成功重建 | 全失败前缀仍在；成功 Final 的真实依赖链不剪辑 |
| 104 | 两次非相邻列读取拒绝，之后分开读取并计算 | 原拒绝次数、位置和后续执行均保留 |

完整原轨迹重放和旧 assessment 身份回归一致；四条在新有限执行事件表示中均可映射。**旧资格仍是 pending，不将新结果回写旧 17→13 漏斗。** 另一个已知开发公司定义记录 ordinal 0 的原空 locator 在来源证明成立后可由新规则验证；同样不混入正式材料。

新表示仅承认已声明的确定错误域。未知失败工具语义、无法源绑定的计算、未知混合方法等仍 pending。非主支持计算不被宣称为“正确验证”或特定心理目的。成功工具指运行时执行成功，不代表每个额外侧计算都有正确的财务用途；这些实际执行不能为整齐类别而删掉。

## 4. 固定科学任务总体与公开版本

先读取原 255 个科学任务的元数据，再按各 family 内来源簇升序轮转、簇内固定 TaskID 升序选题：

| 训练任务 family | 任务数 |
| --- | ---: |
| annual_flow | 40 |
| stock_rollforward | 40 |
| company_defined_metric | 40 |
| control | 80 |
| 合计 | 200 |

数量类型保留，但不另加差额/增长率的结果驱动配额。规则不读 Probe/Student 成绩。所有池和训练臂共用原公共问题、sources 和 surface version：

\[\mu(x)=1/200.\]

工程检查已经按该规则构造 200 清单，population 内容身份为：

`population:e1331f06631f5a72b790372b15da38cccf4c1f4255a1aae4594609b161105c15`。

正式登记与启动时间以 root 的 freeze/registry 工件为准；内存构造清单和脚本验证不是实际 API 登记。`load_inputs()` 返回纯 JSON 结构并关闭全部父链句柄。`boundary_manifest` 逐题绑定原/扩展 native SHA、source-boundary ID、bundle/parent/surface/public-message 身份。正式运行前重建对照，不从覆盖结果换题。

某题只有一个方法时仍留在总体。若某题在任一池没有合格训练实例，不能保持 \(\mu\) 又悄悄训练剩余题；记录输入不足并停止本方案训练，不转移其质量或换题。

## 5. 一次固定材料采集和独立角色

| 每池对象 | 每题固定会话数 | 每池会话 |
| --- | --- | ---: |
| 120 个目标任务 | P2 endpoint 16 + P2 movement 16 | 3,840 |
| 80 个控制任务 | 共同交付合同、neutral 无路线偏好 16 | 1,280 |
| 每池合计 | — | 5,120 |
| A/B 两池合计 | — | 10,240 |

每个池×任务×指导 cell 的 replicate 0..11 事前分给 train，12..15 分给 sealed。每池最多 3,840 个训练候选、1,280 个封存候选；两池分别最多 7,680/2,560 个。角色先于结果，不能将成功的 sealed 候选回填 train。

注册顺序采用事前固定洗牌种子 `20260914`，不是 Teacher 生成种子。目标任务 P2 SYSTEM 与旧 Probe P2 逐字节相同，没有新 P3。控制使用共同 delivery 合同，无 endpoint/movement 指导。

固定 Teacher 为协议中的 `deepseek-flash`，请求端点 `https://api.deepseek.com/chat/completions`。请求启用 thinking/high reasoning effort、JSON object、非 streaming；不临时搜索 temperature/top-p。公开 response content 和请求正文保留；不保存私有 reasoning 文本。公开投影不能重建整份原 HTTP envelope，这一限制明确记录，不伪称可还原私有 CoT。

上限为每会话 32 个响应、32 个工具调用；两池合计最多 327,680 个请求。HTTP 并行度 128，CPU 资格/工程并行度 24。完整历史请求体上限 98,304 字节，公开单响应上限 65,536 字节；达到边界不截断题面或历史，不追加“修复采样”。

## 6. 第五用途预算与闭合语义

新材料是共同钱包中的第五个独立用途，子额硬上限 250,000,000 Token，且始终受共同 1,000,000,000 Token 上限及冻结时真实保守余额约束。不是继承旧 Probe 尚未使用额度，也不假定历史审计时的余额仍等于当前余额。

请求先有租约再发送；每请求保留输入 99,328 + 输出 16,384 = 115,712 Token 预算。结算使用实际返回 usage 并验证模型/用量合同。已发送但用量未知的租约不当作免费或擅自返还；未发出的预留只能按严格“未发出”证明取消，不能同一会话重新尝试。

不重置旧用途费用，不打开旧用途，不从其它人的未知租约借余额。预算中止仍保留全部 10,240 注册分母，不用成功前缀训练。

三个不同事实必须分别报告：

- `raw_registry_complete`：10,240 个原状态是否全部 finished；财务失败/unknown/无 Final 可以是一次已结束尝试，不能为了美化分母删除。
- `generation_contract_passed` / `collection_gate_passed`：来源、代码、钱包、传输等全局合同是否允许进入材料消费阶段。
- `materialization_permitted`：上两者同时满足才执行 Token 物化。

若原会话全部结束但全局合同失败，不把它写成“没有采完”。材料状态为 `NOT_MEASURED_GLOBAL_GATE`；财务/完整类/实际方法原资格保留，Token 计数和 S/剂量/空支持的未测量项不写成零。outcome 的 `consumable=False` 此时仅禁止准入，另有 `consumability_status` 说明未测，不构成不可消费的经验结论。

## 7. 原包消费与有限材料核

完整闭合且允许物化后，对所有 financial-valid + MAPPED + 真实完整来源的 train/sealed 候选统一尝试同一个本地 Qwen tokenizer；批量构造一次 tokenizer，不加载 Student 权重。

- 使用既有 `encode_original_candidate()`，序列上限 24,576，不重新拼写 target，不重建一套新 mask，不截断。
- 正向目标为实际成功公共工具响应及首个 Final；输入保留当时的完整公共历史，包括所有更早失败工具、格式错误和反馈。
- 失败响应不会被提升为正向 target；其真实历史也不能被剪掉。
- 一个原包任一行编码错误或 overlength，整包不可消费。所有原候选及 not-fit/error 记录仍保留，不丢长行后伪造完整包。
- 失败异常导致某些 Token 数不可知时保留 unknown，不用已知小计代替真实整包分母。
- 所有合格、完整、可消费 train 原包进入核，不选最好八条；sealed 原包不进入训练核。

每个 `encoded_original_package` 绑定 registration/session/qualification/source-boundary/bundle/code/tokenizer 身份、实际方法与完整类，并保存原 encoder 的完整 `input_ids/target_mask/labels/attention_mask` 等表示。

大数组只在 `packages/<registered_session_id>/package.json` 保存一次。`stored_material_outcome` 与 `materialization_index` 保留路径/SHA/ID 的轻量索引；`hydrate_outcomes()` 验证原字节后可在内存重建同一 material-outcome ID。不会把巨大 kernel/outcomes 数组再写一份直接提交 Git。

## 8. 唯一分布干预、不等包数和剂量门

池 \(h\)、任务 \(x\)、完整状态 \(z\) 有 \(n_{h,x,z}\) 个合格训练原包时：

\[M_h(P\mid x,z)=1/n_{h,x,z}.\]

完整状态 ID 由实际方法与已认证完整类内容共同派生，不由 requested-basis 产生。定义 \(S\) 为 A/B 两池都具有真实 endpoint 和 movement 训练支持的非控制任务集合。\(S\) 只决定干预在哪些任务上生效，不决定保留哪些任务。

在 \(S\) 内：

\[\pi_{a,h}(z\mid x)=\alpha_a(m(z)\mid x)\frac{n_{h,x,z}}{n_{h,x,m(z)}}.\]

| arm | endpoint 质量 | movement 质量 |
| --- | ---: | ---: |
| alpha0 | 1/2 | 1/2 |
| plus | 1/3 | 2/3 |
| minus | 2/3 | 1/3 |

\(S\) 外各臂保持同一个预定静态核：在该池/任务的全部合格训练原包上均匀；相应细类质量为 \(n_z/n_x\)。单方法任务和控制不被删除。

相对基线的全局移动：

\[\Delta_{\rm mass}=|S|/(6N)=|S|/1200.\]

事前最低剂量为 5%，即 \(|S|\ge60\)。这是本次共享方向实验的剂量设计，不是 VTDO 理论阈值，也不是统计功效保证。未达标不临时放大步长、不追补采样、不按成功子集改总体。

有限细类被保留，但优化自由度仅是上述共享方法边际。不能说已经优化整个细商空间，更不能把“复杂/罕见/更多组件”当成 Contribution。

## 9. 同一 Full Loss 和物理训练预算

每次更新取五题：三个目标 family 各一题，加两个 control。对同一批全部原包反传完成后，才 clip 和 step 一次：

\[
\mathcal L_B(\theta)=\frac15\sum_{x\in B}\sum_z\pi_h(z\mid x)
\frac1{n_{h,x,z}}\sum_{P\in(x,z)}\frac1{L_P}\sum_{u\in P}{\rm NLL}_{\theta,u}.
\]

逐目标 Token 系数是：

\[\pi_h(z\mid x)/(5n_{h,x,z}L_P).\]

\(L_P\) 是整个原包所有正向公开响应的目标 Token 总数，不是当前行长度。没有额外微批、Token、任务数或全局 N 的重复均值。200 题十遍，40 次更新/遍，共 400 次更新；每步包数可变，不再硬编码 64。

物理基线保持：Qwen2.5-7B-Instruct；冻结 BF16 base，FP32 q_proj/v_proj LoRA；rank 8、alpha 16、dropout 0.05；AdamW，lr 1e-4，betas (0.9,0.999)，eps 1e-8，weight decay 0；常数学习率、0 warmup；最大梯度范数 1；种子 11/29/47。每行 microbatch 1；gradient checkpointing 非 reentrant；Full 原 target mask；禁 TF32，使用既定确定性配置和 FLASH_ATTENTION SDPA。

同池各臂训练同一物理原包、相同顺序/处理量，只是系数不同。每次正式训练从配对的 fresh base + seeded LoRA + 空 AdamW 状态开始。工程预检的 Adapter/优化器状态不会继承。

## 10. 独立 Student 选择与确认

复用原受保护 900 题及其公开 surface manifest，不加 movement 指导、不根据本批 Teacher 产率改题面。评估分组是 `dual_sufficient`、`composition_required`、`other_financial`，**不是训练集的三个目标 family 配额**。

| 阶段 | 固定范围 |
| --- | --- |
| A 训练 | 三臂 × 三种子 = 9 次 |
| A dev | 180 题（三组各 60）× 9 模型 = 1,620 会话 |
| 选择 | 跨种子的平均配对完整轨迹收益严格为正才离开基线；平局顺序 alpha0、plus、minus |
| B 训练 | 若移动，基线 + 唯一候选 × 三种子 = 6 次；不另跑 B dev |
| 确认 | 两池 × 两臂 × 三种子 × 720 题（三组各 240）= 8,640 会话 |
| 最多合计 | 15 次训练、10,260 次 Student 会话 |

若 A dev 没有严格正方向，止于 9 次训练和 1,620 次评价，B/确认不是“漏跑”。不能在确认失败后转去跑 runner-up。

主指标为三组等权的完整轨迹财务资格，而非仅 Final 数值准确率或 movement 比率。失败、unknown、无 Final 保留固定分母。主财务资格与细类映射分开：fine-mapping pending 本身不抹掉已成立的财务有效性。

评价沿用 neutral greedy 解码、单 beam、每响应最多 2,048 new tokens、24,576 总序列、32 响应/32 工具；完整 prompt 加预留输出超限就记录上下文拒绝，不截断或换参数重跑。

确认按来源 CIK 簇配对，B 为预先固定主确认池，A 为辅助。使用固定 seed 20260912 的 10,000 次共享簇权重 bootstrap、95% paired percentile 区间；空组抽样整次重抽，不删组/重新归一化。B 区间下界严格大于 0 才确认正收益；含 0 不确认。上界仍高于 5 个百分点意味着尚不能排除该量级收益，不等于证明收益存在。

720 道题不会因三个种子变成 2,160 道独立题。区间条件于固定已训练 checkpoints，不覆盖所有训练随机性，也不保证检出 5 个百分点。共享方向没有收益不能推出所有任务条件化 \(\pi\) 更新都无效；人工 plus/minus 不是 oracle 上界。

## 11. GPU：已完成工程使用，不是科学训练结果

为响应空闲 GPU 的使用要求，已在 NVIDIA A100-SXM4-80GB 上执行三次初期检查，并完成一次最终代码复核；全部是**合成材料、同一不等包数消费者**工程检查。每次均为五题、15 个原包形式的合成结构、一次 optimizer update；独立分组损失与消费者一致。它们不使用正式材料，不保存可继承的 Adapter/优化器 checkpoint。

| 本地工程目录标签 | 最大序列 | 目标 Token 总数 | 峰值 allocated bytes | update 秒 | 损失绝对误差 |
| --- | ---: | ---: | ---: | ---: | ---: |
| engineering_gpu0_20260914 | 512 | 156 | 15,578,290,688 | 3.8787 | 1.6161e-8 |
| engineering_gpu1_20260914 | 24,576 | 156 | 28,013,189,632 | 12.8518 | 2.1625e-8 |
| engineering_gpu0_long_target_20260914 | 24,576 | 2,196 | 28,633,626,624 | 12.7125 | 1.6658e-8 |
| engineering_final_code_20260913 | 24,576 | 2,196 | 28,633,626,624 | 12.6058 | 1.6658e-8 |

报告均 `PASS_ENGINEERING_ONLY`，`scientific_student_updates=0`、`formal_materials_consumed=0`、`production_initialization_reused=False`。前三份报告 ID 前缀分别为 `4f60f74a…`、`e6052197…`、`c2ffd650…`；最终代码报告为 `gpu_engineering_report:3893def05222d3c743ce4a10da43ec3b7bce56728725fc31e9c671858c82553a`。原件位于新工作树 `trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/` 的相应工程目录。

最终报告的 `baseline_configuration` 是历史物理配置引用，其中旧 64 包/8+2 描述不能当成本轮生产包数。实际 `update_report` 明确 `engineering_only=True`、15 个异量合成包和新 `pi/(5*n_state*L)`；正式 `training.training_config()` 才是 200 题/动态全包的生产配置。

这些观测证明实际 GPU 上相关形状和消费者的一次更新能运行、有限误差内算术相符，不证明 Student 效用、全程吞吐、最坏上下文/监督密度或三臂统计功效。正式最多八个并行 GPU worker，一卡一任务，加载前再次验证材料/剂量门、空闲显存和 GPU UUID；故障停止新启动，保留在途/失败/未启动分母，不自动重试。

另外，选定 200 题的 560 项 CPU 原 witness 工程矩阵（目标每题 2 指导 × 2 实际方法，控制 neutral）已全部通过；最大 10 响应、9 工具、28,588 字节请求体。外层明确 `ENGINEERING_SYNTHETIC` 和读取 private witness/reference answer，绝不拿 runtime 内部的 `private_oracle_access=False` 声称脚本没用私有参考。它们不属于正式 10,240 登记。

## 12. 归档、发布和可重放性

`publish.seal_stage(code_root,data_root,stage=...)` 只封存，不执行 Git，不改钱包或原始文件。原始数据根为 `p.OUTPUT`，发布目录为其兄弟 `p.OUTPUT + '_publication'` 下的 `materials` / `results`，不是原目录子树，避免打包自己。

- materials 必须有闭合 generation report、无在途请求、报告 ID 对应的已关闭第五用途，以及 10,240 固定 registry/session-results/materialization 分母。允许收口 STOP/材料门 FAIL，但发布不是科学 PASS，不把前缀变成功。
- results 必须有实际完整 execution report 的两种预定终态、对应 execution freeze/decision/producer manifest；失败工件保留本地，不能把 `actual_complete=False` 当作完整科学结果。
- 最终 LoRA 仅从明确批准的 9/15 个真实 training report 的 `final_adapter.safetensors` 引用核对路径、字节数、SHA 和 checkpoint 身份；不扫描/打包 base weights 或工程状态。
- JSON 要与 canonical 原字节一致；JSONL 每行 payload canonical，原换行字节保留；XML 保留原件并做语法/无外部实体检查。所有选择的原文件逐项 SHA。
- 真实 DEEPSEEK credential 仅加载到内存做精确扫描，不写值、不输出值。symlink、钱包/SQLite、runtime、`.env`、私钥和未批准格式拒绝；console `.log` 留本地并在发布清单说明排除原因。
- 每个确定性 USTAR/gzip 分片的原 tar 和压缩文件都不超过 32 MiB，成员顺序固定、owner/mode/mtime 固定、gzip filename 为空、mtime=0。逐物理成员解包到内存并与原字节范围比较。
- 大逻辑文件（如 request journal 或 Student manifest）只在出版包装层按固定 16 MiB 范围形成有序 raw 片段；不修改、重写或切分落回原文件。physical index 记录逻辑路径、offset、length、片段 SHA 和 archive 路径；完整回读验证无间隙/无重叠、重建总长度及整个原逻辑文件 SHA。即使原单文件超过 32 MiB，也不必截断或改变科学材料。
- 当前单逻辑文件的明确 CPU 格式检查容量是 1 GiB；超过此容量仍拒绝，不假装已验证。已用真实 33 MiB canonical JSON 的 3 片重建控制验证 >32 MiB 路径；这不是承诺无限大的内存/文件支持。基座权重依然禁止，不能利用分片机制混入模型基座。
- 所有原路径在分页面 logical member index 中，物理片段另有 physical index，重复内容另有 duplicate index；两个原路径及各自字节均保留。顶层 publication manifest 只绑定各索引页、分片和阶段闭合证据，不复制巨大 kernel/outcomes 数组。
- 新发布 manifest 明确区别原 execution manifest。后者可能记录本地 `.log`；排除日志后不能冒称完整重现原 producer 命名空间。
- 每阶段只写一次；后续 Student 新文件不能改变已经封存的 materials 快照。若途中出错，原件保持完好，未完成发布目录保留供检查，不能覆盖伪装成已封存。

根协调者负责最终 Git 提交、远端推送及发布说明；子模块不自行做 Git 或对外发送。

## 13. 与 anchored / HierLoss 的关系

本方案是有限方法质量方向的训练价值基线，不是完整 anchored VTDO。

anchored 的真实生产适配应使用当前 Student 和优化器状态形成实际 \(C,N,\Phi,\pi_{t+1}\)，适配不等包数和细状态目录，在相同核上继续训练；不能用 Probe 覆盖率替代 Contribution，也不能把已有 CPU 公式控制当作真实 Qwen 反馈。原两次外层、连续内层训练边界保留，不改成每轮重置模型。

HierLoss 置后。先在固定 \(\pi\) 下比较 Full 与真实可用的公共层模式，再研究和自动分布更新的交互。TF 权重含总 Loss 尺度变化，会改变梯度和 Contribution，不作为当前三臂的无关小改混入。

双 KL、正势函数、两次更新不是无条件收敛证明。收敛和消融是独立问题，不被工程 PASS 或共享方向正/负结果替代。

## 14. 最终实现检查与事前发布顺序

2026-09-13 的冻结前联合 CPU 回归实际完成 **349 项通过、0 失败、0 跳过**，耗时 193.70 秒。包括材料/分布/消费者/执行/来源/预算/协议的 298 项既有本轮测试、新采集生命周期 17 项、发布主测试 26 项、独立分片攻击 8 项。正式准备将保存完整 JUnit XML，而不是把这些合成/工程控制计入 Teacher 或 Student 分母。

全源码 Ruff 检查另发现 `protocol.py` 中 9 条 `E501`：均为政策说明字符串超过 100 列；其余规则使用 `--ignore E501` 核对通过。本轮客观保留这 9 条格式警告，不称完整默认 Ruff 全绿，也不为纯换行修改已通过实际 GPU 工程检查的协议字节。该格式事项不改变政策内容身份、数学权重或执行行为。

先冻结代码、原来源/钱包快照、200 题总体、角色与 10,240 项注册，再提交并推送授权远端的 `main`。生成及训练期间，本地旧 `main` 和其他四个保护工作树仍保持冻结时字节与本地 HEAD，执行使用新隔离工作树；远端新增提交不被描述为旧实验结果变更。全部阶段闭合后再将本地 `main` 快进到已发布提交。发布只追加新源码、说明和结果，不重写旧 Probe/Phase 0 结论或恢复旧 A/B。

## 15. 第一次正式采集的实际停止结果

| 项目 | 正式结果 |
| --- | --- |
| 冻结/生产提交 | freeze `7ca50f2a…`；实际源码 `4d9b3bf6aa3c6252fdd15397a5923256f666a35b`，先提交推送 main 后执行 |
| 正式开始/生成闭合 UTC | 2026-09-13 14:42:09.807158 / 14:44:15.433300；生成编排计时 119.3965 秒 |
| 10,240 注册终态 | `finished` 19、`budget_aborted` 116、`not_run` 10,105；135 个原会话及135个既有资格结果完整保留 |
| 实际外发 | 131个会话实际发送342次HTTP；另30个已预留请求证明未发送并取消；372条原租约全部保留 |
| 实际费用 | prompt 1,046,356 + completion 223,347 = **1,269,703 Token**；342次外发全部已知结算，新未知0、在途0 |
| 共同保守扣款 | 384,440,191 + 1,269,703 = 385,709,894；剩余614,290,106；旧用途行与旧未知扣款不变 |
| 已保存前缀中的既有资格 | 17个first Final；财务有效16、完整类有效16、完整来源链认证17；16个满足逐候选Token物化前置条件，但全局门禁止物化 |
| 上述16条实际方法 | control 6、endpoint 9、movement 1；仅为提前停止所观察的诊断前缀，不是总体产率或训练材料 |
| Token/支持/剂量 | tokenizer加载0；消费性、共同S、全局质量移动及空支持任务均未测（null），不是0个支持或剂量不足 |
| 训练/评价 | 正式Student训练0、评价0；三臂选择、确认和效用区间均未测；不得使用成功前缀训练 |
| 原件封存 | 11,632文件、75,974,582字节；3个确定性分片；publication `688f6194…`；secret命中0 |

19个`finished`包括17个first Final与2个无有效公开响应的局部终态，不等于19个财务成功。10,109个注册会话未真正外发，包括10,105个没有进入生成器的会话及4个进入后、首发前停止的会话；不能把钱包关闭时所有行的行政`finished`状态当成10,240个完整模型会话。

### 15.1 停止原因与证据强度

6个会话实际记录`OperationalError: database is locked`：4次发生在HTTP 200响应已保存后的本地结算，另2次发生在下一次调用形成新租约之前。最早有落盘时间证据的请求`ef791489…`在14:42:30.455623保存公开响应、14:43:00.786972保存锁错误，间隔30.331秒，与源码SQLite连接的30秒超时一致。四个HTTP后锁例均返回`deepseek-flash`、有效usage和非空公开内容；异常分支随后完成本地费用结算，但仍把原错误传回运行时，**未重新发送HTTP**。

运行时将SQLite错误列为全局错误，采集器据此设置stop Event。最先持久化的`kernel_fatal`指向`f283…`，该会话已经是`study.stopped_before_next_HTTP_request`传播项，不能把它写成最初的锁源；严格线程级第一次stop时间未独立记录。外层`generation_report.failure_records=[]`，因此也不能把此次事件误写成独立评估任务异常。

两条无有效公开内容是`ValueError`且`global_fatal=False`，只结束各自会话，不是全局停止的触发原因。原钱包已启用WAL；128线程直接通过多个连接争用一个SQLite写者，写事务内仍重复执行保护验证与全用途SUM，旧Teacher表有119,249行且其SUM执行计划为全表扫描。这些是实际存在的竞争结构；将其归因为具体线程饥饿属于与观测一致的工程解释，不冒充已记录了每个底层锁的完整调度轨迹。

349项小规模/工程测试没有覆盖“真实大旧账本＋128路混合reserve/mark/settle/cancel”的完整压力组合。这是本轮实现的验证缺口，不能用测试全绿抹去真实失败，也不据此推断模型财务能力不足。

### 15.2 轻量收口、可复核工件与继续授权

事后仅用24路读取已经生成的135个会话/资格记录做计数，没有再执行金融语义、API、tokenizer或GPU。计数脚本是[`summarize_fixed_kernel_value_20260913.py`](../scripts/summarize_fixed_kernel_value_20260913.py)；[机器摘要](../artifacts/qa_vnext_fixed_kernel_value/study_20260913/closed_collection_summary.json)绑定脚本SHA及闭合报告。五个既有保护工作树快照、旧账本逻辑快照的前后记录相同；该计数步骤没有重新全量读取这些原始来源或账本。

[生成闭合报告](../artifacts/qa_vnext_fixed_kernel_value/study_20260913/generation_report.json)、[预算关闭](../artifacts/qa_vnext_fixed_kernel_value/study_20260913/budget_finalization.json)、[训练门](../artifacts/qa_vnext_fixed_kernel_value/study_20260913/material_gate.json)及[完整分片发布索引](../artifacts/qa_vnext_fixed_kernel_value/study_20260913_publication/materials/publication_manifest.json)保留失败与未测状态。三个gzip分片共12,832,762字节，全部原路径、SHA、逐字节回读已验证；本次没有需要再次拆分的超大逻辑成员，未重复运行整套回归。

用户在看到停止后明确要求“尽快处理继续在线采集以及后续训练”。因此后继将以新修订条件修复账本写入竞争，保持原200题、公开协议和角色规则，另登记一次固定采集；旧失败原件不混入。前后两批合计上限仍为2.5亿Token及327,680次实际HTTP，后继最多248,730,297 Token及327,338请求。未重新获得完整材料与5%剂量准入前，不启动Student。该后继授权不使本节的STOP、未测或原门失败变为PASS。
