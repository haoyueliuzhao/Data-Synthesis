# FinQA 结构化公开动作 Probe 库存报告

协议：`cebb38c517cd48e3a68aea0b9c800a0f41bbf028b6d86589a7443ed5eee90624`；执行提交：`572179e0e3a21b71c81a4f60081e836ad5a9b7fe`。

原始候选 **1000 题**；预先登记静态支持子总体 **165 题**；另 **835 题**保留排除记录，不冒称原总体已准入。

固定采集 **1320 会话**，其中 train **990**、sealed 表示／支持诊断 **330**。所有槽完成封存后才统一判定。

| 用途 | CompletePass（有限资格） | invalid | unknown |
|---|---:|---:|---:|
| train | 121 | 641 | 228 |
| sealed_diagnostic | 45 | 204 | 81 |

条件子总体材料支持准入：**未成立**。合格 train 原包全部保留：**121 包**；sealed 进入训练 **0 包**。

缺合格 train 支持：**111 题**；单状态：**40 题**；多状态：**14 题**。缺支持任务不再删除、不补采；单状态不提供 π 重权自由度。

## 调用与费用

模型固定 `deepseek-flash`，实际 API 请求 **4151**。按真实 usage 和最高峰价逐请求向上取整得到的费用上界为 **¥5.892471**，不是供应商实际账单。

输入 Token：**20458788**（缓存命中 19049620，未命中 1409168）；输出 Token：**288760**。

生成封存时间（原记录）：`2026-09-28T09:33:16.184382+00:00`。

## 解释边界

本报告仅聚合已冻结的资格、状态及结算记录，不重新评分、生成或读取私有答案。unknown 不等同于答案错误；CompletePass 仅代表已登记有限规则范围内的资格。

原 1000 题未获整体准入；Student 编码准入与正式训练仍是独立后续步骤。本轮不授权训练，不声称 SFT、Delayed-C 或 VTDO 收益。缺支持名册、原因计数和文件哈希见 summary.json；完整排除记录与逐题状态不重复复制，保留在绑定的原库存中。

[查看原库存](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/structured_probe_followup_01/structured_inventory_01/inventory_complete/record.json)；[查看原范围登记](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/structured_probe_followup_01/structured_inventory_01/protocol.json)。

## 非通过资格的原因计数

以下是有限判定器的判定原因，不是金融错误率。未获语义验证的附加自然语言说明反映当前判定覆盖边界，不能直接断言这些说明或最终金融答案错误。这类 unknown 是先触发的阻断原因，不表示后续工具／Final 已被完整核验，也不能反向解释为这些 unknown 其实都正确。原规则、原判定保持，不通过修改规则重判来增加材料。

| 用途 | 判定 | 原因 | 会话数 |
|---|---|---|---:|
| train | invalid | submitted_program_result_contradicts_anchored_task | 335 |
| train | invalid | Final_value_or_declared_scale_contradicts_source_bound_program | 263 |
| train | invalid | normal_terminal_has_no_completed_Final | 30 |
| train | invalid | submitted_program_structure_invalid | 11 |
| train | invalid | submitted_program_does_not_execute | 2 |
| train | unknown | undeclared_Final_dimensionless_scale | 95 |
| train | unknown | numeric_leaf_missing_or_ambiguous_in_author_sources | 74 |
| train | unknown | Final_currency_scale_outside_finite_policy | 35 |
| train | unknown | actual_calculation_not_a_proved_required_dependency | 10 |
| train | unknown | unproved_alternative_or_extra_program_dependency | 6 |
| train | unknown | non_scalar_Final_outside_numerical_qualification | 5 |
| train | unknown | additional_free_text_claims_not_semantically_verified | 2 |
| train | unknown | non_numeric_value | 1 |
| sealed_diagnostic | invalid | submitted_program_result_contradicts_anchored_task | 104 |
| sealed_diagnostic | invalid | Final_value_or_declared_scale_contradicts_source_bound_program | 88 |
| sealed_diagnostic | invalid | submitted_program_structure_invalid | 6 |
| sealed_diagnostic | invalid | normal_terminal_has_no_completed_Final | 5 |
| sealed_diagnostic | invalid | submitted_program_does_not_execute | 1 |
| sealed_diagnostic | unknown | undeclared_Final_dimensionless_scale | 30 |
| sealed_diagnostic | unknown | numeric_leaf_missing_or_ambiguous_in_author_sources | 22 |
| sealed_diagnostic | unknown | Final_currency_scale_outside_finite_policy | 10 |
| sealed_diagnostic | unknown | actual_calculation_not_a_proved_required_dependency | 10 |
| sealed_diagnostic | unknown | unproved_alternative_or_extra_program_dependency | 4 |
| sealed_diagnostic | unknown | non_numeric_value | 3 |
| sealed_diagnostic | unknown | non_scalar_Final_outside_numerical_qualification | 2 |

## 本轮结构化输出与分布支持

`assessed_slots=1320` 表示全部槽已完成资格处理，不表示1320个合格槽。全部 4151 次响应中，严格空公开正文 4116 次，非空正文 35 次；其中非空白正文 35 次。空正文且恰好一个原生工具调用 4114 次；这只是输出合同合规，不等于完整金融资格。

`observed_D_pi=19`；完整总体 `D_pi=null（固定总体支持尚未齐全）`；`M_flex=14/165`。存在状态差异也不自动代表充分统计功效。

逐状态原包数和 API 输入／输出 Token 已保留于 summary.json；API Token 不是 Student 监督 Token。尚未执行 Student 编码准入，不能宣称训练 ready。

资格限于冻结的作者锚定规范 DAG，不覆盖全部代数等价解法。新旧差异仅能作为联合协议修订的开发观察；本报告没有改标签、删正文、合并旧包、重新评分或启动训练。
