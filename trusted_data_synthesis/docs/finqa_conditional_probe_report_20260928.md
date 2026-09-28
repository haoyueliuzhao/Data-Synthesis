# FinQA 条件性 Probe 材料库存报告

协议：`d17c2861b9b729081d41a7c79d48db0227be9dd53eeb6e2925f50f37e54c0d96`；执行提交：`5ca0e7675da482769ddcfc8a8540c80a6498f9e9`。

原始候选 **1000 题**；预先登记静态支持子总体 **165 题**；另 **835 题**保留排除记录，不冒称原总体已准入。

固定采集 **1320 会话**，其中 train **990**、sealed 表示／支持诊断 **330**。所有槽完成封存后才统一判定。

| 用途 | CompletePass（有限资格） | invalid | unknown |
|---|---:|---:|---:|
| train | 2 | 97 | 891 |
| sealed_diagnostic | 4 | 31 | 295 |

条件子总体材料支持准入：**未成立**。合格 train 原包全部保留：**2 包**；sealed 进入训练 **0 包**。

缺合格 train 支持：**163 题**；单状态：**2 题**；多状态：**0 题**。缺支持任务不再删除、不补采；单状态不提供 π 重权自由度。

## 调用与费用

模型固定 `deepseek-flash`，实际 API 请求 **4356**。按真实 usage 和最高峰价逐请求向上取整得到的费用上界为 **¥6.684336**，不是供应商实际账单。

输入 Token：**20283276**（缓存命中 18774922，未命中 1508354）；输出 Token：**364301**。

生成封存时间（原记录）：`2026-09-28T08:20:02.620079+00:00`。

## 解释边界

本报告仅聚合已冻结的资格、状态及结算记录，不重新评分、生成或读取私有答案。unknown 不等同于答案错误；CompletePass 仅代表已登记有限规则范围内的资格。

原 1000 题未获整体准入；Student 编码准入与正式训练仍是独立后续步骤。本轮不授权训练，不声称 SFT、Delayed-C 或 VTDO 收益。缺支持名册、原因计数和文件哈希见 summary.json；完整排除记录与逐题状态不重复复制，保留在绑定的原库存中。

[查看原库存](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_conditional_probe_inventory_01/inventory_complete/record.json)；[查看原范围登记](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_conditional_probe_inventory_01/protocol.json)。

## 非通过资格的原因计数

以下是有限判定器的判定原因，不是金融错误率。未获语义验证的附加自然语言说明反映当前判定覆盖边界，不能直接断言这些说明或最终金融答案错误。这类 unknown 是先触发的阻断原因，不表示后续工具／Final 已被完整核验，也不能反向解释为这些 unknown 其实都正确。原规则、原判定保持，不通过修改规则重判来增加材料。

| 用途 | 判定 | 原因 | 会话数 |
|---|---|---|---:|
| train | invalid | normal_terminal_has_no_completed_Final | 66 |
| train | invalid | submitted_program_result_contradicts_anchored_task | 23 |
| train | invalid | Final_value_or_declared_scale_contradicts_source_bound_program | 8 |
| train | unknown | additional_free_text_claims_not_semantically_verified | 865 |
| train | unknown | undeclared_Final_dimensionless_scale | 15 |
| train | unknown | Final_currency_scale_outside_finite_policy | 5 |
| train | unknown | numeric_leaf_missing_or_ambiguous_in_author_sources | 3 |
| train | unknown | actual_calculation_not_a_proved_required_dependency | 1 |
| train | unknown | non_numeric_value | 1 |
| train | unknown | unproved_alternative_or_extra_program_dependency | 1 |
| sealed_diagnostic | invalid | normal_terminal_has_no_completed_Final | 21 |
| sealed_diagnostic | invalid | Final_value_or_declared_scale_contradicts_source_bound_program | 6 |
| sealed_diagnostic | invalid | submitted_program_result_contradicts_anchored_task | 4 |
| sealed_diagnostic | unknown | additional_free_text_claims_not_semantically_verified | 288 |
| sealed_diagnostic | unknown | undeclared_Final_dimensionless_scale | 4 |
| sealed_diagnostic | unknown | numeric_leaf_missing_or_ambiguous_in_author_sources | 2 |
| sealed_diagnostic | unknown | Final_currency_scale_outside_finite_policy | 1 |
