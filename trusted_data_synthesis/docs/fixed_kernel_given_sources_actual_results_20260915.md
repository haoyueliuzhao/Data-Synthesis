# 给定公开来源：固定材料核的同接口训练价值实验结果

状态：`COMPLETE_FIXED_GIVEN_SOURCES_DEVELOPMENT`；报告 `given_sources_final_report:a358507ef3de20e1a82dca176ad94622b1ef9b07248dd564f6b1519020de9e7c`。

本轮完整执行10模型×180开发题，共1,800会话；三组各60题，固定分母不删失败、UNKNOWN或无Final。
效用为J_sources：给定方法中立的原始公开来源后，从空工具表自主读取、计算和交付。不是完整快照J_snapshot，不覆盖旧R0/R1。

开始：2026-09-15T13:56:37.109180+00:00；完成评分汇总：2026-09-15T18:49:14.026247+00:00（时间为UTC）。

## 模型与三组结果

| 模型 | 完整资格/180 | 双充分/60 | 三期均值/60 | 峰值后查询/60 | J_sources |
|---|---:|---:|---:|---:|---:|
| unfinetuned_base | 3/180 | 0/60 | 3/60 | 0/60 | 0.016667 |
| A_alpha0_11 | 67/180 | 34/60 | 33/60 | 0/60 | 0.372222 |
| A_plus_11 | 55/180 | 28/60 | 27/60 | 0/60 | 0.305556 |
| A_minus_11 | 54/180 | 29/60 | 25/60 | 0/60 | 0.300000 |
| A_alpha0_29 | 66/180 | 35/60 | 31/60 | 0/60 | 0.366667 |
| A_plus_29 | 62/180 | 27/60 | 35/60 | 0/60 | 0.344444 |
| A_minus_29 | 49/180 | 29/60 | 20/60 | 0/60 | 0.272222 |
| A_alpha0_47 | 37/180 | 27/60 | 10/60 | 0/60 | 0.205556 |
| A_plus_47 | 49/180 | 34/60 | 15/60 | 0/60 | 0.272222 |
| A_minus_47 | 51/180 | 31/60 | 20/60 | 0/60 | 0.283333 |

## SFT效应与分布增量分开报告

三种子平均效用（精确分数）：`{'alpha0': '17/54', 'plus': '83/270', 'minus': '77/270'}`。基座为`1/60`，不是alpha0或额外训练种子。

效应（精确分数）：`{'SFT_alpha0_minus_base': '161/540', 'pi_plus_minus_alpha0': '-1/135', 'pi_minus_minus_alpha0': '-4/135'}`。分布差异来自同题同种子配对，并与三个组等权主效用一致。

严格正收益/固定平局顺序下选择：**alpha0**。本次不自动获得B或确认准入。

## 执行阶段诊断

以下阶段可重叠，不加成临时总分。

| 模型/组 | 数值读取 | 成功计算 | Final | 工具错误 | 上下文拒绝 |
|---|---:|---:|---:|---:|---:|
| unfinetuned_base/dual_sufficient | 4 | 3 | 59 | 4 | 0 |
| unfinetuned_base/composition_required | 4 | 3 | 55 | 10 | 2 |
| unfinetuned_base/other_financial | 2 | 2 | 42 | 15 | 1 |
| A_alpha0_11/dual_sufficient | 60 | 60 | 59 | 1 | 0 |
| A_alpha0_11/composition_required | 60 | 52 | 37 | 10 | 13 |
| A_alpha0_11/other_financial | 58 | 1 | 2 | 53 | 5 |
| A_plus_11/dual_sufficient | 60 | 60 | 59 | 0 | 1 |
| A_plus_11/composition_required | 60 | 43 | 37 | 26 | 6 |
| A_plus_11/other_financial | 57 | 1 | 2 | 51 | 2 |
| A_minus_11/dual_sufficient | 60 | 60 | 58 | 0 | 1 |
| A_minus_11/composition_required | 60 | 57 | 34 | 9 | 22 |
| A_minus_11/other_financial | 60 | 2 | 5 | 46 | 4 |
| A_alpha0_29/dual_sufficient | 60 | 60 | 60 | 0 | 0 |
| A_alpha0_29/composition_required | 60 | 40 | 37 | 24 | 3 |
| A_alpha0_29/other_financial | 59 | 4 | 5 | 51 | 1 |
| A_plus_29/dual_sufficient | 60 | 60 | 56 | 2 | 1 |
| A_plus_29/composition_required | 60 | 44 | 43 | 21 | 4 |
| A_plus_29/other_financial | 57 | 1 | 10 | 56 | 2 |
| A_minus_29/dual_sufficient | 60 | 59 | 58 | 1 | 1 |
| A_minus_29/composition_required | 57 | 36 | 28 | 22 | 10 |
| A_minus_29/other_financial | 55 | 1 | 8 | 49 | 2 |
| A_alpha0_47/dual_sufficient | 60 | 60 | 58 | 0 | 2 |
| A_alpha0_47/composition_required | 60 | 24 | 14 | 38 | 9 |
| A_alpha0_47/other_financial | 60 | 1 | 4 | 45 | 2 |
| A_plus_47/dual_sufficient | 60 | 60 | 59 | 0 | 1 |
| A_plus_47/composition_required | 60 | 31 | 20 | 30 | 11 |
| A_plus_47/other_financial | 60 | 0 | 7 | 54 | 1 |
| A_minus_47/dual_sufficient | 60 | 60 | 59 | 0 | 1 |
| A_minus_47/composition_required | 60 | 42 | 26 | 20 | 17 |
| A_minus_47/other_financial | 60 | 2 | 6 | 50 | 0 |

## 方法与失败原因

- unfinetuned_base：方法 `{'UNDETERMINED': 177, 'temporal_component_integration': 3}`；原因 `{'no_final': 24, 'PASS': 3, 'assessment.successful_support_result_required': 149, 'assessment.not_equivalent_under_admitted_public_relations': 3, 'assessment.one_actual_selection_support_required': 1}`。
- A_alpha0_11：方法 `{'UNDETERMINED': 113, 'temporal_component_integration': 33, 'endpoint': 34}`；原因 `{'no_final': 82, 'assessment.mean_requires_all_three_actual_interval_amounts': 3, 'PASS': 67, 'assessment.final_not_supported_by_result': 21, 'assessment.not_equivalent_under_admitted_public_relations': 5, 'assessment.not_a_financial_arithmetic_result': 1, 'assessment.one_actual_selection_support_required': 1}`。
- A_plus_11：方法 `{'UNDETERMINED': 125, 'endpoint': 28, 'temporal_component_integration': 27}`；原因 `{'no_final': 82, 'assessment.mean_requires_all_three_actual_interval_amounts': 8, 'assessment.final_not_supported_by_result': 26, 'PASS': 55, 'assessment.not_equivalent_under_admitted_public_relations': 7, 'assessment.one_actual_selection_support_required': 1, 'invalid_numeric_literal': 1}`。
- A_minus_11：方法 `{'UNDETERMINED': 126, 'endpoint': 29, 'temporal_component_integration': 25}`；原因 `{'no_final': 83, 'assessment.mean_requires_all_three_actual_interval_amounts': 7, 'assessment.not_equivalent_under_admitted_public_relations': 8, 'PASS': 54, 'assessment.final_not_supported_by_result': 23, 'assessment.not_a_financial_arithmetic_result': 1, 'assessment.selection_unique_public_candidate_period': 1, 'assessment.final_selected_actual_period': 1, 'assessment.one_actual_selection_support_required': 1, 'tool.unit_dimension_conflict': 1}`。
- A_alpha0_29：方法 `{'UNDETERMINED': 114, 'temporal_component_integration': 31, 'endpoint': 35}`；原因 `{'no_final': 78, 'assessment.mean_requires_all_three_actual_interval_amounts': 4, 'PASS': 66, 'assessment.final_not_supported_by_result': 21, 'assessment.not_equivalent_under_admitted_public_relations': 5, 'assessment.selection_unique_public_candidate_period': 1, 'assessment.one_actual_selection_support_required': 2, 'tool.unit_dimension_conflict': 1, 'invalid_numeric_literal': 1, 'assessment.successful_support_result_required': 1}`。
- A_plus_29：方法 `{'UNDETERMINED': 118, 'temporal_component_integration': 35, 'endpoint': 27}`；原因 `{'no_final': 71, 'PASS': 62, 'assessment.not_equivalent_under_admitted_public_relations': 8, 'assessment.final_not_supported_by_result': 25, 'assessment.mean_requires_all_three_actual_interval_amounts': 5, 'assessment.one_actual_selection_support_required': 7, 'assessment.final_selected_actual_period': 1, 'invalid_numeric_literal': 1}`。
- A_minus_29：方法 `{'UNDETERMINED': 131, 'endpoint': 29, 'temporal_component_integration': 20}`；原因 `{'no_final': 86, 'assessment.mean_requires_all_three_actual_interval_amounts': 7, 'assessment.not_equivalent_under_admitted_public_relations': 7, 'PASS': 49, 'assessment.final_not_supported_by_result': 23, 'assessment.peak_requires_all_three_candidate_periods': 2, 'assessment.one_actual_selection_support_required': 5, 'assessment.final_selected_actual_period': 1}`。
- A_alpha0_47：方法 `{'UNDETERMINED': 143, 'endpoint': 27, 'temporal_component_integration': 10}`；原因 `{'no_final': 104, 'assessment.final_not_supported_by_result': 26, 'PASS': 37, 'assessment.not_equivalent_under_admitted_public_relations': 8, 'assessment.final_selected_actual_period': 1, 'assessment.mean_requires_all_three_actual_interval_amounts': 1, 'assessment.selection_unique_public_candidate_period': 2, 'tool.unit_dimension_conflict': 1}`。
- A_plus_47：方法 `{'UNDETERMINED': 131, 'temporal_component_integration': 15, 'endpoint': 34}`；原因 `{'no_final': 94, 'PASS': 49, 'assessment.selection_unique_public_candidate_period': 6, 'assessment.final_not_supported_by_result': 26, 'assessment.not_equivalent_under_admitted_public_relations': 4, 'assessment.final_selected_actual_period': 1}`。
- A_minus_47：方法 `{'UNDETERMINED': 129, 'endpoint': 31, 'temporal_component_integration': 20}`；原因 `{'assessment.final_selected_actual_period': 2, 'no_final': 89, 'assessment.final_not_supported_by_result': 24, 'PASS': 51, 'tool.unit_dimension_conflict': 2, 'assessment.mean_requires_all_three_actual_interval_amounts': 3, 'assessment.not_equivalent_under_admitted_public_relations': 6, 'assessment.selection_unique_public_candidate_period': 2, 'assessment.successful_support_result_required': 1}`。

## 资源与边界

实际资源：`{'actual_model_generation_calls': 29509, 'generated_tokens': 1631328, 'context_rejections': 125, 'model_weight_loads': 10, 'final_adapter_loads': 9}`；模型生成上限57,600。未使用调用容量不表示缺失会话。

| 模型 | worker秒 | reserved显存峰值GiB |
|---|---:|---:|
| unfinetuned_base | 5638.60 | 78.672 |
| A_alpha0_11 | 9954.66 | 78.654 |
| A_plus_11 | 9360.64 | 78.561 |
| A_minus_11 | 10533.19 | 78.418 |
| A_alpha0_29 | 8116.80 | 71.508 |
| A_plus_29 | 8246.74 | 78.279 |
| A_minus_29 | 9731.60 | 70.727 |
| A_alpha0_47 | 11731.91 | 70.979 |
| A_plus_47 | 11037.51 | 78.080 |
| A_minus_47 | 9087.64 | 58.551 |

180开发题未进入Student梯度训练，但已有研究者开发/诊断曝光，不能称为新盲测。来源与训练簇隔离通过；12个开发来源簇不能被任务×种子乘积替代为独立题量。
公开窗口保留全部已注册指标记录，未按私有叶子选择；v2无损共享元数据只解决初始历史空间不足，未改SYSTEM、数值记录、指针或来源ID。
端点、movement、均值和完整峰值依赖的必要新接口正控通过；不完整峰值支持的反例被拒绝。这些CPU脚本未发送给Student，不计入模型结果。
金融资格仍核查首个Final、实际来源、单位、期间及完整符号/选择支持；来源提供不免除评分要求。
A_minus_47 was trained by8GPU globalSUM with disclosed numerical/RNG differences; unchanged checkpoint reused
效应只限此固定材料核与给定来源环境。没有据此宣布完整快照检索改善、总体统计显著、完整anchored或HierLoss有效。
不重训、不再采Probe、不根据结果改来源或说明。B、720题确认及独立检索能力适配均未启动，需另行授权。
原始会话、callback、源视图与原生材料留本地；仅发布明确的小型输入准入/计划/汇总和本文。
