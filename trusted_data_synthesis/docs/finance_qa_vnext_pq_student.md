# 固定支持 P/Q 类质量干预：三配对种子 Student 诊断

## 状态与声明边界

本文件的初版是**运行前设计**。代码、评测问题及政策须先提交并推送，再封存 preparation，随后才可加载实际 Qwen2.5-7B-Instruct。初版不声称训练或效用结果已经成立。后续结果应追加，冻结时副本保存在 `preparation/design_at_freeze.md`。

承接用户 2026-09-10 审计（SHA256 `30758445df231f9f9c26c15a0573cfd33659873a6295ec9ebf7a6d5e10898d87`）。上轮发布 `f7af54f4bf2633036c2aca96d198212de512c1bd` 已收口：24 会话中 18 个完整有效包，36 行，4,793 个监督 Token；L1 有余额差两条、明细一条。历史失败/未知、不同行为的 19 个配对与旧 Token 数组均不重判或重写。本轮没有新教师采样。

唯一主问题：固定六任务边际、有效支持、类内原样物化、实际训练预算和独立评测面板，只移动 L1 类质量，是否精确实现，并造成可观察的 Student 表现差异？Q 是人工诊断条件，不是优化后的 Contribution/Novelty 分布，也不预设更好。该实验不是完整 VTDO 算法验证。

## 1. 固定数据与精确损失

直接引用 `qa_vnext_open_support_exploration/three_structures_4rep_20260909` 已封存的十八包及三十六行；不重新采样、改写原始 assistant 文本、裁剪、重新分词或补齐失败会话。新增的是权重/损失视图。

六任务 G1、G2、F1、F2、L1、L2 各有质量 `mu=1/6`。每类内部的既有包均匀，固定 `kappa`。L1 的余额差 D 为 `T_L1_01` 与 `T_L1_04`，期间变动明细 R 为 `T_L1_03`。

| 包所属位置 | P 每包质量 | Q 每包质量 |
| --- | ---: | ---: |
| G1/G2/F1，各题三个包 | 1/18 | 1/18 |
| F2，四个包 | 1/24 | 1/24 |
| L1 D，两个包 | 1/18 | 1/24 |
| L1 R，一个包 | 1/18 | 1/12 |
| L2，两个包 | 1/12 | 1/12 |

因此 P 的 L1 类质量为 `(2/3,1/3)`，Q 为 `(1/2,1/2)`，两条件总质量皆为 1，每题质量皆为 1/6。十八包均匀取样不满足此任务边际，因此未使用。

一个包的损失是其**所有原监督目标 Token 的平均 NLL**；每个目标 Token 的系数是 `w(package)/L(package)`。全局目标为所有这些加权 NLL 的和。不能先求每行均值再平均，不能再除以全局 Token 数或微批数。角色标记、历史、工具返回和原政策未监督后缀继续保持原标签屏蔽。

CPU 精确分数控制验证：

`L_Q-L_P = [ell(T_L1_03) - (ell(T_L1_01)+ell(T_L1_04))/2] / 36`。

同时验证按 1、2、5、12、36 行分块再求和完全一致；小型合成 logits 检查 float32 交叉熵、因果错位一次且仅一次，以及选择目标前驱 logits 与完整序列参考的损失/梯度一致。这些是接线控制，不是 Student 能力结果。原数组只读必要绑定核验，不重复上轮 45 项控制、19 对语义比较或 778 文件审计。

## 2. 固定 Student 与训练配置

本地检查点 `Qwen2.5-7B-Instruct-a09a35458c702b33eeacc393d103063234e8bc28`。四个 safetensors 分片、索引、config、generation config 逐文件 SHA256，张量名称/形状与索引核对，版本记录在 `checkpoint_binding.json`。不以目录名代替权重身份，不下载新模型。tokenizer 使用历史绑定的同一版本资产，原 36 行不重编码。

| 设置 | 冻结值 |
| --- | --- |
| 基础模型 | Qwen2.5-7B-Instruct，原权重 BF16、全部冻结 |
| 可训练范围 | 28 层 q_proj/v_proj 的显式 LoRA A/B，不训练 bias、embedding、lm_head |
| LoRA | rank 8，alpha 16，dropout 0.05；A Kaiming uniform，B 零；A/B FP32 |
| 低秩残差 | `base(x)+(alpha/r)*B(A(dropout(x)))`；A/B 计算 FP32，残差回到基础输出 dtype |
| 优化器 | AdamW，lr 1e-4，betas 0.9/0.999，eps 1e-8，weight decay 0 |
| 学习率/裁剪 | 恒定，无 warmup；全 36 行累积后 clip grad norm 1，再 step |
| 配对种子 | 11、29、47；P/Q 共六次训练 |
| 每次训练 | 完整 36 行遍历 10 次，10 次更新；microbatch=1 行 |
| 顺序 | 每 seed 一个固定 RNG 生成每轮全行置换；同 seed 的 P/Q 相同 |
| Token 预算/运行 | 47,930 监督 Token；2,326,030 完整序列 Token |
| 注意力/显存 | PyTorch SDPA 的 FLASH_ATTENTION；非 reentrant gradient checkpointing；训练 use_cache=False |
| logit 范围 | 只投影原标签有效位置的前驱 hidden states；不改变原上下文或目标 |
| 数值设置 | loss FP32；TF32=False；确定性算法；CUBLAS_WORKSPACE_CONFIG=:4096:8 |
| 检查点选择 | 只保存第 10 次更新的最终 adapter；不按评测挑选 |

训练不是随机重采样：每个运行都处理相同的物理数据量，用不同确定系数实现指定加权目标。它不声称教师自然采样概率已改变，也不声称与任意重采样过程的优化噪声相同。10 次全遍历是事先选定的有限敏感性诊断，尚未证明为合适强度；不根据结果延长训练或修改学习率。

执行顺序为未更新 B0 先评测一次，再运行 P11/Q11/P29/Q29/P47/Q47。最多两个训练 worker 并行，其余排队；在物理 0–7 中只选择当前至少空闲 70,000 MiB 的 A100-SXM4-80GB，每卡至多一个本实验 worker，不触碰其他 GPU 进程。设计中途资源复查发现空闲卡陆续被其他任务占用，因此在任何实际 Student 运行前将并发数从五改为二，并使设备准入按上述固定规则动态选择；各次训练内容和预算不变。若首次启动时无合格卡，保持 preparation，不创建 execution 或加载 Student；一旦开始，后继运行可等待合格卡。每个训练 worker 在同一常驻最终模型上完成自己的十二题评测。固定随机性减少可控差异，但不泛化为所有硬件/版本的逐位可复现保证。

实际运行后必须核对三对的初始 adapter 摘要、CPU/CUDA RNG、可训练范围、优化器空状态、全十轮顺序及配置相同；每次完整物理 Token 量相同；第一遍未更新参数下各包 NLL 差异与 Q−P 恒等式误差均小于 1e-5（FP32 求和与系数恢复有舍入）。该恒等式比较同一参数/同一逐行随机实现的目标；后续两臂参数已经不同，不能机械地用其相减作同一解释。训练后可验证 adapter 确已更新。每个 step 的全局加权损失、各包平均 NLL、梯度范数、耗时与累计 Token 留档。

## 3. 训练前冻结的独立十二题

来源是既有冻结 FinQA test JSON，SHA256 `831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc`。问题及完整 pre_text/table/post_text 原样公开，不仅提供选中数字；年份、无关值及 OCR 异常同样进入统一 numeric catalog。目标、可接受充分依据、财务恒等式与语义解释只存在离线私有评测文件，不进入模型提示或运行工具。

| 题 | 源问题 ID | 目标（精确参考单位） |
| --- | --- | --- |
| T1 | IPG/2008/page_72.pdf-2 | 2008 未确认税收优惠余额变化：148.8−134.8=14 百万美元 |
| T2 | PPG/2008/page_52.pdf-3 | 2008 相对 2007 应计余额变化：99−110=−11 百万美元 |
| T3 | AMT/2006/page_113.pdf-2 | 2004 员工离职负债变化：665−2239=−1574 千美元 |
| T4 | ABMD/2008/page_86.pdf-3 | 2008 相对 2007 正式滚动表未确认优惠余额变化率：(168−224)/224×100=−25% |
| T5 | AON/2007/page_188.pdf-3 | 2007 未确认税收优惠余额变化：70−53=17 百万美元 |
| T6 | ETR/2013/page_21.pdf-3 | 2012 批发业务净收入变化：1854−2045=−191 百万美元 |
| R1 | AMT/2012/page_50.pdf-1 | 12 月占第四季度回购份额：102400/619314×100% |
| R2 | PNC/2012/page_174.pdf-5 | commercial 占重组债务总额：541/2859×100% |
| R3 | UAA/2016/page_42.pdf-4 | 2016 相对 2015 营运资本增长：(1279337−1019953)/1019953×100% |
| R4 | UNP/2011/page_24.pdf-3 | 公司定义的调整后自由现金流增长：(1415−699)/699×100% |
| R5 | LMT/2016/page_49.pdf-4 | 三年 MFC 经营利润均值：(1018+1282+1344)/3 百万美元 |
| R6 | CB/2008/page_229.pdf-2 | 三年实际摊销均值：(90+77+64)/3=77 百万美元 |

前六题是主要余额/期间变化迁移对象，后六题是比例、公司指标、跨期汇总回归检查。23 个已登记充分依据与 20 个来源财务恒等式进行精确有理数检查；这些只是有限可接受见证，不是必须执行的路线菜单或穷尽全部正确解法。所有 12 张来源页面彼此不同，且不与六张训练页面重合。

**隔离范围是页面，不是公司/报告或预训练语料。**T5 与训练 L1 同为 AON 2007 报告，但不同页面和账户；R4 与训练 F2 同为 UNP、不同时期。候选筛选属于目的性开发集，部分来源曾在早期选择中被阅读；LMT 页面在旧源码目录有来源级列举。没有模型预训练未见、独立专家盲选、随机总体代表性声明。基线若饱和也保留该固定面板。

事先剔除 KHC 2016–2018 题，是因为起点可能指 2016 年初或年末，不能用 FinQA exe_ans 倒推唯一语义；替换为期间明确的 AON T5。剔除 APD 摊销均值候选，是因为闭合页面未清楚建立拟采用的百万美元单位。上述选择均在首次实际 Student 运行之前完成，不基于 P/Q 输出。

关键语义：T3 只能采用 2004 员工离职项而非租赁或总计；T4 采用排除利息的正式滚动表，不能以包含利息的粗略 prose 0.3m/0.2m 替换；T6 文本直接披露减少 191，不等于 Student 实际执行了计算；R4 使用公司表内的调整定义，非泛化的 CFO−capex；R5 原文 p14 确立百万美元，R6 actual 摊销与后续预计摊销分开。`panel_selection.json` 保存各题完整语义、来源定位、选中值、候选路线与排除说明。

## 4. 相同开放 Harness 的本地 Student 传输

Teacher 的 Flash/high、T 指令和既有轨迹完全不变；本轮不调用 Teacher。Student 使用同一个 T 系统文本、完整公开输入、原 calculate/read_source/notebook 实现、严格 JSON 事件和第一 Final 总是终止的开放规则。没有 accept gate、候选公式菜单、强制读证据或在线答案反馈。

新本地传输是真实 `model.generate`，不是伪造 HTTP 响应或回放教师文本。所有七个 Student 变体统一：greedy、do_sample=False、beam=1、repetition penalty=1、每响应最多 1024 新 Token、最多 32 响应及 32 工具调用。上下文上限 32768，完整当前输入加 1024 保留必须容纳；超限不裁剪、不补采样。request byte cap 延用 98304。初始十二题 prompt 长度在 CPU 上先检查；新增评测提示的编码不等于对原训练行重新分词。

decoder 仅移除真正生成的最后 EOS（151645 或 151643）；不清理 JSON 围栏、改写模型内容、删除其他特殊符号或提供 JSON grammar。无法形成合法事件时采用相同通用格式错误反馈，原响应原样留存。局部新传输拒绝解析结果中的孤立 Unicode surrogate，防止无效字符串使 UTF-8 工件落盘失败；不更改历史 parser。空生成、长度终止、上下文限制分别记录；没有真实 generate 时不伪造 assistant.raw。

本地每次 request、完整生成 token IDs、实际公开字符串、finish reason、prompt SHA/长度、工具调用及回执、Final、notebook、result 和清单均留档，origin 为 local_student_generation，明确不是 HTTP。每个生成进程只接收公开材料与训练模型身份；不 import 本轮目标/评分模块、不读 `.env`，运行环境不传 API key，模型 local_files_only/token=False；Python 网络入口与私有评测文件读入口守卫记录全零。这些是工程隔离证据，不是任意代码安全隔离证明。

Student 1024 Token 本地响应上限与旧 Teacher 16384 上限不同，因此不能用本轮 Student 表现与 Teacher 批次直接比较为能力差异。但 B0、P、Q 的配置完全相同。

## 5. 统一新评测政策与离线评审

七个模型完成 84 个登记会话后再统一离线评分。缺失、未开始或资源终止仍保留固定分母，不能从统计中移除。回答数值与完整可验证轨迹分开，另报交付/终止原因。无 Final 的目标答案保留 UNDETERMINED，不从成功前缀推断正确或确定金融错误；完整轨迹不得 PASS。可见错误答案、协议失败及资源未知不能混同。

数值核心沿用 `publication_tolerance.v2`：原 Final.value 优先于 explanation 中其他数字，原始出版精度决定允差，主要答案容差上限仍为 **0.005 参考单位**。不从 tool 或其他字段的更细数字救回粗主答案。次要显示字段按自身精度另检。所有变体共用以下**事先声明的新任务物理量适配**，不追改上轮 2 条 FAIL 或任何历史资格结果：

- percent、美元 million/thousand 的有限单位别名统一处理；million↔thousand 换算同时作用于值及出版量子，主要上限在参考单位仍是 0.005。单位语义与公式、对象是否匹配仍需评审。
- “decrease of 11 million”与有符号变化 −11 是同一物理量的两种表述。评审必须保留原正数及原单位，额外登记方向乘数、真实 Final 中的明确负向词引用和解释；不能改写 Final 数字。负数不能再次翻转，不能根据 gold 推断方向。
- 被选计算若输出正减少幅值，其方向也必须在该调用或之前有明确 decrease/reduction 等语义或变量名证据；后到 Final 不能修补先前含混的 old−new。仅减法次序不自动解释成“减少幅值”。答案可 PASS 而计算物理量/完整轨迹仍未建立。

自动工具重放只证明实际表达式、实际消费值及前序 result_id 引用；不独立认证财务公式、期间、角色或单位。评审逐题引用原始消息，检查公式适用、变量对应、单位处理、出版对齐及 Final 一致性；记录所选真实 calculation.call_id、其他数值断言与路线观察。预登记路线不是强制模板，合法的其他充分依据可凭公开材料判定。该人工代理评审不是独立专家盲审；该限制必须保留。

主结果按 B0、每 seed 的 P/Q，分别给 transfer 6、regression 6、全部 12 的答案及完整轨迹 PASS/FAIL/UNDETERMINED 数；给三组逐 seed Q−P 与简单均值，样本太少不声称统计显著。路线选择仅是机制观察；采用明细更多本身不是收益。正差异也共同加权了唯一明细样本的措辞、来源解释与公式组织，不能归因于抽象路线普遍优越。

## 6. 工件与复现入口

源码包：`trusted_synthesis.experiments.finance_qa_vnext_pq_student`。

实验根：`trusted_data_synthesis/artifacts/qa_vnext_pq_student/pq_3seed_20260910`。

| 子目录 | 内容 |
| --- | --- |
| preparation | 推送后的源码快照、审计原件、设计副本、精确权重、CPU 接线、12 题公私文件、政策、检查点绑定与新控制结果 |
| training/P_11 等 | 身份、十次全遍历更新记录、最终 adapter.safetensors、训练报告、清单 |
| evaluation/B0 等 | 每模型十二个原始本地会话及模型/配置/报告清单 |
| worker_logs / worker_guards | 原进程 stdout/stderr 与网络/私有读取计数 |
| execution | 固定登记、各进程退出、实际配对与预算核验 |
| assessment / closeout | 离线审计、人工评审模板/输入、资格和配对结果 |

运行命令（先完成代码/设计提交与推送；`prepare` 与 `run` 均只允许一次，不自动复跑）：

```bash
PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_pq_student.stage prepare --root /data1/zhuxinrui/projects/Data-Synthesis
PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_pq_student.stage run --root /data1/zhuxinrui/projects/Data-Synthesis
PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_pq_student.stage assess --root /data1/zhuxinrui/projects/Data-Synthesis
```

最终需输入完成的逐会话离线 review 文件，使用同入口 `finalize --reviews <path>`。15GB 基础模型不入 Git，绑定文件与约每个 10MB 的六个最终 adapter、公开预测和审计工件随发布保留。失败不自动换配置、换题、延长训练或再次采样；如果实现故障使预定对照未完成，必须如实报告，而不隐去失败尝试。

## 7. 待运行后追加

冻结提交、真实加载/完成状态、新控制数量、配对恒等式误差、训练耗时/峰值显存、84 个会话的交付与任务结果、主要迁移和回归的逐 seed 对照、已观察路线、局限与发布提交将在本节追加。当前设计阶段无能力或效用结论。
