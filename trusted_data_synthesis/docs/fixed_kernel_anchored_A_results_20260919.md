# 固定材料核 anchored A：六项训练最终结果与限定收口（2026-09-19）

## 结论

正式实验已于2026-09-19 08:31（北京时间）完成。六项新训练、十二次外层反馈及六个唯一最终检查点评估均完成；协调器正常结束，不是故障中断。主候选Full没有在本轮固定开发集上取得正的平均收益，保留Static，不启动B池或确认实验，C-only不得替代主候选。

这是已实现训练闭环的负向开发集结果，不是“训练没有执行”，也不是对VTDO理论或所有任务的一般否定。该180题开发集已参与随机反馈优化，不是独立验证或确认集。

| 条件 | seed11 | seed29 | seed47 | 合计 / 540 | 合格率 | 相对Static |
|---|---:|---:|---:|---:|---:|---:|
| Static | 67 | 66 | 37 | 170 | 31.48% | +0.00个百分点 |
| Full | 60 | 48 | 45 | 153 | 28.33% | -3.15个百分点 |
| C_only | 62 | 45 | 48 | 155 | 28.70% | -2.78个百分点 |

每个种子分母为180；540是180题在三个固定训练种子上的任务—种子评分次数，不是540道独立题。Static三训练及540次评分按原冻结绑定复用，未重训或重新评分。Full的种子差分别为−7、−18、+8题；C-only为−5、−21、+11题，不能只选seed47的正差报告收益。

## 同题同种子配对统计

沿用前轮CIK聚类重采样方案：固定seed=20260916、10000次，共享所有条件及种子的簇权重，保留三组等权，不重采训练种子。此处95%百分位范围仅描述固定已训练模型的开发来源重加权敏感性；因为dev参与过元学习、CIK簇有限且模型固定，不把它解释为独立验证置信区间或覆盖全部训练随机性，也不据此宣称统计显著性。

| 对照 | 获益配对 | 受损配对 | 不变 | 净变化 | 描述性95%范围（百分点） |
|---|---:|---:|---:|---:|---|
| C_only_minus_Static | 28 | 43 | 469 | -15 | [-4.96, 0.74] |
| Full_minus_C_only | 26 | 28 | 486 | -2 | [-3.69, 2.78] |
| Full_minus_Static | 28 | 45 | 467 | -17 | [-6.83, 2.04] |

实际来源簇数：12；有效重采样：10000/10000。空组样本不补抽。逐任务540行配对表留本地；公开报告只含汇总。

### 按开发任务组

| 组 | Static | Full | C-only | 每条件分母 |
|---|---:|---:|---:|---:|
| composition_required | 74 | 68 | 68 | 180 |
| dual_sufficient | 96 | 85 | 87 | 180 |
| other_financial | 0 | 0 | 0 | 180 |

## 真实外层更新与反馈

每项从配对原初始化及空Adam开始，不从Static最终模型加训。每次全类G使用3547个A原包、1681个当前Mapper状态及200个任务（含控制）；实际step0/200的360条随机轨迹全部生成封存后才独立评分。gJ通过真实Adam pullback、中心化C和分布更新接入下一次真实SFT；阶段报告在第1/201次optimizer更新完成后才发布。

反馈使用虚拟一步参数点、T=1、每题两次；最终分数来自epoch10/400步唯一检查点的180次greedy。反馈Q与最终分数不可直接比较，更不是可互换的收益指标。

| 任务 | 轮次 | 随机反馈 / 360 | Novelty项实际非零 | 加权TV | 对原先pi的KL | 对固定先验KL | 采样GPU数 |
|---|---:|---:|---|---:|---:|---:|---:|
| A_full_11 | epoch0 | 5 | False | 0.0151259 | 0.0012972 | 0.0012972 | 8 |
| A_full_11 | epoch5 | 97 | True | 0.0155294 | 0.00152273 | 0.00156511 | 4 |
| A_c_only_11 | epoch0 | 5 | False | 0.0151259 | 0.0012972 | 0.0012972 | 3 |
| A_c_only_11 | epoch5 | 97 | False | 0.0141042 | 0.00131079 | 0.00191142 | 4 |
| A_full_29 | epoch0 | 5 | False | 0.0161332 | 0.00138327 | 0.00138327 | 6 |
| A_full_29 | epoch5 | 102 | True | 0.015338 | 0.00154607 | 0.00180942 | 4 |
| A_c_only_29 | epoch0 | 5 | False | 0.0161332 | 0.00138327 | 0.00138327 | 4 |
| A_c_only_29 | epoch5 | 102 | False | 0.013953 | 0.00136398 | 0.00223469 | 6 |
| A_full_47 | epoch0 | 8 | False | 0.015886 | 0.00135568 | 0.00135568 | 1 |
| A_full_47 | epoch5 | 109 | True | 0.0141465 | 0.00135116 | 0.00179504 | 5 |
| A_c_only_47 | epoch0 | 8 | False | 0.015886 | 0.00135568 | 0.00135568 | 6 |
| A_c_only_47 | epoch5 | 109 | False | 0.0130646 | 0.00120145 | 0.0022379 | 7 |

Novelty项实际非零3/12轮，仅Full的三个epoch5。原包装层novelty_active在6/12轮为true，含C-only的epoch5，但其含义只是诊断潜势N非零，不表示该项进入更新：C-only的effective_novelty_exponent始终为0，Full为0.2。第一轮两臂pi与先验重合，N为0。未修改原始报告或训练，只在本收口明确区分潜势与实际系数。两臂均保留prior KL，不能把C-only说成无先验正则。控制任务分布保留标记均为True；最大中心化残差1.52466e-20。这证明本次有限工程路径被执行，不等于精确多步训练或greedy效用的全导数，也不保证实际最终效用单调。

## 已消费预算与效率

| 项目 | 实际 |
|---|---:|
| extra_G_sequence_tokens | 215,307,588 |
| feedback_sessions | 4,320 |
| final_greedy_sessions | 1,080 |
| generate_calls | 70,743 |
| optimizer_updates | 2,400 |
| packages_completed | 212,820 |
| rows_completed | 212,820 |
| sequence_tokens | 1,076,537,940 |
| target_tokens | 59,516,640 |

新增金融会话共5400（4320随机反馈+1080最终greedy）；实际generate 70,743 次，低于172800上限。SFT序列/监督token与额外全类G序列token分别计量，不能当成去重语料量或全部GPU计算量。

| 反馈反传计量 | 实际 |
|---|---:|
| cached_forward_target_positions | 332,692 |
| positive_reward_trajectories | 652 |
| responses_replayed | 3,726 |
| sampled_tokens_with_parameter_derivative | 166,346 |
| zero_reward_gradient_terms_skipped | 3,668 |

Q=0项在原执行时完成真实性与必要记录检查后省去GPU反传，分母仍为360；缺失、资源故障或回放失败没有当作零奖励。Q=1包含其实际采样的错误、恢复与EOS token，不施加SFT正响应mask。回放计数不包括完整prefill/KV重算FLOPs，cached_forward_target_positions也不是新的generate调用。

从首项启动至矩阵收口，墙钟约67.11小时；不能把并行任务各自elapsed相加当作墙钟。单外层梯度槽包含生成、评分及反传，SFT与适格GPU采样可并行；GPU准入按剩余60GiB、正式主存阈值256GiB，不要求GPU利用率归零。其他任务会等待此槽，等待不等于重复校验。

R3/R4资源、严格容差、完整前缀伴随与非空Adam控制沿用[既有资源及生产说明](fixed_kernel_anchored_runtime_20260916.md)。本收口未重跑这些控制或旧8/157项测试；只新增并通过三个轻量控制：配对计数/共享簇权重、缺失评分不作零分、非零Novelty潜势不等于C-only启用该项。

## 保存评分的失败标签（不重新评分）

聚合脚本单次读取新六项的1080份已保存assessment，Static使用旧已落盘结果；不打开任何原始会话、提示词、模型或梯度张量，不调用模型、工具环境或评分器。下表是评分理由计数，不等于经过轨迹因果分析的失败机制。

| 保存的reason | Static | Full | C-only |
|---|---:|---:|---:|
| PASS | 170 | 153 | 155 |
| assessment.final_not_supported_by_result | 68 | 69 | 75 |
| assessment.final_selected_actual_period | 1 | 2 | 6 |
| assessment.mean_requires_all_three_actual_interval_amounts | 8 | 14 | 15 |
| assessment.not_a_financial_arithmetic_result | 1 | 0 | 2 |
| assessment.not_equivalent_under_admitted_public_relations | 18 | 26 | 25 |
| assessment.one_actual_selection_support_required | 3 | 4 | 6 |
| assessment.selection_unique_public_candidate_period | 3 | 8 | 1 |
| assessment.successful_support_result_required | 1 | 0 | 1 |
| invalid_numeric_literal | 1 | 1 | 0 |
| no_final | 264 | 261 | 253 |
| tool.unit_dimension_conflict | 2 | 2 | 1 |

`no_final`不能表述成财务计算答错；支持证明、方法或数量失败也不自动等同某个根因。没有把未确定方法补成目标方法、按答案相等重标方法或修补Final。方法标签汇总保存在JSON，非训练材料的精细类完备性证据。

## 下一步与证据边界

1. 本轮收口，保留Static。Full是唯一主候选，C-only即使局部种子更高也不替换候选；B及确认实验均未启动。
2. 已测到本次工程闭环，但未测到本次两个分布干预的正平均收益。不能推广成VTDO在任何数据或超参数上都无效，也不能从负差直接断言实现错误。
3. 如继续研究，建议先用已保存C/pi、任务配对和训练轨迹提出可证伪的偏差来源假设，再另行冻结一个有对照的修订实验。当前未启动新训练、增加反馈轮次/预算、修改任务或增加确认集；这些不冒充本轮自然续跑。
4. 本轮可能的代理目标与最终greedy目标不匹配、跨任务干扰或种子交互均仍是假设，不作已证明因果解释。进一步实验需新的明确范围；原始会话深度审计也尚未执行。

## 追溯

- 登记计划：`anchored_registered_A_plan:a48f25774415bafa7f1fcbfdce72de51aebcbb1df3b320d37af2bdebba31f9b1`
- 完成矩阵：`anchored_A_complete_matrix:bd736f023225a1e967cf1c13e96bd530f827da183afbf03d78e3461d4e2759b9`
- 本收口报告：`anchored_A_saved_score_closure:7bc364f71e9f3fc5543c1e678dac0bcd9b33181609896a2ecefcc0bec8aa0528`
- 数据：[公开汇总JSON](../artifacts/qa_vnext_fixed_kernel_value/anchored_sources_20260916/registered_A/closure_20260919/report.json)
- 逐项实际开始/训练结束/最终结束UTC时间、报告ID、反馈计量和描述性统计均保存在该JSON。原始会话、模型、梯度及逐任务配对表不随本次公开汇总发布。
