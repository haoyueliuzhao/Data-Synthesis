# 给定来源三臂：配对结果与行为机制收口

报告`given_sources_closure_report:4e18038d94452ba331c4ffb04d5e1967b60311749bb08b88ce80a3c06d77b221`；原结果`given_sources_final_report:a358507ef3de20e1a82dca176ad94622b1ef9b07248dd564f6b1519020de9e7c`。

仅分析既有540行task×seed配对；微调模型1,620份会话各读一次。没有新模型调用、重评分、callback扫描或改写Final。

成功/失败转移：`{'plus': {'gain': 32, 'loss': 36, 'unchanged': 472}, 'minus': {'gain': 26, 'loss': 42, 'unchanged': 472}}`。

每任务三种子差异符号：`{'plus': {'all_three_zero': 133, 'nonnegative_with_gain': 19, 'nonpositive_with_loss': 19, 'mixed_positive_and_negative': 9}, 'minus': {'all_three_zero': 133, 'nonpositive_with_loss': 23, 'nonnegative_with_gain': 13, 'mixed_positive_and_negative': 11}}`。

CSV保留三臂Q、差值、终态、首失败原因和训练配置/后端；A_minus_47仍为8GPU global SUM。

| CIK | 配对行 | plus得/失/净 | minus得/失/净 |
|---|---:|---:|---:|
| cik:0000019617 | 39 | 2/4/-2 | 0/6/-6 |
| cik:0000021344 | 81 | 4/12/-8 | 4/7/-3 |
| cik:0000072971 | 18 | 1/2/-1 | 3/3/+0 |
| cik:0000092122 | 33 | 2/0/+2 | 3/1/+2 |
| cik:0000093410 | 39 | 2/2/+0 | 2/3/-1 |
| cik:0000101829 | 33 | 3/3/+0 | 1/2/-1 |
| cik:0000109198 | 27 | 1/0/+1 | 1/0/+1 |
| cik:0000731766 | 39 | 2/2/+0 | 2/3/-1 |
| cik:0000796343 | 129 | 6/9/-3 | 5/8/-3 |
| cik:0000804328 | 30 | 6/0/+6 | 1/2/-1 |
| cik:0001065280 | 39 | 1/2/-1 | 3/2/+1 |
| cik:0001403161 | 33 | 2/0/+2 | 1/5/-4 |

## 来源簇配对区间（开发描述）

固定seed20260916、10,000次CIK重采样；同一簇权重用于所有臂/种子，各次保留三组等权。

| 比较 | 点估计/百分点 | 95%百分位区间/百分点 |
|---|---:|---:|
| plus_minus_alpha0 | -0.741 | [-4.180, +2.768] |
| minus_minus_alpha0 | -2.963 | [-5.687, +0.001] |
| alpha0_minus_base | +29.815 | [+26.433, +34.032] |

这只描述固定这些模型的开发来源抽样不确定性，不是确认，不覆盖全部训练随机性；跨零不证明等效。

minus区间上界的未四舍五入数值为+0.0005144个百分点，仍跨零，不能由于表格显示
接近零就宣布负效应已显著。两种固定分布的均值均没有正收益，因此本轮保留alpha0；
这既不证明所有分布优化无效，也不允许按某个种子或局部题组改选方向。

## 峰值选择链

540会话的重叠观测：`{'all_three_primary_periods_read': 290, 'any_successful_selection': 183, 'full_primary_selection_observed': 82, 'secondary_in_selected_period_read': 20, 'secondary_read_after_selection': 16, 'successful_linked_lookup': 1, 'final_names_complete_selection': 0, 'final_names_linked_lookup': 1, 'Final_object_observed': 49, 'runtime_recognized_Final': 49}`。

完整primary选择观测要求三期公开主指标读数及实际选择返回覆盖全部期间；先读后选与选后读另列。不以calculate数量替代选择链，也不新增财务判分。

在540次峰值组会话中，读齐三期不是最末端交付：完整主指标选择只观测到82次，
同期间次指标读取20次，成功关联查询1次。这支持继续检查“选择—关联—Final”的
组合链路；各计数是重叠行为证据，不能相减后直接当作互斥失败原因或因果损失量。

## Final失配

既有final_not_supported_by_result的模式：`{'sessions': 215, 'referenced_numeric_result_exists': 215, 'requested_rounding_mismatch': 215, 'raw_number_equal_but_unit_labels_differ': 0, 'difference_within_one_requested_rounding_quantum': 47, 'another_numeric_tool_matches_submitted_amount': 0, 'exact_factor_100_or_inverse': 0, 'exact_factor_million_or_inverse': 0, 'unresolved_other_numeric_mismatch': 168}`。

结果存在、单位标签、100/百万倍数、接近舍入量子、另一个工具金额匹配和未解数值差异可以重叠，不是已证因果根因；换引用不保证通过完整资格。

215次均找到了被引用的数值结果，因而不能把本批问题统称为“引用ID不存在”。其中
47次差额不超过一个请求舍入量子，只说明接近程度，不足以断言修正舍入就会合格；
其余168次仍是未解释的数值失配。这里未观测到指定倍数模式，也不等于证明整个
实验不存在单位/百分数类问题。没有据此修补任何回答或回填合格分数。

非目标概念读取/计算：`{'other_financial': {'read_non_target_concept': 83, 'successful_calculate': 13}, 'composition_required': {'read_non_target_concept': 6, 'successful_calculate': 369}, 'dual_sufficient': {'read_non_target_concept': 37, 'successful_calculate': 539}}`。非目标读取不是movement标签；三期聚合不是披露组件重建；失败轨迹未补标movement。

## 收口

继续保留alpha0，不启动原三臂B或确认。不改来源、提示、预算、困难组或主指标来救结果。
开发180题与训练200题不同，本配对表不能直接成为训练任务/状态Contribution标签。新C须在真实模型与优化器点、用J_sources反馈计算。
每会话小账留本地；发布配对CSV、汇总与本文，不上传callback原文。
